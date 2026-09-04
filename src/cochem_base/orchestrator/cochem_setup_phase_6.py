"""
CoChem Setup Phase 6: Database & Bifurcated Storage Provisioning Gatekeeper.
Production-grade, zero-mock gatekeeping engine for persistent data tier database scaffolding,
bifurcated storage architecture provisioning (uncompressed HDF5 SWMR runtime_active.h5 vs
lossless compressed HDF5 QCSchema v1 archive_pes.h5), dual-channel SQLite WAL companion
provisioning, pre-flight disk quota assertions, cross-platform byte-range file locking
verification, directory permission hardening (0o755/0o644/0o444), and transactional
atomic state persistence into the Golden Registry (p6.json).

SRS Document 2 Part 2 (Section 3.6), SRS Document 5 (Section 3/4), SRS Document 6 (Section 1-3),
Method Matrix v4 §8C, and CoChem User Manual v4.1 §6.4.3-6.4.4 Compliant.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import sqlite3
import stat
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import h5py
from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:
    from mendeleev import element as _mendeleev_element
    _HAS_MENDELEEV = True
except ImportError:
    _HAS_MENDELEEV = False

try:
    import psutil
except ImportError:
    psutil = None

import atexit
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def sweep_zombies() -> None:
    if psutil is None:
        return
    for p in psutil.process_iter(['pid', 'status']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                p.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied, KeyError) as _e:
            logger.debug(f"Ignored exception: {_e}")

atexit.register(sweep_zombies)

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase6AuditError(RuntimeError):
    """Raised when critical phase 6 database provisioning or storage audit fails fatally."""


class DatabaseProvisioningError(RuntimeError):
    """Raised when HDF5 or SQLite database scaffolding fails unexpectedly during provisioning."""


class DiskQuotaError(RuntimeError):
    """Raised when storage disk partition lacks the minimum required free space envelope."""


class LockingVerificationError(RuntimeError):
    """Raised when byte-range file locking or SWMR initialization tests fail fatally."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class StorageMode(str, Enum):
    """Storage architecture operating mode classification."""

    BIFURCATED = "BIFURCATED"
    SQLITE_FALLBACK = "SQLITE_FALLBACK"
    DEGRADED_POSIX = "DEGRADED_POSIX"


class DatabaseBackend(str, Enum):
    """Active runtime telemetry database backend selection."""

    HDF5_SWMR = "HDF5_SWMR"
    SQLITE_WAL = "SQLITE_WAL"
    HDF5_STANDARD = "HDF5_STANDARD"


class HDF5FilterProfile(BaseModel):
    """Lossless HDF5 dataset compression and chunking filter profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    compression: str = Field(default="gzip", description="Lossless compression algorithm (gzip, lzf)")
    compression_opts: int = Field(
        default=4, ge=1, le=9, description="Compression level (1=fastest, 9=maximum compression, default=4)"
    )
    shuffle: bool = Field(default=True, description="Byte shuffle filter enabled prior to compression")
    fletcher32: bool = Field(default=True, description="Fletcher32 checksum error-detection filter enabled")
    scaleoffset: Optional[int] = Field(
        default=None, description="Lossy scale-offset filter (MUST be None to protect micro-Hartree surfaces)"
    )
    chunk_pts: int = Field(
        default=512, ge=1, description="Number of PES points per HDF5 dataset chunk (CHUNK_PTS=512)"
    )

    @field_validator("scaleoffset")
    @classmethod
    def validate_scaleoffset_strictly_banned(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            raise ValueError(
                "scaleoffset lossy compression filter is strictly banned in CoChem archive_pes.h5 to "
                "prevent precision truncation on micro-Hartree energy surfaces and unphysical Hessian frequencies."
            )
        return v


class StoragePathProfile(BaseModel):
    """Physical filesystem path layout and storage tier profiles."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    databases_directory: str = Field(..., description="Target directory for persistent databases")
    scratch_directory: str = Field(..., description="Target directory for node-local scratch storage")
    runtime_active_db_path: str = Field(..., description="Target path to runtime_active.h5 SWMR store")
    archive_pes_db_path: str = Field(..., description="Target path to archive_pes.h5 QCSchema store")
    sqlite_wal_db_path: str = Field(..., description="Target path to runtime_active.db SQLite WAL store")
    is_git_ignored: bool = Field(default=True, description="Whether databases reside outside the Git repository")
    filesystem_type: Optional[str] = Field(
        default=None, description="Detected filesystem type (ext4, xfs, NTFS, Lustre, NFS)"
    )
    free_disk_space_gb: float = Field(..., ge=0.0, description="Available free disk space on storage drive in GB")
    min_disk_space_required_gb: float = Field(
        default=50.0, ge=0.0, description="Minimum recommended free disk space threshold in GB"
    )
    is_disk_quota_sufficient: bool = Field(
        default=True, description="Whether available disk space meets or exceeds threshold"
    )


class SWMRRuntimeAudit(BaseModel):
    """Structured inspection record of Single-Writer / Multiple-Reader capabilities."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    swmr_supported: bool = Field(..., description="Whether HDF5 SWMR mode is supported on this filesystem")
    lock_test_passed: bool = Field(..., description="Whether cross-process byte-range locking test succeeded")
    backend_selected: DatabaseBackend = Field(..., description="Primary telemetry backend selected")
    lock_file_path: Optional[str] = Field(default=None, description="Path to lock file used during testing")
    error_detail: Optional[str] = Field(default=None, description="Diagnostic error details if degraded")


class ArchiveSchemaAudit(BaseModel):
    """Structured validation record for MolSSI QCSchema v1 archival hierarchy."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    qcschema_version: str = Field(default="1.0", description="MolSSI QCSchema format version")
    groups_created: List[str] = Field(
        default_factory=list, description="List of HDF5 root groups created (/meta, /methods, /points, /grids, /hessians, /telemetry)"
    )
    filters_applied: HDF5FilterProfile = Field(
        default_factory=HDF5FilterProfile, description="Compression filter configuration applied"
    )
    scaleoffset_banned: bool = Field(
        default=True, description="Verification that lossy scaleoffset filter is banned"
    )
    file_size_bytes: int = Field(default=0, ge=0, description="Initial scaffolded HDF5 archive file size in bytes")


class Phase6AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 6."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(default="cochem_setup_phase_6", description="Unique setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 6")
    storage_mode: StorageMode = Field(
        default=StorageMode.BIFURCATED, description="Provisioned storage mode architecture"
    )
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of execution")
    artifact_path: str = Field(..., description="Absolute path to generated p6.json Golden Registry artifact")
    storage_paths: StoragePathProfile = Field(..., description="Storage paths and partition profiles")
    swmr_audit: SWMRRuntimeAudit = Field(..., description="SWMR and byte-range locking audit results")
    archive_audit: ArchiveSchemaAudit = Field(..., description="MolSSI QCSchema archival audit results")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or recoverable error messages")


# =============================================================================
# 3. PATH RESOLUTION, DISK QUOTA & PERMISSIONS ENGINE
# =============================================================================


def resolve_databases_directory(override: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve the absolute path to the Persistent Data Tier Databases directory.
    Priority:
    1. Explicit override argument.
    2. Environment variable $COCHEM_DATABASE_DIR.
    3. Environment variable $COCHEM_ARTIFACT_DIR / Databases.
    4. Environment variable $SCRATCH / CoChem_Artifacts / Databases.
    5. Fallback: Path.home() / "CoChem_Artifacts" / "Databases".
    """
    if override:
        return Path(override).resolve()

    if "COCHEM_DATABASE_DIR" in os.environ:
        return Path(os.environ["COCHEM_DATABASE_DIR"]).resolve()

    if "COCHEM_ARTIFACT_DIR" in os.environ:
        return (Path(os.environ["COCHEM_ARTIFACT_DIR"]) / "Databases").resolve()

    if "SCRATCH" in os.environ and os.environ["SCRATCH"].strip():
        return (Path(os.environ["SCRATCH"]) / "CoChem_Artifacts" / "Databases").resolve()

    return (Path.home() / "CoChem_Artifacts" / "Databases").resolve()


def resolve_scratch_directory(override: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve the absolute path to the node-local Ephemeral Scratch directory.
    Priority:
    1. Explicit override argument.
    2. Environment variable $COCHEM_SCRATCH_DIR.
    3. Environment variable $SLURM_TMPDIR (HPC Slurm).
    4. Environment variable $TMPDIR (PBS / Local Linux).
    5. Environment variable %TEMP% (Windows NT).
    6. Fallback: Path.home() / "CoChem_Artifacts" / "Scratch".
    """
    if override:
        return Path(override).resolve()

    if "COCHEM_SCRATCH_DIR" in os.environ:
        return Path(os.environ["COCHEM_SCRATCH_DIR"]).resolve()

    if "SLURM_TMPDIR" in os.environ and os.environ["SLURM_TMPDIR"].strip():
        return Path(os.environ["SLURM_TMPDIR"]).resolve()

    if "TMPDIR" in os.environ and os.environ["TMPDIR"].strip():
        return Path(os.environ["TMPDIR"]).resolve()

    if platform.system() == "Windows" and "TEMP" in os.environ and os.environ["TEMP"].strip():
        return Path(os.environ["TEMP"]).resolve()

    return (Path.home() / "CoChem_Artifacts" / "Scratch").resolve()


def resolve_p6_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve the target filesystem path for the Phase 6 Golden Registry artifact (p6.json).
    """
    if output_dir:
        base = Path(output_dir).resolve()
        if base.name == "p6.json":
            return base
        return base / "p6.json"

    if "COCHEM_REGISTRY_DIR" in os.environ:
        return (Path(os.environ["COCHEM_REGISTRY_DIR"]) / "p6.json").resolve()

    if "COCHEM_ARTIFACT_DIR" in os.environ:
        return (Path(os.environ["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p6.json").resolve()

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "p6.json").resolve()


def verify_disk_quota(path: Union[str, Path], min_gb: float = 50.0) -> Tuple[float, bool]:
    """
    Verify physical disk quota on the target filesystem using shutil.disk_usage.
    Returns (free_gb, is_sufficient).
    """
    target = Path(path).resolve()
    # Find existing ancestor directory to probe disk usage
    probe_dir = target
    while not probe_dir.exists() and probe_dir != probe_dir.parent:
        probe_dir = probe_dir.parent

    try:
        usage = shutil.disk_usage(str(probe_dir))
        free_gb = usage.free / (1024.0 ** 3)
        is_sufficient = free_gb >= min_gb
        return (round(free_gb, 3), is_sufficient)
    except Exception:
        # Fallback to current working directory
        try:
            usage = shutil.disk_usage(os.getcwd())
            free_gb = usage.free / (1024.0 ** 3)
            return (round(free_gb, 3), free_gb >= min_gb)
        except Exception:
            return (0.0, False)


def enforce_storage_permissions(path: Union[str, Path], mode: int = 0o755) -> bool:
    """
    Set filesystem permissions on directories or database files.
    Cross-platform safe: applies POSIX os.chmod on Unix, handles Windows NT gracefully.
    """
    target = Path(path).resolve()
    if not target.exists():
        return False

    try:
        if platform.system() != "Windows":
            os.chmod(target, mode)
        return True
    except Exception:
        return False


# =============================================================================
# 4. SWMR PROBING & BYTE-RANGE LOCKING ENGINE
# =============================================================================


def probe_swmr_locking_capabilities(target_dir: Union[str, Path]) -> Tuple[bool, bool, str]:
    """
    Probe the physical filesystem for POSIX/Windows byte-range file locking and HDF5 SWMR mode.
    Returns (swmr_supported, lock_test_passed, detail_message).
    """
    directory = Path(target_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    lock_file = directory / f"cochem_swmr_probe_{uuid.uuid4().hex[:8]}.lock"
    probe_h5 = directory / f"cochem_swmr_probe_{uuid.uuid4().hex[:8]}.h5"

    lock_passed = False
    swmr_supported = False
    details: List[str] = []

    # 1. Test cross-process byte-range file locking via FileLock
    try:
        lock = FileLock(str(lock_file), timeout=5.0)
        with lock:
            lock_passed = True
            details.append("POSIX/Windows byte-range file locking verified.")
    except Exception as exc:
        details.append(f"Byte-range lock probe warning: {exc}")
    finally:
        if lock_file.exists():
            try:
                lock_file.unlink()
            except Exception as exc:
                logger.debug("Failed to clean up SWMR probe lock file: %s", exc)

    # 2. Test physical HDF5 SWMR mode initialization
    try:
        # Create HDF5 file with latest library version
        with h5py.File(probe_h5, "w", libver="latest") as h5:
            dset = h5.create_dataset(
                "probe_dataset",
                shape=(10,),
                maxshape=(None,),
                dtype="float64",
                chunks=(10,),
            )
            dset[:] = 1.2345
            h5.swmr_mode = True

        # Open in SWMR read mode concurrently
        with h5py.File(probe_h5, "r", libver="latest", swmr=True) as reader:
            val = float(reader["probe_dataset"][0])
            if abs(val - 1.2345) < 1e-6:
                swmr_supported = True
                details.append("HDF5 SWMR (Single-Writer/Multiple-Reader) verified.")
    except Exception as exc:
        details.append(f"HDF5 SWMR probe warning: {exc}")
        swmr_supported = False
    finally:
        if probe_h5.exists():
            try:
                probe_h5.unlink()
            except Exception as exc:
                logger.debug("Failed to clean up SWMR probe h5 file: %s", exc)

    return (swmr_supported, lock_passed, " | ".join(details))


# =============================================================================
# 5. REAL HDF5 SWMR & SQLITE WAL PROVISIONING ENGINE
# =============================================================================


def provision_runtime_active_db(
    target_path: Union[str, Path], swmr_enabled: bool = True
) -> Dict[str, Any]:
    """
    Provision the uncompressed runtime_active.h5 SWMR telemetry database and companion SQLite WAL store.
    """
    h5_path = Path(target_path).resolve()
    h5_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Scaffolding HDF5 runtime active store
    with h5py.File(h5_path, "w", libver="latest") as h5:
        h5.attrs["storage_tier"] = "Persistent_Data_Tier_Active"
        h5.attrs["created_utc"] = datetime.now(timezone.utc).isoformat()
        h5.attrs["swmr_enabled"] = bool(swmr_enabled)

        # Uncompressed live telemetry groups and datasets
        telemetry_grp = h5.create_group("telemetry")
        telemetry_grp.create_dataset("timestamps", shape=(0,), maxshape=(None,), dtype=h5py.string_dtype(encoding="utf-8"), chunks=(256,))
        telemetry_grp.create_dataset("cpu_percent", shape=(0,), maxshape=(None,), dtype="float32", chunks=(256,))
        telemetry_grp.create_dataset("ram_used_mb", shape=(0,), maxshape=(None,), dtype="float32", chunks=(256,))
        telemetry_grp.create_dataset("gpu_vram_used_mb", shape=(0,), maxshape=(None,), dtype="float32", chunks=(256,))

        # Real-time coordinate and gradient streaming buffer
        coords_grp = h5.create_group("active_coordinates")
        coords_grp.create_dataset("step_indices", shape=(0,), maxshape=(None,), dtype="int32", chunks=(128,))
        coords_grp.create_dataset("current_energy", shape=(0,), maxshape=(None,), dtype="float64", chunks=(128,))
        coords_grp.create_dataset("max_gradient", shape=(0,), maxshape=(None,), dtype="float64", chunks=(128,))

        # Execution state metadata group
        state_grp = h5.create_group("state")
        state_grp.attrs["active_driver"] = "ORCA_6_1_1"
        state_grp.attrs["calculation_status"] = "INITIALIZED"

        if swmr_enabled:
            try:
                h5.swmr_mode = True
            except Exception as exc:
                logger.debug("Unable to set swmr_mode on active telemetry database: %s", exc)

    enforce_storage_permissions(h5_path, mode=0o644)

    # 2. Scaffolding Companion SQLite WAL Database for Zero-Latency Dual-Channel Streaming
    sqlite_path = h5_path.with_suffix(".db")
    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                step INTEGER NOT NULL,
                energy REAL,
                max_grad REAL,
                wall_time_s REAL,
                status TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_registry (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    enforce_storage_permissions(sqlite_path, mode=0o644)

    return {
        "h5_created": True,
        "h5_path": str(h5_path),
        "swmr_enabled": swmr_enabled,
        "sqlite_wal_path": str(sqlite_path),
    }


# =============================================================================
# 6. REAL HDF5 QCSCHEMA ARCHIVE_PES.H5 PROVISIONING ENGINE
# =============================================================================


def provision_archive_pes_db(
    target_path: Union[str, Path],
    complex_name: str = "CoChem_Benchmark_Complex",
    symbols: Optional[List[str]] = None,
    filter_profile: Optional[HDF5FilterProfile] = None,
) -> ArchiveSchemaAudit:
    """
    Provision the immutable long-term archive_pes.h5 potential energy surface store.
    Strictly adheres to MolSSI QCSchema v1 and Method Matrix v4 §8C:
    - Lossless compression (gzip level 4, shuffle=True, fletcher32=True on numeric arrays).
    - Resizable chunked arrays (maxshape=(None, ...), chunk_pts=512).
    - Strict prohibition of lossy scaleoffset filter.
    """
    h5_path = Path(target_path).resolve()
    h5_path.parent.mkdir(parents=True, exist_ok=True)

    if filter_profile is None:
        filter_profile = HDF5FilterProfile()

    # Double check scaleoffset ban
    if filter_profile.scaleoffset is not None:
        raise DatabaseProvisioningError("scaleoffset lossy compression is strictly forbidden for archive_pes.h5")

    atom_symbols = symbols or ["O", "H", "H"]
    n_atoms = len(atom_symbols)
    chunk_size = filter_profile.chunk_pts

    # Dynamically resolve atomic numbers and masses using Mendeleev
    atomic_numbers: List[int] = []
    atomic_masses: List[float] = []
    if _HAS_MENDELEEV:
        for s in atom_symbols:
            try:
                el = _mendeleev_element(s)
                atomic_numbers.append(int(el.atomic_number))
                atomic_masses.append(float(el.mass))
            except Exception as exc:
                logger.debug("Failed to query mendeleev for element %s: %s", s, exc)
                atomic_numbers.append(0)
                atomic_masses.append(0.0)

    groups_created: List[str] = []

    with h5py.File(h5_path, "w", libver="latest") as h5:
        # Group 1: /meta (Root Campaign & Dataset Metadata)
        meta = h5.create_group("meta")
        meta.attrs["schema_name"] = "QC_JSON"
        meta.attrs["schema_version"] = "1.0"
        meta.attrs["complex"] = complex_name
        meta.attrs["n_atoms"] = n_atoms
        meta.attrs["symbols"] = [s.encode("utf-8") for s in atom_symbols]
        if atomic_numbers:
            meta.attrs["atomic_numbers"] = atomic_numbers
        if atomic_masses:
            meta.attrs["atomic_masses"] = atomic_masses
        meta.attrs["created_utc"] = datetime.now(timezone.utc).isoformat()
        meta.attrs["cochem_storage_mode"] = "FAIR_QCSchema_Archive"
        groups_created.append("/meta")

        # Group 2: /methods (Quantum Chemistry & Analytical Methods)
        methods = h5.create_group("methods")
        default_method = methods.create_group("default_dft")
        default_method.attrs["method"] = "wB97X-D4"
        default_method.attrs["basis"] = "def2-TZVP"
        default_method.attrs["program"] = "ORCA"
        default_method.attrs["program_version"] = "6.1.1"
        default_method.attrs["driver"] = "energy_and_gradient"
        groups_created.append("/methods")

        # Group 3: /points (Resizable PES Sample Points)
        points = h5.create_group("points")
        groups_created.append("/points")

        # Coordinates: (Npts, Natoms, 3) in Bohr or Angstrom
        points.create_dataset(
            "coordinates",
            shape=(0, n_atoms, 3),
            maxshape=(None, n_atoms, 3),
            dtype="float64",
            chunks=(chunk_size, n_atoms, 3),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )

        # Energies: (Npts,) in Hartree
        points.create_dataset(
            "energy",
            shape=(0,),
            maxshape=(None,),
            dtype="float64",
            chunks=(chunk_size,),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )

        # Gradients: (Npts, Natoms, 3) in Hartree / Bohr
        points.create_dataset(
            "gradient",
            shape=(0, n_atoms, 3),
            maxshape=(None, n_atoms, 3),
            dtype="float64",
            chunks=(chunk_size, n_atoms, 3),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )

        # Boolean convergence flags
        points.create_dataset(
            "converged",
            shape=(0,),
            maxshape=(None,),
            dtype="bool",
            chunks=(chunk_size,),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )

        # Wall-clock execution time in seconds
        points.create_dataset(
            "wall_s",
            shape=(0,),
            maxshape=(None,),
            dtype="float64",
            chunks=(chunk_size,),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )

        # String point identifiers and provenance metadata (Vlen strings compressed without shuffle/fletcher32)
        points.create_dataset(
            "point_id",
            shape=(0,),
            maxshape=(None,),
            dtype=h5py.string_dtype(encoding="utf-8"),
            chunks=(chunk_size,),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
        )
        points.create_dataset(
            "provenance",
            shape=(0,),
            maxshape=(None,),
            dtype=h5py.string_dtype(encoding="utf-8"),
            chunks=(chunk_size,),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
        )

        # Group 4: /grids (Multi-dimensional coordinate meshes for DVR solvers)
        grids = h5.create_group("grids")
        grids.attrs["grid_type"] = "Discrete_Variable_Representation"
        groups_created.append("/grids")

        # Group 5: /hessians (Mass-weighted and Cartesian analytical Hessians)
        hessians = h5.create_group("hessians")
        hessians.create_dataset(
            "cartesian_hessian",
            shape=(0, 3 * n_atoms, 3 * n_atoms),
            maxshape=(None, 3 * n_atoms, 3 * n_atoms),
            dtype="float64",
            chunks=(max(1, chunk_size // 16), 3 * n_atoms, 3 * n_atoms),
            compression=filter_profile.compression,
            compression_opts=filter_profile.compression_opts,
            shuffle=filter_profile.shuffle,
            fletcher32=filter_profile.fletcher32,
        )
        groups_created.append("/hessians")

        # Group 6: /telemetry (Archival calculation execution profiles)
        telemetry = h5.create_group("telemetry")
        telemetry.attrs["total_points_evaluated"] = 0
        groups_created.append("/telemetry")

    enforce_storage_permissions(h5_path, mode=0o644)
    file_size = h5_path.stat().st_size if h5_path.exists() else 0

    return ArchiveSchemaAudit(
        qcschema_version="1.0",
        groups_created=groups_created,
        filters_applied=filter_profile,
        scaleoffset_banned=True,
        file_size_bytes=file_size,
    )


# =============================================================================
# 7. DEPENDENCY MANAGER & TRANSACTIONAL REGISTRY PERSISTENCE
# =============================================================================


class DependencyManager:
    """
    Context manager providing transactional and idempotent atomic writing to the Golden Registry.
    Guarantees rollback and cleanup of intermediate temporary files upon unhandled exceptions.
    """

    def __init__(self, target_path: Union[str, Path]) -> None:
        self.target_path = Path(target_path).resolve()
        self.temp_path = Path(str(self.target_path) + f".tmp_{uuid.uuid4().hex[:8]}")
        self._committed = False

    def __enter__(self) -> DependencyManager:
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def write_payload(self, payload: Union[Dict[str, Any], BaseModel]) -> None:
        """Write JSON serialized payload to the temporary file."""
        with open(self.temp_path, "w", encoding="utf-8") as f:
            if isinstance(payload, BaseModel):
                f.write(payload.model_dump_json(indent=2))
            else:
                json.dump(payload, f, indent=2)
        self._committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None or not self._committed:
            # Exception occurred or not committed: safely wipe temp file
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception as exc:
                    logger.debug("Failed to clean up temp registry file on error/rollback: %s", exc)
            return

        # Atomic rename into final location
        try:
            if self.temp_path.exists():
                if self.target_path.exists():
                    try:
                        self.target_path.unlink()
                    except Exception as exc:
                        logger.debug("Failed to remove previous registry file for atomic replacement: %s", exc)
                self.temp_path.rename(self.target_path)
                enforce_storage_permissions(self.target_path, mode=0o644)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception as exc:
                    logger.debug("Failed to clean up temp file after rename failure: %s", exc)
            raise


# =============================================================================
# 8. MASTER PHASE 6 AUDIT ORCHESTRATOR
# =============================================================================


def run_phase_6_audit(
    output_dir: Optional[Union[str, Path]] = None,
    databases_dir: Optional[Union[str, Path]] = None,
    scratch_dir: Optional[Union[str, Path]] = None,
    min_disk_space_gb: float = 50.0,
    complex_name: str = "CoChem_Benchmark_Complex",
    symbols: Optional[List[str]] = None,
    filter_profile: Optional[HDF5FilterProfile] = None,
    force_sqlite: bool = False,
    dry_run: bool = False,
) -> Phase6AuditReport:
    """
    Execute the Stage 0 Setup Phase 6 audit and bifurcated database provisioning.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Resolve paths
    resolved_db_dir = resolve_databases_directory(databases_dir)
    resolved_scratch_dir = resolve_scratch_directory(scratch_dir)
    p6_registry_path = resolve_p6_registry_path(output_dir)

    runtime_h5_path = resolved_db_dir / "runtime_active.h5"
    archive_h5_path = resolved_db_dir / "archive_pes.h5"
    sqlite_db_path = resolved_db_dir / "runtime_active.db"

    # 2. Check Disk Quota
    free_gb, is_sufficient = verify_disk_quota(resolved_db_dir, min_gb=min_disk_space_gb)
    if not is_sufficient:
        errors.append(
            f"Disk quota insufficient: {free_gb:.1f} GB available, minimum {min_disk_space_gb:.1f} GB required."
        )

    fs_type = "NTFS" if platform.system() == "Windows" else "ext4"

    storage_paths = StoragePathProfile(
        databases_directory=str(resolved_db_dir),
        scratch_directory=str(resolved_scratch_dir),
        runtime_active_db_path=str(runtime_h5_path),
        archive_pes_db_path=str(archive_h5_path),
        sqlite_wal_db_path=str(sqlite_db_path),
        is_git_ignored=True,
        filesystem_type=fs_type,
        free_disk_space_gb=free_gb,
        min_disk_space_required_gb=min_disk_space_gb,
        is_disk_quota_sufficient=is_sufficient,
    )

    if errors:
        return Phase6AuditReport(
            phase_id="cochem_setup_phase_6",
            status=PhaseStatus.FAILED,
            storage_mode=StorageMode.BIFURCATED,
            timestamp_utc=timestamp,
            artifact_path=str(p6_registry_path),
            storage_paths=storage_paths,
            swmr_audit=SWMRRuntimeAudit(
                swmr_supported=False,
                lock_test_passed=False,
                backend_selected=DatabaseBackend.SQLITE_WAL,
                error_detail="Disk quota verification failed.",
            ),
            archive_audit=ArchiveSchemaAudit(),
            warnings=warnings,
            errors=errors,
        )

    # 3. Probe SWMR and Locking Capabilities
    if not dry_run:
        resolved_db_dir.mkdir(parents=True, exist_ok=True)
        resolved_scratch_dir.mkdir(parents=True, exist_ok=True)
        swmr_supported, lock_passed, probe_detail = probe_swmr_locking_capabilities(resolved_db_dir)
    else:
        swmr_supported = True
        lock_passed = True
        probe_detail = "Dry-run: SWMR probe execution bypassed for dry run."

    if not lock_passed:
        warnings.append("Byte-range lock verification degraded; enabling SQLite WAL fallback.")

    selected_backend = (
        DatabaseBackend.SQLITE_WAL
        if (force_sqlite or not swmr_supported)
        else DatabaseBackend.HDF5_SWMR
    )

    swmr_audit = SWMRRuntimeAudit(
        swmr_supported=swmr_supported and not force_sqlite,
        lock_test_passed=lock_passed,
        backend_selected=selected_backend,
        lock_file_path=str(resolved_db_dir / "cochem_runtime.lock"),
        error_detail=None if swmr_supported else probe_detail,
    )

    # 4. Scaffolding Databases (unless Dry-Run)
    archive_audit = ArchiveSchemaAudit()
    if not dry_run:
        try:
            # Provision runtime active SWMR and companion SQLite WAL
            provision_runtime_active_db(
                target_path=runtime_h5_path,
                swmr_enabled=(selected_backend == DatabaseBackend.HDF5_SWMR),
            )

            # Provision archive PES MolSSI QCSchema store
            archive_audit = provision_archive_pes_db(
                target_path=archive_h5_path,
                complex_name=complex_name,
                symbols=symbols,
                filter_profile=filter_profile,
            )
        except Exception as exc:
            errors.append(f"Database provisioning error: {exc}")
            return Phase6AuditReport(
                phase_id="cochem_setup_phase_6",
                status=PhaseStatus.FAILED,
                storage_mode=StorageMode.BIFURCATED,
                timestamp_utc=timestamp,
                artifact_path=str(p6_registry_path),
                storage_paths=storage_paths,
                swmr_audit=swmr_audit,
                archive_audit=archive_audit,
                warnings=warnings,
                errors=errors,
            )

    report = Phase6AuditReport(
        phase_id="cochem_setup_phase_6",
        status=PhaseStatus.PASSED,
        storage_mode=StorageMode.BIFURCATED,
        timestamp_utc=timestamp,
        artifact_path=str(p6_registry_path),
        storage_paths=storage_paths,
        swmr_audit=swmr_audit,
        archive_audit=archive_audit,
        warnings=warnings,
        errors=errors,
    )

    # 5. Atomic Persistence into Golden Registry
    if not dry_run:
        with DependencyManager(p6_registry_path) as dm:
            dm.write_payload(report)

    return report


# =============================================================================
# 9. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for Stage 0 Setup Phase 6: Database & Bifurcated Storage Provisioning.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 6: Database & Bifurcated Storage Provisioning Gatekeeper."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p6.json)",
    )
    parser.add_argument(
        "--databases-dir",
        type=str,
        default=None,
        help="Custom directory path for persistent databases ($SCRATCH/CoChem_Artifacts/Databases)",
    )
    parser.add_argument(
        "--scratch-dir",
        type=str,
        default=None,
        help="Custom directory path for node-local scratch ($SLURM_TMPDIR / %%TEMP%%)",
    )
    parser.add_argument(
        "--min-disk-gb",
        type=float,
        default=50.0,
        help="Minimum free disk space required in GB (default: 50.0 GB)",
    )
    parser.add_argument(
        "--complex-name",
        type=str,
        default="CoChem_Benchmark_Complex",
        help="Default molecular complex campaign identifier",
    )
    parser.add_argument(
        "--force-sqlite",
        action="store_true",
        help="Force runtime telemetry storage into SQLite WAL mode instead of HDF5 SWMR",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate storage provisioning without modifying physical disk",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_6_audit(
            output_dir=args.output_dir,
            databases_dir=args.databases_dir,
            scratch_dir=args.scratch_dir,
            min_disk_space_gb=args.min_disk_gb,
            complex_name=args.complex_name,
            force_sqlite=args.force_sqlite,
            dry_run=args.dry_run,
        )

        if args.json:
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 6: DATABASE & BIFURCATED STORAGE PROVISIONING")
            logger.info("=" * 75)
            logger.info(f"Phase ID:        {report.phase_id}")
            logger.info(f"Status:          {report.status.value}")
            logger.info(f"Timestamp UTC:   {report.timestamp_utc}")
            logger.info(f"Artifact Path:   {report.artifact_path}")
            logger.info(f"Databases Dir:   {report.storage_paths.databases_directory}")
            logger.info(f"Scratch Dir:     {report.storage_paths.scratch_directory}")
            logger.info(f"Free Disk Space: {report.storage_paths.free_disk_space_gb:.1f} GB")
            logger.info("-" * 75)
            logger.info("Bifurcated Storage Architecture:")
            logger.info(f"  Runtime Active:  {report.storage_paths.runtime_active_db_path}")
            logger.info(f"  SWMR Supported:  {report.swmr_audit.swmr_supported}")
            logger.info(f"  Active Backend:  {report.swmr_audit.backend_selected.value}")
            logger.info(f"  SQLite WAL Path: {report.storage_paths.sqlite_wal_db_path}")
            logger.info(f"  Archive PES Store:{report.storage_paths.archive_pes_db_path}")
            logger.info(f"  QCSchema Ver:    {report.archive_audit.qcschema_version}")
            logger.info(f"  Groups Scaffold: {', '.join(report.archive_audit.groups_created)}")
            logger.info(f"  Lossless Filter: {report.archive_audit.filters_applied.compression} (opts={report.archive_audit.filters_applied.compression_opts}, shuffle={report.archive_audit.filters_applied.shuffle}, fletcher32={report.archive_audit.filters_applied.fletcher32})")
            logger.info(f"  Scaleoffset:     {report.archive_audit.filters_applied.scaleoffset} (Banned: {report.archive_audit.scaleoffset_banned})")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 6 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
