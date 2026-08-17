import os
import time
import subprocess
import logging
import psutil
import atexit
import shutil
import tempfile
from pathlib import Path
import pytest
from pydantic import BaseModel, Field

from cochem_base.interfaces.cochem_unity_installer_dashboard import SynapInstallerGUI, ECOSYSTEM_REGISTRY
from cochem_base.config_loader import get_base_root

logger = logging.getLogger(__name__)

# Verify that zombie process sweeping is properly executed using psutil within atexit 
# strictly catching psutil.NoSuchProcess and psutil.AccessDenied.
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

@pytest.fixture
def codespaces_mac_ephemeral_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Simulates a Codespaces interaction + MacOS calculation environment.
    """
    cs_mac_scratch = tmp_path / "scratch" / "codespaces_mac" / "CoChem_Artifacts"
    cs_mac_scratch.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(cs_mac_scratch))
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setenv("COCHEM_CALCULATION_OS", "macos")
    return cs_mac_scratch

def get_real_orca_binary() -> str:
    # Attempt to resolve physically
    orca_path = shutil.which("orca")
    if not orca_path:
        env_orca = os.environ.get("ORCA_PATH")
        if env_orca and Path(env_orca).exists():
            orca_path = env_orca
    if not orca_path:
        raise RuntimeError("[ERR_MISSING_DATA] ORCA binary not found via PATH or ORCA_PATH env var. Cannot proceed with physical execution.")
    return orca_path

def test_matrix_dashboard_new_codespaces_mac(codespaces_mac_ephemeral_env: Path, caplog: pytest.LogCaptureFixture):
    """
    Tests the 'New Install -> Set Paths & Test' logic of the Interactive Matrix Dashboard module
    targeting Codespaces interaction and Local-MacOS (OrbStack) calculation environment.
    Zero-Mock policy enforced. Real binaries and physical resolution must be utilized.
    """
    caplog.set_level(logging.INFO)
    
    installer = SynapInstallerGUI()
    
    # Asserting artifact dir was dynamically injected properly
    assert str(codespaces_mac_ephemeral_env) in str(installer.artifact_dir)
    assert installer.module_registry.exists()
    
    # Simulate User Interaction for Codespaces + Local-MacOS (OrbStack)
    installer.interact_target.value = "Codespaces"
    installer.calc_target.value = "Local-MacOS (OrbStack)"
    
    # Physically resolve ORCA
    try:
        orca_path = get_real_orca_binary()
    except RuntimeError as e:
        pytest.fail(str(e))
        
    installer.host_orca_path.value = orca_path
    
    # Disable unneeded repos for faster execution
    for prog, cb in installer.buttons.items():
        if not ECOSYSTEM_REGISTRY[prog]["mandatory"]:
            cb.value = False
            
    # We will invoke the native ORCA validation directly via NamedTemporaryFile to avoid string injection
    # and to verify "Set Paths & Test" physically.
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.inp', delete=False) as tf:
        tf.write("! SP STO-3G\n*xyz 0 1\nHe 0 0 0\n*\n")
        tf.flush()
        inp_path = tf.name

    try:
        # No shell=True. Use argument list (no string injection).
        result = subprocess.run(
            [orca_path, inp_path],
            capture_output=True,
            text=True,
            timeout=120.0,
            check=True
        )
        assert result.returncode == 0 or "TERMINATED NORMALLY" in result.stdout.upper() or "O   R   C   A" in result.stdout.upper()
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Physical ORCA verification failed (timeout): {e}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Physical ORCA verification failed (process error): {e}\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
    finally:
        Path(inp_path).unlink(missing_ok=True)
        
    # Trigger _on_submit which executes deployment natively via thread
    # We will call it manually to wait for it synchronously instead of running the async UI version
    manifest_payload = {
        "version": "2026.2",
        "git_provenance_hash": installer._get_git_hash(),
        "interaction_environment": installer.interact_target.value,
        "calculation_environment": installer.calc_target.value,
        "orca_tarball_path": installer.host_orca_path.value,
        "selected_repositories": [mod for mod, cb in installer.buttons.items() if cb.value]
    }
    
    installer._pure_python_deployment_worker(manifest_payload)
    
    # Validate
    log_file_content = installer.log_file.read_text(encoding="utf-8")
    assert "Cloned" in log_file_content or "updated successfully" in log_file_content or "Bypassing clone" in log_file_content
    
    logger.info("Test passed successfully.")
