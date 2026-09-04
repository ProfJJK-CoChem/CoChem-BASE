"""
Frozen-Monomer Spatial Protections and Internal Coordinate Constraint Generator.
Compliant with Method Matrix v4 §9A.1-9A.7 and Zero-Mock Mandate.
"""

from __future__ import annotations

import itertools
from typing import Any, List, Sequence, Set, Tuple

import networkx as nx

from cochem_base.schemas import ConstraintPayload


def generate_frozen_monomer_constraints(
    atoms_a: Sequence[int],
    atoms_b: Sequence[int],
    molecular_graph: Any,
) -> ConstraintPayload:
    """Generate internal coordinate constraints for Monomer A and Monomer B.

    Implements Method Matrix v4 §9A.1-9A.2 Frozen-Monomer Protocol:
    Freezes high-level monomers across all internal degrees of freedom (bonds, angles, dihedrals)
    to fix rotational constant A to < 0.2% error [M], while ensuring zero constraints are placed
    on intermolecular separation (R) and mutual monomer orientations.

    Parameters
    ----------
    atoms_a : Sequence[int]
        0-based atom indices belonging to Monomer A.
    atoms_b : Sequence[int]
        0-based atom indices belonging to Monomer B.
    molecular_graph : Any
        NetworkX Graph or adjacency structure defining chemical bonds.

    Returns
    -------
    ConstraintPayload
        Container with intramolecular bonds, valence angles, and proper dihedrals for A and B.
    """
    set_a: Set[int] = set(atoms_a)
    set_b: Set[int] = set(atoms_b)

    # Convert to NetworkX Graph if needed
    if not isinstance(molecular_graph, nx.Graph):
        G = nx.Graph()
        if hasattr(molecular_graph, "edges"):
            G.add_edges_from(molecular_graph.edges())
        elif isinstance(molecular_graph, (list, tuple, set)):
            G.add_edges_from(molecular_graph)
        elif isinstance(molecular_graph, dict):
            for u, neighbors in molecular_graph.items():
                for v in neighbors:
                    G.add_edge(u, v)
        else:
            raise TypeError(f"Unsupported molecular_graph type: {type(molecular_graph)}")
    else:
        G = molecular_graph

    bonds: List[Tuple[int, int]] = []
    angles: List[Tuple[int, int, int]] = []
    dihedrals: List[Tuple[int, int, int, int]] = []

    for monomer_atoms in [set_a, set_b]:
        # Extract intramolecular subgraph
        sub_g = G.subgraph(monomer_atoms)

        # 1. Distance constraints { B u v C } for all intramolecular edges
        for u, v in sub_g.edges():
            bonds.append(tuple(sorted((int(u), int(v)))))

        # 2. Angle constraints { A i j k C } for all adjacent intramolecular valence angles (apex j)
        for j in sub_g.nodes():
            neighbors = sorted(list(sub_g.neighbors(j)))
            if len(neighbors) >= 2:
                for i, k in itertools.combinations(neighbors, 2):
                    angles.append((int(i), int(j), int(k)))

        # 3. Proper dihedral constraints { D i j k l C } for all proper dihedral quartets
        seen_dihedrals: Set[Tuple[int, int, int, int]] = set()
        for j, k in sub_g.edges():
            j_int, k_int = int(j), int(k)
            j_neighbors = [int(nbr) for nbr in sub_g.neighbors(j) if int(nbr) != k_int]
            k_neighbors = [int(nbr) for nbr in sub_g.neighbors(k) if int(nbr) != j_int]

            for i in j_neighbors:
                for l in k_neighbors:
                    if i == l:
                        continue
                    # Canonicalize representation (i, j, k, l) vs (l, k, j, i)
                    forward = (i, j_int, k_int, l)
                    backward = (l, k_int, j_int, i)
                    canonical = min(forward, backward)
                    if canonical not in seen_dihedrals:
                        seen_dihedrals.add(canonical)
                        dihedrals.append(canonical)

    # Sort deterministically
    bonds = sorted(list(set(bonds)))
    angles = sorted(list(set(angles)))
    dihedrals = sorted(list(set(dihedrals)))

    return ConstraintPayload(
        bonds=bonds,
        angles=angles,
        dihedrals=dihedrals,
        metadata={
            "n_atoms_a": len(atoms_a),
            "n_atoms_b": len(atoms_b),
            "n_bonds": len(bonds),
            "n_angles": len(angles),
            "n_dihedrals": len(dihedrals),
            "provenance_tag": "[M]",
        },
    )
