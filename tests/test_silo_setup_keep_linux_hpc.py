import os
import time
import subprocess
import logging
import psutil
import atexit
from pathlib import Path
import pytest
from filelock import FileLock, Timeout

from cochem_base.config_loader import resolve_conda_executable
from setup.cochem_base_silo_setup import setup_conda_silo

logger = logging.getLogger(__name__)

def sweep_zombie_processes():
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        logger.warning(f"Failed to sweep zombie processes: {e}")

atexit.register(sweep_zombie_processes)

@pytest.fixture
def hpc_mock_env(tmp_path, monkeypatch):
    """
    Simulates an HPC environment path requirement by pointing the artifact directory
    to an HPC-like scratch space and overriding environment variables.
    No code mocking is used; we physically alter the environment.
    """
    # Simulate an HPC scratch directory target
    hpc_scratch = tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
    hpc_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(hpc_scratch))
    # Some HPC clusters might set specific cluster variables
    return hpc_scratch

@pytest.mark.skipif(not os.environ.get("SLURM_JOB_ID") or os.environ.get("COCHEM_OS_TARGET") != "linux_x86_64", reason="Requires SLURM_JOB_ID and COCHEM_OS_TARGET=linux_x86_64")
def test_silo_setup_keep_linux_hpc(hpc_mock_env, caplog):
    """
    Tests the "Keep previous setup" logic of the Silo Setup module targeting Local-Linux/HPC.
    Physically provisions Conda with `zlib` to simulate a "kept" environment.
    Uses FileLock and retry logic to avoid hitting conda's 429 RESOURCE_EXHAUSTED rate limits.
    """
    caplog.set_level(logging.INFO)
    artifact_dir = hpc_mock_env
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    silo_dir.parent.mkdir(parents=True, exist_ok=True)

    conda_exe = resolve_conda_executable()
    lock_path = artifact_dir / "conda_provision.lock"

    max_attempts = 3
    delay_s = 5
    provisioned = False

    # EXPLICIT RETRY LOGIC and SERIALIZED EXECUTION
    try:
        with FileLock(str(lock_path), timeout=60):
            for attempt in range(1, max_attempts + 1):
                try:
                    cmd = [
                        str(conda_exe), "create", "--prefix", str(silo_dir),
                        "-c", "conda-forge", "zlib", "--yes"
                    ]
                    logger.info(f"Attempt {attempt}: Provisioning conda env at {silo_dir}")
                    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
                    provisioned = True
                    break
                except subprocess.TimeoutExpired as e:
                    logger.warning(f"Attempt {attempt} timed out: {e}")
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts due to timeout.") from e
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Attempt {attempt} failed with error: {e.stderr}")
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError("Failed to provision conda environment after max attempts.") from e
    except Timeout as e:
        raise RuntimeError(f"Could not acquire file lock {lock_path} for conda provisioning.") from e

    assert provisioned, "Conda environment was not successfully provisioned."

    # Verify that conda-meta exists and contains json files as expected by the script
    conda_meta_dir = silo_dir / "conda-meta"
    assert conda_meta_dir.exists(), "conda-meta directory was not created."
    assert list(conda_meta_dir.glob("*.json")), "No .json files found in conda-meta."

    # Now run the setup module, it should detect the existing environment and KEEP it.
    setup_conda_silo()

    # Assert that it skipped creation
    assert "Conda environment already exists at:" in caplog.text, "Did not detect existing Conda environment."
    assert "Skipping creation process" in caplog.text, "Did not skip creation process."
