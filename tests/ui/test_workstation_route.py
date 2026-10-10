"""Lab-workstation route in the actual student app; each case runs in a fresh interpreter."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

WATER = "O 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043"


def _wait(predicate, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached")


def case_route_requires_an_assigned_folder(gui):
    gui.calc_env_dropdown.value = "workstation"
    assert tuple(gui.dynamic_setup_container.children) == (gui.workstation_panel,)
    assert "ORCA" in {value for _, value in gui.matrix_engine.options}
    gui.matrix_engine.value = "PYSCF"
    gui._refresh_execution_gate()
    assert gui.btn_execute.description == "Send to lab workstation"
    assert gui.btn_execute.disabled and "Assign your workstation Drive folder" in gui.engine_warning.value
    with pytest.raises(ValueError, match="lab workstation"):
        gui._build_pipeline_command()


def case_assign_folder_then_send_without_blocking(gui):
    drive = Path(os.environ["COCHEM_TEST_DRIVE"])
    drive.mkdir()
    folder = drive / "alice-workstation"
    gui.calc_env_dropdown.value = "workstation"
    panel = gui.workstation_panel
    panel.folder.value, panel.student.value, panel.cores.value = str(folder), "alice", "2"
    panel.assign()
    _wait(lambda: (folder / "cochem_workstation_folder.json").is_file() and not panel.btn_assign.disabled
          and not panel.busy)
    assert "Folder assigned" in panel.settings_status.value
    gui.matrix_engine.value = "PYSCF"
    gui.matrix_geometry.value = WATER
    gui._refresh_execution_gate()
    assert not gui.btn_execute.disabled, gui.engine_warning.value
    gui._execute_pipeline(None)
    assert not gui._pipeline_running  # submission never blocks the app
    inbox = folder / "inbox"
    _wait(lambda: any(p.is_dir() and not p.name.startswith(".") for p in inbox.iterdir()))
    job = next(p for p in inbox.iterdir() if not p.name.startswith("."))
    manifest = json.loads((job / "job.json").read_text())
    calculation = json.loads((job / "calculation.json").read_text())
    assert manifest["engine"] == "cochem_base" and manifest["resources"]["cores"] == 2
    assert manifest["student_id"] == "alice" and calculation["engine"] == "pyscf"
    assert calculation["geometry"] == WATER
    # The app reports "queued" only once the deposit has actually succeeded.
    _wait(lambda: "Queued for the lab workstation" in gui.calculation_result.value)
    assert "Lab workstation panel" in gui.calculation_result.value
    _wait(lambda: panel.history.value != "")
    assert json.loads(panel.history.value)["job_name"] == job.name
    _wait(lambda: "Queued for the lab workstation" in panel.job_status.value
          or "Waiting for the workstation to pick the job up" in panel.job_status.value)


CASES = [name.removeprefix("case_") for name in list(globals()) if name.startswith("case_")]


@pytest.mark.parametrize("case", CASES)
def test_workstation_route_in_student_app(case, tmp_path):
    environment = dict(os.environ, COCHEM_ARTIFACTS=str(tmp_path / "artifacts"),
                       COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"), COCHEM_STUDENT_AUTO_SETUP="false",
                       CODESPACES="false", COCHEM_WORKSTATION_POLL="false", COCHEM_TEST_DRIVE=str(tmp_path / "Drive"))
    for key in ("COCHEM_WORKSTATION_FOLDER", "COCHEM_WORKSTATION_STUDENT"):
        environment.pop(key, None)
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), case], env=environment,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def exercise(case: str) -> None:
    from ui.voila_layout.cochem_gui import CoChemGUI
    instance = CoChemGUI()
    for name in ("_student_setup_initial_worker", "_module_refresh_worker", "_research_capability_worker"):
        getattr(instance, name).join(timeout=10)
    try:
        globals()["case_" + case](instance)
    finally:
        instance._actions_monitor_stop.set()
        instance._cleanup_topos_search()
        instance.workstation_panel.close()


if __name__ == "__main__":
    sys.path[:0] = [str(Path(__file__).resolve().parents[2])]
    exercise(sys.argv[1])
