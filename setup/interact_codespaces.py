#!/usr/bin/env python3
"""
CoChem-BASE Stage 0.2a: Interaction Environment Setup (Codespaces)
Provisions the UI dependencies, establishes the Air-Gap structure, and 
enforces strict WebGL memory constraints based on the host cloud instance.
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Dict, Any
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-InteractCodespaces")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def verify_codespace_kernel() -> bool:
    """Validates execution within a GitHub Codespaces or DevContainer context."""
    return Path("/workspaces").exists() or "CODESPACES" in os.environ


def provision_airgap_directories() -> Path:
    """Constructs the Air-Gap directory tree. Defaults to the user home to isolate from Git."""
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
    """Bootstraps missing pip dependencies for the Codespace UI."""
    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab"]
    logger.info("Bootstrapping Codespace Interaction UI Dependencies...")

    try:
        cmd = [sys.executable, "-m", "pip", "install", "--user"] + required_packages
        if safe_subprocess_run:
            safe_subprocess_run(cmd, check=True, timeout=120.0)
        else:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', timeout=120.0)
        logger.info("UI Dependencies satisfied.")
    except Exception as e:
        logger.error(f"FATAL: Failed to provision UI packages. Error: {e}")
        sys.exit(1)


def probe_hardware_memory() -> Tuple[str, float]:
    """Probes available Codespace RAM and adjusts the UI rendering fidelity."""
    import psutil

    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    logger.info(f"Codespace RAM Detected: {total_ram_gb:.2f} GB")

    render_mode = "sparse" if total_ram_gb < 8.0 else "full"

    if render_mode == "sparse":
        logger.warning("Memory < 8GB. Forcing 'sparse' UI render mode to prevent WebGL browser crashes.")
    else:
        logger.info("Memory >= 8GB. 'full' WebGL UI render mode enabled.")

    return render_mode, total_ram_gb


def register_interaction_state(artifact_dir: Path, render_mode: str, ram_gb: float) -> None:
    """Updates the Golden Registry to confirm Codespace Interaction provisioning."""
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"

    if registry_path.exists():
        with open(registry_path, 'r', encoding='utf-8') as f:
            try:
                registry = json.loads(f.read())
            except json.JSONDecodeError:
                registry = {}
    else:
        registry = {}

    registry.setdefault("silos", {})
    registry["interaction_environment"] = "Codespaces"
    registry["interaction_ready"] = True
    registry["ui_render_mode"] = render_mode
    registry["codespace_ram_gb"] = round(ram_gb, 2)

    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=4)

    logger.info(f"Codespace Interaction State locked into Golden Registry: {registry_path}")


def run_interaction_setup() -> None:
    logger.info("=======================================================")
    logger.info(" CoChem-BASE: Codespace Interaction Provisioning ")
    logger.info("=======================================================\n")

    if not verify_codespace_kernel():
        logger.error("FATAL: Target environment is not a Codespace (/workspaces/ missing).")
        logger.error("Please ensure you selected the correct Interaction Environment.")
        sys.exit(1)

    artifact_dir = provision_airgap_directories()
    install_ui_dependencies()

    render_mode, ram_gb = probe_hardware_memory()
    register_interaction_state(artifact_dir, render_mode, ram_gb)

    logger.info("Codespace Interaction Layer successfully established. Ready for UI handoff.")


if __name__ == "__main__":
    run_interaction_setup()