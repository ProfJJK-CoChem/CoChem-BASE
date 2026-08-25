#!/usr/bin/env python3
r"""Stage 4.0: Scalar Relativistic & Spin-Orbit Coupling (SOC) Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_rel
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. RelativisticHamiltonianInjector: Modifies ORCA 6.1.1 inputs to utilize exact
   two-component (X2C) matrices and relativistically re-contracted basis sets
   (e.g., def2-TZVPP -> x2c-TZVPPall-s, cc-pVTZ -> cc-pVTZ-X2C), and inspects
   elemental composition via the Mendeleev library.
2. X2CHandler: Divergence safety net that detects SCF/DIIS instability in the
   X2C Hamiltonian cycle. Fails fast and explicitly raises an exception without
   falling back to DKH2, ensuring strictly uniform benchmark evaluations.
3. SpinOrbitCoupler: For open-shell radicals flagged in Stage 1.0 (REQUIRES_UHF /
   multiplicity > 1), automatically injects the SOMF(1X) (Spin-Orbit Mean-Field)
   operator to extract the asymmetric spin-orbit splitting delta.
4. DeltaRelExtractor: Extracts electronic energies from authentic ORCA standard
   outputs, derives Delta_E_rel = E_Total^(Rel) - E_Total^(Non-Rel) and Delta_E_SOC,
   and converts all energetic shifts to kcal/mol.
5. EphemeralScratchPurge: Tripartite scratch workspace manager executing sweeps
   and unlinking of .gbw, .tmp, and intermediate files.
6. HDF5 Persistence: Commits computed relativistic corrections directly to landscape.h5.

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
from typing import Any, Dict, List, Optional, Tuple, Union

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
    """Raised when the X2C relativistic Hamiltonian diverges during the SCF cycle.
    
    In accordance with CoChem-BENCH Stage 4.0 specifications, fallback to DKH2
    is strictly forbidden to ensure uniform benchmark evaluations.
    """


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
    e_total_rel: float = Field(description="Scalar relativistic (X2C) electronic energy in Hartree")
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
    hamiltonian: str = Field(default="X2C", description="Relativistic Hamiltonian used (Exact Two-Component)")
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
    RECONTRACTION_MAP: Dict[str, str] = {
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

    @classmethod
    def map_relativistic_basis_set(cls, basis_set: str) -> str:
        """Maps standard non-relativistic basis sets to relativistically re-contracted X2C variants."""
        b_clean = basis_set.strip()
        b_lower = b_clean.lower()

        # Check explicit mapping dictionary
        if b_lower in cls.RECONTRACTION_MAP:
            return cls.RECONTRACTION_MAP[b_lower]

        # If already designated as an X2C or relativistically contracted basis set, return cleaned
        if "x2c" in b_lower or "-x2c" in b_lower or "ano-rcc" in b_lower:
            return b_clean

        # Algorithmic fallback for Karlsruhe def2 variants
        if b_lower.startswith("def2-"):
            suffix = b_clean[5:]
            if not suffix.endswith("all-s") and not suffix.endswith("all"):
                return f"x2c-{suffix}all-s"
            return f"x2c-{suffix}"

        # Algorithmic fallback for Dunning correlation consistent sets
        if "cc-pv" in b_lower and not b_lower.endswith("-x2c"):
            return f"{b_clean}-X2C"

        return b_clean

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
    ) -> str:
        """Modifies an existing ORCA input text to utilize X2C Hamiltonian and re-contracted basis set."""
        lines = input_text.splitlines()
        new_lines: List[str] = []
        header_processed = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!") and not header_processed:
                tokens = stripped.split()
                new_tokens: List[str] = []

                for token in tokens:
                    # Check if token is a basis set needing recontraction
                    t_lower = token.lower()
                    if basis_set and t_lower == basis_set.lower():
                        new_tokens.append(self.map_relativistic_basis_set(token))
                    elif t_lower in self.RECONTRACTION_MAP:
                        new_tokens.append(self.map_relativistic_basis_set(token))
                    elif t_lower.startswith("def2-") or (("cc-pv" in t_lower) and not t_lower.endswith("-x2c")):
                        new_tokens.append(self.map_relativistic_basis_set(token))
                    else:
                        new_tokens.append(token)

                # Inject X2C keyword
                if force_x2c:
                    has_x2c = any(t.upper() == "X2C" for t in new_tokens)
                    if not has_x2c:
                        # Insert X2C after method or at position 1
                        new_tokens.insert(2 if len(new_tokens) >= 2 else 1, "X2C")

                new_lines.append(" ".join(new_tokens))
                header_processed = True
            else:
                new_lines.append(line)

        if not header_processed and force_x2c:
            new_lines.insert(0, "! X2C")

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
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for non-relativistic baseline and relativistic jobs."""
        elem_info = self.inspect_heavy_elements(coords)
        rel_basis = self.map_relativistic_basis_set(base_basis)

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

        # 2. Relativistic (X2C) deck
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
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck string."""
        keywords = ["!", method, basis]
        if is_relativistic:
            keywords.insert(2, "X2C")
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
# 2. X2CHandler
# ==============================================================================

class X2CHandler:
    """Detects SCF/DIIS instability in the X2C Hamiltonian cycle and enforces fail-fast error trapping."""

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
        """Validates convergence of relativistic X2C calculation and extracts final single-point energy float.
        
        Raises:
            X2CDivergenceError: If X2C SCF cycle diverged. Fallback to DKH2 is strictly forbidden.
            RelativisticExecutionError: If execution failed with non-zero returncode.
            ValueError: If FINAL SINGLE POINT ENERGY marker is absent.
        """
        if self.detect_divergence(stdout_text, stderr_text, returncode):
            raise X2CDivergenceError(
                "X2C relativistic Hamiltonian diverged or failed during the SCF cycle. "
                "In accordance with CoChem-BENCH Stage 4.0 specifications, fallback to DKH2 "
                "is strictly prohibited to maintain uniform benchmark methodology."
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
    def derive_soc_correction(
        e_total_rel: float,
        e_total_soc: Optional[float] = None,
        soc_trace_hartree: Optional[float] = None,
    ) -> float:
        """Derives the spin-orbit coupling energy correction Delta E_SOC in Hartree.
        
        Math:
            Delta E_SOC = E_Total^(SOC) - E_Total^(Rel)
            or Delta E_SOC = Tr(P, H+F)_2C - Tr(P, H+F)_non-rel
        """
        if soc_trace_hartree is not None:
            return float(soc_trace_hartree)

        if e_total_soc is not None:
            return float(e_total_soc - e_total_rel)

        return 0.0

    @staticmethod
    def parse_soc_energy_from_stdout(stdout_text: str) -> Optional[float]:
        """Parses spin-orbit coupling expectation value or shift from ORCA standard output."""
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
        basis_set: str = "",
        rel_basis_set: str = "",
        method: str = "DLPNO-CCSD(T)",
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
            hamiltonian="X2C",
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
        if stdout_soc:
            e_soc = self.parse_final_energy_from_stdout(stdout_soc)
            is_open_shell = True

        return self.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=e_soc,
            basis_set=basis_set,
            rel_basis_set=rel_basis_set,
            method=method,
            has_heavy_elements=has_heavy_elements,
            is_open_shell=is_open_shell,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 5. EphemeralScratchPurge
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

def commit_rel_to_hdf5(
    h5_path: Union[str, Path],
    result: RelCorrectionResult,
) -> None:
    """Commits computed Relativistic and Spin-Orbit correction results atomically to landscape.h5."""
    target_path = Path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    node_group_name = result.node_id if result.node_id else "default_rel_node"

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


def read_rel_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
) -> Dict[str, Any]:
    """Reads back computed Relativistic correction results from landscape.h5."""
    target_path = Path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    with h5py.File(target_path, "r") as f:
        root_grp = f["rel_corrections"]
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
) -> RelCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 4.0 Relativistic and SOC Correction."""
    # 1. Map basis set and inspect elemental composition
    injector = RelativisticHamiltonianInjector()
    rel_basis = injector.map_relativistic_basis_set(base_basis)
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
        has_heavy_elements=heavy_info["has_heavy_elements"],
        is_open_shell=is_open_shell,
        node_id=node_id,
        metadata={"heavy_info": heavy_info},
    )

    # 4. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_rel_to_hdf5(h5_path=h5_path, result=result)

    return result
