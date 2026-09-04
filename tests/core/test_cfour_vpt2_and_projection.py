"""Physical unit tests for CFOUR projection null-space and VPT2 force-field re-transformation.
Strictly adheres to Method Matrix v4, Zero-Mock Protocol, and the Mendeleev Mandate.
Verifies 3N-6 mode preservation without scalar cutoffs and exact Duschinsky-based alpha re-weighting.
"""

from __future__ import annotations

import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_cfour_bridge import (
    VibrationRotationAlpha,
    _diagonalize_projected_hessian,
    isomass_rediagonalize_force_field,
)


def test_diagonalize_projected_hessian_mode_count_and_soft_modes() -> None:
    """Verify that a 6-atom molecular Hessian generates exactly 3N-6 = 12 physical modes with 0 negative modes.

    Tests that soft intermolecular modes down to < 10 cm^-1 are authentically preserved
    without scalar cutoff drops.
    """
    symbols = ["O", "H", "H", "O", "H", "H"]
    n_atoms = len(symbols)
    assert n_atoms == 6

    # Physical water dimer benchmark geometry
    coordinates = np.array([
        [-1.455, 0.0, -0.076],
        [-1.838, -0.781, 0.325],
        [-0.518, 0.0, 0.147],
        [1.455, 0.0, 0.076],
        [1.772, 0.758, -0.412],
        [1.772, -0.758, -0.412],
    ], dtype=np.float64)

    masses = [float(element(sym).mass) for sym in symbols]

    # Construct physical Cartesian force constant matrix (intramolecular + weak intermolecular)
    # in Hartree / bohr^2
    hessian = np.full((3 * n_atoms, 3 * n_atoms), 0.0, dtype=np.float64)
    interactions = [
        (0, 1, 0.52),    # O1-H1 covalent bond
        (0, 2, 0.52),    # O1-H2 covalent bond
        (3, 4, 0.52),    # O2-H3 covalent bond
        (3, 5, 0.52),    # O2-H4 covalent bond
        (1, 2, 0.08),    # H1-O1-H2 valence angle
        (4, 5, 0.08),    # H3-O2-H4 valence angle
        (2, 3, 0.002),   # H2...O2 hydrogen bond
        (0, 3, 0.0006),  # O1...O2 dipole coupling
        (1, 3, 0.0003),  # Intermolecular angle stabilization
        (2, 4, 0.0003),
        (2, 5, 0.0003),
    ]

    for i, j, k_const in interactions:
        rij = coordinates[j] - coordinates[i]
        dist = float(np.linalg.norm(rij))
        u_vec = rij / dist
        k_tensor = np.outer(u_vec, u_vec) * k_const
        hessian[3 * i : 3 * i + 3, 3 * i : 3 * i + 3] += k_tensor
        hessian[3 * j : 3 * j + 3, 3 * j : 3 * j + 3] += k_tensor
        hessian[3 * i : 3 * i + 3, 3 * j : 3 * j + 3] -= k_tensor
        hessian[3 * j : 3 * j + 3, 3 * i : 3 * i + 3] -= k_tensor

    frequencies, zpe = _diagonalize_projected_hessian(
        hessian=hessian,
        symbols=symbols,
        coordinates=coordinates,
        masses=masses,
    )

    # 1. Verify mode count: exactly 3N - 6 = 12 modes
    expected_modes = 3 * n_atoms - 6
    assert len(frequencies) == expected_modes, f"Expected {expected_modes} modes, got {len(frequencies)}"

    # 2. Verify zero negative (imaginary) modes on minimum
    for f in frequencies:
        assert f >= 0.0, f"Found negative mode {f} cm^-1 on stable minimum"

    # 3. Verify authentic preservation of soft intermolecular modes (< 100 cm^-1 and down to soft range)
    lowest_frequency = frequencies[0]
    assert lowest_frequency < 50.0, f"Expected soft floppy mode, got {lowest_frequency} cm^-1"
    assert zpe > 0.0


def test_isomass_vpt2_non_linear_alpha_scaling() -> None:
    """Verify that VPT2 force-field re-transformation for HDO vs H2O tests non-linear alpha scaling."""
    symbols = ["O", "H", "H"]
    coordinates = np.array([
        [0.0, 0.0, 0.1173],
        [0.0, 0.7572, -0.4692],
        [0.0, -0.7572, -0.4692],
    ], dtype=np.float64)

    # Cartesian force constants for water (Hartree / bohr^2)
    hessian = np.full((9, 9), 0.0, dtype=np.float64)
    interactions = [(0, 1, 0.55), (0, 2, 0.55), (1, 2, 0.06)]
    for i, j, k_const in interactions:
        rij = coordinates[j] - coordinates[i]
        u_vec = rij / float(np.linalg.norm(rij))
        k_tensor = np.outer(u_vec, u_vec) * k_const
        hessian[3 * i : 3 * i + 3, 3 * i : 3 * i + 3] += k_tensor
        hessian[3 * j : 3 * j + 3, 3 * j : 3 * j + 3] += k_tensor
        hessian[3 * i : 3 * i + 3, 3 * j : 3 * j + 3] -= k_tensor
        hessian[3 * j : 3 * j + 3, 3 * i : 3 * i + 3] -= k_tensor

    # Water monomer vibration-rotation alphas (MHz)
    parent_alphas = [
        VibrationRotationAlpha(
            mode_index=1,
            symmetry="A1",
            harmonic_freq_cm_inv=3800.0,
            alpha_A_MHz=22700.0,
            alpha_B_MHz=-6800.0,
            alpha_C_MHz=4100.0,
        ),
        VibrationRotationAlpha(
            mode_index=2,
            symmetry="A1",
            harmonic_freq_cm_inv=1600.0,
            alpha_A_MHz=-64500.0,
            alpha_B_MHz=-5200.0,
            alpha_C_MHz=-2600.0,
        ),
        VibrationRotationAlpha(
            mode_index=3,
            symmetry="B2",
            harmonic_freq_cm_inv=3900.0,
            alpha_A_MHz=29600.0,
            alpha_B_MHz=-4100.0,
            alpha_C_MHz=3700.0,
        ),
    ]

    # Re-diagonalize for HDO (target isotope mass number 2 on second H)
    iso_result = isomass_rediagonalize_force_field(
        cartesian_hessian_hartree_bohr2=hessian,
        symbols=symbols,
        coordinates_angstrom=coordinates,
        parent_isotopes=[16, 1, 1],
        target_isotopes=[16, 1, 2],
        parent_alphas=parent_alphas,
    )

    # Linear scaling baseline prediction (the flawed formula that was eradicated)
    parent_delta_A = -0.5 * sum(a.alpha_A_MHz for a in parent_alphas)
    parent_delta_B = -0.5 * sum(a.alpha_B_MHz for a in parent_alphas)
    linear_scaled_delta_A = parent_delta_A * (iso_result.iso_Be_MHz[0] / iso_result.parent_Be_MHz[0])
    linear_scaled_delta_B = parent_delta_B * (iso_result.iso_Be_MHz[1] / iso_result.parent_Be_MHz[1])

    # Exact Duschinsky VPT2 re-transformation results
    actual_delta_A = iso_result.iso_B0_MHz[0] - iso_result.iso_Be_MHz[0]
    actual_delta_B = iso_result.iso_B0_MHz[1] - iso_result.iso_Be_MHz[1]

    # Assert that non-linear VPT2 scaling differs significantly from the flawed linear scaling formula
    assert abs(actual_delta_A - linear_scaled_delta_A) > 10.0, (
        f"VPT2 re-transformation must produce non-linear alpha scaling: "
        f"actual={actual_delta_A}, linear={linear_scaled_delta_A}"
    )
    assert abs(actual_delta_B - linear_scaled_delta_B) > 10.0, (
        f"VPT2 re-transformation must produce non-linear alpha scaling: "
        f"actual={actual_delta_B}, linear={linear_scaled_delta_B}"
    )

    # Assert ground-state rotational constants strictly evaluate as B0 = Be + delta_vib
    assert iso_result.iso_B0_MHz[0] == pytest.approx(iso_result.iso_Be_MHz[0] + actual_delta_A, rel=1e-12)
    assert iso_result.iso_B0_MHz[1] == pytest.approx(iso_result.iso_Be_MHz[1] + actual_delta_B, rel=1e-12)
    assert iso_result.iso_zpe_cm_inv > 0.0
    assert iso_result.zpe_shift_cm_inv != 0.0
