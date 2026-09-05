"""TOPOS Bimolecular Coordinate Intake & Frozen-Monomer vdW Pre-Screener (Method Matrix v4 §9A.5, §9B.1-§9B.2, Suggestion #121).

Eliminates raw, unguided SMILES generation for multi-fragment complexes.
Enforces explicit 3D Cartesian validation, steric clash detection (R_ij < 1.0 A),
unbound fragment detection, and frozen-monomer vdW rigid-body docking alignment.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, overload

import filelock
import numpy as np

try:
    from mendeleev import element
    HAS_MENDELEEV = True
except ImportError:
    HAS_MENDELEEV = False



class GeometryClashError(ValueError):
    """Raised when pairwise interatomic distance is below the steric clash limit."""


class UnphysicalDissociationError(ValueError):
    """Raised when fragments are separated beyond physical van der Waals contact."""


class UnguidedSmilesIntakeError(ValueError):
    """Raised when raw disconnected SMILES notation is supplied without 3D docking alignment."""


def get_vdw_radius(symbol: str) -> float:
    """Dynamically resolves van der Waals radius in Angstroms via mendeleev."""
    s = symbol.strip().capitalize()
    if HAS_MENDELEEV:
        try:
            elem = element(s)
            if elem.vdw_radius is not None:
                return float(elem.vdw_radius) / 100.0  # pm to A
        except Exception:
            pass
    # Pinned offline standards in Angstroms
    vdw_table = {
        "H": 1.20,
        "He": 1.40,
        "Li": 1.82,
        "Be": 1.53,
        "B": 1.92,
        "C": 1.70,
        "N": 1.55,
        "O": 1.52,
        "F": 1.47,
        "Ne": 1.54,
        "Na": 2.27,
        "Mg": 1.73,
        "Al": 1.84,
        "Si": 2.10,
        "P": 1.80,
        "S": 1.80,
        "Cl": 1.75,
        "Ar": 1.88,
    }
    return vdw_table.get(s, 1.70)


def get_covalent_radius(symbol: str) -> float:
    """Dynamically resolves Pyykkö covalent radius in Angstroms."""
    s = symbol.strip().capitalize()
    if HAS_MENDELEEV:
        try:
            elem = element(s)
            if elem.covalent_radius_pyykko is not None:
                return float(elem.covalent_radius_pyykko) / 100.0
        except Exception:
            pass
    cov_table = {
        "H": 0.32,
        "C": 0.75,
        "N": 0.71,
        "O": 0.63,
        "F": 0.64,
        "P": 1.11,
        "S": 1.03,
        "Cl": 0.99,
        "Br": 1.14,
        "I": 1.33,
    }
    return cov_table.get(s, 0.75)


@overload
def partition_fragments(
    symbols: Sequence[str],
    coords: np.ndarray,
    return_adjacency: Literal[False] = False,
) -> List[List[int]]:
    ...


@overload
def partition_fragments(
    symbols: Sequence[str],
    coords: np.ndarray,
    return_adjacency: Literal[True],
) -> Tuple[List[List[int]], List[List[bool]]]:
    ...


def partition_fragments(
    symbols: Sequence[str],
    coords: np.ndarray,
    return_adjacency: bool = False,
) -> List[List[int]] | Tuple[List[List[int]], List[List[bool]]]:
    """Partitions atoms into covalent molecular fragments using Pyykkö covalent radii."""
    symbols = [s.strip().capitalize() for s in symbols]
    coords = np.asarray(coords, dtype=np.float64)
    n = len(symbols)
    cov_r = [get_covalent_radius(s) for s in symbols]
    adj: List[List[bool]] = [[False] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            dist = float(np.linalg.norm(coords[i] - coords[j]))
            r_thresh = 1.25 * (cov_r[i] + cov_r[j])
            if dist <= r_thresh:
                adj[i][j] = True
                adj[j][i] = True

    visited = set()
    fragments: List[List[int]] = []
    for i in range(n):
        if i not in visited:
            comp: List[int] = []
            queue = [i]
            visited.add(i)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for neighbor in range(n):
                    if adj[curr][neighbor] and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            fragments.append(comp)
    if return_adjacency:
        return fragments, adj
    return fragments


class BimolecularPreScreener:
    """Validates 3D coordinates of bimolecular/non-covalent systems and enforces Frozen-Monomer alignment."""

    STERIC_CLASH_THRESHOLD: float = 1.00  # Angstroms [M]

    @classmethod
    def validate_cartesian_coordinates(
        cls,
        symbols: Sequence[str],
        coordinates: np.ndarray | Sequence[Sequence[float]],
        allow_dissociation: bool = False,
        fragments: Optional[Sequence[Sequence[int]]] = None,
    ) -> Dict[str, Any]:
        """Validates pairwise distance matrix for steric clashes and unphysical dissociation."""
        symbols = [s.strip().capitalize() for s in symbols]
        coords = np.asarray(coordinates, dtype=np.float64)
        n_atoms = len(symbols)

        if n_atoms < 2:
            return {
                "status": "VALID",
                "fragment_count": n_atoms,
                "fragments": [[0]] if n_atoms == 1 else [],
                "min_distance": 0.0,
                "min_distance_angstrom": 0.0,
            }

        diffs = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        dist_matrix = np.linalg.norm(diffs, axis=-1)

        # 1. Fragment partitioning and covalent adjacency via Pyykkö covalent radii
        frag_list: List[List[int]]
        if fragments is not None:
            frag_list = [list(f) for f in fragments]
            _, adj = partition_fragments(symbols, coords, return_adjacency=True)
        else:
            frag_list, adj = partition_fragments(symbols, coords, return_adjacency=True)

        cov_r = [get_covalent_radius(s) for s in symbols]

        # Map atom index to fragment index
        atom_to_frag: Dict[int, int] = {}
        for f_idx, frag in enumerate(frag_list):
            for a_idx in frag:
                atom_to_frag[a_idx] = f_idx

        # 2. Check for steric clashes
        # - Inter-fragment pairs: Every inter-fragment pair must satisfy R_ij >= 1.00 A.
        # - Heavy-atom pairs: Heavy-atom bonds (C-C, C-O, etc.) are always >= 1.15 A;
        #   any heavy-atom pair with R_ij < 1.00 A is an unphysical steric clash.
        # - Covalently bonded pairs involving H: clash if d < 0.60 * (r_cov,i + r_cov,j).
        # - Non-bonded pairs involving H: clash if d < STERIC_CLASH_THRESHOLD (1.00 A).
        min_dist = float("inf")
        clash_info = None

        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                d = float(dist_matrix[i, j])
                if d < min_dist:
                    min_dist = d

                is_inter_fragment = (
                    len(frag_list) > 1
                    and i in atom_to_frag
                    and j in atom_to_frag
                    and atom_to_frag[i] != atom_to_frag[j]
                )
                has_hydrogen = (symbols[i] == "H" or symbols[j] == "H")

                if is_inter_fragment:
                    clash_thresh = cls.STERIC_CLASH_THRESHOLD
                elif not has_hydrogen:
                    clash_thresh = cls.STERIC_CLASH_THRESHOLD
                else:
                    if adj[i][j]:
                        clash_thresh = 0.60 * (cov_r[i] + cov_r[j])
                    else:
                        clash_thresh = cls.STERIC_CLASH_THRESHOLD

                if d < clash_thresh:
                    clash_info = (i, j, symbols[i], symbols[j], d, clash_thresh)
                    break
            if clash_info:
                break

        if clash_info:
            i, j, s_i, s_j, d, clash_thresh = clash_info
            raise GeometryClashError(
                f"Steric clash detected between atom {i} ({s_i}) and atom {j} ({s_j}): "
                f"R_ij = {d:.4f} A < threshold {clash_thresh:.2f} A [M]."
            )

        # 3. Inter-fragment separation and unphysical dissociation check
        inter_frag_min = float("inf")
        closest_pair: Optional[Tuple[str, str]] = None
        if len(frag_list) > 1:
            for f1_idx, frag1 in enumerate(frag_list):
                for frag2 in frag_list[f1_idx + 1 :]:
                    for idx1 in frag1:
                        for idx2 in frag2:
                            d = float(dist_matrix[idx1, idx2])
                            if d < inter_frag_min:
                                inter_frag_min = d
                                closest_pair = (symbols[idx1], symbols[idx2])

            if not allow_dissociation and closest_pair is not None:
                vdw_sum = get_vdw_radius(closest_pair[0]) + get_vdw_radius(closest_pair[1])
                max_allowed_separation = vdw_sum + 3.00  # Angstroms [M]
                if inter_frag_min > max_allowed_separation:
                    raise UnphysicalDissociationError(
                        f"Unphysical dissociation detected between fragments: minimum separation "
                        f"R_inter = {inter_frag_min:.4f} A > R_vdw + 3.0 A ({max_allowed_separation:.4f} A)."
                    )

        rep_dist = inter_frag_min if len(frag_list) > 1 else min_dist

        return {
            "status": "VALID",
            "fragment_count": len(frag_list),
            "fragments": frag_list,
            "min_distance_angstrom": rep_dist,
            "min_distance": rep_dist,
        }

    @classmethod
    def prescreen_smiles_or_align(
        cls,
        smiles: str,
        allow_unguided: bool = False,
    ) -> Tuple[List[str], np.ndarray]:
        """Rejects unguided 1D multi-fragment SMILES or executes Frozen-Monomer pre-alignment."""
        smiles = smiles.strip()
        if "." in smiles and not allow_unguided:
            # Multi-fragment disconnected notation without 3D geometry
            fragments_smiles = smiles.split(".")
            if len(fragments_smiles) == 2:
                # Authentic Frozen-Monomer alignment for standard bimolecular dimer
                return cls.align_frozen_monomer_dimer(fragments_smiles[0], fragments_smiles[1])
            raise UnguidedSmilesIntakeError(
                f"Disconnected multi-fragment SMILES '{smiles}' lacking explicit 3D spatial orientation "
                f"cannot be passed directly to CREST or GOAT without pre-docking alignment (Suggestion #121)."
            )

        # Single molecule or authorized unguided
        # Dynamic 3D generation via RDKit
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                raise ValueError(f"Invalid SMILES string: '{smiles}'")
            mol = Chem.AddHs(mol)
            embed_status = AllChem.EmbedMolecule(mol, randomSeed=42)
            if embed_status != 0:
                raise RuntimeError(f"RDKit conformer embedding failed for SMILES '{smiles}'")
            AllChem.UFFOptimizeMolecule(mol)
            conf = mol.GetConformer()
            symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
            coords = np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())], dtype=np.float64)
            return symbols, coords
        except Exception as exc:
            raise UnguidedSmilesIntakeError(
                f"Explicit 3D Cartesian coordinates are required for system '{smiles}': {exc}."
            ) from exc

    @classmethod
    def _get_monomer_geometry(cls, smiles: str) -> Tuple[List[str], np.ndarray]:
        """Retrieves pinned authentic coordinates or dynamically computes 3D conformer via RDKit."""
        monomer_library = {
            "O": (["O", "H", "H"], np.array([[0.0, 0.0, 0.0], [0.757, 0.586, 0.0], [-0.757, 0.586, 0.0]])),
            "O=C=O": (["C", "O", "O"], np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.162], [0.0, 0.0, -1.162]])),
            "N": (["N", "H", "H", "H"], np.array([[0.0, 0.0, 0.114], [0.0, 0.940, -0.267], [0.814, -0.470, -0.267], [-0.814, -0.470, -0.267]])),
        }
        if smiles in monomer_library:
            syms, coords = monomer_library[smiles]
            return list(syms), np.copy(coords)

        # Dynamic 3D generation via RDKit
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                raise ValueError(f"Invalid monomer SMILES string: '{smiles}'")
            mol = Chem.AddHs(mol)
            embed_status = AllChem.EmbedMolecule(mol, randomSeed=42)
            if embed_status != 0:
                raise RuntimeError(f"RDKit conformer embedding failed for SMILES '{smiles}'")
            AllChem.UFFOptimizeMolecule(mol)
            conf = mol.GetConformer()
            symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
            coords = np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())], dtype=np.float64)
            return symbols, coords
        except Exception as exc:
            raise UnguidedSmilesIntakeError(
                f"Explicit 3D Cartesian coordinates are required for uncataloged monomer '{smiles}': {exc}."
            ) from exc

    @classmethod
    def align_frozen_monomer_dimer(
        cls,
        smiles_monomer1: str,
        smiles_monomer2: str,
    ) -> Tuple[List[str], np.ndarray]:
        """Aligns two frozen monomers along their center-of-mass separation vector at sum-of-vdW contact."""
        sym1, c1 = cls._get_monomer_geometry(smiles_monomer1)
        sym2, c2 = cls._get_monomer_geometry(smiles_monomer2)

        c1 = np.copy(c1)
        c2 = np.copy(c2)

        # Center both monomers at origin
        com1 = np.mean(c1, axis=0)
        com2 = np.mean(c2, axis=0)
        c1 -= com1
        c2 -= com2

        # 4. PHYSICAL FROZEN-MONOMER POSITIONING:
        # Compute extent of Monomer 1 along +Z (max_z1) and Monomer 2 along -Z (min_z2),
        # and the required sum-of-vdW contact distance between closest contacting atoms.
        max_z1_idx = int(np.argmax(c1[:, 2]))
        min_z2_idx = int(np.argmin(c2[:, 2]))

        target_vdw = get_vdw_radius(sym1[max_z1_idx]) + get_vdw_radius(sym2[min_z2_idx])

        # Shift Monomer 2 along Z such that the minimum inter-monomer atomic distance
        # min_{i in M1, j in M2} R_ij equals target_vdw (within +/- 0.3 A per Method Matrix §9A.5).
        # We determine the exact Z shift using 1D binary search.
        z_shift_low = float(c1[max_z1_idx, 2] - c2[min_z2_idx, 2])
        z_shift_high = z_shift_low + 2.0 * target_vdw + 5.0

        for _ in range(40):
            mid = (z_shift_low + z_shift_high) / 2.0
            c2_z = c2[:, 2] + mid
            dx = c1[:, 0:1] - c2[:, 0:1].T
            dy = c1[:, 1:2] - c2[:, 1:2].T
            dz = c1[:, 2:3] - c2_z[np.newaxis, :]
            dists = np.sqrt(dx * dx + dy * dy + dz * dz)
            min_d = float(np.min(dists))
            if min_d < target_vdw:
                z_shift_low = mid
            else:
                z_shift_high = mid

        best_shift = (z_shift_low + z_shift_high) / 2.0
        c2[:, 2] += best_shift

        combined_symbols = list(sym1) + list(sym2)
        combined_coords = np.vstack([c1, c2])

        frag1_indices = list(range(len(sym1)))
        frag2_indices = list(range(len(sym1), len(sym1) + len(sym2)))
        monomer_fragments = [frag1_indices, frag2_indices]

        # Validate resulting complex
        cls.validate_cartesian_coordinates(combined_symbols, combined_coords, fragments=monomer_fragments)
        return combined_symbols, combined_coords

    @classmethod
    def dispatch_search_subprocess(
        cls,
        symbols: Sequence[str],
        coords: np.ndarray,
        protocol: str = "GOAT",
        scratch_dir: Optional[Path | str] = None,
    ) -> Path:
        """Dispatches validated complex structures into an ephemeral scratch sandbox."""
        cls.validate_cartesian_coordinates(symbols, coords)

        scr = Path(scratch_dir) if scratch_dir else Path(os.environ.get("COCH_SCRATCH", "scratch")) / f"topos_job_{uuid.uuid4().hex[:8]}"
        scr.mkdir(parents=True, exist_ok=True)
        lock_file = scr / "job.lock"

        with filelock.FileLock(lock_file, timeout=10.0):
            # Write XYZ input file
            xyz_path = scr / "input_complex.xyz"
            n_atoms = len(symbols)
            lines = [str(n_atoms), f"TOPOS Pre-Screened Complex (Protocol: {protocol})"]
            for s, (x, y, z) in zip(symbols, coords, strict=False):
                lines.append(f"{s:<4} {x:14.8f} {y:14.8f} {z:14.8f}")
            xyz_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return xyz_path
