"""Committee Model (Ensemble) Wrapper for conservative forces and epistemic uncertainty.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic autograd mechanics, unbiased variance, and stream safety.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence
import torch
import torch.nn as nn

from Libraries.cochem_torq_inference_errors import EnsembleConsensusError
from Libraries.cochem_torq_inference_schemas import CommitteeEnsembleConfig


@dataclass(frozen=True)
class CommitteePrediction:
    """Immutable data container for aggregated committee inference outputs. [M]"""

    mean_energy: torch.Tensor             # (B,) or scalar energy
    mean_forces: torch.Tensor             # (N, 3) or (B, N, 3) conservative forces
    energy_variance: torch.Tensor         # (B,) or scalar unbiased sample variance
    per_atom_force_variance: torch.Tensor # (N,) or (B, N) per-atom force variance
    max_force_std: float                  # Scalar max epistemic force std across atoms
    model_energies: torch.Tensor          # (M, ...) individual model energies
    model_forces: torch.Tensor            # (M, N, 3) individual model forces


def compute_committee_moments(
    energies: torch.Tensor,
    forces: torch.Tensor,
) -> CommitteePrediction:
    """Compute unbiased sample mean, energy variance, and per-atom force epistemic variance. [D]
    
    energies: (M,) or (M, B)
    forces: (M, N, 3) or (M, B, N, 3)
    """
    m = energies.shape[0]
    if m < 2:
        raise EnsembleConsensusError(
            f"Committee ensemble requires at least 2 models for variance estimation, got M={m}.",
            diagnostics={"num_models": m},
        )
    if forces.shape[0] != m:
        raise EnsembleConsensusError(
            f"Mismatched ensemble model count: energies has M={m}, forces has M={forces.shape[0]}.",
            diagnostics={"energies_M": m, "forces_M": forces.shape[0]},
        )

    # 1. Conservative Energy and Force Means
    mean_e = torch.mean(energies, dim=0) # (B,) or scalar
    mean_f = torch.mean(forces, dim=0)   # (N, 3)

    # 2. Unbiased Sample Variance of Energy: 1/(M-1) sum_m (E_m - E_mean)^2
    e_diff = energies - mean_e.unsqueeze(0)
    e_var = torch.sum(e_diff ** 2, dim=0) / float(m - 1)

    # 3. Per-atom Force Epistemic Variance: 1/(3*(M-1)) sum_m ||F_{i,m} - F_{i,mean}||_2^2
    # forces: (M, N, 3) -> f_diff: (M, N, 3)
    f_diff = forces - mean_f.unsqueeze(0)
    # Norm squared over Cartesian coordinates (dim=-1)
    f_sq_norm = torch.sum(f_diff ** 2, dim=-1) # (M, N)
    # Sum over models and divide by 3*(M-1)
    atom_f_var = torch.sum(f_sq_norm, dim=0) / float(3.0 * (m - 1)) # (N,)

    # 4. Maximum Atomic Force Epistemic Standard Deviation:
    # alpha_F^{std} = max_i sqrt( 1/(M-1) sum_m ||F_{i,m} - F_{i,mean}||_2^2 )
    atom_f_sum = torch.sum(f_sq_norm, dim=0) / float(m - 1) # (N,)
    atom_f_std = torch.sqrt(torch.clamp(atom_f_sum, min=0.0))
    max_f_std = float(torch.max(atom_f_std).item())

    return CommitteePrediction(
        mean_energy=mean_e,
        mean_forces=mean_f,
        energy_variance=e_var,
        per_atom_force_variance=atom_f_var,
        max_force_std=max_f_std,
        model_energies=energies,
        model_forces=forces,
    )


class CommitteeEnsemble(nn.Module):
    """Ensemble wrapper coordinating M independent potential models with VRAM safeguards. [M]/[D]"""

    def __init__(
        self,
        models: Sequence[nn.Module],
        config: Optional[CommitteeEnsembleConfig] = None,
    ) -> None:
        super().__init__()
        if len(models) < 2:
            raise EnsembleConsensusError(
                f"Committee requires at least 2 potential models, got {len(models)}.",
                diagnostics={"num_models": len(models)},
            )
        self.models = nn.ModuleList(models)
        self.config = config or CommitteeEnsembleConfig(num_models_m=len(models))
        self.num_models = len(models)

    def forward(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Evaluate ensemble forward passes with sequential micro-batching and stream synchronization. [D]"""
        energies_list: List[torch.Tensor] = []
        forces_list: List[torch.Tensor] = []

        max_concurrent = max(1, self.config.max_concurrent_models_vram)
        is_cuda = torch.cuda.is_available()

        for idx, model in enumerate(self.models):
            # Model forward call
            out = model(*args, **kwargs)
            if isinstance(out, tuple):
                e_m, f_m = out[0], out[1]
            elif isinstance(out, dict):
                e_m, f_m = out["energy"], out["forces"]
            else:
                raise EnsembleConsensusError(
                    f"Model {idx} output type {type(out)} is not supported. Expected (energy, forces) tuple or dict.",
                    diagnostics={"model_index": idx, "out_type": str(type(out))},
                )

            energies_list.append(e_m)
            forces_list.append(f_m)

            # Stream synchronization at micro-batch boundaries or when enabled
            if is_cuda and self.config.synchronize_cuda_streams:
                if (idx + 1) % max_concurrent == 0 or (idx + 1) == self.num_models:
                    torch.cuda.synchronize()

        all_energies = torch.stack(energies_list, dim=0) # (M, ...)
        all_forces = torch.stack(forces_list, dim=0)     # (M, N, 3)

        return compute_committee_moments(all_energies, all_forces)

    def predict(self, *args: Any, **kwargs: Any) -> CommitteePrediction:
        """Alias for forward evaluation. [M]"""
        return self.forward(*args, **kwargs)
