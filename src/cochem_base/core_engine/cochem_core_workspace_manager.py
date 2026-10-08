"""Artifact workspace provisioning through the canonical source/data boundary.

This compatibility entry point does not delete directories or infer job liveness.
POSIX modes restrict access; they are not a claim of Windows ACL enforcement.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from cochem.core.context import (
    AirGapViolationError,
    FileLock,
    assert_writable_path,
    get_current_context,
)
from cochem_base.config_loader import _writable_runtime_path

CORE_DIRECTORIES = ("Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases")
DEFAULT_ARTIFACT_ROOT = Path.home() / "CoChem_Artifacts"


def _artifact_root(path: str | Path | None) -> Path:
    requested = path or os.environ.get("COCHEM_ARTIFACTS") or os.environ.get("COCHEM_ARTIFACT_DIR") or DEFAULT_ARTIFACT_ROOT
    return _writable_runtime_path(Path(requested))


def _admit_children(root: Path) -> dict[str, Path]:
    if root.exists() and not root.is_dir():
        raise NotADirectoryError(root)
    paths = {name: root / name for name in CORE_DIRECTORIES}
    lock_path = root / ".workspace.lock"
    if lock_path.is_symlink():
        raise AirGapViolationError(f"Workspace lock cannot redirect through a symlink: {lock_path}")
    for path in paths.values():
        assert_writable_path(path)
        if path.is_symlink() or path.resolve().parent != root:
            raise AirGapViolationError(f"Workspace directory cannot redirect through a symlink: {path}")
        if path.exists() and not path.is_dir():
            raise NotADirectoryError(path)
    return paths


def provision_core_directories(artifact_root: str | Path | None = None) -> dict[str, Path]:
    """Idempotently provision admitted directories without an external lock.

    Directory creation changes no ledger or scientific file. This path is also
    safe for Stage 0 and scheduler/shared-filesystem provisioning, where external
    POSIX or Windows locks must not be introduced. Existing stricter permissions
    and all existing data are retained.
    """
    root = _artifact_root(artifact_root)
    paths = _admit_children(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    paths = _admit_children(root)
    if os.name == "posix":
        root.chmod(stat.S_IMODE(root.stat().st_mode) & 0o750)
    for path in paths.values():
        assert_writable_path(path)
        path.mkdir(mode=0o750, exist_ok=True)
        if path.is_symlink() or path.resolve().parent != root:
            raise AirGapViolationError(f"Workspace directory cannot redirect through a symlink: {path}")
        if os.name == "posix":
            path.chmod(stat.S_IMODE(path.stat().st_mode) & 0o750)
    return paths


def _external_lock_allowed(root: Path) -> bool:
    """Allow local locking only when the active tier and observed mount permit it."""
    try:
        tier = get_current_context().env_tier.upper()
    except RuntimeError:
        tier = ""
    if "TIER 5" in tier or "TIER 6" in tier:
        return False
    if any(os.environ.get(name) for name in ("SLURM_JOB_ID", "PBS_JOBID", "LSB_JOBID")):
        return False
    import psutil
    try:
        mounts = [entry for entry in psutil.disk_partitions(all=True)
                  if root.is_relative_to(Path(entry.mountpoint).resolve())]
    except (OSError, ValueError):
        return False
    if not mounts:
        return False
    fs_type = max(mounts, key=lambda entry: len(entry.mountpoint)).fstype.lower()
    return fs_type in {"ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "tmpfs", "ramfs",
                       "overlay", "overlayfs", "apfs", "hfs", "hfs+", "ntfs", "ntfs3", "refs"}


def scaffold_core_directories(artifact_root: str | Path | None = None) -> dict[str, Path]:
    """Provision directories with a ten-second local lock where permitted.

    Shared, scheduler-managed and unclassified mounts use the idempotent
    directory-only path. Scientific publication and ledger locking remain the
    responsibility of their existing local-scratch/atomic-publish services.
    """
    root = _artifact_root(artifact_root)
    _admit_children(root)
    if not _external_lock_allowed(root):
        return provision_core_directories(root)
    lock = FileLock(root / ".workspace.lock", timeout_sec=10.0)
    root.mkdir(parents=True, exist_ok=True, mode=0o750)
    with lock:
        return provision_core_directories(root)


@dataclass(frozen=True)
class WorkspaceManager:
    """Small, explicit workspace facade for callers of the historic module."""

    artifact_root: str | Path | None = None

    def scaffold(self) -> dict[str, Path]:
        return scaffold_core_directories(self.artifact_root)


__all__ = ["CORE_DIRECTORIES", "DEFAULT_ARTIFACT_ROOT", "WorkspaceManager",
           "provision_core_directories", "scaffold_core_directories"]
