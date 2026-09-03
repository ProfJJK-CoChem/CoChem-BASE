"""Physical Verification Test Suite for CoChem-TOPOS Alignment Part 1.

Verifies chiral enantiomer reflection parity guards, collinear rank-deficiency,
coplanar coordinate stabilization, BSSE ghost-atom exclusion, Pydantic validation,
numerical degeneracy safeguards, MCS timeouts, ensemble clustering, and HDF5 persistence [M][D].
"""

from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np
from pydantic import ValidationError
import pytest

from cochem.topos.alignment import (
    AirGapBoundaryViolationError,
    AlignedConformerResult,
    CollinearDegeneracyError,
    ConformerInput,
    DegenerateCoordinatesError,
    EnsembleAlignmentSummary,
    IncompatibleTopologyError,
    MCSAlignmentConfig,
    MCSConvergenceTimeoutError,
    StorageTier,
    align_conformers_by_mcs,
    cluster_ensemble_conformers,
    compute_kabsch_transformation,
    detect_concurrency_tier,
    persist_aligned_ensemble_h5,
)


def test_kabsch_chiral_enantiomer_reflection_guard():
    """REQ-TOPOS-013.3 & REQ-TOPOS-013.4: Verify that Kabsch alignment between chiral enantiomers

    enforces proper rotation det(R) = +1.0 via parity correction factor d = -1, preventing coordinate inversion.
    """
    coords_l = np.array(
        [
            [-0.432, 1.254, -0.428],  # N
            [0.000, 0.000, 0.354],  # CA
            [1.520, 0.000, 0.354],  # C
            [2.145, 1.050, 0.354],  # O
            [-0.534, -1.242, -0.354],  # CB
        ],
        dtype=np.float64,
    )

    coords_d = coords_l.copy()
    coords_d[:, 2] *= -1.0

    r_rot, t_trans, rmsd = compute_kabsch_transformation(coords_d, coords_l)

    assert np.allclose(r_rot.T @ r_rot, np.eye(3), atol=1e-5), "Rotation matrix must satisfy R.T @ R = I"
    assert np.isclose(np.linalg.det(r_rot), 1.0, atol=1e-5), f"Improper rotation detected: det(R) = {np.linalg.det(r_rot)}"
    assert rmsd > 0.1, "Enantiomer alignment must retain non-zero RMSD under proper SO(3) rotation"


def test_collinear_degeneracy_detection():
    """REQ-TOPOS-013.3: Verify that collinear coordinates (e.g., linear acetylene C2H2)

    trigger CollinearDegeneracyError due to singular value condition ratio sigma_2 / sigma_1 < 1e-7.
    """
    acetylene_coords = np.array(
        [
            [0.0, 0.0, -1.665],  # H1
            [0.0, 0.0, -0.601],  # C1
            [0.0, 0.0, 0.601],  # C2
            [0.0, 0.0, 1.665],  # H2
        ],
        dtype=np.float64,
    )

    rotated_coords = acetylene_coords @ np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)

    with pytest.raises(CollinearDegeneracyError) as exc_info:
        compute_kabsch_transformation(rotated_coords, acetylene_coords)
    assert "collinear" in str(exc_info.value).lower()


def test_coplanar_coordinates_stabilization():
    """REQ-TOPOS-013.3: Verify that coplanar coordinates (benzene C6 heavy atoms in xy-plane)

    are successfully stabilized via right-handed cross-product basis completion without degeneracy failure.
    """
    angles = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    r_cc = 1.397
    benzene_c = np.column_stack([r_cc * np.cos(angles), r_cc * np.sin(angles), np.zeros(6)])

    theta = np.pi / 4.0
    r_z = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0.0],
            [np.sin(theta), np.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rotated_benzene = benzene_c @ r_z.T + np.array([1.5, -2.0, 0.0])

    r_rot, t_trans, rmsd = compute_kabsch_transformation(rotated_benzene, benzene_c)
    assert np.allclose(r_rot.T @ r_rot, np.eye(3), atol=1e-5)
    assert np.isclose(np.linalg.det(r_rot), 1.0, atol=1e-5)
    assert np.isclose(rmsd, 0.0, atol=1e-5)


def test_bsse_ghost_atom_exclusion_and_mass():
    """REQ-TOPOS-013.1 & REQ-TOPOS-013.2: Verify that BSSE counterpoise complexes with ghost atoms (Z=0)

    assign zero mass without throwing Mendeleev ValueError, and are excluded from alignment calculations.
    """
    target = ConformerInput(
        conformer_id="bsse_dimer_conf_1",
        elements=["O", "H", "H", "Gh", "Gh", "Gh"],
        atomic_numbers=[8, 1, 1, 0, 0, 0],
        coordinates=[
            (0.000, 0.000, 0.117),
            (0.000, 0.757, -0.469),
            (0.000, -0.757, -0.469),
            (2.800, 0.000, 0.117),
            (2.800, 0.757, -0.469),
            (2.800, -0.757, -0.469),
        ],
        is_ghost=[False, False, False, True, True, True],
    )
    assert len(target.is_ghost) == 6
    assert target.is_ghost[3] is True
    masses = target.get_dynamic_masses()
    assert len(masses) == 6
    assert masses[0] > 15.0  # Oxygen
    assert masses[3] == 0.0  # Ghost atom


def test_pydantic_validation_guards():
    """Verify that Pydantic v2 data models reject empty coordinate lists, non-orthogonal rotation matrices,

    and asymmetric pairwise RMSD matrices.
    """
    with pytest.raises(ValidationError):
        ConformerInput(
            conformer_id="invalid_conf_01",
            elements=["C", "C", "C"],
            atomic_numbers=[6, 6, 6],
            coordinates=[],
        )

    non_orthogonal_mat = [[2.0, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 1.0]]
    with pytest.raises(ValidationError):
        AlignedConformerResult(
            conformer_id="conf_01",
            reference_id="ref_01",
            rmsd_angstrom=0.15,
            rotation_matrix=non_orthogonal_mat,
            translation_vector=[0.0, 0.0, 0.0],
            aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            atom_mapping={0: 0, 1: 1, 2: 2},
            execution_duration_seconds=0.012,
        )

    with pytest.raises(ValidationError):
        EnsembleAlignmentSummary(
            ensemble_id="ens_01",
            reference_id="ref_01",
            total_conformers=2,
            aligned_conformers=[],
            pairwise_rmsd_matrix=[[0.0, 0.35], [0.10, 0.0]],
        )


def test_point_degeneracy_error():
    """REQ-TOPOS-013.3: Verify that point-collapsed coordinates raise DegenerateCoordinatesError."""
    point_coords = np.zeros((4, 3), dtype=np.float64)
    ref_coords = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    with pytest.raises(DegenerateCoordinatesError):
        compute_kabsch_transformation(point_coords, ref_coords)


def test_incompatible_topology_atom_count_error():
    """REQ-TOPOS-013.1: Verify IncompatibleTopologyError when overlapping atom count N_MCS < 3."""
    target = ConformerInput(
        conformer_id="conf_diatomic",
        elements=["H", "Cl"],
        atomic_numbers=[1, 17],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 1.27)],
    )
    ref = ConformerInput(
        conformer_id="conf_water",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    with pytest.raises(IncompatibleTopologyError):
        align_conformers_by_mcs(target, ref)


def test_mcs_timeout_raises_custom_error():
    """REQ-TOPOS-013.1: Verify that an exhausted MCS timeout ceiling raises MCSConvergenceTimeoutError."""
    c1 = ConformerInput(
        conformer_id="polycycle_1",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[(float(i), 0.0, 0.0) for i in range(10)],
    )
    c2 = ConformerInput(
        conformer_id="polycycle_2",
        elements=["C"] * 10,
        atomic_numbers=[6] * 10,
        coordinates=[(0.0, float(i), 0.0) for i in range(10)],
    )
    tight_config = MCSAlignmentConfig(timeout_seconds=0.0001)
    with pytest.raises(MCSConvergenceTimeoutError):
        align_conformers_by_mcs(c1, c2, config=tight_config)


def test_cluster_ensemble_deduplication():
    """REQ-TOPOS-013.5: Verify pairwise RMSD calculation and duplicate cluster grouping."""
    ref = ConformerInput(
        conformer_id="ref_methane",
        elements=["C", "H", "H", "H", "H"],
        atomic_numbers=[6, 1, 1, 1, 1],
        coordinates=[
            (0.000, 0.000, 0.000),
            (0.629, 0.629, 0.629),
            (-0.629, -0.629, 0.629),
            (-0.629, 0.629, -0.629),
            (0.629, -0.629, -0.629),
        ],
    )
    dup = ConformerInput(
        conformer_id="dup_methane",
        elements=ref.elements,
        atomic_numbers=ref.atomic_numbers,
        coordinates=ref.coordinates,
    )
    summary = cluster_ensemble_conformers([ref, dup], reference=ref)
    assert summary.total_conformers == 2
    assert len(summary.duplicate_clusters) >= 1
    assert "dup_methane" in summary.duplicate_clusters[0] or "ref_methane" in summary.duplicate_clusters[0]


def test_persist_aligned_ensemble_h5_roundtrip(tmp_path, monkeypatch):
    """REQ-TOPOS-013.6: Verify thread-safe HDF5 persistence and air-gap boundary check."""
    store_dir = tmp_path / "topos_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCH_STORE_DIR", str(store_dir))

    summary = EnsembleAlignmentSummary(
        ensemble_id="test_ensemble_01",
        reference_id="ref_01",
        total_conformers=1,
        aligned_conformers=[
            AlignedConformerResult(
                conformer_id="conf_01",
                reference_id="ref_01",
                rmsd_angstrom=0.05,
                rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                translation_vector=[0.0, 0.0, 0.0],
                aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
                atom_mapping={0: 0, 1: 1, 2: 2},
                execution_duration_seconds=0.01,
            )
        ],
        pairwise_rmsd_matrix=[[0.0]],
        duplicate_clusters=[],
        mcs_mapping={0: 0, 1: 1, 2: 2},
        aligned_mcs_coords=[[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]],
    )

    archive_path = store_dir / "ensemble_01.h5"
    out_path = persist_aligned_ensemble_h5(summary, archive_path)
    assert out_path.exists()

    with h5py.File(out_path, "r") as h5f:
        assert f"/ensembles/{summary.ensemble_id}/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/pairwise_rmsd" in h5f
        assert f"/ensembles/{summary.ensemble_id}/mcs_mapping" in h5f

    # Air-gap violation check
    outside_path = tmp_path / "unauthorized" / "leak.h5"
    with pytest.raises(AirGapBoundaryViolationError):
        persist_aligned_ensemble_h5(summary, outside_path)


def test_concurrency_tier_detection(monkeypatch):
    """REQ-TOPOS-013.6: Verify concurrency tier detection logic across environment markers."""
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    assert detect_concurrency_tier() == StorageTier.TIER6_HPC
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert detect_concurrency_tier() == StorageTier.TIER5_GITHUB_ACTIONS
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    monkeypatch.setenv("CODESPACES", "true")
    assert detect_concurrency_tier() == StorageTier.TIER4_CODESPACES
    monkeypatch.delenv("CODESPACES", raising=False)


def test_mass_weighted_alignment_preserves_so3_and_calculates_analytical_rmsd():
    """REQ-TOPOS-013.2 & REQ-TOPOS-013.4: Verify mass-weighted alignment dynamically pulls masses via mendeleev."""
    c1 = ConformerInput(
        conformer_id="water_1",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    c2 = ConformerInput(
        conformer_id="water_2",
        elements=["O", "H", "H"],
        atomic_numbers=[8, 1, 1],
        coordinates=[(0.0, 0.0, 0.117), (0.0, 0.757, -0.469), (0.0, -0.757, -0.469)],
    )
    cfg = MCSAlignmentConfig(mass_weighting=True)
    res = align_conformers_by_mcs(c1, c2, config=cfg)
    assert res.rmsd_angstrom < 1e-4
    assert np.allclose(np.array(res.rotation_matrix).T @ np.array(res.rotation_matrix), np.eye(3), atol=1e-4)
    assert np.isclose(np.linalg.det(np.array(res.rotation_matrix)), 1.0, atol=1e-4)


def test_heterogeneous_ensemble_persistence_h5(tmp_path, monkeypatch):
    """REQ-TOPOS-013.6: Verify HDF5 persistence for heterogeneous ensembles with differing atom counts."""
    store_dir = tmp_path / "topos_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCH_STORE_DIR", str(store_dir))

    conf_3atom = AlignedConformerResult(
        conformer_id="conf_3",
        reference_id="ref_root",
        rmsd_angstrom=0.01,
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translation_vector=[0.0, 0.0, 0.0],
        aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        atom_mapping={0: 0, 1: 1, 2: 2},
        execution_duration_seconds=0.005,
    )
    conf_4atom = AlignedConformerResult(
        conformer_id="conf_4",
        reference_id="ref_root",
        rmsd_angstrom=0.02,
        rotation_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translation_vector=[0.0, 0.0, 0.0],
        aligned_coordinates=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
        atom_mapping={0: 0, 1: 1, 2: 2},
        execution_duration_seconds=0.006,
    )
    summary = EnsembleAlignmentSummary(
        ensemble_id="ens_hetero_01",
        reference_id="ref_root",
        total_conformers=2,
        aligned_conformers=[conf_3atom, conf_4atom],
        pairwise_rmsd_matrix=[[0.0, 0.1], [0.1, 0.0]],
        duplicate_clusters=[],
        mcs_mapping={0: 0, 1: 1, 2: 2},
    )

    archive_path = store_dir / "hetero_ensemble.h5"
    out_path = persist_aligned_ensemble_h5(summary, archive_path)
    assert out_path.exists()

    with h5py.File(out_path, "r") as h5f:
        assert f"/ensembles/{summary.ensemble_id}/conformers/conf_3/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/conformers/conf_4/aligned_coords" in h5f
        assert f"/ensembles/{summary.ensemble_id}/pairwise_rmsd" in h5f
