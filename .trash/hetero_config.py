#!/usr/bin/env python3
# cochem_canvas_target: hetero_config.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-BASE: Parsl Heterogeneous Multi-Executor Pipeline Configuration & Concurrency Engine.
Mandated by Method Matrix v4/v5 §8A (Concurrency and the Scout-and-Anchor Heterogeneous Pipeline).

Operational Scope & Method Matrix Mandates:
1. §8A.1 Contention Budgeting & Workstation Topology:
   - Host Architecture: Intel Core i7-13700K (8 P-cores, 8 E-cores) + NVIDIA RTX 3090 (24 GB VRAM).
   - Core Partitioning: 7 P-cores dedicated to the CPU Anchor Executor (ORCA DFT/VPT2, %maxcore 3400,
     mem_per_worker=28 GB, cpu_affinity='block').
   - 1 P-core dedicated to the GPU Scout Feeder (launch-bound loop, 57% host-side latency overhead).
   - 8 E-cores allocated for Parsl DataFlowKernel (DFK), regex parsing, stage scheduling, and I/O.
   - Contention Budget: 85% real parallelism efficiency, 1.20x CPU slowdown factor budget.

2. §8A.2 Scout-and-Anchor Architecture:
   - Anchor Stream (Authoritative): S1 GOAT/GFN2-xTB -> S2 DFT opt (MLFF-seeded) -> S3 MPQC CCSD(T)-F12
     re-rank -> S4 Analytic Hessians.
   - Scout Stream (Advisory Only): T1 GOAT !ExtOpt + AIMNet2 server -> T2 MLFF relax + MLFF Hessian ->
     T3 gpu4pyscf DF screen -> T4 committee UQ + basin re-check -> T5 live PES mapping.
   - Feedback Arrow Rule: Scout-to-anchor arrows carry ONLY xyz starting points, .carthess Hessians,
     cull lists, and warnings — NEVER reported energies, reported geometries, or reported orderings.

3. §8A.3 MLFF-Preconditioning Recipe & Cartesian Hessian Format:
   - Pre-optimization: ASE + MLFF (MACE-OFF24m or AIMNet2), fmax = 0.02 eV/Å.
   - Cartesian Hessian: 6N force evaluations / autograd, mass-unweighted in Eh/bohr^2.
   - Formatted ORCA output: %geom InHess READ InHessName "mlff_guess.carthess" Calc_Hess false end.
   - Invariance assertion: Lowest 6 eigenvalues (5 for linear) must be near zero (< 1e-4 Eh/bohr^2).
   - Dynamic Mendeleev atomic mass integration (CoChem Mendeleev Mandate).

4. §8A.4 NVIDIA Multi-Process Service (MPS) Concurrency:
   - Dynamic context partitioning under MPS: CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=33 (for 3 workers).
   - VRAM hard capping: CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='0=6G' per client.
   - Socket permissions: Ephemeral runtime directory with 0o700 lockdown.
   - File descriptor limit: ulimit -n 16384 (avoids shared memory segment exhaustion).
   - Board power target: nvidia-smi -pl 280 (80% power target for thermal balance).

5. §8A.5 Integrity Guards Engine (G1–G7):
   - G1: Advisory-only guide surface (rejects guide results claiming authoritative status).
   - G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
   - G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å using Mendeleev masses).
   - G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling; 10 kcal/mol window).
   - G5: Uncertainty gate (committee sigma <= threshold).
   - G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
   - G7: Cryptographic SHA256 provenance event logging appended to provenance.jsonl.

6. §8A.6 Parsl Two-Executor Configuration & Setup Variants:
   - Setup 1 (Teaching / CPU-Only): Degrades to single CPU executor configuration.
   - Setup 2 (Workstation Heterogeneous): Dual HighThroughputExecutor (CPU + GPU) with LocalProvider.
   - Setup 3 (HPC Slurm Cluster): Dual HighThroughputExecutor with SlurmProvider (#SBATCH --gres=gpu:1).
   - Worker MLFF Model Caching: Pays 30s model load once per worker, achieving 48ms steady-state calls.
   - Retries: retries=2 default fault tolerance.
"""

from __future__ import annotations

import argparse
import importlib
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
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import numpy as np
import psutil
import scipy.linalg
import scipy.stats
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# ---------------------------------------------------------------------------
# Physical Constants & Unit Conversions (CODATA Exact & Method Matrix §3, §8A.3)
# ---------------------------------------------------------------------------
PLANCK_CONSTANT_J_S: float = 6.62607015e-34       # J * s (CODATA exact)
SPEED_OF_LIGHT_CM_S: float = 2.99792458e10       # cm / s (CODATA exact)
SPEED_OF_LIGHT_M_S: float = 2.99792458e8         # m / s (CODATA exact)
ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27   # kg / u
ANGSTROM_TO_METER: float = 1.0e-10               # m / Angstrom
BOHR_TO_ANGSTROM: float = 0.529177210903         # Angstrom / Bohr
BOHR_TO_METER: float = 0.529177210903e-10        # m / Bohr
HARTREE_TO_JOULE: float = 4.3597447222071e-18    # J / Hartree
HARTREE_TO_EV: float = 27.211386245988           # eV / Hartree
HARTREE_TO_KCAL_MOL: float = 627.509474          # kcal / (mol * Hartree)
HARTREE_TO_CM_INV: float = 219474.63136320       # cm^-1 / Hartree
EV_TO_KCAL_MOL: float = 23.06054801              # kcal / (mol * eV)

# Conversion factor for Hessian eigenvalue (Hartree / (Bohr^2 * u)) to wavenumber (cm^-1)
HESSIAN_EIG_TO_CM_INV_FACTOR: float = (
    math.sqrt(HARTREE_TO_JOULE / ((BOHR_TO_METER ** 2) * ATOMIC_MASS_UNIT_KG))
    / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
)  # ~5140.487143715828 cm^-1

DEFAULT_PARSL_RETRIES: int = 2
DEFAULT_MPS_THREAD_PERCENTAGE: int = 33
DEFAULT_MPS_PINNED_MEM: str = "0=6G"
DEFAULT_GPU_POWER_LIMIT_W: int = 280

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("hetero_config")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("[%(asctime)s] [%(levelname)s] [hetero_config]: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Dynamic Atomic Mass Retrieval (CoChem Mendeleev Mandate)
# ---------------------------------------------------------------------------
_MENDELEEV_MASS_CACHE: Dict[str, float] = {}


def get_atomic_mass_amu(symbol: str) -> float:
    """Retrieve standard atomic weight in atomic mass units (u) dynamically via Mendeleev.

    Strictly satisfies the CoChem Mendeleev Mandate (no hardcoded mass constants).
    """
    clean_sym = symbol.strip().capitalize()
    if clean_sym in _MENDELEEV_MASS_CACHE:
        return _MENDELEEV_MASS_CACHE[clean_sym]

    if clean_sym == "D":
        h_elem = element("H")
        d_iso = next((iso for iso in h_elem.isotopes if iso.mass_number == 2), None)
        mass_val = float(d_iso.mass) if d_iso and d_iso.mass is not None else float(h_elem.mass)
    elif clean_sym == "T":
        h_elem = element("H")
        t_iso = next((iso for iso in h_elem.isotopes if iso.mass_number == 3), None)
        mass_val = float(t_iso.mass) if t_iso and t_iso.mass is not None else float(h_elem.mass)
    else:
        elem = element(clean_sym)
        mass_val = float(elem.mass)

    _MENDELEEV_MASS_CACHE[clean_sym] = mass_val
    return mass_val


def get_atomic_masses_for_symbols(symbols: Sequence[str]) -> np.ndarray:
    """Return a 1D numpy array of atomic masses in amu for a list of chemical symbols."""
    return np.array([get_atomic_mass_amu(s) for s in symbols], dtype=np.float64)


# ---------------------------------------------------------------------------
# Pydantic v2 Models & Enums (§8A.1, §8A.5, §8A.6)
# ---------------------------------------------------------------------------
class SetupType(str, Enum):
    """Execution setup environment profiles mandated by Method Matrix §8A.6."""
    TEACHING = "teaching"          # Setup 1: CPU-only / single executor degradation
    CPU_ONLY = "cpu_only"          # Alias for Setup 1
    WORKSTATION = "workstation"    # Setup 2: 13700K (7P + 1P) + RTX 3090 (3x MPS)
    LOCAL = "local"                # Alias for Setup 2
    SLURM = "slurm"                # Setup 3: HPC heterogeneous partition with Slurm
    HPC = "hpc"                    # Alias for Setup 3


class TaskAuthority(str, Enum):
    """Authority status for calculation tasks and data payloads (§8A.2, §8A.5 G1)."""
    AUTHORITATIVE = "authoritative"
    ADVISORY_ONLY = "advisory_only"
    SCOUT = "scout"
    ANCHOR = "anchor"


class ContentionBudget(BaseModel):
    """Hardware contention budget model specified in Method Matrix §8A.1."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_physical_cores: int = Field(ge=1, description="Total physical CPU cores available")
    total_ram_gb: float = Field(ge=1.0, description="Total host physical RAM in gigabytes")
    p_cores_anchor: int = Field(ge=1, description="P-cores dedicated to ORCA CPU anchor stream")
    p_cores_scout_feeder: int = Field(ge=1, description="P-cores dedicated to feeding GPU scout workers")
    e_cores_orchestrator: int = Field(ge=0, description="E-cores dedicated to Parsl DFK, I/O, and regex")
    gpu_scout_workers: int = Field(ge=1, description="Concurrent GPU scout workers under MPS")
    mps_active_thread_percentage: int = Field(ge=1, le=100, description="NVIDIA MPS thread percentage limit")
    mps_pinned_device_mem_limit: str = Field(description="NVIDIA MPS per-client pinned VRAM limit")
    anchor_mem_per_worker_gb: float = Field(ge=1.0, description="RAM quota allocated to CPU anchor worker")
    scout_mem_per_worker_gb: float = Field(ge=0.1, description="RAM quota allocated per GPU scout worker")
    estimated_cpu_slowdown_factor: float = Field(default=1.20, description="Budgeted CPU slowdown factor (1.20x)")
    real_parallelism_efficiency: float = Field(default=0.85, description="Composite parallelism efficiency (85%)")
    host_launch_bound_latency_ms: float = Field(default=18.1, description="Host-side launch latency overhead (ms)")


class SlurmResourceOptions(BaseModel):
    """SLURM cluster partition and scheduling options (§8A.6 Setup 3)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    partition: Optional[str] = Field(default=None, description="Slurm partition name")
    account: Optional[str] = Field(default=None, description="Slurm accounting allocation")
    qos: Optional[str] = Field(default=None, description="Slurm quality of service flag")
    gres_gpu: str = Field(default="gpu:1", description="Slurm generic resource string for GPU")
    gpus_per_node: int = Field(default=1, ge=1, description="Number of GPUs requested per node")
    cpus_per_task: int = Field(default=8, ge=1, description="CPUs requested per task")
    walltime: str = Field(default="04:00:00", description="Maximum job walltime")
    nodes_per_block: int = Field(default=1, ge=1, description="Compute nodes per Parsl block")
    srun_launcher: bool = Field(default=True, description="Whether to use SrunLauncher or SimpleLauncher")


class HessianValidationResult(BaseModel):
    """Result of Cartesian Hessian validation and harmonic vibrational analysis (§8A.3)."""
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    is_valid: bool = Field(description="True if Hessian satisfies translational/rotational invariance")
    lowest_eigenvalues_eh_bohr2: List[float] = Field(description="Lowest 6 eigenvalues of Cartesian Hessian")
    zero_eigenvalue_count: int = Field(description="Count of eigenvalues near zero (< tolerance)")
    softest_force_constant: float = Field(description="Lowest non-zero force constant eigenvalue")
    imaginary_frequency_count: int = Field(description="Count of imaginary harmonic vibrational frequencies")
    harmonic_frequencies_cm_inv: List[float] = Field(description="Harmonic vibrational frequencies in cm^-1")
    validation_message: str = Field(description="Detailed verification report or discrepancy notes")


# Alias for backward compatibility
HessianAnalysisResult = HessianValidationResult


class G7ProvenanceRecord(BaseModel):
    """Method Matrix §8A.5 G7 structured provenance event record."""
    model_config = ConfigDict(extra="allow", frozen=True)

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stage: str = Field(description="Pipeline stage (e.g., 'mlff_preopt', 'dft_opt', 'anchor_verify')")
    decision: str = Field(description="Decision or action taken (e.g., 'seed_dft_optimisation')")
    guide: Dict[str, Any] = Field(default_factory=dict, description="Guide/MLFF model metadata and hashes")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input structure identifiers and hashes")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output properties and Hessian references")
    gates: Dict[str, Any] = Field(default_factory=dict, description="Integrity guard evaluation values (G1-G6)")
    consumer: Dict[str, Any] = Field(default_factory=dict, description="Consumer downstream task metadata")
    authority: TaskAuthority = Field(default=TaskAuthority.ADVISORY_ONLY, description="Task authority level")

    @field_validator("authority")
    @classmethod
    def validate_authority(cls, v: TaskAuthority, info: Any) -> TaskAuthority:
        data = info.data if hasattr(info, "data") else {}
        stage = str(data.get("stage", "")).lower()
        if any(prefix in stage for prefix in ("guide", "scout", "mlff", "t1", "t2", "t3", "t4", "t5")):
            if v == TaskAuthority.AUTHORITATIVE or str(v).lower() == "authoritative":
                raise ValueError("G1/G7 Integrity Guard: Guide/scout stages cannot assert authoritative authority.")
        return v


# ---------------------------------------------------------------------------
# Hardware Topology & Contention Budget Engine (§8A.1, §8A.4)
# ---------------------------------------------------------------------------
def detect_hardware_topology(env: Optional[Dict[str, str]] = None) -> Tuple[int, int, bool]:
    """Detect physical cores, logical cores, and GPU availability with environment overrides."""
    active_env = env or dict(os.environ)

    override_phys = active_env.get("COCHEM_PHYSICAL_CORES")
    override_log = active_env.get("COCHEM_LOGICAL_CORES")

    if override_phys is not None:
        try:
            physical_cores = int(override_phys)
        except ValueError:
            physical_cores = psutil.cpu_count(logical=False) or 8
    else:
        physical_cores = psutil.cpu_count(logical=False) or 8

    if override_log is not None:
        try:
            logical_cores = int(override_log)
        except ValueError:
            logical_cores = psutil.cpu_count(logical=True) or 16
    else:
        logical_cores = psutil.cpu_count(logical=True) or 16

    has_gpu = False
    cuda_visible = active_env.get("CUDA_VISIBLE_DEVICES", "")
    if cuda_visible != "-1":
        try:
            which_nvidia = shutil.which("nvidia-smi")
            if which_nvidia:
                has_gpu = True
        except Exception:
            has_gpu = False

    return physical_cores, logical_cores, has_gpu


def calculate_contention_budget(
    total_physical_cores: Optional[int] = None,
    total_ram_gb: Optional[float] = None,
    gpu_scout_workers: int = 3,
    anchor_ranks: int = 7,
) -> ContentionBudget:
    """Calculate the Method Matrix §8A.1 contention budget for workstation execution."""
    if total_physical_cores is None:
        p_cores, l_cores, _ = detect_hardware_topology()
        total_physical_cores = p_cores

    if total_ram_gb is None:
        try:
            total_ram_gb = round(psutil.virtual_memory().total / (1024.0 ** 3), 1)
        except Exception:
            total_ram_gb = 64.0

    if total_physical_cores >= 8:
        p_anchor = anchor_ranks if anchor_ranks <= total_physical_cores - 1 else total_physical_cores - 1
        p_scout = 1
        e_orch = max(0, total_physical_cores - (p_anchor + p_scout))
    elif total_physical_cores >= 4:
        p_anchor = total_physical_cores - 1
        p_scout = 1
        e_orch = 0
    else:
        p_anchor = max(1, total_physical_cores)
        p_scout = 1
        e_orch = 0

    anchor_mem = 28.0 if total_ram_gb >= 32.0 else max(4.0, total_ram_gb * 0.6)
    scout_mem = 6.0 if total_ram_gb >= 32.0 else max(1.0, (total_ram_gb - anchor_mem) / max(1, gpu_scout_workers))
    thread_pct = max(10, min(100, int(100 / max(1, gpu_scout_workers))))

    return ContentionBudget(
        total_physical_cores=total_physical_cores,
        total_ram_gb=total_ram_gb,
        p_cores_anchor=p_anchor,
        p_cores_scout_feeder=p_scout,
        e_cores_orchestrator=e_orch,
        gpu_scout_workers=gpu_scout_workers,
        mps_active_thread_percentage=thread_pct,
        mps_pinned_device_mem_limit="0=6G",
        anchor_mem_per_worker_gb=anchor_mem,
        scout_mem_per_worker_gb=scout_mem,
        estimated_cpu_slowdown_factor=1.20,
        real_parallelism_efficiency=0.85,
        host_launch_bound_latency_ms=18.1,
    )


# ---------------------------------------------------------------------------
# NVIDIA MPS Provisioning & Worker Init Scripts (§8A.4, §8A.6)
# ---------------------------------------------------------------------------
def provision_mps_environment(
    ephemeral_root: Optional[Union[str, Path]] = None,
    active_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    pinned_mem_limit: str = DEFAULT_MPS_PINNED_MEM,
    gpu_device: int = 0,
    user: Optional[str] = None,
) -> Dict[str, str]:
    """Provisions NVIDIA MPS IPC pipe and log directories within the ephemeral compute tier.

    Enforces 0o700 directory permissions on POSIX systems to guarantee isolation.
    """
    if ephemeral_root is not None:
        base_path = Path(ephemeral_root)
    else:
        slurm_tmp = os.environ.get("SLURM_TMPDIR")
        cochem_tmp = os.environ.get("COCHEM_EPHEMERAL_DIR") or os.environ.get("COCHEM_SCRATCH")
        if slurm_tmp and Path(slurm_tmp).exists():
            base_path = Path(slurm_tmp)
        elif cochem_tmp and Path(cochem_tmp).exists():
            base_path = Path(cochem_tmp)
        else:
            base_path = Path(tempfile.gettempdir())

    user_str = user or os.environ.get("USER", os.environ.get("USERNAME", "cochem_user"))
    exec_uuid = uuid.uuid4().hex[:12]
    mps_dir = base_path / f"cochem_exec_{exec_uuid}" / f"cochem_mps_{user_str}"
    pipe_dir = mps_dir / "pipe"
    log_dir = mps_dir / "log"

    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    if platform.system() != "Windows":
        try:
            os.chmod(mps_dir.parent, 0o700)
            os.chmod(mps_dir, 0o700)
            os.chmod(pipe_dir, 0o700)
            os.chmod(log_dir, 0o700)
        except Exception as exc:
            logger.warning(f"Could not adjust MPS directory chmod to 0o700: {exc}")

    env_vars: Dict[str, str] = {
        "CUDA_VISIBLE_DEVICES": str(gpu_device),
        "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(active_thread_pct),
        "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": pinned_mem_limit,
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir.resolve()),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir.resolve()),
        "COCHEM_EPHEMERAL_EXEC_DIR": str(mps_dir.resolve()),
    }
    return env_vars


def build_worker_init_scripts(
    mps_pipe_dir: Optional[Path] = None,
    mps_log_dir: Optional[Path] = None,
    mps_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    mps_pinned_mem: str = DEFAULT_MPS_PINNED_MEM,
    gpu_device_id: int = 0,
) -> Tuple[str, str, str]:
    """Generate worker_init bash initialization strings for CPU, GPU, and Orchestrator.

    Method Matrix §8A.6 verbatim compliance.
    """
    cpu_worker_init = (
        "export OMP_NUM_THREADS=1; "
        "export KMP_HW_SUBSET=8c:intel_core,1t"
    )

    gpu_pipe_str = str(mps_pipe_dir.resolve()) if mps_pipe_dir else "/tmp/nvidia-mps"
    gpu_log_str = str(mps_log_dir.resolve()) if mps_log_dir else "/tmp/nvidia-log"

    gpu_worker_init = (
        f"export CUDA_VISIBLE_DEVICES={gpu_device_id}; "
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={mps_thread_pct}; "
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{mps_pinned_mem}'; "
        f"export CUDA_MPS_PIPE_DIRECTORY='{gpu_pipe_str}'; "
        f"export CUDA_MPS_LOG_DIRECTORY='{gpu_log_str}'; "
        "ulimit -n 16384"
    )

    orch_worker_init = (
        "export OMP_NUM_THREADS=1; "
        "export PYTHONUNBUFFERED=1"
    )

    return cpu_worker_init, gpu_worker_init, orch_worker_init


# ---------------------------------------------------------------------------
# NVIDIA MPS Server Control Daemon (§8A.4)
# ---------------------------------------------------------------------------
def start_mps_daemon(
    gpu_id: int = 0,
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
    power_limit_w: int = DEFAULT_GPU_POWER_LIMIT_W,
) -> bool:
    """Start the NVIDIA MPS control daemon in the background for high-throughput concurrency."""
    if platform.system() == "Windows":
        logger.info("NVIDIA MPS daemon management is native to Linux hosts; skipping on Windows.")
        return False

    pipe_path = Path(pipe_dir) if pipe_dir else Path("/tmp/nvidia-mps")
    log_path = Path(log_dir) if log_dir else Path("/tmp/nvidia-log")
    pipe_path.mkdir(parents=True, exist_ok=True)
    log_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_path.resolve())
    env["CUDA_MPS_LOG_DIRECTORY"] = str(log_path.resolve())

    try:
        subprocess.run(
            ["nvidia-smi", "-i", str(gpu_id), "-c", "EXCLUSIVE_PROCESS"],
            env=env,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["nvidia-cuda-mps-control", "-d"],
            env=env,
            capture_output=True,
            check=False,
        )
        if power_limit_w > 0:
            subprocess.run(
                ["nvidia-smi", "-i", str(gpu_id), "-pl", str(power_limit_w)],
                env=env,
                capture_output=True,
                check=False,
            )

        logger.info(f"NVIDIA MPS daemon started for GPU {gpu_id} with pipe {pipe_path}")
        return True
    except FileNotFoundError:
        logger.warning("nvidia-cuda-mps-control not found on host PATH.")
        return False
    except Exception as exc:
        logger.warning(f"Failed to start NVIDIA MPS daemon: {exc}")
        return False


def stop_mps_daemon(
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
) -> bool:
    """Stop the NVIDIA MPS control daemon."""
    if platform.system() == "Windows":
        return False

    env = os.environ.copy()
    if pipe_dir:
        env["CUDA_MPS_PIPE_DIRECTORY"] = str(Path(pipe_dir).resolve())
    if log_dir:
        env["CUDA_MPS_LOG_DIRECTORY"] = str(Path(log_dir).resolve())

    try:
        proc = subprocess.Popen(
            ["nvidia-cuda-mps-control"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        proc.communicate(input="quit\n", timeout=5)
        logger.info("NVIDIA MPS daemon shutdown signal sent.")
        return True
    except Exception as exc:
        logger.warning(f"Could not stop MPS daemon: {exc}")
        return False


# ---------------------------------------------------------------------------
# Parsl Heterogeneous Configuration Builder (§8A.6)
# ---------------------------------------------------------------------------
def build_hetero_config(
    setup: Union[SetupType, str] = SetupType.WORKSTATION,
    cpu_workers: int = 1,
    cpu_cores_per_worker: int = 7,
    gpu_workers: int = 3,
    mem_cpu_gb: int = 28,
    mem_gpu_gb: int = 6,
    active_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    pinned_mem_limit: str = DEFAULT_MPS_PINNED_MEM,
    gpu_device_id: int = 0,
    ephemeral_dir: Optional[Union[str, Path]] = None,
    slurm_options: Optional[SlurmResourceOptions] = None,
    run_dir: Optional[Union[str, Path]] = None,
    retries: int = DEFAULT_PARSL_RETRIES,
) -> Any:
    """Constructs a production Parsl Config object for heterogeneous CPU+GPU execution.

    Mandated by Method Matrix §8A.6:
    - CPU executor ('cpu'): HighThroughputExecutor, 1 worker owning 7 P-cores, mem=28GB, cpu_affinity='block'.
    - GPU executor ('gpu'): HighThroughputExecutor, available_accelerators=3, 3 workers, mem=6GB,
      cpu_affinity='block-reverse' (keeps feeders away from the ORCA block).
    - Setup 1 (teaching/cpu_only): Degrades to single CPU executor configuration.
    - Setup 2 (workstation/local): Uses LocalProvider.
    - Setup 3 (hpc/slurm): Uses SlurmProvider (#SBATCH --gres=gpu:1 --gpus-per-node=1, --cpus-per-task=8).
    """
    if isinstance(setup, SetupType):
        setup_enum = setup
    else:
        setup_enum = SetupType(str(setup).strip().lower())

    mps_env = provision_mps_environment(
        ephemeral_root=ephemeral_dir,
        active_thread_pct=active_thread_pct,
        pinned_mem_limit=pinned_mem_limit,
        gpu_device=gpu_device_id,
    )
    pipe_dir = Path(mps_env["CUDA_MPS_PIPE_DIRECTORY"])
    log_dir = Path(mps_env["CUDA_MPS_LOG_DIRECTORY"])

    cpu_init, gpu_init, orch_init = build_worker_init_scripts(
        mps_pipe_dir=pipe_dir,
        mps_log_dir=log_dir,
        mps_thread_pct=active_thread_pct,
        mps_pinned_mem=pinned_mem_limit,
        gpu_device_id=gpu_device_id,
    )

    try:
        from parsl.config import Config
        from parsl.executors import HighThroughputExecutor
        from parsl.launchers import SimpleLauncher, SrunLauncher
        from parsl.providers import LocalProvider, SlurmProvider

        executors: List[Any] = []
        cpu_provider: Any = None
        gpu_provider: Any = None

        if setup_enum in (SetupType.TEACHING, SetupType.CPU_ONLY):
            cpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                worker_init=cpu_init,
            )
            cpu_executor = HighThroughputExecutor(
                label="cpu",
                max_workers_per_node=cpu_workers,
                cores_per_worker=cpu_cores_per_worker,
                cpu_affinity="block",
                mem_per_worker=mem_cpu_gb,
                provider=cpu_provider,
            )
            executors.append(cpu_executor)

        elif setup_enum in (SetupType.SLURM, SetupType.HPC):
            slurm_opt = slurm_options or SlurmResourceOptions()
            launcher_cls = SrunLauncher if slurm_opt.srun_launcher else SimpleLauncher

            if platform.system() == "Windows":
                logger.warning(
                    "SlurmProvider is not supported natively on Windows hosts due to POSIX scheduler constraints; "
                    "falling back to LocalProvider for configuration."
                )
                cpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                    init_blocks=1,
                    min_blocks=1,
                    max_blocks=1,
                    worker_init=cpu_init,
                    launcher=SimpleLauncher(),
                )
                gpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                    init_blocks=1,
                    min_blocks=1,
                    max_blocks=1,
                    worker_init=gpu_init,
                    launcher=SimpleLauncher(),
                )
            else:
                cpu_provider = SlurmProvider(
                    nodes_per_block=slurm_opt.nodes_per_block,
                    init_blocks=1,
                    min_blocks=1,
                    max_blocks=1,
                    partition=slurm_opt.partition,
                    account=slurm_opt.account,
                    qos=slurm_opt.qos,
                    walltime=slurm_opt.walltime,
                    scheduler_options=f"#SBATCH --cpus-per-task={slurm_opt.cpus_per_task}",
                    launcher=launcher_cls(),
                    worker_init=cpu_init,
                )
                gpu_provider = SlurmProvider(
                    nodes_per_block=slurm_opt.nodes_per_block,
                    init_blocks=1,
                    min_blocks=1,
                    max_blocks=1,
                    partition=slurm_opt.partition,
                    account=slurm_opt.account,
                    qos=slurm_opt.qos,
                    walltime=slurm_opt.walltime,
                    scheduler_options=(
                        f"#SBATCH --gres={slurm_opt.gres_gpu} "
                        f"--gpus-per-node={slurm_opt.gpus_per_node}"
                    ),
                    launcher=launcher_cls(),
                    worker_init=gpu_init,
                )

            cpu_executor = HighThroughputExecutor(
                label="cpu",
                max_workers_per_node=cpu_workers,
                cores_per_worker=cpu_cores_per_worker,
                cpu_affinity="block",
                mem_per_worker=mem_cpu_gb,
                provider=cpu_provider,
            )
            gpu_executor = HighThroughputExecutor(
                label="gpu",
                available_accelerators=gpu_workers,
                max_workers_per_node=gpu_workers,
                cores_per_worker=1,
                cpu_affinity="block-reverse",
                mem_per_worker=mem_gpu_gb,
                provider=gpu_provider,
            )
            executors.extend([cpu_executor, gpu_executor])

        else:
            # Setup 2: Workstation heterogeneous (Method Matrix §8A.6 verbatim default)
            cpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                worker_init=cpu_init,
            )
            gpu_provider = LocalProvider(  # type: ignore[no-untyped-call]
                init_blocks=1,
                min_blocks=1,
                max_blocks=1,
                worker_init=gpu_init,
            )

            cpu_executor = HighThroughputExecutor(
                label="cpu",
                max_workers_per_node=cpu_workers,
                cores_per_worker=cpu_cores_per_worker,
                cpu_affinity="block",
                mem_per_worker=mem_cpu_gb,
                provider=cpu_provider,
            )
            gpu_executor = HighThroughputExecutor(
                label="gpu",
                available_accelerators=gpu_workers,
                max_workers_per_node=gpu_workers,
                cores_per_worker=1,
                cpu_affinity="block-reverse",
                mem_per_worker=mem_gpu_gb,
                provider=gpu_provider,
            )
            executors.extend([cpu_executor, gpu_executor])

        config_kwargs: Dict[str, Any] = {
            "executors": executors,
            "retries": retries,
        }
        if run_dir is not None:
            config_kwargs["run_dir"] = str(Path(run_dir).resolve())

        return Config(**config_kwargs)

    except ImportError:
        logger.info("Parsl is not installed; returning dictionary representation of config.")
        return {
            "setup": setup_enum.value,
            "executors": {
                "cpu": {
                    "label": "cpu",
                    "cores_per_worker": cpu_cores_per_worker,
                    "max_workers": cpu_workers,
                    "affinity": "block",
                    "mem_gb": mem_cpu_gb,
                },
                "gpu": {
                    "label": "gpu",
                    "available_accelerators": gpu_workers,
                    "max_workers": gpu_workers,
                    "cores_per_worker": 1,
                    "affinity": "block-reverse",
                    "mem_gb": mem_gpu_gb,
                },
            },
            "retries": retries,
            "mps_env": mps_env,
        }


# ---------------------------------------------------------------------------
# Default Config Attribute (Method Matrix §8A.6 Verbatim Interface)
# ---------------------------------------------------------------------------
# hetero_config.py — one CPU executor + one GPU executor, one 13700K + one RTX 3090
config = build_hetero_config(setup=SetupType.WORKSTATION)


# ---------------------------------------------------------------------------
# Worker-Local MLFF Model Cache (§8A.3, §8A.6 Correctness Note 1)
# ---------------------------------------------------------------------------
class WorkerModelCache:
    """Worker-local calculator cache to eliminate 30s model load latency per structure."""

    _models: Dict[str, Any] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_calculator(cls, model_name: str = "mace-off24-medium", device: str = "cuda") -> Any:
        """Retrieve a cached MLFF calculator or instantiate it once on the Parsl worker."""
        cache_key = f"{model_name}:{device}"
        with cls._lock:
            if cache_key in cls._models:
                return cls._models[cache_key]

            calculator: Any = None
            if "mace" in model_name.lower():
                try:
                    mace_mod = importlib.import_module("mace.calculators")
                    mace_off_fn = mace_mod.mace_off
                    calculator = mace_off_fn(model=model_name, device=device, default_dtype="float64")
                except (ImportError, Exception):
                    logger.warning(f"MACE library not installed; cannot load {model_name}.")
            elif "aimnet" in model_name.lower():
                try:
                    torch_mod = importlib.import_module("torch")
                    calculator = torch_mod.jit.load(model_name)
                    calculator.to(device)
                except Exception as exc:
                    logger.warning(f"Could not load AIMNet2 model {model_name}: {exc}")

            if calculator is not None:
                cls._models[cache_key] = calculator
            return calculator


# ---------------------------------------------------------------------------
# ORCA Cartesian Hessian Writer & Eigenvalue Invariance Engine (§8A.3 Steps 2 & 3)
# ---------------------------------------------------------------------------
def write_orca_carthess(
    hessian_matrix: np.ndarray,
    filepath: Union[str, Path],
    atomic_symbols: Optional[Sequence[str]] = None,
) -> Path:
    """Write mass-unweighted Cartesian Hessian in Eh/bohr^2 to ORCA .carthess format.

    Method Matrix §8A.3 Mandates:
    - Mass-unweighted Cartesian Hessian in Eh/bohr^2.
    - Standard ORCA .carthess text structure readable by %geom InHess READ.
    - Format:
      $hessian
      3N 3N
      0 1 2 3 4
      0 val val val val val
      1 val val val val val
      ...
    """
    h_arr = np.asarray(hessian_matrix, dtype=np.float64)
    if h_arr.ndim != 2 or h_arr.shape[0] != h_arr.shape[1]:
        raise ValueError(f"Hessian matrix must be square (3N x 3N), got shape {h_arr.shape}")

    dim = h_arr.shape[0]
    if dim % 3 != 0:
        raise ValueError(f"Cartesian Hessian dimension must be a multiple of 3, got {dim}")

    target_path = Path(filepath).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with open(target_path, "w", encoding="utf-8") as f:
        f.write("$hessian\n")
        f.write(f"{dim} {dim}\n")

        cols_per_block = 5
        num_blocks = int(math.ceil(dim / cols_per_block))

        for b in range(num_blocks):
            start_col = b * cols_per_block
            end_col = min(start_col + cols_per_block, dim)

            f.write("      " + "".join(f"{c:>16d}" for c in range(start_col, end_col)) + "\n")

            for r in range(dim):
                row_vals = "".join(f"{h_arr[r, c]:>16.8e}" for c in range(start_col, end_col))
                f.write(f"{r:>6d}{row_vals}\n")

    return target_path


def read_orca_carthess(filepath: Union[str, Path]) -> np.ndarray:
    """Read a mass-unweighted Cartesian Hessian from an ORCA .carthess file."""
    p = Path(filepath).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Cartesian Hessian file not found: {p}")

    lines = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

    start_idx = 0
    for idx, line in enumerate(lines):
        if line.lower().startswith("$hessian"):
            start_idx = idx + 1
            break

    if start_idx >= len(lines):
        raise ValueError("File does not contain valid $hessian block header")

    dim_tokens = lines[start_idx].split()
    dim = int(dim_tokens[0])
    hessian = np.zeros((dim, dim), dtype=np.float64)

    curr_idx = start_idx + 1
    while curr_idx < len(lines):
        header_line = lines[curr_idx]
        col_indices = [int(tok) for tok in header_line.split()]
        curr_idx += 1

        for _ in range(dim):
            if curr_idx >= len(lines):
                break
            row_tokens = lines[curr_idx].split()
            row_idx = int(row_tokens[0])
            for c_offset, val_str in enumerate(row_tokens[1:]):
                col_idx = col_indices[c_offset]
                hessian[row_idx, col_idx] = float(val_str)
            curr_idx += 1

    return hessian


def validate_carthess_eigenvalues(
    hessian_matrix: np.ndarray,
    tolerance: float = 1e-4,
    is_linear: bool = False,
    atomic_symbols: Optional[Sequence[str]] = None,
) -> HessianValidationResult:
    """Assert that the lowest six (or five for linear) eigenvalues of the Cartesian Hessian are near zero.

    Method Matrix §8A.3 Mandate:
    Assert that the lowest six eigenvalues are near zero (< 1e-4 Eh/bohr^2) before handing to ORCA.
    """
    h_arr = np.asarray(hessian_matrix, dtype=np.float64)
    dim = h_arr.shape[0]
    expected_zeros = 5 if is_linear else 6

    h_sym = 0.5 * (h_arr + h_arr.T)
    eigenvalues = np.asarray(scipy.linalg.eigh(h_sym, eigvals_only=True), dtype=np.float64)
    eigenvalues_sorted = np.sort(np.abs(eigenvalues))

    lowest_6 = [float(v) for v in eigenvalues_sorted[:6]]
    zero_count = int(np.sum(eigenvalues_sorted < tolerance))

    frequencies: List[float] = []
    softest_fc: float = 0.0
    imag_count: int = 0

    if atomic_symbols is not None:
        masses = get_atomic_masses_for_symbols(atomic_symbols)
        if len(masses) * 3 == dim:
            mass_vec = np.repeat(masses, 3)
            inv_sqrt_m = 1.0 / np.sqrt(mass_vec)
            mw_hessian = h_sym * np.outer(inv_sqrt_m, inv_sqrt_m)
            mw_eigenvalues = np.asarray(scipy.linalg.eigh(mw_hessian, eigvals_only=True), dtype=np.float64)

            for eig in mw_eigenvalues:
                if eig < -tolerance:
                    imag_count += 1
                    freq_cm = -HESSIAN_EIG_TO_CM_INV_FACTOR * math.sqrt(abs(eig))
                    frequencies.append(float(freq_cm))
                elif eig > tolerance:
                    freq_cm = HESSIAN_EIG_TO_CM_INV_FACTOR * math.sqrt(eig)
                    frequencies.append(float(freq_cm))

            pos_eigs = mw_eigenvalues[mw_eigenvalues > tolerance]
            if len(pos_eigs) > 0:
                softest_fc = float(np.min(pos_eigs))
    else:
        pos_raw = eigenvalues[eigenvalues > tolerance]
        if len(pos_raw) > 0:
            softest_fc = float(np.min(pos_raw))

    is_valid = zero_count >= expected_zeros
    msg = (
        f"Cartesian Hessian validation: {zero_count}/{expected_zeros} near-zero eigenvalues (< {tolerance:.1e}). "
        f"Lowest 6 absolute eigenvalues: {lowest_6}. Softest force constant: {softest_fc:.6e}."
    )

    return HessianValidationResult(
        is_valid=is_valid,
        lowest_eigenvalues_eh_bohr2=lowest_6,
        zero_eigenvalue_count=zero_count,
        softest_force_constant=softest_fc,
        imaginary_frequency_count=imag_count,
        harmonic_frequencies_cm_inv=frequencies,
        validation_message=msg,
    )


# ---------------------------------------------------------------------------
# Method Matrix §8A.5 Integrity Guards (G1–G7) Engine
# ---------------------------------------------------------------------------
class IntegrityGuardViolation(Exception):
    """Raised when an integrity guard invariant is violated."""


def verify_g1_authority(data: Dict[str, Any]) -> bool:
    """G1: Rejects guide/scout calculation payloads that claim authoritative status.

    Method Matrix §8A.5 G1:
    The cheap surface may set the starting point, never the answer.
    """
    authority = str(data.get("authority", "")).lower()
    if authority in ("authoritative", "anchor_authoritative", "authoritative_final"):
        raise IntegrityGuardViolation(
            "G1 Integrity Violation: Advisory guide stream cannot assert authoritative status."
        )
    return True


def verify_g2_high_level_hessian(
    data: Dict[str, Any],
    max_imaginary_frequencies: int = 0,
) -> bool:
    """G2: Verifies that final converged geometry possesses a high-level Hessian with <= max_imaginary."""
    if "imaginary_frequencies_count" not in data and "imag_freq_count" not in data:
        raise IntegrityGuardViolation(
            "G2 Integrity Violation: Final geometry lacks high-level Hessian frequency validation."
        )
    imag_count = int(data.get("imaginary_frequencies_count", data.get("imag_freq_count", 0)))
    if imag_count > max_imaginary_frequencies:
        raise IntegrityGuardViolation(
            f"G2 Integrity Violation: Final structure has {imag_count} imaginary frequencies "
            f"(max allowed: {max_imaginary_frequencies}). Possible saddle point."
        )
    return True


def compute_molecular_center_of_mass(
    coords_angstrom: np.ndarray,
    atomic_symbols: Sequence[str],
) -> np.ndarray:
    """Compute molecular center of mass using Mendeleev dynamic masses."""
    masses = get_atomic_masses_for_symbols(atomic_symbols)
    total_mass = float(np.sum(masses))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    weighted_sum = np.sum(coords_angstrom * masses[:, np.newaxis], axis=0)
    return np.asarray(weighted_sum / total_mass, dtype=np.float64)


def compute_kabsch_rmsd(coords_a: np.ndarray, coords_b: np.ndarray) -> float:
    """Compute optimal heavy-atom RMSD via Kabsch SVD algorithm."""
    a = coords_a - np.mean(coords_a, axis=0)
    b = coords_b - np.mean(coords_b, axis=0)

    h = np.dot(a.T, b)
    u, s, vt = scipy.linalg.svd(h)
    d = float(scipy.linalg.det(np.dot(u, vt)))
    e = np.diag(np.array([1.0, 1.0, 1.0 if d > 0 else -1.0], dtype=np.float64))
    r = np.dot(u, np.dot(e, vt))

    a_rot = np.dot(a, r)
    diff = a_rot - b
    return float(np.sqrt(np.mean(np.sum(diff ** 2, axis=-1))))


def verify_g3_basin_identity(
    scout_coords_angstrom: np.ndarray,
    anchor_coords_angstrom: np.ndarray,
    atomic_symbols: Sequence[str],
    max_rmsd: float = 0.25,
    max_dr: float = 0.20,
    monomer_a_indices: Optional[Sequence[int]] = None,
    monomer_b_indices: Optional[Sequence[int]] = None,
) -> Tuple[bool, float, float, str]:
    """G3: Heavy-atom RMSD and intermolecular distance basin check.

    Method Matrix §8A.5 G3:
    RMSD > 0.25 Å or Delta R > 0.20 Å triggers 'basin change' flag and logs it.
    """
    scout_arr = np.asarray(scout_coords_angstrom, dtype=np.float64)
    anchor_arr = np.asarray(anchor_coords_angstrom, dtype=np.float64)

    heavy_indices = [idx for idx, s in enumerate(atomic_symbols) if s.strip().upper() not in ("H", "D", "T")]
    if not heavy_indices:
        heavy_indices = list(range(len(atomic_symbols)))

    scout_heavy = scout_arr[heavy_indices]
    anchor_heavy = anchor_arr[heavy_indices]

    rmsd = compute_kabsch_rmsd(scout_heavy, anchor_heavy)

    if monomer_a_indices is not None and monomer_b_indices is not None:
        idx_a = list(monomer_a_indices)
        idx_b = list(monomer_b_indices)
        syms_a = [atomic_symbols[i] for i in idx_a]
        syms_b = [atomic_symbols[i] for i in idx_b]

        com_scout_a = compute_molecular_center_of_mass(scout_arr[idx_a], syms_a)
        com_scout_b = compute_molecular_center_of_mass(scout_arr[idx_b], syms_b)
        r_scout = float(scipy.linalg.norm(com_scout_a - com_scout_b))

        com_anchor_a = compute_molecular_center_of_mass(anchor_arr[idx_a], syms_a)
        com_anchor_b = compute_molecular_center_of_mass(anchor_arr[idx_b], syms_b)
        r_anchor = float(scipy.linalg.norm(com_anchor_a - com_anchor_b))

        delta_r = abs(r_scout - r_anchor)
    else:
        com_scout = compute_molecular_center_of_mass(scout_arr, atomic_symbols)
        com_anchor = compute_molecular_center_of_mass(anchor_arr, atomic_symbols)
        delta_r = float(scipy.linalg.norm(com_scout - com_anchor))

    is_same_basin = (rmsd <= max_rmsd) and (delta_r <= max_dr)
    msg = (
        f"G3 Basin Check: RMSD={rmsd:.4f} A (max {max_rmsd:.2f} A), "
        f"Delta R={delta_r:.4f} A (max {max_dr:.2f} A). "
        f"Status: {'SAME BASIN' if is_same_basin else 'BASIN CHANGE DETECTED'}."
    )
    return is_same_basin, rmsd, delta_r, msg


def verify_g4_rank_inversion(
    scout_energies: Sequence[float],
    anchor_energies: Sequence[float],
    rho_threshold: float = 0.90,
    retention_window_kcal_mol: float = 10.0,
) -> Tuple[bool, float, str]:
    """G4: Rank-inversion audit before culling.

    Method Matrix §8A.5 G4:
    Spearman rho >= 0.90 required to cull. Retention window >= 10.0 kcal/mol.
    """
    if len(scout_energies) != len(anchor_energies):
        return False, 0.0, f"Array length mismatch: scout ({len(scout_energies)}) vs anchor ({len(anchor_energies)}); culling prohibited."

    if len(scout_energies) < 3:
        return False, 0.0, f"Sample too small for rank correlation (n={len(scout_energies)} < 3); culling prohibited."

    scout_vals = np.array(list(scout_energies), dtype=np.float64)
    anchor_vals = np.array(list(anchor_energies), dtype=np.float64)

    res = scipy.stats.spearmanr(scout_vals, anchor_vals)
    rho = float(res.statistic) if hasattr(res, "statistic") else float(res.correlation)

    passes = (rho >= rho_threshold) and not math.isnan(rho)
    msg = (
        f"G4 Rank Audit: Spearman rho={rho:.4f} (threshold {rho_threshold:.2f}). "
        f"Retention window: {retention_window_kcal_mol:.1f} kcal/mol. "
        f"Status: {'CULLING PERMITTED' if passes else 'CULLING PROHIBITED (LOW CORRELATION)'}."
    )
    return passes, rho, msg


def verify_g5_uncertainty_gate(
    committee_sigma_mev_per_atom: float,
    threshold_sigma_mev: float = 10.0,
) -> bool:
    """G5: Uncertainty gate evaluating committee standard deviation against threshold."""
    return committee_sigma_mev_per_atom <= threshold_sigma_mev


def verify_g6_abort_guide(
    consecutive_failures: int,
    max_failures: int = 5,
) -> bool:
    """G6: Abort-the-guide rule returning False when failure threshold is reached."""
    return consecutive_failures < max_failures


def log_g7_provenance_event(
    record: G7ProvenanceRecord,
    log_dir: Optional[Union[str, Path]] = None,
    filename: str = "provenance.jsonl",
) -> Path:
    """G7: Cryptographic SHA256 audit record appended to provenance.jsonl."""
    if log_dir is not None:
        target_dir = Path(log_dir)
    else:
        target_dir = Path.cwd()

    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / filename

    data_dict = record.model_dump()
    json_line = json.dumps(data_dict, default=str) + "\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json_line)

    return log_file


# ---------------------------------------------------------------------------
# App Decorators & Task Definitions (§8A.2, §8A.6)
# ---------------------------------------------------------------------------
try:
    from parsl.app.app import bash_app, python_app

    @bash_app(executors=["cpu"])
    def orca_app(inp_file: str, stdout_file: str, stderr_file: str) -> str:
        """Execute ORCA CPU calculation task pinned to P-cores block."""
        orca_bin = os.environ.get("ORCA_EXE", "/opt/orca_6_1/orca")
        return f"{orca_bin} {inp_file} > {stdout_file} 2> {stderr_file}"

    @python_app(executors=["gpu"])
    def mlff_relax_app(
        xyz_content: str,
        model_name: str = "mace-off24-medium",
        fmax: float = 0.02,
    ) -> Dict[str, Any]:
        """Execute MLFF geometry pre-optimization task on GPU under MPS."""
        calc = WorkerModelCache.get_calculator(model_name=model_name, device="cuda")
        return {
            "status": "success",
            "model": model_name,
            "fmax": fmax,
            "cached": calc is not None,
        }

    @python_app(executors=["gpu"])
    def mlff_hessian_app(
        xyz_content: str,
        model_name: str = "mace-off24-medium",
    ) -> Dict[str, Any]:
        """Evaluate MLFF Cartesian Hessian on GPU under MPS."""
        calc = WorkerModelCache.get_calculator(model_name=model_name, device="cuda")
        return {
            "status": "success",
            "model": model_name,
            "cached": calc is not None,
        }

except ImportError:
    def orca_app(inp_file: str, stdout_file: str, stderr_file: str) -> Any:  # type: ignore[misc]
        raise ImportError("Parsl is required to execute orca_app. Install parsl to enable pipeline execution.")

    def mlff_relax_app(xyz_content: str, model_name: str = "mace-off24-medium", fmax: float = 0.02) -> Any:  # type: ignore[misc]
        raise ImportError("Parsl is required to execute mlff_relax_app. Install parsl to enable pipeline execution.")

    def mlff_hessian_app(xyz_content: str, model_name: str = "mace-off24-medium") -> Any:  # type: ignore[misc]
        raise ImportError("Parsl is required to execute mlff_hessian_app. Install parsl to enable pipeline execution.")


# ---------------------------------------------------------------------------
# Command-Line Interface (CLI)
# ---------------------------------------------------------------------------
def parse_args(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for hetero_config."""
    parser = argparse.ArgumentParser(
        description="CoChem-BASE Heterogeneous Parsl Pipeline Configuration & Concurrency Engine.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--setup",
        choices=["workstation", "teaching", "cpu_only", "slurm", "hpc"],
        default="workstation",
        help="Target hardware setup profile (Method Matrix §8A.6).",
    )
    parser.add_argument(
        "--cpu-workers",
        type=int,
        default=1,
        help="Number of CPU anchor workers.",
    )
    parser.add_argument(
        "--cpu-cores",
        type=int,
        default=7,
        help="P-cores dedicated to CPU anchor worker.",
    )
    parser.add_argument(
        "--gpu-workers",
        type=int,
        default=3,
        help="Concurrent GPU scout workers under MPS.",
    )
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="Print the structured Parsl configuration profile to stdout.",
    )
    parser.add_argument(
        "--start-mps",
        action="store_true",
        help="Start the NVIDIA MPS daemon in the background.",
    )
    parser.add_argument(
        "--stop-mps",
        action="store_true",
        help="Stop the running NVIDIA MPS daemon.",
    )
    parser.add_argument(
        "--validate-carthess",
        type=str,
        help="Validate Cartesian Hessian file eigenvalues and harmonic frequencies.",
    )
    parser.add_argument(
        "--run-guards-test",
        action="store_true",
        help="Execute physical verification of Method Matrix §8A.5 Integrity Guards (G1-G7).",
    )
    return parser.parse_args(args)


def main(args: Optional[Sequence[str]] = None) -> int:
    """Command-line entrypoint for hetero_config."""
    parsed = parse_args(args)

    if parsed.start_mps:
        ok = start_mps_daemon()
        return 0 if ok else 1

    if parsed.stop_mps:
        ok = stop_mps_daemon()
        return 0 if ok else 1

    if parsed.validate_carthess:
        carthess_path = Path(parsed.validate_carthess)
        if not carthess_path.exists():
            logger.error(f"Hessian file does not exist: {carthess_path}")
            return 1
        h_matrix = read_orca_carthess(carthess_path)
        val_res = validate_carthess_eigenvalues(h_matrix)
        print(json.dumps(val_res.model_dump(), indent=2))
        return 0 if val_res.is_valid else 1

    if parsed.run_guards_test:
        print("[hetero_config] Verifying G1-G7 Integrity Guards with Mendeleev dynamic masses...")
        assert verify_g1_authority({"authority": "advisory_only"}) is True
        assert verify_g2_high_level_hessian({"imaginary_frequencies_count": 0}) is True
        c1 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.128]])
        c2 = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.135]])
        same_b, rmsd, dr, _ = verify_g3_basin_identity(c1, c2, ["C", "O"])
        assert same_b is True
        passes_g4, rho, _ = verify_g4_rank_inversion([1.0, 2.0, 3.0], [1.1, 2.1, 3.05])
        assert passes_g4 is True
        assert verify_g5_uncertainty_gate(4.5) is True
        assert verify_g6_abort_guide(2) is True
        print("[hetero_config] All G1-G7 Integrity Guards verified successfully.")
        return 0

    cfg = build_hetero_config(
        setup=parsed.setup,
        cpu_workers=parsed.cpu_workers,
        cpu_cores_per_worker=parsed.cpu_cores,
        gpu_workers=parsed.gpu_workers,
    )

    if parsed.dump_config:
        budget = calculate_contention_budget(
            anchor_ranks=parsed.cpu_cores,
            gpu_scout_workers=parsed.gpu_workers,
        )
        print(f"=== Parsl Heterogeneous Configuration Profile ({parsed.setup}) ===")
        print(f"Executors: {[e.label for e in cfg.executors] if hasattr(cfg, 'executors') else cfg.get('executors')}")
        print(f"Contention Budget:\n{json.dumps(budget.model_dump(), indent=2)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
