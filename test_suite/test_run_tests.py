"""Master test suite execution script pytest test suite.

Validates:
- Direct and module execution of test_suite.run_tests.
- Preflight environment check execution and response structures.
- Pydantic schema validation for TestResult and PreflightCheckResult.
- Robust error handling for non-existent directories and invalid binaries.
- Strict LF line endings and typing compliance.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_suite.run_tests import (
    PreflightCheckResult,
    TestResult,
    cleanup_zombie_processes,
    run_all_preflight_checks,
)


@pytest.fixture
def target_file_path() -> Path:
    """Return absolute path to run_tests.py."""
    return Path(__file__).resolve().parent / "run_tests.py"


def test_run_tests_file_integrity_and_lf_endings(target_file_path: Path) -> None:
    """Validate that run_tests.py uses UTF-8 encoding and strictly LF line endings."""
    raw_bytes = target_file_path.read_bytes()
    assert b"\r\n" not in raw_bytes, "CRLF line endings detected in run_tests.py!"
    content = raw_bytes.decode("utf-8")
    assert "run_all_preflight_checks" in content
    assert "PreflightCheckResult" in content
    assert "TestResult" in content


def test_test_result_model_validation() -> None:
    """Validate TestResult Pydantic schema serialization and attributes."""
    res_pass = TestResult(status=True, message="All checks passed successfully.")
    assert res_pass.status is True
    assert res_pass.message == "All checks passed successfully."
    dumped = res_pass.model_dump()
    assert dumped["status"] is True
    assert dumped["message"] == "All checks passed successfully."

    res_fail = TestResult(
        status=False,
        message="Check failed.",
    )
    assert res_fail.status is False
    assert res_fail.message == "Check failed."
    dumped_fail = res_fail.model_dump()
    assert dumped_fail["status"] is False
    assert dumped_fail["message"] == "Check failed."


def test_preflight_check_result_serialization() -> None:
    """Validate PreflightCheckResult Pydantic schema and JSON export."""
    res = PreflightCheckResult(
        silo=TestResult(status=True, message="Silo OK"),
        artifacts=TestResult(status=True, message="Artifacts OK"),
        modules=TestResult(status=True, message="Modules OK"),
        orca_single=TestResult(status=True, message="ORCA single OK"),
        orca_mpi=TestResult(status=True, message="ORCA MPI OK"),
    )
    assert res.silo.status is True
    assert res.artifacts.status is True
    assert res.modules.status is True
    assert res.orca_single.status is True
    assert res.orca_mpi.status is True

    json_str = res.model_dump_json(indent=2)
    assert "Silo OK" in json_str
    assert "Artifacts OK" in json_str
    assert "Modules OK" in json_str


def test_cleanup_zombie_processes_execution() -> None:
    """Validate that cleanup_zombie_processes runs cleanly without throwing unhandled exceptions."""
    cleanup_zombie_processes()


def test_run_all_preflight_checks_live() -> None:
    """Validate running preflight checks against the active physical environment."""
    result = run_all_preflight_checks()
    assert isinstance(result, PreflightCheckResult)
    assert isinstance(result.silo, TestResult)
    assert isinstance(result.artifacts, TestResult)
    assert isinstance(result.modules, TestResult)
    assert isinstance(result.orca_single, TestResult)
    assert isinstance(result.orca_mpi, TestResult)
    assert isinstance(result.silo.status, bool)
    assert isinstance(result.artifacts.status, bool)
    assert isinstance(result.modules.status, bool)
    assert isinstance(result.orca_single.status, bool)
    assert isinstance(result.orca_mpi.status, bool)


def test_run_all_preflight_checks_custom_valid_paths(tmp_path: Path) -> None:
    """Validate running preflight checks with custom temporary artifact and module directories."""
    custom_art = tmp_path / "custom_artifacts"
    custom_art.mkdir(parents=True, exist_ok=True)

    custom_mod = tmp_path / "custom_modules"
    custom_mod.mkdir(parents=True, exist_ok=True)
    for mod in ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]:
        (custom_mod / mod).mkdir(parents=True, exist_ok=True)

    result = run_all_preflight_checks(artifact_dir=custom_art, module_dir=custom_mod)
    assert result.artifacts.status is True
    assert f"CoChem_Artifacts directory found at {custom_art}" in result.artifacts.message
    assert result.modules.status is True
    assert "All required modules found" in result.modules.message


def test_run_all_preflight_checks_missing_module_dir(tmp_path: Path) -> None:
    """Validate preflight check handling when the module directory is non-existent."""
    non_existent_mod = tmp_path / "non_existent_modules_dir"
    result = run_all_preflight_checks(module_dir=non_existent_mod)
    assert result.modules.status is False
    assert "Error: Missing modules" in result.modules.message


def test_run_all_preflight_checks_invalid_orca_and_mpi_paths() -> None:
    """Validate that invalid ORCA and MPI binary paths fail gracefully with clear status messages."""
    result = run_all_preflight_checks(
        orca_path="non_existent_orca_binary_path_xyz",
        mpi_path="non_existent_mpi_binary_path_xyz",
    )
    assert result.orca_single.status is False
    assert result.orca_mpi.status is False


def test_direct_script_subprocess_execution() -> None:
    """Validate direct CLI execution of run_tests.py via subprocess."""
    script_path = Path(__file__).resolve().parent / "run_tests.py"
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
        check=True,
    )
    assert result.returncode == 0
    combined_output = result.stdout + result.stderr
    assert "Preflight Results:" in combined_output
    assert "silo" in combined_output
    assert "artifacts" in combined_output
    assert "modules" in combined_output


def test_module_execution_via_python_m() -> None:
    """Validate module execution of test_suite.run_tests via python -m."""
    script_path = Path(__file__).resolve().parent / "run_tests.py"
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)
    result = subprocess.run(
        [sys.executable, "-m", "test_suite.run_tests"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
        check=True,
    )
    assert result.returncode == 0
    combined_output = result.stdout + result.stderr
    assert "Preflight Results:" in combined_output
    assert "silo" in combined_output
    assert "artifacts" in combined_output
    assert "modules" in combined_output
