"""Unit tests for cross-platform process lifecycle manager and zombie reaper.

Verifies PID/PPID/create_time tracking, progressive escalation (terminate -> kill),
telemetry metric collection, orphan classification, and SQLite task failure transitions.
"""

import subprocess
import sys
import time
from pathlib import Path

import psutil

from src.cochem.core.process_reaper import ProcessTreeManager, ZombieReaperDaemon
from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue


def test_process_tree_manager_registration() -> None:
    """Verify registration, create_time recording, and liveness polling."""
    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])

    try:
        meta = manager.register_process(proc.pid, task_id="test_task_001")
        assert meta.pid == proc.pid
        assert meta.task_id == "test_task_001"
        assert meta.create_time > 0.0
        assert manager.is_alive(proc.pid) is True
    finally:
        metrics = manager.terminate_tree(proc.pid, grace_timeout_sec=2.0)
        assert metrics["success"] is True
        assert manager.is_alive(proc.pid) is False


def test_process_tree_manager_termination_escalation() -> None:
    """Verify progressive escalation cleanly terminates stubborn subprocesses."""
    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])

    _ = manager.register_process(proc.pid)
    time.sleep(0.1)

    metrics = manager.terminate_tree(proc.pid, grace_timeout_sec=1.0)
    assert metrics["success"] is True
    assert metrics["pid"] == proc.pid
    assert "cpu_time" in metrics
    assert "resident_memory_mb" in metrics

    # Process must be gone from OS
    assert not psutil.pid_exists(proc.pid) or psutil.Process(proc.pid).status() == psutil.STATUS_ZOMBIE


def test_zombie_reaper_orphan_sweep_and_task_failure(tmp_path: Path) -> None:
    """Verify reaper sweeps orphaned processes and marks associated task as FAILED in queue."""
    db_file = tmp_path / "reaper_test.db"
    with SQLiteTaskQueue(db_file) as queue:
        task_id = queue.enqueue_task(task_type="qm_opt", payload={"molecule": "ethanol"})
        task = queue.lease_task(worker_pid=1234, worker_host="local")
        assert task is not None

        manager = ProcessTreeManager()
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(15)"])

        try:
            manager.register_process(proc.pid, task_id=task_id)

            # Configure reaper with a non-existent parent PID to classify proc as orphan
            reaper = ZombieReaperDaemon(
                queue=queue,
                tree_manager=manager,
                parent_pid=99999999,
                grace_period_sec=10.0,
            )

            assert reaper.is_orphan(proc.pid) is True

            terminated = reaper.sweep_orphans()
            assert proc.pid in terminated

            # Verify associated task state transitioned to PENDING with incremented retry_count
            failed_task = queue.get_task(task_id)
            assert failed_task is not None
            assert failed_task.state == "PENDING"
            assert failed_task.retry_count == 1
            assert "orphaned and terminated" in str(failed_task.error_message)

        finally:
            if psutil.pid_exists(proc.pid):
                manager.terminate_tree(proc.pid)
