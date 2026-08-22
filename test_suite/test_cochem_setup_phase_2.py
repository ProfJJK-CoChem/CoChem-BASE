"""
Unit test suite for CoChem Setup Phase 2: Hardware & Resource Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, live CPU/memory interrogations,
deterministic Pydantic V2 schema validations, real cgroups v1/v2 synthetic fixtures,
real IEEE-754 subnormal floating-point arithmetic, real atomic I/O, and real rollback mechanics.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import pytest

from orchestrator.cochem_setup_phase_2 import (
    CPUAudit,
    DependencyManager,
    GPUDevice,
    GPUProfile,
    IEEE754PrecisionAudit,
    MemoryAudit,
    Phase2AuditReport,
    PhaseStatus,
    audit_cpu,
    audit_gpus,
    audit_memory,
    get_absolute_physical_ram,
    main,
    parse_cgroup_cpu_quota,
    parse_cgroup_memory_limit,
    probe_amd_gpus,
    probe_intel_gpus,
    probe_nvidia_gpus,
    resolve_p2_registry_path,
    run_phase_2_audit,
    verify_ieee754_subnormal_precision,
)

# =============================================================================
# 1. PYDANTIC V2 SCHEMA & ENUM VALIDATION TESTS
# =============================================================================


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum definitions and string representations."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED
    assert PhaseStatus("FAILED") is PhaseStatus.FAILED
    assert PhaseStatus("DEGRADED") is PhaseStatus.DEGRADED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_memory_audit_model_valid() -> None:
    """Test MemoryAudit model initialization and serialization with valid fields."""
    mem = MemoryAudit(
        total_bytes=17179869184,  # 16 GB
        available_bytes=8589934592,  # 8 GB
        swap_total_bytes=4294967296,  # 4 GB
        swap_free_bytes=2147483648,  # 2 GB
        cgroup_memory_limit_bytes=10737418240,  # 10 GB
        cgroup_swap_limit_bytes=None,
        is_cgroup_constrained=True,
        effective_memory_bytes=10737418240,
    )
    assert mem.total_bytes == 17179869184
    assert mem.available_bytes == 8589934592
    assert mem.is_cgroup_constrained is True
    assert mem.effective_memory_bytes == 10737418240

    dumped = mem.model_dump()
    assert dumped["total_bytes"] == 17179869184
    restored = MemoryAudit.model_validate(dumped)
    assert restored == mem


def test_memory_audit_model_unconstrained() -> None:
    """Test MemoryAudit model when no cgroup constraints exist."""
    mem = MemoryAudit(
        total_bytes=34359738368,  # 32 GB
        available_bytes=25769803776,  # 24 GB
        swap_total_bytes=0,
        swap_free_bytes=0,
        cgroup_memory_limit_bytes=None,
        cgroup_swap_limit_bytes=None,
        is_cgroup_constrained=False,
        effective_memory_bytes=34359738368,
    )
    assert mem.is_cgroup_constrained is False
    assert mem.effective_memory_bytes == mem.total_bytes
    assert mem.cgroup_memory_limit_bytes is None


def test_cpu_audit_model_valid() -> None:
    """Test CPUAudit model initialization and validation."""
    cpu = CPUAudit(
        physical_cores=8,
        logical_cores=16,
        frequency_mhz=3600.0,
        cgroup_cpu_quota_us=400000,
        cgroup_cpu_period_us=100000,
        cgroup_effective_cpus=4.0,
        cpu_affinity_count=16,
        architecture="x86_64",
    )
    assert cpu.physical_cores == 8
    assert cpu.logical_cores == 16
    assert cpu.frequency_mhz == 3600.0
    assert cpu.cgroup_effective_cpus == 4.0
    assert cpu.architecture == "x86_64"

    dumped = cpu.model_dump()
    assert dumped["logical_cores"] == 16
    restored = CPUAudit.model_validate(dumped)
    assert restored == cpu


def test_gpu_device_model() -> None:
    """Test GPUDevice model initialization and fields."""
    dev = GPUDevice(
        index=0,
        vendor="NVIDIA",
        name="NVIDIA GeForce RTX 4090",
        memory_total_bytes=25769803776,  # 24 GB
        memory_free_bytes=23622320128,  # 22 GB
        driver_version="555.42.02",
        compute_capability="8.9",
        uuid="GPU-12345678-abcd-ef01-2345-6789abcdef01",
    )
    assert dev.index == 0
    assert dev.vendor == "NVIDIA"
    assert dev.compute_capability == "8.9"
    assert dev.memory_total_bytes == 25769803776


def test_gpu_profile_model() -> None:
    """Test GPUProfile model representing heterogeneous accelerator configurations."""
    profile = GPUProfile(
        available=True,
        vendor_summary={"NVIDIA": 1},
        devices=[
            GPUDevice(
                index=0,
                vendor="NVIDIA",
                name="NVIDIA RTX 4090",
                memory_total_bytes=25769803776,
                memory_free_bytes=23622320128,
                driver_version="555.42.02",
                compute_capability="8.9",
                uuid="GPU-0001",
            )
        ],
        cuda_available=True,
        rocm_available=False,
        oneapi_available=False,
        degraded_fallback=False,
    )
    assert profile.available is True
    assert profile.cuda_available is True
    assert profile.degraded_fallback is False
    assert len(profile.devices) == 1
    assert profile.vendor_summary["NVIDIA"] == 1


def test_ieee754_precision_audit_model() -> None:
    """Test IEEE754PrecisionAudit model field validation."""
    precision = IEEE754PrecisionAudit(
        float32_epsilon=1.1920928955078125e-07,
        float64_epsilon=2.220446049250313e-16,
        subnormal_supported=True,
        smallest_subnormal_f64=4.9406564584124654e-324,
        smallest_normal_f64=2.2250738585072014e-308,
        subnormal_arithmetic_valid=True,
        precision_intact=True,
        precision_message="Float Precision: Intact",
    )
    assert precision.subnormal_supported is True
    assert precision.precision_intact is True
    assert precision.precision_message == "Float Precision: Intact"
    assert precision.smallest_subnormal_f64 > 0.0


def test_phase2_audit_report_full_schema(tmp_path: Path) -> None:
    """Test Phase2AuditReport comprehensive schema validation and JSON round-trip."""
    report = Phase2AuditReport(
        phase_id="PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T22:30:00Z",
        memory=MemoryAudit(
            total_bytes=17179869184,
            available_bytes=12884901888,
            swap_total_bytes=4294967296,
            swap_free_bytes=4294967296,
            cgroup_memory_limit_bytes=None,
            cgroup_swap_limit_bytes=None,
            is_cgroup_constrained=False,
            effective_memory_bytes=17179869184,
        ),
        cpu=CPUAudit(
            physical_cores=8,
            logical_cores=16,
            frequency_mhz=3600.0,
            cgroup_cpu_quota_us=None,
            cgroup_cpu_period_us=None,
            cgroup_effective_cpus=None,
            cpu_affinity_count=16,
            architecture="x86_64",
        ),
        gpu=GPUProfile(
            available=False,
            vendor_summary={},
            devices=[],
            cuda_available=False,
            rocm_available=False,
            oneapi_available=False,
            degraded_fallback=True,
        ),
        precision=IEEE754PrecisionAudit(
            float32_epsilon=1.1920928955078125e-07,
            float64_epsilon=2.220446049250313e-16,
            subnormal_supported=True,
            smallest_subnormal_f64=4.9406564584124654e-324,
            smallest_normal_f64=2.2250738585072014e-308,
            subnormal_arithmetic_valid=True,
            precision_intact=True,
            precision_message="Float Precision: Intact",
        ),
        warnings=["No hardware GPU accelerator detected; falling back to CPU execution"],
        errors=[],
        artifact_path=str(tmp_path / "Registry" / "p2.json"),
    )
    assert report.phase_id == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert report.status is PhaseStatus.PASSED

    # Roundtrip through JSON
    json_str = report.model_dump_json(indent=2)
    assert "Float Precision: Intact" in json_str
    parsed = Phase2AuditReport.model_validate_json(json_str)
    assert parsed.phase_id == report.phase_id
    assert parsed.memory.total_bytes == report.memory.total_bytes
    assert parsed.precision.precision_intact is True


# =============================================================================
# 2. CGROUPS V1 & V2 SYNTHETIC FILESYSTEM PARSING TESTS (ZERO MOCKS)
# =============================================================================


def test_cgroup_v2_memory_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 memory.max numeric parsing on real filesystem fixture."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    mem_max_file = cg_dir / "memory.max"
    mem_max_file.write_text("4294967296\n", encoding="utf-8")  # 4 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 4294967296
    assert swap_limit is None


def test_cgroup_v2_memory_limit_max_string(tmp_path: Path) -> None:
    """Test cgroups v2 memory.max 'max' string parsing indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("max\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None
    assert swap_limit is None


def test_cgroup_v2_swap_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 memory.swap.max numeric and memory.max numeric."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("8589934592\n", encoding="utf-8")  # 8 GB
    (cg_dir / "memory.swap.max").write_text("2147483648\n", encoding="utf-8")  # 2 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 8589934592
    assert swap_limit == 2147483648


def test_cgroup_v2_cpu_quota_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 cpu.max numeric quota and period (e.g. 2.5 CPUs)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("250000 100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 250000
    assert effective_cpus == 2.5


def test_cgroup_v2_cpu_quota_max_string(tmp_path: Path) -> None:
    """Test cgroups v2 cpu.max 'max' string indicates unlimited CPU quota."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("max 100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v1_memory_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes numeric parsing."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("2147483648\n", encoding="utf-8")  # 2 GB
    (cg_dir / "memory.memsw.limit_in_bytes").write_text("4294967296\n", encoding="utf-8")  # 4 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 2147483648
    assert swap_limit == 4294967296


def test_cgroup_v1_memory_limit_unlimited_large_int(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes large int (0x7FFFFFFFFFFFF000) indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("9223372036854771712\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None


def test_cgroup_v1_memory_limit_unlimited_negative(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes -1 indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("-1\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None


def test_cgroup_v1_cpu_quota_numeric(tmp_path: Path) -> None:
    """Test cgroups v1 cpu.cfs_quota_us and cpu.cfs_period_us (4.0 CPUs)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("400000\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 400000
    assert effective_cpus == 4.0


def test_cgroup_v1_cpu_quota_unlimited_negative(tmp_path: Path) -> None:
    """Test cgroups v1 cpu.cfs_quota_us -1 indicates unlimited CPU allocation."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("-1\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_missing_files(tmp_path: Path) -> None:
    """Test graceful handling when cgroup files do not exist (returns None, None)."""
    empty_root = tmp_path / "empty_root"
    empty_root.mkdir()
    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=empty_root)
    assert mem_limit is None
    assert swap_limit is None

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=empty_root)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_corrupted_content(tmp_path: Path) -> None:
    """Test resilient parsing when cgroup files contain invalid/corrupted non-numeric data."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("corrupted_non_numeric_garbage\n", encoding="utf-8")
    (cg_dir / "cpu.max").write_text("invalid_quota_format\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None
    assert swap_limit is None

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


# =============================================================================
# 3. CPU TOPOLOGY & PSUTIL MEMORY PROBING TESTS
# =============================================================================


def test_get_absolute_physical_ram() -> None:
    """Verify absolute physical RAM detection returns positive byte count."""
    ram = get_absolute_physical_ram()
    assert isinstance(ram, int)
    assert ram > 0
    # Physical RAM on standard machines should be at least 1 GB
    assert ram >= 1024 * 1024 * 1024


def test_audit_memory_real_host() -> None:
    """Test live host memory auditing via psutil and OS interfaces."""
    mem_audit = audit_memory()
    assert isinstance(mem_audit, MemoryAudit)
    assert mem_audit.total_bytes > 0
    assert mem_audit.available_bytes > 0
    assert mem_audit.effective_memory_bytes > 0
    assert mem_audit.effective_memory_bytes <= mem_audit.total_bytes
    assert mem_audit.available_bytes <= mem_audit.total_bytes


def test_audit_memory_with_synthetic_cgroup_limit(tmp_path: Path) -> None:
    """Test memory auditing when cgroup limits constrain memory below physical RAM."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # Set limit to 1 GB (which is smaller than any standard test machine RAM)
    (cg_dir / "memory.max").write_text("1073741824\n", encoding="utf-8")

    mem_audit = audit_memory(cgroup_root=tmp_path)
    assert mem_audit.cgroup_memory_limit_bytes == 1073741824
    assert mem_audit.is_cgroup_constrained is True
    assert mem_audit.effective_memory_bytes == 1073741824


def test_audit_cpu_real_host() -> None:
    """Test live CPU topology interrogation."""
    cpu_audit = audit_cpu()
    assert isinstance(cpu_audit, CPUAudit)
    assert cpu_audit.physical_cores >= 1
    assert cpu_audit.logical_cores >= 1
    assert cpu_audit.logical_cores >= cpu_audit.physical_cores
    assert cpu_audit.architecture != ""
    if cpu_audit.frequency_mhz is not None:
        assert cpu_audit.frequency_mhz > 0.0


def test_audit_cpu_with_synthetic_cgroup_quota(tmp_path: Path) -> None:
    """Test CPU auditing with synthetic cgroup quota."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("200000 100000\n", encoding="utf-8")  # 2.0 CPUs

    cpu_audit = audit_cpu(cgroup_root=tmp_path)
    assert cpu_audit.cgroup_cpu_quota_us == 200000
    assert cpu_audit.cgroup_cpu_period_us == 100000
    assert cpu_audit.cgroup_effective_cpus == 2.0


# =============================================================================
# 4. HETEROGENEOUS GPU DISCOVERY TESTS (ZERO MOCKS)
# =============================================================================


def test_probe_nvidia_gpus_execution() -> None:
    """Execute live NVIDIA GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_nvidia_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "NVIDIA"
        assert dev.index >= 0


def test_probe_amd_gpus_execution() -> None:
    """Execute live AMD GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_amd_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "AMD"


def test_probe_intel_gpus_execution() -> None:
    """Execute live Intel GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_intel_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "INTEL"


def test_audit_gpus_real() -> None:
    """Audit GPU accelerators on the host system, ensuring valid GPUProfile."""
    gpu_profile = audit_gpus()
    assert isinstance(gpu_profile, GPUProfile)
    assert isinstance(gpu_profile.devices, list)
    assert isinstance(gpu_profile.vendor_summary, dict)
    if not gpu_profile.available:
        assert gpu_profile.degraded_fallback is True
    else:
        assert len(gpu_profile.devices) > 0


# =============================================================================
# 5. REAL IEEE-754 SUBNORMAL PRECISION & MACHINE EPSILON AUDIT TESTS
# =============================================================================


def test_ieee754_subnormal_precision_live() -> None:
    """Execute live IEEE-754 precision audit and verify subnormal arithmetic and message."""
    precision = verify_ieee754_subnormal_precision()
    assert isinstance(precision, IEEE754PrecisionAudit)
    assert precision.precision_intact is True
    assert precision.subnormal_supported is True
    assert precision.subnormal_arithmetic_valid is True
    assert precision.precision_message == "Float Precision: Intact"
    assert precision.smallest_normal_f64 == sys.float_info.min
    assert precision.smallest_subnormal_f64 > 0.0
    assert precision.smallest_subnormal_f64 < precision.smallest_normal_f64


def test_ieee754_math_assertions() -> None:
    """Directly assert IEEE-754 subnormal properties and absence of flush-to-zero (FTZ)."""
    # Smallest positive normal double float (2^-1022)
    normal_min = math.ldexp(1.0, -1022)
    assert normal_min == sys.float_info.min

    # Smallest positive subnormal double float (2^-1074)
    subnormal_min = math.ldexp(1.0, -1074)
    assert subnormal_min > 0.0

    # Subnormal arithmetic verification
    sub_a = math.ldexp(1.0, -1073)  # 2 * subnormal_min
    sub_b = subnormal_min
    diff = sub_a - sub_b
    assert diff == subnormal_min
    assert diff > 0.0

    # Gradual underflow to zero
    underflow = subnormal_min / 2.0
    assert underflow == 0.0

    # Machine epsilon verification
    eps_f64 = sys.float_info.epsilon
    assert (1.0 + eps_f64) > 1.0
    assert (1.0 + (eps_f64 / 2.0)) == 1.0

    # Float32 machine epsilon check
    eps_f32 = struct.unpack("f", struct.pack("f", 1.0 + 2**-23))[0] - 1.0
    assert eps_f32 > 0.0
    assert abs(eps_f32 - 1.1920928955078125e-07) < 1e-12


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER & ATOMIC PERSISTENCE TESTS
# =============================================================================


def test_dependency_manager_atomic_write(tmp_path: Path) -> None:
    """Verify atomic JSON writing creates target file and removes temporary staging file."""
    dm = DependencyManager()
    target_file = tmp_path / "Registry" / "p2.json"
    payload = {"phase": "PHASE_2", "status": "PASSED"}

    with dm:
        written_path = dm.atomic_write_json(target_file, payload)
        assert written_path.exists()

    assert target_file.exists()
    content = json.loads(target_file.read_text(encoding="utf-8"))
    assert content["phase"] == "PHASE_2"
    assert content["status"] == "PASSED"
    assert len(dm._tracked_temp_files) == 0


def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify transactional cleanup of staged files when an unhandled exception occurs."""
    dm = DependencyManager()
    staged_file: Path

    with pytest.raises(RuntimeError, match="Simulation Failure"):
        with dm:
            staged_file = dm.create_temp_file(directory=tmp_path)
            assert staged_file.exists()
            raise RuntimeError("Simulation Failure")

    assert not staged_file.exists()


def test_dependency_manager_manual_rollback(tmp_path: Path) -> None:
    """Verify manual rollback explicitly purges tracked temporary files and directories."""
    dm = DependencyManager()
    f1 = dm.create_temp_file(directory=tmp_path)
    d1 = dm.create_temp_dir(directory=tmp_path)
    assert f1.exists()
    assert d1.exists()

    dm.rollback()
    assert not f1.exists()
    assert not d1.exists()


# =============================================================================
# 7. REGISTRY RESOLUTION & AUDIT EXECUTION TESTS
# =============================================================================


def test_resolve_p2_registry_path_default() -> None:
    """Verify default Registry/p2.json path resolution."""
    resolved = resolve_p2_registry_path()
    assert resolved.name == "p2.json"
    assert resolved.parent.name == "Registry"


def test_resolve_p2_registry_path_custom(tmp_path: Path) -> None:
    """Verify path resolution with explicit output_dir and target_path."""
    custom_out = tmp_path / "custom_out"
    resolved_out = resolve_p2_registry_path(output_dir=custom_out)
    assert resolved_out == (custom_out / "p2.json").resolve()

    custom_tgt = tmp_path / "workspace"
    resolved_tgt = resolve_p2_registry_path(target_path=custom_tgt)
    assert resolved_tgt == (custom_tgt / "Registry" / "p2.json").resolve()


def test_run_phase_2_audit_execution(tmp_path: Path) -> None:
    """Execute complete Phase 2 audit and assert report artifact serialization."""
    report = run_phase_2_audit(output_dir=tmp_path)
    assert isinstance(report, Phase2AuditReport)
    assert report.phase_id == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.precision.precision_intact is True
    assert report.precision.precision_message == "Float Precision: Intact"

    p2_file = tmp_path / "p2.json"
    assert p2_file.exists()
    saved_data = json.loads(p2_file.read_text(encoding="utf-8"))
    assert saved_data["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert saved_data["precision"]["precision_message"] == "Float Precision: Intact"


# =============================================================================
# 8. CLI INTEGRATION TESTS
# =============================================================================


def test_cli_main_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI invocation with --json and --output-dir flags."""
    exit_code = main(["--output-dir", str(tmp_path), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    stdout_text = captured.out

    assert "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER" in stdout_text
    assert "Float Precision: Intact" in stdout_text
    parsed = json.loads(stdout_text)
    assert parsed["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert (tmp_path / "p2.json").exists()


def test_cli_main_standard_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test standard human-readable CLI banner output."""
    exit_code = main(["--output-dir", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    stdout_text = captured.out

    assert "COCHEM SETUP PHASE 2: HARDWARE & RESOURCE GATEKEEPER AUDIT" in stdout_text
    assert "Float Precision: Intact" in stdout_text
    assert (tmp_path / "p2.json").exists()


def test_cli_main_target_path_flag(tmp_path: Path) -> None:
    """Test CLI invocation with --target-path creating Registry/p2.json."""
    exit_code = main(["--target-path", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "Registry" / "p2.json").exists()


def test_resolve_p2_registry_path_direct_file(tmp_path: Path) -> None:
    """Verify path resolution when output_dir directly points to a .json filename."""
    direct_file = tmp_path / "custom_p2_report.json"
    resolved = resolve_p2_registry_path(output_dir=direct_file)
    assert resolved == direct_file.resolve()


def test_dependency_manager_atomic_write_scalar_and_list(tmp_path: Path) -> None:
    """Verify atomic writing works for lists and scalar types."""
    dm = DependencyManager()
    list_file = tmp_path / "list.json"
    scalar_file = tmp_path / "scalar.json"

    with dm:
        dm.atomic_write_json(list_file, [1, 2, 3])
        dm.atomic_write_json(scalar_file, "pure_string_data")

    assert json.loads(list_file.read_text(encoding="utf-8")) == [1, 2, 3]
    assert json.loads(scalar_file.read_text(encoding="utf-8")) == "pure_string_data"


def test_cgroup_v1_cpu_quota_zero_period(tmp_path: Path) -> None:
    """Test cgroup v1 cpu period of 0 does not raise ZeroDivisionError."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("100000\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("0\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v2_cpu_quota_zero_period(tmp_path: Path) -> None:
    """Test cgroup v2 cpu period of 0 does not raise ZeroDivisionError."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("100000 0\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v2_cpu_quota_single_token(tmp_path: Path) -> None:
    """Test cgroup v2 cpu.max with single quota token defaults period to 100000."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("300000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 300000
    assert effective_cpus == 3.0


def test_run_phase_2_audit_low_memory_warning(tmp_path: Path) -> None:
    """Verify warning is registered when effective memory is constrained below 4GB."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # 512 MB cgroup memory limit
    (cg_dir / "memory.max").write_text("536870912\n", encoding="utf-8")

    report = run_phase_2_audit(output_dir=tmp_path, cgroup_root=tmp_path)
    assert report.memory.is_cgroup_constrained is True
    assert report.memory.effective_memory_bytes == 536870912
    assert any("below recommended 4.0 GB" in w for w in report.warnings)
    assert report.status is PhaseStatus.DEGRADED

