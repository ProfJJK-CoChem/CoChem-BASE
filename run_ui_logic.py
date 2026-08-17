import json
import logging
import os
import shutil
import sys
import traceback
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def resolve_base_root():
    mapped_root = os.environ.get('COCHEM_BASE_ROOT')
    if mapped_root:
        root = Path(os.path.expandvars(mapped_root)).expanduser().resolve()
        if (root / 'setup' / 'cochem_base_setup.py').is_file():
            return root
        raise RuntimeError(f'COCHEM_BASE_ROOT does not contain CoChem-BASE: {root}')
    for candidate in (Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents):
        for root in (candidate, candidate / 'CoChem-BASE'):
            if (root / 'setup' / 'cochem_base_setup.py').is_file():
                return root.resolve()
    raise RuntimeError('Unable to locate CoChem-BASE. Set COCHEM_BASE_ROOT to this checkout.')

def resolve_artifact_path(value):
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()

def main():
    try:
        BASE_ROOT = resolve_base_root()
        if str(BASE_ROOT) not in sys.path:
            sys.path.insert(0, str(BASE_ROOT))
        os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)

        import cochem_base.config_loader as config_loader
        resolve_conda_executable = config_loader.resolve_conda_executable

        default_art = resolve_artifact_path(os.environ.get('COCHEM_ARTIFACT_DIR', 'CoChem_Artifacts'))
        conda_exe = os.environ.get('COCHEM_CONDA_EXE', resolve_conda_executable(required=False))

        # --- Task 1: Cell 03 'New Install' and 'Create & Provision' ---
        logger.info("--- TASK 1: Cell 03 ---")
        target_path = default_art
        silo_path = target_path / 'Silos'
        if silo_path.exists():
            logger.info(f"Deleting previous Silos directory at {silo_path}...")
            shutil.rmtree(silo_path, ignore_errors=True)

        logger.info("Setting up minimum environment...")
        os.environ['COCHEM_ARTIFACT_DIR'] = str(target_path)
        if conda_exe and conda_exe.strip():
            os.environ['COCHEM_CONDA_EXE'] = conda_exe.strip()

        from setup.cochem_base_setup import provision_silo

        def log_cb(msg):
            sys.stdout.write(msg)

        success, env_dir, already_provisioned = provision_silo(str(target_path), log_callback=log_cb)

        if success:
            logger.info("SUCCESS: New installation completed and ready for the next step!")
        else:
            logger.info("FAILURE: Silo provisioning failed.")
            return {"status": "FAILURE", "error": "Silo provisioning failed"}

        # --- Task 2: Cell 05 'Interface Env: Codespaces', 'Calc Env: GitHub Actions' ---
        logger.info("\n--- TASK 2: Cell 05 ---")
        get_modules_dir = config_loader.get_modules_dir
        resolve_executable = config_loader.resolve_executable

        def resolve_tool_paths(orca_value=None, mpi_value=None):
            orca_path = resolve_executable(orca_value, env_var='ORCA_CMD', candidates=('orca',))
            mpi_path = resolve_executable(mpi_value, env_var='MPI_CMD', candidates=('mpirun', 'mpiexec'))
            return orca_path, mpi_path

        # Apply dropdown selections setting environment/config conceptually
        # Though the logic primarily runs run_all_preflight_checks
        import platform
        interface_env = {
            'Windows': 'Local-Windows (WSL)',
            'Darwin': 'Local-MacOS (OrbStack)',
            'Linux': 'Local-Linux (Deb)',
        }.get(platform.system(), 'Codespaces')
        if os.environ.get('CODESPACES'):
            interface_env = 'Codespaces'
        calc_env = interface_env if interface_env != 'Codespaces' else 'GitHub Actions'

        os.environ['COCHEM_INTERFACE_ENV'] = interface_env
        os.environ['COCHEM_CALC_ENV'] = calc_env

        orca_path, mpi_path = resolve_tool_paths()
        if orca_path:
            os.environ['ORCA_CMD'] = orca_path
        if mpi_path:
            os.environ['MPI_CMD'] = mpi_path

        logger.info(f"Resolved ORCA Path: {orca_path}")
        logger.info(f"Resolved MPI Path: {mpi_path}")

        from test_suite.run_tests import run_all_preflight_checks
        results = run_all_preflight_checks(
            module_dir=str(get_modules_dir()),
            orca_path=orca_path,
            mpi_path=mpi_path,
        )

        all_passed = True
        for key, res in results.items():
            if key in ['modules', 'orca_single', 'orca_mpi']:
                logger.info(res['message'])
                if not res['status']:
                    all_passed = False

        if all_passed:
            logger.info("SUCCESS: Environment is fully ready to go!")
            return {"status": "SUCCESS", "results": results}
        else:
            logger.info("FAILURE: Tests failed. Please check paths or verify OpenMPI configuration.")
            return {"status": "FAILURE", "results": results}

    except Exception as e:
        logger.error(f"ERROR: {e}")
        traceback.print_exc()
        raise ValueError("CRITICAL: UI Logic run failed. Exception Deflection blocked. Process crashing.") from e

if __name__ == '__main__':
    res = main()
    with open('ui_task_result.json', 'w') as f:
        json.dump(res, f, indent=2)
