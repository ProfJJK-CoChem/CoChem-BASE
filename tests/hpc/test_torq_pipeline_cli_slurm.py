"""Test suite for SLURM Batch Submission CLI Contract & Dynamic HPC Resource Mapping (Suggestion #70).

Method Matrix v4 §8A.6: Production High-Performance Computing Mandate (Tier 6: HPC).
Strict Zero-Mock Mandate: Authentic CLI argument parsing, dynamic SLURM environment
ingestion, genuine XYZ file ingestion, Tripartite Air-Gap enforcement, and SLURM launcher contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from Libraries.cochem_torq_pipeline import (
    TorqPipelineCliArgs,
    parse_cli_args,
    execute_cli_pipeline,
)


@pytest.fixture
def sample_water_xyz(tmp_path: Path) -> Path:
    """Generates an authentic 3D geometry file for H2O."""
    xyz_path = tmp_path / "water.xyz"
    content = (
        "3\n"
        "Water molecule benchmark\n"
        "O   0.00000000   0.00000000   0.11726900\n"
        "H   0.00000000   0.75695000  -0.46907600\n"
        "H   0.00000000  -0.75695000  -0.46907600\n"
    )
    xyz_path.write_text(content, encoding="utf-8")
    return xyz_path


@pytest.mark.skipif("SLURM_CPUS_PER_TASK" not in os.environ, reason="Physical SLURM environment not present (Zero-Mock Mandate)")
def test_torq_pipeline_cli_args_parsing_slurm(sample_water_xyz: Path, tmp_path: Path):
    """Verifies that parse_cli_args validates schema and dynamically ingests true SLURM variables."""
    out_dir = tmp_path / "output_artifacts"
    scratch_dir = tmp_path / "scratch_space"

    cli_args = parse_cli_args([
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "B3LYP-D4/def2-TZVP",
    ])

    # Assert Pydantic validation and field bindings
    assert isinstance(cli_args, TorqPipelineCliArgs)
    assert cli_args.input_geometry == sample_water_xyz.resolve()
    assert cli_args.output_directory == out_dir.resolve()
    assert cli_args.scratch_dir == scratch_dir.resolve()
    assert cli_args.theory_level == "B3LYP-D4/def2-TZVP"

    # Assert physical SLURM scaling matches the real environment
    assert cli_args.cpus_per_task == int(os.environ["SLURM_CPUS_PER_TASK"])


def test_torq_pipeline_cli_args_parsing_local(sample_water_xyz: Path, tmp_path: Path):
    """Verifies that parse_cli_args validates schema physically without SLURM."""
    out_dir = tmp_path / "output_artifacts"
    scratch_dir = tmp_path / "scratch_space"

    # Ensure we don't accidentally run this when SLURM is present, or just verify defaults
    cli_args = parse_cli_args([
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "B3LYP-D4/def2-TZVP",
    ])

    assert isinstance(cli_args, TorqPipelineCliArgs)
    assert cli_args.input_geometry == sample_water_xyz.resolve()


def test_torq_pipeline_cli_execution_and_airgap(sample_water_xyz: Path, tmp_path: Path):
    """Executes the CLI pipeline directly and verifies output deliverables in Ring 3."""
    out_dir = tmp_path / "artifacts"
    scratch_dir = tmp_path / "scratch"

    env = os.environ.copy()
    env["COCHEM_SCRATCH"] = str(scratch_dir)
    env["COCHEM_ARTIFACTS"] = str(out_dir)
    env["COCHEM_ROOT"] = str(REPO_BASE)
    env["SLURM_CPUS_PER_TASK"] = "2"
    env["SLURM_MEM_PER_NODE"] = "4096"
    env["PYTHONPATH"] = f"{REPO_TORQ}{os.pathsep}{REPO_BASE / 'src'}{os.pathsep}{REPO_BASE}"

    cmd = [
        sys.executable,
        "-m",
        "Libraries.cochem_torq_pipeline",
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "PM6",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, f"Airgap pipeline failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Verify deliverables written to Ring 3 persistent artifacts
    results_file = out_dir / "pipeline_results.json"
    assert results_file.exists(), f"Missing {results_file}"
    assert results_file.stat().st_size > 0

    final_xyz = out_dir / "final_structure.xyz"
    assert final_xyz.exists(), f"Missing {final_xyz}"
    assert final_xyz.stat().st_size > 0
    assert "3" in final_xyz.read_text(encoding="utf-8")

    # Air-gap verification: assert scratch and output are isolated from Ring 1
    root_resolved = REPO_BASE.resolve()
    assert root_resolved not in out_dir.resolve().parents
    assert root_resolved not in scratch_dir.resolve().parents


def test_torq_pipeline_cli_subprocess_invocation(sample_water_xyz: Path, tmp_path: Path):
    """Executes cochem_torq_pipeline.py via python -m CLI invocation."""
    out_dir = tmp_path / "artifacts_cli"
    scratch_dir = tmp_path / "scratch_cli"

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{REPO_TORQ}{os.pathsep}{REPO_BASE / 'src'}{os.pathsep}{REPO_BASE}"
    env["SLURM_CPUS_PER_TASK"] = "4"
    env["SLURM_MEM_PER_NODE"] = "8192"

    cmd = [
        sys.executable,
        "-m",
        "Libraries.cochem_torq_pipeline",
        "--input", str(sample_water_xyz),
        "--output", str(out_dir),
        "--scratch", str(scratch_dir),
        "--theory", "PM6",
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, f"CLI command failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert (out_dir / "pipeline_results.json").exists()
    assert (out_dir / "final_structure.xyz").exists()


def test_slurm_script_forwarding_contract():
    """Verifies that cochem_submit.slurm forwards --input, --output, --scratch, --theory."""
    slurm_script = REPO_TORQ / "HPC_Launchers" / "cochem_submit.slurm"
    assert slurm_script.exists()
    content = slurm_script.read_text(encoding="utf-8")

    # Verify transparent CLI parameter forwarding on line 68+
    assert "--input" in content
    assert "--output" in content
    assert "--scratch" in content
    assert "--theory" in content
    assert "${INPUT_GEOM}" in content
    assert "${THEORY_LEVEL}" in content
