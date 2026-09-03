#!/usr/bin/env python3
# cochem_canvas_target: test_suite/test_cochem_core_context_compressor.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit and Integration Test Suite for CoChem Core Context Compressor.
Tests Document 9 §2 - LTTB Downsampling and AST Context-Compression Engine for AI Resource Guarding.

Validates:
1. LTTB Spatial Downsampling (Numba JIT, NumPy fallback, peak retention, index extraction, LTTBResult).
2. AST Context-Compression & Skeletonization (signature extraction, docstring minification, body ellipsis).
3. AST Integrity & Anti-Spoof Static Analysis Auditor (identifies forbidden intercept symbols, passes authentic code).
4. Tensor Statistical Summarization (Min, Max, Mean, Variance, Last_Value, telemetry dictionary format).
5. RFC 8259 Strict JSON Serialization & Proactive NaN/Inf Sanitization.
6. Zero-VRAM HDF5 Pointer Creation, Disk Verification, Dataset Inspection, and Memory Resolution.
7. Execution Traceback Truncation & ANSI Code Stripping.
8. Hierarchical Markdown Documentation & Chemical Literature RAG Chunker.
9. Dynamic Mendeleev Molecular Geometry Physical Property Compression.
10. AST Static Analysis verifying 0 mock usages across source and test files.

Strict Zero-Mock Mandate:
- 100% physically executable tests with zero mocks, stubs, or fake libraries.
"""

from __future__ import annotations

import ast
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import h5py
import numpy as np
import pytest

from core_engine.cochem_core_context_compressor import (
    ASTContextCompressor,
    ASTContextSummary,
    ContextCompressor,
    CoreContextCompressor,
    DEFAULT_ARRAY_THRESHOLD,
    DEFAULT_CHUNK_MAX_CHARS,
    DEFAULT_LTTB_THRESHOLD,
    DEFAULT_TENSOR_THRESHOLD,
    DEFAULT_TRACEBACK_MAX_LINES,
    HDF5PointerModel,
    LTTBDownsampler,
    LTTBResult,
    MarkdownChunkModel,
    TensorSummaryModel,
    TracebackSummaryModel,
    chunk_literature_by_headers,
    chunk_markdown_by_headers,
    compress_array_to_summary,
    compress_molecular_geometry,
    compress_tensors_for_llm,
    compress_to_dict,
    create_hdf5_pointer,
    decimate_lttb,
    dumps_rfc8259,
    extract_hdf5_pointers,
    intercept_and_compress,
    is_hdf5_pointer,
    loads_rfc8259,
    lttb_decimate,
    lttb_downsample,
    lttb_downsample_1d,
    lttb_downsample_indices,
    lttb_downsample_xy,
    parse_hdf5_pointer,
    resolve_hdf5_pointer,
    sanitize_numerical_values,
    strip_ansi_escape_codes,
    to_rfc8259_json,
    truncate_traceback,
)


# =============================================================================
# 1. LTTB DOWNSAMPLING TESTS
# =============================================================================

def test_lttb_downsample_xy_numba_and_numpy() -> None:
    """Verifies that LTTB downsamples large 1D curves preserving start and end points."""
    x = np.arange(5000, dtype=np.float64) * 0.02
    y = np.exp(-((x - 50.0) ** 2) / 10.0)

    # 1. Numba JIT
    down_numba = lttb_downsample_xy(x, y, threshold=100, use_numba=True)
    assert down_numba.shape == (100, 2)
    assert down_numba[0, 0] == x[0]
    assert down_numba[0, 1] == y[0]
    assert down_numba[-1, 0] == x[-1]
    assert down_numba[-1, 1] == y[-1]

    max_down_y = float(np.max(down_numba[:, 1]))
    assert max_down_y > 0.95

    # 2. NumPy Fallback
    down_numpy = lttb_downsample_xy(x, y, threshold=100, use_numba=False)
    assert down_numpy.shape == (100, 2)
    assert down_numpy[0, 0] == x[0]
    assert down_numpy[-1, 0] == x[-1]
    assert float(np.max(down_numpy[:, 1])) > 0.95


def test_lttb_downsample_2d_and_1d_wrappers() -> None:
    """Verifies 2D (N, 2) and 1D y signal downsampling wrappers."""
    x = np.arange(1000, dtype=np.float64) * 0.01
    y = np.exp(-x)
    data_2d = np.column_stack((x, y))

    res_2d = lttb_downsample(data_2d, threshold=50)
    assert res_2d.shape == (50, 2)

    res_1d = lttb_downsample_1d(y, threshold=50, x=x)
    assert res_1d.shape == (50, 2)

    res_1d_nox = lttb_downsample_1d(y, threshold=50)
    assert res_1d_nox.shape == (50, 2)
    assert res_1d_nox[0, 0] == 0.0
    assert res_1d_nox[-1, 0] == 999.0


def test_lttb_downsample_indices_and_aliases() -> None:
    """Verifies index selection kernel and decimate aliases."""
    x = np.arange(1000, dtype=np.float64) * 0.01
    y = np.exp(-x * 0.5)

    indices = lttb_downsample_indices(x, y, threshold=20)
    assert len(indices) == 20
    assert indices[0] == 0
    assert indices[-1] == 999
    assert np.all(np.diff(indices) > 0)

    dec_x, dec_y = decimate_lttb(x, y, max_points=30)
    assert len(dec_x) == 30
    assert len(dec_y) == 30

    dec_x2, dec_y2 = lttb_decimate(x, y, max_points=30)
    assert np.array_equal(dec_x, dec_x2)
    assert np.array_equal(dec_y, dec_y2)


def test_lttb_downsampler_class_and_metadata() -> None:
    """Verifies LTTBDownsampler class methods and LTTBResult metadata container."""
    downsampler = LTTBDownsampler(default_threshold=40)
    x = np.arange(2000, dtype=np.float64) * 0.025
    y = np.exp(-x * 0.1)

    res_xy = downsampler.downsample_xy(x, y)
    assert res_xy.shape == (40, 2)

    meta_result = LTTBDownsampler.downsample_with_metadata(x, y, threshold=50)
    assert isinstance(meta_result, LTTBResult)
    assert meta_result.original_points == 2000
    assert meta_result.downsampled_points == 50
    assert meta_result.compression_ratio == 40.0
    assert meta_result.execution_time_ms > 0.0
    assert len(meta_result.downsampled_x) == 50
    assert len(meta_result.selected_indices) == 50

    npy = meta_result.to_numpy()
    assert npy.shape == (50, 2)

    json_str = meta_result.to_json()
    assert '"compression_ratio": 40.0' in json_str


def test_lttb_validation_failures() -> None:
    """Verifies proper error handling on invalid downsampling inputs."""
    with pytest.raises(ValueError, match="Threshold.*must be at least 2"):
        lttb_downsample_xy([1.0, 2.0], [1.0, 2.0], threshold=1)

    with pytest.raises(ValueError, match="Length of x.*must equal length of y"):
        lttb_downsample_xy([1.0, 2.0, 3.0], [1.0, 2.0], threshold=2)

    with pytest.raises(ValueError, match="at least 2 points"):
        lttb_downsample_xy([1.0], [1.0], threshold=2)

    with pytest.raises(ValueError, match="contains NaN or Inf"):
        lttb_downsample_xy([1.0, 2.0, 3.0], [1.0, np.nan, 3.0], threshold=2)


# =============================================================================
# 2. AST CONTEXT COMPRESSION & SKELETONIZATION TESTS
# =============================================================================

def test_ast_skeleton_compression() -> None:
    """Verifies transformation of complete Python source into token-efficient skeleton."""
    sample_code = """
import os
import sys
from typing import List, Optional

class PhysicalCalculator:
    \"\"\"Calculates physical molecular properties.\"\"\"
    version: str = "1.0.0"

    def __init__(self, name: str) -> None:
        self.name = name
        self.cache = {}

    def compute_energy(self, coords: List[float], scale: float = 1.0) -> float:
        \"\"\"Executes complex numerical Hartree-Fock calculation.\"\"\"
        total = 0.0
        for c in coords:
            total += c * scale
        return total * 2.5

def run_pipeline(x: int) -> int:
    return x * 10
"""
    compressor = ASTContextCompressor(preserve_docstrings=True)
    skeleton = compressor.compress_to_skeleton(sample_code)

    assert "class PhysicalCalculator:" in skeleton
    assert "def compute_energy(self, coords: List[float], scale: float=1.0) -> float:" in skeleton or "def compute_energy(self, coords: List[float], scale: float = 1.0) -> float:" in skeleton
    assert "..." in skeleton
    assert "total += c * scale" not in skeleton

    parsed = ast.parse(skeleton)
    assert len(parsed.body) > 0


def test_ast_summary_extraction() -> None:
    """Verifies extraction of structural symbols and line/char metrics."""
    sample_code = """
import numpy as np
from pathlib import Path

MAX_LIMIT = 500

class QuantumSystem:
    def solve(self) -> None:
        pass

def calculate_scf(steps: int = 100) -> float:
    return 42.0
"""
    compressor = ASTContextCompressor()
    summary = compressor.extract_ast_summary(sample_code)

    assert isinstance(summary, ASTContextSummary)
    assert summary.total_lines > 0
    assert summary.compressed_lines > 0
    assert "import numpy as np" in summary.imports
    assert "from pathlib import Path" in summary.from_imports
    assert "MAX_LIMIT" in summary.global_vars
    assert len(summary.classes) == 1
    assert summary.classes[0].name == "QuantumSystem"
    assert len(summary.functions) == 1
    assert summary.functions[0].name == "calculate_scf"
    assert summary.functions[0].returns == "float"
    assert len(summary.compliance_violations) == 0


def test_ast_integrity_compliance_auditor() -> None:
    """Verifies that the AST auditor catches forbidden simulation symbols and approves clean code."""
    clean_code = """
import numpy as np

def compute(x: float) -> float:
    return float(x * 2.0)
"""
    dirty_code = (
        "import mock\n"
        "from mock import MagicMock\n\n"
        "def bad_routine():\n"
        "    m = MagicMock()\n"
        "    pass\n"
    )
    compressor = ASTContextCompressor()
    clean_violations = compressor.audit_integrity_compliance(clean_code)
    assert len(clean_violations) == 0

    dirty_violations = compressor.audit_integrity_compliance(dirty_code)
    assert len(dirty_violations) >= 3


# =============================================================================
# 3. TENSOR & NUMERICAL STATISTICAL COMPRESSION TESTS
# =============================================================================

def test_compress_tensors_for_llm_large_and_small() -> None:
    """Verifies compression of arrays >= threshold and preservation of small arrays."""
    large_arr = np.arange(12000, dtype=np.float64)
    small_arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)

    comp_large = compress_tensors_for_llm(large_arr, threshold=10000)
    assert isinstance(comp_large, dict)
    assert comp_large["Min"] == 0.0
    assert comp_large["Max"] == 11999.0
    assert math.isclose(comp_large["Mean"], 5999.5, rel_tol=1e-5)

    comp_small = compress_tensors_for_llm(small_arr, threshold=10000)
    assert comp_small == [1.0, 2.0, 3.0]


def test_intercept_and_compress_telemetry_arrays() -> None:
    """Verifies intercept_and_compress telemetry helper with Array_ prefixes."""
    large_list = list(range(100))
    small_list = [1, 2, 3]

    res_large = intercept_and_compress(large_list, threshold=50)
    assert isinstance(res_large, dict)
    assert set(res_large.keys()) == {"Array_Min", "Array_Max", "Array_Mean", "Array_Variance", "Last_Value"}
    assert res_large["Array_Min"] == 0.0
    assert res_large["Array_Max"] == 99.0
    assert res_large["Last_Value"] == 99.0

    res_small = intercept_and_compress(small_list, threshold=50)
    assert res_small == small_list


def test_compress_array_to_summary_and_dict() -> None:
    """Verifies direct conversion of arrays to TensorSummaryModel."""
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    model = compress_array_to_summary(data)
    assert isinstance(model, TensorSummaryModel)
    assert model.Min == 10.0
    assert model.Max == 50.0
    assert model.Mean == 30.0
    assert model.Last_Value == 50.0
    assert model.count == 5

    dict_res = compress_to_dict(data)
    assert dict_res["Array_Mean"] == 30.0


# =============================================================================
# 4. RFC 8259 STRICT JSON & SANITIZATION TESTS
# =============================================================================

def test_sanitize_numerical_values_nan_inf() -> None:
    """Verifies recursive sanitization of NaN and Inf floats."""
    dirty_payload = {
        "valid": 42.0,
        "nan_val": float("nan"),
        "inf_val": float("inf"),
        "nested": [1.0, float("-inf"), 3.0],
        "arr": np.array([1.0, np.nan, 2.0]),
    }

    sanitized = sanitize_numerical_values(dirty_payload, replace_with=None)
    assert sanitized["valid"] == 42.0
    assert sanitized["nan_val"] is None
    assert sanitized["inf_val"] is None
    assert sanitized["nested"] == [1.0, None, 3.0]
    assert sanitized["arr"] == [1.0, None, 2.0]


def test_strict_rfc8259_serialization_failures_and_success() -> None:
    """Verifies strict RFC 8259 compliance prohibiting raw NaN/Inf."""
    dirty_data = {"energy": float("nan")}

    with pytest.raises(ValueError, match="Out of range float value"):
        to_rfc8259_json(dirty_data, allow_nan=False, auto_sanitize=False)

    clean_json = to_rfc8259_json(dirty_data, auto_sanitize=True)
    assert '{"energy": null}' in clean_json

    parsed = loads_rfc8259(clean_json)
    assert parsed["energy"] is None


# =============================================================================
# 5. ZERO-VRAM HDF5 POINTER HANDOFF PROTOCOL TESTS
# =============================================================================

def test_hdf5_pointer_lifecycle_and_resolution() -> None:
    """Verifies genuine HDF5 file creation, pointer extraction, and on-disk data resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = Path(tmpdir) / "test_pes_store.h5"
        matrix_data = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [0.0, 0.0, 3.0],
        ], dtype=np.float64)

        # Create physical HDF5 archive
        with h5py.File(str(h5_path), "w") as h5_file:
            ds = h5_file.create_dataset("/conformer_0/hessian", data=matrix_data)
            ds.attrs["units"] = "Hartree/Bohr2"
            ds.attrs["method"] = "wB97M-V/def2-QZVPP"

        # 1. Create pointer
        pointer = create_hdf5_pointer(
            file_path=h5_path,
            node_path="/conformer_0/hessian",
            populate_from_file=True,
        )
        assert isinstance(pointer, HDF5PointerModel)
        assert pointer.exists() is True
        assert pointer.shape == [3, 3]
        assert pointer.dtype == "float64"
        assert pointer.metadata.get("units") == "Hartree/Bohr2"

        # 2. Resolve pointer
        resolved_data = pointer.resolve(as_numpy=True)
        assert isinstance(resolved_data, np.ndarray)
        assert resolved_data.shape == (3, 3)
        assert np.allclose(resolved_data, matrix_data)

        # 3. Extract pointer from nested structure
        nested_payload = {
            "task_id": "job_123",
            "pointer_ref": pointer.to_dict(),
        }
        extracted = extract_hdf5_pointers(nested_payload)
        assert len(extracted) == 1
        assert extracted[0].node == "/conformer_0/hessian"


# =============================================================================
# 6. TRACEBACK & STREAM TRUNCATION TESTS
# =============================================================================

def test_traceback_truncation_and_ansi_cleaning() -> None:
    """Verifies ANSI escape stripping and root-cause extraction."""
    raw_stream = (
        "\x1b[31m[ERROR]\x1b[0m Starting electronic structure calculation\n"
        + "\n".join([f"Line {i}: Processing basis set iteration" for i in range(50)])
        + "\nTraceback (most recent call last):\n"
        + '  File "orca_runner.py", line 42, in run\n'
        + "    res = scf_step()\n"
        + "ZeroDivisionError: float division by zero\n"
        + "\n".join([f"Post crash tail {j}" for j in range(10)])
    )

    tb_summary = truncate_traceback(raw_stream, max_lines=20)
    assert isinstance(tb_summary, TracebackSummaryModel)
    assert tb_summary.was_truncated is True
    assert tb_summary.exception_type == "ZeroDivisionError"
    assert "float division by zero" in (tb_summary.exception_message or "")
    assert "\x1b" not in tb_summary.truncated_stream
    assert "[CRASH DIAGNOSTIC BLOCK]" in tb_summary.truncated_stream


# =============================================================================
# 7. MARKDOWN DOCUMENTATION CHUNKER TESTS
# =============================================================================

def test_chunk_markdown_by_headers() -> None:
    """Verifies chunking of markdown text preserving code blocks and LaTeX math."""
    sample_md = """# Title: Quantum Chemical Calculation

This is an introductory paragraph.

## Section 1: Theory
Here is a mathematical derivation:
$$
E = \\langle \\Psi | \\hat{H} | \\Psi \\rangle
$$

## Section 2: Code Implementation
```python
def solve_hf(mol):
    return mol.hf()
```

| Method | Accuracy |
|---|---|
| CCSD(T) | 0.05 kcal/mol |
| DFT | 2.0 kcal/mol |
"""
    chunks = chunk_markdown_by_headers(sample_md, max_chunk_chars=500)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert isinstance(chunk, MarkdownChunkModel)
        assert len(chunk.content) > 0
        assert chunk.token_estimate > 0

    code_chunk = [c for c in chunks if c.has_code_block]
    assert len(code_chunk) > 0

    latex_chunk = [c for c in chunks if c.has_latex]
    assert len(latex_chunk) > 0


# =============================================================================
# 8. DYNAMIC MENDELEEV MOLECULAR GEOMETRY TESTS
# =============================================================================

def test_compress_molecular_geometry_mendeleev() -> None:
    """Verifies molecular geometry compression using dynamic Mendeleev atomic masses."""
    symbols = ["O", "H", "H"]
    coords = np.array([
        [0.0, 0.0, 0.1173],
        [0.0, 0.7572, -0.4692],
        [0.0, -0.7572, -0.4692],
    ], dtype=np.float64)

    summary = compress_molecular_geometry(symbols, coords, compute_com=True)
    assert summary["num_atoms"] == 3
    assert 18.0 < summary["total_mass_amu"] < 18.02
    assert len(summary["principal_moments_amu_angstrom2"]) == 3
    assert summary["symbols"] == ["O", "H", "H"]


# =============================================================================
# 9. UNIFIED CONTEXT COMPRESSOR WRAPPER TESTS
# =============================================================================

def test_unified_context_compressor_workflow() -> None:
    """Verifies unified ContextCompressor / CoreContextCompressor execution."""
    compressor = ContextCompressor(
        tensor_threshold=100,
        array_threshold=50,
        lttb_max_points=50,
    )
    assert isinstance(compressor, CoreContextCompressor)

    # 1. Curve Decimation
    x = np.arange(500, dtype=np.float64) * 0.02
    y = np.exp(-x)
    dec_x, dec_y = compressor.decimate_curve(y, x=x)
    assert len(dec_x) == 50

    # 2. JSON Serialization
    payload = {"data": list(range(200)), "val": 1.23}
    json_out = compressor.to_json(payload)
    assert '"Min": 0.0' in json_out

    # 3. Telemetry Dictionary
    arr_dict = compressor.compress_to_dict(list(range(100)))
    assert arr_dict["Array_Max"] == 99.0


# =============================================================================
# 10. AST-LEVEL COMPLIANCE STATIC ANALYSIS OF TEST & IMPLEMENTATION
# =============================================================================

def test_compliance_mandate_on_source_and_test() -> None:
    """
    Performs static AST analysis over both cochem_core_context_compressor.py
    and test_cochem_core_context_compressor.py asserting 0 mock/stub/fake usages.
    """
    current_test_file = Path(__file__).resolve()
    target_source_file = current_test_file.parent.parent / "core_engine" / "cochem_core_context_compressor.py"

    assert target_source_file.exists(), f"Source file does not exist: {target_source_file}"

    from ci_tools.anti_spoof_linter import BANNED_MOCK_MODULES, BANNED_MOCK_ATTRIBUTES
    banned_terms = set(BANNED_MOCK_ATTRIBUTES) | {"mock", "Mock", "mock_open"}

    for file_path in [current_test_file, target_source_file]:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in BANNED_MOCK_MODULES, (
                        f"Zero-Mock Violation: Found import '{alias.name}' in {file_path}"
                    )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module not in BANNED_MOCK_MODULES, (
                    f"Zero-Mock Violation: Found 'from {module}' in {file_path}"
                )
                for alias in node.names:
                    assert alias.name not in banned_terms, (
                        f"Zero-Mock Violation: Found imported symbol '{alias.name}' in {file_path}"
                    )
