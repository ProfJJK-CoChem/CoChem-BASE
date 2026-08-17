import os
import tempfile
import subprocess
import pytest
import logging
import atexit
import psutil
import pathlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_zombies():
    logger.info("Sweeping for zombie processes...")
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                if child.is_running():
                    child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.error(f"Failed to cleanup zombies: {e}")

atexit.register(cleanup_zombies)

SCRIPT_TEMPLATE = """
import os
import sys
from cochem_base.antigravity_daemon import AntigravityLocalDaemon

# Ensure env vars are respected
assert os.environ.get("CODESPACES") == "true"
assert os.environ.get("COCHEM_CALCULATION_OS") == "macos"

daemon = AntigravityLocalDaemon()

try:
    token = daemon.google_oauth_flow()
    print("TOKEN_ACQUIRED:" + token)
except Exception as e:
    print("ERROR:" + str(type(e).__name__) + ":" + str(e))
"""

@pytest.fixture
def run_script():
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8")
    path = temp.name
    temp.write(SCRIPT_TEMPLATE)
    temp.close()
    
    def _run(env_vars=None, stdin_data=None):
        env = os.environ.copy()
        env["CODESPACES"] = "true"
        env["COCHEM_CALCULATION_OS"] = "macos"
        repo_root = str(pathlib.Path(__file__).parent.parent.resolve())
        env["PYTHONPATH"] = repo_root
        if env_vars:
            env.update(env_vars)
        else:
            if "GEMINI_API_KEY" in env:
                del env["GEMINI_API_KEY"]
                
        cmd = ["python", path]
        try:
            input_bytes = stdin_data.encode("utf-8") if stdin_data is not None else None
            result = subprocess.run(
                cmd,
                env=env,
                input=input_bytes if stdin_data is not None else b"",
                capture_output=True,
                timeout=15,
                check=True
            )
            # using .decode("utf-8") to safely handle output
            return result.stdout.decode("utf-8", errors="replace"), result.stderr.decode("utf-8", errors="replace")
        except subprocess.CalledProcessError as e:
            return e.stdout.decode("utf-8", errors="replace"), e.stderr.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            return stdout, stderr + f"\nTimeout expired after {e.timeout}s"
            
    yield _run
    
    os.remove(path)

def test_oauth_env_key(run_script):
    logger.info("Testing execution path: Env key")
    stdout, stderr = run_script(env_vars={"GEMINI_API_KEY": "neutral_token_123"}, stdin_data="should_not_read_this\n")
    assert "TOKEN_ACQUIRED:neutral_token_123" in stdout, f"Stdout:\n{stdout}\nStderr:\n{stderr}"

def test_oauth_interactive_token(run_script):
    logger.info("Testing execution path: Interactive token")
    stdout, stderr = run_script(env_vars={}, stdin_data="neutral_token_interactive\n")
    assert "TOKEN_ACQUIRED:neutral_token_interactive" in stdout, f"Stdout:\n{stdout}\nStderr:\n{stderr}"

def test_oauth_interactive_empty(run_script):
    logger.info("Testing execution path: Interactive empty")
    stdout, stderr = run_script(env_vars={}, stdin_data="\n")
    assert "ERROR:ValueError:[MISSING DATA] Token cannot be empty. No invalid tokens allowed." in stdout, f"Stdout:\n{stdout}\nStderr:\n{stderr}"

def test_oauth_interactive_eof(run_script):
    logger.info("Testing execution path: Interactive EOF")
    stdout, stderr = run_script(env_vars={}, stdin_data="")
    assert "ERROR:RuntimeError:[HARD_ABORT: MISSING DATA] No interactive stdin available for OAuth flow and GEMINI_API_KEY not set." in stdout, f"Stdout:\n{stdout}\nStderr:\n{stderr}"
