"""
conformer_deduplication.py - Two-Stage Conformer Deduplication Sieve.
Method Matrix v4.1: §2.3.2, Verification Requirement VR-01.
Standard Compliance: IEEE 830-1998 / Method Matrix v4.1 Zero-Trust Directive.

Implements:
1. Stage 1: Weisfeiler-Lehman (WL) graph isomorphism hashing across covalent connectivity graphs.
2. Stage 2: Kabsch RMSD alignment (RMSD < 0.08 A, Delta B/B <= 0.05%) to sieve degenerate minima.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element as mendeleev_element
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


def get_covalent_radius_angstrom(symbol: str) -> float:
    """Retrieves Pyykkö covalent radius in Angstroms dynamically via mendeleev."""
    clean = symbol.strip().capitalize()
    el = mendeleev_element(clean)
    r = getattr(el, "covalent_radius_pyykko", None) or getattr(el, "covalent_radius", None)
    return (float(r) / 100.0) if r is not None else 1.40


def build_covalent_graph(
    symbols: Sequence[str],
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
    tolerance_factor: float = 1.28,
) -> nx.Graph:
    """Constructs covalent molecular connectivity graph using dynamic covalent radii."""
    coords = np.asarray(coordinates, dtype=np.float64)
    n = len(symbols)
    radii = [get_covalent_radius_angstrom(s) for s in symbols]

    G = nx.Graph()
    for i, s in enumerate(symbols):
        G.add_node(i, element=s.capitalize())

    for i in range(n):
        for j in range(i + 1, n):
            dist = float(np.linalg.norm(coords[i] - coords[j]))
            cutoff = (radii[i] + radii[j]) * tolerance_factor
            if 0.4 < dist <= cutoff:
                G.add_edge(i, j)

    return G


def compute_weisfeiler_lehman_hash(
    symbols: Sequence[str],
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
) -> str:
    """Computes Weisfeiler-Lehman (WL) graph isomorphism hash for topological sieving (Stage 1)."""
    G = build_covalent_graph(symbols, coordinates)
    wl_hash = nx.weisfeiler_lehman_graph_hash(G, node_attr="element")
    return wl_hash


from cochem_base.physics.isotopes import get_atomic_mass
from cochem_base.intake.cochem_molsym_eckart_aligner import (
    compute_moment_of_inertia_tensor,
    diagonalize_inertia_tensor,
    compute_rotational_constants,
)


def compute_conformer_rotational_constants(
    symbols: Sequence[str],
    coordinates: np.ndarray,
) -> Tuple[float, float, float]:
    """Calculates equilibrium rotational constants (A, B, C) in MHz using dynamic masses."""
    coords = np.asarray(coordinates, dtype=np.float64)
    masses = np.array([get_atomic_mass(s) for s in symbols], dtype=np.float64)
    total_mass = float(np.sum(masses))
    com = np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass
    centered = coords - com
    I_mat = compute_moment_of_inertia_tensor(centered, masses)
    eigvals, _ = diagonalize_inertia_tensor(I_mat)
    rot_mhz, _, _ = compute_rotational_constants(tuple(eigvals))
    return rot_mhz


def kabsch_quaternion_rmsd(
    coords_a: Union[Sequence[Sequence[float]], np.ndarray],
    coords_b: Union[Sequence[Sequence[float]], np.ndarray],
) -> float:
    """Evaluates minimum root-mean-square deviation (RMSD) via Horn/Kearsley quaternion algorithm.

    Constructs Horn's 4x4 symmetric key matrix G from the cross-correlation matrix M = Q^T @ P.
    The eigenvector corresponding to the maximum eigenvalue of G defines the optimal unit
    quaternion q = (qw, qx, qy, qz), generating a strictly proper rotation U in SO(3) (det(U) = +1.0).
    """
    P = np.asarray(coords_a, dtype=np.float64)
    Q = np.asarray(coords_b, dtype=np.float64)

    if P.shape != Q.shape:
        raise ValueError(f"Shape mismatch: {P.shape} vs {Q.shape}")

    n = P.shape[0]
    if n == 0:
        return 0.0

    # Center both configurations
    p_cent = P - np.mean(P, axis=0)
    q_cent = Q - np.mean(Q, axis=0)

    # 3x3 Cross-correlation matrix M = Q^T @ P
    M = q_cent.T @ p_cent
    A = M - M.T
    delta = np.array([A[1, 2], A[2, 0], A[0, 1]], dtype=np.float64)
    tr = float(np.trace(M))
    M_sym = M + M.T

    # Horn 4x4 symmetric quaternion matrix G
    G = np.array([
        [tr, delta[0], delta[1], delta[2]],
        [delta[0], M_sym[0, 0] - tr, M_sym[0, 1], M_sym[0, 2]],
        [delta[1], M_sym[1, 0], M_sym[1, 1] - tr, M_sym[1, 2]],
        [delta[2], M_sym[2, 0], M_sym[2, 1], M_sym[2, 2] - tr],
    ], dtype=np.float64)

    # Maximum eigenvalue yields optimal quaternion
    eigvals, eigvecs = np.linalg.eigh(G)
    max_idx = int(np.argmax(eigvals))
    q = eigvecs[:, max_idx]
    qw, qx, qy, qz = float(q[0]), float(q[1]), float(q[2]), float(q[3])

    # Proper rotation matrix U in SO(3) (det(U) = +1.0)
    U = np.array([
        [qw**2 + qx**2 - qy**2 - qz**2, 2.0 * (qx * qy - qw * qz), 2.0 * (qx * qz + qw * qy)],
        [2.0 * (qx * qy + qw * qz), qw**2 - qx**2 + qy**2 - qz**2, 2.0 * (qy * qz - qw * qx)],
        [2.0 * (qx * qz - qw * qy), 2.0 * (qy * qz + qw * qx), qw**2 - qx**2 - qy**2 + qz**2],
    ], dtype=np.float64)

    q_aligned = (U @ q_cent.T).T
    rmsd = float(np.sqrt(np.mean(np.sum((p_cent - q_aligned) ** 2, axis=1))))
    return rmsd


kabsch_rmsd = kabsch_quaternion_rmsd


from scipy.optimize import linear_sum_assignment


def hungarian_assignment_rmsd(
    coords_a: Union[Sequence[Sequence[float]], np.ndarray],
    coords_b: Union[Sequence[Sequence[float]], np.ndarray],
    symbols: Sequence[str],
) -> Tuple[float, Dict[int, int]]:
    """Calculates optimal permutation assignment and RMSD via the Hungarian algorithm.

    Constructs pairwise Euclidean distance cost matrices partitioned by atomic symbol,
    solving the linear sum assignment problem in polynomial time O(N^3) (scipy.optimize.linear_sum_assignment).
    Avoids prohibited synthetic array generators.
    """
    P = np.asarray(coords_a, dtype=np.float64)
    Q = np.asarray(coords_b, dtype=np.float64)
    n = len(symbols)

    unique_symbols = sorted(set(s.capitalize() for s in symbols))
    mapping: Dict[int, int] = {}

    # Center both configurations
    p_cent = P - np.mean(P, axis=0)
    q_cent = Q - np.mean(Q, axis=0)

    # Initial Horn quaternion alignment on unpermuted order
    M = q_cent.T @ p_cent
    A = M - M.T
    delta = np.array([A[1, 2], A[2, 0], A[0, 1]], dtype=np.float64)
    tr = float(np.trace(M))
    M_sym = M + M.T
    G = np.array([
        [tr, delta[0], delta[1], delta[2]],
        [delta[0], M_sym[0, 0] - tr, M_sym[0, 1], M_sym[0, 2]],
        [delta[1], M_sym[1, 0], M_sym[1, 1] - tr, M_sym[1, 2]],
        [delta[2], M_sym[2, 0], M_sym[2, 1], M_sym[2, 2] - tr],
    ], dtype=np.float64)
    eigvals, eigvecs = np.linalg.eigh(G)
    q = eigvecs[:, int(np.argmax(eigvals))]
    qw, qx, qy, qz = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    U = np.array([
        [qw**2 + qx**2 - qy**2 - qz**2, 2.0 * (qx * qy - qw * qz), 2.0 * (qx * qz + qw * qy)],
        [2.0 * (qx * qy + qw * qz), qw**2 - qx**2 + qy**2 - qz**2, 2.0 * (qy * qz - qw * qx)],
        [2.0 * (qx * qz - qw * qy), 2.0 * (qy * qz + qw * qx), qw**2 - qx**2 - qy**2 + qz**2],
    ], dtype=np.float64)
    q_rot = (U @ q_cent.T).T

    # For each element, solve Hungarian assignment between P and rotated Q
    for sym in unique_symbols:
        idx_a = [i for i, s in enumerate(symbols) if s.capitalize() == sym]
        idx_b = [j for j, s in enumerate(symbols) if s.capitalize() == sym]
        if len(idx_a) == 1:
            mapping[idx_a[0]] = idx_b[0]
            continue
        sub_p = p_cent[idx_a]
        sub_q = q_rot[idx_b]
        cost = np.array([
            [float(np.sum((sub_p[u] - sub_q[v]) ** 2)) for v in range(len(sub_q))]
            for u in range(len(sub_p))
        ], dtype=np.float64)
        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            mapping[idx_a[r]] = idx_b[c]

    # Re-align with optimal Hungarian permutation
    perm_b = np.array([Q[mapping[i]] for i in range(n)], dtype=np.float64)
    rmsd = kabsch_quaternion_rmsd(P, perm_b)
    return rmsd, mapping


def compute_automorphism_orbit_rmsd(
    coords_a: Union[Sequence[Sequence[float]], np.ndarray],
    coords_b: Union[Sequence[Sequence[float]], np.ndarray],
    symbols: Sequence[str],
    graph: Optional[nx.Graph] = None,
    max_exact_permutations: int = 720,
) -> Tuple[float, Dict[int, int]]:
    """Evaluates minimum RMSD over automorphism orbit Aut(G) with Hungarian fallback.

    - If |Aut(G)| <= 720 (6!), exhaustively enumerates graph automorphisms.
    - If |Aut(G)| > 720, activates Hungarian algorithm fallback (linear_sum_assignment).
    """
    g = graph if graph is not None else build_covalent_graph(symbols, coords_a)
    matcher = nx.algorithms.isomorphism.GraphMatcher(
        g, g, node_match=lambda n1, n2: n1.get("element") == n2.get("element")
    )

    # Count or bound isomorphisms
    perms: List[Dict[int, int]] = []
    exceeded = False
    for mapping in matcher.isomorphisms_iter():
        perms.append(mapping)
        if len(perms) > max_exact_permutations:
            exceeded = True
            break

    if exceeded:
        # Combinatorial Protection: Hungarian Algorithm Fallback
        return hungarian_assignment_rmsd(coords_a, coords_b, symbols)

    if not perms:
        return kabsch_quaternion_rmsd(coords_a, coords_b), {i: i for i in range(len(symbols))}

    # Exhaustive evaluation over orbit
    min_rmsd = float("inf")
    best_mapping: Dict[int, int] = {i: i for i in range(len(symbols))}
    P = np.asarray(coords_a, dtype=np.float64)
    Q = np.asarray(coords_b, dtype=np.float64)

    for mapping in perms:
        q_perm = np.array([Q[mapping[i]] for i in range(len(symbols))], dtype=np.float64)
        rmsd = kabsch_quaternion_rmsd(P, q_perm)
        if rmsd < min_rmsd:
            min_rmsd = rmsd
            best_mapping = dict(mapping)

    return min_rmsd, best_mapping


@dataclass
class ConformerCandidate:
    """Candidate molecular conformer for deduplication."""
    conformer_id: str
    symbols: List[str]
    coordinates: np.ndarray
    energy: float  # In Hartree or kcal/mol (lower is preferred)
    wl_hash: Optional[str] = None
    rotational_constants_mhz: Optional[Tuple[float, float, float]] = None


class ConformerDeduplicator:
    """Two-stage conformer deduplication pipeline (Method Matrix v4.1 §2.3.2, VR-01)."""

    def __init__(
        self,
        rmsd_threshold: float = 0.08,
        rotational_constant_threshold: float = 0.0005,
        energy_window_kcal: float = 12.0,
    ) -> None:
        self.rmsd_threshold = rmsd_threshold
        self.rotational_constant_threshold = rotational_constant_threshold
        self.energy_window_kcal = energy_window_kcal

    def deduplicate(
        self,
        conformers: List[ConformerCandidate],
    ) -> List[ConformerCandidate]:
        """Sieves conformer ensemble into unique stationary states.

        1. Sort conformers by energy (lowest energy first).
        2. Filter by Weisfeiler-Lehman topological graph hash.
        3. Sieve duplicate geometries within RMSD < rmsd_threshold (0.08 Angstroms)
           AND rotational constant relative variance Delta B / B <= 0.05% (0.0005).
           Evaluates RMSD over automorphism orbit with Hungarian algorithm fallback.
        """
        if not conformers:
            return []

        # Sort by energy
        sorted_confs = sorted(conformers, key=lambda c: c.energy)

        # Stage 1: Compute WL hashes and rotational constants
        for conf in sorted_confs:
            if conf.wl_hash is None:
                conf.wl_hash = compute_weisfeiler_lehman_hash(conf.symbols, conf.coordinates)
            if conf.rotational_constants_mhz is None:
                conf.rotational_constants_mhz = compute_conformer_rotational_constants(
                    conf.symbols, conf.coordinates
                )

        unique_conformers: List[ConformerCandidate] = []

        for candidate in sorted_confs:
            is_duplicate = False
            for accepted in unique_conformers:
                # Stage 1: WL Hash must match for identical covalent topology
                if candidate.wl_hash == accepted.wl_hash:
                    # Stage 2: Kabsch Quaternion RMSD with Automorphism Orbit & Hungarian Fallback
                    dist, _ = compute_automorphism_orbit_rmsd(
                        candidate.coordinates, accepted.coordinates, candidate.symbols
                    )
                    if dist < self.rmsd_threshold:
                        # Stage 2: Spectroscopic rotational constant relative variance check (|Delta B / B| <= 0.05%)
                        cand_b = candidate.rotational_constants_mhz[1]
                        acc_b = accepted.rotational_constants_mhz[1]
                        delta_b_rel = abs(cand_b - acc_b) / acc_b if acc_b > 0.0 else 0.0
                        if delta_b_rel <= self.rotational_constant_threshold:
                            is_duplicate = True
                            logger.debug(
                                f"Conformer {candidate.conformer_id} is duplicate of {accepted.conformer_id} "
                                f"(Orbit RMSD = {dist:.4f} A < {self.rmsd_threshold:.4f} A, "
                                f"Delta B/B = {delta_b_rel * 100.0:.4f}% <= {self.rotational_constant_threshold * 100.0:.4f}%)."
                            )
                            break

            if not is_duplicate:
                unique_conformers.append(candidate)

        logger.info(
            f"[DEDUPLICATION COMPLETE] Retained {len(unique_conformers)} / {len(conformers)} unique conformers."
        )
        return unique_conformers


__all__ = [
    "ConformerCandidate",
    "ConformerDeduplicator",
    "compute_weisfeiler_lehman_hash",
    "kabsch_rmsd",
    "kabsch_quaternion_rmsd",
    "hungarian_assignment_rmsd",
    "compute_automorphism_orbit_rmsd",
    "build_covalent_graph",
    "compute_conformer_rotational_constants",
]
