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
from pathlib import Path

def verify_wsl_kernel() -> bool:
    """Validates that the script is executing inside a Windows Subsystem for Linux kernel."""
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            if "microsoft" in version_info or "wsl" in version_info:
                return True
    except FileNotFoundError:
        pass
    return False

def provision_airgap_directories() -> Path:
    """Constructs the strict CoChem_Artifacts directory tree to replace Docker volume mounts."""
    artifact_dir = Path.home() / "CoChem_Artifacts"
    subdirs = [
        artifact_dir / "Registry" / "Engines",
        artifact_dir / "Registry" / "Modules",
        artifact_dir / "Logs",
        artifact_dir / "Workspaces"
    ]
    
    for directory in subdirs:
        directory.mkdir(parents=True, exist_ok=True)
    
    print(f"🔒 Air-Gap Directories Provisioned at: {artifact_dir}")
    return artifact_dir

def install_ui_dependencies():
    """Installs the core ipywidgets and telemetry libraries required by CoChem-UNITY/DOCK."""
    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab"]
    print("📦 Bootstrapping Interaction UI Dependencies...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user"] + required_packages,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("✅ UI Dependencies satisfied.")
    except subprocess.CalledProcessError as e:
        print(f"❌ FATAL: Failed to provision UI packages. Error: {e.stderr}")
        sys.exit(1)

def register_interaction_state(artifact_dir: Path):
    """Updates the Golden Registry to confirm WSL Interaction provisioning."""
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"
    
    # Load existing or create fresh
    if registry_path.exists():
        with open(registry_path, 'r') as f:
            registry = json.load(f)
    else:
        registry = {"interaction_environment": None, "calculation_environment": None, "silos": {}}
        
    registry["interaction_environment"] = "Local-Windows (WSL)"
    registry["interaction_ready"] = True
    
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=4)
        
    print(f"✅ Interaction State locked into Golden Registry: {registry_path}")

def run_interaction_setup():
    print("=======================================================")
    print(" CoChem-BASE: WSL Interaction Environment Provisioning ")
    print("=======================================================\n")
    
    if not verify_wsl_kernel():
        print("❌ FATAL: Target environment is not WSL. Please run interact_mac.py or interact_linux.py instead.")
        sys.exit(1)
        
    artifact_dir = provision_airgap_directories()
    install_ui_dependencies()
    register_interaction_state(artifact_dir)
    
    print("\n✅ WSL Interaction Layer successfully established. Ready for UI handoff.")

if __name__ == "__main__":
    run_interaction_setup()