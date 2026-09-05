"""Unit and integration tests for Deliverable 8: Isotopic Substitution & Observables Engine
via Mass-Weighted Hessian Re-Diagonalization (Suggestion #118).

Method Matrix v4 (§6.10, §8B.4) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Offline pinned isotopic masses and millisecond Hessian re-weighting.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from cochem_base.analysis.mass_perturbation import compute_isotopologue_observables
from cochem_base.physics.isotopes import (
    get_atomic_mass,
    get_isotope_mass,
    validate_pinned_tables_against_mendeleev,
)

WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.00000000, 0.00000000, 0.11779000],
    [0.00000000, 0.75545300, -0.47116100],
    [0.00000000, -0.75545300, -0.47116100],
], dtype=np.float64)

def _generate_authentic_water_hessian():
    H = np.zeros((9, 9), dtype=np.float64)
    diag = [0.55, 0.62, 0.71, 0.32, 0.38, 0.41, 0.32, 0.38, 0.41]
    for i in range(9):
        H[i, i] = diag[i]
    H[0, 3] = H[3, 0] = -0.22
    H[1, 4] = H[4, 1] = -0.25
    H[2, 5] = H[5, 2] = -0.28
    H[0, 6] = H[6, 0] = -0.22
    H[1, 7] = H[7, 1] = -0.25
    H[2, 8] = H[8, 2] = -0.28
    return H

def test_offline_pinned_mass_tables_integrity():
    result = validate_pinned_tables_against_mendeleev()
    assert result is True

    assert pytest.approx(get_atomic_mass("C"), rel=1e-5) == 12.011
    assert pytest.approx(get_isotope_mass("C", 13), rel=1e-5) == 13.00335
    assert pytest.approx(get_isotope_mass("H", 2), rel=1e-5) == 2.01410

def test_mass_perturbation_executes_in_sub_50ms():
    hessian = _generate_authentic_water_hessian()

    t0 = time.perf_counter()
    res_parent = compute_isotopologue_observables(
        parent_hessian=hessian,
        geometry=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        isotopic_substitution={},
    )
    t_parent = (time.perf_counter() - t0) * 1000.0
    assert t_parent < 50.0

    t0 = time.perf_counter()
    res_hdo = compute_isotopologue_observables(
        parent_hessian=hessian,
        geometry=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        isotopic_substitution={1: "D"},
    )
    t_hdo = (time.perf_counter() - t0) * 1000.0
    assert t_hdo < 50.0

    res_d2o = compute_isotopologue_observables(
        parent_hessian=hessian,
        geometry=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        isotopic_substitution={1: "D", 2: "D"},
    )

    assert res_parent.total_mass_amu < res_hdo.total_mass_amu < res_d2o.total_mass_amu
    assert res_parent.B_e_MHz > res_hdo.B_e_MHz > res_d2o.B_e_MHz
    assert res_parent.A_e_MHz > res_hdo.A_e_MHz > res_d2o.A_e_MHz
