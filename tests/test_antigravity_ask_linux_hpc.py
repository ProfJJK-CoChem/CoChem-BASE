import os
import subprocess
import tempfile
import sys
import pytest
import psutil
import atexit
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_zombies():
    logger.info("Sweeping for zombie processes...")
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    logger.warning(f"Reaping zombie process: {child.pid}")
                    child.wait(timeout=1)
                elif child.is_running():
                    logger.info(f"Terminating running child process: {child.pid}")
                    child.terminate()
                    child.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired, FileNotFoundError) as e:
                logger.error(f"Error handling child process {child.pid}: {e}")
    except (psutil.NoSuchProcess, FileNotFoundError) as e:
        logger.error(f"Error during zombie sweep: {e}")

atexit.register(cleanup_zombies)

def run_script_in_subprocess(script_content: str, env_vars: dict = None, stdin_data: str = None):
    env = os.environ.copy()
    env["COCHEM_OS_TARGET"] = "linux"
    env["SLURM_JOB_ID"] = "12345"
    
    repo_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    
    if env_vars:
        for k, v in env_vars.items():
            if v is None:
                if k in env:
                    del env[k]
            else:
                env[k] = v
                
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script_content)
        temp_path = Path(f.name)
        
    try:
        result = subprocess.run(
            [sys.executable, str(temp_path)],
            env=env,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=15,
            check=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess failed with exit code {e.returncode}: {e.stderr}")
        return e
    except subprocess.TimeoutExpired as e:
        logger.error(f"Subprocess timed out after {e.timeout}s")
        return e
    finally:
        if temp_path.exists():
            temp_path.unlink()

def test_query_no_token():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
try:
    daemon.query("Hello")
except ValueError as e:
    logging.error("VALUE_ERROR:" + str(e))
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, env_vars={"GEMINI_API_KEY": None})
    assert isinstance(result, subprocess.CompletedProcess), "Subprocess did not complete successfully"
    assert "VALUE_ERROR:[MISSING DATA] Please sign in" in result.stderr

def test_query_invalid_token_api_error_hpc():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
daemon.google_oauth_flow()
try:
    daemon.query("Hello")
except RuntimeError as e:
    logging.error("RUNTIME_ERROR:" + str(e))
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, env_vars={"GEMINI_API_KEY": "INVALID_TOKEN_999"})
    assert isinstance(result, subprocess.CompletedProcess), "Subprocess did not complete successfully"
    assert "RUNTIME_ERROR:API Error" in result.stderr

def test_guardrail_strip_hpc():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
sanitized = daemon._guardrail_strip("Optimize this: O 0.00000 0.00000 0.00000")
logging.info("SANITIZED:" + sanitized)
"""
    result = run_script_in_subprocess(script)
    assert isinstance(result, subprocess.CompletedProcess), "Subprocess did not complete successfully"
    assert "SANITIZED:Optimize this: O <XYZ_STRIPPED>" in result.stderr
