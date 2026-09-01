"""Module Installation and Preflight Verification Suite for CoChem.

Provides runtime preflight checks for required CoChem repositories/modules
(CoChem-BASE, CoChem-TOPOS, CoChem-TORQ) as well as a comprehensive pytest
suite to validate module detection, directory resolution, edge cases,
and CLI/module execution.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cochem_base.config_loader import get_modules_dir, resolve_mapped_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-TestModules")


def check_modules_installed(base_path: str | Path | None = None) -> tuple[bool, str]:
    """Checks if the required modules are present in the modules directory."""
    modules_dir: Path = resolve_mapped_path(base_path, get_modules_dir()) if base_path else get_modules_dir()

    required_modules: list[str] = ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]
    missing: list[str] = []
    found: list[str] = []

    for mod in required_modules:
        mod_path: Path = modules_dir / mod
        if mod_path.exists() and mod_path.is_dir():
            found.append(mod)
        else:
            missing.append(mod)

    if missing:
        return False, f"Error: Missing modules in {modules_dir}: {', '.join(missing)}"
    return True, f"Success: All required modules found in {modules_dir}."


# ==============================================================================
# Pytest Test Cases for Module Installation & Preflight Verification
# ==============================================================================


def test_check_modules_installed_return_contract() -> None:
    """Validate that check_modules_installed returns a (bool, str) tuple with non-empty message."""
    ok, msg = check_modules_installed()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_check_modules_installed_default_resolution() -> None:
    """Validate check_modules_installed with default path resolution against the active environment."""
    ok, msg = check_modules_installed()
    modules_dir = get_modules_dir()
    if ok:
        assert f"Success: All required modules found in {modules_dir}." in msg
    else:
        assert f"Error: Missing modules in {modules_dir}:" in msg


def test_check_modules_installed_valid_custom_path(tmp_path: Path) -> None:
    """Validate check_modules_installed when all required modules exist in a directory."""
    for mod in ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]:
        (tmp_path / mod).mkdir(parents=True, exist_ok=True)

    ok, msg = check_modules_installed(tmp_path)
    assert ok is True
    assert msg == f"Success: All required modules found in {tmp_path.resolve()}."


def test_check_modules_installed_missing_modules(tmp_path: Path) -> None:
    """Validate check_modules_installed correctly detects and reports missing modules."""
    (tmp_path / "CoChem-BASE").mkdir(parents=True, exist_ok=True)

    ok, msg = check_modules_installed(tmp_path)
    assert ok is False
    assert f"Error: Missing modules in {tmp_path.resolve()}: CoChem-TOPOS, CoChem-TORQ" == msg


def test_check_modules_installed_all_missing(tmp_path: Path) -> None:
    """Validate check_modules_installed when no required modules exist."""
    ok, msg = check_modules_installed(tmp_path)
    assert ok is False
    assert f"Error: Missing modules in {tmp_path.resolve()}: CoChem-BASE, CoChem-TOPOS, CoChem-TORQ" == msg


def test_check_modules_installed_file_target_not_dir(tmp_path: Path) -> None:
    """Validate check_modules_installed requires modules to be directories, not plain files."""
    (tmp_path / "CoChem-BASE").write_text("dummy", encoding="utf-8")
    (tmp_path / "CoChem-TOPOS").mkdir(parents=True, exist_ok=True)
    (tmp_path / "CoChem-TORQ").mkdir(parents=True, exist_ok=True)

    ok, msg = check_modules_installed(tmp_path)
    assert ok is False
    assert "CoChem-BASE" in msg


def test_check_modules_installed_str_input_handling(tmp_path: Path) -> None:
    """Validate check_modules_installed properly parses string input paths."""
    for mod in ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]:
        (tmp_path / mod).mkdir(parents=True, exist_ok=True)

    ok, msg = check_modules_installed(str(tmp_path))
    assert ok is True
    assert str(tmp_path.resolve()) in msg


def test_check_modules_installed_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate check_modules_installed respects COCHEM_MODULE_DIR environment variable."""
    for mod in ["CoChem-BASE", "CoChem-TOPOS", "CoChem-TORQ"]:
        (tmp_path / mod).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_MODULE_DIR", str(tmp_path))

    ok, msg = check_modules_installed()
    assert ok is True
    assert str(tmp_path.resolve()) in msg


def test_test_modules_direct_script_execution() -> None:
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
    assert result.returncode in (0, 1)
    combined_output = result.stdout + result.stderr
    assert ("Success: All required modules found" in combined_output) or ("Error: Missing modules" in combined_output)


def test_test_modules_module_execution() -> None:
    """Validate module execution via python -m test_suite.test_modules."""
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [sys.executable, "-m", "test_suite.test_modules"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode in (0, 1)
    combined_output = result.stdout + result.stderr
    assert ("Success: All required modules found" in combined_output) or ("Error: Missing modules" in combined_output)


def test_test_modules_file_encoding_and_lf() -> None:
    """Validate UTF-8 encoding and strictly LF line endings in test_modules.py."""
    target_file = Path(__file__).resolve()
    raw_bytes = target_file.read_bytes()
    assert b"\r\n" not in raw_bytes, "CRLF line endings detected in test_modules.py!"
    content = raw_bytes.decode("utf-8")
    assert "check_modules_installed" in content


if __name__ == "__main__":
    success, message = check_modules_installed()
    if not success:
        logger.error(message)
        sys.exit(1)

    logger.info(message)

