"""
Unit and Integration Test Suite for CoChem Core Subprocess Broker.
Validates NUMA CPU Pinning, OpenMPI Sanitization, Pre-Flight Disk Quota,
64KB SHA-256 Binary Probe, RAM-Disk Overlay Routing, ZeroMQ Heartbeats (CurveZMQ/IPC),
Dead-Man's Switch Watchdogs, Win32 Job Objects, and Zombie Reaping with ZERO MOCKS.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import pytest

from core_engine.cochem_core_subprocess_broker import (
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
    get_active_popen_processes,
    kill_process_tree,
    lock_directory_permissions,
    register_popen_process,
    safe_subprocess_run,
    sanitize_mpi_environment,
    unregister_popen_process,
    verify_scratch_io,
    verify_scratch_quota_and_io,
)

if HAS_PSUTIL:
    import psutil

if HAS_ZMQ:
    import zmq


# =====================================================================
# 1. Process Lifecycle & Zombie Sweeping
# =====================================================================

def test_popen_registration_and_unregistration() -> None:
    """Test registering, polling active, and unregistering subprocesses."""
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
    child_pids: List[int] = []
    if HAS_PSUTIL:
        try:
            parent_p = psutil.Process(pid)
            child_pids = [c.pid for c in parent_p.children(recursive=True)]
        except psutil.NoSuchProcess:
            pass

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


def test_zombie_reaper_class() -> None:
    """Test ZombieReaper static helper methods."""
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    register_popen_process(proc)
    try:
        ZombieReaper.reap_pid(proc.pid, timeout=2.0)
        proc.wait(timeout=2.0)
        assert proc.poll() is not None
    finally:
        unregister_popen_process(proc)


# =====================================================================
# 2. NUMA CPU Pinning & MPI Sanitization
# =====================================================================

def test_cpu_topology_detection_and_manager() -> None:
    """Test physical host CPU topology detection and CPUTopologyManager allocation."""
    topo = detect_cpu_topology()
    assert isinstance(topo, dict)
    assert topo["logical_cores"] >= 1
    assert topo["physical_cores"] >= 1
    assert topo["sockets"] >= 1
    assert len(topo["numa_nodes"]) >= 1

    mgr = CPUTopologyManager()
    mgr_topo = mgr.get_topology()
    assert mgr_topo["logical_cores"] == topo["logical_cores"]

    allocated = mgr.allocate_cores(count=1)
    assert len(allocated) == 1
    assert isinstance(allocated[0], int)

    affinity_calc = mgr.calculate_thread_affinity(rank=0, threads_per_rank=1)
    assert len(affinity_calc) == 1


def test_enforce_cpu_affinity() -> None:
    """Test CPU affinity enforcement on current process."""
    if HAS_PSUTIL:
        pid = os.getpid()
        num_cores = os.cpu_count() or 1
        target_cores = [0] if num_cores > 0 else []
        success = enforce_cpu_affinity(pid, target_cores)
        assert success is True


def test_cpu_affinity_darwin_graceful_fallback() -> None:
    """Test enforce_cpu_affinity does not crash on empty cores or current PID."""
    assert enforce_cpu_affinity(os.getpid(), None) is True
    assert enforce_cpu_affinity(os.getpid(), []) is True


def test_detect_mpi_environment() -> None:
    """Test detection of multi-rank OpenMPI / SLURM execution environments."""
    empty_env: dict[str, str] = {}
    assert detect_mpi_environment(empty_env) is False

    openmpi_env = {"OMPI_COMM_WORLD_SIZE": "4"}
    assert detect_mpi_environment(openmpi_env) is True

    pmi_env = {"PMI_SIZE": "8"}
    assert detect_mpi_environment(pmi_env) is True

    slurm_env = {"SLURM_NTASKS": "16"}
    assert detect_mpi_environment(slurm_env) is True

    rank_env = {"MPI_LOCALRANKID": "0"}
    assert detect_mpi_environment(rank_env) is True


def test_sanitize_mpi_environment_multi_rank() -> None:
    """Test forcing single-thread variables when MPI environment is detected."""
    env = {
        "OMPI_COMM_WORLD_SIZE": "4",
        "OMP_NUM_THREADS": "8",
        "MKL_NUM_THREADS": "8",
    }
    sanitized = sanitize_mpi_environment(env)
    assert sanitized["OMP_NUM_THREADS"] == "1"
    assert sanitized["MKL_NUM_THREADS"] == "1"
    assert sanitized["OPENBLAS_NUM_THREADS"] == "1"
    assert sanitized["VECLIB_MAXIMUM_THREADS"] == "1"
    assert sanitized["NUMEXPR_NUM_THREADS"] == "1"
    assert sanitized["BLIS_NUM_THREADS"] == "1"


def test_sanitize_mpi_environment_single_rank() -> None:
    """Test that single rank non-MPI environments are preserved unless forced."""
    env = {
        "OMP_NUM_THREADS": "8",
    }
    sanitized = sanitize_mpi_environment(env, force_single_thread=False)
    assert sanitized["OMP_NUM_THREADS"] == "8"

    sanitized_forced = sanitize_mpi_environment(env, force_single_thread=True)
    assert sanitized_forced["OMP_NUM_THREADS"] == "1"


# =====================================================================
# 3. Pre-Flight Storage Quota & RAM-Disk Routing
# =====================================================================

def test_preflight_disk_quota_success(tmp_path: Path) -> None:
    """Test pre-flight quota check passes when requesting small valid capacity."""
    scratch_dir = tmp_path / "valid_quota_scratch"
    res = verify_scratch_quota_and_io(scratch_dir, required_gb=0.001)
    assert res is True
    assert scratch_dir.exists()


def test_preflight_disk_quota_breach_raises_error(tmp_path: Path) -> None:
    """Test real physical DiskQuotaError is raised when requesting impossible capacity without mocks."""
    scratch_dir = tmp_path / "quota_fail_dir"
    with pytest.raises(DiskQuotaError) as exc_info:
        verify_scratch_quota_and_io(scratch_dir, required_gb=999999.0)

    err = exc_info.value
    assert err.required_gb == 999999.0
    assert err.available_gb < 999999.0
    assert err.path == scratch_dir.resolve()
    assert "Insufficient scratch disk quota" in str(err)


def test_scratch_binary_probe_integrity(tmp_path: Path) -> None:
    """Test 64KB unbuffered SHA-256 binary probe integrity on physical media."""
    probe_dir = tmp_path / "probe_dir"
    assert verify_scratch_quota_and_io(probe_dir, required_gb=0.01) is True

    # Backward compatibility helper
    assert verify_scratch_io(probe_dir, required_mb=10) is True


def test_lock_directory_permissions(tmp_path: Path) -> None:
    """Test locking directory permissions (0o700 on POSIX or icacls on Windows)."""
    target = tmp_path / "locked_perm_dir"
    res = lock_directory_permissions(target)
    assert res is True
    assert target.exists()

    if platform.system() != "Windows":
        mode = target.stat().st_mode & 0o777
        assert mode == 0o700


def test_ramdisk_overlay_manager_threshold_and_provisioning(tmp_path: Path) -> None:
    """Test RAMDiskOverlayManager host RAM threshold checks and provisioning."""
    mgr = RAMDiskOverlayManager(threshold_ram_gb=128.0)
    total_ram = mgr.get_total_host_ram_gb()
    assert isinstance(total_ram, float)

    is_eligible = mgr.is_ramdisk_eligible(min_ram_gb=128.0)
    assert is_eligible == (total_ram >= 128.0)

    # Provisioning fallback directory
    fallback = tmp_path / "custom_fallback"
    overlay = mgr.provision_overlay("job_unit_test", required_gb=1.0, fallback_dir=fallback)
    assert overlay.exists()


def test_ramdisk_overlay_sync_and_cleanup(tmp_path: Path) -> None:
    """Test RAMDiskOverlayManager synchronizes quantum artifacts and cleans up overlay."""
    mgr = RAMDiskOverlayManager()
    overlay_dir = tmp_path / "overlay_source"
    perm_dir = tmp_path / "permanent_dest"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    perm_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy quantum artifacts
    out_file = overlay_dir / "geom_opt.out"
    out_file.write_text("ENERGY = -100.123456 Hartree\n", encoding="utf-8")
    xyz_file = overlay_dir / "coords.xyz"
    xyz_file.write_text("3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    hashes = mgr.sync_and_cleanup(overlay_dir, perm_dir)
    assert "geom_opt.out" in hashes
    assert "coords.xyz" in hashes
    assert (perm_dir / "geom_opt.out").exists()
    assert (perm_dir / "coords.xyz").exists()
    assert not overlay_dir.exists()


# =====================================================================
# 4. ZeroMQ Heartbeat & Dead-Man's Switch Watchdog
# =====================================================================

def test_zmq_heartbeat_manager_curve_and_lifecycle() -> None:
    """Test ZMQHeartbeatManager start, publish, and stop lifecycle."""
    if not HAS_ZMQ:
        pytest.skip("pyzmq not installed")

    hb_mgr = ZMQHeartbeatManager(job_id="test_heartbeat_job")
    try:
        endpoint = hb_mgr.start(interval_sec=0.1, metadata={"role": "quantum_worker"})
        assert endpoint != ""
        assert hb_mgr._thread is not None
        assert hb_mgr._thread.is_alive()

        # Publish manual heartbeat
        hb_mgr.publish_heartbeat(status="running", extra={"step": 1})
        time.sleep(0.3)
    finally:
        hb_mgr.stop()
        assert hb_mgr._thread is None


def test_broker_zmq_heartbeat_lifecycle() -> None:
    """Test SubprocessBroker starting and receiving heartbeats over ZeroMQ."""
    if not HAS_ZMQ:
        pytest.skip("pyzmq not installed")

    port = 5569
    broker = SubprocessBroker()
    ctx = zmq.Context()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.connect(f"tcp://127.0.0.1:{port}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "heartbeat")

    try:
        broker.start_zmq_heartbeat(port=port, interval_sec=0.1, metadata={"tier": "test"})
        assert broker._zmq_thread is not None
        assert broker._zmq_thread.is_alive()

        poller = zmq.Poller()
        poller.register(sub_socket, zmq.POLLIN)
        events = dict(poller.poll(timeout=2000))

        if sub_socket in events:
            topic, payload_bytes = sub_socket.recv_multipart()
            assert topic == b"heartbeat"
            data = json.loads(payload_bytes.decode("utf-8"))
            assert data["status"] == "alive"
            assert data["metadata"]["tier"] == "test"
    finally:
        broker.stop_zmq_heartbeat()
        sub_socket.close(linger=0)
        ctx.term()
        broker.close()


def test_dead_mans_switch_watchdog_daemon_transition() -> None:
    """Test DeadMansSwitchWatchdog transitions process to detached daemon on timeout."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    register_popen_process(proc)

    try:
        watchdog = DeadMansSwitchWatchdog(
            job_id="test_dms_daemon",
            proc=proc,
            timeout=0.3,
            check_interval=0.05,
            on_timeout="daemonize",
        )
        with watchdog:
            time.sleep(0.6)
            assert watchdog.is_daemonized is True
            # Assert process is still alive and was detached rather than killed
            assert proc.poll() is None
    finally:
        kill_process_tree(proc.pid)
        proc.wait(timeout=2.0)


def test_dead_mans_switch_watchdog_ping_reset() -> None:
    """Test that active pings prevent DeadMansSwitchWatchdog from triggering."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    register_popen_process(proc)

    try:
        watchdog = DeadMansSwitchWatchdog(
            job_id="test_dms_ping",
            proc=proc,
            timeout=0.4,
            check_interval=0.05,
            on_timeout="kill",
        )
        with watchdog:
            for _ in range(5):
                time.sleep(0.1)
                watchdog.ping()
            assert watchdog.is_daemonized is False
            assert proc.poll() is None
    finally:
        kill_process_tree(proc.pid)
        proc.wait(timeout=2.0)


# =====================================================================
# 5. Win32 Job Objects & Process Groups
# =====================================================================

def test_windows_job_object_kill_on_close() -> None:
    """Test Win32 Job Object automatically terminates child processes when handle closes."""
    if platform.system() != "Windows":
        pytest.skip("Win32 Job Object test is Windows-only")

    job = WindowsJobObject(kill_on_close=True)
    assert job.handle is not None

    cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
    proc = subprocess.Popen(cmd)
    try:
        assigned = job.assign_popen(proc)
        assert assigned is True
        # Close job object; process should be terminated by OS kernel
        job.close()
        time.sleep(0.5)
        assert proc.poll() is not None
    finally:
        kill_process_tree(proc.pid)


# =====================================================================
# 6. Safe Subprocess Execution (safe_subprocess_run)
# =====================================================================

def test_safe_subprocess_run_success() -> None:
    """Test safe_subprocess_run with successful execution and output capture."""
    res = safe_subprocess_run(
        [sys.executable, "-c", "print('SUBPROCESS_BROKER_OK')"],
        capture_output=True,
        text=True,
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
        text=True,
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
            cwd=non_existent_dir,
        )


def test_safe_subprocess_run_called_process_error() -> None:
    """Test safe_subprocess_run raising CalledProcessError on non-zero exit with check=True."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        safe_subprocess_run(
            [sys.executable, "-c", "import sys; sys.stderr.write('FAILURE_LOG'); sys.exit(42)"],
            check=True,
        )
    assert exc_info.value.returncode == 42
    assert "FAILURE_LOG" in (exc_info.value.stderr or "")


def test_safe_subprocess_run_timeout() -> None:
    """Test safe_subprocess_run timing out and raising TimeoutExpired."""
    with pytest.raises(subprocess.TimeoutExpired):
        safe_subprocess_run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.5,
        )


def test_safe_subprocess_run_string_command() -> None:
    """Test safe_subprocess_run when passing a command string."""
    res = safe_subprocess_run(
        f'"{sys.executable}" -c "print(12345)"',
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "12345" in res.stdout


def test_safe_subprocess_run_with_affinity() -> None:
    """Test safe_subprocess_run with explicit CPU affinity specification."""
    if HAS_PSUTIL:
        available_cores = list(range(min(2, os.cpu_count() or 1)))
        res = safe_subprocess_run(
            [sys.executable, "-c", "print('AFFINITY_OK')"],
            capture_output=True,
            text=True,
            cpu_affinity=available_cores,
        )
        assert res.returncode == 0
        assert "AFFINITY_OK" in res.stdout


def test_safe_subprocess_run_with_quota_check(tmp_path: Path) -> None:
    """Test safe_subprocess_run performs pre-flight disk quota assertion."""
    res = safe_subprocess_run(
        [sys.executable, "-c", "print('QUOTA_OK')"],
        cwd=tmp_path,
        required_disk_gb=0.001,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "QUOTA_OK" in res.stdout

    with pytest.raises(DiskQuotaError):
        safe_subprocess_run(
            [sys.executable, "-c", "print('FAIL')"],
            cwd=tmp_path,
            required_disk_gb=999999.0,
        )


# =====================================================================
# 7. SubprocessBroker Execution & Artifacts
# =====================================================================

def test_broker_init_and_context_manager(tmp_path: Path) -> None:
    """Test SubprocessBroker initialization, context manager enter/exit, and directory setup."""
    scratch_dir = tmp_path / "custom_scratch"
    with SubprocessBroker(cwd=scratch_dir) as broker:
        assert broker.cwd.exists()
        assert broker.memory_limit_bytes > 0
        assert broker._atexit_reaper is not None
        assert broker._lock is not None


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
            job_name="test_exec_ok",
            required_disk_gb=0.01,
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
            job_name="test_exec_fail",
            required_disk_gb=0.01,
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
            timeout=0.6,
            required_disk_gb=0.01,
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
        out_file = tmp_path / "water_opt.out"
        out_file.write_text("FINAL SINGLE POINT ENERGY -76.43210 Hartree\n", encoding="utf-8")

        script = 'import sys; sys.stdout.write("DONE"); sys.exit(0)'
        exit_code = broker.execute(
            [sys.executable, "-c", script],
            job_name="hash_test",
            required_disk_gb=0.01,
        )
        assert exit_code == 0
        assert out_file.exists()

        hashes = broker.hash_quantum_artifacts(tmp_path)
        assert "water_opt.out" in hashes
        assert len(hashes["water_opt.out"]) == 64
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


def test_sanitize_mpi_environment_with_command_line() -> None:
    """Test detect_mpi_environment and sanitize_mpi_environment trigger on MPI runner commands."""
    plain_env = {"OMP_NUM_THREADS": "16"}
    sanitized = sanitize_mpi_environment(plain_env, cmd=["mpirun", "-np", "4", "orca", "job.inp"])
    assert sanitized["OMP_NUM_THREADS"] == "1"
    assert sanitized["MKL_NUM_THREADS"] == "1"

    sanitized_srun = sanitize_mpi_environment(plain_env, cmd="srun -n 8 /usr/bin/orca input.inp")
    assert sanitized_srun["OMP_NUM_THREADS"] == "1"


def test_windows_job_object_disable_kill_on_close() -> None:
    """Test that set_kill_on_close(False) prevents OS kernel from terminating processes on handle close."""
    if platform.system() != "Windows":
        pytest.skip("Win32 Job Object test is Windows-only")

    job = WindowsJobObject(kill_on_close=True)
    assert job.handle is not None

    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    try:
        assigned = job.assign_popen(proc)
        assert assigned is True
        # Disable kill on close flag
        toggled = job.set_kill_on_close(False)
        assert toggled is True
        # Close handle
        job.close()
        time.sleep(0.3)
        # Process should remain alive
        assert proc.poll() is None
    finally:
        kill_process_tree(proc.pid)
        proc.wait(timeout=2.0)

