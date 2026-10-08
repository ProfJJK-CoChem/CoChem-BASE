"""Student input and transport boundaries independent of installed engines."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cochem_base.interfaces.student_research import (
    SCHEMA,
    assemble_monomers,
    build_topos_matrix_request,
    build_topos_request,
    execute_provider_request,
    required_provider_engines,
    required_provider_modules,
    student_matrix_recipes,
    validate_provider_request,
)

WATER = "3\nStudent Avogadro starting geometry; no observed energy\nO 0 0 0\nH .9572 0 0\nH -.24 .927 0\n"


def envelope():
    return {"schema_version": SCHEMA, "module": "topos", "operation": "energy",
            "artifact": "inputs/water.xyz", "artifact_sha256": hashlib.sha256(WATER.encode()).hexdigest(),
            "options": {"topos_request": build_topos_request(WATER, operation="energy", charge=0, multiplicity=1)}}


@pytest.mark.parametrize("module", ["topos", "torq"])
def test_geometric_inspection_requires_actual_module_and_does_not_invent_electronic_calculation(module):
    request = {"schema_version": SCHEMA, "module": module, "operation": "geometry_analysis",
        "artifact": "inputs/water.xyz", "artifact_sha256": hashlib.sha256(WATER.encode()).hexdigest(), "options": {}}
    assert validate_provider_request(request) == request
    assert required_provider_engines(request) == []
    assert required_provider_modules(request)[-1] == module
    request["options"] = {"charge": 0}
    with pytest.raises(ValueError, match="source geometry only"):
        validate_provider_request(request)


def test_hosted_admission_imports_without_site_packages_or_base_import_side_effects():
    source = Path(__file__).resolve().parents[2] / "src/cochem_base/interfaces/student_research.py"
    code = "import importlib.util,sys; s=importlib.util.spec_from_file_location('research',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m.SCHEMA=='cochem.student-provider/1'; assert 'numpy' not in sys.modules; assert 'pydantic' not in sys.modules"
    process = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(source)],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr


def test_original_student_file_hash_and_explicit_state_bound_to_transport():
    value = envelope()
    assert validate_provider_request(value, {"inputs/water.xyz": {"sha256": value["artifact_sha256"]}}) == value
    assert required_provider_engines(value) == ["xtb"]
    assert required_provider_modules(value) == ["torq", "topos"]
    assert value["options"]["topos_request"]["molecule"]["charge"] == 0
    with pytest.raises(ValueError, match="SHA-256 differs"):
        validate_provider_request(value, {"inputs/water.xyz": "0" * 64})


@pytest.mark.parametrize("name", ["../outside.xyz", "/outside.xyz", "inputs/../water.xyz", "inputs\\water.xyz", "./water.xyz"])
def test_upload_path_cannot_escape_bundle(name):
    value = envelope()
    value["artifact"] = name
    with pytest.raises(ValueError, match="artifact"):
        validate_provider_request(value)


@pytest.mark.parametrize("field", ["command", "executable", "shell", "COCHEM_SOURCE_CREDENTIAL", "secret"])
def test_scientific_options_cannot_execute_code_or_carry_credentials(field):
    value = envelope()
    value["options"]["topos_request"]["metadata"] = {field: "rejected before installation"}
    with pytest.raises(ValueError, match="forbidden"):
        validate_provider_request(value)


def test_missing_electronic_state_and_nonfinite_data_are_never_defaulted():
    value = envelope()
    del value["options"]["topos_request"]["molecule"]["multiplicity"]
    with pytest.raises(ValueError, match="explicit"):
        validate_provider_request(value)
    value = envelope()
    value["options"]["topos_request"]["molecule"]["coordinates"][0][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        validate_provider_request(value)


def test_provider_search_cannot_inherit_looser_upstream_deduplication_defaults():
    request = build_topos_request(WATER, operation="search", charge=0, multiplicity=1)
    assert request["rmsd_threshold_angstrom"] == .08
    assert request["dedup_rotational_threshold_fraction"] == .0005
    assert request["dedup_energy_threshold_kcal_mol"] == .05
    assert request["energy_window_kcal_mol"] == 12
    for field, value in (("rmsd_threshold_angstrom", .125), ("dedup_rotational_threshold_fraction", .01),
                         ("dedup_energy_threshold_kcal_mol", .1), ("energy_window_kcal_mol", 15)):
        with pytest.raises(ValueError, match="SRS"):
            build_topos_request(WATER, operation="search", charge=0, multiplicity=1, options={field: value})


def test_isotope_labels_and_original_source_hash_survive_student_ingestion():
    labelled = WATER.replace("O 0", "18O 0").replace("H .9572", "D .9572")
    request = build_topos_request(labelled, operation="frequency", charge=0, multiplicity=1)
    assert request["molecule"]["symbols"] == ["O", "H", "H"]
    assert request["molecule"]["isotopes"] == [18, 2, None]
    assert request["molecule"]["coordinates"] == envelope()["options"]["topos_request"]["molecule"]["coordinates"]


def test_windows_xyz_encoding_signature_preserves_uploaded_bytes_and_hash(tmp_path):
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    from cochem_base.interfaces.artifact_handoff import load_module_handoff, prepare_module_handoff

    original = ("\ufeff" + WATER).encode("utf-8")
    artifact = tmp_path / "water.xyz"
    artifact.write_bytes(original)
    request = build_topos_request(original.decode("utf-8"), operation="energy", charge=0, multiplicity=1)
    assert request["molecule"]["symbols"] == ["O", "H", "H"]
    assert parse_geometry_identity(original.decode("utf-8")).elements == ("O", "H", "H")
    handoff = tmp_path / "handoff"
    prepare_module_handoff("topos", artifact, handoff, operation="energy", options={"topos_request": request})
    loaded = load_module_handoff(handoff / "handoff.json")
    assert loaded.artifact.sha256 == hashlib.sha256(original).hexdigest()
    assert (handoff / "artifact.xyz").read_bytes() == original
    assert artifact.read_bytes() == original


def test_student_monomers_are_translated_only_and_explicitly_partitioned():
    import numpy as np

    monomers = [{"xyz": WATER, "charge": 0, "multiplicity": 1}] * 2
    result = assemble_monomers(monomers, separation_angstrom=4)
    molecule = result["molecule"]
    original = np.asarray(envelope()["options"]["topos_request"]["molecule"]["coordinates"])
    actual = np.asarray(molecule["coordinates"])
    assert molecule["fragments"] == [[0, 1, 2], [3, 4, 5]]
    assert all(state["charge"] == 0 and state["multiplicity"] == 1 for state in molecule["fragment_states"])
    for group in molecule["fragments"]:
        assert np.allclose(actual[group] - actual[group][0], original - original[0], atol=1e-15)
    assert np.allclose(actual[3:] - actual[:3], [4, 0, 0])
    assert all(item["sha256"] == hashlib.sha256(WATER.encode()).hexdigest()
               for item in result["topos_request"]["metadata"]["student_monomer_sources"])
    assert "energy_hartree" not in json.dumps(result)


def test_association_requires_fragment_electronic_states():
    value = envelope()
    value["operation"] = value["options"]["topos_request"]["purpose"] = "association"
    with pytest.raises(ValueError, match="partitions"):
        validate_provider_request(value)


def test_geometry_mismatch_rejected_before_installation_or_output(tmp_path):
    input_root = tmp_path / "input"
    (input_root / "inputs").mkdir(parents=True)
    (input_root / "inputs/water.xyz").write_text(WATER)
    value = envelope()
    value["options"]["topos_request"]["molecule"]["coordinates"][1][0] = 3
    with pytest.raises(ValueError, match="identity differs"):
        execute_provider_request(value, input_root, tmp_path / "result", root=tmp_path / "not-installed")
    assert not (tmp_path / "result").exists()


def test_resource_overrequest_rejected_before_installation_or_output(tmp_path):
    input_root = tmp_path / "input"
    (input_root / "inputs").mkdir(parents=True)
    (input_root / "inputs/water.xyz").write_text(WATER)
    with pytest.raises(ValueError, match="allocated threads"):
        execute_provider_request(envelope(), input_root, tmp_path / "result", resources={"cores": 1})
    assert not (tmp_path / "result").exists()


def test_impossible_molecular_and_fragment_spin_states_are_rejected_before_installation():
    value = envelope()
    value["options"]["topos_request"]["molecule"]["multiplicity"] = 2
    with pytest.raises(ValueError, match="parity"):
        validate_provider_request(value)
    monomers = assemble_monomers([{"xyz": WATER, "charge": 0, "multiplicity": 1}] * 2)
    value["operation"] = "association"
    value["options"]["topos_request"] = monomers["topos_request"]
    value["options"]["topos_request"]["molecule"]["fragment_states"][0]["multiplicity"] = 2
    with pytest.raises(ValueError, match="parity"):
        validate_provider_request(value)


def test_invalid_fragment_partition_cannot_be_guessed_from_coordinates():
    monomers = assemble_monomers([{"xyz": WATER, "charge": 0, "multiplicity": 1}] * 2)
    value = envelope()
    value["operation"] = "association"
    value["options"]["topos_request"] = monomers["topos_request"]
    value["options"]["topos_request"]["molecule"]["fragments"][1] = [0, 4, 5]
    with pytest.raises(ValueError, match="exactly once"):
        validate_provider_request(value)


def test_topos_crested_search_requires_both_sampling_and_refinement_engines():
    value = envelope()
    value["operation"] = value["options"]["topos_request"]["purpose"] = "search"
    value["options"]["topos_request"]["search_algorithm"] = "union"
    assert required_provider_engines(value) == ["xtb", "crest", "orca"]


def test_matrix_recipe_form_requires_actual_installed_callable_provider():
    assert student_matrix_recipes(capabilities=[]) == []
    uninstalled = [{"module_id": "topos", "status": "not_installed", "operations": ["matrix"]}]
    assert student_matrix_recipes(capabilities=uninstalled) == []
    with pytest.raises(ValueError, match="verified installed"):
        build_topos_matrix_request(WATER, row_id="T3O-10s", charge=0, multiplicity=1, capabilities=uninstalled)
    with pytest.raises(ValueError, match="exact source revision"):
        build_topos_request(WATER, operation="matrix", charge=0, multiplicity=1)


def test_orbital_form_cannot_inject_engine_input_or_omit_state():
    value = {"schema_version": SCHEMA, "module": "torq", "operation": "nbo_analysis",
             "artifact": "inputs/water.xyz", "artifact_sha256": hashlib.sha256(WATER.encode()).hexdigest(),
             "options": {"engine": "orca", "method": {"name": "HF", "basis": "STO-3G"},
                         "charge": 0, "multiplicity": 1, "cores": 1, "memory_mb": 512}}
    assert required_provider_engines(value) == ["orca"]
    value["options"]["method"]["name"] = "HF\n%output"
    with pytest.raises(ValueError, match="method and basis"):
        validate_provider_request(value)
    value["options"]["method"]["name"] = "HF"
    del value["options"]["multiplicity"]
    with pytest.raises(ValueError, match="complete typed"):
        validate_provider_request(value)


def test_timed_out_provider_controller_and_real_descendant_are_stopped(tmp_path):
    import psutil

    from cochem_base.interfaces.module_execution import _run_adapter

    pid_file = tmp_path / "child.pid"
    script = ("import subprocess,sys,pathlib,time; "
              "child=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)']); "
              "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); child.wait()")
    with (tmp_path / "controller.log").open("w") as log:
        with pytest.raises(subprocess.TimeoutExpired):
            _run_adapter([sys.executable, "-I", "-c", script, str(pid_file)], tmp_path, log, 1)
    assert pid_file.is_file()
    try:
        child = psutil.Process(int(pid_file.read_text()))
    except psutil.NoSuchProcess:
        return
    assert child.status() == psutil.STATUS_ZOMBIE  # terminated, no execution remains


def test_user_cancellation_stops_owned_provider_and_real_descendant(tmp_path):
    from threading import Event, Timer

    import psutil

    from cochem_base.interfaces.module_execution import ModuleOperationCancelled, _run_adapter

    pid_file = tmp_path / "child.pid"
    script = ("import subprocess,sys,pathlib; "
              "child=subprocess.Popen([sys.executable,'-I','-c','import time; time.sleep(60)']); "
              "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); child.wait()")
    event = Event()
    timer = Timer(1, event.set)
    timer.start()
    try:
        with (tmp_path / "controller.log").open("w") as log:
            with pytest.raises(ModuleOperationCancelled, match="cancelled"):
                _run_adapter([sys.executable, "-I", "-c", script, str(pid_file)], tmp_path, log, 30, cancel_event=event)
    finally:
        timer.cancel()
        timer.join()
    assert pid_file.is_file()
    try:
        child = psutil.Process(int(pid_file.read_text()))
    except psutil.NoSuchProcess:
        return
    assert child.status() == psutil.STATUS_ZOMBIE
