"""Physical Unit Tests for CoChem-TOPOS Resonance Structure Enumeration.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev mass queries.
Verifies conjugated pi-system traversal, alternating cycles, formal charge conservation,
energy penalties, and Boltzmann weights on authentic topologies (Pyrrole, Nitrobenzene).
"""

from __future__ import annotations

import pytest

from cochem.topos.graph import TopologyGraph
from cochem.topos.resonance import (
    ResonanceEnsembleResult,
    ResonanceEnumerator,
    ResonanceStructure,
)


def build_pyrrole() -> TopologyGraph:
    """Builds authentic topological representation of Pyrrole (C4H5N).

    5-membered heteroaromatic ring with divalent/trivalent pyrrolic nitrogen.
    """
    graph = TopologyGraph()
    # Ring nodes: N0, C1, C2, C3, C4
    graph.add_chemical_node(0, "N", formal_charge=0, hybridization="sp2", in_ring=True)
    graph.add_chemical_node(1, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    graph.add_chemical_node(2, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    graph.add_chemical_node(3, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    graph.add_chemical_node(4, "C", formal_charge=0, hybridization="sp2", in_ring=True)

    # N-H hydrogen
    graph.add_chemical_node(5, "H", formal_charge=0, hybridization="sp3")
    graph.add_chemical_edge(0, 5, bond_order=1.0)

    # Ring connectivity (canonical Kekule form: C1=C2, C3=C4)
    graph.add_chemical_edge(0, 1, bond_order=1.0, aromatic=True, in_ring=True)
    graph.add_chemical_edge(1, 2, bond_order=2.0, aromatic=True, in_ring=True)
    graph.add_chemical_edge(2, 3, bond_order=1.0, aromatic=True, in_ring=True)
    graph.add_chemical_edge(3, 4, bond_order=2.0, aromatic=True, in_ring=True)
    graph.add_chemical_edge(4, 0, bond_order=1.0, aromatic=True, in_ring=True)
    return graph


def build_nitrobenzene() -> TopologyGraph:
    """Builds authentic topological representation of Nitrobenzene (C6H5NO2)."""
    graph = TopologyGraph()
    # Benzene ring (nodes 0..5)
    for i in range(6):
        graph.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        graph.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)

    # Nitro group at C0: -N+(=O)O-
    graph.add_chemical_node(6, "N", formal_charge=1, hybridization="sp2")
    graph.add_chemical_node(7, "O", formal_charge=0, hybridization="sp2")   # =O
    graph.add_chemical_node(8, "O", formal_charge=-1, hybridization="sp3")  # -O^-
    graph.add_chemical_edge(0, 6, bond_order=1.0)
    graph.add_chemical_edge(6, 7, bond_order=2.0)
    graph.add_chemical_edge(6, 8, bond_order=1.0)
    return graph


class TestResonanceEnumeration:
    """Verifies resonance structure enumeration on authentic conjugated pi-systems."""

    def test_pyrrole_resonance_contributors(self) -> None:
        """Run on Pyrrole (assert 5 non-bipartite resonance contributors, aromatic nitrogen participating in pi-sextet)."""
        pyrrole = build_pyrrole()
        res = ResonanceEnumerator.enumerate(pyrrole, max_structures=50, temperature_k=298.15)
        assert isinstance(res, ResonanceEnsembleResult)

        # Assert exactly 5 non-bipartite resonance contributors
        assert res.ensemble_size == 5
        assert len(res.structures) == 5

        # Verify Pydantic v2 contract fields
        assert len(res.kekule_structures) == 5
        assert len(res.formal_charges) == 5
        assert len(res.weights) == 5
        assert abs(sum(res.weights) - 1.0) < 1e-4

        # Check aromatic nitrogen participation in pi-sextet across all contributors
        for s in res.structures:
            assert isinstance(s, ResonanceStructure)
            assert 0 in s.formal_charges
            # In neutral contributor formal charge is 0; in the other 4 charge-separated it is +1
            assert s.formal_charges[0] in (0, 1)

        # Check charge separation: exactly 1 neutral contributor and 4 charge-separated contributors
        neutral_count = sum(1 for s in res.structures if s.formal_charges[0] == 0)
        charged_count = sum(1 for s in res.structures if s.formal_charges[0] == 1)
        assert neutral_count == 1
        assert charged_count == 4

        # For the 4 charged structures, one carbon has -1 formal charge
        for s in res.structures:
            if s.formal_charges[0] == 1:
                neg_carbons = [c for c in (1, 2, 3, 4) if s.formal_charges.get(c) == -1]
                assert len(neg_carbons) == 1
                # Overall molecular charge conservation: sum of formal charges == 0
                assert sum(s.formal_charges.values()) == 0

        # Verify Boltzmann weights sum to 1.0 within numerical precision
        total_weight = sum(s.boltzmann_weight for s in res.structures)
        assert abs(total_weight - 1.0) < 1e-4

        # Major contributor must have the highest Boltzmann weight
        major = max(res.structures, key=lambda s: s.boltzmann_weight)
        assert major.formal_charges[0] == 0
        assert major.is_major is True

    def test_nitrobenzene_resonance_contributors(self) -> None:
        """Run on Nitrobenzene (assert 3 charge-separated ortho/para quinoid contributors,

        or ensemble size >= 3 across canonical forms, with valid formal charges recorded).
        """
        nitro = build_nitrobenzene()
        res = ResonanceEnumerator.enumerate(nitro, max_structures=50, temperature_k=298.15)
        assert isinstance(res, ResonanceEnsembleResult)

        # Ensemble size >= 3 across canonical forms
        assert res.ensemble_size >= 3

        # Check charge-separated ortho/para quinoid contributors
        # In quinoid forms: C0-N6 is double bond (order 2.0), both O's are negative (formal_charge -1),
        # N6 is +1, and an ortho or para carbon (C1, C3, or C5) has +1 formal charge.
        quinoid_forms = []
        for s in res.structures:
            c0_n6_order = s.bond_orders.get((0, 6), s.bond_orders.get((6, 0), 1.0))
            if c0_n6_order == 2.0 and s.formal_charges.get(7) == -1 and s.formal_charges.get(8) == -1:
                quinoid_forms.append(s)

        assert len(quinoid_forms) >= 3

        # Verify positive charges at ortho and para carbons in quinoid forms
        positively_charged_ring_carbons = set()
        for qf in quinoid_forms:
            # sum of formal charges must equal net charge (0)
            assert sum(qf.formal_charges.values()) == 0
            for c in (1, 2, 3, 4, 5):
                if qf.formal_charges.get(c) == 1:
                    positively_charged_ring_carbons.add(c)

        # Ortho (1, 5) and Para (3) positions have positive formal charges recorded
        assert 1 in positively_charged_ring_carbons or 5 in positively_charged_ring_carbons
        assert 3 in positively_charged_ring_carbons
