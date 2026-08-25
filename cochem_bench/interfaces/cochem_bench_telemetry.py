#!/usr/bin/env python3
r"""Stage 6.0 / 7.0: Context-Compression & Streaming Telemetry Engine.

Authoritative Implementation: cochem_bench.interfaces.cochem_bench_telemetry
System Domain: CoChem-BENCH Interface Layer & Telemetry Perimeter

Key Capabilities:
1. ContextCompressor:
   - Intercepts massive raw metric arrays (e.g. DIIS error vectors, SCF energy histories)
     and mathematically downsamples them into compact statistical summaries
     (Min, Max, Mean, Variance, Last Value) before transmission.
   - Largest-Triangle-Three-Buckets (LTTB) decimation algorithm for plotting continuous
     convergence curves while capping payloads to < 1,000 points.
2. NDJSONStreamer:
   - Broadcasts compressed telemetry via lightweight NDJSON (Newline Delimited JSON)
     to Jupyter frontend / Voila dashboard using asynchronous polling.
   - Zero-Interruption / Detachment Invariant: If frontend disconnects, calculation continues
     uninterrupted in the air-gapped workspace.
3. NanInfInterceptor:
   - Exact RegEx hooks on live standard output stream catching NaN, Inf, and linear dependence.
   - Specifically traps literal "Lowest eigenvalue of the overlap matrix" and extracts float value;
     if < 1e-6, alerts backend and creates a 0-byte ABORT.signal file in $SCRATCH workspace.
4. Air-Gap & Mendeleev Dynamic Integration:
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR without hardcoded paths.
   - Dynamic atomic mass retrieval via the Mendeleev library.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt2_telemetry.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 2 File Inventory & Deliverable Capabilities Manifest (Part 2 Interface Layer & Core System Bridges).txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import collections
import datetime
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ==============================================================================
# Dynamic Environment & Path Resolution Helpers
# ==============================================================================

def get_cochem_artifacts_dir() -> Path:
    """Dynamically resolves the CoChem artifacts root directory from environment.

    Priority:
    1. os.environ['COCHEM_ARTIFACTS_DIR']
    2. Path.home() / 'cochem_artifacts'
    """
    env_path = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if env_path and env_path.strip():
        return Path(env_path).resolve()
    return (Path.home() / "cochem_artifacts").resolve()


def get_scratch_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic $SCRATCH workspace directory ($ARTIFACTS/BENCH_Workspace/Scratch)."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    scratch_path = base / "BENCH_Workspace" / "Scratch"
    scratch_path.mkdir(parents=True, exist_ok=True)
    return scratch_path


def get_logs_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic Logs directory ($ARTIFACTS/Logs)."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    logs_path = base / "Logs"
    logs_path.mkdir(parents=True, exist_ok=True)
    return logs_path


def get_element_mass_mendeleev(symbol: str) -> float:
    """Dynamically retrieves the atomic mass of an element via the Mendeleev library."""
    elem_obj = element(symbol)
    mass_val = elem_obj.atomic_weight or elem_obj.mass
    if mass_val is None:
        raise ValueError(f"Atomic mass for element {symbol} could not be retrieved.")
    return float(mass_val)


# ==============================================================================
# Pydantic Models for Telemetry and Summaries
# ==============================================================================

class StatisticalSummary(BaseModel):
    """Pydantic model representing a mathematically downsampled array summary."""
    model_config = ConfigDict(frozen=True)

    Array_Min: float = Field(description="Minimum value in the array")
    Array_Max: float = Field(description="Maximum value in the array")
    Array_Mean: float = Field(description="Arithmetic mean of array elements")
    Array_Variance: float = Field(description="Variance of array elements")
    Last_Value: float = Field(description="Final trailing value in the sequence")
    count: int = Field(description="Total number of elements compressed")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the statistical summary",
    )


class TelemetryEvent(BaseModel):
    """Structured telemetry event model for NDJSON serialization."""
    model_config = ConfigDict(frozen=True)

    event_type: str = Field(description="Event classification (e.g. SCF_ITERATION, STAGE_PROGRESS)")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    node_id: Optional[str] = Field(default=None, description="Identifier of the active compute node")
    data: Dict[str, Any] = Field(default_factory=dict, description="Payload data or compressed metrics")
    status: Optional[str] = Field(default="OK", description="Execution status")


class InterceptionAlert(BaseModel):
    """Structured interception report for NaN, Inf, or Linear Dependence traps."""
    model_config = ConfigDict(frozen=True)

    alert_type: str = Field(description="Classification: LINEAR_DEPENDENCE, NAN_DETECTED, or INF_DETECTED")
    raw_line: str = Field(description="The matching stdout line intercepted")
    extracted_value: Optional[float] = Field(default=None, description="Extracted numerical metric (e.g. eigenvalue)")
    abort_triggered: bool = Field(description="True if 0-byte ABORT.signal was generated")
    abort_file_path: Optional[str] = Field(default=None, description="Path to ABORT.signal on disk")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of interception",
    )


# ==============================================================================
# LTTB Decimation Algorithm
# ==============================================================================

def decimate_lttb(
    x: Union[Sequence[float], np.ndarray],
    y: Union[Sequence[float], np.ndarray],
    max_points: int = 1000,
) -> Tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets (LTTB) visual decimation algorithm.

    Downsamples time-series / convergence curves to max_points while strictly
    preserving visual extrema, local peaks, and overall curve geometry.

    Args:
        x: 1D array of monotonic X coordinates (e.g. cycle indices, timestamps).
        y: 1D array of Y values (e.g. energy fluctuations, gradient norms).
        max_points: Maximum number of points in output (default: 1000).

    Returns:
        Tuple of (decimated_x, decimated_y) as numpy arrays.
    """
    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)

    if x_arr.ndim != 1 or y_arr.ndim != 1 or len(x_arr) != len(y_arr):
        raise ValueError("x and y must be 1D arrays of identical length.")

    n_points = len(x_arr)
    if n_points <= max_points or max_points < 3:
        return x_arr.copy(), y_arr.copy()

    # Output arrays
    out_x = np.empty(max_points, dtype=np.float64)
    out_y = np.empty(max_points, dtype=np.float64)

    # Always include the first point
    out_x[0] = x_arr[0]
    out_y[0] = y_arr[0]

    # Number of intermediate buckets
    bucket_size = (n_points - 2) / (max_points - 2)

    a_idx = 0  # Point A index in previous bucket

    for i in range(max_points - 2):
        # Current bucket B range [b_start, b_end)
        b_start = int(math.floor((i + 0) * bucket_size)) + 1
        b_end = int(math.floor((i + 1) * bucket_size)) + 1
        b_end = min(b_end, n_points - 1)

        # Next bucket C range [c_start, c_end) to compute average point C
        c_start = int(math.floor((i + 1) * bucket_size)) + 1
        c_end = int(math.floor((i + 2) * bucket_size)) + 1
        c_end = min(c_end, n_points)

        # Average coordinates of bucket C
        if c_end > c_start:
            avg_c_x = float(np.mean(x_arr[c_start:c_end]))
            avg_c_y = float(np.mean(y_arr[c_start:c_end]))
        else:
            avg_c_x = float(x_arr[-1])
            avg_c_y = float(y_arr[-1])

        # Point A coordinates
        p_a_x = x_arr[a_idx]
        p_a_y = y_arr[a_idx]

        # Find point in bucket B that maximizes triangle area (A, B, C)
        # Area = 0.5 * |(Ax - Cx)(By - Ay) - (Ax - Bx)(Cy - Ay)|
        max_area = -1.0
        max_idx = b_start

        for idx in range(b_start, b_end):
            p_b_x = x_arr[idx]
            p_b_y = y_arr[idx]

            area = abs(
                (p_a_x - avg_c_x) * (p_b_y - p_a_y)
                - (p_a_x - p_b_x) * (avg_c_y - p_a_y)
            )
            if area > max_area:
                max_area = area
                max_idx = idx

        out_x[i + 1] = x_arr[max_idx]
        out_y[i + 1] = y_arr[max_idx]
        a_idx = max_idx

    # Always include the last point
    out_x[-1] = x_arr[-1]
    out_y[-1] = y_arr[-1]

    return out_x, out_y


# ==============================================================================
# 1. ContextCompressor
# ==============================================================================

class ContextCompressor:
    """Mathematical downsampler reducing massive numeric arrays into statistical summaries.

    Protects Jupyter frontend DOM and AI context windows from overflow.
    """

    def __init__(self, array_threshold: int = 50, lttb_max_points: int = 1000) -> None:
        self.array_threshold = int(array_threshold)
        self.lttb_max_points = int(lttb_max_points)

    def compress_array(self, values: Union[Sequence[float], np.ndarray]) -> StatisticalSummary:
        """Compresses a 1D or multi-dimensional numeric sequence into a StatisticalSummary.

        Args:
            values: Sequence of floats or numpy array.

        Returns:
            StatisticalSummary instance with Min, Max, Mean, Variance, Last Value, and count.

        Raises:
            ValueError: If the sequence is empty.
        """
        arr = np.asarray(values, dtype=np.float64).ravel()
        if arr.size == 0:
            raise ValueError("Cannot compress empty array.")

        # Compute exact statistics
        arr_min = float(np.min(arr))
        arr_max = float(np.max(arr))
        arr_mean = float(np.mean(arr))
        arr_var = float(np.var(arr))
        last_val = float(arr[-1])

        return StatisticalSummary(
            Array_Min=arr_min,
            Array_Max=arr_max,
            Array_Mean=arr_mean,
            Array_Variance=arr_var,
            Last_Value=last_val,
            count=int(arr.size),
        )

    def compress_to_dict(self, values: Union[Sequence[float], np.ndarray]) -> Dict[str, float]:
        """Compresses a sequence into the exact 5-key dictionary matching SRS Task 7.2.1.

        Keys: Array_Min, Array_Max, Array_Mean, Array_Variance, Last_Value.
        """
        summary = self.compress_array(values)
        return {
            "Array_Min": summary.Array_Min,
            "Array_Max": summary.Array_Max,
            "Array_Mean": summary.Array_Mean,
            "Array_Variance": summary.Array_Variance,
            "Last_Value": summary.Last_Value,
        }

    def decimate_curve(
        self,
        y_values: Union[Sequence[float], np.ndarray],
        x_values: Optional[Union[Sequence[float], np.ndarray]] = None,
        max_points: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Applies LTTB visual decimation on a 1D curve."""
        y_arr = np.asarray(y_values, dtype=np.float64)
        if x_values is None:
            x_arr = np.arange(len(y_arr), dtype=np.float64)
        else:
            x_arr = np.asarray(x_values, dtype=np.float64)

        limit = max_points if max_points is not None else self.lttb_max_points
        return decimate_lttb(x_arr, y_arr, max_points=limit)

    def compress_payload(
        self,
        payload: Dict[str, Any],
        array_threshold: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Recursively intercepts large arrays in a dictionary payload and compresses them.

        Args:
            payload: Input dictionary (e.g. telemetry frame, job status).
            array_threshold: Minimum element count to trigger compression (default: self.array_threshold).

        Returns:
            New dictionary with large arrays replaced by statistical summary dictionaries.
        """
        threshold = array_threshold if array_threshold is not None else self.array_threshold
        compressed: Dict[str, Any] = {}

        for k, v in payload.items():
            if isinstance(v, (list, tuple, np.ndarray)):
                try:
                    arr = np.asarray(v, dtype=np.float64)
                    if arr.size > threshold:
                        compressed[k] = self.compress_to_dict(arr)
                    else:
                        compressed[k] = v
                except (ValueError, TypeError):
                    # Non-numeric list/array remains intact
                    compressed[k] = v
            elif isinstance(v, dict):
                compressed[k] = self.compress_payload(v, array_threshold=threshold)
            else:
                compressed[k] = v

        return compressed


# ==============================================================================
# 2. NDJSONStreamer
# ==============================================================================

class NDJSONStreamer:
    """Asynchronous polling and lightweight NDJSON broadcasting streamer.

    Broadcasts real-time telemetry updates to Jupyter/Voila dashboards.
    Implements the Zero-Interruption / Detachment invariant: calculations continue
    uninterrupted in the air-gapped workspace even if the frontend disconnects.
    """

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        buffer_capacity: int = 1000,
        compressor: Optional[ContextCompressor] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.buffer_capacity = int(buffer_capacity)
        self.buffer: collections.deque[Dict[str, Any]] = collections.deque(maxlen=self.buffer_capacity)
        self.compressor = compressor or ContextCompressor()
        self._is_detached: bool = False
        self._total_events_emitted: int = 0

    @property
    def is_detached(self) -> bool:
        """Returns True if the frontend has safely detached from the streamer."""
        return self._is_detached

    def detach(self) -> None:
        """Safely detaches the streamer from the frontend without interrupting compute."""
        self._is_detached = True
        logger.info("NDJSONStreamer: Frontend detached. Telemetry spools to local air-gap buffer.")

    def attach(self) -> None:
        """Re-attaches an active frontend consumer."""
        self._is_detached = False
        logger.info("NDJSONStreamer: Frontend re-attached.")

    def resolve_log_path(self, filename: str = "telemetry.ndjson") -> Path:
        """Resolves destination path for telemetry.ndjson in the Logs workspace."""
        logs_dir = get_logs_workspace_dir(self.artifacts_dir)
        return logs_dir / filename

    def emit_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        node_id: Optional[str] = None,
        write_to_disk: bool = False,
        log_file: Optional[Union[str, Path]] = None,
        auto_compress: bool = True,
    ) -> str:
        """Constructs, buffers, and optionally persists a single NDJSON event.

        Args:
            event_type: Classification string (e.g. SCF_ITERATION, STAGE_PROGRESS).
            data: Payload dictionary.
            node_id: Identifier of the compute node.
            write_to_disk: If True, appends the line to the NDJSON log file.
            log_file: Optional explicit file path override.
            auto_compress: If True, compresses arrays larger than threshold in data.

        Returns:
            The single-line NDJSON formatted string (with trailing newline).
        """
        payload_data = self.compressor.compress_payload(data) if auto_compress else data

        event = TelemetryEvent(
            event_type=str(event_type),
            node_id=str(node_id) if node_id is not None else None,
            data=payload_data,
        )

        event_dict = event.model_dump()
        event_dict["_event_index"] = self._total_events_emitted
        self._total_events_emitted += 1

        # Store in in-memory ring buffer for async polling
        self.buffer.append(event_dict)

        # Format as strict NDJSON single line
        ndjson_line = json.dumps(event_dict, ensure_ascii=False) + "\n"

        if write_to_disk:
            target_path = Path(log_file).resolve() if log_file else self.resolve_log_path()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(ndjson_line)

        return ndjson_line

    def poll_events(
        self,
        since_index: int = 0,
        max_items: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Asynchronously polls buffered events since a given event index.

        Args:
            since_index: Starting event sequence index.
            max_items: Optional ceiling on number of returned events.

        Returns:
            List of event dictionaries matching criteria.
        """
        results: List[Dict[str, Any]] = []
        for item in self.buffer:
            idx = item.get("_event_index", 0)
            if idx >= since_index:
                results.append(dict(item))
                if max_items and len(results) >= max_items:
                    break
        return results

    def read_stream_file(
        self,
        log_file: Optional[Union[str, Path]] = None,
        from_byte_offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Incrementally reads newly appended NDJSON lines from disk.

        Args:
            log_file: Path to the NDJSON file (defaults to telemetry.ndjson in Logs).
            from_byte_offset: Starting byte position for tail reading.

        Returns:
            Tuple of (list_of_parsed_event_dicts, next_byte_offset).
        """
        target_path = Path(log_file).resolve() if log_file else self.resolve_log_path()
        if not target_path.exists():
            return [], from_byte_offset

        events: List[Dict[str, Any]] = []
        with open(target_path, "r", encoding="utf-8") as f:
            f.seek(from_byte_offset)
            while True:
                line = f.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped:
                    try:
                        events.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        pass
            next_offset = f.tell()

        return events, next_offset


# ==============================================================================
# 3. NanInfInterceptor
# ==============================================================================

class NanInfInterceptor:
    """Live standard output stream scanner with exact RegEx hooks.

    Traps:
    1. Linear dependence overlap: "Lowest eigenvalue of the overlap matrix" < 1e-6.
    2. NaN values in energy/residual outputs.
    3. Inf / Infinity values in numerical matrices.

    Upon detection, immediately severs the worker process by creating a 0-byte
    ABORT.signal file in the dynamic $SCRATCH workspace.
    """

    # Exact RegEx for lowest eigenvalue of overlap matrix
    # Captures: "Lowest eigenvalue of the overlap matrix : 1.42e-04" or "Lowest eigenvalue of the overlap matrix = 3.85e-07"
    OVERLAP_EIGENVAL_REGEX = re.compile(
        r"Lowest\s+eigenvalue\s+of\s+the\s+overlap\s+matrix\s*[:=]?\s*([+-]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?)",
        re.IGNORECASE,
    )

    # Exact RegEx for NaN occurrences in numerical stdout tokens
    NAN_REGEX = re.compile(r"\b(?:nan|nan\s+eh)\b", re.IGNORECASE)

    # Exact RegEx for Inf occurrences in numerical stdout tokens
    INF_REGEX = re.compile(r"\b(?:[+-]?inf|[+-]?infinity)\b", re.IGNORECASE)

    # Linear dependence eigenvalue threshold
    LINEAR_DEPENDENCE_THRESHOLD: float = 1e-6

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        eigenvalue_threshold: float = LINEAR_DEPENDENCE_THRESHOLD,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.eigenvalue_threshold = float(eigenvalue_threshold)

    def resolve_scratch_dir(self) -> Path:
        """Resolves the dynamic $SCRATCH directory ($ARTIFACTS/BENCH_Workspace/Scratch)."""
        return get_scratch_workspace_dir(self.artifacts_dir)

    def get_abort_signal_path(self) -> Path:
        """Returns the dynamic path to $SCRATCH/ABORT.signal."""
        return self.resolve_scratch_dir() / "ABORT.signal"

    def create_abort_signal(self, reason: str = "LINEAR_DEPENDENCE_OVERLAP") -> Path:
        """Creates an exact 0-byte ABORT.signal file in the $SCRATCH directory."""
        abort_path = self.get_abort_signal_path()
        abort_path.parent.mkdir(parents=True, exist_ok=True)
        # Create strict 0-byte file
        abort_path.touch()
        logger.warning("NanInfInterceptor: Created 0-byte ABORT.signal at %s (Reason: %s)", abort_path, reason)
        return abort_path

    def check_abort_signal(self) -> bool:
        """Returns True if the ABORT.signal file exists in $SCRATCH."""
        return self.get_abort_signal_path().exists()

    def clear_abort_signal(self) -> bool:
        """Safely removes the ABORT.signal file if present."""
        abort_path = self.get_abort_signal_path()
        if abort_path.exists():
            try:
                abort_path.unlink()
                return True
            except OSError:
                return False
        return False

    def scan_line(self, line: str) -> Optional[InterceptionAlert]:
        """Scans a single standard output line against exact regex hooks.

        Args:
            line: Single stdout text string.

        Returns:
            InterceptionAlert if a fatal numerical trap is triggered; None otherwise.
        """
        if not line or not line.strip():
            return None

        # 1. Check Linear Dependence Overlap Eigenvalue
        match_eig = self.OVERLAP_EIGENVAL_REGEX.search(line)
        if match_eig:
            try:
                val_str = match_eig.group(1)
                val = float(val_str)
                if val < self.eigenvalue_threshold:
                    abort_path = self.create_abort_signal(reason=f"OVERLAP_EIGENVALUE_{val:.2e}_BELOW_THRESHOLD")
                    return InterceptionAlert(
                        alert_type="LINEAR_DEPENDENCE",
                        raw_line=line.strip(),
                        extracted_value=val,
                        abort_triggered=True,
                        abort_file_path=str(abort_path),
                    )
            except (ValueError, IndexError):
                pass

        # 2. Check for NaN in stream
        if self.NAN_REGEX.search(line):
            abort_path = self.create_abort_signal(reason="NAN_DETECTED_IN_STREAM")
            return InterceptionAlert(
                alert_type="NAN_DETECTED",
                raw_line=line.strip(),
                abort_triggered=True,
                abort_file_path=str(abort_path),
            )

        # 3. Check for Inf in stream
        if self.INF_REGEX.search(line):
            abort_path = self.create_abort_signal(reason="INF_DETECTED_IN_STREAM")
            return InterceptionAlert(
                alert_type="INF_DETECTED",
                raw_line=line.strip(),
                abort_triggered=True,
                abort_file_path=str(abort_path),
            )

        return None

    def scan_chunk(self, text: str) -> List[InterceptionAlert]:
        """Scans a multi-line output text chunk and returns all triggered alerts."""
        alerts: List[InterceptionAlert] = []
        for line in text.splitlines():
            alert = self.scan_line(line)
            if alert is not None:
                alerts.append(alert)
        return alerts
