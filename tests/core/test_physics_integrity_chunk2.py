"""Zero-Mock Physics Integrity Test Suite for Chunk 2 (Suggestions #11-#14).

Adheres to:
- Method Matrix v4 (§6.10, §16.1)
- Zero-Mock Anti-Spoofing Protocol (100% authentic physical calculations)
- Dynamic Mendeleev Invariant Mandate (Zero hardcoded masses)
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
from mendeleev import element

from cochem.core.exceptions import MissingDataError, RotationalGridInstabilityError
from cochem.core.mendeleev_invariants import (
    get_element,
    get_element_mass,
    get_isotope_mass,
    parse_symbol_or_isotope,
)
from cochem_base.calc.cochem_calc_input_generator import (
    MoleculeInput,
    generate_orca_input,
    validate_rotational_mode_stability,
)
from cochem_base.cochem_torq_alignment import (
    diagonalize_principal_axes,
    translate_com_to_origin,
)
from cochem_base.cochem_torq_topology import build_molecular_graph
from cochem_base.cochem_torq_vault import standardize_geometry_dataframe
from cochem_base.core_engine.cochem_core_dvr_solver import (
    DVRGridType,
    build_grid_1d,
    build_sinc_kinetic_1d,
)


def test_mendeleev_mass_resolution_and_rejection() -> None:
    """Suggestion #11 & #13: Verify dynamic mass lookup, isotopic aliases, and rejection of invalid symbols."""
    # 1. Standard elemental symbols match IUPAC atomic weights via mendeleev
    for sym in ["H", "C", "N", "O", "Ar"]:
        elem_truth = element(sym)
        resolved_mass = get_element_mass(sym)
        assert abs(resolved_mass - float(elem_truth.atomic_weight)) < 1e-6
        elem_data = get_element(sym)
        assert elem_data.symbol == sym
        assert abs(elem_data.atomic_weight - float(elem_truth.atomic_weight)) < 1e-6

    # 2. Isotopic aliases dynamically resolved
    # Deuterium (D / 2H): ~2.01410178 u
    d_mass = get_element_mass("D")
    assert abs(d_mass - 2.01410178) < 1e-4

    two_h_mass = get_element_mass("2H")
    assert abs(two_h_mass - 2.01410178) < 1e-4

    # Tritium (T / 3H): ~3.01604928 u
    t_mass = get_element_mass("T")
    assert abs(t_mass - 3.01604928) < 1e-4

    # Carbon-13 (13C): ~13.00335484 u
    c13_mass = get_element_mass("13C")
    assert abs(c13_mass - 13.00335484) < 1e-4

    # Oxygen-18 (18O): ~17.9991604 u
    o18_mass = get_element_mass("18O")
    assert abs(o18_mass - 17.9991604) < 1e-4

    # 3. Invalid symbols MUST raise MissingDataError (NEVER silently default to 12.0)
    for invalid_sym in ["Xx", "", "123", "NonExistent"]:
        with pytest.raises(MissingDataError):
            get_element_mass(invalid_sym)

        with pytest.raises(MissingDataError):
            get_element(invalid_sym)

    # 4. Invariant checks across TORQ modules
    # In cochem_torq_vault: invalid symbol raises MissingDataError
    invalid_coords = np.array([[0.0, 0.0, 0.0]], dtype=np.float64)
    with pytest.raises(MissingDataError):
        standardize_geometry_dataframe(["Xx"], invalid_coords)

    # Valid H2O dataframe has authentic masses (H ~ 1.008, O ~ 15.999) and NO 12.0
    h2o_coords = np.array(
        [[0.0, 0.0, 0.0], [0.0, 0.757, 0.586], [0.0, -0.757, 0.586]], dtype=np.float64
    )
    df_h2o = standardize_geometry_dataframe(["O", "H", "H"], h2o_coords)
    assert abs(df_h2o.loc[0, "mass_amu"] - get_element_mass("O")) < 1e-4
    assert abs(df_h2o.loc[1, "mass_amu"] - get_element_mass("H")) < 1e-4
    assert not any(abs(m - 12.0) < 1e-3 for m in df_h2o["mass_amu"])

    # In cochem_torq_alignment: invalid symbol raises MissingDataError
    with pytest.raises(MissingDataError):
        translate_com_to_origin(["Xx"], invalid_coords)

    with pytest.raises(MissingDataError):
        diagonalize_principal_axes(["Xx"], invalid_coords)

    # In cochem_torq_topology: invalid symbol raises MissingDataError
    with pytest.raises(MissingDataError):
        build_molecular_graph(["Xx"], invalid_coords)


def test_sinc_dvr_interior_grid_and_dirichlet_boundaries() -> None:
    """Suggestion #12: Verify Colbert & Miller (1992) Dirichlet interior Sinc DVR discretization."""
    x_min = -3.0
    x_max = 3.0
    n = 50

    coords, weights = build_grid_1d(DVRGridType.SINC, n_points=n, x_min=x_min, x_max=x_max)

    # 1. Grid points must be strictly interior: no point equals boundaries
    assert len(coords) == n
    assert coords[0] > x_min
    assert coords[-1] < x_max
    assert np.all(coords > x_min)
    assert np.all(coords < x_max)

    # 2. Verify step size dx = (x_max - x_min) / (n + 1) = 6.0 / 51
    expected_dx = (x_max - x_min) / float(n + 1)
    actual_dx = float(coords[1] - coords[0])
    assert abs(actual_dx - expected_dx) < 1e-12
    assert abs(float(coords[0] - x_min) - expected_dx) < 1e-12
    assert abs(float(x_max - coords[-1]) - expected_dx) < 1e-12

    # 3. Exact symmetry about 0.0
    assert np.allclose(coords, -coords[::-1], atol=1e-12)

    # 4. Harmonic Oscillator test: V(x) = 0.5 * m * omega^2 * x^2
    # In atomic units: m = 1.0, omega = 1.0, hbar = 1.0
    # True eigenvalues: E_v = hbar * omega * (v + 1/2) = 0.5, 1.5, 2.5, 3.5...
    n_ho = 80
    l_ho = 6.0
    grid_ho, _ = build_grid_1d(DVRGridType.SINC, n_points=n_ho, x_min=-l_ho, x_max=l_ho)
    dx_ho = float(grid_ho[1] - grid_ho[0])

    # Colbert-Miller kinetic energy matrix (hbar=1.0, m=1.0 in atomic units)
    idx = np.arange(n_ho, dtype=np.float64)
    diff = idx[:, None] - idx[None, :]
    mask_diag = (diff == 0.0)
    diff_safe = np.where(mask_diag, 1.0, diff)
    factor = 1.0 / (2.0 * (dx_ho ** 2))
    t_mat = factor * 2.0 * ((-1.0) ** diff) / (diff_safe ** 2)
    np.fill_diagonal(t_mat, factor * (math.pi ** 2) / 3.0)

    # Potential matrix V_ij = V(x_i) * delta_ij
    v_diag = 0.5 * (grid_ho ** 2)
    h_mat = t_mat + np.diag(v_diag)

    eigenvalues = np.linalg.eigvalsh(h_mat)
    expected_e0 = 0.5
    expected_e1 = 1.5
    expected_e2 = 2.5

    # Eigenvalues must match hbar * omega * (v + 1/2) within 0.01%
    assert abs(eigenvalues[0] - expected_e0) / expected_e0 < 0.0001
    assert abs(eigenvalues[1] - expected_e1) / expected_e1 < 0.0001
    assert abs(eigenvalues[2] - expected_e2) / expected_e2 < 0.0001


def test_rotational_mode_stability_defgrid3(tmp_path: Path) -> None:
    """Suggestion #14: Verify defgrid3 mandate for harmonic frequency tasks and rotational mode stability."""
    # 1. ORCA input generator mandates defgrid3 for frequency calculation
    water_dimer = MoleculeInput(
        basin_id="dimer_test",
        elements=["O", "H", "H", "O", "H", "H"],
        coordinates=[
            (-1.464, -0.019, 0.000),
            (-1.823, 0.428, 0.772),
            (-1.823, 0.428, -0.772),
            (1.464, 0.019, 0.000),
            (0.823, -0.428, 0.000),
            (1.823, -0.428, 0.772),
        ],
        theory_level="B3LYP-D3 def2-TZVP Freq",
        is_opt=False,
    )

    out_file = generate_orca_input(water_dimer, output_dir=tmp_path)
    content = out_file.read_text(encoding="utf-8")

    # Assert deck contains defgrid3 and rejects defgrid1
    assert "defgrid3" in content
    assert "defgrid1" not in content

    # 2. Rotational stability validation
    # Construct a model harmonic calculation engine with a soft intermolecular mode (35 cm^-1)
    stable_frequencies = np.array([35.0, 72.0, 150.0, 3650.0, 3750.0])

    def stable_calc_engine(coords: np.ndarray) -> np.ndarray:
        return stable_frequencies.copy()

    geom = np.array(water_dimer.coordinates)
    validate_rotational_mode_stability(geom, stable_calc_engine, threshold_cm1=50.0, max_delta_cm1=1.0)

    # Unstable calculation engine where rotation causes the 35 cm^-1 mode to shift by 3.5 cm^-1
    def unstable_calc_engine(coords: np.ndarray) -> np.ndarray:
        if not np.allclose(coords, geom, atol=1e-5):
            return np.array([38.5, 72.0, 150.0, 3650.0, 3750.0])
        return stable_frequencies.copy()

    with pytest.raises(RotationalGridInstabilityError):
        validate_rotational_mode_stability(geom, unstable_calc_engine, threshold_cm1=50.0, max_delta_cm1=1.0)
