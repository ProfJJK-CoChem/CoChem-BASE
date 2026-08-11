#!/usr/bin/env python3
"""
CoChem-BASE Silo Setup Script
This script creates the conda environment for CoChem-BASE.
"""

import subprocess
import sys
import os
import json
import logging
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-SiloSetup")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def setup_conda_silo() -> bool:
    """Setup the conda silo environment"""

    logger.info("==============================================================")
    logger.info(" 🧪 CoChem-BASE: Conda Silo Environment Creation")
    logger.info("==============================================================\n")

    artifact_dir = get_artifact_dir()
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"

    logger.info(f"Artifact Directory: {artifact_dir}")
    logger.info(f"Silo Directory: {silo_dir}\n")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    silo_dir.parent.mkdir(parents=True, exist_ok=True)

    conda_meta_path = silo_dir / "conda-meta"

    env_valid = False

    if conda_meta_path.exists():
        try:
            meta_files = list(conda_meta_path.glob("*.json"))
            if len(meta_files) > 0:
                env_valid = True
            else:
                logger.warning("Conda-meta directory exists but is empty - treating as invalid")
        except Exception as e:
            logger.warning(f"Error checking conda-meta: {e}")

    if env_valid:
        logger.info(f"Conda environment already exists at: {silo_dir}")
        logger.info("   Skipping creation process")
        return True

    logger.info("Environment not found or invalid, proceeding with creation...")
    logger.info("Creating new conda environment...")

    try:
        create_cmd = [
            "conda", "create", "--prefix", str(silo_dir),
            "-c", "conda-forge", "python=3.10", "numpy", "pandas", 
            "scipy", "matplotlib", "jupyter", "ipywidgets",
            "openbabel", "rdkit", "ase", "pyyaml", "requests",
            "--yes"
        ]

        logger.info(f"Running command: {' '.join(create_cmd)}")
        if safe_subprocess_run:
            result = safe_subprocess_run(create_cmd, check=True, timeout=300.0)
        else:
            result = subprocess.run(create_cmd, check=True, capture_output=True, text=True, timeout=300.0)
        logger.info(result.stdout)

        install_cmd = [
            "conda", "install", "--prefix", str(silo_dir),
            "-c", "conda-forge", "mypy", "black", "flake8",
            "--yes"
        ]

        logger.info("Installing additional packages...")
        if safe_subprocess_run:
            result = safe_subprocess_run(install_cmd, check=True, timeout=300.0)
        else:
            result = subprocess.run(install_cmd, check=True, capture_output=True, text=True, timeout=300.0)
        logger.info(result.stdout)

        pip_install = [
            sys.executable, "-m", "pip", "install",
            "openbabel", "pybel", "chemformula", "periodictable"
        ]

        logger.info("Installing pip packages...")
        if safe_subprocess_run:
            result = safe_subprocess_run(pip_install, check=True, timeout=300.0)
        else:
            result = subprocess.run(pip_install, check=True, capture_output=True, text=True, timeout=300.0)
        logger.info(result.stdout)

        logger.info(f"Conda environment created successfully at: {silo_dir}")
        return True

    except Exception as e:
        logger.error(f"Error creating conda environment: {e}")
        return False


if __name__ == "__main__":
    setup_conda_silo()
