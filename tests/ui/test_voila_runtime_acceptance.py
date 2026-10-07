"""GUI scientific evidence and owned subprocess lifecycle acceptance."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
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


if __name__ == "__main__":
    _exercise_physical_gui_case(sys.argv[1], Path(sys.argv[2]))
