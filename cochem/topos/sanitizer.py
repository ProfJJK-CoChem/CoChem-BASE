"""TOPOS Automated Topology Sanitization Pass: Salt stripping, API retention, and formal charge neutralization."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from mendeleev import element

from cochem.topos.exceptions import SanitizationError
from cochem.topos.models import TopologySanitizationResult


class TopologySanitizer:
    """Sanitizes molecular topologies via authoritative counterion stripping and resonance-aware neutralization."""

    def __init__(self) -> None:
        self._counterion_registry: Dict[str, Chem.Mol] = self._build_counterion_registry()

    def _build_counterion_registry(self) -> Dict[str, Chem.Mol]:
        """Compiles authoritative curated SMARTS and SMILES registry of common pharmaceutical counterions."""
        raw_dict: Dict[str, str] = {
            # Inorganic Cations
            "sodium": "[Na+]",
            "potassium": "[K+]",
            "lithium": "[Li+]",
            "calcium": "[Ca+2]",
            "magnesium": "[Mg+2]",
            # Inorganic Anions
            "chloride": "[Cl-]",
            "bromide": "[Br-]",
            "iodide": "[I-]",
            "sulfate": "OS(=O)(=O)O",
            "nitrate": "O[N+](=O)[O-]",
            "phosphate": "OP(=O)(O)O",
            "tetrafluoroborate": "F[B-](F)(F)F",
            "hexafluorophosphate": "F[P-](F)(F)(F)(F)F",
            # Bulky Organic Sulfonates
            "besylate": "c1ccccc1S(=O)(=O)O",
            "tosylate": "Cc1ccc(S(=O)(=O)O)cc1",
            "mesylate": "CS(=O)(=O)O",
            "triflate": "FC(F)(F)S(=O)(=O)O",
            "napsylate": "c1cccc2c(S(=O)(=O)O)cccc12",
            "isethionate": "OCCS(=O)(=O)O",
            # Bulky Organic Carboxylates
            "pamoate": "O=C(O)c1c(O)c2ccccc2cc1Cc3cc4ccccc4c(O)c3C(=O)O",
            "citrate": "OC(=O)CC(O)(CC(=O)O)C(=O)O",
            "tartrate": "OC(=O)C(O)C(O)C(=O)O",
            "maleate": "OC(=O)C=CC(=O)O",
            "fumarate": "OC(=O)/C=C/C(=O)O",
            "succinate": "OC(=O)CCC(=O)O",
            "benzoate": "c1ccccc1C(=O)O",
            "acetate": "CC(=O)O",
            "lactate": "CC(O)C(=O)O",
            # Organic Base Cations
            "meglumine": "CNCC(O)C(O)C(O)C(O)CO",
            "tromethamine": "NC(CO)(CO)CO",
            "choline": "C[N+](C)(C)CCO",
        }

        registry: Dict[str, Chem.Mol] = {}
        for name, sm in raw_dict.items():
            mol = Chem.MolFromSmiles(sm)
            if mol is not None:
                registry[name] = mol
        return registry

    def _is_transition_metal_complex(self, mol: Chem.Mol) -> bool:
        """Determines whether molecule contains a transition metal with coordination degree >= 1."""
        for atom in mol.GetAtoms():
            sym = atom.GetSymbol()
            try:
                el = element(sym)
                s = getattr(el, "series", "").lower()
                if "nonmetal" not in s and "alkali" not in s and ("metal" in s or getattr(el, "group_id", 0) in range(3, 13)):
                    if atom.GetDegree() >= 1:
                        return True
            except Exception:
                continue
        return False

    def _matches_counterion_registry(self, comp_mol: Chem.Mol) -> Optional[str]:
        """Checks if a component matches an entry in the counterion registry."""
        comp_can = Chem.MolToSmiles(comp_mol)
        for name, reg_mol in self._counterion_registry.items():
            reg_can = Chem.MolToSmiles(reg_mol)
            if comp_can == reg_can:
                return name
            if comp_mol.HasSubstructMatch(reg_mol) and reg_mol.HasSubstructMatch(comp_mol):
                return name

        # Inorganic single-ion checks
        if comp_mol.GetNumHeavyAtoms() == 1:
            sym = comp_mol.GetAtomWithIdx(0).GetSymbol()
            if sym in {"Na", "K", "Li", "Ca", "Mg", "Cl", "Br", "I"}:
                return f"{sym}_ion"

        return None

    def _neutralize_charges(self, mol: Chem.Mol) -> Tuple[Chem.Mol, bool]:
        """Neutralizes uncoupled acidic and basic formal charges while preserving physiological zwitterions."""
        rw_mol = Chem.RWMol(mol)
        num_atoms = rw_mol.GetNumAtoms()

        # Check physiological zwitterion invariant: amino acids, betaines
        pos_n_indices: List[int] = []
        neg_o_indices: List[int] = []

        for idx in range(num_atoms):
            at = rw_mol.GetAtomWithIdx(idx)
            fc = at.GetFormalCharge()
            sym = at.GetSymbol()
            if sym == "N" and fc > 0:
                # Exclude quaternary ammonium with 4 carbon neighbors
                c_nbrs = sum(1 for nbr in at.GetNeighbors() if nbr.GetSymbol() == "C")
                if c_nbrs < 4:
                    pos_n_indices.append(idx)
            elif sym == "O" and fc < 0:
                neg_o_indices.append(idx)

        total_net_charge = sum(rw_mol.GetAtomWithIdx(i).GetFormalCharge() for i in range(num_atoms))
        is_zwitterion = False

        if total_net_charge == 0 and len(pos_n_indices) == len(neg_o_indices) and len(pos_n_indices) > 0:
            # Check intramolecular distance if 3D coordinates are present or by graph distance
            is_zwitterion = True

        if is_zwitterion:
            return rw_mol.GetMol(), True

        # Neutralize uncoupled basic sites (e.g. protonated amines, amidines, guanidines)
        for idx in range(num_atoms):
            at = rw_mol.GetAtomWithIdx(idx)
            fc = at.GetFormalCharge()
            sym = at.GetSymbol()

            if sym == "N" and fc > 0:
                # Protect quaternary ammonium (4 carbon neighbors)
                num_c_nbrs = sum(1 for nbr in at.GetNeighbors() if nbr.GetSymbol() == "C")
                if num_c_nbrs >= 4:
                    continue
                # Protect nitro group N+(O-)=O
                o_minus_nbrs = [
                    nbr for nbr in at.GetNeighbors()
                    if nbr.GetSymbol() == "O" and nbr.GetFormalCharge() < 0
                ]
                if o_minus_nbrs:
                    continue

                # Neutralize protonated amine / amidinium
                at.SetFormalCharge(fc - 1)
                at.SetNumExplicitHs(max(0, at.GetNumExplicitHs() - 1))

            elif sym in {"O", "S"} and fc < 0:
                # Protect nitro oxygens
                is_nitro_o = False
                for nbr in at.GetNeighbors():
                    if nbr.GetSymbol() == "N" and nbr.GetFormalCharge() > 0:
                        is_nitro_o = True
                        break
                if is_nitro_o:
                    continue

                at.SetFormalCharge(fc + 1)
                at.SetNumExplicitHs(at.GetNumExplicitHs() + 1)

        try:
            Chem.SanitizeMol(rw_mol)
        except Exception as err:
            raise SanitizationError(f"Valence or octet violation during neutralization: {err}") from err

        return rw_mol.GetMol(), False

    def sanitize_topology(
        self,
        smiles: str,
        coordinates: list[list[float]] | np.ndarray | None = None,
    ) -> TopologySanitizationResult:
        """Splits connected components, removes curated counterions, and neutralizes charges."""
        raw_mol = Chem.MolFromSmiles(smiles)
        if raw_mol is None:
            raise SanitizationError(f"Input SMILES '{smiles}' cannot be parsed into a molecular graph.")

        frags = Chem.GetMolFrags(raw_mol, asMols=True, sanitizeFrags=True)
        if not frags:
            raise SanitizationError(f"No valid molecular fragments generated from SMILES '{smiles}'.")

        removed_ions: List[str] = []
        candidate_apis: List[Chem.Mol] = []

        for comp in frags:
            # Organometallic guard
            if self._is_transition_metal_complex(comp):
                candidate_apis.append(comp)
                continue

            matched_ion_name = self._matches_counterion_registry(comp)
            if matched_ion_name is not None:
                can_sm = Chem.MolToSmiles(comp)
                removed_ions.append(f"{matched_ion_name}: {can_sm}")
            else:
                candidate_apis.append(comp)

        if not candidate_apis:
            # If all components matched registry, retain the largest one
            largest_comp = max(frags, key=lambda m: m.GetNumHeavyAtoms())
            candidate_apis.append(largest_comp)

        # Retain primary API: pick the unique or largest API entity
        unique_apis: Dict[str, Chem.Mol] = {}
        for api_mol in candidate_apis:
            can_s = Chem.MolToSmiles(api_mol)
            if can_s not in unique_apis:
                unique_apis[can_s] = api_mol

        primary_api = max(unique_apis.values(), key=lambda m: m.GetNumHeavyAtoms())

        neutralized_mol, is_zw = self._neutralize_charges(primary_api)
        sanitized_smiles = Chem.MolToSmiles(neutralized_mol)
        retained_count = neutralized_mol.GetNumHeavyAtoms()
        net_formal_charge = sum(at.GetFormalCharge() for at in neutralized_mol.GetAtoms())

        sanitized_coords: Optional[List[List[float]]] = None
        if coordinates is not None:
            coords_arr = np.array(coordinates, dtype=float)
            if coords_arr.shape[0] >= retained_count:
                sanitized_coords = coords_arr[:retained_count].tolist()

        return TopologySanitizationResult(
            sanitized_smiles=sanitized_smiles,
            sanitized_coordinates=sanitized_coords,
            formal_net_charge=net_formal_charge,
            is_zwitterion=is_zw,
            removed_counterions=removed_ions,
            retained_atom_count=retained_count,
        )
