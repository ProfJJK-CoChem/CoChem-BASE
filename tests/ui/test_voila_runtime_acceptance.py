"""GUI scientific evidence and owned subprocess lifecycle acceptance."""

from __future__ import annotations

import base64
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from cochem_base.config_loader import resolve_executable
from cochem_base.spectroscopy.parser import SpectroscopyTelemetryParser
from ui.voila_layout.cochem_gui import BoundedTelemetryOutput, CoChemGUI, MatrixConfigModel


WATER = "O 0 0 0\nH 0 0 0.96\nH 0.92 0 -0.24"


@pytest.fixture
def audited_xtb(tmp_path):
    """Sign the executable actually tested, using measured host resources."""
    executable = shutil.which(resolve_executable("xtb", env_var="XTB_CMD"))
    if executable is None:
        pytest.skip("A native xTB executable is required for physical GUI acceptance")
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
    from cochem_base.core.cochem_core_registry_manager import save_system_config
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    config.hardware.maxcore_mb = 64
    executable = Path(executable).resolve()
    with executable.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    config.engines = {"xtb": EngineInfo(status="found", path=str(executable), hash=digest)}
    registry = tmp_path / "cochem_system_config.json"
    save_system_config(config.model_dump(mode="json"), registry)
    return registry


def test_inspector_preserves_absent_corrections_and_dipoles():
    result = SpectroscopyTelemetryParser().parse_log_content(
        "Rotational constants in MHz:\nA = 60778.520 B = 10318.060 C = 8820.610\n"
    )
    assert result.a_e == 60778.520
    assert result.delta_a_vib is None
    assert result.a_0 is None and result.b_0 is None and result.c_0 is None
    assert result.total_dipole is None and result.dipole_components is None


def test_inspector_rejects_reordered_axes():
    with pytest.raises(ValueError, match="axis labels"):
        SpectroscopyTelemetryParser().parse_log_content(
            "Rotational constants in MHz:\nA = 10 B = 20 C = 5\n"
        )


def test_telemetry_retains_only_last_thousand_lines():
    output = BoundedTelemetryOutput()
    output.append_stdout("".join(f"line {i}\n" for i in range(1500)))
    text = output.outputs[0]["text"]
    assert len(text.splitlines()) == 1000
    assert text.startswith("line 500\n") and text.endswith("line 1499\n")
    output.clear_output()
    assert output.outputs == ()


def test_gui_and_cli_config_reject_unimplemented_operations():
    with pytest.raises(ValidationError, match="Extra inputs"):
        MatrixConfigModel(geometry=WATER, engine="xtb", torq_resolution=36)


def test_gui_xtb_serialization_and_invalid_spin():
    gui = CoChemGUI()
    gui.matrix_geometry.value = WATER
    gui.matrix_engine.value = "XTB"
    config = gui._collect_run_config()
    assert config["engine"] == "xtb" and config["method"] == "GFN2-xTB"
    assert config["product_class"] is None and config["implicit_solvation"] is None
    gui.multiplicity_input.value = 2
    assert gui.btn_execute.disabled
    assert "Open-shell" in gui.dispersion_warning.value


def test_gui_cancellation_stops_its_actual_worker(tmp_path, audited_xtb):
    _run_physical_gui_case("cancel", tmp_path, audited_xtb)


def test_gui_executes_real_xtb_optimization(tmp_path, audited_xtb):
    _run_physical_gui_case("optimize", tmp_path, audited_xtb)


def _run_physical_gui_case(case, directory, registry):
    environment = dict(os.environ, COCHEM_CONFIG=str(registry),
                       COCHEM_COMPLEXES_H5=str(directory / "complexes.h5"))
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), case, str(directory)],
                               env=environment, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _exercise_physical_gui_case(case, tmp_path):
    if case == "actions-export":
        _exercise_actions_export(tmp_path)
        return
    if case not in {"cancel", "optimize"}:
        raise ValueError("Unknown physical GUI case")
    gui = CoChemGUI()
    gui.matrix_geometry.value = WATER
    gui.matrix_engine.value = "XTB"
    gui.artifact_output_path.value = str(tmp_path)
    if case == "cancel":
        config_path = gui._prepare_pipeline()
        gui._pipeline_running = True
        gui._pipeline_cancellation.set()
        gui._pipeline_thread(config_path)
        assert gui.state.system_status == "Calculation Cancelled", gui.state.error_message
        assert not gui._pipeline_running
        assert not list(tmp_path.rglob("result.json"))
        return
    assert not gui.btn_execute.disabled, gui.engine_warning.value
    gui._execute_pipeline(None)
    gui._pipeline_worker.join(timeout=45)
    assert not gui._pipeline_worker.is_alive()
    assert gui.state.system_status == "Optimization Finished", gui.state.error_message
    executions = list(tmp_path.rglob("execution.json"))
    assert len(executions) == 1
    execution = json.loads(executions[0].read_text())
    assert execution["status"] == "EXECUTION_VERIFIED"
    published = executions[0].parent
    payload = json.loads((published / "result.json").read_text())
    assert payload["engine"] == "xtb" and payload["scope"] == "screening"
    assert payload["optimization_converged"] is True
    assert payload["energy_hartree"] < 0
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    import numpy as np

    records = read_scientific_results(payload["telemetry_job_id"], store_path=payload["telemetry_path"])
    evaluations = [row["gradient_source"] for row in records["metadata"] if "gradient_source" in row]
    assert len(evaluations) >= 2
    assert len(evaluations) == payload["optimization_evidence"]["evaluations"]
    assert len(records["gradients_hartree_per_bohr"]) == len(evaluations) + 1
    assert np.isfinite(records["gradients_hartree_per_bohr"]).all()
    assert np.allclose(records["coordinates_angstrom"][-1], payload["coordinates_angstrom"], atol=1e-12, rtol=0)
    assert abs(records["energy_hartree"][-1] - payload["energy_hartree"]) < 1e-10
    for evaluation in evaluations:
        source = evaluation["gradient_artifact"]
        assert hashlib.sha256((published / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def test_pyscf_gui_configuration_is_a_single_point_and_rejects_open_shell():
    gui = CoChemGUI()
    gui.matrix_geometry.value = WATER
    gui.matrix_engine.value = "PYSCF"
    config = gui._collect_run_config()
    assert config['engine'] == 'pyscf' and config['method'] == 'HF'
    assert config['basis_set'] == 'STO-3G'
    assert config['is_opt'] is False and config['is_freq'] is False
    assert config['product_class'] is None
    gui.multiplicity_input.value = 2
    assert gui.btn_execute.disabled
    assert 'singlet' in gui.dispersion_warning.value


def _classroom_gui():
    gui = CoChemGUI()
    gui.calc_env_dropdown.value = "github-actions"
    gui.gh_repo_input.value = "course-organization/student-water"
    gui.matrix_geometry.value = WATER
    gui.product_class_selector.value = "Screening (no product accuracy claim)"
    gui.matrix_engine.value = "XTB"
    gui.project_name.value = "water homework"
    return gui


def test_actions_exports_portable_job_without_local_authority(tmp_path):
    environment = dict(os.environ, COCHEM_CONFIG=str(tmp_path / "missing-registry.json"))
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "actions-export", str(tmp_path)],
        env=environment, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _exercise_actions_export(tmp_path):
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry
    from cochem_base.calc.xtb_execution import validate_xtb_config

    with pytest.raises((ValueError, RuntimeError, OSError)):
        authorize_engine_execution("orca", cores=1)
    gui = _classroom_gui()
    gui.artifact_output_path.value = str(tmp_path / "local-results")
    assert not gui.btn_execute.disabled
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    gui._save_matrix_config(None)
    encoded = re.search(r"data:application/json;base64,([^']+)", gui.actions_job_download.value).group(1)
    contents = base64.b64decode(encoded)
    config = CalculationMatrixConfig.model_validate_json(contents)
    validate_xtb_config(config, parse_run_geometry(config.geometry)[0])
    assert config.engine == "xtb" and config.method == "GFN2-xTB" and config.basis_set == "built-in"
    assert config.geometry == WATER and config.is_opt and not config.is_freq
    assert config.timeout_seconds == 300 and config.product_class is None
    assert gui._last_actions_job["job_file"] == "jobs/water_homework-xtb-job.json"
    assert gui._last_actions_job["sha256"] == hashlib.sha256(contents).hexdigest()
    assert not gui._pipeline_running and not hasattr(gui, "_pipeline_worker")
    assert not (tmp_path / "local-results").exists()
    assert "No calculation has been submitted or run" in gui.actions_job_download.value
    assert 'Select <b>Run on GitHub Actions</b>' in gui.actions_job_download.value
    assert 'Upload this file' not in gui.actions_job_download.value
    gui.matrix_geometry.value = "invalid geometry"
    assert gui._last_actions_job is None and gui.actions_job_download.value == ""
    assert gui.btn_execute.disabled


def test_actions_guidance_has_course_links_and_no_secret_widgets():
    gui = _classroom_gui()
    gui.gh_branch_input.value = "approved/course"
    assert ("course-organization/student-water/blob/approved%2Fcourse/"
            ".docs/Student_Research_No_Code.md#start-your-workspace") in gui.gh_guidance.value
    for anchor in ("instructor-setup", "troubleshooting"):
        assert ("course-organization/student-water/blob/approved%2Fcourse/"
                f".docs/GitHub_Classroom_ORCA_Setup.md#{anchor}") in gui.gh_guidance.value
    for obsolete in ("gh_pat_input", "gh_orca_url_input", "gh_cfour_url_input", "btn_provision_secrets"):
        assert not hasattr(gui, obsolete)
    assert "Students do not enter tokens" in gui.gh_guidance.value
    assert gui.run_install_btn.description == "Review Actions setup"
    assert not gui.run_install_btn.disabled
    gui._run_installation(None)
    assert gui.state.system_status == "Actions setup instructions"
    assert not gui._installation_running


def test_actions_dependent_scientific_inputs_require_genuine_uploads():
    gui = _classroom_gui()
    gui.cb_recipe_r2.value = True
    with pytest.raises(ValueError, match='Upload the genuine'):
        gui._selected_scientific_input()
    gui.cb_recipe_r2.value = False
    gui.scientific_initial_hessian.value = 'READ'
    with pytest.raises(ValueError, match='Upload the genuine'):
        gui._selected_scientific_input()
    assert not gui._pipeline_running and not gui._actions_running


def test_actions_selection_never_falls_back_to_local_engine(tmp_path):
    gui = _classroom_gui()
    gui.matrix_engine.value = "XTB"
    gui.artifact_output_path.value = str(tmp_path / "local-results")
    assert not gui.btn_execute.disabled
    assert gui.btn_execute.description == "Run on GitHub Actions"
    gui.gh_repo_input.value = "invalid-course-repository"
    gui._execute_pipeline(None)
    assert "repository" in gui.state.error_message
    assert not gui._pipeline_running and not (tmp_path / "local-results").exists()
    gui._execute_periodic_pipeline(None)
    gui._start_topos_search(None)
    gui._on_slurm_submit(None)
    assert "Select HPC" in gui.slurm_status_output.value
    assert gui.calc_env_dropdown.value == "github-actions"
    assert not (tmp_path / "local-results").exists()
    assert not gui._pipeline_running and not gui._topos_running
    with pytest.raises(ValueError, match="GitHub Actions"):
        gui._build_pipeline_command()
    gui.calc_env_dropdown.value = "linux"
    assert gui.btn_execute.description == "Run xTB optimization"
    assert gui.actions_job_options.layout.display == "none"


def test_actions_rejects_more_than_fifty_atoms():
    gui = _classroom_gui()
    gui.cb_recipe_r1.value = False
    gui.matrix_geometry.value = "\n".join(f"He {index * 3} 0 0" for index in range(51))
    gui._prepare_actions_job()
    assert gui._last_actions_job is None
    assert "50 atoms" in gui.state.error_message


if __name__ == "__main__":
    _exercise_physical_gui_case(sys.argv[1], Path(sys.argv[2]))
