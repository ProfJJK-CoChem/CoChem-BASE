"""
Zero-Mock Test Suite for CoChem-TOPOS Stage 2.2 Topographic Escape Subsystem.
Validates:
1. Dynamic Mendeleev library atomic mass and Pyykkö covalent radius retrieval.
2. Single inverse-mass-root scaling in Wigner-Guided Escape (resolution of double inverse mass scaling).
3. RDKit 3D stereocenter perception and Pyykkö-radius tetrahedral volume fallback in ParityLock.
4. Selective and complete SHAKE constraints for rigid water solvent molecules (O-H1, O-H2, H1-H2) without locking solute hydroxyls.
5. End-to-end Escape Orchestration and FAIR provenance records.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from ase.calculators.lj import LennardJones
from mendeleev import element

from cochem_topos.cochem_topos_escape import (
    EscapeConfig,
    EscapeMechanism,
    EscapeResult,
    EscapeRoom,
    EscapeStatus,
    GoodTuringEstimator,
    IPCTelemetryBroadcaster,
    NormalModeAnalysisResult,
    ParityLock,
    ProgressiveLangevinEscape,
    ToposEscapeOrchestrator,
    WignerGuidedEscape,
    WignerModeInfo,
    calculate_rmsd,
    canonical_geometry_hash,
    create_fair_provenance_record,
    get_atomic_masses,
    get_mendeleev_mass,
    get_pyykko_covalent_radius,
)


# ============================================================================
# 1. Dynamic Mendeleev Integration Tests
# ============================================================================

def test_dynamic_mendeleev_atomic_masses() -> None:
    """Verify atomic masses are dynamically retrieved from Mendeleev for various elements."""
    for sym in ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"]:
        expected_mass = float(element(sym).mass)
        retrieved_mass = get_mendeleev_mass(sym)
        assert abs(retrieved_mass - expected_mass) < 1e-6

    # Test Atoms object
    atoms = Atoms("CH3Br", positions=[
        [0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [-1.0, 0.0, 0.0],
    ])
    masses = get_atomic_masses(atoms)
    assert len(masses) == 5
    assert abs(masses[0] - float(element("C").mass)) < 1e-6
    assert abs(masses[4] - float(element("Br").mass)) < 1e-6


def test_dynamic_mendeleev_pyykko_radii() -> None:
    """Verify covalent radii are dynamically retrieved from Mendeleev."""
    for sym in ["H", "C", "N", "O", "P", "S", "Br", "I"]:
        r = get_pyykko_covalent_radius(sym)
        assert 0.2 < r < 2.0
    # Heavy atoms like Br and I should have larger covalent radii than C
    assert get_pyykko_covalent_radius("Br") > get_pyykko_covalent_radius("C")
    assert get_pyykko_covalent_radius("I") > get_pyykko_covalent_radius("Br")


# ============================================================================
# 2. Wigner Scaling & Dimensional Verification Tests
# ============================================================================

def test_wigner_single_inverse_mass_scaling() -> None:
    """
    Verify Wigner displacement scales with exactly 1 / sqrt(m) rather than 1 / m.
    Checks that mode.eigenvector is orthonormal mass-weighted vector l_k,
    and Cartesian delta_x = l_k / sqrt(m) * q_sample.
    """
    # Create simple linear molecule with widely different masses: H-C#N (H=1, C=12, N=14)
    atoms = Atoms("HCN", positions=[
        [0.0, 0.0, -1.06],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.15],
    ])
    atoms.calc = LennardJones()

    wigner = WignerGuidedEscape(EscapeConfig(soft_mode_cutoff_cm1=2000.0, seed=42))
    mode_analysis = wigner.analyze_normal_modes(atoms)

    assert len(mode_analysis.modes) == 9  # 3 * 3 = 9 degrees of freedom
    assert len(mode_analysis.frequencies_cm1) == 9

    # Check mode eigenvector properties
    for mode in mode_analysis.modes:
        vec = np.array(mode.eigenvector)
        assert vec.shape == (3, 3)
        # Mass-weighted eigenvector l_k has unit norm: sum(l_k^2) = 1
        norm_sq = np.sum(vec ** 2)
        assert abs(norm_sq - 1.0) < 1e-4

    # Sample a displacement along a mode
    mode = mode_analysis.modes[0]
    rng = np.random.default_rng(42)
    perturbed = wigner.sample_wigner_displacement(atoms, mode=mode, scale=1.0, rng=rng)

    assert perturbed is not None
    delta_x = perturbed.get_positions() - atoms.get_positions()
    masses = get_atomic_masses(atoms)

    # Verify that the ratio of displacements between atom 0 (H) and atom 1 (C)
    # in Cartesian coordinates is proportional to (l_0 / sqrt(m_0)) / (l_1 / sqrt(m_1))
    vec = np.array(mode.eigenvector)
    for coord in range(3):
        if abs(vec[0, coord]) > 1e-4 and abs(vec[1, coord]) > 1e-4:
            expected_ratio = (vec[0, coord] / np.sqrt(masses[0])) / (vec[1, coord] / np.sqrt(masses[1]))
            actual_ratio = delta_x[0, coord] / delta_x[1, coord]
            assert abs(actual_ratio - expected_ratio) < 1e-5


# ============================================================================
# 3. Chiral ParityLock & Invariance Tests
# ============================================================================

def test_parity_lock_chiral_inversion_detection() -> None:
    """
    Test chiral stereocenter detection with heavy atoms (CHBrClF) and inversion trap.
    """
    # Tetrahedral chiral center: C at origin, H, F, Cl, Br substituents
    # (R)-bromochlorofluoromethane approximate geometry
    pos_r = np.array([
        [0.0, 0.0, 0.0],       # C
        [0.0, 0.0, 1.09],      # H
        [1.35, 0.0, -0.4],     # F
        [-0.7, 1.5, -0.4],     # Cl
        [-0.7, -1.6, -0.4],    # Br
    ])
    atoms_r = Atoms("CHFCBr", positions=pos_r)

    # Mirror image (inversion through y -> -y)
    pos_s = pos_r.copy()
    pos_s[:, 1] = -pos_s[:, 1]
    atoms_s = Atoms("CHFCBr", positions=pos_s)

    # Verify tetrahedral volume calculation detects heavy atoms (Br, Cl, F)
    vols_r = ParityLock._calculate_tetrahedral_volumes(atoms_r)
    vols_s = ParityLock._calculate_tetrahedral_volumes(atoms_s)

    assert 0 in vols_r, "ParityLock failed to detect 4-coordinate tetrahedral C center with heavy Br/Cl/F substituents"
    assert 0 in vols_s
    assert vols_r[0] != vols_s[0], "Inverted enantiomer should have opposite volume sign"

    # Verify invariance check returns False for inverted stereocenter
    assert ParityLock.verify_invariance(atoms_r, atoms_s) is False

    # Small thermal perturbation should preserve stereocenter
    pos_perturbed = pos_r + np.random.default_rng(42).normal(scale=0.02, size=pos_r.shape)
    atoms_perturbed = Atoms("CHFCBr", positions=pos_perturbed)
    assert ParityLock.verify_invariance(atoms_r, atoms_perturbed) is True


# ============================================================================
# 4. Selective Rigid Solvent SHAKE Constraints Tests
# ============================================================================

def test_selective_shake_constraints() -> None:
    """
    Verify SHAKE constraints:
    1. Apply complete triads (O-H1, O-H2, H1-H2) to isolated water solvent molecules.
    2. Do NOT constrain solute hydroxyl groups (e.g. methanol CH3OH).
    """
    engine = ProgressiveLangevinEscape(EscapeConfig())

    # Case A: Pure Water Dimer (2 water molecules)
    # Water 1: O(0), H(1), H(2); Water 2: O(3), H(4), H(5)
    water_dimer = Atoms(symbols=["O", "H", "H", "O", "H", "H"], positions=[
        # Water 1
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],
        # Water 2
        [2.9, 0.0, 0.0],
        [3.657, 0.586, 0.0],
        [2.143, 0.586, 0.0],
    ])
    constraints = engine._apply_shake_constraints(water_dimer)
    assert len(constraints) == 1
    # Each water has 3 constraints: O-H1, O-H2, H1-H2 -> total 6 pairs for 2 waters
    pairs = constraints[0].pairs
    assert len(pairs) == 6

    # Verify that water 1 has triad (0, 1), (0, 2), (1, 2)
    pair_list = [tuple(sorted(p)) for p in pairs]
    assert (0, 1) in pair_list
    assert (0, 2) in pair_list
    assert (1, 2) in pair_list

    # Case B: Solute with hydroxyl (Methanol CH3OH) - MUST NOT BE CONSTRAINED
    # C(0), O(1), H(2-methyl), H(3-methyl), H(4-methyl), H(5-hydroxyl)
    methanol = Atoms(symbols=["C", "O", "H", "H", "H", "H"], positions=[
        [0.0, 0.0, 0.0],      # C
        [1.42, 0.0, 0.0],     # O
        [-0.36, 1.03, 0.0],   # H
        [-0.36, -0.51, 0.89], # H
        [-0.36, -0.51, -0.89],# H
        [1.78, 0.94, 0.0],    # H (hydroxyl)
    ])
    methanol_constraints = engine._apply_shake_constraints(methanol)
    assert len(methanol_constraints) == 0, "Solute methanol hydroxyl was incorrectly constrained by SHAKE"

    # Case C: Mixed Solute (Methanol) + Solvent (Water)
    mixed = Atoms(symbols=["C", "O", "H", "H", "H", "H", "O", "H", "H"], positions=[
        # Methanol
        [0.0, 0.0, 0.0],      # C(0)
        [1.42, 0.0, 0.0],     # O(1)
        [-0.36, 1.03, 0.0],   # H(2)
        [-0.36, -0.51, 0.89], # H(3)
        [-0.36, -0.51, -0.89],# H(4)
        [1.78, 0.94, 0.0],    # H(5)
        # Water
        [4.0, 0.0, 0.0],      # O(6)
        [4.757, 0.586, 0.0],  # H(7)
        [3.243, 0.586, 0.0],  # H(8)
    ])
    mixed_constraints = engine._apply_shake_constraints(mixed)
    assert len(mixed_constraints) == 1
    mixed_pairs = [tuple(sorted(p)) for p in mixed_constraints[0].pairs]
    # Exactly 3 constraints for the water solvent (6-7, 6-8, 7-8), 0 for methanol
    assert len(mixed_pairs) == 3
    assert (6, 7) in mixed_pairs
    assert (6, 8) in mixed_pairs
    assert (7, 8) in mixed_pairs


# ============================================================================
# 5. Topographic Escape Orchestrator & Telemetry Tests
# ============================================================================

def test_escape_orchestrator_end_to_end() -> None:
    """
    Test full ToposEscapeOrchestrator pipeline on water dimer.
    """
    water_dimer = Atoms("O2H4", positions=[
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],
        [2.9, 0.0, 0.0],
        [3.657, 0.586, 0.0],
        [2.143, 0.586, 0.0],
    ])
    water_dimer.calc = LennardJones()

    config = EscapeConfig(
        soft_mode_cutoff_cm1=500.0,
        wigner_samples_per_mode=2,
        thermal_schedule=[300.0],
        langevin_steps_per_stage=10,
        quench_max_steps=50,
        save_to_hdf5=False,
        ipc_streaming_enabled=False,
        seed=42,
    )
    orchestrator = ToposEscapeOrchestrator(config=config)
    result = orchestrator.run_escape_search(water_dimer, escape_id="test_run_01")

    assert isinstance(result, EscapeResult)
    assert result.status in [EscapeStatus.BREACH_SUCCESS, EscapeStatus.RELAXED_TO_SAME_BASIN]
    assert len(result.quenched_coords) == len(water_dimer)


def test_fair_provenance_record_generation() -> None:
    """Verify FAIR-compliant provenance record creation with [M], [D], [E] tags."""
    prov = create_fair_provenance_record(
        parent_hash="abc123parent",
        conformer_hash="def456conformer",
        mechanism=EscapeMechanism.WIGNER,
        initial_energy_hartree=-76.4,
        quenched_energy_hartree=-76.45,
        rmsd=0.15,
        converged=True,
        engine_tier="TorchMLFF",
    )
    assert "[M:WIGNER]" in prov.method_tag
    assert "[D:PARENT_SHA256:abc123parent]" in prov.data_tag
    assert "[E:ENGINE:TorchMLFF]" in prov.energy_tag
    assert "[E:CONVERGED:True]" in prov.energy_tag
    assert len(prov.tags) >= 5


def test_good_turing_completeness_estimator() -> None:
    """Verify Good-Turing Completeness Estimator dynamics."""
    gt = GoodTuringEstimator(target_coverage=0.95, n_rotatable_bonds=2)
    # Minimum sample size for 2 rotatable bonds: 15 * 2^2 = 60
    assert gt.get_dynamic_min_sample_size() == 60

    # Feed fewer than N_min samples
    for i in range(30):
        gt.update([f"basin_{i}"])
    assert gt.calculate_coverage() == 0.0

    # Feed enough samples with revisits
    for _ in range(10):
        gt.update([f"basin_{i}" for i in range(10)])
    # Now N = 30 + 100 = 130 > 60
    cov = gt.calculate_coverage()
    assert cov > 0.0
