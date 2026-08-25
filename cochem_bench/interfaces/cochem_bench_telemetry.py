#!/usr/bin/env python3
r"""Stage 6.0 / 7.0 & Task 3: Telemetry, State Reflection & Crash-Proofing Engine.

Authoritative Implementation: cochem_bench.interfaces.cochem_bench_telemetry
System Domain: CoChem-BENCH Interface Layer & Telemetry Perimeter

Key Capabilities:
1. Stateless Rehydration (The "Zombie UI" Protocol):
   - Execution logic handoff to SubprocessBroker using cross-platform process group
     detachment orchestrated via psutil.
   - Dynamic path inspection of $COCHEM_ARTIFACTS_DIR/BENCH_Workspace/Logs/bench_run_state.jsonl.
   - Rehydrates active stage progress, SCF cycles, energy history, and variance from active NDJSON streams.
2. Context-Compression Stream Integration:
   - Intercepts massive raw metric arrays (e.g. DIIS error vectors, SCF energy histories)
     and mathematically downsamples them into compact statistical summaries
     (Min, Max, Mean, Variance, Last Value) before transmission.
   - Polls lightweight NDJSON stream and renders summaries using asynchronous debouncing
     on a fixed interval (e.g. 2.0 seconds).
3. Live Asymptotic Convergence Plotting:
   - Uses plotly.graph_objects.FigureWidget (or Figure fallback) to graph energy residuals (|ΔE|).
   - Utilizes Largest-Triangle-Three-Buckets (LTTB) visual decimation algorithm
     if dataset exceeds 1,000 points, preserving visual extrema and curve geometry.
4. Fatal Error Interception:
   - ZeroMQ heartbeat subscriber monitoring and drop detection.
   - Intercepts cross-platform OS Segfaults (139, -11, 0xC0000005, 3221225477, -1073741819)
     and OOM (137, -9).
   - Generates high-visibility red HTML readout and structured JSON-LD recovery instructions
     from the provenance block ([M], [D], [E]) alongside exact 256-byte stderr hex-dump.
   - Traps numerical instability ("Lowest eigenvalue of the overlap matrix" < 1e-6, NaN, Inf)
     and creates a 0-byte ABORT.signal in $SCRATCH.
5. Air-Gap & Mendeleev Dynamic Integration:
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR without hardcoded paths.
   - Dynamic atomic mass retrieval via the Mendeleev library.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task3_telemetry.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\.improved\Perfected_Task 3 Interactive UI (Jupyter) & Voila GUI Specifications.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import collections
import datetime
import html
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
import plotly.graph_objects as go
import psutil
import zmq
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ==============================================================================
# Constant Definitions & Fatal Exit Codes
# ==============================================================================

# Segmentation fault return codes across POSIX and Windows NT platforms
# POSIX: -11 (-signal.SIGSEGV), 139 (128 + 11)
# Windows NT STATUS_ACCESS_VIOLATION (0xC0000005):
#   - Hex: 0xC0000005
#   - Unsigned 32-bit: 3221225477
#   - Signed 32-bit: -1073741819
SEGFAULT_RETURN_CODES: Set[int] = {
    -11,
    139,
    3221225477,
    -1073741819,
    0xC0000005,
}

# Out Of Memory (OOM) kill codes
# POSIX: -9 (-signal.SIGKILL), 137 (128 + 9)
OOM_RETURN_CODES: Set[int] = {
    -9,
    137,
}

# Combined fatal return codes set
ALL_FATAL_RETURN_CODES: Set[int] = SEGFAULT_RETURN_CODES | OOM_RETURN_CODES


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


def get_bench_logs_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic BENCH Logs directory ($ARTIFACTS/BENCH_Workspace/Logs)."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    bench_logs_path = base / "BENCH_Workspace" / "Logs"
    bench_logs_path.mkdir(parents=True, exist_ok=True)
    return bench_logs_path


def get_bench_run_state_path(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the path to bench_run_state.jsonl in $ARTIFACTS/BENCH_Workspace/Logs."""
    return get_bench_logs_workspace_dir(artifacts_dir) / "bench_run_state.jsonl"


def get_element_mass_mendeleev(symbol: str) -> float:
    """Dynamically retrieves the atomic mass of an element via the Mendeleev library."""
    elem_obj = element(symbol)
    mass_val = elem_obj.atomic_weight or elem_obj.mass
    if mass_val is None:
        raise ValueError(f"Atomic mass for element {symbol} could not be retrieved.")
    return float(mass_val)


# ==============================================================================
# Pydantic Schemas for Telemetry, State Rehydration & Fatal Reports
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


class RehydratedRunState(BaseModel):
    """Pydantic model representing state rehydrated from bench_run_state.jsonl."""
    model_config = ConfigDict(frozen=True)

    stage: str = Field(description="Active execution stage identifier")
    scf_cycle: int = Field(default=0, description="Current SCF iteration count")
    progress_percent: float = Field(default=0.0, description="Overall pipeline completion percentage")
    current_energy: float = Field(default=0.0, description="Latest calculated energy value")
    energy_history: List[float] = Field(default_factory=list, description="Historical energy sequence")
    variance: float = Field(default=0.0, description="Variance of energy fluctuations or residuals")
    pid: Optional[int] = Field(default=None, description="Active compute process ID")
    status: str = Field(default="RUNNING", description="Pipeline status (RUNNING, COMPLETE, ERROR)")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the last recorded state frame",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary engine metadata")


class FatalErrorReport(BaseModel):
    """Structured report representing a fatal crash or intercepted error."""
    model_config = ConfigDict(frozen=True)

    is_fatal: bool = Field(default=True, description="Always True for fatal error reports")
    error_type: str = Field(description="Error classification: SEGMENTATION_FAULT, OUT_OF_MEMORY, etc.")
    exit_code: Optional[int] = Field(default=None, description="Integer process exit code")
    stderr_hex_dump: str = Field(description="Exact 256-byte hexadecimal dump of stderr")
    red_html_readout: str = Field(description="High-visibility HTML warning markup")
    json_ld_provenance: Dict[str, Any] = Field(description="Structured JSON-LD recovery instructions")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the crash report",
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

    out_x = np.empty(max_points, dtype=np.float64)
    out_y = np.empty(max_points, dtype=np.float64)

    out_x[0] = x_arr[0]
    out_y[0] = y_arr[0]

    bucket_size = (n_points - 2) / (max_points - 2)
    a_idx = 0

    for i in range(max_points - 2):
        b_start = int(math.floor((i + 0) * bucket_size)) + 1
        b_end = int(math.floor((i + 1) * bucket_size)) + 1
        b_end = min(b_end, n_points - 1)

        c_start = int(math.floor((i + 1) * bucket_size)) + 1
        c_end = int(math.floor((i + 2) * bucket_size)) + 1
        c_end = min(c_end, n_points)

        if c_end > c_start:
            avg_c_x = float(np.mean(x_arr[c_start:c_end]))
            avg_c_y = float(np.mean(y_arr[c_start:c_end]))
        else:
            avg_c_x = float(x_arr[-1])
            avg_c_y = float(y_arr[-1])

        p_a_x = x_arr[a_idx]
        p_a_y = y_arr[a_idx]

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

    out_x[-1] = x_arr[-1]
    out_y[-1] = y_arr[-1]

    return out_x, out_y


# ==============================================================================
# 1. ContextCompressor
# ==============================================================================

class ContextCompressor:
    """Mathematical downsampler reducing massive numeric arrays into statistical summaries."""

    def __init__(self, array_threshold: int = 50, lttb_max_points: int = 1000) -> None:
        self.array_threshold = int(array_threshold)
        self.lttb_max_points = int(lttb_max_points)

    def compress_array(self, values: Union[Sequence[float], np.ndarray]) -> StatisticalSummary:
        """Compresses a numeric sequence into a StatisticalSummary."""
        arr = np.asarray(values, dtype=np.float64).ravel()
        if arr.size == 0:
            raise ValueError("Cannot compress empty array.")

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
        """Compresses a sequence into the exact 5-key dictionary matching SRS Task 7.2.1."""
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
        """Recursively intercepts large arrays in a dictionary payload and compresses them."""
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
    """Asynchronous polling and lightweight NDJSON broadcasting streamer."""

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
        """Returns True if frontend is safely detached."""
        return self._is_detached

    def detach(self) -> None:
        """Detaches frontend consumer without interrupting backend compute."""
        self._is_detached = True
        logger.info("NDJSONStreamer: Frontend detached.")

    def attach(self) -> None:
        """Re-attaches frontend consumer."""
        self._is_detached = False
        logger.info("NDJSONStreamer: Frontend re-attached.")

    def resolve_log_path(self, filename: str = "telemetry.ndjson") -> Path:
        """Resolves destination path for telemetry.ndjson in Logs workspace."""
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
        """Constructs, buffers, and optionally persists a single NDJSON event."""
        payload_data = self.compressor.compress_payload(data) if auto_compress else data

        event = TelemetryEvent(
            event_type=str(event_type),
            node_id=str(node_id) if node_id is not None else None,
            data=payload_data,
        )

        event_dict = event.model_dump()
        event_dict["_event_index"] = self._total_events_emitted
        self._total_events_emitted += 1

        self.buffer.append(event_dict)
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
        """Polls buffered events since a given event sequence index."""
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
        """Incrementally reads newly appended NDJSON lines from disk."""
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
                    except json.JSONDecodeError as e:
                        logger.debug("Skipping unparseable NDJSON line: %s", e)
            next_offset = f.tell()

        return events, next_offset


# ==============================================================================
# 3. Stateless Rehydration (Zombie UI Protocol)
# ==============================================================================

class StatelessRehydrator:
    """Implements the Zombie UI Protocol for session recovery and process detachment.

    Inspects $COCHEM_ARTIFACTS_DIR/BENCH_Workspace/Logs/bench_run_state.jsonl to
    rehydrate progress bars, energy graphs, and active compute states.
    """

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None

    def resolve_state_file(self) -> Path:
        """Resolves path to bench_run_state.jsonl in BENCH_Workspace/Logs."""
        return get_bench_run_state_path(self.artifacts_dir)

    def check_active_run_state(self) -> bool:
        """Returns True if bench_run_state.jsonl exists and contains state records."""
        state_file = self.resolve_state_file()
        if not state_file.exists():
            return False
        return state_file.stat().st_size > 0

    def rehydrate_state(self) -> RehydratedRunState:
        """Parses bench_run_state.jsonl and builds a RehydratedRunState object.

        Raises:
            FileNotFoundError: If the state file does not exist.
            ValueError: If the state file contains no valid JSON records.
        """
        state_file = self.resolve_state_file()
        if not state_file.exists():
            raise FileNotFoundError(f"Active run state log not found at {state_file}")

        last_record: Optional[Dict[str, Any]] = None
        with open(state_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        last_record = json.loads(stripped)
                    except json.JSONDecodeError as e:
                        logger.debug("Skipping unparseable state line: %s", e)

        if last_record is None:
            raise ValueError(f"State file at {state_file} contains no valid JSON lines.")

        energy_hist = last_record.get("energy_history", [])
        variance = 0.0
        if energy_hist and len(energy_hist) > 1:
            variance = float(np.var(np.array(energy_hist, dtype=np.float64)))

        return RehydratedRunState(
            stage=str(last_record.get("stage", "UNKNOWN_STAGE")),
            scf_cycle=int(last_record.get("scf_cycle", 0)),
            progress_percent=float(last_record.get("progress_percent", 0.0)),
            current_energy=float(last_record.get("current_energy", 0.0)),
            energy_history=list(energy_hist),
            variance=variance,
            pid=int(last_record.get("pid")) if last_record.get("pid") is not None else None,
            status=str(last_record.get("status", "RUNNING")),
            timestamp=str(last_record.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat())),
            metadata=dict(last_record.get("metadata", {})),
        )

    def handoff_to_subprocess_broker(
        self,
        cmd: Sequence[str],
        initial_stage: str = "STAGE_0_BOOTSTRAP",
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Hands off workload to detached background process group using psutil.

        Cross-platform isolation:
        - Windows: creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        - POSIX: start_new_session=True

        Writes initial state frame to bench_run_state.jsonl.
        """
        launch_env = os.environ.copy()
        if env:
            launch_env.update(env)

        working_dir = str(cwd) if cwd else None

        kwargs: Dict[str, Any] = {
            "cwd": working_dir,
            "env": launch_env,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            kwargs["creationflags"] = creationflags
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(list(cmd), **kwargs)

        state_file = self.resolve_state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)

        initial_record = {
            "stage": initial_stage,
            "scf_cycle": 0,
            "progress_percent": 0.0,
            "current_energy": 0.0,
            "energy_history": [],
            "pid": proc.pid,
            "status": "RUNNING",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        with open(state_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(initial_record) + "\n")

        return {
            "pid": proc.pid,
            "state_file": str(state_file),
            "status": "DETACHED_RUNNING",
        }

    def is_broker_process_alive(self, pid: int) -> bool:
        """Verifies liveness of the broker process via psutil."""
        if not psutil.pid_exists(pid):
            return False
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug("Process %s is no longer accessible: %s", pid, e)
            return False


# ==============================================================================
# 4. Context-Compression Stream Integration
# ==============================================================================

class ContextCompressionStreamIntegrator:
    """Asynchronously polls lightweight NDJSON streams and renders debounced statistical summaries."""

    def __init__(
        self,
        debounce_interval: float = 2.0,
        compressor: Optional[ContextCompressor] = None,
    ) -> None:
        self.debounce_interval = float(debounce_interval)
        self.compressor = compressor or ContextCompressor()
        self._last_render_time: float = 0.0
        self._buffered_energies: List[float] = []
        self._latest_stage: str = "INITIALIZING"
        self._latest_scf_cycle: int = 0
        self._latest_progress: float = 0.0

    def process_stream_events(
        self,
        events: List[Dict[str, Any]],
        current_time: Optional[float] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Processes a batch of NDJSON events with debounced statistical compression."""
        now = time.time() if current_time is None else float(current_time)

        for ev in events:
            data = ev.get("data", {})
            if "stage" in data:
                self._latest_stage = str(data["stage"])
            if "scf_cycle" in data:
                self._latest_scf_cycle = int(data["scf_cycle"])
            if "progress_percent" in data:
                self._latest_progress = float(data["progress_percent"])
            if "energy" in data:
                try:
                    self._buffered_energies.append(float(data["energy"]))
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse energy float: %s", e)
            if "delta_e" in data:
                try:
                    self._buffered_energies.append(float(data["delta_e"]))
                except (ValueError, TypeError) as e:
                    logger.debug("Could not parse delta_e float: %s", e)

        if not force and self._last_render_time > 0.0:
            if (now - self._last_render_time) < self.debounce_interval:
                return None

        self._last_render_time = now

        energy_arr = np.array(self._buffered_energies, dtype=np.float64) if self._buffered_energies else np.array([0.0])
        var_val = float(np.var(energy_arr)) if len(energy_arr) > 0 else 0.0
        summary_dict = self.compressor.compress_to_dict(energy_arr)

        return {
            "current_stage": self._latest_stage,
            "scf_cycle": self._latest_scf_cycle,
            "progress_percent": self._latest_progress,
            "energy_variance": var_val,
            "energy_summary": summary_dict,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def poll_ndjson_and_render_summary(
        self,
        log_file: Union[str, Path],
        from_byte_offset: int = 0,
        current_time: Optional[float] = None,
        force: bool = False,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """Incrementally tails an NDJSON file and applies debounced statistical rendering."""
        target_path = Path(log_file).resolve()
        if not target_path.exists():
            return None, from_byte_offset

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
                    except json.JSONDecodeError as e:
                        logger.debug("Skipping unparseable NDJSON line: %s", e)
            next_offset = f.tell()

        if not events:
            return None, next_offset

        summary = self.process_stream_events(events, current_time=current_time, force=force)
        return summary, next_offset


# ==============================================================================
# 5. Live Asymptotic Convergence Plotting
# ==============================================================================

class LiveConvergencePlotter:
    """Plotly FigureWidget controller for live energy residual convergence graphing."""

    def __init__(self, max_points: int = 1000) -> None:
        self.max_points = int(max_points)

    def create_figure(self, title: str = "Live Asymptotic Convergence") -> Union[go.FigureWidget, go.Figure]:
        """Initializes a Plotly FigureWidget (with go.Figure fallback) with scientific styling and log y-axis."""
        data = [
            go.Scatter(
                x=[],
                y=[],
                mode="lines+markers",
                name="Energy Residual |ΔE|",
                line=dict(color="#00bcd4", width=2),
                marker=dict(size=4, color="#ffffff"),
            )
        ]
        layout = go.Layout(
            title=title,
            xaxis=dict(title="SCF Iteration / Extrapolation Cycle", showgrid=True),
            yaxis=dict(
                title="Energy Residual |ΔE| (Hartree)",
                type="log",
                exponentformat="e",
                showgrid=True,
            ),
            template="plotly_dark",
            margin=dict(l=60, r=40, t=50, b=50),
        )
        try:
            return go.FigureWidget(data=data, layout=layout)
        except Exception as e:
            logger.debug("FigureWidget initialization deferred to Figure fallback: %s", e)
            return go.Figure(data=data, layout=layout)

    def update_plot(
        self,
        fig: Any,
        energy_residuals: Union[Sequence[float], np.ndarray],
        iterations: Optional[Union[Sequence[float], np.ndarray]] = None,
        max_points: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Updates trace data on FigureWidget with LTTB decimation when exceeding max_points.

        Returns:
            Tuple of (original_point_count, rendered_point_count).
        """
        y_arr = np.asarray(energy_residuals, dtype=np.float64)
        if len(y_arr) == 0:
            return 0, 0

        if iterations is None:
            x_arr = np.arange(1, len(y_arr) + 1, dtype=np.float64)
        else:
            x_arr = np.asarray(iterations, dtype=np.float64)

        limit = max_points if max_points is not None else self.max_points
        orig_count = len(y_arr)

        if orig_count > limit:
            x_rendered, y_rendered = decimate_lttb(x_arr, y_arr, max_points=limit)
        else:
            x_rendered, y_rendered = x_arr, y_arr

        if hasattr(fig, "data") and len(fig.data) > 0:
            try:
                fig.data[0].x = x_rendered
                fig.data[0].y = y_rendered
            except Exception as e:
                logger.debug("Falling back to update_traces on Figure: %s", e)
                fig.update_traces(x=x_rendered, y=y_rendered)

        return orig_count, len(y_rendered)


# ==============================================================================
# 6. NanInfInterceptor & Fatal Error Interception
# ==============================================================================

class NanInfInterceptor:
    """Live stdout stream scanner trapping linear dependence, NaN, and Inf anomalies."""

    OVERLAP_EIGENVAL_REGEX = re.compile(
        r"Lowest\s+eigenvalue\s+of\s+the\s+overlap\s+matrix\s*[:=]?\s*([+-]?(?:[0-9]*\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?)",
        re.IGNORECASE,
    )
    NAN_REGEX = re.compile(r"\b(?:nan|nan\s+eh)\b", re.IGNORECASE)
    INF_REGEX = re.compile(r"\b(?:[+-]?inf|[+-]?infinity)\b", re.IGNORECASE)
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
            except OSError as e:
                logger.debug("Failed to unlink ABORT.signal: %s", e)
                return False
        return False

    def scan_line(self, line: str) -> Optional[InterceptionAlert]:
        """Scans a single stdout line against exact regex hooks."""
        if not line or not line.strip():
            return None

        match_eig = self.OVERLAP_EIGENVAL_REGEX.search(line)
        if match_eig:
            try:
                val = float(match_eig.group(1))
                if val < self.eigenvalue_threshold:
                    abort_path = self.create_abort_signal(reason=f"OVERLAP_EIGENVAL_{val:.2e}_BELOW_THRESHOLD")
                    return InterceptionAlert(
                        alert_type="LINEAR_DEPENDENCE",
                        raw_line=line.strip(),
                        extracted_value=val,
                        abort_triggered=True,
                        abort_file_path=str(abort_path),
                    )
            except (ValueError, IndexError) as e:
                logger.debug("Could not parse eigenvalue token: %s", e)

        if self.NAN_REGEX.search(line):
            abort_path = self.create_abort_signal(reason="NAN_DETECTED")
            return InterceptionAlert(
                alert_type="NAN_DETECTED",
                raw_line=line.strip(),
                abort_triggered=True,
                abort_file_path=str(abort_path),
            )

        if self.INF_REGEX.search(line):
            abort_path = self.create_abort_signal(reason="INF_DETECTED")
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


class FatalErrorInterceptor:
    """Interception engine monitoring ZMQ heartbeats, Segfaults, OOMs, and numerical anomalies."""

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        nan_inf_interceptor: Optional[NanInfInterceptor] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.nan_inf_interceptor = nan_inf_interceptor or NanInfInterceptor(artifacts_dir=self.artifacts_dir)

    def is_fatal_exit_code(self, exit_code: Optional[int]) -> bool:
        """Returns True if exit code indicates OS Segfault or Out-Of-Memory termination."""
        if exit_code is None:
            return False
        return exit_code in ALL_FATAL_RETURN_CODES

    def check_zmq_heartbeat(self, sub_socket: zmq.Socket, timeout_ms: int = 1000) -> bool:
        """Polls a ZeroMQ SUB heartbeat socket. Returns True if heartbeat received."""
        events = sub_socket.poll(timeout=timeout_ms, flags=zmq.POLLIN)
        if events & zmq.POLLIN:
            try:
                sub_socket.recv(flags=zmq.NOBLOCK)
                return True
            except zmq.ZMQError as e:
                logger.debug("Failed non-blocking receive on ZMQ heartbeat socket: %s", e)
                return False
        return False

    def extract_stderr_hex_dump(self, stderr_data: Optional[Union[str, bytes]], num_bytes: int = 256) -> str:
        """Extracts exact 256-byte hexadecimal dump of stderr output."""
        if stderr_data is None:
            return "00" * num_bytes
        if isinstance(stderr_data, str):
            b_data = stderr_data.encode("utf-8", errors="replace")
        else:
            b_data = bytes(stderr_data)

        truncated = b_data[:num_bytes]
        if len(truncated) < num_bytes:
            truncated = truncated.ljust(num_bytes, b"\x00")
        return truncated.hex()

    def generate_red_html_readout(
        self,
        error_type: str,
        exit_code: Optional[int],
        message: str,
        hex_dump: str,
    ) -> str:
        """Generates high-visibility red HTML crash banner for Jupyter/Voila UI."""
        safe_msg = html.escape(message)
        safe_type = html.escape(error_type)
        safe_hex = html.escape(hex_dump[:64] + ("..." if len(hex_dump) > 64 else ""))

        return (
            f'<div class="cochem-fatal-crash-card" style="'
            f'background-color: #8b0000; color: #ffffff; padding: 18px; border: 2px solid #ff4d4d; '
            f'border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, monospace; '
            f'margin: 12px 0; box-shadow: 0 4px 12px rgba(255, 77, 77, 0.3);">'
            f'<h3 style="margin-top: 0; color: #ffcccc; display: flex; align-items: center;">'
            f'<span style="background-color: #ff4d4d; color: #000000; padding: 2px 8px; border-radius: 4px; '
            f'font-size: 12px; font-weight: bold; margin-right: 10px;">FATAL ERROR</span> '
            f'{safe_type}</h3>'
            f'<p style="margin: 6px 0; font-size: 14px;"><strong>Exit Code:</strong> {exit_code}</p>'
            f'<p style="margin: 6px 0; font-size: 13px;"><strong>Diagnostic:</strong> {safe_msg}</p>'
            f'<div style="background-color: #1a0000; padding: 10px; border-radius: 4px; margin-top: 10px; '
            f'font-family: monospace; font-size: 11px; word-break: break-all; color: #ff9999;">'
            f'<strong>256-Byte Stderr Hex:</strong> {safe_hex}'
            f'</div></div>'
        )

    def generate_jsonld_provenance(
        self,
        error_type: str,
        exit_code: Optional[int],
        hex_dump: str,
        provenance_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Constructs structured JSON-LD recovery instructions from provenance block."""
        return {
            "@context": "https://schema.org",
            "@type": "SoftwareCrashProvenance",
            "errorType": error_type,
            "exitCode": exit_code,
            "stderrHexDump": hex_dump,
            "provenance": {
                "methodology": "[M] Method Matrix v4 Standards",
                "dataset": "[D] Canonical Wavefunction Landscape",
                "execution": "[E] CoChem-BENCH SubprocessBroker",
            },
            "recoveryInstructions": [
                "Step 1: Reduce integration grid to defgrid1 to relax convergence criteria.",
                "Step 2: Increase physical memory ceiling in cochem_system_config.json.",
                "Step 3: Remove orphaned lock files in BENCH_Workspace/Logs and restart benchmark.",
            ],
            "metadata": provenance_meta or {},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def intercept_fatal_error(
        self,
        exit_code: Optional[int] = None,
        stderr_bytes: Optional[Union[str, bytes]] = None,
        error_classification: Optional[str] = None,
        provenance_meta: Optional[Dict[str, Any]] = None,
    ) -> FatalErrorReport:
        """Constructs complete FatalErrorReport from exit code and standard error dump."""
        err_type = error_classification or ("SEGMENTATION_FAULT" if exit_code in SEGFAULT_RETURN_CODES else "FATAL_CRASH")
        hex_dump = self.extract_stderr_hex_dump(stderr_bytes)
        red_html = self.generate_red_html_readout(
            error_type=err_type,
            exit_code=exit_code,
            message="Fatal OS-level fault or process abort detected.",
            hex_dump=hex_dump,
        )
        json_ld = self.generate_jsonld_provenance(
            error_type=err_type,
            exit_code=exit_code,
            hex_dump=hex_dump,
            provenance_meta=provenance_meta,
        )
        return FatalErrorReport(
            is_fatal=True,
            error_type=err_type,
            exit_code=exit_code,
            stderr_hex_dump=hex_dump,
            red_html_readout=red_html,
            json_ld_provenance=json_ld,
        )

    def intercept_line(self, line: str) -> Optional[FatalErrorReport]:
        """Scans line for numerical instability (lowest eigenvalue < 1e-6, NaN, Inf)."""
        alert = self.nan_inf_interceptor.scan_line(line)
        if alert is None:
            return None

        hex_dump = self.extract_stderr_hex_dump(line)
        red_html = self.generate_red_html_readout(
            error_type=alert.alert_type,
            exit_code=-1,
            message=f"Numerical Trap Intercepted: {alert.raw_line}",
            hex_dump=hex_dump,
        )
        json_ld = self.generate_jsonld_provenance(
            error_type=alert.alert_type,
            exit_code=-1,
            hex_dump=hex_dump,
        )
        return FatalErrorReport(
            is_fatal=True,
            error_type=alert.alert_type,
            exit_code=-1,
            stderr_hex_dump=hex_dump,
            red_html_readout=red_html,
            json_ld_provenance=json_ld,
        )
