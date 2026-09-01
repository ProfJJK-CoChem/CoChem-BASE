from __future__ import annotations
"""
    Unit test suite for CoChem Setup Phase 5: NVIDIA MPS Daemon Initialization & VRAM Budgeting.
    Strict Zero-Mock Mandate: Real filesystem operations, real mathematical VRAM partitioning,
    deterministic Pydantic V2 schema validations, real socket/pipe path resolution, real script
    generation, and real atomic state persistence into the Golden Registry.

    SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 3), and Method Matrix v4 Compliant.
"""


import json
import os
import platform
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_5 import (
    ConfigLockAuditReport,
    ConfigLockError,
    DependencyManager,
    GPUDeviceVRAM,
    LockTestFailureError,
    LockTestResult,
    MPSControlError,
    MPSDaemonAudit,
    MPSStatus,
    Phase5AuditError,
    Phase5AuditReport,
    PhaseStatus,
    VRAMAllocationError,
    VRAMBudgetReport,
    WorkspaceSweepReport,
    build_pinned_memory_limit_string,
    calculate_vram_budget,
    configure_mps_device_limit,
    consolidate_intermediate_states,
    discover_mps_binaries,
    enforce_socket_directory_permissions,
    execute_workspace_sweep,
    finalize_and_lock_golden_registry,
    generate_mps_activation_scripts,
    get_current_username,
    inject_mps_environment_variables,
    main,
    probe_gpu_devices_vram,
    probe_mps_daemon_status,
    resolve_golden_config_path,
    resolve_mps_log_directory,
    resolve_mps_pipe_directory,
    resolve_p5_registry_path,
    run_phase_5_audit,
    start_mps_daemon,
    stop_mps_daemon,
    validate_and_build_system_config,
    )
from orchestrator.cochem_setup_phase_5 import (
    test_posix_byte_range_locking as posix_byte_range_locking_fn,
    )

# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 5 exception classes inherit from RuntimeError."""
    err1 = Phase5AuditError("Phase 5 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = MPSControlError("MPS control command failed")
    assert isinstance(err2, RuntimeError)
    err3 = VRAMAllocationError("VRAM allocation calculation failed")
    assert isinstance(err3, RuntimeError)
    err4 = ConfigLockError("Config lock failed")
    assert isinstance(err4, RuntimeError)
    err5 = LockTestFailureError("Lock test failed")
    assert isinstance(err5, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_mps_status_enum() -> None:
    """Verify MPSStatus enum values and validation."""
    assert MPSStatus.RUNNING.value == "RUNNING"
    assert MPSStatus.INITIALIZED.value == "INITIALIZED"
    assert MPSStatus.STOPPED.value == "STOPPED"
    assert MPSStatus.NOT_SUPPORTED.value == "NOT_SUPPORTED"
    assert MPSStatus.DEGRADED.value == "DEGRADED"
    assert MPSStatus.ERROR.value == "ERROR"


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_gpu_device_vram_model_valid_and_validation() -> None:
    """Test GPUDeviceVRAM model construction, field validation, and extra='forbid'."""
    dev = GPUDeviceVRAM(
        index=0,
        name="NVIDIA RTX 4090",
        uuid="GPU-12345678-ABCD",
        total_vram_mb=24576.0,
        free_vram_mb=22000.0,
        reserved_vram_mb=3686.4,
        allocatable_vram_mb=20889.6,
        allocated_limit_per_worker_mb=10444.0,
        active_worker_capacity=2,
        pinned_mem_limit_str="0=10444M",
        compute_capability="sm_89",
    )
    assert dev.index == 0
    assert dev.name == "NVIDIA RTX 4090"
    assert dev.total_vram_mb == 24576.0
    assert dev.active_worker_capacity == 2

    # Roundtrip JSON validation
    json_str = dev.model_dump_json()
    assert "RTX 4090" in json_str
    restored = GPUDeviceVRAM.model_validate_json(json_str)
    assert restored == dev

    # Empty name should fail
    with pytest.raises(ValidationError):
        GPUDeviceVRAM(
            index=0,
            name="",
            total_vram_mb=8192.0,
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        GPUDeviceVRAM(
            index=0,
            name="GPU 0",
            total_vram_mb=8192.0,
            forbidden_extra_param="illegal",  # type: ignore
        )


def test_mps_daemon_audit_model_valid() -> None:
    """Test MPSDaemonAudit model construction and serialization."""
    audit = MPSDaemonAudit(
        mps_control_binary="/usr/bin/nvidia-cuda-mps-control",
        mps_server_binary="/usr/bin/nvidia-cuda-mps-server",
        status=MPSStatus.INITIALIZED,
        pipe_directory="/tmp/cochem_mps_user",
        log_directory="/tmp/cochem_mps_log_user",
        socket_path="/tmp/cochem_mps_user/control",
        is_daemon_active=False,
        pid=None,
        socket_permissions="0o700",
        is_permission_secure=True,
        server_active=False,
        control_active=False,
        environment_variables={"CUDA_MPS_PIPE_DIRECTORY": "/tmp/cochem_mps_user"},
        details="MPS control initialized",
    )
    assert audit.status is MPSStatus.INITIALIZED
    assert audit.is_permission_secure is True

    dumped = audit.model_dump()
    assert dumped["pipe_directory"] == "/tmp/cochem_mps_user"
    restored = MPSDaemonAudit.model_validate(dumped)
    assert restored == audit


def test_vram_budget_report_model_valid() -> None:
    """Test VRAMBudgetReport model construction."""
    report = VRAMBudgetReport(
        total_gpus_detected=1,
        active_gpu_devices=[],
        total_cluster_vram_mb=16384.0,
        total_reserved_vram_mb=2457.6,
        total_allocatable_vram_mb=13926.4,
        worker_concurrency_target=2,
        default_pinned_mem_limit="6963M",
        per_device_limits={"0": "0=6963M"},
        is_vram_bounded=True,
        strategy="PROPORTIONAL_PINNED_BUDGET",
    )
    assert report.total_cluster_vram_mb == 16384.0
    assert report.worker_concurrency_target == 2
    assert report.per_device_limits["0"] == "0=6963M"


def test_phase_5_audit_report_model_and_validator(tmp_path: Path) -> None:
    """Test Phase5AuditReport model validation and phase_id check."""
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T00:00:00Z",
        mps_daemon=MPSDaemonAudit(
            status=MPSStatus.NOT_SUPPORTED,
            is_permission_secure=True,
        ),
        vram_budget=VRAMBudgetReport(
            total_gpus_detected=0,
            total_cluster_vram_mb=0.0,
            total_reserved_vram_mb=0.0,
            total_allocatable_vram_mb=0.0,
        ),
        is_cuda_available=False,
        is_hpc_slurm=False,
        warnings=["No GPU detected"],
        errors=[],
        artifact_path=str(tmp_path / "p5.json"),
    )
    assert report.status is PhaseStatus.PASSED
    assert report.phase_id == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"

    # Invalid phase_id should fail
    with pytest.raises(ValidationError):
        Phase5AuditReport(
            phase_id="INVALID_PHASE_ID",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-21T00:00:00Z",
            mps_daemon=MPSDaemonAudit(),
            vram_budget=VRAMBudgetReport(),
            artifact_path=str(tmp_path / "p5.json"),
        )


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY MANAGER TESTS
# =============================================================================


def test_dependency_manager_tracking_and_cleanup(tmp_path: Path) -> None:
    """Verify DependencyManager tracks and untracks files cleanly."""
    with DependencyManager() as dm:
        f1 = dm.track_temp_file(tmp_path / "test_file.tmp")
        f1.write_text("temporary data", encoding="utf-8")
        assert f1.exists()
        dm.untrack_file(f1)

    # Untracked file persists
    assert f1.exists()
    f1.unlink()


def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify DependencyManager purges tracked temporary files and directories on exception."""
    staged_file = tmp_path / "staged_artifact.tmp"
    staged_dir = tmp_path / "staged_directory.tmp"

    try:
        with DependencyManager() as dm:
            dm.track_temp_file(staged_file)
            dm.track_temp_dir(staged_dir)

            staged_file.write_text("transient state", encoding="utf-8")
            staged_dir.mkdir(parents=True, exist_ok=True)
            (staged_dir / "subfile.txt").write_text("sub content", encoding="utf-8")

            assert staged_file.exists()
            assert staged_dir.exists()

            raise RuntimeError("Simulated execution failure during stage 5 setup")
    except RuntimeError:
        pass

    # Verify rollback successfully deleted staged artifacts
    assert not staged_file.exists()
    assert not staged_dir.exists()


def test_dependency_manager_atomic_write_json(tmp_path: Path) -> None:
    """Verify DependencyManager performs atomic JSON file writes."""
    target_json = tmp_path / "target_registry.json"
    payload = {"phase": "phase_5", "status": "PASSED", "limit": 4096}

    with DependencyManager() as dm:
        dm.atomic_write_json(target_json, payload)

    assert target_json.exists()
    data = json.loads(target_json.read_text(encoding="utf-8"))
    assert data["status"] == "PASSED"
    assert data["limit"] == 4096


# =============================================================================
# 4. PATH RESOLUTION & DIRECTORY PROVISIONING TESTS
# =============================================================================


def test_get_current_username() -> None:
    """Verify username sanitization returns a non-empty alphanumeric string."""
    uname = get_current_username()
    assert isinstance(uname, str)
    assert len(uname) > 0
    assert " " not in uname


def test_resolve_mps_pipe_directory_default_and_custom(tmp_path: Path) -> None:
    """Verify resolve_mps_pipe_directory respects custom directory and defaults."""
    custom_dir = tmp_path / "custom_mps_pipe"
    res = resolve_mps_pipe_directory(custom_dir)
    assert res == custom_dir.resolve()
    assert res.exists()

    default_res = resolve_mps_pipe_directory()
    assert default_res.exists()
    assert "cochem_mps" in default_res.name


def test_resolve_mps_pipe_directory_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory respects CUDA_MPS_PIPE_DIRECTORY."""
    env_dir = tmp_path / "env_mps_pipe"
    monkeypatch.setenv("CUDA_MPS_PIPE_DIRECTORY", str(env_dir))
    res = resolve_mps_pipe_directory()
    assert res == env_dir.resolve()
    assert res.exists()


def test_resolve_mps_pipe_directory_slurm_hpc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory utilizes SLURM_TMPDIR in HPC envelopes."""
    monkeypatch.delenv("CUDA_MPS_PIPE_DIRECTORY", raising=False)
    slurm_dir = tmp_path / "slurm_tmp"
    slurm_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SLURM_TMPDIR", str(slurm_dir))
    res = resolve_mps_pipe_directory()
    assert slurm_dir in res.parents
    assert "cochem_mps" in res.name
    assert res.exists()


def test_resolve_mps_log_directory_default_and_custom(tmp_path: Path) -> None:
    """Verify resolve_mps_log_directory respects custom directory and defaults."""
    custom_log = tmp_path / "custom_mps_log"
    res = resolve_mps_log_directory(custom_log)
    assert res == custom_log.resolve()
    assert res.exists()

    default_log = resolve_mps_log_directory()
    assert default_log.exists()
    assert "cochem_mps_log" in default_log.name


def test_resolve_mps_log_directory_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_log_directory respects CUDA_MPS_LOG_DIRECTORY."""
    env_log = tmp_path / "env_log_dir"
    monkeypatch.setenv("CUDA_MPS_LOG_DIRECTORY", str(env_log))
    res = resolve_mps_log_directory()
    assert res == env_log.resolve()
    assert res.exists()


def test_enforce_socket_directory_permissions(tmp_path: Path) -> None:
    """Verify socket directory permissions enforcement."""
    test_dir = tmp_path / "socket_test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    ok, perm_str = enforce_socket_directory_permissions(test_dir)
    assert ok is True
    assert perm_str is not None
    if platform.system() != "Windows":
        mode = oct(stat.S_IMODE(test_dir.stat().st_mode))
        assert mode == "0o700"


def test_resolve_p5_registry_path(tmp_path: Path) -> None:
    """Verify resolve_p5_registry_path behavior."""
    custom_out = tmp_path / "custom_reg"
    p5_path = resolve_p5_registry_path(custom_out)
    assert p5_path == custom_out / "p5.json"

    direct_json = tmp_path / "p5.json"
    assert resolve_p5_registry_path(direct_json) == direct_json.resolve()

    default_p5 = resolve_p5_registry_path()
    assert default_p5.name == "p5.json"


# =============================================================================
# 5. VRAM BUDGETING & MEMORY PARTITIONING TESTS
# =============================================================================


def test_calculate_vram_budget_single_gpu() -> None:
    """Test VRAM budgeting formula for a single 24GB GPU."""
    dev = GPUDeviceVRAM(
        index=0,
        name="NVIDIA GeForce RTX 4090",
        uuid="GPU-UUID-001",
        total_vram_mb=24576.0,
        free_vram_mb=24000.0,
    )
    budget = calculate_vram_budget(
        devices=[dev],
        worker_concurrency_target=2,
        reserved_headroom_fraction=0.15,
        min_reserved_headroom_mb=1024.0,
    )
    assert budget.total_gpus_detected == 1
    assert budget.total_cluster_vram_mb == 24576.0
    # Reserved = 24576 * 0.15 = 3686.4 MB
    assert budget.total_reserved_vram_mb == pytest.approx(3686.4, rel=1e-2)
    # Allocatable = 24576 - 3686.4 = 20889.6 MB
    assert budget.total_allocatable_vram_mb == pytest.approx(20889.6, rel=1e-2)
    # Per worker = 20889.6 / 2 = 10444.8 -> int 10444 MB
    d0 = budget.active_gpu_devices[0]
    assert d0.allocated_limit_per_worker_mb == 10444.0
    assert d0.pinned_mem_limit_str == "0=10444M"
    assert d0.active_worker_capacity == 2
    assert budget.per_device_limits["0"] == "0=10444M"
    assert budget.default_pinned_mem_limit == "10444M"


def test_calculate_vram_budget_multi_gpu() -> None:
    """Test VRAM budgeting formula for dual heterogeneous GPUs."""
    dev0 = GPUDeviceVRAM(index=0, name="NVIDIA RTX A6000", total_vram_mb=49152.0)
    dev1 = GPUDeviceVRAM(index=1, name="NVIDIA RTX 3090", total_vram_mb=24576.0)

    budget = calculate_vram_budget(
        devices=[dev0, dev1],
        worker_concurrency_target=2,
    )
    assert budget.total_gpus_detected == 2
    assert budget.total_cluster_vram_mb == 73728.0
    assert "0" in budget.per_device_limits
    assert "1" in budget.per_device_limits

    # Dev 0: 49152 * 0.85 = 41779.2 -> 20889 MB per worker
    # Dev 1: 24576 * 0.85 = 20889.6 -> 10444 MB per worker
    d0 = budget.active_gpu_devices[0]
    d1 = budget.active_gpu_devices[1]
    assert d0.allocated_limit_per_worker_mb == 20889.0
    assert d1.allocated_limit_per_worker_mb == 10444.0
    assert d0.pinned_mem_limit_str == "0=20889M"
    assert d1.pinned_mem_limit_str == "1=10444M"


def test_calculate_vram_budget_custom_worker_count() -> None:
    """Test VRAM budgeting with high worker concurrency target (e.g. 4 workers)."""
    dev = GPUDeviceVRAM(index=0, name="NVIDIA A100-SXM4-80GB", total_vram_mb=81920.0)
    budget = calculate_vram_budget(
        devices=[dev],
        worker_concurrency_target=4,
    )
    assert budget.worker_concurrency_target == 4
    # Allocatable = 81920 - max(1024, 81920*0.15=12288) = 69632 MB
    # Per worker = 69632 / 4 = 17408 MB
    assert budget.active_gpu_devices[0].allocated_limit_per_worker_mb == 17408.0
    assert budget.active_gpu_devices[0].active_worker_capacity == 4
    assert budget.active_gpu_devices[0].pinned_mem_limit_str == "0=17408M"


def test_calculate_vram_budget_custom_vram_limit() -> None:
    """Test VRAM budgeting with explicit user-override custom limit."""
    dev = GPUDeviceVRAM(index=0, name="NVIDIA RTX 4090", total_vram_mb=24576.0)
    budget = calculate_vram_budget(
        devices=[dev],
        custom_limit_per_worker_mb=4096.0,
    )
    assert budget.active_gpu_devices[0].allocated_limit_per_worker_mb == 4096.0
    assert budget.active_gpu_devices[0].pinned_mem_limit_str == "0=4096M"
    # 20889.6 // 4096 = 5 workers capacity
    assert budget.active_gpu_devices[0].active_worker_capacity == 5


def test_calculate_vram_budget_zero_gpu_degraded() -> None:
    """Test VRAM budgeting behavior when zero physical GPUs are discovered."""
    budget = calculate_vram_budget(devices=[])
    assert budget.total_gpus_detected == 0
    assert budget.total_cluster_vram_mb == 0.0
    assert budget.strategy == "ZERO_GPU_DEGRADED"
    assert budget.default_pinned_mem_limit is None
    assert budget.per_device_limits == {}


def test_build_pinned_memory_limit_string() -> None:
    """Test build_pinned_memory_limit_string helper."""
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=8192.0)
    budget = calculate_vram_budget([dev], worker_concurrency_target=2)
    s0 = build_pinned_memory_limit_string(budget, device_index=0)
    assert "0=" in s0
    assert "M" in s0

    # Non-existent device should fall back to default limit string
    s_fallback = build_pinned_memory_limit_string(budget, device_index=99)
    assert s_fallback == budget.default_pinned_mem_limit


def test_probe_gpu_devices_vram_live_or_fallback(tmp_path: Path) -> None:
    """Verify probe_gpu_devices_vram executes without exceptions across platforms."""
    devices, is_cuda = probe_gpu_devices_vram()
    assert isinstance(devices, list)
    assert isinstance(is_cuda, bool)

    # Test reading synthetic p2.json
    p2_dir = tmp_path / "Registry"
    p2_dir.mkdir(parents=True, exist_ok=True)
    p2_file = p2_dir / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "timestamp_utc": "2026-08-21T00:00:00Z",
        "gpu": {
            "available": True,
            "cuda_available": True,
            "devices": [
                {
                    "index": 0,
                    "vendor": "NVIDIA",
                    "name": "NVIDIA H100 PCIe",
                    "memory_total_bytes": 85899345920,
                    "memory_free_bytes": 80000000000,
                    "compute_capability": "sm_90",
                    "uuid": "GPU-H100-TEST-UUID",
                }
            ],
        },
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    synth_devices, synth_cuda = probe_gpu_devices_vram(registry_p2_path=p2_file)
    assert synth_cuda is True
    assert len(synth_devices) == 1
    assert synth_devices[0].name == "NVIDIA H100 PCIe"
    assert synth_devices[0].total_vram_mb == pytest.approx(81920.0, rel=1e-2)
    assert synth_devices[0].compute_capability == "sm_90"


# =============================================================================
# 6. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE TESTS
# =============================================================================


def test_discover_mps_binaries() -> None:
    """Verify discover_mps_binaries scans and returns tuple of paths or None."""
    control_path, server_path = discover_mps_binaries()
    assert control_path is None or isinstance(control_path, str)
    assert server_path is None or isinstance(server_path, str)


def test_probe_mps_daemon_status(tmp_path: Path) -> None:
    """Verify probe_mps_daemon_status inspects directories and returns valid model."""
    pipe_dir = tmp_path / "test_pipe_dir"
    log_dir = tmp_path / "test_log_dir"
    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    audit = probe_mps_daemon_status(pipe_dir, log_dir)
    assert isinstance(audit, MPSDaemonAudit)
    assert audit.pipe_directory == str(pipe_dir)
    assert audit.log_directory == str(log_dir)
    assert audit.is_permission_secure is True


def test_start_and_stop_mps_daemon_lifecycle(tmp_path: Path) -> None:
    """Verify daemon start and stop functions execute cleanly across platforms."""
    pipe_dir = tmp_path / "test_pipe_lifecycle"
    log_dir = tmp_path / "test_log_lifecycle"

    # Testing on current OS without throwing unhandled crashes
    try:
        audit = start_mps_daemon(pipe_dir, log_dir, control_binary="nonexistent_mps_control")
        assert isinstance(audit, MPSDaemonAudit)
    except MPSControlError:
        pass

    stopped = stop_mps_daemon(pipe_dir, control_binary="nonexistent_mps_control")
    assert isinstance(stopped, bool)


def test_configure_mps_device_limit_offline(tmp_path: Path) -> None:
    """Verify configure_mps_device_limit returns False gracefully when binary is absent."""
    pipe_dir = tmp_path / "pipe_limit_test"
    res = configure_mps_device_limit(pipe_dir, device_index=0, limit_mb=4096, control_binary=None)
    assert res is False


# =============================================================================
# 7. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION TESTS
# =============================================================================


def test_inject_mps_environment_variables(tmp_path: Path) -> None:
    """Verify inject_mps_environment_variables populates os.environ and returns dict."""
    pipe_dir = tmp_path / "inj_pipe"
    log_dir = tmp_path / "inj_log"
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=16384.0)
    budget = calculate_vram_budget([dev])

    env_vars = inject_mps_environment_variables(pipe_dir, log_dir, budget)
    assert env_vars["CUDA_MPS_PIPE_DIRECTORY"] == str(pipe_dir)
    assert env_vars["CUDA_MPS_LOG_DIRECTORY"] == str(log_dir)
    assert env_vars["CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT"] == "1"
    assert "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT" in env_vars
    assert os.environ["CUDA_MPS_PIPE_DIRECTORY"] == str(pipe_dir)


def test_generate_mps_activation_scripts(tmp_path: Path) -> None:
    """Verify generate_mps_activation_scripts creates .sh, .bat, and .json files."""
    env_vars = {
        "CUDA_MPS_PIPE_DIRECTORY": "/tmp/cochem_mps_user",
        "CUDA_MPS_LOG_DIRECTORY": "/tmp/cochem_mps_log_user",
        "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": "0=4096M",
        "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT": "1",
    }
    scripts = generate_mps_activation_scripts(tmp_path, env_vars)
    assert "sh" in scripts
    assert "bat" in scripts
    assert "json" in scripts

    sh_file = scripts["sh"]
    bat_file = scripts["bat"]
    json_file = scripts["json"]

    assert sh_file.exists()
    assert bat_file.exists()
    assert json_file.exists()

    sh_content = sh_file.read_text(encoding="utf-8")
    assert "export CUDA_MPS_PIPE_DIRECTORY=\"/tmp/cochem_mps_user\"" in sh_content
    assert "export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=\"0=4096M\"" in sh_content

    bat_content = bat_file.read_text(encoding="utf-8")
    assert "set CUDA_MPS_PIPE_DIRECTORY=/tmp/cochem_mps_user" in bat_content
    assert "set CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=4096M" in bat_content

    json_data = json.loads(json_file.read_text(encoding="utf-8"))
    assert json_data["env_vars"]["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] == "0=4096M"


# =============================================================================
# 8. FULL PROGRAMMATIC AUDIT PIPELINE TESTS
# =============================================================================


def test_run_phase_5_audit_dry_run(tmp_path: Path) -> None:
    """Verify run_phase_5_audit in dry_run mode does not write files to disk."""
    out_dir = tmp_path / "dry_run_reg"
    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=tmp_path / "socket_dry",
        log_dir=tmp_path / "log_dry",
        dry_run=True,
    )
    assert isinstance(report, Phase5AuditReport)
    assert report.phase_id == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    # File should NOT exist in dry run
    assert not (out_dir / "p5.json").exists()


def test_run_phase_5_audit_live_execution(tmp_path: Path) -> None:
    """Verify run_phase_5_audit live execution atomically writes p5.json."""
    out_dir = tmp_path / "live_reg"
    socket_dir = tmp_path / "live_socket"
    log_dir = tmp_path / "live_log"

    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=socket_dir,
        log_dir=log_dir,
        worker_concurrency=2,
        dry_run=False,
    )
    assert isinstance(report, Phase5AuditReport)
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)

    # Artifact must be atomically written
    p5_artifact = Path(report.artifact_path)
    assert p5_artifact.exists()
    data = json.loads(p5_artifact.read_text(encoding="utf-8"))
    assert data["phase_id"] == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert "mps_daemon" in data
    assert "vram_budget" in data


def test_run_phase_5_audit_custom_parameters(tmp_path: Path) -> None:
    """Verify run_phase_5_audit with custom workers and explicit vram limit."""
    out_dir = tmp_path / "custom_reg"
    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=tmp_path / "custom_socket",
        log_dir=tmp_path / "custom_log",
        worker_concurrency=4,
        custom_vram_limit_mb=2048.0,
        dry_run=False,
    )
    assert report.vram_budget.worker_concurrency_target == 4
    if report.vram_budget.active_gpu_devices:
        assert report.vram_budget.active_gpu_devices[0].allocated_limit_per_worker_mb <= 2048.0


# =============================================================================
# 9. CLI ENTRYPOINT TESTS
# =============================================================================


def test_phase_5_cli_dry_run(tmp_path: Path) -> None:
    """Test CLI main with --dry-run option."""
    code = main([
        "--output-dir", str(tmp_path),
        "--socket-dir", str(tmp_path / "cli_socket"),
        "--log-dir", str(tmp_path / "cli_log"),
        "--dry-run",
    ])
    assert code == 0


def test_phase_5_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --json option prints serialized report."""
    code = main([
        "--output-dir", str(tmp_path),
        "--socket-dir", str(tmp_path / "cli_socket"),
        "--log-dir", str(tmp_path / "cli_log"),
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert data["status"] in ("PASSED", "DEGRADED")


def test_phase_5_cli_stop_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --stop option."""
    code = main(["--stop"])
    assert code == 0
    captured = capsys.readouterr()
    assert "MPS daemon" in captured.out


def test_phase_5_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --help option."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "CoChem Setup Phase 5" in captured.out


def test_resolve_mps_pipe_directory_slurm_job_id_scoping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory scopes by SLURM_JOB_ID when present."""
    monkeypatch.delenv("CUDA_MPS_PIPE_DIRECTORY", raising=False)
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    res = resolve_mps_pipe_directory()
    assert "123456" in res.name


def test_inject_mps_environment_variables_thread_percentage(tmp_path: Path) -> None:
    """Verify CUDA_MPS_ACTIVE_THREAD_PERCENTAGE calculation in environment injection."""
    pipe_dir = tmp_path / "thread_pipe"
    log_dir = tmp_path / "thread_log"
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=16384.0)
    budget = calculate_vram_budget([dev], worker_concurrency_target=4)
    env_vars = inject_mps_environment_variables(pipe_dir, log_dir, budget)
    assert env_vars["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "25"


def test_probe_mps_daemon_status_with_server_binary(tmp_path: Path) -> None:
    """Verify probe_mps_daemon_status properly binds server_binary."""
    pipe_dir = tmp_path / "pipe_srv"
    log_dir = tmp_path / "log_srv"
    audit = probe_mps_daemon_status(
        pipe_dir,
        log_dir,
        control_binary="/usr/bin/nvidia-cuda-mps-control",
        server_binary="/usr/bin/nvidia-cuda-mps-server",
    )
    assert audit.mps_server_binary == "/usr/bin/nvidia-cuda-mps-server"


# =============================================================================
# 10. IPC CONFIG LOCK & POSIX BYTE-RANGE LOCKING TESTS
# =============================================================================


def test_lock_test_result_model() -> None:
    """Test LockTestResult Pydantic v2 model construction and validation."""
    ltr = LockTestResult(
        passed=True,
        method="POSIX_FCNTL_LOCKF",
        single_threaded_mode=False,
        target_path="/tmp/lock_probe.lock",
        lock_type="POSIX_BYTE_RANGE_LOCK",
    )
    assert ltr.passed is True
    assert ltr.single_threaded_mode is False
    assert ltr.method == "POSIX_FCNTL_LOCKF"

    dumped = ltr.model_dump()
    assert dumped["passed"] is True
    restored = LockTestResult.model_validate(dumped)
    assert restored == ltr


def test_workspace_sweep_report_model() -> None:
    """Test WorkspaceSweepReport Pydantic v2 model construction and serialization."""
    report = WorkspaceSweepReport(
        swept_files_count=3,
        cleaned_paths=["/tmp/a.tmp", "/tmp/b.tmp"],
        retained_paths=["/reg/cochem_system_config.json"],
        trash_dir="/tmp/trash",
    )
    assert report.swept_files_count == 3
    assert len(report.cleaned_paths) == 2
    assert len(report.retained_paths) == 1


def test_config_lock_audit_report_model() -> None:
    """Test ConfigLockAuditReport Pydantic v2 model validation."""
    audit = ConfigLockAuditReport(
        golden_registry_path="/reg/cochem_system_config.json",
        status="LOCKED",
        checksum="a" * 64,
        posix_lock_test=LockTestResult(
            passed=True,
            method="POSIX_FCNTL_LOCKF",
            single_threaded_mode=False,
            target_path="/reg/.lock_probe.lock",
        ),
        sweep_report=WorkspaceSweepReport(),
        intermediate_phases_found=["p1.json", "p2.json"],
        is_immutable_mode_enforced=True,
    )
    assert audit.status == "LOCKED"
    assert len(audit.checksum) == 64
    assert audit.posix_lock_test.passed is True


def test_posix_byte_range_locking_live_filesystem(tmp_path: Path) -> None:
    """Verify posix_byte_range_locking_fn executes real locking against directory."""
    res = posix_byte_range_locking_fn(target_dir=tmp_path)
    assert isinstance(res, LockTestResult)
    assert res.passed is True
    assert res.single_threaded_mode is False
    assert res.method in ("POSIX_FCNTL_LOCKF", "MSVCRT_LOCKING_BYTE_RANGE", "GENERIC_FALLBACK_LOCK")


def test_posix_byte_range_locking_invalid_dir() -> None:
    """Verify posix_byte_range_locking_fn handles invalid paths gracefully with single-threaded mode."""
    invalid_path = Path("/nonexistent_forbidden_dir_12345/subdir")
    res = posix_byte_range_locking_fn(target_dir=invalid_path)
    assert isinstance(res, LockTestResult)
    if not res.passed:
        assert res.single_threaded_mode is True
        assert res.error_message is not None


# =============================================================================
# 11. INTERMEDIATE STATE CONSOLIDATION (p1.json -> p11.json) TESTS
# =============================================================================


def test_consolidate_intermediate_states_synthetic_phases(tmp_path: Path) -> None:
    """Verify consolidate_intermediate_states extracts and aggregates all phase sections."""
    reg_dir = tmp_path / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic p1.json
    p1 = {
        "phase_id": "PHASE_1_ENVIRONMENT_GATEKEEPER",
        "os_profile": {"system": "Linux"},
    }
    (reg_dir / "p1.json").write_text(json.dumps(p1), encoding="utf-8")

    # Synthetic p2.json
    p2 = {
        "phase_id": "PHASE_2_HARDWARE_SURVEYOR",
        "memory": {"total_physical_bytes": 34359738368},
        "cpu": {"physical_cores": 8, "logical_cores": 16, "avx512_support": True},
        "gpu": {"gpu_available": True, "devices": [{"name": "RTX 4090", "memory_total_bytes": 25769803776}]},
    }
    (reg_dir / "p2.json").write_text(json.dumps(p2), encoding="utf-8")

    # Synthetic p3.json
    p3 = {
        "phase_id": "PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        "engines": {
            "orca": {
                "name": "orca",
                "path": str(tmp_path / "orca"),
                "version": "6.1.1",
                "sha256_hash": "8d6b51bf4093c967dbed997cc651f0212b8f94313ee77ea56f548f000672c42f",
                "status": "FOUND_VALID",
            }
        },
    }
    (reg_dir / "p3.json").write_text(json.dumps(p3), encoding="utf-8")

    # Synthetic p4.json
    p4 = {
        "phase_id": "PHASE_4_MICRO_SILO_PROVISIONING",
        "silos": {"cochem_core_silo": {"status": "PROVISIONED"}, "cochem_mace_silo": {"status": "PROVISIONED"}},
    }
    (reg_dir / "p4.json").write_text(json.dumps(p4), encoding="utf-8")

    # Synthetic p10.json & p11.json
    (reg_dir / "p10.json").write_text(json.dumps({"alignment_engine_ready": True}), encoding="utf-8")
    (reg_dir / "p11.json").write_text(json.dumps({"oom_shield": {"maxcore_mb": 4096}}), encoding="utf-8")

    consolidated, found = consolidate_intermediate_states(registry_dir=reg_dir)

    assert "p1.json" in found
    assert "p2.json" in found
    assert "p3.json" in found
    assert "p4.json" in found
    assert "p10.json" in found
    assert "p11.json" in found

    assert consolidated["hardware"]["cpu_physical_cores"] == 8
    assert consolidated["hardware"]["ram_gb"] == pytest.approx(32.0, rel=1e-1)
    assert consolidated["hardware"]["maxcore_mb"] == 4096
    assert consolidated["silos"]["gpu_silo_active"] is True
    assert consolidated["alignment_engine_ready"] is True
    assert "orca" in consolidated["engines"]
    assert consolidated["engines"]["orca"]["status"] == "found"


def test_consolidate_intermediate_states_empty_directory(tmp_path: Path) -> None:
    """Verify consolidate_intermediate_states returns empty dict gracefully when no p*.json files exist."""
    empty_dir = tmp_path / "empty_reg"
    empty_dir.mkdir(parents=True, exist_ok=True)

    consolidated, found = consolidate_intermediate_states(registry_dir=empty_dir, search_dirs=[])
    assert isinstance(consolidated, dict)
    assert isinstance(found, list)


# =============================================================================
# 12. MASTER SYSTEM CONFIG VALIDATION & IMMUTABLE LOCKING TESTS
# =============================================================================


def test_validate_and_build_system_config_locks_and_seals() -> None:
    """Verify validate_and_build_system_config sets status='LOCKED' and recalculates checksum."""
    raw_data = {
        "hardware": {
            "ram_gb": 32.0,
            "cpu_physical_cores": 8,
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
        },
        "environment": {
            "os_target": "Local-Linux",
        },
    }
    cfg = validate_and_build_system_config(consolidated_data=raw_data)
    assert cfg.status == "LOCKED"
    assert cfg.schema_version == "4.0.0"
    assert cfg.hardware.ram_gb == 32.0
    assert cfg.verify_checksum() is True


def test_validate_and_build_system_config_single_threaded_mode() -> None:
    """Verify validate_and_build_system_config limits compute cores when single_threaded_mode is True."""
    cfg = validate_and_build_system_config(
        consolidated_data={"hardware": {"ram_gb": 16.0, "cpu_physical_cores": 8}},
        single_threaded_mode=True,
    )
    assert cfg.hardware.allocatable_compute_cores == 1


def test_finalize_and_lock_golden_registry_and_chmod(tmp_path: Path) -> None:
    """Verify finalize_and_lock_golden_registry writes cochem_system_config.json and applies 0o444."""
    out_file = tmp_path / "Registry" / "cochem_system_config.json"
    cfg = validate_and_build_system_config()

    path_res, serialized = finalize_and_lock_golden_registry(
        cfg=cfg,
        output_path=out_file,
        dry_run=False,
    )
    assert path_res.exists()
    assert serialized["status"] == "LOCKED"

    # Check read-only attribute / permissions
    file_stat = path_res.stat()
    assert bool(file_stat.st_mode & stat.S_IREAD)
    if platform.system() != "Windows":
        mode_octal = oct(stat.S_IMODE(file_stat.st_mode))
        assert "4" in mode_octal

    # Verify content parses cleanly
    data = json.loads(path_res.read_text(encoding="utf-8"))
    assert data["status"] == "LOCKED"
    assert "hardware" in data

    # Unset read-only attribute so tmp_path fixture can clean up
    try:
        os.chmod(path_res, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


# =============================================================================
# 13. WORKSPACE GARBAGE COLLECTION SWEEP TESTS
# =============================================================================


def test_execute_workspace_sweep_cleans_ephemeral_preserves_registry(tmp_path: Path) -> None:
    """Verify execute_workspace_sweep cleans .tmp files while preserving cochem_system_config.json."""
    ws = tmp_path / "workspace"
    reg = tmp_path / "registry"
    ws.mkdir(parents=True, exist_ok=True)
    reg.mkdir(parents=True, exist_ok=True)

    # Ephemeral files
    f_tmp1 = ws / "test_module.tmp"
    f_tmp2 = ws / "staging.tmp.1234"
    f_lock = reg / ".cochem_swmr_lock_probe.lock"
    f_tmp1.write_text("transient", encoding="utf-8")
    f_tmp2.write_text("transient", encoding="utf-8")
    f_lock.write_text("probe", encoding="utf-8")

    # Persistent files
    f_perm = ws / "user_input.xyz"
    f_golden = reg / "cochem_system_config.json"
    f_perm.write_text("C 0 0 0", encoding="utf-8")
    f_golden.write_text('{"status": "LOCKED"}', encoding="utf-8")

    report = execute_workspace_sweep(
        workspace_dir=ws,
        registry_dir=reg,
        dry_run=False,
        remove_intermediate_json=False,
    )

    assert report.swept_files_count >= 3
    assert not f_tmp1.exists()
    assert not f_tmp2.exists()
    assert not f_lock.exists()
    assert f_perm.exists()
    assert f_golden.exists()


def test_execute_workspace_sweep_dry_run(tmp_path: Path) -> None:
    """Verify execute_workspace_sweep in dry_run mode does not unlink files."""
    ws = tmp_path / "ws_dry"
    ws.mkdir(parents=True, exist_ok=True)
    f_tmp = ws / "ephemeral.tmp"
    f_tmp.write_text("tmp", encoding="utf-8")

    report = execute_workspace_sweep(
        workspace_dir=ws,
        dry_run=True,
    )
    assert report.swept_files_count == 1
    assert f_tmp.exists()


# =============================================================================
# 14. FULL INTEGRATED PHASE 5 PIPELINE WITH CONFIG LOCK TESTS
# =============================================================================


def test_run_phase_5_audit_full_integration(tmp_path: Path) -> None:
    """Verify run_phase_5_audit executes both MPS and Config Lock & Sweep pipelines."""
    out_dir = tmp_path / "FullReg"
    socket_dir = tmp_path / "FullSocket"
    log_dir = tmp_path / "FullLog"

    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=socket_dir,
        log_dir=log_dir,
        worker_concurrency=2,
        dry_run=False,
        sweep_workspace=True,
    )

    assert report.status is PhaseStatus.PASSED
    assert report.config_lock is not None
    assert report.config_lock.status == "LOCKED"
    assert report.config_lock.posix_lock_test.passed is True
    assert (out_dir / "p5.json").exists()
    assert (out_dir / "cochem_system_config.json").exists()

    # Clean up read-only permissions for teardown
    try:
        os.chmod(out_dir / "cochem_system_config.json", stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def test_resolve_golden_config_path_custom_and_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_golden_config_path handles custom path and environment overrides."""
    custom_p = tmp_path / "my_config.json"
    res1 = resolve_golden_config_path(custom_p)
    assert res1 == custom_p.resolve()

    monkeypatch.setenv("COCHEM_CONFIG", str(tmp_path / "env_config.json"))
    res2 = resolve_golden_config_path()
    assert res2 == (tmp_path / "env_config.json").resolve()


