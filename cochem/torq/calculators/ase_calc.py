"""ASE Calculator Interface with Strain Autograd Virial Stress for CoChem-TORQ."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
import numpy as np
import torch
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes

from cochem.torq.backbones.equivariant_tensor import CartesianEquivariantBackbone
from cochem.torq.backbones.observables import DifferentiableObservables
from cochem.torq.errors import (
    PeriodicBoundaryConditionError,
    TorqDeviceAllocationError,
    TorqModelBackboneError,
)
from cochem.torq.models.schemas import TorqModelConfig

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


class TORQCalculator(Calculator):
    """ASE Calculator providing energy, autograd forces, strain virial stress, and observables [M].

    Virial stress is evaluated strictly via spatial strain autograd:
        sigma_{alpha, beta} = 1/V * dE / deps_{alpha, beta} |_{eps=0}  [D]
    returned as standard ASE 6-element Voigt notation in eV/Angstrom^3 [M].
    No kinetic energy or velocity terms are included [M].
    """

    implemented_properties = [
        "energy",
        "forces",
        "stress",
        "dipole",
        "polarizability",
    ]

    def __init__(
        self,
        model: Optional[torch.nn.Module] = None,
        observables: Optional[DifferentiableObservables] = None,
        config: Optional[TorqModelConfig] = None,
        device: Union[torch.device, str] = "cpu",
        dtype: torch.dtype = torch.float64,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        try:
            self.device = torch.device(device)
        except Exception as e:
            raise TorqDeviceAllocationError(
                f"Failed allocating device '{device}': {str(e)}"
            ) from e

        self.dtype = dtype
        self.config = config or TorqModelConfig()

        if model is None:
            self.model = CartesianEquivariantBackbone(config=self.config)
        else:
            self.model = model

        self.model.to(device=self.device, dtype=self.dtype)

        if observables is None:
            self.observables = DifferentiableObservables(
                num_channels=self.config.num_channels,
                l_max=self.config.l_max,
            )
        else:
            self.observables = observables

        self.observables.to(device=self.device, dtype=self.dtype)

    def calculate(
        self,
        atoms: Optional[Atoms] = None,
        properties: Optional[List[str]] = None,
        system_changes: Any = all_changes,
    ) -> None:
        """Execute potential evaluation and populate results dictionary [M]."""
        if properties is None:
            properties = ["energy", "forces"]

        Calculator.calculate(self, atoms, properties, system_changes)

        if atoms is None:
            raise TorqModelBackboneError("No ASE Atoms object provided to calculate.")

        z = atoms.get_atomic_numbers().tolist()
        positions = atoms.get_positions()
        pbc = tuple(bool(b) for b in atoms.get_pbc())
        has_pbc = any(pbc)

        # Base atomic coordinates tensor
        r_orig = torch.tensor(
            positions,
            dtype=self.dtype,
            device=self.device,
            requires_grad=True,
        )

        # Optional unit cell
        c_orig: Optional[torch.Tensor] = None
        if has_pbc:
            cell_np = np.array(atoms.get_cell())
            if np.abs(np.linalg.det(cell_np)) < 1e-7:
                raise PeriodicBoundaryConditionError(
                    "ASE Atoms unit cell determinant is singular (< 1e-7)."
                )
            c_orig = torch.tensor(
                cell_np,
                dtype=self.dtype,
                device=self.device,
            )

        # Handle virial stress via virtual cell and coordinate strain autograd [D]
        calc_stress = "stress" in properties and has_pbc

        if calc_stress:
            # Virtual strain tensor eps initialized to zero [D]
            eps = torch.zeros(
                (3, 3),
                dtype=self.dtype,
                device=self.device,
                requires_grad=True,
            )
            # Affine deformation: R' = R(I + eps), C' = C(I + eps) [D]
            r_deformed = r_orig + torch.matmul(r_orig, eps)
            c_deformed = c_orig + torch.matmul(c_orig, eps)

            model_out = self.model(
                atomic_numbers=z,
                coordinates=r_deformed,
                cell=c_deformed,
                pbc=pbc,
                compute_forces=False,
            )
            energy = model_out["energy"]

            # Autograd with respect to unperturbed coordinates and virtual strain [D]
            grads = torch.autograd.grad(
                outputs=energy,
                inputs=[r_orig, eps],
                create_graph=False,
                retain_graph=False,
            )
            raw_forces = -grads[0]
            # Center of mass momentum projection [D]
            net_f = raw_forces.mean(dim=0, keepdim=True)
            forces = raw_forces - net_f

            # Virial stress: sigma = 1/V * dE/deps |_{eps=0} [D]
            # No kinetic velocity terms are included! [M]
            volume = float(atoms.get_volume())
            if volume <= 1e-8:
                raise PeriodicBoundaryConditionError(
                    f"Unit cell volume non-positive: {volume}"
                )
            dE_deps = grads[1]
            sigma_tensor = 0.5 * (dE_deps + dE_deps.T) / volume  # (3, 3) in eV/Angstrom^3

            # Convert to standard ASE 6-element Voigt notation [M]:
            # [sigma_xx, sigma_yy, sigma_zz, sigma_yz, sigma_xz, sigma_xy]
            voigt_stress = np.array(
                [
                    sigma_tensor[0, 0].item(),
                    sigma_tensor[1, 1].item(),
                    sigma_tensor[2, 2].item(),
                    sigma_tensor[1, 2].item(),
                    sigma_tensor[0, 2].item(),
                    sigma_tensor[0, 1].item(),
                ],
                dtype=np.float64,
            )
            self.results["stress"] = voigt_stress
        else:
            model_out = self.model(
                atomic_numbers=z,
                coordinates=r_orig,
                cell=c_orig,
                pbc=pbc,
                compute_forces=False,
            )
            energy = model_out["energy"]

            grad = torch.autograd.grad(
                outputs=energy,
                inputs=r_orig,
                create_graph=False,
                retain_graph=False,
            )[0]
            raw_forces = -grad
            net_f = raw_forces.mean(dim=0, keepdim=True)
            forces = raw_forces - net_f

        self.results["energy"] = float(energy.item())
        self.results["forces"] = forces.detach().cpu().numpy()

        # Differentiable electronic observables if requested
        if "dipole" in properties or "polarizability" in properties:
            scalar_feats = model_out.get("scalar_features")
            vector_feats = model_out.get("vector_features")
            rank2_feats = model_out.get("rank2_tensor")

            obs_output = self.observables(
                coordinates=r_orig,
                atomic_numbers=z,
                scalar_features=scalar_feats,
                vector_features=vector_feats,
                rank2_tensor=rank2_feats,
            )
            self.results["dipole"] = np.array(
                obs_output.dipole_vector, dtype=np.float64
            )
            self.results["polarizability"] = np.array(
                obs_output.polarizability_tensor, dtype=np.float64
            )
            self.results["mean_polarizability"] = obs_output.mean_polarizability
            self.results["anisotropy"] = obs_output.anisotropy
