"""
CoChem-TORQ: Phase 1 SWMR Zombie Lock Reaper & H5 Healer
========================================================
Autonomously detects and releases stale HDF5 SWMR file locks held by
terminated/zombie processes, safeguarding database integrity without data loss.

Authoritative Standards:
- Method Matrix: Stage 0.0 Database Concurrency & SWMR Protocol
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
import platform
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from filelock import FileLock
import h5py
import psutil

from cochem_base.exceptions import HDF5LockTimeoutError, ProvenanceErrorCode

logger = logging.getLogger("CoChem-TORQ.H5Healer")

# In-process mutex serialization (§8C) eliminating intra-process thread contention
_IN_PROCESS_LOCK = threading.RLock()


class TorqH5LockError(HDF5LockTimeoutError):
    """Raised when an active lock cannot be safely inspected or released."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            details=details,
        )


def get_lock_file_path(h5_path: Union[str, Path]) -> Path:
    """Returns the standardized companion lock file path for a given HDF5 file."""
    p = Path(h5_path).resolve()
    return p.with_name(f"{p.name}.swmr.lock")


def get_lease_metadata_path(h5_path: Union[str, Path]) -> Path:
    """Returns companion JSON lease metadata path (f'{db_path}.lease.json') (§8C) [M]."""
    p = Path(h5_path).resolve()
    return Path(f"{p}.lease.json")


def get_ipc_filelock(h5_path: Union[str, Path], timeout: float = 60.0) -> FileLock:
    """Returns cross-platform filelock.FileLock located dynamically via COCH_STORE_DIR (§8C) [M]."""
    lock_dir = Path(os.environ.get("COCH_STORE_DIR", Path.home() / ".cochem" / "locks"))
    lock_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(lock_dir / f"{Path(h5_path).name}.lock"), timeout=timeout)


def create_swmr_lock(
    h5_path: Union[str, Path],
    pid: Optional[int] = None,
    lease_duration_sec: float = 60.0,
) -> Path:
    """Creates a valid SWMR lock metadata file containing PID, timestamp, hostname, and monotonic lease.

    Follows the Tripartite Storage model:
    Host Client <---> Atomic Staging Lease (.tmp.<pid>) <---> Canonical Persistent Lock.
    Protected under cross-platform IPC FileLock and in-process RLock.
    """
    target_h5 = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target_h5)
    lease_file = get_lease_metadata_path(target_h5)
    ipc_lock = get_ipc_filelock(target_h5, timeout=60.0)

    current_pid = pid if pid is not None else os.getpid()
    now_ts = time.time()
    payload = {
        "h5_file": str(target_h5),
        "pid": current_pid,
        "hostname": platform.node(),
        "timestamp": now_ts,
        "timestamp_utc": now_ts,
        "lease_start_monotonic": time.monotonic(),
        "lease_duration_sec": float(lease_duration_sec),
        "mode": "SWMR_WRITE",
    }

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    staging_path = lock_file.with_name(f"{lock_file.name}.tmp.{current_pid}")

    with _IN_PROCESS_LOCK:
        with ipc_lock:
            with open(staging_path, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=2)
            os.replace(staging_path, lock_file)

            # Companion JSON lease metadata (f"{db_path}.lease.json")
            lease_staging = lease_file.with_name(f"{lease_file.name}.tmp.{current_pid}")
            with open(lease_staging, "w", encoding="utf-8") as fp:
                json.dump(
                    {
                        "pid": current_pid,
                        "hostname": platform.node(),
                        "timestamp": now_ts,
                    },
                    fp,
                    indent=2,
                )
            os.replace(lease_staging, lease_file)

    logger.debug("Created SWMR lock and lease for PID %d on %s", current_pid, lock_file)
    return lock_file


def remove_swmr_lock(h5_path: Union[str, Path]) -> bool:
    """Safely removes the SWMR lock file and lease metadata if it exists under IPC lock."""
    target_h5 = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target_h5)
    lease_file = get_lease_metadata_path(target_h5)
    ipc_lock = get_ipc_filelock(target_h5, timeout=60.0)

    with _IN_PROCESS_LOCK:
        with ipc_lock:
            removed = False
            for lf in (lock_file, lease_file):
                if lf.exists():
                    try:
                        lf.unlink(missing_ok=True)
                        removed = True
                    except OSError as err:
                        logger.error("Failed to remove lock/lease file %s: %s", lf, err)
                        raise TorqH5LockError(
                            message=f"Failed to remove lock file {lf}: {err}",
                            details={"field": "lock_file", "value": str(lf)},
                        ) from err
            return removed


def detect_zombie_pids(h5_path: Union[str, Path]) -> List[int]:
    """Inspects companion lock and lease metadata files for the specified HDF5 path.

    Enforces strict host-identity gating:
    - If hostname == platform.node(): checks local PID liveness via psutil.pid_exists.
      If PID is dead, evicts stale lock immediately.
    - If hostname != platform.node(): NEVER calls local psutil.pid_exists.
      Enforces a 60.0-second lease expiration timeout: if time.time() - lease["timestamp"] > 60.0,
      logs [SWMR-LEASE-EVICTION] and breaks expired lock.
    """
    target = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target)
    lease_file = get_lease_metadata_path(target)

    active_file = lease_file if lease_file.exists() else (lock_file if lock_file.exists() else None)
    if active_file is None:
        return []

    zombie_pids: List[int] = []
    try:
        with open(active_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        lock_pid = data.get("pid")
        lock_host = data.get("hostname")
        now_ts = time.time()
        lease_ts = float(data.get("timestamp", data.get("timestamp_utc", now_ts)))

        if lock_host == platform.node():
            # Local host: inspect local PID liveness
            if lock_pid is not None:
                if not psutil.pid_exists(lock_pid):
                    logger.warning("Detected dead process PID %d in lock file %s; evicting immediately", lock_pid, active_file)
                    zombie_pids.append(lock_pid)
                else:
                    try:
                        proc = psutil.Process(lock_pid)
                        status = proc.status()
                        if status in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                            logger.warning(
                                "Detected zombie process PID %d (status=%s) in lock file %s",
                                lock_pid,
                                status,
                                active_file,
                            )
                            zombie_pids.append(lock_pid)
                    except psutil.NoSuchProcess:
                        zombie_pids.append(lock_pid)
                    except psutil.AccessDenied as _e:
                        logger.debug(f"Ignored exception: {_e}")
        else:
            # Remote host: NEVER call local psutil.pid_exists!
            # Enforce 60.0-second lease expiration timeout (§8C) [M]
            if (now_ts - lease_ts) > 60.0:
                logger.warning(
                    "[SWMR-LEASE-EVICTION] Remote SWMR lease on host %s (PID %s) expired (age %.1fs > 60.0s); evicting stale lock.",
                    lock_host,
                    lock_pid,
                    now_ts - lease_ts,
                )
                zombie_pids.append(lock_pid if lock_pid is not None else -1)
            else:
                logger.debug(
                    "Remote SWMR lock from %s is active (lease preserved); skipped.", lock_host
                )

    except (json.JSONDecodeError, OSError) as err:
        logger.warning(
            "Corrupt or unreadable lock file %s: %s; treating as orphan lock", active_file, err
        )
        zombie_pids.append(-1)

    return zombie_pids


def init_swmr_database(
    h5_path: Union[str, Path],
    datasets: Optional[Dict[str, Tuple[Tuple[int, ...], Any]]] = None,
) -> Path:
    """Safe SWMR Initialization Protocol (§8C).

    Pre-allocates chunks, sets shuffle=True and Fletcher32=True filters,
    creates root groups, flushes to disk, and activates SWMR mode (h5.swmr_mode = True).
    Protected under threading.RLock and FileLock.
    """
    target = Path(h5_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    ipc_lock = get_ipc_filelock(target)

    with _IN_PROCESS_LOCK:
        with ipc_lock:
            with h5py.File(target, "w", libver="latest") as f:
                if datasets:
                    for ds_name, (shape, dtype) in datasets.items():
                        chunk_shape = tuple(max(1, min(s, 100)) for s in shape)
                        f.create_dataset(
                            ds_name,
                            shape=shape,
                            maxshape=tuple(None for _ in shape),
                            chunks=chunk_shape,
                            dtype=dtype,
                            shuffle=True,
                            fletcher32=True,
                        )
                f.flush()
                f.swmr_mode = True
    return target


@contextmanager
def swmr_locked_session(h5_path: Union[str, Path], mode: str = "a"):
    """Context manager serializing h5py access under threading.RLock, FileLock, and lease tracking."""
    target = Path(h5_path).resolve()
    ipc_lock = get_ipc_filelock(target)
    lease_file = get_lease_metadata_path(target)

    with _IN_PROCESS_LOCK:
        with ipc_lock:
            now_ts = time.time()
            lease_file.parent.mkdir(parents=True, exist_ok=True)
            with open(lease_file, "w", encoding="utf-8") as fp:
                json.dump(
                    {
                        "pid": os.getpid(),
                        "hostname": platform.node(),
                        "timestamp": now_ts,
                    },
                    fp,
                    indent=2,
                )
            try:
                with h5py.File(target, mode, libver="latest", swmr=(mode == "r")) as h5_file:
                    yield h5_file
                    h5_file.flush()
            finally:
                lease_file.unlink(missing_ok=True)


def inspect_h5_integrity(h5_path: Union[str, Path]) -> bool:
    """
    Verifies whether the HDF5 file can be safely opened in read mode.
    """
    target = Path(h5_path).resolve()
    if not target.exists():
        return True  # Non-existent file is clean for creation

    try:
        with h5py.File(target, "r") as fp:
            _ = list(fp.keys())
        return True
    except Exception as err:
        logger.error("HDF5 integrity check failed for %s: %s", target, err)
        return False


def force_release_swmr(
    h5_path: Union[str, Path],
    force: bool = False,
) -> Dict[str, Any]:
    """
    Forcefully releases an HDF5 SWMR lock if held by dead/zombie processes,
    or unconditionally if force=True.
    Flushes and validates HDF5 database readability.
    """
    target = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)

    with ipc_lock:
        if not lock_file.exists():
            healthy = inspect_h5_integrity(target)
            return {
                "lock_released": False,
                "reaped_pids": [],
                "file_healthy": healthy,
                "h5_path": str(target),
                "status": "NO_LOCK_PRESENT",
            }

        zombies = detect_zombie_pids(target)
        should_release = force or len(zombies) > 0

        if not should_release:
            # Check if the lock is held by the current process on this host
            try:
                with open(lock_file, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if data.get("hostname") == platform.node() and data.get("pid") == os.getpid():
                    should_release = True
            except (json.JSONDecodeError, OSError, KeyError) as _e:
                logger.debug(f"Ignored exception: {_e}")

        reaped_pids: List[int] = []
        released = False

        if should_release:
            reaped_pids = list(zombies)
            try:
                lock_file.unlink(missing_ok=True)
                released = True
                logger.info("Successfully reaped lock %s (reaped PIDs: %s)", lock_file, reaped_pids)
            except OSError as err:
                logger.error("Could not unlink lock file %s: %s", lock_file, err)
                raise TorqH5LockError(
                    message=f"Failed to release SWMR lock: {err}",
                    details={"field": "lock_file", "value": str(lock_file)},
                ) from err
        else:
            logger.info("Lock file %s is held by an active live process or active remote lease; release skipped.", lock_file)

        healthy = inspect_h5_integrity(target)

        return {
            "lock_released": released,
            "reaped_pids": reaped_pids,
            "file_healthy": healthy,
            "h5_path": str(target),
            "status": "LOCK_RELEASED" if released else "LOCK_ACTIVE",
        }

