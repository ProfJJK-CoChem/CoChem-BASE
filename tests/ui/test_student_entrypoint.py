"""Student widget ingestion and asynchronous service-boundary regressions.

These tests exercise the actual ipywidgets upload model in fresh processes.
Hosted submission, monitoring and retrieval acceptance uses real Actions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ui.voila_layout.cochem_gui import CoChemGUI


WATER = b"3\nStudent Avogadro water; angstrom\nO 0 0 0\nH 0 0 .96\nH .92 0 -.24\n"
ISOTOPES = b"3\nStudent isotope geometry\n13C 0 0 0\nD 0 0 1.08\nT 1.08 0 0\n"




def upload(gui, raw=WATER, name="my-water.xyz"):
    gui.xyz_upload.value = ({"name": name, "type": "chemical/x-xyz", "size": len(raw),
        "content": memoryview(raw), "last_modified": datetime.now(timezone.utc)},)


def classroom(gui):
    gui.calc_env_dropdown.value = "github-actions"
    gui.gh_repo_input.value = "course/student-research"
    gui.product_class_selector.value = "Screening (no product accuracy claim)"
    gui.matrix_engine.value = "XTB"


def case_actual_ipywidgets8_upload_retains_original_and_geometry(gui):
    upload(gui)
    assert isinstance(gui.xyz_upload.value, tuple)
    assert isinstance(gui.xyz_upload.value[0]["content"], memoryview)
    assert gui.matrix_geometry.value.encode() == WATER
    record = gui._student_uploads[gui.student_geometry_choice.value]
    original = Path(record["path"])
    assert original.read_bytes() == WATER
    assert record["sha256"] == hashlib.sha256(WATER).hexdigest()
    assert record["origin"] == "student_upload"
    assert original.is_relative_to(Path(gui.module_root.value).parent)
    assert original.stat().st_mode & 0o222 == 0
    assert record["nuclides"] == ["O", "H", "H"]
    assert "SHA-256" in gui.student_upload_status.value


def case_student_upload_preserves_explicit_isotope_labels(gui):
    upload(gui, ISOTOPES, "my-isotopes.xyz")
    record = gui._student_uploads[gui.student_geometry_choice.value]
    assert record["nuclides"] == ["13C", "2H", "3H"]
    assert record["elements"] == ["C", "H", "H"]
    assert gui.matrix_geometry.value == ISOTOPES.decode()
    assert Path(record["path"]).read_bytes() == ISOTOPES


def case_malformed_upload_rejected_without_losing_valid_geometry(gui, invalid):
    upload(gui)
    selected = gui.student_geometry_choice.value
    upload(gui, invalid, "bad.xyz")
    assert gui.matrix_geometry.value.encode() == WATER
    assert gui.student_geometry_choice.value == selected
    assert len(gui._student_uploads) == 1
    assert "Rejected uploads" in gui.student_upload_status.value


def case_upload_paths_and_extensions_are_rejected(gui, name):
    upload(gui, WATER, name)
    assert not gui._student_uploads
    assert "Rejected uploads" in gui.student_upload_status.value


def case_student_states_and_complete_fragment_membership_persist(gui):
    upload(gui)
    gui.student_input_role.value = "monomer_a"
    gui.student_input_label.value = "My neutral water"
    gui.student_fragment_atoms.value = "1,2,3"
    gui._save_student_input_details()
    record = gui._student_uploads[gui.student_geometry_choice.value]
    assert record["role"] == "monomer_a" and record["fragments"] == [[0, 1, 2]]
    assert record["charge"] == 0 and record["multiplicity"] == 1
    assert json.loads(Path(record["path"]).parent.joinpath("input-manifest.json").read_text()) == record
    assert gui.student_monomer_choices.options[0][0] == "My neutral water"
    original = Path(record["path"]).read_bytes()
    gui.student_fragment_atoms.value = "1,2;2,3"
    gui._save_student_input_details()
    assert "assign every atom exactly once" in gui.student_upload_status.value
    assert record["fragments"] == [[0, 1, 2]] and Path(record["path"]).read_bytes() == original


def case_complex_seed_uses_only_student_monomers_and_keeps_originals(gui):
    upload(gui, WATER, "monomer-a.xyz")
    gui.student_input_role.value = "monomer_a"
    gui._save_student_input_details()
    first = gui.student_geometry_choice.value
    upload(gui, WATER, "monomer-b.xyz")
    gui.student_input_role.value = "monomer_b"
    gui._save_student_input_details()
    second = gui.student_geometry_choice.value
    gui.student_monomer_choices.value = (first, second)
    gui._assemble_student_monomers()
    seed = gui._student_uploads[gui.student_geometry_choice.value]
    assert seed["origin"] == "student_monomer_translation_seed" and seed["atom_count"] == 6
    assert seed["fragments"] == [[0, 1, 2], [3, 4, 5]]
    assert seed["fragment_states"] == [
        {"atom_indices": [0, 1, 2], "charge": 0, "multiplicity": 1},
        {"atom_indices": [3, 4, 5], "charge": 0, "multiplicity": 1},
    ]
    assert seed["assembly"]["separation_angstrom"] == 5.0
    assert "no calculated energy" in seed["assembly"]["scope"]
    assert Path(gui._student_uploads[first]["path"]).read_bytes() == WATER
    assert Path(gui._student_uploads[second]["path"]).read_bytes() == WATER
    assert "No energy or stable-complex claim" in gui.student_upload_status.value


def case_invalid_actions_repository_cannot_execute_local_chemistry(gui):
    upload(gui)
    classroom(gui)
    gui.gh_repo_input.value = "not-a-repository"
    gui._execute_pipeline(None)
    assert "repository" in gui.state.error_message
    assert not gui._actions_running and not gui._pipeline_running
    assert not hasattr(gui, "_pipeline_worker") and not hasattr(gui, "_actions_worker")
    assert Path(gui._student_uploads[gui.student_geometry_choice.value]["path"]).read_bytes() == WATER


def case_optional_export_remains_available_without_submitting(gui):
    upload(gui)
    classroom(gui)
    gui._save_matrix_config(None)
    assert gui._last_actions_job is not None
    assert "No calculation has been submitted or run" in gui.actions_job_download.value
    assert not hasattr(gui, "_actions_worker")


def case_setup_update_and_restart_controls_need_no_student_terminal(gui):
    assert "terminal commands" in gui.student_setup_panel.children[0].value
    assert gui.btn_setup_retry.description == "Retry setup"
    assert gui.btn_setup_updates.description == "Check for updates"
    gui._render_student_setup_status({"base": {"revision": "a" * 40, "restart_required": True},
        "modules": {}, "ready": True, "update_plan": {"status": "updates_available"}, "operation": {}})
    assert not gui.btn_setup_apply.disabled and not gui.btn_setup_restart.disabled


def case_uninstalled_research_capabilities_cannot_start_science(gui):
    upload(gui)
    gui._research_capability_observations = {}
    gui._run_student_topos()
    assert "does not support" in gui.research_status.value
    gui._run_student_torq()
    assert "does not support" in gui.research_status.value
    assert not gui._pipeline_running and not gui._actions_running
    assert gui.btn_research_nbo.disabled


def case_gui_restart_recovers_student_inputs_and_details(gui):
    upload(gui)
    gui.student_input_role.value = "monomer_a"
    gui.student_input_label.value = "My research monomer"
    gui._save_student_input_details()
    record = dict(gui._student_uploads[gui.student_geometry_choice.value])
    reopened = CoChemGUI()
    for name in ("_student_setup_initial_worker", "_module_refresh_worker", "_research_capability_worker"):
        getattr(reopened, name).join(timeout=10)
    assert reopened._student_uploads[record["id"]] == record
    assert reopened.student_input_role.value == "monomer_a"
    assert reopened.student_input_label.value == "My research monomer"
    assert reopened.matrix_geometry.value.encode() == WATER
    assert Path(record["path"]).read_bytes() == WATER


def case_corrupt_retained_input_metadata_is_rejected_on_restart(gui):
    upload(gui)
    record = gui._student_uploads[gui.student_geometry_choice.value]
    manifest = Path(record['path']).parent / 'input-manifest.json'
    corrupt = {**record, 'label': ['not a string'], 'fragments': 'malformed'}
    manifest.write_text(json.dumps(corrupt), encoding='utf-8')
    reopened = CoChemGUI()
    assert record['id'] not in reopened._student_uploads
    assert Path(record['path']).read_bytes() == WATER


def case_unverified_remote_licenses_are_omitted_and_free_request_is_portable(gui):
    upload(gui)
    classroom(gui)
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    assert gui.research_topos_engine.options == (('xTB GFN2 screening', 'xtb'),)
    assert gui.actions_operation.options == (('Geometry optimization', 'optimization'),)
    gui._prepare_actions_job()
    assert gui._last_actions_job['config']['engine'] == 'xtb'
    assert gui._last_actions_job['config']['is_opt'] is True
    assert not gui._pipeline_running and not gui._actions_running
    gui.gh_repo_input.value = 'course/other-research'
    assert gui._last_actions_job is None
    assert all(not item['provisionable'] for item in gui._remote_engine_availability.values())


def case_portable_t9_form_validates_electrons_orbitals_and_rationale(gui):
    upload(gui)
    gui.t9_enable.value = True
    gui.t9_electrons.value = 2
    gui.t9_orbitals.value = '4,5'
    gui.t9_rationale.value = 'Valence pair for this neutral singlet water geometry'
    request = gui._portable_t9_request()
    assert request['active_electrons'] == 2 and request['active_orbitals'] == [4, 5]
    assert 'python_executable' not in request and request['pyscf_version'] == '2.14.0'
    gui.t9_orbitals.value = '4,4'
    with pytest.raises(ValueError, match='distinct'):
        gui._portable_t9_request()
    gui.t9_orbitals.value = '4,5'
    gui.t9_electrons.value = 3
    with pytest.raises(ValueError, match='charge and multiplicity'):
        gui._portable_t9_request()
    gui.t9_electrons.value = 2
    gui.t9_rationale.value = ''
    with pytest.raises(ValueError, match='rationale'):
        gui._portable_t9_request()


MALFORMED = [
    b"4\nwrong count\nO 0 0 0\nH 0 0 .96\nH .92 0 -.24\n",
    b"1\nnonfinite\nH nan 0 0\n",
    b"1\nghost\nXx 0 0 0\n",
    b"1\nnot physical isotope\n999C 0 0 0\n",
    b"1\nfirst\nH 0 0 0\n1\nsecond\nH 0 0 1\n",
    b"H 0 0 0\n",
    b"1\ninvalid encoding\nH 0 0 \xff\n",
]
UNSAFE_NAMES = ["../escape.xyz", "dir/water.xyz", "dir\\water.xyz", "water.txt"]
CASES = [name.removeprefix("case_") for name in globals() if name.startswith("case_")
         and name not in {"case_malformed_upload_rejected_without_losing_valid_geometry", "case_upload_paths_and_extensions_are_rejected"}]
CASES += [f"malformed-{index}" for index in range(len(MALFORMED))]
CASES += [f"unsafe-name-{index}" for index in range(len(UNSAFE_NAMES))]


@pytest.mark.parametrize("case", CASES)
def test_actual_student_entrypoint_contract(case, tmp_path):
    environment = dict(os.environ, COCHEM_ARTIFACTS=str(tmp_path / "artifacts"),
                       COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"), COCHEM_STUDENT_AUTO_SETUP="false", CODESPACES="false")
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), case],
        env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def exercise(case):
    instance = CoChemGUI()
    for name in ("_student_setup_initial_worker", "_module_refresh_worker", "_research_capability_worker"):
        getattr(instance, name).join(timeout=10)
    try:
        if case.startswith("malformed-"):
            case_malformed_upload_rejected_without_losing_valid_geometry(instance, MALFORMED[int(case.split("-")[1])])
        elif case.startswith("unsafe-name-"):
            case_upload_paths_and_extensions_are_rejected(instance, UNSAFE_NAMES[int(case.rsplit("-", 1)[1])])
        else:
            globals()["case_" + case](instance)
    finally:
        instance._actions_monitor_stop.set()
        instance._cleanup_topos_search()


if __name__ == "__main__":
    exercise(sys.argv[1])
