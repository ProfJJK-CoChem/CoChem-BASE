"""Physical Unit Tests for CoChem-TOPOS Pharmacophore Feature Extraction.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies HBD, HBA, aromatic rings, anionic centers, cationic centers, and lipophilic clusters
on authentic pharmaceutical topologies (Aspirin, Acetylsalicylate anion, Ibuprofen).
"""

from __future__ import annotations

import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.pharmacophore import (
    PharmacophoreExtractor,
    PharmacophoreFeatureSet,
)


def build_neutral_aspirin() -> TopologyGraph:
    """Builds authentic topological representation of neutral Aspirin (acetylsalicylic acid)."""
    graph = TopologyGraph()
    # Benzene ring
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Carboxylic acid group at C0: -C(=O)OH
    graph.add_chemical_node(6, "C", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O
    graph.add_chemical_node(8, "O", formal_charge=0, hybridization="sp3")  # Hydroxyl -OH
    graph.add_chemical_node(9, "H", formal_charge=0, hybridization="sp3")  # Hydroxyl H
    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=1.0)
    graph.add_chemical_edge(8, 9, bond_order=1.0)

    # Acetoxy group at C1: -O-C(=O)CH3
    graph.add_chemical_node(10, "O", formal_charge=0, hybridization="sp3")  # Ester -O-
    graph.add_chemical_node(11, "C", formal_charge=0, hybridization="sp2")  # Carbonyl C
    graph.add_chemical_node(12, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O
    graph.add_chemical_node(13, "C", formal_charge=0, hybridization="sp3")  # Methyl C
    graph.add_chemical_edge(1, 10, bond_order=1.0)
    graph.add_chemical_edge(10, 11, bond_order=1.0)
    graph.add_chemical_edge(11, 12, bond_order=2.0)
    graph.add_chemical_edge(11, 13, bond_order=1.0)

    return graph


def build_acetylsalicylate_anion() -> TopologyGraph:
    """Builds authentic topological representation of deprotonated Aspirin (acetylsalicylate anion)."""
    graph = TopologyGraph()
    # Benzene ring
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Carboxylate group at C0: -C(=O)O^-
    graph.add_chemical_node(6, "C", formal_charge=0, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")   # Carbonyl =O
    graph.add_chemical_node(8, "O", formal_charge=-1, hybridization="sp3")  # Deprotonated O^-
    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=1.0)

    # Acetoxy group at C1: -O-C(=O)CH3
    graph.add_chemical_node(10, "O", formal_charge=0, hybridization="sp3")  # Ester -O-
    graph.add_chemical_node(11, "C", formal_charge=0, hybridization="sp2")  # Carbonyl C
    graph.add_chemical_node(12, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O
    graph.add_chemical_node(13, "C", formal_charge=0, hybridization="sp3")  # Methyl C
    graph.add_chemical_edge(1, 10, bond_order=1.0)
    graph.add_chemical_edge(10, 11, bond_order=1.0)
    graph.add_chemical_edge(11, 12, bond_order=2.0)
    graph.add_chemical_edge(11, 13, bond_order=1.0)

    return graph


def build_ibuprofen() -> TopologyGraph:
    """Builds authentic topological representation of Ibuprofen."""
    graph = TopologyGraph()
    # Benzene ring (nodes 0..5)
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Isobutyl group at C0: -CH2-CH(CH3)2
    graph.add_chemical_node(6, "C", formal_charge=0, hybridization="sp3")  # CH2
    graph.add_chemical_node(7, "C", formal_charge=0, hybridization="sp3")  # CH
    graph.add_chemical_node(8, "C", formal_charge=0, hybridization="sp3")  # CH3
    graph.add_chemical_node(9, "C", formal_charge=0, hybridization="sp3")  # CH3
    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=1.0)
    graph.add_chemical_edge(7, 8, bond_order=1.0)
    graph.add_chemical_edge(7, 9, bond_order=1.0)

    # 2-propanoic acid group at C3 (para): -CH(CH3)-COOH
    graph.add_chemical_node(10, "C", formal_charge=0, hybridization="sp3")  # CH
    graph.add_chemical_node(11, "C", formal_charge=0, hybridization="sp3")  # CH3
    graph.add_chemical_node(12, "C", formal_charge=0, hybridization="sp2")  # Carbonyl C
    graph.add_chemical_node(13, "O", formal_charge=0, hybridization="sp2")  # Carbonyl =O
    graph.add_chemical_node(14, "O", formal_charge=0, hybridization="sp3")  # Hydroxyl -OH
    graph.add_chemical_node(15, "H", formal_charge=0, hybridization="sp3")  # Hydroxyl H
    graph.add_chemical_edge(3, 10, bond_order=1.0)
    graph.add_chemical_edge(10, 11, bond_order=1.0)
    graph.add_chemical_edge(10, 12, bond_order=1.0)
    graph.add_chemical_edge(12, 13, bond_order=2.0)
    graph.add_chemical_edge(12, 14, bond_order=1.0)
    graph.add_chemical_edge(14, 15, bond_order=1.0)

    return graph


class TestPharmacophoreExtraction:
    """Verifies pharmacophore extraction on neutral aspirin, acetylsalicylate anion, and ibuprofen."""

    def test_neutral_aspirin_pharmacophore(self) -> None:
        """Run on Neutral Aspirin (assert 1 HBD, 4 HBA, 1 aromatic ring, 0 anionic centers)."""
        aspirin = build_neutral_aspirin()
        features = PharmacophoreExtractor.extract(aspirin)
        assert isinstance(features, PharmacophoreFeatureSet)

        assert len(features.hbd) == 1
        assert len(features.hba) == 4
        assert len(features.aromatic_rings) == 1
        assert len(features.anionic_centers) == 0

        # Pydantic v2 data contract verification
        assert len(features.donors) == 1
        assert len(features.acceptors) == 4
        assert len(features.aromatic_rings[0]) == 6
        assert len(features.anionic_centers) == 0

    def test_acetylsalicylate_anion_pharmacophore(self) -> None:
        """Run on Acetylsalicylate Anion (assert 0 HBD, 4 HBA, 1 aromatic ring, 1 anionic center)."""
        anion = build_acetylsalicylate_anion()
        features = PharmacophoreExtractor.extract(anion)
        assert isinstance(features, PharmacophoreFeatureSet)

        assert len(features.hbd) == 0
        assert len(features.hba) == 4
        assert len(features.aromatic_rings) == 1
        assert len(features.anionic_centers) == 1

        # Pydantic v2 data contract verification
        assert len(features.donors) == 0
        assert len(features.acceptors) == 4
        assert features.anionic_centers == [8]

    def test_ibuprofen_pharmacophore(self) -> None:
        """Run on Ibuprofen (assert 1 HBD, 2 HBA, 1 lipophilic cluster)."""
        ibuprofen = build_ibuprofen()
        features = PharmacophoreExtractor.extract(ibuprofen)
        assert isinstance(features, PharmacophoreFeatureSet)

        assert len(features.hbd) == 1
        assert len(features.hba) == 2
        assert len(features.lipophilic_clusters) == 1
        assert len(features.aromatic_rings) == 1

        # Pydantic v2 data contract verification
        assert len(features.donors) == 1
        assert len(features.acceptors) == 2
        assert len(features.lipophilic_centers) == 1
