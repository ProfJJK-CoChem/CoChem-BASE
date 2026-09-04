"""Extended-connectivity circular fingerprint (ECFP4 / Morgan) generator engine.

Implements Rogers-Hahn circular invariants, dynamic Mendeleev isotopic mass offsets,
MurmurHash3 integer hashing via mmh3, and modulo bitvector folding with similarity metrics.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Sequence, Set, Tuple, Union
try:
    import mmh3
    def _murmurhash3_32(key: bytes, seed: int = 0) -> int:
        return mmh3.hash(key, seed=seed) & 0xFFFFFFFF
except ImportError:
    def _murmurhash3_32(key: bytes, seed: int = 0) -> int:
        def _rotl32(x: int, r: int) -> int:
            return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF

        c1 = 0xcc9e2d51
        c2 = 0x1b873593
        h = seed & 0xFFFFFFFF
        length = len(key)
        n_blocks = length // 4

        for i in range(n_blocks):
            k = struct.unpack_from("<I", key, i * 4)[0]
            k = (k * c1) & 0xFFFFFFFF
            k = _rotl32(k, 15)
            k = (k * c2) & 0xFFFFFFFF

            h ^= k
            h = _rotl32(h, 13)
            h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF

        tail = key[n_blocks * 4:]
        k = 0
        tail_len = len(tail)
        if tail_len >= 3:
            k ^= tail[2] << 16
        if tail_len >= 2:
            k ^= tail[1] << 8
        if tail_len >= 1:
            k ^= tail[0]
            k = (k * c1) & 0xFFFFFFFF
            k = _rotl32(k, 15)
            k = (k * c2) & 0xFFFFFFFF
            h ^= k

        h ^= length
        h ^= (h >> 16)
        h = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= (h >> 13)
        h = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= (h >> 16)

        return h

from mendeleev import element
from rdkit import Chem

from cochem.topos.exceptions import FingerprintGenerationError
from cochem.topos.models import ECFP4FingerprintPayload


def generate_ecfp4_fingerprint(
    smiles: str,
    radius: int = 2,
    n_bits: int = 2048,
) -> ECFP4FingerprintPayload:
    """Generates an extended-connectivity circular fingerprint (ECFP4 / Morgan) from a SMILES string.

    Parameters
    ----------
    smiles : str
        Canonical or arbitrary SMILES string of the input molecule.
    radius : int, default=2
        Circular neighborhood expansion radius (radius=2 corresponds to diameter=4, ECFP4).
    n_bits : int, default=2048
        Fixed bitvector length for modulo folding.

    Returns
    -------
    ECFP4FingerprintPayload
        Payload containing 1024-bit and 2048-bit vectors, active bit indices, and count vector.

    Raises
    ------
    FingerprintGenerationError
        If the SMILES cannot be parsed or fingerprint generation fails.
    """
    if not smiles or not isinstance(smiles, str):
        raise FingerprintGenerationError("Input SMILES must be a non-empty string.")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise FingerprintGenerationError(f"Failed to parse SMILES string: '{smiles}'")

    n_atoms = mol.GetNumAtoms()
    if n_atoms == 0:
        return ECFP4FingerprintPayload(
            bit_vector_1024=[0] * 1024,
            bit_vector_2048=[0] * n_bits,
            on_bits_2048=[],
            count_vector={},
            features_de_duplicated=0,
        )

    all_raw_features: List[int] = []

    # 1. Initial Atom Invariant Packing (Radius 0)
    current_hashes: List[int] = [0] * n_atoms
    for i, atom in enumerate(mol.GetAtoms()):
        atomic_num = atom.GetAtomicNum()
        degree = atom.GetDegree()
        total_valence = atom.GetTotalValence()
        formal_charge = atom.GetFormalCharge()
        in_ring_flag = 1 if atom.IsInRing() else 0

        # Dynamic Mendeleev discrete isotopic state offset
        try:
            elem_obj = element(atomic_num)
            nominal_mass = int(elem_obj.mass_number)
        except Exception as exc:
            raise FingerprintGenerationError(
                f"Dynamic Mendeleev lookup failed for atomic number {atomic_num}: {exc}"
            ) from exc

        explicit_isotope = atom.GetIsotope()
        delta_mass = (explicit_isotope - nominal_mass) if explicit_isotope != 0 else 0

        # Pack initial invariant into 24-byte struct (<iiiiii)
        raw_packed = struct.pack(
            "<iiiiii",
            atomic_num,
            degree,
            total_valence,
            formal_charge,
            in_ring_flag,
            delta_mass,
        )
        inv_0 = _murmurhash3_32(raw_packed, seed=0)
        current_hashes[i] = inv_0
        all_raw_features.append(inv_0)

    # 2. Neighborhood Expansion for Radius 1 .. R
    for r in range(1, radius + 1):
        next_hashes: List[int] = [0] * n_atoms
        for i, atom in enumerate(mol.GetAtoms()):
            neighbor_tuples: List[Tuple[float, int]] = []
            for bond in atom.GetBonds():
                nbr = bond.GetOtherAtom(atom)
                bo = float(bond.GetBondTypeAsDouble())
                nbr_h = current_hashes[nbr.GetIdx()]
                neighbor_tuples.append((bo, nbr_h))

            # Canonical sorting of neighbor tuples to ensure invariance to atom indexing
            neighbor_tuples.sort(key=lambda t: (t[0], t[1]))

            head_bytes = struct.pack("<II", r, current_hashes[i])
            tail_bytes = b"".join(
                struct.pack("<fI", bo, nbr_h) for bo, nbr_h in neighbor_tuples
            )

            h_r = _murmurhash3_32(head_bytes + tail_bytes, seed=0)
            next_hashes[i] = h_r
            all_raw_features.append(h_r)

        current_hashes = next_hashes

    # 3. Rogers-Hahn Feature De-duplication across radii
    unique_features: Set[int] = set(all_raw_features)
    dedup_count = len(all_raw_features) - len(unique_features)

    # 4. Modulo Bit Folding
    bv_1024 = [0] * 1024
    bv_2048 = [0] * n_bits
    count_map: Dict[int, int] = {}

    for feat in unique_features:
        bit_1024 = feat % 1024
        bit_2048 = feat % n_bits
        bv_1024[bit_1024] = 1
        bv_2048[bit_2048] = 1
        count_map[bit_2048] = count_map.get(bit_2048, 0) + 1

    on_bits = sorted(count_map.keys())

    return ECFP4FingerprintPayload(
        bit_vector_1024=bv_1024,
        bit_vector_2048=bv_2048,
        on_bits_2048=on_bits,
        count_vector=count_map,
        features_de_duplicated=dedup_count,
    )


def compute_tanimoto_similarity(
    fp1: Union[ECFP4FingerprintPayload, Sequence[int]],
    fp2: Union[ECFP4FingerprintPayload, Sequence[int]],
) -> float:
    """Computes vectorized Jaccard-Tanimoto similarity between two fingerprints."""
    if isinstance(fp1, ECFP4FingerprintPayload):
        bits1 = set(fp1.on_bits_2048)
    else:
        bits1 = {idx for idx, val in enumerate(fp1) if val > 0}

    if isinstance(fp2, ECFP4FingerprintPayload):
        bits2 = set(fp2.on_bits_2048)
    else:
        bits2 = {idx for idx, val in enumerate(fp2) if val > 0}

    if not bits1 and not bits2:
        return 1.0
    union_size = len(bits1 | bits2)
    if union_size == 0:
        return 0.0
    return float(len(bits1 & bits2) / union_size)


def compute_dice_similarity(
    fp1: Union[ECFP4FingerprintPayload, Sequence[int]],
    fp2: Union[ECFP4FingerprintPayload, Sequence[int]],
) -> float:
    """Computes vectorized Sørensen-Dice similarity coefficient between two fingerprints."""
    if isinstance(fp1, ECFP4FingerprintPayload):
        bits1 = set(fp1.on_bits_2048)
    else:
        bits1 = {idx for idx, val in enumerate(fp1) if val > 0}

    if isinstance(fp2, ECFP4FingerprintPayload):
        bits2 = set(fp2.on_bits_2048)
    else:
        bits2 = {idx for idx, val in enumerate(fp2) if val > 0}

    total_cardinality = len(bits1) + len(bits2)
    if total_cardinality == 0:
        return 1.0
    intersection_size = len(bits1 & bits2)
    return float(2.0 * intersection_size / total_cardinality)
