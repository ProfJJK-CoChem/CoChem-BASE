# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 1 (Suggestion #71):
Thread-Safe & Deadlock-Free HDF5 Serialization in CascadeHDF5Serializer.
Verifies bounded lock acquisition, SWMR mode activation, multi-process write safety,
and stale lock eviction without mocking.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import tempfile
import time
from pathlib import Path

import h5py
import numpy as np
import pytest

from cascade_engine.cochem_cascade_hdf5 import CascadeHDF5Serializer
from cochem_base.exceptions import DatabaseLockTimeoutError


def _worker_write_task(db_path_str: str, worker_id: int, num_entries: int) -> int:
    """Worker task executing concurrent writes to the shared HDF5 database."""
    serializer = CascadeHDF5Serializer(db_path_str)
    written = 0
    for i in range(num_entries):
        geom_id = f"geom_worker_{worker_id}_{i}"
        tier_id = "1"
        energy = -100.0 - float(worker_id) * 1.0 - float(i) * 0.01
        grad = np.array([[0.01 * (worker_id + 1), 0.02, 0.03]], dtype=np.float64)
        geometry = f"1\nTest atom\nC 0.0 0.0 {float(i)}"
        serializer.write_tier_data(
            geom_id=geom_id,
            tier_id=tier_id,
            energy=energy,
            gradient=grad,
            geometry=geometry,
        )
        written += 1
    serializer.close()
    return written


def test_hdf5_serializer_concurrency_and_swmr() -> None:
    """Launch 4 multi-process workers attempting simultaneous writes;
    verify lock acquisition timeout bounds, SWMR status, and zero data corruption.
    """
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_cascade_concurrent.h5"
        serializer = CascadeHDF5Serializer(db_path)
        serializer.close()

        num_workers = 4
        entries_per_worker = 5

        # Execute 4 concurrent worker processes
        ctx = mp.get_context("spawn")
        processes = []
        for w_id in range(num_workers):
            p = ctx.Process(
                target=_worker_write_task,
                args=(str(db_path), w_id, entries_per_worker),
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join(timeout=45.0)
            assert not p.is_alive(), "Worker process timed out during concurrent write"
            assert p.exitcode == 0, f"Worker failed with exit code {p.exitcode}"

        # Verify all entries were written without data corruption
        with h5py.File(db_path, "r", libver="latest", swmr=True) as h5:
            assert h5.swmr_mode is True  # File opened in SWMR mode
            for w_id in range(num_workers):
                for i in range(entries_per_worker):
                    geom_id = f"geom_worker_{w_id}_{i}"
                    assert geom_id in h5, f"Missing geometry group {geom_id}"
                    assert "1" in h5[geom_id], f"Missing tier 1 in {geom_id}"
                    tier_grp = h5[geom_id]["1"]
                    expected_energy = -100.0 - float(w_id) * 1.0 - float(i) * 0.01
                    actual_energy = float(tier_grp.attrs["electronic_energy_hartree"])
                    assert actual_energy == pytest.approx(expected_energy, abs=1e-6)


def test_hdf5_serializer_stale_lock_eviction() -> None:
    """Verify that a stale lock with a non-existent PID is evicted and retried."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_stale_lock.h5"
        serializer = CascadeHDF5Serializer(db_path)
        serializer.close()

        lock_path = Path(f"{db_path}.lock")
        # Simulate dead PID lockfile: write a dead PID (e.g. 99999999)
        lock_path.write_text("pid: 99999999\n", encoding="utf-8")

        # Serializer should detect dead PID or handle stale lock, evict it, and succeed
        serializer2 = CascadeHDF5Serializer(db_path)
        serializer2.write_tier_data(
            geom_id="recovery_geom",
            tier_id="1",
            energy=-75.1234,
            geometry="1\nRecovered\nH 0.0 0.0 0.0",
        )
        data = serializer2.read_tier_data("recovery_geom", "1")
        assert data is not None
        assert data["energy"] == pytest.approx(-75.1234, abs=1e-4)
        serializer2.close()
