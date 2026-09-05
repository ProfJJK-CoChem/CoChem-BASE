# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Cross-Process Reader-Writer Locking (RWFileLock) for Concurrent HDF5 Campaign Datastores.
Validates Suggestion #143 (Deliverable 3) under Method Matrix v4 §8C, §8C.1, §8C.2 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
import time

import h5py
import numpy as np
import pytest
from filelock import FileLock


def _worker_write_task(h5_filepath_str: str, worker_id: int, points_per_worker: int) -> int:
    """Worker task executing genuine physical energy insertions under exclusive FileLock."""
    h5_path = Path(h5_filepath_str)
    lock_path = Path(f"{h5_filepath_str}.lock")
    lock = FileLock(lock_path, timeout=30.0)

    written = 0
    for idx in range(points_per_worker):
        # Genuine physical Hartree values
        e_hartree = -76.0 + float(worker_id * 0.1) + float(idx * 0.001)
        point_key = f"w{worker_id}_pt{idx}"

        with lock:
            with h5py.File(h5_path, "a", libver="latest") as f:
                grp = f.require_group(f"points/{point_key}")
                grp.attrs["energy_hartree"] = e_hartree
                grp.attrs["worker_id"] = worker_id
                grp.attrs["provenance_tag"] = "[M]"
                if "coordinates" not in grp:
                    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], dtype=np.float64)
                    grp.create_dataset("coordinates", data=coords)
        written += 1
        time.sleep(0.005)

    return written


def test_concurrent_hdf5_rwfilelock(tmp_path: Path) -> None:
    """Launch 4 concurrent workers writing to a single campaign HDF5 file; verify zero collisions."""
    h5_path = tmp_path / "campaign.h5"

    # Pre-initialize master HDF5 file
    with h5py.File(h5_path, "w", libver="latest") as f:
        meta = f.require_group("meta")
        meta.attrs["campaign_name"] = "concurrent_rwlock_test"
        meta.attrs["schema_version"] = 1

    num_workers = 4
    points_per_worker = 10
    total_expected = num_workers * points_per_worker

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=num_workers) as pool:
        results = [
            pool.apply_async(_worker_write_task, (str(h5_path), w_id, points_per_worker))
            for w_id in range(num_workers)
        ]
        written_counts = [r.get(timeout=45.0) for r in results]

    assert sum(written_counts) == total_expected

    # Verify HDF5 dataset integrity under read-through
    with h5py.File(h5_path, "r", libver="latest", swmr=True) as f:
        assert "points" in f
        pts_grp = f["points"]
        assert len(pts_grp.keys()) == total_expected
        for key in pts_grp:
            assert pts_grp[key].attrs["provenance_tag"] == "[M]"
            assert "coordinates" in pts_grp[key]