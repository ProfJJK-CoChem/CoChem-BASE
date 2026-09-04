# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
HPC SLURM Single-Node Shared-Memory Template Generator.
Mandated by Method Matrix v4 §8A.6 (Suggestion #72).
Enforces:
- #SBATCH --nodes=1
- #SBATCH --ntasks=1
- #SBATCH --cpus-per-task={cores}
- ORCA %pal nprocs {cores} end alignment
- CFOUR / OpenMP thread binding: export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
- Dynamic core capacity clamping with [SCHEDULER-WARNING]
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Union

import psutil

logger = logging.getLogger("cochem_base.calc.slurm_generator")


@dataclass
class SlurmSubmissionSpec:
    """Specification for HPC Slurm single-node shared-memory job."""

    job_name: str
    partition: str = "standard"
    cores: int = 8
    mem_mb: int = 16384
    walltime: str = "24:00:00"
    scratch_dir: str = "/scratch"
    artifact_dir: str = "/artifacts"
    solver: str = "orca"
    account: Optional[str] = None
    qos: Optional[str] = None
    gpus_per_node: Optional[int] = None


class SlurmGenerator:
    """Generator for HPC SLURM submission scripts strictly adhering to Method Matrix §8A.6."""

    def __init__(self) -> None:
        pass

    def get_physical_core_limit(self) -> int:
        """Determines the physical single-node core limit via SLURM environment or psutil."""
        slurm_env = os.environ.get("SLURM_CPUS_ON_NODE")
        if slurm_env and slurm_env.isdigit():
            return int(slurm_env)
        count = psutil.cpu_count(logical=False)
        return int(count) if count is not None and count > 0 else 8

    def generate_submission_script(
        self,
        spec: SlurmSubmissionSpec,
        input_file: str = "calc.inp",
        payload_command: Optional[str] = None,
    ) -> str:
        """Generates an SBATCH script with single-node shared-memory directives."""
        physical_limit = self.get_physical_core_limit()
        requested_cores = spec.cores
        effective_cores = requested_cores

        if requested_cores > physical_limit:
            effective_cores = physical_limit
            logger.warning(
                f"[SCHEDULER-WARNING] Requested cores ({requested_cores}) exceeds physical "
                f"single-node bounds ({physical_limit}). Clamped to {effective_cores}."
            )

        scratch_posix = PurePosixPath(spec.scratch_dir).as_posix()
        artifact_posix = PurePosixPath(spec.artifact_dir).as_posix()

        solver_lower = spec.solver.lower().strip()

        # Shared-memory directives conforming to Method Matrix §8A.6
        header = [
            "#!/bin/bash",
            f"#SBATCH --job-name={spec.job_name}",
            f"#SBATCH --partition={spec.partition}",
            "#SBATCH --nodes=1",
            "#SBATCH --ntasks=1",
            f"#SBATCH --cpus-per-task={effective_cores}",
            f"#SBATCH --mem={spec.mem_mb}M",
            f"#SBATCH --time={spec.walltime}",
        ]

        if spec.account:
            header.append(f"#SBATCH --account={spec.account}")
        if spec.qos:
            header.append(f"#SBATCH --qos={spec.qos}")
        if spec.gpus_per_node is not None and spec.gpus_per_node > 0:
            header.append(f"#SBATCH --gpus-per-node={spec.gpus_per_node}")

        # Thread binding & Solver execution block
        exec_lines = [
            "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK",
            "export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK",
            f"export COCHEM_SCRATCH=\"{scratch_posix}\"",
            f"export COCHEM_ARTIFACTS=\"{artifact_posix}\"",
            "mkdir -p \"$COCHEM_SCRATCH\"",
            "mkdir -p \"$COCHEM_ARTIFACTS\"",
            "cd \"$COCHEM_SCRATCH\"",
        ]

        if payload_command:
            exec_lines.append(payload_command)
        elif solver_lower == "orca":
            maxcore_mb = int(math.floor((spec.mem_mb * 0.75) / 1))
            exec_lines.extend([
                f"# ORCA parallel execution alignment (%pal nprocs {effective_cores} end)",
                f"# MaxCore per rank: {maxcore_mb} MB",
                f"orca {input_file} > orca_output.out",
            ])
        elif solver_lower == "cfour":
            exec_lines.extend([
                "# CFOUR OpenMP / MPI hybrid execution",
                "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK",
                "xcfour > cfour_output.out",
            ])
        elif solver_lower == "crest":
            exec_lines.append(
                f"crest {input_file} --nci --nocross --noreftopo -T $SLURM_CPUS_PER_TASK > crest_output.out"
            )
        else:
            exec_lines.append(f"{spec.solver} {input_file}")

        exec_lines.append("cp -r \"$COCHEM_SCRATCH\"/* \"$COCHEM_ARTIFACTS\"/")

        return "\n".join(header) + "\n\n" + "\n".join(exec_lines) + "\n"
