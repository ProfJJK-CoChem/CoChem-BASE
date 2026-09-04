"""Delta-Learning (Delta-ML) Architecture for CoChem-TORQ.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, dynamic baselines, and exact unit harmonization.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import scipy.constants as const
import torch
from mendeleev import element

from Libraries.cochem_torq_inference_errors import BaselineExecutionError
from Libraries.cochem_torq_inference_schemas import DeltaMLConfig

# Conversion factors via scipy.constants
HARTREE_TO_EV: float = float(const.value("Hartree energy in eV"))  # ~27.211386245981 eV [D]
BOHR_TO_ANGSTROM: float = float(const.value("Bohr radius") * 1e10)  # ~0.529177210544 Angstrom [D]
HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM: float = HARTREE_TO_EV / BOHR_TO_ANGSTROM  # ~51.422067511 eV/Angstrom [D]
KCAL_PER_MOL_TO_EV: float = float(const.calorie * 1000.0 / (const.N_A * const.eV))  # ~0.0433641 eV [D]


class UnitHarmonizer:
    """Rigorous unit harmonization utilities between quantum chemistry and internal standard. [D]"""

    @staticmethod
    def convert_energy(
        value: Union[float, torch.Tensor],
        from_unit: str,
        to_unit: str = "eV",
    ) -> Union[float, torch.Tensor]:
        """Convert scalar energy between standard computational chemistry units. [D]"""
        if from_unit == to_unit:
            return value

        # Convert to eV first
        if from_unit == "eV":
            val_ev = value
        elif from_unit == "Hartree":
            val_ev = value * HARTREE_TO_EV
        elif from_unit == "kcal/mol":
            val_ev = value * KCAL_PER_MOL_TO_EV
        else:
            raise ValueError(f"Unsupported energy unit: {from_unit}")

        # Convert from eV to target unit
        if to_unit == "eV":
            return val_ev
        elif to_unit == "Hartree":
            return val_ev / HARTREE_TO_EV
        elif to_unit == "kcal/mol":
            return val_ev / KCAL_PER_MOL_TO_EV
        else:
            raise ValueError(f"Unsupported target energy unit: {to_unit}")

    @staticmethod
    def convert_forces(
        forces: torch.Tensor,
        from_length_unit: str = "Bohr",
        to_length_unit: str = "Angstrom",
        from_energy_unit: str = "Hartree",
        to_energy_unit: str = "eV",
    ) -> torch.Tensor:
        """Convert force tensors between atomic units and internal standard (eV/Angstrom). [D]"""
        # F = -dE / dR.
        # factor = (E_conversion_factor) / (R_conversion_factor)
        factor = 1.0
        if from_energy_unit == "Hartree" and to_energy_unit == "eV":
            factor *= HARTREE_TO_EV
        elif from_energy_unit == "eV" and to_energy_unit == "Hartree":
            factor /= HARTREE_TO_EV

        if from_length_unit == "Bohr" and to_length_unit == "Angstrom":
            factor /= BOHR_TO_ANGSTROM
        elif from_length_unit == "Angstrom" and to_length_unit == "Bohr":
            factor *= BOHR_TO_ANGSTROM

        return forces * factor


class BaselinePhysicsEngine:
    """Base contract for genuine physical baseline calculation engines. [M]"""

    def calculate(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
    ) -> Tuple[float, torch.Tensor]:
        """Compute baseline potential energy (eV) and forces (eV/Angstrom). [M]"""
        raise BaselineExecutionError("Base physics engine has no underlying calculator defined", method="NONE")



class GFN2xTBEngine(BaselinePhysicsEngine):
    """Adapter for physical GFN2-xTB semi-empirical calculations. [M]"""

    def __init__(self) -> None:
        self.xtb_available = False
        self._check_environment()

    def _check_environment(self) -> None:
        """Verify presence of xtb-python library or xtb executable in PATH. [M]"""
        try:
            import xtb  # noqa: F401
            self.xtb_available = True
            return
        except ImportError:
            pass

        if shutil.which("xtb") is not None:
            self.xtb_available = True
            return

        self.xtb_available = False

    def calculate(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
    ) -> Tuple[float, torch.Tensor]:
        if not self.xtb_available:
            raise BaselineExecutionError(
                "TORQ_BASELINE_UNAVAILABLE: GFN2-xTB executable or xtb-python library not found in runtime environment",
                method="GFN2-xTB",
                diagnostics={"atomic_count": len(atomic_numbers)},
            )
            
        import tempfile
        import os
        from ase import Atoms
        from ase.io import write
        
        atoms = Atoms(numbers=atomic_numbers, positions=coordinates.detach().cpu().numpy())
        with tempfile.TemporaryDirectory() as tmpdir:
            xyz_path = os.path.join(tmpdir, "mol.xyz")
            write(xyz_path, atoms, format="xyz")
            
            try:
                result = subprocess.run(["xtb", xyz_path, "--gfn", "2", "--grad"], cwd=tmpdir, capture_output=True, text=True, check=True)
                
                energy_hartree = 0.0
                for line in result.stdout.splitlines():
                    if "TOTAL ENERGY" in line:
                        parts = line.split()
                        energy_hartree = float(parts[-3]) if len(parts) >= 3 else 0.0
                
                grad_path = os.path.join(tmpdir, "gradient")
                forces_hartree_bohr = []
                with open(grad_path, "r") as f:
                    lines = f.readlines()
                    for line in lines[2:2+len(atomic_numbers)]:
                        parts = line.split()
                        forces_hartree_bohr.append([-float(parts[0]), -float(parts[1]), -float(parts[2])])
                        
                energy_ev = float(energy_hartree * HARTREE_TO_EV)
                forces_tensor = UnitHarmonizer.convert_forces(
                    torch.tensor(forces_hartree_bohr, dtype=coordinates.dtype, device=coordinates.device),
                    from_length_unit="Bohr", to_length_unit="Angstrom",
                    from_energy_unit="Hartree", to_energy_unit="eV"
                )
                return energy_ev, forces_tensor
                
            except Exception as e:
                raise BaselineExecutionError(
                    f"TORQ_BASELINE_EXEC_FAIL: GFN2-xTB execution failed during runtime dispatch: {e}",
                    method="GFN2-xTB",
                )


class PM6Engine(BaselinePhysicsEngine):
    """Adapter for semi-empirical PM6 Hamiltonian calculations. [M]"""

    def calculate(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
    ) -> Tuple[float, torch.Tensor]:
        import shutil
        import subprocess
        import tempfile
        import os
        from ase import Atoms
        from ase.io import write
        
        if shutil.which("mopac") is None:
            raise BaselineExecutionError(
                "TORQ_BASELINE_UNAVAILABLE: PM6 solver not found in runtime environment",
                method="PM6",
                diagnostics={"atomic_count": len(atomic_numbers)},
            )
            
        atoms = Atoms(numbers=atomic_numbers, positions=coordinates.detach().cpu().numpy())
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                xyz_path = os.path.join(tmpdir, "mol.xyz")
                write(xyz_path, atoms, format="xyz")
                
                mop_path = os.path.join(tmpdir, "mol.mop")
                with open(mop_path, "w") as f:
                    f.write("PM6 1SCF GRADIENTS\nTitle\n\n")
                    for i in range(len(atomic_numbers)):
                        pos = atoms.positions[i]
                        f.write(f"{atoms.get_chemical_symbols()[i]} {pos[0]} 1 {pos[1]} 1 {pos[2]} 1\n")
                
                subprocess.run(["mopac", mop_path], cwd=tmpdir, capture_output=True, text=True, check=True)
                
                out_path = os.path.join(tmpdir, "mol.out")
                energy_ev = 0.0
                forces_ev_angstrom = []
                reading_grad = False
                with open(out_path, "r") as f:
                    for line in f:
                        if "FINAL HEAT OF FORMATION" in line:
                            kcal = float(line.split()[5])
                            energy_ev = kcal * KCAL_PER_MOL_TO_EV
                        elif "FINAL POINT AND DERIVATIVES" in line:
                            reading_grad = True
                        elif reading_grad and len(line.split()) == 8:
                            parts = line.split()
                            try:
                                fx = -float(parts[5]) * KCAL_PER_MOL_TO_EV
                                fy = -float(parts[6]) * KCAL_PER_MOL_TO_EV
                                fz = -float(parts[7]) * KCAL_PER_MOL_TO_EV
                                forces_ev_angstrom.append([fx, fy, fz])
                            except ValueError:
                                pass
                
                if len(forces_ev_angstrom) != len(atomic_numbers):
                    raise ValueError("Failed to parse all forces from MOPAC output.")
                    
                return energy_ev, torch.tensor(forces_ev_angstrom, dtype=coordinates.dtype, device=coordinates.device)
                
            except Exception as e:
                raise BaselineExecutionError(
                    f"TORQ_BASELINE_EXEC_FAIL: PM6 execution failed: {e}",
                    method="PM6",
                )


class EMTBaselineEngine(BaselinePhysicsEngine):
    """Adapter for Effective Medium Theory (EMT) baseline calculations. [M]"""

    def calculate(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
    ) -> Tuple[float, torch.Tensor]:
        try:
            import ase  # noqa: F401
            from ase import Atoms
            from ase.calculators.emt import EMT
        except ImportError:
            raise BaselineExecutionError(
                "TORQ_BASELINE_UNAVAILABLE: ASE EMT library not found",
                method="EMT",
            )
        
        atoms = Atoms(numbers=atomic_numbers, positions=coordinates.detach().cpu().numpy())
        atoms.calc = EMT()
        
        try:
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces()
        except Exception as e:
            raise BaselineExecutionError(
                f"TORQ_BASELINE_EXEC_FAIL: EMT calculation failed: {e}",
                method="EMT",
            )
        
        return float(energy), torch.tensor(forces, dtype=coordinates.dtype, device=coordinates.device)


class LennardJonesBaselineEngine(BaselinePhysicsEngine):
    """Authentic physical Lennard-Jones non-bonded baseline engine with Lorentz-Berthelot mixing. [M]"""

    def __init__(self) -> None:
        # Standard Universal Force Field (UFF) / OPLS non-bonded physical parameters:
        # sigma in Angstroms, epsilon in eV
        self.default_params: Dict[int, Tuple[float, float]] = {
            1: (2.571, 0.001908),   # H
            6: (3.431, 0.004553),   # C
            7: (3.261, 0.003035),   # N
            8: (3.118, 0.002602),   # O
            9: (2.997, 0.002168),   # F
            16: (3.595, 0.011880),  # S
            17: (3.516, 0.009843),  # Cl
            18: (3.405, 0.010410),  # Ar
            36: (3.636, 0.014380),  # Kr
        }

    def _get_params(self, z: int) -> Tuple[float, float]:
        """Dynamically retrieve or estimate LJ parameters using Mendeleev covalent radii. [D]"""
        if z in self.default_params:
            return self.default_params[z]
        # Dynamically scale from mendeleev vdw or covalent radius
        el = element(int(z))
        r_cov_pm = el.covalent_radius or 100.0
        sigma = float(r_cov_pm * 1e-2 * 2.0)  # Convert pm to Angstroms and diameter
        epsilon = 0.005  # Standard default non-bonded depth in eV
        return (sigma, epsilon)

    def calculate(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
    ) -> Tuple[float, torch.Tensor]:
        """Evaluate exact physical Lennard-Jones potential and analytical autograd forces. [D]"""
        N = len(atomic_numbers)
        if N < 2:
            return 0.0, torch.zeros_like(coordinates)

        coords = coordinates.clone().detach().requires_grad_(True)
        device = coords.device
        dtype = coords.dtype

        # Build pairwise sigma_ij and epsilon_ij tensors
        sigmas = []
        epsilons = []
        for z in atomic_numbers:
            s, e = self._get_params(int(z))
            sigmas.append(s)
            epsilons.append(e)

        sig = torch.tensor(sigmas, dtype=dtype, device=device)
        eps = torch.tensor(epsilons, dtype=dtype, device=device)

        # Lorentz-Berthelot mixing: sigma_ij = (sigma_i + sigma_j)/2, eps_ij = sqrt(eps_i * eps_j)
        sig_ij = 0.5 * (sig.unsqueeze(1) + sig.unsqueeze(0))
        eps_ij = torch.sqrt(eps.unsqueeze(1) * eps.unsqueeze(0))

        # Coordinate differences
        diff = coords.unsqueeze(1) - coords.unsqueeze(0)  # [N, N, 3]
        dist = torch.norm(diff, dim=-1)  # [N, N]

        # Upper triangular mask (i < j)
        mask = torch.triu(torch.ones((N, N), dtype=torch.bool, device=device), diagonal=1)

        # Guard against zero distance
        clamped_dist = torch.where(mask, dist, torch.ones_like(dist))
        sr6 = (sig_ij / clamped_dist) ** 6
        sr12 = sr6 ** 2

        lj_pairs = 4.0 * eps_ij * (sr12 - sr6)
        energy = torch.sum(torch.where(mask, lj_pairs, torch.zeros_like(lj_pairs)))

        # Analytical conservative forces via exact autograd: F = -dE / dR
        grads = torch.autograd.grad(energy, coords, create_graph=False)[0]
        forces = -grads

        return float(energy.item()), forces.detach()


class DeltaMLEngine:
    """Delta-Learning engine managing difference mapping and target high-level reconstruction. [M]"""

    def __init__(
        self,
        config: DeltaMLConfig,
        baseline_engine: Optional[BaselinePhysicsEngine] = None,
    ) -> None:
        self.config = config
        if baseline_engine is not None:
            self.baseline_engine = baseline_engine
        else:
            if config.baseline_method == "GFN2-xTB":
                self.baseline_engine = GFN2xTBEngine()
            elif config.baseline_method == "PM6":
                self.baseline_engine = PM6Engine()
            elif config.baseline_method == "LennardJones":
                self.baseline_engine = LennardJonesBaselineEngine()
            elif config.baseline_method == "EMT":
                self.baseline_engine = EMTBaselineEngine()
            else:
                raise ValueError(f"Unknown baseline method: {config.baseline_method}")

    @staticmethod
    def compute_delta(
        qm_energy: float,
        qm_forces: torch.Tensor,
        baseline_energy: float,
        baseline_forces: torch.Tensor,
    ) -> Tuple[float, torch.Tensor]:
        r"""Compute physical delta difference targets for ML model training. [D]

        $$E_{\Delta}(\mathbf{R}) = E_{\text{QM}}(\mathbf{R}) - E_{\text{baseline}}(\mathbf{R})$$
        $$\mathbf{F}_{\Delta}(\mathbf{R}) = \mathbf{F}_{\text{QM}}(\mathbf{R}) - \mathbf{F}_{\text{baseline}}(\mathbf{R})$$
        """
        delta_e = float(qm_energy) - float(baseline_energy)
        delta_f = qm_forces - baseline_forces
        return delta_e, delta_f

    @staticmethod
    def reconstruct_target(
        baseline_energy: float,
        baseline_forces: torch.Tensor,
        predicted_delta_energy: float,
        predicted_delta_forces: torch.Tensor,
    ) -> Tuple[float, torch.Tensor]:
        r"""Reconstruct target high-level potential energy surface from predicted delta. [D]

        $$\hat{E}_{\text{target}}(\mathbf{R}) = E_{\text{baseline}}(\mathbf{R}) + \hat{E}_{\Delta}(\mathbf{R})$$
        $$\hat{\mathbf{F}}_{\text{target}}(\mathbf{R}) = \mathbf{F}_{\text{baseline}}(\mathbf{R}) + \hat{\mathbf{F}}_{\Delta}(\mathbf{R})$$
        """
        target_e = float(baseline_energy) + float(predicted_delta_energy)
        target_f = baseline_forces + predicted_delta_forces
        return target_e, target_f

    def forward(
        self,
        coordinates: torch.Tensor,
        atomic_numbers: Sequence[int],
        delta_predictor: Callable[[torch.Tensor, Sequence[int]], Tuple[float, torch.Tensor]],
    ) -> Tuple[float, torch.Tensor]:
        """Execute full forward inference pipeline: baseline + predicted delta. [M]"""
        e_base, f_base = self.baseline_engine.calculate(coordinates, atomic_numbers)
        e_delta, f_delta = delta_predictor(coordinates, atomic_numbers)
        return self.reconstruct_target(e_base, f_base, e_delta, f_delta)
