"""Environment and Preflight Verification Suite for CoChem.

Provides runtime preflight checks for the conda environment and artifact directories,
as well as a comprehensive pytest suite to validate environment detection, directory
resolution, edge cases, and CLI/module execution.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path for direct execution and isolated test runs
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from cochem_base.config_loader import get_artifact_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-TestEnvironment")


def check_cochem_base_silo() -> tuple[bool, str]:
    """Checks if the python execution environment is cochem_base_silo."""
    env_name = os.environ.get("CONDA_DEFAULT_ENV", "")
    if "cochem_base_silo" in env_name or "cochem_base_silo" in sys.executable:
        return True, "Success: Running within cochem_base_silo."
    return False, f"Warning: Not running within cochem_base_silo (current env: {env_name})."


def check_artifacts_dir(path: Path | str | None = None) -> tuple[bool, str]:
    """Checks if the CoChem_Artifacts directory exists."""
    resolved_path = Path(path) if path is not None else get_artifact_dir()

    if resolved_path.exists() and resolved_path.is_dir():
        return True, f"Success: CoChem_Artifacts directory found at {resolved_path}."
    return False, f"Error: CoChem_Artifacts directory missing at {resolved_path}."


# ==============================================================================
# Pytest Test Cases for Environment & Preflight Verification
# ==============================================================================


def test_check_cochem_base_silo_return_contract() -> None:
    """Validate that check_cochem_base_silo returns a (bool, str) tuple with non-empty message."""
    ok, msg = check_cochem_base_silo()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_check_cochem_base_silo_active_environment() -> None:
    """Validate check_cochem_base_silo evaluation against the active process runtime."""
    env_name = os.environ.get("CONDA_DEFAULT_ENV", "")
    ok, msg = check_cochem_base_silo()
    if "cochem_base_silo" in env_name or "cochem_base_silo" in sys.executable:
        assert ok is True
        assert "Success: Running within cochem_base_silo." in msg
    else:
        assert ok is False
        assert "Warning: Not running within cochem_base_silo" in msg


def test_check_cochem_base_silo_with_matching_conda_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that check_cochem_base_silo returns True when CONDA_DEFAULT_ENV is set."""
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "cochem_base_silo")
    ok, msg = check_cochem_base_silo()
    assert ok is True
    assert msg == "Success: Running within cochem_base_silo."


def test_check_cochem_base_silo_with_non_matching_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that check_cochem_base_silo handles non-matching conda environments."""
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "base")
    if "cochem_base_silo" not in sys.executable:
        ok, msg = check_cochem_base_silo()
        assert ok is False
        assert "Warning: Not running within cochem_base_silo (current env: base)." == msg


def test_check_artifacts_dir_default_resolution() -> None:
    """Validate check_artifacts_dir using default path resolution."""
    ok, msg = check_artifacts_dir()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    if ok:
        assert "Success: CoChem_Artifacts directory found at" in msg
    else:
        assert "Error: CoChem_Artifacts directory missing at" in msg


def test_check_artifacts_dir_valid_custom_path(tmp_path: Path) -> None:
    """Validate check_artifacts_dir with a real, existing physical directory."""
    valid_dir = tmp_path / "valid_artifacts"
    valid_dir.mkdir(parents=True, exist_ok=True)

    ok, msg = check_artifacts_dir(valid_dir)
    assert ok is True
    assert msg == f"Success: CoChem_Artifacts directory found at {valid_dir}."


def test_check_artifacts_dir_missing_custom_path(tmp_path: Path) -> None:
    """Validate check_artifacts_dir with a non-existent directory."""
    missing_dir = tmp_path / "missing_artifacts_directory"
    assert not missing_dir.exists()

    ok, msg = check_artifacts_dir(missing_dir)
    assert ok is False
    assert msg == f"Error: CoChem_Artifacts directory missing at {missing_dir}."


def test_check_artifacts_dir_file_target(tmp_path: Path) -> None:
    """Validate check_artifacts_dir returns False if path points to a file instead of a directory."""
    file_path = tmp_path / "not_a_directory.txt"
    file_path.write_text("dummy artifact file content", encoding="utf-8")
    assert file_path.is_file()

    ok, msg = check_artifacts_dir(file_path)
    assert ok is False
    assert msg == f"Error: CoChem_Artifacts directory missing at {file_path}."


def test_check_artifacts_dir_str_input_handling(tmp_path: Path) -> None:
    """Validate check_artifacts_dir properly parses str input paths."""
    str_dir = tmp_path / "str_artifacts"
    str_dir.mkdir(parents=True, exist_ok=True)

    ok, msg = check_artifacts_dir(str(str_dir))
    assert ok is True
    assert str(str_dir) in msg


def test_check_artifacts_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate check_artifacts_dir respects the COCHEM_ARTIFACT_DIR environment variable."""
    env_dir = tmp_path / "env_artifacts"
    env_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(env_dir))

    ok, msg = check_artifacts_dir()
    assert ok is True
    assert str(env_dir) in msg


def test_environment_direct_script_execution() -> None:
    """Validate direct CLI script execution via subprocess."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 0
    combined_output = result.stdout + result.stderr
    assert "cochem_base_silo" in combined_output
    assert "CoChem_Artifacts" in combined_output


def test_environment_module_execution() -> None:
    """Validate module execution via python -m test_suite.test_environment."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, "-m", "test_suite.test_environment"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 0
    combined_output = result.stdout + result.stderr
    assert "cochem_base_silo" in combined_output
    assert "CoChem_Artifacts" in combined_output


def test_test_environment_file_encoding_and_lf() -> None:
    """Validate UTF-8 encoding and strictly LF line endings in test_environment.py."""
    target_file = Path(__file__).resolve()
    raw_bytes = target_file.read_bytes()
    assert b"\r\n" not in raw_bytes, "CRLF line endings detected in test_environment.py!"
    content = raw_bytes.decode("utf-8")
    assert "check_cochem_base_silo" in content
    assert "check_artifacts_dir" in content


if __name__ == "__main__":
    logger.info(check_cochem_base_silo()[1])
    logger.info(check_artifacts_dir()[1])
