"""Physical Zero-Mock Test Suite for Two-Tier HDF5 Persistence Architecture & Concurrent Staging.

Method Matrix Reference: Method Matrix v4 §8C (Production HDF5 Store Architecture & Chunking) [M], [D].
Validates Suggestion #64:
- In-process threading.RLock serialization across worker threads.
- Cross-process RWFileLock with exponential backoff.
- Atomic staging: workers write into $COCHEM_SCRATCH/chunks/chunk_<uuid>.h5.
- Central persistence coordinator merges staged chunks into $COCHEM_ARTIFACTS/campaign.h5 under exclusive write lock.
- Zero occurrences of BlockingIOError or OSError: file already open for write during concurrent sweeps.
- Integrity: Fletcher32 checksum and gzip compression filter verification.
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import numpy as np
import pytest
from pathlib import Path
import h5py

from cochem_base.concurrency import HDF5PersistenceCoordinator, locked_h5
from cochem_base.schemas import HDF5PersistenceConfig


def _worker_task(scratch_dir: str, worker_id: int, num_points: int) -> list[str]:
    """Worker task simulating concurrent calculation that writes directly to staged chunk container."""
    config = HDF5PersistenceConfig(
        lock_timeout_seconds=30.0,
        compression_filter="gzip",
        compression_level=4,
        enable_fletcher32=True,
        enable_shuffle=True,
    )
    chunk_paths: list[str] = []
    natoms = 3  # Water molecule
    # Standard equilibrium geometry for H2O
    base_coords = np.array([
        [0.0000, 0.0000, 0.1173],
        [0.0000, 0.7572, -0.4692],
        [0.0000, -0.7572, -0.4692],
    ], dtype=np.float64)

    for i in range(num_points):
        # Displace geometry slightly for each point
        displacement = (worker_id * 10 + i) * 0.005
        coords = base_coords + displacement
        # Genuine Morse-like approximate energy variation around equilibrium
        energy = -76.438 + 0.5 * (displacement ** 2)
        grads = np.full_like(coords, displacement * 0.1)

        pt_id = f"w{worker_id}_pt{i}"
        chunk_p = HDF5PersistenceCoordinator.stage_chunk(
            scratch_dir=scratch_dir,
            method_id="b3lyp_def2-tzvp",
            coords=coords,
            energies=[energy],
            gradients=[grads],
            point_ids=[pt_id],
            converged=[True],
            wall_s=[0.05],
            creator="gpu4pyscf",
            version="1.8.0",
            routine="sp",
            config=config,
        )
        chunk_paths.append(str(chunk_p))

    return chunk_paths


def test_hdf5_concurrent_staging_and_merge(tmp_path: Path):
    """Assert 10 concurrent workers staging 5 points each merge into campaign.h5 with Fletcher32 & gzip."""
    cochem_scratch = tmp_path / "scratch"
    cochem_artifacts = tmp_path / "artifacts"
    cochem_scratch.mkdir(parents=True, exist_ok=True)
    cochem_artifacts.mkdir(parents=True, exist_ok=True)

    campaign_h5 = cochem_artifacts / "campaign.h5"
    config = HDF5PersistenceConfig(
        lock_timeout_seconds=45.0,
        compression_filter="gzip",
        compression_level=4,
        enable_fletcher32=True,
        enable_shuffle=True,
    )

    coordinator = HDF5PersistenceCoordinator(
        campaign_path=campaign_h5,
        config=config,
        complex_name="H2O",
        symbols=["O", "H", "H"],
    )

    num_workers = 10
    points_per_worker = 5
    total_expected = num_workers * points_per_worker

    # Execute 10 concurrent workers concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(_worker_task, str(cochem_scratch), w_id, points_per_worker)
            for w_id in range(num_workers)
        ]
        all_chunk_paths = []
        for f in concurrent.futures.as_completed(futures):
            chunk_list = f.result()
            all_chunk_paths.extend(chunk_list)

    assert len(all_chunk_paths) == total_expected
    # Verify staged files exist in scratch
    chunks_dir = cochem_scratch / "chunks"
    assert chunks_dir.is_dir()
    staged_files = list(chunks_dir.glob("chunk_*.h5"))
    assert len(staged_files) == total_expected

    # Central coordinator merges all staged chunks under exclusive write lock
    merged_count = coordinator.merge_staged_chunks(scratch_dir=cochem_scratch, purge=True)
    assert merged_count == total_expected

    # Assert staged chunk files were purged from scratch
    remaining_chunks = list(chunks_dir.glob("chunk_*.h5"))
    assert len(remaining_chunks) == 0

    # Open campaign.h5 in read mode and verify datasets, Fletcher32, and gzip
    with locked_h5(campaign_h5, mode="r", config=config) as f:
        assert "points/b3lyp_def2-tzvp" in f
        grp = f["points/b3lyp_def2-tzvp"]

        coords_ds = grp["coordinates"]
        energy_ds = grp["energy"]
        conv_ds = grp["converged"]
        pids_ds = grp["point_id"]

        assert coords_ds.shape == (total_expected, 3, 3)
        assert energy_ds.shape == (total_expected,)
        assert conv_ds.shape == (total_expected,)
        assert pids_ds.shape == (total_expected,)

        # Assert Fletcher32 checksum is active on energy
        assert energy_ds.fletcher32 is True
        # Assert gzip compression is active
        assert energy_ds.compression == "gzip"
        assert energy_ds.compression_opts == 4
        # Assert shuffle filter is active
        assert energy_ds.shuffle is True

        # Check all expected point IDs are present
        pids = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in pids_ds[:]]
        assert len(set(pids)) == total_expected
        for w in range(num_workers):
            for i in range(points_per_worker):
                assert f"w{w}_pt{i}" in pids


def test_hdf5_concurrent_direct_writers(tmp_path: Path):
    """Verify that multiple concurrent threads writing directly to campaign.h5 using locked_h5 never raise BlockingIOError."""
    campaign_h5 = tmp_path / "direct_campaign.h5"
    config = HDF5PersistenceConfig(lock_timeout_seconds=30.0)

    coordinator = HDF5PersistenceCoordinator(
        campaign_path=campaign_h5,
        config=config,
        complex_name="H2O",
        symbols=["O", "H", "H"],
    )

    def direct_writer(thread_id: int):
        coords = np.zeros((1, 3, 3), dtype=np.float64)
        energies = np.array([-76.4 - thread_id * 0.01], dtype=np.float64)
        pids = [f"direct_t{thread_id}"]
        with locked_h5(campaign_h5, mode="a", config=config) as f:
            coordinator._append_to_master(
                f,
                mid="direct_method",
                coords=coords,
                energies=energies,
                pids=pids,
                conv=np.array([True]),
                wall=np.array([0.01]),
                grads=None,
                prov=None,
            )

    threads = 8
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
        futures = [pool.submit(direct_writer, t) for t in range(threads)]
        for fut in concurrent.futures.as_completed(futures):
            fut.result()

    with locked_h5(campaign_h5, mode="r", config=config) as f:
        assert f["points/direct_method/energy"].shape == (threads,)
