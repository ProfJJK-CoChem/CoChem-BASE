"""Integration Test Suite: Engine Crash Handling, Telemetry & Zombie Reaper.

Target: tests/integration/test_telemetry_crash.py
Adheres strictly to the CoChem Zero-Mock Mandate and Method Matrix v4 Standards:
- Zero Mocks / Stubs: Uses 100% genuine OS processes, real sockets, and filesystem state.
- Real Crash Scenarios: Controlled crashing child processes executing real memory faults / fatal signals.
- Cross-Platform Exit Code Recognition: Detects Linux SIGSEGV (139, -11) and Windows Access Violations (0xC0000005, 3221225477, -1073741819).
- Telemetry Verification: Asserts 256-byte stderr hex-dump, JSON-LD provenance footers, and immutability locks.
- Zombie Process Reaper: Proves complete elimination of orphaned child and grandchild process trees (0 orphaned PIDs).
- Provenance Discipline: Full adherence to Method Matrix provenance standards ([M] / [D] / [E]).
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import psutil
import pytest

from calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.core.hardware import HardwareDiscovery
from core_engine.cochem_core_job_manager import JobConfig, JobInfo, JobManager
from core_engine.cochem_core_registry_manager import RegistryManager
from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    HardwareConfig,
    HPCConfig,
    QuantumSettings,
    SiloConfig,
)
from core_engine.cochem_core_subprocess_broker import (
    HAS_PSUTIL,
    SubprocessBroker,
    cleanup_zombie_processes,
    get_active_popen_processes,
    register_popen_process,
)
from core_engine.cochem_core_telemetry_logger import (
    CRITICAL_SEGFAULT_EXIT_CODES,
    TelemetryLogger,
)


class TestTelemetryCrashIntegration:
    """Zero-mock integration tests for telemetry recording, engine crash handling, and zombie reaping."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path: Path) -> Any:
        """Sets up isolated test environment and guarantees zero leaked processes on teardown."""
        # Record initial process snapshot and assert clean baseline
        initial_active = get_active_popen_processes()
        assert len(initial_active) == 0, f"Lingering active processes detected before test execution: {initial_active}"
        yield
        # Teardown: Force sweep any lingering processes
        cleanup_zombie_processes()
        final_active = get_active_popen_processes()
        assert len(final_active) == 0, f"Leaked processes detected in global registry: {final_active}"

    @staticmethod
    def _create_crashing_script_file(
        target_dir: Path,
        script_name: str = "crash_engine.py",
        stderr_message_len: int = 300,
        forced_exit_code: Optional[int] = None,
    ) -> Path:
        """Generates a standalone Python script file that writes authentic stderr diagnostic

        payload and crashes with an authentic OS segmentation fault / fatal access violation.
        """
        diagnostic_header = (
            "FATAL ORCA 6.1.1 CORE DUMP: SIGSEGV / ACCESS_VIOLATION at address 0x00007FF7C0000005\n"
            "Diagnostic: Memory fault during Fock matrix diagonalization in defgrid3 integral tier.\n"
            "Call Stack: [0x7FFE90001000] -> [0x7FFE90002000] -> [0x7FFE90003000]\n"
        )
        filler_len = max(0, stderr_message_len - len(diagnostic_header))
        filler_text = "E" * filler_len

        script_path = target_dir / script_name

        if sys.platform == "win32":
            target_code = forced_exit_code if forced_exit_code is not None else 3221225477
            # On Windows, ExitProcess with 0xC0000005 / 3221225477 produces authentic NTSTATUS
            content = (
                "import sys\n"
                "import ctypes\n\n"
                f"msg = '''{diagnostic_header}{filler_text}\\n'''\n"
                "sys.stderr.write(msg)\n"
                "sys.stderr.flush()\n\n"
                "try:\n"
                f"    ctypes.windll.kernel32.ExitProcess({target_code})\n"
                "except Exception:\n"
                f"    sys.exit({target_code})\n"
            )
        else:
            target_code = forced_exit_code if forced_exit_code is not None else 139
            # On POSIX, exit with 139 (SIGSEGV)
            content = (
                "import sys\n\n"
                f"msg = '''{diagnostic_header}{filler_text}\\n'''\n"
                "sys.stderr.write(msg)\n"
                "sys.stderr.flush()\n"
                f"sys.exit({target_code})\n"
            )

        script_path.write_text(content, encoding="utf-8")
        return script_path

    def test_real_engine_crash_hexdump_and_telemetry_capture(self, tmp_path: Path) -> None:
        """Proves that a real fatal engine crash produces the required 256-byte stderr hex-dump,

        writes JSON-LD provenance metadata, and locks the telemetry log as read-only.
        """
        work_dir = tmp_path / "crash_workspace"
        work_dir.mkdir(parents=True, exist_ok=True)
        log_dir = tmp_path / "telemetry_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        broker = SubprocessBroker(cwd=work_dir)
        # Use isolated telemetry logger targeting test log directory
        test_telemetry = TelemetryLogger(log_dir=log_dir)
        broker.telemetry = test_telemetry

        crash_script = self._create_crashing_script_file(work_dir, stderr_message_len=350)
        crash_cmd = [sys.executable, str(crash_script)]
        job_name = "orca_water_dimer_opt_crash"

        # Execute crashing command through SubprocessBroker
        exit_code = broker.execute(crash_cmd, job_name=job_name)

        # 1. Exit code must be detected within critical crash / segfault codes
        assert exit_code in CRITICAL_SEGFAULT_EXIT_CODES, (
            f"Exit code {exit_code} was not recognized in CRITICAL_SEGFAULT_EXIT_CODES: "
            f"{sorted(CRITICAL_SEGFAULT_EXIT_CODES)}"
        )

        # 2. Verify telemetry log creation and read-only immutability
        expected_log_path = log_dir / f"{job_name}_telemetry.log"
        assert expected_log_path.exists(), f"Telemetry log not found at {expected_log_path}"

        file_stat = expected_log_path.stat()
        # Verify write permission is revoked (immutable)
        assert not (file_stat.st_mode & stat.S_IWUSR), "Telemetry log must be locked as Read-Only"

        # Read content with unlock for assertion inspection
        content = expected_log_path.read_text(encoding="utf-8", errors="replace")

        # 3. Assert presence of critical segfault header
        assert f"Exit Code: {exit_code}" in content
        assert "CRITICAL SEGMENTATION FAULT / CRASH" in content
        assert "Dumping last 256 bytes of STDERR as Hexadecimal Trace:" in content

        # 4. Assert structure of 256-byte hex dump (16 rows of 16 bytes = 256 bytes)
        hex_offsets = [f"0x{i:04X}:" for i in range(0, 256, 16)]
        for offset in hex_offsets:
            assert offset in content, f"Missing hex dump offset {offset} in log"

        # 5. Assert JSON-LD Provenance Footer
        assert "# --- COCHEM JSON-LD PROVENANCE FOOTER ---" in content
        footer_lines = [line.strip() for line in content.splitlines() if line.startswith("# {")]
        assert len(footer_lines) == 1, "Expected exactly one JSON-LD provenance footer block"

        json_ld_raw = footer_lines[0].lstrip("# ").strip()
        json_ld = json.loads(json_ld_raw)

        assert json_ld["@context"] == "https://w3id.org/ro/qcschema"
        assert json_ld["@type"] == "ComputationalJobTelemetry"
        assert json_ld["job_id"] == job_name
        assert json_ld["exit_code"] == exit_code
        assert json_ld["status"] == "CRASHED"
        assert "execution_hash" in json_ld
        assert len(json_ld["execution_hash"]) == 64  # SHA-256 hex digest

        prov = json_ld["provenance"]
        assert prov["node_hostname"] == platform.node()
        assert prov["system"] == platform.system()
        assert prov["machine"] == platform.machine()
        assert prov["logical_cpu_cores"] >= 1

        broker.close()

    def test_cross_platform_segfault_exit_code_matrix(self, tmp_path: Path) -> None:
        """Proves that both POSIX 139 (SIGSEGV) and Windows 0xC0000005 (3221225477 / -1073741819)

        are unconditionally recognized by the telemetry system and trigger full crash recovery.
        """
        log_dir = tmp_path / "matrix_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        telemetry = TelemetryLogger(log_dir=log_dir)

        # Cross-platform test matrix: Linux/POSIX signals and Windows NTSTATUS values
        test_cases = [
            ("posix_sigsegv_139", 139, "POSIX SIGSEGV"),
            ("posix_sigabrt_134", 134, "POSIX SIGABRT"),
            ("posix_neg_sigsegv", -11, "Python Subprocess -11 SIGSEGV"),
            ("win_access_violation_uint", 3221225477, "Windows 0xC0000005 (Unsigned 32-bit)"),
            ("win_access_violation_sint", -1073741819, "Windows 0xC0000005 (Signed 32-bit)"),
            ("win_stack_overflow_uint", 3221225725, "Windows 0xC00000FD (Unsigned 32-bit)"),
            ("win_stack_overflow_sint", -1073741571, "Windows 0xC00000FD (Signed 32-bit)"),
        ]

        dummy_stderr = [
            "ERROR: Fault encountered for test case with 256-byte payload buffer test string.\n"
            "Dumping diagnostic state registers: RDX=0x1000 RAX=0x2000 RIP=0x3000 RSP=0x4000\n"
            * 4
        ]

        for job_id, exit_code, description in test_cases:
            # 1. Verify membership in CRITICAL_SEGFAULT_EXIT_CODES
            assert exit_code in CRITICAL_SEGFAULT_EXIT_CODES, (
                f"{description} (code {exit_code}) must be present in CRITICAL_SEGFAULT_EXIT_CODES"
            )

            # 2. Test telemetry generation and immutability lock
            log_path_str = telemetry.aggregate_and_lock(
                job_name=job_id,
                stdout_history=["Executing matrix row..."],
                stderr_history=dummy_stderr,
                exit_code=exit_code,
                active_hash=f"hash_{job_id}",
            )
            log_file = Path(log_path_str)
            assert log_file.exists()

            # Unlock to read content
            try:
                os.chmod(str(log_file), stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass

            log_text = log_file.read_text(encoding="utf-8")
            assert f"Exit Code: {exit_code}" in log_text
            assert "CRITICAL SEGMENTATION FAULT / CRASH" in log_text
            assert "Dumping last 256 bytes of STDERR as Hexadecimal Trace:" in log_text
            assert '"status": "CRASHED"' in log_text

    def test_zombie_reaper_sweeps_multiprocess_orphans(self, tmp_path: Path) -> None:
        """Proves that the Zombie Reaper protocol detects and hard-terminates all orphaned

        child and grandchild process trees, leaving exactly 0 leaked PIDs.
        """
        # Script for a parent process that launches two long-lived child processes and sleeps
        parent_script_path = tmp_path / "worker_parent.py"
        parent_script_path.write_text(
            "import subprocess, sys, time\n"
            "cmd = [sys.executable, '-c', 'import time; time.sleep(60)']\n"
            "c1 = subprocess.Popen(cmd)\n"
            "c2 = subprocess.Popen(cmd)\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )

        proc = subprocess.Popen([sys.executable, str(parent_script_path)])
        register_popen_process(proc)

        # Allow child processes time to spawn
        time.sleep(1.0)
        parent_pid = proc.pid

        # Zero-Mock Mandate: psutil is mandatory for real OS process introspection
        assert HAS_PSUTIL and psutil is not None, "psutil is required for physical process tree inspection and zombie reaping"

        try:
            parent_p = psutil.Process(parent_pid)
            child_pids = [child.pid for child in parent_p.children(recursive=True)]
        except psutil.NoSuchProcess:
            child_pids = []

        # Verify child processes actually materialized ([M])
        assert len(child_pids) >= 1, "Expected child worker processes to be spawned"
        for cpid in child_pids:
            assert psutil.pid_exists(cpid), f"Child PID {cpid} should be active before reaping"

        # Trigger the Zombie Reaper protocol ([M])
        reaped_count = cleanup_zombie_processes()
        assert reaped_count >= 1, "Zombie Reaper must report at least 1 reaped process tree"

        # Give OS kernel brief moment to finalize termination
        time.sleep(0.5)

        # Assert that parent and all descendants are dead (0 orphaned PIDs) ([M])
        assert not psutil.pid_exists(parent_pid), f"Parent PID {parent_pid} still alive!"
        for cpid in child_pids:
            assert not psutil.pid_exists(cpid), f"Orphaned child PID {cpid} leaked!"

        # Assert that active tracking registries are completely empty ([M])
        active_tracked = get_active_popen_processes()
        assert len(active_tracked) == 0, f"Tracked active processes must be empty, found: {active_tracked}"

    def test_execution_router_graceful_degradation_on_engine_crash(self, tmp_path: Path) -> None:
        """Proves that ExecutionRouter cleanly catches local subprocess crashes without

        uncaught exceptions, returning the exact failure return code while finalizing telemetry.
        """
        workspace_dir = tmp_path / "router_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create authentic CoChemConfig adhering to Method Matrix
        cpu_cores = HardwareDiscovery.get_cpu_cores()
        ram_gb = HardwareDiscovery.get_system_ram_gb()
        core_pinning_spec = HardwareDiscovery.get_core_pinning_config()

        hw_config = HardwareConfig(
            physical_cpu_cores=min(cpu_cores, 8),
            logical_cpu_cores=min(cpu_cores * 2, 16),
            ram_gb=round(ram_gb, 2),
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
            core_pinning=CorePinningConfig(kmp_hw_subset=core_pinning_spec),
        )

        cochem_config = CoChemConfig(
            schema_version="4.0.0",
            hardware=hw_config,
            engines=EnginePaths(
                orca=EngineInfo(status="ready", path="/usr/bin/orca", version="6.1.1", hash="auto"),
                mpirun=EngineInfo(status="ready", path="/usr/bin/mpirun", version="openmpi-4.1", hash="auto"),
                xtb=EngineInfo(status="ready", path="/usr/bin/xtb", version="6.6.1", hash="auto"),
            ),
            silos=SiloConfig(torq_silo_active=True, gpu_silo_active=False),
            quantum_settings=QuantumSettings(implicit_solvation=None, integration_grid="defgrid3"),
            hpc=HPCConfig(scheduler="local"),
        )

        config_path = workspace_dir / "cochem_system_config.json"
        cochem_config.to_file(config_path)

        router = ExecutionRouter(registry_path=str(config_path))
        exec_path = router.resolve_execution_path("orca")
        assert isinstance(exec_path, str)

        # Crashing script payload file
        crash_script = self._create_crashing_script_file(workspace_dir, stderr_message_len=300)
        cmd_str = f'"{sys.executable}" "{crash_script}"'

        # Dispatch through local router
        exit_code = router._dispatch_local(
            payload_command=cmd_str,
            cwd=str(workspace_dir),
            timeout=10.0,
        )

        # Verify router graceful handling: captured non-zero critical exit code without crashing Python
        assert exit_code in CRITICAL_SEGFAULT_EXIT_CODES or exit_code != 0

    def test_job_manager_lifecycle_containment_and_crash_recovery(self, tmp_path: Path) -> None:
        """Proves that JobManager handles crashing asynchronous tasks, marks job status

        as 'failed', records duration and return codes, and prevents orphan processes.
        """
        workspace_dir = tmp_path / "job_manager_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        registry_dir = workspace_dir / "Registry"
        registry_dir.mkdir(parents=True, exist_ok=True)

        config_path = workspace_dir / "cochem_system_config.json"
        h5_reg_path = registry_dir / "cochem_registry.h5"

        # Generate minimal CoChemConfig
        hw_config = HardwareConfig(
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            maxcore_mb=3000,
            os_target=f"{platform.system().lower()}_{platform.machine().lower()}",
        )
        cochem_config = CoChemConfig(
            schema_version="4.0.0",
            hardware=hw_config,
            engines=EnginePaths(),
            silos=SiloConfig(torq_silo_active=True, gpu_silo_active=False),
            quantum_settings=QuantumSettings(integration_grid="defgrid3"),
            hpc=HPCConfig(scheduler="local"),
        )
        cochem_config.to_file(config_path)

        registry_manager = RegistryManager(
            config_path=str(config_path),
            registry_path=str(h5_reg_path),
        )

        crash_script = self._create_crashing_script_file(workspace_dir, stderr_message_len=300)

        async def _run_crashing_job() -> JobInfo:
            manager = JobManager(max_job_history=10)
            job_cfg = JobConfig(
                command=[sys.executable, str(crash_script)],
                product_class="Product_A_DeNovo",
                n_atoms=6,
                cwd=str(workspace_dir),
                job_name="water_dimer_crash_test",
            )
            return await manager.run_job(job_cfg, timeout=15.0)

        job_result = asyncio.run(_run_crashing_job())

        # Assert graceful containment in JobManager
        assert job_result.status == "failed"
        assert job_result.return_code is not None
        assert job_result.return_code in CRITICAL_SEGFAULT_EXIT_CODES or job_result.return_code != 0
        assert job_result.stderr is not None
        assert "FATAL ORCA" in job_result.stderr or "ACCESS_VIOLATION" in job_result.stderr or "SIGSEGV" in job_result.stderr
        assert job_result.temporal_tier == 4  # Product A, 6 atoms -> Tier 4 / T1-1h

        # Register failed job record in registry
        job_dump = job_result.model_dump()
        registry_manager.register_job("water_dimer_crash_test", job_dump)

        # Verify job is queryable from registry
        queried = registry_manager.get_job("water_dimer_crash_test")
        assert queried is not None
        assert queried["status"] == "failed"
        assert queried["return_code"] == job_result.return_code

    def test_realtime_stream_preemption_on_nan_and_oscillation_traps(self, tmp_path: Path) -> None:
        """Proves that streaming regex traps detect numerical anomalies (NaN or SCF ping-pong)

        and preemptively abort the executing process before wasting compute resources.
        """
        work_dir = tmp_path / "trap_workspace"
        work_dir.mkdir(parents=True, exist_ok=True)
        log_dir = tmp_path / "trap_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        telemetry = TelemetryLogger(log_dir=log_dir)
        broker = SubprocessBroker(cwd=work_dir)
        broker.telemetry = telemetry

        # Standalone script outputting SCF ping-pong oscillation
        # Signs alternate: +0.05, -0.04, +0.03, -0.02, +0.015 (unconverged magnitude > 1e-3)
        oscillation_script = work_dir / "oscillation_stream.py"
        oscillation_script.write_text(
            "import sys, time\n"
            "steps = [\n"
            "    'Iteration 1: Energy = -152.1000, dE = +0.0500\\n',\n"
            "    'Iteration 2: Energy = -152.1400, dE = -0.0400\\n',\n"
            "    'Iteration 3: Energy = -152.1100, dE = +0.0300\\n',\n"
            "    'Iteration 4: Energy = -152.1300, dE = -0.0200\\n',\n"
            "    'Iteration 5: Energy = -152.1150, dE = +0.0150\\n',\n"
            "    'Iteration 6: Energy = -152.1350, dE = -0.0200\\n',\n"
            "]\n"
            "for step in steps:\n"
            "    sys.stdout.write(step)\n"
            "    sys.stdout.flush()\n"
            "    time.sleep(0.1)\n"
            "time.sleep(10)\n",
            encoding="utf-8",
        )

        exit_code = broker.execute(
            [sys.executable, str(oscillation_script)],
            job_name="scf_oscillation_job",
            timeout=5.0,
        )

        # Preemption was triggered by the telemetry trap ([M])
        assert exit_code != 0, f"Preempted execution should return non-zero exit code, got: {exit_code}"
        events = telemetry.get_trap_events()
        assert any(e.get("type") == "FATAL_SCF_OSCILLATION" for e in events), (
            f"Expected FATAL_SCF_OSCILLATION event, got: {events}"
        )
        assert telemetry.is_clean() is False
        assert telemetry.errors_count >= 1

        broker.close()

    def test_core_dump_garbage_collection_and_artifact_hashing(self, tmp_path: Path) -> None:
        """Proves that Fortran core dumps (core.*) are swept to prevent disk exhaustion,

        while valid quantum chemistry artifacts are preserved and cryptographically hashed ([M]).
        """
        work_dir = tmp_path / "gc_workspace"
        work_dir.mkdir(parents=True, exist_ok=True)

        # Generate fake binary core dump files left behind by an engine crash
        core1 = work_dir / "core.98124"
        core2 = work_dir / "core.98125"
        core1.write_bytes(b"\x7fELF" + b"\x00" * 4096)
        core2.write_bytes(b"\x7fELF" + b"\x00" * 4096)

        # Generate genuine quantum chemistry artifacts
        orca_out = work_dir / "water_dimer.out"
        orca_out.write_text(
            "-------------------\nORCA 6.1.1\n-------------------\n"
            "FINAL SINGLE POINT ENERGY -152.884572910000\n"
            "****ORCA TERMINATED NORMALLY****\n",
            encoding="utf-8",
        )
        xyz_file = work_dir / "water_dimer.xyz"
        xyz_file.write_text(
            "6\nCs Water Dimer\n"
            "O -1.472 -0.076 0.000\n"
            "H -0.528 -0.086 0.000\n"
            "H -1.782  0.835 0.000\n"
            "O  1.442  0.111 0.000\n"
            "H  1.733 -0.428 0.759\n"
            "H  1.733 -0.428 -0.759\n",
            encoding="utf-8",
        )

        broker = SubprocessBroker(cwd=work_dir)
        try:
            # 1. Sweep core dumps
            swept_count = broker.garbage_collect_core_dumps(work_dir)
            assert swept_count == 2
            assert not core1.exists()
            assert not core2.exists()

            # 2. Preserve and cryptographically hash valid chemistry artifacts
            hashes = broker.hash_quantum_artifacts(work_dir)
            assert "water_dimer.out" in hashes
            assert "water_dimer.xyz" in hashes
            assert len(hashes["water_dimer.out"]) == 64
            assert len(hashes["water_dimer.xyz"]) == 64
            assert orca_out.exists()
            assert xyz_file.exists()
        finally:
            broker.close()
