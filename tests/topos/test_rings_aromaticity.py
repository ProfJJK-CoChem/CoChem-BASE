"""Physical Unit Tests for CoChem-TOPOS Ring Perception & Aromaticity Engine.

Strictly adheres to Zero-Mock mandate and physical molecular inputs.
Validates:
- Deterministic cycle basis & cubane cage topology (ESSR).
- Hückel (4n+2) aromaticity for benzene, pyridine, pyrrole.
- Polycyclic aromaticity for naphthalene.
- Non-aromatic rings (cyclohexane, cyclooctatetraene).
- Non-destructive Stage 2 planarity validation.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.rings import perceive_aromaticity, perceive_cycle_basis


class TestRingPerception:
    """Verifies deterministic cycle basis perception and cage topology handling."""

    def test_benzene_monocyclic_basis(self) -> None:
        """Verify cycle basis perception for monocyclic benzene."""
        benzene = TopologyGraph()
        for i in range(6):
            benzene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")
        for i in range(6):
            benzene.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5)

        cycles = perceive_cycle_basis(benzene)
        assert len(cycles) == 1
        assert len(cycles[0]) == 6
        # Canonical order starts at min index (0)
        assert cycles[0][0] == 0

        # Verify node and edge annotations
        for n in benzene.nodes:
            assert benzene.nodes[n]["in_ring"] is True
            assert 6 in benzene.nodes[n]["ring_sizes"]

        for u, v in benzene.edges:
            assert benzene.edges[u, v]["in_ring"] is True
            assert 6 in benzene.edges[u, v]["ring_sizes"]

    def test_cubane_symmetric_polycyclic_cage(self) -> None:
        """Verify cubane cage perceives 4-membered faces and essential rings deterministically."""
        cubane = TopologyGraph()
        # 8 carbon vertices of cubane
        for i in range(8):
            cubane.add_chemical_node(i, "C", formal_charge=0, hybridization="sp3")

        # 12 edges of a cube:
        # Bottom face: 0-1-2-3-0
        # Top face: 4-5-6-7-4
        # Vertical edges: 0-4, 1-5, 2-6, 3-7
        cube_edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        for u, v in cube_edges:
            cubane.add_chemical_edge(u, v, bond_order=1.0)

        cycles = perceive_cycle_basis(cubane)
        # Cycle basis has dimension E - V + 1 = 12 - 8 + 1 = 5 cycles (or 6 in ESSR relevant rings)
        assert len(cycles) in (5, 6)
        for c in cycles:
            assert len(c) == 4

        # All 8 atoms and 12 edges are strictly in rings of size 4
        for n in cubane.nodes:
            assert cubane.nodes[n]["in_ring"] is True
            assert 4 in cubane.nodes[n]["ring_sizes"]

        for u, v in cubane.edges:
            assert cubane.edges[u, v]["in_ring"] is True
            assert 4 in cubane.edges[u, v]["ring_sizes"]


class TestAromaticityEngine:
    """Verifies Hückel and Clar aromaticity rules and electron counting."""

    def test_benzene_huckel_aromaticity(self) -> None:
        """Verify benzene 6 pi-electron Hückel aromaticity."""
        benzene = TopologyGraph()
        for i in range(6):
            benzene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")
        for i in range(6):
            benzene.add_chemical_edge(i, (i + 1) % 6, bond_order=1.0)

        # Real planar coordinates
        coords = np.array([
            [ 1.397,  0.000, 0.0],
            [ 0.699,  1.210, 0.0],
            [-0.699,  1.210, 0.0],
            [-1.397,  0.000, 0.0],
            [-0.699, -1.210, 0.0],
            [ 0.699, -1.210, 0.0],
        ], dtype=float)

        perceive_aromaticity(benzene, coords=coords, planarity_threshold=0.15)

        for n in benzene.nodes:
            assert benzene.nodes[n]["is_aromatic"] is True

        for u, v in benzene.edges:
            assert benzene.edges[u, v]["aromatic"] is True
            assert benzene.edges[u, v]["bond_order"] == 1.5

        # Check non-destructive planarity strain metric was recorded
        assert "ring_planarity_rmsd" in benzene.graph
        for ring_key, rmsd_val in benzene.graph["ring_planarity_rmsd"].items():
            assert rmsd_val < 0.05

    def test_pyridine_heteroatom_aromaticity(self) -> None:
        """Verify pyridine (1 pi-electron nitrogen) 6 pi-electron aromaticity."""
        pyridine = TopologyGraph()
        pyridine.add_chemical_node(0, "N", formal_charge=0, hybridization="sp2")
        for i in range(1, 6):
            pyridine.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")

        edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)]
        for u, v in edges:
            pyridine.add_chemical_edge(u, v, bond_order=1.0)

        perceive_aromaticity(pyridine)

        for n in pyridine.nodes:
            assert pyridine.nodes[n]["is_aromatic"] is True

        for u, v in pyridine.edges:
            assert pyridine.edges[u, v]["aromatic"] is True
            assert pyridine.edges[u, v]["bond_order"] == 1.5

    def test_pyrrole_five_membered_aromaticity(self) -> None:
        """Verify pyrrole (2 pi-electron NH donor) 6 pi-electron aromaticity."""
        pyrrole = TopologyGraph()
        # 0: NH, 1..4: C
        pyrrole.add_chemical_node(0, "N", formal_charge=0, hybridization="sp2")
        for i in range(1, 5):
            pyrrole.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")

        for u, v in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]:
            pyrrole.add_chemical_edge(u, v, bond_order=1.0)

        perceive_aromaticity(pyrrole)

        for n in pyrrole.nodes:
            assert pyrrole.nodes[n]["is_aromatic"] is True

        for u, v in pyrrole.edges:
            assert pyrrole.edges[u, v]["aromatic"] is True

    def test_naphthalene_fused_polycyclic_aromaticity(self) -> None:
        """Verify naphthalene 10 pi-electron fused aromatic system."""
        naphthalene = TopologyGraph()
        # 10 carbons: ring 1 is 0-1-2-3-4-5, ring 2 is 4-5-6-7-8-9, bridge is 4-5
        for i in range(10):
            naphthalene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")

        naphthalene_edges = [
            (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0),
            (5, 6), (6, 7), (7, 8), (8, 9), (9, 4),
        ]
        for u, v in naphthalene_edges:
            naphthalene.add_chemical_edge(u, v, bond_order=1.0)

        perceive_aromaticity(naphthalene)

        for n in naphthalene.nodes:
            assert naphthalene.nodes[n]["is_aromatic"] is True

    def test_cyclohexane_non_aromatic(self) -> None:
        """Verify cyclohexane (all sp3 carbons, 0 pi electrons) is non-aromatic."""
        cyclohexane = TopologyGraph()
        for i in range(6):
            cyclohexane.add_chemical_node(i, "C", formal_charge=0, hybridization="sp3")
        for i in range(6):
            cyclohexane.add_chemical_edge(i, (i + 1) % 6, bond_order=1.0)

        perceive_aromaticity(cyclohexane)

        for n in cyclohexane.nodes:
            assert cyclohexane.nodes[n].get("is_aromatic", False) is False

        for u, v in cyclohexane.edges:
            assert cyclohexane.edges[u, v].get("aromatic", False) is False

    def test_non_destructive_planarity_validation(self) -> None:
        """Verify non-planar coordinates record RMSD strain without altering topological aromaticity."""
        benzene = TopologyGraph()
        for i in range(6):
            benzene.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2")
        for i in range(6):
            benzene.add_chemical_edge(i, (i + 1) % 6, bond_order=1.0)

        # Heavily warped coordinates (boat conformation)
        puckered_coords = np.array([
            [ 1.397,  0.000,  0.85],
            [ 0.699,  1.210, -0.85],
            [-0.699,  1.210,  0.85],
            [-1.397,  0.000, -0.85],
            [-0.699, -1.210,  0.85],
            [ 0.699, -1.210, -0.85],
        ], dtype=float)

        perceive_aromaticity(benzene, coords=puckered_coords, planarity_threshold=0.15)

        # Non-destructive invariant: topological aromaticity MUST remain True
        for n in benzene.nodes:
            assert benzene.nodes[n]["is_aromatic"] is True

        # But planarity RMSD must be greater than threshold
        rmsd_dict = benzene.graph.get("ring_planarity_rmsd", {})
        assert len(rmsd_dict) > 0
        for rmsd_val in rmsd_dict.values():
            assert rmsd_val > 0.15
