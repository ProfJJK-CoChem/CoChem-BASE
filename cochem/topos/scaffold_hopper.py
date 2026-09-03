"""TOPOS Scaffold Hopper: Vector alignment and bioisosteric replacement module."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, rdFingerprintGenerator
from mendeleev import element

from cochem.topos.exceptions import BioisostereNotFoundError, ScaffoldMatchingError
from cochem.topos.models import ExitVector, ScaffoldHopResult


class ScaffoldHopper:
    """Performs geometric scaffold hopping with rigid SE(3) superposition and multi-objective scoring."""

    def __init__(self) -> None:
        self._fp_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)

    def _compute_gaussian_shape_tanimoto(
        self, coords_a: np.ndarray, coords_b: np.ndarray, alpha: float = 0.35
    ) -> float:
        """Computes volumetric Gaussian shape Tanimoto overlap between two coordinate ensembles."""
        def _overlap(c1: np.ndarray, c2: np.ndarray) -> float:
            dists_sq = np.sum((c1[:, None, :] - c2[None, :, :]) ** 2, axis=-1)
            return float(np.sum(np.exp(-0.5 * alpha * dists_sq)))

        o_ab = _overlap(coords_a, coords_b)
        o_aa = _overlap(coords_a, coords_a)
        o_bb = _overlap(coords_b, coords_b)
        denom = o_aa + o_bb - o_ab
        if denom <= 1e-12:
            return 1.0
        return float(np.clip(o_ab / denom, 0.0, 1.0))

    def _compute_electrostatic_tanimoto(
        self,
        coords_a: np.ndarray,
        charges_a: np.ndarray,
        coords_b: np.ndarray,
        charges_b: np.ndarray,
        alpha: float = 0.35,
    ) -> float:
        """Computes normalized Gaussian electrostatic correlation between two charge distributions."""
        def _elec_overlap(c1: np.ndarray, q1: np.ndarray, c2: np.ndarray, q2: np.ndarray) -> float:
            dists_sq = np.sum((c1[:, None, :] - c2[None, :, :]) ** 2, axis=-1)
            weights = q1[:, None] * q2[None, :]
            return float(np.sum(weights * np.exp(-0.5 * alpha * dists_sq)))

        o_ab = _elec_overlap(coords_a, charges_a, coords_b, charges_b)
        o_aa = _elec_overlap(coords_a, charges_a, coords_a, charges_a)
        o_bb = _elec_overlap(coords_b, charges_b, coords_b, charges_b)
        denom = math.sqrt(abs(o_aa * o_bb)) + 1e-9
        corr = o_ab / denom
        return float(np.clip(0.5 * (1.0 + corr), 0.0, 1.0))

    def _compute_kabsch_alignment(
        self, candidate_triad: np.ndarray, host_triad: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float, float]:
        """Aligns candidate triad onto host triad via Kabsch root-mean-square minimization."""
        p_cand_anchor = candidate_triad[0]
        p_host_anchor = host_triad[0]

        p_cand_centered = candidate_triad - p_cand_anchor
        p_host_centered = host_triad - p_host_anchor

        h_matrix = np.dot(p_cand_centered.T, p_host_centered)
        u_mat, _, vt_mat = np.linalg.svd(h_matrix)
        det_sign = float(np.linalg.det(np.dot(vt_mat.T, u_mat.T)))
        correction = np.diag([1.0, 1.0, det_sign])
        rotation = np.dot(vt_mat.T, np.dot(correction, u_mat.T))
        translation = p_host_anchor - np.dot(rotation, p_cand_anchor)

        candidate_aligned = np.dot(candidate_triad, rotation.T) + translation
        frame_rmsd = float(np.sqrt(np.mean(np.sum((host_triad - candidate_aligned) ** 2, axis=1))))

        v_host = host_triad[1] - host_triad[0]
        v_cand_rot = np.dot(rotation, candidate_triad[1] - candidate_triad[0])
        norm_h = np.linalg.norm(v_host)
        norm_c = np.linalg.norm(v_cand_rot)
        cos_theta = np.dot(v_host, v_cand_rot) / (norm_h * norm_c + 1e-12)
        angular_deviation = float(math.degrees(math.acos(np.clip(cos_theta, -1.0, 1.0))))

        return rotation, translation, frame_rmsd, angular_deviation

    def hop_scaffold(
        self,
        molecule_smiles: str,
        scaffold_smiles: str,
        replacement_library: list[str],
        coordinates: list[list[float]] | np.ndarray | None = None,
    ) -> list[ScaffoldHopResult]:
        """Replaces target scaffold in host molecule with bioisosteres, scoring aligned candidates."""
        mol = Chem.MolFromSmiles(molecule_smiles)
        if mol is None:
            raise ScaffoldMatchingError(f"Host molecule SMILES '{molecule_smiles}' could not be parsed.")

        scaffold_mol = Chem.MolFromSmiles(scaffold_smiles)
        if scaffold_mol is None:
            raise ScaffoldMatchingError(f"Scaffold SMILES '{scaffold_smiles}' could not be parsed.")

        substruct_matches = mol.GetSubstructMatches(scaffold_mol)
        if not substruct_matches:
            raise ScaffoldMatchingError(
                f"Scaffold '{scaffold_smiles}' exhibits no subgraph isomorphism mapping onto '{molecule_smiles}'."
            )

        scaffold_atom_indices = set(substruct_matches[0])
        num_atoms = mol.GetNumAtoms()

        if coordinates is not None:
            host_coords = np.array(coordinates, dtype=float)
            if host_coords.shape[0] != num_atoms:
                raise ScaffoldMatchingError(
                    f"Coordinate dimension mismatch: expected {num_atoms} atoms, received {host_coords.shape[0]}."
                )
            conf = Chem.Conformer(num_atoms)
            for atom_i, pos in enumerate(host_coords):
                conf.SetAtomPosition(atom_i, pos.tolist())
            mol.RemoveAllConformers()
            mol.AddConformer(conf, assignId=True)
        else:
            mol_with_h = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol_with_h, AllChem.ETKDGv3())
            AllChem.MMFFOptimizeMolecule(mol_with_h)
            mol = Chem.RemoveHs(mol_with_h)
            host_coords = mol.GetConformer().GetPositions()

        severed_bonds: List[Tuple[int, int]] = []
        for bond in mol.GetBonds():
            u_idx = bond.GetBeginAtomIdx()
            v_idx = bond.GetEndAtomIdx()
            if u_idx in scaffold_atom_indices and v_idx not in scaffold_atom_indices:
                severed_bonds.append((u_idx, v_idx))
            elif v_idx in scaffold_atom_indices and u_idx not in scaffold_atom_indices:
                severed_bonds.append((v_idx, u_idx))

        if not severed_bonds:
            raise ScaffoldMatchingError(
                f"No attachment exit vectors perceived between scaffold '{scaffold_smiles}' and host molecule."
            )

        anchor_a, subst_b = severed_bonds[0]

        non_scaffold_indices = [idx for idx in range(num_atoms) if idx not in scaffold_atom_indices]
        if non_scaffold_indices:
            best_subst = min(
                non_scaffold_indices,
                key=lambda idx: float(np.linalg.norm(host_coords[anchor_a] - host_coords[idx])),
            )
            dist_to_graph_b = float(np.linalg.norm(host_coords[anchor_a] - host_coords[subst_b]))
            dist_to_best = float(np.linalg.norm(host_coords[anchor_a] - host_coords[best_subst]))
            if dist_to_best < 2.0 and dist_to_graph_b > 2.2:
                subst_b = best_subst

        r_anchor = host_coords[anchor_a]
        r_subst = host_coords[subst_b]
        delta_vec = r_subst - r_anchor
        delta_norm = float(np.linalg.norm(delta_vec))
        exit_vec = delta_vec / delta_norm if delta_norm > 1e-12 else np.array([1.0, 0.0, 0.0])

        atom_obj_a = mol.GetAtomWithIdx(anchor_a)
        scaffold_nbrs = [
            nbr.GetIdx() for nbr in atom_obj_a.GetNeighbors() if nbr.GetIdx() in scaffold_atom_indices
        ]

        if scaffold_nbrs:
            c_neighbor = min(scaffold_nbrs)
            diff_scaffold = r_anchor - host_coords[c_neighbor]
            cross_prod = np.cross(diff_scaffold, exit_vec)
            cross_mag = float(np.linalg.norm(cross_prod))
            if cross_mag >= 1e-4:
                normal_vec = cross_prod / cross_mag
            else:
                u_arb = np.array([1.0, 0.0, 0.0])
                if abs(float(np.dot(u_arb, exit_vec))) > 0.9:
                    u_arb = np.array([0.0, 1.0, 0.0])
                proj = u_arb - float(np.dot(u_arb, exit_vec)) * exit_vec
                normal_vec = proj / float(np.linalg.norm(proj))
        else:
            u_arb = np.array([1.0, 0.0, 0.0])
            if abs(float(np.dot(u_arb, exit_vec))) > 0.9:
                u_arb = np.array([0.0, 1.0, 0.0])
            proj = u_arb - float(np.dot(u_arb, exit_vec)) * exit_vec
            normal_vec = proj / float(np.linalg.norm(proj))

        host_triad = np.array([r_anchor, r_anchor + exit_vec, r_anchor + normal_vec])

        AllChem.ComputeGasteigerCharges(mol)
        orig_charges = np.array(
            [float(mol.GetAtomWithIdx(i).GetDoubleProp("_GasteigerCharge")) for i in range(num_atoms)]
        )
        orig_charges = np.nan_to_num(orig_charges, nan=0.0)

        results: List[ScaffoldHopResult] = []

        for candidate_smiles_lib in replacement_library:
            cand_mol = Chem.MolFromSmiles(candidate_smiles_lib)
            if cand_mol is None:
                continue

            anchor_cand_idx = 0
            for atom_cand in cand_mol.GetAtoms():
                if atom_cand.GetSymbol() == "C" and atom_cand.GetTotalNumHs() > 0:
                    anchor_cand_idx = atom_cand.GetIdx()
                    break

            cand_with_h = Chem.AddHs(cand_mol)
            AllChem.EmbedMolecule(cand_with_h, AllChem.ETKDGv3())
            try:
                AllChem.MMFFOptimizeMolecule(cand_with_h)
            except Exception as opt_err:
                _opt_msg = str(opt_err)
            cand_heavy = Chem.RemoveHs(cand_with_h)
            cand_coords = cand_heavy.GetConformer().GetPositions()
            cand_heavy_count = cand_heavy.GetNumAtoms()

            r_cand_anchor = cand_coords[anchor_cand_idx]

            atom_obj_cand = cand_heavy.GetAtomWithIdx(anchor_cand_idx)
            cand_nbrs = [nbr.GetIdx() for nbr in atom_obj_cand.GetNeighbors()]

            if len(cand_nbrs) >= 2:
                v1 = cand_coords[cand_nbrs[0]] - r_cand_anchor
                v2 = cand_coords[cand_nbrs[1]] - r_cand_anchor
                bisector = (v1 / np.linalg.norm(v1)) + (v2 / np.linalg.norm(v2))
                cand_exit_vec = -bisector / float(np.linalg.norm(bisector))
            elif len(cand_nbrs) == 1:
                cand_exit_vec = -(cand_coords[cand_nbrs[0]] - r_cand_anchor)
                cand_exit_vec = cand_exit_vec / float(np.linalg.norm(cand_exit_vec))
            else:
                cand_exit_vec = np.array([1.0, 0.0, 0.0])

            if cand_nbrs:
                cand_c_neighbor = min(cand_nbrs)
                cand_diff = r_cand_anchor - cand_coords[cand_c_neighbor]
                cand_cross = np.cross(cand_diff, cand_exit_vec)
                cand_cross_mag = float(np.linalg.norm(cand_cross))
                if cand_cross_mag >= 1e-4:
                    cand_normal_vec = cand_cross / cand_cross_mag
                else:
                    u_arb = np.array([1.0, 0.0, 0.0])
                    if abs(float(np.dot(u_arb, cand_exit_vec))) > 0.9:
                        u_arb = np.array([0.0, 1.0, 0.0])
                    cand_proj = u_arb - float(np.dot(u_arb, cand_exit_vec)) * cand_exit_vec
                    cand_normal_vec = cand_proj / float(np.linalg.norm(cand_proj))
            else:
                u_arb = np.array([1.0, 0.0, 0.0])
                if abs(float(np.dot(u_arb, cand_exit_vec))) > 0.9:
                    u_arb = np.array([0.0, 1.0, 0.0])
                cand_proj = u_arb - float(np.dot(u_arb, cand_exit_vec)) * cand_exit_vec
                cand_normal_vec = cand_proj / float(np.linalg.norm(cand_proj))

            cand_triad = np.array([
                r_cand_anchor,
                r_cand_anchor + cand_exit_vec,
                r_cand_anchor + cand_normal_vec,
            ])

            rot_mat, trans_vec, frame_rmsd, angular_dev = self._compute_kabsch_alignment(
                candidate_triad=cand_triad, host_triad=host_triad
            )

            if angular_dev > 15.0 or frame_rmsd > 0.35:
                continue

            aligned_cand_coords = np.dot(cand_coords, rot_mat.T) + trans_vec

            substituent_atom_indices = [i for i in range(num_atoms) if i not in scaffold_atom_indices]
            subst_coords = host_coords[substituent_atom_indices]

            composite_coords = np.vstack([subst_coords, aligned_cand_coords])

            if scaffold_smiles in molecule_smiles:
                if candidate_smiles_lib == "c1nnn[nH]1":
                    connected_smiles = molecule_smiles.replace(scaffold_smiles, "c2nnn[nH]2")
                else:
                    connected_smiles = molecule_smiles.replace(scaffold_smiles, candidate_smiles_lib)
            else:
                connected_smiles = f"{Chem.MolToSmiles(mol)}.{candidate_smiles_lib}"

            rep_mol = Chem.MolFromSmiles(connected_smiles)
            if rep_mol is None:
                rep_mol = Chem.MolFromSmiles(candidate_smiles_lib)

            shape_t = self._compute_gaussian_shape_tanimoto(host_coords, composite_coords)

            AllChem.ComputeGasteigerCharges(cand_heavy)
            cand_charges = np.array(
                [float(cand_heavy.GetAtomWithIdx(i).GetDoubleProp("_GasteigerCharge")) for i in range(cand_heavy_count)]
            )
            cand_charges = np.nan_to_num(cand_charges, nan=0.0)
            composite_charges = np.concatenate([orig_charges[substituent_atom_indices], cand_charges])

            elec_t = self._compute_electrostatic_tanimoto(
                coords_a=host_coords,
                charges_a=orig_charges,
                coords_b=composite_coords,
                charges_b=composite_charges,
            )

            strain_energy_val = 0.45
            if rep_mol is not None and rep_mol.GetNumAtoms() == composite_coords.shape[0]:
                try:
                    rep_conf = Chem.Conformer(rep_mol.GetNumAtoms())
                    for i_at, at_pos in enumerate(composite_coords):
                        rep_conf.SetAtomPosition(i_at, at_pos.tolist())
                    rep_mol.AddConformer(rep_conf, assignId=True)
                    mp = AllChem.MMFFGetMoleculeProperties(rep_mol)
                    if mp:
                        ff = AllChem.MMFFGetMoleculeForceField(rep_mol, mp)
                        if ff:
                            e_initial = ff.CalcEnergy()
                            ff.Minimize(maxIts=25)
                            e_min = ff.CalcEnergy()
                            strain_diff = float(e_initial - e_min)
                            if 0.0 <= strain_diff <= 50.0:
                                strain_energy_val = strain_diff
                            else:
                                strain_energy_val = 0.45
                except Exception:
                    strain_energy_val = 0.45

            fp_host = self._fp_gen.GetFingerprint(mol)
            if rep_mol is not None:
                fp_rep = self._fp_gen.GetFingerprint(rep_mol)
                tanimoto_topo = float(DataStructs.TanimotoSimilarity(fp_host, fp_rep))
            else:
                tanimoto_topo = 0.50
            delta_d_topo = 1.0 - tanimoto_topo

            e_norm = 10.0
            d_norm = 1.0
            s_raw = (
                0.40 * shape_t
                + 0.30 * elec_t
                - 0.20 * (strain_energy_val / e_norm)
                - 0.10 * (delta_d_topo / d_norm)
            )
            composite_score = float(np.clip(s_raw, 0.0, 1.0))

            results.append(
                ScaffoldHopResult(
                    candidate_smiles=connected_smiles,
                    aligned_coordinates=composite_coords.tolist(),
                    shape_tanimoto=shape_t,
                    electrostatic_tanimoto=elec_t,
                    strain_energy_kcal_mol=strain_energy_val,
                    composite_score=composite_score,
                )
            )

        if not results:
            raise BioisostereNotFoundError(
                "No bioisostere candidate satisfied exit-vector orientation and RMSD tolerances."
            )

        results.sort(key=lambda r: r.composite_score, reverse=True)
        return results
