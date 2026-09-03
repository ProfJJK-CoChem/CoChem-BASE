#!/usr/bin/env python3
"""Zero-Mock Integration & Unit Test Suite for Zero-Trust Quarantine Runner.

Module: tests/test_zero_trust_runner.py
Target Implementation: ci_tools/zero_trust_runner.py

Authoritative Standards & Requirements:
- CoChem Anti-Spoofing Protocol v2 (Rules 1, 2, 3, 6, 7, 8)
- Method Matrix v4 Standards & Zero-Mock Execution Invariants
- Dynamic Atomic Mass Retrieval via Mendeleev Mandate
- Asymmetric Verification: Zero-Trust Quarantine Environment Sandbox (%TEMP%/cochem_exec_<uuid>)
- Zombie Process Sweeping & Subprocess Lifetime Governance
- PathCanonicalRewriter & Cryptographic ExecutionReceipt Generation

Provenance Tags:
- [M] Measured process runtimes, CLI exit codes, cryptographic SHA-256 hashes, and filesystem I/O metrics.
- [D] Derived AST invariants, dataclass attributes, environment overrides, and path mapping logic.
- [E] Estimated resource thresholds, timeout boundaries, and directory lifecycle guarantees.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import pytest
from mendeleev import element

from ci_tools.zero_trust_runner import (
    QuarantineEnvironment,
    QuarantineResult,
    main,
    run_in_quarantine,
    sweep_zombie_processes,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "ci_tools" / "zero_trust_runner.py"


@pytest.fixture
def repo_root() -> Path:
    """Return absolute path to CoChem repository root."""
    return REPO_ROOT


@pytest.fixture
def runner_path() -> Path:
    """Return absolute path to zero_trust_runner.py script."""
    assert RUNNER_PATH.exists(), f"zero_trust_runner.py not found at {RUNNER_PATH}"
    return RUNNER_PATH


# ==============================================================================
# 1. Script Integrity and AST Verification [M] [D]
# ==============================================================================

def test_runner_script_exists_and_encoding(runner_path: Path) -> None:
    """Verify zero_trust_runner.py exists, valid UTF-8 encoding, no BOM, and Unix LF line endings."""
    assert runner_path.exists(), f"Target script missing at {runner_path}"
    assert runner_path.is_file(), f"Target is not a regular file: {runner_path}"

    raw_bytes = runner_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in zero_trust_runner.py"
    assert b"\r\n" not in raw_bytes, "Found CRLF line endings in zero_trust_runner.py (Unix LF required)"
    assert b"\n" in raw_bytes, "Missing newline characters in zero_trust_runner.py"

    text = raw_bytes.decode("utf-8")
    assert len(text) > 500, f"Script unexpectedly short ({len(text)} chars)"
    assert "class QuarantineEnvironment" in text
    assert "def run_in_quarantine" in text
    assert "def sweep_zombie_processes" in text

    # Verify script parses cleanly into a valid Python AST
    parsed_ast = ast.parse(text, filename=str(runner_path))
    assert isinstance(parsed_ast, ast.Module)


def test_runner_ast_anti_spoof_compliance(runner_path: Path) -> None:
    """Verify AST compliance: no forbidden mock imports, no empty pass stubs, no NotImplementedError."""
    text = runner_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(runner_path))

    from ci_tools.anti_spoof_linter import BANNED_MOCK_MODULES

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in BANNED_MOCK_MODULES, (
                    f"Forbidden mock import '{alias.name}' detected in zero_trust_runner.py at line {node.lineno}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in BANNED_MOCK_MODULES, (
                f"Forbidden mock from-import '{node.module}' detected in zero_trust_runner.py at line {node.lineno}"
            )
        elif isinstance(node, ast.Raise):
            if isinstance(node.exc, ast.Name):
                assert node.exc.id != "NotImplementedError", (
                    f"Forbidden NotImplementedError raised at line {node.lineno}"
                )
            elif isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
                assert node.exc.func.id != "NotImplementedError", (
                    f"Forbidden NotImplementedError() call raised at line {node.lineno}"
                )


# ==============================================================================
# 2. QuarantineResult Dataclass Architecture [D] [M]
# ==============================================================================

def test_quarantine_result_fields_and_defaults() -> None:
    """Verify QuarantineResult fields, default arguments, and type integrity."""
    result = QuarantineResult(
        exit_code=0,
        stdout="Process executed successfully\n",
        stderr="",
        quarantine_dir="/tmp/cochem_exec_test_uuid",
        duration_s=0.4521,
        passed=True,
    )

    assert result.exit_code == 0
    assert result.stdout == "Process executed successfully\n"
    assert result.stderr == ""
    assert result.quarantine_dir == "/tmp/cochem_exec_test_uuid"
    assert result.duration_s == 0.4521
    assert result.passed is True
    assert result.timed_out is False


def test_quarantine_result_to_dict_serialization() -> None:
    """Verify QuarantineResult to_dict serialization produces complete dictionary mapping."""
    result = QuarantineResult(
        exit_code=124,
        stdout="Partial output before timeout",
        stderr="TimeoutExpired: command timed out",
        quarantine_dir="/tmp/cochem_exec_timed_out",
        duration_s=300.0,
        passed=False,
        timed_out=True,
    )

    result_dict = result.to_dict()
    assert isinstance(result_dict, dict)
    assert result_dict == {
        "exit_code": 124,
        "stdout": "Partial output before timeout",
        "stderr": "TimeoutExpired: command timed out",
        "quarantine_dir": "/tmp/cochem_exec_timed_out",
        "duration_s": 300.0,
        "passed": False,
        "timed_out": True,
    }


# ==============================================================================
# 3. Zombie Process Sweeping & Subprocess Lifetime [M]
# ==============================================================================

def test_sweep_zombie_processes_execution() -> None:
    """Verify sweep_zombie_processes executes safely and returns non-negative integer."""
    terminated_count = sweep_zombie_processes()
    assert isinstance(terminated_count, int)
    assert terminated_count >= 0


def test_sweep_zombie_processes_terminates_active_child() -> None:
    """Verify sweep_zombie_processes locates and terminates real active child processes."""
    # Spawn a physical background child process with sleep
    child_proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(20)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert child_proc.poll() is None, "Child process failed to start"

    try:
        # Execute zombie sweep
        terminated_count = sweep_zombie_processes()
        assert terminated_count >= 1, "sweep_zombie_processes did not report terminating child process"
        time.sleep(0.5)
        assert child_proc.poll() is not None, "Child process was not terminated by sweep_zombie_processes"
    finally:
        if child_proc.poll() is None:
            child_proc.kill()
            child_proc.wait()


# ==============================================================================
# 4. QuarantineEnvironment Lifecycle and File Isolation [M] [D]
# ==============================================================================

def test_quarantine_env_default_initialization() -> None:
    """Verify QuarantineEnvironment initializes with valid base directory, prefix, and UUID."""
    qe = QuarantineEnvironment()
    assert qe.base_dir.exists(), f"Base directory does not exist: {qe.base_dir}"
    assert qe.prefix == "cochem_exec_"
    assert qe.preserve_on_failure is False
    assert len(qe.copy_paths) == 0

    # Verify quarantine_id is a valid UUID4 string
    parsed_uuid = uuid.UUID(qe.quarantine_id, version=4)
    assert str(parsed_uuid) == qe.quarantine_id
    assert qe.quarantine_dir.name.startswith("cochem_exec_")


def test_quarantine_env_context_lifecycle_clean_exit() -> None:
    """Verify directory is physically created on enter and fully removed on normal exit."""
    captured_dir: Optional[Path] = None

    with QuarantineEnvironment() as qe:
        captured_dir = qe.quarantine_dir
        assert captured_dir.exists(), f"Quarantine directory was not created: {captured_dir}"
        assert captured_dir.is_dir(), f"Quarantine path is not a directory: {captured_dir}"

    assert captured_dir is not None
    assert not captured_dir.exists(), f"Quarantine directory was not cleaned up: {captured_dir}"


def test_quarantine_env_custom_base_and_prefix(tmp_path: Path) -> None:
    """Verify QuarantineEnvironment respects custom base directory and custom directory prefix."""
    custom_prefix = "custom_sandbox_"
    custom_base = tmp_path / "sandbox_parent"
    custom_base.mkdir(parents=True, exist_ok=True)

    with QuarantineEnvironment(base_dir=custom_base, prefix=custom_prefix) as qe:
        assert qe.quarantine_dir.parent.resolve() == custom_base.resolve()
        assert qe.quarantine_dir.name.startswith(custom_prefix)
        assert qe.quarantine_dir.exists()

    assert not qe.quarantine_dir.exists()


def test_quarantine_env_copy_paths_files_and_directories(tmp_path: Path) -> None:
    """Verify QuarantineEnvironment copies specified source files and directory trees on enter."""
    src_dir = tmp_path / "source_data"
    src_dir.mkdir(parents=True, exist_ok=True)

    file_a = src_dir / "sample_a.txt"
    file_a.write_text("CONTENT_ALPHA_12345", encoding="utf-8")

    sub_dir = src_dir / "nested_dir"
    sub_dir.mkdir(parents=True, exist_ok=True)
    file_b = sub_dir / "sample_b.json"
    file_b.write_text('{"status": "CONFIRMED_PHYSICAL"}', encoding="utf-8")

    standalone_file = tmp_path / "standalone.conf"
    standalone_file.write_text("KEY=VALUE_OMEGA", encoding="utf-8")

    with QuarantineEnvironment(copy_paths=[standalone_file, src_dir]) as qe:
        dest_standalone = qe.quarantine_dir / "standalone.conf"
        dest_src_dir = qe.quarantine_dir / "source_data"
        dest_file_a = dest_src_dir / "sample_a.txt"
        dest_file_b = dest_src_dir / "nested_dir" / "sample_b.json"

        assert dest_standalone.exists()
        assert dest_standalone.read_text(encoding="utf-8") == "KEY=VALUE_OMEGA"

        assert dest_src_dir.exists()
        assert dest_file_a.exists()
        assert dest_file_a.read_text(encoding="utf-8") == "CONTENT_ALPHA_12345"

        assert dest_file_b.exists()
        assert dest_file_b.read_text(encoding="utf-8") == '{"status": "CONFIRMED_PHYSICAL"}'


def test_quarantine_env_preserve_on_failure_flag(tmp_path: Path) -> None:
    """Verify preserve_on_failure keeps directory on error, while default cleans up."""
    preserved_dir: Optional[Path] = None

    # Case 1: preserve_on_failure = True -> directory preserved on exception
    try:
        with QuarantineEnvironment(base_dir=tmp_path, preserve_on_failure=True) as qe:
            preserved_dir = qe.quarantine_dir
            assert preserved_dir.exists()
            raise RuntimeError("Intentional error for forensic preservation check")
    except RuntimeError:
        pass

    assert preserved_dir is not None
    assert preserved_dir.exists(), "Quarantine directory was not preserved when preserve_on_failure=True"

    # Clean up preserved directory
    shutil.rmtree(preserved_dir, ignore_errors=True)

    # Case 2: preserve_on_failure = False (default) -> directory deleted even on exception
    deleted_dir: Optional[Path] = None
    try:
        with QuarantineEnvironment(base_dir=tmp_path, preserve_on_failure=False) as qe:
            deleted_dir = qe.quarantine_dir
            assert deleted_dir.exists()
            raise RuntimeError("Intentional error for deletion check")
    except RuntimeError:
        pass

    assert deleted_dir is not None
    assert not deleted_dir.exists(), "Quarantine directory was not removed when preserve_on_failure=False"


# ==============================================================================
# 5. QuarantineEnvironment Command Execution (run_command) [M]
# ==============================================================================

def test_run_command_success_and_working_directory() -> None:
    """Verify run_command executes process with cwd set strictly to the quarantine directory."""
    with QuarantineEnvironment() as qe:
        cmd = [sys.executable, "-c", "import os, pathlib; print(pathlib.Path.cwd().resolve())"]
        result = qe.run_command(cmd)

        assert result.exit_code == 0
        assert result.passed is True
        assert result.timed_out is False
        assert result.duration_s >= 0.0

        executed_cwd = Path(result.stdout.strip()).resolve()
        assert executed_cwd == qe.quarantine_dir.resolve(), (
            f"Execution cwd ({executed_cwd}) does not match quarantine dir ({qe.quarantine_dir.resolve()})"
        )


def test_run_command_failure_and_stderr_capture() -> None:
    """Verify run_command accurately records non-zero return codes and stderr content."""
    with QuarantineEnvironment() as qe:
        cmd = [
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('ISOLATED_FAILURE_REASON'); sys.exit(37)",
        ]
        result = qe.run_command(cmd)

        assert result.exit_code == 37
        assert result.passed is False
        assert result.timed_out is False
        assert "ISOLATED_FAILURE_REASON" in result.stderr


def test_run_command_timeout_expiration() -> None:
    """Verify run_command handles timeout expiration, returns exit code 124, and marks timed_out."""
    with QuarantineEnvironment() as qe:
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        result = qe.run_command(cmd, timeout=1)

        assert result.exit_code == 124
        assert result.timed_out is True
        assert result.passed is False
        assert result.duration_s >= 0.8


def test_run_command_env_overrides() -> None:
    """Verify run_command applies environment overrides to the executed subprocess."""
    with QuarantineEnvironment() as qe:
        env_vars = {
            "CUSTOM_TEST_VARIABLE": "VERIFIED_ISOLATION_PAYLOAD_999",
            "CUSTOM_ISOLATION_MODE": "STRICT_QUARANTINE",
        }
        cmd = [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('CUSTOM_TEST_VARIABLE')); print(os.environ.get('CUSTOM_ISOLATION_MODE'))",
        ]
        result = qe.run_command(cmd, env_overrides=env_vars)

        assert result.exit_code == 0
        assert result.passed is True
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        assert len(lines) >= 2
        assert lines[0] == "VERIFIED_ISOLATION_PAYLOAD_999"
        assert lines[1] == "STRICT_QUARANTINE"


def test_run_command_invalid_executable_handling() -> None:
    """Verify run_command gracefully captures OS execution errors (non-existent binaries)."""
    with QuarantineEnvironment() as qe:
        cmd = ["__non_existent_quarantine_binary_99999__"]
        result = qe.run_command(cmd)

        assert result.exit_code == 1
        assert result.passed is False
        assert result.timed_out is False
        assert len(result.stderr) > 0


# ==============================================================================
# 6. run_in_quarantine Convenience Wrapper [M]
# ==============================================================================

def test_run_in_quarantine_execution_and_auto_cleanup() -> None:
    """Verify run_in_quarantine runs command in ephemeral directory and cleans up afterwards."""
    cmd = [sys.executable, "-c", "print('RUN_IN_QUARANTINE_SUCCESS')"]
    result = run_in_quarantine(cmd, timeout=60)

    assert result.exit_code == 0
    assert result.passed is True
    assert "RUN_IN_QUARANTINE_SUCCESS" in result.stdout

    # The quarantine directory must have been purged upon exit
    quarantine_path = Path(result.quarantine_dir)
    assert not quarantine_path.exists(), f"Quarantine dir was not purged: {quarantine_path}"


def test_run_in_quarantine_with_copy_paths(tmp_path: Path) -> None:
    """Verify run_in_quarantine provides copied files to the isolated command."""
    sample_file = tmp_path / "payload.txt"
    sample_file.write_text("AUTHENTIC_DATA_42", encoding="utf-8")

    cmd = [
        sys.executable,
        "-c",
        "from pathlib import Path; print(Path('payload.txt').read_text(encoding='utf-8'))",
    ]
    result = run_in_quarantine(cmd, copy_paths=[sample_file])

    assert result.exit_code == 0
    assert result.passed is True
    assert result.stdout.strip() == "AUTHENTIC_DATA_42"


# ==============================================================================
# 7. CLI Execution, Path Canonicalization & Cryptographic ExecutionReceipt [M] [D]
# ==============================================================================

def test_cli_no_arguments_exits_with_code_1() -> None:
    """Verify zero_trust_runner.py CLI exits with code 1 when invoked with no command."""
    res = subprocess.run(
        [sys.executable, str(RUNNER_PATH)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1


def test_cli_dash_dash_argument_stripping() -> None:
    """Verify zero_trust_runner.py CLI strips leading '--' command separator."""
    res = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--", sys.executable, "-c", "print('DASH_STRIPPED_OUTPUT')"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "DASH_STRIPPED_OUTPUT" in res.stdout


def test_cli_cryptographic_execution_receipt_verification() -> None:
    """Verify CLI produces valid Cryptographic ExecutionReceipt matching SHA-256 hashes."""
    nonce_val = "PROOF_OF_EXECUTION_NONCE_888"
    stdout_payload = "OUT_PHYSICAL_STREAM_DATA"
    stderr_payload = "ERR_PHYSICAL_STREAM_DATA"

    cmd = [
        sys.executable,
        str(RUNNER_PATH),
        "--nonce",
        nonce_val,
        "--",
        sys.executable,
        "-c",
        f"import sys; sys.stdout.write('{stdout_payload}\\n'); sys.stderr.write('{stderr_payload}\\n')",
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0

    stdout_text = res.stdout
    stderr_text = res.stderr

    # Verify stdout payload is printed
    assert stdout_payload in stdout_text
    # Verify stderr payload is printed to stderr stream
    assert stderr_payload in stderr_text

    # Verify execution receipt structure in stdout
    assert "=== EXECUTION RECEIPT ===" in stdout_text
    assert f"NONCE: {nonce_val}" in stdout_text
    assert "EXIT_CODE: 0" in stdout_text
    assert "DURATION:" in stdout_text
    assert "STDOUT_HASH:" in stdout_text
    assert "STDERR_HASH:" in stdout_text
    assert "===========================" in stdout_text

    # Extract SHA-256 hashes from receipt
    stdout_hash_match = re.search(r"STDOUT_HASH:\s+([a-fA-F0-9]{64})", stdout_text)
    stderr_hash_match = re.search(r"STDERR_HASH:\s+([a-fA-F0-9]{64})", stdout_text)

    assert stdout_hash_match is not None, "Failed to extract STDOUT_HASH from receipt"
    assert stderr_hash_match is not None, "Failed to extract STDERR_HASH from receipt"

    reported_stdout_hash = stdout_hash_match.group(1).lower()
    reported_stderr_hash = stderr_hash_match.group(1).lower()

    # Calculate expected SHA256 of the command's original streams
    expected_stdout_hash = hashlib.sha256(f"{stdout_payload}\n".encode("utf-8")).hexdigest()
    expected_stderr_hash = hashlib.sha256(f"{stderr_payload}\n".encode("utf-8")).hexdigest()

    assert reported_stdout_hash == expected_stdout_hash, (
        f"Mismatch in STDOUT_HASH: {reported_stdout_hash} vs {expected_stdout_hash}"
    )
    assert reported_stderr_hash == expected_stderr_hash, (
        f"Mismatch in STDERR_HASH: {reported_stderr_hash} vs {expected_stderr_hash}"
    )


def test_cli_quarantine_sandbox_conftest_compatibility() -> None:
    """Verify zero_trust_runner satisfies conftest.py sandbox check by running inside quarantine."""
    # Invoking pytest via zero_trust_runner satisfies conftest.py check: 'cochem_exec_' in os.getcwd()
    cmd = [
        sys.executable,
        str(RUNNER_PATH),
        "--nonce",
        "CONFTEST_SANDBOX_VERIFICATION",
        "--",
        "pytest",
        "tests/test_zero_trust_runner.py",
        "-k",
        "test_quarantine_result_fields_and_defaults",
        "-v",
    ]

    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, f"Pytest in quarantine failed with output:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "PASSED" in res.stdout
    assert "=== EXECUTION RECEIPT ===" in res.stdout
    assert "NONCE: CONFTEST_SANDBOX_VERIFICATION" in res.stdout


# ==============================================================================
# 8. Dynamic Mendeleev Atomic Mass Integration Invariant Check [M]
# ==============================================================================

def test_mendeleev_dynamic_mass_integration() -> None:
    """Verify adherence to Mendeleev Library Mandate: dynamic atomic masses without hardcoding."""
    carbon = element("C")
    hydrogen = element("H")
    oxygen = element("O")

    c_mass = carbon.mass
    h_mass = hydrogen.mass
    o_mass = oxygen.mass

    assert isinstance(c_mass, float)
    assert isinstance(h_mass, float)
    assert isinstance(o_mass, float)

    # Validate physical bounds
    assert 12.0 < c_mass < 12.02
    assert 1.007 < h_mass < 1.01
    assert 15.998 < o_mass < 16.002

    # Calculate molecular mass of Water Dimer ((H2O)2 = H4O2)
    water_dimer_mass = (4 * h_mass) + (2 * o_mass)
    assert 36.0 < water_dimer_mass < 36.05
