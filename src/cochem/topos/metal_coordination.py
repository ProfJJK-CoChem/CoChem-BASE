"""TOPOS Metal Coordination Perception Engine: Continuous Shape Measure and CBC perception."""

from __future__ import annotations

import itertools
import math
from typing import Dict, List, Set, Tuple
import networkx as nx
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import CoordinationPerceptionError
from cochem.topos.models import (
    CoordinationCenter,
    CoordinationPerceptionResult,
    PolyhedronScore,
)


class MetalCoordinationEngine:
    """Perceives coordination spheres, continuous shape measures (CShM), and CBC formal oxidation states."""

    def __init__(self) -> None:
        self._cov_cache: Dict[str, float] = {}
        self._reference_polyhedra: Dict[int, Dict[str, np.ndarray]] = self._build_reference_polyhedra()

    def _get_covalent_radius(self, symbol: str) -> float:
        """Retrieves dynamic covalent radius in Angstroms via Mendeleev."""
        if symbol not in self._cov_cache:
            elem_obj = element(symbol)
            pm = elem_obj.covalent_radius_pyykko or elem_obj.covalent_radius
            self._cov_cache[symbol] = float(pm / 100.0)
        return self._cov_cache[symbol]

    def _is_metal(self, symbol: str) -> bool:
        """Identifies metal elements via dynamic series and group membership."""
        elem_obj = element(symbol)
        series_str = getattr(elem_obj, "series", "").lower()
        if (
            "nonmetal" in series_str
            or "alkali" in series_str
            or "halogen" in series_str
            or "noble gas" in series_str
        ):
            return False
        return "metal" in series_str or getattr(elem_obj, "group_id", 0) in range(3, 13)

    def _build_reference_polyhedra(self) -> Dict[int, Dict[str, np.ndarray]]:
        """Constructs canonical reference polyhedra for coordination numbers 4, 5, and 6."""
        refs: Dict[int, Dict[str, np.ndarray]] = {}

        # CN = 4
        sp_pts = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
        ])
        td_pts = np.array([
            [1.0, 1.0, 1.0],
            [1.0, -1.0, -1.0],
            [-1.0, 1.0, -1.0],
            [-1.0, -1.0, 1.0],
        ]) / math.sqrt(3.0)

        refs[4] = {
            "Square_Planar": sp_pts,
            "Tetrahedral": td_pts,
        }

        # CN = 5
        tbp_pts = np.array([
            [1.0, 0.0, 0.0],
            [-0.5, math.sqrt(3) / 2.0, 0.0],
            [-0.5, -math.sqrt(3) / 2.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ])
        spy_pts = np.array([
            [1.0, 0.0, -0.3535],
            [0.0, 1.0, -0.3535],
            [-1.0, 0.0, -0.3535],
            [0.0, -1.0, -0.3535],
            [0.0, 0.0, 0.7071],
        ])

        refs[5] = {
            "Trigonal_Bipyramidal": tbp_pts,
            "Square_Pyramidal": spy_pts,
        }

        # CN = 6
        oct_pts = np.array([
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ])
        tpr_pts = np.array([
            [1.0, 0.0, 0.5],
            [-0.5, math.sqrt(3) / 2.0, 0.5],
            [-0.5, -math.sqrt(3) / 2.0, 0.5],
            [1.0, 0.0, -0.5],
            [-0.5, math.sqrt(3) / 2.0, -0.5],
            [-0.5, -math.sqrt(3) / 2.0, -0.5],
        ])

        refs[6] = {
            "Octahedral": oct_pts,
            "Trigonal_Prismatic": tpr_pts,
        }

        return refs

    def _compute_cshm(self, q_coords: np.ndarray, p_coords: np.ndarray) -> float:
        """Computes Alvarez Continuous Shape Measure (CShM) minimized over symmetric permutations."""
        n_pts = len(q_coords)
        q_centered = q_coords - np.mean(q_coords, axis=0)
        p_centered = p_coords - np.mean(p_coords, axis=0)

        denom_q = float(np.sum(q_centered ** 2))
        denom_p = float(np.sum(p_centered ** 2))
        if denom_q < 1e-12 or denom_p < 1e-12:
            return 0.0

        min_s = float("inf")

        for perm in itertools.permutations(range(n_pts)):
            p_perm = p_centered[list(perm)]
            h_mat = np.dot(p_perm.T, q_centered)
            u_mat, s_vals, vt_mat = np.linalg.svd(h_mat)
            det_val = float(np.linalg.det(np.dot(vt_mat.T, u_mat.T)))
            tr_val = float(s_vals[0] + s_vals[1] + det_val * s_vals[2])
            if tr_val < 0.0:
                continue

            sq_ratio = (tr_val ** 2) / (denom_q * denom_p)
            val = max(0.0, (1.0 - sq_ratio) * 100.0)
            if val < min_s:
                min_s = val

        return float(min_s)

    def _classify_ligand_charge(self, symbol: str, is_haptic: bool = False) -> int:
        """Assigns formal CBC ligand charge contributions."""
        if is_haptic:
            return -1
        elem_obj = element(symbol)
        series_str = getattr(elem_obj, "series", "").lower()

        if symbol in {"F", "Cl", "Br", "I"} or "halogen" in series_str:
            return -1
        if symbol in {"O", "S", "Se"}:
            return 0
        if symbol in {"N", "P", "As"}:
            return 0
        if symbol == "C":
            return -1
        return 0

    def perceive_coordination(
        self,
        atoms: list[str],
        coordinates: list[list[float]] | np.ndarray,
        net_charge: int = 0,
    ) -> CoordinationPerceptionResult:
        """Perceives coordination spheres, shapes, and formal oxidation states across all metal centers."""
        num_atoms = len(atoms)
        coords = np.array(coordinates, dtype=float)

        metal_indices = [idx for idx in range(num_atoms) if self._is_metal(atoms[idx])]
        total_metals = len(metal_indices)
        if total_metals == 0:
            return CoordinationPerceptionResult(
                coordination_centers=[],
                unassigned_metal_indices=[],
                total_metals_detected=0,
            )

        centers: List[CoordinationCenter] = []
        unassigned_metals: List[int] = []

        for m_idx in metal_indices:
            m_sym = atoms[m_idx]
            m_cov = self._get_covalent_radius(m_sym)
            m_pos = coords[m_idx]

            donor_indices: List[int] = []
            for other_idx in range(num_atoms):
                if other_idx == m_idx:
                    continue
                d = float(np.linalg.norm(m_pos - coords[other_idx]))
                l_cov = self._get_covalent_radius(atoms[other_idx])
                cutoff = m_cov + l_cov + 0.55
                if d <= cutoff:
                    donor_indices.append(other_idx)

            cn = len(donor_indices)
            if cn == 0:
                unassigned_metals.append(m_idx)
                continue

            # Perceive hapticity by building ligand connectivity among donors
            ligand_graph = nx.Graph()
            for d_idx in donor_indices:
                ligand_graph.add_node(d_idx, symbol=atoms[d_idx])

            for i_d in range(cn):
                for j_d in range(i_d + 1, cn):
                    idx1 = donor_indices[i_d]
                    idx2 = donor_indices[j_d]
                    d_between = float(np.linalg.norm(coords[idx1] - coords[idx2]))
                    cov1 = self._get_covalent_radius(atoms[idx1])
                    cov2 = self._get_covalent_radius(atoms[idx2])
                    if d_between <= cov1 + cov2 + 0.45:
                        ligand_graph.add_edge(idx1, idx2)

            hapticities: Dict[str, int] = {}
            haptic_atom_set: Set[int] = set()
            haptic_group_counter = 0

            components = list(nx.connected_components(ligand_graph))
            for comp in components:
                if len(comp) >= 3:
                    haptic_group_counter += 1
                    key_name = f"haptic_group_{haptic_group_counter}"
                    hapticities[key_name] = len(comp)
                    haptic_atom_set.update(comp)

            # Check chelate formation
            is_chelated = False
            for comp in components:
                if len(comp) >= 2 and len(comp) not in {5, 6}:
                    is_chelated = True

            polyhedron_scores: List[PolyhedronScore] = []
            assigned_geom = "Unassigned"

            if cn in {4, 5, 6} and not hapticities:
                ref_dict = self._reference_polyhedra.get(cn, {})
                q_coords = coords[donor_indices]
                for poly_name, poly_pts in ref_dict.items():
                    score_val = self._compute_cshm(q_coords, poly_pts)
                    polyhedron_scores.append(
                        PolyhedronScore(polyhedron_name=poly_name, cshm_value=score_val)
                    )

                best_poly = min(polyhedron_scores, key=lambda p: p.cshm_value)
                if best_poly.cshm_value <= 15.0:
                    assigned_geom = best_poly.polyhedron_name
                else:
                    assigned_geom = "Distorted/Unassigned"
            else:
                if hapticities:
                    assigned_geom = "Special_Haptic"
                else:
                    assigned_geom = f"Unassigned_CN{cn}"

            # CBC oxidation state calculation
            q_local = float(net_charge) / float(total_metals)
            ligand_charge_sum = 0
            if hapticities:
                for comp in components:
                    if len(comp) >= 3:
                        ligand_charge_sum += -1
                    else:
                        for atom_i in comp:
                            ligand_charge_sum += self._classify_ligand_charge(atoms[atom_i])
            else:
                for d_idx in donor_indices:
                    ligand_charge_sum += self._classify_ligand_charge(atoms[d_idx])

            formal_ox_state = int(round(q_local - ligand_charge_sum))

            centers.append(
                CoordinationCenter(
                    metal_idx=m_idx,
                    metal_element=m_sym,
                    coordination_number=cn,
                    assigned_geometry=assigned_geom,
                    formal_oxidation_state=formal_ox_state,
                    ligand_atom_indices=donor_indices,
                    is_chelated=is_chelated,
                    hapticities=hapticities,
                    polyhedron_scores=polyhedron_scores,
                )
            )

        return CoordinationPerceptionResult(
            coordination_centers=centers,
            unassigned_metal_indices=unassigned_metals,
            total_metals_detected=total_metals,
        )
