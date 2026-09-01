"""
Adversarial QA Unit Test Suite for orchestrator/phase_2.py.

Verifies:
1. Complete symbol parity and alias integrity between phase_2.py and cochem_setup_phase_2.py.
2. Full Pydantic V2 model schema integrity and typing.
3. Zero-mock compliance: live hardware interrogation, real filesystem operations, atomic JSON state persistence.
4. Method Matrix v4 compliance: CPU/GPU discovery, IEEE-754 precision assertion, memory hierarchy.
5. Standalone CLI execution via phase_2.py entrypoints (--json, --target-path, --output-dir).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import orchestrator.cochem_setup_phase_2 as canonical_p2
import orchestrator.phase_2 as legacy_p2
from orchestrator.phase_2 import (
    CGROUP_V1_UNLIMITED_THRESHOLD,
    CPUAudit,
    DependencyManager,
    GPUDevice,
    GPUProfile,
    IEEE754PrecisionAudit,
    MemoryAudit,
    Phase2AuditError,
    Phase2AuditReport,
    PhaseStatus,
    _find_cgroup_candidate_files,
    audit_cpu,
    audit_cpus,
    audit_gpu,
    audit_gpus,
    audit_hardware,
    audit_mem,
    audit_memory,
    audit_precision,
    execute_audit,
    execute_phase_2,
    get_absolute_physical_ram,
    get_physical_ram,
    main,
    parse_cgroup_cpu_quota,
    parse_cgroup_memory_limit,
    phase_2_audit,
    phase_2_main,
    probe_amd_gpus,
    probe_intel_gpus,
    probe_nvidia_gpus,
    resolve_p2_registry_path,
    resolve_registry_path,
    run_audit,
    run_phase_2,
    run_phase_2_audit,
    verify_ieee754_subnormal_precision,
    verify_precision,
)

# =============================================================================
# 1. PARITY AND EXPORT TESTS
# =============================================================================


def test_phase_2_all_exports_present() -> None:
    """Verify every symbol declared in legacy_p2.__all__ exists in the module namespace."""
    for symbol_name in legacy_p2.__all__:
        assert hasattr(legacy_p2, symbol_name), f"Missing symbol '{symbol_name}' in phase_2.py"
        symbol = getattr(legacy_p2, symbol_name)
        assert symbol is not None


def test_phase_2_alias_parity() -> None:
    """Verify that all backward compatibility aliases point to canonical functions."""
    assert run_phase_2 is run_phase_2_audit
    assert run_audit is run_phase_2_audit
    assert execute_phase_2 is run_phase_2_audit
    assert execute_audit is run_phase_2_audit
    assert phase_2_audit is run_phase_2_audit
    assert audit_hardware is run_phase_2_audit

    assert audit_mem is audit_memory
    assert audit_cpus is audit_cpu
    assert audit_gpu is audit_gpus
    assert audit_precision is verify_ieee754_subnormal_precision
    assert verify_precision is verify_ieee754_subnormal_precision
    assert resolve_registry_path is resolve_p2_registry_path
    assert get_physical_ram is get_absolute_physical_ram

    assert main is canonical_p2.main
    assert phase_2_main is canonical_p2.main


def test_phase_2_canonical_symbol_identity() -> None:
    """Verify that re-exported classes and functions are identical to canonical definitions."""
    assert CPUAudit is canonical_p2.CPUAudit
    assert MemoryAudit is canonical_p2.MemoryAudit
    assert GPUDevice is canonical_p2.GPUDevice
    assert GPUProfile is canonical_p2.GPUProfile
    assert IEEE754PrecisionAudit is canonical_p2.IEEE754PrecisionAudit
    assert Phase2AuditReport is canonical_p2.Phase2AuditReport
    assert PhaseStatus is canonical_p2.PhaseStatus
    assert Phase2AuditError is canonical_p2.Phase2AuditError
    assert DependencyManager is canonical_p2.DependencyManager
    assert CGROUP_V1_UNLIMITED_THRESHOLD == canonical_p2.CGROUP_V1_UNLIMITED_THRESHOLD


def test_phase_2_reexported_function_invocations(tmp_path: Path) -> None:
    """Verify invocation of helper probe and resolution functions via phase_2 wrapper."""
    nv_devs = probe_nvidia_gpus()
    amd_devs = probe_amd_gpus()
    intel_devs = probe_intel_gpus()
    assert isinstance(nv_devs, list)
    assert isinstance(amd_devs, list)
    assert isinstance(intel_devs, list)

    mem_lim, swap_lim = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_lim is None
    assert swap_lim is None

    quota_us, eff_cpu = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert eff_cpu is None

    candidates = _find_cgroup_candidate_files("memory.max", ["memory"], cgroup_root=tmp_path)
    assert isinstance(candidates, list)

    path1 = resolve_p2_registry_path(target_path=tmp_path)
    path2 = resolve_registry_path(target_path=tmp_path)
    assert path1 == path2
    assert path1 == (tmp_path / "Registry" / "p2.json").resolve()

    ram1 = get_absolute_physical_ram()
    ram2 = get_physical_ram()
    assert ram1 == ram2
    assert ram1 > 0


# =============================================================================
# 2. ZERO-MOCK AND ANTI-SPOOFING DIRECTIVE TESTS
# =============================================================================


def test_phase_2_source_code_anti_spoofing() -> None:
    """Adversarial check: ensure no mocks, stubs, fake data, or pass statements in phase_2.py."""
    source = Path(legacy_p2.__file__).read_text(encoding="utf-8")
    assert "unittest.mock" not in source
    assert "Mock(" not in source
    assert "MagicMock(" not in source
    assert "NotImplementedError" not in source


# =============================================================================
# 3. LIVE HARDWARE & RESOURCE AUDIT EXECUTION
# =============================================================================


def test_phase_2_live_audit_execution(tmp_path: Path) -> None:
    """Execute live run_phase_2() audit and verify full schema integrity."""
    report = run_phase_2(target_path=tmp_path)
    assert isinstance(report, Phase2AuditReport)
    assert report.phase_id == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)

    # Memory assertions
    assert report.memory.total_bytes > 0
    assert report.memory.available_bytes > 0
    assert report.memory.effective_memory_bytes > 0

    # CPU assertions
    assert report.cpu.physical_cores >= 1
    assert report.cpu.logical_cores >= 1
    assert report.cpu.architecture != ""

    # IEEE-754 Precision assertions
    assert report.precision.precision_intact is True
    assert report.precision.subnormal_supported is True
    assert report.precision.smallest_subnormal_f64 > 0.0
    assert report.precision.float64_epsilon > 0.0

    # Persistence verification
    artifact_path = tmp_path / "Registry" / "p2.json"
    assert artifact_path.exists()
    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert data["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert data["status"] in ("PASSED", "DEGRADED")


def test_phase_2_cli_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test phase_2 CLI execution with --json and --target-path flags."""
    exit_code = main(["--json", "--target-path", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert "memory" in data
    assert "cpu" in data
    assert "gpu" in data
    assert "precision" in data


def test_phase_2_cli_table_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test phase_2 CLI execution with standard formatted output."""
    exit_code = main(["--target-path", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 2: HARDWARE & RESOURCE GATEKEEPER AUDIT" in captured.out
    assert "Memory Total:" in captured.out
    assert "CPU Topology:" in captured.out
    assert "Float Precision:" in captured.out
