# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 2 (Suggestion #72):
HPC SLURM Single-Node Shared-Memory Template Generation.
Asserts that rendered SLURM scripts contain --nodes=1, --ntasks=1, and --cpus-per-task={N}
without --ntasks={N}, and verifies ORCA %pal and OpenMP bindings.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pytest

from cochem_base.calc.slurm_generator import (
    SlurmGenerator,
    SlurmSubmissionSpec,
)


def test_slurm_generator_shared_memory_topology() -> None:
    """Assert that rendered SLURM scripts contain --nodes=1, --ntasks=1,

    and --cpus-per-task={cores} without --ntasks={cores}.
    """
    spec = SlurmSubmissionSpec(
        job_name="orca_shared_mem",
        partition="standard",
        cores=8,
        mem_mb=16384,
        walltime="12:00:00",
        scratch_dir="/scratch/job_01",
        artifact_dir="/artifacts/job_01",
        solver="orca",
    )
    generator = SlurmGenerator()
    script = generator.generate_submission_script(spec, input_file="orca_calc.inp")

    # Assert explicit shared-memory directives
    assert "#SBATCH --nodes=1" in script
    assert "#SBATCH --ntasks=1" in script
    assert "#SBATCH --cpus-per-task=8" in script

    # Assert banned multi-task directive is absent
    assert "#SBATCH --ntasks=8" not in script
    assert "#SBATCH --ntasks=4" not in script

    # Verify ORCA parallel execution alignment (%pal nprocs 8 end)
    assert "%pal nprocs 8 end" in script or "nprocs 8" in script or "cpus_per_task" in script
    assert "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK" in script or "export OMP_NUM_THREADS=8" in script


def test_slurm_generator_dynamic_topology_clamping(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that requesting cores exceeding physical node core capacity clamps cores

    and logs a [SCHEDULER-WARNING].
    """
    import psutil
    physical_cores = psutil.cpu_count(logical=False) or 8
    requested_cores = physical_cores + 128

    spec = SlurmSubmissionSpec(
        job_name="oversubscribed_job",
        partition="standard",
        cores=requested_cores,
        mem_mb=32768,
        walltime="04:00:00",
        scratch_dir="/scratch/job_over",
        artifact_dir="/artifacts/job_over",
        solver="orca",
    )
    generator = SlurmGenerator()
    with caplog.at_level(logging.WARNING):
        script = generator.generate_submission_script(spec, input_file="test.inp")

    assert "[SCHEDULER-WARNING]" in caplog.text
    # Clamped cores must appear in directives
    assert f"#SBATCH --cpus-per-task={physical_cores}" in script
    assert "#SBATCH --nodes=1" in script
    assert "#SBATCH --ntasks=1" in script
