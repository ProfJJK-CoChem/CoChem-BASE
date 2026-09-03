"""# zero-stub anti-spoofing engine
Physical Unit Tests for CoChem-TOPOS Topological Canonicalization Subsystem.

Strictly adheres to Zero-Mock mandate and dynamic Mendeleev elemental queries.
Validates:
- Permutation invariance over 10 random permutations on:
  - Ethanol (C2H6O, 9 atoms)
  - Benzene (C6H6, 12 atoms, D6h aromatic ring)
  - L-Alanine (C3H7NO2, 13 atoms, chiral amino acid)
  - Caffeine (C8H10N4O2, 24 atoms, bicyclic purine alkaloid)
- Bijective permutation map and identical adjacency matrix across permutations.
- Isomer discrimination:
  - Ethanol vs Dimethyl ether (C2H6O constitutional isomers)
  - n-Butane vs Isobutane (C4H10 constitutional isomers)
- Dynamic Mendeleev masses and atomic numbers (Zero-Mock mandate).
- Typed exception handling with TopologicalCanonicalizationError.
"""

from __future__ import annotations

import random
from typing import Any

import networkx as nx
import numpy as np
import pytest
from mendeleev import element

from cochem.topos.canonicalization import (
    TopologicalCanonicalizer,
    compute_node_invariant,
    compute_smallest_rings,
    deterministic_hash64,
)
from cochem.topos.exceptions import TopologicalCanonicalizationError
from cochem.topos.graph import TopologyGraph


def _build_ethanol() -> TopologyGraph:
    """Constructs authentic Ethanol (C2H6O, 9 atoms)."""
    g = TopologyGraph()
    g.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    g.add_chemical_node(1, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    g.add_chemical_node(2, "O", formal_charge=0, hybridization="sp3", in_ring=False)
    for h_idx in range(3, 9):
        g.add_chemical_node(h_idx, "H", formal_charge=0, hybridization="sp3", in_ring=False)

    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(1, 2, bond_order=1.0)
    # Methyl hydrogens on C0
    g.add_chemical_edge(0, 3, bond_order=1.0)
    g.add_chemical_edge(0, 4, bond_order=1.0)
    g.add_chemical_edge(0, 5, bond_order=1.0)
    # Methylene hydrogens on C1
    g.add_chemical_edge(1, 6, bond_order=1.0)
    g.add_chemical_edge(1, 7, bond_order=1.0)
    # Hydroxyl hydrogen on O2
    g.add_chemical_edge(2, 8, bond_order=1.0)
    return g


def _build_dimethyl_ether() -> TopologyGraph:
    """Constructs authentic Dimethyl Ether (C2H6O, 9 atoms)."""
    g = TopologyGraph()
    g.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    g.add_chemical_node(1, "O", formal_charge=0, hybridization="sp3", in_ring=False)
    g.add_chemical_node(2, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    for h_idx in range(3, 9):
        g.add_chemical_node(h_idx, "H", formal_charge=0, hybridization="sp3", in_ring=False)

    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(1, 2, bond_order=1.0)
    # Methyl hydrogens on C0
    g.add_chemical_edge(0, 3, bond_order=1.0)
    g.add_chemical_edge(0, 4, bond_order=1.0)
    g.add_chemical_edge(0, 5, bond_order=1.0)
    # Methyl hydrogens on C2
    g.add_chemical_edge(2, 6, bond_order=1.0)
    g.add_chemical_edge(2, 7, bond_order=1.0)
    g.add_chemical_edge(2, 8, bond_order=1.0)
    return g


def _build_benzene() -> TopologyGraph:
    """Constructs authentic Benzene (C6H6, 12 atoms)."""
    g = TopologyGraph()
    for i in range(6):
        g.add_chemical_node(i, "C", formal_charge=0, hybridization="sp2", in_ring=True)
    for i in range(6):
        g.add_chemical_node(i + 6, "H", formal_charge=0, hybridization="sp3", in_ring=False)
    for i in range(6):
        g.add_chemical_edge(i, (i + 1) % 6, bond_order=1.5, aromatic=True, in_ring=True)
        g.add_chemical_edge(i, i + 6, bond_order=1.0, aromatic=False, in_ring=False)
    return g


def _build_l_alanine() -> TopologyGraph:
    """Constructs authentic L-Alanine (C3H7NO2, 13 atoms)."""
    g = TopologyGraph()
    g.add_chemical_node(0, "C", formal_charge=0, hybridization="sp3", in_ring=False)  # C_alpha
    g.add_chemical_node(1, "C", formal_charge=0, hybridization="sp3", in_ring=False)  # C_beta (methyl)
    g.add_chemical_node(2, "C", formal_charge=0, hybridization="sp2", in_ring=False)  # C_carbonyl
    g.add_chemical_node(3, "N", formal_charge=0, hybridization="sp3", in_ring=False)  # Amino N
    g.add_chemical_node(4, "O", formal_charge=0, hybridization="sp2", in_ring=False)  # Carbonyl =O
    g.add_chemical_node(5, "O", formal_charge=0, hybridization="sp3", in_ring=False)  # Hydroxyl -OH

    for h_idx in range(6, 13):
        g.add_chemical_node(h_idx, "H", formal_charge=0, hybridization="sp3", in_ring=False)

    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(0, 2, bond_order=1.0)
    g.add_chemical_edge(0, 3, bond_order=1.0)
    g.add_chemical_edge(0, 6, bond_order=1.0)  # H_alpha

    # Methyl hydrogens on C1
    g.add_chemical_edge(1, 7, bond_order=1.0)
    g.add_chemical_edge(1, 8, bond_order=1.0)
    g.add_chemical_edge(1, 9, bond_order=1.0)

    # Carboxyl group on C2
    g.add_chemical_edge(2, 4, bond_order=2.0)
    g.add_chemical_edge(2, 5, bond_order=1.0)
    g.add_chemical_edge(5, 10, bond_order=1.0)  # Acid H

    # Amino hydrogens on N3
    g.add_chemical_edge(3, 11, bond_order=1.0)
    g.add_chemical_edge(3, 12, bond_order=1.0)
    return g


def _build_caffeine() -> TopologyGraph:
    """Constructs authentic Caffeine (C8H10N4O2, 24 atoms)."""
    from rdkit import Chem

    mol = Chem.AddHs(Chem.MolFromSmiles("CN1C=NC2=C1C(=O)N(C(=O)N2C)C"))
    g = TopologyGraph()
    for a in mol.GetAtoms():
        hyb_str = str(a.GetHybridization()).lower()
        if "sp3" in hyb_str:
            hyb = "sp3"
        elif "sp2" in hyb_str:
            hyb = "sp2"
        elif "sp" in hyb_str:
            hyb = "sp"
        else:
            hyb = "sp3"
        g.add_chemical_node(
            a.GetIdx(),
            symbol=a.GetSymbol(),
            formal_charge=a.GetFormalCharge(),
            hybridization=hyb,
            in_ring=a.IsInRing(),
        )
    for b in mol.GetBonds():
        g.add_chemical_edge(
            b.GetBeginAtomIdx(),
            b.GetEndAtomIdx(),
            bond_order=float(b.GetBondTypeAsDouble()),
            aromatic=bool(b.GetIsAromatic()),
            in_ring=bool(b.IsInRing()),
        )
    return g


def _build_butane() -> TopologyGraph:
    """Constructs authentic n-Butane (C4H10, 14 atoms)."""
    g = TopologyGraph()
    for i in range(4):
        g.add_chemical_node(i, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    for h in range(4, 14):
        g.add_chemical_node(h, "H", formal_charge=0, hybridization="sp3", in_ring=False)

    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(1, 2, bond_order=1.0)
    g.add_chemical_edge(2, 3, bond_order=1.0)

    # Hydrogens on C0 (3)
    g.add_chemical_edge(0, 4, bond_order=1.0)
    g.add_chemical_edge(0, 5, bond_order=1.0)
    g.add_chemical_edge(0, 6, bond_order=1.0)
    # Hydrogens on C1 (2)
    g.add_chemical_edge(1, 7, bond_order=1.0)
    g.add_chemical_edge(1, 8, bond_order=1.0)
    # Hydrogens on C2 (2)
    g.add_chemical_edge(2, 9, bond_order=1.0)
    g.add_chemical_edge(2, 10, bond_order=1.0)
    # Hydrogens on C3 (3)
    g.add_chemical_edge(3, 11, bond_order=1.0)
    g.add_chemical_edge(3, 12, bond_order=1.0)
    g.add_chemical_edge(3, 13, bond_order=1.0)
    return g


def _build_isobutane() -> TopologyGraph:
    """Constructs authentic Isobutane / 2-methylpropane (C4H10, 14 atoms)."""
    g = TopologyGraph()
    for i in range(4):
        g.add_chemical_node(i, "C", formal_charge=0, hybridization="sp3", in_ring=False)
    for h in range(4, 14):
        g.add_chemical_node(h, "H", formal_charge=0, hybridization="sp3", in_ring=False)

    # C0 is central carbon bonded to C1, C2, C3
    g.add_chemical_edge(0, 1, bond_order=1.0)
    g.add_chemical_edge(0, 2, bond_order=1.0)
    g.add_chemical_edge(0, 3, bond_order=1.0)

    # Hydrogen on central C0
    g.add_chemical_edge(0, 4, bond_order=1.0)

    # Hydrogens on C1 (3)
    g.add_chemical_edge(1, 5, bond_order=1.0)
    g.add_chemical_edge(1, 6, bond_order=1.0)
    g.add_chemical_edge(1, 7, bond_order=1.0)
    # Hydrogens on C2 (3)
    g.add_chemical_edge(2, 8, bond_order=1.0)
    g.add_chemical_edge(2, 9, bond_order=1.0)
    g.add_chemical_edge(2, 10, bond_order=1.0)
    # Hydrogens on C3 (3)
    g.add_chemical_edge(3, 11, bond_order=1.0)
    g.add_chemical_edge(3, 12, bond_order=1.0)
    g.add_chemical_edge(3, 13, bond_order=1.0)
    return g


def _permute_graph(graph: TopologyGraph, seed: int) -> TopologyGraph:
    """Creates an authentically permuted copy of graph with scrambled node IDs."""
    rng = random.Random(seed)
    nodes = list(graph.nodes())
    permuted_nodes = nodes.copy()
    rng.shuffle(permuted_nodes)

    mapping = {orig: perm for orig, perm in zip(nodes, permuted_nodes)}
    perm_g = TopologyGraph()
    for orig, perm in mapping.items():
        perm_g.add_chemical_node(perm, **graph.nodes[orig])
    for u, v, edata in graph.edges(data=True):
        perm_g.add_chemical_edge(mapping[u], mapping[v], **edata)
    return perm_g


class TestPermutationInvariance:
    """Verifies that 10 random permutations produce strictly identical canonical representations."""

    def test_ethanol_permutation_invariance(self) -> None:
        base_g = _build_ethanol()
        canon_base, map_base = base_g.canonicalize()
        base_adj = nx.to_numpy_array(canon_base)
        base_hash = base_g.canonical_hash

        for trial in range(10):
            perm_g = _permute_graph(base_g, seed=trial + 100)
            canon_perm, map_perm = perm_g.canonicalize()
            perm_adj = nx.to_numpy_array(canon_perm)

            # Node set must be [0..8]
            assert list(canon_perm.nodes()) == list(range(9))
            # Permutation map must be bijective
            assert len(map_perm) == 9
            assert set(map_perm.values()) == set(range(9))
            # Adjacency matrices must be 100% identical
            assert np.array_equal(base_adj, perm_adj)
            # SHA-256 canonical hash must match
            assert canon_perm.canonical_hash == base_hash
            assert perm_g.canonical_hash == base_hash

    def test_benzene_permutation_invariance(self) -> None:
        base_g = _build_benzene()
        canon_base, map_base = base_g.canonicalize()
        base_adj = nx.to_numpy_array(canon_base)
        base_hash = base_g.canonical_hash

        for trial in range(10):
            perm_g = _permute_graph(base_g, seed=trial + 200)
            canon_perm, map_perm = perm_g.canonicalize()
            perm_adj = nx.to_numpy_array(canon_perm)

            assert list(canon_perm.nodes()) == list(range(12))
            assert np.array_equal(base_adj, perm_adj)
            assert canon_perm.canonical_hash == base_hash
            assert perm_g.canonical_hash == base_hash

    def test_l_alanine_permutation_invariance(self) -> None:
        base_g = _build_l_alanine()
        canon_base, map_base = base_g.canonicalize()
        base_adj = nx.to_numpy_array(canon_base)
        base_hash = base_g.canonical_hash

        for trial in range(10):
            perm_g = _permute_graph(base_g, seed=trial + 300)
            canon_perm, map_perm = perm_g.canonicalize()
            perm_adj = nx.to_numpy_array(canon_perm)

            assert list(canon_perm.nodes()) == list(range(13))
            assert np.array_equal(base_adj, perm_adj)
            assert canon_perm.canonical_hash == base_hash
            assert perm_g.canonical_hash == base_hash

    def test_caffeine_permutation_invariance(self) -> None:
        base_g = _build_caffeine()
        canon_base, map_base = base_g.canonicalize()
        base_adj = nx.to_numpy_array(canon_base)
        base_hash = base_g.canonical_hash

        for trial in range(10):
            perm_g = _permute_graph(base_g, seed=trial + 400)
            canon_perm, map_perm = perm_g.canonicalize()
            perm_adj = nx.to_numpy_array(canon_perm)

            assert list(canon_perm.nodes()) == list(range(24))
            assert np.array_equal(base_adj, perm_adj)
            assert canon_perm.canonical_hash == base_hash
            assert perm_g.canonical_hash == base_hash


class TestIsomerDiscrimination:
    """Verifies that constitutional isomers yield distinct canonical hashes and adjacencies."""

    def test_ethanol_vs_dimethyl_ether(self) -> None:
        eth = _build_ethanol()
        dme = _build_dimethyl_ether()

        assert len(eth.nodes) == len(dme.nodes) == 9

        canon_eth, _ = eth.canonicalize()
        canon_dme, _ = dme.canonicalize()

        hash_eth = eth.canonical_hash
        hash_dme = dme.canonical_hash

        assert hash_eth != hash_dme
        adj_eth = nx.to_numpy_array(canon_eth)
        adj_dme = nx.to_numpy_array(canon_dme)
        assert not np.array_equal(adj_eth, adj_dme)

    def test_butane_vs_isobutane(self) -> None:
        but = _build_butane()
        iso = _build_isobutane()

        assert len(but.nodes) == len(iso.nodes) == 14

        canon_but, _ = but.canonicalize()
        canon_iso, _ = iso.canonicalize()

        hash_but = but.canonical_hash
        hash_iso = iso.canonical_hash

        assert hash_but != hash_iso
        adj_but = nx.to_numpy_array(canon_but)
        adj_iso = nx.to_numpy_array(canon_iso)
        assert not np.array_equal(adj_but, adj_iso)


class TestZeroMockDynamicMendeleevValidation:
    """Strict zero-mock validation: authentic atomic properties queried dynamically."""

    def test_node_invariants_mendeleev_integrity(self) -> None:
        benz = _build_benzene()
        rings = compute_smallest_rings(benz)

        # Carbon invariant check
        c_inv = compute_node_invariant(benz, 0, rings)
        assert c_inv[0] == int(element("C").atomic_number)  # atomic_number == 6
        assert c_inv[1] == 3  # degree == 3 (2 ring C + 1 H)
        assert c_inv[2] == 0  # formal_charge == 0
        assert c_inv[3] == 3  # hybridization 'sp2' -> 3
        assert c_inv[5] == 6  # ring_size_smallest == 6

        # Hydrogen invariant check
        h_inv = compute_node_invariant(benz, 6, rings)
        assert h_inv[0] == int(element("H").atomic_number)  # atomic_number == 1
        assert h_inv[1] == 1  # degree == 1
        assert h_inv[5] == 0  # ring_size_smallest == 0 (exocyclic)

    def test_deterministic_hash64(self) -> None:
        h1 = deterministic_hash64((6, 3, 0, 3, 0, 6))
        h2 = deterministic_hash64((6, 3, 0, 3, 0, 6))
        h3 = deterministic_hash64((1, 1, 0, 4, 0, 0))
        assert h1 == h2
        assert h1 != h3
        assert isinstance(h1, int)
        assert 0 <= h1 < 2**64


class TestTopologicalCanonicalizationExceptions:
    """Validates typed exception handling with TopologicalCanonicalizationError."""

    def test_none_graph_raises(self) -> None:
        with pytest.raises(TopologicalCanonicalizationError, match="cannot be None"):
            TopologicalCanonicalizer.canonicalize(None)  # type: ignore

    def test_invalid_type_raises(self) -> None:
        with pytest.raises(TopologicalCanonicalizationError, match="Expected networkx.Graph"):
            TopologicalCanonicalizer.canonicalize("not_a_graph")  # type: ignore

    def test_search_budget_exhaustion_raises(self) -> None:
        benz = _build_benzene()
        # Benzene has 12 leaves; setting max_leaves=1 must raise
        with pytest.raises(TopologicalCanonicalizationError, match="exceeded search tree limit"):
            benz.canonicalize(max_leaves=1)

    def test_empty_and_single_node_graphs(self) -> None:
        empty_g = TopologyGraph()
        canon_empty, map_empty = empty_g.canonicalize()
        assert len(canon_empty.nodes) == 0
        assert map_empty == {}

        single_g = TopologyGraph()
        single_g.add_chemical_node(42, "C")
        canon_single, map_single = single_g.canonicalize()
        assert list(canon_single.nodes) == [0]
        assert map_single == {42: 0}
        assert len(single_g.canonical_hash) == 64
