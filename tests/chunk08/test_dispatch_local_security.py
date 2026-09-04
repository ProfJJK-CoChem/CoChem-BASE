# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 3 (Suggestion #73):
Structured Local Dispatch & Tripartite Air-Gap Isolation.
Verifies deprecation of shell=True, handling of spaces and special chars (%),
rejection of shell injection attempts, and stream redirection in Ring 2 scratch.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pytest

from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter


def test_dispatch_local_structured_execution_and_stream_isolation() -> None:
    """Verify commands with spaces and % execute cleanly without shell=True,

    and standard output streams are saved into Ring 2 scratch files.
    """
    with tempfile.TemporaryDirectory() as scratch_td:
        # Set Ring 2 scratch
        os.environ["COCHEM_SCRATCH"] = scratch_td
        router = ExecutionRouter()

        # Command containing spaces and % in arguments
        test_msg = "Hello %VARIABLE% World with Spaces"
        cmd = f'"{sys.executable}" -c "import sys; print(\'{test_msg}\')"'

        exit_code = router._dispatch_local(
            payload_command=cmd,
            cwd=scratch_td,
            timeout=15.0,
        )

        assert exit_code == 0

        # Verify stream isolation: output files exist in scratch
        out_files = list(Path(scratch_td).glob("*.out")) + list(Path(scratch_td).glob("*.log")) + list(Path(scratch_td).glob("*task*/*.out"))
        assert len(out_files) > 0, "No stdout/stderr stream files found in Ring 2 scratch"

        content = out_files[0].read_text(encoding="utf-8")
        assert "Hello %VARIABLE% World with Spaces" in content


def test_dispatch_local_rejects_shell_injection() -> None:
    """Verify that shell injection vectors (e.g. ; or && or |) are treated as literal arguments

    and do not execute arbitrary chained sub-commands.
    """
    with tempfile.TemporaryDirectory() as scratch_td:
        os.environ["COCHEM_SCRATCH"] = scratch_td
        router = ExecutionRouter()

        canary_file = Path(scratch_td) / "injection_canary.txt"

        # Attempt command injection via chained shell syntax: python -c "print(1)" ; touch canary
        cmd = f'"{sys.executable}" -c "print(1)" ; "{sys.executable}" -c "open(\'{canary_file.as_posix()}\', \'w\').write(\'injected\')"'

        # Without shell=True, the whole command is passed to sys.executable as arguments or split,
        # which will either fail or not execute the secondary command via a shell interpreter
        exit_code = router._dispatch_local(
            payload_command=cmd,
            cwd=scratch_td,
            timeout=15.0,
        )

        # The canary file must NOT exist because shell interpretation is disabled
        assert not canary_file.exists(), "Shell injection succeeded! shell=True was improperly used."
