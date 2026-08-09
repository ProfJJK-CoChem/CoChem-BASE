#!/usr/bin/env python3
"""
Test script for environment detection logic in CoChem-BASE setup.
This validates that our improved detection method works correctly.
"""

import json
from pathlib import Path
import subprocess

def test_environment_detection():
    """Test the environment detection logic."""
    
    # Test configuration
    cfg_path = Path.cwd() / '.cochem_env.json'
    if not cfg_path.exists():
        print("❌ No configuration file found")
        return False
    
    with open(cfg_path, 'r') as f:
        config = json.load(f)
    
    artifact_dir = Path(config['artifact_dir'])
    env_dir = artifact_dir / "Silos" / "cochem_base_silo"
    
    print(f"Testing environment at: {env_dir}")
    
    # Check if directory exists
    print(f"Directory exists: {env_dir.exists()}")
    
    # More robust check - verify conda environment actually exists and is valid
    env_exists = False
    try:
        result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True)
        # Check if our environment path is in the conda environments list
        if str(env_dir) in result.stdout:
            # Additional verification: make sure it's actually a valid conda environment
            # by checking for conda-meta directory or other conda artifacts
            conda_meta_path = env_dir / "conda-meta"
            if conda_meta_path.exists():
                env_exists = True
                print("✅ Valid conda environment detected")
            else:
                print(f"⚠️ Environment path found but conda-meta directory missing: {conda_meta_path}")
                # This indicates a potentially invalid environment that needs recreation
                env_exists = False
        else:
            # Also check if the directory exists (fallback method)
            env_exists = env_dir.exists()
            if env_exists:
                print("⚠️ Directory exists but not registered in conda environments")
                print("   This might be an old setup or broken installation")
    except Exception as e:
        # If conda command fails or environment not found, fall back to filesystem check
        print(f"⚠️ Conda check failed: {e}")
        env_exists = env_dir.exists()
        if env_exists:
            print("   Directory exists but no valid conda environment detected")
    
    print(f"Final environment detection result: {env_exists}")
    return env_exists

if __name__ == "__main__":
    test_environment_detection()