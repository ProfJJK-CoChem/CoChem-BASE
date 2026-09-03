"""SchNet Continuous-Filter Convolutional Backbone for CoChem-TORQ."""

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


class ShiftedSoftplus(nn.Module):
    """Smooth shifted softplus activation function: ln(0.5 * e^x + 0.5) [D]."""

    def __init__(self) -> None:
        super().__init__()
        self.shift = math.log(2.0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.nn.functional.softplus(x) - self.shift


class CFConv(nn.Module):
    """Continuous-Filter Convolution layer (CFConv) [D].

    v_i^{(l+1)} = sum_{j in N(i)} v_j^{(l)} (x) W^{(l)}(d_ij) * f_cut(d_ij)
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

        # Dense radial filter generator network
        self.filter_network = nn.Sequential(
            nn.Linear(num_radial_basis, num_channels),
            ShiftedSoftplus(),
            nn.Linear(num_channels, num_channels),
        )

    def forward(
        self,
        v: torch.Tensor,
        radial_features: torch.Tensor,
        distances: torch.Tensor,
        mask_self: torch.Tensor,
    ) -> torch.Tensor:
        """Apply continuous-filter convolution over all atom pairs."""
        # radial_features: (N, N, num_radial_basis)
        # distances: (N, N)
        # mask_self: (N, N) boolean mask where i != j
        w_ij = self.filter_network(radial_features)  # (N, N, num_channels)
        cutoff = polynomial_cutoff(distances, self.r_max).unsqueeze(
            -1
        )  # (N, N, 1)

        # w_ij masked: eliminate self-interactions and out-of-cutoff pairs
        pair_weights = w_ij * cutoff * mask_self.unsqueeze(-1)

        # Message from atom j to atom i: v_j has shape (N, num_channels)
        # We compute sum_j v_j * pair_weights_{ij} -> (N, num_channels)
        messages = torch.einsum("jc, ijc -> ic", v, pair_weights)
        return messages


class SchNetInteraction(nn.Module):
    """SchNet interaction block combining dense projections and CFConv [D]."""

    def __init__(
        self,
        num_channels: int,
        num_radial_basis: int,
        r_max: float,
    ) -> None:
        super().__init__()
        self.in_proj = nn.Linear(num_channels, num_channels)
        self.cfconv = CFConv(num_channels, num_radial_basis, r_max)
        self.out_proj = nn.Sequential(
            nn.Linear(num_channels, num_channels),
            ShiftedSoftplus(),
            nn.Linear(num_channels, num_channels),
        )

    def forward(
        self,
        v: torch.Tensor,
        radial_features: torch.Tensor,
        distances: torch.Tensor,
        mask_self: torch.Tensor,
    ) -> torch.Tensor:
        v_in = self.in_proj(v)
        v_conv = self.cfconv(v_in, radial_features, distances, mask_self)
        v_out = self.out_proj(v_conv)
        return v + v_out


class SchNetBackbone(nn.Module):
    """Pure-PyTorch SchNet Invariant Continuous-Filter Convolutional Backbone [D]."""

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

        self.embedding = nn.Embedding(max_z + 1, self.num_channels)
        self.radial_basis = RadialBasis(
            num_radial_basis=self.num_radial_basis,
            r_max=self.r_max,
            basis_type="gaussian",
        )

        self.interactions = nn.ModuleList(
            [
                SchNetInteraction(
                    num_channels=self.num_channels,
                    num_radial_basis=self.num_radial_basis,
                    r_max=self.r_max,
                )
                for _ in range(self.num_layers)
            ]
        )

        self.readout = nn.Sequential(
            nn.Linear(self.num_channels, self.num_channels // 2),
            ShiftedSoftplus(),
            nn.Linear(self.num_channels // 2, 1),
        )

    def _compute_displacements(
        self,
        coords: torch.Tensor,
        cell: Optional[torch.Tensor] = None,
        pbc: Optional[Sequence[bool]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute pairwise displacements and Euclidean distances under optional PBC [D]."""
        num_atoms = coords.shape[0]
        # Pairwise differences: r_ij = r_j - r_i (shape: N, N, 3)
        diff = coords.unsqueeze(0) - coords.unsqueeze(1)

        if cell is not None and pbc is not None and any(pbc):
            det = torch.linalg.det(cell)
            if torch.abs(det) < 1e-7:
                raise PeriodicBoundaryConditionError(
                    f"Unit cell matrix is singular (det={det.item():.6e})"
                )
            cell_inv = torch.linalg.inv(cell)
            # Fractional coordinates displacement: s_ij = diff @ cell_inv
            s_ij = diff @ cell_inv
            pbc_mask = torch.tensor(
                [bool(b) for b in pbc], dtype=coords.dtype, device=coords.device
            )
            # Round fractional shift for periodic directions
            shift = torch.round(s_ij).detach() * pbc_mask
            s_pbc = s_ij - shift
            diff = s_pbc @ cell

        # Numerically stable Euclidean distance
        dists = torch.norm(diff, dim=-1)
        return diff, dists

    def forward(
        self,
        atomic_numbers: Union[List[int], torch.Tensor],
        coordinates: torch.Tensor,
        cell: Optional[torch.Tensor] = None,
        pbc: Optional[Sequence[bool]] = None,
        compute_forces: bool = True,
    ) -> Dict[str, torch.Tensor]:
        """Evaluate scalar potential energy and conservative autograd forces [D]."""
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

            # Ensure coordinates require gradient if forces are needed and match model dtype
            if coordinates.dtype != target_dtype or coordinates.device != target_device:
                coords = coordinates.to(dtype=target_dtype, device=target_device)
            else:
                coords = coordinates

            if compute_forces and not coords.requires_grad:
                coords = coords.clone().detach().requires_grad_(True)

            # Compute pairwise displacements and distances
            diff, dists = self._compute_displacements(coords, cell, pbc)

            # Radial basis expansion
            radial_feats = self.radial_basis(dists).to(
                dtype=target_dtype, device=target_device
            )

            # Mask out self-interactions
            mask_self = (
                ~torch.eye(num_atoms, dtype=torch.bool, device=target_device)
            ).to(target_dtype)

            # Node feature embedding
            v = self.embedding(z_tensor)

            # Message passing layers
            for layer in self.interactions:
                v = layer(v, radial_feats, dists, mask_self)

            # Atomic energies and total potential energy
            atomic_energies = self.readout(v).squeeze(-1)  # (N,)
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
                    # Conservative force F_i = -dE/dr_i [D]
                    raw_forces = -grad

                    # Center-of-mass momentum projection [D]
                    # Guarantee net force <= 10^-6 eV/Angstrom [M]
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
                "scalar_features": v,
            }

        except Exception as e:
            if isinstance(e, (AutogradForceError, PeriodicBoundaryConditionError)):
                raise
            raise TorqModelBackboneError(f"SchNet forward pass failed: {str(e)}") from e


class SchNetFallbackRouter:
    """Seamless router providing fallback to invariant SchNet backbone [D]."""

    def __init__(self, config: Optional[TorqModelConfig] = None) -> None:
        self.config = config or TorqModelConfig(model_name="schnet")
        self.backbone = SchNetBackbone(config=self.config)

    def forward(
        self,
        atomic_numbers: Union[List[int], torch.Tensor],
        coordinates: torch.Tensor,
        cell: Optional[torch.Tensor] = None,
        pbc: Optional[Sequence[bool]] = None,
        compute_forces: bool = True,
    ) -> Dict[str, torch.Tensor]:
        return self.backbone(
            atomic_numbers=atomic_numbers,
            coordinates=coordinates,
            cell=cell,
            pbc=pbc,
            compute_forces=compute_forces,
        )
