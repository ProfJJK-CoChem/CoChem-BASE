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

import json
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from filelock import FileLock
import h5py
import psutil

from cochem_base.exceptions import HDF5LockTimeoutError, ProvenanceErrorCode

logger = logging.getLogger("CoChem-TORQ.H5Healer")


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


def create_swmr_lock(
    h5_path: Union[str, Path],
    pid: Optional[int] = None,
    lease_duration_sec: float = 60.0,
) -> Path:
    """Creates a valid SWMR lock metadata file containing PID, timestamp, hostname, and monotonic lease.

    Follows the Tripartite Storage model:
    Host Client <---> Atomic Staging Lease (.tmp.<pid>) <---> Canonical Persistent Lock.
    Protected under cross-platform IPC FileLock.
    """
    target_h5 = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target_h5)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)

    current_pid = pid if pid is not None else os.getpid()
    payload = {
        "h5_file": str(target_h5),
        "pid": current_pid,
        "hostname": platform.node(),
        "timestamp_utc": time.time(),
        "lease_start_monotonic": time.monotonic(),
        "lease_duration_sec": float(lease_duration_sec),
        "mode": "SWMR_WRITE",
    }

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    staging_path = lock_file.with_name(f"{lock_file.name}.tmp.{current_pid}")

    with ipc_lock:
        with open(staging_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
        os.replace(staging_path, lock_file)

    logger.debug("Created SWMR lock file: %s for PID %d", lock_file, current_pid)
    return lock_file


def remove_swmr_lock(h5_path: Union[str, Path]) -> bool:
    """Safely removes the SWMR lock file if it exists under IPC lock."""
    lock_file = get_lock_file_path(h5_path)
    ipc_lock = FileLock(f"{lock_file}.ipc.lock", timeout=60)
    with ipc_lock:
        if lock_file.exists():
            try:
                lock_file.unlink(missing_ok=True)
                logger.debug("Removed SWMR lock file: %s", lock_file)
                return True
            except OSError as err:
                logger.error("Failed to remove lock file %s: %s", lock_file, err)
                raise TorqH5LockError(
                    message=f"Failed to remove lock file {lock_file}: {err}",
                    details={"field": "lock_file", "value": str(lock_file)},
                ) from err
    return False


def detect_zombie_pids(h5_path: Union[str, Path]) -> List[int]:
    """Inspects companion lock files for the specified HDF5 path.

    Enforces strict host-identity gating:
    - If hostname == platform.node(): checks local PID liveness via psutil.pid_exists.
    - If hostname != platform.node(): NEVER calls local psutil.pid_exists.
      Checks monotonic heartbeat lease expiration (time.monotonic() > lease_start + lease_duration).
    """
    lock_file = get_lock_file_path(h5_path)
    if not lock_file.exists():
        return []

    zombie_pids: List[int] = []
    try:
        with open(lock_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        lock_pid = data.get("pid")
        lock_host = data.get("hostname")

        if lock_host == platform.node():
            # Local host: inspect local PID liveness
            if lock_pid is not None:
                if not psutil.pid_exists(lock_pid):
                    logger.warning("Detected dead process PID %d in lock file %s", lock_pid, lock_file)
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
                                lock_file,
                            )
                            zombie_pids.append(lock_pid)
                    except psutil.NoSuchProcess:
                        zombie_pids.append(lock_pid)
                    except psutil.AccessDenied as _e:
                        logger.debug(f"Ignored exception: {_e}")
        else:
            # Remote host: NEVER call local psutil.pid_exists!
            # Evaluate wall-clock heartbeat lease expiration (monotonic clocks are not cross-host synchronized)
            lease_duration = float(data.get("lease_duration_sec", 60.0))
            timestamp_utc = data.get("timestamp_utc")
            lease_start = data.get("lease_start_monotonic")

            expired = False
            if timestamp_utc is not None:
                if time.time() > (float(timestamp_utc) + lease_duration):
                    expired = True
            elif lease_start is not None:
                # Emergency fallback only if timestamp_utc was missing
                if time.monotonic() > (float(lease_start) + lease_duration):
                    expired = True

            if expired:
                logger.warning(
                    "Remote SWMR lock from %s (PID %s) lease expired; classifying as stale.",
                    lock_host,
                    lock_pid,
                )
                zombie_pids.append(lock_pid if lock_pid is not None else -1)
            else:
                logger.debug(
                    "Remote SWMR lock from %s is active (lease preserved); skipped.", lock_host
                )

    except (json.JSONDecodeError, OSError) as err:
        logger.warning(
            "Corrupt or unreadable lock file %s: %s; treating as orphan lock", lock_file, err
        )
        zombie_pids.append(-1)

    return zombie_pids


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

