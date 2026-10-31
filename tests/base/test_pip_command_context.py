"""Real verified-tool adapters; engineering fixtures, not scientific execution."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from ci_tools.source_quarantine import source_child_environment
from scripts import manage_modules as installer
from cochem_base.orchestrator.dependency_manager import DependencyManager, PipExecutionError
from tests.base.test_pinned_pip_runtime import (
    PIP_SHA256, _caller_pip, _inspect, _project, _tree,
    bare_python, offline_env, wheel,
)

ROOT = Path(__file__).resolve().parents[2]
assert Path(installer.__file__).resolve() == ROOT / "scripts/manage_modules.py"


def _private_wheel(command):
    assert command[1:3] == ["-I", "-B"]
    assert command[3].endswith(".whl/pip")
    path = Path(command[3]).parent
    assert path.is_file() and not path.is_symlink()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o400
    else:
        assert not stat.S_IMODE(path.stat().st_mode) & 0o222
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PIP_SHA256
    return path


def test_actual_context_separates_streams_and_owns_private_wheel(wheel, offline_env):
    original = dict(offline_env)
    caller = _caller_pip()
    with installer._pip_command(Path(sys.executable), ["debug"], env=offline_env,
                                wheel=wheel, timeout=30) as (command, environment, remaining):
        private = _private_wheel(command)
        assert command[0] == sys.executable
        assert "COCHEM_PINNED_PIP_WHEEL" not in environment
        assert 0 < remaining <= 30
        result = subprocess.run(command, env=environment, capture_output=True,
                                text=True, timeout=remaining, check=False)
        assert result.returncode == 0, result.stderr
        assert "pip 26.2" in result.stdout
        assert "WARNING" in result.stderr
        assert "WARNING" not in result.stdout
        assert private.is_file()
    assert not private.exists() and not private.parent.exists()
    assert offline_env == original and _caller_pip() == caller


@pytest.mark.parametrize("kind", ["missing_file", "invalid_json"])
def test_context_preserves_real_caller_body_exception(kind, wheel, offline_env, tmp_path):
    expected = FileNotFoundError if kind == "missing_file" else json.JSONDecodeError
    missing = tmp_path / "absent-caller-input.json"
    with pytest.raises(expected) as failure:
        with installer._pip_command(Path(sys.executable), ["--version"], env=offline_env,
                                    wheel=wheel, timeout=20) as (command, environment, remaining):
            private = _private_wheel(command)
            if kind == "missing_file":
                missing.read_text()
            else:
                json.loads("{not-json")
    assert not isinstance(failure.value, installer.ModuleInstallationError)
    if kind == "missing_file":
        assert failure.value.filename == str(missing)
    assert not private.exists() and not private.parent.exists()


LEGACY_CHILD = r'''
import json, os, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1]).resolve()
from ci_tools import source_quarantine
state = source_quarantine.activate_from_environment()
if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
    assert state is not None and state["copied"] == root
    shim = sys.modules.get("sitecustomize")
    assert shim is not None
    assert Path(shim.__file__).resolve() == root / "ci_tools/quarantine_startup/sitecustomize.py"
from scripts import manage_modules as installer
assert Path(installer.__file__).resolve() == root / "scripts/manage_modules.py"
assert Path(installer._run_pip.__code__.co_filename).resolve() == root / "scripts/manage_modules.py"
work = Path(sys.argv[3])
assert Path(tempfile.gettempdir()).resolve() == work.resolve()
before = sorted(str(p) for p in work.glob("cochem-pinned-pip-*"))
mode = sys.argv[4]
python = work / "absent-python" if mode == "interpreter" else Path(sys.executable)
cwd = None if mode == "interpreter" else work / "absent-cwd"
try:
    installer._run_pip(python, ["--version"], env=dict(os.environ), label="Real prelaunch refusal",
                       cwd=cwd, wheel=Path(sys.argv[2]), timeout=20)
except installer.ModuleInstallationError as error:
    assert isinstance(error.__cause__, FileNotFoundError)
    assert "could not execute" in str(error)
else:
    raise AssertionError("Missing interpreter/cwd unexpectedly executed")
assert sorted(str(p) for p in work.glob("cochem-pinned-pip-*")) == before
print(json.dumps({"boundary": "ModuleInstallationError", "cause": "FileNotFoundError",
                  "mode": mode, "temporary_wheel_cleaned": True}))
'''


@pytest.mark.parametrize("mode", ["interpreter", "cwd"])
def test_legacy_wrapper_keeps_real_prelaunch_error_contract(mode, wheel, offline_env, tmp_path):
    scratch = tmp_path / "owned-tool-temporary"
    scratch.mkdir()
    environment = dict(offline_env, TMPDIR=str(scratch), TEMP=str(scratch), TMP=str(scratch),
                       PYTHONDONTWRITEBYTECODE="1")
    environment = source_child_environment(environment, selected_source=ROOT)
    result = subprocess.run([sys.executable, "-B", "-c", LEGACY_CHILD,
                             str(ROOT), str(wheel), str(scratch), mode],
                            env=environment, cwd=ROOT, capture_output=True, text=True,
                            timeout=35, check=False)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout.splitlines()[-1])
    assert observed == {"boundary": "ModuleInstallationError", "cause": "FileNotFoundError",
                        "mode": mode, "temporary_wheel_cleaned": True}
    assert list(scratch.iterdir()) == []


def test_invalid_artifact_refuses_before_context_body(wheel, offline_env, tmp_path):
    corrupt = tmp_path / wheel.name
    data = bytearray(wheel.read_bytes())
    data[-1] ^= 1
    corrupt.write_bytes(data)
    entered = tmp_path / "context-body-entered"
    with pytest.raises(installer.ModuleInstallationError, match="checksum"):
        with installer._pip_command(Path(sys.executable), ["install", "unused"],
                                    env=offline_env, wheel=corrupt, timeout=20):
            entered.write_text("Body would execute only after verified admission")
    assert not entered.exists()
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == PIP_SHA256


def test_dependency_manager_uses_actual_venv_before_local_install(
        wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    lexical = str(python.absolute())
    caller = _caller_pip()
    base_python = Path(sys.executable).resolve()
    base_hash = hashlib.sha256(base_python.read_bytes()).hexdigest()
    manager = DependencyManager(auto_rollback=False)
    environment = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    # This nonmutating real invocation must demonstrate the lexical venv target
    # BEFORE any install. The old .resolve() bug fails here without a base install.
    debug = manager.run_pip_command(["debug"], python_executable=python,
                                    env=environment, timeout=30, check=True)
    assert debug.success and debug.returncode == 0
    assert debug.command[0] == debug.executable_path == lexical
    assert f"sys.executable: {lexical}" in debug.stdout
    assert Path(_inspect(python, environment)["prefix"]).resolve() == target.resolve()
    installer._run_pip(python, [], env=environment, label="Own fresh venv bootstrap",
                       wheel=wheel, bootstrap=True, timeout=30)
    project, wheels = tmp_path / "actual-project", tmp_path / "actual-wheels"
    marker = _project(project)
    installer._run_pip(python, ["wheel", "--no-deps", "--no-index", "--wheel-dir",
                                str(wheels), str(project)], env=environment,
                       label="Real local fixture wheel", wheel=wheel, timeout=45)
    assert marker.read_text() == "real PEP 517 build"
    built = list(wheels.glob("*.whl"))
    assert len(built) == 1
    installed = manager.run_pip_command(["install", "--no-index", "--no-deps", str(built[0])],
                                        python_executable=python, env=environment,
                                        timeout=30, check=True)
    assert installed.success and installed.returncode == 0
    assert installed.command[0] == installed.executable_path == lexical
    observed = _inspect(python, environment)
    assert Path(observed["prefix"]).resolve() == target.resolve()
    assert observed["fixture_value"] == 42
    assert Path(observed["fixture_origin"]).resolve().is_relative_to(target.resolve())
    assert observed["distributions"]["cochem-installer-fixture"]["version"] == "1.2.3"
    assert observed["distributions"]["cochem-installer-fixture"]["direct_url"]["url"] == built[0].as_uri()
    assert _caller_pip() == caller
    assert hashlib.sha256(base_python.read_bytes()).hexdigest() == base_hash


@pytest.mark.parametrize("check", [False, True])
def test_dependency_manager_keeps_actual_nonzero_result_or_exception(
        check, wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    before = _tree(target)
    manager = DependencyManager(auto_rollback=False)
    args = ["install", "--no-index", "--no-deps",
            str(tmp_path / "absent_fixture-0.0-py3-none-any.whl")]
    environment = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    if check:
        with pytest.raises(PipExecutionError, match="exit code") as error:
            manager.run_pip_command(args, python_executable=python, env=environment,
                                    timeout=30, check=True)
        assert "STDERR:" in str(error.value) and "ERROR" in str(error.value)
    else:
        result = manager.run_pip_command(args, python_executable=python, env=environment,
                                         timeout=30, check=False)
        assert not result.success and result.returncode != 0
        assert result.command[0] == result.executable_path == str(python.absolute())
        assert "ERROR" in result.stderr and "ERROR" not in result.stdout
        assert result.duration_seconds >= 0
    assert _tree(target) == before


def test_dependency_manager_readonly_does_not_fetch_missing_artifact(offline_env, tmp_path):
    caller = _caller_pip()
    missing = tmp_path / "must-not-fetch" / installer.PINNED_PIP_FILENAME
    environment = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(missing))
    result = DependencyManager(auto_rollback=False).run_pip_command(
        ["--version"], python_executable=Path(sys.executable), env=environment,
        timeout=20, check=True)
    assert result.success and result.returncode == 0
    assert result.command == [sys.executable, "-m", "pip", "--version"]
    assert result.stdout.startswith(f"pip {caller['version']} from ")
    assert not missing.parent.exists() and _caller_pip() == caller


def test_actual_intake_broker_streams_verified_tool(wheel, offline_env, tmp_path):
    from cochem_base.intake import cochem_mint_ingestor as intake

    # Exercise the actual broker imported by the intake caller, without changing
    # HAS_WATCHDOG or installing anything into the accepted test interpreter.
    broker = intake.safe_subprocess_run
    assert broker is not None
    assert Path(broker.__code__.co_filename).resolve() == (
        ROOT / "src/cochem_base/core_engine/cochem_core_subprocess_broker.py")
    stdout_lines, stderr_lines = [], []
    caller = _caller_pip()
    with installer._pip_command(Path(sys.executable), ["debug"], env=offline_env,
                                wheel=wheel, timeout=30) as (command, environment, remaining):
        private = _private_wheel(command)
        result = broker(command, cwd=tmp_path, env=environment, timeout=remaining,
                        check=True, on_stdout_line=stdout_lines.append,
                        on_stderr_line=stderr_lines.append,
                        crash_log_directory=tmp_path / "crash-records")
        assert result.returncode == 0
        assert "pip 26.2" in result.stdout and "WARNING" in result.stderr
        assert any("pip 26.2" in line for line in stdout_lines)
        assert any("WARNING" in line for line in stderr_lines)
        assert not any("WARNING" in line for line in stdout_lines)
    assert not private.parent.exists() and _caller_pip() == caller
