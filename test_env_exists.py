#!/usr/bin/env python3
"""
Script to test if a conda environment exists at a specific path.
This is used to optimize the setup process by avoiding unnecessary reinstallation.
"""

import logging
import subprocess
import sys
from pathlib import Path

from cochem_base.config_loader import resolve_conda_executable, resolve_mapped_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestEnvExists")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def check_conda_environment_exists(env_path: str) -> bool:
    """
    Check if a conda environment exists at the specified path.

    Args:
        env_path (str): The path where the conda environment should exist

    Returns:
        bool: True if environment exists, False otherwise
    """
    env_dir = resolve_mapped_path(env_path, Path.home())
    try:
        conda_executable = resolve_conda_executable(required=False)
        command = [conda_executable, "info", "--envs"]
        if safe_subprocess_run:
            safe_subprocess_run(command, check=True, timeout=30.0)
        else:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=30.0)

    except subprocess.CalledProcessError as e:
        logger.warning(f"Conda command failed: {e}")
    except Exception as e:
        logger.warning(f"Error checking environment: {e}")

    conda_meta_path = env_dir / "conda-meta"
    exists = conda_meta_path.is_dir() and any(conda_meta_path.glob("*.json"))
    if exists:
        logger.info(f"Valid Conda environment found at: {env_dir}")
    return exists


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python test_env_exists.py <environment_path>")
        sys.exit(1)

    target_env_path = sys.argv[1]
    exists = check_conda_environment_exists(target_env_path)

    if exists:
        logger.info("Environment exists")
        sys.exit(0)
    else:
        logger.info("Environment does not exist")
        sys.exit(1)
