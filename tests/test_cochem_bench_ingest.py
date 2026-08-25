#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 1.0 Registry Ingestion & Pre-Flight Engine.

Module: tests/test_cochem_bench_ingest.py
Target Implementation: cochem_bench.bench_engine.cochem_bench_ingest

Authoritative Requirements & Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 4 Registry Polling & The Stage 0 Handshake (Stage 1.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.finished_coding_prompts\draft_task4_ingest_pt1.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import filelock
import pytest
from pydantic import ValidationError

from cochem_bench.bench_engine.cochem_bench_ingest import (
    BenchConfigSchema,
    BenchHardwareSchema,
    BenchRunContext,
    BenchSiloPathsSchema,
    HardwareGovernor,
    HardwareGovernorResult,
    PreFlightVerification,
    RegistryHandshake,
    ResourceGuardError,
    SiloIntegrityAssert,
    SiloIntegrityError,
    cleanse_ld_library_path,
    extract_orca_path,
    run_bench_ingest_pipeline,
)
from cochem_bench.bench_libraries.subprocess_reaper import (
    PreFlightScratchVerifier,
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
)


# ==============================================================================
# Authentic Test Fixtures
# ==============================================================================

@pytest.fixture
def authentic_registry_data(tmp_path: Path) -> Dict[str, Any]:
    """Generates an authentic CoChem Stage 0 registry dictionary."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    scratch_dir = artifacts_dir / "Scratch"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    return {
        "schema_version": "4.0.0",
        "registry_version": "4.0",
        "status": "LOCKED",
        "hardware": {
            "ram_gb": 64.0,
            "cpu_physical_cores": 8,
            "allocatable_compute_cores": 7,
            "logical_cpu_cores": 16,
            "vram_gb": 24.0,
            "gpu_profile": "NVIDIA RTX 4090",
            "avx512_support": True,
            "host_id": "cochem-node-01",
            "numa_nodes": 1,
            "os_target": "Local-Windows" if platform.system() == "Windows" else "Local-Linux",
        },
        "environment": {
            "artifacts_dir": str(artifacts_dir),
            "scratch_dir": str(scratch_dir),
            "codata_version": "2018",
            "isotopic_mass_locking": True,
        },
        "silo_paths": {
            "bench_silo": str(Path(sys.executable).resolve()),
            "orca_binary_path": "C:\\ORCA\\orca.exe" if platform.system() == "Windows" else "/opt/orca/orca",
            "xtb_binary_path": "C:\\xTB\\xtb.exe" if platform.system() == "Windows" else "/opt/xtb/bin/xtb",
            "mpirun_binary_path": "C:\\MPI\\mpirun.exe" if platform.system() == "Windows" else "/usr/bin/mpirun",
        },
        "engines": {
            "orca": {
                "status": "found",
                "path": "C:\\ORCA\\orca.exe" if platform.system() == "Windows" else "/opt/orca/orca",
                "version": "6.1.1",
            },
            "xtb": {
                "status": "found",
                "path": "C:\\xTB\\xtb.exe" if platform.system() == "Windows" else "/opt/xtb/bin/xtb",
                "version": "6.7.0",
            },
        },
    }


@pytest.fixture
def stage0_environment(tmp_path: Path, authentic_registry_data: Dict[str, Any]) -> Generator[Path, None, None]:
    """Sets up an authentic filesystem environment with cochem_system_config.json."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    registry_dir = artifacts_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(authentic_registry_data, indent=2), encoding="utf-8")

    prev_artifacts = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)
    try:
        yield artifacts_dir
    finally:
        if prev_artifacts is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_artifacts
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


# ==============================================================================
# 1. Pydantic Schema Validation Tests
# ==============================================================================

def test_bench_config_schema_valid(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that authentic registry data parses correctly into BenchConfigSchema."""
    schema = BenchConfigSchema.model_validate(authentic_registry_data)
    assert schema.schema_version == "4.0.0"
    assert schema.hardware.ram_gb == 64.0
    assert schema.hardware.cpu_physical_cores == 8
    assert schema.available_ram_gb == 64.0
    assert schema.physical_cores == 8
    assert schema.silo_paths.bench_silo is not None
    assert schema.engines is not None


def test_bench_config_schema_invalid_ram_type(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that invalid non-numeric RAM types raise a strict ValidationError."""
    corrupted = dict(authentic_registry_data)
    corrupted["hardware"] = dict(corrupted["hardware"])
    corrupted["hardware"]["ram_gb"] = "not_a_number_and_invalid"

    with pytest.raises(ValidationError):
        BenchConfigSchema.model_validate(corrupted)


def test_bench_config_schema_missing_hardware(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that missing required hardware section raises ValidationError."""
    corrupted = dict(authentic_registry_data)
    del corrupted["hardware"]

    with pytest.raises(ValidationError):
        BenchConfigSchema.model_validate(corrupted)


# ==============================================================================
# 2. Stage 0 Registry Handshake Tests
# ==============================================================================

def test_registry_handshake_success(stage0_environment: Path) -> None:
    """Validate successful Stage 0 handshake from COCHEM_ARTIFACTS_DIR environment."""
    cfg = RegistryHandshake()
    assert isinstance(cfg, BenchConfigSchema)
    assert cfg.hardware.ram_gb == 64.0
    assert cfg.hardware.cpu_physical_cores == 8


def test_registry_handshake_with_explicit_artifacts_dir(stage0_environment: Path) -> None:
    """Validate successful Stage 0 handshake when passing artifacts_dir explicitly."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    assert isinstance(cfg, BenchConfigSchema)
    assert cfg.hardware.ram_gb == 64.0


def test_registry_handshake_missing_env_var() -> None:
    """Validate that missing COCHEM_ARTIFACTS_DIR env var raises fatal EnvironmentError."""
    prev_val = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ.pop("COCHEM_ARTIFACTS_DIR", None)
    try:
        with pytest.raises(EnvironmentError) as exc_info:
            RegistryHandshake()
        assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)
    finally:
        if prev_val is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_val


def test_registry_handshake_missing_registry_file(tmp_path: Path) -> None:
    """Validate that missing cochem_system_config.json raises fatal EnvironmentError with Stage 0 instructions."""
    empty_artifacts = tmp_path / "empty_artifacts"
    empty_artifacts.mkdir(parents=True, exist_ok=True)
    prev_val = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(empty_artifacts)

    try:
        with pytest.raises(EnvironmentError) as exc_info:
            RegistryHandshake()
        msg = str(exc_info.value)
        assert "cochem_system_config.json" in msg
        assert "Stage 0" in msg
    finally:
        if prev_val is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_val
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


def test_registry_handshake_filelock_behavior(stage0_environment: Path) -> None:
    """Validate that RegistryHandshake uses filelock without deadlocking."""
    config_path = stage0_environment / "Registry" / "cochem_system_config.json"
    lock_path = stage0_environment / "Registry" / "cochem_system_config.json.lock"

    lock = filelock.FileLock(str(lock_path), timeout=5.0)
    with lock:
        pass

    cfg = RegistryHandshake(artifacts_dir=stage0_environment, timeout=5.0)
    assert cfg.hardware.ram_gb == 64.0


# ==============================================================================
# 3. Hardware Governor Tests
# ==============================================================================

def test_hardware_governor_high_spec_node(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate %maxcore and MPI thread allocation on 8-core, 64 GB RAM system.

    Formula:
      Target_MPI_Threads = 8 - 1 = 7
      Safe_MaxCore_MB = floor(((64 * 1024) * 0.85) / 7) = floor(55705.6 / 7) = 7957 MB
    """
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    gov = HardwareGovernor(cfg)

    expected_threads = 7
    expected_maxcore = math.floor(((64.0 * 1024.0) * 0.85) / 7)  # 7957 MB

    assert gov.target_mpi_threads == expected_threads
    assert gov.safe_maxcore_mb == expected_maxcore
    assert not gov.resource_warning


def test_hardware_governor_low_core_node(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate %maxcore and thread allocation when physical cores <= 4.

    For physical_cores = 4:
      Target_MPI_Threads = 4
      Safe_MaxCore_MB = floor(((16 * 1024) * 0.85) / 4) = floor(13926.4 / 4) = 3481 MB
    """
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 4
    data["hardware"]["ram_gb"] = 16.0

    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg)

    assert gov.target_mpi_threads == 4
    assert gov.safe_maxcore_mb == math.floor(((16.0 * 1024.0) * 0.85) / 4)
    assert not gov.resource_warning


def test_hardware_governor_resource_warning_below_1500mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that Safe_MaxCore_MB < 1500 MB flags a resource warning."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 8.0

    # 8 cores -> 7 threads. (8 * 1024 * 0.85) / 7 = 6963.2 / 7 = 994 MB < 1500 MB
    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg)

    assert gov.safe_maxcore_mb < 1500
    assert gov.resource_warning is True


def test_hardware_governor_refuses_dlpno_ccsd_t_under_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that DLPNO-CCSD(T) is refused if Safe_MaxCore_MB < 4000 MB."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 24.0

    # 8 cores -> 7 threads. (24 * 1024 * 0.85) / 7 = 20889.6 / 7 = 2984 MB (< 4000 MB)
    cfg = BenchConfigSchema.model_validate(data)

    with pytest.raises(ResourceGuardError) as exc_info:
        HardwareGovernor(cfg, requested_method="DLPNO-CCSD(T)")
    assert "4000 MB" in str(exc_info.value)
    assert "DLPNO-CCSD(T)" in str(exc_info.value)


def test_hardware_governor_allows_dlpno_ccsd_t_above_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that DLPNO-CCSD(T) is permitted if Safe_MaxCore_MB >= 4000 MB."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    gov = HardwareGovernor(cfg, requested_method="DLPNO-CCSD(T)")
    assert gov.safe_maxcore_mb >= 4000
    assert not gov.resource_warning


def test_hardware_governor_allows_dft_under_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that non-DLPNO methods (e.g. B3LYP-D4) are allowed even if < 4000 MB."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 24.0

    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg, requested_method="B3LYP-D4")
    assert gov.safe_maxcore_mb < 4000
    assert gov.safe_maxcore_mb >= 1500
    assert not gov.resource_warning


# ==============================================================================
# 4. Silo Integrity Assertion Tests
# ==============================================================================

def test_silo_integrity_assert_success(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that active executable matching bench_silo passes verification."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    SiloIntegrityAssert(cfg, current_executable=sys.executable)


def test_silo_integrity_assert_mismatch_raises(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that active executable mismatching bench_silo raises SiloIntegrityError."""
    data = dict(authentic_registry_data)
    data["silo_paths"] = dict(data["silo_paths"])
    data["silo_paths"]["bench_silo"] = "C:\\Different_Venv\\python.exe" if platform.system() == "Windows" else "/opt/different_venv/bin/python"

    cfg = BenchConfigSchema.model_validate(data)
    with pytest.raises(SiloIntegrityError) as exc_info:
        SiloIntegrityAssert(cfg, current_executable=sys.executable)

    msg = str(exc_info.value)
    assert "ABI Protection Fault" in msg
    assert "cochem_bench_silo" in msg


def test_silo_integrity_assert_bypassed_token(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that 'BYPASSED' token in bench_silo skips the integrity check."""
    data = dict(authentic_registry_data)
    data["silo_paths"] = dict(data["silo_paths"])
    data["silo_paths"]["bench_silo"] = "BYPASSED"

    cfg = BenchConfigSchema.model_validate(data)
    SiloIntegrityAssert(cfg, current_executable="/foreign/bin/python")


# ==============================================================================
# 5. LD_LIBRARY_PATH Cleansing Tests
# ==============================================================================

def test_cleanse_ld_library_path_strips_anaconda_and_miniconda() -> None:
    """Validate that cleanse_ld_library_path strips conda paths while preserving system MPI."""
    sep = os.pathsep
    raw_path = sep.join([
        "/usr/lib/x86_64-linux-gnu",
        "/home/user/anaconda3/lib",
        "/opt/openmpi/lib",
        "/home/user/miniconda3/envs/test/lib",
        "/usr/local/gcc/lib64",
    ])

    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ["LD_LIBRARY_PATH"] = raw_path
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)

        assert cleansed is not None
        cleansed_parts = cleansed.split(sep)
        assert "/usr/lib/x86_64-linux-gnu" in cleansed_parts
        assert "/opt/openmpi/lib" in cleansed_parts
        assert "/usr/local/gcc/lib64" in cleansed_parts
        assert "/home/user/anaconda3/lib" not in cleansed_parts
        assert "/home/user/miniconda3/envs/test/lib" not in cleansed_parts

        assert os.environ.get("LD_LIBRARY_PATH") == cleansed
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)


def test_cleanse_ld_library_path_only_conda_paths() -> None:
    """Validate that if LD_LIBRARY_PATH contains only conda paths, it is safely purged."""
    sep = os.pathsep
    raw_path = sep.join([
        "/home/user/anaconda3/lib",
        "/home/user/miniconda3/lib",
    ])

    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ["LD_LIBRARY_PATH"] = raw_path
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)

        assert cleansed is None
        assert "LD_LIBRARY_PATH" not in os.environ
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)


def test_cleanse_ld_library_path_unset() -> None:
    """Validate that unset LD_LIBRARY_PATH is handled gracefully."""
    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ.pop("LD_LIBRARY_PATH", None)
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)
        assert cleansed is None
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld


# ==============================================================================
# 6. ORCA Path Extraction Tests
# ==============================================================================

def test_extract_orca_path_from_engines(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate extracting ORCA binary path from engines section."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    orca_path = extract_orca_path(cfg)
    assert orca_path is not None
    assert "orca" in orca_path.lower()


def test_extract_orca_path_from_silo_paths(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate extracting ORCA path from silo_paths when engines is empty."""
    data = dict(authentic_registry_data)
    data["engines"] = {}
    cfg = BenchConfigSchema.model_validate(data)
    orca_path = extract_orca_path(cfg)
    assert orca_path is not None
    assert "orca" in orca_path.lower()


# ==============================================================================
# 7. Pre-Flight Verification & Provenance Tests
# ==============================================================================

def test_preflight_verification_success(stage0_environment: Path) -> None:
    """Validate that PreFlightVerification executes scratch check, verifies HDF5, and returns BenchRunContext."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    context = PreFlightVerification(
        cfg=cfg,
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )

    assert isinstance(context, BenchRunContext)
    assert context.safe_maxcore_mb > 0
    assert context.target_mpi_threads > 0
    assert context.node_id != ""
    assert context.timestamp != ""
    assert context.config_hash != ""
    assert context.hdf5_path == stage0_environment / "BENCH_Workspace" / "landscape.h5"
    assert context.scratch_path.exists()
    assert not context.resource_warning


def test_preflight_context_immutability(stage0_environment: Path) -> None:
    """Validate that BenchRunContext is a frozen read-only dataclass."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    context = PreFlightVerification(
        cfg=cfg,
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.safe_maxcore_mb = 99999  # type: ignore[misc]


def test_preflight_insufficient_scratch_raises(stage0_environment: Path) -> None:
    """Validate that insufficient scratch disk space raises ResourceGuardError."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    huge_bytes = 1024 * 1024 * 1024 * 1024 * 1024

    with pytest.raises(ResourceGuardError) as exc_info:
        PreFlightVerification(
            cfg=cfg,
            artifacts_dir=stage0_environment,
            min_scratch_bytes=huge_bytes,
            current_executable=sys.executable,
        )
    assert "RESOURCE_GUARD" in str(exc_info.value)


# ==============================================================================
# 8. End-to-End Pipeline Execution Tests
# ==============================================================================

def test_run_bench_ingest_pipeline_e2e(stage0_environment: Path) -> None:
    """Validate end-to-end execution of run_bench_ingest_pipeline."""
    context = run_bench_ingest_pipeline(
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )
    assert isinstance(context, BenchRunContext)
    assert context.safe_maxcore_mb == math.floor(((64.0 * 1024.0) * 0.85) / 7)
    assert context.target_mpi_threads == 7
    assert len(context.config_hash) == 64
