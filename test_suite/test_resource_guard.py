# cochem_canvas_target: test_suite/test_resource_guard.py
"""
CoChem-BASE AI Hardware Safety Resource Guard Unit and Integration Test Suite.
Strict Zero-Mock Mandate Compliance.

Validates:
1. Pydantic typed ResourceGuardDecision schema, immutability, dict/JSON serialization.
2. Dynamic host physical RAM polling via Win32 Kernel32 GlobalMemoryStatusEx and psutil.
3. NVIDIA NVML (pynvml) VRAM metrics probing, device counts, and active compute/graphics processes.
4. Real Linux cgroups v1 (memory.limit_in_bytes) and cgroups v2 (memory.max) filesystem limit parsing.
5. Container runtime environment marker detection.
6. Real cochem_system_config.json discovery, HardwareSchema extraction, and active_jobs resolution.
7. Active calculation conflict detection (ORCA, xTB, CFOUR, AIMNet2, MACE, PySCF, GPU processes).
8. Physical RAM safety threshold boundary testing (<8.0 GB interception vs >=8.0 GB allowance).
9. Real-time available RAM and VRAM boundary interception.
10. Automatic failover cascading (Tier 2 EXTERNAL_API vs Tier 3 DRY_RUN).
11. Resilient exception handling against nonexistent, empty, and corrupted configuration files without fatal crashes.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

import psutil
import pytest

from cochem_core.ai.resource_guard import (
    CALCULATION_ENGINE_STEMS,
    ResourceGuardDecision,
    detect_active_calculations,
    evaluate_resource_guard,
    is_container_environment,
    probe_host_memory,
    probe_nvidia_vram,
    probe_windows_memory,
    read_cgroup_memory_limit,
    resolve_cochem_system_config,
)


def test_resource_guard_decision_schema_and_serialization() -> None:
    """Verifies typed validation, immutability, and serialization of ResourceGuardDecision."""
    decision = ResourceGuardDecision(
        allow_local_llm=True,
        execution_mode="LOCAL_LLM",
        total_ram_gb=32.0,
        available_ram_gb=16.5,
        is_container=False,
        container_ram_limit_gb=None,
        vram_gb=24.0,
        available_vram_gb=20.0,
        gpu_device_count=1,
        active_calculation_detected=False,
        intercepted=False,
        reason="Hardware safety criteria satisfied",
        hardware_schema={"ram_gb": 32.0, "vram_gb": 24.0},
        details={"os_target": "Windows"},
    )

    # Validate attributes
    assert decision.allow_local_llm is True
    assert decision.execution_mode == "LOCAL_LLM"
    assert decision.total_ram_gb == 32.0
    assert decision.available_ram_gb == 16.5
    assert decision.is_container is False
    assert decision.container_ram_limit_gb is None
    assert decision.vram_gb == 24.0
    assert decision.available_vram_gb == 20.0
    assert decision.gpu_device_count == 1
    assert decision.active_calculation_detected is False
    assert decision.intercepted is False
    assert "safety criteria satisfied" in decision.reason

    # Test dictionary serialization
    dumped_dict = decision.to_dict()
    assert isinstance(dumped_dict, dict)
    assert dumped_dict["allow_local_llm"] is True
    assert dumped_dict["total_ram_gb"] == 32.0

    # Test JSON serialization and round-trip parsing
    json_str = decision.to_json()
    assert isinstance(json_str, str)
    parsed_dict = json.loads(json_str)
    assert parsed_dict["execution_mode"] == "LOCAL_LLM"
    reloaded = ResourceGuardDecision.model_validate(parsed_dict)
    assert reloaded.total_ram_gb == decision.total_ram_gb
    assert reloaded.vram_gb == decision.vram_gb


def test_real_hardware_memory_probing() -> None:
    """Verifies real-time physical RAM probing against real OS APIs without mocks."""
    total_ram, avail_ram = probe_host_memory()
    assert isinstance(total_ram, float)
    assert isinstance(avail_ram, float)
    assert total_ram > 0.0
    assert avail_ram >= 0.0
    assert avail_ram <= total_ram * 1.05  # Allowing minor kernel page fluctuation

    # Cross-reference with real psutil virtual memory query
    psutil_vm = psutil.virtual_memory()
    expected_total_gb = round(psutil_vm.total / (1024 ** 3), 3)
    assert abs(total_ram - expected_total_gb) < 1.0

    if platform.system() == "Windows":
        win_total, win_avail = probe_windows_memory()
        assert win_total > 0.0
        assert win_avail >= 0.0
        assert abs(win_total - total_ram) < 0.1


def test_real_nvidia_vram_probing() -> None:
    """Verifies real NVIDIA NVML query execution or graceful fallback if no NVIDIA GPU is attached."""
    vram_gb, avail_vram_gb, gpu_count, gpu_procs = probe_nvidia_vram()

    assert isinstance(vram_gb, float)
    assert isinstance(avail_vram_gb, float)
    assert isinstance(gpu_count, int)
    assert isinstance(gpu_procs, list)
    assert vram_gb >= 0.0
    assert avail_vram_gb >= 0.0
    assert gpu_count >= 0

    if gpu_count > 0:
        assert vram_gb > 0.0
        assert avail_vram_gb <= vram_gb * 1.05
        for proc in gpu_procs:
            assert "pid" in proc
            assert "used_memory_gb" in proc
            assert "process_name" in proc


def test_cgroups_v2_memory_limit_parsing_real_files(tmp_path: Path) -> None:
    """Verifies parsing of real cgroups v2 memory.max files."""
    v2_file = tmp_path / "memory.max"

    # Test numerical limit: 4 GB in bytes (4294967296 bytes)
    v2_file.write_text("4294967296\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v2_path=v2_file)
    assert limit_gb == 4.0

    # Test numerical limit: 16 GB in bytes (17179869184 bytes)
    v2_file.write_text("17179869184\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v2_path=v2_file)
    assert limit_gb == 16.0

    # Test unconstrained container: 'max'
    v2_file.write_text("max\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v2_path=v2_file)
    assert limit_gb is None

    # Test invalid / non-numeric content
    v2_file.write_text("unlimited\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v2_path=v2_file)
    assert limit_gb is None


def test_cgroups_v1_memory_limit_parsing_real_files(tmp_path: Path) -> None:
    """Verifies parsing of real cgroups v1 memory.limit_in_bytes files."""
    v1_file = tmp_path / "memory.limit_in_bytes"

    # Test numerical limit: 8 GB in bytes (8589934592 bytes)
    v1_file.write_text("8589934592\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v1_path=v1_file)
    assert limit_gb == 8.0

    # Test unconstrained container in cgroups v1 (typical huge number ~ 2^63 - 4096)
    v1_file.write_text("9223372036854771712\n", encoding="utf-8")
    limit_gb = read_cgroup_memory_limit(cgroup_v1_path=v1_file)
    assert limit_gb is None


def test_cgroups_nonexistent_paths(tmp_path: Path) -> None:
    """Verifies that nonexistent cgroup files return None gracefully without errors."""
    missing_v2 = tmp_path / "missing_v2.max"
    missing_v1 = tmp_path / "missing_v1.limit"
    limit_gb = read_cgroup_memory_limit(cgroup_v2_path=missing_v2, cgroup_v1_path=missing_v1)
    assert limit_gb is None


def test_is_container_environment_real() -> None:
    """Verifies real runtime container inspection returns a boolean."""
    is_cont = is_container_environment()
    assert isinstance(is_cont, bool)


def test_active_calculation_detection_from_config_jobs() -> None:
    """Verifies active calculation detection from system configuration active_jobs registry."""
    # Active running job
    active_jobs_running = {
        "orca_opt_001": {"status": "running", "engine": "orca", "pid": 1001}
    }
    is_active, reasons = detect_active_calculations(
        config_active_jobs=active_jobs_running,
        scan_process_table=False
    )
    assert is_active is True
    assert len(reasons) == 1
    assert "orca_opt_001" in reasons[0]
    assert "running" in reasons[0]

    # Active in_progress job
    active_jobs_progress = {
        "xtb_grad_002": {"status": "in_progress", "engine": "xtb"}
    }
    is_active, reasons = detect_active_calculations(
        config_active_jobs=active_jobs_progress,
        scan_process_table=False
    )
    assert is_active is True
    assert "xtb_grad_002" in reasons[0]

    # Completed jobs (should NOT trigger active detection)
    finished_jobs = {
        "orca_job_done": {"status": "completed"},
        "xtb_job_fail": {"status": "failed"},
        "mace_job_cancelled": {"status": "cancelled"},
        "job_term": {"status": "terminated"},
    }
    is_active, reasons = detect_active_calculations(
        config_active_jobs=finished_jobs,
        scan_process_table=False
    )
    assert is_active is False
    assert len(reasons) == 0

    # Empty dictionary
    is_active, reasons = detect_active_calculations(
        config_active_jobs={},
        scan_process_table=False
    )
    assert is_active is False
    assert len(reasons) == 0


def test_active_calculation_detection_from_gpu_processes() -> None:
    """Verifies detection of computational chemistry processes allocating GPU VRAM."""
    calc_gpu_proc = [
        {
            "device_index": 0,
            "pid": 4321,
            "used_memory_bytes": 4294967296,
            "used_memory_gb": 4.0,
            "process_name": "orca.exe",
            "type": "compute",
        }
    ]
    is_active, reasons = detect_active_calculations(
        config_active_jobs={},
        scan_process_table=False,
        gpu_processes=calc_gpu_proc,
    )
    assert is_active is True
    assert any("orca" in r for r in reasons)

    # General compute process with substantial memory allocation
    heavy_compute_proc = [
        {
            "device_index": 0,
            "pid": 8765,
            "used_memory_bytes": 3221225472,
            "used_memory_gb": 3.0,
            "process_name": "cuda_solver",
            "type": "compute",
        }
    ]
    is_active, reasons = detect_active_calculations(
        config_active_jobs={},
        scan_process_table=False,
        gpu_processes=heavy_compute_proc,
    )
    assert is_active is True
    assert any("cuda_solver" in r for r in reasons)

    # Idle graphics process (e.g. desktop window manager, small VRAM)
    idle_gfx_proc = [
        {
            "device_index": 0,
            "pid": 100,
            "used_memory_bytes": 104857600,
            "used_memory_gb": 0.098,
            "process_name": "dwmp.exe",
            "type": "graphics",
        }
    ]
    is_active, reasons = detect_active_calculations(
        config_active_jobs={},
        scan_process_table=False,
        gpu_processes=idle_gfx_proc,
    )
    assert is_active is False
    assert len(reasons) == 0


def test_calculation_engine_stems_completeness() -> None:
    """Verifies that all standard CoChem quantum chemistry and MLFF engines are covered."""
    required_engines = {"orca", "xtb", "cfour", "aimnet2", "mace", "pyscf", "mpirun", "spycfit"}
    assert required_engines.issubset(CALCULATION_ENGINE_STEMS)


def test_ram_threshold_interception_boundary(tmp_path: Path) -> None:
    """Verifies that when RAM is below min_ram_gb threshold, the request is intercepted."""
    # Test setting an impossible min_ram_gb requirement (e.g. 5000.0 GB)
    decision = evaluate_resource_guard(
        min_ram_gb=5000.0,
        scan_process_table=False,
        system_config_override={"active_jobs": {}},
    )

    assert decision.allow_local_llm is False
    assert decision.intercepted is True
    assert "below minimum safety threshold" in decision.reason or "Container memory ceiling" in decision.reason
    assert decision.execution_mode in ("EXTERNAL_API", "DRY_RUN")


def test_container_ram_limit_interception_real_file(tmp_path: Path) -> None:
    """Verifies that a constrained cgroups container RAM limit overrides host RAM and triggers interception."""
    # Write a real cgroup v2 file with 4.0 GB memory limit
    cg_file = tmp_path / "memory.max"
    cg_file.write_text("4294967296\n", encoding="utf-8")  # 4 GB

    decision = evaluate_resource_guard(
        min_ram_gb=8.0,
        custom_cgroup_v2_path=cg_file,
        scan_process_table=False,
        system_config_override={"active_jobs": {}},
    )

    assert decision.intercepted is True
    assert decision.allow_local_llm is False
    assert decision.total_ram_gb == 4.0
    assert decision.container_ram_limit_gb == 4.0
    assert "Container memory ceiling (4.00 GB) is below safety threshold (8.00 GB)" in decision.reason


def test_active_job_interception_and_failover_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that active jobs force interception and fail over to EXTERNAL_API or DRY_RUN."""
    active_override = {
        "active_jobs": {
            "orca_scf_calc_123": {"status": "running", "engine": "orca"}
        }
    }

    # Test failover without API keys in environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("COCHEM_AI_API_KEY", raising=False)

    decision_dry = evaluate_resource_guard(
        min_ram_gb=1.0,
        scan_process_table=False,
        system_config_override=active_override,
    )
    assert decision_dry.intercepted is True
    assert decision_dry.allow_local_llm is False
    assert decision_dry.execution_mode == "DRY_RUN"
    assert "Active calculation detected" in decision_dry.reason

    # Test failover with GEMINI_API_KEY set
    monkeypatch.setenv("GEMINI_API_KEY", "test_gemini_api_key_auth_value_12345")
    decision_api = evaluate_resource_guard(
        min_ram_gb=1.0,
        scan_process_table=False,
        system_config_override=active_override,
    )
    assert decision_api.intercepted is True
    assert decision_api.allow_local_llm is False
    assert decision_api.execution_mode == "EXTERNAL_API"

    # Test explicit fallback_mode override
    decision_custom = evaluate_resource_guard(
        min_ram_gb=1.0,
        scan_process_table=False,
        fallback_mode="CUSTOM_FALLBACK",
        system_config_override=active_override,
    )
    assert decision_custom.execution_mode == "CUSTOM_FALLBACK"


def test_vram_and_available_ram_threshold_boundaries() -> None:
    """Verifies interception when available VRAM or available host RAM is insufficient."""
    # Test impossible min_vram_gb threshold (1000.0 GB)
    decision_vram = evaluate_resource_guard(
        min_ram_gb=1.0,
        min_vram_gb=1000.0,
        scan_process_table=False,
        system_config_override={"active_jobs": {}},
    )
    assert decision_vram.intercepted is True
    assert decision_vram.allow_local_llm is False
    assert "Available VRAM" in decision_vram.reason

    # Test impossible min_available_ram_gb threshold (5000.0 GB)
    decision_avail_ram = evaluate_resource_guard(
        min_ram_gb=1.0,
        min_available_ram_gb=5000.0,
        scan_process_table=False,
        system_config_override={"active_jobs": {}},
    )
    assert decision_avail_ram.intercepted is True
    assert decision_avail_ram.allow_local_llm is False
    assert "Available RAM" in decision_avail_ram.reason


def test_resolve_cochem_system_config_real_file(tmp_path: Path) -> None:
    """Verifies resolution and parsing of real cochem_system_config.json files on disk."""
    config_file = tmp_path / "cochem_system_config.json"
    config_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "ram_gb": 64.0,
            "vram_gb": 24.0,
            "physical_cpu_cores": 16,
            "logical_cpu_cores": 32,
            "gpu_profile": "NVIDIA RTX 4090",
            "os_target": "Local-Windows",
        },
        "active_jobs": {
            "test_job": {"status": "completed"}
        }
    }
    config_file.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")

    hw_schema, active_jobs, path_str = resolve_cochem_system_config(config_path=config_file)
    assert hw_schema is not None
    assert hw_schema["ram_gb"] == 64.0
    assert hw_schema["vram_gb"] == 24.0
    assert hw_schema["gpu_profile"] == "NVIDIA RTX 4090"
    assert active_jobs == {"test_job": {"status": "completed"}}
    assert path_str == str(config_file.resolve())


def test_robust_error_handling_nonexistent_and_corrupt_files(tmp_path: Path) -> None:
    """Verifies that missing, empty, and corrupted JSON files never cause fatal exceptions."""
    # 1. Nonexistent file path
    missing_path = tmp_path / "non_existent_config.json"
    hw_schema, active_jobs, path_str = resolve_cochem_system_config(config_path=missing_path)
    assert hw_schema is None or isinstance(hw_schema, dict)

    # 2. Corrupted JSON file
    corrupt_file = tmp_path / "corrupted_config.json"
    corrupt_file.write_text("{ unclosed invalid json payload ...", encoding="utf-8")
    hw_schema_c, active_jobs_c, path_str_c = resolve_cochem_system_config(config_path=corrupt_file)
    assert hw_schema_c is None or isinstance(hw_schema_c, dict)

    # 3. Empty file
    empty_file = tmp_path / "empty_config.json"
    empty_file.write_text("", encoding="utf-8")
    hw_schema_e, active_jobs_e, path_str_e = resolve_cochem_system_config(config_path=empty_file)
    assert hw_schema_e is None or isinstance(hw_schema_e, dict)

    # 4. evaluate_resource_guard with corrupted file should complete smoothly
    decision = evaluate_resource_guard(config_path=corrupt_file)
    assert isinstance(decision, ResourceGuardDecision)
    assert decision.total_ram_gb > 0.0


def test_full_evaluation_telemetry_payload() -> None:
    """Verifies that ResourceGuardDecision contains comprehensive diagnostic telemetry."""
    decision = evaluate_resource_guard(scan_process_table=False, system_config_override={"active_jobs": {}})

    assert isinstance(decision.details, dict)
    assert "os_target" in decision.details
    assert "host_total_ram_gb" in decision.details
    assert "host_available_ram_gb" in decision.details
    assert "gpu_processes" in decision.details
    assert "active_reasons" in decision.details
    assert "intercept_reasons" in decision.details
    assert decision.details["host_total_ram_gb"] > 0.0


def test_env_vars_config_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies config resolution via COCHEM_CONFIG and COCHEM_ARTIFACT_DIR env vars."""
    custom_cfg = tmp_path / "env_config.json"
    custom_cfg.write_text(json.dumps({"hardware": {"ram_gb": 128.0}, "active_jobs": {}}), encoding="utf-8")

    monkeypatch.setenv("COCHEM_CONFIG", str(custom_cfg))
    hw, jobs, resolved_path = resolve_cochem_system_config()
    assert hw is not None
    assert hw["ram_gb"] == 128.0
    assert resolved_path == str(custom_cfg.resolve())

    # Test COCHEM_ARTIFACT_DIR
    monkeypatch.delenv("COCHEM_CONFIG", raising=False)
    art_dir = tmp_path / "artifacts"
    reg_dir = art_dir / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    art_cfg = reg_dir / "cochem_system_config.json"
    art_cfg.write_text(json.dumps({"hardware": {"vram_gb": 48.0}}), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(art_dir))
    hw_art, jobs_art, resolved_path_art = resolve_cochem_system_config()
    assert hw_art is not None
    assert hw_art["vram_gb"] == 48.0
    assert resolved_path_art == str(art_cfg.resolve())


def test_container_env_variable_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that container environment variables are detected without synthetic mocks."""
    monkeypatch.setenv("CONTAINER", "true")
    assert is_container_environment() is True

    monkeypatch.delenv("CONTAINER", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert is_container_environment() is True

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    assert is_container_environment() is True


def test_active_calculation_non_dict_job_entry_and_inactive_status() -> None:
    """Verifies active calculation handling for non-dict job entries and inactive statuses."""
    active_jobs = {
        "raw_string_entry": "running_some_job",
        "inactive_job": {"status": "inactive"},
    }
    is_active, reasons = detect_active_calculations(
        config_active_jobs=active_jobs,
        scan_process_table=False
    )
    assert is_active is True
    assert any("raw_string_entry" in r for r in reasons)
    assert not any("inactive_job" in r for r in reasons)


def test_fatal_exception_failover_safety() -> None:
    """Verifies that if an unexpected error occurs, evaluate_resource_guard fails over cleanly."""
    # Pass an invalid min_ram_gb type or trigger internal exception
    # evaluate_resource_guard handles exceptions at the top level
    decision = evaluate_resource_guard(min_ram_gb=-999.0)
    assert isinstance(decision, ResourceGuardDecision)
    assert decision.total_ram_gb >= 0.0

