#!/usr/bin/env python3
"""
Zero-Mock Physical Test Suite for CoChem-MInt Consolidated Intake Backend.
Module: test_suite/test_cochem_mint_ingestor.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

import pytest

from intake.cochem_mint_ingestor import (
    CoChemMIntUI,
    IngestionWatchdog,
    bootstrap_watchdog,
    generate_3d_geometry,
    print_status,
    resolve_smiles,
    sanitize_project_name,
    save_uploaded_geometries,
    scan_workspace_geometries,
    validate_xyz_content,
)


def test_sanitize_project_name_normal() -> None:
    """Verify standard project names are preserved cleanly."""
    assert sanitize_project_name("My_Project") == "My_Project"
    assert sanitize_project_name("Benzene_Simulation_01") == "Benzene_Simulation_01"


def test_sanitize_project_name_spaces_and_special() -> None:
    """Verify spaces and non-alphanumeric chars are converted to underscores."""
    assert sanitize_project_name("My New Project") == "My_New_Project"
    assert sanitize_project_name("Molecule #1 (Batch A)!") == "Molecule_1_Batch_A"


def test_sanitize_project_name_path_traversal() -> None:
    """Verify directory traversal attacks are neutralized."""
    assert sanitize_project_name("../../evil_workspace") == "evil_workspace"
    assert sanitize_project_name("..\\..\\malicious") == "malicious"
    assert sanitize_project_name("sub/folder/target") == "target"


def test_sanitize_project_name_empty_or_whitespace() -> None:
    """Verify empty or whitespace strings fallback safely."""
    assert sanitize_project_name("") == "New_Project"
    assert sanitize_project_name("   ") == "New_Project"
    assert sanitize_project_name("...") == "New_Project"


def test_validate_xyz_content_valid() -> None:
    """Verify valid XYZ coordinates pass validation and return atom count."""
    valid_xyz = """3
Water Molecule
O  0.000000  0.000000  0.117300
H  0.000000  0.757200 -0.469200
H  0.000000 -0.757200 -0.469200
"""
    is_valid, count, comment = validate_xyz_content(valid_xyz)
    assert is_valid is True
    assert count == 3
    assert comment == "Water Molecule"

    # Also test bytes input
    is_valid_b, count_b, comment_b = validate_xyz_content(valid_xyz.encode("utf-8"))
    assert is_valid_b is True
    assert count_b == 3
    assert comment_b == "Water Molecule"


def test_validate_xyz_content_invalid() -> None:
    """Verify malformed XYZ content is rejected."""
    assert validate_xyz_content("")[0] is False
    assert validate_xyz_content("NotAnInteger\nComment\nO 0 0 0")[0] is False
    assert validate_xyz_content("3\nComment\nO 0 0 0\nH 0 0 1")[0] is False
    assert validate_xyz_content("1\nComment\nO 0 0 NotANumber")[0] is False


def test_generate_3d_geometry_ethanol(tmp_path: Path) -> None:
    """Verify RDKit generates real 3D conformer with full hydrogens for ethanol."""
    out_file = tmp_path / "ethanol.xyz"
    result = generate_3d_geometry("CCO", output_path=out_file, optimize_mmff=True)

    assert result.exists()
    assert result == out_file

    content = out_file.read_text(encoding="utf-8")
    is_valid, atom_count, _ = validate_xyz_content(content)
    assert is_valid is True
    # Ethanol C2H6O has 2 C + 1 O + 6 H = 9 atoms
    assert atom_count == 9


def test_generate_3d_geometry_methane(tmp_path: Path) -> None:
    """Verify 3D geometry generation for methane."""
    out_file = tmp_path / "methane.xyz"
    result = generate_3d_geometry("C", output_path=out_file, optimize_mmff=True)
    assert result.exists()

    content = out_file.read_text(encoding="utf-8")
    is_valid, atom_count, _ = validate_xyz_content(content)
    assert is_valid is True
    # Methane CH4 = 5 atoms
    assert atom_count == 5


def test_generate_3d_geometry_invalid_smiles(tmp_path: Path) -> None:
    """Verify invalid SMILES raises ValueError."""
    with pytest.raises(ValueError, match="RDKit could not mathematically parse"):
        generate_3d_geometry("InvalidSMILES_XYZ_123", output_path=tmp_path / "fail.xyz")


def test_resolve_smiles_direct() -> None:
    """Verify direct SMILES parsing without network call."""
    smiles, source = resolve_smiles("CCO")
    assert smiles == "CCO"
    assert source == "direct_smiles"

    smiles2, source2 = resolve_smiles("c1ccccc1")
    assert smiles2 == "c1ccccc1"
    assert source2 == "direct_smiles"


def test_resolve_smiles_pubchem() -> None:
    """Verify PubChem API resolves common names to SMILES."""
    smiles, source = resolve_smiles("Aspirin")
    assert smiles is not None
    assert source == "pubchem"
    assert "C" in smiles


def test_resolve_smiles_empty() -> None:
    """Verify empty query returns None."""
    smiles, source = resolve_smiles("   ")
    assert smiles is None
    assert source is None


def test_scan_workspace_geometries(tmp_path: Path) -> None:
    """Verify directory scanner identifies and parses real .xyz files."""
    f1 = tmp_path / "mol1.xyz"
    f1.write_text("3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    f2 = tmp_path / "mol2.xyz"
    f2.write_text("1\nSingle Atom\nC 0.0 0.0 0.0\n", encoding="utf-8")

    f3 = tmp_path / "other.txt"
    f3.write_text("Not an xyz file", encoding="utf-8")

    results = scan_workspace_geometries(tmp_path)
    assert len(results) == 2

    names = {r["name"] for r in results}
    assert "mol1.xyz" in names
    assert "mol2.xyz" in names

    mol1_info = next(r for r in results if r["name"] == "mol1.xyz")
    assert mol1_info["valid"] is True
    assert mol1_info["atom_count"] == 3
    assert mol1_info["comment"] == "Water"


def test_save_uploaded_geometries_ipywidgets_v7(tmp_path: Path) -> None:
    """Verify file upload handler processes ipywidgets 7 dict schema."""
    upload_dict = {
        "water.xyz": {
            "content": b"3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
            "metadata": {"size": 35},
        }
    }
    saved = save_uploaded_geometries(upload_dict, tmp_path)
    assert len(saved) == 1
    assert saved[0].name == "water.xyz"
    assert saved[0].exists()
    assert "Water" in saved[0].read_text(encoding="utf-8")


def test_save_uploaded_geometries_ipywidgets_v8(tmp_path: Path) -> None:
    """Verify file upload handler processes ipywidgets 8 tuple schema."""
    upload_tuple = (
        {
            "name": "methane.xyz",
            "content": memoryview(b"5\nMethane\nC 0 0 0\nH 1 0 0\nH -1 0 0\nH 0 1 0\nH 0 -1 0\n"),
        },
    )
    saved = save_uploaded_geometries(upload_tuple, tmp_path)
    assert len(saved) == 1
    assert saved[0].name == "methane.xyz"
    assert saved[0].exists()


def test_save_uploaded_geometries_path_traversal(tmp_path: Path) -> None:
    """Verify path traversal in uploaded filename is safely sanitized."""
    upload_tuple = (
        {
            "name": "../../evil_upload.xyz",
            "content": b"1\nAtom\nHe 0 0 0\n",
        },
    )
    saved = save_uploaded_geometries(upload_tuple, tmp_path)
    assert len(saved) == 1
    assert saved[0].parent == tmp_path.resolve()
    assert saved[0].name == "evil_upload.xyz"


def test_ingestion_watchdog_callback() -> None:
    """Verify IngestionWatchdog triggers callback on .xyz creation."""
    events_logged: List[str] = []

    def dummy_cb(msg: str) -> None:
        events_logged.append(msg)

    watchdog = IngestionWatchdog(dummy_cb)

    class MockEvent:
        def __init__(self, path: str, is_dir: bool = False):
            self.src_path = path
            self.is_directory = is_dir

    watchdog.on_created(MockEvent("/tmp/cochem_artifacts/test_mol.xyz", False))
    assert len(events_logged) == 1
    assert "test_mol.xyz" in events_logged[0]

    watchdog.on_created(MockEvent("/tmp/cochem_artifacts/data.csv", False))
    assert len(events_logged) == 1

    watchdog.on_created(MockEvent("/tmp/cochem_artifacts/subdir.xyz", True))
    assert len(events_logged) == 1


def test_cochem_mint_ui_full_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify complete CoChemMIntUI initialization, workspace resolution, and actions."""
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path / "CoChem_Artifacts"))

    ui = CoChemMIntUI(default_project="Test_Experiment_A")
    assert ui.current_workspace.name == "Test_Experiment_A"
    assert ui.current_workspace.exists()

    ui.project_name.value = "Project Beta 2026"
    assert ui.current_workspace.name == "Project_Beta_2026"
    assert ui.current_workspace.exists()

    ui.molecule_name_input.value = "CCO"
    ui._on_build_clicked(None)

    built_files = list(ui.current_workspace.glob("*.xyz"))
    assert len(built_files) >= 1
    assert any("CCO_rdkit.xyz" in f.name for f in built_files)

    ui._on_scan_clicked(None)
    ui._on_watch_clicked(None)
    ui._on_watch_clicked(None)
    ui.close()


def test_print_status_utility() -> None:
    """Verify print_status executes without throwing exceptions."""
    print_status("Initialization successful", "success")
    print_status("Warning encountered", "warning")
    print_status("Fatal error", "fail")
    print_status("Standard info", "info")


def test_bootstrap_watchdog() -> None:
    """Verify bootstrap_watchdog returns boolean without crash."""
    res = bootstrap_watchdog()
    assert isinstance(res, bool)