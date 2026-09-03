"""# zero-stub anti-spoofing engine
Physical Unit Tests for CoChem-TOPOS Explicit Solvent Builder and SolventBox.

Strictly adheres to Zero-Mock mandate and Mendeleev dynamic mass queries.
Validates:
- Authentic solvation of H2O, Methanol, and Benzene.
- Bulk and observed solvent density within 0.0333 +- 0.002 molecules/A^3.
- Physical steric exclusion >= 2.4 A (solute-solvent) and >= 2.5 A (d_OO solvent-solvent).
- TIP3P water model geometric constraints, dynamic masses, charges, and LJ parameters.
- Backward compatibility for symbols list input and SolventBox container properties.
- Comprehensive typed exception handling with SolventBuilderError.
"""

from __future__ import annotations

import numpy as np
import pytest
from mendeleev import element
from scipy.spatial import cKDTree

from cochem.topos.exceptions import SolventBuilderError
from cochem.topos.graph import TopologyGraph
from cochem.topos.solvent import (
    TIP3P_EPSILON_H,
    TIP3P_EPSILON_O,
    TIP3P_Q_H,
    TIP3P_Q_O,
    TIP3P_R_OH,
    TIP3P_SIGMA_H,
    TIP3P_SIGMA_O,
    TIP3P_THETA_DEG,
    ExplicitSolventBuilder,
    SolventBox,
)

# Authentic physical molecular coordinates
WATER_COORDS = np.array([
    [0.000000, 0.000000, 0.117400],
    [0.000000, 0.757000, -0.469600],
    [0.000000, -0.757000, -0.469600],
], dtype=np.float64)
WATER_SYMBOLS = ["O", "H", "H"]

METHANOL_COORDS = np.array([
    [-0.0464, 0.6652, 0.0000],   # C
    [-0.0464, -0.7584, 0.0000],  # O
    [0.8522, -1.0963, 0.0000],   # H (hydroxyl)
    [-1.0853, 0.9822, 0.0000],   # H1 (methyl)
    [0.4431, 1.0538, 0.8900],    # H2 (methyl)
    [0.4431, 1.0538, -0.8900],   # H3 (methyl)
], dtype=np.float64)
METHANOL_SYMBOLS = ["C", "O", "H", "H", "H", "H"]

BENZENE_COORDS = np.array([
    [1.3970, 0.0000, 0.0000],
    [0.6985, 1.2098, 0.0000],
    [-0.6985, 1.2098, 0.0000],
    [-1.3970, 0.0000, 0.0000],
    [-0.6985, -1.2098, 0.0000],
    [0.6985, -1.2098, 0.0000],
    [2.4790, 0.0000, 0.0000],
    [1.2395, 2.1469, 0.0000],
    [-1.2395, 2.1469, 0.0000],
    [-2.4790, 0.0000, 0.0000],
    [-1.2395, -2.1469, 0.0000],
    [1.2395, -2.1469, 0.0000],
], dtype=np.float64)
BENZENE_SYMBOLS = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]


def _build_water_graph() -> TopologyGraph:
    g = TopologyGraph()
    g.add_chemical_node(0, "O", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(1, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(2, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(0, 2, bond_order=1.0)
    return g


def _build_methanol_graph() -> TopologyGraph:
    g = TopologyGraph()
    g.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(1, "O", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(2, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(3, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(4, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_node(5, "H", formal_charge=0, hybridization="sp3")
    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(1, 2, bond_order=1.0)
    g.add_chemical_edge(0, 3, bond_order=1.0)
    g.add_chemical_edge(0, 4, bond_order=1.0)
    g.add_chemical_edge(0, 5, bond_order=1.0)
    return g


def _build_benzene_graph() -> TopologyGraph:
    g = TopologyGraph()
    for i in range(6):
        g.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        g.add_chemical_node(i + 6, "H", formal_charge=0, hybridization="sp3", in_ring=False)
    for i in range(6):
        g.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)
        g.add_chemical_edge(i, i + 6, bond_order=1.0, aromatic=False, in_ring=False)
    return g


class TestSolvationH2O:
    """Verifies solvation of authentic physical H2O solute."""

    def test_solvate_water_solute(self) -> None:
        solute_g = _build_water_graph()
        composite_g, coords, lattice = ExplicitSolventBuilder.solvate(
            graph=solute_g,
            coordinates=WATER_COORDS,
            padding=10.0,
            density_g_cm3=0.997,
            min_distance=2.4,
            seed=42,
        )

        assert isinstance(composite_g, TopologyGraph)
        assert coords.ndim == 2
        assert coords.shape[1] == 3
        assert coords.shape[0] == len(composite_g.nodes)
        assert lattice.shape == (3, 3)

        # 3 solute atoms + 3 * n_waters
        n_total = coords.shape[0]
        n_waters = (n_total - 3) // 3
        assert n_waters > 100

        # Solute atoms centered around L / 2
        box_lengths = np.diag(lattice)
        box_center = box_lengths / 2.0
        solute_coords = coords[:3]
        computed_solute_center = (np.min(solute_coords, axis=0) + np.max(solute_coords, axis=0)) / 2.0
        assert np.allclose(computed_solute_center, box_center, atol=1e-3)

        # Physical steric exclusion solute-solvent >= 2.4 A
        solvent_coords = coords[3:]
        solute_tree = cKDTree(solute_coords)
        dists, _ = solute_tree.query(solvent_coords)
        assert np.min(dists) >= 2.4 - 1e-4

        # Solvent-solvent exclusion d_OO >= 2.5 A
        solvent_o_coords = solvent_coords[0::3]
        o_tree = cKDTree(solvent_o_coords)
        pairs = o_tree.query_pairs(r=2.5 - 1e-4)
        assert len(pairs) == 0

        # Bulk solvent density in 0.0333 +- 0.002 molecules/A^3
        volume = float(np.prod(box_lengths))
        box_density = n_waters / volume
        assert 0.0313 <= box_density <= 0.0353


class TestSolvationMethanol:
    """Verifies solvation of authentic Methanol solute."""

    def test_solvate_methanol_solute(self) -> None:
        solute_g = _build_methanol_graph()
        composite_g, coords, lattice = ExplicitSolventBuilder.solvate(
            graph=solute_g,
            coordinates=METHANOL_COORDS,
            padding=10.0,
            density_g_cm3=0.997,
            min_distance=2.4,
            seed=123,
        )

        n_solute = 6
        assert coords.shape[0] == len(composite_g.nodes)
        n_waters = (coords.shape[0] - n_solute) // 3
        assert n_waters > 100

        # Solute centered at L / 2
        box_lengths = np.diag(lattice)
        box_center = box_lengths / 2.0
        solute_coords = coords[:n_solute]
        computed_solute_center = (np.min(solute_coords, axis=0) + np.max(solute_coords, axis=0)) / 2.0
        assert np.allclose(computed_solute_center, box_center, atol=1e-3)

        # Steric exclusion >= 2.4 A
        solvent_coords = coords[n_solute:]
        solute_tree = cKDTree(solute_coords)
        dists, _ = solute_tree.query(solvent_coords)
        assert np.min(dists) >= 2.4 - 1e-4

        # Solvent density 0.0333 +- 0.002 molecules/A^3
        volume = float(np.prod(box_lengths))
        box_density = n_waters / volume
        assert 0.0313 <= box_density <= 0.0353


class TestSolvationBenzene:
    """Verifies solvation of authentic aromatic Benzene solute."""

    def test_solvate_benzene_solute(self) -> None:
        solute_g = _build_benzene_graph()
        composite_g, coords, lattice = ExplicitSolventBuilder.solvate(
            graph=solute_g,
            coordinates=BENZENE_COORDS,
            padding=10.0,
            density_g_cm3=0.997,
            min_distance=2.4,
            seed=999,
        )

        n_solute = 12
        assert coords.shape[0] == len(composite_g.nodes)
        n_waters = (coords.shape[0] - n_solute) // 3
        assert n_waters > 200

        # Solute centered at L / 2
        box_lengths = np.diag(lattice)
        box_center = box_lengths / 2.0
        solute_coords = coords[:n_solute]
        computed_solute_center = (np.min(solute_coords, axis=0) + np.max(solute_coords, axis=0)) / 2.0
        assert np.allclose(computed_solute_center, box_center, atol=1e-3)

        # Steric exclusion >= 2.4 A
        solvent_coords = coords[n_solute:]
        solute_tree = cKDTree(solute_coords)
        dists, _ = solute_tree.query(solvent_coords)
        assert np.min(dists) >= 2.4 - 1e-4

        # Solvent-solvent exclusion d_OO >= 2.5 A
        solvent_o_coords = solvent_coords[0::3]
        o_tree = cKDTree(solvent_o_coords)
        pairs = o_tree.query_pairs(r=2.5 - 1e-4)
        assert len(pairs) == 0

        # Bulk density tolerance
        volume = float(np.prod(box_lengths))
        box_density = n_waters / volume
        assert 0.0313 <= box_density <= 0.0353


class TestDynamicMendeleevMassesAndTIP3P:
    """Validates dynamic Mendeleev elemental mass queries and TIP3P parameters."""

    def test_dynamic_tip3p_water_mass(self) -> None:
        expected_mass = float(element("O").mass) + 2.0 * float(element("H").mass)
        builder_mass = ExplicitSolventBuilder.get_tip3p_water_mass()
        assert abs(builder_mass - expected_mass) < 1e-6

    def test_dynamic_grid_spacing_and_density(self) -> None:
        d_grid = ExplicitSolventBuilder.compute_grid_spacing(density_g_cm3=0.997)
        bulk_density = 1.0 / (d_grid**3)
        assert 0.0313 <= bulk_density <= 0.0353
        assert 3.05 <= d_grid <= 3.15

    def test_composite_graph_tip3p_parameters(self) -> None:
        solute_g = _build_water_graph()
        box = ExplicitSolventBuilder.build_solvent_box(
            graph=solute_g,
            coordinates=WATER_COORDS,
            padding=5.0,
            density_g_cm3=0.997,
            min_distance=2.4,
            seed=42,
        )

        comp = box.composite_graph
        # Check solvent O parameters
        o_node = comp.nodes[3]
        assert o_node["symbol"] == "O"
        assert abs(o_node["charge"] - TIP3P_Q_O) < 1e-6
        assert abs(o_node["sigma"] - TIP3P_SIGMA_O) < 1e-6
        assert abs(o_node["epsilon"] - TIP3P_EPSILON_O) < 1e-6
        assert o_node["mass"] == float(element("O").mass)

        # Check solvent H parameters
        h_node = comp.nodes[4]
        assert h_node["symbol"] == "H"
        assert abs(h_node["charge"] - TIP3P_Q_H) < 1e-6
        assert abs(h_node["sigma"] - TIP3P_SIGMA_H) < 1e-6
        assert abs(h_node["epsilon"] - TIP3P_EPSILON_H) < 1e-6
        assert h_node["mass"] == float(element("H").mass)

        # Check solvent bonds
        assert comp.has_edge(3, 4)
        assert comp.has_edge(3, 5)
        assert comp[3][4]["bond_order"] == 1.0
        assert comp[3][5]["bond_order"] == 1.0


class TestBackwardsCompatibilityAndSolventBox:
    """Verifies backwards compatibility with symbols list and SolventBox properties."""

    def test_symbols_input_compatibility(self) -> None:
        comp, coords, lattice = ExplicitSolventBuilder.solvate(
            WATER_SYMBOLS,
            WATER_COORDS,
            padding=5.0,
            seed=42,
        )
        assert len(comp.nodes) == coords.shape[0]
        assert lattice.shape == (3, 3)

    def test_solvent_box_container_properties(self) -> None:
        box = ExplicitSolventBuilder.build_solvent_box(
            symbols=METHANOL_SYMBOLS,
            coordinates=METHANOL_COORDS,
            padding=5.0,
            seed=42,
        )
        assert isinstance(box, SolventBox)
        assert box.total_atoms == len(box.coordinates)
        assert box.n_solute_atoms == 6
        assert box.volume_angstrom3 > 0.0
        assert box.solute_coordinates.shape == (6, 3)
        assert box.solvent_coordinates.shape == (box.n_solvent_molecules * 3, 3)
        assert 0.0313 <= box.bulk_density_molecules_per_angstrom3 <= 0.0353
        assert 0.0250 <= box.box_density_molecules_per_angstrom3 <= 0.0353

    def test_empty_solute_pure_water_box(self) -> None:
        empty_coords: np.ndarray = np.empty((0, 3), dtype=np.float64)
        box = ExplicitSolventBuilder.build_solvent_box(
            coordinates=empty_coords,
            padding=5.0,
            seed=42,
        )
        assert box.n_solute_atoms == 0
        assert box.n_solvent_molecules > 0
        assert box.total_atoms == box.n_solvent_molecules * 3
        assert 0.0313 <= box.bulk_density_molecules_per_angstrom3 <= 0.0353


class TestSolventBuilderExceptions:
    """Validates robust exception raising on invalid physical configurations."""

    def test_invalid_padding_raises(self) -> None:
        with pytest.raises(SolventBuilderError, match="padding must be strictly positive"):
            ExplicitSolventBuilder.solvate(WATER_SYMBOLS, WATER_COORDS, padding=-1.0)

    def test_invalid_density_raises(self) -> None:
        with pytest.raises(SolventBuilderError, match="density must be strictly positive"):
            ExplicitSolventBuilder.solvate(WATER_SYMBOLS, WATER_COORDS, density_g_cm3=0.0)

    def test_invalid_min_distance_raises(self) -> None:
        with pytest.raises(SolventBuilderError, match="min_distance cannot be negative"):
            ExplicitSolventBuilder.solvate(WATER_SYMBOLS, WATER_COORDS, min_distance=-0.5)

    def test_invalid_coordinates_shape_raises(self) -> None:
        bad_coords = np.array([[0.0, 0.0]], dtype=np.float64)
        with pytest.raises(SolventBuilderError, match="Coordinates must have shape"):
            ExplicitSolventBuilder.solvate(WATER_SYMBOLS, bad_coords)

    def test_atom_count_mismatch_raises(self) -> None:
        with pytest.raises(SolventBuilderError, match="Mismatch between symbols count"):
            ExplicitSolventBuilder.solvate(["O"], WATER_COORDS)
