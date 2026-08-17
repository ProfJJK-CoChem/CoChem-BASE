import os
import sys
import subprocess
import tempfile
import atexit
import psutil
import pytest

_temp_scripts = []

def cleanup_zombies():
    """Sweep for zombie subprocesses related to our temp scripts."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline') or []
            if any(script in cmdline for script in _temp_scripts):
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

atexit.register(cleanup_zombies)

@pytest.fixture(scope="module")
def daemon_script_path():
    script_content = """import os
import sys
from cochem_base.antigravity_daemon import daemon_instance

try:
    print(daemon_instance.google_oauth_flow())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)}")
    sys.exit(1)
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write(script_content)
        temp_path = f.name
    
    _temp_scripts.append(temp_path)
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.remove(temp_path)
        if temp_path in _temp_scripts:
            _temp_scripts.remove(temp_path)

@pytest.fixture
def base_env():
    env = os.environ.copy()
    env["CODESPACES"] = "true"
    env["COCHEM_CALCULATION_OS"] = "github-actions"
    # Ensure GEMINI_API_KEY is not in base_env by default
    env.pop("GEMINI_API_KEY", None)
    
    # We must also ensure PYTHONPATH includes the package root
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{pkg_root}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = pkg_root
    return env

def test_oauth_env_key(daemon_script_path, base_env):
    env = base_env.copy()
    env["GEMINI_API_KEY"] = "ENV_MOCK_API_KEY"
    
    try:
        result = subprocess.run(
            [sys.executable, daemon_script_path],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=15
        )
        assert "ENV_MOCK_API_KEY" in result.stdout
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Subprocess timed out: {e}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Subprocess failed with code {e.returncode}: {e.stdout} {e.stderr}")

def test_oauth_interactive_token(daemon_script_path, base_env):
    try:
        result = subprocess.run(
            [sys.executable, daemon_script_path],
            env=base_env,
            input="INTERACTIVE_TOKEN_123\n",
            capture_output=True,
            text=True,
            check=True,
            timeout=15
        )
        assert "INTERACTIVE_TOKEN_123" in result.stdout
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Subprocess timed out: {e}")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Subprocess failed with code {e.returncode}: {e.stdout} {e.stderr}")

def test_oauth_interactive_empty(daemon_script_path, base_env):
    try:
        subprocess.run(
            [sys.executable, daemon_script_path],
            env=base_env,
            input="\n",
            capture_output=True,
            text=True,
            check=True,
            timeout=15
        )
        pytest.fail("Expected subprocess to fail on empty token.")
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Subprocess timed out: {e}")
    except subprocess.CalledProcessError as e:
        assert e.returncode != 0
        output = e.stdout + e.stderr
        assert "ERROR: ValueError:" in output
        assert "[MISSING DATA] Token cannot be empty" in output

def test_oauth_interactive_eof(daemon_script_path, base_env):
    try:
        subprocess.run(
            [sys.executable, daemon_script_path],
            env=base_env,
            input="", # EOF
            capture_output=True,
            text=True,
            check=True,
            timeout=15
        )
        pytest.fail("Expected subprocess to fail on EOF.")
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Subprocess timed out: {e}")
    except subprocess.CalledProcessError as e:
        assert e.returncode != 0
        output = e.stdout + e.stderr
        assert "ERROR: RuntimeError:" in output
        assert "[HARD_ABORT: MISSING DATA]" in output

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
