"""TOPOS Geometry Validation: Dynamic bond-length and bond-angle dictionary validation."""

from __future__ import annotations

import math
import warnings
from typing import Dict, List, Set, Tuple
import networkx as nx
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import GeometricPlausibilityError
from cochem.topos.models import GeometricViolation, GeometryValidationResult


def get_vdw_radius(symbol: str) -> float:
    """Dynamically fetches van der Waals radius in Angstroms via mendeleev."""
    el = element(symbol)
    rad = el.vdw_radius_alvarez or el.vdw_radius_bondi or el.vdw_radius
    return float(rad) / 100.0 if rad > 10.0 else float(rad)


def get_covalent_radius(symbol: str) -> float:
    """Dynamically fetches relativistic covalent radius in Angstroms via mendeleev."""
    el = element(symbol)
    cov = el.covalent_radius_pyykko or el.covalent_radius
    return float(cov) / 100.0 if cov > 10.0 else float(cov)


class DynamicBondDictionary:
    """Validates 3D molecular geometry against empirical valence parameter distributions and steric constraints."""

    def __init__(self) -> None:
        self._vdw_cache: Dict[str, float] = {}
        self._cov_cache: Dict[str, float] = {}

    def _get_vdw_radius(self, symbol: str) -> float:
        """Retrieves van der Waals radius dynamically in Angstroms with fallback hierarchy."""
        if symbol not in self._vdw_cache:
            self._vdw_cache[symbol] = get_vdw_radius(symbol)
        return self._vdw_cache[symbol]

    def _get_covalent_radius(self, symbol: str) -> float:
        """Retrieves relativistic covalent radius dynamically in Angstroms."""
        if symbol not in self._cov_cache:
            self._cov_cache[symbol] = get_covalent_radius(symbol)
        return self._cov_cache[symbol]

    def _get_reference_bond_length(
        self, elem_i: str, elem_j: str, bond_order: float, graph: nx.Graph, i: int, j: int
    ) -> Tuple[float, float]:
        """Returns empirical expected distance and standard deviation for a given bond."""
        pair = tuple(sorted([elem_i, elem_j]))
        bo = float(bond_order)

        if pair == ("C", "C"):
            if abs(bo - 1.5) < 1e-3:
                return 1.397, 0.035
            elif abs(bo - 2.0) < 1e-3:
                return 1.340, 0.035
            elif abs(bo - 3.0) < 1e-3:
                return 1.200, 0.030
            else:
                deg_i = graph.degree(i)
                deg_j = graph.degree(j)
                if deg_i == 3 and deg_j == 3:
                    return 1.480, 0.040
                elif (deg_i == 3 and deg_j >= 4) or (deg_j == 3 and deg_i >= 4):
                    return 1.505, 0.040
                else:
                    return 1.530, 0.040

        if pair == ("C", "O"):
            if abs(bo - 2.0) < 1e-3:
                return 1.215, 0.035
            else:
                deg_c = graph.degree(i if elem_i == "C" else j)
                if deg_c == 3:
                    return 1.360, 0.045
                else:
                    return 1.420, 0.045

        if pair == ("C", "N"):
            if abs(bo - 3.0) < 1e-3:
                return 1.160, 0.030
            elif abs(bo - 2.0) < 1e-3:
                return 1.280, 0.035
            elif abs(bo - 1.5) < 1e-3:
                return 1.340, 0.035
            else:
                return 1.460, 0.040

        r_sum = self._get_covalent_radius(elem_i) + self._get_covalent_radius(elem_j)
        if abs(bo - 1.5) < 1e-3:
            return r_sum - 0.10, 0.040
        elif abs(bo - 2.0) < 1e-3:
            return r_sum - 0.20, 0.035
        elif abs(bo - 3.0) < 1e-3:
            return r_sum - 0.32, 0.030
        else:
            return r_sum, 0.045

    def _get_reference_angle(
        self,
        elem_center: str,
        center_idx: int,
        graph: nx.Graph,
        cycle_basis: List[List[int]],
        measured_angle: float,
    ) -> Tuple[float, float]:
        """Returns empirical expected angle and standard deviation for atom center."""
        rings_with_center = [c for c in cycle_basis if center_idx in c]
        min_ring_size = min((len(c) for c in rings_with_center), default=0)

        if min_ring_size == 3:
            return 60.0, 3.5
        elif min_ring_size == 4:
            return 90.0, 4.0
        elif min_ring_size == 5:
            return 108.0, 4.5
        elif min_ring_size == 6:
            return 120.0, 4.5

        coord_num = graph.degree(center_idx)

        # Period 3+ hypervalency
        if elem_center in {"Si", "P", "S", "Cl", "Se", "Br", "I"}:
            if coord_num == 5:
                ref_angles = [90.0, 120.0, 180.0]
                best_ref = min(ref_angles, key=lambda a: abs(a - measured_angle))
                return best_ref, 5.0
            elif coord_num >= 6:
                ref_angles = [90.0, 180.0]
                best_ref = min(ref_angles, key=lambda a: abs(a - measured_angle))
                return best_ref, 5.0

        # Perceive hybridization from incident bond orders
        incident_bos = [graph[center_idx][nbr].get("bond_order", 1.0) for nbr in graph[center_idx]]
        has_aromatic = any(abs(bo - 1.5) < 1e-3 for bo in incident_bos)
        has_double = any(abs(bo - 2.0) < 1e-3 for bo in incident_bos)
        has_triple = any(abs(bo - 3.0) < 1e-3 for bo in incident_bos)
        num_double = sum(1 for bo in incident_bos if abs(bo - 2.0) < 1e-3)
        bo_sum = sum(incident_bos)

        if has_triple or num_double >= 2:
            return 180.0, 5.0

        if has_aromatic or has_double or bo_sum >= 2.5:
            return 120.0, 5.0

        if elem_center in {"O", "S"}:
            if coord_num == 2:
                return 110.0, 5.0

        if coord_num == 4:
            return 109.5, 4.5

        if coord_num == 3:
            if elem_center in {"N", "P"}:
                return 107.0, 4.5
            return 120.0, 5.0

        return 109.5, 5.0

    def validate_geometry(
        self,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        bonds: list[tuple[int, int, float]],
        raise_on_error: bool = True,
    ) -> GeometryValidationResult:
        """Validates 3D coordinates against authoritative empirical bond and angle distributions."""
        num_atoms = len(atoms)
        coords = np.array(coordinates, dtype=float)

        graph = nx.Graph()
        for idx in range(num_atoms):
            graph.add_node(idx, symbol=atoms[idx])
        for u_idx, v_idx, b_order in bonds:
            graph.add_edge(u_idx, v_idx, bond_order=float(b_order))

        cycle_basis = nx.cycle_basis(graph)
        violations: List[GeometricViolation] = []
        max_z = 0.0

        for u_idx, v_idx, b_order in bonds:
            dist = float(np.linalg.norm(coords[u_idx] - coords[v_idx]))
            ref_d, sigma_d = self._get_reference_bond_length(
                atoms[u_idx], atoms[v_idx], b_order, graph, u_idx, v_idx
            )
            z = abs(dist - ref_d) / sigma_d
            if z > max_z:
                max_z = z
            if z >= 3.0:
                violations.append(
                    GeometricViolation(
                        violation_type="bond_length",
                        atom_indices=[u_idx, v_idx],
                        measured_value=dist,
                        reference_value=ref_d,
                        z_score=z,
                    )
                )
                if z < 5.0:
                    warnings.warn(
                        f"Non-fatal bond length deviation: ({u_idx}, {v_idx}) d={dist:.3f}A, ref={ref_d:.3f}A, z={z:.2f}",
                        UserWarning,
                        stacklevel=2,
                    )

        for center_idx in graph.nodes():
            neighbors = sorted(graph.neighbors(center_idx))
            num_nbrs = len(neighbors)
            for idx_a in range(num_nbrs):
                for idx_b in range(idx_a + 1, num_nbrs):
                    i_at = neighbors[idx_a]
                    k_at = neighbors[idx_b]
                    vec_1 = coords[i_at] - coords[center_idx]
                    vec_2 = coords[k_at] - coords[center_idx]
                    norm_1 = float(np.linalg.norm(vec_1))
                    norm_2 = float(np.linalg.norm(vec_2))
                    if norm_1 < 1e-12 or norm_2 < 1e-12:
                        continue
                    cos_val = float(np.dot(vec_1, vec_2) / (norm_1 * norm_2))
                    meas_ang = float(math.degrees(math.acos(np.clip(cos_val, -1.0, 1.0))))

                    ref_ang, sigma_ang = self._get_reference_angle(
                        atoms[center_idx], center_idx, graph, cycle_basis, meas_ang
                    )
                    z_ang = abs(meas_ang - ref_ang) / sigma_ang
                    if z_ang > max_z:
                        max_z = z_ang
                    if z_ang >= 3.0:
                        violations.append(
                            GeometricViolation(
                                violation_type="bond_angle",
                                atom_indices=[i_at, center_idx, k_at],
                                measured_value=meas_ang,
                                reference_value=ref_ang,
                                z_score=z_ang,
                            )
                        )
                        if z_ang < 5.0:
                            warnings.warn(
                                f"Non-fatal angle deviation: ({i_at}-{center_idx}-{k_at}) "
                                f"theta={meas_ang:.1f}deg, ref={ref_ang:.1f}deg, z={z_ang:.2f}",
                                UserWarning,
                                stacklevel=2,
                            )

        steric_clashes = self.validate_steric_contacts(atoms, coords, graph=graph)
        for clash in steric_clashes:
            if clash.z_score > max_z:
                max_z = clash.z_score
            violations.append(clash)

        is_plausible = (max_z < 5.0) and (len(steric_clashes) == 0)

        if (max_z >= 5.0 or len(steric_clashes) > 0) and raise_on_error:
            raise GeometricPlausibilityError(
                f"Critical geometric strain or clash: max z-score {max_z:.2f} >= 5.0 or {len(steric_clashes)} steric clash(es) detected."
            )

        return GeometryValidationResult(
            is_physically_plausible=is_plausible,
            max_z_score=max_z,
            violations=violations,
        )

    @classmethod
    def _is_polar_hydrogen(
        cls, idx: int, atoms: List[str], coords: np.ndarray, graph: Optional[nx.Graph] = None
    ) -> bool:
        """Determines if atom is a hydrogen covalently bonded (d <= 1.20 * (r_cov(H) + r_cov(donor))) to a donor (O, N, F, Cl)."""
        if atoms[idx] != "H":
            return False
        donors = {"O", "N", "F", "Cl"}
        if graph is not None and idx in graph:
            for nbr in graph.neighbors(idx):
                if atoms[nbr] in donors:
                    return True
        r_h = get_covalent_radius("H")
        for k, sym in enumerate(atoms):
            if k != idx and sym in donors:
                r_don = get_covalent_radius(sym)
                cov_max = 1.20 * (r_h + r_don)
                d = float(np.linalg.norm(coords[idx] - coords[k]))
                if d <= cov_max:
                    return True
        return False

    @staticmethod
    def _is_electronegative_acceptor(idx: int, atoms: List[str]) -> bool:
        """Determines if atom is an electronegative hydrogen bond acceptor (O, N, F, Cl)."""
        return atoms[idx] in {"O", "N", "F", "Cl"}

    @staticmethod
    def _is_halogen_bond_pair(i: int, j: int, atoms: List[str]) -> bool:
        """Determines if pair represents a halogen-bonding pair (Lewis-acidic Cl, Br, I with Lewis-basic O, N, S)."""
        sym_i = atoms[i]
        sym_j = atoms[j]
        halogens = {"Cl", "Br", "I"}
        lewis_bases = {"O", "N", "S"}
        return (sym_i in halogens and sym_j in lewis_bases) or (sym_j in halogens and sym_i in lewis_bases)

    def validate_steric_contacts(
        self,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        bonds: Optional[list[tuple[int, int, float]]] = None,
        graph: Optional[nx.Graph] = None,
    ) -> list[GeometricViolation]:
        """Validates non-bonded pairs against dynamic vdW steric thresholds with polar HB & halogen bond exemptions [M]."""
        num_atoms = len(atoms)
        coords = np.array(coordinates, dtype=float)

        if graph is None:
            graph = nx.Graph()
            for idx in range(num_atoms):
                graph.add_node(idx, symbol=atoms[idx])
            if bonds:
                for u_idx, v_idx, b_order in bonds:
                    graph.add_edge(u_idx, v_idx, bond_order=float(b_order))

        shortest_paths = dict(nx.all_pairs_shortest_path_length(graph))
        violations: list[GeometricViolation] = []

        for i_idx in range(num_atoms):
            for j_idx in range(i_idx + 1, num_atoms):
                path_len = shortest_paths.get(i_idx, {}).get(j_idx, 999)
                if path_len >= 3:
                    d_ij = float(np.linalg.norm(coords[i_idx] - coords[j_idx]))
                    vdw_sum = self._get_vdw_radius(atoms[i_idx]) + self._get_vdw_radius(atoms[j_idx])

                    # Inspect polar hydrogen bond / halogen bond donor-acceptor exemption [M]
                    is_hb_contact = (
                        (self._is_polar_hydrogen(i_idx, atoms, coords, graph) and self._is_electronegative_acceptor(j_idx, atoms))
                        or (self._is_polar_hydrogen(j_idx, atoms, coords, graph) and self._is_electronegative_acceptor(i_idx, atoms))
                    )
                    is_xb_contact = self._is_halogen_bond_pair(i_idx, j_idx, atoms)
                    is_relaxed = is_hb_contact or is_xb_contact

                    threshold = (0.50 * vdw_sum) if is_relaxed else (0.65 * vdw_sum)

                    if d_ij < threshold:
                        clash_z = max(5.0, abs(d_ij - threshold) / 0.05)
                        violations.append(
                            GeometricViolation(
                                violation_type="steric_clash",
                                atom_indices=[i_idx, j_idx],
                                measured_value=d_ij,
                                reference_value=threshold,
                                z_score=clash_z,
                            )
                        )
        return violations


GeometryValidator = DynamicBondDictionary
