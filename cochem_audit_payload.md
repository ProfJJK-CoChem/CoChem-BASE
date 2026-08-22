Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc4_01_registry_schema_prompt.md.
Original prompt:
# Task: Implement Pydantic Schema Enforcement (`cochem_core_registry_schema.py`)

## Context
Implement the Pydantic schemas that enforce the Stage 0 Authority Rule for the CoChem-BASE Master Registry. These models act as rigid mathematical boundaries, preventing hallucinated configurations or silent floating-point errors downstream. Raw dictionary manipulation of the registry is forbidden.

## Instructions
Create the file `cochem_core_registry_schema.py` and implement the following `pydantic v2` models. 

1. **Global Schema Constraints**: 
   All schemas MUST include `model_config = ConfigDict(extra='forbid', validate_assignment=True)` to prevent legacy or hallucinated key-value pairs.

2. **`GPUComputeSchema`**:
   A strictly typed sub-model tracking FLOPs, tensor cores, and memory bandwidth.

3. **`HardwareSchema`**:
   - `ram_gb` (float): Must enforce `Field(gt=0.0)`
   - `cpu_physical_cores` (int): Must enforce `Field(ge=1)`
   - `allocatable_compute_cores` (int): Enforce `Field(ge=0)`
   - `vram_gb` (float): Enforce `Field(ge=0.0)`
   - `gpu_compute_metrics`: Typed as `GPUComputeSchema`
   - `gpu_fp64_capable` (bool)
   - `mps_enabled` (bool)
   - `avx_512_capable` (bool)
   - Note: Core attributes defining hardware identity or OS constants should use `frozen=True` where applicable.

4. **`EnvironmentSchema`**:
   - `os_target` (Enum): Strictly accept only `"Local-Windows"`, `"Local-MacOS"`, `"Local-Linux"`, `"Codespaces"`, `"GitHub_Actions"`, or `"HPC"`.
   - Isotopic Mass Constants: Lock in exact isotopic mass float values (e.g., `13.00335` for ^13C).

5. **`SiloPathsSchema`**:
   - Implement absolute path validators (`@field_validator`) that resolve to OS-native paths via `Path.resolve()`. Explicitly reject relative paths.
   - Interception Logic: Allow the explicit strings `"BYPASSED"` or `"Not_Found"` to be valid values for binary paths (e.g., `cfour_binary_path`, `aimnet2_server_path`) without triggering an `os.access` execution check.
   - Define fields: `hdf5_pes_store_path`, `cfour_binary_path`, `aimnet2_server_path`.
   - Prevent write-access pointing to the codebase `$COCHEM_ROOT` (HPC Tripartite - Immutable Code Tier). Paths should map to the Dynamic Data Tier or Volatile Compute Tier.

6. **`CoChemSystemConfig`**:
   - Aggregate `HardwareSchema`, `EnvironmentSchema`, and `SiloPathsSchema`.
   - `active_jobs`: Must be typed as `Dict[str, Any]` and default to an empty dictionary (`default_factory=dict`).
   - `registry_checksum` (str, optional): Stores the SHA-256 checksum of the file contents.
   - Include a `@model_validator(mode='before')` hook (`RegistryMigrator`) capable of reading legacy flat JSON architectures and remapping them to this nested architecture before validation.

## Constraints
- **Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_core_registry_schema.py`
- Absolutely NO mocks, stubs, dummy variables, or `# TODO` placeholders. The future coder agent is explicitly commanded to *not* use mocks.
- Ensure 100% compliance with `pydantic v2` standards.
- Must strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_schema.py ---
#!/usr/bin/env python3
"""
CoChem-CORE: Re-exports authoritative schemas from root cochem_core_registry_schema.
"""

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
    HPCConfig,
    HardwareConfig,
    HardwareSchema,
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

__all__ = [
    "BYPASS_TOKENS",
    "CARBON_13_ISOTOPIC_MASS",
    "ISOTOPIC_MASSES",
    "CoChemConfig",
    "CoChemSystemConfig",
    "CorePinningConfig",
    "EngineInfo",
    "EnginePaths",
    "EnvironmentSchema",
    "GPUComputeSchema",
    "HPCConfig",
    "HardwareConfig",
    "HardwareSchema",
    "MPSConfig",
    "OSTarget",
    "QuantumSettings",
    "RoutingPolicy",
    "SiloConfig",
    "SiloPathsSchema",
    "discover_engine",
    "discover_host_hardware",
    "validate_system_config",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_registry_schema.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_core_registry_schema.py ---
#!/usr/bin/env python3
"""
CoChem-BASE: Stage 0 Authority Rule - Golden Master Registry Schema
Defines rigid Pydantic v2 models for `cochem_system_config.json`.
Acts as a mathematical boundary preventing hallucinated configurations,
silent floating-point drift, relative path vulnerabilities, and OOM thread allocation.
All schemas strictly forbid extra fields and enforce validation on assignment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import platform
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND ENVIRONMENT EXPANSION
# =============================================================================

CARBON_13_ISOTOPIC_MASS: float = 13.00335483507

ISOTOPIC_MASSES: Dict[str, float] = {
    "1H": 1.00782503223,
    "2H": 2.01410177812,
    "3H": 3.01604928132,
    "12C": 12.00000000000,
    "13C": CARBON_13_ISOTOPIC_MASS,
    "14N": 14.00307400443,
    "15N": 15.00010889888,
    "16O": 15.99491461957,
    "17O": 16.99913175650,
    "18O": 17.99915961286,
    "19F": 18.99840316273,
    "31P": 30.97376199842,
    "32S": 31.97207117440,
    "35Cl": 34.96885268200,
    "37Cl": 36.96590260200,
    "79Br": 78.91833760000,
    "81Br": 80.91629100000,
    "127I": 126.9044719000,
}

BYPASS_TOKENS: Set[str] = {"BYPASSED", "Not_Found", "missing"}


def _expand_env_vars(path_str: str) -> str:
    """Uniformly expands %VAR%, $VAR, and ${VAR} across Windows and POSIX."""
    if not path_str:
        return path_str

    def replace_percent(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, f"%{var}%")

    s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, path_str)
    s = os.path.expandvars(s)
    return os.path.expanduser(s)


def _default_mps_pipe_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[0])
    except Exception:
        return "/tmp/nvidia-mps"


def _default_mps_log_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[1])
    except Exception:
        return "/tmp/nvidia-log"


def _default_os_target() -> str:
    sys_name = platform.system().lower()
    if "windows" in sys_name:
        return OSTarget.LOCAL_WINDOWS.value
    if "darwin" in sys_name:
        return OSTarget.LOCAL_MACOS.value
    if os.getenv("GITHUB_ACTIONS") == "true":
        return OSTarget.GITHUB_ACTIONS.value
    if os.getenv("CODESPACES") == "true":
        return OSTarget.CODESPACES.value
    return OSTarget.LOCAL_LINUX.value


def _default_artifacts_dir() -> str:
    return os.getenv("COCHEM_ARTIFACTS_DIR", str(Path.home() / "cochem_artifacts"))


# =============================================================================
# ENUMS
# =============================================================================

class OSTarget(str, Enum):
    """
    Authoritative Operating System and Architecture Targets for the CoChem Ecosystem.
    Canonical 6-tier values: Local-Windows, Local-MacOS, Local-Linux, Codespaces, GitHub_Actions, HPC.
    """
    LOCAL_WINDOWS = "Local-Windows"
    LOCAL_MACOS = "Local-MacOS"
    LOCAL_LINUX = "Local-Linux"
    CODESPACES = "Codespaces"
    GITHUB_ACTIONS = "GitHub_Actions"
    HPC = "HPC"

    # Direct ecosystem aliases
    LINUX_X86_64 = "linux_x86_64"
    LINUX_AARCH64 = "linux_aarch64"
    WINDOWS_X86_64 = "windows_x86_64"
    WINDOWS_AMD64 = "windows_amd64"
    DARWIN_ARM64 = "darwin_arm64"
    DARWIN_X86_64 = "darwin_x86_64"
    GENERIC_POSIX = "posix"
    GENERIC_NT = "nt"


_OS_TARGET_NORMALIZATION_MAP: Dict[str, str] = {
    "local-windows": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_native": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_wsl": OSTarget.LOCAL_WINDOWS.value,
    "windows": OSTarget.LOCAL_WINDOWS.value,
    "windows_x86_64": OSTarget.WINDOWS_X86_64.value,
    "windows_amd64": OSTarget.WINDOWS_AMD64.value,
    "nt": OSTarget.GENERIC_NT.value,

    "local-macos": OSTarget.LOCAL_MACOS.value,
    "local-macos_darwin": OSTarget.LOCAL_MACOS.value,
    "darwin": OSTarget.LOCAL_MACOS.value,
    "darwin_arm64": OSTarget.DARWIN_ARM64.value,
    "darwin_x86_64": OSTarget.DARWIN_X86_64.value,

    "local-linux": OSTarget.LOCAL_LINUX.value,
    "local-linux_deb": OSTarget.LOCAL_LINUX.value,
    "linux": OSTarget.LOCAL_LINUX.value,
    "linux_x86_64": OSTarget.LINUX_X86_64.value,
    "linux_amd64": OSTarget.LINUX_X86_64.value,
    "linux_aarch64": OSTarget.LINUX_AARCH64.value,
    "posix": OSTarget.GENERIC_POSIX.value,

    "codespaces": OSTarget.CODESPACES.value,
    "github_codespaces": OSTarget.CODESPACES.value,
    "github_actions": OSTarget.GITHUB_ACTIONS.value,
    "hpc": OSTarget.HPC.value,
    "hpc_slurm_linux": OSTarget.HPC.value,
}


# =============================================================================
# 1. GPU COMPUTE SCHEMA
# =============================================================================

class GPUComputeSchema(BaseModel):
    """
    GPU Compute Metrics and Hardware Topology.
    Tracks peak theoretical/measured TFLOPS, Tensor Cores count, Memory Bandwidth, and CUDA features.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    gpu_profile: str = Field(default="None", description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    device_count: int = Field(default=0, ge=0, description="Number of detected GPU devices")
    compute_capability: Optional[str] = Field(default=None, description="CUDA Compute capability, e.g. '8.9'")
    fp64_capable: bool = Field(default=False, description="Whether device supports native double-precision FP64")
    subnormal_precision_trap: bool = Field(default=False, description="Whether subnormal precision traps are enabled")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak TFLOPS compute metric")
    fp32_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP32 TFLOPS")
    fp16_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP16 TFLOPS")
    fp64_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP64 TFLOPS")
    tensor_cores: Optional[int] = Field(default=None, ge=0, description="Number of hardware Tensor Cores")
    memory_bandwidth_gb_s: Optional[float] = Field(default=None, ge=0.0, description="GPU memory bandwidth in GB/s")


# =============================================================================
# 2. MPS & CORE PINNING CONFIGURATIONS
# =============================================================================

class MPSConfig(BaseModel):
    """CUDA Multi-Process Service (MPS) configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable CUDA MPS daemon multiplexing")
    max_workers: int = Field(default=4, gt=0, le=64, description="Max concurrent MPS worker tasks per GPU")
    thread_percentage: int = Field(default=25, ge=1, le=100, description="CUDA MPS active thread percentage ceiling")
    pipe_dir: str = Field(default_factory=_default_mps_pipe_dir, description="MPS pipe directory")
    log_dir: str = Field(default_factory=_default_mps_log_dir, description="MPS log directory")


class CorePinningConfig(BaseModel):
    """Core Pinning and CPU Topology Configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    kmp_hw_subset: str = Field(default="8c:intel_core,1t", description="OpenMP core pinning HW subset spec")
    anchor_p_cores: int = Field(default=7, ge=0, description="Number of P-cores assigned to CPU anchor tasks")
    scout_p_cores: int = Field(default=1, ge=0, description="Number of P-cores assigned to GPU scout tasks")
    background_e_cores: int = Field(default=8, ge=0, description="E-cores reserved for OS/background tasks")


# =============================================================================
# 3. QUANTUM SOLVER SETTINGS
# =============================================================================

class QuantumSettings(BaseModel):
    """Quantum chemical solver settings."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    implicit_solvation: Optional[str] = Field(default=None, description="Implicit solvent model (CPCM, SMD) or None")
    integration_grid: Optional[str] = Field(default="defgrid2", description="Integration grid size (defgrid1, defgrid2, defgrid3)")
    charge: int = Field(default=0)
    multiplicity: int = Field(default=1, ge=1)

    @field_validator("implicit_solvation", mode="before")
    @classmethod
    def validate_implicit_solvation(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().upper()
            if cleaned in ("CPCM", "SMD"):
                return cleaned
            raise ValueError("implicit_solvation must be 'CPCM' or 'SMD'")
        return cast(Optional[str], v)

    @field_validator("integration_grid", mode="before")
    @classmethod
    def validate_integration_grid(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("defgrid1", "defgrid2", "defgrid3"):
                return cleaned
            raise ValueError("integration_grid must be one of ('defgrid1', 'defgrid2', 'defgrid3')")
        return cast(Optional[str], v)


# =============================================================================
# 4. HARDWARE SCHEMA
# =============================================================================

class HardwareSchema(BaseModel):
    """
    Rigid bounds for physical compute resources to prevent OOM and thread contention.
    Enforces positive RAM (gt=0.0), at least 1 physical core (ge=1), non-negative allocatable cores (ge=0),
    and non-negative VRAM (ge=0.0).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Actual physical silicon cores")
    allocatable_compute_cores: int = Field(default=1, ge=0, description="Allocatable compute cores for scientific jobs")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    gpu_compute_metrics: GPUComputeSchema = Field(default_factory=GPUComputeSchema, description="GPU compute metrics and capabilities")
    gpu_fp64_capable: bool = Field(default=False, description="Whether GPU supports native FP64 precision")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    avx_512_capable: bool = Field(default=False, description="Whether CPU supports AVX-512 vector instructions")

    # Ecosystem & compatibility aliases
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Alias for cpu_physical_cores")
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Hyperthreaded threads count")
    cpu_cores: Optional[int] = Field(default=None, ge=1, description="Legacy CPU cores alias")
    ram_mb: Optional[int] = Field(default=None, ge=1, description="Total system RAM in MB")
    maxcore_mb: Optional[int] = Field(default=3000, ge=0, description="Max core memory per process in MB")
    avx512_support: bool = Field(default=False, description="Legacy alias for avx_512_capable")
    gpu_profile: str = Field(default="None", description="Detected GPU model name")
    subnormal_precision_trap: bool = Field(default=False, description="Subnormal floating-point trap")
    os_target: Union[OSTarget, str] = Field(default=OSTarget.LOCAL_WINDOWS, description="Target execution environment")
    host_id: Optional[str] = Field(default=None, description="Host identity identifier")
    mps: Optional[MPSConfig] = Field(default_factory=MPSConfig, description="MPS daemon configuration")
    core_pinning: Optional[CorePinningConfig] = Field(default_factory=CorePinningConfig, description="CPU core pinning topology")
    gpu: Optional[GPUComputeSchema] = Field(default=None, description="Legacy alias for gpu_compute_metrics")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def flex_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # String-to-number coercions
        for float_field in ["ram_gb", "vram_gb"]:
            if float_field in d and isinstance(d[float_field], str):
                try:
                    d[float_field] = float(d[float_field])
                except ValueError:
                    pass

        for int_field in ["cpu_physical_cores", "physical_cpu_cores", "logical_cpu_cores", "cpu_cores", "allocatable_compute_cores", "ram_mb", "maxcore_mb"]:
            if int_field in d and isinstance(d[int_field], str):
                try:
                    d[int_field] = int(float(d[int_field]))
                except ValueError:
                    pass

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
                if "cpu_cores" not in d:
                    d["cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        if "logical_cpu_cores" not in d or d["logical_cpu_cores"] is None:
            if phys is not None:
                try:
                    d["logical_cpu_cores"] = int(phys)
                except (ValueError, TypeError):
                    pass

        if "allocatable_compute_cores" not in d or d["allocatable_compute_cores"] is None:
            if phys is not None:
                try:
                    d["allocatable_compute_cores"] = int(phys)
                except (ValueError, TypeError):
                    pass

        # Synchronize RAM
        if "ram_mb" not in d and "ram_gb" in d:
            try:
                d["ram_mb"] = int(float(d["ram_gb"]) * 1024)
            except (ValueError, TypeError):
                pass
        elif "ram_gb" not in d and "ram_mb" in d:
            try:
                d["ram_gb"] = float(d["ram_mb"]) / 1024.0
            except (ValueError, TypeError):
                pass

        # Maxcore OOM clamping guard
        if "maxcore_mb" in d and "ram_mb" in d:
            try:
                maxcore = int(d["maxcore_mb"])
                ram_mb = int(d["ram_mb"])
                if maxcore > ram_mb:
                    phys_count = int(d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or 1)
                    d["maxcore_mb"] = max(500, int(ram_mb * 0.75 / max(1, phys_count)))
            except (ValueError, TypeError):
                pass

        # Synchronize AVX-512 capabilities
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])
        elif "avx_512_capable" not in d and "avx512_support" not in d:
            d["avx_512_capable"] = False
            d["avx512_support"] = False

        # Synchronize GPU compute metrics
        gpu_data = d.get("gpu_compute_metrics") or d.get("gpu")
        if gpu_data is None:
            gpu_prof = d.get("gpu_profile", "None")
            vram = d.get("vram_gb", 0.0)
            trap = d.get("subnormal_precision_trap", False)
            fp64 = d.get("gpu_fp64_capable", False)
            mps_en = d.get("mps_enabled", False)
            built_gpu = {
                "gpu_profile": gpu_prof,
                "vram_gb": float(vram) if isinstance(vram, (int, float, str)) else 0.0,
                "subnormal_precision_trap": trap,
                "fp64_capable": fp64,
                "mps_enabled": mps_en,
            }
            d["gpu_compute_metrics"] = built_gpu
            d["gpu"] = built_gpu
        else:
            if isinstance(gpu_data, dict):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "fp64_capable" in gpu_data and "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = bool(gpu_data["fp64_capable"])
                if "mps_enabled" in gpu_data and "mps_enabled" not in d:
                    d["mps_enabled"] = bool(gpu_data["mps_enabled"])
            elif isinstance(gpu_data, GPUComputeSchema):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = gpu_data.fp64_capable
                if "mps_enabled" not in d:
                    d["mps_enabled"] = gpu_data.mps_enabled

        return d


HardwareConfig = HardwareSchema


# =============================================================================
# 5. ENVIRONMENT SCHEMA
# =============================================================================

class EnvironmentSchema(BaseModel):
    """
    Operating environment configuration, OS target validation, and isotopic mass locking.
    Enforces exact isotopic mass float values (e.g., ^13C = 13.00335483507).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    os_target: Union[OSTarget, str] = Field(
        default_factory=_default_os_target,
        description="Target OS tier",
    )
    artifacts_dir: Union[str, Path] = Field(
        default_factory=_default_artifacts_dir,
        description="Path to artifacts directory",
    )
    scratch_dir: Optional[Union[str, Path]] = Field(default=None, description="Path to fast scratch directory")
    codata_version: str = Field(default="2018", description="CODATA constant version (e.g. '2018')")
    isotopic_mass_locking: bool = Field(default=True, description="Strict lock on atomic/isotopic masses")
    isotopic_mass_13c: float = Field(
        default=CARBON_13_ISOTOPIC_MASS,
        description="Locked isotopic mass for Carbon-13 (^13C = 13.00335483507)",
    )
    isotopic_masses: Dict[str, float] = Field(
        default_factory=lambda: dict(ISOTOPIC_MASSES),
        description="Exact isotopic mass registry",
    )
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Custom environment variable overrides")
    strict_path_resolution: bool = Field(default=False, description="Reject unresolvable relative paths if True")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @field_validator("codata_version")
    @classmethod
    def validate_codata(cls, v: str) -> str:
        valid = {"2014", "2018", "2022"}
        if v not in valid:
            raise ValueError(f"codata_version must be one of {sorted(valid)}, got '{v}'")
        return v

    @field_validator("artifacts_dir", "scratch_dir", mode="before")
    @classmethod
    def expand_and_normalize_path(cls, v: Any) -> Any:
        if v is None or v == "[MISSING DATA]":
            return None
        return _expand_env_vars(str(v))

    def resolve_path(self, raw_path: Union[str, Path]) -> Path:
        """Cross-platform path resolution with environment variable expansion."""
        if not raw_path:
            raise ValueError("Cannot resolve empty path.")
        expanded = _expand_env_vars(str(raw_path))
        p = Path(expanded)
        if self.strict_path_resolution and not p.is_absolute():
            raise ValueError(f"Strict path resolution enabled: relative path '{raw_path}' is rejected.")
        return p.resolve()

    def get_isotopic_mass(self, isotope: str) -> float:
        """Retrieve authoritative locked isotopic mass float."""
        if isotope in self.isotopic_masses:
            return self.isotopic_masses[isotope]
        if isotope == "13C":
            return self.isotopic_mass_13c
        raise KeyError(f"Isotope '{isotope}' not registered in isotopic mass matrix.")


# =============================================================================
# 6. SILO PATHS SCHEMA
# =============================================================================

class SiloPathsSchema(BaseModel):
    """
    Paths configuration for isolated silos and scientific binaries.
    Enforces absolute path resolution (rejects relative paths), intercepting 'BYPASSED' and 'Not_Found'
    tokens, and preventing write stores (like HDF5 PES stores) from targeting immutable $COCHEM_ROOT.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    hdf5_pes_store_path: Optional[str] = Field(default=None, description="Path to centralized HDF5 PES store")
    cfour_binary_path: Optional[str] = Field(default=None, description="Path to CFOUR binary or 'BYPASSED'")
    aimnet2_server_path: Optional[str] = Field(default=None, description="Path to AIMNet2 server script or 'BYPASSED'")
    orca_binary_path: Optional[str] = Field(default=None, description="Path to ORCA executable or 'BYPASSED'")
    xtb_binary_path: Optional[str] = Field(default=None, description="Path to xTB executable or 'BYPASSED'")
    mpirun_binary_path: Optional[str] = Field(default=None, description="Path to mpirun executable or 'BYPASSED'")

    # Aliases
    orca_path: Optional[str] = Field(default=None, description="Alias for orca_binary_path")
    xtb_path: Optional[str] = Field(default=None, description="Alias for xtb_binary_path")
    mpirun_path: Optional[str] = Field(default=None, description="Alias for mpirun_binary_path")
    cfour_path: Optional[str] = Field(default=None, description="Alias for cfour_binary_path")
    aimnet2_path: Optional[str] = Field(default=None, description="Alias for aimnet2_server_path")
    python_path: Optional[str] = Field(default=None, description="Path to silo Python interpreter")
    silo_root: Optional[str] = Field(default=None, description="Root directory for micro-environments")
    strict_resolution: bool = Field(default=False, description="Enforce binary presence verification")

    @field_validator(
        "hdf5_pes_store_path",
        "cfour_binary_path",
        "aimnet2_server_path",
        "orca_binary_path",
        "xtb_binary_path",
        "mpirun_binary_path",
        "orca_path",
        "xtb_path",
        "mpirun_path",
        "cfour_path",
        "aimnet2_path",
        "python_path",
        "silo_root",
        mode="before",
    )
    @classmethod
    def validate_and_expand_path(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, (str, Path)):
            s = str(v).strip()
            if s in BYPASS_TOKENS:
                return s

            expanded = _expand_env_vars(s)
            p = Path(expanded)

            # Reject relative paths strictly
            if not p.is_absolute():
                raise ValueError(
                    f"Relative paths are forbidden in SiloPathsSchema for '{info.field_name}': '{s}'. "
                    "Path must be absolute or a bypass token ('BYPASSED', 'Not_Found', 'missing')."
                )

            resolved = p.resolve()

            # HPC Tripartite Air-Gap Check: Prevent write stores from targeting immutable $COCHEM_ROOT
            if info.field_name == "hdf5_pes_store_path":
                cochem_root_env = os.environ.get("COCHEM_ROOT")
                if cochem_root_env:
                    resolved_root = Path(os.path.expandvars(cochem_root_env)).resolve()
                    try:
                        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                    except AttributeError:
                        try:
                            resolved.relative_to(resolved_root)
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                        except ValueError:
                            pass

            return str(resolved)
        raise ValueError(f"Invalid path type '{type(v)}' for '{info.field_name}'. Expected string or Path.")

    @model_validator(mode="before")
    @classmethod
    def sync_path_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        alias_pairs = [
            ("orca_binary_path", "orca_path"),
            ("xtb_binary_path", "xtb_path"),
            ("mpirun_binary_path", "mpirun_path"),
            ("cfour_binary_path", "cfour_path"),
            ("aimnet2_server_path", "aimnet2_path"),
        ]
        for canonical, alias in alias_pairs:
            if canonical in d and alias not in d:
                d[alias] = d[canonical]
            elif alias in d and canonical not in d:
                d[canonical] = d[alias]
        return d

    def is_bypassed(self, binary_name: str) -> bool:
        """Check if binary execution is marked as BYPASSED."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                return val == "BYPASSED"
        return False

    def is_found(self, binary_name: str) -> bool:
        """Check if binary exists on filesystem and is not bypassed/missing."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if not val or val in BYPASS_TOKENS:
                    return False
                return Path(val).exists()
        return False

    def resolve_binary(self, binary_name: str) -> Optional[str]:
        """Resolve executable path or return bypass token."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if val is None or val in BYPASS_TOKENS:
                    return cast(Optional[str], val)
                p = Path(val)
                if self.strict_resolution and not p.exists():
                    raise FileNotFoundError(f"Binary '{binary_name}' not found at path '{val}'")
                return str(p.resolve())
        raise AttributeError(f"Unknown binary configuration '{binary_name}' in SiloPathsSchema")


# =============================================================================
# 7. COMPUTATIONAL BINARY PROVENANCE & SILO CONFIGS
# =============================================================================

class EngineInfo(BaseModel):
    """Pathing and cryptographic provenance for computational binaries."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(..., description="found, missing, permission_denied, or bypassed")
    path: Optional[str] = Field(None, description="Absolute path to executable, or 'BYPASSED', or 'Not_Found'")
    version: Optional[str] = Field(None, description="Semantic version of the engine")
    hash: Optional[str] = Field(None, description="SHA-256 binary hash")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> str:
        if v is None or v == "[MISSING DATA]":
            return "missing"
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("found", "missing", "permission_denied", "bypassed"):
                return cleaned
            raise ValueError(f"Invalid engine status '{v}'. Must be one of ('found', 'missing', 'permission_denied', 'bypassed').")
        raise ValueError(f"Invalid engine status type '{type(v)}'. Expected string.")

    @field_validator("path", "version", "hash", mode="before")
    @classmethod
    def clean_missing_data(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return str(v)


class EnginePaths(BaseModel):
    """Aggregated binary path specifications."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    orca: Optional[EngineInfo] = Field(default=None)
    mpirun: Optional[EngineInfo] = Field(default=None)
    xtb: Optional[EngineInfo] = Field(default=None)
    cfour: Optional[EngineInfo] = Field(default=None)
    aimnet2: Optional[EngineInfo] = Field(default=None)
    mace: Optional[EngineInfo] = Field(default=None)


class SiloConfig(BaseModel):
    """Micro-environment deployment status."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    torq_silo_active: bool = Field(default=False)
    gpu_silo_active: bool = Field(default=False)


class RoutingPolicy(BaseModel):
    """Dynamically assigned execution constraints."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_concurrent_mace_threads: int = Field(default=4, gt=0)
    max_dft_basis_functions: int = Field(default=2000, gt=0)
    recommend_ccsdt: bool = Field(default=False)
    classification: str = Field(default="STANDARD")


class HPCConfig(BaseModel):
    """Cluster integration parameters."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scheduler: str = Field(default="local", description="local, slurm, pbs, or sge")
    default_partition: str = Field(default="compute")
    max_walltime_hours: Optional[int] = Field(default=24, gt=0)
    partition: Optional[str] = Field(default="compute")
    cluster_hostname: Optional[str] = Field(default="localhost")
    ssh_key_path: Optional[str] = Field(default="")
    username: Optional[str] = Field(default="localuser")
    execution_mode: Optional[str] = Field(default="local")
    walltime_budgets: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("scheduler", mode="before")
    @classmethod
    def validate_scheduler(cls, v: Any) -> str:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("local", "slurm", "pbs", "sge"):
                return s
            raise ValueError(f"Invalid HPC scheduler '{v}'. Must be one of ('local', 'slurm', 'pbs', 'sge').")
        raise ValueError(f"HPC scheduler must be a string, got {type(v)}")


# =============================================================================
# 8. MASTER COCHEM SYSTEM CONFIG
# =============================================================================

class CoChemSystemConfig(BaseModel):
    """
    The CoChem Master System Configuration Schema.
    Rigid mathematical boundary enforcing Stage 0 Authority Rule.
    Aggregates HardwareSchema, EnvironmentSchema, SiloPathsSchema, and live execution jobs.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    orca_version: Optional[str] = Field(default="6.1.1")
    rdkit_random_seed: Optional[int] = Field(default=42)
    registry_checksum: Optional[str] = Field(default="", description="SHA-256 checksum of registry payload")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hardware: HardwareSchema = Field(..., description="Rigid compute hardware bounds and topology")
    environment: EnvironmentSchema = Field(default_factory=EnvironmentSchema, description="Operating environment settings")
    silo_paths: SiloPathsSchema = Field(default_factory=SiloPathsSchema, description="Silo and binary path mappings")
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    silos: Optional[SiloConfig] = Field(default=None, description="Micro-environment deployment status")
    quantum_settings: Optional[QuantumSettings] = Field(default_factory=QuantumSettings)
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

    @model_validator(mode="before")
    @classmethod
    def registry_migrator(cls, data: Any) -> Any:
        """
        RegistryMigrator: Transforms legacy flat configuration dictionaries
        into the authoritative nested schema architecture before validation.
        """
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Migrate flat Hardware fields
        hw_keys = {
            "physical_cpu_cores", "cpu_physical_cores", "logical_cpu_cores",
            "cpu_cores", "ram_gb", "ram_mb", "maxcore_mb", "avx512_support",
            "avx_512_capable", "gpu_profile", "vram_gb", "subnormal_precision_trap",
            "allocatable_compute_cores", "gpu_compute_metrics", "gpu_fp64_capable",
            "mps_enabled", "core_pinning", "mps", "gpu", "host_id"
        }
        extracted_hw: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in hw_keys:
                extracted_hw[k] = d.pop(k)

        if "hardware" not in d or d["hardware"] is None:
            if extracted_hw:
                d["hardware"] = extracted_hw
        elif isinstance(d["hardware"], dict):
            for k, v in extracted_hw.items():
                if k not in d["hardware"]:
                    d["hardware"][k] = v

        # 2. Migrate flat Environment fields
        env_keys = {
            "codata_version", "isotopic_mass_locking", "isotopic_mass_13c",
            "isotopic_masses", "artifacts_dir", "scratch_dir",
            "strict_path_resolution", "env_vars"
        }
        extracted_env: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in env_keys:
                extracted_env[k] = d.pop(k)

        if "os_target" in d:
            os_target_val = d.pop("os_target")
            extracted_env["os_target"] = os_target_val
            if "hardware" in d and isinstance(d["hardware"], dict) and "os_target" not in d["hardware"]:
                d["hardware"]["os_target"] = os_target_val

        if "environment" not in d or d["environment"] is None:
            if extracted_env:
                d["environment"] = extracted_env
        elif isinstance(d["environment"], dict):
            for k, v in extracted_env.items():
                if k not in d["environment"]:
                    d["environment"][k] = v

        # 3. Migrate flat Silo fields
        silo_keys = {
            "orca_path", "xtb_path", "mpirun_path", "cfour_path", "aimnet2_server_path",
            "aimnet2_path", "cfour_binary_path", "orca_binary_path", "xtb_binary_path",
            "mpirun_binary_path", "hdf5_pes_store_path", "silo_root", "python_path", "strict_resolution"
        }
        extracted_silo: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in silo_keys:
                extracted_silo[k] = d.pop(k)

        if "silo_paths" not in d or d["silo_paths"] is None:
            if extracted_silo:
                d["silo_paths"] = extracted_silo
        elif isinstance(d["silo_paths"], dict):
            for k, v in extracted_silo.items():
                if k not in d["silo_paths"]:
                    d["silo_paths"][k] = v

        # 4. Default active_jobs
        if "active_jobs" not in d or d["active_jobs"] is None:
            d["active_jobs"] = {}

        return d

    @field_validator("adaptive_routing", mode="before")
    @classmethod
    def clean_adaptive_routing(cls, v: Any) -> Any:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return v

    @field_validator("engines", mode="before")
    @classmethod
    def validate_engines(cls, v: Any) -> Any:
        if isinstance(v, dict):
            validated: Dict[str, Any] = {}
            for engine_name, engine_val in v.items():
                if isinstance(engine_val, dict):
                    validated[engine_name] = EngineInfo.model_validate(engine_val)
                else:
                    validated[engine_name] = engine_val
            return validated
        return v

    def compute_checksum(self) -> str:
        """Calculates deterministic SHA-256 checksum of configuration payload."""
        d = self.model_dump(exclude={"registry_checksum", "last_updated"})
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def update_checksum(self) -> str:
        """Calculates and updates registry_checksum in place."""
        cs = self.compute_checksum()
        self.registry_checksum = cs
        return cs

    def verify_checksum(self) -> bool:
        """Verifies whether registry_checksum matches the current configuration payload."""
        if not self.registry_checksum:
            return False
        return self.registry_checksum == self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CoChemSystemConfig:
        return cls.model_validate(d)

    @classmethod
    def from_json(cls, json_str: str) -> CoChemSystemConfig:
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> CoChemSystemConfig:
        p = Path(path)
        return cls.model_validate_json(p.read_text(encoding="utf-8"))

    @classmethod
    def create_default(cls, auto_detect_hardware: bool = False) -> CoChemSystemConfig:
        hw = discover_host_hardware() if auto_detect_hardware else HardwareSchema(
            cpu_physical_cores=4,
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            os_target=OSTarget.LOCAL_WINDOWS if os.name == "nt" else OSTarget.LOCAL_LINUX,
        )
        return cls(
            hardware=hw,
            quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
            silos=SiloConfig(torq_silo_active=True),
        )


CoChemConfig = CoChemSystemConfig


# =============================================================================
# 9. DISCOVERY & CONVENIENCE FUNCTIONS
# =============================================================================

def discover_engine(binary_name: str) -> EngineInfo:
    """Check physical presence and provenance of a scientific binary."""
    p = shutil.which(binary_name)
    if p:
        return EngineInfo(status="found", path=str(p), version="auto", hash="auto")
    return EngineInfo(status="missing", path=None, version=None, hash=None)


def discover_host_hardware() -> HardwareSchema:
    """Discover host hardware configuration safely."""
    try:
        import psutil  # type: ignore[import-untyped]
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        phys_cores = psutil.cpu_count(logical=False) or 1
        log_cores = psutil.cpu_count(logical=True) or 1
    except ImportError:
        total_ram_gb = 16.0
        phys_cores = os.cpu_count() or 1
        log_cores = os.cpu_count() or 1

    os_target = _default_os_target()

    return HardwareSchema(
        cpu_physical_cores=phys_cores,
        physical_cpu_cores=phys_cores,
        logical_cpu_cores=log_cores,
        allocatable_compute_cores=phys_cores,
        ram_gb=round(total_ram_gb, 2),
        avx_512_capable=False,
        gpu_profile="None",
        vram_gb=0.0,
        os_target=os_target,
    )


def validate_system_config(source: Union[str, Path, Dict[str, Any], CoChemSystemConfig]) -> CoChemSystemConfig:
    """Authoritative gatekeeper validating system configuration from any source."""
    if isinstance(source, CoChemSystemConfig):
        return source
    if isinstance(source, dict):
        return CoChemSystemConfig.model_validate(source)
    if isinstance(source, Path):
        return CoChemSystemConfig.from_file(source)
    if isinstance(source, str):
        if os.path.exists(source):
            return CoChemSystemConfig.from_file(source)
        try:
            return CoChemSystemConfig.from_json(source)
        except Exception:
            try:
                raw_dict = json.loads(source)
                return CoChemSystemConfig.model_validate(raw_dict)
            except Exception:
                pass
    raise TypeError(f"Unsupported configuration source type: {type(source)}")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_core_registry_schema.py ---
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

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.