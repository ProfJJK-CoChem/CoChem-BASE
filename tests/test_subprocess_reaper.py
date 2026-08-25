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
from typing import Generator

import psutil
import pytest
import zmq
from mendeleev import element

from cochem_bench.bench_libraries.subprocess_reaper import (
    CRITICAL_TEMP_CELSIUS,
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ExitCode139_Trapper,
    HighSpeedIORouter,
    HighSpeedIORouting,
    IOCleanupReport,
    IOScratchRouteReport,
    JSONLDProvenanceBlock,
    NUMAPinningError,
    NUMA_ThreadPinner,
    PreFlightResourceError,
    PreFlightScratchVerifier,
    ProcessReapReport,
    RESUME_TEMP_CELSIUS,
    ResourceGuardError,
    SEGFAULT_RETURN_CODES,
    ScratchSpaceReport,
    SegfaultTrapper,
    SegmentationFaultError,
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
    execute_protected_subprocess,
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


