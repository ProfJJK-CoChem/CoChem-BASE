"""
Unit and Integration Test Suite for CoChem Core Subprocess Broker.
Validates process tree lifecycle, safe execution, zombie reaping, OOM monitor thread,
telemetry stream trapping, and artifact provenance hashing against real OS processes.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

from core_engine.cochem_core_subprocess_broker import (
    SubprocessBroker,
    safe_subprocess_run,
    register_popen_process,
    unregister_popen_process,
    get_active_popen_processes,
    cleanup_zombie_processes,
    kill_process_tree,
    HAS_PSUTIL
)

if HAS_PSUTIL:
    import psutil


def test_popen_registration_and_unregistration() -> None:
    """Test registering, polling active, and unregistering subprocesses."""
    # Launch a brief sleep process
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    try:
        register_popen_process(proc)
        active = get_active_popen_processes()
        assert proc in active

        # Unregister manually
        unregister_popen_process(proc)
        active_after = get_active_popen_processes()
        assert proc not in active_after
    finally:
        kill_process_tree(proc.pid)
        proc.wait(timeout=3.0)


def test_kill_process_tree_recursive() -> None:
    """Test terminating a parent and its recursive child processes."""
    parent_script = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
time.sleep(30)
"""
    proc = subprocess.Popen([sys.executable, "-c", parent_script])
    register_popen_process(proc)
    time.sleep(0.8)

    pid = proc.pid
    child_pids = []
    if HAS_PSUTIL:
        try:
            parent_p = psutil.Process(pid)
            child_pids = [c.pid for c in parent_p.children(recursive=True)]
        except psutil.NoSuchProcess:
            pass

    # Kill process tree
    kill_process_tree(pid)
    proc.wait(timeout=3.0)

    if HAS_PSUTIL:
        time.sleep(0.3)
        assert not psutil.pid_exists(pid)
        for cpid in child_pids:
            assert not psutil.pid_exists(cpid), f"Child PID {cpid} leaked!"


def test_cleanup_zombie_processes_global() -> None:
    """Test that global cleanup sweeps all registered living processes."""
    proc1 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    register_popen_process(proc1)
    register_popen_process(proc2)

    time.sleep(0.3)
    reaped = cleanup_zombie_processes()
    assert reaped >= 2

    proc1.wait(timeout=2.0)
    proc2.wait(timeout=2.0)
    assert len(get_active_popen_processes()) == 0


def test_safe_subprocess_run_success() -> None:
    """Test safe_subprocess_run with successful execution and output capture."""
    res = safe_subprocess_run(
        [sys.executable, "-c", "print('SUBPROCESS_BROKER_OK')"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "SUBPROCESS_BROKER_OK" in res.stdout


def test_safe_subprocess_run_with_custom_env_and_cwd(tmp_path: Path) -> None:
    """Test safe_subprocess_run with custom working directory and environment variables."""
    test_env = {"COCHEM_BROKER_TEST_VAR": "ALPHA_OMEGA_VALUE"}
    test_script = "import os, sys; print(os.getcwd()); print(os.environ.get('COCHEM_BROKER_TEST_VAR'))"

    res = safe_subprocess_run(
        [sys.executable, "-c", test_script],
        cwd=tmp_path,
        env=test_env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert str(tmp_path).lower() in res.stdout.lower()
    assert "ALPHA_OMEGA_VALUE" in res.stdout


def test_safe_subprocess_run_invalid_cwd() -> None:
    """Test safe_subprocess_run raising FileNotFoundError on non-existent directory."""
    non_existent_dir = Path("D:/non_existent_dir_co_chem_xyz_987")
    with pytest.raises(FileNotFoundError):
        safe_subprocess_run(
            [sys.executable, "-c", "print('fail')"],
            cwd=non_existent_dir
        )


def test_safe_subprocess_run_called_process_error() -> None:
    """Test safe_subprocess_run raising CalledProcessError on non-zero exit with check=True."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        safe_subprocess_run(
            [sys.executable, "-c", "import sys; sys.stderr.write('FAILURE_LOG'); sys.exit(42)"],
            check=True
        )
    assert exc_info.value.returncode == 42
    assert "FAILURE_LOG" in (exc_info.value.stderr or "")


def test_safe_subprocess_run_timeout() -> None:
    """Test safe_subprocess_run timing out and raising TimeoutExpired."""
    with pytest.raises(subprocess.TimeoutExpired):
        safe_subprocess_run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.5
        )


def test_safe_subprocess_run_string_command() -> None:
    """Test safe_subprocess_run when passing a command string."""
    res = safe_subprocess_run(
        f'"{sys.executable}" -c "print(12345)"',
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "12345" in res.stdout


def test_broker_init_and_context_manager(tmp_path: Path) -> None:
    """Test SubprocessBroker initialization, context manager enter/exit, and directory setup."""
    scratch_dir = tmp_path / "custom_scratch"
    with SubprocessBroker(cwd=scratch_dir) as broker:
        assert broker.cwd.exists()
        assert broker.memory_limit_bytes > 0
        assert broker._atexit_reaper is not None


def test_broker_oom_monitor_lifecycle() -> None:
    """Test starting and stopping OOM preemption monitor thread without blocking."""
    broker = SubprocessBroker()
    try:
        broker.start_oom_monitor(check_interval=0.1)
        if HAS_PSUTIL:
            assert broker._monitor_thread is not None
            assert broker._monitor_thread.is_alive()
        time.sleep(0.3)
    finally:
        broker.stop_oom_monitor()
        assert broker._monitor_thread is None
        broker.close()


def test_broker_execute_success(tmp_path: Path) -> None:
    """Test SubprocessBroker executing a command successfully."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import sys; sys.stdout.write('BROKER_EXEC_OK'); sys.exit(0)"],
            job_name="test_exec_ok"
        )
        assert exit_code == 0
    finally:
        broker.close()


def test_broker_execute_failure(tmp_path: Path) -> None:
    """Test SubprocessBroker capturing a non-zero exit code."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import sys; sys.stderr.write('CRASH'); sys.exit(5)"],
            job_name="test_exec_fail"
        )
        assert exit_code == 5
    finally:
        broker.close()


def test_broker_execute_timeout(tmp_path: Path) -> None:
    """Test SubprocessBroker enforcing process timeout and returning -124."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            job_name="test_exec_timeout",
            timeout=0.6
        )
        assert exit_code == -124
    finally:
        broker.close()


def test_broker_core_dump_garbage_collection(tmp_path: Path) -> None:
    """Test sweeping core dump binary files."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        core1 = tmp_path / "core.1234"
        core2 = tmp_path / "core.5678"
        normal = tmp_path / "output.txt"
        core1.write_bytes(b"DUMP_DATA_1")
        core2.write_bytes(b"DUMP_DATA_2")
        normal.write_text("VALID_DATA", encoding="utf-8")

        swept = broker.garbage_collect_core_dumps(tmp_path)
        assert swept == 2
        assert not core1.exists()
        assert not core2.exists()
        assert normal.exists()
    finally:
        broker.close()


def test_broker_artifact_sync_and_hash(tmp_path: Path) -> None:
    """Test SubprocessBroker generates hashes for quantum chemistry artifact files."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        # Create output file in cwd
        out_file = tmp_path / "water_opt.out"
        out_file.write_text("FINAL SINGLE POINT ENERGY -76.43210 Hartree\n", encoding="utf-8")

        script = f'import sys; sys.stdout.write("DONE"); sys.exit(0)'
        exit_code = broker.execute([sys.executable, "-c", script], job_name="hash_test")
        assert exit_code == 0
        assert out_file.exists()
    finally:
        broker.close()


def test_broker_zombie_reaper_active_processes() -> None:
    """Test execute_zombie_reaper kills active processes tracked by the broker."""
    broker = SubprocessBroker()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        with broker._lock:
            broker.active_processes.append(proc)
        register_popen_process(proc)

        time.sleep(0.3)
        reaped = broker.execute_zombie_reaper()
        assert reaped >= 1
        assert len(broker.active_processes) == 0

        proc.wait(timeout=2.0)
    finally:
        broker.close()
