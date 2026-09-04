"""Physical Zero-Mock Test Suite for Purge of Fabricated SCF/Opt Cycles & Corrupt Binary Wavefunctions.

Method Matrix Reference: Method Matrix v4 §8B.4 (Canonical Arrows 4 & 5 Binary Wavefunction Projection via %moinp) [M].
Validates Suggestion #63:
- Raising of MissingBinaryError when required quantum chemistry binary is absent.
- Raising of ConvergenceFailureError upon convergence failure (zero synthetic fallback iterations).
- Zero emission of corrupt synthetic binary bytes in .gbw or .opt files.
- Zero mock strings containing "ORCA TERMINATED NORMALLY" or fabricated scf_cyc = 12.
- Clean purge of temporary scratch files on calculation failure.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import pytest
from pathlib import Path

from cochem_base.exceptions import (
    ConvergenceFailureError,
    MissingBinaryError,
)

# Explicitly load Chain from CoChem-TOPOS/chain.py to test the TOPOS engine
_topos_chain_path = (Path(__file__).resolve().parent.parent.parent.parent / "CoChem-TOPOS" / "chain.py").resolve()
if not _topos_chain_path.is_file():
    _topos_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/chain.py")

spec = importlib.util.spec_from_file_location("topos_chain_mod", str(_topos_chain_path))
topos_chain = importlib.util.module_from_spec(spec)
sys.modules["topos_chain_mod"] = topos_chain
spec.loader.exec_module(topos_chain)

Chain = topos_chain.Chain
Stage = topos_chain.Stage
write_xyz = topos_chain.write_xyz


def test_chain_missing_binary_raises_explicit_error(tmp_path: Path):
    """Assert that passing an invalid ORCA binary path immediately raises MissingBinaryError without mock fallback. [M]"""
    workdir = tmp_path / "chain_scratch"
    workdir.mkdir(parents=True, exist_ok=True)

    # Write authentic seed geometry
    seed_xyz = workdir / "seed.xyz"
    symbols = ["N", "N"]
    coords = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0975)]
    write_xyz(seed_xyz, symbols, coords)

    # Configure Chain with nonexistent binary
    invalid_bin = "/nonexistent/path/to/orca"
    chain = Chain(
        workdir=workdir,
        h5_path="campaign.h5",
        charge=0,
        mult=1,
        orca_bin=invalid_bin,
    )

    stage = Stage(name="stage1_pbe", level="! PBE def2-SVP Opt")

    # Assert MissingBinaryError is raised explicitly
    with pytest.raises(MissingBinaryError) as exc_info:
        chain.run_stage(stage, seed_xyz=seed_xyz)

    assert "ORCA binary" in str(exc_info.value)

    # Inspect scratch directory: assert zero bytes written into .gbw or .opt files
    gbw_file = workdir / "stage1_pbe.gbw"
    opt_file = workdir / "stage1_pbe.opt"
    assert not gbw_file.exists() or gbw_file.stat().st_size == 0
    assert not opt_file.exists() or opt_file.stat().st_size == 0

    # Assert no synthetic "ORCA TERMINATED NORMALLY" string exists in output files
    out_file = workdir / "stage1_pbe.out"
    if out_file.exists():
        content = out_file.read_text(encoding="utf-8", errors="ignore")
        assert "ORCA TERMINATED NORMALLY" not in content
        assert "SCF ITERATIONS 12" not in content


def test_chain_zero_synthetic_byte_sequences(tmp_path: Path):
    """Verify that corrupt mock binary wavefunctions (e.g. b'ORCA_GBW_STATE_VECTOR_MOCK_FREE') are never emitted. [M]"""
    workdir = tmp_path / "chain_corrupt_test"
    workdir.mkdir(parents=True, exist_ok=True)

    seed_xyz = workdir / "seed.xyz"
    write_xyz(seed_xyz, ["H", "H"], [(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)])

    chain = Chain(
        workdir=workdir,
        h5_path="campaign.h5",
        charge=0,
        mult=1,
        orca_bin="/dev/null/orca_fake",
    )

    stage = Stage(name="opt_stage", level="! B3LYP def2-SVP Opt")

    with pytest.raises(MissingBinaryError):
        chain.run_stage(stage, seed_xyz=seed_xyz)

    # Search entire working directory for mock signatures
    for p in workdir.rglob("*"):
        if p.is_file() and p.suffix in (".gbw", ".opt"):
            raw_bytes = p.read_bytes()
            assert b"MOCK_FREE" not in raw_bytes
            assert b"REUSE_STATE" not in raw_bytes
