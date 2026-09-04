import os
os.environ["JAX_ENABLE_X64"] = "True"

import pytest
import torch
from mendeleev import element

from Libraries.cochem_torq_engine import ExecutionContext
from cochem_base.schemas import HardwareTelemetryReport
from cochem_topos.telemetry.hardware import probe_hardware_telemetry


def test_honest_hardware_telemetry_and_cpu_fallback():
    """Verify honest hardware telemetry with zero-spoofed VRAM and automated CPU fallback (Suggestion #52 / Method Matrix v4 §8.3 [M], [D])."""
    # Dynamic Mendeleev check
    si = element("Si")
    assert si.atomic_number == 14

    ctx = ExecutionContext()
    report = ctx.get_telemetry()
    assert isinstance(report, HardwareTelemetryReport)

    # Check that fabricated values (e.g. exactly 24 GB / 24576 MB) are strictly absent
    assert report.vram_total_mb != 24576.0
    assert report.vram_free_mb != 24576.0

    # Verify physical consistency with genuine PyTorch device availability
    has_cuda = torch.cuda.is_available()
    if not has_cuda:
        assert report.gpu_available is False
        assert report.device_count == 0
        assert report.vram_free_mb == 0.0
        assert report.vram_total_mb == 0.0
        assert report.selected_runtime in ("cpu", "onnx_cpu")
    else:
        assert report.gpu_available is True
        assert report.device_count > 0
        assert report.vram_total_mb > 0.0

    # Verify TOPOS telemetry probe parity
    topos_report = probe_hardware_telemetry()
    assert isinstance(topos_report, HardwareTelemetryReport)
    assert topos_report.gpu_available == report.gpu_available
    assert topos_report.device_count == report.device_count
    assert topos_report.vram_total_mb != 24576.0


def test_honest_cpu_inference_routing_without_cuda_error():
    """Verify model inference routes honestly to CPU without raising unhandled CUDAInitializationError."""
    ctx = ExecutionContext()
    # Force float64 precision query
    telemetry = ctx.get_telemetry(precision="float64")

    # If discrete GPU is absent or has < 2048 MB free VRAM, selected_runtime MUST be 'cpu'
    if not telemetry.gpu_available or telemetry.vram_free_mb < 2048.0:
        assert telemetry.selected_runtime == "cpu"

    # Verify simple PyTorch tensor computation succeeds on the selected runtime
    device = torch.device(telemetry.selected_runtime)
    tensor_a = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float64, device=device)
    tensor_b = torch.tensor([4.0, 5.0, 6.0], dtype=torch.float64, device=device)
    res = tensor_a + tensor_b
    assert torch.allclose(res, torch.tensor([5.0, 7.0, 9.0], dtype=torch.float64, device=device))
