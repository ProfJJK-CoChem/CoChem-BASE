"""CoChem-TOPOS Molecular Topology & Graph Connectivity Engine.

Provides:
- Robust atomic coordinate & symbol Pydantic validation (AtomModel).
- Covalent radius resolution via QCElemental with comprehensive fallback table.
- Efficient Euclidean pairwise distance matrix computation.
- Topology validation and sanitization against physical covalent thresholds:
  Validates abstract adjacency matrices against physical interatomic distances;
  unphysical edges (> sum of covalent radii + tol) are removed and trigger
  dynamic re-derivation with configurable scaling factor alpha (default 1.15).
- Graph connectivity and fragment extraction via scipy.sparse.csgraph connected components.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Sequence, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from scipy.sparse.csgraph import connected_components

try:
    import qcelemental as qcel
except ImportError:
    qcel = None

logger = logging.getLogger(__name__)

# Fallback covalent radii in Angstroms (Pyykkö and Atsumi / Alvarez et al. standards)
FALLBACK_RADII: dict[str, float] = {
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
    "Sc": 1.70,
    "Ti": 1.60,
    "V": 1.53,
    "Cr": 1.39,
    "Mn": 1.39,
    "Fe": 1.32,
    "Co": 1.26,
    "Ni": 1.24,
    "Cu": 1.32,
    "Zn": 1.22,
    "Ga": 1.22,
    "Ge": 1.20,
    "As": 1.19,
    "Se": 1.20,
    "Br": 1.20,
    "Kr": 1.16,
    "Rb": 2.20,
    "Sr": 1.95,
    "Y": 1.90,
    "Zr": 1.75,
    "Nb": 1.64,
    "Mo": 1.54,
    "Tc": 1.47,
    "Ru": 1.46,
    "Rh": 1.42,
    "Pd": 1.39,
    "Ag": 1.45,
    "Cd": 1.44,
    "In": 1.42,
    "Sn": 1.39,
    "Sb": 1.39,
    "Te": 1.38,
    "I": 1.39,
    "Xe": 1.40,
    "Cs": 2.44,
    "Ba": 2.15,
    "La": 2.07,
    "Ce": 2.04,
    "Pr": 2.03,
    "Nd": 2.01,
    "Pm": 1.99,
    "Sm": 1.98,
    "Eu": 1.98,
    "Gd": 1.96,
    "Tb": 1.94,
    "Dy": 1.92,
    "Ho": 1.92,
    "Er": 1.89,
    "Tm": 1.90,
    "Yb": 1.87,
    "Lu": 1.87,
    "Hf": 1.75,
    "Ta": 1.70,
    "W": 1.62,
    "Re": 1.51,
    "Os": 1.44,
    "Ir": 1.41,
    "Pt": 1.36,
    "Au": 1.36,
    "Hg": 1.32,
    "Tl": 1.45,
    "Pb": 1.46,
    "Bi": 1.48,
    "Po": 1.40,
    "At": 1.50,
    "Rn": 1.50,
    "Fr": 2.60,
    "Ra": 2.21,
    "Ac": 2.15,
    "Th": 2.06,
    "Pa": 2.00,
    "U": 1.96,
    "Np": 1.90,
    "Pu": 1.87,
    "Am": 1.80,
    "Cm": 1.69,
}


class AtomModel(BaseModel):
    """Pydantic model representing an atom with element symbol and 3D Cartesian coordinates."""

    model_config = ConfigDict(extra="ignore")

    symbol: str = Field(..., description="IUPAC atomic element symbol (e.g. C, H, O)")
    coords: Tuple[float, float, float] = Field(..., description="Cartesian coordinates (x, y, z) in Angstroms")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("[MISSING DATA] Atomic symbol cannot be empty.")
        return v.strip().capitalize()

    @field_validator("coords", mode="before")
    @classmethod
    def validate_coords(cls, v: Any) -> Tuple[float, float, float]:
        if isinstance(v, (list, tuple, np.ndarray)):
            if len(v) != 3:
                raise ValueError(f"[MISSING DATA] Coordinates must have exactly 3 dimensions (x, y, z), got {len(v)}.")
            return (float(v[0]), float(v[1]), float(v[2]))
        raise TypeError(f"[MISSING DATA] Unsupported coordinate type: {type(v).__name__}")


def get_covalent_radius(symbol: str) -> float:
    """Helper to get covalent radius in Angstroms safely without hallucinating.

    Parameters
    ----------
    symbol : str
        Elemental symbol (e.g., 'C', 'H', 'Fe').

    Returns
    -------
    float
        Covalent radius in Angstroms.

    Raises
    ------
    ValueError
        If the atomic symbol is invalid or the radius is missing.
    """
    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("[MISSING DATA] Atomic symbol cannot be empty.")

    cap_symbol = symbol.strip().capitalize()

    if qcel is not None:
        try:
            val = qcel.covalentradii.get(cap_symbol, units="angstrom")
            if val is not None and not np.isnan(val):
                return float(val)
        except KeyError:
            pass
        except (RuntimeError, ValueError, OSError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            if type(e).__name__ in ("NotAnElementError", "ValidationError", "DataUnavailableError"):
                pass
            else:
                logger.warning("Unexpected error accessing qcelemental for %s: %s", cap_symbol, e)

    if cap_symbol in FALLBACK_RADII:
        return float(FALLBACK_RADII[cap_symbol])

    raise ValueError(f"[MISSING DATA] Covalent radius for symbol '{symbol}' is unknown.")


def compute_distance_matrix(coords: np.ndarray) -> np.ndarray:
    """Computes symmetric NxN Euclidean pairwise distance matrix for N 3D coordinates.

    Parameters
    ----------
    coords : np.ndarray
        Array of shape (N, 3) with Cartesian coordinates in Angstroms.

    Returns
    -------
    np.ndarray
        Symmetric (N, N) distance matrix.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ValueError(f"[MISSING DATA] Expected coordinates array of shape (N, 3), got {coords_arr.shape}.")
    diffs = coords_arr[:, np.newaxis, :] - coords_arr[np.newaxis, :, :]
    return np.linalg.norm(diffs, axis=-1)


def compute_covalent_adjacency(
    atoms: Sequence[Dict[str, Any] | AtomModel],
    alpha: float = 1.15,
) -> np.ndarray:
    """Constructs a binary covalent adjacency matrix from atomic symbols and coordinates.

    An edge is placed between atom i and atom j (i != j) if:
        distance(i, j) <= alpha * (r_cov(i) + r_cov(j))

    Parameters
    ----------
    atoms : Sequence[Dict[str, Any] | AtomModel]
        List or sequence of atom representations.
    alpha : float, default 1.15
        Covalent bond cutoff scaling factor (Standard CoChem value: 1.15).

    Returns
    -------
    np.ndarray
        (N, N) binary adjacency matrix (np.int32).
    """
    if not atoms:
        raise ValueError("[MISSING DATA] atoms list is empty or missing.")

    coords_list = []
    radii = []

    for idx, item in enumerate(atoms):
        if isinstance(item, AtomModel):
            atom_model = item
        elif isinstance(item, dict):
            coord_val = item.get("coords", item.get("position"))
            if coord_val is None and "x" in item and "y" in item and "z" in item:
                coord_val = (item["x"], item["y"], item["z"])
            if coord_val is None:
                raise ValueError(f"[MISSING DATA] Atomic coordinates are missing for atom index {idx}.")
            symbol_val = item.get("symbol")
            if symbol_val is None:
                raise ValueError(f"[MISSING DATA] Atomic symbol is missing for atom index {idx}.")
            try:
                atom_model = AtomModel(symbol=symbol_val, coords=coord_val)
            except ValidationError as e:
                raise ValueError(f"[MISSING DATA] Pydantic validation failed for atom {idx}: {e}")
        else:
            raise TypeError(f"[MISSING DATA] Unsupported atom representation at index {idx}: {type(item).__name__}")

        coords_list.append(atom_model.coords)
        radii.append(get_covalent_radius(atom_model.symbol))

    coords_arr = np.array(coords_list, dtype=np.float64)
    dist_mat = compute_distance_matrix(coords_arr)
    radii_arr = np.array(radii, dtype=np.float64)
    radii_sum = radii_arr[:, np.newaxis] + radii_arr[np.newaxis, :]

    threshold = alpha * radii_sum
    adj = (dist_mat <= threshold).astype(np.int32)
    np.fill_diagonal(adj, 0)
    return adj


def validate_and_sanitize_topology(
    atoms: Sequence[Dict[str, Any] | AtomModel],
    abstract_adjacency: np.ndarray,
    tol: float = 0.8,
    alpha: float = 1.15,
) -> np.ndarray:
    """Validates the given abstract adjacency matrix against physical atomic coordinates.

    If any edge in the abstract adjacency matrix exceeds the sum of covalent radii + tol,
    it removes the edge, logs the error code `[E: TOPOLOGY_SANITIZED_UNPHYSICAL_EDGE]`,
    and re-derives the entire adjacency matrix dynamically using `alpha` (default 1.15).

    Parameters
    ----------
    atoms : Sequence[Dict[str, Any] | AtomModel]
        Sequence of atomic definitions containing symbol and coordinates.
    abstract_adjacency : np.ndarray
        (N, N) candidate adjacency matrix to validate.
    tol : float, default 0.8
        Tolerance added to the sum of covalent radii before an edge is classified unphysical (Angstroms).
    alpha : float, default 1.15
        Scaling factor used when dynamically re-deriving the adjacency matrix upon detecting unphysical edges.

    Returns
    -------
    np.ndarray
        (N, N) sanitized binary adjacency matrix (np.int32).
    """
    if abstract_adjacency is None:
        raise ValueError("[MISSING DATA] abstract_adjacency is missing.")

    if not atoms:
        raise ValueError("[MISSING DATA] atoms list is empty or missing.")

    n_atoms = len(atoms)
    abstract_adj_arr = np.asarray(abstract_adjacency, dtype=np.int32)

    if abstract_adj_arr.ndim != 2 or abstract_adj_arr.shape[0] != abstract_adj_arr.shape[1]:
        raise ValueError(
            f"[MISSING DATA] abstract_adjacency must be a 2D square matrix, got shape {abstract_adj_arr.shape}."
        )

    if abstract_adj_arr.shape[0] != n_atoms:
        raise ValueError(
            f"[MISSING DATA] Dimension mismatch: {n_atoms} atoms provided, but adjacency matrix is {abstract_adj_arr.shape}."
        )

    coords_list = []
    radii = []

    for idx, item in enumerate(atoms):
        if isinstance(item, AtomModel):
            atom_model = item
        elif isinstance(item, dict):
            coord_val = item.get("coords", item.get("position"))
            if coord_val is None and "x" in item and "y" in item and "z" in item:
                coord_val = (item["x"], item["y"], item["z"])
            if coord_val is None:
                raise ValueError(f"[MISSING DATA] Atomic coordinates are missing for atom index {idx}.")
            symbol_val = item.get("symbol")
            if symbol_val is None:
                raise ValueError(f"[MISSING DATA] Atomic symbol is missing for atom index {idx}.")
            try:
                atom_model = AtomModel(symbol=symbol_val, coords=coord_val)
            except ValidationError as e:
                raise ValueError(f"[MISSING DATA] Pydantic validation failed for atom {idx}: {e}")
        else:
            raise TypeError(f"[MISSING DATA] Unsupported atom representation at index {idx}: {type(item).__name__}")

        coords_list.append(atom_model.coords)
        radii.append(get_covalent_radius(atom_model.symbol))

    coords_arr = np.array(coords_list, dtype=np.float64)
    dist_mat = compute_distance_matrix(coords_arr)
    radii_arr = np.array(radii, dtype=np.float64)
    radii_sum = radii_arr[:, np.newaxis] + radii_arr[np.newaxis, :]

    sanitized = abstract_adj_arr.copy()
    np.fill_diagonal(sanitized, 0)
    unphysical_found = False

    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            if abstract_adj_arr[i, j] > 0 or abstract_adj_arr[j, i] > 0:
                dist = dist_mat[i, j]
                r_sum = radii_sum[i, j]
                threshold = r_sum + tol

                if dist > threshold:
                    sanitized[i, j] = 0
                    sanitized[j, i] = 0
                    logger.warning(
                        "[E: TOPOLOGY_SANITIZED_UNPHYSICAL_EDGE] Edge %s-%s removed (dist=%.3f, threshold=%.3f)",
                        i,
                        j,
                        float(dist),
                        float(threshold),
                    )
                    unphysical_found = True

    if unphysical_found:
        return compute_covalent_adjacency(atoms, alpha=alpha)

    # Ensure output is symmetric int32
    sanitized = np.maximum(sanitized, sanitized.T)
    return sanitized


def get_connected_components(adjacency: np.ndarray) -> int:
    """Returns the number of connected components in the graph defined by the adjacency matrix.

    Parameters
    ----------
    adjacency : np.ndarray
        (N, N) adjacency matrix.

    Returns
    -------
    int
        Number of connected components.
    """
    if adjacency is None:
        raise ValueError("[MISSING DATA] adjacency matrix is missing.")

    adj_arr = np.asarray(adjacency)
    if adj_arr.size == 0:
        raise ValueError("[MISSING DATA] adjacency matrix is empty.")

    if adj_arr.ndim != 2 or adj_arr.shape[0] != adj_arr.shape[1]:
        raise ValueError(f"[MISSING DATA] Expected square 2D adjacency matrix, got shape {adj_arr.shape}.")

    n_components, _ = connected_components(csgraph=adj_arr, directed=False, return_labels=True)
    return int(n_components)


def get_fragment_indices(adjacency: np.ndarray) -> list[list[int]]:
    """Partitions the atoms into connected component groups (fragments).

    Parameters
    ----------
    adjacency : np.ndarray
        (N, N) adjacency matrix.

    Returns
    -------
    list[list[int]]
        List of lists containing atom indices for each fragment.
    """
    if adjacency is None:
        raise ValueError("[MISSING DATA] adjacency matrix is missing.")

    adj_arr = np.asarray(adjacency)
    if adj_arr.size == 0:
        return []

    if adj_arr.ndim != 2 or adj_arr.shape[0] != adj_arr.shape[1]:
        raise ValueError(f"[MISSING DATA] Expected square 2D adjacency matrix, got shape {adj_arr.shape}.")

    n_components, labels = connected_components(csgraph=adj_arr, directed=False, return_labels=True)
    fragments: list[list[int]] = [[] for _ in range(n_components)]
    for idx, label in enumerate(labels):
        fragments[label].append(idx)
    return fragments


def is_connected(adjacency: np.ndarray) -> bool:
    """Checks whether the molecular graph is fully connected (i.e. single connected component).

    Parameters
    ----------
    adjacency : np.ndarray
        (N, N) adjacency matrix.

    Returns
    -------
    bool
        True if the entire graph is connected, False if disconnected or multiple fragments.
    """
    return get_connected_components(adjacency) == 1
