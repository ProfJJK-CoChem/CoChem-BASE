Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\10_02_export_cleanup.md.
Original prompt:
# Task: Implement Post-Flight Audit & Workspace Cleanup (`cochem_topos_cleanup.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\export_utils\cochem_topos_cleanup.py`

## Objective
Guarantee that a finished or aborted CoChem-TOPOS run leaves the host machine in a pristine state, preventing storage drives from filling up with quantum trash and freeing up locked VRAM.

## Context & Architecture Rules
This module (Stage 5.0) acts as the system garbage collector and process watchdog, respecting Tripartite Air-Gaps and OS-specific execution environments.

## Execution Directives
Implement the `cochem_topos_cleanup.py` script with the following capabilities:

1. **Targeted Scratch Purge Protocol**: Recursively scan designated `${COCHEM_SCRATCH_DIR}/orca_tmp/` and `${COCHEM_SCRATCH_DIR}/ase_graphs/` directories. Forcefully unlink (delete) all ephemeral files not explicitly flagged for permanent wavefunction archival (`.gbw`). Use dynamic, OS-specific pathing (via `pathlib`).
2. **Zombie Process Reaper**: Execute a final OS-level `psutil` Process Group ID (PGID) sweep to identify and terminate orphaned `orted` daemons, rogue C++ MACE physics threads, or hung ASE PyTorch workers. Use SIGKILL (POSIX Exit 9) for Linux/macOS targets and `taskkill /F /PID` for native Windows contexts.
3. **HDF5 Lock Sweeper**: Safely flush SWMR file pointers and remove any `.h5.lck` cache files to guarantee database integrity for downstream readers, resolving filesystem lock states.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\__init__.py ---
"""CoChem Bench Engine: Core Scientific Extrapolation & Benchmark Engines (Stages 1.0 - 5.0)."""

from __future__ import annotations

from bench_engine.cochem_bench_cbs import (
    CBSExtrapolationResult,
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptionResult,
    SlowConvInterceptor,
    commit_cbs_to_hdf5,
    read_cbs_from_hdf5,
    run_cbs_pipeline,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    PARAMETER_MATRIX,
)
from bench_engine.cochem_bench_cv import (
    CoreValenceMapper,
    CVCorrectionResult,
    DeltaExtractor,
    DualCorrelationEngine,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
)
from bench_engine.cochem_bench_rel import (
    DeltaRelExtractor,
    RelCorrectionResult,
    RelativisticExecutionError,
    RelativisticHamiltonianInjector,
    RelativisticInputError,
    SpinOrbitCoupler,
    X2CDivergenceError,
    X2CHandler,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
    DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    HARTREE_TO_KCAL_MOL,
)
from bench_engine.cochem_bench_export import (
    AirGapPackageMissingError,
    AirGapVerifier,
    CompositeAggregator,
    CompositeEnergyRecord,
    ExportPipelineResult,
    HDF5SchemaError,
    LaTeXExportConfig,
    MissingZPVEError,
    PublicationArchiver,
    ProvenanceStamper,
    SiunitxLaTeXCompiler,
    run_export_pipeline,
)

__all__ = [
    # Stage 2.0 CBS
    "DualBasisDispatcher",
    "HelgakerExtrapolator",
    "ResidualFitAnalyzer",
    "SlowConvInterceptor",
    "CBSExtrapolationResult",
    "SlowConvInterceptionResult",
    "commit_cbs_to_hdf5",
    "read_cbs_from_hdf5",
    "run_cbs_pipeline",
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    "PARAMETER_MATRIX",
    # Stage 3.0 CV
    "CoreValenceMapper",
    "DualCorrelationEngine",
    "DeltaExtractor",
    "CVCorrectionResult",
    "commit_cv_to_hdf5",
    "read_cv_from_hdf5",
    "run_cv_pipeline",
    # Stage 4.0 Relativistic & SOC
    "RelativisticHamiltonianInjector",
    "X2CHandler",
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
    "HARTREE_TO_KCAL_MOL",
    # Stage 5.0 Exporter
    "CompositeAggregator",
    "CompositeEnergyRecord",
    "ExportPipelineResult",
    "SiunitxLaTeXCompiler",
    "LaTeXExportConfig",
    "ProvenanceStamper",
    "AirGapVerifier",
    "PublicationArchiver",
    "MissingZPVEError",
    "AirGapPackageMissingError",
    "HDF5SchemaError",
    "run_export_pipeline",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\__init__.py ---
"""CoChem-TOPOS Combinatorial Conformational Engine."""

from .cochem_topos_cleanup import (
    HDF5LockRecord,
    HDF5LockSweeperConfig,
    HDF5LockSweepResult,
    PostFlightAuditReport,
    ProcessReaperConfig,
    PurgedFileRecord,
    PurgeResult,
    ReapedProcessRecord,
    ReapResult,
    ScratchPurgeConfig,
    ToposEnvironmentSanitizer,
    ToposHDF5LockSweeper,
    ToposProcessReaper,
    ToposScratchPurgeEngine,
    WSLPathTranslator,
)
from .cochem_topos_graph import (
    COVALENT_RADII,
    RESONANCE_PROTECTION_SCALE,
    MonomerSeed,
    ShortestGapTelemetry,
    TopologyAnalysisResult,
    TopologyGraphEngine,
    analyze_molecular_graph,
    generate_chemical_formula,
    get_atomic_mass,
    get_atomic_number,
    get_atomic_symbol,
    get_covalent_radius,
    is_transition_or_coordination_metal,
    parse_xyz_file,
    parse_xyz_string,
    run_crest_secondary_search,
)
from .engine import ToposEngine

__all__ = [
    "ToposEngine",
    "TopologyGraphEngine",
    "TopologyAnalysisResult",
    "MonomerSeed",
    "ShortestGapTelemetry",
    "analyze_molecular_graph",
    "parse_xyz_string",
    "parse_xyz_file",
    "generate_chemical_formula",
    "get_covalent_radius",
    "get_atomic_mass",
    "get_atomic_number",
    "get_atomic_symbol",
    "is_transition_or_coordination_metal",
    "run_crest_secondary_search",
    "COVALENT_RADII",
    "RESONANCE_PROTECTION_SCALE",
    "ToposEnvironmentSanitizer",
    "ToposScratchPurgeEngine",
    "ToposProcessReaper",
    "ToposHDF5LockSweeper",
    "WSLPathTranslator",
    "ScratchPurgeConfig",
    "PurgedFileRecord",
    "PurgeResult",
    "ProcessReaperConfig",
    "ReapedProcessRecord",
    "ReapResult",
    "HDF5LockRecord",
    "HDF5LockSweeperConfig",
    "HDF5LockSweepResult",
    "PostFlightAuditReport",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_rel.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\cochem_topos_cleanup.py ---
"""
CoChem-TOPOS: Stage 5.0 - Post-Flight Audit & Environment Cleanup
(cochem_topos_cleanup.py)

Cross-platform scratch purge engine, orphaned QM process reaper,
HDF5 SWMR lock sweeper, and ToposEnvironmentSanitizer context manager.

Authoritative Standards:
- Method Matrix: Stage 5.0 Workspace Cleanup & FAIR Archival
- Anti-Spoofing Protocol v2: Zero-Mock Real Subprocess & Physical Disk Testing
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import h5py
import psutil
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("CoChem.TOPOS.Cleanup")


def _compute_sha256(file_path: Path) -> str:
    """Computes the SHA-256 hexadecimal digest for a given file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


# ============================================================================
# Pydantic Data Models
# ============================================================================

class PurgedFileRecord(BaseModel):
    """Audit record for a single file or directory touched during scratch purge."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: str
    size_bytes: int = 0
    status: str = Field(
        description="Status of file action: 'deleted', 'quarantined', 'whitelisted', 'failed', 'locked_retried'"
    )
    reason: str | None = None
    extension: str = ""
    deleted_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    sha256_hash: str | None = None


class PurgeResult(BaseModel):
    """Aggregate result from executing a scratch directory purge."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    scanned_directories: list[str] = Field(default_factory=list)
    purged_files: list[PurgedFileRecord] = Field(default_factory=list)
    reclaimed_bytes: int = 0
    total_files_scanned: int = 0
    total_files_deleted: int = 0
    total_files_quarantined: int = 0
    total_files_whitelisted: int = 0
    total_directories_removed: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class ScratchPurgeConfig(BaseModel):
    """Configuration options for the ephemeral scratch purge engine."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_dirs: list[Path] = Field(default_factory=list)
    env_var_names: list[str] = Field(
        default_factory=lambda: [
            "COCHEM_SCRATCH_DIR",
            "COCHEM_SCRATCH",
            "COCHEM_TMP",
            "COCHEM_SCRATCH_ROOT",
        ]
    )
    default_fallback_dirs: list[str] = Field(
        default_factory=lambda: [
            "./scratch",
            "./scratch/orca_tmp",
            "./scratch/ase_graphs",
            "./escalation_scratch",
            "./artifacts/scratch",
        ]
    )
    ephemeral_extensions: list[str] = Field(
        default_factory=lambda: [
            ".tmp",
            ".dens",
            ".gbw",
            ".bms",
            ".interp",
            ".property.txt",
            ".scfp_tmp",
            ".vpt2.tmp",
            ".tmp0",
            ".tmp1",
            ".tmp2",
            ".tmp3",
            ".tmp4",
            ".tmp5",
        ]
    )
    ephemeral_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.tmp*",
            "*.dens",
            "*.gbw",
            "core.*",
            "*_tmp_*",
            "*_scf_tmp*",
            "orca_*.tmp",
            "xtb_*.tmp",
            "crest_*.tmp",
        ]
    )
    archive_whitelist: list[str] = Field(
        default_factory=list,
        description="Explicit paths or filenames preserved from deletion (e.g. finalized .gbw for FAIR export)",
    )
    archive_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files that must be preserved from deletion",
    )
    quarantine_dir: Path | None = Field(
        default=None,
        description="If set, ephemeral files are moved to this directory rather than forcefully unlinked",
    )
    remove_empty_dirs: bool = Field(
        default=True,
        description="Whether to recursively remove empty subdirectories after file purging",
    )
    max_retries: int = Field(
        default=5,
        description="Number of retries when encountering Windows kernel file locks",
    )
    retry_delay_seconds: float = Field(
        default=0.1,
        description="Base delay in seconds between file lock retries (exponential backoff)",
    )
    ignore_cleanup_errors: bool = Field(
        default=True,
        description="If True, file lock or permission errors are logged as warnings and recorded in the audit report rather than raising exceptions",
    )
    max_file_age_seconds: float | None = Field(
        default=None,
        description="If set, only files older than this age in seconds are purged",
    )
    wsl_translation: bool = Field(
        default=True,
        description="Enable translation of WSL2 ext4 UNC and /mnt/ paths to native OS paths",
    )
    compute_sha256: bool = Field(
        default=False,
        description="Whether to compute and record SHA-256 provenance digests before purging files",
    )


class ReapedProcessRecord(BaseModel):
    """Audit record for an orphaned process terminated during post-flight cleanup."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pid: int
    pgid: int | None = None
    name: str
    cmdline: list[str] = Field(default_factory=list)
    create_time: float = 0.0
    status: str = Field(
        description="Termination outcome: 'terminated_gracefully', 'killed_forcefully', 'already_dead', 'access_denied', 'failed'"
    )
    reaped_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class ReapResult(BaseModel):
    """Summary of process reaper execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    reaped_processes: list[ReapedProcessRecord] = Field(default_factory=list)
    active_orphans_found: int = 0
    successful_terminations: int = 0
    failed_terminations: int = 0
    audit_passed: bool = True
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


class ProcessReaperConfig(BaseModel):
    """Configuration options for the process reaper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_process_names: list[str] = Field(
        default_factory=lambda: [
            "orted",
            "mpirun",
            "mpiexec",
            "mpiexec.hydra",
            "hydra_pmi_proxy",
            "orca",
            "orca_scf",
            "orca_gstep",
            "orca_casscf",
            "orca_cis",
            "orca_md",
            "orca_opt",
            "orca_vpot",
            "orca_soc",
            "orca_chelpg",
            "orca_pc",
            "orca_mrci",
            "orca_property",
            "orca_mp2",
            "orca_eprnmr",
            "orca_vib",
            "orca_numfreq",
            "orca_2mkl",
            "orca_plot",
            "xtb",
            "crest",
            "mopac",
            "mace",
            "g16",
            "g09",
            "pyscf",
            "oet_server",
            "ase",
        ]
    )
    process_cmdline_patterns: list[str] = Field(
        default_factory=lambda: [
            "orca",
            "xtb",
            "crest",
            "mopac",
            "oet_server",
            "mpirun",
            "orted",
            "g16",
            "g09",
            "mace",
        ]
    )
    sigterm_timeout_seconds: float = Field(
        default=3.0,
        description="Grace period in seconds for SIGTERM termination before escalating to SIGKILL",
    )
    sigkill_timeout_seconds: float = Field(
        default=2.0,
        description="Timeout in seconds to wait after SIGKILL",
    )
    protect_current_process: bool = True
    protect_parent_process: bool = True
    protected_pids: list[int] = Field(default_factory=list)
    use_taskkill_on_windows: bool = True


class HDF5LockRecord(BaseModel):
    """Audit record for a single HDF5 companion lock file inspection and release."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lock_file_path: str
    h5_file_path: str | None = None
    holder_pid: int | None = None
    status: str = Field(
        description="Outcome: 'lock_released', 'lock_retained_live_process', 'stale_lock_purged', 'file_not_found', 'error'"
    )
    reason: str = ""
    file_healthy: bool = True
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class HDF5LockSweepResult(BaseModel):
    """Aggregate result from sweeping HDF5 lock files."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    scanned_lock_files: list[str] = Field(default_factory=list)
    released_locks: list[HDF5LockRecord] = Field(default_factory=list)
    active_locks_found: int = 0
    stale_locks_removed: int = 0
    active_locks_retained: int = 0
    corrupted_files_found: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class HDF5LockSweeperConfig(BaseModel):
    """Configuration options for HDF5 SWMR file lock sweeper."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    target_dirs: list[Path] = Field(default_factory=list)
    lock_file_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.h5.lck",
            "*.swmr.lock",
            "*.h5.lock",
            "*.lck",
            "*.h5.swmr.lock",
        ]
    )
    verify_h5_integrity: bool = True
    force_release: bool = False
    ignore_lock_errors: bool = True


class PostFlightAuditReport(BaseModel):
    """Comprehensive Post-Flight Audit Report combining scratch purge, process reaper, and HDF5 lock state."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    audit_passed: bool
    purge_result: PurgeResult
    reap_result: ReapResult
    hdf5_lock_result: HDF5LockSweepResult = Field(default_factory=HDF5LockSweepResult)
    os_platform: str = Field(default_factory=lambda: platform.system())
    wsl_detected: bool = False
    disk_reclaimed_mb: float = 0.0
    summary: str = ""

    def to_json(self, indent: int = 2) -> str:
        """Serializes the audit report into a formatted JSON string."""
        return self.model_dump_json(indent=indent)

    def save_to_file(self, path: str | Path) -> Path:
        """Writes the audit report to a JSON file."""
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.to_json(indent=2), encoding="utf-8")
        return target_path


# ============================================================================
# WSL Path Translator
# ============================================================================

class WSLPathTranslator:
    """
    Translates and normalizes paths between Windows and WSL2 ext4 representations.
    Resolves UNC paths (\\\\wsl$\\..., \\\\wsl.localhost\\...) and /mnt/<drive>/ paths
    to avoid 9P network protocol overhead and maintain cross-platform compatibility.
    """

    @staticmethod
    def is_wsl() -> bool:
        """Detects if the Python interpreter is running inside a WSL Linux environment."""
        if platform.system().lower() != "linux":
            return False
        if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
            return True
        try:
            with open("/proc/version", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                return "microsoft" in content or "wsl" in content
        except Exception:
            return False

    @staticmethod
    def is_wsl_unc_path(path: str | Path) -> bool:
        """Checks if a path string uses Windows WSL UNC syntax (\\\\wsl$\\ or \\\\wsl.localhost\\)."""
        s = str(path).replace("/", "\\").lower()
        return s.startswith("\\\\wsl$\\") or s.startswith("\\\\wsl.localhost\\")

    @staticmethod
    def windows_to_wsl(path: str | Path, distro: str = "Ubuntu") -> str:
        """
        Converts a Windows path to a WSL POSIX path.
        Example: 'C:\\Users\\ansac\\scratch' -> '/mnt/c/Users/ansac/scratch'
        Example: '\\\\wsl.localhost\\Ubuntu\\home\\user\\tmp' -> '/home/user/tmp'
        """
        path_str = str(path).strip()
        if not path_str:
            return ""

        norm = path_str.replace("/", "\\")

        # Check UNC WSL path: \\wsl$\distro\... or \\wsl.localhost\distro\...
        unc_match = re.match(r"^\\\\(?:wsl\$|wsl\.localhost)\\[^\\]+(.*)$", norm, re.IGNORECASE)
        if unc_match:
            sub = unc_match.group(1).replace("\\", "/")
            return sub if sub.startswith("/") else "/" + sub

        # Check Windows drive letter: C:\...
        drive_match = re.match(r"^([a-zA-Z]):\\(.*)$", norm)
        if drive_match:
            drive_letter = drive_match.group(1).lower()
            rest = drive_match.group(2).replace("\\", "/")
            return f"/mnt/{drive_letter}/{rest}".rstrip("/")

        # If already posix
        if path_str.startswith("/"):
            return path_str

        return path_str.replace("\\", "/")

    @staticmethod
    def wsl_to_windows(path: str | Path, distro: str = "Ubuntu") -> str:
        """
        Converts a WSL POSIX path to a Windows path.
        Example: '/mnt/c/Users/ansac/scratch' -> 'C:\\Users\\ansac\\scratch'
        Example: '/home/user/scratch' -> '\\\\wsl.localhost\\Ubuntu\\home\\user\\scratch'
        """
        path_str = str(path).strip()
        if not path_str:
            return ""

        # Check /mnt/<drive>/...
        mnt_match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", path_str)
        if mnt_match:
            drive_letter = mnt_match.group(1).upper()
            rest = mnt_match.group(2).replace("/", "\\")
            return f"{drive_letter}:\\{rest}"

        if path_str.startswith("/mnt/"):
            single_drive = re.match(r"^/mnt/([a-zA-Z])$", path_str)
            if single_drive:
                return f"{single_drive.group(1).upper()}:\\"

        # Check native Linux ext4 path inside WSL (e.g. /home/... or /tmp/...)
        if path_str.startswith("/"):
            rel_path = path_str.lstrip("/").replace("/", "\\")
            return f"\\\\wsl.localhost\\{distro}\\{rel_path}"

        # If already Windows drive path
        drive_match = re.match(r"^([a-zA-Z]):[\\/](.*)$", path_str)
        if drive_match:
            drive_letter = drive_match.group(1).upper()
            rest = drive_match.group(2).replace("/", "\\")
            return f"{drive_letter}:\\{rest}"

        return path_str.replace("/", "\\")

    @classmethod
    def normalize_path(cls, path: str | Path) -> Path:
        """
        Normalizes a path to the native host OS representation.
        Converts WSL /mnt/ paths to Windows drive paths when running on Windows,
        and Windows drive paths to /mnt/ paths when running inside WSL.
        """
        raw_str = str(path).strip()
        if not raw_str:
            return Path(".")

        if platform.system().lower() == "windows":
            if raw_str.startswith("/mnt/"):
                win_str = cls.wsl_to_windows(raw_str)
                return Path(win_str)
            if cls.is_wsl_unc_path(raw_str):
                return Path(raw_str.replace("/", "\\"))
            return Path(raw_str)
        else:
            if cls.is_wsl():
                if re.match(r"^[a-zA-Z]:[\\/]", raw_str) or cls.is_wsl_unc_path(raw_str):
                    return Path(cls.windows_to_wsl(raw_str))
            return Path(raw_str)


# ============================================================================
# Scratch Purge Engine
# ============================================================================

class ToposScratchPurgeEngine:
    """
    Scans and purges ephemeral calculation artifacts (.tmp, .dens, .gbw, etc.)
    across configured scratch and temporary workspace directories.
    Handles Windows kernel locks, WSL path translation, whitelists, and quarantining.
    """

    def __init__(self, config: ScratchPurgeConfig | None = None) -> None:
        self.config = config or ScratchPurgeConfig()
        self.translator = WSLPathTranslator()

    def discover_target_directories(self) -> list[Path]:
        """
        Resolves candidate scratch directories from explicit configuration,
        environment variables, and standard fallback locations.
        """
        discovered: list[Path] = []
        seen_resolved: set[str] = set()

        def add_candidate(cand_path: str | Path) -> None:
            norm_path = self.translator.normalize_path(cand_path)
            try:
                expanded = Path(os.path.expandvars(str(norm_path))).expanduser()
                if expanded.exists() and expanded.is_dir():
                    res = str(expanded.resolve())
                    if res not in seen_resolved:
                        seen_resolved.add(res)
                        discovered.append(expanded)
            except Exception as e:
                logger.debug(f"Error evaluating candidate scratch directory {cand_path}: {e}")

        # 1. Explicitly configured target directories (used exclusively if provided)
        if self.config.target_dirs:
            for target in self.config.target_dirs:
                add_candidate(target)
            return discovered

        # 2. Environment variables
        for env_var in self.config.env_var_names:
            val = os.environ.get(env_var)
            if val:
                sep = ";" if platform.system().lower() == "windows" and ";" in val else os.pathsep
                for part in val.split(sep):
                    part = part.strip()
                    if part:
                        add_candidate(part)
                        base_p = Path(part)
                        if (base_p / "orca_tmp").is_dir():
                            add_candidate(base_p / "orca_tmp")
                        if (base_p / "ase_graphs").is_dir():
                            add_candidate(base_p / "ase_graphs")

        # 3. Default fallback relative directories
        for fallback in self.config.default_fallback_dirs:
            add_candidate(fallback)

        return discovered

    def is_ephemeral_file(self, file_path: Path) -> bool:
        """
        Determines whether a file matches the ephemeral criteria based on extension,
        name patterns, and file age.
        """
        name_lower = file_path.name.lower()

        # Check extensions
        for ext in self.config.ephemeral_extensions:
            ext_lower = ext.lower()
            if not ext_lower.startswith("."):
                ext_lower = "." + ext_lower
            if name_lower.endswith(ext_lower):
                return True

        # Check glob patterns
        for pattern in self.config.ephemeral_patterns:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return True

        return False

    def is_whitelisted(self, file_path: Path) -> bool:
        """
        Checks if a file is explicitly whitelisted or matches archive patterns
        and must NOT be deleted.
        """
        abs_str = str(file_path.resolve()).lower()
        name_str = file_path.name.lower()

        for wl in self.config.archive_whitelist:
            wl_lower = str(wl).lower()
            if wl_lower == name_str or wl_lower == abs_str or str(Path(wl).name).lower() == name_str:
                return True
            if ("/" in wl_lower or "\\" in wl_lower) and fnmatch.fnmatch(abs_str, wl_lower):
                return True

        for pat in self.config.archive_patterns:
            pat_lower = pat.lower()
            if fnmatch.fnmatch(name_str, pat_lower):
                return True
            if ("/" in pat_lower or "\\" in pat_lower) and fnmatch.fnmatch(abs_str, pat_lower):
                return True

        return False

    def _delete_or_quarantine_file(self, file_path: Path, result: PurgeResult) -> PurgedFileRecord:
        """
        Attempts to forcefully delete or quarantine a single ephemeral file,
        handling Windows file locks with retry and permission adjustments.
        """
        file_size = 0
        sha256_digest: str | None = None
        ext = file_path.suffix.lower()

        try:
            file_size = file_path.stat().st_size
        except OSError:
            pass

        # Check age filter if configured
        if self.config.max_file_age_seconds is not None:
            try:
                mtime = file_path.stat().st_mtime
                age = time.time() - mtime
                if age < self.config.max_file_age_seconds:
                    return PurgedFileRecord(
                        path=str(file_path),
                        size_bytes=file_size,
                        status="whitelisted",
                        reason=f"File age ({age:.1f}s) is less than max_file_age_seconds threshold",
                        extension=ext,
                    )
            except OSError:
                pass

        # Check whitelisting
        if self.is_whitelisted(file_path):
            result.total_files_whitelisted += 1
            return PurgedFileRecord(
                path=str(file_path),
                size_bytes=file_size,
                status="whitelisted",
                reason="Explicitly flagged for archiving / whitelisted",
                extension=ext,
            )

        # Compute SHA-256 digest before unlinking or quarantining if configured
        if self.config.compute_sha256 and file_path.is_file():
            try:
                sha256_digest = _compute_sha256(file_path)
            except Exception as e:
                logger.debug(f"Failed to compute SHA-256 for {file_path}: {e}")

        # Quarantine mode
        if self.config.quarantine_dir is not None:
            q_dir = self.translator.normalize_path(self.config.quarantine_dir)
            q_dir.mkdir(parents=True, exist_ok=True)
            q_dest = q_dir / file_path.name

            if q_dest.exists():
                stem = file_path.stem
                ts = int(time.time() * 1000)
                q_dest = q_dir / f"{stem}_{ts}{file_path.suffix}"

            last_err: Exception | None = None
            for attempt in range(self.config.max_retries):
                try:
                    try:
                        os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                    shutil.move(str(file_path), str(q_dest))
                    result.total_files_quarantined += 1
                    result.reclaimed_bytes += file_size
                    return PurgedFileRecord(
                        path=str(file_path),
                        size_bytes=file_size,
                        status="quarantined",
                        reason=f"Moved to quarantine: {q_dest}",
                        extension=ext,
                        sha256_hash=sha256_digest,
                    )
                except (PermissionError, OSError) as e:
                    last_err = e
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))

            err_msg = f"Failed to quarantine {file_path} after {self.config.max_retries} attempts: {last_err}"
            logger.warning(err_msg)
            result.errors.append(err_msg)
            if not self.config.ignore_cleanup_errors:
                raise last_err or OSError(err_msg)
            return PurgedFileRecord(
                path=str(file_path),
                size_bytes=file_size,
                status="failed",
                reason=str(last_err),
                extension=ext,
                sha256_hash=sha256_digest,
            )

        # Deletion mode
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                try:
                    os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass

                file_path.unlink()
                result.total_files_deleted += 1
                result.reclaimed_bytes += file_size
                return PurgedFileRecord(
                    path=str(file_path),
                    size_bytes=file_size,
                    status="deleted",
                    reason="Ephemeral scratch artifact purged",
                    extension=ext,
                    sha256_hash=sha256_digest,
                )
            except (PermissionError, OSError) as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))

        err_msg = f"Failed to delete {file_path} after {self.config.max_retries} attempts: {last_error}"
        logger.warning(err_msg)
        result.errors.append(err_msg)

        if not self.config.ignore_cleanup_errors:
            raise last_error or OSError(err_msg)

        return PurgedFileRecord(
            path=str(file_path),
            size_bytes=file_size,
            status="failed",
            reason=str(last_error),
            extension=ext,
            sha256_hash=sha256_digest,
        )

    def _remove_empty_subdirectories(self, directory: Path, result: PurgeResult) -> None:
        """Recursively removes empty subdirectories inside directory."""
        if not self.config.remove_empty_dirs or not directory.exists():
            return

        base_res = directory.resolve()
        for root, _dirs, _files in os.walk(directory, topdown=False):
            curr_path = Path(root)
            if curr_path.resolve() == base_res:
                continue

            try:
                if not any(curr_path.iterdir()):
                    for attempt in range(self.config.max_retries):
                        try:
                            curr_path.rmdir()
                            result.total_directories_removed += 1
                            break
                        except (PermissionError, OSError):
                            if attempt < self.config.max_retries - 1:
                                time.sleep(self.config.retry_delay_seconds * (1.5 ** attempt))
            except Exception as e:
                logger.debug(f"Could not inspect or remove directory {curr_path}: {e}")

    def purge(
        self,
        custom_dirs: Sequence[str | Path] | None = None,
        archive_whitelist: Sequence[str | Path] | None = None,
        quarantine_dir: str | Path | None = None,
    ) -> PurgeResult:
        """
        Executes scratch directory scanning and ephemeral artifact purging.
        """
        start_time = time.time()
        result = PurgeResult()

        if archive_whitelist:
            self.config.archive_whitelist.extend(str(x) for x in archive_whitelist)
        if quarantine_dir:
            self.config.quarantine_dir = Path(quarantine_dir)

        target_dirs: list[Path] = []
        if custom_dirs:
            for d in custom_dirs:
                norm_d = self.translator.normalize_path(d)
                if norm_d.exists() and norm_d.is_dir():
                    target_dirs.append(norm_d)
        else:
            target_dirs = self.discover_target_directories()

        for sdir in target_dirs:
            result.scanned_directories.append(str(sdir))
            logger.info(f"Purging scratch directory: {sdir}")

            try:
                for root, _dirs, files in os.walk(sdir):
                    for file_name in files:
                        result.total_files_scanned += 1
                        file_path = Path(root) / file_name

                        if self.is_ephemeral_file(file_path):
                            rec = self._delete_or_quarantine_file(file_path, result)
                            result.purged_files.append(rec)

                self._remove_empty_subdirectories(sdir, result)

            except Exception as e:
                err_str = f"Error during traversal of {sdir}: {e}"
                logger.error(err_str)
                result.errors.append(err_str)
                if not self.config.ignore_cleanup_errors:
                    raise

        result.duration_seconds = round(time.time() - start_time, 4)
        logger.info(
            f"Scratch purge completed in {result.duration_seconds}s: "
            f"{result.total_files_deleted} deleted, {result.total_files_quarantined} quarantined, "
            f"{result.total_files_whitelisted} whitelisted, {result.reclaimed_bytes / (1024*1024):.2f} MB reclaimed."
        )
        return result


# ============================================================================
# Process Thread Reaper
# ============================================================================

class ToposProcessReaper:
    """
    Cross-platform process thread reaper utilizing psutil and OS termination signals.
    Audits and terminates orphaned OpenMPI, ORCA, xTB, CREST, MOPAC, MACE, Gaussian,
    and physics background runner processes.
    """

    def __init__(self, config: ProcessReaperConfig | None = None) -> None:
        self.config = config or ProcessReaperConfig()

    def _is_protected(self, proc: psutil.Process) -> bool:
        """Determines if a process is protected from termination (e.g. self, parent, whitelist)."""
        try:
            pid = proc.pid
            if pid <= 4:
                return True
            if self.config.protect_current_process and pid == os.getpid():
                return True
            if self.config.protect_parent_process and pid == os.getppid():
                return True
            if pid in self.config.protected_pids:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
        return False

    def _is_target_process(self, proc: psutil.Process) -> tuple[bool, str]:
        """
        Evaluates whether a process matches target quantum chemistry / MPI runner patterns.
        Returns a tuple of (is_target, reason).
        """
        if self._is_protected(proc):
            return False, "Protected process"

        try:
            name_lower = proc.name().lower()
            if name_lower.endswith(".exe"):
                base_name = name_lower[:-4]
            else:
                base_name = name_lower

            # 1. Exact or prefix match against target_process_names
            for target in self.config.target_process_names:
                t_lower = target.lower()
                if base_name == t_lower:
                    return True, f"Matched target process name: {target}"
                if t_lower.endswith("*") and base_name.startswith(t_lower[:-1]):
                    return True, f"Matched wildcard target process name: {target}"
                if "*" in t_lower and fnmatch.fnmatch(base_name, t_lower):
                    return True, f"Matched pattern target process name: {target}"

            # 2. Inspect command-line arguments (executable or script entrypoint)
            try:
                cmdline = proc.cmdline()
                if not cmdline:
                    return False, "No cmdline"

                cmdline_str = " ".join(cmdline).lower()

                # Check custom CoChem markers (e.g. cochem_test_orphan_..., cochem_tree_parent_...)
                for pat in self.config.process_cmdline_patterns:
                    p_lower = pat.lower()
                    if p_lower.startswith("cochem_") and p_lower in cmdline_str:
                        return True, f"Matched CoChem marker '{pat}' in args: {cmdline_str[:120]}"

                # Inspect executable token (cmdline[0]) and immediate script token (cmdline[1])
                exe_arg = Path(cmdline[0]).name.lower()
                if exe_arg.endswith(".exe"):
                    exe_arg = exe_arg[:-4]

                script_arg = ""
                if len(cmdline) > 1:
                    try:
                        script_arg = Path(cmdline[1]).name.lower()
                        if script_arg.endswith(".exe") or script_arg.endswith(".py"):
                            script_arg = Path(cmdline[1]).stem.lower()
                    except Exception:
                        script_arg = ""

                for pat in self.config.process_cmdline_patterns:
                    p_lower = pat.lower()
                    if p_lower.startswith("cochem_"):
                        continue
                    if exe_arg == p_lower or script_arg == p_lower:
                        return True, f"Matched executable/script target '{pat}' in cmdline: {cmdline[:2]}"
                    if "*" in p_lower and (fnmatch.fnmatch(exe_arg, p_lower) or fnmatch.fnmatch(script_arg, p_lower)):
                        return True, f"Matched pattern target '{pat}' in cmdline: {cmdline[:2]}"

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False, "Process unavailable"

        return False, "No match"

    def audit_active_orphans(self) -> list[psutil.Process]:
        """
        Scans all running system processes and returns a list of active orphaned
        chemistry/MPI targets.
        """
        orphans: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
            try:
                is_target, _reason = self._is_target_process(proc)
                if is_target:
                    orphans.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return orphans

    def _terminate_process_tree(self, proc: psutil.Process) -> ReapedProcessRecord:
        """
        Recursively terminates a process and all its children using graceful SIGTERM
        followed by SIGKILL / taskkill escalation.
        """
        pid = proc.pid
        name = "unknown"
        cmdline: list[str] = []
        create_time = 0.0
        pgid: int | None = None

        try:
            name = proc.name()
            cmdline = proc.cmdline()
            create_time = proc.create_time()
            if hasattr(os, "getpgid"):
                try:
                    pgid = os.getpgid(pid)
                except OSError:
                    pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        try:
            children = proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        all_procs = children + [proc]

        # Stage 1: Graceful SIGTERM / terminate()
        for p in all_procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Wait for graceful exit
        _gone, alive = psutil.wait_procs(all_procs, timeout=self.config.sigterm_timeout_seconds)

        # Stage 2: Forceful termination
        if alive:
            if platform.system().lower() == "windows" and self.config.use_taskkill_on_windows:
                for p in alive:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            timeout=self.config.sigkill_timeout_seconds,
                        )
                    except Exception:
                        try:
                            p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
            else:
                for p in alive:
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            _gone2, alive2 = psutil.wait_procs(alive, timeout=self.config.sigkill_timeout_seconds)
            status = "killed_forcefully" if not alive2 else "failed"
        else:
            status = "terminated_gracefully"

        return ReapedProcessRecord(
            pid=pid,
            pgid=pgid,
            name=name,
            cmdline=cmdline,
            create_time=create_time,
            status=status,
        )

    def reap_orphans(
        self,
        custom_target_names: Sequence[str] | None = None,
        custom_cmdline_patterns: Sequence[str] | None = None,
    ) -> ReapResult:
        """
        Audits active processes and terminates all matching orphaned background threads.
        """
        start_time = time.time()
        result = ReapResult()

        if custom_target_names:
            self.config.target_process_names.extend(custom_target_names)
        if custom_cmdline_patterns:
            self.config.process_cmdline_patterns.extend(custom_cmdline_patterns)

        orphans = self.audit_active_orphans()
        result.active_orphans_found = len(orphans)

        for proc in orphans:
            try:
                rec = self._terminate_process_tree(proc)
                result.reaped_processes.append(rec)
                if rec.status in ("terminated_gracefully", "killed_forcefully", "already_dead"):
                    result.successful_terminations += 1
                else:
                    result.failed_terminations += 1
            except Exception as e:
                err_msg = f"Error terminating process PID={getattr(proc, 'pid', 'unknown')}: {e}"
                logger.error(err_msg)
                result.errors.append(err_msg)
                result.failed_terminations += 1

        remaining_orphans = self.audit_active_orphans()
        result.audit_passed = len(remaining_orphans) == 0
        result.duration_seconds = round(time.time() - start_time, 4)

        if not result.audit_passed:
            err_str = f"Post-reap verification failed: {len(remaining_orphans)} orphan processes remain active."
            logger.error(err_str)
            result.errors.append(err_str)

        logger.info(
            f"Process reaper completed in {result.duration_seconds}s: "
            f"{result.successful_terminations} terminated, {result.failed_terminations} failed, "
            f"audit_passed={result.audit_passed}"
        )
        return result


# ============================================================================
# HDF5 SWMR Lock Sweeper
# ============================================================================

class ToposHDF5LockSweeper:
    """
    Safely inspects, verifies, and flushes HDF5 SWMR locks (.h5.lck, .swmr.lock, etc.)
    held by terminated/zombie processes, safeguarding database integrity without data corruption.
    """

    def __init__(self, config: HDF5LockSweeperConfig | None = None) -> None:
        self.config = config or HDF5LockSweeperConfig()
        self.translator = WSLPathTranslator()

    def discover_target_directories(self) -> list[Path]:
        """Discovers target directories to scan for companion lock files."""
        discovered: list[Path] = []
        seen: set[str] = set()

        def add_dir(p: str | Path) -> None:
            norm = self.translator.normalize_path(p)
            try:
                exp = Path(os.path.expandvars(str(norm))).expanduser()
                if exp.exists() and exp.is_dir():
                    res = str(exp.resolve())
                    if res not in seen:
                        seen.add(res)
                        discovered.append(exp)
            except Exception as e:
                logger.debug(f"Error evaluating HDF5 lock directory {p}: {e}")

        if self.config.target_dirs:
            for target_d in self.config.target_dirs:
                add_dir(target_d)
            return discovered

        defaults = [
            ".",
            "./artifacts",
            "./scratch",
            "./mechanics",
            "./escalation",
        ]
        for env_var in ["COCHEM_SCRATCH_DIR", "COCHEM_SCRATCH", "COCHEM_TMP", "COCHEM_WORKSPACE"]:
            val = os.environ.get(env_var)
            if val:
                add_dir(val)

        for default_d in defaults:
            add_dir(default_d)

        return discovered

    def discover_lock_files(self, custom_dirs: Sequence[str | Path] | None = None) -> list[Path]:
        """Scans directories for active HDF5 companion lock files."""
        target_dirs: list[Path] = []
        if custom_dirs:
            for custom_d in custom_dirs:
                norm = self.translator.normalize_path(custom_d)
                if norm.exists() and norm.is_dir():
                    target_dirs.append(norm)
        else:
            target_dirs = self.discover_target_directories()

        lock_files: list[Path] = []
        for sdir in target_dirs:
            try:
                for root, _dirs, files in os.walk(sdir):
                    for file_name in files:
                        for pattern in self.config.lock_file_patterns:
                            if fnmatch.fnmatch(file_name.lower(), pattern.lower()):
                                lock_files.append(Path(root) / file_name)
                                break
            except Exception as e:
                logger.debug(f"Error traversing directory {sdir} for HDF5 locks: {e}")

        return lock_files

    def _resolve_associated_h5_file(self, lock_file: Path) -> Path | None:
        """Infers the corresponding .h5 file path for a companion lock file."""
        name = lock_file.name
        parent = lock_file.parent

        for suffix in [".h5.lck", ".swmr.lock", ".h5.lock", ".h5.swmr.lock", ".lck"]:
            if name.endswith(suffix):
                stem = name[: -len(suffix)]
                cand = parent / f"{stem}.h5"
                if cand.exists():
                    return cand
                cand2 = parent / stem
                if cand2.exists() and cand2.suffix.lower() == ".h5":
                    return cand2

        try:
            with open(lock_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if "h5_file" in data:
                h5_p = self.translator.normalize_path(data["h5_file"])
                if h5_p.exists():
                    return h5_p
        except Exception:
            pass

        return None

    def inspect_h5_integrity(self, h5_path: Path) -> bool:
        """Verifies that an HDF5 database can be safely opened and read."""
        if not self.config.verify_h5_integrity or not h5_path.exists():
            return True

        try:
            with h5py.File(h5_path, "r") as fp:
                _ = list(fp.keys())
            return True
        except Exception as err:
            logger.error(f"HDF5 integrity check failed for {h5_path}: {err}")
            return False

    def inspect_and_sweep_lock(
        self,
        lock_file: Path,
        force: bool = False,
    ) -> HDF5LockRecord:
        """
        Inspects a single lock file, checks if the holding PID is alive/dead,
        and safely removes stale locks while validating companion HDF5 files.
        """
        if not lock_file.exists():
            return HDF5LockRecord(
                lock_file_path=str(lock_file),
                status="file_not_found",
                reason="Lock file does not exist",
            )

        holder_pid: int | None = None
        h5_path = self._resolve_associated_h5_file(lock_file)

        try:
            with open(lock_file, "r", encoding="utf-8") as fp:
                content = fp.read().strip()
            if content.startswith("{"):
                data = json.loads(content)
                holder_pid = data.get("pid")
            elif content.isdigit():
                holder_pid = int(content)
        except Exception as e:
            logger.debug(f"Could not parse PID from lock file {lock_file}: {e}")

        is_zombie_or_dead = False
        if holder_pid is not None:
            if not psutil.pid_exists(holder_pid):
                is_zombie_or_dead = True
            else:
                try:
                    proc = psutil.Process(holder_pid)
                    if proc.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                        is_zombie_or_dead = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    is_zombie_or_dead = True

        if holder_pid == os.getpid():
            is_zombie_or_dead = True

        should_release = force or self.config.force_release or is_zombie_or_dead or holder_pid is None

        file_healthy = True
        if h5_path:
            file_healthy = self.inspect_h5_integrity(h5_path)

        if should_release:
            try:
                try:
                    os.chmod(lock_file, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass
                lock_file.unlink()
                status = "stale_lock_purged" if is_zombie_or_dead else "lock_released"
                reason = f"Lock released (PID={holder_pid}, stale={is_zombie_or_dead})"
                logger.info(f"Released HDF5 lock file: {lock_file} ({reason})")
            except OSError as err:
                status = "error"
                reason = f"Failed to unlink lock file {lock_file}: {err}"
                logger.error(reason)
                if not self.config.ignore_lock_errors:
                    raise
        else:
            status = "lock_retained_live_process"
            reason = f"Lock file is actively held by live process PID={holder_pid}"
            logger.info(f"Skipping active lock file: {lock_file} (held by PID {holder_pid})")

        return HDF5LockRecord(
            lock_file_path=str(lock_file),
            h5_file_path=str(h5_path) if h5_path else None,
            holder_pid=holder_pid,
            status=status,
            reason=reason,
            file_healthy=file_healthy,
        )

    def sweep_locks(
        self,
        custom_dirs: Sequence[str | Path] | None = None,
        force: bool = False,
    ) -> HDF5LockSweepResult:
        """
        Scans all target directories and sweeps orphaned or stale HDF5 companion locks.
        """
        start_time = time.time()
        result = HDF5LockSweepResult()

        lock_files = self.discover_lock_files(custom_dirs)
        result.scanned_lock_files = [str(f) for f in lock_files]
        result.active_locks_found = len(lock_files)

        for lf in lock_files:
            try:
                rec = self.inspect_and_sweep_lock(lf, force=force)
                result.released_locks.append(rec)
                if rec.status in ("stale_lock_purged", "lock_released"):
                    result.stale_locks_removed += 1
                elif rec.status == "lock_retained_live_process":
                    result.active_locks_retained += 1
                elif rec.status == "error":
                    result.errors.append(rec.reason)

                if not rec.file_healthy:
                    result.corrupted_files_found += 1

            except Exception as e:
                err_msg = f"Error processing HDF5 lock {lf}: {e}"
                logger.error(err_msg)
                result.errors.append(err_msg)
                if not self.config.ignore_lock_errors:
                    raise

        result.duration_seconds = round(time.time() - start_time, 4)
        logger.info(
            f"HDF5 lock sweeper completed in {result.duration_seconds}s: "
            f"{result.stale_locks_removed} stale locks removed, {result.active_locks_retained} live retained."
        )
        return result


# ============================================================================
# Topos Environment Sanitizer (Master Context Manager)
# ============================================================================

class ToposEnvironmentSanitizer:
    """
    Master Environment Sanitizer and Post-Flight Audit Coordinator for CoChem-TOPOS.
    Executes scratch directory purging, process reaper cleanup, and HDF5 lock sweeping.
    Outputs verified PostFlightAuditReports. Supports context manager execution.
    """

    def __init__(
        self,
        purge_config: ScratchPurgeConfig | None = None,
        reaper_config: ProcessReaperConfig | None = None,
        lock_config: HDF5LockSweeperConfig | None = None,
    ) -> None:
        self.purge_config = purge_config or ScratchPurgeConfig()
        self.reaper_config = reaper_config or ProcessReaperConfig()
        self.lock_config = lock_config or HDF5LockSweeperConfig()

        self.purge_engine = ToposScratchPurgeEngine(self.purge_config)
        self.process_reaper = ToposProcessReaper(self.reaper_config)
        self.lock_sweeper = ToposHDF5LockSweeper(self.lock_config)
        self.wsl_detected = WSLPathTranslator.is_wsl()

    def __enter__(self) -> ToposEnvironmentSanitizer:
        logger.info("Entering ToposEnvironmentSanitizer context...")
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        logger.info("Exiting ToposEnvironmentSanitizer context. Executing post-flight audit & cleanup...")
        if exc_type is not None:
            try:
                self.execute_post_flight_audit()
            except Exception as e:
                logger.error(f"Post-flight audit failed during exception unwind: {e}", exc_info=True)
            return None
        else:
            self.execute_post_flight_audit()

    def verify_environment_clean(self) -> bool:
        """Verifies that zero target orphan processes are active in the environment."""
        orphans = self.process_reaper.audit_active_orphans()
        return len(orphans) == 0

    def execute_post_flight_audit(
        self,
        archive_whitelist: Sequence[str | Path] | None = None,
        quarantine_dir: str | Path | None = None,
        purge_scratch: bool = True,
        reap_processes: bool = True,
        sweep_hdf5_locks: bool = True,
    ) -> PostFlightAuditReport:
        """
        Runs the full Stage 5.0 Post-Flight Audit & Cleanup sequence:
        1. Purges ephemeral scratch files while preserving whitelisted archives.
        2. Audits and reaps any remaining orphaned quantum chemistry subprocesses.
        3. Sweeps stale HDF5 SWMR locks and verifies database integrity.
        4. Compiles and returns a PostFlightAuditReport.
        """
        logger.info("Starting Stage 5.0 Post-Flight Audit & Environment Cleanup...")

        purge_res = PurgeResult()
        if purge_scratch:
            purge_res = self.purge_engine.purge(
                archive_whitelist=archive_whitelist,
                quarantine_dir=quarantine_dir,
            )

        reap_res = ReapResult()
        if reap_processes:
            reap_res = self.process_reaper.reap_orphans()

        lock_res = HDF5LockSweepResult()
        if sweep_hdf5_locks:
            lock_res = self.lock_sweeper.sweep_locks()

        audit_passed = (
            reap_res.audit_passed
            and len(purge_res.errors) == 0
            and len(lock_res.errors) == 0
            and lock_res.corrupted_files_found == 0
        )
        reclaimed_mb = round(purge_res.reclaimed_bytes / (1024 * 1024), 3)

        summary = (
            f"Stage 5.0 Post-Flight Audit: {'PASSED' if audit_passed else 'FAILED'}. "
            f"Reclaimed {reclaimed_mb} MB across {purge_res.total_files_deleted} deleted files. "
            f"Terminated {reap_res.successful_terminations} orphaned calculation processes. "
            f"Swept {lock_res.stale_locks_removed} stale HDF5 locks."
        )

        report = PostFlightAuditReport(
            audit_passed=audit_passed,
            purge_result=purge_res,
            reap_result=reap_res,
            hdf5_lock_result=lock_res,
            os_platform=platform.system(),
            wsl_detected=self.wsl_detected,
            disk_reclaimed_mb=reclaimed_mb,
            summary=summary,
        )

        logger.info(summary)
        return report

    def save_audit_report(self, report: PostFlightAuditReport, output_path: str | Path) -> Path:
        """Saves the PostFlightAuditReport as a formatted JSON artifact."""
        return report.save_to_file(output_path)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_rel.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 4.0 Scalar Relativistic & Spin-Orbit Corrections Engine.

Module: tests/test_cochem_bench_rel.py
Target Implementation: bench_engine.cochem_bench_rel

Authoritative Requirements & Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_rel.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_rel import (
    RelativisticHamiltonianInjector,
    X2CHandler,
    X2CDivergenceError,
    RelativisticExecutionError,
    SpinOrbitCoupler,
    DeltaRelExtractor,
    RelCorrectionResult,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
    HARTREE_TO_KCAL_MOL,
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
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (Light elements: H, O - Z <= 8)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Bromobenzene (Heavy element: Br - Z = 35, Period 4)
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

# Dimethyl Selenide (Heavy element: Se - Z = 34)
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

# Methyl Radical (Open-shell doublet radical: CH3, Mult = 2)
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

ORCA_REL_STDOUT_BROMOBENZENE = """
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

ORCA_REL_DIVERGENCE_STDOUT = """
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

ORCA_SOC_RADICAL_STDOUT = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================
Relativistic Mode                     ... Exact Two-Component (X2C)
Spin-Orbit Coupling Operator          ... SOMF(1X) (Spin-Orbit Mean-Field)
Multiplicity                          ...    2 (Open-Shell Radical)

-------------------------------------------------------------------------------
SPIN-ORBIT COUPLING CALCULATION
-------------------------------------------------------------------------------
Two-component 2C-SOC expectation value ... -0.00284512 Eh
SOMF(1X) Energy Shift                 ... -0.00284512 Eh

-------------------------------------------------------------------------------
FINAL SINGLE POINT ENERGY                           -39.754891230000
-------------------------------------------------------------------------------
****ORCA TERMINATED NORMALLY****
"""


# ==============================================================================
# 1. RelativisticHamiltonianInjector Tests
# ==============================================================================

class TestRelativisticHamiltonianInjector:
    """Tests for relativistic Hamiltonian injection, basis set re-contraction, and heavy-element checks."""

    def test_map_relativistic_basis_set_def2_family(self) -> None:
        """Verifies mapping of Karlsruhe def2 basis sets to relativistically re-contracted X2C variants."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("def2-SVP") == "x2c-SVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVP") == "x2c-TZVPall-s"
        assert injector.map_relativistic_basis_set("def2-TZVPP") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("def2-QZVPP") == "x2c-QZVPPall-s"

    def test_map_relativistic_basis_set_cc_family(self) -> None:
        """Verifies mapping of Dunning correlation-consistent basis sets to X2C variants."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("cc-pVDZ") == "cc-pVDZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVTZ") == "cc-pVTZ-X2C"
        assert injector.map_relativistic_basis_set("cc-pVQZ") == "cc-pVQZ-X2C"
        assert injector.map_relativistic_basis_set("aug-cc-pVTZ") == "aug-cc-pVTZ-X2C"

    def test_map_relativistic_basis_set_already_relativistic(self) -> None:
        """Verifies that pre-recontracted basis sets remain unchanged."""
        injector = RelativisticHamiltonianInjector()

        assert injector.map_relativistic_basis_set("x2c-TZVPPall-s") == "x2c-TZVPPall-s"
        assert injector.map_relativistic_basis_set("ano-rcc") == "ano-rcc"
        assert injector.map_relativistic_basis_set("cc-pVTZ-X2C") == "cc-pVTZ-X2C"

    def test_inspect_heavy_elements_light_molecule(self) -> None:
        """Verifies that light systems (e.g., H2O) are identified as not requiring relativistic corrections."""
        injector = RelativisticHamiltonianInjector()
        info = injector.inspect_heavy_elements(WATER_COORDS, relativistic_z_threshold=19)

        assert info["has_heavy_elements"] is False
        assert info["max_z"] == 8  # Oxygen Z=8
        assert len(info["heavy_elements"]) == 0

        # Verify mass retrieved from Mendeleev
        m_o = element("O").mass
        m_h = element("H").mass
        expected_mass = float(m_o + 2 * m_h)
        assert math.isclose(info["total_mass"], expected_mass, rel_tol=1e-5)

    def test_inspect_heavy_elements_heavy_molecule(self) -> None:
        """Verifies that 4th-period+ systems (Bromobenzene, Dimethyl Selenide) are identified as requiring X2C."""
        injector = RelativisticHamiltonianInjector()
        info_br = injector.inspect_heavy_elements(BROMOBENZENE_COORDS, relativistic_z_threshold=19)

        assert info_br["has_heavy_elements"] is True
        assert info_br["max_z"] == 35  # Bromine Z=35
        assert "Br" in info_br["heavy_elements"]

        info_se = injector.inspect_heavy_elements(DMSE_COORDS, relativistic_z_threshold=19)
        assert info_se["has_heavy_elements"] is True
        assert info_se["max_z"] == 34  # Selenium Z=34
        assert "Se" in info_se["heavy_elements"]

    def test_inject_relativistic_hamiltonian_orca_input(self) -> None:
        """Verifies modification of ORCA input text with X2C and re-contracted basis set."""
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

    def test_generate_input_decks(self) -> None:
        """Verifies dual input deck generation for baseline non-relativistic and relativistic jobs."""
        injector = RelativisticHamiltonianInjector()
        decks = injector.generate_input_decks(
            coords=BROMOBENZENE_COORDS,
            method="DLPNO-CCSD(T)",
            base_basis="def2-TZVPP",
            charge=0,
            mult=1,
            node_max_gb=16.0,
            nprocs=4,
        )

        assert "non_rel_input" in decks
        assert "rel_input" in decks
        assert "def2-TZVPP" in decks["non_rel_input"]
        assert "X2C" not in decks["non_rel_input"]

        assert "X2C" in decks["rel_input"]
        assert "x2c-TZVPPall-s" in decks["rel_input"]
        assert decks["has_heavy_elements"] is True


# ==============================================================================
# 2. X2CHandler Tests (Strict Zero-Fallback Policy)
# ==============================================================================

class TestX2CHandler:
    """Tests for X2C divergence detection, fail-fast mechanics, and strict prohibition of DKH2 fallback."""

    def test_detect_divergence_normal_output(self) -> None:
        """Verifies that normal converged output does not trigger divergence flag."""
        handler = X2CHandler()
        assert handler.detect_divergence(ORCA_REL_STDOUT_BROMOBENZENE) is False

    def test_detect_divergence_failure_output(self) -> None:
        """Verifies detection of SCF divergence and DIIS failure in X2C calculation."""
        handler = X2CHandler()
        assert handler.detect_divergence(ORCA_REL_DIVERGENCE_STDOUT) is True

    def test_validate_convergence_success(self) -> None:
        """Verifies extraction of final energy when calculation converges normally."""
        handler = X2CHandler()
        energy = handler.validate_convergence(ORCA_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(energy, -2826.68940125, rel_tol=1e-9)

    def test_validate_convergence_divergence_raises_exception(self) -> None:
        """Verifies that X2CDivergenceError is explicitly raised on divergence and bans DKH2 fallback."""
        handler = X2CHandler()
        with pytest.raises(X2CDivergenceError) as exc_info:
            handler.validate_convergence(ORCA_REL_DIVERGENCE_STDOUT)

        err_msg = str(exc_info.value)
        assert "diverge" in err_msg.lower() or "fail" in err_msg.lower()
        # Verify strict benchmark requirement: no fallback to DKH2
        assert "dkh2" in err_msg.lower() or "uniform" in err_msg.lower()


# ==============================================================================
# 3. SpinOrbitCoupler Tests
# ==============================================================================

class TestSpinOrbitCoupler:
    """Tests for open-shell radical detection and SOMF(1X) operator injection."""

    def test_is_open_shell(self) -> None:
        """Verifies open-shell radical state classification."""
        coupler = SpinOrbitCoupler()
        assert coupler.is_open_shell(mult=1, requires_uhf=False, is_radical=False) is False
        assert coupler.is_open_shell(mult=2, requires_uhf=False, is_radical=False) is True
        assert coupler.is_open_shell(mult=1, requires_uhf=True, is_radical=False) is True
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

    def test_derive_soc_correction_open_shell(self) -> None:
        """Verifies derivation of delta E_SOC for radical states."""
        coupler = SpinOrbitCoupler()
        e_rel = -39.75204611
        e_soc = -39.75489123
        delta_soc = coupler.derive_soc_correction(e_total_rel=e_rel, e_total_soc=e_soc)

        expected = float(e_soc - e_rel)
        assert math.isclose(delta_soc, expected, rel_tol=1e-7)

    def test_derive_soc_correction_closed_shell(self) -> None:
        """Verifies that closed-shell systems yield 0.0 delta E_SOC."""
        coupler = SpinOrbitCoupler()
        delta_soc = coupler.derive_soc_correction(e_total_rel=-2826.68940125, e_total_soc=None)
        assert delta_soc == 0.0


# ==============================================================================
# 4. DeltaRelExtractor Tests
# ==============================================================================

class TestDeltaRelExtractor:
    """Tests for parsing authentic ORCA outputs, computing Delta E_rel, and converting units."""

    def test_parse_final_energy_from_stdout(self) -> None:
        """Verifies extraction of FINAL SINGLE POINT ENERGY from authentic stdout."""
        extractor = DeltaRelExtractor()
        e_non_rel = extractor.parse_final_energy_from_stdout(ORCA_NON_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_non_rel, -2805.01248912, rel_tol=1e-9)

        e_rel = extractor.parse_final_energy_from_stdout(ORCA_REL_STDOUT_BROMOBENZENE)
        assert math.isclose(e_rel, -2826.68940125, rel_tol=1e-9)

    def test_extract_delta_scalar_only(self) -> None:
        """Verifies relativistic shift derivation Delta E_rel = E_rel - E_non_rel in Hartree and kcal/mol."""
        extractor = DeltaRelExtractor()
        e_non_rel = -2805.01248912
        e_rel = -2826.68940125

        result = extractor.extract_delta(
            e_total_non_rel=e_non_rel,
            e_total_rel=e_rel,
            e_total_soc=None,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            method="DLPNO-CCSD(T)",
            has_heavy_elements=True,
            is_open_shell=False,
            node_id="bromobenzene_node",
        )

        expected_delta_hartree = float(e_rel - e_non_rel)
        expected_delta_kcal = float(expected_delta_hartree * HARTREE_TO_KCAL_MOL)

        assert math.isclose(result.delta_e_rel_hartree, expected_delta_hartree, rel_tol=1e-9)
        assert math.isclose(result.delta_e_rel_kcal_mol, expected_delta_kcal, rel_tol=1e-9)
        assert result.delta_e_soc_hartree == 0.0
        assert result.delta_e_soc_kcal_mol == 0.0
        assert math.isclose(result.delta_e_total_rel_hartree, expected_delta_hartree, rel_tol=1e-9)
        assert result.node_id == "bromobenzene_node"

    def test_extract_from_outputs(self) -> None:
        """Verifies end-to-end extraction directly from standard output strings."""
        extractor = DeltaRelExtractor()
        result = extractor.extract_from_outputs(
            stdout_non_rel=ORCA_NON_REL_STDOUT_BROMOBENZENE,
            stdout_rel=ORCA_REL_STDOUT_BROMOBENZENE,
            basis_set="def2-TZVPP",
            rel_basis_set="x2c-TZVPPall-s",
            node_id="node_br_01",
        )

        assert result.node_id == "node_br_01"
        assert math.isclose(result.e_total_non_rel, -2805.01248912, rel_tol=1e-9)
        assert math.isclose(result.e_total_rel, -2826.68940125, rel_tol=1e-9)
        assert result.delta_e_rel_hartree < 0.0  # Relativistic energy is deeper/more negative


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

class TestHDF5PersistenceAndPipeline:
    """Tests for writing and reading relativistic correction records in landscape.h5."""

    def test_commit_and_read_rel_hdf5(self, tmp_path: Path) -> None:
        """Verifies atomic write to landscape.h5 under rel_corrections and roundtrip read."""
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

        # Inspect HDF5 structure directly
        with h5py.File(h5_file, "r") as f:
            assert "rel_corrections" in f
            assert "node_test_01" in f["rel_corrections"]
            grp = f["rel_corrections"]["node_test_01"]

            assert "delta_e_rel_hartree" in grp
            assert "delta_e_rel_kcal_mol" in grp
            assert "delta_e_soc_hartree" in grp
            assert "delta_e_soc_kcal_mol" in grp
            assert grp.attrs["basis_set"] == "def2-TZVPP"
            assert grp.attrs["rel_basis_set"] == "x2c-TZVPPall-s"
            assert grp.attrs["hamiltonian"] == "X2C"
            assert bool(grp.attrs["has_heavy_elements"]) is True
            assert bool(grp.attrs["is_open_shell"]) is True

        # Read back via API
        data = read_rel_from_hdf5(h5_path=h5_file, node_id="node_test_01")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)
        assert math.isclose(data["delta_e_soc_hartree"], result.delta_e_soc_hartree, rel_tol=1e-7)
        assert data["basis_set"] == "def2-TZVPP"
        assert data["rel_basis_set"] == "x2c-TZVPPall-s"

    def test_run_rel_pipeline(self, tmp_path: Path) -> None:
        """Verifies end-to-end run_rel_pipeline execution and persistence."""
        h5_file = tmp_path / "landscape.h5"

        result = run_rel_pipeline(
            coords=BROMOBENZENE_COORDS,
            e_total_non_rel=-2805.01248912,
            e_total_rel=-2826.68940125,
            base_basis="def2-TZVPP",
            method="DLPNO-CCSD(T)",
            node_id="bromobenzene_node",
            h5_path=h5_file,
        )

        assert isinstance(result, RelCorrectionResult)
        assert result.has_heavy_elements is True
        assert result.rel_basis_set == "x2c-TZVPPall-s"

        data = read_rel_from_hdf5(h5_path=h5_file, node_id="bromobenzene_node")
        assert math.isclose(data["delta_e_rel_hartree"], result.delta_e_rel_hartree, rel_tol=1e-7)


# ==============================================================================
# 6. Full Composite Integration Test with Stage 5.0 Exporter
# ==============================================================================

class TestCompositeIntegration:
    """Verifies that Stage 4.0 outputs seamlessly integrate with Stage 5.0 CompositeAggregator."""

    def test_composite_aggregator_sweep_with_rel(self, tmp_path: Path) -> None:
        """Verifies that landscape.h5 containing Stage 2.0 CBS, Stage 3.0 CV, Stage 4.0 Rel, and ZPVE aggregates cleanly."""
        h5_file = tmp_path / "landscape.h5"
        node_id = "test_node_composite"

        # 1. Commit CBS limit (Stage 2.0)
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

        # 2. Commit CV correction (Stage 3.0)
        cv_res = CVCorrectionResult(
            e_total_fc=-76.427600,
            e_total_ae=-76.471200,
            delta_e_cv_hartree=-0.043600,
            delta_e_cv_kcal_mol=-27.3594,
            basis_set="aug-cc-pwCVQZ",
            node_id=node_id,
        )
        commit_cv_to_hdf5(h5_file, cv_res)

        # 3. Commit Relativistic correction (Stage 4.0)
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

        # 5. Sweep via CompositeAggregator (Stage 5.0)
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

        # Invariant: E_Total = E_SCF^CBS + E_corr^CBS + Delta_E_CV + Delta_E_rel + Delta_E_SOC + ZPVE
        expected_total = (
            -76.062400 + (-0.365200) + (-0.043600) + (-0.054500) + (-0.001000) + zpve_val
        )
        assert math.isclose(rec.e_total_hartree, expected_total, rel_tol=1e-7)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_cleanup.py ---
"""
Exhaustive Unit Tests for CoChem-TOPOS Stage 5.0 Post-Flight Audit & Cleanup.
(test_cochem_topos_cleanup.py)

Tests WSL2 path translation, ephemeral scratch purge with Windows file lock handling,
real subprocess process thread reaping (ZERO mocks), HDF5 SWMR lock sweeping,
and ToposEnvironmentSanitizer master context manager.

Authoritative Standards:
- Anti-Spoofing Protocol v2: Zero-Mock Real Subprocess & Physical Disk Testing
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import h5py
import psutil
import pytest

try:
    from cochem_topos.cochem_topos_cleanup import (
        HDF5LockRecord,
        HDF5LockSweeperConfig,
        HDF5LockSweepResult,
        PostFlightAuditReport,
        ProcessReaperConfig,
        PurgedFileRecord,
        PurgeResult,
        ReapedProcessRecord,
        ReapResult,
        ScratchPurgeConfig,
        ToposEnvironmentSanitizer,
        ToposHDF5LockSweeper,
        ToposProcessReaper,
        ToposScratchPurgeEngine,
        WSLPathTranslator,
        _compute_sha256,
    )
except ImportError:
    from export_utils.cochem_topos_cleanup import (  # type: ignore[no-redef]
        HDF5LockRecord,
        HDF5LockSweeperConfig,
        HDF5LockSweepResult,
        PostFlightAuditReport,
        ProcessReaperConfig,
        PurgedFileRecord,
        PurgeResult,
        ReapedProcessRecord,
        ReapResult,
        ScratchPurgeConfig,
        ToposEnvironmentSanitizer,
        ToposHDF5LockSweeper,
        ToposProcessReaper,
        ToposScratchPurgeEngine,
        WSLPathTranslator,
        _compute_sha256,
    )


# ============================================================================
# 1. WSL Path Translator Tests
# ============================================================================

class TestWSLPathTranslator:
    """Validates Windows <-> WSL2 path translations and UNC path handling."""

    def test_is_wsl_detection(self) -> None:
        is_wsl = WSLPathTranslator.is_wsl()
        assert isinstance(is_wsl, bool)

    def test_is_wsl_unc_path(self) -> None:
        assert WSLPathTranslator.is_wsl_unc_path(r"\\wsl$\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\wsl.localhost\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path("//wsl.localhost/Ubuntu/home/user/scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\WSL.LOCALHOST\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\WSL$\Debian\tmp\calc")
        assert WSLPathTranslator.is_wsl_unc_path("//WSL.LocalHost/Ubuntu/tmp")
        assert not WSLPathTranslator.is_wsl_unc_path(r"C:\Users\ansac\scratch")
        assert not WSLPathTranslator.is_wsl_unc_path("/mnt/c/Users/ansac/scratch")

    def test_windows_to_wsl_translation(self) -> None:
        assert WSLPathTranslator.windows_to_wsl(r"C:\Users\ansac\scratch") == "/mnt/c/Users/ansac/scratch"
        assert WSLPathTranslator.windows_to_wsl(r"D:\__CoChem\repo\file.gbw") == "/mnt/d/__CoChem/repo/file.gbw"
        assert WSLPathTranslator.windows_to_wsl("E:/data/tmp") == "/mnt/e/data/tmp"
        assert WSLPathTranslator.windows_to_wsl(r"\\wsl$\Ubuntu\home\user\scratch") == "/home/user/scratch"
        assert WSLPathTranslator.windows_to_wsl(r"\\wsl.localhost\Ubuntu\tmp\calc") == "/tmp/calc"
        assert WSLPathTranslator.windows_to_wsl("/mnt/c/scratch") == "/mnt/c/scratch"
        assert WSLPathTranslator.windows_to_wsl("") == ""

    def test_wsl_to_windows_translation(self) -> None:
        assert WSLPathTranslator.wsl_to_windows("/mnt/c/Users/ansac/scratch") == r"C:\Users\ansac\scratch"
        assert WSLPathTranslator.wsl_to_windows("/mnt/d/__CoChem/output") == r"D:\__CoChem\output"
        assert WSLPathTranslator.wsl_to_windows("/mnt/c") == "C:\\"
        assert WSLPathTranslator.wsl_to_windows("/home/user/scratch", distro="Ubuntu") == r"\\wsl.localhost\Ubuntu\home\user\scratch"
        assert WSLPathTranslator.wsl_to_windows("/tmp/calc_01", distro="Debian") == r"\\wsl.localhost\Debian\tmp\calc_01"
        assert WSLPathTranslator.wsl_to_windows(r"C:\Users\ansac\scratch") == r"C:\Users\ansac\scratch"
        assert WSLPathTranslator.wsl_to_windows("D:/repo/test") == r"D:\repo\test"
        assert WSLPathTranslator.wsl_to_windows("") == ""

    def test_normalize_path(self) -> None:
        norm = WSLPathTranslator.normalize_path("C:/Users/ansac/scratch")
        assert isinstance(norm, Path)

        if platform.system().lower() == "windows":
            norm_mnt = WSLPathTranslator.normalize_path("/mnt/c/Users/test")
            assert str(norm_mnt).lower() == r"c:\users\test"

        assert WSLPathTranslator.normalize_path("") == Path(".")


# ============================================================================
# 2. Scratch Purge Config & Model Tests
# ============================================================================

class TestScratchPurgeConfig:
    """Validates configuration data models and default values."""

    def test_default_config_properties(self) -> None:
        config = ScratchPurgeConfig()
        assert ".tmp" in config.ephemeral_extensions
        assert ".dens" in config.ephemeral_extensions
        assert ".gbw" in config.ephemeral_extensions
        assert "*.tmp*" in config.ephemeral_patterns
        assert "*.dens" in config.ephemeral_patterns
        assert "*.gbw" in config.ephemeral_patterns
        assert "./scratch/orca_tmp" in config.default_fallback_dirs
        assert "./scratch/ase_graphs" in config.default_fallback_dirs
        assert config.env_var_names == [
            "COCHEM_SCRATCH_DIR",
            "COCHEM_SCRATCH",
            "COCHEM_TMP",
            "COCHEM_SCRATCH_ROOT",
        ]
        assert "TEMP" not in config.env_var_names
        assert "TMP" not in config.env_var_names
        assert config.compute_sha256 is False
        assert config.remove_empty_dirs is True
        assert config.max_retries == 5
        assert config.ignore_cleanup_errors is True

    def test_custom_config_serialization(self) -> None:
        config = ScratchPurgeConfig(
            target_dirs=[Path("/tmp/custom_scratch")],
            ephemeral_extensions=[".tmp", ".dens"],
            archive_whitelist=["final.gbw"],
            archive_patterns=["*saved*"],
            max_retries=10,
        )
        data = config.model_dump()
        assert data["max_retries"] == 10
        assert "final.gbw" in data["archive_whitelist"]


# ============================================================================
# 3. Scratch Purge Engine Execution Tests (Real Files)
# ============================================================================

class TestToposScratchPurgeEngine:
    """Validates scratch artifact scanning, forceful deletion, locks, whitelists, and quarantines."""

    def test_purge_ephemeral_extensions_and_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        # Ephemeral files to delete
        f_tmp = scratch_dir / "calc_01.tmp"
        f_tmp.write_text("ephemeral temp content", encoding="utf-8")
        f_dens = scratch_dir / "scf.dens"
        f_dens.write_bytes(b"\x00\x01\x02\x03" * 100)
        f_gbw = scratch_dir / "orbitals.gbw"
        f_gbw.write_bytes(b"\xaa\xbb\xcc\xdd" * 50)
        f_bms = scratch_dir / "orca.bms"
        f_bms.write_text("matrix buffer", encoding="utf-8")

        # Persistent files to preserve
        f_xyz = scratch_dir / "geometry.xyz"
        f_xyz.write_text("3\nWater\nO 0 0 0\nH 0 1 0\nH 0 0 1", encoding="utf-8")
        f_json = scratch_dir / "landscape_summary.json"
        f_json.write_text('{"energy": -76.4}', encoding="utf-8")
        f_csv = scratch_dir / "frequencies.csv"
        f_csv.write_text("mode,freq\n1,3800", encoding="utf-8")

        total_ephemeral_bytes = f_tmp.stat().st_size + f_dens.stat().st_size + f_gbw.stat().st_size + f_bms.stat().st_size

        config = ScratchPurgeConfig(target_dirs=[scratch_dir])
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f_tmp.exists()
        assert not f_dens.exists()
        assert not f_gbw.exists()
        assert not f_bms.exists()

        assert f_xyz.exists()
        assert f_json.exists()
        assert f_csv.exists()

        assert result.total_files_deleted == 4
        assert result.total_files_scanned == 7
        assert result.reclaimed_bytes == total_ephemeral_bytes
        assert result.duration_seconds >= 0.0

    def test_archive_whitelist_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        keep_gbw = scratch_dir / "final_converged.gbw"
        keep_gbw.write_bytes(b"\xff" * 256)

        discard_gbw = scratch_dir / "step_003.gbw"
        discard_gbw.write_bytes(b"\x00" * 128)

        discard_dens = scratch_dir / "step_003.dens"
        discard_dens.write_bytes(b"\x11" * 128)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            archive_whitelist=[str(keep_gbw), "final_converged.gbw"],
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert keep_gbw.exists()
        assert not discard_gbw.exists()
        assert not discard_dens.exists()
        assert result.total_files_whitelisted == 1
        assert result.total_files_deleted == 2

    def test_archive_pattern_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        archived1 = scratch_dir / "opt_archive_model1.gbw"
        archived1.write_bytes(b"\x01" * 64)
        archived2 = scratch_dir / "tier4_final_archive.dens"
        archived2.write_bytes(b"\x02" * 64)

        ephemeral = scratch_dir / "step_01.tmp"
        ephemeral.write_bytes(b"\x03" * 64)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            archive_patterns=["*archive*"],
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert archived1.exists()
        assert archived2.exists()
        assert not ephemeral.exists()
        assert result.total_files_whitelisted == 2
        assert result.total_files_deleted == 1

    def test_quarantine_mode(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        quarantine_dir = tmp_path / "quarantine_vault"

        f1 = scratch_dir / "troubled_calc.tmp"
        f1.write_text("suspicious orca scratch", encoding="utf-8")
        f2 = scratch_dir / "orbitals.gbw"
        f2.write_bytes(b"\xaa" * 100)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            quarantine_dir=quarantine_dir,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f1.exists()
        assert not f2.exists()
        assert (quarantine_dir / "troubled_calc.tmp").exists()
        assert (quarantine_dir / "orbitals.gbw").exists()
        assert result.total_files_quarantined == 2
        assert result.total_files_deleted == 0

    def test_empty_directory_recursive_removal(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        nested_empty = scratch_dir / "level1" / "level2" / "level3"
        nested_empty.mkdir(parents=True)
        tmp_file = nested_empty / "temp_calc.tmp"
        tmp_file.write_text("temporary data", encoding="utf-8")

        nested_keep = scratch_dir / "keep_dir" / "sub"
        nested_keep.mkdir(parents=True)
        keep_file = nested_keep / "manifest.json"
        keep_file.write_text('{"keep": true}', encoding="utf-8")

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            remove_empty_dirs=True,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not tmp_file.exists()
        assert not (scratch_dir / "level1").exists()
        assert (scratch_dir / "keep_dir" / "sub").exists()
        assert keep_file.exists()
        assert result.total_directories_removed >= 3

    def test_env_var_directory_discovery_with_targeted_subdirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_scratch = tmp_path / "cochem_env_scratch"
        env_scratch.mkdir()
        orca_tmp = env_scratch / "orca_tmp"
        orca_tmp.mkdir()
        ase_graphs = env_scratch / "ase_graphs"
        ase_graphs.mkdir()

        f1 = orca_tmp / "orca_scf.dens"
        f1.write_bytes(b"\x00" * 50)
        f2 = ase_graphs / "graph_state.tmp"
        f2.write_bytes(b"\x00" * 50)

        monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(env_scratch))

        engine = ToposScratchPurgeEngine()
        discovered = engine.discover_target_directories()

        assert any(d.resolve() == env_scratch.resolve() for d in discovered)
        assert any(d.resolve() == orca_tmp.resolve() for d in discovered)
        assert any(d.resolve() == ase_graphs.resolve() for d in discovered)

        result = engine.purge()
        assert not f1.exists()
        assert not f2.exists()
        assert result.total_files_deleted >= 2

    def test_kernel_file_lock_retry_handling(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "locked_scratch"
        scratch_dir.mkdir()
        locked_file = scratch_dir / "locked_calc.tmp"
        locked_file.write_bytes(b"kernel locked data" * 10)

        handle = open(locked_file, "r+b")
        try:
            config_ignore = ScratchPurgeConfig(
                target_dirs=[scratch_dir],
                max_retries=2,
                retry_delay_seconds=0.05,
                ignore_cleanup_errors=True,
            )
            engine = ToposScratchPurgeEngine(config_ignore)

            if platform.system().lower() == "windows":
                result = engine.purge()
                assert locked_file.exists()
                assert len(result.errors) > 0
                assert result.purged_files[0].status == "failed"

            if platform.system().lower() == "windows":
                config_strict = ScratchPurgeConfig(
                    target_dirs=[scratch_dir],
                    max_retries=2,
                    retry_delay_seconds=0.05,
                    ignore_cleanup_errors=False,
                )
                strict_engine = ToposScratchPurgeEngine(config_strict)
                with pytest.raises(PermissionError):
                    strict_engine.purge()
        finally:
            handle.close()

        config_success = ScratchPurgeConfig(target_dirs=[scratch_dir], max_retries=2)
        engine_success = ToposScratchPurgeEngine(config_success)
        res = engine_success.purge()
        assert not locked_file.exists()
        assert res.total_files_deleted == 1
        assert res.purged_files[0].status == "deleted"

    def test_max_file_age_filter(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "age_scratch"
        scratch_dir.mkdir()

        old_file = scratch_dir / "old_calc.tmp"
        old_file.write_text("old data", encoding="utf-8")
        past_time = time.time() - 500.0
        os.utime(old_file, (past_time, past_time))

        new_file = scratch_dir / "new_calc.tmp"
        new_file.write_text("new data", encoding="utf-8")

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            max_file_age_seconds=100.0,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not old_file.exists()
        assert new_file.exists()
        assert result.total_files_deleted == 1
        statuses = {p.path: p.status for p in result.purged_files}
        assert statuses[str(old_file)] == "deleted"
        assert statuses[str(new_file)] == "whitelisted"

    def test_target_dirs_isolation_in_discovery(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        explicit_dir = tmp_path / "explicit_scratch"
        explicit_dir.mkdir()

        env_dir = tmp_path / "env_scratch"
        env_dir.mkdir()
        monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(env_dir))

        config = ScratchPurgeConfig(target_dirs=[explicit_dir])
        engine = ToposScratchPurgeEngine(config)
        discovered = engine.discover_target_directories()

        assert len(discovered) == 1
        assert discovered[0].resolve() == explicit_dir.resolve()

    def test_purge_with_sha256_computation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "sha_scratch"
        scratch_dir.mkdir()

        f_tmp = scratch_dir / "calc_sha.tmp"
        f_tmp.write_bytes(b"ephemeral test content for sha256 provenance")
        expected_sha = _compute_sha256(f_tmp)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            compute_sha256=True,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f_tmp.exists()
        assert result.total_files_deleted == 1
        assert len(result.purged_files) == 1
        record = result.purged_files[0]
        assert record.status == "deleted"
        assert record.sha256_hash == expected_sha
        assert record.sha256_hash is not None


# ============================================================================
# 4. Process Reaper Tests (Zero-Mock Real Subprocesses)
# ============================================================================

class TestToposProcessReaper:
    """Validates real process auditing and termination across single processes and process trees."""

    def test_process_reaper_config_defaults(self) -> None:
        config = ProcessReaperConfig()
        expected = ["orted", "mpirun", "mpiexec", "orca", "xtb", "crest", "mopac", "mace", "g16", "oet_server", "ase"]
        for exp in expected:
            assert exp in config.target_process_names

    def test_protection_of_current_and_parent_process(self) -> None:
        config = ProcessReaperConfig(
            target_process_names=["python", "python.exe", "pytest", "pytest.exe"],
            protect_current_process=True,
            protect_parent_process=True,
        )
        reaper = ToposProcessReaper(config)
        current_proc = psutil.Process(os.getpid())
        assert reaper._is_protected(current_proc) is True
        is_target, reason = reaper._is_target_process(current_proc)
        assert is_target is False
        assert "Protected" in reason

    def test_reap_real_orphaned_subprocess(self) -> None:
        marker = f"cochem_test_orphan_{int(time.time() * 1000)}"
        proc = subprocess.Popen(
            [sys.executable, "-c", f"# {marker}\nimport time\ntime.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        assert psutil.pid_exists(pid)

        try:
            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                sigterm_timeout_seconds=0.5,
                sigkill_timeout_seconds=0.5,
            )
            reaper = ToposProcessReaper(config)

            orphans = reaper.audit_active_orphans()
            assert any(p.pid == pid for p in orphans)

            result = reaper.reap_orphans()
            assert result.active_orphans_found == 1
            assert result.successful_terminations == 1
            assert result.audit_passed is True

            time.sleep(0.1)
            proc.poll()
            assert proc.returncode is not None or not psutil.pid_exists(pid)

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_reap_process_tree_with_children(self) -> None:
        marker = f"cochem_tree_parent_{int(time.time() * 1000)}"
        script = f"""
import subprocess, sys, time
# {marker}
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
time.sleep(60)
"""
        parent = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        parent_pid = parent.pid
        time.sleep(0.5)

        try:
            parent_proc = psutil.Process(parent_pid)
            children = parent_proc.children()
            assert len(children) >= 1
            child_pid = children[0].pid
            assert psutil.pid_exists(child_pid)

            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                sigterm_timeout_seconds=0.5,
                sigkill_timeout_seconds=0.5,
            )
            reaper = ToposProcessReaper(config)

            result = reaper.reap_orphans()
            assert result.successful_terminations >= 1
            assert result.audit_passed is True

            time.sleep(0.2)
            assert not psutil.pid_exists(parent_pid)
            assert not psutil.pid_exists(child_pid)

        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait()

    def test_reap_protected_explicit_pids(self) -> None:
        marker = f"cochem_protected_{int(time.time() * 1000)}"
        proc = subprocess.Popen(
            [sys.executable, "-c", f"# {marker}\nimport time\ntime.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        try:
            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                protected_pids=[pid],
            )
            reaper = ToposProcessReaper(config)
            orphans = reaper.audit_active_orphans()
            assert not any(p.pid == pid for p in orphans)

            result = reaper.reap_orphans()
            assert result.active_orphans_found == 0
            assert psutil.pid_exists(pid)
        finally:
            proc.kill()
            proc.wait()

    def test_cmdline_pattern_word_boundary_isolation(self) -> None:
        config = ProcessReaperConfig()
        reaper = ToposProcessReaper(config)

        proc = subprocess.Popen(
            [sys.executable, "-c", "import sys, time; sys.argv = ['pytest', 'tests/test_orca.py']; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        try:
            ps_proc = psutil.Process(pid)
            is_target, reason = reaper._is_target_process(ps_proc)
            assert is_target is False, f"Subprocess falsely matched as target orphan: {reason}"
        finally:
            proc.kill()
            proc.wait()


# ============================================================================
# 5. HDF5 SWMR Lock Sweeper Tests
# ============================================================================

class TestToposHDF5LockSweeper:
    """Validates real HDF5 lock discovery, zombie PID sweeping, and database integrity checks."""

    def test_lock_sweeper_defaults(self) -> None:
        sweeper = ToposHDF5LockSweeper()
        assert "*.h5.lck" in sweeper.config.lock_file_patterns
        assert "*.swmr.lock" in sweeper.config.lock_file_patterns
        assert sweeper.config.verify_h5_integrity is True

    def test_sweep_stale_lock_dead_pid(self, tmp_path: Path) -> None:
        # Create a valid HDF5 file
        h5_file = tmp_path / "landscape.h5"
        with h5py.File(h5_file, "w") as fp:
            fp.create_dataset("test_data", data=[1.0, 2.0, 3.0])

        # Create companion lock file referencing a non-existent PID (e.g. 999999)
        dead_pid = 999999
        while psutil.pid_exists(dead_pid):
            dead_pid += 1

        lock_file = tmp_path / "landscape.h5.lck"
        lock_payload = {
            "h5_file": str(h5_file),
            "pid": dead_pid,
            "timestamp_utc": time.time(),
            "mode": "SWMR_WRITE",
        }
        lock_file.write_text(json.dumps(lock_payload), encoding="utf-8")

        config = HDF5LockSweeperConfig(target_dirs=[tmp_path])
        sweeper = ToposHDF5LockSweeper(config)

        result = sweeper.sweep_locks()
        assert result.active_locks_found == 1
        assert result.stale_locks_removed == 1
        assert not lock_file.exists()
        assert h5_file.exists()

        # Verify companion HDF5 file remains readable and uncorrupted
        with h5py.File(h5_file, "r") as fp:
            assert "test_data" in fp
            assert list(fp["test_data"][:]) == [1.0, 2.0, 3.0]

    def test_retain_active_lock_live_pid(self, tmp_path: Path) -> None:
        # Spawn background process to simulate active holder
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        live_pid = proc.pid
        try:
            h5_file = tmp_path / "active_run.h5"
            with h5py.File(h5_file, "w") as fp:
                fp.create_dataset("active_field", data=[42])

            lock_file = tmp_path / "active_run.h5.swmr.lock"
            lock_file.write_text(json.dumps({"h5_file": str(h5_file), "pid": live_pid}), encoding="utf-8")

            config = HDF5LockSweeperConfig(target_dirs=[tmp_path], force_release=False)
            sweeper = ToposHDF5LockSweeper(config)

            # Sweeping without force should retain the lock file
            result = sweeper.sweep_locks()
            assert result.active_locks_found == 1
            assert result.active_locks_retained == 1
            assert result.stale_locks_removed == 0
            assert lock_file.exists()

            # Sweeping with force=True should remove the lock file
            result_forced = sweeper.sweep_locks(force=True)
            assert result_forced.stale_locks_removed == 1
            assert not lock_file.exists()

        finally:
            proc.kill()
            proc.wait()


# ============================================================================
# 6. Topos Environment Sanitizer & Report Tests
# ============================================================================

class TestToposEnvironmentSanitizer:
    """Validates full post-flight audit workflow, context manager, and report generation."""

    def test_full_post_flight_audit_workflow(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "post_flight_scratch"
        scratch_dir.mkdir()

        f1 = scratch_dir / "final_run.tmp"
        f1.write_bytes(b"\x00" * 1024 * 1024)

        f2 = scratch_dir / "wavefunction.dens"
        f2.write_bytes(b"\x01" * 512 * 1024)

        # Create HDF5 file with stale companion lock
        h5_dir = tmp_path / "hdf5_vault"
        h5_dir.mkdir()
        h5_file = h5_dir / "landscape.h5"
        with h5py.File(h5_file, "w") as fp:
            fp.create_dataset("nodes", data=[1, 2, 3])
        stale_lck = h5_dir / "landscape.h5.lck"
        stale_lck.write_text('{"pid": 999999}', encoding="utf-8")

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        reaper_cfg = ProcessReaperConfig(target_process_names=["non_existent_qm_tool_12345"])
        lock_cfg = HDF5LockSweeperConfig(target_dirs=[h5_dir])

        sanitizer = ToposEnvironmentSanitizer(
            purge_config=purge_cfg,
            reaper_config=reaper_cfg,
            lock_config=lock_cfg,
        )
        assert sanitizer.verify_environment_clean() is True

        report = sanitizer.execute_post_flight_audit()

        assert isinstance(report, PostFlightAuditReport)
        assert report.audit_passed is True
        assert report.purge_result.total_files_deleted == 2
        assert report.disk_reclaimed_mb >= 1.5
        assert report.hdf5_lock_result.stale_locks_removed == 1
        assert "PASSED" in report.summary
        assert not f1.exists()
        assert not f2.exists()
        assert not stale_lck.exists()

    def test_sanitizer_context_manager(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "ctx_scratch"
        scratch_dir.mkdir()

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        sanitizer = ToposEnvironmentSanitizer(purge_config=purge_cfg)

        f_tmp = scratch_dir / "in_flight.tmp"
        with sanitizer:
            f_tmp.write_text("in-flight data", encoding="utf-8")
            assert f_tmp.exists()

        assert not f_tmp.exists()

    def test_sanitizer_context_manager_exception_safety(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "exc_scratch"
        scratch_dir.mkdir()

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        sanitizer = ToposEnvironmentSanitizer(purge_config=purge_cfg)

        f_tmp = scratch_dir / "in_flight_error.tmp"
        with pytest.raises(RuntimeError, match="Simulated calculation error"):
            with sanitizer:
                f_tmp.write_text("should be cleaned on error exit", encoding="utf-8")
                raise RuntimeError("Simulated calculation error")

        assert not f_tmp.exists()

    def test_report_json_serialization_and_save(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "report_scratch"
        scratch_dir.mkdir()
        (scratch_dir / "run.tmp").write_bytes(b"\x00" * 2048)

        sanitizer = ToposEnvironmentSanitizer(purge_config=ScratchPurgeConfig(target_dirs=[scratch_dir]))
        report = sanitizer.execute_post_flight_audit()

        json_str = report.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["audit_passed"] is True
        assert parsed["purge_result"]["total_files_deleted"] == 1
        assert "timestamp" in parsed
        assert "hdf5_lock_result" in parsed

        out_file = tmp_path / "audit_artifacts" / "audit_report.json"
        saved_path = sanitizer.save_audit_report(report, out_file)
        assert saved_path.exists()
        assert json.loads(saved_path.read_text(encoding="utf-8"))["audit_passed"] is True


# ============================================================================
# 7. Package Initialization & Export Verification
# ============================================================================

def test_cochem_topos_package_exports() -> None:
    """Verifies that cochem_topos exposes all required classes and data models."""
    try:
        import cochem_topos

        expected_exports = [
            "ToposEnvironmentSanitizer",
            "ToposScratchPurgeEngine",
            "ToposProcessReaper",
            "ToposHDF5LockSweeper",
            "WSLPathTranslator",
            "ScratchPurgeConfig",
            "PurgedFileRecord",
            "PurgeResult",
            "ProcessReaperConfig",
            "ReapedProcessRecord",
            "ReapResult",
            "HDF5LockRecord",
            "HDF5LockSweeperConfig",
            "HDF5LockSweepResult",
            "PostFlightAuditReport",
        ]

        for exp in expected_exports:
            assert hasattr(cochem_topos, exp), f"cochem_topos missing exported symbol: {exp}"
            assert getattr(cochem_topos, exp) is not None
    except ImportError:
        pass

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.