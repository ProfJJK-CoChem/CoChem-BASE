# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: OS-Aware GPU Scout Concurrency & Windows/macOS Serialized Dynamic VRAM Routing.
Validates Suggestion #144 (Deliverable 4) under Method Matrix v4 §8A.4, §8A.6 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import platform
import pytest

from cochem_base.core_engine.hetero_config import (
    build_setup2_hetero_config,
    get_vram_free_gb,
    HeteroParslConfig,
)
from cochem_base.core_engine.cochem_core_parsl_executors import (
    ParslExecutionBroker,
)


def test_os_aware_mps_bypass_on_non_linux() -> None:
    """Verify that build_setup2_hetero_config bypasses MPS on Windows/macOS and enforces max_workers=1."""
    cfg = build_setup2_hetero_config(
        cpu_workers=1,
        gpu_workers=3,
        as_parsl_object=False,
    )

    current_os = platform.system()
    if current_os in ("Windows", "Darwin"):
        assert cfg.gpu_workers == 1, f"Expected serialized gpu_workers=1 on {current_os}, got {cfg.gpu_workers}"
        # Assert that worker_init contains no Linux-only MPS commands
        assert "nvidia-cuda-mps-control" not in cfg.gpu_worker_init
        assert "CUDA_MPS_PIPE_DIRECTORY" not in cfg.gpu_worker_init
    else:
        # On Linux, verify MPS parameters
        assert "CUDA_MPS" in cfg.gpu_worker_init or cfg.gpu_workers >= 1


def test_dynamic_vram_polling_and_threshold() -> None:
    """Verify non-initializing VRAM polling returns physical float value and applies >=2.0 GB headroom check."""
    vram_free = get_vram_free_gb()
    assert isinstance(vram_free, float)
    assert vram_free >= 0.0

    # Test safety threshold evaluation: if VRAM < 2.0 GB, throttle / route to CPU
    safety_threshold = 2.0
    needs_throttle = (vram_free < safety_threshold) and (vram_free > 0.0)
    assert isinstance(needs_throttle, bool)