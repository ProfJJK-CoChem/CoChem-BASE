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
import platform
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
    artifact_dir = os.environ.get("COCHEM_ARTIFACT_DIR")
    if artifact_dir:
        registry_dir = Path(artifact_dir) / "Registry"
    else:
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

def execute_script(script_name: str, env_name: str):
    """Dispatches the target Python script sequentially with strict error trapping."""
    script_path = Path(__file__).resolve().parent / script_name
    
    if not script_path.exists():
        print(f"❌ FATAL: Setup script '{script_name}' is missing from the setup/ directory.")
        sys.exit(1)
        
    print(f"\n▶️ Dispatching OS-Native Router: {script_name}...")
    try:
        # Cross OS boundary if executing from a Windows host targeting WSL
        if "WSL" in env_name and platform.system() == "Windows":
            drive = str(script_path)[0].lower()
            wsl_path = f"/mnt/{drive}/{str(script_path)[3:].replace(os.sep, '/')}"
            cmd = ["wsl", "python3", wsl_path]
        else:
            cmd = [sys.executable, str(script_path)]
            
        # Standardize execution to the active python interpreter
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FATAL: '{script_name}' failed with exit code {e.returncode}.")
        print("Please check the terminal output above for specific OS errors.")
        sys.exit(e.returncode)

def detect_cuda_capability() -> bool:
    """
    Detects CUDA capability and returns whether GPU acceleration is available.
    Returns True if CUDA is available, False otherwise.
    """
    try:
        # Try to run nvidia-smi command to check for CUDA availability
        result = subprocess.run(['nvidia-smi', '--query-gpu=count', '--format=csv,noheader,nounits'], 
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip() != '0':
            return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # If nvidia-smi is not available or fails, try alternative methods
        pass

    # Try to detect CUDA via Python libraries
    try:
        import torch
        if torch.cuda.is_available():
            return True
    except ImportError:
        pass

    try:
        import tensorflow as tf
        if tf.config.list_physical_devices('GPU'):
            return True
    except ImportError:
        pass

    # No CUDA capability detected
    return False

def detect_hardware_capability() -> dict:
    """
    Detects hardware capabilities and returns a dictionary with relevant info.
    """
    try:
        import psutil
        import platform
        import multiprocessing
        
        cpu_count = multiprocessing.cpu_count()
        memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        is_cuda_available = detect_cuda_capability()
        
        # Detect QCxMS binary availability
        is_qcxms_available = False
        try:
            # Try to find QCxMS in common locations or via PATH
            result = subprocess.run(['which', 'QCxMS'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                is_qcxms_available = True
        except Exception:
            # If which command fails, try direct execution test
            try:
                subprocess.run(['QCxMS', '--version'], capture_output=True, timeout=5)
                is_qcxms_available = True
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                pass
        
        return {
            'cpu_count': cpu_count,
            'memory_gb': memory_gb,
            'cuda_available': is_cuda_available,
            'platform': platform.system(),
            'architecture': platform.machine(),
            'qcxms_available': is_qcxms_available
        }
    except Exception as e:
        print(f"⚠️  Failed to detect hardware capabilities: {e}")
        return {'cpu_count': 1, 'memory_gb': 0, 'cuda_available': False, 'platform': 'Unknown', 'architecture': 'Unknown', 'qcxms_available': False}

def get_mlff_fallback_strategy(hardware_info: dict) -> str:
    """
    Determines the appropriate MLFF fallback strategy based on hardware capabilities.
    Returns the calculation environment to use for MLFF routing.
    """
    # If CUDA is available, prioritize GPU-accelerated MLFF
    if hardware_info.get('cuda_available', False):
        print("🎮 GPU Acceleration detected - prioritizing CUDA-enabled MLFF execution")
        return "Local-Linux (Deb)"  # Assuming this can handle CUDA
    
    # For CPU-only systems, determine appropriate fallback strategy
    cpu_count = hardware_info.get('cpu_count', 1)
    memory_gb = hardware_info.get('memory_gb', 0)
    
    # Determine MLFF strategy based on system resources
    if cpu_count >= 8 and memory_gb >= 16:
        print("🧠 High-performance CPU detected - enabling advanced MLFF with full parallelization")
        return "Local-Linux (Deb)"
    elif cpu_count >= 4 and memory_gb >= 8:
        print("⚡ Medium-performance CPU detected - enabling optimized MLFF execution")
        return "Local-Linux (Deb)"  # This could be adjusted based on specific requirements
    else:
        print("⚡ Low-performance system detected - enabling basic MLFF execution with minimal resources")
        # For very low performance systems, route to Codespaces for fallback or g-xTB if available
        return "Codespaces"  # Route to Codespaces as a fallback for CPU-only systems

def detect_element_boundaries(molecule_input: str) -> list:
    """
    Parse the molecular input (xyz or SMILES) to detect elements.
    Returns a list of detected elements.
    """
    try:
        # Try to parse as SMILES first
        if molecule_input.startswith('[') and ']' in molecule_input:
            # This is likely a SMILES string with atom specifications
            import re
            # Extract elements from SMILES notation
            elements = re.findall(r'[A-Z][a-z]*', molecule_input)
            return list(set(elements))  # Remove duplicates
        else:
            # Try to parse as XYZ file
            lines = molecule_input.strip().split('\n')
            if len(lines) >= 2:
                # First line is number of atoms, second line is atom symbols
                element_symbols = []
                for i in range(2, min(len(lines), 100)):  # Check first 100 lines
                    if lines[i].strip():
                        parts = lines[i].split()
                        if len(parts) > 0:
                            symbol = parts[0]
                            if symbol.isalpha() and len(symbol) <= 2:
                                element_symbols.append(symbol)
                return list(set(element_symbols))  # Remove duplicates
    except Exception as e:
        print(f"⚠️  Failed to parse molecule input for elements: {e}")
    
    return []

def get_element_fallback_strategy(elements: list) -> str:
    """
    Determine if elements are outside MACE-OFF24m parameterized boundaries.
    Returns appropriate fallback method if needed.
    """
    # Elements that are outside the parameterized boundaries of MACE-OFF24m
    # These typically include transition metals and heavier elements
    non_mace_elements = {
        'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
        'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
        'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
        'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
        'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
        'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
        'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
        'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm',
        'Md', 'No', 'Lr'
    }
    
    # Check if any elements are outside MACE-OFF24m boundaries
    non_mace_detected = [elem for elem in elements if elem in non_mace_elements]
    
    if non_mace_detected:
        print(f"⚠️  Detected elements outside MACE-OFF24m parameterized boundaries: {non_mace_detected}")
        print("🎯 Triggering AIMNet2 fallback to prevent runtime crashes")
        return "AIMNet2"
    
    return None  # No fallback needed

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
        
    # Detect hardware capabilities
    hardware_info = detect_hardware_capability()
    print(f"🔧 Detected Hardware: {hardware_info}")
    
    # Implement MLFF fallback routing logic based on hardware capability
    if calc_env == "MLFF-Fallback":
        print("🔄 MLFF-Fallback strategy detected - determining optimal execution environment")
        calc_env = get_mlff_fallback_strategy(hardware_info)
        print(f"🎯 Selected calculation environment: {calc_env}")

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
    execute_script(interact_script, interact_env)
    
    # Phase 2: Provision Calculation (Engines / MPI / Slurm)
    execute_script(calc_script, calc_env)
    
    print("\n✅ CoChem-BASE Master Orchestration Complete.")
    print("System Config Registry has been successfully compiled.")

if __name__ == "__main__":
    main()