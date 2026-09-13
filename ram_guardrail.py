"""Root-level entry point and module wrapper for Dynamic RAM Polling Guardrail Subsystem.

Governed by Method Matrix v4.2, Anti-Spoofing Protocol v4, Mendeleev Dynamic Mass Mandate,
and SRS-CHUNK-018-AG-ML-RL-TRANSITION-V1.0-20260913 (Task 1.13 & FR-04/FR-06).
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure src/ is on Python search path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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

__all__ = [
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
