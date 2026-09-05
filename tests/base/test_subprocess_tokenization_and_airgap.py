# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 2: Subprocess Execution Tokenization & Tripartite Workspace Air-Gap Enforcement.
Adheres strictly to Method Matrix §8A.2, §8A.6, and Zero-Mock Mandate.
"""

from __future__ import annotations

import sys
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


def test_tripartite_airgap_boundary_confinement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that output files and execution are strictly confined to T_scratch,
    and assert_writable_path prevents writing into T_repo.
    """
    repo_dir = tmp_path / "repo"
    scratch_dir = tmp_path / "scratch"
    store_dir = tmp_path / "store"
    repo_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    store_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("COCHEM_REPO_DIR", str(repo_dir))
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_dir))
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(store_dir))

    t_repo, t_scratch, t_store = get_tripartite_paths()
    assert t_repo == repo_dir.resolve()
    assert t_scratch == scratch_dir.resolve()
    assert t_store == store_dir.resolve()

    # Verify that writing directly to T_repo raises AirGapViolationError
    forbidden_target = repo_dir / "unauthorized_output.tmp"
    with pytest.raises(AirGapViolationError):
        assert_writable_path(forbidden_target)

    # Verify execution in scratch leaves repo clean
    broker = SubprocessBroker(cwd=scratch_dir)
    out_file = scratch_dir / "valid_output.engrad"
    cmd = [
        sys.executable,
        "-c",
        f"from pathlib import Path; Path(r'{out_file}').write_text('gradient_data', encoding='utf-8')",
    ]
    res = broker.execute(cmd, cwd=scratch_dir)
    assert res.success
    assert out_file.exists()
    assert len(list(repo_dir.iterdir())) == 0, "T_repo was polluted!"
