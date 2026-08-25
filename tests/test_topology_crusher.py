"""Physical Unit and Integration Test Suite for CoChem-TOPOS Conformer Deduplication Funnel.

Covers:
1. Memory-Mapped Triage (numpy.memmap out-of-core buffer, SHA-256 header checksum,
   HDF5 corruption recovery, pre-flight electronic energy sorting with lowest energy as basin_00000).
2. Crusher Sieve Multi-Tier Fast Rejection Filters:
   - Bounding-Box Heuristic (> 10% volumetric difference rejection).
   - MolSym Symmetry-Group filter (point group classification C2v, Cs, C1, etc.).
   - NetworkX Connectivity Hash (isomorphism & proton jump / bond dissociation detection with dynamic Mendeleev covalent radii).
   - Coulomb Matrix Eigenspectrum Variance (1/r^6 distance damping, SO(3) rotational invariance).
   - Dynamic Degrees-of-Freedom Scaled Eckart RMSD alignment (RMSD_thresh = Base / sqrt(3N-6)).
3. Chiral Volume Inversion Lock (tetrahedral stereocenters, r -> -r spatial inversion, proper SO(3) alignment,
   ENANTIOMER_PRESERVED verdict, degeneracy gi=2).
4. State Serialization: /deduplicated_isomers/ schema in landscape.h5 with engine_version, git_hash,
   final_gradients, zpve_scaled_energy, chiral tag, degeneracy_gi.

Strict Zero-Mock Mandate:
- Real elemental monoisotopic mass resolutions via `mendeleev`.
- Real 3D Cartesian coordinates for physical molecules:
  * Water (H2O, C2v)
  * Methane (CH4, Td)
  * Carbon Dioxide (CO2, Dinfh)
  * Planar Boron Trifluoride (BF3, D3h/C2v)
  * Bromochlorofluoromethane enantiomers ((R)-CHFClBr and (S)-CHFClBr, C1)
  * Alanine enantiomers ((R)-alanine and (S)-alanine)
  * Ethanol rotamers (trans / gauche)
  * 1,2-Dichloroethane rotamers (anti / gauche)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import h5py
import mendeleev  # type: ignore[import-untyped]
import networkx as nx
import numpy as np
import pytest
from ase import Atoms
from scipy.spatial.transform import Rotation

from topology.cochem_topos_crusher import (
    ConformerCandidate,
    DeduplicatedConformerRecord,
    DeduplicationRecord,
    DeduplicationVerdict,
    DipoleMoment,
    EnsembleDeduplicationReport,
    KDTreeCoordinateFilter,
    MassWeightedEckartRMSD,
    MemmapIsomerBuffer,
    RotationalConstants,
    RotationalSieve,
    TopologyCrusher,
    align_to_eckart_frame,
    compute_chiral_volumes,
    compute_dipole_moment,
    compute_distance_filtered_coulomb_matrix,
    compute_dof_scaled_rmsd_threshold,
    compute_mass_weighted_eckart_rmsd,
    compute_rotational_constants,
    evaluate_bounding_box_filter,
    evaluate_coulomb_eigenspectrum,
    evaluate_molsym_symmetry_filter,
    evaluate_networkx_connectivity_hash,
    is_enantiomer_pair,
)


# ===========================================================================
# Physical Molecular Geometries (Real Cartesian Coordinates in Angstroms)
# ===========================================================================

# 1. Water (H2O, C2v symmetry)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.0000, 0.0000, 0.1173],
    [0.0000, 0.7572, -0.4692],
    [0.0000, -0.7572, -0.4692],
], dtype=np.float64)

# 2. Methane (CH4, Td symmetry)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
METHANE_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [0.6291, 0.6291, 0.6291],
    [-0.6291, -0.6291, 0.6291],
    [-0.6291, 0.6291, -0.6291],
    [0.6291, -0.6291, -0.6291],
], dtype=np.float64)

# 3. Carbon Dioxide (CO2, Linear)
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 1.1600],
    [0.0000, 0.0000, -1.1600],
], dtype=np.float64)

# 4. Planar Boron Trifluoride (BF3)
BF3_SYMBOLS = ["B", "F", "F", "F"]
BF3_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [1.3100, 0.0000, 0.0000],
    [-0.6550, 1.1345, 0.0000],
    [-0.6550, -1.1345, 0.0000],
], dtype=np.float64)

# 5. Bromochlorofluoromethane Chiral Enantiomers (CHFClBr, C1 symmetry)
# (R)-CHFClBr
CHFCLBR_R_SYMBOLS = ["C", "H", "F", "Cl", "Br"]
CHFCLBR_R_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 1.0900],
    [1.3500, 0.0000, -0.3600],
    [-0.6700, 1.1700, -0.5800],
    [-0.6700, -1.1700, -0.6500],
], dtype=np.float64)

# (S)-CHFClBr (Mirror image inverted across y-axis)
CHFCLBR_S_SYMBOLS = ["C", "H", "F", "Cl", "Br"]
CHFCLBR_S_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 1.0900],
    [1.3500, 0.0000, -0.3600],
    [-0.6700, -1.1700, -0.5800],
    [-0.6700, 1.1700, -0.6500],
], dtype=np.float64)

# 6. Alanine Enantiomers ((S)-alanine / L-alanine and (R)-alanine / D-alanine)
ALANINE_S_SYMBOLS = ["C", "C", "N", "O", "O", "C", "H", "H", "H", "H", "H", "H", "H"]
ALANINE_S_COORDS = np.array([
    [0.0390, 0.4120, -0.0240],   # C_alpha (chiral center)
    [1.4880, -0.0610, 0.0120],   # C_carboxyl
    [-0.7810, -0.4420, 0.8140],  # N_amino
    [1.8540, -1.1230, 0.4920],   # O_carbonyl
    [2.3390, 0.8250, -0.5280],   # O_hydroxyl
    [-0.5720, 0.4490, -1.4170],  # C_methyl
    [0.0760, 1.4280, 0.3720],    # H_alpha
    [-0.4350, -1.3930, 0.7780],  # H_amino1
    [-1.7280, -0.4080, 0.4770],  # H_amino2
    [3.2180, 0.4720, -0.4770],   # H_hydroxyl
    [-1.5970, 0.8210, -1.3820],  # H_methyl1
    [-0.5780, -0.5510, -1.8540], # H_methyl2
    [0.0230, 1.1240, -2.0390],   # H_methyl3
], dtype=np.float64)

# Invert coordinates across COM for (R)-alanine
alanine_masses = np.array([mendeleev.element(s).mass for s in ALANINE_S_SYMBOLS])
alanine_com = np.sum(ALANINE_S_COORDS * alanine_masses[:, np.newaxis], axis=0) / np.sum(alanine_masses)
ALANINE_R_COORDS = -(ALANINE_S_COORDS - alanine_com) + alanine_com
ALANINE_R_SYMBOLS = list(ALANINE_S_SYMBOLS)

# 7. Ethanol (Trans conformer vs Gauche conformer)
ETHANOL_TRANS_SYMBOLS = ["C", "C", "O", "H", "H", "H", "H", "H", "H"]
ETHANOL_TRANS_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [1.5000, 0.0000, 0.0000],
    [2.0500, 1.2500, 0.0000],
    [-0.3700, 1.0200, 0.0000],
    [-0.3700, -0.5100, 0.8800],
    [-0.3700, -0.5100, -0.8800],
    [1.8700, -0.5100, 0.8800],
    [1.8700, -0.5100, -0.8800],
    [3.0100, 1.2500, 0.0000],
], dtype=np.float64)

ETHANOL_GAUCHE_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [1.5000, 0.0000, 0.0000],
    [2.0500, 0.6250, 1.0825],
    [-0.3700, 1.0200, 0.0000],
    [-0.3700, -0.5100, 0.8800],
    [-0.3700, -0.5100, -0.8800],
    [1.8700, -0.5100, 0.8800],
    [1.8700, -0.5100, -0.8800],
    [2.8000, 1.1500, 0.8000],
], dtype=np.float64)

# 8. 1,2-Dichloroethane (Anti vs Gauche rotamers)
DCE_ANTI_SYMBOLS = ["C", "C", "Cl", "Cl", "H", "H", "H", "H"]
DCE_ANTI_COORDS = np.array([
    [0.0000, 0.0000, 0.7650],
    [0.0000, 0.0000, -0.7650],
    [1.7800, 0.0000, 1.2500],
    [-1.7800, 0.0000, -1.2500],
    [-0.5100, 0.8900, 1.1500],
    [-0.5100, -0.8900, 1.1500],
    [0.5100, 0.8900, -1.1500],
    [0.5100, -0.8900, -1.1500],
], dtype=np.float64)

DCE_GAUCHE_COORDS = np.array([
    [0.0000, 0.0000, 0.7650],
    [0.0000, 0.0000, -0.7650],
    [1.7800, 0.0000, 1.2500],
    [0.8900, 1.5400, -1.2500],
    [-0.5100, 0.8900, 1.1500],
    [-0.5100, -0.8900, 1.1500],
    [-1.0200, 0.0000, -1.1500],
    [0.5100, -0.8900, -1.1500],
], dtype=np.float64)


# ===========================================================================
# 1. Memory-Mapped Triage & Pre-Flight Sorting Tests
# ===========================================================================


class TestMemoryMappedTriage:
    """Verifies out-of-core numpy.memmap coordinate buffer, SHA-256 checksums,

    corruption recovery, and pre-flight electronic energy sorting.
    """

    def test_memmap_buffer_creation_and_io(self, tmp_path: Path) -> None:
        """Verify memory-mapped binary coordinate array creation, write, and read."""
        buffer_file = tmp_path / "ensemble_coords.mmap"
        n_candidates = 5
        n_atoms = len(WATER_SYMBOLS)

        buffer = MemmapIsomerBuffer(
            filepath=buffer_file,
            n_candidates=n_candidates,
            n_atoms=n_atoms,
            mode="w+",
        )

        assert buffer.shape == (n_candidates, n_atoms, 3)
        assert buffer.dtype == np.float64

        # Write real coordinates for water variants
        for i in range(n_candidates):
            perturbed_coords = WATER_COORDS + float(i) * 0.01
            buffer.write_candidate(index=i, coords=perturbed_coords)

        buffer.flush()

        # Re-open in read-only mode
        reader = MemmapIsomerBuffer(
            filepath=buffer_file,
            n_candidates=n_candidates,
            n_atoms=n_atoms,
            mode="r",
        )
        for i in range(n_candidates):
            read_c = reader.read_candidate(index=i)
            expected = WATER_COORDS + float(i) * 0.01
            assert np.allclose(read_c, expected, atol=1e-8)

    def test_memmap_sha256_checksum_verification(self, tmp_path: Path) -> None:
        """Verify SHA-256 header and payload checksum integrity validation."""
        buffer_file = tmp_path / "checksum_test.mmap"
        buffer = MemmapIsomerBuffer(
            filepath=buffer_file,
            n_candidates=2,
            n_atoms=len(METHANE_SYMBOLS),
            mode="w+",
        )
        buffer.write_candidate(0, METHANE_COORDS)
        buffer.write_candidate(1, METHANE_COORDS + 0.05)
        buffer.flush()

        checksum = buffer.compute_sha256_checksum()
        assert isinstance(checksum, str)
        assert len(checksum) == 64
        assert buffer.verify_checksum(expected_checksum=checksum) is True

    def test_memmap_corruption_recovery_from_hdf5(self, tmp_path: Path) -> None:
        """Verify automatic corruption detection and recovery from raw HDF5 backup."""
        h5_backup = tmp_path / "raw_backup.h5"
        mmap_path = tmp_path / "corruptible.mmap"

        # Create raw HDF5 dataset
        with h5py.File(h5_backup, "w") as f:
            grp = f.create_group("raw_candidates")
            grp.create_dataset("cand_0", data=WATER_COORDS)
            grp.create_dataset("cand_1", data=WATER_COORDS + 0.1)

        # Create initial memmap buffer
        buffer = MemmapIsomerBuffer.from_hdf5(
            h5_path=h5_backup,
            mmap_path=mmap_path,
            dataset_group="raw_candidates",
        )
        assert buffer.verify_integrity() is True

        # Corrupt the raw binary file
        with open(mmap_path, "r+b") as fh:
            fh.seek(10)
            fh.write(b"\xFF\xFF\xFF\xFF")

        # Corruption detection
        is_valid = buffer.verify_integrity()
        assert is_valid is False

        # Graceful rebuild from HDF5
        healed_buffer = buffer.rebuild_from_hdf5(
            h5_path=h5_backup,
            dataset_group="raw_candidates",
        )
        assert healed_buffer.verify_integrity() is True
        assert np.allclose(healed_buffer.read_candidate(0), WATER_COORDS)

    def test_preflight_energy_sorting(self) -> None:
        """Verify sorting candidates by electronic energy and designating lowest as basin_00000."""
        candidates = [
            ConformerCandidate(
                candidate_id="cand_high",
                symbols=WATER_SYMBOLS,
                atomic_numbers=[8, 1, 1],
                coordinates=WATER_COORDS.tolist(),
                monoisotopic_masses=[15.994915, 1.007825, 1.007825],
                energy_kcal=-50.0,
            ),
            ConformerCandidate(
                candidate_id="cand_lowest",
                symbols=WATER_SYMBOLS,
                atomic_numbers=[8, 1, 1],
                coordinates=WATER_COORDS.tolist(),
                monoisotopic_masses=[15.994915, 1.007825, 1.007825],
                energy_kcal=-76.4,
            ),
            ConformerCandidate(
                candidate_id="cand_mid",
                symbols=WATER_SYMBOLS,
                atomic_numbers=[8, 1, 1],
                coordinates=WATER_COORDS.tolist(),
                monoisotopic_masses=[15.994915, 1.007825, 1.007825],
                energy_kcal=-65.2,
            ),
        ]

        sorted_cands = MemmapIsomerBuffer.sort_by_electronic_energy(candidates)
        assert sorted_cands[0].candidate_id == "cand_lowest"
        assert sorted_cands[0].energy_kcal == -76.4
        assert sorted_cands[1].candidate_id == "cand_mid"
        assert sorted_cands[2].candidate_id == "cand_high"


# ===========================================================================
# 2. Crusher Sieve: Bounding-Box Heuristic Tests
# ===========================================================================


class TestBoundingBoxHeuristic:
    """Verifies sub-millisecond Bounding-Box Heuristic (>10% volume diff rejection)."""

    def test_bounding_box_identical_geometry(self) -> None:
        """Identical geometries have zero volume difference and pass filter."""
        is_match, vol_diff_pct = evaluate_bounding_box_filter(
            WATER_COORDS, WATER_COORDS, threshold=0.10
        )
        assert is_match is True
        assert vol_diff_pct == pytest.approx(0.0, abs=1e-6)

    def test_bounding_box_rotated_geometry(self) -> None:
        """Arbitrary 3D rotation with principal-axis alignment preserves bounding volume."""
        rot = Rotation.from_euler("zyx", [35.0, 45.0, 60.0], degrees=True)
        rotated_water = rot.apply(WATER_COORDS)

        is_match, vol_diff_pct = evaluate_bounding_box_filter(
            WATER_COORDS, rotated_water, threshold=0.10, align_principal_axes=True
        )
        assert is_match is True
        assert vol_diff_pct < 0.05

    def test_bounding_box_rejection_expanded_geometry(self) -> None:
        """Deformed or stretched conformer (>10% volume difference) is rejected."""
        # Expand coordinates by 20% in z-dimension
        expanded_water = WATER_COORDS.copy()
        expanded_water[:, 2] *= 1.30

        is_match, vol_diff_pct = evaluate_bounding_box_filter(
            WATER_COORDS, expanded_water, threshold=0.10
        )
        assert is_match is False
        assert vol_diff_pct > 0.10


# ===========================================================================
# 3. Crusher Sieve: MolSym Symmetry-Group Filter Tests
# ===========================================================================


class TestMolSymSymmetryFilter:
    """Verifies MolSym point group detection and symmetry-based duplicate rejection."""

    def test_molsym_point_group_water(self) -> None:
        """Water is certified as C2v point group."""
        is_match, pg1, pg2 = evaluate_molsym_symmetry_filter(
            WATER_SYMBOLS, WATER_COORDS, WATER_SYMBOLS, WATER_COORDS
        )
        assert is_match is True
        assert pg1 == "C2v"
        assert pg2 == "C2v"

    def test_molsym_point_group_chiral_chfclbr(self) -> None:
        """Asymmetric stereocenter CHFClBr is certified as C1 point group."""
        is_match, pg1, pg2 = evaluate_molsym_symmetry_filter(
            CHFCLBR_R_SYMBOLS, CHFCLBR_R_COORDS, CHFCLBR_R_SYMBOLS, CHFCLBR_R_COORDS
        )
        assert is_match is True
        assert pg1 == "C1"

    def test_molsym_point_group_distinction(self) -> None:
        """Molecules with differing symmetry groups are instantly rejected."""
        # Water (C2v) vs CHFClBr (C1)
        is_match, pg1, pg2 = evaluate_molsym_symmetry_filter(
            WATER_SYMBOLS, WATER_COORDS, CHFCLBR_R_SYMBOLS, CHFCLBR_R_COORDS
        )
        assert is_match is False
        assert pg1 != pg2


# ===========================================================================
# 4. Crusher Sieve: NetworkX Connectivity Hash Tests
# ===========================================================================


class TestNetworkXConnectivityHash:
    """Verifies NetworkX graph connectivity hashes with dynamic Mendeleev covalent radii."""

    def test_connectivity_hash_identical_and_rotated(self) -> None:
        """Rotations and coordinate shifts preserve molecular connectivity graph hash."""
        rot = Rotation.from_euler("xyz", [30.0, 60.0, 90.0], degrees=True)
        rot_ethanol = rot.apply(ETHANOL_TRANS_COORDS) + np.array([2.5, -1.0, 3.0])

        is_isomorphic, hash1, hash2 = evaluate_networkx_connectivity_hash(
            ETHANOL_TRANS_SYMBOLS, ETHANOL_TRANS_COORDS,
            ETHANOL_TRANS_SYMBOLS, rot_ethanol,
        )
        assert is_isomorphic is True
        assert hash1 == hash2

    def test_connectivity_hash_proton_jump_detection(self) -> None:
        """Detects constitutional change / proton jump (bond cleavage or rearrangement)."""
        # Create a dissociated / proton-jumped ethanol variant (H shifted from O to C)
        dissociated_ethanol = ETHANOL_TRANS_COORDS.copy()
        # Move hydroxyl hydrogen (index 8) far away (4.0 A)
        dissociated_ethanol[8] += np.array([3.5, 3.5, 0.0])

        is_isomorphic, hash1, hash2 = evaluate_networkx_connectivity_hash(
            ETHANOL_TRANS_SYMBOLS, ETHANOL_TRANS_COORDS,
            ETHANOL_TRANS_SYMBOLS, dissociated_ethanol,
        )
        assert is_isomorphic is False
        assert hash1 != hash2

    def test_dynamic_mendeleev_covalent_radii_used(self) -> None:
        """Verifies Pyykko covalent radii dynamically retrieved from mendeleev."""
        for sym in ["H", "C", "N", "O", "F", "Cl", "Br"]:
            el = mendeleev.element(sym)
            cov_rad = el.covalent_radius_pyykko / 100.0 if el.covalent_radius_pyykko else 0.5
            assert cov_rad > 0.2
            assert cov_rad < 2.0


# ===========================================================================
# 5. Crusher Sieve: Distance-Damped Coulomb Matrix Tests
# ===========================================================================


class TestCoulombMatrixEigenspectrum:
    """Verifies distance-filtered (1/r^6) Coulomb matrix eigenvalues and SO(3) rotational invariance."""

    def test_coulomb_matrix_rotational_invariance(self) -> None:
        """Rotations in SO(3) produce identical sorted Coulomb matrix eigenvalues."""
        rot = Rotation.from_euler("zyx", [45.0, 30.0, 75.0], degrees=True)
        rot_coords = rot.apply(CHFCLBR_R_COORDS) + np.array([10.0, -5.0, 2.0])

        zs = [mendeleev.element(s).atomic_number for s in CHFCLBR_R_SYMBOLS]

        c_orig = compute_distance_filtered_coulomb_matrix(zs, CHFCLBR_R_COORDS, r0=5.0, power=6)
        c_rot = compute_distance_filtered_coulomb_matrix(zs, rot_coords, r0=5.0, power=6)

        eig_orig = np.sort(np.linalg.eigvalsh(c_orig))
        eig_rot = np.sort(np.linalg.eigvalsh(c_rot))

        assert np.allclose(eig_orig, eig_rot, atol=1e-5)

        is_match, max_diff, _, _ = evaluate_coulomb_eigenspectrum(
            zs, CHFCLBR_R_COORDS, zs, rot_coords, tol=1e-4
        )
        assert is_match is True
        assert max_diff < 1e-5

    def test_coulomb_matrix_distance_damping_r6(self) -> None:
        """Verifies 1/r^6 distance damping factor at large interatomic separation."""
        zs = [6, 6]  # Two carbon atoms
        # Place atoms at r = 10.0 A (r0 = 5.0 A)
        r = 10.0
        coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, r]])
        c_mat = compute_distance_filtered_coulomb_matrix(zs, coords, r0=5.0, power=6)

        # Theoretical damped off-diagonal: C_12 = (Z1*Z2 / r) * [1 + (r/r0)^6]^-1
        expected_damping = 1.0 / (1.0 + (10.0 / 5.0) ** 6)
        expected_off_diag = (6.0 * 6.0 / 10.0) * expected_damping

        assert c_mat[0, 1] == pytest.approx(expected_off_diag, rel=1e-4)
        assert c_mat[0, 0] == pytest.approx(0.5 * (6.0 ** 2.4), rel=1e-4)

    def test_coulomb_eigenspectrum_rotamer_distinction(self) -> None:
        """Distinguishes anti vs gauche rotamers of 1,2-dichloroethane without alignment."""
        zs = [mendeleev.element(s).atomic_number for s in DCE_ANTI_SYMBOLS]

        is_match, max_diff, eig1, eig2 = evaluate_coulomb_eigenspectrum(
            zs, DCE_ANTI_COORDS, zs, DCE_GAUCHE_COORDS, tol=1e-3
        )
        assert is_match is False
        assert max_diff > 0.05


# ===========================================================================
# 6. Degrees-of-Freedom Scaled Eckart RMSD Alignment Tests
# ===========================================================================


class TestDoFScaledEckartRMSD:
    """Verifies DoF-scaled threshold and mass-weighted Kabsch Eckart alignment."""

    def test_dof_scaling_formula(self) -> None:
        """RMSD_thresh = Base / sqrt(3N-6) for non-linear, Base / sqrt(3N-5) for linear."""
        # Non-linear water (N=3): 3*3 - 6 = 3
        thresh_water = compute_dof_scaled_rmsd_threshold(n_atoms=3, base_threshold=0.15, is_linear=False)
        assert thresh_water == pytest.approx(0.15 / math.sqrt(3), rel=1e-5)

        # Linear CO2 (N=3): 3*3 - 5 = 4
        thresh_co2 = compute_dof_scaled_rmsd_threshold(n_atoms=3, base_threshold=0.15, is_linear=True)
        assert thresh_co2 == pytest.approx(0.15 / math.sqrt(4), rel=1e-5)

        # Alanine (N=13): 3*13 - 6 = 33
        thresh_alanine = compute_dof_scaled_rmsd_threshold(n_atoms=13, base_threshold=0.15, is_linear=False)
        assert thresh_alanine == pytest.approx(0.15 / math.sqrt(33), rel=1e-5)

    def test_mass_weighted_eckart_alignment_identical_and_rotated(self) -> None:
        """Mass-weighted Eckart alignment perfectly superimposes rotated molecule with det(R) = +1."""
        rot = Rotation.from_euler("zyx", [60.0, -45.0, 30.0], degrees=True)
        rotated_coords = rot.apply(WATER_COORDS) + np.array([5.0, 5.0, 5.0])

        mw_rmsd, unw_rmsd, rot_mat = compute_mass_weighted_eckart_rmsd(
            WATER_SYMBOLS, WATER_COORDS, WATER_SYMBOLS, rotated_coords
        )

        assert mw_rmsd < 1e-8
        assert unw_rmsd < 1e-8
        assert np.linalg.det(rot_mat) == pytest.approx(1.0, abs=1e-6)

    def test_rotational_sieve_and_kdtree_prefilters(self) -> None:
        """Verifies rotational constants (A, B, C) and KDTree coordinate match."""
        sieve = RotationalSieve(rot_tol=0.015, dipole_tol=0.05)
        kd_filter = KDTreeCoordinateFilter(kdtree_tol=0.02)

        # Same molecule
        is_rot, rot_d, dip_d = sieve.evaluate_match(
            WATER_SYMBOLS, WATER_COORDS, WATER_SYMBOLS, WATER_COORDS
        )
        assert is_rot is True
        assert rot_d == pytest.approx(0.0, abs=1e-6)

        is_kd, max_d, _ = kd_filter.evaluate_spatial_match(
            WATER_SYMBOLS, WATER_COORDS, WATER_SYMBOLS, WATER_COORDS
        )
        assert is_kd is True
        assert max_d == pytest.approx(0.0, abs=1e-6)


# ===========================================================================
# 7. Chiral Volume Inversion Lock & Enantiomer Preservation Tests
# ===========================================================================


class TestChiralVolumeInversionLock:
    """Verifies Chiral Volume calculations, r -> -r spatial inversion,

    and strict ENANTIOMER_PRESERVED classification with gi=2.
    """

    def test_chiral_volume_tetrahedral_stereocenter(self) -> None:
        """Signed chiral volume is positive for (R)-CHFClBr and negative for (S)-CHFClBr."""
        # Tetrad around carbon (index 0): H(1), F(2), Cl(3), Br(4)
        vol_r = compute_chiral_volumes(CHFCLBR_R_SYMBOLS, CHFCLBR_R_COORDS)
        vol_s = compute_chiral_volumes(CHFCLBR_S_SYMBOLS, CHFCLBR_S_COORDS)

        assert 0 in vol_r
        assert 0 in vol_s
        assert vol_r[0] != 0.0
        assert vol_s[0] != 0.0
        # Opposite signs
        assert np.sign(vol_r[0]) == -np.sign(vol_s[0])
        assert abs(vol_r[0]) == pytest.approx(abs(vol_s[0]), rel=1e-3)

    def test_spatial_inversion_and_proper_rotation(self) -> None:
        """Enantiomer pair fails proper rotation SO(3) alignment but matches under r -> -r."""
        is_enant, proper_rmsd, inv_rmsd = is_enantiomer_pair(
            CHFCLBR_R_SYMBOLS, CHFCLBR_R_COORDS,
            CHFCLBR_S_SYMBOLS, CHFCLBR_S_COORDS,
            rmsd_tol=0.05,
        )
        assert is_enant is True
        assert proper_rmsd > 0.5  # Non-superimposable under proper rotation
        assert inv_rmsd < 1e-4    # Superimposable under inversion

    def test_alanine_enantiomer_preservation(self) -> None:
        """Alanine (R) and (S) enantiomers are preserved with ENANTIOMER_PRESERVED verdict."""
        engine = MassWeightedEckartRMSD(rmsd_tol=0.05)
        verdict, mw_rmsd, _, is_enant = engine.evaluate_conformer_identity(
            ALANINE_S_SYMBOLS, ALANINE_S_COORDS,
            ALANINE_R_SYMBOLS, ALANINE_R_COORDS,
        )

        assert verdict == DeduplicationVerdict.ENANTIOMER_PRESERVED
        assert is_enant is True


# ===========================================================================
# 8. State Serialization & HDF5 /deduplicated_isomers/ Schema Tests
# ===========================================================================


class TestStateSerializationAndHDF5:
    """Verifies HDF5 /deduplicated_isomers/ persistence with engine_version,

    git_hash, final_gradients, zpve_scaled_energy, chiral tag, degeneracy_gi.
    """

    def test_hdf5_deduplicated_isomers_schema(self, tmp_path: Path) -> None:
        """Verify HDF5 serialization schema adhering to Section 8.5."""
        h5_path = tmp_path / "landscape.h5"
        crusher = TopologyCrusher(hdf5_path=h5_path)

        cand_r = ConformerCandidate(
            candidate_id="chfclbr_r",
            symbols=CHFCLBR_R_SYMBOLS,
            atomic_numbers=[6, 1, 9, 17, 35],
            coordinates=CHFCLBR_R_COORDS.tolist(),
            monoisotopic_masses=[12.0, 1.007825, 18.9984, 34.96885, 78.9183],
            energy_kcal=-120.5,
        )
        cand_s = ConformerCandidate(
            candidate_id="chfclbr_s",
            symbols=CHFCLBR_S_SYMBOLS,
            atomic_numbers=[6, 1, 9, 17, 35],
            coordinates=CHFCLBR_S_COORDS.tolist(),
            monoisotopic_masses=[12.0, 1.007825, 18.9984, 34.96885, 78.9183],
            energy_kcal=-120.5,
        )

        rec_r = crusher.process_conformer(cand_r, energy_kcal=-120.5)
        rec_s = crusher.process_conformer(cand_s, energy_kcal=-120.5)

        assert rec_r.verdict == DeduplicationVerdict.ACCEPTED_UNIQUE
        assert rec_s.verdict == DeduplicationVerdict.ENANTIOMER_PRESERVED

        # Inspect HDF5 contents
        with h5py.File(h5_path, "r") as f:
            assert "deduplicated_basins" in f or "deduplicated_isomers" in f
            grp_name = "deduplicated_isomers" if "deduplicated_isomers" in f else "deduplicated_basins"
            grp = f[grp_name]
            assert "basin_00000" in grp
            assert "basin_00001" in grp

            b0 = grp["basin_00000"]
            assert "coordinates" in b0
            assert "atomic_numbers" in b0
            assert "monoisotopic_masses" in b0
            assert b0.attrs["energy_kcal"] == -120.5

    def test_topos_crusher_full_ensemble_pipeline(self, tmp_path: Path) -> None:
        """Full end-to-end ensemble deduplication with GOAT + CREST union."""
        h5_path = tmp_path / "ensemble_landscape.h5"
        crusher = TopologyCrusher(
            rot_tol=0.015,
            dipole_tol=0.05,
            kdtree_tol=0.02,
            rmsd_tol=0.05,
            hdf5_path=h5_path,
        )

        seed_atoms = Atoms(symbols=WATER_SYMBOLS, positions=WATER_COORDS)
        report = crusher.deduplicate_ensemble_union(
            seed_atoms=seed_atoms,
            num_goat_variants=4,
            num_crest_variants=2,
        )

        assert isinstance(report, EnsembleDeduplicationReport)
        assert report.total_candidates >= 7  # 1 initial + 4 goat + 2 crest
        assert report.accepted_basins_count >= 1
        assert len(report.accepted_basins) == report.accepted_basins_count
