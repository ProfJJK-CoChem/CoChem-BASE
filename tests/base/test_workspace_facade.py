"""Real filesystem admission and concurrent scaffolding for the shipped facade."""

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cochem.core.context import AirGapViolationError, ExecutionContext, FileLock, scoped_context
from cochem_base.core_engine.cochem_core_workspace_manager import (
    CORE_DIRECTORIES,
    WorkspaceManager,
    provision_core_directories,
    scaffold_core_directories,
)


def test_workspace_concurrent_scaffolding_preserves_files(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    existing = root / "Registry"
    existing.mkdir()
    original_modes = {path: stat.S_IMODE(path.stat().st_mode) for path in (root, existing)}
    record = existing / "original.json"
    record.write_bytes(b'{"retained":true}\n')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: WorkspaceManager(root).scaffold(), range(8)))
    assert all(set(result) == set(CORE_DIRECTORIES) for result in results)
    assert record.read_bytes() == b'{"retained":true}\n'
    for path in [root, *results[0].values()]:
        assert path.is_dir()
        if os.name == "posix":
            actual_mode = stat.S_IMODE(path.stat().st_mode)
            assert actual_mode & ~0o750 == 0
            assert actual_mode & 0o700 == 0o700
            if path in original_modes:
                assert actual_mode == original_modes[path] & 0o750


def test_workspace_rejects_source_and_resolved_source_alias(tmp_path):
    source = Path(__file__).resolve().parents[2]
    target = source / "prohibited-workspace-scaffold"
    alias = tmp_path / "source-link"
    alias.symlink_to(source, target_is_directory=True)
    for requested in (target, alias / target.name):
        with pytest.raises(AirGapViolationError):
            scaffold_core_directories(requested)
    assert not target.exists()


@pytest.mark.parametrize("name", ["Input_Files", "Scratch", ".workspace.lock"])
def test_workspace_redirect_is_rejected_before_any_child_created(tmp_path, name):
    root = tmp_path / "artifacts"
    root.mkdir()
    other = tmp_path / "outside"
    other.mkdir()
    (root / name).symlink_to(other, target_is_directory=True)
    before = set(root.iterdir())
    with pytest.raises(AirGapViolationError):
        scaffold_core_directories(root)
    assert set(root.iterdir()) == before
    assert not tuple(other.iterdir())


def test_workspace_non_directory_child_is_rejected_without_partial_scaffold(tmp_path):
    root = tmp_path / "artifacts"
    root.mkdir()
    marker = root / "Logs"
    marker.write_bytes(b"student data")
    with pytest.raises(NotADirectoryError):
        scaffold_core_directories(root)
    assert tuple(root.iterdir()) == (marker,)
    assert marker.read_bytes() == b"student data"


def test_workspace_keeps_stricter_existing_permissions(tmp_path):
    root = tmp_path / "private-artifacts"
    root.mkdir(mode=0o700)
    (root / "Registry").mkdir(mode=0o700)
    paths = scaffold_core_directories(root)
    assert set(paths) == set(CORE_DIRECTORIES)
    if os.name == "posix":
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(paths["Registry"].stat().st_mode) == 0o700


def test_student_setup_automatically_provisions_workspace(tmp_path):
    from cochem_base.interfaces.student_setup import StudentSetupService
    source = tmp_path / "student-assignment"
    source.mkdir()
    original = source / "student-notes.md"
    original.write_bytes(b"Retain my research notes")
    runtime = tmp_path / "runtime"
    service = StudentSetupService(runtime, source)
    assert service.artifact_dir == runtime
    assert all((runtime / name).is_dir() for name in CORE_DIRECTORIES)
    assert original.read_bytes() == b"Retain my research notes"


def test_lock_free_stage0_directory_provisioning_preserves_data_and_permissions(tmp_path):
    """Real concurrent mkdir operations; no shared-filesystem acceptance claim."""
    root = tmp_path / "stage0-artifacts"
    root.mkdir(mode=0o700)
    (root / "Logs").mkdir(mode=0o700)
    notes = root / "Logs" / "retained-notes.txt"
    notes.write_bytes(b"Student-owned retained observations")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: provision_core_directories(root), range(8)))
    assert all(set(paths) == set(CORE_DIRECTORIES) for paths in results)
    assert notes.read_bytes() == b"Student-owned retained observations"
    assert not (root / ".workspace.lock").exists()
    if os.name == "posix":
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "Logs").stat().st_mode) == 0o700


@pytest.mark.parametrize("tier", ["Tier 5 HPC", "Tier 6 HPC"])
def test_hpc_context_provisions_without_prohibited_external_lock(tmp_path, tier):
    """Enforce the declared tier policy using real filesystem operations."""
    source = tmp_path / "source"
    baseline = tmp_path / "baseline"
    source.mkdir()
    baseline.mkdir()
    root = tmp_path / "hpc-artifacts"
    context = ExecutionContext("directory-policy", "student-provisioning", source,
                               baseline, root, tmp_path / "local-scratch", tier)
    with scoped_context(context):
        with pytest.raises(RuntimeError, match="locks are prohibited"):
            FileLock(root / ".workspace.lock")
        paths = scaffold_core_directories(root)
    assert all(path.is_dir() for path in paths.values())
    assert not (root / ".workspace.lock").exists()
    assert not tuple(source.iterdir()) and not tuple(baseline.iterdir())
