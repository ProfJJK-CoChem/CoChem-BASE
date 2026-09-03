"""Bond-order and formal charge perception engine from bare 3D Cartesian coordinates.

Uses dynamic Mendeleev covalent radii, Pauling empirical geometric bond order formulation,
and SciPy Mixed-Integer Linear Programming (MILP) with the HiGHS solver backend.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple, Union
import numpy as np
from mendeleev import element
from scipy.optimize import Bounds, LinearConstraint, milp

from cochem.topos.exceptions import BondPerceptionError
from cochem.topos.models import BondOrderEdge, BondPerceptionResult


def perceive_bond_orders_from_xyz(
    elements: Sequence[str],
    coordinates: Union[Sequence[Tuple[float, float, float]], np.ndarray],
    net_charge: int = 0,
) -> BondPerceptionResult:
    """Perceives formal bond orders, lone pairs, and atomic formal charges from bare XYZ coordinates.

    Parameters
    ----------
    elements : Sequence[str]
        Elemental symbols (e.g., ["O", "H", "H"]).
    coordinates : Sequence[Tuple[float, float, float]] or np.ndarray
        3D Cartesian coordinates in Angstroms, shape (N, 3).
    net_charge : int, default=0
        Total net molecular charge.

    Returns
    -------
    BondPerceptionResult
        Perceived bond orders, atomic formal charges, lone pairs, and conserved total charge.

    Raises
    ------
    BondPerceptionError
        If coordinates are inconsistent, covalent radii cannot be resolved, or ILP optimization fails.
    """
    coords_arr = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(elements)
    if coords_arr.shape != (n_atoms, 3):
        raise BondPerceptionError(
            f"Coordinate shape {coords_arr.shape} does not match atom count ({n_atoms}, 3)."
        )

    if n_atoms == 0:
        return BondPerceptionResult(
            bond_orders=[],
            formal_charges=[],
            lone_pairs=[],
            total_charge=net_charge,
        )

    # 1. Dynamic Mendeleev calibration
    covalent_radii: List[float] = []
    valence_electrons: List[int] = []
    for sym in elements:
        try:
            elem_obj = element(sym)
            cov_pm = elem_obj.covalent_radius_pyykko
            if cov_pm is None:
                raise ValueError(f"No Pyykko covalent radius for element '{sym}'")
            # Convert picometers (pm) to Angstroms (A)
            covalent_radii.append(float(cov_pm) / 100.0)
            valence_electrons.append(int(elem_obj.nvalence()))
        except Exception as exc:
            raise BondPerceptionError(
                f"Dynamic Mendeleev resolution failed for element symbol '{sym}': {exc}"
            ) from exc

    # 2. Candidate connectivity graph and Pauling geometric bond orders
    edges: List[Tuple[int, int]] = []
    geometric_bos: List[float] = []
    pauling_b = 0.37  # Angstroms

    for i in range(n_atoms):
        for j in range(i + 1, n_atoms):
            dist = float(np.linalg.norm(coords_arr[i] - coords_arr[j]))
            r0 = covalent_radii[i] + covalent_radii[j]
            # Spatial distance threshold: D_ij <= R_cov(i) + R_cov(j) + 0.40 A
            if dist <= r0 + 0.40:
                edges.append((i, j))
                # Pauling's geometric BO formula
                geom_bo = float(np.exp((r0 - dist) / pauling_b))
                geometric_bos.append(geom_bo)

    n_edges = len(edges)

    # Variables layout for MILP:
    # 0 .. n_edges-1                     : BO_e (int, [0, 3])
    # n_edges .. n_edges+n_atoms-1       : n_lp_i (int, [0, 4])
    # n_edges+n_atoms .. n_edges+2*n_atoms-1: q_i (int, [-2, 2])
    # n_edges+2*n_atoms .. n_edges+3*n_atoms-1: u_i (cont, >= |q_i|)
    # n_edges+3*n_atoms .. n_edges+3*n_atoms+n_edges-1: v_e (cont, >= |BO_e - geom_bo_e|)
    num_vars = 2 * n_edges + 3 * n_atoms
    c_obj = [0.0] * num_vars

    weight_q = 2.0
    weight_bo = 1.0

    for i in range(n_atoms):
        c_obj[n_edges + 2 * n_atoms + i] = weight_q
    for e in range(n_edges):
        c_obj[n_edges + 3 * n_atoms + e] = weight_bo

    integrality = [0] * num_vars
    # BO_e are integers
    for e in range(n_edges):
        integrality[e] = 1
    # n_lp_i are integers
    for i in range(n_atoms):
        integrality[n_edges + i] = 1
    # q_i are integers
    for i in range(n_atoms):
        integrality[n_edges + n_atoms + i] = 1

    lower_bounds = [0.0] * num_vars
    upper_bounds = [0.0] * num_vars

    # BO bounds [0, 3]
    for e in range(n_edges):
        lower_bounds[e] = 0.0
        upper_bounds[e] = 3.0

    # Lone pairs bounds: [0, 4] for heavy atoms, [0, 0] for Hydrogen
    for i in range(n_atoms):
        lower_bounds[n_edges + i] = 0.0
        upper_bounds[n_edges + i] = 0.0 if elements[i] == "H" else 4.0

    # Formal charge bounds [-2, 2]
    for i in range(n_atoms):
        lower_bounds[n_edges + n_atoms + i] = -2.0
        upper_bounds[n_edges + n_atoms + i] = 2.0

    # Auxiliary variables bounds
    for i in range(n_atoms):
        lower_bounds[n_edges + 2 * n_atoms + i] = 0.0
        upper_bounds[n_edges + 2 * n_atoms + i] = 4.0

    for e in range(n_edges):
        lower_bounds[n_edges + 3 * n_atoms + e] = 0.0
        upper_bounds[n_edges + 3 * n_atoms + e] = 10.0

    constraints_matrix: List[List[float]] = []
    lhs_bounds: List[float] = []
    rhs_bounds: List[float] = []

    # 1. Formal charge coupling equality:
    # q_i + 2 * n_lp_i + sum_{j in adj(i)} BO_ij = N_valence(i)
    for i in range(n_atoms):
        row = [0.0] * num_vars
        row[n_edges + n_atoms + i] = 1.0  # q_i
        row[n_edges + i] = 2.0  # 2 * n_lp_i
        for e_idx, (u, v) in enumerate(edges):
            if u == i or v == i:
                row[e_idx] = 1.0
        constraints_matrix.append(row)
        lhs_bounds.append(float(valence_electrons[i]))
        rhs_bounds.append(float(valence_electrons[i]))

    # 2. Total charge conservation: sum_{i=1}^N q_i = net_charge
    row_charge = [0.0] * num_vars
    for i in range(n_atoms):
        row_charge[n_edges + n_atoms + i] = 1.0
    constraints_matrix.append(row_charge)
    lhs_bounds.append(float(net_charge))
    rhs_bounds.append(float(net_charge))

    # 3. Period 2 Valence Shell (Octet Rule): For C, N, O, F:
    # 2 * n_lp_i + 2 * sum_{j in adj(i)} BO_ij <= 8
    period_2 = {"C", "N", "O", "F"}
    for i, sym in enumerate(elements):
        if sym in period_2:
            row_oct = [0.0] * num_vars
            row_oct[n_edges + i] = 2.0
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_oct[e_idx] = 2.0
            constraints_matrix.append(row_oct)
            lhs_bounds.append(0.0)
            rhs_bounds.append(8.0)

    # 4. Period 3+ Hypervalency Limits: For Si, P, S, Cl, Se, Br, I:
    # 2 * n_lp_i + 2 * sum_{j in adj(i)} BO_ij <= 12
    hypervalent_period3_plus = {"Si", "P", "S", "Cl", "Se", "Br", "I"}
    for i, sym in enumerate(elements):
        if sym in hypervalent_period3_plus:
            row_hyp = [0.0] * num_vars
            row_hyp[n_edges + i] = 2.0
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_hyp[e_idx] = 2.0
            constraints_matrix.append(row_hyp)
            lhs_bounds.append(0.0)
            rhs_bounds.append(12.0)

    # 5. Hydrogen Duet Rule: For all H atoms:
    # sum_{j in adj(H)} BO_Hj = 1 and n_lp_H = 0
    for i, sym in enumerate(elements):
        if sym == "H":
            row_h = [0.0] * num_vars
            for e_idx, (u, v) in enumerate(edges):
                if u == i or v == i:
                    row_h[e_idx] = 1.0
            constraints_matrix.append(row_h)
            lhs_bounds.append(1.0)
            rhs_bounds.append(1.0)

    # 6. Auxiliary variable constraints for |q_i|:
    # u_i - q_i >= 0 and u_i + q_i >= 0
    for i in range(n_atoms):
        row_u1 = [0.0] * num_vars
        row_u1[n_edges + 2 * n_atoms + i] = 1.0
        row_u1[n_edges + n_atoms + i] = -1.0
        constraints_matrix.append(row_u1)
        lhs_bounds.append(0.0)
        rhs_bounds.append(float(np.inf))

        row_u2 = [0.0] * num_vars
        row_u2[n_edges + 2 * n_atoms + i] = 1.0
        row_u2[n_edges + n_atoms + i] = 1.0
        constraints_matrix.append(row_u2)
        lhs_bounds.append(0.0)
        rhs_bounds.append(float(np.inf))

    # 7. Auxiliary variable constraints for |BO_e - geom_bo_e|:
    # v_e - BO_e >= -geom_bo_e and v_e + BO_e >= geom_bo_e
    for e_idx in range(n_edges):
        geom_val = geometric_bos[e_idx]
        row_v1 = [0.0] * num_vars
        row_v1[n_edges + 3 * n_atoms + e_idx] = 1.0
        row_v1[e_idx] = -1.0
        constraints_matrix.append(row_v1)
        lhs_bounds.append(-geom_val)
        rhs_bounds.append(float(np.inf))

        row_v2 = [0.0] * num_vars
        row_v2[n_edges + 3 * n_atoms + e_idx] = 1.0
        row_v2[e_idx] = 1.0
        constraints_matrix.append(row_v2)
        lhs_bounds.append(geom_val)
        rhs_bounds.append(float(np.inf))

    a_matrix = np.array(constraints_matrix, dtype=np.float64)
    lin_constraints = LinearConstraint(a_matrix, lhs_bounds, rhs_bounds)
    var_bounds = Bounds(lower_bounds, upper_bounds)

    result = milp(
        c=c_obj,
        integrality=integrality,
        bounds=var_bounds,
        constraints=lin_constraints,
    )

    if not result.success or result.x is None:
        raise BondPerceptionError(
            f"ILP HiGHS bond perception solver failed to converge: {result.status} ({result.message})"
        )

    solution = result.x
    bo_values = solution[0:n_edges]
    lp_values = solution[n_edges : n_edges + n_atoms]
    q_values = solution[n_edges + n_atoms : n_edges + 2 * n_atoms]

    # Assemble perceived bond edges (only edges where perceived bond order > 0)
    perceived_edges: List[BondOrderEdge] = []
    for e_idx, (u, v) in enumerate(edges):
        bo_val = float(round(bo_values[e_idx]))
        if bo_val > 0.0:
            perceived_edges.append(
                BondOrderEdge(
                    atom_i=min(u, v),
                    atom_j=max(u, v),
                    bond_order=bo_val,
                )
            )

    # Sort bonds canonically by (atom_i, atom_j)
    perceived_edges.sort(key=lambda edge: (edge.atom_i, edge.atom_j))

    formal_charges_int = [int(round(q_values[i])) for i in range(n_atoms)]
    lone_pairs_int = [int(round(lp_values[i])) for i in range(n_atoms)]
    computed_total_charge = sum(formal_charges_int)

    return BondPerceptionResult(
        bond_orders=perceived_edges,
        formal_charges=formal_charges_int,
        lone_pairs=lone_pairs_int,
        total_charge=computed_total_charge,
    )
