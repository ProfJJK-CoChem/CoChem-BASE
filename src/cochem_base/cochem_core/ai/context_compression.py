# cochem_canvas_target: cochem_core/ai/context_compression.py
"""
CoChem-BASE AI Integrations - Context Compression Protocol.
Strict Zero-Mock Mandate Compliance.

Protects LLM prompt windows from overflow by compressing large numerical arrays,
sanitizing non-RFC-8259 floating-point tokens (NaN/Inf), delegating massive tensors
to lightweight HDF5 pointer handoffs, truncating verbose execution tracebacks,
and chunking literature/documentation by markdown header hierarchy.

Core Capabilities:
1. Tensor Compression: Summarizes >=10,000 element NumPy arrays / PyTorch tensors
   into exact statistical dicts {"Min": x, "Max": y, "Mean": z, "Variance": v}.
2. RFC 8259 Sanitization: Proactively eliminates NaN and Infinity float values,
   enforcing allow_nan=False for standards-compliant JSON interchange.
3. HDF5 Pointer Handoffs: Replaces heavy tensor dumps with structured filesystem
   and internal node pointers {"file": ..., "node": ...}, resolvable on-demand via h5py.
4. Traceback Truncation: Strips ANSI codes, extracts root-cause crash blocks,
   and retains the final N lines (default 30) of execution streams.
5. Markdown RAG Chunker: Strictly parses literature and documentation across header
   hierarchies (#, ##, ###) while preserving code fences, LaTeX equations, and tables.
"""

from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import h5py
import numpy as np
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# CONSTANTS & REGEX DEFINITIONS
# =============================================================================

DEFAULT_TENSOR_THRESHOLD: int = 10000
DEFAULT_TRACEBACK_MAX_LINES: int = 30
DEFAULT_CHUNK_MAX_CHARS: int = 4000

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


# =============================================================================
# TYPED DATA MODELS
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

    def to_dict(self) -> Dict[str, float]:
        """Convert model to standard dictionary."""
        return {
            "Min": float(self.Min),
            "Max": float(self.Max),
            "Mean": float(self.Mean),
            "Variance": float(self.Variance),
        }


class HDF5PointerModel(BaseModel):
    """
    Lightweight pointer reference separating OS filepath from internal HDF5 dataset node.
    Used for Zero-VRAM LLM prompt handoffs instead of massive serialized tensors.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file: str = Field(
        ...,
        description="Absolute or relative filesystem path to the HDF5 archive (.h5 / .hdf5)"
    )
    node: str = Field(
        ...,
        description="Internal HDF5 dataset or group hierarchy path (e.g. '/conformer_0/hessian')"
    )
    shape: Optional[List[int]] = Field(
        default=None,
        description="Dimension shape of the referenced HDF5 dataset"
    )
    dtype: Optional[str] = Field(
        default=None,
        description="Data type string of the referenced dataset (e.g. 'float64')"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Auxiliary metadata, units, and attributes extracted from the HDF5 node"
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
        except Exception:
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
        description="Extracted primary traceback block and root-cause exception"
    )
    retained_lines: List[str] = Field(
        ...,
        description="Exact retained trailing lines of the execution log stream"
    )
    truncated_stream: str = Field(
        ...,
        description="Clean formatted execution stream containing crash block and trailing context"
    )
    total_original_lines: int = Field(
        ...,
        ge=0,
        description="Total line count of the raw execution stream before truncation"
    )
    retained_line_count: int = Field(
        ...,
        ge=0,
        description="Number of tail lines retained in the output"
    )
    was_truncated: bool = Field(
        ...,
        description="Whether the original stream was truncated"
    )
    exception_type: Optional[str] = Field(
        default=None,
        description="Parsed exception class name (e.g. 'ZeroDivisionError', 'RuntimeError')"
    )
    exception_message: Optional[str] = Field(
        default=None,
        description="Parsed exception detail message"
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
        description="Sequential index of the documentation chunk"
    )
    header_title: str = Field(
        ...,
        description="Immediate section header title"
    )
    header_level: int = Field(
        ...,
        ge=0,
        le=6,
        description="Markdown header level (1 for #, 2 for ##, etc., 0 for headerless root)"
    )
    header_path: List[str] = Field(
        default_factory=list,
        description="Hierarchical breadcrumb list of enclosing parent headers"
    )
    content: str = Field(
        ...,
        description="Document chunk text preserving code blocks, LaTeX equations, and tables"
    )
    char_count: int = Field(
        ...,
        ge=0,
        description="Total character count of the chunk content"
    )
    token_estimate: int = Field(
        ...,
        ge=0,
        description="Estimated token count (approximately char_count / 4)"
    )
    has_code_block: bool = Field(
        default=False,
        description="Whether the chunk contains fenced code blocks"
    )
    has_table: bool = Field(
        default=False,
        description="Whether the chunk contains markdown tables"
    )
    has_latex: bool = Field(
        default=False,
        description="Whether the chunk contains inline or display LaTeX mathematical formulas"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk model to standard dictionary."""
        return self.model_dump()

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize chunk model to RFC 8259 JSON string."""
        return to_rfc8259_json(self.to_dict(), indent=indent)


# =============================================================================
# 1. TENSOR COMPRESSION FOR LLM CONTEXT
# =============================================================================

def _compute_tensor_stats(arr: np.ndarray) -> Dict[str, float]:
    """
    Compute Min, Max, Mean, and Variance from a NumPy array, returning native Python floats.
    Handles NaN/Inf values gracefully by filtering finite elements where appropriate.
    """
    flat = arr.ravel()
    if flat.size == 0:
        return {"Min": 0.0, "Max": 0.0, "Mean": 0.0, "Variance": 0.0}

    # Cast/accumulate in float64 to prevent float16/float32 sum-of-squares overflow
    if np.issubdtype(flat.dtype, np.complexfloating):
        flat = np.abs(flat)

    # If all finite, compute directly with standard numpy reductions in float64
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
            # Entire array is NaN / Inf
            min_val = 0.0
            max_val = 0.0
            mean_val = 0.0
            var_val = 0.0

    return {
        "Min": min_val,
        "Max": max_val,
        "Mean": mean_val,
        "Variance": var_val,
    }


def compress_tensors_for_llm(
    payload: Any,
    threshold: int = DEFAULT_TENSOR_THRESHOLD,
    return_models: bool = False,
) -> Any:
    """
    Recursively traverse arbitrary nested Python payloads (dicts, lists, tuples, sets,
    Pydantic models, NumPy arrays, PyTorch tensors) and compress any numerical array
    with element count >= threshold into a 4-statistic summary dict:
    {"Min": x, "Max": y, "Mean": z, "Variance": v}.

    Arrays with size < threshold are converted to standard Python nested lists for JSON safety.
    """
    # 1. Handle NumPy ndarray
    if isinstance(payload, np.ndarray):
        if np.issubdtype(payload.dtype, np.number) or np.issubdtype(payload.dtype, np.bool_):
            if payload.size >= threshold:
                stats = _compute_tensor_stats(payload)
                return TensorSummaryModel(**stats) if return_models else stats
        return payload.tolist()

    # 2. Handle PyTorch tensor if present
    if hasattr(payload, "__class__") and payload.__class__.__name__ == "Tensor":
        try:
            arr = payload.detach().cpu().numpy()
            return compress_tensors_for_llm(arr, threshold=threshold, return_models=return_models)
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    # 3. Handle HDF5 Dataset if passed directly
    if isinstance(payload, h5py.Dataset):
        if payload.size >= threshold:
            # Read into numpy array and summarize
            arr = payload[()]
            stats = _compute_tensor_stats(arr)
            return TensorSummaryModel(**stats) if return_models else stats
        return payload[()].tolist()

    # 4. Handle Pydantic BaseModel
    if isinstance(payload, BaseModel):
        dumped = payload.model_dump()
        return compress_tensors_for_llm(dumped, threshold=threshold, return_models=return_models)

    # 5. Handle Dictionary
    if isinstance(payload, dict):
        compressed_dict: Dict[str, Any] = {}
        for k, v in payload.items():
            compressed_dict[str(k)] = compress_tensors_for_llm(
                v, threshold=threshold, return_models=return_models
            )
        return compressed_dict

    # 6. Handle List
    if isinstance(payload, list):
        # Check if list is a large flat list of numbers
        if len(payload) >= threshold and all(isinstance(x, (int, float, np.number)) for x in payload[:20]):
            try:
                arr = np.asarray(payload, dtype=np.float64)
                if arr.size >= threshold:
                    stats = _compute_tensor_stats(arr)
                    return TensorSummaryModel(**stats) if return_models else stats
            except (ValueError, TypeError) as _e:
                logger.debug(f"Ignored exception: {_e}")
        return [
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        ]

    # 7. Handle Tuple
    if isinstance(payload, tuple):
        return tuple(
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        )

    # 8. Handle Set
    if isinstance(payload, set):
        return [
            compress_tensors_for_llm(elem, threshold=threshold, return_models=return_models)
            for elem in payload
        ]

    # 9. Handle scalar NumPy numbers
    if isinstance(payload, (np.integer, np.signedinteger, np.unsignedinteger)):
        return int(payload)
    if isinstance(payload, (np.floating, np.float64, np.float32, np.float16)):
        return float(payload)

    # 10. Default / scalar returns
    return payload


# =============================================================================
# 2. PROACTIVE RFC 8259 SANITIZATION & JSON SERIALIZATION
# =============================================================================

def sanitize_numerical_values(payload: Any, replace_with: Any = None) -> Any:
    """
    Recursively sanitize data structures to replace non-compliant IEEE 754 float
    values (NaN, Infinity, -Infinity) with an RFC 8259 compliant substitute (default: None).

    Ensures zero ValueError exceptions during subsequent strict JSON serialization.
    """
    # 1. Single Python float / NumPy float
    if isinstance(payload, (float, np.floating)):
        val = float(payload)
        if math.isnan(val) or math.isinf(val):
            return replace_with
        return val

    # Complex numbers
    if isinstance(payload, (complex, np.complexfloating)):
        real_part = float(payload.real)
        imag_part = float(payload.imag)
        if math.isnan(real_part) or math.isinf(real_part) or math.isnan(imag_part) or math.isinf(imag_part):
            return replace_with
        return {"real": real_part, "imag": imag_part}

    # 2. Single Python int / NumPy int
    if isinstance(payload, (int, np.integer)):
        return int(payload)

    # 3. NumPy ndarray
    if isinstance(payload, np.ndarray):
        if payload.dtype == object:
            flat_sanitized = [sanitize_numerical_values(x, replace_with=replace_with) for x in payload.flatten()]
            if payload.ndim == 1:
                return flat_sanitized
            return np.array(flat_sanitized, dtype=object).reshape(payload.shape).tolist()

        if np.issubdtype(payload.dtype, np.floating) or np.issubdtype(payload.dtype, np.complexfloating):
            # Check if any NaN or Inf exists
            has_nan_or_inf = np.isnan(payload).any() or np.isinf(payload).any()
            if has_nan_or_inf:
                # Convert array elements into sanitized Python list
                flat = payload.flatten()
                sanitized_list = [
                    replace_with if (
                        math.isnan(float(x.real if isinstance(x, (complex, np.complexfloating)) else x))
                        or math.isinf(float(x.real if isinstance(x, (complex, np.complexfloating)) else x))
                    ) else float(x.real if isinstance(x, (complex, np.complexfloating)) else x)
                    for x in flat
                ]
                # If 1D, return flat sanitized list; otherwise reshape list
                if payload.ndim == 1:
                    return sanitized_list
                # For multi-dimensional, rebuild nested list
                reshaped_arr = np.array(sanitized_list, dtype=object).reshape(payload.shape)
                return reshaped_arr.tolist()
            return payload.tolist()
        return payload.tolist()

    # 4. Pydantic BaseModel
    if isinstance(payload, BaseModel):
        return sanitize_numerical_values(payload.model_dump(), replace_with=replace_with)

    # 5. Dictionary
    if isinstance(payload, dict):
        return {
            str(k): sanitize_numerical_values(v, replace_with=replace_with)
            for k, v in payload.items()
        }

    # 6. List
    if isinstance(payload, list):
        return [
            sanitize_numerical_values(item, replace_with=replace_with)
            for item in payload
        ]

    # 7. Tuple
    if isinstance(payload, tuple):
        return tuple(
            sanitize_numerical_values(item, replace_with=replace_with)
            for item in payload
        )

    # 8. Set
    if isinstance(payload, set):
        return {
            sanitize_numerical_values(item, replace_with=replace_with)
            for item in payload
        }

    # 9. Path objects
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

    Setting allow_nan=False (default) strictly disallows NaN, Infinity, and -Infinity,
    raising ValueError if unsanitized out-of-range floats are supplied.
    If auto_sanitize=True, non-compliant floats are sanitized to null before serialization.
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


# Alias for standard python naming convention
dumps_rfc8259 = to_rfc8259_json


def loads_rfc8259(json_str: str, **kwargs: Any) -> Any:
    """
    Parse an RFC 8259 JSON string into Python objects.
    """
    return json.loads(json_str, **kwargs)


# =============================================================================
# 3. HDF5 POINTER HANDOFFS PROTOCOL
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
        except Exception:
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

    If populate_from_file=True and the file exists on disk, shape, dtype, and node attributes
    are automatically inspected and populated via h5py.
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
                    # Extract attributes
                    for attr_key, attr_val in target_obj.attrs.items():
                        if isinstance(attr_val, bytes):
                            inferred_metadata[attr_key] = attr_val.decode("utf-8", errors="replace")
                        elif isinstance(attr_val, np.ndarray):
                            inferred_metadata[attr_key] = attr_val.tolist()
                        elif isinstance(attr_val, (np.integer, np.floating)):
                            inferred_metadata[attr_key] = attr_val.item()
                        else:
                            inferred_metadata[attr_key] = attr_val
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

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
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
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
# 4. TRACEBACK TRUNCATION & ANSI SANITIZATION
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

    # Remove empty trailing lines if any
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

    # 1. Locate the Crash Block
    crash_block_lines: List[str] = []
    parsed_exc_type: Optional[str] = None
    parsed_exc_msg: Optional[str] = None

    # Search for standard Python "Traceback (most recent call last):"
    tb_indices = [
        i for i, line in enumerate(raw_lines)
        if "Traceback (most recent call last):" in line
    ]

    if tb_indices:
        # Take the final traceback
        start_idx = tb_indices[-1]
        # Collect lines until a non-indented error line or end of stream
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

    # If no standard traceback, search backwards for explicit error lines
    if not crash_block_lines:
        for idx in range(total_lines - 1, -1, -1):
            line_str = raw_lines[idx].strip()
            match = EXCEPTION_LINE_PATTERN.match(line_str)
            if match:
                parsed_exc_type = match.group(1)
                parsed_exc_msg = match.group(2) or ""
                # Retain context window around the error line
                ctx_start = max(0, idx - 5)
                ctx_end = min(total_lines, idx + 2)
                crash_block_lines = raw_lines[ctx_start:ctx_end]
                break

    # If still empty, use the final lines as crash diagnostic
    if not crash_block_lines:
        crash_block_lines = raw_lines[-min(total_lines, 5):]

    crash_block_str = "\n".join(crash_block_lines).strip()

    # 2. Compute Retained Tail Lines
    was_truncated = total_lines > max_lines
    retained_lines = raw_lines[-max_lines:] if was_truncated else raw_lines

    # 3. Format Combined Truncated Stream
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
# 5. RAG DOCUMENTATION CHUNKER BY HEADERS
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
    """
    Detect presence of code blocks, markdown tables, and LaTeX formulas.
    """
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

        # Track code block fence state
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence

        # Track LaTeX display math state
        if stripped.startswith("$$") and not in_code_fence:
            # Check if inline display on single line
            if stripped.endswith("$$") and len(stripped) > 2 and stripped != "$$":
                pass
            else:
                in_latex_display = not in_latex_display

        line_len = len(line) + 1  # include newline char
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

    Each chunk retains its breadcrumb hierarchy trail and structural metadata.
    """
    if not markdown_text or not markdown_text.strip():
        return []

    lines = markdown_text.split("\n")
    sections: List[_SectionNode] = []
    header_stack: List[Tuple[int, str]] = []

    # Create root section for text preceding the first markdown header
    current_section = _SectionNode(title="Root", level=0, path=["Root"])
    in_code_fence = False

    for line in lines:
        stripped = line.strip()

        # Track code block fences to prevent comment lines # from acting as headers
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence

        if not in_code_fence:
            header_match = MARKDOWN_HEADER_PATTERN.match(stripped)
            if header_match:
                # Save previous section if it had content
                if current_section.lines and any(l.strip() for l in current_section.lines):
                    sections.append(current_section)

                hashes, title = header_match.groups()
                level = len(hashes)
                clean_title = title.strip()

                # Maintain hierarchy breadcrumb stack
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

    # Append trailing section
    if current_section.lines and any(l.strip() for l in current_section.lines):
        sections.append(current_section)

    # Convert sections into MarkdownChunkModel list
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
            # Oversized section splitting
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
    """
    Alias for chunk_markdown_by_headers targeted for chemical literature and publication ingestion.
    """
    return chunk_markdown_by_headers(literature_text, max_chunk_chars=max_chunk_chars)


# =============================================================================
# 6. UNIFIED CONTEXT COMPRESSION PROTOCOL WRAPPER
# =============================================================================

class ContextCompressor:
    """
    Unified high-level interface executing the CoChem Context Compression Protocol.
    """
    def __init__(
        self,
        tensor_threshold: int = DEFAULT_TENSOR_THRESHOLD,
        traceback_max_lines: int = DEFAULT_TRACEBACK_MAX_LINES,
        chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    ):
        self.tensor_threshold: int = tensor_threshold
        self.traceback_max_lines: int = traceback_max_lines
        self.chunk_max_chars: int = chunk_max_chars

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
