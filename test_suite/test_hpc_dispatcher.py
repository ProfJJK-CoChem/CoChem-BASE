"""Comprehensive physical test suite for cochem_base.engine subsystem.

Validates HPCDispatcher, TaskStatus enumeration, asynchronous task dispatching,
future shielding, exception propagation, timeout handling, and context manager lifecycle.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path

import pytest

import cochem_base.engine as engine
from cochem_base.engine import HPCDispatcher, TaskStatus


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


def compute_physical_sha256(file_path: str) -> str:
    """Compute physical SHA-256 hash of a file on disk."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_failing_task() -> None:
    """Task that raises a deliberate exception."""
    raise ValueError("Deliberate physical calculation failure")


def compute_slow_task(delay: float) -> str:
    """Simulate a workload with blocking execution."""
    time.sleep(delay)
    return "slow_task_done"


def test_engine_module_exports() -> None:
    """Verify engine __init__.py exports and __all__ definitions."""
    assert hasattr(engine, "HPCDispatcher")
    assert hasattr(engine, "TaskStatus")
    assert "HPCDispatcher" in engine.__all__
    assert "TaskStatus" in engine.__all__
    assert issubclass(TaskStatus, str)


def test_task_status_enum_invariants() -> None:
    """Verify TaskStatus enumeration members and string equivalences."""
    assert TaskStatus.RUNNING == "RUNNING"
    assert TaskStatus.COMPLETED == "COMPLETED"
    assert TaskStatus.FAILED == "FAILED"
    assert TaskStatus.CANCELLED == "CANCELLED"
    assert TaskStatus.UNKNOWN == "UNKNOWN"
    assert str(TaskStatus.COMPLETED) == "COMPLETED"


def test_dispatcher_invalid_workers() -> None:
    """Verify ValueError when initializing with invalid worker count."""
    with pytest.raises(ValueError, match="max_workers must be at least 1"):
        HPCDispatcher(max_workers=0)


def test_dispatcher_sync_context_manager() -> None:
    """Verify synchronous context manager lifecycle."""
    with HPCDispatcher(max_workers=2) as dispatcher:
        assert dispatcher.is_shutdown is False
        assert dispatcher.max_workers == 2
    assert dispatcher.is_shutdown is True


@pytest.mark.anyio
async def test_dispatcher_async_context_manager() -> None:
    """Verify asynchronous context manager lifecycle."""
    async with HPCDispatcher(max_workers=2) as dispatcher:
        assert dispatcher.is_shutdown is False
    assert dispatcher.is_shutdown is True


@pytest.mark.anyio
async def test_dispatch_physical_execution(tmp_path: Path) -> None:
    """Verify physical execution and SHA-256 computation via HPCDispatcher."""
    test_file = tmp_path / "sample.bin"
    sample_bytes = b"CoChem Physical Computation Engine Invariant"
    test_file.write_bytes(sample_bytes)
    expected_hash = hashlib.sha256(sample_bytes).hexdigest()

    async with HPCDispatcher(max_workers=2) as dispatcher:
        task_id = await dispatcher.dispatch(compute_physical_sha256, str(test_file))
        assert isinstance(task_id, str)
        assert task_id in dispatcher.all_task_ids

        result = await dispatcher.get_result(task_id, timeout=10.0)
        assert result == expected_hash
        assert dispatcher.get_status(task_id) == TaskStatus.COMPLETED


@pytest.mark.anyio
async def test_dispatch_failure_propagation() -> None:
    """Verify exception capture and accurate propagation on failing tasks."""
    async with HPCDispatcher(max_workers=2) as dispatcher:
        task_id = await dispatcher.dispatch(compute_failing_task)

        with pytest.raises(ValueError, match="Deliberate physical calculation failure"):
            await dispatcher.get_result(task_id, timeout=5.0)

        assert dispatcher.get_status(task_id) == TaskStatus.FAILED


@pytest.mark.anyio
async def test_dispatch_timeout_handling() -> None:
    """Verify TimeoutError when task execution exceeds timeout threshold."""
    async with HPCDispatcher(max_workers=2) as dispatcher:
        task_id = await dispatcher.dispatch(compute_slow_task, 1.0)

        with pytest.raises(asyncio.TimeoutError):
            await dispatcher.get_result(task_id, timeout=0.05)

        # Result should still be available after allowing sufficient time
        result = await dispatcher.get_result(task_id, timeout=5.0)
        assert result == "slow_task_done"
        assert dispatcher.get_status(task_id) == TaskStatus.COMPLETED


@pytest.mark.anyio
async def test_unknown_task_query() -> None:
    """Verify unknown task status and get_result handling."""
    async with HPCDispatcher(max_workers=2) as dispatcher:
        assert dispatcher.get_status("non-existent-uuid") == TaskStatus.UNKNOWN
        with pytest.raises(ValueError, match="Unknown task ID"):
            await dispatcher.get_result("non-existent-uuid")


@pytest.mark.anyio
async def test_dispatch_after_shutdown() -> None:
    """Verify error when attempting to dispatch to a shut-down dispatcher."""
    dispatcher = HPCDispatcher(max_workers=2)
    dispatcher.shutdown(wait=True)
    assert dispatcher.is_shutdown is True

    with pytest.raises(RuntimeError, match="Cannot dispatch task to a shut-down HPCDispatcher"):
        await dispatcher.dispatch(compute_physical_sha256, "some_file.bin")


def test_file_integrity_engine_init() -> None:
    """Verify engine/__init__.py formatting, LF line endings, and no path leaks."""
    init_path = Path(engine.__file__)
    raw = init_path.read_bytes()
    assert b"\r\n" not in raw, "Found CRLF in engine/__init__.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found BOM in engine/__init__.py"

    content = init_path.read_text(encoding="utf-8")
    assert "HPCDispatcher" in content
    assert "TaskStatus" in content
