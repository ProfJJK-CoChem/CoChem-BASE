#!/usr/bin/env python3
"""CoChem-CORE: Stage 1.x - Consolidated Molecular Intake Backend.

Module: intake/cochem_mint_ingestor.py
Purpose: Jupyter-native unified GUI and backend for directory scanning, structural
         canonicalization, and real-time watchdog monitoring.
         STRICT AIR-GAP: Forcibly routes all workspaces to CoChem_Artifacts.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
import site
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import ipywidgets as widgets
from IPython.display import display

from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-MInt")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


def bootstrap_watchdog() -> bool:
    """Attempts dynamic installation and import of the watchdog library."""
    global HAS_WATCHDOG, FileSystemEventHandler, Observer
    if HAS_WATCHDOG:
        return True
    try:
        cmd = [sys.executable, "-m", "pip", "install", "watchdog"]
        if safe_subprocess_run is not None:
            safe_subprocess_run(cmd, timeout=60.0, check=True)
        else:
            subprocess.run(cmd, check=True, timeout=60.0, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        importlib.invalidate_caches()
        importlib.reload(site)

        watchdog_events = importlib.import_module("watchdog.events")
        watchdog_observers = importlib.import_module("watchdog.observers")
        globals()["FileSystemEventHandler"] = watchdog_events.FileSystemEventHandler
        globals()["Observer"] = watchdog_observers.Observer
        HAS_WATCHDOG = True
        return True
    except Exception as e:
        logger.warning(f"Watchdog bootstrap failed: {e}")
        return False


def print_status(msg: str, status: str = "info") -> None:
    """Jupyter-safe HTML status printer."""
    colors = {"success": "green", "warning": "orange", "fail": "red", "info": "blue"}
    color = colors.get(status, "black")
    try:
        display(widgets.HTML(f"<span style='color:{color}; font-weight:bold;'>[{status.upper()}]</span> {msg}"))
    except Exception:
        pass


def sanitize_project_name(name: str) -> str:
    """Sanitizes user input project name against path traversals and invalid characters."""
    if not name or not name.strip():
        return "New_Project"

    clean_base = Path(name).name.strip()
    clean_base = re.sub(r'[\.\/\\]+', '', clean_base)
    clean_name = re.sub(r'[^A-Za-z0-9_\-]+', '_', clean_base).strip('_')

    if not clean_name:
        return "New_Project"
    return clean_name


def validate_xyz_content(content: Union[str, bytes]) -> Tuple[bool, int, str]:
    """Validates XYZ formatted text or bytes, returning (is_valid, atom_count, comment)."""
    text = content.decode("utf-8") if isinstance(content, (bytes, memoryview)) else str(content)
    raw_lines = text.strip().splitlines()
    if len(raw_lines) < 2:
        return False, 0, ""

    try:
        atom_count = int(raw_lines[0].strip())
        if atom_count <= 0:
            return False, 0, ""
    except (ValueError, IndexError):
        return False, 0, ""

    comment = raw_lines[1].strip()
    coord_lines = [line.strip() for line in raw_lines[2:] if line.strip()]
    if len(coord_lines) != atom_count:
        return False, 0, ""

    for line in coord_lines:
        tokens = line.split()
        if len(tokens) < 4:
            return False, 0, ""
        try:
            float(tokens[1])
            float(tokens[2])
            float(tokens[3])
        except ValueError:
            return False, 0, ""

    return True, atom_count, comment


def resolve_smiles(query: str) -> Tuple[Optional[str], Optional[str]]:
    """Resolves a molecule query either directly as SMILES or via PubChem API."""
    if not query or not query.strip():
        return None, None

    q = query.strip()

    # Explicit SMILES structural markers (branching, rings, stereochemistry, bonds, charges)
    smiles_structural_markers = ["=", "#", "(", ")", "[", "]", "/", "\\", "@", ".", ":", "%", "+"]
    has_structure_marker = any(char in q for char in smiles_structural_markers)
    has_ring_digits = any(char.isdigit() for char in q)

    # Check for pure uppercase aliphatic SMILES strings (e.g. CCO, CCC, CO, CCN)
    is_pure_upper_smiles = q.isupper() and all(c in "BCNOPSFIH" for c in q)

    if has_structure_marker or has_ring_digits or is_pure_upper_smiles:
        return q, "direct_smiles"

    # Attempt PubChem REST API lookup for common chemical names
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(q)}/property/IsomericSMILES,CanonicalSMILES/JSON"
        req = urllib.request.Request(url, headers={"User-Agent": "CoChem/1.0"})
        with urllib.request.urlopen(req, timeout=10.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
                smiles = props.get("SMILES") or props.get("IsomericSMILES") or props.get("ConnectivitySMILES") or props.get("CanonicalSMILES")
                if smiles:
                    return smiles, "pubchem"
    except Exception as e:
        logger.debug(f"PubChem lookup failed for '{q}': {e}")

    return q, "direct_smiles"


def generate_3d_geometry(
    smiles_or_name: str, output_path: Optional[Path] = None, optimize_mmff: bool = True
) -> Path:
    """Generates 3D coordinates using RDKit and saves them to an XYZ file."""
    smiles, _ = resolve_smiles(smiles_or_name)
    if not smiles:
        raise ValueError(f"Could not resolve SMILES for '{smiles_or_name}'")

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as e:
        raise RuntimeError("RDKit is required for generate_3d_geometry") from e

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not mathematically parse the SMILES string: {smiles}")

    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.useRandomCoords = False
    AllChem.EmbedMolecule(mol, params)

    if optimize_mmff:
        try:
            AllChem.MMFFOptimizeMolecule(mol)
        except Exception:
            pass

    out_p = Path(output_path) if output_path is not None else Path(f"{sanitize_project_name(smiles_or_name)}.xyz")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    Chem.MolToXYZFile(mol, str(out_p))
    return out_p


def scan_workspace_geometries(workspace_dir: Path) -> List[Dict[str, Any]]:
    """Scans workspace directory for .xyz files and parses validation metadata."""
    results = []
    p = Path(workspace_dir)
    if not p.exists():
        return results

    for f in sorted(p.glob("*.xyz")):
        try:
            content = f.read_text(encoding="utf-8")
            is_valid, count, comment = validate_xyz_content(content)
            results.append({
                "name": f.name,
                "path": str(f),
                "valid": is_valid,
                "atom_count": count,
                "comment": comment,
            })
        except Exception as e:
            results.append({
                "name": f.name,
                "path": str(f),
                "valid": False,
                "atom_count": 0,
                "comment": f"Error: {e}",
            })
    return results


def save_uploaded_geometries(uploaded_files: Any, target_dir: Path) -> List[Path]:
    """Extracts and writes uploaded geometries supporting ipywidgets v7 and v8 schemas."""
    target_p = Path(target_dir).resolve()
    target_p.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    if isinstance(uploaded_files, dict):
        for fname, item in uploaded_files.items():
            content = item.get("content", b"")
            if isinstance(content, memoryview):
                content = content.tobytes()
            safe_name = Path(fname).name
            dest = target_p / safe_name
            dest.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
            saved_paths.append(dest)
    elif isinstance(uploaded_files, (list, tuple)):
        for item in uploaded_files:
            fname = getattr(item, "name", None) or (item.get("name") if isinstance(item, dict) else "geometry.xyz")
            content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else b"")
            if isinstance(content, memoryview):
                content = content.tobytes()
            safe_name = Path(fname).name
            dest = target_p / safe_name
            dest.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
            saved_paths.append(dest)

    return saved_paths


if not HAS_WATCHDOG:
    class FileSystemEventHandler:  # type: ignore
        pass


class IngestionWatchdog(FileSystemEventHandler):
    """Monitors the active Project directory for new .xyz submissions."""

    def __init__(self, ui_callback: Any) -> None:
        super().__init__()
        self.ui_callback = ui_callback

    def on_created(self, event: Any) -> None:
        if not getattr(event, "is_directory", False) and str(event.src_path).endswith(".xyz"):
            logger.info(f"Watchdog detected new geometry: {event.src_path}")
            self.ui_callback(f"Detected: {Path(event.src_path).name}")



class CoChemMIntUI:
    def __init__(self, default_project: str = "New_Project") -> None:
        if not HAS_WATCHDOG:
            print_status("CRITICAL: 'watchdog' library missing from main environment. Cannot build data bridge.", "fail")

        self.artifact_dir = self._enforce_airgap_path()
        self.observer = None
        self._build_ui(default_project=default_project)

    def _enforce_airgap_path(self) -> Path:
        """Strictly locates or creates the CoChem_Artifacts air-gapped directory."""
        artifact_dir = get_artifact_dir()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    @property
    def current_workspace(self) -> Path:
        """Dynamically generates and returns the active project workspace path."""
        proj_name = sanitize_project_name(self.project_name.value)
        workspace_path = self.artifact_dir / proj_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        return workspace_path

    def _build_ui(self, default_project: str = "New_Project") -> None:
        """Constructs the Jupyter VBox interface."""
        self.out = widgets.Output(layout={'border': '1px solid #ccc', 'padding': '10px', 'height': '200px', 'overflow_y': 'auto'})

        self.title = widgets.HTML("<h2>🧪 CoChem-MInt: Molecular Intake & Canonicalization</h2>")

        self.project_name = widgets.Text(
            value=default_project,
            description='Project Name:',
            style={'description_width': 'initial'},
            tooltip='This creates a dedicated workspace inside CoChem_Artifacts/'
        )
        self.project_name.observe(self._on_project_name_change, names='value')

        self.path_display = widgets.HTML(
            value=f"<span style='color: #4B5563; font-family: monospace; font-size: 0.9em;'>📁 Air-Gapped Target: {self.current_workspace}</span>"
        )

        self.file_upload = widgets.FileUpload(
            accept='.xyz',
            multiple=True,
            description='Drop Geometries',
            button_style='primary'
        )
        self.file_upload.observe(self._on_file_upload, names='value')

        self.molecule_name_input = widgets.Text(
            value='',
            placeholder='e.g., Aspirin or CC(=O)OC1=CC=CC=C1C(=O)O',
            description='Molecule:',
            tooltip='Enter a common name or SMILES string for 3D coordinate generation',
            layout=widgets.Layout(width='400px')
        )

        self.btn_scan = widgets.Button(description="Scan Folder & Canonicalize", button_style="info", icon="search")
        self.btn_build = widgets.Button(description="Build Molecule", button_style="warning", icon="cube")
        self.btn_watch = widgets.Button(description="Start Watchdog", button_style="success", icon="eye")

        self.btn_scan.on_click(self._on_scan_clicked)
        self.btn_build.on_click(self._on_build_clicked)
        self.btn_watch.on_click(self._on_watch_clicked)

        self.config_panel = widgets.VBox([
            widgets.HBox([self.project_name, self.file_upload]),
            self.path_display
        ])

        self.control_panel = widgets.VBox([
            widgets.HBox([self.molecule_name_input, self.btn_build]),
            widgets.HBox([self.btn_scan, self.btn_watch])
        ])

        self.main_ui = widgets.VBox([self.title, self.config_panel, widgets.HTML("<hr>"), self.control_panel, widgets.HTML("<b>Telemetry Console:</b>"), self.out])

    def _on_project_name_change(self, change: Any) -> None:
        """Live-updates the path visualizer when the user types a new project name."""
        new_path = self.current_workspace
        self.path_display.value = f"<span style='color: #4B5563; font-family: monospace; font-size: 0.9em;'>📁 Air-Gapped Target: {new_path}</span>"

    def _ui_log(self, message: str) -> None:
        """Appends logs directly to the widget output area."""
        with self.out:
            logger.info(message)

    def _on_file_upload(self, change: Any) -> None:
        """Intercepts uploaded files, extracts binary content, and writes to workspace."""
        if not change.new:
            return

        workspace = self.current_workspace
        saved = save_uploaded_geometries(change.new, workspace)
        for s in saved:
            self._ui_log(f"📥 Saved geometry: {s.name} -> {workspace}/")

        self.file_upload.value = ()

    def _on_scan_clicked(self, b: Any) -> None:
        workspace = self.current_workspace
        self._ui_log(f"Scanning {workspace} for raw geometries...")

        files = scan_workspace_geometries(workspace)
        if not files:
            self._ui_log("No .xyz files found in the active workspace.")
            return

        self._ui_log(f"Found {len(files)} files. Handoff to Stage 2.0 Ingestor initiated.")

    def _on_build_clicked(self, b: Any) -> None:
        target_name = self.molecule_name_input.value.strip()
        if not target_name:
            self._ui_log("❌ Error: Please enter a SMILES string or Molecule Name.")
            return

        try:
            ws = self.current_workspace
            safe_name = sanitize_project_name(target_name)
            out_path = ws / f"{safe_name}_rdkit.xyz"
            generated = generate_3d_geometry(target_name, output_path=out_path, optimize_mmff=True)
            self._ui_log("✅ 3D Molecule successfully built and saved to the air-gapped vault:")
            self._ui_log(f"   {generated}")
            self._ui_log("➡️ You can now proceed to [Scan & Canonicalize].")
        except Exception as e:
            self._ui_log(f"❌ Error: {e}")

    def _on_watch_clicked(self, b: Any) -> None:
        if not HAS_WATCHDOG:
            self._ui_log("Watchdog module unavailable.")
            return

        workspace = self.current_workspace

        if self.observer and self.observer.is_alive():
            self._ui_log("Stopping Watchdog Daemon...")
            self.observer.stop()
            self.observer.join()
            self.btn_watch.description = "Start Watchdog"
            self.btn_watch.button_style = "success"
        else:
            self._ui_log(f"Starting Watchdog Daemon on {workspace}...")
            event_handler = IngestionWatchdog(self._ui_log)
            self.observer = Observer()  # type: ignore
            self.observer.schedule(event_handler, str(workspace), recursive=False)  # type: ignore
            self.observer.start()  # type: ignore
            self.btn_watch.description = "Stop Watchdog"
            self.btn_watch.button_style = "danger"

    def close(self) -> None:
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def display(self) -> None:
        display(self.main_ui)


if __name__ == "__main__":
    logger.info("CoChem-MInt Backend initialized.")
    logger.info("To launch the GUI, import CoChemMIntUI into a Jupyter Notebook cell and call .display()")

