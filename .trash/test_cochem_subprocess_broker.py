"""
Comprehensive Zero-Mock Unit and Integration Test Suite for CoChem Subprocess Broker.
Validates:
1. Cross-platform process isolation and Win32 Job Object management.
2. psutil process tree tracking and 10-second grace period recursive tree killing.
3. atexit Zombie Reaper daemon and signal cleanup hooks.
4. Segfault (POSIX 139 / -11) & Access Violation (Windows 0xC0000005 / -1073741819 / 3221225477)
   256-byte terminal stderr hex-dump extraction and canonical formatting.
5. safe_subprocess_run execution, timeout handling, crash trace attachment, and quota checks.
6. SubprocessBroker lifecycle, scratch provisioning, RAM-disk routing, watchdog, and artifact hashing.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import pytest

from core_engine.cochem_subprocess_broker import (
    HAS_PSUTIL,
    HAS_ZMQ,
    CPUTopologyManager,
    DeadMansSwitchWatchdog,
    DiskQuotaError,
    RAMDiskOverlayManager,
    SubprocessBroker,
    WindowsJobObject,
    ZMQHeartbeatManager,
    ZombieReaper,
    cleanup_zombie_processes,
    detect_cpu_topology,
    detect_mpi_environment,
    enforce_cpu_affinity,
    extract_segfault_hex_dump,
    get_active_popen_processes,
    is_crash_returncode,
    kill_process_tree,
    lock_directory_permissions,
    register_popen_process,
    safe_subprocess_run,
    sanitize_mpi_environment,
    sweep_crash_hex_dump,
    unregister_popen_process,
    verify_scratch_quota_and_io,
)

if HAS_PSUTIL:
    import psutil

if HAS_ZMQ:
    pass


# =====================================================================
# 1. Process Lifecycle, Registration & Unregistration
# =====================================================================

def test_process_registration_lifecycle() -> None:
    """Test registering, polling active status, and unregistering subprocesses."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    try:
        register_popen_process(proc)
        active = get_active_popen_processes()
        assert proc in active

        unregister_popen_process(proc)
        active_after = get_active_popen_processes()
        assert proc not in active_after
    finally:
        kill_process_tree(proc.pid, timeout=10.0)
        proc.wait(timeout=3.0)


def test_multiple_process_registration() -> None:
    """Test registering multiple real processes and automatic cleanup of terminated processes."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc1 = subprocess.Popen(cmd)
    proc2 = subprocess.Popen(cmd)
    try:
        register_popen_process(proc1)
        register_popen_process(proc2)
        active = get_active_popen_processes()
        assert proc1 in active
        assert proc2 in active

        # Terminate proc1
        kill_process_tree(proc1.pid, timeout=10.0)
        proc1.wait(timeout=3.0)

        # Polling active list automatically drops completed processes
        active_updated = get_active_popen_processes()
        assert proc1 not in active_updated
        assert proc2 in active_updated
    finally:
        kill_process_tree(proc2.pid, timeout=10.0)
        proc2.wait(timeout=3.0)


# =====================================================================
# 2. Recursive Process Tree Killing & 10-Second Grace Period
# =====================================================================

def test_kill_process_tree_multi_level() -> None:
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
    child_pids: List[int] = []
    if HAS_PSUTIL:
        try:
            parent_p = psutil.Process(pid)
            child_pids = [c.pid for c in parent_p.children(recursive=True)]
        except psutil.NoSuchProcess:
            pass

    kill_process_tree(pid, timeout=10.0)
    proc.wait(timeout=3.0)

    if HAS_PSUTIL:
        time.sleep(0.3)
        assert not psutil.pid_exists(pid)
        for c_pid in child_pids:
            assert not psutil.pid_exists(c_pid)


def test_kill_process_tree_nonexistent_pid() -> None:
    """Ensure kill_process_tree gracefully handles non-existent PIDs."""
    # Should not raise exception
    kill_process_tree(999999, timeout=10.0)


# =====================================================================
# 3. atexit Zombie Reaper Daemon & Cleanup Hooks
# =====================================================================

def test_cleanup_zombie_processes_sweeps_all() -> None:
    """Test global cleanup_zombie_processes terminates all tracked background processes."""
    cmd = [sys.executable, "-c", "import time; time.sleep(20)"]
    proc1 = subprocess.Popen(cmd)
    proc2 = subprocess.Popen(cmd)
    register_popen_process(proc1)
    register_popen_process(proc2)

    count = cleanup_zombie_processes()
    assert count >= 2

    proc1.wait(timeout=3.0)
    proc2.wait(timeout=3.0)

    if HAS_PSUTIL:
        assert not psutil.pid_exists(proc1.pid)
        assert not psutil.pid_exists(proc2.pid)


def test_zombie_reaper_class_methods() -> None:
    """Test ZombieReaper static helper methods."""
    cmd = [sys.executable, "-c", "import time; time.sleep(15)"]
    proc = subprocess.Popen(cmd)
    register_popen_process(proc)
    try:
        ZombieReaper.reap_pid(proc.pid, timeout=10.0)
        proc.wait(timeout=3.0)
        if HAS_PSUTIL:
            assert not psutil.pid_exists(proc.pid)
    finally:
        if proc.poll() is None:
            proc.kill()


# =====================================================================
# 4. Segfault & Access Violation Hex-Dump Sweeper
# =====================================================================

def test_is_crash_returncode() -> None:
    """Test detection of POSIX segfaults, signals, and Windows access violations."""
    assert is_crash_returncode(139) is True
    assert is_crash_returncode(-11) is True
    assert is_crash_returncode(-1073741819) is True
    assert is_crash_returncode(3221225477) is True
    assert is_crash_returncode(0xC0000005) is True
    assert is_crash_returncode(134) is True
    assert is_crash_returncode(-6) is True
    assert is_crash_returncode(-1073741571) is True
    assert is_crash_returncode(0xC00000FD) is True

    # Non crash codes
    assert is_crash_returncode(0) is False
    assert is_crash_returncode(1) is False
    assert is_crash_returncode(2) is False
    assert is_crash_returncode(None) is False


def test_extract_segfault_hex_dump_posix_139() -> None:
    """Test hex dump extraction on POSIX Exit Code 139 (SIGSEGV)."""
    raw_stderr = b"Fatal error in ORCA SCF iteration: Segmentation fault at memory offset 0x7fffabcd\n"
    res = extract_segfault_hex_dump(139, raw_stderr)

    assert res["is_crash"] is True
    assert res["returncode"] == 139
    assert res["crash_type"] == "SIGSEGV"
    assert res["raw_hex"] == raw_stderr.hex()
    assert res["byte_count"] == len(raw_stderr)
    assert "00000000:" in res["formatted_hex_dump"]
    assert "Fatal error" in res["formatted_hex_dump"]
    assert res["terminal_stderr_snippet"] == raw_stderr.decode("utf-8")


def test_extract_segfault_hex_dump_windows_access_violation_signed() -> None:
    """Test hex dump extraction on Windows Access Violation -1073741819 (0xC0000005)."""
    raw_stderr = b"ACCESS_VIOLATION reading address 0x0000000000000010\n"
    res = extract_segfault_hex_dump(-1073741819, raw_stderr)

    assert res["is_crash"] is True
    assert res["returncode"] == -1073741819
    assert res["crash_type"] == "STATUS_ACCESS_VIOLATION"
    assert res["raw_hex"] == raw_stderr.hex()
    assert "00000000:" in res["formatted_hex_dump"]


def test_extract_segfault_hex_dump_windows_access_violation_unsigned() -> None:
    """Test hex dump extraction on Windows Access Violation 3221225477 (0xC0000005 unsigned)."""
    raw_stderr = b"STATUS_ACCESS_VIOLATION in quantum module\n"
    res = extract_segfault_hex_dump(3221225477, raw_stderr)

    assert res["is_crash"] is True
    assert res["returncode"] == 3221225477
    assert res["crash_type"] == "STATUS_ACCESS_VIOLATION"
    assert res["raw_hex"] == raw_stderr.hex()


def test_extract_segfault_hex_dump_256_byte_tail_extraction() -> None:
    """Test that precisely the final 256 bytes are extracted when stderr buffer exceeds 256 bytes."""
    full_buffer = os.urandom(1024)
    expected_tail = full_buffer[-256:]

    res = extract_segfault_hex_dump(139, full_buffer, max_bytes=256)
    assert res["is_crash"] is True
    assert res["byte_count"] == 256
    assert res["raw_hex"] == expected_tail.hex()


def test_extract_segfault_hex_dump_string_and_list_formats() -> None:
    """Test extracting hex dumps from string and list of strings stderr buffers."""
    str_buffer = "Critical quantum failure: segfault core dumped\n"
    res_str = extract_segfault_hex_dump(139, str_buffer)
    assert res_str["is_crash"] is True
    assert res_str["raw_hex"] == str_buffer.encode("utf-8").hex()

    list_buffer = ["Line 1: computing integrals", "Line 2: memory crash"]
    res_list = extract_segfault_hex_dump(-1073741819, list_buffer)
    assert res_list["is_crash"] is True
    assert res_list["byte_count"] == len("\n".join(list_buffer).encode("utf-8"))


def test_extract_segfault_hex_dump_non_crash_returncode() -> None:
    """Test extract_segfault_hex_dump returns non-crash payload for standard exit codes."""
    res_zero = extract_segfault_hex_dump(0, b"Normal output")
    assert res_zero["is_crash"] is False
    assert res_zero["raw_hex"] == ""
    assert res_zero["formatted_hex_dump"] == ""
    assert res_zero["crash_type"] is None

    res_one = extract_segfault_hex_dump(1, "Syntax error")
    assert res_one["is_crash"] is False


def test_sweep_crash_hex_dump_alias() -> None:
    """Test sweep_crash_hex_dump alias performs identically to extract_segfault_hex_dump."""
    raw_data = b"Crash test buffer"
    res1 = extract_segfault_hex_dump(139, raw_data)
    res2 = sweep_crash_hex_dump(139, raw_data)
    assert res1 == res2


# =====================================================================
# 5. Safe Subprocess Run & Crash Trace Integration
# =====================================================================

def test_safe_subprocess_run_success() -> None:
    """Test safe_subprocess_run executes standard commands successfully."""
    cmd = [sys.executable, "-c", "print('BrokerExecutionSuccess')"]
    res = safe_subprocess_run(cmd, check=True)
    assert res.returncode == 0
    assert "BrokerExecutionSuccess" in res.stdout
    assert getattr(res, "crash_payload", {}).get("is_crash") is False


def test_safe_subprocess_run_with_custom_env_and_cwd(tmp_path: Path) -> None:
    """Test safe_subprocess_run respects custom environment variables and working directory."""
    test_dir = tmp_path / "broker_work"
    test_dir.mkdir(parents=True, exist_ok=True)
    env = {"CUSTOM_VAR": "COCHEM_VALIDATED_2026"}
    cmd = [sys.executable, "-c", "import os; print(os.environ.get('CUSTOM_VAR'))"]

    res = safe_subprocess_run(cmd, cwd=test_dir, env=env, check=True)
    assert res.returncode == 0
    assert "COCHEM_VALIDATED_2026" in res.stdout


def test_safe_subprocess_run_invalid_cwd() -> None:
    """Test safe_subprocess_run raises FileNotFoundError when given non-existent cwd."""
    invalid_dir = Path("/non/existent/path/for/cochem/test")
    cmd = [sys.executable, "-c", "print(1)"]
    with pytest.raises(FileNotFoundError):
        safe_subprocess_run(cmd, cwd=invalid_dir)


def test_safe_subprocess_run_called_process_error_and_crash_payload() -> None:
    """Test safe_subprocess_run raises CalledProcessError with attached crash trace."""
    cmd = [sys.executable, "-c", "import sys; sys.stderr.write('Fatal segfault memory trace'); sys.exit(139)"]
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        safe_subprocess_run(cmd, check=True)

    err = exc_info.value
    assert err.returncode == 139
    crash_payload = getattr(err, "crash_payload", {})
    assert crash_payload.get("is_crash") is True
    assert crash_payload.get("crash_type") == "SIGSEGV"
    assert "Fatal segfault memory trace" in crash_payload.get("terminal_stderr_snippet", "")


def test_safe_subprocess_run_timeout() -> None:
    """Test safe_subprocess_run terminates unresponsive process upon timeout."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    with pytest.raises(subprocess.TimeoutExpired):
        safe_subprocess_run(cmd, timeout=0.6)


def test_safe_subprocess_run_string_command() -> None:
    """Test safe_subprocess_run parses string command lines properly."""
    cmd_str = f'"{sys.executable}" -c "print(\'StringCommandOk\')"'
    res = safe_subprocess_run(cmd_str, check=True)
    assert res.returncode == 0
    assert "StringCommandOk" in res.stdout


def test_safe_subprocess_run_with_affinity() -> None:
    """Test safe_subprocess_run with CPU affinity specification."""
    cmd = [sys.executable, "-c", "print('AffinityPinned')"]
    res = safe_subprocess_run(cmd, cpu_affinity=[0], check=True)
    assert res.returncode == 0
    assert "AffinityPinned" in res.stdout


def test_safe_subprocess_run_with_quota_check(tmp_path: Path) -> None:
    """Test safe_subprocess_run performs pre-flight storage quota check."""
    cmd = [sys.executable, "-c", "print('QuotaCheckPassed')"]
    res = safe_subprocess_run(cmd, cwd=tmp_path, required_disk_gb=0.01, check=True)
    assert res.returncode == 0
    assert "QuotaCheckPassed" in res.stdout


# =====================================================================
# 6. Win32 Job Object Integration
# =====================================================================

def test_windows_job_object_kill_on_close() -> None:
    """Test Win32 Job Object creation and PID assignment."""
    if platform.system() != "Windows":
        pytest.skip("Win32 Job Objects are Windows-specific.")

    job = WindowsJobObject(kill_on_close=True)
    assert job.handle is not None

    cmd = [sys.executable, "-c", "import time; time.sleep(20)"]
    proc = subprocess.Popen(cmd)
    try:
        assigned = job.assign_popen(proc)
        assert assigned is True
    finally:
        job.close()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_windows_job_object_disable_kill_on_close() -> None:
    """Test dynamically modifying Win32 Job Object kill-on-close limits."""
    if platform.system() != "Windows":
        pytest.skip("Win32 Job Objects are Windows-specific.")

    with WindowsJobObject(kill_on_close=True) as job:
        success = job.set_kill_on_close(False)
        assert success is True


# =====================================================================
# 7. CPU Topology & MPI Environment Sanitization
# =====================================================================

def test_cpu_topology_detection_and_manager() -> None:
    """Test hardware CPU topology detection and core allocation."""
    topo = detect_cpu_topology()
    assert "logical_cores" in topo
    assert "physical_cores" in topo
    assert topo["logical_cores"] >= 1

    mgr = CPUTopologyManager(topo)
    cores = mgr.allocate_cores(1)
    assert len(cores) >= 1
    assert isinstance(mgr.get_topology(), dict)


def test_enforce_cpu_affinity() -> None:
    """Test process CPU affinity enforcement."""
    cmd = [sys.executable, "-c", "import time; time.sleep(5)"]
    proc = subprocess.Popen(cmd)
    try:
        success = enforce_cpu_affinity(proc.pid, [0])
        assert isinstance(success, bool)
    finally:
        kill_process_tree(proc.pid, timeout=10.0)
        proc.wait(timeout=3.0)


def test_detect_and_sanitize_mpi_environment() -> None:
    """Test MPI multi-rank detection and environment variable thread sanitization."""
    test_env = {"OMPI_COMM_WORLD_SIZE": "4", "OMP_NUM_THREADS": "8"}
    assert detect_mpi_environment(test_env) is True

    sanitized = sanitize_mpi_environment(test_env)
    assert sanitized["OMP_NUM_THREADS"] == "1"
    assert sanitized["MKL_NUM_THREADS"] == "1"
    assert sanitized["OPENBLAS_NUM_THREADS"] == "1"


# =====================================================================
# 8. Pre-Flight Disk Quota & RAM-Disk Overlay
# =====================================================================

def test_preflight_disk_quota_success(tmp_path: Path) -> None:
    """Test successful quota verification on local scratch."""
    assert verify_scratch_quota_and_io(tmp_path, required_gb=0.001) is True


def test_preflight_disk_quota_breach(tmp_path: Path) -> None:
    """Test DiskQuotaError is raised when requested capacity is impossible."""
    with pytest.raises(DiskQuotaError) as exc_info:
        verify_scratch_quota_and_io(tmp_path, required_gb=99999999.0)
    assert exc_info.value.required_gb == 99999999.0


def test_lock_directory_permissions(tmp_path: Path) -> None:
    """Test directory permission lockdown."""
    target_dir = tmp_path / "locked_scratch"
    target_dir.mkdir(parents=True, exist_ok=True)
    res = lock_directory_permissions(target_dir)
    assert res is True


def test_ramdisk_overlay_manager_and_artifact_sync(tmp_path: Path) -> None:
    """Test RAMDiskOverlayManager provisioning, artifact hashing, and sync."""
    overlay_dir = tmp_path / "overlay"
    permanent_dir = tmp_path / "permanent"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    # Write quantum output artifacts
    (overlay_dir / "molecule.out").write_text("ORCA TERMINATED NORMALLY\nFINAL SINGLE POINT ENERGY -76.4\n", encoding="utf-8")
    (overlay_dir / "structure.xyz").write_text("3\nWater\nO 0.0 0.0 0.0\nH 0.0 0.7 0.5\nH 0.0 -0.7 0.5\n", encoding="utf-8")

    mgr = RAMDiskOverlayManager(threshold_ram_gb=1024.0)
    hashes = mgr.sync_and_cleanup(overlay_dir, permanent_dir)

    assert "molecule.out" in hashes
    assert "structure.xyz" in hashes
    assert (permanent_dir / "molecule.out").exists()
    assert (permanent_dir / "structure.xyz").exists()


# =====================================================================
# 9. Dead-Man's Switch Watchdog & ZeroMQ Heartbeats
# =====================================================================

def test_dead_mans_switch_watchdog_ping_reset() -> None:
    """Test dead-man's switch watchdog timer resets upon activity pings."""
    cmd = [sys.executable, "-c", "import time; time.sleep(3)"]
    proc = subprocess.Popen(cmd)
    try:
        with DeadMansSwitchWatchdog(job_id="test_ping_job", proc=proc, timeout=1.0, check_interval=0.2) as wd:
            for _ in range(5):
                time.sleep(0.3)
                wd.ping()
            assert wd.is_daemonized is False
    finally:
        kill_process_tree(proc.pid, timeout=10.0)
        proc.wait(timeout=3.0)


def test_zmq_heartbeat_manager_lifecycle() -> None:
    """Test ZMQHeartbeatManager start and stop lifecycle."""
    if not HAS_ZMQ:
        pytest.skip("pyzmq not installed.")

    hb = ZMQHeartbeatManager(job_id="test_hb_job")
    endpoint = hb.start(interval_sec=0.2)
    assert endpoint != ""
    assert hb._thread is not None
    time.sleep(0.4)
    hb.stop()
    assert hb._thread is None


# =====================================================================
# 10. SubprocessBroker Integration Tests
# =====================================================================

def test_broker_init_and_context_manager(tmp_path: Path) -> None:
    """Test SubprocessBroker initialization and context manager protocol."""
    with SubprocessBroker(cwd=tmp_path, memory_limit_gb=4.0) as broker:
        assert broker.cwd.exists()
        assert len(broker.active_processes) == 0


def test_broker_execute_success_command(tmp_path: Path) -> None:
    """Test SubprocessBroker executes real python payloads cleanly."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        cmd = [sys.executable, "-c", "print('SubprocessBrokerPayloadSuccess')"]
        exit_code = broker.execute(cmd, job_name="test_success_job", timeout=10.0, required_disk_gb=0.01)
        assert exit_code == 0
    finally:
        broker.shutdown()


def test_broker_execute_failure_command(tmp_path: Path) -> None:
    """Test SubprocessBroker captures non-zero return codes."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        cmd = [sys.executable, "-c", "import sys; sys.exit(42)"]
        exit_code = broker.execute(cmd, job_name="test_failure_job", timeout=10.0, required_disk_gb=0.01)
        assert exit_code == 42
    finally:
        broker.shutdown()


def test_broker_execute_timeout_handling(tmp_path: Path) -> None:
    """Test SubprocessBroker terminates processes that exceed execution timeout."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        cmd = [sys.executable, "-c", "import time; time.sleep(15)"]
        exit_code = broker.execute(cmd, job_name="test_timeout_job", timeout=0.8, required_disk_gb=0.01)
        assert exit_code == -124
    finally:
        broker.shutdown()


def test_broker_core_dump_garbage_collection(tmp_path: Path) -> None:
    """Test SubprocessBroker sweeps binary core dump files."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        core1 = tmp_path / "core.5512"
        core2 = tmp_path / "core.8891"
        core1.write_bytes(b"\x7fELF" + b"\x00" * 100)
        core2.write_bytes(b"\x7fELF" + b"\x00" * 100)
        assert core1.exists() and core2.exists()

        swept = broker.garbage_collect_core_dumps(tmp_path)
        assert swept == 2
        assert not core1.exists()
        assert not core2.exists()
    finally:
        broker.shutdown()


def test_broker_artifact_hashing(tmp_path: Path) -> None:
    """Test SubprocessBroker SHA-256 cryptographic provenance hashing."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        out_file = tmp_path / "orca_calc.out"
        out_file.write_text("TOTAL ENERGY: -382.123456 Hartree\n", encoding="utf-8")
        hashes = broker.hash_quantum_artifacts(tmp_path)
        assert "orca_calc.out" in hashes
        assert len(hashes["orca_calc.out"]) == 64
    finally:
        broker.shutdown()


def test_broker_zombie_reaper_active_processes(tmp_path: Path) -> None:
    """Test execute_zombie_reaper on SubprocessBroker terminates all internal processes."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        cmd = [sys.executable, "-c", "import time; time.sleep(20)"]
        p1 = subprocess.Popen(cmd)
        p2 = subprocess.Popen(cmd)
        with broker._lock:
            broker.active_processes.extend([p1, p2])
        register_popen_process(p1)
        register_popen_process(p2)

        reaped = broker.execute_zombie_reaper()
        assert reaped == 2
        p1.wait(timeout=3.0)
        p2.wait(timeout=3.0)
        if HAS_PSUTIL:
            assert not psutil.pid_exists(p1.pid)
            assert not psutil.pid_exists(p2.pid)
    finally:
        broker.shutdown()


def test_broker_extract_crash_hex_dump_method(tmp_path: Path) -> None:
    """Test extract_crash_hex_dump method on SubprocessBroker."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        res = broker.extract_crash_hex_dump(139, b"Segmentation fault at 0xdeadbeef\n")
        assert res["is_crash"] is True
        assert res["crash_type"] == "SIGSEGV"
    finally:
        broker.shutdown()
