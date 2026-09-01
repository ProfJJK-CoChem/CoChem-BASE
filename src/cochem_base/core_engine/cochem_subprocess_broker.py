#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 3.0 / SRS Doc8_03 - Dedicated Process Reaper & Fault Isolation Broker.

Referenced in SRS Doc8_03 (Doc8_03_subprocess_broker_prompt.md) as the dedicated process reaper
and fault isolation broker for computational chemistry binary executions (ORCA, CFOUR, xTB, CREST, PySCF).
Provides robust cross-platform subprocess management, process group & Win32 Job Object isolation,
10-second grace period recursive tree termination, atexit zombie reaping, OOM preemption polling,
crash hex-dump extraction, NUMA-aware thread pinning, pre-flight storage quota checks,
and ZeroMQ heartbeat telemetry.

Unified with `core_engine.cochem_core_subprocess_broker`.
"""

from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

# Import unified implementation from core_engine.cochem_core_subprocess_broker
try:
    from core_engine.cochem_core_subprocess_broker import (
        CRITICAL_SEGFAULT_EXIT_CODES,
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
        verify_scratch_io,
        verify_scratch_quota_and_io,
    )
except ImportError:
    # Fallback to local import if package structure is flat
    from cochem_core_subprocess_broker import (  # type: ignore[no-redef]
        CRITICAL_SEGFAULT_EXIT_CODES,
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
        verify_scratch_io,
        verify_scratch_quota_and_io,
    )

logger = logging.getLogger("CoChem-SubprocessBroker")


# =============================================================================
# DEDICATED PROCESS REAPER & FAULT ISOLATION EXTENSIONS
# =============================================================================

class ProcessFaultIsolationBroker(SubprocessBroker):
    """
    Dedicated process reaper and fault isolation broker for computational chemistry.
    Extends SubprocessBroker with specialized fault isolation, telemetry logging,
    and automatic cleanup of crashed or orphaned compute jobs.
    """

    def __init__(
        self,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        memory_limit_gb: float = 8.0,
        total_ram_threshold_gb: float = 128.0,
        enable_job_object: bool = True,
    ) -> None:
        super().__init__(
            cwd=cwd,
            env=env,
            memory_limit_gb=memory_limit_gb,
            total_ram_threshold_gb=total_ram_threshold_gb,
        )
        self.enable_job_object = enable_job_object

    def execute_with_fault_isolation(
        self,
        command: Union[str, List[str]],
        job_name: str = "quantum_job",
        timeout: Optional[float] = None,
        cpu_affinity: Optional[List[int]] = None,
        required_disk_gb: float = 0.05,
        dead_man_timeout: float = 60.0,
        daemonize_on_timeout: bool = False,
    ) -> int:
        """
        Executes a calculation payload inside a fault-isolated sandbox with
        dead-man's switch watchdog, crash hex-dump telemetry, and automatic
        process tree reaping on failure.
        """
        logger.info(f"Executing '{job_name}' under ProcessFaultIsolationBroker...")
        return self.execute(
            payload_command=command,
            job_name=job_name,
            timeout=timeout,
            cpu_affinity=cpu_affinity,
            required_disk_gb=required_disk_gb,
            dead_man_timeout=dead_man_timeout,
            daemonize_on_timeout=daemonize_on_timeout,
        )


# Alias for backward and SRS Doc8_03 compatibility
DedicatedProcessReaper = ZombieReaper
FaultIsolationBroker = ProcessFaultIsolationBroker


# =============================================================================
# CLI INTERFACE
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds command-line argument parser for cochem_subprocess_broker."""
    parser = argparse.ArgumentParser(
        description="CoChem Subprocess Broker: Process Reaper, Fault Isolation & Execution Sandbox."
    )
    parser.add_argument(
        "--cmd",
        type=str,
        default=None,
        help="Command to execute inside the isolated broker sandbox.",
    )
    parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory for command execution.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Maximum execution timeout in seconds.",
    )
    parser.add_argument(
        "--reap-zombies",
        action="store_true",
        help="Immediately sweep and terminate all dangling zombie processes.",
    )
    parser.add_argument(
        "--show-cpu-topology",
        action="store_true",
        help="Detect and display physical host CPU topology and NUMA nodes.",
    )
    parser.add_argument(
        "--check-quota",
        type=float,
        default=None,
        help="Assert scratch disk quota in GB at target working directory.",
    )
    return parser


def main() -> int:
    """Main CLI entrypoint for standalone invocation."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.show_cpu_topology:
        topo = detect_cpu_topology()
        print(f"Host CPU Topology: {topo}")
        return 0

    if args.reap_zombies:
        count = cleanup_zombie_processes()
        print(f"Reaped {count} zombie process tree(s).")
        return 0

    if args.check_quota is not None:
        target_dir = Path(args.cwd) if args.cwd else Path.cwd()
        try:
            verify_scratch_quota_and_io(target_dir, required_gb=args.check_quota)
            print(f"Disk quota verification passed ({args.check_quota} GB required).")
            return 0
        except DiskQuotaError as exc:
            print(f"Disk quota check failed: {exc}", file=sys.stderr)
            return 1

    if args.cmd:
        try:
            completed = safe_subprocess_run(
                args.cmd,
                cwd=args.cwd,
                timeout=args.timeout,
                check=False,
                capture_output=False,
            )
            return completed.returncode
        except Exception as exc:
            print(f"Execution error: {exc}", file=sys.stderr)
            return 1

    print("CoChem Subprocess Broker armed. Use --help for usage instructions.")
    return 0


__all__ = [
    "SubprocessBroker",
    "ProcessFaultIsolationBroker",
    "FaultIsolationBroker",
    "DedicatedProcessReaper",
    "safe_subprocess_run",
    "register_popen_process",
    "unregister_popen_process",
    "get_active_popen_processes",
    "cleanup_zombie_processes",
    "kill_process_tree",
    "enforce_cpu_affinity",
    "detect_cpu_topology",
    "CPUTopologyManager",
    "detect_mpi_environment",
    "sanitize_mpi_environment",
    "verify_scratch_io",
    "verify_scratch_quota_and_io",
    "lock_directory_permissions",
    "RAMDiskOverlayManager",
    "ZMQHeartbeatManager",
    "DeadMansSwitchWatchdog",
    "WindowsJobObject",
    "ZombieReaper",
    "DiskQuotaError",
    "extract_segfault_hex_dump",
    "sweep_crash_hex_dump",
    "is_crash_returncode",
    "CRITICAL_SEGFAULT_EXIT_CODES",
    "HAS_PSUTIL",
    "HAS_ZMQ",
    "build_cli_parser",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
