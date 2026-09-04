"""Physical unit tests for DVR potential grid NaN handling and spline interpolation gate.
Strictly adheres to Method Matrix v4 §7, Zero-Mock Protocol, and Anti-Spoofing Protocol.
Verifies eradication of 0.0 minimum fabrication and strict boundary validation.
"""

from __future__ import annotations

import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_dvr_solver import nan_regularization_watchdog
from cochem_base.exceptions import MethodMatrixViolationError


def test_dvr_nan_watchdog_1d_interior_resolved() -> None:
    """Verify that 1D potential with interior holes is resolved via cubic spline without zero wells."""
    # Physical 1D harmonic potential shifted away from zero: V(x) = 100.0 + 5.0 * x^2
    n_points = 21
    grid_points = np.array([-2.0 + 0.2 * i for i in range(n_points)], dtype=np.float64)
    potential = 100.0 + 5.0 * (grid_points ** 2)

    # Inject missing data at an interior point (center x = 0.0, true V = 100.0)
    center_idx = 10
    potential_with_hole = potential.copy()
    potential_with_hole[center_idx] = np.nan

    # Process through watchdog
    resolved_potential = nan_regularization_watchdog(potential_with_hole, name="1D Test Potential")

    # Assert all points are finite
    assert np.all(np.isfinite(resolved_potential)), "Resolved potential must be completely finite"

    # Assert cubic interpolation accurately reconstructs true potential (> 99.0 kcal/mol, NEVER 0.0!)
    interpolated_val = float(resolved_potential[center_idx])
    expected_val = float(potential[center_idx])
    assert abs(interpolated_val - expected_val) < 0.1, (
        f"Interpolated value {interpolated_val} deviates from true value {expected_val}"
    )
    assert interpolated_val > 50.0, "Watchdog must never fabricate a 0.0 potential well"


def test_dvr_nan_watchdog_1d_boundary_raises() -> None:
    """Verify that non-finite values on the 1D outer boundary raise MethodMatrixViolationError."""
    n_points = 21
    grid_points = np.array([-2.0 + 0.2 * i for i in range(n_points)], dtype=np.float64)
    potential = 100.0 + 5.0 * (grid_points ** 2)

    # Edge missing data at left boundary (index 0)
    potential_left_edge = potential.copy()
    potential_left_edge[0] = np.nan
    with pytest.raises(MethodMatrixViolationError) as exc_info:
        nan_regularization_watchdog(potential_left_edge, name="1D Edge Potential")
    assert "boundary" in str(exc_info.value).lower()

    # Edge missing data at right boundary (index n - 1)
    potential_right_edge = potential.copy()
    potential_right_edge[-1] = float("inf")
    with pytest.raises(MethodMatrixViolationError) as exc_info:
        nan_regularization_watchdog(potential_right_edge, name="1D Edge Potential")
    assert "boundary" in str(exc_info.value).lower()


def test_dvr_nan_watchdog_2d_interior_resolved() -> None:
    """Verify that 2D potential surface with interior hole is resolved via 2D cubic interpolation."""
    # Physical 2D coupled surface: V(x, y) = 50.0 + 2.0*(x-5)^2 + 3.0*(y-5)^2
    grid_2d = np.array([
        [50.0 + 2.0 * ((i - 5) ** 2) + 3.0 * ((j - 5) ** 2) for j in range(11)]
        for i in range(11)
    ], dtype=np.float64)

    # Inject interior missing point at center (5, 5) where true V = 50.0
    grid_with_hole = grid_2d.copy()
    grid_with_hole[5, 5] = np.nan

    resolved_grid = nan_regularization_watchdog(grid_with_hole, name="2D Test Potential")

    assert np.all(np.isfinite(resolved_grid)), "Resolved 2D grid must be completely finite"

    interpolated_val = float(resolved_grid[5, 5])
    expected_val = float(grid_2d[5, 5])
    assert abs(interpolated_val - expected_val) < 2.0, (
        f"2D interpolated value {interpolated_val} deviates from expected {expected_val}"
    )
    assert interpolated_val > 25.0, "Watchdog must never fabricate a 0.0 potential minimum"


def test_dvr_nan_watchdog_2d_boundary_raises() -> None:
    """Verify that non-finite values on the 2D outer boundary raise MethodMatrixViolationError."""
    grid_2d = np.array([
        [50.0 + 2.0 * (i ** 2) + 3.0 * (j ** 2) for j in range(10)]
        for i in range(10)
    ], dtype=np.float64)

    # Edge missing data at boundary row (0, 4)
    grid_edge = grid_2d.copy()
    grid_edge[0, 4] = np.nan

    with pytest.raises(MethodMatrixViolationError) as exc_info:
        nan_regularization_watchdog(grid_edge, name="2D Boundary Potential")
    assert "boundary" in str(exc_info.value).lower()
