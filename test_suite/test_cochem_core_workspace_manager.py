"""
Unit and integration tests for CoChem Core Workspace Manager.
Tests atomic directory scaffolding, cross-platform locking, job provisioning,
active job detection, workspace cleanup, zombie directory sweeping,
Tripartite Air-Gap topology enforcement, permission locking, and WorkspaceDaemon.
"""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path
import pytest

from core_engine.cochem_core_workspace_manager import (
    AirgapTopology,
    DaemonStatus,
    DirectoryInfo,
    WorkspaceDaemon,
    WorkspaceManager,
    apply_tripartite_airgap,
    cleanup_job_workspace,
    file_lock,
    get_default_workspace_manager,
    get_directory_status,
    get_job_workspace,
    is_job_active,
    lock_directory_permissions,
    provision_job_workspace,
    scaffold_core_directories,
    sweep_zombie_directories,
)


def test_workspace_manager_initialization(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=str(tmp_path))
    assert manager.base_path == tmp_path.resolve()
    assert manager.lock_file == tmp_path.resolve() / ".cochem_workspace.lock"


def test_scaffold_core_directories(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
    assert success is True

    for d in WorkspaceManager.CORE_DIRECTORIES:
        expected_dir = tmp_path / d
        assert expected_dir.exists() and expected_dir.is_dir()

    assert (tmp_path / "CustomModule").exists()
    assert (tmp_path / "CustomCache").exists()


def test_provision_and_get_job_workspace(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_TEST_001"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    assert job_dir.exists()
    assert job_dir == tmp_path / "Scratch" / job_id
    assert (job_dir / ".job.lock").exists()

    retrieved = manager.get_job_workspace(job_id)
    assert retrieved == job_dir


def test_file_lock_context_manager(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    lock_file = tmp_path / "test.lock"

    with manager.file_lock(lock_file, exclusive=True) as acquired:
        assert acquired is True
        # Attempt to acquire lock on same file in non-blocking mode with 0 timeout
        with manager.file_lock(lock_file, exclusive=True, timeout=0.0) as second_acquired:
            # Second acquire should fail because lock is already held
            assert second_acquired is False

    # After exiting, lock should be free
    with manager.file_lock(lock_file, exclusive=True) as third_acquired:
        assert third_acquired is True


def test_is_job_active_and_cleanup(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ACTIVE_CHECK"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    job_lock = job_dir / ".job.lock"

    assert manager.is_job_active(job_id) is False

    # Hold the lock
    fd = os.open(str(job_lock), os.O_RDWR)
    try:
        acquired = manager._acquire_lock(fd)
        assert acquired is True
        assert manager.is_job_active(job_id) is True

        # Cleanup should fail without force
        assert manager.cleanup_job_workspace(job_id, force=False) is False
        assert job_dir.exists()
    finally:
        manager._release_lock(fd)
        os.close(fd)

    assert manager.is_job_active(job_id) is False
    # Cleanup should succeed now
    assert manager.cleanup_job_workspace(job_id, force=False) is True
    assert not job_dir.exists()


def test_sweep_zombie_directories(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Create 3 jobs:
    # 1. Zombie job without active lock
    job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
    (job1_dir / "temp_calc.dat").write_text("# ORCA calculation state payload\n! B3LYP def2-SVP\n", encoding="utf-8")

    # 2. Active job with held lock
    job2_dir = manager.provision_job_workspace("JOB_ACTIVE_2", create_job_lock=True)
    job2_lock = job2_dir / ".job.lock"
    fd2 = os.open(str(job2_lock), os.O_RDWR)
    manager._acquire_lock(fd2)

    # 3. Zombie job with no lock file at all
    job3_dir = manager.provision_job_workspace("JOB_ZOMBIE_3", create_job_lock=False)
    (job3_dir / "output.log").write_text("SCF CONVERGED IN 12 ITERATIONS\n", encoding="utf-8")

    try:
        swept = manager.sweep_zombie_directories()
        assert swept == 2

        # Job 1 and Job 3 should be swept
        assert not job1_dir.exists()
        assert not job3_dir.exists()

        # Job 2 should still exist because it was actively locked
        assert job2_dir.exists()
    finally:
        manager._release_lock(fd2)
        os.close(fd2)

    # After releasing lock, sweeping again should sweep Job 2
    swept_again = manager.sweep_zombie_directories()
    assert swept_again == 1
    assert not job2_dir.exists()


def test_get_directory_status(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Add a file in Logs
    log_file = tmp_path / "Logs" / "session.log"
    log_file.write_text("Log session line 1\nLine 2\n", encoding="utf-8")

    status = manager.get_directory_status()
    assert "Logs" in status
    assert status["Logs"]["exists"] is True
    assert status["Logs"]["file_count"] == 1
    assert status["Logs"]["total_size_bytes"] > 0
    assert "Scratch" in status
    assert status["Scratch"]["exists"] is True


def test_apply_tripartite_airgap(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    custom_code_dir = tmp_path / "CoChem_Code"
    custom_code_dir.mkdir()

    airgap = manager.apply_tripartite_airgap(code_dir=custom_code_dir)
    assert "immutable_code" in airgap
    assert "dynamic_state" in airgap
    assert "volatile_compute" in airgap
    assert airgap["immutable_code"] == str(custom_code_dir.resolve())
    assert airgap["dynamic_state"] == str(tmp_path.resolve())
    assert airgap["volatile_compute"] == str((tmp_path / "Scratch").resolve())

    # Verify all core directories exist
    for d in WorkspaceManager.CORE_DIRECTORIES:
        assert (tmp_path / d).exists()


def test_lock_directory_permissions(tmp_path: Path) -> None:
    test_dir = tmp_path / "protected_data"
    test_dir.mkdir()
    test_file = test_dir / "state.h5"
    test_file.write_bytes(b"HDF5_DATA")

    # Lock read-only
    lock_directory_permissions(test_file, read_only=True)
    mode = os.stat(test_file).st_mode
    if sys.platform == "win32":
        assert not (mode & stat.S_IWRITE)
    else:
        assert not (mode & stat.S_IWUSR)

    # Unlock read-write
    lock_directory_permissions(test_file, read_only=False)
    mode = os.stat(test_file).st_mode
    if sys.platform == "win32":
        assert bool(mode & stat.S_IWRITE)
    else:
        assert bool(mode & stat.S_IWUSR)

    # Test recursive locking on directory tree
    sub_dir = test_dir / "sub_registry"
    sub_dir.mkdir()
    sub_file = sub_dir / "config.json"
    sub_file.write_text('{"status": "protected"}', encoding="utf-8")

    lock_directory_permissions(test_dir, read_only=True, recursive=True)
    mode_sub = os.stat(sub_file).st_mode
    if sys.platform == "win32":
        assert not (mode_sub & stat.S_IWRITE)
    else:
        assert not (mode_sub & stat.S_IWUSR)

    lock_directory_permissions(test_dir, read_only=False, recursive=True)
    mode_sub = os.stat(sub_file).st_mode
    if sys.platform == "win32":
        assert bool(mode_sub & stat.S_IWRITE)
    else:
        assert bool(mode_sub & stat.S_IWUSR)


def test_scaffold_core_directories_lock_permissions(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(lock_permissions=True)
    assert success is True
    assert (tmp_path / "Databases").exists()


def test_sweep_zombie_directories_grace_period(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_dir = manager.provision_job_workspace("JOB_GRACE_PERIOD", create_job_lock=False)
    assert job_dir.exists()

    # With high grace period (e.g. 100s), newly created job must NOT be swept
    swept = manager.sweep_zombie_directories(grace_period_seconds=100.0)
    assert swept == 0
    assert job_dir.exists()

    # With 0 grace period, newly created unlocked job is swept
    swept_now = manager.sweep_zombie_directories(grace_period_seconds=0.0)
    assert swept_now == 1
    assert not job_dir.exists()


def test_acquire_lock_timeout(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    test_file = tmp_path / "timeout_test.lock"
    fd1 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    fd2 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    try:
        acquired1 = manager._acquire_lock(fd1, exclusive=True, timeout=0.0)
        assert acquired1 is True

        start = time.time()
        acquired2 = manager._acquire_lock(fd2, exclusive=True, timeout=0.05)
        elapsed = time.time() - start
        assert acquired2 is False
        assert elapsed >= 0.04
    finally:
        manager._release_lock(fd1)
        os.close(fd1)
        os.close(fd2)


def test_workspace_daemon_lifecycle(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    daemon = WorkspaceDaemon(manager=manager, sweep_interval_seconds=0.1)

    assert daemon.get_status().is_running is False

    # Execute single run
    res = daemon.run_once()
    assert res["cycle"] == 1
    assert res["zombies_swept"] == 0
    assert "airgap_topology" in res
    assert "directory_status" in res

    # Start background daemon
    daemon.start()
    assert daemon.get_status().is_running is True
    time.sleep(0.35)
    daemon.stop()

    status = daemon.get_status()
    assert status.is_running is False
    assert status.sweeps_completed >= 2


def test_workspace_daemon_run_async(tmp_path: Path) -> None:
    import asyncio

    async def _run() -> None:
        manager = WorkspaceManager(base_path=tmp_path)
        daemon = WorkspaceDaemon(manager=manager, sweep_interval_seconds=0.05)

        task = asyncio.create_task(daemon.run_async())
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert daemon.sweeps_completed >= 1

    asyncio.run(_run())


def test_module_level_helpers(tmp_path: Path) -> None:
    manager = get_default_workspace_manager()
    assert isinstance(manager, WorkspaceManager)

    # Test file_lock helper
    test_lock = tmp_path / "helper.lock"
    with file_lock(test_lock, exclusive=True) as ok:
        assert ok is True

    # Test module-level scaffold, provision, get, is_active, cleanup, status, airgap, sweep
    scaffold_ok = scaffold_core_directories()
    assert isinstance(scaffold_ok, bool)

    prov_path = provision_job_workspace("JOB_HELPER_TEST", create_job_lock=True)
    assert prov_path.exists()
    assert get_job_workspace("JOB_HELPER_TEST") == prov_path
    assert is_job_active("JOB_HELPER_TEST") is False

    status = get_directory_status()
    assert isinstance(status, dict)

    airgap = apply_tripartite_airgap()
    assert "immutable_code" in airgap

    cleaned = cleanup_job_workspace("JOB_HELPER_TEST")
    assert cleaned is True

    swept = sweep_zombie_directories(grace_period_seconds=0.0)
    assert isinstance(swept, int)


def test_pydantic_models() -> None:
    d_info = DirectoryInfo(
        path="/tmp/test",
        exists=True,
        file_count=5,
        dir_count=2,
        total_size_bytes=1024,
        is_writable=True,
        is_readable=True,
    )
    assert d_info.file_count == 5
    assert d_info.model_dump()["exists"] is True

    topo = AirgapTopology(
        immutable_code="/repo",
        dynamic_state="/data",
        volatile_compute="/scratch",
        code_tier="/repo",
        data_tier="/data",
        compute_tier="/scratch",
    )
    assert topo.status == "active"

    d_status = DaemonStatus(
        is_running=True,
        interval_seconds=60.0,
        sweeps_completed=10,
        last_sweep_timestamp=time.time(),
        last_zombies_swept=3,
    )
    assert d_status.sweeps_completed == 10
