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
from pathlib import Path

def verify_codespace_kernel() -> bool:
    """Validates execution within a GitHub Codespaces or DevContainer context."""
    return Path("/workspaces").exists() or "CODESPACES" in os.environ

def provision_airgap_directories() -> Path:
    """Constructs the Air-Gap directory tree. Defaults to the user home to isolate from Git."""
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
    """Bootstraps missing pip dependencies for the Codespace UI."""
    required_packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab"]
    print("📦 Bootstrapping Codespace Interaction UI Dependencies...")
    
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

def probe_hardware_memory():
    """Probes available Codespace RAM and adjusts the UI rendering fidelity."""
    # Import psutil dynamically after guaranteed installation
    import psutil
    
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    print(f"📊 Codespace RAM Detected: {total_ram_gb:.2f} GB")
    
    # Enforce the < 8GB Sparse UI rule
    render_mode = "sparse" if total_ram_gb < 8.0 else "full"
    
    if render_mode == "sparse":
        print("⚠️ Memory < 8GB. Forcing 'sparse' UI render mode to prevent WebGL browser crashes.")
    else:
        print("✅ Memory >= 8GB. 'full' WebGL UI render mode enabled.")
        
    return render_mode, total_ram_gb

def register_interaction_state(artifact_dir: Path, render_mode: str, ram_gb: float):
    """Updates the Golden Registry to confirm Codespace Interaction provisioning."""
    registry_path = artifact_dir / "Registry" / "cochem_system_config.json"
    
    # Load existing or create fresh
    if registry_path.exists():
        with open(registry_path, 'r') as f:
            try:
                registry = json.load(f)
            except json.JSONDecodeError:
                registry = {}
    else:
        registry = {}
        
    registry.setdefault("silos", {})
    registry["interaction_environment"] = "Codespaces"
    registry["interaction_ready"] = True
    registry["ui_render_mode"] = render_mode
    registry["codespace_ram_gb"] = round(ram_gb, 2)
    
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=4)
        
    print(f"✅ Codespace Interaction State locked into Golden Registry: {registry_path}")

def run_interaction_setup():
    print("=======================================================")
    print(" CoChem-BASE: Codespace Interaction Provisioning ")
    print("=======================================================\n")
    
    if not verify_codespace_kernel():
        print("❌ FATAL: Target environment is not a Codespace (/workspaces/ missing).")
        print("Please ensure you selected the correct Interaction Environment.")
        sys.exit(1)
        
    artifact_dir = provision_airgap_directories()
    install_ui_dependencies()
    
    render_mode, ram_gb = probe_hardware_memory()
    register_interaction_state(artifact_dir, render_mode, ram_gb)
    
    print("\n✅ Codespace Interaction Layer successfully established. Ready for UI handoff.")

if __name__ == "__main__":
    run_interaction_setup()