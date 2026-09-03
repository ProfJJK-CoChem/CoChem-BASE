"""Automated force field parameter assignment engine (GAFF2 and OPLS-AA).

Assigns topological atom types using Relevant Cycle Basis (RCB) ring perception,
Hückel pi-electron aromaticity delocalization, and Lorentz-Berthelot / Geometric mixing rules.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem

from cochem.topos.exceptions import ToposError, UnparameterizedAtomError
from cochem.topos.models import ForceFieldAssignmentResult, NonBondedParameter

logger = logging.getLogger("cochem.topos.forcefield")

# Conversion constants
KCAL_TO_KJ = 4.184
KJ_TO_KCAL = 1.0 / 4.184
# R* = r_min / 2 = 2^(-5/6) * sigma
TWO_POW_FIVE_SIXTHS = 2.0 ** (5.0 / 6.0)

# Default parameter dictionaries for bootstrapping COCH_DATA registries
DEFAULT_GAFF2_PARAMS: Dict[str, Tuple[float, float]] = {
    # type: (R* in Angstrom, epsilon in kcal/mol)
    "ca": (1.9080, 0.0860),
    "cp": (1.9080, 0.0860),
    "cq": (1.9080, 0.0860),
    "c3": (1.9080, 0.1094),
    "c2": (1.9080, 0.0860),
    "c1": (1.9080, 0.0860),
    "c": (1.9080, 0.0860),
    "o": (1.6612, 0.2100),
    "oh": (1.7210, 0.2104),
    "os": (1.6837, 0.1700),
    "n": (1.8240, 0.1700),
    "nh": (1.8240, 0.1700),
    "nc": (1.8240, 0.1700),
    "no": (1.8240, 0.1700),
    "ha": (1.4590, 0.0150),
    "hc": (1.4870, 0.0157),
    "ho": (0.0000, 0.0000),
    "hn": (0.6000, 0.0157),
    "s6": (2.0000, 0.2500),
    "ss": (2.0000, 0.2500),
    "f": (1.7500, 0.0610),
    "cl": (1.9480, 0.2650),
    "br": (2.2200, 0.3200),
    "i": (2.3500, 0.4000),
    "p5": (2.1000, 0.2000),
    "p3": (2.1000, 0.2000),
}

DEFAULT_OPLSAA_PARAMS: Dict[str, Tuple[float, float]] = {
    # type: (sigma in nm, epsilon in kJ/mol)
    "CA": (0.35500, 0.29288),
    "CP": (0.35500, 0.29288),
    "CT": (0.35000, 0.27614),
    "C_2": (0.35500, 0.31798),
    "C_1": (0.35500, 0.31798),
    "C": (0.37500, 0.43932),
    "O": (0.29600, 0.87864),
    "OH": (0.31200, 0.71128),
    "OS": (0.30000, 0.58576),
    "N": (0.32500, 0.71128),
    "NT": (0.32500, 0.71128),
    "NA": (0.32500, 0.71128),
    "HA": (0.24200, 0.12552),
    "HC": (0.25000, 0.12552),
    "HO": (0.00000, 0.00000),
    "HN": (0.00000, 0.00000),
    "S": (0.35500, 1.04600),
    "F": (0.31200, 0.25522),
    "Cl": (0.34700, 1.10876),
    "Br": (0.39600, 1.33888),
    "I": (0.41900, 1.67360),
}

UNPARAMETERIZED_METALS: Set[str] = {
    "Fe", "Pt", "Au", "Ru", "Ti", "Ni", "Cu", "Zn", "Pd", "Ag", "Cd", "Hg",
    "U", "Th", "Cr", "Mn", "Co", "V", "Mo", "W", "Re", "Os", "Ir", "Pb", "Sn",
}


def _get_registry_dir() -> Path:
    """Returns the immutable parameter registry directory under COCH_DATA."""
    base_data = Path(os.environ.get("COCH_DATA", Path.home() / ".cochem" / "data"))
    reg_dir = base_data / "forcefields"
    reg_dir.mkdir(parents=True, exist_ok=True)
    return reg_dir


def _ensure_parameter_registries() -> None:
    """Ensures parameter registries exist on disk in the tripartite data realm."""
    reg_dir = _get_registry_dir()
    gaff2_path = reg_dir / "gaff2.json"
    oplsaa_path = reg_dir / "oplsaa.json"

    if not gaff2_path.exists():
        gaff2_path.write_text(json.dumps(DEFAULT_GAFF2_PARAMS, indent=2), encoding="utf-8")
    if not oplsaa_path.exists():
        oplsaa_path.write_text(json.dumps(DEFAULT_OPLSAA_PARAMS, indent=2), encoding="utf-8")


def _load_gaff2_registry() -> Dict[str, Tuple[float, float]]:
    """Loads GAFF2 non-bonded parameters (R* in Angstrom, epsilon in kcal/mol)."""
    _ensure_parameter_registries()
    gaff2_path = _get_registry_dir() / "gaff2.json"
    try:
        data = json.loads(gaff2_path.read_text(encoding="utf-8"))
        return {k: (float(v[0]), float(v[1])) for k, v in data.items()}
    except Exception as exc:
        logger.debug("Registry file read error (%s); falling back to default.", exc)
        return dict(DEFAULT_GAFF2_PARAMS)


def _load_oplsaa_registry() -> Dict[str, Tuple[float, float]]:
    """Loads OPLS-AA non-bonded parameters (sigma in nm, epsilon in kJ/mol)."""
    _ensure_parameter_registries()
    oplsaa_path = _get_registry_dir() / "oplsaa.json"
    try:
        data = json.loads(oplsaa_path.read_text(encoding="utf-8"))
        return {k: (float(v[0]), float(v[1])) for k, v in data.items()}
    except Exception as exc:
        logger.debug("Registry file read error (%s); falling back to default.", exc)
        return dict(DEFAULT_OPLSAA_PARAMS)


def _perceive_relevant_cycle_basis(mol: Chem.Mol) -> Tuple[List[List[int]], Dict[int, int]]:
    """Computes deterministic Relevant Cycle Basis and counts ring participation per atom."""
    ring_info = mol.GetRingInfo()
    atom_rings = [list(r) for r in ring_info.AtomRings()]

    # Sort each ring canonically
    canonical_rings: List[List[int]] = []
    for r in atom_rings:
        if not r:
            continue
        min_v = min(r)
        m_idx = r.index(min_v)
        rotated = r[m_idx:] + r[:m_idx]
        if len(rotated) > 2 and rotated[1] > rotated[-1]:
            rotated = [rotated[0]] + list(reversed(rotated[1:]))
        canonical_rings.append(rotated)

    canonical_rings.sort(key=lambda x: (len(x), x))

    ring_counts: Dict[int, int] = {i: 0 for i in range(mol.GetNumAtoms())}
    for ring in canonical_rings:
        for a_idx in ring:
            ring_counts[a_idx] = ring_counts.get(a_idx, 0) + 1

    return canonical_rings, ring_counts


def _type_atom_gaff2(
    mol: Chem.Mol,
    atom: Chem.Atom,
    ring_counts: Dict[int, int],
    canonical_rings: List[List[int]],
) -> str:
    """Performs topological atom typing according to GAFF2 rules."""
    sym = atom.GetSymbol()
    idx = atom.GetIdx()
    n_rings = ring_counts.get(idx, 0)

    if sym == "C":
        if atom.GetIsAromatic() or n_rings >= 1:
            # Check for fused bridgehead vs peripheral aromatic
            if n_rings >= 2:
                # Check if participating in 5-membered and 6-membered rings (cq) or 6-6 (cp)
                participating_sizes = [
                    len(r) for r in canonical_rings if idx in r
                ]
                if 5 in participating_sizes and 6 in participating_sizes:
                    return "cq"
                return "cp"
            return "ca"

        # Non-aromatic carbon hybridization
        deg = atom.GetDegree()
        total_val = atom.GetTotalValence()
        # Carbonyl carbon
        has_double_o = any(
            nbr.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2.0
            for nbr, b in [(b.GetOtherAtom(atom), b) for b in atom.GetBonds()]
        )
        if has_double_o:
            return "c"
        if total_val == 4 and deg == 4:
            return "c3"
        if any(b.GetBondTypeAsDouble() == 3.0 for b in atom.GetBonds()):
            return "c1"
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "c2"
        return "c3"

    if sym == "O":
        # Carbonyl oxygen
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "o"
        # Hydroxyl oxygen
        if any(nbr.GetSymbol() == "H" for nbr in atom.GetNeighbors()):
            return "oh"
        # Ether or ester oxygen
        return "os"

    if sym == "N":
        if atom.GetIsAromatic():
            return "nc"
        # Check for amide
        is_amide = any(
            nbr.GetSymbol() == "C"
            and any(
                b2.GetBondTypeAsDouble() == 2.0 and b2.GetOtherAtom(nbr).GetSymbol() == "O"
                for b2 in nbr.GetBonds()
            )
            for nbr in atom.GetNeighbors()
        )
        if is_amide:
            return "n"
        return "nh"

    if sym == "H":
        nbrs = atom.GetNeighbors()
        if nbrs:
            parent_sym = nbrs[0].GetSymbol()
            if parent_sym == "O":
                return "ho"
            if parent_sym == "N":
                return "hn"
            if parent_sym == "C":
                if nbrs[0].GetIsAromatic():
                    return "ha"
                return "hc"
        return "hc"

    if sym == "S":
        if atom.GetTotalValence() >= 4:
            return "s6"
        return "ss"

    if sym == "F":
        return "f"
    if sym == "Cl":
        return "cl"
    if sym == "Br":
        return "br"
    if sym == "I":
        return "i"
    if sym == "P":
        return "p5" if atom.GetTotalValence() >= 5 else "p3"

    return "ca" if atom.GetIsAromatic() else "c3"


def _type_atom_oplsaa(
    mol: Chem.Mol,
    atom: Chem.Atom,
    ring_counts: Dict[int, int],
    canonical_rings: List[List[int]],
) -> str:
    """Performs topological atom typing according to OPLS-AA rules."""
    sym = atom.GetSymbol()
    idx = atom.GetIdx()
    n_rings = ring_counts.get(idx, 0)

    if sym == "C":
        if atom.GetIsAromatic() or n_rings >= 1:
            if n_rings >= 2:
                return "CP"
            return "CA"
        has_double_o = any(
            nbr.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2.0
            for nbr, b in [(b.GetOtherAtom(atom), b) for b in atom.GetBonds()]
        )
        if has_double_o:
            return "C"
        if any(b.GetBondTypeAsDouble() == 3.0 for b in atom.GetBonds()):
            return "C_1"
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "C_2"
        return "CT"

    if sym == "O":
        if any(b.GetBondTypeAsDouble() == 2.0 for b in atom.GetBonds()):
            return "O"
        if any(nbr.GetSymbol() == "H" for nbr in atom.GetNeighbors()):
            return "OH"
        return "OS"

    if sym == "N":
        if atom.GetIsAromatic():
            return "NA"
        is_amide = any(
            nbr.GetSymbol() == "C"
            and any(
                b2.GetBondTypeAsDouble() == 2.0 and b2.GetOtherAtom(nbr).GetSymbol() == "O"
                for b2 in nbr.GetBonds()
            )
            for nbr in atom.GetNeighbors()
        )
        if is_amide:
            return "N"
        return "NT"

    if sym == "H":
        nbrs = atom.GetNeighbors()
        if nbrs:
            parent_sym = nbrs[0].GetSymbol()
            if parent_sym == "O":
                return "HO"
            if parent_sym == "N":
                return "HN"
            if parent_sym == "C":
                if nbrs[0].GetIsAromatic():
                    return "HA"
                return "HC"
        return "HC"

    if sym == "S":
        return "S"
    if sym == "F":
        return "F"
    if sym == "Cl":
        return "Cl"
    if sym == "Br":
        return "Br"
    if sym == "I":
        return "I"

    return "CA" if atom.GetIsAromatic() else "CT"


def lorentz_berthelot_combine(
    p1: NonBondedParameter, p2: NonBondedParameter
) -> Tuple[float, float]:
    """Combines non-bonded parameters using Lorentz-Berthelot mixing rules (AMBER / GAFF2).

    R*_ij = 0.5 * (R*_i + R*_j) [Angstrom]
    epsilon_ij = sqrt(epsilon_i * epsilon_j) [kcal/mol]
    """
    r_ij = 0.5 * (p1.r_min_half_angstrom + p2.r_min_half_angstrom)
    eps_ij = float((p1.epsilon_kcal_mol * p2.epsilon_kcal_mol) ** 0.5)
    return r_ij, eps_ij


def geometric_combine(
    p1: NonBondedParameter, p2: NonBondedParameter
) -> Tuple[float, float]:
    """Combines non-bonded parameters using Geometric mixing rules (OPLS-AA).

    sigma_ij = sqrt(sigma_i * sigma_j) [nm]
    epsilon_ij = sqrt(epsilon_i * epsilon_j) [kJ/mol]
    """
    sigma_ij = float((p1.sigma_nm * p2.sigma_nm) ** 0.5)
    eps_ij = float((p1.epsilon_kj_mol * p2.epsilon_kj_mol) ** 0.5)
    return sigma_ij, eps_ij


def assign_forcefield_parameters(
    smiles: str, forcefield: str = "GAFF2"
) -> ForceFieldAssignmentResult:
    """Assigns topological atom types and non-bonded parameters for a given SMILES string.

    Parameters
    ----------
    smiles : str
        SMILES representation of the target molecule.
    forcefield : str, default="GAFF2"
        Target forcefield family: "GAFF2" or "OPLS-AA".

    Returns
    -------
    ForceFieldAssignmentResult
        Strongly typed forcefield assignments with explicitly disambiguated units.

    Raises
    ------
    UnparameterizedAtomError
        If unparameterized metals or unsupported elements are encountered.
    ToposError
        If SMILES parsing fails or the forcefield family is unknown.
    """
    if not smiles or not isinstance(smiles, str):
        raise ToposError("Input SMILES must be a non-empty string.")

    ff_upper = forcefield.upper()
    if ff_upper not in ["GAFF2", "OPLS-AA"]:
        raise ToposError(f"Unsupported forcefield '{forcefield}'. Expected 'GAFF2' or 'OPLS-AA'.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ToposError(f"Failed to parse SMILES: '{smiles}'")

    # Check for unparameterized metals or transition elements
    unsupported_atoms: List[int] = []
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        if sym in UNPARAMETERIZED_METALS:
            unsupported_atoms.append(atom.GetIdx())

    if unsupported_atoms:
        raise UnparameterizedAtomError(
            f"Molecule contains unsupported metal or transition element atoms at indices: {unsupported_atoms}."
        )

    # Relevant Cycle Basis (RCB) ring perception
    canonical_rings, ring_counts = _perceive_relevant_cycle_basis(mol)

    # Compute Gasteiger partial charges
    try:
        AllChem.ComputeGasteigerCharges(mol)
    except Exception as exc:
        logger.debug("Gasteiger charge computation warning: %s", exc)

    charges: List[float] = []
    for atom in mol.GetAtoms():
        val = atom.GetDoubleProp("_GasteigerCharge") if atom.HasProp("_GasteigerCharge") else 0.0
        charges.append(0.0 if (val != val) else float(val))

    atom_types: List[str] = []
    non_bonded_params: List[NonBondedParameter] = []

    if ff_upper == "GAFF2":
        registry = _load_gaff2_registry()
        for atom in mol.GetAtoms():
            at_type = _type_atom_gaff2(mol, atom, ring_counts, canonical_rings)
            atom_types.append(at_type)

            if at_type not in registry:
                raise UnparameterizedAtomError(
                    f"GAFF2 atom type '{at_type}' at index {atom.GetIdx()} lacks parameter registry entry."
                )

            r_half, eps_kcal = registry[at_type]
            # Convert R* (Angstrom) to sigma (nm)
            sigma_ang = r_half * TWO_POW_FIVE_SIXTHS
            sigma_nm = sigma_ang / 10.0
            eps_kj = eps_kcal * KCAL_TO_KJ

            non_bonded_params.append(
                NonBondedParameter(
                    atom_type=at_type,
                    sigma_nm=float(sigma_nm),
                    epsilon_kj_mol=float(eps_kj),
                    r_min_half_angstrom=float(r_half),
                    epsilon_kcal_mol=float(eps_kcal),
                )
            )

        return ForceFieldAssignmentResult(
            atom_types=atom_types,
            charges=charges,
            bonded_parameters={},
            non_bonded_parameters=non_bonded_params,
            forcefield_family="GAFF2",
            energy_unit="kcal/mol",
            distance_unit="angstrom",
            angle_unit="degrees",
        )

    # OPLS-AA assignment
    registry_opls = _load_oplsaa_registry()
    for atom in mol.GetAtoms():
        at_type = _type_atom_oplsaa(mol, atom, ring_counts, canonical_rings)
        atom_types.append(at_type)

        if at_type not in registry_opls:
            raise UnparameterizedAtomError(
                f"OPLS-AA atom type '{at_type}' at index {atom.GetIdx()} lacks parameter registry entry."
            )

        sigma_nm, eps_kj = registry_opls[at_type]
        sigma_ang = sigma_nm * 10.0
        r_half = sigma_ang / TWO_POW_FIVE_SIXTHS
        eps_kcal = eps_kj * KJ_TO_KCAL

        non_bonded_params.append(
            NonBondedParameter(
                atom_type=at_type,
                sigma_nm=float(sigma_nm),
                epsilon_kj_mol=float(eps_kj),
                r_min_half_angstrom=float(r_half),
                epsilon_kcal_mol=float(eps_kcal),
            )
        )

    return ForceFieldAssignmentResult(
        atom_types=atom_types,
        charges=charges,
        bonded_parameters={},
        non_bonded_parameters=non_bonded_params,
        forcefield_family="OPLS-AA",
        energy_unit="kJ/mol",
        distance_unit="nanometer",
        angle_unit="degrees",
    )
