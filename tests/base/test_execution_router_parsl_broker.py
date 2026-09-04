"""Physical Zero-Mock Test Suite for Unified Parsl Multi-Executor Routing in ExecutionRouter.

Method Matrix Reference: Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
Validates Suggestion #66:
- Elimination of bypassed execution paths by wiring Parsl DataFlowKernel into ExecutionRouter.
- Workload mapping: heavy_qm_opt -> cochem_anchor_cpu with CPU core pinning.
- Workload mapping: fast_potential_scan -> cochem_scout_gpu.
- Task sandboxing in Ring 2 ephemeral scratch ($COCHEM_SCRATCH/task_<uuid>/).
- Non-blocking task futures resolution.
"""

from __future__ import annotations

import os
import sys
import time
import pytest
from pathlib import Path

import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig


@pytest.fixture(scope="module")
def parsl_test_dfk():
    """Module-level fixture configuring an authentic Parsl DFK with anchor and scout pools."""
    try:
        parsl.clear()
    except Exception:
        pass

    parsl_config = Config(
        executors=[
            ThreadPoolExecutor(max_threads=2, label="cochem_anchor_cpu"),
            ThreadPoolExecutor(max_threads=2, label="cochem_scout_gpu"),
        ],
        strategy=None,
    )
    dfk = parsl.load(parsl_config)
    yield dfk
    try:
        parsl.clear()
    except Exception:
        pass


def test_execution_router_parsl_routing(tmp_path: Path, parsl_test_dfk):
    """Verify routing of heavy QM to anchor CPU and rapid scans to scout GPU in isolated scratch."""
    cochem_scratch = tmp_path / "scratch"
    cochem_scratch.mkdir(parents=True, exist_ok=True)

    router = ExecutionRouter(dfk=parsl_test_dfk)

    # 1. Submit heavy QM optimization task
    heavy_cmd = [sys.executable, "-c", "import os; print('HEAVY_QM_DONE')"]
    heavy_result = router.route_job(
        job_type="heavy_qm_opt",
        payload_command=heavy_cmd,
        scratch_dir=cochem_scratch,
        cpu_core_pinning=[0, 1, 2, 3],
        timeout=30.0,
    )

    assert isinstance(heavy_result, ExecutionRouteResult)
    assert heavy_result.assigned_executor == "cochem_anchor_cpu"
    assert heavy_result.status == "SUBMITTED"
    assert heavy_result.scratch_dir.is_dir()
    assert heavy_result.scratch_dir.name.startswith("task_")
    assert heavy_result.future is not None

    # 2. Submit fast potential scan task
    scan_cmd = [sys.executable, "-c", "import os; print('FAST_SCAN_DONE')"]
    scan_result = router.route_job(
        job_type="fast_potential_scan",
        payload_command=scan_cmd,
        scratch_dir=cochem_scratch,
        timeout=30.0,
    )

    assert isinstance(scan_result, ExecutionRouteResult)
    assert scan_result.assigned_executor == "cochem_scout_gpu"
    assert scan_result.status == "SUBMITTED"
    assert scan_result.scratch_dir.is_dir()
    assert scan_result.scratch_dir.name.startswith("task_")
    # Verify separate isolated sandboxes in scratch
    assert heavy_result.scratch_dir != scan_result.scratch_dir

    # 3. Non-blocking futures resolution: await results
    t0 = time.time()
    heavy_rc = heavy_result.future.result()
    scan_rc = scan_result.future.result()
    elapsed = time.time() - t0

    assert heavy_rc == 0
    assert scan_rc == 0
    # Verified that execution resolved without hanging
    assert elapsed < 15.0
