"""Unit tests for Slurm dry-run script generator and validator."""

from src.cochem.hpc.models import SlurmJobDirectiveSpec
from src.cochem.hpc.slurm_generator import SlurmDryRunGenerator


def test_slurm_generator_orca_maxcore_calculation() -> None:
    """Verify exact ORCA %maxcore formula according to Method Matrix v4 specifications."""
    spec = SlurmJobDirectiveSpec(
        job_name="orca_calc",
        partition="standard",
        nodes=1,
        ntasks_per_node=4,
        cpus_per_task=2,
        walltime_str="08:00:00",
        memory_per_node_mb=32768,
        scratch_dir="/scratch/chem/orca_run_01",
        artifact_dir="/artifacts/chem/orca_run_01",
    )
    generator = SlurmDryRunGenerator()
    result = generator.generate_sbatch_script(spec, solver="orca", input_filename="calc.inp")

    assert result.is_valid is True
    # Formula: floor((32768 * 0.75) / 4) = floor(24576 / 4) = 6144
    assert result.orca_maxcore_mb == 6144
    assert result.estimated_memory_per_rank_mb == 8192
    assert "#SBATCH --job-name=orca_calc" in result.generated_script_content
    assert "#SBATCH --partition=standard" in result.generated_script_content
    assert "#SBATCH --mem=32768M" in result.generated_script_content
    assert "orca calc.inp > orca_output.out" in result.generated_script_content
    assert "COCH_SCRATCH=\"/scratch/chem/orca_run_01\"" in result.generated_script_content
    assert "COCH_ARTIFACTS=\"/artifacts/chem/orca_run_01\"" in result.generated_script_content


def test_slurm_generator_crest_and_xtb() -> None:
    """Verify CREST and xTB specific commands and thread bindings."""
    spec = SlurmJobDirectiveSpec(
        job_name="crest_opt",
        partition="compute",
        nodes=1,
        ntasks_per_node=1,
        cpus_per_task=8,
        walltime_str="02:00:00",
        memory_per_node_mb=16384,
        scratch_dir="/scratch/crest_01",
        artifact_dir="/artifacts/crest_01",
    )
    generator = SlurmDryRunGenerator()

    # CREST test
    crest_res = generator.generate_sbatch_script(spec, solver="crest", input_filename="coord.xyz")
    assert crest_res.is_valid is True
    assert "export OMP_NUM_THREADS=8" in crest_res.generated_script_content
    assert "crest coord.xyz --nci --nocross --noreftopo -T 8" in crest_res.generated_script_content

    # xTB test
    xtb_res = generator.generate_sbatch_script(spec, solver="xtb", input_filename="coord.xyz")
    assert xtb_res.is_valid is True
    assert "export OMP_NUM_THREADS=8" in xtb_res.generated_script_content
    assert "xtb coord.xyz" in xtb_res.generated_script_content


def test_slurm_generator_partition_limits_validation() -> None:
    """Verify partition boundary checking."""
    spec = SlurmJobDirectiveSpec(
        job_name="oversized_job",
        partition="standard",
        nodes=8,
        ntasks_per_node=64,
        cpus_per_task=4,
        walltime_str="48:00:00",
        memory_per_node_mb=128000,
        scratch_dir="/scratch/job",
        artifact_dir="/artifacts/job",
    )
    partition_limits = {
        "allowed_partitions": ["standard", "gpu"],
        "max_nodes": 4,
        "max_cpus_per_task": 2,
        "max_mem_mb": 64000,
    }
    generator = SlurmDryRunGenerator()
    errors = generator.validate_directives(spec, partition_limits=partition_limits)

    assert len(errors) >= 3
    assert any("max_nodes" in err.lower() or "nodes" in err.lower() for err in errors)
    assert any("cpus_per_task" in err.lower() for err in errors)
    assert any("memory" in err.lower() for err in errors)

    result = generator.generate_sbatch_script(spec, solver="orca", partition_limits=partition_limits)
    assert result.is_valid is False
    assert len(result.validation_errors) >= 3


def test_slurm_generator_posix_path_validation() -> None:
    """Verify non-POSIX paths are rejected during directive validation."""
    spec = SlurmJobDirectiveSpec(
        job_name="win_paths",
        partition="standard",
        nodes=1,
        ntasks_per_node=1,
        cpus_per_task=1,
        walltime_str="01:00:00",
        memory_per_node_mb=8192,
        scratch_dir="relative/path/scratch",
        artifact_dir="/valid/posix/artifacts",
    )
    generator = SlurmDryRunGenerator()
    errors = generator.validate_directives(spec)
    assert any("scratch_dir" in err and "absolute posix" in err.lower() for err in errors)
