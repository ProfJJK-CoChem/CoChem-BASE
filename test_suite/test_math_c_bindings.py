"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.math.c_bindings.

Tests SafeCBuffer ctypes memory allocations, strict boundary overflow guards (BufferOverflow-009),
raw pointer extraction, Python sequence protocols (indexing, slicing, mutation, iteration),
zero-copy NumPy bridging, and memory management routines (fill, clear, copy).
"""

from __future__ import annotations

import ctypes
import math
from pathlib import Path

import numpy as np
import pytest

from cochem_base.math.c_bindings import SafeCBuffer
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def c_bindings_source_path() -> Path:
    """Return the absolute path to cochem_base/math/c_bindings.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "math" / "c_bindings.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_c_bindings_file_encoding_and_lf_endings(c_bindings_source_path: Path) -> None:
    """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
    raw = c_bindings_source_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/c_bindings.py"
    assert b"\n" in raw, "Missing newline characters in math/c_bindings.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in math/c_bindings.py"


def test_zero_personal_path_leaks_in_c_bindings(c_bindings_source_path: Path) -> None:
    """Verify zero personal machine or local username path leakage in c_bindings.py."""
    lines = c_bindings_source_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in c_bindings.py: {leaks}"


def test_safe_c_buffer_instantiation_and_properties() -> None:
    """Verify memory buffer initialization, size, itemsize, byte_size, and ctypes type."""
    buf = SafeCBuffer(10)
    assert buf.size == 10
    assert len(buf) == 10
    assert buf.itemsize == 8
    assert buf.byte_size == 80
    assert buf.DEFAULT_DTYPE == ctypes.c_double


def test_safe_c_buffer_invalid_size_validation() -> None:
    """Verify non-positive and non-integer buffer size allocations raise appropriate exceptions."""
    with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
        SafeCBuffer(0)

    with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
        SafeCBuffer(-5)

    with pytest.raises(TypeError, match="Buffer size must be an integer"):
        SafeCBuffer(3.14)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="Buffer size must be an integer"):
        SafeCBuffer("10")  # type: ignore[arg-type]


def test_safe_c_buffer_write_read_bounds() -> None:
    """Verify write and read operations with boundary overflow enforcement."""
    buf = SafeCBuffer(4)

    buf.write(0, 1.234)
    buf.write(1, 5.678)
    buf.write(2, -9.876)
    buf.write(3, 0.0)

    assert math.isclose(buf.read(0), 1.234)
    assert math.isclose(buf.read(1), 5.678)
    assert math.isclose(buf.read(2), -9.876)
    assert math.isclose(buf.read(3), 0.0)

    # Overflow attempts
    with pytest.raises(IndexError, match="Buffer overflow attempt: index 4 is out of bounds for size 4"):
        buf.read(4)

    with pytest.raises(IndexError, match="Buffer overflow attempt: index -1 is out of bounds for size 4"):
        buf.read(-1)

    with pytest.raises(IndexError, match="Buffer overflow attempt: index 4 is out of bounds for size 4"):
        buf.write(4, 10.0)

    with pytest.raises(IndexError, match="Buffer overflow attempt: index -1 is out of bounds for size 4"):
        buf.write(-1, 10.0)


def test_safe_c_buffer_pointer_and_ctypes_array() -> None:
    """Verify raw pointer export and direct ctypes array access."""
    buf = SafeCBuffer(3)
    buf.write(0, 100.5)
    buf.write(1, 200.5)
    buf.write(2, 300.5)

    ptr = buf.get_raw_pointer()
    assert bool(ptr)
    assert ptr[0] == 100.5
    assert ptr[1] == 200.5
    assert ptr[2] == 300.5

    ctypes_arr = buf.as_ctypes()
    assert len(ctypes_arr) == 3
    assert ctypes_arr[0] == 100.5


def test_safe_c_buffer_sequence_protocol_and_indexing() -> None:
    """Verify indexing with positive and negative integer offsets and slicing."""
    buf = SafeCBuffer(5)
    for i in range(5):
        buf[i] = float(i * 10)

    # Positive indexing
    assert buf[0] == 0.0
    assert buf[4] == 40.0

    # Negative indexing
    assert buf[-1] == 40.0
    assert buf[-2] == 30.0
    assert buf[-5] == 0.0

    # Out-of-bounds indexing
    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        _ = buf[5]

    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        _ = buf[-6]

    # Slicing
    assert buf[1:4] == [10.0, 20.0, 30.0]
    assert buf[:2] == [0.0, 10.0]
    assert buf[3:] == [30.0, 40.0]
    assert buf[::2] == [0.0, 20.0, 40.0]
    assert buf[::-1] == [40.0, 30.0, 20.0, 10.0, 0.0]

    with pytest.raises(TypeError, match="Buffer indices must be integers or slices"):
        _ = buf["invalid"]  # type: ignore[call-overload,index]


def test_safe_c_buffer_slice_and_item_assignment() -> None:
    """Verify slice assignment, size validation, and type checking."""
    buf = SafeCBuffer(5)
    buf[:] = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert buf.to_list() == [1.0, 2.0, 3.0, 4.0, 5.0]

    # Slice assignment with partial range
    buf[1:3] = [20.0, 30.0]
    assert buf.to_list() == [1.0, 20.0, 30.0, 4.0, 5.0]

    # Negative index assignment
    buf[-1] = 50.0
    assert buf[4] == 50.0

    # Negative out of bounds assignment
    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        buf[-6] = 99.0

    # Slice size mismatch
    with pytest.raises(ValueError, match="could not broadcast input sequence"):
        buf[0:2] = [1.0, 2.0, 3.0]

    # Non-iterable slice assignment
    with pytest.raises(TypeError, match="Can only assign an iterable to a slice"):
        buf[0:2] = 42.0  # type: ignore[call-overload,assignment]

    with pytest.raises(TypeError, match="Buffer indices must be integers or slices"):
        buf["key"] = 1.0  # type: ignore[call-overload,index]


def test_safe_c_buffer_iteration_reversed_and_contains() -> None:
    """Verify iter, reversed, and in operators."""
    buf = SafeCBuffer(3)
    buf[:] = [10.0, 20.0, 30.0]

    assert list(buf) == [10.0, 20.0, 30.0]
    assert list(reversed(buf)) == [30.0, 20.0, 10.0]
    assert 20.0 in buf
    assert 20 in buf
    assert 99.0 not in buf
    assert "non_numeric" not in buf


def test_safe_c_buffer_numpy_zero_copy_and_copy() -> None:
    """Verify zero-copy view mutations and independent copy array isolation."""
    buf = SafeCBuffer(3)
    buf[:] = [1.0, 2.0, 3.0]

    np_view = buf.to_numpy(copy=False)
    assert np.array_equal(np_view, [1.0, 2.0, 3.0])

    # Mutate through NumPy view -> reflected in buffer
    np_view[0] = 99.0
    assert buf[0] == 99.0

    # Mutate through buffer -> reflected in NumPy view
    buf[1] = 88.0
    assert np_view[1] == 88.0

    # Isolated copy
    np_copy = buf.to_numpy(copy=True)
    np_copy[0] = 111.0
    assert buf[0] == 99.0


def test_safe_c_buffer_from_numpy_and_from_iterable() -> None:
    """Verify factory classmethods from_numpy and from_iterable."""
    arr = np.array([3.14, 2.71, 1.41])
    buf_np = SafeCBuffer.from_numpy(arr)
    assert len(buf_np) == 3
    assert np.allclose(buf_np.to_numpy(), arr)

    # 2D array input flattened
    arr_2d = np.array([[1.0, 2.0], [3.0, 4.0]])
    buf_2d = SafeCBuffer.from_numpy(arr_2d)
    assert len(buf_2d) == 4
    assert np.allclose(buf_2d.to_numpy(), [1.0, 2.0, 3.0, 4.0])

    # Empty array validation
    with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
        SafeCBuffer.from_numpy(np.array([]))

    # from_iterable
    buf_iter = SafeCBuffer.from_iterable(range(4))
    assert len(buf_iter) == 4
    assert buf_iter.to_list() == [0.0, 1.0, 2.0, 3.0]

    with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
        SafeCBuffer.from_iterable([])


def test_safe_c_buffer_fill_clear_copy() -> None:
    """Verify fill, clear (memset), and deep copy memory operations."""
    buf = SafeCBuffer(4)
    buf.fill(7.77)
    assert buf.to_list() == [7.77, 7.77, 7.77, 7.77]

    # Deep copy
    buf_copy = buf.copy()
    assert buf_copy == buf
    buf_copy[0] = 0.0
    assert buf[0] == 7.77
    assert buf_copy[0] == 0.0

    # Clear
    buf.clear()
    assert buf.to_list() == [0.0, 0.0, 0.0, 0.0]


def test_safe_c_buffer_representations_and_equality() -> None:
    """Verify __repr__, __str__, and __eq__ comparisons."""
    buf = SafeCBuffer(3)
    buf[:] = [1.0, 2.0, 3.0]

    assert "SafeCBuffer" in repr(buf)
    assert "<SafeCBuffer" in str(buf)

    # Long buffer repr ellipsis
    long_buf = SafeCBuffer(10)
    assert "..." in repr(long_buf)

    # Equality against another SafeCBuffer
    buf2 = SafeCBuffer(3)
    buf2[:] = [1.0, 2.0, 3.0]
    assert buf == buf2

    buf_diff_size = SafeCBuffer(4)
    assert buf != buf_diff_size

    # Equality against list, tuple, numpy array
    assert buf == [1.0, 2.0, 3.0]
    assert buf == (1.0, 2.0, 3.0)
    assert buf == np.array([1.0, 2.0, 3.0])
    assert buf != [1.0, 2.0]
    assert buf != np.array([1.0, 2.0, 4.0])
    assert buf != "other_type"



