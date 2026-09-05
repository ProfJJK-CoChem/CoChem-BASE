# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Test Deliverable 1: Single-Node SLURM Core Binding & OpenMPI Fabric Variable Export.
Adheres strictly to Method Matrix §8A.6 [M] and Zero-Mock Mandate.
"""

from __future__ import annotations

from pathlib import Path

from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec


def test_slurm_single_node_core_binding_and_openmpi_exports(tmp_path: Path) -> None:
    """
    Instantiate SLURM template generator with multi-core configuration (cores=16).
    Assert generated script contains:
      #SBATCH --nodes=1
      #SBATCH --ntasks=1
      #SBATCH --cpus-per-task=16
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
    assert "#SBATCH --cpus-per-task=16" in script
    assert "#SBATCH --ntasks=16" not in script

    # Verify OpenMPI fabric exports for Tier 6 HPC environments
    assert 'export OMPI_MCA_btl="^openib"' in script
    assert 'export OMPI_MCA_pml="ucx"' in script
    assert 'export OMPI_MCA_opal_warn_on_missing_libudev=0' in script
