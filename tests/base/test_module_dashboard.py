"""Actual controller, HTTP and process checks; no scientific engines are replaced."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from scripts.module_dashboard import (
    ModuleDashboard,
    browser_url,
    dashboard_environment,
    launch_dashboard,
    owns_listener,
    page_ready,
)


@pytest.mark.parametrize("port", [True, -1, 0, 65536, 8501.5])
def test_invalid_port_is_rejected_before_any_installation(tmp_path, port):
    with pytest.raises(ValueError, match="port"):
        launch_dashboard(root=tmp_path, port=port)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("timeout", [True, -1, 0, float("nan"), float("inf")])
def test_invalid_deadline_is_rejected_before_any_installation(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        launch_dashboard(root=tmp_path, startup_timeout=timeout)
    assert not list(tmp_path.iterdir())


def test_missing_mandatory_kit_cannot_launch_or_create_runtime(tmp_path):
    root = tmp_path / "modules"
    with pytest.raises((ValueError, OSError, RuntimeError)):
        launch_dashboard(root=root)
    assert not root.exists()
    assert not (tmp_path / "Dashboards").exists()


def test_dashboard_bindings_preserve_account_auth_and_remove_asset_source_and_loader_overrides(tmp_path):
    runtime, output = tmp_path / "runtime", tmp_path / "interface"
    runtime.mkdir()
    output.mkdir()
    inherited = {"PATH": os.environ.get("PATH", ""), "GH_TOKEN": "account-session",
                 "GITHUB_TOKEN": "project-session", "LAB_ASSET_CREDENTIAL": "lab-session",
                 "COCHEM_SOURCE_READ_TOKEN": "source-session", "PYTHONPATH": "/another/source",
                 "LD_PRELOAD": "/another/loader", "COCHEM_BASE_ROOT": "/another/base",
                 "COCHEM_CORE_SILO": "/another/silo", "TOPOS_CONFIG": "/another/settings",
                 "TOPOS_EXECUTION_BACKEND": "development", "CODESPACES": "true"}
    before = dict(inherited)
    environment = dashboard_environment(runtime, output, inherited,
        remote_repository="student/private-project", remote_ref="reviewed", base_commit="a" * 40)
    assert inherited == before
    assert environment["GH_TOKEN"] == inherited["GH_TOKEN"]
    assert environment["GITHUB_TOKEN"] == inherited["GITHUB_TOKEN"]
    for key in ("LAB_ASSET_CREDENTIAL", "COCHEM_SOURCE_READ_TOKEN", "PYTHONPATH", "LD_PRELOAD", "COCHEM_BASE_ROOT"):
        assert key not in environment
    assert environment["COCHEM_CONFIG"] == str(runtime / "Registry/cochem_system_config.json")
    assert environment["COCHEM_CORE_SILO"] == str(runtime / "Silos/cochem_core_silo")
    assert environment["TOPOS_EXECUTION_BACKEND"] == "base"
    assert environment["TOPOS_CONFIG"] == str(output / "topos-settings.json")
    settings = json.loads(Path(environment["TOPOS_CONFIG"]).read_text())
    assert settings["remote_base_commit"] == "a" * 40
    assert settings["remote_repository"] == "student/private-project" and settings["remote_ref"] == "reviewed"
    assert settings["base_registry_path"] == environment["COCHEM_CONFIG"]
    assert settings["output_root"] == str(output / "runs")
    assert "account-session" not in json.dumps(settings)


@pytest.mark.parametrize("selection", [
    {"remote_repository": "../outside", "base_commit": "a" * 40},
    {"remote_repository": "student/private-project", "base_commit": "main"},
    {"remote_repository": "student/private-project", "base_commit": "a" * 40, "remote_ref": "bad\nref"},
])
def test_ambiguous_remote_authority_is_rejected(tmp_path, selection):
    runtime, output = tmp_path / "runtime", tmp_path / "interface"
    runtime.mkdir()
    output.mkdir()
    with pytest.raises(ValueError):
        dashboard_environment(runtime, output, {}, **selection)
    assert not list(output.iterdir())


@pytest.mark.parametrize("values,expected", [
    ({}, "http://127.0.0.1:8501"),
    ({"CODESPACE_NAME": "quiet-space-123", "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"},
     "https://quiet-space-123-8501.app.github.dev"),
    ({"CODESPACE_NAME": "<unsafe>", "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"},
     "http://127.0.0.1:8501"),
])
def test_browser_url_uses_validated_student_codespace(values, expected):
    assert browser_url(8501, values) == expected


def test_actual_streamlit_service_is_checked_and_only_owned_process_stops(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    command = [sys.executable, "-I", "-B", "-m", "streamlit", "hello",
               "--server.address", "127.0.0.1", "--server.port", str(port),
               "--server.headless", "true", "--browser.gatherUsageStats", "false"]
    with (tmp_path / "streamlit.log").open("ab") as log:
        process = subprocess.Popen(command, cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=os.name != "nt")
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    dashboard = ModuleDashboard(process, port, tmp_path, "a" * 40, command,
                                psutil.Process(process.pid).create_time(), browser_url(port, {}))
    try:
        deadline = time.monotonic() + 20
        while process.poll() is None and time.monotonic() < deadline and not page_ready(port):
            time.sleep(.1)
        assert page_ready(port), (tmp_path / "streamlit.log").read_text()
        assert owns_listener(psutil.Process(process.pid), port)
        assert not owns_listener(psutil.Process(unrelated.pid), port)
        dashboard.stop()
        assert process.poll() is not None and unrelated.poll() is None
        assert not page_ready(port)
        dashboard.stop()
        assert unrelated.poll() is None
    finally:
        dashboard.stop()
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_real_base_gui_exposes_full_interface_and_rejects_missing_installation(tmp_path):
    code = """import sys
from pathlib import Path
from ui.voila_layout.cochem_gui import CoChemGUI
gui = CoChemGUI()
try:
    assert gui.btn_module_dashboard.description == 'Open complete TOPOS interface'
    assert not gui.btn_module_dashboard.disabled
    assert gui.btn_module_dashboard_stop.disabled
    gui.module_root.value = str(Path(sys.argv[1]) / 'absent-modules')
    gui.gh_repo_input.value = ''
    gui.btn_module_dashboard.click()
    gui._module_dashboard_worker.join(timeout=20)
    assert not gui._module_dashboard_worker.is_alive()
    assert 'was not started' in gui.module_dashboard_status.value
    assert gui._module_dashboard is None and not gui.btn_module_dashboard.disabled
    assert not (Path(sys.argv[1]) / 'Dashboards').exists()
    gui.module_recipient.value = 'torq'
    assert gui.btn_module_dashboard.disabled
finally:
    gui._cleanup_module_dashboard()
    gui._cleanup_topos_search()
    gui._module_cancellation.set()
    if hasattr(gui, '_module_refresh_worker'):
        gui._module_refresh_worker.join(timeout=10)
"""
    environment = {**os.environ, "COCHEM_ARTIFACT_DIR": str(tmp_path / "artifacts"),
                   "COCHEM_CONFIG": str(tmp_path / "absent-registry.json")}
    subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], env=environment,
                   cwd=Path(__file__).resolve().parents[2], check=True, timeout=60)
