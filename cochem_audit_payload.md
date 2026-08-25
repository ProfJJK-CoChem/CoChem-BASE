Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cv.md.
Original prompt:
# Task: Create/Update cochem_bench_cv.py

## Target File
`cochem_bench\bench_engine\cochem_bench_cv.py` (relative to repo root)

## Requirements
Implement Stage 3.0: Core-Valence (CV) Correlation Correction.

Functions to implement:
1. `Execution Protocol`:
   - Dispatch two single-point jobs: Job A (Frozen-Core, default), Job B (All-Electron, injects `NoFrozenCore`).
   - Use `subprocess.run([BenchRunContext.orca_binary_path, input_file])` to execute the jobs using the validated engine path.
   - Use correctly matched core-polarized basis sets by implementing this explicit string mapping: replace `"cc-pV"` with `"cc-pCV"` and `"aug-cc-pV"` with `"aug-cc-pwCV"`. For `"def2"`, no prefix change is needed.
   - Inject `CUDA_VISIBLE_DEVICES=""` to isolate accelerators.
2. `Delta Extractor`:
   - Parse `E_Total` from the ORCA output by searching for the exact literal string `"FINAL SINGLE POINT ENERGY"`.
   - Compute `Delta_E_CV = E_Total^(AE) - E_Total^(FC)`.
3. `Ephemeral Scratch Purge`:
   - Create isolated scratch directory: `job_scratch = pathlib.Path(os.environ["COCHEM_ARTIFACTS_DIR"]) / "BENCH_Workspace" / "Scratch" / f"job_{uuid.uuid4()}"`.
   - After extraction, execute cleanup via `pathlib.Path.glob()` unlinking `.gbw` and `.tmp` files, and remove the directory to prevent NVMe exhaustion.

## Safety Contract
- Air-Gap strictly enforced dynamically: NO absolute paths. Resolve paths via `os.environ["COCHEM_ARTIFACTS_DIR"]`.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_cv.py ---
#!/usr/bin/env python3
r"""Stage 3.0: Core-Valence (CV) Correlation Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_cv
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. CoreValenceMapper: Dynamically maps appropriate core-polarized basis sets
   (e.g., aug-cc-pwCVnZ, cc-pCVnZ) and inspects elemental core electron configurations
   via the Mendeleev library.
2. DualCorrelationEngine: Formulates and executes dual single-point evaluations
   comparing Frozen-Core (FC) against All-Electron (AE with NoFrozenCore) treatments,
   enforcing CUDA accelerator isolation (CUDA_VISIBLE_DEVICES="") and %maxcore memory limits.
   Executes jobs via subprocess.run([BenchRunContext.orca_binary_path, input_file]) with
   safe parameter extraction.
3. DeltaExtractor: Extracts FINAL SINGLE POINT ENERGY floats from authentic ORCA standard
   outputs and mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC).
4. EphemeralScratchPurge: Tripartite scratch workspace manager executing explicit sweeps
   and unlinking of .gbw, .tmp, and intermediate files immediately after energy extraction.
5. HDF5 Persistence: Commits computed CV corrections atomically to landscape.h5.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cv.md
"""

from __future__ import annotations

import datetime
import math
import os
import re
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class CVCorrectionError(Exception):
    """Base exception for Stage 3.0 Core-Valence correlation operations."""
    pass


class CVExecutionError(CVCorrectionError, RuntimeError):
    """Raised when ORCA calculation execution fails."""
    pass


class CVParsingError(CVCorrectionError, ValueError):
    """Raised when required energy signature cannot be extracted from ORCA output."""
    pass


class CVScratchPurgeError(CVCorrectionError, OSError):
    """Raised when scratch purging encounters an OS-level filesystem error."""
    pass


# ==============================================================================
# Data Models
# ==============================================================================

class CVCorrectionResult(BaseModel):
    """Structured result model for Core-Valence (CV) correlation energy corrections."""
    e_total_fc: float = Field(description="Frozen-Core total electronic energy in Hartree")
    e_total_ae: float = Field(description="All-Electron total electronic energy in Hartree")
    delta_e_cv_hartree: float = Field(description="Core-Valence correction delta (AE - FC) in Hartree")
    delta_e_cv_kcal_mol: float = Field(description="Core-Valence correction delta in kcal/mol")
    basis_set: str = Field(description="Core-polarized basis set used for calculations")
    original_basis_set: str = Field(default="", description="Original basis set before core-valence mapping")
    method: str = Field(default="DLPNO-CCSD(T)", description="Quantum chemistry method")
    has_core_electrons: bool = Field(default=True, description="True if molecule contains elements with core electrons (Z >= 3)")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution or provenance metadata")


# ==============================================================================
# 1. CoreValenceMapper
# ==============================================================================

class CoreValenceMapper:
    """Dynamically maps appropriate core-polarized basis sets and inspects elemental core configurations."""

    @staticmethod
    def map_basis_set(basis_set: str) -> str:
        """Maps standard valence basis sets to their corresponding core-polarized variants.
        
        Rules:
        - "aug-cc-pVnZ" -> "aug-cc-pwCVnZ"
        - "cc-pVnZ" -> "cc-pCVnZ"
        - "def2-*" -> unchanged (def2 family natively supports all-electron/core-valence)
        - "ano-*" -> unchanged (ANO basis sets are general contraction all-electron bases)
        """
        b_str = basis_set.strip()
        b_lower = b_str.lower()

        # Handle augmented correlation consistent sets first
        if "aug-cc-pv" in b_lower:
            pattern = re.compile(r"aug-cc-pv", re.IGNORECASE)
            return pattern.sub("aug-cc-pwCV", b_str)

        # Handle standard correlation consistent sets
        if "cc-pv" in b_lower:
            pattern = re.compile(r"cc-pv", re.IGNORECASE)
            return pattern.sub("cc-pCV", b_str)

        # def2 and ANO families do not require prefix modification
        return b_str

    @staticmethod
    def inspect_elemental_core(
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    ) -> Dict[str, Any]:
        """Inspects elemental composition using Mendeleev to determine core electron counts and molecular mass."""
        total_mass = 0.0
        total_electrons = 0
        total_core_electrons = 0
        elements_present: List[str] = []

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            z = int(elem_data.atomic_number)
            mass = float(elem_data.mass)

            total_mass += mass
            total_electrons += z
            if sym not in elements_present:
                elements_present.append(sym)

            # Core electron calculation:
            # Z = 1, 2 (H, He): 0 core electrons
            # Z = 3 - 10 (Li - Ne): 2 core electrons (1s^2 / [He])
            # Z = 11 - 18 (Na - Ar): 10 core electrons ([Ne])
            # Z = 19 - 36 (K - Kr): 18 core electrons ([Ar])
            # Z = 37 - 54 (Rb - Xe): 36 core electrons ([Kr])
            if z <= 2:
                core_e = 0
            elif z <= 10:
                core_e = 2
            elif z <= 18:
                core_e = 10
            elif z <= 36:
                core_e = 18
            elif z <= 54:
                core_e = 36
            else:
                core_e = 54

            total_core_electrons += core_e

        has_core = total_core_electrons > 0

        return {
            "has_core_electrons": has_core,
            "total_core_electrons": total_core_electrons,
            "total_electrons": total_electrons,
            "total_mass": total_mass,
            "elements": elements_present,
        }


# ==============================================================================
# 2. DualCorrelationEngine
# ==============================================================================

class DualCorrelationEngine:
    """Manages dual Frozen-Core vs All-Electron single-point ORCA calculation configurations."""

    def __init__(
        self,
        method: str = "DLPNO-CCSD(T)",
        base_basis: str = "aug-cc-pVTZ",
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        ram_safety_fraction: float = 0.75,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        extra_keywords: Optional[List[str]] = None,
    ) -> None:
        self.method = method
        self.base_basis = base_basis
        self.node_max_gb = float(node_max_gb)
        self.nprocs = max(1, int(nprocs))
        self.ram_safety_fraction = float(ram_safety_fraction)
        self.tight_scf = tight_scf
        self.defgrid = defgrid
        self.extra_keywords = list(extra_keywords) if extra_keywords else []

    def calculate_maxcore_per_thread(self) -> int:
        """Calculates strict per-process %maxcore in MB leaving headroom for OS and MPI runtime."""
        available_mb = self.node_max_gb * 1024.0 * self.ram_safety_fraction
        per_thread_mb = int(available_mb / self.nprocs)
        min_allowed = 250
        max_allowed = int((self.node_max_gb * 1024.0) / self.nprocs)
        candidate = max(min_allowed, per_thread_mb)
        return min(candidate, max_allowed)

    def prepare_execution_env(self) -> Dict[str, str]:
        """Prepares child subprocess execution environment, air-gapping GPUs via CUDA_VISIBLE_DEVICES=''."""
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    def generate_input_decks(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        charge: int = 0,
        mult: int = 1,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for Frozen-Core and All-Electron calculations."""
        mapper = CoreValenceMapper()
        mapped_basis = mapper.map_basis_set(self.base_basis)
        maxcore_mb = self.calculate_maxcore_per_thread()

        # Job A: Frozen-Core (default)
        fc_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=False,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        # Job B: All-Electron (NoFrozenCore)
        ae_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=True,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        decks = {
            "fc_input": fc_input,
            "ae_input": ae_input,
            "basis_set": mapped_basis,
            "original_basis": self.base_basis,
            "method": self.method,
            "maxcore_mb": maxcore_mb,
            "nprocs": self.nprocs,
            "charge": charge,
            "mult": mult,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / "orca_fc.inp").write_text(fc_input, encoding="utf-8")
            (out_path / "orca_ae.inp").write_text(ae_input, encoding="utf-8")

        return decks

    def _build_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        basis: str,
        is_all_electron: bool,
        charge: int,
        mult: int,
        maxcore_mb: int,
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck."""
        keywords = ["!", self.method, basis]
        if is_all_electron:
            keywords.append("NoFrozenCore")
        if self.tight_scf:
            keywords.append("TightSCF")
        if self.defgrid:
            keywords.append(self.defgrid)
        for kw in self.extra_keywords:
            if kw not in keywords:
                keywords.append(kw)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if self.nprocs > 1:
            lines.append(f"%pal nprocs {self.nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)

    def execute_job(
        self,
        input_text: str,
        orca_binary_path: Union[str, Path, List[str], Any],
        scratch_dir: Union[str, Path],
        job_prefix: str = "job",
        timeout_seconds: int = 7200,
    ) -> Tuple[str, str, int]:
        """Executes ORCA binary via subprocess inside isolated scratch with GPU air-gapping."""
        if hasattr(orca_binary_path, "orca_binary_path") and orca_binary_path.orca_binary_path:
            resolved_bin = orca_binary_path.orca_binary_path
        elif hasattr(orca_binary_path, "orca_path") and orca_binary_path.orca_path:
            resolved_bin = orca_binary_path.orca_path
        else:
            resolved_bin = orca_binary_path

        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        inp_file = scratch_path / f"{job_prefix}.inp"
        inp_file.write_text(input_text, encoding="utf-8")

        env = self.prepare_execution_env()

        if isinstance(resolved_bin, (list, tuple)):
            cmd = [str(x) for x in resolved_bin] + [str(inp_file)]
        else:
            cmd_str = str(resolved_bin).strip()
            if " " in cmd_str and not Path(cmd_str).exists():
                cmd = shlex.split(cmd_str, posix=False) + [str(inp_file)]
            else:
                cmd = [cmd_str, str(inp_file)]

        proc = subprocess.run(
            cmd,
            cwd=str(scratch_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode

    def execute_dual_sp(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        orca_binary: Union[str, Path, List[str], Any],
        charge: int = 0,
        mult: int = 1,
        node_id: str = "node_0",
        scratch_dir: Optional[Union[str, Path]] = None,
        timeout_seconds: int = 7200,
        auto_purge: bool = True,
    ) -> CVCorrectionResult:
        """Dispatches dual single-point jobs: Job A (Frozen-Core) and Job B (All-Electron).
        
        Executes via subprocess.run using the validated engine path, isolates accelerators,
        extracts FINAL SINGLE POINT ENERGY from stdout, and purges intermediate scratch files.
        """
        purger = EphemeralScratchPurge()
        if scratch_dir is None:
            job_scratch = purger.create_scratch_dir()
        else:
            job_scratch = Path(scratch_dir)
            job_scratch.mkdir(parents=True, exist_ok=True)

        decks = self.generate_input_decks(coords=coords, charge=charge, mult=mult)

        try:
            # Job A: Frozen-Core
            stdout_fc, stderr_fc, code_fc = self.execute_job(
                input_text=decks["fc_input"],
                orca_binary_path=orca_binary,
                scratch_dir=job_scratch,
                job_prefix="orca_fc",
                timeout_seconds=timeout_seconds,
            )
            if code_fc != 0:
                raise CVExecutionError(
                    f"Job A (Frozen-Core) execution failed with exit code {code_fc}: {stderr_fc}"
                )

            # Job B: All-Electron (NoFrozenCore)
            stdout_ae, stderr_ae, code_ae = self.execute_job(
                input_text=decks["ae_input"],
                orca_binary_path=orca_binary,
                scratch_dir=job_scratch,
                job_prefix="orca_ae",
                timeout_seconds=timeout_seconds,
            )
            if code_ae != 0:
                raise CVExecutionError(
                    f"Job B (All-Electron) execution failed with exit code {code_ae}: {stderr_ae}"
                )

            # Extract energies and compute delta
            extractor = DeltaExtractor()
            result = extractor.extract_from_outputs(
                stdout_fc=stdout_fc,
                stdout_ae=stdout_ae,
                basis_set=decks["basis_set"],
                original_basis=decks["original_basis"],
                method=self.method,
                node_id=node_id,
            )
            return result
        finally:
            if auto_purge:
                purger.purge_scratch_dir(job_scratch, remove_dir=True)


# ==============================================================================
# 3. DeltaExtractor
# ==============================================================================

class DeltaExtractor:
    """Extracts electronic energies from ORCA stdout streams and derives Core-Valence deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from standard ORCA output."""
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise CVParsingError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(match.group(1))

    @staticmethod
    def extract_delta(
        e_total_fc: float,
        e_total_ae: float,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
        delta_hartree = float(e_total_ae) - float(e_total_fc)
        delta_kcal = delta_hartree * HARTREE_TO_KCAL_MOL

        return CVCorrectionResult(
            e_total_fc=float(e_total_fc),
            e_total_ae=float(e_total_ae),
            delta_e_cv_hartree=delta_hartree,
            delta_e_cv_kcal_mol=delta_kcal,
            basis_set=basis_set,
            original_basis_set=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata or {},
        )

    def extract_from_outputs(
        self,
        stdout_fc: str,
        stdout_ae: str,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Parses energies directly from stdout texts and computes CV correction."""
        e_fc = self.parse_final_energy_from_stdout(stdout_fc)
        e_ae = self.parse_final_energy_from_stdout(stdout_ae)
        return self.extract_delta(
            e_total_fc=e_fc,
            e_total_ae=e_ae,
            basis_set=basis_set,
            original_basis=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 4. EphemeralScratchPurge
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
# 5. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves target landscape.h5 path dynamically adhering to Air-Gap mandate."""
    if h5_path is not None:
        target = Path(h5_path)
        if not target.is_absolute() and "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
            return (Path(os.environ["COCHEM_ARTIFACTS_DIR"]) / target).resolve()
        return target.resolve()

    if "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        artifacts_dir = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
        return (artifacts_dir / "BENCH_Workspace" / "landscape.h5").resolve()

    return Path("BENCH_Workspace/landscape.h5").resolve()


def commit_cv_to_hdf5(
    h5_path: Union[str, Path],
    result: CVCorrectionResult,
    timeout: float = 120.0,
) -> Path:
    """Commits computed Core-Valence correction results atomically to landscape.h5 using FileLock."""
    target_path = resolve_hdf5_path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    node_group_name = result.node_id if result.node_id else "default_cv_node"

    with lock:
        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("cv_corrections")
            node_grp = root_grp.require_group(node_group_name)

            datasets = {
                "e_total_fc": result.e_total_fc,
                "e_total_ae": result.e_total_ae,
                "delta_e_cv_hartree": result.delta_e_cv_hartree,
                "delta_e_cv_kcal_mol": result.delta_e_cv_kcal_mol,
            }

            for ds_name, ds_val in datasets.items():
                if ds_name in node_grp:
                    del node_grp[ds_name]
                node_grp.create_dataset(ds_name, data=float(ds_val))

            node_grp.attrs["basis_set"] = result.basis_set
            node_grp.attrs["original_basis_set"] = result.original_basis_set
            node_grp.attrs["method"] = result.method
            node_grp.attrs["has_core_electrons"] = bool(result.has_core_electrons)
            node_grp.attrs["timestamp"] = result.timestamp
            node_grp.attrs["node_id"] = result.node_id

    return target_path


def read_cv_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Reads back computed Core-Valence correction results atomically from landscape.h5 using FileLock."""
    target_path = resolve_hdf5_path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    with lock:
        with h5py.File(target_path, "r") as f:
            if "cv_corrections" not in f:
                raise KeyError(f"Root group 'cv_corrections' not found in '{target_path}'")
            root_grp = f["cv_corrections"]
            if node_id not in root_grp:
                raise KeyError(f"Node '{node_id}' not found in 'cv_corrections'")
            node_grp = root_grp[node_id]

            data = {
                "e_total_fc": float(node_grp["e_total_fc"][()]),
                "e_total_ae": float(node_grp["e_total_ae"][()]),
                "delta_e_cv_hartree": float(node_grp["delta_e_cv_hartree"][()]),
                "delta_e_cv_kcal_mol": float(node_grp["delta_e_cv_kcal_mol"][()]),
                "basis_set": str(node_grp.attrs.get("basis_set", "")),
                "original_basis_set": str(node_grp.attrs.get("original_basis_set", "")),
                "method": str(node_grp.attrs.get("method", "")),
                "has_core_electrons": bool(node_grp.attrs.get("has_core_electrons", True)),
                "timestamp": str(node_grp.attrs.get("timestamp", "")),
                "node_id": str(node_grp.attrs.get("node_id", "")),
            }
            return data


def run_cv_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_total_fc: Optional[float] = None,
    e_total_ae: Optional[float] = None,
    orca_binary: Optional[Union[str, Path, List[str], Any]] = None,
    base_basis: str = "aug-cc-pVQZ",
    method: str = "DLPNO-CCSD(T)",
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
    charge: int = 0,
    mult: int = 1,
    scratch_dir: Optional[Union[str, Path]] = None,
) -> CVCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 3.0 Core-Valence (CV) Correction."""
    mapper = CoreValenceMapper()
    mapped_basis = mapper.map_basis_set(base_basis)
    core_info = mapper.inspect_elemental_core(coords)

    if e_total_fc is not None and e_total_ae is not None:
        extractor = DeltaExtractor()
        result = extractor.extract_delta(
            e_total_fc=e_total_fc,
            e_total_ae=e_total_ae,
            basis_set=mapped_basis,
            original_basis=base_basis,
            method=method,
            has_core_electrons=core_info["has_core_electrons"],
            node_id=node_id,
            metadata={"core_info": core_info},
        )
    elif orca_binary is not None:
        engine = DualCorrelationEngine(
            method=method,
            base_basis=base_basis,
            node_max_gb=node_max_gb,
            nprocs=nprocs,
        )
        result = engine.execute_dual_sp(
            coords=coords,
            orca_binary=orca_binary,
            charge=charge,
            mult=mult,
            node_id=node_id,
            scratch_dir=scratch_dir,
        )
        result.metadata["core_info"] = core_info
    else:
        raise CVCorrectionError(
            "run_cv_pipeline requires either (e_total_fc, e_total_ae) or orca_binary to be supplied."
        )

    if h5_path:
        commit_cv_to_hdf5(h5_path=h5_path, result=result)

    return result

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_ingest.py ---
#!/usr/bin/env python3
r"""Stage 1.0: Stage 0 Handshake, Registry Polling, Hardware Governor, and Pre-Flight Engine.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_ingest
System Domain: CoChem-BENCH Ingestion Infrastructure

Key Capabilities:
1. Stage 0 Authority Rule & Atomic Polling (RegistryHandshake):
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR environment variable.
   - File locking using filelock.FileLock with a strict 10-second timeout.
   - Fatal interception if registry is absent, instructing user to run CoChem-CORE Stage 0 setup.
   - Strict Pydantic schema validation preventing hallucinated configurations or malformed types.
2. Dynamic %maxcore Calculation & Hardware Governor (HardwareGovernor):
   - Extraction of accessible RAM and physical silicon cores from the validated registry.
   - Reserving 15% headroom for host OS, OpenMPI daemons, and background telemetry brokers.
   - Mathematical formula: Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads).
   - Thread allocation: physical_cores - 1 if physical_cores > 4, else physical_cores.
   - Resource warnings when Safe_MaxCore_MB < 1500 MB.
   - Refusal to spawn heavy tensor contractions (e.g. DLPNO-CCSD(T)) if Safe_MaxCore_MB < 4000 MB.
3. Micro-Silo Verification & ABI Protection (SiloIntegrityAssert):
   - Strict assertion comparing sys.executable against silo_paths.bench_silo.
   - Ghost dependency purge: cleansing LD_LIBRARY_PATH to strip anaconda3/miniconda3 paths
     causing libtinfo.so.6 segfaults with ORCA while strictly preserving system MPI and compiler paths.
   - Dynamic extraction of ORCA executable path for downstream execution contexts.
4. Pre-Flight Verification & Execution Handoff (PreFlightVerification):
   - NVMe scratch space verification using PreFlightScratchVerifier from cochem_bench.bench_libraries.subprocess_reaper.
   - HDF5 workspace verification for landscape.h5.
   - Cryptographic provenance stamping: SHA-256 hash of configuration, Safe_MaxCore_MB, physical node ID,
     and ISO 8601 UTC timestamp assembled into an immutable read-only BenchRunContext dataclass.
5. Dynamic Mendeleev Integration: Dynamic mass querying when required.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 4 Registry Polling & The Stage 0 Handshake (Stage 1.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.finished_coding_prompts\draft_task4_ingest_pt1.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import filelock
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from cochem_bench.bench_libraries.subprocess_reaper import (
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    PreFlightScratchVerifier,
    ResourceGuardError as SubprocessResourceGuardError,
)
from cochem_core_registry_schema import (
    BYPASS_TOKENS,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    HPCConfig,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class BenchIngestBaseError(Exception):
    """Base exception for CoChem-BENCH ingestion and pre-flight operations."""
    pass


class RegistryHandshakeError(BenchIngestBaseError, EnvironmentError):
    """Raised when the Stage 0 Golden Registry is missing, unreadable, or invalid."""
    pass


class SiloIntegrityError(BenchIngestBaseError, RuntimeError):
    """Raised when the active Python runtime fails silo isolation assertions."""
    pass


class HardwareGovernorError(BenchIngestBaseError, ValueError):
    """Raised when hardware limits or calculations encounter fatal bounds."""
    pass


class ResourceGuardError(BenchIngestBaseError, RuntimeError):
    """Raised when available memory or scratch resources are insufficient for requested quantum methods."""
    pass


class PreFlightVerificationError(BenchIngestBaseError):
    """Raised when pre-flight hardware or environment checks fail."""
    pass


# ==============================================================================
# Rigid Pydantic Ingestion Schemas
# ==============================================================================

class BenchHardwareSchema(BaseModel):
    """Rigid compute hardware bounds for CoChem-BENCH execution."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible RAM in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Physical silicon CPU cores")
    allocatable_compute_cores: Optional[int] = Field(default=None, ge=0)
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    cpu_cores: Optional[int] = Field(default=None, ge=1)
    available_ram_gb: Optional[float] = Field(default=None, ge=0.0)
    vram_gb: float = Field(default=0.0, ge=0.0)
    gpu_profile: Optional[str] = Field(default="None")
    avx512_support: bool = Field(default=False)
    avx_512_capable: bool = Field(default=False)
    numa_nodes: int = Field(default=1, ge=1)
    host_id: Optional[str] = Field(default=None)
    os_target: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        # Synchronize RAM
        ram = d.get("ram_gb") or d.get("available_ram_gb")
        if ram is not None:
            try:
                ram_flt = float(ram)
                d["ram_gb"] = ram_flt
                d["available_ram_gb"] = ram_flt
            except (ValueError, TypeError):
                pass

        # Synchronize AVX-512
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])

        return d


class BenchSiloPathsSchema(BaseModel):
    """Pathing configurations for isolated execution micro-silos and scientific engines."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    bench_silo: Optional[str] = Field(default=None, description="Path to cochem_bench_silo python interpreter")
    orca_binary_path: Optional[str] = Field(default=None)
    orca_path: Optional[str] = Field(default=None)
    xtb_binary_path: Optional[str] = Field(default=None)
    xtb_path: Optional[str] = Field(default=None)
    mpirun_binary_path: Optional[str] = Field(default=None)
    mpirun_path: Optional[str] = Field(default=None)
    cfour_binary_path: Optional[str] = Field(default=None)
    cfour_path: Optional[str] = Field(default=None)
    aimnet2_server_path: Optional[str] = Field(default=None)
    aimnet2_path: Optional[str] = Field(default=None)
    python_path: Optional[str] = Field(default=None)
    silo_root: Optional[str] = Field(default=None)
    hdf5_pes_store_path: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_path_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        alias_pairs = [
            ("orca_binary_path", "orca_path"),
            ("xtb_binary_path", "xtb_path"),
            ("mpirun_binary_path", "mpirun_path"),
            ("cfour_binary_path", "cfour_path"),
            ("aimnet2_server_path", "aimnet2_path"),
        ]
        for canonical, alias in alias_pairs:
            if canonical in d and alias not in d:
                d[alias] = d[canonical]
            elif alias in d and canonical not in d:
                d[canonical] = d[alias]
        return d


class BenchConfigSchema(BaseModel):
    """Authoritative Stage 0 Ingestion Schema for CoChem-BENCH."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    status: Optional[str] = Field(default="LOCKED")
    hardware: BenchHardwareSchema = Field(..., description="Hardware topology and memory limits")
    environment: Optional[EnvironmentSchema] = Field(default=None)
    silo_paths: BenchSiloPathsSchema = Field(default_factory=BenchSiloPathsSchema)
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    engine_paths: Optional[EnginePaths] = None
    cost_heuristics: Optional[Dict[str, Any]] = None
    active_jobs: Optional[Dict[str, Any]] = None
    hpc: Optional[HPCConfig] = None
    quantum_settings: Optional[QuantumSettings] = None
    adaptive_routing: Optional[RoutingPolicy] = None
    silos: Optional[SiloConfig] = None
    registry_checksum: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def available_ram_gb(self) -> float:
        """Returns authoritative accessible RAM in GB."""
        return float(self.hardware.available_ram_gb or self.hardware.ram_gb)

    @property
    def physical_cores(self) -> int:
        """Returns physical silicon core count."""
        return int(self.hardware.physical_cpu_cores or self.hardware.cpu_physical_cores or self.hardware.cpu_cores or 1)


# ==============================================================================
# Immutable Results & Context Dataclasses
# ==============================================================================

@dataclasses.dataclass(frozen=True)
class HardwareGovernorResult:
    """Immutable result from HardwareGovernor calculations."""
    safe_maxcore_mb: int
    target_mpi_threads: int
    resource_warning: bool
    numa_nodes: int = 1


@dataclasses.dataclass(frozen=True)
class BenchRunContext:
    """Immutable read-only execution context for downstream Stage 2.0 - 5.0 modules."""
    config_hash: str
    safe_maxcore_mb: int
    target_mpi_threads: int
    node_id: str
    timestamp: str
    orca_path: Optional[str]
    hdf5_path: Path
    scratch_path: Path
    numa_nodes: int
    resource_warning: bool
    config: BenchConfigSchema

    @property
    def orca_binary_path(self) -> Optional[str]:
        return self.orca_path


# ==============================================================================
# Core Stage 1.0 Components
# ==============================================================================

def HardwareGovernor(
    cfg: BenchConfigSchema,
    requested_method: Optional[str] = None,
) -> HardwareGovernorResult:
    """Calculates safe %maxcore allocation per MPI thread and enforces memory bounds.

    The 85% Headroom Heuristic:
      Target_MPI_Threads = physical_cores - 1 if physical_cores > 4 else physical_cores
      Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads)

    Args:
        cfg: Validated BenchConfigSchema.
        requested_method: Optional method string (e.g. 'DLPNO-CCSD(T)').

    Returns:
        HardwareGovernorResult containing calculated limits and warning flags.

    Raises:
        ResourceGuardError: If DLPNO-CCSD(T) is requested and Safe_MaxCore_MB < 4000 MB.
    """
    ram_gb = cfg.available_ram_gb
    cores = cfg.physical_cores

    if cores > 4:
        target_mpi_threads = cores - 1
    else:
        target_mpi_threads = max(1, cores)

    safe_maxcore_mb = math.floor(((ram_gb * 1024.0) * 0.85) / target_mpi_threads)

    resource_warning = False
    if safe_maxcore_mb < 1500:
        resource_warning = True
        logger.warning(
            f"RESOURCE_WARNING: Calculated Safe_MaxCore_MB ({safe_maxcore_mb} MB) is below the recommended "
            f"1500 MB floor. High-memory jobs may experience severe page thrashing or OOM aborts."
        )

    if requested_method:
        method_clean = requested_method.lower().replace(" ", "").replace("_", "").replace("-", "")
        is_dlpno = "dlpno" in method_clean or "ccsd(t)" in method_clean
        if is_dlpno and safe_maxcore_mb < 4000:
            raise ResourceGuardError(
                f"RESOURCE_GUARD: Requested method '{requested_method}' requires at least 4000 MB per core, "
                f"but only {safe_maxcore_mb} MB is safely available ({ram_gb:.1f} GB RAM across "
                f"{target_mpi_threads} MPI threads). Refusing to spawn to prevent host OOM lockup."
            )

    return HardwareGovernorResult(
        safe_maxcore_mb=safe_maxcore_mb,
        target_mpi_threads=target_mpi_threads,
        resource_warning=resource_warning,
        numa_nodes=cfg.hardware.numa_nodes,
    )


def SiloIntegrityAssert(
    cfg: BenchConfigSchema,
    current_executable: Optional[Union[str, Path]] = None,
) -> None:
    """Asserts that execution is strictly contained within cochem_bench_silo.

    Args:
        cfg: Validated BenchConfigSchema.
        current_executable: Optional override for active Python executable path.

    Raises:
        SiloIntegrityError: If active executable does not match silo_paths.bench_silo.
    """
    bench_silo = cfg.silo_paths.bench_silo or cfg.silo_paths.python_path
    if not bench_silo or bench_silo in ("BYPASSED", "Not_Found", "missing"):
        return

    active_exe = Path(current_executable or sys.executable).resolve()
    target_silo = Path(bench_silo).resolve()

    if platform.system() == "Windows":
        is_match = str(active_exe).lower() == str(target_silo).lower()
    else:
        is_match = active_exe == target_silo

    if not is_match:
        raise SiloIntegrityError(
            f"ABI Protection Fault: CoChem-BENCH must be executed strictly within the cochem_bench_silo "
            f"to prevent binary collisions. Active runtime '{active_exe}' does not match registered "
            f"silo path '{target_silo}'."
        )


def cleanse_ld_library_path(
    env_val: Optional[str] = None,
    mutate_environ: bool = True,
) -> Optional[str]:
    """Cleanses LD_LIBRARY_PATH by stripping any paths containing anaconda3 or miniconda3.

    Strictly preserves system MPI, compiler, and OS library paths.

    Args:
        env_val: Optional explicit LD_LIBRARY_PATH string to cleanse.
        mutate_environ: Whether to update os.environ with the cleansed string.

    Returns:
        Cleansed LD_LIBRARY_PATH string or None if variable is unset or fully stripped.
    """
    raw = env_val if env_val is not None else os.environ.get("LD_LIBRARY_PATH")
    if not raw:
        if mutate_environ and "LD_LIBRARY_PATH" in os.environ and env_val is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None

    sep = os.pathsep
    entries = raw.split(sep)
    cleansed_entries: List[str] = []

    for entry in entries:
        norm = entry.strip().lower()
        if not norm:
            continue
        if "anaconda3" in norm or "miniconda3" in norm:
            logger.info(f"Stripping conda library path from LD_LIBRARY_PATH: {entry}")
            continue
        cleansed_entries.append(entry.strip())

    if cleansed_entries:
        cleansed_str = sep.join(cleansed_entries)
        if mutate_environ:
            os.environ["LD_LIBRARY_PATH"] = cleansed_str
        return cleansed_str
    else:
        if mutate_environ:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None


def extract_orca_path(cfg: BenchConfigSchema) -> Optional[str]:
    """Dynamically extracts the ORCA executable path from registry configuration."""
    if cfg.engine_paths and cfg.engine_paths.orca and cfg.engine_paths.orca.path:
        p = cfg.engine_paths.orca.path
        if p not in ("BYPASSED", "Not_Found", "missing"):
            return p

    if isinstance(cfg.engines, dict) and "orca" in cfg.engines:
        orca_val = cfg.engines["orca"]
        if isinstance(orca_val, dict) and orca_val.get("path"):
            p = orca_val["path"]
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)
        elif hasattr(orca_val, "path") and orca_val.path:
            p = orca_val.path
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)

    for candidate in (cfg.silo_paths.orca_binary_path, cfg.silo_paths.orca_path):
        if candidate and candidate not in ("BYPASSED", "Not_Found", "missing"):
            return candidate

    return None


def PreFlightVerification(
    cfg: BenchConfigSchema,
    artifacts_dir: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
) -> BenchRunContext:
    """Executes full pre-flight verification and returns an immutable BenchRunContext.

    Args:
        cfg: Validated BenchConfigSchema.
        artifacts_dir: Optional artifacts directory override.
        min_scratch_bytes: Optional required NVMe scratch space threshold in bytes.
        requested_method: Optional quantum chemistry method string.
        current_executable: Optional current python executable override.

    Returns:
        Immutable BenchRunContext dataclass.

    Raises:
        SiloIntegrityError: If runtime does not match bench_silo.
        ResourceGuardError: If scratch space or RAM envelope is insufficient.
        RegistryHandshakeError: If artifacts directory is missing.
    """
    # 1. Micro-silo integrity assertion
    SiloIntegrityAssert(cfg, current_executable=current_executable)

    # 2. Ghost dependency purge: cleanse LD_LIBRARY_PATH
    cleanse_ld_library_path(mutate_environ=True)

    # 3. Hardware Governor validation
    gov_result = HardwareGovernor(cfg, requested_method=requested_method)

    # 4. Resolve artifacts directory
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "COCHEM_ARTIFACTS_DIR environment variable is not defined for Pre-Flight verification."
        )

    # 5. Verify scratch space via PreFlightScratchVerifier
    try:
        verifier = PreFlightScratchVerifier(artifacts_dir=resolved_artifacts)
        scratch_report = verifier.verify(min_free_bytes=min_scratch_bytes)
        scratch_path = Path(scratch_report.scratch_path).resolve()
    except SubprocessResourceGuardError as err:
        raise ResourceGuardError(str(err)) from err

    # 6. Verify HDF5 path in workspace
    workspace_dir = resolved_artifacts / "BENCH_Workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = workspace_dir / "landscape.h5"

    # 7. Stamp provenance
    cfg_json = cfg.model_dump_json()
    config_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    node_id = cfg.hardware.host_id or platform.node() or "cochem_node"
    now_ts = datetime.now(timezone.utc).isoformat()
    orca_path = extract_orca_path(cfg)

    return BenchRunContext(
        config_hash=config_hash,
        safe_maxcore_mb=gov_result.safe_maxcore_mb,
        target_mpi_threads=gov_result.target_mpi_threads,
        node_id=node_id,
        timestamp=now_ts,
        orca_path=orca_path,
        hdf5_path=hdf5_path,
        scratch_path=scratch_path,
        numa_nodes=gov_result.numa_nodes,
        resource_warning=gov_result.resource_warning,
        config=cfg,
    )


def RegistryHandshake(
    artifacts_dir: Optional[Union[str, Path]] = None,
    timeout: float = 10.0,
) -> BenchConfigSchema:
    """Executes Stage 0 Handshake by atomically polling cochem_system_config.json.

    Args:
        artifacts_dir: Optional explicit artifacts root directory path.
        timeout: Maximum time in seconds to wait for filelock acquisition.

    Returns:
        Validated BenchConfigSchema instance.

    Raises:
        RegistryHandshakeError: If COCHEM_ARTIFACTS_DIR is unset, registry is absent,
                                lock acquisition times out, or validation fails.
    """
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "Stage 0 Handshake Error: COCHEM_ARTIFACTS_DIR environment variable is not defined. "
            "CoChem-BENCH requires an active artifacts directory to resolve system configuration."
        )

    config_path = resolved_artifacts / "Registry" / "cochem_system_config.json"
    if not config_path.exists():
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: CoChem system configuration registry not found at '{config_path}'. "
            "Please run CoChem-CORE Stage 0 setup to initialize the system registry."
        )

    lock_file = config_path.parent / f"{config_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    try:
        with lock:
            raw_text = config_path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
    except filelock.Timeout:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Timeout: Failed to acquire read lock on '{config_path}' within {timeout}s."
        )
    except json.JSONDecodeError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry JSON at '{config_path}' is corrupted: {err}"
        ) from err

    try:
        cfg = BenchConfigSchema.model_validate(raw_data)
    except ValidationError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry at '{config_path}' failed strict Pydantic validation: {err}"
        ) from err

    return cfg


def run_bench_ingest_pipeline(
    artifacts_dir: Optional[Union[str, Path]] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    handshake_timeout: float = 10.0,
) -> BenchRunContext:
    """Executes the complete Stage 1.0 Registry Handshake & Pre-Flight Verification pipeline."""
    cfg = RegistryHandshake(artifacts_dir=artifacts_dir, timeout=handshake_timeout)
    return PreFlightVerification(
        cfg=cfg,
        artifacts_dir=artifacts_dir,
        min_scratch_bytes=min_scratch_bytes,
        requested_method=requested_method,
        current_executable=current_executable,
    )

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
]


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_engine\cochem_bench_ingest.py ---
#!/usr/bin/env python3
r"""Stage 1.0: Stage 0 Handshake, Registry Polling, Hardware Governor, and Pre-Flight Engine.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_ingest
System Domain: CoChem-BENCH Ingestion Infrastructure

Key Capabilities:
1. Stage 0 Authority Rule & Atomic Polling (RegistryHandshake):
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR environment variable.
   - File locking using filelock.FileLock with a strict 10-second timeout.
   - Fatal interception if registry is absent, instructing user to run CoChem-CORE Stage 0 setup.
   - Strict Pydantic schema validation preventing hallucinated configurations or malformed types.
2. Dynamic %maxcore Calculation & Hardware Governor (HardwareGovernor):
   - Extraction of accessible RAM and physical silicon cores from the validated registry.
   - Reserving 15% headroom for host OS, OpenMPI daemons, and background telemetry brokers.
   - Mathematical formula: Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads).
   - Thread allocation: physical_cores - 1 if physical_cores > 4, else physical_cores.
   - Resource warnings when Safe_MaxCore_MB < 1500 MB.
   - Refusal to spawn heavy tensor contractions (e.g. DLPNO-CCSD(T)) if Safe_MaxCore_MB < 4000 MB.
3. Micro-Silo Verification & ABI Protection (SiloIntegrityAssert):
   - Strict assertion comparing sys.executable against silo_paths.bench_silo.
   - Ghost dependency purge: cleansing LD_LIBRARY_PATH to strip anaconda3/miniconda3 paths
     causing libtinfo.so.6 segfaults with ORCA while strictly preserving system MPI and compiler paths.
   - Dynamic extraction of ORCA executable path for downstream execution contexts.
4. Pre-Flight Verification & Execution Handoff (PreFlightVerification):
   - NVMe scratch space verification using PreFlightScratchVerifier from cochem_bench.bench_libraries.subprocess_reaper.
   - HDF5 workspace verification for landscape.h5.
   - Cryptographic provenance stamping: SHA-256 hash of configuration, Safe_MaxCore_MB, physical node ID,
     and ISO 8601 UTC timestamp assembled into an immutable read-only BenchRunContext dataclass.
5. Dynamic Mendeleev Integration: Dynamic mass querying when required.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 4 Registry Polling & The Stage 0 Handshake (Stage 1.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.finished_coding_prompts\draft_task4_ingest_pt1.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import filelock
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from cochem_bench.bench_libraries.subprocess_reaper import (
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    PreFlightScratchVerifier,
    ResourceGuardError as SubprocessResourceGuardError,
)
from cochem_core_registry_schema import (
    BYPASS_TOKENS,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    HPCConfig,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class BenchIngestBaseError(Exception):
    """Base exception for CoChem-BENCH ingestion and pre-flight operations."""
    pass


class RegistryHandshakeError(BenchIngestBaseError, EnvironmentError):
    """Raised when the Stage 0 Golden Registry is missing, unreadable, or invalid."""
    pass


class SiloIntegrityError(BenchIngestBaseError, RuntimeError):
    """Raised when the active Python runtime fails silo isolation assertions."""
    pass


class HardwareGovernorError(BenchIngestBaseError, ValueError):
    """Raised when hardware limits or calculations encounter fatal bounds."""
    pass


class ResourceGuardError(BenchIngestBaseError, RuntimeError):
    """Raised when available memory or scratch resources are insufficient for requested quantum methods."""
    pass


class PreFlightVerificationError(BenchIngestBaseError):
    """Raised when pre-flight hardware or environment checks fail."""
    pass


# ==============================================================================
# Rigid Pydantic Ingestion Schemas
# ==============================================================================

class BenchHardwareSchema(BaseModel):
    """Rigid compute hardware bounds for CoChem-BENCH execution."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible RAM in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Physical silicon CPU cores")
    allocatable_compute_cores: Optional[int] = Field(default=None, ge=0)
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    cpu_cores: Optional[int] = Field(default=None, ge=1)
    available_ram_gb: Optional[float] = Field(default=None, ge=0.0)
    vram_gb: float = Field(default=0.0, ge=0.0)
    gpu_profile: Optional[str] = Field(default="None")
    avx512_support: bool = Field(default=False)
    avx_512_capable: bool = Field(default=False)
    numa_nodes: int = Field(default=1, ge=1)
    host_id: Optional[str] = Field(default=None)
    os_target: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        # Synchronize RAM
        ram = d.get("ram_gb") or d.get("available_ram_gb")
        if ram is not None:
            try:
                ram_flt = float(ram)
                d["ram_gb"] = ram_flt
                d["available_ram_gb"] = ram_flt
            except (ValueError, TypeError):
                pass

        # Synchronize AVX-512
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])

        return d


class BenchSiloPathsSchema(BaseModel):
    """Pathing configurations for isolated execution micro-silos and scientific engines."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    bench_silo: Optional[str] = Field(default=None, description="Path to cochem_bench_silo python interpreter")
    orca_binary_path: Optional[str] = Field(default=None)
    orca_path: Optional[str] = Field(default=None)
    xtb_binary_path: Optional[str] = Field(default=None)
    xtb_path: Optional[str] = Field(default=None)
    mpirun_binary_path: Optional[str] = Field(default=None)
    mpirun_path: Optional[str] = Field(default=None)
    cfour_binary_path: Optional[str] = Field(default=None)
    cfour_path: Optional[str] = Field(default=None)
    aimnet2_server_path: Optional[str] = Field(default=None)
    aimnet2_path: Optional[str] = Field(default=None)
    python_path: Optional[str] = Field(default=None)
    silo_root: Optional[str] = Field(default=None)
    hdf5_pes_store_path: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_path_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        alias_pairs = [
            ("orca_binary_path", "orca_path"),
            ("xtb_binary_path", "xtb_path"),
            ("mpirun_binary_path", "mpirun_path"),
            ("cfour_binary_path", "cfour_path"),
            ("aimnet2_server_path", "aimnet2_path"),
        ]
        for canonical, alias in alias_pairs:
            if canonical in d and alias not in d:
                d[alias] = d[canonical]
            elif alias in d and canonical not in d:
                d[canonical] = d[alias]
        return d


class BenchConfigSchema(BaseModel):
    """Authoritative Stage 0 Ingestion Schema for CoChem-BENCH."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    status: Optional[str] = Field(default="LOCKED")
    hardware: BenchHardwareSchema = Field(..., description="Hardware topology and memory limits")
    environment: Optional[EnvironmentSchema] = Field(default=None)
    silo_paths: BenchSiloPathsSchema = Field(default_factory=BenchSiloPathsSchema)
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    engine_paths: Optional[EnginePaths] = None
    cost_heuristics: Optional[Dict[str, Any]] = None
    active_jobs: Optional[Dict[str, Any]] = None
    hpc: Optional[HPCConfig] = None
    quantum_settings: Optional[QuantumSettings] = None
    adaptive_routing: Optional[RoutingPolicy] = None
    silos: Optional[SiloConfig] = None
    registry_checksum: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def available_ram_gb(self) -> float:
        """Returns authoritative accessible RAM in GB."""
        return float(self.hardware.available_ram_gb or self.hardware.ram_gb)

    @property
    def physical_cores(self) -> int:
        """Returns physical silicon core count."""
        return int(self.hardware.physical_cpu_cores or self.hardware.cpu_physical_cores or self.hardware.cpu_cores or 1)


# ==============================================================================
# Immutable Results & Context Dataclasses
# ==============================================================================

@dataclasses.dataclass(frozen=True)
class HardwareGovernorResult:
    """Immutable result from HardwareGovernor calculations."""
    safe_maxcore_mb: int
    target_mpi_threads: int
    resource_warning: bool
    numa_nodes: int = 1


@dataclasses.dataclass(frozen=True)
class BenchRunContext:
    """Immutable read-only execution context for downstream Stage 2.0 - 5.0 modules."""
    config_hash: str
    safe_maxcore_mb: int
    target_mpi_threads: int
    node_id: str
    timestamp: str
    orca_path: Optional[str]
    hdf5_path: Path
    scratch_path: Path
    numa_nodes: int
    resource_warning: bool
    config: BenchConfigSchema

    @property
    def orca_binary_path(self) -> Optional[str]:
        return self.orca_path


# ==============================================================================
# Core Stage 1.0 Components
# ==============================================================================

def HardwareGovernor(
    cfg: BenchConfigSchema,
    requested_method: Optional[str] = None,
) -> HardwareGovernorResult:
    """Calculates safe %maxcore allocation per MPI thread and enforces memory bounds.

    The 85% Headroom Heuristic:
      Target_MPI_Threads = physical_cores - 1 if physical_cores > 4 else physical_cores
      Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads)

    Args:
        cfg: Validated BenchConfigSchema.
        requested_method: Optional method string (e.g. 'DLPNO-CCSD(T)').

    Returns:
        HardwareGovernorResult containing calculated limits and warning flags.

    Raises:
        ResourceGuardError: If DLPNO-CCSD(T) is requested and Safe_MaxCore_MB < 4000 MB.
    """
    ram_gb = cfg.available_ram_gb
    cores = cfg.physical_cores

    if cores > 4:
        target_mpi_threads = cores - 1
    else:
        target_mpi_threads = max(1, cores)

    safe_maxcore_mb = math.floor(((ram_gb * 1024.0) * 0.85) / target_mpi_threads)

    resource_warning = False
    if safe_maxcore_mb < 1500:
        resource_warning = True
        logger.warning(
            f"RESOURCE_WARNING: Calculated Safe_MaxCore_MB ({safe_maxcore_mb} MB) is below the recommended "
            f"1500 MB floor. High-memory jobs may experience severe page thrashing or OOM aborts."
        )

    if requested_method:
        method_clean = requested_method.lower().replace(" ", "").replace("_", "").replace("-", "")
        is_dlpno = "dlpno" in method_clean or "ccsd(t)" in method_clean
        if is_dlpno and safe_maxcore_mb < 4000:
            raise ResourceGuardError(
                f"RESOURCE_GUARD: Requested method '{requested_method}' requires at least 4000 MB per core, "
                f"but only {safe_maxcore_mb} MB is safely available ({ram_gb:.1f} GB RAM across "
                f"{target_mpi_threads} MPI threads). Refusing to spawn to prevent host OOM lockup."
            )

    return HardwareGovernorResult(
        safe_maxcore_mb=safe_maxcore_mb,
        target_mpi_threads=target_mpi_threads,
        resource_warning=resource_warning,
        numa_nodes=cfg.hardware.numa_nodes,
    )


def SiloIntegrityAssert(
    cfg: BenchConfigSchema,
    current_executable: Optional[Union[str, Path]] = None,
) -> None:
    """Asserts that execution is strictly contained within cochem_bench_silo.

    Args:
        cfg: Validated BenchConfigSchema.
        current_executable: Optional override for active Python executable path.

    Raises:
        SiloIntegrityError: If active executable does not match silo_paths.bench_silo.
    """
    bench_silo = cfg.silo_paths.bench_silo or cfg.silo_paths.python_path
    if not bench_silo or bench_silo in ("BYPASSED", "Not_Found", "missing"):
        return

    active_exe = Path(current_executable or sys.executable).resolve()
    target_silo = Path(bench_silo).resolve()

    if platform.system() == "Windows":
        is_match = str(active_exe).lower() == str(target_silo).lower()
    else:
        is_match = active_exe == target_silo

    if not is_match:
        raise SiloIntegrityError(
            f"ABI Protection Fault: CoChem-BENCH must be executed strictly within the cochem_bench_silo "
            f"to prevent binary collisions. Active runtime '{active_exe}' does not match registered "
            f"silo path '{target_silo}'."
        )


def cleanse_ld_library_path(
    env_val: Optional[str] = None,
    mutate_environ: bool = True,
) -> Optional[str]:
    """Cleanses LD_LIBRARY_PATH by stripping any paths containing anaconda3 or miniconda3.

    Strictly preserves system MPI, compiler, and OS library paths.

    Args:
        env_val: Optional explicit LD_LIBRARY_PATH string to cleanse.
        mutate_environ: Whether to update os.environ with the cleansed string.

    Returns:
        Cleansed LD_LIBRARY_PATH string or None if variable is unset or fully stripped.
    """
    raw = env_val if env_val is not None else os.environ.get("LD_LIBRARY_PATH")
    if not raw:
        if mutate_environ and "LD_LIBRARY_PATH" in os.environ and env_val is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None

    sep = os.pathsep
    entries = raw.split(sep)
    cleansed_entries: List[str] = []

    for entry in entries:
        norm = entry.strip().lower()
        if not norm:
            continue
        if "anaconda3" in norm or "miniconda3" in norm:
            logger.info(f"Stripping conda library path from LD_LIBRARY_PATH: {entry}")
            continue
        cleansed_entries.append(entry.strip())

    if cleansed_entries:
        cleansed_str = sep.join(cleansed_entries)
        if mutate_environ:
            os.environ["LD_LIBRARY_PATH"] = cleansed_str
        return cleansed_str
    else:
        if mutate_environ:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None


def extract_orca_path(cfg: BenchConfigSchema) -> Optional[str]:
    """Dynamically extracts the ORCA executable path from registry configuration."""
    if cfg.engine_paths and cfg.engine_paths.orca and cfg.engine_paths.orca.path:
        p = cfg.engine_paths.orca.path
        if p not in ("BYPASSED", "Not_Found", "missing"):
            return p

    if isinstance(cfg.engines, dict) and "orca" in cfg.engines:
        orca_val = cfg.engines["orca"]
        if isinstance(orca_val, dict) and orca_val.get("path"):
            p = orca_val["path"]
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)
        elif hasattr(orca_val, "path") and orca_val.path:
            p = orca_val.path
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)

    for candidate in (cfg.silo_paths.orca_binary_path, cfg.silo_paths.orca_path):
        if candidate and candidate not in ("BYPASSED", "Not_Found", "missing"):
            return candidate

    return None


def PreFlightVerification(
    cfg: BenchConfigSchema,
    artifacts_dir: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
) -> BenchRunContext:
    """Executes full pre-flight verification and returns an immutable BenchRunContext.

    Args:
        cfg: Validated BenchConfigSchema.
        artifacts_dir: Optional artifacts directory override.
        min_scratch_bytes: Optional required NVMe scratch space threshold in bytes.
        requested_method: Optional quantum chemistry method string.
        current_executable: Optional current python executable override.

    Returns:
        Immutable BenchRunContext dataclass.

    Raises:
        SiloIntegrityError: If runtime does not match bench_silo.
        ResourceGuardError: If scratch space or RAM envelope is insufficient.
        RegistryHandshakeError: If artifacts directory is missing.
    """
    # 1. Micro-silo integrity assertion
    SiloIntegrityAssert(cfg, current_executable=current_executable)

    # 2. Ghost dependency purge: cleanse LD_LIBRARY_PATH
    cleanse_ld_library_path(mutate_environ=True)

    # 3. Hardware Governor validation
    gov_result = HardwareGovernor(cfg, requested_method=requested_method)

    # 4. Resolve artifacts directory
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "COCHEM_ARTIFACTS_DIR environment variable is not defined for Pre-Flight verification."
        )

    # 5. Verify scratch space via PreFlightScratchVerifier
    try:
        verifier = PreFlightScratchVerifier(artifacts_dir=resolved_artifacts)
        scratch_report = verifier.verify(min_free_bytes=min_scratch_bytes)
        scratch_path = Path(scratch_report.scratch_path).resolve()
    except SubprocessResourceGuardError as err:
        raise ResourceGuardError(str(err)) from err

    # 6. Verify HDF5 path in workspace
    workspace_dir = resolved_artifacts / "BENCH_Workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = workspace_dir / "landscape.h5"

    # 7. Stamp provenance
    cfg_json = cfg.model_dump_json()
    config_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    node_id = cfg.hardware.host_id or platform.node() or "cochem_node"
    now_ts = datetime.now(timezone.utc).isoformat()
    orca_path = extract_orca_path(cfg)

    return BenchRunContext(
        config_hash=config_hash,
        safe_maxcore_mb=gov_result.safe_maxcore_mb,
        target_mpi_threads=gov_result.target_mpi_threads,
        node_id=node_id,
        timestamp=now_ts,
        orca_path=orca_path,
        hdf5_path=hdf5_path,
        scratch_path=scratch_path,
        numa_nodes=gov_result.numa_nodes,
        resource_warning=gov_result.resource_warning,
        config=cfg,
    )


def RegistryHandshake(
    artifacts_dir: Optional[Union[str, Path]] = None,
    timeout: float = 10.0,
) -> BenchConfigSchema:
    """Executes Stage 0 Handshake by atomically polling cochem_system_config.json.

    Args:
        artifacts_dir: Optional explicit artifacts root directory path.
        timeout: Maximum time in seconds to wait for filelock acquisition.

    Returns:
        Validated BenchConfigSchema instance.

    Raises:
        RegistryHandshakeError: If COCHEM_ARTIFACTS_DIR is unset, registry is absent,
                                lock acquisition times out, or validation fails.
    """
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "Stage 0 Handshake Error: COCHEM_ARTIFACTS_DIR environment variable is not defined. "
            "CoChem-BENCH requires an active artifacts directory to resolve system configuration."
        )

    config_path = resolved_artifacts / "Registry" / "cochem_system_config.json"
    if not config_path.exists():
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: CoChem system configuration registry not found at '{config_path}'. "
            "Please run CoChem-CORE Stage 0 setup to initialize the system registry."
        )

    lock_file = config_path.parent / f"{config_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    try:
        with lock:
            raw_text = config_path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
    except filelock.Timeout:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Timeout: Failed to acquire read lock on '{config_path}' within {timeout}s."
        )
    except json.JSONDecodeError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry JSON at '{config_path}' is corrupted: {err}"
        ) from err

    try:
        cfg = BenchConfigSchema.model_validate(raw_data)
    except ValidationError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry at '{config_path}' failed strict Pydantic validation: {err}"
        ) from err

    return cfg


def run_bench_ingest_pipeline(
    artifacts_dir: Optional[Union[str, Path]] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    handshake_timeout: float = 10.0,
) -> BenchRunContext:
    """Executes the complete Stage 1.0 Registry Handshake & Pre-Flight Verification pipeline."""
    cfg = RegistryHandshake(artifacts_dir=artifacts_dir, timeout=handshake_timeout)
    return PreFlightVerification(
        cfg=cfg,
        artifacts_dir=artifacts_dir,
        min_scratch_bytes=min_scratch_bytes,
        requested_method=requested_method,
        current_executable=current_executable,
    )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_cv.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 3.0 Core-Valence (CV) Correlation Correction Engine.

Module: tests/test_cochem_bench_cv.py
Target Implementation: bench_engine.cochem_bench_cv

Tests:
1. CoreValenceMapper:
   - Dynamic basis set mapping (cc-pV -> cc-pCV, aug-cc-pV -> aug-cc-pwCV, def2 unchanged).
   - Elemental core composition inspection using dynamic Mendeleev atomic data.
   - Core electron presence and mass calculation.
2. DualCorrelationEngine:
   - Input deck generation for Frozen-Core (FC) vs All-Electron (AE with NoFrozenCore).
   - Dynamic %maxcore RAM calculation per MPI thread.
   - Accelerator isolation injecting CUDA_VISIBLE_DEVICES="".
   - Execution via subprocess using BenchRunContext and binary path.
   - Dual execution protocol (execute_dual_sp) with automatic scratch purging.
3. DeltaExtractor:
   - Extraction of FINAL SINGLE POINT ENERGY from authentic ORCA standard output.
   - Mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC).
   - Unit conversion from Hartree to kcal/mol via exact CODATA conversion.
   - CVParsingError exception hierarchy verification.
4. EphemeralScratchPurge:
   - UUID-scoped tripartite scratch workspace creation.
   - Sweep and unlink of .gbw, .tmp, and ephemeral intermediate files.
   - Directory removal preventing disk and NVMe exhaustion.
5. HDF5 Persistence & Pipeline Orchestration:
   - Atomic commitment of CV correction results to landscape.h5.
   - Schema validation and roundtrip retrieval.
   - End-to-end pipeline execution with pre-computed energies and direct execution.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cv.md
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cv import (
    CoreValenceMapper,
    DualCorrelationEngine,
    DeltaExtractor,
    EphemeralScratchPurge,
    CVCorrectionResult,
    CVCorrectionError,
    CVExecutionError,
    CVParsingError,
    CVScratchPurgeError,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
    HARTREE_TO_KCAL_MOL,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (C2v equilibrium geometry)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Methane (Td equilibrium geometry)
METHANE_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.627600, 0.627600, 0.627600),
    ("H", -0.627600, -0.627600, 0.627600),
    ("H", -0.627600, 0.627600, -0.627600),
    ("H", 0.627600, -0.627600, -0.627600),
]

# Dihydrogen (No core electrons)
H2_COORDS: List[Tuple[str, float, float, float]] = [
    ("H", 0.000000, 0.000000, 0.370000),
    ("H", 0.000000, 0.000000, -0.370000),
]

# Carbon Monoxide (Multiple heavy atoms)
CO_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, -0.645000),
    ("O", 0.000000, 0.000000, 0.485000),
]


# ==============================================================================
# Authentic ORCA 6.1.1 Output Fixtures
# ==============================================================================

ORCA_FC_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.3623851042 Eh
FINAL SINGLE POINT ENERGY      -76.3623851042
ORCA TERMINATED NORMALLY
"""

ORCA_AE_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.4215403210 Eh
FINAL SINGLE POINT ENERGY      -76.4215403210
ORCA TERMINATED NORMALLY
"""


# ==============================================================================
# 1. CoreValenceMapper Tests
# ==============================================================================

def test_basis_set_mapping_cc_pv() -> None:
    """Validate string mapping of standard cc-pVnZ basis sets to core-valence cc-pCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("cc-pVDZ") == "cc-pCVDZ"
    assert mapper.map_basis_set("cc-pVTZ") == "cc-pCVTZ"
    assert mapper.map_basis_set("cc-pVQZ") == "cc-pCVQZ"
    assert mapper.map_basis_set("cc-pV5Z") == "cc-pCV5Z"


def test_basis_set_mapping_aug_cc_pv() -> None:
    """Validate string mapping of augmented aug-cc-pVnZ basis sets to aug-cc-pwCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("aug-cc-pVDZ") == "aug-cc-pwCVDZ"
    assert mapper.map_basis_set("aug-cc-pVTZ") == "aug-cc-pwCVTZ"
    assert mapper.map_basis_set("aug-cc-pVQZ") == "aug-cc-pwCVQZ"
    assert mapper.map_basis_set("aug-cc-pV5Z") == "aug-cc-pwCV5Z"


def test_basis_set_mapping_def2_and_ano() -> None:
    """Validate def2 and ano families retain their native all-electron character without mutation."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("def2-SVP") == "def2-SVP"
    assert mapper.map_basis_set("def2-TZVP") == "def2-TZVP"
    assert mapper.map_basis_set("def2-QZVPP") == "def2-QZVPP"
    assert mapper.map_basis_set("ano-pVTZ") == "ano-pVTZ"
    assert mapper.map_basis_set("saug-ano-pVTZ") == "saug-ano-pVTZ"


def test_elemental_core_inspection_mendeleev() -> None:
    """Validate dynamic atomic and core electron inspection using Mendeleev library."""
    mapper = CoreValenceMapper()

    # Water inspection: Oxygen (Z=8, 2 core e-), Hydrogen (Z=1, 0 core e-)
    water_info = mapper.inspect_elemental_core(WATER_COORDS)
    assert water_info["has_core_electrons"] is True
    assert water_info["total_core_electrons"] == 2
    assert "O" in water_info["elements"]
    assert "H" in water_info["elements"]

    # Verify dynamic masses
    expected_mass = float(element("O").mass) + 2.0 * float(element("H").mass)
    assert math.isclose(water_info["total_mass"], expected_mass, rel_tol=1e-5)

    # Dihydrogen inspection (No core electrons present)
    h2_info = mapper.inspect_elemental_core(H2_COORDS)
    assert h2_info["has_core_electrons"] is False
    assert h2_info["total_core_electrons"] == 0

    # Carbon Monoxide inspection: C (Z=6, 2 core), O (Z=8, 2 core) -> 4 core e-
    co_info = mapper.inspect_elemental_core(CO_COORDS)
    assert co_info["has_core_electrons"] is True
    assert co_info["total_core_electrons"] == 4


# ==============================================================================
# 2. DualCorrelationEngine Tests
# ==============================================================================

def test_dual_correlation_engine_maxcore_calculation() -> None:
    """Validate dynamic %maxcore per MPI process with safety margin."""
    engine = DualCorrelationEngine(node_max_gb=16.0, nprocs=4, ram_safety_fraction=0.75)
    maxcore = engine.calculate_maxcore_per_thread()

    # 16 GB * 1024 MB/GB * 0.75 / 4 = 3072 MB
    assert maxcore == 3072


def test_dual_correlation_input_deck_generation() -> None:
    """Validate generation of Job A (Frozen-Core) and Job B (All-Electron with NoFrozenCore)."""
    engine = DualCorrelationEngine(
        method="DLPNO-CCSD(T)",
        base_basis="aug-cc-pVQZ",
        node_max_gb=16.0,
        nprocs=4,
    )

    decks = engine.generate_input_decks(coords=WATER_COORDS, charge=0, mult=1)

    assert "fc_input" in decks
    assert "ae_input" in decks
    assert decks["basis_set"] == "aug-cc-pwCVQZ"
    assert decks["original_basis"] == "aug-cc-pVQZ"

    fc_inp = decks["fc_input"]
    ae_inp = decks["ae_input"]

    # Job A (FC) must use mapped basis and NOT contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in fc_inp
    assert "NoFrozenCore" not in fc_inp
    assert "%maxcore 3072" in fc_inp
    assert "%pal nprocs 4 end" in fc_inp
    assert "* xyz 0 1" in fc_inp

    # Job B (AE) must contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in ae_inp
    assert "NoFrozenCore" in ae_inp
    assert "%maxcore 3072" in ae_inp
    assert "%pal nprocs 4 end" in ae_inp
    assert "* xyz 0 1" in ae_inp


def test_cuda_accelerator_isolation_env() -> None:
    """Validate execution environment injects CUDA_VISIBLE_DEVICES='' for GPU isolation."""
    engine = DualCorrelationEngine()
    env = engine.prepare_execution_env()

    assert "CUDA_VISIBLE_DEVICES" in env
    assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_dual_correlation_input_file_writing(tmp_path: Path) -> None:
    """Validate writing input decks to disk."""
    engine = DualCorrelationEngine(base_basis="cc-pVTZ")
    decks = engine.generate_input_decks(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
        output_dir=tmp_path,
    )

    fc_file = tmp_path / "orca_fc.inp"
    ae_file = tmp_path / "orca_ae.inp"

    assert fc_file.exists()
    assert ae_file.exists()
    assert "cc-pCVTZ" in fc_file.read_text(encoding="utf-8")
    assert "NoFrozenCore" in ae_file.read_text(encoding="utf-8")


def test_dual_correlation_execute_job_with_runner(tmp_path: Path) -> None:
    """Validate execute_job executes external runner script and captures output."""
    script_file = tmp_path / "sim_orca.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    engine = DualCorrelationEngine(base_basis="aug-cc-pVQZ")
    scratch = tmp_path / "scratch"

    # Use python executable with script file list
    stdout, stderr, ret = engine.execute_job(
        input_text="! DLPNO-CCSD(T) aug-cc-pwCVQZ\n* xyz 0 1\nO 0 0 0\n*\n",
        orca_binary_path=[sys.executable, str(script_file)],
        scratch_dir=scratch,
        job_prefix="test_job",
    )

    assert ret == 0
    assert "FINAL SINGLE POINT ENERGY      -76.3623851042" in stdout


def test_dual_correlation_execute_dual_sp(tmp_path: Path) -> None:
    """Validate execute_dual_sp runs dual jobs, extracts delta, and purges scratch."""
    script_file = tmp_path / "sim_orca_dual.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    engine = DualCorrelationEngine(base_basis="aug-cc-pVQZ")
    scratch = tmp_path / "scratch_dual"

    result = engine.execute_dual_sp(
        coords=WATER_COORDS,
        orca_binary=[sys.executable, str(script_file)],
        node_id="water_dual_test",
        scratch_dir=scratch,
        auto_purge=True,
    )

    assert math.isclose(result.e_total_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(result.e_total_ae, -76.4215403210, abs_tol=1e-10)
    assert result.delta_e_cv_hartree < 0.0
    assert result.node_id == "water_dual_test"
    assert not scratch.exists()  # Purged


# ==============================================================================
# 3. DeltaExtractor Tests
# ==============================================================================

def test_parse_final_energy_from_stdout() -> None:
    """Validate extracting FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
    extractor = DeltaExtractor()

    e_fc = extractor.parse_final_energy_from_stdout(ORCA_FC_STDOUT_WATER)
    e_ae = extractor.parse_final_energy_from_stdout(ORCA_AE_STDOUT_WATER)

    assert math.isclose(e_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(e_ae, -76.4215403210, abs_tol=1e-10)


def test_parse_final_energy_missing_raises() -> None:
    """Validate CVParsingError is raised when FINAL SINGLE POINT ENERGY is absent."""
    extractor = DeltaExtractor()
    invalid_stdout = "ORCA CALCULATION FAILED\nNO ENERGY REPORTED\n"

    with pytest.raises(CVParsingError, match="FINAL SINGLE POINT ENERGY"):
        extractor.parse_final_energy_from_stdout(invalid_stdout)

    # Also verify that CVParsingError is a ValueError subclass
    with pytest.raises(ValueError):
        extractor.parse_final_energy_from_stdout(invalid_stdout)


def test_delta_extractor_mathematics() -> None:
    """Validate mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
    extractor = DeltaExtractor()

    e_fc = -76.3623851042
    e_ae = -76.4215403210

    result: CVCorrectionResult = extractor.extract_delta(
        e_total_fc=e_fc,
        e_total_ae=e_ae,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_test_01",
    )

    expected_delta_hartree = e_ae - e_fc
    expected_delta_kcal = expected_delta_hartree * HARTREE_TO_KCAL_MOL

    assert math.isclose(result.delta_e_cv_hartree, expected_delta_hartree, rel_tol=1e-10)
    assert math.isclose(result.delta_e_cv_kcal_mol, expected_delta_kcal, rel_tol=1e-10)
    assert result.delta_e_cv_hartree < 0.0  # All-electron energy is lower than frozen-core
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert result.original_basis_set == "aug-cc-pVQZ"
    assert result.node_id == "water_test_01"


def test_extract_from_outputs() -> None:
    """Validate extraction directly from authentic ORCA output texts."""
    extractor = DeltaExtractor()

    result = extractor.extract_from_outputs(
        stdout_fc=ORCA_FC_STDOUT_WATER,
        stdout_ae=ORCA_AE_STDOUT_WATER,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        node_id="water_out_test",
    )

    assert math.isclose(result.e_total_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(result.e_total_ae, -76.4215403210, abs_tol=1e-10)
    assert math.isclose(result.delta_e_cv_hartree, -76.4215403210 - (-76.3623851042), abs_tol=1e-10)


# ==============================================================================
# 4. EphemeralScratchPurge Tests
# ==============================================================================

def test_scratch_dir_creation(tmp_path: Path) -> None:
    """Validate creation of isolated UUID-scoped scratch directory."""
    purger = EphemeralScratchPurge()
    scratch_dir = purger.create_scratch_dir(base_artifacts_dir=tmp_path)

    assert scratch_dir.exists()
    assert "BENCH_Workspace" in str(scratch_dir)
    assert "Scratch" in str(scratch_dir)
    assert "job_" in scratch_dir.name


def test_scratch_dir_purge(tmp_path: Path) -> None:
    """Validate sweep and removal of .gbw, .tmp, and intermediate scratch files."""
    purger = EphemeralScratchPurge()
    job_dir = tmp_path / "BENCH_Workspace" / "Scratch" / "job_12345"
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create simulation intermediate files
    (job_dir / "calc.gbw").write_bytes(b"BINARY_GBW_CONTENT")
    (job_dir / "calc.tmp").write_text("TMP_CONTENT", encoding="utf-8")
    (job_dir / "calc.densities").write_text("DENSITIES", encoding="utf-8")
    (job_dir / "calc.inp").write_text("! Input deck", encoding="utf-8")

    assert (job_dir / "calc.gbw").exists()
    assert (job_dir / "calc.tmp").exists()

    # Execute purge
    summary = purger.purge_scratch_dir(job_dir, remove_dir=True)

    assert summary["purged_count"] >= 2
    assert not job_dir.exists()


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

def test_hdf5_cv_persistence(tmp_path: Path) -> None:
    """Validate atomic serialization of CV correction delta to landscape.h5."""
    h5_file = tmp_path / "landscape.h5"

    cv_result = CVCorrectionResult(
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        delta_e_cv_hartree=-0.059155,
        delta_e_cv_kcal_mol=-37.120300,
        basis_set="aug-cc-pwCVQZ",
        original_basis_set="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        has_core_electrons=True,
        node_id="water_cv_node_01",
    )

    commit_cv_to_hdf5(h5_path=h5_file, result=cv_result)
    assert h5_file.exists()

    # Read back and verify exact data integrity
    loaded = read_cv_from_hdf5(h5_path=h5_file, node_id="water_cv_node_01")

    assert math.isclose(loaded["e_total_fc"], -76.362385, abs_tol=1e-6)
    assert math.isclose(loaded["e_total_ae"], -76.421540, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_hartree"], -0.059155, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_kcal_mol"], -37.120300, abs_tol=1e-6)
    assert loaded["basis_set"] == "aug-cc-pwCVQZ"
    assert loaded["original_basis_set"] == "aug-cc-pVQZ"
    assert loaded["method"] == "DLPNO-CCSD(T)"
    assert loaded["has_core_electrons"] is True
    assert loaded["node_id"] == "water_cv_node_01"


def test_run_cv_pipeline_end_to_end(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 3.0 CV pipeline orchestrator."""
    h5_file = tmp_path / "landscape.h5"

    result = run_cv_pipeline(
        coords=WATER_COORDS,
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        base_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_pipeline_01",
        h5_path=h5_file,
    )

    assert result.has_core_electrons is True
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert math.isclose(result.delta_e_cv_hartree, -76.421540 - (-76.362385), abs_tol=1e-6)
    assert h5_file.exists()


def test_run_cv_pipeline_with_orca_binary(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 3.0 CV pipeline with engine execution."""
    script_file = tmp_path / "sim_orca_pipe.py"
    script_file.write_text(
        'import sys\n'
        'with open(sys.argv[1], "r", encoding="utf-8") as f:\n'
        '    inp = f.read()\n'
        'if "NoFrozenCore" in inp:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.4215403210")\n'
        'else:\n'
        '    print("FINAL SINGLE POINT ENERGY      -76.3623851042")\n'
        'sys.exit(0)\n',
        encoding="utf-8",
    )

    h5_file = tmp_path / "landscape.h5"
    result = run_cv_pipeline(
        coords=WATER_COORDS,
        orca_binary=[sys.executable, str(script_file)],
        base_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_pipe_bin_01",
        h5_path=h5_file,
    )

    assert result.has_core_electrons is True
    assert result.node_id == "water_pipe_bin_01"
    assert math.isclose(result.delta_e_cv_hartree, -76.4215403210 - (-76.3623851042), abs_tol=1e-10)
    assert h5_file.exists()


def test_run_cv_pipeline_missing_args_raises() -> None:
    """Validate run_cv_pipeline raises CVCorrectionError when neither energies nor binary provided."""
    with pytest.raises(CVCorrectionError, match="requires either"):
        run_cv_pipeline(coords=WATER_COORDS)


def test_read_cv_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cv_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "missing_landscape.h5"
    with pytest.raises(FileNotFoundError):
        read_cv_from_hdf5(h5_path=missing_file, node_id="node_none")


def test_cochem_bench_package_imports() -> None:
    """Validate that all Stage 3.0 symbols are accessible via cochem_bench.bench_engine."""
    from cochem_bench.bench_engine.cochem_bench_cv import (
        CoreValenceMapper as CBMapper,
        DualCorrelationEngine as CBEngine,
        DeltaExtractor as CBExtractor,
        EphemeralScratchPurge as CBPurge,
        CVCorrectionResult as CBResult,
        CVCorrectionError,
        CVExecutionError,
        CVParsingError,
        CVScratchPurgeError,
    )

    mapper = CBMapper()
    assert mapper.map_basis_set("cc-pVDZ") == "cc-pCVDZ"
    assert issubclass(CVExecutionError, CVCorrectionError)
    assert issubclass(CVParsingError, CVCorrectionError)
    assert issubclass(CVScratchPurgeError, CVCorrectionError)


def test_bench_run_context_integration(tmp_path: Path) -> None:
    """Validate DualCorrelationEngine execution with BenchRunContext."""
    from cochem_bench.bench_engine.cochem_bench_ingest import BenchRunContext, BenchConfigSchema, BenchHardwareSchema

    cfg = BenchConfigSchema(
        hardware=BenchHardwareSchema(ram_gb=16.0, cpu_physical_cores=4),
    )
    ctx = BenchRunContext(
        config_hash="abc123hash",
        safe_maxcore_mb=3072,
        target_mpi_threads=4,
        node_id="test_node",
        timestamp="2026-08-24T00:00:00Z",
        orca_path=str(tmp_path / "fake_orca_exe"),
        hdf5_path=tmp_path / "landscape.h5",
        scratch_path=tmp_path / "scratch",
        numa_nodes=1,
        resource_warning=False,
        config=cfg,
    )

    assert ctx.orca_binary_path == str(tmp_path / "fake_orca_exe")
    assert ctx.orca_path == str(tmp_path / "fake_orca_exe")

    engine = DualCorrelationEngine()
    env = engine.prepare_execution_env()
    assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_scratch_dir_creation_with_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate scratch dir creation adheres to COCHEM_ARTIFACTS_DIR environment variable."""
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(tmp_path))
    purger = EphemeralScratchPurge()
    scratch_dir = purger.create_scratch_dir()

    assert scratch_dir.exists()
    assert str(tmp_path) in str(scratch_dir)
    assert "BENCH_Workspace" in str(scratch_dir)
    assert "Scratch" in str(scratch_dir)

    summary = purger.purge_scratch_dir(scratch_dir, remove_dir=True)
    assert summary["status"] == "purged"
    assert not scratch_dir.exists()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_engine\cochem_bench_cv.py ---
#!/usr/bin/env python3
r"""Stage 3.0: Core-Valence (CV) Correlation Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_cv
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. CoreValenceMapper: Dynamically maps appropriate core-polarized basis sets
   (e.g., aug-cc-pwCVnZ, cc-pCVnZ) and inspects elemental core electron configurations
   via the Mendeleev library.
2. DualCorrelationEngine: Formulates and executes dual single-point evaluations
   comparing Frozen-Core (FC) against All-Electron (AE with NoFrozenCore) treatments,
   enforcing CUDA accelerator isolation (CUDA_VISIBLE_DEVICES="") and %maxcore memory limits.
   Executes jobs via subprocess.run([BenchRunContext.orca_binary_path, input_file]) with
   safe parameter extraction.
3. DeltaExtractor: Extracts FINAL SINGLE POINT ENERGY floats from authentic ORCA standard
   outputs and mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC).
4. EphemeralScratchPurge: Tripartite scratch workspace manager executing explicit sweeps
   and unlinking of .gbw, .tmp, and intermediate files immediately after energy extraction.
5. HDF5 Persistence: Commits computed CV corrections atomically to landscape.h5.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task5_cv.md
"""

from __future__ import annotations

import datetime
import math
import os
import re
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class CVCorrectionError(Exception):
    """Base exception for Stage 3.0 Core-Valence correlation operations."""
    pass


class CVExecutionError(CVCorrectionError, RuntimeError):
    """Raised when ORCA calculation execution fails."""
    pass


class CVParsingError(CVCorrectionError, ValueError):
    """Raised when required energy signature cannot be extracted from ORCA output."""
    pass


class CVScratchPurgeError(CVCorrectionError, OSError):
    """Raised when scratch purging encounters an OS-level filesystem error."""
    pass


# ==============================================================================
# Data Models
# ==============================================================================

class CVCorrectionResult(BaseModel):
    """Structured result model for Core-Valence (CV) correlation energy corrections."""
    e_total_fc: float = Field(description="Frozen-Core total electronic energy in Hartree")
    e_total_ae: float = Field(description="All-Electron total electronic energy in Hartree")
    delta_e_cv_hartree: float = Field(description="Core-Valence correction delta (AE - FC) in Hartree")
    delta_e_cv_kcal_mol: float = Field(description="Core-Valence correction delta in kcal/mol")
    basis_set: str = Field(description="Core-polarized basis set used for calculations")
    original_basis_set: str = Field(default="", description="Original basis set before core-valence mapping")
    method: str = Field(default="DLPNO-CCSD(T)", description="Quantum chemistry method")
    has_core_electrons: bool = Field(default=True, description="True if molecule contains elements with core electrons (Z >= 3)")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution or provenance metadata")


# ==============================================================================
# 1. CoreValenceMapper
# ==============================================================================

class CoreValenceMapper:
    """Dynamically maps appropriate core-polarized basis sets and inspects elemental core configurations."""

    @staticmethod
    def map_basis_set(basis_set: str) -> str:
        """Maps standard valence basis sets to their corresponding core-polarized variants.
        
        Rules:
        - "aug-cc-pVnZ" -> "aug-cc-pwCVnZ"
        - "cc-pVnZ" -> "cc-pCVnZ"
        - "def2-*" -> unchanged (def2 family natively supports all-electron/core-valence)
        - "ano-*" -> unchanged (ANO basis sets are general contraction all-electron bases)
        """
        b_str = basis_set.strip()
        b_lower = b_str.lower()

        # Handle augmented correlation consistent sets first
        if "aug-cc-pv" in b_lower:
            pattern = re.compile(r"aug-cc-pv", re.IGNORECASE)
            return pattern.sub("aug-cc-pwCV", b_str)

        # Handle standard correlation consistent sets
        if "cc-pv" in b_lower:
            pattern = re.compile(r"cc-pv", re.IGNORECASE)
            return pattern.sub("cc-pCV", b_str)

        # def2 and ANO families do not require prefix modification
        return b_str

    @staticmethod
    def inspect_elemental_core(
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    ) -> Dict[str, Any]:
        """Inspects elemental composition using Mendeleev to determine core electron counts and molecular mass."""
        total_mass = 0.0
        total_electrons = 0
        total_core_electrons = 0
        elements_present: List[str] = []

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            z = int(elem_data.atomic_number)
            mass = float(elem_data.mass)

            total_mass += mass
            total_electrons += z
            if sym not in elements_present:
                elements_present.append(sym)

            # Core electron calculation:
            # Z = 1, 2 (H, He): 0 core electrons
            # Z = 3 - 10 (Li - Ne): 2 core electrons (1s^2 / [He])
            # Z = 11 - 18 (Na - Ar): 10 core electrons ([Ne])
            # Z = 19 - 36 (K - Kr): 18 core electrons ([Ar])
            # Z = 37 - 54 (Rb - Xe): 36 core electrons ([Kr])
            if z <= 2:
                core_e = 0
            elif z <= 10:
                core_e = 2
            elif z <= 18:
                core_e = 10
            elif z <= 36:
                core_e = 18
            elif z <= 54:
                core_e = 36
            else:
                core_e = 54

            total_core_electrons += core_e

        has_core = total_core_electrons > 0

        return {
            "has_core_electrons": has_core,
            "total_core_electrons": total_core_electrons,
            "total_electrons": total_electrons,
            "total_mass": total_mass,
            "elements": elements_present,
        }


# ==============================================================================
# 2. DualCorrelationEngine
# ==============================================================================

class DualCorrelationEngine:
    """Manages dual Frozen-Core vs All-Electron single-point ORCA calculation configurations."""

    def __init__(
        self,
        method: str = "DLPNO-CCSD(T)",
        base_basis: str = "aug-cc-pVTZ",
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        ram_safety_fraction: float = 0.75,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        extra_keywords: Optional[List[str]] = None,
    ) -> None:
        self.method = method
        self.base_basis = base_basis
        self.node_max_gb = float(node_max_gb)
        self.nprocs = max(1, int(nprocs))
        self.ram_safety_fraction = float(ram_safety_fraction)
        self.tight_scf = tight_scf
        self.defgrid = defgrid
        self.extra_keywords = list(extra_keywords) if extra_keywords else []

    def calculate_maxcore_per_thread(self) -> int:
        """Calculates strict per-process %maxcore in MB leaving headroom for OS and MPI runtime."""
        available_mb = self.node_max_gb * 1024.0 * self.ram_safety_fraction
        per_thread_mb = int(available_mb / self.nprocs)
        min_allowed = 250
        max_allowed = int((self.node_max_gb * 1024.0) / self.nprocs)
        candidate = max(min_allowed, per_thread_mb)
        return min(candidate, max_allowed)

    def prepare_execution_env(self) -> Dict[str, str]:
        """Prepares child subprocess execution environment, air-gapping GPUs via CUDA_VISIBLE_DEVICES=''."""
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    def generate_input_decks(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        charge: int = 0,
        mult: int = 1,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for Frozen-Core and All-Electron calculations."""
        mapper = CoreValenceMapper()
        mapped_basis = mapper.map_basis_set(self.base_basis)
        maxcore_mb = self.calculate_maxcore_per_thread()

        # Job A: Frozen-Core (default)
        fc_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=False,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        # Job B: All-Electron (NoFrozenCore)
        ae_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=True,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        decks = {
            "fc_input": fc_input,
            "ae_input": ae_input,
            "basis_set": mapped_basis,
            "original_basis": self.base_basis,
            "method": self.method,
            "maxcore_mb": maxcore_mb,
            "nprocs": self.nprocs,
            "charge": charge,
            "mult": mult,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / "orca_fc.inp").write_text(fc_input, encoding="utf-8")
            (out_path / "orca_ae.inp").write_text(ae_input, encoding="utf-8")

        return decks

    def _build_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        basis: str,
        is_all_electron: bool,
        charge: int,
        mult: int,
        maxcore_mb: int,
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck."""
        keywords = ["!", self.method, basis]
        if is_all_electron:
            keywords.append("NoFrozenCore")
        if self.tight_scf:
            keywords.append("TightSCF")
        if self.defgrid:
            keywords.append(self.defgrid)
        for kw in self.extra_keywords:
            if kw not in keywords:
                keywords.append(kw)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if self.nprocs > 1:
            lines.append(f"%pal nprocs {self.nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)

    def execute_job(
        self,
        input_text: str,
        orca_binary_path: Union[str, Path, List[str], Any],
        scratch_dir: Union[str, Path],
        job_prefix: str = "job",
        timeout_seconds: int = 7200,
    ) -> Tuple[str, str, int]:
        """Executes ORCA binary via subprocess inside isolated scratch with GPU air-gapping."""
        if hasattr(orca_binary_path, "orca_binary_path") and orca_binary_path.orca_binary_path:
            resolved_bin = orca_binary_path.orca_binary_path
        elif hasattr(orca_binary_path, "orca_path") and orca_binary_path.orca_path:
            resolved_bin = orca_binary_path.orca_path
        else:
            resolved_bin = orca_binary_path

        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        inp_file = scratch_path / f"{job_prefix}.inp"
        inp_file.write_text(input_text, encoding="utf-8")

        env = self.prepare_execution_env()

        if isinstance(resolved_bin, (list, tuple)):
            cmd = [str(x) for x in resolved_bin] + [str(inp_file)]
        else:
            cmd_str = str(resolved_bin).strip()
            if " " in cmd_str and not Path(cmd_str).exists():
                cmd = shlex.split(cmd_str, posix=False) + [str(inp_file)]
            else:
                cmd = [cmd_str, str(inp_file)]

        proc = subprocess.run(
            cmd,
            cwd=str(scratch_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode

    def execute_dual_sp(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        orca_binary: Union[str, Path, List[str], Any],
        charge: int = 0,
        mult: int = 1,
        node_id: str = "node_0",
        scratch_dir: Optional[Union[str, Path]] = None,
        timeout_seconds: int = 7200,
        auto_purge: bool = True,
    ) -> CVCorrectionResult:
        """Dispatches dual single-point jobs: Job A (Frozen-Core) and Job B (All-Electron).
        
        Executes via subprocess.run using the validated engine path, isolates accelerators,
        extracts FINAL SINGLE POINT ENERGY from stdout, and purges intermediate scratch files.
        """
        purger = EphemeralScratchPurge()
        if scratch_dir is None:
            job_scratch = purger.create_scratch_dir()
        else:
            job_scratch = Path(scratch_dir)
            job_scratch.mkdir(parents=True, exist_ok=True)

        decks = self.generate_input_decks(coords=coords, charge=charge, mult=mult)

        try:
            # Job A: Frozen-Core
            stdout_fc, stderr_fc, code_fc = self.execute_job(
                input_text=decks["fc_input"],
                orca_binary_path=orca_binary,
                scratch_dir=job_scratch,
                job_prefix="orca_fc",
                timeout_seconds=timeout_seconds,
            )
            if code_fc != 0:
                raise CVExecutionError(
                    f"Job A (Frozen-Core) execution failed with exit code {code_fc}: {stderr_fc}"
                )

            # Job B: All-Electron (NoFrozenCore)
            stdout_ae, stderr_ae, code_ae = self.execute_job(
                input_text=decks["ae_input"],
                orca_binary_path=orca_binary,
                scratch_dir=job_scratch,
                job_prefix="orca_ae",
                timeout_seconds=timeout_seconds,
            )
            if code_ae != 0:
                raise CVExecutionError(
                    f"Job B (All-Electron) execution failed with exit code {code_ae}: {stderr_ae}"
                )

            # Extract energies and compute delta
            extractor = DeltaExtractor()
            result = extractor.extract_from_outputs(
                stdout_fc=stdout_fc,
                stdout_ae=stdout_ae,
                basis_set=decks["basis_set"],
                original_basis=decks["original_basis"],
                method=self.method,
                node_id=node_id,
            )
            return result
        finally:
            if auto_purge:
                purger.purge_scratch_dir(job_scratch, remove_dir=True)


# ==============================================================================
# 3. DeltaExtractor
# ==============================================================================

class DeltaExtractor:
    """Extracts electronic energies from ORCA stdout streams and derives Core-Valence deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from standard ORCA output."""
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise CVParsingError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(match.group(1))

    @staticmethod
    def extract_delta(
        e_total_fc: float,
        e_total_ae: float,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
        delta_hartree = float(e_total_ae) - float(e_total_fc)
        delta_kcal = delta_hartree * HARTREE_TO_KCAL_MOL

        return CVCorrectionResult(
            e_total_fc=float(e_total_fc),
            e_total_ae=float(e_total_ae),
            delta_e_cv_hartree=delta_hartree,
            delta_e_cv_kcal_mol=delta_kcal,
            basis_set=basis_set,
            original_basis_set=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata or {},
        )

    def extract_from_outputs(
        self,
        stdout_fc: str,
        stdout_ae: str,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Parses energies directly from stdout texts and computes CV correction."""
        e_fc = self.parse_final_energy_from_stdout(stdout_fc)
        e_ae = self.parse_final_energy_from_stdout(stdout_ae)
        return self.extract_delta(
            e_total_fc=e_fc,
            e_total_ae=e_ae,
            basis_set=basis_set,
            original_basis=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 4. EphemeralScratchPurge
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
# 5. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves target landscape.h5 path dynamically adhering to Air-Gap mandate."""
    if h5_path is not None:
        target = Path(h5_path)
        if not target.is_absolute() and "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
            return (Path(os.environ["COCHEM_ARTIFACTS_DIR"]) / target).resolve()
        return target.resolve()

    if "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        artifacts_dir = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
        return (artifacts_dir / "BENCH_Workspace" / "landscape.h5").resolve()

    return Path("BENCH_Workspace/landscape.h5").resolve()


def commit_cv_to_hdf5(
    h5_path: Union[str, Path],
    result: CVCorrectionResult,
    timeout: float = 120.0,
) -> Path:
    """Commits computed Core-Valence correction results atomically to landscape.h5 using FileLock."""
    target_path = resolve_hdf5_path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    node_group_name = result.node_id if result.node_id else "default_cv_node"

    with lock:
        with h5py.File(target_path, "a") as f:
            root_grp = f.require_group("cv_corrections")
            node_grp = root_grp.require_group(node_group_name)

            datasets = {
                "e_total_fc": result.e_total_fc,
                "e_total_ae": result.e_total_ae,
                "delta_e_cv_hartree": result.delta_e_cv_hartree,
                "delta_e_cv_kcal_mol": result.delta_e_cv_kcal_mol,
            }

            for ds_name, ds_val in datasets.items():
                if ds_name in node_grp:
                    del node_grp[ds_name]
                node_grp.create_dataset(ds_name, data=float(ds_val))

            node_grp.attrs["basis_set"] = result.basis_set
            node_grp.attrs["original_basis_set"] = result.original_basis_set
            node_grp.attrs["method"] = result.method
            node_grp.attrs["has_core_electrons"] = bool(result.has_core_electrons)
            node_grp.attrs["timestamp"] = result.timestamp
            node_grp.attrs["node_id"] = result.node_id

    return target_path


def read_cv_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Reads back computed Core-Valence correction results atomically from landscape.h5 using FileLock."""
    target_path = resolve_hdf5_path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    lock_file = target_path.parent / f"{target_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    with lock:
        with h5py.File(target_path, "r") as f:
            if "cv_corrections" not in f:
                raise KeyError(f"Root group 'cv_corrections' not found in '{target_path}'")
            root_grp = f["cv_corrections"]
            if node_id not in root_grp:
                raise KeyError(f"Node '{node_id}' not found in 'cv_corrections'")
            node_grp = root_grp[node_id]

            data = {
                "e_total_fc": float(node_grp["e_total_fc"][()]),
                "e_total_ae": float(node_grp["e_total_ae"][()]),
                "delta_e_cv_hartree": float(node_grp["delta_e_cv_hartree"][()]),
                "delta_e_cv_kcal_mol": float(node_grp["delta_e_cv_kcal_mol"][()]),
                "basis_set": str(node_grp.attrs.get("basis_set", "")),
                "original_basis_set": str(node_grp.attrs.get("original_basis_set", "")),
                "method": str(node_grp.attrs.get("method", "")),
                "has_core_electrons": bool(node_grp.attrs.get("has_core_electrons", True)),
                "timestamp": str(node_grp.attrs.get("timestamp", "")),
                "node_id": str(node_grp.attrs.get("node_id", "")),
            }
            return data


def run_cv_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_total_fc: Optional[float] = None,
    e_total_ae: Optional[float] = None,
    orca_binary: Optional[Union[str, Path, List[str], Any]] = None,
    base_basis: str = "aug-cc-pVQZ",
    method: str = "DLPNO-CCSD(T)",
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
    charge: int = 0,
    mult: int = 1,
    scratch_dir: Optional[Union[str, Path]] = None,
) -> CVCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 3.0 Core-Valence (CV) Correction."""
    mapper = CoreValenceMapper()
    mapped_basis = mapper.map_basis_set(base_basis)
    core_info = mapper.inspect_elemental_core(coords)

    if e_total_fc is not None and e_total_ae is not None:
        extractor = DeltaExtractor()
        result = extractor.extract_delta(
            e_total_fc=e_total_fc,
            e_total_ae=e_total_ae,
            basis_set=mapped_basis,
            original_basis=base_basis,
            method=method,
            has_core_electrons=core_info["has_core_electrons"],
            node_id=node_id,
            metadata={"core_info": core_info},
        )
    elif orca_binary is not None:
        engine = DualCorrelationEngine(
            method=method,
            base_basis=base_basis,
            node_max_gb=node_max_gb,
            nprocs=nprocs,
        )
        result = engine.execute_dual_sp(
            coords=coords,
            orca_binary=orca_binary,
            charge=charge,
            mult=mult,
            node_id=node_id,
            scratch_dir=scratch_dir,
        )
        result.metadata["core_info"] = core_info
    else:
        raise CVCorrectionError(
            "run_cv_pipeline requires either (e_total_fc, e_total_ae) or orca_binary to be supplied."
        )

    if h5_path:
        commit_cv_to_hdf5(h5_path=h5_path, result=result)

    return result

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.