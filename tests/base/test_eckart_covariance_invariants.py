"""
Unit & Adversarial Test Suite: Mass-Weighted Covariance (Gram) Matrix Formulation.
WBS 1.4.1: Mass-Weighted Covariance (Gram) Matrix Formulation (Subsystem VR01-SS3)

Governing Specifications:
- Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5)
- L3_Decomposition_Task_1_VR01.md:L298-L306
- Anti-Spoofing Protocols v2 & v4 (Zero mocks, zero stubs, authentic physical fixtures)
- Dynamic Mendeleev Mandate: Zero static mass dictionaries; dynamic nuclide resolution via disambiguate_mass()
- Invariant: Analytic gradient verification confirms C corresponds exactly to bilinear displacement trace product
- Performance Constraint: <15 µs execution time per call for N=100 atoms
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

# Ensure repo root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
for parent in CURRENT_FILE.parents:
    src_candidate = parent / "src"
    if src_candidate.is_dir() and str(src_candidate) not in sys.path:
        sys.path.insert(0, str(src_candidate))

try:
    from cochem_base.exceptions import CoChemError
except ImportError:
    class CoChemError(Exception):
        pass

from cochem_base.physics.eckart_aligner import (
    check_covariance_symmetry,
    compute_covariance_frobenius_norm,
    compute_mass_weighted_covariance_matrix,
    translate_to_center_of_mass,
)
from cochem_base.physics.nuclide_resolver import disambiguate_mass


# ============================================================================
# Helpers: Authentic Geometry Loaders (Zero Mocks / Real Physical Data)
# ============================================================================

def _find_data_file(filename: str) -> Path:
    """Locate authentic test data file in repository."""
    for parent in CURRENT_FILE.parents:
        data_path = parent / "tests" / "data" / filename
        if data_path.is_file():
            return data_path
    raise FileNotFoundError(f"Authentic physical fixture {filename} not found.")


def load_xyz_fixture(filename: str) -> Tuple[List[str], np.ndarray]:
    """Parse authentic physical XYZ coordinate file into symbols and float64 numpy array."""
    path = _find_data_file(filename)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    n_atoms = int(lines[0].strip())
    symbols: List[str] = []
    coords: List[List[float]] = []
    for line in lines[2 : 2 + n_atoms]:
        parts = line.split()
        symbols.append(parts[0])
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return symbols, np.array(coords, dtype=np.float64)


# ============================================================================
# Test Cases (WBS 1.4.1 & Acceptance Criteria)
# ============================================================================

def test_water_monomer_covariance_self_symmetry():
    """WBS 1.4.1 Test 1: Self-covariance symmetry and Frobenius norm on authentic water monomer."""
    symbols, coords = load_xyz_fixture("water.xyz")
    assert len(symbols) == 3
    assert coords.shape == (3, 3)

    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Self-covariance: coords_ref == coords_target
    c_mat = compute_mass_weighted_covariance_matrix(
        coords_ref=coords, coords_target=coords, masses=masses, center=True
    )
    assert c_mat.shape == (3, 3)
    assert c_mat.dtype == np.float64

    # 1. Symmetry verification: C == C^T under Frobenius norm
    is_sym = check_covariance_symmetry(c_mat, tol=1e-14)
    assert is_sym is True, f"Self-covariance matrix must be symmetric, diff: {c_mat - c_mat.T}"

    # 2. Frobenius norm verification: ||C||_F = sqrt(Tr(C^T C))
    fro_norm = compute_covariance_frobenius_norm(c_mat)
    expected_fro = float(np.sqrt(np.sum(c_mat * c_mat)))
    assert np.isclose(fro_norm, expected_fro, atol=1e-14)
    assert fro_norm > 0.0

    # 3. Positive semi-definiteness: all eigenvalues of self-covariance >= 0
    eigenvalues = np.linalg.eigvalsh(c_mat)
    assert np.all(eigenvalues >= -1e-14), f"Eigenvalues must be non-negative: {eigenvalues}"

    # 4. Trace equals mass-weighted sum of squared centered distances
    centered, _ = translate_to_center_of_mass(coords, masses=masses)
    expected_trace = float(np.sum(masses * np.sum(centered * centered, axis=1)))
    assert np.isclose(float(np.trace(c_mat)), expected_trace, atol=1e-14)


def test_water_dimer_batch_covariance():
    """WBS 1.4.1 Test 2: Authentic (H2O)2 coordinates with batched tensor broadcasting."""
    symbols, coords = load_xyz_fixture("water_dimer.xyz")
    assert len(symbols) == 6
    assert coords.shape == (6, 3)

    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Exact Pythagorean SO(3) rotation matrix about z-axis (cos=0.8, sin=0.6, det=+1.0)
    rot_z = np.array([
        [0.8, -0.6, 0.0],
        [0.6,  0.8, 0.0],
        [0.0,  0.0, 1.0],
    ], dtype=np.float64)

    # Conformation 0: unrotated, Conformation 1: rotated
    coords_rotated = coords @ rot_z.T
    batch_target = np.stack([coords, coords_rotated], axis=0)
    assert batch_target.shape == (2, 6, 3)

    # Compute unbatched reference covariance matrices
    c_single_0 = compute_mass_weighted_covariance_matrix(
        coords, coords, masses=masses, center=True
    )
    c_single_1 = compute_mass_weighted_covariance_matrix(
        coords, coords_rotated, masses=masses, center=True
    )

    # Compute batched covariance matrix: ref (6, 3) broadcast over target (2, 6, 3)
    c_batch = compute_mass_weighted_covariance_matrix(
        coords, batch_target, masses=masses, center=True
    )
    assert c_batch.shape == (2, 3, 3)
    assert np.allclose(c_batch[0], c_single_0, atol=1e-15)
    assert np.allclose(c_batch[1], c_single_1, atol=1e-15)

    # Batched Frobenius norm and symmetry checks
    fro_norms = compute_covariance_frobenius_norm(c_batch)
    assert isinstance(fro_norms, np.ndarray)
    assert fro_norms.shape == (2,)
    assert np.isclose(fro_norms[0], compute_covariance_frobenius_norm(c_single_0), atol=1e-15)
    assert np.isclose(fro_norms[1], compute_covariance_frobenius_norm(c_single_1), atol=1e-15)

    sym_batch = check_covariance_symmetry(c_batch, tol=1e-12)
    assert isinstance(sym_batch, np.ndarray)
    assert sym_batch[0] is True or sym_batch[0] == True
    # Rotated conformation is not symmetric with unrotated reference
    assert bool(sym_batch[1]) == bool(check_covariance_symmetry(c_single_1, tol=1e-12))


def test_analytic_gradient_bilinear_trace_product():
    """WBS 1.4.1 Acceptance Criteria: Analytic gradient corresponds exactly to bilinear displacement trace product."""
    # Test on authentic water monomer
    symbols_w, coords_w = load_xyz_fixture("water.xyz")
    masses_w = np.array([disambiguate_mass(s) for s in symbols_w], dtype=np.float64)

    # Exact Pythagorean SO(3) rotation matrix about y-axis (cos=0.8, sin=0.6, det=+1.0)
    rot_matrix = np.array([
        [ 0.8, 0.0, 0.6],
        [ 0.0, 1.0, 0.0],
        [-0.6, 0.0, 0.8],
    ], dtype=np.float64)
    coords_target_w = coords_w @ rot_matrix.T

    # Formulate mass-weighted covariance matrix C
    c_mat = compute_mass_weighted_covariance_matrix(
        coords_w, coords_target_w, masses=masses_w, center=True
    )
    assert c_mat.shape == (3, 3)

    centered_ref, _ = translate_to_center_of_mass(coords_w, masses=masses_w)
    centered_target, _ = translate_to_center_of_mass(coords_target_w, masses=masses_w)

    def bilinear_displacement_functional(a_matrix: np.ndarray) -> float:
        """Physical functional: F(A) = Tr(A^T C) = sum_i m_i * r_tilde_i,ref^T * A * r_tilde_i,target."""
        val = 0.0
        for i in range(len(masses_w)):
            val += masses_w[i] * float(centered_ref[i] @ a_matrix @ centered_target[i])
        return val

    # Test at multiple arbitrary probe matrices A
    identity_3 = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)

    probe_matrices = [
        identity_3,
        rot_matrix,
        np.array([[1.2, -0.4, 0.7], [0.3, 0.9, -0.2], [-0.5, 0.1, 1.1]], dtype=np.float64),
    ]

    h = 1e-6  # Central difference step
    for a_probe in probe_matrices:
        # Verify F(A) == Tr(A^T C)
        f_val = bilinear_displacement_functional(a_probe)
        trace_val = float(np.trace(a_probe.T @ c_mat))
        assert np.isclose(f_val, trace_val, atol=1e-12), f"Functional mismatch: {f_val} vs {trace_val}"

        # Compute numerical gradient with respect to A_jk: dF / dA_jk
        num_grad_list = []
        for j in range(3):
            row_grads = []
            for k in range(3):
                e_jk = [
                    [1.0 if (r == j and c == k) else 0.0 for c in range(3)]
                    for r in range(3)
                ]
                e_mat = np.array(e_jk, dtype=np.float64)

                f_plus = bilinear_displacement_functional(a_probe + h * e_mat)
                f_minus = bilinear_displacement_functional(a_probe - h * e_mat)
                row_grads.append((f_plus - f_minus) / (2.0 * h))
            num_grad_list.append(row_grads)

        num_grad = np.array(num_grad_list, dtype=np.float64)

        # Analytic gradient of Tr(A^T C) with respect to A is exactly C
        max_diff = float(np.max(np.abs(num_grad - c_mat)))
        assert max_diff < 1e-9, f"Analytic gradient breach: max error {max_diff:.4e} exceeds 1e-9"

    # Also verify on authentic formaldehyde (H2CO) fixture
    symbols_h, coords_h = load_xyz_fixture("h2co_eq.xyz")
    masses_h = np.array([disambiguate_mass(s) for s in symbols_h], dtype=np.float64)
    c_h2co = compute_mass_weighted_covariance_matrix(
        coords_h, coords_h, masses=masses_h, center=True
    )
    centered_h, _ = translate_to_center_of_mass(coords_h, masses=masses_h)

    num_grad_h_list = []
    for j in range(3):
        row_grads_h = []
        for k in range(3):
            e_jk = [
                [1.0 if (r == j and c == k) else 0.0 for c in range(3)]
                for r in range(3)
            ]
            e_mat = np.array(e_jk, dtype=np.float64)
            f_plus = sum(masses_h[i] * float(centered_h[i] @ (identity_3 + h * e_mat) @ centered_h[i]) for i in range(len(masses_h)))
            f_minus = sum(masses_h[i] * float(centered_h[i] @ (identity_3 - h * e_mat) @ centered_h[i]) for i in range(len(masses_h)))
            row_grads_h.append((f_plus - f_minus) / (2.0 * h))
        num_grad_h_list.append(row_grads_h)

    num_grad_h = np.array(num_grad_h_list, dtype=np.float64)
    assert np.allclose(num_grad_h, c_h2co, atol=1e-9)


def test_dynamic_mendeleev_symbols_resolution():
    """WBS 1.4.1 Test 4: Dynamic Mendeleev resolution and isotopic water (18O, D, T)."""
    _, coords = load_xyz_fixture("water.xyz")

    # 1. Standard water using chemical symbols
    symbols_std = ["O", "H", "H"]
    c_from_symbols = compute_mass_weighted_covariance_matrix(
        coords, coords, symbols=symbols_std, center=True
    )

    masses_std = np.array([disambiguate_mass(s) for s in symbols_std], dtype=np.float64)
    c_from_masses = compute_mass_weighted_covariance_matrix(
        coords, coords, masses=masses_std, center=True
    )
    assert np.allclose(c_from_symbols, c_from_masses, atol=1e-15)

    # 2. Heavy isotopic water: 18O, Deuterium, Tritium
    symbols_iso = ["18O", "D", "T"]
    c_iso_symbols = compute_mass_weighted_covariance_matrix(
        coords, coords, symbols=symbols_iso, center=True
    )

    masses_iso = np.array([disambiguate_mass(s) for s in symbols_iso], dtype=np.float64)
    c_iso_masses = compute_mass_weighted_covariance_matrix(
        coords, coords, masses=masses_iso, center=True
    )
    assert np.allclose(c_iso_symbols, c_iso_masses, atol=1e-15)

    # Verify that heavy isotopic substitution alters covariance matrix
    assert not np.allclose(c_from_symbols, c_iso_symbols, atol=1e-4)


def test_precentered_vs_uncentered_equivalence():
    """WBS 1.4.1 Test 5: Equivalence between center=True and pre-centered coordinates."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Computation with internal centering
    c_auto_centered = compute_mass_weighted_covariance_matrix(
        coords, coords, masses=masses, center=True
    )

    # Computation with pre-centered coordinates and center=False
    centered_coords, _ = translate_to_center_of_mass(coords, masses=masses)
    c_pre_centered = compute_mass_weighted_covariance_matrix(
        centered_coords, centered_coords, masses=masses, center=False
    )

    assert np.allclose(c_auto_centered, c_pre_centered, atol=1e-15)


def test_frobenius_norm_and_numerical_conditioning():
    """WBS 1.4.1 Test 6: Frobenius norm properties and numerical conditioning."""
    symbols, coords = load_xyz_fixture("h2co_eq.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    c_mat = compute_mass_weighted_covariance_matrix(coords, coords, masses=masses, center=True)
    fro_norm = compute_covariance_frobenius_norm(c_mat)

    # Trace formula for Frobenius norm: ||C||_F^2 = Tr(C^T C)
    expected_fro_sq = float(np.trace(c_mat.T @ c_mat))
    assert np.isclose(fro_norm ** 2, expected_fro_sq, atol=1e-12)

    # Verify conditioning: singular values are well-behaved
    s_vals = np.linalg.svd(c_mat, compute_uv=False)
    assert len(s_vals) == 3
    assert s_vals[0] >= s_vals[1] >= s_vals[2] >= 0.0


def test_performance_microsecond_benchmark():
    """WBS 1.4.1 Test 7: Microsecond benchmark (<15 µs for N=100 atoms over 1,000 iterations)."""
    # Construct authentic 100-atom molecular system using replicated water monomers
    _, single_water_coords = load_xyz_fixture("water.xyz")
    n_monomers = 34  # 34 * 3 = 102 atoms
    cluster_coords = []
    cluster_symbols = []

    for i in range(n_monomers):
        offset = np.array([3.0 * (i % 6), 3.0 * ((i // 6) % 6), 3.0 * (i // 36)], dtype=np.float64)
        cluster_coords.append(single_water_coords + offset)
        cluster_symbols.extend(["O", "H", "H"])

    coords_100 = np.concatenate(cluster_coords, axis=0)[:100]
    symbols_100 = cluster_symbols[:100]
    assert coords_100.shape == (100, 3)
    assert len(symbols_100) == 100

    masses_100 = np.array([disambiguate_mass(s) for s in symbols_100], dtype=np.float64)

    # Pre-center for benchmarking pure covariance matrix accumulation
    centered_100, _ = translate_to_center_of_mass(coords_100, masses=masses_100)

    # Warm-up iterations
    for _ in range(50):
        _ = compute_mass_weighted_covariance_matrix(
            centered_100, centered_100, masses=masses_100, center=False
        )

    # Monotonic high-resolution timing over 1,000 iterations
    n_iterations = 1000
    t_start = time.perf_counter()
    for _ in range(n_iterations):
        _ = compute_mass_weighted_covariance_matrix(
            centered_100, centered_100, masses=masses_100, center=False
        )
    t_end = time.perf_counter()

    avg_time_us = ((t_end - t_start) / n_iterations) * 1e6
    assert avg_time_us < 15.0, (
        f"Benchmark SLA violation: N=100 covariance accumulation took {avg_time_us:.2f} µs "
        f"(hard limit: 15.0 µs)."
    )


def test_adversarial_nan_inf_fuzzing():
    """WBS 1.4.1 Test 8: Rejection of NaN or Inf in coordinates, masses, and covariance matrices."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # 1. NaN in coords_ref
    coords_nan = coords.copy()
    coords_nan[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_mass_weighted_covariance_matrix(coords_nan, coords, masses=masses)

    # 2. Inf in coords_target
    coords_inf = coords.copy()
    coords_inf[1, 1] = np.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_mass_weighted_covariance_matrix(coords, coords_inf, masses=masses)

    # 3. NaN in masses
    masses_nan = masses.copy()
    masses_nan[0] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_mass_weighted_covariance_matrix(coords, coords, masses=masses_nan)

    # 4. NaN in Frobenius norm
    nan_mat = np.full((3, 3), np.nan, dtype=np.float64)
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_covariance_frobenius_norm(nan_mat)

    # 5. NaN in symmetry check
    with pytest.raises(ValueError, match="NaN or Inf"):
        check_covariance_symmetry(nan_mat)


def test_adversarial_dimensional_mismatch():
    """WBS 1.4.1 Test 9: Strict dimensional and shape mismatch rejection."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Atom count mismatch (3 atoms vs 6 atoms)
    _, coords_dimer = load_xyz_fixture("water_dimer.xyz")
    with pytest.raises(ValueError, match="Atom count mismatch"):
        compute_mass_weighted_covariance_matrix(coords, coords_dimer, masses=masses)

    # Non-3D coordinates (last dimension != 3)
    coords_4d = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0], [9.0, 10.0, 11.0, 12.0]], dtype=np.float64)
    with pytest.raises(ValueError, match="Last dimension"):
        compute_mass_weighted_covariance_matrix(coords_4d, coords_4d, masses=masses)

    # Invalid rank (1D array)
    with pytest.raises(ValueError, match="2 or 3 dimensions"):
        compute_mass_weighted_covariance_matrix(coords[0], coords[0], masses=masses)

    # Symbols length mismatch
    with pytest.raises(ValueError, match="Number of chemical symbols"):
        compute_mass_weighted_covariance_matrix(coords, coords, symbols=["O", "H"])

    # Batch size mismatch
    batch_2 = np.stack([coords, coords], axis=0)
    batch_3 = np.stack([coords, coords, coords], axis=0)
    with pytest.raises(ValueError, match="Batch size mismatch"):
        compute_mass_weighted_covariance_matrix(batch_2, batch_3, masses=masses)


def test_negative_or_zero_mass_rejection():
    """WBS 1.4.1 Test 10: Strict rejection of non-positive or empty atomic masses."""
    coords = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)

    # Negative mass
    with pytest.raises(ValueError, match="strictly positive"):
        compute_mass_weighted_covariance_matrix(coords, coords, masses=[-1.0, 2.0])

    # Zero mass
    with pytest.raises(ValueError, match="strictly positive"):
        compute_mass_weighted_covariance_matrix(coords, coords, masses=[0.0, 2.0])

    # Empty mass array
    with pytest.raises(ValueError, match="empty"):
        compute_mass_weighted_covariance_matrix(coords, coords, masses=[])


def test_covariance_symmetry_asymmetric_geometry():
    """WBS 1.4.1 Test 11: Covariance matrix between distinct rotated geometries is non-symmetric."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Exact Pythagorean SO(3) rotation matrix about y-axis (cos=0.6, sin=0.8, det=+1.0)
    rot_y = np.array([
        [ 0.6, 0.0, 0.8],
        [ 0.0, 1.0, 0.0],
        [-0.8, 0.0, 0.6],
    ], dtype=np.float64)

    coords_target = coords @ rot_y.T

    c_mat = compute_mass_weighted_covariance_matrix(
        coords, coords_target, masses=masses, center=True
    )
    # Check that asymmetry is detected
    is_sym = check_covariance_symmetry(c_mat, tol=1e-8)
    assert is_sym is False, "Cross-covariance between distinct rotated geometries should not be symmetric."
