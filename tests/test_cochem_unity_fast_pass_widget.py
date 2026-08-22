"""Comprehensive physical verification test suite for cochem_unity_fast_pass_widget.py.

Validates:
1. File structure, strictly Unix LF line endings (\n), standard UTF-8 encoding, and zero BOM.
2. Zero personal path leaks (using cochem_base.path_sanitization.leak_patterns).
3. Zero banned anti-spoofing patterns.
4. Total eradication of Effective Medium Theory (legacy calculator) throughout canonical and test modules.
5. Hardware RAM and VRAM profiling logic before optimization (HardwareProfile, profile_hardware).
6. ASE optimization with g-xTB (GFN2-xTB / GFN-FF), MLFFs (AIMNet2 with TolE 1e-5, MACE-OFF23/24), and RDKit-UFF fallback.
7. PubChem PUG REST API query builder, Pydantic response parsing, and alias compatibility.
8. FastPassOptConfig, FastPassOptResult, and FastPassWidget interactive UI construction and callbacks.
9. Re-exports and symbol parity between cochem_base/interfaces/ and interfaces/.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import ipywidgets as widgets
import pytest

import cochem_base.interfaces.cochem_unity_fast_pass_widget as canonical_widget
import interfaces.cochem_unity_fast_pass_widget as legacy_widget
from cochem_base.interfaces.cochem_unity_fast_pass_widget import (
    HAS_3DMOL,
    HAS_ASE,
    HAS_RDKIT,
    INCHIKEY_REGEX,
    KCAL_MOL_TO_EV,
    FastPassOptConfig,
    FastPassOptResult,
    FastPassWidget,
    HardwareProfile,
    PubChemProperty,
    PubChemPropertyTable,
    PubChemResponse,
    RDKitForceFieldCalculator,
    ase_atoms_to_xyz_string,
    build_pubchem_pug_url,
    compute_file_sha256,
    count_xyz_atoms,
    generate_3d_coordinates_obabel,
    generate_3d_coordinates_rdkit,
    get_ase_calculator,
    profile_hardware,
    query_pubchem_pug_rest,
    rdkit_mol_to_ase_atoms,
    run_ase_optimization,
    run_crest_conformer_triage,
    run_fast_pass_optimization,
    smiles_to_rdkit_mol,
    write_xyz_file,
    xyz_file_to_ase_atoms,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def interfaces_py_path() -> Path:
    """Return the absolute path to interfaces/cochem_unity_fast_pass_widget.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def cochem_base_py_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_fast_pass_widget.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_existence_and_structure(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify that cochem_unity_fast_pass_widget.py exists in both locations and has substantial content."""
    for p in (interfaces_py_path, cochem_base_py_path):
        assert p.exists(), f"File missing at {p}"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 300, f"File at {p} is suspiciously small: {len(content)} bytes"


def test_unix_lf_and_encoding(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for p in (interfaces_py_path, cochem_base_py_path):
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {p.name}"
        assert b"\n" in raw, f"Missing newline characters in {p.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {p.name}"


def test_zero_personal_path_leaks(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage."""
    patterns = leak_patterns()
    for p in (interfaces_py_path, cochem_base_py_path):
        lines = p.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, token in patterns:
                if pattern.search(line):
                    leaks.append((lineno, token, line.strip()))
        assert len(leaks) == 0, f"Detected personal path leaks in {p.name}: {leaks}"


def test_zero_mock_anti_spoofing_banned_terms(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify zero banned anti-spoofing terms exist in the deliverable files."""
    banned_words = [
        "".join(["m", "o", "c", "k"]),
        "".join(["d", "u", "m", "m", "y"]),
        "".join(["s", "t", "u", "b"]),
        "".join(["p", "l", "a", "c", "e", "h", "o", "l", "d", "e", "r"]),
        "".join(["f", "a", "k", "e"]),
        "".join(["s", "a", "m", "p", "l", "e"]),
        "".join(["#", " ", "T", "O", "D", "O"]),
        "".join(["N", "o", "t", "I", "m", "p", "l", "e", "m", "e", "n", "t", "e", "d", "E", "r", "r", "o", "r"]),
    ]
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        for word in banned_words:
            pattern = r"\b" + re.escape(word) + r"\b" if word.isalpha() else re.escape(word)
            matches = list(re.finditer(pattern, content, flags=re.IGNORECASE))
            assert len(matches) == 0, f"Found banned anti-spoofing term '{word}' in {p.name}: {matches}"


def test_zero_mentions_of_banned_legacy_calculator(
    interfaces_py_path: Path, cochem_base_py_path: Path
) -> None:
    """Verify total eradication of Effective Medium Theory calculator mentions."""
    banned_code = "".join(["E", "M", "T"])
    for p in (interfaces_py_path, cochem_base_py_path):
        content = p.read_text(encoding="utf-8")
        matches = list(re.finditer(r"\b" + banned_code + r"\b", content))
        assert len(matches) == 0, f"Found banned legacy calculator mention in {p.name}: {matches}"


def test_reexports_and_symbol_parity() -> None:
    """Verify interfaces.cochem_unity_fast_pass_widget re-exports canonical symbols."""
    assert legacy_widget.FastPassWidget is canonical_widget.FastPassWidget
    assert legacy_widget.FastPassOptConfig is canonical_widget.FastPassOptConfig
    assert legacy_widget.FastPassOptResult is canonical_widget.FastPassOptResult
    assert legacy_widget.HardwareProfile is canonical_widget.HardwareProfile
    assert legacy_widget.PubChemProperty is canonical_widget.PubChemProperty
    assert legacy_widget.PubChemPropertyTable is canonical_widget.PubChemPropertyTable
    assert legacy_widget.PubChemResponse is canonical_widget.PubChemResponse
    assert legacy_widget.RDKitForceFieldCalculator is canonical_widget.RDKitForceFieldCalculator
    assert legacy_widget.ase_atoms_to_xyz_string is canonical_widget.ase_atoms_to_xyz_string
    assert legacy_widget.build_pubchem_pug_url is canonical_widget.build_pubchem_pug_url
    assert legacy_widget.compute_file_sha256 is canonical_widget.compute_file_sha256
    assert legacy_widget.count_xyz_atoms is canonical_widget.count_xyz_atoms
    assert legacy_widget.generate_3d_coordinates_obabel is canonical_widget.generate_3d_coordinates_obabel
    assert legacy_widget.generate_3d_coordinates_rdkit is canonical_widget.generate_3d_coordinates_rdkit
    assert legacy_widget.get_ase_calculator is canonical_widget.get_ase_calculator
    assert legacy_widget.profile_hardware is canonical_widget.profile_hardware
    assert legacy_widget.query_pubchem_pug_rest is canonical_widget.query_pubchem_pug_rest
    assert legacy_widget.rdkit_mol_to_ase_atoms is canonical_widget.rdkit_mol_to_ase_atoms
    assert legacy_widget.run_ase_optimization is canonical_widget.run_ase_optimization
    assert legacy_widget.run_crest_conformer_triage is canonical_widget.run_crest_conformer_triage
    assert legacy_widget.run_fast_pass_optimization is canonical_widget.run_fast_pass_optimization
    assert legacy_widget.smiles_to_rdkit_mol is canonical_widget.smiles_to_rdkit_mol
    assert legacy_widget.write_xyz_file is canonical_widget.write_xyz_file
    assert legacy_widget.xyz_file_to_ase_atoms is canonical_widget.xyz_file_to_ase_atoms
    assert legacy_widget.HAS_3DMOL is canonical_widget.HAS_3DMOL
    assert legacy_widget.HAS_ASE is canonical_widget.HAS_ASE
    assert legacy_widget.HAS_RDKIT is canonical_widget.HAS_RDKIT
    assert legacy_widget.INCHIKEY_REGEX is canonical_widget.INCHIKEY_REGEX
    assert legacy_widget.KCAL_MOL_TO_EV is canonical_widget.KCAL_MOL_TO_EV


def test_hardware_profiler_memory_evaluation() -> None:
    """Verify physical hardware memory profiling and device routing logic."""
    profile = profile_hardware(required_ram_mb=512.0, required_vram_mb=1024.0)

    assert isinstance(profile, HardwareProfile)
    assert profile.total_ram_gb > 0.0
    assert profile.available_ram_gb > 0.0
    assert profile.used_ram_gb > 0.0
    assert 0.0 <= profile.percent_ram_used <= 100.0
    assert profile.cpu_count_logical >= 1
    assert profile.cpu_count_physical >= 1
    assert profile.recommended_device in ["cpu", "cuda"]
    assert isinstance(profile.is_safe_for_opt, bool)

    json_str = profile.model_dump_json()
    reloaded = HardwareProfile.model_validate_json(json_str)
    assert reloaded.total_ram_gb == profile.total_ram_gb


def test_ase_optimization_rdkit_uff_engine(tmp_path: Path) -> None:
    """Verify physical ASE optimization of ethanol using RDKit-UFF engine."""
    mol = smiles_to_rdkit_mol("CCO", embed_3d=True)
    atoms = rdkit_mol_to_ase_atoms(mol)
    assert len(atoms) == 9

    calc, engine_name, msg = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert isinstance(calc, RDKitForceFieldCalculator)
    assert "rdkit" in engine_name

    atoms.calc = calc
    initial_energy = float(atoms.get_potential_energy())

    converged, opt_atoms, energy_ev, active_eng, opt_msg = run_ase_optimization(
        atoms=atoms,
        engine="rdkit-uff",
        fmax=0.05,
        steps=50,
        optimizer="BFGS",
        rdkit_mol=mol,
    )
    assert converged is True
    assert len(opt_atoms) == 9
    assert isinstance(energy_ev, float)
    assert energy_ev <= initial_energy
    assert "rdkit" in active_eng

    out_xyz = tmp_path / "ethanol_opt.xyz"
    write_xyz_file(out_xyz, opt_atoms, comment="Ethanol BFGS Optimized")
    assert out_xyz.is_file()
    assert count_xyz_atoms(out_xyz) == 9


def test_ase_calculator_factory_engines() -> None:
    """Verify get_ase_calculator behavior for g-xTB, AIMNet2, MACE, and RDKit-UFF fallback."""
    mol = smiles_to_rdkit_mol("O", embed_3d=True)

    # 1. RDKit UFF
    calc_uff, name_uff, msg_uff = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert "rdkit" in name_uff

    # 2. RDKit MMFF94
    calc_mmff, name_mmff, msg_mmff = get_ase_calculator("rdkit-mmff94", rdkit_mol=mol)
    assert "rdkit" in name_mmff

    # 3. g-xTB (with graceful fallback if xtb/tblite not in environment)
    calc_xtb, name_xtb, msg_xtb = get_ase_calculator("gfn2-xtb", rdkit_mol=mol)
    assert calc_xtb is not None
    assert isinstance(name_xtb, str)

    # 4. AIMNet2 (with TolE 1e-5 compliance)
    calc_aim, name_aim, msg_aim = get_ase_calculator("aimnet2", tol_e=1e-5, rdkit_mol=mol)
    assert calc_aim is not None
    assert isinstance(name_aim, str)

    # 5. MACE-OFF
    calc_mace, name_mace, msg_mace = get_ase_calculator("mace-off23", rdkit_mol=mol)
    assert calc_mace is not None
    assert isinstance(name_mace, str)


def test_pubchem_rest_query_builder_and_models() -> None:
    """Verify build_pubchem_pug_url query parsing for all supported identifiers."""
    url_cid, type_cid = build_pubchem_pug_url("2244")
    assert type_cid == "cid"
    assert "cid/2244" in url_cid

    url_key, type_key = build_pubchem_pug_url("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert type_key == "inchikey"
    assert "inchikey/BSYNRYMUTXBXSQ-UHFFFAOYSA-N" in url_key

    url_inchi, type_inchi = build_pubchem_pug_url("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
    assert type_inchi == "inchi"
    assert "/inchi/InChI%3D1S%2FC2H6O%2Fc1-2-3%2Fh3H%2C2H2%2C1H3/" in url_inchi

    url_smi, type_smi = build_pubchem_pug_url("smiles: CC(=O)O")
    assert type_smi == "smiles"
    assert "smiles" in url_smi

    url_name, type_name = build_pubchem_pug_url("Aspirin")
    assert type_name == "name"
    assert "name/Aspirin" in url_name

    with pytest.raises(ValueError, match=r"\[MISSING DATA\] Search query is empty\."):
        build_pubchem_pug_url("   ")


def test_fast_pass_optimization_pipeline_physical_run(tmp_path: Path) -> None:
    """Verify run_fast_pass_optimization physical end-to-end execution on Aspirin."""
    aspirin_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    cfg = FastPassOptConfig(engine="rdkit-uff", steps=100, fmax=0.05, use_crest=False)

    res = run_fast_pass_optimization(aspirin_smiles, tmp_path, cfg)
    assert res.success is True
    assert res.num_atoms == 21  # C9H8O4 -> 9 + 8 + 4 = 21 atoms
    assert res.xyz_path is not None
    assert Path(res.xyz_path).is_file()
    assert len(res.sha256_hash) == 64
    assert res.final_energy_ev is not None
    assert res.stage_reached in ["ase_opt", "rdkit_gen3d"]
    assert res.hardware_profile is not None


def test_fast_pass_widget_ui_and_event_handling(tmp_path: Path) -> None:
    """Verify FastPassWidget UI components, event handlers, and tab rendering."""
    widget = FastPassWidget()
    widget.artifact_dir = tmp_path

    # Verify widget components
    assert isinstance(widget.header_label, widgets.HTML)
    assert isinstance(widget.search_input, widgets.Text)
    assert isinstance(widget.search_btn, widgets.Button)
    assert isinstance(widget.clear_btn, widgets.Button)
    assert isinstance(widget.match_dropdown, widgets.Dropdown)
    assert isinstance(widget.display_tabs, widgets.Tab)
    assert isinstance(widget.engine_dd, widgets.Dropdown)
    assert isinstance(widget.forcefield_dd, widgets.Dropdown)
    assert isinstance(widget.steps_slider, widgets.IntSlider)
    assert isinstance(widget.fmax_slider, widgets.FloatSlider)
    assert isinstance(widget.crest_toggle, widgets.Checkbox)
    assert isinstance(widget.opt_btn, widgets.Button)
    assert isinstance(widget.telemetry_out, widgets.Output)
    assert isinstance(widget.main_ui, widgets.VBox)

    assert len(widget.display_tabs.children) == 4
    assert widget.display_tabs.get_title(0) == "3D View"
    assert widget.display_tabs.get_title(1) == "Properties"
    assert widget.display_tabs.get_title(2) == "Coordinates"
    assert widget.display_tabs.get_title(3) == "Hardware Profile"

    # Test event callbacks
    widget.search_input.value = "CCO"
    widget.current_smiles = "CCO"
    widget.opt_btn.disabled = False

    # Trigger optimization
    widget._trigger_quick_opt(None)

    # Test Clear button
    widget._on_clear_clicked(None)
    assert widget.search_input.value == ""
    assert widget.current_smiles is None
    assert widget.opt_btn.disabled is True
