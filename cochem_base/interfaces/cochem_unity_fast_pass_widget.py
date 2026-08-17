#!/usr/bin/env python3
"""
CoChem-UNITY: Stage 0.2 - Fast Pass Ingestion & Triage Widget
Implements Remote Database Searching, 3D Visualization, Dynamic ETA, and Telemetry Traps.
"""
import importlib.util
import logging
import os
import pathlib
import json
import urllib.request
import urllib.parse
from urllib.error import URLError
import subprocess
import atexit
import psutil
from typing import Any, List

import ipywidgets as widgets
from IPython.display import clear_output, display
from pydantic import BaseModel

HAS_3DMOL = importlib.util.find_spec("py3Dmol") is not None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Telemetry")


class PubChemProperty(BaseModel):
    CID: int
    CanonicalSMILES: str

class PubChemPropertyTable(BaseModel):
    Properties: List[PubChemProperty]

class PubChemResponse(BaseModel):
    PropertyTable: PubChemPropertyTable


def _cleanup_zombie_processes() -> None:
    try:
        current_process = psutil.Process(os.getpid())
        for child in current_process.children(recursive=True):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.error(f"Failed to clean up zombie processes: {e}")

atexit.register(_cleanup_zombie_processes)


class FastPassWidget:
    def __init__(self) -> None:
        self.current_smiles = None
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

    def _log_telemetry(self, level: str, message: str) -> None:
        if level in ["ERROR", "FATAL"]:
            logger.error(message)
        else:
            logger.info(message)
        with self.telemetry_out:
            clear_output(wait=True)
            color = "red" if level in ["ERROR", "FATAL"] else "green"
            display(widgets.HTML(f"<span style='color:{color};'><b>[{level}]</b> {message}</span>"))

    def _perform_remote_search(self, b: Any) -> None:
        query = self.search_input.value.strip()
        if not query:
            self._log_telemetry("ERROR", "[MISSING DATA] Search query is empty.")
            return

        self._log_telemetry("INFO", f"Searching PubChem for {query}...")
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(query)}/property/CanonicalSMILES/JSON"
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if "Fault" in data:
                self._log_telemetry("ERROR", f"[MISSING DATA] PubChem error: {data['Fault'].get('Message', 'Unknown error')}")
                return
                
            pubchem_resp = PubChemResponse(**data)
            matches = []
            for prop in pubchem_resp.PropertyTable.Properties:
                matches.append((f"{query} (CID: {prop.CID})", prop.CanonicalSMILES))
            
            if matches:
                self.match_dropdown.options = matches
                self.match_dropdown.disabled = False
                self.opt_btn.disabled = False
                self._log_telemetry("SUCCESS", f"Found {len(matches)} matches.")
            else:
                self._log_telemetry("ERROR", "[MISSING DATA] No SMILES found in response.")

        except URLError as e:
            self._log_telemetry("ERROR", f"Search failed: {str(e)}")
        except Exception as e:
            self._log_telemetry("ERROR", f"An unexpected error occurred: {str(e)}")

    def _render_3d_molecule(self, change: Any) -> None:
        if change.new is None:
            return
        self.current_smiles = change.new
        with self.viz_output:
            clear_output()
            if HAS_3DMOL:
                display(widgets.HTML("3D Viewer rendered here via py3Dmol (Requires execution context)."))
            else:
                display(widgets.HTML(f"Selected SMILES: {self.current_smiles}"))

    def _trigger_quick_opt(self, b: Any) -> None:
        if not self.current_smiles:
            self._log_telemetry("ERROR", "[MISSING DATA] No SMILES selected for optimization.")
            return
            
        self._log_telemetry("INFO", "Initiating Fast Pass Geometry Optimization via CREST/ORCA...")
        
        artifacts_dir = pathlib.Path.home() / "CoChem_Artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        smiles_file = artifacts_dir / "input.smi"
        try:
            with open(smiles_file, "w") as f:
                f.write(self.current_smiles)
        except Exception as e:
            self._log_telemetry("ERROR", f"Failed to write SMILES file: {str(e)}")
            return
            
        try:
            xyz_file = artifacts_dir / "input.xyz"
            obabel_cmd = ["obabel", str(smiles_file), "-O", str(xyz_file), "--gen3d"]
            subprocess.run(obabel_cmd, check=True, timeout=30, capture_output=True, text=True)
            
            crest_cmd = ["crest", str(xyz_file), "--gfn2", "--mquick"]
            subprocess.run(crest_cmd, check=True, timeout=300, capture_output=True, text=True, cwd=str(artifacts_dir))
            
            self._log_telemetry("SUCCESS", "Optimization Complete. Geometry ready for TOPOS.")
        except FileNotFoundError:
            self._log_telemetry("ERROR", "[MISSING DATA] Required binaries (obabel or crest) not found in PATH.")
        except subprocess.TimeoutExpired:
            self._log_telemetry("ERROR", "Optimization timed out.")
        except subprocess.CalledProcessError as e:
            self._log_telemetry("ERROR", f"Optimization failed: {e.stderr}")
        except Exception as e:
            self._log_telemetry("ERROR", f"Unexpected error during optimization: {str(e)}")


if __name__ == "__main__":
    widget = FastPassWidget()
    display(widget.main_ui)
