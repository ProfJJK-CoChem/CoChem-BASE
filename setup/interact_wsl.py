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

def check_wsl2_installation() -> bool:
    """Check if WSL2 is installed and available on Windows system."""
    try:
        # Check if wsl.exe exists in System32
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
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def bootstrap_wsl2_if_missing() -> bool:
    """Bootstrap WSL2 if not installed on Windows system."""
    print("🔍 Checking for WSL2 installation...")
    
    # Check if we're on Windows and WSL is available
    if sys.platform != "win32":
        return False  # Not running on Windows, so no need to bootstrap WSL2

    if check_wsl2_installation():
        print("✅ WSL2 is already installed on this system.")
        return True

    print("⚠️  WSL2 not found on Windows system. Initiating installation...")
    print("💡 This will trigger the UAC elevation prompt and install WSL2.")

    # Check if we have admin privileges
    if not request_admin_elevation():
        print("❌ Admin privileges required to install WSL2. Please run this script as Administrator.")
        return False

    try:
        # Attempt to install WSL2 using PowerShell command
        print("🔄 Installing WSL2 and Ubuntu distribution...")
        result = subprocess.run([
            "powershell", "-Command", 
            "wsl --install -d Ubuntu"
        ], capture_output=True, text=True, check=True)
        
        print("✅ WSL2 installation initiated. Please reboot your system and re-run this script.")
        print("💡 After rebooting, you'll need to complete the Ubuntu setup process in the WSL terminal.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install WSL2: {e.stderr}")
        return False

def provision_airgap_directories() -> Path:
    """Constructs the strict CoChem_Artifacts directory tree to replace Docker volume mounts."""
    artifact_dir = (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else Path.home() / "CoChem_Artifacts"))
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
    print("📦 Bootstrapping Interaction UI Dependencies...")
    
    # Probe for pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ PIP not found in WSL Python.")
        print("⚠️  WSL Fix: Run 'sudo apt-get update && sudo apt-get install -y python3-pip' in your WSL terminal.")
        sys.exit(1)

    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab"]
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user"] + required_packages,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
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
    
    # Stage -0.1: Windows Host Pre-Flight & WSL2 Bootstrapper
    if sys.platform == "win32":
        # Check if we're in WSL or native Windows
        if not verify_wsl_kernel():
            # We are running on native Windows, so try to bootstrap WSL2
            print("⚠️  Detected native Windows execution. Attempting to bootstrap WSL2...")
            if not bootstrap_wsl2_if_missing():
                print("❌ Failed to bootstrap WSL2. Please install WSL2 manually and re-run this script.")
                sys.exit(1)
            else:
                print("✅ WSL2 bootstrapping initiated. Reboot your system, then re-run this script in WSL Ubuntu terminal.")
                sys.exit(0)
        else:
            print("✅ Running inside WSL kernel - proceeding with normal setup...")
    else:
        # Not on Windows, verify we're in WSL
        if not verify_wsl_kernel():
            print("❌ FATAL: Target environment is not WSL. Please run interact_mac.py or interact_linux.py instead.")
            sys.exit(1)
    
    # Stage 0.1a: WSL Interaction Provisioning & UI Dependency (existing functionality)
    artifact_dir = provision_airgap_directories()
    install_ui_dependencies()
    register_interaction_state(artifact_dir)
    
    print("\n✅ WSL Interaction Layer successfully established. Ready for UI handoff.")

if __name__ == "__main__":
    run_interaction_setup()