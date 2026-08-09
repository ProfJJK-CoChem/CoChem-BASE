#!/usr/bin/env python3
"""
CoChem-BASE Silo Setup Script
This script creates the conda environment for CoChem-BASE.
"""

import subprocess
import sys
import os
import json
from pathlib import Path

def setup_conda_silo():
    """Setup the conda silo environment"""
    
    print("==============================================================")
    print(" 🧪 CoChem-BASE: Conda Silo Environment Creation")
    print("==============================================================\n")
    
    # Get the artifact directory from config
    cfg_path = Path.cwd() / ".cochem_env.json"
    if not cfg_path.exists():
        print("❌ Configuration file (.cochem_env.json) not found!")
        sys.exit(1)
        
    with open(cfg_path, "r") as f:
        config = json.load(f)
        
    artifact_dir = Path(config["artifact_dir"])
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"
    
    print(f"Artifact Directory: {artifact_dir}")
    print(f"Silo Directory: {silo_dir}\n")
    
    # Create the artifact directory if it doesn't exist
    artifact_dir.mkdir(parents=True, exist_ok=True)
    silo_dir.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if environment already exists
    conda_meta_path = silo_dir / "conda-meta"
    
    # More robust check - verify this is actually a valid conda environment
    env_valid = False
    
    if conda_meta_path.exists():
        # Additional verification: check for key conda files that should exist
        try:
            # Check if there's at least one conda package installed
            import os
            meta_files = list(conda_meta_path.glob("*.json"))
            if len(meta_files) > 0:
                env_valid = True
            else:
                print("⚠️ Conda-meta directory exists but is empty - treating as invalid")
        except Exception as e:
            print(f"⚠️ Error checking conda-meta: {e}")
    
    if env_valid:
        print("✅ Conda environment already exists at:", silo_dir)
        print("   Skipping creation process")
        return True
        
    # If we're here, the environment doesn't exist or is invalid
    print("🔄 Environment not found or invalid, proceeding with creation...")
        
    print("🔄 Creating new conda environment...")
    
    # Create the conda environment
    try:
        # Create the environment using the specified directory
        create_cmd = [
            "conda", "create", "--prefix", str(silo_dir),
            "-c", "conda-forge", "python=3.10", "numpy", "pandas", 
            "scipy", "matplotlib", "jupyter", "ipywidgets",
            "openbabel", "rdkit", "ase", "pyyaml", "requests",
            "--yes"
        ]
        
        print("Running command:", " ".join(create_cmd))
        result = subprocess.run(create_cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # Install additional packages
        install_cmd = [
            "conda", "install", "--prefix", str(silo_dir),
            "-c", "conda-forge", "mypy", "black", "flake8",
            "--yes"
        ]
        
        print("Installing additional packages...")
        result = subprocess.run(install_cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # Install specific packages that might not be in conda-forge
        pip_install = [
            "python", "-m", "pip", "install",
            "openbabel", "pybel", "chemformula", "periodictable"
        ]
        
        print("Installing pip packages...")
        result = subprocess.run(pip_install, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        print("✅ Conda environment created successfully at:", silo_dir)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating conda environment: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    setup_conda_silo()
