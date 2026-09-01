"""
Dedicated Unit and Integration Test Suite for CoChem Subprocess Broker.
Validates ProcessFaultIsolationBroker, FaultIsolationBroker, DedicatedProcessReaper,
CLI entrypoint and arguments, and re-exported core broker functionality.
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
    CRITICAL_SEGFAULT_EXIT_CODES,
    HAS_PSUTIL,
    HAS_ZMQ,
    CPUTopologyManager,
    DeadMansSwitchWatchdog,
    DedicatedProcessReaper,
    DiskQuotaError,
    FaultIsolationBroker,
    ProcessFaultIsolationBroker,
    RAMDiskOverlayManager,
    SubprocessBroker,
    WindowsJobObject,
    ZMQHeartbeatManager,
    ZombieReaper,
    build_cli_parser,
    cleanup_zombie_processes,
    detect_cpu_topology,
    detect_mpi_environment,
    enforce_cpu_affinity,
    extract_segfault_hex_dump,
    get_active_popen_processes,
    is_crash_returncode,
    kill_process_tree,
    lock_directory_permissions,
    main,
    register_popen_process,
    safe_subprocess_run,
    sanitize_mpi_environment,
    sweep_crash_hex_dump,
    unregister_popen_process,
    verify_scratch_io,
    verify_scratch_quota_and_io,
)


# =====================================================================
# 1. Class and Symbol Identity Tests
# =====================================================================

def test_class_inheritance_and_aliases() -> None:
    """Test inheritance hierarchy and backward compatibility aliases."""
    assert issubclass(ProcessFaultIsolationBroker, SubprocessBroker)
    assert FaultIsolationBroker is ProcessFaultIsolationBroker
    assert DedicatedProcessReaper is ZombieReaper


def test_process_fault_isolation_broker_init(tmp_path: Path) -> None:
    """Test ProcessFaultIsolationBroker instantiation with custom parameters."""
    env = {"CUSTOM_VAR": "VALUE"}
    broker = ProcessFaultIsolationBroker(
        cwd=tmp_path,
        env=env,
        memory_limit_gb=16.0,
        total_ram_threshold_gb=64.0,
        enable_job_object=True,
    )
    try:
        assert broker.cwd == tmp_path
        assert broker.env.get("CUSTOM_VAR") == "VALUE"
        assert broker.enable_job_object is True
        assert broker.memory_limit_bytes == 16.0 * (1024 ** 3)
        assert broker.total_ram_threshold_gb == 64.0
    finally:
        broker.close()


def test_execute_with_fault_isolation_success(tmp_path: Path) -> None:
    """Test successful execution via execute_with_fault_isolation."""
    broker = ProcessFaultIsolationBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute_with_fault_isolation(
            [sys.executable, "-c", "import sys; sys.stdout.write('ISOLATED_OK'); sys.exit(0)"],
            job_name="unit_isolation_success",
            required_disk_gb=0.01,
        )
        assert exit_code == 0
    finally:
        broker.close()


def test_execute_with_fault_isolation_failure(tmp_path: Path) -> None:
    """Test non-zero exit code handling in execute_with_fault_isolation."""
    broker = ProcessFaultIsolationBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute_with_fault_isolation(
            [sys.executable, "-c", "import sys; sys.stderr.write('ISOLATED_ERR'); sys.exit(7)"],
            job_name="unit_isolation_failure",
            required_disk_gb=0.01,
        )
        assert exit_code == 7
    finally:
        broker.close()


def test_execute_with_fault_isolation_timeout(tmp_path: Path) -> None:
    """Test timeout enforcement in execute_with_fault_isolation."""
    broker = ProcessFaultIsolationBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute_with_fault_isolation(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            job_name="unit_isolation_timeout",
            timeout=0.5,
            required_disk_gb=0.01,
        )
        assert exit_code == -124
    finally:
        broker.close()


# =====================================================================
# 2. CLI Parser and Entrypoint Tests
# =====================================================================

def test_build_cli_parser() -> None:
    """Test CLI argument parser configuration."""
    parser = build_cli_parser()
    args = parser.parse_args(["--cmd", "echo test", "--timeout", "120", "--reap-zombies"])
    assert args.cmd == "echo test"
    assert args.timeout == 120.0
    assert args.reap_zombies is True
    assert args.show_cpu_topology is False
    assert args.check_quota is None


def test_cli_main_show_cpu_topology(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI --show-cpu-topology execution path."""
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker", "--show-cpu-topology"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "Host CPU Topology:" in captured.out
    assert "logical_cores" in captured.out


def test_cli_main_reap_zombies(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI --reap-zombies execution path."""
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker", "--reap-zombies"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "Reaped" in captured.out


def test_cli_main_check_quota_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI --check-quota passing when requesting a reasonable quota."""
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker", "--check-quota", "0.01", "--cwd", str(tmp_path)])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "Disk quota verification passed" in captured.out


def test_cli_main_check_quota_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI --check-quota failing when requesting an impossible quota."""
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker", "--check-quota", "999999.0", "--cwd", str(tmp_path)])
    ret = main()
    assert ret == 1
    captured = capsys.readouterr()
    assert "Disk quota check failed" in captured.err


def test_cli_main_execute_cmd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test CLI --cmd execution."""
    cmd_str = f'"{sys.executable}" -c "print(98765)"'
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker", "--cmd", cmd_str, "--cwd", str(tmp_path)])
    ret = main()
    assert ret == 0


def test_cli_main_default_banner(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI default output when no command is specified."""
    monkeypatch.setattr(sys, "argv", ["cochem_subprocess_broker"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "CoChem Subprocess Broker armed" in captured.out
