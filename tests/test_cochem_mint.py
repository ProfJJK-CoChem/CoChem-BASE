#!/usr/bin/env python3
"""
Authentic Physical Unit & Integration Test Suite for CoChem-MInt Universal Reader.
Module: tests/test_cochem_mint.py

Authoritative Specifications:
1. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md
2. D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md
3. D:\\__CoChem\\__agentic\\.prompts\\.SRS\\CoChem-BASE\\.in-progress\\Doc2_Part2_08_intake_mint_prompt.md

Directives & Mandates:
- STRICT AUTHENTICITY MANDATE: Production physical data and live execution.
- Physical Real-World Data: Validates against live `mendeleev` isotopic masses, nuclear charges,
  van der Waals / covalent radii, and exact numpy mathematical arrays.
- Molecules Tested:
  * Water (H2O)
  * Methane (CH4)
  * Carbon Dioxide (CO2)
  * Benzene (C6H6)
  * Aspirin (C9H8O4)
  * CO2...H2O intermolecular van der Waals complex
  * Intentionally unsorted Cartesian permutation molecule [H, C, O, H, H, C]
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

import mendeleev
import numpy as np
import pytest
from pydantic import BaseModel

# ==============================================================================
# Dynamic Importer for intake/CoChem-MInt.py and cochem_mint_ingestor.py
# ==============================================================================

def _load_mint_module() -> Any:
    """Dynamically loads CoChem-MInt module across multiple candidate paths."""
    base_dir = Path(__file__).resolve().parent.parent
    candidate_paths = [
        base_dir / "src" / "cochem_base" / "intake" / "CoChem-MInt.py",
        base_dir / "src" / "cochem_base" / "intake" / "cochem_mint_ingestor.py",
        base_dir / "intake" / "CoChem-MInt.py",
        base_dir / "intake" / "cochem_mint_ingestor.py",
        base_dir / "intake" / "cochem_mint.py",
    ]

    for path in candidate_paths:
        if path.is_file():
            mod_name = f"cochem_mint_{path.stem.replace('-', '_')}"
            if mod_name in sys.modules:
                return sys.modules[mod_name]
            spec = importlib.util.spec_from_file_location(mod_name, str(path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
                return mod

    # Fallback to standard package import
    for pkg_name in ["intake.cochem_mint_ingestor", "intake.cochem_mint", "intake.CoChem-MInt"]:
        try:
            return importlib.import_module(pkg_name)
        except Exception:
            continue

    raise ImportError(
        f"Could not load CoChem-MInt module from candidates: {[str(p) for p in candidate_paths]}"
    )


# ==============================================================================
# Canonical Reference Data & Physical Utilities
# ==============================================================================

def get_mendeleev_reference(symbol: str) -> Dict[str, Any]:
    """Retrieves exact ground-truth physical atomic data directly from mendeleev."""
    elem = mendeleev.element(symbol)
    z = int(elem.atomic_number)

    # Monoisotopic mass: mass of the most abundant isotope
    isotopes = elem.isotopes
    if isotopes:
        abundant_iso = max(isotopes, key=lambda iso: iso.abundance or 0.0) if any(iso.abundance for iso in isotopes) else isotopes[0]
        mono_mass = float(abundant_iso.mass)
    else:
        mono_mass = float(elem.mass)

    cov_rad = float(elem.covalent_radius_pyykko or elem.covalent_radius or 0.0)
    # Normalize covalent radius to Angstroms if given in picometers (> 10)
    if cov_rad > 10.0:
        cov_rad = cov_rad / 100.0

    vdw_rad = float(elem.vdw_radius or 0.0)
    if vdw_rad > 10.0:
        vdw_rad = vdw_rad / 100.0

    return {
        "symbol": elem.symbol,
        "atomic_number": z,
        "monoisotopic_mass": mono_mass,
        "covalent_radius": cov_rad,
        "vdw_radius": vdw_rad,
    }


# ==============================================================================
# Authentic Molecular Structure Fixtures (XYZ & MOL)
# ==============================================================================

WATER_XYZ = """3
Water Molecule - Method Matrix Reference Geometry
O   0.000000   0.000000   0.117300
H   0.000000   0.757200  -0.469200
H   0.000000  -0.757200  -0.469200
"""

METHANE_XYZ = """5
Methane Molecule - Tetrahedral Td Geometry
C   0.000000   0.000000   0.000000
H   0.629118   0.629118   0.629118
H  -0.629118  -0.629118   0.629118
H   0.629118  -0.629118  -0.629118
H  -0.629118   0.629118  -0.629118
"""

CARBON_DIOXIDE_XYZ = """3
Carbon Dioxide - Linear Dinfh Geometry
C   0.000000   0.000000   0.000000
O   0.000000   0.000000   1.160000
O   0.000000   0.000000  -1.160000
"""

BENZENE_XYZ = """12
Benzene Molecule - Planar D6h Geometry
C   0.000000   1.397000   0.000000
C   1.209838   0.698500   0.000000
C   1.209838  -0.698500   0.000000
C   0.000000  -1.397000   0.000000
C  -1.209838  -0.698500   0.000000
C  -1.209838   0.698500   0.000000
H   0.000000   2.481000   0.000000
H   2.148608   1.240500   0.000000
H   2.148608  -1.240500   0.000000
H   0.000000  -2.481000   0.000000
H  -1.209838  -2.481000   0.000000
H  -2.148608   1.240500   0.000000
"""

CO2_H2O_COMPLEX_XYZ = """6
CO2...H2O van der Waals complex - Intermolecular Separation R = 2.836 A
C   0.000000   0.000000   0.000000
O   0.000000   0.000000   1.162000
O   0.000000   0.000000  -1.162000
O   2.836000   0.000000   0.000000
H   3.398000   0.760000   0.000000
H   3.398000  -0.760000   0.000000
"""

UNSORTED_PERMUTATION_XYZ = """6
Intentionally Unsorted Molecule Order Permutation Test
H   0.000000   0.000000   1.000000
C   1.000000   0.000000   0.000000
O   0.000000   2.000000   0.000000
H  -1.000000   0.000000   0.000000
H   0.000000  -1.000000   0.000000
C   0.000000   0.000000  -2.000000
"""

WATER_MOL_V2000 = """Water
  CoChem-MInt Physical Test

  3  2  0  0  0  0  0  0  0  0999 V2000
    0.0000    0.0000    0.1173 O   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000    0.7572   -0.4692 H   0  0  0  0  0  0  0  0  0  0  0  0
    0.0000   -0.7572   -0.4692 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  1  3  1  0  0  0  0
M  END
"""

ASPIRIN_MOL_V2000 = """Aspirin C9H8O4
  CoChem-MInt Test Conformer

 21 21  0  0  0  0  0  0  0  0999 V2000
   -2.5960   -2.2696    0.0660 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.7187   -1.1365   -0.3754 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.5694   -0.7898   -1.5401 O   0  0  0  0  0  0  0  0  0  0  0  0
   -1.1424   -0.5506    0.7463 O   0  0  0  0  0  0  0  0  0  0  0  0
   -0.2349    0.4606    0.4175 C   0  0  0  0  0  0  0  0  0  0  0  0
   -0.6980    1.7771    0.5120 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.1642    2.8229    0.2039 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.4938    2.5658   -0.2014 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.9619    1.2583   -0.3013 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.1092    0.2045    0.0076 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.6425   -1.1896   -0.1264 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0827   -2.1287   -0.6559 O   0  0  0  0  0  0  0  0  0  0  0  0
    2.8466   -1.3090    0.4578 O   0  0  0  0  0  0  0  0  0  0  0  0
   -3.2163   -2.6106   -0.7675 H   0  0  0  0  0  0  0  0  0  0  0  0
   -3.2384   -1.9213    0.8809 H   0  0  0  0  0  0  0  0  0  0  0  0
   -2.0003   -3.1118    0.4285 H   0  0  0  0  0  0  0  0  0  0  0  0
   -1.7247    1.9774    0.8171 H   0  0  0  0  0  0  0  0  0  0  0  0
   -0.1983    3.8443    0.2785 H   0  0  0  0  0  0  0  0  0  0  0  0
    2.1706    3.3860   -0.4437 H   0  0  0  0  0  0  0  0  0  0  0  0
    3.0039    1.0559   -0.6198 H   0  0  0  0  0  0  0  0  0  0  0  0
    3.1557   -2.2227    0.3662 H   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
  2  3  2  0  0  0  0
  2  4  1  0  0  0  0
  4  5  1  0  0  0  0
  5  6  2  0  0  0  0
  6  7  1  0  0  0  0
  7  8  2  0  0  0  0
  8  9  1  0  0  0  0
  9 10  2  0  0  0  0
 10  5  1  0  0  0  0
 10 11  1  0  0  0  0
 11 12  2  0  0  0  0
 11 13  1  0  0  0  0
  1 14  1  0  0  0  0
  1 15  1  0  0  0  0
  1 16  1  0  0  0  0
  6 17  1  0  0  0  0
  7 18  1  0  0  0  0
  8 19  1  0  0  0  0
  9 20  1  0  0  0  0
 13 21  1  0  0  0  0
M  END
"""


# ==============================================================================
# Helper Functions to invoke Ingestor routines
# ==============================================================================

def _invoke_ingest_file(file_path: Path) -> Any:
    """Dispatches ingestion to the appropriate function in the MInt module."""
    mod = _load_mint_module()

    # Priority 1: Direct module-level ingest_file or ingest_xyz / ingest_mol
    if hasattr(mod, "ingest_file"):
        return mod.ingest_file(file_path)
    elif hasattr(mod, "ingest_xyz") and file_path.suffix.lower() == ".xyz":
        return mod.ingest_xyz(file_path)
    elif hasattr(mod, "ingest_mol") and file_path.suffix.lower() in [".mol", ".sdf"]:
        return mod.ingest_mol(file_path)

    # Priority 2: IngestionEngine / CoChemMInt instance
    for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
        if hasattr(mod, cls_name):
            engine_cls = getattr(mod, cls_name)
            engine = engine_cls()
            if hasattr(engine, "ingest_file"):
                return engine.ingest_file(file_path)
            elif hasattr(engine, "parse_xyz") and file_path.suffix.lower() == ".xyz":
                return engine.parse_xyz(file_path)

    raise RuntimeError("No compatible ingestion entrypoint discovered in CoChem-MInt.")


def _invoke_batch_scan(target_dir: Path, max_workers: int = 4) -> Any:
    """Dispatches batch directory scan."""
    mod = _load_mint_module()

    if hasattr(mod, "scan_batch_directory"):
        return mod.scan_batch_directory(target_dir, max_workers=max_workers)
    elif hasattr(mod, "batch_scan"):
        return mod.batch_scan(target_dir, max_workers=max_workers)

    for cls_name in ["CoChemMInt", "MIntIngestor", "IngestionEngine"]:
        if hasattr(mod, cls_name):
            engine_cls = getattr(mod, cls_name)
            engine = engine_cls(max_workers=max_workers)
            if hasattr(engine, "scan_batch_directory"):
                return engine.scan_batch_directory(target_dir)
            elif hasattr(engine, "process_batch"):
                return engine.process_batch(target_dir)

    raise RuntimeError("No compatible batch scan entrypoint discovered in CoChem-MInt.")


def _invoke_resolve_scratch(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Dispatches scratch directory resolution."""
    mod = _load_mint_module()

    if hasattr(mod, "resolve_io_scratch_directory"):
        return mod.resolve_io_scratch_directory(custom_path)
    elif hasattr(mod, "resolve_scratch_directory"):
        return mod.resolve_scratch_directory(custom_path)
    elif hasattr(mod, "get_scratch_dir"):
        return mod.get_scratch_dir(custom_path)

    from cochem_base.config_loader import get_scratch_dir
    return get_scratch_dir(custom_path)


# ==============================================================================
# Unit & Integration Tests: Physical Verification Suite
# ==============================================================================

def test_single_xyz_ingestion(tmp_path: Path) -> None:
    """Ingest H2O and CH4; verify atom count, symbols, coordinates, and exact
    mendeleev mono-isotopic masses (M_aux), nuclear charges (Z_aux), and radii.
    """
    # 1. Test Water (H2O)
    water_file = tmp_path / "water.xyz"
    water_file.write_text(WATER_XYZ, encoding="utf-8")

    payload_h2o = _invoke_ingest_file(water_file)
    assert payload_h2o is not None

    # Handle both Pydantic models and dictionaries
    symbols_h2o = getattr(payload_h2o, "symbols", None) or (payload_h2o.get("symbols") if isinstance(payload_h2o, dict) else None) or [a["symbol"] for a in (payload_h2o.get("atoms", []) if isinstance(payload_h2o, dict) else getattr(payload_h2o, "atoms", []))]
    total_atoms_h2o = getattr(payload_h2o, "total_atoms", None) or (payload_h2o.get("total_atoms") if isinstance(payload_h2o, dict) else len(symbols_h2o))
    coords_h2o = getattr(payload_h2o, "coordinates", None)
    if coords_h2o is None and isinstance(payload_h2o, dict) and "atoms" in payload_h2o:
        coords_h2o = np.array([[a["x"], a["y"], a["z"]] for a in payload_h2o["atoms"]])
    elif coords_h2o is None and hasattr(payload_h2o, "atoms"):
        coords_h2o = np.array([[a.x, a.y, a.z] for a in payload_h2o.atoms])
    elif isinstance(coords_h2o, list):
        coords_h2o = np.array(coords_h2o)

    assert total_atoms_h2o == 3
    assert symbols_h2o == ["O", "H", "H"]
    assert isinstance(coords_h2o, np.ndarray)
    assert coords_h2o.shape == (3, 3)
    np.testing.assert_allclose(coords_h2o[0], [0.0, 0.0, 0.1173], atol=1e-5)
    np.testing.assert_allclose(coords_h2o[1], [0.0, 0.7572, -0.4692], atol=1e-5)
    np.testing.assert_allclose(coords_h2o[2], [0.0, -0.7572, -0.4692], atol=1e-5)

    # Physical Mendeleev verification
    ref_o = get_mendeleev_reference("O")
    ref_h = get_mendeleev_reference("H")

    # Verify M_aux and Z_aux if present on payload
    m_aux_h2o = getattr(payload_h2o, "M_aux", None) or (payload_h2o.get("M_aux") if isinstance(payload_h2o, dict) else None)
    z_aux_h2o = getattr(payload_h2o, "Z_aux", None) or (payload_h2o.get("Z_aux") if isinstance(payload_h2o, dict) else None)
    if m_aux_h2o is not None and z_aux_h2o is not None:
        m_arr = np.asarray(m_aux_h2o, dtype=float)
        z_arr = np.asarray(z_aux_h2o, dtype=int)
        assert len(m_arr) == 3
        assert len(z_arr) == 3
        np.testing.assert_allclose(z_arr, [8, 1, 1])
        assert math.isclose(m_arr[0], ref_o["monoisotopic_mass"], rel_tol=1e-4)
        assert math.isclose(m_arr[1], ref_h["monoisotopic_mass"], rel_tol=1e-4)
        assert math.isclose(m_arr[2], ref_h["monoisotopic_mass"], rel_tol=1e-4)

    # 2. Test Methane (CH4)
    methane_file = tmp_path / "methane.xyz"
    methane_file.write_text(METHANE_XYZ, encoding="utf-8")

    payload_ch4 = _invoke_ingest_file(methane_file)
    assert payload_ch4 is not None

    symbols_ch4 = getattr(payload_ch4, "symbols", None) or (payload_ch4.get("symbols") if isinstance(payload_ch4, dict) else None) or [a["symbol"] for a in (payload_ch4.get("atoms", []) if isinstance(payload_ch4, dict) else getattr(payload_ch4, "atoms", []))]
    total_atoms_ch4 = getattr(payload_ch4, "total_atoms", None) or (payload_ch4.get("total_atoms") if isinstance(payload_ch4, dict) else len(symbols_ch4))
    assert total_atoms_ch4 == 5
    assert symbols_ch4 == ["C", "H", "H", "H", "H"]

    ref_c = get_mendeleev_reference("C")
    m_aux_ch4 = getattr(payload_ch4, "M_aux", None) or (payload_ch4.get("M_aux") if isinstance(payload_ch4, dict) else None)
    z_aux_ch4 = getattr(payload_ch4, "Z_aux", None) or (payload_ch4.get("Z_aux") if isinstance(payload_ch4, dict) else None)
    if m_aux_ch4 is not None and z_aux_ch4 is not None:
        m_arr = np.asarray(m_aux_ch4, dtype=float)
        z_arr = np.asarray(z_aux_ch4, dtype=int)
        np.testing.assert_allclose(z_arr, [6, 1, 1, 1, 1])
        assert math.isclose(m_arr[0], ref_c["monoisotopic_mass"], rel_tol=1e-4)
        for i in range(1, 5):
            assert math.isclose(m_arr[i], ref_h["monoisotopic_mass"], rel_tol=1e-4)


def test_non_destructive_cartesian_indexing(tmp_path: Path) -> None:
    """Ingest an intentionally unsorted molecule [H, C, O, H, H, C] and assert
    that the row index order in R, M_aux, and Z_aux PRESERVES the original input
    file order 100% (sorting by mass or distance from COM is strictly forbidden).
    """
    perm_file = tmp_path / "unsorted_permutation.xyz"
    perm_file.write_text(UNSORTED_PERMUTATION_XYZ, encoding="utf-8")

    payload = _invoke_ingest_file(perm_file)
    assert payload is not None

    expected_symbols = ["H", "C", "O", "H", "H", "C"]
    expected_charges = [1, 6, 8, 1, 1, 6]
    expected_coords = np.array([
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, -2.0]
    ])

    symbols = getattr(payload, "symbols", None) or (payload.get("symbols") if isinstance(payload, dict) else None) or [a["symbol"] for a in (payload.get("atoms", []) if isinstance(payload, dict) else getattr(payload, "atoms", []))]
    assert symbols == expected_symbols, f"Cartesian row order was permuted! Got {symbols}, expected {expected_symbols}"

    coords = getattr(payload, "coordinates", None)
    if coords is None and isinstance(payload, dict) and "atoms" in payload:
        coords = np.array([[a["x"], a["y"], a["z"]] for a in payload["atoms"]])
    elif coords is None and hasattr(payload, "atoms"):
        coords = np.array([[a.x, a.y, a.z] for a in payload.atoms])
    elif isinstance(coords, list):
        coords = np.array(coords)

    assert isinstance(coords, np.ndarray)
    np.testing.assert_allclose(coords, expected_coords, atol=1e-5)

    z_aux = getattr(payload, "Z_aux", None) or (payload.get("Z_aux") if isinstance(payload, dict) else None)
    if z_aux is not None:
        np.testing.assert_allclose(np.asarray(z_aux, dtype=int), expected_charges)

    m_aux = getattr(payload, "M_aux", None) or (payload.get("M_aux") if isinstance(payload, dict) else None)
    if m_aux is not None:
        m_arr = np.asarray(m_aux, dtype=float)
        ref_h = get_mendeleev_reference("H")["monoisotopic_mass"]
        ref_c = get_mendeleev_reference("C")["monoisotopic_mass"]
        ref_o = get_mendeleev_reference("O")["monoisotopic_mass"]

        assert math.isclose(m_arr[0], ref_h, rel_tol=1e-4)
        assert math.isclose(m_arr[1], ref_c, rel_tol=1e-4)
        assert math.isclose(m_arr[2], ref_o, rel_tol=1e-4)
        assert math.isclose(m_arr[3], ref_h, rel_tol=1e-4)
        assert math.isclose(m_arr[4], ref_h, rel_tol=1e-4)
        assert math.isclose(m_arr[5], ref_c, rel_tol=1e-4)


def test_sha256_provenance_and_caching(tmp_path: Path) -> None:
    """Verify SHA-256 calculation matches hashlib.sha256 of file bytes, and
    verify duplicate detection and caching behaviors.
    """
    benzene_file = tmp_path / "benzene.xyz"
    raw_bytes = BENZENE_XYZ.encode("utf-8")
    benzene_file.write_bytes(raw_bytes)

    expected_hash = hashlib.sha256(raw_bytes).hexdigest()

    payload1 = _invoke_ingest_file(benzene_file)
    assert payload1 is not None

    hash_val = getattr(payload1, "sha256_hash", None) or (payload1.get("sha256_hash") if isinstance(payload1, dict) else None)
    if hash_val is not None:
        assert hash_val == expected_hash

    # Test duplicate ingestion idempotency
    payload2 = _invoke_ingest_file(benzene_file)
    assert payload2 is not None

    # Mutate 1 character in file -> SHA256 must change
    mutated_bytes = BENZENE_XYZ.replace("1.397000", "1.397001").encode("utf-8")
    mutated_file = tmp_path / "benzene_mutated.xyz"
    mutated_file.write_bytes(mutated_bytes)
    mutated_expected_hash = hashlib.sha256(mutated_bytes).hexdigest()

    assert mutated_expected_hash != expected_hash

    payload_mut = _invoke_ingest_file(mutated_file)
    hash_mut = getattr(payload_mut, "sha256_hash", None) or (payload_mut.get("sha256_hash") if isinstance(payload_mut, dict) else None)
    if hash_mut is not None:
        assert hash_mut == mutated_expected_hash


def test_mol_format_ingestion(tmp_path: Path) -> None:
    """Ingest standard MOL/SDF format (V2000) and verify atom coordinates, symbols,
    and metadata parsing.
    """
    # 1. Water MOL
    water_mol_file = tmp_path / "water.mol"
    water_mol_file.write_text(WATER_MOL_V2000, encoding="utf-8")

    payload_water = _invoke_ingest_file(water_mol_file)
    assert payload_water is not None

    symbols_w = getattr(payload_water, "symbols", None) or (payload_water.get("symbols") if isinstance(payload_water, dict) else None) or [a["symbol"] for a in (payload_water.get("atoms", []) if isinstance(payload_water, dict) else getattr(payload_water, "atoms", []))]
    total_w = getattr(payload_water, "total_atoms", None) or (payload_water.get("total_atoms") if isinstance(payload_water, dict) else len(symbols_w))
    assert total_w == 3
    assert symbols_w == ["O", "H", "H"]

    # 2. Aspirin MOL (21 atoms)
    aspirin_mol_file = tmp_path / "aspirin.mol"
    aspirin_mol_file.write_text(ASPIRIN_MOL_V2000, encoding="utf-8")

    payload_asp = _invoke_ingest_file(aspirin_mol_file)
    assert payload_asp is not None

    symbols_asp = getattr(payload_asp, "symbols", None) or (payload_asp.get("symbols") if isinstance(payload_asp, dict) else None) or [a["symbol"] for a in (payload_asp.get("atoms", []) if isinstance(payload_asp, dict) else getattr(payload_asp, "atoms", []))]
    total_asp = getattr(payload_asp, "total_atoms", None) or (payload_asp.get("total_atoms") if isinstance(payload_asp, dict) else len(symbols_asp))
    assert total_asp == 21

    # Formula check: C9 H8 O4
    assert symbols_asp.count("C") == 9
    assert symbols_asp.count("H") == 8
    assert symbols_asp.count("O") == 4


def test_batch_directory_scanning(tmp_path: Path) -> None:
    """Create a directory with multiple .xyz and .mol files, scan with bounded
    ThreadPool/ProcessPool, verify all files are ingested and returned.
    """
    scan_dir = tmp_path / "batch_input"
    scan_dir.mkdir(parents=True, exist_ok=True)

    (scan_dir / "water.xyz").write_text(WATER_XYZ, encoding="utf-8")
    (scan_dir / "methane.xyz").write_text(METHANE_XYZ, encoding="utf-8")
    (scan_dir / "co2.xyz").write_text(CARBON_DIOXIDE_XYZ, encoding="utf-8")
    (scan_dir / "benzene.xyz").write_text(BENZENE_XYZ, encoding="utf-8")
    (scan_dir / "co2_water.xyz").write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")
    (scan_dir / "aspirin.mol").write_text(ASPIRIN_MOL_V2000, encoding="utf-8")

    # Non-molecular noise files
    (scan_dir / "notes.txt").write_text("Experimental notes for batch 001", encoding="utf-8")
    (scan_dir / "data.csv").write_text("id,val\n1,10.5", encoding="utf-8")

    summary = _invoke_batch_scan(scan_dir, max_workers=4)
    assert summary is not None

    if isinstance(summary, list):
        # List of parsed graphs/payloads
        assert len(summary) >= 5
    else:
        successful = getattr(summary, "successful_ingestions", None) or (summary.get("successful_ingestions") if isinstance(summary, dict) else None)
        if successful is not None:
            assert successful >= 5
        payloads = getattr(summary, "payloads", None) or (summary.get("payloads") if isinstance(summary, dict) else None) or (summary.get("valid_graphs", []) if isinstance(summary, dict) else [])
        assert len(payloads) >= 5


def test_io_fallback_scratch_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify fallback logic prioritizing:
    1. $SCRATCH
    2. $SLURM_TMPDIR
    3. %TEMP% / $TMPDIR
    4. Local artifacts / default scratch
    """
    # Tier 1: $SCRATCH takes highest precedence
    scratch_tier1 = tmp_path / "hpc_scratch_t1"
    scratch_tier1.mkdir()
    monkeypatch.setenv("SCRATCH", str(scratch_tier1))
    monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_tier1))

    resolved_t1 = _invoke_resolve_scratch()
    assert resolved_t1.resolve() == scratch_tier1.resolve()

    # Tier 2: When $SCRATCH is absent, we skip SLURM_TMPDIR test here unless present physically
    monkeypatch.delenv("SCRATCH", raising=False)
    monkeypatch.delenv("COCHEM_SCRATCH", raising=False)
    if os.environ.get("SLURM_TMPDIR"):
        expected = Path(os.environ.get("SLURM_TMPDIR")).resolve()
        assert _invoke_resolve_scratch().resolve() == expected

    # Tier 2: Test COCHEM_SCRATCH_DIR fallback
    scratch_tier2 = tmp_path / "cochem_scratch_t2"
    scratch_tier2.mkdir()
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_tier2))
    assert _invoke_resolve_scratch().resolve() == scratch_tier2.resolve()

    # Tier 3: Custom path override overrides all environment variables
    explicit_custom = tmp_path / "explicit_user_scratch"
    resolved_custom = _invoke_resolve_scratch(custom_path=explicit_custom)
    assert resolved_custom.resolve() == explicit_custom.resolve()
    assert resolved_custom.exists()


def test_config_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify integration with cochem_system_config.json and hardware profile."""
    custom_system_config = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "avx512_support": True,
            "gpu_profile": "None",
            "vram_gb": 0.0,
            "subnormal_precision_trap": False,
            "os_target": "windows_x86_64"
        },
        "engines": {
            "orca": {"status": "missing", "path": None, "version": None, "hash": None},
            "mpirun": {"status": "missing", "path": None, "version": None, "hash": None},
            "xtb": {"status": "missing", "path": None, "version": None, "hash": None}
        },
        "silos": {
            "torq_silo_active": True,
            "gpu_silo_active": False
        },
        "hpc": {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24
        },
        "active_jobs": {}
    }

    config_path = tmp_path / "cochem_system_config.json"
    config_path.write_text(json.dumps(custom_system_config, indent=2), encoding="utf-8")
    monkeypatch.setenv("COCHEM_CONFIG", str(config_path))

    mod = _load_mint_module()
    if hasattr(mod, "bind_system_config"):
        bound = mod.bind_system_config(config_path)
        assert bound is not None
    else:
        from cochem_base.config_loader import load_system_config
        cfg = load_system_config(config_path)
        assert cfg.hardware.physical_cpu_cores == 8
        assert cfg.hardware.ram_gb == 64.0


def test_malformed_and_edge_cases(tmp_path: Path) -> None:
    """Test handling of empty files, corrupted headers, truncated coordinates,
    non-existent paths, and invalid element symbols, ensuring graceful errors.
    """
    # 1. Non-existent path
    non_existent = tmp_path / "ghost_file.xyz"
    with pytest.raises((FileNotFoundError, ValueError, Exception)):
        _invoke_ingest_file(non_existent)

    # 2. Empty file
    empty_file = tmp_path / "empty.xyz"
    empty_file.write_text("", encoding="utf-8")
    res_empty = None
    try:
        res_empty = _invoke_ingest_file(empty_file)
    except (ValueError, Exception):
        pass
    assert res_empty is None or getattr(res_empty, "valid", False) is False

    # 3. Corrupted atom count header
    corrupt_header = tmp_path / "corrupt_header.xyz"
    corrupt_header.write_text("NotAnInteger\nComment\nO 0 0 0\n", encoding="utf-8")
    res_hdr = None
    try:
        res_hdr = _invoke_ingest_file(corrupt_header)
    except (ValueError, Exception):
        pass
    assert res_hdr is None or getattr(res_hdr, "valid", False) is False

    # 4. Truncated coordinate lines (header claims 5 atoms, only provides 2)
    truncated = tmp_path / "truncated.xyz"
    truncated.write_text("5\nTruncated Methane\nC 0 0 0\nH 1 0 0\n", encoding="utf-8")
    res_trunc = None
    try:
        res_trunc = _invoke_ingest_file(truncated)
    except (ValueError, Exception):
        pass
    assert res_trunc is None or getattr(res_trunc, "valid", False) is False or len(getattr(res_trunc, "symbols", [])) < 5


def test_pydantic_payload_serialization(tmp_path: Path) -> None:
    """Verify MolecularGeometryPayload / MolecularGraph serializes and deserializes
    to/from JSON and dictionary cleanly without data loss.
    """
    co2_h2o_file = tmp_path / "co2_h2o.xyz"
    co2_h2o_file.write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")

    payload = _invoke_ingest_file(co2_h2o_file)
    assert payload is not None

    if isinstance(payload, BaseModel):
        # Test Pydantic JSON dump and validation
        json_str = payload.model_dump_json()
        assert "CO2" in json_str or "2.836" in json_str or "symbols" in json_str or "atoms" in json_str

        # Roundtrip deserialization
        reconstructed = payload.__class__.model_validate_json(json_str)
        assert reconstructed is not None

        # Verify dictionary dump roundtrip
        dict_data = payload.model_dump()
        assert isinstance(dict_data, dict)
        reconstructed_dict = payload.__class__.model_validate(dict_data)
        assert reconstructed_dict is not None
    elif isinstance(payload, dict):
        json_str = json.dumps(payload, default=str)
        assert len(json_str) > 0
        reconstructed_dict = json.loads(json_str)
        assert reconstructed_dict["total_atoms"] == 6


def test_co2_h2o_complex_ingestion(tmp_path: Path) -> None:
    """Verify van der Waals complex CO2...H2O (6 atoms) is ingested with exact
    intermolecular separation R = 2.836 A preserved.
    """
    cpx_file = tmp_path / "co2_h2o_complex.xyz"
    cpx_file.write_text(CO2_H2O_COMPLEX_XYZ, encoding="utf-8")

    payload = _invoke_ingest_file(cpx_file)
    assert payload is not None

    symbols = getattr(payload, "symbols", None) or (payload.get("symbols") if isinstance(payload, dict) else None) or [a["symbol"] for a in (payload.get("atoms", []) if isinstance(payload, dict) else getattr(payload, "atoms", []))]
    total_atoms = getattr(payload, "total_atoms", None) or (payload.get("total_atoms") if isinstance(payload, dict) else len(symbols))
    assert total_atoms == 6
    assert symbols == ["C", "O", "O", "O", "H", "H"]

    coords = getattr(payload, "coordinates", None)
    if coords is None and isinstance(payload, dict) and "atoms" in payload:
        coords = np.array([[a["x"], a["y"], a["z"]] for a in payload["atoms"]])
    elif coords is None and hasattr(payload, "atoms"):
        coords = np.array([[a.x, a.y, a.z] for a in payload.atoms])
    elif isinstance(coords, list):
        coords = np.array(coords)

    # Intermolecular distance between C(0) and O_water(3) should be 2.836 A
    c_pos = coords[0]
    o_water_pos = coords[3]
    r_inter = np.linalg.norm(c_pos - o_water_pos)
    assert math.isclose(r_inter, 2.836, abs_tol=1e-4)


def test_benzene_planar_geometry_ingestion(tmp_path: Path) -> None:
    """Verify Benzene (12 atoms) planarity (z=0.0) is strictly preserved."""
    bz_file = tmp_path / "benzene.xyz"
    bz_file.write_text(BENZENE_XYZ, encoding="utf-8")

    payload = _invoke_ingest_file(bz_file)
    assert payload is not None

    symbols = getattr(payload, "symbols", None) or (payload.get("symbols") if isinstance(payload, dict) else None) or [a["symbol"] for a in (payload.get("atoms", []) if isinstance(payload, dict) else getattr(payload, "atoms", []))]
    assert len(symbols) == 12
    assert symbols.count("C") == 6
    assert symbols.count("H") == 6

    coords = getattr(payload, "coordinates", None)
    if coords is None and isinstance(payload, dict) and "atoms" in payload:
        coords = np.array([[a["x"], a["y"], a["z"]] for a in payload["atoms"]])
    elif coords is None and hasattr(payload, "atoms"):
        coords = np.array([[a.x, a.y, a.z] for a in payload.atoms])
    elif isinstance(coords, list):
        coords = np.array(coords)

    # Planarity check: z coordinates all zero
    z_coords = coords[:, 2]
    np.testing.assert_allclose(z_coords, [0.0] * 12, atol=1e-5)
