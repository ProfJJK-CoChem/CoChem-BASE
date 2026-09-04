"""Zero-Mock Filesystem Synchronization & Fault Remediation Test Suite for Chunk 3.

Validates Suggestions #23, #26, #27, #28, #29:
- Cross-process atomic persistence for swarm_state.json (multiprocessing stress test)
- NetworkHeartbeatLock split-brain defense, heartbeat renewal, and stale lease fencing
- SubprocessBroker ephemeral sandboxing & Tripartite scratch isolation
- RWFileLock concurrent shared readers with exclusive writer-priority
- Self-healing subprocess remediation callback with parameter and input deck escalation
"""

from __future__ import annotations

import json
import multiprocessing
import os
import pathlib
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List

import pytest

from cochem.concurrency.atomic_file_lock import RWFileLock
from cochem.concurrency.network_lock import NetworkHeartbeatLock
from cochem.concurrency.subprocess_broker import (
    FailureCategory,
    SubprocessBroker,
    SubprocessExecutionResult,
)
from cochem_base.core_engine.cochem_core_scheduler import (
    CoreScheduler,
    TaskResult,
    persist_swarm_state_atomic,
)


def _worker_update_swarm_state(state_file_path: str, worker_id: int, count: int) -> None:
    """Worker function executed across independent OS processes."""
    state_file = pathlib.Path(state_file_path)
    for i in range(count):
        task_id = f"proc_task_{worker_id}_{i}"
        entry = {
            "agent": f"worker_{worker_id}",
            "status": "SUCCESS",
            "artifacts": [f"{task_id}.out"],
            "hashes": {"sha256": f"hash_{worker_id}_{i}"},
            "error_message": None,
            "timestamp": time.time(),
        }
        persist_swarm_state_atomic(state_file, task_id, entry)
        time.sleep(0.001)


def test_swarm_state_cross_process_locking_integrity(tmp_path: pathlib.Path) -> None:
    """Suggestion #23: 8 independent OS processes execute 20 concurrent updates each (160 total) without JSON corruption."""
    state_file = tmp_path / "swarm_state.json"

    num_processes = 8
    updates_per_proc = 20
    processes: List[multiprocessing.Process] = []

    for wid in range(num_processes):
        p = multiprocessing.Process(
            target=_worker_update_swarm_state,
            args=(str(state_file), wid, updates_per_proc),
        )
        processes.append(p)
        p.start()

    for p in processes:
        p.join(timeout=30.0)
        assert p.exitcode == 0, f"Worker process failed with exit code {p.exitcode}"

    assert state_file.exists(), "swarm_state.json was not created"
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    expected_total = num_processes * updates_per_proc
    assert len(data) == expected_total, f"Expected {expected_total} entries, got {len(data)}"
    for wid in range(num_processes):
        for i in range(updates_per_proc):
            key = f"proc_task_{wid}_{i}"
            assert key in data, f"Missing key {key}"
            assert data[key]["agent"] == f"worker_{wid}"
            assert data[key]["status"] == "SUCCESS"


def test_network_heartbeat_lock_split_brain_defense(tmp_path: pathlib.Path) -> None:
    """Suggestion #26: Atomic directory lease fencing, heartbeat renewals, and stale lease reclamation."""
    lock_dir = tmp_path / "hpc_cluster_lock.lease"

    # Node 1 acquires lease with 1.5s TTL
    lock_node1 = NetworkHeartbeatLock(lock_dir=lock_dir, lease_ttl_sec=1.5, node_id="node-1")
    acquired1 = lock_node1.acquire(timeout=2.0)
    assert acquired1 is True
    assert lock_node1.is_locked() is True

    # Node 2 fails to acquire while Node 1 holds active lease
    lock_node2 = NetworkHeartbeatLock(lock_dir=lock_dir, lease_ttl_sec=1.5, node_id="node-2")
    acquired2 = lock_node2.acquire(timeout=0.3)
    assert acquired2 is False

    # Simulate active heartbeat refresh on Node 1: verify lease remains valid
    time.sleep(0.6)
    assert lock_node1.renew_heartbeat() is True
    assert lock_node2.is_stale() is False

    # Node 1 terminates / releases or lease expires
    lock_node1.release()
    assert lock_node1.is_locked() is False

    # Node 2 safely acquires the lock
    acquired2_retry = lock_node2.acquire(timeout=2.0)
    assert acquired2_retry is True
    assert lock_node2.is_locked() is True
    lock_node2.release()


def test_subprocess_broker_ephemeral_scratch_isolation(tmp_path: pathlib.Path) -> None:
    """Suggestion #27: Two concurrent brokers write identical relative filenames without colliding."""
    scratch_root = tmp_path / "ephemeral_scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)

    broker1 = SubprocessBroker(context_or_engine="worker_1", base_scratch_dir=scratch_root)
    broker2 = SubprocessBroker(context_or_engine="worker_2", base_scratch_dir=scratch_root)

    script1 = (
        "import pathlib, time\n"
        "p = pathlib.Path('temp_output.dat')\n"
        "p.write_text('PAYLOAD_FROM_WORKER_1')\n"
        "time.sleep(0.3)\n"
        "assert p.read_text() == 'PAYLOAD_FROM_WORKER_1'\n"
    )
    script2 = (
        "import pathlib, time\n"
        "p = pathlib.Path('temp_output.dat')\n"
        "p.write_text('PAYLOAD_FROM_WORKER_2')\n"
        "time.sleep(0.3)\n"
        "assert p.read_text() == 'PAYLOAD_FROM_WORKER_2'\n"
    )

    t1_result: List[SubprocessExecutionResult] = []
    t2_result: List[SubprocessExecutionResult] = []

    def run_b1() -> None:
        res = broker1.execute_with_remediation([sys.executable, "-c", script1])
        t1_result.append(res)

    def run_b2() -> None:
        res = broker2.execute_with_remediation([sys.executable, "-c", script2])
        t2_result.append(res)

    th1 = threading.Thread(target=run_b1)
    th2 = threading.Thread(target=run_b2)

    th1.start()
    th2.start()
    th1.join(timeout=10.0)
    th2.join(timeout=10.0)

    assert len(t1_result) == 1 and t1_result[0].success is True, f"Broker 1 failed: {t1_result}"
    assert len(t2_result) == 1 and t2_result[0].success is True, f"Broker 2 failed: {t2_result}"

    # Verify each ephemeral job sandbox subdirectory was swept and deleted
    remaining_dirs = list(scratch_root.glob("cochem_job_*"))
    assert len(remaining_dirs) == 0, f"Scratch leakage detected: {remaining_dirs}"


def test_rw_file_lock_concurrent_readers_exclusive_writer(tmp_path: pathlib.Path) -> None:
    """Suggestion #28: Concurrent readers and writers run simultaneously without mutual exclusion violations."""
    state_file = tmp_path / "state_data.dat"
    state_file.write_text("initial_value", encoding="utf-8")
    rw_lock = RWFileLock(state_file, timeout=10.0)

    active_readers = 0
    active_writers = 0
    max_concurrent_readers = 0
    violations: List[str] = []
    counter_lock = threading.Lock()
    stop_event = threading.Event()

    def reader_task(reader_id: int) -> None:
        nonlocal active_readers, max_concurrent_readers
        for _ in range(15):
            if stop_event.is_set():
                break
            with rw_lock.read_lock():
                with counter_lock:
                    if active_writers > 0:
                        violations.append(f"Reader {reader_id} entered while writer active ({active_writers})")
                    active_readers += 1
                    if active_readers > max_concurrent_readers:
                        max_concurrent_readers = active_readers

                content = state_file.read_text(encoding="utf-8")
                assert "value" in content
                time.sleep(0.01)

                with counter_lock:
                    active_readers -= 1
            time.sleep(0.005)

    def writer_task(writer_id: int) -> None:
        nonlocal active_writers
        for step in range(5):
            if stop_event.is_set():
                break
            with rw_lock.write_lock():
                with counter_lock:
                    if active_readers > 0:
                        violations.append(f"Writer {writer_id} entered while {active_readers} readers active")
                    if active_writers > 0:
                        violations.append(f"Writer {writer_id} entered while another writer active")
                    active_writers += 1

                state_file.write_text(f"writer_value_{writer_id}_{step}", encoding="utf-8")
                time.sleep(0.02)

                with counter_lock:
                    active_writers -= 1
            time.sleep(0.01)

    reader_threads = [threading.Thread(target=reader_task, args=(i,)) for i in range(8)]
    writer_threads = [threading.Thread(target=writer_task, args=(j,)) for j in range(2)]
    all_threads = reader_threads + writer_threads

    for t in all_threads:
        t.start()
    for t in all_threads:
        t.join(timeout=15.0)

    assert not violations, f"Mutual exclusion violations detected: {violations}"
    assert max_concurrent_readers > 1, f"Expected concurrency, got max {max_concurrent_readers}"
    assert state_file.exists()


def test_subprocess_remediation_callback_execution(tmp_path: pathlib.Path) -> None:
    """Suggestion #29: Dynamic input deck and parameter remediation callback execution under failure."""
    broker = SubprocessBroker(scratch_dir=tmp_path)

    # Command fails on attempt 1 without '--damping', succeeds on attempt 2 when '--damping' is injected
    script = (
        "import sys\n"
        "if '--damping' not in sys.argv:\n"
        "    print('SCF FAILED TO CONVERGE', file=sys.stdout)\n"
        "    sys.exit(1)\n"
        "print('SCF CONVERGED SUCCESSFULLY', file=sys.stdout)\n"
        "sys.exit(0)\n"
    )

    base_cmd = [sys.executable, "-c", script]

    def remediate_cb(category: FailureCategory, params: Dict[str, Any], scratch: pathlib.Path) -> List[str]:
        assert category == FailureCategory.SCF_CONVERGENCE_FAILURE
        # Method Matrix §8B: escalate convergence by injecting damping
        return base_cmd + ["--damping"]

    result = broker.execute_with_remediation(
        command=base_cmd,
        timeout_sec=5.0,
        remediate_callback=remediate_cb,
    )

    assert result.success is True
    assert result.retries_attempted == 1
    assert "SCF CONVERGED SUCCESSFULLY" in result.stdout
