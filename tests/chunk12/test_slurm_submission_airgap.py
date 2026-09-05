"""Unit and integration tests for Deliverable 2: HPC/SLURM Batch Submission Controller &
Sanitized Air-Gapped sbatch Dispatch (Suggestion #112).

Method Matrix v4 (§8A) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Shell injection defense and air-gapped sbatch dispatch.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cochem.hpc.slurm_controller import (
    SlurmSubmissionController,
    sanitize_slurm_parameter,
    validate_slurm_walltime,
)
from ui.voila_layout.cochem_gui import CoChemGUI


def test_slurm_parameter_sanitization_defense():
    assert sanitize_slurm_parameter("partition", "gpu_standard") == "gpu_standard"
    assert sanitize_slurm_parameter("job_name", "water_dimer-opt.1") == "water_dimer-opt.1"
    assert sanitize_slurm_parameter("mem", "64GB") == "64GB"

    injection_attacks = [
        "standard; rm -rf /",
        "partition_name | cat /etc/passwd",
        "job && echo hacked",
        "`whoami`",
        "$(reboot)",
        "gpu\n#SBATCH --bad-option",
        "part<hack>",
    ]
    for attack in injection_attacks:
        with pytest.raises(ValueError, match="Shell injection detected"):
            sanitize_slurm_parameter("partition", attack)

def test_slurm_walltime_validation():
    assert validate_slurm_walltime("04:00:00") == "04:00:00"
    assert validate_slurm_walltime("1-12:00:00") == "1-12:00:00"

    with pytest.raises(ValueError, match="exceeds maximum allowable limit of 48:00:00"):
        validate_slurm_walltime("50:00:00")

    with pytest.raises(ValueError, match="Invalid walltime format"):
        validate_slurm_walltime("not-a-time")

def test_slurm_script_airgap_and_promotion(tmp_path: Path):
    controller = SlurmSubmissionController()
    manifest_data = {
        "job_name": "cochem_test_run",
        "partition": "compute",
        "nodes": 2,
        "ntasks_per_node": 16,
        "mem": "32GB",
        "walltime": "08:00:00",
        "engine": "orca",
        "input_deck_path": "matrix_input.inp",
    }

    script_content = controller.validate_and_generate(**manifest_data)
    assert "#SBATCH --partition=compute" in script_content
    assert "#SBATCH --nodes=2" in script_content
    assert "$SLURM_TMPDIR" in script_content

    script_path = tmp_path / "cochem_test_run.sh"
    script_path.write_text(script_content, encoding="utf-8")
    status = controller.dispatch(script_path)
    assert "PENDING_LOCAL_STAGED" in status or status.isdigit()

def test_gui_slurm_submit_event_binding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COCHEM_ARTIFACT_DIR", str(tmp_path))
    gui = CoChemGUI()
    assert hasattr(gui, "slurm_submit_btn")
    assert hasattr(gui, "_on_slurm_submit")

    gui.partition_input.value = "gpu_batch"
    gui.job_name_input.value = "gui_slurm_job"
    gui._on_slurm_submit()
    assert "gpu_batch" in gui.slurm_status_output.value or "Ready" in gui.slurm_status_output.value or "Slurm" in gui.slurm_status_output.value
