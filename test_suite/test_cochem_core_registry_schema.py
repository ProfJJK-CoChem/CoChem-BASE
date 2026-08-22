"""
CoChem-BASE Stage 0.0: Golden Registry Schema Gatekeeper Test Suite.
Strict Zero-Mock Mandate: Real physical file I/O, deterministic SHA-256 hashing,
and rigorous Pydantic V2 model validations across POSIX and Windows platforms.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CoChemSystemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    GPUComputeSchema,
    HardwareConfig,
    HardwareSchema,
    HPCConfig,
    MPSConfig,
    OSTarget,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
    SiloPathsSchema,
    discover_engine,
    discover_host_hardware,
    validate_system_config,
)


# =============================================================================
# 1. HARDWARE SCHEMA & HARDWARE CONFIG TESTS
# =============================================================================

def test_hardware_schema_alias():
    """Verify that HardwareConfig is a direct alias of HardwareSchema."""
    assert HardwareConfig is HardwareSchema


def test_hardware_schema_valid_defaults():
    """Test HardwareSchema with valid required bounds."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target=OSTarget.LINUX_X86_64,
    )
    assert hw.physical_cpu_cores == 8
    assert hw.logical_cpu_cores == 16
    assert hw.cpu_cores == 8
    assert hw.ram_gb == 32.0
    assert hw.ram_mb == 32768
    assert hw.maxcore_mb == 3000
    assert hw.avx512_support is False
    assert hw.gpu_profile == "None"
    assert hw.vram_gb == 0.0
    assert hw.subnormal_precision_trap is False
    assert hw.os_target == "linux_x86_64"
    assert hw.host_id is None
    assert isinstance(hw.mps, MPSConfig)
    assert isinstance(hw.core_pinning, CorePinningConfig)
    assert isinstance(hw.gpu, GPUComputeSchema)


def test_hardware_schema_flex_validation():
    """Test flex validation: auto-populating cpu_cores, ram_mb, ram_gb, and gpu fields."""
    # Case 1: physical_cpu_cores provided, cpu_cores missing -> cpu_cores populated
    # ram_gb provided, ram_mb missing -> ram_mb computed
    hw1 = HardwareSchema(
        physical_cpu_cores=12,
        logical_cpu_cores=24,
        ram_gb=64.0,
        os_target="windows_x86_64",
    )
    assert hw1.cpu_cores == 12
    assert hw1.ram_mb == 65536

    # Case 2: cpu_cores provided, physical_cpu_cores missing -> physical_cpu_cores populated
    # ram_mb provided, ram_gb missing -> ram_gb computed
    hw2 = HardwareSchema(
        cpu_cores=16,
        logical_cpu_cores=32,
        ram_mb=32768,
        os_target="linux_x86_64",
    )
    assert hw2.physical_cpu_cores == 16
    assert hw2.ram_gb == 32.0

    # Case 3: String representation of numbers coerced properly
    hw3 = HardwareSchema(
        physical_cpu_cores="4",  # type: ignore
        logical_cpu_cores="8",  # type: ignore
        ram_gb="16.5",  # type: ignore
        vram_gb="8.0",  # type: ignore
        os_target="darwin_arm64",
    )
    assert hw3.physical_cpu_cores == 4
    assert hw3.logical_cpu_cores == 8
    assert hw3.ram_gb == 16.5
    assert hw3.ram_mb == int(16.5 * 1024)
    assert hw3.vram_gb == 8.0
    assert hw3.gpu.vram_gb == 8.0


def test_hardware_schema_gpu_compute_metrics():
    """Test hardware schema with explicit GPUCompute metrics and custom attributes."""
    gpu_custom = GPUComputeSchema(
        gpu_profile="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_count=2,
        compute_capability="8.9",
        fp64_capable=False,
        subnormal_precision_trap=True,
        mps_enabled=True,
    )
    hw = HardwareSchema(
        physical_cpu_cores=16,
        logical_cpu_cores=32,
        ram_gb=128.0,
        gpu_profile="NVIDIA RTX 4090",
        vram_gb=24.0,
        subnormal_precision_trap=True,
        os_target="linux_x86_64",
        gpu=gpu_custom,
    )
    assert hw.gpu.gpu_profile == "NVIDIA RTX 4090"
    assert hw.gpu.vram_gb == 24.0
    assert hw.gpu.device_count == 2
    assert hw.gpu.compute_capability == "8.9"
    assert hw.gpu.fp64_capable is False
    assert hw.gpu.subnormal_precision_trap is True
    assert hw.gpu.mps_enabled is True


def test_hardware_schema_negative_bounds():
    """Negative tests for invalid CPU, RAM, and VRAM bounds."""
    # Zero or negative physical CPU cores
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=0, logical_cpu_cores=8, ram_gb=16.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=-4, logical_cpu_cores=8, ram_gb=16.0, os_target="linux_x86_64")

    # Zero or negative logical CPU cores
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=0, ram_gb=16.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=-8, ram_gb=16.0, os_target="linux_x86_64")

    # Zero or negative RAM
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=0.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=-16.0, os_target="linux_x86_64")

    # Negative VRAM
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=16.0, vram_gb=-1.0, os_target="linux_x86_64")

    # Invalid OS target
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=16.0, os_target="NonExistentOS_999")


# =============================================================================
# 2. ENVIRONMENT SCHEMA & OS TARGET TESTS
# =============================================================================

def test_ostarget_enum():
    """Test OSTarget enum integrity."""
    assert OSTarget.LINUX_X86_64.value == "linux_x86_64"
    assert OSTarget.LINUX_AARCH64.value == "linux_aarch64"
    assert OSTarget.WINDOWS_X86_64.value == "windows_x86_64"
    assert OSTarget.WINDOWS_AMD64.value == "windows_amd64"
    assert OSTarget.DARWIN_ARM64.value == "darwin_arm64"
    assert OSTarget.DARWIN_X86_64.value == "darwin_x86_64"
    assert OSTarget.GENERIC_POSIX.value == "posix"
    assert OSTarget.GENERIC_NT.value == "nt"


def test_environment_schema_defaults_and_custom(tmp_path: Path):
    """Test EnvironmentSchema defaults and custom path expansion."""
    env = EnvironmentSchema()
    assert isinstance(env.os_target, str)
    assert env.codata_version == "2018"
    assert env.isotopic_mass_locking is True
    assert isinstance(env.artifacts_dir, (str, Path))
    assert env.strict_path_resolution is False

    custom_artifacts = str(tmp_path / "artifacts")
    custom_scratch = str(tmp_path / "scratch")
    env_custom = EnvironmentSchema(
        os_target=OSTarget.WINDOWS_AMD64,
        artifacts_dir=custom_artifacts,
        scratch_dir=custom_scratch,
        codata_version="2022",
        isotopic_mass_locking=True,
        env_vars={"COCHEM_NUM_THREADS": "8", "OMP_STACKSIZE": "64M"},
        strict_path_resolution=True,
    )
    assert env_custom.os_target == "windows_amd64"
    assert env_custom.codata_version == "2022"
    assert env_custom.artifacts_dir == custom_artifacts
    assert env_custom.scratch_dir == custom_scratch
    assert env_custom.env_vars["COCHEM_NUM_THREADS"] == "8"
    assert env_custom.strict_path_resolution is True


def test_environment_schema_path_expansion_and_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test environment variable expansion and cross-platform path resolution."""
    test_dir = tmp_path / "cochem_test_env_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_TEST_VAR", str(test_dir))

    env = EnvironmentSchema(
        artifacts_dir="$COCHEM_TEST_VAR/artifacts" if os.name != "nt" else "%COCHEM_TEST_VAR%\\artifacts",
        scratch_dir="$COCHEM_TEST_VAR/scratch" if os.name != "nt" else "%COCHEM_TEST_VAR%\\scratch",
    )
    assert str(test_dir) in str(env.artifacts_dir)
    assert str(test_dir) in str(env.scratch_dir)

    # Path resolution
    resolved = env.resolve_path(str(test_dir / "subfile.txt"))
    assert resolved.name == "subfile.txt"
    assert resolved.parent == test_dir

    # Strict path resolution on relative path
    env_strict = EnvironmentSchema(strict_path_resolution=True)
    with pytest.raises(ValueError, match="Strict path resolution enabled"):
        env_strict.resolve_path("relative/path/not/absolute.txt")

    # Empty path resolution rejection
    with pytest.raises(ValueError, match="Cannot resolve empty path"):
        env.resolve_path("")


def test_environment_schema_negative_validations():
    """Negative tests for invalid CODATA versions and OS targets."""
    with pytest.raises(ValidationError, match="codata_version must be one of"):
        EnvironmentSchema(codata_version="1998")

    with pytest.raises(ValidationError, match="codata_version must be one of"):
        EnvironmentSchema(codata_version="2035")

    with pytest.raises(ValidationError, match="Invalid OS target"):
        EnvironmentSchema(os_target="AmigaOS_68k")


# =============================================================================
# 3. SILO PATHS SCHEMA TESTS
# =============================================================================

def test_silo_paths_schema_operations(tmp_path: Path):
    """Test SiloPathsSchema path resolution, bypass tokens, and status checks."""
    # Create real physical binary file for testing
    real_orca = tmp_path / ("orca.exe" if sys.platform == "win32" else "orca")
    real_orca.write_text("#!/bin/sh\necho orca\n", encoding="utf-8")

    silo_paths = SiloPathsSchema(
        orca_path=str(real_orca),
        xtb_path="BYPASSED",
        mpirun_path="missing",
        cfour_path="Not_Found",
        python_path=sys.executable,
        silo_root=str(tmp_path),
        strict_resolution=False,
    )

    # Bypass check
    assert silo_paths.is_bypassed("xtb") is True
    assert silo_paths.is_bypassed("orca") is False
    assert silo_paths.is_bypassed("cfour") is False

    # Found check
    assert silo_paths.is_found("orca") is True
    assert silo_paths.is_found("xtb") is False
    assert silo_paths.is_found("mpirun") is False
    assert silo_paths.is_found("cfour") is False
    assert silo_paths.is_found("python") is True

    # Path resolution
    assert silo_paths.resolve_binary("orca") == str(real_orca.resolve())
    assert silo_paths.resolve_binary("xtb") == "BYPASSED"
    assert silo_paths.resolve_binary("cfour") == "Not_Found"

    # Unknown binary name raises AttributeError
    with pytest.raises(AttributeError):
        silo_paths.resolve_binary("unknown_engine_binary")


def test_silo_paths_schema_strict_resolution(tmp_path: Path):
    """Test SiloPathsSchema strict resolution mode rejecting missing binaries."""
    non_existent = tmp_path / "non_existent_binary"
    silo_strict = SiloPathsSchema(
        orca_path=str(non_existent),
        strict_resolution=True,
    )
    with pytest.raises(FileNotFoundError, match="Binary 'orca' not found"):
        silo_strict.resolve_binary("orca")


# =============================================================================
# 4. COCHEM SYSTEM CONFIG & GATEKEEPER TESTS
# =============================================================================

def test_cochem_system_config_alias():
    """Verify CoChemConfig is an alias of CoChemSystemConfig."""
    assert CoChemConfig is CoChemSystemConfig


def test_cochem_system_config_lifecycle(tmp_path: Path):
    """Test full serialization, deserialization, file I/O, and defaults."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    env = EnvironmentSchema(
        os_target="linux_x86_64",
        codata_version="2018",
    )
    config = CoChemSystemConfig(
        hardware=hw,
        environment=env,
        engines={
            "orca": {"status": "found", "path": "/opt/orca/orca", "version": "6.1.1", "hash": "abc123"}
        },
        quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
        hpc=HPCConfig(scheduler="slurm", default_partition="gpu-node", max_walltime_hours=12),
    )

    # to_dict
    d = config.to_dict()
    assert d["schema_version"] == "4.0.0"
    assert d["hardware"]["physical_cpu_cores"] == 8
    assert d["quantum_settings"]["implicit_solvation"] == "CPCM"
    assert d["hpc"]["scheduler"] == "slurm"

    # to_json and from_json
    json_str = config.to_json()
    assert isinstance(json_str, str)
    restored = CoChemSystemConfig.from_json(json_str)
    assert restored.schema_version == config.schema_version
    assert restored.hardware.physical_cpu_cores == 8
    assert restored.quantum_settings.implicit_solvation == "CPCM"
    assert restored.hpc.scheduler == "slurm"

    # to_file and from_file
    config_path = tmp_path / "sub" / "cochem_system_config.json"
    config.to_file(config_path)
    assert config_path.exists()
    loaded = CoChemSystemConfig.from_file(config_path)
    assert loaded.hardware.ram_gb == 32.0
    assert loaded.environment.codata_version == "2018"

    # create_default
    default_cfg = CoChemSystemConfig.create_default(auto_detect_hardware=False)
    assert default_cfg.hardware.physical_cpu_cores == 4
    assert default_cfg.quantum_settings.integration_grid == "defgrid2"
    assert default_cfg.silos.torq_silo_active is True


def test_checksum_calculation_and_verification():
    """Verify cryptographic SHA-256 checksum calculation, update, and tamper detection."""
    hw = HardwareSchema(
        physical_cpu_cores=4,
        logical_cpu_cores=8,
        ram_gb=16.0,
        os_target="windows_x86_64",
    )
    config = CoChemSystemConfig(hardware=hw)

    # Initial state has no checksum
    assert config.registry_checksum == ""
    assert config.verify_checksum() is False

    # Compute checksum
    cs1 = config.compute_checksum()
    assert isinstance(cs1, str)
    assert len(cs1) == 64  # SHA-256 is 64 hex chars
    assert all(c in "0123456789abcdef" for c in cs1)

    # Checksum is deterministic
    cs2 = config.compute_checksum()
    assert cs1 == cs2

    # Invariance to last_updated timestamp
    config.last_updated = "2026-08-21T00:00:00+00:00"
    assert config.compute_checksum() == cs1

    # Update checksum in place
    updated_cs = config.update_checksum()
    assert updated_cs == cs1
    assert config.registry_checksum == cs1
    assert config.verify_checksum() is True

    # Tampering with payload invalidates checksum
    config.hardware.ram_gb = 64.0
    assert config.verify_checksum() is False

    # Re-updating restores verification
    new_cs = config.update_checksum()
    assert new_cs != cs1
    assert config.verify_checksum() is True


def test_gatekeeper_validate_system_config(tmp_path: Path):
    """Test gatekeeper validate_system_config with various source formats."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    cfg_inst = CoChemSystemConfig(hardware=hw)

    # Source: CoChemSystemConfig instance
    res1 = validate_system_config(cfg_inst)
    assert res1 is cfg_inst

    # Source: Python Dict
    raw_dict = cfg_inst.to_dict()
    res2 = validate_system_config(raw_dict)
    assert res2.hardware.physical_cpu_cores == 8

    # Source: Path object
    file_path = tmp_path / "valid_config.json"
    cfg_inst.to_file(file_path)
    res3 = validate_system_config(file_path)
    assert res3.hardware.ram_gb == 32.0

    # Source: String path
    res4 = validate_system_config(str(file_path))
    assert res4.hardware.logical_cpu_cores == 16

    # Source: JSON string payload
    json_str = cfg_inst.to_json()
    res5 = validate_system_config(json_str)
    assert res5.hardware.os_target == "linux_x86_64"

    # Unsupported types raise TypeError
    with pytest.raises(TypeError, match="Unsupported configuration source type"):
        validate_system_config(98765)  # type: ignore
    with pytest.raises(TypeError, match="Unsupported configuration source type"):
        validate_system_config(["invalid", "list"])  # type: ignore


# =============================================================================
# 5. HELPER SUB-MODELS TESTS
# =============================================================================

def test_mps_config_comprehensive():
    """Verify MPSConfig default, custom, and negative parameter validations."""
    cfg = MPSConfig()
    assert cfg.enabled is True
    assert cfg.max_workers == 4
    assert cfg.thread_percentage == 25
    assert isinstance(cfg.pipe_dir, str)
    assert isinstance(cfg.log_dir, str)

    custom = MPSConfig(
        enabled=False,
        max_workers=8,
        thread_percentage=50,
        pipe_dir="/tmp/custom_pipe",
        log_dir="/tmp/custom_log",
    )
    assert custom.enabled is False
    assert custom.max_workers == 8
    assert custom.thread_percentage == 50
    assert custom.pipe_dir == "/tmp/custom_pipe"
    assert custom.log_dir == "/tmp/custom_log"

    # Negative: max_workers <= 0
    with pytest.raises(ValidationError):
        MPSConfig(max_workers=0)
    with pytest.raises(ValidationError):
        MPSConfig(max_workers=-4)

    # Negative: thread_percentage < 1 or > 100
    with pytest.raises(ValidationError):
        MPSConfig(thread_percentage=0)
    with pytest.raises(ValidationError):
        MPSConfig(thread_percentage=101)


def test_core_pinning_config_comprehensive():
    """Verify CorePinningConfig default, custom, and negative parameter validations."""
    cfg = CorePinningConfig()
    assert cfg.kmp_hw_subset == "8c:intel_core,1t"
    assert cfg.anchor_p_cores == 7
    assert cfg.scout_p_cores == 1
    assert cfg.background_e_cores == 8

    custom = CorePinningConfig(
        kmp_hw_subset="16c:intel_core,1t",
        anchor_p_cores=14,
        scout_p_cores=2,
        background_e_cores=16,
    )
    assert custom.anchor_p_cores == 14
    assert custom.scout_p_cores == 2
    assert custom.background_e_cores == 16

    # Negative: core counts < 0
    with pytest.raises(ValidationError):
        CorePinningConfig(anchor_p_cores=-1)
    with pytest.raises(ValidationError):
        CorePinningConfig(scout_p_cores=-1)
    with pytest.raises(ValidationError):
        CorePinningConfig(background_e_cores=-1)


def test_quantum_settings_comprehensive():
    """Verify QuantumSettings solvation models, integration grids, and negative cases."""
    # Case normalization
    qs1 = QuantumSettings(implicit_solvation="cpcm", integration_grid="DEFGRID2", charge=-1, multiplicity=2)
    assert qs1.implicit_solvation == "CPCM"
    assert qs1.integration_grid == "defgrid2"
    assert qs1.charge == -1
    assert qs1.multiplicity == 2

    qs2 = QuantumSettings(implicit_solvation="SMD", integration_grid="defgrid3")
    assert qs2.implicit_solvation == "SMD"
    assert qs2.integration_grid == "defgrid3"

    # Missing data / empty string to None
    qs3 = QuantumSettings(implicit_solvation="[MISSING DATA]", integration_grid="")
    assert qs3.implicit_solvation is None
    assert qs3.integration_grid is None

    # Negative: invalid solvation model
    with pytest.raises(ValidationError, match="implicit_solvation must be 'CPCM' or 'SMD'"):
        QuantumSettings(implicit_solvation="COSMO")
    with pytest.raises(ValidationError, match="implicit_solvation must be 'CPCM' or 'SMD'"):
        QuantumSettings(implicit_solvation="IEFPCM")

    # Negative: invalid integration grid
    with pytest.raises(ValidationError, match="integration_grid must be one of"):
        QuantumSettings(integration_grid="ultrafine")
    with pytest.raises(ValidationError, match="integration_grid must be one of"):
        QuantumSettings(integration_grid="grid99")

    # Negative: multiplicity < 1
    with pytest.raises(ValidationError):
        QuantumSettings(multiplicity=0)
    with pytest.raises(ValidationError):
        QuantumSettings(multiplicity=-1)


def test_engine_info_and_engine_paths():
    """Verify EngineInfo and EnginePaths sub-models."""
    info_orca = EngineInfo(status="found", path="/opt/orca/orca", version="6.1.1", hash="sha256_hash_123")
    assert info_orca.status == "found"
    assert info_orca.path == "/opt/orca/orca"
    assert info_orca.version == "6.1.1"
    assert info_orca.hash == "sha256_hash_123"

    info_xtb = EngineInfo(status="bypassed", path="BYPASSED")
    assert info_xtb.status == "bypassed"
    assert info_xtb.path == "BYPASSED"

    info_mpirun = EngineInfo(status="missing", path=None)
    assert info_mpirun.status == "missing"
    assert info_mpirun.path is None

    paths = EnginePaths(
        orca=info_orca,
        xtb=info_xtb,
        mpirun=info_mpirun,
    )
    assert paths.orca.version == "6.1.1"
    assert paths.xtb.path == "BYPASSED"
    assert paths.mpirun.status == "missing"
    assert paths.cfour is None


def test_routing_policy_comprehensive():
    """Verify RoutingPolicy bounds and defaults."""
    rp = RoutingPolicy()
    assert rp.max_concurrent_mace_threads == 4
    assert rp.max_dft_basis_functions == 2000
    assert rp.recommend_ccsdt is False
    assert rp.classification == "STANDARD"

    custom_rp = RoutingPolicy(
        max_concurrent_mace_threads=8,
        max_dft_basis_functions=5000,
        recommend_ccsdt=True,
        classification="HIGH_PERFORMANCE",
    )
    assert custom_rp.max_concurrent_mace_threads == 8
    assert custom_rp.recommend_ccsdt is True

    # Negative: threads <= 0 or basis functions <= 0
    with pytest.raises(ValidationError):
        RoutingPolicy(max_concurrent_mace_threads=0)
    with pytest.raises(ValidationError):
        RoutingPolicy(max_dft_basis_functions=-10)


def test_hpc_config_comprehensive():
    """Verify HPCConfig scheduler validation, walltimes, and budgets."""
    hpc = HPCConfig()
    assert hpc.scheduler == "local"
    assert hpc.default_partition == "compute"
    assert hpc.max_walltime_hours == 24
    assert isinstance(hpc.walltime_budgets, dict)

    slurm_hpc = HPCConfig(
        scheduler="SLURM",
        default_partition="gpu-a100",
        max_walltime_hours=48,
        partition="gpu-a100",
        cluster_hostname="hpc.cluster.org",
        username="cochem_user",
        execution_mode="batch",
        walltime_budgets={"opt": "04:00:00", "vpt2": "12:00:00"},
    )
    assert slurm_hpc.scheduler == "slurm"
    assert slurm_hpc.max_walltime_hours == 48
    assert slurm_hpc.walltime_budgets["opt"] == "04:00:00"

    # Schedulers: pbs, sge
    pbs_hpc = HPCConfig(scheduler="pbs")
    assert pbs_hpc.scheduler == "pbs"
    sge_hpc = HPCConfig(scheduler="sge")
    assert sge_hpc.scheduler == "sge"

    # Negative: unsupported scheduler
    with pytest.raises(ValidationError, match="Invalid HPC scheduler"):
        HPCConfig(scheduler="lsf_unsupported")

    # Negative: walltime <= 0
    with pytest.raises(ValidationError):
        HPCConfig(max_walltime_hours=0)
    with pytest.raises(ValidationError):
        HPCConfig(max_walltime_hours=-12)


def test_gpu_compute_schema_comprehensive():
    """Verify GPUComputeSchema metrics, flags, and negative bounds."""
    gpu = GPUComputeSchema()
    assert gpu.gpu_profile == "None"
    assert gpu.vram_gb == 0.0
    assert gpu.device_count == 0
    assert gpu.fp64_capable is False
    assert gpu.subnormal_precision_trap is False
    assert gpu.mps_enabled is False

    custom_gpu = GPUComputeSchema(
        gpu_profile="NVIDIA A100-SXM4-80GB",
        vram_gb=80.0,
        device_count=4,
        compute_capability="8.0",
        fp64_capable=True,
        subnormal_precision_trap=False,
        mps_enabled=True,
    )
    assert custom_gpu.gpu_profile == "NVIDIA A100-SXM4-80GB"
    assert custom_gpu.vram_gb == 80.0
    assert custom_gpu.fp64_capable is True

    # Negative: vram_gb < 0, device_count < 0
    with pytest.raises(ValidationError):
        GPUComputeSchema(vram_gb=-1.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(device_count=-1)


# =============================================================================
# 6. DISCOVERY HELPERS TESTS
# =============================================================================

def test_discover_engine_physical():
    """Test discover_engine using physically present and non-existent binaries."""
    # Real physical binary: python interpreter must be found
    py_engine = discover_engine("python" if sys.platform != "win32" else "python.exe")
    assert py_engine.status == "found"
    assert py_engine.path is not None
    assert Path(py_engine.path).exists()

    # Non-existent binary must be missing
    missing_engine = discover_engine("non_existent_binary_xyz_12345_never_installed")
    assert missing_engine.status == "missing"
    assert missing_engine.path is None


def test_engine_info_status_validation():
    """Negative tests for invalid EngineInfo status strings."""
    with pytest.raises(ValidationError, match="Invalid engine status"):
        EngineInfo(status="MALICIOUS_INJECTED_STATUS")

    with pytest.raises(ValidationError, match="Invalid engine status"):
        EngineInfo(status="running")


def test_discover_host_hardware_physical():
    """Test discover_host_hardware retrieving physical CPU and RAM."""
    hw = discover_host_hardware()
    assert isinstance(hw, HardwareSchema)
    assert hw.physical_cpu_cores >= 1
    assert hw.logical_cpu_cores >= 1
    assert hw.ram_gb > 0.0
    assert isinstance(hw.os_target, str)
    assert len(hw.os_target) > 0
