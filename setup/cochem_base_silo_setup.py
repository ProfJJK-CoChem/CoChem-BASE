import subprocess
import sys
import json
import os
from pathlib import Path

def get_artifact_dir():
    try:
        repo_root = Path(__file__).resolve().parent.parent
        config_path = repo_root / ".cochem_env.json"
        
        # also check cwd
        if not config_path.exists():
            config_path = Path.cwd() / ".cochem_env.json"
            
        if config_path.exists():
            with open(config_path, "r") as f:
                data = json.load(f)
                if "artifact_dir" in data:
                    return Path(data["artifact_dir"])
    except Exception:
        pass
    # Fix the logic error in the original code
    artifact_dir = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifact_dir:
        return Path(artifact_dir)
    else:
        return Path.home() / "CoChem_Artifacts"

def main():
    artifact_dir = get_artifact_dir()
    env_dir = artifact_dir / "Silos" / "cochem_base_silo"
    env_dir.parent.mkdir(parents=True, exist_ok=True)
    
    print("🔍 Checking system requirements...")
    
    # Check if conda is available
    try:
        result = subprocess.run(["conda", "--version"], check=True, capture_output=True, text=True)
        print(f"✅ Conda found: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Conda not found. Please ensure Conda/Miniconda is installed and in your PATH.")
        print("   You can download it from: https://docs.conda.io/en/latest/miniconda.html")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("❌ Conda command failed.")
        sys.exit(1)
        
    print(f"🔄 Creating / Updating Conda environment at: {env_dir}...")
    
    # Create the conda environment
    try:
        # Check if environment already exists
        result = subprocess.run(["conda", "info", "--envs"], check=True, capture_output=True, text=True)
        if str(env_dir) in result.stdout:
            print("⚠️ Environment already exists, updating...")
        else:
            print("📦 Creating new conda environment...")
        
        # Create or update the environment
        subprocess.run(["conda", "create", "-p", str(env_dir), "python=3.10", "-y"], check=True, capture_output=True)
        print(f"✅ Conda environment created/updated at: {env_dir}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create/update conda environment: {e}")
        sys.exit(1)

    # Install pip dependencies inside the environment
    packages = ["ipywidgets>=8.0.0", "psutil", "jupyterlab", "numpy", "pandas", "matplotlib", "seaborn", "scipy", "openbabel", "rdkit"]
    print(f"📦 Installing Python packages into {env_dir}: {', '.join(packages)}")
    
    try:
        # Use conda run to execute pip install within the environment
        subprocess.run(["conda", "run", "-p", str(env_dir), "pip", "install"] + packages, check=True, capture_output=True)
        print("✅ Python packages installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages into {env_dir}. Error: {e}")
        sys.exit(1)
    
    # Install additional conda packages
    conda_packages = ["pip", "conda", "ipython", "jupyter"]
    print(f"📦 Installing additional conda packages: {', '.join(conda_packages)}")
    
    try:
        subprocess.run(["conda", "install", "-p", str(env_dir)] + conda_packages, check=True, capture_output=True)
        print("✅ Additional conda packages installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install additional conda packages into {env_dir}. Error: {e}")
        sys.exit(1)
        
    # Install the CoChem modules in development mode
    try:
        current_dir = Path(__file__).parent.parent
        print(f"📦 Installing CoChem modules from: {current_dir}")
        subprocess.run(["conda", "run", "-p", str(env_dir), "pip", "install", "-e", str(current_dir)], check=True, capture_output=True)
        print("✅ CoChem modules installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install CoChem modules. Error: {e}")
        sys.exit(1)
    
    # Verify installation
    try:
        result = subprocess.run(["conda", "run", "-p", str(env_dir), "python", "-c", "import ipywidgets; print('ipywidgets version:', ipywidgets.__version__)"], 
                               check=True, capture_output=True, text=True)
        print("✅ Verification successful!")
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"❌ Verification failed: {e}")
        
    print(f"✅ Silo setup complete at {env_dir}!")

if __name__ == "__main__":
    main()
