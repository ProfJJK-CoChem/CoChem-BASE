# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Inter-Process Lock Acquisition Timeouts & Stale Lock Eviction in Cascade HDF5.
Validates Suggestion #150 (Deliverable 10) under Method Matrix v4 §8C, §8C.1 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import h5py
import pytest

from cascade_engine.cochem_cascade_hdf5 import (
    CascadeHDF5Serializer,
    DatabaseLockTimeoutError,
)


def test_cascade_hdf5_stale_lock_eviction_and_recovery(tmp_path: Path) -> None:
    """Verify that an abandoned/stale lock file (> 120s old from a dead process) is safely evicted."""
    db_path = tmp_path / "cascade.h5"
    lock_path = Path(f"{db_path}.lock")

    # Simulate an orphaned stale lock file from a non-existent deceased PID (e.g., 999999)
    # with modification time set 200 seconds in the past
    lock_path.write_text("999999", encoding="utf-8")
    past_time = time.time() - 200.0
    os.utime(lock_path, (past_time, past_time))

    # Instantiate serializer with timeout=5.0s, stale_threshold_sec=120.0s
    serializer = CascadeHDF5Serializer(db_path=db_path, timeout=5.0, stale_threshold_sec=120.0)

    # Perform physical write operation
    serializer.write_tier_data(
        geom_id="geom_water_001",
        tier_id="T1",
        energy=-76.4321,
        geometry="O 0 0 0.117\nH 0 0.757 -0.469\nH 0 -0.757 -0.469",
    )

    # Verify that data was successfully written to the HDF5 archive
    with h5py.File(db_path, "r", libver="latest", swmr=True) as f:
        grp = f["geometries/geom_water_001/T1"]
        assert grp.attrs["energy_hartree"] == pytest.approx(-76.4321, rel=1e-5)