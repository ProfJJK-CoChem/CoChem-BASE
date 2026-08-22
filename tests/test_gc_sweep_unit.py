"""Unit Test Suite: GC Sweep Audit & Path Containment (tests/test_gc_sweep_unit.py).

Adheres strictly to the CoChem Zero-Mock Mandate and Method Matrix v4 Standards:
- Zero Mocks / Stubs: Uses 100% genuine OS processes, real files, real HDF5 stores, and physical constraints.
- Path Traversal Defense Unit Tests: Validates strict path containment for relative escapes, absolute escapes,
  null bytes, cross-drive traversal, and prefix spoofing.
- Ephemeral Pattern Matching Unit Tests: Validates exact classification of .tmp, .swmr.tmp, .bak, .extinp.tmp,
  .lock.tmp, core.* while strictly preserving authoritative .h5 state files.
- Cross-Platform Shared Memory Release: Asserts multiprocessing.shared_memory IPC buffers are created, verified,
  and unlinked without hardcoding POSIX /dev/shm.
- Scratch Sterilization Unit Tests: Tests full tree purging, read-only Windows file unlinking, and directory preservation.
- GC Sweep Audit Report Serialization: Validates dataclass conversion and [M], [D], [E] provenance chains.
"""

from __future__ import annotations

import os
import stat
import sys
import time
from multiprocessing import shared_memory
from pathlib import Path
from typing import Generator, List

import pytest

from cochem_base.exceptions import (
    PathTraversalError,
    ProvenanceErrorCode,
)
from tests.integration.test_gc_sweep import (
    GCSweepAuditor,
    GCSweepAuditReport,
)

# =============================================================================
# PYTEST FIXTURES FOR LIFECYCLE & SHM CLEANUP
# =============================================================================


@pytest.fixture
def managed_shm_tracker() -> Generator[List[shared_memory.SharedMemory], None, None]:
    """Fixture that tracks allocated SharedMemory instances and guarantees unlinking on teardown."""
    created_shm_list: List[shared_memory.SharedMemory] = []
    yield created_shm_list

    for shm in created_shm_list:
        try:
            shm.close()
        except Exception:
            pass
        try:
            shm.unlink()
        except Exception:
            pass


# =============================================================================
# TEST SUITE 1: PATH CONTAINMENT UNIT TESTS
# =============================================================================


class TestValidatePathContainmentUnit:
    """Unit tests for GCSweepAuditor.validate_path_containment."""

    def test_valid_relative_child_resolution(self, tmp_path: Path) -> None:
        """Valid relative child paths within the root boundary resolve to canonical paths."""
        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        child_dir = root / "subdir" / "job_001"
        child_dir.mkdir(parents=True, exist_ok=True)

        validated = GCSweepAuditor.validate_path_containment("subdir/job_001", root)
        assert validated == child_dir.resolve()
        assert validated.is_relative_to(root.resolve())

    def test_valid_nested_deep_path(self, tmp_path: Path) -> None:
        """Valid nested deep subdirectories within allowed root resolve safely."""
        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        deep_dir = root / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True, exist_ok=True)

        validated = GCSweepAuditor.validate_path_containment(deep_dir, root)
        assert validated == deep_dir.resolve()

    def test_parent_double_dot_escape_traversal(self, tmp_path: Path) -> None:
        """Path traversal attempts using double dots ('../../') raise PathTraversalError."""
        root = tmp_path / "sandbox" / "Scratch"
        root.mkdir(parents=True, exist_ok=True)

        traversal_attempts = [
            "../../",
            "..\\..",
            "../escape",
            "..\\escape",
            "sub/../../../../escaped",
            "sub\\..\\..\\..\\..\\escaped",
            "./../../etc/shadow",
            ".\\..\\..\\Windows\\System32",
        ]

        for attempt in traversal_attempts:
            with pytest.raises(PathTraversalError) as exc_info:
                GCSweepAuditor.validate_path_containment(attempt, root)

            err = exc_info.value
            assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
            assert "Path traversal escape attempt detected" in str(err)

    def test_absolute_path_outside_sandbox(self, tmp_path: Path) -> None:
        """Absolute paths resolving outside the sandbox root raise PathTraversalError."""
        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        outside = tmp_path / "outside_dir"
        outside.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(outside, root)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "outside allowed boundary" in str(exc_info.value)

    def test_null_byte_injection_blocked(self, tmp_path: Path) -> None:
        """Null byte injections raise PathTraversalError."""
        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        poisoned = str(root / "safe_dir") + "\x00/../../etc/passwd"

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(poisoned, root)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "Null-byte injection detected" in str(exc_info.value)

    def test_prefix_spoofing_blocked(self, tmp_path: Path) -> None:
        """Sibling directories sharing a string prefix raise PathTraversalError."""
        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        spoofed = tmp_path / "sandbox_fake" / "nested"
        spoofed.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(spoofed, root)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED

    def test_windows_cross_drive_blocked(self, tmp_path: Path) -> None:
        """Cross-drive path resolution on Windows raises PathTraversalError."""
        if sys.platform != "win32":
            pytest.skip("Drive mismatch test is Windows-specific")

        root = tmp_path / "sandbox"
        root.mkdir(parents=True, exist_ok=True)
        current_drive = root.resolve().drive.upper()
        other_drive = "Z:" if current_drive != "Z:" else "Y:"
        cross_drive_target = f"{other_drive}\\temp\\target"

        with pytest.raises(PathTraversalError) as exc_info:
            GCSweepAuditor.validate_path_containment(cross_drive_target, root)

        assert exc_info.value.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert "Cross-drive path traversal escape attempt detected" in str(exc_info.value)


# =============================================================================
# TEST SUITE 2: EPHEMERAL SWMR PATTERN MATCHING UNIT TESTS
# =============================================================================


class TestEphemeralSWMRPatternMatchingUnit:
    """Unit tests for GCSweepAuditor.is_ephemeral_swmr_backup_file."""

    def test_is_ephemeral_swmr_backup_positive(self) -> None:
        """Transient SWMR backups, lock files, and core dumps are correctly identified as ephemeral."""
        positive_cases = [
            Path("workspace/cochem_state.h5.tmp"),
            Path("workspace/cochem_state.h5.swmr.tmp"),
            Path("workspace/cochem_state.h5.tmp.bak"),
            Path("workspace/scf_history.tmp"),
            Path("workspace/orca_job.extinp.tmp"),
            Path("workspace/job_backup.bak"),
            Path("workspace/.cochem_workspace.lock.tmp"),
            Path("workspace/.job.lock.tmp"),
            Path("workspace/core.12345"),
            Path("workspace/core.998231"),
            Path("workspace/transient.tmp.1284"),
        ]

        for p in positive_cases:
            assert GCSweepAuditor.is_ephemeral_swmr_backup_file(p) is True, f"Failed for {p}"

    def test_is_ephemeral_swmr_backup_negative(self) -> None:
        """Authoritative primary HDF5 databases and persistent code files are NOT classified as ephemeral."""
        negative_cases = [
            Path("workspace/cochem_state.h5"),
            Path("workspace/landscape.h5"),
            Path("workspace/water_dimer_opt.h5"),
            Path("workspace/cochem_base.py"),
            Path("workspace/config.json"),
            Path("workspace/pyproject.toml"),
            Path("workspace/README.md"),
            Path("workspace/core_engine.py"),
            Path("workspace/core.py"),
            Path("workspace/core.json"),
            Path("workspace/core.toml"),
            Path("workspace/core.cochem"),
        ]

        for p in negative_cases:
            assert GCSweepAuditor.is_ephemeral_swmr_backup_file(p) is False, f"Failed for {p}"


# =============================================================================
# TEST SUITE 3: SHARED MEMORY IPC RELEASE UNIT TESTS
# =============================================================================


class TestSharedMemoryIPCUnit:
    """Unit tests for GCSweepAuditor.sweep_shared_memory."""

    def test_sweep_shared_memory_single_buffer(
        self,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Allocates a genuine shared memory segment, verifies release, and asserts FileNotFoundError upon attach."""
        shm_name = f"cochem_unit_shm_{os.getpid()}_{int(time.time() * 1000)}"
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=256)
        managed_shm_tracker.append(shm)
        assert shm.buf is not None
        shm.buf[:14] = b"COCHEM_PAYLOAD"

        # Sweep shared memory
        result = GCSweepAuditor.sweep_shared_memory([shm])
        assert result[shm_name] is True

        # Assert no subsequent attachment is possible
        with pytest.raises(FileNotFoundError):
            probe = shared_memory.SharedMemory(name=shm_name)
            probe.close()

    def test_sweep_shared_memory_multiple_named_buffers(
        self,
        managed_shm_tracker: List[shared_memory.SharedMemory],
    ) -> None:
        """Allocates multiple named buffers and audits their simultaneous unlinking."""
        buffer_names = [
            f"cochem_unit_shm_rank_0_{os.getpid()}_{int(time.time() * 1000)}",
            f"cochem_unit_shm_rank_1_{os.getpid()}_{int(time.time() * 1000)}",
        ]
        created = []
        for name in buffer_names:
            buf = shared_memory.SharedMemory(name=name, create=True, size=128)
            managed_shm_tracker.append(buf)
            created.append(buf)

        result = GCSweepAuditor.sweep_shared_memory(created)
        for name in buffer_names:
            assert result[name] is True
            with pytest.raises(FileNotFoundError):
                probe = shared_memory.SharedMemory(name=name)
                probe.close()

    def test_sweep_nonexistent_shared_memory_graceful(self) -> None:
        """Sweeping non-existent shared memory names handles FileNotFoundError gracefully."""
        nonexistent_name = f"cochem_nonexistent_shm_{os.getpid()}_{int(time.time() * 1000)}"
        result = GCSweepAuditor.sweep_shared_memory([nonexistent_name])
        assert result[nonexistent_name] is True


# =============================================================================
# TEST SUITE 4: SCRATCH DIRECTORY SWEEP UNIT TESTS
# =============================================================================


class TestScratchDirectorySweepUnit:
    """Unit tests for GCSweepAuditor.sweep_scratch_directory."""

    def test_sweep_scratch_empty_directory(self, tmp_path: Path) -> None:
        """Sweeping an already empty scratch directory returns zero removed items."""
        scratch_dir = tmp_path / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        files_removed, dirs_removed = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=tmp_path,
            preserve_root=True,
        )
        assert files_removed == 0
        assert dirs_removed == 0
        assert scratch_dir.exists()

    def test_sweep_scratch_nested_files_and_dirs(self, tmp_path: Path) -> None:
        """Sweeping a scratch directory with nested subdirectories cleans all transient files and subdirectories."""
        scratch_dir = tmp_path / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        sub1 = scratch_dir / "job_01"
        sub1.mkdir(parents=True, exist_ok=True)
        sub2 = sub1 / "nested_grid"
        sub2.mkdir(parents=True, exist_ok=True)

        f1 = scratch_dir / "root_scratch.tmp"
        f2 = sub1 / "job.gbw"
        f3 = sub2 / "grid_integrals.dat"

        f1.write_bytes(b"DATA_F1")
        f2.write_bytes(b"DATA_F2")
        f3.write_bytes(b"DATA_F3")

        files_removed, dirs_removed = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=tmp_path,
            preserve_root=True,
        )

        assert files_removed == 3
        assert dirs_removed == 2  # sub1 and sub2
        assert scratch_dir.exists()
        assert len(list(scratch_dir.iterdir())) == 0

    def test_sweep_scratch_preserve_root_flag(self, tmp_path: Path) -> None:
        """Testing preserve_root=False deletes the scratch root directory itself."""
        scratch_dir = tmp_path / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        (scratch_dir / "transient.tmp").write_bytes(b"DATA")

        files_removed, dirs_removed = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=tmp_path,
            preserve_root=False,
        )

        assert files_removed == 1
        assert dirs_removed == 1
        assert not scratch_dir.exists()

    def test_sweep_scratch_read_only_files_on_windows(self, tmp_path: Path) -> None:
        """Ensures read-only files on Windows are cleanly unlinked by revoking read-only permissions."""
        scratch_dir = tmp_path / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        ro_file = scratch_dir / "locked_scratch.tmp"
        ro_file.write_bytes(b"LOCKED_DATA")

        # Set read-only attribute
        os.chmod(str(ro_file), stat.S_IREAD)

        files_removed, _ = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=tmp_path,
            preserve_root=True,
        )

        assert files_removed == 1
        assert not ro_file.exists()

    def test_sweep_scratch_nested_read_only_files_on_windows(self, tmp_path: Path) -> None:
        """Ensures deeply nested read-only files in scratch subdirectories are cleanly unlinked on Windows."""
        scratch_dir = tmp_path / "Scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        sub_dir = scratch_dir / "job_nested" / "integrals"
        sub_dir.mkdir(parents=True, exist_ok=True)

        ro_file1 = sub_dir / "read_only_grid.dat"
        ro_file1.write_bytes(b"GRID_INTEGRAL_DATA")
        os.chmod(str(ro_file1), stat.S_IREAD)

        ro_file2 = scratch_dir / "job_nested" / "locked_output.tmp"
        ro_file2.write_bytes(b"LOCKED_TMP")
        os.chmod(str(ro_file2), stat.S_IREAD)

        files_removed, dirs_removed = GCSweepAuditor.sweep_scratch_directory(
            scratch_dir,
            allowed_root=tmp_path,
            preserve_root=True,
        )

        assert files_removed == 2
        assert dirs_removed == 2  # job_nested and integrals
        assert not (scratch_dir / "job_nested").exists()
        assert len(list(scratch_dir.iterdir())) == 0


# =============================================================================
# TEST SUITE 5: GC SWEEP AUDIT REPORT DATACLASS UNIT TESTS
# =============================================================================


class TestGCSweepAuditReportDataclassUnit:
    """Unit tests for GCSweepAuditReport serialization and provenance validation."""

    def test_audit_report_to_dict_structure(self, tmp_path: Path) -> None:
        """Verifies that GCSweepAuditReport converts to a valid dictionary with expected keys and types."""
        report = GCSweepAuditReport(
            workspace_root=tmp_path / "ws",
            scratch_dir=tmp_path / "ws" / "Scratch",
            hdf5_ephemeral_swept_count=3,
            hdf5_ephemeral_swept_files=["f1.tmp", "f2.tmp", "f3.tmp"],
            scratch_files_swept_count=5,
            scratch_dirs_swept_count=2,
            shared_memory_released_buffers=["shm_001", "shm_002"],
            zombie_subprocesses_reaped=0,
            provenance_chain=["[M]", "[D]", "[E]"],
            is_sterile=True,
        )

        d = report.to_dict()
        assert d["workspace_root"] == str(tmp_path / "ws")
        assert d["scratch_dir"] == str(tmp_path / "ws" / "Scratch")
        assert d["hdf5_ephemeral_swept_count"] == 3
        assert d["hdf5_ephemeral_swept_files"] == ["f1.tmp", "f2.tmp", "f3.tmp"]
        assert d["scratch_files_swept_count"] == 5
        assert d["scratch_dirs_swept_count"] == 2
        assert d["shared_memory_released_buffers"] == ["shm_001", "shm_002"]
        assert d["zombie_subprocesses_reaped"] == 0
        assert d["provenance_chain"] == ["[M]", "[D]", "[E]"]
        assert d["is_sterile"] is True
        assert isinstance(d["timestamp"], float)

    def test_audit_report_provenance_tags(self, tmp_path: Path) -> None:
        """Verifies that default provenance chain contains authentic [M], [D], [E] tags."""
        report = GCSweepAuditReport(
            workspace_root=tmp_path / "ws",
            scratch_dir=tmp_path / "ws" / "Scratch",
            hdf5_ephemeral_swept_count=0,
            hdf5_ephemeral_swept_files=[],
            scratch_files_swept_count=0,
            scratch_dirs_swept_count=0,
            shared_memory_released_buffers=[],
            zombie_subprocesses_reaped=0,
        )
        assert "[M]" in report.provenance_chain
        assert "[D]" in report.provenance_chain
        assert "[E]" in report.provenance_chain
