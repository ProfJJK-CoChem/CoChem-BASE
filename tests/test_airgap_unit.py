"""Unit Test Suite: Air-Gap Boundary Monitoring & Directory State Utilities.

Module: tests/test_airgap_unit.py
Adheres strictly to the Zero-Mock Mandate and Method Matrix v4 Standards:
- Zero Mocks / Stubs: Uses 100% genuine filesystem operations, real cryptographic SHA-256 hashing, and OS audit hooks.
- DirectoryStateSnapshot: Cryptographic SHA-256 and byte-level stat tracking across directory trees.
- FileIOMonitor: Native Python audit hook (sys.addaudithook) and path interception.
- Air-Gap Path Boundary Verification: Validates dynamic data routing away from the static execution repository.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pytest

# Add repo root and scripts to sys.path for direct imports
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from airgap_trap import (
    BLOCKED_EXTENSIONS,
    AirgapScanResult,
    format_violation_report,
    is_blocked_file,
    scan_repository,
)
from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_cochem_root,
    get_repo_root,
    get_scratch_dir,
    get_state_file_path,
    resolve_mapped_path,
)

DEFAULT_EXCLUDED_DIRS: Set[str] = {
    ".git",
    ".venv",
    ".trash",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".agents",
}


class DirectoryStateSnapshot:
    """Captures and compares cryptographic and stat-based states of a directory tree.

    Provides irrefutable proof of zero modification and zero bytes written to static execution repositories.
    """

    def __init__(
        self,
        root: Path,
        exclude_dirs: Optional[Sequence[str] | Set[str]] = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.exclude_dirs: Set[str] = set(exclude_dirs) if exclude_dirs is not None else set(DEFAULT_EXCLUDED_DIRS)
        self.files: Dict[str, Tuple[int, int, str]] = {}  # rel_path -> (size_bytes, mtime_ns, sha256)
        self.directories: Set[str] = set()
        self.capture()

    def capture(self) -> None:
        """Traverses the directory tree and records stats and SHA-256 hashes."""
        self.files.clear()
        self.directories.clear()

        if not self.root.exists() or not self.root.is_dir():
            return

        for dirpath, dirnames, filenames in os.walk(self.root, topdown=True):
            # Prune excluded directories in place
            dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]

            rel_dir = os.path.relpath(dirpath, self.root)
            if rel_dir != ".":
                self.directories.add(rel_dir.replace("\\", "/"))

            for fname in filenames:
                full_path = Path(dirpath) / fname
                rel_path = os.path.relpath(full_path, self.root).replace("\\", "/")

                try:
                    stat_res = full_path.stat()
                    file_size = stat_res.st_size
                    mtime_ns = stat_res.st_mtime_ns

                    hasher = hashlib.sha256()
                    with open(full_path, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    sha256_hex = hasher.hexdigest()

                    self.files[rel_path] = (file_size, mtime_ns, sha256_hex)
                except (OSError, PermissionError):
                    continue

    def diff(self, current: DirectoryStateSnapshot) -> Dict[str, Any]:
        """Calculates differences between this baseline snapshot and a subsequent snapshot."""
        added_files: Set[str] = set()
        removed_files: Set[str] = set()
        modified_files: Set[str] = set()
        bytes_written: int = 0

        current_files = current.files

        for path, (size, _, sha256) in current_files.items():
            if path not in self.files:
                added_files.add(path)
                bytes_written += size
            else:
                base_size, _, base_sha = self.files[path]
                if sha256 != base_sha:
                    modified_files.add(path)
                    bytes_written += max(0, size - base_size) if size > base_size else size

        for path in self.files:
            if path not in current_files:
                removed_files.add(path)

        added_dirs = current.directories - self.directories
        removed_dirs = self.directories - current.directories

        return {
            "added_files": added_files,
            "removed_files": removed_files,
            "modified_files": modified_files,
            "added_directories": added_dirs,
            "removed_directories": removed_dirs,
            "bytes_written": bytes_written,
        }

    def assert_zero_modifications(self, current: DirectoryStateSnapshot, context: str = "") -> None:
        """Asserts that no files or directories were added, removed, or modified."""
        diff_res = self.diff(current)
        added = diff_res["added_files"]
        removed = diff_res["removed_files"]
        modified = diff_res["modified_files"]
        bytes_written = diff_res["bytes_written"]

        error_lines: List[str] = []
        if added:
            error_lines.append(f"Added files: {sorted(added)}")
        if removed:
            error_lines.append(f"Removed files: {sorted(removed)}")
        if modified:
            error_lines.append(f"Modified files: {sorted(modified)}")
        if bytes_written > 0:
            error_lines.append(f"Bytes written: {bytes_written}")

        if error_lines:
            ctx_msg = f" [{context}]" if context else ""
            raise AssertionError(
                f"Air-Gap Boundary Violation: Static directory mutation detected{ctx_msg}:\n"
                + "\n".join(error_lines)
            )


class FileIOMonitor:
    """Tracks filesystem write events via Python audit hook (sys.addaudithook) and records static boundary violations."""

    _hook_registered: bool = False
    _active_monitors: List[FileIOMonitor] = []

    @classmethod
    def _global_audit_hook(cls, event: str, args: tuple) -> None:
        """Global sys.addaudithook handler dispatching write events to all active monitors."""
        if not cls._active_monitors:
            return

        target_path: Optional[Path] = None
        operation: Optional[str] = None

        if event == "open" and len(args) >= 2:
            path_arg, mode_arg = args[0], args[1]
            flags_arg = args[2] if len(args) > 2 else 0
            if isinstance(path_arg, (str, Path, os.PathLike)):
                is_write = False
                if isinstance(mode_arg, str) and any(c in mode_arg for c in ("w", "a", "x", "+")):
                    is_write = True
                elif isinstance(flags_arg, int) and (
                    flags_arg & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
                ):
                    is_write = True
                if is_write:
                    target_path = Path(path_arg)
                    operation = f"open({mode_arg})"

        elif event in ("os.remove", "os.unlink", "os.mkdir", "os.rmdir", "os.truncate"):
            if args and isinstance(args[0], (str, Path, os.PathLike)):
                target_path = Path(args[0])
                operation = event

        elif event in ("os.rename", "os.replace"):
            if len(args) > 1 and isinstance(args[1], (str, Path, os.PathLike)):
                target_path = Path(args[1])
                operation = event

        if target_path and operation:
            for mon in list(cls._active_monitors):
                mon.record_write(target_path, operation)

    def __init__(
        self,
        restricted_roots: Sequence[Path],
        allowed_roots: Optional[Sequence[Path]] = None,
        ignore_patterns: Optional[Sequence[str] | Set[str]] = None,
    ) -> None:
        self.restricted_roots: List[Path] = [Path(p).resolve() for p in restricted_roots]
        self.allowed_roots: List[Path] = [Path(p).resolve() for p in (allowed_roots or [])]
        self.ignore_patterns: Set[str] = set(
            ignore_patterns or [".pytest_cache", "__pycache__", ".git", ".mypy_cache", ".ruff_cache"]
        )
        self.recorded_writes: List[Tuple[Path, str]] = []
        self.violations: List[Tuple[Path, str]] = []
        self.active: bool = False

        if not FileIOMonitor._hook_registered:
            try:
                sys.addaudithook(FileIOMonitor._global_audit_hook)
                FileIOMonitor._hook_registered = True
            except Exception:
                pass

    def __enter__(self) -> FileIOMonitor:
        self.active = True
        if self not in FileIOMonitor._active_monitors:
            FileIOMonitor._active_monitors.append(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.active = False
        if self in FileIOMonitor._active_monitors:
            FileIOMonitor._active_monitors.remove(self)

    def is_in_path(self, target: Path, root: Path) -> bool:
        """Checks if target is within or equals root directory."""
        try:
            target.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _should_ignore(self, path: Path) -> bool:
        """Checks if path matches any benign internal harness ignore patterns."""
        path_str = str(path.resolve())
        return any(ign in path_str for ign in self.ignore_patterns)

    def record_write(self, target_path: Path, operation: str = "write") -> None:
        """Records a file write/create/delete operation and flags restricted boundary breaches."""
        if self._should_ignore(target_path):
            return

        resolved = target_path.resolve()
        self.recorded_writes.append((resolved, operation))

        for restricted in self.restricted_roots:
            if self.is_in_path(resolved, restricted):
                self.violations.append((resolved, operation))

    def assert_zero_violations(self) -> None:
        """Asserts that zero write operations targeted restricted static roots."""
        if self.violations:
            violation_details = "\n".join(f"- {p} (operation: {op})" for p, op in self.violations)
            raise AssertionError(
                f"Air-Gap Boundary Violation: {len(self.violations)} write(s) targeted restricted static repository:\n"
                f"{violation_details}"
            )


# =============================================================================
# UNIT TESTS: DirectoryStateSnapshot
# =============================================================================

def test_directory_state_snapshot_clean_baseline(tmp_path: Path) -> None:
    """Verify DirectoryStateSnapshot detects no changes on an untouched directory."""
    test_dir = tmp_path / "static_repo"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "file1.txt").write_text("Hello World", encoding="utf-8")
    (test_dir / "subdir").mkdir()
    (test_dir / "subdir" / "file2.py").write_text("print('test')", encoding="utf-8")

    snap1 = DirectoryStateSnapshot(test_dir)
    assert len(snap1.files) == 2
    assert len(snap1.directories) == 1

    snap2 = DirectoryStateSnapshot(test_dir)
    diff_res = snap1.diff(snap2)
    assert len(diff_res["added_files"]) == 0
    assert len(diff_res["removed_files"]) == 0
    assert len(diff_res["modified_files"]) == 0
    assert diff_res["bytes_written"] == 0

    snap1.assert_zero_modifications(snap2)


def test_directory_state_snapshot_detects_file_addition(tmp_path: Path) -> None:
    """Verify DirectoryStateSnapshot detects added files and computes bytes written."""
    test_dir = tmp_path / "static_repo"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "base.py").write_text("x = 1", encoding="utf-8")

    snap_before = DirectoryStateSnapshot(test_dir)

    new_file = test_dir / "added.txt"
    new_file.write_text("New file content with 30 bytes!", encoding="utf-8")

    snap_after = DirectoryStateSnapshot(test_dir)
    diff = snap_before.diff(snap_after)

    assert "added.txt" in diff["added_files"]
    assert diff["bytes_written"] == len("New file content with 30 bytes!".encode("utf-8"))

    with pytest.raises(AssertionError, match="Air-Gap Boundary Violation: Static directory mutation detected"):
        snap_before.assert_zero_modifications(snap_after)


def test_directory_state_snapshot_detects_file_modification(tmp_path: Path) -> None:
    """Verify DirectoryStateSnapshot detects content modification via SHA-256 mismatch."""
    test_dir = tmp_path / "static_repo"
    test_dir.mkdir(parents=True, exist_ok=True)
    target = test_dir / "script.py"
    target.write_text("version = 1.0", encoding="utf-8")

    snap_before = DirectoryStateSnapshot(test_dir)

    target.write_text("version = 2.0_modified_string", encoding="utf-8")
    snap_after = DirectoryStateSnapshot(test_dir)
    diff = snap_before.diff(snap_after)

    assert "script.py" in diff["modified_files"]
    with pytest.raises(AssertionError, match="Air-Gap Boundary Violation: Static directory mutation detected"):
        snap_before.assert_zero_modifications(snap_after)


def test_directory_state_snapshot_detects_file_deletion(tmp_path: Path) -> None:
    """Verify DirectoryStateSnapshot detects removed files."""
    test_dir = tmp_path / "static_repo"
    test_dir.mkdir(parents=True, exist_ok=True)
    file_to_delete = test_dir / "temp_to_delete.txt"
    file_to_delete.write_text("to be deleted", encoding="utf-8")

    snap_before = DirectoryStateSnapshot(test_dir)
    file_to_delete.unlink()
    snap_after = DirectoryStateSnapshot(test_dir)

    diff = snap_before.diff(snap_after)
    assert "temp_to_delete.txt" in diff["removed_files"]
    with pytest.raises(AssertionError, match="Air-Gap Boundary Violation: Static directory mutation detected"):
        snap_before.assert_zero_modifications(snap_after)


def test_directory_state_snapshot_ignores_excluded_directories(tmp_path: Path) -> None:
    """Verify DirectoryStateSnapshot prunes excluded directories (.git, __pycache__, .pytest_cache)."""
    test_dir = tmp_path / "static_repo"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "main.py").write_text("print(1)", encoding="utf-8")

    for ex_name in [".git", "__pycache__", ".pytest_cache", ".venv"]:
        ex_dir = test_dir / ex_name
        ex_dir.mkdir(parents=True, exist_ok=True)
        (ex_dir / "ignored_file.tmp").write_text("ignored content", encoding="utf-8")

    snap1 = DirectoryStateSnapshot(test_dir)
    assert len(snap1.files) == 1
    assert "main.py" in snap1.files
    assert len(snap1.directories) == 0

    # Mutate inside excluded directory
    (test_dir / ".git" / "another_ignored.dat").write_text("git data", encoding="utf-8")
    snap2 = DirectoryStateSnapshot(test_dir)

    diff = snap1.diff(snap2)
    assert diff["bytes_written"] == 0
    snap1.assert_zero_modifications(snap2)


# =============================================================================
# UNIT TESTS: FileIOMonitor
# =============================================================================

def test_file_io_monitor_clean_execution(tmp_path: Path) -> None:
    """Verify FileIOMonitor allows writes strictly within dynamic data roots."""
    static_root = tmp_path / "static_repo"
    static_root.mkdir(parents=True, exist_ok=True)

    dynamic_root = tmp_path / "dynamic_artifacts"
    dynamic_root.mkdir(parents=True, exist_ok=True)

    with FileIOMonitor(restricted_roots=[static_root], allowed_roots=[dynamic_root]) as mon:
        allowed_log = dynamic_root / "calculation.log"
        allowed_log.write_text("SCF iteration completed successfully", encoding="utf-8")

        allowed_h5 = dynamic_root / "state.h5"
        allowed_h5.write_bytes(b"\x89HDF\r\n\x1a\n")

    assert len(mon.recorded_writes) >= 2
    assert len(mon.violations) == 0
    mon.assert_zero_violations()


def test_file_io_monitor_detects_prohibited_static_write(tmp_path: Path) -> None:
    """Verify FileIOMonitor intercepts write into restricted static repository root."""
    static_root = tmp_path / "static_repo"
    static_root.mkdir(parents=True, exist_ok=True)

    dynamic_root = tmp_path / "dynamic_artifacts"
    dynamic_root.mkdir(parents=True, exist_ok=True)

    with FileIOMonitor(restricted_roots=[static_root], allowed_roots=[dynamic_root]) as mon:
        bad_file = static_root / "leaked_scratch.tmp"
        bad_file.write_text("Illegal write to static tree", encoding="utf-8")

    assert len(mon.violations) >= 1
    with pytest.raises(AssertionError, match="Air-Gap Boundary Violation"):
        mon.assert_zero_violations()


def test_file_io_monitor_manual_write_recording(tmp_path: Path) -> None:
    """Verify FileIOMonitor manual record_write method accurately distinguishes roots."""
    static_root = tmp_path / "static_repo"
    dynamic_root = tmp_path / "dynamic_artifacts"

    mon = FileIOMonitor(restricted_roots=[static_root], allowed_roots=[dynamic_root])

    mon.record_write(dynamic_root / "test.json", "write_json")
    assert len(mon.violations) == 0

    mon.record_write(static_root / "leak.h5", "write_h5")
    assert len(mon.violations) == 1
    assert mon.violations[0][0] == (static_root / "leak.h5").resolve()
    assert mon.violations[0][1] == "write_h5"


def test_file_io_monitor_path_containment(tmp_path: Path) -> None:
    """Verify is_in_path correctly resolves nested and parent relative paths."""
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    sub = root / "src" / "pkg"
    sub.mkdir(parents=True, exist_ok=True)

    other = tmp_path / "other"
    other.mkdir(parents=True, exist_ok=True)

    mon = FileIOMonitor(restricted_roots=[root])
    assert mon.is_in_path(sub / "mod.py", root) is True
    assert mon.is_in_path(root / "README.md", root) is True
    assert mon.is_in_path(other / "data.h5", root) is False


# =============================================================================
# UNIT TESTS: Air-Gap Boundary Utility Functions & Path Isolation
# =============================================================================

def test_path_resolvers_dynamic_tier_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify path resolvers direct dynamic outputs strictly to the configured artifact directory."""
    custom_art = tmp_path / "custom_artifacts"
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(custom_art))

    resolved_art = get_artifact_dir()
    assert resolved_art == custom_art.resolve()

    state_path = get_state_file_path("cochem_state.h5")
    assert state_path == (custom_art / "cochem_state.h5").resolve()
    assert not str(state_path).startswith(str(get_base_root()))

    scratch_path = get_scratch_dir()
    assert str(scratch_path).startswith(str(custom_art)) or str(scratch_path).startswith(str(Path.home()))


def test_blocked_extensions_matching() -> None:
    """Verify blocked extension detection covers all restricted dynamic artifact formats."""
    blocked_set = set(BLOCKED_EXTENSIONS)
    assert is_blocked_file(Path("dataset.h5"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path("geometry.xyz"), blocked_set) == (True, ".xyz")
    assert is_blocked_file(Path("orbitals.gbw"), blocked_set) == (True, ".gbw")
    assert is_blocked_file(Path("scratch.tmp"), blocked_set) == (True, ".tmp")
    assert is_blocked_file(Path("orca_run.log"), blocked_set) == (True, ".log")

    # Case insensitivity
    assert is_blocked_file(Path("SURFACE.H5"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path("COORDS.XYZ"), blocked_set) == (True, ".xyz")

    # Allowed code files
    assert is_blocked_file(Path("main.py"), blocked_set) == (False, "")
    assert is_blocked_file(Path("config.json"), blocked_set) == (False, "")
    assert is_blocked_file(Path("README.md"), blocked_set) == (False, "")


def test_clean_directory_scan_airgap_trap(tmp_path: Path) -> None:
    """Verify scan_repository from airgap_trap passes cleanly on compliant static trees."""
    static_tree = tmp_path / "static_cochem"
    static_tree.mkdir(parents=True, exist_ok=True)
    (static_tree / "core.py").write_text("class Engine: pass", encoding="utf-8")
    (static_tree / "README.md").write_text("# Static Repo", encoding="utf-8")

    result: AirgapScanResult = scan_repository(static_tree, use_git=False)
    assert result.is_clean is True
    assert result.violation_count == 0
