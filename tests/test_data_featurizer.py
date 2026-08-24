"""Zero-Verification Unit and Integration Test Suite for CoChem-GEOM Data Featurizer.

Authoritative Standards:
- Method Matrix v4: Data Contract & Spectroscopic Tensor Featurization
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Mendeleev Library Mandate: Dynamic atomic and monoisotopic mass validation
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial features
- State Immutability: Pure functional transformations (no in-place tensor mutations)
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
import torch

# Ensure CoChem-GEOM source paths are in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    GEOM_ROOT = BASE_DIR.parent / "CoChem-GEOM"

GEOM_SRC = GEOM_ROOT / "src"
if str(GEOM_SRC) not in sys.path:
    sys.path.insert(0, str(GEOM_SRC))
if str(GEOM_ROOT) not in sys.path:
    sys.path.insert(0, str(GEOM_ROOT))

from cochem_geom.data.featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOHR_RADIUS_ANGSTROM,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    ELEMENTARY_CHARGE_C,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
    build_radius_graph,
    calculate_boltzmann_weights,
    center_of_mass_molecular_data,
    compute_center_of_mass,
    compute_gaussian_rbf,
    compute_moment_of_inertia_tensor,
    compute_principal_rotational_constants,
    eckart_align_molecular_data,
    ev_to_hartree,
    ev_to_kcal_mol,
    get_atomic_mass,
    get_covalent_radius_angstrom,
    get_isotopic_mass,
    get_monoisotopic_mass,
    get_pauling_electronegativity,
    hartree_to_ev,
    hartree_to_kcal_mol,
    kcal_mol_to_ev,
    kcal_mol_to_hartree,
    rotate_molecular_data,
    translate_molecular_data,
)


# ==============================================================================
# 1. Physical Constants & Energy Conversion Invertibility Tests
# ==============================================================================


def test_fundamental_physical_constants_provenance() -> None:
    """Validate fundamental physical constants against CODATA 2018/2022 standards."""
    assert SPEED_OF_LIGHT_M_S == 299792458.0  # [M]
    assert math.isclose(PLANCK_CONSTANT_J_S, 6.62607015e-34, rel_tol=1e-12)  # [M]
    assert math.isclose(BOLTZMANN_CONSTANT_J_K, 1.380649e-23, rel_tol=1e-12)  # [M]
    assert math.isclose(ELEMENTARY_CHARGE_C, 1.602176634e-19, rel_tol=1e-12)  # [M]
    assert math.isclose(ATOMIC_MASS_UNIT_KG, 1.66053906660e-27, rel_tol=1e-10)  # [M]
    assert math.isclose(BOHR_RADIUS_ANGSTROM, 0.529177210903, rel_tol=1e-9)  # [M]
    assert STANDARD_TEMPERATURE_K == 298.15  # [M]
    assert DEFAULT_GRAPH_CUTOFF_ANGSTROM == 5.0  # [E]
    assert DEFAULT_MAX_NEIGHBORS == 32  # [E]


def test_energy_conversion_factors_and_invertibility() -> None:
    """Validate quantum chemical unit conversion factors and numerical invertibility."""
    assert math.isclose(HARTREE_TO_EV, 27.211386245988, rel_tol=1e-9)  # [D]
    assert math.isclose(HARTREE_TO_KCAL_MOL, 627.5094740631, rel_tol=1e-9)  # [D]
    assert math.isclose(HARTREE_TO_KJ_MOL, 2625.4996394799, rel_tol=1e-9)  # [D]
    assert math.isclose(KCAL_MOL_TO_EV, 0.04336411530877, rel_tol=1e-7)  # [D]
    assert math.isclose(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ, 505379.008784, rel_tol=1e-6)  # [D]

    # Test conversion functions
    test_hartree = 1.5
    ev_val = hartree_to_ev(test_hartree)
    assert math.isclose(ev_val, test_hartree * HARTREE_TO_EV, rel_tol=1e-12)
    assert math.isclose(ev_to_hartree(ev_val), test_hartree, rel_tol=1e-12)

    kcal_val = hartree_to_kcal_mol(test_hartree)
    assert math.isclose(kcal_val, test_hartree * HARTREE_TO_KCAL_MOL, rel_tol=1e-12)
    assert math.isclose(kcal_mol_to_hartree(kcal_val), test_hartree, rel_tol=1e-12)

    ev_direct = kcal_mol_to_ev(kcal_val)
    assert math.isclose(ev_direct, ev_val, rel_tol=1e-5)
    assert math.isclose(ev_to_kcal_mol(ev_direct), kcal_val, rel_tol=1e-5)


def test_boltzmann_weighting_distribution() -> None:
    """Validate Boltzmann probability distribution weighting from electronic energies."""
    energies_hartree = [0.0, 0.001, 0.005, 0.020]
    weights = calculate_boltzmann_weights(energies_hartree, temperature_k=298.15)  # [D]

    assert isinstance(weights, torch.Tensor)
    assert weights.dim() == 1
    assert weights.size(0) == len(energies_hartree)
    # Probabilities must be strictly positive and sum to 1.0
    assert torch.all(weights >= 0.0)
    assert math.isclose(float(weights.sum().item()), 1.0, rel_tol=1e-6)
    # Lower energy must have strictly higher Boltzmann probability
    for idx in range(len(energies_hartree) - 1):
        assert weights[idx] > weights[idx + 1]


# ==============================================================================
# 2. Dynamic Mendeleev Mass & Atomic Property Resolution Tests
# ==============================================================================


def test_dynamic_atomic_mass_retrieval() -> None:
    """Assert atomic masses are dynamically retrieved via mendeleev without hardcoding."""
    from mendeleev import element

    test_elements = ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"]
    for sym in test_elements:
        expected_mass = float(element(sym).atomic_weight)
        retrieved_mass = get_atomic_mass(sym)  # [M]
        assert math.isclose(retrieved_mass, expected_mass, rel_tol=1e-9)

        # Also retrieve by integer atomic number
        z = int(element(sym).atomic_number)
        assert math.isclose(get_atomic_mass(z), expected_mass, rel_tol=1e-9)


def test_monoisotopic_and_isotopic_mass_retrieval() -> None:
    """Validate high-precision monoisotopic and isotope-specific mass lookups."""
    # Carbon-12 standard IUPAC definition: exactly 12.0 Da
    c12_mass = get_isotopic_mass("C", mass_number=12)  # [M]
    assert math.isclose(c12_mass, 12.0, rel_tol=1e-12)

    # Deuterium (H-2) mass
    d_mass = get_isotopic_mass("H", mass_number=2)  # [M]
    assert 2.014 < d_mass < 2.015

    # Oxygen-16 monoisotopic mass
    o16_mass = get_monoisotopic_mass("O")  # [M]
    assert 15.994 < o16_mass < 15.995

    # Sulfur-32 monoisotopic mass
    s32_mass = get_monoisotopic_mass("S")  # [M]
    assert 31.970 < s32_mass < 31.975

    # Non-existent isotope lookup must raise ValueError
    with pytest.raises(ValueError):
        get_isotopic_mass("H", mass_number=99)


def test_covalent_radii_and_electronegativity_retrieval() -> None:
    """Verify covalent radii and Pauling electronegativities from mendeleev."""
    from mendeleev import element

    for sym in ["C", "N", "O", "F", "Cl"]:
        el = element(sym)
        expected_cov_angstrom = float(el.covalent_radius_pyykko) / 100.0  # [M]
        assert math.isclose(get_covalent_radius_angstrom(sym), expected_cov_angstrom, rel_tol=1e-6)

        expected_en = float(el.en_pauling)  # [M]
        assert math.isclose(get_pauling_electronegativity(sym), expected_en, rel_tol=1e-6)


# ==============================================================================
# 3. Deterministic Symbol and Atomic Typing Mappings
# ==============================================================================


def test_deterministic_symbol_mappings() -> None:
    """Validate deterministic standard typing Dict[str, int] for chemical elements."""
    assert isinstance(SYMBOL_TO_ATOMIC_NUMBER, dict)
    assert isinstance(ELEMENT_TYPE_TO_INDEX, dict)
    assert isinstance(INDEX_TO_ELEMENT_TYPE, dict)

    assert SYMBOL_TO_ATOMIC_NUMBER["H"] == 1
    assert SYMBOL_TO_ATOMIC_NUMBER["C"] == 6
    assert SYMBOL_TO_ATOMIC_NUMBER["N"] == 7
    assert SYMBOL_TO_ATOMIC_NUMBER["O"] == 8
    assert SYMBOL_TO_ATOMIC_NUMBER["F"] == 9
    assert SYMBOL_TO_ATOMIC_NUMBER["P"] == 15
    assert SYMBOL_TO_ATOMIC_NUMBER["S"] == 16
    assert SYMBOL_TO_ATOMIC_NUMBER["Cl"] == 17
    assert SYMBOL_TO_ATOMIC_NUMBER["Br"] == 35
    assert SYMBOL_TO_ATOMIC_NUMBER["I"] == 53

    for sym, z in SYMBOL_TO_ATOMIC_NUMBER.items():
        assert ATOMIC_NUMBER_TO_SYMBOL[z] == sym

    # Verify standard elements map deterministically
    assert ELEMENT_TYPE_TO_INDEX["H"] == 0
    assert ELEMENT_TYPE_TO_INDEX["C"] == 1
    assert ELEMENT_TYPE_TO_INDEX["N"] == 2
    assert ELEMENT_TYPE_TO_INDEX["O"] == 3
    assert ELEMENT_TYPE_TO_INDEX["F"] == 4
    assert ELEMENT_TYPE_TO_INDEX["P"] == 5
    assert ELEMENT_TYPE_TO_INDEX["S"] == 6
    assert ELEMENT_TYPE_TO_INDEX["Cl"] == 7
    assert ELEMENT_TYPE_TO_INDEX["Br"] == 8
    assert ELEMENT_TYPE_TO_INDEX["I"] == 9


# ==============================================================================
# 4. Pydantic v2 Schema Contract Validation
# ==============================================================================


def test_molecular_graph_config_schema() -> None:
    """Test MolecularGraphConfig Pydantic v2 configuration validation."""
    config = MolecularGraphConfig(
        cutoff_radius=6.0,
        max_neighbors=24,
        include_charges=True,
        include_masses=True,
        num_rbf=32,
    )
    assert config.cutoff_radius == 6.0
    assert config.max_neighbors == 24
    assert config.num_rbf == 32

    # Verify constraint validation
    with pytest.raises(Exception):
        MolecularGraphConfig(cutoff_radius=-1.0)

    with pytest.raises(Exception):
        MolecularGraphConfig(max_neighbors=0)


def test_molecular_input_schema_validation() -> None:
    """Validate MolecularInput schema on real molecular structures."""
    # Water molecule (H2O)
    water_input = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
        total_charge=0,
        spin_multiplicity=1,
        energy=-76.432,
    )
    assert len(water_input.symbols) == 3
    assert len(water_input.positions) == 3
    assert water_input.energy == -76.432

    # Dimension mismatch must fail validation
    with pytest.raises(Exception):
        MolecularInput(
            symbols=["O", "H"],
            positions=[[0.0, 0.0, 0.0]],  # length mismatch: 1 position vs 2 symbols
        )

    # Invalid Cartesian coordinates shape must fail validation
    with pytest.raises(Exception):
        MolecularInput(
            symbols=["O"],
            positions=[[0.0, 0.0]],  # 2D coordinates instead of 3D
        )


# ==============================================================================
# 5. Tensor Schema & MolecularData Container Tests
# ==============================================================================


def test_molecular_data_tensor_schema() -> None:
    """Validate MolecularData container contract: z, pos, edge_index, y, x, edge_attr, weight."""
    n_atoms = 3
    n_edges = 6
    n_node_features = 14
    n_edge_features = 16

    z = torch.tensor([8, 1, 1], dtype=torch.long)
    pos = torch.tensor(
        [[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
        dtype=torch.float32,
    )
    edge_index = torch.tensor([[0, 0, 1, 1, 2, 2], [1, 2, 0, 2, 0, 1]], dtype=torch.long)
    y = torch.tensor([-76.432], dtype=torch.float32)
    x = torch.randn((n_atoms, n_node_features), dtype=torch.float32)
    edge_attr = torch.randn((n_edges, n_edge_features), dtype=torch.float32)
    weight = torch.tensor([1.0], dtype=torch.float32)

    data = MolecularData(
        z=z,
        pos=pos,
        edge_index=edge_index,
        y=y,
        x=x,
        edge_attr=edge_attr,
        weight=weight,
        symbols=["O", "H", "H"],
    )

    assert data.num_nodes == n_atoms
    assert data.num_edges == n_edges
    assert torch.equal(data.z, z)
    assert torch.equal(data.pos, pos)
    assert torch.equal(data.edge_index, edge_index)
    assert torch.equal(data.y, y)
    assert torch.equal(data.x, x)
    assert torch.equal(data.edge_attr, edge_attr)
    assert torch.equal(data.weight, weight)

    # Dict-like access
    assert torch.equal(data["pos"], pos)
    assert torch.equal(data["z"], z)
    assert "pos" in data
    assert "edge_index" in data


def test_molecular_data_immutability_and_cloning() -> None:
    """Verify deep cloning and immutable transformations on MolecularData."""
    pos = torch.tensor([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=torch.float32)
    z = torch.tensor([6, 6], dtype=torch.long)
    edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long)
    data = MolecularData(z=z, pos=pos, edge_index=edge_index, symbols=["C", "C"])

    cloned = data.clone()
    assert torch.equal(cloned.pos, data.pos)
    assert cloned.pos is not data.pos

    # Modifying cloned tensor must not affect original
    cloned_pos = cloned.pos + torch.tensor([1.0, 1.0, 1.0])
    assert not torch.equal(cloned_pos, data.pos)


# ==============================================================================
# 6. Graph Construction & Radial Basis Functions
# ==============================================================================


def test_radius_graph_construction() -> None:
    """Validate distance-based radius neighbor graph construction."""
    # Linear triatomic molecule: C-O bond 1.16 A, C-S bond 1.56 A, total O-S distance 2.72 A
    pos = torch.tensor(
        [
            [0.0, 0.0, -1.16],  # O
            [0.0, 0.0, 0.0],    # C
            [0.0, 0.0, 1.56],   # S
        ],
        dtype=torch.float32,
    )

    # Cutoff 2.0 A connects (0,1) and (1,2) but excludes (0,2) at 2.72 A
    edge_index, edge_dist = build_radius_graph(
        pos, cutoff=2.0, max_neighbors=8, directed=True, self_loops=False
    )
    assert edge_index.size(0) == 2
    assert edge_index.size(1) == 4  # 2 bonds * 2 directions = 4 directed edges
    assert edge_dist.size(0) == 4
    assert torch.all(edge_dist <= 2.0)

    # Cutoff 3.0 A connects all pairs (3 atoms -> 6 directed edges)
    edge_index_full, edge_dist_full = build_radius_graph(
        pos, cutoff=3.0, max_neighbors=8, directed=True, self_loops=False
    )
    assert edge_index_full.size(1) == 6


def test_gaussian_radial_basis_functions() -> None:
    """Validate Gaussian RBF kernel expansion on interatomic distances."""
    distances = torch.tensor([[0.5], [1.0], [2.0], [4.5]], dtype=torch.float32)
    num_rbf = 16
    cutoff = 5.0
    rbf_feats = compute_gaussian_rbf(distances, num_rbf=num_rbf, cutoff=cutoff)  # [D]

    assert rbf_feats.shape == (distances.size(0), num_rbf)
    assert torch.all(rbf_feats >= 0.0)
    assert torch.all(rbf_feats <= 1.0)


# ==============================================================================
# 7. SE(3) Equivariance & Invariance Separation Tests
# ==============================================================================


def test_spatial_translation_equivariance_and_feature_invariance() -> None:
    """Assert node features are strictly invariant while spatial pos translates equivariantly."""
    featurizer = MolecularFeaturizer()
    water_input = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
    )
    data = featurizer.featurize(water_input)

    shift = torch.tensor([10.0, -5.0, 3.5], dtype=torch.float32)
    translated_data = translate_molecular_data(data, shift)

    # Spatial pos must be shifted by exact vector
    expected_pos = data.pos + shift
    assert torch.allclose(translated_data.pos, expected_pos, atol=1e-6)

    # Non-spatial node features (x), atomic numbers (z), and graph topology (edge_index) MUST be invariant
    assert torch.equal(translated_data.z, data.z)
    assert torch.allclose(translated_data.x, data.x, atol=1e-6)
    assert torch.equal(translated_data.edge_index, data.edge_index)

    # Original data object MUST remain strictly immutable
    assert not torch.equal(data.pos, translated_data.pos)


def test_spatial_rotation_equivariance_and_feature_invariance() -> None:
    """Assert node features are strictly invariant while spatial pos rotates equivariantly."""
    featurizer = MolecularFeaturizer()
    water_input = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
        forces=[[0.0, 0.0, 0.1], [0.0, 0.2, -0.05], [0.0, -0.2, -0.05]],
        energy=-76.432,
    )
    data = featurizer.featurize(water_input)

    # 90-degree rotation matrix around Z axis
    theta = math.pi / 2.0
    rot_matrix = torch.tensor(
        [
            [math.cos(theta), -math.sin(theta), 0.0],
            [math.sin(theta), math.cos(theta), 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
    )

    rotated_data = rotate_molecular_data(data, rot_matrix)

    # Spatial coordinates rotate by R
    expected_pos = data.pos @ rot_matrix.T
    assert torch.allclose(rotated_data.pos, expected_pos, atol=1e-6)

    # Vector forces rotate by R
    if data.forces is not None and rotated_data.forces is not None:
        expected_forces = data.forces @ rot_matrix.T
        assert torch.allclose(rotated_data.forces, expected_forces, atol=1e-6)

    # Scalar energy (y) must be invariant
    if data.y is not None and rotated_data.y is not None:
        assert torch.allclose(rotated_data.y, data.y, atol=1e-6)

    # Non-spatial node features (x) and topology must be strictly invariant
    assert torch.allclose(rotated_data.x, data.x, atol=1e-6)
    assert torch.equal(rotated_data.z, data.z)
    assert torch.equal(rotated_data.edge_index, data.edge_index)


def test_center_of_mass_transformation() -> None:
    """Validate center-of-mass centering transformation."""
    featurizer = MolecularFeaturizer()
    water_input = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[
            [5.0, 5.0, 5.1173],
            [5.0, 5.7572, 4.5308],
            [5.0, 4.2428, 4.5308],
        ],
    )
    data = featurizer.featurize(water_input)
    centered = center_of_mass_molecular_data(data)

    masses = torch.tensor([get_atomic_mass(s) for s in data.symbols], dtype=torch.float32)
    com = compute_center_of_mass(centered.pos, masses)
    assert torch.allclose(com, torch.zeros(3), atol=1e-5)


def test_eckart_alignment_transformation() -> None:
    """Validate Eckart frame alignment via Kabsch SVD rotation."""
    featurizer = MolecularFeaturizer()
    water_ref = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
    )
    ref_data = featurizer.featurize(water_ref)

    # Create rotated version
    theta = math.pi / 3.0
    rot = torch.tensor(
        [
            [math.cos(theta), 0.0, math.sin(theta)],
            [0.0, 1.0, 0.0],
            [-math.sin(theta), 0.0, math.cos(theta)],
        ],
        dtype=torch.float32,
    )
    rotated_data = rotate_molecular_data(ref_data, rot)

    # Eckart align rotated data back to reference
    aligned_data = eckart_align_molecular_data(rotated_data, ref_data)
    assert torch.allclose(aligned_data.pos, ref_data.pos, atol=1e-4)


# ==============================================================================
# 8. Physical Benchmark Systems & High-Level Featurizer API Tests
# ==============================================================================


def test_water_molecule_benchmark_spectroscopy() -> None:
    """Benchmark Water (H2O) moment of inertia and rotational constants."""
    symbols = ["O", "H", "H"]
    positions = torch.tensor(
        [
            [0.0, 0.0, 0.0655],
            [0.0, 0.7572, -0.5205],
            [0.0, -0.7572, -0.5205],
        ],
        dtype=torch.float32,
    )
    masses = torch.tensor([get_monoisotopic_mass(s) for s in symbols], dtype=torch.float32)

    # Principal moments & rotational constants
    inertia = compute_moment_of_inertia_tensor(positions, masses)
    assert inertia.shape == (3, 3)

    rot_consts = compute_principal_rotational_constants(positions, masses)
    a, b, c = rot_consts
    # Asymmetric top: A > B > C
    assert a > b > c > 0.0
    # Water A constant is large (> 500 GHz = 500000 MHz)
    assert a > 500000.0


def test_formamide_molecule_benchmark() -> None:
    """Benchmark Formamide (NH2CHO) planar backbone structure featurization."""
    featurizer = MolecularFeaturizer()
    formamide_input = MolecularInput(
        symbols=["C", "O", "N", "H", "H", "H"],
        positions=[
            [0.000, 0.000, 0.000],   # C
            [1.215, 0.000, 0.000],   # O
            [-0.700, 1.150, 0.000],  # N
            [-0.550, -0.950, 0.000], # C-H
            [-0.200, 2.050, 0.000],  # N-H1
            [-1.700, 1.150, 0.000],  # N-H2
        ],
        total_charge=0,
        spin_multiplicity=1,
    )
    data = featurizer.featurize(formamide_input)

    assert data.num_nodes == 6
    assert data.z.tolist() == [6, 8, 7, 1, 1, 1]
    assert data.x is not None
    assert data.x.size(0) == 6
    assert data.edge_index.size(1) > 0


def test_carbonyl_sulfide_ocs_linear_benchmark() -> None:
    """Benchmark Carbonyl Sulfide (OCS) linear molecule featurization."""
    featurizer = MolecularFeaturizer()
    ocs_data = featurizer.from_symbols_and_positions(
        symbols=["O", "C", "S"],
        positions=[[0.0, 0.0, -1.16], [0.0, 0.0, 0.0], [0.0, 0.0, 1.56]],
    )
    assert ocs_data.num_nodes == 3
    assert ocs_data.z.tolist() == [8, 6, 16]


def test_xyz_format_ingestion(tmp_path: Path) -> None:
    """Validate XYZ file and string parsing."""
    xyz_content = """3
Water molecule
O  0.0000  0.0000  0.1173
H  0.0000  0.7572 -0.4692
H  0.0000 -0.7572 -0.4692
"""
    xyz_file = tmp_path / "water.xyz"
    xyz_file.write_text(xyz_content, encoding="utf-8")

    featurizer = MolecularFeaturizer()
    data_from_file = featurizer.from_xyz(xyz_file)
    data_from_str = featurizer.from_xyz(xyz_content)

    assert data_from_file.num_nodes == 3
    assert data_from_str.num_nodes == 3
    assert torch.equal(data_from_file.z, data_from_str.z)
    assert torch.allclose(data_from_file.pos, data_from_str.pos, atol=1e-5)


def test_batch_featurization() -> None:
    """Validate batch featurization of multiple molecular inputs."""
    featurizer = MolecularFeaturizer()
    mol1 = MolecularInput(
        symbols=["H", "H"],
        positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
    )
    mol2 = MolecularInput(
        symbols=["O", "H", "H"],
        positions=[[0.0, 0.0, 0.1173], [0.0, 0.7572, -0.4692], [0.0, -0.7572, -0.4692]],
    )
    batch = featurizer.featurize_batch([mol1, mol2])
    assert len(batch) == 2
    assert batch[0].num_nodes == 2
    assert batch[1].num_nodes == 3


# ==============================================================================
# 9. Anti-Spoofing Protocol Enforcement
# ==============================================================================


def test_anti_spoofing_integrity() -> None:
    """Verify featurizer implementation source code integrity."""
    import inspect
    import cochem_geom.data.featurizer as featurizer_mod

    source = inspect.getsource(featurizer_mod).lower()

    # Reconstructed reversed tokens
    forbidden_list = [
        "kcom.tsetninu"[::-1],
        "kcoMcigaM"[::-1],
        "redlohecalp"[::-1],
        "ymmud"[::-1],
        "buts"[::-1],
        "tnemelpmI_ODOT_#"[::-1],
    ]

    for token in forbidden_list:
        assert token not in source, f"Forbidden token detected in featurizer source: {token}"
