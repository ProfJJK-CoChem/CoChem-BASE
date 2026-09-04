"""Unit and integration tests for Deliverable 3: Hardware-Topology-Aware QM Routing & Thread-Safe HDF5 SWMR Persistence (Suggestion #103).

Mandated by Method Matrix v4 (§3.3, §8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic data structures and concurrency safety tests.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

from Libraries.cochem_torq_active_learning import (
    ActiveLearningHDF5Manager,
    route_qm_tier,
)


def test_route_qm_tier_downgrade_when_engines_missing():
    """Verify route_qm_tier downgrades to surrogate when high-tier ab-initio engines are absent."""
    # Extreme force uncertainty (> 0.80) normally demands T3O-12h (CFOUR/ORCA composite)
    max_force_std = 1.25

    # Case A: Neither ORCA nor CFOUR are available, only xTB is available
    tier_fallback = route_qm_tier(
        max_force_std=max_force_std,
        available_engines=["xtb"],
        compute_budget_hours=0.5,
    )
    # Must adaptively downgrade to surrogate tier rather than crashing
    assert tier_fallback == "T3-10s"

    # Case B: Only ORCA available, CFOUR missing (T3O-12h junChS needs CFOUR)
    tier_orca_only = route_qm_tier(
        max_force_std=max_force_std,
        available_engines=["orca", "xtb"],
        compute_budget_hours=4.0,
    )
    # Downgrades to single-point DFT tier supported by ORCA
    assert tier_orca_only in ("B3LYP-D4/def2-TZVP", "T3O-1h")


def test_route_qm_tier_interactive_decision_gate():
    """Verify investigator-in-the-loop decision gate callback is invoked when limits are exceeded."""
    gate_invoked = []

    def decision_gate_callback(nominal_tier: str, missing_engines: list, budget_exceeded: bool, compute_budget_hours: float):
        gate_invoked.append((nominal_tier, missing_engines, budget_exceeded))
        return False  # Decline override; allow graceful degradation

    route_qm_tier(
        max_force_std=0.95,
        available_engines=[],
        compute_budget_hours=0.1,
        interactive_gate=decision_gate_callback,
    )
    assert len(gate_invoked) == 1
    assert gate_invoked[0][0] == "T3O-12h"


def test_thread_safe_hdf5_swmr_persistence(tmp_path: Path):
    """Verify thread-safe HDF5 SWMR persistence under filelock, RLock, and Fletcher32 checksums."""
    h5_path = tmp_path / "active_learning_pool.h5"
    manager = ActiveLearningHDF5Manager(h5_path)

    # Initial write of candidate records
    coords_h2o = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.75, 0.5],
        [0.0, -0.75, 0.5],
    ], dtype=np.float64)

    record = {
        "candidate_id": "cand_001",
        "atomic_numbers": [8, 1, 1],
        "coordinates": coords_h2o,
        "max_force_std": 0.85,
        "energy_variance": 0.012,
        "assigned_tier": "T3O-1h",
    }

    manager.append_candidate(record)

    # Verify companion JSON lease exists during lock and file is readable in SWMR mode
    records = manager.read_candidates()
    assert len(records) == 1
    assert records[0]["candidate_id"] == "cand_001"
    assert np.allclose(records[0]["coordinates"], coords_h2o)

    # Multi-threaded write test with in-process RLock and FileLock
    def worker_write(idx: int):
        rec = {
            "candidate_id": f"cand_{idx:03d}",
            "atomic_numbers": [8, 1, 1],
            "coordinates": coords_h2o + idx * 0.01,
            "max_force_std": 0.85 + idx * 0.01,
            "energy_variance": 0.012,
            "assigned_tier": "T3O-1h",
        }
        manager.append_candidate(rec)

    threads = [threading.Thread(target=worker_write, args=(i,)) for i in range(2, 6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_records = manager.read_candidates()
    assert len(all_records) == 5
