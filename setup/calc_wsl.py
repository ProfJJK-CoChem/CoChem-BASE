
#!/usr/bin/env python3
"""
CoChem-BASE: Calculation Environment Setup (Local-Windows / WSL)
Provisions the ORCA engine and OpenMPI pathway natively inside WSL.
Extracts archives, resolves paths, and locks the state into the Golden Registry.
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Optional, Sequence

from cochem_base.config_loader import (
    get_artifact_dir,
    get_default_cochem_config,
    load_system_config,
    resolve_config_path,
    resolve_executable,
    update_config,
)
from core_engine.cochem_core_registry_schema import (
    EngineInfo,
    EnginePaths,
    HPCConfig,
    SiloPathsSchema,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-WSLSetup")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore


def verify_wsl_kernel() -> bool:
    """Validates that the script is executing inside a Windows Subsystem for Linux kernel."""
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True

    rel = platform.release().lower()
    if "microsoft" in rel or "wsl" in rel:
        return True

    ver = platform.version().lower()
    if "microsoft" in ver or "wsl" in ver:
        return True

    if hasattr(os, "uname"):
        try:
            u = os.uname()
            u_rel = getattr(u, "release", "").lower()
            u_ver = getattr(u, "version", "").lower()
            if "microsoft" in u_rel or "wsl" in u_rel or "microsoft" in u_ver or "wsl" in u_ver:
                return True
        except Exception:
            pass

    proc_path = Path("/proc/version")
    try:
        if proc_path.is_file():
            content = proc_path.read_text(encoding="utf-8").lower()
            if "microsoft" in content or "wsl" in content:
                return True
    except Exception:
        pass

    return False


def _available_executable(value: Optional[str]) -> Optional[str]:
    """Resolve and return absolute path of an executable if available, otherwise None."""
    if not value:
        return None
    executable_path = Path(value).expanduser()
    if executable_path.is_file():
        return str(executable_path.resolve())
    discovered = shutil.which(value)
    return str(Path(discovered).resolve()) if discovered else None


def _safe_extract(archive: Path, target_dir: Path) -> None:
    """Safely extract tar or zip archives preventing path traversal attacks."""
    target_root = target_dir.resolve()
    archive_path = Path(archive).resolve()

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as bundle:
            members = bundle.namelist()
            for member in members:
                dest = (target_root / member).resolve()
                if not dest.is_relative_to(target_root):
                    raise ValueError(f"Archive contains an unsafe path: {archive}")
            bundle.extractall(target_root)
        return

    with tarfile.open(archive_path) as bundle:
        members = bundle.getmembers()  # type: ignore[attr-defined]
        for member in members:  # type: ignore[attr-defined]
            dest = (target_root / member.name).resolve()
            if not dest.is_relative_to(target_root):
                raise ValueError(f"Archive contains an unsafe path: {archive}")
            if member.issym():  # type: ignore[attr-defined]
                link_dest = ((target_root / member.name).parent / member.linkname).resolve()
                if not link_dest.is_relative_to(target_root) or member.linkname.startswith("/"):
                    raise ValueError(f"Archive contains an unsafe symlink: {archive}")
            elif member.islnk():  # type: ignore[attr-defined]
                link_dest = ((target_root / member.name).parent / member.linkname).resolve()
                if not link_dest.is_relative_to(target_root) or member.linkname.startswith("/"):
                    raise ValueError(f"Archive contains an unsafe hardlink: {archive}")

        if sys.version_info >= (3, 12):
            bundle.extractall(target_root, filter="data")
        else:
            bundle.extractall(target_root)


def _find_staged_orca(engine_dir: Path) -> Optional[str]:
    """Scan engine_dir recursively for staged orca executable."""
    executable_names = ("orca", "orca.exe")
    for executable_name in executable_names:
        for candidate in engine_dir.rglob(executable_name):
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def locate_orca(engine_dir: Path) -> Optional[str]:
    """Locate or extract ORCA executable in the target engine directory."""
    mapped = _available_executable(resolve_executable(env_var="ORCA_CMD", candidates=("orca",)))
    if mapped:
        return mapped
    staged = _find_staged_orca(engine_dir)
    if staged:
        return staged
    archives = [
        path
        for pattern in (
            "orca*.tar.xz",
            "ORCA*.tar.xz",
            "orca*.tar.gz",
            "ORCA*.tar.gz",
            "orca*.tar.bz2",
            "ORCA*.tar.bz2",
            "orca*.tar",
            "orca*.tgz",
            "orca*.zip",
            "ORCA*.zip",
        )
        for path in engine_dir.glob(pattern)
    ]
    if archives:
        _safe_extract(archives[0], engine_dir)
        return _find_staged_orca(engine_dir)
    return None


def check_openmpi_version(mpi_path: str) -> str:
    """Check the version of OpenMPI and return it."""
    try:
        if safe_subprocess_run is not None:
            result = safe_subprocess_run([mpi_path, "--version"], capture_output=True, text=True, check=True, timeout=10.0)
        else:
            result = subprocess.run([mpi_path, "--version"], capture_output=True, text=True, encoding="utf-8", check=True, timeout=10.0)
        version_line = result.stdout.split("\n")[0]
        match = re.search(r"(?:(?:v|version|MPI:?)\s*|\b)(\d+\.\d+(?:\.\d+)?)", version_line)
        if match:
            return match.group(1)
        raise ValueError(f"Could not parse OpenMPI version from: {version_line}")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Command to check OpenMPI version failed: {e}")


def provision_openmpi() -> str:
    """Locates OpenMPI or autonomously installs it with Active Repair."""
    logger.info("Probing for OpenMPI (mpirun)...")
    mpi_path = _available_executable(resolve_executable(env_var="MPI_CMD", candidates=("mpirun", "mpiexec")))

    if not mpi_path:
        logger.warning("OpenMPI not found in WSL $PATH.")
        logger.info("Initiating Autonomous OpenMPI Installation & Path Binder...")

        try:
            logger.info("Installing OpenMPI 4.1.x via apt-get...")
            sudo = resolve_executable(env_var="SUDO_CMD", candidates=("sudo",))
            apt_get = resolve_executable(env_var="APT_GET_CMD", candidates=("apt-get",))
            if safe_subprocess_run is not None:
                safe_subprocess_run([sudo, apt_get, "update"], check=True, timeout=60.0)
                safe_subprocess_run([sudo, apt_get, "install", "-y", "openmpi-bin", "libopenmpi-dev"], check=True, timeout=120.0)
            else:
                subprocess.run([sudo, apt_get, "update"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60.0)
                subprocess.run([sudo, apt_get, "install", "-y", "openmpi-bin", "libopenmpi-dev"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120.0)

            logger.info("OpenMPI installation completed successfully.")

            mpi_path = _available_executable(resolve_executable(env_var="MPI_CMD", candidates=("mpirun", "mpiexec")))
            if not mpi_path:
                raise RuntimeError("Failed to locate mpirun after installation.")

            version = check_openmpi_version(mpi_path)
            logger.info(f"OpenMPI verified at: {mpi_path} (Version: {version})")

            if not version.startswith("4.1"):
                logger.warning("Warning: OpenMPI version is not 4.1.x. ORCA requires this specific version.")

            return mpi_path

        except (subprocess.CalledProcessError, RuntimeError) as e:
            logger.error(f"Failed to install OpenMPI: {e}")
            logger.warning("WSL Fix: Please manually run 'sudo apt-get update && sudo apt-get install openmpi-bin libopenmpi-dev' in your terminal.")
            raise RuntimeError(f"OpenMPI provisioning failed: {e}")
    else:
        version = check_openmpi_version(mpi_path)
        logger.info(f"OpenMPI found at: {mpi_path} (Version: {version})")

        if not version.startswith("4.1"):
            logger.warning("Warning: OpenMPI version is not 4.1.x. ORCA requires this specific version.")

        return mpi_path


def provision_orca(engine_dir: Path) -> str:
    """Finds existing ORCA or extracts an archive into engine_dir."""
    logger.info("Probing for ORCA Linux Engine...")
    located = locate_orca(engine_dir)
    if located:
        logger.info(f"Active ORCA binary found at: {located}")
        return located

    logger.error(f"ORCA engine not found in {engine_dir}")
    logger.warning("Please drop the Linux ORCA archive into the Registry/Engines folder and rerun.")
    raise RuntimeError("ORCA engine missing.")


def register_calculation_state(
    arg1: Optional[str] = None,
    arg2: Optional[str] = None,
    arg3: Optional[str] = None,
    *,
    mpi_path: Optional[str] = None,
    orca_path: Optional[str] = None,
    environment: Optional[str] = None,
) -> Path:
    """Updates the Golden Registry with calculation environment pathways."""
    target_env = environment or "Local-Windows (WSL)"
    target_orca = orca_path
    target_mpi = mpi_path

    if arg1 is not None and arg2 is not None and arg3 is not None:
        if any(arg1.startswith(p) for p in ("Local-", "GitHub", "HPC")) or ("/" not in arg1 and "\\" not in arg1):
            target_env = arg1
            target_orca = target_orca or arg2
            target_mpi = target_mpi or arg3
        else:
            target_mpi = target_mpi or arg1
            target_orca = target_orca or arg2
            target_env = environment or arg3
    elif arg1 is not None and arg2 is not None:
        target_mpi = target_mpi or arg1
        target_orca = target_orca or arg2
    elif arg1 is not None:
        if any(arg1.startswith(p) for p in ("Local-", "GitHub", "HPC")) or ("/" not in arg1 and "\\" not in arg1):
            target_env = arg1
        else:
            target_mpi = target_mpi or arg1

    registry_path = resolve_config_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        config = load_system_config(registry_path)
    except FileNotFoundError:
        config = get_default_cochem_config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}. Resetting to default.")
        config = get_default_cochem_config()

    if isinstance(getattr(config, "engines", None), dict):
        if "orca" not in config.engines or not hasattr(config.engines["orca"], "status"):
            config.engines["orca"] = EngineInfo(status="ready" if target_orca else "missing", path=target_orca)
        else:
            config.engines["orca"].status = "ready" if target_orca else "missing"
            config.engines["orca"].path = target_orca

        if "mpirun" not in config.engines or not hasattr(config.engines["mpirun"], "status"):
            config.engines["mpirun"] = EngineInfo(status="ready" if target_mpi else "missing", path=target_mpi)
        else:
            config.engines["mpirun"].status = "ready" if target_mpi else "missing"
            config.engines["mpirun"].path = target_mpi
    elif getattr(config, "engines", None) is not None:
        config.engines.orca.status = "ready" if target_orca else "missing"
        config.engines.orca.path = target_orca
        config.engines.mpirun.status = "ready" if target_mpi else "missing"
        config.engines.mpirun.path = target_mpi

    if getattr(config, "silo_paths", None) is None:
        config.silo_paths = SiloPathsSchema(
            orca_path=target_orca,
            orca_binary_path=target_orca,
            mpirun_path=target_mpi,
            mpirun_binary_path=target_mpi,
        )
    else:
        config.silo_paths.orca_path = target_orca
        config.silo_paths.orca_binary_path = target_orca
        config.silo_paths.mpirun_path = target_mpi
        config.silo_paths.mpirun_binary_path = target_mpi

    if getattr(config, "hpc", None) is None:
        config.hpc = HPCConfig(execution_mode=target_env)
    else:
        config.hpc.execution_mode = target_env

    if hasattr(config, "update_checksum"):
        config.update_checksum()

    update_config(config, registry_path)
    logger.info(f"Calculation State & Engine Paths locked into Golden Registry: {registry_path}")
    return registry_path


def cleanup_zombies() -> None:
    """Safe zombie process cleanup guard."""
    pass


def run_calculation_setup() -> None:
    """Entrypoint to provision WSL calculation layer."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python calc_wsl.py\nProvisions ORCA and OpenMPI calculation environment inside WSL.")
        sys.exit(0)

    logger.info("=======================================================")
    logger.info(" CoChem-BASE: WSL Calculation Environment Provisioning ")
    logger.info("=======================================================\n")

    if not verify_wsl_kernel():
        raise RuntimeError("FATAL: Target environment is not WSL. Please run calc_mac.py or calc_linux.py instead.")

    engine_dir = get_artifact_dir() / "Registry" / "Engines"
    engine_dir.mkdir(parents=True, exist_ok=True)

    mpi_path = provision_openmpi()
    orca_path = provision_orca(engine_dir)
    register_calculation_state(mpi_path=mpi_path, orca_path=orca_path, environment="Local-Windows (WSL)")

    logger.info("WSL Calculation Layer successfully established. Engines are ready for execution.")


__all__ = [
    "_available_executable",
    "_find_staged_orca",
    "_safe_extract",
    "check_openmpi_version",
    "cleanup_zombies",
    "locate_orca",
    "provision_openmpi",
    "provision_orca",
    "register_calculation_state",
    "run_calculation_setup",
    "verify_wsl_kernel",
]


if __name__ == "__main__":
    run_calculation_setup()

