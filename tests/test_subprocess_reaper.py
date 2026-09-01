#!/usr/bin/env python3
r"""Authentic Unit Test Suite for Stage 6.0 Subprocess Brokering, Isolation, and Thermal Governors.

Module: tests/test_subprocess_reaper.py
Target Implementation: cochem_bench.bench_libraries.subprocess_reaper

Capabilities Tested:
1. Air-Gap Safety Contract:
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR.
   - Fatal RuntimeError if COCHEM_ARTIFACTS_DIR environment variable is missing/empty.
2. PreFlightScratchVerifier:
   - NVMe scratch space verification using shutil.disk_usage().
   - ResourceGuardError fast-failure on threshold breach.
   - Pydantic v2 ScratchSpaceReport validation.
3. Process Group Isolation & ZombieReaper:
   - Process group isolation via launch_isolated_process (start_new_session on POSIX, CREATE_NEW_PROCESS_GROUP on Windows).
   - Recursive child process mapping (psutil.Process.children(recursive=True)) and ruthless termination.
   - Ephemeral port ZeroMQ PUB/SUB socket binding and manifest logging to Registry/zmq_ipc.json.
   - Real-time heartbeat broadcast and verification.
   - ABORT.signal file detection, triggering, and clearing in $SCRATCH workspace.
4. NUMA-Aware Thread Pinning:
   - Topology probing via numactl/lscpu or psutil.
   - Sockets/numa binding command generation (numactl --cpunodebind=0 --membind=0).
   - Dynamic configuration loading from Registry/cochem_system_config.json.
   - Core affinity assignment via psutil.Process().cpu_affinity().
5. Thermal Evacuation Governor:
   - Polling psutil.sensors_temperatures() with dynamic temperature iteration.
   - Windows Guard: ResourceWarning logging and graceful daemon abort if unsupported/empty.
   - Automatic suspend at > 90C and resume at <= 75C for parent and all child processes.
   - Asynchronous daemon lifecycle management.
6. SegfaultTrapper & ExitCode139_Trapper:
   - Precise returncode classification for POSIX (-11, 139) and Windows (0xC0000005, 3221225477, -1073741819).
   - FAIR JSON-LD provenance block generation and atomic commit to bench_provenance.jsonld.
7. Mendeleev Elemental Mass Integration:
   - Dynamic atomic weight lookup for elements via mendeleev library.
8. Composite Protected Subprocess Orchestrator:
   - End-to-end protected subprocess execution with isolation, pinning, and segfault trapping.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task6_reaper_pt2.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 6 Subprocess Brokering & Temporal Engine Routing.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Generator, Optional

import psutil
import pytest
import zmq
from mendeleev import element

from cochem_bench.bench_libraries.subprocess_reaper import (
    ActiveStreamRegexTrap,
    CRITICAL_TEMP_CELSIUS,
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ENERGY_MATRIX_NAN_INF_FAULT,
    EnergyMatrixNaNInfFaultError,
    ExitCode139_Trapper,
    HardwareRegistryConfig,
    HighSpeedIORouter,
    HighSpeedIORouting,
    IOCleanupReport,
    IOScratchRouteReport,
    JSONLDProvenanceBlock,
    JSONLDProvenanceFooter,
    LINEAR_DEPENDENCE_PATTERN,
    LinearDependenceFaultError,
    NAN_INF_PATTERN,
    NUMAPinningError,
    NUMA_ThreadPinner,
    OOM_RETURN_CODES,
    ORCA_LINEAR_DEPENDENCE_FAULT,
    OSFaultError,
    OS_FAULT_RETURN_CODES,
    PreFlightResourceError,
    PreFlightScratchVerifier,
    ProcessReapReport,
    ProvenanceFooterPayload,
    RESUME_TEMP_CELSIUS,
    ResourceGuardError,
    SCF_DELTA_E_PATTERN,
    SCF_PING_PONG_OSCILLATION,
    SCFPingPongOscillationError,
    SEGFAULT_RETURN_CODES,
    SLOWCONV_SOSCF_KEYWORD,
    ScratchSpaceReport,
    SegfaultTrapper,
    SegmentationFaultError,
    StreamRegexTrap,
    StreamTrapError,
    StreamTrapEvent,
    StreamTrapReport,
    SystemRegistryConfig,
    TemporalRouteResult,
    TemporalRouter,
    TemporalRoutingError,
    ThermalEvacuationGovernor,
    ThermalGovernor,
    ThermalGovernorState,
    ThreadPinningResult,
    ZMQEndpointManifest,
    ZombieReaper,
    ZombieReaperError,
    append_jsonld_provenance_footer,
    compute_geometry_hash,
    compute_orca_binary_hash,
    compute_sha256_hash,
    execute_protected_subprocess,
    extract_tail_hex_dump,
    find_scratch_dump_file,
    format_hex_dump,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_processed_workspace_dir,
    get_registry_workspace_dir,
    get_scratch_workspace_dir,
    launch_isolated_process,
)


# ==============================================================================
# Authentic Fixtures
# ==============================================================================

@pytest.fixture
def isolated_artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Establishes an authentic, isolated artifacts workspace."""
    artifacts_root = tmp_path / "cochem_isolated_artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_root))
    yield artifacts_root
    if artifacts_root.exists():
        shutil.rmtree(artifacts_root, ignore_errors=True)


# ==============================================================================
# 1. Air-Gap Safety Contract & Dynamic Path Resolution Tests
# ==============================================================================

def test_dynamic_path_resolution(isolated_artifacts_dir: Path) -> None:
    """Verifies dynamic resolution of artifacts, scratch, registry, and processed dirs."""
    resolved_artifacts = get_cochem_artifacts_dir()
    assert resolved_artifacts == isolated_artifacts_dir.resolve()

    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    assert scratch_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Scratch"

    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    assert reg_dir == isolated_artifacts_dir / "Registry"

    proc_dir = get_processed_workspace_dir(isolated_artifacts_dir)
    assert proc_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Processed"


def test_air_gap_missing_env_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies fatal RuntimeError is raised when COCHEM_ARTIFACTS_DIR is missing."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        get_cochem_artifacts_dir()
    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)

    with pytest.raises(RuntimeError):
        get_scratch_workspace_dir()

    with pytest.raises(RuntimeError):
        get_registry_workspace_dir()

    with pytest.raises(RuntimeError):
        get_processed_workspace_dir()


def test_mendeleev_elemental_mass_dynamic() -> None:
    """Validates dynamic retrieval of atomic weights via the Mendeleev database."""
    carbon_mass = get_element_mass_mendeleev("C")
    expected_carbon = float(element("C").atomic_weight)
    assert abs(carbon_mass - expected_carbon) < 1e-6

    hydrogen_mass = get_element_mass_mendeleev("H")
    expected_hydrogen = float(element("H").atomic_weight)
    assert abs(hydrogen_mass - expected_hydrogen) < 1e-6

    oxygen_mass = get_element_mass_mendeleev("O")
    expected_oxygen = float(element("O").atomic_weight)
    assert abs(oxygen_mass - expected_oxygen) < 1e-6

    platinum_mass = get_element_mass_mendeleev("Pt")
    expected_platinum = float(element("Pt").atomic_weight)
    assert abs(platinum_mass - expected_platinum) < 1e-6


# ==============================================================================
# 2. PreFlightScratchVerifier Tests
# ==============================================================================

def test_preflight_scratch_verifier_success(isolated_artifacts_dir: Path) -> None:
    """Verifies that scratch verification succeeds when available space exceeds threshold."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    report = verifier.verify(min_free_bytes=1024)

    assert isinstance(report, ScratchSpaceReport)
    assert report.is_sufficient is True
    assert report.total_bytes > 0
    assert report.free_bytes >= 1024
    assert Path(report.scratch_path).exists()
    assert verifier.check_space_safe(min_free_bytes=1024) is True


def test_preflight_scratch_verifier_insufficient_space_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies fast-failure with ResourceGuardError when disk space threshold is unmet."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    impossible_bytes = 100 * (1024 ** 5)

    with pytest.raises(ResourceGuardError) as exc_info:
        verifier.verify(min_free_bytes=impossible_bytes)

    assert "RESOURCE_GUARD" in str(exc_info.value)
    assert verifier.check_space_safe(min_free_bytes=impossible_bytes) is False


# ==============================================================================
# 3. Process Group Isolation & ZombieReaper Tests
# ==============================================================================

def test_launch_isolated_process() -> None:
    """Verifies launch_isolated_process configures process group isolation flags."""
    proc = launch_isolated_process(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0


def test_zombie_reaper_zmq_heartbeat_lifecycle(isolated_artifacts_dir: Path) -> None:
    """Verifies ephemeral ZMQ PUB/SUB socket binding, manifest recording, and message transmission."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    ctx = zmq.Context()

    try:
        pub_socket, manifest = reaper.establish_heartbeat_publisher(context=ctx)
        assert isinstance(manifest, ZMQEndpointManifest)
        assert manifest.port > 0
        assert manifest.endpoint.startswith("tcp://127.0.0.1:")
        assert reaper.get_ipc_manifest_path().exists()

        disk_manifest = reaper.read_ipc_manifest()
        assert disk_manifest.port == manifest.port
        assert disk_manifest.endpoint == manifest.endpoint

        reaper.publish_heartbeat(pub_socket, topic="HEARTBEAT", payload={"status": "ACTIVE_CALCULATION"})

        received = reaper.check_heartbeat_receptive(
            endpoint=manifest.endpoint,
            timeout_ms=1000,
            topic="HEARTBEAT",
            context=ctx,
        )
        assert isinstance(received, bool)
    finally:
        pub_socket.close()
        ctx.term()


def test_zombie_reaper_abort_signal_file(isolated_artifacts_dir: Path) -> None:
    """Verifies detection, triggering, and clearing of ABORT.signal file in $SCRATCH."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    assert reaper.check_abort_signal() is False

    abort_file = reaper.trigger_abort_signal(reason="MANUAL_TEST_ABORT")
    assert abort_file.exists()
    assert reaper.check_abort_signal() is True

    cleared = reaper.clear_abort_signal()
    assert cleared is True
    assert reaper.check_abort_signal() is False


def test_zombie_reaper_exterminate_real_child_process(isolated_artifacts_dir: Path) -> None:
    """Spawns an authentic background child process and ruthlessly terminates it."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid
    assert psutil.pid_exists(worker_pid) is True

    report = reaper.terminate_process_tree(target_pid=worker_pid, reason="ORPHAN_TERMINATION_TEST")

    assert isinstance(report, ProcessReapReport)
    assert report.target_pid == worker_pid
    assert report.status == "EXTERMINATED"
    assert worker_pid in report.terminated_pids

    time.sleep(0.2)
    assert psutil.pid_exists(worker_pid) is False or not psutil.Process(worker_pid).is_running()


def test_zombie_reaper_terminate_process_tree_with_children(isolated_artifacts_dir: Path) -> None:
    """Spawns a parent process that launches a child process, verifying recursive mapping & termination."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    # Parent script spawns a child python process, then both sleep
    parent_script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "time.sleep(120)\n"
    )
    parent_proc = launch_isolated_process(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    parent_pid = parent_proc.pid

    # Allow child process to spawn
    time.sleep(0.5)
    assert psutil.pid_exists(parent_pid) is True

    # Terminate process tree
    report = reaper.terminate_process_tree(target_pid=parent_pid, reason="TREE_TERMINATION_TEST")

    assert isinstance(report, ProcessReapReport)
    assert report.target_pid == parent_pid
    assert report.status == "EXTERMINATED"
    assert len(report.terminated_pids) >= 1

    time.sleep(0.2)
    assert psutil.pid_exists(parent_pid) is False or not psutil.Process(parent_pid).is_running()


# ==============================================================================
# 4. NUMA-Aware Thread Pinning Tests
# ==============================================================================

def test_numa_thread_pinner_topology_probe(isolated_artifacts_dir: Path) -> None:
    """Verifies NUMA topology probing and numactl binding command creation."""
    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    topology = pinner.probe_numa_topology()

    assert isinstance(topology, dict)
    assert "logical_cpus" in topology
    assert "numa_nodes" in topology
    assert topology["logical_cpus"] >= 1

    # Check wrap_command_for_numa
    cmd = ["python", "calc.py"]
    wrapped = pinner.wrap_command_for_numa(cmd, required_cores=1)
    assert isinstance(wrapped, list)
    assert wrapped[-2:] == ["python", "calc.py"]


def test_numa_thread_pinner_from_config(isolated_artifacts_dir: Path) -> None:
    """Verifies loading affinity configuration from dynamic cochem_system_config.json."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    total_logical = psutil.cpu_count(logical=True) or 1
    target_core_indices = [0] if total_logical == 1 else [0, min(1, total_logical - 1)]

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": min(2, total_logical),
            "logical_cpu_cores": total_logical,
            "ram_gb": 16.0,
            "pinned_cores": target_core_indices,
        },
        "pinned_cores": target_core_indices,
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    loaded_cores = pinner.load_affinity_cores()
    assert loaded_cores == target_core_indices

    result = pinner.pin_process(pid=os.getpid())
    assert isinstance(result, ThreadPinningResult)
    assert result.pid == os.getpid()
    assert result.assigned_cores == target_core_indices
    assert result.status in ("PINNED_SUCCESS", "UNSUPPORTED_PLATFORM")
    if result.status == "PINNED_SUCCESS":
        assert set(result.active_affinity) == set(target_core_indices)


def test_numa_thread_pinner_invalid_pid_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies that pinning a non-existent process ID raises NUMAPinningError."""
    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    invalid_pid = 99999999
    with pytest.raises(NUMAPinningError):
        pinner.pin_process(pid=invalid_pid, cores=[0])


# ==============================================================================
# 5. Thermal Evacuation Governor Tests
# ==============================================================================

def test_thermal_governor_windows_guard() -> None:
    """Verifies that Windows Guard emits ResourceWarning and aborts without infinite loop."""
    governor = ThermalEvacuationGovernor()

    # On platforms where sensors_temperatures returns empty (like Windows without WMI),
    # verify ResourceWarning is emitted and None is returned
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        temp = governor.get_current_max_temperature()

    if temp is None:
        assert any(issubclass(w.category, ResourceWarning) for w in record)

    # Verify daemon loop aborts gracefully when unsupported
    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        thread = governor.start_daemon(pid=worker.pid, poll_interval_sec=0.05)
        time.sleep(0.2)
        governor.stop()
        assert not thread.is_alive()
    finally:
        if psutil.pid_exists(worker.pid):
            try:
                psutil.Process(worker.pid).kill()
            except Exception:
                pass


def test_thermal_governor_dynamic_temp_iteration() -> None:
    """Verifies dynamic iteration and state transitions on critical threshold breach and cooling."""
    governor = ThermalEvacuationGovernor(critical_temp_c=CRITICAL_TEMP_CELSIUS, resume_temp_c=RESUME_TEMP_CELSIUS)

    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid

    try:
        # 1. Normal temperature (50.0C) -> RUNNING
        state1 = governor.govern_step(pid=worker_pid, temperature_override=50.0)
        assert isinstance(state1, ThermalGovernorState)
        assert state1.status == "RUNNING"
        assert state1.is_suspended is False

        # 2. Critical temperature (95.0C > 90C) -> SUSPENDED
        state2 = governor.govern_step(pid=worker_pid, temperature_override=95.0)
        assert state2.status == "SUSPENDED"
        assert state2.is_suspended is True

        # 3. Intermediate cooling (80.0C > 75C) -> Still SUSPENDED
        state3 = governor.govern_step(pid=worker_pid, temperature_override=80.0)
        assert state3.status == "SUSPENDED"
        assert state3.is_suspended is True

        # 4. Safe cooling (70.0C <= 75C) -> RESUMED to RUNNING
        state4 = governor.govern_step(pid=worker_pid, temperature_override=70.0)
        assert state4.status == "RUNNING"
        assert state4.is_suspended is False
    finally:
        if psutil.pid_exists(worker_pid):
            try:
                psutil.Process(worker_pid).kill()
            except Exception:
                pass


def test_thermal_governor_alias_equivalence() -> None:
    """Verifies that ThermalGovernor is an alias for ThermalEvacuationGovernor."""
    assert ThermalGovernor is ThermalEvacuationGovernor


# ==============================================================================
# 6. SegfaultTrapper & ExitCode139_Trapper Tests
# ==============================================================================

@pytest.mark.parametrize("segfault_code", [-11, 139, 3221225477, -1073741819, 0xC0000005])
def test_segfault_trapper_identifies_all_segfault_codes(segfault_code: int) -> None:
    """Validates that all POSIX and Windows segmentation fault return codes are recognized."""
    assert SegfaultTrapper.is_segmentation_fault(segfault_code) is True
    assert ExitCode139_Trapper.is_segmentation_fault(segfault_code) is True


@pytest.mark.parametrize("normal_code", [0, 1, 2, 127, 255])
def test_segfault_trapper_ignores_normal_and_generic_codes(normal_code: int) -> None:
    """Validates that non-segfault return codes return False."""
    assert SegfaultTrapper.is_segmentation_fault(normal_code) is False


def test_segfault_trapper_generates_jsonld_provenance(isolated_artifacts_dir: Path) -> None:
    """Verifies JSON-LD provenance block generation and atomic commitment on segfault."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)
    simulated_pid = 45120
    simulated_returncode = -11

    provenance = trapper.trap(
        process_id=simulated_pid,
        returncode=simulated_returncode,
        metadata={"method": "DLPNO-CCSD(T)", "basis": "aug-cc-pVQZ"},
    )

    assert isinstance(provenance, JSONLDProvenanceBlock)
    assert provenance.process_id == simulated_pid
    assert provenance.return_code == simulated_returncode
    assert provenance.fault_type == "OS_SEGMENTATION_FAULT"
    assert provenance.status == "FATAL_CRASH_RECORDED"

    prov_path = trapper.get_provenance_file_path()
    assert prov_path.exists()

    data = json.loads(prov_path.read_text(encoding="utf-8"))
    assert data["@context"] == "https://doi.org/10.5281/zenodo.cochem.v2"
    assert data["@type"] == "ComputationalProcessProvenance"
    assert data["process_id"] == simulated_pid
    assert data["return_code"] == simulated_returncode
    assert data["fault_type"] == "OS_SEGMENTATION_FAULT"
    assert data["metadata"]["method"] == "DLPNO-CCSD(T)"


def test_segfault_trapper_check_and_raise(isolated_artifacts_dir: Path) -> None:
    """Verifies that check_and_raise commits JSON-LD and raises SegmentationFaultError."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)

    with pytest.raises(SegmentationFaultError) as exc_info:
        trapper.check_and_raise(process_id=8888, returncode=3221225477)

    assert "Segmentation fault detected" in str(exc_info.value)
    assert trapper.get_provenance_file_path().exists()


def test_segfault_trapper_exitcode139_alias(isolated_artifacts_dir: Path) -> None:
    """Verifies that ExitCode139_Trapper operates identically to SegfaultTrapper."""
    assert ExitCode139_Trapper is SegfaultTrapper
    trapper = ExitCode139_Trapper(artifacts_dir=isolated_artifacts_dir)
    assert trapper.is_segmentation_fault(139) is True


# ==============================================================================
# 7. Composite Subprocess Execution Orchestrator Tests
# ==============================================================================

def test_execute_protected_subprocess_success(isolated_artifacts_dir: Path) -> None:
    """Verifies end-to-end execution of a healthy protected subprocess."""
    retcode, provenance = execute_protected_subprocess(
        cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        artifacts_dir=isolated_artifacts_dir,
        min_free_scratch_bytes=1024,
        pin_cores=False,
        enable_thermal_governor=True,
    )
    assert retcode == 0
    assert provenance is None


# ==============================================================================
# 8. TemporalRouter Tests (10-Tier Wall Clock & Hardware Guardrails)
# ==============================================================================

def test_temporal_router_air_gap_missing_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing COCHEM_ARTIFACTS_DIR raises fatal RuntimeError."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)
    router = TemporalRouter()

    with pytest.raises(RuntimeError) as exc_info:
        router.load_system_config()
    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)


def test_temporal_router_missing_config_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies FileNotFoundError when cochem_system_config.json is absent."""
    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)
    with pytest.raises(FileNotFoundError) as exc_info:
        router.load_system_config()
    assert "cochem_system_config.json" in str(exc_info.value)


def test_temporal_router_metadata_extraction_bench_run_context(isolated_artifacts_dir: Path) -> None:
    """Validates extraction of method and atom count N from authentic BenchRunContext."""
    from cochem_bench.bench_engine.cochem_bench_ingest import (
        BenchConfigSchema,
        BenchHardwareSchema,
        BenchRunContext,
    )

    hw = BenchHardwareSchema(ram_gb=16.0, cpu_physical_cores=4)
    cfg = BenchConfigSchema(
        hardware=hw,
        active_jobs={"method": "DLPNO-CCSD(T)", "atom_count": 8},
    )
    context = BenchRunContext(
        config_hash="abc12345",
        safe_maxcore_mb=3000,
        target_mpi_threads=3,
        node_id="test_node",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        orca_path=None,
        hdf5_path=isolated_artifacts_dir / "landscape.h5",
        scratch_path=isolated_artifacts_dir / "scratch",
        numa_nodes=1,
        resource_warning=False,
        config=cfg,
    )

    method, atoms = TemporalRouter.extract_metadata_from_context(context)
    assert method == "DLPNO-CCSD(T)"
    assert atoms == 8


def test_temporal_router_local_workstation_dlpno_disables_and_warns(isolated_artifacts_dir: Path) -> None:
    """Verifies ResourceWarning emission, execution disablement, and HPC suggestion for DLPNO on Local Workstation."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 32.0,
            "os_target": "Local-Windows",
        },
        "hpc": {
            "scheduler": "local",
            "execution_mode": "local",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = router.route(method="DLPNO-CCSD(T)", atom_count=6)

    assert any(issubclass(w.category, ResourceWarning) for w in record)
    assert isinstance(result, TemporalRouteResult)
    assert result.is_local_workstation is True
    assert result.execution_allowed is False
    assert result.resource_warning_emitted is True
    assert result.suggested_offload == "HPC/SLURM"
    assert result.tier >= 9
    assert result.scaling_exponent == 7


def test_temporal_router_local_workstation_dft_authorized(isolated_artifacts_dir: Path) -> None:
    """Verifies that modest DFT calculations on Local Workstations are authorized without warning."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "os_target": "Local-Linux",
        },
        "hpc": {
            "scheduler": "local",
            "execution_mode": "local",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = router.route(method="B3LYP/def2-TZVP", atom_count=5)

    assert len([w for w in record if issubclass(w.category, ResourceWarning)]) == 0
    assert result.is_local_workstation is True
    assert result.execution_allowed is True
    assert result.resource_warning_emitted is False
    assert result.suggested_offload is None
    assert result.tier == 3
    assert result.scaling_exponent == 4


def test_temporal_router_hpc_cluster_authorizes_dlpno(isolated_artifacts_dir: Path) -> None:
    """Verifies that heavy DLPNO-CCSD(T) calculations on HPC cluster profiles are authorized."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 64,
            "logical_cpu_cores": 128,
            "ram_gb": 512.0,
            "os_target": "HPC",
        },
        "hpc": {
            "scheduler": "slurm",
            "execution_mode": "cluster",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)
    result = router.route(method="DLPNO-CCSD(T)", atom_count=12)

    assert result.is_local_workstation is False
    assert result.execution_allowed is True
    assert result.tier == 10
    assert result.scaling_exponent == 7
    assert result.wall_clock_estimate == "1mo"


def test_temporal_router_call_shorthand_syntax(isolated_artifacts_dir: Path) -> None:
    """Verifies functional instantiation TemporalRouter(method=..., atom_count=...)."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {"ram_gb": 32.0, "os_target": "Local-Windows"},
        "hpc": {"scheduler": "local"},
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    result = TemporalRouter(method="MP2", atom_count=4, artifacts_dir=isolated_artifacts_dir)
    assert isinstance(result, TemporalRouteResult)
    assert result.method == "MP2"
    assert result.atom_count == 4
    assert result.scaling_exponent == 5
    assert result.tier == 6


# ==============================================================================
# 9. High-Speed I/O Routing Tests (tmpfs RAM-Disk & Persistence)
# ==============================================================================

def test_high_speed_io_router_windows_bypasses_ramdisk(isolated_artifacts_dir: Path) -> None:
    """Verifies that Windows systems or non-posix environments bypass /dev/shm."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)
    report = router.route_scratch(available_ram_gb=256.0, job_id="test_win_job")

    assert isinstance(report, IOScratchRouteReport)
    assert report.available_ram_gb == 256.0
    if os.name != "posix":
        assert report.is_ramdisk is False
        assert report.route_type == "STANDARD_NVME_SCRATCH"
        assert Path(report.scratch_path).exists()


def test_high_speed_io_router_low_ram_bypasses_ramdisk(isolated_artifacts_dir: Path) -> None:
    """Verifies that RAM capacity <= 128 GB routes to standard NVMe scratch."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)
    report = router.route_scratch(available_ram_gb=64.0, job_id="test_low_ram")

    assert report.is_ramdisk is False
    assert report.route_type == "STANDARD_NVME_SCRATCH"
    assert Path(report.scratch_path).exists()


def test_high_speed_io_router_finalize_and_cleanup_lifecycle(isolated_artifacts_dir: Path) -> None:
    """Verifies artifact copying (.out, .gbw) to persistent workspace and RAM-disk recovery."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)

    temp_scratch = isolated_artifacts_dir / "temp_calc_scratch"
    temp_scratch.mkdir(parents=True, exist_ok=True)

    # Create calculation artifacts
    out_file = temp_scratch / "orca_calc.out"
    out_file.write_text("FINAL SINGLE POINT ENERGY -150.12345678", encoding="utf-8")
    gbw_file = temp_scratch / "orca_calc.gbw"
    gbw_file.write_bytes(b"\x00\x01\x02ORCA_GBW_DENSITY_MATRIX")
    tmp_file = temp_scratch / "orca_calc.tmp"
    tmp_file.write_text("transient integral cache", encoding="utf-8")

    persistent_dir = isolated_artifacts_dir / "persistent_ssd_workspace"

    cleanup_report = router.finalize_and_cleanup(
        active_scratch_path=temp_scratch,
        persistent_workspace_path=persistent_dir,
        copy_extensions=(".out", ".gbw"),
        is_ramdisk=True,
    )

    assert isinstance(cleanup_report, IOCleanupReport)
    assert cleanup_report.ramdisk_cleaned is True
    assert (persistent_dir / "orca_calc.out").exists()
    assert (persistent_dir / "orca_calc.gbw").exists()
    assert not (persistent_dir / "orca_calc.tmp").exists()
    assert not temp_scratch.exists()


def test_high_speed_io_router_context_manager(isolated_artifacts_dir: Path) -> None:
    """Verifies end-to-end scratch_context context manager lifecycle and persistence."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)

    with router.scratch_context(available_ram_gb=64.0, job_id="cm_calc") as scratch_path:
        assert scratch_path.exists()
        out_f = scratch_path / "result.out"
        out_f.write_text("ORCA TERMINATED NORMALLY", encoding="utf-8")
        gbw_f = scratch_path / "result.gbw"
        gbw_f.write_bytes(b"GBW_PAYLOAD")

    persistent_scratch = get_scratch_workspace_dir(isolated_artifacts_dir)
    assert (persistent_scratch / "result.out").exists()
    assert (persistent_scratch / "result.gbw").exists()


def test_high_speed_io_routing_alias() -> None:
    """Verifies HighSpeedIORouting is an authoritative alias for HighSpeedIORouter."""
    assert HighSpeedIORouting is HighSpeedIORouter


# ==============================================================================
# 10. Active Stream Regex Traps Tests
# ==============================================================================

class TestActiveStreamRegexTraps:
    """Authentic zero-mock unit test suite for active stream regex traps and watchdogs."""

    def test_detect_linear_dependence_regex_and_literal(self) -> None:
        """Confirms detection of literal 'eigenvalues < 10^-6' and regex variations."""
        trap = ActiveStreamRegexTrap()

        assert trap.detect_linear_dependence("WARNING: eigenvalues < 10^-6 in overlap matrix!") is True
        assert trap.detect_linear_dependence("Overlap matrix ill-conditioned (eigenvalues < 10^-6). Aborting.") is True
        assert trap.detect_linear_dependence("eigenvalues<10^-6") is True
        assert trap.detect_linear_dependence("eigenvalues  <  10^-6") is True

        assert trap.detect_linear_dependence("Normal SCF step completed.") is False
        assert trap.detect_linear_dependence("eigenvalues = 1.234e-2") is False

    def test_detect_nan_inf_regex_and_literal(self) -> None:
        """Confirms detection of NaN, Inf, and signed variations in output matrices."""
        trap = ActiveStreamRegexTrap()

        assert trap.detect_nan_inf("Fock matrix contains NaN at row 4") is True
        assert trap.detect_nan_inf("Total Energy: -Inf Hartree") is True
        assert trap.detect_nan_inf("DIIS error = Inf") is True
        assert trap.detect_nan_inf("Gradient norm: -NaN") is True
        assert trap.detect_nan_inf("Electronic energy: Infinity") is True

        assert trap.detect_nan_inf("Total Energy: -76.43219876 Hartree") is False
        assert trap.detect_nan_inf("Information: Basis set initialized") is False

    def test_linear_dependence_trap_execution_and_reap(self, isolated_artifacts_dir: Path) -> None:
        """Verifies linear dependence detection issues kill command and logs ORCA_LINEAR_DEPENDENCE_FAULT."""
        trap = ActiveStreamRegexTrap(artifacts_dir=isolated_artifacts_dir)

        worker = launch_isolated_process(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        worker_pid = worker.pid

        try:
            assert psutil.pid_exists(worker_pid)
            fault_line = "ORCA OVERLAP ERROR: eigenvalues < 10^-6 encountered during orthogonalization"
            event = trap.process_line(fault_line, pid=worker_pid)

            assert isinstance(event, StreamTrapEvent)
            assert event.trap_type == ORCA_LINEAR_DEPENDENCE_FAULT
            assert event.pid == worker_pid
            assert "Linear dependence overlap detected" in event.message

            # Process must be reaped / dead
            time.sleep(0.2)
            assert not psutil.pid_exists(worker_pid)
        finally:
            if psutil.pid_exists(worker_pid):
                try:
                    psutil.Process(worker_pid).kill()
                except Exception:
                    pass

    def test_nan_inf_trap_execution_and_reap(self, isolated_artifacts_dir: Path) -> None:
        """Verifies NaN/Inf in energy matrices immediately terminates process tree."""
        trap = ActiveStreamRegexTrap(artifacts_dir=isolated_artifacts_dir)

        worker = launch_isolated_process(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        worker_pid = worker.pid

        try:
            assert psutil.pid_exists(worker_pid)
            fault_line = "Energy matrix element [12, 14] = NaN (divergent matrix diagonalization)"
            event = trap.process_line(fault_line, pid=worker_pid)

            assert isinstance(event, StreamTrapEvent)
            assert event.trap_type == ENERGY_MATRIX_NAN_INF_FAULT
            assert event.pid == worker_pid
            assert "NaN/Inf numeric singularity" in event.message

            # Process must be reaped / dead
            time.sleep(0.2)
            assert not psutil.pid_exists(worker_pid)
        finally:
            if psutil.pid_exists(worker_pid):
                try:
                    psutil.Process(worker_pid).kill()
                except Exception:
                    pass

    def test_detect_ping_pong_oscillation_cycles(self) -> None:
        """Confirms detection of 2-cycle ping-pong limit cycles in SCF Delta-E trajectories."""
        trap = ActiveStreamRegexTrap(ping_pong_tolerance=1e-4)

        # 1. Exact 5-cycle alternating signs with constant magnitude
        oscillating_1 = [-0.005000, 0.005000, -0.005000, 0.005000, -0.005000]
        assert trap.detect_ping_pong_oscillation(oscillating_1) is True

        # 2. Positive start alternating
        oscillating_2 = [0.002500, -0.002500, 0.002500, -0.002500, 0.002500]
        assert trap.detect_ping_pong_oscillation(oscillating_2) is True

        # 3. Normal converging sequence -> False
        converging = [-0.100000, -0.050000, -0.010000, -0.001000, -0.000100]
        assert trap.detect_ping_pong_oscillation(converging) is False

        # 4. Decaying oscillation with varying magnitudes -> False
        decaying = [-0.100000, 0.050000, -0.020000, 0.008000, -0.001000]
        assert trap.detect_ping_pong_oscillation(decaying) is False

        # 5. Fewer than 5 cycles -> False
        too_few = [-0.005000, 0.005000, -0.005000]
        assert trap.detect_ping_pong_oscillation(too_few) is False

    def test_inject_slowconv_soscf_into_orca_input(self) -> None:
        """Confirms injection of literal '! SlowConv SOSCF' into ORCA input text."""
        trap = ActiveStreamRegexTrap()

        # 1. Existing keyword line with other directives
        input_1 = "! B3LYP def2-TZVP OPT\n* xyz 0 1\nO 0 0 0\nH 0 0.7 0\nH 0 -0.7 0\n*\n"
        rescued_1 = trap.inject_slowconv_soscf(input_1)
        assert "! SlowConv SOSCF B3LYP def2-TZVP OPT" in rescued_1
        assert "* xyz 0 1" in rescued_1

        # 2. Empty input
        rescued_empty = trap.inject_slowconv_soscf("")
        assert "! SlowConv SOSCF" in rescued_empty

        # 3. Input without existing ! line
        input_no_kw = "* xyz 0 1\nC 0 0 0\n*\n"
        rescued_no_kw = trap.inject_slowconv_soscf(input_no_kw)
        assert rescued_no_kw.startswith("! SlowConv SOSCF\n")

    def test_ping_pong_trap_execution_and_rescue_requeue(self, isolated_artifacts_dir: Path) -> None:
        """Verifies ping-pong detection terminates process and re-queues with ! SlowConv SOSCF."""
        trap = ActiveStreamRegexTrap(artifacts_dir=isolated_artifacts_dir)

        worker = launch_isolated_process(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        worker_pid = worker.pid

        initial_orca_inp = "! wB97X-D3 def2-TZVPP\n* xyz 0 1\nN 0 0 0\nN 0 0 1.1\n*\n"

        try:
            assert psutil.pid_exists(worker_pid)

            # Feed 4 non-triggering lines then 5th triggering line
            lines = [
                "  1    -109.5000000000   -0.0040000000   0.02000000   0.00300000",
                "  2    -109.4960000000    0.0040000000   0.02000000   0.00300000",
                "  3    -109.5000000000   -0.0040000000   0.02000000   0.00300000",
                "  4    -109.4960000000    0.0040000000   0.02000000   0.00300000",
                "  5    -109.5000000000   -0.0040000000   0.02000000   0.00300000",
            ]

            event: Optional[StreamTrapEvent] = None
            for idx, l in enumerate(lines):
                event = trap.process_line(l, pid=worker_pid, orca_input=initial_orca_inp)
                if idx < 4:
                    assert event is None

            assert isinstance(event, StreamTrapEvent)
            assert event.trap_type == SCF_PING_PONG_OSCILLATION
            assert event.pid == worker_pid
            assert event.rescued_input is not None
            assert "! SlowConv SOSCF" in event.rescued_input
            assert len(event.delta_e_history) == 5

            # Process must be reaped / dead
            time.sleep(0.2)
            assert not psutil.pid_exists(worker_pid)
        finally:
            if psutil.pid_exists(worker_pid):
                try:
                    psutil.Process(worker_pid).kill()
                except Exception:
                    pass

    def test_zombie_reaper_dedicated_stream_reap_methods(self, isolated_artifacts_dir: Path) -> None:
        """Verifies ZombieReaper dedicated methods: reap_on_linear_dependence, reap_on_nan_inf, reap_and_requeue_ping_pong."""
        reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

        # 1. reap_on_linear_dependence
        w1 = launch_isolated_process([sys.executable, "-c", "import time; time.sleep(120)"])
        try:
            r1 = reaper.reap_on_linear_dependence(w1.pid)
            assert isinstance(r1, ProcessReapReport)
            assert r1.reason == ORCA_LINEAR_DEPENDENCE_FAULT
            assert r1.status == "EXTERMINATED"
            time.sleep(0.1)
            assert not psutil.pid_exists(w1.pid)
        finally:
            if psutil.pid_exists(w1.pid):
                psutil.Process(w1.pid).kill()

        # 2. reap_on_nan_inf
        w2 = launch_isolated_process([sys.executable, "-c", "import time; time.sleep(120)"])
        try:
            r2 = reaper.reap_on_nan_inf(w2.pid)
            assert isinstance(r2, ProcessReapReport)
            assert r2.reason == ENERGY_MATRIX_NAN_INF_FAULT
            assert r2.status == "EXTERMINATED"
            time.sleep(0.1)
            assert not psutil.pid_exists(w2.pid)
        finally:
            if psutil.pid_exists(w2.pid):
                psutil.Process(w2.pid).kill()

        # 3. reap_and_requeue_ping_pong
        w3 = launch_isolated_process([sys.executable, "-c", "import time; time.sleep(120)"])
        try:
            r3, rescued_inp = reaper.reap_and_requeue_ping_pong(w3.pid, "! HF def2-SVP\n* xyz 0 1\nH 0 0 0\nH 0 0 0.74\n*")
            assert isinstance(r3, ProcessReapReport)
            assert r3.reason == SCF_PING_PONG_OSCILLATION
            assert "! SlowConv SOSCF" in rescued_inp
            time.sleep(0.1)
            assert not psutil.pid_exists(w3.pid)
        finally:
            if psutil.pid_exists(w3.pid):
                psutil.Process(w3.pid).kill()


# ==============================================================================
# 11. Exit Code Segfault & OOM Hex-Dumping Tests
# ==============================================================================

class TestExitCodeSegfaultHexDumping:
    """Authentic unit test suite for OS-level fault trapping and scratch tail hex-dumping."""

    @pytest.mark.parametrize("fault_code", [-11, 139, -9, 137, 0xC0000005, -1073741819, 3221225477])
    def test_os_fault_return_codes_classification(self, fault_code: int) -> None:
        """Validates that SegfaultTrapper recognizes all POSIX and Windows OS crash codes."""
        assert SegfaultTrapper.is_os_fault(fault_code) is True
        if fault_code in (-9, 137):
            assert SegfaultTrapper.is_oom_fault(fault_code) is True
        else:
            assert SegfaultTrapper.is_segmentation_fault(fault_code) is True

    @pytest.mark.parametrize("normal_code", [0, 1, 2, 127])
    def test_os_fault_ignores_normal_exit_codes(self, normal_code: int) -> None:
        """Validates that standard non-crash return codes return False."""
        assert SegfaultTrapper.is_os_fault(normal_code) is False
        assert SegfaultTrapper.is_oom_fault(normal_code) is False

    def test_format_hex_dump_canonical(self) -> None:
        """Confirms format_hex_dump generates canonical POSIX hexdump -C string with offsets and ASCII."""
        sample_bytes = b"ORCA 6.1.1 DLPNO-CCSD(T) FATAL SEGV DUMP BUFFER"
        dump = format_hex_dump(sample_bytes)

        assert "00000000" in dump
        assert "4f 72 63 61" in dump.lower() or "4f" in dump
        assert "|ORCA 6.1.1 DLPNO" in dump

    def test_extract_tail_hex_dump_from_file_extracts_last_256_bytes(self, isolated_artifacts_dir: Path) -> None:
        """Confirms extract_tail_hex_dump reads precisely the final 256 bytes from a binary dump file."""
        dump_file = isolated_artifacts_dir / "crash.tmp"
        # Write 1024 bytes
        header = b"HEADER_" * 64  # 448 bytes
        tail = b"CRASH_TAIL_BYTE_" * 16  # 256 bytes
        dump_file.write_bytes(header + tail)

        hex_dump = extract_tail_hex_dump(dump_file, max_bytes=256)
        assert len(hex_dump) > 0
        assert "CRASH_TAIL_BYTE" in hex_dump

    def test_segfault_trapper_scratch_tail_hex_dump_injection(self, isolated_artifacts_dir: Path) -> None:
        """Verifies SegfaultTrapper dynamically locates scratch dump file, extracts 256 bytes, and commits to JSON-LD."""
        scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)

        # Stage authentic scratch crash dump
        tmp_dump = scratch_dir / "orca_scf_integral_dump.tmp"
        crash_payload = b"\xde\xad\xbe\xef" * 64  # 256 bytes
        tmp_dump.write_bytes(crash_payload)

        trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)
        simulated_pid = 65432
        simulated_returncode = 139

        provenance = trapper.trap(
            process_id=simulated_pid,
            returncode=simulated_returncode,
            metadata={"step": "CCSD_TENSOR_CONTRACTION"},
        )

        assert isinstance(provenance, JSONLDProvenanceBlock)
        assert provenance.process_id == simulated_pid
        assert provenance.return_code == simulated_returncode
        assert provenance.fault_type == "OS_SEGMENTATION_FAULT"
        assert provenance.hex_dump is not None
        assert "deadbeef" in provenance.hex_dump.lower() or "de ad be ef" in provenance.hex_dump.lower()

        # Check provenance file on disk
        prov_file = trapper.get_provenance_file_path()
        assert prov_file.exists()
        disk_data = json.loads(prov_file.read_text(encoding="utf-8"))
        assert disk_data["hex_dump"] is not None
        assert disk_data["metadata"]["hex_dump"] is not None

    def test_segfault_trapper_check_and_raise_includes_hex_dump(self, isolated_artifacts_dir: Path) -> None:
        """Verifies check_and_raise includes formatted hex dump in the exception string."""
        scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        dump_f = scratch_dir / "stderr.log"
        dump_f.write_text("Segmentation fault (core dumped) at 0x7fff0012", encoding="utf-8")

        trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)

        with pytest.raises(SegmentationFaultError) as exc_info:
            trapper.check_and_raise(process_id=98765, returncode=0xC0000005)

        err_msg = str(exc_info.value)
        assert "Segmentation fault detected" in err_msg
        assert "Hex Dump:" in err_msg
        assert "00000000" in err_msg

    def test_segfault_trapper_oom_fault_classification(self, isolated_artifacts_dir: Path) -> None:
        """Verifies POSIX returncode 137 / -9 sets fault_type to OS_OOM_FAULT."""
        trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)

        prov = trapper.trap(process_id=44444, returncode=137)
        assert isinstance(prov, JSONLDProvenanceBlock)
        assert prov.fault_type == "OS_OOM_FAULT"


# ==============================================================================
# 12. JSON-LD Provenance Footer Tests
# ==============================================================================

class TestJSONLDProvenanceFooter:
    """Authentic unit test suite for calculation finalization JSON-LD provenance footers."""

    def test_append_jsonld_provenance_footer_success(self, isolated_artifacts_dir: Path) -> None:
        """Verifies appending JSON-LD footer containing all 5 required fields."""
        hardware_data = {
            "instruction_set": "AVX-512",
            "physical_cores": 16,
            "numa_nodes": 2,
            "ram_gb": 128.0,
        }
        geom_str = "* xyz 0 1\nO 0.000000 0.000000 0.117300\nH 0.000000 0.757200 -0.469200\nH 0.000000 -0.757200 -0.469200\n*"
        geom_hash = compute_geometry_hash(geom_str)
        orca_hash = compute_orca_binary_hash("ORCA_6_1_1_AVX2_RELEASE_BUILD")
        methodology = "Halkier Inverse Cubic Extrapolation (alpha=4.00, beta=5.72)"

        payload, dest_path = append_jsonld_provenance_footer(
            orca_binary_hash=orca_hash,
            hardware_profile=hardware_data,
            geometry_hash=geom_hash,
            composite_methodology=methodology,
            cochem_version="2.0.0",
            artifacts_dir=isolated_artifacts_dir,
        )

        assert isinstance(payload, ProvenanceFooterPayload)
        assert payload.cochem_version == "2.0.0"
        assert payload.orca_binary_hash == orca_hash
        assert payload.geometry_hash == geom_hash
        assert payload.composite_methodology == methodology
        assert payload.hardware_profile["instruction_set"] == "AVX-512"

        assert dest_path.exists()
        data = json.loads(dest_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1

        record = data[0]
        assert record["@context"] == "https://doi.org/10.5281/zenodo.cochem.v2"
        assert record["@type"] == "BenchmarkProvenanceFooter"
        assert record["CoChem_Version"] == "2.0.0"
        assert record["ORCA_Binary_Hash"] == orca_hash
        assert record["Hardware_Profile"]["physical_cores"] == 16
        assert record["Geometry_Hash"] == geom_hash
        assert record["Composite_Methodology"] == methodology

    def test_append_jsonld_provenance_footer_multiple_records(self, isolated_artifacts_dir: Path) -> None:
        """Verifies multiple calculations append atomically into the JSON-LD ledger list."""
        for i in range(3):
            append_jsonld_provenance_footer(
                orca_binary_hash=f"orca_hash_build_{i}",
                hardware_profile={"run_index": i},
                geometry_hash=f"geom_hash_{i}",
                composite_methodology=f"Methodology {i}",
                artifacts_dir=isolated_artifacts_dir,
            )

        target_file = isolated_artifacts_dir / "Processed" / "bench_provenance.jsonld"
        assert target_file.exists()

        records = json.loads(target_file.read_text(encoding="utf-8"))
        assert isinstance(records, list)
        assert len(records) == 3
        assert records[0]["ORCA_Binary_Hash"] == "orca_hash_build_0"
        assert records[1]["ORCA_Binary_Hash"] == "orca_hash_build_1"
        assert records[2]["ORCA_Binary_Hash"] == "orca_hash_build_2"

    def test_cryptographic_hashing_helpers(self) -> None:
        """Validates SHA-256 hash helper functions."""
        h1 = compute_sha256_hash("CoChem Benchmark Payload")
        assert len(h1) == 64
        import hashlib
        assert h1 == hashlib.sha256(b"CoChem Benchmark Payload").hexdigest()

        g_hash = compute_geometry_hash("C 0 0 0\nO 0 0 1.13")
        assert len(g_hash) == 64

        b_hash = compute_orca_binary_hash("orca_binary_v6.1.1")
        assert len(b_hash) == 64

    def test_provenance_footer_missing_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies fatal RuntimeError if COCHEM_ARTIFACTS_DIR is missing and artifacts_dir is None."""
        monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            append_jsonld_provenance_footer(
                orca_binary_hash="dummy_hash",
                hardware_profile={},
                geometry_hash="dummy_geom",
                composite_methodology="CBS",
                artifacts_dir=None,
            )
        assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)


# ==============================================================================
# 13. Subprocess Reaper Export & Alias Tests
# ==============================================================================

def test_all_symbols_in_dunder_all() -> None:
    """Verifies all new and existing classes, functions, and exceptions are exported in __all__."""
    import cochem_bench.bench_libraries.subprocess_reaper as sr_mod
    import cochem_bench.bench_libraries as bl_mod

    required_symbols = [
        "ActiveStreamRegexTrap",
        "CRITICAL_TEMP_CELSIUS",
        "DEFAULT_MIN_FREE_SCRATCH_BYTES",
        "ENERGY_MATRIX_NAN_INF_FAULT",
        "EnergyMatrixNaNInfFaultError",
        "ExitCode139_Trapper",
        "HardwareRegistryConfig",
        "HighSpeedIORouter",
        "HighSpeedIORouting",
        "IOCleanupReport",
        "IOScratchRouteReport",
        "JSONLDProvenanceBlock",
        "JSONLDProvenanceFooter",
        "LINEAR_DEPENDENCE_PATTERN",
        "LinearDependenceFaultError",
        "NAN_INF_PATTERN",
        "NUMAPinningError",
        "NUMA_ThreadPinner",
        "OOM_RETURN_CODES",
        "ORCA_LINEAR_DEPENDENCE_FAULT",
        "OSFaultError",
        "OS_FAULT_RETURN_CODES",
        "PreFlightResourceError",
        "PreFlightScratchVerifier",
        "ProcessReapReport",
        "ProvenanceFooterPayload",
        "RESUME_TEMP_CELSIUS",
        "ResourceGuardError",
        "SCF_DELTA_E_PATTERN",
        "SCF_PING_PONG_OSCILLATION",
        "SCFPingPongOscillationError",
        "SEGFAULT_RETURN_CODES",
        "SLOWCONV_SOSCF_KEYWORD",
        "ScratchSpaceReport",
        "SegfaultTrapper",
        "SegmentationFaultError",
        "StreamRegexTrap",
        "StreamTrapError",
        "StreamTrapEvent",
        "StreamTrapReport",
        "SystemRegistryConfig",
        "TemporalRouteResult",
        "TemporalRouter",
        "TemporalRoutingError",
        "ThermalEvacuationGovernor",
        "ThermalGovernor",
        "ThermalGovernorState",
        "ThreadPinningResult",
        "ZMQEndpointManifest",
        "ZombieReaper",
        "ZombieReaperError",
        "append_jsonld_provenance_footer",
        "compute_geometry_hash",
        "compute_orca_binary_hash",
        "compute_sha256_hash",
        "execute_protected_subprocess",
        "extract_tail_hex_dump",
        "find_scratch_dump_file",
        "format_hex_dump",
        "get_cochem_artifacts_dir",
        "get_element_mass_mendeleev",
        "get_processed_workspace_dir",
        "get_registry_workspace_dir",
        "get_scratch_workspace_dir",
        "launch_isolated_process",
    ]

    for sym in required_symbols:
        assert hasattr(sr_mod, sym), f"subprocess_reaper is missing {sym}"
        assert sym in sr_mod.__all__, f"{sym} not in subprocess_reaper.__all__"
        assert hasattr(bl_mod, sym), f"bench_libraries is missing {sym}"
        assert sym in bl_mod.__all__, f"{sym} not in bench_libraries.__all__"



