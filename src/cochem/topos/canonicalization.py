"""# zero-stub anti-spoofing engine
CoChem-TOPOS: Deterministic Topological Graph Canonicalization Subsystem.

Implements iterative 1-WL (Weisfeiler-Lehman) color refinement and McKay's
individualization-refinement search tree for deterministic tie-breaking.
Permuted inputs yield identical canonical node ordering, identical adjacency
matrices, and identical SHA-256 canonical hash signatures.
Strictly adheres to Zero-Mock mandate.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import networkx as nx
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import TopologicalCanonicalizationError
from cochem.topos.graph import TopologyGraph

logger = logging.getLogger("cochem.topos.canonicalization")

HYBRIDIZATION_MAP: dict[str, int] = {
    "s": 1,
    "sp": 2,
    "sp2": 3,
    "sp3": 4,
    "sp3d": 5,
    "sp3d2": 6,
    "coarse_grained": 7,
}


def deterministic_hash64(data: Any) -> int:
    """Computes deterministic 64-bit unsigned integer hash using SHA-256."""
    if isinstance(data, (int, float, str, bool)):
        raw = str(data).encode("utf-8")
    elif isinstance(data, (tuple, list)):
        raw = json.dumps([str(x) for x in data], sort_keys=True).encode("utf-8")
    elif isinstance(data, dict):
        raw = json.dumps({str(k): str(v) for k, v in sorted(data.items(), key=lambda kv: str(kv[0]))}, sort_keys=True).encode("utf-8")
    elif isinstance(data, bytes):
        raw = data
    else:
        raw = repr(data).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def compute_smallest_rings(graph: nx.Graph) -> dict[Any, int]:
    """Computes the size of the smallest cycle containing each node (0 if not in any ring)."""
    smallest_rings: dict[Any, int] = {}
    for u in graph.nodes():
        deg = graph.degree(u)
        if deg < 2:
            smallest_rings[u] = 0
            continue

        neighbors = list(graph.neighbors(u))
        h = graph.copy()
        h.remove_node(u)
        min_cycle = float("inf")

        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                v1, v2 = neighbors[i], neighbors[j]
                if nx.has_path(h, v1, v2):
                    p_len = nx.shortest_path_length(h, v1, v2)
                    min_cycle = min(min_cycle, p_len + 2)

        smallest_rings[u] = int(min_cycle) if min_cycle != float("inf") else 0

    return smallest_rings


def compute_node_invariant(
    graph: nx.Graph,
    u: Any,
    smallest_rings: dict[Any, int] | None = None,
) -> tuple[int, int, int, int, int, int]:
    """Computes deterministic node invariant vector I(u).

    I(u) = (atomic_number, degree, formal_charge, hybridization_int, implicit_hydrogens, ring_size_smallest)
    """
    ndata = graph.nodes[u]
    atomic_num = int(ndata.get("atomic_number", 0))
    if atomic_num == 0 and "symbol" in ndata:
        sym = str(ndata["symbol"]).strip()
        try:
            atomic_num = int(element(sym).atomic_number)
        except Exception:
            atomic_num = 0

    degree = int(graph.degree(u))
    formal_charge = int(ndata.get("formal_charge", 0))

    hyb_val = ndata.get("hybridization", "sp3")
    if isinstance(hyb_val, int):
        hyb_int = hyb_val
    else:
        hyb_str = str(hyb_val).strip().lower()
        hyb_int = HYBRIDIZATION_MAP.get(hyb_str, 0)

    implicit_h = int(ndata.get("implicit_hydrogens", ndata.get("num_h", 0)))
    ring_sz = smallest_rings.get(u, 0) if smallest_rings is not None else 0

    return (atomic_num, degree, formal_charge, hyb_int, implicit_h, ring_sz)


class TopologicalCanonicalizer:
    """Deterministic graph canonicalizer using 1-WL color refinement and McKay search tree."""

    @classmethod
    def _refine_partition(
        cls,
        graph: nx.Graph,
        partition: list[list[Any]],
    ) -> list[list[Any]]:
        """Iterative 1-WL color refinement on ordered partition until stabilization."""
        while True:
            node_to_cell: dict[Any, int] = {}
            for c_idx, cell in enumerate(partition):
                for node in cell:
                    node_to_cell[node] = c_idx

            new_partition: list[list[Any]] = []
            any_split = False

            for cell in partition:
                if len(cell) <= 1:
                    new_partition.append(cell)
                    continue

                sig_groups: dict[int, list[Any]] = {}
                for node in cell:
                    neighbor_entries: list[tuple[float, bool, int]] = []
                    for nbr in graph.neighbors(node):
                        edata = graph[node][nbr]
                        bo = round(float(edata.get("bond_order", 1.0)), 3)
                        arom = bool(edata.get("aromatic", False))
                        neighbor_entries.append((bo, arom, node_to_cell[nbr]))

                    sig_hash = deterministic_hash64((node_to_cell[node], tuple(sorted(neighbor_entries))))
                    sig_groups.setdefault(sig_hash, []).append(node)

                if len(sig_groups) > 1:
                    any_split = True
                    # Deterministic ordering of newly created cells by 64-bit signature
                    for s_hash in sorted(sig_groups.keys()):
                        new_partition.append(sig_groups[s_hash])
                else:
                    new_partition.append(cell)

            partition = new_partition
            if not any_split:
                break

        return partition

    @classmethod
    def _build_certificate(
        cls,
        graph: nx.Graph,
        ordering: list[Any],
        node_invariants: dict[Any, tuple[int, int, int, int, int, int]],
    ) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        """Builds a canonical certificate for a candidate total vertex ordering."""
        n = len(ordering)
        inv_seq = tuple(node_invariants[v] for v in ordering)
        edge_seq: list[tuple[int, int, float, bool, str]] = []

        for i in range(n):
            for j in range(i + 1, n):
                u, v = ordering[i], ordering[j]
                if graph.has_edge(u, v):
                    edata = graph[u][v]
                    bo = round(float(edata.get("bond_order", 1.0)), 4)
                    arom = bool(edata.get("aromatic", False))
                    stereo = str(edata.get("stereo", ""))
                    edge_seq.append((i, j, bo, arom, stereo))

        return (inv_seq, tuple(edge_seq))

    @classmethod
    def _mckay_search(
        cls,
        graph: nx.Graph,
        partition: list[list[Any]],
        node_invariants: dict[Any, tuple[int, int, int, int, int, int]],
        best_holder: list[Any],
        leaf_counter: list[int],
        max_leaves: int,
    ) -> None:
        """Recursive individualization-refinement search tree for tie-breaking."""
        refined = cls._refine_partition(graph, partition)
        non_singletons = [i for i, cell in enumerate(refined) if len(cell) > 1]

        if not non_singletons:
            ordering = [cell[0] for cell in refined]
            cert = cls._build_certificate(graph, ordering, node_invariants)
            leaf_counter[0] += 1
            if leaf_counter[0] > max_leaves:
                raise TopologicalCanonicalizationError(
                    f"Canonicalization exceeded search tree limit of {max_leaves} leaves."
                )

            if best_holder[0] is None or cert < best_holder[0]:
                best_holder[0] = cert
                best_holder[1] = ordering
            return

        # Deterministically select first non-singleton cell
        target_idx = non_singletons[0]
        target_cell = refined[target_idx]

        for u in target_cell:
            rest = [x for x in target_cell if x != u]
            new_part = refined[:target_idx] + [[u], rest] + refined[target_idx + 1 :]
            cls._mckay_search(graph, new_part, node_invariants, best_holder, leaf_counter, max_leaves)

    @classmethod
    def canonicalize(
        cls,
        graph: TopologyGraph,
        max_leaves: int = 5000,
    ) -> tuple[TopologyGraph, dict[Any, int]]:
        """Transforms graph into canonical topological representation.

        Returns:
            (canonical_graph, permutation_map)
            where canonical_graph has nodes [0..N-1] and identical adjacency across permutations,
            and permutation_map maps original_node_id -> canonical_node_id.
        """
        if graph is None:
            raise TopologicalCanonicalizationError("Input graph cannot be None.")
        if not isinstance(graph, nx.Graph):
            raise TopologicalCanonicalizationError(f"Expected networkx.Graph or TopologyGraph, got {type(graph)}")

        n_nodes = graph.number_of_nodes()
        if n_nodes == 0:
            return TopologyGraph(), {}

        if n_nodes == 1:
            only_node = next(iter(graph.nodes()))
            canon = TopologyGraph()
            canon.add_chemical_node(0, **graph.nodes[only_node])
            return canon, {only_node: 0}

        # Step 1: Invariant perception
        smallest_rings = compute_smallest_rings(graph)
        node_invariants = {
            u: compute_node_invariant(graph, u, smallest_rings)
            for u in graph.nodes()
        }

        # Step 2: Initial partition by node invariant
        init_cell_map: dict[int, list[Any]] = {}
        for u, inv in node_invariants.items():
            inv_hash = deterministic_hash64(inv)
            init_cell_map.setdefault(inv_hash, []).append(u)

        init_partition = [init_cell_map[h] for h in sorted(init_cell_map.keys())]

        # Step 3: McKay search tree with 1-WL refinement
        best_holder: list[Any] = [None, None]
        leaf_counter: list[int] = [0]
        cls._mckay_search(
            graph=graph,
            partition=init_partition,
            node_invariants=node_invariants,
            best_holder=best_holder,
            leaf_counter=leaf_counter,
            max_leaves=max_leaves,
        )

        best_ordering: list[Any] = best_holder[1]
        if best_ordering is None:
            raise TopologicalCanonicalizationError("Failed to determine canonical node ordering.")

        # Step 4: Construct canonical TopologyGraph and bijective map
        perm_map: dict[Any, int] = {
            orig_id: canon_idx for canon_idx, orig_id in enumerate(best_ordering)
        }

        canonical_graph = TopologyGraph()
        for canon_idx, orig_id in enumerate(best_ordering):
            orig_data = dict(graph.nodes[orig_id])
            canonical_graph.add_chemical_node(canon_idx, **orig_data)

        for u, v, edata in graph.edges(data=True):
            cu = perm_map[u]
            cv = perm_map[v]
            canonical_graph.add_chemical_edge(min(cu, cv), max(cu, cv), **dict(edata))

        return canonical_graph, perm_map

    @classmethod
    def compute_canonical_hash(cls, graph: TopologyGraph) -> str:
        """Computes deterministic SHA-256 hash string from canonicalized topology."""
        if graph is None:
            raise TopologicalCanonicalizationError("Input graph cannot be None.")

        canon_graph, _ = cls.canonicalize(graph)

        # Serialize canonical nodes
        canonical_nodes: list[dict[str, Any]] = []
        for i in sorted(canon_graph.nodes()):
            ndata = canon_graph.nodes[i]
            canonical_nodes.append({
                "id": int(i),
                "symbol": str(ndata.get("symbol", "")),
                "atomic_number": int(ndata.get("atomic_number", 0)),
                "formal_charge": int(ndata.get("formal_charge", 0)),
                "hybridization": str(ndata.get("hybridization", "sp3")),
                "in_ring": bool(ndata.get("in_ring", False)),
            })

        # Serialize canonical edges
        canonical_edges: list[dict[str, Any]] = []
        for u, v, edata in canon_graph.edges(data=True):
            cu, cv = min(int(u), int(v)), max(int(u), int(v))
            canonical_edges.append({
                "u": cu,
                "v": cv,
                "bond_order": round(float(edata.get("bond_order", 1.0)), 4),
                "aromatic": bool(edata.get("aromatic", False)),
                "in_ring": bool(edata.get("in_ring", False)),
                "stereo": edata.get("stereo", None),
            })

        canonical_edges.sort(key=lambda e: (e["u"], e["v"]))

        payload_dict = {
            "nodes": canonical_nodes,
            "edges": canonical_edges,
        }
        serialized_payload = json.dumps(payload_dict, sort_keys=True)
        return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()
