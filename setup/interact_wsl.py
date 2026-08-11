#!/usr/bin/env python3
"""
CoChem-BASE: Interaction Environment Setup (Local-Windows / WSL)
Provisions the UI dependencies, air-gap directories, and registers 
the WSL interaction layer into the Golden Registry without Docker abstractions.
"""

import os
import sys
import json
import subprocess
import shutil
import logging
from pathlib import Path
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-InteractWSL")

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
        pass
    return False


def check_wsl2_installation() -> bool:
    """Check if WSL2 is installed and available on Windows system."""
    try:
        wsl_path = Path("C:/Windows/System32/wsl.exe")
        if not wsl_path.exists():
            return False
        return True
    except Exception:
        return False


def request_admin_elevation() -> bool:
    """Request elevation to Administrator privileges using ctypes."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def bootstrap_wsl2_if_missing() -> bool:
    """Bootstrap WSL2 if not installed on Windows system."""
    logger.info("Checking for WSL2 installation...")

    if sys.platform != "win32":
        return False

    if check_wsl2_installation():
        logger.info("WSL2 is already installed on this system.")
        return True

    logger.warning("WSL2 not found on Windows system. Initiating installation...")
    logger.info("This will trigger the UAC elevation prompt and install WSL2.")

    if not request_admin_elevation():
        logger.error("Admin privileges required to install WSL2. Please run this script as Administrator.")
        return False

    try:
        logger.info("Installing WSL2 and Ubuntu distribution...")
        cmd = ["powershell", "-Command", "wsl --install -d Ubuntu"]
        if safe_subprocess_run:
            safe_subprocess_run(cmd, check=True, timeout=120.0)
        else:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120.0)

        logger.info("WSL2 installation initiated. Please reboot your system and re-run this script.")
        return True
    except Exception as e:
        logger.error(f"Failed to install WSL2: {e}")
        return False


def provision_airgap_directories() -> Path:
    """Constructs the strict CoChem_Artifacts directory tree to replace Docker volume mounts."""
    artifact_dir = get_artifact_dir()
    subdirs = [
        artifact_dir / "Registry" / "Engines",
        artifact_dir / "Registry" / "Modules",
        artifact_dir / "Logs",
        artifact_dir / "Workspaces"
    ]

    for directory in subdirs:
        directory.mkdir(parents=True, exist_ok=True)

    logger.info(f"Air-Gap Directories Provisioned at: {artifact_dir}")
    return artifact_dir


def install_ui_dependencies() -> None:
    """Installs the core ipywidgets and telemetry libraries required by CoChem-UNITY/DOCK."""
    logger.info("Bootstrapping Interaction UI Dependencies...")

    try:
        cmd_ver = [sys.executable, "-m", "pip", "--version"]
        if safe_subprocess_run:
            safe_subprocess_run(cmd_ver, check=True, timeout=10.0)
        else:
            subprocess.run(cmd_ver, check=True, capture_output=True, timeout=10.0)
    except Exception:
        logger.error("PIP not found in WSL Python.")
        logger.warning("WSL Fix: Run 'sudo apt-get update && sudo apt-get install -y python3-pip' in your WSL terminal.")
        sys.exit(1)

    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab"]

    try:
        cmd_inst = [sys.executable, "-m", "pip", "install", "--user"] + required_packages
        if safe_subprocess_run:
            safe_subprocess_run(cmd_inst, check=True, timeout=120.0)
        else:
            subprocess.run(cmd_inst, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', timeout=120.0)
        logger.info("UI Dependencies satisfied.")
    except Exception as e:
        logger.error(f"FATAL: Failed to provision UI packages. Error: {e}")
        sys.exit(1)


def register_interaction_state(artifact_dir: Path) -> None:
    """Updates the Golden Registry to confirm WSL Interaction provisioning."""
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"

    if registry_path.exists():
        with open(registry_path, 'r', encoding='utf-8') as f:
            try:
                registry = json.loads(f.read())
            except json.JSONDecodeError:
                registry = {"interaction_environment": None, "calculation_environment": None, "silos": {}}
    else:
        registry = {"interaction_environment": None, "calculation_environment": None, "silos": {}}

    registry["interaction_environment"] = "Local-Windows (WSL)"
    registry["interaction_ready"] = True

    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=4)

    logger.info(f"Interaction State locked into Golden Registry: {registry_path}")


def run_interaction_setup() -> None:
    logger.info("=======================================================")
    logger.info(" CoChem-BASE: WSL Interaction Environment Provisioning ")
    logger.info("=======================================================\n")

    if sys.platform == "win32":
        if not verify_wsl_kernel():
            logger.warning("Detected native Windows execution. Attempting to bootstrap WSL2...")
            if not bootstrap_wsl2_if_missing():
                logger.error("Failed to bootstrap WSL2. Please install WSL2 manually and re-run this script.")
                sys.exit(1)
            else:
                logger.info("WSL2 bootstrapping initiated. Reboot your system, then re-run this script in WSL Ubuntu terminal.")
                sys.exit(0)
        else:
            logger.info("Running inside WSL kernel - proceeding with normal setup...")
    else:
        if not verify_wsl_kernel():
            logger.error("FATAL: Target environment is not WSL. Please run interact_mac.py or interact_linux.py instead.")
            sys.exit(1)

    artifact_dir = provision_airgap_directories()
    install_ui_dependencies()
    register_interaction_state(artifact_dir)

    logger.info("WSL Interaction Layer successfully established. Ready for UI handoff.")


if __name__ == "__main__":
    run_interaction_setup()