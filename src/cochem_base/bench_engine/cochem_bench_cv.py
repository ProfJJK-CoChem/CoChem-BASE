#!/usr/bin/env python3
"""Compatibility data helpers for core-valence correlation corrections.

These helpers build decks, parse supplied observations, calculate AE minus FC,
and store numeric records. They do not execute calculations or establish that
the supplied observations form a physically validated core-valence protocol.
Native calculations belong to the canonical registry-authorized BASE broker and
the separately installed, verified scientific provider.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import datetime
import hashlib
import json
import math
from numbers import Real
import os
import re
import stat
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
from mendeleev import element
import psutil
from pydantic import BaseModel, Field

from cochem.core.context import AirGapViolationError, assert_writable_path
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity


# ==============================================================================
# Physical Constants
# ==============================================================================

from cochem_base.core.glossary import HARTREE_TO_KCAL_MOL


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

        identity = resolve_nuclear_identity([str(item[0]).strip() for item in coords])
        for sym, mass in zip(identity.elements, identity.masses_u):
            elem_data = element(sym)
            z = int(elem_data.atomic_number)

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
            "nuclear_identity": identity.metadata,
        }


# ==============================================================================
# 2. DualCorrelationEngine
# ==============================================================================

class DualCorrelationEngine:
    """Builds frozen-core/all-electron input data; does not launch an engine."""

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
        """Returns a CPU-only environment specification without launching a process."""
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
        """Builds candidate FC/AE decks; native acceptance belongs to the provider."""
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

# ==============================================================================
# 3. DeltaExtractor
# ==============================================================================

class DeltaExtractor:
    """Extracts electronic energies from ORCA stdout streams and derives Core-Valence deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from standard ORCA output."""
        matches = re.findall(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not matches:
            raise CVParsingError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(matches[-1])

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
        if any(isinstance(value, bool) or not isinstance(value, Real)
               or not math.isfinite(float(value)) for value in (e_total_fc, e_total_ae)):
            raise CVParsingError("Both FC and AE observations must be finite real energies.")
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
    """Reclaims only intermediates in a directory created by this process.

    The generation marker is corroborated by the creator's inode record, not
    accepted as authority supplied by a caller. Unknown inputs/results remain.
    """

    _marker_name = ".cochem-cv-scratch-owner.json"
    _created: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _ancestors(path: Path) -> List[Tuple[str, int, int]]:
        observed = []
        for ancestor in reversed((path, *path.parents)):
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise CVScratchPurgeError("Scratch paths require nonsymlink directory ancestors.")
            observed.append((str(ancestor), info.st_dev, info.st_ino))
        return observed

    @staticmethod
    def create_scratch_dir(base_artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
        """Creates a new externally located directory with private creator authority."""
        if base_artifacts_dir:
            base_dir = Path(base_artifacts_dir)
        else:
            base_env = os.environ.get(
                "COCHEM_ARTIFACTS_DIR",
                os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
            )
            base_dir = Path(base_env)

        base_dir = Path(os.path.abspath(base_dir))
        try:
            assert_writable_path(base_dir)
        except AirGapViolationError as error:
            raise CVScratchPurgeError(str(error)) from error
        source_root = Path(__file__).resolve().parents[3]
        for protected in (source_root, Path(sys.prefix).resolve()):
            if base_dir == protected or protected in base_dir.parents:
                raise CVScratchPurgeError("Scratch must be outside source and installed runtime roots.")
        for ancestor in (base_dir, *base_dir.parents):
            if ancestor.is_symlink():
                raise CVScratchPurgeError("Scratch paths require nonsymlink directory ancestors.")
        parent = base_dir / "BENCH_Workspace" / "Scratch"
        parent.mkdir(parents=True, exist_ok=True)
        EphemeralScratchPurge._ancestors(parent)
        generation = str(uuid.uuid4())
        scratch_dir = parent / f"job_{generation}"
        scratch_dir.mkdir(mode=0o700)
        marker = scratch_dir / EphemeralScratchPurge._marker_name
        payload = json.dumps({"generation": generation, "path": str(scratch_dir)}, sort_keys=True).encode()
        with marker.open("xb") as output:
            output.write(payload)
        info = marker.lstat()
        EphemeralScratchPurge._created[str(scratch_dir)] = {
            "creator_pid": os.getpid(),
            "creator_create_time": psutil.Process().create_time(),
            "ancestors": EphemeralScratchPurge._ancestors(scratch_dir),
            "marker_inode": (info.st_dev, info.st_ino),
            "marker_sha256": hashlib.sha256(payload).hexdigest(),
        }
        return scratch_dir

    @staticmethod
    def purge_scratch_dir(
        scratch_dir: Union[str, Path],
        remove_dir: bool = True,
    ) -> Dict[str, Any]:
        """Validate the unchanged creator generation before deleting intermediates.

        Refuse unknown/replaced directories and links before any deletion. An
        input, result, or subdirectory prevents removal of the owned directory.
        """
        scratch_path = Path(os.path.abspath(scratch_dir))
        owner = EphemeralScratchPurge._created.get(str(scratch_path))
        if owner is None:
            raise CVScratchPurgeError("Scratch deletion requires this process's exact creator authority.")
        if (os.getpid() != owner["creator_pid"]
                or psutil.Process().create_time() != owner["creator_create_time"]):
            raise CVScratchPurgeError("Scratch deletion is reserved to its creating process generation.")
        marker = scratch_path / EphemeralScratchPurge._marker_name
        try:
            if EphemeralScratchPurge._ancestors(scratch_path) != owner["ancestors"]:
                raise CVScratchPurgeError("Scratch directory generation or ancestors changed.")
            info = marker.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or (info.st_dev, info.st_ino) != owner["marker_inode"]
                    or hashlib.sha256(marker.read_bytes()).hexdigest() != owner["marker_sha256"]):
                raise CVScratchPurgeError("Scratch creator marker changed.")
            members = list(scratch_path.rglob("*"))
            if any(member.is_symlink() for member in members):
                raise CVScratchPurgeError("Scratch contains a symlink; no deletion is authorized.")
        except CVScratchPurgeError:
            raise
        except OSError as error:
            raise CVScratchPurgeError("Scratch creator generation is unavailable.") from error

        purged_files: List[str] = []
        extensions_to_purge = {".gbw", ".tmp", ".densities", ".bso", ".prop",
                               ".core", ".host", ".ges", ".int", ".uco"}
        candidates = [member for member in members if member.parent == scratch_path
                      and member.suffix in extensions_to_purge]
        if any(not stat.S_ISREG(member.lstat().st_mode) or member.lstat().st_nlink != 1
               for member in candidates):
            raise CVScratchPurgeError("Only private regular intermediate files may be deleted.")
        for member in candidates:
            member.unlink()
            purged_files.append(member.name)
        retained = [member.name for member in scratch_path.iterdir() if member != marker]
        directory_removed = bool(remove_dir and not retained)
        if directory_removed:
            marker.unlink()
            scratch_path.rmdir()
            del EphemeralScratchPurge._created[str(scratch_path)]

        return {
            "status": "purged",
            "purged_count": len(purged_files),
            "purged_files": purged_files,
            "directory_removed": directory_removed,
            "retained_files": retained,
        }


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def resolve_hdf5_path(h5_path: Optional[Union[str, Path]] = None) -> Path:
    """Admit an explicit external data file; never guess a source/CWD store."""
    artifact_root = os.environ.get("COCHEM_ARTIFACT_DIR") or os.environ.get("COCHEM_ARTIFACTS_DIR")
    if h5_path is None:
        if not artifact_root:
            raise CVCorrectionError("An explicit HDF5 target or configured external artifact root is required.")
        target = Path(artifact_root) / "BENCH_Workspace" / "landscape.h5"
    else:
        target = Path(h5_path)
        if not target.is_absolute():
            if not artifact_root:
                raise CVCorrectionError("A relative HDF5 target requires a configured external artifact root.")
            target = Path(artifact_root) / target
    if not target.is_absolute():
        raise CVCorrectionError("The configured artifact root must be absolute.")
    target = Path(os.path.abspath(target))
    try:
        assert_writable_path(target)
    except AirGapViolationError as error:
        raise CVCorrectionError(str(error)) from error
    for protected in (Path(__file__).resolve().parents[3], Path(sys.prefix).resolve()):
        if target == protected or protected in target.parents:
            raise CVCorrectionError("HDF5 data must be outside source and installed runtime roots.")
    lock_path = target.with_name(target.name + ".lock")
    for candidate in (target, lock_path, *target.parents):
        if candidate.is_symlink():
            raise CVCorrectionError("HDF5 data and lock paths require nonsymlink ancestors and targets.")
    for candidate in (target, lock_path):
        if candidate.exists():
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise CVCorrectionError("HDF5 data and locks must be private regular files.")
    return target


def commit_cv_to_hdf5(
    h5_path: Union[str, Path],
    result: CVCorrectionResult,
    timeout: float = 120.0,
) -> Path:
    """Write a numeric CV record to an admitted local file under a writer lock.

    This compatibility store does not certify a native scientific protocol or
    provide an atomic replacement/SWMR ledger publication service.
    """
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
    """Read a numeric compatibility record under the same local writer lock."""
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
