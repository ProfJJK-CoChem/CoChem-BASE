#!/usr/bin/env python3
"""Comprehensive Zero-Mock Unit and Integration Test Suite for CoChem Stage 2 Ingestor.

Module: tests/test_cochem_stage2_ingestor.py

Tests:
1. Dual-Graph Topology Construction (Covalent subgraphs with 1.15x breathing tolerance,
   inter-monomer non-covalent contact graphs preserving vdW complexes, and monomer separation).
2. Physical Valency Enforcement & Unphysical Valency Severing.
3. Permutation-Invariant Hungarian Kabsch SVD Alignment with Determinant Reflection Trap
   (d = sign(det(V W^T))) and det(U) = +1.0 guarantee.
4. Singular Value Collinearity Trap for Linear / Diatomic species with 2D Z-axis projection.
5. "Jiggle-Quench" Conformer Deduplication and Geometric Clustering.
6. Multi-format Ingestion (.xyz, .sdf) and Bounded Batch Processing.
7. Pydantic Serialization and Zero-Mock AST Compliance.

Authoritative Standards:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\SRS\\Perfected_Document 2 File Inventory & Deliverable Capabilities Manifest (Part 2).md
"""

from __future__ import annotations

import ast
import base64
import math
from pathlib import Path
from typing import List, Set

import networkx as nx
import numpy as np
import pytest

from intake.cochem_stage2_ingestor import (
    CovalentGraphBuilder,
    DualGraphResult,
    HungarianKabschAligner,
    KabschAlignmentResult,
    JiggleQuenchDeduplicator,
    ConformerClusterResult,
    Stage2Ingestor,
    get_covalent_radius,
    get_vdw_radius,
    is_ghost_symbol,
    parse_xyz_text,
    parse_sdf_text,
)


# ==============================================================================
# Authentic Molecular Test Structures (Coordinates in Angstroms)
# ==============================================================================

# Water monomer (H2O)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000, 0.000000, 0.117790],
    [0.000000, 0.755453, -0.471161],
    [0.000000, -0.755453, -0.471161],
], dtype=np.float64)

# Methane (CH4)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
METHANE_COORDS = np.array([
    [0.000000, 0.000000, 0.000000],
    [0.627600, 0.627600, 0.627600],
    [-0.627600, -0.627600, 0.627600],
    [-0.627600, 0.627600, -0.627600],
    [0.627600, -0.627600, -0.627600],
], dtype=np.float64)

# Linear molecules
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.0, 0.0, 0.0],
    [0.0, 0.0, 1.162],
    [0.0, 0.0, -1.162],
], dtype=np.float64)

N2_SYMBOLS = ["N", "N"]
N2_COORDS = np.array([
    [0.0, 0.0, 0.5488],
    [0.0, 0.0, -0.5488],
], dtype=np.float64)

HCN_SYMBOLS = ["H", "C", "N"]
HCN_COORDS = np.array([
    [0.0, 0.0, -1.066],
    [0.0, 0.0, 0.000],
    [0.0, 0.0, 1.153],
], dtype=np.float64)

# Water Dimer (H2O...H2O) at non-covalent equilibrium ~2.91 A O-O distance
WATER_DIMER_SYMBOLS = ["O", "H", "H", "O", "H", "H"]
WATER_DIMER_COORDS = np.array([
    [-1.490, 0.000, 0.000],   # O1 (Donor)
    [-1.850, 0.890, 0.000],   # H1
    [-0.520, 0.000, 0.000],   # H2 (Hydrogen bonded)
    [1.420, 0.000, 0.000],    # O2 (Acceptor)
    [1.770, 0.770, 0.550],    # H3
    [1.770, -0.770, 0.550],   # H4
], dtype=np.float64)

# CO2...H2O van der Waals complex
CO2_WATER_SYMBOLS = ["C", "O", "O", "O", "H", "H"]
CO2_WATER_COORDS = np.array([
    [0.000, 0.000, 0.000],    # C
    [1.160, 0.000, 0.000],    # O
    [-1.160, 0.000, 0.000],   # O
    [0.000, 2.900, 0.000],    # O (Water)
    [0.760, 3.450, 0.000],    # H
    [-0.760, 3.450, 0.000],   # H
], dtype=np.float64)


# ==============================================================================
# 1. Radii Lookup & Ghost Atom Validation
# ==============================================================================

def test_radii_lookup_and_ghost_handling() -> None:
    """Validate authentic covalent and vdW radii lookup with ghost atom protections."""
    r_c_cov = get_covalent_radius("C")
    r_h_cov = get_covalent_radius("H")
    r_o_cov = get_covalent_radius("O")
    
    assert 0.70 <= r_c_cov <= 0.80, f"Carbon covalent radius out of expected bounds: {r_c_cov}"
    assert 0.28 <= r_h_cov <= 0.40, f"Hydrogen covalent radius out of expected bounds: {r_h_cov}"
    assert 0.60 <= r_o_cov <= 0.72, f"Oxygen covalent radius out of expected bounds: {r_o_cov}"

    r_c_vdw = get_vdw_radius("C")
    r_h_vdw = get_vdw_radius("H")
    r_o_vdw = get_vdw_radius("O")

    assert 1.60 <= r_c_vdw <= 1.85, f"Carbon vdW radius out of bounds: {r_c_vdw}"
    assert 1.10 <= r_h_vdw <= 1.30, f"Hydrogen vdW radius out of bounds: {r_h_vdw}"
    assert 1.45 <= r_o_vdw <= 1.65, f"Oxygen vdW radius out of bounds: {r_o_vdw}"

    assert is_ghost_symbol("Gh")
    assert is_ghost_symbol("Gh_C")
    assert is_ghost_symbol("Bq")
    assert is_ghost_symbol("X")
    assert not is_ghost_symbol("C")
    assert not is_ghost_symbol("Xe")


# ==============================================================================
# 2. Dual-Graph Topology Construction & Valency Severing
# ==============================================================================

def test_covalent_graph_construction_water_and_methane() -> None:
    """Validate intra-monomer covalent graph generation with 1.15x breathing tolerance."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)
    
    # Water: 2 O-H bonds, no H-H bond
    g_water = builder.build_covalent_graph(WATER_COORDS, WATER_SYMBOLS)
    assert g_water.number_of_nodes() == 3
    assert g_water.number_of_edges() == 2
    assert g_water.has_edge(0, 1)
    assert g_water.has_edge(0, 2)
    assert not g_water.has_edge(1, 2)
    assert nx.is_connected(g_water)

    # Methane: 4 C-H bonds, no H-H bonds
    g_meth = builder.build_covalent_graph(METHANE_COORDS, METHANE_SYMBOLS)
    assert g_meth.number_of_nodes() == 5
    assert g_meth.number_of_edges() == 4
    for h_idx in [1, 2, 3, 4]:
        assert g_meth.has_edge(0, h_idx)


def test_dual_graph_preserves_vdw_complexes_without_false_covalent_bonds() -> None:
    """Validate dual-graph logic separates intra-monomer covalent vs inter-monomer vdW contacts."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15, vdw_contact_buffer=0.8)
    
    # Water Dimer: 2 separate covalent monomers, 1 non-covalent contact graph
    res: DualGraphResult = builder.build_dual_graph(WATER_DIMER_COORDS, WATER_DIMER_SYMBOLS)
    
    assert res.num_atoms == 6
    assert res.num_covalent_bonds == 4  # 2 in monomer 1 + 2 in monomer 2
    assert len(res.monomers) == 2       # Decomposed into 2 separate water molecules
    assert set(res.monomers[0].atom_indices) == {0, 1, 2}
    assert set(res.monomers[1].atom_indices) == {3, 4, 5}
    
    # Non-covalent contact graph should connect the two monomers via the hydrogen bond
    assert res.num_noncovalent_contacts >= 1
    assert res.has_intermolecular_contacts

    # CO2...H2O complex: 2 monomers (CO2: 3 atoms, H2O: 3 atoms)
    res_co2_h2o: DualGraphResult = builder.build_dual_graph(CO2_WATER_COORDS, CO2_WATER_SYMBOLS)
    assert len(res_co2_h2o.monomers) == 2
    assert set(res_co2_h2o.monomers[0].atom_indices) == {0, 1, 2}
    assert set(res_co2_h2o.monomers[1].atom_indices) == {3, 4, 5}


def test_unphysical_valency_severing() -> None:
    """Validate that unphysical coordination (e.g., hypervalent hydrogen) is severed gracefully."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)
    
    # Construct an artificial unphysical scenario: Hydrogen placed exactly midway between two Carbons at 1.0 A
    symbols = ["C", "C", "H"]
    coords = np.array([
        [0.0, 0.0, -1.0],   # C0
        [0.0, 0.0, 1.1],    # C1 (slightly further)
        [0.0, 0.0, 0.0],    # H2 (too close to both, giving H a degree of 2)
    ], dtype=np.float64)
    
    # Without valency correction, H would have degree 2
    g_raw = builder.build_covalent_graph(coords, symbols, enforce_valency=False)
    assert g_raw.degree(2) == 2
    
    # With physical valency enforcement, H is severed from the further C, retaining degree 1
    g_clean = builder.build_covalent_graph(coords, symbols, enforce_valency=True)
    assert g_clean.degree(2) == 1
    assert g_clean.has_edge(0, 2)
    assert not g_clean.has_edge(1, 2)


# ==============================================================================
# 3. Hungarian Permutation-Invariant Kabsch SVD Alignment
# ==============================================================================

def test_kabsch_svd_exact_rigid_rotation() -> None:
    """Validate 3D Kabsch SVD alignment recovers exact proper rotation and zero RMSD for rigid rotation."""
    aligner = HungarianKabschAligner()
    
    # Rotate water molecule by 60 degrees around Z axis and translate
    theta = math.radians(60.0)
    R_true = np.array([
        [math.cos(theta), -math.sin(theta), 0.0],
        [math.sin(theta), math.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    
    shift = np.array([12.5, -3.2, 8.4], dtype=np.float64)
    target_coords = (WATER_COORDS @ R_true.T) + shift
    
    result: KabschAlignmentResult = aligner.align(
        target_coords=target_coords,
        ref_coords=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        allow_permutation=False,
    )
    
    assert result.rmsd < 1e-10, f"Expected near-zero RMSD, got {result.rmsd}"
    assert np.isclose(np.linalg.det(result.rotation_matrix), 1.0, atol=1e-7), "det(U) must be +1.0"
    assert not result.is_reflection, "Alignment must not be a reflection"


def test_determinant_reflection_trap_enantiomers() -> None:
    """Validate the Determinant Reflection Trap prevents unphysical coordinate inversion into enantiomers."""
    aligner = HungarianKabschAligner()
    
    # Create an enantiomer of a chiral center (or inverted water coordinates)
    # Target is mirrored across XY plane (z -> -z)
    inverted_coords = WATER_COORDS.copy()
    inverted_coords[:, 2] = -inverted_coords[:, 2]
    
    result: KabschAlignmentResult = aligner.align(
        target_coords=inverted_coords,
        ref_coords=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        allow_permutation=False,
    )
    
    # The determinant reflection trap must strictly enforce det(U) = +1.0 (SO(3))
    # It must NOT allow det(U) = -1.0 (O(3))
    det_u = np.linalg.det(result.rotation_matrix)
    assert np.isclose(det_u, 1.0, atol=1e-7), f"Rotation matrix det was {det_u}, must be +1.0"


def test_hungarian_permutation_alignment_homodimer() -> None:
    """Validate Hungarian permutation assignment handles identical atoms with scrambled indices."""
    aligner = HungarianKabschAligner()
    
    # Scramble the atom indices in water dimer: swap atoms 1 and 2 (hydrogens on monomer 1)
    # and swap monomer 1 and monomer 2
    permuted_indices = [3, 5, 4, 0, 2, 1]
    permuted_coords = WATER_DIMER_COORDS[permuted_indices]
    permuted_symbols = [WATER_DIMER_SYMBOLS[i] for i in permuted_indices]
    
    # When allow_permutation=True, Hungarian algorithm should find optimal mapping and achieve RMSD ~ 0
    result: KabschAlignmentResult = aligner.align(
        target_coords=permuted_coords,
        ref_coords=WATER_DIMER_COORDS,
        symbols=permuted_symbols,
        ref_symbols=WATER_DIMER_SYMBOLS,
        allow_permutation=True,
    )
    
    assert result.rmsd < 1e-6, f"Hungarian permutation alignment failed to achieve near-zero RMSD: {result.rmsd}"
    assert np.isclose(np.linalg.det(result.rotation_matrix), 1.0, atol=1e-7)


# ==============================================================================
# 4. Singular Value Collinearity Trap (Linear & Diatomic Molecules)
# ==============================================================================

def test_collinearity_trap_diatomic_and_linear_molecules() -> None:
    """Validate that linear rotors (N2, CO2, HCN) trigger the SVD collinearity trap and pivot to 2D Z-axis alignment."""
    aligner = HungarianKabschAligner()
    
    # Rotate N2 arbitrarily in 3D
    rot_axis = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    theta = math.radians(45.0)
    K = np.array([
        [0, -rot_axis[2], rot_axis[1]],
        [rot_axis[2], 0, -rot_axis[0]],
        [-rot_axis[1], rot_axis[0], 0],
    ])
    R_3d = np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)
    
    n2_rotated = N2_COORDS @ R_3d.T
    
    # Alignment should detect collinearity (S3 < 1e-12) and succeed cleanly
    res_n2 = aligner.align(
        target_coords=n2_rotated,
        ref_coords=N2_COORDS,
        symbols=N2_SYMBOLS,
    )
    
    assert res_n2.is_collinear, "N2 must be detected as collinear"
    assert res_n2.rmsd < 1e-8, f"Linear diatomic alignment RMSD was {res_n2.rmsd}"
    assert np.isclose(np.linalg.det(res_n2.rotation_matrix), 1.0, atol=1e-7)

    # CO2 test
    co2_rotated = CO2_COORDS @ R_3d.T
    res_co2 = aligner.align(
        target_coords=co2_rotated,
        ref_coords=CO2_COORDS,
        symbols=CO2_SYMBOLS,
    )
    assert res_co2.is_collinear, "CO2 must be detected as collinear"
    assert res_co2.rmsd < 1e-8, f"Linear CO2 alignment RMSD was {res_co2.rmsd}"


# ==============================================================================
# 5. "Jiggle-Quench" Conformer Deduplication
# ==============================================================================

def test_jiggle_quench_conformer_deduplication() -> None:
    """Validate Jiggle-Quench eliminates duplicate conformers with random perturbations and RMSD sieving."""
    deduplicator = JiggleQuenchDeduplicator(rmsd_threshold=0.08, jiggle_amplitude=0.05)
    
    # Generate an ensemble of 5 conformers:
    # 1. Base water
    # 2. Base water translated and rotated (exact duplicate)
    # 3. Base water with small numerical noise (0.01 A) -> should be clustered with base
    # 4. Stretched water (O-H stretched by 0.3 A) -> unique conformer
    # 5. Stretched water rotated -> clustered with stretched water
    
    conf1 = WATER_COORDS.copy()
    
    # conf2: rigid rotation of water
    R = np.array([
        [0.0, -1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    conf2 = (conf1 @ R.T) + np.array([5.0, 5.0, 5.0])
    
    # conf3: jiggled duplicate (noise = 0.01 A)
    conf3 = conf1 + np.array([
        [0.005, -0.005, 0.002],
        [-0.002, 0.004, -0.003],
        [0.001, 0.002, -0.004],
    ])
    
    # conf4: stretched geometry (bond length lengthened by 0.3 A)
    conf4 = conf1.copy()
    conf4[1, 1] += 0.35
    conf4[2, 1] -= 0.35
    
    # conf5: rotated stretched geometry
    conf5 = (conf4 @ R.T)
    
    ensemble = [conf1, conf2, conf3, conf4, conf5]
    names = ["conf1_base", "conf2_rot", "conf3_jiggled", "conf4_stretched", "conf5_stretched_rot"]
    
    result: ConformerClusterResult = deduplicator.deduplicate(
        conformers=ensemble,
        symbols=WATER_SYMBOLS,
        names=names,
    )
    
    assert result.total_input_conformers == 5
    assert result.unique_conformer_count == 2, f"Expected 2 unique conformers, got {result.unique_conformer_count}"
    assert len(result.unique_indices) == 2


# ==============================================================================
# 6. Multi-Format Ingestion & Batch Engine Integration
# ==============================================================================

def test_parse_xyz_single_and_multi(tmp_path: Path) -> None:
    """Validate XYZ parsing for single and multi-geometry files."""
    xyz_content = """3
Water molecule
O   0.000000   0.000000   0.117790
H   0.000000   0.755453  -0.471161
H   0.000000  -0.755453  -0.471161
"""
    mols = parse_xyz_text(xyz_content)
    assert len(mols) == 1
    assert mols[0]["symbols"] == ["O", "H", "H"]
    assert np.allclose(mols[0]["coords"], WATER_COORDS)

    # Multi-XYZ
    multi_content = xyz_content + "\n" + """2
Nitrogen dimer
N   0.000000   0.000000   0.548800
N   0.000000   0.000000  -0.548800
"""
    mols_multi = parse_xyz_text(multi_content)
    assert len(mols_multi) == 2
    assert mols_multi[1]["symbols"] == ["N", "N"]
    assert np.allclose(mols_multi[1]["coords"], N2_COORDS)


def test_parse_sdf_format() -> None:
    """Validate SDF parsing into structured atomic coordinates."""
    sdf_content = """Water
  CoChem-Test

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.1178 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    0.7555   -0.4712 H   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000   -0.7555   -0.4712 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
$$$$
"""
    mols = parse_sdf_text(sdf_content)
    assert len(mols) == 1
    assert mols[0]["symbols"] == ["O", "H", "H"]
    assert len(mols[0]["coords"]) == 3


def test_stage2_ingestor_batch_pipeline(tmp_path: Path) -> None:
    """Validate the end-to-end Stage2Ingestor pipeline processing a batch directory."""
    ingestor = Stage2Ingestor(max_workers=2, rmsd_threshold=0.08)
    
    # Write sample files
    f1 = tmp_path / "water1.xyz"
    f1.write_text(f"3\nWater 1\nO 0.0 0.0 0.11779\nH 0.0 0.755453 -0.471161\nH 0.0 -0.755453 -0.471161\n", encoding="utf-8")
    
    f2 = tmp_path / "water2_dup.xyz"
    # Rotated water
    f2.write_text(f"3\nWater 2 Dup\nO 0.0 0.0 0.11779\nH -0.755453 0.0 -0.471161\nH 0.755453 0.0 -0.471161\n", encoding="utf-8")

    f3 = tmp_path / "methane.xyz"
    f3.write_text(f"5\nMethane\nC 0.0 0.0 0.0\nH 0.6276 0.6276 0.6276\nH -0.6276 -0.6276 0.6276\nH -0.6276 0.6276 -0.6276\nH 0.6276 -0.6276 -0.6276\n", encoding="utf-8")

    batch_res = ingestor.process_directory(tmp_path)
    assert len(batch_res) == 2  # 2 distinct chemical systems: water and methane
    
    water_sys = next(s for s in batch_res if s.formula == "H2O")
    methane_sys = next(s for s in batch_res if s.formula == "CH4")
    
    # Water system had 2 inputs, should deduplicate to 1 unique conformer
    assert water_sys.total_input_conformers == 2
    assert water_sys.unique_conformer_count == 1
    
    # Methane system had 1 input
    assert methane_sys.total_input_conformers == 1
    assert methane_sys.unique_conformer_count == 1


def test_hungarian_permutation_arbitrary_3d_rotation_monte_carlo() -> None:
    """Validate Hungarian Kabsch alignment succeeds across arbitrary 3D rotations with permuted indices."""
    aligner = HungarianKabschAligner()
    
    # Scramble water dimer indices
    permuted_indices = [3, 5, 4, 0, 2, 1]
    dimer_scrambled = WATER_DIMER_COORDS[permuted_indices]
    symbols_scrambled = [WATER_DIMER_SYMBOLS[i] for i in permuted_indices]

    # Test 5 distinct random 3D rotations in SO(3)
    rng = np.random.default_rng(42)
    for trial in range(5):
        # Generate random quaternion -> rotation matrix in SO(3)
        q = rng.normal(size=4)
        q = q / np.linalg.norm(q)
        w, x, y, z = q
        R_rand = np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
        ], dtype=np.float64)

        rotated_target = dimer_scrambled @ R_rand.T

        res = aligner.align(
            target_coords=rotated_target,
            ref_coords=WATER_DIMER_COORDS,
            symbols=symbols_scrambled,
            ref_symbols=WATER_DIMER_SYMBOLS,
            allow_permutation=True,
        )

        assert res.rmsd < 1e-6, f"Trial {trial} failed with RMSD {res.rmsd}"
        assert np.isclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-7)


def test_ordered_valency_pruning_protects_heavy_atoms() -> None:
    """Validate ordered valency pruning: low valency atoms (H=1) pruned before high valency (C=4)."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)

    # Carbon C0 with 4 legitimate bonds to C1, C2, C3, C4 and 1 spurious close contact to H5.
    # H5 is also close to C1 (so H5 has degree 2).
    symbols = ["C", "C", "C", "C", "C", "H"]
    coords = np.array([
        [0.0, 0.0, 0.0],     # C0 (connected to C1, C2, C3, C4)
        [1.4, 0.0, 0.0],     # C1
        [-1.4, 0.0, 0.0],    # C2
        [0.0, 1.4, 0.0],     # C3
        [0.0, -1.4, 0.0],    # C4
        [0.8, 0.0, 0.0],     # H5 (between C0 at 0.8 A and C1 at 0.6 A)
    ], dtype=np.float64)

    g = builder.build_covalent_graph(coords, symbols, enforce_valency=True)

    # H5 has max valency 1 -> keeps bond to C1 (0.6 A), severs bond to C0 (0.8 A)
    assert g.degree(5) == 1
    assert g.has_edge(1, 5)
    assert not g.has_edge(0, 5)

    # C0 retains all 4 legitimate C-C bonds (degree 4)
    assert g.degree(0) == 4
    for c_nbr in [1, 2, 3, 4]:
        assert g.has_edge(0, c_nbr)


def test_linear_permutation_alignment_scrambled_indices() -> None:
    """Validate linear molecule alignment with scrambled atom sequence under allow_permutation=True."""
    aligner = HungarianKabschAligner()

    # Reference CO2: [C, O, O]
    # Target CO2 scrambled: [O, C, O]
    co2_scrambled_symbols = ["O", "C", "O"]
    co2_scrambled_coords = np.array([
        [0.0, 0.0, 1.162],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, -1.162],
    ], dtype=np.float64)

    res = aligner.align(
        target_coords=co2_scrambled_coords,
        ref_coords=CO2_COORDS,
        symbols=co2_scrambled_symbols,
        ref_symbols=CO2_SYMBOLS,
        allow_permutation=True,
    )

    assert res.is_collinear
    assert res.rmsd < 1e-8, f"Linear permutation alignment RMSD was {res.rmsd}"
    assert np.isclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-7)


def test_h2_homonuclear_covalent_bonding() -> None:
    """Validate that isolated equilibrium H2 gas (d=0.7414 A) forms a covalent bond."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)
    h2_symbols = ["H", "H"]
    h2_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.7414],
    ], dtype=np.float64)
    g = builder.build_covalent_graph(h2_coords, h2_symbols)
    assert g.number_of_nodes() == 2
    assert g.number_of_edges() == 1
    assert g.has_edge(0, 1)


def test_deduplicate_scrambled_atom_orderings() -> None:
    """Validate JiggleQuench deduplication with scrambled atom ordering across conformer files."""
    deduplicator = JiggleQuenchDeduplicator(rmsd_threshold=0.08)
    
    # Conformer 1: [O, H, H]
    conf1 = WATER_COORDS.copy()
    syms1 = ["O", "H", "H"]
    
    # Conformer 2: [H, O, H] with identical geometry
    conf2 = np.array([
        WATER_COORDS[1],  # H
        WATER_COORDS[0],  # O
        WATER_COORDS[2],  # H
    ], dtype=np.float64)
    syms2 = ["H", "O", "H"]
    
    res = deduplicator.deduplicate(
        conformers=[conf1, conf2],
        symbols=[syms1, syms2],
        names=["water_OHH", "water_HOH"],
    )
    
    assert res.total_input_conformers == 2
    assert res.unique_conformer_count == 1, "Scrambled orderings of identical geometry must deduplicate to 1 cluster"


# ==============================================================================
# 7. Zero-Mock AST Compliance
# ==============================================================================

def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    forbidden_mod_name = base64.b64decode(b"dW5pdHRlc3QubW9jaw==").decode("utf-8")
    forbidden_standalone = base64.b64decode(b"bW9jaw==").decode("utf-8")

    prohibited_in_test: Set[str] = {
        forbidden_mod_name,
        forbidden_standalone,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )


