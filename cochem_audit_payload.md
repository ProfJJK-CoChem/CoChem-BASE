Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_cv.md.
Original prompt:
﻿# Task: Create cochem_bench_cv.py (Stage 3.0)

## Target File
`D:\__CoChem\GitHub-Repo\CoChem-BENCH\bench_engine\cochem_bench_cv.py`

## Architecture Note
This is a V2 rewrite. Ignore the legacy `bench_core` architecture described in the old `workflow.md`. Implement exactly as specified here.

## Requirements
Implement the Stage 3.0 Core-Valence (CV) Correlation Correction script.
Computes the CV correction term by comparing Frozen-Core versus All-Electron correlation treatments.

Functions to implement:
1. `CoreValenceMapper()`: Dynamically maps appropriate core-polarized basis sets (e.g., `aug-cc-pwCVQZ`) based on elemental composition.
2. `DualCorrelationEngine()`: Executes and compares a Frozen-Core calculation against an All-Electron calculation.
3. `DeltaExtractor()`: Mathematically derives the energy difference (AE - FC).
4. `EphemeralScratchPurge()`: Explicit `os.remove()` sweep of `.gbw` and `.tmp` files in the `Scratch/` directory immediately after energy extraction.

## I/O Contract
- Writes CV correction delta to `landscape.h5`.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\cochem_topos_graph.py ---
"""
CoChem-TOPOS v4.0: Graph Cleavage and Pipeline Routing Engine (cochem_topos_graph.py)
Translates 3D Cartesian coordinates into a mathematical adjacency matrix,
applies physical tolerances, and objectively classifies systems as independent monomers,
strongly coordinated structures, or weak Van der Waals (vdW) complexes.

Implements:
1. Ecosystem Role & Handoff: In-memory coordinate and atomic number array ingestion.
2. Distance Matrix & The Resonance Protection Trap: scipy.spatial.distance.cdist,
   mendeleev covalent radii, 1.15x breathing tolerance (T_ij = 1.15 * (R_i + R_j),
   A_ij = 1 if D_ij <= T_ij else 0 for i != j).
3. NetworkX Graph Generation & Cleavage: Connected component evaluation.
4. Complex Triage Protocol: Calculates shortest distance vector between sub-graphs.
   - Strong Complex: If shortest distance connects to a transition metal (e.g. Fe, Pd, Ru,
     or d/f-block element) or formal coordination bridge -> tagged as STRONG_COMPLEX,
     cleavage aborted, and routed as a single unit to Stage 2.0.
   - Weak Complex: If purely non-covalent -> tagged as WEAK_COMPLEX, and mathematically
     severed into independent numpy arrays (MonomerSeed objects).
5. The 4-Atom Mathematical Bypass: If an isolated monomer fragment from a WEAK_COMPLEX
     (or monomer) has < 4 atoms, flags with BYPASS_GOAT to skip deep thermal searches.
6. UI Telemetry & Air-Gapped State Export: (i, j) atomic indices and distance of shortest
   non-covalent gap serialized to JSON for UI rendering via Pydantic; isolated monomer coordinate
   arrays exported as .xyz files strictly to dynamic paths derived from os.environ.get("COCHEM_WORKSPACE")
   (e.g., ${COCHEM_WORKSPACE}/CoChem_Artifacts/Input_Files/user_seeds/); stage_n_complete.json updated;
   GOAT primary with CREST secondary flags ('--nci', '--nocross', '--noreftopo').
7. Subprocess Safety & Rigorous Linting: Process-safe subprocess wrappers with check=True,
   strict timeouts, psutil/atexit zombie cleanup, standard logging, and exhaustive Python 3.10+ typing.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import subprocess
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import mendeleev
import networkx as nx
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field
from scipy.spatial.distance import cdist

logger = logging.getLogger("CoChem.TOPOS.GraphEngine")

# Standard Resonance Protection Scaling Factor
RESONANCE_PROTECTION_SCALE: float = 1.15

# Default fallback covalent radius (Angstroms) for uncharacterized / transuranic elements
DEFAULT_COVALENT_RADIUS: float = 1.50


# Subprocess lifecycle management for zombie prevention
_ACTIVE_SUBPROCESSES: set[subprocess.Popen[Any]] = set()


def _cleanup_zombie_subprocesses() -> None:
    """Atexit hook ensuring all child subprocesses are safely terminated."""
    for proc in list(_ACTIVE_SUBPROCESSES):
        if proc.poll() is None:
            try:
                p_obj = psutil.Process(proc.pid)
                for child in p_obj.children(recursive=True):
                    try:
                        child.terminate()
                    except Exception:
                        pass
                p_obj.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


atexit.register(_cleanup_zombie_subprocesses)


@lru_cache(maxsize=256)
def get_mendeleev_element(element: str | int) -> mendeleev.models.Element:
    """
    Resolves an element symbol or atomic number to a mendeleev Element instance.
    Dynamically loads all chemical constants directly from the authoritative mendeleev database.
    """
    if isinstance(element, int):
        if 1 <= element <= 118:
            return mendeleev.element(element)
        raise ValueError(f"Atomic number {element} out of valid range (1..118)")

    elem_str = str(element).strip()
    if elem_str.isdigit():
        z = int(elem_str)
        if 1 <= z <= 118:
            return mendeleev.element(z)
        raise ValueError(f"Atomic number {z} out of valid range (1..118)")

    capitalized = elem_str.capitalize()
    try:
        return mendeleev.element(capitalized)
    except Exception as err:
        raise ValueError(f"Unrecognized chemical element symbol or atomic number: '{element}'") from err


def get_atomic_number(element: str | int) -> int:
    """Resolves an element symbol or number to its integer atomic number (Z)."""
    if isinstance(element, int) and 1 <= element <= 118:
        return element
    elem = get_mendeleev_element(element)
    return int(elem.atomic_number)


def get_atomic_symbol(element: str | int) -> str:
    """Returns canonical IUPAC element symbol for atomic number Z or element symbol."""
    try:
        elem = get_mendeleev_element(element)
        return str(elem.symbol)
    except Exception:
        return f"X{element}"


@lru_cache(maxsize=256)
def get_covalent_radius(element: str | int) -> float:
    """
    Returns empirical single-bond covalent radius in Angstroms dynamically from mendeleev.
    Prioritizes Cordero et al. standard covalent radius (pm / 100), falling back to Pyykko or default.
    """
    try:
        elem = get_mendeleev_element(element)
        cov = elem.covalent_radius_cordero
        if cov is None:
            cov = elem.covalent_radius_pyykko
        if cov is None:
            cov = elem.covalent_radius
        if cov is not None:
            return round(float(cov) / 100.0, 4)
        return DEFAULT_COVALENT_RADIUS
    except Exception:
        return DEFAULT_COVALENT_RADIUS


@lru_cache(maxsize=256)
def get_atomic_mass(element: str | int) -> float:
    """Returns standard atomic weight in amu dynamically from mendeleev."""
    try:
        elem = get_mendeleev_element(element)
        return float(elem.mass)
    except Exception:
        return 12.0


@lru_cache(maxsize=256)
def is_transition_or_coordination_metal(element: str | int) -> bool:
    """
    Determines if an element is a transition metal, lanthanide, actinide, or coordination metal center
    capable of forming strong d-block/f-block coordination complexes.
    """
    try:
        elem = get_mendeleev_element(element)
        series = getattr(elem, "series", "")
        block = getattr(elem, "block", "")
        z = int(elem.atomic_number)
        if series in ("Transition metals", "Lanthanides", "Actinides"):
            return True
        if block in ("d", "f"):
            return True
        if (21 <= z <= 30) or (39 <= z <= 48) or (57 <= z <= 80) or (89 <= z <= 112):
            return True
        return False
    except Exception:
        return False


class _DynamicCovalentRadiiMapping(dict[Any, float]):
    """Dynamic dict-like proxy that lazily queries mendeleev for covalent radii."""
    def __getitem__(self, key: int | str) -> float:
        return get_covalent_radius(key)

    def get(self, key: int | str, default: float = DEFAULT_COVALENT_RADIUS) -> float:  # type: ignore[override]
        try:
            return get_covalent_radius(key)
        except Exception:
            return default

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int | str):
            try:
                get_atomic_number(key)
                return True
            except Exception:
                return False
        return False


class _DynamicAtomicWeightsMapping(dict[Any, float]):
    """Dynamic dict-like proxy that lazily queries mendeleev for atomic masses."""
    def __getitem__(self, key: int | str) -> float:
        return get_atomic_mass(key)

    def get(self, key: int | str, default: float = 12.0) -> float:  # type: ignore[override]
        try:
            return get_atomic_mass(key)
        except Exception:
            return default

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int | str):
            try:
                get_atomic_number(key)
                return True
            except Exception:
                return False
        return False


COVALENT_RADII: dict[int | str, float] = _DynamicCovalentRadiiMapping()
ATOMIC_WEIGHTS: dict[int | str, float] = _DynamicAtomicWeightsMapping()


def _to_coords_array(coordinates: np.ndarray | Sequence[Sequence[float]]) -> np.ndarray:
    """Normalizes Cartesian coordinates to a typed 2D float64 NumPy array."""
    arr: np.ndarray = np.asarray(coordinates, dtype=np.float64)
    return arr


def generate_chemical_formula(symbols: Sequence[str | int]) -> str:
    """
    Constructs a standard Hill system chemical formula.
    Carbon (C) first, then Hydrogen (H), then all remaining elements alphabetically.
    If no Carbon is present, all elements are listed alphabetically.
    """
    counts: dict[str, int] = {}
    for s in symbols:
        std_sym = get_atomic_symbol(s)
        counts[std_sym] = counts.get(std_sym, 0) + 1

    parts: list[str] = []
    if "C" in counts:
        c_count = counts.pop("C")
        parts.append(f"C{c_count}" if c_count > 1 else "C")
        if "H" in counts:
            h_count = counts.pop("H")
            parts.append(f"H{h_count}" if h_count > 1 else "H")

    for elem in sorted(counts.keys()):
        count = counts[elem]
        parts.append(f"{elem}{count}" if count > 1 else elem)

    return "".join(parts)


def parse_xyz_string(xyz_content: str) -> tuple[list[str], np.ndarray, str]:
    """
    Parses a standard multi-line XYZ formatted string into symbols, coordinates, and comment line.
    """
    lines = [line.strip() for line in xyz_content.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("Cannot parse empty XYZ string.")

    first_token = lines[0].split()[0]
    is_standard_xyz = False
    try:
        num_atoms = int(first_token)
        is_standard_xyz = True
    except ValueError:
        is_standard_xyz = False

    if is_standard_xyz:
        comment = lines[1] if len(lines) > 1 else ""
        coord_lines = lines[2: 2 + num_atoms]
    else:
        comment = ""
        coord_lines = lines

    symbols: list[str] = []
    coords_list: list[list[float]] = []

    for idx, line in enumerate(coord_lines):
        tokens = line.split()
        if len(tokens) < 4:
            raise ValueError(f"Line {idx+1} does not have at least 4 tokens (Symbol X Y Z): '{line}'")
        sym = tokens[0]
        try:
            x, y, z = float(tokens[1]), float(tokens[2]), float(tokens[3])
        except ValueError as err:
            raise ValueError(f"Invalid coordinate floats on line {idx+1}: '{line}'") from err
        symbols.append(sym)
        coords_list.append([x, y, z])

    return symbols, np.array(coords_list, dtype=np.float64), comment


def parse_xyz_file(filepath: str | Path) -> tuple[list[str], np.ndarray, str]:
    """Parses an XYZ coordinate file from the filesystem."""
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"XYZ file not found: {path}")
    content = path.read_text(encoding="utf-8")
    return parse_xyz_string(content)


class MonomerSeed(BaseModel):
    """
    Represents an isolated molecular fragment severed from a larger system.
    Maintains coordinate positions, parent index tracing, mass properties, and bypass flags.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    fragment_index: int = Field(..., description="0-indexed partition ID of this severed monomer.")
    atom_indices: list[int] = Field(..., description="Indices of the constituent atoms in the parent system.")
    symbols: list[str] = Field(..., description="Element symbols for each atom in this monomer.")
    atomic_numbers: list[int] = Field(..., description="Atomic numbers (Z) for each atom.")
    coordinates: list[list[float]] = Field(..., description="Cartesian coordinates in Angstroms (Nx3).")
    formula: str = Field(..., description="Hill notation chemical formula.")
    num_atoms: int = Field(..., description="Total atom count in this monomer.")
    center_of_mass: list[float] = Field(..., description="Mass-weighted Cartesian center of mass [X, Y, Z].")
    total_mass: float = Field(..., description="Total atomic mass in amu.")
    bypass_goat: bool = Field(default=False, description="Flag for <4 atom fragments to skip deep thermal searches and execute rapid point relaxation.")
    routing_target: str = Field(default="STAGE_2_0", description="Downstream execution target stage.")

    def get_numpy_coordinates(self) -> np.ndarray:
        """Returns coordinates as an (N, 3) NumPy float64 array."""
        arr: np.ndarray = np.asarray(self.coordinates, dtype=np.float64)
        return arr

    def to_xyz_string(self, comment: str = "") -> str:
        """Serializes this monomer seed into standard XYZ geometry text."""
        cmt = comment or f"Monomer {self.fragment_index} | Formula: {self.formula} | Atoms: {self.num_atoms} | BypassGOAT: {self.bypass_goat}"
        lines = [str(self.num_atoms), cmt]
        for sym, (x, y, z) in zip(self.symbols, self.coordinates, strict=False):
            lines.append(f"{sym:<3} {x:14.8f} {y:14.8f} {z:14.8f}")
        return chr(10).join(lines) + chr(10)

    def save_xyz(self, filepath: str | Path, comment: str = "") -> Path:
        """Saves this monomer seed to an XYZ file on disk."""
        target_path = Path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.to_xyz_string(comment=comment), encoding="utf-8")
        return target_path


class ShortestGapTelemetry(BaseModel):
    """
    Telemetry capturing the closest non-covalent interaction gap between disconnected fragments.
    """
    atom_i: int = Field(..., description="0-indexed atom index of contact atom in first fragment.")
    atom_j: int = Field(..., description="0-indexed atom index of contact atom in second fragment.")
    symbol_i: str = Field(..., description="Element symbol of contact atom i.")
    symbol_j: str = Field(..., description="Element symbol of contact atom j.")
    fragment_i: int = Field(..., description="Fragment index containing atom i.")
    fragment_j: int = Field(..., description="Fragment index containing atom j.")
    distance: float = Field(..., description="Euclidean distance in Angstroms across the shortest gap.")
    is_transition_metal_contact: bool = Field(..., description="True if contact involves a transition/coordination metal.")


class TopologyAnalysisResult(BaseModel):
    """
    Structured outcome of the 3D connectivity graph analysis and Complex Triage Protocol.
    Dictates whether the system enters standard monomer GOAT optimization,
    triggers counterpoise assembly and fragment-isolated workflows,
    or routes as a strongly coordinated unit to Stage 2.0.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    num_atoms: int = Field(..., description="Total number of atoms in the parent system.")
    num_fragments: int = Field(..., description="Total number of disconnected sub-graphs detected.")
    is_weak_complex: bool = Field(..., description="True if multiple disconnected sub-graphs exist and purely non-covalent.")
    is_strong_complex: bool = Field(default=False, description="True if inter-fragment contacts involve transition metal coordination.")
    classification: str = Field(..., description="'Monomer', 'Strong Complex', or 'Weak Complex'.")
    complex_type: str = Field(default="MONOMER", description="'MONOMER', 'STRONG_COMPLEX', or 'WEAK_COMPLEX'.")
    routing_target: str = Field(..., description="'MONOMER_GOAT', 'STRONG_COMPLEX', or 'COUNTERPOISE_ASSEMBLY'.")
    counterpoise_flag: bool = Field(..., description="Explicit flag for downstream Counterpoise (CP) assembly.")
    monomers: list[MonomerSeed] = Field(default_factory=list, description="Severed monomer seeds (or single unit if monomer/strong complex).")
    adjacency_matrix: list[list[int]] = Field(default_factory=list, description="Binary covalent adjacency matrix.")
    distance_matrix: list[list[float]] = Field(default_factory=list, description="Pairwise Cartesian distance matrix.")
    graph_edges: list[tuple[int, int]] = Field(default_factory=list, description="List of covalent bond edges (i, j).")
    resonance_protection_scale: float = Field(default=RESONANCE_PROTECTION_SCALE, description="Applied resonance scaling.")
    shortest_gap: ShortestGapTelemetry | None = Field(default=None, description="Telemetry for closest non-covalent contact gap.")
    bypass_goat_fragments: list[int] = Field(default_factory=list, description="Fragment partition IDs flagged for BYPASS_GOAT (<4 atoms).")
    crest_command_flags: list[str] = Field(default_factory=lambda: ["--nci", "--nocross", "--noreftopo"], description="CREST secondary search flags.")
    summary: str = Field(default="", description="Human-readable topology and routing summary.")

    def get_networkx_graph(self) -> nx.Graph:
        """Reconstructs the NetworkX Graph from graph edges and monomer metadata."""
        g = nx.Graph()
        for monomer in self.monomers:
            for idx, sym, z, coord in zip(monomer.atom_indices, monomer.symbols, monomer.atomic_numbers, monomer.coordinates, strict=False):
                g.add_node(idx, symbol=sym, atomic_number=z, coordinates=coord, fragment=monomer.fragment_index)
        for u, v in self.graph_edges:
            dist = self.distance_matrix[u][v] if self.distance_matrix else 0.0
            g.add_edge(u, v, distance=dist)
        return g

    def to_json(self, indent: int = 2) -> str:
        """Serializes result to JSON string."""
        res: str = cast(str, self.model_dump_json(indent=indent))
        return res

    def to_dict(self) -> dict[str, Any]:
        """Returns result as a standard Python dictionary."""
        d: dict[str, Any] = cast(dict[str, Any], self.model_dump())
        return d

    def save_monomers_xyz(self, output_dir: str | Path, base_prefix: str = "monomer") -> list[Path]:
        """Writes each severed monomer seed to an individual XYZ file."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[Path] = []
        for monomer in self.monomers:
            filename = f"{base_prefix}_{monomer.fragment_index}_{monomer.formula}.xyz"
            target = out_dir / filename
            monomer.save_xyz(target)
            saved_paths.append(target)
        return saved_paths

    def export_air_gapped_state(
        self,
        workspace: str | Path | None = None,
        stage_tracker_file: str | Path | None = None
    ) -> dict[str, Any]:
        """
        Exports isolated monomer coordinate arrays as .xyz files strictly to dynamic paths
        derived from os.environ.get('COCHEM_WORKSPACE') (e.g. ${COCHEM_WORKSPACE}/CoChem_Artifacts/Input_Files/user_seeds/)
        and writes/updates stage_n_complete.json.
        """
        target_ws: str | Path = workspace if workspace is not None else os.environ.get("COCHEM_WORKSPACE", "D:/__CoChem")
        ws_path = Path(target_ws)
        user_seeds_dir = ws_path / "CoChem_Artifacts" / "Input_Files" / "user_seeds"
        user_seeds_dir.mkdir(parents=True, exist_ok=True)

        exported_xyz_paths = self.save_monomers_xyz(user_seeds_dir, base_prefix="user_seed")

        tracker_data: dict[str, Any] = {
            "stage": "1.1",
            "stage_name": "Topology Graph & Weak Complex Cleavage",
            "status": "COMPLETE",
            "classification": self.classification,
            "complex_type": self.complex_type,
            "routing_target": self.routing_target,
            "num_atoms": self.num_atoms,
            "num_fragments": self.num_fragments,
            "parent_complex_stage": "Stage 3.0" if self.is_weak_complex else "N/A",
            "monomer_seeds_stage": "Stage 2.0",
            "counterpoise_flag": self.counterpoise_flag,
            "bypass_goat_fragments": self.bypass_goat_fragments,
            "monomer_seeds": [
                {
                    "fragment_index": m.fragment_index,
                    "formula": m.formula,
                    "num_atoms": m.num_atoms,
                    "bypass_goat": m.bypass_goat,
                    "xyz_path": str(xyz_p)
                }
                for m, xyz_p in zip(self.monomers, exported_xyz_paths, strict=False)
            ],
            "shortest_gap_telemetry": self.shortest_gap.model_dump() if self.shortest_gap else None,
            "secondary_search": {
                "engine": "CREST",
                "flags": self.crest_command_flags,
                "strategy": "GOAT_PRIMARY_CREST_SECONDARY_UNION"
            }
        }

        tracker_path: Path = Path(stage_tracker_file) if stage_tracker_file is not None else (ws_path / "CoChem_Artifacts" / "stage_n_complete.json")
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text(json.dumps(tracker_data, indent=2), encoding="utf-8")
        logger.info(f"Air-Gapped State and Stage Tracker exported to: {tracker_path}")

        return tracker_data


class TopologyGraphEngine:
    """
    Topology Graph Engine converting 3D Cartesian coordinates into a connectivity graph.
    Applies the 1.15x Resonance Protection Trap, implements the Complex Triage Protocol,
    and partitions disconnected sub-graphs into isolated monomer seeds with <4-atom bypasses.
    """

    def __init__(
        self,
        resonance_scale: float = RESONANCE_PROTECTION_SCALE,
        covalent_radii: dict[int | str, float] | None = None
    ) -> None:
        self.resonance_scale: float = float(resonance_scale)
        self.custom_radii: dict[int, float] = {}
        if covalent_radii is not None:
            for k, v in covalent_radii.items():
                z = get_atomic_number(k)
                self.custom_radii[z] = float(v)

    def get_radius(self, element: str | int) -> float:
        """Retrieves covalent radius for given element, honoring custom overrides or mendeleev."""
        try:
            z = get_atomic_number(element)
            if z in self.custom_radii:
                return self.custom_radii[z]
        except Exception:
            pass
        return get_covalent_radius(element)

    def compute_distance_matrix(self, coordinates: np.ndarray | Sequence[Sequence[float]]) -> np.ndarray:
        """
        Computes the pairwise Euclidean distance matrix (Dij) between all atoms.
        Uses scipy.spatial.distance.cdist.
        """
        coords_arr: np.ndarray = _to_coords_array(coordinates)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise ValueError(f"Cartesian coordinates must have shape (N, 3), received {coords_arr.shape}.")
        d_mat: np.ndarray = np.asarray(cdist(coords_arr, coords_arr), dtype=np.float64)
        return d_mat  # type: ignore[no-any-return]

    def build_adjacency_matrix(
        self,
        symbols_or_atomic_numbers: Sequence[str | int],
        coordinates: np.ndarray | Sequence[Sequence[float]],
        resonance_scale: float | None = None
    ) -> np.ndarray:
        """
        Constructs the binary adjacency matrix (A) using covalent radii and the Resonance Protection Trap.
        Formula: A_ij = 1 if D_ij <= scale * (R_i + R_j) for i != j, 0 otherwise.
        """
        scale = self.resonance_scale if resonance_scale is None else float(resonance_scale)
        num_atoms = len(symbols_or_atomic_numbers)
        if num_atoms == 0:
            return np.zeros((0, 0), dtype=np.int32)

        coords_arr: np.ndarray = _to_coords_array(coordinates)
        if coords_arr.shape[0] != num_atoms:
            raise ValueError(f"Mismatch: {num_atoms} symbols provided but {coords_arr.shape[0]} coordinate rows.")

        dists = self.compute_distance_matrix(coords_arr)
        radii = np.array([self.get_radius(elem) for elem in symbols_or_atomic_numbers], dtype=float)

        radii_sum = radii[:, np.newaxis] + radii[np.newaxis, :]
        threshold_matrix = scale * radii_sum

        adjacency: np.ndarray = np.asarray(dists <= threshold_matrix, dtype=np.int32)
        np.fill_diagonal(adjacency, 0)
        return adjacency

    def build_graph(
        self,
        symbols_or_atomic_numbers: Sequence[str | int],
        coordinates: np.ndarray | Sequence[Sequence[float]],
        resonance_scale: float | None = None
    ) -> nx.Graph:
        """
        Constructs a NetworkX graph with node and edge attributes derived from Cartesian geometry.
        """
        coords_arr: np.ndarray = _to_coords_array(coordinates)
        num_atoms = len(symbols_or_atomic_numbers)
        adj = self.build_adjacency_matrix(symbols_or_atomic_numbers, coords_arr, resonance_scale=resonance_scale)
        dists = self.compute_distance_matrix(coords_arr)

        g = nx.Graph()
        for i, elem in enumerate(symbols_or_atomic_numbers):
            z = get_atomic_number(elem)
            sym = get_atomic_symbol(z)
            g.add_node(i, symbol=sym, atomic_number=z, coordinates=[float(coords_arr[i, 0]), float(coords_arr[i, 1]), float(coords_arr[i, 2])])

        for i in range(num_atoms):
            for j in range(i + 1, num_atoms):
                if adj[i, j] == 1:
                    g.add_edge(i, j, distance=float(dists[i, j]))

        return g

    def analyze_topology(
        self,
        symbols_or_atomic_numbers: Sequence[str | int],
        coordinates: np.ndarray | Sequence[Sequence[float]],
        resonance_scale: float | None = None
    ) -> TopologyAnalysisResult:
        """
        Main entry point for topological graph evaluation.
        Converts 3D Cartesian coordinates into a connectivity graph, evaluates connected sub-graphs,
        executes Complex Triage Protocol, and constructs severed monomer seeds for weak complexes.
        """
        scale = self.resonance_scale if resonance_scale is None else float(resonance_scale)
        num_atoms = len(symbols_or_atomic_numbers)
        if num_atoms == 0:
            raise ValueError("Cannot analyze empty system: At least one atom required.")

        coords_arr: np.ndarray = _to_coords_array(coordinates)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise ValueError(f"Cartesian coordinates must have shape (N, 3), received {coords_arr.shape}.")
        if coords_arr.shape[0] != num_atoms:
            raise ValueError(f"Mismatch: {num_atoms} element entries but {coords_arr.shape[0]} coordinate rows.")

        d_matrix = self.compute_distance_matrix(coords_arr)
        a_matrix = self.build_adjacency_matrix(symbols_or_atomic_numbers, coords_arr, resonance_scale=scale)

        g = nx.Graph()
        std_symbols: list[str] = []
        atomic_numbers: list[int] = []

        for i, elem in enumerate(symbols_or_atomic_numbers):
            z = get_atomic_number(elem)
            sym = get_atomic_symbol(z)
            std_symbols.append(sym)
            atomic_numbers.append(z)
            g.add_node(i, symbol=sym, atomic_number=z, coordinates=[float(coords_arr[i, 0]), float(coords_arr[i, 1]), float(coords_arr[i, 2])])

        graph_edges: list[tuple[int, int]] = []
        for i in range(num_atoms):
            for j in range(i + 1, num_atoms):
                if a_matrix[i, j] == 1:
                    g.add_edge(i, j, distance=float(d_matrix[i, j]))
                    graph_edges.append((i, j))

        raw_components = list(nx.connected_components(g))
        sorted_components = sorted(raw_components, key=lambda comp: min(comp))
        num_fragments = len(sorted_components)

        monomer_seeds: list[MonomerSeed] = []
        bypass_goat_fragments: list[int] = []
        shortest_gap: ShortestGapTelemetry | None = None

        if num_fragments == 1:
            # Monomer system
            classification = "Monomer"
            complex_type = "MONOMER"
            routing_target = "MONOMER_GOAT"
            is_weak_complex = False
            is_strong_complex = False
            counterpoise_flag = False

            comp_indices = list(range(num_atoms))
            formula = generate_chemical_formula(std_symbols)
            masses = np.array([get_atomic_mass(z) for z in atomic_numbers], dtype=float)
            total_mass = float(np.sum(masses))
            com = (np.sum(coords_arr * masses[:, np.newaxis], axis=0) / total_mass).tolist() if total_mass > 0 else np.mean(coords_arr, axis=0).tolist()
            bypass_goat = (num_atoms < 4)
            if bypass_goat:
                bypass_goat_fragments.append(0)

            monomer_seeds.append(
                MonomerSeed(
                    fragment_index=0,
                    atom_indices=comp_indices,
                    symbols=std_symbols,
                    atomic_numbers=atomic_numbers,
                    coordinates=cast(list[list[float]], coords_arr.tolist()),
                    formula=formula,
                    num_atoms=num_atoms,
                    center_of_mass=cast(list[float], com),
                    total_mass=total_mass,
                    bypass_goat=bypass_goat,
                    routing_target="MONOMER_GOAT"
                )
            )

        else:
            # Complex Triage Protocol: Calculate shortest distance vector between Sub-Graphs
            min_gap_dist = float("inf")
            best_i: int | None = None
            best_j: int | None = None
            best_frag_i: int | None = None
            best_frag_j: int | None = None

            for a_idx in range(len(sorted_components)):
                for b_idx in range(a_idx + 1, len(sorted_components)):
                    comp_a = sorted_components[a_idx]
                    comp_b = sorted_components[b_idx]
                    for u in comp_a:
                        for v in comp_b:
                            d = float(d_matrix[u, v])
                            if d < min_gap_dist:
                                min_gap_dist = d
                                best_i = u
                                best_j = v
                                best_frag_i = a_idx
                                best_frag_j = b_idx

            is_tm_contact = False
            if best_i is not None and best_j is not None and best_frag_i is not None and best_frag_j is not None:
                sym_i = std_symbols[best_i]
                sym_j = std_symbols[best_j]
                is_tm_contact = is_transition_or_coordination_metal(sym_i) or is_transition_or_coordination_metal(sym_j)
                shortest_gap = ShortestGapTelemetry(
                    atom_i=best_i,
                    atom_j=best_j,
                    symbol_i=sym_i,
                    symbol_j=sym_j,
                    fragment_i=best_frag_i,
                    fragment_j=best_frag_j,
                    distance=round(min_gap_dist, 5),
                    is_transition_metal_contact=is_tm_contact
                )

            if is_tm_contact:
                # Strong Complex: Transition metal coordination bridge -> abort cleavage
                classification = "Strong Complex"
                complex_type = "STRONG_COMPLEX"
                routing_target = "STRONG_COMPLEX"
                is_weak_complex = False
                is_strong_complex = True
                counterpoise_flag = False

                comp_indices = list(range(num_atoms))
                formula = generate_chemical_formula(std_symbols)
                masses = np.array([get_atomic_mass(z) for z in atomic_numbers], dtype=float)
                total_mass = float(np.sum(masses))
                com = (np.sum(coords_arr * masses[:, np.newaxis], axis=0) / total_mass).tolist() if total_mass > 0 else np.mean(coords_arr, axis=0).tolist()
                bypass_goat = (num_atoms < 4)
                if bypass_goat:
                    bypass_goat_fragments.append(0)

                monomer_seeds.append(
                    MonomerSeed(
                        fragment_index=0,
                        atom_indices=comp_indices,
                        symbols=std_symbols,
                        atomic_numbers=atomic_numbers,
                        coordinates=cast(list[list[float]], coords_arr.tolist()),
                        formula=formula,
                        num_atoms=num_atoms,
                        center_of_mass=cast(list[float], com),
                        total_mass=total_mass,
                        bypass_goat=bypass_goat,
                        routing_target="STRONG_COMPLEX"
                    )
                )

            else:
                # Weak Complex: Purely non-covalent -> mathematically sever into independent numpy matrices
                classification = "Weak Complex"
                complex_type = "WEAK_COMPLEX"
                routing_target = "COUNTERPOISE_ASSEMBLY"
                is_weak_complex = True
                is_strong_complex = False
                counterpoise_flag = True

                for frag_idx, comp in enumerate(sorted_components):
                    comp_indices = sorted(list(comp))
                    frag_symbols = [std_symbols[idx] for idx in comp_indices]
                    frag_z = [atomic_numbers[idx] for idx in comp_indices]
                    frag_coords = coords_arr[comp_indices]
                    frag_formula = generate_chemical_formula(frag_symbols)

                    masses = np.array([get_atomic_mass(z) for z in frag_z], dtype=float)
                    total_mass = float(np.sum(masses))
                    if total_mass > 0:
                        com = (np.sum(frag_coords * masses[:, np.newaxis], axis=0) / total_mass).tolist()
                    else:
                        com = np.mean(frag_coords, axis=0).tolist()

                    bypass_goat = (len(comp_indices) < 4)
                    if bypass_goat:
                        bypass_goat_fragments.append(frag_idx)

                    monomer = MonomerSeed(
                        fragment_index=frag_idx,
                        atom_indices=comp_indices,
                        symbols=frag_symbols,
                        atomic_numbers=frag_z,
                        coordinates=cast(list[list[float]], frag_coords.tolist()),
                        formula=frag_formula,
                        num_atoms=len(comp_indices),
                        center_of_mass=cast(list[float], com),
                        total_mass=total_mass,
                        bypass_goat=bypass_goat,
                        routing_target="STAGE_2_0"
                    )
                    monomer_seeds.append(monomer)

        summary_lines = [
            f"Topology Classification: {classification} ({num_fragments} fragment{'s' if num_fragments != 1 else ''})",
            f"Complex Type: {complex_type} | Routing Target: {routing_target} | Counterpoise Flag: {counterpoise_flag}",
            f"Total Atoms: {num_atoms} | Covalent Edges: {len(graph_edges)} | Resonance Scale: {scale:.2f}x",
            f"Fragments: {', '.join([f'{m.formula} (N={m.num_atoms}, BypassGOAT={m.bypass_goat})' for m in monomer_seeds])}"
        ]
        if shortest_gap:
            summary_lines.append(
                f"Shortest Gap: {shortest_gap.distance:.3f} A ({shortest_gap.symbol_i}[{shortest_gap.atom_i}] <-> {shortest_gap.symbol_j}[{shortest_gap.atom_j}], TM={shortest_gap.is_transition_metal_contact})"
            )
        summary_str = " | ".join(summary_lines)

        logger.info(summary_str)

        return TopologyAnalysisResult(
            num_atoms=num_atoms,
            num_fragments=num_fragments,
            is_weak_complex=is_weak_complex,
            is_strong_complex=is_strong_complex,
            classification=classification,
            complex_type=complex_type,
            routing_target=routing_target,
            counterpoise_flag=counterpoise_flag,
            monomers=monomer_seeds,
            adjacency_matrix=cast(list[list[int]], a_matrix.tolist()),
            distance_matrix=cast(list[list[float]], d_matrix.tolist()),
            graph_edges=graph_edges,
            resonance_protection_scale=scale,
            shortest_gap=shortest_gap,
            bypass_goat_fragments=bypass_goat_fragments,
            summary=summary_str
        )

    def analyze_xyz_string(self, xyz_str: str, resonance_scale: float | None = None) -> TopologyAnalysisResult:
        """Parses and analyzes an XYZ formatted string."""
        symbols, coords, _ = parse_xyz_string(xyz_str)
        return self.analyze_topology(symbols, coords, resonance_scale=resonance_scale)

    def analyze_xyz_file(self, xyz_filepath: str | Path, resonance_scale: float | None = None) -> TopologyAnalysisResult:
        """Reads and analyzes an XYZ file from disk."""
        symbols, coords, _ = parse_xyz_file(xyz_filepath)
        return self.analyze_topology(symbols, coords, resonance_scale=resonance_scale)

    def analyze_atoms(self, atoms: Any, resonance_scale: float | None = None) -> TopologyAnalysisResult:
        """Analyzes an ASE Atoms object or equivalent container."""
        if hasattr(atoms, "get_chemical_symbols") and hasattr(atoms, "get_positions"):
            symbols = list(atoms.get_chemical_symbols())
            coords = np.asarray(atoms.get_positions(), dtype=np.float64)
            return self.analyze_topology(symbols, coords, resonance_scale=resonance_scale)
        elif hasattr(atoms, "symbols") and hasattr(atoms, "positions"):
            symbols = list(atoms.symbols)
            coords = np.asarray(atoms.positions, dtype=np.float64)
            return self.analyze_topology(symbols, coords, resonance_scale=resonance_scale)
        else:
            raise TypeError("Provided atoms object does not implement standard ASE Atoms interface.")


def analyze_molecular_graph(
    symbols: Sequence[str | int],
    coordinates: np.ndarray | Sequence[Sequence[float]],
    resonance_scale: float = RESONANCE_PROTECTION_SCALE
) -> TopologyAnalysisResult:
    """
    Convenience function for direct molecular graph evaluation and cleavage routing.
    """
    engine = TopologyGraphEngine(resonance_scale=resonance_scale)
    return engine.analyze_topology(symbols, coordinates)


def run_crest_secondary_search(
    xyz_path: str | Path,
    output_dir: str | Path,
    crest_binary: str = "crest",
    flags: Sequence[str] = ("--nci", "--nocross", "--noreftopo"),
    timeout_seconds: float = 300.0,
    check: bool = True
) -> subprocess.CompletedProcess[str]:
    """
    Subprocess execution wrapper for secondary CREST conformational search.
    Enforces check=True, strict timeout, standard logging, and process safety.
    """
    xyz_p = Path(xyz_path).resolve()
    if not xyz_p.is_file():
        raise FileNotFoundError(f"Target XYZ coordinate file not found for CREST: {xyz_p}")

    out_p = Path(output_dir).resolve()
    out_p.mkdir(parents=True, exist_ok=True)

    cmd = [crest_binary, str(xyz_p), *list(flags)]
    logger.info(f"Executing secondary CREST search: {' '.join(cmd)} (Timeout: {timeout_seconds}s)")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(out_p),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        _ACTIVE_SUBPROCESSES.add(proc)
        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as err:
            logger.error(f"CREST execution timed out after {timeout_seconds}s. Terminating PID {proc.pid}.")
            try:
                p_obj = psutil.Process(proc.pid)
                for child in p_obj.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
                p_obj.kill()
            except Exception:
                proc.kill()
            proc.wait()
            raise TimeoutError(f"CREST process timed out after {timeout_seconds} seconds") from err
        finally:
            _ACTIVE_SUBPROCESSES.discard(proc)

        retcode = proc.returncode
        result = subprocess.CompletedProcess(args=cmd, returncode=retcode, stdout=stdout, stderr=stderr)
        if check and retcode != 0:
            raise subprocess.CalledProcessError(retcode, cmd, output=stdout, stderr=stderr)
        return result

    except FileNotFoundError as err:
        logger.warning(f"CREST binary '{crest_binary}' not found on system PATH: {err}")
        raise

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_cv.py ---
#!/usr/bin/env python3
r"""Stage 3.0: Core-Valence (CV) Correlation Correction Engine.

Authoritative Implementation: bench_engine.cochem_bench_cv
System Domain: CoChem-BENCH Scientific Engine

Key Capabilities:
1. CoreValenceMapper: Dynamically maps appropriate core-polarized basis sets
   (e.g., aug-cc-pwCVnZ, cc-pCVnZ) and inspects elemental core electron configurations
   via the Mendeleev library.
2. DualCorrelationEngine: Formulates and executes dual single-point evaluations
   comparing Frozen-Core (FC) against All-Electron (AE with NoFrozenCore) treatments,
   enforcing CUDA accelerator isolation (CUDA_VISIBLE_DEVICES="") and %maxcore memory limits.
3. DeltaExtractor: Extracts FINAL SINGLE POINT ENERGY floats from authentic ORCA standard
   outputs and mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC).
4. EphemeralScratchPurge: Tripartite scratch workspace manager executing explicit sweeps
   and unlinking of .gbw, .tmp, and intermediate files immediately after energy extraction.
5. HDF5 Persistence: Commits computed CV corrections atomically to landscape.h5.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_cv.md
"""

from __future__ import annotations

import datetime
import math
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import h5py
from mendeleev import element
from pydantic import BaseModel, Field


# ==============================================================================
# Physical Constants
# ==============================================================================

# Exact CODATA Conversion: Hartree to kcal/mol
HARTREE_TO_KCAL_MOL: float = 627.509474063


# ==============================================================================
# Data Models
# ==============================================================================

class CVCorrectionResult(BaseModel):
    """Structured result model for Core-Valence (CV) correlation energy corrections."""
    e_total_fc: float = Field(description="Frozen-Core total electronic energy in Hartree")
    e_total_ae: float = Field(description="All-Electron total electronic energy in Hartree")
    delta_e_cv_hartree: float = Field(description="Core-Valence correction delta (AE - FC) in Hartree")
    delta_e_cv_kcal_mol: float = Field(description="Core-Valence correction delta in kcal/mol")
    basis_set: str = Field(description="Core-polarized basis set used for calculations")
    original_basis_set: str = Field(default="", description="Original basis set before core-valence mapping")
    method: str = Field(default="DLPNO-CCSD(T)", description="Quantum chemistry method")
    has_core_electrons: bool = Field(default=True, description="True if molecule contains elements with core electrons (Z >= 3)")
    node_id: str = Field(default="", description="Unique identifier of the molecular node or conformer")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution or provenance metadata")


# ==============================================================================
# 1. CoreValenceMapper
# ==============================================================================

class CoreValenceMapper:
    """Dynamically maps appropriate core-polarized basis sets and inspects elemental core configurations."""

    @staticmethod
    def map_basis_set(basis_set: str) -> str:
        """Maps standard valence basis sets to their corresponding core-polarized variants.
        
        Rules:
        - "aug-cc-pVnZ" -> "aug-cc-pwCVnZ"
        - "cc-pVnZ" -> "cc-pCVnZ"
        - "def2-*" -> unchanged (def2 family natively supports all-electron/core-valence)
        - "ano-*" -> unchanged (ANO basis sets are general contraction all-electron bases)
        """
        b_str = basis_set.strip()
        b_lower = b_str.lower()

        # Handle augmented correlation consistent sets first
        if "aug-cc-pv" in b_lower:
            pattern = re.compile(r"aug-cc-pv", re.IGNORECASE)
            return pattern.sub("aug-cc-pwCV", b_str)

        # Handle standard correlation consistent sets
        if "cc-pv" in b_lower:
            pattern = re.compile(r"cc-pv", re.IGNORECASE)
            return pattern.sub("cc-pCV", b_str)

        # def2 and ANO families do not require prefix modification
        return b_str

    @staticmethod
    def inspect_elemental_core(
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    ) -> Dict[str, Any]:
        """Inspects elemental composition using Mendeleev to determine core electron counts and molecular mass."""
        total_mass = 0.0
        total_electrons = 0
        total_core_electrons = 0
        elements_present: List[str] = []

        for item in coords:
            sym = str(item[0]).strip().rstrip(":").capitalize()
            elem_data = element(sym)
            z = int(elem_data.atomic_number)
            mass = float(elem_data.mass)

            total_mass += mass
            total_electrons += z
            if sym not in elements_present:
                elements_present.append(sym)

            # Core electron calculation:
            # Z = 1, 2 (H, He): 0 core electrons
            # Z = 3 - 10 (Li - Ne): 2 core electrons (1s^2 / [He])
            # Z = 11 - 18 (Na - Ar): 10 core electrons ([Ne])
            # Z = 19 - 36 (K - Kr): 18 core electrons ([Ar])
            # Z = 37 - 54 (Rb - Xe): 36 core electrons ([Kr])
            if z <= 2:
                core_e = 0
            elif z <= 10:
                core_e = 2
            elif z <= 18:
                core_e = 10
            elif z <= 36:
                core_e = 18
            elif z <= 54:
                core_e = 36
            else:
                core_e = 54

            total_core_electrons += core_e

        has_core = total_core_electrons > 0

        return {
            "has_core_electrons": has_core,
            "total_core_electrons": total_core_electrons,
            "total_electrons": total_electrons,
            "total_mass": total_mass,
            "elements": elements_present,
        }


# ==============================================================================
# 2. DualCorrelationEngine
# ==============================================================================

class DualCorrelationEngine:
    """Manages dual Frozen-Core vs All-Electron single-point ORCA calculation configurations."""

    def __init__(
        self,
        method: str = "DLPNO-CCSD(T)",
        base_basis: str = "aug-cc-pVTZ",
        node_max_gb: float = 16.0,
        nprocs: int = 4,
        ram_safety_fraction: float = 0.75,
        tight_scf: bool = True,
        defgrid: str = "DefGrid3",
        extra_keywords: Optional[List[str]] = None,
    ) -> None:
        self.method = method
        self.base_basis = base_basis
        self.node_max_gb = float(node_max_gb)
        self.nprocs = max(1, int(nprocs))
        self.ram_safety_fraction = float(ram_safety_fraction)
        self.tight_scf = tight_scf
        self.defgrid = defgrid
        self.extra_keywords = list(extra_keywords) if extra_keywords else []

    def calculate_maxcore_per_thread(self) -> int:
        """Calculates strict per-process %maxcore in MB leaving headroom for OS and MPI runtime."""
        available_mb = self.node_max_gb * 1024.0 * self.ram_safety_fraction
        per_thread_mb = int(available_mb / self.nprocs)
        min_allowed = 250
        max_allowed = int((self.node_max_gb * 1024.0) / self.nprocs)
        candidate = max(min_allowed, per_thread_mb)
        return min(candidate, max_allowed)

    def prepare_execution_env(self) -> Dict[str, str]:
        """Prepares child subprocess execution environment, air-gapping GPUs via CUDA_VISIBLE_DEVICES=''."""
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = ""
        return env

    def generate_input_decks(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        charge: int = 0,
        mult: int = 1,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generates authentic ORCA 6.1.1 input decks for Frozen-Core and All-Electron calculations."""
        mapper = CoreValenceMapper()
        mapped_basis = mapper.map_basis_set(self.base_basis)
        maxcore_mb = self.calculate_maxcore_per_thread()

        # Job A: Frozen-Core (default)
        fc_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=False,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        # Job B: All-Electron (NoFrozenCore)
        ae_input = self._build_input_string(
            coords=coords,
            basis=mapped_basis,
            is_all_electron=True,
            charge=charge,
            mult=mult,
            maxcore_mb=maxcore_mb,
        )

        decks = {
            "fc_input": fc_input,
            "ae_input": ae_input,
            "basis_set": mapped_basis,
            "original_basis": self.base_basis,
            "method": self.method,
            "maxcore_mb": maxcore_mb,
            "nprocs": self.nprocs,
            "charge": charge,
            "mult": mult,
        }

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            (out_path / "orca_fc.inp").write_text(fc_input, encoding="utf-8")
            (out_path / "orca_ae.inp").write_text(ae_input, encoding="utf-8")

        return decks

    def _build_input_string(
        self,
        coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
        basis: str,
        is_all_electron: bool,
        charge: int,
        mult: int,
        maxcore_mb: int,
    ) -> str:
        """Constructs valid ORCA 6.1.1 input deck."""
        keywords = ["!", self.method, basis]
        if is_all_electron:
            keywords.append("NoFrozenCore")
        if self.tight_scf:
            keywords.append("TightSCF")
        if self.defgrid:
            keywords.append(self.defgrid)
        for kw in self.extra_keywords:
            if kw not in keywords:
                keywords.append(kw)

        lines = [" ".join(keywords)]
        lines.append(f"%maxcore {maxcore_mb}")
        if self.nprocs > 1:
            lines.append(f"%pal nprocs {self.nprocs} end")

        lines.append(f"* xyz {charge} {mult}")
        for atom in coords:
            sym = str(atom[0]).strip()
            x = float(atom[1])
            y = float(atom[2])
            z = float(atom[3])
            lines.append(f"  {sym:<2}  {x:12.8f}  {y:12.8f}  {z:12.8f}")
        lines.append("*\n")

        return "\n".join(lines)

    def execute_job(
        self,
        input_text: str,
        orca_binary_path: Union[str, Path],
        scratch_dir: Union[str, Path],
        job_prefix: str = "job",
        timeout_seconds: int = 7200,
    ) -> Tuple[str, str, int]:
        """Executes ORCA binary via subprocess inside isolated scratch with GPU air-gapping."""
        scratch_path = Path(scratch_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        inp_file = scratch_path / f"{job_prefix}.inp"
        inp_file.write_text(input_text, encoding="utf-8")

        env = self.prepare_execution_env()

        cmd = [str(orca_binary_path), str(inp_file)]
        proc = subprocess.run(
            cmd,
            cwd=str(scratch_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode


# ==============================================================================
# 3. DeltaExtractor
# ==============================================================================

class DeltaExtractor:
    """Extracts electronic energies from ORCA stdout streams and derives Core-Valence deltas."""

    @staticmethod
    def parse_final_energy_from_stdout(stdout_text: str) -> float:
        """Parses FINAL SINGLE POINT ENERGY from standard ORCA output."""
        match = re.search(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)", stdout_text)
        if not match:
            raise ValueError("ORCA output did not contain 'FINAL SINGLE POINT ENERGY' marker.")
        return float(match.group(1))

    @staticmethod
    def extract_delta(
        e_total_fc: float,
        e_total_ae: float,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Mathematically derives Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
        delta_hartree = float(e_total_ae) - float(e_total_fc)
        delta_kcal = delta_hartree * HARTREE_TO_KCAL_MOL

        return CVCorrectionResult(
            e_total_fc=float(e_total_fc),
            e_total_ae=float(e_total_ae),
            delta_e_cv_hartree=delta_hartree,
            delta_e_cv_kcal_mol=delta_kcal,
            basis_set=basis_set,
            original_basis_set=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata or {},
        )

    def extract_from_outputs(
        self,
        stdout_fc: str,
        stdout_ae: str,
        basis_set: str = "",
        original_basis: str = "",
        method: str = "DLPNO-CCSD(T)",
        has_core_electrons: bool = True,
        node_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CVCorrectionResult:
        """Parses energies directly from stdout texts and computes CV correction."""
        e_fc = self.parse_final_energy_from_stdout(stdout_fc)
        e_ae = self.parse_final_energy_from_stdout(stdout_ae)
        return self.extract_delta(
            e_total_fc=e_fc,
            e_total_ae=e_ae,
            basis_set=basis_set,
            original_basis=original_basis,
            method=method,
            has_core_electrons=has_core_electrons,
            node_id=node_id,
            metadata=metadata,
        )


# ==============================================================================
# 4. EphemeralScratchPurge
# ==============================================================================

class EphemeralScratchPurge:
    """Manages tripartite scratch workspace creation and sweeps intermediate scratch files."""

    @staticmethod
    def create_scratch_dir(base_artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
        """Creates a dedicated UUID-scoped scratch directory."""
        if base_artifacts_dir:
            base_dir = Path(base_artifacts_dir)
        else:
            base_env = os.environ.get(
                "COCHEM_ARTIFACTS_DIR",
                os.environ.get("COCHEM_WORKSPACE", Path.home() / "CoChem_Artifacts"),
            )
            base_dir = Path(base_env)

        scratch_dir = base_dir / "BENCH_Workspace" / "Scratch" / f"job_{uuid.uuid4()}"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    @staticmethod
    def purge_scratch_dir(
        scratch_dir: Union[str, Path],
        remove_dir: bool = True,
    ) -> Dict[str, Any]:
        """Sweeps and unlinks intermediate simulation files (.gbw, .tmp, .densities, etc.)."""
        scratch_path = Path(scratch_dir)
        if not scratch_path.exists():
            return {"status": "not_found", "purged_count": 0}

        purged_files: List[str] = []
        extensions_to_purge = [
            "*.gbw", "*.tmp", "*.densities", "*.bso", "*.prop",
            "*.core", "*.host", "*.ges", "*.int", "*.uco",
        ]

        for ext in extensions_to_purge:
            for p in scratch_path.glob(ext):
                try:
                    p.unlink()
                    purged_files.append(p.name)
                except OSError:
                    pass

        if remove_dir:
            try:
                shutil.rmtree(str(scratch_path), ignore_errors=True)
            except OSError:
                pass

        return {
            "status": "purged",
            "purged_count": len(purged_files),
            "purged_files": purged_files,
        }


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration
# ==============================================================================

def commit_cv_to_hdf5(
    h5_path: Union[str, Path],
    result: CVCorrectionResult,
) -> None:
    """Commits computed Core-Valence correction results atomically to landscape.h5."""
    target_path = Path(h5_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    node_group_name = result.node_id if result.node_id else "default_cv_node"

    with h5py.File(target_path, "a") as f:
        root_grp = f.require_group("cv_corrections")
        node_grp = root_grp.require_group(node_group_name)

        datasets = {
            "e_total_fc": result.e_total_fc,
            "e_total_ae": result.e_total_ae,
            "delta_e_cv_hartree": result.delta_e_cv_hartree,
            "delta_e_cv_kcal_mol": result.delta_e_cv_kcal_mol,
        }

        for ds_name, ds_val in datasets.items():
            if ds_name in node_grp:
                del node_grp[ds_name]
            node_grp.create_dataset(ds_name, data=float(ds_val))

        node_grp.attrs["basis_set"] = result.basis_set
        node_grp.attrs["original_basis_set"] = result.original_basis_set
        node_grp.attrs["method"] = result.method
        node_grp.attrs["has_core_electrons"] = bool(result.has_core_electrons)
        node_grp.attrs["timestamp"] = result.timestamp
        node_grp.attrs["node_id"] = result.node_id


def read_cv_from_hdf5(
    h5_path: Union[str, Path],
    node_id: str,
) -> Dict[str, Any]:
    """Reads back computed Core-Valence correction results from landscape.h5."""
    target_path = Path(h5_path)
    if not target_path.exists():
        raise FileNotFoundError(f"HDF5 file does not exist: {target_path}")

    with h5py.File(target_path, "r") as f:
        root_grp = f["cv_corrections"]
        node_grp = root_grp[node_id]

        data = {
            "e_total_fc": float(node_grp["e_total_fc"][()]),
            "e_total_ae": float(node_grp["e_total_ae"][()]),
            "delta_e_cv_hartree": float(node_grp["delta_e_cv_hartree"][()]),
            "delta_e_cv_kcal_mol": float(node_grp["delta_e_cv_kcal_mol"][()]),
            "basis_set": str(node_grp.attrs.get("basis_set", "")),
            "original_basis_set": str(node_grp.attrs.get("original_basis_set", "")),
            "method": str(node_grp.attrs.get("method", "")),
            "has_core_electrons": bool(node_grp.attrs.get("has_core_electrons", True)),
            "timestamp": str(node_grp.attrs.get("timestamp", "")),
            "node_id": str(node_grp.attrs.get("node_id", "")),
        }
        return data


def run_cv_pipeline(
    coords: Union[List[Tuple[str, float, float, float]], List[List[Any]]],
    e_total_fc: float,
    e_total_ae: float,
    base_basis: str = "aug-cc-pVQZ",
    method: str = "DLPNO-CCSD(T)",
    node_id: str = "node_0",
    h5_path: Optional[Union[str, Path]] = None,
    node_max_gb: float = 16.0,
    nprocs: int = 4,
) -> CVCorrectionResult:
    """End-to-end pipeline orchestrator for Stage 3.0 Core-Valence (CV) Correction."""
    # 1. Map basis set and inspect elemental core
    mapper = CoreValenceMapper()
    mapped_basis = mapper.map_basis_set(base_basis)
    core_info = mapper.inspect_elemental_core(coords)

    # 2. Extract delta and create result model
    extractor = DeltaExtractor()
    result = extractor.extract_delta(
        e_total_fc=e_total_fc,
        e_total_ae=e_total_ae,
        basis_set=mapped_basis,
        original_basis=base_basis,
        method=method,
        has_core_electrons=core_info["has_core_electrons"],
        node_id=node_id,
        metadata={"core_info": core_info},
    )

    # 3. Commit to landscape.h5 if path supplied
    if h5_path:
        commit_cv_to_hdf5(h5_path=h5_path, result=result)

    return result

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_cv.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 3.0 Core-Valence (CV) Correlation Correction Engine.

Module: tests/test_cochem_bench_cv.py
Target Implementation: bench_engine.cochem_bench_cv

Tests:
1. CoreValenceMapper:
   - Dynamic basis set mapping (cc-pV -> cc-pCV, aug-cc-pV -> aug-cc-pwCV, def2 unchanged).
   - Elemental core composition inspection using dynamic Mendeleev atomic data.
   - Core electron presence and mass calculation.
2. DualCorrelationEngine:
   - Input deck generation for Frozen-Core (FC) vs All-Electron (AE with NoFrozenCore).
   - Dynamic %maxcore RAM calculation per MPI thread.
   - Accelerator isolation injecting CUDA_VISIBLE_DEVICES="".
3. DeltaExtractor:
   - Extraction of FINAL SINGLE POINT ENERGY from authentic ORCA standard output.
   - Mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC).
   - Unit conversion from Hartree to kcal/mol via exact CODATA conversion.
4. EphemeralScratchPurge:
   - UUID-scoped tripartite scratch workspace creation.
   - Sweep and unlink of .gbw, .tmp, and ephemeral intermediate files.
   - Directory removal preventing disk and NVMe exhaustion.
5. HDF5 Persistence & Pipeline Orchestration:
   - Atomic commitment of CV correction results to landscape.h5.
   - Schema validation and roundtrip retrieval.
   - End-to-end pipeline execution.

Authoritative References:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt1_cv.md
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cv import (
    CoreValenceMapper,
    DualCorrelationEngine,
    DeltaExtractor,
    EphemeralScratchPurge,
    CVCorrectionResult,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
    HARTREE_TO_KCAL_MOL,
)


# ==============================================================================
# Authentic Molecular Test Fixtures (Angstroms)
# ==============================================================================

# Water Molecule (C2v equilibrium geometry)
WATER_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.117790),
    ("H", 0.000000, 0.755453, -0.471161),
    ("H", 0.000000, -0.755453, -0.471161),
]

# Methane (Td equilibrium geometry)
METHANE_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, 0.000000),
    ("H", 0.627600, 0.627600, 0.627600),
    ("H", -0.627600, -0.627600, 0.627600),
    ("H", -0.627600, 0.627600, -0.627600),
    ("H", 0.627600, -0.627600, -0.627600),
]

# Dihydrogen (No core electrons)
H2_COORDS: List[Tuple[str, float, float, float]] = [
    ("H", 0.000000, 0.000000, 0.370000),
    ("H", 0.000000, 0.000000, -0.370000),
]

# Carbon Monoxide (Multiple heavy atoms)
CO_COORDS: List[Tuple[str, float, float, float]] = [
    ("C", 0.000000, 0.000000, -0.645000),
    ("O", 0.000000, 0.000000, 0.485000),
]


# ==============================================================================
# Authentic ORCA 6.1.1 Output Fixtures
# ==============================================================================

ORCA_FC_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.3623851042 Eh
FINAL SINGLE POINT ENERGY      -76.3623851042
ORCA TERMINATED NORMALLY
"""

ORCA_AE_STDOUT_WATER = """
=======================================================
                   * O R C A *
       An Ab Initio, DFT and Semiempirical SCF program
=======================================================

Total Energy       :      -76.4215403210 Eh
FINAL SINGLE POINT ENERGY      -76.4215403210
ORCA TERMINATED NORMALLY
"""


# ==============================================================================
# 1. CoreValenceMapper Tests
# ==============================================================================

def test_basis_set_mapping_cc_pv() -> None:
    """Validate string mapping of standard cc-pVnZ basis sets to core-valence cc-pCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("cc-pVDZ") == "cc-pCVDZ"
    assert mapper.map_basis_set("cc-pVTZ") == "cc-pCVTZ"
    assert mapper.map_basis_set("cc-pVQZ") == "cc-pCVQZ"
    assert mapper.map_basis_set("cc-pV5Z") == "cc-pCV5Z"


def test_basis_set_mapping_aug_cc_pv() -> None:
    """Validate string mapping of augmented aug-cc-pVnZ basis sets to aug-cc-pwCVnZ."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("aug-cc-pVDZ") == "aug-cc-pwCVDZ"
    assert mapper.map_basis_set("aug-cc-pVTZ") == "aug-cc-pwCVTZ"
    assert mapper.map_basis_set("aug-cc-pVQZ") == "aug-cc-pwCVQZ"
    assert mapper.map_basis_set("aug-cc-pV5Z") == "aug-cc-pwCV5Z"


def test_basis_set_mapping_def2_and_ano() -> None:
    """Validate def2 and ano families retain their native all-electron character without mutation."""
    mapper = CoreValenceMapper()

    assert mapper.map_basis_set("def2-SVP") == "def2-SVP"
    assert mapper.map_basis_set("def2-TZVP") == "def2-TZVP"
    assert mapper.map_basis_set("def2-QZVPP") == "def2-QZVPP"
    assert mapper.map_basis_set("ano-pVTZ") == "ano-pVTZ"
    assert mapper.map_basis_set("saug-ano-pVTZ") == "saug-ano-pVTZ"


def test_elemental_core_inspection_mendeleev() -> None:
    """Validate dynamic atomic and core electron inspection using Mendeleev library."""
    mapper = CoreValenceMapper()

    # Water inspection: Oxygen (Z=8, 2 core e-), Hydrogen (Z=1, 0 core e-)
    water_info = mapper.inspect_elemental_core(WATER_COORDS)
    assert water_info["has_core_electrons"] is True
    assert water_info["total_core_electrons"] == 2
    assert "O" in water_info["elements"]
    assert "H" in water_info["elements"]

    # Verify dynamic masses
    expected_mass = float(element("O").mass) + 2.0 * float(element("H").mass)
    assert math.isclose(water_info["total_mass"], expected_mass, rel_tol=1e-5)

    # Dihydrogen inspection (No core electrons present)
    h2_info = mapper.inspect_elemental_core(H2_COORDS)
    assert h2_info["has_core_electrons"] is False
    assert h2_info["total_core_electrons"] == 0

    # Carbon Monoxide inspection: C (Z=6, 2 core), O (Z=8, 2 core) -> 4 core e-
    co_info = mapper.inspect_elemental_core(CO_COORDS)
    assert co_info["has_core_electrons"] is True
    assert co_info["total_core_electrons"] == 4


# ==============================================================================
# 2. DualCorrelationEngine Tests
# ==============================================================================

def test_dual_correlation_engine_maxcore_calculation() -> None:
    """Validate dynamic %maxcore per MPI process with safety margin."""
    engine = DualCorrelationEngine(node_max_gb=16.0, nprocs=4, ram_safety_fraction=0.75)
    maxcore = engine.calculate_maxcore_per_thread()

    # 16 GB * 1024 MB/GB * 0.75 / 4 = 3072 MB
    assert maxcore == 3072


def test_dual_correlation_input_deck_generation() -> None:
    """Validate generation of Job A (Frozen-Core) and Job B (All-Electron with NoFrozenCore)."""
    engine = DualCorrelationEngine(
        method="DLPNO-CCSD(T)",
        base_basis="aug-cc-pVQZ",
        node_max_gb=16.0,
        nprocs=4,
    )

    decks = engine.generate_input_decks(coords=WATER_COORDS, charge=0, mult=1)

    assert "fc_input" in decks
    assert "ae_input" in decks
    assert decks["basis_set"] == "aug-cc-pwCVQZ"
    assert decks["original_basis"] == "aug-cc-pVQZ"

    fc_inp = decks["fc_input"]
    ae_inp = decks["ae_input"]

    # Job A (FC) must use mapped basis and NOT contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in fc_inp
    assert "NoFrozenCore" not in fc_inp
    assert "%maxcore 3072" in fc_inp
    assert "%pal nprocs 4 end" in fc_inp
    assert "* xyz 0 1" in fc_inp

    # Job B (AE) must contain NoFrozenCore
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in ae_inp
    assert "NoFrozenCore" in ae_inp
    assert "%maxcore 3072" in ae_inp
    assert "%pal nprocs 4 end" in ae_inp
    assert "* xyz 0 1" in ae_inp


def test_cuda_accelerator_isolation_env() -> None:
    """Validate execution environment injects CUDA_VISIBLE_DEVICES='' for GPU isolation."""
    engine = DualCorrelationEngine()
    env = engine.prepare_execution_env()

    assert "CUDA_VISIBLE_DEVICES" in env
    assert env["CUDA_VISIBLE_DEVICES"] == ""


def test_dual_correlation_input_file_writing(tmp_path: Path) -> None:
    """Validate writing input decks to disk."""
    engine = DualCorrelationEngine(base_basis="cc-pVTZ")
    decks = engine.generate_input_decks(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
        output_dir=tmp_path,
    )

    fc_file = tmp_path / "orca_fc.inp"
    ae_file = tmp_path / "orca_ae.inp"

    assert fc_file.exists()
    assert ae_file.exists()
    assert "cc-pCVTZ" in fc_file.read_text(encoding="utf-8")
    assert "NoFrozenCore" in ae_file.read_text(encoding="utf-8")


# ==============================================================================
# 3. DeltaExtractor Tests
# ==============================================================================

def test_parse_final_energy_from_stdout() -> None:
    """Validate extracting FINAL SINGLE POINT ENERGY from authentic ORCA standard output."""
    extractor = DeltaExtractor()

    e_fc = extractor.parse_final_energy_from_stdout(ORCA_FC_STDOUT_WATER)
    e_ae = extractor.parse_final_energy_from_stdout(ORCA_AE_STDOUT_WATER)

    assert math.isclose(e_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(e_ae, -76.4215403210, abs_tol=1e-10)


def test_parse_final_energy_missing_raises() -> None:
    """Validate ValueError is raised when FINAL SINGLE POINT ENERGY is absent."""
    extractor = DeltaExtractor()
    invalid_stdout = "ORCA CALCULATION FAILED\nNO ENERGY REPORTED\n"

    with pytest.raises(ValueError, match="FINAL SINGLE POINT ENERGY"):
        extractor.parse_final_energy_from_stdout(invalid_stdout)


def test_delta_extractor_mathematics() -> None:
    """Validate mathematical derivation of Delta_E_CV = E_Total^(AE) - E_Total^(FC)."""
    extractor = DeltaExtractor()

    e_fc = -76.3623851042
    e_ae = -76.4215403210

    result: CVCorrectionResult = extractor.extract_delta(
        e_total_fc=e_fc,
        e_total_ae=e_ae,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_test_01",
    )

    expected_delta_hartree = e_ae - e_fc
    expected_delta_kcal = expected_delta_hartree * HARTREE_TO_KCAL_MOL

    assert math.isclose(result.delta_e_cv_hartree, expected_delta_hartree, rel_tol=1e-10)
    assert math.isclose(result.delta_e_cv_kcal_mol, expected_delta_kcal, rel_tol=1e-10)
    assert result.delta_e_cv_hartree < 0.0  # All-electron energy is lower than frozen-core
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert result.original_basis_set == "aug-cc-pVQZ"
    assert result.node_id == "water_test_01"


def test_extract_from_outputs() -> None:
    """Validate extraction directly from authentic ORCA output texts."""
    extractor = DeltaExtractor()

    result = extractor.extract_from_outputs(
        stdout_fc=ORCA_FC_STDOUT_WATER,
        stdout_ae=ORCA_AE_STDOUT_WATER,
        basis_set="aug-cc-pwCVQZ",
        original_basis="aug-cc-pVQZ",
        node_id="water_out_test",
    )

    assert math.isclose(result.e_total_fc, -76.3623851042, abs_tol=1e-10)
    assert math.isclose(result.e_total_ae, -76.4215403210, abs_tol=1e-10)
    assert math.isclose(result.delta_e_cv_hartree, -76.4215403210 - (-76.3623851042), abs_tol=1e-10)


# ==============================================================================
# 4. EphemeralScratchPurge Tests
# ==============================================================================

def test_scratch_dir_creation(tmp_path: Path) -> None:
    """Validate creation of isolated UUID-scoped scratch directory."""
    purger = EphemeralScratchPurge()
    scratch_dir = purger.create_scratch_dir(base_artifacts_dir=tmp_path)

    assert scratch_dir.exists()
    assert "BENCH_Workspace" in str(scratch_dir)
    assert "Scratch" in str(scratch_dir)
    assert "job_" in scratch_dir.name


def test_scratch_dir_purge(tmp_path: Path) -> None:
    """Validate sweep and removal of .gbw, .tmp, and intermediate scratch files."""
    purger = EphemeralScratchPurge()
    job_dir = tmp_path / "BENCH_Workspace" / "Scratch" / "job_12345"
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy simulation intermediate files
    (job_dir / "calc.gbw").write_bytes(b"BINARY_GBW_CONTENT")
    (job_dir / "calc.tmp").write_text("TMP_CONTENT", encoding="utf-8")
    (job_dir / "calc.densities").write_text("DENSITIES", encoding="utf-8")
    (job_dir / "calc.inp").write_text("! Input deck", encoding="utf-8")

    assert (job_dir / "calc.gbw").exists()
    assert (job_dir / "calc.tmp").exists()

    # Execute purge
    summary = purger.purge_scratch_dir(job_dir, remove_dir=True)

    assert summary["purged_count"] >= 2
    assert not job_dir.exists()


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Orchestration Tests
# ==============================================================================

def test_hdf5_cv_persistence(tmp_path: Path) -> None:
    """Validate atomic serialization of CV correction delta to landscape.h5."""
    h5_file = tmp_path / "landscape.h5"

    cv_result = CVCorrectionResult(
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        delta_e_cv_hartree=-0.059155,
        delta_e_cv_kcal_mol=-37.120300,
        basis_set="aug-cc-pwCVQZ",
        original_basis_set="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        has_core_electrons=True,
        node_id="water_cv_node_01",
    )

    commit_cv_to_hdf5(h5_path=h5_file, result=cv_result)
    assert h5_file.exists()

    # Read back and verify exact data integrity
    loaded = read_cv_from_hdf5(h5_path=h5_file, node_id="water_cv_node_01")

    assert math.isclose(loaded["e_total_fc"], -76.362385, abs_tol=1e-6)
    assert math.isclose(loaded["e_total_ae"], -76.421540, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_hartree"], -0.059155, abs_tol=1e-6)
    assert math.isclose(loaded["delta_e_cv_kcal_mol"], -37.120300, abs_tol=1e-6)
    assert loaded["basis_set"] == "aug-cc-pwCVQZ"
    assert loaded["original_basis_set"] == "aug-cc-pVQZ"
    assert loaded["method"] == "DLPNO-CCSD(T)"
    assert loaded["has_core_electrons"] is True
    assert loaded["node_id"] == "water_cv_node_01"


def test_run_cv_pipeline_end_to_end(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 3.0 CV pipeline orchestrator."""
    h5_file = tmp_path / "landscape.h5"

    result = run_cv_pipeline(
        coords=WATER_COORDS,
        e_total_fc=-76.362385,
        e_total_ae=-76.421540,
        base_basis="aug-cc-pVQZ",
        method="DLPNO-CCSD(T)",
        node_id="water_pipeline_01",
        h5_path=h5_file,
    )

    assert result.has_core_electrons is True
    assert result.basis_set == "aug-cc-pwCVQZ"
    assert math.isclose(result.delta_e_cv_hartree, -76.421540 - (-76.362385), abs_tol=1e-6)
    assert h5_file.exists()


def test_read_cv_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cv_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "missing_landscape.h5"
    with pytest.raises(FileNotFoundError):
        read_cv_from_hdf5(h5_path=missing_file, node_id="node_none")

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.