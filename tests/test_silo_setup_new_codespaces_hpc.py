import os
import sys
import time
import pytest
import psutil
import logging
import filelock
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add repo root to path dynamically
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from setup.cochem_base_silo_setup import setup_conda_silo

@pytest.fixture
def isolation_env(tmp_path, monkeypatch):
    """
    Fixture to isolate testing, set specific variables, and sweep zombies.
    """
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    
    yield tmp_path
    
    # Process cleanup
    try:
        current_proc = psutil.Process()
        children = current_proc.children(recursive=True)
        for child in children:
            try:
                if child.is_running():
                    child.kill()
                    child.wait(timeout=3)
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                logger.warning(f"Access denied when trying to kill process {child.pid}")
            except psutil.TimeoutExpired:
                logger.warning(f"Timeout expired when waiting for process {child.pid} to terminate")
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        pass
    except psutil.TimeoutExpired:
        pass

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "hpc", reason="Requires CODESPACES and COCHEM_CALCULATION_OS=hpc")
def test_silo_setup_new_codespaces_hpc(isolation_env, monkeypatch):
    """
    Test the 'New Install -> Create & Provision' path of silo setup
    simulating Codespaces+HPC target, but executing physically.
    """
    artifact_dir = isolation_env
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    lock_file = artifact_dir / "conda_silo.lock"
    
    lock = filelock.FileLock(str(lock_file), timeout=60)
    
    max_retries = 3
    delay = 5
    success = False
    
    # Verify logger takes precedence over print - redirect stdout to capture print
    # But since setup uses its own logger, we just ensure the execution completes successfully.
    
    for attempt in range(max_retries):
        try:
            with lock:
                logger.info(f"Attempting Conda Silo Setup (Attempt {attempt + 1}/{max_retries})")
                setup_conda_silo()
                success = True
                break
        except filelock.Timeout:
            logger.warning(f"[Attempt {attempt + 1}] Timeout acquiring lock.")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError("Failed to acquire lock after max retries") from None
        except FileNotFoundError as e:
            logger.error(f"[Attempt {attempt + 1}] File not found error: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"File not found after max retries: {e}") from e
        except subprocess.CalledProcessError as e:
            logger.error(f"[Attempt {attempt + 1}] Conda command failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"Conda command failed after max retries: {e}") from e
        except subprocess.TimeoutExpired as e:
            logger.error(f"[Attempt {attempt + 1}] Conda command timed out: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"Conda command timed out after max retries: {e}") from e
        except OSError as e:
            logger.error(f"[Attempt {attempt + 1}] OS Error (possibly required executable not found): {e}")
            raise RuntimeError(f"OS Error during setup: {e}") from e
            
    assert success, f"Failed to execute silo setup after {max_retries} attempts."
    
    # Validation
    assert silo_dir.exists(), "Silo directory was not created."
    conda_meta = silo_dir / "conda-meta"
    assert conda_meta.exists(), "conda-meta directory missing."
    json_files = list(conda_meta.glob("*.json"))
    assert len(json_files) > 0, "No packages recorded in conda-meta."
