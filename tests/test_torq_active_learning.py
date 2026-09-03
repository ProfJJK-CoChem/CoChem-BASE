"""Authentic physical verification test suite for Active Learning Orchestrator (REQ-TORQ-INF-101).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, Ethanol (N=9), and Alanine Dipeptide (N=22).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np
import pytest

from Libraries.cochem_torq_active_learning import (
    ActiveLearningOrchestrator,
    ActiveLearningState,
    CandidateGeometry,
    center_geometry_mass_weighted,
    check_stage_b_rotational_redundancy,
    compute_max_force_epistemic_std,
    compute_qbc_energy_variance,
    compute_rotational_constants,
    kabsch_rmsd,
    route_qm_tier,
)
from Libraries.cochem_torq_inference_schemas import ActiveLearningOrchestratorConfig


# Physical Fixture: Ethanol (N=9) [M]
ETHANOL_Z = [6, 6, 8, 1, 1, 1, 1, 1, 1]
ETHANOL_COORDS = np.array(
    [
        [0.0072, 0.0000, 0.0000],  # C1
        [1.5173, 0.0000, 0.0000],  # C2
        [-0.5638, 1.2987, 0.0000],  # O
        [-0.3756, -0.5218, 0.8872],  # H
        [-0.3756, -0.5218, -0.8872],  # H
        [1.9056, 0.5255, 0.8837],  # H
        [1.9056, 0.5255, -0.8837],  # H
        [1.8885, -1.0253, 0.0000],  # H
        [-1.5277, 1.2052, 0.0000],  # H (hydroxyl)
    ],
    dtype=np.float64,
)

# Physical Fixture: Alanine Dipeptide (N=22) [M]
ALANINE_DIPEPTIDE_Z = [
    6, 8, 7, 1, 6, 1, 6, 1, 1, 1, 6, 8, 7, 1, 6, 1, 1, 1, 6, 1, 1, 1
]
ALANINE_DIPEPTIDE_COORDS = np.array(
    [
        [2.012, -0.407, -0.380],
        [1.576, -1.488, -0.771],
        [1.341, 0.697, -0.016],
        [1.776, 1.564, 0.222],
        [-0.089, 0.722, 0.134],
        [-0.344, 0.245, 1.087],
        [-0.721, -0.091, -1.011],
        [-0.495, 0.373, -1.975],
        [-0.334, -1.114, -0.999],
        [-1.808, -0.106, -0.898],
        [-0.589, 2.164, 0.180],
        [-0.038, 2.973, 0.923],
        [-1.637, 2.470, -0.581],
        [-2.083, 1.758, -1.144],
        [-2.247, 3.794, -0.570],
        [-2.213, 4.195, 0.446],
        [-1.706, 4.475, -1.234],
        [-3.284, 3.714, -0.899],
        [3.472, -0.107, -0.324],
        [3.659, 0.885, -0.738],
        [4.020, -0.852, -0.902],
        [3.829, -0.119, 0.710],
    ],
    dtype=np.float64,
)


def test_qbc_energy_variance_and_force_std() -> None:
    """Verify QBC energy variance and maximum atomic force epistemic standard deviation. [M]/[D]"""
    # Authentic ensemble predictions on Ethanol from 4 models
    energies = [-154.250, -154.262, -154.248, -154.256]
    var_e = compute_qbc_energy_variance(energies)
    assert var_e > 0.0
    expected_mean = np.mean(energies)
    expected_var = np.sum((np.array(energies) - expected_mean) ** 2) / 3.0
    assert abs(var_e - expected_var) < 1e-10

    # 4 models x 9 atoms x 3 coords
    m, n = 4, 9
    forces = np.full((m, n, 3), 0.02, dtype=np.float64)
    # Give atom 2 (Oxygen) elevated epistemic spread
    forces[0, 2, :] = [0.12, -0.05, 0.08]
    forces[1, 2, :] = [0.18, -0.02, 0.04]
    forces[2, 2, :] = [0.09, -0.08, 0.11]
    forces[3, 2, :] = [0.22, -0.01, 0.02]

    max_std = compute_max_force_epistemic_std(forces)
    assert max_std > 0.05


def test_acquisition_threshold_trigger(tmp_path: Path) -> None:
    """Verify acquisition threshold triggers correctly on high-variance conformers. [M]"""
    config = ActiveLearningOrchestratorConfig(
        batch_capacity_k=4,
        force_uncertainty_threshold_ev_per_angstrom=0.05,
        energy_uncertainty_threshold_ev2_per_atom=0.001,
        stage_a_rmsd_threshold_angstrom=0.125,
        stage_b_rotational_threshold=0.001,
        staging_manifest_dir=tmp_path / "manifests",
    )
    orch = ActiveLearningOrchestrator(config)

    # Candidate 1: low variance (should NOT trigger)
    c1_coords = ETHANOL_COORDS.copy()
    c1_e = [-154.250, -154.251]
    c1_f = np.full((2, 9, 3), 0.01, dtype=np.float64)
    c1_f[0, 0, :] = [0.012, 0.011, 0.010]
    c1_f[1, 0, :] = [0.015, 0.010, 0.011]

    # Candidate 2: high force variance (SHOULD trigger)
    c2_coords = ETHANOL_COORDS.copy()
    c2_e = [-154.250, -154.251]
    c2_f = np.full((2, 9, 3), 0.01, dtype=np.float64)
    c2_f[0, 2, :] = [0.40, 0.10, -0.10]
    c2_f[1, 2, :] = [0.10, -0.20, 0.30]

    orch.evaluate_pool(
        geometries=[c1_coords, c2_coords],
        atomic_numbers=[ETHANOL_Z, ETHANOL_Z],
        committee_energies=[c1_e, c2_e],
        committee_forces=[c1_f, c2_f],
        candidate_ids=["cand_low_var", "cand_high_var"],
    )

    selected = orch.select_active_batch()
    assert len(selected) == 1
    assert selected[0].candidate_id == "cand_high_var"
    assert selected[0].state == ActiveLearningState.CANDIDATE_SELECTED


def test_kabsch_rmsd_stage_a_deduplication(tmp_path: Path) -> None:
    """Verify Kabsch SVD RMSD prunes duplicate conformers within delta_RMSD = 0.125 A. [M]/[D]"""
    config = ActiveLearningOrchestratorConfig(
        batch_capacity_k=10,
        force_uncertainty_threshold_ev_per_angstrom=0.05,
        stage_a_rmsd_threshold_angstrom=0.125,
        staging_manifest_dir=tmp_path / "manifests",
    )
    orch = ActiveLearningOrchestrator(config)

    # Conformer 1: base Alanine Dipeptide
    coords1 = ALANINE_DIPEPTIDE_COORDS.copy()

    # Conformer 2: rigid rotation of Alanine Dipeptide around z-axis (exact physical duplicate)
    theta = 0.785398  # 45 degrees
    rot_z = np.array([
        [np.cos(theta), -np.sin(theta), 0.0],
        [np.sin(theta), np.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ])
    coords2 = np.dot(coords1, rot_z)

    # Conformer 3: significantly distorted conformer
    coords3 = coords1.copy()
    coords3[0, :] += [0.8, -0.5, 0.6]  # Perturb terminal methyl

    # High force variance on all to trigger acquisition
    high_f = np.full((2, 22, 3), 0.02, dtype=np.float64)
    high_f[0, 0, :] = [0.3, 0.2, 0.1]
    high_f[1, 0, :] = [-0.1, -0.2, 0.4]
    e_pair = [-412.0, -412.1]

    orch.evaluate_pool(
        geometries=[coords1, coords2, coords3],
        atomic_numbers=[ALANINE_DIPEPTIDE_Z, ALANINE_DIPEPTIDE_Z, ALANINE_DIPEPTIDE_Z],
        committee_energies=[e_pair, e_pair, e_pair],
        committee_forces=[high_f, high_f, high_f],
        candidate_ids=["conf1_base", "conf2_rotated", "conf3_distorted"],
    )

    # Pairwise Kabsch between conf1 and rotated conf2 must be near zero (< 1e-10)
    rmsd_1_2 = kabsch_rmsd(coords1, coords2)
    assert rmsd_1_2 < 1e-6

    # Pairwise Kabsch between conf1 and conf3 should exceed threshold 0.125 A
    rmsd_1_3 = kabsch_rmsd(coords1, coords3)
    assert rmsd_1_3 > 0.125

    selected = orch.select_active_batch()
    # Rotated conf2 must be pruned as redundant; only 2 selected (conf1 and conf3)
    assert len(selected) == 2
    selected_ids = {c.candidate_id for c in selected}
    assert "conf1_base" in selected_ids
    assert "conf3_distorted" in selected_ids
    assert "conf2_rotated" not in selected_ids


def test_stage_b_rotational_constant_deduplication() -> None:
    """Verify Stage B rotational constant invariance check prunes spectroscopic duplicates. [M]"""
    # Authentic rotational constants for Ethanol
    rot1 = compute_rotational_constants(ETHANOL_COORDS, ETHANOL_Z)
    assert rot1[0] > rot1[1] >= rot1[2] > 0.0

    # Slight perturbation with identical rotational constants within 0.05%
    rot2 = (rot1[0] * 1.0002, rot1[1] * 0.9999, rot1[2] * 1.0001)
    is_redundant = check_stage_b_rotational_redundancy(rot1, rot2, threshold=0.001)
    assert is_redundant is True

    # Perturbation exceeding 0.1% threshold
    rot3 = (rot1[0] * 1.005, rot1[1], rot1[2])
    is_redundant_3 = check_stage_b_rotational_redundancy(rot1, rot3, threshold=0.001)
    assert is_redundant_3 is False


def test_dynamic_qm_tier_routing() -> None:
    """Verify dynamic QM tier routing across variance levels. [M]"""
    assert route_qm_tier(0.12) == "T3-10s"
    assert route_qm_tier(0.45) == "T3O-1h"
    assert route_qm_tier(0.95) == "T3O-12h"


def test_air_gapped_manifest_emission(tmp_path: Path) -> None:
    """Verify manifest emission generates valid JSON and verifiable SHA-256 in Ring 3. [M]"""
    manifest_dir = tmp_path / "artifacts" / "manifests"
    config = ActiveLearningOrchestratorConfig(
        batch_capacity_k=5,
        force_uncertainty_threshold_ev_per_angstrom=0.05,
        staging_manifest_dir=manifest_dir,
    )
    orch = ActiveLearningOrchestrator(config)

    # Setup one triggered candidate
    coords = ETHANOL_COORDS.copy()
    e_pair = [-154.250, -154.260]
    high_f = np.full((2, 9, 3), 0.02, dtype=np.float64)
    high_f[0, 2, :] = [0.5, 0.02, 0.01]
    high_f[1, 2, :] = [-0.3, 0.01, 0.02]

    orch.evaluate_pool(
        geometries=[coords],
        atomic_numbers=[ETHANOL_Z],
        committee_energies=[e_pair],
        committee_forces=[high_f],
        candidate_ids=["cand_eth_01"],
    )
    orch.select_active_batch()

    manifest_file, sha256_hash = orch.emit_air_gapped_manifest()

    assert manifest_file.exists()
    assert orch.selected_batch[0].state == ActiveLearningState.MANIFEST_EMITTED

    # Verify SHA-256 digest file
    digest_file = manifest_file.with_suffix(manifest_file.suffix + ".sha256")
    assert digest_file.exists()
    digest_content = digest_file.read_text(encoding="utf-8")
    assert sha256_hash in digest_content

    # Re-hash file content directly
    actual_hash = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    assert actual_hash == sha256_hash

    # Verify JSON content
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["selected_count"] == 1
    assert data["candidates"][0]["candidate_id"] == "cand_eth_01"
    assert data["candidates"][0]["assigned_tier"] == "T3O-1h"
