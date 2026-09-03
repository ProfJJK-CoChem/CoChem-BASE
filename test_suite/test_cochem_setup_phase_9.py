"""
Unit test suite for CoChem Setup Phase 9: Heterogeneous Parsl Concurrency Executor Mapping & Scout-and-Anchor Gatekeeper.
Strict Zero-Mock Mandate: Real CPU topology interrogation, real core-affinity pinning partitioning,
real .anti_spoof_amnesty.json validation and AST scanning, real Parsl HTEX configuration construction,
real temporary directory persistence, real environment variable injection dictionaries,
and transactional atomic state persistence into the Golden Registry (p9.json).

SRS Document 2 Part 2 (Section 3.9), Method Matrix v4 (§8A), SRS Document 1 (Section 2),
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_9 import (
    AffinityPinningError,
    AffinityStrategy,
    AmnestyAuditProfile,
    AmnestyVerificationError,
    CoreAffinityMapping,
    DependencyManager,
    ExecutorStreamType,
    HTEXExecutorConfig,
    ParslConfigGenerationError,
    ParslExecutorMappingError,
    ParslProviderType,
    Phase9AuditError,
    Phase9AuditReport,
    PhaseStatus,
    ScoutAndAnchorProfile,
    audit_anti_spoof_amnesty,
    build_htex_executor_config,
    compute_core_affinity_distribution,
    construct_parsl_config_object,
    detect_system_cpu_topology,
    find_repository_root,
    generate_environment_injection_dict,
    main,
    resolve_p9_registry_path,
    resolve_parsl_provider,
    run_phase_9_audit,
)


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    try:
        return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    except TypeError:
        return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 9 exception classes inherit from Phase9AuditError and RuntimeError."""
    err1 = Phase9AuditError("Phase 9 fatal error")
    assert isinstance(err1, RuntimeError)

    err2 = ParslExecutorMappingError("Parsl executor mapping error")
    assert isinstance(err2, Phase9AuditError)
    assert isinstance(err2, RuntimeError)

    err3 = AmnestyVerificationError("Amnesty verification error")
    assert isinstance(err3, Phase9AuditError)
    assert isinstance(err3, RuntimeError)

    err4 = AffinityPinningError("Core affinity pinning error")
    assert isinstance(err4, Phase9AuditError)
    assert isinstance(err4, RuntimeError)

    err5 = ParslConfigGenerationError("Parsl config generation error")
    assert isinstance(err5, ParslExecutorMappingError)
    assert isinstance(err5, Phase9AuditError)
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


def test_parsl_provider_type_enum() -> None:
    """Verify ParslProviderType enum values."""
    assert ParslProviderType.LOCAL.value == "LOCAL"
    assert ParslProviderType.SLURM.value == "SLURM"
    assert ParslProviderType.PBS.value == "PBS"
    assert ParslProviderType.LSF.value == "LSF"
    assert ParslProviderType.SGE.value == "SGE"
    assert ParslProviderType.LOCAL_STANDALONE.value == "LOCAL_STANDALONE"

    with pytest.raises(ValueError):
        ParslProviderType("UNKNOWN_PROVIDER")


def test_executor_stream_type_enum() -> None:
    """Verify ExecutorStreamType enum values."""
    assert ExecutorStreamType.CPU_ANCHOR.value == "CPU_ANCHOR"
    assert ExecutorStreamType.GPU_SCOUT.value == "GPU_SCOUT"

    with pytest.raises(ValueError):
        ExecutorStreamType("UNKNOWN_STREAM")


def test_affinity_strategy_enum() -> None:
    """Verify AffinityStrategy enum values."""
    assert AffinityStrategy.PINNED_EXPLICIT.value == "PINNED_EXPLICIT"
    assert AffinityStrategy.BLOCK.value == "BLOCK"
    assert AffinityStrategy.ROUND_ROBIN.value == "ROUND_ROBIN"
    assert AffinityStrategy.SHARED_DEGRADED.value == "SHARED_DEGRADED"
    assert AffinityStrategy.NONE.value == "NONE"


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_core_affinity_mapping_validation() -> None:
    """Test CoreAffinityMapping model validation, constraints, and extra field rejection."""
    mapping = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=[0, 1, 2, 3, 4, 5, 6],
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    assert mapping.stream == ExecutorStreamType.CPU_ANCHOR
    assert mapping.core_count == 7
    assert mapping.core_ids == [0, 1, 2, 3, 4, 5, 6]
    assert mapping.affinity_string == "list:0,1,2,3,4,5,6"

    # Core count must be >= 1
    with pytest.raises(ValidationError):
        CoreAffinityMapping(
            stream=ExecutorStreamType.CPU_ANCHOR,
            core_count=0,
            core_ids=[],
            affinity_string="none",
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        CoreAffinityMapping(
            stream=ExecutorStreamType.CPU_ANCHOR,
            core_count=7,
            core_ids=[0, 1, 2, 3, 4, 5, 6],
            affinity_string="list:0,1,2,3,4,5,6",
            forbidden_key="bad",  # type: ignore[call-arg]
        )


def test_htex_executor_config_validation() -> None:
    """Test HTEXExecutorConfig model validation, constraints, and extra field rejection."""
    config = HTEXExecutorConfig(
        label="cochem_anchor_cpu",
        stream=ExecutorStreamType.CPU_ANCHOR,
        provider=ParslProviderType.LOCAL,
        max_workers_per_node=7,
        cores_per_worker=1.0,
        mem_per_worker_gb=3.4,
        cpu_affinity="list:0,1,2,3,4,5,6",
        worker_port_range=(50000, 55000),
        interchange_port_range=(55001, 60000),
        init_blocks=1,
        min_blocks=0,
        max_blocks=1,
        nodes_per_block=1,
        walltime="01:00:00",
        launcher="SimpleLauncher",
    )
    assert config.label == "cochem_anchor_cpu"
    assert config.max_workers_per_node == 7
    assert config.mem_per_worker_gb == 3.4

    # Invalid max_workers_per_node < 1
    with pytest.raises(ValidationError):
        HTEXExecutorConfig(
            label="bad_exec",
            stream=ExecutorStreamType.CPU_ANCHOR,
            max_workers_per_node=0,
            cpu_affinity="block",
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HTEXExecutorConfig(
            label="bad_exec",
            stream=ExecutorStreamType.CPU_ANCHOR,
            max_workers_per_node=1,
            cpu_affinity="block",
            unauthorized_key="bad",  # type: ignore[call-arg]
        )


def test_amnesty_audit_profile_validation() -> None:
    """Test AmnestyAuditProfile model validation."""
    profile = AmnestyAuditProfile(
        amnesty_file_path="/repo/.anti_spoof_amnesty.json",
        is_amnesty_present=True,
        total_amnestied_entries=18,
        is_utf8_lf_compliant=True,
        is_alphabetically_sorted=True,
        has_zero_duplicates=True,
        parsl_whitelisted=True,
        scanned_concurrency_modules=["parsl", "multiprocessing"],
    )
    assert profile.is_amnesty_present is True
    assert profile.total_amnestied_entries == 18
    assert profile.parsl_whitelisted is True


def test_scout_and_anchor_profile_and_roundtrip() -> None:
    """Test ScoutAndAnchorProfile and Phase9AuditReport full roundtrip serialization."""
    anchor_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=list(range(7)),
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    scout_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.GPU_SCOUT,
        core_count=1,
        core_ids=[7],
        affinity_string="list:7",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    anchor_exec = HTEXExecutorConfig(
        label="cochem_anchor_cpu",
        stream=ExecutorStreamType.CPU_ANCHOR,
        provider=ParslProviderType.LOCAL,
        max_workers_per_node=7,
        cores_per_worker=1.0,
        cpu_affinity=anchor_aff.affinity_string,
    )
    scout_exec = HTEXExecutorConfig(
        label="cochem_scout_gpu",
        stream=ExecutorStreamType.GPU_SCOUT,
        provider=ParslProviderType.LOCAL,
        max_workers_per_node=3,
        cores_per_worker=0.33,
        cpu_affinity=scout_aff.affinity_string,
    )
    scout_anchor = ScoutAndAnchorProfile(
        total_physical_cores=8,
        total_logical_cores=16,
        anchor_cores=7,
        scout_cores=1,
        scout_gpu_workers=3,
        scout_step_latency_ms=18.1,
        anchor_executor=anchor_exec,
        scout_executor=scout_exec,
        anchor_affinity=anchor_aff,
        scout_affinity=scout_aff,
        is_parsl_installed=True,
        parsl_version="2026.08.10",
        is_heterogeneous_balanced=True,
    )
    amnesty = AmnestyAuditProfile(
        amnesty_file_path="/repo/.anti_spoof_amnesty.json",
        is_amnesty_present=True,
        total_amnestied_entries=18,
        is_utf8_lf_compliant=True,
        is_alphabetically_sorted=True,
        has_zero_duplicates=True,
        parsl_whitelisted=True,
        scanned_concurrency_modules=["parsl"],
    )

    with make_temp_dir() as tmpdir:
        art_path = Path(tmpdir) / "p9.json"
        report = Phase9AuditReport(
            phase_id="cochem_setup_phase_9",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-22T00:00:00Z",
            artifact_path=str(art_path),
            scout_anchor_profile=scout_anchor,
            amnesty_profile=amnesty,
            injected_env_vars={"COCHEM_PARSL_ANCHOR_CORES": "7"},
            warnings=[],
            errors=[],
        )
        json_str = report.model_dump_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["phase_id"] == "cochem_setup_phase_9"
        assert parsed["status"] == "PASSED"
        assert parsed["scout_anchor_profile"]["anchor_cores"] == 7
        assert parsed["scout_anchor_profile"]["scout_cores"] == 1

        restored = Phase9AuditReport.model_validate(parsed)
        assert restored.status == PhaseStatus.PASSED
        assert restored.scout_anchor_profile.scout_gpu_workers == 3


# =============================================================================
# 3. CPU TOPOLOGY & CORE AFFINITY ENGINE TESTS
# =============================================================================


def test_detect_system_cpu_topology_real() -> None:
    """Test detect_system_cpu_topology returns valid core counts on host."""
    phys, log = detect_system_cpu_topology()
    assert phys >= 1
    assert log >= 1
    assert log >= phys


def test_detect_system_cpu_topology_env_overrides() -> None:
    """Test detect_system_cpu_topology respects environment variable overrides."""
    env = {"COCHEM_PHYSICAL_CORES": "12", "COCHEM_LOGICAL_CORES": "24"}
    phys, log = detect_system_cpu_topology(env=env)
    assert phys == 12
    assert log == 24


def test_compute_core_affinity_distribution_8_cores() -> None:
    """Test Method Matrix v4 §8A default on 8-core system (7 Anchor, 1 Scout)."""
    anchor, scout, warnings = compute_core_affinity_distribution(total_physical=8)
    assert anchor.core_count == 7
    assert anchor.core_ids == [0, 1, 2, 3, 4, 5, 6]
    assert anchor.affinity_string == "list:0,1,2,3,4,5,6"
    assert scout.core_count == 1
    assert scout.core_ids == [7]
    assert scout.affinity_string == "list:7"
    assert len(warnings) == 0


def test_compute_core_affinity_distribution_4_cores() -> None:
    """Test Method Matrix v4 §8A allocation on smaller 4-core system (3 Anchor, 1 Scout)."""
    anchor, scout, warnings = compute_core_affinity_distribution(total_physical=4)
    assert anchor.core_count == 3
    assert anchor.core_ids == [0, 1, 2]
    assert anchor.affinity_string == "list:0,1,2"
    assert scout.core_count == 1
    assert scout.core_ids == [3]
    assert scout.affinity_string == "list:3"
    assert len(warnings) == 0


def test_compute_core_affinity_distribution_1_core_degraded() -> None:
    """Test 1-core system falls back to shared degraded mode with warning."""
    anchor, scout, warnings = compute_core_affinity_distribution(total_physical=1)
    assert anchor.core_count == 1
    assert anchor.core_ids == [0]
    assert anchor.strategy == AffinityStrategy.SHARED_DEGRADED
    assert scout.core_count == 1
    assert scout.core_ids == [0]
    assert scout.strategy == AffinityStrategy.SHARED_DEGRADED
    assert len(warnings) == 1
    assert "only 1 physical CPU core" in warnings[0]


def test_compute_core_affinity_distribution_custom_requests_and_oversubscription() -> None:
    """Test explicit custom core requests and over-subscription warning."""
    # Custom requests fitting within physical cores
    anchor, scout, warnings = compute_core_affinity_distribution(
        total_physical=16,
        requested_anchor=10,
        requested_scout=2,
    )
    assert anchor.core_count == 10
    assert scout.core_count == 2
    assert len(warnings) == 0

    # Over-subscription warning
    anchor_over, scout_over, warn_over = compute_core_affinity_distribution(
        total_physical=8,
        requested_anchor=7,
        requested_scout=4,
    )
    assert anchor_over.core_count == 7
    assert scout_over.core_count == 4
    assert len(warn_over) >= 1
    assert "exceed physical cores" in warn_over[0]
    # Core IDs must remain within physical topology [0..7] via modulo wrapping
    assert all(0 <= cid < 8 for cid in anchor_over.core_ids)
    assert all(0 <= cid < 8 for cid in scout_over.core_ids)
    assert scout_over.core_ids == [7, 0, 1, 2]


def test_compute_core_affinity_distribution_invalid_cores_error() -> None:
    """Test AffinityPinningError raised on total_physical <= 0."""
    with pytest.raises(AffinityPinningError):
        compute_core_affinity_distribution(total_physical=0)


# =============================================================================
# 4. ANTI-SPOOFING AMNESTY VALIDATION TESTS
# =============================================================================


def test_audit_anti_spoof_amnesty_real_repository() -> None:
    """Test audit_anti_spoof_amnesty on the active repository .anti_spoof_amnesty.json."""
    profile = audit_anti_spoof_amnesty()
    assert profile.is_amnesty_present is True
    assert profile.total_amnestied_entries >= 10
    assert profile.is_utf8_lf_compliant is True
    assert profile.is_alphabetically_sorted is True
    assert profile.has_zero_duplicates is True
    assert profile.parsl_whitelisted is True


def test_audit_anti_spoof_amnesty_missing_file() -> None:
    """Test audit_anti_spoof_amnesty gracefully returns missing profile when file does not exist."""
    with make_temp_dir() as tmpdir:
        non_existent = Path(tmpdir) / "missing_amnesty.json"
        profile = audit_anti_spoof_amnesty(amnesty_path=non_existent)
        assert profile.is_amnesty_present is False
        assert profile.total_amnestied_entries == 0


def test_audit_anti_spoof_amnesty_corrupted_json() -> None:
    """Test audit_anti_spoof_amnesty raises AmnestyVerificationError on non-JSON content."""
    with make_temp_dir() as tmpdir:
        bad_file = Path(tmpdir) / ".anti_spoof_amnesty.json"
        bad_file.write_text("NOT_JSON_DATA", encoding="utf-8")
        with pytest.raises(AmnestyVerificationError):
            audit_anti_spoof_amnesty(amnesty_path=bad_file)


def test_audit_anti_spoof_amnesty_unsorted_and_duplicates() -> None:
    """Test audit_anti_spoof_amnesty accurately detects unsorted arrays and duplicate entries."""
    with make_temp_dir() as tmpdir:
        unsorted_file = Path(tmpdir) / "unsorted_amnesty.json"
        unsorted_file.write_text(json.dumps(["z_module", "a_module", "parsl"]), encoding="utf-8")
        profile_unsorted = audit_anti_spoof_amnesty(amnesty_path=unsorted_file)
        assert profile_unsorted.is_alphabetically_sorted is False
        assert profile_unsorted.has_zero_duplicates is True

        dup_file = Path(tmpdir) / "dup_amnesty.json"
        dup_file.write_text(json.dumps(["a_module", "a_module", "parsl"]), encoding="utf-8")
        profile_dup = audit_anti_spoof_amnesty(amnesty_path=dup_file)
        assert profile_dup.has_zero_duplicates is False


def test_orchestrator_package_phase_9_exports() -> None:
    """Test that orchestrator package root re-exports Phase 9 symbols cleanly."""
    import orchestrator
    assert hasattr(orchestrator, "Phase9AuditReport")
    assert hasattr(orchestrator, "run_phase_9_audit")
    assert hasattr(orchestrator, "ScoutAndAnchorProfile")
    assert hasattr(orchestrator, "HTEXExecutorConfig")
    assert hasattr(orchestrator, "generate_phase_9_env_vars")
    assert "run_phase_9_audit" in orchestrator.__all__


# =============================================================================
# 5. PARSL PROVIDER RESOLUTION & HTEX CONFIGURATION TESTS
# =============================================================================


def test_resolve_parsl_provider_overrides_and_detection() -> None:
    """Test resolve_parsl_provider with explicit arguments, env vars, and HPC detections."""
    # 1. Explicit override
    assert resolve_parsl_provider(provider_override="SLURM") == ParslProviderType.SLURM
    assert resolve_parsl_provider(provider_override=ParslProviderType.PBS) == ParslProviderType.PBS

    # 2. Environment variable override
    env_slurm = {"COCHEM_PARSL_PROVIDER": "SLURM"}
    assert resolve_parsl_provider(env=env_slurm) == ParslProviderType.SLURM

    # 3. Slurm detection
    env_slurm_detect = {"SLURM_JOB_ID": "12345"}
    assert resolve_parsl_provider(env=env_slurm_detect) == ParslProviderType.SLURM

    # 4. PBS detection
    env_pbs = {"PBS_JOBID": "pbs_999"}
    assert resolve_parsl_provider(env=env_pbs) == ParslProviderType.PBS

    # 5. LSF detection
    env_lsf = {"LSB_JOBID": "lsf_888"}
    assert resolve_parsl_provider(env=env_lsf) == ParslProviderType.LSF

    # 6. Default Local
    assert resolve_parsl_provider(env={}) == ParslProviderType.LOCAL


def test_build_htex_executor_config_anchor_and_scout() -> None:
    """Test build_htex_executor_config generates appropriate settings for CPU Anchor and GPU Scout."""
    anchor_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=list(range(7)),
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    scout_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.GPU_SCOUT,
        core_count=1,
        core_ids=[7],
        affinity_string="list:7",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )

    anchor_exec = build_htex_executor_config(
        stream=ExecutorStreamType.CPU_ANCHOR,
        cores=7,
        affinity_mapping=anchor_aff,
        provider_type=ParslProviderType.LOCAL,
    )
    assert anchor_exec.label == "cochem_anchor_cpu"
    assert anchor_exec.max_workers_per_node == 7
    assert anchor_exec.cores_per_worker == 1.0
    assert anchor_exec.cpu_affinity == "list:0,1,2,3,4,5,6"

    scout_exec = build_htex_executor_config(
        stream=ExecutorStreamType.GPU_SCOUT,
        cores=1,
        affinity_mapping=scout_aff,
        provider_type=ParslProviderType.LOCAL,
        gpu_workers=3,
    )
    assert scout_exec.label == "cochem_scout_gpu"
    assert scout_exec.max_workers_per_node == 3
    assert scout_exec.cores_per_worker == 0.33
    assert scout_exec.cpu_affinity == "list:7"


def test_build_htex_executor_config_slurm_launcher() -> None:
    """Test build_htex_executor_config selects SrunLauncher for SLURM provider."""
    anchor_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=list(range(7)),
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    slurm_exec = build_htex_executor_config(
        stream=ExecutorStreamType.CPU_ANCHOR,
        cores=7,
        affinity_mapping=anchor_aff,
        provider_type=ParslProviderType.SLURM,
    )
    assert slurm_exec.provider == ParslProviderType.SLURM
    assert slurm_exec.launcher == "SrunLauncher"


def test_construct_parsl_config_object_real() -> None:
    """Test construct_parsl_config_object creates real Parsl Config with both executors or raises when missing."""
    anchor_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=list(range(7)),
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    scout_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.GPU_SCOUT,
        core_count=1,
        core_ids=[7],
        affinity_string="list:7",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    anchor_exec = build_htex_executor_config(
        stream=ExecutorStreamType.CPU_ANCHOR,
        cores=7,
        affinity_mapping=anchor_aff,
        provider_type=ParslProviderType.LOCAL,
    )
    scout_exec = build_htex_executor_config(
        stream=ExecutorStreamType.GPU_SCOUT,
        cores=1,
        affinity_mapping=scout_aff,
        provider_type=ParslProviderType.LOCAL,
        gpu_workers=3,
    )
    profile = ScoutAndAnchorProfile(
        total_physical_cores=8,
        total_logical_cores=16,
        anchor_cores=7,
        scout_cores=1,
        scout_gpu_workers=3,
        scout_step_latency_ms=18.1,
        anchor_executor=anchor_exec,
        scout_executor=scout_exec,
        anchor_affinity=anchor_aff,
        scout_affinity=scout_aff,
        is_parsl_installed=True,
        parsl_version="2026.08.10",
        is_heterogeneous_balanced=True,
    )

    try:
        import parsl
        cfg = construct_parsl_config_object(profile)
        assert hasattr(cfg, "executors")
        assert len(cfg.executors) == 2
        assert cfg.executors[0].label == "cochem_anchor_cpu"
        assert cfg.executors[1].label == "cochem_scout_gpu"
    except ImportError:
        with pytest.raises(ParslConfigGenerationError):
            construct_parsl_config_object(profile)


# =============================================================================
# 6. ENVIRONMENT INJECTION & REGISTRY PATH RESOLUTION TESTS
# =============================================================================


def test_generate_environment_injection_dict() -> None:
    """Test generate_environment_injection_dict produces all required COCHEM_PARSL_* variables."""
    anchor_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=7,
        core_ids=list(range(7)),
        affinity_string="list:0,1,2,3,4,5,6",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    scout_aff = CoreAffinityMapping(
        stream=ExecutorStreamType.GPU_SCOUT,
        core_count=1,
        core_ids=[7],
        affinity_string="list:7",
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    anchor_exec = build_htex_executor_config(
        stream=ExecutorStreamType.CPU_ANCHOR,
        cores=7,
        affinity_mapping=anchor_aff,
        provider_type=ParslProviderType.LOCAL,
    )
    scout_exec = build_htex_executor_config(
        stream=ExecutorStreamType.GPU_SCOUT,
        cores=1,
        affinity_mapping=scout_aff,
        provider_type=ParslProviderType.LOCAL,
        gpu_workers=3,
    )
    profile = ScoutAndAnchorProfile(
        total_physical_cores=8,
        total_logical_cores=16,
        anchor_cores=7,
        scout_cores=1,
        scout_gpu_workers=3,
        scout_step_latency_ms=18.1,
        anchor_executor=anchor_exec,
        scout_executor=scout_exec,
        anchor_affinity=anchor_aff,
        scout_affinity=scout_aff,
        is_parsl_installed=True,
        parsl_version="2026.08.10",
        is_heterogeneous_balanced=True,
    )
    amnesty = AmnestyAuditProfile(
        amnesty_file_path="/repo/.anti_spoof_amnesty.json",
        is_amnesty_present=True,
        total_amnestied_entries=18,
        is_utf8_lf_compliant=True,
        is_alphabetically_sorted=True,
        has_zero_duplicates=True,
        parsl_whitelisted=True,
        scanned_concurrency_modules=["parsl"],
    )

    injected = generate_environment_injection_dict(profile, amnesty)
    assert injected["COCHEM_PARSL_ANCHOR_CORES"] == "7"
    assert injected["COCHEM_PARSL_ANCHOR_AFFINITY"] == "list:0,1,2,3,4,5,6"
    assert injected["COCHEM_PARSL_SCOUT_CORES"] == "1"
    assert injected["COCHEM_PARSL_SCOUT_WORKERS"] == "3"
    assert injected["COCHEM_PARSL_SCOUT_AFFINITY"] == "list:7"
    assert injected["COCHEM_PARSL_SCOUT_LATENCY_MS"] == "18.1"
    assert injected["COCHEM_PARSL_PROVIDER"] == "LOCAL"
    assert injected["COCHEM_PARSL_AMNESTY_VERIFIED"] == "1"
    assert injected["COCHEM_PARSL_CONFIG_READY"] == "1"


def test_resolve_p9_registry_path_override_and_env() -> None:
    """Test resolving p9.json path with override parameter and environment variables."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "custom_p9.json"
        resolved = resolve_p9_registry_path(output_dir=target)
        assert resolved == target.resolve()

        target_dir = Path(tmpdir) / "registry_sub"
        resolved_dir = resolve_p9_registry_path(output_dir=target_dir)
        assert resolved_dir == (target_dir / "p9.json").resolve()

        env1 = {"COCHEM_REGISTRY_DIR": str(target_dir)}
        assert resolve_p9_registry_path(env=env1) == (target_dir / "p9.json").resolve()

        env2 = {"COCHEM_ARTIFACT_DIR": str(tmpdir)}
        assert resolve_p9_registry_path(env=env2) == (Path(tmpdir) / "Registry" / "p9.json").resolve()


# =============================================================================
# 7. DEPENDENCY MANAGER & TRANSACTIONAL ATOMIC WRITE TESTS
# =============================================================================


def test_dependency_manager_atomic_write_and_commit() -> None:
    """Test DependencyManager atomic writing and permissions hardening."""
    with make_temp_dir() as tmpdir:
        target_file = Path(tmpdir) / "Registry" / "p9.json"
        payload = {"phase": "phase_9", "status": "PASSED"}

        with DependencyManager(target_file) as dm:
            dm.write_payload(payload)

        assert target_file.exists()
        loaded = json.loads(target_file.read_text(encoding="utf-8"))
        assert loaded["phase"] == "phase_9"
        assert loaded["status"] == "PASSED"


def test_dependency_manager_rollback_on_exception() -> None:
    """Test DependencyManager safely cleans up temp files if an exception is raised."""
    with make_temp_dir() as tmpdir:
        target_file = Path(tmpdir) / "Registry" / "p9.json"

        with pytest.raises(ZeroDivisionError):
            with DependencyManager(target_file) as dm:
                dm.write_payload({"data": "incomplete"})
                _ = 1 / 0

        # Target file must not exist and no temporary files left behind
        assert not target_file.exists()
        remaining_files = list(Path(tmpdir).glob("**/*"))
        assert all(f.is_dir() for f in remaining_files)


# =============================================================================
# 8. MASTER AUDIT ORCHESTRATOR & CLI TESTS
# =============================================================================


def test_run_phase_9_audit_passed() -> None:
    """Test run_phase_9_audit end-to-end execution resulting in PASSED or DEGRADED status."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_9_audit(
            output_dir=art_dir,
        )
        assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
        assert report.phase_id == "cochem_setup_phase_9"
        assert Path(report.artifact_path).exists()
        assert report.scout_anchor_profile.anchor_cores >= 1
        assert report.scout_anchor_profile.scout_cores >= 1
        assert len(report.injected_env_vars) >= 8


def test_run_phase_9_audit_dry_run() -> None:
    """Test run_phase_9_audit with dry_run=True does not create artifacts on disk."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_9_audit(
            output_dir=art_dir,
            dry_run=True,
        )
        assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
        assert not Path(report.artifact_path).exists()


def test_run_phase_9_audit_custom_parameters() -> None:
    """Test run_phase_9_audit with custom core and worker allocations."""
    with make_temp_dir() as tmpdir:
        art_dir = Path(tmpdir) / "Registry"
        report = run_phase_9_audit(
            output_dir=art_dir,
            anchor_cores=10,
            scout_cores=2,
            scout_gpu_workers=4,
            provider="LOCAL",
        )
        assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
        assert report.scout_anchor_profile.anchor_cores == 10
        assert report.scout_anchor_profile.scout_cores == 2
        assert report.scout_anchor_profile.scout_gpu_workers == 4


def test_cli_main_success_and_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with argument passing and stdout verification."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--anchor-cores", "7", "--scout-cores", "1"])
        assert ret == 0

        captured = capsys.readouterr()
        assert "COCHEM SETUP PHASE 9" in captured.out
        assert "Status:" in captured.out


def test_cli_main_json_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with --json flag."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--json"])
        assert ret == 0

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["phase_id"] == "cochem_setup_phase_9"
        assert parsed["status"] in ("PASSED", "DEGRADED")


# =============================================================================
# 9. ZERO-MOCK MANDATE AST INSPECTION
# =============================================================================


def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    from ci_tools.anti_spoof_linter import BANNED_MOCK_MODULES
    prohibited_in_test: Set[str] = set(BANNED_MOCK_MODULES)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )
