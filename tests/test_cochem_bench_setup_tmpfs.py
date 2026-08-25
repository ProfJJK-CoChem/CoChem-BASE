"""Unit tests for CoChem-BENCH Transient RAM-Disk (tmpfs) Setup Script (setup_tmpfs.sh).

Task: CoChem-BENCH Task 1 - Master Repository Map, Bipartite Topology & Air-Gap Enforcement.
Validates:
- File existence at repository root as a regular file.
- UTF-8 encoding with no BOM and strict Unix LF line endings.
- Strict bash shebang and error safety configuration (set -euo pipefail).
- Dynamic mount point binding via eval MOUNT_POINT="$COCHEM_ARTIFACTS_DIR/Scratch_RAM".
- Strict failure when $COCHEM_ARTIFACTS_DIR is unset or empty.
- Dynamic Air-Gap enforcement: Zero hardcoded absolute paths (no /tmp/ramdisk, /dev/shm, etc.).
- Absence of unverified markers (FIXME, UNIMPLEMENTED, TEMP_HACK, etc.).
- Strict Zero-Mock compliance verified via AST analysis.
- Physical execution tests via subprocess verifying exit codes, directory creation, idempotency, and stdout logs.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_TMPFS_PATH = REPO_ROOT / "setup_tmpfs.sh"

REQUIRED_EVAL_STATEMENT = 'eval MOUNT_POINT="$COCHEM_ARTIFACTS_DIR/Scratch_RAM"'

FORBIDDEN_HARDCODED_PATHS: List[str] = [
    "/tmp/ramdisk",
    "/dev/shm",
    "/home/",
    "C:\\",
    "D:\\",
    "c:\\",
    "d:\\",
]

FORBIDDEN_PLACEHOLDER_MARKERS: List[str] = [
    "FIXME",
    "UNIMPLEMENTED",
    "TEMP_HACK",
    "BROKEN_MARKER",
    "DUMMY",
    "MOCK",
    "STUB",
]


def resolve_bash_executable() -> str:
    """Resolve an available Bash executable across Windows, WSL, and POSIX platforms."""
    # Check standard Git for Windows bash locations if on Windows
    git_bash_candidates = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
    ]
    for candidate in git_bash_candidates:
        if candidate.exists():
            return str(candidate)

    # Check PATH for bash or sh
    system_bash = shutil.which("bash") or shutil.which("sh")
    if system_bash:
        return system_bash

    return "bash"


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the CoChem repository root."""
    return REPO_ROOT


@pytest.fixture
def setup_tmpfs_file() -> Path:
    """Return the absolute path to setup_tmpfs.sh and assert existence."""
    assert SETUP_TMPFS_PATH.exists(), f"setup_tmpfs.sh does not exist at {SETUP_TMPFS_PATH}"
    return SETUP_TMPFS_PATH


@pytest.fixture
def bash_cmd() -> str:
    """Return the resolved bash executable path."""
    return resolve_bash_executable()


def test_setup_tmpfs_file_exists(repo_root: Path) -> None:
    """Validate that setup_tmpfs.sh exists in the repository root as a regular file."""
    path = repo_root / "setup_tmpfs.sh"
    assert path.exists(), f"setup_tmpfs.sh missing from repository root: {path}"
    assert path.is_file(), f"setup_tmpfs.sh at {path} must be a regular file"


def test_setup_tmpfs_encoding_and_lf_endings(setup_tmpfs_file: Path) -> None:
    """Validate that setup_tmpfs.sh has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = setup_tmpfs_file.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "setup_tmpfs.sh contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "setup_tmpfs.sh contains Windows CRLF line endings; must use Unix LF"
    assert b"\r" not in raw_bytes, "setup_tmpfs.sh contains Mac/legacy CR line endings; must use Unix LF"
    assert b"\n" in raw_bytes, "setup_tmpfs.sh missing Unix LF line endings"
    assert len(raw_bytes.strip()) > 0, "setup_tmpfs.sh must not be empty"


def test_setup_tmpfs_shebang_and_strict_mode(setup_tmpfs_file: Path) -> None:
    """Validate that setup_tmpfs.sh begins with a valid bash shebang and enables strict error handling."""
    content = setup_tmpfs_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    assert len(lines) > 0, "setup_tmpfs.sh is empty"
    first_line = lines[0].strip()
    assert first_line.startswith("#!"), "setup_tmpfs.sh must start with a shebang"
    assert "bash" in first_line or "sh" in first_line, "Shebang must invoke bash or sh"

    assert "set -e" in content or "set -euo pipefail" in content, (
        "setup_tmpfs.sh must configure strict bash error handling (e.g., set -euo pipefail)"
    )


def test_setup_tmpfs_eval_mount_point_binding(setup_tmpfs_file: Path) -> None:
    """Validate that MOUNT_POINT is strictly bound using the required eval statement."""
    content = setup_tmpfs_file.read_text(encoding="utf-8")
    assert REQUIRED_EVAL_STATEMENT in content, (
        f"Missing required mount point binding: '{REQUIRED_EVAL_STATEMENT}'"
    )


def test_setup_tmpfs_no_forbidden_hardcoded_paths(setup_tmpfs_file: Path) -> None:
    """Validate that setup_tmpfs.sh contains zero hardcoded absolute paths."""
    content = setup_tmpfs_file.read_text(encoding="utf-8")
    # Exclude comment lines from inspection
    non_comment_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    code_body = "\n".join(non_comment_lines)

    for forbidden in FORBIDDEN_HARDCODED_PATHS:
        assert forbidden not in code_body, (
            f"setup_tmpfs.sh must not contain hardcoded path '{forbidden}' in active code"
        )


def test_setup_tmpfs_no_unverified_placeholder_markers(setup_tmpfs_file: Path) -> None:
    """Validate that setup_tmpfs.sh contains no unverified placeholder tokens or stubs."""
    content = setup_tmpfs_file.read_text(encoding="utf-8").upper()
    for marker in FORBIDDEN_PLACEHOLDER_MARKERS:
        assert marker not in content, (
            f"setup_tmpfs.sh must not contain forbidden placeholder marker '{marker}'"
        )


def test_zero_mock_compliance_in_test_suite() -> None:
    """Verify that test implementation strictly adheres to Zero-Mock rules via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), f"Forbidden mock import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert "mock" not in module.lower(), f"Forbidden mock import: {module}"


def test_setup_tmpfs_fails_when_cochem_artifacts_dir_unset(
    setup_tmpfs_file: Path, bash_cmd: str
) -> None:
    """Validate that setup_tmpfs.sh fails with non-zero exit code when COCHEM_ARTIFACTS_DIR is unset."""
    env = os.environ.copy()
    env.pop("COCHEM_ARTIFACTS_DIR", None)

    script_path_str = str(setup_tmpfs_file.as_posix()) if os.name == "nt" else str(setup_tmpfs_file)
    result = subprocess.run(
        [bash_cmd, script_path_str],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        f"setup_tmpfs.sh must fail when COCHEM_ARTIFACTS_DIR is unset. "
        f"Exit code: {result.returncode}, Stdout: {result.stdout}, Stderr: {result.stderr}"
    )
    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    assert "cochem_artifacts_dir" in combined_output or "not set" in combined_output, (
        "Script output must report missing COCHEM_ARTIFACTS_DIR"
    )


def test_setup_tmpfs_fails_when_cochem_artifacts_dir_empty(
    setup_tmpfs_file: Path, bash_cmd: str
) -> None:
    """Validate that setup_tmpfs.sh fails with non-zero exit code when COCHEM_ARTIFACTS_DIR is empty string."""
    env = os.environ.copy()
    env["COCHEM_ARTIFACTS_DIR"] = ""

    script_path_str = str(setup_tmpfs_file.as_posix()) if os.name == "nt" else str(setup_tmpfs_file)
    result = subprocess.run(
        [bash_cmd, script_path_str],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        f"setup_tmpfs.sh must fail when COCHEM_ARTIFACTS_DIR is empty. "
        f"Exit code: {result.returncode}, Stdout: {result.stdout}, Stderr: {result.stderr}"
    )


def test_setup_tmpfs_succeeds_and_creates_scratch_ram(
    setup_tmpfs_file: Path, bash_cmd: str, tmp_path: Path
) -> None:
    """Validate that setup_tmpfs.sh succeeds and creates Scratch_RAM directory when COCHEM_ARTIFACTS_DIR is set."""
    artifacts_dir = tmp_path / "artifacts"
    expected_scratch_ram = artifacts_dir / "Scratch_RAM"

    assert not expected_scratch_ram.exists(), "Scratch_RAM directory should not exist prior to script execution"

    env = os.environ.copy()
    env["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir.as_posix())

    script_path_str = str(setup_tmpfs_file.as_posix()) if os.name == "nt" else str(setup_tmpfs_file)
    result = subprocess.run(
        [bash_cmd, script_path_str],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"setup_tmpfs.sh failed unexpectedly with code {result.returncode}.\n"
        f"Stdout: {result.stdout}\nStderr: {result.stderr}"
    )

    assert expected_scratch_ram.exists(), (
        f"Expected Scratch_RAM directory at {expected_scratch_ram} was not created."
    )
    assert expected_scratch_ram.is_dir(), (
        f"Scratch_RAM path {expected_scratch_ram} must be a directory."
    )
    assert "[SUCCESS]" in result.stdout, (
        "Script stdout must contain [SUCCESS] status indication."
    )


def test_setup_tmpfs_handles_nested_target_directory(
    setup_tmpfs_file: Path, bash_cmd: str, tmp_path: Path
) -> None:
    """Validate that setup_tmpfs.sh creates multi-level nested directories via mkdir -p."""
    deep_artifacts_dir = tmp_path / "deep" / "nested" / "workspace" / "tier"
    expected_scratch_ram = deep_artifacts_dir / "Scratch_RAM"

    assert not deep_artifacts_dir.exists(), "Parent directories should not exist prior to test"

    env = os.environ.copy()
    env["COCHEM_ARTIFACTS_DIR"] = str(deep_artifacts_dir.as_posix())

    script_path_str = str(setup_tmpfs_file.as_posix()) if os.name == "nt" else str(setup_tmpfs_file)
    result = subprocess.run(
        [bash_cmd, script_path_str],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"Nested setup_tmpfs.sh failed with exit code {result.returncode}.\n"
        f"Stdout: {result.stdout}\nStderr: {result.stderr}"
    )
    assert expected_scratch_ram.exists() and expected_scratch_ram.is_dir(), (
        f"Nested Scratch_RAM directory was not created at {expected_scratch_ram}"
    )


def test_setup_tmpfs_idempotent_execution(
    setup_tmpfs_file: Path, bash_cmd: str, tmp_path: Path
) -> None:
    """Validate that running setup_tmpfs.sh multiple times consecutively succeeds idempotently."""
    artifacts_dir = tmp_path / "idempotent_artifacts"
    expected_scratch_ram = artifacts_dir / "Scratch_RAM"

    env = os.environ.copy()
    env["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir.as_posix())
    script_path_str = str(setup_tmpfs_file.as_posix()) if os.name == "nt" else str(setup_tmpfs_file)

    # First execution
    res1 = subprocess.run([bash_cmd, script_path_str], env=env, capture_output=True, text=True)
    assert res1.returncode == 0, f"First execution failed: {res1.stderr}"
    assert expected_scratch_ram.exists()

    # Drop a canary file inside Scratch_RAM to test that subsequent execution does not destroy existing contents
    canary_file = expected_scratch_ram / "canary.txt"
    canary_file.write_text("persisted data", encoding="utf-8")

    # Second execution
    res2 = subprocess.run([bash_cmd, script_path_str], env=env, capture_output=True, text=True)
    assert res2.returncode == 0, f"Second execution failed: {res2.stderr}"
    assert expected_scratch_ram.exists()
    assert canary_file.exists(), "Canary file inside Scratch_RAM should persist across runs in filesystem fallback mode"
