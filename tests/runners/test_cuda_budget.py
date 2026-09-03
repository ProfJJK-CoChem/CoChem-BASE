"""Unit tests for CUDA memory budgeter and backpressure manager."""

import os

import pytest

from src.cochem.hpc.models import CudaMemoryExhaustionError
from src.cochem.runners.cuda_budget import CudaMemoryManager


def test_cuda_memory_manager_device_count() -> None:
    """Verify physical hardware device count querying or headless fallback."""
    mgr = CudaMemoryManager()
    count = mgr.get_device_count()
    assert isinstance(count, int)
    assert count >= 0


def test_prepare_worker_environment() -> None:
    """Verify worker environment variable generation for isolated execution."""
    mgr = CudaMemoryManager()
    base_env = {"CUSTOM_VAR": "ALPHA_VAL", "PATH": os.environ.get("PATH", "")}
    env = mgr.prepare_worker_environment(device_id=3, base_env=base_env)

    assert env["CUDA_VISIBLE_DEVICES"] == "3"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    assert env["CUSTOM_VAR"] == "ALPHA_VAL"


def test_prepare_worker_environment_default() -> None:
    """Verify worker environment defaults when no base env is supplied."""
    mgr = CudaMemoryManager()
    env = mgr.prepare_worker_environment(device_id=0)
    assert env["CUDA_VISIBLE_DEVICES"] == "0"
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"


def test_acquire_vram_budget_exhaustion_timeout() -> None:
    """Verify that requesting excessive VRAM raises CudaMemoryExhaustionError on timeout."""
    import asyncio

    async def _run() -> None:
        mgr = CudaMemoryManager()
        # Request an impossible amount of VRAM (100 TB) with small timeout
        with pytest.raises(CudaMemoryExhaustionError) as exc_info:
            await mgr.acquire_vram_budget(
                device_id=0,
                required_mb=100_000_000,
                timeout_seconds=0.3,
                poll_interval=0.1,
            )
        assert "exhausted" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()

    asyncio.run(_run())


def test_acquire_vram_budget_invalid_device() -> None:
    """Verify requesting VRAM on a non-existent device raises CudaMemoryExhaustionError."""
    import asyncio

    async def _run() -> None:
        mgr = CudaMemoryManager()
        # Request on a device that doesn't exist (device 999)
        with pytest.raises(CudaMemoryExhaustionError):
            await mgr.acquire_vram_budget(
                device_id=999,
                required_mb=512,
                timeout_seconds=0.2,
                poll_interval=0.1,
            )

    asyncio.run(_run())
