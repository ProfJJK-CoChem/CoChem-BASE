import os
import time
import subprocess
import pytest
import filelock
from pathlib import Path
import psutil

from setup.cochem_base_silo_setup import setup_conda_silo
from cochem_base.config_loader import resolve_conda_executable

@pytest.fixture(autouse=True)
def sweep_zombie_processes():
    yield
    for proc in psutil.process_iter():
        try:
            if "conda" in proc.name().lower() and proc.status() == psutil.STATUS_ZOMBIE:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

@pytest.fixture
def conda_exe():
    try:
        return resolve_conda_executable()
    except FileNotFoundError:
        pytest.skip("Conda executable not found, cannot run physical Conda tests.")

def test_silo_setup_keep_previous(tmp_path, monkeypatch, conda_exe, caplog):
    # 1. OS-level monkeypatching
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setenv("COCHEM_CALCULATION_OS", "macos")
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))

    artifact_dir = tmp_path
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    silo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    # 2. Physically provision Conda with zlib to simulate a 'kept' environment
    # Serialized execution with filelock and explicit retry
    lock_path = tmp_path / "conda.lock"
    lock = filelock.FileLock(str(lock_path), timeout=60)
    
    success = False
    for attempt in range(3):
        try:
            with lock:
                cmd = [conda_exe, "create", "--prefix", str(silo_dir), "zlib", "--yes"]
                subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
                success = True
                break
        except filelock.Timeout:
            time.sleep(5)
        except subprocess.CalledProcessError as e:
            if attempt == 2:
                raise RuntimeError(f"Conda provision failed after 3 attempts: {e.stderr}")
            time.sleep(5)
        except FileNotFoundError as e:
            raise RuntimeError(f"Conda executable missing: {e}")
        except subprocess.TimeoutExpired as e:
            if attempt == 2:
                raise RuntimeError(f"Conda provision timed out: {e}")
            time.sleep(5)
            
    assert success, "Failed to provision conda with zlib"

    # 3. Verify it identifies the correct path requirements (through artifact dir)
    # 4. Execute the 'Keep previous setup' logic
    import logging
    caplog.set_level(logging.INFO)
    caplog.clear()
    setup_conda_silo()
    
    # 5. Verify Logger takes precedence over print()
    # If the setup skipped creation, it logs "Conda environment already exists"
    log_text = caplog.text
    assert "Conda environment already exists at:" in log_text, "Failed to hit the 'Keep previous setup' branch"
    assert "Skipping creation process" in log_text, "Failed to skip creation"

    # Since there's a strict no-mocking policy, we did not mock the print function, 
    # but we can verify that the standard logger was used instead of print,
    # as the output is in caplog.
