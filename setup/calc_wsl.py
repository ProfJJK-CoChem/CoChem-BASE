#!/usr/bin/env python3
"""
CoChem-BASE: Calculation Environment Setup (Local-Windows / WSL)
Provisions the ORCA engine and OpenMPI pathway natively inside WSL.
Extracts archives, resolves paths, and locks the state into the Golden Registry.
"""

import os
import sys
import json
import subprocess
import shutil
import logging
import re
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-WSLSetup")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def verify_wsl_kernel() -> bool:
    """Validates that the script is executing inside a Windows Subsystem for Linux kernel."""
    try:
        with open('/proc/version', 'r', encoding='utf-8') as f:
            version_info = f.read().lower()
            if "microsoft" in version_info or "wsl" in version_info:
                return True
    except FileNotFoundError:
        """Implementation pending"""
    return False


def check_openmpi_version(mpi_path: str) -> str:
    """Check the version of OpenMPI and return it."""
    try:
        if safe_subprocess_run:
            result = safe_subprocess_run([mpi_path, "--version"], capture_output=True, text=True, check=True, timeout=10.0)
        else:
            result = subprocess.run([mpi_path, "--version"], capture_output=True, text=True, encoding='utf-8', check=True, timeout=10.0)
        version_line = result.stdout.split('\n')[0]
        match = re.search(r'v(\d+\.\d+)', version_line)
        if match:
            return match.group(1)
        return "unknown"
    except Exception:
        return "unknown"


def provision_openmpi() -> str:
    """Locates OpenMPI or autonomously installs it with Active Repair."""
    logger.info("Probing for OpenMPI (mpirun)...")
    mpi_path = shutil.which("mpirun")

    if not mpi_path:
        logger.warning("OpenMPI not found in WSL $PATH.")
        logger.info("Initiating Autonomous OpenMPI Installation & Path Binder...")

        try:
            logger.info("Installing OpenMPI 4.1.x via apt-get...")
            if safe_subprocess_run:
                safe_subprocess_run(["sudo", "apt-get", "update"], check=True, timeout=60.0)
                safe_subprocess_run(["sudo", "apt-get", "install", "-y", "openmpi-bin", "libopenmpi-dev"], check=True, timeout=120.0)
            else:
                subprocess.run(["sudo", "apt-get", "update"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60.0)
                subprocess.run(["sudo", "apt-get", "install", "-y", "openmpi-bin", "libopenmpi-dev"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120.0)

            logger.info("OpenMPI installation completed successfully.")

            mpi_path = shutil.which("mpirun")
            if not mpi_path:
                logger.error("Failed to locate mpirun after installation.")
                sys.exit(1)

            version = check_openmpi_version(mpi_path)
            logger.info(f"OpenMPI verified at: {mpi_path} (Version: {version})")

            if not version.startswith("4.1"):
                logger.warning("Warning: OpenMPI version is not 4.1.x. ORCA 6.1.1 requires this specific version.")

            return mpi_path

        except (subprocess.CalledProcessError, Exception) as e:
            logger.error(f"Failed to install OpenMPI: {e}")
            logger.warning("WSL Fix: Please manually run 'sudo apt-get update && sudo apt-get install openmpi-bin libopenmpi-dev' in your terminal.")
            sys.exit(1)
    else:
        version = check_openmpi_version(mpi_path)
        logger.info(f"OpenMPI found at: {mpi_path} (Version: {version})")

        if not version.startswith("4.1"):
            logger.warning("Warning: OpenMPI version is not 4.1.x. ORCA 6.1.1 requires this specific version.")

        return mpi_path


def provision_orca(engine_dir: Path) -> str:
    """Finds existing ORCA or extracts a .tar.xz archive using the Siloed Linux Archive protocol."""
    logger.info("Probing for ORCA Linux Engine...")

    orca_bin = engine_dir / "orca"
    if orca_bin.exists() and os.access(orca_bin, os.X_OK):
        logger.info(f"Active ORCA binary found at: {orca_bin}")
        return str(orca_bin)

    for subdir in engine_dir.iterdir():
        if subdir.is_dir():
            potential_bin = subdir / "orca"
            if potential_bin.exists() and os.access(potential_bin, os.X_OK):
                logger.info(f"Active ORCA binary found at: {potential_bin}")
                return str(potential_bin)

    archives = list(engine_dir.glob("orca*.tar.xz")) + list(engine_dir.glob("ORCA*.tar.xz"))
    if not archives:
        logger.error(f"ORCA engine not found. No .tar.xz archives detected in {engine_dir}")
        logger.warning("Please drop the Linux ORCA archive into the Registry/Engines folder and rerun.")
        sys.exit(1)

    target_archive = archives[0]
    logger.info(f"Found ORCA Archive: {target_archive.name}. Initiating extraction...")

    try:
        cmd = ["tar", "-xf", str(target_archive), "--no-same-owner", "-C", str(engine_dir)]
        if safe_subprocess_run:
            safe_subprocess_run(cmd, check=True, timeout=120.0)
        else:
            subprocess.run(cmd, check=True, timeout=120.0)
        logger.info("Archive extraction complete.")

        for path in engine_dir.rglob("orca"):
            if path.is_file() and os.access(path, os.X_OK):
                logger.info(f"Successfully staged and verified ORCA at: {path}")
                return str(path)

        logger.error("Extraction succeeded but 'orca' binary could not be located inside the folder.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Extraction failed. Is the archive corrupted? Error: {e}")
        sys.exit(1)


def register_calculation_state(mpi_path: str, orca_path: str) -> None:
    """Updates the Golden Registry with the native WSL execution pathways."""
    registry_path = get_artifact_dir() / "Registry" / "cochem_system_config.json"

    if registry_path.exists():
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.loads(f.read())
    else:
        registry = {"engines": {}}

    if "engines" not in registry:
        registry["engines"] = {}

    registry["calculation_environment"] = "Local-Windows (WSL)"
    registry["engines"]["mpirun"] = {
        "status": "ready",
        "path": mpi_path
    }
    registry["engines"]["orca"] = {
        "status": "ready",
        "path": orca_path
    }
    registry["calculation_ready"] = True

    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=4)

    logger.info(f"Calculation State & Engine Paths locked into Golden Registry: {registry_path}")


def run_calculation_setup() -> None:
    logger.info("=======================================================")
    logger.info(" CoChem-BASE: WSL Calculation Environment Provisioning ")
    logger.info("=======================================================\n")

    if not verify_wsl_kernel():
        logger.error("FATAL: Target environment is not WSL. Please run calc_mac.py or calc_linux.py instead.")
        sys.exit(1)

    engine_dir = get_artifact_dir() / "Registry" / "Engines"
    engine_dir.mkdir(parents=True, exist_ok=True)

    mpi_path = provision_openmpi()
    orca_path = provision_orca(engine_dir)
    register_calculation_state(mpi_path, orca_path)

    logger.info("WSL Calculation Layer successfully established. Engines are ready for execution.")


if __name__ == "__main__":
    run_calculation_setup()