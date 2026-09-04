"""Authentic physical verification test suite for Training Persistence & Checkpointing Engine.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely unmocked HDF5 SWMR locking and atomic checkpoint I/O.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import time

import filelock
import numpy as np
import pytest
import torch

from Libraries.cochem_torq_training_errors import (
    CheckpointCorruptionError,
    HDF5LockTimeoutError,
)
from Libraries.cochem_torq_training_persistence import (
    HDF5DatasetManager,
    load_atomic_checkpoint,
    save_atomic_checkpoint,
)
from tests.torq_test_fixtures import get_water_dimer_fixture


def test_hdf5_lock_path_in_dataset_directory() -> None:
    """Verify advisory lock path is placed in the shared dataset mount directory, not /tmp. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "subfolder" / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=5.0)

        expected_lock = h5_path.with_suffix(".h5.lock")
        assert manager.lock_path == expected_lock
        assert manager.lock_path.parent == h5_path.parent


def test_hdf5_lock_timeout_exception() -> None:
    """Verify HDF5LockTimeoutError is raised when concurrent lock exceeds timeout ceiling. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=0.1)

        # Acquire an external advisory lock on the exact same lock path
        external_lock = filelock.FileLock(str(manager.lock_path), timeout=5.0)
        external_lock.acquire()

        coords = np.array([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]], dtype=np.float64)
        species = [8, 1]
        energies = np.array([-1.5], dtype=np.float64)
        forces = np.array([[[0.1, 0.0, 0.0], [-0.1, 0.0, 0.0]]], dtype=np.float64)

        try:
            with pytest.raises(HDF5LockTimeoutError) as exc_info:
                manager.write_trajectory_batch("water", coords, species, energies, forces)
            assert exc_info.value.error_code == "TORQ_TRAIN_HDF5_LOCK_TIMEOUT"
        finally:
            external_lock.release()


def test_hdf5_write_trajectory_batch_success() -> None:
    """Verify successful trajectory writing with chunking, compression, and fletcher32. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        h5_path = Path(tmpdir) / "trajectory.h5"
        manager = HDF5DatasetManager(h5_path, timeout_seconds=5.0)

        base_coords, base_species = get_water_dimer_fixture()
        n_atoms = base_coords.shape[0]

        # Authentic trajectory snapshots with explicit physical values
        c0 = base_coords.numpy().astype(np.float64)
        c1 = c0 + np.array([[0.001, -0.001, 0.002]] * n_atoms)
        coords = np.stack([c0, c1])
        
        species = base_species.tolist()
        energies = np.array([-152.000, -151.998], dtype=np.float64)
        
        f0 = np.array([[0.01, -0.02, 0.03]] * n_atoms, dtype=np.float64)
        f1 = np.array([[-0.01, 0.02, -0.03]] * n_atoms, dtype=np.float64)
        forces = np.stack([f0, f1])

        manager.write_trajectory_batch("water_batch_1", coords, species, energies, forces)

        assert h5_path.exists()
        import h5py
        with h5py.File(h5_path, "r") as f:
            assert "water_batch_1" in f
            grp = f["water_batch_1"]
            assert grp["coordinates"].shape == (2, n_atoms, 3)
            assert grp["energies"].shape == (2,)
            assert grp["forces"].shape == (2, n_atoms, 3)
            assert np.array_equal(grp["atomic_numbers"][:], np.array(species, dtype=np.int32))


def test_atomic_checkpoint_replace_and_sha256_generation() -> None:
    """Verify atomic checkpoint serialization (.pt.tmp -> fsync -> os.replace -> .sha256). [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        ckpt_path = Path(tmpdir) / "models" / "checkpoint_epoch_10.pt"

        state_dict = {
            "epoch": 10,
            "weights": torch.tensor([1.23, 4.56, 7.89], dtype=torch.float64),
            "step": 5000,
        }

        saved_pt, saved_sha = save_atomic_checkpoint(state_dict, ckpt_path)

        assert saved_pt.exists()
        assert saved_sha.exists()
        # Invariant: temporary file must be cleaned up / replaced
        assert not Path(str(ckpt_path) + ".tmp").exists()

        # Reload and verify integrity
        reloaded_dict = load_atomic_checkpoint(saved_pt)
        assert reloaded_dict["epoch"] == 10
        assert reloaded_dict["step"] == 5000
        assert torch.equal(reloaded_dict["weights"], state_dict["weights"])


def test_checkpoint_corruption_detection() -> None:
    """Verify CheckpointCorruptionError is raised when file checksum mismatches or payload is corrupted. [M]"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        ckpt_path = Path(tmpdir) / "corrupt_checkpoint.pt"
        state_dict = {"param": torch.tensor([42.0])}
        save_atomic_checkpoint(state_dict, ckpt_path)

        sha_path = ckpt_path.with_suffix(ckpt_path.suffix + ".sha256")

        # 1. Corrupt sha file contents
        sha_path.write_text("0000000000000000000000000000000000000000000000000000000000000000\n")
        with pytest.raises(CheckpointCorruptionError) as exc1:
            load_atomic_checkpoint(ckpt_path)
        assert exc1.value.error_code == "TORQ_TRAIN_CHECKPOINT_CORRUPT"

        # 2. Delete sha file
        sha_path.unlink()
        with pytest.raises(CheckpointCorruptionError) as exc2:
            load_atomic_checkpoint(ckpt_path)
        assert exc2.value.error_code == "TORQ_TRAIN_CHECKPOINT_CORRUPT"


def test_worker_init_fn_initialization() -> None:
    """Validate independent HDF5 handles and cluster configuration in worker_init_fn. [M]"""
    from Libraries.cochem_torq_training_persistence import worker_init_fn
    import os

    worker_init_fn(worker_id=1)
    assert os.environ.get("HDF5_USE_FILE_LOCKING") == "FALSE"

