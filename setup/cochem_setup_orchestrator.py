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
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-SetupOrchestrator")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None

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
    manifest = get_artifact_dir() / "Registry" / "cochem_deployment_manifest.json"

    if manifest.exists():
        return manifest

    local_manifest = Path(__file__).resolve().parent.parent / "cochem_deployment_manifest.json"
    if local_manifest.exists():
        return local_manifest

    logger.error(f"Deployment manifest not found at {manifest}.")
    logger.error("Please complete the CoChem-BASE UI selection in Start_Here.ipynb first.")
    sys.exit(1)


def execute_script(script_name: str, env_name: str) -> None:
    """Dispatches the target Python script sequentially with strict error trapping."""
    script_path = Path(__file__).resolve().parent / script_name

    if not script_path.exists():
        logger.error(f"Setup script '{script_name}' is missing from the setup/ directory.")
        sys.exit(1)

    logger.info(f"[DISPATCH] Dispatching OS-Native Router: {script_name}...")
    try:
        if "WSL" in env_name and platform.system() == "Windows":
            drive = str(script_path)[0].lower()
            wsl_path = f"/mnt/{drive}/{str(script_path)[3:].replace(os.sep, '/')}"
            cmd = ["wsl", "python3", wsl_path]
        else:
            cmd = [sys.executable, str(script_path)]

        if safe_subprocess_run:
            safe_subprocess_run(cmd, check=True, timeout=300.0)
        else:
            subprocess.run(cmd, check=True, timeout=300.0)
    except subprocess.CalledProcessError as e:
        logger.error(f"'{script_name}' failed with exit code {e.returncode}.")
        sys.exit(e.returncode)


def detect_cuda_capability() -> bool:
    """
    Detects CUDA capability and returns whether GPU acceleration is available.
    Returns True if CUDA is available, False otherwise.
    """
    try:
        if safe_subprocess_run:
            result = safe_subprocess_run(['nvidia-smi', '--query-gpu=count', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10.0, check=False)
        else:
            result = subprocess.run(['nvidia-smi', '--query-gpu=count', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10.0, check=False)  # check=True
        if result.returncode == 0 and result.stdout and result.stdout.strip() != '0':
            return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

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

    return False


def detect_hardware_capability() -> Dict[str, Any]:
    """
    Detects hardware capabilities and returns a dictionary with relevant info.
    """
    try:
        import psutil
        import multiprocessing

        cpu_count = multiprocessing.cpu_count()
        memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        is_cuda_available = detect_cuda_capability()

        is_qcxms_available = bool(shutil.which("QCxMS"))
        if not is_qcxms_available:
            try:
                subprocess.run(['QCxMS', '--version'], capture_output=True, timeout=5.0, check=False)  # check=True
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
        logger.warning(f"Failed to detect hardware capabilities: {e}")
        return {'cpu_count': 1, 'memory_gb': 0, 'cuda_available': False, 'platform': 'Unknown', 'architecture': 'Unknown', 'qcxms_available': False}


def get_mlff_fallback_strategy(hardware_info: Dict[str, Any], daemon_online: bool = True, atom_count: int = 10) -> str:
    """
    Determines MLFF fallback routing (§9B.4) considering daemon availability and memory limits.
    """
    if not daemon_online:
        logger.warning("MLFF-GOAT server daemon offline -> Falling back to local AIMNet2 / GFN2-xTB")
        return "AIMNet2"

    memory_gb = hardware_info.get('memory_gb', 16)
    is_cuda = hardware_info.get('cuda_available', False)

    if not is_cuda and atom_count > 100:
        logger.warning(f"CPU system RAM limit warning for N={atom_count} -> Falling back to GFN2-xTB")
        return "GFN2-xTB"
    elif is_cuda and atom_count > 500:
        logger.warning(f"GPU VRAM limit warning for N={atom_count} -> Falling back to GFN2-xTB")
        return "GFN2-xTB"

    if is_cuda:
        return "Local-Linux (Deb)"
    return "Local-Linux (Deb)" if memory_gb >= 16 else "Codespaces"


def detect_element_boundaries(molecule_input: str) -> List[str]:
    """
    Parse the molecular input (xyz or SMILES) to detect elements.
    Returns a list of detected elements.
    """
    try:
        if molecule_input.startswith('[') and ']' in molecule_input:
            import re
            elements = re.findall(r'[A-Z][a-z]*', molecule_input)
            return list(set(elements))
        else:
            lines = molecule_input.strip().split('\n')
            if len(lines) >= 2:
                element_symbols = []
                for i in range(2, min(len(lines), 100)):
                    if lines[i].strip():
                        parts = lines[i].split()
                        if len(parts) > 0:
                            symbol = parts[0]
                            if symbol.isalpha() and len(symbol) <= 2:
                                element_symbols.append(symbol)
                return list(set(element_symbols))
    except Exception as e:
        logger.warning(f"Failed to parse molecule input for elements: {e}")

    return []


def get_element_fallback_strategy(elements: List[str]) -> Optional[str]:
    """
    Determine if elements are outside MACE-OFF24m parameterized boundaries.
    Returns appropriate fallback method if needed.
    """
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

    non_mace_detected = [elem for elem in elements if elem in non_mace_elements]

    if non_mace_detected:
        logger.warning(f"Detected elements outside MACE-OFF24m parameterized boundaries: {non_mace_detected}")
        logger.info("[TARGET] Triggering AIMNet2 fallback to prevent runtime crashes")
        return "AIMNet2"

    return None


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        logger.info("CoChem-BASE Setup Orchestrator")
        logger.info("Usage: python setup/cochem_setup_orchestrator.py [--help]")
        sys.exit(0)

    logger.info("=======================================================")
    logger.info(" CoChem-BASE: OS-Native Dual Matrix Orchestrator ")
    logger.info("=======================================================\n")

    manifest_path = get_manifest_path()
    with open(manifest_path, 'r', encoding='utf-8') as f:
        try:
            manifest = json.loads(f.read())
        except json.JSONDecodeError:
            logger.error(f"Manifest {manifest_path} is corrupted.")
            sys.exit(1)

    interact_env = manifest.get("interaction_environment")
    calc_env = manifest.get("calculation_environment")

    if not interact_env or not calc_env:
        logger.error("Manifest is missing 'interaction_environment' or 'calculation_environment' keys.")
        sys.exit(1)

    hardware_info = detect_hardware_capability()
    logger.info(f"[HARDWARE] Detected Hardware: {hardware_info}")

    if calc_env == "MLFF-Fallback":
        logger.info("[ROUTING] MLFF-Fallback strategy detected - determining optimal execution environment")
        calc_env = get_mlff_fallback_strategy(hardware_info)
        logger.info(f"[TARGET] Selected calculation environment: {calc_env}")

    interact_script = INTERACT_MAP.get(interact_env)
    calc_script = CALC_MAP.get(calc_env)

    if not interact_script:
        logger.error(f"Unknown Interaction Environment: {interact_env}")
        sys.exit(1)

    if not calc_script:
        logger.error(f"Unknown Calculation Environment: {calc_env}")
        sys.exit(1)

    logger.info(f"[INTERACTION] Target Interaction Layer: {interact_env}")
    logger.info(f"[CALCULATION] Target Calculation Layer: {calc_env}\n")

    execute_script(interact_script, interact_env)
    execute_script(calc_script, calc_env)

    logger.info("\n[SUCCESS] CoChem-BASE Master Orchestration Complete.")
    logger.info("System Config Registry has been successfully compiled.")


if __name__ == "__main__":
    main()