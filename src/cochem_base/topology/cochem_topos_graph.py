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
                    except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError) as _e:
                        logger.debug(f"Ignored exception: {_e}")
                p_obj.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                try:
                    proc.kill()
                except (ProcessLookupError, OSError) as _e:
                    logger.debug(f"Ignored exception: {_e}")


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
    elem = get_mendeleev_element(element)
    return str(elem.symbol)


@lru_cache(maxsize=256)
def get_covalent_radius(element: str | int) -> float:
    """
    Returns empirical single-bond covalent radius in Angstroms dynamically from mendeleev.
    Prioritizes Cordero et al. standard covalent radius (pm / 100), falling back to Pyykko or default.
    """
    elem = get_mendeleev_element(element)
    cov = elem.covalent_radius_cordero
    if cov is None:
        cov = elem.covalent_radius_pyykko
    if cov is None:
        cov = elem.covalent_radius
    if cov is not None:
        return round(float(cov) / 100.0, 4)
    return DEFAULT_COVALENT_RADIUS


@lru_cache(maxsize=256)
def get_atomic_mass(element: str | int) -> float:
    """Returns standard atomic weight in amu dynamically from mendeleev."""
    elem = get_mendeleev_element(element)
    mass = elem.mass
    if mass is None:
        raise ValueError(f"Could not dynamically retrieve atomic mass from mendeleev for element '{element}'")
    return float(mass)


@lru_cache(maxsize=256)
def is_transition_or_coordination_metal(element: str | int) -> bool:
    """
    Determines if an element is a transition metal, lanthanide, actinide, or coordination metal center
    capable of forming strong d-block/f-block coordination complexes.
    """
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


class _DynamicCovalentRadiiMapping(dict[Any, float]):
    """Dynamic dict-like proxy that lazily queries mendeleev for covalent radii."""
    def __getitem__(self, key: int | str) -> float:
        return get_covalent_radius(key)

    def get(self, key: int | str, default: float = DEFAULT_COVALENT_RADIUS) -> float:  # type: ignore[override]
        try:
            return get_covalent_radius(key)
        except (ValueError, KeyError):
            return default

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int | str):
            try:
                get_atomic_number(key)
                return True
            except (ValueError, KeyError):
                return False
        return False


class _DynamicAtomicWeightsMapping(dict[Any, float]):
    """Dynamic dict-like proxy that lazily queries mendeleev for atomic masses."""
    def __getitem__(self, key: int | str) -> float:
        return get_atomic_mass(key)

    def get(self, key: int | str, default: float | None = None) -> float | None:  # type: ignore[override]
        try:
            return get_atomic_mass(key)
        except (ValueError, KeyError):
            return default

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int | str):
            try:
                get_atomic_number(key)
                return True
            except (ValueError, KeyError):
                return False
        return False


COVALENT_RADII: dict[int | str, float] = _DynamicCovalentRadiiMapping()
ATOMIC_WEIGHTS: dict[int | str, float] = _DynamicAtomicWeightsMapping()


def _to_coords_array(coordinates: np.ndarray | Sequence[Sequence[float]]) -> np.ndarray:
    """Normalizes Cartesian coordinates to a typed 2D float64 NumPy array."""
    if isinstance(coordinates, np.ndarray):
        return coordinates.astype(np.float64, copy=False)
    return np.array([list(row) for row in coordinates], dtype=np.float64)


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
        arr: np.ndarray = np.array(self.coordinates, dtype=np.float64)
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
        target_ws: str | Path = workspace if workspace is not None else os.environ.get("COCHEM_WORKSPACE", str(Path.cwd()))
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
        z = get_atomic_number(element)
        if z in self.custom_radii:
            return self.custom_radii[z]
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
                    except Exception as _e:
                        logger.debug(f"Ignored exception: {_e}")
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
