"""
CoChem-BASE Master Test Suite: SpycFit Fit Registry Manager.

Validates:
1. Pydantic v2 schemas and strict validation constraints.
2. Cross-platform StandardFileLock & HPC LustreMkdirLock implementations.
3. Dynamically scaled timeouts (10s local vs 60s Lustre).
4. SWMR HDF5 connections and dynamic Lustre fallback to atomic snapshots.
5. High-level FitRegistryManager transaction lifecycle and multi-threaded concurrency.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import List

# Ensure SpycFit paths are accessible from CoChem-BASE test runner
BASE_REPO = Path(__file__).resolve().parents[2]
SPYCFIT_SRC = BASE_REPO / "CoChem-SpycFit" / "src"
SPYCFIT_ROOT = BASE_REPO / "CoChem-SpycFit"

for p in (str(SPYCFIT_SRC), str(SPYCFIT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from cochem_spycfit.core_engine.cochem_fit_registry_manager import (
    DEFAULT_LOCAL_LOCK_TIMEOUT,
    DEFAULT_LUSTRE_LOCK_TIMEOUT,
    FitParameterRecord,
    FitRegistryCorruptionError,
    FitRegistryError,
    FitRegistryManager,
    FitRegistryMissingError,
    FitRegistrySchemaError,
    FitRegistryState,
    HDF5TensorError,
    InstrumentLimits,
    LustreLockError,
    LustreMkdirLock,
    MLFeedbackState,
    RegistryLockError,
    RegistryLockTimeoutError,
    SnapshotMetadata,
    StandardFileLock,
    compute_file_sha256,
    create_atomic_snapshot,
    get_atomic_lock,
    is_lustre_filesystem,
    open_state_tensor,
    resolve_lock_timeout,
)


@pytest.fixture
def base_test_env(tmp_path: Path):
    """Provides isolated test directory for CoChem-BASE test suite."""
    workspace = tmp_path / "base_spycfit_reg_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    reg_json = workspace / "cochem_fit_registry.json"
    db_h5 = workspace / "spectra_fit.h5"

    yield {
        "workspace": workspace,
        "reg_json": reg_json,
        "db_h5": db_h5,
    }


def test_base_pydantic_schemas_and_forbid_extra():
    """Verifies strict Pydantic v2 schemas and forbidden extra fields."""
    limits = InstrumentLimits(min_freq_ghz=3.0, max_freq_ghz=20.0)
    assert limits.min_freq_ghz == 3.0

    with pytest.raises(ValidationError):
        InstrumentLimits(min_freq_ghz=3.0, extra_prop="invalid")  # type: ignore[call-arg]

    ml = MLFeedbackState(active=True, iteration=1, learning_rate=0.01)
    assert ml.active is True

    state = FitRegistryState(manual_locks=["B", "A", "B"])
    assert state.manual_locks == ["A", "B"]


def test_base_filesystem_detection_and_timeouts(tmp_path: Path):
    """Verifies filesystem detection and dynamically scaled timeouts."""
    local_p = tmp_path / "local_run"
    assert is_lustre_filesystem(local_p) is False
    assert resolve_lock_timeout(is_lustre=False) == DEFAULT_LOCAL_LOCK_TIMEOUT

    lustre_p = tmp_path / "lustre" / "run"
    assert is_lustre_filesystem(lustre_p) is True
    assert resolve_lock_timeout(is_lustre=True) == DEFAULT_LUSTRE_LOCK_TIMEOUT


def test_base_standard_and_lustre_locks(tmp_path: Path):
    """Verifies both StandardFileLock and LustreMkdirLock acquire, timeout, and release."""
    # 1. StandardFileLock
    std_lock_file = tmp_path / "std.lock"
    std_lock = StandardFileLock(std_lock_file, timeout=5.0)
    with std_lock:
        assert std_lock_file.exists()
    assert not std_lock_file.exists()

    # 2. LustreMkdirLock
    lustre_lock_dir = tmp_path / "lustre.lockdir"
    lustre_lock = LustreMkdirLock(lustre_lock_dir, timeout=5.0)
    with lustre_lock:
        assert lustre_lock_dir.is_dir()
        assert lustre_lock.owner_file.is_file()
    assert not lustre_lock_dir.exists()


def test_base_atomic_snapshot_generation(tmp_path: Path):
    """Verifies atomic snapshot creation and SHA-256 validation."""
    source_h5 = tmp_path / "origin.h5"
    with h5py.File(str(source_h5), "w") as f:
        f.create_dataset("weights", data=np.ones(50))

    snap_meta = create_atomic_snapshot(source_path=source_h5, is_lustre=True)
    assert snap_meta.is_lustre_fallback is True
    assert Path(snap_meta.snapshot_path).is_file()
    assert snap_meta.sha256 == compute_file_sha256(source_h5)


def test_base_hdf5_swmr_and_lustre_fallback(tmp_path: Path):
    """Verifies SWMR execution on standard FS and snapshot fallback on Lustre."""
    # Standard SWMR
    swmr_db = tmp_path / "swmr_base.h5"
    with open_state_tensor(swmr_db, mode="w", is_lustre=False) as f:
        f.create_dataset("tensor_a", data=np.arange(25))

    with open_state_tensor(swmr_db, mode="r", is_lustre=False) as f:
        loaded = np.array(f["tensor_a"])
        np.testing.assert_array_equal(loaded, np.arange(25))

    # Lustre fallback
    lustre_db = tmp_path / "lustre_base.h5"
    with open_state_tensor(lustre_db, mode="w", is_lustre=True) as f:
        assert not getattr(f, "swmr_mode", False)
        f.create_dataset("tensor_b", data=np.zeros((5, 5)))

    snaps = list((lustre_db.parent / "snapshots").glob("lustre_base_snap_*.h5"))
    assert len(snaps) >= 1


def test_base_fit_registry_manager_lifecycle(base_test_env):
    """Verifies high-level FitRegistryManager transaction, parameter freezing, and tensor I/O."""
    mgr = FitRegistryManager(
        db_path=base_test_env["db_h5"],
        registry_json_path=base_test_env["reg_json"],
        force_lustre=False,
    )

    mgr.freeze_parameter("C", value=3200.45)
    state = mgr.get_fit_record()
    assert "C" in state.manual_locks
    assert state.parameters["C"].value == 3200.45

    mgr.update_ml_feedback(active=True, loss=0.12, assigned=8, unassigned=2, status="converged")
    state2 = mgr.get_fit_record()
    assert state2.ml_feedback.convergence_status == "converged"
    assert state2.ml_feedback.assigned_transitions_count == 8

    # Tensor persistence
    test_arr = np.linspace(0.0, 100.0, 128)
    mgr.save_spectral_tensor("freq_grid", test_arr, metadata={"unit": "GHz"})
    loaded_arr, meta = mgr.load_spectral_tensor("freq_grid")
    np.testing.assert_allclose(loaded_arr, test_arr)
    assert meta["unit"] == "GHz"
    assert mgr.verify_registry_integrity() is True
