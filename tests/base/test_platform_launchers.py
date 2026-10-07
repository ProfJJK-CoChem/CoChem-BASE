"""Exercise the actual host launcher without installing a GUI or running chemistry."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _launch(arguments: list[str], cwd: Path, *, finder: bool = False) -> subprocess.CompletedProcess[str]:
    if os.name == "nt":
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c",
                   str(ROOT / "Launch_CoChem_Windows.bat"), *arguments]
    else:
        name = "Launch_CoChem_Mac.command" if finder else "Launch_CoChem_Mac_Linux.sh"
        command = [str(ROOT / name), *arguments]
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30)


def test_actual_host_launcher_reaches_real_bootstrap_from_external_directory(tmp_path: Path):
    arguments = ["--native", "--check"] if os.name == "nt" else ["--check"]
    result = _launch(arguments, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--venv" in result.stdout and "--launch" in result.stdout
    assert "GUI dependencies and chemistry were not tested" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_actual_host_launcher_help_and_secondary_entry_point(tmp_path: Path):
    result = _launch(["--help"], tmp_path, finder=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--check" in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("arguments", [["--unknown"], ["--check", "unexpected"]])
def test_actual_host_launcher_rejects_invalid_arguments(tmp_path: Path, arguments: list[str]):
    result = _launch(arguments, tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert list(tmp_path.iterdir()) == []
