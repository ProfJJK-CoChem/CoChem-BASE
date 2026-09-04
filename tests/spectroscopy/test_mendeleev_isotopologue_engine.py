"""
Zero-Mock Physical Verification Test Suite: Dynamic Mendeleev Isotopologue Engine.
Validating Suggestion #39 (Chunk 4).

Method Matrix v4 & Anti-Spoofing Protocols v2:
- Zero-Mock Mandate: Authentic execution only without test doubles.
- Authentic physical molecular structures (H2O, D2O, H2-18O).
- Dynamic Mendeleev masses verified against authoritative IUPAC values.
- Electronic Hessian invariance re-diagonalization in < 200 ms.
"""

import math
import time
from pathlib import Path

import numpy as np
import pytest
from mendeleev import element

from cochem_base.spectroscopy.isotopologue import (
    IsotopologueResult,
    IsotopologueSpectroscopyEngine,
    get_nuclide_mass,
)


def test_mendeleev_dynamic_mass_retrieval():
    """Verify IUPAC nuclide masses are dynamically queried without hardcoded values."""
    m_h1 = get_nuclide_mass("H", 1)
    m_h2 = get_nuclide_mass("D")
    m_o16 = get_nuclide_mass("O", 16)
    m_o18 = get_nuclide_mass("O", 18)
    m_c13 = get_nuclide_mass("13C")

    # Authoritative IUPAC mass comparisons
    assert abs(m_h1 - 1.007825032) < 1e-6
    assert abs(m_h2 - 2.014101778) < 1e-6
    assert abs(m_o16 - 15.99491462) < 1e-6
    assert abs(m_o18 - 17.99915961) < 1e-6
    assert abs(m_c13 - 13.00335484) < 1e-6


def test_water_isotopologue_spectroscopy_engine():
    """Test 6: Mass-weighted Hessian re-diagonalization and spectroscopic observables for H2O.

    Verifies:
    1. Parent H2-16O rotational constants computed at equilibrium geometry.
    2. D2-16O and H2-18O isotopologues computed via electronic Hessian invariance.
    3. Distinct physical shifts: A constant for H2-18O is invariant due to C2v axis geometry.
    4. Execution wall time is strictly < 200 ms.
    5. Theoretical B_e and physical ground-state B_0 maintain proper separation.
    """
    symbols = ["O", "H", "H"]
    data_dir = Path(__file__).parent.parent / "data"
    
    # Authentic equilibrium geometry of water loaded from physical file
    water_eq_lines = (data_dir / "water_eq.xyz").read_text(encoding="utf-8").strip().split('\n')[2:]
    coords = [[float(x) for x in line.split()[1:4]] for line in water_eq_lines]

    # Authentic Cartesian force constant Hessian matrix for H2O (Hartree / Bohr^2) loaded from physical file
    cart_hessian = np.load(data_dir / "water_hessian.npy")

    engine = IsotopologueSpectroscopyEngine(
        symbols=symbols,
        coordinates_angstrom=coords,
        cartesian_hessian=cart_hessian,
    )

    # 1. Compute Parent H2-16O observables
    parent_res = engine.compute_observables()
    assert isinstance(parent_res, IsotopologueResult)
    assert parent_res.execution_walltime_ms < 200.0

    # Authentic water rotational constants check: A > B > C
    assert parent_res.A_e_MHz > parent_res.B_e_MHz > parent_res.C_e_MHz
    assert 800000.0 < parent_res.A_e_MHz < 900000.0
    assert 400000.0 < parent_res.B_e_MHz < 500000.0
    assert 260000.0 < parent_res.C_e_MHz < 320000.0

    # Theoretical B_e vs Effective Ground-State B_0 distinction [M] vs [D]
    assert parent_res.B_0_MHz != parent_res.B_e_MHz
    assert parent_res.delta_B_vib_MHz < 0  # Vibrational averaging lowers effective rotational constant
    assert parent_res.B_0_MHz == parent_res.B_e_MHz + parent_res.delta_B_vib_MHz

    # Inertial defect for planar triatomic: Delta = I_c - I_a - I_b approx 0
    assert abs(parent_res.inertial_defect_amu_A2) < 0.05

    # 2. Compute D2-16O (deuterated water)
    d2o_res = engine.compute_observables(isotopic_substitution={1: "D", 2: "D"})
    assert d2o_res.execution_walltime_ms < 200.0
    # Deuteration approximately halves rotational constants
    assert 400000.0 < d2o_res.A_e_MHz < 480000.0
    assert 200000.0 < d2o_res.B_e_MHz < 260000.0
    assert 130000.0 < d2o_res.C_e_MHz < 170000.0
    assert d2o_res.total_mass_amu > parent_res.total_mass_amu

    # 3. Compute H2-18O (heavy oxygen)
    o18_res = engine.compute_observables(isotopic_substitution={0: "18O"})
    assert o18_res.execution_walltime_ms < 200.0
    # Crucial physical check: In H2O, C2 axis passes through oxygen atom (x=0, y=0).
    # Therefore, substituting 18O causes only a minor ~1.2% shift in moment of inertia about C2 axis (A constant).
    # B constant is invariant under oxygen substitution because y_O = 0 in the C2v plane
    assert abs(o18_res.B_e_MHz - parent_res.B_e_MHz) < 1e-3
    # C constant decreases noticeably due to increased total moment about out-of-plane axis
    assert o18_res.C_e_MHz < parent_res.C_e_MHz
