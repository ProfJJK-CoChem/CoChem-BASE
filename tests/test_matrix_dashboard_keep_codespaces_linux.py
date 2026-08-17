import os
import subprocess
import logging
import psutil
import atexit
from pathlib import Path
import pytest
from pydantic import BaseModel

from cochem_base.interfaces.cochem_unity_installer_dashboard import SynapInstallerGUI

logger = logging.getLogger(__name__)

class DeploymentManifest(BaseModel):
    version: str
    git_provenance_hash: str
    interaction_environment: str
    calculation_environment: str
    orca_tarball_path: str
    selected_repositories: list[str]

def sweep_zombie_processes() -> None:
    """Sweep zombie processes spawned by the current process."""
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
                p.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.warning(f"Process lookup or access error during zombie sweep: {e}")

atexit.register(sweep_zombie_processes)

@pytest.fixture
def codespaces_linux_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Simulates a Codespaces interaction + Local-Linux calculation environment by pointing the artifact directory
    to a scratch space and overriding environment variables.
    No code mimicking is used; we physically alter the environment.
    """
    # Use environment variable or default to a dynamic scratch path
    codespaces_scratch = Path(os.environ.get("COCHEM_ARTIFACT_DIR", tmp_path / "CoChem_Artifacts"))
    codespaces_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(codespaces_scratch))
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setenv("COCHEM_CALCULATION_OS", "linux")
    return codespaces_scratch

def test_matrix_dashboard_keep_codespaces_linux(codespaces_linux_ephemeral_env: Path, caplog: pytest.LogCaptureFixture):
    """
    Tests the "Keep previous setup" logic of the Interactive Matrix Dashboard module
    targeting Codespaces interaction and Local-Linux (Deb) calculation environment.
    Verifies that it identifies the correct path requirements, ensuring simulation of a Codespaces/Linux node
    and physically resolving binaries natively.
    """
    caplog.set_level(logging.INFO)
    
    # Initialize the GUI (which acts as the deployment orchestrator)
    installer = SynapInstallerGUI()
    
    # Verify path resolutions respected our injected environment
    assert str(codespaces_linux_ephemeral_env) in str(installer.artifact_dir)
    assert installer.module_registry.exists()
    
    # Set up our physical repository to test the 'keep previous setup' logic
    target_mod = "CoChem-TOPOS"
    mod_dir = installer.module_registry / target_mod
    mod_dir.mkdir(parents=True, exist_ok=True)
    
    # Init a real git repo so it triggers the 'keep' logic (git pull --ff-only)
    try:
        subprocess.run(["git", "init"], cwd=str(mod_dir), check=True, timeout=10)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(mod_dir), check=True, timeout=10)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(mod_dir), check=True, timeout=10)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=str(mod_dir), check=True, timeout=10)
    except FileNotFoundError as e:
        pytest.fail(f"git binary missing or not found on system path: {e}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"git command timed out: {e}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"git command failed: {e}")
    
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash="abcdef1234567890",
        interaction_environment="Codespaces",
        calculation_environment="Local-Linux (Deb)",
        orca_tarball_path="",
        selected_repositories=[target_mod]
    )
    
    # Invoke the pure python worker synchronously
    # Use model_dump() for pydantic v2, or dict() for v1; we will assume manifest processing is a dictionary.
    installer._pure_python_deployment_worker(manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict())
    
    # Verify the "Keep previous setup" code path was followed
    log_file_content = installer.log_file.read_text(encoding="utf-8")
    
    assert f"Updating existing module: {target_mod}" in log_file_content, "The 'keep previous setup' (update) logic was not triggered."
    assert "Fast-forward failed for" in log_file_content or "updated successfully" in log_file_content
    
    logger.info("Test passed successfully.")
