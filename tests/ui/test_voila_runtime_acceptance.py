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
    results = list(tmp_path.rglob("result.json"))
    assert len(results) == 1
    payload = json.loads(results[0].read_text())
    assert payload["engine"] == "xtb" and payload["scope"] == "screening"
    assert payload["optimization_converged"] is True
    assert payload["energy_hartree"] < 0


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
    gui.matrix_tier.value = "T2"
    gui.matrix_method.value = "HF/STO-3G"
    gui.matrix_basis.value = "STO-3G"
    gui.matrix_solvation.value = None
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
    from cochem_base.calc.calculation_service import CalculationMatrixConfig
    from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
    from cochem_base.calc.calculation_service import parse_run_geometry
    from cochem_base.interfaces.actions_jobs import validate_configuration

    with pytest.raises((ValueError, RuntimeError, OSError)):
        authorize_engine_execution("orca", cores=1)
    gui = _classroom_gui()
    gui.artifact_output_path.value = str(tmp_path / "local-results")
    assert not gui.btn_execute.disabled
    gui._execute_pipeline(None)
    encoded = re.search(r"data:application/json;base64,([^']+)", gui.actions_job_download.value).group(1)
    contents = base64.b64decode(encoded)
    config = CalculationMatrixConfig.model_validate_json(contents)
    assert config.engine == "orca" and config.method == "HF" and config.basis_set == "STO-3G"
    assert config.geometry == WATER and not config.is_opt and not config.is_freq
    assert config.timeout_seconds == 300
    assert config.grid_stage == 2
    assert gui._last_actions_job["job_file"] == "jobs/water_homework-orca-job.json"
    assert gui._last_actions_job["sha256"] == hashlib.sha256(contents).hexdigest()
    assert gui.state.system_status == "Actions job prepared"
    assert not gui._pipeline_running and not hasattr(gui, "_pipeline_worker")
    assert not (tmp_path / "local-results").exists()
    assert "No calculation has been submitted or run" in gui.actions_job_download.value
    assert "course-organization/student-water/actions/workflows/orca_calculation.yml" in gui.actions_job_download.value
    for operation, optimize, frequencies in (("optimization", True, False),
                                             ("harmonic_frequencies", False, True),
                                             ("optimization_frequencies", True, True)):
        gui.actions_operation.value = operation
        assert gui._last_actions_job is None and gui.actions_job_download.value == ""
        gui._save_matrix_config(None)
        assert gui._last_actions_job["config"]["is_opt"] is optimize
        assert gui._last_actions_job["config"]["is_freq"] is frequencies
        assert json.loads(gui.live_preview.value)["is_freq"] is frequencies
        encoded = re.search(r"data:application/json;base64,([^']+)", gui.actions_job_download.value).group(1)
        payload = base64.b64decode(encoded)
        exported = validate_configuration(payload, gui._last_actions_job["config"])
        elements, coordinates = parse_run_geometry(exported.geometry)
        policy = MoleculeInput(
            basin_id="export-boundary", elements=elements, coordinates=coordinates,
            theory_level=f"{exported.method} {exported.basis_set}",
            is_opt=exported.is_opt, is_freq=exported.is_freq, grid_stage=exported.grid_stage,
        )
        assert policy.resolved_grid() == ("DEFGRID3" if frequencies else "DEFGRID2")
    gui.matrix_geometry.value = "invalid geometry"
    assert gui._last_actions_job is None and gui.actions_job_download.value == ""
    assert gui.btn_execute.disabled


def test_actions_guidance_has_course_links_and_no_secret_widgets():
    gui = _classroom_gui()
    gui.gh_branch_input.value = "approved/course"
    for anchor in ("student-quick-start", "instructor-setup", "troubleshooting"):
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


@pytest.mark.parametrize("external", ["r2", "t9"])
def test_actions_rejects_source_host_dependencies(external):
    gui = _classroom_gui()
    if external == "r2":
        gui.cb_recipe_r2.value = True
    else:
        gui.t9_config_path.value = "/nonexistent/source-only-checkpoint.json"
    gui._execute_pipeline(None)
    assert gui._last_actions_job is None
    assert "self-contained" in gui.state.error_message
    assert not gui._pipeline_running


def test_actions_selection_never_falls_back_to_local_engine(tmp_path):
    gui = _classroom_gui()
    gui.matrix_engine.value = "XTB"
    gui.artifact_output_path.value = str(tmp_path / "local-results")
    assert gui.btn_execute.disabled
    assert gui.btn_execute.description == "Prepare GitHub Actions job"
    gui._execute_pipeline(None)
    assert "ORCA or CFOUR jobs only" in gui.state.error_message
    assert not gui._pipeline_running and not (tmp_path / "local-results").exists()
    gui._execute_periodic_pipeline(None)
    gui._start_topos_search(None)
    gui._on_slurm_submit(None)
    assert "GitHub Actions is selected" in gui.slurm_status_output.value
    assert not gui._pipeline_running and not gui._topos_running
    with pytest.raises(ValueError, match="Actions job JSON"):
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
