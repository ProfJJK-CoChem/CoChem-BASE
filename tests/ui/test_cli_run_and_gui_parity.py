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
WATER_DIMER_XYZ = "\n".join(Path(__file__).parent.parent.joinpath("data", "water_dimer.xyz").read_text(encoding="utf-8").strip().splitlines()[2:])


def test_dual_entry_point_model_parity():
    """Validates that CLI CalculationMatrixConfig and GUI MatrixConfigModel

    exhibit structural parity on the identical physical input payload.
    """
    payload = {
        "geometry": WATER_DIMER_XYZ,
        "engine": "ORCA",
        "method": "wB97M-V",
        "basis_set": "def2-TZVP",
    }

    # GUI Model validation
    gui_cfg = MatrixConfigModel(**payload)
    assert gui_cfg.engine == "orca"
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
            "--scratch", str(Path(tmpdir) / "scratch"),
            "--output", str(Path(tmpdir) / "results"),
            "--json",
        ]

        from cochem_base.core_engine.hardware_profiler import profile_hardware
        hardware = profile_hardware()
        authority = Path(tmpdir) / "hardware.json"
        authority.write_text(json.dumps({"hardware": {
            "physical_cpu_cores": min(hardware.physical_cores, len(hardware.available_cpu_ids)),
            "ram_mb": hardware.available_ram_bytes // (1024 * 1024),
        }}))
        env = {**os.environ, "COCHEM_CONFIG": str(authority)}
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        assert result.returncode == 0, f"CLI run failed with stderr: {result.stderr}"

        # Validate JSON telemetry output
        parsed_out = json.loads(result.stdout)
        assert parsed_out["status"] == "DECK_GENERATED"
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
        assert "Unknown engine" in combined_out


def test_slurm_script_synthesis_valid(tmp_path: Path):
    """Stage declared allocation and real scientific input without claiming execution."""
    config_path = tmp_path / "water.json"
    config_path.write_text(json.dumps({
        "geometry": "O 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n",
        "engine": "xtb", "method": "GFN2-xTB", "basis_set": "built-in", "is_opt": True,
    }))
    staged = tmp_path / "planned job with spaces"
    script = generate_slurm_script(
        config_path=config_path, staging_dir=staged,
        job_name="water_opt", partition="standard", nodes=1,
        ntasks_per_node=2, cpus_per_task=1, mem="1GB", walltime="08:00:00",
        email="researcher@chem.univ.edu",
    )
    assert "#SBATCH --nodes=1" in script and "#SBATCH --ntasks=1" in script
    assert "#SBATCH --cpus-per-task=2" in script and "#SBATCH --mem=1024M" in script
    assert "#SBATCH --mail-user=researcher@chem.univ.edu" in script
    assert "module load" not in script and "matrix_input.inp" not in script
    manifest = json.loads((staged / "job_manifest.json").read_text())
    assert manifest["status"] == "STAGED_INPUT_ONLY"
    assert manifest["scientific_execution_performed"] is False
    assert manifest["allocation_authority"].startswith("declared_request_only")
    assert json.loads((staged / "calculation.json").read_text())["geometry"] == json.loads(config_path.read_text())["geometry"]
    checked = subprocess.run(["bash", "-n", str(staged / "submit.sh")], capture_output=True, text=True, timeout=15)
    assert checked.returncode == 0, checked.stderr


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


def test_slurm_controller_staging_and_dispatch(tmp_path: Path):
    """Missing cluster configuration stays pending; changed scientific inputs fail."""
    controller = SlurmSubmissionController(default_partition="compute")
    config_path = tmp_path / "water.json"
    config_path.write_text(json.dumps({
        "geometry": "O 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n",
        "engine": "xtb", "method": "GFN2-xTB", "basis_set": "built-in", "is_opt": True,
    }))
    staged = tmp_path / "submission"
    script = controller.validate_and_generate(config_path=config_path, staging_dir=staged,
                job_name="water", partition="compute", nodes=1, ntasks_per_node=1,
                mem="512MB", walltime="01:00:00")
    assert (staged / "submit.sh").read_text() == script
    status = controller.dispatch(staged / "submit.sh")
    assert status.startswith("PENDING_CLUSTER_CONFIGURATION")
    assert controller.last_submitted_job_id is None
    assert not (staged / "submission.json").exists()
    (staged / "calculation.json").write_text(config_path.read_text() + " ")
    with pytest.raises(ValueError, match="altered"):
        controller.dispatch(staged / "submit.sh")
