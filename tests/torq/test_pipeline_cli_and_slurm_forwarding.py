# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Automated SLURM Batch Execution Interface & CLI Parameter Binding.
Validates Suggestion #149 (Deliverable 9) under Method Matrix v4 §8A.6, §8B [M], [D].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import pytest

from Libraries.cochem_torq_pipeline import parse_cli_args, TorqPipelineCliArgs

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SLURM_SCRIPT = REPO_ROOT.parent / "CoChem-TORQ" / "HPC_Launchers" / "cochem_submit.slurm"


def test_pipeline_cli_argument_parsing(tmp_path: Path) -> None:
    """Verify that cochem_torq_pipeline CLI parses flags correctly."""
    input_file = tmp_path / "mol.xyz"
    input_file.write_text("2\nH2\nH 0 0 0\nH 0 0 0.74\n", encoding="utf-8")
    out_dir = tmp_path / "output"
    scratch_dir = tmp_path / "scratch"

    cli_args = [
        "--input", str(input_file),
        "--output-dir", str(out_dir),
        "--scratch-dir", str(scratch_dir),
        "--device", "cpu",
        "--task-id", "42",
        "--mode", "refine",
    ]

    parsed = parse_cli_args(cli_args)
    assert isinstance(parsed, TorqPipelineCliArgs)
    assert parsed.input_geometry == input_file.resolve()
    assert parsed.output_directory == out_dir.resolve()
    assert parsed.scratch_dir == scratch_dir.resolve()
    assert parsed.device == "cpu"
    assert parsed.task_id == 42
    assert parsed.mode == "refine"


def test_pipeline_cli_non_zero_exit_on_invalid_input(tmp_path: Path) -> None:
    """Verify that running the pipeline CLI entrypoint with an invalid input path exits with code != 0."""
    non_existent_file = tmp_path / "missing_structure.xyz"
    cmd = [
        sys.executable,
        "-m",
        "Libraries.cochem_torq_pipeline",
        "--input", str(non_existent_file),
        "--output-dir", str(tmp_path / "out"),
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT.parent / "CoChem-TORQ"),
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, f"Expected non-zero exit code on missing input, got {proc.returncode}"


def test_slurm_script_parameter_binding() -> None:
    """Verify that cochem_submit.slurm forwards pipeline parameters dynamically."""
    assert SLURM_SCRIPT.exists(), f"SLURM script missing: {SLURM_SCRIPT}"
    content = SLURM_SCRIPT.read_text(encoding="utf-8")

    assert "--input" in content
    assert "--output-dir" in content or "--output" in content
    assert "--scratch-dir" in content or "--scratch" in content
    assert "SLURM_ARRAY_TASK_ID" in content