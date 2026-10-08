"""Core AsyncProcessRunner integrating CUDA budgeting, Slurm preflight, and MPI supervision.

Enforces Tripartite Air-Gapped Storage ($COCH_SRC, $COCH_ARTIFACTS, $COCH_SCRATCH)
and concurrency-safe Single-Writer Multiple-Reader (SWMR) HDF5 telemetry.
"""

import os
import math
import re
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import filelock
import h5py

from cochem.hpc.models import (
    MpiClusterExecutionConfig,
    SlurmDryRunResult,
    SlurmJobDirectiveSpec,
    SlurmResourceValidationError,
)
from cochem.hpc.slurm_generator import SlurmDryRunGenerator
from cochem.runners.cuda_budget import CudaMemoryManager
from cochem.runners.mpi_supervisor import MpiProcessSupervisor


class AsyncProcessRunner:
    """Orchestrates high-performance computational workflows across heterogeneous cluster resources."""

    def __init__(
        self,
        src_dir: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
        scratch_dir: Optional[Path] = None,
        cuda_manager: Optional[CudaMemoryManager] = None,
        slurm_generator: Optional[SlurmDryRunGenerator] = None,
        mpi_supervisor: Optional[MpiProcessSupervisor] = None,
    ) -> None:
        src_env = os.environ.get("COCH_SRC")
        self.src_dir = Path(
            src_dir if src_dir is not None else (src_env if src_env is not None else Path.cwd() / "src")
        ).resolve()

        art_env = os.environ.get("COCH_ARTIFACTS")
        self.artifacts_dir = Path(
            artifacts_dir
            if artifacts_dir is not None
            else (art_env if art_env is not None else Path.cwd() / "artifacts")
        ).resolve()

        scratch_env = os.environ.get("COCH_SCRATCH")
        slurm_env = os.environ.get("SLURM_TMPDIR")
        fallback_scratch = (
            scratch_env if scratch_env is not None else (slurm_env if slurm_env is not None else Path.cwd() / "scratch")
        )
        self.scratch_dir = Path(
            scratch_dir if scratch_dir is not None else fallback_scratch
        ).resolve()

        roots = (self.src_dir, self.artifacts_dir, self.scratch_dir)
        for index, left in enumerate(roots):
            for right in roots[index + 1:]:
                if left.is_relative_to(right) or right.is_relative_to(left):
                    raise PermissionError("Tripartite source, artifacts and scratch roots must not overlap")

        self.cuda_manager = cuda_manager or CudaMemoryManager()
        self.slurm_generator = slurm_generator or SlurmDryRunGenerator()
        self.mpi_supervisor = mpi_supervisor or MpiProcessSupervisor()

        self.telemetry_lock_path = self.scratch_dir / ".telemetry.lock"
        self._active_writers: Dict[str, h5py.File] = {}
        self._owned_scratch: set[Path] = set()

        # Ensure write destinations exist
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def validate_write_path(self, target_path: Path) -> None:
        """Enforce Tripartite architecture: strictly forbid writing into read-only $COCH_SRC."""
        resolved = target_path.resolve()
        try:
            resolved.relative_to(self.src_dir)
            is_in_src = True
        except ValueError:
            is_in_src = False

        if is_in_src or resolved == self.src_dir:
            raise PermissionError(
                f"Tripartite storage violation: Cannot write to read-only source directory ($COCH_SRC): '{resolved}'."
            )

    def init_telemetry(self, telemetry_file: Path) -> None:
        """Initialize resizable datasets for Single-Writer Multiple-Reader (SWMR) HDF5 telemetry."""
        self.validate_write_path(telemetry_file)
        telemetry_file.parent.mkdir(parents=True, exist_ok=True)

        resolved_key = str(telemetry_file.resolve())
        with filelock.FileLock(str(self.telemetry_lock_path), timeout=30.0):
            h5_file = h5py.File(telemetry_file, "x", libver="latest")
            grp = h5_file.create_group("telemetry")
            grp.create_dataset(
                "step",
                shape=(0,),
                maxshape=(None,),
                dtype="int64",
                chunks=True,
            )
            grp.create_dataset(
                "energy",
                shape=(0,),
                maxshape=(None,),
                dtype="float64",
                chunks=True,
            )
            grp.create_dataset(
                "walltime",
                shape=(0,),
                maxshape=(None,),
                dtype="float64",
                chunks=True,
            )
            grp.create_dataset("energy_available", shape=(0,), maxshape=(None,), dtype="bool", chunks=True)
            grp.attrs["energy_unit"] = "hartree"
            grp.attrs["unmeasured_energy_representation"] = "NaN with energy_available=False"
            h5_file.swmr_mode = True
            h5_file.flush()
            self._active_writers[resolved_key] = h5_file

    def close_telemetry(self, telemetry_file: Path) -> None:
        """Explicitly flush and close an active SWMR HDF5 telemetry file handle."""
        resolved_key = str(telemetry_file.resolve())
        h5_file = self._active_writers.pop(resolved_key, None)
        if h5_file is not None and h5_file.id.valid:
            h5_file.flush()
            h5_file.close()

    def close(self) -> None:
        """Flush and close all open SWMR telemetry writer handles."""
        keys = list(self._active_writers.keys())
        for key in keys:
            h5_file = self._active_writers.pop(key, None)
            if h5_file is not None and h5_file.id.valid:
                h5_file.flush()
                h5_file.close()

    def __enter__(self) -> "AsyncProcessRunner":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
        self.cleanup_scratch()

    def cleanup_scratch(self, task_name: Optional[str] = None) -> None:
        """Clean up ephemeral per-job scratch directory or entire scratch root safely."""
        if task_name is not None:
            self._validate_task_name(task_name)
            selected = [self.scratch_dir / task_name]
        else:
            selected = list(self._owned_scratch)
        for path in selected:
            if path not in self._owned_scratch:
                continue
            # A changed symlink must never redirect cleanup into another job.
            if path.is_symlink() or path.resolve().parent != self.scratch_dir:
                raise PermissionError("Owned job scratch identity changed before cleanup")
            if path.exists():
                shutil.rmtree(path)
            self._owned_scratch.discard(path)

    @staticmethod
    def _validate_task_name(task_name: str) -> None:
        if not isinstance(task_name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", task_name) is None:
            raise ValueError("A bounded filesystem-safe task identifier is required")

    def record_telemetry_metric(
        self,
        telemetry_file: Path,
        step: int,
        energy: float | None,
        walltime: float,
    ) -> None:
        """Thread and process-safely record telemetry progress metric to SWMR HDF5."""
        self.validate_write_path(telemetry_file)
        if energy is not None and (isinstance(energy, bool) or not math.isfinite(float(energy))):
            raise ValueError("A measured telemetry energy must be a finite Hartree value")
        if not math.isfinite(walltime) or walltime < 0:
            raise ValueError("Telemetry walltime must be finite and nonnegative")
        resolved_key = str(telemetry_file.resolve())

        with filelock.FileLock(str(self.telemetry_lock_path), timeout=30.0):
            active_handle = self._active_writers.get(resolved_key)
            if active_handle is not None and active_handle.id.valid:
                step_ds = active_handle["telemetry/step"]
                energy_ds = active_handle["telemetry/energy"]
                walltime_ds = active_handle["telemetry/walltime"]
                energy_available_ds = active_handle["telemetry/energy_available"]

                current_len = step_ds.shape[0]
                new_len = current_len + 1

                step_ds.resize((new_len,))
                energy_ds.resize((new_len,))
                walltime_ds.resize((new_len,))
                energy_available_ds.resize((new_len,))

                step_ds[current_len] = step
                energy_ds[current_len] = float("nan") if energy is None else energy
                energy_available_ds[current_len] = energy is not None
                walltime_ds[current_len] = walltime

                step_ds.flush()
                energy_ds.flush()
                walltime_ds.flush()
                energy_available_ds.flush()
                active_handle.flush()
            else:
                with h5py.File(telemetry_file, "a", libver="latest") as h5_file:
                    h5_file.swmr_mode = True
                    step_ds = h5_file["telemetry/step"]
                    energy_ds = h5_file["telemetry/energy"]
                    walltime_ds = h5_file["telemetry/walltime"]
                    energy_available_ds = h5_file["telemetry/energy_available"]

                    current_len = step_ds.shape[0]
                    new_len = current_len + 1

                    step_ds.resize((new_len,))
                    energy_ds.resize((new_len,))
                    walltime_ds.resize((new_len,))
                    energy_available_ds.resize((new_len,))

                    step_ds[current_len] = step
                    energy_ds[current_len] = float("nan") if energy is None else energy
                    energy_available_ds[current_len] = energy is not None
                    walltime_ds[current_len] = walltime

                    step_ds.flush()
                    energy_ds.flush()
                    walltime_ds.flush()
                    energy_available_ds.flush()
                    h5_file.flush()

    async def dispatch_task(
        self,
        task_name: str,
        binary_args: List[str],
        gpu_required_mb: Optional[int] = None,
        device_id: Optional[int] = None,
        slurm_spec: Optional[SlurmJobDirectiveSpec] = None,
        partition_limits: Optional[Dict[str, Any]] = None,
        mpi_config: Optional[MpiClusterExecutionConfig] = None,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        telemetry_callback: Optional[Callable[[str], None]] = None,
        rank_trace_callback: Optional[Callable[[str], None]] = None,
        cleanup_on_completion: bool = True,
    ) -> Dict[str, Any]:
        """Dispatch a high-performance computation task adhering to tripartite and cluster invariants."""
        # Never redirect or overwrite an earlier job's retained directory.
        self._validate_task_name(task_name)
        job_scratch = self.scratch_dir / task_name
        self.validate_write_path(job_scratch)
        job_scratch.mkdir(parents=False, exist_ok=False)
        self._owned_scratch.add(job_scratch)
        execution_cwd = cwd or job_scratch

        # Prepare environment with Tripartite storage locations
        run_env = dict(os.environ) if env is None else dict(env)
        run_env["COCH_SRC"] = str(self.src_dir)
        run_env["COCH_ARTIFACTS"] = str(self.artifacts_dir)
        run_env["COCH_SCRATCH"] = str(job_scratch)
        run_env["SLURM_TMPDIR"] = str(job_scratch)

        # 1. GPU VRAM Budgeting & Environment Isolation
        if gpu_required_mb is not None and gpu_required_mb > 0:
            assigned_dev = await self.cuda_manager.schedule_gpu_task(
                required_mb=gpu_required_mb,
                requested_device_id=device_id,
            )
            run_env = self.cuda_manager.prepare_worker_environment(
                device_id=assigned_dev,
                base_env=run_env,
            )

        # 2. Slurm Preflight Validation
        slurm_result: Optional[SlurmDryRunResult] = None
        if slurm_spec is not None:
            slurm_result = self.slurm_generator.generate_sbatch_script(
                spec=slurm_spec,
                partition_limits=partition_limits,
            )
            if not slurm_result.is_valid:
                error_summary = "; ".join(slurm_result.validation_errors)
                raise SlurmResourceValidationError(
                    f"Slurm preflight validation failed for task '{task_name}': {error_summary}"
                )

        # 3. Initialize SWMR HDF5 Telemetry
        telemetry_file = job_scratch / f"{task_name}_telemetry.h5"
        self.init_telemetry(telemetry_file)

        # 4. Supervise Process Execution
        start_time = time.monotonic()
        if mpi_config is not None:
            config_with_env = mpi_config.model_copy(
                update={"environment_vars": {**mpi_config.environment_vars, **run_env}}
            )
            exec_result = await self.mpi_supervisor.run_mpi_task(
                config=config_with_env,
                binary_args=binary_args,
                cwd=execution_cwd,
                telemetry_callback=telemetry_callback,
                rank_trace_callback=rank_trace_callback,
            )
        else:
            exec_result = await self.mpi_supervisor.run_command(
                command=binary_args,
                cwd=execution_cwd,
                env=run_env,
                telemetry_callback=telemetry_callback,
                rank_trace_callback=rank_trace_callback,
            )

        elapsed = time.monotonic() - start_time

        # 5. Record Completion Metric to Telemetry
        self.record_telemetry_metric(
            telemetry_file=telemetry_file,
            step=1,
            energy=None,
            walltime=elapsed,
        )
        self.close_telemetry(telemetry_file)

        if cleanup_on_completion:
            self.cleanup_scratch(task_name=task_name)

        return {
            "task_name": task_name,
            "exit_code": exec_result["exit_code"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "telemetry_file": str(telemetry_file),
            "scratch_dir": str(job_scratch),
            "artifacts_dir": str(self.artifacts_dir),
            "slurm_result": slurm_result,
            "elapsed_seconds": elapsed,
        }
