import os
import subprocess
import time
import sys
import logging
import psutil
import atexit
from pathlib import Path

import filelock
import pytest

# Add the repository root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from setup.cochem_base_silo_setup import setup_conda_silo
from cochem_base.config_loader import resolve_conda_executable

logger = logging.getLogger(__name__)

def sweep_zombie_processes():
    """Sweep and terminate any zombie processes left over."""
    for proc in psutil.process_iter(['pid', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                proc.terminate()
                proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

atexit.register(sweep_zombie_processes)

@pytest.fixture
def conda_env_simulator(tmp_path, monkeypatch):
    """Fixture to set up env vars and clean up."""
    # Simulate Codespaces + Local-Linux (Deb)
    
    # Point artifact dir to tmp_path
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    
    silo_dir = tmp_path / "Silos" / "cochem_base_silo"
    return silo_dir

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "linux", reason="Requires CODESPACES and COCHEM_CALCULATION_OS=linux")
def test_silo_setup_keep_codespaces_linux(conda_env_simulator, caplog, capsys):
    """
    Test that Silo Setup properly identifies an existing environment and skips
    re-creation (the 'Keep previous setup' logic) under Codespaces/Linux simulation.
    """
    silo_dir = conda_env_simulator
    conda_exe = resolve_conda_executable()
    
    # Physically provision Conda with zlib to simulate a "kept" environment
    lock_path = silo_dir.parent / "conda.lock"
    silo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    max_retries = 3
    retry_delay = 5
    success = False
    
    try:
        with filelock.FileLock(str(lock_path), timeout=60):
            for attempt in range(max_retries):
                try:
                    subprocess.run(
                        [str(conda_exe), "create", "--prefix", str(silo_dir), "zlib", "--yes"],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    success = True
                    break
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e.stderr}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        raise RuntimeError(f"Failed to provision conda with zlib after {max_retries} attempts.")
                except subprocess.TimeoutExpired as e:
                    logger.warning(f"Attempt {attempt + 1} timed out: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        raise RuntimeError(f"Subprocess timed out after {max_retries} attempts.")
                except FileNotFoundError as e:
                    logger.error(f"Conda executable not found: {e}")
                    raise RuntimeError(f"Conda executable not found at {conda_exe}")
    except filelock.Timeout:
        raise RuntimeError(f"Failed to acquire file lock at {lock_path} within 60 seconds.")
    finally:
        sweep_zombie_processes()
        
    assert success, "Conda provisioning failed."
    
    # Ensure conda-meta was created and has json files
    conda_meta = silo_dir / "conda-meta"
    assert conda_meta.exists(), "conda-meta directory was not created."
    assert list(conda_meta.glob("*.json")), "No JSON files found in conda-meta."
    
    # Run the setup logic
    with caplog.at_level("INFO"):
        setup_conda_silo()
        
    # Verify the skip logic was triggered
    logs = caplog.text
    assert "Conda environment already exists at:" in logs
    assert "Skipping creation process" in logs
    assert "Creating new conda environment..." not in logs
    
    # Verify that logger takes precedence over print()
    captured = capsys.readouterr()
    assert "Conda environment already exists at:" not in captured.out
    assert "Skipping creation process" not in captured.out
