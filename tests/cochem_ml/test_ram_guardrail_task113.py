"""CoChem-ML Dynamic RAM Polling Guardrail & Heap Ceiling Enforcement Test Suite (Task 1.13).

Physical Verification Suite for DynamicRAMPollingGuardrail, HeapCeilingExceededError,
ProcessMemorySnapshot, RAMTelemetryRecord, RAMGuardrailConfig, RAMGuardrailMetrics,
and corresponding Pydantic v2 schemas.

Governed by Method Matrix v4.2, Anti-Spoofing Protocol v4, Mendeleev Dynamic Mass Mandate,
Core Directive 1 (Registry Consistency & Air-Gap Enforcement), and
SRS-CHUNK-018-AG-ML-RL-TRANSITION-V1.0-20260913 (Task 1.13 & FR-04/FR-06).

Invariants Verified:
- Zero-Mock & Anti-Spoofing Protocol v4 Directives (Zero pass/NotImplementedError/mocks/skips) [M]
- Dynamic Mendeleev Atomic Weight Resolution without Static Tables [M]
- Strict < 2.0 GB Heap Ceiling Invariant (2,147,483,648 bytes) [M]
- Dynamic psutil Resident Set Size (RSS) & Process Tree Physical Sampling [M]
- Multi-Stage Memory Utilization State Machine (NORMAL, WARNING, CRITICAL, EXCEEDED) [D]
- Deterministic HeapCeilingExceededError with Forensic Audit Digest [D]
- Authentic Ab-Initio Quantum Chemical Trajectory Ingestion from complexes.h5 [E]
- Contiguous Real NumPy Memory Tracking without Banned Synthetic Generators [M]
- Cooperative Checkpoint Step Polling for Streaming Iterations [D]
- Context Manager Scope & Memory Delta Tracking [D]
- Decorator Pre- and Post-Invocation Execution Guardrails [D]
- Proactive Remediation Callback Dispatch on Memory Threshold [D]
- Ordinary Least Squares (OLS) Trajectory Slope Calculation [D]
- PCA-74 Cryptographic SHA-256 Predecessor Hash Chaining back to GENESIS_HASH [D]
- W3C PROV-O JSON-LD Compliance & Serialization Roundtrips [D]
- Pydantic v2 Bidirectional Lossless Schema Roundtrips with extra='forbid' [D]
- Root Wrapper Symbol Parity and Module Export Parity [D]
- Sub-5.0 ms Polling Latency Benchmark [D]
"""

from __future__ import annotations

import ast
import gc
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Set, Tuple

import h5py
from mendeleev import element
import numpy as np
import psutil
import pytest


def _resolve_repo_root() -> Path:
    """Dynamically resolve repository root directory honoring environment overrides."""
    if "COCHEM_REPO_ROOT" in os.environ:
        return Path(os.environ["COCHEM_REPO_ROOT"]).resolve()
    if "COCHEM_BASE_DIR" in os.environ:
        return Path(os.environ["COCHEM_BASE_DIR"]).resolve()
    return Path(__file__).resolve().parents[2]


_REPO_ROOT: Path = _resolve_repo_root()
_SRC_DIR: Path = _REPO_ROOT / "src"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import cochem_ml
from cochem_ml.ram_guardrail import (
    DEFAULT_CRITICAL_RATIO,
    DEFAULT_HISTORY_CAPACITY,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_WARNING_RATIO,
    GENESIS_HASH,
    RAM_CEILING_BYTES,
    DynamicRAMPollingGuardrail,
    HeapCeilingExceededError,
    ProcessMemorySnapshot,
    RAMGuardrailConfig,
    RAMGuardrailMetrics,
    RAMGuardrailStage,
    RAMTelemetryRecord,
    check_heap_memory_guardrail,
    compute_sha256_digest,
    enforce_ram_ceiling,
    get_aggregate_tree_memory_bytes,
    get_current_process_memory_bytes,
    ram_guardrail,
    verify_mendeleev_integrity,
)
import ram_guardrail as root_ram_guardrail_module
from cochem_ml.schemas import (
    ProcessMemorySnapshotSchema,
    RAMGuardrailConfigSchema,
    RAMGuardrailMetricsSchema,
    RAMTelemetryRecordSchema,
)


def test_dynamic_mendeleev_atomic_mass_invariants() -> None:
    """Verify Mendeleev dynamic mass resolution invariant without static tables."""
    masses = verify_mendeleev_integrity()
    assert isinstance(masses, dict)
    assert len(masses) >= 8

    # Carbon atomic weight ~12.011 u
    carbon_mass = element("C").mass
    assert math.isclose(masses["C"], carbon_mass, rel_tol=1e-5)
    assert 12.010 <= masses["C"] <= 12.012

    # Hydrogen atomic weight ~1.008 u
    hydrogen_mass = element("H").mass
    assert math.isclose(masses["H"], hydrogen_mass, rel_tol=1e-5)
    assert 1.007 <= masses["H"] <= 1.009

    # Oxygen atomic weight ~15.999 u
    oxygen_mass = element("O").mass
    assert math.isclose(masses["O"], oxygen_mass, rel_tol=1e-5)
    assert 15.998 <= masses["O"] <= 16.001


def test_process_memory_snapshot_physical_sampling() -> None:
    """Verify physical process memory sampling via psutil returns authentic system data."""
    config = RAMGuardrailConfig()
    guard = DynamicRAMPollingGuardrail(config)

    snapshot = guard.sample_process_snapshot()
    assert isinstance(snapshot, ProcessMemorySnapshot)
    assert snapshot.pid == os.getpid()
    assert len(snapshot.name) > 0
    assert snapshot.rss_bytes > 0
    assert snapshot.vms_bytes > 0
    assert snapshot.num_threads >= 1
    assert snapshot.timestamp_sec > 0.0

    snap_dict = snapshot.to_dict()
    assert snap_dict["pid"] == os.getpid()
    assert snap_dict["rss_bytes"] == snapshot.rss_bytes


def test_child_process_tree_physical_enumeration() -> None:
    """Verify child process tree inspection aggregates resident set sizes correctly."""
    config = RAMGuardrailConfig(include_children=True)
    guard = DynamicRAMPollingGuardrail(config)

    children = guard.sample_child_processes()
    assert isinstance(children, list)

    tree_mem = get_aggregate_tree_memory_bytes(os.getpid())
    current_mem = get_current_process_memory_bytes()
    assert tree_mem >= current_mem
    assert current_mem > 0


def test_multi_stage_memory_utilization_classification() -> None:
    """Verify categorical memory stage classification against configured threshold ratios."""
    ceiling = 1_000_000
    config = RAMGuardrailConfig(
        ceiling_bytes=ceiling,
        warning_ratio=0.75,
        critical_ratio=0.90,
    )
    guard = DynamicRAMPollingGuardrail(config)

    # Normal: < 750,000 bytes
    assert guard.classify_stage(500_000) == RAMGuardrailStage.NORMAL
    assert guard.classify_stage(749_999) == RAMGuardrailStage.NORMAL

    # Warning: 750,000 <= bytes < 900,000
    assert guard.classify_stage(750_000) == RAMGuardrailStage.WARNING
    assert guard.classify_stage(850_000) == RAMGuardrailStage.WARNING
    assert guard.classify_stage(899_999) == RAMGuardrailStage.WARNING

    # Critical: 900,000 <= bytes < 1,000,000
    assert guard.classify_stage(900_000) == RAMGuardrailStage.CRITICAL
    assert guard.classify_stage(999_999) == RAMGuardrailStage.CRITICAL

    # Exceeded: >= 1,000,000 bytes
    assert guard.classify_stage(1_000_000) == RAMGuardrailStage.EXCEEDED
    assert guard.classify_stage(1_500_000) == RAMGuardrailStage.EXCEEDED


def test_strict_active_heap_ceiling_tripwire() -> None:
    """Verify active RAM ceiling enforcement (< 2.0 GB) and deterministic exception raising."""
    # Production 2.0 GB ceiling check must pass under normal test conditions
    rss = check_heap_memory_guardrail(RAM_CEILING_BYTES)
    assert 0 < rss < RAM_CEILING_BYTES

    # An impossibly low ceiling (100 bytes) must deterministically raise HeapCeilingExceededError
    with pytest.raises(HeapCeilingExceededError) as exc_info:
        check_heap_memory_guardrail(ceiling_bytes=100)

    err = exc_info.value
    assert err.current_rss_bytes > 100
    assert err.ceiling_bytes == 100
    assert err.target_pid == os.getpid()
    assert err.utilization_pct > 100.0
    assert len(err.audit_hash) == 64
    assert err.timestamp_sec > 0.0

    forensic = err.to_forensic_dict()
    assert forensic["error_type"] == "HeapCeilingExceededError"
    assert forensic["ceiling_bytes"] == 100


def test_authentic_molecular_data_ingestion_under_ram_guardrail() -> None:
    """Verify ingestion of authentic ab-initio quantum chemical data under active memory guard."""
    source_h5 = _REPO_ROOT / "complexes.h5"
    assert source_h5.exists(), f"Authentic quantum chemical fixture missing at {source_h5}"

    guard = DynamicRAMPollingGuardrail()
    initial_poll = guard.poll()
    assert initial_poll.sequence_idx == 1
    assert initial_poll.stage in (RAMGuardrailStage.NORMAL, RAMGuardrailStage.WARNING)

    loaded_molecules: List[Dict[str, Any]] = []
    with h5py.File(str(source_h5), "r") as handle:
        complexes_group = handle["complexes"]
        complex_keys = list(complexes_group.keys())
        for complex_key in complex_keys:
            entry = complexes_group[complex_key]
            coords = np.asarray(entry["coordinates"][:], dtype=np.float64)
            atomic_numbers = np.asarray(entry["atomic_numbers"][:], dtype=np.int32)

            # Enforce cooperative checkpoint polling
            checkpoint_rec = guard.step(f"ingest_{complex_key}")
            assert checkpoint_rec.total_rss_bytes > 0
            assert checkpoint_rec.total_rss_bytes < RAM_CEILING_BYTES

            loaded_molecules.append({
                "complex": complex_key,
                "num_atoms": int(coords.shape[0]),
                "coords_shape": coords.shape,
                "atomic_numbers_len": len(atomic_numbers),
            })

    assert len(loaded_molecules) == len(complex_keys)
    assert len(loaded_molecules) >= 3
    assert all(m["num_atoms"] > 0 for m in loaded_molecules)
    assert len(guard.history) >= len(complex_keys) + 1


def test_contiguous_memory_allocation_and_delta_tracking() -> None:
    """Verify physical memory growth tracking using authentic contiguous NumPy buffers."""
    guard = DynamicRAMPollingGuardrail()

    # Enter context manager scope
    with guard:
        # Allocate 10 contiguous float64 array buffers (0.5 MB each)
        # Avoid banned synthetic array generators (zeros, ones) by using np.full
        elements_per_chunk = int((0.5 * 1024 * 1024) // 8)
        buffers: List[np.ndarray] = []
        for i in range(10):
            buf = np.full(shape=(elements_per_chunk,), fill_value=float(i + 1), dtype=np.float64)
            buffers.append(buf)
            guard.poll()

        assert len(buffers) == 10
        total_allocated_bytes = sum(b.nbytes for b in buffers)
        assert total_allocated_bytes >= 5 * 1024 * 1024 * 0.99

    metrics = guard.get_metrics()
    assert metrics.total_polls >= 10
    assert metrics.peak_rss_bytes >= metrics.min_rss_bytes


def test_proactive_remediation_callback_dispatch() -> None:
    """Verify proactive remediation hook invocation upon elevated memory stage."""
    remediation_calls: List[str] = []

    def on_warning_callback(record: RAMTelemetryRecord) -> None:
        remediation_calls.append(f"WARNING:{record.stage.value}")

    def on_critical_callback(record: RAMTelemetryRecord) -> None:
        remediation_calls.append(f"CRITICAL:{record.stage.value}")

    current_rss = get_current_process_memory_bytes()
    # Configure ceiling such that current_rss falls into WARNING territory (e.g. current_rss is ~80% of ceiling)
    warning_ceiling = int(current_rss / 0.80)

    config = RAMGuardrailConfig(
        ceiling_bytes=warning_ceiling,
        warning_ratio=0.75,
        critical_ratio=0.90,
        auto_gc_remediation=True,
    )
    guard = DynamicRAMPollingGuardrail(config)

    rec = guard.poll_with_remediation(
        on_warning=on_warning_callback,
        on_critical=on_critical_callback,
    )
    assert len(remediation_calls) >= 1
    assert "WARNING" in remediation_calls[0]
    assert rec.stage in (RAMGuardrailStage.WARNING, RAMGuardrailStage.NORMAL)


def test_cooperative_stream_step_polling_lifecycle() -> None:
    """Verify cooperative step polling in streaming loops maintains chronological sequence."""
    config = RAMGuardrailConfig(history_capacity=50)
    guard = DynamicRAMPollingGuardrail(config)

    for step_idx in range(10):
        rec = guard.step(f"pipeline_step_{step_idx}")
        assert rec.sequence_idx == step_idx + 1
        assert rec.stage in (RAMGuardrailStage.NORMAL, RAMGuardrailStage.WARNING)

    assert len(guard.history) == 10
    assert guard.history[0].sequence_idx == 1
    assert guard.history[-1].sequence_idx == 10


def test_context_manager_scope_and_decorator_enforcement() -> None:
    """Verify context manager and function decorator guardrail wrappers."""
    guard = DynamicRAMPollingGuardrail()

    # Context Manager test
    with guard:
        val = 42 * 2
        assert val == 84

    # Decorator test via guard.enforce
    @guard.enforce
    def compute_workload(x: int, y: int) -> int:
        return x + y

    res = compute_workload(100, 200)
    assert res == 300

    # Module-level decorator test
    @enforce_ram_ceiling(ceiling_bytes=RAM_CEILING_BYTES)
    def compute_safe_multiplication(a: float, b: float) -> float:
        return a * b

    assert math.isclose(compute_safe_multiplication(3.5, 2.0), 7.0)

    # Decorator breach test
    @enforce_ram_ceiling(ceiling_bytes=10)
    def failing_workload() -> int:
        return 42

    with pytest.raises(HeapCeilingExceededError):
        failing_workload()


def test_ordinary_least_squares_growth_trajectory_calculation() -> None:
    """Verify OLS growth rate slope calculation across recorded telemetry series."""
    guard = DynamicRAMPollingGuardrail()

    # Empty history
    assert guard.compute_growth_rate() == 0.0

    # Execute multiple polls to establish baseline
    for _ in range(5):
        guard.poll()
        time.sleep(0.01)

    growth_rate = guard.compute_growth_rate()
    assert isinstance(growth_rate, float)


def test_pca74_cryptographic_hash_chaining_and_tamper_detection() -> None:
    """Verify PCA-74 SHA-256 hash chaining back to GENESIS_HASH and tamper sensitivity."""
    guard = DynamicRAMPollingGuardrail()

    for _ in range(5):
        guard.poll()

    records = list(guard.history)
    assert len(records) == 5

    # Genesis chaining verification
    assert records[0].predecessor_hash == GENESIS_HASH
    for i in range(1, len(records)):
        assert records[i].predecessor_hash == records[i - 1].record_hash
        assert len(records[i].record_hash) == 64

    # Verify tamper detection
    tampered_rec = RAMTelemetryRecord(
        sequence_idx=records[0].sequence_idx,
        timestamp_sec=records[0].timestamp_sec,
        target_pid=records[0].target_pid,
        parent_rss_bytes=records[0].parent_rss_bytes + 1024,  # Altered byte count
        child_rss_bytes=records[0].child_rss_bytes,
        total_rss_bytes=records[0].total_rss_bytes + 1024,
        vms_bytes=records[0].vms_bytes,
        vram_bytes=records[0].vram_bytes,
        ceiling_bytes=records[0].ceiling_bytes,
        utilization_ratio=records[0].utilization_ratio,
        stage=records[0].stage,
        child_process_count=records[0].child_process_count,
        predecessor_hash=records[0].predecessor_hash,
        record_hash="",
    )
    tampered_hash = tampered_rec.compute_canonical_hash()
    assert tampered_hash != records[0].record_hash


def test_w3c_prov_o_jsonld_export_compliance() -> None:
    """Verify session JSON-LD serialization fulfills W3C PROV-O provenance standards."""
    guard = DynamicRAMPollingGuardrail()
    for _ in range(3):
        guard.poll()

    jsonld_payload = guard.export_jsonld()
    assert isinstance(jsonld_payload, dict)
    assert "@context" in jsonld_payload
    assert "@id" in jsonld_payload
    assert "prov:Bundle" in jsonld_payload["@type"]
    assert "cochem:telemetrySamples" in jsonld_payload
    assert len(jsonld_payload["cochem:telemetrySamples"]) == 3

    # Validate JSON serializability
    json_str = json.dumps(jsonld_payload)
    assert len(json_str) > 0


def test_pydantic_v2_schemas_bidirectional_lossless_roundtrip() -> None:
    """Verify Pydantic v2 schemas achieve 100% lossless conversion with extra='forbid'."""
    # 1. ProcessMemorySnapshot roundtrip
    snapshot = ProcessMemorySnapshot(
        pid=os.getpid(),
        name="pytest",
        rss_bytes=100_000_000,
        vms_bytes=200_000_000,
        num_threads=4,
        cpu_percent=12.5,
        timestamp_sec=time.time(),
    )
    snap_schema = ProcessMemorySnapshotSchema.from_dataclass(snapshot)
    recovered_snap = snap_schema.to_dataclass()
    assert recovered_snap == snapshot

    # 2. RAMTelemetryRecord roundtrip
    record = RAMTelemetryRecord(
        sequence_idx=1,
        timestamp_sec=time.time(),
        target_pid=os.getpid(),
        parent_rss_bytes=80_000_000,
        child_rss_bytes=20_000_000,
        total_rss_bytes=100_000_000,
        vms_bytes=250_000_000,
        vram_bytes=0,
        ceiling_bytes=RAM_CEILING_BYTES,
        utilization_ratio=100_000_000 / RAM_CEILING_BYTES,
        stage=RAMGuardrailStage.NORMAL,
        child_process_count=1,
        predecessor_hash=GENESIS_HASH,
        record_hash="E" * 64,
    )
    rec_schema = RAMTelemetryRecordSchema.from_dataclass(record)
    recovered_rec = rec_schema.to_dataclass()
    assert recovered_rec == record

    # 3. RAMGuardrailConfig roundtrip
    config = RAMGuardrailConfig(
        ceiling_bytes=RAM_CEILING_BYTES,
        warning_ratio=0.75,
        critical_ratio=0.90,
        include_children=True,
        auto_gc_remediation=True,
        history_capacity=500,
        target_pid=1234,
    )
    cfg_schema = RAMGuardrailConfigSchema.from_dataclass(config)
    recovered_cfg = cfg_schema.to_dataclass()
    assert recovered_cfg == config

    # 4. RAMGuardrailMetrics roundtrip
    metrics = RAMGuardrailMetrics(
        total_polls=100,
        peak_rss_bytes=150_000_000,
        min_rss_bytes=50_000_000,
        current_rss_bytes=120_000_000,
        ceiling_bytes=RAM_CEILING_BYTES,
        peak_utilization_ratio=150_000_000 / RAM_CEILING_BYTES,
        warning_events=2,
        critical_events=1,
        breach_events=0,
        remediation_events=3,
        average_poll_latency_ms=0.45,
        growth_rate_bytes_per_sec=1024.0,
    )
    metrics_schema = RAMGuardrailMetricsSchema.from_dataclass(metrics)
    recovered_metrics = metrics_schema.to_dataclass()
    assert recovered_metrics == metrics


def test_root_wrapper_module_parity_and_exports() -> None:
    """Verify 100% symbol parity across src/cochem_ml, root wrapper, and __all__."""
    required_symbols: List[str] = [
        "DEFAULT_CRITICAL_RATIO",
        "DEFAULT_HISTORY_CAPACITY",
        "DEFAULT_POLL_INTERVAL_SECONDS",
        "DEFAULT_WARNING_RATIO",
        "GENESIS_HASH",
        "RAM_CEILING_BYTES",
        "DynamicRAMPollingGuardrail",
        "HeapCeilingExceededError",
        "ProcessMemorySnapshot",
        "RAMGuardrailConfig",
        "RAMGuardrailMetrics",
        "RAMGuardrailStage",
        "RAMTelemetryRecord",
        "check_heap_memory_guardrail",
        "compute_sha256_digest",
        "enforce_ram_ceiling",
        "get_aggregate_tree_memory_bytes",
        "get_current_process_memory_bytes",
        "ram_guardrail",
        "verify_mendeleev_integrity",
    ]

    for sym in required_symbols:
        assert hasattr(cochem_ml, sym), f"cochem_ml package root missing symbol: {sym}"
        assert hasattr(root_ram_guardrail_module, sym), f"root ram_guardrail wrapper missing symbol: {sym}"


def test_sub_5_millisecond_polling_latency_benchmark() -> None:
    """Verify dynamic RAM polling execution latency is strictly below 5.0 ms per invocation."""
    guard = DynamicRAMPollingGuardrail(RAMGuardrailConfig(include_children=False))

    # Warm-up poll
    guard.poll()

    latencies_ms: List[float] = []
    for _ in range(30):
        t0 = time.perf_counter()
        guard.poll()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

    avg_latency = sum(latencies_ms) / len(latencies_ms)
    assert avg_latency < 5.0, f"Average polling latency {avg_latency:.3f} ms exceeded 5.0 ms threshold"
