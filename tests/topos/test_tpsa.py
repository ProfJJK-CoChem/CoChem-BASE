"""Physical Unit Tests for CoChem-TOPOS Topological Polar Surface Area (TPSA) Subsystem.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies full Ertl 2000 fragment-based parameters on authentic molecular topologies
including Aspirin and Nitrobenzene (both pentavalent and charge-separated representations).
"""

from __future__ import annotations

import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.tpsa import TPSACalculator, TPSAResult


def build_aspirin() -> TopologyGraph:
    """Builds authentic topological representation of Aspirin (acetylsalicylic acid)."""
    graph = TopologyGraph()
    # Benzene ring (nodes 0..5)
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Carboxylic acid group at C0: -C(=O)OH
    graph.add_chemical_node(6, "C", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O (17.07)
    graph.add_chemical_node(8, "O", formal_charge=0, hybridization="sp3")  # Hydroxyl -OH (20.23)
    graph.add_chemical_node(9, "H", formal_charge=0, hybridization="sp3")  # Hydroxyl H
    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=1.0)
    graph.add_chemical_edge(8, 9, bond_order=1.0)

    # Acetoxy group at C1: -O-C(=O)CH3
    graph.add_chemical_node(10, "O", formal_charge=0, hybridization="sp3")  # Ester -O- (9.23)
    graph.add_chemical_node(11, "C", formal_charge=0, hybridization="sp2")  # Carbonyl C
    graph.add_chemical_node(12, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O (17.07)
    graph.add_chemical_node(13, "C", formal_charge=0, hybridization="sp3")  # Methyl C
    graph.add_chemical_edge(1, 10, bond_order=1.0)
    graph.add_chemical_edge(10, 11, bond_order=1.0)
    graph.add_chemical_edge(11, 12, bond_order=2.0)
    graph.add_chemical_edge(11, 13, bond_order=1.0)

    return graph


def build_nitrobenzene_pentavalent() -> TopologyGraph:
    """Builds Nitrobenzene under pentavalent neutral representation (-N(=O)2)."""
    graph = TopologyGraph()
    # Benzene ring (nodes 0..5)
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Nitro group: neutral N with two double bonds to O
    graph.add_chemical_node(6, "N", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(8, "O", formal_charge=0, hybridization="sp2")

    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=2.0)
    return graph


def build_nitrobenzene_zwitterionic() -> TopologyGraph:
    """Builds Nitrobenzene under charge-separated zwitterionic representation (-N+(=O)O-)."""
    graph = TopologyGraph()
    # Benzene ring (nodes 0..5)
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Nitro group: N+ with one =O and one -O-
    graph.add_chemical_node(6, "N", formal_charge=1, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(8, "O", formal_charge=-1, hybridization="sp3")

    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=1.0)
    return graph


class TestTPSACalculator:
    """Verifies Ertl 2000 fragment-based TPSA calculations."""

    def test_aspirin_tpsa(self) -> None:
        """Run on Aspirin (assert TPSA = 63.60 +/- 0.1 A^2)."""
        aspirin = build_aspirin()
        res = TPSACalculator.calculate(aspirin)
        assert isinstance(res, TPSAResult)
        # Expected: 17.07 + 20.23 + 9.23 + 17.07 = 63.60 A^2
        assert abs(res.total_tpsa - 63.60) <= 0.1
        assert abs(res.tpsa - 63.60) <= 0.1
        # Test integrated graph method
        assert abs(aspirin.calculate_tpsa() - 63.60) <= 0.1

    def test_nitrobenzene_pentavalent_tpsa(self) -> None:
        """Run on Nitrobenzene (assert TPSA = 45.82 +/- 0.1 A^2 under pentavalent neutral representation)."""
        nitro = build_nitrobenzene_pentavalent()
        res = TPSACalculator.calculate(nitro)
        # Expected: 11.68 (N) + 2 * 17.07 (O) = 45.82 A^2
        assert abs(res.total_tpsa - 45.82) <= 0.1
        assert abs(res.tpsa - 45.82) <= 0.1
        assert abs(nitro.calculate_tpsa() - 45.82) <= 0.1

    def test_nitrobenzene_zwitterionic_tpsa(self) -> None:
        """Run on Nitrobenzene (assert TPSA = 43.14 +/- 0.1 A^2 under charge-separated zwitterionic representation)."""
        nitro = build_nitrobenzene_zwitterionic()
        res = TPSACalculator.calculate(nitro)
        # Expected: 3.01 (N+) + 17.07 (=O) + 23.06 (O-) = 43.14 A^2
        assert abs(res.total_tpsa - 43.14) <= 0.1
        assert abs(res.tpsa - 43.14) <= 0.1
        assert abs(nitro.calculate_tpsa() - 43.14) <= 0.1
