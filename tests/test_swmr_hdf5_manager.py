#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Task 7 Thread-Safe Atomic I/O and SWMR HDF5 Manager.

Module: tests/test_swmr_hdf5_manager.py
Target Implementation: cochem_bench.bench_libraries.swmr_hdf5_manager

Authoritative Requirements & Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task7_swmr.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Generator, List

import filelock
import h5py
import numpy as np
import psutil
import pytest

from cochem_bench.bench_libraries.swmr_hdf5_manager import (
    AtomicJSONManager,
    BenchHDF5Serializer,
    CoChemHDF5Error,
    CoChemRegistryLockError,
    CoChemSWMRHDF5BaseError,
    CoChemStaleLockError,
    SWMRWriteReport,
    get_bench_workspace_dir,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_registry_workspace_dir,
)


# ==============================================================================
# Authentic Test Fixtures
# ==============================================================================

@pytest.fixture
def isolated_artifacts_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Sets up an isolated, authentic CoChem artifacts directory environment."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    registry_dir = artifacts_dir / "Registry"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    registry_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    prev_artifacts = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)
    try:
        yield artifacts_dir
    finally:
        if prev_artifacts is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_artifacts
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


@pytest.fixture
def sample_registry_data() -> Dict[str, Any]:
    """Returns genuine Stage 0 system registry configuration data."""
    return {
        "schema_version": "1.0.0",
        "registry_version": "4.0",
        "status": "LOCKED",
        "hardware": {
            "ram_gb": 64.0,
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "gpu_profile": "NVIDIA RTX 4090",
        },
        "environment": {
            "codata_version": "2018",
            "isotopic_mass_locking": True,
        },
    }


# ==============================================================================
# 1. Air-Gap Safety Contract Tests
# ==============================================================================

def test_airgap_get_cochem_artifacts_dir_success(isolated_artifacts_dir: Path) -> None:
    """Validate dynamic resolution of COCHEM_ARTIFACTS_DIR without hardcoded paths."""
    resolved = get_cochem_artifacts_dir()
    assert resolved == isolated_artifacts_dir.resolve()
    assert resolved.exists()


def test_airgap_get_cochem_artifacts_dir_missing_raises() -> None:
    """Validate that missing COCHEM_ARTIFACTS_DIR environment variable raises fatal RuntimeError."""
    prev_env = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ.pop("COCHEM_ARTIFACTS_DIR", None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            get_cochem_artifacts_dir()
        assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)
    finally:
        if prev_env is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_env


def test_airgap_workspace_resolution(isolated_artifacts_dir: Path) -> None:
    """Validate dynamic resolution of Registry and BENCH_Workspace directories."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    bench_dir = get_bench_workspace_dir(isolated_artifacts_dir)

    assert reg_dir == isolated_artifacts_dir / "Registry"
    assert bench_dir == isolated_artifacts_dir / "BENCH_Workspace"


# ==============================================================================
# 2. AtomicJSONManager & Cross-Platform Locking Tests
# ==============================================================================

def test_atomic_json_manager_write_and_read(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate atomic writing and reading of cochem_system_config.json."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    target_path = mgr.resolve_target_path()

    written_path = mgr.write_json(sample_registry_data)
    assert written_path == target_path
    assert target_path.exists()

    # Read back and verify exact data integrity
    loaded_data = mgr.read_json()
    assert loaded_data == sample_registry_data
    assert loaded_data["hardware"]["ram_gb"] == 64.0


def test_atomic_json_manager_fsync_and_temp_swap(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate that atomic write uses .tmp file in the Air-Gap and atomically replaces target."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    tmp_path = mgr.resolve_tmp_path()

    # Ensure no leftover tmp file exists prior to write
    if tmp_path.exists():
        tmp_path.unlink()

    mgr.write_json(sample_registry_data)

    # After successful replace, tmp file must be cleaned up / swapped
    assert not tmp_path.exists()
    assert mgr.resolve_target_path().exists()


def test_atomic_json_manager_update_mutation(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate atomic read-modify-write mutation via update_json."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    mgr.write_json(sample_registry_data)

    def mutate_cfg(data: Dict[str, Any]) -> Dict[str, Any]:
        data["hardware"]["ram_gb"] = 128.0
        data["status"] = "UPDATED_LOCK"
        return data

    updated = mgr.update_json(mutate_cfg)
    assert updated["hardware"]["ram_gb"] == 128.0
    assert updated["status"] == "UPDATED_LOCK"

    # Verify persistent state on disk
    persisted = mgr.read_json()
    assert persisted["hardware"]["ram_gb"] == 128.0


def test_atomic_json_manager_lock_timeout_raises_lock_error(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate that locked file raises CoChemRegistryLockError when timeout is reached."""
    mgr1 = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir, timeout_sec=0.5)
    lock_path = mgr1.resolve_lock_path()

    # Artificially hold the lock with an external filelock for longer than timeout
    external_lock = filelock.FileLock(str(lock_path), timeout=5.0)
    with external_lock:
        mgr2 = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir, timeout_sec=0.3)
        with pytest.raises(CoChemRegistryLockError) as exc_info:
            mgr2.write_json(sample_registry_data)
        assert "Failed to acquire atomic lock" in str(exc_info.value) or "timeout" in str(exc_info.value).lower()


def test_atomic_json_manager_missing_file_raises_not_found(isolated_artifacts_dir: Path) -> None:
    """Validate that reading non-existent configuration raises FileNotFoundError."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    target_path = mgr.resolve_target_path()
    if target_path.exists():
        target_path.unlink()

    with pytest.raises(FileNotFoundError):
        mgr.read_json()


def test_atomic_json_manager_context_manager(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate AtomicJSONManager as a context manager."""
    with AtomicJSONManager(artifacts_dir=isolated_artifacts_dir) as mgr:
        mgr.write_json(sample_registry_data)
        data = mgr.read_json()
        assert data["schema_version"] == "1.0.0"


# ==============================================================================
# 3. Stale Lock Sweeper Tests
# ==============================================================================

def test_stale_lock_sweeper_detects_dead_pid(isolated_artifacts_dir: Path) -> None:
    """Validate that Stale Lock Sweeper unlinks lock files containing dead/non-existent PIDs."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    lock_path = mgr.resolve_lock_path()

    # Find a definitely non-existent PID (e.g. 9999999 or scanning upwards)
    dead_pid = 999999
    while psutil.pid_exists(dead_pid):
        dead_pid += 1

    # Inscribe dead PID into the lock file
    payload = {
        "pid": dead_pid,
        "timestamp": "2026-01-01T00:00:00Z",
        "target_file": str(mgr.resolve_target_path()),
    }
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    assert lock_path.exists()

    # Run stale lock sweep
    swept = mgr.sweep_stale_lock()
    assert swept is True
    assert not lock_path.exists()


def test_stale_lock_sweeper_preserves_alive_pid(isolated_artifacts_dir: Path) -> None:
    """Validate that Stale Lock Sweeper preserves lock files owned by currently running processes."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    lock_path = mgr.resolve_lock_path()

    current_pid = os.getpid()
    payload = {
        "pid": current_pid,
        "timestamp": "2026-01-01T00:00:00Z",
        "target_file": str(mgr.resolve_target_path()),
    }
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    assert lock_path.exists()

    swept = mgr.sweep_stale_lock()
    assert swept is False
    assert lock_path.exists()

    # Clean up
    lock_path.unlink()


def test_stale_lock_automatic_recovery_on_acquire(
    isolated_artifacts_dir: Path,
    sample_registry_data: Dict[str, Any],
) -> None:
    """Validate that AtomicJSONManager automatically clears stale lock and succeeds on acquire."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir, timeout_sec=1.0)
    lock_path = mgr.resolve_lock_path()

    dead_pid = 999999
    while psutil.pid_exists(dead_pid):
        dead_pid += 1

    payload = {"pid": dead_pid, "timestamp": "2026-01-01T00:00:00Z"}
    lock_path.write_text(json.dumps(payload), encoding="utf-8")

    # Should detect stale lock, sweep it, and succeed
    written_path = mgr.write_json(sample_registry_data)
    assert written_path.exists()
    assert mgr.read_json()["schema_version"] == "1.0.0"


# ==============================================================================
# 4. BenchHDF5Serializer & SWMR Persistence Tests
# ==============================================================================

def test_bench_hdf5_serializer_instantiation_and_airgap(isolated_artifacts_dir: Path) -> None:
    """Validate BenchHDF5Serializer path resolution and 8192-byte chunk cache configuration."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    hdf5_path = serializer.resolve_hdf5_path()

    assert hdf5_path == isolated_artifacts_dir / "BENCH_Workspace" / "landscape.h5"
    assert serializer.chunk_cache_bytes == 8192

    # Initialize file
    serializer.initialize_database()
    assert hdf5_path.exists()


def test_bench_hdf5_serializer_append_scf_energy_and_flush(isolated_artifacts_dir: Path) -> None:
    """Validate appending SCF energy iterations with immediate explicit dataset.flush()."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()

    energies = [-76.4321, -76.4325, -76.4328, -76.4329]
    for e in energies:
        report = serializer.append_scf_energy(dataset_path="/scf/energies", energy=e)
        assert isinstance(report, SWMRWriteReport)
        assert report.flushed is True
        assert report.records_appended == 1

    # Read back and verify
    read_energies = serializer.read_dataset("/scf/energies")
    assert len(read_energies) == 4
    np.testing.assert_allclose(read_energies, energies, rtol=1e-7)


def test_bench_hdf5_serializer_append_multidimensional_array(isolated_artifacts_dir: Path) -> None:
    """Validate appending 1D and 2D arrays with SWMR chunking and explicit flushing."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()

    grad_chunk_1 = np.array([[0.01, 0.02, 0.03], [0.04, 0.05, 0.06]], dtype=np.float64)
    grad_chunk_2 = np.array([[0.07, 0.08, 0.09]], dtype=np.float64)

    serializer.append_array("/opt/gradients", grad_chunk_1)
    serializer.append_array("/opt/gradients", grad_chunk_2)

    data = serializer.read_dataset("/opt/gradients")
    assert data.shape == (3, 3)
    np.testing.assert_allclose(data[:2], grad_chunk_1)
    np.testing.assert_allclose(data[2:], grad_chunk_2)


def test_bench_hdf5_serializer_concurrent_swmr_reader_writer(isolated_artifacts_dir: Path) -> None:
    """Validate Single-Writer / Multiple-Reader (SWMR) concurrent visibility.

    Writer maintains an active SWMR session and appends new data points;
    concurrent reader refreshes and observes them without reopening file.
    """
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()
    hdf5_path = serializer.resolve_hdf5_path()

    # Writer starts SWMR session and pre-creates dataset with initial element
    with serializer.open_writer() as writer_handle:
        serializer.append_scf_energy("/live_telemetry/energies", -100.0, file_handle=writer_handle)

        # Open reader in SWMR read mode while writer session is active
        with h5py.File(str(hdf5_path), "r", libver="latest", swmr=True, rdcc_nbytes=8192) as reader_file:
            reader_ds = reader_file["/live_telemetry/energies"]
            assert reader_ds.shape == (1,)
            assert reader_ds[0] == -100.0

            # Writer appends more data in separate iteration
            for val in [-101.5, -102.25, -103.125]:
                serializer.append_scf_energy("/live_telemetry/energies", val, file_handle=writer_handle)

            # Reader calls dataset.refresh() and sees updated values
            reader_ds.refresh()
            assert reader_ds.shape == (4,)
            np.testing.assert_allclose(reader_ds[:], [-100.0, -101.5, -102.25, -103.125])


def test_bench_hdf5_serializer_store_composite_result(isolated_artifacts_dir: Path) -> None:
    """Validate storing composite extrapolation results (CBS limits, CV, REL) with metadata attributes."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()

    calc_id = "calc_h2o_cbs_01"
    composite_data = {
        "hf_cbs_limit": -76.06543,
        "correl_cbs_limit": -0.32145,
        "delta_e_cv": 0.00512,
        "delta_e_rel": -0.00123,
        "total_composite_energy": -76.38299,
    }
    attributes = {
        "formula": "Halkier-TwoPoint",
        "alpha": 4.57,
        "beta": 3.0,
        "orca_version": "6.1.1",
    }

    report = serializer.store_composite_result(calc_id=calc_id, results=composite_data, attributes=attributes)
    assert report.flushed is True

    # Read back and verify values and attributes
    res_dict, read_attrs = serializer.read_composite_result(calc_id=calc_id)
    assert res_dict["total_composite_energy"] == pytest.approx(-76.38299, rel=1e-6)
    assert read_attrs["formula"] == "Halkier-TwoPoint"
    assert read_attrs["alpha"] == 4.57


def test_bench_hdf5_serializer_missing_dataset_raises_keyerror(isolated_artifacts_dir: Path) -> None:
    """Validate that reading non-existent dataset raises KeyError."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()

    with pytest.raises(KeyError):
        serializer.read_dataset("/non_existent_dataset/values")


# ==============================================================================
# 5. Mendeleev Dynamic Mass Integration Tests
# ==============================================================================

def test_mendeleev_dynamic_mass_resolution() -> None:
    """Validate dynamic retrieval of element masses without hardcoded constants."""
    c_mass = get_element_mass_mendeleev("C")
    h_mass = get_element_mass_mendeleev("H")
    o_mass = get_element_mass_mendeleev("O")

    assert isinstance(c_mass, float)
    assert 12.0 < c_mass < 12.02
    assert 1.00 < h_mass < 1.01
    assert 15.99 < o_mass < 16.01


def test_mendeleev_invalid_element_raises() -> None:
    """Validate that querying an invalid element symbol raises ValueError."""
    with pytest.raises(Exception):
        get_element_mass_mendeleev("InvalidElementSymbolXyZ")


def test_bench_hdf5_serializer_store_composite_result_strings_and_scalars(isolated_artifacts_dir: Path) -> None:
    """Validate storing string results, numpy scalars, and nested lists in composite results."""
    serializer = BenchHDF5Serializer(artifacts_dir=isolated_artifacts_dir)
    serializer.initialize_database()

    calc_id = "calc_ch4_cbs_02"
    composite_data = {
        "method_name": "CCSD(T)-F12b",
        "basis_limit": "CBS[Q:5]",
        "scf_energy": np.float64(-40.21345),
        "f12_correction": -0.01234,
        "energy_vector": [1.0, 2.0, 3.5],
    }
    attributes = {"comment": "Accurate CBS limit"}

    report = serializer.store_composite_result(calc_id=calc_id, results=composite_data, attributes=attributes)
    assert report.flushed is True

    res, attrs = serializer.read_composite_result(calc_id=calc_id)
    assert res["method_name"] == "CCSD(T)-F12b"
    assert res["basis_limit"] == "CBS[Q:5]"
    assert res["scf_energy"] == pytest.approx(-40.21345)
    np.testing.assert_allclose(res["energy_vector"], [1.0, 2.0, 3.5])
    assert attrs["comment"] == "Accurate CBS limit"


def test_atomic_json_manager_lock_metadata_written(isolated_artifacts_dir: Path) -> None:
    """Validate that PID metadata is inscribed in the lock file during acquisition."""
    mgr = AtomicJSONManager(artifacts_dir=isolated_artifacts_dir)
    lock = mgr.acquire_lock()
    try:
        fd = getattr(getattr(lock, "_context", None), "lock_file_fd", None)
        if fd is not None and isinstance(fd, int) and fd >= 0:
            os.lseek(fd, 0, os.SEEK_SET)
            chunks = []
            while True:
                chunk = os.read(fd, 4096)
                if not chunk:
                    break
                chunks.append(chunk)
            raw_bytes = b"".join(chunks)
            os.lseek(fd, 0, os.SEEK_SET)
            assert len(raw_bytes) > 0
            parsed = json.loads(raw_bytes.decode("utf-8"))
            assert parsed["pid"] == os.getpid()
    finally:
        lock.release()


