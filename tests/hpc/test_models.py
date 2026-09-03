"""Unit tests for HPC data models and exception hierarchy."""

import pytest
from pydantic import ValidationError

from src.cochem.hpc.models import (
    CoChemHpcScalingError,
    CudaMemoryExhaustionError,
    CudaResourceBudget,
    MpiClusterExecutionConfig,
    MpiProcessSupervisorError,
    SlurmDryRunResult,
    SlurmJobDirectiveSpec,
    SlurmResourceValidationError,
)


def test_exception_hierarchy() -> None:
    """Verify HPC exception inheritance structure."""
    assert issubclass(CudaMemoryExhaustionError, CoChemHpcScalingError)
    assert issubclass(SlurmResourceValidationError, CoChemHpcScalingError)
    assert issubclass(MpiProcessSupervisorError, CoChemHpcScalingError)
    assert issubclass(CoChemHpcScalingError, Exception)

    err = CudaMemoryExhaustionError("VRAM exhausted on device 0")
    assert str(err) == "VRAM exhausted on device 0"
    assert isinstance(err, CoChemHpcScalingError)


def test_cuda_resource_budget_valid() -> None:
    """Verify CudaResourceBudget calculations and properties."""
    budget = CudaResourceBudget(
        device_id=0,
        total_vram_mb=16384,
        free_vram_mb=8192,
        reserved_headroom_mb=1024,
        fractional_limit=0.85,
    )
    # available = max(0, int((8192 - 1024) * 0.85)) = int(7168 * 0.85) = 6092
    assert budget.available_vram_mb == 6092
    assert budget.device_id == 0
    assert budget.total_vram_mb == 16384

    # Test headroom truncation
    low_budget = CudaResourceBudget(
        device_id=1,
        total_vram_mb=8192,
        free_vram_mb=512,
        reserved_headroom_mb=1024,
        fractional_limit=0.85,
    )
    assert low_budget.available_vram_mb == 0


def test_cuda_resource_budget_immutability_and_bounds() -> None:
    """Verify CudaResourceBudget immutability and boundary validations."""
    budget = CudaResourceBudget(
        device_id=0,
        total_vram_mb=4096,
        free_vram_mb=2048,
    )
    with pytest.raises(ValidationError):
        budget.device_id = 1  # type: ignore

    with pytest.raises(ValidationError):
        CudaResourceBudget(
            device_id=-1,
            total_vram_mb=4096,
            free_vram_mb=2048,
        )

    with pytest.raises(ValidationError):
        CudaResourceBudget(
            device_id=0,
            total_vram_mb=0,
            free_vram_mb=0,
        )

    with pytest.raises(ValidationError):
        CudaResourceBudget(
            device_id=0,
            total_vram_mb=4096,
            free_vram_mb=2048,
            fractional_limit=1.5,
        )


def test_slurm_job_directive_spec_valid() -> None:
    """Verify valid Slurm directive specifications."""
    spec = SlurmJobDirectiveSpec(
        job_name="orca_ts_opt",
        partition="standard",
        nodes=2,
        ntasks_per_node=4,
        cpus_per_task=2,
        gpus_per_node=1,
        walltime_str="04:00:00",
        memory_per_node_mb=32768,
        account="chem_proj",
        qos="high",
        scratch_dir="/scratch/chem_job_001",
        artifact_dir="/artifacts/chem_job_001",
    )
    assert spec.job_name == "orca_ts_opt"
    assert spec.nodes == 2
    assert spec.walltime_str == "04:00:00"

    # Walltime with day prefix
    spec_day = SlurmJobDirectiveSpec(
        job_name="long_job",
        partition="batch",
        walltime_str="2-12:30:00",
        memory_per_node_mb=16384,
        scratch_dir="/scratch/chem_job_002",
        artifact_dir="/artifacts/chem_job_002",
    )
    assert spec_day.walltime_str == "2-12:30:00"


def test_slurm_job_directive_spec_invalid() -> None:
    """Verify invalid Slurm directive fields raise ValidationError."""
    # Invalid walltime format
    with pytest.raises(ValidationError):
        SlurmJobDirectiveSpec(
            job_name="test_job",
            partition="batch",
            walltime_str="invalid_time",
            memory_per_node_mb=16384,
            scratch_dir="/scratch/job",
            artifact_dir="/artifacts/job",
        )

    # Empty job name
    with pytest.raises(ValidationError):
        SlurmJobDirectiveSpec(
            job_name="",
            partition="batch",
            walltime_str="01:00:00",
            memory_per_node_mb=16384,
            scratch_dir="/scratch/job",
            artifact_dir="/artifacts/job",
        )

    # Negative nodes
    with pytest.raises(ValidationError):
        SlurmJobDirectiveSpec(
            job_name="test_job",
            partition="batch",
            nodes=0,
            walltime_str="01:00:00",
            memory_per_node_mb=16384,
            scratch_dir="/scratch/job",
            artifact_dir="/artifacts/job",
        )


def test_slurm_dry_run_result_model() -> None:
    """Verify SlurmDryRunResult model creation and fields."""
    res = SlurmDryRunResult(
        is_valid=True,
        generated_script_content="#!/bin/bash\n#SBATCH --job-name=test",
        estimated_memory_per_rank_mb=4096,
        orca_maxcore_mb=3072,
        validation_errors=[],
        validation_warnings=["Non-standard partition specified"],
    )
    assert res.is_valid is True
    assert res.orca_maxcore_mb == 3072
    assert len(res.validation_warnings) == 1

    with pytest.raises(ValidationError):
        res.is_valid = False  # type: ignore


def test_mpi_cluster_execution_config_valid_and_invalid() -> None:
    """Verify MpiClusterExecutionConfig launcher pattern and bounds."""
    for launcher in ("srun", "mpirun", "mpiexec"):
        config = MpiClusterExecutionConfig(
            launcher=launcher,
            n_nodes=2,
            n_tasks_per_node=8,
            cpus_per_task=2,
            timeout_seconds=7200.0,
        )
        assert config.launcher == launcher
        assert config.n_nodes == 2

    # Invalid launcher
    with pytest.raises(ValidationError):
        MpiClusterExecutionConfig(launcher="invalid_exec")

    # Invalid timeout
    with pytest.raises(ValidationError):
        MpiClusterExecutionConfig(launcher="srun", timeout_seconds=0.0)
