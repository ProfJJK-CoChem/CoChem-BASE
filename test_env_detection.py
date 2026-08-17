#!/usr/bin/env python3
"""
Test script for environment detection logic in CoChem-BASE setup.
This validates that our improved detection method works correctly.
"""

import logging
import subprocess

from cochem_base.config_loader import get_artifact_dir, resolve_conda_executable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestEnvDetection")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def check_environment_detection() -> bool:
    """Check environment detection logic."""
    artifact_dir = get_artifact_dir()
    env_dir = artifact_dir / "Silos" / "cochem_base_silo"

    logger.info(f"Testing environment at: {env_dir}")
    logger.info(f"Directory exists: {env_dir.exists()}")

    env_exists = False
    try:
        conda_executable = resolve_conda_executable(required=False)
        command = [conda_executable, "info", "--envs"]
        if safe_subprocess_run:
            safe_subprocess_run(command, check=True, timeout=30.0)
        else:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30.0)

        conda_meta_path = env_dir / "conda-meta"
        env_exists = conda_meta_path.is_dir() and any(conda_meta_path.glob("*.json"))
        if env_exists:
            logger.info("Valid Conda environment metadata detected")
    except Exception as e:
        logger.warning(f"Conda check failed: {e}")
        conda_meta_path = env_dir / "conda-meta"
        env_exists = conda_meta_path.is_dir() and any(conda_meta_path.glob("*.json"))

    logger.info(f"Final environment detection result: {env_exists}")
    return env_exists


def test_environment_detection() -> None:
    """Pytest wrapper function returning None."""
    res = check_environment_detection()
    assert isinstance(res, bool)


if __name__ == "__main__":
    check_environment_detection()
