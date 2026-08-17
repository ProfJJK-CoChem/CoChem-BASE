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
            except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied) as e:
                logger.error(f"Error handling child process {child.pid}: {e}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
        logger.error(f"Error during zombie sweep: {e}")

atexit.register(cleanup_zombies)

def run_script_in_subprocess(script_content: str, env_vars: dict = None, stdin_data: str = None):
    # Set Codespaces + Linux vars
    env = os.environ.copy()
    env["CODESPACES"] = "true"
    env["COCHEM_CALCULATION_OS"] = "linux"
    
    # Ensure cochem_base can be found
    repo_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    
    # Remove GEMINI_API_KEY to ensure tests don't accidentally pass via the real environment
    if "GEMINI_API_KEY" in env:
        del env["GEMINI_API_KEY"]
        
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
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass

def test_google_oauth_env_key():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
try:
    token = daemon.google_oauth_flow()
    logging.info("TOKEN_RESULT:" + token)
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, env_vars={"GEMINI_API_KEY": "test_env_token_abc"})
    assert isinstance(result, subprocess.CompletedProcess), "Subprocess did not complete successfully"
    assert "TOKEN_RESULT:test_env_token_abc" in result.stderr

def test_google_oauth_interactive_token():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
try:
    token = daemon.google_oauth_flow()
    logging.info("TOKEN_RESULT:" + token)
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, stdin_data="test_interactive_token_xyz\n")
    assert isinstance(result, subprocess.CompletedProcess), "Subprocess did not complete successfully"
    assert "TOKEN_RESULT:test_interactive_token_xyz" in result.stderr

def test_google_oauth_interactive_empty():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
try:
    token = daemon.google_oauth_flow()
    logging.info("TOKEN_RESULT:" + token)
except ValueError as e:
    logging.error("VALUE_ERROR:" + str(e))
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, stdin_data="\n")
    assert isinstance(result, subprocess.CompletedProcess), f"Subprocess did not complete successfully: {getattr(result, 'stderr', result)}"
    assert "VALUE_ERROR:[MISSING DATA] Token cannot be empty." in result.stderr

def test_google_oauth_interactive_eof():
    script = """
import sys
import logging
from cochem_base.antigravity_daemon import AntigravityLocalDaemon
logging.basicConfig(level=logging.INFO, format="%(message)s")
daemon = AntigravityLocalDaemon()
try:
    token = daemon.google_oauth_flow()
    logging.info("TOKEN_RESULT:" + token)
except RuntimeError as e:
    logging.error("RUNTIME_ERROR:" + str(e))
except Exception as e:
    logging.error("ERROR:" + str(e))
"""
    result = run_script_in_subprocess(script, stdin_data="")
    assert isinstance(result, subprocess.CompletedProcess), f"Subprocess did not complete successfully: {getattr(result, 'stderr', result)}"
    assert "RUNTIME_ERROR:[HARD_ABORT: MISSING DATA] No interactive stdin available" in result.stderr
