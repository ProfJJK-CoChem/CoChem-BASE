"""Filesystem and server ownership boundaries of the real Codespaces launcher."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from scripts.hosted_dashboard import REPO_ROOT, runtime_environment, server_identity, start_dashboard, stop_owned_server, validate_setup


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
        validate_setup(Path(sys.executable), tmp_path)


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
