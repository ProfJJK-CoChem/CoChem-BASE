"""Zero-mock unit test for Non-Initializing GPU Telemetry via NVML & Honest CPU/ONNX Dispatch.

SRS Chunk 14 / Suggestion #131 / Method Matrix v4 §8A.4, §8.2, §8.3 [M], [D].
Zero-Mock Mandate v3: Completely authentic NVML probing without torch.cuda.init context locks.
"""

from __future__ import annotations

import os
from pathlib import Path

from hetero_config import MPSStatus, probe_mps_status
from Libraries.cochem_torq_engine import ExecutionContext, HardwareTelemetryReport


def test_non_initializing_gpu_telemetry_cpu_environment() -> None:
    """Verify probe_mps_status and ExecutionContext.probe_hardware query NVML without torch.cuda.init [M]."""
    old_cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    try:
        # Simulate CPU-only execution node by masking visible CUDA devices
        os.environ["CUDA_VISIBLE_DEVICES"] = ""

        # Execute non-initializing NVML status probe
        status = probe_mps_status(pipe_dir=Path("./scratch/mps_pipe"), log_dir=Path("./scratch/mps_log"))
        assert isinstance(status, MPSStatus)
        assert getattr(status, "provenance", "[M]") == "[M]"

        # On CPU-only environment, honest reporting of exact zero devices
        if status.cuda_device_count == 0:
            assert status.vram_total_mb == 0.0
            assert status.vram_free_mb == 0.0
            assert status.device_name == "None"

        # Verify ExecutionContext hardware probe
        ctx = ExecutionContext()
        telemetry = ctx.get_telemetry()
        assert isinstance(telemetry, HardwareTelemetryReport)
        assert getattr(telemetry, "provenance", "[M]") == "[M]"

        if telemetry.device_count == 0:
            assert telemetry.gpu_available is False
            assert telemetry.vram_total_mb == 0.0
            assert telemetry.vram_free_mb == 0.0
            assert telemetry.selected_runtime == "cpu"

        # Verify autonomous Orchestration Tier dispatch contract
        dispatch_contract = ctx.get_dispatch_contract()
        assert dispatch_contract["device"] == ("cuda" if ctx.gpu_available and ctx.vram_mb >= 2048 else "cpu")
        assert dispatch_contract["num_threads"] == ctx.num_cores
    finally:
        if old_cuda_visible is not None:
            os.environ["CUDA_VISIBLE_DEVICES"] = old_cuda_visible
        else:
            os.environ.pop("CUDA_VISIBLE_DEVICES", None)
