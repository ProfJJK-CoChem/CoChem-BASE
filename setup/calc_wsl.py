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

def provision_openmpi() -> str:
    """Locates OpenMPI or halts with instructions for WSL installation."""
    print("🔍 Probing for OpenMPI (mpirun)...")
    mpi_path = shutil.which("mpirun")
    
    if not mpi_path:
        print("❌ OpenMPI not found in WSL $PATH.")
        print("⚠️  WSL Fix: Run 'sudo apt-get update && sudo apt-get install openmpi-bin libopenmpi-dev' in your terminal.")
        sys.exit(1)
        
    try:
        result = subprocess.run([mpi_path, "--version"], capture_output=True, text=True, check=True)
        version_line = result.stdout.split('\n')[0]
        print(f"✅ OpenMPI verified at: {mpi_path} ({version_line})")
        return mpi_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to execute mpirun. Error: {e.stderr}")
        sys.exit(1)

def provision_orca(engine_dir: Path) -> str:
    """Finds existing ORCA or extracts a .tar.xz archive using the Siloed Linux Archive protocol."""
    print("🔍 Probing for ORCA Linux Engine...")
    
    # Check if already extracted
    orca_bin = engine_dir / "orca"
    if orca_bin.exists() and os.access(orca_bin, os.X_OK):
        print(f"✅ Active ORCA binary found at: {orca_bin}")
        return str(orca_bin)

    # Search for extracted subdirectories
    for subdir in engine_dir.iterdir():
        if subdir.is_dir():
            potential_bin = subdir / "orca"
            if potential_bin.exists() and os.access(potential_bin, os.X_OK):
                print(f"✅ Active ORCA binary found at: {potential_bin}")
                return str(potential_bin)

    # If no binary, look for archive
    archives = list(engine_dir.glob("orca*.tar.xz")) + list(engine_dir.glob("ORCA*.tar.xz"))
    if not archives:
        print(f"❌ ORCA engine not found. No .tar.xz archives detected in {engine_dir}")
        print("⚠️  Please drop the Linux ORCA archive into the Registry/Engines folder and rerun.")
        sys.exit(1)
        
    target_archive = archives[0]
    print(f"📦 Found ORCA Archive: {target_archive.name}. Initiating extraction...")
    
    try:
        # --no-same-owner prevents UID panic when WSL extracts files mapped from Windows
        subprocess.run(
            ["tar", "-xf", str(target_archive), "--no-same-owner", "-C", str(engine_dir)],
            check=True
        )
        print("✅ Archive extraction complete.")
        
        # Recursively hunt for the binary again after extraction
        for path in engine_dir.rglob("orca"):
            if path.is_file() and os.access(path, os.X_OK):
                print(f"✅ Successfully staged and verified ORCA at: {path}")
                return str(path)
                
        print("❌ Extraction succeeded but 'orca' binary could not be located inside the folder.")
        sys.exit(1)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Extraction failed. Is the archive corrupted? Error: {e}")
        sys.exit(1)

def register_calculation_state(mpi_path: str, orca_path: str):
    """Updates the Golden Registry with the native WSL execution pathways."""
    registry_path = Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json"
    
    if registry_path.exists():
        with open(registry_path, 'r') as f:
            registry = json.load(f)
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
    
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=4)
        
    print(f"✅ Calculation State & Engine Paths locked into Golden Registry: {registry_path}")

def run_calculation_setup():
    print("=======================================================")
    print(" CoChem-BASE: WSL Calculation Environment Provisioning ")
    print("=======================================================\n")
    
    if not verify_wsl_kernel():
        print("❌ FATAL: Target environment is not WSL. Please run calc_mac.py or calc_linux.py instead.")
        sys.exit(1)
        
    engine_dir = Path.home() / "CoChem_Artifacts" / "Registry" / "Engines"
    engine_dir.mkdir(parents=True, exist_ok=True)
    
    mpi_path = provision_openmpi()
    orca_path = provision_orca(engine_dir)
    register_calculation_state(mpi_path, orca_path)
    
    print("\n✅ WSL Calculation Layer successfully established. Engines are ready for execution.")

if __name__ == "__main__":
    run_calculation_setup()