"""Topology difference and maximum common connected substructure (MCCS) diff tool.

Implements modular product graph construction, Bron-Kerbosch maximal clique detection,
and localized chemical mutation tracking across molecular topologies.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Tuple
import networkx as nx
from rdkit import Chem
from rdkit.Chem import rdFMCS

from cochem.topos.exceptions import TopologyDiffError
from cochem.topos.models import SubgraphDeltaRecord, TopologyDelta

logger = logging.getLogger("cochem.topos.diff")


def _bron_kerbosch_pivot(
    r_set: Set[int],
    p_set: Set[int],
    x_set: Set[int],
    adj: Dict[int, Set[int]],
    cliques: List[Set[int]],
) -> None:
    """Finds maximal cliques using the Bron-Kerbosch algorithm with vertex pivoting."""
    if not p_set and not x_set:
        cliques.append(set(r_set))
        return

    # Choose pivot vertex maximizing |P ∩ N(u)|
    pivot = max(p_set | x_set, key=lambda u: len(p_set & adj.get(u, set())))
    for v in list(p_set - adj.get(pivot, set())):
        _bron_kerbosch_pivot(
            r_set | {v},
            p_set & adj.get(v, set()),
            x_set & adj.get(v, set()),
            adj,
            cliques,
        )
        p_set.remove(v)
        x_set.add(v)


def _find_mccs_mapping(mol_a: Chem.Mol, mol_b: Chem.Mol) -> Dict[int, int]:
    """Finds the maximum common connected substructure mapping from mol_a to mol_b.

    Attempts modular product graph Bron-Kerbosch maximal clique matching,
    with robust fallback to RDKit's topological FMCS algorithm.
    """
    n_a = mol_a.GetNumAtoms()
    n_b = mol_b.GetNumAtoms()

    # If small enough for direct modular product graph clique detection
    if n_a > 0 and n_b > 0 and n_a * n_b <= 400:
        # Build modular product graph vertices
        vertices: List[Tuple[int, int]] = []
        for i, a_atom in enumerate(mol_a.GetAtoms()):
            for j, b_atom in enumerate(mol_b.GetAtoms()):
                if a_atom.GetSymbol() == b_atom.GetSymbol():
                    vertices.append((i, j))

        v_count = len(vertices)
        if v_count > 0:
            adj: Dict[int, Set[int]] = {k: set() for k in range(v_count)}
            for u_idx in range(v_count):
                u_a, u_b = vertices[u_idx]
                for v_idx in range(u_idx + 1, v_count):
                    v_a, v_b = vertices[v_idx]
                    if u_a == v_a or u_b == v_b:
                        continue

                    bond_a = mol_a.GetBondBetweenAtoms(u_a, v_a)
                    bond_b = mol_b.GetBondBetweenAtoms(u_b, v_b)

                    has_bond_a = bond_a is not None
                    has_bond_b = bond_b is not None

                    if has_bond_a == has_bond_b:
                        if not has_bond_a:
                            adj[u_idx].add(v_idx)
                            adj[v_idx].add(u_idx)
                        else:
                            # Verify compatible bond orders
                            bo_a = bond_a.GetBondTypeAsDouble()
                            bo_b = bond_b.GetBondTypeAsDouble()
                            if abs(bo_a - bo_b) < 1e-4:
                                adj[u_idx].add(v_idx)
                                adj[v_idx].add(u_idx)

            cliques: List[Set[int]] = []
            _bron_kerbosch_pivot(set(), set(range(v_count)), set(), adj, cliques)
            if cliques:
                max_clique = max(cliques, key=len)
                mapping: Dict[int, int] = {}
                for v_idx in max_clique:
                    u_a, u_b = vertices[v_idx]
                    mapping[u_a] = u_b
                if len(mapping) > 0:
                    return mapping

    # FMCS detection
    try:
        mcs_res = rdFMCS.FindMCS(
            [mol_a, mol_b],
            completeRingsOnly=True,
            ringMatchesRingOnly=False,
            timeout=30,
        )
        if mcs_res and mcs_res.smartsString:
            patt = Chem.MolFromSmarts(mcs_res.smartsString)
            if patt is not None:
                match_a = mol_a.GetSubstructMatch(patt)
                match_b = mol_b.GetSubstructMatch(patt)
                if match_a and match_b and len(match_a) == len(match_b):
                    return {a: b for a, b in zip(match_a, match_b)}
    except Exception as exc:
        logger.debug("Strict FMCS resolution fallback: %s", exc)

    # If completeRingsOnly was too strict, try relaxed FMCS
    try:
        mcs_relaxed = rdFMCS.FindMCS(
            [mol_a, mol_b],
            completeRingsOnly=False,
            timeout=30,
        )
        if mcs_relaxed and mcs_relaxed.smartsString:
            patt = Chem.MolFromSmarts(mcs_relaxed.smartsString)
            if patt is not None:
                match_a = mol_a.GetSubstructMatch(patt)
                match_b = mol_b.GetSubstructMatch(patt)
                if match_a and match_b and len(match_a) == len(match_b):
                    return {a: b for a, b in zip(match_a, match_b)}
    except Exception as exc:
        logger.debug("Relaxed FMCS resolution fallback: %s", exc)

    return {}


def _extract_unmapped_subgraphs(
    mol: Chem.Mol, unmapped_indices: Set[int]
) -> List[SubgraphDeltaRecord]:
    """Partitions unmapped atoms into connected subgraph delta records."""
    if not unmapped_indices:
        return []

    # Build NetworkX graph of unmapped atoms
    gx = nx.Graph()
    for idx in unmapped_indices:
        gx.add_node(idx, symbol=mol.GetAtomWithIdx(idx).GetSymbol())

    for idx in unmapped_indices:
        atom = mol.GetAtomWithIdx(idx)
        for bond in atom.GetBonds():
            nbr = bond.GetOtherAtom(atom)
            nbr_idx = nbr.GetIdx()
            if nbr_idx in unmapped_indices and idx < nbr_idx:
                gx.add_edge(idx, nbr_idx, order=float(bond.GetBondTypeAsDouble()))

    subgraphs: List[SubgraphDeltaRecord] = []
    for component in nx.connected_components(gx):
        comp_indices = sorted(list(component))
        idx_map = {orig: i for i, orig in enumerate(comp_indices)}
        elements = [mol.GetAtomWithIdx(orig).GetSymbol() for orig in comp_indices]

        internal_bonds: List[Tuple[int, int, float]] = []
        for orig in comp_indices:
            atom = mol.GetAtomWithIdx(orig)
            for bond in atom.GetBonds():
                nbr = bond.GetOtherAtom(atom)
                nbr_orig = nbr.GetIdx()
                if nbr_orig in idx_map and orig < nbr_orig:
                    internal_bonds.append(
                        (idx_map[orig], idx_map[nbr_orig], float(bond.GetBondTypeAsDouble()))
                    )

        # Generate SMILES for the component
        try:
            rwmol = Chem.RWMol()
            for el in elements:
                rwmol.AddAtom(Chem.Atom(el))
            for u, v, bo in internal_bonds:
                if abs(bo - 2.0) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.DOUBLE)
                elif abs(bo - 3.0) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.TRIPLE)
                elif abs(bo - 1.5) < 1e-4:
                    rwmol.AddBond(u, v, Chem.BondType.AROMATIC)
                else:
                    rwmol.AddBond(u, v, Chem.BondType.SINGLE)
            frag_smiles = Chem.MolToSmiles(rwmol.GetMol())
        except Exception:
            frag_smiles = "".join(elements)

        subgraphs.append(
            SubgraphDeltaRecord(
                atom_indices=comp_indices,
                elements=elements,
                bonds=internal_bonds,
                smiles=frag_smiles,
            )
        )

    return subgraphs


def compute_topology_diff(mol_a_smiles: str, mol_b_smiles: str) -> TopologyDelta:
    """Computes the topological difference between two molecular graphs.

    Parameters
    ----------
    mol_a_smiles : str
        SMILES string of reference molecule A.
    mol_b_smiles : str
        SMILES string of target molecule B.

    Returns
    -------
    TopologyDelta
        Structured mutation delta including conserved mapping, element mutations,
        bond order modifications, and added/deleted subgraphs.

    Raises
    ------
    TopologyDiffError
        If either SMILES is invalid or diffing fails to resolve.
    """
    if not mol_a_smiles or not isinstance(mol_a_smiles, str):
        raise TopologyDiffError("Reference molecule SMILES must be a non-empty string.")
    if not mol_b_smiles or not isinstance(mol_b_smiles, str):
        raise TopologyDiffError("Target molecule SMILES must be a non-empty string.")

    mol_a = Chem.MolFromSmiles(mol_a_smiles)
    if mol_a is None:
        raise TopologyDiffError(f"Failed to parse reference molecule SMILES: '{mol_a_smiles}'")

    mol_b = Chem.MolFromSmiles(mol_b_smiles)
    if mol_b is None:
        raise TopologyDiffError(f"Failed to parse target molecule SMILES: '{mol_b_smiles}'")

    atom_mapping = _find_mccs_mapping(mol_a, mol_b)

    # Detect element mutations in mapped atoms
    element_mutations: List[Tuple[int, str, str]] = []
    for idx_a, idx_b in atom_mapping.items():
        elem_a = mol_a.GetAtomWithIdx(idx_a).GetSymbol()
        elem_b = mol_b.GetAtomWithIdx(idx_b).GetSymbol()
        if elem_a != elem_b:
            element_mutations.append((idx_a, elem_a, elem_b))

    # Detect bond order mutations between mapped atom pairs
    bond_order_mutations: List[Tuple[int, int, float, float]] = []
    inv_mapping = {b: a for a, b in atom_mapping.items()}
    for bond_a in mol_a.GetBonds():
        u_a = bond_a.GetBeginAtomIdx()
        v_a = bond_a.GetEndAtomIdx()
        if u_a in atom_mapping and v_a in atom_mapping:
            u_b = atom_mapping[u_a]
            v_b = atom_mapping[v_a]
            bond_b = mol_b.GetBondBetweenAtoms(u_b, v_b)
            bo_a = float(bond_a.GetBondTypeAsDouble())
            bo_b = float(bond_b.GetBondTypeAsDouble()) if bond_b is not None else 0.0
            if abs(bo_a - bo_b) > 1e-4:
                bond_order_mutations.append((min(u_a, v_a), max(u_a, v_a), bo_a, bo_b))

    # Identify unmapped subgraphs
    mapped_a_indices = set(atom_mapping.keys())
    unmapped_a_indices = {i for i in range(mol_a.GetNumAtoms()) if i not in mapped_a_indices}
    subgraph_deletions = _extract_unmapped_subgraphs(mol_a, unmapped_a_indices)

    mapped_b_indices = set(atom_mapping.values())
    unmapped_b_indices = {i for i in range(mol_b.GetNumAtoms()) if i not in mapped_b_indices}
    subgraph_additions = _extract_unmapped_subgraphs(mol_b, unmapped_b_indices)

    return TopologyDelta(
        atom_mapping=atom_mapping,
        element_mutations=element_mutations,
        bond_order_mutations=bond_order_mutations,
        subgraph_additions=subgraph_additions,
        subgraph_deletions=subgraph_deletions,
    )
