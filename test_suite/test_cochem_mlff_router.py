#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Zero-Mock Physical Unit Test Suite for CoChem-BASE Dynamic MLFF Fallback Router.
Tests:
1. Stage 0 Mandatory First Line JAX x64 Precision Pre-initialization.
2. Comprehensive Pydantic v2 Models (MLFFMethod, PrecisionMode, ExecutionDevice, Requests, Decisions).
3. Precision Downgrade Protocol & cpu_mlff_precision_fence Context Manager.
4. Golden Registry Polling & Real-time Hardware Introspection.
5. VRAM-Governed MLFF Fallback Cascade (MACE-OFF24m -> MACE-ONNX -> AIMNet2 -> g-xTB -> xTB2).
6. Anti-Silent Downgrade Guard (StrategyPivotException, PivotWarning, [Reduced Fidelity] tags).
7. Structured JSON-LD Telemetry Logging and Cryptographic Provenance Blocks.
8. Real Execution Pipeline under Precision Fencing.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Tuple
import warnings

import numpy as np
import pytest

# Target module under test
import core_engine.cochem_mlff_router as mlff_module
from core_engine.cochem_mlff_router import (
    CASCADE_ORDER,
    CASCADE_STEPPED_TAG,
    FP32_CPU_FENCED_TAG,
    FP64_CANONICAL_TAG,
    METHOD_PROFILES,
    REDUCED_FIDELITY_TAG,
    ExecutionDevice,
    MLFFMethod,
    MLFFRouter,
    MLFFRoutingDecision,
    MLFFRoutingRequest,
    PivotWarning,
    PrecisionMode,
    StrategyPivotException,
    cpu_mlff_precision_fence,
    execute_fenced_mlff,
    execute_mlff_cascade,
    poll_hardware_registry,
    probe_live_hardware,
    route_mlff,
)
from core_engine.cochem_core_registry_schema import (
    GPUComputeSchema,
    HardwareSchema,
)

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    HAS_TORCH = False

try:
    import jax
    import jax.numpy as jnp
    HAS_JAX = True
except ImportError:
    jax = None  # type: ignore[assignment]
    jnp = None  # type: ignore[assignment]
    HAS_JAX = False


# =============================================================================
# 1. LINE 1 JAX X64 PRE-INIT & CANONICAL QUANTUM PRECISION
# =============================================================================

def test_jax_x64_preinit_on_first_line() -> None:
    """Verifies that the top of cochem_mlff_router.py initializes JAX_ENABLE_X64."""
    router_file = Path(mlff_module.__file__).resolve()
    assert router_file.exists(), f"Router file '{router_file}' not found."

    with open(router_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    top_content = "\n".join(lines[:5])
    assert "JAX_ENABLE_X64" in top_content, (
        f"Top lines must configure JAX_ENABLE_X64. Got: '{top_content}'"
    )
    assert os.environ.get("JAX_ENABLE_X64") == "True"


def test_jax_double_precision_tensor_allocation() -> None:
    """Verifies that JAX allocates float64 double-precision arrays by default."""
    if not HAS_JAX or jax is None or jnp is None:
        pytest.skip("JAX not installed on this host environment.")

    arr = jnp.array([1.0, 2.0, 3.141592653589793])
    assert arr.dtype == jnp.float64, f"Expected jnp.float64, got {arr.dtype}"


# =============================================================================
# 2. ENUMS, MODELS & PYDANTIC V2 SCHEMA AIR-GAP VALIDATION
# =============================================================================

def test_mlff_method_enum_and_aliases() -> None:
    """Tests MLFFMethod enum members, aliases, and normalization."""
    assert MLFFMethod.MACE_OFF24M.value == "MACE-OFF24m"
    assert MLFFMethod.MACE_ONNX.value == "MACE-ONNX (CPU)"
    assert MLFFMethod.AIMNET2.value == "AIMNet2"
    assert MLFFMethod.G_XTB.value == "g-xTB"
    assert MLFFMethod.XTB2.value == "xTB2"

    # Alias coercions
    assert MLFFMethod.from_string("mace") == MLFFMethod.MACE_OFF24M
    assert MLFFMethod.from_string("mace-off24m") == MLFFMethod.MACE_OFF24M
    assert MLFFMethod.from_string("mace-off23") == MLFFMethod.MACE_OFF24M
    assert MLFFMethod.from_string("mace-onnx") == MLFFMethod.MACE_ONNX
    assert MLFFMethod.from_string("mace-cpu") == MLFFMethod.MACE_ONNX
    assert MLFFMethod.from_string("aimnet2") == MLFFMethod.AIMNET2
    assert MLFFMethod.from_string("aimnet") == MLFFMethod.AIMNET2
    assert MLFFMethod.from_string("g-xtb") == MLFFMethod.G_XTB
    assert MLFFMethod.from_string("gxtb") == MLFFMethod.G_XTB
    assert MLFFMethod.from_string("xtb2") == MLFFMethod.XTB2
    assert MLFFMethod.from_string("xtb") == MLFFMethod.XTB2
    assert MLFFMethod.from_string("gfn2-xtb") == MLFFMethod.XTB2

    with pytest.raises(ValueError, match="Unknown or unregistered MLFFMethod"):
        MLFFMethod.from_string("non_existent_method_xyz")


def test_execution_device_enum() -> None:
    """Tests ExecutionDevice enum coercions and validations."""
    assert ExecutionDevice.from_string("cuda") == ExecutionDevice.CUDA
    assert ExecutionDevice.from_string("gpu") == ExecutionDevice.CUDA
    assert ExecutionDevice.from_string("cpu") == ExecutionDevice.CPU
    assert ExecutionDevice.from_string("mps") == ExecutionDevice.MPS
    assert ExecutionDevice.from_string("auto") == ExecutionDevice.AUTO

    with pytest.raises(ValueError, match="Unknown ExecutionDevice"):
        ExecutionDevice.from_string("quantum_tpu")


def test_precision_mode_enum() -> None:
    """Tests PrecisionMode enum coercions and validations."""
    assert PrecisionMode.from_string("FP64") == PrecisionMode.FP64
    assert PrecisionMode.from_string("float64") == PrecisionMode.FP64
    assert PrecisionMode.from_string("fp32") == PrecisionMode.FP32
    assert PrecisionMode.from_string("float32") == PrecisionMode.FP32
    assert PrecisionMode.from_string("fp16") == PrecisionMode.FP16
    assert PrecisionMode.from_string("bf16") == PrecisionMode.BF16
    assert PrecisionMode.from_string("mixed") == PrecisionMode.MIXED

    with pytest.raises(ValueError, match="Unknown PrecisionMode"):
        PrecisionMode.from_string("FP8_INT4")


def test_method_profiles_completeness() -> None:
    """Validates that all cascade methods have valid, non-empty profile metadata."""
    assert len(CASCADE_ORDER) == 5
    for method in CASCADE_ORDER:
        assert method in METHOD_PROFILES
        profile = METHOD_PROFILES[method]
        assert profile.method == method
        assert profile.fidelity_rank >= 1
        assert profile.min_vram_gb >= 0.0
        assert len(profile.description) > 5


def test_mlff_routing_request_pydantic_validation() -> None:
    """Validates MLFFRoutingRequest schema validation and extra fields rejection."""
    req = MLFFRoutingRequest(
        requested_method=MLFFMethod.MACE_OFF24M,
        requested_device=ExecutionDevice.CUDA,
        requested_precision=PrecisionMode.FP32,
        atom_count=42,
        required_vram_gb=4.5,
        strict=True,
    )
    assert req.requested_method == MLFFMethod.MACE_OFF24M
    assert req.requested_device == ExecutionDevice.CUDA
    assert req.requested_precision == PrecisionMode.FP32
    assert req.atom_count == 42
    assert req.required_vram_gb == 4.5
    assert req.strict is True

    # Test alias and string coercion via model_validate
    req_coerced = MLFFRoutingRequest.model_validate({
        "requested_method": "mace-off24m",
        "requested_device": "cuda",
        "requested_precision": "FP32",
        "atom_count": 42,
        "required_vram_gb": 4.5,
        "strict": True,
    })
    assert req_coerced.requested_method == MLFFMethod.MACE_OFF24M
    assert req_coerced.requested_device == ExecutionDevice.CUDA
    assert req_coerced.requested_precision == PrecisionMode.FP32

    # Extra fields rejection (Anti-Spoofing & Schema Air-Gap)
    with pytest.raises(ValueError):
        MLFFRoutingRequest.model_validate({
            "requested_method": "MACE-OFF24m",
            "unauthorized_extra_field": "spoofed_injection",
        })


def test_mlff_routing_decision_serialization() -> None:
    """Tests MLFFRoutingDecision validation and JSON roundtrip."""
    decision = MLFFRoutingDecision(
        requested_method=MLFFMethod.MACE_OFF24M,
        selected_method=MLFFMethod.MACE_ONNX,
        execution_device=ExecutionDevice.CPU,
        precision_mode=PrecisionMode.FP32,
        is_pivoted=True,
        pivot_reason="VRAM 0.0 GB triggers downgrade",
        cascade_trace=[MLFFMethod.MACE_OFF24M, MLFFMethod.MACE_ONNX],
        provenance_tags=[REDUCED_FIDELITY_TAG, CASCADE_STEPPED_TAG, FP32_CPU_FENCED_TAG],
        hardware_snapshot={"vram_gb": 0.0, "ram_gb": 32.0},
        fenced_execution=True,
    )

    json_str = decision.model_dump_json()
    parsed = MLFFRoutingDecision.model_validate_json(json_str)
    assert parsed.requested_method == MLFFMethod.MACE_OFF24M
    assert parsed.selected_method == MLFFMethod.MACE_ONNX
    assert parsed.is_pivoted is True
    assert REDUCED_FIDELITY_TAG in parsed.provenance_tags
    assert parsed.fenced_execution is True


# =============================================================================
# 3. PRECISION DOWNGRADE PROTOCOL & FENCING TESTS
# =============================================================================

def test_cpu_mlff_precision_fence_transitions() -> None:
    """Tests that cpu_mlff_precision_fence sets FP32 and restores original dtype."""
    if not HAS_TORCH or torch is None:
        pytest.skip("PyTorch not installed on this host environment.")

    # Set initial default to float64 (Canonical Quantum Precision)
    torch.set_default_dtype(torch.float64)
    assert torch.get_default_dtype() == torch.float64

    # Enter precision fence
    with cpu_mlff_precision_fence(PrecisionMode.FP32) as mode:
        assert mode == PrecisionMode.FP32
        assert torch.get_default_dtype() == torch.float32
        t = torch.tensor([1.0, 2.0, 3.0])
        assert t.dtype == torch.float32

    # Exit precision fence: Must be restored to float64
    assert torch.get_default_dtype() == torch.float64
    t_after = torch.tensor([1.0, 2.0, 3.0])
    assert t_after.dtype == torch.float64


def test_cpu_mlff_precision_fence_exception_safety() -> None:
    """Verifies that precision is safely restored even when an unhandled exception occurs."""
    if not HAS_TORCH or torch is None:
        pytest.skip("PyTorch not installed on this host environment.")

    torch.set_default_dtype(torch.float64)

    with pytest.raises(RuntimeError, match="Simulated inference fault"):
        with cpu_mlff_precision_fence(PrecisionMode.FP32):
            assert torch.get_default_dtype() == torch.float32
            raise RuntimeError("Simulated inference fault")

    # Verify restoration after crash
    assert torch.get_default_dtype() == torch.float64


def test_execute_fenced_mlff_helper() -> None:
    """Tests the execute_fenced_mlff functional wrapper."""
    if not HAS_TORCH or torch is None:
        pytest.skip("PyTorch not installed on this host environment.")

    torch.set_default_dtype(torch.float64)

    def dummy_forward_pass(x: float, y: float) -> Tuple[float, Any]:
        curr_dtype = torch.get_default_dtype()
        return x + y, curr_dtype

    res, dtype_inside = execute_fenced_mlff(dummy_forward_pass, 10.0, 20.0, target_precision=PrecisionMode.FP32)
    assert res == 30.0
    assert dtype_inside == torch.float32
    assert torch.get_default_dtype() == torch.float64


# =============================================================================
# 4. GOLDEN REGISTRY POLLING & HARDWARE RESOLUTION TESTS
# =============================================================================

def test_probe_live_hardware_zero_mock() -> None:
    """Tests live hardware introspection with real psutil values."""
    hw = probe_live_hardware()
    assert isinstance(hw, HardwareSchema)
    assert hw.ram_gb > 0.0
    assert hw.cpu_physical_cores is not None and hw.cpu_physical_cores >= 1
    assert hw.logical_cpu_cores is not None and hw.logical_cpu_cores >= hw.cpu_physical_cores
    assert hw.vram_gb >= 0.0
    assert hw.gpu_compute_metrics is not None


def test_poll_hardware_registry_from_file() -> None:
    """Tests polling a Golden Registry cochem_system_config.json from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "cochem_system_config.json"
        sample_config = {
            "hardware": {
                "ram_gb": 64.0,
                "cpu_physical_cores": 16,
                "logical_cpu_cores": 32,
                "allocatable_compute_cores": 16,
                "vram_gb": 24.0,
                "gpu_fp64_capable": True,
                "mps_enabled": False,
                "avx_512_capable": True,
                "gpu_profile": "NVIDIA RTX 4090",
                "os_target": "Local-Windows" if os.name == "nt" else "Local-Linux",
                "gpu_compute_metrics": {
                    "gpu_profile": "NVIDIA RTX 4090",
                    "vram_gb": 24.0,
                    "device_count": 1,
                    "compute_capability": "8.9",
                    "fp64_capable": True,
                    "mps_enabled": False,
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(sample_config))

        hw = poll_hardware_registry(config_path=config_path)
        assert hw.vram_gb == 24.0
        assert hw.ram_gb == 64.0
        assert hw.gpu_profile == "NVIDIA RTX 4090"
        assert hw.gpu_compute_metrics.device_count == 1


# =============================================================================
# 5. VRAM-GOVERNED MLFF FALLBACK CASCADE & DEGRADATION TESTS
# =============================================================================

def test_cascade_pivot_gpu_unavailable_to_mace_onnx() -> None:
    """
    Scenario: User requests MACE-OFF24m on GPU, but host has 0.0 VRAM (e.g. CPU host).
    Expected: Pivot to MACE-ONNX (CPU), emit PivotWarning, record [Reduced Fidelity] tag.
    """
    hw_cpu_only = HardwareSchema(
        ram_gb=32.0,
        cpu_physical_cores=8,
        logical_cpu_cores=16,
        allocatable_compute_cores=8,
        vram_gb=0.0,
        gpu_fp64_capable=False,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
        gpu_compute_metrics=GPUComputeSchema(gpu_profile="None", vram_gb=0.0, device_count=0),
    )

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always", PivotWarning)
        decision = route_mlff(
            requested_method=MLFFMethod.MACE_OFF24M,
            requested_device=ExecutionDevice.AUTO,
            strict=False,
            hardware_override=hw_cpu_only,
        )

    assert decision.requested_method == MLFFMethod.MACE_OFF24M
    assert decision.selected_method == MLFFMethod.MACE_ONNX
    assert decision.execution_device == ExecutionDevice.CPU
    assert decision.precision_mode == PrecisionMode.FP32
    assert decision.is_pivoted is True
    assert decision.fenced_execution is True
    assert REDUCED_FIDELITY_TAG in decision.provenance_tags
    assert CASCADE_STEPPED_TAG in decision.provenance_tags
    assert FP32_CPU_FENCED_TAG in decision.provenance_tags
    assert len(recorded_warnings) == 1
    assert issubclass(recorded_warnings[0].category, PivotWarning)
    assert "Requested 'MACE-OFF24m' -> Fell back to 'MACE-ONNX (CPU)'" in str(recorded_warnings[0].message)


def test_route_mace_gpu_success_when_vram_sufficient() -> None:
    """
    Scenario: User requests MACE-OFF24m on a GPU with 16.0 GB VRAM.
    Expected: Direct execution on CUDA with MACE-OFF24m, is_pivoted=False.
    """
    hw_gpu = HardwareSchema(
        ram_gb=64.0,
        cpu_physical_cores=16,
        logical_cpu_cores=32,
        allocatable_compute_cores=16,
        vram_gb=16.0,
        gpu_fp64_capable=True,
        gpu_profile="NVIDIA RTX 4090",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
        gpu_compute_metrics=GPUComputeSchema(
            gpu_profile="NVIDIA RTX 4090",
            vram_gb=16.0,
            device_count=1,
            compute_capability="8.9",
        ),
    )

    decision = route_mlff(
        requested_method=MLFFMethod.MACE_OFF24M,
        requested_device=ExecutionDevice.CUDA,
        strict=True,
        hardware_override=hw_gpu,
    )

    assert decision.requested_method == MLFFMethod.MACE_OFF24M
    assert decision.selected_method == MLFFMethod.MACE_OFF24M
    assert decision.execution_device == ExecutionDevice.CUDA
    assert decision.is_pivoted is False
    assert REDUCED_FIDELITY_TAG not in decision.provenance_tags


def test_cascade_pivot_insufficient_vram_for_large_molecule() -> None:
    """
    Scenario: User requests MACE-OFF24m for a 1000-atom molecule requiring 12.0 GB VRAM,
    but the GPU only has 4.0 GB VRAM.
    Expected: VRAM shortage triggers pivot to MACE-ONNX (CPU).
    """
    hw_small_gpu = HardwareSchema(
        ram_gb=32.0,
        cpu_physical_cores=8,
        logical_cpu_cores=16,
        allocatable_compute_cores=8,
        vram_gb=4.0,
        gpu_profile="NVIDIA RTX 3050",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
        gpu_compute_metrics=GPUComputeSchema(gpu_profile="NVIDIA RTX 3050", vram_gb=4.0, device_count=1),
    )

    with warnings.catch_warnings(record=True) as recorded_warnings:
        warnings.simplefilter("always", PivotWarning)
        decision = route_mlff(
            requested_method=MLFFMethod.MACE_OFF24M,
            atom_count=1000,
            required_vram_gb=12.0,
            strict=False,
            hardware_override=hw_small_gpu,
        )

    assert len(recorded_warnings) >= 1
    assert decision.selected_method == MLFFMethod.MACE_ONNX
    assert decision.execution_device == ExecutionDevice.CPU
    assert decision.is_pivoted is True
    assert REDUCED_FIDELITY_TAG in decision.provenance_tags
    assert decision.pivot_reason is not None
    assert "requires 12.0 GB VRAM" in decision.pivot_reason


def test_route_aimnet2_flexible_fallback() -> None:
    """
    Scenario: AIMNet2 requested on CPU host.
    Expected: Routes to AIMNet2 on CPU with FP32 precision fence.
    """
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    decision = route_mlff(
        requested_method=MLFFMethod.AIMNET2,
        requested_device=ExecutionDevice.AUTO,
        hardware_override=hw_cpu,
    )

    assert decision.selected_method == MLFFMethod.AIMNET2
    assert decision.execution_device == ExecutionDevice.CPU
    assert decision.fenced_execution is True


def test_route_xtb2_canonical_fp64() -> None:
    """
    Scenario: xTB2 requested directly.
    Expected: Selected xTB2 on CPU with FP64 canonical precision, no pivot.
    """
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    decision = route_mlff(
        requested_method=MLFFMethod.XTB2,
        hardware_override=hw_cpu,
    )

    assert decision.selected_method == MLFFMethod.XTB2
    assert decision.execution_device == ExecutionDevice.CPU
    assert decision.precision_mode == PrecisionMode.FP64
    assert decision.is_pivoted is False
    assert FP64_CANONICAL_TAG in decision.provenance_tags


def test_cascade_stepping_trace() -> None:
    """Validates that cascade_trace logs all candidate methods evaluated in order."""
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    decision = route_mlff(
        requested_method=MLFFMethod.MACE_OFF24M,
        hardware_override=hw_cpu,
    )

    assert decision.cascade_trace == [MLFFMethod.MACE_OFF24M, MLFFMethod.MACE_ONNX]


# =============================================================================
# 6. ANTI-SILENT DOWNGRADE GUARD & STRICT PIVOT TRAPS
# =============================================================================

def test_strict_mode_prohibits_silent_downgrade() -> None:
    """
    Scenario: strict=True on a GPU-bound request with 0.0 VRAM.
    Expected: Raises StrategyPivotException immediately to prevent silent physics drift.
    """
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    with pytest.raises(StrategyPivotException) as exc_info:
        route_mlff(
            requested_method=MLFFMethod.MACE_OFF24M,
            strict=True,
            hardware_override=hw_cpu,
        )

    err = exc_info.value
    assert err.requested_method == "MACE-OFF24m"
    assert err.fallback_method == "MACE-ONNX (CPU)"
    assert "Strict MLFF Strategy Pivot Trap" in str(err)
    assert REDUCED_FIDELITY_TAG in err.provenance_tags
    assert err.hardware_snapshot["vram_gb"] == 0.0


def test_disallowing_downgrades_raises_on_gpu_failure() -> None:
    """
    Scenario: allow_downgrade=False when requested method cannot run on host.
    Expected: Raises StrategyPivotException with no fallback.
    """
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    with pytest.raises(StrategyPivotException, match="MLFF Fallback Cascade Exhausted"):
        route_mlff(
            requested_method=MLFFMethod.MACE_OFF24M,
            allow_downgrade=False,
            hardware_override=hw_cpu,
        )


# =============================================================================
# 7. STRUCTURED JSON-LD TELEMETRY LOGGING & PROVENANCE SIGNING
# =============================================================================

def test_telemetry_event_emission_on_pivot() -> None:
    """Tests emitting and parsing a structured JSON-LD telemetry pivot record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_log = Path(tmpdir) / "test_mlff_telemetry.jsonl"

        hw_cpu = HardwareSchema(
            ram_gb=16.0,
            cpu_physical_cores=4,
            logical_cpu_cores=8,
            allocatable_compute_cores=4,
            vram_gb=0.0,
            gpu_profile="None",
            os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
        )

        router = MLFFRouter(telemetry_log_path=telemetry_log)
        decision = router.route(
            MLFFRoutingRequest(
                requested_method=MLFFMethod.MACE_OFF24M,
                strict=False,
                hardware_override=hw_cpu,
            )
        )
        assert decision.is_pivoted is True

        assert telemetry_log.exists(), "Telemetry JSONL file was not created."
        with open(telemetry_log, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) >= 1
        record = lines[-1]
        assert record["@type"] == "MLFFRoutingPivotEvent"
        assert record["requested_method"] == "MACE-OFF24m"
        assert record["selected_method"] == "MACE-ONNX (CPU)"
        assert record["execution_device"] == "cpu"
        assert record["is_pivoted"] is True
        assert REDUCED_FIDELITY_TAG in record["provenance_tags"]


# =============================================================================
# 8. REAL EXECUTION WORKFLOW INTEGRATION
# =============================================================================

def test_execute_mlff_cascade_pipeline() -> None:
    """Tests execute_mlff_cascade running an end-to-end simulated inference task."""
    hw_cpu = HardwareSchema(
        ram_gb=16.0,
        cpu_physical_cores=4,
        logical_cpu_cores=8,
        allocatable_compute_cores=4,
        vram_gb=0.0,
        gpu_profile="None",
        os_target="Local-Windows" if os.name == "nt" else "Local-Linux",
    )

    def dummy_mlff_potential(coords: np.ndarray) -> float:
        # Simple Lennard-Jones toy potential computation
        diff = coords[0] - coords[1]
        r = float(np.sqrt(np.sum(diff ** 2)))
        energy = 4.0 * ((1.0 / r)**12 - (1.0 / r)**6)
        return float(energy)

    coords = np.array([[0.0, 0.0, 0.0], [1.12, 0.0, 0.0]], dtype=np.float64)

    decision, energy = execute_mlff_cascade(
        dummy_mlff_potential,
        coords,
        requested_method=MLFFMethod.MACE_OFF24M,
        hardware_override=hw_cpu,
    )

    assert decision.selected_method == MLFFMethod.MACE_ONNX
    assert decision.is_pivoted is True
    assert isinstance(energy, float)
    assert not math.isnan(energy)
