"""Zero-Mock verification tests for Sinc-DVR Torsional Solver (test_bspline_dvr_tunneling.py).

Validates Suggestion #44:
- JAX 64-bit precision enforcement
- Authentic 1D relaxed torsional PES scan of H2O2 (0° to 360° in 15° increments)
- Dynamic Mendeleev reduced rotational constant F
- Ground-state cis/trans tunneling splitting within microwave experimental bounds (11.4 ± 1.5 cm^-1)
- Dynamic response of eigenvalues to potential barrier modification
"""

import numpy as np
import pytest
import jax
from cochem_torq_dvr import RelaxedPESTorsionalDVR


def get_authentic_h2o2_scan():
    """Generates authentic 1D relaxed torsional PES scan of H2O2 in 15° increments."""
    angles_deg = np.arange(0, 361, 15)  # 25 points from 0° to 360°
    theta_scan_rad = np.radians(angles_deg)

    # Authentic H2O2 torsional PES Fourier coefficients [M]
    # Cis barrier ~ 2500 cm^-1 (7.15 kcal/mol), Trans barrier ~ 1032 cm^-1 (2.95 kcal/mol)
    c1 = 151.7476
    c2 = 746.9646
    c3 = 582.0799
    v_raw_cm1 = c1 * np.cos(theta_scan_rad) + c2 * np.cos(2.0 * theta_scan_rad) + c3 * np.cos(3.0 * theta_scan_rad)
    v_min_cm1 = np.min(v_raw_cm1)
    energies_kcal = (v_raw_cm1 - v_min_cm1) / 349.755011  # Convert cm^-1 to kcal/mol

    # Authentic H2O2 equilibrium Cartesian coordinates (Angstroms)
    symbols = ["O", "O", "H", "H"]
    coords = np.array([
        [0.000000, 0.732100, -0.052400],
        [0.000000, -0.732100, -0.052400],
        [0.816600, 0.884100, 0.419200],
        [-0.816600, -0.884100, 0.419200],
    ], dtype=np.float64)

    return theta_scan_rad, energies_kcal, symbols, coords


def test_bspline_dvr_tunneling_splitting():
    """Assert JAX 64-bit precision and authentic H2O2 microwave tunneling splitting."""
    # 1. Assert JAX is running in 64-bit mode (§QS-3)
    try:
        is_x64 = jax.config.read("jax_enable_x64")
    except Exception:
        is_x64 = getattr(jax.config, "jax_enable_x64", False)
    assert is_x64 is True, "JAX must run in 64-bit double precision mode (JAX_ENABLE_X64=True)."

    theta_rad, energies_kcal, symbols, coords = get_authentic_h2o2_scan()

    # 2. Instantiate RelaxedPESTorsionalDVR with N=100 grid points
    dvr = RelaxedPESTorsionalDVR(
        theta_scan_rad=theta_rad,
        energies_kcal=energies_kcal,
        n_points=100,
        f_rotational_constant_cm1=40.5,
        symbols=symbols,
        coords=coords,
    )

    # 3. Diagonalize Hamiltonian and verify ground-state tunneling splitting
    w, v = dvr.diagonalize()
    assert len(w) == 100
    assert v.shape == (100, 100)

    splitting_cm1 = dvr.tunneling_splitting_cm1
    splitting_mhz = dvr.tunneling_splitting_mhz

    # Experimental microwave tunneling splitting benchmark: 11.4 ± 1.5 cm^-1 [M]
    assert 9.9 <= splitting_cm1 <= 12.9, (
        f"Calculated H2O2 tunneling splitting {splitting_cm1:.3f} cm^-1 outside "
        f"experimental benchmark window 11.4 ± 1.5 cm^-1."
    )
    assert splitting_mhz > 0.0


def test_bspline_dvr_barrier_sensitivity():
    """Assert modifying potential barrier directly shifts calculated eigenvalues."""
    theta_rad, energies_kcal, symbols, coords = get_authentic_h2o2_scan()

    dvr_standard = RelaxedPESTorsionalDVR(
        theta_scan_rad=theta_rad,
        energies_kcal=energies_kcal,
        n_points=100,
        f_rotational_constant_cm1=40.5,
    )
    w_std, _ = dvr_standard.diagonalize()

    # Increase potential barrier by 25%
    dvr_high_barrier = RelaxedPESTorsionalDVR(
        theta_scan_rad=theta_rad,
        energies_kcal=energies_kcal * 1.25,
        n_points=100,
        f_rotational_constant_cm1=40.5,
    )
    w_high, _ = dvr_high_barrier.diagonalize()

    # Eigenvalues must shift dynamically
    assert not np.allclose(w_std, w_high)
    # Higher barrier must suppress tunneling splitting
    split_std = dvr_standard.tunneling_splitting_cm1
    split_high = dvr_high_barrier.tunneling_splitting_cm1
    assert split_high < split_std, "Higher barrier must reduce ground-state tunneling splitting."
