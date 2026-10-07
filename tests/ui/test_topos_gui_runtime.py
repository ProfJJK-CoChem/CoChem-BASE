"""Actual CREST GUI launch, cancellation and publication; no engine substitution."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from cochem_base.cochem_core_registry_schema import CoChemSystemConfig, EngineInfo
from cochem_base.core.cochem_core_registry_manager import save_system_config
from ui.voila_layout.cochem_gui import CoChemGUI


@pytest.fixture
def crest_registry(tmp_path):
    executable = shutil.which(os.environ.get("CREST_CMD", "crest"))
    if executable is None:
        pytest.skip("Native CREST is required for conformer GUI acceptance")
    config = CoChemSystemConfig.create_default(auto_detect_hardware=True)
    binary = Path(executable).resolve()
    with binary.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    config.engines = {"crest": EngineInfo(status="found", path=str(binary), hash=digest)}
    registry = tmp_path / "registry.json"
    save_system_config(config, registry)
    return registry


def _exercise_physical_case(case, tmp_path):
    gui = CoChemGUI()
    gui.matrix_geometry.value = "O 4 5 6\nH 4.758602 5 6.504284\nH 3.241398 5 6.504284"
    gui.artifact_output_path.value = str(tmp_path)
    gui.topos_walltime.value = 1.0
    cases = {"publish": _check_publish, "cancel": _check_cancel, "open_shell": _check_open_shell}
    try:
        cases[case](gui)
    finally:
        gui._cleanup_topos_search()
        if hasattr(gui, "_topos_worker"):
            gui._topos_worker.join(timeout=10)


@pytest.mark.parametrize("case", ["publish", "cancel", "open_shell"])
def test_real_crest_gui_lifecycle(case, tmp_path, crest_registry):
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), case, str(tmp_path)],
        env=dict(os.environ, COCHEM_CONFIG=str(crest_registry), COCHEM_COMPLEXES_H5=str(tmp_path / "complexes.h5")),
        capture_output=True, text=True, timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _check_publish(gui):
    assert gui.topos_heuristic.value == "CREST_NCI"
    assert not gui.btn_topos_submit.disabled
    gui._start_topos_search()
    assert gui._topos_running, gui.topos_status.value
    gui._topos_worker.join(timeout=60)
    assert not gui._topos_worker.is_alive()
    assert "COMPLETED" in gui.topos_status.value, gui.topos_status.value
    assert not gui.btn_topos_promote.disabled
    gui._promote_topos_search()
    assert "Conformer ensemble published" in gui.topos_results.value
    promoted = gui._topos_broker.store_root / gui._topos_job_id
    assert (promoted / "conformer_ensemble.xyz").exists()
    assert (promoted / "provenance.jsonld").exists()
    assert "Download conformer ensemble" in gui.topos_results.value


def _check_cancel(gui):
    gui._start_topos_search()
    assert gui._topos_running, gui.topos_status.value
    gui._topos_cancellation.set()
    gui._topos_worker.join(timeout=15)
    assert not gui._topos_worker.is_alive()
    assert "CANCELLED" in gui.topos_status.value
    assert gui.btn_topos_promote.disabled
    assert gui._topos_broker.active_processes[gui._topos_job_id].poll() is not None


def _check_open_shell(gui):
    gui.multiplicity_input.value = 2
    gui._start_topos_search()
    assert not gui._topos_running
    assert "closed-shell" in gui.topos_status.value


if __name__ == "__main__":
    _exercise_physical_case(sys.argv[1], Path(sys.argv[2]))
