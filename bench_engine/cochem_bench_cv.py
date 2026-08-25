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
3. DeltaExtractor: Extracts FINAL SINGLE POINT ENERGY floats from authentic ORCA standard
   outputs and mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC).
4. EphemeralScratchPurge: Tripartite scratch workspace manager executing explicit sweeps
   and unlinking of .gbw, .tmp, and intermediate files immediately after energy extraction.
5. HDF5 Persistence: Commits computed CV corrections atomically to landscape.h5.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_cv.md
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
# Physical Constants
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063


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
        orca_binary_path: Union[str, Path],
        scratch_dir: Union[str, Path],
        job_prefix: str = "job",
        timeout_seconds: int = 7200,
    ) -> Tuple[str, str, int]:
        """Executes ORCA binary via subprocess inside isolated scratch with GPU air-gapping."""
        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        inp_file = scratch_path / f"{job_prefix}.inp"
        inp_file.write_text(input_text, encoding="utf-8")

        env = self.prepare_execution_env()

        cmd = [str(orca_binary_path), str(inp_file)]
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
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
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

def commit_cv_to_hdf5(
    h5_path: Union[str, Path],
    result: CVCorrectionResult,
) -> None:
    """Commits computed Core-Valence correction results atomically to landscape.h5."""
    target_path = Path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    node_group_name = result.node_id if result.node_id else "default_cv_node"

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


def read_cv_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
) -> Dict[str, Any]:
    """Reads back computed Core-Valence correction results from landscape.h5."""
    target_path = Path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    with h5py.File(target_path, "r") as f:
        root_grp = f["cv_corrections"]
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
    e_total_fc: float,
    e_total_ae: float,
    base_basis: str = "aug-cc-pVQZ",
    method: str = "DLPNO-CCSD(T)",
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
) -> CVCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 3.0 Core-Valence (CV) Correction."""
    # 1. Map basis set and inspect elemental core
    mapper = CoreValenceMapper()
    mapped_basis = mapper.map_basis_set(base_basis)
    core_info = mapper.inspect_elemental_core(coords)

    # 2. Extract delta and create result model
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

    # 3. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_cv_to_hdf5(h5_path=h5_path, result=result)

    return result
