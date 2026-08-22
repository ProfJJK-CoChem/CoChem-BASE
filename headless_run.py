"""Headless execution runner for CoChem-BASE environment provisioning and preflight tests."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

import cochem_base.config_loader as config_loader
from setup.cochem_base_setup import provision_silo

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

BASE_ROOT = Path(__file__).resolve().parent
if str(BASE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASE_ROOT))
os.environ["COCHEM_BASE_ROOT"] = str(BASE_ROOT)


def resolve_artifact_path(value: str | Path | None = None) -> Path:
    """Resolves target artifact directory path from input or environment."""
    if value is None:
        env_val = os.environ.get("COCHEM_ARTIFACT_DIR")
        if env_val:
            value = env_val
        else:
            value = "CoChem_Artifacts"
    path_str = str(value)
    expanded = os.path.expandvars(path_str)
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()


def get_interface_and_calc_env() -> tuple[str, str]:
    """Determines interface and calculation environment names."""
    if os.environ.get("CODESPACES"):
        return "Codespaces", "GitHub Actions"
    sys_name = platform.system()
    mapping = {
        "Windows": "Local-Windows (WSL)",
        "Darwin": "Local-MacOS (OrbStack)",
        "Linux": "Local-Linux (Deb)",
    }
    if sys_name in mapping:
        val = mapping[sys_name]
        return val, val
    return "Codespaces", "GitHub Actions"


def configure_execution_environment(
    orca_cmd: str | Path | None = None,
    mpi_cmd: str | Path | None = None,
) -> dict[str, Any]:
    """Sets environment variables for execution interface, calculation, and executables."""
    iface, calc = get_interface_and_calc_env()
    os.environ["COCHEM_INTERFACE_ENV"] = iface
    os.environ["COCHEM_CALC_ENV"] = calc

    if orca_cmd is not None:
        orca_path = str(Path(orca_cmd).resolve())
    else:
        orca_path = config_loader.resolve_executable(
            None, env_var="ORCA_CMD", candidates=("orca",)
        )

    if mpi_cmd is not None:
        mpi_path = str(Path(mpi_cmd).resolve())
    else:
        mpi_path = config_loader.resolve_executable(
            None, env_var="MPI_CMD", candidates=("mpirun", "mpiexec")
        )

    os.environ["ORCA_CMD"] = orca_path
    os.environ["MPI_CMD"] = mpi_path

    return {
        "COCHEM_INTERFACE_ENV": iface,
        "COCHEM_CALC_ENV": calc,
        "ORCA_CMD": orca_path,
        "MPI_CMD": mpi_path,
    }


def provision_cochem_environment(
    artifact_path: str | Path | None = None,
    clean_silo: bool = True,
) -> tuple[bool, Path, bool]:
    """Provisions CoChem environment and silo directory."""
    logger.info("==== TASK 1: New Install -> Create & Provision ====")
    target_path = resolve_artifact_path(artifact_path)
    silo_path = target_path / "Silos"
    if clean_silo and silo_path.exists():
        logger.info(f"Deleting previous Silos directory at {silo_path}...")
        shutil.rmtree(silo_path, ignore_errors=True)
    silo_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created CoChem_Artifacts/Silos at {silo_path}")
    logger.info("Setting up minimum environment...")
    os.environ["COCHEM_ARTIFACT_DIR"] = str(target_path)

    try:
        success, env_dir, already = provision_silo(str(target_path))
        if success:
            logger.info("✅ New installation completed!")
        else:
            logger.info("❌ Installation failed.")
        return success, env_dir, already
    except Exception as e:
        logger.info(f"Error during setup: {e}")
        raise ValueError("CRITICAL: Provisioning failed. EXCEPTION_DEFLECTION_BLOCKED") from e


def run_preflight_suite(
    module_dir: str | Path | None = None,
    orca_path: str | None = None,
    mpi_path: str | None = None,
) -> tuple[bool, Any]:
    """Executes preflight validation suite."""
    logger.info("\n==== TASK 2: Running Environment Preflight Checks ====")
    if module_dir is None:
        module_dir = config_loader.get_modules_dir()
    else:
        module_dir = str(Path(module_dir))

    if orca_path is None:
        orca_path = config_loader.resolve_executable(
            None, env_var="ORCA_CMD", candidates=("orca",)
        )
    if mpi_path is None:
        mpi_path = config_loader.resolve_executable(
            None, env_var="MPI_CMD", candidates=("mpirun", "mpiexec")
        )

    try:
        from test_suite.run_tests import run_all_preflight_checks

        results = run_all_preflight_checks(
            module_dir=str(module_dir),
            orca_path=orca_path,
            mpi_path=mpi_path,
        )
        all_passed = True
        for _key, res in results.model_dump().items():
            logger.info(res["message"])
            if not res["status"]:
                all_passed = False
        if all_passed:
            logger.info("✅ Environment is fully ready to go!")
        else:
            logger.info("❌ Tests failed.")
        return all_passed, results
    except Exception as e:
        logger.info(f"❌ Error running tests: {e}")
        raise ValueError("CRITICAL: Test suite crashed. EXCEPTION_DEFLECTION_BLOCKED") from e


def main(args: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="CoChem Headless Runner")
    parser.add_argument("--artifact-dir", type=str, default=None)
    parser.add_argument("--module-dir", type=str, default=None)
    parser.add_argument("--orca-cmd", type=str, default=None)
    parser.add_argument("--mpi-cmd", type=str, default=None)
    parser.add_argument("--clean", action="store_true", default=False)
    parser.add_argument("--skip-provision", action="store_true", default=False)
    parser.add_argument("--skip-tests", action="store_true", default=False)

    parsed = parser.parse_args(args)

    if not parsed.skip_provision:
        success, _, _ = provision_cochem_environment(
            artifact_path=parsed.artifact_dir,
            clean_silo=parsed.clean,
        )
        if not success:
            return 1

    configure_execution_environment(
        orca_cmd=parsed.orca_cmd,
        mpi_cmd=parsed.mpi_cmd,
    )

    if not parsed.skip_tests:
        all_passed, _ = run_preflight_suite(
            module_dir=parsed.module_dir,
            orca_path=parsed.orca_cmd,
            mpi_path=parsed.mpi_cmd,
        )
        if not all_passed:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
