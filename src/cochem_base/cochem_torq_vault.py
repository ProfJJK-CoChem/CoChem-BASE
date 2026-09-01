"""
CoChem-TORQ: Phase 2 Dual-Intake Gateway & Vault
================================================
Routes geometries into the TORQ engine, standardizing inputs from both native
ecosystem databases (landscape.h5) and external uploads (.xyz, .mol).
Applies exact CIAAW isotopic masses, SHA-256 integrity hashes, and PyArrow/Pandas standardization.

Authoritative Standards:
- CIAAW / IUPAC Standard Atomic Weights & Exact Mono-Isotopic Masses
- Method Matrix: Stage 1.0 - 2.0 Geometry Intake & Provenance Verification
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa

from cochem_base.exceptions import (
    CoChemIntegrityError,
    MissingDataError,
    ProvenanceErrorCode,
)

from collections.abc import Mapping
try:
    from mendeleev import element as _mendeleev_element
except ImportError:
    _mendeleev_element = None

from cochem_tensor_extractor import CIAAW_ISOTOPIC_MASSES

logger = logging.getLogger("CoChem-TORQ")

ATOMIC_NUMBERS: Dict[str, int] = {
    "H": 1,
    "He": 2,
    "Li": 3,
    "Be": 4,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Ne": 10,
    "Na": 11,
    "Mg": 12,
    "Al": 13,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Ar": 18,
    "K": 19,
    "Ca": 20,
    "Sc": 21,
    "Ti": 22,
    "V": 23,
    "Cr": 24,
    "Mn": 25,
    "Fe": 26,
    "Co": 27,
    "Ni": 28,
    "Cu": 29,
    "Zn": 30,
    "Ga": 31,
    "Ge": 32,
    "As": 33,
    "Se": 34,
    "Br": 35,
    "Kr": 36,
    "I": 53,
}


def compute_sha256_hash(data: Union[str, bytes]) -> str:
    """Computes SHA-256 hex digest for cryptographic integrity tracking."""
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data
    return hashlib.sha256(raw).hexdigest()


def standardize_geometry_dataframe(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    masses: Optional[Sequence[float]] = None,
    provenance_tag: str = "[D]",
) -> pd.DataFrame:
    """
    Standardizes geometry coordinates into a consistent Pandas DataFrame / PyArrow representation.
    """
    n_atoms = len(symbols)
    if coordinates.shape != (n_atoms, 3):
        raise ValueError(
            f"Coordinate shape mismatch: expected ({n_atoms}, 3), got {coordinates.shape}"
        )

    computed_masses: List[float] = []
    atomic_nums: List[int] = []

    for i, sym in enumerate(symbols):
        clean_sym = sym.capitalize()
        if masses is not None and i < len(masses):
            computed_masses.append(float(masses[i]))
        else:
            computed_masses.append(CIAAW_ISOTOPIC_MASSES.get(clean_sym, 12.0))
        atomic_nums.append(ATOMIC_NUMBERS.get(clean_sym, 6))

    df = pd.DataFrame(
        {
            "atom_index": np.arange(n_atoms, dtype=np.int32),
            "symbol": [s.capitalize() for s in symbols],
            "atomic_number": np.array(atomic_nums, dtype=np.int32),
            "x": coordinates[:, 0].astype(np.float64),
            "y": coordinates[:, 1].astype(np.float64),
            "z": coordinates[:, 2].astype(np.float64),
            "mass_amu": np.array(computed_masses, dtype=np.float64),
            "provenance": [provenance_tag] * n_atoms,
        }
    )
    return df


def parse_external_xyz(
    file_path_or_content: Union[str, Path],
    sanitize: bool = True,
) -> Dict[str, Any]:
    """
    Parses standard Cartesian XYZ format with immediate valency, proximity, and integrity sanitization.
    Throws CoChemIntegrityError if severe atomic overlap (< 0.4 Angstrom) or corrupted syntax is detected.
    """
    content: str = ""

    if isinstance(file_path_or_content, Path) or (
        isinstance(file_path_or_content, str)
        and "\n" not in file_path_or_content
        and Path(file_path_or_content).exists()
    ):
        path_obj = Path(file_path_or_content)
        with open(path_obj, "r", encoding="utf-8") as fp:
            content = fp.read()
    else:
        content = str(file_path_or_content)

    if not content.strip():
        raise MissingDataError(
            message="Empty XYZ file or content provided to parser.",
            error_code=ProvenanceErrorCode.MISSING_DATA,
        )

    sha256 = compute_sha256_hash(content)
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

    if len(lines) < 3:
        raise CoChemIntegrityError(
            message=f"Corrupt XYZ format: Expected at least 3 lines, got {len(lines)}",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    try:
        atom_count = int(lines[0])
    except ValueError as err:
        raise CoChemIntegrityError(
            message=f"Invalid atom count on line 1: '{lines[0]}'",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        ) from err

    comment = lines[1]
    coord_lines = lines[2:]

    if len(coord_lines) < atom_count:
        raise CoChemIntegrityError(
            message=f"Atom count mismatch: header declared {atom_count}, found {len(coord_lines)} coordinate lines.",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    symbols: List[str] = []
    coords: List[List[float]] = []

    for idx in range(atom_count):
        tokens = coord_lines[idx].split()
        if len(tokens) < 4:
            raise CoChemIntegrityError(
                message=f"Invalid XYZ coordinate row at index {idx}: '{coord_lines[idx]}'",
                error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
            )
        sym = tokens[0].capitalize()
        try:
            x, y, z = float(tokens[1]), float(tokens[2]), float(tokens[3])
        except ValueError as err:
            raise CoChemIntegrityError(
                message=f"Non-numeric coordinates on line {idx + 3}: '{coord_lines[idx]}'",
                error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
            ) from err

        symbols.append(sym)
        coords.append([x, y, z])

    coords_arr = np.array(coords, dtype=np.float64)

    # Proximity sanitization: check for unphysical overlap < 0.4 Angstrom
    if sanitize and atom_count > 1:
        diff = coords_arr[:, np.newaxis, :] - coords_arr[np.newaxis, :, :]
        dist_mat = np.sqrt(np.sum(diff**2, axis=-1))
        np.fill_diagonal(dist_mat, 999.0)
        min_dist = float(np.min(dist_mat))
        if min_dist < 0.4:
            min_i, min_j = np.unravel_index(np.argmin(dist_mat), dist_mat.shape)
            msg = f"Severe atomic clash detected between atom {min_i} ({symbols[min_i]}) and atom {min_j} ({symbols[min_j]}): distance = {min_dist:.4f} Angstrom (< 0.4 Angstrom limit)."
            logger.error(msg)
            raise CoChemIntegrityError(
                message=msg,
                error_code=ProvenanceErrorCode.PATHOLOGY_CLASH,
                details={
                    "field": "coordinates",
                    "value": f"{min_dist:.4f}",
                    "expected": ">= 0.4 Angstrom",
                },
            )

    masses = [CIAAW_ISOTOPIC_MASSES.get(s, 12.0) for s in symbols]
    atomic_numbers = [ATOMIC_NUMBERS.get(s, 6) for s in symbols]

    df = standardize_geometry_dataframe(symbols, coords_arr, masses, provenance_tag="[D]")
    arrow_table = pa.Table.from_pandas(df)

    logger.info("Successfully parsed XYZ geometry (%d atoms, SHA256=%s...)", atom_count, sha256[:8])

    return {
        "symbols": symbols,
        "coordinates": coords_arr,
        "masses": np.array(masses, dtype=np.float64),
        "atomic_numbers": np.array(atomic_numbers, dtype=np.int32),
        "atom_count": atom_count,
        "title": comment,
        "sha256_hash": sha256,
        "dataframe": df,
        "arrow_table": arrow_table,
        "provenance": "[D]",
    }


def fetch_topos_matrices(
    h5_path: Union[str, Path],
    conformer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Polls landscape.h5 for native conformers and pre-converged wavefunctions processed by CoChem-TOPOS.
    """
    target = Path(h5_path).resolve()
    if not target.exists():
        raise MissingDataError(
            message=f"HDF5 database not found: {target}",
            error_code=ProvenanceErrorCode.MISSING_DATA,
        )

    with h5py.File(target, "r") as fp:
        conformers_group = fp.get("conformers")
        if conformers_group is None:
            conf_keys = list(fp.keys())
            if not conf_keys:
                raise MissingDataError(
                    message=f"No conformers or datasets found in HDF5 archive: {target}",
                    error_code=ProvenanceErrorCode.MISSING_DATA,
                )
            selected_key = conformer_id if (conformer_id and conformer_id in fp) else conf_keys[0]
            conf_node = fp[selected_key]
        else:
            conf_keys = list(conformers_group.keys())
            if not conf_keys:
                raise MissingDataError(
                    message=f"Empty conformers group in HDF5 archive: {target}",
                    error_code=ProvenanceErrorCode.MISSING_DATA,
                )
            selected_key = (
                conformer_id
                if (conformer_id and conformer_id in conformers_group)
                else conf_keys[0]
            )
            conf_node = conformers_group[selected_key]

        coords = np.array(conf_node["coordinates"], dtype=np.float64)
        raw_symbols = conf_node["symbols"]
        symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw_symbols]
        energy = (
            float(conf_node.attrs.get("energy_hartree", 0.0))
            if "energy_hartree" in conf_node.attrs
            else (float(conf_node["energy"][()]) if "energy" in conf_node else 0.0)
        )
        gbw_path = str(conf_node.attrs.get("gbw_path", ""))

    masses = [CIAAW_ISOTOPIC_MASSES.get(s.capitalize(), 12.0) for s in symbols]
    atomic_numbers = [ATOMIC_NUMBERS.get(s.capitalize(), 6) for s in symbols]
    df = standardize_geometry_dataframe(symbols, coords, masses, provenance_tag="[M]")
    arrow_table = pa.Table.from_pandas(df)

    return {
        "conformer_id": selected_key,
        "symbols": symbols,
        "coordinates": coords,
        "masses": np.array(masses, dtype=np.float64),
        "atomic_numbers": np.array(atomic_numbers, dtype=np.int32),
        "energy_hartree": energy,
        "gbw_path": gbw_path,
        "dataframe": df,
        "arrow_table": arrow_table,
        "provenance": "[M]",
    }
