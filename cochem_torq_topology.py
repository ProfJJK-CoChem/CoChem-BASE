"""
CoChem-TORQ: Phase 2 Topological Math Engine & Ring Strain Guard
================================================================
Automates the graph-theoretical identification of rotatable dihedrals
and prevents unphysical macrocyclic ring shattering via ring-strain protection.

Authoritative Standards:
- Method Matrix: Stage 1.0 - 2.0 Molecular Topology & Dihedral Optimization
- Pyykkö & Atsumi (2008) / Alvarez (2008) Covalent Radii Standards
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

import networkx as nx
import numpy as np

from cochem_torq_vault import CIAAW_ISOTOPIC_MASSES

logger = logging.getLogger("CoChem-TORQ.Topology")

# Pyykkö Covalent Radii in Angstroms (single bond)
COVALENT_RADII_ANG: Dict[str, float] = {
    "H": 0.31,
    "He": 0.28,
    "Li": 1.28,
    "Be": 0.96,
    "B": 0.84,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "F": 0.57,
    "Ne": 0.58,
    "Na": 1.66,
    "Mg": 1.41,
    "Al": 1.21,
    "Si": 1.11,
    "P": 1.07,
    "S": 1.05,
    "Cl": 1.02,
    "Ar": 1.06,
    "K": 2.03,
    "Ca": 1.76,
    "Br": 1.20,
    "I": 1.39,
}


def build_molecular_graph(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    scale_factor: float = 1.25,
) -> nx.Graph:
    """
    Constructs a NetworkX connectivity graph from 3D atomic coordinates
    and empirical covalent radii.
    """
    n_atoms = len(symbols)
    g = nx.Graph()

    for i in range(n_atoms):
        sym = symbols[i].capitalize()
        g.add_node(
            i,
            symbol=sym,
            mass=CIAAW_ISOTOPIC_MASSES.get(sym, 12.0),
            coord=coordinates[i],
        )

    diff = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]
    dist_mat = np.sqrt(np.sum(diff**2, axis=-1))

    for i in range(n_atoms):
        sym_i = symbols[i].capitalize()
        r_i = COVALENT_RADII_ANG.get(sym_i, 0.76)
        for j in range(i + 1, n_atoms):
            sym_j = symbols[j].capitalize()
            r_j = COVALENT_RADII_ANG.get(sym_j, 0.76)
            bond_thresh = (r_i + r_j) * scale_factor
            if dist_mat[i, j] <= bond_thresh:
                g.add_edge(i, j, distance=float(dist_mat[i, j]))

    return g


def ring_strain_guard(
    graph: nx.Graph,
    dihedral: Tuple[int, int, int, int],
) -> bool:
    """
    Algorithmically identifies whether the central bond (j, k) of a 4-atom
    dihedral (i, j, k, l) resides within a closed loop (such as a phenyl ring).
    Returns True if the dihedral is ring-locked (rotation forbidden), False if acyclic/free.
    """
    _, j, k, _ = dihedral

    if not graph.has_edge(j, k):
        return False

    # Check all cycle bases in graph
    cycles = nx.cycle_basis(graph)
    for cycle in cycles:
        cycle_len = len(cycle)
        for idx in range(cycle_len):
            u = cycle[idx]
            v = cycle[(idx + 1) % cycle_len]
            if (u == j and v == k) or (u == k and v == j):
                logger.debug(
                    "Dihedral (%d, %d, %d, %d) central bond (%d, %d) is in cycle of size %d",
                    *dihedral,
                    j,
                    k,
                    cycle_len,
                )
                return True

    return False


def detect_5_option_dihedrals(
    symbols: Sequence[str],
    coordinates: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Utilizes NetworkX graph-cleaving to isolate the rotatable bonds (e.g. C-C, C-O, C-N)
    and determine the exact 4-atom dihedral anchors (i, j, k, l).
    Returns up to 5 best dihedral options prioritized by substituent mass and rotational significance.
    """
    graph = build_molecular_graph(symbols, coordinates)
    candidates: List[Dict[str, Any]] = []

    # Iterate over all internal edges
    for u, v in graph.edges():
        # A rotatable bond must be non-terminal: both u and v must have degree >= 2
        deg_u = graph.degree(u)
        deg_v = graph.degree(v)

        if deg_u < 2 or deg_v < 2:
            continue

        # Find neighbors of u (excluding v) and neighbors of v (excluding u)
        u_nbrs = [n for n in graph.neighbors(u) if n != v]
        v_nbrs = [n for n in graph.neighbors(v) if n != u]

        if not u_nbrs or not v_nbrs:
            continue

        # Pick heaviest neighbor for anchor i attached to u, and anchor l attached to v
        u_nbrs.sort(key=lambda n: graph.nodes[n]["mass"], reverse=True)
        v_nbrs.sort(key=lambda n: graph.nodes[n]["mass"], reverse=True)

        best_i = u_nbrs[0]
        best_l = v_nbrs[0]

        dihedral_tuple = (best_i, u, v, best_l)
        is_ring_locked = ring_strain_guard(graph, dihedral_tuple)

        # Rotational importance score based on substituent masses
        score = (graph.nodes[best_i]["mass"] + graph.nodes[u]["mass"]) * (
            graph.nodes[v]["mass"] + graph.nodes[best_l]["mass"]
        )

        candidates.append(
            {
                "dihedral": dihedral_tuple,
                "central_bond": (u, v),
                "central_bond_symbols": (graph.nodes[u]["symbol"], graph.nodes[v]["symbol"]),
                "is_ring_locked": is_ring_locked,
                "rotational_score": float(score),
                "degrees": (deg_u, deg_v),
            }
        )

    # Sort: acyclic free rotors first, then by rotational score descending
    candidates.sort(
        key=lambda item: (not item["is_ring_locked"], item["rotational_score"]), reverse=True
    )

    # Return top 5
    top_5 = candidates[:5]
    logger.info("Detected %d candidate dihedrals, returning top %d", len(candidates), len(top_5))
    return top_5


def select_active_torsions(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    requested_dihedrals: Optional[List[Tuple[int, int, int, int]]] = None,
) -> List[Dict[str, Any]]:
    """
    Selects valid active torsional coordinates for potential energy surface scans.
    If a requested dihedral violates the ring strain guard, an override warning is logged,
    and execution falls back to available free rotors.
    """
    graph = build_molecular_graph(symbols, coordinates)
    detected = detect_5_option_dihedrals(symbols, coordinates)
    active_dihedrals: List[Dict[str, Any]] = []

    if requested_dihedrals:
        for req in requested_dihedrals:
            is_locked = ring_strain_guard(graph, req)
            if is_locked:
                logger.warning(
                    "Ring strain guard triggered: Dihedral %s is locked inside a ring structure. "
                    "Overriding input to prevent unphysical macrocyclic shattering.",
                    req,
                )
            else:
                u, v = req[1], req[2]
                active_dihedrals.append(
                    {
                        "dihedral": req,
                        "central_bond": (u, v),
                        "is_ring_locked": False,
                        "status": "APPROVED",
                    }
                )

    # If no approved requested dihedrals, fallback to top detected free rotors
    if not active_dihedrals:
        free_rotors = [cand for cand in detected if not cand["is_ring_locked"]]
        if free_rotors:
            chosen = free_rotors[0]
            logger.info("Falling back to top free rotor: %s", chosen["dihedral"])
            active_dihedrals.append(
                {
                    "dihedral": chosen["dihedral"],
                    "central_bond": chosen["central_bond"],
                    "is_ring_locked": False,
                    "status": "FALLBACK_FREE_ROTOR",
                }
            )
        elif detected:
            # All rotors are in rings; use with warning
            logger.warning("No free acyclic rotors found; using primary ring dihedral.")
            chosen = detected[0]
            active_dihedrals.append(
                {
                    "dihedral": chosen["dihedral"],
                    "central_bond": chosen["central_bond"],
                    "is_ring_locked": True,
                    "status": "RING_LOCKED_WARNING",
                }
            )

    return active_dihedrals
