"""Unit tests for AsyncProcessRunner and Tripartite Storage integration."""

import sys
from pathlib import Path

import h5py
import pytest

from src.cochem.hpc.models import (
    CoChemHpcScalingError,
    SlurmJobDirectiveSpec,
    SlurmResourceValidationError,
)
from src.cochem.runners.async_process_runner import AsyncProcessRunner


@pytest.fixture
def tripartite_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Generate isolated Tripartite storage directory tree."""
    src_dir = tmp_path / "src"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir = tmp_path / "scratch"

    src_dir.mkdir(parents=True)
    artifacts_dir.mkdir(parents=True)
    scratch_dir.mkdir(parents=True)

    return src_dir, artifacts_dir, scratch_dir


def test_tripartite_read_only_src_protection(tripartite_dirs: tuple[Path, Path, Path]) -> None:
    """Verify write attempts into $COCH_SRC are strictly rejected."""
    src_dir, artifacts_dir, scratch_dir = tripartite_dirs
    runner = AsyncProcessRunner(
        src_dir=src_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
    )

    forbidden_target = src_dir / "unauthorized_write.txt"
    with pytest.raises((PermissionError, CoChemHpcScalingError)):
        runner.validate_write_path(forbidden_target)

    # Allowed targets in scratch and artifacts
    runner.validate_write_path(scratch_dir / "temp.log")
    runner.validate_write_path(artifacts_dir / "final_model.h5")


def test_swmr_hdf5_telemetry_streaming(tripartite_dirs: tuple[Path, Path, Path]) -> None:
    """Verify SWMR HDF5 telemetry recording and concurrent reading."""
    import asyncio

    async def _run() -> None:
        src_dir, artifacts_dir, scratch_dir = tripartite_dirs
        runner = AsyncProcessRunner(
            src_dir=src_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir=scratch_dir,
        )

        telemetry_file = scratch_dir / "telemetry.h5"
        runner.init_telemetry(telemetry_file)

        # Step 1 written
        runner.record_telemetry_metric(telemetry_file, step=1, energy=-76.421, walltime=0.45)

        # Concurrent reader opens file while writer is actively attached
        with h5py.File(telemetry_file, "r", swmr=True, libver="latest") as h5_reader:
            steps = h5_reader["telemetry/step"][:]
            energies = h5_reader["telemetry/energy"][:]
            assert len(steps) == 1
            assert steps[0] == 1
            assert abs(energies[0] - (-76.421)) < 1e-5

            # Step 2 written while reader handle is currently held open
            runner.record_telemetry_metric(telemetry_file, step=2, energy=-76.435, walltime=0.92)

            # Reader refreshes datasets and verifies streamed record
            h5_reader["telemetry/step"].refresh()
            h5_reader["telemetry/energy"].refresh()
            steps_updated = h5_reader["telemetry/step"][:]
            energies_updated = h5_reader["telemetry/energy"][:]
            assert len(steps_updated) == 2
            assert steps_updated[1] == 2
            assert abs(energies_updated[1] - (-76.435)) < 1e-5

        runner.close_telemetry(telemetry_file)

    asyncio.run(_run())


def test_async_process_runner_dispatch_task(tripartite_dirs: tuple[Path, Path, Path]) -> None:
    """Verify physical dispatch_task execution lifecycle and scratch cleanup."""
    import asyncio

    async def _run() -> None:
        src_dir, artifacts_dir, scratch_dir = tripartite_dirs
        runner = AsyncProcessRunner(
            src_dir=src_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir=scratch_dir,
        )

        # Create input file in src
        input_file = src_dir / "data.txt"
        input_file.write_text("HYDROGEN_1_008", encoding="utf-8")

        py_code = (
            "import sys\n"
            "print('Worker computing energy rank 0', flush=True)\n"
        )

        # 1. Execution retaining scratch for inspection
        result = await runner.dispatch_task(
            task_name="compute_step",
            binary_args=[sys.executable, "-c", py_code],
            cleanup_on_completion=False,
        )

        assert result["exit_code"] == 0
        assert "Worker computing energy" in result["stdout"]
        assert Path(result["telemetry_file"]).exists()

        # Explicit scratch cleanup
        runner.cleanup_scratch("compute_step")
        assert not Path(result["telemetry_file"]).exists()

        # 2. Execution with default ephemeral scratch cleanup
        result_ephemeral = await runner.dispatch_task(
            task_name="compute_step_ephemeral",
            binary_args=[sys.executable, "-c", py_code],
            cleanup_on_completion=True,
        )
        assert result_ephemeral["exit_code"] == 0
        assert not Path(result_ephemeral["telemetry_file"]).exists()

    asyncio.run(_run())


def test_async_process_runner_slurm_validation(tripartite_dirs: tuple[Path, Path, Path]) -> None:
    """Verify preflight Slurm validation during dispatch_task."""
    import asyncio

    async def _run() -> None:
        src_dir, artifacts_dir, scratch_dir = tripartite_dirs
        runner = AsyncProcessRunner(
            src_dir=src_dir,
            artifacts_dir=artifacts_dir,
            scratch_dir=scratch_dir,
        )

        spec = SlurmJobDirectiveSpec(
            job_name="oversized_slurm_job",
            partition="small_partition",
            nodes=100,
            ntasks_per_node=64,
            cpus_per_task=8,
            walltime_str="12:00:00",
            memory_per_node_mb=500_000,
            scratch_dir="/scratch/job",
            artifact_dir="/artifacts/job",
        )
        partition_limits = {
            "allowed_partitions": ["small_partition"],
            "max_nodes": 2,
        }

        with pytest.raises(SlurmResourceValidationError):
            await runner.dispatch_task(
                task_name="slurm_job",
                binary_args=["orca", "job.inp"],
                slurm_spec=spec,
                partition_limits=partition_limits,
            )

    asyncio.run(_run())
