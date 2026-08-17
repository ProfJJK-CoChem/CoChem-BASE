import logging
import os
import subprocess
from pathlib import Path

import pytest

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

@pytest.fixture
def base_env():
    env = os.environ.copy()
    project_root = os.getenv("COCHEM_PROJECT_ROOT", str(Path.home() / "CoChem-BASE"))
    env["PYTHONPATH"] = project_root
    return env

@pytest.fixture(params=[
    "COCHEM_ARTIFACT_DIR_1",
    "COCHEM_ARTIFACT_DIR_2"
])
def artifact_dir(request):
    default_path = Path.home() / ("CoChem_Artifacts_1" if "1" in request.param else "CoChem_Artifacts_2")
    return os.getenv(request.param, str(default_path))

def test_keep_previous_setup(tmp_path, base_env, artifact_dir):
    """
    Validates the existing silo environment dynamically without hardcoded paths.
    Executes tests against real binaries and wraps subprocesses safely.
    """
    silo_base_dir = Path(os.getenv("COCHEM_SILO_DIR", str(Path("D:/__CoChem") / ".agent_artifacts" / "Silos" / "cochem_base_silo")))
    silo_python = silo_base_dir / ("python.exe" if os.name == "nt" else "bin/python")

    if not silo_python.exists():
        pytest.fail(f"ERR_MISSING_BIN: Real cochem_base_silo python binary is missing at {silo_python}!")

    script = tmp_path / "validate.py"
    script.write_text(
        "import sys\n"
        "from test_suite.test_environment import check_cochem_base_silo, check_artifacts_dir\n"
        "s_ok, s_msg = check_cochem_base_silo()\n"
        "a_ok, a_msg = check_artifacts_dir()\n"
        "print('Silo Msg:', s_msg)\n"
        "print('Art Msg:', a_msg)\n"
        "if not s_ok:\n"
        "    sys.exit(1)\n"
        "if not a_ok:\n"
        "    sys.exit(2)\n"
        "sys.exit(0)\n",
        encoding="utf-8"
    )

    base_env["COCHEM_ARTIFACT_DIR"] = artifact_dir

    try:
        result = subprocess.run(
            [str(silo_python), str(script)],
            env=base_env,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        logging.info("Validation successful. Output: %s", result.stdout)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Validation failed with code {e.returncode}. Output: {e.stdout}\nStderr: {e.stderr}")
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"Validation timed out after {e.timeout}s.")
