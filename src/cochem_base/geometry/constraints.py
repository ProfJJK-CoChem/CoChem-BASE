"""Frozen-Monomer Spatial Protections and Internal Coordinate Constraint Generator.

Compliant with Method Matrix v4 §9A.1-9A.7, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
"""

from __future__ import annotations

import itertools
import math
from functools import lru_cache
from typing import Any, List, Optional, Sequence, Set, Tuple, Union
from mendeleev import element as mendeleev_element
import networkx as nx
import numpy as np

from cochem_base.schemas import ConstraintPayload
from cochem_base.exceptions import FrozenMonomerViolationError, TrajectoryDriftViolationError


@lru_cache(maxsize=128)
def get_dynamic_covalent_radius(symbol: str) -> float:
    """Retrieve Pyykkö covalent radius in Angstroms via mendeleev."""
    clean = str(symbol).strip().rstrip(":").capitalize()
    el = mendeleev_element(clean)
    if hasattr(el, "covalent_radius_pyykko") and el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if hasattr(el, "covalent_radius") and el.covalent_radius is not None:
        return float(el.covalent_radius) / 100.0
    raise ValueError(f"No covalent radius available for {symbol}.")


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
    if len(symbols) == 0 or coords.shape != (len(symbols), 3) or not np.all(np.isfinite(coords)):
        raise ValueError("Geometry must contain finite N x 3 coordinates matching the atom symbols.")
    radii = [get_dynamic_covalent_radius(s) for s in symbols]
    G = nx.Graph()
    G.add_nodes_from(range(len(symbols)))

    subsets = atom_subsets if atom_subsets is not None else [list(range(len(symbols)))]
    flattened = [i for subset in subsets for i in subset]
    if len(flattened) != len(set(flattened)) or any(
        isinstance(i, bool) or not isinstance(i, (int, np.integer)) or i < 0 or i >= len(symbols)
        for i in flattened
    ):
        raise FrozenMonomerViolationError("Monomer atom subsets must be disjoint, unique and within the geometry.")
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
    if any(isinstance(i, bool) or not isinstance(i, (int, np.integer)) or i < 0 for i in [*atoms_a, *atoms_b]):
        raise FrozenMonomerViolationError("Monomer indices must be nonnegative integers, not booleans.")
    set_a: Set[int] = set(atoms_a)
    set_b: Set[int] = set(atoms_b)
    if not set_a or not set_b or set_a & set_b or len(set_a) != len(atoms_a) or len(set_b) != len(atoms_b):
        raise FrozenMonomerViolationError("Monomer atom subsets must be nonempty, unique and disjoint.")

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
    if not (set_a | set_b).issubset(G.nodes):
        raise FrozenMonomerViolationError("The molecular graph does not contain all monomer atoms.")
    for monomer in (set_a, set_b):
        if not nx.is_connected(G.subgraph(monomer)):
            raise FrozenMonomerViolationError("Each monomer must be covalently connected.")

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
    thresh = {
        "TolE": "1e-7",
        "TolRMSG": "3e-6",
        "TolMaxG": "1e-5",
        "TolRMSD": "5e-5",
        "TolMaxD": "1e-4",
        "MaxIter": "200",
    }
    if convergence_thresholds is not None:
        for key, value in convergence_thresholds.items():
            if key not in thresh or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"Unsupported or invalid convergence threshold: {key}.")
            if key != "MaxIter" and float(value) > float(thresh[key]):
                raise ValueError(f"{key} cannot relax the SRS convergence threshold.")
            if key == "MaxIter" and (float(value) != int(float(value)) or int(float(value)) > 200):
                raise ValueError("MaxIter must be an integer no greater than 200.")
            thresh[key] = str(value)
    lines: list[str] = ["%geom", "  InHess XTB2"]
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


def validate_trajectory_monomer_drift(
    trajectory: Sequence[Union[Sequence[Sequence[float]], np.ndarray]],
    monomer_indices: Sequence[int],
    tolerance: float = 1.0e-6,
    *,
    raise_on_violation: bool = False,
) -> Tuple[bool, float]:
    """Validate that internal pairwise distances within a frozen monomer remain invariant across a trajectory.

    Parameters
    ----------
    trajectory : Sequence[np.ndarray]
        List or array of Cartesian geometries [N_steps, N_atoms, 3].
    monomer_indices : Sequence[int]
        Indices of atoms belonging to the monomer whose internal geometry should be rigid.
    tolerance : float, default 1.0e-6
        Maximum permissible internal distance deviation in Angstroms.

    Returns
    -------
    Tuple[bool, float]
        (is_valid, max_drift) where max_drift is the maximum distance variation observed.
    """
    if len(trajectory) == 0:
        raise ValueError("An empty trajectory cannot establish frozen-monomer integrity.")
    if not math.isfinite(tolerance) or not 0 < tolerance <= 1.0e-6:
        raise ValueError("Monomer drift tolerance must be positive and no greater than 1e-6 Angstrom.")

    steps = [np.asarray(step, dtype=np.float64) for step in trajectory]
    indices = sorted(list(monomer_indices))
    if not indices or len(indices) != len(set(indices)):
        raise ValueError("Monomer indices must be nonempty and unique.")
    for step in steps:
        if step.ndim != 2 or step.shape[1] != 3 or step.shape != steps[0].shape or not np.all(np.isfinite(step)):
            raise ValueError("Each trajectory frame must be a finite N x 3 geometry of the same shape.")
    if any(isinstance(i, bool) or not isinstance(i, (int, np.integer)) or i < 0 or i >= len(steps[0]) for i in indices):
        raise ValueError("Monomer atom index is outside the trajectory geometry.")
    if len(indices) == 1:
        return True, 0.0

    # Reference pairwise distances from step 0
    ref_step = steps[0]
    ref_distances: dict[Tuple[int, int], float] = {}
    for i_idx, i in enumerate(indices):
        for j in indices[i_idx + 1 :]:
            ref_distances[(i, j)] = float(np.linalg.norm(ref_step[i] - ref_step[j]))

    max_drift: float = 0.0
    for step in steps[1:]:
        for (i, j), ref_d in ref_distances.items():
            curr_d = float(np.linalg.norm(step[i] - step[j]))
            drift = abs(curr_d - ref_d)
            if drift > max_drift:
                max_drift = drift

    is_valid = max_drift < tolerance and not math.isclose(max_drift, tolerance, rel_tol=1e-10)
    if not is_valid and raise_on_violation:
        raise TrajectoryDriftViolationError(details={"max_drift_angstrom": max_drift, "tolerance_angstrom": tolerance})
    return is_valid, max_drift


FrozenConstraintPayload = ConstraintPayload


def build_wilson_b_matrix(
    constraints: ConstraintPayload,
    coordinates: Union[Sequence[Sequence[float]], np.ndarray],
    difference_step: float = 1e-6,
) -> np.ndarray:
    """Return d(internal coordinates)/d(Cartesians), in Angstrom/radian units.

    Bond and angle derivatives are analytic. Proper torsions use centered
    differences of their wrapped angles. A linear angle has two independent
    transverse bending coordinates: a linear monomer has 3N-5 internal modes,
    not the 3N-6 applicable to a nonlinear monomer.
    """
    coords = np.asarray(coordinates, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 3 or len(coords) == 0 or not np.all(np.isfinite(coords)):
        raise ValueError("Wilson coordinates must be a finite N x 3 array.")
    if not math.isfinite(difference_step) or difference_step <= 0:
        raise ValueError("Finite-difference step must be finite and positive.")
    for entry in [*constraints.bonds, *constraints.angles, *constraints.dihedrals]:
        if len(set(entry)) != len(entry) or any(i < 0 or i >= len(coords) for i in entry):
            raise FrozenMonomerViolationError("Invalid atom indices in Wilson internal coordinates.")
    rows: list[np.ndarray] = []
    for i, j in constraints.bonds:
        diff = coords[i] - coords[j]
        norm = np.linalg.norm(diff)
        if norm < 1e-12:
            raise FrozenMonomerViolationError("Coincident atoms do not define a bond derivative.")
        row = np.zeros_like(coords)
        row[i], row[j] = diff / norm, -diff / norm
        rows.append(row.ravel())
    for i, j, k in constraints.angles:
        a, b = coords[i] - coords[j], coords[k] - coords[j]
        ra, rb = np.linalg.norm(a), np.linalg.norm(b)
        if min(ra, rb) < 1e-12:
            raise FrozenMonomerViolationError("Coincident atoms do not define an angle derivative.")
        u, v = a / ra, b / rb
        cosine = float(np.clip(u @ v, -1.0, 1.0))
        sine = float(np.linalg.norm(np.cross(u, v)))
        if sine < 1e-8:
            # Two orthonormal directions perpendicular to the linear bond axis.
            _, _, vh = np.linalg.svd(u.reshape(1, 3), full_matrices=True)
            for perpendicular in vh[1:]:
                row = np.zeros_like(coords)
                row[i] = perpendicular / ra
                row[k] = -math.copysign(1.0, cosine) * perpendicular / rb
                row[j] = -row[i] - row[k]
                rows.append(row.ravel())
        else:
            row = np.zeros_like(coords)
            row[i] = (cosine * u - v) / (ra * sine)
            row[k] = (cosine * v - u) / (rb * sine)
            row[j] = -row[i] - row[k]
            rows.append(row.ravel())

    def torsion(frame: np.ndarray, indices: Sequence[int]) -> float:
        i, j, k, l = indices
        axis = frame[k] - frame[j]
        length = np.linalg.norm(axis)
        if length < 1e-12:
            raise FrozenMonomerViolationError("Coincident torsion axis atoms.")
        axis /= length
        left, right = frame[i] - frame[j], frame[l] - frame[k]
        left -= (left @ axis) * axis
        right -= (right @ axis) * axis
        if min(np.linalg.norm(left), np.linalg.norm(right)) < 1e-10:
            raise FrozenMonomerViolationError("A collinear quartet does not define a torsion.")
        return math.atan2(float(np.cross(axis, left) @ right), float(left @ right))

    for indices in constraints.dihedrals:
        torsion(coords, indices)  # Validate the unperturbed coordinate.
        row = np.zeros_like(coords)
        for atom in indices:
            for axis in range(3):
                plus, minus = coords.copy(), coords.copy()
                plus[atom, axis] += difference_step
                minus[atom, axis] -= difference_step
                delta = torsion(plus, indices) - torsion(minus, indices)
                row[atom, axis] = math.atan2(math.sin(delta), math.cos(delta)) / (2 * difference_step)
        rows.append(row.ravel())
    return np.asarray(rows).reshape(-1, 3 * len(coords))


def get_reference_monomer_geometry(monomer: str) -> Tuple[List[str], np.ndarray]:
    """Retrieve isolated monomer geometries from NIST/CCCBDB (Task 5.3.1)."""
    m = monomer.upper().strip()
    if m == "CO2":
        # Dinfh, r_CO = 1.1621 A, angle = 180.0 deg
        symbols = ["C", "O", "O"]
        coords = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.1621],
            [0.0, 0.0, -1.1621],
        ], dtype=np.float64)
        return symbols, coords
    elif m in ("H2O", "WATER"):
        # C2v, r_OH = 0.9572 A, angle = 104.52 deg
        theta_rad = math.radians(104.52)
        half_theta = theta_rad / 2.0
        r_oh = 0.9572
        symbols = ["O", "H", "H"]
        coords = np.array([
            [0.0, 0.0, 0.0],
            [0.0, r_oh * math.sin(half_theta), r_oh * math.cos(half_theta)],
            [0.0, -r_oh * math.sin(half_theta), r_oh * math.cos(half_theta)],
        ], dtype=np.float64)
        return symbols, coords
    else:
        raise ValueError(f"Unknown monomer: {monomer}")


def build_reference_co2_h2o_complex(
    r_com: float = 2.8361,
) -> Tuple[List[str], np.ndarray, Tuple[int, int, int], Tuple[int, int, int]]:
    """Build reference CO2...H2O complex from NIST/CCCBDB monomers (Task 5.3.1)."""
    syms_co2, coords_co2 = get_reference_monomer_geometry("CO2")
    syms_h2o, coords_h2o = get_reference_monomer_geometry("H2O")
    shifted_h2o = coords_h2o + np.array([float(r_com), 0.0, 0.0])
    symbols = syms_co2 + syms_h2o
    coords = np.vstack([coords_co2, shifted_h2o])
    atoms_co2 = (0, 1, 2)
    atoms_h2o = (3, 4, 5)
    return symbols, coords, atoms_co2, atoms_h2o


def formulate_recipe_r2_wilson_constraints(
    atoms_co2: Sequence[int] = (0, 1, 2),
    atoms_h2o: Sequence[int] = (3, 4, 5),
    symbols: Optional[Sequence[str]] = None,
    coordinates: Optional[Union[Sequence[Sequence[float]], np.ndarray]] = None,
) -> ConstraintPayload:
    """Formulate Wilson internal coordinate constraints for CO2...H2O complex (Task 5.3.1).

    Locks 2 C-O bonds and 1 O-C-O angle in CO2, and 2 O-H bonds and 1 H-O-H angle in H2O.
    Ensures exactly 6 intramolecular constraints and zero intermolecular constraints.
    """
    c_idx, o1_idx, o2_idx = atoms_co2[0], atoms_co2[1], atoms_co2[2]
    o_w_idx, h1_idx, h2_idx = atoms_h2o[0], atoms_h2o[1], atoms_h2o[2]

    bonds = [
        (min(c_idx, o1_idx), max(c_idx, o1_idx)),
        (min(c_idx, o2_idx), max(c_idx, o2_idx)),
        (min(o_w_idx, h1_idx), max(o_w_idx, h1_idx)),
        (min(o_w_idx, h2_idx), max(o_w_idx, h2_idx)),
    ]
    angles = [
        (min(o1_idx, o2_idx), c_idx, max(o1_idx, o2_idx)),
        (min(h1_idx, h2_idx), o_w_idx, max(h1_idx, h2_idx)),
    ]

    return ConstraintPayload(
        bonds=sorted(bonds),
        angles=angles,
        dihedrals=[],
        metadata={
            "recipe": "R2",
            "provenance_tag": "[M]",
            "n_constraints": 6,
        },
    )


__all__ = [
    "ConstraintPayload",
    "FrozenConstraintPayload",
    "generate_frozen_monomer_constraints",
    "format_orca_frozen_monomer_constraints_block",
    "build_molecular_graph_from_geometry",
    "validate_trajectory_monomer_drift",
    "build_wilson_b_matrix",
    "get_reference_monomer_geometry",
    "build_reference_co2_h2o_complex",
    "formulate_recipe_r2_wilson_constraints",
]
