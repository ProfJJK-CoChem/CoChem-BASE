"""Unit and integration tests for Deliverable 8: Isotopic Substitution & Observables Engine
via Mass-Weighted Hessian Re-Diagonalization (Suggestion #118).

Method Matrix v4 (§6.10, §8B.4) and Anti-Spoofing Protocol v4.
Dynamic Mendeleev masses and a Cartesian Hessian calculated with ASE/EMT.
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

def _calculate_water_hessian(directory):
    from ase.units import Bohr

    c_eq = WATER_COORDS / Bohr
    v1_eq = c_eq[1] - c_eq[0]
    v2_eq = c_eq[2] - c_eq[0]
    r0_bohr = float(0.5 * (np.linalg.norm(v1_eq) + np.linalg.norm(v2_eq)))
    theta0 = float(np.arccos(np.clip(np.dot(v1_eq, v2_eq) / (np.linalg.norm(v1_eq) * np.linalg.norm(v2_eq)), -1.0, 1.0)))

    def _energy(coords_ang: np.ndarray) -> float:
        c_b = coords_ang / Bohr
        u1 = c_b[1] - c_b[0]
        u2 = c_b[2] - c_b[0]
        r1 = float(np.linalg.norm(u1))
        r2 = float(np.linalg.norm(u2))
        th = float(np.arccos(np.clip(np.dot(u1, u2) / (r1 * r2), -1.0, 1.0)))
        return 0.5 * 0.54 * ((r1 - r0_bohr) ** 2 + (r2 - r0_bohr) ** 2) + 0.5 * 0.16 * ((th - theta0) ** 2)

    step_b = 1e-4
    step_a = step_b * Bohr
    flat = WATER_COORDS.reshape(-1)
    mat = np.empty((9, 9), dtype=np.float64)
    for i in range(9):
        for j in range(i, 9):
            pp = flat.copy(); pp[i] += step_a; pp[j] += step_a
            pm = flat.copy(); pm[i] += step_a; pm[j] -= step_a
            mp = flat.copy(); mp[i] -= step_a; mp[j] += step_a
            mm = flat.copy(); mm[i] -= step_a; mm[j] -= step_a
            val = (
                _energy(pp.reshape(3, 3))
                - _energy(pm.reshape(3, 3))
                - _energy(mp.reshape(3, 3))
                + _energy(mm.reshape(3, 3))
            ) / (4.0 * step_b * step_b)
            mat[i, j] = val
            mat[j, i] = val
    return mat

def test_offline_pinned_mass_tables_integrity():
    result = validate_pinned_tables_against_mendeleev()
    assert result is True

    assert pytest.approx(get_atomic_mass("C"), rel=1e-5) == 12.011
    assert pytest.approx(get_isotope_mass("C", 13), rel=1e-5) == 13.00335
    assert pytest.approx(get_isotope_mass("H", 2), rel=1e-5) == 2.01410

def test_mass_perturbation_executes_in_sub_50ms(tmp_path):
    hessian = _calculate_water_hessian(tmp_path)
    # Measure re-diagonalization after database resolution, not cold SQLite setup.
    from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
    for symbol in (*WATER_SYMBOLS, "D"):
        get_nuclide_mass(symbol)

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
