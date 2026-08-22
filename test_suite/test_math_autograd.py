"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.math.autograd.

Tests Coulomb potential, gradient force vectors, electric field, DualNumber forward-mode
automatic differentiation, singularity protection thresholds, and numerical gradients.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import pytest

from cochem_base.math.autograd import (
    COULOMB_CONSTANT,
    DEFAULT_SINGULARITY_THRESHOLD,
    ELEMENTARY_CHARGE,
    DualNumber,
    SingularityError,
    coulomb_field,
    coulomb_force,
    coulomb_gradient,
    coulomb_potential,
    dual_gradient,
    numerical_gradient,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def autograd_source_path() -> Path:
    """Return the absolute path to cochem_base/math/autograd.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "math" / "autograd.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_autograd_file_encoding_and_lf_endings(autograd_source_path: Path) -> None:
    """Verify strictly Unix LF line endings, UTF-8 encoding, and no UTF-8 BOM."""
    raw = autograd_source_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\\r\\n) line endings in math/autograd.py"
    assert b"\n" in raw, "Missing newline characters in math/autograd.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in math/autograd.py"


def test_zero_personal_path_leaks_in_autograd(autograd_source_path: Path) -> None:
    """Verify zero personal machine or local username path leakage."""
    lines = autograd_source_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in autograd.py: {leaks}"


def test_physical_constants() -> None:
    """Verify standard SI constants exported by autograd subsystem."""
    assert math.isclose(COULOMB_CONSTANT, 8.9875517923e9, rel_tol=1e-8)
    assert math.isclose(DEFAULT_SINGULARITY_THRESHOLD, 1e-12, rel_tol=1e-8)
    assert math.isclose(ELEMENTARY_CHARGE, 1.602176634e-19, rel_tol=1e-8)


def test_singularity_error_instantiation_and_context() -> None:
    """Verify SingularityError messages, attributes, and inheritance."""
    assert issubclass(SingularityError, ValueError)

    # Default without args
    err1 = SingularityError()
    assert "singularity" in str(err1).lower()

    # With distance and threshold
    dist = 5e-14
    thresh = 1e-12
    err2 = SingularityError(distance=dist, threshold=thresh)
    assert err2.distance == dist
    assert err2.threshold == thresh
    assert f"Distance {dist}" in str(err2)


def test_coulomb_potential_calculation_and_polarities() -> None:
    """Verify Coulomb potential calculation for attractive and repulsive charges."""
    q_prot = ELEMENTARY_CHARGE
    q_elec = -ELEMENTARY_CHARGE
    r_bohr = 5.29177210903e-11  # Bohr radius in meters

    # Attractive interaction (electron + proton) -> negative potential energy
    v_attract = coulomb_potential(q_prot, q_elec, r_bohr)
    expected_v = COULOMB_CONSTANT * q_prot * q_elec / r_bohr
    assert math.isclose(v_attract, expected_v, rel_tol=1e-9)
    assert v_attract < 0.0

    # Repulsive interaction (two protons) -> positive potential energy
    v_repulse = coulomb_potential(q_prot, q_prot, r_bohr)
    assert math.isclose(v_repulse, -v_attract, rel_tol=1e-9)
    assert v_repulse > 0.0


def test_coulomb_potential_singularity_enforcement() -> None:
    """Verify singularity exceptions on sub-threshold distances."""
    with pytest.raises(SingularityError) as exc_info:
        coulomb_potential(1.0, 1.0, 1e-13)
    assert "dangerously close to zero" in str(exc_info.value)

    # Custom threshold
    with pytest.raises(SingularityError):
        coulomb_potential(1.0, 1.0, 1e-8, singularity_threshold=1e-7)

    # Invalid non-positive threshold
    with pytest.raises(ValueError, match="singularity_threshold must be strictly positive"):
        coulomb_potential(1.0, 1.0, 1e-9, singularity_threshold=-1.0)


def test_coulomb_gradient_vector_mechanics() -> None:
    """Verify Coulomb force gradient 3D vectors along coordinate axes and diagonals."""
    q1 = ELEMENTARY_CHARGE
    q2 = ELEMENTARY_CHARGE
    r = 1e-9

    # Along +x axis
    fx, fy, fz = coulomb_gradient(q1, q2, dx=r, dy=0.0, dz=0.0)
    expected_f = COULOMB_CONSTANT * q1 * q2 / (r**2)
    assert math.isclose(fx, expected_f, rel_tol=1e-7)
    assert math.isclose(fy, 0.0, abs_tol=1e-15)
    assert math.isclose(fz, 0.0, abs_tol=1e-15)

    # Along diagonal (r_vec = (d, d, d))
    d = 1e-9
    diag_r = math.sqrt(3) * d
    diag_fx, diag_fy, diag_fz = coulomb_gradient(q1, q2, dx=d, dy=d, dz=d)
    expected_diag_f_comp = (COULOMB_CONSTANT * q1 * q2 / (diag_r**3)) * d
    assert math.isclose(diag_fx, expected_diag_f_comp, rel_tol=1e-7)
    assert math.isclose(diag_fy, expected_diag_f_comp, rel_tol=1e-7)
    assert math.isclose(diag_fz, expected_diag_f_comp, rel_tol=1e-7)


def test_coulomb_gradient_singularity_enforcement() -> None:
    """Verify singularity detection when 3D displacement norm falls below cutoff."""
    with pytest.raises(SingularityError):
        coulomb_gradient(1.0, 1.0, dx=1e-13, dy=0.0, dz=0.0)

    with pytest.raises(ValueError, match="singularity_threshold must be strictly positive"):
        coulomb_gradient(1.0, 1.0, dx=1e-9, dy=0.0, dz=0.0, singularity_threshold=0.0)


def test_coulomb_field_and_force_wrappers() -> None:
    """Verify high-level coulomb_field and coulomb_force convenience functions."""
    q = ELEMENTARY_CHARGE
    ex, ey, ez = coulomb_field(q, dx=1e-9, dy=0.0, dz=0.0)
    assert ex > 0.0
    assert ey == 0.0
    assert ez == 0.0

    pos1 = (0.0, 0.0, 0.0)
    pos2 = (1e-9, 0.0, 0.0)
    fx, fy, fz = coulomb_force(q, q, pos1=pos1, pos2=pos2)
    assert fx > 0.0

    # Invalid dimension lengths
    with pytest.raises(ValueError, match="Cartesian position vectors must have length 3"):
        coulomb_force(q, q, pos1=[0.0, 0.0], pos2=[1.0, 1.0, 1.0])


def test_dual_number_basic_arithmetic() -> None:
    """Verify DualNumber arithmetic operations, product rule, and quotient rule."""
    x = DualNumber(3.0, 1.0)
    y = DualNumber(2.0, 0.0)

    # Addition: (3 + ε) + (2 + 0ε) = 5 + ε, and with scalar: (3 + ε) + 2 = 5 + ε, 2 + (3 + ε) = 5 + ε
    res_add = x + y
    assert res_add.real == 5.0
    assert res_add.dual == 1.0
    res_add_scalar = x + 2.0
    assert res_add_scalar.real == 5.0
    assert res_add_scalar.dual == 1.0
    res_radd_scalar = 2.0 + x
    assert res_radd_scalar.real == 5.0
    assert res_radd_scalar.dual == 1.0

    # Subtraction: (3 + ε) - (2 + 0ε) = 1 + ε, and with scalar: (3 + ε) - 2 = 1 + ε
    res_sub = x - y
    assert res_sub.real == 1.0
    assert res_sub.dual == 1.0
    res_sub_scalar = x - 2.0
    assert res_sub_scalar.real == 1.0
    assert res_sub_scalar.dual == 1.0

    # Reverse Subtraction: 5 - (3 + ε) = 2 - ε
    res_rsub = 5.0 - x
    assert res_rsub.real == 2.0
    assert res_rsub.dual == -1.0

    # Multiplication (Product Rule): (3 + ε) * (2 + 0ε) = 6 + 2ε
    res_mul = x * y
    assert res_mul.real == 6.0
    assert res_mul.dual == 2.0

    # Multiplication with scalar: 4 * (3 + ε) = 12 + 4ε
    res_rmul = 4.0 * x
    assert res_rmul.real == 12.0
    assert res_rmul.dual == 4.0

    # Division (Quotient Rule): (3 + ε) / (2 + 0ε) = 1.5 + 0.5ε, and with scalar: (3 + ε) / 2 = 1.5 + 0.5ε
    res_div = x / y
    assert res_div.real == 1.5
    assert res_div.dual == 0.5
    res_div_scalar = x / 2.0
    assert res_div_scalar.real == 1.5
    assert res_div_scalar.dual == 0.5

    # Reverse division: 6 / (3 + ε) -> val = 2, deriv = -6 * 1 / 3^2 = -2/3
    res_rdiv = 6.0 / x
    assert math.isclose(res_rdiv.real, 2.0)
    assert math.isclose(res_rdiv.dual, -6.0 / 9.0)

    # Division by zero checks
    with pytest.raises(ZeroDivisionError):
        _ = x / 0.0
    with pytest.raises(ZeroDivisionError):
        _ = x / DualNumber(0.0, 1.0)
    with pytest.raises(ZeroDivisionError):
        _ = 5.0 / DualNumber(0.0, 1.0)


def test_dual_number_powers_and_elementary_functions() -> None:
    """Verify DualNumber powers, sqrt, exp, log, sin, and cos derivatives."""
    # Power rule: d/dx (x^3) at x=2 -> 3 * 2^2 = 12
    x = DualNumber(2.0, 1.0)
    p = x**3
    assert p.real == 8.0
    assert p.dual == 12.0

    # Power rule at zero real part
    z = DualNumber(0.0, 1.0)
    pz = z**2
    assert pz.real == 0.0
    assert pz.dual == 0.0

    with pytest.raises(ValueError, match="Derivative undefined for non-positive power at zero"):
        _ = z**0.5

    # Sqrt: d/dx (sqrt(x)) at x=4 -> 1 / (2*sqrt(4)) = 0.25
    x4 = DualNumber(4.0, 1.0)
    s = x4.sqrt()
    assert s.real == 2.0
    assert s.dual == 0.25

    with pytest.raises(ValueError, match="Square root undefined for non-positive"):
        DualNumber(-1.0, 1.0).sqrt()

    # Exp: d/dx (exp(x)) at x=0 -> exp(0) = 1
    x0 = DualNumber(0.0, 1.0)
    e = x0.exp()
    assert e.real == 1.0
    assert e.dual == 1.0

    # Log: d/dx (log(x)) at x=2 -> 1/2 = 0.5
    l = x.log()
    assert math.isclose(l.real, math.log(2.0))
    assert l.dual == 0.5

    with pytest.raises(ValueError, match="Logarithm undefined for non-positive"):
        DualNumber(0.0, 1.0).log()

    # Sin / Cos: d/dx (sin(x)) = cos(x), d/dx (cos(x)) = -sin(x)
    x_pi = DualNumber(math.pi / 2.0, 1.0)
    sin_val = x_pi.sin()
    assert math.isclose(sin_val.real, 1.0)
    assert math.isclose(sin_val.dual, 0.0, abs_tol=1e-15)

    cos_val = x_pi.cos()
    assert math.isclose(cos_val.real, 0.0, abs_tol=1e-15)
    assert math.isclose(cos_val.dual, -1.0)

    # String, float, equality, and unary operators
    assert float(x) == 2.0
    assert +x == x
    assert (-x).real == -2.0
    assert (-x).dual == -1.0
    assert "DualNumber" in repr(x)
    assert "ε" in str(x)
    assert DualNumber(2.0, 1.0) == DualNumber(2.0, 1.0)
    assert DualNumber(2.0, 0.0) == 2.0
    assert DualNumber(2.0, 0.0) == 2
    assert DualNumber(2.0, 1.0) != DualNumber(2.0, 0.0)
    assert DualNumber(2.0, 0.0) != "not_a_dual"


def test_dual_gradient_multivariate() -> None:
    """Verify dual_gradient exact analytical gradients for multivariate potentials."""
    # Quadratic potential: f(x, y) = x^2 + 3*x*y + y^3
    # df/dx = 2x + 3y
    # df/dy = 3x + 3y^2
    def potential(coords: Sequence[DualNumber]) -> DualNumber:
        x, y = coords[0], coords[1]
        return x**2 + 3.0 * x * y + y**3

    point = [2.0, 4.0]
    val, grad = dual_gradient(potential, point)

    expected_val = (2.0**2) + (3.0 * 2.0 * 4.0) + (4.0**3)  # 4 + 24 + 64 = 92
    expected_df_dx = 2.0 * 2.0 + 3.0 * 4.0  # 4 + 12 = 16
    expected_df_dy = 3.0 * 2.0 + 3.0 * (4.0**2)  # 6 + 48 = 54

    assert math.isclose(val, expected_val)
    assert math.isclose(grad[0], expected_df_dx)
    assert math.isclose(grad[1], expected_df_dy)


def test_numerical_gradient_verification() -> None:
    """Verify numerical_gradient finite differences match analytical derivatives."""
    def func(coords: Sequence[float]) -> float:
        x, y = coords[0], coords[1]
        return float(x**2 + 3.0 * x * y + y**3)

    point = [2.0, 4.0]
    grad_num = numerical_gradient(func, point, h=1e-6)

    # Compare with analytical [16.0, 54.0]
    assert math.isclose(grad_num[0], 16.0, rel_tol=1e-5)
    assert math.isclose(grad_num[1], 54.0, rel_tol=1e-5)

    with pytest.raises(ValueError, match="Step size 'h' must be strictly positive"):
        numerical_gradient(func, point, h=-1e-4)
