#!/usr/bin/env python3
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

# Add repo root to path
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
            except psutil.TimeoutExpired:
                logger.warning(f"Timeout expired while waiting for child process {child.pid} to terminate.")
    except psutil.Error as e:
        logger.error(f"Failed during cleanup of child processes: {e}")

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "wsl", reason="Requires CODESPACES and COCHEM_CALCULATION_OS=wsl")
def test_silo_setup_new_codespaces_wsl(isolation_env, monkeypatch):
    """
    Test the 'New Install -> Create & Provision' path of silo setup
    simulating Codespaces+WSL target, but executing physically.
    """
    artifact_dir = isolation_env
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    lock_file = artifact_dir / "conda_silo.lock"
    
    lock = filelock.FileLock(str(lock_file), timeout=60)
    
    max_retries = 3
    delay = 5
    success = False
    
    for attempt in range(max_retries):
        try:
            with lock:
                setup_conda_silo()
                success = True
                break
        except filelock.Timeout:
            logger.warning(f"[Attempt {attempt + 1}] Timeout acquiring lock.")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
        except subprocess.CalledProcessError as e:
            logger.error(f"[Attempt {attempt + 1}] Conda command failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
        except subprocess.TimeoutExpired as e:
            logger.error(f"[Attempt {attempt + 1}] Conda command timed out: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
        except FileNotFoundError as e:
            logger.error(f"[Attempt {attempt + 1}] Required executable not found: {e}")
            raise # No point retrying if file not found
            
    assert success, f"Failed to execute silo setup after {max_retries} attempts."
    
    # Validation
    assert silo_dir.exists(), "Silo directory was not created."
    conda_meta = silo_dir / "conda-meta"
    assert conda_meta.exists(), "conda-meta directory missing."
    json_files = list(conda_meta.glob("*.json"))
    assert len(json_files) > 0, "No packages recorded in conda-meta."
