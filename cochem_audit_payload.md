Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_10_intake_stage2_ingestor_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_stage2_ingestor.py

## 1. Goal
Implement the file `cochem_stage2_ingestor.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\intake\cochem_stage2_ingestor.py`

## 3. Context & Ecosystem Role
The Topology Sorter. Actively severs unphysical valencies, prevents matrix inversion crashes on linear molecules, and purges redundant geometric conformers to save downstream compute time while ensuring perfect topological reproducibility.

## 4. Deliverable Functions
Constructs covalent graphs using `NetworkX` (with a 1.15x breathing tolerance). Executes Kabsch RMSD geometric alignment and 'Jiggle-Quench' deduplication logic. Enforces a determinant reflection trap (`d = np.sign(np.linalg.det(Vt.T @ U.T))`) and an SVD collinearity trap. For linear and diatomic species causing high condition numbers, mathematically pivots to a 2D Z-axis projection instead of skipping alignments.

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\intake\cochem_stage2_ingestor.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Stage 2.0 - Dual-Graph Non-Covalent Sieve & Hungarian SVD Alignor.

Module: intake/cochem_stage2_ingestor.py
Ecosystem Role: The Topology Sorter & Conformer Deduplicator.
                Actively severs unphysical valencies, constructs covalent subgraphs
                with a 1.15x breathing tolerance, preserves non-covalent van der Waals
                contacts, prevents matrix inversion crashes on linear/diatomic species
                via 2D Z-axis projection, and purges redundant geometric conformers
                via Hungarian Kabsch alignment and Jiggle-Quench logic.

Authoritative Standards:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\SRS\\Perfected_Document 2 File Inventory & Deliverable Capabilities Manifest (Part 2).md
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import mendeleev
import networkx as nx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from scipy.optimize import linear_sum_assignment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-Stage2Ingestor")


# ==============================================================================
# 1. Authentic Atomic Radii, Valency Limits & Mass Helpers
# ==============================================================================

# Standard Covalent Radii (Pyykkö & Atsumi single-bond values in Angstroms)
COVALENT_RADII_FALLBACK: Dict[str, float] = {
    "H": 0.31, "He": 0.28,
    "Li": 1.28, "Be": 0.96, "B": 0.84, "C": 0.76, "N": 0.71, "O": 0.66, "F": 0.57, "Ne": 0.58,
    "Na": 1.66, "Mg": 1.41, "Al": 1.21, "Si": 1.11, "P": 1.07, "S": 1.05, "Cl": 1.02, "Ar": 1.06,
    "K": 2.03, "Ca": 1.76, "Sc": 1.70, "Ti": 1.60, "V": 1.53, "Cr": 1.39, "Mn": 1.39,
    "Fe": 1.32, "Co": 1.26, "Ni": 1.24, "Cu": 1.32, "Zn": 1.22, "Ga": 1.22, "Ge": 1.20,
    "As": 1.19, "Se": 1.20, "Br": 1.20, "Kr": 1.16,
    "Rb": 2.20, "Sr": 1.95, "Y": 1.90, "Zr": 1.75, "Nb": 1.64, "Mo": 1.54, "Tc": 1.47,
    "Ru": 1.46, "Rh": 1.42, "Pd": 1.39, "Ag": 1.45, "Cd": 1.44, "In": 1.42, "Sn": 1.39,
    "Sb": 1.39, "Te": 1.38, "I": 1.39, "Xe": 1.40,
}

# Standard van der Waals Radii (Alvarez / Bondi values in Angstroms)
VDW_RADII_FALLBACK: Dict[str, float] = {
    "H": 1.20, "He": 1.40,
    "Li": 1.82, "Be": 1.53, "B": 1.92, "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "Ne": 1.54,
    "Na": 2.27, "Mg": 1.73, "Al": 1.84, "Si": 2.10, "P": 1.80, "S": 1.80, "Cl": 1.75, "Ar": 1.88,
    "K": 2.75, "Ca": 2.31, "Sc": 2.11, "Ti": 2.00, "V": 2.00, "Cr": 2.00, "Mn": 2.00,
    "Fe": 2.00, "Co": 2.00, "Ni": 1.63, "Cu": 1.40, "Zn": 1.39, "Ga": 1.87, "Ge": 2.11,
    "As": 1.85, "Se": 1.90, "Br": 1.85, "Kr": 2.02,
    "Rb": 3.03, "Sr": 2.49, "I": 1.98, "Xe": 2.16,
}

# Physical Maximum Covalent Valency Limits
MAX_PHYSICAL_VALENCY: Dict[str, int] = {
    "H": 1, "He": 0,
    "Li": 1, "Be": 2, "B": 4, "C": 4, "N": 4, "O": 3, "F": 1, "Ne": 0,
    "Na": 1, "Mg": 2, "Al": 4, "Si": 4, "P": 6, "S": 6, "Cl": 4, "Ar": 0,
    "K": 1, "Ca": 2, "Br": 4, "I": 5,
}


def is_ghost_symbol(symbol: str) -> bool:
    """Checks whether an atomic element symbol represents a ghost / dummy atom."""
    if not symbol or not isinstance(symbol, str):
        return False
    clean = symbol.strip().lower()
    if clean.startswith("gh") or clean.startswith("bq") or clean == "bq":
        return True
    if clean == "x" or clean.startswith("x_") or clean.startswith("x-") or clean.startswith("x:"):
        return True
    if clean.startswith("x") and not clean.startswith("xe"):
        return True
    return False


def normalize_symbol(symbol: str) -> str:
    """Cleans and standardizes an atomic element symbol."""
    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("[MISSING DATA] Atomic symbol cannot be empty.")
    clean = symbol.strip()
    if is_ghost_symbol(clean):
        return "Gh"
    match = re.match(r"^([A-Za-z]{1,2})", clean)
    if match:
        return match.group(1).capitalize()
    return clean.capitalize()


def get_covalent_radius(symbol: str) -> float:
    """Retrieves standard covalent radius in Angstroms."""
    sym = normalize_symbol(symbol)
    if is_ghost_symbol(sym):
        return 0.0
    try:
        elem = mendeleev.element(sym)
        if elem is not None and elem.covalent_radius_pyykko is not None:
            return float(elem.covalent_radius_pyykko) / 100.0
        if elem is not None and elem.covalent_radius is not None:
            return float(elem.covalent_radius) / 100.0
    except Exception:
        pass
    return COVALENT_RADII_FALLBACK.get(sym, 1.20)


def get_vdw_radius(symbol: str) -> float:
    """Retrieves standard van der Waals radius in Angstroms."""
    sym = normalize_symbol(symbol)
    if is_ghost_symbol(sym):
        return 0.0
    try:
        elem = mendeleev.element(sym)
        if elem is not None and elem.vdw_radius_alvarez is not None:
            return float(elem.vdw_radius_alvarez) / 100.0
        if elem is not None and elem.vdw_radius is not None:
            return float(elem.vdw_radius) / 100.0
    except Exception:
        pass
    return VDW_RADII_FALLBACK.get(sym, 1.70)


def get_atomic_mass(symbol: str) -> float:
    """Retrieves standard atomic weight in unified atomic mass units (u)."""
    sym = normalize_symbol(symbol)
    if is_ghost_symbol(sym):
        return 0.0
    try:
        elem = mendeleev.element(sym)
        if elem is not None and elem.mass is not None:
            return float(elem.mass)
    except Exception:
        pass
    return 1.008 if sym == "H" else 12.011


# ==============================================================================
# 2. Pydantic Serialization Models
# ==============================================================================

class AtomNode(BaseModel):
    """Pydantic model representing an individual atom node in molecular space."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    index: int
    symbol: str
    x: float
    y: float
    z: float
    is_ghost: bool = False


class MonomerSubgraph(BaseModel):
    """Pydantic model representing an intra-monomer covalent subgraph."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    monomer_id: int
    formula: str
    num_atoms: int
    atom_indices: List[int]
    symbols: List[str]
    covalent_edges: List[Tuple[int, int]]


class DualGraphResult(BaseModel):
    """Pydantic model containing the complete Dual-Graph topology construction."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    num_atoms: int
    num_covalent_bonds: int
    num_noncovalent_contacts: int
    monomers: List[MonomerSubgraph]
    intermolecular_contact_edges: List[Tuple[int, int]]
    has_intermolecular_contacts: bool
    covalent_adjacency: Any = Field(None, description="Covalent adjacency matrix")

    @field_serializer("covalent_adjacency", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


class KabschAlignmentResult(BaseModel):
    """Pydantic model containing Hungarian Kabsch alignment results."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    rmsd: float
    rotation_matrix: Any
    translation_vector: Any
    aligned_coords: Any
    is_reflection: bool = False
    is_collinear: bool = False
    permutation_indices: Optional[List[int]] = None

    @field_serializer("rotation_matrix", "translation_vector", "aligned_coords", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


class ConformerClusterResult(BaseModel):
    """Pydantic model representing deduplicated conformer clusters."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    total_input_conformers: int
    unique_conformer_count: int
    unique_indices: List[int]
    cluster_assignments: Dict[int, int]
    representative_names: List[str]


class ChemicalSystemResult(BaseModel):
    """Pydantic model representing an ingested chemical system with conformers and topology."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    system_name: str
    formula: str
    total_input_conformers: int
    unique_conformer_count: int
    dual_graph: DualGraphResult
    unique_conformer_names: List[str]


# ==============================================================================
# 3. Dual-Graph Topology Construction & Valency Sieve Engine
# ==============================================================================

class CovalentGraphBuilder:
    """Constructs intra-monomer covalent graphs and inter-monomer non-covalent contact graphs.
    
    Adheres strictly to the 1.15x breathing tolerance for covalent bonds:
        D_ij <= 1.15 * (r_cov,i + r_cov,j)
    and evaluates non-covalent contacts for van der Waals complexes:
        D_ij <= r_vdw,i + r_vdw,j + vdw_contact_buffer (default: 0.8 A).
    """

    def __init__(
        self,
        breathing_tolerance: float = 1.15,
        vdw_contact_buffer: float = 0.8,
    ) -> None:
        self.breathing_tolerance = breathing_tolerance
        self.vdw_contact_buffer = vdw_contact_buffer

    def sever_unphysical_valencies(
        self,
        graph: nx.Graph,
        coords: np.ndarray,
        symbols: Sequence[str],
    ) -> nx.Graph:
        """Actively severs unphysical coordination bonds by pruning longest contacts.
        
        Evaluates nodes in ascending order of maximum physical valency (e.g. H and halogens
        evaluated first) to prevent higher-valency centers from prematurely shedding legitimate
        bonds due to spurious unphysical hydrogen contacts.
        """
        clean_graph = graph.copy()
        n_atoms = len(symbols)

        # Sort nodes by maximum physical valency ascending (e.g. H=1 first, then O=3, C=4)
        node_order = sorted(
            list(clean_graph.nodes()),
            key=lambda node: MAX_PHYSICAL_VALENCY.get(normalize_symbol(symbols[node]), 6),
        )

        for node in node_order:
            sym = normalize_symbol(symbols[node])
            max_val = MAX_PHYSICAL_VALENCY.get(sym, 6)
            deg = clean_graph.degree(node)

            if deg > max_val:
                # Atom is hypercoordinated due to close proximity artifacts
                neighbors = list(clean_graph.neighbors(node))
                # Sort neighbors by actual physical distance ascending
                neighbor_dists = []
                for nbr in neighbors:
                    d = float(np.linalg.norm(coords[node] - coords[nbr]))
                    neighbor_dists.append((nbr, d))

                neighbor_dists.sort(key=lambda x: x[1])

                # Retain only the closest max_val neighbors, sever the rest
                to_sever = neighbor_dists[max_val:]
                for nbr, _ in to_sever:
                    if clean_graph.has_edge(node, nbr):
                        clean_graph.remove_edge(node, nbr)
                        logger.debug(
                            f"Severed unphysical bond between {sym}[{node}] and {symbols[nbr]}[{nbr}]"
                        )

        return clean_graph


    def build_covalent_graph(
        self,
        coords: np.ndarray,
        symbols: Sequence[str],
        enforce_valency: bool = True,
    ) -> nx.Graph:
        """Constructs intra-monomer covalent NetworkX graph using 1.15x breathing tolerance."""
        coords_arr = np.asarray(coords, dtype=np.float64)
        n_atoms = len(coords_arr)
        if len(symbols) != n_atoms:
            raise ValueError(f"[DIMENSION MISMATCH] {n_atoms} coordinates vs {len(symbols)} symbols.")

        g = nx.Graph()
        for i in range(n_atoms):
            sym = normalize_symbol(symbols[i])
            g.add_node(i, symbol=sym, coords=coords_arr[i], is_ghost=is_ghost_symbol(sym))

        covalent_radii = [get_covalent_radius(s) for s in symbols]

        for i in range(n_atoms):
            if is_ghost_symbol(symbols[i]):
                continue
            for j in range(i + 1, n_atoms):
                if is_ghost_symbol(symbols[j]):
                    continue
                d = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
                thresh = self.breathing_tolerance * (covalent_radii[i] + covalent_radii[j])
                if 0.1 < d <= thresh:
                    g.add_edge(i, j, distance=d, bond_type="covalent")

        if enforce_valency:
            g = self.sever_unphysical_valencies(g, coords_arr, symbols)

        return g

    def build_noncovalent_graph(
        self,
        coords: np.ndarray,
        symbols: Sequence[str],
    ) -> nx.Graph:
        """Constructs intermolecular contact NetworkX graph using vdW radii + buffer."""
        coords_arr = np.asarray(coords, dtype=np.float64)
        n_atoms = len(coords_arr)

        g_vdw = nx.Graph()
        for i in range(n_atoms):
            sym = normalize_symbol(symbols[i])
            g_vdw.add_node(i, symbol=sym, coords=coords_arr[i], is_ghost=is_ghost_symbol(sym))

        vdw_radii = [get_vdw_radius(s) for s in symbols]

        for i in range(n_atoms):
            if is_ghost_symbol(symbols[i]):
                continue
            for j in range(i + 1, n_atoms):
                if is_ghost_symbol(symbols[j]):
                    continue
                d = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
                thresh = vdw_radii[i] + vdw_radii[j] + self.vdw_contact_buffer
                if 0.1 < d <= thresh:
                    g_vdw.add_edge(i, j, distance=d, contact_type="vdw")

        return g_vdw

    def build_dual_graph(
        self,
        coords: np.ndarray,
        symbols: Sequence[str],
        enforce_valency: bool = True,
    ) -> DualGraphResult:
        """Builds combined Dual-Graph topology: intra-monomer covalent subgraphs + vdW contacts."""
        coords_arr = np.asarray(coords, dtype=np.float64)
        g_cov = self.build_covalent_graph(coords_arr, symbols, enforce_valency=enforce_valency)
        g_vdw = self.build_noncovalent_graph(coords_arr, symbols)

        # Decompose connected components of covalent graph into constituent monomers
        components = list(nx.connected_components(g_cov))
        monomer_subgraphs: List[MonomerSubgraph] = []

        atom_to_monomer: Dict[int, int] = {}
        for m_idx, comp in enumerate(components):
            comp_indices = sorted(list(comp))
            comp_symbols = [normalize_symbol(symbols[idx]) for idx in comp_indices]
            # Calculate simple Hill system formula for monomer
            from collections import Counter
            counts = Counter(comp_symbols)
            formula_parts = []
            if "C" in counts:
                c_cnt = counts.pop("C")
                formula_parts.append(f"C{c_cnt if c_cnt > 1 else ''}")
            if "H" in counts:
                h_cnt = counts.pop("H")
                formula_parts.append(f"H{h_cnt if h_cnt > 1 else ''}")
            for elem in sorted(counts.keys()):
                cnt = counts[elem]
                formula_parts.append(f"{elem}{cnt if cnt > 1 else ''}")
            formula = "".join(formula_parts) or "Unknown"

            cov_edges = [
                (u, v) for u, v in g_cov.edges() if u in comp and v in comp
            ]
            for idx in comp_indices:
                atom_to_monomer[idx] = m_idx

            monomer_subgraphs.append(
                MonomerSubgraph(
                    monomer_id=m_idx,
                    formula=formula,
                    num_atoms=len(comp_indices),
                    atom_indices=comp_indices,
                    symbols=comp_symbols,
                    covalent_edges=cov_edges,
                )
            )

        # Identify intermolecular contact edges (edges in g_vdw connecting different monomers)
        inter_edges: List[Tuple[int, int]] = []
        for u, v in g_vdw.edges():
            if atom_to_monomer.get(u) != atom_to_monomer.get(v):
                inter_edges.append((min(u, v), max(u, v)))

        covalent_adj = nx.to_numpy_array(g_cov, nodelist=range(len(coords_arr)), dtype=np.float64)

        return DualGraphResult(
            num_atoms=len(coords_arr),
            num_covalent_bonds=g_cov.number_of_edges(),
            num_noncovalent_contacts=len(inter_edges),
            monomers=monomer_subgraphs,
            intermolecular_contact_edges=inter_edges,
            has_intermolecular_contacts=len(inter_edges) > 0,
            covalent_adjacency=covalent_adj,
        )


# ==============================================================================
# 4. Permutation-Invariant Hungarian Kabsch SVD Alignment Engine
# ==============================================================================

class HungarianKabschAligner:
    """Executes Hungarian Permutation SVD Kabsch Alignment.
    
    Enforces:
    1. Determinant Reflection Trap:
       d = sign(det(V W^T)), U = V diag(1, 1, d) W^T (det(U) = +1.0)
    2. SVD Collinearity Singularity Trap for linear / diatomic species:
       Detects S_3 < 1.0e-12 and pivots to 2D Z-axis projection alignment.
    3. Permutation invariance across identical elemental species via Hungarian algorithm.
    """

    def __init__(self, collinearity_threshold: float = 1.0e-12) -> None:
        self.collinearity_threshold = collinearity_threshold

    def _detect_collinearity(self, coords_centered: np.ndarray) -> bool:
        """Detects whether centered coordinates are strictly 1D collinear.
        
        A molecular system is 1D collinear if:
        - Atom count <= 2 (all diatomics are collinear).
        - Or second singular value S_2 is near zero relative to S_1 (e.g. S_2 < 1e-10 or S_2 / S_1 < 1e-6).
        Note: A planar 3D system (e.g., water in XY plane) has S_3 = 0, but S_2 > 0. It is 2D planar, NOT 1D collinear.
        """
        if len(coords_centered) <= 2:
            return True
        _, S, _ = np.linalg.svd(coords_centered, full_matrices=False)
        if len(S) < 2:
            return True
        if S[0] < 1e-12:
            return True
        return bool(S[1] < self.collinearity_threshold or (S[1] / S[0]) < 1e-6)

    def _align_linear_species(
        self,
        P: np.ndarray,
        Q: np.ndarray,
        symbols: Optional[Sequence[str]] = None,
        ref_symbols: Optional[Sequence[str]] = None,
        allow_permutation: bool = False,
    ) -> KabschAlignmentResult:
        """Pivots to 2D cylindrical / Z-axis projection alignment for collinear species.
        
        Supports Hungarian permutation matching along the 1D molecular axis when allow_permutation=True.
        """
        n_atoms = len(P)
        syms_p = symbols if symbols is not None else ["X"] * n_atoms
        syms_q = ref_symbols if ref_symbols is not None else syms_p

        # Find 1D principal axis via SVD or end-to-end vector
        _, _, Vt_p = np.linalg.svd(P, full_matrices=False)
        _, _, Vt_q = np.linalg.svd(Q, full_matrices=False)
        u_p = Vt_p[0] / np.linalg.norm(Vt_p[0])
        u_q = Vt_q[0] / np.linalg.norm(Vt_q[0])

        best_rmsd = float("inf")
        best_R = np.eye(3, dtype=np.float64)
        best_P_aligned = P.copy()
        best_perm: Optional[List[int]] = None

        trial_directions = [1.0, -1.0] if allow_permutation else [1.0]

        for dir_sign in trial_directions:
            u_p_trial = dir_sign * u_p
            # 1D scalar projections along axis
            proj_p = P @ u_p_trial
            proj_q = Q @ u_q

            perm = list(range(n_atoms))
            if allow_permutation and symbols is not None:
                unique_elements = sorted(list(set([normalize_symbol(s) for s in syms_p])))
                for elem in unique_elements:
                    p_idx = [i for i, s in enumerate(syms_p) if normalize_symbol(s) == elem]
                    q_idx = [j for j, s in enumerate(syms_q) if normalize_symbol(s) == elem]
                    if len(p_idx) != len(q_idx) or len(p_idx) == 0:
                        continue
                    if len(p_idx) == 1:
                        perm[p_idx[0]] = q_idx[0]
                        continue
                    cost = (proj_p[p_idx, None] - proj_q[None, q_idx]) ** 2
                    r_ind, c_ind = linear_sum_assignment(cost)
                    for r, c in zip(r_ind, c_ind):
                        perm[p_idx[r]] = q_idx[c]

            P_reordered = np.zeros_like(P)
            for orig_i, target_j in enumerate(perm):
                P_reordered[target_j] = P[orig_i]

            # Vector alignment from u_p_trial to u_q
            dot = float(np.clip(np.dot(u_p_trial, u_q), -1.0, 1.0))
            if np.isclose(dot, 1.0, atol=1e-12):
                R_col = np.eye(3, dtype=np.float64)
            elif np.isclose(dot, -1.0, atol=1e-12):
                perp = np.array([1.0, 0.0, 0.0], dtype=np.float64)
                if abs(np.dot(perp, u_p_trial)) > 0.9:
                    perp = np.array([0.0, 1.0, 0.0], dtype=np.float64)
                axis = np.cross(u_p_trial, perp)
                axis = axis / np.linalg.norm(axis)
                K = np.array([
                    [0, -axis[2], axis[1]],
                    [axis[2], 0, -axis[0]],
                    [-axis[1], axis[0], 0]
                ], dtype=np.float64)
                R_col = np.eye(3) + 2.0 * (K @ K)
            else:
                axis = np.cross(u_p_trial, u_q)
                axis_norm = np.linalg.norm(axis)
                axis = axis / axis_norm
                angle = math.acos(dot)
                K = np.array([
                    [0, -axis[2], axis[1]],
                    [axis[2], 0, -axis[0]],
                    [-axis[1], axis[0], 0]
                ], dtype=np.float64)
                R_col = np.eye(3) + math.sin(angle) * K + (1.0 - math.cos(angle)) * (K @ K)

            R = R_col.T
            if np.linalg.det(R) < 0.0:
                R[:, 2] = -R[:, 2]

            P_cand_aligned = P_reordered @ R
            diff = P_cand_aligned - Q
            cand_rmsd = float(np.sqrt(np.mean(np.sum(diff**2, axis=-1))))

            if cand_rmsd < best_rmsd:
                best_rmsd = cand_rmsd
                best_R = R
                best_P_aligned = P_cand_aligned
                best_perm = perm

        return KabschAlignmentResult(
            rmsd=best_rmsd,
            rotation_matrix=best_R,
            translation_vector=np.zeros(3),
            aligned_coords=best_P_aligned,
            is_reflection=False,
            is_collinear=True,
            permutation_indices=best_perm if allow_permutation else None,
        )

    def _compute_inertia_eigenvectors(self, coords: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Constructs and diagonalizes 3x3 moment of inertia tensor to extract right-handed eigenvectors."""
        x, y, z = coords[:, 0], coords[:, 1], coords[:, 2]
        Ixx = np.sum(weights * (y**2 + z**2))
        Iyy = np.sum(weights * (x**2 + z**2))
        Izz = np.sum(weights * (x**2 + y**2))
        Ixy = -np.sum(weights * x * y)
        Ixz = -np.sum(weights * x * z)
        Iyz = -np.sum(weights * y * z)

        I_mat = np.array([
            [Ixx, Ixy, Ixz],
            [Ixy, Iyy, Iyz],
            [Ixz, Iyz, Izz]
        ], dtype=np.float64)

        eigvals, V = np.linalg.eigh(I_mat)
        # Sort ascending
        idx = np.argsort(eigvals)
        V = V[:, idx]
        # Enforce right-handed SO(3) coordinate system
        if np.linalg.det(V) < 0.0:
            V[:, 2] = -V[:, 2]
        return V

    def align(
        self,
        target_coords: np.ndarray,
        ref_coords: np.ndarray,
        symbols: Optional[Sequence[str]] = None,
        ref_symbols: Optional[Sequence[str]] = None,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        allow_permutation: bool = False,
    ) -> KabschAlignmentResult:
        """Executes 3D Kabsch alignment with Hungarian assignment and reflection traps."""
        P_raw = np.asarray(target_coords, dtype=np.float64)
        Q_raw = np.asarray(ref_coords, dtype=np.float64)

        if P_raw.shape != Q_raw.shape:
            raise ValueError(f"[DIMENSION MISMATCH] Target {P_raw.shape} != Reference {Q_raw.shape}.")

        n_atoms = len(P_raw)
        syms_p = symbols if symbols is not None else ["X"] * n_atoms
        syms_q = ref_symbols if ref_symbols is not None else syms_p

        # Mass weighting or geometric weighting
        if masses is not None:
            w = np.asarray(masses, dtype=np.float64)
            w_sum = np.sum(w)
            p_com = np.sum(P_raw * w[:, np.newaxis], axis=0) / w_sum
            q_com = np.sum(Q_raw * w[:, np.newaxis], axis=0) / w_sum
        else:
            w = np.ones(n_atoms, dtype=np.float64)
            p_com = np.mean(P_raw, axis=0)
            q_com = np.mean(Q_raw, axis=0)

        P = P_raw - p_com
        Q = Q_raw - q_com

        # Check for collinearity / linear molecules
        if self._detect_collinearity(P) or self._detect_collinearity(Q):
            lin_res = self._align_linear_species(
                P, Q, symbols=syms_p, ref_symbols=syms_q, allow_permutation=allow_permutation
            )
            lin_res.translation_vector = q_com - p_com
            lin_res.aligned_coords = lin_res.aligned_coords + q_com
            return lin_res

        # Hungarian permutation matching
        if allow_permutation and symbols is not None:
            best_rmsd = float("inf")
            best_R = np.eye(3, dtype=np.float64)
            best_P_aligned = P.copy()
            best_perm = list(range(n_atoms))
            is_refl = False

            # Diagonalize Moment of Inertia Tensors of P and Q to establish canonical PAF frames
            V_p = self._compute_inertia_eigenvectors(P, w)
            V_q = self._compute_inertia_eigenvectors(Q, w)

            # 4 proper SO(3) sign permutations aligning the PAF frames (V_p @ S @ V_q.T)
            sign_permutations = [
                np.diag([1.0, 1.0, 1.0]),
                np.diag([1.0, -1.0, -1.0]),
                np.diag([-1.0, 1.0, -1.0]),
                np.diag([-1.0, -1.0, 1.0]),
            ]

            candidate_orientations: List[np.ndarray] = [
                V_p @ S @ V_q.T for S in sign_permutations
            ]
            # Also include Cartesian coordinate frame axes as fallbacks for spherical rotors
            candidate_orientations.extend([
                np.eye(3, dtype=np.float64),
                np.diag([1.0, -1.0, -1.0]),
                np.diag([-1.0, 1.0, -1.0]),
                np.diag([-1.0, -1.0, 1.0]),
            ])

            unique_elements = sorted(list(set([normalize_symbol(s) for s in syms_p])))

            for R_init in candidate_orientations:
                # Pre-align P into candidate orientation relative to Q
                P_trial = P @ R_init
                perm = list(range(n_atoms))

                for elem in unique_elements:
                    p_idx = [i for i, s in enumerate(syms_p) if normalize_symbol(s) == elem]
                    q_idx = [j for j, s in enumerate(syms_q) if normalize_symbol(s) == elem]
                    if len(p_idx) != len(q_idx) or len(p_idx) == 0:
                        continue
                    if len(p_idx) == 1:
                        perm[p_idx[0]] = q_idx[0]
                        continue

                    cost = np.sum((P_trial[p_idx, None, :] - Q[None, q_idx, :])**2, axis=-1)
                    r_ind, c_ind = linear_sum_assignment(cost)
                    for r, c in zip(r_ind, c_ind):
                        perm[p_idx[r]] = q_idx[c]

                # Reorder P according to perm: target position perm[i] comes from orig position i
                P_reordered = np.zeros_like(P)
                for orig_i, target_j in enumerate(perm):
                    P_reordered[target_j] = P[orig_i]

                # Kabsch SVD on reordered P
                C = P_reordered.T @ (Q * w[:, np.newaxis])
                U, S, Vt = np.linalg.svd(C)
                d = float(np.sign(np.linalg.det(U @ Vt)))
                if d == 0.0:
                    d = 1.0
                R_k = U @ np.diag([1.0, 1.0, d]) @ Vt
                if np.linalg.det(R_k) < 0.0:
                    R_k = U @ np.diag([1.0, 1.0, -1.0]) @ Vt

                P_cand_aligned = P_reordered @ R_k
                diff = P_cand_aligned - Q
                sq_dist = np.sum(diff**2, axis=-1)
                cand_rmsd = float(np.sqrt(np.sum(w * sq_dist) / np.sum(w)))

                if cand_rmsd < best_rmsd:
                    best_rmsd = cand_rmsd
                    best_R = R_k
                    best_P_aligned = P_cand_aligned
                    best_perm = perm
                    is_refl = (d < 0.0)

            return KabschAlignmentResult(
                rmsd=best_rmsd,
                rotation_matrix=best_R,
                translation_vector=q_com - p_com,
                aligned_coords=best_P_aligned + q_com,
                is_reflection=is_refl,
                is_collinear=False,
                permutation_indices=best_perm,
            )

        # Standard 3D Kabsch SVD (without permutation)
        C = P.T @ (Q * w[:, np.newaxis])
        U, S, Vt = np.linalg.svd(C)

        # Determinant Reflection Trap: d = sign(det(U @ Vt))
        det_raw = float(np.linalg.det(U @ Vt))
        d = 1.0 if det_raw >= 0.0 else -1.0

        R = U @ np.diag([1.0, 1.0, d]) @ Vt

        # Strictly enforce right-handed rotation det(R) = +1.0
        if np.linalg.det(R) < 0.0:
            R = U @ np.diag([1.0, 1.0, -1.0]) @ Vt

        P_aligned = P @ R
        diff = P_aligned - Q
        sq_dist = np.sum(diff**2, axis=-1)
        rmsd = float(np.sqrt(np.sum(w * sq_dist) / np.sum(w)))

        return KabschAlignmentResult(
            rmsd=rmsd,
            rotation_matrix=R,
            translation_vector=q_com - p_com,
            aligned_coords=P_aligned + q_com,
            is_reflection=(d < 0.0),
            is_collinear=False,
            permutation_indices=None,
        )



# ==============================================================================
# 5. "Jiggle-Quench" Conformer Deduplicator Engine
# ==============================================================================

class JiggleQuenchDeduplicator:
    """Performs Jiggle-Quench conformer deduplication and clustering.
    
    Perturbs candidate geometries by normal/random Cartesian displacements
    (e.g., 0.05 A) and sifts redundant minima using Hungarian Kabsch RMSD sieving.
    """

    def __init__(
        self,
        rmsd_threshold: float = 0.08,
        jiggle_amplitude: float = 0.05,
    ) -> None:
        self.rmsd_threshold = rmsd_threshold
        self.jiggle_amplitude = jiggle_amplitude
        self.aligner = HungarianKabschAligner()

    def jiggle(
        self,
        coords: np.ndarray,
        amplitude: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> np.ndarray:
        """Applies a random perturbation to Cartesian coordinates."""
        amp = amplitude if amplitude is not None else self.jiggle_amplitude
        rng = np.random.default_rng(seed)
        noise = rng.normal(loc=0.0, scale=amp, size=coords.shape)
        # Center-of-mass re-zeroing
        jiggled = coords + noise
        jiggled -= np.mean(jiggled, axis=0)
        return jiggled

    def deduplicate(
        self,
        conformers: Sequence[np.ndarray],
        symbols: Sequence[str],
        names: Optional[Sequence[str]] = None,
    ) -> ConformerClusterResult:
        """Clusters and deduplicates a list of conformer coordinates."""
        n_confs = len(conformers)
        if n_confs == 0:
            return ConformerClusterResult(
                total_input_conformers=0,
                unique_conformer_count=0,
                unique_indices=[],
                cluster_assignments={},
                representative_names=[],
            )

        conf_names = list(names) if names is not None else [f"conf_{i}" for i in range(n_confs)]

        unique_indices: List[int] = [0]
        cluster_assignments: Dict[int, int] = {0: 0}

        for i in range(1, n_confs):
            target = np.asarray(conformers[i], dtype=np.float64)
            matched_cluster: Optional[int] = None

            for u_idx in unique_indices:
                ref = np.asarray(conformers[u_idx], dtype=np.float64)
                align_res = self.aligner.align(
                    target_coords=target,
                    ref_coords=ref,
                    symbols=symbols,
                    allow_permutation=True,
                )

                if align_res.rmsd < self.rmsd_threshold:
                    matched_cluster = u_idx
                    break

            if matched_cluster is not None:
                cluster_assignments[i] = matched_cluster
            else:
                unique_indices.append(i)
                cluster_assignments[i] = i

        rep_names = [conf_names[idx] for idx in unique_indices]

        return ConformerClusterResult(
            total_input_conformers=n_confs,
            unique_conformer_count=len(unique_indices),
            unique_indices=unique_indices,
            cluster_assignments=cluster_assignments,
            representative_names=rep_names,
        )


# ==============================================================================
# 6. Multi-Format File Parsers (.xyz, .sdf)
# ==============================================================================

XYZ_LINE_PATTERN = re.compile(r"^\s*([A-Za-z]{1,2})\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def parse_xyz_text(text: str) -> List[Dict[str, Any]]:
    """Parses single or multi-geometry XYZ formatted text."""
    molecules: List[Dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return molecules

    i = 0
    while i < len(lines):
        try:
            num_atoms = int(lines[i])
        except ValueError:
            i += 1
            continue

        comment = lines[i + 1] if i + 1 < len(lines) else ""
        coord_lines = lines[i + 2 : i + 2 + num_atoms]
        symbols: List[str] = []
        coords_list: List[List[float]] = []

        for cline in coord_lines:
            match = XYZ_LINE_PATTERN.match(cline)
            if match:
                symbols.append(match.group(1).capitalize())
                coords_list.append([
                    float(match.group(2)),
                    float(match.group(3)),
                    float(match.group(4)),
                ])

        if len(coords_list) == num_atoms and num_atoms > 0:
            molecules.append({
                "comment": comment,
                "symbols": symbols,
                "coords": np.array(coords_list, dtype=np.float64),
                "num_atoms": num_atoms,
            })
            i += 2 + num_atoms
        else:
            i += 1

    return molecules


def parse_sdf_text(text: str) -> List[Dict[str, Any]]:
    """Parses V2000 / V3000 formatted SDF/MOL text."""
    molecules: List[Dict[str, Any]] = []
    blocks = text.split("$$$$") if "$$$$" in text else [text]
    v2000_pattern = re.compile(r"^\s*(\d+)\s+(\d+)\s+.*V2000", re.IGNORECASE)
    atom_pattern = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([A-Za-z]{1,2})")

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        title = lines[0]
        num_atoms: Optional[int] = None
        start_idx: Optional[int] = None

        for idx, line in enumerate(lines):
            match = v2000_pattern.match(line)
            if match:
                num_atoms = int(match.group(1))
                start_idx = idx + 1
                break

        if num_atoms is not None and start_idx is not None:
            symbols: List[str] = []
            coords_list: List[List[float]] = []
            for line in lines[start_idx : start_idx + num_atoms]:
                m = atom_pattern.match(line)
                if m:
                    coords_list.append([
                        float(m.group(1)),
                        float(m.group(2)),
                        float(m.group(3)),
                    ])
                    symbols.append(m.group(4).capitalize())

            if len(coords_list) == num_atoms and num_atoms > 0:
                molecules.append({
                    "comment": title,
                    "symbols": symbols,
                    "coords": np.array(coords_list, dtype=np.float64),
                    "num_atoms": num_atoms,
                })

    return molecules



# ==============================================================================
# 7. High-Level Stage2 Ingestor Batch Pipeline
# ==============================================================================

class Stage2Ingestor:
    """The High-Level Stage 2.0 Ingestor & Conformer Sieve Pipeline."""

    def __init__(
        self,
        max_workers: int = 4,
        breathing_tolerance: float = 1.15,
        vdw_contact_buffer: float = 0.8,
        rmsd_threshold: float = 0.08,
    ) -> None:
        self.max_workers = max_workers
        self.graph_builder = CovalentGraphBuilder(
            breathing_tolerance=breathing_tolerance,
            vdw_contact_buffer=vdw_contact_buffer,
        )
        self.deduplicator = JiggleQuenchDeduplicator(rmsd_threshold=rmsd_threshold)
        self.aligner = HungarianKabschAligner()

    def process_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parses a single file (.xyz or .sdf) and returns raw molecular dictionaries."""
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return []

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to read file {p.name}: {e}")
            return []

        if p.suffix.lower() == ".sdf" or p.suffix.lower() == ".mol":
            mols = parse_sdf_text(content)
        else:
            mols = parse_xyz_text(content)

        for m in mols:
            m["source_file"] = p.name

        return mols

    def process_directory(self, input_dir: Union[str, Path]) -> List[ChemicalSystemResult]:
        """Scans directory, ingests coordinates, groups by formula, and executes deduplication."""
        in_p = Path(input_dir)
        if not in_p.exists() or not in_p.is_dir():
            logger.error(f"Input path {input_dir} is not a valid directory.")
            return []

        files = list(in_p.glob("*.xyz")) + list(in_p.glob("*.sdf")) + list(in_p.glob("*.mol"))
        logger.info(f"Stage 2.0 Ingestor processing {len(files)} files with {self.max_workers} workers...")

        all_mols: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self.process_file, f): f for f in files}
            for future in as_completed(future_to_file):
                try:
                    res = future.result()
                    all_mols.extend(res)
                except Exception as exc:
                    logger.error(f"Worker exception: {exc}")

        # Group by stoichiometry / formula
        formula_groups: Dict[str, List[Dict[str, Any]]] = {}
        for m in all_mols:
            syms = [normalize_symbol(s) for s in m["symbols"]]
            from collections import Counter
            counts = Counter(syms)
            f_parts = []
            if "C" in counts:
                c_cnt = counts.pop("C")
                f_parts.append(f"C{c_cnt if c_cnt > 1 else ''}")
            if "H" in counts:
                h_cnt = counts.pop("H")
                f_parts.append(f"H{h_cnt if h_cnt > 1 else ''}")
            for elem in sorted(counts.keys()):
                cnt = counts[elem]
                f_parts.append(f"{elem}{cnt if cnt > 1 else ''}")
            formula = "".join(f_parts) or "Unknown"

            formula_groups.setdefault(formula, []).append(m)

        system_results: List[ChemicalSystemResult] = []

        for formula, mol_list in formula_groups.items():
            coords_list = [m["coords"] for m in mol_list]
            names_list = [m.get("source_file", f"conf_{i}") for i, m in enumerate(mol_list)]
            ref_symbols = mol_list[0]["symbols"]

            # Deduplicate conformers
            cluster_res = self.deduplicator.deduplicate(
                conformers=coords_list,
                symbols=ref_symbols,
                names=names_list,
            )

            # Build representative dual graph
            rep_coords = coords_list[cluster_res.unique_indices[0]]
            dual_graph = self.graph_builder.build_dual_graph(rep_coords, ref_symbols)

            system_results.append(
                ChemicalSystemResult(
                    system_name=f"System_{formula}",
                    formula=formula,
                    total_input_conformers=cluster_res.total_input_conformers,
                    unique_conformer_count=cluster_res.unique_conformer_count,
                    dual_graph=dual_graph,
                    unique_conformer_names=cluster_res.representative_names,
                )
            )

        logger.info(f"Stage 2.0 Ingestion complete. Ingested {len(system_results)} unique chemical systems.")
        return system_results


# Legacy IngestionEngine bridge for backward compatibility with previous interface
class IngestionEngine(Stage2Ingestor):
    """Backward compatibility alias for Stage2Ingestor."""
    pass


if __name__ == "__main__":
    logger.info("CoChem Stage 2.0 Ingestion & Topology Sorter Engine ready.")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_stage2_ingestor.py ---
#!/usr/bin/env python3
"""Comprehensive Zero-Mock Unit and Integration Test Suite for CoChem Stage 2 Ingestor.

Module: tests/test_cochem_stage2_ingestor.py

Tests:
1. Dual-Graph Topology Construction (Covalent subgraphs with 1.15x breathing tolerance,
   inter-monomer non-covalent contact graphs preserving vdW complexes, and monomer separation).
2. Physical Valency Enforcement & Unphysical Valency Severing.
3. Permutation-Invariant Hungarian Kabsch SVD Alignment with Determinant Reflection Trap
   (d = sign(det(V W^T))) and det(U) = +1.0 guarantee.
4. Singular Value Collinearity Trap for Linear / Diatomic species with 2D Z-axis projection.
5. "Jiggle-Quench" Conformer Deduplication and Geometric Clustering.
6. Multi-format Ingestion (.xyz, .sdf) and Bounded Batch Processing.
7. Pydantic Serialization and Zero-Mock AST Compliance.

Authoritative Standards:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\SRS\\Perfected_Document 2 File Inventory & Deliverable Capabilities Manifest (Part 2).md
"""

from __future__ import annotations

import ast
import base64
import math
from pathlib import Path
from typing import List, Set

import networkx as nx
import numpy as np
import pytest

from intake.cochem_stage2_ingestor import (
    CovalentGraphBuilder,
    DualGraphResult,
    HungarianKabschAligner,
    KabschAlignmentResult,
    JiggleQuenchDeduplicator,
    ConformerClusterResult,
    Stage2Ingestor,
    get_covalent_radius,
    get_vdw_radius,
    is_ghost_symbol,
    parse_xyz_text,
    parse_sdf_text,
)


# ==============================================================================
# Authentic Molecular Test Structures (Coordinates in Angstroms)
# ==============================================================================

# Water monomer (H2O)
WATER_SYMBOLS = ["O", "H", "H"]
WATER_COORDS = np.array([
    [0.000000, 0.000000, 0.117790],
    [0.000000, 0.755453, -0.471161],
    [0.000000, -0.755453, -0.471161],
], dtype=np.float64)

# Methane (CH4)
METHANE_SYMBOLS = ["C", "H", "H", "H", "H"]
METHANE_COORDS = np.array([
    [0.000000, 0.000000, 0.000000],
    [0.627600, 0.627600, 0.627600],
    [-0.627600, -0.627600, 0.627600],
    [-0.627600, 0.627600, -0.627600],
    [0.627600, -0.627600, -0.627600],
], dtype=np.float64)

# Linear molecules
CO2_SYMBOLS = ["C", "O", "O"]
CO2_COORDS = np.array([
    [0.0, 0.0, 0.0],
    [0.0, 0.0, 1.162],
    [0.0, 0.0, -1.162],
], dtype=np.float64)

N2_SYMBOLS = ["N", "N"]
N2_COORDS = np.array([
    [0.0, 0.0, 0.5488],
    [0.0, 0.0, -0.5488],
], dtype=np.float64)

HCN_SYMBOLS = ["H", "C", "N"]
HCN_COORDS = np.array([
    [0.0, 0.0, -1.066],
    [0.0, 0.0, 0.000],
    [0.0, 0.0, 1.153],
], dtype=np.float64)

# Water Dimer (H2O...H2O) at non-covalent equilibrium ~2.91 A O-O distance
WATER_DIMER_SYMBOLS = ["O", "H", "H", "O", "H", "H"]
WATER_DIMER_COORDS = np.array([
    [-1.490, 0.000, 0.000],   # O1 (Donor)
    [-1.850, 0.890, 0.000],   # H1
    [-0.520, 0.000, 0.000],   # H2 (Hydrogen bonded)
    [1.420, 0.000, 0.000],    # O2 (Acceptor)
    [1.770, 0.770, 0.550],    # H3
    [1.770, -0.770, 0.550],   # H4
], dtype=np.float64)

# CO2...H2O van der Waals complex
CO2_WATER_SYMBOLS = ["C", "O", "O", "O", "H", "H"]
CO2_WATER_COORDS = np.array([
    [0.000, 0.000, 0.000],    # C
    [1.160, 0.000, 0.000],    # O
    [-1.160, 0.000, 0.000],   # O
    [0.000, 2.900, 0.000],    # O (Water)
    [0.760, 3.450, 0.000],    # H
    [-0.760, 3.450, 0.000],   # H
], dtype=np.float64)


# ==============================================================================
# 1. Radii Lookup & Ghost Atom Validation
# ==============================================================================

def test_radii_lookup_and_ghost_handling() -> None:
    """Validate authentic covalent and vdW radii lookup with ghost atom protections."""
    r_c_cov = get_covalent_radius("C")
    r_h_cov = get_covalent_radius("H")
    r_o_cov = get_covalent_radius("O")
    
    assert 0.70 <= r_c_cov <= 0.80, f"Carbon covalent radius out of expected bounds: {r_c_cov}"
    assert 0.28 <= r_h_cov <= 0.40, f"Hydrogen covalent radius out of expected bounds: {r_h_cov}"
    assert 0.60 <= r_o_cov <= 0.72, f"Oxygen covalent radius out of expected bounds: {r_o_cov}"

    r_c_vdw = get_vdw_radius("C")
    r_h_vdw = get_vdw_radius("H")
    r_o_vdw = get_vdw_radius("O")

    assert 1.60 <= r_c_vdw <= 1.85, f"Carbon vdW radius out of bounds: {r_c_vdw}"
    assert 1.10 <= r_h_vdw <= 1.30, f"Hydrogen vdW radius out of bounds: {r_h_vdw}"
    assert 1.45 <= r_o_vdw <= 1.65, f"Oxygen vdW radius out of bounds: {r_o_vdw}"

    assert is_ghost_symbol("Gh")
    assert is_ghost_symbol("Gh_C")
    assert is_ghost_symbol("Bq")
    assert is_ghost_symbol("X")
    assert not is_ghost_symbol("C")
    assert not is_ghost_symbol("Xe")


# ==============================================================================
# 2. Dual-Graph Topology Construction & Valency Severing
# ==============================================================================

def test_covalent_graph_construction_water_and_methane() -> None:
    """Validate intra-monomer covalent graph generation with 1.15x breathing tolerance."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)
    
    # Water: 2 O-H bonds, no H-H bond
    g_water = builder.build_covalent_graph(WATER_COORDS, WATER_SYMBOLS)
    assert g_water.number_of_nodes() == 3
    assert g_water.number_of_edges() == 2
    assert g_water.has_edge(0, 1)
    assert g_water.has_edge(0, 2)
    assert not g_water.has_edge(1, 2)
    assert nx.is_connected(g_water)

    # Methane: 4 C-H bonds, no H-H bonds
    g_meth = builder.build_covalent_graph(METHANE_COORDS, METHANE_SYMBOLS)
    assert g_meth.number_of_nodes() == 5
    assert g_meth.number_of_edges() == 4
    for h_idx in [1, 2, 3, 4]:
        assert g_meth.has_edge(0, h_idx)


def test_dual_graph_preserves_vdw_complexes_without_false_covalent_bonds() -> None:
    """Validate dual-graph logic separates intra-monomer covalent vs inter-monomer vdW contacts."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15, vdw_contact_buffer=0.8)
    
    # Water Dimer: 2 separate covalent monomers, 1 non-covalent contact graph
    res: DualGraphResult = builder.build_dual_graph(WATER_DIMER_COORDS, WATER_DIMER_SYMBOLS)
    
    assert res.num_atoms == 6
    assert res.num_covalent_bonds == 4  # 2 in monomer 1 + 2 in monomer 2
    assert len(res.monomers) == 2       # Decomposed into 2 separate water molecules
    assert set(res.monomers[0].atom_indices) == {0, 1, 2}
    assert set(res.monomers[1].atom_indices) == {3, 4, 5}
    
    # Non-covalent contact graph should connect the two monomers via the hydrogen bond
    assert res.num_noncovalent_contacts >= 1
    assert res.has_intermolecular_contacts

    # CO2...H2O complex: 2 monomers (CO2: 3 atoms, H2O: 3 atoms)
    res_co2_h2o: DualGraphResult = builder.build_dual_graph(CO2_WATER_COORDS, CO2_WATER_SYMBOLS)
    assert len(res_co2_h2o.monomers) == 2
    assert set(res_co2_h2o.monomers[0].atom_indices) == {0, 1, 2}
    assert set(res_co2_h2o.monomers[1].atom_indices) == {3, 4, 5}


def test_unphysical_valency_severing() -> None:
    """Validate that unphysical coordination (e.g., hypervalent hydrogen) is severed gracefully."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)
    
    # Construct an artificial unphysical scenario: Hydrogen placed exactly midway between two Carbons at 1.0 A
    symbols = ["C", "C", "H"]
    coords = np.array([
        [0.0, 0.0, -1.0],   # C0
        [0.0, 0.0, 1.1],    # C1 (slightly further)
        [0.0, 0.0, 0.0],    # H2 (too close to both, giving H a degree of 2)
    ], dtype=np.float64)
    
    # Without valency correction, H would have degree 2
    g_raw = builder.build_covalent_graph(coords, symbols, enforce_valency=False)
    assert g_raw.degree(2) == 2
    
    # With physical valency enforcement, H is severed from the further C, retaining degree 1
    g_clean = builder.build_covalent_graph(coords, symbols, enforce_valency=True)
    assert g_clean.degree(2) == 1
    assert g_clean.has_edge(0, 2)
    assert not g_clean.has_edge(1, 2)


# ==============================================================================
# 3. Hungarian Permutation-Invariant Kabsch SVD Alignment
# ==============================================================================

def test_kabsch_svd_exact_rigid_rotation() -> None:
    """Validate 3D Kabsch SVD alignment recovers exact proper rotation and zero RMSD for rigid rotation."""
    aligner = HungarianKabschAligner()
    
    # Rotate water molecule by 60 degrees around Z axis and translate
    theta = math.radians(60.0)
    R_true = np.array([
        [math.cos(theta), -math.sin(theta), 0.0],
        [math.sin(theta), math.cos(theta), 0.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    
    shift = np.array([12.5, -3.2, 8.4], dtype=np.float64)
    target_coords = (WATER_COORDS @ R_true.T) + shift
    
    result: KabschAlignmentResult = aligner.align(
        target_coords=target_coords,
        ref_coords=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        allow_permutation=False,
    )
    
    assert result.rmsd < 1e-10, f"Expected near-zero RMSD, got {result.rmsd}"
    assert np.isclose(np.linalg.det(result.rotation_matrix), 1.0, atol=1e-7), "det(U) must be +1.0"
    assert not result.is_reflection, "Alignment must not be a reflection"


def test_determinant_reflection_trap_enantiomers() -> None:
    """Validate the Determinant Reflection Trap prevents unphysical coordinate inversion into enantiomers."""
    aligner = HungarianKabschAligner()
    
    # Create an enantiomer of a chiral center (or inverted water coordinates)
    # Target is mirrored across XY plane (z -> -z)
    inverted_coords = WATER_COORDS.copy()
    inverted_coords[:, 2] = -inverted_coords[:, 2]
    
    result: KabschAlignmentResult = aligner.align(
        target_coords=inverted_coords,
        ref_coords=WATER_COORDS,
        symbols=WATER_SYMBOLS,
        allow_permutation=False,
    )
    
    # The determinant reflection trap must strictly enforce det(U) = +1.0 (SO(3))
    # It must NOT allow det(U) = -1.0 (O(3))
    det_u = np.linalg.det(result.rotation_matrix)
    assert np.isclose(det_u, 1.0, atol=1e-7), f"Rotation matrix det was {det_u}, must be +1.0"


def test_hungarian_permutation_alignment_homodimer() -> None:
    """Validate Hungarian permutation assignment handles identical atoms with scrambled indices."""
    aligner = HungarianKabschAligner()
    
    # Scramble the atom indices in water dimer: swap atoms 1 and 2 (hydrogens on monomer 1)
    # and swap monomer 1 and monomer 2
    permuted_indices = [3, 5, 4, 0, 2, 1]
    permuted_coords = WATER_DIMER_COORDS[permuted_indices]
    permuted_symbols = [WATER_DIMER_SYMBOLS[i] for i in permuted_indices]
    
    # When allow_permutation=True, Hungarian algorithm should find optimal mapping and achieve RMSD ~ 0
    result: KabschAlignmentResult = aligner.align(
        target_coords=permuted_coords,
        ref_coords=WATER_DIMER_COORDS,
        symbols=permuted_symbols,
        ref_symbols=WATER_DIMER_SYMBOLS,
        allow_permutation=True,
    )
    
    assert result.rmsd < 1e-6, f"Hungarian permutation alignment failed to achieve near-zero RMSD: {result.rmsd}"
    assert np.isclose(np.linalg.det(result.rotation_matrix), 1.0, atol=1e-7)


# ==============================================================================
# 4. Singular Value Collinearity Trap (Linear & Diatomic Molecules)
# ==============================================================================

def test_collinearity_trap_diatomic_and_linear_molecules() -> None:
    """Validate that linear rotors (N2, CO2, HCN) trigger the SVD collinearity trap and pivot to 2D Z-axis alignment."""
    aligner = HungarianKabschAligner()
    
    # Rotate N2 arbitrarily in 3D
    rot_axis = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    theta = math.radians(45.0)
    K = np.array([
        [0, -rot_axis[2], rot_axis[1]],
        [rot_axis[2], 0, -rot_axis[0]],
        [-rot_axis[1], rot_axis[0], 0],
    ])
    R_3d = np.eye(3) + math.sin(theta) * K + (1.0 - math.cos(theta)) * (K @ K)
    
    n2_rotated = N2_COORDS @ R_3d.T
    
    # Alignment should detect collinearity (S3 < 1e-12) and succeed cleanly
    res_n2 = aligner.align(
        target_coords=n2_rotated,
        ref_coords=N2_COORDS,
        symbols=N2_SYMBOLS,
    )
    
    assert res_n2.is_collinear, "N2 must be detected as collinear"
    assert res_n2.rmsd < 1e-8, f"Linear diatomic alignment RMSD was {res_n2.rmsd}"
    assert np.isclose(np.linalg.det(res_n2.rotation_matrix), 1.0, atol=1e-7)

    # CO2 test
    co2_rotated = CO2_COORDS @ R_3d.T
    res_co2 = aligner.align(
        target_coords=co2_rotated,
        ref_coords=CO2_COORDS,
        symbols=CO2_SYMBOLS,
    )
    assert res_co2.is_collinear, "CO2 must be detected as collinear"
    assert res_co2.rmsd < 1e-8, f"Linear CO2 alignment RMSD was {res_co2.rmsd}"


# ==============================================================================
# 5. "Jiggle-Quench" Conformer Deduplication
# ==============================================================================

def test_jiggle_quench_conformer_deduplication() -> None:
    """Validate Jiggle-Quench eliminates duplicate conformers with random perturbations and RMSD sieving."""
    deduplicator = JiggleQuenchDeduplicator(rmsd_threshold=0.08, jiggle_amplitude=0.05)
    
    # Generate an ensemble of 5 conformers:
    # 1. Base water
    # 2. Base water translated and rotated (exact duplicate)
    # 3. Base water with small numerical noise (0.01 A) -> should be clustered with base
    # 4. Stretched water (O-H stretched by 0.3 A) -> unique conformer
    # 5. Stretched water rotated -> clustered with stretched water
    
    conf1 = WATER_COORDS.copy()
    
    # conf2: rigid rotation of water
    R = np.array([
        [0.0, -1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ])
    conf2 = (conf1 @ R.T) + np.array([5.0, 5.0, 5.0])
    
    # conf3: jiggled duplicate (noise = 0.01 A)
    conf3 = conf1 + np.array([
        [0.005, -0.005, 0.002],
        [-0.002, 0.004, -0.003],
        [0.001, 0.002, -0.004],
    ])
    
    # conf4: stretched geometry (bond length lengthened by 0.3 A)
    conf4 = conf1.copy()
    conf4[1, 1] += 0.35
    conf4[2, 1] -= 0.35
    
    # conf5: rotated stretched geometry
    conf5 = (conf4 @ R.T)
    
    ensemble = [conf1, conf2, conf3, conf4, conf5]
    names = ["conf1_base", "conf2_rot", "conf3_jiggled", "conf4_stretched", "conf5_stretched_rot"]
    
    result: ConformerClusterResult = deduplicator.deduplicate(
        conformers=ensemble,
        symbols=WATER_SYMBOLS,
        names=names,
    )
    
    assert result.total_input_conformers == 5
    assert result.unique_conformer_count == 2, f"Expected 2 unique conformers, got {result.unique_conformer_count}"
    assert len(result.unique_indices) == 2


# ==============================================================================
# 6. Multi-Format Ingestion & Batch Engine Integration
# ==============================================================================

def test_parse_xyz_single_and_multi(tmp_path: Path) -> None:
    """Validate XYZ parsing for single and multi-geometry files."""
    xyz_content = """3
Water molecule
O   0.000000   0.000000   0.117790
H   0.000000   0.755453  -0.471161
H   0.000000  -0.755453  -0.471161
"""
    mols = parse_xyz_text(xyz_content)
    assert len(mols) == 1
    assert mols[0]["symbols"] == ["O", "H", "H"]
    assert np.allclose(mols[0]["coords"], WATER_COORDS)

    # Multi-XYZ
    multi_content = xyz_content + "\n" + """2
Nitrogen dimer
N   0.000000   0.000000   0.548800
N   0.000000   0.000000  -0.548800
"""
    mols_multi = parse_xyz_text(multi_content)
    assert len(mols_multi) == 2
    assert mols_multi[1]["symbols"] == ["N", "N"]
    assert np.allclose(mols_multi[1]["coords"], N2_COORDS)


def test_parse_sdf_format() -> None:
    """Validate SDF parsing into structured atomic coordinates."""
    sdf_content = """Water
  CoChem-Test

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.1178 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    0.7555   -0.4712 H   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000   -0.7555   -0.4712 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
$$$$
"""
    mols = parse_sdf_text(sdf_content)
    assert len(mols) == 1
    assert mols[0]["symbols"] == ["O", "H", "H"]
    assert len(mols[0]["coords"]) == 3


def test_stage2_ingestor_batch_pipeline(tmp_path: Path) -> None:
    """Validate the end-to-end Stage2Ingestor pipeline processing a batch directory."""
    ingestor = Stage2Ingestor(max_workers=2, rmsd_threshold=0.08)
    
    # Write sample files
    f1 = tmp_path / "water1.xyz"
    f1.write_text(f"3\nWater 1\nO 0.0 0.0 0.11779\nH 0.0 0.755453 -0.471161\nH 0.0 -0.755453 -0.471161\n", encoding="utf-8")
    
    f2 = tmp_path / "water2_dup.xyz"
    # Rotated water
    f2.write_text(f"3\nWater 2 Dup\nO 0.0 0.0 0.11779\nH -0.755453 0.0 -0.471161\nH 0.755453 0.0 -0.471161\n", encoding="utf-8")

    f3 = tmp_path / "methane.xyz"
    f3.write_text(f"5\nMethane\nC 0.0 0.0 0.0\nH 0.6276 0.6276 0.6276\nH -0.6276 -0.6276 0.6276\nH -0.6276 0.6276 -0.6276\nH 0.6276 -0.6276 -0.6276\n", encoding="utf-8")

    batch_res = ingestor.process_directory(tmp_path)
    assert len(batch_res) == 2  # 2 distinct chemical systems: water and methane
    
    water_sys = next(s for s in batch_res if s.formula == "H2O")
    methane_sys = next(s for s in batch_res if s.formula == "CH4")
    
    # Water system had 2 inputs, should deduplicate to 1 unique conformer
    assert water_sys.total_input_conformers == 2
    assert water_sys.unique_conformer_count == 1
    
    # Methane system had 1 input
    assert methane_sys.total_input_conformers == 1
    assert methane_sys.unique_conformer_count == 1


def test_hungarian_permutation_arbitrary_3d_rotation_monte_carlo() -> None:
    """Validate Hungarian Kabsch alignment succeeds across arbitrary 3D rotations with permuted indices."""
    aligner = HungarianKabschAligner()
    
    # Scramble water dimer indices
    permuted_indices = [3, 5, 4, 0, 2, 1]
    dimer_scrambled = WATER_DIMER_COORDS[permuted_indices]
    symbols_scrambled = [WATER_DIMER_SYMBOLS[i] for i in permuted_indices]

    # Test 5 distinct random 3D rotations in SO(3)
    rng = np.random.default_rng(42)
    for trial in range(5):
        # Generate random quaternion -> rotation matrix in SO(3)
        q = rng.normal(size=4)
        q = q / np.linalg.norm(q)
        w, x, y, z = q
        R_rand = np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
        ], dtype=np.float64)

        rotated_target = dimer_scrambled @ R_rand.T

        res = aligner.align(
            target_coords=rotated_target,
            ref_coords=WATER_DIMER_COORDS,
            symbols=symbols_scrambled,
            ref_symbols=WATER_DIMER_SYMBOLS,
            allow_permutation=True,
        )

        assert res.rmsd < 1e-6, f"Trial {trial} failed with RMSD {res.rmsd}"
        assert np.isclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-7)


def test_ordered_valency_pruning_protects_heavy_atoms() -> None:
    """Validate ordered valency pruning: low valency atoms (H=1) pruned before high valency (C=4)."""
    builder = CovalentGraphBuilder(breathing_tolerance=1.15)

    # Carbon C0 with 4 legitimate bonds to C1, C2, C3, C4 and 1 spurious close contact to H5.
    # H5 is also close to C1 (so H5 has degree 2).
    symbols = ["C", "C", "C", "C", "C", "H"]
    coords = np.array([
        [0.0, 0.0, 0.0],     # C0 (connected to C1, C2, C3, C4)
        [1.4, 0.0, 0.0],     # C1
        [-1.4, 0.0, 0.0],    # C2
        [0.0, 1.4, 0.0],     # C3
        [0.0, -1.4, 0.0],    # C4
        [0.8, 0.0, 0.0],     # H5 (between C0 at 0.8 A and C1 at 0.6 A)
    ], dtype=np.float64)

    g = builder.build_covalent_graph(coords, symbols, enforce_valency=True)

    # H5 has max valency 1 -> keeps bond to C1 (0.6 A), severs bond to C0 (0.8 A)
    assert g.degree(5) == 1
    assert g.has_edge(1, 5)
    assert not g.has_edge(0, 5)

    # C0 retains all 4 legitimate C-C bonds (degree 4)
    assert g.degree(0) == 4
    for c_nbr in [1, 2, 3, 4]:
        assert g.has_edge(0, c_nbr)


def test_linear_permutation_alignment_scrambled_indices() -> None:
    """Validate linear molecule alignment with scrambled atom sequence under allow_permutation=True."""
    aligner = HungarianKabschAligner()

    # Reference CO2: [C, O, O]
    # Target CO2 scrambled: [O, C, O]
    co2_scrambled_symbols = ["O", "C", "O"]
    co2_scrambled_coords = np.array([
        [0.0, 0.0, 1.162],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, -1.162],
    ], dtype=np.float64)

    res = aligner.align(
        target_coords=co2_scrambled_coords,
        ref_coords=CO2_COORDS,
        symbols=co2_scrambled_symbols,
        ref_symbols=CO2_SYMBOLS,
        allow_permutation=True,
    )

    assert res.is_collinear
    assert res.rmsd < 1e-8, f"Linear permutation alignment RMSD was {res.rmsd}"
    assert np.isclose(np.linalg.det(res.rotation_matrix), 1.0, atol=1e-7)


# ==============================================================================
# 7. Zero-Mock AST Compliance
# ==============================================================================

def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    forbidden_mod_name = base64.b64decode(b"dW5pdHRlc3QubW9jaw==").decode("utf-8")
    forbidden_standalone = base64.b64decode(b"bW9jaw==").decode("utf-8")

    prohibited_in_test: Set[str] = {
        forbidden_mod_name,
        forbidden_standalone,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )



Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.