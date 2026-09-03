"""Pure-PyTorch Cartesian Equivariant Tensor Backbone for CoChem-TORQ."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import torch
import torch.nn as nn

from cochem.torq.backbones.cutoff import RadialBasis, polynomial_cutoff
from cochem.torq.errors import (
    AutogradForceError,
    PeriodicBoundaryConditionError,
    TorqModelBackboneError,
)
from cochem.torq.models.schemas import TorqModelConfig

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


class EquivariantInteractionBlock(nn.Module):
    """Cartesian Equivariant message-passing interaction block [D].

    Updates scalar representations s_i and Cartesian vector representations v_i.
    Delta v_i = sum_j [ W_vv(r_ij) v_j + W_sv(r_ij) s_j r_hat_ij ] f_cut(r_ij)
    Delta s_i = sum_j [ W_ss(r_ij) s_j + W_vs(r_ij) (v_j . r_hat_ij) ] f_cut(r_ij)
    """

    def __init__(
        self,
        num_channels: int,
        num_radial_basis: int,
        r_max: float,
    ) -> None:
        super().__init__()
        self.num_channels = num_channels
        self.num_radial_basis = num_radial_basis
        self.r_max = r_max

        # Radial weight generator for the 4 equivariant channels [D]
        # Generates: [W_vv, W_sv, W_ss, W_vs] of shape (..., 4 * num_channels)
        self.radial_filter = nn.Sequential(
            nn.Linear(num_radial_basis, num_channels * 2),
            nn.SiLU(),
            nn.Linear(num_channels * 2, num_channels * 4),
        )

        # Self-interaction scalar MLP mixing s_i and ||v_i||^2 [D]
        self.scalar_self = nn.Sequential(
            nn.Linear(num_channels * 2, num_channels),
            nn.SiLU(),
            nn.Linear(num_channels, num_channels),
        )

        # Vector self-interaction: channel linear mixing [D]
        self.vector_channel_linear = nn.Linear(
            num_channels, num_channels, bias=False
        )

        # Scalar gating on vector representations [D]
        self.vector_gate = nn.Sequential(
            nn.Linear(num_channels, num_channels),
            nn.Sigmoid(),
        )

    def forward(
        self,
        s: torch.Tensor,
        v: torch.Tensor,
        radial_features: torch.Tensor,
        r_hat: torch.Tensor,
        dists: torch.Tensor,
        mask_self: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Perform equivariant message passing.

        s: (N, C)
        v: (N, C, 3)
        radial_features: (N, N, num_radial_basis)
        r_hat: (N, N, 3)
        dists: (N, N)
        mask_self: (N, N)
        """
        N, C = s.shape
        f_cut = polynomial_cutoff(dists, self.r_max).unsqueeze(-1)  # (N, N, 1)

        # Generate weights: (N, N, 4 * C)
        weights = (
            self.radial_filter(radial_features) * f_cut * mask_self.unsqueeze(-1)
        )
        w_vv, w_sv, w_ss, w_vs = torch.split(weights, C, dim=-1)

        # 1. Delta v:
        # Term 1: w_vv * v_j -> (N, N, C, 3)
        # einsum or broadcasting:
        # v has shape (N, C, 3). For j in range N, v_j is (N_j, C, 3)
        # w_vv has shape (N_i, N_j, C). w_vv.unsqueeze(-1) is (N_i, N_j, C, 1)
        term_vv = torch.einsum("ijc, jca -> ica", w_vv, v)

        # Term 2: w_sv * s_j * r_hat_ij
        # s has shape (N_j, C). w_sv has (N_i, N_j, C). s_weighted: (N_i, N_j, C)
        # r_hat has (N_i, N_j, 3). r_hat.unsqueeze(2): (N_i, N_j, 1, 3)
        term_sv = torch.einsum(
            "ijc, ija -> ica", w_sv * s.unsqueeze(0), r_hat
        )

        delta_v = term_vv + term_sv

        # 2. Delta s:
        # Term 1: w_ss * s_j
        term_ss = torch.einsum("ijc, jc -> ic", w_ss, s)

        # Term 2: w_vs * (v_j . r_hat_ij)
        # v_j . r_hat_ij: (N_i, N_j, C)
        v_dot_r = torch.einsum("jca, ija -> ijc", v, r_hat)
        term_vs = torch.einsum("ijc, ijc -> ic", w_vs, v_dot_r)

        delta_s = term_ss + term_vs

        # Apply residual updates
        s_new = s + delta_s
        v_new = v + delta_v

        # Self-interaction:
        # Vector norm squared ||v_i||^2: (N, C) [D]
        v_norm2 = torch.sum(v_new**2, dim=-1)
        s_combined = torch.cat([s_new, v_norm2], dim=-1)
        s_updated = s_new + self.scalar_self(s_combined)

        # Vector mixing: Linear across channels [D]
        # v_new has shape (N, C, 3). Permute to (N, 3, C) to apply Linear(C, C), then permute back
        v_perm = v_new.permute(0, 2, 1)  # (N, 3, C)
        v_mixed = self.vector_channel_linear(v_perm).permute(0, 2, 1)  # (N, C, 3)
        # Gated scaling
        gate = self.vector_gate(s_updated).unsqueeze(-1)  # (N, C, 1)
        v_updated = v_new + v_mixed * gate

        return s_updated, v_updated


class CartesianEquivariantBackbone(nn.Module):
    """Pure-PyTorch Cartesian Equivariant Tensor Network Backbone [D].

    Evaluates potential energy E, autograd forces F, and higher-order rank-2
    traceless symmetric tensor features A_i^(2e) = sum_c w_c (v_c (x) v_c - 1/3 ||v_c||^2 I).
    """

    def __init__(
        self,
        config: Optional[TorqModelConfig] = None,
        num_channels: int = 64,
        num_radial_basis: int = 32,
        num_layers: int = 3,
        r_max: float = 5.0,
        max_z: int = 118,
    ) -> None:
        super().__init__()
        if config is not None:
            self.num_channels = config.num_channels
            self.num_radial_basis = config.num_radial_basis
            self.num_layers = config.num_layers
            self.r_max = config.r_max
        else:
            self.num_channels = num_channels
            self.num_radial_basis = num_radial_basis
            self.num_layers = num_layers
            self.r_max = r_max

        # Species scalar embedding
        self.embedding = nn.Embedding(max_z + 1, self.num_channels)

        # Radial basis expansion
        self.radial_basis = RadialBasis(
            num_radial_basis=self.num_radial_basis,
            r_max=self.r_max,
            basis_type="bessel",
        )

        # Equivariant message passing layers
        self.layers = nn.ModuleList(
            [
                EquivariantInteractionBlock(
                    num_channels=self.num_channels,
                    num_radial_basis=self.num_radial_basis,
                    r_max=self.r_max,
                )
                for _ in range(self.num_layers)
            ]
        )

        # Multi-body rank-2 tensor weight projection: s_i -> w_c [D]
        self.tensor_weights = nn.Linear(self.num_channels, self.num_channels)

        # Scalar energy readout head: s_i -> E_i [D]
        self.energy_readout = nn.Sequential(
            nn.Linear(self.num_channels, self.num_channels // 2),
            nn.SiLU(),
            nn.Linear(self.num_channels // 2, 1),
        )

    def _compute_displacements(
        self,
        coords: torch.Tensor,
        cell: Optional[torch.Tensor] = None,
        pbc: Optional[Sequence[bool]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute displacement vectors, distances, and unit direction vectors [D]."""
        diff = coords.unsqueeze(0) - coords.unsqueeze(1)  # (N, N, 3)

        if cell is not None and pbc is not None and any(pbc):
            det = torch.linalg.det(cell)
            if torch.abs(det) < 1e-7:
                raise PeriodicBoundaryConditionError(
                    f"Unit cell matrix is singular (det={det.item():.6e})"
                )
            cell_inv = torch.linalg.inv(cell)
            s_ij = diff @ cell_inv
            pbc_mask = torch.tensor(
                [bool(b) for b in pbc], dtype=coords.dtype, device=coords.device
            )
            shift = torch.round(s_ij).detach() * pbc_mask
            s_pbc = s_ij - shift
            diff = s_pbc @ cell

        dists = torch.norm(diff, dim=-1)  # (N, N)
        # Unit direction vectors with smooth clamp to prevent 0/0 division on diagonal
        safe_dists = torch.clamp(dists, min=1e-8).unsqueeze(-1)
        r_hat = diff / safe_dists  # (N, N, 3)
        return diff, dists, r_hat

    def compute_rank2_tensor(
        self, s: torch.Tensor, v: torch.Tensor
    ) -> torch.Tensor:
        """Construct equivariant rank-2 symmetric traceless tensor A_i^(2e) [D].

        A_i^(2e) = sum_c w_c ( v_c (x) v_c - 1/3 ||v_c||^2 I_3x3 )

        Returns
        -------
        torch.Tensor
            Rank-2 symmetric traceless tensor of shape (N, 3, 3).
        """
        N, C, _ = v.shape
        w = self.tensor_weights(s)  # (N, C)
        # Outer product: v_{c, alpha} * v_{c, beta} -> (N, C, 3, 3)
        outer = torch.einsum("nca, ncb -> ncab", v, v)
        # Squared norms: ||v_c||^2 -> (N, C)
        v_norm2 = torch.sum(v**2, dim=-1)  # (N, C)

        eye = torch.eye(3, dtype=v.dtype, device=v.device).view(1, 1, 3, 3)
        traceless = outer - (1.0 / 3.0) * v_norm2.unsqueeze(-1).unsqueeze(
            -1
        ) * eye  # (N, C, 3, 3)

        # Contract over channels c with weights w_c: (N, 3, 3)
        A_2e = torch.einsum("nc, ncab -> nab", w, traceless)
        return A_2e

    def forward(
        self,
        atomic_numbers: Union[List[int], torch.Tensor],
        coordinates: torch.Tensor,
        cell: Optional[torch.Tensor] = None,
        pbc: Optional[Sequence[bool]] = None,
        compute_forces: bool = True,
    ) -> Dict[str, torch.Tensor]:
        """Forward pass evaluating invariant energy, equivariant forces, and tensor features [D]."""
        try:
            if not isinstance(atomic_numbers, torch.Tensor):
                z_tensor = torch.tensor(
                    atomic_numbers, dtype=torch.int64, device=coordinates.device
                )
            else:
                z_tensor = atomic_numbers.to(coordinates.device, torch.int64)

            num_atoms = coordinates.shape[0]
            if z_tensor.shape[0] != num_atoms:
                raise TorqModelBackboneError(
                    f"Mismatch between number of atomic numbers ({z_tensor.shape[0]}) and coordinates ({num_atoms})"
                )

            target_dtype = self.embedding.weight.dtype
            target_device = self.embedding.weight.device

            if coordinates.dtype != target_dtype or coordinates.device != target_device:
                coords = coordinates.to(dtype=target_dtype, device=target_device)
            else:
                coords = coordinates

            if compute_forces and not coords.requires_grad:
                coords = coords.clone().detach().requires_grad_(True)

            # Compute pairwise displacements, distances, and unit directions
            diff, dists, r_hat = self._compute_displacements(coords, cell, pbc)
            radial_feats = self.radial_basis(dists).to(
                dtype=target_dtype, device=target_device
            )
            r_hat = r_hat.to(dtype=target_dtype, device=target_device)
            dists = dists.to(dtype=target_dtype, device=target_device)

            mask_self = (
                ~torch.eye(num_atoms, dtype=torch.bool, device=target_device)
            ).to(target_dtype)

            # Initialize scalar and vector representations
            s = self.embedding(z_tensor)  # (N, C)
            v = torch.zeros(
                (num_atoms, self.num_channels, 3),
                dtype=target_dtype,
                device=target_device,
            )  # (N, C, 3)

            # Equivariant message passing
            for layer in self.layers:
                s, v = layer(s, v, radial_feats, r_hat, dists, mask_self)

            # Rank-2 tensor contraction A_i^(2e) [D]
            rank2_tensor = self.compute_rank2_tensor(s, v)

            # Atomic energies and total energy [D]
            atomic_energies = self.energy_readout(s).squeeze(-1)  # (N,)
            total_energy = atomic_energies.sum()

            forces = None
            if compute_forces:
                try:
                    grad = torch.autograd.grad(
                        outputs=total_energy,
                        inputs=coords,
                        create_graph=True,
                        retain_graph=True,
                    )[0]
                    if grad is None:
                        raise AutogradForceError(
                            "Autograd returned None for coordinate gradient."
                        )
                    raw_forces = -grad
                    # Momentum projection [D], [M]
                    net_force = raw_forces.mean(dim=0, keepdim=True)
                    forces = raw_forces - net_force
                except Exception as e:
                    if isinstance(e, AutogradForceError):
                        raise
                    raise AutogradForceError(
                        f"Failed coordinate autograd force evaluation: {str(e)}"
                    ) from e

            return {
                "energy": total_energy,
                "atomic_energies": atomic_energies,
                "forces": forces if forces is not None else torch.zeros_like(coords),
                "scalar_features": s,
                "vector_features": v,
                "rank2_tensor": rank2_tensor,
            }

        except Exception as e:
            if isinstance(e, (AutogradForceError, PeriodicBoundaryConditionError)):
                raise
            raise TorqModelBackboneError(
                f"CartesianEquivariantBackbone forward pass failed: {str(e)}"
            ) from e


# Aliases for architectural configurations [E]
MACEBackbone = CartesianEquivariantBackbone
NequIPWrapper = CartesianEquivariantBackbone
