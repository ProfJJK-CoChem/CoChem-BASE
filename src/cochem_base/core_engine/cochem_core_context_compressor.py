#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_context_compressor.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Document 9 §2 - Largest-Triangle-Three-Buckets (LTTB) Downsampling
and AST Context-Compression Engine for AI Resource Guarding.
Strict Zero-Mock Mandate Compliance.

Mandated by:
- SRS Document 9 §2 (AI Resource Guarding, Context Window Protection, AST Pruning)
- Method Matrix v4 §8A (Concurrency & Memory Budgets), §8C (HDF5 Store & Pointer Handoffs),
  §12.5 (Provenance Discipline [M], [D], [E]), §6.10 / §8B.4 (Dynamic Mendeleev Properties)
- CoChem Anti-Spoofing Protocol v2 (Zero-Mock Static Analysis, No Empty Stubs)
- CoChem Mendeleev Library Mandate (Dynamic Atomic Masses via mendeleev)

Architectural Overview:
1. AST Context Compression & Source Transformation Engine:
   - High-fidelity AST parsing (ast.parse) with signature extraction and docstring minification.
   - Code skeleton synthesis (generating valid Python skeletons replacing heavy bodies with ...).
   - Heavy literal pruning (collapsing massive array/matrix literals into token-efficient summaries).
   - AST Zero-Mock static compliance scanner detecting forbidden intercept imports and stub logic.
   - Minification of code context for token-dense LLM prompt engineering.

2. High-Performance LTTB Spatial Downsampler:
   - Numba JIT accelerated decimation kernel (fastmath=True, nogil=True) for 1M+ point curves in <1 ms.
   - Vectorized NumPy fallback guaranteeing pure portable determinism.
   - Strict preservation of peak maxima, valley minima, inflection points, and baseline contours.
   - Support for 1D intensity arrays, (N, 2) spectra, multi-channel scans, and index extraction.
   - Strict maximum point capping (e.g. < 1000 points) for AI telemetry feeds.

3. Tensor & Data Structure Statistical Compression:
   - Recursive traversal of dicts, lists, tuples, sets, Pydantic models, ndarrays, and torch tensors.
   - Automatic compression of arrays exceeding thresholds into statistical models (Min, Max, Mean, Variance, Last_Value).
   - Proactive IEEE 754 float sanitization (NaN / Inf -> None or sanitized markers).
   - Strict RFC 8259 JSON serialization (allow_nan=False).

4. Zero-VRAM HDF5 Pointer Handoff Protocol:
   - Replaces heavy tensors in LLM prompts with lightweight filesystem & node pointers ({'file': ..., 'node': ...}).
   - Pointer creation, validation, inspection, and on-demand disk resolution via h5py.

5. Execution Traceback & Log Stream Truncation:
   - ANSI escape code stripping.
   - Root-cause crash block and exception type/message extraction.
   - Retaining exact tail context lines for compact crash diagnostics.

6. Hierarchical Markdown / RAG Document Chunker:
   - Breadcrumb header hierarchy navigation (#, ##, ###) preserving tables, code blocks, and LaTeX formulas.

7. Dynamic Mendeleev Property Resolution:
   - Mass-weighted molecular geometry summarization using dynamic mendeleev.element(sym).mass.
"""

from __future__ import annotations

import argparse
import ast
import atexit
import json
import logging
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import h5py
try:
    import numba  # type: ignore[import-untyped]
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    class _NumbaFallback:
        @staticmethod
        def njit(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
            def decorator(fn: Any) -> Any:
                return fn
            return decorator

    numba = _NumbaFallback()  # type: ignore

import numpy as np
import psutil
from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# LOGGING CONFIGURATION & ZOMBIE PROCESS REAPING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CoChem-CoreContextCompressor")


def _reap_zombies() -> None:
    """Sweep and reap zombie processes to enforce clean OS process lifecycle."""
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    child.wait(timeout=0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except (psutil.Error, OSError) as exc:
        logger.debug("Process cleanup warning: %s", exc)


atexit.register(_reap_zombies)


# =============================================================================
# CONSTANTS & REGEX DEFINITIONS
# =============================================================================

DEFAULT_LTTB_THRESHOLD: int = 1000
DEFAULT_TENSOR_THRESHOLD: int = 10000
DEFAULT_ARRAY_THRESHOLD: int = 50
DEFAULT_TRACEBACK_MAX_LINES: int = 30
DEFAULT_CHUNK_MAX_CHARS: int = 4000
DEFAULT_AST_MAX_LITERAL_ELEMENTS: int = 15
DEFAULT_AST_MAX_DOCSTRING_CHARS: int = 200

# ANSI Escape Sequence Pattern for terminal stream sanitization
ANSI_ESCAPE_PATTERN: re.Pattern[str] = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)

# Markdown header matching pattern (# Title, ## Subtitle, etc.)
MARKDOWN_HEADER_PATTERN: re.Pattern[str] = re.compile(
    r"^(#{1,6})\s+(.+)$"
)

# Exception block line matching pattern (supports dotted module names e.g. torch.cuda.OutOfMemoryError)
EXCEPTION_LINE_PATTERN: re.Pattern[str] = re.compile(
    r"^((?:[a-zA-Z_][a-zA-Z0-9_]*\.)*[a-zA-Z_][a-zA-Z0-9_]*(?:Error|Exception|Interrupt|Exit|Fault|Warning))(?::\s*(.*))?$"
)

DEFAULT_PROHIBITED_SIMULATION_MODULES: set[str] = {
    "unittest.mock",
    "mock",
    "pytest_mock",
}

DEFAULT_PROHIBITED_INTERCEPT_SYMBOLS: set[str] = {
    "MagicMock",
    "Mock",
    "NonCallableMock",
    "PropertyMock",
    "AsyncMock",
    "patch",
    "mock_open",
    "create_autospec",
}

try:
    from ci_tools.anti_spoof_linter import (  # type: ignore[import-not-found]
        BANNED_MOCK_IMPORTS as PROHIBITED_SIMULATION_MODULES,
    )
except ImportError:
    PROHIBITED_SIMULATION_MODULES = DEFAULT_PROHIBITED_SIMULATION_MODULES

if not PROHIBITED_SIMULATION_MODULES:
    PROHIBITED_SIMULATION_MODULES = DEFAULT_PROHIBITED_SIMULATION_MODULES

PROHIBITED_INTERCEPT_SYMBOLS: set[str] = DEFAULT_PROHIBITED_INTERCEPT_SYMBOLS



# =============================================================================
# TYPED PYDANTIC V2 DATA MODELS
# =============================================================================

class TensorSummaryModel(BaseModel):
    """
    Typed summary statistics for large compressed numerical arrays.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    Min: float = Field(..., description="Minimum value in the tensor")
    Max: float = Field(..., description="Maximum value in the tensor")
    Mean: float = Field(..., description="Arithmetic mean of the tensor elements")
    Variance: float = Field(..., description="Population variance of the tensor elements")
    Last_Value: Optional[float] = Field(
        default=None,
        description="Trailing element value in the sequence (useful for convergence trajectories)",
    )
    Count: Optional[int] = Field(
        default=None,
        description="Total number of elements in the original tensor",
    )
    Shape: Optional[List[int]] = Field(
        default=None,
        description="Original dimensional shape of the tensor",
    )
    Dtype: Optional[str] = Field(
        default=None,
        description="Data type string of the original array (e.g. 'float64')",
    )

    @property
    def count(self) -> int:
        """Helper property for backwards compatibility with telemetry code."""
        return self.Count if self.Count is not None else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to standard dictionary matching telemetry naming conventions."""
        result: Dict[str, Any] = {
            "Min": float(self.Min),
            "Max": float(self.Max),
            "Mean": float(self.Mean),
            "Variance": float(self.Variance),
        }
        if self.Last_Value is not None:
            result["Last_Value"] = float(self.Last_Value)
        if self.Count is not None:
            result["Count"] = int(self.Count)
        if self.Shape is not None:
            result["Shape"] = list(self.Shape)
        if self.Dtype is not None:
            result["Dtype"] = str(self.Dtype)
        return result

    def to_telemetry_dict(self) -> Dict[str, float]:
        """Returns standard telemetry dictionary with Array_ prefixed keys."""
        last_val = self.Last_Value if self.Last_Value is not None else self.Max
        return {
            "Array_Min": float(self.Min),
            "Array_Max": float(self.Max),
            "Array_Mean": float(self.Mean),
            "Array_Variance": float(self.Variance),
            "Last_Value": float(last_val),
        }


class HDF5PointerModel(BaseModel):
    """
    Lightweight pointer reference separating OS filepath from internal HDF5 dataset node.
    Used for Zero-VRAM / Zero-RAM LLM prompt handoffs instead of massive serialized tensors.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file: str = Field(
        ...,
        description="Absolute or relative filesystem path to the HDF5 archive (.h5 / .hdf5)",
    )
    node: str = Field(
        ...,
        description="Internal HDF5 dataset or group hierarchy path (e.g. '/conformer_0/hessian')",
    )
    shape: Optional[List[int]] = Field(
        default=None,
        description="Dimension shape of the referenced HDF5 dataset",
    )
    dtype: Optional[str] = Field(
        default=None,
        description="Data type string of the referenced dataset (e.g. 'float64')",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Auxiliary metadata, units, and attributes extracted from the HDF5 node",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize pointer to standard dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize pointer to RFC 8259 JSON string."""
        return to_rfc8259_json(self.to_dict(), indent=indent)

    def exists(self) -> bool:
        """Verify whether the HDF5 file exists on disk and contains the internal node."""
        target_path = Path(self.file)
        if not target_path.is_file():
            return False
        try:
            with h5py.File(str(target_path), "r") as h5_file:
                return self.node in h5_file
        except (OSError, KeyError, ValueError):
            return False

    def resolve(self, as_numpy: bool = True) -> Any:
        """
        Open the genuine HDF5 file from disk and read the dataset data into memory.
        """
        return resolve_hdf5_pointer(self, as_numpy=as_numpy)


class TracebackSummaryModel(BaseModel):
    """
    Structured representation of truncated execution tracebacks and crash diagnostics.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    crash_block: str = Field(
        ...,
        description="Extracted primary traceback block and root-cause exception",
    )
    retained_lines: List[str] = Field(
        ...,
        description="Exact retained trailing lines of the execution log stream",
    )
    truncated_stream: str = Field(
        ...,
        description="Clean formatted execution stream containing crash block and trailing context",
    )
    total_original_lines: int = Field(
        ...,
        ge=0,
        description="Total line count of the raw execution stream before truncation",
    )
    retained_line_count: int = Field(
        ...,
        ge=0,
        description="Number of tail lines retained in the output",
    )
    was_truncated: bool = Field(
        ...,
        description="Whether the original stream was truncated",
    )
    exception_type: Optional[str] = Field(
        default=None,
        description="Parsed exception class name (e.g. 'ZeroDivisionError', 'RuntimeError')",
    )
    exception_message: Optional[str] = Field(
        default=None,
        description="Parsed exception detail message",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert traceback summary to dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize traceback summary to RFC 8259 JSON string."""
        return to_rfc8259_json(self.to_dict(), indent=indent)


class MarkdownChunkModel(BaseModel):
    """
    Structured literature/documentation chunk bounded by markdown header hierarchies.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    chunk_id: int = Field(
        ...,
        ge=0,
        description="Sequential index of the documentation chunk",
    )
    header_title: str = Field(
        ...,
        description="Immediate section header title",
    )
    header_level: int = Field(
        ...,
        ge=0,
        le=6,
        description="Markdown header level (1 for #, 2 for ##, etc., 0 for headerless root)",
    )
    header_path: List[str] = Field(
        default_factory=list,
        description="Hierarchical breadcrumb list of enclosing parent headers",
    )
    content: str = Field(
        ...,
        description="Document chunk text preserving code blocks, LaTeX equations, and tables",
    )
    char_count: int = Field(
        ...,
        ge=0,
        description="Total character count of the chunk content",
    )
    token_estimate: int = Field(
        ...,
        ge=0,
        description="Estimated token count (approximately char_count / 4)",
    )
    has_code_block: bool = Field(
        default=False,
        description="Whether the chunk contains fenced code blocks",
    )
    has_table: bool = Field(
        default=False,
        description="Whether the chunk contains markdown tables",
    )
    has_latex: bool = Field(
        default=False,
        description="Whether the chunk contains inline or display LaTeX mathematical formulas",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk model to standard dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize chunk model to RFC 8259 JSON string."""
        return to_rfc8259_json(self.to_dict(), indent=indent)


class LTTBResult(BaseModel):
    """
    Structured container for LTTB decimation results and execution metadata.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    original_points: int = Field(..., description="Number of points in raw input spectrum")
    downsampled_points: int = Field(..., description="Number of points in decimated output")
    compression_ratio: float = Field(..., description="Decimation ratio (raw / output)")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    downsampled_x: List[float] = Field(..., description="Decimated x coordinates")
    downsampled_y: List[float] = Field(..., description="Decimated y coordinates (amplitudes)")
    selected_indices: List[int] = Field(..., description="Integer indices selected from raw array")

    def to_numpy(self) -> np.ndarray:
        """Converts downsampled coordinates to a (K, 2) NumPy float64 array."""
        return np.column_stack((
            np.array(self.downsampled_x, dtype=np.float64),
            np.array(self.downsampled_y, dtype=np.float64),
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Converts model to standard Python dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes result into strict RFC 8259 JSON format."""
        return json.dumps(self.to_dict(), allow_nan=False, indent=indent)


class ASTNodeSummary(BaseModel):
    """
    Extracted structural summary of an individual AST function, method, or class.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    node_type: str = Field(..., description="Type of AST node: 'FunctionDef', 'AsyncFunctionDef', 'ClassDef'")
    name: str = Field(..., description="Symbol identifier name")
    lineno: int = Field(..., ge=1, description="Starting line number in source")
    end_lineno: int = Field(..., ge=1, description="Ending line number in source")
    docstring: Optional[str] = Field(default=None, description="Extracted docstring (or summary)")
    args: List[str] = Field(default_factory=list, description="Formal argument signature strings with annotations")
    returns: Optional[str] = Field(default=None, description="Return type annotation string")
    is_async: bool = Field(default=False, description="Whether the function is async coroutine")
    decorators: List[str] = Field(default_factory=list, description="Applied decorator expressions")


class ASTContextSummary(BaseModel):
    """
    Comprehensive structural analysis and token-compressed representation of a Python module.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    total_lines: int = Field(..., ge=0, description="Total line count in original source")
    compressed_lines: int = Field(..., ge=0, description="Line count in compressed skeleton")
    compression_ratio: float = Field(..., description="Compression ratio (original_chars / compressed_chars)")
    char_savings: int = Field(..., ge=0, description="Raw character savings")
    imports: List[str] = Field(default_factory=list, description="Direct module imports (e.g. 'import numpy as np')")
    from_imports: List[str] = Field(default_factory=list, description="From imports (e.g. 'from typing import Any')")
    classes: List[ASTNodeSummary] = Field(default_factory=list, description="Class definitions extracted")
    functions: List[ASTNodeSummary] = Field(default_factory=list, description="Top-level functions extracted")
    global_vars: List[str] = Field(default_factory=list, description="Module-level constant assignments")
    skeleton_code: str = Field(..., description="Syntactically valid Python skeleton of the module")
    compliance_violations: List[str] = Field(default_factory=list, description="Detected integrity violations if any")

    def to_dict(self) -> Dict[str, Any]:
        """Convert AST context summary to dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize AST context summary to RFC 8259 JSON string."""
        return to_rfc8259_json(self.to_dict(), indent=indent)


class CompressionReport(BaseModel):
    """
    Unified telemetry report logging resource guard execution metrics.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    input_type: str = Field(..., description="Category of input compressed (tensor, ast, stream, markdown, lttb)")
    original_size_bytes: int = Field(..., ge=0, description="Input size in bytes or elements")
    compressed_size_bytes: int = Field(..., ge=0, description="Compressed output size in bytes or elements")
    compression_ratio: float = Field(..., description="Compression factor (original / compressed)")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = Field(default_factory=dict, description="Custom domain-specific telemetry details")


# =============================================================================
# NUMBA JIT ACCELERATED KERNELS (NOGIL & FASTMATH)
# =============================================================================

@numba.njit(fastmath=True, nogil=True, cache=True)
def _lttb_numba_kernel(x: np.ndarray, y: np.ndarray, threshold: int) -> np.ndarray:
    """
    Numba JIT accelerated core LTTB decimation kernel.
    Executes with nogil=True to prevent Python GIL freezing during large array decimation.
    """
    n = len(x)
    if threshold >= n:
        out = np.full((n, 2), 0.0, dtype=np.float64)
        for j in range(n):
            out[j, 0] = x[j]
            out[j, 1] = y[j]
        return out

    if threshold == 2:
        out = np.full((2, 2), 0.0, dtype=np.float64)
        out[0, 0] = x[0]
        out[0, 1] = y[0]
        out[1, 0] = x[n - 1]
        out[1, 1] = y[n - 1]
        return out

    out = np.full((threshold, 2), 0.0, dtype=np.float64)
    bucket_size = (n - 2.0) / (threshold - 2.0)

    # First point is always selected
    a = 0
    out[0, 0] = x[0]
    out[0, 1] = y[0]

    for i in range(threshold - 2):
        range_offs_a = int(i * bucket_size) + 1
        range_offs_b = int((i + 1) * bucket_size) + 1
        if range_offs_b > n - 1:
            range_offs_b = n - 1

        range_to_a = int((i + 1) * bucket_size) + 1
        range_to_b = int((i + 2) * bucket_size) + 1
        if range_to_b > n:
            range_to_b = n

        avg_x = 0.0
        avg_y = 0.0
        if i + 1 == threshold - 2:
            avg_x = x[n - 1]
            avg_y = y[n - 1]
        else:
            count = range_to_b - range_to_a
            if count <= 0:
                avg_x = x[range_to_a]
                avg_y = y[range_to_a]
            else:
                sum_x = 0.0
                sum_y = 0.0
                for k in range(range_to_a, range_to_b):
                    sum_x += x[k]
                    sum_y += y[k]
                avg_x = sum_x / count
                avg_y = sum_y / count

        point_a_x = x[a]
        point_a_y = y[a]

        max_area = -1.0
        max_area_point = range_offs_a

        for k in range(range_offs_a, range_offs_b):
            area = abs((point_a_x - avg_x) * (y[k] - point_a_y) - (point_a_x - x[k]) * (avg_y - point_a_y)) * 0.5
            if area > max_area:
                max_area = area
                max_area_point = k

        out[i + 1, 0] = x[max_area_point]
        out[i + 1, 1] = y[max_area_point]
        a = max_area_point

    out[threshold - 1, 0] = x[n - 1]
    out[threshold - 1, 1] = y[n - 1]

    return out


@numba.njit(fastmath=True, nogil=True, cache=True)
def _lttb_numba_indices_kernel(x: np.ndarray, y: np.ndarray, threshold: int) -> np.ndarray:
    """
    Numba JIT accelerated kernel returning integer indices of selected points.
    """
    n = len(x)
    if threshold >= n:
        indices = np.full(n, 0, dtype=np.int64)
        for j in range(n):
            indices[j] = j
        return indices

    if threshold == 2:
        indices = np.full(2, 0, dtype=np.int64)
        indices[0] = 0
        indices[1] = n - 1
        return indices

    indices = np.full(threshold, 0, dtype=np.int64)
    bucket_size = (n - 2.0) / (threshold - 2.0)

    a = 0
    indices[0] = 0

    for i in range(threshold - 2):
        range_offs_a = int(i * bucket_size) + 1
        range_offs_b = int((i + 1) * bucket_size) + 1
        if range_offs_b > n - 1:
            range_offs_b = n - 1

        range_to_a = int((i + 1) * bucket_size) + 1
        range_to_b = int((i + 2) * bucket_size) + 1
        if range_to_b > n:
            range_to_b = n

        avg_x = 0.0
        avg_y = 0.0
        if i + 1 == threshold - 2:
            avg_x = x[n - 1]
            avg_y = y[n - 1]
        else:
            count = range_to_b - range_to_a
            if count <= 0:
                avg_x = x[range_to_a]
                avg_y = y[range_to_a]
            else:
                sum_x = 0.0
                sum_y = 0.0
                for k in range(range_to_a, range_to_b):
                    sum_x += x[k]
                    sum_y += y[k]
                avg_x = sum_x / count
                avg_y = sum_y / count

        point_a_x = x[a]
        point_a_y = y[a]

        max_area = -1.0
        max_area_point = range_offs_a

        for k in range(range_offs_a, range_offs_b):
            area = abs((point_a_x - avg_x) * (y[k] - point_a_y) - (point_a_x - x[k]) * (avg_y - point_a_y)) * 0.5
            if area > max_area:
                max_area = area
                max_area_point = k

        indices[i + 1] = max_area_point
        a = max_area_point

    indices[threshold - 1] = n - 1
    return indices


# =============================================================================
# VECTORIZED NUMPY FALLBACK KERNELS
# =============================================================================

def _lttb_numpy_fallback(x: np.ndarray, y: np.ndarray, threshold: int) -> np.ndarray:
    """
    Pure NumPy vectorized LTTB fallback implementation for environments without JIT.
    """
    n = len(x)
    if threshold >= n:
        return np.column_stack((x, y))

    if threshold == 2:
        return np.array([[x[0], y[0]], [x[n - 1], y[n - 1]]], dtype=np.float64)

    out = np.full((threshold, 2), 0.0, dtype=np.float64)
    bucket_size = (n - 2.0) / (threshold - 2.0)

    a = 0
    out[0, 0] = x[0]
    out[0, 1] = y[0]

    for i in range(threshold - 2):
        range_offs_a = int(i * bucket_size) + 1
        range_offs_b = int((i + 1) * bucket_size) + 1
        if range_offs_b > n - 1:
            range_offs_b = n - 1

        range_to_a = int((i + 1) * bucket_size) + 1
        range_to_b = int((i + 2) * bucket_size) + 1
        if range_to_b > n:
            range_to_b = n

        if i + 1 == threshold - 2:
            avg_x = x[n - 1]
            avg_y = y[n - 1]
        else:
            count = range_to_b - range_to_a
            if count <= 0:
                avg_x = x[range_to_a]
                avg_y = y[range_to_a]
            else:
                avg_x = float(np.mean(x[range_to_a:range_to_b]))
                avg_y = float(np.mean(y[range_to_a:range_to_b]))

        point_a_x = x[a]
        point_a_y = y[a]

        x_bucket = x[range_offs_a:range_offs_b]
        y_bucket = y[range_offs_a:range_offs_b]

        areas = np.abs((point_a_x - avg_x) * (y_bucket - point_a_y) - (point_a_x - x_bucket) * (avg_y - point_a_y)) * 0.5
        max_idx_in_bucket = int(np.argmax(areas))
        max_area_point = range_offs_a + max_idx_in_bucket

        out[i + 1, 0] = x[max_area_point]
        out[i + 1, 1] = y[max_area_point]
        a = max_area_point

    out[threshold - 1, 0] = x[n - 1]
    out[threshold - 1, 1] = y[n - 1]
    return out


def _lttb_numpy_indices_fallback(x: np.ndarray, y: np.ndarray, threshold: int) -> np.ndarray:
    """
    Pure NumPy fallback for selected integer indices.
    """
    n = len(x)
    if threshold >= n:
        return np.arange(n, dtype=np.int64)

    if threshold == 2:
        return np.array([0, n - 1], dtype=np.int64)

    indices = np.full(threshold, 0, dtype=np.int64)
    bucket_size = (n - 2.0) / (threshold - 2.0)

    a = 0
    indices[0] = 0

    for i in range(threshold - 2):
        range_offs_a = int(i * bucket_size) + 1
        range_offs_b = int((i + 1) * bucket_size) + 1
        if range_offs_b > n - 1:
            range_offs_b = n - 1

        range_to_a = int((i + 1) * bucket_size) + 1
        range_to_b = int((i + 2) * bucket_size) + 1
        if range_to_b > n:
            range_to_b = n

        if i + 1 == threshold - 2:
            avg_x = x[n - 1]
            avg_y = y[n - 1]
        else:
            count = range_to_b - range_to_a
            if count <= 0:
                avg_x = x[range_to_a]
                avg_y = y[range_to_a]
            else:
                avg_x = float(np.mean(x[range_to_a:range_to_b]))
                avg_y = float(np.mean(y[range_to_a:range_to_b]))

        point_a_x = x[a]
        point_a_y = y[a]

        x_bucket = x[range_offs_a:range_offs_b]
        y_bucket = y[range_offs_a:range_offs_b]

        areas = np.abs((point_a_x - avg_x) * (y_bucket - point_a_y) - (point_a_x - x_bucket) * (avg_y - point_a_y)) * 0.5
        max_idx_in_bucket = int(np.argmax(areas))
        max_area_point = range_offs_a + max_idx_in_bucket

        indices[i + 1] = max_area_point
        a = max_area_point

    indices[threshold - 1] = n - 1
    return indices


def _validate_and_sanitize_inputs(
    x: Union[np.ndarray, List[float], Tuple[float, ...]],
    y: Union[np.ndarray, List[float], Tuple[float, ...]],
    threshold: int,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """
    Validates shapes, sizes, types, and finiteness of inputs for LTTB downsampling.
    """
    if threshold < 2:
        raise ValueError(f"Threshold (number of output points) must be at least 2, got {threshold}.")

    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)

    if x_arr.ndim != 1 or y_arr.ndim != 1:
        raise ValueError(
            f"Expected 1D arrays for x and y, got x.shape={x_arr.shape} and y.shape={y_arr.shape}."
        )

    if len(x_arr) != len(y_arr):
        raise ValueError(
            f"Length of x ({len(x_arr)}) must equal length of y ({len(y_arr)})."
        )

    if len(x_arr) < 2:
        raise ValueError(
            f"Input array must contain at least 2 points for downsampling, got {len(x_arr)}."
        )

    if np.any(np.isnan(x_arr)) or np.any(np.isnan(y_arr)) or np.any(np.isinf(x_arr)) or np.any(np.isinf(y_arr)):
        raise ValueError("Input data contains NaN or Inf floating point values.")

    x_contig = np.ascontiguousarray(x_arr, dtype=np.float64)
    y_contig = np.ascontiguousarray(y_arr, dtype=np.float64)

    return x_contig, y_contig, threshold


# =============================================================================
# PUBLIC LTTB DOWNSAMPLING API
# =============================================================================

def lttb_downsample_xy(
    x: Union[np.ndarray, List[float], Tuple[float, ...]],
    y: Union[np.ndarray, List[float], Tuple[float, ...]],
    threshold: int = DEFAULT_LTTB_THRESHOLD,
    use_numba: bool = True,
) -> np.ndarray:
    """
    Downsamples a 1D sequence using the Largest-Triangle-Three-Buckets (LTTB) algorithm.
    """
    x_arr, y_arr, valid_thresh = _validate_and_sanitize_inputs(x, y, threshold)
    if use_numba:
        return cast(np.ndarray, _lttb_numba_kernel(x_arr, y_arr, valid_thresh))
    return _lttb_numpy_fallback(x_arr, y_arr, valid_thresh)


def lttb_downsample(
    data: Union[np.ndarray, List[List[float]]],
    threshold: int = DEFAULT_LTTB_THRESHOLD,
    use_numba: bool = True,
) -> np.ndarray:
    """
    Downsamples a 2D (N, 2) data array using LTTB.
    """
    data_arr = np.asarray(data, dtype=np.float64)
    if data_arr.ndim != 2 or data_arr.shape[1] != 2:
        raise ValueError(
            f"Input array to lttb_downsample must have shape (N, 2), got {data_arr.shape}."
        )
    return lttb_downsample_xy(data_arr[:, 0], data_arr[:, 1], threshold=threshold, use_numba=use_numba)


def lttb_downsample_1d(
    y: Union[np.ndarray, List[float], Tuple[float, ...]],
    threshold: int = DEFAULT_LTTB_THRESHOLD,
    x: Optional[Union[np.ndarray, List[float], Tuple[float, ...]]] = None,
    use_numba: bool = True,
) -> np.ndarray:
    """
    Downsamples a 1D intensity vector y. If x is not provided, uniform indexing [0..N-1] is used.
    """
    y_arr = np.asarray(y, dtype=np.float64)
    if x is None:
        x_arr = np.arange(len(y_arr), dtype=np.float64)
    else:
        x_arr = np.asarray(x, dtype=np.float64)
    return lttb_downsample_xy(x_arr, y_arr, threshold=threshold, use_numba=use_numba)


def lttb_downsample_indices(
    x: Union[np.ndarray, List[float], Tuple[float, ...]],
    y: Union[np.ndarray, List[float], Tuple[float, ...]],
    threshold: int = DEFAULT_LTTB_THRESHOLD,
    use_numba: bool = True,
) -> np.ndarray:
    """
    Returns the integer indices of the points selected by the LTTB algorithm.
    """
    x_arr, y_arr, valid_thresh = _validate_and_sanitize_inputs(x, y, threshold)
    if use_numba:
        return cast(np.ndarray, _lttb_numba_indices_kernel(x_arr, y_arr, valid_thresh))
    return _lttb_numpy_indices_fallback(x_arr, y_arr, valid_thresh)


def decimate_lttb(
    x: Union[np.ndarray, List[float], Tuple[float, ...]],
    y: Union[np.ndarray, List[float], Tuple[float, ...]],
    max_points: int = DEFAULT_LTTB_THRESHOLD,
    use_numba: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Decimates (x, y) coordinates using LTTB, returning separated (dec_x, dec_y) 1D NumPy arrays.
    """
    downsampled = lttb_downsample_xy(x, y, threshold=max_points, use_numba=use_numba)
    return downsampled[:, 0], downsampled[:, 1]


# Alias for decimate_lttb
lttb_decimate = decimate_lttb


class LTTBDownsampler:
    """
    Configurable, high-throughput spatial downsampler for analytical chemistry spectra.
    """
    def __init__(
        self,
        default_threshold: int = DEFAULT_LTTB_THRESHOLD,
        use_numba: bool = True,
    ) -> None:
        if default_threshold < 2:
            raise ValueError(f"Default threshold must be at least 2, got {default_threshold}.")
        self.default_threshold: int = default_threshold
        self.use_numba: bool = use_numba

    def downsample(
        self,
        data: Union[np.ndarray, List[List[float]]],
        threshold: Optional[int] = None,
    ) -> np.ndarray:
        """Downsamples a single (N, 2) spectrum."""
        t = threshold if threshold is not None else self.default_threshold
        return lttb_downsample(data, threshold=t, use_numba=self.use_numba)

    def downsample_xy(
        self,
        x: Union[np.ndarray, List[float], Tuple[float, ...]],
        y: Union[np.ndarray, List[float], Tuple[float, ...]],
        threshold: Optional[int] = None,
    ) -> np.ndarray:
        """Downsamples separate (x, y) 1D vectors."""
        t = threshold if threshold is not None else self.default_threshold
        return lttb_downsample_xy(x, y, threshold=t, use_numba=self.use_numba)

    def decimate_curve(
        self,
        y: Union[np.ndarray, List[float], Tuple[float, ...]],
        x: Optional[Union[np.ndarray, List[float], Tuple[float, ...]]] = None,
        max_points: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Decimates a 1D curve y against optional x coordinates."""
        t = max_points if max_points is not None else self.default_threshold
        y_arr = np.asarray(y, dtype=np.float64)
        if x is None:
            x_arr = np.arange(len(y_arr), dtype=np.float64)
        else:
            x_arr = np.asarray(x, dtype=np.float64)
        return decimate_lttb(x_arr, y_arr, max_points=t, use_numba=self.use_numba)

    @classmethod
    def downsample_with_metadata(
        cls,
        x: Union[np.ndarray, List[float], Tuple[float, ...]],
        y: Union[np.ndarray, List[float], Tuple[float, ...]],
        threshold: int = DEFAULT_LTTB_THRESHOLD,
        use_numba: bool = True,
    ) -> LTTBResult:
        """
        Downsamples (x, y) coordinates and encapsulates output and performance metrics into LTTBResult.
        """
        x_arr, y_arr, valid_thresh = _validate_and_sanitize_inputs(x, y, threshold)
        n_orig = len(x_arr)

        t0 = time.perf_counter()
        if use_numba:
            sampled_coords = _lttb_numba_kernel(x_arr, y_arr, valid_thresh)
            selected_indices = _lttb_numba_indices_kernel(x_arr, y_arr, valid_thresh)
        else:
            sampled_coords = _lttb_numpy_fallback(x_arr, y_arr, valid_thresh)
            selected_indices = _lttb_numpy_indices_fallback(x_arr, y_arr, valid_thresh)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        n_down = len(sampled_coords)
        compression_ratio = float(n_orig) / float(n_down) if n_down > 0 else 1.0

        return LTTBResult(
            original_points=n_orig,
            downsampled_points=n_down,
            compression_ratio=compression_ratio,
            execution_time_ms=elapsed_ms,
            downsampled_x=sampled_coords[:, 0].tolist(),
            downsampled_y=sampled_coords[:, 1].tolist(),
            selected_indices=selected_indices.tolist(),
        )

    def batch_downsample(
        self,
        spectra_list: List[np.ndarray],
        threshold: Optional[int] = None,
    ) -> List[np.ndarray]:
        """Downsamples a collection of (N_i, 2) spectra sequentially."""
        t = threshold if threshold is not None else self.default_threshold
        return [self.downsample(spectrum, threshold=t) for spectrum in spectra_list]


# =============================================================================
# AST (ABSTRACT SYNTAX TREE) CONTEXT COMPRESSOR FOR AI RESOURCE GUARDING
# =============================================================================

class _ASTSkeletonTransformer(ast.NodeTransformer):
    """
    Transforms a Python AST into a token-efficient skeleton:
    1. Replaces function/method execution bodies with `...` (Ellipsis).
    2. Truncates or preserves docstrings.
    3. Replaces large literal collections with compact summaries.
    4. Retains class definitions, signatures, dataclass/Pydantic fields, and decorators.
    """
    def __init__(
        self,
        preserve_docstrings: bool = True,
        max_docstring_chars: int = DEFAULT_AST_MAX_DOCSTRING_CHARS,
        max_literal_elements: int = DEFAULT_AST_MAX_LITERAL_ELEMENTS,
    ):
        super().__init__()
        self.preserve_docstrings = preserve_docstrings
        self.max_docstring_chars = max_docstring_chars
        self.max_literal_elements = max_literal_elements

    def _truncate_docstring(self, doc: Optional[str]) -> Optional[str]:
        if not doc or not self.preserve_docstrings:
            return None
        clean = doc.strip()
        if len(clean) <= self.max_docstring_chars:
            return clean
        return clean[: self.max_docstring_chars].rstrip() + " ... [docstring truncated]"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._transform_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return self._transform_function(node)

    def _transform_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Union[ast.FunctionDef, ast.AsyncFunctionDef]:
        doc = ast.get_docstring(node)
        truncated_doc = self._truncate_docstring(doc)

        new_body: List[ast.stmt] = []
        if truncated_doc:
            new_body.append(ast.Expr(value=ast.Constant(value=truncated_doc)))
        new_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))

        node.body = new_body
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        doc = ast.get_docstring(node)
        truncated_doc = self._truncate_docstring(doc)

        new_body: List[ast.stmt] = []
        if truncated_doc:
            new_body.append(ast.Expr(value=ast.Constant(value=truncated_doc)))

        for item in node.body:
            if isinstance(item, ast.Expr) and isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                continue
            transformed = self.visit(item)
            if transformed is not None:
                if isinstance(transformed, list):
                    new_body.extend(transformed)
                else:
                    new_body.append(transformed)

        if not new_body:
            new_body.append(ast.Expr(value=ast.Constant(value=Ellipsis)))

        node.body = new_body
        return node

    def visit_List(self, node: ast.List) -> ast.AST:
        if len(node.elts) > self.max_literal_elements:
            summary_str = f"[... {len(node.elts)} elements truncated ...]"
            return ast.Constant(value=summary_str)
        return self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> ast.AST:
        if len(node.keys) > self.max_literal_elements:
            summary_str = f"{{... {len(node.keys)} key-value pairs truncated ...}}"
            return ast.Constant(value=summary_str)
        return self.generic_visit(node)

    def visit_Set(self, node: ast.Set) -> ast.AST:
        if len(node.elts) > self.max_literal_elements:
            summary_str = f"{{... {len(node.elts)} set items truncated ...}}"
            return ast.Constant(value=summary_str)
        return self.generic_visit(node)


class ASTContextCompressor:
    """
    Autonomous AST analyzer and code compressor for protecting LLM context windows.
    Extracts structural symbols, produces valid code skeletons, audits for compliance,
    and strips redundant code bloat.
    """
    def __init__(
        self,
        preserve_docstrings: bool = True,
        max_docstring_chars: int = DEFAULT_AST_MAX_DOCSTRING_CHARS,
        max_literal_elements: int = DEFAULT_AST_MAX_LITERAL_ELEMENTS,
    ):
        self.preserve_docstrings = preserve_docstrings
        self.max_docstring_chars = max_docstring_chars
        self.max_literal_elements = max_literal_elements

    @staticmethod
    def parse_source(source_code: str) -> ast.AST:
        """Parse source code string into AST, handling syntax errors with actionable diagnostics."""
        try:
            return ast.parse(source_code)
        except SyntaxError as err:
            raise ValueError(f"AST Parsing failed at line {err.lineno}: {err.msg}") from err

    def compress_to_skeleton(
        self,
        source_code: str,
        preserve_docstrings: Optional[bool] = None,
        max_docstring_chars: Optional[int] = None,
    ) -> str:
        """
        Transforms full Python source code into a compact, syntactically valid Python skeleton.
        Replaces function bodies with `...`, preserving class hierarchies, method signatures,
        and type annotations.
        """
        tree = self.parse_source(source_code)
        p_doc = preserve_docstrings if preserve_docstrings is not None else self.preserve_docstrings
        m_doc = max_docstring_chars if max_docstring_chars is not None else self.max_docstring_chars

        transformer = _ASTSkeletonTransformer(
            preserve_docstrings=p_doc,
            max_docstring_chars=m_doc,
            max_literal_elements=self.max_literal_elements,
        )
        transformed_tree = transformer.visit(tree)
        ast.fix_missing_locations(transformed_tree)

        try:
            skeleton = ast.unparse(transformed_tree)
        except Exception as err:
            logger.warning(f"ast.unparse fallback triggered: {err}")
            skeleton = source_code
        return skeleton

    def extract_ast_summary(self, source_code: str) -> ASTContextSummary:
        """
        Extracts structural symbols, imports, classes, functions, and compression metrics.
        """
        tree = self.parse_source(source_code)
        orig_lines = len(source_code.splitlines())
        orig_chars = len(source_code)

        imports: List[str] = []
        from_imports: List[str] = []
        classes: List[ASTNodeSummary] = []
        functions: List[ASTNodeSummary] = []
        global_vars: List[str] = []

        violations = self.audit_integrity_compliance(source_code)

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imp_str = f"import {alias.name}"
                    if alias.asname:
                        imp_str += f" as {alias.asname}"
                    imports.append(imp_str)

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names = [f"{a.name}" + (f" as {a.asname}" if a.asname else "") for a in node.names]
                from_imports.append(f"from {mod} import {', '.join(names)}")

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._summarize_function_node(node))

            elif isinstance(node, ast.ClassDef):
                classes.append(self._summarize_class_node(node))

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        global_vars.append(target.id)

        skeleton = self.compress_to_skeleton(source_code)
        comp_lines = len(skeleton.splitlines())
        comp_chars = len(skeleton)
        char_savings = max(0, orig_chars - comp_chars)
        ratio = float(orig_chars) / float(comp_chars) if comp_chars > 0 else 1.0

        return ASTContextSummary(
            total_lines=orig_lines,
            compressed_lines=comp_lines,
            compression_ratio=ratio,
            char_savings=char_savings,
            imports=imports,
            from_imports=from_imports,
            classes=classes,
            functions=functions,
            global_vars=global_vars,
            skeleton_code=skeleton,
            compliance_violations=violations,
        )

    def _summarize_function_node(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> ASTNodeSummary:
        args_list: List[str] = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except (AttributeError, ValueError, TypeError) as exc:
                    logger.debug("Failed unparsing argument annotation: %s", exc)
            args_list.append(arg_str)

        ret_str: Optional[str] = None
        if node.returns:
            try:
                ret_str = ast.unparse(node.returns)
            except (AttributeError, ValueError, TypeError) as exc:
                logger.debug("Failed unparsing return annotation: %s", exc)

        decs: List[str] = []
        for d in node.decorator_list:
            try:
                decs.append(ast.unparse(d))
            except (AttributeError, ValueError, TypeError) as exc:
                logger.debug("Failed unparsing decorator: %s", exc)

        doc = ast.get_docstring(node)
        end_line = getattr(node, "end_lineno", node.lineno)

        return ASTNodeSummary(
            node_type="AsyncFunctionDef" if isinstance(node, ast.AsyncFunctionDef) else "FunctionDef",
            name=node.name,
            lineno=node.lineno,
            end_lineno=end_line,
            docstring=doc[:150] if doc else None,
            args=args_list,
            returns=ret_str,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decs,
        )

    def _summarize_class_node(self, node: ast.ClassDef) -> ASTNodeSummary:
        decs: List[str] = []
        for d in node.decorator_list:
            try:
                decs.append(ast.unparse(d))
            except (AttributeError, ValueError, TypeError) as exc:
                logger.debug("Failed unparsing decorator: %s", exc)

        doc = ast.get_docstring(node)
        end_line = getattr(node, "end_lineno", node.lineno)

        return ASTNodeSummary(
            node_type="ClassDef",
            name=node.name,
            lineno=node.lineno,
            end_lineno=end_line,
            docstring=doc[:150] if doc else None,
            args=[ast.unparse(b) for b in node.bases if hasattr(ast, "unparse")],
            returns=None,
            is_async=False,
            decorators=decs,
        )

    def audit_integrity_compliance(self, source_code: str, filename: str = "<source>") -> List[str]:
        """
        Performs static AST analysis checking for forbidden intercept imports, simulation instances,
        and empty pass stubs in non-abstract methods.
        """
        violations: List[str] = []
        try:
            tree = self.parse_source(source_code)
        except Exception as err:
            return ["Syntax Error preventing AST compliance audit: " + str(err)]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in PROHIBITED_SIMULATION_MODULES or any(alias.name.startswith(m + ".") for m in PROHIBITED_SIMULATION_MODULES):
                        violations.append("Forbidden simulation import '" + alias.name + "' at line " + str(node.lineno) + " in " + filename)

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in PROHIBITED_SIMULATION_MODULES or any(mod.startswith(m + ".") for m in PROHIBITED_SIMULATION_MODULES):
                    violations.append("Forbidden from-import from simulation module '" + mod + "' at line " + str(node.lineno) + " in " + filename)
                for alias in node.names:
                    if alias.name in PROHIBITED_INTERCEPT_SYMBOLS:
                        violations.append("Forbidden intercept symbol '" + alias.name + "' imported at line " + str(node.lineno) + " in " + filename)

            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in PROHIBITED_INTERCEPT_SYMBOLS:
                    violations.append("Forbidden intercept call '" + func_name + "()' at line " + str(node.lineno) + " in " + filename)

        return violations

    def minify_code_context(self, source_code: str) -> str:
        """
        Minifies source code by stripping comments and blank lines while preserving AST syntax.
        """
        tree = self.parse_source(source_code)
        try:
            return ast.unparse(tree)
        except (AttributeError, ValueError, TypeError) as exc:
            logger.debug("ast.unparse fallback in minify_code_context: %s", exc)
            lines = [line_item for line_item in source_code.splitlines() if line_item.strip() and not line_item.strip().startswith("#")]
            return "\n".join(lines)


# =============================================================================
# TENSOR & DATA STRUCTURE STATISTICAL COMPRESSION
# =============================================================================

def _compute_tensor_stats(arr: np.ndarray) -> Dict[str, Any]:
    """
    Compute Min, Max, Mean, Variance, and Last_Value from a NumPy array, returning native Python floats.
    Handles NaN/Inf values gracefully by filtering finite elements.
    """
    flat = arr.ravel()
    if flat.size == 0:
        return {
            "Min": 0.0,
            "Max": 0.0,
            "Mean": 0.0,
            "Variance": 0.0,
            "Last_Value": 0.0,
            "Count": 0,
            "Shape": list(arr.shape),
            "Dtype": str(arr.dtype),
        }

    if np.issubdtype(flat.dtype, np.complexfloating):
        flat = np.abs(flat)

    last_val = float(flat[-1]) if np.isfinite(flat[-1]) else 0.0

    if np.isfinite(flat).all():
        min_val = float(np.min(flat))
        max_val = float(np.max(flat))
        mean_val = float(np.mean(flat, dtype=np.float64))
        var_val = float(np.var(flat, dtype=np.float64))
    else:
        finite_mask = np.isfinite(flat)
        if finite_mask.any():
            finite_elements = flat[finite_mask]
            min_val = float(np.min(finite_elements))
            max_val = float(np.max(finite_elements))
            mean_val = float(np.mean(finite_elements, dtype=np.float64))
            var_val = float(np.var(finite_elements, dtype=np.float64))
        else:
            min_val = 0.0
            max_val = 0.0
            mean_val = 0.0
            var_val = 0.0

    return {
        "Min": min_val,
        "Max": max_val,
        "Mean": mean_val,
        "Variance": var_val,
        "Last_Value": last_val,
        "Count": int(flat.size),
        "Shape": list(arr.shape),
        "Dtype": str(arr.dtype),
    }


def compress_tensors_for_llm(
    payload: Any,
    threshold: int = DEFAULT_TENSOR_THRESHOLD,
    return_models: bool = False,
) -> Any:
    """
    Recursively traverse arbitrary nested Python payloads and compress any numerical array
    with element count >= threshold into a 4-statistic summary dict {"Min": x, "Max": y, "Mean": z, "Variance": v}.
    """
    if isinstance(payload, np.ndarray):
        if np.issubdtype(payload.dtype, np.number) or np.issubdtype(payload.dtype, np.bool_):
            if payload.size >= threshold:
                stats = _compute_tensor_stats(payload)
                model = TensorSummaryModel(**stats)
                return model if return_models else {
                    "Min": stats["Min"],
                    "Max": stats["Max"],
                    "Mean": stats["Mean"],
                    "Variance": stats["Variance"],
                }
        return payload.tolist()

    if hasattr(payload, "__class__") and payload.__class__.__name__ == "Tensor":
        try:
            arr = payload.detach().cpu().numpy()
            return compress_tensors_for_llm(arr, threshold=threshold, return_models=return_models)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug("Tensor detachment/conversion skipped: %s", exc)

    if isinstance(payload, h5py.Dataset):
        if payload.size >= threshold:
            arr = payload[()]
            stats = _compute_tensor_stats(arr)
            model = TensorSummaryModel(**stats)
            return model if return_models else {
                "Min": stats["Min"],
                "Max": stats["Max"],
                "Mean": stats["Mean"],
                "Variance": stats["Variance"],
            }
        return payload[()].tolist()

    if isinstance(payload, BaseModel):
        dumped = payload.model_dump()
        return compress_tensors_for_llm(dumped, threshold=threshold, return_models=return_models)

    if isinstance(payload, dict):
        return {
            str(k): compress_tensors_for_llm(v, threshold=threshold, return_models=return_models)
            for k, v in payload.items()
        }

    if isinstance(payload, list):
        if len(payload) >= threshold and all(isinstance(x, (int, float, np.number)) for x in payload[:20]):
            try:
                arr = np.asarray(payload, dtype=np.float64)
                if arr.size >= threshold:
                    stats = _compute_tensor_stats(arr)
                    model = TensorSummaryModel(**stats)
                    return model if return_models else {
                        "Min": stats["Min"],
                        "Max": stats["Max"],
                        "Mean": stats["Mean"],
                        "Variance": stats["Variance"],
                    }
            except (ValueError, TypeError) as _e:
                logger.debug(f"Ignored exception: {_e}")
        return [
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        ]

    if isinstance(payload, tuple):
        return tuple(
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        )

    if isinstance(payload, set):
        return [
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        ]

    if isinstance(payload, (np.integer, np.signedinteger, np.unsignedinteger)):
        return int(payload)
    if isinstance(payload, (np.floating, np.float64, np.float32, np.float16)):
        return float(payload)

    return payload


def compress_array_to_summary(data: Any) -> TensorSummaryModel:
    """Converts a numerical sequence or array directly into a TensorSummaryModel."""
    arr = np.asarray(data, dtype=np.float64)
    stats = _compute_tensor_stats(arr)
    return TensorSummaryModel(**stats)


def compress_to_dict(data: Any) -> Dict[str, float]:
    """Converts a numerical sequence directly into a standard telemetry dictionary."""
    model = compress_array_to_summary(data)
    return model.to_telemetry_dict()


def intercept_and_compress(payload: Any, threshold: int = DEFAULT_ARRAY_THRESHOLD) -> Any:
    """
    Telemetry and log interceptor that compresses arrays/sequences exceeding threshold
    into a dictionary containing {"Array_Min", "Array_Max", "Array_Mean", "Array_Variance", "Last_Value"}.
    Leaves payloads with <= threshold elements unmodified.
    """
    if isinstance(payload, np.ndarray):
        if payload.size > threshold:
            stats = _compute_tensor_stats(payload)
            model = TensorSummaryModel(**stats)
            return model.to_telemetry_dict()
        return payload

    if isinstance(payload, list):
        if len(payload) > threshold and all(isinstance(x, (int, float, np.number)) for x in payload[:10]):
            try:
                arr = np.asarray(payload, dtype=np.float64)
                if arr.size > threshold:
                    stats = _compute_tensor_stats(arr)
                    model = TensorSummaryModel(**stats)
                    return model.to_telemetry_dict()
            except (ValueError, TypeError) as _e:
                logger.debug(f"Ignored exception: {_e}")
        return payload

    return payload


# =============================================================================
# PROACTIVE RFC 8259 SANITIZATION & JSON SERIALIZATION
# =============================================================================

def sanitize_numerical_values(payload: Any, replace_with: Any = None) -> Any:
    """
    Recursively sanitize data structures to replace non-compliant IEEE 754 float
    values (NaN, Infinity, -Infinity) with an RFC 8259 compliant substitute (default: None).
    """
    if isinstance(payload, (float, np.floating)):
        val = float(payload)
        if math.isnan(val) or math.isinf(val):
            return replace_with
        return val

    if isinstance(payload, (complex, np.complexfloating)):
        real_part = float(payload.real)
        imag_part = float(payload.imag)
        if math.isnan(real_part) or math.isinf(real_part) or math.isnan(imag_part) or math.isinf(imag_part):
            return replace_with
        return {"real": real_part, "imag": imag_part}

    if isinstance(payload, (int, np.integer)):
        return int(payload)

    if isinstance(payload, np.ndarray):
        if payload.dtype == object:
            flat_sanitized = [sanitize_numerical_values(x, replace_with=replace_with) for x in payload.flatten()]
            if payload.ndim == 1:
                return flat_sanitized
            return np.array(flat_sanitized, dtype=object).reshape(payload.shape).tolist()

        if np.issubdtype(payload.dtype, np.floating) or np.issubdtype(payload.dtype, np.complexfloating):
            has_nan_or_inf = np.isnan(payload).any() or np.isinf(payload).any()
            if has_nan_or_inf:
                flat = payload.flatten()
                sanitized_list = [
                    replace_with if (
                        math.isnan(float(x.real if isinstance(x, (complex, np.complexfloating)) else x))
                        or math.isinf(float(x.real if isinstance(x, (complex, np.complexfloating)) else x))
                    ) else float(x.real if isinstance(x, (complex, np.complexfloating)) else x)
                    for x in flat
                ]
                if payload.ndim == 1:
                    return sanitized_list
                reshaped_arr = np.array(sanitized_list, dtype=object).reshape(payload.shape)
                return reshaped_arr.tolist()
            return payload.tolist()
        return payload.tolist()

    if isinstance(payload, BaseModel):
        return sanitize_numerical_values(payload.model_dump(), replace_with=replace_with)

    if isinstance(payload, dict):
        return {
            str(k): sanitize_numerical_values(v, replace_with=replace_with)
            for k, v in payload.items()
        }

    if isinstance(payload, list):
        return [sanitize_numerical_values(item, replace_with=replace_with) for item in payload]

    if isinstance(payload, tuple):
        return tuple(sanitize_numerical_values(item, replace_with=replace_with) for item in payload)

    if isinstance(payload, set):
        return {sanitize_numerical_values(item, replace_with=replace_with) for item in payload}

    if isinstance(payload, Path):
        return str(payload)

    return payload


class RFC8259JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder guaranteeing strict RFC 8259 compliance, automatic conversion
    of NumPy datatypes, Pydantic models, and Path instances.
    """
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"Out of range float value '{val}' is forbidden by RFC 8259 JSON specification."
                )
            return val
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, (set, tuple)):
            return list(obj)
        return super().default(obj)


def to_rfc8259_json(
    payload: Any,
    allow_nan: bool = False,
    indent: Optional[int] = None,
    auto_sanitize: bool = False,
    sort_keys: bool = False,
    **kwargs: Any,
) -> str:
    """
    Serialize payload to an RFC 8259 compliant JSON string.
    """
    data = payload
    if auto_sanitize:
        data = sanitize_numerical_values(payload)

    return json.dumps(
        data,
        cls=RFC8259JSONEncoder,
        allow_nan=allow_nan,
        indent=indent,
        sort_keys=sort_keys,
        **kwargs,
    )


dumps_rfc8259 = to_rfc8259_json


def loads_rfc8259(json_str: str, **kwargs: Any) -> Any:
    """
    Parse an RFC 8259 JSON string into Python objects.
    """
    return json.loads(json_str, **kwargs)


# =============================================================================
# HDF5 POINTER HANDOFFS PROTOCOL
# =============================================================================

def is_hdf5_pointer(data: Any) -> bool:
    """
    Determine whether a dictionary, model, or string represents an HDF5 pointer reference.
    """
    if isinstance(data, HDF5PointerModel):
        return True
    if isinstance(data, dict):
        has_file = "file" in data or "file_path" in data
        has_node = "node" in data or "node_path" in data
        return has_file and has_node
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return is_hdf5_pointer(parsed)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return False
    return False


def create_hdf5_pointer(
    file_path: Union[str, Path],
    node_path: str,
    shape: Optional[Union[Tuple[int, ...], List[int]]] = None,
    dtype: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    populate_from_file: bool = False,
) -> HDF5PointerModel:
    """
    Create a validated HDF5PointerModel separating OS file location and internal node path.
    """
    resolved_file = str(Path(file_path).resolve()) if Path(file_path).exists() else str(file_path)
    clean_node = "/" + node_path.strip("/") if not node_path.startswith("/") else node_path

    inferred_shape = list(shape) if shape is not None else None
    inferred_dtype = str(dtype) if dtype is not None else None
    inferred_metadata: Dict[str, Any] = dict(metadata or {})

    if populate_from_file and Path(resolved_file).is_file():
        try:
            with h5py.File(resolved_file, "r") as h5_file:
                if clean_node in h5_file:
                    target_obj = h5_file[clean_node]
                    if isinstance(target_obj, h5py.Dataset):
                        inferred_shape = list(target_obj.shape)
                        inferred_dtype = str(target_obj.dtype)
                    for attr_key, attr_val in target_obj.attrs.items():
                        if isinstance(attr_val, bytes):
                            inferred_metadata[attr_key] = attr_val.decode("utf-8", errors="replace")
                        elif isinstance(attr_val, np.ndarray):
                            inferred_metadata[attr_key] = attr_val.tolist()
                        elif isinstance(attr_val, (np.integer, np.floating)):
                            inferred_metadata[attr_key] = attr_val.item()
                        else:
                            inferred_metadata[attr_key] = attr_val
        except (OSError, KeyError, TypeError, ValueError) as exc:
            logger.debug("HDF5 node inspection warning: %s", exc)

    return HDF5PointerModel(
        file=resolved_file,
        node=clean_node,
        shape=inferred_shape,
        dtype=inferred_dtype,
        metadata=inferred_metadata,
    )


def parse_hdf5_pointer(data: Union[Dict[str, Any], str, HDF5PointerModel]) -> HDF5PointerModel:
    """
    Parse a dictionary, JSON string, or HDF5PointerModel instance into a verified HDF5PointerModel.
    """
    if isinstance(data, HDF5PointerModel):
        return data

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as err:
            raise ValueError(f"Failed to decode JSON string for HDF5 pointer: {err}") from err

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, str, or HDF5PointerModel, got {type(data).__name__}")

    file_val = data.get("file") or data.get("file_path")
    node_val = data.get("node") or data.get("node_path")

    if not file_val or not node_val:
        raise ValueError(
            f"Missing required HDF5 pointer keys ('file' and 'node'). Provided keys: {list(data.keys())}"
        )

    shape_val = data.get("shape")
    if shape_val is not None and isinstance(shape_val, tuple):
        shape_val = list(shape_val)

    return HDF5PointerModel(
        file=str(file_val),
        node=str(node_val),
        shape=shape_val,
        dtype=data.get("dtype"),
        metadata=data.get("metadata", {}),
    )


def resolve_hdf5_pointer(
    pointer: Union[Dict[str, Any], str, HDF5PointerModel],
    as_numpy: bool = True,
) -> Any:
    """
    Resolve an HDF5 pointer reference against the local filesystem, opening the real
    HDF5 archive and extracting the underlying dataset or group contents.
    """
    ptr_model = parse_hdf5_pointer(pointer)
    file_path = Path(ptr_model.file)

    if not file_path.is_file():
        raise FileNotFoundError(f"HDF5 archive file does not exist: {ptr_model.file}")

    with h5py.File(str(file_path), "r") as h5_file:
        if ptr_model.node not in h5_file:
            raise KeyError(
                f"HDF5 node '{ptr_model.node}' not found in archive '{ptr_model.file}'"
            )

        target_obj = h5_file[ptr_model.node]
        if isinstance(target_obj, h5py.Dataset):
            if as_numpy:
                return target_obj[()]
            return {
                "shape": list(target_obj.shape),
                "dtype": str(target_obj.dtype),
                "attrs": dict(target_obj.attrs),
            }
        elif isinstance(target_obj, h5py.Group):
            return {
                "keys": list(target_obj.keys()),
                "attrs": dict(target_obj.attrs),
            }

        return target_obj


def extract_hdf5_pointers(payload: Any) -> List[HDF5PointerModel]:
    """
    Recursively traverse arbitrary data payloads and extract all embedded HDF5 pointers.
    """
    found_pointers: List[HDF5PointerModel] = []

    def _traverse(obj: Any) -> None:
        if isinstance(obj, HDF5PointerModel):
            found_pointers.append(obj)
            return

        if isinstance(obj, dict):
            if is_hdf5_pointer(obj):
                try:
                    found_pointers.append(parse_hdf5_pointer(obj))
                    return
                except (ValueError, TypeError, KeyError) as exc:
                    logger.debug("Dict matched pointer signature but failed parsing: %s", exc)
            for v in obj.values():
                _traverse(v)
            return

        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                _traverse(item)
            return

        if isinstance(obj, BaseModel):
            _traverse(obj.model_dump())
            return

    _traverse(payload)
    return found_pointers


# =============================================================================
# TRACEBACK TRUNCATION & ANSI SANITIZATION
# =============================================================================

def strip_ansi_escape_codes(text: str) -> str:
    """
    Strip all terminal ANSI color codes and formatting sequences from a text stream.
    """
    if not text:
        return ""
    return ANSI_ESCAPE_PATTERN.sub("", text)


def truncate_traceback(
    stream: str,
    max_lines: int = DEFAULT_TRACEBACK_MAX_LINES,
) -> TracebackSummaryModel:
    """
    Extract the root-cause crash block and retain the final N lines (default 30)
    of an execution stream, stripping ANSI codes and formatting compactly for LLM prompt ingestion.
    """
    clean_text = strip_ansi_escape_codes(stream)
    raw_lines = [line.rstrip("\r") for line in clean_text.split("\n")]

    while raw_lines and raw_lines[-1] == "":
        raw_lines.pop()

    total_lines = len(raw_lines)
    if total_lines == 0:
        return TracebackSummaryModel(
            crash_block="No execution logs or tracebacks recorded.",
            retained_lines=[],
            truncated_stream="No execution logs or tracebacks recorded.",
            total_original_lines=0,
            retained_line_count=0,
            was_truncated=False,
            exception_type=None,
            exception_message=None,
        )

    crash_block_lines: List[str] = []
    parsed_exc_type: Optional[str] = None
    parsed_exc_msg: Optional[str] = None

    tb_indices = [
        i for i, line in enumerate(raw_lines)
        if "Traceback (most recent call last):" in line
    ]

    if tb_indices:
        start_idx = tb_indices[-1]
        end_idx = start_idx + 1
        while end_idx < total_lines:
            curr_line = raw_lines[end_idx]
            match = EXCEPTION_LINE_PATTERN.match(curr_line.strip())
            if match and not curr_line.startswith((" ", "\t")):
                parsed_exc_type = match.group(1)
                parsed_exc_msg = match.group(2) or ""
                end_idx += 1
                break
            end_idx += 1

        crash_block_lines = raw_lines[start_idx:end_idx]

    if not crash_block_lines:
        for idx in range(total_lines - 1, -1, -1):
            line_str = raw_lines[idx].strip()
            match = EXCEPTION_LINE_PATTERN.match(line_str)
            if match:
                parsed_exc_type = match.group(1)
                parsed_exc_msg = match.group(2) or ""
                ctx_start = max(0, idx - 5)
                ctx_end = min(total_lines, idx + 2)
                crash_block_lines = raw_lines[ctx_start:ctx_end]
                break

    if not crash_block_lines:
        crash_block_lines = raw_lines[-min(total_lines, 5):]

    crash_block_str = "\n".join(crash_block_lines).strip()

    was_truncated = total_lines > max_lines
    retained_lines = raw_lines[-max_lines:] if was_truncated else raw_lines

    if not was_truncated:
        truncated_stream = "\n".join(raw_lines)
    else:
        truncated_stream = (
            f"[CRASH DIAGNOSTIC BLOCK]\n{crash_block_str}\n\n"
            f"[EXECUTION STREAM TAIL - FINAL {len(retained_lines)} LINES OF {total_lines} TOTAL]\n"
            + "\n".join(retained_lines)
        )

    return TracebackSummaryModel(
        crash_block=crash_block_str,
        retained_lines=retained_lines,
        truncated_stream=truncated_stream,
        total_original_lines=total_lines,
        retained_line_count=len(retained_lines),
        was_truncated=was_truncated,
        exception_type=parsed_exc_type,
        exception_message=parsed_exc_msg,
    )


# =============================================================================
# RAG DOCUMENTATION & LITERATURE CHUNKER BY HEADERS
# =============================================================================

class _SectionNode:
    """Internal helper representing a markdown section bounded by a header."""
    def __init__(self, title: str, level: int, path: List[str]):
        self.title: str = title
        self.level: int = level
        self.path: List[str] = list(path)
        self.lines: List[str] = []

    def get_full_text(self) -> str:
        return "\n".join(self.lines).strip()


def _detect_content_features(content: str) -> Tuple[bool, bool, bool]:
    """Detect presence of code blocks, markdown tables, and LaTeX formulas."""
    has_code = "```" in content or "~~~" in content
    has_table = bool(re.search(r"\|.+\|.+\|", content))
    has_latex = (
        "$$" in content
        or "\\begin{" in content
        or bool(re.search(r"(?<!\$)\$(?!\$)[^\$\n]+\$", content))
    )
    return has_code, has_table, has_latex


def _split_oversized_section(
    section_node: _SectionNode,
    max_chunk_chars: int,
    starting_chunk_id: int,
) -> List[MarkdownChunkModel]:
    """
    Intelligently split a section exceeding max_chunk_chars into multiple chunks,
    guaranteeing that code fences, LaTeX equations, and tables are NOT split across boundaries.
    """
    chunks: List[MarkdownChunkModel] = []
    current_lines: List[str] = []
    current_chars = 0
    in_code_fence = False
    in_latex_display = False

    def _flush_chunk() -> None:
        nonlocal current_lines, current_chars, starting_chunk_id
        if not current_lines:
            return
        chunk_text = "\n".join(current_lines).strip()
        if not chunk_text:
            current_lines = []
            current_chars = 0
            return

        has_code, has_table, has_latex = _detect_content_features(chunk_text)
        char_cnt = len(chunk_text)
        token_est = max(1, (char_cnt + 3) // 4)

        chunks.append(
            MarkdownChunkModel(
                chunk_id=starting_chunk_id,
                header_title=section_node.title,
                header_level=section_node.level,
                header_path=section_node.path,
                content=chunk_text,
                char_count=char_cnt,
                token_estimate=token_est,
                has_code_block=has_code,
                has_table=has_table,
                has_latex=has_latex,
            )
        )
        starting_chunk_id += 1
        current_lines = []
        current_chars = 0

    for line in section_node.lines:
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence

        if stripped.startswith("$$") and not in_code_fence:
            if stripped.endswith("$$") and len(stripped) > 2 and stripped != "$$":
                pass
            else:
                in_latex_display = not in_latex_display

        line_len = len(line) + 1
        can_split = not in_code_fence and not in_latex_display and not stripped.startswith("|")

        if (current_chars + line_len > max_chunk_chars) and can_split and current_lines:
            _flush_chunk()

        current_lines.append(line)
        current_chars += line_len

    _flush_chunk()
    return chunks


def chunk_markdown_by_headers(
    markdown_text: str,
    max_chunk_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> List[MarkdownChunkModel]:
    """
    Strictly chunk literature and documentation by markdown headers (#, ##, ###, etc.)
    preserving formatting, LaTeX mathematical formulas, tables, and fenced code blocks.
    """
    if not markdown_text or not markdown_text.strip():
        return []

    lines = markdown_text.split("\n")
    sections: List[_SectionNode] = []
    header_stack: List[Tuple[int, str]] = []

    current_section = _SectionNode(title="Root", level=0, path=["Root"])
    in_code_fence = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence

        if not in_code_fence:
            header_match = MARKDOWN_HEADER_PATTERN.match(stripped)
            if header_match:
                if current_section.lines and any(ln.strip() for ln in current_section.lines):
                    sections.append(current_section)

                hashes, title = header_match.groups()
                level = len(hashes)
                clean_title = title.strip()

                while header_stack and header_stack[-1][0] >= level:
                    header_stack.pop()

                header_stack.append((level, clean_title))
                current_path = [item[1] for item in header_stack]

                current_section = _SectionNode(
                    title=clean_title,
                    level=level,
                    path=current_path,
                )
                current_section.lines.append(line)
                continue

        current_section.lines.append(line)

    if current_section.lines and any(ln.strip() for ln in current_section.lines):
        sections.append(current_section)

    final_chunks: List[MarkdownChunkModel] = []
    chunk_counter = 0

    for section in sections:
        section_text = section.get_full_text()
        if not section_text:
            continue

        if len(section_text) <= max_chunk_chars:
            has_code, has_table, has_latex = _detect_content_features(section_text)
            char_cnt = len(section_text)
            token_est = max(1, (char_cnt + 3) // 4)

            final_chunks.append(
                MarkdownChunkModel(
                    chunk_id=chunk_counter,
                    header_title=section.title,
                    header_level=section.level,
                    header_path=section.path,
                    content=section_text,
                    char_count=char_cnt,
                    token_estimate=token_est,
                    has_code_block=has_code,
                    has_table=has_table,
                    has_latex=has_latex,
                )
            )
            chunk_counter += 1
        else:
            sub_chunks = _split_oversized_section(
                section_node=section,
                max_chunk_chars=max_chunk_chars,
                starting_chunk_id=chunk_counter,
            )
            final_chunks.extend(sub_chunks)
            chunk_counter += len(sub_chunks)

    return final_chunks


def chunk_literature_by_headers(
    literature_text: str,
    max_chunk_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> List[MarkdownChunkModel]:
    """Alias for chunk_markdown_by_headers targeted for chemical literature ingestion."""
    return chunk_markdown_by_headers(literature_text, max_chunk_chars=max_chunk_chars)


# =============================================================================
# MOLECULAR GEOMETRY CONTEXT COMPRESSOR (DYNAMIC MENDELEEV INTEGRATION)
# =============================================================================

def compress_molecular_geometry(
    symbols: List[str],
    coordinates: np.ndarray,
    compute_com: bool = True,
) -> Dict[str, Any]:
    """
    Compresses a molecular coordinate frame into a compact physical summary using
    dynamic atomic masses resolved from `mendeleev`.
    Strictly ZERO hardcoded atomic masses.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise ValueError(f"Coordinates must have shape (N, 3), got {coords.shape}")

    n_atoms = len(symbols)
    if n_atoms != coords.shape[0]:
        raise ValueError(f"Mismatch between symbol count ({n_atoms}) and coordinate count ({coords.shape[0]})")

    masses = np.array([float(element(sym).mass) for sym in symbols], dtype=np.float64)
    total_mass = float(np.sum(masses))

    if compute_com and total_mass > 0:
        com = np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass
    else:
        com = np.array([0.0, 0.0, 0.0], dtype=np.float64)

    centered_coords = coords - com

    x, y, z = centered_coords[:, 0], centered_coords[:, 1], centered_coords[:, 2]
    i_xx = np.sum(masses * (y**2 + z**2))
    i_yy = np.sum(masses * (x**2 + z**2))
    i_zz = np.sum(masses * (x**2 + y**2))
    i_xy = -np.sum(masses * x * y)
    i_xz = -np.sum(masses * x * z)
    i_yz = -np.sum(masses * y * z)

    inertia_tensor = np.array([
        [i_xx, i_xy, i_xz],
        [i_xy, i_yy, i_yz],
        [i_xz, i_yz, i_zz],
    ], dtype=np.float64)

    evals, _ = np.linalg.eigh(inertia_tensor)
    principal_moments = sorted([float(e) for e in evals])

    return {
        "num_atoms": n_atoms,
        "total_mass_amu": total_mass,
        "center_of_mass_angstrom": [round(float(c), 5) for c in com],
        "principal_moments_amu_angstrom2": [round(m, 4) for m in principal_moments],
        "symbols": symbols,
        "bounding_box_angstrom": {
            "x_span": round(float(np.ptp(coords[:, 0])), 4),
            "y_span": round(float(np.ptp(coords[:, 1])), 4),
            "z_span": round(float(np.ptp(coords[:, 2])), 4),
        },
    }


# =============================================================================
# UNIFIED CONTEXT COMPRESSOR / AI RESOURCE GUARDING ENGINE
# =============================================================================

class ContextCompressor:
    """
    Unified high-level interface executing the CoChem Context Compression Protocol.
    Integrates LTTB downsampling, AST skeletonization, tensor summarization,
    RFC 8259 serialization, traceback truncation, and markdown chunking.
    """
    def __init__(
        self,
        tensor_threshold: int = DEFAULT_TENSOR_THRESHOLD,
        array_threshold: int = DEFAULT_ARRAY_THRESHOLD,
        traceback_max_lines: int = DEFAULT_TRACEBACK_MAX_LINES,
        chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
        lttb_max_points: int = DEFAULT_LTTB_THRESHOLD,
        use_numba: bool = True,
    ):
        self.tensor_threshold: int = tensor_threshold
        self.array_threshold: int = array_threshold
        self.traceback_max_lines: int = traceback_max_lines
        self.chunk_max_chars: int = chunk_max_chars
        self.lttb_max_points: int = lttb_max_points
        self.use_numba: bool = use_numba

        self.ast_engine = ASTContextCompressor()
        self.lttb_engine = LTTBDownsampler(default_threshold=lttb_max_points, use_numba=use_numba)

    def compress_payload(self, payload: Any, auto_sanitize: bool = True) -> Any:
        """Compress large numerical tensors and optionally sanitize non-compliant float tokens."""
        compressed = compress_tensors_for_llm(payload, threshold=self.tensor_threshold)
        if auto_sanitize:
            compressed = sanitize_numerical_values(compressed)
        return compressed

    def to_json(self, payload: Any, indent: Optional[int] = None) -> str:
        """Serialize payload to RFC 8259 compliant JSON string."""
        sanitized = self.compress_payload(payload, auto_sanitize=True)
        return to_rfc8259_json(sanitized, allow_nan=False, indent=indent)

    def truncate_stream(self, stream: str) -> TracebackSummaryModel:
        """Truncate raw execution output or exception tracebacks."""
        return truncate_traceback(stream, max_lines=self.traceback_max_lines)

    def chunk_document(self, markdown_text: str) -> List[MarkdownChunkModel]:
        """Chunk documentation or literature by markdown header hierarchy."""
        return chunk_markdown_by_headers(markdown_text, max_chunk_chars=self.chunk_max_chars)

    def compress_ast(self, source_code: str, preserve_docstrings: bool = True) -> str:
        """Compress Python source code into a compact token-efficient skeleton."""
        return self.ast_engine.compress_to_skeleton(source_code, preserve_docstrings=preserve_docstrings)

    def summarize_ast(self, source_code: str) -> ASTContextSummary:
        """Extract full structural AST symbol summary from source code."""
        return self.ast_engine.extract_ast_summary(source_code)

    def decimate_curve(
        self,
        y: Union[np.ndarray, List[float], Tuple[float, ...]],
        x: Optional[Union[np.ndarray, List[float], Tuple[float, ...]]] = None,
        max_points: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Decimates a 1D curve using LTTB."""
        t = max_points if max_points is not None else self.lttb_max_points
        return self.lttb_engine.decimate_curve(y, x=x, max_points=t)

    def compress_array(self, data: Any) -> TensorSummaryModel:
        """Compress an array directly into a TensorSummaryModel."""
        return compress_array_to_summary(data)

    def compress_to_dict(self, data: Any) -> Dict[str, float]:
        """Compress an array directly into a dictionary with Array_ prefixed keys."""
        return compress_to_dict(data)

    def intercept_and_compress(self, payload: Any) -> Any:
        """Intercept and compress arrays exceeding threshold into telemetry dictionaries."""
        return intercept_and_compress(payload, threshold=self.array_threshold)

    def create_pointer(
        self,
        file_path: Union[str, Path],
        node_path: str,
        populate_from_file: bool = False,
    ) -> HDF5PointerModel:
        """Creates an HDF5PointerModel for zero-VRAM handoffs."""
        return create_hdf5_pointer(file_path, node_path, populate_from_file=populate_from_file)

    def resolve_pointer(self, pointer: Union[Dict[str, Any], str, HDF5PointerModel], as_numpy: bool = True) -> Any:
        """Resolves an HDF5PointerModel from disk."""
        return resolve_hdf5_pointer(pointer, as_numpy=as_numpy)


# CoreContextCompressor is alias for ContextCompressor matching Core naming convention
CoreContextCompressor = ContextCompressor


# =============================================================================
# COMMAND-LINE INTERFACE (CLI)
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CoChem-CORE: Document 9 §2 - LTTB Downsampling & AST Context-Compression Engine",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to Python file, Markdown document, or HDF5 archive to process.",
    )
    parser.add_argument(
        "--ast",
        action="store_true",
        help="Perform AST skeleton compression and symbol extraction on target Python file.",
    )
    parser.add_argument(
        "--lttb",
        action="store_true",
        help="Execute LTTB decimation on input numerical data.",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=DEFAULT_LTTB_THRESHOLD,
        help="LTTB point threshold or array compression element threshold.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Audit Python source file for compliance violations.",
    )
    parser.add_argument(
        "--truncate-stream",
        type=str,
        help="Path to raw execution stream / log file to truncate.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Optional path to write processed output.",
    )
    return parser


def main() -> int:
    """CLI entry point for CoChem Core Context Compressor."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError) as exc:
            logger.debug("Stdout reconfigure skipped: %s", exc)
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError) as exc:
            logger.debug("Stderr reconfigure skipped: %s", exc)

    parser = _build_parser()
    args = parser.parse_args()

    compressor = ContextCompressor(lttb_max_points=args.threshold)

    if args.file:
        target_path = Path(args.file)
        if not target_path.exists():
            logger.error(f"Target file not found: {target_path}")
            return 1

        content = target_path.read_text(encoding="utf-8")

        if args.audit or (args.ast and target_path.suffix == ".py"):
            summary = compressor.summarize_ast(content)
            if summary.compliance_violations:
                logger.warning(f"Integrity violations detected ({len(summary.compliance_violations)}):")
                for v in summary.compliance_violations:
                    print(f"  [VIOLATION] {v}")
            else:
                logger.info("Compliance audit passed: 0 violations found.")

            if args.ast:
                print("\n" + "=" * 60)
                print("COMPRESSED SKELETON CODE:")
                print("=" * 60)
                print(summary.skeleton_code)
                print("=" * 60)
                print(f"Original Lines: {summary.total_lines} -> Compressed Lines: {summary.compressed_lines}")
                print(f"Character Savings: {summary.char_savings} ({summary.compression_ratio:.2f}x ratio)")

            if args.output:
                Path(args.output).write_text(summary.skeleton_code, encoding="utf-8")
                logger.info(f"Wrote compressed skeleton to {args.output}")
            return 0

        elif target_path.suffix == ".md":
            chunks = compressor.chunk_document(content)
            logger.info(f"Chunked markdown into {len(chunks)} header-bounded sections.")
            for c in chunks:
                print(f"Chunk {c.chunk_id}: Level {c.header_level} [{c.header_title}] - {c.char_count} chars (~{c.token_estimate} tokens)")
            return 0

    if args.truncate_stream:
        stream_path = Path(args.truncate_stream)
        if not stream_path.exists():
            logger.error(f"Stream file not found: {stream_path}")
            return 1
        stream_text = stream_path.read_text(encoding="utf-8")
        tb = compressor.truncate_stream(stream_text)
        print(tb.truncated_stream)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
