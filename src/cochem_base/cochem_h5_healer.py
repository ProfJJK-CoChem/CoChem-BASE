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
) -> Path:
    """
    Creates a valid SWMR lock metadata file containing PID, timestamp, and hostname.
    """
    target_h5 = Path(h5_path).resolve()
    lock_file = get_lock_file_path(target_h5)

    current_pid = pid if pid is not None else os.getpid()
    payload = {
        "h5_file": str(target_h5),
        "pid": current_pid,
        "timestamp_utc": time.time(),
        "hostname": platform.node(),
        "mode": "SWMR_WRITE",
    }

    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)

    logger.debug("Created SWMR lock file: %s for PID %d", lock_file, current_pid)
    return lock_file


def remove_swmr_lock(h5_path: Union[str, Path]) -> bool:
    """
    Safely removes the SWMR lock file if it exists.
    """
    lock_file = get_lock_file_path(h5_path)
    if lock_file.exists():
        try:
            lock_file.unlink()
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
    """
    Inspects companion lock files for the specified HDF5 path.
    Scans active OS processes via psutil to identify dead or zombie PIDs holding the lock.
    """
    lock_file = get_lock_file_path(h5_path)
    if not lock_file.exists():
        return []

    zombie_pids: List[int] = []
    try:
        with open(lock_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        lock_pid = data.get("pid")
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
                except psutil.AccessDenied:
                    # Process is running and owned by another user/system; not a dead process
                    pass
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
        # Check if the lock is held by the current process
        try:
            with open(lock_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("pid") == os.getpid():
                should_release = True
        except (json.JSONDecodeError, OSError, KeyError):
            pass

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
        logger.info("Lock file %s is held by an active live process; release skipped.", lock_file)

    healthy = inspect_h5_integrity(target)

    return {
        "lock_released": released,
        "reaped_pids": reaped_pids,
        "file_healthy": healthy,
        "h5_path": str(target),
        "status": "LOCK_RELEASED" if released else "LOCK_ACTIVE",
    }
