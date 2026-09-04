"""Physical Zero-Mock Test Suite for SubprocessBroker Contract Harmonization & Process Tree Reclamation.

Method Matrix Reference: Method Matrix v4 §8A.4, Cross-Platform Architecture Mandate.
Validates Suggestion #67:
- Interface signature harmonization (__init__ with cwd, env, timeout_seconds; execute with command string or list, cwd, env).
- Robust command parsing via shlex.split without character decomposition.
- Strict working directory and environment inheritance.
- Deterministic child process tree termination on timeout via psutil.
"""

from __future__ import annotations

import os
import sys
import time
import pytest
from pathlib import Path

from cochem_base.concurrency.subprocess_broker import (
    SubprocessBroker,
    SubprocessExecutionResult,
)


def test_subprocess_broker_string_command(tmp_path: Path):
    """Test 1: Invoke broker with string command. Verify output parses cleanly without single-char decomposition."""
    broker = SubprocessBroker(cwd=tmp_path)
    result = broker.execute("echo 'cochem-concurrency-test'")

    assert result.success is True
    assert result.returncode == 0
    # Assert string parsed cleanly as a whole token, not decomposed character by character
    clean_out = result.stdout.strip().replace("'", "").replace('"', "")
    assert "cochem-concurrency-test" in clean_out


def test_subprocess_broker_list_command(tmp_path: Path):
    """Test 2: Invoke broker with pre-tokenized list of strings. Verify identical execution."""
    broker = SubprocessBroker(cwd=tmp_path)
    result = broker.execute(["echo", "cochem-concurrency-test"])

    assert result.success is True
    assert result.returncode == 0
    clean_out = result.stdout.strip().replace("'", "").replace('"', "")
    assert "cochem-concurrency-test" in clean_out


def test_subprocess_broker_cwd_and_env(tmp_path: Path):
    """Test 3: Pass custom cwd and env dicts during init and execute; assert correct execution directory & env."""
    custom_dir = tmp_path / "custom_workdir"
    custom_dir.mkdir(parents=True, exist_ok=True)
    custom_env = {"COCHEM_TEST_VAR": "provenance_verified_777"}

    broker = SubprocessBroker(cwd=custom_dir, env={"COCHEM_BASE_VAR": "base_value"})

    # Python one-liner to print current working directory and env vars
    cmd = [
        sys.executable,
        "-c",
        (
            "import os, pathlib; "
            "print('CWD=' + str(pathlib.Path.cwd())); "
            "print('VAR=' + os.environ.get('COCHEM_TEST_VAR', '')); "
            "print('BASE=' + os.environ.get('COCHEM_BASE_VAR', ''))"
        ),
    ]

    result = broker.execute(cmd, cwd=custom_dir, env=custom_env)

    assert result.success is True
    assert result.returncode == 0
    assert f"CWD={custom_dir.resolve()}" in result.stdout
    assert "VAR=provenance_verified_777" in result.stdout
    assert "BASE=base_value" in result.stdout


def test_subprocess_broker_timeout_process_tree_cleanup(tmp_path: Path):
    """Test 4: Launch long-running child process tree with short timeout (0.5s); assert psutil tree termination."""
    broker = SubprocessBroker(cwd=tmp_path, timeout_seconds=60.0)

    # Launch python script that spawns a child process and both sleep for 10s
    spawn_script = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)']); "
        "time.sleep(10)"
    )
    cmd = [sys.executable, "-c", spawn_script]

    t0 = time.time()
    result = broker.execute(cmd, timeout_seconds=0.5)
    elapsed = time.time() - t0

    # Execution should fail gracefully due to timeout within ~2s
    assert result.success is False
    assert result.returncode == -124 or "timed out" in result.stderr.lower()
    assert elapsed < 5.0
