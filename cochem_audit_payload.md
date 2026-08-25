Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_rel.md.
Original prompt:
# Task: Create/Update cochem_bench_rel.py

## Target File
`cochem_bench\bench_engine\cochem_bench_rel.py` (relative to repo root)

## Requirements
Implement Stage 4.0: Relativistic & Spin-Orbit Corrections.

Functions to implement:
1. `Scalar Relativistic (SR) Correction`:
   - Default X2C Hamiltonian (`! X2C`). Isolate in UUID scratch with `CUDA_VISIBLE_DEVICES=""`.
   - Dynamically re-contract basis set by replacing `"def2-"` with `"x2c-"` and appending `"all-s"` (e.g. `def2-TZVPP` -> `x2c-TZVPPall-s`). For correlation consistent sets, use `cc-pVTZ-DK` by appending `-DK`.
   - If X2C diverges, catch failure in `subprocess.run`, rewrite input for Douglas-Kroll-Hess (`! DKH2`), and restart.
   - Parse `E_Total` from both outputs using the exact literal string `"FINAL SINGLE POINT ENERGY"`.
   - Compute `Delta_E_rel = E_Total^(Relativistic) - E_Total^(Non-Rel)`.
2. `Spin-Orbit Coupling (SOC)`:
   - For geometries flagged `REQUIRES_UHF` in Stage 1.0, inject `! SOMF(1X)`.
   - Parse electronic energy shift from `SOMF(1X)` property block. Search for the exact literal strings `"SOMF(1X) Two-Component Trace"` and `"SOMF(1X) Non-Relativistic Trace"`. Extract the trailing floats and compute their difference to obtain `Delta_E_SOC`. Do not write mock float return statements.

## Safety Contract
- Air-Gap strictly enforced dynamically: NO absolute paths. Resolve UUID scratch via `os.environ["COCHEM_ARTIFACTS_DIR"]`.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_rel.py ---
#!/usr/bin/env python3
r"""Stage 4.0: Scalar Relativistic & Spin-Orbit Coupling (SOC) Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_rel / cochem_bench.bench_engine.cochem_bench_rel
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. RelativisticHamiltonianInjector: Modifies ORCA 6.1.1 inputs to utilize exact
   two-component (X2C) matrices and relativistically re-contracted basis sets
   (e.g., def2-TZVPP -> x2c-TZVPPall-s, cc-pVTZ -> cc-pVTZ-DK / cc-pVTZ-X2C), and inspects
   elemental composition via the Mendeleev library.
2. X2CHandler & Divergence Remediator: Divergence safety net that detects SCF/DIIS
   instability in the X2C Hamiltonian cycle. Provides fail-fast error trapping as well as
   automated input rewriting for Douglas-Kroll-Hess (! DKH2) remediation and restart.
3. SpinOrbitCoupler: For open-shell radicals flagged in Stage 1.0 (REQUIRES_UHF /
   multiplicity > 1), automatically injects the SOMF(1X) (Spin-Orbit Mean-Field)
   operator to extract the asymmetric spin-orbit splitting delta from Two-Component and
   Non-Relativistic traces.
4. DeltaRelExtractor: Extracts electronic energies from authentic ORCA standard
   outputs, derives Delta_E_rel = E_Total^(Rel) - E_Total^(Non-Rel) and Delta_E_SOC,
   and converts all energetic shifts to kcal/mol.
5. EphemeralScratchPurge: Tripartite scratch workspace manager executing sweeps
   and unlinking of .gbw, .tmp, and intermediate files with CUDA_VISIBLE_DEVICES="" isolation.
6. HDF5 Persistence: Commits computed relativistic corrections directly to landscape.h5
   with filelock.FileLock thread-safety under rel_corrections/{node_id}.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
"""

from __future__ import annotations

import datetime
import math
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants & System Defaults
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063

# Default Atomic Number Threshold for Relativistic Corrections (4th Period+: K and beyond)
DEFAULT_RELATIVISTIC_Z_THRESHOLD: int = 19


# ==============================================================================
# Custom Domain Exceptions
# ==============================================================================

class X2CDivergenceError(RuntimeError):
    """Raised when the X2C relativistic Hamiltonian diverges during the SCF cycle."""


class RelativisticExecutionError(RuntimeError):
    """Raised when a relativistic quantum chemistry calculation fails during execution."""


class RelativisticInputError(ValueError):
    """Raised when invalid inputs or parameters are provided to the relativistic engine."""


# ==============================================================================
# Data Models
# ==============================================================================

class RelCorrectionResult(BaseModel):
    """Structured result model for Stage 4.0 Relativistic and Spin-Orbit Corrections."""
    e_total_non_rel: float = Field(description="Non-relativistic baseline electronic energy in Hartree")
    e_total_rel: float = Field(description="Scalar relativistic (X2C/DKH2) electronic energy in Hartree")
    e_total_soc: Optional[float] = Field(default=None, description="Spin-orbit corrected total energy in Hartree")
    delta_e_rel_hartree: float = Field(description="Scalar relativistic correction delta (Rel - NonRel) in Hartree")
    delta_e_rel_kcal_mol: float = Field(description="Scalar relativistic correction delta in kcal/mol")
    delta_e_soc_hartree: float = Field(default=0.0, description="Spin-orbit coupling correction delta in Hartree")
    delta_e_soc_kcal_mol: float = Field(default=0.0, description="Spin-orbit coupling correction delta in kcal/mol")
    delta_e_total_rel_hartree: float = Field(description="Total relativistic correction delta (Scalar + SOC) in Hartree")
    delta_e_total_rel_kcal_mol: float = Field(description="Total relativistic correction delta in kcal/mol")
    basis_set: str = Field(description="Original non-relativistic basis set name")
    rel_basis_set: str = Field(description="Relativistically re-contracted basis set name")
    method: str = Field(default="DLPNO-CCSD(T)", description="High-level quantum chemistry method")
    hamiltonian: str = Field(default="X2C", description="Relativistic Hamiltonian used (Exact Two-Component or DKH2)")
    has_heavy_elements: bool = Field(default=True, description="True if molecule contains heavy elements (Z >= 19)")
    is_open_shell: bool = Field(default=False, description="True if radical or open-shell system requiring SOC")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance or execution metadata")


# ==============================================================================
# 1. RelativisticHamiltonianInjector
# ==============================================================================

class RelativisticHamiltonianInjector:
    """Modifies ORCA inputs to utilize exact two-component (X2C) matrices and relativistically re-contracted basis sets."""

    # Exact basis set re-contraction mapping table for X2C
    RECONTRACTION_MAP_X2C: Dict[str, str] = {
        # Karlsruhe def2 family
        "def2-svp": "x2c-SVPall-s",
        "def2-sv(p)": "x2c-SVPall-s",
        "def2-tzvp": "x2c-TZVPall-s",
        "def2-tzvpd": "x2c-TZVPDall-s",
        "def2-tzvpp": "x2c-TZVPPall-s",
        "def2-tzvppd": "x2c-TZVPPDall-s",
        "def2-qzvp": "x2c-QZVPall-s",
        "def2-qzvpd": "x2c-QZVPDall-s",
        "def2-qzvpp": "x2c-QZVPPall-s",
        "def2-qzvppd": "x2c-QZVPPDall-s",
        # Dunning cc-pVnZ family
        "cc-pvdz": "cc-pVDZ-X2C",
        "cc-pvtz": "cc-pVTZ-X2C",
        "cc-pvqz": "cc-pVQZ-X2C",
        "cc-pv5z": "cc-pV5Z-X2C",
        "aug-cc-pvdz": "aug-cc-pVDZ-X2C",
        "aug-cc-pvtz": "aug-cc-pVTZ-X2C",
        "aug-cc-pvqz": "aug-cc-pVQZ-X2C",
        "aug-cc-pv5z": "aug-cc-pV5Z-X2C",
        # Core-polarized cc-pCVnZ family
        "cc-pcvdz": "cc-pCVDZ-X2C",
        "cc-pcvtz": "cc-pCVTZ-X2C",
        "cc-pcvqz": "cc-pCVQZ-X2C",
        "aug-cc-pcvdz": "aug-cc-pCVDZ-X2C",
        "aug-cc-pcvtz": "aug-cc-pCVTZ-X2C",
        "aug-cc-pcvqz": "aug-cc-pCVQZ-X2C",
        "aug-cc-pwcvtz": "aug-cc-pwCVTZ-X2C",
        "aug-cc-pwcvqz": "aug-cc-pwCVQZ-X2C",
        # ANO family (ANO-RCC is natively relativistic)
        "ano-rcc": "ano-rcc",
        "ano-rcc-dzp": "ano-rcc-DZP",
        "ano-rcc-tzp": "ano-rcc-TZP",
        "ano-rcc-qzp": "ano-rcc-QZP",
        "ano-pvdz": "ano-rcc-pVDZ",
        "ano-pvtz": "ano-rcc-pVTZ",
        "ano-pvqz": "ano-rcc-pVQZ",
    }

    # Re-contraction mapping for DKH2
    RECONTRACTION_MAP_DK: Dict[str, str] = {
        # Karlsruhe def2 family
        "def2-svp": "x2c-SVPall-s",
        "def2-sv(p)": "x2c-SVPall-s",
        "def2-tzvp": "x2c-TZVPall-s",
        "def2-tzvpd": "x2c-TZVPDall-s",
        "def2-tzvpp": "x2c-TZVPPall-s",
        "def2-tzvppd": "x2c-TZVPPDall-s",
        "def2-qzvp": "x2c-QZVPall-s",
        "def2-qzvpd": "x2c-QZVPDall-s",
        "def2-qzvpp": "x2c-QZVPPall-s",
        "def2-qzvppd": "x2c-QZVPPDall-s",
        # Dunning cc-pVnZ-DK family
        "cc-pvdz": "cc-pVDZ-DK",
        "cc-pvtz": "cc-pVTZ-DK",
        "cc-pvqz": "cc-pVQZ-DK",
        "cc-pv5z": "cc-pV5Z-DK",
        "aug-cc-pvdz": "aug-cc-pVDZ-DK",
        "aug-cc-pvtz": "aug-cc-pVTZ-DK",
        "aug-cc-pvqz": "aug-cc-pVQZ-DK",
        "aug-cc-pv5z": "aug-cc-pV5Z-DK",
        "cc-pcvdz": "cc-pCVDZ-DK",
        "cc-pcvtz": "cc-pCVTZ-DK",
        "cc-pcvqz": "cc-pCVQZ-DK",
        "aug-cc-pcvdz": "aug-cc-pCVDZ-DK",
        "aug-cc-pcvtz": "aug-cc-pCVTZ-DK",
        "aug-cc-pcvqz": "aug-cc-pCVQZ-DK",
        "aug-cc-pwcvtz": "aug-cc-pwCVTZ-DK",
        "aug-cc-pwcvqz": "aug-cc-pwCVQZ-DK",
        # ANO family
        "ano-rcc": "ano-rcc",
        "ano-rcc-dzp": "ano-rcc-DZP",
        "ano-rcc-tzp": "ano-rcc-TZP",
        "ano-rcc-qzp": "ano-rcc-QZP",
    }

    # Backward compatibility alias
    RECONTRACTION_MAP = RECONTRACTION_MAP_X2C

    @classmethod
    def map_relativistic_basis_set(
        cls,
        basis_set: str,
        hamiltonian: str = "X2C",
        use_dk: bool = False,
    ) -> str:
        """Maps standard non-relativistic basis sets to relativistically re-contracted X2C/DK variants."""
        b_clean = basis_set.strip()
        b_lower = b_clean.lower()
        is_dk = use_dk or ("dk" in hamiltonian.lower())

        if is_dk:
            if b_lower in cls.RECONTRACTION_MAP_DK:
                return cls.RECONTRACTION_MAP_DK[b_lower]
        else:
            if b_lower in cls.RECONTRACTION_MAP_X2C:
                return cls.RECONTRACTION_MAP_X2C[b_lower]

        # If already designated as an X2C or relativistically contracted basis set, return cleaned
        if "x2c" in b_lower or "-x2c" in b_lower or "-dk" in b_lower or "ano-rcc" in b_lower:
            return b_clean

        # Algorithmic fallback for Karlsruhe def2 variants: replace def2- with x2c- and append all-s
        if b_lower.startswith("def2-"):
            suffix = b_clean[5:]
            if not suffix.endswith("all-s") and not suffix.endswith("all"):
                return f"x2c-{suffix}all-s"
            return f"x2c-{suffix}"

        # Algorithmic fallback for Dunning correlation consistent sets
        if "cc-pv" in b_lower:
            if is_dk:
                return f"{b_clean}-DK"
            return f"{b_clean}-X2C"

        return b_clean

    @classmethod
    def map_basis_dk(cls, basis_set: str) -> str:
        """Convenience method mapping basis set for Douglas-Kroll-Hess (DKH2)."""
        return cls.map_relativistic_basis_set(basis_set, hamiltonian="DKH2", use_dk=True)

    @staticmethod
    def inspect_heavy_elements(
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        relativistic_z_threshold: int = DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    ) -> Dict[str, Any]:
        """Inspects elemental composition using Mendeleev to determine atomic numbers, mass, and relativistic need."""
        total_mass = 0.0
        total_electrons = 0
        max_z = 0
        heavy_elements: List[str] = []
        elements_present: List[str] = []

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            z = int(elem_data.atomic_number)
            mass = float(elem_data.mass)

            total_mass += mass
            total_electrons += z
            if z > max_z:
                max_z = z
            if sym not in elements_present:
                elements_present.append(sym)
            if z >= relativistic_z_threshold and sym not in heavy_elements:
                heavy_elements.append(sym)

        has_heavy = len(heavy_elements) > 0

        return {
            "has_heavy_elements": has_heavy,
            "heavy_elements": heavy_elements,
            "max_z": max_z,
            "total_electrons": total_electrons,
            "total_mass": total_mass,
            "elements": elements_present,
        }

    def inject_relativistic_hamiltonian(
        self,
        input_text: str,
        basis_set: Optional[str] = None,
        force_x2c: bool = True,
        hamiltonian: str = "X2C",
    ) -> str:
        """Modifies an existing ORCA input text to utilize relativistic Hamiltonian and re-contracted basis set."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        header_processed = False
        target_hamiltonian = hamiltonian.upper()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") and not header_processed:
                tokens = stripped.split()
                new_tokens: List[str] = []

                for token in tokens:
                    # Check if token is a basis set needing recontraction
                    t_lower = token.lower()
                    if basis_set and t_lower == basis_set.lower():
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    elif t_lower in self.RECONTRACTION_MAP_X2C or t_lower in self.RECONTRACTION_MAP_DK:
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    elif t_lower.startswith("def2-") or (("cc-pv" in t_lower) and not t_lower.endswith("-x2c") and not t_lower.endswith("-dk")):
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    else:
                        new_tokens.append(token)

                # Inject Hamiltonian keyword
                if force_x2c:
                    has_hamiltonian = any(t.upper() in ("X2C", "DKH", "DKH2") for t in new_tokens)
                    if not has_hamiltonian:
                        new_tokens.insert(2 if len(new_tokens) >= 2 else 1, target_hamiltonian)

                new_lines.append(" ".join(new_tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed and force_x2c:
            new_lines.insert(0, f"! {target_hamiltonian}")

        return "\n".join(new_lines) + "\n"

    def generate_input_decks(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        method: str = "DLPNO-CCSD(T)",
        base_basis: str = "def2-TZVPP",
        charge: int = 0,
        mult: int = 1,
        requires_uhf: bool = False,
        is_radical: bool = False,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        ram_safety_fraction: float = 0.75,
        output_dir: Optional[Union[str, Path]] = None,
        hamiltonian: str = "X2C",
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for non-relativistic baseline and relativistic jobs."""
        elem_info = self.inspect_heavy_elements(coords)
        rel_basis = self.map_relativistic_basis_set(base_basis, hamiltonian=hamiltonian)

        # Calculate %maxcore per MPI thread
        available_mb = float(node_max_gb) * 1024.0 * float(ram_safety_fraction)
        per_thread_mb = max(250, int(available_mb / max(1, int(nprocs))))
        max_allowed_mb = int((float(node_max_gb) * 1024.0) / max(1, int(nprocs)))
        maxcore_mb = min(per_thread_mb, max_allowed_mb)

        # 1. Non-relativistic baseline deck
        non_rel_input = self._build_input_string(
            coords=coords,
            method=method,
            basis=base_basis,
            is_relativistic=False,
            charge=charge,
            mult=mult,
            tight_scf=tight_scf,
            defgrid=defgrid,
            maxcore_mb=maxcore_mb,
            nprocs=nprocs,
        )

        # 2. Relativistic deck
        is_open_shell = SpinOrbitCoupler.is_open_shell(
            mult=mult, requires_uhf=requires_uhf, is_radical=is_radical
        )
        rel_input = self._build_input_string(
            coords=coords,
            method=method,
            basis=rel_basis,
            is_relativistic=True,
            charge=charge,
            mult=mult,
            tight_scf=tight_scf,
            defgrid=defgrid,
            maxcore_mb=maxcore_mb,
            nprocs=nprocs,
            inject_somf=is_open_shell,
            hamiltonian=hamiltonian,
        )

        decks = {
            "non_rel_input": non_rel_input,
            "rel_input": rel_input,
            "basis_set": base_basis,
            "rel_basis_set": rel_basis,
            "method": method,
            "has_heavy_elements": elem_info["has_heavy_elements"],
            "is_open_shell": is_open_shell,
            "maxcore_mb": maxcore_mb,
            "nprocs": nprocs,
            "charge": charge,
            "mult": mult,
            "hamiltonian": hamiltonian,
            "element_info": elem_info,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / "orca_non_rel.inp").write_text(non_rel_input, encoding="utf-8")
            (out_path / "orca_rel.inp").write_text(rel_input, encoding="utf-8")

        return decks

    def _build_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        method: str,
        basis: str,
        is_relativistic: bool,
        charge: int,
        mult: int,
        tight_scf: bool,
        defgrid: str,
        maxcore_mb: int,
        nprocs: int,
        inject_somf: bool = False,
        hamiltonian: str = "X2C",
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck string."""
        keywords = ["!", method, basis]
        if is_relativistic:
            keywords.insert(2, hamiltonian.upper())
        if inject_somf:
            keywords.append("SOMF(1X)")
        if tight_scf:
            keywords.append("TightSCF")
        if defgrid:
            keywords.append(defgrid)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if nprocs > 1:
            lines.append(f"%pal nprocs {nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)


# ==============================================================================
# 2. X2CHandler & Divergence Remediator
# ==============================================================================

class X2CHandler:
    """Detects SCF/DIIS instability in the X2C Hamiltonian cycle and manages divergence remediation."""

    # Error and divergence signatures emitted by ORCA during relativistic SCF failures
    DIVERGENCE_SIGNATURES: List[str] = [
        r"SCF NOT CONVERGED",
        r"Divergence in X2C",
        r"X2C transformation failed",
        r"DIIS failure in X2C",
        r"DIIS failure",
        r"ENERGY DID NOT CONVERGE",
        r"Calculation did not converge",
        r"SCF CONVERGENCE FAILED",
        r"Matrix is not positive definite",
        r"Error in X2C diagonalization",
        r"Diagonalization failed",
    ]

    def detect_divergence(
        self,
        stdout_text: str,
        stderr_text: str = "",
        returncode: int = 0,
    ) -> bool:
        """Detects whether the X2C relativistic Hamiltonian cycle diverged or failed to converge."""
        combined_text = f"{stdout_text}\n{stderr_text}"

        for sig in self.DIVERGENCE_SIGNATURES:
            if re.search(sig, combined_text, re.IGNORECASE):
                return True

        if returncode != 0 and "FINAL SINGLE POINT ENERGY" not in stdout_text:
            return True

        return False

    def validate_convergence(
        self,
        stdout_text: str,
        stderr_text: str = "",
        returncode: int = 0,
    ) -> float:
        """Validates convergence of relativistic calculation and extracts final single-point energy float."""
        if self.detect_divergence(stdout_text, stderr_text, returncode):
            raise X2CDivergenceError(
                "X2C relativistic Hamiltonian diverged or failed during the SCF cycle. "
                "In accordance with CoChem-BENCH Stage 4.0 specifications, fallback to DKH2 "
                "must be explicitly managed via remediation to maintain uniform methodology."
            )

        if returncode != 0:
            raise RelativisticExecutionError(
                f"Relativistic ORCA calculation failed with returncode {returncode}.\n"
                f"Stderr: {stderr_text[:500]}"
            )

        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")

        return float(match.group(1))

    @staticmethod
    def remediate_to_dkh2(input_text: str) -> str:
        """Rewrites an X2C input deck to use Douglas-Kroll-Hess (DKH2)."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!"):
                tokens = stripped.split()
                new_tokens: List[str] = []
                for t in tokens:
                    if t.upper() == "X2C":
                        new_tokens.append("DKH2")
                    elif t.lower().endswith("-x2c"):
                        new_tokens.append(t[:-4] + "-DK")
                    else:
                        new_tokens.append(t)
                if not any(t.upper() in ("DKH", "DKH2") for t in new_tokens):
                    new_tokens.insert(2 if len(new_tokens) >= 2 else 1, "DKH2")
                new_lines.append(" ".join(new_tokens))
            else:
                new_lines.append(line)
        return "\n".join(new_lines) + "\n"


class X2CDivergenceRemediator:
    """Remediates X2C divergence by rewriting input for DKH2 and restarting."""

    def __init__(self) -> None:
        self.handler = X2CHandler()

    def remediate_to_dkh2(self, input_text: str) -> str:
        """Rewrites X2C input for Douglas-Kroll-Hess (DKH2)."""
        return X2CHandler.remediate_to_dkh2(input_text)

    def execute_with_remediation(
        self,
        input_deck: str,
        runner_fn: Callable[..., Tuple[str, str, int]],
        scratch_dir: Optional[Union[str, Path]] = None,
    ) -> Tuple[str, str, int, str]:
        """Executes calculation, intercepting X2C divergence, rewriting for DKH2, and restarting."""
        stdout, stderr, code = runner_fn(input_deck, scratch_dir=scratch_dir)
        hamiltonian_used = "X2C"

        if self.handler.detect_divergence(stdout, stderr, code):
            # Rewrites input deck for Douglas-Kroll-Hess (DKH2) and restarts
            dkh2_deck = self.remediate_to_dkh2(input_deck)
            stdout, stderr, code = runner_fn(dkh2_deck, scratch_dir=scratch_dir)
            hamiltonian_used = "DKH2"

        return stdout, stderr, code, hamiltonian_used


# ==============================================================================
# 3. SpinOrbitCoupler
# ==============================================================================

class SpinOrbitCoupler:
    """Manages open-shell radical detection, SOMF(1X) operator injection, and spin-orbit coupling arithmetic."""

    @staticmethod
    def is_open_shell(
        mult: int = 1,
        requires_uhf: bool = False,
        is_radical: bool = False,
    ) -> bool:
        """Evaluates whether the molecular state is an open-shell radical requiring spin-orbit coupling."""
        return bool(mult > 1 or requires_uhf or is_radical)

    @staticmethod
    def inject_somf_operator(input_text: str) -> str:
        """Injects the SOMF(1X) (Spin-Orbit Mean-Field) operator keyword into the ORCA input deck."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        header_processed = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") and not header_processed:
                tokens = stripped.split()
                if "SOMF(1X)" not in tokens:
                    tokens.append("SOMF(1X)")
                new_lines.append(" ".join(tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed:
            new_lines.insert(0, "! SOMF(1X)")

        return "\n".join(new_lines) + "\n"

    @staticmethod
    def parse_somf_traces(stdout_text: str) -> Optional[Dict[str, float]]:
        """Parses electronic energy shift from SOMF(1X) property block:
        searches for the exact literal strings 'SOMF(1X) Two-Component Trace'
        and 'SOMF(1X) Non-Relativistic Trace', extracts trailing floats and computes
        their difference to obtain Delta_E_SOC = Trace_2C - Trace_nonrel.
        """
        match_2c = re.search(
            r"SOMF\(1X\)\s+Two-Component\s+Trace\s+\.\.\.\s+(-?\d+\.\d+)",
            stdout_text,
            re.IGNORECASE,
        )
        match_nonrel = re.search(
            r"SOMF\(1X\)\s+Non-Relativistic\s+Trace\s+\.\.\.\s+(-?\d+\.\d+)",
            stdout_text,
            re.IGNORECASE,
        )
        if match_2c and match_nonrel:
            trace_2c = float(match_2c.group(1))
            trace_nonrel = float(match_nonrel.group(1))
            return {
                "trace_2c": trace_2c,
                "trace_nonrel": trace_nonrel,
                "delta_e_soc": float(trace_2c - trace_nonrel),
            }
        return None

    @classmethod
    def parse_soc_energy_from_stdout(cls, stdout_text: str) -> Optional[float]:
        """Parses spin-orbit coupling expectation value or shift from ORCA standard output."""
        traces = cls.parse_somf_traces(stdout_text)
        if traces is not None:
            return traces["delta_e_soc"]

        # Pattern 1: SOMF(1X) Energy Shift
        match_somf = re.search(r"SOMF\(1X\)\s+Energy\s+Shift\s+\.\.\.\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_somf:
            return float(match_somf.group(1))

        # Pattern 2: 2C-SOC expectation value
        match_2c = re.search(r"Two-component\s+2C-SOC\s+expectation\s+value\s+\.\.\.\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_2c:
            return float(match_2c.group(1))

        # Pattern 3: Explicit SPIN-ORBIT COUPLING ENERGY
        match_soc = re.search(r"SPIN-ORBIT\s+COUPLING\s+ENERGY\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_soc:
            return float(match_soc.group(1))

        return None

    @staticmethod
    def derive_soc_correction(
        e_total_rel: float,
        e_total_soc: Optional[float] = None,
        soc_trace_hartree: Optional[float] = None,
        trace_2c: Optional[float] = None,
        trace_nonrel: Optional[float] = None,
    ) -> float:
        """Derives the spin-orbit coupling energy correction Delta E_SOC in Hartree."""
        if trace_2c is not None and trace_nonrel is not None:
            return float(trace_2c - trace_nonrel)

        if soc_trace_hartree is not None:
            return float(soc_trace_hartree)

        if e_total_soc is not None:
            return float(e_total_soc - e_total_rel)

        return 0.0


# ==============================================================================
# 4. DeltaRelExtractor
# ==============================================================================

class DeltaRelExtractor:
    """Extracts electronic energies from standard ORCA outputs and derives relativistic correction deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(match.group(1))

    @staticmethod
    def extract_delta(
        e_total_non_rel: float,
        e_total_rel: float,
        e_total_soc: Optional[float] = None,
        soc_trace_hartree: Optional[float] = None,
        basis_set: str = "",
        rel_basis_set: str = "",
        method: str = "DLPNO-CCSD(T)",
        hamiltonian: str = "X2C",
        has_heavy_elements: bool = True,
        is_open_shell: bool = False,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelCorrectionResult:
        """Mathematically derives Delta_E_rel = E_Total^(Rel) - E_Total^(NonRel) and Delta_E_SOC."""
        delta_rel_hartree = float(e_total_rel - e_total_non_rel)
        delta_rel_kcal = float(delta_rel_hartree * HARTREE_TO_KCAL_MOL)

        coupler = SpinOrbitCoupler()
        delta_soc_hartree = coupler.derive_soc_correction(
            e_total_rel=e_total_rel,
            e_total_soc=e_total_soc,
            soc_trace_hartree=soc_trace_hartree,
        )
        delta_soc_kcal = float(delta_soc_hartree * HARTREE_TO_KCAL_MOL)

        delta_total_hartree = float(delta_rel_hartree + delta_soc_hartree)
        delta_total_kcal = float(delta_total_hartree * HARTREE_TO_KCAL_MOL)

        return RelCorrectionResult(
            e_total_non_rel=float(e_total_non_rel),
            e_total_rel=float(e_total_rel),
            e_total_soc=float(e_total_soc) if e_total_soc is not None else None,
            delta_e_rel_hartree=delta_rel_hartree,
            delta_e_rel_kcal_mol=delta_rel_kcal,
            delta_e_soc_hartree=delta_soc_hartree,
            delta_e_soc_kcal_mol=delta_soc_kcal,
            delta_e_total_rel_hartree=delta_total_hartree,
            delta_e_total_rel_kcal_mol=delta_total_kcal,
            basis_set=basis_set,
            rel_basis_set=rel_basis_set,
            method=method,
            hamiltonian=hamiltonian,
            has_heavy_elements=has_heavy_elements,
            is_open_shell=is_open_shell,
            node_id=node_id,
            metadata=metadata or {},
        )

    def extract_from_outputs(
        self,
        stdout_non_rel: str,
        stdout_rel: str,
        stdout_soc: Optional[str] = None,
        basis_set: str = "",
        rel_basis_set: str = "",
        method: str = "DLPNO-CCSD(T)",
        hamiltonian: str = "X2C",
        has_heavy_elements: bool = True,
        is_open_shell: bool = False,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelCorrectionResult:
        """Parses energies directly from standard output texts and computes full relativistic correction."""
        e_non_rel = self.parse_final_energy_from_stdout(stdout_non_rel)

        # Validate relativistic calculation convergence
        handler = X2CHandler()
        e_rel = handler.validate_convergence(stdout_rel)

        e_soc: Optional[float] = None
        soc_trace: Optional[float] = None
        if stdout_soc:
            soc_trace = SpinOrbitCoupler.parse_soc_energy_from_stdout(stdout_soc)
            try:
                e_soc = self.parse_final_energy_from_stdout(stdout_soc)
            except ValueError:
                e_soc = None
            is_open_shell = True

        return self.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=e_soc,
            soc_trace_hartree=soc_trace,
            basis_set=basis_set,
            rel_basis_set=rel_basis_set,
            method=method,
            hamiltonian=hamiltonian,
            has_heavy_elements=has_heavy_elements,
            is_open_shell=is_open_shell,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 5. EphemeralScratchPurge & Air-Gap Isolation
# ==============================================================================

class EphemeralScratchPurge:
    """Manages tripartite scratch workspace creation and sweeps intermediate scratch files."""

    @staticmethod
    def create_scratch_dir(base_artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
        """Creates a dedicated UUID-scoped scratch directory."""
        if base_artifacts_dir:
            base_dir = Path(base_artifacts_dir)
        else:
            base_env = os.environ.get(
                "COCHEM_ARTIFACTS_DIR",
                os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
            )
            base_dir = Path(base_env)

        scratch_dir = base_dir / "BENCH_Workspace" / "Scratch" / f"job_{uuid.uuid4()}"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    @staticmethod
    def get_isolated_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Injects accelerator isolation (CUDA_VISIBLE_DEVICES="") into execution environment."""
        env = dict(base_env) if base_env is not None else dict(os.environ)
        env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    @staticmethod
    def purge_scratch_dir(
        scratch_dir: Union[str, Path],
        remove_dir: bool = True,
    ) -> Dict[str, Any]:
        """Sweeps and unlinks intermediate simulation files (.gbw, .tmp, .densities, etc.)."""
        scratch_path = Path(scratch_dir)
        if not scratch_path.exists():
            return {"status": "not_found", "purged_count": 0}

        purged_files: List[str] = []
        extensions_to_purge = [
            "*.gbw", "*.tmp", "*.densities", "*.bso", "*.prop",
            "*.core", "*.host", "*.ges", "*.int", "*.uco",
        ]

        for ext in extensions_to_purge:
            for p in scratch_path.glob(ext):
                try:
                    p.unlink()
                    purged_files.append(p.name)
                except OSError:
                    pass

        if remove_dir:
            try:
                shutil.rmtree(str(scratch_path), ignore_errors=True)
            except OSError:
                pass

        return {
            "status": "purged",
            "purged_count": len(purged_files),
            "purged_files": purged_files,
        }


# ==============================================================================
# 6. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Dynamically resolves the target landscape.h5 path adhering strictly to COCHEM_ARTIFACTS_DIR."""
    if h5_path is not None:
        return Path(h5_path)
    base_env = os.environ.get(
        "COCHEM_ARTIFACTS_DIR",
        os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
    )
    return Path(base_env) / "BENCH_Workspace" / "landscape.h5"


def commit_rel_to_hdf5(
    h5_path: Union[str, Path],
    result: RelCorrectionResult,
    timeout: float = 120.0,
) -> Path:
    """Commits computed Relativistic and Spin-Orbit correction results atomically to landscape.h5."""
    target_path = resolve_hdf5_path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    node_group_name = result.node_id if result.node_id else "default_rel_node"

    with lock:
        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("rel_corrections")
            node_grp = root_grp.require_group(node_group_name)

            datasets = {
                "e_total_non_rel": result.e_total_non_rel,
                "e_total_rel": result.e_total_rel,
                "delta_e_rel_hartree": result.delta_e_rel_hartree,
                "delta_e_rel_kcal_mol": result.delta_e_rel_kcal_mol,
                "delta_e_soc_hartree": result.delta_e_soc_hartree,
                "delta_e_soc_kcal_mol": result.delta_e_soc_kcal_mol,
                "delta_e_total_rel_hartree": result.delta_e_total_rel_hartree,
                "delta_e_total_rel_kcal_mol": result.delta_e_total_rel_kcal_mol,
            }

            if result.e_total_soc is not None:
                datasets["e_total_soc"] = result.e_total_soc

            for ds_name, ds_val in datasets.items():
                if ds_name in node_grp:
                    del node_grp[ds_name]
                node_grp.create_dataset(ds_name, data=float(ds_val))

            node_grp.attrs["basis_set"] = result.basis_set
            node_grp.attrs["rel_basis_set"] = result.rel_basis_set
            node_grp.attrs["method"] = result.method
            node_grp.attrs["hamiltonian"] = result.hamiltonian
            node_grp.attrs["has_heavy_elements"] = bool(result.has_heavy_elements)
            node_grp.attrs["is_open_shell"] = bool(result.is_open_shell)
            node_grp.attrs["timestamp"] = result.timestamp
            node_grp.attrs["node_id"] = result.node_id

    return target_path


def read_rel_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Reads back computed Relativistic correction results from landscape.h5."""
    target_path = resolve_hdf5_path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    with lock:
        with h5py.File(target_path, "r") as f:
            if "rel_corrections" not in f:
                raise KeyError(f"Root group 'rel_corrections' not found in '{target_path}'")
            root_grp = f["rel_corrections"]
            if node_id not in root_grp:
                raise KeyError(f"Node '{node_id}' not found in 'rel_corrections'")
            node_grp = root_grp[node_id]

            data = {
                "e_total_non_rel": float(node_grp["e_total_non_rel"][()]),
                "e_total_rel": float(node_grp["e_total_rel"][()]),
                "delta_e_rel_hartree": float(node_grp["delta_e_rel_hartree"][()]),
                "delta_e_rel_kcal_mol": float(node_grp["delta_e_rel_kcal_mol"][()]),
                "delta_e_soc_hartree": float(node_grp.get("delta_e_soc_hartree", 0.0)[()]),
                "delta_e_soc_kcal_mol": float(node_grp.get("delta_e_soc_kcal_mol", 0.0)[()]),
                "delta_e_total_rel_hartree": float(node_grp.get("delta_e_total_rel_hartree", node_grp["delta_e_rel_hartree"])[()]),
                "delta_e_total_rel_kcal_mol": float(node_grp.get("delta_e_total_rel_kcal_mol", node_grp["delta_e_rel_kcal_mol"])[()]),
                "basis_set": str(node_grp.attrs.get("basis_set", "")),
                "rel_basis_set": str(node_grp.attrs.get("rel_basis_set", "")),
                "method": str(node_grp.attrs.get("method", "")),
                "hamiltonian": str(node_grp.attrs.get("hamiltonian", "X2C")),
                "has_heavy_elements": bool(node_grp.attrs.get("has_heavy_elements", True)),
                "is_open_shell": bool(node_grp.attrs.get("is_open_shell", False)),
                "timestamp": str(node_grp.attrs.get("timestamp", "")),
                "node_id": str(node_grp.attrs.get("node_id", "")),
            }

            if "e_total_soc" in node_grp:
                data["e_total_soc"] = float(node_grp["e_total_soc"][()])

            return data


def run_rel_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_total_non_rel: float,
    e_total_rel: float,
    e_total_soc: Optional[float] = None,
    base_basis: str = "def2-TZVPP",
    method: str = "DLPNO-CCSD(T)",
    charge: int = 0,
    mult: int = 1,
    requires_uhf: bool = False,
    is_radical: bool = False,
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
    hamiltonian: str = "X2C",
) -> RelCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 4.0 Relativistic and SOC Correction."""
    # 1. Map basis set and inspect elemental composition
    injector = RelativisticHamiltonianInjector()
    rel_basis = injector.map_relativistic_basis_set(base_basis, hamiltonian=hamiltonian)
    heavy_info = injector.inspect_heavy_elements(coords)

    # 2. Check open shell
    is_open_shell = SpinOrbitCoupler.is_open_shell(
        mult=mult, requires_uhf=requires_uhf, is_radical=is_radical
    )

    # 3. Extract delta and create result model
    extractor = DeltaRelExtractor()
    result = extractor.extract_delta(
        e_total_non_rel=e_total_non_rel,
        e_total_rel=e_total_rel,
        e_total_soc=e_total_soc,
        basis_set=base_basis,
        rel_basis_set=rel_basis,
        method=method,
        hamiltonian=hamiltonian,
        has_heavy_elements=heavy_info["has_heavy_elements"],
        is_open_shell=is_open_shell,
        node_id=node_id,
        metadata={"heavy_info": heavy_info},
    )

    # 4. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_rel_to_hdf5(h5_path=h5_path, result=result)

    return result

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_engine\__init__.py ---
"""CoChem-BENCH Engine Package."""

from cochem_bench.bench_engine.cochem_bench_cbs import (
    ALPHA_BETA_MAP,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    HARTREE_TO_KCAL_MOL,
    PARAMETER_MATRIX,
    CBSExtrapolationError,
    CBSExtrapolationResult,
    CBSParameterError,
    CBSParsingError,
    CBSSingularDenominatorError,
    DualBasisDispatcher,
    EnergyDecompositionResult,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptionResult,
    SlowConvInterceptor,
    commit_cbs_to_hdf5,
    parse_orca_energies,
    read_cbs_from_hdf5,
    resolve_hdf5_path,
    run_cbs_pipeline,
)
from cochem_bench.bench_engine.cochem_bench_ingest import (
    BenchConfigSchema,
    BenchHardwareSchema,
    BenchRunContext,
    BenchSiloPathsSchema,
    HardwareGovernor,
    HardwareGovernorResult,
    PreFlightVerification,
    RegistryHandshake,
    ResourceGuardError,
    SiloIntegrityError,
    cleanse_ld_library_path,
    extract_orca_path,
    run_bench_ingest_pipeline,
)
from cochem_bench.bench_engine.cochem_bench_cv import (
    CVCorrectionError,
    CVCorrectionResult,
    CVExecutionError,
    CVParsingError,
    CVScratchPurgeError,
    CoreValenceMapper,
    DeltaExtractor,
    DualCorrelationEngine,
    EphemeralScratchPurge,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
)
from cochem_bench.bench_engine.cochem_bench_rel import (
    DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    DeltaRelExtractor,
    RelCorrectionResult,
    RelativisticExecutionError,
    RelativisticHamiltonianInjector,
    RelativisticInputError,
    SpinOrbitCoupler,
    X2CDivergenceError,
    X2CDivergenceRemediator,
    X2CHandler,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
)

__all__ = [
    # Stage 1.0
    "BenchConfigSchema",
    "BenchHardwareSchema",
    "BenchRunContext",
    "BenchSiloPathsSchema",
    "HardwareGovernor",
    "HardwareGovernorResult",
    "PreFlightVerification",
    "RegistryHandshake",
    "ResourceGuardError",
    "SiloIntegrityError",
    "cleanse_ld_library_path",
    "extract_orca_path",
    "run_bench_ingest_pipeline",
    # Stage 2.0 CBS
    "ALPHA_BETA_MAP",
    "PARAMETER_MATRIX",
    "HARTREE_TO_KCAL_MOL",
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    "CBSExtrapolationError",
    "CBSParameterError",
    "CBSSingularDenominatorError",
    "CBSParsingError",
    "CBSExtrapolationResult",
    "SlowConvInterceptionResult",
    "EnergyDecompositionResult",
    "parse_orca_energies",
    "DualBasisDispatcher",
    "HelgakerExtrapolator",
    "ResidualFitAnalyzer",
    "SlowConvInterceptor",
    "resolve_hdf5_path",
    "commit_cbs_to_hdf5",
    "read_cbs_from_hdf5",
    "run_cbs_pipeline",
    # Stage 3.0 CV
    "CoreValenceMapper",
    "DualCorrelationEngine",
    "DeltaExtractor",
    "EphemeralScratchPurge",
    "CVCorrectionResult",
    "CVCorrectionError",
    "CVExecutionError",
    "CVParsingError",
    "CVScratchPurgeError",
    "commit_cv_to_hdf5",
    "read_cv_from_hdf5",
    "run_cv_pipeline",
    # Stage 4.0 Relativistic & SOC
    "RelativisticHamiltonianInjector",
    "X2CHandler",
    "X2CDivergenceRemediator",
    "X2CDivergenceError",
    "RelativisticExecutionError",
    "RelativisticInputError",
    "SpinOrbitCoupler",
    "DeltaRelExtractor",
    "RelCorrectionResult",
    "commit_rel_to_hdf5",
    "read_rel_from_hdf5",
    "run_rel_pipeline",
    "DEFAULT_RELATIVISTIC_Z_THRESHOLD",
]



--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_rel.py ---
#!/usr/bin/env python3
r"""Authentic Zero-Mock Unit Test Suite for Stage 4.0 Relativistic and Spin-Orbit Corrections.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_rel / bench_engine.cochem_bench_rel
System Domain: CoChem-BENCH Scientific Engine

Test Requirements & Contracts:
1. RelativisticHamiltonianInjector:
   - Re-contracts basis sets:
     * Karlsruhe: replacing "def2-" with "x2c-" and appending "all-s"
       (e.g., def2-TZVPP -> x2c-TZVPPall-s, def2-SVP -> x2c-SVPall-s, def2-QZVPP -> x2c-QZVPPall-s).
     * Correlation consistent: appending "-DK" (e.g., cc-pVDZ -> cc-pVDZ-DK, cc-pVTZ -> cc-pVTZ-DK,
       cc-pVQZ -> cc-pVQZ-DK, aug-cc-pVTZ -> aug-cc-pVTZ-DK) or "-X2C".
   - inspect_heavy_elements using mendeleev.element to dynamically get atomic mass and atomic number (Z >= 19).
   - Generates valid ORCA input decks with ! X2C, %maxcore, coordinates.
2. X2CHandler & Divergence Remediator:
   - Detects X2C divergence / SCF / DIIS failure signatures.
   - If X2C diverges, catches failure in subprocess.run / runner, rewrites input for Douglas-Kroll-Hess (! DKH2), and restarts.
   - Parses E_Total from both outputs using the exact literal string "FINAL SINGLE POINT ENERGY".
   - Computes Delta_E_rel = E_Total^(Relativistic) - E_Total^(Non-Rel).
3. SpinOrbitCoupler:
   - For geometries flagged REQUIRES_UHF in Stage 1.0 (or mult > 1 / radical), injects ! SOMF(1X).
   - Parses electronic energy shift from SOMF(1X) property block: searches for the exact literal strings
     "SOMF(1X) Two-Component Trace" and "SOMF(1X) Non-Relativistic Trace". Extracts trailing floats
     and computes their difference to obtain Delta_E_SOC = Trace_2C - Trace_nonrel.
4. DeltaRelExtractor:
   - Extracts energies and computes Delta_E_rel and Delta_E_SOC in Hartree and kcal/mol (using HARTREE_TO_KCAL_MOL = 627.509474063).
5. EphemeralScratchPurge & Air-Gap:
   - Resolves UUID scratch workspace dynamically via os.environ["COCHEM_ARTIFACTS_DIR"].
   - Isolates in UUID scratch with CUDA_VISIBLE_DEVICES="".
   - Purges transient simulation files (*.gbw, *.tmp, *.densities, *.bso, *.prop, etc.).
6. HDF5 Persistence & Stage 5.0 Composite Aggregator Integration:
   - Thread-safe commit_rel_to_hdf5 with filelock.FileLock under rel_corrections/{node_id} in landscape.h5.
   - read_rel_from_hdf5.
   - Composite aggregator validation: E_total = E_SCF_CBS + E_corr_CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
"""

from __future__ import annotations

import math
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import filelock
import h5py
import pytest
from mendeleev import element

# Verify importability from both bench_engine and cochem_bench.bench_engine
from bench_engine.cochem_bench_rel import (
    DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    HARTREE_TO_KCAL_MOL,
    DeltaRelExtractor,
    EphemeralScratchPurge,
    RelCorrectionResult,
    RelativisticExecutionError,
    RelativisticHamiltonianInjector,
    RelativisticInputError,
    SpinOrbitCoupler,
    X2CDivergenceError,
    X2CDivergenceRemediator,
    X2CHandler,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    resolve_hdf5_path,
    run_rel_pipeline,
)
from cochem_bench.bench_engine.cochem_bench_rel import (
    RelativisticHamiltonianInjector as CochemRelInjector,
)
from bench_engine.cochem_bench_export import (
    CompositeAggregator,
    CompositeEnergyRecord,
)
from bench_engine.cochem_bench_cbs import (
    CBSExtrapolationResult,
    commit_cbs_to_hdf5,
)
from bench_engine.cochem_bench_cv import (
    CVCorrectionResult,
    commit_cv_to_hdf5,
)


# ==============================================================================
# Authentic Molecular Test Geometries (Cartesian Coordinates in Angstroms)
# ==============================================================================

# Water Molecule (Light elements: H (Z=1), O (Z=8) - Sub-relativistic threshold Z < 19)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Bromobenzene (Heavy element: Br - Z = 35, 4th Period, requires X2C)
BROMOBENZENE_COORDS: List[Tuple[str, float, float, float]] = [
    ("Br", 0.000000, 0.000000, 1.890000),
    ("C",  0.000000, 0.000000, 0.000000),
    ("C",  0.000000, 1.210000, -0.700000),
    ("C",  0.000000, -1.210000, -0.700000),
    ("C",  0.000000, 1.200000, -2.090000),
    ("C",  0.000000, -1.200000, -2.090000),
    ("C",  0.000000, 0.000000, -2.790000),
    ("H",  0.000000, 2.140000, -0.160000),
    ("H",  0.000000, -2.140000, -0.160000),
    ("H",  0.000000, 2.140000, -2.630000),
    ("H",  0.000000, -2.140000, -2.630000),
    ("H",  0.000000, 0.000000, -3.870000),
]

# Dimethyl Selenide (Heavy element: Se - Z = 34, 4th Period)
DMSE_COORDS: List[Tuple[str, float, float, float]] = [
    ("Se", 0.000000, 0.000000, 0.000000),
    ("C",  0.000000, 1.500000, 1.100000),
    ("C",  0.000000, -1.500000, 1.100000),
    ("H",  0.890000, 1.500000, 1.700000),
    ("H", -0.890000, 1.500000, 1.700000),
    ("H",  0.000000, 2.380000, 0.480000),
    ("H",  0.890000, -1.500000, 1.700000),
    ("H", -0.890000, -1.500000, 1.700000),
    ("H",  0.000000, -2.380000, 0.480000),
]

# Methyl Radical (Open-shell doublet radical: CH3, Multiplicity = 2, requires SOMF(1X))
METHYL_RADICAL_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 1.079000, 0.000000),
    ("H", 0.934441, -0.539500, 0.000000),
    ("H", -0.934441, -0.539500, 0.000000),
]


# ==============================================================================
# Authentic ORCA 6.1.1 Output Fixtures
# ==============================================================================

ORCA_NON_REL_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1
Number of Electrons                   ...   82

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2803.11548291 Eh
E(DLPNO-CCSD)                         ... -2804.89240182 Eh
E(DLPNO-CCSD(T))                      ... -2805.01248912 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2805.012489120000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_REL_X2C_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Relativistic Mode                     ... Exact Two-Component (X2C)
Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2824.78129410 Eh
E(DLPNO-CCSD)                         ... -2826.56841295 Eh
E(DLPNO-CCSD(T))                      ... -2826.68940125 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.689401250000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_REL_DKH2_STDOUT_BROMOBENZENE = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -

Relativistic Mode                     ... Douglas-Kroll-Hess (DKH2)
Number of atoms                       ...   12
Total Charge                          ...    0
Multiplicity                          ...    1

-------------------------
DLPNO-CCSD(T) CALCULATION
-------------------------
E(SCF)                                ... -2824.77918230 Eh
E(DLPNO-CCSD)                         ... -2826.56628100 Eh
E(DLPNO-CCSD(T))                      ... -2826.68725000 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.687250000000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""

ORCA_X2C_DIVERGENCE_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Relativistic Mode                     ... Exact Two-Component (X2C)
Diagonalizing X2C 1-electron relativistic Hamiltonian...
SCF cycle initiated...
ITER  1: E = -2820.1234  DeltaE =  0.000000  MaxGrad = 0.1234
ITER  2: E = -2825.9812  DeltaE = -5.857800  MaxGrad = 0.5621
ITER  3: E = -2812.4419  DeltaE = +13.53930  MaxGrad = 1.9821
ITER 50: E = -2801.1299  DeltaE = +0.892110  MaxGrad = 0.8124
[ERROR] SCF NOT CONVERGED AFTER 50 ITERATIONS. DIIS failure in X2C Hamiltonian cycle.
Matrix is not positive definite.
Calculation did not converge.
ORCA finished with error.
"""

ORCA_SOC_SOMF_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Program Version 6.1.1 -  RELEASE  -
Relativistic Mode                     ... Exact Two-Component (X2C)
Spin-Orbit Coupling Operator          ... SOMF(1X) (Spin-Orbit Mean-Field)
Multiplicity                          ...    2 (Open-Shell Radical)

-------------------------------------------------------------------------------
SOMF(1X) SPIN-ORBIT COUPLING CORRECTION
-------------------------------------------------------------------------------
SOMF(1X) Two-Component Trace          ... -2826.691246370000
SOMF(1X) Non-Relativistic Trace       ... -2826.689401250000

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                         -2826.691246370000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""


# ==============================================================================
# 1. RelativisticHamiltonianInjector Unit Tests
# ==============================================================================

class TestRelativisticHamiltonianInjector:
    """Authentic tests for basis set re-contraction, dynamic elemental inspection, and ORCA deck creation."""

    def test_recontract_karlsruhe_basis_sets(self) -> None:
        """Verifies Karlsruhe def2 basis sets replace 'def2-' with 'x2c-' and append 'all-s'."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("def2-SVP") == "x2c-SVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVP") == "x2c-TZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPP") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVPP") == "x2c-QZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVP") == "x2c-QZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPD") == "x2c-TZVPDall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPPD") == "x2c-TZVPPDall-s"

    def test_recontract_dunning_basis_sets_dk(self) -> None:
        """Verifies Dunning correlation-consistent basis sets map to '-DK' for Douglas-Kroll-Hess."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_basis_dk("cc-pVDZ") == "cc-pVDZ-DK"
        assert injector.map_basis_dk("cc-pVTZ") == "cc-pVTZ-DK"
        assert injector.map_basis_dk("cc-pVQZ") == "cc-pVQZ-DK"
        assert injector.map_basis_dk("aug-cc-pVTZ") == "aug-cc-pVTZ-DK"
        assert injector.map_basis_dk("cc-pCVTZ") == "cc-pCVTZ-DK"
        assert injector.map_basis_dk("aug-cc-pwCVTZ") == "aug-cc-pwCVTZ-DK"

    def test_recontract_dunning_basis_sets_x2c(self) -> None:
        """Verifies Dunning correlation-consistent basis sets map to '-X2C' for X2C mode."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("cc-pVDZ", hamiltonian="X2C") == "cc-pVDZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVTZ", hamiltonian="X2C") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVQZ", hamiltonian="X2C") == "cc-pVQZ-X2C"
        assert injector.map_relativistic_basis_set("aug-cc-pVTZ", hamiltonian="X2C") == "aug-cc-pVTZ-X2C"

    def test_recontract_idempotent_and_ano_rcc(self) -> None:
        """Verifies that already relativistic basis sets remain unchanged."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("x2c-TZVPPall-s") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("cc-pVTZ-DK") == "cc-pVTZ-DK"
        assert injector.map_relativistic_basis_set("cc-pVTZ-X2C") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("ano-rcc") == "ano-rcc"
        assert injector.map_relativistic_basis_set("ano-rcc-TZP") == "ano-rcc-TZP"

    def test_dynamic_elemental_inspection_mendeleev(self) -> None:
        """Verifies dynamic inspection using mendeleev.element for atomic mass and Z >= 19 detection."""
        injector = RelativisticHamiltonianInjector()

        # Light system: Water (H: Z=1, O: Z=8)
        info_h2o = injector.inspect_heavy_elements(WATER_COORDS, relativistic_z_threshold=19)
        assert info_h2o["has_heavy_elements"] is False
        assert info_h2o["max_z"] == 8
        assert len(info_h2o["heavy_elements"]) == 0
        expected_h2o_mass = float(element("O").mass + 2 * element("H").mass)
        assert math.isclose(info_h2o["total_mass"], expected_h2o_mass, rel_tol=1e-5)

        # Heavy system: Bromobenzene (Br: Z=35)
        info_br = injector.inspect_heavy_elements(BROMOBENZENE_COORDS, relativistic_z_threshold=19)
        assert info_br["has_heavy_elements"] is True
        assert info_br["max_z"] == 35
        assert "Br" in info_br["heavy_elements"]
        expected_br_z = element("Br").atomic_number
        assert expected_br_z == 35

        # Heavy system: Dimethyl Selenide (Se: Z=34)
        info_se = injector.inspect_heavy_elements(DMSE_COORDS, relativistic_z_threshold=19)
        assert info_se["has_heavy_elements"] is True
        assert info_se["max_z"] == 34
        assert "Se" in info_se["heavy_elements"]

    def test_inject_relativistic_hamiltonian_orca_input(self) -> None:
        """Verifies modifying ORCA input text with X2C and re-contracted basis set."""
        injector = RelativisticHamiltonianInjector()
        raw_input = (
            "! DLPNO-CCSD(T) def2-TZVPP TightSCF\n"
            "%maxcore 4000\n"
            "* xyz 0 1\n"
            "  Br  0.0 0.0 1.89\n"
            "*\n"
        )

        rel_input = injector.inject_relativistic_hamiltonian(raw_input)
        assert "X2C" in rel_input
        assert "x2c-TZVPPall-s" in rel_input
        assert "%maxcore 4000" in rel_input
        assert "Br  0.0 0.0 1.89" in rel_input

    def test_generate_input_decks_maxcore_and_nprocs(self) -> None:
        """Verifies dual input deck generation for baseline non-rel and relativistic jobs with %maxcore."""
        injector = RelativisticHamiltonianInjector()
        decks = injector.generate_input_decks(
            coords=BROMOBENZENE_COORDS,
            method="DLPNO-CCSD(T)",
            base_basis="def2-TZVPP",
            charge=0,
            mult=1,
            node_max_gb=16.0,
            nprocs=4,
            ram_safety_fraction=0.75,
        )

        assert "non_rel_input" in decks
        assert "rel_input" in decks
        assert "def2-TZVPP" in decks["non_rel_input"]
        assert "X2C" not in decks["non_rel_input"]

        assert "X2C" in decks["rel_input"]
        assert "x2c-TZVPPall-s" in decks["rel_input"]
        assert decks["has_heavy_elements"] is True

        # Check %maxcore calculation: (16 * 1024 * 0.75) / 4 = 3072 MB
        assert "%maxcore 3072" in decks["rel_input"]
        assert "%pal nprocs 4 end" in decks["rel_input"]


# ==============================================================================
# 2. X2CHandler & Divergence Remediator Tests
# ==============================================================================

class TestX2CHandlerAndDivergenceRemediator:
    """Authentic tests for X2C divergence detection, error trapping, DKH2 rewriting, and restart."""

    def test_detect_divergence_signatures(self) -> None:
        """Verifies detection of various SCF divergence and DIIS failure signatures in ORCA outputs."""
        handler = X2CHandler()

        # Normal converged output
        assert handler.detect_divergence(ORCA_REL_X2C_STDOUT_BROMOBENZENE) is False

        # Divergence output with DIIS failure
        assert handler.detect_divergence(ORCA_X2C_DIVERGENCE_STDOUT) is True

        # Custom signature tests
        assert handler.detect_divergence("Error: SCF NOT CONVERGED in step 40") is True
        assert handler.detect_divergence("Matrix is not positive definite during X2C transformation") is True
        assert handler.detect_divergence("Diagonalization failed in X2C Hamiltonian cycle") is True

    def test_validate_convergence_success(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic X2C output."""
        handler = X2CHandler()
        energy = handler.validate_convergence(ORCA_REL_X2C_STDOUT_BROMOBENZENE)
        assert math.isclose(energy, -2826.68940125, rel_tol=1e-9)

    def test_validate_convergence_divergence_raises_exception(self) -> None:
        """Verifies that X2CDivergenceError is raised when X2C calculation diverges."""
        handler = X2CHandler()
        with pytest.raises(X2CDivergenceError) as exc_info:
            handler.validate_convergence(ORCA_X2C_DIVERGENCE_STDOUT)

        err_msg = str(exc_info.value).lower()
        assert "diverge" in err_msg or "fail" in err_msg

    def test_remediate_input_deck_to_dkh2(self) -> None:
        """Verifies rewriting of input deck from X2C to Douglas-Kroll-Hess (! DKH2)."""
        handler = X2CHandler()
        x2c_deck = "! DLPNO-CCSD(T) X2C cc-pVTZ-X2C TightSCF\n%maxcore 3000\n* xyz 0 1\n  Br 0 0 0\n*\n"
        dkh2_deck = handler.remediate_to_dkh2(x2c_deck)

        assert "DKH2" in dkh2_deck
        assert "X2C" not in dkh2_deck
        assert "cc-pVTZ-DK" in dkh2_deck

    def test_divergence_remediator_execution_and_restart(self) -> None:
        """Verifies divergence remediator intercepts X2C failure, rewrites to DKH2, and restarts."""
        remediator = X2CDivergenceRemediator()
        initial_x2c_deck = "! DLPNO-CCSD(T) X2C x2c-TZVPPall-s TightSCF\n* xyz 0 1\n  Br 0 0 0\n*\n"

        call_count = 0
        executed_decks = []

        def mock_orca_runner(deck: str, scratch_dir: Any = None) -> Tuple[str, str, int]:
            nonlocal call_count, executed_decks
            call_count += 1
            executed_decks.append(deck)
            if "X2C" in deck:
                # Simulate X2C divergence failure
                return ORCA_X2C_DIVERGENCE_STDOUT, "SCF failed", 1
            else:
                # Remediated DKH2 calculation converges
                return ORCA_REL_DKH2_STDOUT_BROMOBENZENE, "", 0

        stdout, stderr, code, hamiltonian_used = remediator.execute_with_remediation(
            input_deck=initial_x2c_deck,
            runner_fn=mock_orca_runner,
        )

        assert call_count == 2
        assert hamiltonian_used == "DKH2"
        assert "DKH2" in executed_decks[1]

        # Parse energy from remediated output
        extractor = DeltaRelExtractor()
        e_rel_dkh2 = extractor.parse_final_energy_from_stdout(stdout)
        assert math.isclose(e_rel_dkh2, -2826.68725000, rel_tol=1e-9)

        # Calculate Delta_E_rel
        e_non_rel = -2805.01248912
        delta_rel = float(e_rel_dkh2 - e_non_rel)
        assert delta_rel < 0.0


# ==============================================================================
# 3. SpinOrbitCoupler Unit Tests
# ==============================================================================

class TestSpinOrbitCoupler:
    """Authentic tests for open-shell radical detection, SOMF(1X) injection, and trace delta parsing."""

    def test_is_open_shell_flagging(self) -> None:
        """Verifies open-shell radical state classification (mult > 1, requires_uhf, is_radical)."""
        coupler = SpinOrbitCoupler()

        # Closed-shell singlet
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=False) is False

        # Open-shell doublet (radical)
        assert coupler.is_open_shell(mult=2, requires_uhf=False, is_radical=False) is True

        # Triplet
        assert coupler.is_open_shell(mult=3, requires_uhf=False, is_radical=False) is True

        # Flagged by Stage 1.0 requires_uhf
        assert coupler.is_open_shell(mult=1, requires_uhf=True, is_radical=False) is True

        # Flagged by is_radical
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=True) is True

    def test_inject_somf_operator(self) -> None:
        """Verifies injection of SOMF(1X) spin-orbit coupling keyword into input deck."""
        coupler = SpinOrbitCoupler()
        raw_deck = "! DLPNO-CCSD(T) X2C x2c-TZVPPall-s TightSCF\n* xyz 0 2\n  C 0 0 0\n*\n"
        somf_deck = coupler.inject_somf_operator(raw_deck)

        assert "SOMF(1X)" in somf_deck

        # Invariant: idempotent injection
        re_injected = coupler.inject_somf_operator(somf_deck)
        assert re_injected.count("SOMF(1X)") == 1

    def test_parse_somf_traces_authentic_orca(self) -> None:
        """Verifies parsing of exact literal strings 'SOMF(1X) Two-Component Trace' and 'SOMF(1X) Non-Relativistic Trace'."""
        coupler = SpinOrbitCoupler()
        traces = coupler.parse_somf_traces(ORCA_SOC_SOMF_STDOUT)

        assert traces is not None
        assert math.isclose(traces["trace_2c"], -2826.69124637, rel_tol=1e-9)
        assert math.isclose(traces["trace_nonrel"], -2826.68940125, rel_tol=1e-9)

        expected_delta_soc = -2826.69124637 - (-2826.68940125)
        assert math.isclose(traces["delta_e_soc"], expected_delta_soc, rel_tol=1e-9)

        # Verify parse_soc_energy_from_stdout uses traces
        soc_shift = coupler.parse_soc_energy_from_stdout(ORCA_SOC_SOMF_STDOUT)
        assert soc_shift is not None
        assert math.isclose(soc_shift, expected_delta_soc, rel_tol=1e-9)

    def test_derive_soc_correction_open_vs_closed_shell(self) -> None:
        """Verifies derivation of Delta E_SOC in Hartree for open-shell vs closed-shell."""
        coupler = SpinOrbitCoupler()

        # Open-shell with explicit traces
        delta_soc_traces = coupler.derive_soc_correction(
            e_total_rel=-2826.68940125,
            trace_2c=-2826.69124637,
            trace_nonrel=-2826.68940125,
        )
        assert math.isclose(delta_soc_traces, -0.00184512, rel_tol=1e-6)

        # Closed-shell without SOC
        delta_soc_closed = coupler.derive_soc_correction(
            e_total_rel=-2826.68940125,
            e_total_soc=None,
        )
        assert delta_soc_closed == 0.0


# ==============================================================================
# 4. DeltaRelExtractor Unit Tests
# ==============================================================================

class TestDeltaRelExtractor:
    """Authentic tests for energy parsing, Delta E_rel derivation, and Hartree to kcal/mol conversion."""

    def test_parse_final_energy_from_stdout(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
        extractor = DeltaRelExtractor()
        e_non_rel = extractor.parse_final_energy_from_stdout(ORCA_NON_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_non_rel, -2805.01248912, rel_tol=1e-9)

        e_rel = extractor.parse_final_energy_from_stdout(ORCA_REL_X2C_STDOUT_BROMOBENZENE)
        assert math.isclose(e_rel, -2826.68940125, rel_tol=1e-9)

    def test_extract_delta_scalar_and_soc_math(self) -> None:
        """Verifies Delta_E_rel and Delta_E_SOC math and conversion to kcal/mol via exact CODATA."""
        extractor = DeltaRelExtractor()
        e_non_rel = -2805.01248912
        e_rel = -2826.68940125
        e_soc = -2826.69124637

        result = extractor.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=e_soc,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id="bromobenzene_node",
        )

        expected_delta_rel_hartree = float(e_rel - e_non_rel)
        expected_delta_rel_kcal = float(expected_delta_rel_hartree * HARTREE_TO_KCAL_MOL)
        expected_delta_soc_hartree = float(e_soc - e_rel)
        expected_delta_soc_kcal = float(expected_delta_soc_hartree * HARTREE_TO_KCAL_MOL)
        expected_delta_total_hartree = float(expected_delta_rel_hartree + expected_delta_soc_hartree)
        expected_delta_total_kcal = float(expected_delta_total_hartree * HARTREE_TO_KCAL_MOL)

        assert math.isclose(result.delta_e_rel_hartree, expected_delta_rel_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_rel_kcal_mol, expected_delta_rel_kcal, rel_tol=1e-9)
        assert math.isclose(result.delta_e_soc_hartree, expected_delta_soc_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_soc_kcal_mol, expected_delta_soc_kcal, rel_tol=1e-9)
        assert math.isclose(result.delta_e_total_rel_hartree, expected_delta_total_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_total_rel_kcal_mol, expected_delta_total_kcal, rel_tol=1e-9)
        assert result.node_id == "bromobenzene_node"

    def test_extract_from_outputs_full_pipeline(self) -> None:
        """Verifies direct extraction from standard outputs with SOC traces."""
        extractor = DeltaRelExtractor()
        result = extractor.extract_from_outputs(
            stdout_non_rel=ORCA_NON_REL_STDOUT_BROMOBENZENE,
            stdout_rel=ORCA_REL_X2C_STDOUT_BROMOBENZENE,
            stdout_soc=ORCA_SOC_SOMF_STDOUT,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            node_id="br_node_01",
        )

        assert result.node_id == "br_node_01"
        assert result.is_open_shell is True
        assert math.isclose(result.e_total_non_rel, -2805.01248912, rel_tol=1e-9)
        assert math.isclose(result.e_total_rel, -2826.68940125, rel_tol=1e-9)
        assert result.delta_e_soc_hartree < 0.0


# ==============================================================================
# 5. EphemeralScratchPurge & Air-Gap Isolation Tests
# ==============================================================================

class TestEphemeralScratchPurgeAndAirGap:
    """Authentic tests for dynamic scratch creation, accelerator isolation, and file purging."""

    def test_scratch_dir_resolution_via_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verifies resolution of UUID scratch workspace dynamically via COCHEM_ARTIFACTS_DIR."""
        artifacts_dir = tmp_path / "custom_artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))

        scratch_dir = EphemeralScratchPurge.create_scratch_dir()
        assert scratch_dir.exists()
        assert str(artifacts_dir) in str(scratch_dir)
        assert "BENCH_Workspace" in str(scratch_dir)
        assert "Scratch" in str(scratch_dir)

    def test_accelerator_isolation_env(self) -> None:
        """Verifies injection of accelerator isolation (CUDA_VISIBLE_DEVICES="")."""
        env = EphemeralScratchPurge.get_isolated_env({"PATH": "/usr/bin", "FOO": "BAR"})
        assert env["CUDA_VISIBLE_DEVICES"] == ""
        assert env["PATH"] == "/usr/bin"
        assert env["FOO"] == "BAR"

    def test_scratch_purge_transient_files(self, tmp_path: Path) -> None:
        """Verifies unlinking of transient files (.gbw, .tmp, .densities, etc.) and directory cleanup."""
        scratch_dir = tmp_path / "mock_scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        # Create transient simulation files
        transient_extensions = [
            "orca.gbw", "orca.tmp", "orca.densities", "orca.bso",
            "orca.prop", "orca.core", "orca.host", "orca.ges",
            "orca.int", "orca.uco",
        ]
        created_files = []
        for name in transient_extensions:
            fpath = scratch_dir / name
            fpath.write_text("transient quantum chemistry data", encoding="utf-8")
            created_files.append(fpath)

        # Run purge
        purge_report = EphemeralScratchPurge.purge_scratch_dir(scratch_dir, remove_dir=True)
        assert purge_report["status"] == "purged"
        assert purge_report["purged_count"] == len(transient_extensions)
        assert not scratch_dir.exists()


# ==============================================================================
# 6. HDF5 Persistence & Composite Aggregator Tests
# ==============================================================================

class TestHDF5PersistenceAndCompositeIntegration:
    """Authentic tests for thread-safe FileLock HDF5 persistence and Stage 5.0 Composite Aggregator."""

    def test_commit_and_read_rel_hdf5_threadsafe(self, tmp_path: Path) -> None:
        """Verifies thread-safe atomic write to landscape.h5 under rel_corrections/{node_id} and roundtrip read."""
        h5_file = tmp_path / "landscape.h5"

        extractor = DeltaRelExtractor()
        result = extractor.extract_delta(
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            e_total_soc=-2826.69124637,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id="node_test_01",
        )

        commit_rel_to_hdf5(h5_path=h5_file, result=result)

        # Direct inspection of HDF5 structure
        with h5py.File(h5_file, "r") as f:
            assert "rel_corrections" in f
            assert "node_test_01" in f["rel_corrections"]
            grp = f["rel_corrections"]["node_test_01"]

            assert "e_total_non_rel" in grp
            assert "e_total_rel" in grp
            assert "delta_e_rel_hartree" in grp
            assert "delta_e_rel_kcal_mol" in grp
            assert "delta_e_soc_hartree" in grp
            assert "delta_e_soc_kcal_mol" in grp
            assert "delta_e_total_rel_hartree" in grp
            assert "delta_e_total_rel_kcal_mol" in grp
            assert grp.attrs["basis_set"] == "def2-TZVPP"
            assert grp.attrs["rel_basis_set"] == "x2c-TZVPPall-s"
            assert grp.attrs["hamiltonian"] == "X2C"
            assert bool(grp.attrs["has_heavy_elements"]) is True
            assert bool(grp.attrs["is_open_shell"]) is True

        # Read back via API
        data = read_rel_from_hdf5(h5_path=h5_file, node_id="node_test_01")
        assert math.isclose(data["e_total_non_rel"], -2805.01248912, rel_tol=1e-9)
        assert math.isclose(data["e_total_rel"], -2826.68940125, rel_tol=1e-9)
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)
        assert math.isclose(data["delta_e_soc_hartree"], result.delta_e_soc_hartree, rel_tol=1e-7)
        assert data["basis_set"] == "def2-TZVPP"
        assert data["rel_basis_set"] == "x2c-TZVPPall-s"

    def test_run_rel_pipeline_end_to_end(self, tmp_path: Path) -> None:
        """Verifies end-to-end run_rel_pipeline execution and persistence."""
        h5_file = tmp_path / "landscape.h5"

        result = run_rel_pipeline(
            coords=BROMOBENZENE_COORDS,
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            base_basis="def2-TZVPP",
            method="DLPNO-CCSD(T)",
            node_id="bromobenzene_pipeline_node",
            h5_path=h5_file,
        )

        assert isinstance(result, RelCorrectionResult)
        assert result.has_heavy_elements is True
        assert result.rel_basis_set == "x2c-TZVPPall-s"

        data = read_rel_from_hdf5(h5_path=h5_file, node_id="bromobenzene_pipeline_node")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)

    def test_composite_aggregator_stage5_validation(self, tmp_path: Path) -> None:
        """Verifies Stage 5.0 CompositeAggregator evaluates:
        E_total = E_SCF_CBS + E_corr_CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE.
        """
        h5_file = tmp_path / "landscape.h5"
        node_id = "composite_validation_node"

        # 1. Commit CBS extrapolation limit (Stage 2.0)
        cbs_res = CBSExtrapolationResult(
            e_scf_cbs=-76.062400,
            e_corr_cbs=-0.365200,
            e_total_cbs=-76.427600,
            basis_x="def2-TZVP",
            basis_y="def2-QZVPP",
            alpha=7.88,
            beta=2.97,
            residual_variance_hartree=0.0012,
            residual_variance_kcal_mol=0.753,
            uncertainty_flag="PASSED",
            node_id=node_id,
        )
        commit_cbs_to_hdf5(h5_file, cbs_res)

        # 2. Commit Core-Valence correction (Stage 3.0)
        cv_res = CVCorrectionResult(
            e_total_fc=-76.427600,
            e_total_ae=-76.471200,
            delta_e_cv_hartree=-0.043600,
            delta_e_cv_kcal_mol=-27.3594,
            basis_set="aug-cc-pwCVQZ",
            node_id=node_id,
        )
        commit_cv_to_hdf5(h5_file, cv_res)

        # 3. Commit Relativistic & SOC correction (Stage 4.0)
        rel_res = RelCorrectionResult(
            e_total_non_rel=-76.427600,
            e_total_rel=-76.482100,
            e_total_soc=-76.483100,
            delta_e_rel_hartree=-0.054500,
            delta_e_rel_kcal_mol=-34.1992,
            delta_e_soc_hartree=-0.001000,
            delta_e_soc_kcal_mol=-0.6275,
            delta_e_total_rel_hartree=-0.055500,
            delta_e_total_rel_kcal_mol=-34.8267,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            has_heavy_elements=True,
            is_open_shell=True,
            node_id=node_id,
        )
        commit_rel_to_hdf5(h5_file, rel_res)

        # 4. Write ZPVE to HDF5
        zpve_val = 0.021340
        with h5py.File(h5_file, "a") as f:
            zpve_grp = f.require_group("zpve_corrections").require_group(node_id)
            zpve_grp.create_dataset("zpve_hartree", data=zpve_val)

        # 5. Execute Stage 5.0 Composite Aggregator
        aggregator = CompositeAggregator()
        records = aggregator.sweep_hdf5(h5_file)

        assert len(records) == 1
        rec = records[0]
        assert rec.node_id == node_id
        assert math.isclose(rec.e_scf_cbs, -76.062400, rel_tol=1e-7)
        assert math.isclose(rec.e_corr_cbs, -0.365200, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_cv, -0.043600, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_rel, -0.054500, rel_tol=1e-7)
        assert math.isclose(rec.delta_e_soc, -0.001000, rel_tol=1e-7)
        assert math.isclose(rec.zpve, zpve_val, rel_tol=1e-7)

        # Mathematical Invariant:
        # E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE
        expected_total = (
            -76.062400 + (-0.365200) + (-0.043600) + (-0.054500) + (-0.001000) + zpve_val
        )
        assert math.isclose(rec.e_total_hartree, expected_total, rel_tol=1e-7)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_engine\cochem_bench_rel.py ---
#!/usr/bin/env python3
r"""Stage 4.0: Scalar Relativistic & Spin-Orbit Coupling (SOC) Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_rel / cochem_bench.bench_engine.cochem_bench_rel
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. RelativisticHamiltonianInjector: Modifies ORCA 6.1.1 inputs to utilize exact
   two-component (X2C) matrices and relativistically re-contracted basis sets
   (e.g., def2-TZVPP -> x2c-TZVPPall-s, cc-pVTZ -> cc-pVTZ-DK / cc-pVTZ-X2C), and inspects
   elemental composition via the Mendeleev library.
2. X2CHandler & Divergence Remediator: Divergence safety net that detects SCF/DIIS
   instability in the X2C Hamiltonian cycle. Provides fail-fast error trapping as well as
   automated input rewriting for Douglas-Kroll-Hess (! DKH2) remediation and restart.
3. SpinOrbitCoupler: For open-shell radicals flagged in Stage 1.0 (REQUIRES_UHF /
   multiplicity > 1), automatically injects the SOMF(1X) (Spin-Orbit Mean-Field)
   operator to extract the asymmetric spin-orbit splitting delta from Two-Component and
   Non-Relativistic traces.
4. DeltaRelExtractor: Extracts electronic energies from authentic ORCA standard
   outputs, derives Delta_E_rel = E_Total^(Rel) - E_Total^(Non-Rel) and Delta_E_SOC,
   and converts all energetic shifts to kcal/mol.
5. EphemeralScratchPurge: Tripartite scratch workspace manager executing sweeps
   and unlinking of .gbw, .tmp, and intermediate files with CUDA_VISIBLE_DEVICES="" isolation.
6. HDF5 Persistence: Commits computed relativistic corrections directly to landscape.h5
   with filelock.FileLock thread-safety under rel_corrections/{node_id}.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
"""

from __future__ import annotations

import datetime
import math
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants & System Defaults
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063

# Default Atomic Number Threshold for Relativistic Corrections (4th Period+: K and beyond)
DEFAULT_RELATIVISTIC_Z_THRESHOLD: int = 19


# ==============================================================================
# Custom Domain Exceptions
# ==============================================================================

class X2CDivergenceError(RuntimeError):
    """Raised when the X2C relativistic Hamiltonian diverges during the SCF cycle."""


class RelativisticExecutionError(RuntimeError):
    """Raised when a relativistic quantum chemistry calculation fails during execution."""


class RelativisticInputError(ValueError):
    """Raised when invalid inputs or parameters are provided to the relativistic engine."""


# ==============================================================================
# Data Models
# ==============================================================================

class RelCorrectionResult(BaseModel):
    """Structured result model for Stage 4.0 Relativistic and Spin-Orbit Corrections."""
    e_total_non_rel: float = Field(description="Non-relativistic baseline electronic energy in Hartree")
    e_total_rel: float = Field(description="Scalar relativistic (X2C/DKH2) electronic energy in Hartree")
    e_total_soc: Optional[float] = Field(default=None, description="Spin-orbit corrected total energy in Hartree")
    delta_e_rel_hartree: float = Field(description="Scalar relativistic correction delta (Rel - NonRel) in Hartree")
    delta_e_rel_kcal_mol: float = Field(description="Scalar relativistic correction delta in kcal/mol")
    delta_e_soc_hartree: float = Field(default=0.0, description="Spin-orbit coupling correction delta in Hartree")
    delta_e_soc_kcal_mol: float = Field(default=0.0, description="Spin-orbit coupling correction delta in kcal/mol")
    delta_e_total_rel_hartree: float = Field(description="Total relativistic correction delta (Scalar + SOC) in Hartree")
    delta_e_total_rel_kcal_mol: float = Field(description="Total relativistic correction delta in kcal/mol")
    basis_set: str = Field(description="Original non-relativistic basis set name")
    rel_basis_set: str = Field(description="Relativistically re-contracted basis set name")
    method: str = Field(default="DLPNO-CCSD(T)", description="High-level quantum chemistry method")
    hamiltonian: str = Field(default="X2C", description="Relativistic Hamiltonian used (Exact Two-Component or DKH2)")
    has_heavy_elements: bool = Field(default=True, description="True if molecule contains heavy elements (Z >= 19)")
    is_open_shell: bool = Field(default=False, description="True if radical or open-shell system requiring SOC")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional provenance or execution metadata")


# ==============================================================================
# 1. RelativisticHamiltonianInjector
# ==============================================================================

class RelativisticHamiltonianInjector:
    """Modifies ORCA inputs to utilize exact two-component (X2C) matrices and relativistically re-contracted basis sets."""

    # Exact basis set re-contraction mapping table for X2C
    RECONTRACTION_MAP_X2C: Dict[str, str] = {
        # Karlsruhe def2 family
        "def2-svp": "x2c-SVPall-s",
        "def2-sv(p)": "x2c-SVPall-s",
        "def2-tzvp": "x2c-TZVPall-s",
        "def2-tzvpd": "x2c-TZVPDall-s",
        "def2-tzvpp": "x2c-TZVPPall-s",
        "def2-tzvppd": "x2c-TZVPPDall-s",
        "def2-qzvp": "x2c-QZVPall-s",
        "def2-qzvpd": "x2c-QZVPDall-s",
        "def2-qzvpp": "x2c-QZVPPall-s",
        "def2-qzvppd": "x2c-QZVPPDall-s",
        # Dunning cc-pVnZ family
        "cc-pvdz": "cc-pVDZ-X2C",
        "cc-pvtz": "cc-pVTZ-X2C",
        "cc-pvqz": "cc-pVQZ-X2C",
        "cc-pv5z": "cc-pV5Z-X2C",
        "aug-cc-pvdz": "aug-cc-pVDZ-X2C",
        "aug-cc-pvtz": "aug-cc-pVTZ-X2C",
        "aug-cc-pvqz": "aug-cc-pVQZ-X2C",
        "aug-cc-pv5z": "aug-cc-pV5Z-X2C",
        # Core-polarized cc-pCVnZ family
        "cc-pcvdz": "cc-pCVDZ-X2C",
        "cc-pcvtz": "cc-pCVTZ-X2C",
        "cc-pcvqz": "cc-pCVQZ-X2C",
        "aug-cc-pcvdz": "aug-cc-pCVDZ-X2C",
        "aug-cc-pcvtz": "aug-cc-pCVTZ-X2C",
        "aug-cc-pcvqz": "aug-cc-pCVQZ-X2C",
        "aug-cc-pwcvtz": "aug-cc-pwCVTZ-X2C",
        "aug-cc-pwcvqz": "aug-cc-pwCVQZ-X2C",
        # ANO family (ANO-RCC is natively relativistic)
        "ano-rcc": "ano-rcc",
        "ano-rcc-dzp": "ano-rcc-DZP",
        "ano-rcc-tzp": "ano-rcc-TZP",
        "ano-rcc-qzp": "ano-rcc-QZP",
        "ano-pvdz": "ano-rcc-pVDZ",
        "ano-pvtz": "ano-rcc-pVTZ",
        "ano-pvqz": "ano-rcc-pVQZ",
    }

    # Re-contraction mapping for DKH2
    RECONTRACTION_MAP_DK: Dict[str, str] = {
        # Karlsruhe def2 family
        "def2-svp": "x2c-SVPall-s",
        "def2-sv(p)": "x2c-SVPall-s",
        "def2-tzvp": "x2c-TZVPall-s",
        "def2-tzvpd": "x2c-TZVPDall-s",
        "def2-tzvpp": "x2c-TZVPPall-s",
        "def2-tzvppd": "x2c-TZVPPDall-s",
        "def2-qzvp": "x2c-QZVPall-s",
        "def2-qzvpd": "x2c-QZVPDall-s",
        "def2-qzvpp": "x2c-QZVPPall-s",
        "def2-qzvppd": "x2c-QZVPPDall-s",
        # Dunning cc-pVnZ-DK family
        "cc-pvdz": "cc-pVDZ-DK",
        "cc-pvtz": "cc-pVTZ-DK",
        "cc-pvqz": "cc-pVQZ-DK",
        "cc-pv5z": "cc-pV5Z-DK",
        "aug-cc-pvdz": "aug-cc-pVDZ-DK",
        "aug-cc-pvtz": "aug-cc-pVTZ-DK",
        "aug-cc-pvqz": "aug-cc-pVQZ-DK",
        "aug-cc-pv5z": "aug-cc-pV5Z-DK",
        "cc-pcvdz": "cc-pCVDZ-DK",
        "cc-pcvtz": "cc-pCVTZ-DK",
        "cc-pcvqz": "cc-pCVQZ-DK",
        "aug-cc-pcvdz": "aug-cc-pCVDZ-DK",
        "aug-cc-pcvtz": "aug-cc-pCVTZ-DK",
        "aug-cc-pcvqz": "aug-cc-pCVQZ-DK",
        "aug-cc-pwcvtz": "aug-cc-pwCVTZ-DK",
        "aug-cc-pwcvqz": "aug-cc-pwCVQZ-DK",
        # ANO family
        "ano-rcc": "ano-rcc",
        "ano-rcc-dzp": "ano-rcc-DZP",
        "ano-rcc-tzp": "ano-rcc-TZP",
        "ano-rcc-qzp": "ano-rcc-QZP",
    }

    # Backward compatibility alias
    RECONTRACTION_MAP = RECONTRACTION_MAP_X2C

    @classmethod
    def map_relativistic_basis_set(
        cls,
        basis_set: str,
        hamiltonian: str = "X2C",
        use_dk: bool = False,
    ) -> str:
        """Maps standard non-relativistic basis sets to relativistically re-contracted X2C/DK variants."""
        b_clean = basis_set.strip()
        b_lower = b_clean.lower()
        is_dk = use_dk or ("dk" in hamiltonian.lower())

        if is_dk:
            if b_lower in cls.RECONTRACTION_MAP_DK:
                return cls.RECONTRACTION_MAP_DK[b_lower]
        else:
            if b_lower in cls.RECONTRACTION_MAP_X2C:
                return cls.RECONTRACTION_MAP_X2C[b_lower]

        # If already designated as an X2C or relativistically contracted basis set, return cleaned
        if "x2c" in b_lower or "-x2c" in b_lower or "-dk" in b_lower or "ano-rcc" in b_lower:
            return b_clean

        # Algorithmic fallback for Karlsruhe def2 variants: replace def2- with x2c- and append all-s
        if b_lower.startswith("def2-"):
            suffix = b_clean[5:]
            if not suffix.endswith("all-s") and not suffix.endswith("all"):
                return f"x2c-{suffix}all-s"
            return f"x2c-{suffix}"

        # Algorithmic fallback for Dunning correlation consistent sets
        if "cc-pv" in b_lower:
            if is_dk:
                return f"{b_clean}-DK"
            return f"{b_clean}-X2C"

        return b_clean

    @classmethod
    def map_basis_dk(cls, basis_set: str) -> str:
        """Convenience method mapping basis set for Douglas-Kroll-Hess (DKH2)."""
        return cls.map_relativistic_basis_set(basis_set, hamiltonian="DKH2", use_dk=True)

    @staticmethod
    def inspect_heavy_elements(
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        relativistic_z_threshold: int = DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    ) -> Dict[str, Any]:
        """Inspects elemental composition using Mendeleev to determine atomic numbers, mass, and relativistic need."""
        total_mass = 0.0
        total_electrons = 0
        max_z = 0
        heavy_elements: List[str] = []
        elements_present: List[str] = []

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            z = int(elem_data.atomic_number)
            mass = float(elem_data.mass)

            total_mass += mass
            total_electrons += z
            if z > max_z:
                max_z = z
            if sym not in elements_present:
                elements_present.append(sym)
            if z >= relativistic_z_threshold and sym not in heavy_elements:
                heavy_elements.append(sym)

        has_heavy = len(heavy_elements) > 0

        return {
            "has_heavy_elements": has_heavy,
            "heavy_elements": heavy_elements,
            "max_z": max_z,
            "total_electrons": total_electrons,
            "total_mass": total_mass,
            "elements": elements_present,
        }

    def inject_relativistic_hamiltonian(
        self,
        input_text: str,
        basis_set: Optional[str] = None,
        force_x2c: bool = True,
        hamiltonian: str = "X2C",
    ) -> str:
        """Modifies an existing ORCA input text to utilize relativistic Hamiltonian and re-contracted basis set."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        header_processed = False
        target_hamiltonian = hamiltonian.upper()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") and not header_processed:
                tokens = stripped.split()
                new_tokens: List[str] = []

                for token in tokens:
                    # Check if token is a basis set needing recontraction
                    t_lower = token.lower()
                    if basis_set and t_lower == basis_set.lower():
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    elif t_lower in self.RECONTRACTION_MAP_X2C or t_lower in self.RECONTRACTION_MAP_DK:
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    elif t_lower.startswith("def2-") or (("cc-pv" in t_lower) and not t_lower.endswith("-x2c") and not t_lower.endswith("-dk")):
                        new_tokens.append(self.map_relativistic_basis_set(token, hamiltonian=target_hamiltonian))
                    else:
                        new_tokens.append(token)

                # Inject Hamiltonian keyword
                if force_x2c:
                    has_hamiltonian = any(t.upper() in ("X2C", "DKH", "DKH2") for t in new_tokens)
                    if not has_hamiltonian:
                        new_tokens.insert(2 if len(new_tokens) >= 2 else 1, target_hamiltonian)

                new_lines.append(" ".join(new_tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed and force_x2c:
            new_lines.insert(0, f"! {target_hamiltonian}")

        return "\n".join(new_lines) + "\n"

    def generate_input_decks(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        method: str = "DLPNO-CCSD(T)",
        base_basis: str = "def2-TZVPP",
        charge: int = 0,
        mult: int = 1,
        requires_uhf: bool = False,
        is_radical: bool = False,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        ram_safety_fraction: float = 0.75,
        output_dir: Optional[Union[str, Path]] = None,
        hamiltonian: str = "X2C",
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for non-relativistic baseline and relativistic jobs."""
        elem_info = self.inspect_heavy_elements(coords)
        rel_basis = self.map_relativistic_basis_set(base_basis, hamiltonian=hamiltonian)

        # Calculate %maxcore per MPI thread
        available_mb = float(node_max_gb) * 1024.0 * float(ram_safety_fraction)
        per_thread_mb = max(250, int(available_mb / max(1, int(nprocs))))
        max_allowed_mb = int((float(node_max_gb) * 1024.0) / max(1, int(nprocs)))
        maxcore_mb = min(per_thread_mb, max_allowed_mb)

        # 1. Non-relativistic baseline deck
        non_rel_input = self._build_input_string(
            coords=coords,
            method=method,
            basis=base_basis,
            is_relativistic=False,
            charge=charge,
            mult=mult,
            tight_scf=tight_scf,
            defgrid=defgrid,
            maxcore_mb=maxcore_mb,
            nprocs=nprocs,
        )

        # 2. Relativistic deck
        is_open_shell = SpinOrbitCoupler.is_open_shell(
            mult=mult, requires_uhf=requires_uhf, is_radical=is_radical
        )
        rel_input = self._build_input_string(
            coords=coords,
            method=method,
            basis=rel_basis,
            is_relativistic=True,
            charge=charge,
            mult=mult,
            tight_scf=tight_scf,
            defgrid=defgrid,
            maxcore_mb=maxcore_mb,
            nprocs=nprocs,
            inject_somf=is_open_shell,
            hamiltonian=hamiltonian,
        )

        decks = {
            "non_rel_input": non_rel_input,
            "rel_input": rel_input,
            "basis_set": base_basis,
            "rel_basis_set": rel_basis,
            "method": method,
            "has_heavy_elements": elem_info["has_heavy_elements"],
            "is_open_shell": is_open_shell,
            "maxcore_mb": maxcore_mb,
            "nprocs": nprocs,
            "charge": charge,
            "mult": mult,
            "hamiltonian": hamiltonian,
            "element_info": elem_info,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / "orca_non_rel.inp").write_text(non_rel_input, encoding="utf-8")
            (out_path / "orca_rel.inp").write_text(rel_input, encoding="utf-8")

        return decks

    def _build_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        method: str,
        basis: str,
        is_relativistic: bool,
        charge: int,
        mult: int,
        tight_scf: bool,
        defgrid: str,
        maxcore_mb: int,
        nprocs: int,
        inject_somf: bool = False,
        hamiltonian: str = "X2C",
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck string."""
        keywords = ["!", method, basis]
        if is_relativistic:
            keywords.insert(2, hamiltonian.upper())
        if inject_somf:
            keywords.append("SOMF(1X)")
        if tight_scf:
            keywords.append("TightSCF")
        if defgrid:
            keywords.append(defgrid)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if nprocs > 1:
            lines.append(f"%pal nprocs {nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)


# ==============================================================================
# 2. X2CHandler & Divergence Remediator
# ==============================================================================

class X2CHandler:
    """Detects SCF/DIIS instability in the X2C Hamiltonian cycle and manages divergence remediation."""

    # Error and divergence signatures emitted by ORCA during relativistic SCF failures
    DIVERGENCE_SIGNATURES: List[str] = [
        r"SCF NOT CONVERGED",
        r"Divergence in X2C",
        r"X2C transformation failed",
        r"DIIS failure in X2C",
        r"DIIS failure",
        r"ENERGY DID NOT CONVERGE",
        r"Calculation did not converge",
        r"SCF CONVERGENCE FAILED",
        r"Matrix is not positive definite",
        r"Error in X2C diagonalization",
        r"Diagonalization failed",
    ]

    def detect_divergence(
        self,
        stdout_text: str,
        stderr_text: str = "",
        returncode: int = 0,
    ) -> bool:
        """Detects whether the X2C relativistic Hamiltonian cycle diverged or failed to converge."""
        combined_text = f"{stdout_text}\n{stderr_text}"

        for sig in self.DIVERGENCE_SIGNATURES:
            if re.search(sig, combined_text, re.IGNORECASE):
                return True

        if returncode != 0 and "FINAL SINGLE POINT ENERGY" not in stdout_text:
            return True

        return False

    def validate_convergence(
        self,
        stdout_text: str,
        stderr_text: str = "",
        returncode: int = 0,
    ) -> float:
        """Validates convergence of relativistic calculation and extracts final single-point energy float."""
        if self.detect_divergence(stdout_text, stderr_text, returncode):
            raise X2CDivergenceError(
                "X2C relativistic Hamiltonian diverged or failed during the SCF cycle. "
                "In accordance with CoChem-BENCH Stage 4.0 specifications, fallback to DKH2 "
                "must be explicitly managed via remediation to maintain uniform methodology."
            )

        if returncode != 0:
            raise RelativisticExecutionError(
                f"Relativistic ORCA calculation failed with returncode {returncode}.\n"
                f"Stderr: {stderr_text[:500]}"
            )

        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")

        return float(match.group(1))

    @staticmethod
    def remediate_to_dkh2(input_text: str) -> str:
        """Rewrites an X2C input deck to use Douglas-Kroll-Hess (DKH2)."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!"):
                tokens = stripped.split()
                new_tokens: List[str] = []
                for t in tokens:
                    if t.upper() == "X2C":
                        new_tokens.append("DKH2")
                    elif t.lower().endswith("-x2c"):
                        new_tokens.append(t[:-4] + "-DK")
                    else:
                        new_tokens.append(t)
                if not any(t.upper() in ("DKH", "DKH2") for t in new_tokens):
                    new_tokens.insert(2 if len(new_tokens) >= 2 else 1, "DKH2")
                new_lines.append(" ".join(new_tokens))
            else:
                new_lines.append(line)
        return "\n".join(new_lines) + "\n"


class X2CDivergenceRemediator:
    """Remediates X2C divergence by rewriting input for DKH2 and restarting."""

    def __init__(self) -> None:
        self.handler = X2CHandler()

    def remediate_to_dkh2(self, input_text: str) -> str:
        """Rewrites X2C input for Douglas-Kroll-Hess (DKH2)."""
        return X2CHandler.remediate_to_dkh2(input_text)

    def execute_with_remediation(
        self,
        input_deck: str,
        runner_fn: Callable[..., Tuple[str, str, int]],
        scratch_dir: Optional[Union[str, Path]] = None,
    ) -> Tuple[str, str, int, str]:
        """Executes calculation, intercepting X2C divergence, rewriting for DKH2, and restarting."""
        stdout, stderr, code = runner_fn(input_deck, scratch_dir=scratch_dir)
        hamiltonian_used = "X2C"

        if self.handler.detect_divergence(stdout, stderr, code):
            # Rewrites input deck for Douglas-Kroll-Hess (DKH2) and restarts
            dkh2_deck = self.remediate_to_dkh2(input_deck)
            stdout, stderr, code = runner_fn(dkh2_deck, scratch_dir=scratch_dir)
            hamiltonian_used = "DKH2"

        return stdout, stderr, code, hamiltonian_used


# ==============================================================================
# 3. SpinOrbitCoupler
# ==============================================================================

class SpinOrbitCoupler:
    """Manages open-shell radical detection, SOMF(1X) operator injection, and spin-orbit coupling arithmetic."""

    @staticmethod
    def is_open_shell(
        mult: int = 1,
        requires_uhf: bool = False,
        is_radical: bool = False,
    ) -> bool:
        """Evaluates whether the molecular state is an open-shell radical requiring spin-orbit coupling."""
        return bool(mult > 1 or requires_uhf or is_radical)

    @staticmethod
    def inject_somf_operator(input_text: str) -> str:
        """Injects the SOMF(1X) (Spin-Orbit Mean-Field) operator keyword into the ORCA input deck."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        header_processed = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") and not header_processed:
                tokens = stripped.split()
                if "SOMF(1X)" not in tokens:
                    tokens.append("SOMF(1X)")
                new_lines.append(" ".join(tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed:
            new_lines.insert(0, "! SOMF(1X)")

        return "\n".join(new_lines) + "\n"

    @staticmethod
    def parse_somf_traces(stdout_text: str) -> Optional[Dict[str, float]]:
        """Parses electronic energy shift from SOMF(1X) property block:
        searches for the exact literal strings 'SOMF(1X) Two-Component Trace'
        and 'SOMF(1X) Non-Relativistic Trace', extracts trailing floats and computes
        their difference to obtain Delta_E_SOC = Trace_2C - Trace_nonrel.
        """
        match_2c = re.search(
            r"SOMF\(1X\)\s+Two-Component\s+Trace\s+\.\.\.\s+(-?\d+\.\d+)",
            stdout_text,
            re.IGNORECASE,
        )
        match_nonrel = re.search(
            r"SOMF\(1X\)\s+Non-Relativistic\s+Trace\s+\.\.\.\s+(-?\d+\.\d+)",
            stdout_text,
            re.IGNORECASE,
        )
        if match_2c and match_nonrel:
            trace_2c = float(match_2c.group(1))
            trace_nonrel = float(match_nonrel.group(1))
            return {
                "trace_2c": trace_2c,
                "trace_nonrel": trace_nonrel,
                "delta_e_soc": float(trace_2c - trace_nonrel),
            }
        return None

    @classmethod
    def parse_soc_energy_from_stdout(cls, stdout_text: str) -> Optional[float]:
        """Parses spin-orbit coupling expectation value or shift from ORCA standard output."""
        traces = cls.parse_somf_traces(stdout_text)
        if traces is not None:
            return traces["delta_e_soc"]

        # Pattern 1: SOMF(1X) Energy Shift
        match_somf = re.search(r"SOMF\(1X\)\s+Energy\s+Shift\s+\.\.\.\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_somf:
            return float(match_somf.group(1))

        # Pattern 2: 2C-SOC expectation value
        match_2c = re.search(r"Two-component\s+2C-SOC\s+expectation\s+value\s+\.\.\.\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_2c:
            return float(match_2c.group(1))

        # Pattern 3: Explicit SPIN-ORBIT COUPLING ENERGY
        match_soc = re.search(r"SPIN-ORBIT\s+COUPLING\s+ENERGY\s+(-?\d+\.\d+)", stdout_text, re.IGNORECASE)
        if match_soc:
            return float(match_soc.group(1))

        return None

    @staticmethod
    def derive_soc_correction(
        e_total_rel: float,
        e_total_soc: Optional[float] = None,
        soc_trace_hartree: Optional[float] = None,
        trace_2c: Optional[float] = None,
        trace_nonrel: Optional[float] = None,
    ) -> float:
        """Derives the spin-orbit coupling energy correction Delta E_SOC in Hartree."""
        if trace_2c is not None and trace_nonrel is not None:
            return float(trace_2c - trace_nonrel)

        if soc_trace_hartree is not None:
            return float(soc_trace_hartree)

        if e_total_soc is not None:
            return float(e_total_soc - e_total_rel)

        return 0.0


# ==============================================================================
# 4. DeltaRelExtractor
# ==============================================================================

class DeltaRelExtractor:
    """Extracts electronic energies from standard ORCA outputs and derives relativistic correction deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(match.group(1))

    @staticmethod
    def extract_delta(
        e_total_non_rel: float,
        e_total_rel: float,
        e_total_soc: Optional[float] = None,
        soc_trace_hartree: Optional[float] = None,
        basis_set: str = "",
        rel_basis_set: str = "",
        method: str = "DLPNO-CCSD(T)",
        hamiltonian: str = "X2C",
        has_heavy_elements: bool = True,
        is_open_shell: bool = False,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelCorrectionResult:
        """Mathematically derives Delta_E_rel = E_Total^(Rel) - E_Total^(NonRel) and Delta_E_SOC."""
        delta_rel_hartree = float(e_total_rel - e_total_non_rel)
        delta_rel_kcal = float(delta_rel_hartree * HARTREE_TO_KCAL_MOL)

        coupler = SpinOrbitCoupler()
        delta_soc_hartree = coupler.derive_soc_correction(
            e_total_rel=e_total_rel,
            e_total_soc=e_total_soc,
            soc_trace_hartree=soc_trace_hartree,
        )
        delta_soc_kcal = float(delta_soc_hartree * HARTREE_TO_KCAL_MOL)

        delta_total_hartree = float(delta_rel_hartree + delta_soc_hartree)
        delta_total_kcal = float(delta_total_hartree * HARTREE_TO_KCAL_MOL)

        return RelCorrectionResult(
            e_total_non_rel=float(e_total_non_rel),
            e_total_rel=float(e_total_rel),
            e_total_soc=float(e_total_soc) if e_total_soc is not None else None,
            delta_e_rel_hartree=delta_rel_hartree,
            delta_e_rel_kcal_mol=delta_rel_kcal,
            delta_e_soc_hartree=delta_soc_hartree,
            delta_e_soc_kcal_mol=delta_soc_kcal,
            delta_e_total_rel_hartree=delta_total_hartree,
            delta_e_total_rel_kcal_mol=delta_total_kcal,
            basis_set=basis_set,
            rel_basis_set=rel_basis_set,
            method=method,
            hamiltonian=hamiltonian,
            has_heavy_elements=has_heavy_elements,
            is_open_shell=is_open_shell,
            node_id=node_id,
            metadata=metadata or {},
        )

    def extract_from_outputs(
        self,
        stdout_non_rel: str,
        stdout_rel: str,
        stdout_soc: Optional[str] = None,
        basis_set: str = "",
        rel_basis_set: str = "",
        method: str = "DLPNO-CCSD(T)",
        hamiltonian: str = "X2C",
        has_heavy_elements: bool = True,
        is_open_shell: bool = False,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RelCorrectionResult:
        """Parses energies directly from standard output texts and computes full relativistic correction."""
        e_non_rel = self.parse_final_energy_from_stdout(stdout_non_rel)

        # Validate relativistic calculation convergence
        handler = X2CHandler()
        e_rel = handler.validate_convergence(stdout_rel)

        e_soc: Optional[float] = None
        soc_trace: Optional[float] = None
        if stdout_soc:
            soc_trace = SpinOrbitCoupler.parse_soc_energy_from_stdout(stdout_soc)
            try:
                e_soc = self.parse_final_energy_from_stdout(stdout_soc)
            except ValueError:
                e_soc = None
            is_open_shell = True

        return self.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=e_soc,
            soc_trace_hartree=soc_trace,
            basis_set=basis_set,
            rel_basis_set=rel_basis_set,
            method=method,
            hamiltonian=hamiltonian,
            has_heavy_elements=has_heavy_elements,
            is_open_shell=is_open_shell,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 5. EphemeralScratchPurge & Air-Gap Isolation
# ==============================================================================

class EphemeralScratchPurge:
    """Manages tripartite scratch workspace creation and sweeps intermediate scratch files."""

    @staticmethod
    def create_scratch_dir(base_artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
        """Creates a dedicated UUID-scoped scratch directory."""
        if base_artifacts_dir:
            base_dir = Path(base_artifacts_dir)
        else:
            base_env = os.environ.get(
                "COCHEM_ARTIFACTS_DIR",
                os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
            )
            base_dir = Path(base_env)

        scratch_dir = base_dir / "BENCH_Workspace" / "Scratch" / f"job_{uuid.uuid4()}"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    @staticmethod
    def get_isolated_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Injects accelerator isolation (CUDA_VISIBLE_DEVICES="") into execution environment."""
        env = dict(base_env) if base_env is not None else dict(os.environ)
        env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    @staticmethod
    def purge_scratch_dir(
        scratch_dir: Union[str, Path],
        remove_dir: bool = True,
    ) -> Dict[str, Any]:
        """Sweeps and unlinks intermediate simulation files (.gbw, .tmp, .densities, etc.)."""
        scratch_path = Path(scratch_dir)
        if not scratch_path.exists():
            return {"status": "not_found", "purged_count": 0}

        purged_files: List[str] = []
        extensions_to_purge = [
            "*.gbw", "*.tmp", "*.densities", "*.bso", "*.prop",
            "*.core", "*.host", "*.ges", "*.int", "*.uco",
        ]

        for ext in extensions_to_purge:
            for p in scratch_path.glob(ext):
                try:
                    p.unlink()
                    purged_files.append(p.name)
                except OSError:
                    pass

        if remove_dir:
            try:
                shutil.rmtree(str(scratch_path), ignore_errors=True)
            except OSError:
                pass

        return {
            "status": "purged",
            "purged_count": len(purged_files),
            "purged_files": purged_files,
        }


# ==============================================================================
# 6. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Dynamically resolves the target landscape.h5 path adhering strictly to COCHEM_ARTIFACTS_DIR."""
    if h5_path is not None:
        return Path(h5_path)
    base_env = os.environ.get(
        "COCHEM_ARTIFACTS_DIR",
        os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
    )
    return Path(base_env) / "BENCH_Workspace" / "landscape.h5"


def commit_rel_to_hdf5(
    h5_path: Union[str, Path],
    result: RelCorrectionResult,
    timeout: float = 120.0,
) -> Path:
    """Commits computed Relativistic and Spin-Orbit correction results atomically to landscape.h5."""
    target_path = resolve_hdf5_path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    node_group_name = result.node_id if result.node_id else "default_rel_node"

    with lock:
        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("rel_corrections")
            node_grp = root_grp.require_group(node_group_name)

            datasets = {
                "e_total_non_rel": result.e_total_non_rel,
                "e_total_rel": result.e_total_rel,
                "delta_e_rel_hartree": result.delta_e_rel_hartree,
                "delta_e_rel_kcal_mol": result.delta_e_rel_kcal_mol,
                "delta_e_soc_hartree": result.delta_e_soc_hartree,
                "delta_e_soc_kcal_mol": result.delta_e_soc_kcal_mol,
                "delta_e_total_rel_hartree": result.delta_e_total_rel_hartree,
                "delta_e_total_rel_kcal_mol": result.delta_e_total_rel_kcal_mol,
            }

            if result.e_total_soc is not None:
                datasets["e_total_soc"] = result.e_total_soc

            for ds_name, ds_val in datasets.items():
                if ds_name in node_grp:
                    del node_grp[ds_name]
                node_grp.create_dataset(ds_name, data=float(ds_val))

            node_grp.attrs["basis_set"] = result.basis_set
            node_grp.attrs["rel_basis_set"] = result.rel_basis_set
            node_grp.attrs["method"] = result.method
            node_grp.attrs["hamiltonian"] = result.hamiltonian
            node_grp.attrs["has_heavy_elements"] = bool(result.has_heavy_elements)
            node_grp.attrs["is_open_shell"] = bool(result.is_open_shell)
            node_grp.attrs["timestamp"] = result.timestamp
            node_grp.attrs["node_id"] = result.node_id

    return target_path


def read_rel_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Reads back computed Relativistic correction results from landscape.h5."""
    target_path = resolve_hdf5_path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    with lock:
        with h5py.File(target_path, "r") as f:
            if "rel_corrections" not in f:
                raise KeyError(f"Root group 'rel_corrections' not found in '{target_path}'")
            root_grp = f["rel_corrections"]
            if node_id not in root_grp:
                raise KeyError(f"Node '{node_id}' not found in 'rel_corrections'")
            node_grp = root_grp[node_id]

            data = {
                "e_total_non_rel": float(node_grp["e_total_non_rel"][()]),
                "e_total_rel": float(node_grp["e_total_rel"][()]),
                "delta_e_rel_hartree": float(node_grp["delta_e_rel_hartree"][()]),
                "delta_e_rel_kcal_mol": float(node_grp["delta_e_rel_kcal_mol"][()]),
                "delta_e_soc_hartree": float(node_grp.get("delta_e_soc_hartree", 0.0)[()]),
                "delta_e_soc_kcal_mol": float(node_grp.get("delta_e_soc_kcal_mol", 0.0)[()]),
                "delta_e_total_rel_hartree": float(node_grp.get("delta_e_total_rel_hartree", node_grp["delta_e_rel_hartree"])[()]),
                "delta_e_total_rel_kcal_mol": float(node_grp.get("delta_e_total_rel_kcal_mol", node_grp["delta_e_rel_kcal_mol"])[()]),
                "basis_set": str(node_grp.attrs.get("basis_set", "")),
                "rel_basis_set": str(node_grp.attrs.get("rel_basis_set", "")),
                "method": str(node_grp.attrs.get("method", "")),
                "hamiltonian": str(node_grp.attrs.get("hamiltonian", "X2C")),
                "has_heavy_elements": bool(node_grp.attrs.get("has_heavy_elements", True)),
                "is_open_shell": bool(node_grp.attrs.get("is_open_shell", False)),
                "timestamp": str(node_grp.attrs.get("timestamp", "")),
                "node_id": str(node_grp.attrs.get("node_id", "")),
            }

            if "e_total_soc" in node_grp:
                data["e_total_soc"] = float(node_grp["e_total_soc"][()])

            return data


def run_rel_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_total_non_rel: float,
    e_total_rel: float,
    e_total_soc: Optional[float] = None,
    base_basis: str = "def2-TZVPP",
    method: str = "DLPNO-CCSD(T)",
    charge: int = 0,
    mult: int = 1,
    requires_uhf: bool = False,
    is_radical: bool = False,
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
    hamiltonian: str = "X2C",
) -> RelCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 4.0 Relativistic and SOC Correction."""
    # 1. Map basis set and inspect elemental composition
    injector = RelativisticHamiltonianInjector()
    rel_basis = injector.map_relativistic_basis_set(base_basis, hamiltonian=hamiltonian)
    heavy_info = injector.inspect_heavy_elements(coords)

    # 2. Check open shell
    is_open_shell = SpinOrbitCoupler.is_open_shell(
        mult=mult, requires_uhf=requires_uhf, is_radical=is_radical
    )

    # 3. Extract delta and create result model
    extractor = DeltaRelExtractor()
    result = extractor.extract_delta(
        e_total_non_rel=e_total_non_rel,
        e_total_rel=e_total_rel,
        e_total_soc=e_total_soc,
        basis_set=base_basis,
        rel_basis_set=rel_basis,
        method=method,
        hamiltonian=hamiltonian,
        has_heavy_elements=heavy_info["has_heavy_elements"],
        is_open_shell=is_open_shell,
        node_id=node_id,
        metadata={"heavy_info": heavy_info},
    )

    # 4. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_rel_to_hdf5(h5_path=h5_path, result=result)

    return result

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.