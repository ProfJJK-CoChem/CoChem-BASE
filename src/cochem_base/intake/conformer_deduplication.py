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
import hashlib
from dataclasses import dataclass, field
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from cochem_base.physics.nuclide_resolver import resolve_covalent_radius
from cochem_base.physics.isotopes import GHOST_ATOMS, parse_nuclide_token
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)


def get_covalent_radius_angstrom(symbol: str) -> float:
    """Retrieves Pyykkö covalent radius in Angstroms dynamically via mendeleev."""
    element, _ = parse_nuclide_token(symbol)
    if element.upper() in GHOST_ATOMS:
        return 0.0  # A counterpoise center has no physical covalent radius.
    radius = resolve_covalent_radius(element)
    if radius is None or not np.isfinite(radius) or radius <= 0:
        raise ValueError(f"No physical covalent radius available for {symbol}")
    return radius


def build_covalent_graph(
    symbols: Sequence[str],
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
    tolerance_factor: float = 1.28,
) -> nx.Graph:
    """Constructs covalent molecular connectivity graph using dynamic covalent radii."""
    coords = np.asarray(coordinates, dtype=np.float64)
    n = len(symbols)
    if n == 0 or coords.shape != (n, 3) or not np.all(np.isfinite(coords)):
        raise ValueError("Coordinates must be a nonempty finite (N, 3) array matching symbols")
    if not np.isfinite(tolerance_factor) or tolerance_factor <= 0:
        raise ValueError("Bond tolerance must be finite and positive")
    radii = [get_covalent_radius_angstrom(s) for s in symbols]

    G = nx.Graph()
    for i, s in enumerate(symbols):
        element, number = parse_nuclide_token(s)
        # Nuclide labels prevent isotope swaps from disappearing as permutations.
        label = f"{number or ''}{element}"
        G.add_node(i, element=element, mass_number=number, nuclide=label)

    for i in range(n):
        for j in range(i + 1, n):
            if radii[i] == 0 or radii[j] == 0:
                continue
            dist = float(np.linalg.norm(coords[i] - coords[j]))
            if dist <= 0.4:
                raise ValueError("Conformer has an unphysical nuclear overlap at or below 0.40 angstrom")
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
    return _graph_hash(G)


def _graph_hash(graph: nx.Graph) -> str:
    """Three WL iterations followed by a SHA-256 bin identifier, not proof of isomorphism."""
    signature = nx.weisfeiler_lehman_graph_hash(graph, node_attr="nuclide", iterations=3, digest_size=32)
    return hashlib.sha256(signature.encode("ascii")).hexdigest()


from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
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
    if coords.shape != (len(symbols), 3) or not len(symbols) or not np.isfinite(coords).all():
        raise ValueError("Rotational constants require complete finite molecular coordinates")
    masses = np.array([0.0 if parse_nuclide_token(s)[0].upper() in GHOST_ATOMS else get_nuclide_mass(s) for s in symbols], dtype=np.float64)
    total_mass = float(np.sum(masses))
    if total_mass <= 0 or not np.isfinite(total_mass):
        raise ValueError("Rotational constants require a positive finite physical nuclear mass")
    com = np.sum(coords * masses[:, np.newaxis], axis=0) / total_mass
    centered = coords - com
    I_mat = compute_moment_of_inertia_tensor(centered, masses)
    eigvals, _ = diagonalize_inertia_tensor(I_mat)
    rot_mhz, _, _ = compute_rotational_constants(tuple(eigvals))
    return rot_mhz


def rotational_constants_agree(reference: Sequence[float], candidate: Sequence[float], threshold: float) -> bool:
    """Check every defined principal axis; linear molecules have an undefined A axis."""
    if len(reference) != 3 or len(candidate) != 3:
        raise ValueError("The spectroscopic sieve requires three principal rotational constants")
    finite_axes = 0
    for ref, other in zip(reference, candidate, strict=True):
        if np.isinf(ref) and np.isinf(other) and ref > 0 and other > 0:
            continue
        if not np.isfinite(ref) or not np.isfinite(other) or ref <= 0 or other <= 0:
            return False
        finite_axes += 1
        if abs(ref - other) / ref > threshold:
            return False
    return finite_axes > 0


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
    if P.ndim != 2 or P.shape[1] != 3 or not len(P) or not np.all(np.isfinite(P)) or not np.all(np.isfinite(Q)):
        raise ValueError("RMSD coordinates must be nonempty finite (N, 3) arrays")

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
    *, symbols_b: Optional[Sequence[str]] = None,
) -> Tuple[float, Dict[int, int]]:
    """Calculates optimal permutation assignment and RMSD via the Hungarian algorithm.

    Constructs pairwise Euclidean distance cost matrices partitioned by atomic symbol,
    solving the linear sum assignment problem in polynomial time O(N^3) (scipy.optimize.linear_sum_assignment).
    Avoids prohibited synthetic array generators.
    """
    P = np.asarray(coords_a, dtype=np.float64)
    Q = np.asarray(coords_b, dtype=np.float64)
    n = len(symbols)
    target = symbols if symbols_b is None else symbols_b
    if P.shape != (n, 3) or Q.shape != (n, 3) or len(target) != n or not n or not np.isfinite(P).all() or not np.isfinite(Q).all():
        raise ValueError("Hungarian comparison requires complete finite equal-sized geometries")
    labels_a = [(element, number or 0) for element, number in map(parse_nuclide_token, symbols)]
    labels_b = [(element, number or 0) for element, number in map(parse_nuclide_token, target)]
    if sorted(labels_a) != sorted(labels_b):
        raise ValueError("Hungarian atom matching cannot change ordered nuclear identity composition")
    unique_symbols = sorted(set(labels_a))
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
        idx_a = [i for i, s in enumerate(labels_a) if s == sym]
        idx_b = [j for j, s in enumerate(labels_b) if s == sym]
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
    *,
    symbols_b: Optional[Sequence[str]] = None,
    graph_b: Optional[nx.Graph] = None,
) -> Tuple[float, Dict[int, int]]:
    """Compare actual isomorphic graphs, including differently ordered atoms.

    WL hashes are only a fast sieve, not proof of graph isomorphism. At the
    bounded exact-search limit a Hungarian proposal is accepted only if it
    preserves every labeled bond. An unresolved comparison retains a candidate;
    an unverified atom assignment must never delete a distinct conformer.
    """
    if max_exact_permutations < 1:
        raise ValueError("Exact permutation budget must be positive")
    target_symbols = symbols if symbols_b is None else symbols_b
    g_a = graph if graph is not None else build_covalent_graph(symbols, coords_a)
    g_b = graph_b if graph_b is not None else build_covalent_graph(target_symbols, coords_b)
    matcher = nx.algorithms.isomorphism.GraphMatcher(
        g_a, g_b, node_match=lambda left, right: (
            left.get("element") == right.get("element")
            and left.get("mass_number") == right.get("mass_number")
        ),
    )
    P, Q = np.asarray(coords_a, dtype=float), np.asarray(coords_b, dtype=float)
    minimum, best = float("inf"), {}
    for count, mapping in enumerate(matcher.isomorphisms_iter()):
        if count >= max_exact_permutations:
            rmsd, proposed = hungarian_assignment_rmsd(P, Q, symbols, symbols_b=target_symbols)
            preserves_nodes = all(
                g_a.nodes[i].get("nuclide") == g_b.nodes[j].get("nuclide")
                for i, j in proposed.items()
            )
            preserves_edges = {frozenset((proposed[i], proposed[j])) for i, j in g_a.edges} == {
                frozenset(edge) for edge in g_b.edges
            }
            if preserves_nodes and preserves_edges and rmsd < minimum:
                minimum, best = rmsd, proposed
            break
        rmsd = kabsch_quaternion_rmsd(P, Q[[mapping[i] for i in range(len(symbols))]])
        if rmsd < minimum:
            minimum, best = rmsd, dict(mapping)
        if minimum < 1e-12:
            break
    return minimum, best


def are_duplicate_conformers(
    coordinates_a: np.ndarray,
    symbols_a: Sequence[str],
    coordinates_b: np.ndarray,
    symbols_b: Sequence[str],
    rmsd_threshold: float = 0.08,
    rotational_constant_threshold: float = 0.0005,
) -> bool:
    """Apply the labeled graph, proper rotation RMSD, and spectroscopic gates."""
    graph_a = build_covalent_graph(symbols_a, coordinates_a)
    graph_b = build_covalent_graph(symbols_b, coordinates_b)
    if _graph_hash(graph_a) != _graph_hash(graph_b):
        return False
    rmsd, _ = compute_automorphism_orbit_rmsd(
        coordinates_a, coordinates_b, symbols_a, graph=graph_a,
        graph_b=graph_b, symbols_b=symbols_b,
    )
    if rmsd >= rmsd_threshold:
        return False
    constants_a = compute_conformer_rotational_constants(symbols_a, coordinates_a)
    constants_b = compute_conformer_rotational_constants(symbols_b, coordinates_b)
    return rotational_constants_agree(constants_a, constants_b, rotational_constant_threshold)


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Conformer metadata keys must be explicit strings")
        return MappingProxyType({key: _freeze_metadata(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_metadata(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        if isinstance(value, float) and not np.isfinite(value):
            raise ValueError("Conformer metadata must contain finite observations")
        return value
    raise ValueError("Conformer metadata requires immutable JSON data")


def conformer_metadata_dict(candidate: "ConformerCandidate") -> Dict[str, Any]:
    """Return a writable serialization copy without exposing mutable scientific state."""
    def thaw(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: thaw(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [thaw(item) for item in value]
        return value
    return thaw(candidate.metadata)


@dataclass(frozen=True)
class ConformerCandidate:
    """Candidate molecular conformer for deduplication."""
    conformer_id: str
    symbols: Sequence[str]
    coordinates: np.ndarray
    energy: Optional[float] = None  # Missing energy is unknown, never zero.
    wl_hash: Optional[str] = None
    rotational_constants_mhz: Optional[Tuple[float, float, float]] = None
    energy_unit: str = "hartree"
    source: Optional[str] = None
    charge: Optional[int] = None
    multiplicity: Optional[int] = None
    comparison_protocol: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        labels = tuple(self.symbols)
        array = np.asarray(self.coordinates, dtype=np.float64)
        if not labels or array.shape != (len(labels), 3) or not np.isfinite(array).all():
            raise ValueError("Conformer requires complete finite ordered coordinates")
        # A bytes-backed ndarray cannot have write access restored by its caller.
        immutable = np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)
        object.__setattr__(self, "symbols", labels)
        object.__setattr__(self, "coordinates", immutable)
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        if self.rotational_constants_mhz is not None:
            object.__setattr__(self, "rotational_constants_mhz", tuple(self.rotational_constants_mhz))

    @property
    def energy_kcal(self) -> float:
        if self.energy is None or isinstance(self.energy, bool) or not np.isfinite(self.energy):
            raise ValueError("Conformer energy must be finite")
        if self.energy_unit == "kcal/mol":
            return float(self.energy)
        if self.energy_unit == "hartree":
            from scipy.constants import physical_constants, Avogadro
            return float(self.energy) * physical_constants["Hartree energy"][0] * Avogadro / 4184.0
        raise ValueError("Conformer energy_unit must be hartree or kcal/mol")

    @property
    def comparison_key(self) -> tuple:
        nuclei = tuple(sorted((element, number or 0) for element, number in map(parse_nuclide_token, self.symbols)))
        return nuclei, self.charge, self.multiplicity, self.comparison_protocol


@dataclass(frozen=True)
class ConformerSieveDecision:
    conformer_id: str
    disposition: str
    representative_id: Optional[str]
    reason: str
    wl_hash: str
    relative_energy_kcal: Optional[float] = None
    rmsd_angstrom: Optional[float] = None


@dataclass(frozen=True)
class ConformerSieveResult:
    """Every original pool record remains accounted for, including exclusions."""
    candidates: Tuple[ConformerCandidate, ...]
    retained: Tuple[ConformerCandidate, ...]
    decisions: Tuple[ConformerSieveDecision, ...]


class ConformerDeduplicator:
    """Two-stage conformer deduplication pipeline (Method Matrix v4.1 §2.3.2, VR-01)."""

    def __init__(
        self,
        rmsd_threshold: float = 0.08,
        rotational_constant_threshold: float = 0.0005,
        energy_window_kcal: float = 12.0,
        duplicate_energy_threshold_kcal: float = 0.05,
    ) -> None:
        if not np.isfinite(rmsd_threshold) or not 0 < rmsd_threshold <= .08:
            raise ValueError("SRS RMSD threshold must be positive and no greater than 0.08 angstrom")
        if not np.isfinite(rotational_constant_threshold) or not 0 <= rotational_constant_threshold <= .0005:
            raise ValueError("SRS rotational threshold must be nonnegative and no greater than 0.0005")
        if not np.isfinite(energy_window_kcal) or energy_window_kcal < 0:
            raise ValueError("Energy window must be finite and nonnegative")
        if not np.isfinite(duplicate_energy_threshold_kcal) or not 0 < duplicate_energy_threshold_kcal <= 0.05:
            raise ValueError("Duplicate energy threshold must be positive and no greater than 0.05 kcal/mol")
        self.rmsd_threshold = rmsd_threshold
        self.rotational_constant_threshold = rotational_constant_threshold
        self.energy_window_kcal = energy_window_kcal
        self.duplicate_energy_threshold_kcal = duplicate_energy_threshold_kcal

    def deduplicate(self, conformers: List[ConformerCandidate]) -> List[ConformerCandidate]:
        """Return representatives; use sieve() to preserve full pool lineage."""
        return list(self.sieve(conformers).retained)

    def sieve(self, conformers: Sequence[ConformerCandidate], *,
              require_comparable_protocol: bool = False) -> ConformerSieveResult:
        """Apply the SRS sieve within matching nuclear, state and method partitions.

        New ingestion consumers require an explicit comparison protocol and state.
        The historical list API accepts its caller's implicit homogeneous context;
        it never mixes contradictory explicit declarations. Unknown energies are
        retained and excluded from energy ranking, windows and duplicate removal.
        Every excluded member receives an auditable decision; no input is mutated.
        """
        original = tuple(conformers)
        identifiers = [item.conformer_id for item in original]
        if any(not isinstance(value, str) or not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError("Conformer identifiers must be nonempty and unique within their pool")
        graphs, constants, hashes, energies, comparable = {}, {}, {}, {}, {}
        for candidate in original:
            key = candidate.conformer_id
            graphs[key] = build_covalent_graph(candidate.symbols, candidate.coordinates)
            hashes[key] = _graph_hash(graphs[key])
            constants[key] = compute_conformer_rotational_constants(candidate.symbols, candidate.coordinates)
            energies[key] = candidate.energy_kcal if candidate.energy is not None else None
            comparable[key] = energies[key] is not None and (not require_comparable_protocol or (
                type(candidate.charge) is int and type(candidate.multiplicity) is int and candidate.multiplicity >= 1
                and isinstance(candidate.comparison_protocol, str) and bool(candidate.comparison_protocol.strip())))
        ordered = sorted(original, key=lambda item: (repr(item.comparison_key),
                         energies[item.conformer_id] if comparable[item.conformer_id] else float("inf"), item.conformer_id))
        minima = {}
        for candidate in ordered:
            if comparable[candidate.conformer_id]:
                minima.setdefault(candidate.comparison_key, energies[candidate.conformer_id])
        retained, decisions = [], []
        for candidate in ordered:
            key = candidate.conformer_id
            if not comparable[key]:
                retained.append(candidate)
                decisions.append(ConformerSieveDecision(key, "unranked-energy", None,
                    "Original geometry retained: an explicit energy and matching state/protocol are required for scientific ranking", hashes[key]))
                continue
            relative = energies[key] - minima[candidate.comparison_key]
            if relative > self.energy_window_kcal:
                decisions.append(ConformerSieveDecision(key, "outside-energy-window", None,
                    f"Outside the explicit {self.energy_window_kcal:g} kcal/mol window in its own nuclear/state/protocol partition; original member remains in lineage",
                    hashes[key], relative_energy_kcal=relative))
                continue
            representative, distance = None, None
            for accepted in retained:
                other = accepted.conformer_id
                if (not comparable[other] or candidate.comparison_key != accepted.comparison_key
                        or abs(energies[key] - energies[other]) >= self.duplicate_energy_threshold_kcal
                        or hashes[key] != hashes[other]
                        or not rotational_constants_agree(constants[other], constants[key], self.rotational_constant_threshold)):
                    continue
                rmsd, mapping = compute_automorphism_orbit_rmsd(candidate.coordinates, accepted.coordinates,
                    candidate.symbols, graph=graphs[key], symbols_b=accepted.symbols, graph_b=graphs[other])
                if mapping and rmsd < self.rmsd_threshold:
                    representative, distance = other, rmsd
                    break
            if representative is None:
                retained.append(candidate)
                decisions.append(ConformerSieveDecision(key, "retained", None,
                    "Passed its energy window; no verified labeled-graph, proper-rotation, tri-axial and energy-equivalent representative",
                    hashes[key], relative_energy_kcal=relative))
            else:
                decisions.append(ConformerSieveDecision(key, "duplicate", representative,
                    "Verified labeled graph correspondence, proper-rotation RMSD, every defined principal rotational axis and compatible electronic energy",
                    hashes[key], relative_energy_kcal=relative, rmsd_angstrom=distance))
        logger.info("Conformer sieve retained %s of %s; all original records remain in lineage", len(retained), len(original))
        return ConformerSieveResult(original, tuple(retained), tuple(decisions))


__all__ = [
    "are_duplicate_conformers",
    "ConformerCandidate",
    "ConformerDeduplicator",
    "ConformerSieveDecision",
    "ConformerSieveResult",
    "conformer_metadata_dict",
    "rotational_constants_agree",
    "compute_weisfeiler_lehman_hash",
    "kabsch_rmsd",
    "kabsch_quaternion_rmsd",
    "hungarian_assignment_rmsd",
    "compute_automorphism_orbit_rmsd",
    "build_covalent_graph",
    "compute_conformer_rotational_constants",
]
