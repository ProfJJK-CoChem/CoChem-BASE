"""
Tests for Thread-Safe HDF5 Persistence via Worker Sharding & SWMR Concurrency.
Mandated by SRS Chunk 16 (Deliverable 9, Suggestion #159):
- 4 concurrent worker processes writing to independent HDF5 shard files in T_scratch.
- Atomic reduction via merge_hdf5_shards into T_store master archive.
- Verification that aggregated master dataset contains all records without corruption.
- HPC HDF5_USE_FILE_LOCKING="FALSE" suppression test.
- SWMR write context and FileLock protection test.
"""

from __future__ import annotations

import concurrent.futures
import os
import uuid
from pathlib import Path
from typing import List

import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_pes_store import (
    PESStore,
    configure_hdf5_locking,
    create_worker_shard_path,
    merge_hdf5_shards,
    merge_pes_shards,
)


def _worker_write_shard_task(
    shard_path_str: str,
    worker_idx: int,
    base_coords: np.ndarray,
    base_energy: float,
    n_points_per_worker: int,
    symbols: List[str],
    complex_name: str,
) -> int:
    """Top-level picklable worker task that writes to an isolated HDF5 shard."""
    store = PESStore(
        path=shard_path_str,
        complex_name=complex_name,
        symbols=symbols,
        swmr_mode=True,
    )
    store.register_method("wb97x-d3", basis="def2-tzvp", functional="wB97X-D3")

    coords_batch = []
    energies_batch = []
    pids_batch = []
    for i in range(n_points_per_worker):
        disp = (worker_idx * n_points_per_worker + i) * 0.01
        c = base_coords.copy()
        c[1, 2] += disp
        coords_batch.append(c)
        energies_batch.append(base_energy + 0.001 * disp)
        pids_batch.append(f"worker_{worker_idx}_pt_{i}")

    store.add_points(
        method_id="wb97x-d3",
        coords=np.array(coords_batch),
        energies=np.array(energies_batch),
        point_ids=pids_batch,
        converged=True,
        wall_s=0.25,
    )
    return n_points_per_worker


class TestThreadSafeHDF5ShardingAndSWMR:
    """Test suite for Deliverable 9 (Suggestion #159)."""

    @pytest.fixture
    def test_environment(self, tmp_path):
        """Set up isolated Tripartite T_scratch and T_store environments."""
        scratch_dir = tmp_path / "scratch"
        store_dir = tmp_path / "store"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        store_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir, store_dir

    def test_worker_shard_path_generation(self, test_environment):
        """Verify per-worker isolated shard naming convention in T_scratch."""
        scratch_dir, _ = test_environment
        worker_uuid = uuid.uuid4().hex[:8]
        task_id = 42

        shard_p = create_worker_shard_path(scratch_dir, worker_uuid, task_id)
        assert shard_p.parent == scratch_dir
        assert shard_p.name == f"shard_{worker_uuid}_{task_id}.h5"

    def test_hpc_file_locking_suppression(self, monkeypatch):
        """Verify that HPC environments automatically set HDF5_USE_FILE_LOCKING='FALSE'."""
        monkeypatch.delenv("SLURM_JOB_ID", raising=False)
        monkeypatch.delenv("PBS_JOBID", raising=False)
        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)

        monkeypatch.setenv("SLURM_JOB_ID", "987654")
        is_hpc = configure_hdf5_locking()
        assert is_hpc is True
        assert os.environ.get("HDF5_USE_FILE_LOCKING") == "FALSE"

        monkeypatch.delenv("SLURM_JOB_ID", raising=False)
        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)
        res = configure_hdf5_locking(force_hpc=True)
        assert res is True
        assert os.environ.get("HDF5_USE_FILE_LOCKING") == "FALSE"

        monkeypatch.delenv("HDF5_USE_FILE_LOCKING", raising=False)
        res_false = configure_hdf5_locking(force_hpc=False)
        assert res_false is False
        assert os.environ.get("HDF5_USE_FILE_LOCKING") is None

    def test_concurrent_worker_sharding_and_atomic_merge(self, test_environment):
        """
        Spawn 4 concurrent worker processes writing to independent HDF5 shard files
        in T_scratch, then merge into master T_store archive.
        """
        scratch_dir, store_dir = test_environment
        n_workers = 4
        points_per_worker = 5
        complex_name = "water_monomer"
        symbols = ["O", "H", "H"]

        base_coords = np.array([
            [0.000000, 0.000000, 0.000000],
            [0.000000, 0.757000, 0.586000],
            [0.000000, -0.757000, 0.586000],
        ], dtype=np.float64)
        base_energy = -76.425000

        shard_paths = []
        for w_idx in range(n_workers):
            w_uuid = f"worker_{w_idx}"
            s_path = create_worker_shard_path(scratch_dir, w_uuid, 0)
            shard_paths.append(str(s_path))

        with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = [
                executor.submit(
                    _worker_write_shard_task,
                    shard_paths[w_idx],
                    w_idx,
                    base_coords,
                    base_energy,
                    points_per_worker,
                    symbols,
                    complex_name,
                )
                for w_idx in range(n_workers)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == n_workers
        assert sum(results) == n_workers * points_per_worker

        for s_p in shard_paths:
            assert Path(s_p).exists()
            s_store = PESStore(s_p)
            data = s_store.dataset_full("wb97x-d3")
            assert len(data["energy"]) == points_per_worker

        target_store_path = store_dir / "archive_pes.h5"
        total_merged = merge_hdf5_shards(shard_paths, target_store_path)

        assert total_merged == n_workers * points_per_worker

        master_store = PESStore(target_store_path)
        master_data = master_store.dataset_full("wb97x-d3")
        assert len(master_data["energy"]) == n_workers * points_per_worker
        assert len(master_data["point_id"]) == n_workers * points_per_worker

        integrity = master_store.validate_integrity()
        print("INTEGRITY REPORT:", integrity)
        assert integrity["status"] == "PASSED"
        assert integrity["methods"]["wb97x-d3"]["n_points"] == n_workers * points_per_worker

        assert merge_pes_shards == merge_hdf5_shards

    def test_swmr_write_context_and_filelock(self, test_environment):
        """Verify swmr_write_context provides thread/process safe FileLock and SWMR mode."""
        _, store_dir = test_environment
        h5_path = store_dir / "monolithic_swmr.h5"

        store = PESStore(
            path=h5_path,
            complex_name="water",
            symbols=["O", "H", "H"],
            swmr_mode=True,
        )

        with store.swmr_write_context() as f:
            assert f.swmr_mode is True
            lock_p = Path(f"{h5_path}.lock")
            assert lock_p.exists()
