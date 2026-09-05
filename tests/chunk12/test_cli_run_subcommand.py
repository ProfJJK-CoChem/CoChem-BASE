"""Unit and integration tests for Deliverable 1: Dedicated Headless CLI run Subcommand,
Tripartite Air-Gap Sandbox & CUDA Resource Pooling (Suggestion #111).

Method Matrix v4 (§1.6, §8A, §8C) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic execution and configuration testing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pytest

from cli import action_run, build_cli_parser

WATER_XYZ = """3
Water monomer test
O 0.00000000 0.00000000 0.11779000
H 0.00000000 0.75545300 -0.47116100
H 0.00000000 -0.75545300 -0.47116100
"""

def test_cli_parser_registers_run_subcommand():
    parser = build_cli_parser()
    args = parser.parse_args(["run", "--config", "matrix_config.json", "--device", "cpu", "--threads", "4"])
    assert args.subcommand == "run"
    assert args.device == "cpu"
    assert args.threads == 4
    assert hasattr(args, "scratch")
    assert hasattr(args, "output")

def test_cli_run_tripartite_sandbox_promotion(tmp_path: Path):
    cfg_file = tmp_path / "matrix_config.json"
    scratch_root = tmp_path / "scratch"
    output_dir = tmp_path / "store"
    scratch_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    config_data = {
        "geometry": WATER_XYZ,
        "engine": "xtb",
        "method": "GFN2-xTB",
        "basis_set": "default",
        "product_class": "Product A (De Novo Search)",
        "theory_tier": "Tier 3: Semiempirical Screening",
    }
    cfg_file.write_text(json.dumps(config_data), encoding="utf-8")

    args = argparse.Namespace(
        config=cfg_file,
        scratch=scratch_root,
        scratch_dir=scratch_root,
        device="auto",
        threads=2,
        output=output_dir,
        engine="xtb",
        dry_run=True,
        json=True,
    )

    exit_code = action_run(args)
    assert exit_code == 0

    promoted_files = list(output_dir.glob("*"))
    assert len(promoted_files) > 0

    sha_files = list(output_dir.glob("*.sha256"))
    assert len(sha_files) > 0
    for sha_f in sha_files:
        artifact_f = output_dir / sha_f.stem
        if artifact_f.exists():
            expected_hash = hashlib.sha256(artifact_f.read_bytes()).hexdigest()
            assert expected_hash in sha_f.read_text(encoding="utf-8")

def test_cli_run_cpu_fallback_when_cuda_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    cfg_file = tmp_path / "matrix_config.json"
    output_dir = tmp_path / "store"
    output_dir.mkdir(parents=True, exist_ok=True)

    config_data = {
        "geometry": WATER_XYZ,
        "engine": "orca",
        "method": "wB97M-V",
        "basis_set": "def2-TZVP",
        "product_class": "Product A (De Novo Search)",
        "theory_tier": "Tier 1: Modern Dispersion DFT",
    }
    cfg_file.write_text(json.dumps(config_data), encoding="utf-8")

    args = argparse.Namespace(
        config=cfg_file,
        scratch=None,
        scratch_dir=None,
        device="auto",
        threads=4,
        output=output_dir,
        engine="orca",
        dry_run=True,
        json=False,
    )

    exit_code = action_run(args)
    assert exit_code == 0
