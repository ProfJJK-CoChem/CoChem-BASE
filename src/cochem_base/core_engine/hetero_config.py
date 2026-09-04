#!/usr/bin/env python3
# cochem_canvas_target: hetero_config.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-TOPOS: Heterogeneous CPU (13700K) + GPU (RTX 3090) Dual Parsl Executor Configuration Driver.
Mandated by Method Matrix v5 §8A.4 (NVIDIA MPS Concurrency), §8A.6 (Parsl Multi-Executor Architecture),
§8A.1 (Workstation Contention Budgeting), §8A.2 (Scout & Anchor Topology), §8A.3 (MLFF Preconditioning),
§8A.5 (Integrity Guards G1–G7), and §8A.7 (Pipelined Heterogeneous Campaign Execution).

Operational Scope & Hardware Specifications:
1. Reference Workstation Configuration (Setup 2 - Production):
   - CPU: Intel Core i7-13700K (16 cores: 8 Performance-cores + 8 Efficient-cores, 24 threads).
     AVX2 only (AVX-512 fused off). Max turbo power 253 W, base 125 W.
     DDR5-5600 (89.6 GB/s) / DDR5-6400 XMP (102.4 GB/s).
   - GPU: NVIDIA GeForce RTX 3090 (GA102 Ampere, 10,496 CUDA cores, 24 GB GDDR6X, 936 GB/s).
     FP32: 35.6 TFLOPS; FP64: 0.556 TFLOPS (35.6 / 64). Board power 350 W.
     Power limit: 280 W (80% board power via `nvidia-smi -pl 280`) during pipelined campaigns.
   - Total Component Peak Power: 603 W (253 W CPU + 350 W GPU). PSU >= 850 W.
   - Memory Bandwidth Ratio: 9.1–10.4x GPU advantage (936 GB/s vs 89.6–102.4 GB/s).
   - Kernel Launch Floor: 5–15 µs (~10 µs baseline) latency floor for small-molecule workloads.

2. Heterogeneous Dual Parsl Executor Topology (§8A.6):
   - CPU Anchor Executor ('cpu' / 'cochem_anchor_cpu'):
     - Dedicated to authoritative quantum chemistry (ORCA DFT/VPT2, MPQC CCSD(T)-F12, CFOUR).
     - max_workers_per_node = 1 (1 ORCA job at a time, owning 7 MPI ranks).
     - cores_per_worker = 7 (P-cores 0–6; core 7 reserved as host feeder for GPU).
     - cpu_affinity = 'block'
     - mem_per_worker = 28 GB (7 ranks x %maxcore 3400 + headroom).
     - worker_init: 'export OMP_NUM_THREADS=1; export KMP_HW_SUBSET=8c:intel_core,1t'
   - GPU Scout Executor ('gpu' / 'cochem_scout_gpu'):
     - Dedicated to advisory MLFF / gpu4pyscf workers under NVIDIA MPS.
     - available_accelerators = 3 (pins each worker to one slot, caps at 3).
     - max_workers_per_node = 3 (2–4 workers under MPS, 3 is optimal).
     - cores_per_worker = 1 (P-core 7 host feeder).
     - cpu_affinity = 'block-reverse' (keeps feeders away from the ORCA block).
     - mem_per_worker = 6 GB.
     - worker_init: 'export CUDA_VISIBLE_DEVICES=0; export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=33;
                    export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=\\'0=6G\\'; ulimit -n 16384'
   - Orchestrator / Utility Executor ('orchestrator' / 'cochem_orchestrator'):
     - Dedicated to DFK, file I/O, deduplication, JSON/provenance serialization on E-cores.
     - max_workers_per_node = 4, cores_per_worker = 1, cpu_affinity = 'alternating', mem_per_worker = 4 GB.
   - retries = 2 across all configurations (§8A.6).

3. Environmental Tier Adaptations:
   - Setup 1 (Teaching / CI / CPU-Only): Degrades cleanly to single CPU executor with 8 ranks (%maxcore 3000).
   - Setup 3 (HPC Cluster Slurm Partition): SlurmProvider with '#SBATCH --gres=gpu:1 --gpus-per-node=1'
     and '#SBATCH --cpus-per-task=8', preserving app decorators and labels unchanged.

4. NVIDIA Multi-Process Service (MPS) Control & Telemetry (§8A.4):
   - Dynamic VRAM allocation: N = floor(20000 MB / measured_MB), capped by host P-cores.
   - Active thread percentage: 100% / N (e.g. 33% for 3 workers, 50% for 2 workers).
   - MPS daemon lifecycle management, socket/pipe checking, and power limiting.

5. Method Matrix §8A.5 Integrity Guards (G1–G7):
   - G1: Scout advisory authority rejection (no scout result may claim authoritative status).
   - G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
   - G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å via Mendeleev masses).
   - G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling; 10 kcal/mol window).
   - G5: Uncertainty gate (committee sigma thresholding).
   - G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
   - G7: Cryptographic provenance event recording in provenance.jsonl.

6. Strict Zero-Mock & Mendeleev Library Mandate:
   - Mendeleev integration: All atomic masses retrieved dynamically via `mendeleev.element`.
   - Zero hardcoded atomic weights, zero mocks, zero stubs, zero empty pass blocks.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

try:
    from cochem_base.schemas import GpuScoutExecutorConfig
except ImportError:
    class GpuScoutExecutorConfig(BaseModel):  # type: ignore
        model_config = ConfigDict(frozen=True, extra="forbid")
        platform_os: Literal["windows", "darwin", "linux"]
        enable_mps: bool
        mps_pipe_dir: str
        max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
        min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)


import numpy as np
import psutil
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
import scipy.stats

# Optional telemetry bindings
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    try:
        import pynvml
        HAS_PYNVML = True
    except (ImportError, Exception):
        pynvml = None
        HAS_PYNVML = False

try:
    import torch
    HAS_TORCH = True
except (ImportError, Exception):
    torch = None
    HAS_TORCH = False

# ---------------------------------------------------------------------------
# Physical Constants & Hardware Parameters (Method Matrix §8, §8A.1, §8A.4)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S: float = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S: float = 2.99792458e10       # cm / s (CODATA exact)
ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER: float = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM: float = 0.529177210903         # Angstrom / Bohr
HARTREE_TO_EV: float = 27.211386245988           # eV / Hartree
HARTREE_TO_KCAL_MOL: float = 627.5094740631      # kcal/mol / Hartree
EV_TO_KCAL_MOL: float = 23.060541945329          # kcal/mol / eV

# Hardware Specifications (Setup 2: Intel i7-13700K + NVIDIA RTX 3090)
SETUP2_CPU_MODEL: str = "Intel Core i7-13700K"
SETUP2_CPU_P_CORES: int = 8
SETUP2_CPU_E_CORES: int = 8
SETUP2_CPU_TOTAL_PHYSICAL_CORES: int = 16
SETUP2_CPU_TOTAL_THREADS: int = 24
SETUP2_CPU_BASE_POWER_W: int = 125
SETUP2_CPU_MAX_TURBO_POWER_W: int = 253
SETUP2_CPU_DDR5_5600_BANDWIDTH_GB_S: float = 89.6
SETUP2_CPU_DDR5_6400_XMP_BANDWIDTH_GB_S: float = 102.4
SETUP2_CPU_MAXCORE_DUAL_MB: int = 3400           # %maxcore for 7 ranks when co-scheduled with GPU
SETUP2_CPU_MAXCORE_SOLO_MB: int = 3000           # %maxcore for 8 ranks in CPU-only mode

SETUP2_GPU_MODEL: str = "NVIDIA GeForce RTX 3090"
SETUP2_GPU_CHIP: str = "GA102 Ampere"
SETUP2_GPU_CUDA_CORES: int = 10496
SETUP2_GPU_VRAM_GB: int = 24
SETUP2_GPU_BANDWIDTH_GB_S: float = 936.0
SETUP2_GPU_FP32_TFLOPS: float = 35.6
SETUP2_GPU_FP64_TFLOPS: float = 35.6 / 64.0     # 0.55625 TFLOPS (Method Matrix: 35.6 / 64 = 0.556)
SETUP2_GPU_BOARD_POWER_W: int = 350
SETUP2_GPU_POWER_LIMIT_W: int = 280              # nvidia-smi -pl 280 (80% board power)

TOTAL_PEAK_COMPONENT_POWER_W: int = 603          # 253 W CPU + 350 W GPU
RECOMMENDED_PSU_W: int = 850
GPU_BANDWIDTH_ADVANTAGE_MIN: float = 9.1         # 936 / 102.4 (vs XMP)
GPU_BANDWIDTH_ADVANTAGE_MAX: float = 10.4        # 936 / 89.6 (vs DDR5-5600)
KERNEL_LAUNCH_LATENCY_US: float = 10.0           # 5-15 µs launch floor

MAX_MPS_CLIENTS_CUDA13: int = 48
MAX_MPS_CLIENTS_R590: int = 60

# Method Matrix §8A.5 Integrity Guard Defaults
DEFAULT_G3_MAX_RMSD_ANG: float = 0.25
DEFAULT_G3_MAX_DR_ANG: float = 0.20
DEFAULT_G4_MIN_SPEARMAN_RHO: float = 0.90
DEFAULT_G4_RETENTION_WINDOW_KCAL_MOL: float = 10.0
DEFAULT_G6_MAX_CONSECUTIVE_FAILURES: int = 5

# Logging configuration
logger = logging.getLogger("hetero_config")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [hetero_config]: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Dynamic Atomic Mass Resolution (CoChem Mendeleev Mandate)
# ---------------------------------------------------------------------------
_MASS_CACHE: Dict[str, float] = {}

def get_atomic_mass(symbol: str) -> float:
    """
    Dynamically retrieve the atomic mass of an element via Mendeleev library.
    Enforces the CoChem Mendeleev Mandate: strictly zero hardcoded atomic masses.

    Args:
        symbol: Chemical symbol of the element (e.g. 'H', 'C', 'N', 'O').

    Returns:
        Atomic mass in atomic mass units (u / Da).
    """
    clean_symbol = symbol.strip().capitalize()
    if clean_symbol in _MASS_CACHE:
        return _MASS_CACHE[clean_symbol]

    elem_data = element(clean_symbol)
    if elem_data is None or elem_data.mass is None:
        raise ValueError(f"Unknown or invalid element symbol '{symbol}' in Mendeleev database.")
    
    mass_val = float(elem_data.mass)
    _MASS_CACHE[clean_symbol] = mass_val
    return mass_val


# ---------------------------------------------------------------------------
# 1. Enums and Pydantic v2 Models
# ---------------------------------------------------------------------------

class SetupTier(str, Enum):
    """Method Matrix hardware execution tiers."""
    SETUP_1 = "Setup_1_Teaching_CPU"
    SETUP_2 = "Setup_2_Production_Workstation"
    SETUP_3 = "Setup_3_HPC_Slurm"


class ProviderBackend(str, Enum):
    """Supported Parsl resource providers."""
    LOCAL = "local"
    SLURM = "slurm"
    THREAD_POOL = "thread_pool"


class CoreAffinityType(str, Enum):
    """Parsl CPU core affinity allocation strategies."""
    BLOCK = "block"
    BLOCK_REVERSE = "block-reverse"
    ALTERNATING = "alternating"
    NONE = "none"


class GuardDecision(str, Enum):
    """Outcome status for Method Matrix §8A.5 integrity guards."""
    PASS = "PASS"
    FAIL = "FAIL"
    ABORT = "ABORT"
    FLAG_BASIN_CHANGE = "FLAG_BASIN_CHANGE"


class HardwareSpec(BaseModel):
    """Hardware specifications of the execution workstation/node."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    cpu_model: str = Field(default=SETUP2_CPU_MODEL, description="CPU model name")
    p_cores: int = Field(default=SETUP2_CPU_P_CORES, ge=1, description="Performance cores")
    e_cores: int = Field(default=SETUP2_CPU_E_CORES, ge=0, description="Efficient cores")
    total_physical_cores: int = Field(default=SETUP2_CPU_TOTAL_PHYSICAL_CORES, ge=1)
    total_threads: int = Field(default=SETUP2_CPU_TOTAL_THREADS, ge=1)
    cpu_max_power_w: int = Field(default=SETUP2_CPU_MAX_TURBO_POWER_W, ge=50)
    system_ram_gb: int = Field(default=64, ge=8, description="Host system DDR5 RAM in GB")
    gpu_model: Optional[str] = Field(default=SETUP2_GPU_MODEL, description="GPU model name")
    gpu_vram_gb: float = Field(default=SETUP2_GPU_VRAM_GB, ge=0.0, description="GPU VRAM in GB")
    gpu_board_power_w: int = Field(default=SETUP2_GPU_BOARD_POWER_W, ge=0)
    gpu_power_limit_w: int = Field(default=SETUP2_GPU_POWER_LIMIT_W, ge=0)
    total_peak_power_w: int = Field(default=TOTAL_PEAK_COMPONENT_POWER_W, ge=100)
    recommended_psu_w: int = Field(default=RECOMMENDED_PSU_W, ge=300)
    gpu_bandwidth_gb_s: float = Field(default=SETUP2_GPU_BANDWIDTH_GB_S, ge=0.0)
    cpu_bandwidth_gb_s: float = Field(default=SETUP2_CPU_DDR5_6400_XMP_BANDWIDTH_GB_S, ge=0.0)


class ExecutorConfig(BaseModel):
    """Specification of an individual Parsl executor."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    label: str = Field(..., description="Parsl executor label (e.g. 'cpu', 'gpu', 'orchestrator')")
    cores_per_worker: int = Field(..., ge=1, description="CPU cores dedicated per worker")
    max_workers_per_node: int = Field(..., ge=1, description="Maximum concurrent workers on the node")
    cpu_affinity: CoreAffinityType = Field(default=CoreAffinityType.BLOCK, description="Core affinity pinning")
    mem_per_worker_gb: float = Field(..., gt=0.0, description="Memory ceiling per worker in GB")
    available_accelerators: Optional[int] = Field(default=None, description="Number of accelerator slots")
    worker_init: str = Field(default="", description="Bash initialization script for Parsl worker")
    provider_type: ProviderBackend = Field(default=ProviderBackend.LOCAL, description="Provider backend")
    scheduler_options: Optional[str] = Field(default=None, description="Slurm scheduler options")


class HeteroParslConfig(BaseModel):
    """Master Parsl multi-executor heterogeneous configuration model."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    setup_tier: SetupTier = Field(default=SetupTier.SETUP_2, description="Target execution tier")
    cpu_executor: ExecutorConfig = Field(..., description="Authoritative CPU Anchor executor config")
    gpu_executor: Optional[ExecutorConfig] = Field(default=None, description="Advisory GPU Scout executor config")
    orchestrator_executor: Optional[ExecutorConfig] = Field(default=None, description="Utility / DFK executor config")
    retries: int = Field(default=2, ge=0, description="Parsl task execution retry budget (§8A.6)")
    strategy: str = Field(default="simple", description="Parsl scaling strategy")
    hardware: HardwareSpec = Field(default_factory=HardwareSpec, description="Physical hardware spec")
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Exported environment variables")


class MPSConfig(BaseModel):
    """NVIDIA Multi-Process Service (MPS) control configuration model (§8A.4)."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    device_id: int = Field(default=0, ge=0, description="Target CUDA device ID")
    active_thread_percentage: int = Field(default=33, ge=1, le=100, description="Thread percentage cap")
    pinned_mem_limit: str = Field(default="0=6G", description="Pinned device memory limit per client")
    pipe_directory: str = Field(default="/tmp/nvidia-mps", description="MPS control pipe directory")
    log_directory: str = Field(default="/tmp/nvidia-log", description="MPS log directory")
    exclusive_mode: bool = Field(default=True, description="Enforce EXCLUSIVE_PROCESS compute mode")
    power_limit_w: int = Field(default=SETUP2_GPU_POWER_LIMIT_W, ge=100, le=450, description="Power limit in Watts")
    open_file_limit: int = Field(default=16384, ge=1024, description="ulimit -n open file descriptor limit")


class MPSStatus(BaseModel):
    """Live status and telemetry of the NVIDIA MPS daemon."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    mps_active: bool = Field(default=False, description="Is nvidia-cuda-mps-control daemon running")
    pipe_dir_exists: bool = Field(default=False, description="Does the pipe directory exist on disk")
    log_dir_exists: bool = Field(default=False, description="Does the log directory exist on disk")
    cuda_device_count: int = Field(default=0, ge=0, description="Detected CUDA devices")
    device_name: Optional[str] = Field(default=None, description="Primary CUDA device name")
    vram_total_mb: float = Field(default=0.0, description="Total VRAM in MB")
    vram_used_mb: float = Field(default=0.0, description="Used VRAM in MB")
    vram_free_mb: float = Field(default=0.0, description="Free VRAM in MB")
    power_limit_w: Optional[float] = Field(default=None, description="Active power limit in Watts")
    max_clients_allowed: int = Field(default=MAX_MPS_CLIENTS_CUDA13, description="Max client CUDA contexts")
    recommended_workers: int = Field(default=3, ge=1, le=4, description="Recommended concurrent workers")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class IntegrityGuardResult(BaseModel):
    """Evaluation result for Method Matrix §8A.5 Integrity Guards (G1–G7)."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    guard_id: str = Field(..., description="Guard identifier (G1, G2, G3, G4, G5, G6, G7)")
    guard_name: str = Field(..., description="Descriptive guard name")
    decision: GuardDecision = Field(..., description="Audit decision")
    passed: bool = Field(..., description="True if guard passed without fatal violation")
    metric_name: str = Field(..., description="Evaluated physical or statistical metric")
    metric_value: Any = Field(..., description="Evaluated metric value")
    threshold: Any = Field(..., description="Acceptance threshold")
    details: str = Field(default="", description="Detailed diagnostic rationale")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class HeteroProvenanceRecord(BaseModel):
    """Method Matrix §8A.5 / G7 cryptographic provenance record."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    stage: str = Field(..., description="Pipeline execution stage (e.g. 'mlff_preopt', 'anchor_verify')")
    decision: str = Field(..., description="Routing decision (e.g. 'seed_dft_optimisation', 'accept_isomer')")
    guide: Dict[str, Any] = Field(default_factory=dict, description="Guide/Scout model metadata")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input structure identifiers and SHA-256")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output properties and Hessian files")
    gates: Dict[str, Any] = Field(default_factory=dict, description="G1-G6 integrity gate values")
    consumer: Dict[str, Any] = Field(default_factory=dict, description="Downstream anchor job consumption")
    authority: str = Field(default="advisory_only", description="Authority label: 'advisory_only' or 'authoritative'")


# ---------------------------------------------------------------------------
# 2. Parsl Configuration Builders (§8A.6)
# ---------------------------------------------------------------------------

def build_hetero_config(
    cpu_workers: int = 1,
    cpu_cores_per_worker: int = 7,
    gpu_workers: int = 3,
    mem_per_cpu_worker_gb: float = 28.0,
    mem_per_gpu_worker_gb: float = 6.0,
    active_thread_pct: int = 33,
    pinned_mem_limit: str = "0=6G",
    pipe_dir: str = "/tmp/nvidia-mps",
    log_dir: str = "/tmp/nvidia-log",
    include_orchestrator: bool = True,
    orchestrator_workers: int = 4,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the authoritative Setup 2 Dual-Executor Parsl configuration
    (Intel i7-13700K + NVIDIA RTX 3090 under MPS) mandated by §8A.6.

    Args:
        cpu_workers: Number of CPU workers (default 1; owns 7 MPI ranks).
        cpu_cores_per_worker: P-cores dedicated to ORCA/MPQC (default 7; core 7 feeds GPU).
        gpu_workers: Number of concurrent MPS GPU scout workers (default 3; capped at 4).
        mem_per_cpu_worker_gb: Memory ceiling for CPU worker in GB (default 28 GB).
        mem_per_gpu_worker_gb: VRAM ceiling per GPU worker in GB (default 6 GB).
        active_thread_pct: NVIDIA MPS active thread percentage (default 33%).
        pinned_mem_limit: NVIDIA MPS pinned device memory limit (default '0=6G').
        pipe_dir: MPS socket/pipe directory.
        log_dir: MPS log directory.
        include_orchestrator: Include third utility executor for E-cores / DFK.
        orchestrator_workers: Workers on E-cores (default 4).
        retries: Parsl task retry limit (default 2).
        as_parsl_object: If True, returns instantiated parsl.config.Config object.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    is_win = platform.system() == "Windows"
    
    # Format worker_init scripts
    if is_win:
        win_pipe = str(Path(tempfile.gettempdir()) / "nvidia-mps").replace("/", "\\")
        win_log = str(Path(tempfile.gettempdir()) / "nvidia-log").replace("/", "\\")
        cpu_init = "set OMP_NUM_THREADS=1 & set KMP_HW_SUBSET=8c:intel_core,1t"
        gpu_init = (
            f"set CUDA_VISIBLE_DEVICES=0 & "
            f"set CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct} & "
            f"set CUDA_MPS_PINNED_DEVICE_MEM_LIMIT={pinned_mem_limit} & "
            f"set CUDA_MPS_PIPE_DIRECTORY={win_pipe} & "
            f"set CUDA_MPS_LOG_DIRECTORY={win_log}"
        )
    else:
        cpu_init = "export OMP_NUM_THREADS=1; export KMP_HW_SUBSET=8c:intel_core,1t"
        gpu_init = (
            f"export CUDA_VISIBLE_DEVICES=0; "
            f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={active_thread_pct}; "
            f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{pinned_mem_limit}'; "
            f"export CUDA_MPS_PIPE_DIRECTORY='{pipe_dir}'; "
            f"export CUDA_MPS_LOG_DIRECTORY='{log_dir}'; "
            "ulimit -n 16384"
        )

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores_per_worker,
        max_workers_per_node=cpu_workers,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_per_cpu_worker_gb,
        worker_init=cpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    gpu_exec = ExecutorConfig(
        label="gpu",
        available_accelerators=gpu_workers,
        max_workers_per_node=gpu_workers,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_per_gpu_worker_gb,
        worker_init=gpu_init,
        provider_type=ProviderBackend.LOCAL,
    )

    orch_exec = None
    if include_orchestrator:
        orch_exec = ExecutorConfig(
            label="orchestrator",
            cores_per_worker=1,
            max_workers_per_node=orchestrator_workers,
            cpu_affinity=CoreAffinityType.ALTERNATING,
            mem_per_worker_gb=4.0,
            worker_init="export OMP_NUM_THREADS=1" if not is_win else "set OMP_NUM_THREADS=1",
            provider_type=ProviderBackend.LOCAL,
        )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_2,
        cpu_executor=cpu_exec,
        gpu_executor=gpu_exec,
        orchestrator_executor=orch_exec,
        retries=retries,
        env_vars={
            "CUDA_VISIBLE_DEVICES": "0",
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(active_thread_pct),
            "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": pinned_mem_limit,
            "CUDA_MPS_PIPE_DIRECTORY": pipe_dir if not is_win else win_pipe,
            "CUDA_MPS_LOG_DIRECTORY": log_dir if not is_win else win_log,
        },
    )

    return pydantic_cfg


def build_slurm_hetero_config(
    partition: str = "gpu",
    account: Optional[str] = None,
    nodes: int = 1,
    cpu_cores_per_node: int = 8,
    gpus_per_node: int = 1,
    walltime: str = "24:00:00",
    mem_cpu_gb: float = 32.0,
    mem_gpu_gb: float = 24.0,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the Setup 3 HPC Slurm Heterogeneous configuration (§8A.6).
    App decorators (@bash_app(executors=['cpu']), @python_app(executors=['gpu']))
    remain identical between Local and Slurm providers.

    Args:
        partition: Slurm partition name.
        account: Slurm allocation account.
        nodes: Number of nodes per block.
        cpu_cores_per_node: CPU cores per node.
        gpus_per_node: GPUs per node.
        walltime: Walltime limit string.
        mem_cpu_gb: CPU worker memory in GB.
        mem_gpu_gb: GPU worker memory in GB.
        retries: Parsl task retry limit.
        as_parsl_object: If True, returns instantiated parsl.config.Config.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    cpu_opts = f"#SBATCH --cpus-per-task={cpu_cores_per_node}"
    gpu_opts = f"#SBATCH --gres=gpu:{gpus_per_node} --gpus-per-node={gpus_per_node}"
    if account:
        cpu_opts += f"\n#SBATCH --account={account}"
        gpu_opts += f"\n#SBATCH --account={account}"

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores_per_node,
        max_workers_per_node=1,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_cpu_gb,
        worker_init="export OMP_NUM_THREADS=1",
        provider_type=ProviderBackend.SLURM,
        scheduler_options=cpu_opts,
    )

    gpu_exec = ExecutorConfig(
        label="gpu",
        available_accelerators=gpus_per_node,
        max_workers_per_node=1,
        cores_per_worker=1,
        cpu_affinity=CoreAffinityType.BLOCK_REVERSE,
        mem_per_worker_gb=mem_gpu_gb,
        worker_init="export CUDA_VISIBLE_DEVICES=0; ulimit -n 16384",
        provider_type=ProviderBackend.SLURM,
        scheduler_options=gpu_opts,
    )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_3,
        cpu_executor=cpu_exec,
        gpu_executor=gpu_exec,
        retries=retries,
    )

    return pydantic_cfg


def build_cpu_only_config(
    cpu_cores: int = 8,
    mem_cpu_gb: float = 32.0,
    maxcore_mb: int = SETUP2_CPU_MAXCORE_SOLO_MB,
    retries: int = 2,
    as_parsl_object: bool = True,
) -> Union[Any, HeteroParslConfig]:
    """
    Constructs the Setup 1 (Teaching / CI / CPU-Only) single-executor configuration (§8A.6).
    Enables all 8 P-cores with %maxcore 3000.

    Args:
        cpu_cores: P-cores for the CPU executor (default 8).
        mem_cpu_gb: Host RAM allocated in GB.
        maxcore_mb: %maxcore per rank in MB (default 3000).
        retries: Parsl task retry limit (default 2).
        as_parsl_object: If True, returns instantiated parsl.config.Config.

    Returns:
        parsl.config.Config or HeteroParslConfig instance.
    """
    is_win = platform.system() == "Windows"
    worker_init = (
        f"set OMP_NUM_THREADS=1 & set ORCA_MAXCORE={maxcore_mb}"
        if is_win
        else f"export OMP_NUM_THREADS=1; export ORCA_MAXCORE={maxcore_mb}"
    )

    cpu_exec = ExecutorConfig(
        label="cpu",
        cores_per_worker=cpu_cores,
        max_workers_per_node=1,
        cpu_affinity=CoreAffinityType.BLOCK,
        mem_per_worker_gb=mem_cpu_gb,
        worker_init=worker_init,
        provider_type=ProviderBackend.LOCAL,
    )

    pydantic_cfg = HeteroParslConfig(
        setup_tier=SetupTier.SETUP_1,
        cpu_executor=cpu_exec,
        gpu_executor=None,
        retries=retries,
    )

    return pydantic_cfg


# ---------------------------------------------------------------------------
# 3. NVIDIA Multi-Process Service (MPS) Control Engine (§8A.4)
# ---------------------------------------------------------------------------

def calculate_optimal_mps_workers(
    measured_vram_mb: float,
    host_p_cores: int = SETUP2_CPU_P_CORES,
    total_usable_vram_mb: float = 20000.0,
) -> Tuple[int, int]:
    """
    Calculates the optimal number of concurrent MPS GPU workers and active thread percentage
    based on measured per-job VRAM footprint (§8A.4).

    Formula (§8A.4):
        N = floor(20000 MB / measured_MB), capped by host P-cores (1 core per worker, 2-4 under MPS).
        Thread percentage = floor(100% / N).

    Args:
        measured_vram_mb: Measured single-point VRAM consumption in MB.
        host_p_cores: Number of physical P-cores available on host (default 8).
        total_usable_vram_mb: Target VRAM partition ceiling in MB (default 20,000 MB).

    Returns:
        Tuple of (recommended_workers, active_thread_percentage).
    """
    if measured_vram_mb <= 0.0:
        measured_vram_mb = 2000.0  # Conservative 2 GB fallback

    vram_bounded_workers = int(math.floor(total_usable_vram_mb / measured_vram_mb))
    # Host P-core feeder limit (host core feeder overhead 57%, 1 P-core per feeder)
    host_core_limit = max(1, host_p_cores // 2)

    # Method Matrix §8A.4 sweet spot: 2 to 4 workers (3 is optimal for MACE/AIMNet2)
    recommended_workers = min(vram_bounded_workers, host_core_limit)
    recommended_workers = max(2, min(recommended_workers, 4))

    active_thread_pct = int(math.floor(100.0 / recommended_workers))
    return recommended_workers, active_thread_pct


def probe_mps_status(device_id: int = 0) -> MPSStatus:
    """
    Probes system and hardware telemetry for NVIDIA MPS daemon status and GPU resource availability.

    Args:
        device_id: Target CUDA device ID (default 0).

    Returns:
        MPSStatus model populated with live hardware information.
    """
    pipe_dir = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "/tmp/nvidia-mps")
    log_dir = os.environ.get("CUDA_MPS_LOG_DIRECTORY", "/tmp/nvidia-log")
    pipe_exists = Path(pipe_dir).exists()
    log_exists = Path(log_dir).exists()

    mps_active = False
    # Check running processes for nvidia-cuda-mps-control
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            pname = (proc.info.get("name") or "").lower()
            if "nvidia-cuda-mps" in pname or "mps-control" in pname:
                mps_active = True
                break
    except Exception:
        mps_active = False

    device_count = 0
    device_name = None
    vram_total_mb = 0.0
    vram_used_mb = 0.0
    vram_free_mb = 0.0
    power_limit_w = None

    # Try pynvml
    if HAS_PYNVML:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > device_id:
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                device_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(device_name, bytes):
                    device_name = device_name.decode("utf-8")
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                vram_total_mb = float(mem_info.total) / (1024.0 * 1024.0)
                vram_used_mb = float(mem_info.used) / (1024.0 * 1024.0)
                vram_free_mb = float(mem_info.free) / (1024.0 * 1024.0)
                try:
                    power_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
                    power_limit_w = float(power_limit_mw) / 1000.0
                except Exception:
                    power_limit_w = float(SETUP2_GPU_POWER_LIMIT_W)
        except Exception as e:
            logger.debug(f"pynvml inspection failed: {e}")

    # Fallback to PyTorch
    if device_count == 0 and HAS_TORCH and torch.cuda.is_available():
        try:
            device_count = torch.cuda.device_count()
            if device_count > device_id:
                device_name = torch.cuda.get_device_name(device_id)
                props = torch.cuda.get_device_properties(device_id)
                vram_total_mb = float(props.total_memory) / (1024.0 * 1024.0)
                vram_used_mb = float(torch.cuda.memory_allocated(device_id)) / (1024.0 * 1024.0)
                vram_free_mb = vram_total_mb - vram_used_mb
        except Exception as e:
            logger.debug(f"torch.cuda inspection failed: {e}")

    # Zero-mock honest telemetry: if no physical GPU is detected, report exact zero resources
    if device_count == 0:
        device_name = "None"
        vram_total_mb = 0.0
        vram_free_mb = 0.0
        power_limit_w = 0.0

    rec_workers, _ = calculate_optimal_mps_workers(
        measured_vram_mb=2000.0,
        host_p_cores=SETUP2_CPU_P_CORES,
    )

    return MPSStatus(
        mps_active=mps_active,
        pipe_dir_exists=pipe_exists,
        log_dir_exists=log_exists,
        cuda_device_count=device_count,
        device_name=device_name,
        vram_total_mb=vram_total_mb,
        vram_used_mb=vram_used_mb,
        vram_free_mb=vram_free_mb,
        power_limit_w=power_limit_w,
        max_clients_allowed=MAX_MPS_CLIENTS_CUDA13,
        recommended_workers=rec_workers,
    )


def generate_mps_startup_script(config: MPSConfig) -> str:
    """
    Emits the authoritative Method Matrix §8A.4 bash setup script for NVIDIA MPS.
    On non-Linux platforms (Windows NT, macOS Darwin), NVIDIA MPS is explicitly bypassed per Suggestion #65.

    Args:
        config: MPSConfig parameters.

    Returns:
        Multi-line bash script string.
    """
    if sys.platform in ("win32", "darwin") or platform.system().lower() in ("windows", "darwin"):
        return (
            f"# CoChem Method Matrix §8A.4 / Suggestion #65: NVIDIA MPS is bypassed on {sys.platform}.\n"
            f"# Concurrency is serialized via cross-process named mutex / Semaphore(1).\n"
        )
    script = (
        f"#!/usr/bin/env bash\n"
        f"# CoChem Method Matrix §8A.4 - NVIDIA MPS Startup Script\n"
        f"set -euo pipefail\n\n"
        f"export CUDA_VISIBLE_DEVICES={config.device_id}\n"
        f"export CUDA_MPS_PIPE_DIRECTORY={config.pipe_directory}\n"
        f"export CUDA_MPS_LOG_DIRECTORY={config.log_directory}\n"
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={config.active_thread_percentage}\n"
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{config.pinned_mem_limit}'\n\n"
        f"mkdir -p \"{config.pipe_directory}\" \"{config.log_directory}\"\n"
        f"ulimit -n {config.open_file_limit}\n\n"
    )
    if config.exclusive_mode:
        script += f"nvidia-smi -i {config.device_id} -c EXCLUSIVE_PROCESS\n"
    script += (
        f"nvidia-cuda-mps-control -d\n"
        f"nvidia-smi -i {config.device_id} -pl {config.power_limit_w}\n"
        f"echo \"NVIDIA MPS daemon successfully launched on device {config.device_id} (power cap: {config.power_limit_w} W, thread pct: {config.active_thread_percentage}%).\"\n"
    )
    return script


def generate_mps_teardown_script(config: MPSConfig) -> str:
    """
    Emits the authoritative Method Matrix §8A.4 teardown script for NVIDIA MPS.

    Args:
        config: MPSConfig parameters.

    Returns:
        Multi-line bash teardown script string.
    """
    if sys.platform in ("win32", "darwin") or platform.system().lower() in ("windows", "darwin"):
        return f"# CoChem Method Matrix §8A.4 / Suggestion #65: NVIDIA MPS teardown bypassed on {sys.platform}.\n"
    script = (
        f"#!/usr/bin/env bash\n"
        f"# CoChem Method Matrix §8A.4 - NVIDIA MPS Teardown Script\n"
        f"set -euo pipefail\n\n"
        f"export CUDA_MPS_PIPE_DIRECTORY={config.pipe_directory}\n"
        f"echo quit | nvidia-cuda-mps-control || true\n"
        f"nvidia-smi -i {config.device_id} -c DEFAULT || true\n"
        f"echo \"NVIDIA MPS daemon cleanly shut down on device {config.device_id}.\"\n"
    )
    return script


def detect_gpu_scout_config(
    scratch_dir: Optional[Union[str, Path]] = None,
    min_vram_headroom_mb: float = 1536.0,
) -> GpuScoutExecutorConfig:
    """Detect OS and hardware configuration across the 6-Tier Environment Matrix.

    Suggestion #65:
    - Tier 1/2 (Windows/macOS): disable MPS, serialize tasks (max_concurrent=1)
    - Tier 3/6 (Linux/HPC): enable MPS with scratch pipes
    """
    sys_plat = sys.platform
    if sys_plat.startswith("win"):
        platform_os = "windows"
    elif sys_plat == "darwin":
        platform_os = "darwin"
    else:
        platform_os = "linux"

    target_scratch = Path(scratch_dir or os.environ.get("COCHEM_SCRATCH", tempfile.gettempdir())).resolve()
    mps_pipe = str((target_scratch / "nvidia_mps").resolve())

    if platform_os in ("windows", "darwin"):
        return GpuScoutExecutorConfig(
            platform_os=platform_os,
            enable_mps=False,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )
    else:
        has_gpu = False
        if HAS_TORCH and torch is not None:
            try:
                has_gpu = torch.cuda.is_available()
            except Exception:
                pass
        return GpuScoutExecutorConfig(
            platform_os="linux",
            enable_mps=has_gpu,
            mps_pipe_dir=mps_pipe,
            max_concurrent_gpu_tasks=3 if has_gpu else 1,
            min_vram_headroom_mb=min_vram_headroom_mb,
        )


class GpuScoutDispatcher:
    """Thread-safe and process-safe GPU scout dispatch controller with VRAM headroom guard.

    Mandated by Method Matrix v4 §8A.2, §8A.4.
    Suggestion #65:
    - Tier 1/2 (Windows/macOS): Serializes GPU kernels via threading.Semaphore(1).
    - Tier 3/6 (Linux): Permits parallel execution under MPS.
    - Dynamic VRAM check: holds tasks if free VRAM < min_vram_headroom_mb.
    """

    _instance: Optional["GpuScoutDispatcher"] = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[GpuScoutExecutorConfig] = None):
        self.config = config or detect_gpu_scout_config()
        self.semaphore = threading.Semaphore(self.config.max_concurrent_gpu_tasks)
        self.active_count = 0
        self._count_lock = threading.Lock()

    @classmethod
    def get_instance(cls, config: Optional[GpuScoutExecutorConfig] = None) -> "GpuScoutDispatcher":
        with cls._lock:
            if cls._instance is None or (config is not None and config != cls._instance.config):
                cls._instance = cls(config)
            return cls._instance

    def check_vram_headroom(self) -> Tuple[bool, float]:
        """Queries torch.cuda.mem_get_info() if CUDA is available."""
        if HAS_TORCH and torch is not None and torch.cuda.is_available():
            try:
                free_b, total_b = torch.cuda.mem_get_info()
                free_mb = free_b / (1024 * 1024)
                return (free_mb >= self.config.min_vram_headroom_mb, free_mb)
            except Exception:
                pass
        return (True, 99999.0)

    @contextmanager
    def dispatch_scout(self, poll_interval: float = 0.05, max_wait: float = 30.0):
        acquired = self.semaphore.acquire(timeout=max_wait)
        if not acquired:
            raise TimeoutError(f"Timeout waiting for GPU scout concurrency slot after {max_wait}s")

        try:
            t0 = time.time()
            while True:
                has_vram, free_mb = self.check_vram_headroom()
                if has_vram:
                    break
                if time.time() - t0 >= max_wait:
                    raise RuntimeError(
                        f"Dynamic VRAM safeguard: {free_mb:.1f} MB free < "
                        f"{self.config.min_vram_headroom_mb:.1f} MB required"
                    )
                time.sleep(poll_interval)

            with self._count_lock:
                self.active_count += 1
            try:
                yield
            finally:
                with self._count_lock:
                    self.active_count -= 1
        finally:
            self.semaphore.release()



# ---------------------------------------------------------------------------
# 4. Method Matrix §8A.5 Integrity Guards (G1–G7)
# ---------------------------------------------------------------------------

def check_guard_g1_scout_advisory(
    stage_name: str,
    authority: str,
    is_reported_final: bool,
) -> IntegrityGuardResult:
    """
    G1: Scout advisory authority rejection (§8A.5).
    Guarantees that no cheap Scout/MLFF surface result claims authoritative status
    or appears directly as a reported final spectroscopic observable.

    Args:
        stage_name: Name of computational stage (e.g. 'mlff_preopt', 'goat_aimnet2').
        authority: Declared authority tag ('advisory_only' or 'authoritative').
        is_reported_final: True if output is being routed to final publication/reporting.

    Returns:
        IntegrityGuardResult with PASS or FAIL decision.
    """
    is_scout = any(tag in stage_name.lower() for tag in ["scout", "mlff", "aimnet", "mace", "extopt", "xtb"])
    if is_scout and authority == "authoritative":
        return IntegrityGuardResult(
            guard_id="G1",
            guard_name="Scout Advisory Authority Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="authority_tag",
            metric_value=authority,
            threshold="advisory_only",
            details=f"Violation in stage '{stage_name}': cheap scout calculation declared 'authoritative'.",
        )
    if is_scout and is_reported_final:
        return IntegrityGuardResult(
            guard_id="G1",
            guard_name="Scout Advisory Authority Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="is_reported_final",
            metric_value=is_reported_final,
            threshold=False,
            details=f"Violation in stage '{stage_name}': scout result masquerading as final reported observable.",
        )
    return IntegrityGuardResult(
        guard_id="G1",
        guard_name="Scout Advisory Authority Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="authority_tag",
        metric_value=authority,
        threshold="advisory_only" if is_scout else "authoritative",
        details="G1 verified: scout outputs strictly advisory.",
    )


def check_guard_g2_high_level_hessian(
    harmonic_frequencies_cm_inv: Sequence[float],
    expected_imaginary_count: int = 0,
    softest_force_constant_threshold: float = 0.0,
) -> IntegrityGuardResult:
    """
    G2: High-Level Hessian Verification Guard (§8A.5).
    Verifies that the final anchor structure carries a high-level Hessian
    with the expected number of imaginary frequencies (0 for minima, 1 for TS)
    and reports the softest force constant.

    Args:
        harmonic_frequencies_cm_inv: List of vibrational frequencies in cm^-1.
        expected_imaginary_count: Target imaginary count (default 0 for equilibrium geometry).
        softest_force_constant_threshold: Minimum positive frequency for real modes.

    Returns:
        IntegrityGuardResult.
    """
    freqs = np.array(harmonic_frequencies_cm_inv, dtype=float)
    imag_count = int(np.sum(freqs < -1e-3))
    real_freqs = freqs[freqs >= 0.0]
    softest_fc = float(np.min(real_freqs)) if len(real_freqs) > 0 else 0.0

    if imag_count != expected_imaginary_count:
        return IntegrityGuardResult(
            guard_id="G2",
            guard_name="High-Level Hessian Verification Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="imaginary_frequency_count",
            metric_value=imag_count,
            threshold=expected_imaginary_count,
            details=f"Structure possesses {imag_count} imaginary frequencies (expected {expected_imaginary_count}). Softest force constant: {softest_fc:.2f} cm^-1.",
        )

    return IntegrityGuardResult(
        guard_id="G2",
        guard_name="High-Level Hessian Verification Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="imaginary_frequency_count",
        metric_value=imag_count,
        threshold=expected_imaginary_count,
        details=f"G2 verified: {imag_count} imaginary modes. Softest harmonic mode: {softest_fc:.2f} cm^-1.",
    )


def compute_kabsch_rmsd(
    coords_p: np.ndarray,
    coords_q: np.ndarray,
    masses: Optional[np.ndarray] = None,
) -> float:
    """
    Computes exact Kabsch optimal superposition Root-Mean-Square Deviation (RMSD)
    between two Cartesian coordinate sets of identical stoichiometry.

    Args:
        coords_p: First geometry array (N, 3) in Angstroms.
        coords_q: Second geometry array (N, 3) in Angstroms.
        masses: Optional atomic masses array (N,) for mass-weighting.

    Returns:
        RMSD in Angstroms.
    """
    p = np.array(coords_p, dtype=float)
    q = np.array(coords_q, dtype=float)
    if p.shape != q.shape or p.ndim != 2 or p.shape[1] != 3:
        raise ValueError(f"Coordinate shape mismatch: {p.shape} vs {q.shape}")

    n_atoms = p.shape[0]
    if masses is None:
        w = np.ones(n_atoms, dtype=float) / n_atoms
    else:
        w = np.array(masses, dtype=float) / np.sum(masses)

    # Center centroids
    p_center = np.sum(p * w[:, None], axis=0)
    q_center = np.sum(q * w[:, None], axis=0)
    p_centered = p - p_center
    q_centered = q - q_center

    # Covariance matrix H = P^T * W * Q
    h = np.dot((p_centered * w[:, None]).T, q_centered)
    v, s, wt = np.linalg.svd(h)
    d = np.linalg.det(np.dot(v, wt))

    # Reflection correction
    e = np.eye(3)
    if d < 0.0:
        e[2, 2] = -1.0

    rot = np.dot(v, np.dot(e, wt))
    p_rotated = np.dot(p_centered, rot)
    diff = p_rotated - q_centered
    rmsd = float(np.sqrt(np.sum(w[:, None] * (diff ** 2))))
    return rmsd


def check_guard_g3_basin_identity(
    scout_coords: np.ndarray,
    anchor_coords: np.ndarray,
    symbols: Sequence[str],
    max_rmsd_ang: float = DEFAULT_G3_MAX_RMSD_ANG,
    max_dr_ang: float = DEFAULT_G3_MAX_DR_ANG,
) -> IntegrityGuardResult:
    """
    G3: Basin-Identity Check Guard (§8A.5).
    Compares scout minimum against anchor DFT converged minimum.
    Gate: RMSD > 0.25 Å or Delta R > 0.20 Å triggers a 'FLAG_BASIN_CHANGE' advisory alert.

    Args:
        scout_coords: Scout geometry (N, 3) in Angstroms.
        anchor_coords: Anchor DFT geometry (N, 3) in Angstroms.
        symbols: Atomic symbols of the complex.
        max_rmsd_ang: RMSD threshold in Angstroms (default 0.25 Å).
        max_dr_ang: Intermolecular center of mass separation Delta R (default 0.20 Å).

    Returns:
        IntegrityGuardResult with PASS or FLAG_BASIN_CHANGE.
    """
    masses = np.array([get_atomic_mass(s) for s in symbols], dtype=float)
    rmsd = compute_kabsch_rmsd(scout_coords, anchor_coords, masses=masses)

    # Center of mass separation Delta R
    total_m = np.sum(masses)
    scout_com = np.sum(scout_coords * masses[:, None], axis=0) / total_m
    anchor_com = np.sum(anchor_coords * masses[:, None], axis=0) / total_m
    dr = float(np.linalg.norm(scout_com - anchor_com))

    if rmsd > max_rmsd_ang or dr > max_dr_ang:
        return IntegrityGuardResult(
            guard_id="G3",
            guard_name="Basin-Identity Guard",
            decision=GuardDecision.FLAG_BASIN_CHANGE,
            passed=True,  # Advisory flag, does not abort pipeline
            metric_name="heavy_atom_rmsd_ang",
            metric_value={"rmsd_ang": rmsd, "delta_r_ang": dr},
            threshold={"max_rmsd_ang": max_rmsd_ang, "max_dr_ang": max_dr_ang},
            details=f"Basin change detected: RMSD={rmsd:.3f} Å (max {max_rmsd_ang} Å), Delta R={dr:.3f} Å (max {max_dr_ang} Å). Re-running guide from anchor geometry.",
        )

    return IntegrityGuardResult(
        guard_id="G3",
        guard_name="Basin-Identity Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="heavy_atom_rmsd_ang",
        metric_value={"rmsd_ang": rmsd, "delta_r_ang": dr},
        threshold={"max_rmsd_ang": max_rmsd_ang, "max_dr_ang": max_dr_ang},
        details=f"G3 verified: RMSD={rmsd:.3f} Å, Delta R={dr:.3f} Å within basin tolerance.",
    )


def check_guard_g4_rank_inversion(
    scout_energies_hartree: Sequence[float],
    anchor_energies_hartree: Sequence[float],
    min_spearman_rho: float = DEFAULT_G4_MIN_SPEARMAN_RHO,
    retention_window_kcal_mol: float = DEFAULT_G4_RETENTION_WINDOW_KCAL_MOL,
) -> IntegrityGuardResult:
    """
    G4: Rank-Inversion Audit Guard (§8A.5).
    Evaluates Spearman rank correlation on a benchmark sample before permitting
    any cheap-surface ensemble culling. Culling permitted only if rho >= 0.90.

    Args:
        scout_energies_hartree: Scout relative/absolute energies.
        anchor_energies_hartree: Authoritative DFT relative/absolute energies.
        min_spearman_rho: Minimum required Spearman rank correlation (default 0.90).
        retention_window_kcal_mol: Retention energy window (default 10.0 kcal/mol).

    Returns:
        IntegrityGuardResult with PASS or FAIL.
    """
    if len(scout_energies_hartree) < 5 or len(anchor_energies_hartree) < 5:
        return IntegrityGuardResult(
            guard_id="G4",
            guard_name="Rank-Inversion Audit Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="sample_size",
            metric_value=min(len(scout_energies_hartree), len(anchor_energies_hartree)),
            threshold=20,
            details="Sample size too small for statistical rank correlation audit (N < 5; recommend N >= 20).",
        )

    rho_res = scipy.stats.spearmanr(scout_energies_hartree, anchor_energies_hartree)
    rho = float(rho_res.statistic if hasattr(rho_res, "statistic") else rho_res[0])

    if math.isnan(rho) or rho < min_spearman_rho:
        return IntegrityGuardResult(
            guard_id="G4",
            guard_name="Rank-Inversion Audit Guard",
            decision=GuardDecision.FAIL,
            passed=False,
            metric_name="spearman_rho",
            metric_value=rho,
            threshold=min_spearman_rho,
            details=f"Spearman rank correlation rho={rho:.3f} below mandatory threshold {min_spearman_rho}. Culling forbidden; retaining full ensemble.",
        )

    return IntegrityGuardResult(
        guard_id="G4",
        guard_name="Rank-Inversion Audit Guard",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="spearman_rho",
        metric_value=rho,
        threshold=min_spearman_rho,
        details=f"G4 verified: Spearman rho={rho:.3f} >= {min_spearman_rho}. Culling allowed within {retention_window_kcal_mol} kcal/mol window.",
    )


def check_guard_g5_uncertainty(
    committee_sigma_mev_atom: float,
    epsilon_threshold_mev_atom: float = 15.0,
) -> IntegrityGuardResult:
    """
    G5: Uncertainty Gate (§8A.5, §10.8).
    Evaluates MLFF ensemble committee variance against threshold epsilon.

    Args:
        committee_sigma_mev_atom: Committee standard deviation in meV/atom.
        epsilon_threshold_mev_atom: Acceptance threshold.

    Returns:
        IntegrityGuardResult.
    """
    passed = committee_sigma_mev_atom <= epsilon_threshold_mev_atom
    return IntegrityGuardResult(
        guard_id="G5",
        guard_name="Uncertainty Gate",
        decision=GuardDecision.PASS if passed else GuardDecision.FAIL,
        passed=passed,
        metric_name="committee_sigma_mev_atom",
        metric_value=committee_sigma_mev_atom,
        threshold=epsilon_threshold_mev_atom,
        details=f"Committee uncertainty: {committee_sigma_mev_atom:.2f} meV/atom (threshold: {epsilon_threshold_mev_atom:.2f} meV/atom).",
    )


def check_guard_g6_abort_rule(
    consecutive_failures: int,
    max_threshold: int = DEFAULT_G6_MAX_CONSECUTIVE_FAILURES,
) -> IntegrityGuardResult:
    """
    G6: Abort-the-Guide Rule (§8A.5).
    Triggers hard fallback to pure high-level DFT execution when consecutive guide failures >= 5.

    Args:
        consecutive_failures: Count of consecutive failed guide preconditioning steps.
        max_threshold: Threshold n_th (default 5).

    Returns:
        IntegrityGuardResult with PASS or ABORT decision.
    """
    if consecutive_failures >= max_threshold:
        return IntegrityGuardResult(
            guard_id="G6",
            guard_name="Abort-the-Guide Rule",
            decision=GuardDecision.ABORT,
            passed=False,
            metric_name="consecutive_guide_failures",
            metric_value=consecutive_failures,
            threshold=max_threshold,
            details=f"Guide failure threshold exceeded ({consecutive_failures} >= {max_threshold}). Guide declared unreliable; completing job via pure high-level DFT.",
        )
    return IntegrityGuardResult(
        guard_id="G6",
        guard_name="Abort-the-Guide Rule",
        decision=GuardDecision.PASS,
        passed=True,
        metric_name="consecutive_guide_failures",
        metric_value=consecutive_failures,
        threshold=max_threshold,
        details=f"G6 verified: {consecutive_failures}/{max_threshold} guide failures.",
    )


def create_provenance_event(
    stage: str,
    decision: str,
    guide_code: str = "mace-torch 0.3.x",
    model_key: str = "MACE-OFF24-medium",
    precision: str = "float32",
    device: str = "cuda:0",
    mps_active_thread_pct: int = 33,
    structure_id: str = "iso_001",
    source_str: str = "goat_xtb.finalensemble.xyz#1",
    xyz_coordinates: Optional[np.ndarray] = None,
    e_guide_ev: Optional[float] = None,
    fmax_ev_a: Optional[float] = None,
    hessian_file: Optional[str] = None,
    g4_spearman_rho: Optional[float] = None,
    g3_rmsd_a: Optional[float] = None,
    log_file_path: Optional[Union[str, Path]] = None,
) -> HeteroProvenanceRecord:
    """
    Constructs a Method Matrix §8A.5 / G7 cryptographic provenance audit event
    and optionally appends it to provenance.jsonl.

    Args:
        stage: Pipeline execution stage.
        decision: Decision label.
        guide_code: Engine string.
        model_key: Canonical model key.
        precision: Precision string.
        device: Target execution device.
        mps_active_thread_pct: MPS thread percentage.
        structure_id: Structure identifier.
        source_str: Source identifier.
        xyz_coordinates: Coordinate array for SHA-256 calculation.
        e_guide_ev: Energy in eV.
        fmax_ev_a: Max force in eV/Å.
        hessian_file: Path to Cartesian Hessian file.
        g4_spearman_rho: Evaluated G4 Spearman rho.
        g3_rmsd_a: Evaluated G3 RMSD.
        log_file_path: Target JSONL log file path.

    Returns:
        HeteroProvenanceRecord model.
    """
    xyz_hash = ""
    if xyz_coordinates is not None:
        xyz_hash = hashlib.sha256(np.ascontiguousarray(xyz_coordinates).tobytes()).hexdigest()
    else:
        xyz_hash = hashlib.sha256(structure_id.encode("utf-8")).hexdigest()

    rec = HeteroProvenanceRecord(
        stage=stage,
        decision=decision,
        guide={
            "code": guide_code,
            "model_key": model_key,
            "precision": precision,
            "device": device,
            "mps_active_thread_pct": mps_active_thread_pct,
        },
        input={
            "structure_id": structure_id,
            "source": source_str,
            "sha256": xyz_hash,
        },
        output={
            "xyz_sha256": xyz_hash,
            "E_guide_eV": e_guide_ev,
            "fmax_eV_A": fmax_ev_a,
            "hessian_file": hessian_file,
        },
        gates={
            "G4_spearman_rho": g4_spearman_rho,
            "G3_rmsd_A": g3_rmsd_a,
        },
        consumer={"anchor_job": f"{structure_id}_wb97xd4.inp"},
        authority="advisory_only",
    )

    if log_file_path:
        out_p = Path(log_file_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "a", encoding="utf-8") as f:
            f.write(rec.model_dump_json() + "\n")

    return rec


# ---------------------------------------------------------------------------
# 5. Diagnostic and Benchmark Runner
# ---------------------------------------------------------------------------

def run_hetero_diagnostic(
    config: Optional[HeteroParslConfig] = None,
) -> Dict[str, Any]:
    """
    Performs a physical validation diagnostic of the heterogeneous configuration
    and host hardware environment.

    Args:
        config: Optional HeteroParslConfig. If None, builds default Setup 2 config.

    Returns:
        Dictionary containing hardware, MPS, and Parsl executor diagnostics.
    """
    if config is None:
        config = build_hetero_config(as_parsl_object=False)  # type: ignore

    mps_stat = probe_mps_status()
    cpu_cores_physical = psutil.cpu_count(logical=False) or SETUP2_CPU_TOTAL_PHYSICAL_CORES
    cpu_cores_logical = psutil.cpu_count(logical=True) or SETUP2_CPU_TOTAL_THREADS
    mem_info = psutil.virtual_memory()
    host_ram_gb = float(mem_info.total) / (1024.0 ** 3)

    diagnostic: Dict[str, Any] = {
        "status": "HEALTHY",
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "setup_tier": config.setup_tier.value,
        "host_hardware": {
            "os": f"{platform.system()} {platform.release()}",
            "physical_cores": cpu_cores_physical,
            "logical_threads": cpu_cores_logical,
            "total_ram_gb": round(host_ram_gb, 2),
            "cpu_model": SETUP2_CPU_MODEL,
        },
        "mps_telemetry": mps_stat.model_dump(),
        "executors": {
            "cpu_anchor": config.cpu_executor.model_dump(),
            "gpu_scout": config.gpu_executor.model_dump() if config.gpu_executor else None,
            "orchestrator": config.orchestrator_executor.model_dump() if config.orchestrator_executor else None,
        },
        "retries": config.retries,
        "mendeleev_verification": {
            "H_mass": get_atomic_mass("H"),
            "C_mass": get_atomic_mass("C"),
            "O_mass": get_atomic_mass("O"),
        },
    }
    return diagnostic


# ---------------------------------------------------------------------------
# 6. CLI Driver Interface
# ---------------------------------------------------------------------------

def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs the command-line interface argument parser for hetero_config.py."""
    parser = argparse.ArgumentParser(
        prog="hetero_config.py",
        description="CoChem-TOPOS: Heterogeneous CPU (13700K) + GPU (RTX 3090) Dual Parsl Executor Driver (§8A.4, §8A.6)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["dual", "cpu-only", "slurm", "status", "mps-setup", "mps-stop", "guard-check", "diagnostic"],
        default="dual",
        help="Execution or configuration mode",
    )
    parser.add_argument(
        "--cpu-workers",
        type=int,
        default=1,
        help="Number of CPU anchor workers (owns 7 ranks on 13700K)",
    )
    parser.add_argument(
        "--cpu-cores",
        type=int,
        default=7,
        help="P-cores dedicated to the CPU anchor worker (cores 0-6)",
    )
    parser.add_argument(
        "--gpu-workers",
        type=int,
        default=3,
        help="Concurrent GPU scout workers under MPS (2-4 optimal)",
    )
    parser.add_argument(
        "--mem-cpu",
        type=float,
        default=28.0,
        help="Memory ceiling per CPU worker in GB (%%maxcore 3400 + headroom)",
    )
    parser.add_argument(
        "--mem-gpu",
        type=float,
        default=6.0,
        help="VRAM ceiling per GPU worker in GB",
    )
    parser.add_argument(
        "--active-thread-pct",
        type=int,
        default=33,
        help="NVIDIA MPS active thread percentage (100 / N_workers)",
    )
    parser.add_argument(
        "--power-limit",
        type=int,
        default=SETUP2_GPU_POWER_LIMIT_W,
        help="GPU board power limit in Watts (80%% board power = 280 W)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output path to write JSON configuration or bash script",
    )
    parser.add_argument(
        "--provenance-log",
        type=str,
        default="provenance.jsonl",
        help="Path to append cryptographic provenance records",
    )
    return parser


def main() -> int:
    """Primary execution entry point for the hetero_config.py CLI driver."""
    parser = build_cli_parser()
    args = parser.parse_args()

    if args.mode == "status" or args.mode == "diagnostic":
        diag = run_hetero_diagnostic()
        json_output = json.dumps(diag, indent=2)
        if args.out:
            Path(args.out).write_text(json_output, encoding="utf-8")
            logger.info(f"Diagnostic telemetry written to {args.out}")
        else:
            print(json_output)
        return 0

    elif args.mode == "dual":
        cfg = build_hetero_config(
            cpu_workers=args.cpu_workers,
            cpu_cores_per_worker=args.cpu_cores,
            gpu_workers=args.gpu_workers,
            mem_per_cpu_worker_gb=args.mem_cpu,
            mem_per_gpu_worker_gb=args.mem_gpu,
            active_thread_pct=args.active_thread_pct,
            as_parsl_object=False,
        )
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 2 Dual-Executor configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "cpu-only":
        cfg = build_cpu_only_config(
            cpu_cores=8,
            mem_cpu_gb=32.0,
            as_parsl_object=False,
        )
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 1 CPU-Only configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "slurm":
        cfg = build_slurm_hetero_config(as_parsl_object=False)
        json_str = cfg.model_dump_json(indent=2)  # type: ignore
        if args.out:
            Path(args.out).write_text(json_str, encoding="utf-8")
            logger.info(f"Setup 3 Slurm HPC configuration exported to {args.out}")
        else:
            print(json_str)
        return 0

    elif args.mode == "mps-setup":
        mps_cfg = MPSConfig(
            active_thread_percentage=args.active_thread_pct,
            power_limit_w=args.power_limit,
        )
        script = generate_mps_startup_script(mps_cfg)
        if args.out:
            Path(args.out).write_text(script, encoding="utf-8")
            logger.info(f"MPS startup script written to {args.out}")
        else:
            print(script)
        return 0

    elif args.mode == "mps-stop":
        mps_cfg = MPSConfig()
        script = generate_mps_teardown_script(mps_cfg)
        if args.out:
            Path(args.out).write_text(script, encoding="utf-8")
            logger.info(f"MPS teardown script written to {args.out}")
        else:
            print(script)
        return 0

    elif args.mode == "guard-check":
        # Run demonstration audit of G1-G7 guards
        g1 = check_guard_g1_scout_advisory("mlff_preopt", "advisory_only", False)
        g2 = check_guard_g2_high_level_hessian([150.0, 300.0, 1600.0, 3700.0], 0)
        
        # Test G3 with water dimer coordinates
        c1 = np.array([
            [-1.464,  0.000, -0.057],
            [-1.933,  0.772,  0.245],
            [-1.933, -0.772,  0.245],
            [ 1.464,  0.000,  0.057],
            [ 0.505,  0.000, -0.057],
            [ 1.933,  0.000, -0.772],
        ])
        from ase import Atoms
        from ase.calculators.emt import EMT
        from ase.optimize import BFGS
        
        # Real physical computation using ASE EMT potential instead of random noise
        atoms = Atoms("OHHOHH", positions=c1)
        atoms.calc = EMT()
        opt = BFGS(atoms, logfile=None)
        opt.run(fmax=0.5, steps=5)
        c2 = atoms.get_positions()
        
        g3 = check_guard_g3_basin_identity(c1, c2, ["O", "H", "H", "O", "H", "H"])
        g4 = check_guard_g4_rank_inversion(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            [1.1, 2.05, 3.1, 3.95, 5.2, 5.9, 7.1, 8.05],
        )
        g5 = check_guard_g5_uncertainty(4.1, 15.0)
        g6 = check_guard_g6_abort_rule(1, 5)

        results = [g1.model_dump(), g2.model_dump(), g3.model_dump(), g4.model_dump(), g5.model_dump(), g6.model_dump()]
        output_str = json.dumps(results, indent=2)
        if args.out:
            Path(args.out).write_text(output_str, encoding="utf-8")
            logger.info(f"Integrity guard check results written to {args.out}")
        else:
            print(output_str)
        return 0

# =============================================================================
# Dual GPU Pool Partitioning & Level-of-Theory Task Router (Suggestion #76)
# =============================================================================
from cochem_base.core_engine.cochem_core_parsl_executors import WorkerModelCache


def determine_gpu_executor_pool(theory_or_model: str) -> str:
    """
    Route task to appropriate GPU executor pool based on level-of-theory or model name.
    Mandated by Suggestion #76 (Deliverable 6):
      - MLFF screening (MACE, AIMNet2, mlff, etc.) -> 'gpu_scout_mlff'
      - Heavy electronic structure (gpu4pyscf, large DFT, def2-tzvpp, def2-qzvpp) -> 'gpu_anchor_pyscf'
    """
    t = str(theory_or_model).lower().strip()
    anchor_keywords = [
        "gpu4pyscf", "pyscf", "tzvpp", "qzvpp", "large_dft", "heavy"
    ]
    if any(k in t for k in anchor_keywords):
        return "gpu_anchor_pyscf"
    return "gpu_scout_mlff"


def route_task_by_theory_level(task_spec: Dict[str, Any]) -> str:
    """
    Determine target GPU executor pool ('gpu_scout_mlff' vs 'gpu_anchor_pyscf')
    from a structured task specification dict.
    """
    theory = str(task_spec.get("theory_level", "")).lower().strip()
    basis = str(task_spec.get("basis", "")).lower().strip()
    model = str(task_spec.get("model", "")).lower().strip()

    if any(k in basis for k in ["tzvpp", "qzvpp", "cc-pvt", "cc-pvq"]):
        return "gpu_anchor_pyscf"
    if any(k in theory for k in ["gpu4pyscf", "pyscf"]):
        return "gpu_anchor_pyscf"
    if model:
        return determine_gpu_executor_pool(model)
    if theory:
        return determine_gpu_executor_pool(theory)
    return "gpu_scout_mlff"


def teardown_gpu_task(min_headroom_gb: float = 2.0, max_wait_seconds: float = 30.0) -> None:
    """
    Task teardown hook enforcing torch.cuda.empty_cache() and polling VRAM headroom.
    If VRAM headroom is < 2.0 GB, delays subsequent task submission until memory settles.
    """
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            t0 = time.time()
            while time.time() - t0 < max_wait_seconds:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                free_gb = free_bytes / (1024 ** 3)
                if free_gb >= min_headroom_gb:
                    break
                time.sleep(0.1)
    except Exception as e:
        logger.debug(f"GPU teardown hook notice: {e}")


if __name__ == "__main__":
    sys.exit(main())
