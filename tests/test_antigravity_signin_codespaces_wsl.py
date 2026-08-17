import os
import sys
import tempfile
import subprocess
import atexit
import logging
import pytest
import psutil

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def sweep_zombie_processes():
    logger.info("Sweeping zombie processes on exit.")
    try:
        current_process = psutil.Process(os.getpid())
        children = current_process.children(recursive=True)
        for child in children:
            try:
                logger.info("Terminating orphaned subprocess: %s", child.pid)
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

atexit.register(sweep_zombie_processes)

@pytest.fixture
def physical_shim():
    shim_content = """import os
import sys
import logging
from cochem_base.antigravity_daemon import daemon_instance

logging.basicConfig(level=logging.INFO)

assert os.environ.get('CODESPACES') == 'true', "Missing CODESPACES env var"
assert os.environ.get('COCHEM_CALCULATION_OS') == 'wsl', "Missing COCHEM_CALCULATION_OS env var"

token = daemon_instance.google_oauth_flow()
print(f"TOKEN_OUTPUT:{token}")
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix=".py", delete=False, encoding='utf-8') as tmp:
        tmp.write(shim_content)
        shim_path = tmp.name
        
    yield shim_path
    
    try:
        if os.path.exists(shim_path):
            os.remove(shim_path)
    except OSError:
        pass

def run_shim(shim_path: str, env_updates: dict, input_str: str = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if "GEMINI_API_KEY" in env:
        del env["GEMINI_API_KEY"]
        
    for k, v in env_updates.items():
        if v is None:
            if k in env:
                del env[k]
        else:
            env[k] = v
            
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = repo_root
            
    try:
        return subprocess.run(
            [sys.executable, shim_path],
            env=env,
            input=input_str,
            capture_output=True,
            text=True,
            timeout=15,
            check=True
        )
    except subprocess.TimeoutExpired as e:
        logger.error("Command timed out: %s", e)
        raise
    except subprocess.CalledProcessError as e:
        logger.error("Command failed with return code %s", e.returncode)
        raise

def test_signin_codespaces_wsl_env_key(physical_shim):
    """Path 1: env key"""
    env = {
        "CODESPACES": "true",
        "COCHEM_CALCULATION_OS": "wsl",
        "GEMINI_API_KEY": "NEUTRAL_TOKEN_ENV"
    }
    try:
        result = run_shim(physical_shim, env)
        assert "TOKEN_OUTPUT:NEUTRAL_TOKEN_ENV" in result.stdout
        logger.info("Env key path passed.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.fail(f"Subprocess failed unexpectedly: {e}")

def test_signin_codespaces_wsl_interactive_token(physical_shim):
    """Path 2: interactive token"""
    env = {
        "CODESPACES": "true",
        "COCHEM_CALCULATION_OS": "wsl"
    }
    try:
        result = run_shim(physical_shim, env, input_str="NEUTRAL_TOKEN_INTERACTIVE\n")
        assert "TOKEN_OUTPUT:NEUTRAL_TOKEN_INTERACTIVE" in result.stdout
        assert "Please authenticate via browser" in result.stderr
        logger.info("Interactive token path passed.")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.fail(f"Subprocess failed unexpectedly: {e}")

def test_signin_codespaces_wsl_interactive_empty(physical_shim):
    """Path 3: interactive empty"""
    env = {
        "CODESPACES": "true",
        "COCHEM_CALCULATION_OS": "wsl"
    }
    try:
        run_shim(physical_shim, env, input_str="\n")
        pytest.fail("Should have raised CalledProcessError for ValueError")
    except subprocess.CalledProcessError as e:
        assert e.returncode != 0
        assert "ValueError" in e.stderr
        assert "[MISSING DATA]" in e.stderr
        logger.info("Interactive empty path passed.")
    except subprocess.TimeoutExpired:
        pytest.fail("Subprocess timed out unexpectedly")

def test_signin_codespaces_wsl_interactive_eof(physical_shim):
    """Path 4: interactive EOF"""
    env = {
        "CODESPACES": "true",
        "COCHEM_CALCULATION_OS": "wsl"
    }
    try:
        run_shim(physical_shim, env, input_str="")
        pytest.fail("Should have raised CalledProcessError for RuntimeError (EOFError)")
    except subprocess.CalledProcessError as e:
        assert e.returncode != 0
        assert "RuntimeError" in e.stderr
        assert "[HARD_ABORT: MISSING DATA]" in e.stderr
        logger.info("Interactive EOF path passed.")
    except subprocess.TimeoutExpired:
        pytest.fail("Subprocess timed out unexpectedly")

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
