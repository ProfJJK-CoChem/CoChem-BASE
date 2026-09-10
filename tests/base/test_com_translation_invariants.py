"""
Unit & Adversarial Test Suite: Mass-Weighted Center-of-Mass Vector Accumulator.
WBS 1.3.1: Mass-Weighted Center-of-Mass Vector Accumulator (Subsystem VR01-SS2)

Governing Specifications:
- Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5)
- Invariant VR-01-T01: delta_COM = ||sum(m_i * r_tilde_i)||_2 < 1e-12 u*Angstrom
- Dynamic Mendeleev Mandate: Zero static mass dictionaries; dynamic nuclide resolution via disambiguate_mass()
- Authentic Physical Geometries: Zero mocks, zero stubs, genuine ab-initio water geometries
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
    COMResidualError,
    NumericalInvariantBreach,
    compute_center_of_mass,
    translate_to_center_of_mass,
    verify_com_residual,
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
# Test Cases (WBS 1.3.1.4 & Section 6.2)
# ============================================================================

def test_water_monomer_com():
    """WBS 1.3.1.4.1 Test 1: Authentic water monomer COM accuracy & residual gate."""
    symbols, coords = load_xyz_fixture("water.xyz")
    assert len(symbols) == 3
    assert coords.shape == (3, 3)

    # Resolve masses dynamically via Mendeleev
    m_o = disambiguate_mass("O")
    m_h = disambiguate_mass("H")
    masses = np.array([m_o, m_h, m_h], dtype=np.float64)

    # Analytic COM calculation:
    # O is at [0, 0, 0], H1 at [0.758602, 0, 0.504284], H2 at [0.758602, 0, -0.504284]
    m_tot = m_o + 2.0 * m_h
    analytic_x = (2.0 * m_h * coords[1, 0]) / m_tot
    analytic_y = 0.0
    analytic_z = 0.0
    analytic_com = np.array([analytic_x, analytic_y, analytic_z], dtype=np.float64)

    # 1. Compute COM
    r_com = compute_center_of_mass(coords, masses=masses)
    assert np.allclose(r_com, analytic_com, atol=1e-14), f"COM mismatch: {r_com} vs {analytic_com}"

    # 2. Translate coordinates to COM
    centered, r_com_returned = translate_to_center_of_mass(
        coords, masses=masses, enforce_residual_gate=True, tol=1e-12
    )
    assert np.allclose(r_com, r_com_returned, atol=1e-15)

    # 3. Invariant VR-01-T01: residual norm < 1e-12 u*Angstrom
    residual = verify_com_residual(centered, masses=masses, tol=1e-12)
    assert residual < 1e-12, f"Residual {residual:.4e} exceeds 1e-12 u*Angstrom."


def test_water_dimer_batch_com():
    """WBS 1.3.1.4.1 Test 2: Authentic (H2O)2 coordinates with batch tensor broadcasting."""
    symbols, coords = load_xyz_fixture("water_dimer.xyz")
    assert len(symbols) == 6
    assert coords.shape == (6, 3)

    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Unbatched execution
    r_com_single = compute_center_of_mass(coords, masses=masses)
    centered_single, _ = translate_to_center_of_mass(coords, masses=masses)

    # Create batch of shape (2, 6, 3)
    # Structure 0: original, Structure 1: shifted by [10.0, -5.0, 2.0]
    shift = np.array([10.0, -5.0, 2.0], dtype=np.float64)
    batch_coords = np.stack([coords, coords + shift[None, :]], axis=0)
    assert batch_coords.shape == (2, 6, 3)

    # Batched execution with 1D masses (N,)
    r_com_batch = compute_center_of_mass(batch_coords, masses=masses)
    assert r_com_batch.shape == (2, 3)
    assert np.allclose(r_com_batch[0], r_com_single, atol=1e-14)
    assert np.allclose(r_com_batch[1], r_com_single + shift, atol=1e-14)

    centered_batch, r_com_b = translate_to_center_of_mass(batch_coords, masses=masses)
    assert centered_batch.shape == (2, 6, 3)
    assert np.allclose(centered_batch[0], centered_single, atol=1e-14)
    assert np.allclose(centered_batch[1], centered_single, atol=1e-14)

    # Batched execution with 2D masses (B, N)
    batch_masses = np.stack([masses, masses], axis=0)
    residual_b = verify_com_residual(centered_batch, masses=batch_masses, tol=1e-12)
    assert residual_b < 1e-12


def test_dynamic_mendeleev_symbols_resolution():
    """WBS 1.3.1.4.1 Test 3: Dynamic Mendeleev resolution and isotopic water (18O, D, T)."""
    _, coords = load_xyz_fixture("water.xyz")

    # 1. Standard water using symbols
    symbols_std = ["O", "H", "H"]
    r_com_std = compute_center_of_mass(coords, symbols=symbols_std)

    m_o_std = disambiguate_mass("O")
    m_h_std = disambiguate_mass("H")
    masses_std = np.array([m_o_std, m_h_std, m_h_std], dtype=np.float64)
    expected_std = (masses_std @ coords) / np.sum(masses_std)
    assert np.allclose(r_com_std, expected_std, atol=1e-15)

    # 2. Fully isotopic water: 18O, Deuterium, Tritium
    symbols_iso = ["18O", "D", "T"]
    r_com_iso = compute_center_of_mass(coords, symbols=symbols_iso)

    m_18o = disambiguate_mass("18O")
    m_d = disambiguate_mass("D")
    m_t = disambiguate_mass("T")
    masses_iso = np.array([m_18o, m_d, m_t], dtype=np.float64)
    expected_iso = (masses_iso @ coords) / np.sum(masses_iso)
    assert np.allclose(r_com_iso, expected_iso, atol=1e-15)

    # Dynamic translation with symbols
    centered_iso, _ = translate_to_center_of_mass(coords, symbols=symbols_iso)
    res_iso = verify_com_residual(centered_iso, masses=masses_iso, tol=1e-12)
    assert res_iso < 1e-12


def test_extreme_coordinate_displacement():
    """WBS 1.3.1.4.2 Test 4: Extreme coordinate shift and dual-pass compensated summation."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    # Displace geometry to 1,000,000 Angstroms
    r0 = np.array([1e6, 1e6, 1e6], dtype=np.float64)
    extreme_coords = coords + r0[None, :]

    centered, r_com = translate_to_center_of_mass(
        extreme_coords, masses=masses, enforce_residual_gate=True, tol=1e-12
    )

    # Check centered coordinates match standard centered coordinates within 1e-9 Angstroms
    orig_centered, orig_r_com = translate_to_center_of_mass(coords, masses=masses)
    assert np.allclose(centered, orig_centered, atol=1e-9)

    # Invariant VR-01-T01: residual must be < 1e-12 u*Angstrom
    residual = verify_com_residual(centered, masses=masses, tol=1e-12)
    assert residual < 1e-12, f"Catastrophic cancellation breach: residual {residual:.3e} >= 1e-12"


def test_residual_gate_violation_trigger():
    """WBS 1.3.1.4 Test 5: Artificial non-centered displacement triggers COMResidualError."""
    symbols, coords = load_xyz_fixture("water.xyz")
    masses = np.array([disambiguate_mass(s) for s in symbols], dtype=np.float64)

    centered, _ = translate_to_center_of_mass(coords, masses=masses)

    # Manually displace centered coordinates by 0.01 Angstrom
    artificially_shifted = centered + np.array([0.01, 0.0, 0.0], dtype=np.float64)

    with pytest.raises(COMResidualError) as exc_info:
        verify_com_residual(artificially_shifted, masses=masses, tol=1e-12)
    assert "VR-01-T01 breach" in str(exc_info.value) or "exceeds" in str(exc_info.value)

    # Verify that translate_to_center_of_mass with strict impossible tolerance also raises
    with pytest.raises(COMResidualError):
        translate_to_center_of_mass(coords, masses=masses, enforce_residual_gate=True, tol=1e-25)


def test_negative_or_zero_mass_rejection():
    """WBS 1.3.1.1.3 Test 6: Strict rejection of zero, negative, or empty masses."""
    coords = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)

    # Negative mass
    with pytest.raises(ValueError, match="strictly positive"):
        compute_center_of_mass(coords, masses=[-1.0, 2.0])

    # Zero mass
    with pytest.raises(ValueError, match="strictly positive"):
        compute_center_of_mass(coords, masses=[0.0, 2.0])

    # Empty mass array
    with pytest.raises(ValueError, match="empty"):
        compute_center_of_mass(coords, masses=[])


def test_performance_microsecond_benchmark():
    """WBS 1.3.1.4.3 Test 7: Microsecond benchmark (<15 µs for N=100 atoms over 1,000 iterations)."""
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

    # Resolve masses dynamically
    masses_100 = np.array([disambiguate_mass(s) for s in symbols_100], dtype=np.float64)

    # Warmup
    for _ in range(20):
        translate_to_center_of_mass(coords_100, masses=masses_100, enforce_residual_gate=True)

    # Benchmark 1,000 executions
    n_iterations = 1000
    t0 = time.perf_counter()
    for _ in range(n_iterations):
        translate_to_center_of_mass(coords_100, masses=masses_100, enforce_residual_gate=True)
    t1 = time.perf_counter()

    avg_time_us = ((t1 - t0) / n_iterations) * 1e6
    print(f"\n[BENCHMARK] N=100 COM translation average runtime: {avg_time_us:.2f} µs (threshold: < 15.0 µs)")
    assert avg_time_us < 15.0, f"Performance breach: average time {avg_time_us:.2f} µs exceeds 15.0 µs limit."


# ============================================================================
# Adversarial Red-Team & Fault Injection Tests (WBS 1.3.1.5.2)
# ============================================================================

def test_adversarial_nan_inf_fuzzing():
    """Adversarial fault injection: NaN / Inf coordinates and masses must be rejected fail-closed."""
    coords = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
    masses = np.array([12.0, 1.0], dtype=np.float64)

    # NaN in coords
    nan_coords = coords.copy()
    nan_coords[0, 1] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_center_of_mass(nan_coords, masses=masses)

    # Inf in coords
    inf_coords = coords.copy()
    inf_coords[1, 2] = np.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_center_of_mass(inf_coords, masses=masses)

    # NaN in masses
    nan_masses = masses.copy()
    nan_masses[0] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        compute_center_of_mass(coords, masses=nan_masses)


def test_adversarial_extreme_mass_disparity():
    """Adversarial stress test: Extreme mass disparity (e.g. Uranium 238 vs Hydrogen 1)."""
    m_u = disambiguate_mass("238U")
    m_h = disambiguate_mass("H")
    masses = np.array([m_u, m_h], dtype=np.float64)
    coords = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]], dtype=np.float64)

    centered, r_com = translate_to_center_of_mass(coords, masses=masses, enforce_residual_gate=True)
    residual = verify_com_residual(centered, masses=masses, tol=1e-12)
    assert residual < 1e-12
    # COM must be heavily biased toward Uranium (< 0.01 Angstroms from U)
    assert abs(r_com[0]) < 0.02


def test_adversarial_dimensional_mismatch():
    """Adversarial boundary check: Incompatible shapes and dimensions must raise ValueError."""
    _, coords = load_xyz_fixture("water.xyz")
    # 4D coordinates
    coords_4d = np.expand_dims(np.expand_dims(coords, axis=0), axis=0)
    with pytest.raises(ValueError, match="dimensions"):
        compute_center_of_mass(coords_4d, masses=[1.0, 2.0, 3.0])

    # 4-coordinate non-Cartesian vectors
    coords_4coord = np.hstack([coords[:2, :], coords[:2, :1]])
    with pytest.raises(ValueError, match="Last dimension"):
        compute_center_of_mass(coords_4coord, masses=[1.0, 2.0])

    # Mismatched symbol length
    with pytest.raises(ValueError, match="Number of chemical symbols"):
        compute_center_of_mass(coords, symbols=["O", "H"])


def test_exception_inheritance():
    """Verify clean exception inheritance hierarchy from CoChem root exceptions."""
    assert issubclass(NumericalInvariantBreach, CoChemError)
    assert issubclass(COMResidualError, NumericalInvariantBreach)
