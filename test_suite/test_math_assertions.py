"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.math.assertions.

Tests floating-point assertions, MachineEpsilonWarning emissions, SimulationTensor
tolerance checks, slicing/view finalization, boundary conditions, and assert_allclose_eps.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from cochem_base.math.assertions import (
    MachineEpsilonWarning,
    SimulationTensor,
    assert_allclose_eps,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def assertions_source_path() -> Path:
    """Return the absolute path to cochem_base/math/assertions.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "math" / "assertions.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_assertions_file_encoding_and_lf_endings(assertions_source_path: Path) -> None:
    """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
    raw = assertions_source_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/assertions.py"
    assert b"\n" in raw, "Missing newline characters in math/assertions.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in math/assertions.py"


def test_zero_personal_path_leaks_in_assertions(assertions_source_path: Path) -> None:
    """Verify zero personal machine or local username path leakage."""
    lines = assertions_source_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in assertions.py: {leaks}"


def test_machine_epsilon_warning_instantiation() -> None:
    """Verify MachineEpsilonWarning attributes, defaults, and string representations."""
    # Default warning
    warn_default = MachineEpsilonWarning()
    assert issubclass(MachineEpsilonWarning, Warning)
    assert issubclass(MachineEpsilonWarning, UserWarning)
    assert "Exact equality comparison (==) detected" in str(warn_default)
    assert "MachineEpsilonWarning" in repr(warn_default)

    # Custom message warning
    custom_msg = "Custom numerical instability warning."
    warn_custom = MachineEpsilonWarning(custom_msg)
    assert str(warn_custom) == custom_msg
    assert repr(warn_custom) == f"MachineEpsilonWarning({custom_msg!r})"


def test_simulation_tensor_creation_and_attributes() -> None:
    """Verify SimulationTensor constructor, dtype casting, and tolerance settings."""
    arr = [1.0, 2.5, 3.75]
    tensor = SimulationTensor(arr)

    assert isinstance(tensor, SimulationTensor)
    assert isinstance(tensor, np.ndarray)
    assert tensor.dtype == np.float64
    assert tensor.shape == (3,)
    assert tensor.atol == SimulationTensor.DEFAULT_ATOL
    assert tensor.rtol == SimulationTensor.DEFAULT_RTOL


def test_simulation_tensor_custom_tolerances_and_validation() -> None:
    """Verify custom atol/rtol parameters and non-negative tolerance validation."""
    tensor = SimulationTensor([1.0, 2.0], atol=1e-6, rtol=1e-4)
    assert tensor.atol == 1e-6
    assert tensor.rtol == 1e-4

    # Mutate tolerances via properties
    tensor.atol = 1e-9
    tensor.rtol = 1e-6
    assert tensor.atol == 1e-9
    assert tensor.rtol == 1e-6

    # Validation errors on negative tolerances
    with pytest.raises(ValueError, match="Absolute tolerance 'atol' must be non-negative"):
        SimulationTensor([1.0], atol=-1e-5)

    with pytest.raises(ValueError, match="Relative tolerance 'rtol' must be non-negative"):
        SimulationTensor([1.0], rtol=-1e-3)

    with pytest.raises(ValueError, match="Absolute tolerance 'atol' must be non-negative"):
        tensor.atol = -0.1

    with pytest.raises(ValueError, match="Relative tolerance 'rtol' must be non-negative"):
        tensor.rtol = -0.1


def test_simulation_tensor_slicing_and_array_finalize() -> None:
    """Verify slicing and views maintain SimulationTensor subclass and propagate tolerances."""
    tensor = SimulationTensor([[1.0, 2.0], [3.0, 4.0]], atol=1e-7, rtol=1e-4)
    sub_slice = tensor[0, :]

    assert isinstance(sub_slice, SimulationTensor)
    assert sub_slice.atol == 1e-7
    assert sub_slice.rtol == 1e-4
    assert np.array_equal(np.asarray(sub_slice), [1.0, 2.0])


def test_simulation_tensor_equality_interception_and_warning() -> None:
    """Verify exact equality (==) emits MachineEpsilonWarning and applies isclose."""
    t1 = SimulationTensor([1.0, 2.0, 3.0])
    # Very small perturbation within default atol (1e-8)
    t2 = np.array([1.0 + 1e-9, 2.0, 3.0 - 1e-9])

    with pytest.warns(MachineEpsilonWarning) as record:
        result = (t1 == t2)

    assert len(record) == 1
    assert "Exact equality comparison (==) detected" in str(record[0].message)
    assert isinstance(result, np.ndarray)
    assert np.all(result)

    # Large perturbation exceeding tolerance
    t3 = np.array([1.0 + 1e-3, 2.0, 3.0])
    with pytest.warns(MachineEpsilonWarning):
        result_diff = (t1 == t3)
    assert np.array_equal(result_diff, [False, True, True])


def test_simulation_tensor_scalar_equality() -> None:
    """Verify equality comparison against scalar values."""
    tensor = SimulationTensor([5.0, 5.0 + 1e-9, 6.0])
    with pytest.warns(MachineEpsilonWarning):
        res = (tensor == 5.0)

    assert np.array_equal(res, [True, True, False])


def test_simulation_tensor_inequality_interception() -> None:
    """Verify exact inequality (!=) emits MachineEpsilonWarning and inverts isclose."""
    t1 = SimulationTensor([1.0, 2.0, 3.0])
    t2 = np.array([1.0 + 1e-9, 2.0, 4.0])

    with pytest.warns(MachineEpsilonWarning) as record:
        ne_result = (t1 != t2)

    assert len(record) >= 1
    assert np.array_equal(ne_result, [False, False, True])


def test_simulation_tensor_is_close_to_without_warning() -> None:
    """Verify is_close_to performs exact numerical tolerance check without emitting warnings."""
    tensor = SimulationTensor([10.0, 20.0, 30.0])
    other = [10.0 + 1e-3, 20.0, 30.0]

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        # With default tolerances (rtol=1e-5, atol=1e-8), 1e-3 exceeds tolerance (rtol*10 = 1e-4)
        close_default = tensor.is_close_to(other)
        # With loose custom rtol (1e-2), 1e-3 is well within tolerance
        close_loose = tensor.is_close_to(other, rtol=1e-2)

    assert len(record) == 0
    assert np.array_equal(close_default, [False, True, True])
    assert np.array_equal(close_loose, [True, True, True])



def test_assert_allclose_eps_success_and_failure() -> None:
    """Verify assert_allclose_eps functional assertion helper."""
    actual = np.array([1.0, 2.0, 3.0])
    desired = np.array([1.0 + 1e-9, 2.0 - 1e-9, 3.0])

    # Should pass without error
    assert_allclose_eps(actual, desired)

    # Should fail for divergent array
    bad_desired = np.array([1.0, 2.5, 3.0])
    with pytest.raises(AssertionError, match="Custom convergence failure"):
        assert_allclose_eps(actual, bad_desired, err_msg="Custom convergence failure")

