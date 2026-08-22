Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc8_02_regex_traps_prompt.md.
Original prompt:
# Target File: D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_regex_traps.py

## Context
The telemetry system must proactively parse active standard output buffers (`stdout`/`stderr`) from heavy engines to detect mathematical failures before they result in hours of wasted compute time.

## Instructions
1. Implement an `EngineDialect` class or configuration mapping polymorphic regex traps to specific quantum chemistry engines (ORCA, CFOUR, PySCF).
2. Implement a NaN & Infinity Regex Trap: Use `re.compile` to evaluate 1MB chunked streams via the active `EngineDialect`. Actively hunt for `NaN` or `Infinity`. If detected, return a `NUMERICAL_COLLAPSE` state matrix flag (which will later invoke the Zombie Reaper).
3. Implement an SCF Ping-Pong Trap: Track the $\Delta E$ (change in energy) for the last 5 Self-Consistent Field (SCF) cycles. If the energy oscillates with reversing signs but constant magnitude, immediately flag the environment to inject a fallback solver (e.g., SOSCF or KDIIS) in the next iteration.
4. Implement a Linear Dependence Overlap Trap: Search for warnings indicating `eigenvalues < 10^{-6}` according to engine-specific dialects. If detected, flag the geometry/basis combination as ill-conditioned to halt the pipeline safely before matrix inversion fails.

## Constraints
- NO mocks, stubs, or placeholder implementations. Write the actual regex patterns and evaluation logic for standard computational chemistry outputs where possible.
- Adhere strictly to the Tripartite Workspace Air-Gap and Method Matrix rules. All code modifications must strictly target "D:\__CoChem\GitHub-Repo\CoChem-BASE".
- Design the stream parsing to handle inputs as chunked data rather than fully-loaded strings in memory.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_regex_traps.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8.02 - Quantum Chemistry Regex Traps & Stream Parser Engine
Implements:
1. Polymorphic EngineDialect configuration and regex mapping for ORCA, CFOUR, PySCF, and Auto-detection.
2. NaN & Infinity Trap: 1MB chunked streams, boundary overlaps, NUMERICAL_COLLAPSE state flag.
3. SCF Ping-Pong Trap: 5-cycle Delta E tracking, alternating sign oscillations with constant magnitude,
   SCF_PING_PONG_DETECTED state flag, and environment fallback solver injection (SOSCF or KDIIS).
4. Linear Dependence Overlap Trap: Dialect-specific warnings for overlap matrix eigenvalues < 1e-6,
   flagging geometry/basis as ill-conditioned, LINEAR_DEPENDENCE_DETECTED state flag.
5. Chunked stream processing (1MB chunks) across text / binary streams and files without loading whole files into memory.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    TextIO,
    Union,
)

logger = logging.getLogger("CoChem-RegexTraps")


# =====================================================================
# 1. Enums and State Flags
# =====================================================================

class EngineDialect(str, Enum):
    """Supported computational quantum chemistry engine dialects."""

    ORCA = "ORCA"
    CFOUR = "CFOUR"
    PYSCF = "PYSCF"
    AUTODETECT = "AUTODETECT"

    @classmethod
    def from_str(cls, val: Union[str, EngineDialect]) -> EngineDialect:
        """Parse dialect string with normalization and case insensitivity."""
        if isinstance(val, cls):
            return val
        if not isinstance(val, str):
            raise ValueError(f"Expected str or EngineDialect, got {type(val).__name__}: {val!r}")

        cleaned = val.strip().upper().replace("-", "").replace("_", "")
        if cleaned in ("ORCA",):
            return cls.ORCA
        if cleaned in ("CFOUR", "C4", "ACES2", "ACESII"):
            return cls.CFOUR
        if cleaned in ("PYSCF",):
            return cls.PYSCF
        if cleaned in ("AUTO", "AUTODETECT", "DETECT", "UNKNOWN"):
            return cls.AUTODETECT

        raise ValueError(f"Unknown dialect: {val!r}")


class TrapFlag(str, Enum):
    """Ecosystem-wide trap state flags emitted by the regex traps engine."""

    CLEAN = "CLEAN"
    NUMERICAL_COLLAPSE = "NUMERICAL_COLLAPSE"
    SCF_PING_PONG_DETECTED = "SCF_PING_PONG_DETECTED"
    LINEAR_DEPENDENCE_DETECTED = "LINEAR_DEPENDENCE_DETECTED"
    CONVERGENCE_FAILURE = "CONVERGENCE_FAILURE"


class FallbackSolver(str, Enum):
    """Fallback solver recommendations for SCF convergence stabilization."""

    SOSCF = "SOSCF"
    KDIIS = "KDIIS"
    DAMP_SHIFT = "DAMP_SHIFT"
    AUTO_AUX_STHRESH = "AUTO_AUX_STHRESH"
    NONE = "NONE"


class TrapSeverity(str, Enum):
    """Severity classification of detected trap events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =====================================================================
# 2. Structured Dataclasses
# =====================================================================

@dataclass
class SCFCycleRecord:
    """Individual SCF iteration telemetry extracted from engine output."""

    cycle: int
    energy: float
    delta_e: float
    raw_line: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record to dictionary."""
        return asdict(self)


@dataclass
class PingPongAnalysis:
    """Detailed analytics on SCF energy oscillation / ping-pong pathology."""

    detected: bool = False
    cycle_count: int = 0
    delta_e_series: List[float] = field(default_factory=list)
    mean_abs_delta: float = 0.0
    std_abs_delta: float = 0.0
    recommended_fallback: Optional[FallbackSolver] = None
    confidence_score: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize analysis to dictionary."""
        d = asdict(self)
        if self.recommended_fallback:
            d["recommended_fallback"] = self.recommended_fallback.value
        return d


@dataclass
class LinearDependenceRecord:
    """Overlap matrix linear dependence and eigenvalue diagnostics."""

    detected: bool = False
    min_eigenvalue: Optional[float] = None
    threshold: float = 1e-6
    ill_conditioned: bool = False
    matched_lines: List[str] = field(default_factory=list)
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record to dictionary."""
        return asdict(self)


@dataclass
class NumericalCollapseRecord:
    """IEEE floating-point breakdown / NaN / Inf pathology record."""

    detected: bool = False
    token: str = ""
    offset: int = 0
    line_number: Optional[int] = None
    context_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize record to dictionary."""
        return asdict(self)


@dataclass
class TrapDetectionEvent:
    """Discrete trap trigger event emitted during stream evaluation."""

    flag: TrapFlag
    dialect: EngineDialect
    severity: TrapSeverity
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)
    recommended_fallback: Optional[str] = None
    is_terminal: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        d = asdict(self)
        d["flag"] = self.flag.value
        d["dialect"] = self.dialect.value
        d["severity"] = self.severity.value
        return d


@dataclass
class TrapScanReport:
    """Comprehensive diagnostic scan report produced from stream / file evaluation."""

    primary_flag: TrapFlag = TrapFlag.CLEAN
    detected_dialect: EngineDialect = EngineDialect.AUTODETECT
    events: List[TrapDetectionEvent] = field(default_factory=list)
    numerical_collapse: Optional[NumericalCollapseRecord] = None
    scf_ping_pong: Optional[PingPongAnalysis] = None
    linear_dependence: Optional[LinearDependenceRecord] = None
    scf_history: List[SCFCycleRecord] = field(default_factory=list)
    total_bytes_processed: int = 0
    total_chunks_processed: int = 0
    environment_recommendations: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to structured dictionary."""
        return {
            "primary_flag": self.primary_flag.value,
            "detected_dialect": self.detected_dialect.value,
            "events": [e.to_dict() for e in self.events],
            "numerical_collapse": self.numerical_collapse.to_dict() if self.numerical_collapse else None,
            "scf_ping_pong": self.scf_ping_pong.to_dict() if self.scf_ping_pong else None,
            "linear_dependence": self.linear_dependence.to_dict() if self.linear_dependence else None,
            "scf_history": [s.to_dict() for s in self.scf_history],
            "total_bytes_processed": self.total_bytes_processed,
            "total_chunks_processed": self.total_chunks_processed,
            "environment_recommendations": self.environment_recommendations,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# =====================================================================
# 3. Polymorphic Regex Mappings & Engine Signatures
# =====================================================================

# Universal IEEE Floating Point Collapse Regex:
# Traps: NaN, NaNQ, NaNS, Infinity, +Infinity, -Infinity, inf, +inf, -inf,
# 1.#IND, -1.#IND, 1.#INF, -1.#INF, 1.#QNAN, 1.#SNAN
NUMERICAL_COLLAPSE_REGEX: re.Pattern = re.compile(
    r"(?<![a-zA-Z0-9_])(?P<token>[-+]?nan[qs]?|[-+]?infinity|[-+]?inf|[-+]?1\.#(?:ind|inf|qnan|snan))(?![a-zA-Z0-9_])",
    re.IGNORECASE,
)


@dataclass
class EngineRegexMap:
    """Compiled regex pattern maps configured for an electronic structure dialect."""

    dialect: EngineDialect
    dialect_signatures: List[re.Pattern] = field(default_factory=list)
    scf_cycle_patterns: List[re.Pattern] = field(default_factory=list)
    linear_dependence_patterns: List[re.Pattern] = field(default_factory=list)


def _build_orca_regex_map() -> EngineRegexMap:
    """Build compiled patterns tailored for ORCA 5.x/6.x stdout logs."""
    signatures = [
        re.compile(r"\*\s*O\s+R\s+C\s+A\s*\*", re.IGNORECASE),
        re.compile(r"Program Version\s+\d+", re.IGNORECASE),
        re.compile(r"An ab initio.*electronic structure package", re.IGNORECASE),
        re.compile(r"TOTAL RUN TIME:\s*\d+", re.IGNORECASE),
    ]
    scf_patterns = [
        re.compile(
            r"^\s*Iter\s+(?P<cycle>\d+)\s*:\s+Energy=\s*(?P<energy>[-+]?\d+\.\d+)\s+DeltaE=\s*(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?P<cycle>\d+)\s+[-+]?\d+\.\d+\s+[-+]?\d+\.\d+\s+(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\s+(?P<energy>[-+]?\d+\.\d+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*SCF ITERATION\s+(?P<cycle>\d+).*?Total Energy:\s*(?P<energy>[-+]?\d+\.\d+).*?(?:Delta-E|Delta E|Change):\s*(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            r"Smallest eigenvalue of the overlap matrix\s*:\s*(?P<val>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"WARNING:\s*There are\s+\d+\s+small eigenvalues\s*\(<\s*(?P<thresh>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\)\s*in the overlap matrix",
            re.IGNORECASE,
        ),
        re.compile(
            r"WARNING:\s*Basis set has linear dependencies",
            re.IGNORECASE,
        ),
        re.compile(
            r"Linear dependency in the basis set",
            re.IGNORECASE,
        ),
        re.compile(
            r"Smallest eigenvalue of metric matrix\s*:\s*(?P<val>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
    ]
    return EngineRegexMap(
        dialect=EngineDialect.ORCA,
        dialect_signatures=signatures,
        scf_cycle_patterns=scf_patterns,
        linear_dependence_patterns=linear_dep_patterns,
    )


def _build_cfour_regex_map() -> EngineRegexMap:
    """Build compiled patterns tailored for CFOUR 2.x stdout logs."""
    signatures = [
        re.compile(r"EXECUTION OF CFOUR", re.IGNORECASE),
        re.compile(r"ACES2", re.IGNORECASE),
        re.compile(r"ZMAT input file found", re.IGNORECASE),
        re.compile(r"CFOUR Suite", re.IGNORECASE),
    ]
    scf_patterns = [
        re.compile(
            r"^\s*Iter\s+(?P<cycle>\d+)\s+(?P<energy>[-+]?\d+\.\d+)\s+(?P<delta>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*SCF ITERATION\s+#\s*(?P<cycle>\d+)\s+TOTAL ENERGY\s*=\s*(?P<energy>[-+]?\d+\.\d+)\s+CHANGE\s*=\s*(?P<delta>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?P<cycle>\d+)\s+[-+]?\d+\.\d+\s+(?P<energy>[-+]?\d+\.\d+)\s+(?P<delta>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            r"WARNING:\s*Overlap matrix has eigenvalues smaller than\s*(?P<thresh>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)\s*:\s*(?P<val>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"Linear dependenc(?:y|ies) detected in(?: atomic orbital)? basis",
            re.IGNORECASE,
        ),
        re.compile(
            r"Smallest eigenvalue of overlap matrix is\s+(?P<val>[-+]?\d+\.\d+(?:[dDeE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"Overlap matrix is near-singular",
            re.IGNORECASE,
        ),
    ]
    return EngineRegexMap(
        dialect=EngineDialect.CFOUR,
        dialect_signatures=signatures,
        scf_cycle_patterns=scf_patterns,
        linear_dependence_patterns=linear_dep_patterns,
    )


def _build_pyscf_regex_map() -> EngineRegexMap:
    """Build compiled patterns tailored for PySCF / gpu4pyscf stdout logs."""
    signatures = [
        re.compile(r"PySCF", re.IGNORECASE),
        re.compile(r"pyscf\.scf", re.IGNORECASE),
        re.compile(r"pyscf\.dft", re.IGNORECASE),
        re.compile(r"converged SCF energy =", re.IGNORECASE),
    ]
    scf_patterns = [
        re.compile(
            r"^\s*cycle\s*=\s*(?P<cycle>\d+)\s+E\s*=\s*(?P<energy>[-+]?\d+\.\d+)\s+delta_E\s*=\s*(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*SCF\s+cycle\s+(?P<cycle>\d+)\s+E\(SCF\)\s*=\s*(?P<energy>[-+]?\d+\.\d+)\s+delta\s*=\s*(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*cycle\s+(?P<cycle>\d+):\s+E\s*=\s*(?P<energy>[-+]?\d+\.\d+)\s+dE\s*=\s*(?P<delta>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            r"Small(?:est)? eigenvalue of overlap matrix\s*:\s*(?P<val>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"Small eigenvalue of overlap matrix:\s*(?P<val>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\s*<\s*(?P<thresh>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(
            r"Linear dependency in basis set\s*\(eigenvalue\s*<\s*(?P<thresh>[-+]?\d+\.\d+(?:[eE][-+]?\d+)?)\)",
            re.IGNORECASE,
        ),
        re.compile(
            r"Basis set linear dependence detected",
            re.IGNORECASE,
        ),
    ]
    return EngineRegexMap(
        dialect=EngineDialect.PYSCF,
        dialect_signatures=signatures,
        scf_cycle_patterns=scf_patterns,
        linear_dependence_patterns=linear_dep_patterns,
    )


# Registry cache
_DIALECT_REGISTRY: Dict[EngineDialect, EngineRegexMap] = {
    EngineDialect.ORCA: _build_orca_regex_map(),
    EngineDialect.CFOUR: _build_cfour_regex_map(),
    EngineDialect.PYSCF: _build_pyscf_regex_map(),
}


def get_dialect_regex_map(dialect: EngineDialect) -> EngineRegexMap:
    """Retrieve compiled regex mapping for specified dialect, defaulting to ORCA."""
    if dialect in _DIALECT_REGISTRY:
        return _DIALECT_REGISTRY[dialect]
    return _DIALECT_REGISTRY[EngineDialect.ORCA]


def autodetect_dialect(text_sample: str) -> EngineDialect:
    """Inspect text header or content to identify dialect from engine signatures."""
    for dialect, rmap in _DIALECT_REGISTRY.items():
        for sig in rmap.dialect_signatures:
            if sig.search(text_sample):
                return dialect
    return EngineDialect.AUTODETECT


def _safe_float(val_str: str) -> float:
    """Parse scientific float safely supporting Fortran D/d and standard E/e exponents."""
    cleaned = val_str.strip().replace("D", "E").replace("d", "e")
    return float(cleaned)


# =====================================================================
# 4. SCF Ping-Pong Analysis Implementation
# =====================================================================

def evaluate_scf_ping_pong(
    scf_records: List[SCFCycleRecord],
    window_size: int = 5,
    min_magnitude: float = 1e-7,
    max_relative_variance: float = 0.35,
) -> PingPongAnalysis:
    """
    Evaluate SCF history for alternating sign oscillations with constant or near-constant magnitude.
    """
    if len(scf_records) < window_size:
        return PingPongAnalysis(detected=False, cycle_count=len(scf_records))

    deltas = [r.delta_e for r in scf_records]

    # Slide a window of size `window_size` across the history
    for i in range(len(deltas) - window_size + 1):
        win = deltas[i : i + window_size]

        # Check condition 1: Alternating signs across all adjacent pairs
        is_alternating = True
        for j in range(len(win) - 1):
            if win[j] * win[j + 1] >= 0:
                is_alternating = False
                break

        if not is_alternating:
            continue

        # Check condition 2: Non-trivial magnitude
        abs_win = [abs(x) for x in win]
        if any(x < min_magnitude for x in abs_win):
            continue

        # Check condition 3: Constant / near-constant magnitude
        mean_abs = statistics.mean(abs_win)
        std_abs = statistics.stdev(abs_win) if len(abs_win) > 1 else 0.0
        rel_std = std_abs / mean_abs if mean_abs > 0 else 0.0

        if rel_std <= max_relative_variance or (max(abs_win) - min(abs_win)) / mean_abs <= 0.5:
            explanation = (
                f"SCF Ping-Pong detected over {window_size} cycles (indices {i+1} to {i+window_size}): "
                f"alternating signs with mean |Delta E|={mean_abs:.6e} and relative std={rel_std:.3f}."
            )
            return PingPongAnalysis(
                detected=True,
                cycle_count=len(scf_records),
                delta_e_series=win,
                mean_abs_delta=mean_abs,
                std_abs_delta=std_abs,
                recommended_fallback=FallbackSolver.SOSCF,
                confidence_score=round(max(0.0, 1.0 - rel_std), 4),
                explanation=explanation,
            )

    return PingPongAnalysis(
        detected=False,
        cycle_count=len(scf_records),
        delta_e_series=deltas[-window_size:],
    )


# =====================================================================
# 5. Core Regex Traps Engine & Chunked Stream Scanner
# =====================================================================

class RegexTrapEngine:
    """
    Production-grade streaming regex trap scanner for computational chemistry engines.
    """

    def __init__(
        self,
        dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
        chunk_size_bytes: int = 1024 * 1024,  # 1 MB
        overlap_bytes: int = 4096,  # 4 KB
        eigenvalue_threshold: float = 1e-6,
    ) -> None:
        self.requested_dialect = EngineDialect.from_str(dialect)
        self.active_dialect = self.requested_dialect
        self.chunk_size_bytes = chunk_size_bytes
        self.overlap_bytes = overlap_bytes
        self.eigenvalue_threshold = eigenvalue_threshold

        # Internal state tracking
        self._regex_map = get_dialect_regex_map(
            self.active_dialect if self.active_dialect != EngineDialect.AUTODETECT else EngineDialect.ORCA
        )
        self._scf_records: List[SCFCycleRecord] = []
        self._events: List[TrapDetectionEvent] = []
        self._numerical_collapse: Optional[NumericalCollapseRecord] = None
        self._linear_dependence: Optional[LinearDependenceRecord] = None
        self._total_bytes = 0
        self._total_chunks = 0
        self._line_counter = 0
        self._overlap_buffer = ""
        self._line_buffer = ""
        self._environment_recommendations: Dict[str, Any] = {}

    def reset(self) -> None:
        """Reset internal accumulator state for a new scan."""
        self.active_dialect = self.requested_dialect
        self._regex_map = get_dialect_regex_map(
            self.active_dialect if self.active_dialect != EngineDialect.AUTODETECT else EngineDialect.ORCA
        )
        self._scf_records.clear()
        self._events.clear()
        self._numerical_collapse = None
        self._linear_dependence = None
        self._total_bytes = 0
        self._total_chunks = 0
        self._line_counter = 0
        self._overlap_buffer = ""
        self._line_buffer = ""
        self._environment_recommendations.clear()

    def feed_line(self, line: str) -> Optional[TrapDetectionEvent]:
        """
        Process a single output line incrementally in real-time.
        """
        self._line_counter += 1
        line_clean = line.rstrip("\r\n")

        # 1. Dialect auto-detection if pending
        if self.active_dialect == EngineDialect.AUTODETECT:
            detected = autodetect_dialect(line_clean)
            if detected != EngineDialect.AUTODETECT:
                self.active_dialect = detected
                self._regex_map = get_dialect_regex_map(self.active_dialect)

        # 2. Check Numerical Collapse on this line
        match_collapse = NUMERICAL_COLLAPSE_REGEX.search(line_clean)
        if match_collapse and (self._numerical_collapse is None or not self._numerical_collapse.detected):
            token = match_collapse.group("token")
            self._numerical_collapse = NumericalCollapseRecord(
                detected=True,
                token=token,
                offset=self._total_bytes,
                line_number=self._line_counter,
                context_snippet=line_clean[:200],
            )
            event = TrapDetectionEvent(
                flag=TrapFlag.NUMERICAL_COLLAPSE,
                dialect=self.active_dialect,
                severity=TrapSeverity.CRITICAL,
                description=f"Numerical collapse detected: IEEE invalid token {token!r} at line {self._line_counter}.",
                details={"token": token, "line_number": self._line_counter, "line": line_clean},
                is_terminal=True,
            )
            self._events.append(event)
            return event

        # 3. Check Linear Dependence on this line
        for pat in self._regex_map.linear_dependence_patterns:
            m = pat.search(line_clean)
            if m:
                val: Optional[float] = None
                thresh: float = self.eigenvalue_threshold
                if "val" in m.groupdict() and m.group("val"):
                    try:
                        val = _safe_float(m.group("val"))
                    except ValueError:
                        val = None
                if "thresh" in m.groupdict() and m.group("thresh"):
                    try:
                        thresh = _safe_float(m.group("thresh"))
                    except ValueError:
                        thresh = self.eigenvalue_threshold

                is_triggered = False
                if val is not None:
                    if val < self.eigenvalue_threshold:
                        is_triggered = True
                else:
                    is_triggered = True

                if is_triggered:
                    if self._linear_dependence is None or not self._linear_dependence.detected:
                        rec_action = "Inject AutoAux and enforce SThresh 1e-5 to project out linear dependencies."
                        self._linear_dependence = LinearDependenceRecord(
                            detected=True,
                            min_eigenvalue=val,
                            threshold=thresh,
                            ill_conditioned=True,
                            matched_lines=[line_clean],
                            recommended_action=rec_action,
                        )
                        self._environment_recommendations["linear_dependence_mitigation"] = {
                            "auto_aux": True,
                            "sthresh": 1e-5,
                            "autostart": 1e-4,
                        }
                        event = TrapDetectionEvent(
                            flag=TrapFlag.LINEAR_DEPENDENCE_DETECTED,
                            dialect=self.active_dialect,
                            severity=TrapSeverity.WARNING,
                            description=f"Linear dependence in overlap matrix detected (min eigenvalue={val}).",
                            details={"min_eigenvalue": val, "line": line_clean},
                            recommended_fallback="AutoAux / SThresh",
                        )
                        self._events.append(event)
                        return event
                    else:
                        self._linear_dependence.matched_lines.append(line_clean)

        # 4. Check SCF Iteration Parsing on this line
        for pat in self._regex_map.scf_cycle_patterns:
            m = pat.search(line_clean)
            if m:
                try:
                    cycle = int(m.group("cycle"))
                    energy = _safe_float(m.group("energy"))
                    delta = _safe_float(m.group("delta"))
                    record = SCFCycleRecord(cycle=cycle, energy=energy, delta_e=delta, raw_line=line_clean)
                    self._scf_records.append(record)

                    analysis = evaluate_scf_ping_pong(self._scf_records)
                    if analysis.detected:
                        if not any(e.flag == TrapFlag.SCF_PING_PONG_DETECTED for e in self._events):
                            self._environment_recommendations.update({
                                "solver": "SOSCF",
                                "fallback_diis": "KDIIS",
                                "damping": 0.2,
                                "level_shift": 0.1,
                                "shift": 0.1,
                                "damp": 0.2,
                            })
                            event = TrapDetectionEvent(
                                flag=TrapFlag.SCF_PING_PONG_DETECTED,
                                dialect=self.active_dialect,
                                severity=TrapSeverity.ERROR,
                                description=analysis.explanation,
                                details=analysis.to_dict(),
                                recommended_fallback="SOSCF",
                            )
                            self._events.append(event)
                            return event
                except (ValueError, KeyError):
                    pass
                break

        return None

    def feed_chunk(self, chunk: Union[str, bytes]) -> List[TrapDetectionEvent]:
        """
        Feed a raw chunk of text or binary data into the scanner.
        Handles boundary overlap buffer and line buffering across chunks.
        """
        if isinstance(chunk, bytes):
            text_chunk = chunk.decode("utf-8", errors="replace")
            byte_len = len(chunk)
        else:
            text_chunk = chunk
            byte_len = len(chunk.encode("utf-8", errors="replace"))

        self._total_bytes += byte_len
        self._total_chunks += 1
        new_events: List[TrapDetectionEvent] = []

        # 1. Check for numerical collapse across boundary overlap buffer
        combined_overlap = self._overlap_buffer + text_chunk
        match_collapse = NUMERICAL_COLLAPSE_REGEX.search(combined_overlap)
        if match_collapse and (self._numerical_collapse is None or not self._numerical_collapse.detected):
            token = match_collapse.group("token")
            self._numerical_collapse = NumericalCollapseRecord(
                detected=True,
                token=token,
                offset=max(0, self._total_bytes - len(text_chunk)),
                line_number=self._line_counter + 1,
                context_snippet=combined_overlap[max(0, match_collapse.start() - 50) : min(len(combined_overlap), match_collapse.end() + 50)],
            )
            event = TrapDetectionEvent(
                flag=TrapFlag.NUMERICAL_COLLAPSE,
                dialect=self.active_dialect,
                severity=TrapSeverity.CRITICAL,
                description=f"Numerical collapse detected: {token!r} across chunk boundary.",
                details={"token": token},
                is_terminal=True,
            )
            self._events.append(event)
            new_events.append(event)

        # Update overlap buffer for next chunk
        if len(text_chunk) >= self.overlap_bytes:
            self._overlap_buffer = text_chunk[-self.overlap_bytes :]
        else:
            self._overlap_buffer = combined_overlap[-self.overlap_bytes :]

        # 2. Line buffering and feeding complete lines
        data_to_process = self._line_buffer + text_chunk
        lines = data_to_process.splitlines(keepends=True)
        if lines:
            # If the last line does not end with a newline, hold it in line buffer
            if lines[-1].endswith(("\n", "\r")):
                self._line_buffer = ""
                for line in lines:
                    ev = self.feed_line(line)
                    if ev:
                        new_events.append(ev)
            else:
                self._line_buffer = lines[-1]
                for line in lines[:-1]:
                    ev = self.feed_line(line)
                    if ev:
                        new_events.append(ev)

        return new_events

    def finalize(self) -> TrapScanReport:
        """
        Finalize scan report and flush any remaining buffered lines.
        """
        if self._line_buffer:
            ev = self.feed_line(self._line_buffer)
            if ev and ev not in self._events:
                self._events.append(ev)
            self._line_buffer = ""

        ping_pong_analysis = evaluate_scf_ping_pong(self._scf_records)

        # Determine primary flag
        if self._numerical_collapse and self._numerical_collapse.detected:
            primary_flag = TrapFlag.NUMERICAL_COLLAPSE
        elif ping_pong_analysis.detected:
            primary_flag = TrapFlag.SCF_PING_PONG_DETECTED
        elif self._linear_dependence and self._linear_dependence.detected:
            primary_flag = TrapFlag.LINEAR_DEPENDENCE_DETECTED
        else:
            primary_flag = TrapFlag.CLEAN

        final_dialect = self.active_dialect
        if final_dialect == EngineDialect.AUTODETECT:
            final_dialect = EngineDialect.ORCA

        report = TrapScanReport(
            primary_flag=primary_flag,
            detected_dialect=final_dialect,
            events=list(self._events),
            numerical_collapse=self._numerical_collapse,
            scf_ping_pong=ping_pong_analysis if ping_pong_analysis.detected else None,
            linear_dependence=self._linear_dependence,
            scf_history=list(self._scf_records),
            total_bytes_processed=self._total_bytes,
            total_chunks_processed=self._total_chunks,
            environment_recommendations=dict(self._environment_recommendations),
        )
        return report

    def scan_stream(
        self,
        stream: Union[TextIO, BinaryIO, io.IOBase, Iterator[Union[str, bytes]], Iterable[Union[str, bytes]]],
        dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
    ) -> TrapScanReport:
        """
        Scan a text or binary stream in 1MB chunks without reading entire stream into memory.
        """
        self.reset()
        self.requested_dialect = EngineDialect.from_str(dialect)
        self.active_dialect = self.requested_dialect
        self._regex_map = get_dialect_regex_map(
            self.active_dialect if self.active_dialect != EngineDialect.AUTODETECT else EngineDialect.ORCA
        )

        if hasattr(stream, "read"):
            while True:
                chunk = stream.read(self.chunk_size_bytes)
                if not chunk:
                    break
                self.feed_chunk(chunk)
        else:
            for item in stream:
                self.feed_chunk(item)

        return self.finalize()

    def scan_file(
        self,
        file_path: Union[str, Path],
        dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
    ) -> TrapScanReport:
        """
        Scan a physical file on disk in 1MB chunks.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Target log file does not exist: {path}")

        self.reset()
        self.requested_dialect = EngineDialect.from_str(dialect)
        self.active_dialect = self.requested_dialect

        with path.open("rb") as f:
            while True:
                chunk = f.read(self.chunk_size_bytes)
                if not chunk:
                    break
                self.feed_chunk(chunk)

        return self.finalize()

    def scan_text(
        self,
        text: str,
        dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
    ) -> TrapScanReport:
        """Scan an in-memory string using stream chunking."""
        return self.scan_stream(io.StringIO(text), dialect=dialect)

    def scan_bytes(
        self,
        data: bytes,
        dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
    ) -> TrapScanReport:
        """Scan in-memory raw bytes using stream chunking."""
        return self.scan_stream(io.BytesIO(data), dialect=dialect)


# =====================================================================
# 6. Convenience Functional Interface
# =====================================================================

def scan_log_for_traps(
    target: Union[str, bytes, Path, TextIO, BinaryIO],
    dialect: Union[EngineDialect, str] = EngineDialect.AUTODETECT,
    chunk_size_bytes: int = 1024 * 1024,
) -> TrapScanReport:
    """
    Convenience function to scan a string, file path, or stream for quantum chemistry traps.
    """
    engine = RegexTrapEngine(dialect=dialect, chunk_size_bytes=chunk_size_bytes)
    if isinstance(target, Path) or (isinstance(target, str) and os.path.exists(target)):
        return engine.scan_file(target, dialect=dialect)
    if isinstance(target, str):
        return engine.scan_text(target, dialect=dialect)
    if isinstance(target, bytes):
        return engine.scan_bytes(target, dialect=dialect)
    return engine.scan_stream(target, dialect=dialect)

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_regex_traps.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Zero-Mock Physical Test Suite for CoChem-BASE Regex Traps Subsystem.
Tests:
1. Polymorphic EngineDialect configuration and regex mapping for ORCA, CFOUR, PySCF, and Auto-detection.
2. NaN & Infinity Trap: 1MB chunked stream evaluation, boundary overlap detection, NUMERICAL_COLLAPSE state flag.
3. SCF Ping-Pong Trap: 5-cycle Delta E tracking, alternating sign oscillation detection with constant magnitude,
   SCF_PING_PONG_DETECTED flag, and fallback solver recommendations (SOSCF / KDIIS).
4. Linear Dependence Overlap Trap: Dialect-specific warnings for overlap matrix eigenvalues < 1e-6,
   flagging geometry/basis as ill-conditioned, LINEAR_DEPENDENCE_DETECTED state flag.
5. Chunked stream processing (1MB chunks) across text / binary streams and files without loading whole files into memory.
6. Incremental live stream feed and multi-trap composite scan reports.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from typing import List

import pytest

from core_engine.cochem_regex_traps import (
    EngineDialect,
    FallbackSolver,
    RegexTrapEngine,
    TrapDetectionEvent,
    TrapFlag,
    autodetect_dialect,
    get_dialect_regex_map,
)

# =====================================================================
# 1. EngineDialect Configuration & Polymorphic Mapping Tests
# =====================================================================

class TestEngineDialectAndMapping:
    """Validates dialect enumeration, parsing, regex mapping, and auto-detection."""

    def test_dialect_enum_values_and_from_str(self) -> None:
        """Verifies dialect parsing from string with various casing."""
        assert EngineDialect.from_str("orca") == EngineDialect.ORCA
        assert EngineDialect.from_str("ORCA") == EngineDialect.ORCA
        assert EngineDialect.from_str("cfour") == EngineDialect.CFOUR
        assert EngineDialect.from_str("C-FOUR") == EngineDialect.CFOUR
        assert EngineDialect.from_str("pyscf") == EngineDialect.PYSCF
        assert EngineDialect.from_str("PySCF") == EngineDialect.PYSCF
        assert EngineDialect.from_str("auto") == EngineDialect.AUTODETECT
        assert EngineDialect.from_str("autodetect") == EngineDialect.AUTODETECT

        with pytest.raises(ValueError, match="Unknown dialect"):
            EngineDialect.from_str("unsupported_engine_xyz")

    def test_dialect_regex_mapping_registry(self) -> None:
        """Verifies each dialect provides distinct compiled regex patterns."""
        for dialect in [EngineDialect.ORCA, EngineDialect.CFOUR, EngineDialect.PYSCF]:
            regex_map = get_dialect_regex_map(dialect)
            assert regex_map.dialect == dialect
            assert len(regex_map.scf_cycle_patterns) > 0
            assert len(regex_map.linear_dependence_patterns) > 0
            assert len(regex_map.dialect_signatures) > 0

    def test_autodetect_orca_banner(self) -> None:
        """Tests auto-detection of ORCA log header."""
        sample_orca_header = """
        ================================================================================
                                          * O   R   C   A *
        ================================================================================
        Program Version 6.1.0 - RELEASE
        An ab initio, DFT and semiempirical electronic structure package
        """
        assert autodetect_dialect(sample_orca_header) == EngineDialect.ORCA

    def test_autodetect_cfour_banner(self) -> None:
        """Tests auto-detection of CFOUR log header."""
        sample_cfour_header = """
        ================================================================================
                       EXECUTION OF CFOUR (ACES2) SUITE BEGINS
        ================================================================================
        ZMAT input file found. Starting quantum mechanical calculation.
        """
        assert autodetect_dialect(sample_cfour_header) == EngineDialect.CFOUR

    def test_autodetect_pyscf_banner(self) -> None:
        """Tests auto-detection of PySCF output stream."""
        sample_pyscf_header = """
        ******** PySCF-2.5.0 ********
        pyscf.scf.hf.RHF object at 0x7f9a12345678
        geometry coordinates initialized.
        """
        assert autodetect_dialect(sample_pyscf_header) == EngineDialect.PYSCF

    def test_autodetect_unknown_defaults_to_orca(self) -> None:
        """Tests fallback when no signature matches."""
        generic_text = "Some random computation output without package signatures."
        assert autodetect_dialect(generic_text) == EngineDialect.AUTODETECT


# =====================================================================
# 2. NaN & Infinity Trap (Numerical Collapse) Tests
# =====================================================================

class TestNumericalCollapseTrap:
    """Validates IEEE float collapse detection across patterns, chunks, and boundaries."""

    @pytest.mark.parametrize(
        "token",
        [
            "NaN",
            "nan",
            "NAN",
            "+NaN",
            "-NaN",
            "NaNQ",
            "NaNS",
            "Infinity",
            "+Infinity",
            "-Infinity",
            "inf",
            "+inf",
            "-inf",
            "1.#IND",
            "-1.#IND",
            "1.#INF",
            "-1.#INF",
            "1.#QNAN",
            "1.#SNAN",
        ],
    )
    def test_numerical_collapse_tokens_detection(self, token: str) -> None:
        """Tests that all IEEE floating point invalid numerical states are trapped."""
        log_sample = f"""
        Iter  12: Energy= -76.421980012 DeltaE= -0.00012300
        Iter  13: Energy= {token} DeltaE= -0.00000000
        Iter  14: Energy= {token} DeltaE= 0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_sample, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None
        assert report.numerical_collapse.detected is True
        assert token.lower() in report.numerical_collapse.token.lower() or report.numerical_collapse.token.lower() in token.lower()

    def test_numerical_collapse_ignores_safe_words(self) -> None:
        """Ensures plain words like 'information', 'infinite', or 'influence' are not false positives."""
        clean_text = """
        Calculation information:
        The infinite dilution limit is approximated with CPCM.
        The influence of polarization functions was evaluated.
        Total Energy: -154.29817451 Hartree
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(clean_text, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.numerical_collapse is None or not report.numerical_collapse.detected

    def test_numerical_collapse_chunk_boundary_overlap(self) -> None:
        """
        Tests that a numerical collapse token split across consecutive 1MB chunk boundaries
        is correctly trapped due to boundary overlap buffer.
        """
        chunk_size = 64 * 1024  # 64 KB for test speed with overlap
        engine = RegexTrapEngine(chunk_size_bytes=chunk_size, overlap_bytes=1024)

        # Construct a text where "1.#IND" is sliced exactly at chunk boundary
        # chunk 1 ends with "1.#" and chunk 2 starts with "IND "
        prefix_pad = "Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000\n" * 100
        pad_len = chunk_size - len(prefix_pad) - len("Iter 101 : Energy= 1.#")
        part1 = prefix_pad + (" " * max(0, pad_len)) + "Iter 101 : Energy= 1.#"
        part2 = "IND  DeltaE= 0.00000000\n" + (" " * 5000)
        full_stream = io.StringIO(part1 + part2)

        report = engine.scan_stream(full_stream, dialect=EngineDialect.ORCA)
        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None
        assert report.numerical_collapse.detected is True
        assert "1.#IND" in report.numerical_collapse.token



# =====================================================================
# 3. SCF Ping-Pong Trap Tests
# =====================================================================

class TestSCFPingPongTrap:
    """Validates SCF Ping-Pong oscillation detection for ORCA, CFOUR, and PySCF."""

    def test_orca_scf_ping_pong_detection(self) -> None:
        """
        Tests ORCA SCF log showing 5 alternating Delta E cycles with constant magnitude,
        verifying SCF_PING_PONG_DETECTED and SOSCF/KDIIS solver recommendation.
        """
        orca_log = """
        ----------------------------------
        SCF ITERATIONS (ORCA format)
        ----------------------------------
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True
        assert report.scf_ping_pong.recommended_fallback in [FallbackSolver.SOSCF, FallbackSolver.KDIIS]
        assert "solver" in report.environment_recommendations
        assert report.environment_recommendations["solver"] in ["SOSCF", "KDIIS"]
        assert len(report.scf_history) >= 7

    def test_cfour_scf_ping_pong_detection_with_d_notation(self) -> None:
        """
        Tests CFOUR SCF log with Fortran D-exponent formatting showing 5 oscillating cycles.
        """
        cfour_log = """
        EXECUTION OF CFOUR SUITE
        Iter   1   -100.15000000   -0.4500D+00
        Iter   2   -100.28000000   -0.1300D+00
        Iter   3   -100.28350000   +0.3500D-02
        Iter   4   -100.28000000   -0.3500D-02
        Iter   5   -100.28350000   +0.3500D-02
        Iter   6   -100.28000000   -0.3500D-02
        Iter   7   -100.28350000   +0.3500D-02
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(cfour_log, dialect=EngineDialect.CFOUR)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True
        assert report.scf_ping_pong.recommended_fallback in [FallbackSolver.SOSCF, FallbackSolver.KDIIS]

    def test_pyscf_scf_ping_pong_detection(self) -> None:
        """
        Tests PySCF SCF log showing alternating signs.
        """
        pyscf_log = """
        ******** PySCF SCF ********
        cycle = 1  E = -128.50000000  delta_E = -0.80000000
        cycle = 2  E = -128.82000000  delta_E = -0.32000000
        cycle = 3  E = -128.82650000  delta_E =  0.00650000
        cycle = 4  E = -128.82000000  delta_E = -0.00650000
        cycle = 5  E = -128.82650000  delta_E =  0.00650000
        cycle = 6  E = -128.82000000  delta_E = -0.00650000
        cycle = 7  E = -128.82650000  delta_E =  0.00650000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(pyscf_log, dialect=EngineDialect.PYSCF)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.scf_ping_pong is not None
        assert report.scf_ping_pong.detected is True

    def test_monotonic_scf_does_not_trigger_ping_pong(self) -> None:
        """Validates that normal converging SCF does not trigger ping pong."""
        converging_log = """
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3500000000  DeltaE=   -0.04000000
        Iter   4 : Energy=   -76.3550000000  DeltaE=   -0.00500000
        Iter   5 : Energy=   -76.3556000000  DeltaE=   -0.00060000
        Iter   6 : Energy=   -76.3556800000  DeltaE=   -0.00008000
        Iter   7 : Energy=   -76.3556890000  DeltaE=   -0.00000900
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(converging_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.scf_ping_pong is None or not report.scf_ping_pong.detected


# =====================================================================
# 4. Linear Dependence Overlap Trap Tests
# =====================================================================

class TestLinearDependenceTrap:
    """Validates detection of near-singular overlap matrices and small eigenvalues (< 1e-6)."""

    def test_orca_linear_dependence_small_eigenvalue(self) -> None:
        """Tests ORCA output reporting eigenvalue < 1e-6."""
        orca_log = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 4.312e-08
        WARNING: There are 2 small eigenvalues (< 1e-06) in the overlap matrix
        Basis set has linear dependencies
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.ill_conditioned is True
        assert report.linear_dependence.min_eigenvalue is not None
        assert report.linear_dependence.min_eigenvalue < 1e-6
        assert "AutoAux" in report.linear_dependence.recommended_action or "SThresh" in report.linear_dependence.recommended_action

    def test_cfour_linear_dependence_warning(self) -> None:
        """Tests CFOUR output with overlap matrix eigenvalue warning."""
        cfour_log = """
        EXECUTION OF CFOUR SUITE
        WARNING: Overlap matrix has eigenvalues smaller than 1.0D-06: 3.14D-08
        Linear dependencies detected in atomic orbital basis
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(cfour_log, dialect=EngineDialect.CFOUR)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.min_eigenvalue is not None
        assert report.linear_dependence.min_eigenvalue < 1e-6

    def test_pyscf_linear_dependence_warning(self) -> None:
        """Tests PySCF output reporting small overlap matrix eigenvalue."""
        pyscf_log = """
        ******** PySCF ********
        Small eigenvalue of overlap matrix: 5.21e-07 < 1e-06
        Basis set linear dependence detected. Recommend removing diffuse functions.
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(pyscf_log, dialect=EngineDialect.PYSCF)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.linear_dependence is not None
        assert report.linear_dependence.detected is True
        assert report.linear_dependence.ill_conditioned is True

    def test_safe_eigenvalue_does_not_trigger_linear_dependence(self) -> None:
        """Tests that eigenvalue >= 1e-6 is safe and does not trigger trap."""
        clean_log = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 1.452e-04
        Overlap matrix condition is well-behaved.
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(clean_log, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.CLEAN
        assert report.linear_dependence is None or not report.linear_dependence.detected


# =====================================================================
# 5. Chunked Stream Processing & Real File I/O Tests
# =====================================================================

class TestChunkedStreamProcessing:
    """Validates 1MB chunked stream processing for text, binary streams, and files."""

    def test_large_stream_chunking_without_whole_file_memory_load(self) -> None:
        """
        Generates a 2.5 MB simulated stream with an embedded ping-pong oscillation
        and verifies it processes accurately in 1MB chunks.
        """
        pad_chunk = "INFO: Step progress calculation normal\n" * 20000  # ~780 KB
        orca_ping_pong = """
        ================================================================================
                                          * O   R   C   A *
        ================================================================================
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        large_content = (pad_chunk * 3) + orca_ping_pong + (pad_chunk * 1)
        stream = io.StringIO(large_content)

        engine = RegexTrapEngine(chunk_size_bytes=1024 * 1024)  # 1MB
        report = engine.scan_stream(stream, dialect=EngineDialect.AUTODETECT)

        assert report.detected_dialect == EngineDialect.ORCA
        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.total_bytes_processed > 2 * 1024 * 1024
        assert report.total_chunks_processed >= 3

    def test_binary_stream_processing_with_invalid_utf8_recovery(self) -> None:
        """
        Verifies that binary streams with sporadic corrupted bytes
        are decoded safely with replacement and scanned accurately.
        """
        binary_data = (
            b"\x80\x81\xFF"
            b"* O   R   C   A *\n"
            b"Smallest eigenvalue of the overlap matrix : 1.234e-09\n"
            b"\xFE\xFD"
        )
        stream = io.BytesIO(binary_data)
        engine = RegexTrapEngine()
        report = engine.scan_stream(stream, dialect=EngineDialect.AUTODETECT)

        assert report.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED
        assert report.detected_dialect == EngineDialect.ORCA

    def test_scan_real_file_on_disk(self) -> None:
        """Tests scanning an actual physical file on disk."""
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write("""
            ******** PySCF-2.5.0 ********
            cycle = 1  E = -76.00000000  delta_E = -0.50000000
            cycle = 2  E = -76.12000000  delta_E = -0.12000000
            cycle = 3  E = -76.12300000  delta_E =  0.00300000
            cycle = 4  E = -76.12000000  delta_E = -0.00300000
            cycle = 5  E = -76.12300000  delta_E =  0.00300000
            cycle = 6  E = -76.12000000  delta_E = -0.00300000
            cycle = 7  E = -76.12300000  delta_E =  0.00300000
            """)
            temp_path = Path(f.name)

        try:
            engine = RegexTrapEngine()
            report = engine.scan_file(temp_path)
            assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
            assert report.detected_dialect == EngineDialect.PYSCF
        finally:
            if temp_path.exists():
                os.unlink(temp_path)

    def test_incremental_live_stream_feeding(self) -> None:
        """
        Simulates line-by-line streaming from a running subprocess stdout,
        verifying early detection event emission.
        """
        engine = RegexTrapEngine(dialect=EngineDialect.ORCA)
        lines = [
            "* O   R   C   A *",
            "Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000",
            "Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000",
            "Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
            "Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000",
            "Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
            "Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000",
            "Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000",
        ]

        events: List[TrapDetectionEvent] = []
        for line in lines:
            event = engine.feed_line(line)
            if event is not None:
                events.append(event)

        final_report = engine.finalize()
        assert final_report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert any(e.flag == TrapFlag.SCF_PING_PONG_DETECTED for e in events)

    def test_report_serialization_and_to_dict(self) -> None:
        """Verifies full serialization to dict and JSON format for reporting."""
        orca_log = """
        * O   R   C   A *
        Iter   1 : Energy= -76.00000000 DeltaE= -0.50000000
        Iter   2 : Energy= NaN DeltaE= 0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(orca_log, dialect=EngineDialect.ORCA)

        report_dict = report.to_dict()
        assert report_dict["primary_flag"] == "NUMERICAL_COLLAPSE"
        assert report_dict["detected_dialect"] == "ORCA"
        assert isinstance(report_dict["events"], list)

        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["primary_flag"] == "NUMERICAL_COLLAPSE"


# =====================================================================
# 6. Multi-Trap Precedence, Functional API & Edge Cases Tests
# =====================================================================

class TestMultiTrapPrecedenceAndFunctionalAPI:
    """Validates multi-trap conflict resolution, convenience APIs, and edge cases."""

    def test_multi_trap_priority_numerical_collapse_over_scf_ping_pong(self) -> None:
        """
        Tests log containing both SCF ping-pong oscillation AND subsequent NaN,
        verifying NUMERICAL_COLLAPSE takes top priority.
        """
        log_content = """
        * O   R   C   A *
        Smallest eigenvalue of the overlap matrix : 2.123e-08
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   8 : Energy=   NaN             DeltaE=   0.00000000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_content, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.NUMERICAL_COLLAPSE
        assert report.numerical_collapse is not None and report.numerical_collapse.detected
        assert report.scf_ping_pong is not None and report.scf_ping_pong.detected
        assert report.linear_dependence is not None and report.linear_dependence.detected
        assert len(report.events) >= 3

    def test_multi_trap_priority_ping_pong_over_linear_dependence(self) -> None:
        """
        Tests log with linear dependence warning and continuing into ping pong without NaN,
        verifying SCF_PING_PONG_DETECTED takes priority over linear dependence.
        """
        log_content = """
        * O   R   C   A *
        WARNING: Basis set has linear dependencies
        Smallest eigenvalue of the overlap matrix : 5.123e-09
        Iter   1 : Energy=   -76.1200000000  DeltaE=   -0.54000000
        Iter   2 : Energy=   -76.3100000000  DeltaE=   -0.19000000
        Iter   3 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   4 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   5 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        Iter   6 : Energy=   -76.3100000000  DeltaE=   -0.00420000
        Iter   7 : Energy=   -76.3142000000  DeltaE=   +0.00420000
        """
        engine = RegexTrapEngine()
        report = engine.scan_text(log_content, dialect=EngineDialect.ORCA)

        assert report.primary_flag == TrapFlag.SCF_PING_PONG_DETECTED
        assert report.linear_dependence is not None and report.linear_dependence.detected

    def test_convenience_scan_log_for_traps(self) -> None:
        """Verifies top-level helper function across string, bytes, and file."""
        from core_engine.cochem_regex_traps import scan_log_for_traps

        text_orca = "* O   R   C   A *\nSmallest eigenvalue of the overlap matrix : 1.0e-09\n"
        rep1 = scan_log_for_traps(text_orca)
        assert rep1.primary_flag == TrapFlag.LINEAR_DEPENDENCE_DETECTED

        bytes_pyscf = b"******** PySCF ********\ncycle = 1  E = NaN  delta_E = 0.0\n"
        rep2 = scan_log_for_traps(bytes_pyscf)
        assert rep2.primary_flag == TrapFlag.NUMERICAL_COLLAPSE

    def test_empty_stream_and_clean_run(self) -> None:
        """Tests that empty stream returns CLEAN without errors."""
        engine = RegexTrapEngine()
        report = engine.scan_text("")
        assert report.primary_flag == TrapFlag.CLEAN
        assert report.total_bytes_processed == 0
        assert len(report.events) == 0


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.