#!/usr/bin/env python3
"""Map ORCA and MPI for native macOS, Linux, and GitHub Actions hosts."""

import logging
import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_executable,
    load_system_config,
    get_default_cochem_config,
    update_config,
    resolve_config_path,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-CalcNative")


def calculation_environment() -> str:
    if os.environ.get("GITHUB_ACTIONS"):
        return "GitHub Actions"
    system = platform.system()
    if system == "Darwin":
        return "Local-MacOS (OrbStack)"
    if system == "Linux":
        return "Local-Linux (Deb)"
    raise RuntimeError(f"Native calculation setup does not support host platform: {system}")


def _available_executable(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    executable_path = Path(value).expanduser()
    if executable_path.is_file():
        return str(executable_path.resolve())
    discovered = shutil.which(value)
    return str(Path(discovered).resolve()) if discovered else None


def _safe_extract(archive: Path, target_dir: Path) -> None:
    target_root = target_dir.resolve()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.namelist()
            if any(not (target_root / member).resolve().is_relative_to(target_root) for member in members):
                raise ValueError(f"Archive contains an unsafe path: {archive}")
            bundle.extractall(target_root)
        return
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()  # type: ignore
        if any(
            member.issym()  # type: ignore
            or member.islnk()  # type: ignore
            or not (target_root / member.name).resolve().is_relative_to(target_root)  # type: ignore
            for member in members
        ):
            raise ValueError(f"Archive contains an unsafe path: {archive}")
        if sys.version_info >= (3, 12):
            bundle.extractall(target_root, filter="data")
        else:
            bundle.extractall(target_root)


def _find_staged_orca(engine_dir: Path) -> Optional[str]:
    executable_names = ("orca.exe", "orca") if platform.system() == "Windows" else ("orca", "orca.exe")
    for executable_name in executable_names:
        for candidate in engine_dir.rglob(executable_name):
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def locate_orca(engine_dir: Path) -> Optional[str]:
    mapped = _available_executable(resolve_executable(env_var="ORCA_CMD", candidates=("orca",)))
    if mapped:
        return mapped
    staged = _find_staged_orca(engine_dir)
    if staged:
        return staged
    archives = [
        path
        for pattern in ("orca*.tar.xz", "ORCA*.tar.xz", "orca*.tar.gz", "ORCA*.tar.gz", "orca*.zip", "ORCA*.zip")
        for path in engine_dir.glob(pattern)
    ]
    if archives:
        _safe_extract(archives[0], engine_dir)
        return _find_staged_orca(engine_dir)
    return None


def register_calculation_state(environment: str, orca_path: Optional[str], mpi_path: Optional[str]) -> Path:
    registry_path = resolve_config_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        config = load_system_config(registry_path)
    except FileNotFoundError:
        config = get_default_cochem_config()
    except ValueError as e:
        logger.error(f"Failed to load config: {e}. Resetting to default.")
        config = get_default_cochem_config()

    if isinstance(config.engines, dict):
        if "orca" not in config.engines:
            config.engines["orca"] = {}
        config.engines["orca"].update({"status": "ready" if orca_path else "missing", "path": orca_path})
        
        if "mpirun" not in config.engines:
            config.engines["mpirun"] = {}
        config.engines["mpirun"].update({"status": "ready" if mpi_path else "missing", "path": mpi_path})
    else:
        config.engines.orca.status = "ready" if orca_path else "missing"
        config.engines.orca.path = orca_path
        config.engines.mpirun.status = "ready" if mpi_path else "missing"
        config.engines.mpirun.path = mpi_path

    config.hpc.execution_mode = environment
    update_config(config, registry_path)
    return registry_path


def run_calculation_setup() -> None:
    environment = calculation_environment()
    engine_dir = get_artifact_dir() / "Registry" / "Engines"
    engine_dir.mkdir(parents=True, exist_ok=True)
    orca_path = locate_orca(engine_dir)
    mpi_path = _available_executable(
        resolve_executable(env_var="MPI_CMD", candidates=("mpirun", "mpiexec"))
    )
    registry_path = register_calculation_state(environment, orca_path, mpi_path)
    if not orca_path:
        logger.warning("ORCA was not found; map ORCA_CMD or stage an ORCA archive in Registry/Engines.")
    logger.info(f"Native calculation mapping recorded at: {registry_path}")


if __name__ == "__main__":
    run_calculation_setup()
