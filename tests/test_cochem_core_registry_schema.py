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

from cochem_core_registry_schema import (
    BYPASS_TOKENS,
    CARBON_13_ISOTOPIC_MASS,
    ISOTOPIC_MASSES,
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
# 1. GLOBAL SCHEMA CONSTRAINTS: EXTRA FORBIDDEN & VALIDATE ASSIGNMENT
# =============================================================================

def test_global_schema_constraints_extra_fields_forbidden():
    """Verify that all schemas strictly forbid extra/hallucinated fields."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GPUComputeSchema(gpu_profile="NVIDIA", hallucinated_field="forbidden")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MPSConfig(enabled=True, fake_field=123)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CorePinningConfig(anchor_p_cores=4, ghost_core=1)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        QuantumSettings(charge=0, invalid_flag=True)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HardwareSchema(ram_gb=16.0, cpu_physical_cores=4, invalid_hw_key="bad")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EnvironmentSchema(os_target=OSTarget.LOCAL_LINUX, hallucinated_env="bad")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SiloPathsSchema(cfour_binary_path="BYPASSED", rogue_path="/opt/rogue")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EngineInfo(status="found", bogus="data")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RoutingPolicy(max_concurrent_mace_threads=2, extra_policy="strict")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HPCConfig(scheduler="slurm", imaginary_queue="gpu_long")


def test_global_schema_constraints_validate_assignment():
    """Verify that attribute mutation on instances triggers strict Pydantic validation."""
    hw = HardwareSchema(ram_gb=32.0, cpu_physical_cores=8)
    assert hw.ram_gb == 32.0

    # Valid mutation
    hw.ram_gb = 64.0
    assert hw.ram_gb == 64.0

    # Invalid mutations must raise ValidationError
    with pytest.raises(ValidationError):
        hw.ram_gb = 0.0  # ram_gb must be > 0.0

    with pytest.raises(ValidationError):
        hw.ram_gb = -16.0

    with pytest.raises(ValidationError):
        hw.cpu_physical_cores = 0  # cpu_physical_cores must be >= 1

    with pytest.raises(ValidationError):
        hw.allocatable_compute_cores = -1  # allocatable_compute_cores must be >= 0

    gpu = GPUComputeSchema(vram_gb=12.0)
    with pytest.raises(ValidationError):
        gpu.vram_gb = -4.0

    with pytest.raises(ValidationError):
        gpu.device_count = -1


# =============================================================================
# 2. GPU COMPUTE SCHEMA TESTS
# =============================================================================

def test_gpu_compute_schema_comprehensive():
    """Verify GPUComputeSchema metrics, flags, TFLOPS, and Tensor Cores."""
    gpu_default = GPUComputeSchema()
    assert gpu_default.gpu_profile == "None"
    assert gpu_default.vram_gb == 0.0
    assert gpu_default.device_count == 0
    assert gpu_default.compute_capability is None
    assert gpu_default.fp64_capable is False
    assert gpu_default.subnormal_precision_trap is False
    assert gpu_default.mps_enabled is False
    assert gpu_default.tflops is None
    assert gpu_default.fp32_tflops is None
    assert gpu_default.fp16_tflops is None
    assert gpu_default.fp64_tflops is None
    assert gpu_default.tensor_cores is None
    assert gpu_default.memory_bandwidth_gb_s is None

    gpu_custom = GPUComputeSchema(
        gpu_profile="NVIDIA H100 SXM5 80GB",
        vram_gb=80.0,
        device_count=8,
        compute_capability="9.0",
        fp64_capable=True,
        subnormal_precision_trap=False,
        mps_enabled=True,
        tflops=67.0,
        fp32_tflops=67.0,
        fp16_tflops=1979.0,
        fp64_tflops=34.0,
        tensor_cores=528,
        memory_bandwidth_gb_s=3350.0,
    )
    assert gpu_custom.gpu_profile == "NVIDIA H100 SXM5 80GB"
    assert gpu_custom.vram_gb == 80.0
    assert gpu_custom.device_count == 8
    assert gpu_custom.compute_capability == "9.0"
    assert gpu_custom.fp64_capable is True
    assert gpu_custom.mps_enabled is True
    assert gpu_custom.tflops == 67.0
    assert gpu_custom.fp32_tflops == 67.0
    assert gpu_custom.fp16_tflops == 1979.0
    assert gpu_custom.fp64_tflops == 34.0
    assert gpu_custom.tensor_cores == 528
    assert gpu_custom.memory_bandwidth_gb_s == 3350.0


def test_gpu_compute_schema_negative_bounds():
    """Verify negative validation on GPU parameters."""
    with pytest.raises(ValidationError):
        GPUComputeSchema(vram_gb=-1.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(device_count=-1)
    with pytest.raises(ValidationError):
        GPUComputeSchema(tflops=-10.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(fp32_tflops=-5.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(fp16_tflops=-1.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(fp64_tflops=-0.1)
    with pytest.raises(ValidationError):
        GPUComputeSchema(tensor_cores=-10)
    with pytest.raises(ValidationError):
        GPUComputeSchema(memory_bandwidth_gb_s=-100.0)


# =============================================================================
# 3. HARDWARE SCHEMA & ALIAS TESTS
# =============================================================================

def test_hardware_schema_alias():
    """Verify that HardwareConfig is a direct alias of HardwareSchema."""
    assert HardwareConfig is HardwareSchema


def test_hardware_schema_required_bounds():
    """Test HardwareSchema bounds: ram_gb > 0.0, cpu_physical_cores >= 1, allocatable >= 0."""
    hw = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=8,
        allocatable_compute_cores=6,
        vram_gb=8.0,
        gpu_fp64_capable=True,
        mps_enabled=True,
        avx_512_capable=True,
        os_target=OSTarget.LOCAL_WINDOWS,
    )
    assert hw.ram_gb == 16.0
    assert hw.cpu_physical_cores == 8
    assert hw.allocatable_compute_cores == 6
    assert hw.vram_gb == 8.0
    assert hw.gpu_fp64_capable is True
    assert hw.mps_enabled is True
    assert hw.avx_512_capable is True
    assert hw.avx512_support is True
    assert hw.physical_cpu_cores == 8
    assert hw.ram_mb == 16384
    assert isinstance(hw.gpu_compute_metrics, GPUComputeSchema)


def test_hardware_schema_negative_bounds():
    """Verify rejection of invalid RAM, CPU cores, and VRAM bounds."""
    # ram_gb <= 0.0
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=0.0, cpu_physical_cores=4)
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=-8.0, cpu_physical_cores=4)

    # cpu_physical_cores < 1
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=16.0, cpu_physical_cores=0)
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=16.0, cpu_physical_cores=-2)

    # allocatable_compute_cores < 0
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=16.0, cpu_physical_cores=4, allocatable_compute_cores=-1)

    # vram_gb < 0.0
    with pytest.raises(ValidationError):
        HardwareSchema(ram_gb=16.0, cpu_physical_cores=4, vram_gb=-1.0)


def test_hardware_schema_flex_validation():
    """Test flex validation: auto-populating cpu_cores, ram_mb, ram_gb, and gpu fields."""
    # Case 1: physical_cpu_cores provided -> cpu_physical_cores & cpu_cores populated
    hw1 = HardwareSchema(
        physical_cpu_cores=12,
        logical_cpu_cores=24,
        ram_gb=64.0,
        os_target="windows_x86_64",
    )
    assert hw1.cpu_physical_cores == 12
    assert hw1.cpu_cores == 12
    assert hw1.ram_mb == 65536

    # Case 2: ram_mb provided, ram_gb missing -> ram_gb computed
    hw2 = HardwareSchema(
        cpu_cores=16,
        logical_cpu_cores=32,
        ram_mb=32768,
        os_target="linux_x86_64",
    )
    assert hw2.cpu_physical_cores == 16
    assert hw2.ram_gb == 32.0

    # Case 3: String representation of numbers coerced properly
    hw3 = HardwareSchema(
        cpu_physical_cores="4",  # type: ignore
        logical_cpu_cores="8",  # type: ignore
        ram_gb="16.5",  # type: ignore
        vram_gb="8.0",  # type: ignore
        os_target="Local-MacOS",
    )
    assert hw3.cpu_physical_cores == 4
    assert hw3.logical_cpu_cores == 8
    assert hw3.ram_gb == 16.5
    assert hw3.ram_mb == int(16.5 * 1024)
    assert hw3.vram_gb == 8.0
    assert hw3.gpu_compute_metrics.vram_gb == 8.0


def test_hardware_maxcore_oom_clamping():
    """Verify that maxcore_mb is safely clamped when exceeding total physical RAM."""
    hw = HardwareSchema(
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        ram_gb=8.0,
        maxcore_mb=16000,  # Exceeds 8192 MB RAM -> must clamp safely
        os_target=OSTarget.LOCAL_LINUX,
    )
    assert hw.maxcore_mb <= hw.ram_mb
    assert hw.maxcore_mb >= 500


# =============================================================================
# 4. ENVIRONMENT SCHEMA & OS TARGET TESTS
# =============================================================================

def test_ostarget_enum_canonical_values():
    """Test OSTarget enum canonical values and aliases."""
    assert OSTarget.LOCAL_WINDOWS.value == "Local-Windows"
    assert OSTarget.LOCAL_MACOS.value == "Local-MacOS"
    assert OSTarget.LOCAL_LINUX.value == "Local-Linux"
    assert OSTarget.CODESPACES.value == "Codespaces"
    assert OSTarget.GITHUB_ACTIONS.value == "GitHub_Actions"
    assert OSTarget.HPC.value == "HPC"


def test_environment_schema_canonical_os_targets():
    """Verify that all canonical OS targets pass validation."""
    canonical_targets = [
        "Local-Windows",
        "Local-MacOS",
        "Local-Linux",
        "Codespaces",
        "GitHub_Actions",
        "HPC",
    ]
    for target in canonical_targets:
        env = EnvironmentSchema(os_target=target)
        assert env.os_target == target

        hw = HardwareSchema(ram_gb=16.0, cpu_physical_cores=4, os_target=target)
        assert hw.os_target == target


def test_environment_schema_isotopic_mass_locking():
    """Verify strict isotopic mass float locking (e.g. ^13C = 13.00335483507)."""
    env = EnvironmentSchema()
    assert env.isotopic_mass_locking is True
    assert env.isotopic_mass_13c == CARBON_13_ISOTOPIC_MASS
    assert abs(env.isotopic_mass_13c - 13.00335483507) < 1e-9
    assert env.get_isotopic_mass("13C") == CARBON_13_ISOTOPIC_MASS
    assert env.get_isotopic_mass("12C") == 12.0
    assert env.get_isotopic_mass("1H") == 1.00782503223
    assert env.get_isotopic_mass("14N") == 14.00307400443
    assert env.get_isotopic_mass("16O") == 15.99491461957

    with pytest.raises(KeyError):
        env.get_isotopic_mass("999Unobtainium")


def test_environment_schema_path_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test cross-platform path resolution and strict relative path rejection."""
    test_dir = tmp_path / "cochem_env_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_TEST_VAR", str(test_dir))

    env = EnvironmentSchema(
        artifacts_dir="$COCHEM_TEST_VAR/artifacts" if os.name != "nt" else "%COCHEM_TEST_VAR%\\artifacts",
        scratch_dir="$COCHEM_TEST_VAR/scratch" if os.name != "nt" else "%COCHEM_TEST_VAR%\\scratch",
    )
    assert str(test_dir) in str(env.artifacts_dir)
    assert str(test_dir) in str(env.scratch_dir)

    # Resolve absolute path
    resolved = env.resolve_path(str(test_dir / "target.txt"))
    assert resolved.name == "target.txt"

    # Strict path resolution rejecting relative paths
    env_strict = EnvironmentSchema(strict_path_resolution=True)
    with pytest.raises(ValueError, match="Strict path resolution enabled"):
        env_strict.resolve_path("relative/path/not/absolute.txt")

    # Empty path rejection
    with pytest.raises(ValueError, match="Cannot resolve empty path"):
        env.resolve_path("")


def test_environment_schema_invalid_os_target():
    """Verify rejection of hallucinated OS target."""
    with pytest.raises(ValidationError, match="Invalid OS target"):
        EnvironmentSchema(os_target="AmigaOS_68k")


# =============================================================================
# 5. SILO PATHS SCHEMA TESTS: ABSOLUTE RESOLUTION, BYPASS & AIR-GAP
# =============================================================================

def test_silo_paths_schema_absolute_resolution(tmp_path: Path):
    """Verify SiloPathsSchema enforces absolute path resolution and bypass tokens."""
    real_orca = tmp_path / ("orca.exe" if sys.platform == "win32" else "orca")
    real_orca.write_text("#!/bin/sh\necho orca\n", encoding="utf-8")

    real_cfour = tmp_path / ("cfour.exe" if sys.platform == "win32" else "cfour")
    real_cfour.write_text("#!/bin/sh\necho cfour\n", encoding="utf-8")

    real_store = tmp_path / "pes_store.h5"
    real_store.write_bytes(b"HDF5_DATA")

    silo = SiloPathsSchema(
        orca_binary_path=str(real_orca),
        cfour_binary_path=str(real_cfour),
        aimnet2_server_path="BYPASSED",
        xtb_binary_path="Not_Found",
        mpirun_binary_path="missing",
        hdf5_pes_store_path=str(real_store),
    )

    # Bypass check
    assert silo.is_bypassed("aimnet2") is True
    assert silo.is_bypassed("cfour") is False
    assert silo.is_bypassed("orca") is False

    # Found check
    assert silo.is_found("orca") is True
    assert silo.is_found("cfour") is True
    assert silo.is_found("aimnet2") is False
    assert silo.is_found("xtb") is False

    # Resolution
    assert silo.resolve_binary("orca") == str(real_orca.resolve())
    assert silo.resolve_binary("cfour") == str(real_cfour.resolve())
    assert silo.resolve_binary("aimnet2") == "BYPASSED"
    assert silo.resolve_binary("xtb") == "Not_Found"


def test_silo_paths_schema_rejects_relative_paths():
    """Verify SiloPathsSchema explicitly rejects relative paths."""
    with pytest.raises(ValidationError, match="Relative paths are forbidden"):
        SiloPathsSchema(orca_binary_path="./bin/orca")

    with pytest.raises(ValidationError, match="Relative paths are forbidden"):
        SiloPathsSchema(cfour_binary_path="tools/cfour")

    with pytest.raises(ValidationError, match="Relative paths are forbidden"):
        SiloPathsSchema(hdf5_pes_store_path="data/store.h5")


def test_silo_paths_schema_rejects_cochem_root_write_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify write stores targeting immutable $COCHEM_ROOT are rejected."""
    cochem_root = tmp_path / "cochem_codebase_root"
    cochem_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ROOT", str(cochem_root))

    # Path inside COCHEM_ROOT must be rejected for write store
    forbidden_store = cochem_root / "forbidden_pes.h5"
    with pytest.raises(ValidationError, match="targets immutable codebase"):
        SiloPathsSchema(hdf5_pes_store_path=str(forbidden_store))

    # Path outside COCHEM_ROOT is valid
    dynamic_data_dir = tmp_path / "cochem_dynamic_data"
    dynamic_data_dir.mkdir(parents=True, exist_ok=True)
    valid_store = dynamic_data_dir / "valid_pes.h5"
    silo_valid = SiloPathsSchema(hdf5_pes_store_path=str(valid_store))
    assert silo_valid.hdf5_pes_store_path == str(valid_store.resolve())


# =============================================================================
# 6. COCHEM SYSTEM CONFIG & REGISTRY MIGRATOR TESTS
# =============================================================================

def test_cochem_system_config_alias():
    """Verify CoChemConfig is an alias of CoChemSystemConfig."""
    assert CoChemConfig is CoChemSystemConfig


def test_cochem_system_config_defaults():
    """Test CoChemSystemConfig defaults, aggregation, and active_jobs default_factory."""
    hw = HardwareSchema(ram_gb=32.0, cpu_physical_cores=8, os_target=OSTarget.LOCAL_WINDOWS)
    cfg = CoChemSystemConfig(hardware=hw)

    assert cfg.schema_version == "4.0.0"
    assert isinstance(cfg.hardware, HardwareSchema)
    assert isinstance(cfg.environment, EnvironmentSchema)
    assert isinstance(cfg.silo_paths, SiloPathsSchema)
    assert isinstance(cfg.active_jobs, dict)
    assert cfg.active_jobs == {}
    assert cfg.registry_checksum == ""


def test_registry_migrator_legacy_flat_config(tmp_path: Path):
    """Verify RegistryMigrator transforms legacy flat config dictionary into nested structure."""
    legacy_flat_data = {
        "schema_version": "1.0.0",
        "physical_cpu_cores": 16,
        "logical_cpu_cores": 32,
        "ram_gb": 64.0,
        "vram_gb": 24.0,
        "avx512_support": True,
        "gpu_profile": "NVIDIA RTX 4090",
        "os_target": "Local-Linux",
        "codata_version": "2022",
        "orca_path": str(tmp_path.resolve()),
        "cfour_binary_path": "BYPASSED",
        "active_jobs": {"job_101": {"status": "running"}},
    }

    cfg = CoChemSystemConfig.model_validate(legacy_flat_data)

    # Verified migration into hardware
    assert cfg.hardware.cpu_physical_cores == 16
    assert cfg.hardware.logical_cpu_cores == 32
    assert cfg.hardware.ram_gb == 64.0
    assert cfg.hardware.vram_gb == 24.0
    assert cfg.hardware.avx_512_capable is True

    # Verified migration into environment
    assert cfg.environment.os_target == "Local-Linux"
    assert cfg.environment.codata_version == "2022"

    # Verified migration into silo_paths
    assert cfg.silo_paths.orca_binary_path == str(tmp_path.resolve())
    assert cfg.silo_paths.cfour_binary_path == "BYPASSED"

    # Verified active_jobs
    assert cfg.active_jobs["job_101"]["status"] == "running"


def test_checksum_calculation_and_verification():
    """Verify cryptographic SHA-256 checksum calculation, update, and tamper detection."""
    hw = HardwareSchema(ram_gb=16.0, cpu_physical_cores=4, os_target=OSTarget.LOCAL_WINDOWS)
    config = CoChemSystemConfig(hardware=hw)

    assert config.registry_checksum == ""
    assert config.verify_checksum() is False

    cs1 = config.compute_checksum()
    assert isinstance(cs1, str)
    assert len(cs1) == 64
    assert all(c in "0123456789abcdef" for c in cs1)

    # Invariance to last_updated
    config.last_updated = "2026-08-22T00:00:00+00:00"
    assert config.compute_checksum() == cs1

    # Update in place
    updated_cs = config.update_checksum()
    assert updated_cs == cs1
    assert config.registry_checksum == cs1
    assert config.verify_checksum() is True

    # Tampering payload invalidates checksum
    config.hardware.ram_gb = 64.0
    assert config.verify_checksum() is False

    # Re-updating restores verification
    new_cs = config.update_checksum()
    assert new_cs != cs1
    assert config.verify_checksum() is True


def test_cochem_system_config_io_lifecycle(tmp_path: Path):
    """Test full serialization, deserialization, and physical file I/O."""
    hw = HardwareSchema(ram_gb=32.0, cpu_physical_cores=8, os_target=OSTarget.LOCAL_LINUX)
    env = EnvironmentSchema(os_target=OSTarget.LOCAL_LINUX, codata_version="2018")
    cfg = CoChemSystemConfig(
        hardware=hw,
        environment=env,
        engines={
            "orca": {"status": "found", "path": str(tmp_path.resolve()), "version": "6.1.1", "hash": "abc"}
        },
        quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
        hpc=HPCConfig(scheduler="slurm", default_partition="gpu-node", max_walltime_hours=12),
    )

    # to_dict & to_json
    d = cfg.to_dict()
    assert d["schema_version"] == "4.0.0"
    json_str = cfg.to_json()
    assert isinstance(json_str, str)

    # from_json
    restored = CoChemSystemConfig.from_json(json_str)
    assert restored.hardware.ram_gb == 32.0
    assert restored.quantum_settings.implicit_solvation == "CPCM"

    # to_file & from_file
    out_file = tmp_path / "exported_config.json"
    cfg.to_file(out_file)
    assert out_file.exists()

    loaded = CoChemSystemConfig.from_file(out_file)
    assert loaded.hardware.cpu_physical_cores == 8
    assert loaded.hpc.scheduler == "slurm"

    # create_default
    default_cfg = CoChemSystemConfig.create_default(auto_detect_hardware=False)
    assert default_cfg.hardware.cpu_physical_cores == 4
    assert default_cfg.silos.torq_silo_active is True


# =============================================================================
# 7. GATEKEEPER & DISCOVERY HELPER TESTS
# =============================================================================

def test_gatekeeper_validate_system_config(tmp_path: Path):
    """Test gatekeeper validate_system_config with various source formats."""
    hw = HardwareSchema(ram_gb=32.0, cpu_physical_cores=8, os_target=OSTarget.LOCAL_LINUX)
    cfg_inst = CoChemSystemConfig(hardware=hw)

    # Source: CoChemSystemConfig instance
    res1 = validate_system_config(cfg_inst)
    assert res1 is cfg_inst

    # Source: Dict
    raw_dict = cfg_inst.to_dict()
    res2 = validate_system_config(raw_dict)
    assert res2.hardware.cpu_physical_cores == 8

    # Source: Path
    file_path = tmp_path / "valid_gatekeeper.json"
    cfg_inst.to_file(file_path)
    res3 = validate_system_config(file_path)
    assert res3.hardware.ram_gb == 32.0

    # Source: str file path
    res4 = validate_system_config(str(file_path))
    assert res4.hardware.ram_gb == 32.0

    # Source: json string
    res5 = validate_system_config(cfg_inst.to_json())
    assert res5.hardware.cpu_physical_cores == 8

    # Unsupported types
    with pytest.raises(TypeError):
        validate_system_config(12345)  # type: ignore


def test_discover_engine_physical():
    """Test discover_engine using physically present and non-existent binaries."""
    py_engine = discover_engine("python" if sys.platform != "win32" else "python.exe")
    assert py_engine.status == "found"
    assert py_engine.path is not None
    assert Path(py_engine.path).exists()

    missing_engine = discover_engine("non_existent_binary_never_present_12345")
    assert missing_engine.status == "missing"
    assert missing_engine.path is None


def test_discover_host_hardware_physical():
    """Test discover_host_hardware retrieving physical CPU and RAM."""
    hw = discover_host_hardware()
    assert isinstance(hw, HardwareSchema)
    assert hw.cpu_physical_cores >= 1
    assert hw.allocatable_compute_cores >= 1
    assert hw.ram_gb > 0.0
    assert isinstance(hw.os_target, str)
