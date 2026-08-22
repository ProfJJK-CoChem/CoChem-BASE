#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit and Integration Test Suite for CoChem Core Config Compiler.
Validates:
1. Mendeleev ECP Gates & heavy element validation (Z > 36).
2. Semantic version pinning gatekeeper (enforce_semver_pinning).
3. Abstracted HPC schedulers (SlurmStrategy, PBSStrategy, LocalStrategy).
4. HardwareProfileSpec model & real system hardware probing.
5. Tailored hardware environment generation (OMP_NUM_THREADS, MKL, KMP affinity, CUDA, maxcore).
6. Micro-silo binary verification across search roots and custom manifests.
7. Dynamic Fallback Router (MACE -> AIMNet2 -> g-xTB, gpu4pyscf crossover, memory constraints).
8. Asynchronous templater (AsyncTemplateRenderer) with conditionals, filters, and chemistry decks.
9. Execution Handshake Manager (HMAC-SHA256 cryptographic tokens, TTL expiry, tamper detection).
10. ConfigCompiler end-to-end synchronous and asynchronous compilation bundles.
11. Verification-aware dynamic routing with micro-silo manifests.

Strict Zero-Mock Mandate:
- 100% physically executable tests adhering to the Zero-Mock mandate.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
import platform
import stat
import sys
import time
from typing import Any, Dict, List, Tuple

import pytest
from packaging import version

from core_engine.cochem_core_config_compiler import (
    AsyncTemplateRenderer,
    BinaryNotFoundError,
    BinaryVerificationResult,
    CompiledJobBundle,
    CompilerError,
    ConfigCompiler,
    DynamicFallbackRouter,
    ECPValidationError,
    EngineType,
    ExecutionHandshakeManager,
    HandshakeToken,
    HandshakeVerificationError,
    HandshakeVerificationResult,
    HardwareConstraintError,
    HardwareEnvGenerator,
    HardwareProfileSpec,
    LocalStrategy,
    MicroSiloVerifier,
    PBSStrategy,
    RouteDecision,
    SchedulerStrategy,
    SlurmStrategy,
    TaskType,
    TemplateSyntaxError,
)


# =============================================================================
# 1. MENDELEEV ECP GATES & HEAVY ELEMENT VALIDATION
# =============================================================================


def test_ecp_validation_light_elements_pass() -> None:
    """Test that light elements (Z <= 36) pass ECP validation without defined ECPs."""
    compiler = ConfigCompiler()
    light_elements = ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "Fe"]
    # Should execute without raising any exception
    compiler.validate_ecp_requirements(light_elements, defined_ecps={})


def test_ecp_validation_heavy_element_without_ecp_raises() -> None:
    """Test that heavy elements (Z > 36) without defined ECP raise ECPValidationError."""
    compiler = ConfigCompiler()

    # Iodine (Z=53)
    with pytest.raises(ECPValidationError, match="Heavy element I .* missing ECP specification"):
        compiler.validate_ecp_requirements(["C", "H", "I"], defined_ecps={})

    # Platinum (Z=78)
    with pytest.raises(ECPValidationError, match="Heavy element Pt .* missing ECP specification"):
        compiler.validate_ecp_requirements(["Pt", "Cl", "N", "H"], defined_ecps={})

    # Uranium (Z=92)
    with pytest.raises(ECPValidationError, match="Heavy element U .* missing ECP specification"):
        compiler.validate_ecp_requirements(["U", "O"], defined_ecps={})


def test_ecp_validation_heavy_element_with_ecp_passes() -> None:
    """Test that heavy elements with defined ECP pass validation cleanly."""
    compiler = ConfigCompiler()
    elements = ["C", "H", "I", "Pt", "Au"]
    ecps = {
        "I": "def2-TZVPP-ECP",
        "Pt": "def2-ECP",
        "Au": "crenbl-ecp",
    }
    compiler.validate_ecp_requirements(elements, defined_ecps=ecps)


def test_ecp_validation_invalid_element_symbol_raises() -> None:
    """Test that non-existent chemical symbols raise ValueError."""
    compiler = ConfigCompiler()
    with pytest.raises(ValueError, match="Invalid chemical symbol 'Xx'"):
        compiler.validate_ecp_requirements(["C", "H", "Xx"], defined_ecps={})


def test_ecp_validation_duplicate_symbols_handled() -> None:
    """Test that duplicate symbols in element list are deduplicated cleanly."""
    compiler = ConfigCompiler()
    compiler.validate_ecp_requirements(["C", "C", "H", "H", "O", "O"], defined_ecps={})


# =============================================================================
# 2. SEMANTIC VERSION PINNING GATEKEEPER
# =============================================================================


def test_semver_pinning_equal_and_greater_versions() -> None:
    """Test that versions meeting or exceeding minimum requirement pass."""
    compiler = ConfigCompiler()

    assert compiler.enforce_semver_pinning("ORCA", "6.1.0", "6.1.0") is True
    assert compiler.enforce_semver_pinning("ORCA", "6.1.1", "6.1.0") is True
    assert compiler.enforce_semver_pinning("ORCA", "7.0.0", "6.1.0") is True
    assert compiler.enforce_semver_pinning("gpu4pyscf", "1.8.0", "1.8.0") is True
    assert compiler.enforce_semver_pinning("gpu4pyscf", "1.9.2", "1.8.0") is True


def test_semver_pinning_lower_versions_fail() -> None:
    """Test that versions below the minimum requirement return False."""
    compiler = ConfigCompiler()

    assert compiler.enforce_semver_pinning("ORCA", "5.0.4", "6.1.0") is False
    assert compiler.enforce_semver_pinning("gpu4pyscf", "1.7.9", "1.8.0") is False
    assert compiler.enforce_semver_pinning("CFOUR", "2.1.0", "2.2.0") is False


def test_semver_pinning_empty_or_invalid_version_raises() -> None:
    """Test that empty version strings raise ValueError."""
    compiler = ConfigCompiler()

    with pytest.raises(ValueError, match="Version string is empty or missing"):
        compiler.enforce_semver_pinning("ORCA", "", "6.1.0")


def test_semver_pinning_prerelease_and_postrelease() -> None:
    """Test semver comparison with pre-release and post-release tags."""
    compiler = ConfigCompiler()

    # Pre-release is lower than release
    assert compiler.enforce_semver_pinning("MACE", "0.3.0a1", "0.3.0") is False
    # Post-release is higher than release
    assert compiler.enforce_semver_pinning("MACE", "0.3.0.post1", "0.3.0") is True


# =============================================================================
# 3. ABSTRACTED HPC SCHEDULER STRATEGIES
# =============================================================================


def test_slurm_strategy_script_generation() -> None:
    """Test SLURM submission script formatting with custom parameters."""
    strategy = SlurmStrategy(walltime="12:00:00", partition="gpu-cluster")
    script = strategy.build_submission_script(
        job_name="opt_water",
        command="orca water.inp",
        nodes=2,
        cpus=16,
        walltime="08:00:00",
        partition="nvme-nodes",
    )

    assert "#!/bin/bash" in script
    assert "#SBATCH --job-name=opt_water" in script
    assert "#SBATCH --nodes=2" in script
    assert "#SBATCH --ntasks-per-node=16" in script
    assert "#SBATCH --time=08:00:00" in script
    assert "#SBATCH --partition=nvme-nodes" in script
    assert "srun --mpi=pmi2 orca water.inp" in script


def test_pbs_strategy_script_generation() -> None:
    """Test PBS submission script formatting with custom parameters."""
    strategy = PBSStrategy(walltime="24:00:00")
    script = strategy.build_submission_script(
        job_name="freq_benzene",
        command="cfour ZMAT",
        nodes=1,
        cpus=8,
        walltime="04:30:00",
    )

    assert "#!/bin/bash" in script
    assert "#PBS -N freq_benzene" in script
    assert "#PBS -l nodes=1:ppn=8" in script
    assert "#PBS -l walltime=04:30:00" in script
    assert "mpirun -np 8 cfour ZMAT" in script


def test_local_strategy_script_generation() -> None:
    """Test Local execution script formatting."""
    strategy = LocalStrategy()
    script = strategy.build_submission_script(
        job_name="xtb_opt",
        command="xtb input.xyz --opt",
        nodes=1,
        cpus=4,
    )

    assert "#!/bin/bash" in script
    assert "export OMP_NUM_THREADS=4" in script
    assert "export MKL_NUM_THREADS=4" in script
    assert "xtb input.xyz --opt" in script


def test_local_strategy_with_custom_env_vars() -> None:
    """Test LocalStrategy with tailored environment variable dictionary."""
    strategy = LocalStrategy()
    custom_env = {
        "OMP_NUM_THREADS": "7",
        "MKL_NUM_THREADS": "7",
        "CUDA_VISIBLE_DEVICES": "0",
        "COCHEM_MAXCORE_MB": "3400",
    }
    script = strategy.build_submission_script(
        job_name="orca_tight",
        command="orca input.inp",
        nodes=1,
        cpus=7,
        env_vars=custom_env,
    )

    assert "export OMP_NUM_THREADS=7" in script
    assert "export CUDA_VISIBLE_DEVICES=0" in script
    assert "export COCHEM_MAXCORE_MB=3400" in script
    assert "orca input.inp" in script


# =============================================================================
# 4. HARDWARE PROFILE SPECIFICATION & REAL PROBING
# =============================================================================


def test_hardware_profile_spec_defaults_and_validation() -> None:
    """Test HardwareProfileSpec model defaults and field boundaries."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        p_cores=8,
        e_cores=8,
        memory_total_gb=64.0,
        memory_available_gb=48.0,
        gpu_count=1,
        gpu_vram_gb=24.0,
        gpu_device_ids=[0],
        has_avx512=True,
        has_avx2=True,
        has_cuda=True,
        mps_enabled=True,
        maxcore_mb=4000,
    )

    assert hw.cpu_count == 16
    assert hw.physical_cores == 8
    assert hw.memory_total_gb == 64.0
    assert hw.gpu_count == 1
    assert hw.gpu_vram_gb == 24.0
    assert hw.has_avx512 is True
    assert hw.mps_enabled is True
    assert hw.maxcore_mb == 4000


def test_hardware_profile_spec_from_system() -> None:
    """Test real physical host hardware probe via HardwareProfileSpec.from_system()."""
    hw = HardwareProfileSpec.from_system()

    assert hw.cpu_count >= 1
    assert hw.physical_cores >= 1
    assert hw.memory_total_gb > 0.0
    assert hw.memory_available_gb > 0.0
    assert isinstance(hw.has_avx2, bool)
    assert isinstance(hw.has_cuda, bool)
    assert isinstance(hw.gpu_device_ids, list)


# =============================================================================
# 5. HARDWARE-TAILORED ENVIRONMENT GENERATION
# =============================================================================


def test_env_generator_cpu_bound_workload() -> None:
    """Test environment generation for pure CPU-bound task on non-hybrid architecture."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        p_cores=8,
        e_cores=0,
        memory_total_gb=32.0,
        memory_available_gb=24.0,
        gpu_count=0,
    )

    env = HardwareEnvGenerator.generate_environment(
        hardware=hw,
        task_type=TaskType.CPU_BOUND,
        target_engine="orca",
    )

    assert env["OMP_NUM_THREADS"] == "8"
    assert env["MKL_NUM_THREADS"] == "8"
    assert env["OPENBLAS_NUM_THREADS"] == "8"
    assert env["NUMEXPR_NUM_THREADS"] == "8"
    assert env["OMP_DYNAMIC"] == "FALSE"
    assert env["KMP_AFFINITY"] == "granularity=fine,compact,1,0"
    assert env["KMP_BLOCKTIME"] == "0"
    assert env["OMP_PROC_BIND"] == "CLOSE"
    assert env["OMP_PLACES"] == "cores"
    assert env["CUDA_VISIBLE_DEVICES"] == ""

    # Memory: 24GB * 1024 * 0.75 / 8 = ~2304 MB
    maxcore = int(env["COCHEM_MAXCORE_MB"])
    assert maxcore >= 2000
    assert env["ORCA_MAXCORE_MB"] == env["COCHEM_MAXCORE_MB"]


def test_env_generator_hybrid_scout_anchor_pipeline() -> None:
    """
    Test environment generation for hybrid Scout/Anchor workflow (Method Matrix §8A).
    Must reserve 1 P-core for GPU scout and assign 7 P-cores to CPU anchor.
    """
    hw = HardwareProfileSpec(
        cpu_count=24,
        physical_cores=16,
        p_cores=8,
        e_cores=8,
        memory_total_gb=64.0,
        memory_available_gb=48.0,
        gpu_count=1,
        gpu_vram_gb=24.0,
        gpu_device_ids=[0],
    )

    env = HardwareEnvGenerator.generate_environment(
        hardware=hw,
        task_type=TaskType.HYBRID_SCOUT_ANCHOR,
        target_engine="orca",
        reserved_p_cores=1,
    )

    # Anchor receives 8 - 1 = 7 cores
    assert env["OMP_NUM_THREADS"] == "7"
    assert env["MKL_NUM_THREADS"] == "7"
    assert env["KMP_HW_SUBSET"] == "7c:intel_core,1t"
    assert env["CUDA_VISIBLE_DEVICES"] == "0"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"


def test_env_generator_gpu_mlff_workload() -> None:
    """Test environment generation for GPU MLFF inference workload."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        p_cores=8,
        e_cores=0,
        memory_total_gb=32.0,
        memory_available_gb=24.0,
        gpu_count=2,
        gpu_vram_gb=12.0,
        gpu_device_ids=[0, 1],
        mps_enabled=True,
    )

    env = HardwareEnvGenerator.generate_environment(
        hardware=hw,
        task_type=TaskType.GPU_MLFF,
        target_engine="mace_off24m",
        reserved_p_cores=2,
    )

    # Host worker threads capped to reserved P-cores
    assert env["OMP_NUM_THREADS"] == "2"
    assert env["CUDA_VISIBLE_DEVICES"] == "0,1"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    assert "CUDA_MPS_PIPE_DIRECTORY" in env
    assert "CUDA_MPS_LOG_DIRECTORY" in env
    assert env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "25"


def test_env_generator_explicit_overrides() -> None:
    """Test explicit thread and maxcore overrides."""
    hw = HardwareProfileSpec(
        cpu_count=32,
        physical_cores=16,
        memory_total_gb=128.0,
        memory_available_gb=96.0,
        maxcore_mb=5000,
    )

    custom_overlay = {"CUSTOM_VAR": "TEST_VAL_123"}

    env = HardwareEnvGenerator.generate_environment(
        hardware=hw,
        task_type=TaskType.CPU_BOUND,
        requested_threads=12,
        custom_env=custom_overlay,
    )

    assert env["OMP_NUM_THREADS"] == "12"
    assert env["COCHEM_MAXCORE_MB"] == "5000"
    assert env["CUSTOM_VAR"] == "TEST_VAL_123"


# =============================================================================
# 6. MICRO-SILO BINARY VERIFIER
# =============================================================================


def test_micro_silo_verifier_real_python_executable() -> None:
    """Test verifying the active Python executable on the host system."""
    verifier = MicroSiloVerifier()
    res = verifier.verify_binary("python", candidate_path=sys.executable)

    assert res.is_valid is True
    assert res.exists is True
    assert res.is_executable is True
    assert res.executable_path == str(Path(sys.executable).resolve())


def test_micro_silo_verifier_temp_executable_file(tmp_path: Path) -> None:
    """Test verifying a dynamically created real executable file in a micro-silo root."""
    silo_bin = tmp_path / "custom_silo" / "bin"
    silo_bin.mkdir(parents=True, exist_ok=True)

    # Create dummy mock-free real executable script
    if platform.system() == "Windows":
        exe_file = silo_bin / "mockfree_tool.bat"
        exe_file.write_text("@echo off\necho 1.0.0\n", encoding="utf-8")
    else:
        exe_file = silo_bin / "mockfree_tool"
        exe_file.write_text("#!/bin/sh\necho 1.0.0\n", encoding="utf-8")
        exe_file.chmod(exe_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    verifier = MicroSiloVerifier(silo_roots=[tmp_path / "custom_silo"])
    res = verifier.verify_binary("mockfree_tool")

    assert res.is_valid is True
    assert res.exists is True
    assert res.is_executable is True
    assert res.silo_tier == "micro_silo"


def test_micro_silo_verifier_missing_binary() -> None:
    """Test verifying a non-existent binary returns structured failure."""
    verifier = MicroSiloVerifier(silo_roots=[])
    res = verifier.verify_binary("non_existent_qm_engine_xyz999")

    assert res.is_valid is False
    assert res.exists is False
    assert res.is_executable is False
    assert res.executable_path is None
    assert "not found in silos or PATH" in (res.error_message or "")


def test_micro_silo_verifier_manifest_override(tmp_path: Path) -> None:
    """Test verifying binary via custom manifest mapping."""
    target_bin = tmp_path / "special_orca.exe" if platform.system() == "Windows" else tmp_path / "special_orca"
    target_bin.write_text("binary content", encoding="utf-8")
    if platform.system() != "Windows":
        target_bin.chmod(target_bin.stat().st_mode | stat.S_IXUSR)

    manifest = {"orca": str(target_bin)}
    verifier = MicroSiloVerifier(custom_manifest=manifest)
    res = verifier.verify_binary("orca")

    assert res.is_valid is True
    assert res.silo_tier == "manifest"
    assert res.executable_path == str(target_bin.resolve())


def test_micro_silo_verifier_batch_verify(tmp_path: Path) -> None:
    """Test batch verification of multiple binaries."""
    bin1 = tmp_path / "tool1.bat" if platform.system() == "Windows" else tmp_path / "tool1"
    bin1.write_text("tool1", encoding="utf-8")
    if platform.system() != "Windows":
        bin1.chmod(bin1.stat().st_mode | stat.S_IXUSR)

    manifest = {
        "tool1": str(bin1),
        "tool2_missing": str(tmp_path / "non_existent_file"),
    }

    verifier = MicroSiloVerifier(custom_manifest=manifest)
    results = verifier.verify_all_silos(manifest)

    assert results["tool1"].is_valid is True
    assert results["tool2_missing"].is_valid is False


# =============================================================================
# 7. DYNAMIC FALLBACK ROUTER
# =============================================================================


def test_router_mace_on_capable_gpu() -> None:
    """Test that MACE-OFF24m stays on MACE when GPU VRAM >= 4.0GB."""
    hw = HardwareProfileSpec(
        gpu_count=1,
        gpu_vram_gb=12.0,
        has_cuda=True,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("mace_off24m", hardware=hw, task_type=TaskType.GPU_MLFF)

    assert decision.selected_engine == "mace_off24m"
    assert decision.was_fallback is False
    assert decision.fallback_reason is None
    assert decision.execution_tier == "gpu"


def test_router_mace_fallback_to_xtb_when_no_gpu_and_no_avx512() -> None:
    """
    Test fallback router: MACE-OFF24m -> g-xTB when GPU is absent and CPU lacks AVX-512.
    Adheres strictly to Method Matrix prompt constraint.
    """
    hw = HardwareProfileSpec(
        cpu_count=8,
        physical_cores=4,
        gpu_count=0,
        gpu_vram_gb=0.0,
        has_avx512=False,
        has_avx2=False,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("mace_off24m", hardware=hw, task_type=TaskType.CPU_BOUND)

    # Traverses: mace_off24m (fails: no GPU/no AVX512) -> aimnet2 (fails: no GPU/no AVX2) -> g-xtb (passes)
    assert decision.selected_engine == "g-xtb"
    assert decision.was_fallback is True
    assert decision.fallback_reason is not None
    assert decision.execution_tier == "cpu"


def test_router_mace_cpu_avx512_supported() -> None:
    """Test that MACE-OFF24m can execute on CPU if AVX-512 and >=8GB RAM are present."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        memory_total_gb=32.0,
        memory_available_gb=16.0,
        gpu_count=0,
        has_avx512=True,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("mace_off24m", hardware=hw, task_type=TaskType.CPU_BOUND)

    assert decision.selected_engine == "mace_off24m"
    assert decision.was_fallback is False
    assert decision.execution_tier == "cpu"


def test_router_aimnet2_vram_exhausted_fallback_to_xtb() -> None:
    """Test that AIMNet2 falls back to g-xTB if GPU VRAM is < 2.0GB and AVX2 missing."""
    hw = HardwareProfileSpec(
        gpu_count=1,
        gpu_vram_gb=1.0,  # Insufficient VRAM
        has_avx2=False,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("aimnet2", hardware=hw)

    assert decision.selected_engine == "g-xtb"
    assert decision.was_fallback is True


def test_router_gpu4pyscf_crossover_fallback() -> None:
    """
    Test Method Matrix §8.3 crossover rule: gpu4pyscf on < 50 basis functions
    falls back to CPU PySCF because CPU is faster for small systems.
    """
    hw = HardwareProfileSpec(
        gpu_count=1,
        gpu_vram_gb=12.0,
        has_cuda=True,
    )
    router = DynamicFallbackRouter()

    # Small basis (<50) -> Crossover triggers fallback to CPU PySCF
    decision_small = router.resolve_route(
        "gpu4pyscf",
        hardware=hw,
        task_constraints={"basis_functions": 36},
    )
    assert decision_small.selected_engine == "pyscf"
    assert decision_small.was_fallback is True
    assert "crossover" in (decision_small.fallback_reason or "").lower()

    # Large basis (>=50) -> GPU4PySCF is kept
    decision_large = router.resolve_route(
        "gpu4pyscf",
        hardware=hw,
        task_constraints={"basis_functions": 120},
    )
    assert decision_large.selected_engine == "gpu4pyscf"
    assert decision_large.was_fallback is False


def test_router_dlpno_ccsd_t_insufficient_ram_fallback() -> None:
    """Test that DLPNO-CCSD(T) falls back to wB97M-V when RAM < 16GB."""
    hw = HardwareProfileSpec(
        memory_total_gb=12.0,
        memory_available_gb=8.0,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("dlpno_ccsd_t", hardware=hw)

    assert decision.selected_engine == "wb97m_v_def2_qzvpp"
    assert decision.was_fallback is True


def test_router_custom_fallback_registration() -> None:
    """Test registering custom fallback rules and condition evaluators."""
    router = DynamicFallbackRouter()

    def custom_evaluator(hw: HardwareProfileSpec, constraints: Dict[str, Any]) -> Tuple[bool, str | None]:
        if constraints.get("secret_flag"):
            return True, None
        return False, "Custom evaluation failed due to missing secret_flag."

    router.register_custom_fallback(
        engine="custom_engine",
        fallback_chain=["custom_engine", "backup_engine"],
        condition_evaluator=custom_evaluator,
    )

    hw = HardwareProfileSpec()

    # Without flag -> falls back
    d1 = router.resolve_route("custom_engine", hardware=hw, task_constraints={})
    assert d1.selected_engine == "backup_engine"
    assert d1.was_fallback is True

    # With flag -> passes
    d2 = router.resolve_route("custom_engine", hardware=hw, task_constraints={"secret_flag": True})
    assert d2.selected_engine == "custom_engine"
    assert d2.was_fallback is False


def test_router_with_silo_verifier_manifest(tmp_path: Path) -> None:
    """Test router auto-swapping to next available engine in silo manifest."""
    xtb_exe = tmp_path / "xtb.bat" if platform.system() == "Windows" else tmp_path / "xtb"
    xtb_exe.write_text("echo xtb", encoding="utf-8")
    if platform.system() != "Windows":
        xtb_exe.chmod(xtb_exe.stat().st_mode | stat.S_IXUSR)

    # Manifest where MACE and AIMNet2 are missing, but xTB is installed
    manifest = {
        "mace_off24m": str(tmp_path / "missing_mace"),
        "aimnet2": str(tmp_path / "missing_aimnet2"),
        "g-xtb": str(xtb_exe),
    }
    verifier = MicroSiloVerifier(custom_manifest=manifest)
    router = DynamicFallbackRouter()

    hw = HardwareProfileSpec(gpu_count=1, gpu_vram_gb=16.0)

    # Even though GPU is capable of MACE, binary verifier finds only g-xtb in manifest
    decision = router.resolve_route("mace_off24m", hardware=hw, silo_verifier=verifier)
    assert decision.selected_engine == "g-xtb"
    assert decision.was_fallback is True
    assert decision.binary_path == str(xtb_exe.resolve())


# =============================================================================
# 8. ASYNCHRONOUS TEMPLATER
# =============================================================================


def test_async_templater_variable_interpolation() -> None:
    """Test variable interpolation with filters and defaults."""
    async def _test() -> None:
        templater = AsyncTemplateRenderer()
        template = "Job: {{ job_name | upper }}, Method: {{ method.name | lower }}, Threads: {{ threads | default('4') }}"
        context = {
            "job_name": "water_opt",
            "method": {"name": "WB97M-V"},
            "threads": "",
        }
        rendered = await templater.render_async(template, context)
        assert rendered == "Job: WATER_OPT, Method: wb97m-v, Threads: 4"

    asyncio.run(_test())


def test_async_templater_conditional_blocks() -> None:
    """Test {% if %}...{% else %}...{% endif %} template blocks."""
    async def _test() -> None:
        templater = AsyncTemplateRenderer()
        template = """
{% if is_gpu %}
# GPU Configuration Active
export CUDA_VISIBLE_DEVICES={{ gpu_id }}
{% else %}
# CPU Configuration Active
export OMP_NUM_THREADS={{ cpus }}
{% endif %}
"""
        # Test True branch
        res_gpu = await templater.render_async(template, {"is_gpu": True, "gpu_id": "0", "cpus": "8"})
        assert "GPU Configuration Active" in res_gpu
        assert "export CUDA_VISIBLE_DEVICES=0" in res_gpu
        assert "CPU Configuration Active" not in res_gpu

        # Test False branch
        res_cpu = await templater.render_async(template, {"is_gpu": False, "gpu_id": "0", "cpus": "8"})
        assert "CPU Configuration Active" in res_cpu
        assert "export OMP_NUM_THREADS=8" in res_cpu
        assert "GPU Configuration Active" not in res_cpu

    asyncio.run(_test())


def test_async_templater_render_file(tmp_path: Path) -> None:
    """Test rendering template from disk and writing output file asynchronously."""
    async def _test() -> None:
        templater = AsyncTemplateRenderer()
        tpl_file = tmp_path / "job.template.sh"
        out_file = tmp_path / "output_script.sh"

        tpl_file.write_text("#!/bin/bash\n# Job: {{ job_id }}\nrun_cmd {{ engine }}\n", encoding="utf-8")

        rendered = await templater.render_file_async(
            template_path=tpl_file,
            context={"job_id": "job_42", "engine": "orca"},
            output_path=out_file,
        )

        assert "Job: job_42" in rendered
        assert "run_cmd orca" in rendered
        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == rendered

    asyncio.run(_test())


def test_async_templater_built_in_orca_deck() -> None:
    """Test built-in ORCA input deck generator."""
    xyz_coords = "O 0.0 0.0 0.0\nH 0.0 0.75 0.58\nH 0.0 -0.75 0.58"
    deck = AsyncTemplateRenderer.build_orca_input_template(
        method="wB97M-V",
        basis="def2-QZVPP",
        charge=0,
        multiplicity=1,
        nprocs=7,
        maxcore_mb=3400,
        extra_keywords="TightOpt TightSCF DEFGRID3",
        coordinates_xyz=xyz_coords,
    )

    assert "! wB97M-V def2-QZVPP TightOpt TightSCF DEFGRID3" in deck
    assert "%pal nprocs 7 end" in deck
    assert "%maxcore 3400" in deck
    assert "* xyz 0 1" in deck
    assert "O 0.0 0.0 0.0" in deck


# =============================================================================
# 9. EXECUTION HANDSHAKE MANAGER
# =============================================================================


def test_handshake_manager_generate_and_verify_valid_token() -> None:
    """Test cryptographic token generation and successful signature verification."""
    manager = ExecutionHandshakeManager(secret_key="secret_test_key_2026")
    payload = {"basis": "def2-TZVPP", "method": "B3LYP", "n_atoms": 12}

    token = manager.generate_handshake_token(job_id="job_001", config_payload=payload, ttl_seconds=300)

    assert token.job_id == "job_001"
    assert len(token.config_hash) == 64
    assert len(token.signature) == 64
    assert token.expires_at > token.issued_at

    # Verify token
    result = manager.verify_handshake_token(token, config_payload=payload)
    assert result.is_valid is True
    assert result.signature_valid is True
    assert result.hash_valid is True
    assert result.expired is False


def test_handshake_manager_tampered_payload_fails() -> None:
    """Test that modifying payload after token generation causes hash mismatch failure."""
    manager = ExecutionHandshakeManager(secret_key="secret_test_key_2026")
    original_payload = {"basis": "def2-TZVPP", "method": "B3LYP"}
    tampered_payload = {"basis": "def2-SVP", "method": "B3LYP"}

    token = manager.generate_handshake_token(job_id="job_002", config_payload=original_payload)

    result = manager.verify_handshake_token(token, config_payload=tampered_payload)
    assert result.is_valid is False
    assert result.hash_valid is False
    assert "hash mismatch" in (result.reason or "").lower()


def test_handshake_manager_tampered_signature_fails() -> None:
    """Test that modifying the signature string causes signature verification failure."""
    manager = ExecutionHandshakeManager(secret_key="secret_test_key_2026")
    payload = {"charge": 0, "spin": 1}

    token = manager.generate_handshake_token(job_id="job_003", config_payload=payload)

    # Invalidate signature
    tampered_token = token.model_copy(update={"signature": "a" * 64})

    result = manager.verify_handshake_token(tampered_token, config_payload=payload)
    assert result.is_valid is False
    assert result.signature_valid is False
    assert "hmac signature verification failed" in (result.reason or "").lower()


def test_handshake_manager_expired_token_fails() -> None:
    """Test that expired tokens fail verification."""
    manager = ExecutionHandshakeManager(secret_key="secret_test_key_2026")
    payload = {"opt": True}

    # Generate token that expired 10 seconds ago
    token = manager.generate_handshake_token(job_id="job_004", config_payload=payload, ttl_seconds=-10)

    result = manager.verify_handshake_token(token, config_payload=payload)
    assert result.is_valid is False
    assert result.expired is True
    assert "expired" in (result.reason or "").lower()


def test_handshake_manager_async_session() -> None:
    """Test end-to-end async execution handshake session."""
    async def _test() -> None:
        manager = ExecutionHandshakeManager(secret_key="session_secret")
        payload = {"job": "benchmark_1"}

        async def runner_callback(token: HandshakeToken) -> Dict[str, Any]:
            assert token.job_id == "session_job_1"
            return {"status": "SUCCESS", "exit_code": 0, "energy": -123.456}

        session_result = await manager.execute_handshake_session(
            job_id="session_job_1",
            config_payload=payload,
            runner_callback=runner_callback,
        )

        assert session_result["status"] == "SUCCESS"
        assert session_result["exit_code"] == 0
        assert session_result["handshake_verification"]["is_valid"] is True

    asyncio.run(_test())


# =============================================================================
# 10. CONFIG COMPILER INTEGRATION & END-TO-END BUNDLE COMPILATION
# =============================================================================


def test_config_compiler_legacy_execution_package() -> None:
    """Test backward-compatible generate_execution_package method."""
    compiler = ConfigCompiler(target_scheduler="slurm", walltime="12:00:00", partition="gpu")
    params = {"method": "r2scan-3c", "basis": "def2-mTZVP", "charge": 0}

    config_hash, full_script = compiler.generate_execution_package(
        job_name="test_legacy_job",
        engine_command="orca test.inp",
        params=params,
        nodes=1,
        cpus=8,
        walltime="06:00:00",
        partition="fast",
    )

    assert len(config_hash) == 64
    assert f"# COCHEM_EXEC_HASH: {config_hash}" in full_script
    assert "#SBATCH --job-name=test_legacy_job" in full_script
    assert "#SBATCH --time=06:00:00" in full_script
    assert "srun --mpi=pmi2 orca test.inp" in full_script


def test_config_compiler_compile_execution_bundle_synchronous() -> None:
    """Test full synchronous compile_execution_bundle."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        p_cores=8,
        e_cores=0,
        memory_total_gb=32.0,
        memory_available_gb=24.0,
        gpu_count=1,
        gpu_vram_gb=16.0,
        gpu_device_ids=[0],
    )
    compiler = ConfigCompiler(target_scheduler="local", hardware_profile=hw)
    params = {"method": "mace_off24m", "geometry": "water.xyz"}

    bundle = compiler.compile_execution_bundle(
        job_name="bundle_job_1",
        requested_engine="mace_off24m",
        params=params,
        task_type=TaskType.GPU_MLFF,
    )

    assert isinstance(bundle, CompiledJobBundle)
    assert bundle.job_name == "bundle_job_1"
    assert len(bundle.config_hash) == 64
    assert bundle.route_decision.selected_engine == "mace_off24m"
    assert bundle.route_decision.execution_tier == "gpu"
    assert bundle.handshake_token.job_id == "bundle_job_1"
    assert f"# COCHEM_EXEC_HASH: {bundle.config_hash}" in bundle.provenance_header
    assert "export CUDA_VISIBLE_DEVICES=0" in bundle.submission_script


def test_config_compiler_compile_job_async() -> None:
    """Test full asynchronous compile_job_async with template rendering."""
    async def _test() -> None:
        hw = HardwareProfileSpec(
            cpu_count=16,
            physical_cores=8,
            memory_total_gb=32.0,
            memory_available_gb=24.0,
            gpu_count=0,
        )
        compiler = ConfigCompiler(target_scheduler="slurm", hardware_profile=hw)

        deck_template = """! {{ method }} {{ basis }} TightOpt
%pal nprocs {{ nprocs }} end
* xyz 0 1
O 0 0 0
H 0 1 0
H 0 0 1
*
"""
        params = {"method": "wB97M-V", "basis": "def2-TZVPP"}

        bundle = await compiler.compile_job_async(
            job_name="async_bundle_job",
            requested_engine="orca",
            params=params,
            task_type=TaskType.CPU_BOUND,
            input_deck_template=deck_template,
            deck_context={"method": "wB97M-V", "basis": "def2-TZVPP", "nprocs": 8},
        )

        assert isinstance(bundle, CompiledJobBundle)
        assert bundle.input_deck is not None
        assert "! wB97M-V def2-TZVPP TightOpt" in bundle.input_deck
        assert "%pal nprocs 8 end" in bundle.input_deck
        assert bundle.route_decision.selected_engine == "orca"
        assert bundle.route_decision.allocated_threads == 8
        assert f"# COCHEM_EXEC_HASH: {bundle.config_hash}" in bundle.submission_script

    asyncio.run(_test())


def test_micro_silo_verifier_min_version_detection_and_rejection(tmp_path: Path) -> None:
    """Test that binary version is probed and rejected if below min_version."""
    if platform.system() == "Windows":
        exe_file = tmp_path / "test_prog.bat"
        exe_file.write_text("@echo off\necho test_prog version 1.2.0\n", encoding="utf-8")
    else:
        exe_file = tmp_path / "test_prog"
        exe_file.write_text("#!/bin/sh\necho 'test_prog version 1.2.0'\n", encoding="utf-8")
        exe_file.chmod(exe_file.stat().st_mode | stat.S_IXUSR)

    verifier = MicroSiloVerifier()

    # Pass when min_version <= 1.2.0
    res_pass = verifier.verify_binary("test_prog", candidate_path=exe_file, min_version="1.0.0")
    assert res_pass.is_valid is True
    assert res_pass.version == "1.2.0"

    # Fail when min_version > 1.2.0
    res_fail = verifier.verify_binary("test_prog", candidate_path=exe_file, min_version="2.0.0")
    assert res_fail.is_valid is False
    assert res_fail.version == "1.2.0"
    assert "below required minimum" in (res_fail.error_message or "")


def test_async_templater_dotted_if_conditional() -> None:
    """Test conditional blocks using dotted context variables."""
    async def _test() -> None:
        templater = AsyncTemplateRenderer()
        template = "{% if engine.is_gpu %}GPU_MODE{% else %}CPU_MODE{% endif %}"

        res_true = await templater.render_async(template, {"engine": {"is_gpu": True}})
        assert res_true == "GPU_MODE"

        res_false = await templater.render_async(template, {"engine": {"is_gpu": False}})
        assert res_false == "CPU_MODE"

    asyncio.run(_test())


def test_handshake_manager_none_secret_key_fallback() -> None:
    """Test that ExecutionHandshakeManager works safely with None secret key."""
    mgr = ExecutionHandshakeManager(secret_key=None)
    token = mgr.generate_handshake_token("test_job", {"param": 1})
    res = mgr.verify_handshake_token(token, {"param": 1})
    assert res.is_valid is True
    assert res.signature_valid is True


def test_router_mace_low_vram_avx512_cpu_tier_env() -> None:
    """Test that MACE falling back to CPU due to low VRAM gets proper CPU environment."""
    hw = HardwareProfileSpec(
        cpu_count=16,
        physical_cores=8,
        p_cores=8,
        e_cores=0,
        memory_total_gb=32.0,
        memory_available_gb=16.0,
        gpu_count=1,
        gpu_vram_gb=2.0,  # Below 4.0GB requirement
        has_avx512=True,
    )
    router = DynamicFallbackRouter()
    decision = router.resolve_route("mace_off24m", hardware=hw, task_type=TaskType.GPU_MLFF)

    assert decision.selected_engine == "mace_off24m"
    # CUDA_VISIBLE_DEVICES should be disabled because GPU VRAM was inadequate
    assert decision.environment_variables["CUDA_VISIBLE_DEVICES"] == ""
    assert decision.execution_tier == "cpu"

