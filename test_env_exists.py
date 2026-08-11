#!/usr/bin/env python3
"""
Script to test if a conda environment exists at a specific path.
This is used to optimize the setup process by avoiding unnecessary reinstallation.
"""

import sys
import subprocess
import logging
from pathlib import Path

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
    try:
        if safe_subprocess_run:
            result = safe_subprocess_run(["conda", "info", "--envs"], check=True, timeout=30.0)
        else:
            result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True, timeout=30.0)

        if env_path in result.stdout:
            logger.info(f"Conda environment found at: {env_path}")
            return True

        env_dir = Path(env_path)
        if env_dir.exists():
            logger.info(f"Environment directory found at: {env_path}")
            return True

    except subprocess.CalledProcessError as e:
        logger.warning(f"Conda command failed: {e}")
        env_dir = Path(env_path)
        if env_dir.exists():
            logger.info(f"Environment directory found at: {env_path} (fallback)")
            return True

    except Exception as e:
        logger.warning(f"Error checking environment: {e}")

    return False


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