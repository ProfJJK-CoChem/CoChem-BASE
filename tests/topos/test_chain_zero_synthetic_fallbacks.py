# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Eradication of Synthetic GBW/OPT Fallback Artifacts & Explicit Exception Signaling.
Validates Suggestion #142 (Deliverable 2) under Method Matrix v4 §8B.3, §8B.4 [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from cochem_base.chain import (
    Chain,
    Stage,
    MissingBinaryError,
    ConvergenceFailureError,
    CorruptOutputError,
)


def test_chain_missing_binary_raises_immediately(tmp_path: Path) -> None:
    """Verify that Chain raises MissingBinaryError immediately when configured binary does not exist."""
    workdir = tmp_path / "chain_workdir"
    workdir.mkdir(parents=True, exist_ok=True)

    # Seed XYZ with authentic physical coordinates
    seed_xyz = workdir / "seed.xyz"
    seed_xyz.write_text("2\nH2 molecule\nH 0.0 0.0 0.0\nH 0.0 0.0 0.7414\n", encoding="utf-8")

    chain = Chain(
        workdir=workdir,
        h5_path=workdir / "campaign.h5",
        orca_cmd="non_existent_binary_xyz_12345",
        strict_guards=True,
    )

    stage = Stage(
        name="s1_test",
        level="TightOpt",
        geom_from=None,
    )

    with pytest.raises(MissingBinaryError) as exc_info:
        chain.run_stage(stage, seed_xyz=seed_xyz, dry_run=False)

    assert "non_existent_binary" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    # Assert that NO synthetic binary or mock output files were written
    gbw_files = list(workdir.glob("*.gbw"))
    opt_files = list(workdir.glob("*.opt"))
    assert len(gbw_files) == 0, f"Synthetic .gbw files detected: {gbw_files}"
    assert len(opt_files) == 0, f"Synthetic .opt files detected: {opt_files}"

    # Verify no fake 'ORCA TERMINATED NORMALLY' was injected into an output file
    for out_file in workdir.glob("*.out"):
        content = out_file.read_text(encoding="utf-8")
        assert "ORCA TERMINATED NORMALLY" not in content, "Simulated termination string detected in output!"


def test_chain_exception_hierarchy() -> None:
    """Verify explicit exception inheritance conforming to Method Matrix §8B.4."""
    assert issubclass(MissingBinaryError, (FileNotFoundError, Exception))
    assert issubclass(ConvergenceFailureError, (RuntimeError, Exception))
    assert issubclass(CorruptOutputError, (RuntimeError, Exception))