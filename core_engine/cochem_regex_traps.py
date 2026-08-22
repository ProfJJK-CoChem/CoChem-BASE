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

import codecs
import io
import json
import logging
import math
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
# 1.#IND, -1.#IND, 1.#INF, -1.#INF, 1.#QNAN, 1.#SNAN, and MSVC/Fortran variants with trailing digits (1.#IND00, 1.#INF00, 1.#QNAN0)
NUMERICAL_COLLAPSE_REGEX: re.Pattern = re.compile(
    r"(?<![a-zA-Z0-9_])(?P<token>[-+]?nan[qs]?|[-+]?infinity|[-+]?inf|[-+]?1\.#(?:ind|inf|qnan|snan)\d*)(?![a-zA-Z0-9_])",
    re.IGNORECASE,
)

# Robust floating point pattern matching standard floats, scientific notations (with/without decimal point, e/E/d/D)
_FLOAT_PAT = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][-+]?\d+)?"


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
            rf"^\s*Iter\s+(?P<cycle>\d+)\s*:\s+Energy=\s*(?P<energy>{_FLOAT_PAT})\s+DeltaE=\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*(?P<cycle>\d+)\s+{_FLOAT_PAT}\s+{_FLOAT_PAT}\s+(?P<delta>{_FLOAT_PAT})\s+(?P<energy>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*SCF ITERATION\s+(?P<cycle>\d+).*?Total Energy:\s*(?P<energy>{_FLOAT_PAT}).*?(?:Delta-E|Delta E|Change):\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            rf"Smallest eigenvalue of (?:the )?(?:overlap|metric) matrix\s*:\s*(?P<val>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"WARNING:\s*There (?:are|is)\s+\d+\s+small eigenvalue(?:s)?\s*\(<\s*(?P<thresh>{_FLOAT_PAT})\)\s*in the overlap matrix",
            re.IGNORECASE,
        ),
        re.compile(
            r"WARNING:\s*Basis set has linear dependencies",
            re.IGNORECASE,
        ),
        re.compile(
            r"Linear dependenc(?:y|ies) in the basis set",
            re.IGNORECASE,
        ),
        re.compile(
            rf"Smallest eigenvalue of metric matrix\s*:\s*(?P<val>{_FLOAT_PAT})",
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
            rf"^\s*Iter\s+(?P<cycle>\d+)\s+(?P<energy>{_FLOAT_PAT})\s+(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*SCF ITERATION\s+#\s*(?P<cycle>\d+)\s+TOTAL ENERGY\s*=\s*(?P<energy>{_FLOAT_PAT})\s+CHANGE\s*=\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*(?P<cycle>\d+)\s+{_FLOAT_PAT}\s+(?P<energy>{_FLOAT_PAT})\s+(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            rf"WARNING:\s*Overlap matrix has eigenvalues smaller than\s*(?P<thresh>{_FLOAT_PAT})\s*:\s*(?P<val>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            r"Linear dependenc(?:y|ies) detected in(?: atomic orbital)? basis",
            re.IGNORECASE,
        ),
        re.compile(
            rf"Smallest eigenvalue of overlap matrix is\s+(?P<val>{_FLOAT_PAT})",
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
            rf"^\s*cycle\s*=\s*(?P<cycle>\d+)\s+E\s*=\s*(?P<energy>{_FLOAT_PAT})\s+delta_E\s*=\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*SCF\s+cycle\s+(?P<cycle>\d+)\s+E\(SCF\)\s*=\s*(?P<energy>{_FLOAT_PAT})\s+delta\s*=\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"^\s*cycle\s+(?P<cycle>\d+):\s+E\s*=\s*(?P<energy>{_FLOAT_PAT})\s+dE\s*=\s*(?P<delta>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
    ]
    linear_dep_patterns = [
        re.compile(
            rf"Small(?:est)? eigenvalue of overlap matrix\s*:\s*(?P<val>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"Small eigenvalue of overlap matrix:\s*(?P<val>{_FLOAT_PAT})\s*<\s*(?P<thresh>{_FLOAT_PAT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"Linear dependency in basis set\s*\(eigenvalue\s*<\s*(?P<thresh>{_FLOAT_PAT})\)",
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

        # Guard against NaN/Inf values inside delta series
        if not all(math.isfinite(x) for x in win):
            continue

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
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

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
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

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
        maps_to_try = (
            [self._regex_map]
            if self.active_dialect != EngineDialect.AUTODETECT
            else list(_DIALECT_REGISTRY.values())
        )

        for current_map in maps_to_try:
            matched_dep = False
            for pat in current_map.linear_dependence_patterns:
                m = pat.search(line_clean)
                if m:
                    if self.active_dialect == EngineDialect.AUTODETECT:
                        self.active_dialect = current_map.dialect
                        self._regex_map = current_map

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
                        matched_dep = True
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
                    break
            if matched_dep:
                break

        # 4. Check SCF Iteration Parsing on this line
        for current_map in maps_to_try:
            matched_scf = False
            for pat in current_map.scf_cycle_patterns:
                m = pat.search(line_clean)
                if m:
                    try:
                        cycle = int(m.group("cycle"))
                        energy = _safe_float(m.group("energy"))
                        delta = _safe_float(m.group("delta"))

                        if self.active_dialect == EngineDialect.AUTODETECT:
                            self.active_dialect = current_map.dialect
                            self._regex_map = current_map

                        record = SCFCycleRecord(cycle=cycle, energy=energy, delta_e=delta, raw_line=line_clean)
                        self._scf_records.append(record)
                        matched_scf = True

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
            if matched_scf:
                break

        return None

    def feed_chunk(self, chunk: Union[str, bytes]) -> List[TrapDetectionEvent]:
        """
        Feed a raw chunk of text or binary data into the scanner.
        Handles boundary overlap buffer and line buffering across chunks.
        """
        if isinstance(chunk, bytes):
            text_chunk = self._utf8_decoder.decode(chunk, final=False)
            byte_len = len(chunk)
        else:
            text_chunk = chunk
            byte_len = len(chunk.encode("utf-8", errors="replace"))

        self._total_bytes += byte_len
        self._total_chunks += 1
        new_events: List[TrapDetectionEvent] = []

        # Update overlap buffer for next chunk
        combined_overlap = self._overlap_buffer + text_chunk
        if len(text_chunk) >= self.overlap_bytes:
            self._overlap_buffer = text_chunk[-self.overlap_bytes :]
        else:
            self._overlap_buffer = combined_overlap[-self.overlap_bytes :]

        # Line buffering and feeding complete lines
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
        trailing = self._utf8_decoder.decode(b"", final=True)
        if trailing:
            self._line_buffer += trailing

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
