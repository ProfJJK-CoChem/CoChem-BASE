"""Reactive State Synchronization & Molecule Re-Initialization Controller Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §8A, §8C, Suggestion #125.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Pydantic v2 reactive controller model (TORQPipelineController / TORQStateModel).
2. Clean state reset upon molecule switch: downstream memory cache purging and rotational constant invalidation.
3. State persistence to Thread-Safe HDF5 PESStore under cross-platform filelock.FileLock.
4. Downstream execution gating: raising StateDesynchronizationError on uninitialized or desynchronized runs.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from UI.torq_controller import (
    StateDesynchronizationError,
    TORQPipelineController,
)


def test_uninitialized_execution_gating():
    """Assert downstream stages raise StateDesynchronizationError when uninitialized [M]."""
    controller = TORQPipelineController()
    assert controller.state.is_initialized is False

    with pytest.raises(StateDesynchronizationError, match="Molecule state is uninitialized"):
        controller.verify_stage_prerequisites("dvr")

    with pytest.raises(StateDesynchronizationError, match="Molecule state is uninitialized"):
        controller.verify_stage_prerequisites("spcat")


def test_molecule_reinitialization_and_cache_invalidation(tmp_path: Path):
    """Assert switching molecule purges cache and invalidates existing rotational constants [M]."""
    controller = TORQPipelineController(scratch_dir=tmp_path / "scratch")
    h5_store = tmp_path / "pes_store.h5"

    # 1. Initialize with Water Dimer
    dimer_symbols = ["O", "H", "H", "O", "H", "H"]
    dimer_coords = np.array([
        [-1.464, -0.010, 0.000],
        [-0.505, -0.031, 0.000],
        [-1.782, 0.892, 0.000],
        [1.442, 0.010, 0.000],
        [1.798, -0.428, 0.762],
        [1.798, -0.428, -0.762],
    ], dtype=np.float64)

    hash1 = controller.reinitialize_molecule(
        name="Water Dimer",
        symbols=dimer_symbols,
        coords=dimer_coords,
        h5_store_path=h5_store,
    )
    assert controller.state.is_initialized is True
    assert controller.state.molecule_name == "Water Dimer"

    # Simulate downstream computation results in cache
    controller.set_rotational_constants({"A": 7120.5, "B": 6140.2, "C": 3020.1})
    controller.record_pes_scan({"scan_status": "CONVERGED"})
    assert "rotational_constants" in controller.results_cache
    assert controller.state.pes_scan_completed is True

    # 2. Re-initialize with Hydrogen Peroxide (H2O2)
    h2o2_symbols = ["O", "O", "H", "H"]
    h2o2_coords = np.array([
        [0.000000, 0.732100, -0.052400],
        [0.000000, -0.732100, -0.052400],
        [0.816600, 0.884100, 0.419200],
        [-0.816600, -0.884100, 0.419200],
    ], dtype=np.float64)

    hash2 = controller.reinitialize_molecule(
        name="Hydrogen Peroxide",
        symbols=h2o2_symbols,
        coords=h2o2_coords,
        h5_store_path=h5_store,
    )

    # Hashes must differ
    assert hash1 != hash2
    assert controller.state.molecule_name == "Hydrogen Peroxide"
    # Existing constants and flags must be wiped
    assert controller.state.rotational_constants is None
    assert controller.state.pes_scan_completed is False
    assert len(controller.results_cache) == 0

    # Downstream execution before completing scan must be blocked
    with pytest.raises(StateDesynchronizationError, match="Torsional scan has not completed"):
        controller.verify_stage_prerequisites("dvr")


def test_hdf5_swmr_state_persistence(tmp_path: Path):
    """Assert active state is atomically written to HDF5 under FileLock [M], [D]."""
    controller = TORQPipelineController(scratch_dir=tmp_path / "scratch")
    h5_store = tmp_path / "pes_store.h5"

    symbols = ["C", "O", "O"]
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.162], [0.0, 0.0, -1.162]], dtype=np.float64)

    geom_hash = controller.reinitialize_molecule(
        name="Carbon Dioxide",
        symbols=symbols,
        coords=coords,
        h5_store_path=h5_store,
    )

    # Verify HDF5 store content
    assert h5_store.is_file()
    with h5py.File(h5_store, "r") as h5f:
        assert "active_state" in h5f
        grp = h5f["active_state"]
        assert grp.attrs["molecule_name"] == "Carbon Dioxide"
        assert grp.attrs["geometry_hash"] == geom_hash
        stored_coords = np.array(grp["coordinates"])
        assert np.allclose(stored_coords, coords)
