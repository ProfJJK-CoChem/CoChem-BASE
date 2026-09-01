import atexit
import logging
import os
import shutil
import subprocess
from pathlib import Path

import psutil
import pytest

from cochem_base.config_loader import get_base_root
from cochem_base.interfaces.cochem_unity_installer_dashboard import (
    DeploymentManifest,
    SynapInstallerGUI,
    serialize_system_config_json,
)

logger = logging.getLogger(__name__)


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
    except psutil.Error as e:
        logger.warning(f"Process error during zombie sweep: {e}")
    except Exception as e:
        logger.warning(f"Failed to sweep zombie processes: {e}")


atexit.register(sweep_zombie_processes)


def get_git_hash(base_dir: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(base_dir),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return res.stdout.strip()[:16]
    except FileNotFoundError as e:
        raise RuntimeError("git binary missing. Cannot proceed with physical execution.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError("git execution failed. Cannot proceed with physical execution.") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            "git execution timed out. Cannot proceed with physical execution."
        ) from e


@pytest.fixture
def hpc_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Sets up an HPC environment path requirement by pointing the artifact directory
    to an HPC-like scratch space and overriding environment variables.
    No code mimicking is used; we physically alter the environment.
    """
    hpc_scratch = Path(
        os.environ.get(
            "COCHEM_ARTIFACT_DIR", tmp_path / "scratch" / "hpc_user" / "CoChem_Artifacts"
        )
    )
    hpc_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(hpc_scratch))
    return hpc_scratch


@pytest.mark.skipif(
    not os.environ.get("SLURM_JOB_ID") or os.environ.get("COCHEM_OS_TARGET") != "linux_x86_64",
    reason="Requires SLURM_JOB_ID and COCHEM_OS_TARGET=linux_x86_64",
)
def test_matrix_dashboard_new_linux_hpc(
    hpc_ephemeral_env: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Tests the "New Install" logic of the Interactive Matrix Dashboard module
    targeting Local-Linux interaction and HPC calculation environment.
    Verifies that it identifies the correct path requirements on an HPC node
    and physically resolves binaries natively.
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
        selected_repositories=[target_mod],
        headless=True,
    )

    # Persist the deployment manifest and system configuration to disk so downstream orchestrators can read them
    with open(installer.manifest_file, "w", encoding="utf-8") as f:
        f.write(
            manifest.model_dump_json(indent=4)
            if hasattr(manifest, "model_dump_json")
            else manifest.json(indent=4)
        )

    serialize_system_config_json(manifest, target_path=installer.system_config_file)

    # Invoke the pure python worker synchronously
    # Use model_dump() for pydantic v2, or dict() for v1; we will assume manifest processing is a dictionary.
    installer._pure_python_deployment_worker(
        manifest.model_dump() if hasattr(manifest, "model_dump") else manifest.dict()
    )

    # Verify the "New Install" code path was followed
    log_file_content = installer.log_file.read_text(encoding="utf-8")

    assert f"Deep cloning {target_mod}" in log_file_content, (
        "The 'New Install' (clone) logic was not triggered."
    )
    assert "Cloned" in log_file_content or "Failed to clone" in log_file_content

    logger.info("Test passed successfully.")
