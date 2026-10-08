"""Filesystem and server ownership boundaries of the real Codespaces launcher."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.hosted_dashboard import (
    REPO_ROOT,
    runtime_environment,
    server_identity,
    start_dashboard,
    stop_owned_server,
    validate_setup,
)


def test_runtime_files_live_outside_checkout_and_environment_is_not_mutated(tmp_path):
    before = dict(os.environ)
    environment = runtime_environment(tmp_path)
    assert dict(os.environ) == before
    for variable in ("JUPYTER_DATA_DIR", "JUPYTER_RUNTIME_DIR", "JUPYTER_CONFIG_DIR", "IPYTHONDIR", "XDG_CACHE_HOME", "TMPDIR"):
        path = Path(environment[variable])
        assert path.is_dir() and path.is_relative_to(tmp_path)


def test_profile_cannot_inherit_another_registry_or_mutate_its_silos(tmp_path):
    variables = ("COCHEM_CONFIG", "COCHEM_MANIFEST_PATH", "COCHEM_CORE_SILO",
                 "COCHEM_UI_SILO", "COCHEM_CALC_SILO", "COCHEM_ML_SILO")
    environment = {**os.environ, **{name: "/unrelated/environment" for name in variables}}
    code = """
import os, sys
from pathlib import Path
from scripts.hosted_dashboard import runtime_environment
variables = ('COCHEM_CONFIG', 'COCHEM_MANIFEST_PATH', 'COCHEM_CORE_SILO',
             'COCHEM_UI_SILO', 'COCHEM_CALC_SILO', 'COCHEM_ML_SILO')
root = Path(sys.argv[1])
environment = runtime_environment(root)
for name in variables:
    assert Path(environment[name]).is_relative_to(root)
    assert os.environ[name] == '/unrelated/environment'
"""
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=environment,
                   check=True, timeout=20)


def test_missing_registry_cannot_validate_hosted_setup(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        validate_setup(Path(sys.executable), tmp_path, "local")


def test_artifact_symlink_cannot_enter_checkout(tmp_path):
    alias = tmp_path / "source-alias"
    try:
        alias.symlink_to(REPO_ROOT, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("This Windows account does not have symbolic-link privileges")
        raise
    with pytest.raises(ValueError, match="outside the source checkout"):
        runtime_environment(alias / "forbidden-artifacts")


def test_checkout_virtual_environment_is_rejected_before_install(tmp_path):
    result = subprocess.run([
        sys.executable, str(REPO_ROOT / "scripts/hosted_dashboard.py"), "setup",
        "--artifacts", str(tmp_path), "--venv", str(REPO_ROOT / ".venv"),
    ], capture_output=True, text=True, timeout=10)
    assert result.returncode == 2
    assert "must be outside the checkout" in result.stderr


def test_occupied_port_is_not_reused_as_an_unrelated_dashboard(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with pytest.raises(OSError):
            start_dashboard(Path(sys.executable), tmp_path, listener.getsockname()[1], 1)
    assert not (tmp_path / "dashboard/server.json").exists()


def test_stale_recorded_unrelated_process_does_not_block_startup_or_get_terminated(tmp_path):
    runtime_environment(tmp_path)
    record = tmp_path / "dashboard/server.json"
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            record.write_text(json.dumps({"pid": unrelated.pid, "port": port, "create_time": 1.0}), encoding="utf-8")
            # Startup gets past the unrelated PID and reaches the real port
            # ownership check. It must not report an existing dashboard.
            with pytest.raises(OSError):
                start_dashboard(Path(sys.executable), tmp_path, port, 1)
            assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_identity_requires_exact_command_and_reports_creation_time():
    import psutil

    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    process = subprocess.Popen(command)
    try:
        assert server_identity(Path(sys.executable), process.pid, command) == psutil.Process(process.pid).create_time()
        assert server_identity(Path(sys.executable), process.pid, command + ["unrelated"]) is None
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.skipif(os.name == "nt", reason="Checks the Linux Codespaces session boundary")
@pytest.mark.parametrize("parent_exits", [False, True])
def test_failed_server_cleanup_stops_its_group_and_preserves_unrelated_process(tmp_path, parent_exits):
    import psutil

    descendant_record = tmp_path / "descendant.pid"
    code = (
        "import subprocess,sys,time,pathlib; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid)); "
        + ("sys.exit(0)" if parent_exits else "time.sleep(60)")
    )
    server = subprocess.Popen([sys.executable, "-c", code, str(descendant_record)], start_new_session=True)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        deadline = time.monotonic() + 5
        while not descendant_record.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert descendant_record.exists()
        descendant = psutil.Process(int(descendant_record.read_text()))
        if parent_exits:
            server.wait(timeout=5)
        stop_owned_server(server)
        assert server.poll() is not None
        deadline = time.monotonic() + 5
        while descendant.is_running() and descendant.status() != psutil.STATUS_ZOMBIE and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not descendant.is_running() or descendant.status() == psutil.STATUS_ZOMBIE
        assert unrelated.poll() is None
    finally:
        stop_owned_server(server)
        unrelated.terminate()
        unrelated.wait(timeout=5)


@pytest.mark.parametrize("selection", ["unknown", "linux", "", "actions"])
def test_unknown_explicit_calculation_profile_is_rejected(selection, tmp_path):
    if selection == "":
        # Empty defaults are not a valid explicit CLI selection either.
        result = subprocess.run([
            sys.executable, str(REPO_ROOT / "scripts/hosted_dashboard.py"), "start",
            "--artifacts", str(tmp_path), "--calculation-environment", selection,
        ], capture_output=True, text=True, timeout=10)
        assert result.returncode == 2
        assert "invalid choice" in result.stderr
    else:
        with pytest.raises(ValueError, match="github-actions or local"):
            runtime_environment(tmp_path, selection)


def test_local_profile_retains_its_actual_registry_requirement(tmp_path):
    environment = runtime_environment(tmp_path, "local")
    assert environment["COCHEM_CALCULATION_ENVIRONMENT"] == "local"
    assert Path(environment["COCHEM_CONFIG"]) == tmp_path / "Registry" / "cochem_system_config.json"
    with pytest.raises(subprocess.CalledProcessError):
        validate_setup(Path(sys.executable), tmp_path, "local")


def test_actions_profile_points_to_absent_dedicated_authority_and_keeps_local_files(tmp_path):
    local = tmp_path / "Registry" / "cochem_system_config.json"
    local.parent.mkdir()
    local.write_text("An existing user file must remain untouched.\n")
    environment = runtime_environment(tmp_path, "github-actions")
    registry = Path(environment["COCHEM_CONFIG"])
    assert registry.is_relative_to(tmp_path / "dashboard")
    assert not registry.exists()
    assert registry != local
    assert local.read_text() == "An existing user file must remain untouched.\n"
    assert environment["COCHEM_CALCULATION_ENVIRONMENT"] == "github-actions"


def test_actions_profile_cannot_adopt_existing_or_symlinked_execution_registry(tmp_path):
    registry = tmp_path / "dashboard" / "actions-interface-no-local-registry.json"
    registry.parent.mkdir()
    registry.touch()
    with pytest.raises(ValueError, match="cannot adopt"):
        runtime_environment(tmp_path, "github-actions")
    registry.unlink()
    registry.symlink_to(tmp_path / "absent-user-target")
    with pytest.raises(ValueError, match="cannot adopt"):
        runtime_environment(tmp_path, "github-actions")
    assert registry.is_symlink()


def test_actions_runtime_drops_inherited_engine_paths_without_mutating_parent(tmp_path):
    code = """
import os, sys
from pathlib import Path
from scripts.hosted_dashboard import runtime_environment
before = dict(os.environ)
environment = runtime_environment(Path(sys.argv[1]), 'github-actions')
for name in ('XTB_CMD', 'COCHEM_XTB_BIN', 'ORCA_CMD', 'COCHEM_CFOUR_BIN'):
    assert name not in environment
assert dict(os.environ) == before
assert not Path(environment['COCHEM_CONFIG']).exists()
"""
    environment = dict(os.environ)
    for name in ("XTB_CMD", "COCHEM_XTB_BIN", "ORCA_CMD", "COCHEM_CFOUR_BIN"):
        environment[name] = "/unrelated/execution/environment"
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], env=environment,
                   check=True, timeout=20)


def test_calculation_profile_default_and_environment_selection_in_actual_process(tmp_path):
    code = """
import os
from scripts.hosted_dashboard import calculation_environment
os.environ.pop('COCHEM_CALCULATION_ENVIRONMENT', None)
assert calculation_environment() == 'local'
os.environ['COCHEM_CALCULATION_ENVIRONMENT'] = 'github-actions'
assert calculation_environment() == 'github-actions'
assert calculation_environment('local') == 'local'
"""
    subprocess.run([sys.executable, "-c", code], check=True, timeout=10)


def test_actual_owned_process_identity_binds_its_calculation_environment(tmp_path):
    environment = runtime_environment(tmp_path, "local")
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    process = subprocess.Popen(command, env=environment)
    try:
        expected = {name: environment[name] for name in (
            "COCHEM_CONFIG", "COCHEM_CALCULATION_ENVIRONMENT",
        )}
        identity = server_identity(Path(sys.executable), process.pid, command, expected)
        assert identity is not None
        assert server_identity(Path(sys.executable), process.pid, command,
                               {**expected, "COCHEM_CALCULATION_ENVIRONMENT": "github-actions"}) is None
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_actions_interface_genuinely_renders_private_panel_without_stage0(tmp_path):
    evidence = validate_setup(Path(sys.executable), tmp_path, "github-actions")
    assert evidence["status"] == "INTERFACE_READY"
    assert evidence["calculation_environment"] == "github-actions"
    assert evidence["local_execution_authority"] is False
    assert evidence["scientific_calculation_qualification"] is False
    assert evidence["widget_mime"] == "application/vnd.jupyter.widget-view+json"
    assert evidence["private_staging_panel_visible"] is True
    assert evidence["base_version"] and evidence["voila_version"]
    environment = runtime_environment(tmp_path, "github-actions")
    assert not Path(environment["COCHEM_CONFIG"]).exists()
    assert not (tmp_path / "free-engines").exists()
    assert not (tmp_path / "Registry" / "cochem_system_config.json").exists()
