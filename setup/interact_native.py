#!/usr/bin/env python3
"""Provision the CoChem interaction layer on native macOS and Linux hosts."""

import importlib.util
import json
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict

from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-InteractNative")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


PACKAGE_MAP: Dict[str, str] = {
    "ipywidgets": "ipywidgets>=8.0.0",
    "psutil": "psutil",
    "jupyterlab": "jupyterlab",
}


def interaction_environment() -> str:
    system = platform.system()
    if system == "Darwin":
        return "Local-MacOS (OrbStack)"
    if system == "Linux":
        return "Local-Linux (Deb)"
    raise RuntimeError(f"Native interaction setup does not support host platform: {system}")


def provision_airgap_directories() -> Path:
    artifact_dir = get_artifact_dir()
    for relative_path in (
        Path("Registry") / "Engines",
        Path("Registry") / "Modules",
        Path("Logs"),
        Path("Workspaces"),
    ):
        (artifact_dir / relative_path).mkdir(parents=True, exist_ok=True)
    return artifact_dir


def install_missing_ui_dependencies() -> None:
    missing = [package for module, package in PACKAGE_MAP.items() if importlib.util.find_spec(module) is None]
    if not missing:
        return
    command = [sys.executable, "-m", "pip", "install", *missing]
    if safe_subprocess_run:
        safe_subprocess_run(command, check=True, timeout=300.0)
    else:
        subprocess.run(command, check=True, timeout=300.0)


def register_interaction_state(artifact_dir: Path, environment: str) -> None:
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            registry = {}
    else:
        registry = {}
    registry["interaction_environment"] = environment
    registry["interaction_ready"] = True
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def run_interaction_setup() -> None:
    environment = interaction_environment()
    artifact_dir = provision_airgap_directories()
    install_missing_ui_dependencies()
    register_interaction_state(artifact_dir, environment)
    logger.info(f"Native interaction layer ready for {environment}: {artifact_dir}")


if __name__ == "__main__":
    run_interaction_setup()
