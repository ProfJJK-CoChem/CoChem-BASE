"""Zero-Mock Concurrency & Process Containment Test Suite for Chunk 3.

Validates Suggestions #21, #22, #24, #25, #30:
- Thread-safe process tree management & atomic snapshot iteration in ProcessTreeManager
- Thread-safe queue and event-driven worker saturation in CoreScheduler (>50 tasks/s)
- Win32 kernel handle RAII hygiene & leak prevention
- Dynamic host threading contention budgeting and GPU MPS apportionment
- Verified process demise, escalated SIGKILL, and ghost process telemetry
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, List

import psutil
import pytest

from cochem.core.hardware.topology import TopologyDiscoveryEngine
from cochem.core.process_reaper import (
    ProcessReapTimeoutError,
    ProcessTreeManager,
    ZombieReaperDaemon,
)
from cochem_base.core_engine.cochem_core_scheduler import (
    CoreScheduler,
    TaskConfig,
)


def test_process_tree_manager_thread_safety_during_sweep() -> None:
    """Suggestion #21: Verify thread-safe process registration/unregistration during active sweeps."""
    manager = ProcessTreeManager()
    daemon = ZombieReaperDaemon(tree_manager=manager, interval_sec=0.01)

    errors: List[Exception] = []
    stop_event = threading.Event()
    registration_count = 0
    lock = threading.Lock()

    procs: List[subprocess.Popen[Any]] = []
    try:
        for _ in range(5):
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
            procs.append(p)

        def worker(worker_id: int) -> None:
            nonlocal registration_count
            while not stop_event.is_set():
                p = procs[worker_id % len(procs)]
                try:
                    manager.register_process(p.pid, task_id=f"task_{worker_id}")
                    with lock:
                        registration_count += 1
                        if registration_count >= 1000:
                            stop_event.set()
                            break
                    time.sleep(0.0005)
                    manager.unregister_process(p.pid)
                except Exception as exc:
                    errors.append(exc)
                    stop_event.set()
                    break

        def sweeper() -> None:
            while not stop_event.is_set():
                try:
                    daemon.sweep_orphans()
                except Exception as exc:
                    errors.append(exc)
                    stop_event.set()
                    break
                time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        sweep_thread = threading.Thread(target=sweeper)

        sweep_thread.start()
        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=15.0)
        stop_event.set()
        sweep_thread.join(timeout=5.0)

        assert not errors, f"Thread safety errors during sweep: {errors}"
        assert registration_count >= 1000
    finally:
        for p in procs:
            if psutil.pid_exists(p.pid):
                manager.terminate_tree(p.pid, grace_timeout_sec=0.5)


def test_core_scheduler_queue_throughput_and_zero_latency(tmp_path: Path) -> None:
    """Suggestion #22: Verify thread-safe queue dispatch saturates workers (>50 tasks/s) without 500ms delay."""
    scheduler = CoreScheduler(max_workers=16, project_root=tmp_path)
    scheduler.start_scheduling()

    num_tasks = 50
    t0 = time.perf_counter()

    for i in range(num_tasks):
        config = TaskConfig(
            task_id=f"throughput_task_{i}",
            command=[sys.executable, "-c", "import sys; sys.exit(0)"],
            timeout_seconds=10,
        )
        scheduler.add_task(config)

    deadline = time.perf_counter() + 10.0
    while time.perf_counter() < deadline:
        statuses = [scheduler.get_task_status(f"throughput_task_{i}") for i in range(num_tasks)]
        if all(s is not None and s.status in ("completed", "failed") for s in statuses):
            break
        time.sleep(0.005)

    t_elapsed = time.perf_counter() - t0
    scheduler.stop_scheduling()

    statuses = [scheduler.get_task_status(f"throughput_task_{i}") for i in range(num_tasks)]
    completed = [s for s in statuses if s is not None and s.status == "completed"]
    assert len(completed) == num_tasks, f"Only {len(completed)}/{num_tasks} tasks completed"

    dispatch_throughput = num_tasks / t_elapsed
    assert dispatch_throughput > 50.0, f"Throughput {dispatch_throughput:.1f} tasks/s too slow (elapsed: {t_elapsed:.2f}s)"
    assert t_elapsed < 5.0, f"Execution took too long: {t_elapsed:.2f}s"


def test_win32_kernel_handle_leak_prevention() -> None:
    """Suggestion #24: Verify Win32 OpenProcess handle RAII cleanup prevents monotonic handle growth."""
    if sys.platform != "win32":
        pytest.skip("Win32 kernel handle test is Windows-specific")

    manager = ProcessTreeManager()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        current_proc = psutil.Process()
        # Warmup registration
        for _ in range(20):
            manager.register_process(proc.pid)
            manager.unregister_process(proc.pid)

        initial_handles = current_proc.num_handles()

        for _ in range(500):
            manager.register_process(proc.pid)
            manager.unregister_process(proc.pid)

        final_handles = current_proc.num_handles()
        handle_delta = final_handles - initial_handles
        # Strict RAII: handle count must not grow by hundreds
        assert handle_delta <= 10, (
            f"Win32 process handle leak detected: initial={initial_handles}, "
            f"final={final_handles}, delta={handle_delta}"
        )
    finally:
        if psutil.pid_exists(proc.pid):
            manager.terminate_tree(proc.pid, grace_timeout_sec=0.5)


def test_topology_contention_budgeting() -> None:
    """Suggestion #25: Verify dynamic host thread budgeting per worker and MPS apportionment."""
    engine = TopologyDiscoveryEngine()
    topo = engine.discover_topology(concurrent_workers=4)

    expected_threads = max(1, topo.anchor_cores // 4)
    worker_env = engine.get_worker_env(concurrent_workers=4, worker_index=1)

    assert worker_env["OMP_NUM_THREADS"] == str(expected_threads)
    assert worker_env["MKL_NUM_THREADS"] == str(expected_threads)
    assert worker_env["OPENBLAS_NUM_THREADS"] == str(expected_threads)
    assert worker_env["VECLIB_MAXIMUM_THREADS"] == str(expected_threads)
    assert worker_env["NUMEXPR_NUM_THREADS"] == str(expected_threads)

    # NVIDIA MPS active thread percentage for 4 workers = 100 // 4 = 25
    assert worker_env.get("CUDA_MPS_ACTIVE_THREAD_PERCENTAGE") == "25"


def test_verified_process_demise_escalation() -> None:
    """Suggestion #30: Verify process reaper escalates to SIGKILL / Job Object termination for stubborn processes."""
    manager = ProcessTreeManager()

    # Launch a process that ignores SIGTERM
    script = (
        "import signal, time, sys\n"
        "def handler(signum, frame):\n"
        "    return None\n"
        "try:\n"
        "    signal.signal(signal.SIGTERM, handler)\n"
        "except Exception:\n"
        "    sys.stderr.write('Signal setup error\\n')\n"
        "time.sleep(15)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", script])
    pid = proc.pid
    manager.register_process(pid)

    time.sleep(0.2)
    assert manager.is_alive(pid)

    metrics = manager.terminate_tree(pid, grace_timeout_sec=0.5)
    assert metrics["success"] is True
    assert metrics["pid"] == pid
    assert not psutil.pid_exists(pid)
    assert manager.is_alive(pid) is False
