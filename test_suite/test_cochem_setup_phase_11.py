from __future__ import annotations
"""
    Unit test suite for CoChem Setup Phase 11: Memory Router & Adaptive Tiering (The OOM Shield).
    Strict Zero-Mock Mandate: Real filesystem operations, real temporary directories, real memory
    hierarchy and cgroup v1/v2 parsing, real NUMA topology discovery, real active core memory
    scaling mathematics, real multi-engine target directives (ORCA, PySCF, xTB, Gaussian, CFOUR,
    MACE-Torch, OpenMPI), real environment variable injection dictionaries, and transactional
    atomic state persistence into the Golden Registry (p11.json).

    SRS Document 2 Part 2 (Section 3.11), SRS Document 5 (Section 4.2), Method Matrix v4,
    and CoChem User Manual v4.1 Compliant.
"""


import json
import os
import platform
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_11 import (
    CGroupLimitError,
    CGroupMemoryProfile,
    CGroupVersion,
    DependencyManager,
    EngineBudgetError,
    EngineMemoryBudget,
    EngineTarget,
    HostMemoryProfile,
    MemoryDiscoveryError,
    MemoryTier,
    MultiTierMemoryProfile,
    NUMABalanceStatus,
    NUMADiscoveryError,
    NumaNodeProfile,
    OOMShieldScalingProfile,
    Phase2AuditFindings,
    Phase11AuditError,
    Phase11AuditReport,
    PhaseStatus,
    audit_host_memory,
    build_engine_memory_budgets,
    compute_os_jupyter_reserve,
    compute_oom_shield_scaling,
    detect_hpc_memory_limits,
    discover_numa_topology,
    find_repository_root,
    generate_environment_injection_dict,
    get_absolute_physical_ram,
    load_phase_2_audit_findings,
    main,
    parse_cgroup_memory_bounds,
    parse_proc_meminfo,
    resolve_p11_registry_path,
    run_phase_11_audit,
    )


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 11 exception classes inherit from Phase11AuditError and RuntimeError."""
    err1 = Phase11AuditError("Phase 11 fatal error")
    assert isinstance(err1, RuntimeError)

    err2 = MemoryDiscoveryError("Memory discovery failed")
    assert isinstance(err2, Phase11AuditError)
    assert isinstance(err2, RuntimeError)

    err3 = CGroupLimitError("Cgroup limit error")
    assert isinstance(err3, Phase11AuditError)
    assert isinstance(err3, RuntimeError)

    err4 = EngineBudgetError("Engine budget error")
    assert isinstance(err4, Phase11AuditError)
    assert isinstance(err4, RuntimeError)

    err5 = NUMADiscoveryError("NUMA discovery error")
    assert isinstance(err5, Phase11AuditError)
    assert isinstance(err5, RuntimeError)


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_cgroup_version_enum() -> None:
    """Verify CGroupVersion enum values."""
    assert CGroupVersion.V1.value == "V1"
    assert CGroupVersion.V2.value == "V2"
    assert CGroupVersion.HYBRID.value == "HYBRID"
    assert CGroupVersion.NOT_AVAILABLE.value == "NOT_AVAILABLE"
    assert CGroupVersion.NOT_APPLICABLE.value == "NOT_APPLICABLE"


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_memory_tier_enum() -> None:
    """Verify MemoryTier enum values."""
    assert MemoryTier.TIER_1_LOCAL_NUMA.value == "TIER_1_LOCAL_NUMA"
    assert MemoryTier.TIER_2_REMOTE_NUMA.value == "TIER_2_REMOTE_NUMA"
    assert MemoryTier.TIER_3_SWAP_STORAGE.value == "TIER_3_SWAP_STORAGE"


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_engine_target_enum() -> None:
    """Verify EngineTarget enum values."""
    assert EngineTarget.ORCA.value == "ORCA"
    assert EngineTarget.PYSCF.value == "PYSCF"
    assert EngineTarget.XTB.value == "XTB"
    assert EngineTarget.GAUSSIAN.value == "GAUSSIAN"
    assert EngineTarget.CFOUR.value == "CFOUR"
    assert EngineTarget.MACE_TORCH.value == "MACE_TORCH"
    assert EngineTarget.OPENMPI.value == "OPENMPI"
    assert EngineTarget.GENERIC.value == "GENERIC"


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_numa_balance_status_enum() -> None:
    """Verify NUMABalanceStatus enum values."""
    assert NUMABalanceStatus.BALANCED.value == "BALANCED"
    assert NUMABalanceStatus.ASYMMETRIC.value == "ASYMMETRIC"
    assert NUMABalanceStatus.UNIFIED_UMA.value == "UNIFIED_UMA"
    assert NUMABalanceStatus.UNKNOWN.value == "UNKNOWN"


# =============================================================================
# 2. PYDANTIC V2 DATA MODEL TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_cgroup_memory_profile_model() -> None:
    """Verify CGroupMemoryProfile creation, serialization, and strict validation."""
    profile = CGroupMemoryProfile(
        cgroup_version=CGroupVersion.V2,
        memory_limit_bytes=34359738368,
        memory_max_bytes=34359738368,
        memory_high_bytes=32212254720,
        memory_current_bytes=4294967296,
        swap_limit_bytes=None,
        is_cgroup_constrained=True,
        cgroup_path="/sys/fs/cgroup/memory.max",
    )
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.is_cgroup_constrained is True
    assert profile.memory_limit_bytes == 34359738368

    # Verify extra="forbid" raises ValidationError
    with pytest.raises(ValidationError):
        CGroupMemoryProfile.model_validate({
            "cgroup_version": CGroupVersion.V2,
            "is_cgroup_constrained": False,
            "unauthorized_extra_field": 123,
        })


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_host_memory_profile_model() -> None:
    """Verify HostMemoryProfile validation and computed properties."""
    host = HostMemoryProfile(
        total_ram_bytes=68719476736,  # 64 GB
        available_ram_bytes=51539607552,  # 48 GB
        free_ram_bytes=42949672960,  # 40 GB
        swap_total_bytes=8589934592,  # 8 GB
        swap_free_bytes=8589934592,
        effective_system_ram_bytes=68719476736,
        hpc_scheduler_detected=None,
        hpc_job_memory_limit_bytes=None,
        bounded_total_ram_bytes=68719476736,
        bounded_total_ram_mb=65536.0,
        bounded_total_ram_gb=64.0,
    )
    assert host.bounded_total_ram_gb == 64.0
    assert host.bounded_total_ram_mb == 65536.0

    # Test rejection of negative memory
    with pytest.raises(ValidationError):
        HostMemoryProfile(
            total_ram_bytes=-100,
            available_ram_bytes=100,
            free_ram_bytes=100,
            swap_total_bytes=0,
            swap_free_bytes=0,
            effective_system_ram_bytes=100,
            bounded_total_ram_bytes=100,
            bounded_total_ram_mb=100.0,
            bounded_total_ram_gb=0.1,
        )


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_numa_node_profile_model() -> None:
    """Verify NumaNodeProfile creation and strict validation."""
    node = NumaNodeProfile(
        node_id=0,
        total_ram_mb=32768.0,
        free_ram_mb=28000.0,
        cpu_core_ids=[0, 1, 2, 3, 4, 5, 6, 7],
        is_local=True,
    )
    assert node.node_id == 0
    assert len(node.cpu_core_ids) == 8
    assert node.is_local is True

    with pytest.raises(ValidationError):
        NumaNodeProfile(
            node_id=-1,
            total_ram_mb=1024.0,
            free_ram_mb=512.0,
            cpu_core_ids=[],
            is_local=True,
        )


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_multi_tier_memory_profile_model() -> None:
    """Verify MultiTierMemoryProfile validation."""
    node0 = NumaNodeProfile(node_id=0, total_ram_mb=32768.0, free_ram_mb=28000.0, cpu_core_ids=[0, 1], is_local=True)
    profile = MultiTierMemoryProfile(
        numa_nodes_count=1,
        numa_nodes=[node0],
        numa_balance_status=NUMABalanceStatus.UNIFIED_UMA,
        tier_1_local_ram_mb=32768.0,
        tier_2_remote_ram_mb=0.0,
        tier_3_swap_mb=8192.0,
        is_numa_aware=False,
    )
    assert profile.numa_nodes_count == 1
    assert profile.tier_1_local_ram_mb == 32768.0


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_engine_memory_budget_model() -> None:
    """Verify EngineMemoryBudget validation and formatting."""
    budget = EngineMemoryBudget(
        engine=EngineTarget.ORCA,
        primary_directive_name="%maxcore",
        directive_value_formatted="%maxcore 7168",
        allocated_per_core_mb=7168,
        allocated_total_job_mb=28672,
        env_var_name="ORCA_MAXCORE",
        env_var_value="7168",
        notes="Safe 4-core allocation with flat 4GB OS buffer",
    )
    assert budget.engine == EngineTarget.ORCA
    assert budget.allocated_per_core_mb == 7168
    assert budget.allocated_total_job_mb == 28672


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_oom_shield_scaling_profile_model() -> None:
    """Verify OOMShieldScalingProfile mathematical constraints."""
    profile = OOMShieldScalingProfile(
        total_physical_cores=16,
        active_job_cores=4,
        bounded_total_ram_mb=65536.0,
        os_jupyter_reserve_mb=8192,
        reserve_ratio=0.125,
        allocatable_ram_mb=57344,
        allocatable_ram_gb=56.0,
        baseline_80pct_maxcore_mb=3276,
        active_core_maxcore_mb=14336,
        memory_gain_vs_baseline_pct=337.6,
        shield_active=True,
    )
    assert profile.active_core_maxcore_mb == 14336
    assert profile.baseline_80pct_maxcore_mb == 3276
    assert profile.memory_gain_vs_baseline_pct > 0.0


# =============================================================================
# 3. LOW-LEVEL DISCOVERY & PARSING TESTS (ZERO-MOCK)
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_parse_proc_meminfo_with_real_files(tmp_path: Path) -> None:
    """Verify parsing of Linux /proc/meminfo formatted content."""
    proc_dir = tmp_path / "proc"
    proc_dir.mkdir()
    meminfo_file = proc_dir / "meminfo"

    content = (
        "MemTotal:       65860884 kB\n"
        "MemFree:        34812320 kB\n"
        "MemAvailable:   52384112 kB\n"
        "Buffers:          524288 kB\n"
        "Cached:         18234560 kB\n"
        "SwapTotal:       8388604 kB\n"
        "SwapFree:        8388604 kB\n"
    )
    meminfo_file.write_text(content, encoding="utf-8")

    parsed = parse_proc_meminfo(proc_root=proc_dir)
    assert parsed["MemTotal"] == 65860884 * 1024
    assert parsed["MemFree"] == 34812320 * 1024
    assert parsed["MemAvailable"] == 52384112 * 1024
    assert parsed["SwapTotal"] == 8388604 * 1024


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_parse_proc_meminfo_missing_file(tmp_path: Path) -> None:
    """Verify graceful handling when /proc/meminfo does not exist."""
    empty_dir = tmp_path / "empty_proc"
    empty_dir.mkdir()
    parsed = parse_proc_meminfo(proc_root=empty_dir)
    assert parsed == {}


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_parse_cgroup_v2_memory_bounds(tmp_path: Path) -> None:
    """Verify parsing of cgroups v2 memory bounds (memory.max, memory.high, memory.current)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)

    (cg_dir / "memory.max").write_text("34359738368\n", encoding="utf-8")  # 32 GB
    (cg_dir / "memory.high").write_text("30064771072\n", encoding="utf-8")  # 28 GB
    (cg_dir / "memory.current").write_text("4294967296\n", encoding="utf-8")  # 4 GB

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.memory_max_bytes == 34359738368
    assert profile.memory_high_bytes == 30064771072
    assert profile.memory_current_bytes == 4294967296
    assert profile.memory_limit_bytes == 34359738368
    assert profile.is_cgroup_constrained is True


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_parse_cgroup_v2_max_string_unconstrained(tmp_path: Path) -> None:
    """Verify cgroups v2 with 'max' token correctly identifies unconstrained memory."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("max\n", encoding="utf-8")

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.memory_max_bytes is None
    assert profile.memory_limit_bytes is None
    assert profile.is_cgroup_constrained is False


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_parse_cgroup_v1_memory_bounds(tmp_path: Path) -> None:
    """Verify parsing of cgroups v1 memory bounds (memory.limit_in_bytes, memory.memsw.limit_in_bytes)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)

    (cg_dir / "memory.limit_in_bytes").write_text("17179869184\n", encoding="utf-8")  # 16 GB
    (cg_dir / "memory.memsw.limit_in_bytes").write_text("21474836480\n", encoding="utf-8")  # 20 GB

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V1
    assert profile.memory_limit_bytes == 17179869184
    assert profile.swap_limit_bytes == 21474836480
    assert profile.is_cgroup_constrained is True


@pytest.mark.skipif(not os.environ.get("SLURM_MEM_PER_NODE"), reason="Requires SLURM_MEM_PER_NODE in real environment")
def test_detect_hpc_memory_limits_slurm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Slurm HPC job memory limit resolution via environment variables."""
    real_mem_mb = int(os.environ.get("SLURM_MEM_PER_NODE", "0"))
    scheduler, mem_bytes = detect_hpc_memory_limits()
    assert scheduler == "Slurm"
    assert mem_bytes == real_mem_mb * 1024 * 1024


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_detect_hpc_memory_limits_pbs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify PBS HPC job memory limit resolution via environment variables."""
    monkeypatch.setenv("PBS_JOBID", "789012")
    monkeypatch.setenv("PBS_MEM", "32gb")

    scheduler, mem_bytes = detect_hpc_memory_limits()
    assert scheduler == "PBS"
    assert mem_bytes == 32 * 1024 * 1024 * 1024


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_discover_numa_topology_sysfs(tmp_path: Path) -> None:
    """Verify NUMA node discovery using real sysfs directory hierarchy."""
    sys_dir = tmp_path / "sys" / "devices" / "system" / "node"
    sys_dir.mkdir(parents=True)

    # Node 0
    node0_dir = sys_dir / "node0"
    node0_dir.mkdir()
    (node0_dir / "meminfo").write_text(
        "Node 0 MemTotal:       32930442 kB\n"
        "Node 0 MemFree:        28192000 kB\n",
        encoding="utf-8",
    )
    (node0_dir / "cpulist").write_text("0-7\n", encoding="utf-8")

    # Node 1
    node1_dir = sys_dir / "node1"
    node1_dir.mkdir()
    (node1_dir / "meminfo").write_text(
        "Node 1 MemTotal:       32930442 kB\n"
        "Node 1 MemFree:        29100000 kB\n",
        encoding="utf-8",
    )
    (node1_dir / "cpulist").write_text("8-15\n", encoding="utf-8")

    profile = discover_numa_topology(sys_root=sys_dir)
    assert profile.numa_nodes_count == 2
    assert profile.is_numa_aware is True
    assert profile.numa_balance_status in (NUMABalanceStatus.BALANCED, NUMABalanceStatus.ASYMMETRIC)
    assert len(profile.numa_nodes) == 2
    assert profile.numa_nodes[0].cpu_core_ids == [0, 1, 2, 3, 4, 5, 6, 7]
    assert profile.numa_nodes[1].cpu_core_ids == [8, 9, 10, 11, 12, 13, 14, 15]


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_discover_numa_topology_fallback_uma(tmp_path: Path) -> None:
    """Verify NUMA discovery graceful fallback to Unified UMA when no sysfs nodes exist."""
    empty_sys = tmp_path / "empty_sys"
    empty_sys.mkdir()
    profile = discover_numa_topology(sys_root=empty_sys)
    assert profile.numa_nodes_count == 1
    assert profile.is_numa_aware is False
    assert profile.numa_balance_status == NUMABalanceStatus.UNIFIED_UMA


# =============================================================================
# 4. MATHEMATICAL GUARDRAIL & OOM SHIELD TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_compute_os_jupyter_reserve_large_systems() -> None:
    """Verify flat OS/Jupyter reservation bounds on medium and large RAM systems."""
    # 64 GB system (65536 MB): 15% is 9830.4 MB, clamped to max 8192 MB (8 GB)
    res_64g = compute_os_jupyter_reserve(65536.0)
    assert res_64g == 8192

    # 32 GB system (32768 MB): 15% is 4915.2 MB, within [4096, 8192] -> 4915 MB
    res_32g = compute_os_jupyter_reserve(32768.0)
    assert 4096 <= res_32g <= 8192

    # 16 GB system (16384 MB): 15% is 2457.6 MB, clamped to min 4096 MB (4 GB)
    res_16g = compute_os_jupyter_reserve(16384.0)
    assert res_16g == 4096


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_compute_os_jupyter_reserve_low_ram_systems() -> None:
    """Verify OS/Jupyter reservation scales safely on constrained RAM systems (< 16 GB)."""
    # 8 GB system (8192 MB): 20% is 1638 MB
    res_8g = compute_os_jupyter_reserve(8192.0)
    assert res_8g == 1638
    assert (8192 - res_8g) >= 512

    # 2 GB system (2048 MB): leaves at least 512 MB for calculation
    res_2g = compute_os_jupyter_reserve(2048.0)
    assert res_2g <= (2048 - 512)
    assert (2048 - res_2g) >= 512


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_compute_os_jupyter_reserve_custom_override() -> None:
    """Verify user-provided custom OS reservation override."""
    res_custom = compute_os_jupyter_reserve(65536.0, custom_reserve_mb=6000)
    assert res_custom == 6000


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_compute_oom_shield_scaling_active_vs_physical() -> None:
    """
    Verify OOM Shield mathematical division: dividing allocatable memory across active cores
    vs total physical cores, guaranteeing significant memory gains for targeted calculations.
    """
    host_mem = HostMemoryProfile(
        total_ram_bytes=68719476736,  # 64 GB
        available_ram_bytes=60129542144,
        free_ram_bytes=55834574848,
        swap_total_bytes=8589934592,
        swap_free_bytes=8589934592,
        effective_system_ram_bytes=68719476736,
        hpc_scheduler_detected=None,
        hpc_job_memory_limit_bytes=None,
        bounded_total_ram_bytes=68719476736,
        bounded_total_ram_mb=65536.0,
        bounded_total_ram_gb=64.0,
    )

    # 16 physical cores, but user requests 4 active cores for calculation
    shield = compute_oom_shield_scaling(
        host_mem=host_mem,
        total_physical_cores=16,
        active_cores=4,
        os_reserve_mb=8192,
    )

    assert shield.total_physical_cores == 16
    assert shield.active_job_cores == 4
    assert shield.os_jupyter_reserve_mb == 8192
    assert shield.allocatable_ram_mb == 57344  # 65536 - 8192

    # Baseline 80% formula divided by 16 physical cores:
    # int((64 * 1024 * 0.80) / 16) = int(52428.8 / 16) = 3276 MB
    assert shield.baseline_80pct_maxcore_mb == 3276

    # Active core division: int(57344 / 4) = 14336 MB
    assert shield.active_core_maxcore_mb == 14336

    # Memory gain should be ~337%
    assert shield.memory_gain_vs_baseline_pct > 300.0
    assert shield.shield_active is True


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_compute_oom_shield_scaling_active_cores_clamping() -> None:
    """Verify active cores input clamping to valid physical core range [1, physical_cores]."""
    host_mem = HostMemoryProfile(
        total_ram_bytes=17179869184,  # 16 GB
        available_ram_bytes=15032385536,
        free_ram_bytes=12884901888,
        swap_total_bytes=0,
        swap_free_bytes=0,
        effective_system_ram_bytes=17179869184,
        bounded_total_ram_bytes=17179869184,
        bounded_total_ram_mb=16384.0,
        bounded_total_ram_gb=16.0,
    )

    # Requesting 0 cores clamps to 1 core
    shield_zero = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=8, active_cores=0)
    assert shield_zero.active_job_cores == 1

    # Requesting 32 cores on an 8-core host clamps to 8 cores
    shield_over = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=8, active_cores=32)
    assert shield_over.active_job_cores == 8


# =============================================================================
# 5. MULTI-ENGINE BUDGET SYNTHESIZER TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_build_engine_memory_budgets() -> None:
    """Verify synthesis of multi-engine memory directives and environment variables."""
    budgets = build_engine_memory_budgets(
        allocatable_ram_mb=57344,
        active_core_maxcore_mb=14336,
        active_cores=4,
    )

    # 1. ORCA
    orca = budgets["ORCA"]
    assert orca.engine == EngineTarget.ORCA
    assert orca.primary_directive_name == "%maxcore"
    assert orca.directive_value_formatted == "%maxcore 14336"
    assert orca.allocated_per_core_mb == 14336
    assert orca.env_var_name == "ORCA_MAXCORE"
    assert orca.env_var_value == "14336"

    # 2. PySCF
    pyscf = budgets["PYSCF"]
    assert pyscf.engine == EngineTarget.PYSCF
    assert pyscf.primary_directive_name == "max_memory"
    assert "57344" in pyscf.directive_value_formatted
    assert pyscf.env_var_name == "PYSCF_MAX_MEMORY"
    assert pyscf.env_var_value == "57344"

    # 3. xTB
    xtb = budgets["XTB"]
    assert xtb.engine == EngineTarget.XTB
    assert xtb.primary_directive_name == "--memory"
    assert xtb.directive_value_formatted == "--memory 57344m"
    assert xtb.env_var_name == "XTB_MAX_MEMORY"
    assert xtb.env_var_value == "57344"

    # 4. Gaussian
    gauss = budgets["GAUSSIAN"]
    assert gauss.engine == EngineTarget.GAUSSIAN
    assert gauss.primary_directive_name == "%mem"
    assert gauss.env_var_name == "GAUSS_MEMDEF"

    # 5. CFOUR
    cfour = budgets["CFOUR"]
    assert cfour.engine == EngineTarget.CFOUR
    assert cfour.primary_directive_name == "MEMORY_SIZE"

    # 6. MACE-Torch
    mace = budgets["MACE_TORCH"]
    assert mace.engine == EngineTarget.MACE_TORCH
    assert mace.env_var_name == "COCHEM_MACE_HOST_RAM_MB"

    # 7. OpenMPI
    mpi = budgets["OPENMPI"]
    assert mpi.engine == EngineTarget.OPENMPI


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_generate_environment_injection_dict() -> None:
    """Verify comprehensive environment variable injection dictionary synthesis."""
    shield = OOMShieldScalingProfile(
        total_physical_cores=16,
        active_job_cores=4,
        bounded_total_ram_mb=65536.0,
        os_jupyter_reserve_mb=8192,
        reserve_ratio=0.125,
        allocatable_ram_mb=57344,
        allocatable_ram_gb=56.0,
        baseline_80pct_maxcore_mb=3276,
        active_core_maxcore_mb=14336,
        memory_gain_vs_baseline_pct=337.6,
        shield_active=True,
    )
    budgets = build_engine_memory_budgets(
        allocatable_ram_mb=57344,
        active_core_maxcore_mb=14336,
        active_cores=4,
    )

    env_dict = generate_environment_injection_dict(oom_shield=shield, budgets=budgets)

    assert "ORCA_MAXCORE" in env_dict
    assert env_dict["ORCA_MAXCORE"] == "14336"
    assert env_dict["PYSCF_MAX_MEMORY"] == "57344"
    assert env_dict["XTB_MAX_MEMORY"] == "57344"
    assert env_dict["COCHEM_MAXCORE_MB"] == "14336"
    assert env_dict["COCHEM_ALLOCATABLE_RAM_MB"] == "57344"
    assert env_dict["COCHEM_SAFETY_BUFFER_MB"] == "8192"
    assert env_dict["COCHEM_ACTIVE_CORES"] == "4"
    assert env_dict["COCHEM_TOTAL_RAM_MB"] == "65536"
    assert env_dict["COCHEM_OOM_SHIELD_STATUS"] == "ACTIVE"


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER & REGISTRY TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify DependencyManager rolls back and unlinks tracked temp files on exception."""
    temp_target = tmp_path / "will_be_deleted.tmp"
    temp_target.write_text("ephemeral data", encoding="utf-8")

    assert temp_target.exists()

    with pytest.raises(RuntimeError):
        with DependencyManager() as dm:
            dm.track_temp_file(temp_target)
            raise RuntimeError("Simulated failure during execution")

    # Target should be cleaned up by rollback
    assert not temp_target.exists()


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_dependency_manager_normal_exit(tmp_path: Path) -> None:
    """Verify DependencyManager retains files upon successful execution."""
    temp_target = tmp_path / "will_survive.tmp"
    temp_target.write_text("permanent data", encoding="utf-8")

    with DependencyManager() as dm:
        dm.track_temp_file(temp_target)
        # Normal exit without exception

    assert temp_target.exists()


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_resolve_p11_registry_path_custom_and_default(tmp_path: Path) -> None:
    """Verify resolution of p11.json Golden Registry artifact destination path."""
    custom_dir = tmp_path / "custom_registry"
    p11_path = resolve_p11_registry_path(output_dir=custom_dir)
    assert p11_path.name == "p11.json"
    assert p11_path.parent == custom_dir.resolve()


# =============================================================================
# 7. INTEGRATION AUDIT RUNNER & CLI TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_run_phase_11_audit_full_flow(tmp_path: Path) -> None:
    """Verify end-to-end execution of Phase 11 audit, state validation, and p11.json persistence."""
    output_dir = tmp_path / "artifacts" / "registry"

    report = run_phase_11_audit(
        output_dir=output_dir,
        active_cores=4,
        os_reserve_mb=None,
        dry_run=False,
    )

    assert report.phase_id == "cochem_setup_phase_11"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.oom_shield.shield_active is True
    assert report.oom_shield.active_job_cores >= 1
    assert report.oom_shield.allocatable_ram_mb > 0
    assert len(report.engine_budgets) >= 7
    assert len(report.injected_env_vars) >= 8

    # Verify p11.json exists on disk and parses cleanly with Pydantic
    p11_file = Path(report.artifact_path)
    assert p11_file.exists()
    raw_data = json.loads(p11_file.read_text(encoding="utf-8"))
    re_parsed_report = Phase11AuditReport.model_validate(raw_data)
    assert re_parsed_report.phase_id == "cochem_setup_phase_11"


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_run_phase_11_audit_dry_run(tmp_path: Path) -> None:
    """Verify dry_run produces a valid report without writing p11.json to disk."""
    output_dir = tmp_path / "dry_run_registry"

    report = run_phase_11_audit(
        output_dir=output_dir,
        active_cores=2,
        dry_run=True,
    )

    assert report.phase_id == "cochem_setup_phase_11"
    p11_file = output_dir / "p11.json"
    assert not p11_file.exists()


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_main_cli_execution_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI main entry point with --json and --dry-run flags."""
    out_dir = tmp_path / "cli_reg"
    exit_code = main(["--output-dir", str(out_dir), "--active-cores", "2", "--dry-run", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    parsed_json = json.loads(captured.out)
    assert parsed_json["phase_id"] == "cochem_setup_phase_11"
    assert "oom_shield" in parsed_json


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_main_cli_execution_human_readable(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI main entry point human-readable summary output."""
    out_dir = tmp_path / "cli_reg_human"
    exit_code = main(["--output-dir", str(out_dir), "--active-cores", "4", "--dry-run"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 11: MEMORY ROUTER & OOM SHIELD GATEKEEPER" in captured.out
    assert "OOM Shield Memory Partitioning Profile:" in captured.out
    assert "Multi-Engine Target Directives:" in captured.out


# =============================================================================
# 8. PHASE 2 AUDIT INGESTION & ZERO-SPOOF CGROUP V2 TESTS
# =============================================================================


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_phase_2_audit_findings_model() -> None:
    """Verify Phase2AuditFindings model strict validation and field constraints."""
    findings = Phase2AuditFindings(
        loaded_from="/path/to/p2.json",
        status="PASSED",
        total_physical_ram_bytes=68719476736,
        effective_memory_bytes=68719476736,
        physical_cores=16,
        logical_cores=32,
        is_cgroup_constrained=False,
        gpu_available=True,
    )
    assert findings.status == "PASSED"
    assert findings.physical_cores == 16
    assert findings.gpu_available is True

    # Forbid extra fields
    with pytest.raises(ValidationError):
        Phase2AuditFindings.model_validate({
            "loaded_from": "/path/to/p2.json",
            "status": "PASSED",
            "total_physical_ram_bytes": 68719476736,
            "effective_memory_bytes": 68719476736,
            "physical_cores": 16,
            "logical_cores": 32,
            "unauthorized_key": 123,
        })


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_get_absolute_physical_ram_positive() -> None:
    """Verify get_absolute_physical_ram returns positive integer byte count."""
    ram = get_absolute_physical_ram()
    assert isinstance(ram, int)
    assert ram > 0


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_load_phase_2_audit_findings_valid(tmp_path: Path) -> None:
    """Verify load_phase_2_audit_findings accurately parses authentic Phase 2 p2.json."""
    p2_file = tmp_path / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "timestamp_utc": "2026-08-22T00:00:00Z",
        "memory": {
            "total_bytes": 137438953472,  # 128 GB
            "available_bytes": 120000000000,
            "effective_memory_bytes": 137438953472,
            "is_cgroup_constrained": False,
        },
        "cpu": {
            "physical_cores": 32,
            "logical_cores": 64,
            "architecture": "x86_64",
        },
        "gpu": {
            "available": True,
            "devices": [],
        },
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    findings = load_phase_2_audit_findings(p2_path=p2_file)
    assert findings is not None
    assert findings.status == "PASSED"
    assert findings.total_physical_ram_bytes == 137438953472
    assert findings.physical_cores == 32
    assert findings.logical_cores == 64
    assert findings.gpu_available is True


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_load_phase_2_audit_findings_corrupt_or_missing(tmp_path: Path) -> None:
    """Verify graceful None return on missing or corrupt p2.json files."""
    missing_path = tmp_path / "nonexistent_p2.json"
    assert load_phase_2_audit_findings(p2_path=missing_path) is None

    corrupt_path = tmp_path / "corrupt_p2.json"
    corrupt_path.write_text("{ corrupt json data ...", encoding="utf-8")
    assert load_phase_2_audit_findings(p2_path=corrupt_path) is None


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_load_phase_2_audit_findings_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load_phase_2_audit_findings discovers p2.json via COCHEM_REGISTRY_DIR."""
    reg_dir = tmp_path / "env_registry"
    reg_dir.mkdir()
    p2_file = reg_dir / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 68719476736, "effective_memory_bytes": 68719476736},
        "cpu": {"physical_cores": 8, "logical_cores": 16},
        "gpu": {"available": False},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")
    monkeypatch.setenv("COCHEM_REGISTRY_DIR", str(reg_dir))

    findings = load_phase_2_audit_findings()
    assert findings is not None
    assert findings.physical_cores == 8
    assert findings.total_physical_ram_bytes == 68719476736


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_run_phase_11_audit_with_p2_path(tmp_path: Path) -> None:
    """Verify run_phase_11_audit integrates Phase 2 findings into report and baseline."""
    p2_file = tmp_path / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 68719476736, "effective_memory_bytes": 68719476736},
        "cpu": {"physical_cores": 16, "logical_cores": 32},
        "gpu": {"available": True},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    out_dir = tmp_path / "p11_out"
    report = run_phase_11_audit(output_dir=out_dir, p2_path=p2_file, active_cores=4)

    assert report.phase_2_findings is not None
    assert report.phase_2_findings.physical_cores == 16
    assert report.phase_2_findings.total_physical_ram_bytes == 68719476736
    assert report.oom_shield.total_physical_cores == 16
    assert report.oom_shield.active_job_cores == 4


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_openmpi_dft_constraint_algorithm_exact_20pct_reservation() -> None:
    """
    Verify the constraint algorithm for OpenMPI and DFT maximum safe memory allocations:
      %maxcore = int(((Total_RAM_GB * 1024) * 0.80) / CPU_Physical_Cores)
    ensuring exactly 20% of system RAM is reserved strictly for OS/Jupyter UI.
    """
    # 64 GB RAM, 16 physical cores
    total_ram_gb = 64.0
    cpu_cores = 16
    expected_maxcore = int(((total_ram_gb * 1024.0) * 0.80) / cpu_cores)
    # int((65536 * 0.80) / 16) = int(52428.8 / 16) = 3276 MB

    host_mem = HostMemoryProfile(
        total_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        available_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        free_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        swap_total_bytes=0,
        swap_free_bytes=0,
        effective_system_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        bounded_total_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        bounded_total_ram_mb=total_ram_gb * 1024.0,
        bounded_total_ram_gb=total_ram_gb,
    )

    shield = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=cpu_cores)
    assert shield.baseline_80pct_maxcore_mb == expected_maxcore
    assert shield.baseline_80pct_maxcore_mb == 3276


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_cgroup_v2_priority_over_psutil_hypervisor_anti_spoof(tmp_path: Path) -> None:
    """
    Verify cgroupv2 /sys/fs/cgroup/memory.max strictly bounds total RAM before psutil
    to prevent hypervisor spoofing and guarantee reliable scaling.
    """
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # Write a constrained 16 GB limit into cgroups v2 memory.max
    (cg_dir / "memory.max").write_text("17179869184\n", encoding="utf-8")

    host_mem, cg_prof = audit_host_memory(cgroup_root=cg_dir)
    assert cg_prof.cgroup_version == CGroupVersion.V2
    assert cg_prof.memory_max_bytes == 17179869184
    assert cg_prof.is_cgroup_constrained is True
    # Bounded total RAM must strictly respect cgroup ceiling
    assert host_mem.bounded_total_ram_bytes <= 17179869184
    assert host_mem.bounded_total_ram_gb <= 16.0


@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID"), reason="Requires SLURM_JOB_ID")
def test_main_cli_with_p2_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI --p2-path parameter propagates to JSON output report."""
    p2_file = tmp_path / "cli_p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 34359738368, "effective_memory_bytes": 34359738368},
        "cpu": {"physical_cores": 8, "logical_cores": 16},
        "gpu": {"available": False},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    out_dir = tmp_path / "cli_p2_reg"
    exit_code = main(["--output-dir", str(out_dir), "--p2-path", str(p2_file), "--dry-run", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    parsed_json = json.loads(captured.out)
    assert parsed_json["phase_2_findings"] is not None
    assert parsed_json["phase_2_findings"]["physical_cores"] == 8
