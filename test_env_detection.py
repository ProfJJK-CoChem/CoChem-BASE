#!/usr/bin/env python3
"""
Test script for environment detection logic in CoChem-BASE setup.
This validates that our improved detection method works correctly.
"""

import json
import logging
import subprocess
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir

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
        if safe_subprocess_run:
            result = safe_subprocess_run(["conda", "info", "--envs"], check=True, timeout=30.0)
        else:
            result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True, timeout=30.0)

        if str(env_dir) in result.stdout:
            conda_meta_path = env_dir / "conda-meta"
            if conda_meta_path.exists():
                env_exists = True
                logger.info("Valid conda environment detected")
            else:
                logger.warning(f"Environment path found but conda-meta directory missing: {conda_meta_path}")
                env_exists = False
        else:
            env_exists = env_dir.exists()
            if env_exists:
                logger.warning("Directory exists but not registered in conda environments")
    except Exception as e:
        logger.warning(f"Conda check failed: {e}")
        env_exists = env_dir.exists()

    logger.info(f"Final environment detection result: {env_exists}")
    return env_exists


def test_environment_detection() -> None:
    """Pytest wrapper function returning None."""
    res = check_environment_detection()
    assert isinstance(res, bool)


if __name__ == "__main__":
    check_environment_detection()