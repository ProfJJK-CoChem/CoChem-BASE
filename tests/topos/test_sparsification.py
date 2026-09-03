"""Physical Unit Tests for CoChem-TOPOS Graph Sparsification Subsystem.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies Spielman-Srivastava effective resistance sparsification, spanning backbone guarantee,
spectral error bound, and execution efficiency on Ubiquitin (1ubq.pdb).
"""

from __future__ import annotations

import time
from pathlib import Path
import networkx as nx
import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.sparsification import (
    GraphSparsifier,
    SparsifiedGraphResult,
    load_pdb_topology,
)


class TestGraphSparsification:
    """Verifies graph sparsification on macromolecular topologies."""

    def test_ubiquitin_sparsification(self) -> None:
        """Run on Ubiquitin (loaded offline from tests/fixtures/1ubq.pdb, 76 residues, >1200 atoms);

        verify edge reduction >65%, graph remains connected via spanning backbone, and spectral
        error bound <= 0.10 within < 5 seconds on CPU.
        """
        fixture_path = Path("tests/fixtures/1ubq.pdb")
        assert fixture_path.exists(), f"Fixture {fixture_path} not found."

        t0 = time.perf_counter()
        # Load Ubiquitin topology and coordinates offline
        ubiquitin_graph, coords = load_pdb_topology(fixture_path, contact_cutoff=4.5)

        # Invariant checks: >1200 atoms, 76 residues
        assert ubiquitin_graph.number_of_nodes() > 1200
        protein_residues = set(
            ubiquitin_graph.nodes[n].get("residue_num")
            for n in ubiquitin_graph.nodes
            if not ubiquitin_graph.nodes[n].get("is_hetatm", False)
        )
        assert len(protein_residues) == 76

        initial_edge_count = ubiquitin_graph.number_of_edges()
        assert initial_edge_count > 3000

        # Execute sparsification with epsilon = 0.10
        result = GraphSparsifier.sparsify(ubiquitin_graph, epsilon=0.10, coordinates=coords)
        t_elapsed = time.perf_counter() - t0

        assert isinstance(result, SparsifiedGraphResult)

        # Pydantic v2 contract verification
        assert len(result.sparsified_edges) == result.sparsified_edge_count
        assert result.sparsified_edges[0].weight > 0.0
        assert result.sparsified_edges[0].source >= 0
        assert result.sparsified_edges[0].target >= 0

        # Invariant 1: Edge reduction > 65%
        assert result.edge_reduction_ratio > 0.65
        assert result.sparsified_edge_count < initial_edge_count * 0.35

        # Invariant 2: Spanning backbone guarantee (all bonded edges retained)
        sparsified_graph = result.sparsified_graph
        for u, v, d in ubiquitin_graph.edges(data=True):
            if d.get("is_bonded", False):
                assert sparsified_graph.has_edge(u, v)

        # Invariant 3: Graph remains connected via spanning backbone for the protein chain
        # Specifically, heavy atoms of the 76 residues form a connected component
        protein_nodes = [
            n for n in sparsified_graph.nodes
            if sparsified_graph.nodes[n].get("is_hetatm", False) is False
        ]
        protein_subgraph = sparsified_graph.subgraph(protein_nodes)
        assert nx.is_connected(protein_subgraph)

        # Invariant 4: Spectral error bound <= 0.10
        assert result.spectral_error_bound <= 0.10

        # Invariant 5: Performance within < 5 seconds on CPU
        assert t_elapsed < 5.0, f"Sparsification took {t_elapsed:.2f}s, exceeding 5.0s CPU limit"
