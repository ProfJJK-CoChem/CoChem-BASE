import os
import subprocess
import logging
import psutil
import atexit
import tempfile
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
def codespaces_actions_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Simulates a Codespaces interaction + GitHub Actions calculation environment by pointing the artifact directory
    to a scratch space and overriding environment variables.
    No code mimicking is used; we physically alter the environment.
    """
    codespaces_scratch = Path(os.environ.get("COCHEM_ARTIFACT_DIR", tmp_path / "CoChem_Artifacts"))
    codespaces_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(codespaces_scratch))
    return codespaces_scratch

@pytest.mark.skipif(os.environ.get("CODESPACES") != "true" or os.environ.get("COCHEM_CALCULATION_OS") != "github-actions", reason="Requires CODESPACES=true and COCHEM_CALCULATION_OS=github-actions")
def test_matrix_dashboard_keep_codespaces_actions(codespaces_actions_ephemeral_env: Path, caplog: pytest.LogCaptureFixture):
    """
    Tests the "Keep previous setup" logic of the Interactive Matrix Dashboard module
    targeting Codespaces interaction and GitHub Actions calculation environment.
    Verifies that it identifies the correct path requirements, ensuring simulation of a Codespaces/GitHub Actions node
    and physically resolving binaries natively.
    """
    caplog.set_level(logging.INFO)
    
    # Initialize the GUI (which acts as the deployment orchestrator)
    installer = SynapInstallerGUI()
    
    # Verify path resolutions respected our injected environment
    assert str(codespaces_actions_ephemeral_env) in str(installer.artifact_dir)
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
        
        # Use tempfile.NamedTemporaryFile instead of string injection for external processes
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
            tf.write("Initial commit")
            commit_msg_path = tf.name
        
        try:
            subprocess.run(["git", "commit", "--allow-empty", "-F", commit_msg_path], cwd=str(mod_dir), check=True, timeout=10)
            result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(mod_dir), capture_output=True, text=True, check=True, timeout=10)
            real_git_hash = result.stdout.strip()
        finally:
            if os.path.exists(commit_msg_path):
                os.remove(commit_msg_path)
    except FileNotFoundError as e:
        pytest.fail(f"git binary missing or not found on system path: {e}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"git command timed out: {e}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"git command failed: {e}")
    
    manifest = DeploymentManifest(
        version="2026.2",
        git_provenance_hash=real_git_hash,
        interaction_environment="Codespaces",
        calculation_environment="GitHub Actions",
        orca_tarball_path=os.environ.get("ORCA_PATH", ""),
        selected_repositories=[target_mod]
    )
    
    # Invoke the pure python worker synchronously
    # Use model_dump() for pydantic v2, or dict() for v1
    manifest_dict = manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict()
    installer._pure_python_deployment_worker(manifest_dict)
    
    # Verify the "Keep previous setup" code path was followed
    log_file_content = installer.log_file.read_text(encoding="utf-8")
    
    assert f"Updating existing module: {target_mod}" in log_file_content, "The 'keep previous setup' (update) logic was not triggered."
    assert "Fast-forward failed for" in log_file_content or "updated successfully" in log_file_content
    
    logger.info("Test passed successfully.")
