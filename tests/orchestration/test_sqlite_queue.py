"""Unit tests for centralized SQLite task and job queue engine.

Verifies WAL mode pragmas, atomic leasing, priority scheduling, failure retries,
heartbeat liveness, orphan reclamation, and multi-process race safety.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue


def test_sqlite_queue_pragmas(tmp_path: Path) -> None:
    """Verify SQLite connection applies required WAL and durability pragmas."""
    db_file = tmp_path / "tasks.db"
    with SQLiteTaskQueue(db_file) as queue:
        cursor = queue._conn.cursor()
        jm = cursor.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(jm).lower() == "wal"

        bt = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert int(bt) >= 5000

        sync = cursor.execute("PRAGMA synchronous;").fetchone()[0]
        assert int(sync) == 1  # NORMAL

        fk = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert int(fk) == 1  # ON


def test_enqueue_and_lease_lifecycle(tmp_path: Path) -> None:
    """Verify priority-ordered leasing, payload integrity, and completion lifecycle."""
    db_file = tmp_path / "lifecycle.db"
    with SQLiteTaskQueue(db_file) as queue:
        low_id = queue.enqueue_task(
            task_type="qm_opt",
            payload={"system": "water", "method": "b3lyp"},
            priority=1,
        )
        high_id = queue.enqueue_task(
            task_type="qm_freq",
            payload={"system": "benzene", "method": "wb97x-d"},
            priority=10,
        )

        # High priority task should be leased first
        leased1 = queue.lease_task(worker_pid=1001, worker_host="node01")
        assert leased1 is not None
        assert leased1.task_id == high_id
        assert leased1.state == "RUNNING"
        assert leased1.locked_by_pid == 1001
        assert leased1.locked_by_host == "node01"
        assert leased1.payload["system"] == "benzene"

        # Update heartbeat
        assert queue.heartbeat(high_id, worker_pid=1001) is True
        assert queue.heartbeat(high_id, worker_pid=9999) is False  # Wrong PID

        # Complete high priority task
        queue.complete_task(high_id, result={"energy": -232.15, "converged": True})
        completed_record = queue.get_task(high_id)
        assert completed_record is not None
        assert completed_record.state == "COMPLETED"
        assert completed_record.result is not None
        assert completed_record.result["converged"] is True

        # Next lease retrieves lower priority task
        leased2 = queue.lease_task(worker_pid=1002, worker_host="node02")
        assert leased2 is not None
        assert leased2.task_id == low_id

        # Queue is now empty
        leased3 = queue.lease_task(worker_pid=1003, worker_host="node03")
        assert leased3 is None


def test_task_failure_and_retries(tmp_path: Path) -> None:
    """Verify task failure increments retry count and marks FAILED upon exhausting max_retries."""
    db_file = tmp_path / "retries.db"
    with SQLiteTaskQueue(db_file) as queue:
        task_id = queue.enqueue_task(
            task_type="orca_scf",
            payload={"basis": "def2-tzvp"},
            max_retries=2,
        )

        # First failure -> reset to PENDING with retry_count=1
        task = queue.lease_task(worker_pid=2001, worker_host="node01")
        assert task is not None
        queue.fail_task(task_id, error_message="SCF failed to converge", can_retry=True)

        rec1 = queue.get_task(task_id)
        assert rec1 is not None
        assert rec1.state == "PENDING"
        assert rec1.retry_count == 1
        assert rec1.locked_by_pid is None

        # Second failure -> exhausted max_retries=2 -> transition to FAILED
        task_retry = queue.lease_task(worker_pid=2002, worker_host="node01")
        assert task_retry is not None
        queue.fail_task(task_id, error_message="SCF diverged again", can_retry=True)

        rec2 = queue.get_task(task_id)
        assert rec2 is not None
        assert rec2.state == "FAILED"
        assert rec2.retry_count == 2
        assert "SCF diverged again" in str(rec2.error_message)


def test_reclaim_orphaned_tasks(tmp_path: Path) -> None:
    """Verify watchdog reclaims running tasks whose heartbeats have expired."""
    db_file = tmp_path / "orphans.db"
    with SQLiteTaskQueue(db_file) as queue:
        task_id = queue.enqueue_task(
            task_type="crest_search",
            payload={"conformers": 50},
            max_retries=3,
        )
        queue.lease_task(worker_pid=3001, worker_host="node01")

        # Manually backdate heartbeat timestamp beyond grace period (40s ago)
        expired_ts = time.time() - 40.0
        queue._conn.execute(
            "UPDATE tasks SET heartbeat_ts = ? WHERE task_id = ?;",
            (expired_ts, task_id),
        )

        reclaimed = queue.reclaim_orphaned_tasks(timeout_grace_sec=30.0)
        assert task_id in reclaimed

        reclaimed_record = queue.get_task(task_id)
        assert reclaimed_record is not None
        assert reclaimed_record.state == "PENDING"
        assert reclaimed_record.retry_count == 1
        assert reclaimed_record.locked_by_pid is None


def test_concurrent_task_leasing(tmp_path: Path) -> None:
    """Verify zero duplicate task allocations under concurrent multi-process leasing."""
    db_file = tmp_path / "concurrency.db"
    with SQLiteTaskQueue(db_file) as queue:
        for i in range(12):
            queue.enqueue_task(task_type="batch_job", payload={"index": i})

    repo_dir = str(Path(__file__).resolve().parent.parent.parent)
    src_dir = str(Path(__file__).resolve().parent.parent.parent / "src")
    worker_code = (
        "import os, sys, time\n"
        f"sys.path.insert(0, r'{repo_dir}')\n"
        f"sys.path.insert(0, r'{src_dir}')\n"
        "from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue\n"
        "db_path = sys.argv[1]\n"
        "worker_name = sys.argv[2]\n"
        "leased_ids = []\n"
        "with SQLiteTaskQueue(db_path) as queue:\n"
        "    while True:\n"
        "        t = queue.lease_task(worker_pid=os.getpid(), worker_host=worker_name)\n"
        "        if t is None:\n"
        "            break\n"
        "        leased_ids.append(t.task_id)\n"
        "        time.sleep(0.01)\n"
        "print(','.join(leased_ids))\n"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{repo_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"

    proc1 = subprocess.run(
        [sys.executable, "-c", worker_code, str(db_file), "W1"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    proc2 = subprocess.run(
        [sys.executable, "-c", worker_code, str(db_file), "W2"],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    ids1 = [x for x in proc1.stdout.strip().split(",") if x]
    ids2 = [x for x in proc2.stdout.strip().split(",") if x]

    total_leased = ids1 + ids2
    assert len(total_leased) == 12
    # Ensure mutually exclusive leases
    assert len(set(total_leased)) == 12
    assert set(ids1).isdisjoint(set(ids2))
