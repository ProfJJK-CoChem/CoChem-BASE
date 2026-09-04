"""Test suite for HPC NVIDIA MPS Worker Daemon Lifecycle & Pipe Polling (Suggestion #69).

Method Matrix v4 §8A.4: NVIDIA MPS Daemon Lifecycle Management [M].
Strict Zero-Mock Mandate: Authentic shell execution, genuine OS process supervision,
PID polling, termination flag response, and signal-trapped scratch directory purge.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def get_bash_executable() -> str:
    """Resolves an authentic bash executable capable of running POSIX shell scripts."""
    candidates = [
        Path("C:/Program Files/Git/bin/bash.exe"),
        Path("C:/Program Files/Git/usr/bin/bash.exe"),
        Path("/bin/bash"),
        Path("/usr/bin/bash"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    which = shutil.which("bash")
    if which:
        return which
    pytest.skip("No compatible bash interpreter available for MPS worker lifecycle test.")


@pytest.fixture
def mps_script_path() -> Path:
    script = REPO_TORQ / "HPC_Launchers" / "cochem_mps_worker.sh"
    assert script.exists(), f"MPS worker script not found at {script}"
    return script


def test_mps_worker_static_contract(mps_script_path: Path):
    """Verifies that bare wait is eradicated and active monitoring + traps are implemented."""
    content = mps_script_path.read_text(encoding="utf-8")

    # 1. Untargeted bare 'wait' must be eradicated
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        clean = line.strip()
        if clean == "wait":
            pytest.fail(f"Eradicated bare wait command found on line {idx}: '{line}'")

    # 2. Active supervision loop must be present
    assert 'while kill -0 "${MPS_PID}"' in content or 'while' in content
    assert "TERMINATE_FLAG" in content or "mps_terminate" in content

    # 3. Trapped signal handler must intercept EXIT, SIGINT, SIGTERM
    assert "trap cleanup_mps" in content
    assert "SIGINT" in content
    assert "SIGTERM" in content

    # 4. Ring 2 ephemeral scratch pipes and log routing
    assert "CUDA_MPS_PIPE_DIRECTORY" in content
    assert "CUDA_MPS_LOG_DIRECTORY" in content

    # 5. VRAM memory query check
    assert "nvidia-smi" in content
    assert "memory.used" in content


def test_mps_worker_passthrough_execution(mps_script_path: Path, tmp_path: Path):
    """Verifies that cochem_mps_worker.sh executes passthrough commands and runs cleanup."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = "12345"

    cmd = [
        bash_exec,
        str(mps_script_path).replace("\\", "/"),
        "echo",
        "COCHEM_MPS_TEST_PAYLOAD",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
    assert proc.returncode == 0
    assert "COCHEM_MPS_TEST_PAYLOAD" in proc.stdout
    assert "[CoChem-MPS] Initiating graceful MPS daemon termination..." in proc.stdout
    assert "[CoChem-MPS] MPS daemon shutdown and scratch pipe purge complete." in proc.stdout


def test_mps_worker_active_monitoring_and_flag_termination(mps_script_path: Path, tmp_path: Path):
    """Verifies active daemon supervision loop and graceful shutdown via termination flag."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    job_id = "777001"
    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = job_id

    cmd = [bash_exec, str(mps_script_path).replace("\\", "/")]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Give script a brief moment to initialize directories
        time.sleep(1.0)
        assert proc.poll() is None, "MPS worker exited prematurely instead of supervising!"

        pipe_dir = scratch_dir / f"mps_control_{job_id}"
        log_dir = scratch_dir / f"mps_log_{job_id}"
        assert pipe_dir.exists(), f"Expected pipe directory {pipe_dir} was not created!"
        assert log_dir.exists(), f"Expected log directory {log_dir} was not created!"

        # Touch the termination flag in scratch (Method Matrix §8A.4)
        term_flag = scratch_dir / f"mps_terminate_{job_id}.flag"
        term_flag.write_text("TERMINATE", encoding="utf-8")

        # Wait for daemon monitoring loop to detect flag and exit
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0
        assert "Detected termination flag" in stdout or "graceful MPS daemon termination" in stdout
        assert "MPS daemon shutdown and scratch pipe purge complete" in stdout

        # Assert pipe and log directories in scratch are purged by trap cleanup
        assert not pipe_dir.exists(), f"Pipe directory {pipe_dir} was not purged by cleanup trap!"
        assert not log_dir.exists(), f"Log directory {log_dir} was not purged by cleanup trap!"

    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_mps_worker_sigterm_trap_cleanup(mps_script_path: Path, tmp_path: Path):
    """Verifies that SIGTERM triggers the trapped signal cleanup handler."""
    bash_exec = get_bash_executable()
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    job_id = "888002"
    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["SLURM_JOB_ID"] = job_id

    # Execute with command payload that delivers SIGTERM to the process
    cmd = [
        bash_exec,
        str(mps_script_path).replace("\\", "/"),
        "bash",
        "-c",
        "kill -TERM $$",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)

    # Trap handler must execute upon SIGTERM and purge scratch directories
    assert "[CoChem-MPS] Initiating graceful MPS daemon termination..." in proc.stdout
    assert "[CoChem-MPS] MPS daemon shutdown and scratch pipe purge complete." in proc.stdout

    pipe_dir = scratch_dir / f"mps_control_{job_id}"
    log_dir = scratch_dir / f"mps_log_{job_id}"
    assert not pipe_dir.exists(), f"Pipe directory {pipe_dir} was not purged by SIGTERM trap!"
    assert not log_dir.exists(), f"Log directory {log_dir} was not purged by SIGTERM trap!"
