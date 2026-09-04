# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Core Execution Router for the CoChem pipeline.
Mandated by Method Matrix v4 §8A.6 (Parsl Multi-Executor Architecture) and §8A.2 (Scout-and-Anchor Topology) [M].
Validates Suggestion #66:
- Elimination of bypassed execution paths by integrating ParslExecutionBroker.
- Workload mapping: heavy QM -> cochem_anchor_cpu with CPU core pinning and OpenMP binding.
- Rapid scans / MLFF -> cochem_scout_gpu.
- Task sandboxing in Ring 2 ephemeral scratch ($COCHEM_SCRATCH/task_<uuid>/).
- Pydantic v2 JobRouteConfig and ExecutionRouteResult contracts.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem_base.config_loader import (
    load_system_config_dict,
    resolve_config_path,
    resolve_executable,
)
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig

logger = logging.getLogger(__name__)

try:
    import parsl
    from parsl import python_app
    HAS_PARSL = True
except ImportError:
    HAS_PARSL = False
    parsl = None  # type: ignore


class ExecutionRouter:
    """
    Unified Execution Router for the CoChem pipeline.
    Routes computational jobs to Parsl multi-executor topologies (cochem_anchor_cpu, cochem_scout_gpu)
    or remote HPC schedulers (sbatch) with isolated scratch sandboxes.
    """

    def __init__(
        self,
        registry_path: Optional[Union[str, Path]] = None,
        broker: Optional[Any] = None,
        dfk: Optional[Any] = None,
    ) -> None:
        """Initializes the router with Golden Registry and optional Parsl broker/DFK."""
        if registry_path:
            self.registry_path = resolve_config_path(Path(registry_path))
        else:
            self.registry_path = resolve_config_path()

        self.registry = self._load_registry()
        self.broker = broker
        self.dfk = dfk

    def _load_registry(self) -> Dict[str, Any]:
        """Reads the hardware and routing rules."""
        try:
            return load_system_config_dict(self.registry_path)
        except Exception as e:
            logger.error(f"Failed to parse registry at {self.registry_path}: {e}. Defaulting to safe fallback.")
            return {"execution": {"default_engine": "subprocess"}, "engines": {}}

    def resolve_execution_path(self, target_engine: str) -> str:
        """Determines the path for the incoming computational payload."""
        exec_config = self.registry.get("execution") or {}
        engines_config = self.registry.get("engines") or {}

        default_path = exec_config.get("default_engine", "subprocess")

        if target_engine in engines_config:
            engine_info = engines_config[target_engine]
            engine_status = (
                engine_info.get("status", "unknown")
                if isinstance(engine_info, dict)
                else getattr(engine_info, "status", "unknown")
            )
            if engine_status not in ("ready", "found"):
                logger.warning(f"Engine '{target_engine}' status is '{engine_status}'. Proceeding with caution.")
        else:
            logger.warning(f"Engine '{target_engine}' not found in registry. Using default path.")

        return str(default_path)

    def route_job(
        self,
        target_engine_or_type: Optional[str] = None,
        payload_command: Optional[Union[str, List[str]]] = None,
        cwd: Optional[Union[str, Path]] = None,
        *,
        job_type: Optional[str] = None,
        route_config: Optional[JobRouteConfig] = None,
        cpu_core_pinning: Optional[List[int]] = None,
        scratch_dir: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 3600.0,
        job_name: str = "cochem_job",
        **kwargs: Any,
    ) -> ExecutionRouteResult:
        """
        Primary execution dispatch entrypoint conforming to Method Matrix §8A.2, §8A.6.
        Dispatches computational jobs to Parsl heterogeneous pools with sandbox isolation.
        """
        # Determine job type
        effective_job_type = job_type
        if effective_job_type is None and target_engine_or_type is not None:
            if target_engine_or_type in ("heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"):
                effective_job_type = target_engine_or_type
            elif "scan" in target_engine_or_type.lower() or "scout" in target_engine_or_type.lower() or "mlff" in target_engine_or_type.lower():
                effective_job_type = "fast_potential_scan"
            elif "opt" in target_engine_or_type.lower() or "heavy" in target_engine_or_type.lower() or "orca" in target_engine_or_type.lower():
                effective_job_type = "heavy_qm_opt"
            elif "freq" in target_engine_or_type.lower() or "hess" in target_engine_or_type.lower():
                effective_job_type = "frequency"
            else:
                effective_job_type = "single_point"
        elif effective_job_type is None:
            effective_job_type = "heavy_qm_opt"

        # Determine scratch root
        scratch_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_dir or cwd or scratch_env or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Build JobRouteConfig if not explicitly supplied
        if route_config is None:
            if effective_job_type in ("heavy_qm_opt", "frequency"):
                assigned_exec = "cochem_anchor_cpu"
            elif effective_job_type in ("fast_potential_scan",):
                assigned_exec = "cochem_scout_gpu"
            else:
                assigned_exec = "cochem_anchor_cpu"

            route_config = JobRouteConfig(
                job_type=effective_job_type,  # type: ignore
                assigned_executor=assigned_exec,  # type: ignore
                cpu_core_pinning=cpu_core_pinning,
                scratch_dir=str(task_scratch),
                timeout_seconds=timeout,
            )

        # Environment configuration and CPU core pinning
        task_env = os.environ.copy()
        if env:
            task_env.update(env)

        if route_config.assigned_executor == "cochem_anchor_cpu":
            if route_config.cpu_core_pinning:
                pins = ",".join(str(p) for p in route_config.cpu_core_pinning)
                task_env["KMP_AFFINITY"] = f"explicit,proclist=[{pins}],granularity=fine"
                task_env["OMP_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
                task_env["MKL_NUM_THREADS"] = str(len(route_config.cpu_core_pinning))
            else:
                task_env.setdefault("OMP_NUM_THREADS", "1")

        # Command determination
        cmd = payload_command or kwargs.get("command") or [sys.executable, "-c", "print('cochem-task-complete')"]

        # Check if active Parsl DFK exists
        active_dfk = self.dfk
        if active_dfk is None and self.broker is not None and hasattr(self.broker, "get_dfk"):
            active_dfk = self.broker.get_dfk()
        if active_dfk is None and HAS_PARSL:
            try:
                active_dfk = parsl.dfk()
            except Exception:
                active_dfk = None

        if active_dfk is not None:
            executors_in_dfk = list(active_dfk.executors.keys())
            target_executor = route_config.assigned_executor
            if target_executor not in executors_in_dfk and len(executors_in_dfk) > 0:
                logger.warning(
                    f"Executor '{target_executor}' not found in Parsl DFK executors {executors_in_dfk}. Routing to '{executors_in_dfk[0]}'"
                )
                target_executor = executors_in_dfk[0]

            @python_app(executors=[target_executor])
            def _parsl_task_runner(cmd_to_run: Union[str, List[str]], work_dir: str, env_vars: Dict[str, str], t_sec: float) -> int:
                from cochem.concurrency.subprocess_broker import SubprocessBroker
                b = SubprocessBroker(cwd=work_dir, env=env_vars, timeout_seconds=t_sec)
                r = b.execute(cmd_to_run)
                return r.returncode

            future = _parsl_task_runner(cmd, str(task_scratch), task_env, route_config.timeout_seconds)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="SUBMITTED",
                returncode=0,
                future=future,
                output=None,
            )
        else:
            # Fallback to direct SubprocessBroker execution in scratch sandbox
            broker = SubprocessBroker(cwd=task_scratch, env=task_env, timeout_seconds=route_config.timeout_seconds)
            res = broker.execute(cmd)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor=route_config.assigned_executor,
                scratch_dir=task_scratch,
                status="COMPLETED" if res.success else "FAILED",
                returncode=res.returncode,
                future=None,
                output=res.stdout,
            )

    def _dispatch_local(
        self,
        payload_command: Union[str, List[str]],
        cwd: Union[str, Path],
        env: Optional[Dict[str, str]] = None,
        timeout: float = 300.0,
    ) -> int:
        """Deliverable 3 (Suggestion #73): Structured Local Dispatch & Tripartite Air-Gap Isolation.

        Eliminates shell=True, parses structured argument lists via shlex.split,
        routes execution through SubprocessBroker with stream redirection in Ring 2 scratch,
        and enforces Tripartite air-gap boundary rules.
        """
        import shlex
        import shutil

        # Tripartite Air-Gap Resolution (Ring 2 Scratch)
        scratch_root_env = (
            os.environ.get("COCHEM_SCRATCH")
            or os.environ.get("SLURM_TMPDIR")
            or os.environ.get("TEMP")
        )
        base_scratch = Path(scratch_root_env or cwd or tempfile.gettempdir()).resolve()
        base_scratch.mkdir(parents=True, exist_ok=True)

        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir(parents=True, exist_ok=True)

        # Parse command into structured arguments without shell=True
        posix_mode = (sys.platform != "win32")
        if isinstance(payload_command, str):
            cmd_args = shlex.split(payload_command, posix=posix_mode)
            if not posix_mode:
                cmd_args = [
                    a[1:-1] if (len(a) >= 2 and a.startswith('"') and a.endswith('"')) else a
                    for a in cmd_args
                ]
        else:
            cmd_args = list(payload_command)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        # Stream isolation: stdout and stderr directed to explicit streams in Ring 2 scratch
        stdout_path = task_scratch / f"task_{task_id}.out"
        stderr_path = task_scratch / f"task_{task_id}.err"
        flat_stdout = base_scratch / f"task_{task_id}.out"

        try:
            with open(stdout_path, "w", encoding="utf-8") as out_f, open(stderr_path, "w", encoding="utf-8") as err_f:
                proc = subprocess.run(
                    cmd_args,
                    shell=False,
                    cwd=str(task_scratch),
                    env=merged_env,
                    stdout=out_f,
                    stderr=err_f,
                    timeout=timeout,
                    check=False,
                )
                try:
                    if stdout_path.exists():
                        shutil.copy2(stdout_path, flat_stdout)
                except Exception:
                    pass
                return proc.returncode
        except subprocess.TimeoutExpired:
            logger.error(f"Local dispatch timed out after {timeout}s: {cmd_args}")
            return -124
        except Exception as e:
            logger.error(f"Local dispatch failed: {e}")
            return -1

    def _dispatch_hpc(
        self,
        payload_command: str,
        job_name: str,
        cwd: str,
        cores: int = 4,
        mem_mb: int = 8192,
        wall_time: str = "24:00:00",
    ) -> str:
        """Stage 1.2: HPC Dispatch conforming to Method Matrix §8A.6 (Suggestion #72).

        Single-Node Shared-Memory Template Generation without #SBATCH --ntasks={cores}.
        """
        from cochem_base.calc.slurm_generator import SlurmGenerator, SlurmSubmissionSpec

        spec = SlurmSubmissionSpec(
            job_name=job_name,
            partition="standard",
            cores=cores,
            mem_mb=mem_mb,
            walltime=wall_time,
            scratch_dir=str(cwd),
            artifact_dir=str(cwd),
            solver="orca",
        )
        generator = SlurmGenerator()
        rendered_script = generator.generate_submission_script(
            spec,
            payload_command=payload_command,
        )

        target_sbatch = Path(cwd) / f"{job_name}_submit.sbatch"
        sbatch = resolve_executable(env_var="SBATCH_CMD", candidates=("sbatch",))
        try:
            target_sbatch.write_text(rendered_script, encoding="utf-8")
            logger.info(f"Generated SLURM script: {target_sbatch}")
            result = subprocess.run([sbatch, str(target_sbatch)], capture_output=True, text=True, cwd=cwd, timeout=60.0, check=True)
            stdout = result.stdout.strip() if result.stdout else ""
            parts = stdout.split()
            return parts[-1] if parts else "UNKNOWN_ID"
        except FileNotFoundError:
            logger.error("'sbatch' command not found. Are you on an HPC cluster?")
            return "HPC_NOT_AVAILABLE"
        except Exception as e:
            logger.error(f"SLURM submission failed: {e}")
            return "SUBMISSION_FAILED"

    def evaluate_counterpoise_interaction(
        self,
        e_ab: float,
        e_a_ghost: float,
        e_b_ghost: float,
    ) -> float:
        """
        Evaluates decoupled Boys-Bernardi interaction energy via compute_counterpoise_interaction_energy:
            E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
        """
        return compute_counterpoise_interaction_energy(e_ab, e_a_ghost, e_b_ghost)


def compute_counterpoise_interaction_energy(
    e_ab: float,
    e_a_ghost: float,
    e_b_ghost: float,
) -> float:
    """
    Computes decoupled Boys-Bernardi counterpoise-corrected interaction energy
    under Method Matrix v4 §9A.1-9A.2 (Suggestion #81):
        E_int^CP = E_AB^{AB} - E_A^{AB} - E_B^{AB}
    where E_AB^{AB} is complex energy, E_A^{AB} is monomer A with ghost B,
    and E_B^{AB} is monomer B with ghost A.
    """
    return float(e_ab - e_a_ghost - e_b_ghost)


def validate_counterpoise_request(
    is_opt: bool,
    has_frozen_constraints: bool,
    is_complex: bool = True,
) -> None:
    """
    Validates counterpoise optimization constraints under Method Matrix v4 §9A.1-9A.2.
    Unconstrained counterpoise PES optimization on weakly bound complexes is strictly
    prohibited to prevent unphysical dissociation caused by gradient noise and flat PES drift.
    """
    if is_complex and is_opt and not has_frozen_constraints:
        raise ValueError(
            "[ERR_METHOD_MATRIX] Unconstrained counterpoise geometry optimization is strictly prohibited. "
            "Enforce Frozen-Monomer Protocol (Recipe R2) with Cartesian locking on Monomer A."
        )

