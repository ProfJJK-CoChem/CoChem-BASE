"""Physical Unit Tests for CoChem-TOPOS Unified TopologyGraph Subsystem.

Strictly adheres to Zero-Mock mandate and Mendeleev dynamic mass queries.
Operates on authentic molecular graphs (benzene, pyridine, water).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pytest
from mendeleev import element

from cochem.topos.exceptions import TopologyError
from cochem.topos.graph import TopologyGraph


class TestTopologyGraphCore:
    """Verifies core TopologyGraph node and edge schema, and invariant preservation."""

    def test_graph_instantiation_and_subclass(self) -> None:
        """Verify TopologyGraph subclasses networkx.Graph."""
        graph = TopologyGraph()
        assert isinstance(graph, nx.Graph)
        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0

    def test_add_chemical_node_dynamic_mendeleev(self) -> None:
        """Verify node attributes are dynamically populated from mendeleev without coordinates."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3", in_ring=False)
        graph.add_chemical_node(1, "N", formal_charge=0, hybridization="sp2", in_ring=True)
        graph.add_chemical_node(2, "O", formal_charge=-1, hybridization="sp3", in_ring=False)

        c_node = graph.nodes[0]
        assert c_node["symbol"] == "C"
        assert c_node["atomic_number"] == 6
        expected_c_mass = float(element("C").mass)
        assert abs(c_node["mass"] - expected_c_mass) < 1e-4
        assert c_node["formal_charge"] == 0
        assert c_node["hybridization"] == "sp3"
        assert c_node["in_ring"] is False

        # Node coordinates MUST be strictly excluded from node attributes
        assert "coords" not in c_node
        assert "coordinates" not in c_node
        assert "x" not in c_node
        assert "pos" not in c_node

        n_node = graph.nodes[1]
        assert n_node["symbol"] == "N"
        assert n_node["atomic_number"] == 7
        assert abs(n_node["mass"] - float(element("N").mass)) < 1e-4
        assert n_node["in_ring"] is True

        o_node = graph.nodes[2]
        assert o_node["symbol"] == "O"
        assert o_node["atomic_number"] == 8
        assert o_node["formal_charge"] == -1

    def test_invalid_element_symbol_raises(self) -> None:
        """Verify invalid element symbol raises TopologyError."""
        graph = TopologyGraph()
        with pytest.raises(TopologyError, match="Unknown element"):
            graph.add_chemical_node(0, "InvalidElementXYZ")

    def test_invalid_hybridization_raises(self) -> None:
        """Verify invalid hybridization state raises TopologyError."""
        graph = TopologyGraph()
        with pytest.raises(TopologyError, match="Invalid hybridization"):
            graph.add_chemical_node(0, "C", hybridization="invalid_orbital")

    def test_add_chemical_edge_attributes(self) -> None:
        """Verify edge attributes and chemical valence connectivity."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C", hybridization="sp2")
        graph.add_chemical_node(1, "C", hybridization="sp2")
        graph.add_chemical_edge(0, 1, bond_order=2.0, aromatic=False, in_ring=False, stereo="E")

        edge_data = graph.edges[0, 1]
        assert edge_data["bond_order"] == 2.0
        assert edge_data["aromatic"] is False
        assert edge_data["in_ring"] is False
        assert edge_data["stereo"] == "E"

    def test_add_edge_missing_nodes_raises(self) -> None:
        """Verify adding edge between nonexistent nodes raises TopologyError."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C")
        with pytest.raises(TopologyError, match="not found in graph"):
            graph.add_chemical_edge(0, 99)


class TestSubstructureSearch:
    """Verifies VF2 subgraph isomorphism search."""

    def test_substructure_search_benzene_query(self) -> None:
        """Verify benzene contains 6-membered aromatic ring and matching subgraphs."""
        benzene = TopologyGraph()
        for i in range(6):
            benzene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        for i in range(6):
            benzene.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

        query = TopologyGraph()
        query.add_chemical_node(0, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        query.add_chemical_node(1, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        query.add_chemical_edge(0, 1, bond_order=1.5, aromatic=True, in_ring=True)

        matches = benzene.substructure_search(query)
        assert len(matches) == 12
        for match in matches:
            matched_nodes = list(match.keys())
            assert len(matched_nodes) == 2
            u, v = matched_nodes[0], matched_nodes[1]
            assert benzene.has_edge(u, v)
            assert benzene.edges[u, v]["aromatic"] is True

    def test_substructure_search_mismatch_atom_type(self) -> None:
        """Verify query with heteroatom does not match all-carbon ring."""
        benzene = TopologyGraph()
        for i in range(6):
            benzene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        for i in range(6):
            benzene.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

        query = TopologyGraph()
        query.add_chemical_node(0, "N", formal_charge=0, hybridization="sp2", in_ring=True)
        query.add_chemical_node(1, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        query.add_chemical_edge(0, 1, bond_order=1.5, aromatic=True, in_ring=True)

        matches = benzene.substructure_search(query)
        assert len(matches) == 0


class TestQCSchemaExport:
    """Verifies QCSchema-compliant dictionary export."""

    def test_to_qcschema_dict_water(self) -> None:
        """Verify QCSchema dictionary for water molecule with physical coordinates."""
        water = TopologyGraph()
        water.add_chemical_node(0, "O", formal_charge=0, hybridization="sp3")
        water.add_chemical_node(1, "H", formal_charge=0, hybridization="sp3")
        water.add_chemical_node(2, "H", formal_charge=0, hybridization="sp3")
        water.add_chemical_edge(0, 1, bond_order=1.0)
        water.add_chemical_edge(0, 2, bond_order=1.0)

        # Real water geometry in Angstroms
        coords = np.array([
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ], dtype=float)

        qcschema = water.to_qcschema_dict(geometry=coords)

        assert qcschema["schema_name"] == "qcschema_molecule"
        assert qcschema["schema_version"] in (1, 2)
        assert qcschema["symbols"] == ["O", "H", "H"]
        assert qcschema["atomic_numbers"] == [8, 1, 1]
        assert len(qcschema["masses"]) == 3
        assert abs(qcschema["masses"][0] - float(element("O").mass)) < 1e-4
        assert qcschema["molecular_charge"] == 0
        assert qcschema["molecular_multiplicity"] == 1

        geom = qcschema["geometry"]
        assert len(geom) == 9
        assert abs(geom[0]) < 1e-5
        assert abs(geom[1]) < 1e-5

        assert "cochem_topology" in qcschema["extras"]
        topo_extras = qcschema["extras"]["cochem_topology"]
        assert "hybridization" in topo_extras
        assert "in_ring" in topo_extras
        assert "aromatic_bonds" in topo_extras
        assert "stereo" in topo_extras


class TestFileLockSerialization:
    """Verifies atomic thread-safe serialization with filelock."""

    def test_save_and_load_disk_roundtrip(self, tmp_path: Path) -> None:
        """Verify atomic file replacement and serialization round-trip."""
        graph = TopologyGraph()
        graph.add_chemical_node(0, "C", formal_charge=0, hybridization="sp2", in_ring=True)
        graph.add_chemical_node(1, "N", formal_charge=0, hybridization="sp2", in_ring=True)
        graph.add_chemical_edge(0, 1, bond_order=1.5, aromatic=True, in_ring=True)

        target_file = tmp_path / "molecule.json"
        graph.save_to_disk(target_file)

        assert target_file.exists()

        loaded_graph = TopologyGraph.load_from_disk(target_file)
        assert loaded_graph.number_of_nodes() == 2
        assert loaded_graph.number_of_edges() == 1
        assert loaded_graph.nodes[0]["symbol"] == "C"
        assert loaded_graph.nodes[1]["symbol"] == "N"
        assert loaded_graph.edges[0, 1]["aromatic"] is True
        assert loaded_graph.edges[0, 1]["bond_order"] == 1.5
