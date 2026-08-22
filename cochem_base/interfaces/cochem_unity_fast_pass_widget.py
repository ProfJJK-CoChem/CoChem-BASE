#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Fast Pass Ingestion & Triage Widget.

Implements Remote Database Searching, 3D Visualization, Dynamic ETA,
and Zero-Mock Telemetry Traps.
"""

from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

import ipywidgets as widgets
from IPython.display import clear_output, display
import psutil
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.config_loader import get_artifact_dir

HAS_3DMOL = importlib.util.find_spec("py3Dmol") is not None
INCHIKEY_REGEX = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z\d]$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-Telemetry")


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


class PubChemProperty(BaseModel):
    """Pydantic model for PubChem compound properties."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    cid: Optional[int] = Field(default=None, alias="CID")
    canonical_smiles: Optional[str] = Field(default=None, alias="CanonicalSMILES")
    isomeric_smiles: Optional[str] = Field(default=None, alias="IsomericSMILES")
    iupac_name: Optional[str] = Field(default=None, alias="IUPACName")
    molecular_formula: Optional[str] = Field(default=None, alias="MolecularFormula")
    molecular_weight: Optional[Union[float, str]] = Field(default=None, alias="MolecularWeight")
    inchikey: Optional[str] = Field(default=None, alias="InChIKey")
    xlogp: Optional[float] = Field(default=None, alias="XLogP")
    tpsa: Optional[float] = Field(default=None, alias="TPSA")
    heavy_atom_count: Optional[int] = Field(default=None, alias="HeavyAtomCount")
    rotatable_bond_count: Optional[int] = Field(default=None, alias="RotatableBondCount")

    @property
    def CID(self) -> Optional[int]:
        return self.cid

    @property
    def CanonicalSMILES(self) -> Optional[str]:
        return self.canonical_smiles or self.isomeric_smiles

    @property
    def IsomericSMILES(self) -> Optional[str]:
        return self.isomeric_smiles or self.canonical_smiles

    @property
    def IUPACName(self) -> Optional[str]:
        return self.iupac_name

    @property
    def MolecularFormula(self) -> Optional[str]:
        return self.molecular_formula

    @property
    def MolecularWeight(self) -> Optional[Union[float, str]]:
        return self.molecular_weight

    @property
    def InChIKey(self) -> Optional[str]:
        return self.inchikey

    @property
    def XLogP(self) -> Optional[float]:
        return self.xlogp

    @property
    def TPSA(self) -> Optional[float]:
        return self.tpsa

    @property
    def HeavyAtomCount(self) -> Optional[int]:
        return self.heavy_atom_count

    @property
    def RotatableBondCount(self) -> Optional[int]:
        return self.rotatable_bond_count


class PubChemPropertyTable(BaseModel):
    """Pydantic container for PubChem properties list."""

    model_config = ConfigDict(populate_by_name=True)

    properties: List[PubChemProperty] = Field(default_factory=list, alias="Properties")

    @property
    def Properties(self) -> List[PubChemProperty]:
        return self.properties


class PubChemResponse(BaseModel):
    """Pydantic model for PubChem PUG REST JSON response."""

    model_config = ConfigDict(populate_by_name=True)

    property_table: PubChemPropertyTable = Field(alias="PropertyTable")

    @property
    def PropertyTable(self) -> PubChemPropertyTable:
        return self.property_table


class FastPassOptConfig(BaseModel):
    """Configuration options for Fast Pass 3D geometry optimization."""

    forcefield: str = "MMFF94"
    steps: int = 500
    use_crest: bool = True
    crest_args: str = "--gfn2"
    timeout_obabel: float = 120.0
    timeout_crest: float = 600.0


class FastPassOptResult(BaseModel):
    """Result report from Fast Pass optimization."""

    success: bool
    smiles: str
    formula: str = ""
    xyz_path: Optional[str] = None
    sha256_hash: str = ""
    num_atoms: int = 0
    duration_seconds: float = 0.0
    message: str = ""
    stage_reached: str = "init"


def build_pubchem_pug_url(query: str) -> Tuple[str, str]:
    """Builds PubChem PUG REST URL and returns (url, query_type)."""
    q = query.strip()
    if not q:
        raise ValueError("[MISSING DATA] Search query is empty.")

    lower_q = q.lower()
    if lower_q.startswith("cid:") or lower_q.startswith("cid="):
        cid_val = q.split(":", 1)[-1].split("=", 1)[-1].strip()
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid_val}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
        return url, "cid"

    if q.isdigit():
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{q}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
        return url, "cid"

    if INCHIKEY_REGEX.match(q):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{urllib.parse.quote(q)}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
        return url, "inchikey"

    if q.startswith("InChI="):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchi/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
        return url, "inchi"

    if lower_q.startswith("smiles:") or lower_q.startswith("smiles="):
        smi_val = q.split(":", 1)[-1].split("=", 1)[-1].strip()
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{urllib.parse.quote(smi_val)}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
        return url, "smiles"

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(q)}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
    return url, "name"


def compute_file_sha256(path: Union[str, Path]) -> str:
    """Computes SHA256 hex digest of a file, returning empty string if missing."""
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def count_xyz_atoms(path: Union[str, Path]) -> int:
    """Counts atoms from an XYZ format file header."""
    p = Path(path)
    if not p.is_file():
        return 0
    try:
        with open(p, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            return int(first_line)
    except Exception:
        return 0


def query_pubchem_pug_rest(query: str) -> PubChemResponse:
    """Queries PubChem PUG REST API for molecule properties."""
    url, _ = build_pubchem_pug_url(query)
    req = urllib.request.Request(url, headers={"User-Agent": "CoChem/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return PubChemResponse.model_validate(data)
    except Exception as e:
        raise RuntimeError(f"PubChem request failed: {e}") from e


def generate_3d_coordinates_obabel(
    smiles: str, output_dir: Path, forcefield: str = "MMFF94", steps: int = 500
) -> Tuple[bool, Optional[Path], str]:
    """Generates 3D coordinates from SMILES using OpenBabel."""
    if not smiles or not smiles.strip():
        return False, None, "[MISSING DATA] SMILES is empty."

    obabel_bin = os.environ.get("OBABEL_CMD") or shutil.which("obabel")
    if not obabel_bin or not shutil.which(obabel_bin):
        return False, None, "[MISSING DATA] OpenBabel binary 'obabel' not found."

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    xyz_out = out_p / "initial.xyz"
    smi_in = out_p / "input.smi"
    smi_in.write_text(smiles.strip(), encoding="utf-8")

    cmd = [
        obabel_bin,
        str(smi_in),
        "-O",
        str(xyz_out),
        "--gen3d",
        "--ff",
        forcefield,
        "--minimize",
        "--steps",
        str(steps),
    ]

    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        if xyz_out.exists():
            return True, xyz_out, "Coordinates generated successfully."
        return False, None, f"OpenBabel produced no output: {res.stderr}"
    except Exception as e:
        return False, None, f"OpenBabel execution failed: {e}"


def run_crest_conformer_triage(
    xyz_file: Path, output_dir: Path, crest_args: str = "--gfn2", timeout: float = 600.0
) -> Tuple[bool, Optional[Path], str]:
    """Runs CREST conformer triage on an input XYZ file."""
    p_xyz = Path(xyz_file)
    if not p_xyz.is_file():
        return False, None, "[MISSING DATA] XYZ file does not exist."

    crest_bin = os.environ.get("CREST_CMD") or shutil.which("crest")
    if not crest_bin or not shutil.which(crest_bin):
        return False, None, "[MISSING DATA] CREST binary 'crest' not found in PATH."

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    cmd = [crest_bin, str(p_xyz)] + crest_args.split() + ["-opt"]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=str(out_p), timeout=timeout)
        best_xyz = out_p / "crest_best.xyz"
        if best_xyz.exists():
            return True, best_xyz, "CREST optimization converged."
        return True, p_xyz, "CREST completed without separate best file."
    except Exception as e:
        return False, None, f"CREST execution error: {e}"


def run_fast_pass_optimization(
    smiles: str, output_dir: Path, config: Optional[FastPassOptConfig] = None
) -> FastPassOptResult:
    """Executes the full Fast Pass optimization pipeline."""
    t0 = time.time()
    cfg = config or FastPassOptConfig()

    if not smiles or not smiles.strip():
        return FastPassOptResult(
            success=False,
            smiles=smiles,
            message="[MISSING DATA] Empty SMILES provided.",
            stage_reached="failed",
            duration_seconds=round(time.time() - t0, 2),
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 3D coordinate generation via obabel
    ok, xyz_path, msg = generate_3d_coordinates_obabel(
        smiles, out_dir, forcefield=cfg.forcefield, steps=cfg.steps
    )
    if not ok or xyz_path is None:
        return FastPassOptResult(
            success=False,
            smiles=smiles,
            message=msg,
            stage_reached="failed",
            duration_seconds=round(time.time() - t0, 2),
        )

    final_xyz = xyz_path
    stage = "obabel_gen3d"

    # 2. CREST optimization
    if cfg.use_crest:
        crest_ok, crest_path, crest_msg = run_crest_conformer_triage(
            xyz_path, out_dir, crest_args=cfg.crest_args, timeout=cfg.timeout_crest
        )
        if crest_ok and crest_path is not None:
            final_xyz = crest_path
            stage = "crest_opt"

    num_atoms = count_xyz_atoms(final_xyz)
    sha_hash = compute_file_sha256(final_xyz)

    return FastPassOptResult(
        success=True,
        smiles=smiles,
        xyz_path=str(final_xyz),
        sha256_hash=sha_hash,
        num_atoms=num_atoms,
        duration_seconds=round(time.time() - t0, 2),
        message="Fast Pass optimization completed successfully.",
        stage_reached=stage,
    )


class FastPassWidget:
    """Consolidated Fast Pass Ingestion and 3D Triage Jupyter Widget."""

    def __init__(self) -> None:
        self.artifact_dir = get_artifact_dir()
        self.current_smiles: Optional[str] = None
        self.current_title: Optional[str] = None
        self.current_property: Optional[PubChemProperty] = None

        self.header_label = widgets.HTML("<h2>🧪 CoChem-UNITY: Fast Pass Ingestion & Triage</h2>")
        self.search_input = widgets.Text(
            placeholder="e.g. Aspirin, 2244, BSYNRYMUTXBXSQ-UHFFFAOYSA-N...",
            description="Molecule:",
            layout=widgets.Layout(width="350px"),
        )
        self.search_btn = widgets.Button(description="Search PubChem", button_style="primary", icon="search")
        self.search_btn.on_click(self._perform_remote_search)

        self.clear_btn = widgets.Button(description="Clear", button_style="warning", icon="trash")
        self.clear_btn.on_click(self._on_clear_clicked)

        self.match_dropdown = widgets.Dropdown(options=[], description="Matches:", disabled=True, layout=widgets.Layout(width="450px"))
        self.match_dropdown.observe(self._render_3d_molecule, names="value")

        self.viz_output = widgets.Output(layout={"border": "1px solid #334155", "height": "300px"})
        self.property_card_out = widgets.Output(layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "300px", "overflow_y": "auto"})
        self.coord_preview_out = widgets.Output(layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "300px", "overflow_y": "auto"})

        self.display_tabs = widgets.Tab(children=[self.viz_output, self.property_card_out, self.coord_preview_out])
        self.display_tabs.set_title(0, "3D View")
        self.display_tabs.set_title(1, "Properties")
        self.display_tabs.set_title(2, "Coordinates")

        self.forcefield_dd = widgets.Dropdown(options=["MMFF94", "UFF", "GAFF"], value="MMFF94", description="Forcefield:")
        self.steps_slider = widgets.IntSlider(value=500, min=100, max=5000, step=100, description="Steps:")
        self.crest_toggle = widgets.Checkbox(value=True, description="Enable CREST")

        self.opt_btn = widgets.Button(description="Fast Pass Optimize", button_style="success", icon="bolt", disabled=True)
        self.opt_btn.on_click(self._trigger_quick_opt)

        self.telemetry_out = widgets.Output()

        controls = widgets.HBox([self.search_input, self.search_btn, self.clear_btn])
        opt_controls = widgets.HBox([self.forcefield_dd, self.steps_slider, self.crest_toggle, self.opt_btn])

        self.main_ui = widgets.VBox([
            self.header_label,
            controls,
            self.match_dropdown,
            self.display_tabs,
            opt_controls,
            self.telemetry_out,
        ])

    def _log_telemetry(self, level: str, message: str) -> None:
        if level in ["ERROR", "FATAL"]:
            logger.error(message)
        else:
            logger.info(message)
        with self.telemetry_out:
            clear_output(wait=True)
            color_map = {"SUCCESS": "green", "INFO": "blue", "WARNING": "orange", "ERROR": "red", "FATAL": "darkred"}
            color = color_map.get(level.upper(), "black")
            display(widgets.HTML(f"<span style='color:{color}; font-weight:bold;'>[{level}]</span> {message}"))

    def _perform_remote_search(self, b: Any) -> None:
        query = self.search_input.value.strip()
        if not query:
            self._log_telemetry("ERROR", "[MISSING DATA] Search query is empty.")
            self.opt_btn.disabled = True
            return

        self._log_telemetry("INFO", f"Searching PubChem for '{query}'...")
        try:
            resp = query_pubchem_pug_rest(query)
            props = resp.property_table.properties
            if not props:
                self._log_telemetry("ERROR", f"No properties found for '{query}'")
                self.opt_btn.disabled = True
                return

            options = []
            for p in props:
                smi = p.CanonicalSMILES or p.IsomericSMILES
                if smi:
                    title = f"{p.IUPACName or 'Compound'} (CID: {p.CID})"
                    options.append((title, smi))

            if options:
                self.match_dropdown.options = options
                self.match_dropdown.disabled = False
                self.opt_btn.disabled = False
                self.current_smiles = options[0][1]
                self.current_title = options[0][0]
                self.current_property = props[0]
                self._render_properties_card(props[0])
                self._log_telemetry("SUCCESS", f"Found {len(options)} matches in PubChem.")
            else:
                self._log_telemetry("ERROR", "No valid SMILES found in response.")
                self.opt_btn.disabled = True
        except Exception as e:
            self._log_telemetry("ERROR", f"Search failed: {e}")
            self.opt_btn.disabled = True

    def _on_clear_clicked(self, b: Any) -> None:
        self.search_input.value = ""
        self.match_dropdown.options = []
        self.match_dropdown.disabled = True
        self.opt_btn.disabled = True
        self.current_smiles = None
        self.current_title = None
        self.current_property = None
        with self.viz_output:
            clear_output()
        with self.property_card_out:
            clear_output()
        with self.coord_preview_out:
            clear_output()
        with self.telemetry_out:
            clear_output()

    def _render_3d_molecule(self, change: Any) -> None:
        val = change.get("new") if isinstance(change, dict) else change
        if not val:
            return
        self.current_smiles = str(val)
        with self.viz_output:
            clear_output()
            if HAS_3DMOL:
                try:
                    import py3Dmol
                    view = py3Dmol.view(width=400, height=280)
                    view.addModel(self.current_smiles, "smi")
                    view.setStyle({"stick": {}})
                    view.zoomTo()
                    view.show()
                except Exception:
                    display(widgets.HTML(f"<b>Selected SMILES:</b> <code>{self.current_smiles}</code>"))
            else:
                display(widgets.HTML(f"<b>Selected SMILES:</b> <code>{self.current_smiles}</code> <br/><i>(py3Dmol not installed)</i>"))

    def _render_properties_card(self, prop: Optional[PubChemProperty]) -> None:
        with self.property_card_out:
            clear_output()
            if not prop:
                display(widgets.HTML("<i>No property metadata available.</i>"))
                return
            html = f"""
            <h4>PubChem Metadata (CID: {prop.CID})</h4>
            <ul>
                <li><b>IUPAC Name:</b> {prop.IUPACName or 'N/A'}</li>
                <li><b>Formula:</b> {prop.MolecularFormula or 'N/A'}</li>
                <li><b>Molecular Weight:</b> {prop.MolecularWeight or 'N/A'}</li>
                <li><b>InChIKey:</b> {prop.InChIKey or 'N/A'}</li>
                <li><b>Heavy Atoms:</b> {prop.HeavyAtomCount or 'N/A'}</li>
                <li><b>Rotatable Bonds:</b> {prop.RotatableBondCount or 'N/A'}</li>
                <li><b>TPSA:</b> {prop.TPSA or 'N/A'}</li>
                <li><b>XLogP:</b> {prop.XLogP or 'N/A'}</li>
            </ul>
            """
            display(widgets.HTML(html))

    def _render_coord_preview(self, coord_path: Path) -> None:
        with self.coord_preview_out:
            clear_output()
            p = Path(coord_path)
            if not p.is_file():
                display(widgets.HTML("<i>No coordinates generated yet.</i>"))
                return
            content = p.read_text(encoding="utf-8")
            display(widgets.HTML(f"<pre style='font-size: 0.85em;'>{content}</pre>"))

    def _trigger_quick_opt(self, b: Any) -> None:
        if not self.current_smiles:
            self._log_telemetry("ERROR", "No SMILES selected for optimization.")
            return

        self._execute_optimization(self.current_smiles)

    def _execute_optimization(self, smiles: str) -> None:
        self._log_telemetry("INFO", "Initiating Fast Pass Optimization...")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        smi_file = self.artifact_dir / "input.smi"
        smi_file.write_text(smiles.strip(), encoding="utf-8")

        cfg = FastPassOptConfig(
            forcefield=self.forcefield_dd.value,
            steps=self.steps_slider.value,
            use_crest=self.crest_toggle.value,
        )

        res = run_fast_pass_optimization(smiles, self.artifact_dir, cfg)
        if res.success:
            self._log_telemetry("SUCCESS", f"Optimization Complete! Hash: {res.sha256_hash[:16]}... Atoms: {res.num_atoms}")
            if res.xyz_path:
                self._render_coord_preview(Path(res.xyz_path))
        else:
            self._log_telemetry("ERROR", f"Optimization failed: {res.message}")

    def display(self) -> None:
        display(self.main_ui)


if __name__ == "__main__":
    w = FastPassWidget()
    w.display()
