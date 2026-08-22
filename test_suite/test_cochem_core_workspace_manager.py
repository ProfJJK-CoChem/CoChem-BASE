"""
Unit and integration tests for CoChem Core Workspace Manager.
Tests atomic directory scaffolding, cross-platform locking, job provisioning,
active job detection, workspace cleanup, and zombie directory sweeping.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import pytest

from core_engine.cochem_core_workspace_manager import WorkspaceManager


def test_workspace_manager_initialization(tmp_path: Path):
    manager = WorkspaceManager(base_path=str(tmp_path))
    assert manager.base_path == tmp_path.resolve()
    assert manager.lock_file == tmp_path.resolve() / ".cochem_workspace.lock"


def test_scaffold_core_directories(tmp_path: Path):
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
    assert success is True

    for d in WorkspaceManager.CORE_DIRECTORIES:
        expected_dir = tmp_path / d
        assert expected_dir.exists() and expected_dir.is_dir()

    assert (tmp_path / "CustomModule").exists()
    assert (tmp_path / "CustomCache").exists()


def test_provision_and_get_job_workspace(tmp_path: Path):
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_TEST_001"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    assert job_dir.exists()
    assert job_dir == tmp_path / "Scratch" / job_id
    assert (job_dir / ".job.lock").exists()

    retrieved = manager.get_job_workspace(job_id)
    assert retrieved == job_dir


def test_file_lock_context_manager(tmp_path: Path):
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


def test_is_job_active_and_cleanup(tmp_path: Path):
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


def test_sweep_zombie_directories(tmp_path: Path):
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Create 3 jobs:
    # 1. Zombie job without active lock
    job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
    (job1_dir / "temp_calc.dat").write_text("dummy", encoding="utf-8")

    # 2. Active job with held lock
    job2_dir = manager.provision_job_workspace("JOB_ACTIVE_2", create_job_lock=True)
    job2_lock = job2_dir / ".job.lock"
    fd2 = os.open(str(job2_lock), os.O_RDWR)
    manager._acquire_lock(fd2)

    # 3. Zombie job with no lock file at all
    job3_dir = manager.provision_job_workspace("JOB_ZOMBIE_3", create_job_lock=False)
    (job3_dir / "output.log").write_text("data", encoding="utf-8")

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


def test_get_directory_status(tmp_path: Path):
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
