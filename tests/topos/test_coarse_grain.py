"""Physical Unit Tests for CoChem-TOPOS Macromolecular Coarse-Graining (Graph Crusher).

Strictly adheres to Zero-Mock mandate and Mendeleev dynamic mass queries.
Operates on authentic peptide and macromolecular topologies.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest
from mendeleev import element

from cochem.topos.coarse_grain import GraphCrusherConfig, crush_macromolecule
from cochem.topos.exceptions import TopologyError
from cochem.topos.graph import TopologyGraph


def build_dialanine_topology() -> tuple[TopologyGraph, dict[int, int], np.ndarray]:
    """Constructs authentic dialanine (Ala-Ala) topology and coordinates.
    
    Residue 0 (Ala 1):
      0: N, 1: CA, 2: C, 3: O, 4: CB
    Residue 1 (Ala 2):
      5: N, 6: CA, 7: C, 8: O, 9: CB
    Peptide bond: (2, 5) connecting residue 0 and residue 1.
    """
    graph = TopologyGraph()
    # Residue 0
    graph.add_chemical_node(0, "N", formal_charge=0, hybridization="sp3")
    graph.add_chemical_node(1, "C", formal_charge=0, hybridization="sp3")
    graph.add_chemical_node(2, "C", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(3, "O", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(4, "C", formal_charge=0, hybridization="sp3")

    graph.add_chemical_edge(0, 1, bond_order=1.0)
    graph.add_chemical_edge(1, 2, bond_order=1.0)
    graph.add_chemical_edge(2, 3, bond_order=2.0)
    graph.add_chemical_edge(1, 4, bond_order=1.0)

    # Residue 1
    graph.add_chemical_node(5, "N", formal_charge=0, hybridization="sp3")
    graph.add_chemical_node(6, "C", formal_charge=0, hybridization="sp3")
    graph.add_chemical_node(7, "C", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(8, "O", formal_charge=-1, hybridization="sp2")
    graph.add_chemical_node(9, "C", formal_charge=0, hybridization="sp3")

    graph.add_chemical_edge(5, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=1.0)
    graph.add_chemical_edge(7, 8, bond_order=1.5)
    graph.add_chemical_edge(6, 9, bond_order=1.0)

    # Backbone peptide linkage
    graph.add_chemical_edge(2, 5, bond_order=1.0)

    partition_map = {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
        5: 1, 6: 1, 7: 1, 8: 1, 9: 1,
    }

    # Authentic 3D coordinates in Angstroms
    coords = np.array([
        [-1.84, 0.00, 0.00],   # 0: N
        [-1.23, 1.32, 0.00],   # 1: CA
        [ 0.28, 1.23, 0.00],   # 2: C
        [ 0.95, 2.26, 0.00],   # 3: O
        [-1.76, 2.05, 1.24],   # 4: CB
        [ 0.82, 0.00, 0.00],   # 5: N
        [ 2.27, -0.15, 0.00],  # 6: CA
        [ 2.68, -1.61, 0.00],  # 7: C
        [ 3.88, -1.91, 0.00],  # 8: O
        [ 2.91, 0.58, 1.19],   # 9: CB
    ], dtype=float)

    return graph, partition_map, coords


class TestGraphCrusher:
    """Verifies macromolecular coarse-graining and conservation invariants."""

    def test_crush_macromolecule_mass_and_charge_conservation(self) -> None:
        """Verify mass and charge conservation across coarse-graining."""
        graph, partition_map, coords = build_dialanine_topology()
        config = GraphCrusherConfig(mass_tolerance=1e-5, charge_tolerance=1e-5)

        cg_graph, cg_coords = crush_macromolecule(graph, partition_map, coords=coords, config=config)

        assert isinstance(cg_graph, TopologyGraph)
        assert cg_coords is not None
        assert cg_graph.number_of_nodes() == 2
        assert cg_graph.number_of_edges() == 1

        # Calculate original total mass and formal charge
        orig_mass = sum(graph.nodes[n]["mass"] for n in graph.nodes)
        orig_charge = sum(graph.nodes[n]["formal_charge"] for n in graph.nodes)

        cg_mass = sum(cg_graph.nodes[b]["mass"] for b in cg_graph.nodes)
        cg_charge = sum(cg_graph.nodes[b]["formal_charge"] for b in cg_graph.nodes)

        assert abs(cg_mass - orig_mass) < 1e-5
        assert abs(cg_charge - orig_charge) < 1e-5

        # Boundary edge contraction
        assert cg_graph.has_edge(0, 1)
        # Original edge between 2 and 5 had bond_order 1.0
        assert cg_graph.edges[0, 1]["bond_order"] == 1.0

    def test_crush_macromolecule_stage2_center_of_mass(self) -> None:
        """Verify Stage 2 bead coordinates equal exact center of mass."""
        graph, partition_map, coords = build_dialanine_topology()

        cg_graph, cg_coords = crush_macromolecule(graph, partition_map, coords=coords)
        assert cg_coords is not None
        assert cg_coords.shape == (2, 3)

        # Explicitly verify center of mass formula for bead 0
        bead_0_nodes = [0, 1, 2, 3, 4]
        m0 = np.array([graph.nodes[i]["mass"] for i in bead_0_nodes], dtype=float)
        r0 = coords[bead_0_nodes]
        expected_com_0 = np.sum(m0[:, np.newaxis] * r0, axis=0) / np.sum(m0)

        assert np.allclose(cg_coords[0], expected_com_0, atol=1e-5)

        # Topological purity: coordinates must NOT pollute node attributes
        for b in cg_graph.nodes:
            assert "coords" not in cg_graph.nodes[b]
            assert "coordinates" not in cg_graph.nodes[b]

    def test_crush_macromolecule_without_coords(self) -> None:
        """Verify topological coarse-graining succeeds when coords are None."""
        graph, partition_map, _ = build_dialanine_topology()
        cg_graph, cg_coords = crush_macromolecule(graph, partition_map, coords=None)

        assert cg_coords is None
        assert cg_graph.number_of_nodes() == 2
        assert cg_graph.has_edge(0, 1)

    def test_topological_contiguity_violation_raises(self) -> None:
        """Verify partitioning into non-contiguous subgraphs raises TopologyError."""
        graph, _, coords = build_dialanine_topology()
        # Invalid partition: grouping disconnected atoms (0 and 9) into bead 0
        disconnected_partition = {
            0: 0, 9: 0,
            1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1,
        }
        with pytest.raises(TopologyError, match="not topologically contiguous"):
            crush_macromolecule(graph, disconnected_partition, coords=coords)

    def test_missing_nodes_in_partition_raises(self) -> None:
        """Verify partition map omitting nodes raises TopologyError."""
        graph, _, coords = build_dialanine_topology()
        partial_partition = {0: 0, 1: 0}  # missing 2..9
        with pytest.raises(TopologyError, match="Missing partition mapping"):
            crush_macromolecule(graph, partial_partition, coords=coords)
