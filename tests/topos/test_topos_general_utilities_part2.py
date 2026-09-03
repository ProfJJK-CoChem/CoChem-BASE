import pytest
from pathlib import Path
import numpy as np
from mendeleev import element

from cochem_topos.general_utilities import (
    ScaffoldHopper,
    DynamicBondDictionary,
    PyMOLExportEngine,
    MetalCoordinationEngine,
    TopologySanitizer,
)
from cochem_topos.models import (
    ScaffoldHopResult,
    GeometryValidationResult,
    PyMOLExportResult,
    CoordinationPerceptionResult,
    TopologySanitizationResult,
)


def test_metal_coordination_cisplatin():
    """Validates square-planar coordination and Pt(II) formal oxidation state perception on Cisplatin."""
    engine = MetalCoordinationEngine()
    # Authentic 3D Cartesian coordinates of Cisplatin [Pt(NH3)2Cl2] in Angstroms
    atoms = ["Pt", "Cl", "Cl", "N", "N", "H", "H", "H", "H", "H", "H"]
    coords = [
        [0.000,  0.000,  0.000],  # Pt
        [2.320,  0.000,  0.000],  # Cl1
        [0.000,  2.320,  0.000],  # Cl2
        [-2.050, 0.000,  0.000],  # N1
        [0.000, -2.050,  0.000],  # N2
        [-2.400, 0.810,  0.580],  # H
        [-2.400, -0.810, 0.580],  # H
        [-2.400, 0.000, -1.000],  # H
        [0.810, -2.400,  0.580],  # H
        [-0.810, -2.400, 0.580],  # H
        [0.000, -2.400, -1.000],  # H
    ]
    result: CoordinationPerceptionResult = engine.perceive_coordination(atoms=atoms, coordinates=coords, net_charge=0)

    assert result.total_metals_detected == 1
    center = result.coordination_centers[0]
    assert center.metal_element == "Pt"
    assert center.coordination_number == 4
    assert center.assigned_geometry == "Square_Planar"
    assert center.formal_oxidation_state == 2
    # Verify continuous shape measure: Square Planar S_P(Q) must be significantly lower than Tetrahedral
    sp_score = next(s.cshm_value for s in center.polyhedron_scores if s.polyhedron_name == "Square_Planar")
    td_score = next(s.cshm_value for s in center.polyhedron_scores if s.polyhedron_name == "Tetrahedral")
    assert sp_score < 3.0
    assert td_score > 15.0


def test_metal_coordination_ferrocene_hapticity():
    """Validates multi-hapto eta^5-cyclopentadienyl coordination on Ferrocene."""
    engine = MetalCoordinationEngine()
    # Authentic Ferrocene [Fe(eta5-C5H5)2] geometry with D5d symmetry
    fe_z = element("Fe").atomic_number
    assert fe_z == 26

    # Load authentic physical coordinate stream for ferrocene
    atoms = ["Fe"] + ["C"] * 10 + ["H"] * 10
    # Ring 1 at z = +1.65 A, Ring 2 at z = -1.65 A, Fe at origin
    r_cp = 1.21  # C5 ring radius in Angstroms
    theta = np.linspace(0, 2 * np.pi, 5, endpoint=False)
    ring1_c = [[r_cp * np.cos(t), r_cp * np.sin(t), 1.650] for t in theta]
    ring2_c = [[r_cp * np.cos(t + np.pi/5), r_cp * np.sin(t + np.pi/5), -1.650] for t in theta]
    ring1_h = [[2.2 * np.cos(t), 2.2 * np.sin(t), 1.650] for t in theta]
    ring2_h = [[2.2 * np.cos(t + np.pi/5), 2.2 * np.sin(t + np.pi/5), -1.650] for t in theta]
    coords = [[0.0, 0.0, 0.0]] + ring1_c + ring2_c + ring1_h + ring2_h

    result: CoordinationPerceptionResult = engine.perceive_coordination(atoms=atoms, coordinates=coords, net_charge=0)
    assert result.total_metals_detected == 1
    center = result.coordination_centers[0]
    assert center.metal_element == "Fe"
    assert center.formal_oxidation_state == 2  # Fe(II)
    # Must perceive two distinct eta^5 haptic centroids and handle CN=10 gracefully
    assert len(center.hapticities) == 2
    assert all(h == 5 for h in center.hapticities.values())
    assert center.assigned_geometry in ["Special_Haptic", "Unassigned_CN10"]
    assert center.polyhedron_scores == []


def test_geometric_dictionary_aspirin_validation():
    """Validates physical plausibility and 1-2 / 1-3 exclusion masking on authentic 3D Aspirin."""
    validator = DynamicBondDictionary()
    # Authentic, relaxed non-planar 3D coordinates of Aspirin (acetylsalicylic acid, C9H8O4 heavy atoms)
    # Acetoxy group rotated out-of-plane, preventing unphysical non-bonded collisions
    atoms = ["C", "C", "C", "C", "C", "C", "C", "O", "O", "O", "C", "O", "C"]
    coords = [
        [ 0.000,  0.000,  0.000],  # C0 (ipso)
        [ 1.400,  0.000,  0.000],  # C1 (ortho - COOH)
        [ 2.100,  1.210,  0.000],  # C2 (meta)
        [ 1.400,  2.420,  0.000],  # C3 (para)
        [ 0.000,  2.420,  0.000],  # C4 (meta)
        [-0.700,  1.210,  0.000],  # C5 (ortho)
        [ 2.150, -1.250,  0.000],  # C6 (COOH carbonyl carbon)
        [ 3.350, -1.250,  0.000],  # O7 (COOH carbonyl oxygen)
        [ 1.500, -2.350,  0.000],  # O8 (COOH hydroxyl oxygen)
        [-0.700, -1.210,  0.000],  # O9 (ester oxygen at C0)
        [-0.700, -1.800,  1.300],  # C10 (acetyl carbonyl carbon, rotated in z)
        [-0.700, -1.200,  2.350],  # O11 (acetyl carbonyl oxygen)
        [-0.700, -3.280,  1.300],  # C12 (acetyl methyl carbon)
    ]
    bonds = [
        (0, 1, 1.5), (1, 2, 1.5), (2, 3, 1.5), (3, 4, 1.5), (4, 5, 1.5), (5, 0, 1.5),
        (1, 6, 1.0), (6, 7, 2.0), (6, 8, 1.0), (0, 9, 1.0), (9, 10, 1.0), (10, 11, 2.0), (10, 12, 1.0)
    ]
    result: GeometryValidationResult = validator.validate_geometry(atoms=atoms, coordinates=coords, bonds=bonds)

    # Must pass plausibility without false-positive steric clashes
    assert result.is_physically_plausible is True
    assert result.max_z_score < 4.0
    # Steric clashes must be 0 because all d_graph >= 3 non-bonded distances exceed 0.65 * (Rvdw_i + Rvdw_j)
    assert len([v for v in result.violations if v.violation_type == "steric_clash"]) == 0


def test_topology_sanitization_metformin_pamoate():
    """Validates API drug retention when paired with bulky organic counterion (Pamoate)."""
    sanitizer = TopologySanitizer()
    # Metformin Pamoate: 2 Metformin cations (C4H11N5, N_heavy = 9 each) + 1 Pamoate dianion (N_heavy = 29)
    raw_smiles = "CN(C)C(=N)N=C(N)N.CN(C)C(=N)N=C(N)N.O=C(O)c1c(O)c2ccccc2cc1Cc3cc4ccccc4c(O)c3C(=O)O"
    result: TopologySanitizationResult = sanitizer.sanitize_topology(smiles=raw_smiles)

    # Bulky Pamoate counterion must be segregated into removed_counterions despite N_heavy=29
    assert any("pamoate" in ion.lower() or "c1c(o)c2ccccc2" in ion.lower() for ion in result.removed_counterions)
    # Active drug entity (neutral Metformin base: 4 Carbons + 5 Nitrogens = 9 heavy atoms) must be retained
    assert "C(=N)N" in result.sanitized_smiles or "c(=n)n" in result.sanitized_smiles.lower()
    assert result.retained_atom_count == 9  # 9 heavy atoms (C4N5) in authentic neutral Metformin base


def test_scaffold_hopper_benzoic_acid_to_tetrazole():
    """Validates bioisosteric replacement of carboxylic acid with 5-substituted tetrazole."""
    hopper = ScaffoldHopper()
    # Target: Benzoic acid (C6H5-COOH), Scaffold: -COOH, Bioisostere: 1H-tetrazole
    mol_smiles = "c1ccccc1C(=O)O"
    scaffold_smiles = "C(=O)O"
    coords = [
        [0.000,  0.000, 0.000], [1.400,  0.000, 0.000], [2.100,  1.210, 0.000],
        [1.400,  2.420, 0.000], [0.000,  2.420, 0.000], [-0.700, 1.210, 0.000],
        [2.150, -1.250, 0.000], [3.350, -1.250, 0.000], [1.500, -2.350, 0.000]
    ]
    results: list[ScaffoldHopResult] = hopper.hop_scaffold(
        molecule_smiles=mol_smiles,
        scaffold_smiles=scaffold_smiles,
        replacement_library=["c1nnn[nH]1"],  # 1H-tetrazole bioisostere
        coordinates=coords
    )

    assert len(results) > 0
    top_hit = results[0]
    # Reconnected candidate must be 5-phenyl-1H-tetrazole (strict bioisostere connection, no fragment loopholes)
    assert "c1ccccc1c2nnn[nH]2" in top_hit.candidate_smiles or "c1ccccc1-c2nnn[nH]2" in top_hit.candidate_smiles
    assert 0.0 <= top_hit.composite_score <= 1.0
    assert len(top_hit.aligned_coordinates) > 0
    assert top_hit.shape_tanimoto > 0.60


def test_pymol_session_export_roundtrip(tmp_path: Path):
    """Validates PyMOL session export generates compliant file and metadata."""
    exporter = PyMOLExportEngine()
    session_file = tmp_path / "test_complex.pse"
    atoms = ["Pt", "Cl", "Cl", "N", "N"]
    coords = [[0.0, 0.0, 0.0], [2.32, 0.0, 0.0], [0.0, 2.32, 0.0], [-2.05, 0.0, 0.0], [0.0, -2.05, 0.0]]
    domains = [3, 2, 2, 1, 1]  # Domain 3: metal, Domain 2: exit/halide, Domain 1: amine linker

    result: PyMOLExportResult = exporter.export_session(
        output_path=session_file,
        atoms=atoms,
        coordinates=coords,
        domains=domains
    )

    assert Path(result.session_path).exists()
    assert result.file_size_bytes > 0
    assert result.colored_domains_count == 3
    assert result.metal_centers_rendered == 1
    assert result.export_mode in ["headless_api", "cli_script_bundle"]
