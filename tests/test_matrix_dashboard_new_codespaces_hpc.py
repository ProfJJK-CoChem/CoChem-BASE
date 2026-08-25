import os
import sys
import psutil
import atexit
import tempfile
import subprocess
from pathlib import Path
import logging
import pytest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

def sweep_zombie_processes():
    for proc in psutil.process_iter(['pid', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                proc.terminate()
                proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            # Strictly catching only NoSuchProcess, AccessDenied, TimeoutExpired per policy
            pass

atexit.register(sweep_zombie_processes)

@pytest.fixture
def hpc_codespaces_env(monkeypatch, tmp_path):
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    yield tmp_path

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "hpc", reason="Requires CODESPACES=true and COCHEM_CALCULATION_OS=hpc")
def test_interactive_matrix_dashboard_paths_and_test(hpc_codespaces_env):
    """
    Test the New Install -> Set Paths & Test logic of the Interactive Matrix Dashboard.
    Ensures simulation of Codespaces/HPC, native binary resolution, no mocking,
    and git hash logic.
    Executes physically via a NamedTemporaryFile to enforce strict OS boundaries without
    string injection (-c).
    """
    script_content = f"""import os
import sys
import psutil
import atexit
from pathlib import Path

# Insert REPO_ROOT into path
REPO_ROOT = Path(r"{REPO_ROOT}")
sys.path.insert(0, str(REPO_ROOT))

from cochem_base.interfaces.cochem_unity_installer_dashboard import SynapInstallerGUI
from cochem_base.config_loader import resolve_executable

def sweep_zombie_processes():
    for proc in psutil.process_iter(['pid', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                proc.terminate()
                proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

atexit.register(sweep_zombie_processes)

def main():
    dashboard = SynapInstallerGUI()

    assert dashboard.interact_target.value == "GitHub Codespaces"
    assert dashboard.calc_target.value in ("GitHub Actions", "HPC")

    git_hash = dashboard._get_git_hash()
    assert git_hash is not None
    assert len(git_hash) > 0
    assert git_hash != "RELEASE_BUILD"

    res_fail = dashboard._verify_host_orca_path("non_existent_orca_binary_999")
    assert res_fail is False

    res_empty = dashboard._verify_host_orca_path("")

    expected_orca = resolve_executable(env_var="ORCA_CMD", candidates=("orca",))
    assert expected_orca is not None

    expected_mpi = resolve_executable(env_var="MPI_CMD", candidates=("mpirun", "mpiexec"))
    assert expected_mpi is not None

    print("SUCCESS")

    if __name__ == "__main__":
        main()
"""

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
            tmp.write(script_content)
            tmp_path = Path(tmp.name)
        
        env = os.environ.copy()
        
        res = subprocess.run(
            [sys.executable, str(tmp_path)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=60
        )
        assert "SUCCESS" in res.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Shim execution failed with return code {e.returncode}. STDOUT: {e.stdout} STDERR: {e.stderr}")
        raise
    except subprocess.TimeoutExpired as e:
        logger.error(f"Shim execution timed out. STDOUT: {e.stdout} STDERR: {e.stderr}")
        raise
    finally:
        if 'tmp_path' in locals() and tmp_path.exists():
            tmp_path.unlink()
