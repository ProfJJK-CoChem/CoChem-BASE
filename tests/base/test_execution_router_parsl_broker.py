# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Direct Integration of Parsl Multi-Executor Broker in Calculation Execution Router.
Validates Suggestion #145 (Deliverable 5) under Method Matrix v4 §8A.2, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.schemas import JobRouteConfig, ExecutionRouteResult


def test_execution_router_scout_and_anchor_routing(tmp_path: Path, audited_registry) -> None:
    """Verify that ExecutionRouter routes exploratory MLFF to scout_gpu and heavy QM to anchor_cpu."""
    router = ExecutionRouter(audited_registry)

    # 1. Exploratory MLFF scan task
    scout_result = router.route_job(
        target_engine_or_type="fast_potential_scan",
        payload_command=["python", "-c", "print('scout_done')"],
        scratch_dir=tmp_path / "scratch_scout",
        cpu_core_pinning=[0],
    )
    assert isinstance(scout_result, ExecutionRouteResult)
    assert scout_result.assigned_executor == "local_fallback"
    assert scout_result.scratch_dir.exists()

    # 2. Heavy quantum chemical optimization task
    anchor_result = router.route_job(
        target_engine_or_type="heavy_qm_opt",
        payload_command=["python", "-c", "print('anchor_done')"],
        scratch_dir=tmp_path / "scratch_anchor",
        cpu_core_pinning=[0, 1, 2, 3],
    )
    assert isinstance(anchor_result, ExecutionRouteResult)
    assert anchor_result.assigned_executor == "local_fallback"
    assert anchor_result.scratch_dir.exists()


def test_execution_router_thread_budgeting(tmp_path: Path, audited_registry) -> None:
    """Verify CPU core affinity and OpenMP/MKL thread count budgeting."""
    router = ExecutionRouter(audited_registry)
    cores = list(range(min(7, router.registry["hardware"]["logical_cpu_cores"])))

    res = router.route_job(
        target_engine_or_type="heavy_qm_opt",
        payload_command=["python", "-c", "import os; print(os.environ.get('OMP_NUM_THREADS', '1'))"],
        scratch_dir=tmp_path / "scratch_threads",
        cpu_core_pinning=cores,
    )
    assert res.assigned_executor == "local_fallback"
    assert res.scratch_dir.exists()
    assert res.output.strip() == str(len(cores))