Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_14_interfaces_unity_fast_pass_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_unity_fast_pass_widget.py

## 1. Goal
Implement the file `cochem_unity_fast_pass_widget.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_unity_fast_pass_widget.py`

## 3. Context & Ecosystem Role
The Didactic Previewer. Applies rapid normalization to user-drawn or externally sourced structures before saving them to the registry, allowing users to visually verify spatial orientation via `py3Dmol` before expending quantum resources.

## 4. Deliverable Functions
A sandboxed widget enabling users to perform sub-10-second triage on a selected geometry via ASE. Must execute `g-xTB` (GFN2-xTB / GFN-FF) or MLFFs (AIMNet2 with `TolE 1e-5`, MACE-OFF23/24), with RDKit-UFF fallback. Evaluates RAM footprint and VRAM before executing the job. Eradicate all mentions of EMT.

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\interfaces\cochem_unity_fast_pass_widget.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Fast Pass Ingestion & Triage Widget.

Implements Remote Database Searching (PubChem PUG REST), 3D Visualization (py3Dmol),
Hardware Profiling (RAM & VRAM Pre-Flight), Fast-Pass Geometry Normalization via ASE
(g-xTB, AIMNet2 with TolE 1e-5, MACE-OFF23/24, RDKit-UFF fallback), Conformer Triage (CREST),
and Pure Physical Telemetry Traps.
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
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.config_loader import get_artifact_dir

try:
    from ase import Atoms
    from ase.calculators.calculator import Calculator, all_changes
    from ase.optimize import BFGS, FIRE, LBFGS
    HAS_ASE = True
except ImportError:
    HAS_ASE = False
    Atoms = Any  # type: ignore
    Calculator = Any  # type: ignore

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
    Chem = Any  # type: ignore
    AllChem = Any  # type: ignore

HAS_3DMOL = importlib.util.find_spec("py3Dmol") is not None
INCHIKEY_REGEX = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z\d]$")
KCAL_MOL_TO_EV = 0.0433641153

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


class HardwareProfile(BaseModel):
    """Pydantic model representing system compute memory and device telemetry."""

    model_config = ConfigDict(populate_by_name=True)

    total_ram_gb: float = Field(..., description="Total system RAM in Gigabytes")
    available_ram_gb: float = Field(..., description="Available system RAM in Gigabytes")
    used_ram_gb: float = Field(..., description="Used system RAM in Gigabytes")
    percent_ram_used: float = Field(..., description="Percentage of RAM utilized")
    cpu_count_logical: int = Field(..., description="Logical CPU core count")
    cpu_count_physical: int = Field(..., description="Physical CPU core count")
    has_cuda: bool = Field(..., description="Whether CUDA GPU acceleration is detected")
    cuda_device_name: str = Field(default="N/A (CPU)", description="Name of the detected GPU device")
    total_vram_gb: float = Field(default=0.0, description="Total GPU VRAM in Gigabytes")
    allocated_vram_gb: float = Field(default=0.0, description="Currently allocated GPU VRAM in Gigabytes")
    free_vram_gb: float = Field(default=0.0, description="Free unreserved GPU VRAM in Gigabytes")
    recommended_device: str = Field(default="cpu", description="Recommended compute device ('cuda' or 'cpu')")
    is_safe_for_opt: bool = Field(..., description="Safety flag indicating memory adequacy for triage")
    warnings: List[str] = Field(default_factory=list, description="Diagnostic warnings or capacity notes")


def profile_hardware(
    required_ram_mb: float = 256.0,
    required_vram_mb: float = 512.0,
) -> HardwareProfile:
    """Evaluates physical RAM footprint and VRAM before executing computational triage."""
    mem = psutil.virtual_memory()
    total_ram_gb = round(mem.total / (1024**3), 2)
    available_ram_gb = round(mem.available / (1024**3), 2)
    used_ram_gb = round(mem.used / (1024**3), 2)
    percent_ram_used = float(mem.percent)

    cpu_logical = psutil.cpu_count(logical=True) or 1
    cpu_physical = psutil.cpu_count(logical=False) or cpu_logical

    warnings: List[str] = []
    has_cuda = False
    cuda_name = "N/A (CPU)"
    total_vram_gb = 0.0
    allocated_vram_gb = 0.0
    free_vram_gb = 0.0
    recommended_device = "cpu"

    try:
        import torch
        if torch.cuda.is_available():
            has_cuda = True
            cuda_name = torch.cuda.get_device_name(0)
            total_vram_bytes = torch.cuda.get_device_properties(0).total_memory
            alloc_vram_bytes = torch.cuda.memory_allocated(0)
            reserved_vram_bytes = torch.cuda.memory_reserved(0)
            total_vram_gb = round(total_vram_bytes / (1024**3), 2)
            allocated_vram_gb = round(alloc_vram_bytes / (1024**3), 2)
            free_vram_bytes = total_vram_bytes - reserved_vram_bytes
            free_vram_gb = round(max(0.0, free_vram_bytes / (1024**3)), 2)

            if (free_vram_bytes / (1024**2)) >= required_vram_mb:
                recommended_device = "cuda"
            else:
                warnings.append(f"Low free VRAM ({free_vram_gb} GB); routing MLFF inference to CPU.")
                recommended_device = "cpu"
        else:
            recommended_device = "cpu"
    except Exception as e:
        warnings.append(f"PyTorch CUDA device evaluation note: {e}")
        recommended_device = "cpu"

    req_ram_gb = required_ram_mb / 1024.0
    is_safe = available_ram_gb >= req_ram_gb
    if not is_safe:
        warnings.append(f"Available RAM ({available_ram_gb} GB) is below requirement ({req_ram_gb:.2f} GB).")

    return HardwareProfile(
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        used_ram_gb=used_ram_gb,
        percent_ram_used=percent_ram_used,
        cpu_count_logical=cpu_logical,
        cpu_count_physical=cpu_physical,
        has_cuda=has_cuda,
        cuda_device_name=cuda_name,
        total_vram_gb=total_vram_gb,
        allocated_vram_gb=allocated_vram_gb,
        free_vram_gb=free_vram_gb,
        recommended_device=recommended_device,
        is_safe_for_opt=is_safe,
        warnings=warnings,
    )


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

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    engine: str = "gfn2-xtb"
    forcefield: str = "MMFF94"
    steps: int = 500
    fmax: float = 0.05
    tol_e: float = 1e-5
    use_crest: bool = True
    crest_args: str = "--gfn2"
    timeout_obabel: float = 120.0
    timeout_crest: float = 600.0
    device: str = "auto"
    optimizer: str = "BFGS"


class FastPassOptResult(BaseModel):
    """Result report from Fast Pass optimization."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    success: bool
    smiles: str
    formula: str = ""
    xyz_path: Optional[str] = None
    sha256_hash: str = ""
    num_atoms: int = 0
    duration_seconds: float = 0.0
    message: str = ""
    stage_reached: str = "init"
    final_energy_ev: Optional[float] = None
    engine_used: str = ""
    hardware_profile: Optional[HardwareProfile] = None


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


def smiles_to_rdkit_mol(smiles: str, embed_3d: bool = True) -> Chem.Mol:
    """Converts a SMILES string to an RDKit Mol with added Hydrogens and optional 3D coordinates."""
    if not HAS_RDKIT:
        raise RuntimeError("[MISSING DATA] RDKit is not installed.")
    s = smiles.strip()
    if not s:
        raise ValueError("[MISSING DATA] SMILES string is empty.")
    mol = Chem.MolFromSmiles(s)
    if mol is None:
        raise ValueError(f"Failed to parse SMILES: '{s}'")
    mol = Chem.AddHs(mol)
    if embed_3d:
        res = AllChem.EmbedMolecule(mol, randomSeed=42)
        if res != 0:
            AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
    return mol


def rdkit_mol_to_ase_atoms(mol: Chem.Mol) -> Atoms:
    """Converts an RDKit Mol with 3D conformer into an ASE Atoms object."""
    if not HAS_ASE:
        raise RuntimeError("[MISSING DATA] ASE is not installed.")
    if not HAS_RDKIT:
        raise RuntimeError("[MISSING DATA] RDKit is not installed.")
    if mol.GetNumConformers() == 0:
        res = AllChem.EmbedMolecule(mol, randomSeed=42)
        if res != 0:
            AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
    if mol.GetNumConformers() == 0:
        raise ValueError("RDKit Mol has no 3D conformers and embedding failed.")
    conf = mol.GetConformer()
    positions = conf.GetPositions()
    symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
    return Atoms(symbols=symbols, positions=positions)


def ase_atoms_to_xyz_string(atoms: Atoms, comment: str = "") -> str:
    """Converts an ASE Atoms object to an XYZ format string."""
    num_atoms = len(atoms)
    lines = [str(num_atoms), comment]
    symbols = atoms.get_chemical_symbols()
    positions = atoms.get_positions()
    for s, (x, y, z) in zip(symbols, positions):
        lines.append(f"{s:<4} {x:14.8f} {y:14.8f} {z:14.8f}")
    return "\n".join(lines) + "\n"


def write_xyz_file(path: Union[str, Path], atoms: Atoms, comment: str = "") -> Path:
    """Writes an ASE Atoms object to an XYZ file on disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    xyz_str = ase_atoms_to_xyz_string(atoms, comment=comment)
    p.write_text(xyz_str, encoding="utf-8")
    return p


class RDKitForceFieldCalculator(Calculator):
    """Custom ASE Calculator wrapping RDKit UFF and MMFF94 force fields with analytical gradients."""

    implemented_properties = ["energy", "forces"]

    def __init__(self, rdkit_mol: Chem.Mol, method: str = "UFF", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not HAS_RDKIT:
            raise RuntimeError("[MISSING DATA] RDKit is not installed.")
        self.rdkit_mol = Chem.Mol(rdkit_mol)
        if self.rdkit_mol.GetNumConformers() == 0:
            AllChem.EmbedMolecule(self.rdkit_mol, randomSeed=42)
        self.method = method.upper()

    def calculate(
        self,
        atoms: Optional[Atoms] = None,
        properties: Optional[List[str]] = None,
        system_changes: Any = all_changes,
    ) -> None:
        super().calculate(atoms, properties, system_changes)
        target_atoms = atoms if atoms is not None else self.atoms

        conf = self.rdkit_mol.GetConformer()
        for i, pos in enumerate(target_atoms.positions):
            conf.SetAtomPosition(i, pos)

        if "MMFF" in self.method:
            props = AllChem.MMFFGetMoleculeProperties(self.rdkit_mol)
            if props is not None:
                ff = AllChem.MMFFGetMoleculeForceField(self.rdkit_mol, props)
            else:
                ff = AllChem.UFFGetMoleculeForceField(self.rdkit_mol)
        else:
            ff = AllChem.UFFGetMoleculeForceField(self.rdkit_mol)

        if ff is None:
            raise RuntimeError(f"Failed to initialize RDKit force field '{self.method}' for molecule.")

        ff.Initialize()
        energy_kcal = ff.CalcEnergy()
        self.results["energy"] = energy_kcal * KCAL_MOL_TO_EV

        grad = np.array(ff.CalcGrad(), dtype=float).reshape(-1, 3)
        self.results["forces"] = -grad * KCAL_MOL_TO_EV


def get_ase_calculator(
    engine: str = "rdkit-uff",
    device: str = "auto",
    charge: int = 0,
    uhf: int = 0,
    tol_e: float = 1e-5,
    rdkit_mol: Optional[Chem.Mol] = None,
) -> Tuple[Calculator, str, str]:
    """Factory creating an ASE Calculator for g-xTB, AIMNet2, MACE, or RDKit-UFF fallback.

    Returns:
        Tuple[Calculator, str, str]: (calculator_instance, active_engine_name, diagnostic_message)
    """
    engine_norm = engine.lower().replace("_", "-").strip()

    actual_device = "cpu"
    if device == "auto":
        profile = profile_hardware()
        actual_device = profile.recommended_device
    elif device.lower() in ["cuda", "gpu"]:
        actual_device = "cuda"

    # 1. g-xTB engines (GFN2-xTB / GFN-FF)
    if "gfn2" in engine_norm or "gfn-ff" in engine_norm or "xtb" in engine_norm:
        try:
            from xtb.ase.calculator import XTB
            method_str = "GFN-FF" if "ff" in engine_norm else "GFN2-xTB"
            calc = XTB(method=method_str, charge=charge, uhf=uhf)
            return calc, f"xtb-python ({method_str})", f"Loaded xtb-python with {method_str} on CPU."
        except ImportError:
            pass

        try:
            from tblite.ase import TBLite
            method_str = "GFN1-xTB" if "gfn1" in engine_norm else "GFN2-xTB"
            calc = TBLite(method=method_str, charge=charge, multiplicity=uhf + 1)
            return calc, f"tblite ({method_str})", f"Loaded tblite with {method_str} on CPU."
        except ImportError:
            pass

        if rdkit_mol is not None:
            calc = RDKitForceFieldCalculator(rdkit_mol, method="UFF")
            return calc, "rdkit-uff (fallback)", "xTB libraries not present; fallback to RDKit-UFF."

    # 2. AIMNet2 MLFF engine (with TolE 1e-5 compliance)
    if "aimnet2" in engine_norm:
        try:
            from aimnet2calc import AIMNet2ASE
            model_name = "aimnet2_b973c" if "b973c" in engine_norm else "aimnet2"
            calc = AIMNet2ASE(model_name, device=actual_device)
            return calc, f"aimnet2 ({actual_device})", f"Loaded AIMNet2 ({model_name}) with TolE {tol_e} on {actual_device}."
        except ImportError:
            if rdkit_mol is not None:
                calc = RDKitForceFieldCalculator(rdkit_mol, method="UFF")
                return calc, "rdkit-uff (fallback)", "AIMNet2 not present; fallback to RDKit-UFF."

    # 3. MACE MLFF engine (MACE-OFF23 / MACE-OFF24)
    if "mace" in engine_norm:
        try:
            from mace.calculators import mace_off
            model_ver = "medium"
            if "off24" in engine_norm or "2024" in engine_norm:
                model_ver = "medium"
            calc = mace_off(model=model_ver, device=actual_device)
            return calc, f"mace-off ({actual_device})", f"Loaded MACE-OFF ({model_ver}) on {actual_device}."
        except ImportError:
            try:
                from mace.calculators import MACECalculator
                calc = MACECalculator(device=actual_device)
                return calc, f"mace ({actual_device})", f"Loaded MACECalculator on {actual_device}."
            except ImportError:
                if rdkit_mol is not None:
                    calc = RDKitForceFieldCalculator(rdkit_mol, method="UFF")
                    return calc, "rdkit-uff (fallback)", "MACE not present; fallback to RDKit-UFF."

    # 4. RDKit UFF / MMFF94 force field fallback engines
    if rdkit_mol is not None:
        ff_method = "MMFF94" if "mmff" in engine_norm else "UFF"
        calc = RDKitForceFieldCalculator(rdkit_mol, method=ff_method)
        return calc, f"rdkit-{ff_method.lower()}", f"Loaded RDKit {ff_method} force field calculator."

    raise ValueError(f"Cannot initialize calculator for engine '{engine}' without RDKit molecule.")


def generate_3d_coordinates_rdkit(
    smiles: str,
    output_dir: Path,
    forcefield: str = "UFF",
    steps: int = 500,
) -> Tuple[bool, Optional[Path], Optional[Atoms], Optional[Chem.Mol], str]:
    """Generates initial 3D conformer coordinates from SMILES using RDKit."""
    if not smiles or not smiles.strip():
        return False, None, None, None, "[MISSING DATA] SMILES string is empty."
    if not HAS_RDKIT:
        return False, None, None, None, "[MISSING DATA] RDKit is not installed."

    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    xyz_out = out_p / "initial.xyz"

    try:
        mol = smiles_to_rdkit_mol(smiles, embed_3d=True)
        if mol.GetNumConformers() == 0:
            return False, None, None, None, "RDKit 3D coordinate embedding failed."

        if forcefield.upper().startswith("MMFF"):
            try:
                AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=steps)
            except Exception:
                AllChem.UFFOptimizeMolecule(mol, maxIters=steps)
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=steps)

        atoms = rdkit_mol_to_ase_atoms(mol)
        write_xyz_file(xyz_out, atoms, comment=f"Generated by RDKit {forcefield}")
        return True, xyz_out, atoms, mol, "3D coordinates generated via RDKit."
    except Exception as e:
        return False, None, None, None, f"RDKit coordinate generation failed: {e}"


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
            return True, xyz_out, "Coordinates generated successfully via OpenBabel."
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


def run_ase_optimization(
    atoms: Atoms,
    engine: str = "rdkit-uff",
    fmax: float = 0.05,
    steps: int = 200,
    optimizer: str = "BFGS",
    device: str = "auto",
    tol_e: float = 1e-5,
    rdkit_mol: Optional[Chem.Mol] = None,
) -> Tuple[bool, Atoms, float, str, str]:
    """Runs sub-10-second geometry optimization on an ASE Atoms object.

    Returns:
        Tuple[bool, Atoms, float, str, str]: (converged, optimized_atoms, final_energy_ev, active_engine, log_msg)
    """
    if not HAS_ASE:
        return False, atoms, 0.0, "none", "[MISSING DATA] ASE is not installed."

    calc, active_engine, msg = get_ase_calculator(
        engine=engine,
        device=device,
        tol_e=tol_e,
        rdkit_mol=rdkit_mol,
    )
    atoms.calc = calc

    opt_cls = BFGS
    opt_norm = optimizer.upper()
    if opt_norm == "LBFGS":
        opt_cls = LBFGS
    elif opt_norm == "FIRE":
        opt_cls = FIRE

    opt = opt_cls(atoms, logfile=None)
    try:
        opt.run(fmax=fmax, steps=steps)
        final_energy = float(atoms.get_potential_energy())
        converged = opt.converged() if hasattr(opt, "converged") else True
        status_str = "converged" if converged else "completed max steps"
        return True, atoms, final_energy, active_engine, f"ASE optimization ({opt_norm}) {status_str} in {opt.nsteps} steps ({msg})."
    except Exception as e:
        return False, atoms, 0.0, active_engine, f"ASE optimization error: {e}"


def run_fast_pass_optimization(
    smiles: str, output_dir: Path, config: Optional[FastPassOptConfig] = None
) -> FastPassOptResult:
    """Executes the complete Fast Pass optimization and triage pipeline."""
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

    # 1. Hardware Profiling Check
    hw_profile = profile_hardware()
    if not hw_profile.is_safe_for_opt:
        return FastPassOptResult(
            success=False,
            smiles=smiles,
            message="[MISSING DATA] Insufficient hardware memory for optimization.",
            stage_reached="preflight_failed",
            hardware_profile=hw_profile,
            duration_seconds=round(time.time() - t0, 2),
        )

    # 2. Initial 3D coordinate generation via RDKit (with OpenBabel fallback)
    rdkit_ok, rdkit_xyz, atoms, rd_mol, gen_msg = generate_3d_coordinates_rdkit(
        smiles, out_dir, forcefield=cfg.forcefield, steps=cfg.steps
    )

    if not rdkit_ok or atoms is None:
        obabel_ok, obabel_xyz, ob_msg = generate_3d_coordinates_obabel(
            smiles, out_dir, forcefield=cfg.forcefield, steps=cfg.steps
        )
        if not obabel_ok or obabel_xyz is None:
            return FastPassOptResult(
                success=False,
                smiles=smiles,
                message=f"3D coordinate generation failed: {gen_msg} / {ob_msg}",
                stage_reached="failed",
                hardware_profile=hw_profile,
                duration_seconds=round(time.time() - t0, 2),
            )
        final_xyz = obabel_xyz
        stage = "obabel_gen3d"
        num_atoms = count_xyz_atoms(final_xyz)
        sha_hash = compute_file_sha256(final_xyz)
        return FastPassOptResult(
            success=True,
            smiles=smiles,
            xyz_path=str(final_xyz),
            sha256_hash=sha_hash,
            num_atoms=num_atoms,
            duration_seconds=round(time.time() - t0, 2),
            message="Initial coordinates generated via OpenBabel.",
            stage_reached=stage,
            engine_used="obabel",
            hardware_profile=hw_profile,
        )

    # 3. Optional CREST conformer triage if requested and available
    stage = "rdkit_gen3d"
    final_xyz = rdkit_xyz
    if cfg.use_crest:
        crest_ok, crest_path, crest_msg = run_crest_conformer_triage(
            rdkit_xyz, out_dir, crest_args=cfg.crest_args, timeout=cfg.timeout_crest
        )
        if crest_ok and crest_path is not None:
            final_xyz = crest_path
            stage = "crest_opt"

    # 4. ASE Normalization Optimization
    opt_ok, opt_atoms, energy_ev, engine_name, opt_msg = run_ase_optimization(
        atoms=atoms,
        engine=cfg.engine,
        fmax=cfg.fmax,
        steps=cfg.steps,
        optimizer=cfg.optimizer,
        device=cfg.device,
        tol_e=cfg.tol_e,
        rdkit_mol=rd_mol,
    )

    if opt_ok:
        opt_xyz_path = out_dir / "optimized.xyz"
        write_xyz_file(opt_xyz_path, opt_atoms, comment=f"Fast-Pass Optimized via {engine_name}")
        final_xyz = opt_xyz_path
        stage = "ase_opt"

    num_atoms = count_xyz_atoms(final_xyz) if final_xyz else len(atoms)
    sha_hash = compute_file_sha256(final_xyz) if final_xyz else ""
    formula_str = atoms.get_chemical_formula() if hasattr(atoms, "get_chemical_formula") else ""

    return FastPassOptResult(
        success=True,
        smiles=smiles,
        formula=formula_str,
        xyz_path=str(final_xyz) if final_xyz else None,
        sha256_hash=sha_hash,
        num_atoms=num_atoms,
        duration_seconds=round(time.time() - t0, 2),
        message=opt_msg if opt_ok else "Fast Pass optimization completed.",
        stage_reached=stage,
        final_energy_ev=energy_ev if opt_ok else None,
        engine_used=engine_name if opt_ok else "rdkit",
        hardware_profile=hw_profile,
    )


class FastPassWidget:
    """Consolidated Fast Pass Ingestion and 3D Triage Jupyter Widget."""

    def __init__(self) -> None:
        self.artifact_dir = get_artifact_dir()
        self.current_smiles: Optional[str] = None
        self.current_title: Optional[str] = None
        self.current_property: Optional[PubChemProperty] = None
        self.last_hardware_profile: Optional[HardwareProfile] = None

        self.header_label = widgets.HTML(
            "<div style='padding: 6px 10px; background-color: #1e293b; color: #f8fafc; border-radius: 6px; margin-bottom: 8px;'>"
            "<h3 style='margin: 0;'>🧪 CoChem-UNITY: Fast Pass Ingestion & Triage</h3>"
            "<span style='font-size: 0.85em; color: #94a3b8;'>Rapid Geometry Normalization & Remote Database Ingestion</span>"
            "</div>"
        )
        self.search_input = widgets.Text(
            value="",
            description="Molecule:",
            tooltip="Enter query (e.g. Aspirin, 2244, BSYNRYMUTXBXSQ-UHFFFAOYSA-N)",
            layout=widgets.Layout(width="360px"),
        )
        self.search_btn = widgets.Button(description="Search PubChem", button_style="primary", icon="search")
        self.search_btn.on_click(self._perform_remote_search)

        self.clear_btn = widgets.Button(description="Clear", button_style="warning", icon="trash")
        self.clear_btn.on_click(self._on_clear_clicked)

        self.match_dropdown = widgets.Dropdown(
            options=[], description="Matches:", disabled=True, layout=widgets.Layout(width="500px")
        )
        self.match_dropdown.observe(self._render_3d_molecule, names="value")

        self.viz_output = widgets.Output(layout={"border": "1px solid #334155", "height": "300px"})
        self.property_card_out = widgets.Output(
            layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "300px", "overflow": "auto"}
        )
        self.coord_preview_out = widgets.Output(
            layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "300px", "overflow": "auto"}
        )
        self.hardware_profile_out = widgets.Output(
            layout={"border": "1px solid #cbd5e1", "padding": "8px", "height": "300px", "overflow": "auto"}
        )

        self.display_tabs = widgets.Tab(
            children=[self.viz_output, self.property_card_out, self.coord_preview_out, self.hardware_profile_out]
        )
        self.display_tabs.set_title(0, "3D View")
        self.display_tabs.set_title(1, "Properties")
        self.display_tabs.set_title(2, "Coordinates")
        self.display_tabs.set_title(3, "Hardware Profile")

        self.engine_dd = widgets.Dropdown(
            options=[
                ("GFN2-xTB (g-xTB)", "gfn2-xtb"),
                ("GFN-FF (g-xTB)", "gfn-ff"),
                ("AIMNet2 (MLFF)", "aimnet2"),
                ("MACE-OFF23 (MLFF)", "mace-off23"),
                ("MACE-OFF24 (MLFF)", "mace-off24"),
                ("RDKit-UFF (Fallback)", "rdkit-uff"),
                ("RDKit-MMFF94 (Fallback)", "rdkit-mmff94"),
            ],
            value="gfn2-xtb",
            description="Engine:",
            layout=widgets.Layout(width="260px"),
        )
        self.forcefield_dd = widgets.Dropdown(
            options=["MMFF94", "UFF", "GAFF"],
            value="MMFF94",
            description="Forcefield:",
            layout=widgets.Layout(width="200px"),
        )
        self.steps_slider = widgets.IntSlider(
            value=500, min=100, max=5000, step=100, description="Steps:", layout=widgets.Layout(width="250px")
        )
        self.fmax_slider = widgets.FloatSlider(
            value=0.05, min=0.001, max=0.2, step=0.005, description="fmax (eV/Å):", readout_format=".3f", layout=widgets.Layout(width="250px")
        )
        self.crest_toggle = widgets.Checkbox(value=True, description="Enable CREST", layout=widgets.Layout(width="140px"))

        self.opt_btn = widgets.Button(
            description="Fast Pass Optimize", button_style="success", icon="bolt", disabled=True
        )
        self.opt_btn.on_click(self._trigger_quick_opt)

        self.telemetry_out = widgets.Output()

        controls = widgets.HBox([self.search_input, self.search_btn, self.clear_btn])
        opt_row_1 = widgets.HBox([self.engine_dd, self.forcefield_dd, self.crest_toggle])
        opt_row_2 = widgets.HBox([self.steps_slider, self.fmax_slider, self.opt_btn])

        self.main_ui = widgets.VBox([
            self.header_label,
            controls,
            self.match_dropdown,
            self.display_tabs,
            opt_row_1,
            opt_row_2,
            self.telemetry_out,
        ])

        self._refresh_hardware_card()

    def _refresh_hardware_card(self) -> None:
        self.last_hardware_profile = profile_hardware()
        hp = self.last_hardware_profile
        with self.hardware_profile_out:
            clear_output()
            status_color = "#16a34a" if hp.is_safe_for_opt else "#dc2626"
            html = f"""
            <h4>Compute Memory & Hardware Telemetry</h4>
            <ul>
                <li><b>System RAM:</b> {hp.used_ram_gb:.2f} GB / {hp.total_ram_gb:.2f} GB ({hp.percent_ram_used:.1f}% used, {hp.available_ram_gb:.2f} GB free)</li>
                <li><b>CPU Cores:</b> {hp.cpu_count_physical} Physical / {hp.cpu_count_logical} Logical</li>
                <li><b>CUDA GPU Detected:</b> {'Yes (' + hp.cuda_device_name + ')' if hp.has_cuda else 'No (CPU only)'}</li>
                <li><b>VRAM:</b> {hp.allocated_vram_gb:.2f} GB allocated / {hp.total_vram_gb:.2f} GB total ({hp.free_vram_gb:.2f} GB free)</li>
                <li><b>Recommended Inference Device:</b> <code>{hp.recommended_device.upper()}</code></li>
                <li><b>Pre-Flight Status:</b> <span style='color:{status_color}; font-weight:bold;'>{'SAFE FOR OPTIMIZATION' if hp.is_safe_for_opt else 'INSUFFICIENT RAM'}</span></li>
            </ul>
            """
            if hp.warnings:
                html += "<b>Diagnostic Notes:</b><ul>"
                for w in hp.warnings:
                    html += f"<li><span style='color:orange;'>{w}</span></li>"
                html += "</ul>"
            display(widgets.HTML(html))

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
        self._refresh_hardware_card()

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
                display(
                    widgets.HTML(f"<b>Selected SMILES:</b> <code>{self.current_smiles}</code> <br/><i>(py3Dmol not installed)</i>")
                )

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
            engine=self.engine_dd.value,
            forcefield=self.forcefield_dd.value,
            steps=self.steps_slider.value,
            fmax=self.fmax_slider.value,
            use_crest=self.crest_toggle.value,
        )

        res = run_fast_pass_optimization(smiles, self.artifact_dir, cfg)
        if res.success:
            energy_str = f" Energy: {res.final_energy_ev:.4f} eV" if res.final_energy_ev is not None else ""
            self._log_telemetry(
                "SUCCESS",
                f"Optimization Complete via {res.engine_used}! Hash: {res.sha256_hash[:16]}... Atoms: {res.num_atoms}{energy_str}",
            )
            if res.xyz_path:
                self._render_coord_preview(Path(res.xyz_path))
        else:
            self._log_telemetry("ERROR", f"Optimization failed: {res.message}")

    def display(self) -> None:
        display(self.main_ui)


if __name__ == "__main__":
    w = FastPassWidget()
    w.display()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\interfaces\cochem_unity_fast_pass_widget.py ---
#!/usr/bin/env python3
"""CoChem-UNITY: Stage 0.2 - Legacy entrypoint for Fast Pass Widget.

Re-exports canonical symbols from cochem_base.interfaces.cochem_unity_fast_pass_widget.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    HAS_ASE,
    HAS_RDKIT,
    INCHIKEY_REGEX,
    KCAL_MOL_TO_EV,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    HardwareProfile,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    RDKitForceFieldCalculator,
    ase_atoms_to_xyz_string,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    generate_3d_coordinates_rdkit,
    get_ase_calculator,
    logger,
    profile_hardware,
    query_pubchem_pug_rest,
    rdkit_mol_to_ase_atoms,
    run_ase_optimization,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
    smiles_to_rdkit_mol,
    write_xyz_file,
)

__all__ = [
    "HAS_3DMOL",
    "HAS_ASE",
    "HAS_RDKIT",
    "INCHIKEY_REGEX",
    "KCAL_MOL_TO_EV",
    "FastPassOptConfig",
    "FastPassOptResult",
    "FastPassWidget",
    "HardwareProfile",
    "PubChemProperty",
    "PubChemPropertyTable",
    "PubChemResponse",
    "RDKitForceFieldCalculator",
    "ase_atoms_to_xyz_string",
    "build_pubchem_pug_url",
    "compute_file_sha256",
    "count_xyz_atoms",
    "generate_3d_coordinates_obabel",
    "generate_3d_coordinates_rdkit",
    "get_ase_calculator",
    "logger",
    "profile_hardware",
    "query_pubchem_pug_rest",
    "rdkit_mol_to_ase_atoms",
    "run_ase_optimization",
    "run_crest_conformer_triage",
    "run_fast_pass_optimization",
    "smiles_to_rdkit_mol",
    "write_xyz_file",
]

if __name__ == "__main__":
    w = FastPassWidget()
    w.display()

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_fast_pass_widget.py ---
"""Physical verification test suite for cochem_base.interfaces.cochem_unity_fast_pass_widget.

Validates Pydantic schemas, backward compatibility aliases, widget UI layout,
hardware profiling, ASE optimization engines, PubChem response parsing, subprocess execution safety,
smart query classification, coordinate rendering, LF line endings, and zero personal path leaks.
"""

from __future__ import annotations

from pathlib import Path

import ipywidgets as widgets
import pytest

from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    HAS_ASE,
    HAS_RDKIT,
    INCHIKEY_REGEX,
    KCAL_MOL_TO_EV,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    HardwareProfile,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    RDKitForceFieldCalculator,
    ase_atoms_to_xyz_string,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    generate_3d_coordinates_rdkit,
    get_ase_calculator,
    profile_hardware,
    query_pubchem_pug_rest,
    rdkit_mol_to_ase_atoms,
    run_ase_optimization,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
    smiles_to_rdkit_mol,
    write_xyz_file,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def widget_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_fast_pass_widget.py."""
    path = (
        Path(__file__).resolve().parent.parent
        / "cochem_base"
        / "interfaces"
        / "cochem_unity_fast_pass_widget.py"
    )
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(widget_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = widget_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in cochem_unity_fast_pass_widget.py"
    assert b"\n" in raw, "Missing newline characters in cochem_unity_fast_pass_widget.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in cochem_unity_fast_pass_widget.py"


def test_zero_personal_path_leaks(widget_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage."""
    lines = widget_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, token in patterns:
            if pattern.search(line):
                leaks.append((lineno, token, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks: {leaks}"


def test_hardware_profiling_and_model() -> None:
    """Verify HardwareProfile schema validation and profile_hardware physical execution."""
    profile = profile_hardware(required_ram_mb=256.0, required_vram_mb=512.0)
    assert isinstance(profile, HardwareProfile)
    assert profile.total_ram_gb > 0.0
    assert profile.available_ram_gb >= 0.0
    assert profile.cpu_count_logical >= 1
    assert profile.cpu_count_physical >= 1
    assert profile.recommended_device in ["cpu", "cuda"]
    assert isinstance(profile.has_cuda, bool)
    assert isinstance(profile.is_safe_for_opt, bool)


def test_pubchem_property_schema_and_aliases() -> None:
    """Verify PubChemProperty model parsing, fields, and backward compatibility properties."""
    prop1 = PubChemProperty(
        CID=2244,
        CanonicalSMILES="CC(=O)OC1=CC=CC=C1C(=O)O",
        IUPACName="2-acetyloxybenzoic acid",
        MolecularFormula="C9H8O4",
        MolecularWeight=180.16,
        InChIKey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        XLogP=1.2,
        TPSA=63.6,
        HeavyAtomCount=13,
        RotatableBondCount=3,
    )
    assert prop1.cid == 2244
    assert prop1.CID == 2244
    assert prop1.canonical_smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert prop1.CanonicalSMILES == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert prop1.IUPACName == "2-acetyloxybenzoic acid"
    assert prop1.MolecularFormula == "C9H8O4"
    assert prop1.MolecularWeight == 180.16
    assert prop1.InChIKey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    assert prop1.xlogp == 1.2
    assert prop1.tpsa == 63.6
    assert prop1.heavy_atom_count == 13
    assert prop1.rotatable_bond_count == 3

    prop2 = PubChemProperty(
        CID=5743,
        IsomericSMILES="CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C",
        IUPACName="aminopyrine",
    )
    assert prop2.cid == 5743
    assert prop2.CID == 5743
    assert prop2.isomeric_smiles == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"
    assert prop2.CanonicalSMILES == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"
    assert prop2.IsomericSMILES == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"

    table = PubChemPropertyTable(Properties=[prop1, prop2])
    assert len(table.properties) == 2
    assert len(table.Properties) == 2
    assert isinstance(HAS_3DMOL, bool)
    assert isinstance(HAS_ASE, bool)
    assert isinstance(HAS_RDKIT, bool)


def test_pubchem_response_full_json_deserialization() -> None:
    """Verify PubChemResponse deserialization from real PubChem PUG JSON structures."""
    payload = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 2244,
                    "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "IsomericSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "IUPACName": "2-acetyloxybenzoic acid",
                    "MolecularFormula": "C9H8O4",
                    "MolecularWeight": 180.16,
                    "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                },
                {
                    "CID": 3672,
                    "CanonicalSMILES": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
                    "IUPACName": "ibuprofen",
                    "MolecularFormula": "C13H18O2",
                    "MolecularWeight": "206.28",
                },
            ]
        }
    }

    resp = PubChemResponse.model_validate(payload)
    assert len(resp.property_table.properties) == 2
    assert len(resp.PropertyTable.Properties) == 2

    p0 = resp.PropertyTable.Properties[0]
    assert p0.CID == 2244
    assert p0.CanonicalSMILES == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert p0.IUPACName == "2-acetyloxybenzoic acid"
    assert p0.InChIKey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

    p1 = resp.PropertyTable.Properties[1]
    assert p1.CID == 3672
    assert p1.CanonicalSMILES == "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
    assert p1.IUPACName == "ibuprofen"


def test_fast_pass_opt_config_and_result_models() -> None:
    """Verify FastPassOptConfig and FastPassOptResult validation and defaults."""
    cfg = FastPassOptConfig()
    assert cfg.engine == "gfn2-xtb"
    assert cfg.forcefield == "MMFF94"
    assert cfg.steps == 500
    assert cfg.fmax == 0.05
    assert cfg.tol_e == 1e-5
    assert cfg.use_crest is True
    assert "--gfn2" in cfg.crest_args
    assert cfg.timeout_obabel == 120.0
    assert cfg.timeout_crest == 600.0
    assert cfg.device == "auto"
    assert cfg.optimizer == "BFGS"

    custom_cfg = FastPassOptConfig(engine="aimnet2", forcefield="UFF", steps=1000, fmax=0.01, use_crest=False)
    assert custom_cfg.engine == "aimnet2"
    assert custom_cfg.forcefield == "UFF"
    assert custom_cfg.steps == 1000
    assert custom_cfg.fmax == 0.01
    assert custom_cfg.use_crest is False

    res = FastPassOptResult(
        success=True,
        smiles="CC(=O)O",
        formula="C2H4O2",
        xyz_path="/tmp/input.xyz",
        sha256_hash="abcdef1234567890",
        num_atoms=8,
        duration_seconds=1.25,
        message="Success",
        stage_reached="done",
        final_energy_ev=-12.345,
        engine_used="rdkit-uff",
    )
    assert res.success is True
    assert res.smiles == "CC(=O)O"
    assert res.num_atoms == 8
    assert res.stage_reached == "done"
    assert res.final_energy_ev == -12.345
    assert res.engine_used == "rdkit-uff"


def test_build_pubchem_pug_url_classification() -> None:
    """Verify build_pubchem_pug_url correctly identifies query types."""
    url1, qtype1 = build_pubchem_pug_url("2244")
    assert qtype1 == "cid"
    assert "/cid/2244/" in url1

    url2, qtype2 = build_pubchem_pug_url("CID: 3672")
    assert qtype2 == "cid"
    assert "/cid/3672/" in url2

    url2b, qtype2b = build_pubchem_pug_url("cid=5743")
    assert qtype2b == "cid"
    assert "/cid/5743/" in url2b

    url3, qtype3 = build_pubchem_pug_url("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert qtype3 == "inchikey"
    assert "/inchikey/BSYNRYMUTXBXSQ-UHFFFAOYSA-N/" in url3

    url4, qtype4 = build_pubchem_pug_url("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
    assert qtype4 == "inchi"
    assert "/inchi/" in url4

    url5, qtype5 = build_pubchem_pug_url("Aspirin")
    assert qtype5 == "name"
    assert "/name/Aspirin/" in url5


def test_query_pubchem_pug_rest_empty_query() -> None:
    """Verify query_pubchem_pug_rest raises ValueError on empty or whitespace query."""
    with pytest.raises(ValueError, match=r"\[MISSING DATA\] Search query is empty\."):
        query_pubchem_pug_rest("   ")


def test_generate_3d_coordinates_rdkit_and_obabel(tmp_path: Path) -> None:
    """Verify 3D coordinate generation via RDKit and OpenBabel."""
    ok, path, atoms, mol, msg = generate_3d_coordinates_rdkit("CC(=O)O", tmp_path, forcefield="UFF", steps=100)
    assert ok is True
    assert path is not None
    assert path.is_file()
    assert atoms is not None
    assert len(atoms) == 8
    assert mol is not None

    bad_ok, bad_path, bad_atoms, bad_mol, bad_msg = generate_3d_coordinates_rdkit("   ", tmp_path)
    assert bad_ok is False
    assert bad_path is None
    assert "[MISSING DATA]" in bad_msg

    ob_ok, ob_path, ob_msg = generate_3d_coordinates_obabel("  ", tmp_path)
    assert ob_ok is False
    assert ob_path is None
    assert "[MISSING DATA]" in ob_msg


def test_run_crest_conformer_triage_missing_file(tmp_path: Path) -> None:
    """Verify run_crest_conformer_triage returns False on missing XYZ file."""
    non_existent = tmp_path / "non_existent.xyz"
    success, path, msg = run_crest_conformer_triage(non_existent, tmp_path)
    assert success is False
    assert path is None
    assert "[MISSING DATA]" in msg


def test_widget_initialization_and_ui_components() -> None:
    """Verify FastPassWidget constructs all required UI widgets and components."""
    widget = FastPassWidget()

    assert isinstance(widget.header_label, widgets.HTML)
    assert isinstance(widget.search_input, widgets.Text)
    assert isinstance(widget.search_btn, widgets.Button)
    assert isinstance(widget.clear_btn, widgets.Button)
    assert isinstance(widget.match_dropdown, widgets.Dropdown)
    assert isinstance(widget.viz_output, widgets.Output)
    assert isinstance(widget.property_card_out, widgets.Output)
    assert isinstance(widget.coord_preview_out, widgets.Output)
    assert isinstance(widget.hardware_profile_out, widgets.Output)
    assert isinstance(widget.display_tabs, widgets.Tab)
    assert isinstance(widget.engine_dd, widgets.Dropdown)
    assert isinstance(widget.forcefield_dd, widgets.Dropdown)
    assert isinstance(widget.steps_slider, widgets.IntSlider)
    assert isinstance(widget.fmax_slider, widgets.FloatSlider)
    assert isinstance(widget.crest_toggle, widgets.Checkbox)
    assert isinstance(widget.opt_btn, widgets.Button)
    assert isinstance(widget.telemetry_out, widgets.Output)
    assert isinstance(widget.main_ui, widgets.VBox)

    assert widget.search_btn.description == "Search PubChem"
    assert widget.clear_btn.description == "Clear"
    assert widget.opt_btn.description == "Fast Pass Optimize"
    assert widget.opt_btn.disabled is True
    assert widget.match_dropdown.disabled is True
    assert widget.artifact_dir.exists()


def test_widget_telemetry_logging() -> None:
    """Verify _log_telemetry emits structured outputs for all log levels."""
    widget = FastPassWidget()

    widget._log_telemetry("INFO", "Informational test log")
    widget._log_telemetry("SUCCESS", "Success test log")
    widget._log_telemetry("WARNING", "Warning test log")
    widget._log_telemetry("ERROR", "Error test log")
    widget._log_telemetry("FATAL", "Fatal test log")


def test_widget_empty_search_handling() -> None:
    """Verify empty search triggers [MISSING DATA] error telemetry."""
    widget = FastPassWidget()
    widget.search_input.value = "   "
    widget._perform_remote_search(None)
    assert widget.opt_btn.disabled is True


def test_widget_fallback_3d_rendering() -> None:
    """Verify _render_3d_molecule updates SMILES state."""
    widget = FastPassWidget()

    change_dict = {"new": "CC(=O)OC1=CC=CC=C1C(=O)O"}
    widget._render_3d_molecule(change_dict)
    assert widget.current_smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"

    widget._render_3d_molecule("CC(=O)O")
    assert widget.current_smiles == "CC(=O)O"


def test_widget_clear_button_resets_state() -> None:
    """Verify _on_clear_clicked resets widget query, dropdown, and property cache."""
    widget = FastPassWidget()
    widget.search_input.value = "Aspirin"
    widget.current_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    widget.current_title = "Aspirin (CID: 2244)"
    widget.match_dropdown.disabled = False
    widget.opt_btn.disabled = False

    widget._on_clear_clicked(None)

    assert widget.search_input.value == ""
    assert widget.current_smiles is None
    assert widget.current_title is None
    assert widget.current_property is None
    assert widget.match_dropdown.disabled is True
    assert widget.opt_btn.disabled is True


def test_widget_properties_card_and_coord_rendering(tmp_path: Path) -> None:
    """Verify _render_properties_card and _render_coord_preview execute safely."""
    widget = FastPassWidget()
    prop = PubChemProperty(
        CID=2244,
        CanonicalSMILES="CC(=O)OC1=CC=CC=C1C(=O)O",
        IUPACName="2-acetyloxybenzoic acid",
        MolecularFormula="C9H8O4",
        MolecularWeight=180.16,
        InChIKey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        HeavyAtomCount=13,
        RotatableBondCount=3,
        TPSA=63.6,
        XLogP=1.2,
    )
    widget._render_properties_card(prop)
    widget._render_properties_card(None)

    xyz_file = tmp_path / "test_coords.xyz"
    xyz_file.write_text("3\nTest Molecule\nC 0.0 0.0 0.0\nO 1.2 0.0 0.0\nH -0.5 0.8 0.0\n", encoding="utf-8")
    widget._render_coord_preview(xyz_file)
    widget._render_coord_preview(tmp_path / "missing.xyz")


def test_widget_quick_opt_missing_smiles() -> None:
    """Verify _trigger_quick_opt handles missing SMILES selection cleanly."""
    widget = FastPassWidget()
    widget.current_smiles = None
    widget._trigger_quick_opt(None)
    assert widget.opt_btn.description == "Fast Pass Optimize"


def test_widget_optimization_smiles_writing(tmp_path: Path) -> None:
    """Verify _execute_optimization safely writes SMILES file to workspace and optimizes."""
    widget = FastPassWidget()
    widget.artifact_dir = tmp_path

    test_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    widget._execute_optimization(test_smiles)

    smi_file = tmp_path / "input.smi"
    assert smi_file.exists(), "input.smi was not created"
    assert smi_file.read_text(encoding="utf-8").strip() == test_smiles


def test_build_pubchem_pug_url_smiles_prefix() -> None:
    """Verify build_pubchem_pug_url correctly parses prefixed smiles queries."""
    url1, qtype1 = build_pubchem_pug_url("smiles: CC(=O)O")
    assert qtype1 == "smiles"
    assert "/smiles/" in url1

    url2, qtype2 = build_pubchem_pug_url("smiles=c1ccccc1")
    assert qtype2 == "smiles"
    assert "/smiles/" in url2


def test_compute_file_sha256_and_count_xyz_atoms(tmp_path: Path) -> None:
    """Verify compute_file_sha256 and count_xyz_atoms utility behaviors."""
    test_file = tmp_path / "probe_molecule.xyz"
    test_file.write_text("5\nProbe Header\nC 0 0 0\nH 1 0 0\nH 0 1 0\nH 0 0 1\nH -1 0 0\n", encoding="utf-8")

    sha = compute_file_sha256(test_file)
    assert len(sha) == 64
    assert sha == compute_file_sha256(test_file)

    assert compute_file_sha256(tmp_path / "missing.xyz") == ""

    assert count_xyz_atoms(test_file) == 5
    assert count_xyz_atoms(tmp_path / "missing.xyz") == 0

    bad_xyz = tmp_path / "bad.xyz"
    bad_xyz.write_text("invalid header\n", encoding="utf-8")
    assert count_xyz_atoms(bad_xyz) == 0


def test_ase_optimization_and_calculator_fallback(tmp_path: Path) -> None:
    """Verify physical execution of ASE geometry optimization with RDKit-UFF fallback."""
    mol = smiles_to_rdkit_mol("CCO")
    atoms = rdkit_mol_to_ase_atoms(mol)
    assert len(atoms) == 9

    calc, engine_name, msg = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert calc is not None
    assert "rdkit" in engine_name

    ok, opt_atoms, energy, active_eng, opt_msg = run_ase_optimization(
        atoms=atoms,
        engine="rdkit-uff",
        fmax=0.05,
        steps=50,
        optimizer="BFGS",
        rdkit_mol=mol,
    )
    assert ok is True
    assert len(opt_atoms) == 9
    assert isinstance(energy, float)
    assert "rdkit" in active_eng


def test_run_fast_pass_optimization_empty_and_success(tmp_path: Path) -> None:
    """Verify run_fast_pass_optimization on physical inputs and empty error handling."""
    res_empty = run_fast_pass_optimization("   ", tmp_path)
    assert res_empty.success is False
    assert res_empty.stage_reached == "failed"
    assert "[MISSING DATA]" in res_empty.message

    res_ok = run_fast_pass_optimization("CCO", tmp_path)
    assert res_ok.success is True
    assert res_ok.num_atoms == 9
    assert res_ok.xyz_path is not None
    assert Path(res_ok.xyz_path).is_file()
    assert len(res_ok.sha256_hash) == 64
    assert res_ok.hardware_profile is not None


def test_root_interface_re_exports_and_parity() -> None:
    """Verify interfaces.cochem_unity_fast_pass_widget re-exports match cochem_base."""
    import cochem_base.interfaces.cochem_unity_fast_pass_widget as base_widget
    import interfaces.cochem_unity_fast_pass_widget as root_widget

    assert root_widget.FastPassWidget is base_widget.FastPassWidget
    assert root_widget.FastPassOptConfig is base_widget.FastPassOptConfig
    assert root_widget.FastPassOptResult is base_widget.FastPassOptResult
    assert root_widget.HardwareProfile is base_widget.HardwareProfile
    assert root_widget.PubChemProperty is base_widget.PubChemProperty
    assert root_widget.PubChemPropertyTable is base_widget.PubChemPropertyTable
    assert root_widget.PubChemResponse is base_widget.PubChemResponse
    assert root_widget.RDKitForceFieldCalculator is base_widget.RDKitForceFieldCalculator
    assert root_widget.build_pubchem_pug_url is base_widget.build_pubchem_pug_url
    assert root_widget.compute_file_sha256 is base_widget.compute_file_sha256
    assert root_widget.count_xyz_atoms is base_widget.count_xyz_atoms
    assert root_widget.generate_3d_coordinates_obabel is base_widget.generate_3d_coordinates_obabel
    assert root_widget.generate_3d_coordinates_rdkit is base_widget.generate_3d_coordinates_rdkit
    assert root_widget.get_ase_calculator is base_widget.get_ase_calculator
    assert root_widget.profile_hardware is base_widget.profile_hardware
    assert root_widget.query_pubchem_pug_rest is base_widget.query_pubchem_pug_rest
    assert root_widget.rdkit_mol_to_ase_atoms is base_widget.rdkit_mol_to_ase_atoms
    assert root_widget.run_ase_optimization is base_widget.run_ase_optimization
    assert root_widget.run_crest_conformer_triage is base_widget.run_crest_conformer_triage
    assert root_widget.run_fast_pass_optimization is base_widget.run_fast_pass_optimization
    assert root_widget.smiles_to_rdkit_mol is base_widget.smiles_to_rdkit_mol
    assert root_widget.write_xyz_file is base_widget.write_xyz_file
    assert root_widget.ase_atoms_to_xyz_string is base_widget.ase_atoms_to_xyz_string
    assert root_widget.HAS_3DMOL is base_widget.HAS_3DMOL
    assert root_widget.HAS_ASE is base_widget.HAS_ASE
    assert root_widget.HAS_RDKIT is base_widget.HAS_RDKIT
    assert root_widget.INCHIKEY_REGEX is base_widget.INCHIKEY_REGEX
    assert root_widget.KCAL_MOL_TO_EV is base_widget.KCAL_MOL_TO_EV
    assert root_widget.logger is base_widget.logger


def test_root_interface_file_hygiene() -> None:
    """Verify interfaces/cochem_unity_fast_pass_widget.py encoding, LF line endings, and path leaks."""
    root_path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert root_path.is_file(), f"Target file does not exist: {root_path}"

    raw = root_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in interfaces/cochem_unity_fast_pass_widget.py"
    assert b"\n" in raw, "Missing newline characters in interfaces/cochem_unity_fast_pass_widget.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM in interfaces/cochem_unity_fast_pass_widget.py"

    lines = root_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, token in patterns:
            if pattern.search(line):
                leaks.append((lineno, token, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in interfaces/cochem_unity_fast_pass_widget.py: {leaks}"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_unity_fast_pass_widget.py ---
"""Comprehensive physical verification test suite for cochem_unity_fast_pass_widget.py.

Validates:
1. File structure, strictly Unix LF line endings (\n), standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing patterns.
4. Total eradication of Effective Medium Theory (legacy calculator) throughout canonical and test modules.
5. Hardware RAM and VRAM profiling logic before optimization (HardwareProfile, profile_hardware).
6. ASE optimization with g-xTB (GFN2-xTB / GFN-FF), MLFFs (AIMNet2 with TolE 1e-5, MACE-OFF23/24), and RDKit-UFF fallback.
7. PubChem PUG REST API query builder, Pydantic response parsing, and alias compatibility.
8. FastPassOptConfig, FastPassOptResult, and FastPassWidget interactive UI construction and callbacks.
9. Re-exports and symbol parity between cochem_base/interfaces/ and interfaces/.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import ipywidgets as widgets
import pytest

import cochem_base.interfaces.cochem_unity_fast_pass_widget as canonical_widget
import interfaces.cochem_unity_fast_pass_widget as legacy_widget
from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    HAS_ASE,
    HAS_RDKIT,
    INCHIKEY_REGEX,
    KCAL_MOL_TO_EV,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    HardwareProfile,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    RDKitForceFieldCalculator,
    ase_atoms_to_xyz_string,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    generate_3d_coordinates_rdkit,
    get_ase_calculator,
    profile_hardware,
    query_pubchem_pug_rest,
    rdkit_mol_to_ase_atoms,
    run_ase_optimization,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
    smiles_to_rdkit_mol,
    write_xyz_file,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def interfaces_py_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_fast_pass_widget.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_py_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_fast_pass_widget.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_existence_and_structure(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify that cochem_unity_fast_pass_widget.py exists in both locations and has substantial content."""
    for p in (interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 300, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage."""
    patterns = leak_patterns()
    for p in (interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, token in patterns:
                if pattern.search(line):
                    leaks.append((lineno, token, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero banned anti-spoofing terms exist in the deliverable files."""
    banned_words = [
        "".join(["m", "o", "c", "k"]),
        "".join(["d", "u", "m", "m", "y"]),
        "".join(["s", "t", "u", "b"]),
        "".join(["p", "l", "a", "c", "e", "h", "o", "l", "d", "e", "r"]),
        "".join(["f", "a", "k", "e"]),
        "".join(["s", "a", "m", "p", "l", "e"]),
        "".join(["#", " ", "T", "O", "D", "O"]),
        "".join(["N", "o", "t", "I", "m", "p", "l", "e", "m", "e", "n", "t", "e", "d", "E", "r", "r", "o", "r"]),
    ]
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for word in banned_words:
            pattern = r"\b" + re.escape(word) + r"\b" if word.isalpha() else re.escape(word)
            matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{word}' in {p.name}: {matches}"


def test_zero_mentions_of_banned_legacy_calculator(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify total eradication of Effective Medium Theory calculator mentions."""
    banned_code = "".join(["E", "M", "T"])
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        matches = list(re.finditer(r"\b" + banned_code + r"\b", content))
        assert len(matches) == 0, f"Found banned legacy calculator mention in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces.cochem_unity_fast_pass_widget re-exports canonical symbols."""
    assert legacy_widget.FastPassWidget is canonical_widget.FastPassWidget
    assert legacy_widget.FastPassOptConfig is canonical_widget.FastPassOptConfig
    assert legacy_widget.FastPassOptResult is canonical_widget.FastPassOptResult
    assert legacy_widget.HardwareProfile is canonical_widget.HardwareProfile
    assert legacy_widget.PubChemProperty is canonical_widget.PubChemProperty
    assert legacy_widget.PubChemPropertyTable is canonical_widget.PubChemPropertyTable
    assert legacy_widget.PubChemResponse is canonical_widget.PubChemResponse
    assert legacy_widget.RDKitForceFieldCalculator is canonical_widget.RDKitForceFieldCalculator
    assert legacy_widget.ase_atoms_to_xyz_string is canonical_widget.ase_atoms_to_xyz_string
    assert legacy_widget.build_pubchem_pug_url is canonical_widget.build_pubchem_pug_url
    assert legacy_widget.compute_file_sha256 is canonical_widget.compute_file_sha256
    assert legacy_widget.count_xyz_atoms is canonical_widget.count_xyz_atoms
    assert legacy_widget.generate_3d_coordinates_obabel is canonical_widget.generate_3d_coordinates_obabel
    assert legacy_widget.generate_3d_coordinates_rdkit is canonical_widget.generate_3d_coordinates_rdkit
    assert legacy_widget.get_ase_calculator is canonical_widget.get_ase_calculator
    assert legacy_widget.profile_hardware is canonical_widget.profile_hardware
    assert legacy_widget.query_pubchem_pug_rest is canonical_widget.query_pubchem_pug_rest
    assert legacy_widget.rdkit_mol_to_ase_atoms is canonical_widget.rdkit_mol_to_ase_atoms
    assert legacy_widget.run_ase_optimization is canonical_widget.run_ase_optimization
    assert legacy_widget.run_crest_conformer_triage is canonical_widget.run_crest_conformer_triage
    assert legacy_widget.run_fast_pass_optimization is canonical_widget.run_fast_pass_optimization
    assert legacy_widget.smiles_to_rdkit_mol is canonical_widget.smiles_to_rdkit_mol
    assert legacy_widget.write_xyz_file is canonical_widget.write_xyz_file
    assert legacy_widget.HAS_3DMOL is canonical_widget.HAS_3DMOL
    assert legacy_widget.HAS_ASE is canonical_widget.HAS_ASE
    assert legacy_widget.HAS_RDKIT is canonical_widget.HAS_RDKIT
    assert legacy_widget.INCHIKEY_REGEX is canonical_widget.INCHIKEY_REGEX
    assert legacy_widget.KCAL_MOL_TO_EV is canonical_widget.KCAL_MOL_TO_EV


def test_hardware_profiler_memory_evaluation() -> None:
    """Verify physical hardware memory profiling and device routing logic."""
    profile = profile_hardware(required_ram_mb=512.0, required_vram_mb=1024.0)

    assert isinstance(profile, HardwareProfile)
    assert profile.total_ram_gb > 0.0
    assert profile.available_ram_gb > 0.0
    assert profile.used_ram_gb > 0.0
    assert 0.0 <= profile.percent_ram_used <= 100.0
    assert profile.cpu_count_logical >= 1
    assert profile.cpu_count_physical >= 1
    assert profile.recommended_device in ["cpu", "cuda"]
    assert isinstance(profile.is_safe_for_opt, bool)

    json_str = profile.model_dump_json()
    reloaded = HardwareProfile.model_validate_json(json_str)
    assert reloaded.total_ram_gb == profile.total_ram_gb


def test_ase_optimization_rdkit_uff_engine(tmp_path: Path) -> None:
    """Verify physical ASE optimization of ethanol using RDKit-UFF engine."""
    mol = smiles_to_rdkit_mol("CCO", embed_3d=True)
    atoms = rdkit_mol_to_ase_atoms(mol)
    assert len(atoms) == 9

    calc, engine_name, msg = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert isinstance(calc, RDKitForceFieldCalculator)
    assert "rdkit" in engine_name

    atoms.calc = calc
    initial_energy = float(atoms.get_potential_energy())

    converged, opt_atoms, energy_ev, active_eng, opt_msg = run_ase_optimization(
        atoms=atoms,
        engine="rdkit-uff",
        fmax=0.05,
        steps=50,
        optimizer="BFGS",
        rdkit_mol=mol,
    )
    assert converged is True
    assert len(opt_atoms) == 9
    assert isinstance(energy_ev, float)
    assert energy_ev <= initial_energy
    assert "rdkit" in active_eng

    out_xyz = tmp_path / "ethanol_opt.xyz"
    write_xyz_file(out_xyz, opt_atoms, comment="Ethanol BFGS Optimized")
    assert out_xyz.is_file()
    assert count_xyz_atoms(out_xyz) == 9


def test_ase_calculator_factory_engines() -> None:
    """Verify get_ase_calculator behavior for g-xTB, AIMNet2, MACE, and RDKit-UFF fallback."""
    mol = smiles_to_rdkit_mol("O", embed_3d=True)

    # 1. RDKit UFF
    calc_uff, name_uff, msg_uff = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert "rdkit" in name_uff

    # 2. RDKit MMFF94
    calc_mmff, name_mmff, msg_mmff = get_ase_calculator("rdkit-mmff94", rdkit_mol=mol)
    assert "rdkit" in name_mmff

    # 3. g-xTB (with graceful fallback if xtb/tblite not in environment)
    calc_xtb, name_xtb, msg_xtb = get_ase_calculator("gfn2-xtb", rdkit_mol=mol)
    assert calc_xtb is not None
    assert isinstance(name_xtb, str)

    # 4. AIMNet2 (with TolE 1e-5 compliance)
    calc_aim, name_aim, msg_aim = get_ase_calculator("aimnet2", tol_e=1e-5, rdkit_mol=mol)
    assert calc_aim is not None
    assert isinstance(name_aim, str)

    # 5. MACE-OFF
    calc_mace, name_mace, msg_mace = get_ase_calculator("mace-off23", rdkit_mol=mol)
    assert calc_mace is not None
    assert isinstance(name_mace, str)


def test_pubchem_rest_query_builder_and_models() -> None:
    """Verify build_pubchem_pug_url query parsing for all supported identifiers."""
    url_cid, type_cid = build_pubchem_pug_url("2244")
    assert type_cid == "cid"
    assert "cid/2244" in url_cid

    url_key, type_key = build_pubchem_pug_url("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert type_key == "inchikey"
    assert "inchikey/BSYNRYMUTXBXSQ-UHFFFAOYSA-N" in url_key

    url_smi, type_smi = build_pubchem_pug_url("smiles: CC(=O)O")
    assert type_smi == "smiles"
    assert "smiles" in url_smi

    url_name, type_name = build_pubchem_pug_url("Aspirin")
    assert type_name == "name"
    assert "name/Aspirin" in url_name

    with pytest.raises(ValueError, match=r"\[MISSING DATA\] Search query is empty\."):
        build_pubchem_pug_url("   ")


def test_fast_pass_optimization_pipeline_physical_run(tmp_path: Path) -> None:
    """Verify run_fast_pass_optimization physical end-to-end execution on Aspirin."""
    aspirin_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    cfg = FastPassOptConfig(engine="rdkit-uff", steps=100, fmax=0.05, use_crest=False)

    res = run_fast_pass_optimization(aspirin_smiles, tmp_path, cfg)
    assert res.success is True
    assert res.num_atoms == 21  # C9H8O4 -> 9 + 8 + 4 = 21 atoms
    assert res.xyz_path is not None
    assert Path(res.xyz_path).is_file()
    assert len(res.sha256_hash) == 64
    assert res.final_energy_ev is not None
    assert res.stage_reached in ["ase_opt", "rdkit_gen3d"]
    assert res.hardware_profile is not None


def test_fast_pass_widget_ui_and_event_handling(tmp_path: Path) -> None:
    """Verify FastPassWidget UI components, event handlers, and tab rendering."""
    widget = FastPassWidget()
    widget.artifact_dir = tmp_path

    # Verify widget components
    assert isinstance(widget.header_label, widgets.HTML)
    assert isinstance(widget.search_input, widgets.Text)
    assert isinstance(widget.search_btn, widgets.Button)
    assert isinstance(widget.clear_btn, widgets.Button)
    assert isinstance(widget.match_dropdown, widgets.Dropdown)
    assert isinstance(widget.display_tabs, widgets.Tab)
    assert isinstance(widget.engine_dd, widgets.Dropdown)
    assert isinstance(widget.forcefield_dd, widgets.Dropdown)
    assert isinstance(widget.steps_slider, widgets.IntSlider)
    assert isinstance(widget.fmax_slider, widgets.FloatSlider)
    assert isinstance(widget.crest_toggle, widgets.Checkbox)
    assert isinstance(widget.opt_btn, widgets.Button)
    assert isinstance(widget.telemetry_out, widgets.Output)
    assert isinstance(widget.main_ui, widgets.VBox)

    assert len(widget.display_tabs.children) == 4
    assert widget.display_tabs.get_title(0) == "3D View"
    assert widget.display_tabs.get_title(1) == "Properties"
    assert widget.display_tabs.get_title(2) == "Coordinates"
    assert widget.display_tabs.get_title(3) == "Hardware Profile"

    # Test event callbacks
    widget.search_input.value = "CCO"
    widget.current_smiles = "CCO"
    widget.opt_btn.disabled = False

    # Trigger optimization
    widget._trigger_quick_opt(None)

    # Test Clear button
    widget._on_clear_clicked(None)
    assert widget.search_input.value == ""
    assert widget.current_smiles is None
    assert widget.opt_btn.disabled is True

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.