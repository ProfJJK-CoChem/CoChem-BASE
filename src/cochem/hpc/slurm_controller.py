"""Compatibility exports for the canonical validated BASE Slurm controller."""
from cochem_base.calc.slurm_submission import (
    SlurmSubmissionController, generate_slurm_script, memory_megabytes,
    sanitize_slurm_parameter, submit_slurm_job, validate_slurm_walltime,
)

__all__ = ["SlurmSubmissionController", "generate_slurm_script", "memory_megabytes",
           "sanitize_slurm_parameter", "submit_slurm_job", "validate_slurm_walltime"]
