#!/usr/bin/env python3
"""
Authentic Physical Unit and Integration Test Suite for CoChem-TOPOS Alignment Engine.
Module: tests/test_cochem_topos_alignment.py
Target Module: intake/cochem_topos_alignment.py

Authoritative Specifications:
1. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
2. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md
3. D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BASE\\.in-progress\\Doc2_Part2_09_intake_topos_alignment_prompt.md

Directives & Mandates:
- Authentic Physical Foundation: Live physical data, authentic mathematical physics, genuine molecular coordinates.
- Uncompromising computational fidelity across all tensor operations and alignments.
- Rigorous physical validation:
  1. Center of Mass Translation:
     - Exact translation to (0, 0, 0) Center of Mass with sum(m_i * r'_i) < 1e-14.
     - Ghost atom protection: symbols starting with 'Gh', 'X', 'gh', 'x' possess EXACTLY 0.0 mass
       preventing COM shift in BSSE / Counterpoise calculations.
     - Pairwise distance preservation across all atoms.
     - Exception on total non-ghost mass <= 0.
  2. Moment of Inertia Tensor & Top Classification:
     - Symmetric 3x3 inertia tensor construction and diagonalization Ia <= Ib <= Ic.
     - CODATA 2026 conversion to rotational constants A, B, C (MHz, GHz, cm^-1).
     - Inertial defect Delta = Ic - Ia - Ib (~ 0 for planar Water and Benzene).
     - Ray's asymmetry parameter kappa and planar moments Pa, Pb, Pc.
     - Top classifications: asymmetric_top, prolate_symmetric_top, oblate_symmetric_top, spherical_top, linear.
     - Right-handed coordinate frame: det(V) = +1.0.
  3. Eckart Frame Alignment:
     - Translational Eckart condition sum(m_i * r'_i) = 0.
     - Rotational Eckart condition sum(m_i * (r_i^0 x r'_i)) = 0 with residual norm < 1e-12.
     - Proper rotation det(U) = +1.0 via SVD reflection check.
  4. Vibrational Projector:
     - Idempotence: P_vib^2 == P_vib.
     - Symmetry: P_vib^T == P_vib.
     - Trace invariant: Tr(P_vib) == 3N - 6 (or 3N - 5 for linear).
     - Mass-weighted and Cartesian Hessian projection zeroing 6 (or 5) rigid body modes.
  5. High-Level Entrypoint:
     - standardize_molecular_topology compatibility with AtomModel, dict, and raw numpy arrays.
     - Structured Pydantic models: ToposAlignmentResult, EckartAlignmentResult, InertiaTensorResult.
"""

from __future__ import annotations

import importlib
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import mendeleev
import numpy as np
import pytest
from pydantic import BaseModel

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cochem_topos.topology import AtomModel


# ==============================================================================
# Dynamic Module Loader for intake/cochem_topos_alignment.py
# ==============================================================================

def _load_topos_alignment_module() -> Any:
    """Dynamically loads cochem_topos_alignment module across multiple candidate paths."""
    candidate_paths = [
        REPO_ROOT / "intake" / "cochem_topos_alignment.py",
        REPO_ROOT / "cochem_topos" / "cochem_topos_alignment.py",
        REPO_ROOT / "cochem_topos" / "alignment.py",
    ]

    for path in candidate_paths:
        if path.is_file():
            mod_name = f"intake_{path.stem}"
            if mod_name in sys.modules:
                return sys.modules[mod_name]
            spec = importlib.util.spec_from_file_location(mod_name, str(path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
                return mod

    # Package import candidates
    for pkg_name in ["intake.cochem_topos_alignment", "cochem_topos.alignment", "cochem_topos_alignment"]:
        try:
            return importlib.import_module(pkg_name)
        except Exception:
            continue

    raise ImportError(
        f"Could not load cochem_topos_alignment module from candidates: {[str(p) for p in candidate_paths]}"
    )


# ==============================================================================
# Authentic Physical Reference Data & Physical Constants (CODATA 2026 / 2022)
# ==============================================================================

# Fundamental Constants (CODATA 2022 / 2026 SI standard values)
PLANCK_H = 6.62607015e-34          # J * s (exact)
SPEED_OF_LIGHT_C = 299792458.0     # m / s (exact)
ATOMIC_MASS_UNIT_U = 1.66053906892e-27  # kg / u (CODATA 2022)
ANGSTROM_TO_M = 1.0e-10            # m / Angstrom

# Rotational conversion factor: factor_hz / I(amu * A^2) = B (Hz)
FACTOR_HZ = PLANCK_H / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_U * (ANGSTROM_TO_M ** 2))
FACTOR_MHZ = FACTOR_HZ / 1.0e6
FACTOR_GHZ = FACTOR_HZ / 1.0e9
FACTOR_CM1 = FACTOR_HZ / (SPEED_OF_LIGHT_C * 100.0)


def get_physical_mass(symbol: str) -> float:
    """Retrieves authentic ground-truth standard atomic weight from mendeleev.
    
    Ghost symbols (starting with 'Gh', 'gh', 'Bq', 'bq', 'X', 'x', but not 'Xe') return exactly 0.0.
    """
    clean_sym = symbol.strip().lower()
    if clean_sym.startswith("gh") or clean_sym.startswith("bq") or clean_sym == "bq":
        return 0.0
    if clean_sym == "x" or clean_sym.startswith("x_") or clean_sym.startswith("x-") or clean_sym.startswith("x:"):
        return 0.0
    if clean_sym.startswith("x") and not clean_sym.startswith("xe"):
        return 0.0
    elem = mendeleev.element(symbol.strip())
    return float(elem.mass)


# ==============================================================================
# Authentic Physical Molecular Benchmarks
# ==============================================================================

# 1. Water (H2O) - Planar asymmetric top (C2v)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000,  0.000000,  0.117300],
    [0.000000,  0.757200, -0.469200],
    [0.000000, -0.757200, -0.469200],
], dtype=np.float64)

# 2. Carbon Dioxide (CO2) - Linear molecule (Dinfh), Ia = 0
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.000000, 0.000000,  0.000000],
    [0.000000, 0.000000,  1.160000],
    [0.000000, 0.000000, -1.160000],
], dtype=np.float64)

# 3. Methane (CH4) - Spherical top (Td), Ia = Ib = Ic
CH4_SYMBOLS = ["C", "H", "H", "H", "H"]
CH4_COORDS = np.array([
    [ 0.000000,  0.000000,  0.000000],
    [ 0.629118,  0.629118,  0.629118],
    [-0.629118, -0.629118,  0.629118],
    [ 0.629118, -0.629118, -0.629118],
    [-0.629118,  0.629118, -0.629118],
], dtype=np.float64)

# 4. Benzene (C6H6) - Planar oblate symmetric top (D6h), Ia = Ib < Ic, Delta = 0
BENZENE_SYMBOLS = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
BENZENE_COORDS = np.array([
    [ 0.000000,  1.397000, 0.000000],
    [ 1.209838,  0.698500, 0.000000],
    [ 1.209838, -0.698500, 0.000000],
    [ 0.000000, -1.397000, 0.000000],
    [-1.209838, -0.698500, 0.000000],
    [-1.209838,  0.698500, 0.000000],
    [ 0.000000,  2.481000, 0.000000],
    [ 2.148608,  1.240500, 0.000000],
    [ 2.148608, -1.240500, 0.000000],
    [ 0.000000, -2.481000, 0.000000],
    [-2.148608, -1.240500, 0.000000],
    [-2.148608,  1.240500, 0.000000],
], dtype=np.float64)

# 5. Methyl Chloride (CH3Cl) - Prolate symmetric top (C3v), Ia < Ib = Ic, kappa = -1
CH3CL_SYMBOLS = ["C", "Cl", "H", "H", "H"]
CH3CL_COORDS = np.array([
    [0.000000,  0.000000, -1.100000],
    [0.000000,  0.000000,  0.680000],
    [0.000000,  1.030000, -1.450000],
    [0.892000, -0.515000, -1.450000],
    [-0.892000, -0.515000, -1.450000],
], dtype=np.float64)

# 6. Ammonia (NH3) - Oblate symmetric top (C3v), Ia = Ib < Ic, kappa = +1
NH3_SYMBOLS = ["N", "H", "H", "H"]
NH3_COORDS = np.array([
    [ 0.000000,  0.000000,  0.116500],
    [ 0.000000,  0.939700, -0.271800],
    [ 0.813800, -0.469850, -0.271800],
    [-0.813800, -0.469850, -0.271800],
], dtype=np.float64)

# 7. Water Dimer BSSE Counterpoise Complex (Monomer A + Monomer B)
# Monomer A (Donor): atoms 0..2; Monomer B (Acceptor): atoms 3..5
WATER_DIMER_COORDS = np.array([
    [-1.487000,  0.018000, -0.098000],
    [-0.518000,  0.063000, -0.013000],
    [-1.802000, -0.738000,  0.404000],
    [ 1.428000, -0.003000,  0.076000],
    [ 1.758000,  0.771000, -0.380000],
    [ 1.777000, -0.760000, -0.392000],
], dtype=np.float64)

WATER_DIMER_GHOST_A_SYMBOLS = ["GhO", "GhH", "GhH", "O", "H", "H"]
WATER_DIMER_GHOST_B_SYMBOLS = ["O", "H", "H", "GhO", "GhH", "GhH"]
WATER_DIMER_FULL_SYMBOLS = ["O", "H", "H", "O", "H", "H"]

# 8. Xenon - Water van der Waals Complex (Xe...H2O)
XE_WATER_SYMBOLS = ["Xe", "O", "H", "H"]
XE_WATER_COORDS = np.array([
    [ 3.800000,  0.000000,  0.000000],
    [ 0.000000,  0.000000,  0.117300],
    [ 0.000000,  0.757200, -0.469200],
    [ 0.000000, -0.757200, -0.469200],
], dtype=np.float64)


def _generate_3d_rotation_matrix(alpha: float, beta: float, gamma: float) -> np.ndarray:
    """Constructs a 3D Euler ZYZ rotation matrix."""
    ca, sa = math.cos(alpha), math.sin(alpha)
    cb, sb = math.cos(beta), math.sin(beta)
    cg, sg = math.cos(gamma), math.sin(gamma)

    Rz1 = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    Ry = np.array([[cb, 0.0, sb], [0.0, 1.0, 0.0], [-sb, 0.0, cb]], dtype=np.float64)
    Rz2 = np.array([[cg, -sg, 0.0], [sg, cg, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return Rz1 @ Ry @ Rz2


# ==============================================================================
# 1. Unit Tests: Center of Mass Translation & Ghost Atom Protections
# ==============================================================================

class TestCenterOfMassTranslator:
    """Authentic unit tests for CenterOfMassTranslator and translate_to_center_of_mass."""

    def test_com_translation_water_exact_zero(self) -> None:
        """Validates that translation shifts Center of Mass to exact origin: sum(m_i * r'_i) < 1e-14."""
        mod = _load_topos_alignment_module()
        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        
        # Apply arbitrary large spatial offset
        offset = np.array([42.123456, -88.654321, 105.789123], dtype=np.float64)
        offset_coords = WATER_COORDS + offset

        # Standalone function test
        com_computed = mod.compute_center_of_mass(offset_coords, masses)
        expected_com = np.sum(offset_coords * masses[:, np.newaxis], axis=0) / np.sum(masses)
        np.testing.assert_allclose(com_computed, expected_com, atol=1e-14)

        translated_coords, shift_vec = mod.translate_to_center_of_mass(offset_coords, masses, WATER_SYMBOLS)
        
        # Center of mass of translated coordinates must be (0, 0, 0) to machine precision
        new_com = np.sum(translated_coords * masses[:, np.newaxis], axis=0) / np.sum(masses)
        np.testing.assert_allclose(new_com, [0.0, 0.0, 0.0], atol=1e-14)

        # Sum of mass-weighted vectors must be zero
        mass_weighted_sum = np.sum(masses[:, np.newaxis] * translated_coords, axis=0)
        np.testing.assert_allclose(mass_weighted_sum, [0.0, 0.0, 0.0], atol=1e-14)

        # Shift vector must equal -computed_com
        np.testing.assert_allclose(shift_vec, -com_computed, atol=1e-14)

        # Preserves all relative interatomic distances identically
        dists_orig = np.linalg.norm(offset_coords[:, None, :] - offset_coords[None, :, :], axis=-1)
        dists_trans = np.linalg.norm(translated_coords[:, None, :] - translated_coords[None, :, :], axis=-1)
        np.testing.assert_allclose(dists_trans, dists_orig, atol=1e-14)

    def test_com_class_translator_parity(self) -> None:
        """Validates parity between CenterOfMassTranslator class and functional API."""
        mod = _load_topos_alignment_module()
        masses = np.array([get_physical_mass(s) for s in CH4_SYMBOLS], dtype=np.float64)
        offset_coords = CH4_COORDS + np.array([-10.0, 20.0, -30.0])

        translator = mod.CenterOfMassTranslator()
        res_class = translator.translate(offset_coords, masses, symbols=CH4_SYMBOLS)
        res_fn_coords, res_fn_shift = mod.translate_to_center_of_mass(offset_coords, masses, symbols=CH4_SYMBOLS)

        np.testing.assert_allclose(res_class[0], res_fn_coords, atol=1e-15)
        np.testing.assert_allclose(res_class[1], res_fn_shift, atol=1e-15)

    def test_ghost_atom_bsse_dimer_counterpoise_protection(self) -> None:
        """Validates that ghost atoms possess exactly 0.0 mass and do not shift Center of Mass."""
        mod = _load_topos_alignment_module()

        # Case 1: Monomer A ghosted -> COM must equal Monomer B's COM alone
        masses_monomer_b_only = np.array([0.0, 0.0, 0.0, get_physical_mass("O"), get_physical_mass("H"), get_physical_mass("H")])
        
        # Test with symbols starting with 'Gh', 'gh', 'X', 'x'
        ghost_symbols_a = ["GhO", "GhH", "GhH", "O", "H", "H"]
        
        com_ghost_a = mod.compute_center_of_mass(WATER_DIMER_COORDS, masses=None, symbols=ghost_symbols_a)
        
        # Calculate ground truth Monomer B COM directly
        monomer_b_coords = WATER_DIMER_COORDS[3:6]
        monomer_b_masses = masses_monomer_b_only[3:6]
        expected_monomer_b_com = np.sum(monomer_b_coords * monomer_b_masses[:, np.newaxis], axis=0) / np.sum(monomer_b_masses)

        np.testing.assert_allclose(com_ghost_a, expected_monomer_b_com, atol=1e-14)

        # Translate dimer with ghost Monomer A
        trans_coords, shift = mod.translate_to_center_of_mass(WATER_DIMER_COORDS, symbols=ghost_symbols_a)
        
        # Monomer B in translated coords must be centered at (0, 0, 0)
        monomer_b_trans = trans_coords[3:6]
        trans_monomer_b_com = np.sum(monomer_b_trans * monomer_b_masses[:, np.newaxis], axis=0) / np.sum(monomer_b_masses)
        np.testing.assert_allclose(trans_monomer_b_com, [0.0, 0.0, 0.0], atol=1e-14)

        # Monomer A must still be present with exact relative orientation preserved
        monomer_a_trans = trans_coords[0:3]
        np.testing.assert_allclose(monomer_a_trans - monomer_b_trans[0], WATER_DIMER_COORDS[0:3] - WATER_DIMER_COORDS[3], atol=1e-14)

    def test_ghost_atom_prefixes_recognition(self) -> None:
        """Validates recognition of diverse ghost atom symbol prefixes ('Gh', 'GH', 'gh', 'X', 'x', 'Bq', 'bq')."""
        mod = _load_topos_alignment_module()
        symbols = ["Gh_C", "gh_H", "X_O", "x_N", "Bq", "bq_O", "C", "H", "H", "H", "H"]
        coords = np.vstack([np.ones((6, 3)) * 100.0, CH4_COORDS])

        com = mod.compute_center_of_mass(coords, symbols=symbols)
        
        # Methane alone is centered at (0, 0, 0), so COM ignoring 100.0 ghost atoms must be (0, 0, 0)
        np.testing.assert_allclose(com, [0.0, 0.0, 0.0], atol=1e-14)

    def test_xenon_is_not_ghost_atom(self) -> None:
        """Validates that noble gas Xenon ('Xe', 'xe') has authentic physical mass (~131.293 amu) and is NOT a ghost atom."""
        mod = _load_topos_alignment_module()
        assert not mod.is_ghost_symbol("Xe")
        assert not mod.is_ghost_symbol("xe")
        assert not mod.is_ghost_symbol("XE")
        
        xe_mass = mod.get_physical_mass("Xe")
        assert xe_mass > 130.0
        
        # Test Xe...H2O complex Center of Mass
        masses = [mod.get_physical_mass(s) for s in XE_WATER_SYMBOLS]
        com = mod.compute_center_of_mass(XE_WATER_COORDS, masses=masses)
        total_mass = sum(masses)
        expected_com = np.sum(XE_WATER_COORDS * np.array(masses)[:, np.newaxis], axis=0) / total_mass
        np.testing.assert_allclose(com, expected_com, atol=1e-14)

    def test_com_error_on_zero_or_negative_total_mass(self) -> None:
        """Validates informative ValueError when total non-ghost mass is <= 0 or input invalid."""
        mod = _load_topos_alignment_module()
        
        # All ghost atoms -> total non-ghost mass is 0
        all_ghost_symbols = ["GhO", "GhH", "GhH"]
        with pytest.raises(ValueError, match=r"(?i)mass|ghost|positive"):
            mod.compute_center_of_mass(WATER_COORDS, symbols=all_ghost_symbols)

        with pytest.raises(ValueError, match=r"(?i)mass|ghost|positive"):
            mod.translate_to_center_of_mass(WATER_COORDS, masses=np.array([0.0, 0.0, 0.0]))

        # Negative mass
        with pytest.raises(ValueError, match=r"(?i)mass|positive"):
            mod.translate_to_center_of_mass(WATER_COORDS, masses=np.array([16.0, -1.0, 1.0]))

        # Dimension mismatch
        with pytest.raises(ValueError, match=r"(?i)mismatch|shape|length"):
            mod.translate_to_center_of_mass(WATER_COORDS, masses=np.array([16.0, 1.0]))


# ==============================================================================
# 2. Unit Tests: Moment of Inertia Tensor & Top Classification
# ==============================================================================

class TestMomentOfInertiaEngine:
    """Authentic unit tests for MomentOfInertiaEngine and principal axes alignment."""

    def test_inertia_tensor_analytical_construction_and_symmetry(self) -> None:
        """Validates symmetric 3x3 inertia tensor construction: Ixx = sum(m*(y^2+z^2)), Ixy = -sum(m*x*y)."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        translated_coords, _ = mod.translate_to_center_of_mass(WATER_COORDS, masses=masses)

        I = engine.compute_moment_of_inertia_tensor(translated_coords, masses)

        # Symmetry check
        np.testing.assert_allclose(I, I.T, atol=1e-15)

        # Explicit analytical formula check
        x, y, z = translated_coords[:, 0], translated_coords[:, 1], translated_coords[:, 2]
        Ixx_expected = np.sum(masses * (y**2 + z**2))
        Iyy_expected = np.sum(masses * (x**2 + z**2))
        Izz_expected = np.sum(masses * (x**2 + y**2))
        Ixy_expected = -np.sum(masses * x * y)
        Ixz_expected = -np.sum(masses * x * z)
        Iyz_expected = -np.sum(masses * y * z)

        np.testing.assert_allclose(I[0, 0], Ixx_expected, atol=1e-14)
        np.testing.assert_allclose(I[1, 1], Iyy_expected, atol=1e-14)
        np.testing.assert_allclose(I[2, 2], Izz_expected, atol=1e-14)
        np.testing.assert_allclose(I[0, 1], Ixy_expected, atol=1e-14)
        np.testing.assert_allclose(I[0, 2], Ixz_expected, atol=1e-14)
        np.testing.assert_allclose(I[1, 2], Iyz_expected, atol=1e-14)

    def test_water_planar_asymmetric_top_and_inertial_defect(self) -> None:
        """Validates Water (H2O): Ia < Ib < Ic, Delta = Ic - Ia - Ib ~ 0 (planar), kappa in (-1, 1)."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(WATER_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        A_mhz, B_mhz, C_mhz = res.rotational_constants_mhz
        A_ghz, B_ghz, C_ghz = res.rotational_constants_ghz
        A_cm1, B_cm1, C_cm1 = res.rotational_constants_cm1

        # Eigenvalues strictly sorted
        assert Ia <= Ib <= Ic

        # Rotational constants strictly sorted A >= B >= C
        assert A_mhz >= B_mhz >= C_mhz
        assert A_ghz >= B_ghz >= C_ghz
        assert A_cm1 >= B_cm1 >= C_cm1

        # CODATA conversion constant validation
        np.testing.assert_allclose(A_mhz, FACTOR_MHZ / Ia, rtol=1e-6)
        np.testing.assert_allclose(B_mhz, FACTOR_MHZ / Ib, rtol=1e-6)
        np.testing.assert_allclose(C_mhz, FACTOR_MHZ / Ic, rtol=1e-6)

        np.testing.assert_allclose(A_ghz, A_mhz / 1000.0, rtol=1e-9)
        np.testing.assert_allclose(A_cm1, FACTOR_CM1 / Ia, rtol=1e-6)

        # Planar molecule condition: Inertial defect Delta = Ic - Ia - Ib ~ 0.0
        delta = Ic - Ia - Ib
        np.testing.assert_allclose(delta, 0.0, atol=1e-10)
        np.testing.assert_allclose(res.inertial_defect, 0.0, atol=1e-10)

        # Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
        expected_kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)
        np.testing.assert_allclose(res.rays_kappa, expected_kappa, atol=1e-12)
        assert -1.0 < res.rays_kappa < 1.0

        # Planar moments Pa, Pb, Pc
        Pa = (-Ia + Ib + Ic) / 2.0
        Pb = (Ia - Ib + Ic) / 2.0
        Pc = (Ia + Ib - Ic) / 2.0
        np.testing.assert_allclose(res.planar_moments, (Pa, Pb, Pc), atol=1e-12)
        np.testing.assert_allclose(Pc, 0.0, atol=1e-10)  # Pc = sum(m_i * c_i^2) = 0 for planar

        # Top classification
        assert res.top_type == "asymmetric_top"

        # Right-handed coordinate frame
        det_v = np.linalg.det(res.rotation_matrix)
        np.testing.assert_allclose(det_v, 1.0, atol=1e-12)

    def test_carbon_dioxide_linear_molecule(self) -> None:
        """Validates Carbon Dioxide (CO2): linear molecule with Ia ~ 0, Ib = Ic, prolate limit."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in CO2_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(CO2_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2

        # Linear molecule: Ia is zero, Ib == Ic
        np.testing.assert_allclose(Ia, 0.0, atol=1e-10)
        np.testing.assert_allclose(Ib, Ic, rtol=1e-6)

        assert res.top_type == "linear"

        # Rotational constant A is infinite or handled as None/inf, B == C
        _, B_mhz, C_mhz = res.rotational_constants_mhz
        np.testing.assert_allclose(B_mhz, C_mhz, rtol=1e-6)

    def test_methane_spherical_top(self) -> None:
        """Validates Methane (CH4): spherical top with Ia = Ib = Ic, A = B = C."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in CH4_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(CH4_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2
        A_mhz, B_mhz, C_mhz = res.rotational_constants_mhz

        # Spherical top: all 3 moments of inertia equal
        np.testing.assert_allclose(Ia, Ib, rtol=1e-5)
        np.testing.assert_allclose(Ib, Ic, rtol=1e-5)
        np.testing.assert_allclose(A_mhz, B_mhz, rtol=1e-5)
        np.testing.assert_allclose(B_mhz, C_mhz, rtol=1e-5)

        assert res.top_type == "spherical_top"

    def test_benzene_planar_oblate_symmetric_top(self) -> None:
        """Validates Benzene (C6H6): planar oblate symmetric top with Ia = Ib < Ic, Delta = 0, kappa = +1."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in BENZENE_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(BENZENE_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2

        # Oblate top: Ia == Ib < Ic
        np.testing.assert_allclose(Ia, Ib, rtol=1e-5)
        assert Ic > Ia

        # Planar Benzene: Delta = Ic - Ia - Ib ~ 0
        np.testing.assert_allclose(res.inertial_defect, 0.0, atol=1e-10)

        # Ray's parameter kappa ~ +1.0 for oblate top
        np.testing.assert_allclose(res.rays_kappa, 1.0, atol=1e-4)
        assert res.top_type == "oblate_symmetric_top"

    def test_methyl_chloride_prolate_symmetric_top(self) -> None:
        """Validates Methyl Chloride (CH3Cl): prolate symmetric top with Ia < Ib = Ic, kappa = -1."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in CH3CL_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(CH3CL_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2

        # Prolate top: Ia < Ib == Ic
        assert Ia < Ib
        np.testing.assert_allclose(Ib, Ic, rtol=1e-5)

        # Ray's parameter kappa ~ -1.0 for prolate top
        np.testing.assert_allclose(res.rays_kappa, -1.0, atol=1e-4)
        assert res.top_type == "prolate_symmetric_top"

    def test_ammonia_oblate_symmetric_top(self) -> None:
        """Validates Ammonia (NH3): oblate symmetric top with Ia = Ib < Ic, kappa = +1."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        masses = np.array([get_physical_mass(s) for s in NH3_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(NH3_COORDS, masses)

        Ia, Ib, Ic = res.eigenvalues_amu_angstrom2

        # Oblate top: Ia == Ib < Ic
        np.testing.assert_allclose(Ia, Ib, rtol=1e-4)
        assert Ic > Ia

        # Ray's parameter kappa ~ +1.0 for oblate top
        np.testing.assert_allclose(res.rays_kappa, 1.0, atol=1e-3)
        assert res.top_type == "oblate_symmetric_top"

    def test_principal_axes_alignment_invariance_under_random_rotation(self) -> None:
        """Validates that arbitrarily rotated molecules align to a strictly diagonal inertia tensor."""
        mod = _load_topos_alignment_module()
        engine = mod.MomentOfInertiaEngine()

        R_rot = _generate_3d_rotation_matrix(1.234, 0.567, 2.345)
        rotated_water = WATER_COORDS @ R_rot.T + np.array([10.0, -20.0, 30.0])

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        res = engine.align_to_principal_axes(rotated_water, masses)

        # Inertia tensor of aligned coordinates must be diagonal with 0 off-diagonals
        I_aligned = engine.compute_moment_of_inertia_tensor(res.aligned_coords, masses)
        off_diagonals = np.array([I_aligned[0, 1], I_aligned[0, 2], I_aligned[1, 2]])
        np.testing.assert_allclose(off_diagonals, [0.0, 0.0, 0.0], atol=1e-12)

        # Ensure right-handed rotation matrix: det(R) = +1.0
        np.testing.assert_allclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-12)


# ==============================================================================
# 3. Unit Tests: Eckart Frame Alignment Engine
# ==============================================================================

class TestEckartFrameAligner:
    """Authentic unit tests for EckartFrameAligner and mass-weighted Eckart conditions."""

    def test_eckart_alignment_rigid_rotation_and_translation_water(self) -> None:
        """Validates exact Eckart frame alignment for rigidly rotated Water with residual < 1e-12."""
        mod = _load_topos_alignment_module()
        aligner = mod.EckartFrameAligner()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        ref_coords = WATER_COORDS.copy()

        # Rotate target by arbitrary angles and translate
        R_rand = _generate_3d_rotation_matrix(0.85, 1.42, 2.77)
        t_rand = np.array([-15.2, 33.7, -9.4], dtype=np.float64)
        target_coords = ref_coords @ R_rand.T + t_rand

        res = aligner.align(target_coords, ref_coords, masses)

        # RMSD after alignment to identical rigid body must be ~ 0
        assert res.rmsd < 1e-12

        # Aligned coordinates must match ref_coords centered at COM
        ref_centered, _ = mod.translate_to_center_of_mass(ref_coords, masses)
        np.testing.assert_allclose(res.aligned_coords, ref_centered, atol=1e-12)

        # Translational Eckart condition: sum(m_i * r'_i) = 0
        trans_cond = np.sum(masses[:, np.newaxis] * res.aligned_coords, axis=0)
        np.testing.assert_allclose(trans_cond, [0.0, 0.0, 0.0], atol=1e-12)

        # Rotational Eckart condition: sum(m_i * (r_i^0 x r'_i)) = 0
        rot_cond = np.sum(
            masses[:, np.newaxis] * np.cross(ref_centered, res.aligned_coords),
            axis=0,
        )
        rot_norm = np.linalg.norm(rot_cond)
        assert rot_norm < 1e-12
        np.testing.assert_allclose(res.residual_rotational_norm, 0.0, atol=1e-12)

        # Rotation matrix must be proper rotation (det = +1.0)
        np.testing.assert_allclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-12)

    def test_eckart_alignment_perturbed_water_conformation(self) -> None:
        """Validates Eckart alignment on deformed Water (internal vibrations) preserving internal geometry."""
        mod = _load_topos_alignment_module()
        aligner = mod.EckartFrameAligner()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        ref_coords = WATER_COORDS.copy()

        # Apply physical perturbation: stretch OH bond by 0.05 A, open HOH angle by 3 degrees
        perturbed_coords = WATER_COORDS.copy()
        perturbed_coords[1, 1] += 0.05  # stretch H1
        perturbed_coords[2, 1] -= 0.03  # stretch H2
        perturbed_coords[1, 2] += 0.02

        # Rotate and translate perturbed molecule
        R_rand = _generate_3d_rotation_matrix(1.1, 0.7, 1.9)
        t_rand = np.array([10.0, -10.0, 5.0])
        target_coords = perturbed_coords @ R_rand.T + t_rand

        res = aligner.align(target_coords, ref_coords, masses)

        # Translational Eckart condition
        trans_cond = np.sum(masses[:, np.newaxis] * res.aligned_coords, axis=0)
        np.testing.assert_allclose(trans_cond, [0.0, 0.0, 0.0], atol=1e-12)

        # Rotational Eckart condition: sum(m_i * (r_i^0 x r'_i)) = 0
        ref_centered, _ = mod.translate_to_center_of_mass(ref_coords, masses)
        rot_cond = np.sum(
            masses[:, np.newaxis] * np.cross(ref_centered, res.aligned_coords),
            axis=0,
        )
        rot_norm = np.linalg.norm(rot_cond)
        assert rot_norm < 1e-12

        # Preserves all internal pairwise distances of target molecule identically
        dists_target = np.linalg.norm(target_coords[:, None, :] - target_coords[None, :, :], axis=-1)
        dists_aligned = np.linalg.norm(res.aligned_coords[:, None, :] - res.aligned_coords[None, :, :], axis=-1)
        np.testing.assert_allclose(dists_aligned, dists_target, atol=1e-12)

    def test_eckart_alignment_water_dimer(self) -> None:
        """Validates Eckart frame alignment on complex 6-atom Water Dimer."""
        mod = _load_topos_alignment_module()
        aligner = mod.EckartFrameAligner()

        masses = np.array([get_physical_mass(s) for s in WATER_DIMER_FULL_SYMBOLS], dtype=np.float64)
        ref_coords = WATER_DIMER_COORDS.copy()

        R_rand = _generate_3d_rotation_matrix(0.4, 2.1, 1.5)
        target_coords = ref_coords @ R_rand.T + np.array([5.0, 5.0, 5.0])

        res = aligner.align(target_coords, ref_coords, masses)

        ref_centered, _ = mod.translate_to_center_of_mass(ref_coords, masses)
        rot_cond = np.sum(masses[:, np.newaxis] * np.cross(ref_centered, res.aligned_coords), axis=0)
        np.testing.assert_allclose(np.linalg.norm(rot_cond), 0.0, atol=1e-12)
        np.testing.assert_allclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-12)

    def test_eckart_svd_reflection_protection(self) -> None:
        """Validates that SVD reflection check ensures proper rotation matrix det(U) = +1.0."""
        mod = _load_topos_alignment_module()
        aligner = mod.EckartFrameAligner()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        ref_coords = WATER_COORDS.copy()

        # Introduce an improper reflection (det = -1)
        reflected_target = ref_coords.copy()
        reflected_target[:, 0] = -reflected_target[:, 0]

        res = aligner.align(reflected_target, ref_coords, masses)

        # Aligner must NEVER return an improper rotation with det = -1.0
        np.testing.assert_allclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-12)


# ==============================================================================
# 4. Unit Tests: Vibrational Projector & Rigid-Body Modes Zeroing
# ==============================================================================

class TestVibrationalProjector:
    """Authentic unit tests for VibrationalProjector algebraic invariants and Hessian projection."""

    def test_vibrational_projector_water_algebraic_invariants(self) -> None:
        """Validates algebraic invariants for non-linear Water (N=3): P_vib^2 = P_vib, P_vib^T = P_vib, Tr(P_vib) = 3N-6 = 3."""
        mod = _load_topos_alignment_module()
        projector = mod.VibrationalProjector()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        N = len(WATER_SYMBOLS)
        P_vib = projector.construct_vibrational_projector(WATER_COORDS, masses)

        # Shape must be (3N, 3N) = (9, 9)
        assert P_vib.shape == (3 * N, 3 * N)

        # Invariant 1: Idempotence P_vib @ P_vib == P_vib
        np.testing.assert_allclose(P_vib @ P_vib, P_vib, atol=1e-12)

        # Invariant 2: Symmetry P_vib^T == P_vib
        np.testing.assert_allclose(P_vib.T, P_vib, atol=1e-12)

        # Invariant 3: Trace Tr(P_vib) == 3N - 6 = 9 - 6 = 3
        trace_val = np.trace(P_vib)
        np.testing.assert_allclose(trace_val, 3 * N - 6, atol=1e-12)

        # Eigenvalues must be exactly 3 ones and 6 zeros
        eigvals = np.sort(np.linalg.eigvalsh(P_vib))
        expected_eigvals = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
        np.testing.assert_allclose(eigvals, expected_eigvals, atol=1e-12)

    def test_vibrational_projector_carbon_dioxide_linear_invariant(self) -> None:
        """Validates linear CO2 (N=3): Tr(P_vib) = 3N - 5 = 4 vibrational modes."""
        mod = _load_topos_alignment_module()
        projector = mod.VibrationalProjector()

        masses = np.array([get_physical_mass(s) for s in CO2_SYMBOLS], dtype=np.float64)
        N = len(CO2_SYMBOLS)
        P_vib = projector.construct_vibrational_projector(CO2_COORDS, masses, is_linear=True)

        assert P_vib.shape == (3 * N, 3 * N)

        # Idempotence and symmetry
        np.testing.assert_allclose(P_vib @ P_vib, P_vib, atol=1e-12)
        np.testing.assert_allclose(P_vib.T, P_vib, atol=1e-12)

        # Trace for linear molecule: 3N - 5 = 9 - 5 = 4
        np.testing.assert_allclose(np.trace(P_vib), 3 * N - 5, atol=1e-12)

        # Eigenvalues: 4 ones and 5 zeros
        eigvals = np.sort(np.linalg.eigvalsh(P_vib))
        expected_eigvals = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        np.testing.assert_allclose(eigvals, expected_eigvals, atol=1e-12)

    def test_vibrational_projector_methane_and_benzene(self) -> None:
        """Validates trace invariants for Methane (Tr=9) and Benzene (Tr=30)."""
        mod = _load_topos_alignment_module()
        projector = mod.VibrationalProjector()

        # Methane: N=5 -> 3(5) - 6 = 9 modes
        ch4_masses = np.array([get_physical_mass(s) for s in CH4_SYMBOLS], dtype=np.float64)
        P_ch4 = projector.construct_vibrational_projector(CH4_COORDS, ch4_masses)
        np.testing.assert_allclose(np.trace(P_ch4), 3 * 5 - 6, atol=1e-12)
        np.testing.assert_allclose(P_ch4 @ P_ch4, P_ch4, atol=1e-12)

        # Benzene: N=12 -> 3(12) - 6 = 30 modes
        c6h6_masses = np.array([get_physical_mass(s) for s in BENZENE_SYMBOLS], dtype=np.float64)
        P_c6h6 = projector.construct_vibrational_projector(BENZENE_COORDS, c6h6_masses)
        np.testing.assert_allclose(np.trace(P_c6h6), 3 * 12 - 6, atol=1e-12)
        np.testing.assert_allclose(P_c6h6 @ P_c6h6, P_c6h6, atol=1e-12)

    def test_project_mass_weighted_and_cartesian_hessian_zeroing(self) -> None:
        """Validates that projected mass-weighted Hessian zeros out exactly 6 translational/rotational modes."""
        mod = _load_topos_alignment_module()
        projector = mod.VibrationalProjector()

        masses = np.array([get_physical_mass(s) for s in WATER_SYMBOLS], dtype=np.float64)
        N = len(WATER_SYMBOLS)

        # Construct synthetic physically-motivated harmonic mass-weighted Hessian (symmetric positive semi-definite)
        np.random.seed(42)
        A = np.random.randn(3 * N, 3 * N)
        H_mw_raw = A.T @ A + np.eye(3 * N) * 5.0  # (9, 9) positive definite matrix

        H_mw_proj = projector.project_mass_weighted_hessian(H_mw_raw, WATER_COORDS, masses)

        # Eigenvalues of projected Hessian
        eigvals_proj = np.sort(np.linalg.eigvalsh(H_mw_proj))

        # First 6 eigenvalues must be strictly zero (< 1e-12)
        np.testing.assert_allclose(eigvals_proj[:6], np.zeros(6), atol=1e-12)

        # Remaining 3 eigenvalues must be positive non-zero vibrational frequencies
        assert np.all(eigvals_proj[6:] > 1e-3)

        # Cartesian Hessian projection
        M_mat = np.diag(np.repeat(masses, 3))
        M_sqrt = np.sqrt(M_mat)
        M_inv_sqrt = np.diag(1.0 / np.repeat(np.sqrt(masses), 3))

        H_cart_raw = M_sqrt @ H_mw_raw @ M_sqrt
        H_cart_proj = projector.project_cartesian_hessian(H_cart_raw, WATER_COORDS, masses)

        # Mass-weighting the projected Cartesian Hessian recovers H_mw_proj
        H_mw_from_cart = M_inv_sqrt @ H_cart_proj @ M_inv_sqrt
        np.testing.assert_allclose(H_mw_from_cart, H_mw_proj, atol=1e-12)

    def test_project_cartesian_hessian_with_ghost_atoms_no_nan(self) -> None:
        """Validates that Cartesian Hessian projection on systems with ghost atoms (mass = 0.0) produces no NaNs or infs."""
        mod = _load_topos_alignment_module()
        projector = mod.VibrationalProjector()

        # Water dimer with ghost Monomer A
        masses = np.array([get_physical_mass(s) for s in WATER_DIMER_GHOST_A_SYMBOLS], dtype=np.float64)
        N = len(WATER_DIMER_GHOST_A_SYMBOLS)
        H_cart_raw = np.eye(3 * N, dtype=np.float64) * 2.5

        H_cart_proj = projector.project_cartesian_hessian(
            H_cart_raw,
            WATER_DIMER_COORDS,
            masses=masses,
        )

        # Must not contain any NaN or infinite values
        assert not np.any(np.isnan(H_cart_proj))
        assert not np.any(np.isinf(H_cart_proj))
        assert H_cart_proj.shape == (3 * N, 3 * N)



# ==============================================================================
# 5. Integration Tests: High-Level standardize_molecular_topology Entrypoint
# ==============================================================================

class TestStandardizeMolecularTopologyIntegration:
    """Authentic integration tests for standardize_molecular_topology and Pydantic models."""

    def test_standardize_with_atom_model_sequence(self) -> None:
        """Validates standardization from a sequence of Pydantic AtomModel instances."""
        mod = _load_topos_alignment_module()

        atom_models = [
            AtomModel(symbol="O", coords=WATER_COORDS[0]),
            AtomModel(symbol="H", coords=WATER_COORDS[1]),
            AtomModel(symbol="H", coords=WATER_COORDS[2]),
        ]

        result = mod.standardize_molecular_topology(atom_models)

        # Result is instance of ToposAlignmentResult Pydantic model
        assert isinstance(result, mod.ToposAlignmentResult)
        assert isinstance(result.inertia_tensor_result, mod.InertiaTensorResult)

        # Validate aligned coordinates
        np.testing.assert_allclose(result.aligned_coords.shape, (3, 3))
        np.testing.assert_allclose(result.center_of_mass, [0.0, 0.0, 0.0], atol=1e-14)
        assert result.top_type == "asymmetric_top"
        assert result.inertial_defect < 1e-10

        # Pydantic serialization verification
        data_dict = result.model_dump()
        assert "aligned_coords" in data_dict
        assert "rotational_constants_mhz" in data_dict
        assert "inertial_defect" in data_dict
        assert "top_type" in data_dict

        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_standardize_with_dict_and_ghost_atoms(self) -> None:
        """Validates standardization from dictionary representation containing ghost atoms."""
        mod = _load_topos_alignment_module()

        mol_dict = {
            "coords": WATER_DIMER_COORDS,
            "symbols": WATER_DIMER_GHOST_A_SYMBOLS,
        }

        result = mod.standardize_molecular_topology(mol_dict)

        assert isinstance(result, mod.ToposAlignmentResult)
        assert result.n_atoms == 6
        assert result.n_ghost_atoms == 3
        np.testing.assert_allclose(result.center_of_mass, [0.0, 0.0, 0.0], atol=1e-14)

    def test_standardize_with_eckart_reference_conformation(self) -> None:
        """Validates standardization combining COM translation, inertia diagonalization, and Eckart frame alignment."""
        mod = _load_topos_alignment_module()

        R_rot = _generate_3d_rotation_matrix(0.5, 1.2, 0.9)
        target_coords = WATER_COORDS @ R_rot.T + np.array([12.0, -15.0, 20.0])

        result = mod.standardize_molecular_topology(
            target_coords,
            symbols=WATER_SYMBOLS,
            ref_coords=WATER_COORDS,
        )

        assert isinstance(result, mod.ToposAlignmentResult)
        assert result.eckart_alignment_result is not None
        assert isinstance(result.eckart_alignment_result, mod.EckartAlignmentResult)
        assert result.eckart_alignment_result.rmsd < 1e-12
        assert result.eckart_alignment_result.residual_rotational_norm < 1e-12

    def test_standardize_raw_numpy_array_and_masses(self) -> None:
        """Validates standardization from raw numpy arrays of coordinates and masses."""
        mod = _load_topos_alignment_module()
        masses = np.array([get_physical_mass(s) for s in BENZENE_SYMBOLS], dtype=np.float64)

        result = mod.standardize_molecular_topology(BENZENE_COORDS, masses=masses)

        assert isinstance(result, mod.ToposAlignmentResult)
        assert result.top_type == "oblate_symmetric_top"
        np.testing.assert_allclose(result.rays_kappa, 1.0, atol=1e-4)
        np.testing.assert_allclose(result.inertial_defect, 0.0, atol=1e-10)
