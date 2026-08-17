import os
import sys
import subprocess
import tempfile
import psutil
import atexit
import pytest
import pathlib

def sweep_zombie_processes():
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                child.terminate()
                child.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

atexit.register(sweep_zombie_processes)

@pytest.fixture(scope="module")
def setup_env():
    env = os.environ.copy()
    env["CODESPACES"] = "true"
    env["COCHEM_CALCULATION_OS"] = "wsl"
    env["PYTHONPATH"] = str(pathlib.Path(__file__).resolve().parent.parent)
    return env

def test_antigravity_ask_codespaces_wsl(setup_env):
    script_content = """import sys
import os
from cochem_base.antigravity_daemon import daemon_instance

def main():
    # Verify environment values
    assert os.environ.get("CODESPACES") == "true"
    assert os.environ.get("COCHEM_CALCULATION_OS") == "wsl"

    # Test token stripping directly
    stripped = daemon_instance._guardrail_strip('Optimize this: O 0.00000 0.00000 0.00000')
    print(f"STRIPPED: {stripped}")
    sys.stdout.flush()

    try:
        # Inject token
        daemon_instance.google_oauth_flow()
        # Query API natively - should fail because token is generic
        res = daemon_instance.query('Hello')
        print("RESULT:", res)
    except Exception as e:
        print(f"EXCEPTION_CAUGHT: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
        f.write(script_content)
        script_path = f.name

    try:
        try:
            subprocess.run(
                [sys.executable, script_path],
                env=setup_env,
                input="GENERIC_NEUTRAL_TOKEN\n",
                capture_output=True,
                text=True,
                timeout=15,
                check=True
            )
            pytest.fail("Expected subprocess to fail with API Error due to generic neutral token")
        except subprocess.TimeoutExpired:
            pytest.fail("Subprocess timed out after 15 seconds.")
        except subprocess.CalledProcessError as e:
            stdout = e.stdout
            
            # Verify stripping happened
            assert "STRIPPED: Optimize this: O <XYZ_STRIPPED>" in stdout
            
            # Verify proper exception string is caught
            assert "EXCEPTION_CAUGHT:" in stdout
            assert "API Error:" in stdout
            
    finally:
        try:
            os.unlink(script_path)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    pytest.main(["-v", __file__])
