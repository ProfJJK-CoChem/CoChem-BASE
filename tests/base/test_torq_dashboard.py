"""Actual installed Jupyter authentication and owned-process tests for TORQ."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import psutil
import pytest

from scripts import manage_modules as manager
from scripts.torq_dashboard import (
    _start_interface,
    interface_environment,
    launch_dashboard,
    managed_topos_producer,
)


def test_absent_managed_topos_producer_does_not_create_installation_or_guess_python(tmp_path):
    assert managed_topos_producer(tmp_path / "modules") is None
    assert not list(tmp_path.iterdir())


def test_present_invalid_topos_receipt_cannot_be_advertised_as_verified(tmp_path):
    root = tmp_path / "modules"
    (root / "topos").mkdir(parents=True)
    (root / "topos/installation.json").write_text('{"status":"installed"}')
    with pytest.raises((ValueError, manager.ModuleInstallationError)):
        managed_topos_producer(root)
    assert not (tmp_path / "Dashboards").exists()


def test_redirected_topos_receipt_cannot_bind_an_out_of_band_python(tmp_path):
    root = tmp_path / "modules"
    (root / "topos").mkdir(parents=True)
    other = tmp_path / "external.json"
    other.write_text('{"python_path":"/out-of-band/bin/python"}')
    (root / "topos/installation.json").symlink_to(other)
    with pytest.raises(ValueError, match="redirected"):
        managed_topos_producer(root)


def test_real_managed_topos_receipt_exposes_exact_verified_producer_without_execution(tmp_path):
    configured = os.environ.get("COCHEM_TEST_TOPOS_MODULE_ROOT")
    if not configured:
        pytest.skip("Set COCHEM_TEST_TOPOS_MODULE_ROOT to a genuinely installed sealed mandatory package root")
    root = Path(configured).absolute()
    # The checkout's pytest profile deliberately imports source modules. Sealed
    # kit authority belongs to the genuine noneditable installed controller.
    probe = """import json, pathlib, sys
from scripts import manage_modules as manager
from scripts.torq_dashboard import managed_topos_producer
if not pathlib.Path(manager.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve()):
    raise RuntimeError('Receipt verification must use installed BASE authority')
root = pathlib.Path(sys.argv[1])
genuine = manager.verify_installation('topos', manager.load_manifest()['modules']['topos'], root)
observed = managed_topos_producer(root)
print(json.dumps({'genuine': genuine, 'observed': observed,
                  'receipt_sha256': manager._digest_json(genuine)}))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(root)], cwd=tmp_path,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180, check=True,
    )
    proof = json.loads(completed.stdout)
    genuine, observed = proof["genuine"], proof["observed"]
    assert observed is not None and observed["status"] == "verified"
    assert observed["python_path"] == genuine["python_path"]
    assert observed["source_pins"] == genuine["source_pins"]
    assert observed["installation_receipt_sha256"] == proof["receipt_sha256"]


@pytest.mark.parametrize("port", [True, -1, 0, 1023, 65536, 8888.5])
def test_invalid_port_cannot_create_runtime_or_run_module(tmp_path, port):
    with pytest.raises(ValueError, match="port"):
        launch_dashboard(root=tmp_path / "modules", port=port)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("timeout", [True, -1, 0, 61, float("nan"), float("inf")])
def test_invalid_deadline_cannot_create_runtime_or_run_module(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        launch_dashboard(root=tmp_path / "modules", startup_timeout=timeout)
    assert not list(tmp_path.iterdir())


def test_missing_real_installation_receipt_blocks_launch_before_runtime(tmp_path):
    with pytest.raises((ValueError, OSError, RuntimeError)):
        launch_dashboard(root=tmp_path / "modules")
    assert not (tmp_path / "Dashboards").exists()
    assert not (tmp_path / "modules").exists()


def test_malformed_real_receipt_blocks_launch_before_source_or_module_execution(tmp_path):
    root = tmp_path / "modules"
    (root / "torq").mkdir(parents=True)
    (root / "torq/installation.json").write_text(json.dumps({"status": "installed"}))
    with pytest.raises(manager.ModuleInstallationError, match="receipt"):
        launch_dashboard(root=root)
    assert not (tmp_path / "Dashboards").exists()
    assert list((root / "torq").iterdir()) == [root / "torq/installation.json"]


def test_matching_receipt_with_missing_actual_source_cannot_launch(tmp_path):
    root = tmp_path / "modules"
    spec = manager.load_manifest()["modules"]["torq"]
    parent, _, source, environment = manager._paths("torq", spec, root)
    parent.mkdir(parents=True)
    receipt = {
        "schema_version": manager.RECEIPT_SCHEMA,
        "status": "installed",
        "module_id": "torq",
        "repository": spec["repository"],
        "revision": spec["revision"],
        "distribution": spec["distribution"],
        "manifest_spec_sha256": manager._digest_json(spec),
        "source_path": str(source),
        "python_path": str(manager._python_path(environment)),
        "adapter": spec["adapter"],
        "operations": spec["operations"],
    }
    (parent / "installation.json").write_text(json.dumps(receipt))
    with pytest.raises((manager.ModuleInstallationError, OSError, ValueError)):
        launch_dashboard(root=root)
    assert not (tmp_path / "Dashboards").exists()
    assert not source.exists() and not environment.exists()


def test_interface_environment_removes_scientific_loaders_and_asset_credentials(tmp_path):
    python = tmp_path / "separate-env/bin/python"
    inherited = {
        "PATH": "/old/licensed/bin",
        "PYTHONPATH": "/old/science",
        "LD_PRELOAD": "/old/loader",
        "COCHEM_CONFIG": "/old/registry",
        "TOPOS_CONFIG": "/old/topos",
        "ORCA_BINARY": "/old/orca",
        "CFOUR_EXECUTABLE": "/old/cfour",
        "CREST_BINARY": "/old/crest",
        "SOURCE_CREDENTIAL": "private-asset",
        "JUPYTER_TOKEN": "old-ui",
        "GH_TOKEN": "account-session",
        "GITHUB_TOKEN": "job-session",
        "COCHEM_PRIVATE_GH_AUTH": "stored-cli",
        "CODESPACES": "true",
    }
    before = dict(inherited)
    values = interface_environment(
        python,
        tmp_path,
        inherited,
        remote_repository="student/private-project",
        source_revision="a" * 40,
    )
    assert inherited == before
    for key in (
        "PYTHONPATH",
        "LD_PRELOAD",
        "COCHEM_CONFIG",
        "TOPOS_CONFIG",
        "ORCA_BINARY",
        "CFOUR_EXECUTABLE",
        "CREST_BINARY",
        "SOURCE_CREDENTIAL",
        "JUPYTER_TOKEN",
    ):
        assert key not in values
    assert values["PATH"] == str(python.parent) + os.pathsep + os.defpath
    assert values["COCHEM_PRIVATE_GH_AUTH"] == "stored-cli"
    assert values["GH_TOKEN"] == "account-session"
    assert values["COCHEM_TORQ_GITHUB_REPOSITORY"] == "student/private-project"
    assert values["COCHEM_SOURCE_COMMIT"] == "a" * 40
    assert (tmp_path / "jupyter-config/jupyter_server_config.py").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "selection",
    [
        {"remote_repository": "../outside"},
        {"remote_repository": "student/project", "remote_ref": "bad\nref"},
        {"source_revision": "main"},
        {"source_revision": "g" * 40},
        {"source_revision": 40},
        {"inherited": {"COCHEM_PRIVATE_GH_AUTH": "invalid"}},
    ],
)
def test_ambiguous_source_remote_or_auth_authority_fails_before_private_files(tmp_path, selection):
    with pytest.raises(ValueError):
        interface_environment(tmp_path / "env/bin/python", tmp_path, **selection)
    assert not list(tmp_path.iterdir())


def test_actual_installed_torq_jupyter_authenticated_notebook_and_owned_stop(tmp_path):
    configured = os.environ.get("COCHEM_TEST_TORQ_UI_PYTHON")
    if not configured:
        pytest.skip(
            "Set COCHEM_TEST_TORQ_UI_PYTHON to the actual separately installed TORQ interface interpreter."
        )
    # Keep the venv executable's pathname: resolving its symlink selects the
    # system interpreter and bypasses the environment being tested.
    python = Path(configured).absolute()
    assert python.is_file()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    unrelated = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"])
    dashboard = None
    try:
        dashboard = _start_interface(
            python,
            tmp_path / "owned-ui",
            port=port,
            startup_timeout=45,
            inherited={
                **os.environ,
                "PYTHONPATH": "/untrusted/source",
                "COCHEM_SOURCE_READ_TOKEN": "not-a-source-credential",
            },
            remote_repository="student/private-project",
        )
        parsed = urllib.parse.urlparse(dashboard.url)
        authorization = urllib.parse.parse_qs(parsed.query)["token"][0]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with pytest.raises(urllib.error.HTTPError) as denied:
            opener.open(f"http://127.0.0.1:{port}/api/status", timeout=5)
        assert denied.value.code == 403
        for route in (
            "api/status",
            "api/contents/" + parsed.path.removeprefix("/lab/tree/"),
            parsed.path.removeprefix("/"),
        ):
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/{route}",
                headers={"Authorization": "token " + authorization},
            )
            with opener.open(request, timeout=5) as response:
                assert response.status == 200
        connection = dashboard.connection_file
        assert connection is not None and connection.stat().st_mode & 0o777 == 0o600
        assert json.loads(connection.read_text())["url"] == dashboard.url
        assert authorization not in repr(dashboard)
        assert authorization not in (dashboard.output / "launch.json").read_text()
        assert authorization not in (dashboard.output / "jupyter.log").read_text()
        identity = psutil.Process(dashboard.process.pid)
        assert identity.cmdline() == dashboard.command
        assert identity.create_time() == dashboard.create_time
        assert dashboard.command[:3] == [str(python), "-m", "jupyterlab"]
        actual_command = dashboard.command
        dashboard.command = ["not-the-owned-command"]
        with pytest.raises(RuntimeError, match="ownership|identity|refusing"):
            dashboard.stop()
        assert dashboard.process.poll() is None and connection.exists()
        dashboard.command = actual_command
        dashboard.stop()
        assert dashboard.process.poll() is not None and unrelated.poll() is None
        assert not connection.exists() and dashboard.url == dashboard.public_url
        dashboard.stop()
        assert unrelated.poll() is None
    finally:
        if dashboard is not None:
            dashboard.command = (
                psutil.Process(dashboard.process.pid).cmdline()
                if dashboard.process.poll() is None
                else dashboard.command
            )
            dashboard.stop()
        unrelated.terminate()
        unrelated.wait(timeout=5)
