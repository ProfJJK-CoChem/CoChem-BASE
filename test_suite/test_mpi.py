import os
import subprocess
import tempfile
import time
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TestMPI")

try:
    from core_engine.cochem_core_subprocess_broker import safe_subprocess_run
except ImportError:
    safe_subprocess_run = None


def run_multi_core_orca_test(orca_path: str = "orca") -> Tuple[bool, str]:
    """Runs a highly simplified <1 second ORCA job using OpenMPI (2 cores)."""
    inp_content = """! SP tightscf PAL2
* xyz 0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
*
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        inp_file = os.path.join(tmpdir, "test_job_mpi.inp")
        with open(inp_file, "w", encoding="utf-8") as f:
            f.write(inp_content)

        try:
            start = time.time()
            if safe_subprocess_run:
                result = safe_subprocess_run([orca_path, inp_file], capture_output=True, text=True, cwd=tmpdir, timeout=15.0, check=False)
            else:
                result = subprocess.run([orca_path, inp_file], capture_output=True, text=True, cwd=tmpdir, timeout=15.0, check=False)  # check=True
            end = time.time()

            stdout_text = result.stdout or ""
            if "ORCA TERMINATED NORMALLY" in stdout_text:
                return True, f"Success: ORCA multi-core (MPI) test passed in {end - start:.2f}s."
            else:
                return False, f"Error: ORCA MPI ran but failed to terminate normally. Check OpenMPI setup.\nOutput Snippet:\n{stdout_text[-500:]}"
        except FileNotFoundError:
            return False, f"Error: ORCA binary not found at '{orca_path}'. Please check paths."
        except subprocess.TimeoutExpired:
            return False, "Error: ORCA multi-core test timed out. OpenMPI might be hanging."
        except Exception as e:
            return False, f"Error: An unexpected exception occurred: {str(e)}"


if __name__ == "__main__":
    logger.info(run_multi_core_orca_test()[1])
