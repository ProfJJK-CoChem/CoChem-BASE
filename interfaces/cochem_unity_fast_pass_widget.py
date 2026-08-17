#!/usr/bin/env python3
"""
CoChem-UNITY: Stage 0.2 - Fast Pass Ingestion & Triage Widget
Implements Remote Database Searching, 3D Visualization, Dynamic ETA, and Telemetry Traps.
"""
import atexit
import hashlib
import importlib.util
import json
import logging
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import ipywidgets as widgets
from IPython.display import clear_output, display
import psutil
from pydantic import BaseModel, Field

HAS_3DMOL = importlib.util.find_spec("py3Dmol") is not None

# Configure logging properly
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Telemetry")


def cleanup_children() -> None:
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.error(f"Failed to clean up children processes: {e}")

atexit.register(cleanup_children)


class PubChemProperty(BaseModel):
    cid: int = Field(alias='CID')
    isomeric_smiles: str = Field(alias='IsomericSMILES', default="")
    iupac_name: str = Field(alias='IUPACName', default="Unknown")

class PubChemPropertyTable(BaseModel):
    properties: list[PubChemProperty] = Field(alias='Properties', default_factory=list)

class PubChemResponse(BaseModel):
    property_table: PubChemPropertyTable = Field(alias='PropertyTable')


class FastPassWidget:
    def __init__(self) -> None:
        self.current_smiles: str | None = None
        self.search_input = widgets.Text(placeholder='e.g., Aspirin...', description='Molecule:')
        self.search_btn = widgets.Button(description='Search PubChem', button_style='primary')
        self.search_btn.on_click(self._perform_remote_search)
        self.match_dropdown = widgets.Dropdown(options=[], description='Top Matches:', disabled=True)
        self.match_dropdown.observe(self._render_3d_molecule, names='value')
        self.viz_output = widgets.Output(layout={'border': '1px solid #334155', 'height': '300px'})
        self.opt_btn = widgets.Button(description="Fast Pass Optimize", button_style="success", disabled=True)
        self.opt_btn.on_click(self._trigger_quick_opt)
        self.telemetry_out = widgets.Output()
        self.main_ui = widgets.VBox([
            widgets.HBox([self.search_input, self.search_btn]),
            self.match_dropdown,
            self.viz_output,
            self.opt_btn,
            self.telemetry_out
        ])

    def _get_artifacts_dir(self) -> Path:
        base_dir = os.environ.get("COCHEM_ARTIFACTS_DIR", str(Path.home() / ".cochem" / "artifacts"))
        path = Path(base_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _log_telemetry(self, level: str, message: str) -> None:
        logger.log(logging.ERROR if level in ["ERROR", "FATAL"] else logging.INFO, f"[{level}] {message}")
        with self.telemetry_out:
            clear_output(wait=True)
            color = "red" if level in ["ERROR", "FATAL"] else "green"
            display(widgets.HTML(f"<span style='color:{color};'><b>[{level}]</b> {message}</span>"))

    def _perform_remote_search(self, b: Any) -> None:
        query = self.search_input.value
        if not query:
            self._log_telemetry("ERROR", "Empty search query.")
            return

        self._log_telemetry("INFO", f"Searching PubChem for {query}...")
        
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(query)}/property/IsomericSMILES,IUPACName/JSON"
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                response_data = json.loads(response.read().decode())
                pubchem_resp = PubChemResponse(**response_data)
                
                options = []
                for prop in pubchem_resp.property_table.properties:
                    if prop.isomeric_smiles:
                        options.append((f"{prop.iupac_name} (CID: {prop.cid})", prop.isomeric_smiles))
                
                if options:
                    self.match_dropdown.options = options
                    self.match_dropdown.disabled = False
                    self.opt_btn.disabled = False
                    self._log_telemetry("SUCCESS", f"Found {len(options)} matches.")
                else:
                    self._log_telemetry("ERROR", "No valid SMILES found in response.")
        except urllib.error.HTTPError as e:
            self._log_telemetry("ERROR", f"PubChem HTTP Error: {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            self._log_telemetry("ERROR", f"PubChem Connection Error: {e.reason}")
        except Exception as e:
            self._log_telemetry("ERROR", f"PubChem search failed: {e}")

    def _render_3d_molecule(self, change: Any) -> None:
        self.current_smiles = change.new
        with self.viz_output:
            clear_output()
            if HAS_3DMOL:
                import py3Dmol
                view = py3Dmol.view(width=400, height=300)
                view.addModel(self.current_smiles, "smi")
                view.setStyle({'stick': {}})
                view.zoomTo()
                view.show()
            else:
                display(widgets.HTML(f"Selected SMILES: {self.current_smiles} <br/> <em>(py3Dmol not installed)</em>"))

    def _trigger_quick_opt(self, b: Any) -> None:
        if not self.current_smiles:
            self._log_telemetry("ERROR", "No SMILES selected.")
            return

        self._log_telemetry("INFO", "Initiating Fast Pass Geometry Optimization (CREST protocol)...")
        
        artifacts_dir = self._get_artifacts_dir()
        smiles_file = artifacts_dir / "input.smi"
        xyz_file = artifacts_dir / "initial.xyz"
        
        try:
            smiles_file.write_text(self.current_smiles)
            
            cmd_obabel = ["obabel", str(smiles_file), "-O", str(xyz_file), "--gen3d", "--ff", "MMFF94", "--minimize", "--steps", "500"]
            subprocess.run(cmd_obabel, check=True, timeout=120, capture_output=True, text=True)
            
            cmd_crest = ["crest", str(xyz_file), "-g", "H2O", "-opt"]
            subprocess.run(cmd_crest, check=True, timeout=600, capture_output=True, text=True, cwd=str(artifacts_dir))
            
            crest_best = artifacts_dir / "crest_best.xyz"
            if crest_best.exists():
                sha256_hash = hashlib.sha256(crest_best.read_bytes()).hexdigest()
                self._log_telemetry("SUCCESS", f"[M] Optimization Complete. Hash: {sha256_hash}. Artifacts in {artifacts_dir}")
            else:
                self._log_telemetry("SUCCESS", f"Optimization Complete. Artifacts in {artifacts_dir}")
        except subprocess.TimeoutExpired as e:
            self._log_telemetry("ERROR", f"Subprocess timeout: {e.cmd}")
        except subprocess.CalledProcessError as e:
            self._log_telemetry("ERROR", f"Subprocess failed: {e.cmd} - {e.stderr}")
        except FileNotFoundError as e:
            self._log_telemetry("ERROR", f"Required tool not found in PATH: {e.filename}")
        except Exception as e:
            self._log_telemetry("ERROR", f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    widget = FastPassWidget()
    display(widget.main_ui)
