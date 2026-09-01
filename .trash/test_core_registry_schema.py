"""
Unit and Integration Test Suite for CoChem Core Registry Schema.
Rigorously verifies Pydantic V2 models, schema constraints, hardware flexing,
quantum settings validation, engine path handling, JSON serialization, and gatekeeper functions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest
from pydantic import ValidationError

from core_engine.cochem_core_registry_schema import (
    MPSConfig,
    CorePinningConfig,
    HardwareConfig,
    EngineInfo,
    EnginePaths,
    SiloConfig,
    RoutingPolicy,
    HPCConfig,
    QuantumSettings,
    CoChemConfig,
    discover_engine,
    discover_host_hardware,
    validate_system_config,
)


def test_mps_config():
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
        pipe_dir="/tmp/pipe",
        log_dir="/tmp/log",
    )
    assert custom.enabled is False
    assert custom.max_workers == 8
    assert custom.thread_percentage == 50
    assert custom.pipe_dir == "/tmp/pipe"

    with pytest.raises(ValidationError):
        MPSConfig(max_workers=0)
    with pytest.raises(ValidationError):
        MPSConfig(thread_percentage=101)


def test_core_pinning_config():
    cfg = CorePinningConfig()
    assert cfg.kmp_hw_subset == "8c:intel_core,1t"
    assert cfg.anchor_p_cores == 7
    assert cfg.scout_p_cores == 1
    assert cfg.background_e_cores == 8

    custom = CorePinningConfig(anchor_p_cores=12, scout_p_cores=2, background_e_cores=4)
    assert custom.anchor_p_cores == 12

    with pytest.raises(ValidationError):
        CorePinningConfig(anchor_p_cores=-1)


def test_hardware_config_flex_validation():
    hw1 = HardwareConfig(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    assert hw1.cpu_cores == 8
    assert hw1.ram_mb == 32768
    assert hw1.avx512_support is False
    assert hw1.gpu_profile == "None"

    hw2 = HardwareConfig(
        cpu_cores=12,
        logical_cpu_cores=24,
        ram_mb=16384,
        os_target="linux_x86_64",
    )
    assert hw2.physical_cpu_cores == 12
    assert hw2.ram_gb == 16.0

    hw3 = HardwareConfig(
        physical_cpu_cores=4,
        logical_cpu_cores=8,
        ram_gb="64.0",  # type: ignore
        os_target="windows_amd64",
    )
    assert hw3.ram_gb == 64.0
    assert hw3.ram_mb == 65536

    with pytest.raises(ValidationError):
        HardwareConfig(physical_cpu_cores=0, logical_cpu_cores=8, ram_gb=16.0, os_target="linux")
    with pytest.raises(ValidationError):
        HardwareConfig(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=-1.0, os_target="linux")


def test_engine_info_and_paths():
    info = EngineInfo(status="found", path="/usr/bin/orca", version="6.1.1", hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert info.status == "found"
    assert info.path == "/usr/bin/orca"
    assert info.version == "6.1.1"

    info_bypassed = EngineInfo(status="bypassed", path="BYPASSED")
    assert info_bypassed.path == "BYPASSED"

    paths = EnginePaths(orca=info, mpirun=None, xtb=None)
    assert paths.orca.version == "6.1.1"
    assert paths.mpirun is None


def test_silo_config():
    silo = SiloConfig()
    assert silo.torq_silo_active is False
    assert silo.gpu_silo_active is False

    custom_silo = SiloConfig(torq_silo_active=True, gpu_silo_active=True)
    assert custom_silo.torq_silo_active is True
    assert custom_silo.gpu_silo_active is True


def test_routing_policy():
    policy = RoutingPolicy()
    assert policy.max_concurrent_mace_threads == 4
    assert policy.max_dft_basis_functions == 2000
    assert policy.recommend_ccsdt is False
    assert policy.classification == "STANDARD"

    custom_policy = RoutingPolicy(
        max_concurrent_mace_threads=8,
        max_dft_basis_functions=5000,
        recommend_ccsdt=True,
        classification="HIGH_PERFORMANCE",
    )
    assert custom_policy.recommend_ccsdt is True

    with pytest.raises(ValidationError):
        RoutingPolicy(max_concurrent_mace_threads=0)


def test_hpc_config():
    hpc = HPCConfig()
    assert hpc.scheduler == "local"
    assert hpc.default_partition == "compute"
    assert hpc.max_walltime_hours == 24
    assert isinstance(hpc.walltime_budgets, dict)

    slurm_hpc = HPCConfig(
        scheduler="slurm",
        default_partition="gpu-a100",
        max_walltime_hours=48,
        walltime_budgets={"opt": "12:00:00", "freq": "06:00:00"},
    )
    assert slurm_hpc.scheduler == "slurm"
    assert slurm_hpc.walltime_budgets["opt"] == "12:00:00"


def test_quantum_settings_validation():
    qs1 = QuantumSettings(implicit_solvation="cpcm", integration_grid="DEFGRID2")
    assert qs1.implicit_solvation == "CPCM"
    assert qs1.integration_grid == "defgrid2"

    qs2 = QuantumSettings(implicit_solvation="smd", integration_grid="defgrid3")
    assert qs2.implicit_solvation == "SMD"
    assert qs2.integration_grid == "defgrid3"

    qs3 = QuantumSettings(implicit_solvation="[MISSING DATA]", integration_grid="")
    assert qs3.implicit_solvation is None
    assert qs3.integration_grid is None

    with pytest.raises(ValidationError, match="implicit_solvation must be 'CPCM' or 'SMD'"):
        QuantumSettings(implicit_solvation="COSMO")

    with pytest.raises(ValidationError, match="integration_grid must be one of"):
        QuantumSettings(integration_grid="ultrafine")


def test_cochem_config_lifecycle(tmp_path: Path):
    hw = HardwareConfig(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    config = CoChemConfig(
        hardware=hw,
        engines={
            "orca": {"status": "found", "path": "/opt/orca/orca", "version": "6.1.1", "hash": "abc"}
        },
        quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
    )

    d = config.to_dict()
    assert d["schema_version"] == "4.0.0"
    assert d["hardware"]["physical_cpu_cores"] == 8
    assert d["quantum_settings"]["implicit_solvation"] == "CPCM"

    json_str = config.to_json()
    restored = CoChemConfig.from_json(json_str)
    assert restored.schema_version == config.schema_version
    assert restored.hardware.physical_cpu_cores == config.hardware.physical_cpu_cores

    cfg_file = tmp_path / "test_config.json"
    config.to_file(cfg_file)
    assert cfg_file.exists()

    loaded_from_file = CoChemConfig.from_file(cfg_file)
    assert loaded_from_file.hardware.ram_gb == 32.0

    default_cfg = CoChemConfig.create_default(auto_detect_hardware=False)
    assert default_cfg.hardware.physical_cpu_cores == 4
    assert default_cfg.quantum_settings.integration_grid == "defgrid2"


def test_system_config_gatekeeper():
    root_cfg = Path("cochem_system_config.json")
    if root_cfg.exists():
        cfg = validate_system_config(root_cfg)
        assert isinstance(cfg, CoChemConfig)
        assert cfg.hardware.ram_gb > 0

    raw_dict = {
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "windows_x86_64",
        }
    }
    cfg2 = validate_system_config(raw_dict)
    assert cfg2.hardware.cpu_cores == 4

    cfg3 = validate_system_config(json.dumps(raw_dict))
    assert cfg3.hardware.logical_cpu_cores == 8

    with pytest.raises(TypeError, match="Unsupported configuration source type"):
        validate_system_config(12345)  # type: ignore


def test_discovery_helpers():
    hw = discover_host_hardware()
    assert hw.physical_cpu_cores >= 1
    assert hw.logical_cpu_cores >= 1
    assert hw.ram_gb > 0
    assert isinstance(hw.os_target, str)

    engine = discover_engine("python")
    assert engine.status in ("found", "missing")
    if engine.status == "found":
        assert engine.path is not None