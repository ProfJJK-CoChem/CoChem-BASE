import logging
import os
import platform
import shutil
import sys
from pathlib import Path

import cochem_base.config_loader as config_loader
from setup.cochem_base_setup import provision_silo

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Setup paths and environment
BASE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_ROOT))
os.environ['COCHEM_BASE_ROOT'] = str(BASE_ROOT)

def resolve_artifact_path(value):
    path = Path(os.path.expandvars(value)).expanduser()
    if not path.is_absolute():
        path = Path.home() / path
    return path.resolve()

logger.info("==== TASK 1: New Install -> Create & Provision ====")
target_path = resolve_artifact_path(os.environ.get('COCHEM_ARTIFACT_DIR', 'CoChem_Artifacts'))
silo_path = target_path / 'Silos'
if silo_path.exists():
    logger.info(f"Deleting previous Silos directory at {silo_path}...")
    shutil.rmtree(silo_path, ignore_errors=True)
silo_path.mkdir(parents=True, exist_ok=True)
logger.info(f"Created CoChem_Artifacts/Silos at {silo_path}")
logger.info("Setting up minimum environment...")
os.environ['COCHEM_ARTIFACT_DIR'] = str(target_path)



try:
    success, env_dir, already = provision_silo(str(target_path))
    if success:
        logger.info("✅ New installation completed!")
    else:
        logger.info("❌ Installation failed.")
except Exception as e:
    logger.info(f"Error during setup: {e}")
    raise ValueError("CRITICAL: Provisioning failed. Exception Deflection blocked.") from e

logger.info("\n==== TASK 2: Running Environment Preflight Checks ====")


get_modules_dir = config_loader.get_modules_dir
resolve_executable = config_loader.resolve_executable

# This applies what the UI dropdowns would configure, and then we run tests
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

orca_path = resolve_executable(None, env_var='ORCA_CMD', candidates=('orca',))
mpi_path = resolve_executable(None, env_var='MPI_CMD', candidates=('mpirun', 'mpiexec'))
os.environ['ORCA_CMD'] = orca_path
os.environ['MPI_CMD'] = mpi_path

logger.info(f"Interface Env: {interface_env}")
logger.info(f"Calc Env: {calc_env}")
logger.info(f"ORCA Path: {orca_path}")
logger.info(f"OpenMPI Path: {mpi_path}")

logger.info("Running test suite...")
try:
    from test_suite.run_tests import run_all_preflight_checks
    results = run_all_preflight_checks(
        module_dir=str(get_modules_dir()),
        orca_path=orca_path,
        mpi_path=mpi_path,
    )
    all_passed = True
    for _key, res in results.items():
        logger.info(res['message'])
        if not res['status']:
            all_passed = False
    if all_passed:
        logger.info("✅ Environment is fully ready to go!")
    else:
        logger.info("❌ Tests failed.")
except Exception as e:
    logger.info(f"❌ Error running tests: {e}")
    raise ValueError("CRITICAL: Test suite crashed. Exception Deflection blocked.") from e
