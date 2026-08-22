import os
import shutil
import pytest
from pathlib import Path

from cochem_base.config_loader import resolve_conda_executable
from setup.cochem_base_setup import provision_silo

def resolve_artifact_path(value):
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()

def test_new_install_default_paths(tmp_path: Path):
    """
    Test [UI Cell 3 - Silo Setup] Test "New Install" -> "Default paths execution"
    Executes the equivalent logic of clicking "New Install" -> "Create & Provision" 
    using default paths (via env vars mapped to tmp_path for safety).
    """
    # 1. Setup default paths (mapping to tmp_path to be a real physical structure but safe)
    os.environ['COCHEM_ARTIFACT_DIR'] = str(tmp_path / 'CoChem_Artifacts')
    target_path = resolve_artifact_path(os.environ['COCHEM_ARTIFACT_DIR'])
    
    conda_exe = resolve_conda_executable(required=False)
    if conda_exe:
        os.environ['COCHEM_CONDA_EXE'] = str(conda_exe)
        
    silo_path = target_path / 'Silos'
    
    # Simulate UI Cell 3 "Create & Provision" logic
    if silo_path.exists():
        shutil.rmtree(silo_path, ignore_errors=True)
    silo_path.mkdir(parents=True, exist_ok=True)
    
    # Instead of setup_cochem_base() which creates ipywidgets,
    # we call the actual backend provision_silo function to execute the logic.
    success, env_dir, already_provisioned = provision_silo(str(target_path))
    
    assert success is True, "Silo provisioning failed."
    assert env_dir.exists(), f"Environment directory not found at {env_dir}"
    assert env_dir == silo_path / 'cochem_base_silo', "Environment directory path mismatch"
    assert already_provisioned is False, "Expected fresh installation, but environment was already provisioned."
    
    # Validate the generated environment has conda-meta
    conda_meta_path = env_dir / "conda-meta"
    assert conda_meta_path.exists() and conda_meta_path.is_dir(), "conda-meta directory is missing"
    assert any(conda_meta_path.glob("*.json")), "No conda-meta JSON files found, environment might be empty"

