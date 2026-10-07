"""Exercise actual interpreters, package discovery and pip failure boundaries."""
from pathlib import Path
import os
import subprocess
import sys
import venv

from scripts import bootstrap_environment


def _isolated_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(PIP_NO_INDEX="1", PIP_NO_CACHE_DIR="1", PIP_DISABLE_PIP_VERSION_CHECK="1",
                       PYTHONPATH=str(bootstrap_environment.REPO_ROOT))
    return environment


def test_complete_environment_does_not_reinstall_dependencies(tmp_path: Path) -> None:
    # These are the real dashboard dependencies, not a substituted readiness flag.
    assert bootstrap_environment._environment_ready(Path(sys.executable))
    command = (
        "from pathlib import Path; import sys; "
        "from scripts.bootstrap_environment import ensure_dependencies; "
        "ensure_dependencies(Path(sys.executable)); print('environment-ready')"
    )
    completed = subprocess.run([sys.executable, "-c", command], cwd=tmp_path,
                               env=_isolated_environment(), capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Provisioning" not in completed.stdout
    assert completed.stdout.strip() == "environment-ready"


def test_incomplete_environment_attempts_install_and_propagates_real_pip_failure(tmp_path: Path) -> None:
    directory = tmp_path / "incomplete-environment"
    venv.EnvBuilder(with_pip=True).create(directory)
    python = bootstrap_environment._python_in(directory)
    assert not bootstrap_environment._environment_ready(python)
    # No index or wheel cache is available to this new interpreter. The actual
    # pip install must fail, and bootstrap must never certify that environment.
    command = (
        "from pathlib import Path; import sys; "
        "from scripts.bootstrap_environment import ensure_dependencies; "
        "ensure_dependencies(Path(sys.argv[1]))"
    )
    completed = subprocess.run([sys.executable, "-c", command, str(python)], cwd=tmp_path,
                               env=_isolated_environment(), capture_output=True, text=True, timeout=60)
    assert completed.returncode != 0
    assert "Provisioning CoChem UI dependencies" in completed.stdout
    assert "CalledProcessError" in completed.stderr
    assert not bootstrap_environment._environment_ready(python)


def test_current_environment_preserves_its_actual_virtualenv_executable(tmp_path: Path) -> None:
    command = (
        "import sys; from pathlib import Path; "
        "from scripts.bootstrap_environment import ensure_current_environment; "
        "result = ensure_current_environment(); "
        "assert result == Path(sys.executable).absolute(); print(result)"
    )
    completed = subprocess.run([sys.executable, "-c", command], cwd=tmp_path,
                               env=_isolated_environment(), capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == str(Path(sys.executable).absolute())
