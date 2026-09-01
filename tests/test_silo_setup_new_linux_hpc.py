import atexit
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from filelock import FileLock, Timeout
import psutil
import pytest

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
def hpc_artifact_dir(tmp_path):
    """
    Sets up a legitimate HPC-like directory structure and environment.
    We configure the process environment variables directly to replicate
    an HPC node. This is a real environment configuration, not a mock.
    """
    hpc_scratch = tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
    hpc_scratch.mkdir(parents=True, exist_ok=True)

    old_env = os.environ.get("COCHEM_ARTIFACT_DIR")
    os.environ["COCHEM_ARTIFACT_DIR"] = str(hpc_scratch)

    yield hpc_scratch

    if old_env is not None:
        os.environ["COCHEM_ARTIFACT_DIR"] = old_env
    else:
        del os.environ["COCHEM_ARTIFACT_DIR"]


@pytest.mark.skipif(
    not os.environ.get("SLURM_JOB_ID")
    or os.environ.get("COCHEM_OS_TARGET") != "linux_x86_64",
    reason="Requires SLURM_JOB_ID and COCHEM_OS_TARGET=linux_x86_64",
)
def test_silo_setup_new_linux_hpc(hpc_artifact_dir):
    """
    Tests the "New Install" logic of the Silo Setup module targeting
    Local-Linux/HPC. Physically provisions Conda.
    Uses FileLock and retry logic to avoid hitting conda's 429
    RESOURCE_EXHAUSTED rate limits.
    """
    artifact_dir = hpc_artifact_dir
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"

    lock_path = artifact_dir / "conda_provision_new.lock"

    max_attempts = 3
    delay_s = 5
    provisioned = False

    # EXPLICIT RETRY LOGIC and SERIALIZED EXECUTION
    try:
        with FileLock(str(lock_path), timeout=60):
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(
                        f"Attempt {attempt}: Provisioning NEW conda env at "
                        f"{silo_dir}"
                    )
                    if silo_dir.exists():
                        shutil.rmtree(silo_dir, ignore_errors=True)

                    # Physically run setup in an isolated subprocess
                    env = os.environ.copy()
                    env["COCHEM_ARTIFACT_DIR"] = str(artifact_dir)
                    env["PYTHONPATH"] = str(Path(__file__).parent.parent)

                    cmd_script = (
                        "import logging; "
                        "logging.basicConfig(level=logging.INFO); "
                        "from setup.cochem_base_silo_setup import "
                        "setup_conda_silo; "
                        "setup_conda_silo()"
                    )
                    result = subprocess.run(
                        [sys.executable, "-c", cmd_script],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=True,
                    )

                    provisioned = True
                    break
                except subprocess.TimeoutExpired as e:
                    logger.warning(f"Attempt {attempt} timed out: {e}")
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError(
                            "Failed to provision conda environment after "
                            "max attempts due to timeout."
                        ) from e
                except subprocess.CalledProcessError as e:
                    logger.warning(
                        f"Attempt {attempt} failed with error: {e.stderr}"
                    )
                    sweep_zombie_processes()
                    if attempt < max_attempts:
                        logger.info(f"Retrying in {delay_s} seconds...")
                        time.sleep(delay_s)
                    else:
                        raise RuntimeError(
                            "Failed to provision conda environment after "
                            "max attempts."
                        ) from e
    except Timeout as e:
        raise RuntimeError(
            f"Could not acquire file lock {lock_path} for conda provisioning."
        ) from e

    assert provisioned, "Conda environment was not successfully provisioned."

    conda_meta_dir = silo_dir / "conda-meta"
    assert conda_meta_dir.exists(), "conda-meta directory was not created."
    assert list(conda_meta_dir.glob("*.json")), (
        "No .json files found in conda-meta."
    )

    output = result.stdout + result.stderr
    assert (
        "Environment not found or invalid, proceeding with creation..."
        in output
    ), "Did not attempt new creation."
    assert "Conda environment created successfully at:" in output, (
        "Did not successfully create environment."
    )
