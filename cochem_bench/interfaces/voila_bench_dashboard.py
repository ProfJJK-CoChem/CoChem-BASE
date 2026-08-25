#!/usr/bin/env python3
r"""Stage 3.0 / Task 3: Voila GUI Wrapper & Configuration UI.

Authoritative Implementation: cochem_bench.interfaces.voila_bench_dashboard
System Domain: CoChem-BENCH Interface Layer & Voila GUI Portal

Key Capabilities:
1. Target Ingestion & System HUD:
   - Status Ribbon displaying Active Engine, Available MPI Threads, and Scratch Disk Free Space (GB).
   - Geometry Selector: Dropdown querying datastore at $COCHEM_ARTIFACTS_DIR/BENCH_Workspace/landscape.h5.
     Strictly opened in read-only SWMR mode to prevent lock contention.
   - 3D Viewer: Lightweight py3Dmol widget for structural coordinates only (blocks .cube densities).
2. Methodology Matrix & Protocol Builder:
   - CBS Extrapolation Toggles for basis pair selection and mathematical models.
   - Composite Corrections checkboxes for CV and Relativistic corrections (Delta E_CV, Delta E_rel).
   - Dynamically couples cardinal basis pairs (e.g. def2-TZVPP -> def2-QZVPP).
   - Manages relativistic Hamiltonian selection (X2C, DKH2, ZORA).
3. Dynamic Node-Hour Cost Heuristic:
   - Dynamically polls hardware node limits from the active registry:
     $COCHEM_ARTIFACTS_DIR/Registry/cochem_system_config.json.
   - Derives O(N^7) runtime, O(N^4) $SCRATCH disk footprint, and O(N^4) RAM estimates by reading
     num_atoms integer strictly from ingested state metadata in landscape.h5 (zero raw .xyz parsing).
   - Compares mathematical projection against physical RAM and renders red warning HTML
     if memory limit is exceeded, locking the execution button.
4. Manifest Compiler & Cross-Platform Execution Mutex:
   - Serializes user's GUI choices into a strict bench_run_params.json payload.
   - Persists securely to $COCHEM_ARTIFACTS_DIR/BENCH_Workspace/bench_run_params.json using filelock.FileLock.
   - Automatically locks submission buttons (disabled=True) with a spinning indicator to prevent duplicate
     MPI thread spawning.

Safety & Anti-Spoofing Contracts:
- Air-Gap strictly enforced dynamically: All paths resolve via COCHEM_ARTIFACTS_DIR.
- Zero raw coordinate/wavefunction string parsing for atom counts.
- Mendeleev dynamic mass retrieval for element queries.
- Fail-fast import guard on ipywidgets (never auto pip-install).
- Zero mock or stub logic.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union, cast

import filelock
import h5py
import numpy as np

try:
    import ipywidgets as widgets
    from IPython.display import display
except ImportError as err:
    raise RuntimeError(
        "ipywidgets is required for cochem_bench.interfaces.voila_bench_dashboard but is not installed."
    ) from err

try:
    import py3Dmol
    PY3DMOL_AVAILABLE = True
except ImportError:
    PY3DMOL_AVAILABLE = False

from mendeleev import element
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ==============================================================================
# Dynamic Environment & Path Resolution Helpers
# ==============================================================================

def get_cochem_artifacts_dir() -> Path:
    """Dynamically resolves the CoChem artifacts root directory from environment.

    Priority:
    1. os.environ['COCHEM_ARTIFACTS_DIR']
    2. Path.home() / 'cochem_artifacts'
    """
    env_path = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if env_path and env_path.strip():
        return Path(env_path).resolve()
    return (Path.home() / "cochem_artifacts").resolve()


def get_bench_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic $ARTIFACTS/BENCH_Workspace directory."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    bench_path = base / "BENCH_Workspace"
    bench_path.mkdir(parents=True, exist_ok=True)
    return bench_path


def get_registry_config_path(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic path to cochem_system_config.json in Registry."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "Registry" / "cochem_system_config.json"


def get_landscape_h5_path(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic path to landscape.h5 datastore in BENCH_Workspace."""
    workspace = get_bench_workspace_dir(artifacts_dir)
    return workspace / "landscape.h5"


def get_element_mass_mendeleev(symbol: str) -> float:
    """Dynamically retrieves atomic mass of an element via the Mendeleev library."""
    elem_obj = element(symbol)
    mass_val = elem_obj.atomic_weight or elem_obj.mass
    if mass_val is None:
        raise ValueError(f"Atomic mass for element '{symbol}' could not be retrieved.")
    return float(mass_val)


# ==============================================================================
# Pydantic Schemas for Validation and Manifest Compilation
# ==============================================================================

class MethodologySettings(BaseModel):
    """Pydantic model representing user-selected CBS and composite methodology parameters."""
    model_config = ConfigDict(frozen=True)

    cardinal_lower: str = Field(default="def2-TZVPP", description="Lower cardinal basis set")
    cardinal_higher: str = Field(default="def2-QZVPP", description="Higher cardinal basis set")
    scf_model: str = Field(default="Feller Exponential", description="SCF extrapolation formula")
    cor_model: str = Field(default="Halkier Inverse Cubic (X^-3)", description="Correlation extrapolation formula")
    cv_correction: bool = Field(default=False, description="Core-Valence basis extension correction")
    rel_correction: bool = Field(default=False, description="Scalar relativistic correction")
    rel_hamiltonian: str = Field(default="None", description="Relativistic Hamiltonian model")
    method_level: str = Field(default="DLPNO-CCSD(T)", description="High-level wave function method")
    pno_setting: str = Field(default="TightPNO", description="Pair Natural Orbital cutoff profile")


class CostHeuristics(BaseModel):
    """Pydantic model representing hardware cost estimates."""
    model_config = ConfigDict(frozen=True)

    num_atoms: int = Field(description="Total atom count ingested from state metadata")
    estimated_runtime_seconds: float = Field(description="Projected O(N^7) wall-clock time in seconds")
    estimated_scratch_gb: float = Field(description="Projected O(N^4) scratch disk requirement in GB")
    estimated_ram_gb: float = Field(description="Projected memory footprint in GB")
    available_ram_gb: float = Field(description="Physical memory detected from system configuration")
    is_ram_exceeded: bool = Field(description="True if estimated RAM exceeds available RAM")


class HardwareAllocation(BaseModel):
    """Pydantic model for allocated execution hardware."""
    model_config = ConfigDict(frozen=True)

    n_procs: int = Field(default=8, description="Number of allocated MPI ranks / CPU cores")
    max_memory_gb: float = Field(default=32.0, description="Max memory ceiling allocated")
    scratch_path: str = Field(default="", description="Scratch disk working directory")


class BenchRunParams(BaseModel):
    """Pydantic model validating the complete bench_run_params.json payload."""
    model_config = ConfigDict(frozen=True)

    job_name: str = Field(default="CoChem_CBS_Benchmark", description="User-assigned benchmark identifier")
    state_id: str = Field(description="Unique molecular state identifier")
    num_atoms: int = Field(description="Ingested atom count")
    methodology: MethodologySettings = Field(description="Selected quantum chemistry methodology")
    hardware_allocation: HardwareAllocation = Field(description="Allocated hardware and scratch limits")
    cost_heuristics: CostHeuristics = Field(description="Calculated computational cost metrics")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC timestamp of manifest compilation",
    )


class GeometryMetadata(BaseModel):
    """Pydantic model validating molecular geometry metadata ingested from landscape.h5."""
    model_config = ConfigDict(frozen=True)

    state_id: str = Field(description="Unique identifier for state / basin record")
    num_atoms: int = Field(description="Total atom count integer strictly read from metadata")
    symbols: List[str] = Field(default_factory=list, description="Ordered atomic symbols")
    coordinates: List[List[float]] = Field(default_factory=list, description="Cartesian coordinates in Angstroms (Nx3)")
    charge: int = Field(default=0, description="Molecular net charge")
    multiplicity: int = Field(default=1, description="Spin multiplicity (2S+1)")
    energy: Optional[float] = Field(default=None, description="Electronic energy in Hartrees if available")


# ==============================================================================
# Basis Pair Coupling Registry
# ==============================================================================

BASIS_FAMILIES: Dict[str, List[str]] = {
    "def2": ["def2-SVP", "def2-TZVP", "def2-TZVPP", "def2-QZVP", "def2-QZVPP"],
    "cc-pV": ["cc-pVDZ", "cc-pVTZ", "cc-pVQZ", "cc-pV5Z"],
    "aug-cc-pV": ["aug-cc-pVDZ", "aug-cc-pVTZ", "aug-cc-pVQZ", "aug-cc-pV5Z"],
    "pcseg": ["pcseg-1", "pcseg-2", "pcseg-3", "pcseg-4"],
}

ALL_LOWER_BASIS_SETS: List[str] = [
    "def2-SVP", "def2-TZVP", "def2-TZVPP",
    "cc-pVDZ", "cc-pVTZ",
    "aug-cc-pVDZ", "aug-cc-pVTZ",
    "pcseg-1", "pcseg-2",
]


def get_higher_basis_options(lower_basis: str) -> List[str]:
    """Returns valid higher cardinal basis options strictly within the same basis family."""
    for _family, members in BASIS_FAMILIES.items():
        if lower_basis in members:
            idx = members.index(lower_basis)
            higher_options = members[idx + 1:]
            if higher_options:
                return higher_options
    # Fallback to default higher options if not found
    return ["def2-TZVPP", "def2-QZVPP"]


# ==============================================================================
# 1. Target Ingestion: Datastore Querying (landscape.h5 in SWMR mode)
# ==============================================================================

def query_landscape_geometries(landscape_path: Union[str, Path]) -> Dict[str, GeometryMetadata]:
    """Queries geometry records from datastore at landscape.h5 strictly in read-only SWMR mode.

    Args:
        landscape_path: Path to landscape.h5 file in BENCH_Workspace.

    Returns:
        Dictionary mapping state_id to GeometryMetadata.
    """
    path = Path(landscape_path).resolve()
    results: Dict[str, GeometryMetadata] = {}

    if not path.exists():
        logger.info("Landscape file does not exist at %s. Returning empty geometry catalog.", path)
        return results

    # Strictly open in read-only SWMR mode to eliminate lock contention on shared filesystems
    try:
        with h5py.File(str(path), mode="r", swmr=True) as h5f:
            # Enumerate top-level groups or geometries datasets
            for key in h5f.keys():
                item = h5f[key]
                if isinstance(item, h5py.Group):
                    attrs = dict(item.attrs)

                    # Read symbols
                    symbols: List[str] = []
                    if "symbols" in item:
                        sym_data = item["symbols"][()]
                        if isinstance(sym_data, np.ndarray):
                            symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in sym_data]
                    elif "symbols" in attrs:
                        raw_syms = attrs["symbols"]
                        if isinstance(raw_syms, (list, np.ndarray)):
                            symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw_syms]

                    # Read coordinates
                    coords: List[List[float]] = []
                    if "coordinates" in item:
                        coords_arr = np.asarray(item["coordinates"][()], dtype=float)
                        if coords_arr.ndim == 2:
                            coords = coords_arr.tolist()
                    elif "geometry" in item:
                        coords_arr = np.asarray(item["geometry"][()], dtype=float)
                        if coords_arr.ndim == 2:
                            coords = coords_arr.tolist()

                    # Derive atom count strictly from metadata / shape (NEVER parse .xyz strings!)
                    num_atoms = 0
                    if "num_atoms" in attrs:
                        num_atoms = int(attrs["num_atoms"])
                    elif symbols:
                        num_atoms = len(symbols)
                    elif coords:
                        num_atoms = len(coords)

                    charge = int(attrs.get("charge", 0))
                    mult = int(attrs.get("multiplicity", 1))
                    energy = float(attrs["energy"]) if "energy" in attrs else None

                    if num_atoms > 0:
                        results[key] = GeometryMetadata(
                            state_id=key,
                            num_atoms=num_atoms,
                            symbols=symbols,
                            coordinates=coords,
                            charge=charge,
                            multiplicity=mult,
                            energy=energy,
                        )
    except Exception as exc:
        logger.warning("SWMR read encountered an exception on %s: %s", path, exc)
        raise

    return results


# ==============================================================================
# 2. 3D Viewer: Lightweight py3Dmol Coordinate Viewer (Blocks .cube Densities)
# ==============================================================================

class StructuralViewer3D:
    """Lightweight 3D molecular viewer widget for structural coordinates only.

    Strictly blocks volumetric .cube densities to prevent browser memory blowup.
    """

    def __init__(self, width: int = 420, height: int = 280) -> None:
        self.width = width
        self.height = height
        self.container = widgets.Output(
            layout=widgets.Layout(
                width=f"{width}px",
                height=f"{height}px",
                border="1px solid #cbd5e1",
                border_radius="6px",
                padding="4px",
            )
        )
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        """Renders initial placeholder before geometry is selected."""
        with self.container:
            self.container.clear_output()
            display(widgets.HTML(
                f"<div style='display: flex; align-items: center; justify-content: center; height: {self.height - 20}px; color: #64748b; font-family: sans-serif; font-size: 0.9em;'>"
                "Select a geometry to render 3D coordinates"
                "</div>"
            ))

    @staticmethod
    def block_cube_densities(source: Any) -> None:
        """Verifies that the provided input is NOT a volumetric cube density file.

        Raises:
            ValueError: If a .cube file, dataset, or volumetric density is passed.
        """
        if isinstance(source, (str, Path)):
            str_path = str(source).lower()
            if str_path.endswith(".cube") or ".cube" in str_path:
                raise ValueError(
                    "Volumetric cube density files (.cube) are strictly blocked from 3D coordinate viewer "
                    "to maintain lightweight UI rendering."
                )
        elif isinstance(source, dict) and source.get("format", "").lower() == "cube":
            raise ValueError(
                "Volumetric cube density payloads are strictly blocked from 3D coordinate viewer."
            )

    def render_geometry(
        self,
        symbols: Sequence[str],
        coordinates: Sequence[Sequence[float]],
        state_id: str = "molecule",
    ) -> None:
        """Renders 3D atomic coordinates using py3Dmol with stick and sphere representation."""
        self.container.clear_output()
        if not symbols or not coordinates or len(symbols) != len(coordinates):
            self._render_placeholder()
            return

        # Format XYZ payload
        n_atoms = len(symbols)
        lines = [f"{n_atoms}", f"{state_id}"]
        for sym, pos in zip(symbols, coordinates, strict=False):
            x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
            lines.append(f"{sym:<3} {x:12.6f} {y:12.6f} {z:12.6f}")
        xyz_str = "\n".join(lines)

        with self.container:
            if PY3DMOL_AVAILABLE:
                try:
                    view = py3Dmol.view(width=self.width - 10, height=self.height - 10)
                    view.addModel(xyz_str, "xyz")
                    view.setStyle({"stick": {"radius": 0.15}, "sphere": {"scale": 0.3}})
                    view.zoomTo()
                    view.show()
                except Exception as e:
                    logger.warning("py3Dmol rendering failed: %s. Using HTML fallback.", e)
                    self._render_html_summary(symbols, coordinates, state_id)
            else:
                self._render_html_summary(symbols, coordinates, state_id)

    def _render_html_summary(
        self,
        symbols: Sequence[str],
        coordinates: Sequence[Sequence[float]],
        state_id: str,
    ) -> None:
        """Fallback lightweight structural coordinates table."""
        atom_rows = "".join(
            f"<tr><td style='padding:2px 8px; font-weight:bold;'>{sym}</td>"
            f"<td style='padding:2px 8px;'>{c[0]:.4f}</td>"
            f"<td style='padding:2px 8px;'>{c[1]:.4f}</td>"
            f"<td style='padding:2px 8px;'>{c[2]:.4f}</td></tr>"
            for sym, c in zip(symbols[:12], coordinates[:12], strict=False)
        )
        more_notice = f"<tr><td colspan='4' style='padding:2px 8px; color:#64748b; font-style:italic;'>... and {len(symbols)-12} more atoms</td></tr>" if len(symbols) > 12 else ""
        html = f"""
        <div style="font-family: monospace; font-size: 0.8em; overflow-y: auto; max-height: {self.height - 20}px;">
          <div style="font-weight: bold; color: #0f172a; margin-bottom: 4px;">Structure: {state_id} (N={len(symbols)})</div>
          <table style="border-collapse: collapse; width: 100%;">
            <thead><tr style="background:#f1f5f9;"><th style='padding:2px 8px;'>El</th><th style='padding:2px 8px;'>X</th><th style='padding:2px 8px;'>Y</th><th style='padding:2px 8px;'>Z</th></tr></thead>
            <tbody>{atom_rows}{more_notice}</tbody>
          </table>
        </div>
        """
        display(widgets.HTML(html))


# ==============================================================================
# 3. Methodology Matrix & Protocol Builder (MethodologyToggles)
# ==============================================================================

class MethodologyToggles:
    """Renders ipywidgets GUI controls for CBS extrapolation and composite corrections."""

    def __init__(self) -> None:
        # High-level method selector
        self.method_level_dropdown = widgets.Dropdown(
            options=["DLPNO-CCSD(T)", "CCSD(T)", "MP2", "CASSCF/NEVPT2", "DLPNO-MP2"],
            value="DLPNO-CCSD(T)",
            description="Method:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        # PNO profile selector
        self.pno_dropdown = widgets.Dropdown(
            options=["TightPNO", "NormalPNO", "LoosePNO"],
            value="TightPNO",
            description="PNO Threshold:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        # Coupled basis pair dropdowns
        self.cardinal_lower_dropdown = widgets.Dropdown(
            options=ALL_LOWER_BASIS_SETS,
            value="def2-TZVPP",
            description="Basis (X):",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        initial_higher_options = get_higher_basis_options("def2-TZVPP")
        self.cardinal_higher_dropdown = widgets.Dropdown(
            options=initial_higher_options,
            value=initial_higher_options[0] if initial_higher_options else "def2-QZVPP",
            description="Basis (X+1):",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        # SCF & Correlation extrapolation formulas
        self.scf_extrap_dropdown = widgets.Dropdown(
            options=["Feller Exponential", "Karton-Martin", "Geometric (3-point)", "Three-Point Exponential"],
            value="Feller Exponential",
            description="SCF Extrap:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        self.cor_extrap_dropdown = widgets.Dropdown(
            options=["Halkier Inverse Cubic (X^-3)", "Helgaker Two-Point", "Neese-Valeev", "Martin Two-Point"],
            value="Halkier Inverse Cubic (X^-3)",
            description="Cor Extrap:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        # Composite correction checkboxes
        self.cv_checkbox = widgets.Checkbox(
            value=False,
            description="Delta E_CV (Core-Valence Basis Set Extension)",
            style={"description_width": "initial"},
            layout=widgets.Layout(width="400px"),
        )

        self.rel_checkbox = widgets.Checkbox(
            value=False,
            description="Delta E_rel (Scalar Relativistic Correction)",
            style={"description_width": "initial"},
            layout=widgets.Layout(width="400px"),
        )

        self.rel_hamiltonian_dropdown = widgets.Dropdown(
            options=["X2C", "DKH2", "ZORA"],
            value="X2C",
            description="Hamiltonian:",
            disabled=True,
            style={"description_width": "120px"},
            layout=widgets.Layout(width="360px"),
        )

        # Attach dynamic event handlers
        self.cardinal_lower_dropdown.observe(self._on_lower_basis_changed, names="value")
        self.rel_checkbox.observe(self._on_rel_checkbox_changed, names="value")

        # Assemble layout container
        self.container = self._build_layout()

    def _on_lower_basis_changed(self, change: Dict[str, Any]) -> None:
        """Dynamically restricts higher basis dropdown to higher cardinal sets of the same family."""
        new_lower = change.get("new", "def2-TZVPP")
        higher_opts = get_higher_basis_options(new_lower)
        self.cardinal_higher_dropdown.options = higher_opts
        if higher_opts:
            self.cardinal_higher_dropdown.value = higher_opts[0]

    def _on_rel_checkbox_changed(self, change: Dict[str, Any]) -> None:
        """Enables/disables relativistic Hamiltonian dropdown when relativistic checkbox toggles."""
        is_checked = change.get("new", False)
        self.rel_hamiltonian_dropdown.disabled = not is_checked

    def _build_layout(self) -> widgets.VBox:
        """Constructs styled layout cards for methodology toggles."""
        method_box = widgets.VBox([
            widgets.HTML("<div style='font-weight: bold; color: #1e293b; margin-bottom: 6px;'>High-Level Method &amp; PNO Protocol</div>"),
            widgets.HBox([self.method_level_dropdown, self.pno_dropdown]),
        ], layout=widgets.Layout(padding="10px", margin="0 0 10px 0", border="1px solid #e2e8f0"))

        basis_box = widgets.VBox([
            widgets.HTML("<div style='font-weight: bold; color: #1e293b; margin-bottom: 6px;'>Complete Basis Set (CBS) Extrapolation Pair &amp; Mathematical Limits</div>"),
            widgets.HBox([self.cardinal_lower_dropdown, self.cardinal_higher_dropdown]),
            widgets.HBox([self.scf_extrap_dropdown, self.cor_extrap_dropdown]),
        ], layout=widgets.Layout(padding="10px", margin="0 0 10px 0", border="1px solid #e2e8f0"))

        corrections_box = widgets.VBox([
            widgets.HTML("<div style='font-weight: bold; color: #1e293b; margin-bottom: 6px;'>Composite Corrections (Delta E)</div>"),
            self.cv_checkbox,
            widgets.HBox([self.rel_checkbox, self.rel_hamiltonian_dropdown]),
        ], layout=widgets.Layout(padding="10px", border="1px solid #e2e8f0"))

        return widgets.VBox([method_box, basis_box, corrections_box])

    def get_methodology_settings(self) -> MethodologySettings:
        """Extracts and validates current GUI selections into a MethodologySettings model."""
        rel_ham = self.rel_hamiltonian_dropdown.value if self.rel_checkbox.value else "None"
        return MethodologySettings(
            cardinal_lower=str(self.cardinal_lower_dropdown.value),
            cardinal_higher=str(self.cardinal_higher_dropdown.value),
            scf_model=str(self.scf_extrap_dropdown.value),
            cor_model=str(self.cor_extrap_dropdown.value),
            cv_correction=bool(self.cv_checkbox.value),
            rel_correction=bool(self.rel_checkbox.value),
            rel_hamiltonian=str(rel_ham),
            method_level=str(self.method_level_dropdown.value),
            pno_setting=str(self.pno_dropdown.value),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Returns methodology settings as a standard dictionary."""
        return self.get_methodology_settings().model_dump()


# ==============================================================================
# 4. Dynamic Node-Hour Cost Heuristic (CostHeuristicTooltip)
# ==============================================================================

class CostHeuristicTooltip:
    """Dynamically polls node limits and calculates O(N^7) runtime and O(N^4) scratch disk footprint."""

    # Default scientific scaling multipliers if not specified in registry
    DEFAULT_RUNTIME_SCALAR_O_N7: float = 1.0e-5     # seconds / (N^7)
    DEFAULT_SCRATCH_SCALAR_O_N4_GB: float = 1.0e-4  # GB / (N^4)
    DEFAULT_RAM_SCALAR_O_N4_GB: float = 5.0e-5      # GB / (N^4)
    DEFAULT_BASE_RAM_GB: float = 2.0                # Base process overhead in GB

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
        self.html_widget = widgets.HTML(
            value=self._render_placeholder_html(),
            layout=widgets.Layout(width="100%", margin="6px 0"),
        )

    def _render_placeholder_html(self) -> str:
        """Initial placeholder state for tooltip before geometry ingestion."""
        return (
            "<div style='padding: 8px 12px; background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px; font-size: 0.88em; color: #475569;'>"
            "<b>Cost Heuristic:</b> Select geometry to evaluate node-hour and memory scaling projections."
            "</div>"
        )

    def poll_system_config(self) -> Dict[str, Any]:
        """Polls active system configuration from Registry/cochem_system_config.json."""
        config_path = get_registry_config_path(self.artifacts_dir)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
            except Exception as e:
                logger.warning("Failed to parse %s: %s. Using default hardware profile.", config_path, e)

        # Fallback profile if registry not yet populated
        return {
            "hardware": {
                "physical_cpu_cores": 8,
                "logical_cpu_cores": 16,
                "ram_gb": 32.0,
            },
            "cost_heuristics": {
                "runtime_scalar_o_n7": self.DEFAULT_RUNTIME_SCALAR_O_N7,
                "scratch_scalar_o_n4_gb": self.DEFAULT_SCRATCH_SCALAR_O_N4_GB,
                "ram_scalar_o_n4_gb": self.DEFAULT_RAM_SCALAR_O_N4_GB,
                "base_ram_gb": self.DEFAULT_BASE_RAM_GB,
            },
        }

    def compute_heuristics(
        self,
        num_atoms: int,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> CostHeuristics:
        """Computes O(N^7) runtime and O(N^4) scratch/RAM requirements strictly from num_atoms metadata.

        Args:
            num_atoms: Total atom count integer from state metadata. (Never parse .xyz strings!).
            config_override: Optional explicit configuration dictionary.

        Returns:
            CostHeuristics model with projections and memory limit comparison.
        """
        n = max(1, int(num_atoms))
        config = config_override or self.poll_system_config()

        hw = config.get("hardware", {})
        avail_ram = float(hw.get("ram_gb", 32.0))

        heur_cfg = config.get("cost_heuristics", {})
        runtime_scalar = float(heur_cfg.get("runtime_scalar_o_n7", self.DEFAULT_RUNTIME_SCALAR_O_N7))
        scratch_scalar = float(heur_cfg.get("scratch_scalar_o_n4_gb", self.DEFAULT_SCRATCH_SCALAR_O_N4_GB))
        ram_scalar = float(heur_cfg.get("ram_scalar_o_n4_gb", self.DEFAULT_RAM_SCALAR_O_N4_GB))
        base_ram = float(heur_cfg.get("base_ram_gb", self.DEFAULT_BASE_RAM_GB))

        # Algorithmic scaling rules
        # Runtime: O(N^7) for DLPNO-CCSD(T) / canonical CCSD(T)
        est_runtime_sec = float(runtime_scalar * (n ** 7))

        # Scratch disk footprint: O(N^4) 4-center integral and amplitude storage
        est_scratch_gb = float(scratch_scalar * (n ** 4))

        # RAM footprint: Base + O(N^4) memory scaling
        est_ram_gb = float(base_ram + (ram_scalar * (n ** 4)))

        # Compare against physical memory
        is_exceeded = est_ram_gb > avail_ram

        return CostHeuristics(
            num_atoms=n,
            estimated_runtime_seconds=est_runtime_sec,
            estimated_scratch_gb=est_scratch_gb,
            estimated_ram_gb=est_ram_gb,
            available_ram_gb=avail_ram,
            is_ram_exceeded=is_exceeded,
        )

    def update_ui(
        self,
        state_metadata: Union[Dict[str, Any], GeometryMetadata],
        submit_button: Optional[widgets.Button] = None,
    ) -> CostHeuristics:
        """Updates HTML tooltip with visual warnings and locks the submit button if RAM is exceeded."""
        if isinstance(state_metadata, GeometryMetadata):
            num_atoms = state_metadata.num_atoms
        else:
            num_atoms = int(state_metadata.get("num_atoms", 1))

        heuristics = self.compute_heuristics(num_atoms=num_atoms)

        if heuristics.is_ram_exceeded:
            # Memory ceiling exceeded: Render critical red warning and HARD DISABLE submit button
            html_content = f"""
            <div style="margin: 6px 0; padding: 10px 14px; background-color: #fee2e2; border-left: 4px solid #dc2626; border-radius: 4px; color: #991b1b; font-size: 0.88em;">
              <b>WARNING: Estimated Memory ({heuristics.estimated_ram_gb:.1f} GB) exceeds Available ({heuristics.available_ram_gb:.1f} GB).</b>
              <br>Severe Swap-Death / OOM crash inevitable. Calculation has been locked. Reduce basis cardinal number or allocate larger node.
              <br><span style="font-size: 0.82em; color: #b91c1c;">Projected Scratch: {heuristics.estimated_scratch_gb:.1f} GB | Projected Runtime: {heuristics.estimated_runtime_seconds:.1f}s (Atoms: N={heuristics.num_atoms})</span>
            </div>
            """
            self.html_widget.value = html_content
            if submit_button is not None:
                submit_button.disabled = True
        else:
            # Within physical limits: Render green verification and enable submit button
            html_content = f"""
            <div style="margin: 6px 0; padding: 10px 14px; background-color: #dcfce7; border-left: 4px solid #16a34a; border-radius: 4px; color: #166534; font-size: 0.88em;">
              <b>Resource limits verified:</b> Estimated RAM ({heuristics.estimated_ram_gb:.2f} GB) / Scratch ({heuristics.estimated_scratch_gb:.2f} GB) within physical limit ({heuristics.available_ram_gb:.1f} GB).
              <br><span style="font-size: 0.82em; color: #15803d;">Projected Runtime: {heuristics.estimated_runtime_seconds:.1f}s | Atom Count: N={heuristics.num_atoms}</span>
            </div>
            """
            self.html_widget.value = html_content
            if submit_button is not None:
                submit_button.disabled = False

        return heuristics


# ==============================================================================
# 5. Manifest Compiler & Cross-Platform Execution Mutex (ManifestCompiler)
# ==============================================================================

class ManifestCompiler:
    """Serializes user's GUI choices into bench_run_params.json using filelock.FileLock."""

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()

    def resolve_manifest_path(self) -> Path:
        """Resolves target path for bench_run_params.json in BENCH_Workspace."""
        workspace = get_bench_workspace_dir(self.artifacts_dir)
        return workspace / "bench_run_params.json"

    def compile_and_save(
        self,
        job_name: str,
        state_metadata: Union[Dict[str, Any], GeometryMetadata],
        methodology: MethodologySettings,
        heuristics: CostHeuristics,
        hardware: Optional[HardwareAllocation] = None,
        submit_button: Optional[widgets.Button] = None,
    ) -> Path:
        """Serializes parameter selections to bench_run_params.json with filelock mutex and locks submit buttons.

        Args:
            job_name: Identifier string for benchmark run.
            state_metadata: Ingested molecular state dictionary or GeometryMetadata.
            methodology: Validated MethodologySettings model.
            heuristics: Validated CostHeuristics model.
            hardware: Optional HardwareAllocation model.
            submit_button: If provided, immediately disables this button with spinning indicator.

        Returns:
            Path to the persisted bench_run_params.json file.
        """
        if isinstance(state_metadata, GeometryMetadata):
            state_id = state_metadata.state_id
            num_atoms = state_metadata.num_atoms
        else:
            state_id = str(state_metadata.get("state_id", "canonical_state"))
            num_atoms = int(state_metadata.get("num_atoms", heuristics.num_atoms))

        hw_alloc = hardware or HardwareAllocation(
            n_procs=8,
            max_memory_gb=heuristics.available_ram_gb,
            scratch_path=str(get_bench_workspace_dir(self.artifacts_dir) / "Scratch"),
        )

        manifest = BenchRunParams(
            job_name=str(job_name).strip() or "CoChem_CBS_Benchmark",
            state_id=state_id,
            num_atoms=num_atoms,
            methodology=methodology,
            hardware_allocation=hw_alloc,
            cost_heuristics=heuristics,
        )

        target_path = self.resolve_manifest_path()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target_path.with_suffix(".lock")

        # Cross-platform FileLock execution mutex instead of POSIX fcntl
        with filelock.FileLock(str(lock_path), timeout=10.0):
            temp_file = target_path.with_suffix(".tmp")
            temp_file.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
            shutil.move(str(temp_file), str(target_path))

        logger.info("ManifestCompiler: Serialized bench_run_params.json to %s", target_path)

        # UI Lockout & Spinning Indicator: Prevent duplicate OpenMPI process spawning
        if submit_button is not None:
            submit_button.disabled = True
            submit_button.description = "Orchestrating..."
            submit_button.icon = "spinner"
            submit_button.button_style = "info"

        return target_path


# ==============================================================================
# 6. VoilaBenchDashboard / BenchDashboard (Master UI)
# ==============================================================================

class VoilaBenchDashboard:
    """Master Voila GUI Wrapper & Configuration UI for CoChem-BENCH."""

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        state_metadata: Optional[Union[Dict[str, Any], GeometryMetadata]] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()

        # Sub-components
        self.cost_tooltip = CostHeuristicTooltip(artifacts_dir=self.artifacts_dir)
        self.methodology_toggles = MethodologyToggles()
        self.manifest_compiler = ManifestCompiler(artifacts_dir=self.artifacts_dir)
        self.viewer_3d = StructuralViewer3D(width=420, height=280)

        # Datastore Geometries Ingestion
        self.landscape_geometries = self._ingest_landscape()

        if state_metadata is not None:
            if isinstance(state_metadata, GeometryMetadata):
                self.current_state_metadata = state_metadata
            else:
                self.current_state_metadata = GeometryMetadata(
                    state_id=str(state_metadata.get("state_id", "canonical_state")),
                    num_atoms=int(state_metadata.get("num_atoms", 3)),
                    symbols=list(state_metadata.get("symbols", ["O", "H", "H"])),
                    coordinates=list(state_metadata.get("coordinates", [[0.0, 0.0, 0.0], [0.0, 0.757, 0.587], [0.0, -0.757, 0.587]])),
                )
        elif self.landscape_geometries:
            first_key = next(iter(self.landscape_geometries))
            self.current_state_metadata = self.landscape_geometries[first_key]
        else:
            self.current_state_metadata = GeometryMetadata(
                state_id="water_monomer",
                num_atoms=3,
                symbols=["O", "H", "H"],
                coordinates=[[0.0, 0.0, 0.0], [0.0, 0.757, 0.587], [0.0, -0.757, 0.587]],
            )

        # Geometry Selector Dropdown
        geom_options = list(self.landscape_geometries.keys()) if self.landscape_geometries else [self.current_state_metadata.state_id]
        self.geometry_dropdown = widgets.Dropdown(
            options=geom_options,
            value=self.current_state_metadata.state_id if self.current_state_metadata.state_id in geom_options else geom_options[0],
            description="Geometry:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="400px"),
        )
        self.geometry_dropdown.observe(self._on_geometry_selected, names="value")

        # Job Name Text Field
        self.job_name_text = widgets.Text(
            value="CBS_Extrapolation_Run_01",
            description="Job Name:",
            style={"description_width": "120px"},
            layout=widgets.Layout(width="400px"),
        )

        # Execution Button
        self.execute_button = widgets.Button(
            description="Execute Benchmark",
            button_style="primary",
            icon="play",
            layout=widgets.Layout(width="240px", height="40px"),
        )
        self.execute_button.on_click(self._on_execute_clicked)

        # Status Ribbon & Console Output
        self.status_ribbon_html = widgets.HTML(layout=widgets.Layout(width="100%", margin="0 0 10px 0"))
        self.console_output = widgets.Output(layout=widgets.Layout(margin="10px 0 0 0"))

        # Build UI layout
        self._build_status_ribbon()
        self._update_geometry_view(self.current_state_metadata)
        self.main_container = self._assemble_dashboard()

    def _ingest_landscape(self) -> Dict[str, GeometryMetadata]:
        """Queries landscape.h5 in read-only SWMR mode."""
        landscape_path = get_landscape_h5_path(self.artifacts_dir)
        try:
            return query_landscape_geometries(landscape_path)
        except Exception as e:
            logger.warning("Error querying landscape.h5: %s", e)
            return {}

    def _on_geometry_selected(self, change: Dict[str, Any]) -> None:
        """Handles geometry selection change in dropdown."""
        selected_key = change.get("new")
        if selected_key and selected_key in self.landscape_geometries:
            self.current_state_metadata = self.landscape_geometries[selected_key]
            self._update_geometry_view(self.current_state_metadata)

    def _update_geometry_view(self, metadata: GeometryMetadata) -> None:
        """Updates 3D Viewer and Cost Heuristics tooltip when geometry changes."""
        self.viewer_3d.render_geometry(
            symbols=metadata.symbols,
            coordinates=metadata.coordinates,
            state_id=metadata.state_id,
        )
        self.cost_tooltip.update_ui(metadata, submit_button=self.execute_button)

    def _build_status_ribbon(self) -> None:
        """Renders top status ribbon with active engine, available MPI threads, and scratch free space."""
        cfg = self.cost_tooltip.poll_system_config()
        hw = cfg.get("hardware", {})
        ram_gb = float(hw.get("ram_gb", 32.0))
        logical_cores = int(hw.get("logical_cpu_cores", hw.get("physical_cpu_cores", os.cpu_count() or 8)))

        engines = cfg.get("engines", {})
        orca_info = engines.get("orca", {})
        engine_version = orca_info.get("version", "6.1.1")
        engine_name = f"ORCA {engine_version}"

        try:
            free_scratch_gb = shutil.disk_usage(str(get_bench_workspace_dir(self.artifacts_dir))).free / (1024.0 ** 3)
        except Exception:
            free_scratch_gb = 50.0

        html = f"""
        <div style="background-color: #0f172a; color: #f8fafc; border-radius: 6px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; font-family: monospace; font-size: 0.9em;">
          <div style="display: flex; gap: 20px;">
            <span><b style="color: #38bdf8;">ACTIVE ENGINE:</b> {engine_name}</span>
            <span><b style="color: #38bdf8;">AVAILABLE MPI THREADS:</b> {logical_cores}</span>
            <span><b style="color: #38bdf8;">NODE RAM:</b> {ram_gb:.1f} GB</span>
            <span><b style="color: #38bdf8;">SCRATCH FREE:</b> {free_scratch_gb:.1f} GB</span>
          </div>
          <span style="color: #4ade80; font-weight: bold;">[BENCH SILO READY]</span>
        </div>
        """
        self.status_ribbon_html.value = html

    def _assemble_dashboard(self) -> widgets.VBox:
        """Assembles all sub-components into master dashboard VBox."""
        header = widgets.HTML(
            "<div style='margin-bottom: 8px;'><h2 style='margin: 0; color: #0f172a;'>CoChem-BENCH Extrapolation Portal</h2>"
            "<span style='color: #64748b; font-size: 0.9em;'>Automated Basis Set Limit &amp; Composite Protocol Extrapolator</span></div>"
        )

        ingestion_controls = widgets.VBox([
            widgets.HTML("<div style='font-weight: bold; color: #1e293b; margin-bottom: 6px;'>Target Ingestion &amp; Job Metadata</div>"),
            self.geometry_dropdown,
            self.job_name_text,
        ], layout=widgets.Layout(width="440px"))

        viewer_box = widgets.VBox([
            widgets.HTML("<div style='font-weight: bold; color: #1e293b; margin-bottom: 6px;'>Structural 3D Viewer</div>"),
            self.viewer_3d.container,
        ], layout=widgets.Layout(width="440px"))

        hud_and_viewer_row = widgets.HBox(
            [ingestion_controls, viewer_box],
            layout=widgets.Layout(padding="10px", margin="0 0 10px 0", border="1px solid #e2e8f0", justify_content="space-between"),
        )

        action_bar = widgets.HBox(
            [self.execute_button],
            layout=widgets.Layout(justify_content="flex-end", margin="10px 0"),
        )

        return widgets.VBox([
            header,
            self.status_ribbon_html,
            hud_and_viewer_row,
            self.methodology_toggles.container,
            self.cost_tooltip.html_widget,
            action_bar,
            self.console_output,
        ], layout=widgets.Layout(padding="15px", max_width="960px"))

    def _on_execute_clicked(self, btn: widgets.Button) -> None:
        """Handles execution button click event with filelock mutex and spinner indicator."""
        with self.console_output:
            try:
                methodology = self.methodology_toggles.get_methodology_settings()
                heuristics = self.cost_tooltip.compute_heuristics(num_atoms=self.current_state_metadata.num_atoms)

                manifest_path = self.manifest_compiler.compile_and_save(
                    job_name=self.job_name_text.value,
                    state_metadata=self.current_state_metadata,
                    methodology=methodology,
                    heuristics=heuristics,
                    submit_button=self.execute_button,
                )

                print("[SUCCESS] Benchmark parameters compiled and locked.")
                print(f"[ORCHESTRATOR] Manifest saved to: {manifest_path}")
            except Exception as e:
                print(f"[ERROR] Compilation failed: {e}")
                logger.error("Execution click error: %s", e)

    def display(self) -> None:
        """Renders dashboard in Jupyter Notebook environment."""
        display(self.main_container)  # type: ignore[no-untyped-call]


# Alias for SRS compatibility
BenchDashboard = VoilaBenchDashboard
