# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: SubprocessBroker API Harmonization & Tokenized Command Dispatch.
Validates Suggestion #146 (Deliverable 6) under Method Matrix v4 §8A.6, Tripartite Air-Gap [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import pytest

from cochem.concurrency.subprocess_broker import SubprocessBroker, SubprocessExecutionResult


def test_subprocess_broker_string_command_no_character_splitting(tmp_path: Path) -> None:
    """Verify that passing a string command does NOT split characters (shlex tokenization)."""
    broker = SubprocessBroker(cwd=tmp_path)

    # Run authentic python one-liner as string
    cmd_str = f'"{sys.executable}" -c "import sys; sys.stdout.write(\'tokenized_ok\')"'
    res = broker.execute(cmd_str)

    assert isinstance(res, SubprocessExecutionResult)
    assert res.returncode == 0
    assert "tokenized_ok" in res.stdout
    # Verify command is a list of words, not characters
    assert isinstance(res.command, list)
    assert len(res.command) >= 2
    assert all(len(arg) > 1 for arg in res.command if arg not in ("-c", "-m"))


def test_subprocess_broker_list_command_and_metadata(tmp_path: Path) -> None:
    """Verify list command execution, custom env, walltime, and peak memory tracking."""
    custom_env = {"COCH_TEST_MARKER": "authenticated_physical_run"}
    broker = SubprocessBroker(cwd=tmp_path, env=custom_env)

    cmd_list = [
        sys.executable,
        "-c",
        "import os, sys; sys.stdout.write(os.environ.get('COCH_TEST_MARKER', ''))",
    ]

    res = broker.execute(cmd_list, timeout_sec=10.0)

    assert isinstance(res, SubprocessExecutionResult)
    assert res.returncode == 0
    assert res.stdout == "authenticated_physical_run"
    assert res.walltime_sec >= 0.0
    assert res.peak_memory_mb >= 0.0
    assert res.command == cmd_list