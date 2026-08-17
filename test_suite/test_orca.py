import logging
import os
import subprocess
import tempfile
import time
import shutil
import atexit
import psutil
import pathlib
from typing import Any, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestORCA")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None

def _sweep_zombies():
    """Sweep zombie processes for subprocess safety."""
    try:
        current_process = psutil.Process(os.getpid())
        for child in current_process.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass

atexit.register(_sweep_zombies)


def run_single_core_orca_test(orca_path: str = os.environ.get("ORCA_CMD", "orca")) -> Tuple[bool, str]:
    """Runs a highly simplified <1 second ORCA job on a single core."""
    inp_content = """! HF STO-3G SP tightscf
* xyz 0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
*
"""
    artifacts_dir = os.environ.get("COCHEM_ARTIFACTS_DIR", str(pathlib.Path.home() / "cochem_artifacts"))
    os.makedirs(artifacts_dir, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=artifacts_dir) as tmpdir:
        inp_file = os.path.join(tmpdir, "test_job.inp")
        with open(inp_file, "w", encoding="utf-8") as f:
            f.write(inp_content)

        if not shutil.which(orca_path):
            return False, f"Error: ORCA binary not found at '{orca_path}'. Please check paths."

        try:
            start = time.time()
            if safe_subprocess_run is not None:
                result = safe_subprocess_run([orca_path, inp_file], capture_output=True, text=True, cwd=tmpdir, timeout=10.0, check=True)
            else:
                result = subprocess.run([orca_path, inp_file], capture_output=True, text=True, cwd=tmpdir, timeout=10.0, check=True)
            end = time.time()

            stdout_text = result.stdout or ""
            if "ORCA TERMINATED NORMALLY" in stdout_text:
                return True, f"Success: ORCA single-core test passed in {end - start:.2f}s."
            else:
                return False, f"Error: ORCA ran but failed to terminate normally.\nOutput Snippet:\n{stdout_text[-500:]}"
        except subprocess.TimeoutExpired as e:
            logger.error("ORCA execution timed out.")
            return False, "Error: ORCA execution timed out after 10.0s."
        except subprocess.CalledProcessError as e:
            logger.error(f"ORCA failed with return code {e.returncode}.")
            return False, f"Error: ORCA failed with return code {e.returncode}.\nOutput Snippet:\n{e.output[-500:] if e.output else 'None'}"
        except OSError as e:
            logger.error(f"OSError during ORCA execution: {e}")
            return False, f"Error: OS error executing ORCA: {e}"
        finally:
            _sweep_zombies()
            logger.debug("ORCA single-core execution finalized.")


if __name__ == "__main__":
    logger.info(run_single_core_orca_test()[1])
