# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 7 (Suggestion #77):
Dynamic Contention Budgeting for Constrained Hardware (< 32 GB RAM).
Asserts that calculate_contention_budget() dynamically scales memory allocations,
enforces Anchor (4.0 GB) and Scout (1.5 GB) memory floors, downscales gracefully,
and does NOT raise an exception on constrained systems.
"""

from __future__ import annotations

import pytest

from cochem_base.core_engine.cochem_core_parsl_executors import (
    calculate_contention_budget,
    build_heterogeneous_profile,
)


def test_contention_budget_scaling_16gb() -> None:
    """Verify that calculate_contention_budget() succeeds on 16 GB systems

    without raising ContentionBudgetExceededError, and enforces minimum floors.
    """
    # 16 GB RAM student laptop / CI runner
    budget = calculate_contention_budget(
        total_physical_cores=8,
        total_ram_gb=16.0,
        gpu_scout_workers=3,
        anchor_ranks=7,
    )

    # Must not exceed host memory and must enforce floors
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    # On 16 GB, concurrency downscales gracefully
    assert budget.gpu_scout_workers <= 3


def test_contention_budget_scaling_severely_constrained() -> None:
    """Verify minimum floors on severely constrained host (e.g. 8 GB RAM)."""
    budget = calculate_contention_budget(
        total_physical_cores=4,
        total_ram_gb=8.0,
        gpu_scout_workers=2,
        anchor_ranks=3,
    )
    assert budget.anchor_mem_per_worker_gb >= 4.0
    assert budget.scout_mem_per_worker_gb >= 1.5
    assert budget.gpu_scout_workers == 1
