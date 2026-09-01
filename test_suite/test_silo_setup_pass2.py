"""
Physical verification test suite for CoChem-BASE Silo Setup Pass 2.
Validates both fresh installation (Pass 1) and idempotent second-pass bypass (Pass 2)
against real physical environments, process locking, and repo configuration isolation.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Generator

import filelock
import psutil
import pytest

from cochem_base.config_loader import (
    BASE_ROOT,
    resolve_conda_executable,
    resolve_mapped_path,
)
from setup.cochem_base_setup import provision_silo

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def sweep_zombie_processes() -> None:
    """Strictly sweep zombie processes without bare exceptions."""
    try:
        current_proc = psutil.Process()
        children = current_proc.children(recursive=True)
        for child in children:
            try:
                if child.is_running():
                    child.kill()
                    child.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        pass


@pytest.fixture
def isolated_silo_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[tuple[Path, Path], None, None]:
    """
    Fixture to isolate testing environment, set environment variables safely via monkeypatch,
    backup and restore repo-level .cochem_env.json, and sweep zombie processes on teardown.
    """
    artifact_root = tmp_path / "CoChem_Artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)

    # 1. Isolate environment variables via monkeypatch
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(artifact_root))
    conda_exe = resolve_conda_executable(required=False)
    if conda_exe:
        monkeypatch.setenv("COCHEM_CONDA_EXE", str(conda_exe))

    # 2. Backup repository-level .cochem_env.json if present
    cfg_path = BASE_ROOT / ".cochem_env.json"
    cfg_existed = cfg_path.exists()
    backup_cfg_content: str | None = None
    if cfg_existed:
        try:
            backup_cfg_content = cfg_path.read_text(encoding="utf-8")
        except Exception as err:
            logger.warning("Failed to read existing .cochem_env.json for backup: %s", err)

    resolved_target = resolve_mapped_path(str(artifact_root), Path.home())

    try:
        yield resolved_target, tmp_path
    finally:
        # Teardown: sweep zombies
        sweep_zombie_processes()

        # Restore or clean up .cochem_env.json
        if cfg_existed and backup_cfg_content is not None:
            try:
                cfg_path.write_text(backup_cfg_content, encoding="utf-8")
            except Exception as err:
                logger.warning("Failed to restore .cochem_env.json: %s", err)
        elif not cfg_existed and cfg_path.exists():
            try:
                cfg_path.unlink(missing_ok=True)
            except Exception as err:
                logger.warning("Failed to remove temporary .cochem_env.json: %s", err)


def test_new_install_default_paths(isolated_silo_env: tuple[Path, Path]) -> None:
    """
    Test [UI Cell 3 - Silo Setup] Test "New Install" -> "Default paths execution"
    and idempotent Pass 2 execution.
    Executes the equivalent logic of clicking "New Install" -> "Create & Provision"
    using default paths (via env vars mapped to tmp_path for safety), verifies physical
    conda-meta presence and repo config write, and verifies idempotent bypass on Pass 2.
    """
    target_path, tmp_path = isolated_silo_env
    silo_path = target_path / "Silos"
    lock_file = tmp_path / "cochem_silo_setup_pass2.lock"
    lock = filelock.FileLock(str(lock_file), timeout=120)

    with lock:
        # Simulate UI Cell 3 "Create & Provision" logic: start with clean silo directory
        if silo_path.exists():
            shutil.rmtree(silo_path, ignore_errors=True)
        silo_path.mkdir(parents=True, exist_ok=True)

        # --- PASS 1: Fresh Installation ---
        success, env_dir, already_provisioned = provision_silo(str(target_path))

        assert success is True, "Silo provisioning failed on fresh installation."
        assert env_dir.exists(), f"Environment directory not found at {env_dir}"
        assert env_dir == silo_path / "cochem_base_silo", "Environment directory path mismatch"
        assert already_provisioned is False, "Expected fresh installation (already_provisioned=False)."

        # Validate the generated environment has physical conda-meta
        conda_meta_path = env_dir / "conda-meta"
        assert conda_meta_path.exists() and conda_meta_path.is_dir(), "conda-meta directory is missing"
        assert any(conda_meta_path.glob("*.json")), "No conda-meta JSON files found, environment might be empty"

        # Validate .cochem_env.json was recorded and contains valid artifact directory
        cfg_path = BASE_ROOT / ".cochem_env.json"
        assert cfg_path.exists(), ".cochem_env.json was not created by provision_silo"
        cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert cfg_data.get("artifact_dir") == str(target_path), (
            f"Config artifact_dir mismatch: {cfg_data.get('artifact_dir')} != {target_path}"
        )

        # --- PASS 2: Idempotent Second-Pass Execution ---
        success_p2, env_dir_p2, already_provisioned_p2 = provision_silo(str(target_path))

        assert success_p2 is True, "Silo provisioning failed on second idempotent pass."
        assert env_dir_p2 == env_dir, "Environment directory path changed on second pass."
        assert already_provisioned_p2 is True, "Expected idempotent bypass (already_provisioned=True) on second pass."
        assert env_dir_p2.exists(), f"Environment directory missing on second pass: {env_dir_p2}"
        assert (env_dir_p2 / "conda-meta").is_dir(), "conda-meta missing after second pass verification"


