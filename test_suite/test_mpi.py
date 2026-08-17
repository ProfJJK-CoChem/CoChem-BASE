import logging
import os
import subprocess
import atexit
import time
import shutil
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

try:
    import psutil
except ImportError:
    psutil = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestMPI")

def cleanup_zombies() -> None:
    """Atexit handler to sweep any orphaned ORCA/MPI processes."""
    if psutil is None:
        return
    current_proc = psutil.Process()
    children = current_proc.children(recursive=True)
    for child in children:
        try:
            if child.is_running():
                child.terminate()
        except psutil.Error as e:
            logger.warning(f"Failed to terminate zombie process {child.pid}: {e}")

atexit.register(cleanup_zombies)

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None

class TestResult(BaseModel):
    success: bool
    message: str

def get_artifacts_dir() -> Path:
    """Dynamic resolution of artifacts directory based on environment variables."""
    artifacts_env = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if artifacts_env:
        artifacts_path = Path(artifacts_env).resolve()
    else:
        artifacts_path = Path.home() / ".cochem" / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)
    return artifacts_path

def run_multi_core_orca_test(orca_path: str = "orca", mpi_path: Optional[str] = None) -> TestResult:
    """Runs a highly simplified <1 second ORCA job using OpenMPI (2 cores)."""
    inp_content = """! SP tightscf PAL2
* xyz 0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
*
"""
    artifacts_dir = get_artifacts_dir()
    inp_file = artifacts_dir / "test_job_mpi.inp"
    
    try:
        inp_file.write_text(inp_content, encoding="utf-8")
    except OSError as e:
        return TestResult(success=False, message=f"Error writing input file to artifacts directory: {e}")

    if not shutil.which(orca_path):
        return TestResult(success=False, message=f"Error: ORCA binary not found at '{orca_path}'. Please check paths.")
    if mpi_path and not shutil.which(mpi_path):
        return TestResult(success=False, message=f"Error: MPI binary not found at '{mpi_path}'. Please check paths.")

    execution_env = os.environ.copy()
    if mpi_path:
        mpi_executable = Path(mpi_path).expanduser()
        if mpi_executable.is_file():
            # Add mpi path to PATH
            execution_env["PATH"] = os.pathsep.join(
                (str(mpi_executable.resolve().parent), execution_env.get("PATH", ""))
            )
        execution_env["MPI_CMD"] = mpi_path

    cmd: List[str] = [orca_path, str(inp_file)]
    start = time.time()
    
    try:
        if safe_subprocess_run is not None:
            result = safe_subprocess_run(cmd, capture_output=True, text=True, cwd=str(artifacts_dir), timeout=15.0, check=True, env=execution_env)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(artifacts_dir), timeout=15.0, check=True, env=execution_env)
            
        stdout_text = result.stdout or ""
        end = time.time()
        
        if "ORCA TERMINATED NORMALLY" in stdout_text:
            return TestResult(success=True, message=f"Success: ORCA multi-core (MPI) test passed in {end - start:.2f}s. [E]")
        else:
            return TestResult(success=False, message=f"Error: ORCA MPI ran but failed to terminate normally. Check OpenMPI setup.\nOutput Snippet:\n{stdout_text[-500:]}")
            
    except subprocess.TimeoutExpired as e:
        return TestResult(success=False, message=f"Error: ORCA execution timed out after 15.0s: {e}")
    except subprocess.CalledProcessError as e:
        stdout_snippet = e.stdout[-500:] if e.stdout else ""
        stderr_snippet = e.stderr[-500:] if e.stderr else ""
        return TestResult(success=False, message=f"Error: ORCA execution failed with return code {e.returncode}.\nStdout: {stdout_snippet}\nStderr: {stderr_snippet}")
    except OSError as e:
        return TestResult(success=False, message=f"Error: OS Level issue invoking ORCA: {e}")
    finally:
        logger.debug("ORCA multi-core (MPI) execution finalized.")

if __name__ == "__main__":
    result = run_multi_core_orca_test()
    if result.success:
        logger.info(result.message)
    else:
        logger.error(result.message)
