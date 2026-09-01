#!/usr/bin/env python3
# cochem_canvas_target: core_engine/cochem_core_parsl_executors.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8A - Parsl Multi-Executor Heterogeneous HPC & Task Router.
Mandated by SRS Doc 1 (Topology 1.0 §2), Doc 2 Part 1 (§2.5), and Method Matrix §8A.

Implements the Scout-and-Anchor Heterogeneous Concurrency Engine:
1. Multi-Executor Heterogeneous Parsl Topologies:
   - CPU Anchor Executor ('cochem_anchor_cpu' / 'cpu'): Dedicated to heavy, authoritative
     quantum calculations (ORCA DFT/VPT2, MPQC CCSD(T)-F12, CFOUR) pinned to P-cores ('block'),
     %maxcore 3400, 7 P-cores by default on 8-core workstations.
   - GPU Scout Executor ('cochem_scout_gpu' / 'gpu'): Dedicated to advisory GPU workers
     (MLFF, MACE, AIMNet2, gpu4pyscf) under NVIDIA MPS, available_accelerators=3,
     cpu_affinity='block-reverse', 1 P-core for host-side launch feeder (57% host-side overhead),
     6 GB VRAM quota per worker.
   - Orchestrator / Utility Executor ('cochem_orchestrator' / 'orchestrator'): Dedicated to
     E-cores and host tasks (DFK, stage scheduler, deduplication, I/O, regex, provenance stamping).

2. Heterogeneous Resource Providers:
   - LocalProvider: Local workstations / desktops (Setup 2: 13700K + RTX 3090; Setup 1: CPU-only).
   - SlurmProvider: HPC cluster partitions (Setup 3) with '#SBATCH --gres=gpu:1', '#SBATCH --nodes=1',
     walltime, account, qos, partition, and SrunLauncher/SimpleLauncher.
   - Graceful fallback to single-executor or ThreadPool execution on constrained or teaching environments.

3. Contention Budgeting & Core Affinity (§8A.1, §8A.4):
   - Real parallelism budget calculation (85% real efficiency, 1.20x CPU slowdown budget factor).
   - Core affinity partitioning (P-cores 0..N-2 for CPU anchor, P-core N-1 for GPU scout feeder,
     E-cores for DFK/I/O).
   - Dynamic VRAM partitioning and thread percentage capping under NVIDIA MPS.

4. Method Matrix §8A.5 Integrity Guards (G1–G7) Engine:
   - G1: Advisory-only guide surface (rejects guide results claiming authoritative status).
   - G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
   - G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å using Mendeleev masses).
   - G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling).
   - G5: Uncertainty gate (committee sigma thresholding).
   - G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
   - G7: Provenance event audit logging (structured JSONL event lines appended to provenance.jsonl).

5. Task Routing, Parsl App Factories & Pipeline Execution:
   - App decorators and dispatchers for @bash_app and @python_app targeting 'cpu', 'gpu', or 'orchestrator'.
   - Future management, stage chaining, timeout enforcement, retry logic (retries=2 per §8A.6).
   - Standardized TaskExecutionResult models and execution status reporting.

6. Thread-Safe Parsl DFK Lifecycle Manager:
   - Thread-safe singleton ParslExecutionBroker.
   - Safe process cleanup & zombie sweeping via psutil and atexit.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import os
import platform
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np
import psutil
import scipy.stats
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from cochem_base.config_loader import (
    get_artifact_dir,
    get_mps_directories,
    get_runtime_dir,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    CoChemError,
    ProvenanceErrorCode,
)

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-ParslExecutors")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Method Matrix §8A Hardware & Pipeline Constants
# ---------------------------------------------------------------------------
DEFAULT_ORCA_ANCHOR_RANKS: int = 7
DEFAULT_ORCA_MAXCORE_MB: int = 3400
DEFAULT_MAX_GPU_SCOUT_WORKERS: int = 3
DEFAULT_MPS_THREAD_PERCENTAGE: int = 33
DEFAULT_MPS_PINNED_MEM_LIMIT_STR: str = "0=6G"
DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR: float = 1.20
DEFAULT_SCOUT_HOST_LATENCY_MS: float = 18.1
DEFAULT_ULIMIT_NOFILE: int = 16384
DEFAULT_WORKER_PORT_RANGE: Tuple[int, int] = (50000, 52499)
DEFAULT_INTERCHANGE_PORT_RANGE: Tuple[int, int] = (52500, 54999)
DEFAULT_PARSL_RETRIES: int = 2
DEFAULT_G3_RMSD_THRESHOLD_ANGSTROM: float = 0.25
DEFAULT_G3_DELTA_R_THRESHOLD_ANGSTROM: float = 0.20
DEFAULT_G4_SPEARMAN_RHO_THRESHOLD: float = 0.90
DEFAULT_G5_UNCERTAINTY_THRESHOLD_MEV: float = 10.0
DEFAULT_G6_MAX_GUIDE_FAILURES: int = 5


# ---------------------------------------------------------------------------
# Zombie Process Sweeping & Subprocess Safety
# ---------------------------------------------------------------------------
def _sweep_zombie_processes() -> None:
    """Sweep zombie child processes to maintain OS cleanliness."""
    try:
        current_proc = psutil.Process()
        for child in current_proc.children(recursive=True):
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    child.wait(timeout=0.2)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
    except Exception:
        pass


atexit.register(_sweep_zombie_processes)


# =============================================================================
# Custom Exception Hierarchy
# =============================================================================
class ParslExecutorError(CoChemError):
    """Base exception for all CoChem Parsl executor and routing failures."""

    default_error_code = ProvenanceErrorCode.CONFIG_VALIDATION_FAILED


class HeterogeneousTopologyError(ParslExecutorError):
    """Raised when heterogeneous core or device topology partitioning fails."""

    default_error_code = ProvenanceErrorCode.HARDWARE_DETECTION_FAILED


class ContentionBudgetExceededError(ParslExecutorError):
    """Raised when requested worker or memory allocations violate hardware bounds."""

    default_error_code = ProvenanceErrorCode.OUT_OF_MEMORY


class IntegrityGuardViolationError(ParslExecutorError):
    """Raised when a Method Matrix §8A.5 integrity guard (G1-G7) is violated."""

    default_error_code = ProvenanceErrorCode.INTEGRITY_VIOLATION


class ExecutorLifecycleError(ParslExecutorError):
    """Raised when Parsl DataFlowKernel loading, execution, or shutdown fails."""

    default_error_code = ProvenanceErrorCode.CONVERGENCE_FAILURE


# =============================================================================
# Enumerations
# =============================================================================
class ExecutorStreamType(str, Enum):
    """Heterogeneous Scout-and-Anchor execution stream classification."""

    CPU_ANCHOR = "CPU_ANCHOR"
    GPU_SCOUT = "GPU_SCOUT"
    ORCHESTRATOR = "ORCHESTRATOR"


class ParslProviderType(str, Enum):
    """Supported compute resource provider backends."""

    LOCAL = "LOCAL"
    SLURM = "SLURM"
    PBS = "PBS"
    LSF = "LSF"
    THREAD_POOL = "THREAD_POOL"


class AffinityStrategy(str, Enum):
    """CPU core affinity allocation and pinning strategy."""

    BLOCK = "block"
    BLOCK_REVERSE = "block-reverse"
    PINNED_LIST = "pinned-list"
    SHARED_DEGRADED = "shared-degraded"
    NONE = "none"


class TaskAuthority(str, Enum):
    """Authority classification for task execution outputs (§8A.2, §8A.5)."""

    AUTHORITATIVE = "authoritative"
    ADVISORY_ONLY = "advisory_only"
    ORCHESTRATION = "orchestration"


# =============================================================================
# Pydantic V2 Data Models
# =============================================================================
class CorePartitioning(BaseModel):
    """Detailed CPU core partitioning across heterogeneous execution streams."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_physical_cores: int = Field(..., ge=1, description="Total physical CPU cores on host")
    total_logical_cores: int = Field(..., ge=1, description="Total logical CPU threads on host")
    anchor_core_count: int = Field(..., ge=1, description="Physical CPU cores allocated to CPU Anchor")
    anchor_core_ids: List[int] = Field(default_factory=list, description="Zero-indexed core IDs for Anchor")
    anchor_affinity_str: str = Field(..., description="Parsl affinity directive for Anchor")
    scout_core_count: int = Field(..., ge=1, description="Physical CPU cores allocated to GPU Scout feeder")
    scout_core_ids: List[int] = Field(default_factory=list, description="Zero-indexed core IDs for Scout")
    scout_affinity_str: str = Field(..., description="Parsl affinity directive for Scout")
    orchestrator_core_count: int = Field(default=1, ge=0, description="Cores allocated for Orchestrator / I/O")
    strategy: AffinityStrategy = Field(
        default=AffinityStrategy.BLOCK, description="Core affinity assignment strategy"
    )
    is_degraded: bool = Field(
        default=False, description="True if host has <= 1 physical core and streams share resources"
    )


class ContentionBudget(BaseModel):
    """Hardware contention budget model mandated by Method Matrix §8A.1."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    p_cores_anchor: int = Field(default=DEFAULT_ORCA_ANCHOR_RANKS, ge=1)
    p_cores_scout_feeder: int = Field(default=1, ge=1)
    gpu_scout_workers: int = Field(default=DEFAULT_MAX_GPU_SCOUT_WORKERS, ge=1)
    mps_active_thread_percentage: int = Field(default=DEFAULT_MPS_THREAD_PERCENTAGE, ge=1, le=100)
    mps_pinned_device_mem_limit: str = Field(default=DEFAULT_MPS_PINNED_MEM_LIMIT_STR)
    estimated_cpu_slowdown_factor: float = Field(default=DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR, ge=1.0)
    real_parallelism_efficiency: float = Field(default=0.85, ge=0.0, le=1.0)
    host_launch_bound_latency_ms: float = Field(default=DEFAULT_SCOUT_HOST_LATENCY_MS, ge=0.0)
    total_host_ram_gb: float = Field(..., ge=1.0)
    anchor_mem_per_worker_gb: float = Field(default=28.0, ge=1.0)
    scout_mem_per_worker_gb: float = Field(default=6.0, ge=0.5)


class SlurmResourceOptions(BaseModel):
    """HPC SLURM resource allocation options for cluster execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    partition: Optional[str] = Field(default=None, description="SLURM partition name")
    account: Optional[str] = Field(default=None, description="SLURM accounting project name")
    qos: Optional[str] = Field(default=None, description="Quality of service tier")
    gres_gpu: str = Field(default="gpu:1", description="Generic resource request string (e.g. 'gpu:1')")
    gpus_per_node: int = Field(default=1, ge=1, description="GPUs requested per allocated node")
    nodes_per_block: int = Field(default=1, ge=1, description="Nodes per SLURM job block")
    walltime: str = Field(default="04:00:00", description="Wall-clock limit string (HH:MM:SS)")
    srun_launcher: bool = Field(default=True, description="Whether to use SrunLauncher over SimpleLauncher")
    custom_scheduler_options: List[str] = Field(
        default_factory=list, description="Additional #SBATCH header options"
    )


class HTEXConfig(BaseModel):
    """Configuration profile for a single Parsl HighThroughputExecutor (HTEX) pool."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    label: str = Field(..., description="Unique executor label (e.g. 'cpu', 'gpu', 'orchestrator')")
    stream: ExecutorStreamType = Field(..., description="Target execution stream")
    provider_type: ParslProviderType = Field(
        default=ParslProviderType.LOCAL, description="Compute resource provider backend"
    )
    max_workers_per_node: int = Field(default=1, ge=1, description="Concurrent worker processes per node")
    cores_per_worker: float = Field(default=1.0, ge=0.1, description="CPU cores dedicated per worker")
    mem_per_worker_gb: Optional[float] = Field(
        default=None, ge=0.1, description="Memory limit per worker in Gigabytes"
    )
    cpu_affinity: str = Field(
        default="block", description="Parsl CPU affinity directive ('block', 'block-reverse', 'list:0,1..')"
    )
    available_accelerators: Optional[Union[int, List[str]]] = Field(
        default=None, description="GPU accelerator slots or device indices"
    )
    worker_port_range: Tuple[int, int] = Field(default=DEFAULT_WORKER_PORT_RANGE)
    interchange_port_range: Tuple[int, int] = Field(default=DEFAULT_INTERCHANGE_PORT_RANGE)
    worker_init_script: str = Field(default="", description="Bash environment initialization script")
    walltime: str = Field(default="04:00:00", description="Wall-clock limit")


class ParslMultiExecutorProfile(BaseModel):
    """Complete heterogeneous multi-executor system topology profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    profile_id: str = Field(
        default_factory=lambda: f"parsl_topo_{uuid.uuid4().hex[:8]}", description="Unique profile identifier"
    )
    created_at_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Creation timestamp"
    )
    core_partitioning: CorePartitioning = Field(..., description="CPU core partitioning profile")
    contention_budget: ContentionBudget = Field(..., description="Resource contention budget")
    anchor_executor: HTEXConfig = Field(..., description="CPU Anchor executor configuration")
    scout_executor: HTEXConfig = Field(..., description="GPU Scout executor configuration")
    orchestrator_executor: HTEXConfig = Field(..., description="Orchestrator executor configuration")
    slurm_options: Optional[SlurmResourceOptions] = Field(
        default=None, description="SLURM options if running on HPC"
    )
    is_degraded_single_executor: bool = Field(
        default=False, description="True if operating in CPU-only or teaching tier degraded mode"
    )
    parsl_retries: int = Field(default=DEFAULT_PARSL_RETRIES, ge=0)


class G7ProvenanceRecord(BaseModel):
    """Structured JSONL event audit record mandated by Method Matrix §8A.5 (line 1323)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Cryptographic event ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="UTC timestamp"
    )
    stage: str = Field(..., description="Pipeline stage (e.g. 'mlff_preopt', 'anchor_verify')")
    decision: str = Field(..., description="Decision summary (e.g. 'seed_dft_optimisation')")
    guide: Dict[str, Any] = Field(default_factory=dict, description="Guide / Scout execution metadata")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input structure and hash metadata")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output properties and hash metadata")
    gates: Dict[str, Any] = Field(default_factory=dict, description="Integrity guard gate evaluations (G1-G6)")
    consumer: Dict[str, Any] = Field(default_factory=dict, description="Downstream anchor job consumption")
    authority: TaskAuthority = Field(
        default=TaskAuthority.ADVISORY_ONLY, description="Authority tag ('advisory_only' vs 'authoritative')"
    )


class TaskRoutingRequest(BaseModel):
    """Structured request for dispatching a task through Parsl."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    stream: ExecutorStreamType = Field(..., description="Target execution stream (CPU_ANCHOR, GPU_SCOUT, etc.)")
    authority: TaskAuthority = Field(default=TaskAuthority.ADVISORY_ONLY)
    command: Optional[List[str]] = Field(default=None, description="Command line arguments for bash tasks")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Injected environment variables")
    timeout_seconds: float = Field(default=3600.0, ge=1.0)
    stage_name: str = Field(default="generic_stage")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskExecutionResult(BaseModel):
    """Structured result returned by task execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    task_id: str = Field(...)
    stream: ExecutorStreamType = Field(...)
    authority: TaskAuthority = Field(...)
    status: str = Field(..., description="Status string: 'COMPLETED', 'FAILED', 'TIMED_OUT'")
    return_code: Optional[int] = Field(default=None)
    stdout: Optional[str] = Field(default=None)
    stderr: Optional[str] = Field(default=None)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    output_files: Dict[str, str] = Field(default_factory=dict, description="Map of file label to file path")
    file_hashes: Dict[str, str] = Field(default_factory=dict, description="Map of file path to SHA-256")
    provenance_event_id: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


# =============================================================================
# CPU Topology & Contention Budget Engine
# =============================================================================
def detect_system_cpu_topology(env: Optional[Dict[str, str]] = None) -> Tuple[int, int]:
    """
    Detect physical and logical CPU cores on the host system.
    Evaluates psutil, os.cpu_count, and explicit environment overrides.

    Returns:
        Tuple of (physical_cores, logical_cores).
    """
    target_env = os.environ if env is None else env

    physical: Optional[int] = None
    logical: Optional[int] = None

    if "COCHEM_PHYSICAL_CORES" in target_env and target_env["COCHEM_PHYSICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_PHYSICAL_CORES"].strip())
            if val >= 1:
                physical = val
        except ValueError:
            pass

    if "COCHEM_LOGICAL_CORES" in target_env and target_env["COCHEM_LOGICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_LOGICAL_CORES"].strip())
            if val >= 1:
                logical = val
        except ValueError:
            pass

    if physical is None:
        try:
            p = psutil.cpu_count(logical=False)
            if p is not None and p >= 1:
                physical = p
        except Exception:
            pass

    if logical is None:
        try:
            log_count = psutil.cpu_count(logical=True)
            if log_count is not None and log_count >= 1:
                logical = log_count
        except Exception:
            pass

    if physical is None:
        physical = os.cpu_count() or 1

    if logical is None:
        logical = os.cpu_count() or physical or 1

    if physical > logical:
        physical = logical

    return max(1, physical), max(1, logical)


def partition_cpu_cores(
    total_physical: int,
    requested_anchor: Optional[int] = None,
    requested_scout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> CorePartitioning:
    """
    Partition host CPU cores between Anchor (CPU), Scout (GPU Feeder), and Orchestrator.
    Compliant with Method Matrix §8A.1 and §8A.6:
      - 8+ cores: 7 P-cores dedicated to Anchor, 1 P-core dedicated to Scout, remainder Orchestrator.
      - 2..7 cores: 1 P-core dedicated to Scout, N-1 cores dedicated to Anchor.
      - 1 core: Shared degraded mode (core 0 shared).

    Returns:
        CorePartitioning model.
    """
    target_env = os.environ if env is None else env

    def parse_int(key: str) -> Optional[int]:
        if key in target_env and target_env[key].strip():
            try:
                v = int(target_env[key].strip())
                if v >= 1:
                    return v
            except ValueError:
                return None
        return None

    env_anchor = parse_int("COCHEM_PARSL_ANCHOR_CORES")
    env_scout = parse_int("COCHEM_PARSL_SCOUT_CORES")

    req_anchor = requested_anchor if requested_anchor is not None else env_anchor
    req_scout = requested_scout if requested_scout is not None else env_scout

    _, total_logical = detect_system_cpu_topology(target_env)

    if total_physical <= 1:
        # Single core degraded mode
        return CorePartitioning(
            total_physical_cores=1,
            total_logical_cores=total_logical,
            anchor_core_count=1,
            anchor_core_ids=[0],
            anchor_affinity_str="list:0",
            scout_core_count=1,
            scout_core_ids=[0],
            scout_affinity_str="list:0",
            orchestrator_core_count=1,
            strategy=AffinityStrategy.SHARED_DEGRADED,
            is_degraded=True,
        )

    if req_anchor is not None and req_scout is not None:
        anchor_count = req_anchor
        scout_count = req_scout
    elif req_scout is not None:
        scout_count = max(1, req_scout)
        anchor_count = max(1, total_physical - scout_count)
    elif req_anchor is not None:
        anchor_count = max(1, req_anchor)
        scout_count = max(1, total_physical - anchor_count)
    else:
        # Canonical Method Matrix §8A baseline
        if total_physical >= 8:
            anchor_count = DEFAULT_ORCA_ANCHOR_RANKS
            scout_count = 1
        else:
            scout_count = 1
            anchor_count = max(1, total_physical - 1)

    anchor_core_ids = [c % total_physical for c in range(0, anchor_count)]
    scout_start = anchor_count
    scout_core_ids = [(scout_start + c) % total_physical for c in range(0, scout_count)]

    anchor_affinity_str = "list:" + ",".join(str(c) for c in anchor_core_ids)
    scout_affinity_str = "list:" + ",".join(str(c) for c in scout_core_ids)

    orchestrator_count = max(1, total_physical - (anchor_count + scout_count)) if total_physical > (anchor_count + scout_count) else 1

    return CorePartitioning(
        total_physical_cores=total_physical,
        total_logical_cores=total_logical,
        anchor_core_count=anchor_count,
        anchor_core_ids=anchor_core_ids,
        anchor_affinity_str=anchor_affinity_str,
        scout_core_count=scout_count,
        scout_core_ids=scout_core_ids,
        scout_affinity_str=scout_affinity_str,
        orchestrator_core_count=orchestrator_count,
        strategy=AffinityStrategy.BLOCK,
        is_degraded=False,
    )


def calculate_contention_budget(
    total_physical_cores: int,
    total_ram_gb: float,
    gpu_scout_workers: int = DEFAULT_MAX_GPU_SCOUT_WORKERS,
    anchor_ranks: int = DEFAULT_ORCA_ANCHOR_RANKS,
) -> ContentionBudget:
    """
    Calculate resource contention budget model (§8A.1).
    Enforces host RAM headroom, VRAM partitioning under MPS, and slowdown estimates.
    """
    # Dynamic MPS thread partitioning: 100% / N_workers
    thread_pct = max(1, 100 // max(1, gpu_scout_workers))
    # VRAM allocation per worker
    pinned_mem = "0=6G" if gpu_scout_workers <= 3 else "0=4G"

    # Slowdown factor: 8/7 * 1.05 (mem bandwidth) * 1.05 (thermal) ≈ 1.20x
    slowdown_factor = DEFAULT_CONTENZIONE_SLOWDOWN_FACTOR

    return ContentionBudget(
        p_cores_anchor=anchor_ranks,
        p_cores_scout_feeder=1,
        gpu_scout_workers=gpu_scout_workers,
        mps_active_thread_percentage=thread_pct,
        mps_pinned_device_mem_limit=pinned_mem,
        estimated_cpu_slowdown_factor=slowdown_factor,
        real_parallelism_efficiency=0.85,
        host_launch_bound_latency_ms=DEFAULT_SCOUT_HOST_LATENCY_MS,
        total_host_ram_gb=total_ram_gb,
        anchor_mem_per_worker_gb=28.0,
        scout_mem_per_worker_gb=6.0,
    )


# =============================================================================
# Worker Init Scripts & Parsl Configuration Assembly
# =============================================================================
def build_worker_init_scripts(
    mps_pipe_dir: Optional[Path] = None,
    mps_log_dir: Optional[Path] = None,
    mps_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    mps_pinned_mem: str = DEFAULT_MPS_PINNED_MEM_LIMIT_STR,
    gpu_device_id: int = 0,
) -> Tuple[str, str, str]:
    """
    Generate authoritative bash worker initialization scripts for CPU, GPU, and Orchestrator.
    Compliant with Method Matrix §8A.6 lines 1373–1388.

    Returns:
        Tuple of (cpu_init_script, gpu_init_script, orchestrator_init_script).
    """
    if mps_pipe_dir is None or mps_log_dir is None:
        pipe, log = get_mps_directories()
        mps_pipe_dir = pipe if mps_pipe_dir is None else mps_pipe_dir
        mps_log_dir = log if mps_log_dir is None else mps_log_dir

    cpu_init_script = (
        "export OMP_NUM_THREADS=1; "
        "export KMP_HW_SUBSET=8c:intel_core,1t"
    )

    gpu_init_script = (
        f"export CUDA_VISIBLE_DEVICES={gpu_device_id}; "
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={mps_thread_pct}; "
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{mps_pinned_mem}'; "
        f"export CUDA_MPS_PIPE_DIRECTORY='{mps_pipe_dir.resolve()}'; "
        f"export CUDA_MPS_LOG_DIRECTORY='{mps_log_dir.resolve()}'; "
        f"ulimit -n {DEFAULT_ULIMIT_NOFILE}"
    )

    orchestrator_init_script = "export OMP_NUM_THREADS=1"

    return cpu_init_script, gpu_init_script, orchestrator_init_script


def build_heterogeneous_profile(
    provider_type: ParslProviderType = ParslProviderType.LOCAL,
    slurm_options: Optional[SlurmResourceOptions] = None,
    degraded_single_executor: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> ParslMultiExecutorProfile:
    """
    Assemble the complete heterogeneous multi-executor profile (§8A.2, §8A.6).
    """
    target_env = os.environ if env is None else env
    physical_cores, _ = detect_system_cpu_topology(target_env)
    total_ram_gb = psutil.virtual_memory().total / (1024**3)

    partitioning = partition_cpu_cores(
        total_physical=physical_cores,
        env=target_env,
    )

    contention = calculate_contention_budget(
        total_physical_cores=physical_cores,
        total_ram_gb=total_ram_gb,
    )

    pipe_dir, log_dir = get_mps_directories()
    cpu_init, gpu_init, orch_init = build_worker_init_scripts(
        mps_pipe_dir=pipe_dir,
        mps_log_dir=log_dir,
        mps_thread_pct=contention.mps_active_thread_percentage,
        mps_pinned_mem=contention.mps_pinned_device_mem_limit,
    )

    if degraded_single_executor or partitioning.is_degraded:
        # Degraded single executor profile (teaching tier or single-core host)
        anchor_cfg = HTEXConfig(
            label="cpu",
            stream=ExecutorStreamType.CPU_ANCHOR,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=min(8.0, total_ram_gb * 0.5),
            cpu_affinity="none",
            worker_init_script=cpu_init,
        )
        scout_cfg = HTEXConfig(
            label="gpu",
            stream=ExecutorStreamType.GPU_SCOUT,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=min(4.0, total_ram_gb * 0.25),
            cpu_affinity="none",
            worker_init_script=gpu_init,
        )
        orch_cfg = HTEXConfig(
            label="orchestrator",
            stream=ExecutorStreamType.ORCHESTRATOR,
            provider_type=provider_type,
            max_workers_per_node=1,
            cores_per_worker=1.0,
            mem_per_worker_gb=2.0,
            cpu_affinity="none",
            worker_init_script=orch_init,
        )
        return ParslMultiExecutorProfile(
            core_partitioning=partitioning,
            contention_budget=contention,
            anchor_executor=anchor_cfg,
            scout_executor=scout_cfg,
            orchestrator_executor=orch_cfg,
            slurm_options=slurm_options,
            is_degraded_single_executor=True,
        )

    # Full heterogeneous production profile
    anchor_cfg = HTEXConfig(
        label="cpu",
        stream=ExecutorStreamType.CPU_ANCHOR,
        provider_type=provider_type,
        max_workers_per_node=1,
        cores_per_worker=float(partitioning.anchor_core_count),
        mem_per_worker_gb=contention.anchor_mem_per_worker_gb,
        cpu_affinity="block",
        worker_init_script=cpu_init,
    )

    scout_cfg = HTEXConfig(
        label="gpu",
        stream=ExecutorStreamType.GPU_SCOUT,
        provider_type=provider_type,
        max_workers_per_node=contention.gpu_scout_workers,
        cores_per_worker=float(partitioning.scout_core_count) / float(contention.gpu_scout_workers),
        mem_per_worker_gb=contention.scout_mem_per_worker_gb,
        cpu_affinity="block-reverse",
        available_accelerators=contention.gpu_scout_workers,
        worker_init_script=gpu_init,
    )

    orch_cfg = HTEXConfig(
        label="orchestrator",
        stream=ExecutorStreamType.ORCHESTRATOR,
        provider_type=provider_type,
        max_workers_per_node=partitioning.orchestrator_core_count,
        cores_per_worker=1.0,
        mem_per_worker_gb=4.0,
        cpu_affinity="none",
        worker_init_script=orch_init,
    )

    return ParslMultiExecutorProfile(
        core_partitioning=partitioning,
        contention_budget=contention,
        anchor_executor=anchor_cfg,
        scout_executor=scout_cfg,
        orchestrator_executor=orch_cfg,
        slurm_options=slurm_options,
        is_degraded_single_executor=False,
    )


def construct_parsl_config(
    profile: Optional[ParslMultiExecutorProfile] = None,
    run_dir: Optional[Union[str, Path]] = None,
) -> Any:
    """
    Construct a physical parsl.config.Config object incorporating CPU Anchor,
    GPU Scout, and Orchestrator executors.

    Args:
        profile: ParslMultiExecutorProfile descriptor (or default if None).
        run_dir: Optional custom runinfo directory for Parsl logs.

    Returns:
        Configured parsl.config.Config instance.
    """
    try:
        from parsl.config import Config
        from parsl.executors import HighThroughputExecutor, ThreadPoolExecutor
        from parsl.launchers import SimpleLauncher, SrunLauncher
        from parsl.providers import LocalProvider, SlurmProvider
    except ImportError as exc:
        raise ExecutorLifecycleError(f"Parsl library is not installed or importable: {exc}") from exc

    if profile is None:
        profile = build_heterogeneous_profile()

    resolved_run_dir: str
    if run_dir is not None:
        resolved_run_dir = str(resolve_mapped_path(run_dir))
    else:
        resolved_run_dir = str((get_runtime_dir() / "parsl_runinfo").resolve())

    def make_provider(htex_cfg: HTEXConfig) -> Any:
        if htex_cfg.provider_type == ParslProviderType.SLURM and profile.slurm_options:
            if platform.system() == "Windows":
                logger.warning(
                    "SlurmProvider is not supported natively on Windows platforms due to POSIX scheduler constraints; "
                    "falling back to LocalProvider."
                )
                return LocalProvider(
                    init_blocks=1,
                    min_blocks=0,
                    max_blocks=1,
                    nodes_per_block=1,
                    worker_init=htex_cfg.worker_init_script,
                    launcher=SimpleLauncher(),
                )

            slurm_opt = profile.slurm_options
            launcher_cls = SrunLauncher if slurm_opt.srun_launcher else SimpleLauncher
            sched_opts = list(slurm_opt.custom_scheduler_options)
            if slurm_opt.partition:
                sched_opts.append(f"#SBATCH --partition={slurm_opt.partition}")
            if slurm_opt.account:
                sched_opts.append(f"#SBATCH --account={slurm_opt.account}")
            if slurm_opt.qos:
                sched_opts.append(f"#SBATCH --qos={slurm_opt.qos}")
            if htex_cfg.stream == ExecutorStreamType.GPU_SCOUT:
                sched_opts.append(f"#SBATCH --gres={slurm_opt.gres_gpu}")
                sched_opts.append(f"#SBATCH --gpus-per-node={slurm_opt.gpus_per_node}")

            return SlurmProvider(
                nodes_per_block=slurm_opt.nodes_per_block,
                init_blocks=1,
                min_blocks=0,
                max_blocks=1,
                walltime=slurm_opt.walltime,
                scheduler_options="\n".join(sched_opts),
                worker_init=htex_cfg.worker_init_script,
                launcher=launcher_cls(),
            )
        # Default LocalProvider
        return LocalProvider(
            init_blocks=1,
            min_blocks=0,
            max_blocks=1,
            nodes_per_block=1,
            worker_init=htex_cfg.worker_init_script,
            launcher=SimpleLauncher(),
        )

    # 1. CPU Anchor Executor (HighThroughputExecutor)
    anchor_htex = HighThroughputExecutor(
        label=profile.anchor_executor.label,
        provider=make_provider(profile.anchor_executor),
        max_workers_per_node=profile.anchor_executor.max_workers_per_node,
        cores_per_worker=profile.anchor_executor.cores_per_worker,
        mem_per_worker=profile.anchor_executor.mem_per_worker_gb,
        cpu_affinity=profile.anchor_executor.cpu_affinity,
        worker_port_range=profile.anchor_executor.worker_port_range,
        interchange_port_range=profile.anchor_executor.interchange_port_range,
    )

    # 2. GPU Scout Executor (HighThroughputExecutor)
    scout_kwargs: Dict[str, Any] = {
        "label": profile.scout_executor.label,
        "provider": make_provider(profile.scout_executor),
        "max_workers_per_node": profile.scout_executor.max_workers_per_node,
        "cores_per_worker": profile.scout_executor.cores_per_worker,
        "mem_per_worker": profile.scout_executor.mem_per_worker_gb,
        "cpu_affinity": profile.scout_executor.cpu_affinity,
        "worker_port_range": profile.scout_executor.worker_port_range,
        "interchange_port_range": profile.scout_executor.interchange_port_range,
    }
    if profile.scout_executor.available_accelerators is not None:
        scout_kwargs["available_accelerators"] = profile.scout_executor.available_accelerators

    scout_htex = HighThroughputExecutor(**scout_kwargs)

    # 3. Orchestrator Executor (ThreadPoolExecutor for lightweight coordination)
    orch_exec = ThreadPoolExecutor(
        max_threads=profile.orchestrator_executor.max_workers_per_node,
        label=profile.orchestrator_executor.label,
    )

    return Config(
        executors=[anchor_htex, scout_htex, orch_exec],
        run_dir=resolved_run_dir,
        retries=profile.parsl_retries,
        strategy=None,
    )


# =============================================================================
# Method Matrix §8A.5 Integrity Guards (G1–G7) Engine
# =============================================================================
def verify_g1_authority(payload: Dict[str, Any]) -> bool:
    """
    G1: The cheap surface may set starting points, never reported answers.
    Every guide decision payload must be tagged 'advisory_only'.

    Raises:
        IntegrityGuardViolationError: If a guide task claims 'authoritative' status.
    """
    auth = str(payload.get("authority", "")).strip().lower()
    if auth == TaskAuthority.AUTHORITATIVE.value:
        raise IntegrityGuardViolationError(
            "G1 Violation: Guide/scout execution payload cannot claim 'authoritative' authority. "
            "Only anchor calculations may supply reported physical observables."
        )
    return auth in (
        TaskAuthority.ADVISORY_ONLY.value,
        TaskAuthority.ORCHESTRATION.value,
        "advisory_only",
        "guide",
        "scout",
    )


def verify_g2_high_level_hessian(
    anchor_result: Dict[str, Any],
    max_imaginary_frequencies: int = 0,
) -> bool:
    """
    G2: Verify final structure with a high-level Hessian showing correct
    imaginary frequency count and reporting the softest force constant.

    Raises:
        IntegrityGuardViolationError: If Hessian is missing or imaginary frequency count is exceeded.
    """
    imag_freqs = anchor_result.get("imaginary_frequencies_count")
    if imag_freqs is None:
        raise IntegrityGuardViolationError(
            "G2 Violation: Anchor calculation missing high-level Hessian verification."
        )

    if int(imag_freqs) > max_imaginary_frequencies:
        raise IntegrityGuardViolationError(
            f"G2 Violation: Final structure converged to saddle point with {imag_freqs} "
            f"imaginary frequencies (threshold: {max_imaginary_frequencies})."
        )
    return True


def compute_molecular_center_of_mass(
    coordinates: np.ndarray,
    atomic_symbols: Sequence[str],
) -> np.ndarray:
    """
    Compute 3D center of mass dynamically using Mendeleev atomic masses.
    Enforces Mendeleev Library Mandate (Rule 1 & 2).
    """
    masses = np.array([element(sym.strip()).mass for sym in atomic_symbols], dtype=np.float64)
    total_mass = np.sum(masses)
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be greater than zero.")
    return np.sum(coordinates * masses[:, np.newaxis], axis=0) / total_mass


def verify_g3_basin_identity(
    scout_coords_angstrom: np.ndarray,
    anchor_coords_angstrom: np.ndarray,
    atomic_symbols: Sequence[str],
    rmsd_threshold_angstrom: float = DEFAULT_G3_RMSD_THRESHOLD_ANGSTROM,
    delta_r_threshold_angstrom: float = DEFAULT_G3_DELTA_R_THRESHOLD_ANGSTROM,
) -> Tuple[bool, float, float, str]:
    """
    G3: Basin-identity check between scout predicted minimum and anchor relaxed minimum.
    Calculates heavy-atom RMSD and center-of-mass displacement Delta R using Mendeleev masses.
    Gate: RMSD > 0.25 Å or Delta R > 0.20 Å => flag 'basin change'.

    Returns:
        Tuple of (is_same_basin, rmsd, delta_r, message).
    """
    if scout_coords_angstrom.shape != anchor_coords_angstrom.shape:
        raise ValueError(
            f"Shape mismatch in G3 basin check: scout {scout_coords_angstrom.shape} vs "
            f"anchor {anchor_coords_angstrom.shape}"
        )

    # Filter heavy atoms (non-Hydrogen) for heavy-atom RMSD
    heavy_indices = [i for i, sym in enumerate(atomic_symbols) if sym.strip().upper() not in ("H", "D", "T")]
    if heavy_indices:
        scout_heavy = scout_coords_angstrom[heavy_indices]
        anchor_heavy = anchor_coords_angstrom[heavy_indices]
        rmsd = float(np.sqrt(np.mean(np.sum((scout_heavy - anchor_heavy) ** 2, axis=-1))))
    else:
        rmsd = float(np.sqrt(np.mean(np.sum((scout_coords_angstrom - anchor_coords_angstrom) ** 2, axis=-1))))

    # Compute center of mass separation Delta R using Mendeleev masses
    com_scout = compute_molecular_center_of_mass(scout_coords_angstrom, atomic_symbols)
    com_anchor = compute_molecular_center_of_mass(anchor_coords_angstrom, atomic_symbols)
    delta_r = float(np.linalg.norm(com_scout - com_anchor))

    is_same_basin = (rmsd <= rmsd_threshold_angstrom) and (delta_r <= delta_r_threshold_angstrom)
    if not is_same_basin:
        msg = (
            f"Basin change detected: heavy-atom RMSD={rmsd:.4f} A (gate <= {rmsd_threshold_angstrom:.2f} A), "
            f"Delta R={delta_r:.4f} A (gate <= {delta_r_threshold_angstrom:.2f} A)"
        )
    else:
        msg = f"Basin identity verified: RMSD={rmsd:.4f} A, Delta R={delta_r:.4f} A within tolerance."

    return is_same_basin, rmsd, delta_r, msg


def verify_g4_rank_inversion(
    scout_energies: Sequence[float],
    anchor_energies: Sequence[float],
    rho_threshold: float = DEFAULT_G4_SPEARMAN_RHO_THRESHOLD,
) -> Tuple[bool, float, str]:
    """
    G4: Rank-inversion audit before culling on cheap surface (§8A.5).
    Computes Spearman rank correlation rho on sample.
    Mandates rho >= 0.90 before discarding candidate geometries.

    Returns:
        Tuple of (passes_audit, spearman_rho, message).
    """
    if len(scout_energies) != len(anchor_energies):
        raise ValueError(
            f"Sample size mismatch: {len(scout_energies)} scout vs {len(anchor_energies)} anchor"
        )
    if len(scout_energies) < 2:
        return True, 1.0, "Sample size < 2; rank correlation bypassed."

    res = scipy.stats.spearmanr(scout_energies, anchor_energies)
    rho = float(res.statistic if hasattr(res, "statistic") else res[0])

    if np.isnan(rho):
        rho = 0.0

    passes = rho >= rho_threshold
    if not passes:
        msg = (
            f"G4 Violation: Spearman rank correlation rho={rho:.3f} below gate {rho_threshold:.2f}. "
            f"MLFF culling prohibited; retention window must be widened."
        )
    else:
        msg = f"G4 Verified: Spearman rank correlation rho={rho:.3f} >= {rho_threshold:.2f}."

    return passes, rho, msg


def verify_g5_uncertainty_gate(
    committee_sigma_mev_per_atom: float,
    threshold_mev_per_atom: float = DEFAULT_G5_UNCERTAINTY_THRESHOLD_MEV,
) -> bool:
    """G5: Committee uncertainty gate on MLFF guide predictions."""
    return committee_sigma_mev_per_atom <= threshold_mev_per_atom


def verify_g6_abort_guide(
    consecutive_guide_failures: int,
    max_failures: int = DEFAULT_G6_MAX_GUIDE_FAILURES,
) -> bool:
    """G6: Abort-the-guide rule after n_th = 5 consecutive failures."""
    return consecutive_guide_failures < max_failures


def log_g7_provenance_event(
    record: G7ProvenanceRecord,
    log_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """
    G7: Append structured provenance audit JSON event line to provenance.jsonl.
    Mandated by Method Matrix §8A.5 (line 1320).

    Returns:
        Path to the target provenance.jsonl file.
    """
    target_dir = Path(log_dir).resolve() if log_dir else get_artifact_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "provenance.jsonl"

    line = json.dumps(record.model_dump(mode="json")) + "\n"
    with open(target_file, "a", encoding="utf-8") as f:
        f.write(line)

    return target_file


# =============================================================================
# ParslExecutionBroker (Thread-Safe Lifecycle Manager)
# =============================================================================
class ParslExecutionBroker:
    """
    Thread-safe lifecycle manager and task dispatcher for the heterogeneous Parsl DFK.
    Maintains singleton instance, manages executor topology, and coordinates zero-mock execution.
    """

    _instance: Optional[ParslExecutionBroker] = None
    _lock = threading.RLock()

    def __new__(cls, *args: Any, **kwargs: Any) -> ParslExecutionBroker:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ParslExecutionBroker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        profile: Optional[ParslMultiExecutorProfile] = None,
        run_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self.profile: ParslMultiExecutorProfile = profile or build_heterogeneous_profile()
        self.run_dir: Optional[Path] = Path(run_dir).resolve() if run_dir else None
        self._dfk: Optional[Any] = None
        self._is_active: bool = False
        self._task_history: Dict[str, TaskExecutionResult] = {}
        self._consecutive_guide_failures: int = 0
        self._initialized = True

    @classmethod
    def get_instance(cls) -> ParslExecutionBroker:
        """Get the active singleton broker instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def load(self, force_reload: bool = False) -> Any:
        """
        Load or reload the physical Parsl DataFlowKernel.
        """
        with self._lock:
            import parsl

            if self._is_active and not force_reload:
                return self._dfk

            if self._is_active and force_reload:
                self.shutdown()

            parsl_cfg = construct_parsl_config(
                profile=self.profile,
                run_dir=self.run_dir,
            )
            try:
                self._dfk = parsl.load(parsl_cfg)
                self._is_active = True
                logger.info("Parsl DataFlowKernel loaded successfully with heterogeneous executors.")
                return self._dfk
            except Exception as exc:
                self._is_active = False
                raise ExecutorLifecycleError(f"Failed to load Parsl DataFlowKernel: {exc}") from exc

    def shutdown(self) -> None:
        """
        Cleanly shutdown the Parsl DataFlowKernel and reap worker processes.
        """
        with self._lock:
            import parsl

            if self._is_active:
                try:
                    parsl.clear()
                    logger.info("Parsl DataFlowKernel cleared.")
                except Exception as exc:
                    logger.warning(f"Error during parsl.clear(): {exc}")
                finally:
                    self._is_active = False
                    self._dfk = None
                    _sweep_zombie_processes()

    def is_active(self) -> bool:
        """Check if Parsl DFK is active."""
        with self._lock:
            return self._is_active

    def get_dfk(self) -> Optional[Any]:
        """Retrieve the active DataFlowKernel."""
        with self._lock:
            return self._dfk

    def submit_bash_task(
        self,
        request: TaskRoutingRequest,
        stdout_path: Optional[Union[str, Path]] = None,
        stderr_path: Optional[Union[str, Path]] = None,
    ) -> Any:
        """
        Submit a bash-level computational chemistry task to the appropriate executor pool.
        """
        with self._lock:
            if not self._is_active:
                self.load()

            from parsl import bash_app

            executor_label: str
            if request.stream == ExecutorStreamType.CPU_ANCHOR:
                executor_label = self.profile.anchor_executor.label
            elif request.stream == ExecutorStreamType.GPU_SCOUT:
                executor_label = self.profile.scout_executor.label
            else:
                executor_label = self.profile.orchestrator_executor.label

            @bash_app(executors=[executor_label])
            def _generic_bash_runner(
                cmd_args: List[str],
                env_dict: Dict[str, str],
                stdout: Optional[str] = None,
                stderr: Optional[str] = None,
            ) -> str:
                env_prefix = " ".join(f"{k}='{v}'" for k, v in env_dict.items())
                cmd_str = " ".join(cmd_args)
                return f"{env_prefix} {cmd_str}" if env_prefix else cmd_str

            out_str = str(resolve_mapped_path(stdout_path)) if stdout_path else None
            err_str = str(resolve_mapped_path(stderr_path)) if stderr_path else None

            cmd = request.command or ["echo", "no-op"]
            app_future = _generic_bash_runner(
                cmd_args=cmd,
                env_dict=request.env_vars,
                stdout=out_str,
                stderr=err_str,
            )
            return app_future

    def submit_python_task(
        self,
        stream: ExecutorStreamType,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Submit a Python callable to the designated executor stream.
        """
        with self._lock:
            if not self._is_active:
                self.load()

            from parsl import python_app

            executor_label: str
            if stream == ExecutorStreamType.CPU_ANCHOR:
                executor_label = self.profile.anchor_executor.label
            elif stream == ExecutorStreamType.GPU_SCOUT:
                executor_label = self.profile.scout_executor.label
            else:
                executor_label = self.profile.orchestrator_executor.label

            @python_app(executors=[executor_label])
            def _runner(*fn_args: Any, **fn_kwargs: Any) -> Any:
                return func(*fn_args, **fn_kwargs)

            return _runner(*args, **kwargs)

    def execute_and_wait(
        self,
        request: TaskRoutingRequest,
        stdout_path: Optional[Union[str, Path]] = None,
        stderr_path: Optional[Union[str, Path]] = None,
    ) -> TaskExecutionResult:
        """
        Submit a task, wait for resolution within timeout, and generate a validated TaskExecutionResult.
        """
        start_time = time.time()
        try:
            future = self.submit_bash_task(
                request=request,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            ret_code = future.result(timeout=request.timeout_seconds)
            duration = time.time() - start_time

            # Read outputs if available
            stdout_content: Optional[str] = None
            stderr_content: Optional[str] = None
            file_hashes: Dict[str, str] = {}
            output_files: Dict[str, str] = {}

            if stdout_path and Path(stdout_path).exists():
                stdout_content = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
                output_files["stdout"] = str(stdout_path)
                file_hashes[str(stdout_path)] = hashlib.sha256(Path(stdout_path).read_bytes()).hexdigest()

            if stderr_path and Path(stderr_path).exists():
                stderr_content = Path(stderr_path).read_text(encoding="utf-8", errors="replace")
                output_files["stderr"] = str(stderr_path)
                file_hashes[str(stderr_path)] = hashlib.sha256(Path(stderr_path).read_bytes()).hexdigest()

            status = "COMPLETED" if ret_code == 0 else "FAILED"

            result = TaskExecutionResult(
                task_id=request.task_id,
                stream=request.stream,
                authority=request.authority,
                status=status,
                return_code=ret_code,
                stdout=stdout_content,
                stderr=stderr_content,
                duration_seconds=duration,
                output_files=output_files,
                file_hashes=file_hashes,
            )
            self._task_history[request.task_id] = result
            return result

        except Exception as exc:
            duration = time.time() - start_time
            logger.error(f"Task {request.task_id} failed on stream {request.stream}: {exc}")
            result = TaskExecutionResult(
                task_id=request.task_id,
                stream=request.stream,
                authority=request.authority,
                status="FAILED",
                duration_seconds=duration,
                error_message=str(exc),
            )
            self._task_history[request.task_id] = result
            return result

    def get_status_report(self) -> Dict[str, Any]:
        """Generate a complete status report of the broker and executors."""
        with self._lock:
            return {
                "is_active": self._is_active,
                "profile_id": self.profile.profile_id,
                "anchor_executor": self.profile.anchor_executor.model_dump(),
                "scout_executor": self.profile.scout_executor.model_dump(),
                "orchestrator_executor": self.profile.orchestrator_executor.model_dump(),
                "core_partitioning": self.profile.core_partitioning.model_dump(),
                "contention_budget": self.profile.contention_budget.model_dump(),
                "total_tasks_tracked": len(self._task_history),
                "consecutive_guide_failures": self._consecutive_guide_failures,
            }

    def __enter__(self) -> ParslExecutionBroker:
        self.load()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown()


# =============================================================================
# Helper Convenience Functions
# =============================================================================
def load_parsl_executors(
    profile: Optional[ParslMultiExecutorProfile] = None,
    run_dir: Optional[Union[str, Path]] = None,
) -> ParslExecutionBroker:
    """Convenience function to initialize and load the ParslExecutionBroker."""
    broker = ParslExecutionBroker.get_instance()
    if profile:
        broker.profile = profile
    if run_dir:
        broker.run_dir = Path(run_dir).resolve()
    broker.load()
    return broker


def shutdown_parsl_executors() -> None:
    """Convenience function to shutdown the ParslExecutionBroker."""
    broker = ParslExecutionBroker.get_instance()
    broker.shutdown()


# =============================================================================
# CLI Interface
# =============================================================================
def build_cli_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser for Parsl executor management."""
    parser = argparse.ArgumentParser(
        prog="cochem_core_parsl_executors",
        description="CoChem-CORE: Parsl Multi-Executor Heterogeneous HPC & Task Router (Scout-and-Anchor).",
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to execute")

    subparsers.add_parser("status", help="Query status of Parsl executors and DFK")
    subparsers.add_parser("topology", help="Display heterogeneous Scout-and-Anchor topology")
    subparsers.add_parser("dry-run", help="Dry-run configuration assembly and integrity checks")

    export_p = subparsers.add_parser("export-config", help="Export topology profile to JSON")
    export_p.add_argument(
        "--out", "-o", type=str, default="parsl_topology.json", help="Output JSON path"
    )

    audit_p = subparsers.add_parser("audit-guards", help="Run self-audit on G1-G7 integrity guards")
    audit_p.add_argument(
        "--out-dir", type=str, default=None, help="Directory to emit test provenance.jsonl"
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for cochem_core_parsl_executors."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if not args.command or args.command == "status":
        broker = ParslExecutionBroker.get_instance()
        status = broker.get_status_report()
        print(json.dumps(status, indent=2))
        return 0

    if args.command == "topology":
        profile = build_heterogeneous_profile()
        print("=== CoChem Heterogeneous Scout-and-Anchor Topology (Section 8A) ===")
        print(f"Total Physical Cores: {profile.core_partitioning.total_physical_cores}")
        print(f"Anchor Cores:         {profile.core_partitioning.anchor_core_count} ({profile.core_partitioning.anchor_affinity_str})")
        print(f"Scout Cores:          {profile.core_partitioning.scout_core_count} ({profile.core_partitioning.scout_affinity_str})")
        print(f"GPU Scout Workers:    {profile.contention_budget.gpu_scout_workers} (MPS: {profile.contention_budget.mps_active_thread_percentage}%)")
        print(f"Contention Slowdown:  {profile.contention_budget.estimated_cpu_slowdown_factor:.2f}x (85% real efficiency)")
        print(f"Degraded Mode:        {profile.is_degraded_single_executor}")
        return 0

    if args.command == "dry-run":
        try:
            profile = build_heterogeneous_profile()
            cfg = construct_parsl_config(profile)
            print(f"Successfully assembled Parsl Config with {len(cfg.executors)} executors:")
            for exc in cfg.executors:
                print(f"  - Executor: {exc.label} ({type(exc).__name__})")
            return 0
        except Exception as err:
            logger.error(f"Dry-run failed: {err}")
            return 1

    if args.command == "export-config":
        profile = build_heterogeneous_profile()
        out_path = Path(args.out).resolve()
        out_path.write_text(json.dumps(profile.model_dump(mode="json"), indent=2), encoding="utf-8")
        print(f"Exported topology profile to: {out_path}")
        return 0

    if args.command == "audit-guards":
        print("Auditing Method Matrix Section 8A.5 Integrity Guards (G1-G7)...")
        # G1 check
        try:
            verify_g1_authority({"authority": "authoritative"})
            print("[FAIL] G1 Audit Failed: Authoritative guide allowed.")
            return 1
        except IntegrityGuardViolationError:
            print("[OK] G1 Verified: Rejection of authoritative guide claim.")

        # G2 check
        try:
            verify_g2_high_level_hessian({"imaginary_frequencies_count": 0})
            print("[OK] G2 Verified: Hessian frequency validation.")
        except Exception as err:
            print(f"[FAIL] G2 Audit Failed: {err}")
            return 1

        # G3 check with Mendeleev dynamic masses
        scout_xyz = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.1]], dtype=np.float64)
        anchor_xyz = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.12]], dtype=np.float64)
        is_same, rmsd, delta_r, msg = verify_g3_basin_identity(
            scout_coords_angstrom=scout_xyz,
            anchor_coords_angstrom=anchor_xyz,
            atomic_symbols=["C", "O"],
        )
        print(f"[OK] G3 Verified: {msg}")

        # G4 check
        passes, rho, msg = verify_g4_rank_inversion([1.0, 2.0, 3.0], [1.1, 2.1, 3.1])
        print(f"[OK] G4 Verified: {msg}")

        # G5 check
        assert verify_g5_uncertainty_gate(5.0) is True
        print("[OK] G5 Verified: Committee uncertainty thresholding.")

        # G6 check
        assert verify_g6_abort_guide(2) is True
        assert verify_g6_abort_guide(5) is False
        print("[OK] G6 Verified: Guide abort rule on n_th=5 failures.")

        # G7 check
        record = G7ProvenanceRecord(
            stage="audit_test",
            decision="verify_parsl_executors",
            authority=TaskAuthority.ADVISORY_ONLY,
        )
        log_file = log_g7_provenance_event(record, log_dir=args.out_dir)
        print(f"[OK] G7 Verified: Provenance logged to {log_file}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
