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

import json
import logging
import math
import re
import shlex
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem_base.config_loader import (
    resolve_executable,
)
from cochem_base.schemas import ExecutionRouteResult, JobRouteConfig
from cochem.core.context import AirGapViolationError, assert_writable_path
from cochem_base.orchestrator.cochem_system_config import (
    CoChemSystemConfig, resolve_golden_registry_path,
)
from filelock import FileLock


from cochem_base.core_engine.execution_authority import (
    RegistryAuthorityViolationError, authorize_engine_execution,
)


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
        self.registry_path = resolve_golden_registry_path(registry_path)
        self.registry = self._load_registry()
        self.broker = broker
        self.dfk = dfk

    def _load_registry(self) -> Dict[str, Any]:
        """Reject missing or invalid authority instead of guessing machine limits."""
        try:
            with FileLock(str(self.registry_path) + ".lock", timeout=10.0):
                raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
            hardware = raw.get("hardware") if isinstance(raw, dict) else None
            required = {"physical_cpu_cores", "logical_cpu_cores", "ram_gb"}
            if not isinstance(hardware, dict) or not required <= hardware.keys():
                raise ValueError("Registry must contain audited physical_cpu_cores, logical_cpu_cores and ram_gb")
            if any(isinstance(hardware[k], bool) or not math.isfinite(float(hardware[k])) or float(hardware[k]) <= 0 for k in required):
                raise ValueError("Audited hardware bounds must be finite and positive")
            if any(not isinstance(hardware[k], int) for k in ("physical_cpu_cores", "logical_cpu_cores")):
                raise ValueError("Audited CPU counts must be integers")
            if hardware["physical_cpu_cores"] > hardware["logical_cpu_cores"]:
                raise ValueError("Physical CPU cores cannot exceed logical CPU cores")
            cfg = CoChemSystemConfig.model_validate(raw)
            if cfg.registry_checksum and not cfg.verify_checksum():
                raise ValueError("Golden Registry checksum mismatch")
            return cfg.model_dump(mode="json")
        except (OSError, ValueError, TypeError) as exc:
            raise RegistryAuthorityViolationError(f"Invalid Golden Registry at {self.registry_path}: {exc}") from exc

    def resolve_execution_path(self, target_engine: str) -> str:
        """Resolve only engines explicitly recorded as available by Stage 0."""
        engine = (self.registry.get("engines") or {}).get(target_engine)
        if not isinstance(engine, dict) or engine.get("status") not in ("ready", "found", "AVAILABLE"):
            raise RegistryAuthorityViolationError(f"Engine {target_engine!r} is not ready in the Golden Registry")
        return str((self.registry.get("execution") or {}).get("default_engine", "subprocess"))

    @staticmethod
    def _scratch_root(path: Union[str, Path]) -> Path:
        root = Path(path).resolve()
        assert_writable_path(root)
        checkout = Path(__file__).resolve().parents[3]
        if (checkout / "pyproject.toml").is_file() and root.is_relative_to(checkout):
            raise AirGapViolationError(f"Calculation scratch must be outside the source checkout: {root}")
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _command(command: Union[str, List[str], None]) -> List[str]:
        if isinstance(command, str):
            command = shlex.split(command, posix=sys.platform != "win32")
            if sys.platform == "win32":
                command = [part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"' else part for part in command]
        if not command or not isinstance(command, (list, tuple)) or any(not isinstance(part, str) or not part or "\0" in part for part in command):
            raise ValueError("An explicit nonempty executable argument list is required")
        return list(command)

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
        cmd = self._command(payload_command if payload_command is not None else kwargs.get("command"))
        execution_mode = (self.registry.get("execution") or {}).get("default_engine", "subprocess")
        if execution_mode not in ("subprocess", "local", "parsl"):
            raise ValueError(f"Unsupported route mode {execution_mode!r}; use the explicit scheduler submission API")
        known_job_types = {"heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"}
        if target_engine_or_type is not None and target_engine_or_type not in known_job_types:
            self.resolve_execution_path(target_engine_or_type)
            authorize_engine_execution(
                target_engine_or_type, registry_path=self.registry_path, command=cmd,
                cores=len(cpu_core_pinning or route_config.cpu_core_pinning)
                if (cpu_core_pinning or (route_config and route_config.cpu_core_pinning)) else None,
            )
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
        config_scratch = route_config.scratch_dir if route_config is not None else None
        base_scratch = self._scratch_root(scratch_dir or config_scratch or cwd or scratch_env or tempfile.gettempdir())

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

        if route_config.job_type != effective_job_type and (job_type is not None or target_engine_or_type is not None):
            raise ValueError("route_config.job_type conflicts with the requested job type")
        if route_config.cpu_core_pinning:
            pins = route_config.cpu_core_pinning
            logical = self.registry["hardware"]["logical_cpu_cores"]
            if len(set(pins)) != len(pins) or any(isinstance(p, bool) or p < 0 or p >= logical for p in pins):
                raise ValueError("CPU pinning must contain distinct indices within audited logical CPU bounds")
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
        # cmd has already been validated before creating any task directories.

        expected_pool = "cochem_scout_gpu" if route_config.job_type == "fast_potential_scan" else "cochem_anchor_cpu"
        if route_config.assigned_executor != expected_pool and not (execution_mode in ("local", "subprocess") and route_config.assigned_executor == "local_fallback"):
            raise ValueError(f"Job type {route_config.job_type!r} requires {expected_pool!r}")
        if execution_mode in ("local", "subprocess") and (self.dfk is not None or self.broker is not None):
            raise RegistryAuthorityViolationError("A Parsl kernel/broker conflicts with the registry's local execution mode")
        # Probe Parsl only when the authoritative registry requires it.
        active_dfk = self.dfk if execution_mode == "parsl" else None
        if execution_mode == "parsl" and active_dfk is None and self.broker is not None and hasattr(self.broker, "get_dfk"):
            active_dfk = self.broker.get_dfk()
        if execution_mode == "parsl" and active_dfk is None and HAS_PARSL:
            try:
                active_dfk = parsl.dfk()
            except Exception:
                active_dfk = None

        if active_dfk is not None:
            executors_in_dfk = list(active_dfk.executors.keys())
            target_executor = route_config.assigned_executor
            if not HAS_PARSL:
                raise RuntimeError("Parsl is required for the supplied data-flow kernel")
            if target_executor not in executors_in_dfk:
                raise RegistryAuthorityViolationError(f"Requested executor {target_executor!r} is absent; refusing a different hardware pool")

            @python_app(data_flow_kernel=active_dfk, executors=[target_executor])
            def _parsl_task_runner(cmd_to_run: Union[str, List[str]], work_dir: str, env_vars: Dict[str, str], t_sec: float) -> int:
                from cochem.concurrency.subprocess_broker import SubprocessBroker
                b = SubprocessBroker(cwd=work_dir, base_scratch_dir=work_dir, env=env_vars, timeout_seconds=t_sec, max_retries=1)
                r = b.execute(cmd_to_run, cwd=work_dir)
                if not r.success:
                    raise RuntimeError(f"Computational task failed with exit {r.returncode}: {r.stderr}")
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
            if execution_mode == "parsl":
                raise RegistryAuthorityViolationError("Registry requires Parsl, but no active data-flow kernel is available")
            # Explicit local execution in an isolated scratch sandbox.
            broker = SubprocessBroker(cwd=task_scratch, base_scratch_dir=task_scratch, env=task_env, timeout_seconds=route_config.timeout_seconds, max_retries=1)
            res = broker.execute(cmd, cwd=task_scratch)
            return ExecutionRouteResult(
                task_id=task_id,
                assigned_executor="local_fallback",
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
        command = self._command(payload_command)
        scratch_root = os.environ.get("COCHEM_SCRATCH") or os.environ.get("SLURM_TMPDIR") or cwd
        base_scratch = self._scratch_root(scratch_root)
        task_id = uuid.uuid4().hex
        task_scratch = base_scratch / f"task_{task_id}"
        task_scratch.mkdir()
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        broker = SubprocessBroker(cwd=task_scratch, base_scratch_dir=task_scratch, env=merged_env, timeout_seconds=timeout, max_retries=1)
        result = broker.execute(command, cwd=task_scratch)
        (task_scratch / f"task_{task_id}.out").write_text(result.stdout, encoding="utf-8")
        (task_scratch / f"task_{task_id}.err").write_text(result.stderr, encoding="utf-8")
        return result.returncode

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

        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", job_name):
            raise ValueError("Job name must be a single safe filename component")
        cwd = str(self._scratch_root(cwd))
        command = shlex.join(self._command(payload_command))
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
            payload_command=command,
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
    if not all(math.isfinite(value) for value in (e_ab, e_a_ghost, e_b_ghost)):
        raise ValueError("Counterpoise energies must be finite")
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
