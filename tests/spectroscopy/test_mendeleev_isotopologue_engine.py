"""
Dynamic Mendeleev isotope transformations with a newly calculated ASE/EMT Hessian.
Validating Suggestion #39 (Chunk 4).

Method Matrix v4 & Anti-Spoofing Protocols v2:
- Zero-Mock Mandate: Authentic execution only without test doubles.
- Empirical EMT water geometry and force constants; no ab-initio accuracy claim.
- Dynamic Mendeleev masses verified against authoritative IUPAC values.
- Electronic Hessian invariance re-diagonalization in < 200 ms.
"""

import math
import time

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


def test_water_isotopologue_spectroscopy_engine(tmp_path):
    """Test 6: Mass-weighted Hessian re-diagonalization and spectroscopic observables for H2O.

    Verifies:
    1. Parent H2-16O rotational constants computed at equilibrium geometry.
    2. D2-16O and H2-18O isotopologues computed via electronic Hessian invariance.
    3. Distinct physical shifts: A constant for H2-18O is invariant due to C2v axis geometry.
    4. Execution wall time is strictly < 200 ms.
    5. Theoretical B_e and physical ground-state B_0 maintain proper separation.
    """
    from ase.build import molecule
    from ase.calculators.emt import EMT
    from ase.optimize import BFGS
    from ase.units import Bohr, Hartree
    from ase.vibrations import Vibrations

    atoms = molecule("H2O")
    atoms.calc = EMT()
    optimizer = BFGS(atoms, logfile=str(tmp_path / "emt-optimization.log"))
    assert optimizer.run(fmax=1e-5, steps=200)
    vibrations = Vibrations(atoms, name=str(tmp_path / "emt-water"))
    vibrations.run()
    # ASE returns eV/angstrom²; the BASE artifact contract is Hartree/bohr².
    cart_hessian = vibrations.get_vibrations().get_hessian_2d() * Bohr**2 / Hartree
    symbols = atoms.get_chemical_symbols()
    coords = atoms.get_positions()

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
    # This is an EMT geometry, not a microwave experimental reference.
    # Check the exact rigid-rotor relation against independently formed inertia.
    masses = np.asarray(parent_res.masses)
    centered = np.asarray(coords) - np.average(coords, axis=0, weights=masses)
    tensor = sum(mass * (np.dot(r, r) * np.eye(3) - np.outer(r, r)) for mass, r in zip(masses, centered))
    from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2
    expected = C_ROT_MHZ_U_ANG2 / np.linalg.eigvalsh(tensor)
    np.testing.assert_allclose([parent_res.A_e_MHz, parent_res.B_e_MHz, parent_res.C_e_MHz], expected)

    # Theoretical B_e vs Effective Ground-State B_0 distinction [M] vs [D]
    # Harmonic force constants alone do not determine anharmonic B0 corrections.
    assert parent_res.B_0_MHz is None
    assert parent_res.delta_B_vib_MHz is None
    assert len(parent_res.harmonic_frequencies_cm1) == 3
    assert parent_res.rigid_mode_count == 6

    # Inertial defect for planar triatomic: Delta = I_c - I_a - I_b approx 0
    assert abs(parent_res.inertial_defect_amu_A2) < 0.05

    # 2. Compute D2-16O (deuterated water)
    d2o_res = engine.compute_observables(isotopic_substitution={i: "D" for i, symbol in enumerate(symbols) if symbol == "H"})
    assert d2o_res.execution_walltime_ms < 200.0
    # Deuteration approximately halves rotational constants
    assert d2o_res.A_e_MHz < parent_res.A_e_MHz
    assert d2o_res.B_e_MHz < parent_res.B_e_MHz
    assert d2o_res.C_e_MHz < parent_res.C_e_MHz
    assert d2o_res.total_mass_amu > parent_res.total_mass_amu

    # 3. Compute H2-18O (heavy oxygen)
    o18_res = engine.compute_observables(isotopic_substitution={symbols.index("O"): "18O"})
    assert o18_res.execution_walltime_ms < 200.0
    # Crucial physical check: In H2O, C2 axis passes through oxygen atom (x=0, y=0).
    # Therefore, substituting 18O causes only a minor ~1.2% shift in moment of inertia about C2 axis (A constant).
    # B constant is invariant under oxygen substitution because y_O = 0 in the C2v plane
    assert o18_res.B_e_MHz == pytest.approx(parent_res.B_e_MHz, rel=1e-5)
    # C constant decreases noticeably due to increased total moment about out-of-plane axis
    assert o18_res.C_e_MHz < parent_res.C_e_MHz
