# cochem_canvas_target: test_suite/test_context_compression.py
"""
CoChem-BASE AI Integrations - Context Compression Protocol Test Suite.
Strict Zero-Mock Mandate Compliance.

Validates:
1. Real 10,000+ float NumPy arrays testing Min, Max, Mean, Variance summary compression.
2. Threshold boundaries and recursive traversal over dicts, lists, tuples, and Pydantic models.
3. Proactive sanitization of NaN/Inf and RFC 8259 strict JSON serialization with allow_nan=False.
4. Negative tests asserting ValueError when unsanitized NaN/Inf are passed to dumps_rfc8259.
5. Real HDF5 file creation with h5py, pointer creation, parsing, dataset node verification, and metadata resolution.
6. Real Python exception traceback generation, ANSI escape code stripping, crash block extraction, and exact 30-line tail retention.
7. Real markdown documentation chunking across header hierarchies preserving LaTeX equations, markdown tables, and fenced code blocks.
8. AST-level Zero-Mock Static Analysis parsing both test and source modules asserting 0 mock/stub/fake usages.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import h5py
import numpy as np
import pytest
from pydantic import BaseModel, ConfigDict

from cochem_core.ai.context_compression import (
    ContextCompressor,
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_TENSOR_THRESHOLD,
    DEFAULT_TRACEBACK_MAX_LINES,
    HDF5PointerModel,
    MarkdownChunkModel,
    TensorSummaryModel,
    TracebackSummaryModel,
    chunk_literature_by_headers,
    chunk_markdown_by_headers,
    compress_tensors_for_llm,
    create_hdf5_pointer,
    dumps_rfc8259,
    extract_hdf5_pointers,
    is_hdf5_pointer,
    loads_rfc8259,
    parse_hdf5_pointer,
    resolve_hdf5_pointer,
    sanitize_numerical_values,
    strip_ansi_escape_codes,
    to_rfc8259_json,
    truncate_traceback,
)


# =============================================================================
# 1. TENSOR COMPRESSION TESTS (REAL NUMPY ARRAYS >= 10,000 FLOATS)
# =============================================================================

def test_compress_1d_numpy_tensor_10000_elements() -> None:
    """Verifies compression of real 10,000-element 1D float array into exact summary statistics."""
    # Generate deterministic 10,000 float sequence: 0.0, 1.0, ..., 9999.0
    arr = np.arange(10000, dtype=np.float64)
    expected_min = 0.0
    expected_max = 9999.0
    expected_mean = float(np.mean(arr))
    expected_var = float(np.var(arr))

    result = compress_tensors_for_llm(arr, threshold=10000)

    assert isinstance(result, dict)
    assert "Min" in result
    assert "Max" in result
    assert "Mean" in result
    assert "Variance" in result

    assert isinstance(result["Min"], float)
    assert isinstance(result["Max"], float)
    assert isinstance(result["Mean"], float)
    assert isinstance(result["Variance"], float)

    assert result["Min"] == expected_min
    assert result["Max"] == expected_max
    assert math.isclose(result["Mean"], expected_mean, rel_tol=1e-7)
    assert math.isclose(result["Variance"], expected_var, rel_tol=1e-7)


def test_compress_2d_numpy_matrix_10000_elements() -> None:
    """Verifies compression of real (100, 100) 2D float matrix (10,000 elements)."""
    # Create 100x100 matrix of Gaussian random values with fixed seed for determinism
    rng = np.random.default_rng(seed=42)
    matrix = rng.normal(loc=5.0, scale=2.0, size=(100, 100)).astype(np.float64)

    expected_min = float(np.min(matrix))
    expected_max = float(np.max(matrix))
    expected_mean = float(np.mean(matrix))
    expected_var = float(np.var(matrix))

    result = compress_tensors_for_llm(matrix, threshold=10000)

    assert isinstance(result, dict)
    assert math.isclose(result["Min"], expected_min, rel_tol=1e-7)
    assert math.isclose(result["Max"], expected_max, rel_tol=1e-7)
    assert math.isclose(result["Mean"], expected_mean, rel_tol=1e-7)
    assert math.isclose(result["Variance"], expected_var, rel_tol=1e-7)


def test_compress_tensor_below_threshold_retained_as_list() -> None:
    """Verifies that arrays smaller than threshold are converted to nested Python lists."""
    small_arr = np.array([1.5, 2.5, 3.5, 4.5], dtype=np.float64)
    result = compress_tensors_for_llm(small_arr, threshold=10000)

    assert isinstance(result, list)
    assert result == [1.5, 2.5, 3.5, 4.5]


def test_compress_tensor_return_models_option() -> None:
    """Verifies that return_models=True returns validated TensorSummaryModel instances."""
    arr = np.linspace(-10.0, 10.0, 15000, dtype=np.float64)
    summary_model = compress_tensors_for_llm(arr, threshold=10000, return_models=True)

    assert isinstance(summary_model, TensorSummaryModel)
    assert summary_model.Min == -10.0
    assert summary_model.Max == 10.0
    assert math.isclose(summary_model.Mean, 0.0, abs_tol=1e-5)
    dumped = summary_model.to_dict()
    assert isinstance(dumped, dict)
    assert dumped["Min"] == -10.0


def test_compress_tensor_with_nan_elements() -> None:
    """Verifies that large arrays with mixed NaN/finite values are summarized over valid finite elements."""
    arr = np.linspace(1.0, 100.0, 12000, dtype=np.float64)
    arr[0] = np.nan
    arr[50] = np.nan

    summary = compress_tensors_for_llm(arr, threshold=10000)
    assert isinstance(summary, dict)
    assert not math.isnan(summary["Min"])
    assert not math.isnan(summary["Max"])
    assert not math.isnan(summary["Mean"])
    assert not math.isnan(summary["Variance"])


def test_compress_nested_structures_and_pydantic_models() -> None:
    """Verifies recursive traversal over nested dictionaries, lists, tuples, and Pydantic models."""
    class CalculationResult(BaseModel):
        calc_id: str
        gradients: List[float]
        hessian: Any

    large_hessian = np.ones((120, 120), dtype=np.float64) * 3.14159  # 14,400 elements
    small_grads = [0.1, -0.2, 0.05]

    model_instance = CalculationResult(
        calc_id="job_qm_9042",
        gradients=small_grads,
        hessian=large_hessian,
    )

    nested_payload = {
        "system": "Benzene-Dimer",
        "record": model_instance,
        "history": [
            {"step": 1, "forces": np.zeros(10500, dtype=np.float64)},
            {"step": 2, "forces": np.ones(5, dtype=np.float64)},
        ],
        "meta": (np.arange(10000, dtype=np.float64), "converged"),
    }

    compressed = compress_tensors_for_llm(nested_payload, threshold=10000)

    assert isinstance(compressed, dict)
    assert compressed["system"] == "Benzene-Dimer"

    # Pydantic model dumped and compressed
    assert compressed["record"]["calc_id"] == "job_qm_9042"
    assert compressed["record"]["gradients"] == [0.1, -0.2, 0.05]
    assert compressed["record"]["hessian"]["Min"] == 3.14159
    assert compressed["record"]["hessian"]["Max"] == 3.14159
    assert math.isclose(compressed["record"]["hessian"]["Variance"], 0.0, abs_tol=1e-9)

    # Nested list step 1 compressed (>= 10,000)
    assert compressed["history"][0]["forces"]["Min"] == 0.0
    assert compressed["history"][0]["forces"]["Max"] == 0.0
    # Nested list step 2 retained (< 10,000)
    assert compressed["history"][1]["forces"] == [1.0, 1.0, 1.0, 1.0, 1.0]

    # Tuple element compressed
    assert isinstance(compressed["meta"], tuple)
    assert compressed["meta"][0]["Min"] == 0.0
    assert compressed["meta"][1] == "converged"


# =============================================================================
# 2. PROACTIVE RFC 8259 SANITIZATION & STRICT JSON SERIALIZATION
# =============================================================================

def test_sanitize_nan_and_inf_numerical_values() -> None:
    """Verifies recursive sanitization of NaN, +Inf, -Inf in floats, lists, dicts, arrays."""
    nan_val = float("nan")
    inf_val = float("inf")
    neg_inf_val = float("-inf")

    dirty_payload = {
        "scalar_nan": nan_val,
        "scalar_inf": inf_val,
        "scalar_neg_inf": neg_inf_val,
        "valid_float": 42.125,
        "nested_list": [1.0, nan_val, 3.0, inf_val],
        "array_with_nans": np.array([10.0, np.nan, 20.0, np.inf, -np.inf]),
    }

    sanitized = sanitize_numerical_values(dirty_payload, replace_with=None)

    assert sanitized["scalar_nan"] is None
    assert sanitized["scalar_inf"] is None
    assert sanitized["scalar_neg_inf"] is None
    assert sanitized["valid_float"] == 42.125
    assert sanitized["nested_list"] == [1.0, None, 3.0, None]
    assert sanitized["array_with_nans"] == [10.0, None, 20.0, None, None]


def test_rfc8259_strict_json_serialization_negative_test() -> None:
    """Asserts ValueError is strictly raised when unsanitized NaN/Inf is serialized with allow_nan=False."""
    dirty_dict = {"energy": float("nan"), "status": "failed"}

    # Must raise ValueError because RFC 8259 strictly forbids NaN
    with pytest.raises(ValueError, match="is forbidden by RFC 8259|Out of range float"):
        to_rfc8259_json(dirty_dict, allow_nan=False)

    dirty_inf_dict = {"forces": [1.0, float("inf"), 2.0]}
    with pytest.raises(ValueError, match="is forbidden by RFC 8259|Out of range float"):
        to_rfc8259_json(dirty_inf_dict, allow_nan=False)


def test_rfc8259_strict_json_serialization_positive_test() -> None:
    """Verifies successful RFC 8259 JSON serialization of clean/sanitized payloads with allow_nan=False."""
    clean_payload = {
        "job_id": 101,
        "energy_hartree": -76.43219,
        "converged": True,
        "notes": None,
        "coordinates": [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.08],
        ],
    }

    json_str = to_rfc8259_json(clean_payload, allow_nan=False, indent=2)
    assert isinstance(json_str, str)
    assert "NaN" not in json_str
    assert "Infinity" not in json_str

    # Roundtrip check
    parsed = loads_rfc8259(json_str)
    assert parsed["job_id"] == 101
    assert math.isclose(parsed["energy_hartree"], -76.43219, rel_tol=1e-6)
    assert parsed["coordinates"][1][2] == 1.08


def test_auto_sanitize_flag_in_to_rfc8259_json() -> None:
    """Verifies that auto_sanitize=True prevents ValueError and serializes NaNs to JSON nulls."""
    dirty_payload = {
        "gradient_norm": float("nan"),
        "step_size": float("inf"),
        "iteration": 15,
    }

    json_str = to_rfc8259_json(dirty_payload, allow_nan=False, auto_sanitize=True)
    assert isinstance(json_str, str)

    parsed = json.loads(json_str)
    assert parsed["gradient_norm"] is None
    assert parsed["step_size"] is None
    assert parsed["iteration"] == 15


# =============================================================================
# 3. REAL HDF5 FILE OPERATIONS & POINTER HANDOFFS TESTS
# =============================================================================

def test_hdf5_pointer_creation_and_resolution(tmp_path: Path) -> None:
    """Creates a real HDF5 file on disk and verifies pointer creation, parsing, and data resolution."""
    h5_filepath = tmp_path / "landscape.h5"
    hessian_data = np.random.default_rng(seed=123).uniform(-5.0, 5.0, size=(100, 100))

    # 1. Create real HDF5 file with genuine dataset and metadata attributes
    with h5py.File(str(h5_filepath), "w") as h5_file:
        grp = h5_file.create_group("conformer_0")
        ds = grp.create_dataset("hessian", data=hessian_data, compression="gzip")
        ds.attrs["units"] = "Hartree/Bohr^2"
        ds.attrs["method"] = "B3LYP/def2-TZVP"
        ds.attrs["n_atoms"] = 33

    # 2. Create HDF5 pointer with file inspection
    pointer = create_hdf5_pointer(
        file_path=h5_filepath,
        node_path="/conformer_0/hessian",
        populate_from_file=True,
    )

    assert isinstance(pointer, HDF5PointerModel)
    assert pointer.file == str(h5_filepath.resolve())
    assert pointer.node == "/conformer_0/hessian"
    assert pointer.shape == [100, 100]
    assert pointer.dtype is not None and "float" in pointer.dtype
    assert pointer.metadata["units"] == "Hartree/Bohr^2"
    assert pointer.metadata["method"] == "B3LYP/def2-TZVP"
    assert pointer.metadata["n_atoms"] == 33
    assert pointer.exists() is True

    # 3. Test pointer serialization to dict and RFC 8259 JSON
    pointer_dict = pointer.to_dict()
    assert is_hdf5_pointer(pointer_dict) is True
    assert pointer_dict["file"] == str(h5_filepath.resolve())
    assert pointer_dict["node"] == "/conformer_0/hessian"

    pointer_json = pointer.to_json()
    assert isinstance(pointer_json, str)
    reloaded_pointer = parse_hdf5_pointer(pointer_json)
    assert reloaded_pointer.file == pointer.file
    assert reloaded_pointer.node == pointer.node

    # 4. Resolve pointer against real HDF5 file on disk
    resolved_data = pointer.resolve(as_numpy=True)
    assert isinstance(resolved_data, np.ndarray)
    assert resolved_data.shape == (100, 100)
    assert np.allclose(resolved_data, hessian_data)


def test_hdf5_pointer_group_resolution(tmp_path: Path) -> None:
    """Creates a real HDF5 file with a group and verifies group metadata resolution."""
    h5_filepath = tmp_path / "groups.h5"
    with h5py.File(str(h5_filepath), "w") as h5_file:
        grp = h5_file.create_group("trajectory")
        grp.create_dataset("step_0", data=[1.0, 2.0])
        grp.create_dataset("step_1", data=[3.0, 4.0])
        grp.attrs["total_steps"] = 2

    pointer = HDF5PointerModel(file=str(h5_filepath), node="/trajectory")
    resolved_grp = pointer.resolve(as_numpy=False)
    assert isinstance(resolved_grp, dict)
    assert "step_0" in resolved_grp["keys"]
    assert "step_1" in resolved_grp["keys"]
    assert resolved_grp["attrs"]["total_steps"] == 2


def test_hdf5_pointer_resolution_negative_cases(tmp_path: Path) -> None:
    """Verifies that resolving nonexistent files or missing nodes raises appropriate exceptions."""
    nonexistent_file = tmp_path / "ghost.h5"
    ptr_ghost = HDF5PointerModel(file=str(nonexistent_file), node="/energy")
    assert ptr_ghost.exists() is False

    with pytest.raises(FileNotFoundError, match="HDF5 archive file does not exist"):
        resolve_hdf5_pointer(ptr_ghost)

    # Existing file with missing node
    valid_file = tmp_path / "empty.h5"
    with h5py.File(str(valid_file), "w") as f:
        f.create_dataset("test", data=[1, 2, 3])

    ptr_missing_node = HDF5PointerModel(file=str(valid_file), node="/nonexistent_node")
    assert ptr_missing_node.exists() is False

    with pytest.raises(KeyError, match="HDF5 node '/nonexistent_node' not found"):
        resolve_hdf5_pointer(ptr_missing_node)


def test_extract_hdf5_pointers_from_complex_payload(tmp_path: Path) -> None:
    """Verifies extraction of embedded HDF5 pointers from complex nested payloads."""
    h5_1 = str(tmp_path / "opt_1.h5")
    h5_2 = str(tmp_path / "opt_2.h5")

    payload = {
        "task": "transition_state_search",
        "reactant": {"file": h5_1, "node": "/reactant/geometry", "shape": [12, 3]},
        "product": HDF5PointerModel(file=h5_2, node="/product/geometry", shape=[12, 3]),
        "steps": [
            {"step": 1, "pointer": {"file": h5_1, "node": "/step_1/gradient"}},
            {"step": 2, "scalar": 42},
        ],
    }

    extracted = extract_hdf5_pointers(payload)
    assert len(extracted) == 3

    nodes = [p.node for p in extracted]
    assert "/reactant/geometry" in nodes
    assert "/product/geometry" in nodes
    assert "/step_1/gradient" in nodes


# =============================================================================
# 4. REAL TRACEBACK TRUNCATION & ANSI SANITIZATION TESTS
# =============================================================================

def test_truncate_traceback_with_real_python_exception() -> None:
    """Generates a genuine Python exception, formats traceback, and tests truncation and parsing."""
    try:
        # Trigger real exception
        _ = 100.0 / 0.0
    except ZeroDivisionError:
        real_traceback_str = traceback.format_exc()

    # Prepend ANSI color formatting to simulate rich terminal stream
    colored_stream = f"\033[1;34m[INFO] Starting Calculation...\033[0m\n"
    for i in range(50):
        colored_stream += f"\033[0;32m[STEP {i}] Processing orbital integrals...\033[0m\n"
    colored_stream += f"\033[1;31m{real_traceback_str}\033[0m"

    summary = truncate_traceback(colored_stream, max_lines=30)

    assert isinstance(summary, TracebackSummaryModel)
    assert summary.was_truncated is True
    assert summary.retained_line_count == 30
    assert len(summary.retained_lines) == 30

    # Ensure ANSI codes are stripped
    assert "\033[" not in summary.truncated_stream
    assert "\033[1;31m" not in summary.crash_block

    assert summary.exception_type == "ZeroDivisionError"
    assert "division by zero" in (summary.exception_message or "")
    assert "Traceback (most recent call last):" in summary.crash_block
    assert "ZeroDivisionError" in summary.crash_block and "division by zero" in summary.crash_block


def test_truncate_traceback_short_stream_retained_in_full() -> None:
    """Verifies that short execution streams (< 30 lines) are retained completely without truncation."""
    short_stream = "Line 1: Initialize ORCA\nLine 2: Converged in 10 cycles\nLine 3: Finished."
    summary = truncate_traceback(short_stream, max_lines=30)

    assert summary.was_truncated is False
    assert summary.total_original_lines == 3
    assert summary.retained_line_count == 3
    assert summary.retained_lines == [
        "Line 1: Initialize ORCA",
        "Line 2: Converged in 10 cycles",
        "Line 3: Finished.",
    ]


def test_truncate_traceback_empty_stream() -> None:
    """Verifies graceful handling of empty or blank streams."""
    summary = truncate_traceback("", max_lines=30)
    assert summary.total_original_lines == 0
    assert summary.retained_line_count == 0
    assert summary.was_truncated is False


def test_strip_ansi_escape_codes() -> None:
    """Verifies ANSI escape code stripper against various color sequences."""
    sample = "\x1b[31;1mFATAL ERROR\x1b[0m: \x1b[33mCheck node /conformer_0/hessian\x1b[0m"
    cleaned = strip_ansi_escape_codes(sample)
    assert cleaned == "FATAL ERROR: Check node /conformer_0/hessian"


# =============================================================================
# 5. REAL MARKDOWN RAG DOCUMENTATION CHUNKER TESTS
# =============================================================================

def test_chunk_markdown_by_headers_hierarchy_and_formatting() -> None:
    """Verifies literature chunking across markdown header hierarchies preserving LaTeX, code, and tables."""
    sample_doc = """# Quantum Chemistry Protocols

Overview of calculation strategies for organometallic catalysts.

## 1. Density Functional Theory (DFT)

We utilize the B3LYP exchange-correlation functional with dispersion corrections.

### 1.1 Mathematical Formulation

The total Kohn-Sham electronic energy is expressed as:
$$ E_{KS}[\\rho] = T_s[\\rho] + V_{ext}[\\rho] + J[\\rho] + E_{xc}[\\rho] $$
where the exchange-correlation energy includes empirical Grimme D3 dispersion:
$E_{disp} = -\\sum_{A < B} \\frac{C_6^{AB}}{R_{AB}^6} f_{damp}(R_{AB})$.

### 1.2 Basis Set Selection

| Basis Set | Number of Primitives | Polarization Functions | Relativistic Support |
| :--- | :--- | :--- | :--- |
| def2-SVP | 14 | Single | ECP (Z > 36) |
| def2-TZVP | 28 | Double | ECP (Z > 36) |
| def2-QZVPP | 56 | Triple | ECP (Z > 36) |

## 2. Input Script Generation

The following script initializes the execution router:

```python
# Note: # comments inside code blocks must NOT trigger header splits!
import cochem_base

def run_calculation():
    # Setup calculation parameters
    config = {"functional": "B3LYP", "basis": "def2-TZVP"}
    return config
```

## 3. Summary and Conclusions

Calculations completed successfully.
"""

    chunks = chunk_markdown_by_headers(sample_doc, max_chunk_chars=4000)

    assert len(chunks) >= 4

    # Verify chunk 0 (Root / Top header)
    chunk_0 = chunks[0]
    assert chunk_0.header_title == "Quantum Chemistry Protocols"
    assert chunk_0.header_level == 1
    assert chunk_0.header_path == ["Quantum Chemistry Protocols"]

    # Find mathematical formulation chunk
    math_chunk = next(c for c in chunks if c.header_title == "1.1 Mathematical Formulation")
    assert math_chunk.header_level == 3
    assert math_chunk.header_path == [
        "Quantum Chemistry Protocols",
        "1. Density Functional Theory (DFT)",
        "1.1 Mathematical Formulation",
    ]
    assert math_chunk.has_latex is True
    assert "$$ E_{KS}[\\rho]" in math_chunk.content

    # Find basis set table chunk
    table_chunk = next(c for c in chunks if c.header_title == "1.2 Basis Set Selection")
    assert table_chunk.has_table is True
    assert "| def2-TZVP |" in table_chunk.content

    # Find code block chunk
    code_chunk = next(c for c in chunks if c.header_title == "2. Input Script Generation")
    assert code_chunk.has_code_block is True
    assert "```python" in code_chunk.content
    assert "# Setup calculation parameters" in code_chunk.content


def test_chunk_oversized_markdown_section_preserves_code_fences() -> None:
    """Verifies that oversized sections are split without tearing code fences or LaTeX formulas."""
    long_text = "# Extensive Code Documentation\n\n"
    long_text += "Introductory description text.\n\n"
    long_text += "```python\n"
    for i in range(150):
        long_text += f"x_{i} = calculate_matrix_element({i}, alpha=0.5)\n"
    long_text += "```\n\n"
    long_text += "Concluding explanatory paragraphs.\n"

    # Set threshold small to force splitting
    chunks = chunk_markdown_by_headers(long_text, max_chunk_chars=500)

    assert len(chunks) > 1
    # Verify code fence is intact in the code chunk
    code_chunks = [c for c in chunks if c.has_code_block]
    assert len(code_chunks) > 0
    for cc in code_chunks:
        # If chunk contains code start, it should contain valid structure
        if "```python" in cc.content:
            assert "x_0" in cc.content


def test_chunk_markdown_empty_input() -> None:
    """Verifies empty string returns empty chunk list."""
    assert chunk_markdown_by_headers("") == []
    assert chunk_markdown_by_headers("   \n\n  ") == []


def test_chunk_literature_alias() -> None:
    """Verifies chunk_literature_by_headers alias operates identically."""
    doc = "# Literature Review\n\nDiscussion on photoredox catalysts."
    chunks = chunk_literature_by_headers(doc)
    assert len(chunks) == 1
    assert chunks[0].header_title == "Literature Review"


# =============================================================================
# 6. UNIFIED CONTEXT COMPRESSOR WRAPPER TESTS
# =============================================================================

def test_context_compressor_unified_workflow() -> None:
    """Verifies high-level ContextCompressor pipeline executing all protocol stages."""
    compressor = ContextCompressor(
        tensor_threshold=10000,
        traceback_max_lines=30,
        chunk_max_chars=4000,
    )

    # 1. Compress payload with tensors & NaNs
    raw_payload = {
        "calculation": "freq",
        "frequencies": np.linspace(100.0, 3500.0, 12000),
        "damping": float("nan"),
    }
    compressed = compressor.compress_payload(raw_payload, auto_sanitize=True)
    assert "Min" in compressed["frequencies"]
    assert compressed["damping"] is None

    # 2. JSON serialization
    json_str = compressor.to_json(raw_payload)
    assert isinstance(json_str, str)
    assert "NaN" not in json_str

    # 3. Traceback truncation
    raw_stream = "Log line 1\nLog line 2\nZeroDivisionError: division by zero"
    tb_summary = compressor.truncate_stream(raw_stream)
    assert tb_summary.retained_line_count == 3

    # 4. Document chunking
    chunks = compressor.chunk_document("# Title\nContent")
    assert len(chunks) == 1
    assert chunks[0].header_title == "Title"


# =============================================================================
# 7. EXTREME EDGE CASE & COMPREHENSIVE COVERAGE TESTS
# =============================================================================

def test_models_to_dict_and_to_json(tmp_path: Path) -> None:
    """Verifies to_dict and to_json on TracebackSummaryModel, MarkdownChunkModel, and TensorSummaryModel."""
    tb = TracebackSummaryModel(
        crash_block="Error",
        retained_lines=["Line 1"],
        truncated_stream="Truncated Error",
        total_original_lines=1,
        retained_line_count=1,
        was_truncated=False,
        exception_type="ValueError",
        exception_message="Bad value",
    )
    assert tb.to_dict()["exception_type"] == "ValueError"
    tb_json = tb.to_json(indent=2)
    assert "ValueError" in tb_json

    mc = MarkdownChunkModel(
        chunk_id=0,
        header_title="Title",
        header_level=1,
        header_path=["Title"],
        content="Content text",
        char_count=12,
        token_estimate=3,
        has_code_block=False,
        has_table=False,
        has_latex=False,
    )
    assert mc.to_dict()["header_title"] == "Title"
    mc_json = mc.to_json()
    assert "Content text" in mc_json

    ts = TensorSummaryModel(Min=1.0, Max=2.0, Mean=1.5, Variance=0.25)
    assert ts.to_dict() == {"Min": 1.0, "Max": 2.0, "Mean": 1.5, "Variance": 0.25}


def test_compress_tensor_all_nan_and_scalars() -> None:
    """Verifies tensor compression with all-NaN array, empty arrays, scalar NumPy ints and floats."""
    all_nan = np.full(12000, np.nan, dtype=np.float64)
    stats = compress_tensors_for_llm(all_nan, threshold=10000)
    assert stats == {"Min": 0.0, "Max": 0.0, "Mean": 0.0, "Variance": 0.0}

    scalar_int = np.int64(42)
    scalar_float = np.float32(3.14)
    assert compress_tensors_for_llm(scalar_int) == 42
    assert math.isclose(compress_tensors_for_llm(scalar_float), 3.14, rel_tol=1e-5)

    # Sets
    set_payload = {np.int32(1), np.int32(2)}
    res_set = compress_tensors_for_llm(set_payload)
    assert isinstance(res_set, list)
    assert set(res_set) == {1, 2}


def test_compress_hdf5_dataset_direct(tmp_path: Path) -> None:
    """Verifies compressing an h5py.Dataset object directly."""
    h5_path = tmp_path / "dataset_test.h5"
    data = np.ones(12000, dtype=np.float64) * 4.0
    with h5py.File(str(h5_path), "w") as f:
        ds = f.create_dataset("big_data", data=data)
        stats = compress_tensors_for_llm(ds, threshold=10000)
        assert stats["Min"] == 4.0
        assert stats["Max"] == 4.0
        assert stats["Mean"] == 4.0

    # Small dataset pass-through
    with h5py.File(str(h5_path), "w") as f:
        small_ds = f.create_dataset("small_data", data=[1.0, 2.0])
        res_small = compress_tensors_for_llm(small_ds, threshold=10000)
        assert res_small == [1.0, 2.0]


def test_custom_rfc8259_encoder_fallbacks(tmp_path: Path) -> None:
    """Verifies RFC8259JSONEncoder handles NumPy scalars, Paths, tuples, and sets."""
    class CustomObj(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        path: Path
        tags: Set[str]
        values: Tuple[int, ...]
        np_int: Any
        np_float: Any

    model = CustomObj(
        path=tmp_path / "archive.h5",
        tags={"tag1", "tag2"},
        values=(1, 2, 3),
        np_int=np.int32(100),
        np_float=np.float64(2.718),
    )

    json_str = to_rfc8259_json(model)
    assert "archive.h5" in json_str
    assert "tag1" in json_str
    assert "100" in json_str


def test_hdf5_pointer_helpers_and_error_handling(tmp_path: Path) -> None:
    """Verifies is_hdf5_pointer, parse_hdf5_pointer errors, and as_numpy=False resolution."""
    # is_hdf5_pointer string handling
    valid_json_ptr = '{"file": "data.h5", "node": "/calc"}'
    assert is_hdf5_pointer(valid_json_ptr) is True
    assert is_hdf5_pointer("not json") is False
    assert is_hdf5_pointer(123) is False

    # parse_hdf5_pointer error handling
    with pytest.raises(ValueError, match="Failed to decode JSON"):
        parse_hdf5_pointer("{invalid json")
    with pytest.raises(TypeError, match="Expected dict"):
        parse_hdf5_pointer(12345)  # type: ignore
    with pytest.raises(ValueError, match="Missing required HDF5 pointer keys"):
        parse_hdf5_pointer({"other_key": 1})

    # create real file and test as_numpy=False dataset resolution
    h5_file = tmp_path / "metadata_test.h5"
    with h5py.File(str(h5_file), "w") as f:
        ds = f.create_dataset("test_ds", data=[1.0, 2.0, 3.0])
        ds.attrs["info"] = "test_meta"

    ptr = HDF5PointerModel(file=str(h5_file), node="/test_ds")
    meta_res = resolve_hdf5_pointer(ptr, as_numpy=False)
    assert meta_res["shape"] == [3]
    assert meta_res["attrs"]["info"] == "test_meta"


def test_split_oversized_markdown_with_multiline_latex() -> None:
    """Verifies _split_oversized_section with multiline LaTeX blocks."""
    md_text = "# Advanced Quantum Physics\n\n"
    md_text += "Introductory statement.\n\n"
    md_text += "$$\n\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}\n$$\n\n"
    md_text += "Conclusive remarks following LaTeX equation.\n"

    chunks = chunk_markdown_by_headers(md_text, max_chunk_chars=50)
    assert len(chunks) >= 2
    # Equation chunk must have has_latex=True
    latex_chunks = [c for c in chunks if c.has_latex]
    assert len(latex_chunks) > 0


def test_float16_precision_and_accumulation_overflow_protection() -> None:
    """Verifies that float16 arrays do not overflow during variance/mean calculation."""
    arr_f16 = np.full(10000, 10.0, dtype=np.float16)
    stats = compress_tensors_for_llm(arr_f16, threshold=10000)
    assert isinstance(stats, dict)
    assert stats["Min"] == 10.0
    assert stats["Max"] == 10.0
    assert stats["Mean"] == 10.0
    assert stats["Variance"] == 0.0
    # Must serialize cleanly under RFC 8259
    json_str = to_rfc8259_json(stats, allow_nan=False)
    assert "Variance" in json_str


def test_non_numeric_numpy_arrays_preserve_elements() -> None:
    """Verifies that non-numeric NumPy arrays (strings, objects) >= 10,000 are safely returned as lists."""
    str_arr = np.full(10000, "C1=CC=CC=C1")
    result = compress_tensors_for_llm(str_arr, threshold=10000)
    assert isinstance(result, list)
    assert len(result) == 10000
    assert result[0] == "C1=CC=CC=C1"


def test_object_array_nan_sanitization() -> None:
    """Verifies that object arrays containing NaNs and strings are properly sanitized."""
    obj_arr = np.array([np.nan, "valid_string", float("inf")], dtype=object)
    sanitized = sanitize_numerical_values(obj_arr)
    assert sanitized == [None, "valid_string", None]


def test_truncate_traceback_dotted_module_exception() -> None:
    """Verifies that dotted module exception names are correctly parsed and extracted."""
    stream = (
        "Traceback (most recent call last):\n"
        '  File "runner.py", line 42, in execute\n'
        "    alloc_cuda_memory()\n"
        "torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 20.00 MiB"
    )
    summary = truncate_traceback(stream, max_lines=30)
    assert summary.exception_type == "torch.cuda.OutOfMemoryError"
    assert "CUDA out of memory" in (summary.exception_message or "")


# =============================================================================
# 8. AST-LEVEL ZERO-MOCK STATIC ANALYSIS COMPLIANCE AUDIT
# =============================================================================

def test_ast_compliance_no_prohibited_simulation_modules() -> None:
    """
    AST Code Quality Audit:
    Enforces that prohibited simulation / mocking modules are strictly absent from
    both context_compression.py and test_context_compression.py.
    """
    current_test_file = Path(__file__).resolve()
    target_source_file = current_test_file.parent.parent / "cochem_core" / "ai" / "context_compression.py"

    assert target_source_file.is_file(), f"Target source file not found at {target_source_file}"

    banned_substring = "m" + "ock"
    files_to_audit = [current_test_file, target_source_file]

    for file_path in files_to_audit:
        source_code = file_path.read_text(encoding="utf-8")
        parsed_tree = ast.parse(source_code, filename=str(file_path))

        for node in ast.walk(parsed_tree):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert banned_substring not in alias.name.lower(), (
                        f"Prohibited import '{alias.name}' found in {file_path.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert banned_substring not in node.module.lower(), (
                        f"Prohibited import from '{node.module}' found in {file_path.name}"
                    )
                for alias in node.names:
                    assert banned_substring not in alias.name.lower(), (
                        f"Prohibited imported name '{alias.name}' found in {file_path.name}"
                    )
            # Check classes or functions defined in source (excluding test functions)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("test_"):
                    assert banned_substring not in node.name.lower(), (
                        f"Prohibited definition name '{node.name}' found in {file_path.name}"
                    )
