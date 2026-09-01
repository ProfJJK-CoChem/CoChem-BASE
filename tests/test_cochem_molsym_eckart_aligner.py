#!/usr/bin/env python3
"""
Authentic Physical Verification Test Suite for CoChem MolSym & Eckart Frame Aligner.
Target: intake/cochem_molsym_eckart_aligner.py
Module: tests/test_cochem_molsym_eckart_aligner.py

Directives:
- Zero-Mock Anti-Spoofing: Authentic physical datasets, real physical calculations.
- Method Matrix & Standards: Mendeleev dynamic mass, ghost atom handling,
  Eckart frame alignment, SVD reflection protection, and vibrational projector invariants.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import List, Tuple

import mendeleev
import numpy as np
import pytest

REPO_ROOT = Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE").resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intake.cochem_molsym_eckart_aligner import (
    AlignmentStatus,
    CenterOfMassEngine,
    CenterOfMassError,
    DynamicMendeleevMassMap,
    EckartFrameAligner,
    InertiaTensorEngine,
    MassResolutionError,
    MolSymEckartAlignmentResult,
    MolSymEngine,
    RotorTopType,
    VibrationalProjectorEngine,
    align_to_eckart_frame,
    align_to_principal_axes,
    analyze_molecular_symmetry,
    compute_center_of_mass,
    compute_moment_of_inertia_tensor,
    construct_vibrational_projector,
    diagonalize_inertia_tensor,
    get_dynamic_atomic_mass,
    is_ghost_symbol,
    project_cartesian_hessian,
    project_mass_weighted_hessian,
    resolve_molecular_masses,
    standardize_and_align_molsym_eckart,
    translate_to_center_of_mass,
)


# ==============================================================================
# TEST 1: Dynamic Mendeleev Mass Resolution & Ghost Atom Protections
# ==============================================================================
def test_dynamic_mendeleev_mass_resolution_and_ghost_protections():
    """Verify dynamic atomic mass resolution strictly via Mendeleev and ghost atom zero-mass rules."""
    # Standard elements
    m_h = get_dynamic_atomic_mass("H")
    m_c = get_dynamic_atomic_mass("C")
    m_o = get_dynamic_atomic_mass("O")
    assert abs(m_h - float(mendeleev.element("H").mass)) < 1e-6
    assert abs(m_c - float(mendeleev.element("C").mass)) < 1e-6
    assert abs(m_o - float(mendeleev.element("O").mass)) < 1e-6

    # Isotopes
    m_d = get_dynamic_atomic_mass("D")
    m_2h = get_dynamic_atomic_mass("2H")
    m_13c = get_dynamic_atomic_mass("13C")
    assert abs(m_d - 2.01410177812) < 1e-4
    assert abs(m_2h - 2.01410177812) < 1e-4
    assert abs(m_13c - 13.003354835) < 1e-4

    # Ghost atom identification & zero-mass protection
    ghost_symbols = ["Gh", "gh", "GhO", "Gh_C", "Bq", "bq", "X", "x", "X_N", "x-1"]
    for sym in ghost_symbols:
        assert is_ghost_symbol(sym) is True, f"Failed to identify {sym} as ghost"
        assert get_dynamic_atomic_mass(sym) == 0.0, f"Ghost {sym} must have exactly 0.0 mass"

    # Real elements that start with X or similar must NOT be ghosts
    assert is_ghost_symbol("Xe") is False
    assert is_ghost_symbol("xe") is False
    assert is_ghost_symbol("XE") is False
    assert get_dynamic_atomic_mass("Xe") > 130.0

    # Invalid input handling
    with pytest.raises(MassResolutionError):
        get_dynamic_atomic_mass("InvalidElementFooBar")


# ==============================================================================
# TEST 2: Center of Mass Translation & Iterative Floating-Point Refinement
# ==============================================================================
def test_center_of_mass_translation_and_precision():
    """Verify COM translation and iterative residual refinement ensuring ||sum(m_i * r'_i)|| < 1e-14."""
    # Water molecule translated arbitrarily in space
    water_syms = ["O", "H", "H"]
    water_coords = np.array([
        [10.000000, 20.000000, 30.117300],
        [10.000000, 20.757200, 29.530800],
        [10.000000, 19.242800, 29.530800],
    ], dtype=np.float64)

    translated_coords, shift = translate_to_center_of_mass(water_coords, symbols=water_syms)
    masses = resolve_molecular_masses(water_coords, symbols=water_syms)
    total_mass = np.sum(masses)

    # Verify COM is exactly at origin (0, 0, 0)
    com_residual = np.sum(translated_coords * masses[:, np.newaxis], axis=0) / total_mass
    assert np.linalg.norm(com_residual) < 1e-14, f"COM residual too large: {np.linalg.norm(com_residual)}"

    # Verify interatomic pairwise distances are strictly invariant under translation
    d_orig = np.linalg.norm(water_coords[0] - water_coords[1])
    d_trans = np.linalg.norm(translated_coords[0] - translated_coords[1])
    assert abs(d_orig - d_trans) < 1e-14

    # Ghost atom inclusion must not shift the COM
    bsse_syms = ["O", "H", "H", "Gh", "Gh", "Gh"]
    bsse_coords = np.vstack([water_coords, [[100.0, 200.0, 300.0], [105.0, 205.0, 305.0], [110.0, 210.0, 310.0]]])
    bsse_com = compute_center_of_mass(bsse_coords, symbols=bsse_syms)
    real_com = compute_center_of_mass(water_coords, symbols=water_syms)
    assert np.linalg.norm(bsse_com - real_com) < 1e-14


# ==============================================================================
# TEST 3: Moment of Inertia Tensor, Diagonalization, and Right-Handed SO(3) Frame
# ==============================================================================
def test_moment_of_inertia_tensor_and_codata_spectroscopy():
    """Verify Moment of Inertia tensor construction, Ia <= Ib <= Ic ordering, and det(V) = +1.0."""
    # Water planar molecule at origin
    coords = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)
    syms = ["O", "H", "H"]
    masses = resolve_molecular_masses(coords, symbols=syms)
    coords_com, _ = translate_to_center_of_mass(coords, masses=masses)

    I_tensor = compute_moment_of_inertia_tensor(coords_com, masses)
    assert I_tensor.shape == (3, 3)
    assert np.allclose(I_tensor, I_tensor.T), "Inertia tensor must be symmetric"

    eigvals, V = diagonalize_inertia_tensor(I_tensor)
    Ia, Ib, Ic = eigvals

    # Assert ascending sort: Ia <= Ib <= Ic
    assert Ia <= Ib <= Ic
    assert Ia > 0.0 and Ib > 0.0 and Ic > 0.0

    # Assert proper rotation det(V) == +1.0 (right-handed coordinate system)
    det_v = np.linalg.det(V)
    assert abs(det_v - 1.0) < 1e-10, f"Determinant of V must be +1.0, got {det_v}"

    # Planar molecule inertial defect Delta = Ic - Ia - Ib approx 0
    delta = Ic - Ia - Ib
    assert abs(delta) < 1e-3, f"Planar inertial defect Delta should be ~0, got {delta}"


# ==============================================================================
# TEST 4: Authoritative Rotor Top Classifications & Linear Molecule Singularities
# ==============================================================================
def test_rotor_classification_and_linear_singularity():
    """Verify classification of Asymmetric, Spherical, Oblate, Prolate, and Linear rotor tops."""
    # 1. Asymmetric top: H2O
    h2o_res = standardize_and_align_molsym_eckart(
        np.array([[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]]),
        symbols=["O", "H", "H"],
    )
    assert h2o_res.top_type == RotorTopType.ASYMMETRIC

    # 2. Spherical top: CH4 (Td)
    a = 1.089 / math.sqrt(3)
    ch4_coords = np.array([[0.0, 0.0, 0.0], [a, a, a], [a, -a, -a], [-a, a, -a], [-a, -a, a]])
    ch4_res = standardize_and_align_molsym_eckart(ch4_coords, symbols=["C", "H", "H", "H", "H"])
    assert ch4_res.top_type == RotorTopType.SPHERICAL
    assert abs(ch4_res.inertia_result.rays_kappa) < 1e-3

    # 3. Linear top singularity: CO2 (Ia -> 0, A -> inf, B == C)
    co2_coords = np.array([[0.0, 0.0, -1.162], [0.0, 0.0, 0.0], [0.0, 0.0, 1.162]])
    co2_res = standardize_and_align_molsym_eckart(co2_coords, symbols=["O", "C", "O"])
    assert co2_res.top_type == RotorTopType.LINEAR
    assert math.isinf(co2_res.inertia_result.rotational_constants_mhz[0])
    b_mhz = co2_res.inertia_result.rotational_constants_mhz[1]
    c_mhz = co2_res.inertia_result.rotational_constants_mhz[2]
    assert abs(b_mhz - c_mhz) < 1e-4

    # 4. Oblate symmetric top: Benzene C6H6 (Ia == Ib < Ic, kappa = +1.0)
    r_c, r_h = 1.397, 1.397 + 1.084
    c6h6_coords = []
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_c * math.cos(ang), r_c * math.sin(ang), 0.0])
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_h * math.cos(ang), r_h * math.sin(ang), 0.0])
    c6h6_res = standardize_and_align_molsym_eckart(np.array(c6h6_coords), symbols=["C"] * 6 + ["H"] * 6)
    assert c6h6_res.top_type == RotorTopType.SYMMETRIC_OBLATE
    assert abs(c6h6_res.inertia_result.rays_kappa - 1.0) < 1e-2


# ==============================================================================
# TEST 5: MolSym Point-Group Symmetry, SEAs, and Rotational Numbers
# ==============================================================================
def test_molsym_point_group_and_symmetry_orbits():
    """Verify point group symmetry detection, rotational symmetry number sigma, and SEA partitioning."""
    # Water: C2v, sigma = 2, 2 SEA orbits ([O], [H1, H2])
    water_coords = np.array([[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]])
    prof_h2o = analyze_molecular_symmetry(water_coords, symbols=["O", "H", "H"])
    assert prof_h2o.point_group in {"C2v", "C2"}
    assert prof_h2o.rotational_symmetry_number == 2
    assert len(prof_h2o.symmetrically_equivalent_atoms) == 2

    # Methane: Td, sigma = 12, 2 SEA orbits ([C], [H1, H2, H3, H4])
    a = 1.089 / math.sqrt(3)
    ch4_coords = np.array([[0.0, 0.0, 0.0], [a, a, a], [a, -a, -a], [-a, a, -a], [-a, -a, a]])
    prof_ch4 = analyze_molecular_symmetry(ch4_coords, symbols=["C", "H", "H", "H", "H"])
    assert prof_ch4.point_group.startswith("T")
    assert prof_ch4.rotational_symmetry_number == 12
    assert len(prof_ch4.symmetrically_equivalent_atoms) == 2

    # Benzene: D6h, sigma = 12
    r_c, r_h = 1.397, 1.397 + 1.084
    c6h6_coords = []
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_c * math.cos(ang), r_c * math.sin(ang), 0.0])
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_h * math.cos(ang), r_h * math.sin(ang), 0.0])
    prof_c6h6 = analyze_molecular_symmetry(np.array(c6h6_coords), symbols=["C"] * 6 + ["H"] * 6)
    assert prof_c6h6.point_group.startswith("D6")
    assert prof_c6h6.rotational_symmetry_number == 12


# ==============================================================================
# TEST 6: Mass-Weighted Eckart Frame Alignment & Residual Verification
# ==============================================================================
def test_eckart_frame_alignment_and_conditions():
    """Verify mass-weighted Eckart frame alignment, translational & rotational Eckart conditions."""
    water_syms = ["O", "H", "H"]
    water_ref = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)

    # Apply rigid 3D rotation and arbitrary spatial translation
    theta, phi = 0.5236, 1.0472
    Rx = np.array([[1, 0, 0], [0, math.cos(theta), -math.sin(theta)], [0, math.sin(theta), math.cos(theta)]])
    Rz = np.array([[math.cos(phi), -math.sin(phi), 0], [math.sin(phi), math.cos(phi), 0], [0, 0, 1]])
    R_true = Rx @ Rz
    water_target = (water_ref @ R_true) + np.array([5.0, -12.0, 7.5])

    # Slight geometric perturbation (internal vibration)
    water_target[1] += np.array([0.015, -0.010, 0.005])

    eckart_res = align_to_eckart_frame(water_target, water_ref, symbols=water_syms)

    # 1. Rotational Eckart condition: ||sum(m_i * (r_i^0 x r'_i))|| <= 1e-12
    assert eckart_res.residual_rotational_norm <= 1e-12, f"Rotational residual {eckart_res.residual_rotational_norm} > 1e-12"

    # 2. Translational Eckart condition: ||sum(m_i * r'_i) / M|| <= 1e-12
    assert eckart_res.translational_residual_norm <= 1e-12, f"Translational residual {eckart_res.translational_residual_norm} > 1e-12"

    # 3. Proper rotation check: det(U) == +1.0
    assert abs(eckart_res.rotation_determinant - 1.0) < 1e-8, f"Rotation determinant must be 1.0, got {eckart_res.rotation_determinant}"
    assert eckart_res.is_proper_rotation is True
    assert eckart_res.status in {AlignmentStatus.CONVERGED, AlignmentStatus.EXACT_MATCH}


# ==============================================================================
# TEST 7: SVD Reflection Protection & SO(3) Proper Rotation Invariant
# ==============================================================================
def test_svd_reflection_protection_proper_so3():
    """Verify that inverted / mirrored target structures are protected from improper reflection matrices."""
    water_syms = ["O", "H", "H"]
    water_ref = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)

    # Invert parity: Reflection across plane (x, y, z) -> (x, y, -z)
    reflection_matrix = np.diag([1.0, 1.0, -1.0])
    reflected_target = water_ref @ reflection_matrix

    eckart_res = align_to_eckart_frame(reflected_target, water_ref, symbols=water_syms)

    # SVD algorithm must enforce det(U) = +1.0 and prevent improper reflection
    det_u = np.linalg.det(eckart_res.rotation_matrix)
    assert abs(det_u - 1.0) < 1e-8, f"Determinant of U must be +1.0 even for reflected conformer, got {det_u}"
    assert eckart_res.is_proper_rotation is True


# ==============================================================================
# TEST 8: Vibrational Projector P_vib Invariants & Hessian Rigid Mode Zeroing
# ==============================================================================
def test_vibrational_projector_and_hessian_projection():
    """Verify algebraic invariants of P_vib = I - P_rigid (Idempotency, Symmetry, Trace) and Hessian zeroing."""
    water_syms = ["O", "H", "H"]
    water_coords = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)
    N = len(water_coords)

    # 1. Non-linear molecule: Water (Tr = 3N - 6 = 3)
    P_vib_water = construct_vibrational_projector(water_coords, symbols=water_syms, is_linear=False)
    assert P_vib_water.shape == (3 * N, 3 * N)

    # Idempotence: P_vib @ P_vib = P_vib
    assert np.allclose(P_vib_water @ P_vib_water, P_vib_water, atol=1e-10), "P_vib must be idempotent"

    # Symmetry: P_vib^T = P_vib
    assert np.allclose(P_vib_water.T, P_vib_water, atol=1e-10), "P_vib must be symmetric"

    # Trace invariant: Tr(P_vib) = 3N - 6 = 3
    assert abs(np.trace(P_vib_water) - 3.0) < 1e-10, f"Expected Tr=3.0, got {np.trace(P_vib_water)}"

    # 2. Linear molecule: CO2 (Tr = 3N - 5 = 4)
    co2_syms = ["O", "C", "O"]
    co2_coords = np.array([[0.0, 0.0, -1.162], [0.0, 0.0, 0.0], [0.0, 0.0, 1.162]])
    P_vib_co2 = construct_vibrational_projector(co2_coords, symbols=co2_syms, is_linear=True)
    assert abs(np.trace(P_vib_co2) - 4.0) < 1e-10, f"Expected Tr=4.0, got {np.trace(P_vib_co2)}"

    # 3. Hessian Projection: 6 zero eigenvalues
    np.random.seed(42)
    A = np.random.randn(9, 9)
    H_mw_synthetic = A + A.T + 10.0 * np.eye(9)

    H_proj = project_mass_weighted_hessian(H_mw_synthetic, water_coords, symbols=water_syms, is_linear=False)
    eigvals, _ = np.linalg.eigh(H_proj)
    sorted_abs_eigvals = np.sort(np.abs(eigvals))

    # The lowest 6 eigenvalues must be zero within floating point tolerance
    for i in range(6):
        assert sorted_abs_eigvals[i] < 1e-10, f"Rigid mode {i} eigenvalue not zeroed: {sorted_abs_eigvals[i]}"

    # The remaining 3 eigenvalues (vibrations) must be positive
    for i in range(6, 9):
        assert sorted_abs_eigvals[i] > 1e-2, f"Vibrational mode {i} erroneously zeroed"
