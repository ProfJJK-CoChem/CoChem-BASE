"""Unit tests for Async Context Isolation via ContextVar & Storage Tier Locking.
Strictly adheres to Zero-Mock mandate and Tripartite Air-Gap enforcement.
"""

import asyncio
import pathlib
import uuid
from dataclasses import FrozenInstanceError
from typing import Tuple

import pytest

from cochem.core.context import (
    AirGapViolationError,
    AtomicWrite,
    ExecutionContext,
    FileLock,
    assert_writable_path,
    get_current_context,
    scoped_context,
)


@pytest.fixture
def sample_environment_layout(tmp_path: pathlib.Path) -> ExecutionContext:
    """Create authentic directory layout for Tripartite Storage testing."""
    src_dir = tmp_path / "cochem_src"
    data_dir = tmp_path / "cochem_data"
    artifacts_dir = tmp_path / "cochem_artifacts"
    exec_id = str(uuid.uuid4())
    scratch_dir = artifacts_dir / f"cochem_exec_{exec_id}"

    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Place authentic reference file in data
    (data_dir / "elements.db").write_text("authentic_elements_db", encoding="utf-8")

    return ExecutionContext(
        execution_id=exec_id,
        session_name="test_session_context",
        src_dir=src_dir,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
        env_tier="Tier 1A",
        metadata={"runner": "pytest_local"},
    )


def test_execution_context_immutability(sample_environment_layout: ExecutionContext) -> None:
    """Verify ExecutionContext is frozen and rejects attribute mutation."""
    ctx = sample_environment_layout
    assert ctx.env_tier == "Tier 1A"

    with pytest.raises((FrozenInstanceError, AttributeError)):
        ctx.env_tier = "Tier 5"  # type: ignore[misc]


def test_scoped_context_sync_propagation(sample_environment_layout: ExecutionContext) -> None:
    """Verify scoped_context context manager isolates and propagates ExecutionContext."""
    ctx = sample_environment_layout

    with pytest.raises(RuntimeError, match="No active ExecutionContext found"):
        get_current_context()

    with scoped_context(ctx):
        active = get_current_context()
        assert active.execution_id == ctx.execution_id
        assert active.session_name == "test_session_context"

    with pytest.raises(RuntimeError, match="No active ExecutionContext found"):
        get_current_context()


def test_scoped_context_async_propagation(sample_environment_layout: ExecutionContext) -> None:
    """Verify scoped_context propagates across async task boundaries."""
    ctx = sample_environment_layout

    async def worker_task(task_id: int) -> str:
        active = get_current_context()
        await asyncio.sleep(0.01)
        return f"task_{task_id}_{active.execution_id}"

    async def main() -> Tuple[str, str]:
        with scoped_context(ctx):
            res1 = await worker_task(1)
            res2 = await worker_task(2)
            return res1, res2

    res1, res2 = asyncio.run(main())
    assert res1 == f"task_1_{ctx.execution_id}"
    assert res2 == f"task_2_{ctx.execution_id}"


def test_airgap_violation_detection(sample_environment_layout: ExecutionContext) -> None:
    """Verify assert_writable_path raises AirGapViolationError for src and data tiers."""
    ctx = sample_environment_layout

    with scoped_context(ctx):
        # Attempt to write to $COCH_SRC -> Must fail
        illegal_src_target = ctx.src_dir / "illegal_module.py"
        with pytest.raises(AirGapViolationError, match="Air-Gap Violation"):
            assert_writable_path(illegal_src_target)

        # Attempt to write to $COCH_DATA -> Must fail
        illegal_data_target = ctx.data_dir / "corrupted_baseline.h5"
        with pytest.raises(AirGapViolationError, match="Air-Gap Violation"):
            assert_writable_path(illegal_data_target)

        # Writing to $COCH_ARTIFACTS or scratch_dir -> Must succeed
        valid_artifact = ctx.artifacts_dir / "pes_landscape.h5"
        assert_writable_path(valid_artifact)

        valid_scratch = ctx.scratch_dir / "orca_calc.inp"
        assert_writable_path(valid_scratch)


def test_atomic_write_creates_file_safely(sample_environment_layout: ExecutionContext) -> None:
    """Verify AtomicWrite writes to temporary staging file and atomically replaces target."""
    ctx = sample_environment_layout
    target_file = ctx.artifacts_dir / "final_results.json"

    with scoped_context(ctx):
        with AtomicWrite(target_file) as tmp_path:
            assert tmp_path.exists()
            assert tmp_path.name.endswith(".tmp")
            tmp_path.write_text('{"energy": -76.432}', encoding="utf-8")

        assert target_file.exists()
        assert target_file.read_text(encoding="utf-8") == '{"energy": -76.432}'


def test_atomic_write_blocks_src_airgap(sample_environment_layout: ExecutionContext) -> None:
    """Verify AtomicWrite rejects attempts to write into read-only $COCH_SRC tier."""
    ctx = sample_environment_layout
    illegal_target = ctx.src_dir / "injected_code.py"

    with scoped_context(ctx):
        with pytest.raises(AirGapViolationError):
            with AtomicWrite(illegal_target) as tmp:
                tmp.write_text("malicious", encoding="utf-8")


def test_file_lock_local_tier_and_hpc_prohibition(sample_environment_layout: ExecutionContext) -> None:
    """Verify FileLock works on local tiers but strictly forbids distributed locks on HPC tiers."""
    ctx_local = sample_environment_layout
    lock_file = ctx_local.scratch_dir / "task.lock"

    # Local Tier 1A: Locking succeeds
    with scoped_context(ctx_local):
        with FileLock(lock_file, timeout_sec=2.0):
            assert lock_file.exists()

    # HPC Tier 5 / Tier 6: Distributed file locking is strictly prohibited
    hpc_ctx = ExecutionContext(
        execution_id=ctx_local.execution_id,
        session_name="hpc_session",
        src_dir=ctx_local.src_dir,
        data_dir=ctx_local.data_dir,
        artifacts_dir=ctx_local.artifacts_dir,
        scratch_dir=ctx_local.scratch_dir,
        env_tier="Tier 5",
        metadata={},
    )

    with scoped_context(hpc_ctx):
        with pytest.raises(RuntimeError, match="Distributed POSIX/Windows file locks are prohibited in HPC"):
            with FileLock(lock_file, timeout_sec=1.0):
                assert lock_file is not None
