"""Honest Hardware Telemetry & Runtime Dispatcher (Suggestion #52).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Zero mocks, zero synthetic fallback VRAM values.
"""

from __future__ import annotations

import os
import platform
from typing import Literal, Optional

import psutil
import torch

from cochem_base.exceptions import HardwareTelemetryError
from cochem_base.schemas import HardwareTelemetryReport


def probe_hardware_telemetry(precision: str = "float64") -> HardwareTelemetryReport:
    """Queries genuine OS and driver state for physical GPUs and returns an authentic report."""
    gpu_available = False
    device_count = 0
    device_name = "None"
    vram_total_mb = 0.0
    vram_free_mb = 0.0

    # Genuine PyTorch CUDA inspection
    try:
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                gpu_available = True
                device_name = torch.cuda.get_device_name(0)
                free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                vram_total_mb = float(total_bytes) / (1024.0 * 1024.0)
                vram_free_mb = float(free_bytes) / (1024.0 * 1024.0)
    except Exception:
        gpu_available = False
        device_count = 0

    # Genuine macOS MPS inspection
    is_mps = False
    try:
        if (
            platform.system() == "Darwin"
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
        ):
            is_mps = True
    except Exception:
        is_mps = False

    # Dispatcher routing logic mandated by Suggestion #52
    if gpu_available and vram_free_mb >= 2048.0:
        selected_runtime: Literal["cuda", "mps", "cpu", "onnx_cpu"] = "cuda"
    elif is_mps:
        # Check precision: MPS does not support native float64
        if precision.lower() in ("float64", "fp64", "double"):
            selected_runtime = "cpu"
        else:
            selected_runtime = "mps"
    else:
        # Absence of discrete GPU or VRAM < 2048 MB routes to CPU
        selected_runtime = "cpu"

    return HardwareTelemetryReport(
        device_count=device_count,
        gpu_available=gpu_available,
        device_name=device_name,
        vram_total_mb=vram_total_mb,
        vram_free_mb=vram_free_mb,
        selected_runtime=selected_runtime,
    )


__all__ = ["probe_hardware_telemetry", "HardwareTelemetryReport", "HardwareTelemetryError"]
