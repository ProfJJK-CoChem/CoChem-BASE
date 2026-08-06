#!/usr/bin/env python3
"""
CoChem-CORE: Stage 1.x - Consolidated Molecular Intake Backend
Module: intake/CoChem-MInt.py
Purpose: Jupyter-native unified GUI for directory scanning, structural 
         canonicalization, and real-time watchdog monitoring.
         STRICT AIR-GAP: Forcibly routes all workspaces to CoChem_Artifacts.
"""

import os
import sys
import json
import time
import threading
import logging
import subprocess
import importlib
import site
import urllib.request
import urllib.parse
from pathlib import Path

# --- Dynamic Dependency Trap ---
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    print("➡️ 'watchdog' library missing. Triggering inline installation...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "watchdog"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        importlib.invalidate_caches()
        importlib.reload(site)
        
        # Dynamically inject into globals to satisfy class inheritance parsing
        watchdog_events = importlib.import_module('watchdog.events')
        watchdog_observers = importlib.import_module('watchdog.observers')
        globals()['FileSystemEventHandler'] = watchdog_events.FileSystemEventHandler
        globals()['Observer'] = watchdog_observers.Observer
        
        HAS_WATCHDOG = True
        print("✅ Watchdog bootstrap completed.")
    except Exception as e:
        HAS_WATCHDOG = False
        print(f"⚠️ Watchdog bootstrap failed: {e}. Running in degraded mode.")

import ipywidgets as widgets
from IPython.display import display, clear_output

# =====================================================================
# TELEMETRY & LOGGING
# =====================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-MInt")

def print_status(msg: str, status: str = "info") -> None:
    """Jupyter-safe HTML status printer."""
    colors = {"success": "green", "warning": "orange", "fail": "red", "info": "blue"}
    color = colors.get(status, "black")
    display(widgets.HTML(f"<span style='color:{color}; font-weight:bold;'>[{status.upper()}]</span> {msg}"))

# =====================================================================
# WATCHDOG EVENT HANDLER
# =====================================================================
# Define a dummy class if watchdog failed to load, preventing NameError
if not HAS_WATCHDOG:
    class FileSystemEventHandler:
        pass

class IngestionWatchdog(FileSystemEventHandler):
    """Monitors the active Project directory for new .xyz submissions."""
    
    def __init__(self, ui_callback):
        if HAS_WATCHDOG:
            super().__init__()
        self.ui_callback = ui_callback

    def on_created(self, event):
        if HAS_WATCHDOG and not event.is_directory and event.src_path.endswith('.xyz'):
            logger.info(f"Watchdog detected new geometry: {event.src_path}")
            self.ui_callback(f"Detected: {Path(event.src_path).name}")

# =====================================================================
# UNIFIED MINT GUI CLASS
# =====================================================================
class CoChemMIntUI:
    def __init__(self):
        if not HAS_WATCHDOG:
            print_status("CRITICAL: 'watchdog' library missing from main environment. Cannot build data bridge.", "fail")
            
        # Strictly enforce the Air-Gap (Never allow CWD/Repo target)
        self.artifact_dir = self._enforce_airgap_path()
        self.observer = None
        self._build_ui()

    def _enforce_airgap_path(self) -> Path:
        """Strictly locates or creates the CoChem_Artifacts air-gapped directory."""
        # 1. Prefer explicit environmental override
        env_target = os.environ.get("COCHEM_ARTIFACT_DIR")
        if env_target:
            target = Path(env_target)
            target.mkdir(parents=True, exist_ok=True)
            return target

        # 2. Check explicitly mounted DevContainer volumes
        dev_target = Path("/workspaces/CoChem_Artifacts")
        if Path("/workspaces").exists():
            dev_target.mkdir(parents=True, exist_ok=True)
            return dev_target
            
        # 3. Fallback to Local Home Directory (Standard Linux/Windows WSL)
        local_target = Path.home() / "CoChem_Artifacts"
        local_target.mkdir(parents=True, exist_ok=True)
        return local_target

    @property
    def current_workspace(self) -> Path:
        """Dynamically generates and returns the active project workspace path."""
        proj_name = self.project_name.value.strip().replace(" ", "_")
        if not proj_name:
            proj_name = "Unnamed_Project"
            
        workspace_path = self.artifact_dir / proj_name
        workspace_path.mkdir(parents=True, exist_ok=True)
        return workspace_path

    def _build_ui(self):
        """Constructs the Jupyter VBox interface."""
        self.out = widgets.Output(layout={'border': '1px solid #ccc', 'padding': '10px', 'height': '200px', 'overflow_y': 'auto'})
        
        self.title = widgets.HTML("<h2>🧪 CoChem-MInt: Molecular Intake & Canonicalization</h2>")
        
        # Dynamic Project Query
        self.project_name = widgets.Text(
            value='New_Project', 
            description='Project Name:', 
            style={'description_width': 'initial'},
            tooltip='This creates a dedicated workspace inside CoChem_Artifacts/'
        )
        self.project_name.observe(self._on_project_name_change, names='value')

        # Live Path visualizer
        self.path_display = widgets.HTML(
            value=f"<span style='color: #4B5563; font-family: monospace; font-size: 0.9em;'>📁 Air-Gapped Target: {self.current_workspace}</span>"
        )
        
        # Drag and Drop Uploader
        self.file_upload = widgets.FileUpload(
            accept='.xyz', 
            multiple=True, 
            description='Drop Geometries', 
            button_style='primary'
        )
        self.file_upload.observe(self._on_file_upload, names='value')

        # Molecule Target Input
        self.molecule_name_input = widgets.Text(
            value='',
            placeholder='e.g., Aspirin or CC(=O)OC1=CC=CC=C1C(=O)O',
            description='Molecule:',
            tooltip='Enter a common name or SMILES string for 3D coordinate generation',
            layout=widgets.Layout(width='400px')
        )

        # Action Buttons
        self.btn_scan = widgets.Button(description="Scan Folder & Canonicalize", button_style="info", icon="search")
        self.btn_build = widgets.Button(description="Build Molecule", button_style="warning", icon="cube")
        self.btn_watch = widgets.Button(description="Start Watchdog", button_style="success", icon="eye")
        
        self.btn_scan.on_click(self._on_scan_clicked)
        self.btn_build.on_click(self._on_build_clicked)
        self.btn_watch.on_click(self._on_watch_clicked)
        
        # Layout Assembly
        self.config_panel = widgets.VBox([
            widgets.HBox([self.project_name, self.file_upload]),
            self.path_display
        ])
        
        self.control_panel = widgets.VBox([
            widgets.HBox([self.molecule_name_input, self.btn_build]),
            widgets.HBox([self.btn_scan, self.btn_watch])
        ])
        
        self.main_ui = widgets.VBox([self.title, self.config_panel, widgets.HTML("<hr>"), self.control_panel, widgets.HTML("<b>Telemetry Console:</b>"), self.out])

    def _on_project_name_change(self, change):
        """Live-updates the path visualizer when the user types a new project name."""
        new_path = self.current_workspace
        self.path_display.value = f"<span style='color: #4B5563; font-family: monospace; font-size: 0.9em;'>📁 Air-Gapped Target: {new_path}</span>"

    def _ui_log(self, message: str):
        """Appends logs directly to the widget output area."""
        with self.out:
            print(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _on_file_upload(self, change):
        """Intercepts uploaded files, extracts binary content, and writes to workspace."""
        if not change.new:
            return
            
        workspace = self.current_workspace
        
        for item in change.new:
            # Handle ipywidgets 8.x dict structures safely
            try:
                if isinstance(item, dict):
                    f_name = item['name']
                    content = item['content']
                else:
                    f_name = item.name
                    content = item.content
                
                f_path = workspace / f_name
                with open(f_path, "wb") as f:
                    f.write(content)
                self._ui_log(f"📥 Saved geometry: {f_name} -> {workspace}/")
                
            except Exception as e:
                self._ui_log(f"❌ Error saving file: {e}")
                
        # Clear the widget cache so the user can upload the same filename again if needed
        self.file_upload.value = ()

    def _on_scan_clicked(self, b):
        workspace = self.current_workspace
        self._ui_log(f"Scanning {workspace} for raw geometries...")
        
        files = list(workspace.glob("*.xyz"))
        if not files:
            self._ui_log("No .xyz files found in the active workspace.")
            return
            
        self._ui_log(f"Found {len(files)} files. Handoff to Stage 2.0 Ingestor initiated.")
        # In a full run, this triggers cochem_stage2_ingestor.py's ThreadPool

    def _on_build_clicked(self, b):
        target_name = self.molecule_name_input.value.strip()
        if not target_name:
            self._ui_log("❌ Error: Please enter a SMILES string or Molecule Name.")
            return

        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
        except ImportError:
            self._ui_log("❌ Error: RDKit is not installed in the active micro-silo.")
            self._ui_log("   Please execute 'conda install -c conda-forge rdkit' or route through the PLAY environment.")
            return

        self._ui_log(f"⚙️ Building 3D geometry for: {target_name}...")
        smiles = target_name
        
        # Heuristic: If it has no standard SMILES syntax characters, attempt remote resolution via NIH
        if not any(char in target_name for char in ['=', '#', '(', ')', '[', ']', '1', '2']):
            self._ui_log(f"🔍 Attempting to resolve common name '{target_name}' to SMILES via NIH Cactus API...")
            try:
                url = f"https://cactus.nci.nih.gov/chemical/structure/{urllib.parse.quote(target_name)}/smiles"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as response:
                    smiles = response.read().decode('utf8').strip()
                self._ui_log(f"✅ Resolved to SMILES: {smiles}")
            except Exception as e:
                self._ui_log(f"❌ API Fetch Failed for '{target_name}'. Please manually enter a valid SMILES string.")
                return

        # RDKit Graph Generation
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            self._ui_log(f"❌ Error: RDKit could not mathematically parse the SMILES string: {smiles}")
            return

        self._ui_log("➡️ Saturating valencies with Hydrogens...")
        mol = Chem.AddHs(mol)
        
        self._ui_log("➡️ Generating 3D spatial conformer (ETKDGv3)...")
        # ETKDGv3 is the most rigorous modern embedding algorithm in RDKit
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        AllChem.EmbedMolecule(mol, params)
        
        self._ui_log("➡️ Relaxing steric clashes (MMFF94 Forcefield)...")
        AllChem.MMFFOptimizeMolecule(mol)

        # File I/O constraints applied
        ws = self.current_workspace
        safe_name = "".join([c if c.isalnum() else "_" for c in target_name])
        out_path = ws / f"{safe_name}_rdkit.xyz"
        
        Chem.MolToXYZFile(mol, str(out_path))
        self._ui_log(f"✅ 3D Molecule successfully built and saved to the air-gapped vault:")
        self._ui_log(f"   {out_path}")
        self._ui_log("➡️ You can now proceed to [Scan & Canonicalize].")

    def _on_watch_clicked(self, b):
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
            self.observer = Observer()
            self.observer.schedule(event_handler, str(workspace), recursive=False)
            self.observer.start()
            self.btn_watch.description = "Stop Watchdog"
            self.btn_watch.button_style = "danger"

    def display(self):
        display(self.main_ui)

if __name__ == "__main__":
    print("CoChem-MInt Backend initialized.")
    print("To launch the GUI, import CoChemMIntUI into a Jupyter Notebook cell and call .display()")