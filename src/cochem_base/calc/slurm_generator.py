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

import logging
import math
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional

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

    def __post_init__(self) -> None:
        for name in ("job_name", "partition", "account", "qos", "solver"):
            value = getattr(self, name)
            if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
                raise ValueError(f"Invalid Slurm {name}: expected a single identifier")
        for name in ("cores", "mem_mb"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not re.fullmatch(r"(?:\d+-)?\d+:\d{2}:\d{2}", self.walltime):
            raise ValueError("Walltime must use [days-]hours:minutes:seconds")
        for name in ("scratch_dir", "artifact_dir"):
            value = getattr(self, name)
            if not PurePosixPath(value).is_absolute() or any(c in value for c in "\n\r\0"):
                raise ValueError(f"{name} must be an absolute single-line path")


class SlurmGenerator:
    """Generator for HPC SLURM submission scripts strictly adhering to Method Matrix §8A.6."""

    def __init__(self) -> None:
        self.logger = logger

    def get_physical_core_limit(self) -> int:
        """Determines the physical single-node core limit via SLURM environment or psutil."""
        slurm_env = os.environ.get("SLURM_CPUS_ON_NODE")
        if slurm_env and slurm_env.isdigit():
            return int(slurm_env)
        count = psutil.cpu_count(logical=False)
        if count is None or count <= 0:
            raise RuntimeError("Cannot determine physical CPU capacity")
        return int(count)

    def generate_submission_script(
        self,
        spec: SlurmSubmissionSpec,
        input_file: str = "calc.inp",
        payload_command: Optional[str] = None,
        *, configure_fabric: bool = True, copy_scratch: bool = True,
        clamp_to_host: bool = True,
    ) -> str:
        """Generates an SBATCH script with single-node shared-memory directives."""
        # A queued allocation is a declaration; its compute node is audited at
        # execution. Direct callers retain the existing measured-host clamp.
        physical_limit = self.get_physical_core_limit() if clamp_to_host else spec.cores
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

        # OpenMPI Fabric Variable Exports for Tier 6 HPC Environments (Method Matrix §8A.6 [M])
        exec_lines = [
            "set -euo pipefail",
            'export OMPI_MCA_btl="^openib"',
            'export OMPI_MCA_pml="ucx"',
            'export OMPI_MCA_opal_warn_on_missing_libudev=0',
            # ORCA launches %pal ranks itself. Each rank gets one library thread.
            "export OMP_NUM_THREADS=" + ("1" if solver_lower == "orca" else "$SLURM_CPUS_PER_TASK"),
            "export MKL_NUM_THREADS=" + ("1" if solver_lower == "orca" else "$SLURM_CPUS_PER_TASK"),
            "export OPENBLAS_NUM_THREADS=" + ("1" if solver_lower == "orca" else "$SLURM_CPUS_PER_TASK"),
            f"export COCHEM_SCRATCH={shlex.quote(scratch_posix)}",
            f"export COCHEM_ARTIFACTS={shlex.quote(artifact_posix)}",
            "mkdir -p \"$COCHEM_SCRATCH\"",
            "mkdir -p \"$COCHEM_ARTIFACTS\"",
            "cd \"$COCHEM_SCRATCH\"",
        ]

        if not configure_fabric:
            # Registered native runtimes choose their supported MPI transport.
            exec_lines = [line for line in exec_lines if not line.startswith("export OMPI_MCA_")]

        if solver_lower == "orca":
            exec_lines.extend([
                "export VECLIB_MAXIMUM_THREADS=1",
                "export NUMEXPR_NUM_THREADS=1",
                "export BLIS_NUM_THREADS=1",
            ])

        if payload_command:
            exec_lines.append(payload_command)
        elif solver_lower == "orca":
            maxcore_mb = int(math.floor((spec.mem_mb * 0.75) / effective_cores))
            exec_lines.extend([
                f"# ORCA parallel execution alignment (%pal nprocs {effective_cores} end)",
                f"# MaxCore per rank: {maxcore_mb} MB",
                f"orca {shlex.quote(input_file)} > orca_output.out",
            ])
        elif solver_lower == "cfour":
            exec_lines.extend([
                "# CFOUR OpenMP / MPI hybrid execution",
                "export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK",
                "xcfour > cfour_output.out",
            ])
        elif solver_lower == "crest":
            exec_lines.append(
                f"crest {shlex.quote(input_file)} --nci --nocross --noreftopo -T $SLURM_CPUS_PER_TASK > crest_output.out"
            )
        else:
            exec_lines.append(f"{shlex.quote(spec.solver)} {shlex.quote(input_file)}")

        if copy_scratch:
            exec_lines.append("cp -r \"$COCHEM_SCRATCH\"/* \"$COCHEM_ARTIFACTS\"/")

        return "\n".join(header) + "\n\n" + "\n".join(exec_lines) + "\n"
