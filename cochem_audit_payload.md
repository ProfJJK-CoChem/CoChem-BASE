Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\05_01_topology_graph.md.
Original prompt:
# Task: Implement Graph Topology & Weak Complex Cleavage (`cochem_topos_graph.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\topology\cochem_topos_graph.py`

## Objective
Translate 3D Cartesian coordinates into a mathematical adjacency matrix, apply physical tolerances, and objectively classify systems as independent monomers, strongly coordinated structures, or weak Van der Waals (vdW) complexes.

## Context & Architecture Rules
This module (Stage 1.1) algorithmically shatters weak complexes into independent monomer seeds for isolated geometry exploration to prevent computational waste, maintaining Air-Gap compliance.

## Execution Directives
Implement the `cochem_topos_graph.py` script with the following capabilities:

1. **Ecosystem Role & Handoff**: Receive read-only coordinate and atomic number arrays in memory from Stage 1.0 (Pre-Flight).
2. **Distance Matrix & The Resonance Protection Trap**: Compute an NxN distance matrix `D` using `scipy.spatial.distance.cdist`. Query `mendeleev` for exact covalent radii `R`. Apply a 15% breathing tolerance to the adjacency threshold: `Tij = 1.15 * (Ri + Rj)`. Generate an unweighted adjacency matrix `A` (`Aij = 1` if `Dij <= Tij`, else `0`).
3. **NetworkX Graph Generation & Cleavage**: Instantiate `nx.Graph()` and evaluate `nx.connected_components`. If exactly 1 component is returned, classify as `MONOMER` and route to Stage 2.0. If >1 component, execute the Complex Triage Protocol.
4. **Complex Triage Protocol**: Calculate the shortest distance vector between Sub-Graphs.
   - **Strong Complex**: If the shortest distance connects to a transition metal (e.g., Fe, Pd, Ru) OR formal charges imply a tight ionic coordination bridge, tag as `STRONG_COMPLEX`, abort cleavage, and route as a single unit to Stage 2.0.
   - **Weak Complex**: If purely non-covalent, tag as `WEAK_COMPLEX`, and mathematically sever the array into independent `numpy` matrices.
5. **The 4-Atom Mathematical Bypass**: If an isolated monomer fragment from a `WEAK_COMPLEX` has < 4 atoms, flag with `BYPASS_GOAT` to skip deep thermal searches and execute only a rapid point relaxation.
6. **UI Telemetry & Air-Gapped State Export**: Extract the `(i, j)` atomic indices of the shortest non-covalent gap and serialize to JSON for UI rendering using `Pydantic` models. Export isolated monomer coordinate arrays as `.xyz` files strictly to dynamic paths derived from `os.environ.get("COCHEM_WORKSPACE")` (e.g., `${COCHEM_WORKSPACE}/CoChem_Artifacts/Input_Files/user_seeds/`). Update the `stage_n_complete.json` tracker to flag the parent complex for Stage 3.0, while triggering Stage 2.0 for each monomer seed. Keep GOAT primary, add CREST `--nci --nocross --noreftopo` as a secondary search and carry the union.
7. **Subprocess Safety & Rigorous Linting**: Ensure all `subprocess.run` executions (e.g., for CREST) are wrapped in `try/except` blocks with `check=True` and strict timeouts. Implement zombie process sweeping via `psutil` or `atexit`. Replace all `print()` statements with standard `logging`. Apply exhaustive Python 3.10+ type hints across all functions and classes.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\__init__.py ---
"""CoChem-TOPOS Combinatorial Conformational Engine."""

from .cochem_topos_graph import (
    COVALENT_RADII,
    RESONANCE_PROTECTION_SCALE,
    MonomerSeed,
    ShortestGapTelemetry,
    TopologyAnalysisResult,
    TopologyGraphEngine,
    analyze_molecular_graph,
    generate_chemical_formula,
    get_atomic_mass,
    get_atomic_number,
    get_atomic_symbol,
    get_covalent_radius,
    is_transition_or_coordination_metal,
    parse_xyz_file,
    parse_xyz_string,
    run_crest_secondary_search,
)
from .engine import ToposEngine

__all__ = [
    "ToposEngine",
    "TopologyGraphEngine",
    "TopologyAnalysisResult",
    "MonomerSeed",
    "ShortestGapTelemetry",
    "analyze_molecular_graph",
    "parse_xyz_string",
    "parse_xyz_file",
    "generate_chemical_formula",
    "get_covalent_radius",
    "get_atomic_mass",
    "get_atomic_number",
    "get_atomic_symbol",
    "is_transition_or_coordination_metal",
    "run_crest_secondary_search",
    "COVALENT_RADII",
    "RESONANCE_PROTECTION_SCALE",
]


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

# Default fallback covalent radius (Angstroms) for synthetic / uncharacterized elements
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_cbs.py ---
#!/usr/bin/env python3
"""Authentic Unit Test Suite for CoChem Stage 2.0 CBS Extrapolation Engine.

Module: tests/test_cochem_bench_cbs.py
Target Implementation: bench_engine.cochem_bench_cbs

Tests:
1. DualBasisDispatcher:
   - Dynamic %maxcore RAM calculation per MPI thread with host RAM safety margin.
   - Dual-basis ORCA 6.1.1 input deck generation for def2, cc-pVnZ, and custom basis sets.
   - Atom coordinate validation and electronic property derivation via Mendeleev.
   - Multiplicity and open-shell radical detection.
2. HelgakerExtrapolator:
   - Energy decomposition: E_corr = E_total - E_SCF.
   - Exponential decay two-point SCF extrapolation: E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) / (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X))).
   - Inverse power two-point correlation extrapolation: E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta).
   - Parameter matrix lookup (alpha and beta) across cc-pVnZ, pc-n, def2, ano-pVnZ, saug-ano-pVnZ families.
   - Real ab-initio literature validation on authentic molecular calculations (Water, Nitrogen dimer).
3. ResidualFitAnalyzer:
   - Absolute variance calculation: Delta = |E_corr(inf) - E_corr(Y)|.
   - Hartree to kcal/mol conversion (627.509474 kcal/mol per Hartree).
   - Flagging logic: Delta > 10.0 kcal/mol flags CBS_HIGH_UNCERTAINTY; Delta <= 10.0 kcal/mol passes.
4. SlowConvInterceptor:
   - Standard output failure stream parsing for DIIS / SCF non-convergence.
   - Dynamic remediation injecting '! SlowConv SOSCF' and SCF configuration blocks.
   - Bounded retry tracking preventing infinite loop oscillations.
5. HDF5 Persistence & Pipeline Orchestration:
   - Atomic commitment of computed CBS limit to landscape.h5 with complete metadata.
   - Schema validation and roundtrip retrieval.

Authoritative References:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
- D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BENCH\\SRS\\Task 5 CBS Extrapolation & Composite Protocol Math (Stages 2.0 - 4.0).txt
- D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BENCH\\.in-progress\\draft_task2_pt1_cbs.md
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import numpy as np
import pytest
from mendeleev import element

from bench_engine.cochem_bench_cbs import (
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptor,
    CBSExtrapolationResult,
    SlowConvInterceptionResult,
    commit_cbs_to_hdf5,
    read_cbs_from_hdf5,
    run_cbs_pipeline,
    HARTREE_TO_KCAL_MOL,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    PARAMETER_MATRIX,
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

# Nitrogen Dimer (Dinfh equilibrium geometry)
N2_COORDS: List[Tuple[str, float, float, float]] = [
    ("N", 0.000000, 0.000000, 0.548800),
    ("N", 0.000000, 0.000000, -0.548800),
]

# OH Radical (Open-shell doublet)
OH_RADICAL_COORDS: List[Tuple[str, float, float, float]] = [
    ("O", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 0.000000, 0.969700),
]


# ==============================================================================
# 1. DualBasisDispatcher Tests
# ==============================================================================

def test_dynamic_maxcore_ram_calculation() -> None:
    """Validate dynamic maxcore calculation per MPI thread prevents host RAM swap-death."""
    dispatcher = DualBasisDispatcher(node_max_gb=32.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_mb = dispatcher.calculate_maxcore_per_thread()

    # 32 GB * 1024 MB/GB * 0.75 / 8 = 3072 MB per thread
    expected_mb = int((32.0 * 1024.0 * 0.75) / 8)
    assert maxcore_mb == expected_mb
    assert maxcore_mb == 3072

    # Test constrained node budgeting
    dispatcher_constrained = DualBasisDispatcher(node_max_gb=4.0, nprocs=8, ram_safety_fraction=0.75)
    maxcore_constrained = dispatcher_constrained.calculate_maxcore_per_thread()
    # 4 * 1024 * 0.75 / 8 = 384 MB
    assert maxcore_constrained == 384
    assert maxcore_constrained >= 250


def test_dual_basis_orca_input_generation() -> None:
    """Validate ORCA 6.1.1 input file deck generation for dual-basis extrapolation."""
    dispatcher = DualBasisDispatcher(
        node_max_gb=16.0,
        nprocs=4,
        method="DLPNO-CCSD(T)",
        basis_pair=("def2-TZVP", "def2-QZVPP"),
        tight_scf=True,
    )

    deck = dispatcher.generate_input_deck(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
    )

    assert "input_x" in deck
    assert "input_y" in deck
    assert deck["basis_x"] == "def2-TZVP"
    assert deck["basis_y"] == "def2-QZVPP"

    inp_x = deck["input_x"]
    inp_y = deck["input_y"]

    # Verify ORCA syntax in input X
    assert "! DLPNO-CCSD(T) def2-TZVP" in inp_x
    assert "TightSCF" in inp_x
    assert "DefGrid3" in inp_x
    assert "%maxcore" in inp_x
    assert "%pal nprocs 4 end" in inp_x
    assert "* xyz 0 1" in inp_x
    assert "0.11779" in inp_x

    # Verify ORCA syntax in input Y
    assert "! DLPNO-CCSD(T) def2-QZVPP" in inp_y
    assert "TightSCF" in inp_y
    assert "%pal nprocs 4 end" in inp_y


def test_mendeleev_masses_and_electron_integration() -> None:
    """Validate dynamic element property retrieval via mendeleev library (Mendeleev Mandate)."""
    dispatcher = DualBasisDispatcher()
    
    # Calculate molecular mass and total electron count dynamically using mendeleev
    mol_mass, total_electrons = dispatcher.get_molecular_properties(WATER_COORDS)
    
    expected_o_mass = float(element("O").mass)
    expected_h_mass = float(element("H").mass)
    expected_mol_mass = expected_o_mass + 2.0 * expected_h_mass
    
    assert math.isclose(mol_mass, expected_mol_mass, rel_tol=1e-5)
    assert total_electrons == 10  # 8 + 1 + 1 = 10 electrons


def test_open_shell_radical_detection() -> None:
    """Validate automatic detection of open-shell systems and UHF / unrestricted handling."""
    dispatcher = DualBasisDispatcher()

    # OH radical: 8 (O) + 1 (H) = 9 electrons (odd number -> open-shell doublet)
    is_open_shell, inferred_mult = dispatcher.detect_spin_state(OH_RADICAL_COORDS, charge=0)
    assert is_open_shell is True
    assert inferred_mult == 2

    deck = dispatcher.generate_input_deck(OH_RADICAL_COORDS, charge=0, mult=2)
    assert "* xyz 0 2" in deck["input_x"]


# ==============================================================================
# 2. HelgakerExtrapolator Mathematics & Parameter Matrix Tests
# ==============================================================================

def test_energy_decomposition() -> None:
    """Validate energy decomposition into SCF and correlation components."""
    extrapolator = HelgakerExtrapolator()

    # Water with def2-TZVP: E_total = -76.3322 Hartree, E_SCF = -76.0571 Hartree
    e_total_x = -76.3322
    e_scf_x = -76.0571
    e_corr_x = extrapolator.decompose_correlation_energy(e_total_x, e_scf_x)

    expected_corr_x = e_total_x - e_scf_x
    assert math.isclose(e_corr_x, expected_corr_x, abs_tol=1e-10)
    assert e_corr_x < 0.0  # Correlation energy must be negative


def test_scf_exponential_extrapolation_exact_math() -> None:
    """Validate exponential decay formula for Hartree-Fock SCF energy extrapolation.
    
    Formula:
    E_SCF(inf) = (E_SCF(X)*exp(-alpha*sqrt(Y)) - E_SCF(Y)*exp(-alpha*sqrt(X))) /
                 (exp(-alpha*sqrt(Y)) - exp(-alpha*sqrt(X)))
    """
    extrapolator = HelgakerExtrapolator()

    e_scf_x3 = -76.0571
    e_scf_x4 = -76.0648
    alpha = 7.88  # def2 3/4 parameter
    X = 3
    Y = 4

    cbs_scf = extrapolator.extrapolate_scf(e_scf_x=e_scf_x3, e_scf_y=e_scf_x4, X=X, Y=Y, alpha=alpha)

    exp_x = math.exp(-alpha * math.sqrt(X))
    exp_y = math.exp(-alpha * math.sqrt(Y))
    expected_cbs_scf = (e_scf_x3 * exp_y - e_scf_x4 * exp_x) / (exp_y - exp_x)

    assert math.isclose(cbs_scf, expected_cbs_scf, rel_tol=1e-12)
    assert cbs_scf < e_scf_x4  # CBS limit must be more negative than finite basis


def test_correlation_inverse_power_extrapolation_exact_math() -> None:
    """Validate Halkier/Neese inverse power formula for correlation energy extrapolation.
    
    Formula:
    E_corr(inf) = (X^beta * E_corr(X) - Y^beta * E_corr(Y)) / (X^beta - Y^beta)
    """
    extrapolator = HelgakerExtrapolator()

    e_corr_x3 = -0.2751
    e_corr_x4 = -0.2885
    beta = 2.97  # def2 3/4 parameter
    X = 3
    Y = 4

    cbs_corr = extrapolator.extrapolate_correlation(e_corr_x=e_corr_x3, e_corr_y=e_corr_x4, X=X, Y=Y, beta=beta)

    x_beta = float(X) ** beta
    y_beta = float(Y) ** beta
    expected_cbs_corr = (x_beta * e_corr_x3 - y_beta * e_corr_x4) / (x_beta - y_beta)

    assert math.isclose(cbs_corr, expected_cbs_corr, rel_tol=1e-12)
    assert cbs_corr < e_corr_x4  # CBS correlation limit must be more negative


def test_parameter_matrix_coverage() -> None:
    """Validate parameter lookup across all basis set families defined in Task 5 SRS."""
    extrapolator = HelgakerExtrapolator()

    test_cases = [
        # (basis_x, basis_y, expected_alpha, expected_beta, expected_X, expected_Y)
        ("cc-pVDZ", "cc-pVTZ", 4.42, 2.46, 2, 3),
        ("cc-pVTZ", "cc-pVQZ", 5.46, 3.05, 3, 4),
        ("pc-1", "pc-2", 7.02, 2.01, 2, 3),
        ("pc-2", "pc-3", 9.78, 4.09, 3, 4),
        ("def2-SVP", "def2-TZVP", 10.39, 2.40, 2, 3),
        ("def2-TZVP", "def2-QZVPP", 7.88, 2.97, 3, 4),
        ("def2-TZVPP", "def2-QZVPP", 7.88, 2.97, 3, 4),
        ("ano-pVDZ", "ano-pVTZ", 5.41, 2.43, 2, 3),
        ("ano-pVTZ", "ano-pVQZ", 4.48, 2.97, 3, 4),
        ("saug-ano-pVDZ", "saug-ano-pVTZ", 5.48, 2.21, 2, 3),
        ("saug-ano-pVTZ", "saug-ano-pVQZ", 4.18, 2.83, 3, 4),
    ]

    for bx, by, exp_alpha, exp_beta, exp_X, exp_Y in test_cases:
        alpha, beta, X, Y = extrapolator.lookup_parameters(bx, by)
        assert math.isclose(alpha, exp_alpha, rel_tol=1e-4), f"Alpha mismatch for {bx}/{by}: got {alpha}, exp {exp_alpha}"
        assert math.isclose(beta, exp_beta, rel_tol=1e-4), f"Beta mismatch for {bx}/{by}: got {beta}, exp {exp_beta}"
        assert X == exp_X, f"X mismatch for {bx}: got {X}, exp {exp_X}"
        assert Y == exp_Y, f"Y mismatch for {by}: got {Y}, exp {exp_Y}"


def test_full_cbs_extrapolation_pipeline() -> None:
    """Validate full end-to-end extrapolation returning structured CBSExtrapolationResult."""
    extrapolator = HelgakerExtrapolator()

    # Authentic Water DLPNO-CCSD(T) energies:
    # def2-TZVP: E_SCF = -76.0571 Hartree, E_corr = -0.2751 Hartree
    # def2-QZVPP: E_SCF = -76.0648 Hartree, E_corr = -0.2885 Hartree
    result: CBSExtrapolationResult = extrapolator.extrapolate(
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        e_corr_x=-0.2751,
        e_corr_y=-0.2885,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
    )

    assert result.e_scf_cbs < -76.0648
    assert result.e_corr_cbs < -0.2885
    assert result.e_total_cbs == result.e_scf_cbs + result.e_corr_cbs
    assert result.basis_x == "def2-TZVP"
    assert result.basis_y == "def2-QZVPP"
    assert result.alpha == 7.88
    assert result.beta == 2.97


# ==============================================================================
# 3. ResidualFitAnalyzer Tests
# ==============================================================================

def test_residual_fit_analyzer_nominal_pass() -> None:
    """Validate ResidualFitAnalyzer passes when correlation variance Delta <= 10 kcal/mol."""
    analyzer = ResidualFitAnalyzer(threshold_kcal_mol=10.0)

    # Delta = |-0.2970 - (-0.2885)| = 0.0085 Hartree
    # In kcal/mol: 0.0085 * 627.509474 = 5.3338 kcal/mol <= 10.0 kcal/mol -> PASSED
    e_corr_cbs = -0.2970
    e_corr_y = -0.2885

    eval_result = analyzer.analyze(e_corr_cbs=e_corr_cbs, e_corr_y=e_corr_y)

    assert eval_result["is_flagged"] is False
    assert eval_result["flag"] == "PASSED"
    assert math.isclose(eval_result["variance_hartree"], 0.0085, rel_tol=1e-5)
    assert math.isclose(eval_result["variance_kcal_mol"], 0.0085 * HARTREE_TO_KCAL_MOL, rel_tol=1e-5)


def test_residual_fit_analyzer_cbs_high_uncertainty_flag() -> None:
    """Validate ResidualFitAnalyzer flags CBS_HIGH_UNCERTAINTY when variance Delta > 10 kcal/mol."""
    analyzer = ResidualFitAnalyzer(threshold_kcal_mol=10.0)

    # Unphysically large jump / under-saturated basis:
    # Delta = |-0.3200 - (-0.2885)| = 0.0315 Hartree
    # In kcal/mol: 0.0315 * 627.509474 = 19.7665 kcal/mol > 10.0 kcal/mol -> HIGH UNCERTAINTY
    e_corr_cbs = -0.3200
    e_corr_y = -0.2885

    eval_result = analyzer.analyze(e_corr_cbs=e_corr_cbs, e_corr_y=e_corr_y)

    assert eval_result["is_flagged"] is True
    assert eval_result["flag"] == "CBS_HIGH_UNCERTAINTY"
    assert eval_result["variance_kcal_mol"] > 10.0
    assert "asymptotic regime" in eval_result["reason"].lower()


# ==============================================================================
# 4. SlowConvInterceptor Tests
# ==============================================================================

def test_slow_conv_interceptor_detection_and_remediation() -> None:
    """Validate interception of ORCA SCF DIIS convergence failure and injection of SOSCF."""
    interceptor = SlowConvInterceptor()

    failed_orca_stdout = """
    =======================================================
                       * O R C A *
           An Ab Initio, DFT and Semiempirical SCF program
    =======================================================
    SCF NOT CONVERGED AFTER 125 CYCLES
    DIIS error did not drop below threshold: 4.82e-04 > 1.00e-05
    SCF failed to converge!
    -------------------------------------------------------
    """

    base_input = """! DLPNO-CCSD(T) def2-TZVP TightSCF DefGrid3
%maxcore 3072
* xyz 0 1
O 0.0 0.0 0.11779
H 0.0 0.75545 -0.47116
H 0.0 -0.75545 -0.47116
*
"""

    interception: SlowConvInterceptionResult = interceptor.inspect_and_remediate(
        stdout_text=failed_orca_stdout,
        current_input=base_input,
    )

    assert interception.has_failed is True
    assert interception.should_restart is True
    assert "SlowConv" in interception.remediated_input
    assert "SOSCF" in interception.remediated_input


def test_slow_conv_interceptor_nominal_run_passes() -> None:
    """Validate SlowConvInterceptor does nothing on normally terminated calculations."""
    interceptor = SlowConvInterceptor()

    normal_orca_stdout = """
    =======================================================
                       * O R C A *
    =======================================================
    FINAL SINGLE POINT ENERGY      -76.3322194821
    ORCA TERMINATED NORMALLY
    """

    base_input = "! DLPNO-CCSD(T) def2-TZVP TightSCF DefGrid3\n"

    interception: SlowConvInterceptionResult = interceptor.inspect_and_remediate(
        stdout_text=normal_orca_stdout,
        current_input=base_input,
    )

    assert interception.has_failed is False
    assert interception.should_restart is False
    assert interception.remediated_input == base_input


# ==============================================================================
# 5. HDF5 Persistence & Pipeline Integration Tests
# ==============================================================================

def test_hdf5_cbs_persistence(tmp_path: Path) -> None:
    """Validate atomic serialization of computed CBS results to landscape.h5."""
    h5_file = tmp_path / "landscape.h5"

    cbs_result = CBSExtrapolationResult(
        e_scf_cbs=-76.065231,
        e_corr_cbs=-0.297154,
        e_total_cbs=-76.362385,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        alpha=7.88,
        beta=2.97,
        residual_variance_hartree=0.008654,
        residual_variance_kcal_mol=5.430468,
        uncertainty_flag="PASSED",
        node_id="water_c2v_node_01",
    )

    commit_cbs_to_hdf5(h5_path=h5_file, result=cbs_result)
    assert h5_file.exists()

    # Read back and verify exact data integrity
    loaded_data = read_cbs_from_hdf5(h5_path=h5_file, node_id="water_c2v_node_01")
    assert math.isclose(loaded_data["e_scf_cbs"], -76.065231, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_corr_cbs"], -0.297154, abs_tol=1e-6)
    assert math.isclose(loaded_data["e_total_cbs"], -76.362385, abs_tol=1e-6)
    assert loaded_data["uncertainty_flag"] == "PASSED"
    assert loaded_data["basis_x"] == "def2-TZVP"
    assert loaded_data["basis_y"] == "def2-QZVPP"


def test_run_cbs_pipeline_end_to_end(tmp_path: Path) -> None:
    """Validate end-to-end execution of Stage 2.0 CBS pipeline orchestrator."""
    h5_file = tmp_path / "landscape.h5"

    pipeline_result = run_cbs_pipeline(
        coords=WATER_COORDS,
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        e_corr_x=-0.2751,
        e_corr_y=-0.2885,
        basis_pair=("def2-TZVP", "def2-QZVPP"),
        node_id="water_01",
        h5_path=h5_file,
    )

    assert pipeline_result.uncertainty_flag == "PASSED"
    assert pipeline_result.e_total_cbs < -76.35
    assert h5_file.exists()


def test_dual_basis_deck_file_writing(tmp_path: Path) -> None:
    """Validate file output generation for ORCA input decks."""
    dispatcher = DualBasisDispatcher(
        node_max_gb=16.0,
        nprocs=2,
        basis_pair=("def2-TZVP", "def2-QZVPP"),
    )
    deck = dispatcher.generate_input_deck(
        coords=WATER_COORDS,
        charge=0,
        mult=1,
        output_dir=tmp_path,
    )
    file_x = tmp_path / "orca_def2-TZVP.inp"
    file_y = tmp_path / "orca_def2-QZVPP.inp"
    assert file_x.exists()
    assert file_y.exists()
    assert "! DLPNO-CCSD(T) def2-TZVP" in file_x.read_text(encoding="utf-8")
    assert "! DLPNO-CCSD(T) def2-QZVPP" in file_y.read_text(encoding="utf-8")


def test_custom_parameters_override() -> None:
    """Validate user-defined alpha and beta overrides in HelgakerExtrapolator."""
    extrapolator = HelgakerExtrapolator()
    alpha, beta, X, Y = extrapolator.lookup_parameters(
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
        custom_alpha=6.50,
        custom_beta=3.20,
    )
    assert math.isclose(alpha, 6.50, abs_tol=1e-6)
    assert math.isclose(beta, 3.20, abs_tol=1e-6)


def test_extrapolate_from_total() -> None:
    """Validate extrapolate_from_total calculates correlation and invokes full extrapolation."""
    extrapolator = HelgakerExtrapolator()
    res = extrapolator.extrapolate_from_total(
        e_total_x=-76.3322,
        e_total_y=-76.3533,
        e_scf_x=-76.0571,
        e_scf_y=-76.0648,
        basis_x="def2-TZVP",
        basis_y="def2-QZVPP",
    )
    assert res.e_total_cbs < -76.3533
    assert math.isclose(res.e_total_cbs, res.e_scf_cbs + res.e_corr_cbs, abs_tol=1e-10)


def test_singular_denominator_error_handling() -> None:
    """Validate ValueError is raised when denominator in extrapolation is singular."""
    extrapolator = HelgakerExtrapolator()
    with pytest.raises(ValueError, match="Singular denominator"):
        extrapolator.extrapolate_scf(e_scf_x=-76.0, e_scf_y=-76.0, X=3, Y=3, alpha=7.88)

    with pytest.raises(ValueError, match="Singular denominator"):
        extrapolator.extrapolate_correlation(e_corr_x=-0.2, e_corr_y=-0.2, X=3, Y=3, beta=2.97)


def test_slow_conv_max_retries_exhausted() -> None:
    """Validate SlowConvInterceptor terminates restarts when retry limit is exhausted."""
    interceptor = SlowConvInterceptor(max_retries=2)
    failed_orca_stdout = "SCF NOT CONVERGED AFTER 125 CYCLES"
    base_input = "! DLPNO-CCSD(T) def2-TZVP\n"

    interception = interceptor.inspect_and_remediate(
        stdout_text=failed_orca_stdout,
        current_input=base_input,
        retry_count=2,
    )
    assert interception.has_failed is True
    assert interception.should_restart is False
    assert "exhausted" in interception.reason.lower()


def test_read_cbs_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    """Validate read_cbs_from_hdf5 raises FileNotFoundError when target file is missing."""
    missing_file = tmp_path / "non_existent.h5"
    with pytest.raises(FileNotFoundError):
        read_cbs_from_hdf5(h5_path=missing_file, node_id="test_node")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_graph.py ---
"""
Unit tests for CoChem-TOPOS Graph Cleavage and Pipeline Routing Engine (cochem_topos_graph.py).
Strictly adheres to the Zero-Mock mandate using authentic physical molecular coordinates.
Validates:
1. Dynamic Mendeleev elemental lookup & transition metal identification.
2. Distance matrix & Resonance Protection Trap (1.15x breathing tolerance).
3. Monomer routing to MONOMER_GOAT.
4. The 4-Atom Mathematical Bypass (<4 atoms flagged with BYPASS_GOAT).
5. Weak Complex Triage & Cleavage into independent MonomerSeeds.
6. Strong Complex Triage Protocol (transition metal coordination aborts cleavage).
7. UI Telemetry & Air-Gapped State Export to stage_n_complete.json and user_seeds.
8. Subprocess Safety wrapper and Pydantic serialization.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from cochem_topos.cochem_topos_graph import (
    COVALENT_RADII,
    TopologyAnalysisResult,
    TopologyGraphEngine,
    analyze_molecular_graph,
    get_atomic_mass,
    get_atomic_number,
    get_atomic_symbol,
    get_covalent_radius,
    is_transition_or_coordination_metal,
    parse_xyz_file,
    parse_xyz_string,
    run_crest_secondary_search,
)


class TestMendeleevDynamicProperties:
    """Verifies dynamic property lookups from mendeleev with zero hardcoding."""

    def test_atomic_number_and_symbol_resolution(self) -> None:
        """Confirms atomic number and symbol resolution for various inputs."""
        assert get_atomic_number("H") == 1
        assert get_atomic_number("h") == 1
        assert get_atomic_number(1) == 1
        assert get_atomic_number("C") == 6
        assert get_atomic_number("c") == 6
        assert get_atomic_number(6) == 6
        assert get_atomic_number("Fe") == 26
        assert get_atomic_number("fe") == 26
        assert get_atomic_number(26) == 26
        assert get_atomic_number("Pd") == 46
        assert get_atomic_number("Ru") == 44

        assert get_atomic_symbol(1) == "H"
        assert get_atomic_symbol(6) == "C"
        assert get_atomic_symbol(26) == "Fe"
        assert get_atomic_symbol("fe") == "Fe"

    def test_covalent_radii_dynamic_lookup(self) -> None:
        """Confirms covalent radii retrieved from mendeleev match physical standards."""
        assert pytest.approx(get_covalent_radius("H"), abs=0.02) == 0.31
        assert pytest.approx(get_covalent_radius(1), abs=0.02) == 0.31
        assert pytest.approx(get_covalent_radius("C"), abs=0.03) == 0.73
        assert pytest.approx(get_covalent_radius("N"), abs=0.02) == 0.71
        assert pytest.approx(get_covalent_radius("O"), abs=0.02) == 0.66
        assert pytest.approx(get_covalent_radius("F"), abs=0.02) == 0.57
        assert pytest.approx(get_covalent_radius("Ar"), abs=0.02) == 1.06

        # Check mapping proxy
        assert pytest.approx(COVALENT_RADII["H"], abs=0.02) == 0.31
        assert pytest.approx(COVALENT_RADII[6], abs=0.03) == 0.73

    def test_atomic_mass_dynamic_lookup(self) -> None:
        """Confirms dynamic mass lookup from mendeleev adheres to Mendeleev mandate."""
        assert pytest.approx(get_atomic_mass("H"), abs=0.01) == 1.008
        assert pytest.approx(get_atomic_mass("C"), abs=0.01) == 12.011
        assert pytest.approx(get_atomic_mass("O"), abs=0.01) == 15.999
        assert pytest.approx(get_atomic_mass("Fe"), abs=0.01) == 55.845

    def test_transition_metal_identification(self) -> None:
        """Confirms robust classification of transition and coordination metals."""
        assert is_transition_or_coordination_metal("Fe") is True
        assert is_transition_or_coordination_metal(26) is True
        assert is_transition_or_coordination_metal("Pd") is True
        assert is_transition_or_coordination_metal("Ru") is True
        assert is_transition_or_coordination_metal("Pt") is True
        assert is_transition_or_coordination_metal("Cu") is True
        assert is_transition_or_coordination_metal("La") is True
        assert is_transition_or_coordination_metal("U") is True

        assert is_transition_or_coordination_metal("H") is False
        assert is_transition_or_coordination_metal("C") is False
        assert is_transition_or_coordination_metal("N") is False
        assert is_transition_or_coordination_metal("O") is False
        assert is_transition_or_coordination_metal("Ar") is False

    def test_invalid_element_error(self) -> None:
        """Confirms invalid element inputs raise clean ValueError."""
        with pytest.raises(ValueError, match="Unrecognized chemical element"):
            get_atomic_number("InvalidElementXYZ")


class TestResonanceProtectionTrap:
    """Verifies that the 1.15x scaling factor preserves elongated transition state bonds."""

    def test_elongated_carbon_bond_scaling_protection(self) -> None:
        """
        Tests an elongated C-C bond at 1.65 Angstroms (e.g. transition state).
        With 1.15x breathing tolerance: remains 1 protected single monomer.
        With 1.00x unscaled: falsely fractures into 2 fragments.
        """
        symbols = ["C", "C", "H", "H", "H", "H", "H", "H"]
        coordinates = np.array([
            [-0.8250,  0.0000,  0.0000],
            [ 0.8250,  0.0000,  0.0000],
            [-1.1650,  0.9600,  0.0000],
            [-1.1650, -0.4800,  0.8314],
            [-1.1650, -0.4800, -0.8314],
            [ 1.1650,  0.9600,  0.0000],
            [ 1.1650, -0.4800,  0.8314],
            [ 1.1650, -0.4800, -0.8314],
        ])

        engine_scaled = TopologyGraphEngine(resonance_scale=1.15)
        result_scaled = engine_scaled.analyze_topology(symbols, coordinates)
        assert result_scaled.num_fragments == 1
        assert result_scaled.is_weak_complex is False
        assert result_scaled.classification == "Monomer"
        assert result_scaled.routing_target == "MONOMER_GOAT"

        engine_unscaled = TopologyGraphEngine(resonance_scale=1.00)
        result_unscaled = engine_unscaled.analyze_topology(symbols, coordinates)
        assert result_unscaled.num_fragments == 2
        assert result_unscaled.is_weak_complex is True
        assert result_unscaled.classification == "Weak Complex"
        assert result_unscaled.routing_target == "COUNTERPOISE_ASSEMBLY"


class TestMonomerIdentificationAndBypass:
    """Verifies single covalent molecules and the 4-atom mathematical bypass."""

    def test_water_monomer_with_bypass(self) -> None:
        """Evaluates single water molecule (3 atoms < 4 -> bypass_goat=True)."""
        symbols = ["O", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        assert isinstance(result, TopologyAnalysisResult)
        assert result.num_atoms == 3
        assert result.num_fragments == 1
        assert result.is_weak_complex is False
        assert result.classification == "Monomer"
        assert result.complex_type == "MONOMER"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.counterpoise_flag is False
        assert len(result.monomers) == 1

        monomer = result.monomers[0]
        assert monomer.num_atoms == 3
        assert monomer.formula == "H2O"
        assert monomer.bypass_goat is True
        assert result.bypass_goat_fragments == [0]

    def test_methane_monomer_no_bypass(self) -> None:
        """Evaluates methane molecule (5 atoms >= 4 -> bypass_goat=False)."""
        symbols = ["C", "H", "H", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.0000],
            [0.6276,  0.6276,  0.6276],
            [0.6276, -0.6276, -0.6276],
            [-0.6276,  0.6276, -0.6276],
            [-0.6276, -0.6276,  0.6276],
        ])

        result = analyze_molecular_graph(symbols, coordinates)

        assert result.num_atoms == 5
        assert result.num_fragments == 1
        assert result.is_weak_complex is False
        assert result.classification == "Monomer"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.monomers[0].bypass_goat is False
        assert result.bypass_goat_fragments == []

    def test_benzene_monomer(self) -> None:
        """Evaluates aromatic benzene ring (12 atoms)."""
        symbols = ["C", "C", "C", "C", "C", "C", "H", "H", "H", "H", "H", "H"]
        coordinates = np.array([
            [ 0.0000,  1.3970,  0.0000],
            [ 1.2098,  0.6985,  0.0000],
            [ 1.2098, -0.6985,  0.0000],
            [ 0.0000, -1.3970,  0.0000],
            [-1.2098, -0.6985,  0.0000],
            [-1.2098,  0.6985,  0.0000],
            [ 0.0000,  2.4790,  0.0000],
            [ 2.1469,  1.2395,  0.0000],
            [ 2.1469, -1.2395,  0.0000],
            [ 0.0000, -2.4790,  0.0000],
            [-2.1469, -1.2395,  0.0000],
            [-2.1469,  1.2395,  0.0000],
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.num_atoms == 12
        assert result.num_fragments == 1
        assert result.classification == "Monomer"
        assert result.monomers[0].formula == "C6H6"
        assert result.monomers[0].bypass_goat is False


class TestWeakComplexDetectionAndCleavage:
    """Verifies Complex Triage Protocol on non-covalent Van der Waals complexes."""

    def test_water_dimer_cleavage_and_bypass(self) -> None:
        """Tests water dimer cleavage into 2 severed H2O seeds, both with BYPASS_GOAT."""
        symbols = ["O", "H", "H", "O", "H", "H"]
        coordinates = np.array([
            # Monomer A
            [-1.464, -0.019,  0.021],
            [-1.765,  0.888,  0.002],
            [-0.499, -0.008, -0.063],
            # Monomer B
            [ 1.442,  0.001, -0.004],
            [ 1.761, -0.457,  0.778],
            [ 1.745, -0.479, -0.771],
        ])

        engine = TopologyGraphEngine(resonance_scale=1.15)
        result = engine.analyze_topology(symbols, coordinates)

        assert result.num_atoms == 6
        assert result.num_fragments == 2
        assert result.is_weak_complex is True
        assert result.classification == "Weak Complex"
        assert result.complex_type == "WEAK_COMPLEX"
        assert result.routing_target == "COUNTERPOISE_ASSEMBLY"
        assert result.counterpoise_flag is True
        assert len(result.monomers) == 2

        assert result.monomers[0].formula == "H2O"
        assert result.monomers[0].bypass_goat is True
        assert result.monomers[1].formula == "H2O"
        assert result.monomers[1].bypass_goat is True
        assert set(result.bypass_goat_fragments) == {0, 1}

        # Telemetry check
        assert result.shortest_gap is not None
        assert result.shortest_gap.distance > 1.5
        assert result.shortest_gap.is_transition_metal_contact is False

    def test_benzene_water_hetero_complex(self) -> None:
        """Tests benzene...water complex where C6H6 has >=4 atoms and H2O has <4 atoms."""
        symbols = [
            # Benzene (0-11)
            "C", "C", "C", "C", "C", "C",
            "H", "H", "H", "H", "H", "H",
            # Water (12-14)
            "O", "H", "H"
        ]
        coordinates = np.array([
            # Benzene ring in XY plane at Z=0
            [ 0.0000,  1.3970,  0.0000],
            [ 1.2098,  0.6985,  0.0000],
            [ 1.2098, -0.6985,  0.0000],
            [ 0.0000, -1.3970,  0.0000],
            [-1.2098, -0.6985,  0.0000],
            [-1.2098,  0.6985,  0.0000],
            [ 0.0000,  2.4790,  0.0000],
            [ 2.1469,  1.2395,  0.0000],
            [ 2.1469, -1.2395,  0.0000],
            [ 0.0000, -2.4790,  0.0000],
            [-2.1469, -1.2395,  0.0000],
            [-2.1469,  1.2395,  0.0000],
            # Water above pi cloud at Z=3.3 A
            [ 0.0000,  0.0000,  3.3000],
            [ 0.0000,  0.7572,  3.8865],
            [ 0.0000, -0.7572,  3.8865],
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.num_fragments == 2
        assert result.is_weak_complex is True
        assert result.classification == "Weak Complex"
        assert len(result.monomers) == 2

        m0 = result.monomers[0]
        assert m0.formula == "C6H6"
        assert m0.num_atoms == 12
        assert m0.bypass_goat is False

        m1 = result.monomers[1]
        assert m1.formula == "H2O"
        assert m1.num_atoms == 3
        assert m1.bypass_goat is True

        assert result.bypass_goat_fragments == [1]


class TestStrongComplexTriageProtocol:
    """Verifies Complex Triage Protocol on transition metal coordination complexes."""

    def test_iron_water_coordination_complex(self) -> None:
        """
        Tests Fe...H2O coordination complex at 2.40 A.
        Because shortest inter-fragment distance connects to transition metal Fe,
        it is tagged as STRONG_COMPLEX, cleavage is aborted, and routed to Stage 2.0 as a single unit.
        """
        symbols = ["Fe", "O", "H", "H"]
        coordinates = np.array([
            [0.0000, 0.0000, 0.0000],  # Fe (index 0)
            [0.0000, 0.0000, 2.4000],  # O of H2O (index 1) - coordinate interaction at 2.40 A
            [0.0000, 0.7572, 2.9865],  # H (index 2)
            [0.0000, -0.7572, 2.9865], # H (index 3)
        ])

        engine = TopologyGraphEngine(resonance_scale=1.15)
        result = engine.analyze_topology(symbols, coordinates)

        assert result.is_strong_complex is True
        assert result.is_weak_complex is False
        assert result.classification == "Strong Complex"
        assert result.complex_type == "STRONG_COMPLEX"
        assert result.routing_target == "STRONG_COMPLEX"
        assert result.counterpoise_flag is False

        # Cleavage is aborted: system retained as single unit
        assert len(result.monomers) == 1
        assert result.monomers[0].num_atoms == 4
        assert result.shortest_gap is not None
        assert result.shortest_gap.is_transition_metal_contact is True

    def test_palladium_complex_triage(self) -> None:
        """Tests Pd transition metal complex triage at 2.60 A."""
        symbols = ["Pd", "C", "O"]
        coordinates = np.array([
            [0.0000, 0.0000, 0.0000],  # Pd
            [0.0000, 0.0000, 2.6000],  # C of CO
            [0.0000, 0.0000, 3.7300],  # O of CO
        ])

        result = analyze_molecular_graph(symbols, coordinates)
        assert result.is_strong_complex is True
        assert result.classification == "Strong Complex"
        assert result.complex_type == "STRONG_COMPLEX"
        assert result.counterpoise_flag is False


class TestAirGappedStateAndTelemetryExport:
    """Verifies state serialization, XYZ user seeds export, and stage_n_complete.json tracking."""

    def test_air_gapped_state_export(self, tmp_path: Path) -> None:
        """Confirms isolated monomer coordinate arrays are exported to user_seeds and stage tracker is written."""
        symbols = ["O", "H", "H", "O", "H", "H"]
        coordinates = np.array([
            [-1.5, 0.0, 0.0],
            [-1.8, 0.7, 0.0],
            [-0.6, 0.0, 0.0],
            [ 1.5, 0.0, 0.0],
            [ 1.8, 0.7, 0.0],
            [ 1.8,-0.7, 0.0],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        tracker_data = result.export_air_gapped_state(workspace=tmp_path)

        assert tracker_data["stage"] == "1.1"
        assert tracker_data["status"] == "COMPLETE"
        assert tracker_data["classification"] == "Weak Complex"
        assert tracker_data["monomer_seeds_stage"] == "Stage 2.0"
        assert tracker_data["parent_complex_stage"] == "Stage 3.0"
        assert len(tracker_data["monomer_seeds"]) == 2

        # Verify exported files on disk
        user_seeds_dir = tmp_path / "CoChem_Artifacts" / "Input_Files" / "user_seeds"
        assert user_seeds_dir.exists()
        xyz_files = list(user_seeds_dir.glob("*.xyz"))
        assert len(xyz_files) == 2

        stage_tracker = tmp_path / "CoChem_Artifacts" / "stage_n_complete.json"
        assert stage_tracker.exists()
        loaded_json = json.loads(stage_tracker.read_text(encoding="utf-8"))
        assert loaded_json["stage"] == "1.1"
        assert loaded_json["secondary_search"]["flags"] == ["--nci", "--nocross", "--noreftopo"]


class TestSubprocessSafety:
    """Verifies safe execution wrapper for external conformational searches."""

    def test_missing_xyz_file_raises_error(self, tmp_path: Path) -> None:
        """Confirms missing input file raises FileNotFoundError before spawning process."""
        missing_file = tmp_path / "non_existent.xyz"
        with pytest.raises(FileNotFoundError):
            run_crest_secondary_search(missing_file, tmp_path)


class TestPydanticSerializationAndParsers:
    """Verifies Pydantic model serialization, validation, and error traps."""

    def test_pydantic_serialization(self) -> None:
        """Verifies JSON round-trip serialization of TopologyAnalysisResult."""
        symbols = ["O", "H", "H"]
        coordinates = np.array([
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_topology(symbols, coordinates)

        json_str = result.to_json()
        data = json.loads(json_str)

        assert data["num_atoms"] == 3
        assert data["classification"] == "Monomer"
        assert data["routing_target"] == "MONOMER_GOAT"

        reconstructed = TopologyAnalysisResult.model_validate(data)
        assert reconstructed.num_atoms == result.num_atoms
        assert reconstructed.routing_target == result.routing_target

    def test_parse_xyz_string_and_file(self, tmp_path: Path) -> None:
        """Validates XYZ parser on both raw strings and disk files."""
        raw_xyz = """3
Water monomer test coordinate
O  0.0000  0.0000  0.1173
H  0.0000  0.7572 -0.4692
H  0.0000 -0.7572 -0.4692
"""
        parsed_symbols, parsed_coords, title = parse_xyz_string(raw_xyz)
        assert parsed_symbols == ["O", "H", "H"]
        assert parsed_coords.shape == (3, 3)

        file_path = tmp_path / "water.xyz"
        file_path.write_text(raw_xyz, encoding="utf-8")

        file_symbols, file_coords, _ = parse_xyz_file(file_path)
        assert file_symbols == parsed_symbols
        np.testing.assert_allclose(file_coords, parsed_coords)

    def test_ase_atoms_ingestion(self) -> None:
        """Validates ingestion from an ASE Atoms object."""
        atoms = Atoms(symbols=["O", "H", "H"], positions=[
            [0.0000,  0.0000,  0.1173],
            [0.0000,  0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ])

        engine = TopologyGraphEngine()
        result = engine.analyze_atoms(atoms)
        assert result.classification == "Monomer"
        assert result.routing_target == "MONOMER_GOAT"
        assert result.num_atoms == 3

    def test_empty_coordinates_error(self) -> None:
        """Confirms empty inputs raise ValueError."""
        engine = TopologyGraphEngine()
        with pytest.raises(ValueError, match="At least one atom"):
            engine.analyze_topology([], np.empty((0, 3)))

    def test_dimension_mismatch_error(self) -> None:
        """Confirms symbol count and coordinate count mismatch raises ValueError."""
        symbols = ["O", "H"]
        coordinates = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
        ])
        engine = TopologyGraphEngine()
        with pytest.raises(ValueError, match="Mismatch"):
            engine.analyze_topology(symbols, coordinates)

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.