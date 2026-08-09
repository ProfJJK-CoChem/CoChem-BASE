import os
import subprocess
import tempfile
import time

def run_single_core_orca_test(orca_path="orca"):
    """Runs a highly simplified <1 second ORCA job on a single core."""
    inp_content = """! SP tightscf
* xyz 0 1
H 0.0 0.0 0.0
H 0.0 0.0 0.74
*
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        inp_file = os.path.join(tmpdir, "test_job.inp")
        with open(inp_file, "w") as f:
            f.write(inp_content)
        
        try:
            start = time.time()
            result = subprocess.run([orca_path, inp_file], capture_output=True, text=True, cwd=tmpdir, timeout=10)
            end = time.time()
            if "ORCA TERMINATED NORMALLY" in result.stdout:
                return True, f"Success: ORCA single-core test passed in {end - start:.2f}s."
            else:
                return False, f"Error: ORCA ran but failed to terminate normally.\\nOutput Snippet:\\n{result.stdout[-500:]}"
        except FileNotFoundError:
            return False, f"Error: ORCA binary not found at '{orca_path}'. Please check paths."
        except subprocess.TimeoutExpired:
            return False, "Error: ORCA single-core test timed out."
        except Exception as e:
            return False, f"Error: An unexpected exception occurred: {str(e)}"

if __name__ == "__main__":
    print(run_single_core_orca_test()[1])
