import json
import logging
from typing import Dict, Any, Optional
from .test_environment import check_cochem_base_silo, check_artifacts_dir
from .test_modules import check_modules_installed
from .test_orca import run_single_core_orca_test
from .test_mpi import run_multi_core_orca_test

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestSuiteRunner")


def run_all_preflight_checks(artifact_dir: Optional[str] = None, module_dir: Optional[str] = None, orca_path: str = "orca") -> Dict[str, Dict[str, Any]]:
    """Runs all environment and testing suite checks for the UI."""
    results = {}

    silo_ok, silo_msg = check_cochem_base_silo()
    results['silo'] = {'status': silo_ok, 'message': silo_msg}

    art_ok, art_msg = check_artifacts_dir(artifact_dir)
    results['artifacts'] = {'status': art_ok, 'message': art_msg}

    mod_ok, mod_msg = check_modules_installed(module_dir)
    results['modules'] = {'status': mod_ok, 'message': mod_msg}

    orca_ok, orca_msg = run_single_core_orca_test(orca_path)
    results['orca_single'] = {'status': orca_ok, 'message': orca_msg}

    mpi_ok, mpi_msg = run_multi_core_orca_test(orca_path)
    results['orca_mpi'] = {'status': mpi_ok, 'message': mpi_msg}

    return results


if __name__ == "__main__":
    logger.info(json.dumps(run_all_preflight_checks(), indent=2))
