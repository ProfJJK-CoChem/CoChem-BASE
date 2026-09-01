#!/usr/bin/env python3
"""
CoChem-BASE: Interaction Environment Setup (Local-Windows / WSL)
Provisions the UI dependencies, air-gap directories, and registers
the WSL interaction layer into the Golden Registry without Docker abstractions.
"""

import atexit
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from cochem_base.config_loader import get_artifact_dir, resolve_wsl_executable

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-InteractWSL")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore


def cleanup_zombies() -> None:
    """Sweeps for and terminates any zombie subprocesses spawned during setup."""
    try:
        import psutil
        for child in psutil.Process().children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    child.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception:
        pass

atexit.register(cleanup_zombies)


def verify_wsl_kernel() -> bool:
    """Validates that the script is executing inside a Windows Subsystem for Linux kernel."""
    version_path = Path(os.sep) / "proc" / "version"
    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            version_info = f.read().lower()
            if "microsoft" in version_info or "wsl" in version_info:
                return True
    except FileNotFoundError:
        logger.debug("Not a Linux/WSL environment, /proc/version missing.")
    return False


def check_wsl2_installation() -> bool:
    """Check if WSL2 is installed and available on Windows system."""
    wsl_executable = resolve_wsl_executable()
    return sys.platform == "win32" and bool(wsl_executable)


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
        wsl_executable = resolve_wsl_executable(required=True)
        cmd = [str(wsl_executable), "--install", "-d", "Ubuntu"]
        if safe_subprocess_run is not None:
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
        if safe_subprocess_run is not None:
            safe_subprocess_run(cmd_ver, check=True, timeout=10.0)
        else:
            subprocess.run(cmd_ver, check=True, capture_output=True, timeout=10.0)
    except Exception:
        logger.error("PIP not found in WSL Python.")
        logger.warning("WSL Fix: Run 'sudo apt-get update && sudo apt-get install -y python3-pip' in your WSL terminal.")
        sys.exit(1)

    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab", "pydantic>=2.0.0"]

    try:
        cmd_inst = [sys.executable, "-m", "pip", "install", "--user"] + required_packages
        if safe_subprocess_run is not None:
            safe_subprocess_run(cmd_inst, check=True, timeout=120.0)
        else:
            subprocess.run(cmd_inst, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', timeout=120.0)
        
        # Invalidate caches so the newly installed pydantic is available for import in the current process
        import importlib
        import site
        importlib.invalidate_caches()
        
        logger.info("UI Dependencies satisfied.")
    except Exception as e:
        logger.error(f"FATAL: Failed to provision UI packages. Error: {e}")
        sys.exit(1)


def register_interaction_state(artifact_dir: Path) -> None:
    """Updates the Golden Registry to confirm WSL Interaction provisioning."""
    
    from pydantic import BaseModel, Field
    
    class InteractionRegistry(BaseModel):
        interaction_environment: Optional[str] = None
        calculation_environment: Optional[str] = None
        interaction_ready: Optional[bool] = None
        silos: Dict[str, Any] = Field(default_factory=dict)
        
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"

    if registry_path.exists():
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                content = f.read()
                registry = InteractionRegistry.model_validate_json(content)
        except Exception as e:
            logger.warning(f"Failed to parse existing registry, creating new. Error: {e}")
            registry = InteractionRegistry()
    else:
        registry = InteractionRegistry()

    registry.interaction_environment = "Local-Windows (WSL)"
    registry.interaction_ready = True

    with open(registry_path, 'w', encoding='utf-8') as f:
        f.write(registry.model_dump_json(indent=4))

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
