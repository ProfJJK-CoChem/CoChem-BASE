from pathlib import Path
from unittest.mock import Mock

from scripts import bootstrap_environment


def test_complete_environment_skips_install(monkeypatch) -> None:
    check_call = Mock()
    monkeypatch.setattr(bootstrap_environment, "_environment_ready", lambda python: True)
    monkeypatch.setattr(bootstrap_environment.subprocess, "check_call", check_call)

    bootstrap_environment.ensure_dependencies(Path("/env/bin/python"))

    check_call.assert_not_called()


def test_incomplete_environment_installs_shared_requirements(monkeypatch) -> None:
    readiness = iter((False, True))
    check_call = Mock()
    monkeypatch.setattr(
        bootstrap_environment, "_environment_ready", lambda python: next(readiness)
    )
    monkeypatch.setattr(bootstrap_environment.subprocess, "check_call", check_call)

    python = Path("/env/bin/python")
    bootstrap_environment.ensure_dependencies(python)

    command = check_call.call_args.args[0]
    assert command[:4] == [str(python), "-m", "pip", "install"]
    assert command[-2:] == ["-r", str(bootstrap_environment.REQUIREMENTS_FILE)]


def test_current_environment_preserves_virtualenv_executable(monkeypatch) -> None:
    ensure_dependencies = Mock()
    monkeypatch.setattr(bootstrap_environment.sys, "executable", ".venv/bin/python")
    monkeypatch.setattr(bootstrap_environment, "ensure_dependencies", ensure_dependencies)

    python = bootstrap_environment.ensure_current_environment()

    assert python == Path.cwd() / ".venv/bin/python"
    ensure_dependencies.assert_called_once_with(python)