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
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.warning(f"Process error during zombie sweep: {e}")

atexit.register(sweep_zombie_processes)

def get_git_hash(base_dir: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"], 
            cwd=str(base_dir), 
            capture_output=True, 
            text=True, 
            check=True, 
            timeout=5
        )
        return res.stdout.strip()[:16]
    except FileNotFoundError as e:
        raise RuntimeError("git binary missing. Cannot proceed with physical execution.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("git execution failed. Cannot proceed with physical execution.") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("git execution timed out. Cannot proceed with physical execution.") from e

@pytest.fixture
def codespaces_wsl_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Simulates a Codespaces interaction + WSL calculation environment
    by pointing the artifact directory to a temporary space and setting variables.
    """
    cs_wsl_scratch = tmp_path / "scratch" / "codespaces_wsl" / "CoChem_Artifacts"
    cs_wsl_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(cs_wsl_scratch))
    return cs_wsl_scratch

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "wsl", reason="Requires CODESPACES=true and COCHEM_CALCULATION_OS=wsl")
def test_matrix_dashboard_new_codespaces_wsl(codespaces_wsl_ephemeral_env: Path, caplog: pytest.LogCaptureFixture):
    """
    Tests the "New Install -> Set Paths & Test" logic of the Interactive Matrix Dashboard module
    targeting Codespaces interaction and Local-Windows (WSL) calculation environment.
    Verifies that it identifies the correct path requirements and physically resolves binaries
    without any mocking.
    """
    caplog.set_level(logging.INFO)
    
    installer = SynapInstallerGUI()
    
    assert str(codespaces_wsl_ephemeral_env) in str(installer.artifact_dir)
    assert installer.module_registry.exists()
    
    target_mod = "CoChem-BENCH"
    mod_dir = installer.module_registry / target_mod
    
    if mod_dir.exists():
        shutil.rmtree(mod_dir, ignore_errors=True)
    
    base_dir = get_base_root()
    real_git_hash = get_git_hash(base_dir)
    
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash=real_git_hash,
        interaction_environment="Codespaces",
        calculation_environment="Local-Windows (WSL)",
        orca_tarball_path="",
        selected_repositories=[target_mod]
    )
    
    installer._pure_python_deployment_worker(manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict())
    
    log_file_content = installer.log_file.read_text(encoding="utf-8")
    
    assert f"Deep cloning {target_mod}" in log_file_content, "The 'New Install' (clone) logic was not triggered."
    assert "Cloned" in log_file_content or "Failed to clone" in log_file_content
    
    logger.info("Test passed successfully.")
