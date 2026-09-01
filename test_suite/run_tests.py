import json
import logging
import os
import atexit
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path for direct execution and isolated test runs
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    import psutil
except ImportError:
    psutil = None
from pydantic import BaseModel, Field

from cochem_base.config_loader import resolve_executable

try:
    from .test_environment import check_artifacts_dir, check_cochem_base_silo
    from .test_modules import check_modules_installed
    from .test_mpi import run_multi_core_orca_test
    from .test_orca import run_single_core_orca_test
except ImportError:
    from test_suite.test_environment import check_artifacts_dir, check_cochem_base_silo
    from test_suite.test_modules import check_modules_installed
    from test_suite.test_mpi import run_multi_core_orca_test
    from test_suite.test_orca import run_single_core_orca_test

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestSuiteRunner")

class TestResult(BaseModel):
    status: bool = Field(..., description="True if the test passed, False otherwise")
    message: str = Field(..., description="Message describing the result")

class PreflightCheckResult(BaseModel):
    silo: TestResult
    artifacts: TestResult
    modules: TestResult
    orca_single: TestResult
    orca_mpi: TestResult

def cleanup_zombie_processes():
    """Sweeps for zombie processes and terminates them."""
    if psutil is None:
        logger.warning("psutil not installed, skipping zombie process sweep.")
        return
    for proc in psutil.process_iter(['pid', 'status', 'name']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE:
                logger.info(f"Terminating zombie process: {proc.info['name']} (PID: {proc.info['pid']})")
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

atexit.register(cleanup_zombie_processes)

def run_all_preflight_checks(
    artifact_dir: Optional[Path] = None,
    module_dir: Optional[Path] = None,
    orca_path: Optional[Path] = None,
    mpi_path: Optional[Path] = None,
) -> PreflightCheckResult:
    """Runs all environment and testing suite checks for the UI."""
    
    if artifact_dir is None:
        artifact_dir = Path(os.environ.get("COCHEM_ARTIFACT_DIR", Path.home() / "cochem_artifacts"))

    try:
        resolved_orca = resolve_executable(str(orca_path) if orca_path else None, env_var="ORCA_CMD", candidates=("orca",))
    except Exception as e:
        logger.error(f"Failed to resolve ORCA: {e}")
        resolved_orca = ""

    try:
        resolved_mpi = resolve_executable(str(mpi_path) if mpi_path else None, env_var="MPI_CMD", candidates=("mpirun", "mpiexec"))
    except Exception as e:
        logger.error(f"Failed to resolve MPI: {e}")
        resolved_mpi = ""

    def safe_run_test(test_func, *args, **kwargs) -> TestResult:
        try:
            ok, msg = test_func(*args, **kwargs)
            return TestResult(status=ok, message=msg)
        except Exception as e:
            logger.error(f"Test {test_func.__name__} raised an exception: {e}")
            return TestResult(status=False, message=f"Error: Exception during test execution: {str(e)}")

    silo_res = safe_run_test(check_cochem_base_silo)
    art_res = safe_run_test(check_artifacts_dir, str(artifact_dir))
    mod_res = safe_run_test(check_modules_installed, str(module_dir) if module_dir else None)
    orca_res = safe_run_test(run_single_core_orca_test, resolved_orca) if resolved_orca else TestResult(status=False, message="Error: ORCA not found.")
    mpi_res = safe_run_test(run_multi_core_orca_test, resolved_orca, resolved_mpi) if resolved_orca and resolved_mpi else TestResult(status=False, message="Error: ORCA or MPI not found.")

    return PreflightCheckResult(
        silo=silo_res,
        artifacts=art_res,
        modules=mod_res,
        orca_single=orca_res,
        orca_mpi=mpi_res
    )

if __name__ == "__main__":
    try:
        results = run_all_preflight_checks()
        logger.info(f"Preflight Results:\n{results.model_dump_json(indent=2)}")
    except Exception as e:
        logger.error(f"Fatal error running preflight checks: {e}")
        import sys
        sys.exit(1)
