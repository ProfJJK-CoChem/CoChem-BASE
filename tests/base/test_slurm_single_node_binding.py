# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 1: Single-Node SLURM Core Binding & OpenMPI Fabric Variable Export.
Adheres strictly to Method Matrix §8A.6 [M] and Zero-Mock Mandate.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import shlex
import subprocess
import sys

import pytest

from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec


def test_slurm_single_node_core_binding_and_openmpi_exports(tmp_path: Path) -> None:
    """
    Instantiate SLURM template generator with multi-core configuration (cores=16).
    Assert generated script contains:
      #SBATCH --nodes=1
      #SBATCH --ntasks=1
      #SBATCH --cpus-per-task=min(16, measured physical cores)
    and verifies presence of OpenMPI fabric variable exports.
    """
    generator = SlurmGenerator()
    spec = SlurmSubmissionSpec(
        job_name="test_orca_job",
        partition="standard",
        cores=16,
        mem_mb=32768,
        walltime="12:00:00",
        scratch_dir=str(tmp_path / "scratch"),
        artifact_dir=str(tmp_path / "artifacts"),
        solver="orca",
    )

    script = generator.generate_submission_script(spec, input_file="calc.inp")

    # Verify single-node shared-memory directives
    assert "#SBATCH --nodes=1" in script
    assert "#SBATCH --ntasks=1" in script
    effective_cores = min(16, generator.get_physical_core_limit())
    assert f"#SBATCH --cpus-per-task={effective_cores}" in script
    assert f"# MaxCore per rank: {int(32768 * 0.75 / effective_cores)} MB" in script
    assert "#SBATCH --ntasks=16" not in script

    # Verify OpenMPI fabric exports for Tier 6 HPC environments
    assert 'export OMPI_MCA_btl="^openib"' in script
    assert 'export OMPI_MCA_pml="ucx"' in script
    assert 'export OMPI_MCA_opal_warn_on_missing_libudev=0' in script


@pytest.mark.parametrize("solver", ["orca", "cfour"])
def test_generated_slurm_runtime_obeys_engine_thread_budget(tmp_path: Path, solver: str) -> None:
    """Execute generated Bash with a real environment probe, without chemistry."""
    variables = ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]
    if solver == "orca":
        variables += ["VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"]
    generator = SlurmGenerator()
    cores = min(2, generator.get_physical_core_limit())
    spec = SlurmSubmissionSpec(job_name="thread_budget", solver=solver, cores=cores,
                               scratch_dir=str(tmp_path / "scratch"), artifact_dir=str(tmp_path / "results"))
    probe = "import json,os,pathlib,sys; pathlib.Path('environment.json').write_text(json.dumps({k:os.environ[k] for k in sys.argv[1:]}))"
    command = shlex.join([sys.executable, "-I", "-c", probe, *variables])
    script = generator.generate_submission_script(spec, payload_command=command)
    environment = {**os.environ, **dict.fromkeys(variables, "64"), "SLURM_CPUS_PER_TASK": str(cores)}
    completed = subprocess.run(["bash"], input=script, text=True, env=environment,
                               capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    observed = json.loads((tmp_path / "results" / "environment.json").read_text())
    assert observed == dict.fromkeys(variables, "1" if solver == "orca" else str(cores))
