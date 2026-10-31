"""GUI scientific evidence and owned subprocess lifecycle acceptance."""

from __future__ import annotations

import base64
import json
import hashlib
from html import unescape
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import threading
import ast
import inspect
import stat
import zipfile
import io

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    # The ordinary child must already have the canonical startup shim before
    # any application/scientific import. Never manufacture missing authority.
    context = ("COCHEM_SOURCE_QUARANTINE_ROOT", "COCHEM_SOURCE_QUARANTINE_ORIGINAL",
               "COCHEM_SOURCE_QUARANTINE_EVIDENCE", "COCHEM_SOURCE_QUARANTINE_REVISION")
    if any(os.environ.get(key) for key in context):
        assert all(os.environ.get(key) for key in context)
        startup = sys.modules.get("sitecustomize")
        assert startup is not None and Path(startup.__file__).resolve() == ROOT / "ci_tools/quarantine_startup/sitecustomize.py"
        guard = sys.modules.get("ci_tools.source_quarantine")
        assert guard is not None and Path(guard.__file__).resolve() == ROOT / "ci_tools/source_quarantine.py"
        state = guard._active
        assert state is not None and state["copied"] == ROOT == Path(os.environ[context[0]]).resolve()
        assert state["original"] == Path(os.environ[context[1]]).resolve()
        assert state["revision"] == os.environ[context[3]]
    sys.path.insert(0, str(ROOT))
    from ci_tools.source_quarantine import source_paths
    assert Path(sys.modules["ci_tools.source_quarantine"].__file__).resolve() == ROOT / "ci_tools/source_quarantine.py"
    sys.path[:0] = [path for path in source_paths(ROOT) if path not in sys.path]
    import importlib.util
    assert Path(importlib.util.find_spec("ui.voila_layout.cochem_gui").origin).resolve() == ROOT / "ui/voila_layout/cochem_gui.py"
    assert Path(importlib.util.find_spec("cochem_base.config_loader").origin).resolve() == ROOT / "src/cochem_base/config_loader.py"
    assert Path(importlib.util.find_spec("cochem_base.calc.calculation_service").origin).resolve() == ROOT / "src/cochem_base/calc/calculation_service.py"

import pytest
from pydantic import ValidationError
from ci_tools.source_quarantine import source_paths

from cochem_base.config_loader import resolve_executable
from cochem_base.spectroscopy.parser import SpectroscopyTelemetryParser
from ui.voila_layout.cochem_gui import BoundedTelemetryOutput, CoChemGUI, MatrixConfigModel


WATER = "O 0 0 0\nH 0 0 0.96\nH 0.92 0 -0.24"
if __name__ == "__main__":
    import inspect
    assert Path(inspect.getfile(CoChemGUI)).resolve() == ROOT / "ui/voila_layout/cochem_gui.py"
    assert Path(inspect.getfile(resolve_executable)).resolve() == ROOT / "src/cochem_base/config_loader.py"
    from cochem_base.calc import calculation_service
    assert Path(calculation_service.__file__).resolve() == ROOT / "src/cochem_base/calc/calculation_service.py"


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
    warning = unescape(gui.dispersion_warning.value)
    assert "cannot verify the spin state for multiplicities above 1" in warning
    assert "Total charge and Spin multiplicity" in warning
    assert "choose an engine and method that support its spin state" in warning
    assert "do not change the molecule's spin just to enable the calculation" in warning
    assert gui.multiplicity_input.value == 2
    assert gui.matrix_geometry.value == WATER


def test_gui_cancellation_stops_its_actual_worker(tmp_path, audited_xtb):
    _run_physical_gui_case("cancel", tmp_path, audited_xtb)


def test_gui_executes_real_xtb_optimization(tmp_path, audited_xtb):
    _run_physical_gui_case("optimize", tmp_path, audited_xtb)


def test_gui_executes_real_xtb_single_point(tmp_path, audited_xtb):
    _run_physical_gui_case("single-point", tmp_path, audited_xtb)


def test_xtb_task_settings_in_actual_source_widget(tmp_path):
    _run_physical_gui_case("task-settings", tmp_path, tmp_path / "absent-registry.json")
    assert not list(tmp_path.rglob("result.json"))


def test_local_saved_file_controls_without_native_execution(tmp_path):
    _run_physical_gui_case("local-files", tmp_path, tmp_path / "absent-registry.json")
    assert not list(tmp_path.rglob("execution.json"))


def test_native_widget_child_proves_source_origins_without_calculation(tmp_path):
    _run_physical_gui_case("source-origin", tmp_path, tmp_path / "absent-registry.json")
    assert not list(tmp_path.rglob("result.json"))


def _run_physical_gui_case(case, directory, registry):
    environment = dict(os.environ, COCHEM_CONFIG=str(registry),
                       COCHEM_ARTIFACTS=str(directory), COCHEM_ARTIFACT_DIR=str(directory),
                       COCHEM_COMPLEXES_H5=str(directory / "complexes.h5"),
                       COCHEM_STUDENT_AUTO_SETUP="0", COCHEM_STUDENT_AUTO_REMOTE_CHECK="0",
                       PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(source_paths(ROOT)))
    completed = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), case, str(directory)],
                               env=environment, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _exercise_physical_gui_case(case, tmp_path):
    if case == "source-origin":
        # Startup and actual-import assertions at module entry already ran.
        return
    if case == "actions-export":
        _exercise_actions_export(tmp_path)
        return
    if case == "local-files":
        _exercise_local_saved_controls(tmp_path)
        return
    if case == "task-settings":
        _exercise_xtb_task_settings()
        return
    if case not in {"cancel", "optimize", "single-point"}:
        raise ValueError("Unknown physical GUI case")
    gui = CoChemGUI()
    gui.matrix_geometry.value = WATER
    gui.matrix_engine.value = "XTB"
    gui.artifact_output_path.value = str(tmp_path)
    if case == "single-point":
        gui.xtb_task.value = "single_point"
    if case == "cancel":
        config_path = gui._prepare_pipeline()
        gui._pipeline_running = True
        gui._pipeline_cancellation.set()
        gui._pipeline_thread(config_path)
        assert gui.state.system_status == "Calculation Cancelled", gui.state.error_message
        assert not gui._pipeline_running
        assert not list(tmp_path.rglob("result.json"))
        assert not gui._research_observations
        assert gui.btn_research_compare.disabled
        return
    assert not gui.btn_execute.disabled, gui.engine_warning.value
    disabled_transitions = []
    def task_busy_changed(change):
        disabled_transitions.append((change["new"], gui.xtb_task.value))
    gui.xtb_task.observe(task_busy_changed, names="disabled")
    gui._execute_pipeline(None)
    gui._pipeline_worker.join(timeout=45)
    assert not gui._pipeline_worker.is_alive()
    _finish_local_file_work(gui)
    assert gui.state.system_status == ("Single Point Finished" if case == "single-point" else "Optimization Finished"), gui.state.error_message
    assert not gui.xtb_task.disabled
    selected_task = "single_point" if case == "single-point" else "optimization"
    assert gui.xtb_task.value == selected_task
    assert disabled_transitions == [(True, selected_task), (False, selected_task)]
    executions = list(tmp_path.rglob("execution.json"))
    assert len(executions) == 1
    execution = json.loads(executions[0].read_text())
    assert execution["status"] == "EXECUTION_VERIFIED"
    published = executions[0].parent
    payload = json.loads((published / "result.json").read_text())
    assert payload["engine"] == "xtb" and payload["scope"] == "screening"
    assert payload["optimization_converged"] is (None if case == "single-point" else True)
    assert execution["operation"] == ("single_point" if case == "single-point" else "optimization")
    assert payload["energy_hartree"] < 0
    assert execution['retained_files']['available'] is True
    assert gui._viewed_local_record_id == execution['run_id']
    saved_label = "Saved calculation 1 · GFN2-xTB · " + ("Energy at supplied geometry" if case == "single-point" else "Geometry optimization")
    assert saved_label in gui.viewed_local_calculation.value
    assert tuple(gui.research_isomer_choices.options) == ((saved_label, 0),)
    gui.btn_save_local_files.click()
    _finish_local_file_work(gui)
    assert "Download calculation files (.zip)" in gui.local_files_download.value
    assert "to save it on your computer" in gui.local_files_status.value
    encoded = re.search(r"data:application/zip;base64,([^']+)", gui.local_files_download.value).group(1)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert 'shared-multi-job-telemetry-database' in manifest['excluded_scopes']
        assert all(not name.endswith('complexes.h5') for name in archive.namelist())
        for name, evidence in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == evidence['sha256']
    _exercise_fresh_saved_reopen(execution, published, saved_label)
    card = gui.calculation_result.value
    assert "Saved xTB screening result" in card
    assert "These are calculated estimates. Their accuracy for your goal has not been established." in card
    assert "how much of each is present" in card
    assert "Total charge:</b> 0" in card and "Spin multiplicity:</b> 1" in card
    assert "Calculation details and provenance" in card
    assert ("No geometry optimization was requested" in card) is (case == "single-point")
    assert ("optimizer’s stopping checks passed" in card) is (case == "optimize")
    assert "Optimization converged: False" not in card
    gui.xtb_task.value = "optimization" if case == "single-point" else "single_point"
    gui.charge_input.value = 1
    gui.multiplicity_input.value = 2
    assert gui.calculation_result.value == card
    gui._publish_completed_xtb_result(execution, published)
    assert gui.calculation_result.value == card
    status = gui.state.system_status
    gui._publish_completed_xtb_result({**execution, "operation": "unsupported"}, published)
    assert "saved result details are unavailable" in gui.calculation_result.value
    assert gui.state.system_status == status
    gui._publish_completed_xtb_result(execution, published)
    if case == "single-point":
        assert len(gui._research_observations) == 1
        assert tuple(gui.research_isomer_choices.options) == ((saved_label, 0),)
        assert gui._research_observations[0]["electronic_state"] == {"charge": 0, "multiplicity": 1}
        assert gui._research_observations[0]["minimum_verified"] is False
        return
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
    # Exactly one final calculation, not its native line-search evaluations.
    assert len(gui._research_observations) == 1
    observation = gui._research_observations[0]
    assert observation["energy_hartree"] == payload["energy_hartree"]
    assert observation["source"]["path"] == str(published / "result.json")
    assert observation["source"]["sha256"] == hashlib.sha256((published / "result.json").read_bytes()).hexdigest()
    assert observation["electronic_state"] == {"charge": payload["charge"], "multiplicity": payload["multiplicity"]}
    assert observation["method"]["basis"] is None
    assert observation["minimum_verified"] is False
    assert "Calculated structures" in gui.research_isomer_choices.description
    assert gui.btn_research_compare.description == "Compare calculated structures"
    assert tuple(gui.research_isomer_choices.options) == ((saved_label, 0),)
    gui._register_completed_local_calculation(execution, published)
    assert len(gui._research_observations) == 1
    assert gui._research_observations[0]["local_calculation_number"] == 1
    gui.research_populations.value = False
    gui.btn_research_compare.click()
    assert "Structure energy differences" in gui.research_report_output.value
    assert "Download comparison table (CSV)" in gui.research_report_download.value
    assert "population_fraction" not in gui.research_report_output.value
    status, summary = gui.state.system_status, gui.calculation_result.value
    gui._register_completed_local_calculation({**execution, "status": "REJECTED"}, published)
    assert "could not be added to calculated structures" in gui.research_report_output.value
    assert gui.state.system_status == status and gui.calculation_result.value == summary
    assert len(gui._research_observations) == 1
    gui.research_populations.value = True
    gui.btn_research_compare.click()
    assert "verified minimum" in gui.research_report_output.value
    for evaluation in evaluations:
        source = evaluation["gradient_artifact"]
        assert hashlib.sha256((published / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def _finish_local_file_work(gui):
    deadline = time.monotonic() + 30
    while gui._local_file_work_active() and time.monotonic() < deadline:
        for worker in tuple(gui._local_file_workers):
            worker.join(timeout=max(0.01, deadline - time.monotonic()))
    assert not gui._local_file_work_active(), "Actual file worker did not finish"


def _exercise_local_saved_controls(directory):
    gui = CoChemGUI()
    _finish_local_file_work(gui)
    assert len(gui._initial_library_state_models) == 15
    assert gui._initial_local_record_state_models == (gui.saved_local_calculation, gui.saved_local_status, gui.btn_refresh_saved_local)
    assert len(gui._initial_library_state_models + gui._initial_local_record_state_models) == 18
    assert gui.saved_local_calculation.value is None and gui.saved_local_calculation.index == 0
    assert gui.saved_local_calculation._view_count == 0
    assert gui.btn_reopen_saved_local.disabled and gui.btn_save_local_files.disabled
    assert not gui.btn_refresh_saved_local.disabled
    assert not gui._research_observations
    # Presentation-only options exercise real SelectMultiple semantics without
    # inventing a scientific observation or a trusted saved record.
    gui._set_student_research_choice_options([('Presentation row A', 0), ('Presentation row B', 1)])
    for chosen in ((), (1,)):
        gui.research_isomer_choices.value = chosen
        gui._set_student_research_choice_options([('Relabeled A', 0), ('Relabeled B', 1)],
                                                select_all_if_empty=False)
        assert gui.research_isomer_choices.value == chosen
        assert gui.research_isomer_choices.options == (('Relabeled A', 0), ('Relabeled B', 1))
    gui._refresh_student_research_choices()
    assert not gui.research_isomer_choices.options and not gui._research_observations
    before = (gui.matrix_geometry.value, gui.xtb_task.value, gui.charge_input.value, gui.multiplicity_input.value,
              gui.product_class_selector.value, gui.calculation_result.value, gui.state.system_status)
    from cochem_base.config_loader import get_artifact_dir
    root = get_artifact_dir()
    store = root / 'LocalCalculations'
    store.mkdir(exist_ok=True)
    # Real malformed-record catalog entries remain unavailable. These are
    # deliberately missing record files, never fabricated calculation results
    # or registered execution authority. Exercise actual async list refresh and
    # real widget choice preservation even when a row cannot be reopened.
    identifiers = ['job_' + letter * 32 for letter in ('a', 'b')]
    index = {'schema_version': 'cochem.local-calculation-index/1', 'records': {
        identifier: {'path': 'records/' + identifier + '.json', 'sha256': '0' * 64}
        for identifier in identifiers}, 'order': identifiers}
    (store / 'index.json').write_text(json.dumps(index))
    gui.btn_refresh_saved_local.click()
    _finish_local_file_work(gui)
    assert tuple(gui._saved_local_summaries) == tuple(identifiers)
    assert all(not item.available for item in gui._saved_local_summaries.values())
    assert gui.saved_local_calculation.value is None and gui.saved_local_calculation.index == 0
    gui.saved_local_calculation.value = identifiers[1]
    gui.btn_refresh_saved_local.click()
    _finish_local_file_work(gui)
    assert gui.saved_local_calculation.value == identifiers[1] and gui.saved_local_calculation.index == 2
    assert gui.btn_reopen_saved_local.disabled and not gui._research_observations
    gui.saved_local_calculation.value = None
    gui.btn_refresh_saved_local.click()
    _finish_local_file_work(gui)
    assert gui.saved_local_calculation.value is None and gui.saved_local_calculation.index == 0
    (store / 'index.json').write_text('{ genuine malformed index')
    gui.btn_refresh_saved_local.click()
    _finish_local_file_work(gui)
    assert 'unavailable' in gui.saved_local_status.value
    assert not gui._saved_local_catalog_available
    assert gui.saved_local_calculation.value is None and gui.btn_reopen_saved_local.disabled
    fresh = CoChemGUI()
    _finish_local_file_work(fresh)
    assert 'unavailable' in fresh.saved_local_status.value
    assert fresh.matrix_geometry is not None and not fresh._research_observations
    assert (gui.matrix_geometry.value, gui.xtb_task.value, gui.charge_input.value, gui.multiplicity_input.value,
            gui.product_class_selector.value, gui.calculation_result.value, gui.state.system_status) == before
    (store / 'index.json').unlink()
    # Genuine owned I/O pause: no parser/executor or availability replacement.
    watched = root / 'owned-file-worker-gate.txt'
    watched.write_bytes(b'bounded file-worker engineering control')
    paused, release = threading.Event(), threading.Event()
    main_ident = threading.get_ident()
    def pause_owned_read(event, arguments):
        if (event == 'open' and arguments[0] == str(watched)
                and threading.get_ident() != main_ident and not paused.is_set()):
            paused.set()
            assert release.wait(10), 'Owned I/O pause was not released'
    sys.addaudithook(pause_owned_read)
    def real_catalog_read():
        assert watched.read_bytes() == b'bounded file-worker engineering control'
        return gui._local_store().list_saved()
    gui._student_setup_initial_worker.join(timeout=30)
    assert not gui._student_setup_initial_worker.is_alive()
    assert gui._setup_service is not None
    try:
        gui._start_local_file_job('Reading saved calculations', real_catalog_read,
                                  gui._apply_saved_local_catalog, gui.saved_local_status)
        assert paused.wait(5), 'The actual owned worker never reached the I/O pause'
        assert gui._local_file_work_active()
        assert any(worker.is_alive() for worker in gui._local_file_workers)
        assert gui._setup_service.idle_check() is False
    finally:
        release.set()
        _finish_local_file_work(gui)
    assert not gui._local_file_work_active()
    # Both real construction sites must supply the actual-thread guard.
    tree = ast.parse(inspect.getsource(CoChemGUI))
    idle = [keyword.value for call in ast.walk(tree) if isinstance(call, ast.Call)
            for keyword in call.keywords if keyword.arg == 'idle_check']
    assert len(idle) == 2
    assert all(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == '_local_file_work_active' for node in ast.walk(predicate)) for predicate in idle)


def _exercise_fresh_saved_reopen(execution, published, saved_label):
    # Chemistry already completed above. The following new GUI must need no
    # engine installation/probe to read the known original record.
    previous = {key: os.environ.get(key) for key in ('COCHEM_CONFIG', 'XTB_CMD')}
    os.environ['COCHEM_CONFIG'] = str(published.parent / 'absent-registry.json')
    os.environ['XTB_CMD'] = str(published.parent / 'absent-native-engine')
    probes = []
    def forbid_new_science(event, arguments):
        if event == 'subprocess.Popen':
            command = arguments[1]
            allowed = [['uname', '-p'], ['wsl', '-l', '-q'],
                ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                ['git', '-C', str(ROOT), 'config', '--get', 'remote.origin.url']]
            assert command in allowed, command
            probes.append(command)
        elif event in {'os.system', 'socket.connect'}:
            raise AssertionError('Saved-result reopen cannot launch chemistry or network work')
    sys.addaudithook(forbid_new_science)
    try:
        fresh = CoChemGUI()
        _finish_local_file_work(fresh)
        assert not fresh._research_observations
        assert fresh.saved_local_calculation.value is None and fresh.saved_local_calculation.index == 0
        fresh.btn_refresh_saved_local.click()
        _finish_local_file_work(fresh)
        assert fresh.saved_local_calculation.value is None and fresh.saved_local_calculation.index == 0
        fresh.xtb_task.value = 'single_point'
        fresh.matrix_geometry.value = 'O 0 0 0\nH 0 0 1.2\nH 1 0 -.2'
        fresh.charge_input.value, fresh.multiplicity_input.value = 1, 2
        draft = (fresh.matrix_geometry.value, fresh.xtb_task.value, fresh.matrix_engine.value, fresh.matrix_method.value,
                 fresh.matrix_basis.value, fresh.charge_input.value, fresh.multiplicity_input.value, fresh.product_class_selector.value)
        status, card = fresh.state.system_status, fresh.calculation_result.value
        fresh.saved_local_calculation.value = execution['run_id']
        fresh.btn_refresh_saved_local.click()
        _finish_local_file_work(fresh)
        assert fresh.saved_local_calculation.value == execution['run_id']
        assert fresh.calculation_result.value == card and not fresh._research_observations
        fresh.btn_reopen_saved_local.click()
        _finish_local_file_work(fresh)
        assert 'Viewing a saved calculation' in fresh.saved_local_status.value
        assert fresh._viewed_local_record_id == execution['run_id']
        assert tuple(fresh.research_isomer_choices.options) == ((saved_label, 0),)
        assert fresh._research_observations[0]['source']['path'] == str(published / 'result.json')
        assert fresh._research_observations[0]['electronic_state'] == {'charge': 0, 'multiplicity': 1}
        assert fresh.state.system_status == status
        assert (fresh.matrix_geometry.value, fresh.xtb_task.value, fresh.matrix_engine.value, fresh.matrix_method.value,
                fresh.matrix_basis.value, fresh.charge_input.value, fresh.multiplicity_input.value, fresh.product_class_selector.value) == draft
        for chosen in ((), (0,)):
            fresh.research_isomer_choices.value = chosen
            fresh.btn_reopen_saved_local.click()
            _finish_local_file_work(fresh)
            assert fresh.research_isomer_choices.value == chosen
            assert len(fresh._research_observations) == 1 and fresh._research_observations[0]['label'] == saved_label
        if execution['operation'] == 'optimization':
            _exercise_reopen_snapshot_replacement(fresh, published, draft, status)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _exercise_reopen_snapshot_replacement(fresh, published, draft, status):
    # This native case owns both actual files. Retain the verified final A,
    # then replace that same path with its own real first-evaluation B. B is
    # never registered/admitted as a completed calculation.
    identifier = fresh.saved_local_calculation.value
    verified = fresh._local_store().reopen_saved(identifier)
    target = published / 'result.json'
    original, mode = target.read_bytes(), stat.S_IMODE(target.stat().st_mode)
    alternative = (published / 'evaluation-0000/result.json').read_bytes()
    assert json.loads(alternative)['energy_hartree'] != verified.observation['energy_hartree']
    from ui.voila_layout.cochem_gui import reopened_xtb_result_html
    card = reopened_xtb_result_html(verified)
    protected = [False]
    prefix = str(published) + os.sep
    def forbid_snapshot_reread(event, arguments):
        if protected[0] and event == 'open' and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = os.fsdecode(arguments[0])
            assert not path.startswith(prefix), 'Rendering a verified snapshot reread mutable result files'
    sys.addaudithook(forbid_snapshot_reread)
    try:
        target.chmod(0o600)
        target.write_bytes(alternative)
        protected[0] = True
        try:
            assert reopened_xtb_result_html(verified) == card
            fresh._publish_reopened_local_calculation(verified)
        finally:
            protected[0] = False
        assert fresh.calculation_result.value == card
        assert fresh._viewed_local_record_id == identifier
        assert fresh._research_observations[0]['energy_hartree'] == verified.observation['energy_hartree']
        assert fresh._research_observations[0]['source'] == verified.observation['source']
        details = json.loads(unescape(re.search(r'<pre>(.*?)</pre>', card, re.S).group(1)))
        assert details['final_result'] == verified.native_result
        assert details['saved_configuration'] == verified.configuration
        assert details['actual_execution'] == verified.execution_receipt
        assert details['saved_input_context'] == verified.input_context
        before = (fresh.calculation_result.value, fresh._viewed_local_record_id,
                  fresh.viewed_local_calculation.value, json.dumps(fresh._research_observations, sort_keys=True),
                  fresh.research_isomer_choices.value)
        fresh.btn_reopen_saved_local.click()
        _finish_local_file_work(fresh)
        assert 'unavailable' in fresh.saved_local_status.value
        assert (fresh.calculation_result.value, fresh._viewed_local_record_id,
                fresh.viewed_local_calculation.value, json.dumps(fresh._research_observations, sort_keys=True),
                fresh.research_isomer_choices.value) == before
        assert fresh.state.system_status == status
        assert (fresh.matrix_geometry.value, fresh.xtb_task.value, fresh.matrix_engine.value, fresh.matrix_method.value,
                fresh.matrix_basis.value, fresh.charge_input.value, fresh.multiplicity_input.value,
                fresh.product_class_selector.value) == draft
    finally:
        protected[0] = False
        target.write_bytes(original)
        target.chmod(mode)
    assert target.read_bytes() == original and stat.S_IMODE(target.stat().st_mode) == mode
    fresh.btn_reopen_saved_local.click()
    _finish_local_file_work(fresh)
    assert 'Viewing a saved calculation' in fresh.saved_local_status.value
    assert fresh.calculation_result.value == card and fresh._viewed_local_record_id == identifier
    assert len(fresh._research_observations) == 1


def _exercise_xtb_task_settings():
    from ui.voila_layout.cochem_gui import MethodologyViolationError
    gui = CoChemGUI()
    assert tuple(gui.xtb_task.options) == (
        ("Calculate energy at the current geometry", "single_point"),
        ("Optimize the geometry", "optimization"))
    assert gui.xtb_task.value == "optimization"
    assert gui.xtb_task.description == "Calculation task:"
    assert gui.xtb_task._view_count is None
    assert gui.xtb_task not in gui._initial_library_state_models
    assert len(gui._initial_library_state_models) == 15
    gui.matrix_geometry.value = WATER
    gui.matrix_engine.value = "XTB"
    state = (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
             gui.product_class_selector.value, gui.matrix_method.value, gui.matrix_basis.value)
    for task in ("single_point", "optimization", "single_point"):
        gui.xtb_task.value = task
        config = gui._collect_run_config()
        assert config["is_opt"] is (task == "optimization") and config["is_freq"] is False
        assert gui.btn_execute.description == ("Calculate energy" if task == "single_point" else "Optimize geometry")
        assert (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
                gui.product_class_selector.value, gui.matrix_method.value, gui.matrix_basis.value) == state
    for engine in ("PYSCF", "XTB"):
        gui.matrix_engine.value = engine
        assert gui.xtb_task.value == "single_point"
    gui.gh_repo_input.value = "course-organization/student-water"
    for route in ("github-actions", "hpc"):
        gui.calc_env_dropdown.value = route
        assert gui.xtb_task.value == "single_point"
        assert gui.xtb_task_controls.layout.display == ""
        assert "If your assignment calls for optimization, choose <b>Optimize the geometry</b> here" in gui.xtb_task_controls.children[1].value
        assert gui.btn_execute.disabled
        assert "selected single-point task is unsupported" in gui.engine_warning.value
        assert "submission blocked for this preserved single-point draft" in gui.guided_draft_status.value
        with pytest.raises(MethodologyViolationError, match="single-point task is unsupported"):
            gui._collect_run_config()
        preserved = (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
                     gui.product_class_selector.value, gui.matrix_method.value, gui.matrix_basis.value)
        gui.xtb_task.value = "optimization"
        assert gui.calc_env_dropdown.value == route
        recovered = gui._collect_run_config()
        assert recovered["is_opt"] is True and recovered["is_freq"] is False
        assert "single-point task is unsupported" not in gui.engine_warning.value
        assert "submission blocked" not in gui.guided_draft_status.value
        assert (gui.matrix_geometry.value, gui.charge_input.value, gui.multiplicity_input.value,
                gui.product_class_selector.value, gui.matrix_method.value, gui.matrix_basis.value) == preserved
        gui.xtb_task.value = "single_point"
        assert gui.calc_env_dropdown.value == route and gui.btn_execute.disabled
        with pytest.raises(MethodologyViolationError, match="single-point task is unsupported"):
            gui._collect_run_config()
    gui.calc_env_dropdown.value = "linux"
    assert gui.xtb_task.value == "single_point" and gui.xtb_task_controls.layout.display == ""
    assert gui._collect_run_config()["is_opt"] is False
    gui.xtb_task.value = "optimization"
    for route in ("github-actions", "hpc"):
        gui.calc_env_dropdown.value = route
        assert gui._collect_run_config()["is_opt"] is True
        assert "remote route supports optimization only" in gui.guided_draft_status.value
        assert "submission blocked" not in gui.guided_draft_status.value
    assert not gui._research_observations


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
    import ipywidgets as widgets

    gui = _classroom_gui()
    gui.gh_branch_input.value = "approved/course"
    for guide in ("GET_STARTED.md", "Student_Research_No_Code.md",
                  "GitHub_Classroom_ORCA_Setup.md", "CFOUR_Actions_Setup.md"):
        assert ("href='https://github.com/course-organization/student-water/"
                f"blob/approved%2Fcourse/.docs/{guide}'") in gui.gh_guidance.value
        assert (Path(__file__).resolve().parents[2] / ".docs" / guide).is_file()
    for obsolete in ("gh_pat_input", "gh_orca_url_input", "gh_cfour_url_input", "btn_provision_secrets"):
        assert not hasattr(gui, obsolete)
    pending, text_controls = [gui.gh_setup_box], []
    while pending:
        control = pending.pop()
        assert not isinstance(control, widgets.Password)
        if isinstance(control, (widgets.Text, widgets.Textarea)):
            text_controls.append(control)
        pending.extend(getattr(control, "children", ()))
    assert {id(control) for control in text_controls} == {
        id(gui.gh_repo_input), id(gui.gh_branch_input),
        id(gui.course_access_panel.project), id(gui.course_access_panel.controller),
        id(gui.course_access_panel.app_slug),
    }
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
    assert gui.btn_execute.description == "Optimize geometry"
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
