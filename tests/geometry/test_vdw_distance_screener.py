"""Zero-Mock verification tests for VanDerWaalsDistanceScreener (test_vdw_distance_screener.py).

Validates Suggestion #42 against genuine physical molecular geometries of water dimer.
"""

import numpy as np
import pytest
from cochem_base.exceptions import IntermolecularTopologyError
from cochem_base.geometry.vdw_screener import VanDerWaalsDistanceScreener


def test_vdw_distance_screener_water_dimer_equilibrium():
    """Verify authentic equilibrium contact for water dimer (R_O...O ≈ 2.91 Å)."""
    # Authentic ab-initio water dimer coordinates (equilibrium R_O...O ≈ 2.91 Å)
    coords_a = np.array([
        [-1.464, -0.010, 0.000],   # O1
        [-0.505, -0.031, 0.000],   # H1 (donor hydrogen pointing toward O2)
        [-1.787, -0.910, 0.000],   # H2
    ], dtype=np.float64)
    symbols_a = ["O", "H", "H"]

    coords_b = np.array([
        [1.446, 0.000, 0.000],    # O2
        [1.800, 0.440, 0.760],    # H3
        [1.800, 0.440, -0.760],   # H4
    ], dtype=np.float64)
    symbols_b = ["O", "H", "H"]

    is_valid, min_dist, msg = VanDerWaalsDistanceScreener.validate_complex_separation(
        coords_a=coords_a,
        symbols_a=symbols_a,
        coords_b=coords_b,
        symbols_b=symbols_b,
    )

    # Intermolecular min distance is H1...O2 ≈ 1.95 Å, well within vdW contact envelope [M]
    assert is_valid is True
    assert 1.8 < min_dist < 2.2
    assert msg == ""


def test_vdw_distance_screener_severe_clashing():
    """Verify severe steric core clash raises IntermolecularTopologyError."""
    # Scaled / translated water dimer with R_O...O = 0.75 Å
    coords_a = np.array([
        [0.000, 0.000, 0.000],
        [0.000, 0.757, 0.586],
        [0.000, -0.757, 0.586],
    ], dtype=np.float64)
    symbols_a = ["O", "H", "H"]

    coords_b = np.array([
        [0.750, 0.000, 0.000],  # Severe clash O...O at 0.75 Å (< 1.0 Å)
        [0.750, 0.757, -0.586],
        [0.750, -0.757, -0.586],
    ], dtype=np.float64)
    symbols_b = ["O", "H", "H"]

    with pytest.raises(IntermolecularTopologyError, match="Severe steric core clash detected"):
        VanDerWaalsDistanceScreener.validate_complex_separation(
            coords_a=coords_a,
            symbols_a=symbols_a,
            coords_b=coords_b,
            symbols_b=symbols_b,
        )


def test_vdw_distance_screener_dissociated():
    """Verify dissociated dimer raises IntermolecularTopologyError."""
    coords_a = np.array([
        [0.000, 0.000, 0.000],
        [0.000, 0.757, 0.586],
        [0.000, -0.757, 0.586],
    ], dtype=np.float64)
    symbols_a = ["O", "H", "H"]

    coords_b = np.array([
        [9.500, 0.000, 0.000],  # Dissociated at 9.50 Å (> 8.0 Å)
        [9.500, 0.757, -0.586],
        [9.500, -0.757, -0.586],
    ], dtype=np.float64)
    symbols_b = ["O", "H", "H"]

    with pytest.raises(IntermolecularTopologyError, match="Fragments dissociated"):
        VanDerWaalsDistanceScreener.validate_complex_separation(
            coords_a=coords_a,
            symbols_a=symbols_a,
            coords_b=coords_b,
            symbols_b=symbols_b,
        )
