"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.interfaces.web_matrices.

Validates Pydantic v2 data models, WebSparsityMatrix coordinate operations, bounds enforcement,
NumPy conversions, BrowserSparsity-004 little-endian binary packing (<i4, <f4), base64 decoding,
dunder protocols, error handling, LF line endings, and zero personal path leakage.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import cochem_base.interfaces as interfaces
from cochem_base.interfaces.web_matrices import (
    BrowserSparsityPayload,
    MatrixElement,
    SparsityDimensions,
    WebSparsityMatrix,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/web_matrices.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "web_matrices.py"
    assert path.is_file(), f"Target file does not exist at {path}"
    return path


@pytest.fixture
def target_test_path() -> Path:
    """Return the absolute path to test_suite/test_web_matrices.py."""
    path = Path(__file__).resolve()
    assert path.is_file(), f"Test file does not exist at {path}"
    return path


# ============================================================================
# Section 1: File Encoding, LF Line Endings, and Zero Path Leakage
# ============================================================================


def test_file_encoding_and_lf_line_endings(target_file_path: Path, target_test_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    for file_path in [target_file_path, target_test_path]:
        raw = file_path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {file_path.name}"
        assert b"\n" in raw, f"Missing newline characters in {file_path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {file_path.name}"

        content = file_path.read_text(encoding="utf-8")
        assert len(content) > 300, f"File {file_path.name} content is unexpectedly small."


def test_zero_personal_path_leaks(target_file_path: Path, target_test_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in source and test files."""
    patterns = leak_patterns()
    for file_path in [target_file_path, target_test_path]:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {file_path.name}: {leaks}"


def test_module_all_exports() -> None:
    """Verify __all__ contains all required classes."""
    import cochem_base.interfaces.web_matrices as wm

    expected = ["BrowserSparsityPayload", "MatrixElement", "SparsityDimensions", "WebSparsityMatrix"]
    assert hasattr(wm, "__all__")
    assert sorted(wm.__all__) == sorted(expected)
    for sym in expected:
        assert hasattr(wm, sym)


def test_interfaces_package_lazy_resolution() -> None:
    """Verify interfaces package exposes web_matrices symbols via PEP 562."""
    assert interfaces.WebSparsityMatrix is WebSparsityMatrix
    assert interfaces.BrowserSparsityPayload is BrowserSparsityPayload
    assert interfaces.MatrixElement is MatrixElement
    assert interfaces.SparsityDimensions is SparsityDimensions


# ============================================================================
# Section 2: Pydantic v2 Models Validation
# ============================================================================


def test_sparsity_dimensions_model() -> None:
    """Validate SparsityDimensions Pydantic model behavior."""
    dims = SparsityDimensions(rows=10, cols=20)
    assert dims.rows == 10
    assert dims.cols == 20
    assert dims.total_elements == 200
    assert not dims.is_square
    assert dims.as_tuple() == (10, 20)
    assert dims.model_dump() == {"rows": 10, "cols": 20}

    # Square dimension
    sq_dims = SparsityDimensions(rows=15, cols=15)
    assert sq_dims.is_square

    # Zero dimensions are allowed
    zero_dims = SparsityDimensions(rows=0, cols=0)
    assert zero_dims.rows == 0
    assert zero_dims.cols == 0
    assert zero_dims.total_elements == 0
    assert zero_dims.is_square

    # Negative dimensions must raise ValidationError
    with pytest.raises(ValidationError):
        SparsityDimensions(rows=-1, cols=5)
    with pytest.raises(ValidationError):
        SparsityDimensions(rows=5, cols=-1)

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        SparsityDimensions(rows=10, cols=10, extra_field=123)  # type: ignore[call-arg]


def test_matrix_element_model() -> None:
    """Validate MatrixElement Pydantic model behavior."""
    elem = MatrixElement(row=3, col=4, value=12.75)
    assert elem.row == 3
    assert elem.col == 4
    assert elem.value == 12.75
    assert elem.coord == (3, 4)
    assert elem.as_tuple() == (3, 4, 12.75)
    assert elem.model_dump() == {"row": 3, "col": 4, "value": 12.75}

    # Float casting
    elem_int = MatrixElement(row=0, col=0, value=5)
    assert isinstance(elem_int.value, float)
    assert elem_int.value == 5.0

    # Negative coordinates must raise ValidationError
    with pytest.raises(ValidationError):
        MatrixElement(row=-1, col=0, value=1.0)
    with pytest.raises(ValidationError):
        MatrixElement(row=0, col=-1, value=1.0)


def test_browser_sparsity_payload_model() -> None:
    """Validate BrowserSparsityPayload model and base64 operations."""
    dims = SparsityDimensions(rows=4, cols=4)
    payload = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64="",
        cols_b64="",
        vals_b64="",
    )
    assert payload.version == "BrowserSparsity-004"
    assert payload.dimensions.rows == 4
    assert payload.dimensions.cols == 4

    # Empty payload decoding
    r_arr, c_arr, v_arr = payload.decode_coo()
    assert len(r_arr) == 0
    assert len(c_arr) == 0
    assert len(v_arr) == 0
    assert r_arr.dtype == np.dtype("<i4")
    assert c_arr.dtype == np.dtype("<i4")
    assert v_arr.dtype == np.dtype("<f4")

    # to_matrix from empty payload
    mat = payload.to_matrix()
    assert mat.rows == 4
    assert mat.cols == 4
    assert mat.nnz == 0
    assert mat.is_empty


# ============================================================================
# Section 3: WebSparsityMatrix Construction & Factory Classmethods
# ============================================================================


def test_matrix_init_empty() -> None:
    """Verify basic matrix construction without initial data."""
    mat = WebSparsityMatrix(rows=5, cols=10)
    assert mat.rows == 5
    assert mat.cols == 10
    assert mat.shape == (5, 10)
    assert mat.nnz == 0
    assert mat.density == 0.0
    assert mat.is_empty
    assert not mat.is_square
    assert mat.data_dict == {}


def test_matrix_init_with_dict_elements() -> None:
    """Verify matrix construction with dictionary elements."""
    data = [
        {"row": 0, "col": 1, "value": 2.5},
        {"row": 3, "col": 4, "value": -1.25},
    ]
    mat = WebSparsityMatrix(rows=5, cols=5, data=data)
    assert mat.nnz == 2
    assert mat.get_element(0, 1) == 2.5
    assert mat.get_element(3, 4) == -1.25
    assert not mat.is_empty
    assert mat.is_square


def test_matrix_init_with_matrix_element_instances() -> None:
    """Verify matrix construction with MatrixElement instances."""
    data = [
        MatrixElement(row=1, col=2, value=3.14),
        MatrixElement(row=2, col=3, value=2.718),
    ]
    mat = WebSparsityMatrix(rows=4, cols=4, data=data)
    assert mat.nnz == 2
    assert mat[1, 2] == pytest.approx(3.14)
    assert mat[2, 3] == pytest.approx(2.718)


def test_matrix_init_with_tuples() -> None:
    """Verify matrix construction with 3-tuples (row, col, value)."""
    data = [(0, 0, 1.0), (1, 1, 2.0), (2, 2, 3.0)]
    mat = WebSparsityMatrix(rows=3, cols=3, data=data)
    assert mat.nnz == 3
    assert mat[0, 0] == 1.0
    assert mat[1, 1] == 2.0
    assert mat[2, 2] == 3.0


def test_matrix_init_invalid_data() -> None:
    """Verify matrix construction raises ValueError on invalid data items."""
    with pytest.raises(ValueError, match="Unsupported element data format"):
        WebSparsityMatrix(rows=3, cols=3, data=["invalid_string"])  # type: ignore[list-item]

    with pytest.raises(ValueError, match="Unsupported element data format"):
        WebSparsityMatrix(rows=3, cols=3, data=[(0, 1)])  # type: ignore[list-item]


def test_matrix_init_negative_dimensions() -> None:
    """Verify matrix construction raises ValueError for negative dimensions."""
    with pytest.raises(ValueError, match="Matrix dimensions must be non-negative"):
        WebSparsityMatrix(rows=-1, cols=5)
    with pytest.raises(ValueError, match="Matrix dimensions must be non-negative"):
        WebSparsityMatrix(rows=5, cols=-2)


def test_from_dense_factory() -> None:
    """Verify construction from 2D dense numpy array and nested lists."""
    dense_arr = np.array([
        [1.0, 0.0, 0.0],
        [0.0, -4.5, 0.0],
        [0.0, 0.0, 9.2],
    ], dtype=np.float32)

    mat = WebSparsityMatrix.from_dense(dense_arr)
    assert mat.shape == (3, 3)
    assert mat.nnz == 3
    assert mat[0, 0] == 1.0
    assert mat[1, 1] == -4.5
    assert mat[2, 2] == pytest.approx(9.2)
    assert mat[0, 1] == 0.0

    # From nested list
    nested = [[0.0, 3.0], [4.0, 0.0]]
    mat2 = WebSparsityMatrix.from_dense(nested)
    assert mat2.shape == (2, 2)
    assert mat2.nnz == 2
    assert mat2[0, 1] == 3.0
    assert mat2[1, 0] == 4.0

    # Non-2D dense array raises ValueError
    with pytest.raises(ValueError, match="Dense matrix must be 2-dimensional"):
        WebSparsityMatrix.from_dense(np.array([1.0, 2.0, 3.0]))


def test_from_coo_factory() -> None:
    """Verify construction from coordinate sequences."""
    rows = [0, 1, 2]
    cols = [2, 1, 0]
    vals = [7.5, 8.5, 9.5]

    # Inferred shape
    mat = WebSparsityMatrix.from_coo(rows, cols, vals)
    assert mat.shape == (3, 3)
    assert mat.nnz == 3
    assert mat[0, 2] == 7.5
    assert mat[1, 1] == 8.5
    assert mat[2, 0] == 9.5

    # Explicit shape
    mat_explicit = WebSparsityMatrix.from_coo(rows, cols, vals, shape=(10, 10))
    assert mat_explicit.shape == (10, 10)
    assert mat_explicit.nnz == 3

    # Empty COO
    mat_empty = WebSparsityMatrix.from_coo([], [], [])
    assert mat_empty.shape == (0, 0)
    assert mat_empty.nnz == 0

    # Length mismatch raises ValueError
    with pytest.raises(ValueError, match="Length mismatch among COO arrays"):
        WebSparsityMatrix.from_coo([0, 1], [0], [1.0, 2.0])


def test_from_dict_factory() -> None:
    """Verify construction from dictionary representations."""
    d = {
        "rows": 4,
        "cols": 6,
        "elements": [
            {"row": 1, "col": 2, "value": 5.0},
            {"row": 3, "col": 5, "value": -3.0},
        ],
    }
    mat = WebSparsityMatrix.from_dict(d)
    assert mat.shape == (4, 6)
    assert mat.nnz == 2
    assert mat[1, 2] == 5.0
    assert mat[3, 5] == -3.0

    # Missing rows/cols raises ValueError
    with pytest.raises(ValueError, match="Dictionary must contain 'rows' and 'cols' keys"):
        WebSparsityMatrix.from_dict({"elements": []})


def test_identity_factory() -> None:
    """Verify diagonal identity matrix generation."""
    eye = WebSparsityMatrix.identity(4)
    assert eye.shape == (4, 4)
    assert eye.nnz == 4
    for i in range(4):
        for j in range(4):
            if i == j:
                assert eye[i, j] == 1.0
            else:
                assert eye[i, j] == 0.0

    # Custom scalar value
    scaled_eye = WebSparsityMatrix.identity(3, value=5.5)
    assert scaled_eye.shape == (3, 3)
    assert scaled_eye.nnz == 3
    for i in range(3):
        assert scaled_eye[i, i] == 5.5

    # Negative dimension raises ValueError
    with pytest.raises(ValueError, match="Matrix dimension n must be non-negative"):
        WebSparsityMatrix.identity(-1)


# ============================================================================
# Section 4: Bounds Validation and Exception Handling
# ============================================================================


def test_bounds_validation_add_element() -> None:
    """Verify add_element raises ValueError on out-of-bounds indices."""
    mat = WebSparsityMatrix(rows=3, cols=3)
    with pytest.raises(ValueError, match=r"Index out of bounds: \(-1, 0\) for dimensions \(3, 3\)"):
        mat.add_element(-1, 0, 1.0)

    with pytest.raises(ValueError, match=r"Index out of bounds: \(0, -1\) for dimensions \(3, 3\)"):
        mat.add_element(0, -1, 1.0)

    with pytest.raises(ValueError, match=r"Index out of bounds: \(3, 1\) for dimensions \(3, 3\)"):
        mat.add_element(3, 1, 1.0)

    with pytest.raises(ValueError, match=r"Index out of bounds: \(1, 3\) for dimensions \(3, 3\)"):
        mat.add_element(1, 3, 1.0)


def test_bounds_validation_get_and_remove_element() -> None:
    """Verify get_element and remove_element bounds checks."""
    mat = WebSparsityMatrix(rows=2, cols=2)
    with pytest.raises(ValueError, match="Index out of bounds"):
        mat.get_element(2, 0)

    with pytest.raises(ValueError, match="Index out of bounds"):
        mat.remove_element(0, 2)


def test_bounds_validation_dunder_indexing() -> None:
    """Verify __getitem__, __setitem__, and __delitem__ bounds checks."""
    mat = WebSparsityMatrix(rows=2, cols=2)

    with pytest.raises(ValueError, match="Index out of bounds"):
        _ = mat[2, 0]

    with pytest.raises(ValueError, match="Index out of bounds"):
        mat[0, 2] = 1.0

    with pytest.raises(ValueError, match="Index out of bounds"):
        del mat[5, 5]


def test_type_error_on_invalid_key_type() -> None:
    """Verify TypeError when non-2-tuple is provided for indexing."""
    mat = WebSparsityMatrix(rows=3, cols=3)

    with pytest.raises(TypeError, match="Index must be a 2-tuple"):
        _ = mat[0]  # type: ignore[index]

    with pytest.raises(TypeError, match="Index must be a 2-tuple"):
        mat[(0, 1, 2)] = 5.0  # type: ignore[index]

    with pytest.raises(TypeError, match="Index must be a 2-tuple"):
        del mat["0,1"]  # type: ignore[arg-type,index]


# ============================================================================
# Section 5: Python Dunder Protocols
# ============================================================================


def test_dunder_indexing_and_defaults() -> None:
    """Verify __getitem__ returns stored value or 0.0 default for in-bounds coordinates."""
    mat = WebSparsityMatrix(rows=4, cols=4)
    mat[1, 2] = 42.0
    assert mat[1, 2] == 42.0
    assert mat[0, 0] == 0.0
    assert mat[3, 3] == 0.0


def test_dunder_deletion() -> None:
    """Verify __delitem__ removes stored element and raises KeyError for unstored."""
    mat = WebSparsityMatrix(rows=3, cols=3)
    mat[1, 1] = 10.0
    assert (1, 1) in mat
    assert len(mat) == 1

    del mat[1, 1]
    assert (1, 1) not in mat
    assert len(mat) == 0
    assert mat[1, 1] == 0.0

    # Deleting unstored element raises KeyError
    with pytest.raises(KeyError, match=r"Element at \(1, 1\) is not explicitly stored"):
        del mat[1, 1]


def test_dunder_contains() -> None:
    """Verify __contains__ returns True for stored elements, False otherwise."""
    mat = WebSparsityMatrix(rows=3, cols=3)
    mat[0, 2] = 7.0

    assert (0, 2) in mat
    assert (0, 0) not in mat
    assert (5, 5) not in mat
    assert "not_a_tuple" not in mat


def test_dunder_iter_and_len() -> None:
    """Verify __iter__ yields sorted elements and __len__ matches nnz."""
    mat = WebSparsityMatrix(rows=3, cols=3)
    mat[2, 1] = 3.0
    mat[0, 2] = 1.0
    mat[1, 0] = 2.0

    assert len(mat) == 3
    assert mat.nnz == 3

    items = list(mat)
    assert items == [(0, 2, 1.0), (1, 0, 2.0), (2, 1, 3.0)]


def test_dunder_repr() -> None:
    """Verify __repr__ provides clear human-readable structure."""
    mat = WebSparsityMatrix(rows=5, cols=8)
    mat[1, 1] = 3.0
    assert repr(mat) == "WebSparsityMatrix(rows=5, cols=8, nnz=1)"


def test_dunder_eq() -> None:
    """Verify __eq__ comparison between matrices."""
    mat1 = WebSparsityMatrix(rows=3, cols=3)
    mat1[0, 1] = 5.0
    mat1[2, 2] = 10.0

    mat2 = WebSparsityMatrix(rows=3, cols=3)
    mat2[0, 1] = 5.0
    mat2[2, 2] = 10.0

    assert mat1 == mat2

    # Different shapes
    mat3 = WebSparsityMatrix(rows=4, cols=3)
    assert mat1 != mat3

    # Different values
    mat4 = WebSparsityMatrix(rows=3, cols=3)
    mat4[0, 1] = 5.0
    mat4[2, 2] = 9.9
    assert mat1 != mat4

    # Compared with non-WebSparsityMatrix
    assert mat1 != {"rows": 3, "cols": 3}
    assert mat1 != np.zeros((3, 3))


# ============================================================================
# Section 6: Matrix Operations, Pruning, and Conversions
# ============================================================================


def test_density_and_is_empty_properties() -> None:
    """Verify density calculation and is_empty property."""
    # 0x0 matrix
    zero_mat = WebSparsityMatrix(0, 0)
    assert zero_mat.density == 0.0
    assert zero_mat.is_empty

    # 4x5 matrix with 2 non-zeros -> density = 2 / 20 = 0.1
    mat = WebSparsityMatrix(rows=4, cols=5)
    assert mat.density == 0.0
    assert mat.is_empty

    mat[0, 0] = 1.0
    mat[1, 1] = 2.0
    assert mat.density == pytest.approx(0.1)
    assert not mat.is_empty


def test_get_and_remove_element() -> None:
    """Verify get_element and remove_element behaviors."""
    mat = WebSparsityMatrix(rows=3, cols=3)
    mat[1, 1] = 42.0

    assert mat.get_element(1, 1) == 42.0
    assert mat.get_element(0, 0) == 0.0
    assert mat.get_element(0, 0, default=-1.0) == -1.0

    removed = mat.remove_element(1, 1)
    assert removed == 42.0
    assert (1, 1) not in mat
    assert mat.nnz == 0

    # Removing already absent element returns None
    assert mat.remove_element(1, 1) is None


def test_prune_zeros() -> None:
    """Verify prune_zeros removes entries near or equal to zero."""
    mat = WebSparsityMatrix(rows=4, cols=4)
    mat[0, 0] = 0.0
    mat[0, 1] = 1e-15
    mat[1, 1] = 5.0
    mat[2, 2] = -1e-14
    mat[3, 3] = 2.5

    assert mat.nnz == 5
    pruned_count = mat.prune_zeros(tolerance=1e-12)
    assert pruned_count == 3
    assert mat.nnz == 2
    assert (1, 1) in mat
    assert (3, 3) in mat
    assert (0, 0) not in mat
    assert (0, 1) not in mat
    assert (2, 2) not in mat


def test_clear() -> None:
    """Verify clear empties the matrix."""
    mat = WebSparsityMatrix.identity(5)
    assert mat.nnz == 5
    mat.clear()
    assert mat.nnz == 0
    assert mat.is_empty
    assert len(mat.data_dict) == 0


def test_to_dense_round_trip() -> None:
    """Verify to_dense accurate conversion to 2D numpy array."""
    dense_expected = np.array([
        [0.0, 1.5, 0.0],
        [0.0, 0.0, -2.5],
        [3.0, 0.0, 0.0],
    ], dtype=np.float32)

    mat = WebSparsityMatrix.from_dense(dense_expected)
    dense_actual = mat.to_dense()

    assert dense_actual.dtype == np.float32
    assert np.allclose(dense_actual, dense_expected)


def test_to_dict_export() -> None:
    """Verify to_dict produces valid dictionary export."""
    mat = WebSparsityMatrix(rows=2, cols=3)
    mat[0, 1] = 4.0
    mat[1, 2] = 8.0

    d = mat.to_dict()
    assert d["rows"] == 2
    assert d["cols"] == 3
    assert len(d["elements"]) == 2
    assert d["elements"] == [
        {"row": 0, "col": 1, "value": 4.0},
        {"row": 1, "col": 2, "value": 8.0},
    ]

    # Reconstruct from dict
    mat_reconstructed = WebSparsityMatrix.from_dict(d)
    assert mat_reconstructed == mat


# ============================================================================
# Section 7: Little-Endian Binary Packing & BrowserSparsity-004 Protocol
# ============================================================================


def test_binary_packing_types_and_little_endian() -> None:
    """Verify to_coo_arrays produces strictly little-endian '<i4' and '<f4' arrays."""
    mat = WebSparsityMatrix(rows=5, cols=5)
    mat[0, 1] = 10.5
    mat[3, 4] = -20.25

    rows_arr, cols_arr, vals_arr = mat.to_coo_arrays()

    assert rows_arr.dtype == np.dtype("<i4")
    assert cols_arr.dtype == np.dtype("<i4")
    assert vals_arr.dtype == np.dtype("<f4")

    assert np.array_equal(rows_arr, np.array([0, 3], dtype="<i4"))
    assert np.array_equal(cols_arr, np.array([1, 4], dtype="<i4"))
    assert np.allclose(vals_arr, np.array([10.5, -20.25], dtype="<f4"))


def test_browser_sparsity_round_trip() -> None:
    """Verify full round-trip serialization and deserialization via BrowserSparsityPayload."""
    mat = WebSparsityMatrix(rows=10, cols=12)
    # Populate a set of distinct values
    test_entries = [
        (0, 0, 1.0),
        (0, 5, 2.5),
        (2, 3, -4.75),
        (9, 11, 100.125),
    ]
    for r, c, v in test_entries:
        mat[r, c] = v

    payload = mat.to_browser_format()
    assert isinstance(payload, BrowserSparsityPayload)
    assert payload.version == "BrowserSparsity-004"
    assert payload.dimensions.rows == 10
    assert payload.dimensions.cols == 12

    # Check that base64 strings are non-empty
    assert len(payload.rows_b64) > 0
    assert len(payload.cols_b64) > 0
    assert len(payload.vals_b64) > 0

    # Reconstruct via payload.to_matrix()
    mat_reconstructed = payload.to_matrix()
    assert mat_reconstructed.shape == (10, 12)
    assert mat_reconstructed.nnz == 4
    for r, c, v in test_entries:
        assert mat_reconstructed[r, c] == pytest.approx(v, rel=1e-5)

    assert mat == mat_reconstructed


def test_from_browser_format_json_and_dict() -> None:
    """Verify from_browser_format accepts dict and JSON string inputs."""
    mat = WebSparsityMatrix.identity(3, value=4.0)
    payload = mat.to_browser_format()

    # From dict
    payload_dict = payload.model_dump()
    mat_from_dict = WebSparsityMatrix.from_browser_format(payload_dict)
    assert mat_from_dict == mat

    # From JSON string
    payload_json = payload.model_dump_json()
    mat_from_json = WebSparsityMatrix.from_browser_format(payload_json)
    assert mat_from_json == mat

    # Invalid input type raises TypeError
    with pytest.raises(TypeError, match="Expected BrowserSparsityPayload, dict, or JSON str"):
        WebSparsityMatrix.from_browser_format(12345)  # type: ignore[arg-type]


# ============================================================================
# Section 8: Error Handling for Malformed / Corrupted Payloads
# ============================================================================


def test_decode_coo_corrupted_base64() -> None:
    """Verify decode_coo raises ValueError on invalid base64 encoding."""
    dims = SparsityDimensions(rows=5, cols=5)
    payload = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64="!!!NOT_BASE64!!!",
        cols_b64="",
        vals_b64="",
    )
    with pytest.raises(ValueError, match="Failed to decode base64 sparsity payload"):
        payload.decode_coo()


def test_decode_coo_misaligned_bytes() -> None:
    """Verify decode_coo raises ValueError when byte buffer length is not a multiple of 4."""
    dims = SparsityDimensions(rows=5, cols=5)
    bad_bytes_b64 = base64.b64encode(b"\x01\x02\x03\x04\x05").decode("ascii")
    valid_bytes_b64 = base64.b64encode(np.array([0], dtype="<i4").tobytes()).decode("ascii")

    # Misaligned rows
    payload_row = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64=bad_bytes_b64,
        cols_b64=valid_bytes_b64,
        vals_b64=valid_bytes_b64,
    )
    with pytest.raises(ValueError, match=r"Row buffer byte length \(5\) is not a multiple of 4"):
        payload_row.decode_coo()

    # Misaligned cols
    payload_col = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64=valid_bytes_b64,
        cols_b64=bad_bytes_b64,
        vals_b64=valid_bytes_b64,
    )
    with pytest.raises(ValueError, match=r"Col buffer byte length \(5\) is not a multiple of 4"):
        payload_col.decode_coo()

    # Misaligned vals
    payload_val = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64=valid_bytes_b64,
        cols_b64=valid_bytes_b64,
        vals_b64=bad_bytes_b64,
    )
    with pytest.raises(ValueError, match=r"Val buffer byte length \(5\) is not a multiple of 4"):
        payload_val.decode_coo()


def test_decode_coo_mismatched_array_lengths() -> None:
    """Verify decode_coo raises ValueError when row, col, and val lengths mismatch."""
    dims = SparsityDimensions(rows=5, cols=5)
    rows_bytes = np.array([0, 1], dtype="<i4").tobytes()
    cols_bytes = np.array([0], dtype="<i4").tobytes()
    vals_bytes = np.array([1.0, 2.0], dtype="<f4").tobytes()

    payload = BrowserSparsityPayload(
        version="BrowserSparsity-004",
        dimensions=dims,
        rows_b64=base64.b64encode(rows_bytes).decode("ascii"),
        cols_b64=base64.b64encode(cols_bytes).decode("ascii"),
        vals_b64=base64.b64encode(vals_bytes).decode("ascii"),
    )

    with pytest.raises(ValueError, match="Mismatched COO array lengths: rows=2, cols=1, vals=2"):
        payload.decode_coo()


# ============================================================================
# Section 9: Sparse Matrix Arithmetic & Linear Algebra
# ============================================================================


def test_matrix_addition_and_subtraction() -> None:
    """Verify elementwise addition and subtraction between sparse matrices."""
    A = WebSparsityMatrix(3, 3, data=[(0, 0, 2.0), (1, 2, 3.0)])
    B = WebSparsityMatrix(3, 3, data=[(0, 0, 1.0), (1, 2, -3.0), (2, 1, 4.0)])

    C = A + B
    assert C[0, 0] == 3.0
    assert C[1, 2] == 0.0
    assert C[2, 1] == 4.0
    assert (1, 2) not in C.data_dict  # Cancelled element pruned

    D = A - B
    assert D[0, 0] == 1.0
    assert D[1, 2] == 6.0
    assert D[2, 1] == -4.0

    # In-place operations
    A_copy = A.copy()
    A_copy += B
    assert A_copy == C

    A_copy -= B
    assert A_copy == A

    # Shape mismatch error
    Mismatched = WebSparsityMatrix(4, 3)
    with pytest.raises(ValueError, match="Matrix shape mismatch"):
        _ = A + Mismatched


def test_scalar_multiplication_and_division() -> None:
    """Verify scalar multiplication, division, negation, and in-place scaling."""
    A = WebSparsityMatrix(3, 3, data=[(0, 1, 4.0), (2, 2, -8.0)])

    # Multiplication
    B = A * 2.5
    assert B[0, 1] == 10.0
    assert B[2, 2] == -20.0

    # Reverse multiplication
    C = 2.5 * A
    assert C == B

    # Division
    D = A / 2.0
    assert D[0, 1] == 2.0
    assert D[2, 2] == -4.0

    # Division by zero
    with pytest.raises(ZeroDivisionError):
        _ = A / 0.0

    # Negation
    neg_A = -A
    assert neg_A[0, 1] == -4.0
    assert neg_A[2, 2] == 8.0

    # Unary positive
    pos_A = +A
    assert pos_A == A


def test_matrix_multiplication() -> None:
    """Verify matrix-matrix multiplication (sparse @ sparse), matrix-vector, and matrix-dense."""
    A = WebSparsityMatrix(2, 3, data=[(0, 0, 1.0), (0, 1, 2.0), (1, 1, 3.0), (1, 2, 4.0)])
    B = WebSparsityMatrix(3, 2, data=[(0, 0, 1.0), (1, 0, 2.0), (1, 1, 1.0), (2, 1, 3.0)])

    AB = A @ B
    assert isinstance(AB, WebSparsityMatrix)
    assert AB.shape == (2, 2)
    assert AB[0, 0] == 5.0
    assert AB[0, 1] == 2.0
    assert AB[1, 0] == 6.0
    assert AB[1, 1] == 15.0

    # Matrix-vector product (2, 3) @ (3,) -> (2,)
    x = np.array([2.0, -1.0, 3.0], dtype=np.float32)
    y = A @ x
    assert isinstance(y, np.ndarray)
    assert y.shape == (2,)
    assert y[0] == 0.0
    assert y[1] == 9.0

    # Matrix-dense product (2, 3) @ (3, 2)
    X_dense = np.array([[1.0, 0.0], [2.0, 1.0], [0.0, 3.0]], dtype=np.float32)
    Y_dense = A @ X_dense
    assert isinstance(Y_dense, np.ndarray)
    assert Y_dense.shape == (2, 2)
    assert np.allclose(Y_dense, np.array([[5.0, 2.0], [6.0, 15.0]]))

    # Incompatible dimensions
    with pytest.raises(ValueError, match="Dimension mismatch"):
        _ = A @ WebSparsityMatrix(4, 2)


def test_matrix_trace_diagonal_symmetric_bandwidth() -> None:
    """Verify trace, diagonal extraction, is_symmetric, and bandwidth calculation."""
    mat = WebSparsityMatrix(4, 4)
    mat[0, 0] = 1.0
    mat[1, 1] = 2.0
    mat[2, 2] = 3.0
    mat[3, 3] = 4.0
    mat[0, 2] = 5.0
    mat[2, 0] = 5.0

    assert mat.trace() == 10.0
    assert np.array_equal(mat.diagonal(), np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32))
    assert mat.is_symmetric()

    kl, ku = mat.bandwidth()
    assert kl == 2
    assert ku == 2

    # Non-symmetric matrix
    mat[1, 3] = 7.0
    assert not mat.is_symmetric()

    # Trace on non-square matrix raises ValueError
    non_sq = WebSparsityMatrix(3, 4)
    with pytest.raises(ValueError, match="Trace only defined for square matrices"):
        non_sq.trace()


def test_matrix_norms() -> None:
    """Verify Frobenius norm, 1-norm, and infinity-norm."""
    mat = WebSparsityMatrix(2, 2, data=[(0, 0, 3.0), (0, 1, -4.0), (1, 1, 5.0)])

    # Frobenius norm: sqrt(9 + 16 + 25) = sqrt(50) = 7.0710678
    assert mat.norm("fro") == pytest.approx(np.sqrt(50.0))

    # 1-norm: max column sum
    assert mat.norm(1) == pytest.approx(9.0)

    # Inf-norm: max row sum
    assert mat.norm(np.inf) == pytest.approx(7.0)


# ============================================================================
# Section 10: Matrix Slicing & Submatrix Operations
# ============================================================================


def test_matrix_slicing_retrieval_and_assignment() -> None:
    """Verify slicing access matrix[r_slice, c_slice] and slice assignments."""
    mat = WebSparsityMatrix(5, 5)
    for i in range(5):
        for j in range(5):
            if (i + j) % 2 == 0:
                mat[i, j] = float(i * 10 + j)

    # Slice submatrix of rows 1:4 and cols 1:4 (size 3x3)
    sub = mat[1:4, 1:4]
    assert isinstance(sub, WebSparsityMatrix)
    assert sub.shape == (3, 3)
    assert sub[0, 0] == 11.0
    assert sub[0, 2] == 13.0
    assert sub[1, 1] == 22.0

    # Submatrix assignment
    replacement = WebSparsityMatrix(3, 3, data=[(0, 0, 99.0), (1, 1, 88.0)])
    mat[1:4, 1:4] = replacement
    assert mat[1, 1] == 99.0
    assert mat[2, 2] == 88.0
    assert mat[1, 3] == 0.0  # Cleared by submatrix assignment


# ============================================================================
# Section 11: CSR and CSC Conversions
# ============================================================================


def test_csr_and_csc_conversions() -> None:
    """Verify CSR and CSC array extraction and reconstruction."""
    dense = np.array([
        [1.0, 0.0, 2.0],
        [0.0, 3.0, 0.0],
        [4.0, 5.0, 6.0],
    ], dtype=np.float32)

    mat = WebSparsityMatrix.from_dense(dense)

    # CSR round-trip
    indptr_r, indices_c, data_csr = mat.to_csr_arrays()
    assert indptr_r.dtype == np.dtype("<i4")
    assert indices_c.dtype == np.dtype("<i4")
    assert data_csr.dtype == np.dtype("<f4")
    assert len(indptr_r) == 4  # rows + 1
    assert len(indices_c) == mat.nnz == 6

    mat_csr = WebSparsityMatrix.from_csr(indptr_r, indices_c, data_csr, shape=(3, 3))
    assert mat_csr == mat

    # CSC round-trip
    indptr_c, indices_r, data_csc = mat.to_csc_arrays()
    assert indptr_c.dtype == np.dtype("<i4")
    assert indices_r.dtype == np.dtype("<i4")
    assert data_csc.dtype == np.dtype("<f4")
    assert len(indptr_c) == 4  # cols + 1

    mat_csc = WebSparsityMatrix.from_csc(indptr_c, indices_r, data_csc, shape=(3, 3))
    assert mat_csc == mat


# ============================================================================
# Section 12: Advanced Matrix Generators & Tensor Products
# ============================================================================


def test_kronecker_product() -> None:
    """Verify Kronecker product A ⊗ B."""
    A = WebSparsityMatrix.identity(2)
    B = WebSparsityMatrix(2, 2, data=[(0, 0, 1.0), (0, 1, 2.0), (1, 0, 3.0), (1, 1, 4.0)])

    kron_mat = WebSparsityMatrix.kron(A, B)
    assert kron_mat.shape == (4, 4)
    assert kron_mat.nnz == 8

    # Block (0, 0) is B
    assert kron_mat[0, 0] == 1.0
    assert kron_mat[0, 1] == 2.0
    assert kron_mat[1, 0] == 3.0
    assert kron_mat[1, 1] == 4.0

    # Block (1, 1) is B
    assert kron_mat[2, 2] == 1.0
    assert kron_mat[2, 3] == 2.0
    assert kron_mat[3, 2] == 3.0
    assert kron_mat[3, 3] == 4.0

    # Off-diagonal blocks are zero
    assert kron_mat[0, 2] == 0.0
    assert kron_mat[2, 0] == 0.0


def test_block_diag_assembly() -> None:
    """Verify assembling multiple matrices along the block diagonal."""
    A = WebSparsityMatrix.identity(2, value=5.0)
    B = WebSparsityMatrix(2, 3, data=[(0, 1, 7.0), (1, 2, 9.0)])
    C = WebSparsityMatrix.identity(1, value=3.0)

    composed = WebSparsityMatrix.block_diag([A, B, C])
    assert composed.shape == (5, 6)
    assert composed.nnz == 2 + 2 + 1 == 5

    # Check entries in block A
    assert composed[0, 0] == 5.0
    assert composed[1, 1] == 5.0

    # Check entries in block B
    assert composed[2, 3] == 7.0
    assert composed[3, 4] == 9.0

    # Check entries in block C
    assert composed[4, 5] == 3.0


def test_random_and_diag_generators() -> None:
    """Verify random sparse matrix and diagonal vector constructors."""
    diag_mat = WebSparsityMatrix.diag([10.0, 0.0, 20.0, 30.0])
    assert diag_mat.shape == (4, 4)
    assert diag_mat.nnz == 3
    assert diag_mat[0, 0] == 10.0
    assert diag_mat[1, 1] == 0.0
    assert diag_mat[2, 2] == 20.0
    assert diag_mat[3, 3] == 30.0

    rand_mat = WebSparsityMatrix.random(10, 10, density=0.15, seed=42)
    assert rand_mat.shape == (10, 10)
    assert rand_mat.nnz == 15
    assert rand_mat.density == pytest.approx(0.15)


# ============================================================================
# Section 13: Chunking, Transformations & JSON Serialization
# ============================================================================


def test_matrix_chunking_for_webgl() -> None:
    """Verify matrix partitioning into tile chunks."""
    mat = WebSparsityMatrix.identity(6, value=1.0)
    chunks = list(mat.to_chunks(chunk_rows=3, chunk_cols=3))

    assert len(chunks) == 4  # 2x2 grid of 3x3 chunks
    r0_c0 = chunks[0][2]
    assert r0_c0.shape == (3, 3)
    assert r0_c0.nnz == 3  # Diagonal entries 0, 1, 2

    r0_c1 = chunks[1][2]
    assert r0_c1.shape == (3, 3)
    assert r0_c1.nnz == 0  # Off-diagonal tile is empty


def test_transformations_and_json() -> None:
    """Verify clip, threshold, apply, and JSON serialization."""
    mat = WebSparsityMatrix(3, 3, data=[(0, 0, 1.5), (1, 1, -5.0), (2, 2, 10.0)])

    # Clip
    clipped = mat.clip(min_val=0.0, max_val=5.0)
    assert clipped[0, 0] == 1.5
    assert clipped[1, 1] == 0.0
    assert clipped[2, 2] == 5.0

    # Threshold
    thresh = mat.threshold(cutoff=2.0)
    assert thresh.nnz == 2
    assert (0, 0) not in thresh.data_dict
    assert thresh[1, 1] == -5.0
    assert thresh[2, 2] == 10.0

    # Apply unary function
    squared = mat.apply(lambda v: v ** 2)
    assert squared[0, 0] == pytest.approx(2.25)
    assert squared[1, 1] == pytest.approx(25.0)
    assert squared[2, 2] == pytest.approx(100.0)

    # JSON round-trip
    json_str = mat.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["rows"] == 3
    assert parsed["cols"] == 3
    assert len(parsed["elements"]) == 3
    mat_from_json = WebSparsityMatrix.from_json(json_str)
    assert mat_from_json == mat
