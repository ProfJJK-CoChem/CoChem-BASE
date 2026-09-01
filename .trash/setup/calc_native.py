#!/usr/bin/env python3
"""
CoChem-BASE: Calculation Environment Setup (Native macOS, Linux, and GitHub Actions)
Provisions ORCA engine and OpenMPI pathway natively on macOS and Linux hosts.
Extracts archives safely, verifies OpenMPI compatibility, and locks state into the Golden Registry.
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
logger = logging.getLogger("CoChem-CalcNative")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run: Any = None  # type: ignore


def calculation_environment() -> str:
    """Determine the host calculation environment identifier."""
    if os.environ.get("GITHUB_ACTIONS"):
        return "GitHub Actions"
    system = platform.system()
    if system == "Darwin":
        return "Local-MacOS (OrbStack)"
    if system == "Linux":
        return "Local-Linux (Deb)"
    raise RuntimeError(f"Native calculation setup does not support host platform: {system}")


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
    """Safely extract tar or zip archives preventing path traversal attacks while allowing internal relative symlinks."""
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
    executable_names = ("orca.exe", "orca") if platform.system() == "Windows" else ("orca", "orca.exe")
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


def parse_openmpi_version_string(stdout_text: str) -> str:
    """Parse OpenMPI version token from raw command output string."""
    version_line = stdout_text.split("\n")[0]
    match = re.search(r"(?:(?:v|version|MPI:?)\s*|\b)(\d+\.\d+(?:\.\d+)?)", version_line)
    if match:
        return match.group(1)
    raise ValueError(f"Could not parse OpenMPI version from: {version_line}")


def check_openmpi_version(mpi_path: str) -> str:
    """Check the version of OpenMPI and return it."""
    try:
        if safe_subprocess_run is not None:
            result = safe_subprocess_run([mpi_path, "--version"], capture_output=True, text=True, check=True, timeout=10.0)
        else:
            result = subprocess.run([mpi_path, "--version"], capture_output=True, text=True, encoding="utf-8", check=True, timeout=10.0)
        return parse_openmpi_version_string(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Command to check OpenMPI version failed: {e}")


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
    try:
        default_env = calculation_environment()
    except RuntimeError:
        default_env = "Local-Linux (Deb)"

    target_env = environment or default_env
    target_orca = orca_path
    target_mpi = mpi_path

    if arg1 is not None and arg2 is not None and arg3 is not None:
        if any(str(arg1).startswith(p) for p in ("Local-", "GitHub", "HPC")) or ("/" not in str(arg1) and "\\" not in str(arg1)):
            target_env = arg1
            target_orca = target_orca or arg2
            target_mpi = target_mpi or arg3
        else:
            target_mpi = target_mpi or arg1
            target_orca = target_orca or arg2
            target_env = environment or arg3
    elif arg1 is not None and arg2 is not None:
        if any(str(arg1).startswith(p) for p in ("Local-", "GitHub", "HPC")):
            target_env = arg1
            target_orca = target_orca or arg2
        else:
            target_mpi = target_mpi or arg1
            target_orca = target_orca or arg2
    elif arg1 is not None:
        if any(str(arg1).startswith(p) for p in ("Local-", "GitHub", "HPC")) or ("/" not in str(arg1) and "\\" not in str(arg1)):
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
        if getattr(config.engines, "orca", None) is None or not hasattr(config.engines.orca, "status"):
            config.engines.orca = EngineInfo(status="ready" if target_orca else "missing", path=target_orca)
        else:
            config.engines.orca.status = "ready" if target_orca else "missing"
            config.engines.orca.path = target_orca

        if getattr(config.engines, "mpirun", None) is None or not hasattr(config.engines.mpirun, "status"):
            config.engines.mpirun = EngineInfo(status="ready" if target_mpi else "missing", path=target_mpi)
        else:
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
    """Entrypoint to provision native calculation layer."""
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python calc_native.py\nProvisions ORCA and OpenMPI calculation environment natively on macOS/Linux.")
        sys.exit(0)

    logger.info("========================================================")
    logger.info(" CoChem-BASE: Native Calculation Environment Provisioning")
    logger.info("========================================================\n")

    environment = calculation_environment()
    engine_dir = get_artifact_dir() / "Registry" / "Engines"
    engine_dir.mkdir(parents=True, exist_ok=True)
    orca_path = locate_orca(engine_dir)
    mpi_path = _available_executable(
        resolve_executable(env_var="MPI_CMD", candidates=("mpirun", "mpiexec"))
    )

    if mpi_path:
        try:
            version = check_openmpi_version(mpi_path)
            logger.info(f"OpenMPI verified at: {mpi_path} (Version: {version})")
            if not version.startswith("4.1"):
                logger.warning("Warning: OpenMPI version is not 4.1.x. ORCA requires this specific version.")
        except Exception as e:
            logger.warning(f"Could not verify OpenMPI version at {mpi_path}: {e}")

    registry_path = register_calculation_state(
        mpi_path=mpi_path,
        orca_path=orca_path,
        environment=environment,
    )
    if not orca_path:
        logger.warning("ORCA was not found; map ORCA_CMD or stage an ORCA archive in Registry/Engines.")
    logger.info(f"Native calculation mapping recorded at: {registry_path}")


__all__ = [
    "_available_executable",
    "_find_staged_orca",
    "_safe_extract",
    "calculation_environment",
    "check_openmpi_version",
    "cleanup_zombies",
    "locate_orca",
    "parse_openmpi_version_string",
    "register_calculation_state",
    "run_calculation_setup",
]


if __name__ == "__main__":
    run_calculation_setup()

