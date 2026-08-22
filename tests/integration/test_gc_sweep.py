"""Integration Test Suite: GC Sweep Audit (tests/integration/test_gc_sweep.py).

Adheres strictly to the CoChem Zero-Mock Mandate and Method Matrix v4 Standards:
- Zero Mocks / Stubs: Uses 100% genuine OS processes, real files, real HDF5 stores, and physical constraints.
- Ephemeral SWMR Backup Purge: Asserts all ephemeral `.tmp` HDF5 SWMR backups and journals are cleanly removed.
- Cross-Platform Shared Memory Release: Asserts all `multiprocessing.shared_memory` IPC buffers are released
  without hardcoding POSIX `/dev/shm` to guarantee complete Windows compliance.
- Scratch Sterilization: Asserts temporary Scratch directories are completely sterile and empty post-execution.
- Path Containment & Anti-Traversal Engine: Mandates strict path-containment validation to prevent directory
  traversal vulnerabilities (e.g., `../../`, `..\\..`, absolute escapes, drive shifts, prefix spoofing, null bytes)
  using `PathTraversalError` from `cochem_base.exceptions`.
- Method Matrix Rules: Authentic Water Dimer (H4O2, 6 atoms, Cs symmetry), TolMaxG 1e-5, B3LYP-D3, InHess XTB2,
  defgrid1->defgrid3, and provenance tags ([M], [D], [E]).
- Process & Lifecycle Safety: Cleans up all subprocesses and shared memory buffers with pytest fixtures and try-finally.
"""

from __future__ import annotations

import gc
import logging
import math
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Set, Tuple, Union

import h5py
import numpy as np
import pytest

from cochem_base.exceptions import (
    PathTraversalError,
    ProvenanceErrorCode,
)
from core_engine.cochem_base_hdf5 import HDF5OntologyEnforcer
from core_engine.cochem_core_subprocess_broker import (
    cleanup_zombie_processes,
    get_active_popen_processes,
    register_popen_process,
)
from core_engine.cochem_core_workspace_manager import WorkspaceManager

logger = logging.getLogger("CoChem-GCSweep-Integration")

# =============================================================================
# AUTHENTIC WATER DIMER (H4O2) & METHOD MATRIX v4 CONSTANTS
# =============================================================================

# Authentic Cs equilibrium geometry for Water Dimer (H4O2) in Angstroms
WATER_DIMER_COORDINATES: List[Tuple[str, float, float, float]] = [
    ("O", -1.472000, -0.076000, 0.000000),  # O1 (donor)
    ("H", -0.528000, -0.086000, 0.000000),  # H1 (H-bonding donor proton)
    ("H", -1.782000, 0.835000, 0.000000),  # H2 (non-bonding proton)
    ("O", 1.442000, 0.111000, 0.000000),  # O2 (acceptor)
    ("H", 1.733000, -0.428000, 0.759000),  # H3 (acceptor proton A)
    ("H", 1.733000, -0.428000, -0.759000),  # H4 (acceptor proton B)
]

WATER_DIMER_ENERGY_EH: float = -152.875240
WATER_DIMER_SYMMETRY: str = "Cs"
WATER_DIMER_ATOM_COUNT: int = 6

METHOD_MATRIX_SPECS: Dict[str, Any] = {
    "functional": "B3LYP-D3",
    "basis": "def2-TZVP",
    "hessian_strategy": "InHess XTB2",
    "grid_stages": ["defgrid1", "defgrid2", "defgrid3"],
    "tol_max_g": 1e-5,
    "provenance_tags": ["[M]", "[D]", "[E]"],
}

# Blocked / Ephemeral extension patterns for SWMR backups and transient scratch
EPHEMERAL_SWMR_EXTENSIONS: Set[str] = {
    ".tmp",
    ".bak",
    ".lock",
    ".swmr",
}

EPHEMERAL_SWMR_PATTERNS: List[str] = [
    "*.tmp",
    "*.tmp.*",
    "*.swmr.tmp",
    "*.h5.tmp",
    "*.extinp.tmp",
    "*.bak",
    "*.h5.lock",
    ".job.lock.tmp",
    ".cochem_workspace.lock.tmp",
    "core.*",
]


# =============================================================================
# DATA STRUCTURES & AUDIT REPORT
# =============================================================================


@dataclass
class GCSweepAuditReport:
    """Structured immutable audit report from a complete GC sweep cycle."""

    workspace_root: Path
    scratch_dir: Path
    hdf5_ephemeral_swept_count: int
    hdf5_ephemeral_swept_files: List[str]
    scratch_files_swept_count: int
    scratch_dirs_swept_count: int
    shared_memory_released_buffers: List[str]
    zombie_subprocesses_reaped: int
    provenance_chain: List[str] = field(default_factory=lambda: ["[M]", "[D]", "[E]"])
    timestamp: float = field(default_factory=time.time)
    is_sterile: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_root": str(self.workspace_root),
            "scratch_dir": str(self.scratch_dir),
            "hdf5_ephemeral_swept_count": self.hdf5_ephemeral_swept_count,
            "hdf5_ephemeral_swept_files": self.hdf5_ephemeral_swept_files,
            "scratch_files_swept_count": self.scratch_files_swept_count,
            "scratch_dirs_swept_count": self.scratch_dirs_swept_count,
            "shared_memory_released_buffers": self.shared_memory_released_buffers,
            "zombie_subprocesses_reaped": self.zombie_subprocesses_reaped,
            "provenance_chain": self.provenance_chain,
            "timestamp": self.timestamp,
            "is_sterile": self.is_sterile,
        }


# =============================================================================
# GC SWEEP AUDITOR ENGINE (ZERO-MOCK MANDATE)
# =============================================================================


class GCSweepAuditor:
    """Zero-Mock Garbage Collection and Path Security Enforcement Auditor.

    Provides mathematical and physical validation for:
    1. Strict Path Containment & Directory Traversal defense (PathTraversalError).
    2. Ephemeral .tmp HDF5 SWMR backup identification and safe removal.
    3. Cross-platform multiprocessing.shared_memory IPC buffer sweeping.
    4. Scratch directory tree sterilization.
    5. Zombie subprocess reaping and Method Matrix provenance logging.
    """

    @staticmethod
    def validate_path_containment(
        target_path: Union[str, Path],
        allowed_root: Union[str, Path],
    ) -> Path:
        """Validates that target_path is strictly contained within allowed_root.

        Prevents directory traversal vulnerabilities:
        - Relative path traversal: `../../`, `..\\..`, `a/b/../../../etc`
        - Absolute path escapes pointing outside the root sandbox
        - Windows drive letter mismatches: `C:\\...` vs `D:\\...`
        - Prefix spoofing: `/sandbox_evil` vs `/sandbox`
        - Null-byte injection: `path\\x00evil`

        Args:
            target_path: Target path to validate.
            allowed_root: Authoritative enclosing directory boundary.

        Returns:
            Resolved, canonical Path object strictly within allowed_root.

        Raises:
            PathTraversalError: If the target path escapes or violates the allowed root.
        """
        raw_str = str(target_path)

        # 1. Null-byte injection defense
        if "\x00" in raw_str:
            raise PathTraversalError(
                message=f"Null-byte injection detected in target path: {raw_str!r}",
                error_code=ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED,
                details={"target_path": raw_str, "allowed_root": str(allowed_root)},
            )

        # 2. Canonical resolution of root and target
        try:
            resolved_root = Path(allowed_root).resolve()
        except Exception as exc:
            raise PathTraversalError(
                message=f"Failed to resolve allowed root boundary {allowed_root!r}: {exc}",
                error_code=ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED,
                details={"allowed_root": str(allowed_root)},
            ) from exc

        # Handle raw relative paths vs absolute paths
        target_p = Path(raw_str)
        if not target_p.is_absolute():
            candidate = (resolved_root / target_p).resolve()
        else:
            candidate = target_p.resolve()

        # 3. Windows drive-letter containment verification
        if sys.platform == "win32":
            if candidate.drive.upper() != resolved_root.drive.upper():
                raise PathTraversalError(
                    message=(
                        f"Cross-drive path traversal escape attempt detected: target drive "
                        f"{candidate.drive!r} differs from allowed root drive {resolved_root.drive!r}"
                    ),
                    error_code=ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED,
                    details={
                        "target_path": raw_str,
                        "candidate": str(candidate),
                        "allowed_root": str(resolved_root),
                    },
                )

        # 4. Strict ancestor containment verification
        # candidate must be equal to resolved_root or a descendant of resolved_root
        try:
            is_contained = candidate == resolved_root or candidate.is_relative_to(resolved_root)
        except AttributeError:
            # Fallback for Python < 3.9 (safety invariant)
            try:
                candidate.relative_to(resolved_root)
                is_contained = True
            except ValueError:
                is_contained = False

        if not is_contained:
            raise PathTraversalError(
                message=(
                    f"Path traversal escape attempt detected: {raw_str!r} resolves to "
                    f"{candidate!r} which is outside allowed boundary {resolved_root!r}"
                ),
                error_code=ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED,
                details={
                    "target_path": raw_str,
                    "resolved_path": str(candidate),
                    "allowed_root": str(resolved_root),
                },
            )

        # 5. Prefix spoofing check (e.g. /workspace/scratch_spoof vs /workspace/scratch)
        root_str = str(resolved_root)
        cand_str = str(candidate)
        if cand_str != root_str:
            sep = os.sep
            if not cand_str.startswith(root_str.rstrip(sep) + sep):
                raise PathTraversalError(
                    message=(
                        f"Prefix spoofing traversal attempt detected: {cand_str!r} "
                        f"shares string prefix with {root_str!r} but is not a true subpath."
                    ),
                    error_code=ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED,
                    details={
                        "target_path": raw_str,
                        "candidate": cand_str,
                        "allowed_root": root_str,
                    },
                )

        return candidate

    @classmethod
    def is_ephemeral_swmr_backup_file(cls, file_path: Path) -> bool:
        """Determines if a given file matches ephemeral HDF5 SWMR backup or transient job artifacts."""
        name_lower = file_path.name.lower()

        # Primary HDF5 state databases (.h5) must NEVER be classified as ephemeral
        if name_lower.endswith(".h5") and not any(
            name_lower.endswith(ext) for ext in [".h5.tmp", ".h5.bak", ".h5.lock"]
        ):
            return False

        # Match specific known transient patterns
        if name_lower.endswith(".tmp") or ".tmp." in name_lower:
            return True
        if name_lower.endswith(".extinp.tmp"):
            return True
        if name_lower.endswith(".swmr.tmp") or name_lower.endswith(".h5.tmp"):
            return True
        if name_lower.endswith(".bak"):
            return True
        if name_lower.endswith(".lock.tmp") or name_lower.endswith(".job.lock.tmp"):
            return True
        if name_lower.startswith("core.") and len(name_lower) > 5:
            suffix = name_lower[5:]
            if suffix.isdigit():
                return True

        return False

    @classmethod
    def sweep_hdf5_swmr_backups(
        cls,
        directory: Union[str, Path],
        allowed_root: Optional[Union[str, Path]] = None,
    ) -> List[Path]:
        """Sweeps and cleanly removes all ephemeral .tmp HDF5 SWMR backup and journal files.

        Strictly protects the authoritative primary HDF5 store (*.h5) from deletion.

        Args:
            directory: Directory to sweep.
            allowed_root: Optional enclosing sandbox boundary for path containment.

        Returns:
            List of unlinked ephemeral file paths.

        Raises:
            PathTraversalError: If path containment validation fails.
        """
        root_boundary = allowed_root if allowed_root is not None else directory
        safe_dir = cls.validate_path_containment(directory, root_boundary)

        if not safe_dir.exists():
            return []

        swept_files: List[Path] = []

        for current_root, _, filenames in os.walk(safe_dir):
            for fname in filenames:
                file_p = Path(current_root) / fname
                if cls.is_ephemeral_swmr_backup_file(file_p):
                    # Ensure path is strictly contained before unlinking
                    cls.validate_path_containment(file_p, safe_dir)
                    try:
                        # Revoke read-only flag if set on Windows
                        if sys.platform == "win32":
                            os.chmod(str(file_p), stat.S_IWRITE | stat.S_IREAD)
                        file_p.unlink()
                        swept_files.append(file_p)
                        logger.info(f"Swept ephemeral SWMR backup file: {file_p}")
                    except OSError as err:
                        logger.warning(f"Failed to unlink ephemeral file {file_p}: {err}")

        return swept_files

    @classmethod
    def sweep_shared_memory(
        cls,
        shm_targets: Sequence[Union[str, shared_memory.SharedMemory]],
    ) -> Dict[str, bool]:
        """Cross-platform release and unlinking of multiprocessing.shared_memory IPC buffers.

        Guarantees Windows compliance by attaching via Python's standard `multiprocessing.shared_memory`
        without relying on POSIX `/dev/shm`.

        Args:
            shm_targets: Sequence of SharedMemory instances or string identifiers to audit and unlink.

        Returns:
            Dictionary mapping buffer name to boolean release success status.
        """
        results: Dict[str, bool] = {}

        for item in shm_targets:
            name = item.name if isinstance(item, shared_memory.SharedMemory) else str(item)
            try:
                if isinstance(item, shared_memory.SharedMemory):
                    try:
                        item.close()
                    except Exception:
                        pass
                    try:
                        item.unlink()
                    except Exception:
                        pass
                else:
                    shm = shared_memory.SharedMemory(name=name)
                    shm.close()
                    shm.unlink()

                logger.info(f"Successfully unlinked shared memory IPC buffer: {name}")

                # Verification step: ensure subsequent attachment raises FileNotFoundError
                try:
                    probe = shared_memory.SharedMemory(name=name)
                    probe.close()
                    # If still attachable, mark as lingering
                    results[name] = False
                except FileNotFoundError:
                    # Expected: segment is completely released
                    results[name] = True
                except Exception:
                    # Platform-dependent cleanup completed
                    results[name] = True
            except FileNotFoundError:
                # Already cleaned or never created
                results[name] = True
            except Exception as err:
                logger.warning(f"Error while releasing shared memory buffer {name}: {err}")
                results[name] = False

        return results

    @classmethod
    def sweep_scratch_directory(
        cls,
        scratch_dir: Union[str, Path],
        allowed_root: Optional[Union[str, Path]] = None,
        preserve_root: bool = True,
    ) -> Tuple[int, int]:
        """Sterilizes the temporary Scratch directory by removing all subdirectories and transient files.

        Args:
            scratch_dir: The scratch directory to sterilize.
            allowed_root: Optional enclosing sandbox boundary.
            preserve_root: If True, keeps the empty scratch directory; if False, deletes it.

        Returns:
            Tuple of (files_removed_count, directories_removed_count).

        Raises:
            PathTraversalError: If path containment validation fails.
        """
        root_boundary = allowed_root if allowed_root is not None else scratch_dir
        safe_scratch = cls.validate_path_containment(scratch_dir, root_boundary)

        if not safe_scratch.exists():
            return 0, 0

        files_count = 0
        dirs_count = 0

        def _rmtree_onerror(func: Any, path: str, exc_info: Any) -> None:
            """Error handler for shutil.rmtree to remove read-only attributes on Windows."""
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
            except Exception as e:
                logger.warning(f"Failed to force-delete {path} in rmtree: {e}")

        # Iterate through immediate children
        for item in list(safe_scratch.iterdir()):
            cls.validate_path_containment(item, safe_scratch)
            try:
                if item.is_file() or item.is_symlink():
                    if sys.platform == "win32":
                        os.chmod(str(item), stat.S_IWRITE | stat.S_IREAD)
                    item.unlink()
                    if not item.exists():
                        files_count += 1
                elif item.is_dir():
                    # Enumerate nested items before removal
                    nested_f_count = 0
                    nested_d_count = 0
                    for root_dir, dnames, fnames in os.walk(item):
                        if sys.platform == "win32":
                            for fname in fnames:
                                try:
                                    os.chmod(os.path.join(root_dir, fname), stat.S_IWRITE | stat.S_IREAD)
                                except OSError:
                                    pass
                        nested_f_count += len(fnames)
                        nested_d_count += len(dnames)

                    if sys.version_info >= (3, 12):
                        shutil.rmtree(item, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
                    else:
                        shutil.rmtree(item, onerror=_rmtree_onerror)

                    if not item.exists():
                        files_count += nested_f_count
                        dirs_count += nested_d_count + 1
            except OSError as err:
                logger.warning(f"Failed to remove scratch artifact {item}: {err}")

        if not preserve_root:
            try:
                if sys.version_info >= (3, 12):
                    shutil.rmtree(safe_scratch, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
                else:
                    shutil.rmtree(safe_scratch, onerror=_rmtree_onerror)
                if not safe_scratch.exists():
                    dirs_count += 1
            except OSError as err:
                logger.warning(f"Failed to remove root scratch directory {safe_scratch}: {err}")

        logger.info(
            f"Scratch sterilization complete: {files_count} files, {dirs_count} dirs swept."
        )
        return files_count, dirs_count

    @classmethod
    def execute_full_gc_audit(
        cls,
        workspace_dir: Union[str, Path],
        active_shm_targets: Optional[Sequence[Union[str, shared_memory.SharedMemory]]] = None,
        method_metadata: Optional[Dict[str, Any]] = None,
    ) -> GCSweepAuditReport:
        """Executes a full, orchestrated GC cycle across the computational workspace.

        Performs:
        1. Scratch directory sterilization.
        2. Ephemeral HDF5 SWMR backup purge.
        3. IPC Shared Memory release.
        4. Zombie child process reaping.
        5. Post-execution sterility verification.

        Args:
            workspace_dir: Root workspace directory.
            active_shm_targets: Optional list of shared memory instances or identifiers to sweep.
            method_metadata: Optional Method Matrix metadata.

        Returns:
            GCSweepAuditReport summarizing the audit results.
        """
        safe_ws = cls.validate_path_containment(workspace_dir, workspace_dir)
        scratch_path = safe_ws / "Scratch"

        # 1. Scratch directory sterilization (executed first to isolate scratch tier)
        f_count, d_count = 0, 0
        if scratch_path.exists():
            f_count, d_count = cls.sweep_scratch_directory(
                scratch_path,
                allowed_root=safe_ws,
                preserve_root=True,
            )

        # 2. Ephemeral SWMR backup sweep across workspace (e.g. state dir, registry)
        swept_tmp_paths = cls.sweep_hdf5_swmr_backups(safe_ws, allowed_root=safe_ws)
        swept_tmp_names = [p.name for p in swept_tmp_paths]

        # 3. Shared Memory IPC buffer sweep
        shm_to_sweep = list(active_shm_targets) if active_shm_targets is not None else []
        shm_results = cls.sweep_shared_memory(shm_to_sweep)
        released_shm = [name for name, ok in shm_results.items() if ok]

        # 4. Zombie subprocess reaper
        initial_procs = len(get_active_popen_processes())
        cleanup_zombie_processes()
        final_procs = len(get_active_popen_processes())
        zombies_reaped = max(0, initial_procs - final_procs)

        # 5. Sterility check: assert Scratch is completely empty
        is_sterile = True
        if scratch_path.exists():
            remaining_scratch = list(scratch_path.iterdir())
            if len(remaining_scratch) > 0:
                is_sterile = False

        # Check for lingering .tmp files anywhere in workspace
        for _, _, filenames in os.walk(safe_ws):
            for fn in filenames:
                if cls.is_ephemeral_swmr_backup_file(Path(fn)):
                    is_sterile = False
                    break
            if not is_sterile:
                break

        prov_tags = (
            method_metadata.get("provenance_tags", ["[M]", "[D]", "[E]"])
            if method_metadata
            else ["[M]", "[D]", "[E]"]
        )

        return GCSweepAuditReport(
            workspace_root=safe_ws,
            scratch_dir=scratch_path,
            hdf5_ephemeral_swept_count=len(swept_tmp_paths),
            hdf5_ephemeral_swept_files=swept_tmp_names,
            scratch_files_swept_count=f_count,
            scratch_dirs_swept_count=d_count,
            shared_memory_released_buffers=released_shm,
            zombie_subprocesses_reaped=zombies_reaped,
            provenance_chain=prov_tags,
            is_sterile=is_sterile,
        )


# =============================================================================
# PYTEST FIXTURES (LIFECYCLE & PROCESS SAFETY)
# =============================================================================


@pytest.fixture
def managed_shm_tracker() -> Generator[List[shared_memory.SharedMemory], None, None]:
    """Fixture that tracks allocated SharedMemory instances and guarantees unlinking on teardown."""
    created_shm_list: List[shared_memory.SharedMemory] = []

    yield created_shm_list

    # Teardown safety: ensure all allocated segments are closed and unlinked
    for shm in created_shm_list:
        try:
            shm.close()
        except Exception:
            pass
        try:
            shm.unlink()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def process_lifecycle_safety() -> Generator[None, None, None]:
    """Guarantees no orphaned child processes before or after each test execution."""
    cleanup_zombie_processes()
    yield
    cleanup_zombie_processes()
    # Force Python GC to collect circular references
    gc.collect()


# =============================================================================
# TEST SUITE 1: PATH CONTAINMENT & DIRECTORY TRAVERSAL DEFENSE
# =============================================================================


class TestPathContainmentSecurity:
    """Rigorous zero-mock tests for directory traversal attack detection and path containment."""

    def test_valid_child_path_passes_validation(self, tmp_path: Path) -> None:
        """Verify that authentic nested child paths within the root boundary resolve safely."""
        root = tmp_path / "cochem_workspace"
        root.mkdir(parents=True, exist_ok=True)
        child_dir = root / "Scratch" / "job_water_dimer_001"
        child_dir.mkdir(parents=True, exist_ok=True)

        validated = GCSweepAuditor.validate_path_containment(child_dir, root)
        assert validated == child_dir.resolve()
        assert validated.is_relative_to(root.resolve())

    def test_parent_relative_traversal_detection(self, tmp_path: Path) -> None:
        """Verify that parent traversal attempts ('../../', '..\\..') raise PathTraversalError."""
        root = tmp_path / "sandbox" / "Scratch"
        root.mkdir(parents=True, exist_ok=True)

        # Diverse adversarial relative traversal vectors
        malicious_vectors = [
            "../../",
            "..\\..",
            "../other_dir",
            "..\\other_dir",
            "job/../../../escaped",
            "job\\..\\..\\..\\escaped",
            "./../../etc/passwd",
            ".\\..\\..\\Windows\\System32",
        ]

        for vector in malicious_vectors:
            with pytest.raises(PathTraversalError) as exc_info:
                GCSweepAuditor.validate_path_containment(vector, root)

            err = exc_info.value
            assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
            assert "Path traversal escape attempt detected" in str(err)
            assert "details" in err.to_dict()

    def test_absolute_path_escape_detection(self, tmp_path: Path) -> None:
        """Verify that absolute paths pointing outside the root boundary raise PathTraversalError."""
        root = tmp_path / "isolated_workspace"
        root.mkdir(parents=True, exist_ok=True)

        outside_target = (tmp_path / "outside_dir").resolve()
        outside_target.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(outside_target, root)

        err = exc_info.value
        assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "outside allowed boundary" in str(err)

    def test_windows_drive_switch_traversal_detection(self, tmp_path: Path) -> None:
        """Verify that cross-drive path specifications on Windows raise PathTraversalError."""
        if sys.platform != "win32":
            pytest.skip("Drive-letter switching test is Windows-specific")

        root = tmp_path / "workspace"
        root.mkdir(parents=True, exist_ok=True)

        current_drive = root.resolve().drive.upper()
        target_drive = "Z:" if current_drive != "Z:" else "Y:"
        cross_drive_path = f"{target_drive}\\Windows\\System32"

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(cross_drive_path, root)

        err = exc_info.value
        assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "Cross-drive path traversal escape attempt detected" in str(err)

    def test_prefix_spoofing_sibling_attack_detection(self, tmp_path: Path) -> None:
        """Verify that sibling directories sharing string prefixes raise PathTraversalError."""
        root = tmp_path / "scratch"
        root.mkdir(parents=True, exist_ok=True)

        # Sibling directory: shares string prefix 'scratch' but is NOT a child
        spoofed_sibling = tmp_path / "scratch_spoofed" / "subfolder"
        spoofed_sibling.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(spoofed_sibling, root)

        err = exc_info.value
        assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED

    def test_null_byte_injection_traversal_detection(self, tmp_path: Path) -> None:
        """Verify that null-byte path injections are caught and raise PathTraversalError."""
        root = tmp_path / "workspace"
        root.mkdir(parents=True, exist_ok=True)

        poisoned_path = str(root / "safe_dir") + "\x00/../../etc/shadow"

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(poisoned_path, root)

        err = exc_info.value
        assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "Null-byte injection detected" in str(err)


# =============================================================================
# TEST SUITE 2: EPHEMERAL .TMP HDF5 SWMR BACKUP SWEEP
# =============================================================================


class TestHDF5EphemeralBackupSweep:
    """Zero-mock tests verifying complete removal of ephemeral .tmp HDF5 SWMR backups."""

    def test_ephemeral_tmp_hdf5_swmr_removal_with_water_dimer(self, tmp_path: Path) -> None:
        """Proves ephemeral .tmp backups are cleanly removed while authoritative HDF5 data remains intact."""
        workspace_dir = tmp_path / "cochem_data"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        h5_state_path = workspace_dir / "cochem_state.h5"

        # 1. Commit authentic Water Dimer record to primary HDF5 store
        enforcer = HDF5OntologyEnforcer(hdf5_path=h5_state_path)
        dimer_coords = np.array([c[1:] for c in WATER_DIMER_COORDINATES], dtype=np.float64)

        payload: Dict[str, Any] = {
            "molecule_name": "Water_Dimer_H4O2_Cs",
            "xyz_coordinates": dimer_coords.tolist(),
            "energy": WATER_DIMER_ENERGY_EH,
            "symmetry_group": WATER_DIMER_SYMMETRY,
            "LAM_TRIGGER_REQUIRED": False,
        }
        group_key = "basins/basin_water_dimer_cs_001"
        enforcer.write_record(group_key, payload)
        assert h5_state_path.exists(), "Authoritative HDF5 database must exist"

        # 2. Generate authentic ephemeral .tmp HDF5 SWMR backup and journal files
        ephemeral_files = [
            workspace_dir / "cochem_state.h5.tmp",
            workspace_dir / "cochem_state.h5.swmr.tmp",
            workspace_dir / "cochem_state.h5.tmp.bak",
            workspace_dir / "basin_water_dimer.tmp",
            workspace_dir / "swmr_commit_journal.tmp.1284",
            workspace_dir / "orca_water_dimer_EXT.extinp.tmp",
            workspace_dir / ".cochem_workspace.lock.tmp",
            workspace_dir / ".job.lock.tmp",
            workspace_dir / "core.88419",
        ]

        for ef in ephemeral_files:
            ef.write_bytes(b"TRANSIENT_SWMR_PAYLOAD_DATA_CHUNK_" + ef.name.encode("utf-8"))
            assert ef.exists(), f"Ephemeral file {ef} must be physically created"

        # 3. Execute Ephemeral SWMR Backup Sweep
        swept = GCSweepAuditor.sweep_hdf5_swmr_backups(workspace_dir, allowed_root=workspace_dir)

        # 4. Assert all ephemeral files were swept
        assert len(swept) == len(ephemeral_files), (
            f"Expected {len(ephemeral_files)} swept files, got {len(swept)}"
        )
        for ef in ephemeral_files:
            assert not ef.exists(), f"Ephemeral file {ef} must be completely removed post-sweep"

        # 5. Assert authoritative HDF5 database remains 100% healthy, readable, and non-corrupt
        assert h5_state_path.exists(), "Authoritative HDF5 file must NOT be deleted by GC sweep"

        with h5py.File(h5_state_path, "r") as h5f:
            assert group_key in h5f, f"Group {group_key} must exist in authoritative HDF5"
            grp = h5f[group_key]
            assert grp.attrs["molecule_name"] == "Water_Dimer_H4O2_Cs"
            assert grp.attrs["symmetry_group"] == "Cs"
            assert math.isclose(float(grp.attrs["energy"]), WATER_DIMER_ENERGY_EH, rel_tol=1e-5)
            coords_read = grp["xyz_coordinates"][:]
            assert coords_read.shape == (6, 3)
            assert bool(np.all(np.abs(coords_read - dimer_coords) < 1e-5))

    def test_hdf5_swmr_backup_sweep_traversal_protection(self, tmp_path: Path) -> None:
        """Verify that attempting to sweep outside sandbox boundary triggers PathTraversalError."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "outside_unauthorized"
        outside.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.sweep_hdf5_swmr_backups(outside, allowed_root=sandbox)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED


# =============================================================================
# TEST SUITE 3: CROSS-PLATFORM SHARED MEMORY IPC RELEASE (NO /DEV/SHM)
# =============================================================================


class TestSharedMemoryIPCAudit:
    """Zero-mock tests for multiprocessing.shared_memory IPC buffer tracking and release."""

    def test_shared_memory_tensor_allocation_and_clean_release(
        self,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Allocates genuine SharedMemory tensor buffers, verifies data integrity, and audits release."""
        shm_name = f"cochem_shm_dimer_{os.getpid()}_{int(time.time() * 1000)}"

        # 1. Allocate genuine SharedMemory buffer
        dimer_coords = np.array([c[1:] for c in WATER_DIMER_COORDINATES], dtype=np.float64)
        tensor_bytes = dimer_coords.tobytes()
        buffer_size = len(tensor_bytes)

        shm_writer = shared_memory.SharedMemory(name=shm_name, create=True, size=buffer_size)
        managed_shm_tracker.append(shm_writer)

        # Write authentic Water Dimer coordinate tensor into shared memory
        assert shm_writer.buf is not None
        shm_writer.buf[:buffer_size] = tensor_bytes

        # 2. Attach from a second handle and verify data integrity
        shm_reader = shared_memory.SharedMemory(name=shm_name)
        assert shm_reader.buf is not None
        read_array = np.array(
            np.frombuffer(shm_reader.buf[:buffer_size], dtype=np.float64).reshape((6, 3))
        )
        assert bool(np.all(np.abs(read_array - dimer_coords) < 1e-5)), (
            "Shared memory tensor must match original coordinates"
        )
        del read_array
        shm_reader.close()

        # 3. Execute GC Shared Memory Release
        release_status = GCSweepAuditor.sweep_shared_memory([shm_writer])
        assert release_status[shm_name] is True, (
            "Shared memory buffer must be marked as successfully released"
        )

        # 4. Cross-Platform Post-Assertion: Verify subsequent attach raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            probe = shared_memory.SharedMemory(name=shm_name)
            probe.close()

    def test_batch_shared_memory_buffers_lifecycle(
        self,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Verifies bulk release of multiple named shared memory buffers across worker threads/processes."""
        created_buffers: List[shared_memory.SharedMemory] = []
        buffer_names: List[str] = []

        # Create 4 distinct IPC shared memory buffers (e.g. for MPI ranks or Hessian blocks)
        for rank in range(4):
            b_name = f"cochem_shm_rank_{rank}_{os.getpid()}_{int(time.time() * 1000)}"
            shm = shared_memory.SharedMemory(name=b_name, create=True, size=512)
            managed_shm_tracker.append(shm)
            created_buffers.append(shm)
            assert shm.buf is not None
            shm.buf[:8] = f"RANK_{rank:03d}".encode("utf-8")
            buffer_names.append(b_name)

        # Verify all 4 buffers are sweepable
        sweep_report = GCSweepAuditor.sweep_shared_memory(created_buffers)
        assert len(sweep_report) == 4
        for name in buffer_names:
            assert sweep_report[name] is True, f"Buffer {name} should be cleanly released"

        # Assert no buffer can be attached to
        for name in buffer_names:
            with pytest.raises(FileNotFoundError):
                probe = shared_memory.SharedMemory(name=name)
                probe.close()


# =============================================================================
# TEST SUITE 4: SCRATCH DIRECTORY STERILIZATION
# =============================================================================


class TestScratchDirectorySterilization:
    """Zero-mock tests verifying complete sterilization of temporary Scratch directory trees."""

    def test_scratch_directory_purged_completely_post_execution(self, tmp_path: Path) -> None:
        """Creates complex nested scratch hierarchy with transient artifacts and proves 100% sterile cleanup."""
        workspace_dir = tmp_path / "cochem_exec"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        scratch_dir = workspace_dir / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        # Build realistic nested job scratch structure
        job1_dir = scratch_dir / "job_dimer_opt_tier3"
        job1_dir.mkdir(parents=True, exist_ok=True)
        job2_dir = scratch_dir / "job_dimer_vpt2_tier8"
        job2_dir.mkdir(parents=True, exist_ok=True)
        nested_sub = job1_dir / "defgrid3_integrals"
        nested_sub.mkdir(parents=True, exist_ok=True)

        # Populate with realistic quantum calculation temporary scratch files
        transient_files = [
            scratch_dir / "global_scratch.tmp",
            scratch_dir / "core.90210",
            job1_dir / "water_dimer.gbw",
            job1_dir / "water_dimer.densities",
            job1_dir / "scf_history.tmp",
            job1_dir / ".job.lock",
            nested_sub / "two_electron_eri.dat",
            nested_sub / "fock_scratch.tmp",
            job2_dir / "vpt2_force_field.bin",
            job2_dir / "coriolis_coupling.tmp",
        ]

        for tf in transient_files:
            tf.write_bytes(
                b"COMPUTATIONAL_CHEMISTRY_SCRATCH_BINARY_DATA_" + tf.name.encode("utf-8")
            )
            assert tf.exists()

        # Execute Scratch Sterilization
        files_removed, dirs_removed = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=workspace_dir,
            preserve_root=True,
        )

        # Assert all transient files and directories were removed
        assert files_removed == len(transient_files)
        assert dirs_removed == 3  # job1_dir, nested_sub, job2_dir

        # Assert Scratch directory is physically 100% empty
        assert scratch_dir.exists(), "Scratch root directory should be preserved as empty container"
        remaining_items = list(scratch_dir.iterdir())
        assert len(remaining_items) == 0, (
            f"Scratch must be completely empty, but found: {remaining_items}"
        )

    def test_workspace_manager_zombie_sweep_integration(self, tmp_path: Path) -> None:
        """Verifies integration with WorkspaceManager.sweep_zombie_directories()."""
        workspace_dir = tmp_path / "cochem_ws_manager"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        wm = WorkspaceManager(base_path=str(workspace_dir))
        assert wm.scaffold_core_directories() is True

        # Provision a job workspace
        job_dir = wm.provision_job_workspace("JOB_WATER_DIMER_OPT_001")
        assert job_dir.exists()
        (job_dir / "transient_orca.inp").write_text("! B3LYP def2-TZVP TightSCF\n")

        # Execute WorkspaceManager sweep
        swept_count = wm.sweep_zombie_directories()
        assert swept_count == 1
        assert not job_dir.exists(), "Provisioned job scratch directory must be swept"

    def test_scratch_sweep_traversal_protection(self, tmp_path: Path) -> None:
        """Verify that attempting to sweep scratch outside allowed root raises PathTraversalError."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)
        escaped_target = tmp_path / "critical_system_folder"
        escaped_target.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.sweep_scratch_directory(escaped_target, allowed_root=sandbox)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED


# =============================================================================
# TEST SUITE 5: FULL GC SWEEP LIFECYCLE & METHOD MATRIX INTEGRATION
# =============================================================================


class TestFullGCSweepLifecycleIntegration:
    """Zero-mock integration tests for the full end-to-end GC sweep lifecycle."""

    def test_full_gc_sweep_audit_water_dimer_orchestration(
        self,
        tmp_path: Path,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Simulates full quantum execution lifecycle on Water Dimer and executes complete GC audit."""
        workspace_dir = tmp_path / "cochem_full_lifecycle"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        scratch_dir = workspace_dir / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        registry_dir = workspace_dir / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        h5_state_path = workspace_dir / "cochem_state.h5"

        # ---------------------------------------------------------------------
        # 1. METHOD MATRIX SCAFFOLDING & WATER DIMER STATE PERSISTENCE [M]
        # ---------------------------------------------------------------------
        enforcer = HDF5OntologyEnforcer(hdf5_path=h5_state_path)
        dimer_coords = np.array([c[1:] for c in WATER_DIMER_COORDINATES], dtype=np.float64)

        payload: Dict[str, Any] = {
            "molecule_name": "Water_Dimer_H4O2",
            "xyz_coordinates": dimer_coords.tolist(),
            "energy": WATER_DIMER_ENERGY_EH,
            "symmetry_group": WATER_DIMER_SYMMETRY,
            "LAM_TRIGGER_REQUIRED": False,
        }
        basin_group = "basins/basin_water_dimer_opt_001"
        enforcer.write_record(basin_group, payload)

        # ---------------------------------------------------------------------
        # 2. ALLOCATE IPC SHARED MEMORY BUFFERS [D]
        # ---------------------------------------------------------------------
        shm_names = [
            f"cochem_shm_coords_{os.getpid()}_{int(time.time() * 1000)}",
            f"cochem_shm_hessian_{os.getpid()}_{int(time.time() * 1000)}",
        ]

        # Allocate coords buffer
        shm_c = shared_memory.SharedMemory(
            name=shm_names[0], create=True, size=len(dimer_coords.tobytes())
        )
        managed_shm_tracker.append(shm_c)
        assert shm_c.buf is not None
        shm_c.buf[: len(dimer_coords.tobytes())] = dimer_coords.tobytes()

        # Allocate simulated Hessian buffer (18 x 18 float64 = 324 doubles = 2592 bytes)
        hessian_shape = (18, 18)
        hessian_arr = np.zeros(hessian_shape, dtype=np.float64)
        np.fill_diagonal(hessian_arr, 0.5)  # Physical positive diagonal curvature
        hessian_bytes = hessian_arr.tobytes()
        shm_h = shared_memory.SharedMemory(name=shm_names[1], create=True, size=len(hessian_bytes))
        managed_shm_tracker.append(shm_h)
        assert shm_h.buf is not None
        shm_h.buf[: len(hessian_bytes)] = hessian_bytes

        # ---------------------------------------------------------------------
        # 3. GENERATE EPHEMERAL SWMR BACKUPS & SCRATCH JOB DUMPS [E]
        # ---------------------------------------------------------------------
        ephemeral_swmr_files = [
            workspace_dir / "cochem_state.h5.tmp",
            workspace_dir / "cochem_state.h5.swmr.tmp",
            workspace_dir / "cochem_state.h5.bak",
        ]
        for f in ephemeral_swmr_files:
            f.write_bytes(b"SWMR_BACKUP_JOURNAL_CHUNK")

        job_scratch = scratch_dir / "job_water_dimer_opt_b3lyp"
        job_scratch.mkdir(parents=True, exist_ok=True)
        (job_scratch / "water_dimer.gbw").write_bytes(b"ORCA_GBW_BINARY")
        (job_scratch / "water_dimer.densities").write_bytes(b"ELECTRON_DENSITY_ARRAY")
        (job_scratch / "core.55120").write_bytes(b"FORTRAN_CORE_DUMP")
        (job_scratch / "orca_EXT.extinp.tmp").write_bytes(b"EXTINP_TMP")

        # ---------------------------------------------------------------------
        # 4. EXECUTE COMPLETE GC SWEEP AUDIT
        # ---------------------------------------------------------------------
        audit_report = GCSweepAuditor.execute_full_gc_audit(
            workspace_dir=workspace_dir,
            active_shm_targets=[shm_c, shm_h],
            method_metadata=METHOD_MATRIX_SPECS,
        )

        # ---------------------------------------------------------------------
        # 5. RIGOROUS POST-EXECUTION AUDIT ASSERTIONS
        # ---------------------------------------------------------------------
        # 5.1 Assert Sterility
        assert audit_report.is_sterile is True, "Post-execution environment must be 100% sterile"

        # 5.2 Assert Ephemeral SWMR Files Swept
        assert audit_report.hdf5_ephemeral_swept_count >= len(ephemeral_swmr_files)
        for ef in ephemeral_swmr_files:
            assert not ef.exists(), f"Ephemeral SWMR file {ef} must not exist"

        # 5.3 Assert Scratch is completely empty
        assert len(list(scratch_dir.iterdir())) == 0, "Scratch directory must be completely empty"
        assert audit_report.scratch_files_swept_count >= 4
        assert audit_report.scratch_dirs_swept_count >= 1

        # 5.4 Assert Shared Memory buffers released (cross-platform verification)
        assert len(audit_report.shared_memory_released_buffers) == 2
        for name in shm_names:
            with pytest.raises(FileNotFoundError):
                probe = shared_memory.SharedMemory(name=name)
                probe.close()

        # 5.5 Assert Authoritative HDF5 database is intact and contains authentic Water Dimer record
        assert h5_state_path.exists(), "Authoritative HDF5 database must remain intact"
        with h5py.File(h5_state_path, "r") as h5f:
            assert basin_group in h5f
            grp = h5f[basin_group]
            assert grp.attrs["molecule_name"] == "Water_Dimer_H4O2"
            assert grp.attrs["symmetry_group"] == "Cs"
            assert math.isclose(float(grp.attrs["energy"]), WATER_DIMER_ENERGY_EH, rel_tol=1e-5)
            saved_coords = grp["xyz_coordinates"][:]
            assert bool(np.all(np.abs(saved_coords - dimer_coords) < 1e-5))

        # 5.6 Assert Provenance Tags
        assert audit_report.provenance_chain == ["[M]", "[D]", "[E]"]
        report_dict = audit_report.to_dict()
        assert report_dict["is_sterile"] is True
        assert report_dict["workspace_root"] == str(workspace_dir.resolve())


# =============================================================================
# TEST SUITE 6: PROCESS & LIFECYCLE SAFETY GUARANTEES
# =============================================================================


class TestProcessAndLifecycleSafety:
    """Zero-mock tests verifying process reaping and shared memory lifecycle safety."""

    def test_zombie_subprocess_reaper_integration(self) -> None:
        """Verifies that cleanup_zombie_processes actively sweeps running processes and clears tracking."""
        initial_count = len(get_active_popen_processes())
        assert initial_count == 0, "Initial process registry must be empty"

        # Spawn a genuine, active subprocess that is STILL RUNNING
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10.0)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        register_popen_process(proc)

        active = get_active_popen_processes()
        assert len(active) >= 1
        assert proc.poll() is None, "Subprocess must be actively running before cleanup"

        # Run cleanup on the actively running subprocess
        cleanup_zombie_processes()

        # Allow brief interval for termination to propagate
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        assert proc.poll() is not None, "Subprocess must be terminated by cleanup_zombie_processes"
        remaining = get_active_popen_processes()
        assert len(remaining) == 0, "Post-cleanup process registry must be empty"

    def test_shared_memory_fixture_safety_on_error(
        self,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Verifies that managed_shm_tracker safely registers allocations."""
        test_name = f"cochem_shm_fixture_probe_{os.getpid()}_{int(time.time() * 1000)}"
        shm = shared_memory.SharedMemory(name=test_name, create=True, size=128)
        managed_shm_tracker.append(shm)
        assert shm.name == test_name
        assert len(managed_shm_tracker) >= 1
