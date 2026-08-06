#!/usr/bin/env python3
"""
CoChem-BASE Stage 0: Master Setup Orchestrator
Reads the deployment manifest and dynamically routes setup execution
to the correct OS-native Interaction and Calculation scripts, completely
bypassing legacy Docker/DevContainer abstractions.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Dual-Matrix Routing Dictionaries
INTERACT_MAP = {
    "Local-Windows (WSL)": "interact_wsl.py",
    "Local-MacOS (OrbStack)": "interact_mac.py",
    "Local-Linux (Deb)": "interact_linux.py",
    "Codespaces": "interact_codespaces.py"
}

CALC_MAP = {
    "Local-Windows (WSL)": "calc_wsl.py",
    "Local-MacOS (OrbStack)": "calc_mac.py",
    "Local-Linux (Deb)": "calc_linux.py",
    "GitHub Actions": "calc_gh_actions.py",
    "HPC": "calc_hpc.py"
}

def get_manifest_path() -> Path:
    """Locates the unified deployment manifest enforcing the Air-Gap rule."""
    registry_dir = Path.home() / "CoChem_Artifacts" / "Registry"
    manifest = registry_dir / "cochem_deployment_manifest.json"
    
    if manifest.exists():
        return manifest
        
    # Fallback to local execution dir for bootstrap testing
    local_manifest = Path(__file__).resolve().parent.parent / "cochem_deployment_manifest.json"
    if local_manifest.exists():
        return local_manifest
        
    print(f"❌ FATAL: Deployment manifest not found at {manifest}.")
    print("Please complete the CoChem-BASE UI selection in Start_Here.ipynb first.")
    sys.exit(1)

def execute_script(script_name: str):
    """Dispatches the target Python script sequentially with strict error trapping."""
    script_path = Path(__file__).resolve().parent / script_name
    
    if not script_path.exists():
        print(f"❌ FATAL: Setup script '{script_name}' is missing from the setup/ directory.")
        sys.exit(1)
        
    print(f"\n▶️ Dispatching OS-Native Router: {script_name}...")
    try:
        # Standardize execution to the active python interpreter
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FATAL: '{script_name}' failed with exit code {e.returncode}.")
        print("Please check the terminal output above for specific OS errors.")
        sys.exit(e.returncode)

def main():
    print("=======================================================")
    print(" CoChem-BASE: OS-Native Dual Matrix Orchestrator ")
    print("=======================================================\n")
    
    manifest_path = get_manifest_path()
    with open(manifest_path, 'r') as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ FATAL: Manifest {manifest_path} is corrupted.")
            sys.exit(1)
        
    interact_env = manifest.get("interaction_environment")
    calc_env = manifest.get("calculation_environment")
    
    if not interact_env or not calc_env:
        print("❌ FATAL: Manifest is missing 'interaction_environment' or 'calculation_environment' keys.")
        sys.exit(1)
        
    interact_script = INTERACT_MAP.get(interact_env)
    calc_script = CALC_MAP.get(calc_env)
    
    if not interact_script:
        print(f"❌ FATAL: Unknown Interaction Environment: {interact_env}")
        sys.exit(1)
        
    if not calc_script:
        print(f"❌ FATAL: Unknown Calculation Environment: {calc_env}")
        sys.exit(1)
        
    print(f"🌐 Target Interaction Layer: {interact_env}")
    print(f"⚙️  Target Calculation Layer: {calc_env}\n")
    
    # Phase 1: Provision Interaction (UI / Jupyter / Logs)
    execute_script(interact_script)
    
    # Phase 2: Provision Calculation (Engines / MPI / Slurm)
    execute_script(calc_script)
    
    print("\n✅ CoChem-BASE Master Orchestration Complete.")
    print("System Config Registry has been successfully compiled.")

if __name__ == "__main__":
    main()