"""Physical verification test suite for cochem_base.interfaces.cochem_unity_fast_pass_widget.

Validates Pydantic schemas, backward compatibility aliases, widget UI layout,
hardware profiling, ASE optimization engines, PubChem response parsing, subprocess execution safety,
smart query classification, coordinate rendering, LF line endings, and zero personal path leaks.
"""

from __future__ import annotations

from pathlib import Path

import ipywidgets as widgets
import pytest

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
def widget_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_unity_fast_pass_widget.py."""
    path = (
        Path(__file__).resolve().parent.parent
        / "cochem_base"
        / "interfaces"
        / "cochem_unity_fast_pass_widget.py"
    )
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(widget_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    raw = widget_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in cochem_unity_fast_pass_widget.py"
    assert b"\n" in raw, "Missing newline characters in cochem_unity_fast_pass_widget.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in cochem_unity_fast_pass_widget.py"


def test_zero_personal_path_leaks(widget_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage."""
    lines = widget_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, token in patterns:
            if pattern.search(line):
                leaks.append((lineno, token, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks: {leaks}"


def test_hardware_profiling_and_model() -> None:
    """Verify HardwareProfile schema validation and profile_hardware physical execution."""
    profile = profile_hardware(required_ram_mb=256.0, required_vram_mb=512.0)
    assert isinstance(profile, HardwareProfile)
    assert profile.total_ram_gb > 0.0
    assert profile.available_ram_gb >= 0.0
    assert profile.cpu_count_logical >= 1
    assert profile.cpu_count_physical >= 1
    assert profile.recommended_device in ["cpu", "cuda"]
    assert isinstance(profile.has_cuda, bool)
    assert isinstance(profile.is_safe_for_opt, bool)


def test_pubchem_property_schema_and_aliases() -> None:
    """Verify PubChemProperty model parsing, fields, and backward compatibility properties."""
    prop1 = PubChemProperty(
        CID=2244,
        CanonicalSMILES="CC(=O)OC1=CC=CC=C1C(=O)O",
        IUPACName="2-acetyloxybenzoic acid",
        MolecularFormula="C9H8O4",
        MolecularWeight=180.16,
        InChIKey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        XLogP=1.2,
        TPSA=63.6,
        HeavyAtomCount=13,
        RotatableBondCount=3,
    )
    assert prop1.cid == 2244
    assert prop1.CID == 2244
    assert prop1.canonical_smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert prop1.CanonicalSMILES == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert prop1.IUPACName == "2-acetyloxybenzoic acid"
    assert prop1.MolecularFormula == "C9H8O4"
    assert prop1.MolecularWeight == 180.16
    assert prop1.InChIKey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
    assert prop1.xlogp == 1.2
    assert prop1.tpsa == 63.6
    assert prop1.heavy_atom_count == 13
    assert prop1.rotatable_bond_count == 3

    prop2 = PubChemProperty(
        CID=5743,
        IsomericSMILES="CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C",
        IUPACName="aminopyrine",
    )
    assert prop2.cid == 5743
    assert prop2.CID == 5743
    assert prop2.isomeric_smiles == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"
    assert prop2.CanonicalSMILES == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"
    assert prop2.IsomericSMILES == "CC1=C(C(=O)N(N1C)C2=CC=CC=C2)N(C)C"

    table = PubChemPropertyTable(Properties=[prop1, prop2])
    assert len(table.properties) == 2
    assert len(table.Properties) == 2
    assert isinstance(HAS_3DMOL, bool)
    assert isinstance(HAS_ASE, bool)
    assert isinstance(HAS_RDKIT, bool)


def test_pubchem_response_full_json_deserialization() -> None:
    """Verify PubChemResponse deserialization from real PubChem PUG JSON structures."""
    payload = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 2244,
                    "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "IsomericSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "IUPACName": "2-acetyloxybenzoic acid",
                    "MolecularFormula": "C9H8O4",
                    "MolecularWeight": 180.16,
                    "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                },
                {
                    "CID": 3672,
                    "CanonicalSMILES": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
                    "IUPACName": "ibuprofen",
                    "MolecularFormula": "C13H18O2",
                    "MolecularWeight": "206.28",
                },
            ]
        }
    }

    resp = PubChemResponse.model_validate(payload)
    assert len(resp.property_table.properties) == 2
    assert len(resp.PropertyTable.Properties) == 2

    p0 = resp.PropertyTable.Properties[0]
    assert p0.CID == 2244
    assert p0.CanonicalSMILES == "CC(=O)OC1=CC=CC=C1C(=O)O"
    assert p0.IUPACName == "2-acetyloxybenzoic acid"
    assert p0.InChIKey == "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"

    p1 = resp.PropertyTable.Properties[1]
    assert p1.CID == 3672
    assert p1.CanonicalSMILES == "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"
    assert p1.IUPACName == "ibuprofen"


def test_fast_pass_opt_config_and_result_models() -> None:
    """Verify FastPassOptConfig and FastPassOptResult validation and defaults."""
    cfg = FastPassOptConfig()
    assert cfg.engine == "gfn2-xtb"
    assert cfg.forcefield == "MMFF94"
    assert cfg.steps == 500
    assert cfg.fmax == 0.05
    assert cfg.tol_e == 1e-5
    assert cfg.use_crest is True
    assert "--gfn2" in cfg.crest_args
    assert cfg.timeout_obabel == 120.0
    assert cfg.timeout_crest == 600.0
    assert cfg.device == "auto"
    assert cfg.optimizer == "BFGS"

    custom_cfg = FastPassOptConfig(engine="aimnet2", forcefield="UFF", steps=1000, fmax=0.01, use_crest=False)
    assert custom_cfg.engine == "aimnet2"
    assert custom_cfg.forcefield == "UFF"
    assert custom_cfg.steps == 1000
    assert custom_cfg.fmax == 0.01
    assert custom_cfg.use_crest is False

    res = FastPassOptResult(
        success=True,
        smiles="CC(=O)O",
        formula="C2H4O2",
        xyz_path="/tmp/input.xyz",
        sha256_hash="abcdef1234567890",
        num_atoms=8,
        duration_seconds=1.25,
        message="Success",
        stage_reached="done",
        final_energy_ev=-12.345,
        engine_used="rdkit-uff",
    )
    assert res.success is True
    assert res.smiles == "CC(=O)O"
    assert res.num_atoms == 8
    assert res.stage_reached == "done"
    assert res.final_energy_ev == -12.345
    assert res.engine_used == "rdkit-uff"


def test_build_pubchem_pug_url_classification() -> None:
    """Verify build_pubchem_pug_url correctly identifies query types."""
    url1, qtype1 = build_pubchem_pug_url("2244")
    assert qtype1 == "cid"
    assert "/cid/2244/" in url1

    url2, qtype2 = build_pubchem_pug_url("CID: 3672")
    assert qtype2 == "cid"
    assert "/cid/3672/" in url2

    url2b, qtype2b = build_pubchem_pug_url("cid=5743")
    assert qtype2b == "cid"
    assert "/cid/5743/" in url2b

    url3, qtype3 = build_pubchem_pug_url("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert qtype3 == "inchikey"
    assert "/inchikey/BSYNRYMUTXBXSQ-UHFFFAOYSA-N/" in url3

    url4, qtype4 = build_pubchem_pug_url("InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3")
    assert qtype4 == "inchi"
    assert "/inchi/InChI%3D1S%2FC2H6O%2Fc1-2-3%2Fh3H%2C2H2%2C1H3/" in url4

    url5, qtype5 = build_pubchem_pug_url("Aspirin")
    assert qtype5 == "name"
    assert "/name/Aspirin/" in url5


def test_query_pubchem_pug_rest_empty_query() -> None:
    """Verify query_pubchem_pug_rest raises ValueError on empty or whitespace query."""
    with pytest.raises(ValueError, match=r"\[MISSING DATA\] Search query is empty\."):
        query_pubchem_pug_rest("   ")


def test_generate_3d_coordinates_rdkit_and_obabel(tmp_path: Path) -> None:
    """Verify 3D coordinate generation via RDKit and OpenBabel."""
    ok, path, atoms, mol, msg = generate_3d_coordinates_rdkit("CC(=O)O", tmp_path, forcefield="UFF", steps=100)
    assert ok is True
    assert path is not None
    assert path.is_file()
    assert atoms is not None
    assert len(atoms) == 8
    assert mol is not None

    bad_ok, bad_path, bad_atoms, bad_mol, bad_msg = generate_3d_coordinates_rdkit("   ", tmp_path)
    assert bad_ok is False
    assert bad_path is None
    assert "[MISSING DATA]" in bad_msg

    ob_ok, ob_path, ob_msg = generate_3d_coordinates_obabel("  ", tmp_path)
    assert ob_ok is False
    assert ob_path is None
    assert "[MISSING DATA]" in ob_msg


def test_run_crest_conformer_triage_missing_file(tmp_path: Path) -> None:
    """Verify run_crest_conformer_triage returns False on missing XYZ file."""
    non_existent = tmp_path / "non_existent.xyz"
    success, path, msg = run_crest_conformer_triage(non_existent, tmp_path)
    assert success is False
    assert path is None
    assert "[MISSING DATA]" in msg


def test_widget_initialization_and_ui_components() -> None:
    """Verify FastPassWidget constructs all required UI widgets and components."""
    widget = FastPassWidget()

    assert isinstance(widget.header_label, widgets.HTML)
    assert isinstance(widget.search_input, widgets.Text)
    assert isinstance(widget.search_btn, widgets.Button)
    assert isinstance(widget.clear_btn, widgets.Button)
    assert isinstance(widget.match_dropdown, widgets.Dropdown)
    assert isinstance(widget.viz_output, widgets.Output)
    assert isinstance(widget.property_card_out, widgets.Output)
    assert isinstance(widget.coord_preview_out, widgets.Output)
    assert isinstance(widget.hardware_profile_out, widgets.Output)
    assert isinstance(widget.display_tabs, widgets.Tab)
    assert isinstance(widget.engine_dd, widgets.Dropdown)
    assert isinstance(widget.forcefield_dd, widgets.Dropdown)
    assert isinstance(widget.steps_slider, widgets.IntSlider)
    assert isinstance(widget.fmax_slider, widgets.FloatSlider)
    assert isinstance(widget.crest_toggle, widgets.Checkbox)
    assert isinstance(widget.opt_btn, widgets.Button)
    assert isinstance(widget.telemetry_out, widgets.Output)
    assert isinstance(widget.main_ui, widgets.VBox)

    assert widget.search_btn.description == "Search PubChem"
    assert widget.clear_btn.description == "Clear"
    assert widget.opt_btn.description == "Fast Pass Optimize"
    assert widget.opt_btn.disabled is True
    assert widget.match_dropdown.disabled is True
    assert widget.artifact_dir.exists()


def test_widget_telemetry_logging() -> None:
    """Verify _log_telemetry emits structured outputs for all log levels."""
    widget = FastPassWidget()

    widget._log_telemetry("INFO", "Informational test log")
    widget._log_telemetry("SUCCESS", "Success test log")
    widget._log_telemetry("WARNING", "Warning test log")
    widget._log_telemetry("ERROR", "Error test log")
    widget._log_telemetry("FATAL", "Fatal test log")


def test_widget_empty_search_handling() -> None:
    """Verify empty search triggers [MISSING DATA] error telemetry."""
    widget = FastPassWidget()
    widget.search_input.value = "   "
    widget._perform_remote_search(None)
    assert widget.opt_btn.disabled is True


def test_widget_fallback_3d_rendering() -> None:
    """Verify _render_3d_molecule updates SMILES state."""
    widget = FastPassWidget()

    change_dict = {"new": "CC(=O)OC1=CC=CC=C1C(=O)O"}
    widget._render_3d_molecule(change_dict)
    assert widget.current_smiles == "CC(=O)OC1=CC=CC=C1C(=O)O"

    widget._render_3d_molecule("CC(=O)O")
    assert widget.current_smiles == "CC(=O)O"


def test_widget_clear_button_resets_state() -> None:
    """Verify _on_clear_clicked resets widget query, dropdown, and property cache."""
    widget = FastPassWidget()
    widget.search_input.value = "Aspirin"
    widget.current_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    widget.current_title = "Aspirin (CID: 2244)"
    widget.match_dropdown.disabled = False
    widget.opt_btn.disabled = False

    widget._on_clear_clicked(None)

    assert widget.search_input.value == ""
    assert widget.current_smiles is None
    assert widget.current_title is None
    assert widget.current_property is None
    assert widget.match_dropdown.disabled is True
    assert widget.opt_btn.disabled is True


def test_widget_properties_card_and_coord_rendering(tmp_path: Path) -> None:
    """Verify _render_properties_card and _render_coord_preview execute safely."""
    widget = FastPassWidget()
    prop = PubChemProperty(
        CID=2244,
        CanonicalSMILES="CC(=O)OC1=CC=CC=C1C(=O)O",
        IUPACName="2-acetyloxybenzoic acid",
        MolecularFormula="C9H8O4",
        MolecularWeight=180.16,
        InChIKey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        HeavyAtomCount=13,
        RotatableBondCount=3,
        TPSA=63.6,
        XLogP=1.2,
    )
    widget._render_properties_card(prop)
    widget._render_properties_card(None)

    xyz_file = tmp_path / "test_coords.xyz"
    xyz_file.write_text("3\nTest Molecule\nC 0.0 0.0 0.0\nO 1.2 0.0 0.0\nH -0.5 0.8 0.0\n", encoding="utf-8")
    widget._render_coord_preview(xyz_file)
    widget._render_coord_preview(tmp_path / "missing.xyz")


def test_widget_quick_opt_missing_smiles() -> None:
    """Verify _trigger_quick_opt handles missing SMILES selection cleanly."""
    widget = FastPassWidget()
    widget.current_smiles = None
    widget._trigger_quick_opt(None)
    assert widget.opt_btn.description == "Fast Pass Optimize"


def test_widget_optimization_smiles_writing(tmp_path: Path) -> None:
    """Verify _execute_optimization safely writes SMILES file to workspace and optimizes."""
    widget = FastPassWidget()
    widget.artifact_dir = tmp_path

    test_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    widget._execute_optimization(test_smiles)

    smi_file = tmp_path / "input.smi"
    assert smi_file.exists(), "input.smi was not created"
    assert smi_file.read_text(encoding="utf-8").strip() == test_smiles


def test_build_pubchem_pug_url_smiles_prefix() -> None:
    """Verify build_pubchem_pug_url correctly parses prefixed smiles queries."""
    url1, qtype1 = build_pubchem_pug_url("smiles: CC(=O)O")
    assert qtype1 == "smiles"
    assert "/smiles/" in url1

    url2, qtype2 = build_pubchem_pug_url("smiles=c1ccccc1")
    assert qtype2 == "smiles"
    assert "/smiles/" in url2


def test_compute_file_sha256_and_count_xyz_atoms(tmp_path: Path) -> None:
    """Verify compute_file_sha256 and count_xyz_atoms utility behaviors."""
    test_file = tmp_path / "probe_molecule.xyz"
    test_file.write_text("5\nProbe Header\nC 0 0 0\nH 1 0 0\nH 0 1 0\nH 0 0 1\nH -1 0 0\n", encoding="utf-8")

    sha = compute_file_sha256(test_file)
    assert len(sha) == 64
    assert sha == compute_file_sha256(test_file)

    assert compute_file_sha256(tmp_path / "missing.xyz") == ""

    assert count_xyz_atoms(test_file) == 5
    assert count_xyz_atoms(tmp_path / "missing.xyz") == 0

    bad_xyz = tmp_path / "bad.xyz"
    bad_xyz.write_text("invalid header\n", encoding="utf-8")
    assert count_xyz_atoms(bad_xyz) == 0


def test_ase_optimization_and_calculator_fallback(tmp_path: Path) -> None:
    """Verify physical execution of ASE geometry optimization with RDKit-UFF fallback."""
    mol = smiles_to_rdkit_mol("CCO")
    atoms = rdkit_mol_to_ase_atoms(mol)
    assert len(atoms) == 9

    calc, engine_name, msg = get_ase_calculator("rdkit-uff", rdkit_mol=mol)
    assert calc is not None
    assert "rdkit" in engine_name

    ok, opt_atoms, energy, active_eng, opt_msg = run_ase_optimization(
        atoms=atoms,
        engine="rdkit-uff",
        fmax=0.05,
        steps=50,
        optimizer="BFGS",
        rdkit_mol=mol,
    )
    assert ok is True
    assert len(opt_atoms) == 9
    assert isinstance(energy, float)
    assert "rdkit" in active_eng


def test_run_fast_pass_optimization_empty_and_success(tmp_path: Path) -> None:
    """Verify run_fast_pass_optimization on physical inputs and empty error handling."""
    res_empty = run_fast_pass_optimization("   ", tmp_path)
    assert res_empty.success is False
    assert res_empty.stage_reached == "failed"
    assert "[MISSING DATA]" in res_empty.message

    res_ok = run_fast_pass_optimization("CCO", tmp_path)
    assert res_ok.success is True
    assert res_ok.num_atoms == 9
    assert res_ok.xyz_path is not None
    assert Path(res_ok.xyz_path).is_file()
    assert len(res_ok.sha256_hash) == 64
    assert res_ok.hardware_profile is not None


def test_root_interface_re_exports_and_parity() -> None:
    """Verify interfaces.cochem_unity_fast_pass_widget re-exports match cochem_base."""
    import cochem_base.interfaces.cochem_unity_fast_pass_widget as base_widget
    import interfaces.cochem_unity_fast_pass_widget as root_widget

    assert root_widget.FastPassWidget is base_widget.FastPassWidget
    assert root_widget.FastPassOptConfig is base_widget.FastPassOptConfig
    assert root_widget.FastPassOptResult is base_widget.FastPassOptResult
    assert root_widget.HardwareProfile is base_widget.HardwareProfile
    assert root_widget.PubChemProperty is base_widget.PubChemProperty
    assert root_widget.PubChemPropertyTable is base_widget.PubChemPropertyTable
    assert root_widget.PubChemResponse is base_widget.PubChemResponse
    assert root_widget.RDKitForceFieldCalculator is base_widget.RDKitForceFieldCalculator
    assert root_widget.build_pubchem_pug_url is base_widget.build_pubchem_pug_url
    assert root_widget.compute_file_sha256 is base_widget.compute_file_sha256
    assert root_widget.count_xyz_atoms is base_widget.count_xyz_atoms
    assert root_widget.generate_3d_coordinates_obabel is base_widget.generate_3d_coordinates_obabel
    assert root_widget.generate_3d_coordinates_rdkit is base_widget.generate_3d_coordinates_rdkit
    assert root_widget.get_ase_calculator is base_widget.get_ase_calculator
    assert root_widget.profile_hardware is base_widget.profile_hardware
    assert root_widget.query_pubchem_pug_rest is base_widget.query_pubchem_pug_rest
    assert root_widget.rdkit_mol_to_ase_atoms is base_widget.rdkit_mol_to_ase_atoms
    assert root_widget.run_ase_optimization is base_widget.run_ase_optimization
    assert root_widget.run_crest_conformer_triage is base_widget.run_crest_conformer_triage
    assert root_widget.run_fast_pass_optimization is base_widget.run_fast_pass_optimization
    assert root_widget.smiles_to_rdkit_mol is base_widget.smiles_to_rdkit_mol
    assert root_widget.write_xyz_file is base_widget.write_xyz_file
    assert root_widget.xyz_file_to_ase_atoms is base_widget.xyz_file_to_ase_atoms
    assert root_widget.ase_atoms_to_xyz_string is base_widget.ase_atoms_to_xyz_string
    assert root_widget.HAS_3DMOL is base_widget.HAS_3DMOL
    assert root_widget.HAS_ASE is base_widget.HAS_ASE
    assert root_widget.HAS_RDKIT is base_widget.HAS_RDKIT
    assert root_widget.INCHIKEY_REGEX is base_widget.INCHIKEY_REGEX
    assert root_widget.KCAL_MOL_TO_EV is base_widget.KCAL_MOL_TO_EV
    assert root_widget.logger is base_widget.logger


def test_xyz_file_to_ase_atoms_and_3d_render(tmp_path: Path) -> None:
    """Verify xyz_file_to_ase_atoms parses valid XYZ files and handles missing files."""
    xyz_path = tmp_path / "sample.xyz"
    xyz_path.write_text("3\nWater molecule\nO 0.0 0.0 0.0\nH 0.0 0.7 0.6\nH 0.0 -0.7 0.6\n", encoding="utf-8")
    atoms = xyz_file_to_ase_atoms(xyz_path)
    assert len(atoms) == 3
    assert atoms.get_chemical_symbols() == ["O", "H", "H"]

    with pytest.raises(FileNotFoundError):
        xyz_file_to_ase_atoms(tmp_path / "missing_file.xyz")

    widget = FastPassWidget()
    widget._render_3d_xyz(xyz_path)
    widget._render_3d_xyz(tmp_path / "non_existent.xyz")


def test_root_interface_file_hygiene() -> None:
    """Verify interfaces/cochem_unity_fast_pass_widget.py encoding, LF line endings, and path leaks."""
    root_path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_unity_fast_pass_widget.py"
    assert root_path.is_file(), f"Target file does not exist: {root_path}"

    raw = root_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF line endings in interfaces/cochem_unity_fast_pass_widget.py"
    assert b"\n" in raw, "Missing newline characters in interfaces/cochem_unity_fast_pass_widget.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM in interfaces/cochem_unity_fast_pass_widget.py"

    lines = root_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, token in patterns:
            if pattern.search(line):
                leaks.append((lineno, token, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in interfaces/cochem_unity_fast_pass_widget.py: {leaks}"
