
#!/usr/bin/env python3
"""
CoChem-BASE Silo Setup Script
This script creates the conda environment for CoChem-BASE.
"""

import logging
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)
sys.path[:] = [repo_root_str, *(entry for entry in sys.path if entry != repo_root_str)]

import cochem_base  # noqa: E402
from cochem_base.config_loader import get_artifact_dir, resolve_conda_executable  # noqa: E402

LOADED_BASE_ROOT = Path(cochem_base.__file__).resolve().parent.parent
if LOADED_BASE_ROOT != REPO_ROOT:
    raise ImportError(
        f"CoChem-BASE import resolved to {LOADED_BASE_ROOT}, expected active checkout {REPO_ROOT}."
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-SiloSetup")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    from typing import Any
    safe_subprocess_run: Any = None  # type: ignore

import atexit

_RUNNING_PROCS = []

def cleanup_processes() -> None:
    for p in _RUNNING_PROCS:
        if p.poll() is None:
            logger.warning(f"Terminating zombie process PID: {p.pid}")
            try:
                p.kill()
            except Exception:
                pass

atexit.register(cleanup_processes)

def run_cmd(cmd: list[str]) -> None:
    """Run a command with proper cleanup and logging."""
    logger.info(f"Running command: {' '.join(cmd)}")
    
    if safe_subprocess_run is not None:
        result = safe_subprocess_run(cmd, check=True, timeout=300.0)
        if hasattr(result, 'stdout') and result.stdout:
            logger.info(result.stdout)
        return
        
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        _RUNNING_PROCS.append(proc)
        stdout, stderr = proc.communicate(timeout=300.0)
        _RUNNING_PROCS.remove(proc)
        if proc.returncode != 0:
            logger.error(f"Command failed with exit code {proc.returncode}")
            logger.error(f"Stdout: {stdout}")
            logger.error(f"Stderr: {stderr}")
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=stdout, stderr=stderr)
        if stdout:
            logger.info(stdout)
    except subprocess.TimeoutExpired as e:
        logger.error(f"Command timed out: {' '.join(cmd)}")
        if proc in _RUNNING_PROCS:
            proc.kill()
            proc.communicate()
            _RUNNING_PROCS.remove(proc)
        raise e
    except OSError as e:
        logger.error(f"Command execution failed due to OS error: {e}")
        raise e


def setup_conda_silo() -> None:
    """Setup the conda silo environment"""

    logger.info("==============================================================")
    logger.info(" 🧪 CoChem-BASE: Conda Silo Environment Creation")
    logger.info("==============================================================\n")

    artifact_dir = get_artifact_dir()
    silo_dir = artifact_dir / "Silos" / "cochem_base_silo"

    logger.info(f"Artifact Directory: {artifact_dir}")
    logger.info(f"Silo Directory: {silo_dir}\n")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    silo_dir.parent.mkdir(parents=True, exist_ok=True)

    conda_meta_path = silo_dir / "conda-meta"

    env_valid = False

    if conda_meta_path.exists():
        meta_files = list(conda_meta_path.glob("*.json"))
        if len(meta_files) > 0:
            env_valid = True
        else:
            logger.warning("Conda-meta directory exists but is empty - treating as invalid")

    if env_valid:
        logger.info(f"Conda environment already exists at: {silo_dir}")
        logger.info("   Skipping creation process")
        return

    logger.info("Environment not found or invalid, proceeding with creation...")

    conda_executable = resolve_conda_executable()

    primary_silo = Path("d:/__CoChem/.agent_artifacts/Silos/cochem_base_silo")
    if primary_silo.exists() and (primary_silo / "conda-meta").exists() and primary_silo.resolve() != silo_dir.resolve():
        logger.info(f"Cloning from primary valid silo cache at {primary_silo}...")
        clone_cmd = [conda_executable, "create", "--prefix", str(silo_dir), "--clone", str(primary_silo), "--yes"]
        try:
            run_cmd(clone_cmd)
            logger.info("Successfully cloned silo from primary cache.")
            logger.info(f"Conda environment created successfully at: {silo_dir}")
            return
        except Exception as e:
            logger.warning(f"Silo clone failed ({e}), falling back to fresh installation...")

    logger.info("Creating new conda environment...")
    create_cmd = [
        conda_executable, "create", "--prefix", str(silo_dir),
        "-c", "conda-forge", "python=3.10", "numpy", "pandas",
        "scipy", "matplotlib", "jupyter", "ipywidgets",
        "openbabel", "rdkit", "ase", "pyyaml", "requests",
        "pydantic>=2", "h5py", "psutil", "filelock", "rich",
        "--yes"
    ]

    run_cmd(create_cmd)

    install_cmd = [
        conda_executable, "install", "--prefix", str(silo_dir),
        "-c", "conda-forge", "mypy", "black", "flake8", "pytest",
        "--yes"
    ]

    logger.info("Installing additional packages...")
    run_cmd(install_cmd)

    pip_install = [
        conda_executable, "run", "--prefix", str(silo_dir),
        "python", "-m", "pip", "install",
        "chemformula", "periodictable", "mendeleev",
        "PySide6", "pyqtgraph", "pyvista", "pyvistaqt", "vtk",
        "qcelemental", "pluggy", "fastapi", "uvicorn", "watchdog"
    ]

    logger.info("Installing pip packages...")
    run_cmd(pip_install)

    project_install = [
        conda_executable, "run", "--prefix", str(silo_dir),
        "python", "-m", "pip", "install", "--no-deps", "--editable", str(REPO_ROOT)
    ]

    logger.info("Mapping the active CoChem-BASE checkout into the silo...")
    run_cmd(project_install)

    logger.info(f"Conda environment created successfully at: {silo_dir}")


if __name__ == "__main__":
    if "--probe-import" in sys.argv:
        # Intentional print for CLI output parsing
        print(cochem_base.__file__)
    else:
        setup_conda_silo()
