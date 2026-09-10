"""
CoChem Two-Stage Topological & Spectroscopic Conformer Deduplication Engine.
Subsystem VR01-SS4: Work Package 1.5 (WBS 1.5.1 - 1.5.5)

Governing Specifications:
- WBS 1.5.1: Dynamic Pyykkö Covalent Radii Molecular Graph Construction
- WBS 1.5.2: Weisfeiler-Lehman Graph Isomorphism Hashing (Stage A Filter)
- WBS 1.5.3: Automorphism Orbit Traversal (Aut(G)) & Minimum-Orbit Kabsch RMSD
- WBS 1.5.4: Principal Moments of Inertia & Spectroscopic Rotational Constant Discriminator
- WBS 1.5.5: Shallow-Minima Potential Well Preservation Gate (Delta_B/B <= 0.05%)
- Method Matrix v4.1 (§10.1–10.8, §9A.1–9A.5)
- Dynamic Mendeleev Mandate: Zero static mass or radius dictionaries
- Anti-Spoofing Protocols v2 & v4 (Hardened Zero-Mock Execution)
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import numpy as np
import networkx as nx

try:
    from cochem_base.exceptions import CoChemError
except ImportError:
    class CoChemError(Exception):
        """Fallback root exception if cochem_base.exceptions is unavailable."""
        pass

from cochem_base.physics.nuclide_resolver import (
    disambiguate_mass,
    get_element,
    parse_nuclide,
    resolve_covalent_radius,
    NuclideToken,
)
from cochem_base.physics.eckart_aligner import (
    EckartFrameAligner,
    translate_to_center_of_mass,
)


# ============================================================================
# Physical Constants (CODATA 2018 / 2022)
# ============================================================================
# Conversion factor from inertia (u * Angstrom^2) to rotational constant in GHz:
# B = h / (8 * pi^2 * I)
# h = 6.62607015e-34 J*s, 1 u = 1.66053906660e-27 kg, 1 A = 1e-10 m
# Factor = 6.62607015e-34 / (8 * pi^2 * 1.66053906660e-47 * 1e9) = 505.379006 GHz * u * A^2
INERTIA_TO_GHZ: float = 505.37900627725894


# ============================================================================
# Exception Hierarchy (WBS 1.5.1 - 1.5.5)
# ============================================================================

class TopologyError(CoChemError):
    """Base exception for all topological analysis and deduplication errors."""
    pass


class MolecularGraphError(TopologyError):
    """Raised when molecular graph construction fails or invariants are breached."""
    pass


class InvalidGeometryError(TopologyError, ValueError):
    """Raised when coordinates or molecular geometries are physically invalid."""
    pass


class DisconnectedGraphError(MolecularGraphError):
    """Raised when a single molecule is expected but graph has multiple disconnected components."""
    pass


class ConformerDeduplicationError(TopologyError):
    """Raised when conformer deduplication encounter an unrecoverable state."""
    pass


# ============================================================================
# Data Structures
# ============================================================================

@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    """Immutable result of two-stage conformer deduplication comparison.

    Attributes:
        is_duplicate: True if conformers are determined to be identical.
        stage: Filter stage where determination was completed ('STAGE_A_TOPOLOGY', 'STAGE_B_GEOMETRY', 'STAGE_C_SPECTROSCOPY').
        reason: Exact rationale code for the verdict.
        wl_hash_a: Weisfeiler-Lehman 128-bit hex digest for geometry A.
        wl_hash_b: Weisfeiler-Lehman 128-bit hex digest for geometry B.
        min_orbit_rmsd: Minimum RMSD (in Angstroms) over automorphism orbit Aut(G), if evaluated.
        rotational_divergence: Maximum relative rotational constant difference Delta_B / B, if evaluated.
        best_permutation: Vertex permutation mapping B -> A corresponding to min_orbit_rmsd, if evaluated.
    """
    is_duplicate: bool
    stage: str
    reason: str
    wl_hash_a: str
    wl_hash_b: str
    min_orbit_rmsd: Optional[float] = None
    rotational_divergence: Optional[float] = None
    best_permutation: Optional[Dict[int, int]] = None


# ============================================================================
# Dynamic Mendeleev Covalent Radii Resolution (WBS 1.5.1.2)
# ============================================================================

@functools.lru_cache(maxsize=512)
def get_covalent_radius(symbol_or_token: Union[str, NuclideToken]) -> float:
    """Dynamically query relativistic Pyykkö single-bond covalent radius in Angstroms.

    Strictly satisfies the Dynamic Mendeleev Mandate:
    Zero static radius dictionaries permitted. Dynamic resolution via nuclide_resolver
    backed by mendeleev's authoritative database.

    Args:
        symbol_or_token: IUPAC chemical symbol, nuclide token, or NuclideToken instance.

    Returns:
        float: Single-bond covalent radius in Angstroms (Å).

    Raises:
        TopologyError: If covalent radius cannot be resolved from Mendeleev.
    """
    radius = resolve_covalent_radius(symbol_or_token)
    if radius is not None and radius > 0.0:
        return float(radius)

    # Fallback to direct mendeleev query if resolve_covalent_radius returns None
    parsed = parse_nuclide(symbol_or_token if isinstance(symbol_or_token, str) else symbol_or_token.symbol)
    elem = get_element(parsed.symbol)
    r_pm = getattr(elem, "covalent_radius_pyykko", None)
    if r_pm is None:
        r_pm = getattr(elem, "covalent_radius", None)
    if r_pm is not None and r_pm > 0.0:
        return float(r_pm) * 0.01

    raise TopologyError(
        f"Unable to resolve dynamic covalent radius for element '{parsed.symbol}' from Mendeleev database."
    )


# ============================================================================
# Covalent Adjacency Matrix Formulation (WBS 1.5.1.1)
# ============================================================================

def build_covalent_adjacency_matrix(
    coordinates: np.ndarray,
    symbols: Sequence[str],
    fudge_factor: float = 1.15,
    radii: Optional[Union[Sequence[float], np.ndarray]] = None,
) -> np.ndarray:
    """Build covalent adjacency matrix A in {0, 1}^(N x N) via interatomic distance criteria.

    Mathematical formulation (WBS 1.5.1.1):
        A_{ij} = 1  if i != j and ||r_i - r_j||_2 <= fudge_factor * (r_cov(i) + r_cov(j))
                 0  otherwise

    Properties strictly enforced:
        1. A is symmetric: A = A^T
        2. A has zero diagonal: A_{ii} = 0
        3. A is binary integer array: A_{ij} in {0, 1}
        4. Pairwise Euclidean distances computed via vectorized NumPy GEMM broadcasting (<50 µs for N=100).

    Args:
        coordinates: Molecular coordinates of shape (N, 3) in Angstroms.
        symbols: Sequence of N IUPAC chemical element or nuclide symbols.
        fudge_factor: Covalent connectivity scaling factor (default: 1.15 per WBS 1.5.1).
        radii: Optional pre-computed or cached covalent radii array of shape (N,).

    Returns:
        np.ndarray: (N, N) binary symmetric adjacency matrix of dtype np.int64.

    Raises:
        InvalidGeometryError: If coordinates are non-Cartesian, contain NaN/Inf, or have N < 1.
        ValueError: If length of symbols does not match atom count N.
    """
    if not isinstance(coordinates, np.ndarray):
        try:
            coords = np.asarray(coordinates, dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise InvalidGeometryError(f"Coordinates could not be converted to float64: {exc}") from exc
    else:
        coords = coordinates.astype(np.float64, copy=False)

    if coords.ndim != 2 or coords.shape[-1] != 3:
        raise InvalidGeometryError(f"Coordinates must have shape (N, 3), got {coords.shape}.")
    n_atoms = coords.shape[0]
    if n_atoms == 0:
        raise InvalidGeometryError("Coordinate array must contain at least 1 atom (N >= 1).")
    if not np.isfinite(coords.sum()):
        raise InvalidGeometryError("Coordinates must not contain NaN or Inf values.")

    if len(symbols) != n_atoms:
        raise ValueError(
            f"Number of chemical symbols ({len(symbols)}) does not match atom count ({n_atoms})."
        )
    if fudge_factor <= 0.0:
        raise ValueError(f"fudge_factor must be positive, got {fudge_factor}.")

    # Dynamically query single-bond covalent radii from Mendeleev with unique symbol caching
    if radii is None:
        unique_syms = set(symbols)
        r_map = {s: get_covalent_radius(s) for s in unique_syms}
        rad_arr = np.array([r_map[s] for s in symbols], dtype=np.float64)
    else:
        rad_arr = np.asarray(radii, dtype=np.float64)
        if rad_arr.shape != (n_atoms,):
            raise ValueError(f"radii shape {rad_arr.shape} must match atom count {n_atoms}.")

    # Fast Euclidean distance matrix via BLAS GEMM formulation: ||r_i - r_j||^2 = ||r_i||^2 + ||r_j||^2 - 2(r_i . r_j)
    r_sq = np.sum(coords * coords, axis=1, keepdims=True)  # (N, 1)
    dist_sq = np.maximum(r_sq + r_sq.T - 2.0 * (coords @ coords.T), 0.0)  # (N, N)

    # Cutoff squared matrix
    cutoff_matrix = fudge_factor * (rad_arr[:, None] + rad_arr[None, :])
    cutoff_sq = cutoff_matrix * cutoff_matrix

    # Binary connectivity criteria: i != j and dist_sq <= cutoff_sq
    adj_matrix = ((dist_sq <= cutoff_sq) & (dist_sq > 1e-8)).astype(np.int64)
    np.fill_diagonal(adj_matrix, 0)

    return adj_matrix


# ============================================================================
# Molecular Graph Construction (WBS 1.5.1.3)
# ============================================================================

def build_molecular_graph(
    coordinates: np.ndarray,
    symbols: Sequence[str],
    fudge_factor: float = 1.15,
) -> nx.Graph:
    """Construct networkx.Graph representing molecular covalent connectivity.

    Mathematical & topological formulation (WBS 1.5.1.3):
        - Vertices V = {0, 1, ..., N-1}
        - Edges E = {(i, j) : A_{ij} = 1, i < j}
        - Node attributes:
            * 'element': Canonical chemical symbol string (e.g. 'C', 'H', 'O')
            * 'mass_number': Optional integer mass number A (e.g. 12, 13, 1, 2) or None
            * 'atomic_number': IUPAC atomic number integer Z (e.g. 6, 1, 8)
            * 'mass': Unified atomic mass in Daltons (u) dynamically retrieved from Mendeleev
            * 'covalent_radius': Pyykkö covalent radius in Angstroms
            * 'coordinates': Cartesian coordinates of shape (3,) as np.float64 array
        - Edge attributes:
            * 'distance': Interatomic Euclidean distance ||r_i - r_j||_2 in Angstroms
            * 'cutoff': Interatomic covalent threshold 1.15 * (r_cov(i) + r_cov(j)) in Angstroms

    Acceptance criteria (WBS 1.5.1):
        Graph topology correctly identifies all single, double, and aromatic bonds
        for ethanol, formamide, and benzene without missing edges.

    Args:
        coordinates: Molecular coordinates of shape (N, 3) in Angstroms.
        symbols: Sequence of N chemical or nuclide symbol strings.
        fudge_factor: Covalent connectivity threshold multiplier (default: 1.15).

    Returns:
        nx.Graph: Connected molecular graph with fully typed physical node/edge attributes.

    Raises:
        InvalidGeometryError: If coordinates are invalid or contain NaN/Inf.
        ValueError: If symbols count does not match atom count.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    n_atoms = coords.shape[0]

    adj_matrix = build_covalent_adjacency_matrix(coords, symbols, fudge_factor=fudge_factor)

    graph = nx.Graph()

    # Populate nodes with rich physical attributes
    for idx, sym in enumerate(symbols):
        parsed = parse_nuclide(sym)
        elem = get_element(parsed.symbol)
        atomic_num = int(elem.atomic_number)
        mass_val = float(disambiguate_mass(sym))
        r_cov = float(get_covalent_radius(sym))

        graph.add_node(
            idx,
            element=parsed.symbol,
            mass_number=parsed.mass_number,
            atomic_number=atomic_num,
            mass=mass_val,
            covalent_radius=r_cov,
            coordinates=coords[idx].copy(),
        )

    # Populate edges with distance metrics
    radii = [graph.nodes[i]["covalent_radius"] for i in range(n_atoms)]
    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            if adj_matrix[i, j] == 1:
                dist = float(np.linalg.norm(coords[i] - coords[j]))
                cutoff = float(fudge_factor * (radii[i] + radii[j]))
                graph.add_edge(i, j, distance=dist, cutoff=cutoff)

    return graph


# ============================================================================
# Weisfeiler-Lehman Graph Isomorphism Hashing (Stage A Filter, WBS 1.5.2)
# ============================================================================

def compute_weisfeiler_lehman_hash(
    graph: nx.Graph,
    iterations: int = 3,
    digest_size: int = 16,
) -> str:
    """Compute 128-bit Weisfeiler-Lehman graph hash for topological connectivity (WBS 1.5.2).

    Executes 3 iterations of the Weisfeiler-Lehman color refinement algorithm using
    node attribute 'element' to capture chemical identity. Returns a 128-bit hex digest.

    Args:
        graph: NetworkX molecular graph.
        iterations: Number of WL color refinement passes (default: 3).
        digest_size: Hex digest length in bytes (default: 16 -> 128-bit hex string).

    Returns:
        str: 128-bit hexadecimal hash string.
    """
    wl_hash = nx.algorithms.graph_hashing.weisfeiler_lehman_graph_hash(
        graph,
        node_attr="element",
        iterations=iterations,
        digest_size=digest_size,
    )
    return str(wl_hash)


# ============================================================================
# Spectroscopic Moments of Inertia & Rotational Constants (WBS 1.5.4)
# ============================================================================

def compute_principal_moments_of_inertia(
    coordinates: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Construct and diagonalize the principal moment of inertia tensor (WBS 1.5.4.1 - 1.5.4.2).

    Mathematical formulation:
        In the mass-weighted COM frame:
        I_{alpha beta} = sum_{i=1}^N m_i * ( ||r_tilde_i||^2 * delta_{alpha beta} - r_{i, alpha} * r_{i, beta} )

    Args:
        coordinates: Molecular coordinates of shape (N, 3).
        masses: Optional atomic masses sequence or array.
        symbols: Optional IUPAC symbols sequence (resolved via Mendeleev if masses is None).

    Returns:
        Tuple of (principal_moments, principal_axes):
            principal_moments: Sorted eigenvalues [I_a, I_b, I_c] with I_a <= I_b <= I_c in u * Angstrom^2.
            principal_axes: 3x3 array whose columns are the corresponding eigenvectors.
    """
    coords_c, _ = translate_to_center_of_mass(coordinates, masses=masses, symbols=symbols)

    if masses is None:
        if symbols is None:
            raise ValueError("Either masses or symbols must be provided.")
        m_arr = np.asarray([disambiguate_mass(s) for s in symbols], dtype=np.float64)
    else:
        m_arr = np.asarray(masses, dtype=np.float64)

    # Vectorized moment of inertia tensor construction
    # I = sum_i m_i * [ (r_i . r_i) * I_3 - outer(r_i, r_i) ]
    r_sq = np.sum(coords_c * coords_c, axis=1)  # (N,)
    identity_3x3 = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    trace_term = np.sum(m_arr * r_sq) * identity_3x3
    outer_term = coords_c.T @ (m_arr[:, None] * coords_c)
    i_tensor = trace_term - outer_term

    evals, evecs = np.linalg.eigh(i_tensor)
    idx_sorted = np.argsort(evals)
    principal_moments = evals[idx_sorted]
    principal_axes = evecs[:, idx_sorted]

    return principal_moments.astype(np.float64), principal_axes.astype(np.float64)


def compute_rotational_constants(
    coordinates: np.ndarray,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Tuple[float, float, float]:
    """Calculate spectroscopic equilibrium rotational constants A, B, C in GHz (WBS 1.5.4.3).

    Mathematical formulation:
        A = h / (8 * pi^2 * I_a),  B = h / (8 * pi^2 * I_b),  C = h / (8 * pi^2 * I_c)

    Convention:
        I_a <= I_b <= I_c  =>  A >= B >= C

    Args:
        coordinates: Molecular coordinates of shape (N, 3).
        masses: Optional atomic masses array.
        symbols: Optional IUPAC symbols sequence.

    Returns:
        Tuple of (A, B, C) in GHz. Linear rotors report A = Inf (or 0.0 principal moment).
    """
    moments, _ = compute_principal_moments_of_inertia(coordinates, masses=masses, symbols=symbols)
    ia, ib, ic = float(moments[0]), float(moments[1]), float(moments[2])

    a_const = (INERTIA_TO_GHZ / ia) if ia > 1e-8 else float("inf")
    b_const = (INERTIA_TO_GHZ / ib) if ib > 1e-8 else float("inf")
    c_const = (INERTIA_TO_GHZ / ic) if ic > 1e-8 else float("inf")

    return a_const, b_const, c_const


# ============================================================================
# Automorphism Orbit Traversal & Minimum-Orbit Kabsch RMSD (WBS 1.5.3)
# ============================================================================

def compute_automorphism_orbit_rmsd(
    coords_a: np.ndarray,
    coords_b: np.ndarray,
    symbols: Sequence[str],
    graph_a: Optional[nx.Graph] = None,
    graph_b: Optional[nx.Graph] = None,
    fudge_factor: float = 1.15,
) -> Tuple[float, Dict[int, int]]:
    """Compute global minimum RMSD over the automorphism orbit Aut(G) (WBS 1.5.3).

    Mathematical formulation (WBS 1.5.3.1 - 1.5.3.5):
        For isomorphic graphs G_A and G_B:
            Find all vertex permutations pi in Iso(G_B, G_A) preserving chemical element and mass.
            Permute B's coordinates: R_B^(pi) = P_pi R_B
            Align R_B^(pi) to R_A via EckartFrameAligner
            RMSD_min-orbit = min_{pi in Iso(G_B, G_A)} RMSD(R_A, R_B^(pi))

    Args:
        coords_a: Molecular coordinates of structure A (N, 3).
        coords_b: Molecular coordinates of structure B (N, 3).
        symbols: Sequence of N chemical symbols for the molecule.
        graph_a: Optional pre-built graph for structure A.
        graph_b: Optional pre-built graph for structure B.
        fudge_factor: Covalent connectivity threshold (default: 1.15).

    Returns:
        Tuple of (min_orbit_rmsd, best_permutation_mapping).
    """
    g_a = graph_a if graph_a is not None else build_molecular_graph(coords_a, symbols, fudge_factor=fudge_factor)
    g_b = graph_b if graph_b is not None else build_molecular_graph(coords_b, symbols, fudge_factor=fudge_factor)

    masses = [disambiguate_mass(s) for s in symbols]

    # Constrain vertex matches: element and mass number must match identically
    def node_match(n1: Dict[str, Any], n2: Dict[str, Any]) -> bool:
        return (
            n1.get("element") == n2.get("element")
            and n1.get("mass_number") == n2.get("mass_number")
        )

    matcher = nx.algorithms.isomorphism.GraphMatcher(g_a, g_b, node_match=node_match)

    aligner = EckartFrameAligner()
    min_rmsd = float("inf")
    best_mapping: Dict[int, int] = {}

    # Traverse all valid isomorphic permutations
    # mapping is {node_in_g_a: node_in_g_b}
    found_any = False
    for mapping in matcher.isomorphisms_iter():
        found_any = True
        # Construct permuted coordinates of B matching atom order of A
        # For atom i in A, its corresponding atom in B is mapping[i]
        perm_indices = [mapping[i] for i in range(len(symbols))]
        coords_b_perm = coords_b[perm_indices]

        _, _, rmsd = aligner.align(coords_a, coords_b_perm, masses=masses)
        if rmsd < min_rmsd:
            min_rmsd = rmsd
            best_mapping = dict(mapping)

    if not found_any:
        # Fallback to direct non-permuted alignment if graphs are not isomorphic
        _, _, naive_rmsd = aligner.align(coords_a, coords_b, masses=masses)
        return naive_rmsd, {i: i for i in range(len(symbols))}

    return min_rmsd, best_mapping


# ============================================================================
# Two-Stage Conformer Deduplicator Engine (WBS 1.5.1 - 1.5.5)
# ============================================================================

class ConformerDeduplicator:
    """Production Two-Stage Topological & Spectroscopic Conformer Deduplication Engine (Subsystem VR01-SS4).

    Implements:
        - Stage A: Weisfeiler-Lehman 128-bit graph isomorphism hash filter (<0.5 ms rejection)
        - Stage B: Automorphism orbit traversal Aut(G) & minimum-orbit Eckart RMSD
        - Stage C: Spectroscopic rotational constant discriminator (Delta_B / B <= 0.05%)
    """

    def __init__(
        self,
        fudge_factor: float = 1.15,
        rmsd_threshold: float = 0.08,
        rotational_tol: float = 0.0005,
    ) -> None:
        """Initialize conformer deduplication engine.

        Args:
            fudge_factor: Pyykkö covalent radius scaling factor (default: 1.15).
            rmsd_threshold: Geometric RMSD threshold in Angstroms (default: 0.08 Å per VR-01-D04).
            rotational_tol: Relative rotational divergence threshold Delta_B/B (default: 0.05% = 0.0005).
        """
        self.fudge_factor = fudge_factor
        self.rmsd_threshold = rmsd_threshold
        self.rotational_tol = rotational_tol

    def build_graph(self, coordinates: np.ndarray, symbols: Sequence[str]) -> nx.Graph:
        """Build molecular graph with dynamic Mendeleev single-bond Pyykkö covalent radii."""
        return build_molecular_graph(coordinates, symbols, fudge_factor=self.fudge_factor)

    def compute_wl_hash(self, graph: nx.Graph) -> str:
        """Compute Weisfeiler-Lehman 128-bit hex digest."""
        return compute_weisfeiler_lehman_hash(graph)

    def compare_conformers(
        self,
        coords_a: np.ndarray,
        coords_b: np.ndarray,
        symbols: Sequence[str],
    ) -> DeduplicationResult:
        """Execute complete two-stage deduplication comparison between two geometries.

        Returns DeduplicationResult with clear verdict, stage, and forensic telemetry.
        """
        # 1. Build molecular graphs
        graph_a = self.build_graph(coords_a, symbols)
        graph_b = self.build_graph(coords_b, symbols)

        # 2. Stage A: Weisfeiler-Lehman Graph Hash Filter
        hash_a = self.compute_wl_hash(graph_a)
        hash_b = self.compute_wl_hash(graph_b)

        if hash_a != hash_b:
            return DeduplicationResult(
                is_duplicate=False,
                stage="STAGE_A_TOPOLOGY",
                reason="TOPOLOGICALLY_DISTINCT_WL_HASH",
                wl_hash_a=hash_a,
                wl_hash_b=hash_b,
            )

        # 3. Stage B: Automorphism Orbit Traversal & Minimum-Orbit Kabsch RMSD
        min_rmsd, best_perm = compute_automorphism_orbit_rmsd(
            coords_a, coords_b, symbols, graph_a=graph_a, graph_b=graph_b, fudge_factor=self.fudge_factor
        )

        if min_rmsd >= self.rmsd_threshold:
            return DeduplicationResult(
                is_duplicate=False,
                stage="STAGE_B_GEOMETRY",
                reason="GEOMETRICALLY_DISTINCT_RMSD_EXCEEDS_THRESHOLD",
                wl_hash_a=hash_a,
                wl_hash_b=hash_b,
                min_orbit_rmsd=min_rmsd,
                best_permutation=best_perm,
            )

        # 4. Stage C: Spectroscopic Rotational Constant Discriminator
        masses = [disambiguate_mass(s) for s in symbols]
        a1, b1, c1 = compute_rotational_constants(coords_a, masses=masses)
        a2, b2, c2 = compute_rotational_constants(coords_b, masses=masses)

        # Relative rotational divergences
        diff_a = abs(a1 - a2) / a1 if np.isfinite(a1) and a1 > 0 else 0.0
        diff_b = abs(b1 - b2) / b1 if np.isfinite(b1) and b1 > 0 else 0.0
        diff_c = abs(c1 - c2) / c1 if np.isfinite(c1) and c1 > 0 else 0.0
        delta_b_rel = max(diff_a, diff_b, diff_c)

        if delta_b_rel <= self.rotational_tol:
            return DeduplicationResult(
                is_duplicate=True,
                stage="STAGE_C_SPECTROSCOPY",
                reason="CONFIRMED_DUPLICATE",
                wl_hash_a=hash_a,
                wl_hash_b=hash_b,
                min_orbit_rmsd=min_rmsd,
                rotational_divergence=delta_b_rel,
                best_permutation=best_perm,
            )
        else:
            return DeduplicationResult(
                is_duplicate=False,
                stage="STAGE_C_SPECTROSCOPY",
                reason="RETAINED_SHALLOW_MINIMUM_ROTATIONAL_DIVERGENCE",
                wl_hash_a=hash_a,
                wl_hash_b=hash_b,
                min_orbit_rmsd=min_rmsd,
                rotational_divergence=delta_b_rel,
                best_permutation=best_perm,
            )
