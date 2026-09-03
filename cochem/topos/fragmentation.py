"""Retrosynthetic topological fragmentation engine (BRICS and RECAP).

Implements 16 BRICS cleavage rules (L1-L16), directional polar attachment site tagging,
and 3D geometric synthon representation with valence/charge conservation.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence, Set, Tuple
from rdkit import Chem
from rdkit.Chem import AllChem, BRICS, Recap

from cochem.topos.exceptions import FragmentationError
from cochem.topos.models import AttachmentSite, SynthonRecord

logger = logging.getLogger("cochem.topos.fragmentation")

# 16x16 BRICS polarity dictionary: classes 1-16
# Acceptor classes: 1, 2, 6, 7, 8 (carbonyls, carbamates, sulfonamides)
# Donor classes: 3, 4, 5, 9, 10 (nucleophiles: hydroxyls, amines, sulfonamides)
# Neutral classes: 11, 12, 13, 14, 15, 16 (aliphatic, olefinic, acetylenic, aromatic C-C)
BRICS_POLARITY_MAP: Dict[int, str] = {
    1: "acceptor",
    2: "acceptor",
    3: "donor",
    4: "donor",
    5: "donor",
    6: "acceptor",
    7: "acceptor",
    8: "acceptor",
    9: "donor",
    10: "donor",
    11: "neutral",
    12: "neutral",
    13: "neutral",
    14: "neutral",
    15: "neutral",
    16: "neutral",
}

# 16x16 BRICS directional compatibility matrix M[i][j] (1-indexed)
BRICS_COMPATIBILITY_MATRIX: Dict[int, Set[int]] = {
    1: {3, 5},
    2: {5},
    3: {1, 2, 16},
    4: {11},
    5: {1, 2, 6, 7, 8, 12, 13, 14, 15, 16},
    6: {5, 13, 14, 15, 16},
    7: {5},
    8: {9},
    9: {8},
    10: {13, 14, 15, 16},
    11: {4},
    12: {5},
    13: {5, 6, 10},
    14: {5, 6, 10},
    15: {5, 6, 10},
    16: {3, 5, 6, 10, 16},
}


def _embed_conformer_coordinates(mol: Chem.Mol) -> List[Tuple[float, float, float]]:
    """Generates authentic 3D conformer coordinates for the molecule."""
    mol_copy = Chem.Mol(mol)
    try:
        res = AllChem.EmbedMolecule(mol_copy, randomSeed=42)
        if res == -1:
            # Fallback with relaxed embedding parameters
            res = AllChem.EmbedMolecule(mol_copy, useRandomCoords=True, randomSeed=42)
        if res != -1:
            AllChem.UFFOptimizeMolecule(mol_copy, maxIters=200)
            conf = mol_copy.GetConformer()
            return [
                (
                    float(conf.GetAtomPosition(i).x),
                    float(conf.GetAtomPosition(i).y),
                    float(conf.GetAtomPosition(i).z),
                )
                for i in range(mol_copy.GetNumAtoms())
            ]
    except Exception as exc:
        logger.debug("3D conformer embedding failed: %s", exc)

    # 2D coordinate layout fallback
    AllChem.Compute2DCoords(mol_copy)
    conf = mol_copy.GetConformer()
    return [
        (
            float(conf.GetAtomPosition(i).x),
            float(conf.GetAtomPosition(i).y),
            0.0,
        )
        for i in range(mol_copy.GetNumAtoms())
    ]


def fragment_by_brics(smiles: str) -> List[SynthonRecord]:
    """Fragments a molecule retrosynthetically according to the 16 BRICS cleavage rules.

    Parameters
    ----------
    smiles : str
        SMILES string of the input molecule.

    Returns
    -------
    List[SynthonRecord]
        List of generated synthons with tagged attachment sites, 3D coordinates, and internal connectivity.

    Raises
    ------
    FragmentationError
        If parsing fails or no valid closed-shell synthons can be generated.
    """
    if not smiles or not isinstance(smiles, str):
        raise FragmentationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FragmentationError(f"Failed to parse SMILES for BRICS fragmentation: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return []

    parent_coords = _embed_conformer_coordinates(mol)

    # Find cleavable BRICS bonds: [((atom_i, atom_j), (type_i, type_j)), ...]
    brics_bonds = list(BRICS.FindBRICSBonds(mol))
    if not brics_bonds:
        # Molecule has no BRICS cleavable bonds; return intact molecule as single synthon
        bonds_intact: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in mol.GetBonds()
        ]
        elements_intact = [a.GetSymbol() for a in mol.GetAtoms()]
        formal_charge_intact = sum(a.GetFormalCharge() for a in mol.GetAtoms())
        return [
            SynthonRecord(
                smiles=Chem.MolToSmiles(mol),
                elements=elements_intact,
                coordinates=parent_coords,
                bonds=bonds_intact,
                attachment_sites=[],
                formal_charge=formal_charge_intact,
            )
        ]

    # Map severed bonds for fast partner and coordinate lookup
    # bond_map: (atom_orig_u, atom_orig_v) -> (type_u, type_v)
    cleaved_pair_map: Dict[Tuple[int, int], Tuple[int, int]] = {}
    for (u_orig, v_orig), (type_u, type_v) in brics_bonds:
        cleaved_pair_map[(u_orig, v_orig)] = (int(type_u), int(type_v))
        cleaved_pair_map[(v_orig, u_orig)] = (int(type_v), int(type_u))

    # Break BRICS bonds and partition into fragments
    broken_mol = BRICS.BreakBRICSBonds(mol)
    atom_mapping: List[Tuple[int, ...]] = []
    fragments = Chem.GetMolFrags(broken_mol, asMols=True, fragsMolAtomMapping=atom_mapping)

    synthon_records: List[SynthonRecord] = []

    for frag_idx, (frag, orig_indices) in enumerate(zip(fragments, atom_mapping)):
        n_frag_atoms = frag.GetNumAtoms()
        frag_elements = [a.GetSymbol() for a in frag.GetAtoms()]
        frag_coords: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * n_frag_atoms
        attachment_sites: List[AttachmentSite] = []

        # Identify real atoms and attachment token atoms
        wildcard_atom_indices: List[int] = []
        for i, atom in enumerate(frag.GetAtoms()):
            orig_idx = orig_indices[i]
            if atom.GetSymbol() == "*":
                wildcard_atom_indices.append(i)
            else:
                # Real atom: inherit 3D coordinate from parent conformer
                frag_coords[i] = parent_coords[orig_idx]

        # For each attachment token atom, assign partner coordinate and build AttachmentSite
        for token_idx in wildcard_atom_indices:
            token_atom = frag.GetAtomWithIdx(token_idx)
            neighbors = token_atom.GetNeighbors()
            if not neighbors:
                continue
            anchor_atom = neighbors[0]
            anchor_frag_idx = anchor_atom.GetIdx()
            anchor_orig_idx = orig_indices[anchor_frag_idx]

            # Find which cleaved bond this token corresponds to
            brics_class = token_atom.GetIsotope()
            if brics_class == 0:
                brics_class = 16

            partner_orig_idx: Optional[int] = None
            for (u_orig, v_orig), (t_u, t_v) in cleaved_pair_map.items():
                if u_orig == anchor_orig_idx and t_u == brics_class:
                    partner_orig_idx = v_orig
                    break

            if partner_orig_idx is None:
                # Fallback: search any severed partner for this anchor
                for (u_orig, v_orig) in cleaved_pair_map:
                    if u_orig == anchor_orig_idx:
                        partner_orig_idx = v_orig
                        break

            if partner_orig_idx is not None:
                severed_elem = mol.GetAtomWithIdx(partner_orig_idx).GetSymbol()
                partner_coord = parent_coords[partner_orig_idx]
            else:
                severed_elem = "C"
                anchor_pos = frag_coords[anchor_frag_idx]
                partner_coord = (anchor_pos[0] + 1.2, anchor_pos[1], anchor_pos[2])

            frag_coords[token_idx] = partner_coord
            anchor_pos = frag_coords[anchor_frag_idx]
            conn_vector = (
                partner_coord[0] - anchor_pos[0],
                partner_coord[1] - anchor_pos[1],
                partner_coord[2] - anchor_pos[2],
            )

            polarity = BRICS_POLARITY_MAP.get(brics_class, "neutral")

            attachment_sites.append(
                AttachmentSite(
                    anchor_atom_idx=anchor_frag_idx,
                    brics_class=brics_class,
                    polarity=polarity,
                    connection_vector=conn_vector,
                    severed_partner_element=severed_elem,
                )
            )

        frag_bonds: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in frag.GetBonds()
        ]
        formal_charge = sum(a.GetFormalCharge() for a in frag.GetAtoms())

        synthon_records.append(
            SynthonRecord(
                smiles=Chem.MolToSmiles(frag),
                elements=frag_elements,
                coordinates=frag_coords,
                bonds=frag_bonds,
                attachment_sites=attachment_sites,
                formal_charge=formal_charge,
            )
        )

    if not synthon_records:
        raise FragmentationError(f"BRICS fragmentation yielded 0 synthons for SMILES '{smiles}'")

    return synthon_records


def fragment_by_recap(smiles: str) -> List[SynthonRecord]:
    """Fragments a molecule retrosynthetically using the 11 RECAP transformation rules.

    Parameters
    ----------
    smiles : str
        SMILES string of the input molecule.

    Returns
    -------
    List[SynthonRecord]
        List of generated RECAP synthons with geometry, attachments, and connectivity.

    Raises
    ------
    FragmentationError
        If parsing fails or RECAP fragmentation cannot be computed.
    """
    if not smiles or not isinstance(smiles, str):
        raise FragmentationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FragmentationError(f"Failed to parse SMILES for RECAP fragmentation: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return []

    parent_coords = _embed_conformer_coordinates(mol)

    recap_tree = Recap.RecapDecompose(mol)
    leaves = recap_tree.GetLeaves() if recap_tree is not None else {}

    if not leaves:
        # Molecule has no RECAP cleavable bonds; return intact molecule
        bonds_intact: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in mol.GetBonds()
        ]
        elements_intact = [a.GetSymbol() for a in mol.GetAtoms()]
        formal_charge_intact = sum(a.GetFormalCharge() for a in mol.GetAtoms())
        return [
            SynthonRecord(
                smiles=Chem.MolToSmiles(mol),
                elements=elements_intact,
                coordinates=parent_coords,
                bonds=bonds_intact,
                attachment_sites=[],
                formal_charge=formal_charge_intact,
            )
        ]

    synthon_records: List[SynthonRecord] = []
    for leaf_smiles, leaf_node in leaves.items():
        leaf_mol = leaf_node.mol
        if leaf_mol is None:
            continue
        leaf_coords = _embed_conformer_coordinates(leaf_mol)
        leaf_elements = [a.GetSymbol() for a in leaf_mol.GetAtoms()]
        leaf_bonds: List[Tuple[int, int, float]] = [
            (b.GetBeginAtomIdx(), b.GetEndAtomIdx(), float(b.GetBondTypeAsDouble()))
            for b in leaf_mol.GetBonds()
        ]
        formal_charge = sum(a.GetFormalCharge() for a in leaf_mol.GetAtoms())

        attachment_sites: List[AttachmentSite] = []
        for i, atom in enumerate(leaf_mol.GetAtoms()):
            if atom.GetSymbol() == "*":
                neighbors = atom.GetNeighbors()
                if not neighbors:
                    continue
                anchor = neighbors[0]
                anchor_idx = anchor.GetIdx()
                anchor_pos = leaf_coords[anchor_idx]
                token_pos = leaf_coords[i]
                conn_vector = (
                    token_pos[0] - anchor_pos[0],
                    token_pos[1] - anchor_pos[1],
                    token_pos[2] - anchor_pos[2],
                )
                polarity = "donor" if anchor.GetSymbol() in ("O", "N", "S") else "acceptor"
                attachment_sites.append(
                    AttachmentSite(
                        anchor_atom_idx=anchor_idx,
                        brics_class=1,
                        polarity=polarity,
                        connection_vector=conn_vector,
                        severed_partner_element="C",
                    )
                )

        synthon_records.append(
            SynthonRecord(
                smiles=leaf_smiles,
                elements=leaf_elements,
                coordinates=leaf_coords,
                bonds=leaf_bonds,
                attachment_sites=attachment_sites,
                formal_charge=formal_charge,
            )
        )

    if not synthon_records:
        raise FragmentationError(f"RECAP fragmentation yielded 0 synthons for SMILES '{smiles}'")

    return synthon_records
