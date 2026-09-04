"""
Zero-Mock Physical Validation Suite: CLI 'run' Subcommand, Dual-Entry-Point Parity,
and HPC / Slurm Shell Injection Defense.
Method Matrix v4: §1.6, §8A, §13, and SRS Chunk 4 Suggestions #32 & #33.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from src.cochem.hpc.slurm_controller import (
    sanitize_slurm_parameter,
    validate_slurm_walltime,
    generate_slurm_script,
    submit_slurm_job,
    SlurmSubmissionController,
)
from cli import CalculationMatrixConfig
from ui.voila_layout.cochem_gui import MatrixConfigModel


# Authentic physical coordinates of water dimer (H2O...H2O) at equilibrium (R_OO ~ 2.97 A)
WATER_DIMER_XYZ = (
    "O -1.47400000  0.00000000  0.06300000\n"
    "H -1.82100000  0.77200000 -0.40400000\n"
    "H -0.52800000  0.00000000 -0.12600000\n"
    "O  1.42800000  0.00000000 -0.06300000\n"
    "H  1.78200000  0.77200000  0.40400000\n"
    "H  1.78200000 -0.77200000  0.40400000"
)


def test_dual_entry_point_model_parity():
    """Validates that CLI CalculationMatrixConfig and GUI MatrixConfigModel

    exhibit structural parity on the identical physical input payload.
    """
    payload = {
        "geometry": WATER_DIMER_XYZ,
        "engine": "ORCA",
        "method": "wB97M-V",
        "basis_set": "def2-TZVP",
        "topos_heuristic": "iMTD-GC",
        "topos_dedup": 0.05,
        "torq_dihedrals": "",
        "torq_resolution": 36,
        "torq_qrrho": False,
    }

    # GUI Model validation
    gui_cfg = MatrixConfigModel(**payload)
    assert gui_cfg.engine == "ORCA"
    assert gui_cfg.method == "wB97M-V"

    # CLI Model validation
    cli_cfg = CalculationMatrixConfig(**payload)
    assert cli_cfg.engine == "orca"
    assert cli_cfg.method == "wB97M-V"
    assert cli_cfg.basis_set == "def2-TZVP"


def test_cli_run_subcommand_dry_run_success():
    """Validates that 'python cli.py run --config ... --dry-run' executes physically

    via subprocess and returns exit code 0 with Pydantic verification.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_file = Path(tmpdir) / "test_matrix_config.json"
        config_data = {
            "geometry": WATER_DIMER_XYZ,
            "engine": "orca",
            "method": "wB97M-V",
            "basis_set": "def2-TZVP",
            "topos_heuristic": "iMTD-GC",
            "topos_dedup": 0.05,
        }
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        cmd = [
            sys.executable,
            "cli.py",
            "run",
            "--config",
            str(cfg_file),
            "--dry-run",
            "--json",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"CLI run failed with stderr: {result.stderr}"

        # Validate JSON telemetry output
        parsed_out = json.loads(result.stdout)
        assert parsed_out["status"] == "VALIDATED_SUCCESS"
        assert parsed_out["engine"] == "orca"
        assert parsed_out["method"] == "wB97M-V"
        assert parsed_out["dry_run"] is True


def test_cli_run_subcommand_validation_failure():
    """Validates that 'python cli.py run' fails fast with exit code 1 on an invalid engine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_file = Path(tmpdir) / "invalid_config.json"
        config_data = {
            "geometry": WATER_DIMER_XYZ,
            "engine": "unsupported_bogus_engine",
            "method": "HF",
            "basis_set": "STO-3G",
        }
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        cmd = [
            sys.executable,
            "cli.py",
            "run",
            "--config",
            str(cfg_file),
            "--dry-run",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 1
        combined_out = result.stdout + result.stderr
        assert "Validation Error" in combined_out or "Unsupported engine" in combined_out


def test_slurm_script_synthesis_valid():
    """Validates authentic Slurm script synthesis per Method Matrix §8A."""
    script = generate_slurm_script(
        job_name="h2o_dimer_opt",
        partition="standard",
        nodes=2,
        ntasks_per_node=16,
        cpus_per_task=2,
        mem="64GB",
        walltime="08:00:00",
        engine="orca",
        input_deck_path="orca_calc.inp",
        email="researcher@chem.univ.edu",
    )

    assert "#!/bin/bash" in script
    assert "#SBATCH --job-name=h2o_dimer_opt" in script
    assert "#SBATCH --partition=standard" in script
    assert "#SBATCH --nodes=2" in script
    assert "#SBATCH --ntasks-per-node=16" in script
    assert "#SBATCH --cpus-per-task=2" in script
    assert "#SBATCH --time=08:00:00" in script
    assert "#SBATCH --mem=64GB" in script
    assert "#SBATCH --mail-user=researcher@chem.univ.edu" in script
    assert "module load orca" in script
    assert "orca orca_calc.inp > orca.out 2>&1" in script


@pytest.mark.parametrize(
    "malicious_input",
    [
        "; rm -rf /",
        "$(whoami)",
        "test | cat /etc/passwd",
        "`id`",
        "job\n#SBATCH --bad",
        "job; ls",
        "foo & bar",
        "test>out",
        "val<in",
    ],
)
def test_slurm_parameter_injection_defense(malicious_input):
    """Adversarial validation: 100% of shell injection attempts must be blocked with ValueError."""
    with pytest.raises(ValueError) as excinfo:
        sanitize_slurm_parameter("partition", malicious_input)
    assert "Shell injection detected" in str(excinfo.value)


def test_slurm_walltime_validation():
    """Validates walltime bounds checking and 48:00:00 maximum cap enforcement."""
    # Valid formats within 48h limit
    assert validate_slurm_walltime("04:00:00") == "04:00:00"
    assert validate_slurm_walltime("1-12:30:00") == "1-12:30:00"
    assert validate_slurm_walltime("48:00:00") == "48:00:00"
    assert validate_slurm_walltime("2-00:00:00") == "2-00:00:00"

    # Walltime cap exceeded (> 48:00:00)
    with pytest.raises(ValueError, match="exceeds maximum allowable limit of 48:00:00"):
        validate_slurm_walltime("49:00:00")

    with pytest.raises(ValueError, match="exceeds maximum allowable limit of 48:00:00"):
        validate_slurm_walltime("2-01:00:00")

    with pytest.raises(ValueError, match="exceeds maximum allowable limit of 48:00:00"):
        validate_slurm_walltime("3-00:00:00")

    # Zero walltime
    with pytest.raises(ValueError, match="must be strictly greater than zero"):
        validate_slurm_walltime("00:00:00")

    # Invalid component bounds
    with pytest.raises(ValueError):
        validate_slurm_walltime("04:65:00")  # Minutes >= 60

    with pytest.raises(ValueError):
        validate_slurm_walltime("04:00:99")  # Seconds >= 60

    with pytest.raises(ValueError):
        validate_slurm_walltime("not_a_time")


def test_slurm_controller_staging_and_dispatch():
    """Validates SlurmSubmissionController staging and non-crashing execution on local environment."""
    controller = SlurmSubmissionController(default_partition="gpu")
    with tempfile.TemporaryDirectory() as tmpdir:
        script_content = controller.validate_and_generate(
            job_name="h2o_test",
            partition="gpu",
            nodes=1,
            ntasks_per_node=4,
            mem="16GB",
            walltime="01:00:00",
            engine="xtb",
            input_deck_path="coord",
        )
        script_path = Path(tmpdir) / "submit.sh"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        status = controller.dispatch(script_path)
        assert isinstance(status, str)
        assert len(status) > 0
        # If running in environment without sbatch, must state staged / sbatch unavailable
        if shutil.which("sbatch") is None:
            assert "PENDING_LOCAL_STAGED" in status
