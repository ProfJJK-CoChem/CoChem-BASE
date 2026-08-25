#!/usr/bin/env python3
r"""Stage 7.0: Thread-Safe Atomic I/O, POSIX/Windows Locking, and SWMR HDF5 Persistence.

Authoritative Implementation: cochem_bench.bench_libraries.swmr_hdf5_manager
System Domain: CoChem-BENCH Defensive Infrastructure & Data Tier

Key Capabilities:
1. Air-Gap Safety Contract: Dynamically resolves all file and registry paths via
   COCHEM_ARTIFACTS_DIR, raising a fatal RuntimeError if the environment variable is missing.
2. AtomicJSONManager:
   - Cross-platform process-safe atomic JSON file locking utilizing filelock.FileLock.
   - Strict 10-second timeout raising CoChemRegistryLockError on contention.
   - Stale Lock Sweeper: Inspects lock files, verifies process vitality via psutil.pid_exists(),
     and safely unlinks orphaned locks left behind by terminated processes.
   - Atomic Write: Writes updates to an isolated .tmp file rooted in the Air-Gap, forces OS disk
     flush via os.fsync(f.fileno()), and atomically commits via os.replace().
3. BenchHDF5Serializer:
   - Single-Writer/Multiple-Reader (SWMR) HDF5 persistence instantiated exclusively with
     h5py.File(..., libver='latest', swmr=True) / f.swmr_mode = True.
   - High-frequency telemetry optimization configuring chunk cache and datagram buffer to exactly 8192 bytes.
   - Atomic dataset flushes: Executes an explicit dataset.flush() immediately after every append operation,
     ensuring real-time visibility to external readers and the Voila UI without HDF5-DIAG corruption faults.
4. Dynamic Mendeleev Integration:
   - Dynamic atomic and isotopic mass resolution queried directly from the Mendeleev database.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task7_swmr.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Sequence, Tuple, Union

import filelock
import h5py
import numpy as np
import psutil
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ==============================================================================
# Constant Definitions
# ==============================================================================

# Default timeout in seconds for acquiring registry file locks
DEFAULT_LOCK_TIMEOUT_SEC: float = 10.0

# Exact chunk cache and datagram buffer size in bytes (8 KB)
DEFAULT_CHUNK_CACHE_BYTES: int = 8192

# Default chunk element count for 1D float64 datasets (1024 * 8 bytes = 8192 bytes)
DEFAULT_FLOAT64_CHUNK_SIZE: int = 1024


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class CoChemSWMRHDF5BaseError(Exception):
    """Base exception for all atomic I/O and SWMR HDF5 persistence operations."""
    pass


class CoChemRegistryLockError(CoChemSWMRHDF5BaseError, TimeoutError):
    """Raised when file lock acquisition on the registry or JSON state times out or fails."""
    pass


class CoChemHDF5Error(CoChemSWMRHDF5BaseError):
    """Raised when HDF5 initialization, dataset creation, or serialization fails."""
    pass


class CoChemStaleLockError(CoChemSWMRHDF5BaseError):
    """Raised when stale lock evaluation encounters an unrecoverable failure."""
    pass


# ==============================================================================
# Pydantic v2 Data Models
# ==============================================================================

class AtomicLockMetadata(BaseModel):
    """Structured metadata written to companion .lock files for vitality tracking."""
    model_config = ConfigDict(frozen=True)

    pid: int = Field(description="Operating system process ID of the lock holder")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of lock acquisition",
    )
    target_file: str = Field(description="Filesystem path of the guarded target file")
    host_id: Optional[str] = Field(default=None, description="Optional host identifier")


class SWMRWriteReport(BaseModel):
    """Structured telemetry report emitted following an atomic SWMR dataset append."""
    model_config = ConfigDict(frozen=True)

    hdf5_path: str = Field(description="Filesystem path to the target HDF5 container")
    dataset_path: str = Field(description="Internal HDF5 node path of the dataset")
    records_appended: int = Field(description="Number of new data records appended")
    flushed: bool = Field(default=True, description="True if explicit dataset.flush() completed")
    shape: Tuple[int, ...] = Field(description="New dataset shape post-append")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the write operation",
    )


class HDF5DatasetManifest(BaseModel):
    """Manifest record describing an active dataset in landscape.h5."""
    model_config = ConfigDict(frozen=True)

    dataset_name: str = Field(description="Full node path within the HDF5 hierarchy")
    shape: Tuple[int, ...] = Field(description="Current multi-dimensional shape")
    dtype: str = Field(description="NumPy string representation of the data type")
    chunk_size: Optional[Tuple[int, ...]] = Field(default=None, description="HDF5 chunk dimensions")
    last_flushed_timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of last flush",
    )


# ==============================================================================
# Dynamic Environment & Path Resolution Helpers (Air-Gap Contract)
# ==============================================================================

def get_cochem_artifacts_dir() -> Path:
    """Dynamically resolves the CoChem artifacts root directory via COCHEM_ARTIFACTS_DIR env var.

    Raises:
        RuntimeError: If COCHEM_ARTIFACTS_DIR environment variable is missing or empty.
    """
    env_path = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if not env_path or not env_path.strip():
        raise RuntimeError("Air-Gap Fatal: COCHEM_ARTIFACTS_DIR environment variable is missing or empty.")
    return Path(env_path).resolve()


def get_registry_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic Registry directory under the artifacts root."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "Registry"


def get_bench_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic BENCH_Workspace directory under the artifacts root."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "BENCH_Workspace"


def get_scratch_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic Scratch workspace directory under BENCH_Workspace."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "BENCH_Workspace" / "Scratch"


def get_element_mass_mendeleev(symbol: str) -> float:
    """Dynamically retrieves the atomic mass of an element via the Mendeleev library.

    Args:
        symbol: Standard chemical element symbol (e.g. 'C', 'H', 'Fe').

    Returns:
        Atomic weight / mass as float.

    Raises:
        ValueError: If element mass cannot be resolved.
    """
    try:
        elem_obj = element(symbol)
    except Exception as exc:
        raise ValueError(f"Element symbol '{symbol}' not recognized by Mendeleev database: {exc}") from exc

    mass_val = elem_obj.atomic_weight or elem_obj.mass
    if mass_val is None:
        raise ValueError(f"Atomic mass for element '{symbol}' could not be retrieved from Mendeleev.")
    return float(mass_val)


# ==============================================================================
# 1. AtomicJSONManager (Cross-Platform Thread-Safe & Process-Safe Registry I/O)
# ==============================================================================

class AtomicJSONManager:
    """Thread-Safe and Process-Safe Atomic I/O Manager for JSON Registry files.

    Guarantees:
    1. Cross-Platform Safety: Uses filelock.FileLock with a strict 10-second timeout.
    2. Stale Lock Sweeper: Probes PID vitality using psutil.pid_exists() and unlinks dead locks.
    3. Atomic Write: Writes updates to a .tmp file rooted in the Air-Gap, forces buffer
       sync to disk via os.fsync(f.fileno()), and atomically swaps via os.replace().
    """

    def __init__(
        self,
        target_path: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        timeout_sec: float = DEFAULT_LOCK_TIMEOUT_SEC,
        lock_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self._target_path = Path(target_path).resolve() if target_path else None
        self._lock_path = Path(lock_path).resolve() if lock_path else None
        self.timeout_sec = float(timeout_sec)
        self._active_lock: Optional[filelock.FileLock] = None

    def resolve_target_path(self) -> Path:
        """Resolves the dynamic target JSON file path, ensuring parent directory exists."""
        if self._target_path:
            target = self._target_path
        else:
            target = get_registry_workspace_dir(self.artifacts_dir) / "cochem_system_config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def resolve_lock_path(self) -> Path:
        """Resolves the companion lock file path."""
        if self._lock_path:
            return self._lock_path
        target = self.resolve_target_path()
        return target.parent / f"{target.name}.lock"

    def resolve_tmp_path(self) -> Path:
        """Resolves the intermediate temporary file path strictly rooted in the Air-Gap."""
        target = self.resolve_target_path()
        return target.parent / f"{target.name}.tmp"

    def sweep_stale_lock(self, lock_file: Optional[Union[str, Path]] = None) -> bool:
        """Inspects the target lock file and unlinks it if the owning process is dead.

        Args:
            lock_file: Optional lock file path override.

        Returns:
            True if a stale lock was identified and unlinked, False otherwise.
        """
        lock_p = Path(lock_file).resolve() if lock_file else self.resolve_lock_path()
        if not lock_p.exists():
            return False

        # Read lock file content to extract owning PID
        pid: Optional[int] = None
        try:
            content = lock_p.read_text(encoding="utf-8").strip()
            if content:
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and "pid" in data:
                        pid = int(data["pid"])
                except json.JSONDecodeError:
                    if content.isdigit():
                        pid = int(content)
        except OSError:
            pass

        if pid is not None:
            if pid <= 0:
                try:
                    lock_p.unlink(missing_ok=True)
                    logger.warning("Swept invalid non-positive PID %d lock at %s", pid, lock_p)
                    return True
                except OSError:
                    return False

            if not psutil.pid_exists(pid):
                try:
                    lock_p.unlink(missing_ok=True)
                    logger.warning("Swept stale lock file at %s owned by dead PID %d", lock_p, pid)
                    return True
                except OSError:
                    return False
            else:
                try:
                    proc = psutil.Process(pid)
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        lock_p.unlink(missing_ok=True)
                        logger.warning("Swept stale lock file at %s owned by zombie PID %d", lock_p, pid)
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                return False

        # If PID is not recorded or unparseable, check age
        try:
            mtime = lock_p.stat().st_mtime
            age_sec = time.time() - mtime
            if age_sec > max(60.0, self.timeout_sec * 3.0):
                lock_p.unlink(missing_ok=True)
                logger.warning("Swept unparseable aged lock file at %s (age: %.1fs)", lock_p, age_sec)
                return True
        except OSError:
            pass

        return False

    def _write_lock_metadata(self, lock: filelock.FileLock, lock_p: Path) -> None:
        """Safely records PID and timestamp metadata into the lock file using its active descriptor."""
        try:
            metadata = AtomicLockMetadata(
                pid=os.getpid(),
                target_file=str(self.resolve_target_path()),
            )
            raw_bytes = (metadata.model_dump_json() + "\n").encode("utf-8")
            fd = getattr(getattr(lock, "_context", None), "lock_file_fd", None)
            if fd is not None and isinstance(fd, int) and fd >= 0:
                os.lseek(fd, 0, os.SEEK_SET)
                written = os.write(fd, raw_bytes)
                os.ftruncate(fd, written)
                os.fsync(fd)
                os.lseek(fd, 0, os.SEEK_SET)
            else:
                lock_p.write_text(raw_bytes.decode("utf-8"), encoding="utf-8")
        except OSError:
            pass

    def acquire_lock(self, timeout: Optional[float] = None) -> filelock.FileLock:
        """Acquires exclusive cross-platform lock with strict timeout and stale sweep.

        Args:
            timeout: Optional timeout override in seconds (defaults to self.timeout_sec).

        Returns:
            Active acquired filelock.FileLock instance.

        Raises:
            CoChemRegistryLockError: If lock acquisition times out.
        """
        lock_p = self.resolve_lock_path()
        t = float(timeout) if timeout is not None else self.timeout_sec
        lock = filelock.FileLock(str(lock_p), timeout=t)

        try:
            lock.acquire(timeout=t)
            self._active_lock = lock
            self._write_lock_metadata(lock, lock_p)
            return lock
        except filelock.Timeout:
            if self.sweep_stale_lock(lock_p):
                try:
                    lock.acquire(timeout=min(2.0, t))
                    self._active_lock = lock
                    self._write_lock_metadata(lock, lock_p)
                    return lock
                except filelock.Timeout:
                    pass

            raise CoChemRegistryLockError(
                f"Failed to acquire atomic lock on {lock_p} within {t:.1f}s timeout."
            )

    def read_json(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Reads and parses JSON under exclusive atomic lock protection.

        Args:
            timeout: Optional lock acquisition timeout in seconds.

        Returns:
            Parsed dictionary of the JSON contents.

        Raises:
            FileNotFoundError: If the target JSON file does not exist.
            CoChemRegistryLockError: If lock acquisition fails.
            json.JSONDecodeError: If JSON syntax is malformed.
        """
        target_path = self.resolve_target_path()
        lock = self.acquire_lock(timeout=timeout)
        try:
            if not target_path.exists():
                raise FileNotFoundError(f"Target JSON file does not exist at {target_path}")
            raw_text = target_path.read_text(encoding="utf-8")
            return json.loads(raw_text)
        finally:
            lock.release()

    def write_json(
        self,
        data: Union[Dict[str, Any], BaseModel, str],
        indent: int = 2,
        timeout: Optional[float] = None,
    ) -> Path:
        """Atomically writes JSON updates via temp file, fsync, and atomic swap.

        Args:
            data: Data payload as dictionary, Pydantic model, or JSON string.
            indent: JSON indentation spaces.
            timeout: Optional lock acquisition timeout in seconds.

        Returns:
            Resolved Path to the successfully written master file.

        Raises:
            CoChemRegistryLockError: If lock acquisition times out.
        """
        target_path = self.resolve_target_path()
        tmp_path = self.resolve_tmp_path()

        if isinstance(data, BaseModel):
            json_str = data.model_dump_json(indent=indent)
        elif isinstance(data, str):
            json_str = data
        else:
            json_str = json.dumps(data, indent=indent)

        lock = self.acquire_lock(timeout=timeout)
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, target_path)
            return target_path
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            lock.release()

    def update_json(
        self,
        mutation_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        indent: int = 2,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Performs an atomic read-modify-write cycle under single lock hold.

        Args:
            mutation_fn: Callable taking the current dict and returning updated dict.
            indent: JSON indentation spaces.
            timeout: Optional lock timeout in seconds.

        Returns:
            The newly modified and persisted dictionary.
        """
        target_path = self.resolve_target_path()
        tmp_path = self.resolve_tmp_path()

        lock = self.acquire_lock(timeout=timeout)
        try:
            if target_path.exists():
                current_data = json.loads(target_path.read_text(encoding="utf-8"))
            else:
                current_data = {}

            updated_data = mutation_fn(current_data)
            json_str = json.dumps(updated_data, indent=indent)

            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, target_path)
            return updated_data
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            lock.release()

    def __enter__(self) -> AtomicJSONManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._active_lock is not None and self._active_lock.is_locked:
            self._active_lock.release()
            self._active_lock = None


# ==============================================================================
# 2. BenchHDF5Serializer (SWMR-Mode HDF5 Persistence & 8192-Byte Datagrams)
# ==============================================================================

class BenchHDF5Serializer:
    """Single-Writer / Multiple-Reader (SWMR) HDF5 Manager for High-Tier Extrapolations.

    Guarantees:
    1. Instantiates HDF5 exclusively with libver='latest' and SWMR write/read mode.
    2. Configures chunk cache and datagram buffer size to exactly 8192 bytes (rdcc_nbytes=8192).
    3. Executes explicit dataset.flush() immediately after every append operation.
    """

    def __init__(
        self,
        hdf5_path: Optional[Union[str, Path]] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        chunk_cache_bytes: int = DEFAULT_CHUNK_CACHE_BYTES,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self._hdf5_path = Path(hdf5_path).resolve() if hdf5_path else None
        self.chunk_cache_bytes = int(chunk_cache_bytes)

    def resolve_hdf5_path(self) -> Path:
        """Resolves the dynamic HDF5 storage path under BENCH_Workspace, ensuring parent exists."""
        if self._hdf5_path:
            target = self._hdf5_path
        else:
            target = get_bench_workspace_dir(self.artifacts_dir) / "landscape.h5"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def initialize_database(self, wipe_existing: bool = False) -> Path:
        """Initializes the master HDF5 container in SWMR mode with standard groups.

        Args:
            wipe_existing: If True, recreates file from scratch.

        Returns:
            Resolved Path to the initialized HDF5 file.
        """
        target_path = self.resolve_hdf5_path()
        mode = "w" if wipe_existing or not target_path.exists() else "a"

        with h5py.File(
            str(target_path),
            mode,
            libver="latest",
            rdcc_nbytes=self.chunk_cache_bytes,
        ) as f:
            for grp_name in ["scf", "opt", "cbs", "composite", "provenance", "live_telemetry"]:
                if grp_name not in f:
                    f.create_group(grp_name)

            f.attrs["cochem_version"] = "2.0.0"
            f.attrs["schema_version"] = "4.0.0"
            f.attrs["init_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            f.attrs["datagram_buffer_bytes"] = self.chunk_cache_bytes

            if not f.swmr_mode:
                f.swmr_mode = True

        return target_path

    @contextlib.contextmanager
    def open_writer(self) -> Generator[h5py.File, None, None]:
        """Context manager opening the HDF5 file in append mode with SWMR activated."""
        target_path = self.resolve_hdf5_path()
        if not target_path.exists():
            self.initialize_database()

        f = h5py.File(
            str(target_path),
            "a",
            libver="latest",
            rdcc_nbytes=self.chunk_cache_bytes,
        )
        try:
            if not f.swmr_mode:
                f.swmr_mode = True
            yield f
        finally:
            try:
                f.flush()
            except Exception:
                pass
            f.close()

    @contextlib.contextmanager
    def open_reader(self) -> Generator[h5py.File, None, None]:
        """Context manager opening the HDF5 file in read-only SWMR mode."""
        target_path = self.resolve_hdf5_path()
        if not target_path.exists():
            raise FileNotFoundError(f"HDF5 database not found at {target_path}")

        f = h5py.File(
            str(target_path),
            "r",
            libver="latest",
            swmr=True,
            rdcc_nbytes=self.chunk_cache_bytes,
        )
        try:
            yield f
        finally:
            f.close()

    def ensure_extensible_dataset(
        self,
        file_handle: h5py.File,
        dataset_path: str,
        sample_shape: Tuple[int, ...],
        dtype: str = "float64",
        chunks: Optional[Tuple[int, ...]] = None,
    ) -> h5py.Dataset:
        """Guarantees existence of an extensible dataset configured with 8192-byte chunks."""
        if dataset_path in file_handle:
            return file_handle[dataset_path]

        # Calculate chunk dimensions matching 8192-byte datagram
        dtype_itemsize = np.dtype(dtype).itemsize
        if chunks is None:
            if len(sample_shape) == 1:
                chunk_len = max(1, min(DEFAULT_FLOAT64_CHUNK_SIZE, self.chunk_cache_bytes // max(1, dtype_itemsize)))
                chunks = (chunk_len,)
            else:
                row_items = int(np.prod(sample_shape[1:])) if len(sample_shape) > 1 else 1
                row_bytes = row_items * dtype_itemsize
                rows_per_chunk = max(1, self.chunk_cache_bytes // max(1, row_bytes))
                chunks = (rows_per_chunk,) + sample_shape[1:]

        maxshape: Tuple[Optional[int], ...] = (None,) + sample_shape[1:]
        initial_shape: Tuple[int, ...] = (0,) + sample_shape[1:]

        parent_group = "/".join(dataset_path.strip("/").split("/")[:-1])
        if parent_group and parent_group not in file_handle:
            file_handle.create_group(parent_group)

        return file_handle.create_dataset(
            dataset_path,
            shape=initial_shape,
            maxshape=maxshape,
            dtype=dtype,
            chunks=chunks,
        )

    def append_scf_energy(
        self,
        dataset_path: str,
        energy: float,
        file_handle: Optional[h5py.File] = None,
    ) -> SWMRWriteReport:
        """Appends a single SCF energy float, immediately executing dataset.flush().

        Args:
            dataset_path: Internal HDF5 path (e.g. '/scf/energies').
            energy: SCF energy in Hartrees as float.
            file_handle: Optional active open writer file handle.

        Returns:
            SWMRWriteReport confirming atomic write and flush.
        """
        target_path = self.resolve_hdf5_path()

        def _do_append(f: h5py.File) -> SWMRWriteReport:
            ds = self.ensure_extensible_dataset(
                file_handle=f,
                dataset_path=dataset_path,
                sample_shape=(1,),
                dtype="float64",
                chunks=(DEFAULT_FLOAT64_CHUNK_SIZE,),
            )

            current_len = ds.shape[0]
            ds.resize((current_len + 1,))
            ds[current_len] = float(energy)

            # Mandatory Atomic SWMR Flush
            ds.flush()
            f.flush()

            return SWMRWriteReport(
                hdf5_path=str(target_path),
                dataset_path=dataset_path,
                records_appended=1,
                flushed=True,
                shape=tuple(ds.shape),
            )

        if file_handle is not None:
            return _do_append(file_handle)

        with self.open_writer() as f:
            return _do_append(f)

    def append_array(
        self,
        dataset_path: str,
        data: Union[np.ndarray, Sequence[Any]],
        dtype: str = "float64",
        file_handle: Optional[h5py.File] = None,
    ) -> SWMRWriteReport:
        """Appends a multi-dimensional array or block to an extensible HDF5 dataset.

        Args:
            dataset_path: Internal HDF5 path (e.g. '/opt/gradients').
            data: Numerical array or sequence of values.
            dtype: Target NumPy data type string.
            file_handle: Optional active open writer file handle.

        Returns:
            SWMRWriteReport confirming atomic write and flush.
        """
        arr = np.ascontiguousarray(data, dtype=dtype)
        if arr.ndim == 1:
            records_count = arr.shape[0]
            incoming_sample_shape = (1,)
        else:
            records_count = arr.shape[0]
            incoming_sample_shape = (1,) + arr.shape[1:]

        target_path = self.resolve_hdf5_path()

        def _do_append_arr(f: h5py.File) -> SWMRWriteReport:
            ds = self.ensure_extensible_dataset(
                file_handle=f,
                dataset_path=dataset_path,
                sample_shape=incoming_sample_shape,
                dtype=dtype,
            )

            current_len = ds.shape[0]
            new_len = current_len + records_count
            ds.resize((new_len,) + ds.shape[1:])

            if arr.ndim == 1 and ds.ndim == 1:
                ds[current_len:new_len] = arr
            else:
                ds[current_len:new_len, ...] = arr

            # Mandatory Atomic SWMR Flush
            ds.flush()
            f.flush()

            return SWMRWriteReport(
                hdf5_path=str(target_path),
                dataset_path=dataset_path,
                records_appended=records_count,
                flushed=True,
                shape=tuple(ds.shape),
            )

        if file_handle is not None:
            return _do_append_arr(file_handle)

        with self.open_writer() as f:
            return _do_append_arr(f)

    def store_composite_result(
        self,
        calc_id: str,
        results: Dict[str, Any],
        attributes: Optional[Dict[str, Any]] = None,
        file_handle: Optional[h5py.File] = None,
    ) -> SWMRWriteReport:
        """Stores composite extrapolation limit dictionaries and attributes in HDF5.

        Args:
            calc_id: Unique calculation identifier (e.g. 'calc_h2o_cbs_01').
            results: Dictionary of numerical extrapolation metrics.
            attributes: Optional metadata dictionary.
            file_handle: Optional active open writer file handle.

        Returns:
            SWMRWriteReport confirming atomic write and flush.
        """
        target_path = self.resolve_hdf5_path()
        base_group = f"/composite/{calc_id}"

        def _do_store(f: h5py.File) -> SWMRWriteReport:
            if base_group not in f:
                grp = f.create_group(base_group)
            else:
                grp = f[base_group]

            if attributes:
                for k, v in attributes.items():
                    grp.attrs[str(k)] = v

            for k, val in results.items():
                node_path = f"{base_group}/{k}"
                if isinstance(val, (int, float, bool, np.number)):
                    val_arr = np.array(val, dtype=np.float64 if isinstance(val, (float, np.floating)) else np.int64)
                    if node_path in f:
                        f[node_path][...] = val_arr
                    else:
                        f.create_dataset(node_path, data=val_arr)
                    f[node_path].flush()
                elif isinstance(val, str):
                    if node_path in f:
                        del f[node_path]
                    f.create_dataset(node_path, data=val, dtype=h5py.string_dtype(encoding="utf-8"))
                    f[node_path].flush()
                elif isinstance(val, (list, tuple, np.ndarray)):
                    val_arr = np.ascontiguousarray(val)
                    if node_path in f:
                        del f[node_path]
                    f.create_dataset(node_path, data=val_arr)
                    f[node_path].flush()

            f.flush()

            return SWMRWriteReport(
                hdf5_path=str(target_path),
                dataset_path=base_group,
                records_appended=len(results),
                flushed=True,
                shape=(len(results),),
            )

        if file_handle is not None:
            return _do_store(file_handle)

        with self.open_writer() as f:
            return _do_store(f)

    def read_composite_result(self, calc_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Reads back composite results and metadata attributes under SWMR reader mode.

        Args:
            calc_id: Unique calculation identifier.

        Returns:
            Tuple of (results_dict, attributes_dict).
        """
        base_group = f"/composite/{calc_id}"
        with self.open_reader() as f:
            if base_group not in f:
                raise KeyError(f"Composite calculation '{calc_id}' not found in HDF5 database.")

            grp = f[base_group]
            attrs_dict = {k: v for k, v in grp.attrs.items()}

            results_dict: Dict[str, Any] = {}
            for k in grp.keys():
                item = grp[k]
                if isinstance(item, h5py.Dataset):
                    item.refresh()
                    val = item[...]
                    if val.shape == ():
                        scalar_val = val.item()
                        if isinstance(scalar_val, bytes):
                            scalar_val = scalar_val.decode("utf-8")
                        results_dict[k] = scalar_val
                    else:
                        results_dict[k] = val

        return results_dict, attrs_dict

    def read_dataset(self, dataset_path: str, refresh: bool = True) -> np.ndarray:
        """Reads array data from the specified HDF5 dataset in SWMR read mode.

        Args:
            dataset_path: Internal HDF5 path to dataset.
            refresh: If True, executes dataset.refresh() to see latest writer updates.

        Returns:
            NumPy array copy of dataset contents.

        Raises:
            KeyError: If dataset does not exist.
        """
        with self.open_reader() as f:
            if dataset_path not in f:
                raise KeyError(f"Dataset '{dataset_path}' does not exist in HDF5 container.")

            ds = f[dataset_path]
            if not isinstance(ds, h5py.Dataset):
                raise KeyError(f"Node '{dataset_path}' is a group, not a dataset.")

            if refresh:
                ds.refresh()

            return np.array(ds[...])

    def get_dataset_shape(self, dataset_path: str, refresh: bool = True) -> Tuple[int, ...]:
        """Returns the active multi-dimensional shape of an HDF5 dataset."""
        with self.open_reader() as f:
            if dataset_path not in f:
                raise KeyError(f"Dataset '{dataset_path}' does not exist in HDF5 container.")
            ds = f[dataset_path]
            if refresh:
                ds.refresh()
            return tuple(ds.shape)
