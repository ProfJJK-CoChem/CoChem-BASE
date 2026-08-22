"""Comprehensive physical Zero-Mock test suite for cochem_base.math subsystem.

Validates lazy loading architecture (PEP 562), exported symbols, type hinting integrity,
AttributeError handling, __dir__ reflection, LF line endings, path sanitization,
and functional mathematical / geometric operations.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import cochem_base.math as cochem_math
from cochem_base.math.assertions import MachineEpsilonWarning, SimulationTensor
from cochem_base.math.autograd import SingularityError, coulomb_gradient, coulomb_potential
from cochem_base.math.c_bindings import SafeCBuffer
from cochem_base.math.geometry import BoundingBox, Point
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def math_init_path() -> Path:
    """Return the absolute path to cochem_base/math/__init__.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "math" / "__init__.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(math_init_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = math_init_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in math/__init__.py"
    assert b"\n" in raw, "Missing newline characters in math/__init__.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in math/__init__.py"

    content = math_init_path.read_text(encoding="utf-8")
    assert len(content) > 200, "File content is unexpectedly small."


def test_zero_personal_path_leaks(math_init_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in math/__init__.py."""
    lines = math_init_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in math/__init__.py: {leaks}"


def test_docstring_and_architectural_overview(math_init_path: Path) -> None:
    """Verify comprehensive architectural docstring is present on the module."""
    doc = cochem_math.__doc__
    assert doc is not None and len(doc) > 100
    assert "SimulationTensor" in doc
    assert "Coulomb" in doc
    assert "SafeCBuffer" in doc
    assert "BoundingBox" in doc


def test_module_all_exports_present() -> None:
    """Verify __all__ is a sorted list of non-empty public symbols."""
    assert hasattr(cochem_math, "__all__")
    assert isinstance(cochem_math.__all__, list)
    assert cochem_math.__all__ == sorted(cochem_math.__all__)

    expected_symbols = [
        "BoundingBox",
        "MachineEpsilonWarning",
        "Point",
        "SafeCBuffer",
        "SimulationTensor",
        "SingularityError",
        "coulomb_gradient",
        "coulomb_potential",
    ]
    assert cochem_math.__all__ == expected_symbols
    for sym in expected_symbols:
        assert sym in cochem_math.__all__, f"Symbol '{sym}' missing from math.__all__"


@pytest.mark.parametrize(
    "symbol_name",
    [
        "BoundingBox",
        "MachineEpsilonWarning",
        "Point",
        "SafeCBuffer",
        "SimulationTensor",
        "SingularityError",
        "coulomb_gradient",
        "coulomb_potential",
    ],
)
def test_lazy_attribute_resolution(symbol_name: str) -> None:
    """Verify PEP 562 lazy resolution resolves each symbol to an actual valid object."""
    attr = getattr(cochem_math, symbol_name)
    assert attr is not None
    # Verify cached in module dictionary
    assert symbol_name in cochem_math.__dict__


def test_invalid_attribute_access_raises_attribute_error() -> None:
    """Verify accessing undefined attributes raises AttributeError with descriptive message."""
    with pytest.raises(AttributeError) as exc_info:
        _ = cochem_math.NonExistentMathSymbol
    assert "module 'cochem_base.math' has no attribute 'NonExistentMathSymbol'" in str(exc_info.value)


def test_dir_reflection_contains_all_and_globals() -> None:
    """Verify __dir__() lists all public exports and module globals."""
    dir_symbols = dir(cochem_math)
    for sym in cochem_math.__all__:
        assert sym in dir_symbols, f"Symbol '{sym}' missing from dir(cochem_math)"
    assert "__all__" in dir_symbols
    assert "__getattr__" in dir_symbols
    assert "__dir__" in dir_symbols


def test_simulation_tensor_and_machine_epsilon() -> None:
    """Verify SimulationTensor intercepts equality comparisons and raises MachineEpsilonWarning."""
    t1 = SimulationTensor([1.0, 2.0, 3.0])
    t2 = np.array([1.0, 2.0, 3.0 + 1e-9])

    with pytest.warns(MachineEpsilonWarning) as record:
        result = (t1 == t2)
    assert len(record) == 1
    assert "Exact equality comparison (==) detected" in str(record[0].message)
    assert np.all(result)

    # Test inequality
    t3 = np.array([1.0, 2.0, 4.0])
    with pytest.warns(MachineEpsilonWarning):
        ne_result = (t1 != t3)
    assert np.array_equal(ne_result, [False, False, True])


def test_coulomb_potential_and_singularity() -> None:
    """Verify Coulomb potential computation and singularity threshold enforcement."""
    q1 = 1.0e-19
    q2 = -1.0e-19
    r = 1.0e-9
    expected_pot = 8.9875517923e9 * q1 * q2 / r
    pot = coulomb_potential(q1, q2, r)
    assert math.isclose(pot, expected_pot, rel_tol=1e-6)

    # Distance below singularity threshold (1e-12 m)
    with pytest.raises(SingularityError, match="causing a singularity"):
        coulomb_potential(q1, q2, 1e-13)


def test_coulomb_gradient_and_singularity() -> None:
    """Verify Coulomb gradient computation and singularity handling."""
    q1 = 1.0e-19
    q2 = 1.0e-19
    dx, dy, dz = 1.0e-9, 0.0, 0.0
    fx, fy, fz = coulomb_gradient(q1, q2, dx, dy, dz)
    assert fx > 0
    assert fy == 0.0
    assert fz == 0.0

    # Singularity in gradient
    with pytest.raises(SingularityError, match="causing a singularity"):
        coulomb_gradient(q1, q2, 1e-13, 0.0, 0.0)


def test_safe_c_buffer() -> None:
    """Verify SafeCBuffer creation, bounds checking, and pointer retrieval."""
    with pytest.raises(ValueError, match="Buffer size must be strictly positive"):
        SafeCBuffer(0)

    buf = SafeCBuffer(5)
    assert buf.size == 5

    buf.write(0, 3.14159)
    buf.write(4, 2.71828)
    assert math.isclose(buf.read(0), 3.14159, rel_tol=1e-5)
    assert math.isclose(buf.read(4), 2.71828, rel_tol=1e-5)

    # Out of bounds access
    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        buf.read(-1)
    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        buf.read(5)
    with pytest.raises(IndexError, match="Buffer overflow attempt"):
        buf.write(5, 1.0)

    ptr = buf.get_raw_pointer()
    assert ptr is not None


def test_geometry_point_and_bounding_box() -> None:
    """Verify 3D Point and BoundingBox Cartesian validation."""
    p1 = Point(x=0.0, y=0.0, z=0.0)
    p2 = Point(x=3.0, y=4.0, z=0.0)
    assert math.isclose(p1.distance_to(p2), 5.0)

    # Valid BoundingBox
    bbox = BoundingBox(min_point=Point(x=0.0, y=0.0, z=0.0), max_point=Point(x=1.0, y=2.0, z=3.0))
    assert bbox.dimensions == (1.0, 2.0, 3.0)

    # Invalid BoundingBox where max <= min
    with pytest.raises(ValueError, match="Cartesian boundaries invalid"):
        BoundingBox(min_point=Point(x=1.0, y=0.0, z=0.0), max_point=Point(x=0.5, y=1.0, z=1.0))
