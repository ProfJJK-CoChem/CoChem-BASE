"""Topological and Spatial Symmetry Analysis Subsystem.

Provides Weisfeiler-Lehman (1-WL) color refinement, topological-to-spatial symmetry mapping,
Schoenflies point group classification, and rotational symmetry number (sigma_sym) evaluation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

from cochem.topos.exceptions import SymmetryPerceptionError
from cochem.topos.graph import TopologyGraph

logger = logging.getLogger("cochem.topos.symmetry")


class TopologicalSymmetryResult(BaseModel):
    """Pydantic v2 data model storing topological and spatial symmetry analysis results."""

    point_group: str = Field(description="Schoenflies point group symbol (e.g., C2v, D3h, Td, C1).")
    symmetry_number: int = Field(
        default=1,
        ge=1,
        description="Rotational symmetry number sigma.",
    )
    automorphism_partition: list[list[int]] = Field(
        default_factory=list,
        description="Equivalence vertex orbits derived from 1-WL partition.",
    )
    rotational_symmetry_number: int = Field(
        default=1,
        ge=1,
        description="Rotational symmetry number sigma_sym representing rigid rotational operations.",
    )
    orbits: dict[int, list[int]] = Field(
        default_factory=dict,
        description="Topological symmetry orbits / equivalence classes mapped to node indices.",
    )
    automorphism_order: int = Field(
        default=1,
        ge=1,
        description="Order of the automorphism group |Aut(G)| preserving atomic and bond invariants.",
    )
    is_chiral: bool = Field(
        default=False,
        description="True if the molecule lacks improper rotational symmetry (Sn, sigma, i).",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional diagnostic details regarding detected symmetry operations.",
    )

    @property
    def sigma_sym(self) -> int:
        """Alias for rotational_symmetry_number."""
        return self.rotational_symmetry_number


class TopologicalSymmetryAnalyzer:
    """Performs 1-WL color refinement, graph automorphism analysis, and point group perception."""

    @classmethod
    def analyze(
        cls,
        graph: TopologyGraph,
        coordinates: Optional[np.ndarray] = None,
    ) -> TopologicalSymmetryResult:
        """Analyzes topological symmetry with 1-WL refinement and maps to Schoenflies point group.

        Parameters
        ----------
        graph : TopologyGraph
            Chemical topology graph without embedded coordinates.
        coordinates : Optional[np.ndarray]
            Optional (N, 3) Cartesian coordinates array in Angstroms.

        Returns
        -------
        TopologicalSymmetryResult
            Result containing Schoenflies point group, sigma_sym, and 1-WL orbit partition.
        """
        if graph.number_of_nodes() == 0:
            raise SymmetryPerceptionError("Cannot perform symmetry analysis on an empty graph.")

        # 1. 1-WL Color Refinement
        orbits = cls._weisfeiler_lehman_refinement(graph)

        # 2. Graph Automorphism Group Order
        aut_order = cls._compute_automorphism_order(graph)

        # 3. Spatial vs Topological Point Group Assignment
        if coordinates is not None:
            point_group, sigma_sym, is_chiral, details = cls._perceive_spatial_point_group(
                graph, coordinates
            )
        else:
            point_group, sigma_sym, is_chiral, details = cls._perceive_topological_point_group(
                graph, orbits, aut_order
            )

        return TopologicalSymmetryResult(
            point_group=point_group,
            symmetry_number=sigma_sym,
            rotational_symmetry_number=sigma_sym,
            automorphism_partition=list(orbits.values()),
            orbits=orbits,
            automorphism_order=aut_order,
            is_chiral=is_chiral,
            details=details,
        )

    @classmethod
    def _weisfeiler_lehman_refinement(cls, graph: TopologyGraph) -> dict[int, list[int]]:
        """Executes 1-WL color refinement initialized with atomic invariants."""
        # Initial colors c_0(u) = (symbol, formal_charge, hybridization, degree)
        colors: dict[int, Any] = {}
        for u in graph.nodes():
            n_data = graph.nodes[u]
            colors[u] = (
                str(n_data.get("symbol", "")).upper(),
                int(n_data.get("formal_charge", 0)),
                str(n_data.get("hybridization", "sp3")),
                graph.degree(u),
            )

        # Map initial tuples to deterministic discrete integers
        unique_colors = sorted(set(colors.values()))
        color_to_id = {c: i for i, c in enumerate(unique_colors)}
        curr_colors = {u: color_to_id[c] for u, c in colors.items()}

        max_iter = max(len(graph), 20)
        num_classes = len(unique_colors)

        for _ in range(max_iter):
            next_colors: dict[int, Any] = {}
            for u in graph.nodes():
                nbr_multiset = sorted([
                    (
                        round(float(graph.edges[u, v].get("bond_order", 1.0)), 2),
                        bool(graph.edges[u, v].get("aromatic", False)),
                        curr_colors[v],
                    )
                    for v in graph.neighbors(u)
                ])
                next_colors[u] = (curr_colors[u], tuple(nbr_multiset))

            sorted_unique = sorted(set(next_colors.values()))
            new_color_to_id = {c: i for i, c in enumerate(sorted_unique)}
            curr_colors = {u: new_color_to_id[c] for u, c in next_colors.items()}

            new_num_classes = len(sorted_unique)
            if new_num_classes == num_classes:
                break
            num_classes = new_num_classes

        # Partition nodes into orbits
        class_to_nodes: dict[int, list[int]] = {}
        for u, cid in curr_colors.items():
            class_to_nodes.setdefault(cid, []).append(u)

        # Sort orbits canonically by minimum node index
        sorted_classes = sorted(class_to_nodes.values(), key=lambda nodes: min(nodes))
        orbits: dict[int, list[int]] = {i: sorted(nodes) for i, nodes in enumerate(sorted_classes)}
        return orbits

    @classmethod
    def _compute_automorphism_order(cls, graph: TopologyGraph) -> int:
        """Calculates the order of the chemical graph automorphism group |Aut(G)|."""
        def node_match(n1: dict[str, Any], n2: dict[str, Any]) -> bool:
            return (
                n1.get("atomic_number") == n2.get("atomic_number")
                and n1.get("formal_charge") == n2.get("formal_charge")
                and n1.get("hybridization") == n2.get("hybridization")
            )

        def edge_match(e1: dict[str, Any], e2: dict[str, Any]) -> bool:
            return (
                abs(float(e1.get("bond_order", 1.0)) - float(e2.get("bond_order", 1.0))) < 1e-3
                and bool(e1.get("aromatic", False)) == bool(e2.get("aromatic", False))
            )

        matcher = nx.isomorphism.GraphMatcher(
            graph, graph, node_match=node_match, edge_match=edge_match
        )
        return sum(1 for _ in matcher.isomorphisms_iter())

    @classmethod
    def _perceive_topological_point_group(
        cls,
        graph: TopologyGraph,
        orbits: dict[int, list[int]],
        aut_order: int,
    ) -> tuple[str, int, bool, dict[str, Any]]:
        """Assigns point group and rotational symmetry number strictly from topological invariants."""
        n_nodes = graph.number_of_nodes()

        # Diatomic molecules
        if n_nodes == 2 and graph.number_of_edges() == 1:
            u, v = list(graph.nodes())
            if graph.nodes[u]["symbol"] == graph.nodes[v]["symbol"]:
                return "D_inf_h", 2, False, {"type": "homonuclear_diatomic"}
            return "C_inf_v", 1, False, {"type": "heteronuclear_diatomic"}

        # Single central atom surrounded by ligands
        max_deg_node = max(graph.nodes(), key=lambda n: graph.degree(n))
        if graph.degree(max_deg_node) == n_nodes - 1 and n_nodes > 2:
            central_deg = graph.degree(max_deg_node)
            central_hyb = str(graph.nodes[max_deg_node].get("hybridization", "sp3"))
            ligands = [v for v in graph.neighbors(max_deg_node)]
            ligand_symbols = set(graph.nodes[v]["symbol"] for v in ligands)

            # Homoleptic ligands
            if len(ligand_symbols) == 1:
                if central_deg == 2:
                    if central_hyb in ("sp3", "sp2"):
                        return "C2v", 2, False, {"type": "bent_triatomic"}
                    if central_hyb == "sp":
                        return "D_inf_h", 2, False, {"type": "linear_triatomic"}
                elif central_deg == 3:
                    if central_hyb == "sp2":
                        return "D3h", 6, False, {"type": "trigonal_planar"}
                    if central_hyb == "sp3":
                        return "C3v", 3, False, {"type": "trigonal_pyramidal"}
                elif central_deg == 4:
                    if central_hyb == "sp3":
                        return "Td", 12, False, {"type": "tetrahedral"}
                    if central_hyb == "sp3d2":
                        return "D4h", 8, False, {"type": "square_planar"}
                elif central_deg == 5:
                    return "D3h", 6, False, {"type": "trigonal_bipyramidal"}
                elif central_deg == 6:
                    return "Oh", 24, False, {"type": "octahedral"}

        # Symmetric monocyclic ring systems (e.g. Benzene)
        if n_nodes == 6 or (n_nodes == 12 and all(graph.degree(n) in (2, 3) for n in graph.nodes())):
            c_nodes = [n for n in graph.nodes() if graph.nodes[n]["symbol"] == "C"]
            if len(c_nodes) == 6 and aut_order >= 12:
                return "D6h", 12, False, {"type": "aromatic_six_ring"}

        # General fallbacks
        if aut_order == 1:
            return "C1", 1, True, {"type": "asymmetric"}
        if aut_order == 2:
            return "C2", 2, False, {"type": "twofold_symmetric"}

        # Fallback to order-derived sigma_sym
        return "C1", max(1, aut_order), False, {"type": "topological_fallback"}

    @classmethod
    def _perceive_spatial_point_group(
        cls,
        graph: TopologyGraph,
        coordinates: np.ndarray,
    ) -> tuple[str, int, bool, dict[str, Any]]:
        """Assigns Schoenflies point group and rotational symmetry number from 3D coordinates."""
        n_nodes = graph.number_of_nodes()
        if coordinates.shape != (n_nodes, 3):
            raise SymmetryPerceptionError(
                f"Coordinates shape {coordinates.shape} does not match node count ({n_nodes}, 3)."
            )

        sorted_nodes = sorted(graph.nodes())
        masses = np.array([float(graph.nodes[n]["mass"]) for n in sorted_nodes])
        total_mass = np.sum(masses)
        if total_mass <= 0:
            masses = np.ones(n_nodes)
            total_mass = float(n_nodes)

        # Center of mass alignment
        com = np.sum(coordinates * masses[:, None], axis=0) / total_mass
        coords_centered = coordinates - com

        # Inertia tensor
        x, y, z = coords_centered[:, 0], coords_centered[:, 1], coords_centered[:, 2]
        I_xx = np.sum(masses * (y**2 + z**2))
        I_yy = np.sum(masses * (x**2 + z**2))
        I_zz = np.sum(masses * (x**2 + y**2))
        I_xy = -np.sum(masses * x * y)
        I_xz = -np.sum(masses * x * z)
        I_yz = -np.sum(masses * y * z)
        inertia_tensor = np.array([
            [I_xx, I_xy, I_xz],
            [I_xy, I_yy, I_yz],
            [I_xz, I_yz, I_zz],
        ])

        eigvals, eigvecs = np.linalg.eigh(inertia_tensor)
        # Sort principal axes
        idx = np.argsort(eigvals)
        principal_axes = eigvecs[:, idx]
        coords_aligned = coords_centered @ principal_axes

        # Helper to test if a symmetry matrix maps each atom to an identical atom
        symbols = [graph.nodes[n]["symbol"] for n in sorted_nodes]
        charges = [graph.nodes[n].get("formal_charge", 0) for n in sorted_nodes]

        def check_operation(R: np.ndarray, tol: float = 0.15) -> bool:
            transformed = (R @ coords_aligned.T).T
            for i in range(n_nodes):
                pos = transformed[i]
                dists = np.linalg.norm(coords_aligned - pos, axis=1)
                best_match = np.argmin(dists)
                if dists[best_match] > tol:
                    return False
                if symbols[i] != symbols[best_match] or charges[i] != charges[best_match]:
                    return False
            return True

        def rotation_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
            norm = np.linalg.norm(axis)
            if norm < 1e-8:
                return np.eye(3)
            u = axis / norm
            c = np.cos(angle)
            s = np.sin(angle)
            k = 1.0 - c
            ux, uy, uz = u
            return np.array([
                [c + ux*ux*k, ux*uy*k - uz*s, ux*uz*k + uy*s],
                [uy*ux*k + uz*s, c + uy*uy*k, uy*uz*k - ux*s],
                [uz*ux*k - uy*s, uz*uy*k + ux*s, c + uz*uz*k],
            ])

        # Test Inversion
        has_inversion = check_operation(-np.eye(3))

        # Test principal axes: x, y, z (columns of eye(3))
        axes_to_test = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
        ]
        # Add atom-atom vectors and face normals for high-symmetry molecules
        for i in range(min(n_nodes, 10)):
            norm_i = np.linalg.norm(coords_aligned[i])
            if norm_i > 0.1:
                axes_to_test.append(coords_aligned[i] / norm_i)

        # Detect C_n operations
        detected_rotations: list[tuple[int, np.ndarray]] = []
        for axis in axes_to_test:
            for n in (6, 5, 4, 3, 2):
                angle = 2.0 * np.pi / n
                R = rotation_matrix(axis, angle)
                if check_operation(R):
                    detected_rotations.append((n, axis))
                    break

        # Detect reflection planes
        detected_planes: list[np.ndarray] = []
        for normal in axes_to_test:
            # Reflection across plane with normal u: R = I - 2 * u * u^T
            u = normal / np.linalg.norm(normal)
            refl = np.eye(3) - 2.0 * np.outer(u, u)
            if check_operation(refl):
                detected_planes.append(u)

        # Classify Point Group
        max_n = max([n for n, _ in detected_rotations], default=1)
        c3_count = sum(1 for n, _ in detected_rotations if n == 3)

        # Tetrahedral / Octahedral check
        if c3_count >= 4:
            if has_inversion:
                return "Oh", 24, False, {"detected_rotations": len(detected_rotations)}
            return "Td", 12, False, {"detected_rotations": len(detected_rotations)}

        # Dihedral / Cyclic check
        if max_n == 3:
            # Check for horizontal mirror or perpendicular C2
            if len(detected_planes) >= 1:
                return "D3h", 6, False, {"planes": len(detected_planes)}
            return "C3v", 3, False, {"planes": len(detected_planes)}

        if max_n == 2:
            if len(detected_planes) >= 2:
                return "C2v", 2, False, {"planes": len(detected_planes)}
            if len(detected_planes) == 1:
                return "C2h", 2, False, {"planes": len(detected_planes)}
            return "C2", 2, False, {}

        if max_n == 6:
            return "D6h", 12, False, {}

        if len(detected_planes) == 1:
            return "Cs", 1, False, {}

        if has_inversion:
            return "Ci", 1, False, {}

        # Fallback to topological perception
        orbits = cls._weisfeiler_lehman_refinement(graph)
        aut_order = cls._compute_automorphism_order(graph)
        return cls._perceive_topological_point_group(graph, orbits, aut_order)
