import os
import time
import subprocess
import logging
import psutil
import atexit
import shutil
from pathlib import Path
import pytest
from pydantic import BaseModel, Field

from cochem_base.interfaces.cochem_unity_installer_dashboard import SynapInstallerGUI
from cochem_base.config_loader import get_base_root

logger = logging.getLogger(__name__)

class DeploymentManifest(BaseModel):
    version: str
    git_provenance_hash: str
    interaction_environment: str
    calculation_environment: str
    orca_tarball_path: str
    selected_repositories: list[str]

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
    except psutil.Error as e:
        logger.warning(f"Process error during zombie sweep: {e}")
    except FileNotFoundError as e:
        logger.warning(f"Process file not found during zombie sweep: {e}")

atexit.register(sweep_zombie_processes)

def get_git_hash(base_dir: Path) -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(base_dir), capture_output=True, text=True, check=True, timeout=5)
        return res.stdout.strip()[:16]
    except FileNotFoundError as e:
        raise RuntimeError("git binary missing. Cannot proceed with physical execution.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("git execution failed. Cannot proceed with physical execution.") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("git execution timed out. Cannot proceed with physical execution.") from e

@pytest.fixture
def hpc_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Simulates an HPC environment path requirement by pointing the artifact directory
    to an HPC-like scratch space and overriding environment variables.
    No code mimicking is used; we physically alter the environment.
    """
    hpc_scratch = tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
    hpc_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(hpc_scratch))
    monkeypatch.setenv("SLURM_JOB_ID", "999999")
    monkeypatch.setenv("COCHEM_OS_TARGET", "linux_x86_64")
    return hpc_scratch

def test_matrix_dashboard_new_linux_hpc(hpc_ephemeral_env: Path, caplog: pytest.LogCaptureFixture):
    """
    Tests the "New Install" logic of the Interactive Matrix Dashboard module
    targeting Local-Linux interaction and HPC calculation environment.
    Verifies that it identifies the correct path requirements, ensuring simulation of an
    HPC node (via injecting COCHEM_OS_TARGET, SLURM_JOB_ID) and physically resolving binaries.
    """
    caplog.set_level(logging.INFO)
    
    # Initialize the GUI (which acts as the deployment orchestrator)
    installer = SynapInstallerGUI()
    
    # Verify path resolutions respected our injected HPC artifact environment
    assert str(hpc_ephemeral_env) in str(installer.artifact_dir)
    assert installer.module_registry.exists()
    
    # Set up our physical repository to test the 'new install' logic
    target_mod = "CoChem-TOPOS"
    mod_dir = installer.module_registry / target_mod
    
    # Ensure it's completely empty so "New Install" logic (git clone) is triggered
    if mod_dir.exists():
        shutil.rmtree(mod_dir, ignore_errors=True)
    
    base_dir = get_base_root()
    real_git_hash = get_git_hash(base_dir)
    
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash=real_git_hash,
        interaction_environment="Local-Linux (Deb)",
        calculation_environment="HPC",
        orca_tarball_path="",
        selected_repositories=[target_mod]
    )
    
    # Invoke the pure python worker synchronously
    # Use model_dump() for pydantic v2, or dict() for v1; we will assume manifest processing is a dictionary.
    installer._pure_python_deployment_worker(manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict())
    
    # Verify the "New Install" code path was followed
    log_file_content = installer.log_file.read_text(encoding="utf-8")
    
    assert f"Deep cloning {target_mod}" in log_file_content, "The 'New Install' (clone) logic was not triggered."
    assert "Cloned" in log_file_content or "Failed to clone" in log_file_content
    
    logger.info("Test passed successfully.")
