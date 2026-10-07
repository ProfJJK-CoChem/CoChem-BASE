# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""cochem_base.chain -- Canonical State-Chaining Engine & Execution-Arrow Recorder.

Mandated by Method Matrix v4 (§8B, §8C) and Suggestion #157 (Deliverable 7).
Consolidates the authoritative state-chaining engine across the CoChem ecosystem.
"""

from __future__ import annotations

from .auditor import StateChainingAuditor
from .chain import (
    CANONICAL_ARROWS,
    ArrowState,
    CanonicalArrow,
    Chain,
    ChainStage,
    ConvergenceFailureError,
    CorruptOutputError,
    CounterpoiseType,
    ExecutionArrow,
    MissingBinaryError,
    Stage,
    StateRecord,
    PendingStateRecord,
    get_atomic_mass,
    get_isotopic_mass,
)

__all__ = [
    "Chain",
    "ChainStage",
    "Stage",
    "StateChainingAuditor",
    "ArrowState",
    "ExecutionArrow",
    "StateRecord",
    "PendingStateRecord",
    "CanonicalArrow",
    "CounterpoiseType",
    "CANONICAL_ARROWS",
    "get_atomic_mass",
    "get_isotopic_mass",
    "MissingBinaryError",
    "ConvergenceFailureError",
    "CorruptOutputError",
]
