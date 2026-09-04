import os
import sys
import time
import threading
import numpy as np
import pytest
from pathlib import Path

from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem.core.ipc.serializer import SharedMemoryBuffer, SharedMemoryView
from cochem.core.context import FileLock


def test_safe_subprocess_run_tripartite_airgap_and_streaming(tmp_path):
    """Validates Suggestion #73: Subprocess executes in isolated scratch directory,
    streams stdout to disk, and executes live telemetry line callbacks.
    """
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()

    # Script that emits 10 lines with small pauses
    script = (
        "import sys, time\n"
        "for i in range(10):\n"
        "    print(f'SCF ITERATION {i}: ENERGY = {-76.0 - i*0.01}', flush=True)\n"
        "    time.sleep(0.01)\n"
    )
    script_file = scratch_dir / "runner.py"
    script_file.write_text(script, encoding="utf-8")

    captured_lines = []
    def on_line(line: str):
        captured_lines.append(line.strip())

    res = safe_subprocess_run(
        cmd=[sys.executable, str(script_file)],
        cwd=scratch_dir,
        stream_to_disk=True,
        on_stdout_line=on_line,
        tail_buffer_lines=5,
    )

    assert res.returncode == 0
    assert len(captured_lines) == 10
    assert "SCF ITERATION 0" in captured_lines[0]
    assert "SCF ITERATION 9" in captured_lines[-1]

    # Verify log file was written to disk
    stdout_log = scratch_dir / "process_stdout.log"
    assert stdout_log.exists()
    assert stdout_log.stat().st_size > 0


def test_shared_memory_zero_copy_view_and_cleanup():
    """Validates Suggestion #74: SharedMemoryBuffer maps array view without copying
    and cleans up OS descriptors deterministically.
    """
    arr = np.linspace(1.0, 1000.0, 100000, dtype=np.float64)
    buffer = SharedMemoryBuffer.create(arr)
    descriptor = buffer.to_descriptor()

    # Map zero-copy view
    view = SharedMemoryBuffer.read_from_descriptor(descriptor, zero_copy=True)
    assert isinstance(view, SharedMemoryView)

    with view as mapped_arr:
        # Verify it points to the exact same shared memory segment
        assert np.may_share_memory(mapped_arr, buffer.array)
        assert np.array_equal(mapped_arr[:10], arr[:10])
        # In-place modification reflects in shared memory
        mapped_arr[0] = 9999.0
        assert buffer.array[0] == 9999.0

    # View should be closed after exiting context manager
    with pytest.raises(RuntimeError, match="Cannot access array view on a closed"):
        _ = view.array

    buffer.close()
    buffer.unlink()


def test_filelock_adaptive_backoff_and_contention(tmp_path):
    """Validates Suggestion #76: FileLock adaptive exponential backoff acquires rapidly
    in low contention and handles heavy multi-threaded contention without deadlock.
    """
    lock_file = tmp_path / "test_concurrency.lock"
    lock1 = FileLock(lock_file, timeout_sec=5.0)

    # 1. Rapid acquisition latency check (< 10 ms instead of 50 ms)
    t0 = time.perf_counter()
    assert lock1.acquire() is True
    lock1.release()
    t1 = time.perf_counter()
    assert (t1 - t0) < 0.02, f"Uncontended lock acquisition took too long: {t1 - t0:.4f}s"

    # 2. Multi-threaded contention test
    counter = {"value": 0}
    n_threads = 5
    increments_per_thread = 20

    def worker():
        w_lock = FileLock(lock_file, timeout_sec=10.0)
        for _ in range(increments_per_thread):
            if w_lock.acquire(initial_delay_sec=0.001, max_delay_sec=0.015, jitter=True):
                try:
                    c = counter["value"]
                    time.sleep(0.0005)
                    counter["value"] = c + 1
                finally:
                    w_lock.release()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter["value"] == n_threads * increments_per_thread
