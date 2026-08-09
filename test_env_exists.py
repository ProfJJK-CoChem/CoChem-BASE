#!/usr/bin/env python3
"""
Script to test if a conda environment exists at a specific path.
This is used to optimize the setup process by avoiding unnecessary reinstallation.
"""

import sys
import subprocess
from pathlib import Path

def check_conda_environment_exists(env_path):
    """
    Check if a conda environment exists at the specified path.
    
    Args:
        env_path (str): The path where the conda environment should exist
        
    Returns:
        bool: True if environment exists, False otherwise
    """
    try:
        # First try to use conda info --envs to list all environments
        result = subprocess.run(
            ["conda", "info", "--envs"], 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        # Check if the environment path is in the conda environments list
        if env_path in result.stdout:
            print(f"✅ Conda environment found at: {env_path}")
            return True
            
        # If not found via conda info, also check filesystem
        env_dir = Path(env_path)
        if env_dir.exists():
            print(f"✅ Environment directory found at: {env_path}")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Conda command failed: {e}")
        # Fallback to filesystem check only
        env_dir = Path(env_path)
        if env_dir.exists():
            print(f"✅ Environment directory found at: {env_path} (fallback)")
            return True
            
    except Exception as e:
        print(f"⚠️ Error checking environment: {e}")
        
    return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_env_exists.py <environment_path>")
        sys.exit(1)
        
    env_path = sys.argv[1]
    exists = check_conda_environment_exists(env_path)
    
    if exists:
        print("Environment exists")
        sys.exit(0)
    else:
        print("Environment does not exist")
        sys.exit(1)