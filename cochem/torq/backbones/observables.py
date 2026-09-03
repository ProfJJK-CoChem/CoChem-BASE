"""Differentiable Physical Observables (Dipole Moments & Polarizability) for CoChem-TORQ."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple, Union
import torch
import torch.nn as nn

from cochem.torq.constants import DEBYE_PER_EAA
from cochem.torq.errors import ObservableComputationError
from cochem.torq.models.schemas import ObservableOutput
from cochem.torq.utils.mendeleev_masses import get_monoisotopic_masses

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


class DifferentiableObservables(nn.Module):
    """Calculates differentiable physical observables: dipole moments and polarizability tensors [D]."""

    def __init__(
        self,
        num_channels: int = 64,
        l_max: int = 2,
    ) -> None:
        super().__init__()
        self.num_channels = num_channels
        self.l_max = l_max

        # Latent partial charge readout head: s_i -> q_i [D]
        self.charge_head = nn.Sequential(
            nn.Linear(num_channels, num_channels // 2),
            nn.SiLU(),
            nn.Linear(num_channels // 2, 1),
        )

        # Atomic polarization vector readout head: v_i -> p_i [D]
        # v_i has shape (N, C, 3), maps to (N, 3)
        self.polarization_weights = nn.Linear(num_channels, 1, bias=False)

        # Isotropic scalar polarizability trace density: s_i -> a_i^(0e) > 0 [D]
        self.trace_polarizability_head = nn.Sequential(
            nn.Linear(num_channels, num_channels // 2),
            nn.SiLU(),
            nn.Linear(num_channels // 2, 1),
            nn.Softplus(),
        )

    def compute_center_of_mass(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Union[List[int], torch.Tensor],
    ) -> torch.Tensor:
        """Evaluate center of mass dynamically using pure monoisotopic masses [M], [D]."""
        masses = get_monoisotopic_masses(
            atomic_numbers, device=coordinates.device, dtype=coordinates.dtype
        )  # (N,)
        total_mass = masses.sum()
        if total_mass <= 1e-12:
            return torch.zeros(3, dtype=coordinates.dtype, device=coordinates.device)
        com = torch.sum(coordinates * masses.unsqueeze(-1), dim=0) / total_mass
        return com

    def compute_dipole(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Union[List[int], torch.Tensor],
        scalar_features: torch.Tensor,
        vector_features: Optional[torch.Tensor] = None,
        total_charge: float = 0.0,
        electric_field: Optional[torch.Tensor] = None,
        polarizability_tensor: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute permanent and field-coupled electric dipole moment in Debye [M], [D].

        mu = [ sum_i q_tilde_i (r_i - r_COM) + sum_i p_i ] * 4.80320427 [Debye]
        """
        N = coordinates.shape[0]
        # Atomic partial charges
        raw_charges = self.charge_head(scalar_features).squeeze(-1)  # (N,)

        # Neutrality / total charge constraint [D]
        charge_correction = (raw_charges.sum() - total_charge) / float(N)
        net_charges = raw_charges - charge_correction  # (N,)

        # Center of mass coordinates
        r_com = self.compute_center_of_mass(coordinates, atomic_numbers)
        centered_coords = coordinates - r_com.unsqueeze(0)  # (N, 3)

        # Charge dipole in e*Angstrom
        dipole_charge = torch.sum(net_charges.unsqueeze(-1) * centered_coords, dim=0)

        # Atomic vector polarization in e*Angstrom [D]
        if vector_features is not None:
            # vector_features: (N, C, 3)
            # permute to (N, 3, C) and apply Linear(C, 1) -> (N, 3, 1) -> squeeze to (N, 3)
            v_perm = vector_features.permute(0, 2, 1)
            p_i = self.polarization_weights(v_perm).squeeze(-1)  # (N, 3)
            dipole_polarization = p_i.sum(dim=0)
        else:
            dipole_polarization = torch.zeros_like(dipole_charge)

        # Permanent dipole in Debye [M]
        mu_zero_eaa = dipole_charge + dipole_polarization
        mu_zero = mu_zero_eaa * DEBYE_PER_EAA

        # Field coupling: mu(E) = mu_0 + alpha @ E [D]
        if electric_field is not None and polarizability_tensor is not None:
            # polarizability_tensor in Angstrom^3, electric_field in eV/(e*Angstrom)
            # induced dipole in Debye
            induced = torch.matmul(polarizability_tensor, electric_field)
            total_dipole = mu_zero + induced
        else:
            total_dipole = mu_zero

        return total_dipole, net_charges

    def compute_polarizability(
        self,
        scalar_features: torch.Tensor,
        rank2_tensor: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, float, float]:
        """Compute rank-2 symmetric polarizability tensor alpha, isotropic mean, and anisotropy [D].

        alpha = sum_i [ a_i^(0e) I_3x3 + A_i^(2e) ]
        """
        N = scalar_features.shape[0]
        # Invariant positive isotropic trace density per atom
        a_0e = self.trace_polarizability_head(scalar_features).squeeze(-1)  # (N,)
        eye = torch.eye(3, dtype=scalar_features.dtype, device=scalar_features.device)
        iso_tensor = torch.sum(a_0e) * eye  # (3, 3)

        if rank2_tensor is not None:
            # sum_i A_i^(2e) of shape (3, 3)
            aniso_tensor = rank2_tensor.sum(dim=0)
        else:
            aniso_tensor = torch.zeros(
                (3, 3), dtype=scalar_features.dtype, device=scalar_features.device
            )

        alpha = iso_tensor + aniso_tensor  # (3, 3)

        # Enforce exact physical symmetry [M]
        sym_diff = torch.max(torch.abs(alpha - alpha.T)).item()
        if sym_diff > 1e-5:
            raise ObservableComputationError(
                f"Polarizability tensor broken symmetry: max|alpha - alpha^T| = {sym_diff:.6e} > 1e-5"
            )

        # Symmetrize explicitly to remove machine-precision skew
        alpha_sym = 0.5 * (alpha + alpha.T)

        # Mean isotropic polarizability [D]
        mean_alpha = float(torch.trace(alpha_sym).item() / 3.0)

        # Polarizability anisotropy gamma [D]
        xx = alpha_sym[0, 0]
        yy = alpha_sym[1, 1]
        zz = alpha_sym[2, 2]
        xy = alpha_sym[0, 1]
        yz = alpha_sym[1, 2]
        xz = alpha_sym[0, 2]

        gamma_sq = 0.5 * (
            (xx - yy) ** 2
            + (yy - zz) ** 2
            + (zz - xx) ** 2
            + 6.0 * (xy**2 + yz**2 + xz**2)
        )
        anisotropy = float(torch.sqrt(torch.clamp(gamma_sq, min=0.0)).item())

        return alpha_sym, mean_alpha, anisotropy

    def compute_field_response_polarizability(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Union[List[int], torch.Tensor],
        scalar_features: torch.Tensor,
        vector_features: Optional[torch.Tensor] = None,
        rank2_tensor: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Compute polarizability response tensor via automatic differentiation with respect to electric field [D].

        alpha_munu = d(mu_mu) / d(E_nu) |_{E=0}
        """
        electric_field = torch.zeros(
            3,
            dtype=coordinates.dtype,
            device=coordinates.device,
            requires_grad=True,
        )
        alpha_analytic, _, _ = self.compute_polarizability(
            scalar_features, rank2_tensor
        )
        dipole, _ = self.compute_dipole(
            coordinates=coordinates,
            atomic_numbers=atomic_numbers,
            scalar_features=scalar_features,
            vector_features=vector_features,
            electric_field=electric_field,
            polarizability_tensor=alpha_analytic,
        )

        response_cols = []
        for mu_idx in range(3):
            grad_nu = torch.autograd.grad(
                outputs=dipole[mu_idx],
                inputs=electric_field,
                retain_graph=True,
                create_graph=False,
            )[0]
            response_cols.append(grad_nu)

        alpha_response = torch.stack(response_cols, dim=0)  # (3, 3)
        return alpha_response

    def forward(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Union[List[int], torch.Tensor],
        scalar_features: torch.Tensor,
        vector_features: Optional[torch.Tensor] = None,
        rank2_tensor: Optional[torch.Tensor] = None,
        total_charge: float = 0.0,
        electric_field: Optional[torch.Tensor] = None,
    ) -> ObservableOutput:
        """Evaluate electronic observables and format into Pydantic v2 ObservableOutput schema [M]."""
        alpha_tensor, mean_alpha, anisotropy = self.compute_polarizability(
            scalar_features=scalar_features,
            rank2_tensor=rank2_tensor,
        )

        dipole, _ = self.compute_dipole(
            coordinates=coordinates,
            atomic_numbers=atomic_numbers,
            scalar_features=scalar_features,
            vector_features=vector_features,
            total_charge=total_charge,
            electric_field=electric_field,
            polarizability_tensor=alpha_tensor,
        )

        dipole_tuple = (
            float(dipole[0].item()),
            float(dipole[1].item()),
            float(dipole[2].item()),
        )
        alpha_list = alpha_tensor.detach().cpu().tolist()

        return ObservableOutput(
            dipole_vector=dipole_tuple,
            polarizability_tensor=alpha_list,
            mean_polarizability=mean_alpha,
            anisotropy=anisotropy,
        )
