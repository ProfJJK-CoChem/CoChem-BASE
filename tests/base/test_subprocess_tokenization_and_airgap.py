# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 2: Subprocess Execution Tokenization & Tripartite Workspace Air-Gap Enforcement.
Adheres strictly to Method Matrix §8A.2, §8A.6, and Zero-Mock Mandate.
"""

from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path

import pytest

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem.core.context import (
    AirGapViolationError,
    assert_writable_path,
    get_tripartite_paths,
)


def test_subprocess_tokenization_special_chars(tmp_path: Path) -> None:
    """
    Invoke SubprocessBroker with argument strings containing spaces, backslashes, and % characters.
    Asserts command executes without invoking shell=True and produces expected output.
    """
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    broker = SubprocessBroker(cwd=scratch_dir)

    # Command using python to print an argument containing spaces, backslashes, and % symbols
    # e.g.: print(r"%pal nprocs 8 end \ path with spaces %geom")
    test_arg = "%pal nprocs 8 end \\ path with spaces %geom"
    cmd = [
        sys.executable,
        "-c",
        "import sys; print(sys.argv[1])",
        test_arg,
    ]

    result = broker.execute(cmd, cwd=scratch_dir)
    assert result.success, f"Execution failed: {result.stderr}"
    assert result.returncode == 0
    assert test_arg in result.stdout.strip()


def test_tripartite_airgap_boundary_confinement(tmp_path: Path) -> None:
    """Exercise the actual broker in a child with separate source/scratch/store."""
    repo_dir, scratch_dir, store_dir = (tmp_path / name for name in ("repo", "scratch", "store"))
    for path in (repo_dir, scratch_dir, store_dir):
        path.mkdir()
    environment = {**os.environ, "COCHEM_REPO_DIR": str(repo_dir),
                   "COCHEM_SCRATCH_DIR": str(scratch_dir), "COCHEM_ARTIFACT_DIR": str(store_dir)}
    code = """
import os, sys
from pathlib import Path
from cochem.core.context import AirGapViolationError, assert_writable_path, get_tripartite_paths
from cochem.concurrency.subprocess_broker import SubprocessBroker
repo, scratch, store = get_tripartite_paths()
assert repo == Path(os.environ['COCHEM_REPO_DIR']).resolve()
assert scratch == Path(os.environ['COCHEM_SCRATCH_DIR']).resolve()
assert store == Path(os.environ['COCHEM_ARTIFACT_DIR']).resolve()
try:
    assert_writable_path(repo / 'unauthorized_output.tmp')
except AirGapViolationError:
    rejected = True
else:
    rejected = False
assert rejected
output = scratch / 'valid_output.txt'
result = SubprocessBroker(cwd=scratch).execute([
    sys.executable, '-c', 'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("transport data", encoding="utf-8")',
    str(output)], cwd=scratch)
assert result.success
assert output.read_text() == 'transport data'
assert not list(repo.iterdir())
"""
    subprocess.run([sys.executable, "-c", code], env=environment, check=True, timeout=20)
