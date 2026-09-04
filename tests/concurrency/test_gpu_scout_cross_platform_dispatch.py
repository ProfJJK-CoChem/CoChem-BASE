"""Physical Zero-Mock Test Suite for OS-Aware GPU Scout Concurrency & Windows/macOS Mutex Scheduling.

Method Matrix Reference: Method Matrix v4 §8A.4 (NVIDIA MPS Daemon Lifecycle) and §8A.2 (Heterogeneous Concurrency) [M].
Validates Suggestion #65:
- OS-aware hardware detection across 6-Tier Environment Matrix.
- Windows/macOS bypass of NVIDIA MPS daemon scripts (zero nvidia-cuda-mps-control invocation).
- Serialized GPU scout execution via threading.Semaphore(1) / mutex.
- Dynamic VRAM headroom safeguard (< 1.5 GB holds/defers tasks).
- Concurrency verification under 4 concurrent tasks.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import time
import pytest
from pathlib import Path

from cochem_base.schemas import GpuScoutExecutorConfig
from cochem_base.core_engine.cochem_core_parsl_executors import (
    GpuScoutDispatcher,
    build_worker_init_scripts,
    detect_gpu_scout_config,
)

# Import hetero_config from TOPOS
import importlib.util
_topos_hetero_path = (Path(__file__).resolve().parent.parent.parent.parent / "CoChem-TOPOS" / "hetero_config.py").resolve()
if not _topos_hetero_path.is_file():
    _topos_hetero_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/hetero_config.py")

spec = importlib.util.spec_from_file_location("topos_hetero_mod", str(_topos_hetero_path))
topos_hetero = importlib.util.module_from_spec(spec)
sys.modules["topos_hetero_mod"] = topos_hetero
spec.loader.exec_module(topos_hetero)


def test_os_aware_scout_config_windows_macos(tmp_path: Path):
    """Assert Windows/macOS environment disables MPS and sets max_concurrent_gpu_tasks to 1."""
    config = detect_gpu_scout_config(scratch_dir=tmp_path)

    # On Windows or macOS, MPS must be explicitly disabled and max_concurrent must be 1
    if sys.platform in ("win32", "darwin"):
        assert config.enable_mps is False
        assert config.max_concurrent_gpu_tasks == 1
        assert config.platform_os in ("windows", "darwin")
        assert config.min_vram_headroom_mb >= 512.0

    # Test top-level MPS script generator in hetero_config
    mps_cfg = topos_hetero.MPSConfig(
        device_id=0,
        pipe_directory=str(tmp_path / "mps_pipe"),
        log_directory=str(tmp_path / "mps_log"),
    )
    startup_script = topos_hetero.generate_mps_startup_script(mps_cfg)
    if sys.platform in ("win32", "darwin"):
        assert "nvidia-cuda-mps-control -d" not in startup_script
        assert "ulimit -n" not in startup_script
        assert "bypassed" in startup_script.lower()

    # Verify build_worker_init_scripts bypasses MPS
    cpu_init, gpu_init, orch_init = build_worker_init_scripts(
        mps_pipe_dir=tmp_path / "mps_pipe",
        mps_log_dir=tmp_path / "mps_log",
        enable_mps=False,
    )
    assert "CUDA_MPS_PIPE_DIRECTORY" not in gpu_init
    assert "ulimit -n" not in gpu_init


def test_gpu_scout_semaphore_serialization(tmp_path: Path):
    """Launch 4 concurrent scout tasks; verify execution is serialized through Semaphore(1)."""
    cfg = GpuScoutExecutorConfig(
        platform_os="windows" if sys.platform == "win32" else "darwin",
        enable_mps=False,
        mps_pipe_dir=str(tmp_path / "mps"),
        max_concurrent_gpu_tasks=1,
        min_vram_headroom_mb=512.0,
    )
    dispatcher = GpuScoutDispatcher(cfg)

    active_counts: list[int] = []
    task_order: list[int] = []

    def scout_kernel(task_id: int):
        with dispatcher.dispatch_scout(max_wait=10.0):
            # Record active concurrency inside critical section
            active = dispatcher.active_count
            active_counts.append(active)
            time.sleep(0.05)  # Simulate GPU kernel execution
            task_order.append(task_id)
            return task_id

    num_tasks = 4
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_tasks) as pool:
        futures = [pool.submit(scout_kernel, i) for i in range(num_tasks)]
        results = [f.result() for f in futures]

    assert len(results) == num_tasks
    assert set(results) == set(range(num_tasks))
    # Strict serialization check: active count inside critical section must never exceed 1
    assert all(c == 1 for c in active_counts), f"Concurrency exceeded 1: {active_counts}"


def test_dynamic_vram_headroom_safeguard(tmp_path: Path):
    """Verify that if configured min_vram_headroom_mb is exceedingly high, dispatch halts/times out."""
    # Configure an impossible VRAM threshold to trigger the safeguard
    cfg = GpuScoutExecutorConfig(
        platform_os="windows" if sys.platform == "win32" else "linux",
        enable_mps=False,
        mps_pipe_dir=str(tmp_path / "mps"),
        max_concurrent_gpu_tasks=1,
        min_vram_headroom_mb=999999.0,  # Impossible headroom threshold
    )
    dispatcher = GpuScoutDispatcher(cfg)

    # If CUDA is available, check_vram_headroom will report free < 999999 MB
    import torch
    if torch.cuda.is_available():
        has_vram, free_mb = dispatcher.check_vram_headroom()
        assert has_vram is False
        with pytest.raises(RuntimeError) as exc_info:
            with dispatcher.dispatch_scout(poll_interval=0.01, max_wait=0.05):
                pass
        assert "Dynamic VRAM safeguard" in str(exc_info.value)
    else:
        # On CPU-only environments, check_vram_headroom gracefully permits execution
        has_vram, _ = dispatcher.check_vram_headroom()
        assert has_vram is True
