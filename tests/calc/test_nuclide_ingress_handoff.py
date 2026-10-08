"""Real Mendeleev, input bytes and measured Hessians exercise nuclide ingress."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry, parse_run_geometry_identity
from cochem_base.calc.molecular_input import build_molecular_input
from cochem_base.interfaces.artifact_handoff import load_module_handoff, prepare_module_handoff
from cochem_base.interfaces.scientific_jobs import load_calculation_handoff, prepare_calculation_handoff
from cochem_base.physics.eckart_aligner import align_coordinates, compute_center_of_mass
from cochem_base.physics.isotopes import get_isotope_mass


@pytest.mark.parametrize("label", ["13C", "C-13", "C13"])
def test_isotope_xyz_aliases_keep_exact_mass_and_canonical_electronic_symbol(label):
    geometry = f"2\nIsotope input\n{label} 0 0 0\nD 0 0 1.1\n"
    identity = parse_run_geometry_identity(geometry)
    assert identity.nuclides == ("13C", "2H")
    assert identity.elements == ("C", "H")
    assert identity.mass_numbers == (13, 2)
    assert identity.masses_u == (get_isotope_mass("C", 13), get_isotope_mass("H", 2))
    assert parse_run_geometry(geometry) == (["C", "H"], [(0., 0., 0.), (0., 0., 1.1)])


def test_tritium_needs_measured_mass_without_requiring_natural_abundance():
    identity = parse_run_geometry_identity("T 0 0 0\nH 0 0 .74")
    assert identity.nuclides == ("3H", "H")
    assert identity.masses_u[0] == get_isotope_mass("H", 3)


@pytest.mark.parametrize("label", ["0C", "C-0", "999C", "Gh", "X", "C-13-1", "13C:input", "13C;"])
def test_unknown_nonphysical_and_injected_nuclear_labels_are_rejected(label):
    with pytest.raises(ValueError):
        parse_run_geometry_identity(f"{label} 0 0 0")


def test_eckart_uses_assigned_nuclear_masses_and_preserves_bond_length():
    identity = parse_run_geometry_identity("H 8 3 -1\nD 8 3 -.26")
    coords = np.asarray(identity.coordinates_angstrom)
    aligned, rotation, _ = align_coordinates(coords, coords, symbols=identity.nuclides)
    assert np.linalg.norm(compute_center_of_mass(aligned, symbols=identity.nuclides)) < 1e-12
    assert np.linalg.norm(aligned[1] - aligned[0]) == pytest.approx(.74, abs=1e-13)
    assert np.linalg.det(rotation) == pytest.approx(1.)
    # A proton and a deuteron cannot be centered using equal element masses.
    assert np.linalg.norm(aligned.mean(axis=0)) > .1


def test_molecular_electronic_contract_retains_nuclides_without_changing_charge():
    config = CalculationMatrixConfig(geometry="D 0 0 0\nH 0 0 .74", method="HF", basis_set="STO-3G", is_opt=False)
    molecule = build_molecular_input(config)
    assert molecule.elements == ["H", "H"] and molecule.nuclides == ["2H", "H"]
    assert molecule.charge == 0 and molecule.multiplicity == 1
    with pytest.raises(ValueError, match="ordered electronic elements"):
        molecule.model_validate({**molecule.model_dump(), "nuclides": ["13C", "H"]})


def test_pyscf_input_keeps_nuclear_assignment_separate_from_canonical_atom_specification(tmp_path):
    from cochem_base.calc.cochem_calc_input_generator import generate_pyscf_input
    config = CalculationMatrixConfig(geometry="D 0 0 0\nH 0 0 .74", engine="pyscf", method="HF", basis_set="STO-3G", is_opt=False)
    deck = generate_pyscf_input(build_molecular_input(config), output_dir=tmp_path)
    namespace = {}
    # Parse the two generated JSON constants as syntax; executing the deck is a
    # separate native acceptance task and cannot be inferred from this check.
    import ast
    for node in ast.parse(deck.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "loads":
            namespace[node.targets[0].id] = json.loads(ast.literal_eval(node.value.args[0]))
    assert [atom[0] for atom in namespace["specification"]["atom"]] == ["H", "H"]
    assert namespace["nuclear_identity"]["nuclides"] == ["2H", "H"]


def test_module_handoff_retains_nuclide_metadata_and_rejects_erased_assignment(tmp_path):
    source = tmp_path / "isotope.xyz"
    source.write_text("2\nHD\nD 0 0 0\nH 0 0 .74\n")
    target = tmp_path / "package"
    prepared = prepare_module_handoff("torq", source, target, operation="harmonic_isotopologue")
    assert prepared.artifact.metadata["symbols"] == ["H", "H"]
    assert prepared.artifact.metadata["nuclides"] == ["2H", "H"]
    loaded = load_module_handoff(target / "handoff.json")
    assert loaded == prepared
    manifest = json.loads((target / "handoff.json").read_text())
    manifest["artifact"]["metadata"]["nuclides"] = ["H", "H"]
    (target / "handoff.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="metadata disagrees"):
        load_module_handoff(target / "handoff.json")


def test_scientific_job_handoff_cannot_substitute_element_only_geometry(tmp_path):
    geometry = "2\nHD\nD 0 0 0\nH 0 0 .74\n"
    config = CalculationMatrixConfig(geometry=geometry, engine="cfour", method="HF", basis_set="STO-3G", is_opt=False, is_vpt2=True)
    source = tmp_path / "geometry.xyz"
    source.write_text(geometry.replace("D 0", "H 0"))
    with pytest.raises(ValueError, match="exactly match"):
        prepare_calculation_handoff(config, source, tmp_path / "lost-isotope")
    source.write_text(geometry.replace("D 0", "H-2 0"))
    target = tmp_path / "bound-isotope"
    prepare_calculation_handoff(config, source, target)
    request = load_calculation_handoff(target / "handoff.json")
    assert parse_run_geometry_identity(request.calculation_config["geometry"]).nuclides == ("2H", "H")


def test_upload_and_multiframe_ingestion_validate_nuclides_and_empty_comments():
    from cochem_base.intake.cochem_mint_ingestor import validate_xyz_content
    from cochem_base.intake.cochem_stage2_ingestor import get_atomic_mass, parse_xyz_text
    text = "2\n\nD 0 0 0\nH 0 0 .74\n\n2\nHD reversed\nH 0 0 0\nH-2 0 0 .74\n"
    frames = parse_xyz_text(text)
    assert [frame["symbols"] for frame in frames] == [["2H", "H"], ["H", "2H"]]
    assert frames[0]["elements"] == ["H", "H"]
    assert get_atomic_mass("D") == get_isotope_mass("H", 2)
    assert validate_xyz_content("2\n\nD 0 0 0\nH 0 0 .74\n")[0]
    assert not validate_xyz_content("2\nInvalid\n999H 0 0 0\nH 0 0 .74\n")[0]


def test_real_rdkit_smiles_isotopes_survive_xyz_ingress():
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from cochem_base.geometry.nuclide_geometry import rdkit_geometry_xyz
    molecule = Chem.AddHs(Chem.MolFromSmiles("[13CH3][2H]"))
    assert AllChem.EmbedMolecule(molecule, randomSeed=42) == 0
    identity = parse_run_geometry_identity(rdkit_geometry_xyz(molecule))
    assert identity.nuclides[:2] == ("13C", "2H")
    assert identity.elements == ("C", "H", "H", "H", "H")
    assert identity.masses_u[0] == get_isotope_mass("C", 13)


def test_assigned_nuclides_and_default_principal_masses_remain_distinct_in_swmr(tmp_path):
    from cochem_base.core_engine.scientific_telemetry import append_scientific_result, read_scientific_results
    from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
    archive = tmp_path / "isotope-telemetry.h5"
    append_scientific_result("hd", ["D", "H"], [[0, 0, 0], [0, 0, .74]], -1.,
                             metadata={"scope": "test input transport; no quantum accuracy claim"}, store_path=archive)
    read = read_scientific_results("hd", store_path=archive)
    assert read["elements"] == ["H", "H"] and read["nuclides"] == ["2H", "H"]
    assert list(read["selected_isotope_masses_u"]) == [get_nuclide_mass("2H"), get_nuclide_mass("H")]
    assert list(read["principal_isotope_masses_u"]) == [get_nuclide_mass("H")] * 2
    assert read["nuclear_identity"]["mass_numbers"] == [2, None]


def test_gui_explicit_parent_isotope_resets_stale_substitution():
    from ui.voila_layout.cochem_gui import CoChemGUI
    gui = CoChemGUI()
    gui.matrix_geometry.value = "H 0 0 0\nH 0 0 .74"
    gui.isotope_selectors[0].value = "2H"
    gui.matrix_geometry.value = "T 0 0 0\nH 0 0 .74"
    assert gui.isotope_selectors[0].value == "3H"
    assert gui.isotope_selectors[0].options[0] == ("Parent (3H)", "3H")
    gui._on_detect_fragments_clicked(None)
    assert "Detection failed" not in gui.fragments_output.value
    gui._on_run_isotope_reanalysis_clicked(None)
    assert "Parent (3HH)" in gui.isotope_results_table.value


def test_hungarian_rotation_can_reorder_matching_nuclides_but_cannot_exchange_h_and_d():
    from scipy.spatial.transform import Rotation
    from cochem_base.intake.cochem_stage2_ingestor import HungarianKabschAligner
    reference = np.array([[0., 0., 0.], [.96, 0., 0.], [-.32, .82, 0.]])
    rotation = Rotation.from_rotvec([.3, -.4, .2]).as_matrix()
    reordered = reference[[0, 2, 1]] @ rotation.T + [2.1, -.8, 1.3]
    aligner = HungarianKabschAligner()
    preserved = aligner.align(reordered, reference, symbols=["O", "H-2", "H"],
                              ref_symbols=["O", "H", "D"], allow_permutation=True)
    assert preserved.rmsd < 1e-12
    assert np.allclose(preserved.aligned_coords, reference, atol=1e-12, rtol=0)
    # Keeping the labels fixed while swapping the unequal O-H/O-D distances is
    # a different nuclear geometry, not an allowed exchange of equal elements.
    changed = aligner.align(reordered, reference, symbols=["O", "H", "D"],
                            ref_symbols=["O", "H", "D"], allow_permutation=True)
    assert changed.rmsd > .02


def test_chain_pending_request_keeps_isotope_assignment_in_config_and_artifact(tmp_path):
    from cochem_base.chain import Chain, Stage
    config = CalculationMatrixConfig(geometry="2\nHD\nD 0 0 0\nH 0 0 .74\n", engine="cfour", method="HF",
                                     basis_set="STO-3G", is_opt=False, is_vpt2=True)
    source = tmp_path / "HD.xyz"
    source.write_text(config.geometry)
    chain = Chain(workdir=tmp_path / "chain", orca_cmd="deliberately-uninstalled-orca")
    stage = Stage("isotope", "HF STO-3G VPT2", engine="cfour", scientific_config=config.model_dump(mode="json"))
    record = chain.run_stage(stage, source)
    request = load_calculation_handoff(record.handoff_manifest)
    assert parse_run_geometry_identity(request.calculation_config["geometry"]).nuclides == ("2H", "H")
    manifest = load_module_handoff(record.handoff_manifest)
    assert manifest.artifact.metadata["nuclides"] == ["2H", "H"]
    assert record.converged is False and record.energy_hartree is None


def test_chain_dry_electronic_deck_has_canonical_elements_and_retained_nuclear_input(tmp_path):
    from cochem_base.chain import Chain, Stage
    source = tmp_path / "HD.xyz"
    source.write_text("2\nHD\nD 0 0 0\nH 0 0 .74\n")
    chain = Chain(workdir=tmp_path / "chain", orca_cmd="deliberately-uninstalled-orca")
    record = chain.run_stage(Stage("isotope", "HF STO-3G"), source, dry_run=True)
    native = parse_run_geometry_identity((chain.workdir / "isotope_input.xyz").read_text())
    assert native.nuclides == ("H", "H")
    assert parse_run_geometry_identity(source.read_text()).nuclides == ("2H", "H")
    ingress = json.loads((chain.workdir / "isotope.ingress.json").read_text())
    assert ingress["nuclear_identity"]["nuclides"] == ["2H", "H"]
    assert record.exit_status == "DECK_GENERATED" and record.converged is False


def test_native_orca_hessian_bundle_keeps_input_isotopologue_and_original_matrix(tmp_path):
    from cochem_base.calc.orca_derivatives import accept_harmonic_hessian
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine
    native = Path(__file__).resolve().parents[1] / "data/orca_6_1_1_water_hf_sto3g"
    for name in ("water.hess", "water.out.txt", "water.xyz"):
        shutil.copyfile(native / name, tmp_path / name)
    elements, coordinates = parse_run_geometry((tmp_path / "water.xyz").read_text())
    nuclides = ["18O", "2H", "H"]
    result = accept_harmonic_hessian(tmp_path / "water.hess", tmp_path / "water.out.txt", elements,
                                   coordinates, optimized=True, nuclides=nuclides)
    artifact = load_hessian_artifact(tmp_path / result["hessian_bundle_artifact"]["filename"])
    assert artifact.symbols == tuple(nuclides)
    baseline = load_hessian_artifact(tmp_path / "water.hess")
    assert np.array_equal(artifact.hessian_hartree_bohr2, baseline.hessian_hartree_bohr2)
    direct = IsotopologueSpectroscopyEngine(nuclides, artifact.coordinates_angstrom, artifact.hessian_hartree_bohr2).compute_observables()
    assert result["harmonic_frequencies_cm1"] == direct.harmonic_frequencies_cm1
    assert result["harmonic_isotope_masses_u"] == direct.masses
    assert result["principal_isotope_masses_u"] != direct.masses
