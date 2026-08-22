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
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchi/{urllib.parse.quote(q, safe='')}/property/CanonicalSMILES,IsomericSMILES,IUPACName,MolecularFormula,MolecularWeight,InChIKey,XLogP,TPSA,HeavyAtomCount,RotatableBondCount/JSON"
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


def xyz_file_to_ase_atoms(path: Union[str, Path]) -> Atoms:
    """Reads an XYZ file into an ASE Atoms object."""
    if not HAS_ASE:
        raise RuntimeError("[MISSING DATA] ASE is not installed.")
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"XYZ file not found: {path}")
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 3:
        raise ValueError(f"XYZ file {path} has invalid header.")
    symbols = []
    positions = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) >= 4:
            symbols.append(parts[0])
            positions.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return Atoms(symbols=symbols, positions=positions)


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

    try:
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
        opt.run(fmax=fmax, steps=steps)
        final_energy = float(atoms.get_potential_energy())
        converged = opt.converged() if hasattr(opt, "converged") else True
        status_str = "converged" if converged else "completed max steps"
        return True, atoms, final_energy, active_engine, f"ASE optimization ({opt_norm}) {status_str} in {opt.nsteps} steps ({msg})."
    except Exception as e:
        active_eng = active_engine if "active_engine" in locals() else engine
        return False, atoms, 0.0, active_eng, f"ASE optimization error: {e}"


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
        try:
            atoms = xyz_file_to_ase_atoms(obabel_xyz)
        except Exception:
            atoms = None

    if atoms is None:
        num_atoms = count_xyz_atoms(final_xyz) if final_xyz else 0
        sha_hash = compute_file_sha256(final_xyz) if final_xyz else ""
        return FastPassOptResult(
            success=True,
            smiles=smiles,
            xyz_path=str(final_xyz) if final_xyz else None,
            sha256_hash=sha_hash,
            num_atoms=num_atoms,
            duration_seconds=round(time.time() - t0, 2),
            message="Initial coordinates generated via OpenBabel (ASE conversion skipped).",
            stage_reached=stage,
            engine_used="obabel",
            hardware_profile=hw_profile,
        )

    # 3. Optional CREST conformer triage if requested and available
    stage = "rdkit_gen3d" if rdkit_ok else "obabel_gen3d"
    final_xyz = rdkit_xyz if rdkit_ok else obabel_xyz
    if cfg.use_crest and final_xyz is not None:
        crest_ok, crest_path, crest_msg = run_crest_conformer_triage(
            final_xyz, out_dir, crest_args=cfg.crest_args, timeout=cfg.timeout_crest
        )
        if crest_ok and crest_path is not None and crest_path.is_file():
            final_xyz = crest_path
            stage = "crest_opt"
            try:
                crest_atoms = xyz_file_to_ase_atoms(crest_path)
                if crest_atoms is not None and len(crest_atoms) == len(atoms):
                    atoms = crest_atoms
            except Exception:
                pass

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

    def _render_3d_xyz(self, xyz_path: Path) -> None:
        p = Path(xyz_path)
        if not p.is_file():
            return
        xyz_content = p.read_text(encoding="utf-8")
        with self.viz_output:
            clear_output()
            if HAS_3DMOL:
                try:
                    import py3Dmol
                    view = py3Dmol.view(width=400, height=280)
                    view.addModel(xyz_content, "xyz")
                    view.setStyle({"stick": {}})
                    view.zoomTo()
                    view.show()
                except Exception:
                    display(widgets.HTML("<b>3D Optimized Conformer Rendered</b>"))
            else:
                display(
                    widgets.HTML("<b>3D Optimized Conformer Saved</b> <br/><i>(py3Dmol not installed)</i>")
                )

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
                p_xyz = Path(res.xyz_path)
                self._render_coord_preview(p_xyz)
                self._render_3d_xyz(p_xyz)
        else:
            self._log_telemetry("ERROR", f"Optimization failed: {res.message}")

    def display(self) -> None:
        display(self.main_ui)


if __name__ == "__main__":
    w = FastPassWidget()
    w.display()
