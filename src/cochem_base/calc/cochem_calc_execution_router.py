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

from cochem_base.config_loader import (
    get_artifact_dir,
    load_system_config_dict,
    resolve_config_path,
    resolve_executable,
    resolve_mapped_path,
)
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig
from cochem.concurrency.subprocess_broker import SubprocessBroker

logger = logging.getLogger(__name__)

try:
    import parsl
    from parsl import python_app, bash_app
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
