"""Actual standalone broker CLI controls; no executing-interface substitutions."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _run_cli(workspace: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    repository = Path(__file__).resolve().parents[1]
    script = repository / "src/cochem_base/core_engine/cochem_subprocess_broker.py"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.pathsep.join((str(repository / "src"), str(repository))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "COCHEM_ARTIFACTS_DIR": str(workspace / "artifacts"),
        "COCHEM_SCRATCH_DIR": str(workspace / "scratch"),
    }
    for name in ("SYSTEMROOT", "WINDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        cwd=workspace, env=environment, capture_output=True, text=True,
        timeout=45, check=False,
    )


def test_cli_main_show_cpu_topology(tmp_path: Path) -> None:
    observed = _run_cli(tmp_path, "--show-cpu-topology")
    assert observed.returncode == 0, observed.stderr
    assert "Host CPU Topology:" in observed.stdout
    assert "logical_cores" in observed.stdout


def test_cli_main_reap_zombies(tmp_path: Path) -> None:
    observed = _run_cli(tmp_path, "--reap-zombies")
    assert observed.returncode == 0, observed.stderr
    assert "Reaped 0 zombie process tree(s)." in observed.stdout


def test_cli_main_check_quota_success(tmp_path: Path) -> None:
    observed = _run_cli(tmp_path, "--check-quota", "0.01", "--cwd", str(tmp_path))
    assert observed.returncode == 0, observed.stderr
    assert "Disk quota verification passed" in observed.stdout


def test_cli_main_check_quota_failure(tmp_path: Path) -> None:
    observed = _run_cli(tmp_path, "--check-quota", "999999.0", "--cwd", str(tmp_path))
    assert observed.returncode == 1
    assert "Disk quota check failed" in observed.stderr


def test_cli_main_execute_cmd(tmp_path: Path) -> None:
    command = f'"{sys.executable}" -B -c "print(98765)"'
    observed = _run_cli(tmp_path, "--cmd", command, "--cwd", str(tmp_path))
    assert observed.returncode == 0, observed.stderr
    assert observed.stdout.strip() == "98765"


def test_cli_main_default_banner(tmp_path: Path) -> None:
    observed = _run_cli(tmp_path)
    assert observed.returncode == 0, observed.stderr
    assert "CoChem Subprocess Broker armed" in observed.stdout
