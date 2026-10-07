"""Live integrity transport checks; diagnostic text is not quantum benchmark data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psutil
import pytest

from cochem_base.analysis.electronic_sanitizer import SpinContaminationStreamValidator
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.exceptions import SpinContaminationError


@pytest.mark.parametrize("diagnostic", [
    "Expectation value of <S**2> : 0.825",
    "Expectation value of <S^2> : 8.25D-1",
])
def test_contamination_stops_real_process_and_descendant(tmp_path: Path, diagnostic: str) -> None:
    marker = tmp_path / "unacceptable-continuation"
    pid_file = tmp_path / "worker.pid"
    worker = "import pathlib,sys,time; time.sleep(30); pathlib.Path(sys.argv[1]).touch()"
    launcher = """
import pathlib, signal, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])
def stop(signum, frame):
    child.wait(timeout=3)
    raise SystemExit(1)
signal.signal(signal.SIGTERM, stop)
pathlib.Path(sys.argv[3]).write_text(str(child.pid))
print(sys.argv[4], flush=True)
time.sleep(30)
pathlib.Path(sys.argv[2]).touch()
"""
    with pytest.raises(SpinContaminationError) as caught:
        safe_subprocess_run(
            [sys.executable, "-c", launcher, worker, str(marker), str(pid_file), diagnostic],
            cwd=tmp_path, timeout=10, required_disk_gb=0,
            on_stdout_line=SpinContaminationStreamValidator(2),
        )
    assert caught.value.details["routing_tier"] == "T9"
    assert not marker.exists()
    worker_pid = int(pid_file.read_text())
    assert not psutil.pid_exists(worker_pid) or psutil.Process(worker_pid).status() == psutil.STATUS_ZOMBIE
    assert diagnostic in (tmp_path / "process_stdout.log").read_text()


@pytest.mark.skipif(os.name == "nt", reason="POSIX session ownership; Windows uses its native job object")
def test_callback_failure_kills_group_after_launcher_exits(tmp_path: Path) -> None:
    pid_file = tmp_path / "worker.pid"
    worker = """
import pathlib, sys, time
time.sleep(0.2)
print('Expectation value of <S**2> : 0.825', flush=True)
time.sleep(30)
"""
    launcher = """
import pathlib, subprocess, sys
child = subprocess.Popen([sys.executable, '-c', sys.argv[1]])
pathlib.Path(sys.argv[2]).write_text(str(child.pid))
"""
    with pytest.raises(SpinContaminationError):
        safe_subprocess_run(
            [sys.executable, "-c", launcher, worker, str(pid_file)],
            cwd=tmp_path, timeout=10, required_disk_gb=0,
            on_stdout_line=SpinContaminationStreamValidator(2),
        )
    worker_pid = int(pid_file.read_text())
    assert not psutil.pid_exists(worker_pid) or psutil.Process(worker_pid).status() == psutil.STATUS_ZOMBIE


@pytest.mark.parametrize("diagnostic", [
    "expectation value of <s**2> :",
    "Expectation value of <S**2> : NaN",
    "Expectation value of <S**2> : incomplete",
    "Ideal value S*(S+1) :",
    "Ideal value S*(S+1) : 2.0",
])
def test_invalid_live_spin_telemetry_fails_closed(diagnostic: str) -> None:
    with pytest.raises(ValueError):
        SpinContaminationStreamValidator(2)(diagnostic)


@pytest.mark.skipif(os.name == "nt", reason="POSIX session isolation contract")
def test_live_callback_cannot_disable_process_ownership(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="isolated process session"):
        safe_subprocess_run(
            [sys.executable, "-c", "raise RuntimeError('must never execute')"],
            cwd=tmp_path, on_stdout_line=SpinContaminationStreamValidator(2), start_new_session=False,
        )
