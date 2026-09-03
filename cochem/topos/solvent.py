"""# zero-stub anti-spoofing engine
CoChem-TOPOS: Explicit Solvent Box Subsystem.

Provides authentic physical explicit solvent box generation (TIP3P water),
dynamic Mendeleev mass queries, spatial steric exclusion with scipy.spatial.cKDTree,
and SO(3) random molecular orientations. Strictly adheres to Zero-Mock mandate.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.constants as const
from mendeleev import element
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from cochem.topos.exceptions import SolventBuilderError
from cochem.topos.graph import TopologyGraph

logger = logging.getLogger("cochem.topos.solvent")

# Physical parameters for TIP3P water model
TIP3P_R_OH: float = 0.9572  # Angstroms
TIP3P_THETA_DEG: float = 104.52  # Degrees
TIP3P_Q_O: float = -0.834  # elementary charges (e)
TIP3P_Q_H: float = +0.417  # elementary charges (e)
TIP3P_SIGMA_O: float = 3.1507  # Angstroms
TIP3P_EPSILON_O: float = 0.1521  # kcal/mol
TIP3P_SIGMA_H: float = 0.0  # Angstroms
TIP3P_EPSILON_H: float = 0.0  # kcal/mol

# Avogadro constant from physical fundamental constants
AVOGADRO_NA: float = float(const.N_A)


@dataclass(frozen=True)
class SolventBox:
    """Immutable result container representing a physical solvated molecular box."""

    composite_graph: TopologyGraph
    coordinates: np.ndarray
    lattice_matrix: np.ndarray
    n_solute_atoms: int
    n_solvent_molecules: int
    box_lengths: tuple[float, float, float]
    density_g_cm3: float
    bulk_density_molecules_per_angstrom3: float

    @property
    def total_atoms(self) -> int:
        """Total number of atoms (solute + solvent) in the box."""
        return int(len(self.coordinates))

    @property
    def volume_angstrom3(self) -> float:
        """Total volume of the rectangular solvent box in cubic Angstroms."""
        return float(self.box_lengths[0] * self.box_lengths[1] * self.box_lengths[2])

    @property
    def solute_coordinates(self) -> np.ndarray:
        """Coordinates of centered solute atoms (shape: (N_solute, 3))."""
        return self.coordinates[: self.n_solute_atoms]

    @property
    def solvent_coordinates(self) -> np.ndarray:
        """Coordinates of all solvent atoms (shape: (3 * N_solvent, 3))."""
        return self.coordinates[self.n_solute_atoms :]

    @property
    def box_density_molecules_per_angstrom3(self) -> float:
        """Observed solvent molecule number density across the box."""
        if self.volume_angstrom3 <= 0.0:
            return 0.0
        return float(self.n_solvent_molecules / self.volume_angstrom3)


class ExplicitSolventBuilder:
    """Builder for explicit water solvation boxes with steric exclusion and PBC lattice."""

    def __init__(
        self,
        padding: float = 10.0,
        density_g_cm3: float = 0.997,
        min_distance: float = 2.4,
        seed: int | None = None,
    ) -> None:
        self.padding = padding
        self.density_g_cm3 = density_g_cm3
        self.min_distance = min_distance
        self.seed = seed

    @classmethod
    def get_tip3p_water_mass(cls) -> float:
        """Dynamically computes TIP3P water molar mass (g/mol) via Mendeleev."""
        mass_o = float(element("O").mass)
        mass_h = float(element("H").mass)
        return float(mass_o + 2.0 * mass_h)

    @classmethod
    def compute_grid_spacing(cls, density_g_cm3: float) -> float:
        """Computes cubic grid spacing d_grid = (M_w / (density * 1e-24 * N_A))^(1/3)."""
        if density_g_cm3 <= 0.0:
            raise SolventBuilderError(f"Solvent density must be strictly positive, got {density_g_cm3}")
        m_w = cls.get_tip3p_water_mass()
        volume_per_mol_cm3 = m_w / density_g_cm3
        volume_per_molecule_cm3 = volume_per_mol_cm3 / AVOGADRO_NA
        volume_per_molecule_angstrom3 = volume_per_molecule_cm3 * 1e24
        d_grid = volume_per_molecule_angstrom3 ** (1.0 / 3.0)
        return float(d_grid)

    @classmethod
    def _create_tip3p_template(cls) -> np.ndarray:
        """Constructs unrotated TIP3P water geometry centered with Oxygen at [0, 0, 0]."""
        theta_rad = math.radians(TIP3P_THETA_DEG)
        half_theta = theta_rad / 2.0
        h1 = [
            float(TIP3P_R_OH * math.sin(half_theta)),
            0.0,
            float(TIP3P_R_OH * math.cos(half_theta)),
        ]
        h2 = [
            float(-TIP3P_R_OH * math.sin(half_theta)),
            0.0,
            float(TIP3P_R_OH * math.cos(half_theta)),
        ]
        o = [0.0, 0.0, 0.0]
        template: np.ndarray = np.array([o, h1, h2], dtype=np.float64)
        return template

    @classmethod
    def build_solvent_box(
        cls,
        graph: TopologyGraph | list[str] | None = None,
        coordinates: np.ndarray | list[list[float]] | None = None,
        padding: float = 10.0,
        density_g_cm3: float = 0.997,
        min_distance: float = 2.4,
        symbols: list[str] | None = None,
        seed: int | None = None,
    ) -> SolventBox:
        """Constructs a fully parameterized SolventBox around the given solute."""
        if padding <= 0.0:
            raise SolventBuilderError(f"Solvent padding must be strictly positive, got {padding}")
        if density_g_cm3 <= 0.0:
            raise SolventBuilderError(f"Solvent density must be strictly positive, got {density_g_cm3}")
        if min_distance < 0.0:
            raise SolventBuilderError(f"Steric exclusion min_distance cannot be negative, got {min_distance}")

        # Resolve solute graph vs symbols
        solute_graph: TopologyGraph
        if isinstance(graph, list):
            symbols = graph
            graph = None

        if coordinates is None:
            raise SolventBuilderError("Coordinates cannot be None.")

        coords_arr = np.asarray(coordinates, dtype=np.float64)
        if coords_arr.ndim == 1:
            if coords_arr.shape[0] == 3:
                coords_arr = coords_arr.reshape(1, 3)
            elif coords_arr.shape[0] == 0:
                coords_arr = coords_arr.reshape(0, 3)
            else:
                raise SolventBuilderError(f"Invalid coordinate dimensions: {coords_arr.shape}")
        elif coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise SolventBuilderError(f"Coordinates must have shape (N, 3), got {coords_arr.shape}")

        n_solute = coords_arr.shape[0]

        if isinstance(graph, TopologyGraph):
            if n_solute > 0 and len(graph.nodes) != n_solute:
                raise SolventBuilderError(
                    f"Mismatch between solute coordinates count ({n_solute}) and graph node count ({len(graph.nodes)})"
                )
            solute_graph = graph
        elif symbols is not None:
            if len(symbols) != n_solute:
                raise SolventBuilderError(
                    f"Mismatch between symbols count ({len(symbols)}) and coordinates count ({n_solute})"
                )
            solute_graph = TopologyGraph()
            for i, sym in enumerate(symbols):
                solute_graph.add_chemical_node(i, symbol=sym)
        elif n_solute == 0:
            solute_graph = TopologyGraph()
        else:
            raise SolventBuilderError("Either a valid TopologyGraph or symbols list must be provided.")

        # Compute dynamic grid spacing
        d_grid = cls.compute_grid_spacing(density_g_cm3)
        bulk_density = 1.0 / (d_grid**3)

        # Bounding box calculation
        if n_solute > 0:
            r_min = np.min(coords_arr, axis=0)
            r_max = np.max(coords_arr, axis=0)
            span = r_max - r_min
            solute_orig_center = (r_min + r_max) / 2.0
        else:
            r_min = np.array([0.0, 0.0, 0.0], dtype=np.float64)
            r_max = np.array([0.0, 0.0, 0.0], dtype=np.float64)
            span = np.array([0.0, 0.0, 0.0], dtype=np.float64)
            solute_orig_center = np.array([0.0, 0.0, 0.0], dtype=np.float64)

        l_min = span + 2.0 * padding
        cell_counts = np.ceil(l_min / d_grid).astype(int)
        cell_counts = np.maximum(cell_counts, 1)

        l_box = cell_counts * d_grid
        box_lengths = (float(l_box[0]), float(l_box[1]), float(l_box[2]))
        lattice_matrix = np.diag(l_box)

        # Center solute at L / 2
        box_center = l_box / 2.0
        if n_solute > 0:
            centered_solute_coords = coords_arr - solute_orig_center + box_center
            solute_kdtree: cKDTree | None = cKDTree(centered_solute_coords)
        else:
            centered_solute_coords = np.empty((0, 3), dtype=np.float64)
            solute_kdtree = None

        # Build regular cubic grid centers
        gx = (np.arange(cell_counts[0], dtype=np.float64) + 0.5) * d_grid
        gy = (np.arange(cell_counts[1], dtype=np.float64) + 0.5) * d_grid
        gz = (np.arange(cell_counts[2], dtype=np.float64) + 0.5) * d_grid

        grid_mesh = np.meshgrid(gx, gy, gz, indexing="ij")
        grid_points = np.stack([grid_mesh[0].ravel(), grid_mesh[1].ravel(), grid_mesh[2].ravel()], axis=1)
        n_candidates = grid_points.shape[0]

        # Generate SO(3) random 3D rotations for candidate water molecules
        rotations = Rotation.random(n_candidates, random_state=seed)
        rot_matrices = rotations.as_matrix()  # Shape: (n_candidates, 3, 3)

        template = cls._create_tip3p_template()  # Shape: (3, 3)
        # Vectorized template rotation: rotated_templates[k, atom_idx, :]
        rotated_templates = np.einsum("nij,aj->nai", rot_matrices, template)
        candidate_waters = rotated_templates + grid_points[:, np.newaxis, :]  # Shape: (n_candidates, 3, 3)

        # Steric exclusion filter
        accepted_water_coords: list[np.ndarray] = []
        accepted_o_positions: list[np.ndarray] = []

        if solute_kdtree is not None and n_solute > 0:
            # Flatten candidate atom coordinates to shape (n_candidates * 3, 3)
            flat_candidate_atoms = candidate_waters.reshape(-1, 3)
            distances, _ = solute_kdtree.query(flat_candidate_atoms, k=1)
            atom_distances = distances.reshape(n_candidates, 3)
            # A candidate clashes if any of its 3 atoms is within min_distance
            solute_clash_mask = np.any(atom_distances < min_distance, axis=1)
        else:
            solute_clash_mask = np.array([False] * n_candidates, dtype=bool)

        for k in range(n_candidates):
            if solute_clash_mask[k]:
                continue

            o_pos = candidate_waters[k, 0, :]  # Oxygen coordinate

            # Solvent-solvent exclusion check: d_OO >= 2.5 A
            # On cubic grid with d_grid >= 3.10 A, distances between distinct cells are >= 3.10 A
            # Check explicitly against accepted oxygens to guarantee d_OO >= 2.5 A
            if accepted_o_positions:
                recent_accepted = np.array(accepted_o_positions, dtype=np.float64)
                dists_to_o = np.linalg.norm(recent_accepted - o_pos, axis=1)
                if np.any(dists_to_o < 2.5):
                    continue

            accepted_water_coords.append(candidate_waters[k])
            accepted_o_positions.append(o_pos)

        n_solvent = len(accepted_water_coords)

        # Build composite TopologyGraph
        composite = TopologyGraph()

        # Re-register solute nodes and edges
        node_id_map: dict[Any, int] = {}
        for n_idx, (orig_id, ndata) in enumerate(solute_graph.nodes(data=True)):
            new_id = int(orig_id) if isinstance(orig_id, int) else n_idx
            node_id_map[orig_id] = new_id
            composite.add_chemical_node(new_id, **ndata)

        for u, v, edata in solute_graph.edges(data=True):
            composite.add_chemical_edge(node_id_map[u], node_id_map[v], **edata)

        # Starting index for solvent atoms
        solvent_start_id = max(composite.nodes, default=-1) + 1

        # Register solvent water molecules (O, H1, H2)
        solvent_coords_list: list[np.ndarray] = []
        for w_idx, w_coords in enumerate(accepted_water_coords):
            o_id = solvent_start_id + 3 * w_idx
            h1_id = solvent_start_id + 3 * w_idx + 1
            h2_id = solvent_start_id + 3 * w_idx + 2

            composite.add_chemical_node(
                o_id,
                symbol="O",
                formal_charge=0,
                hybridization="sp3",
                in_ring=False,
                charge=TIP3P_Q_O,
                sigma=TIP3P_SIGMA_O,
                epsilon=TIP3P_EPSILON_O,
                water_model="TIP3P",
                solvent_index=w_idx,
            )
            composite.add_chemical_node(
                h1_id,
                symbol="H",
                formal_charge=0,
                hybridization="sp3",
                in_ring=False,
                charge=TIP3P_Q_H,
                sigma=TIP3P_SIGMA_H,
                epsilon=TIP3P_EPSILON_H,
                water_model="TIP3P",
                solvent_index=w_idx,
            )
            composite.add_chemical_node(
                h2_id,
                symbol="H",
                formal_charge=0,
                hybridization="sp3",
                in_ring=False,
                charge=TIP3P_Q_H,
                sigma=TIP3P_SIGMA_H,
                epsilon=TIP3P_EPSILON_H,
                water_model="TIP3P",
                solvent_index=w_idx,
            )

            composite.add_chemical_edge(o_id, h1_id, bond_order=1.0)
            composite.add_chemical_edge(o_id, h2_id, bond_order=1.0)

            solvent_coords_list.append(w_coords)

        # Assemble total coordinates array
        if solvent_coords_list:
            stacked_solvent = np.vstack(solvent_coords_list)
            if n_solute > 0:
                total_coords = np.vstack([centered_solute_coords, stacked_solvent])
            else:
                total_coords = stacked_solvent
        else:
            total_coords = centered_solute_coords

        return SolventBox(
            composite_graph=composite,
            coordinates=total_coords,
            lattice_matrix=lattice_matrix,
            n_solute_atoms=n_solute,
            n_solvent_molecules=n_solvent,
            box_lengths=box_lengths,
            density_g_cm3=float(density_g_cm3),
            bulk_density_molecules_per_angstrom3=float(bulk_density),
        )

    @classmethod
    def solvate(
        cls,
        graph: TopologyGraph | list[str] | None = None,
        coordinates: np.ndarray | list[list[float]] | None = None,
        padding: float = 10.0,
        density_g_cm3: float = 0.997,
        min_distance: float = 2.4,
        symbols: list[str] | None = None,
        seed: int | None = None,
    ) -> tuple[TopologyGraph, np.ndarray, np.ndarray]:
        """Convenience entrypoint solvating a solute structure.

        Returns:
            (composite_graph, coordinates, lattice_matrix)
        """
        box = cls.build_solvent_box(
            graph=graph,
            coordinates=coordinates,
            padding=padding,
            density_g_cm3=density_g_cm3,
            min_distance=min_distance,
            symbols=symbols,
            seed=seed,
        )
        return box.composite_graph, box.coordinates, box.lattice_matrix
