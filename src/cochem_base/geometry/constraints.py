"""Frozen-Monomer Spatial Protections and Internal Coordinate Constraint Generator.

Compliant with Method Matrix v4 §9A.1-9A.7, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
"""

from __future__ import annotations

import itertools
from typing import Any, List, Optional, Sequence, Set, Tuple, Union
from mendeleev import element as mendeleev_element
import networkx as nx
import numpy as np

from cochem_base.schemas import ConstraintPayload


def get_dynamic_covalent_radius(symbol: str) -> float:
    """Retrieve Pyykkö covalent radius in Angstroms via mendeleev."""
    clean = str(symbol).strip().rstrip(":").capitalize()
    el = mendeleev_element(clean)
    if hasattr(el, "covalent_radius_pyykko") and el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if hasattr(el, "covalent_radius") and el.covalent_radius is not None:
        return float(el.covalent_radius) / 100.0
    return 1.40


def build_molecular_graph_from_geometry(
    symbols: Sequence[str],
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
    atom_subsets: Optional[Sequence[Sequence[int]]] = None,
) -> nx.Graph:
    """Build a molecular connectivity graph using dynamic Mendeleev covalent radii.

    If atom_subsets is provided (e.g. [atoms_a, atoms_b]), edges are strictly restricted
    to intramolecular connections within each subset, guaranteeing zero intermolecular edges.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    radii = [get_dynamic_covalent_radius(s) for s in symbols]
    G = nx.Graph()
    G.add_nodes_from(range(len(symbols)))

    subsets = atom_subsets if atom_subsets is not None else [list(range(len(symbols)))]
    for subset in subsets:
        sub_list = sorted(list(subset))
        for idx_i, i in enumerate(sub_list):
            for j in sub_list[idx_i + 1 :]:
                dist = float(np.linalg.norm(coords[i] - coords[j]))
                max_bond = (radii[i] + radii[j]) * 1.28
                if 0.4 < dist <= max_bond:
                    G.add_edge(i, j)

    return G


def generate_frozen_monomer_constraints(
    atoms_a: Sequence[int],
    atoms_b: Sequence[int],
    molecular_graph: Any = None,
    symbols: Optional[Sequence[str]] = None,
    coordinates: Optional[Union[Sequence[Sequence[float]], np.ndarray]] = None,
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
    molecular_graph : Any, optional
        NetworkX Graph or adjacency structure defining chemical bonds.
    symbols : Sequence[str], optional
        Atomic symbols of the complex (used to build graph if not provided).
    coordinates : Sequence[Sequence[float]] | np.ndarray, optional
        Cartesian coordinates in Angstroms (used to build graph if not provided).

    Returns
    -------
    ConstraintPayload
        Container with intramolecular bonds, valence angles, and proper dihedrals for A and B.
    """
    set_a: Set[int] = set(atoms_a)
    set_b: Set[int] = set(atoms_b)

    if molecular_graph is None:
        if symbols is None or coordinates is None:
            raise ValueError(
                "Either molecular_graph or both symbols and coordinates must be provided."
            )
        G = build_molecular_graph_from_geometry(symbols, coordinates, atom_subsets=[atoms_a, atoms_b])
    elif not isinstance(molecular_graph, nx.Graph):
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


def format_orca_frozen_monomer_constraints_block(
    constraints: ConstraintPayload,
    convergence_thresholds: Optional[dict[str, Any]] = None,
) -> str:
    """Format complete ORCA %geom Constraints block for frozen-monomer optimization."""
    thresh = convergence_thresholds or {
        "TolE": "1e-7",
        "TolRMSG": "3e-6",
        "TolMaxG": "1e-5",
        "TolRMSD": "5e-5",
        "TolMaxD": "1e-4",
    }
    lines: list[str] = ["%geom"]
    for k, v in thresh.items():
        lines.append(f"  {k} {v}")

    if constraints.bonds or constraints.angles or constraints.dihedrals:
        lines.append("  Constraints")
        for u, v in constraints.bonds:
            lines.append(f"    {{ B {u} {v} C }}")
        for i, j, k in constraints.angles:
            lines.append(f"    {{ A {i} {j} {k} C }}")
        for i, j, k, l in constraints.dihedrals:
            lines.append(f"    {{ D {i} {j} {k} {l} C }}")
        lines.append("  end")

    lines.append("end")
    return "\n".join(lines)


__all__ = [
    "generate_frozen_monomer_constraints",
    "format_orca_frozen_monomer_constraints_block",
    "build_molecular_graph_from_geometry",
]
