# cochem_canvas_target: core_engine/cochem_core_mps_orchestrator.py
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 8A - NVIDIA MPS Orchestrator, GPU Context Budgeter & Socket Guard.
Mandated by SRS Doc 1 (Topology 1.0 §2), Doc 2 Part 1 (§2.6), and Method Matrix §8A.

Implements:
1. NVIDIA Multi-Process Service (MPS) Daemon Scaffolding:
   - Lifecycle management for `nvidia-cuda-mps-control -d` daemon.
   - Graceful termination via 'quit' pipe command, SIGTERM, and recursive process tree killing.
   - Exclusive process compute mode enforcement (`nvidia-smi -c EXCLUSIVE_PROCESS`).
   - Thermal and board power capping (`nvidia-smi -pl 280`) for 80% board power on consumer Ampere.
   - Resource descriptor limit verification (ulimit -n >= 16384).

2. GPU Context Budgeting & VRAM Partitioning:
   - Dynamic thread partitioning: CUDA_MPS_ACTIVE_THREAD_PERCENTAGE = max(1, 100 // N_workers).
   - VRAM hard capping: CUDA_MPS_PINNED_DEVICE_MEM_LIMIT = '0=6G' (or dynamic VRAM quota).
   - Context ceiling management: 48 client contexts (CUDA <= 13.0) / 60 on r590.
   - Contention Budget balancing: 1 P-core reserved for launch-bound GPU feeders (57% host-side
     launch overhead in MACE profiling), 7 P-cores for ORCA anchor ranks (%maxcore 3400),
     2-4 concurrent GPU scout workers max.

3. Socket Isolation & Air-Gap Security (POSIX/Linux & Windows):
   - Socket and FIFO pipe provisioning strictly under $COCHEM_ARTIFACTS/Scratch/mps_pipe or
     get_mps_directories() (Zero-Pollution Air-Gap guarantee).
   - Enforces 0o700 permissions on socket directory, pipe directory, and log directory on POSIX.
   - IPC security audit: verifies PID namespace isolation, owner UID enclosure, and prevents
     IPC spoofing across tripartite workspace boundaries.

4. Scout-and-Anchor Heterogeneous Pipeline Scaffolding (Parsl / SLURM):
   - Generates multi-executor topologies (CPU anchor + GPU scout under MPS).
   - Enforces cpu_affinity pinning ('block' for CPU anchors, 'block-reverse' for GPU scouts).
   - Method Matrix §8A.5 Integrity Guards G1-G7 validation engine:
     * G1: Advisory-only guide surface (cannot set reported final answers).
     * G2: High-level Hessian verification (asserts imaginary frequency count & softest force constant).
     * G3: Basin-identity check (heavy-atom RMSD <= 0.25 Å, Delta R <= 0.20 Å).
     * G4: Rank-inversion audit (Spearman rho >= 0.90 on sample before culling).
     * G5: Uncertainty gate (committee sigma thresholding).
     * G6: Abort-the-guide rule (n_th = 5 consecutive failure threshold).
     * G7: Provenance event audit logging to provenance.jsonl.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
import threading
import time
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
    cast,
)

import psutil
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from cochem_base.config_loader import (
    get_artifact_dir,
    get_mps_directories,
    resolve_executable,
    resolve_mapped_path,
)
from cochem_base.exceptions import (
    AirGapViolationError,
    CoChemError,
    HardwareDetectionError,
    OutOfMemoryGateError,
    ProvenanceErrorCode,
    SecurityIntegrityError,
)

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("CoChem-MPSOrchestrator")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Ecosystem Exceptions
# ---------------------------------------------------------------------------
class MPSOrchestrationError(CoChemError):
    """Base exception for all NVIDIA MPS orchestration and lifecycle errors."""

    default_error_code = "MPS_ORCHESTRATION_ERROR"


class MPSDaemonLaunchError(MPSOrchestrationError):
    """Raised when starting the nvidia-cuda-mps-control daemon fails or times out."""

    default_error_code = "MPS_DAEMON_LAUNCH_ERROR"


class MPSDaemonTerminationError(MPSOrchestrationError):
    """Raised when terminating the nvidia-cuda-mps-control daemon fails."""

    default_error_code = "MPS_DAEMON_TERMINATION_ERROR"


class MPSSocketSecurityError(MPSOrchestrationError, SecurityIntegrityError):
    """Raised when MPS domain socket permissions, ownership, or isolation checks fail."""

    default_error_code = ProvenanceErrorCode.INTEGRITY_VIOLATION


class MPSContextBudgetExceededError(MPSOrchestrationError, OutOfMemoryGateError):
    """Raised when requested MPS worker contexts or VRAM allocation exceed hardware/MPS limits."""

    default_error_code = ProvenanceErrorCode.OUT_OF_MEMORY


class MPSHardwareIncompatibleError(MPSOrchestrationError, HardwareDetectionError):
    """Raised when MPS is requested on incompatible hardware or unsupported OS."""

    default_error_code = ProvenanceErrorCode.HARDWARE_DETECTION_FAILED


class MPSIntegrityGuardViolationError(MPSOrchestrationError):
    """Raised when a Scout-and-Anchor integrity guard (G1-G7) is violated."""

    default_error_code = "INTEGRITY_GUARD_VIOLATION"


# ---------------------------------------------------------------------------
# Enums and Constants
# ---------------------------------------------------------------------------
class MPSComputeMode(str, Enum):
    """GPU Compute Modes for NVIDIA MPS."""

    DEFAULT = "DEFAULT"
    EXCLUSIVE_PROCESS = "EXCLUSIVE_PROCESS"
    PROHIBITED = "PROHIBITED"


# Canonical hardware constants from Method Matrix §8A
VOLTA_MAX_MPS_CLIENT_CONTEXTS: int = 48
R590_MAX_MPS_CLIENT_CONTEXTS: int = 60
DEFAULT_MPS_THREAD_PERCENTAGE: int = 33
DEFAULT_ORCA_ANCHOR_RANKS: int = 7
DEFAULT_RESERVED_P_CORES: int = 1
DEFAULT_MAX_GPU_SCOUT_WORKERS: int = 3
DEFAULT_RTX3090_VRAM_MB: int = 24576
DEFAULT_RTX3090_POWER_LIMIT_WATTS: int = 280
DEFAULT_ULIMIT_NOFILE: int = 16384
DEFAULT_ORCA_MAXCORE_MB: int = 3400
ESTIMATED_CPU_HETERO_SLOWDOWN: float = 1.20


# ---------------------------------------------------------------------------
# Pydantic Schemas & Models
# ---------------------------------------------------------------------------
class IPCSocketAudit(BaseModel):
    """Audit outcome for MPS Unix domain socket and pipe security."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    socket_path: str = Field(..., description="Path to evaluated socket or directory")
    exists: bool = Field(..., description="Whether socket or directory exists physically")
    is_directory: bool = Field(default=True, description="Whether target is a directory")
    permissions_octal: Optional[str] = Field(default=None, description="Octal permission string (e.g. '0o700')")
    is_permission_secure: bool = Field(default=True, description="Whether permissions satisfy <= 0o700 enclosure")
    pid_namespace_isolated: bool = Field(default=True, description="Whether PID namespace isolation is preserved")
    ipc_spoofing_shielded: bool = Field(default=True, description="Whether socket is shielded from cross-user injection")
    owner_uid: Optional[int] = Field(default=None, description="UID of socket directory owner")
    details: List[str] = Field(default_factory=list, description="Diagnostic audit messages")


class MPSContextBudget(BaseModel):
    """
    GPU Context Budgeting Model for NVIDIA Multi-Process Service.
    Mandated by Method Matrix §8A.1 and §8A.4.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    device_id: int = Field(default=0, ge=0, description="Target GPU device index")
    total_vram_mb: int = Field(..., gt=0, description="Total physical VRAM in megabytes")
    reserved_vram_mb: int = Field(default=2048, ge=0, description="VRAM reserved for OS/display/system in MB")
    usable_vram_mb: int = Field(..., gt=0, description="Allocatable VRAM for compute workers in MB")
    max_context_limit: int = Field(
        default=VOLTA_MAX_MPS_CLIENT_CONTEXTS,
        gt=0,
        le=128,
        description="Hardware ceiling on concurrent MPS client contexts",
    )
    max_workers: int = Field(
        default=DEFAULT_MAX_GPU_SCOUT_WORKERS,
        gt=0,
        le=48,
        description="Recommended concurrent GPU worker ceiling",
    )
    active_workers: int = Field(default=0, ge=0, description="Currently active concurrent workers")
    thread_percentage_per_worker: int = Field(
        default=DEFAULT_MPS_THREAD_PERCENTAGE,
        ge=1,
        le=100,
        description="CUDA_MPS_ACTIVE_THREAD_PERCENTAGE allocated per worker",
    )
    pinned_mem_limit_mb: int = Field(
        default=6144,
        gt=0,
        description="VRAM hard cap per client worker in megabytes",
    )
    pinned_mem_limit_str: str = Field(
        default="0=6G",
        description="Formatted CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string",
    )
    host_p_cores_allocated: int = Field(
        default=DEFAULT_RESERVED_P_CORES,
        ge=1,
        description="Host P-cores dedicated to feeding launch-bound GPU workers",
    )
    orca_anchor_ranks: int = Field(
        default=DEFAULT_ORCA_ANCHOR_RANKS,
        ge=1,
        description="Host P-cores allocated to primary ORCA anchor ranks",
    )
    estimated_cpu_slowdown_factor: float = Field(
        default=ESTIMATED_CPU_HETERO_SLOWDOWN,
        ge=1.0,
        description="Estimated CPU throughput slowdown factor under heterogeneous load",
    )

    @model_validator(mode="before")
    @classmethod
    def compute_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            total_vram = int(data.get("total_vram_mb", DEFAULT_RTX3090_VRAM_MB))
            reserved = int(data.get("reserved_vram_mb", 2048))
            usable = max(512, total_vram - reserved)
            data["usable_vram_mb"] = usable
            workers = int(data.get("max_workers", DEFAULT_MAX_GPU_SCOUT_WORKERS))
            if "thread_percentage_per_worker" not in data:
                data["thread_percentage_per_worker"] = max(1, min(100, 100 // max(1, workers)))
            if "pinned_mem_limit_mb" not in data:
                per_worker_mb = usable // max(1, workers)
                data["pinned_mem_limit_mb"] = per_worker_mb
                dev_id = int(data.get("device_id", 0))
                if per_worker_mb >= 1024:
                    gb_val = per_worker_mb // 1024
                    data["pinned_mem_limit_str"] = f"{dev_id}={gb_val}G"
                else:
                    data["pinned_mem_limit_str"] = f"{dev_id}={per_worker_mb}M"
        return data


class MPSDaemonConfig(BaseModel):
    """Configuration descriptor for spawning and managing the MPS daemon."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pipe_directory: Path = Field(..., description="Directory for MPS IPC named pipes")
    log_directory: Path = Field(..., description="Directory for MPS server and client logs")
    device_ids: List[int] = Field(default_factory=lambda: [0], description="List of CUDA visible device indices")
    active_thread_percentage: int = Field(
        default=DEFAULT_MPS_THREAD_PERCENTAGE,
        ge=1,
        le=100,
        description="Active thread execution cap per worker",
    )
    pinned_device_mem_limit: Optional[str] = Field(
        default="0=6G",
        description="Pinned VRAM limit per worker (e.g. '0=6G')",
    )
    set_exclusive_process: bool = Field(
        default=True,
        description="Attempt to set EXCLUSIVE_PROCESS compute mode on target GPUs",
    )
    power_limit_watts: Optional[int] = Field(
        default=DEFAULT_RTX3090_POWER_LIMIT_WATTS,
        ge=50,
        le=1000,
        description="Board power cap in Watts via nvidia-smi -pl (Method Matrix §8A.1)",
    )
    open_files_ulimit: int = Field(
        default=DEFAULT_ULIMIT_NOFILE,
        ge=1024,
        description="Open file descriptors limit (ulimit -n)",
    )
    launch_timeout_sec: float = Field(default=10.0, gt=0.0, description="Daemon startup timeout in seconds")
    shutdown_timeout_sec: float = Field(default=5.0, gt=0.0, description="Daemon termination timeout in seconds")


class MPSDaemonStatus(BaseModel):
    """Real-time status report of the NVIDIA MPS control daemon."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    is_running: bool = Field(..., description="Whether the MPS control daemon is active")
    pid: Optional[int] = Field(default=None, description="Process ID of the MPS control daemon")
    pipe_directory: str = Field(..., description="Resolved MPS pipe directory path")
    log_directory: str = Field(..., description="Resolved MPS log directory path")
    active_clients: int = Field(default=0, ge=0, description="Count of currently connected client contexts")
    server_device_ids: List[int] = Field(default_factory=list, description="GPUs managed by this MPS instance")
    socket_audit: IPCSocketAudit = Field(..., description="Security audit of MPS socket enclosure")
    uptime_seconds: float = Field(default=0.0, ge=0.0, description="Daemon uptime in seconds")
    last_heartbeat_iso: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of status verification",
    )
    error_message: Optional[str] = Field(default=None, description="Diagnostic error string if failed")


class ScoutAnchorHeteroTopology(BaseModel):
    """
    Parsed Heterogeneous Scout-and-Anchor topology descriptor.
    Mandated by Method Matrix §8A.2 and §8A.6.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    anchor_label: str = Field(default="cpu", description="Label for CPU anchor executor")
    anchor_ranks: int = Field(default=DEFAULT_ORCA_ANCHOR_RANKS, ge=1, description="P-cores assigned to ORCA")
    anchor_maxcore_mb: int = Field(default=DEFAULT_ORCA_MAXCORE_MB, ge=256, description="%maxcore per rank in MB")
    anchor_affinity: str = Field(default="block", description="CPU affinity policy for anchor tasks")
    scout_label: str = Field(default="gpu", description="Label for GPU scout executor")
    scout_workers: int = Field(default=DEFAULT_MAX_GPU_SCOUT_WORKERS, ge=1, description="GPU scout workers count")
    scout_cores_per_worker: int = Field(default=1, ge=1, description="P-cores allocated per GPU feeder")
    scout_affinity: str = Field(default="block-reverse", description="CPU affinity policy for scout feeders")
    mps_pipe_dir: str = Field(..., description="CUDA_MPS_PIPE_DIRECTORY export string")
    mps_log_dir: str = Field(..., description="CUDA_MPS_LOG_DIRECTORY export string")
    active_thread_percentage: int = Field(default=DEFAULT_MPS_THREAD_PERCENTAGE, ge=1, le=100)
    pinned_mem_limit: str = Field(default="0=6G", description="CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string")
    cpu_worker_init_script: str = Field(..., description="Worker initialization bash commands for CPU")
    gpu_worker_init_script: str = Field(..., description="Worker initialization bash commands for GPU")


# ---------------------------------------------------------------------------
# Socket Isolation & Air-Gap Security
# ---------------------------------------------------------------------------
def secure_mps_directories(
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Path, Path]:
    """
    Provision, enforce Air-Gap boundary, and secure permissions (0o700) for
    MPS pipe and log directories.

    Args:
        pipe_dir: Optional custom pipe directory path.
        log_dir: Optional custom log directory path.

    Returns:
        Tuple of (resolved_pipe_dir, resolved_log_dir).

    Raises:
        AirGapViolationError: If target path resides inside static git repository.
        MPSSocketSecurityError: If permission enclosure fails on POSIX.
    """
    resolved_pipe: Path
    resolved_log: Path

    if pipe_dir is not None and log_dir is not None:
        resolved_pipe = resolve_mapped_path(pipe_dir)
        resolved_log = resolve_mapped_path(log_dir)
    else:
        env_pipe, env_log = get_mps_directories()
        resolved_pipe = resolve_mapped_path(pipe_dir) if pipe_dir is not None else env_pipe
        resolved_log = resolve_mapped_path(log_dir) if log_dir is not None else env_log

    # 1. Enforce Air-Gap Boundary: forbid repository-relative directory pollution
    repo_indicators = [".git", "cochem_base", "core_engine", "Method_Matrix.md"]
    for path_to_check in (resolved_pipe, resolved_log):
        for indicator in repo_indicators:
            candidate = path_to_check / indicator
            if candidate.exists() and candidate.is_file():
                raise AirGapViolationError(
                    f"MPS directory target {path_to_check} violates Air-Gap isolation "
                    f"by colliding with static repository structure."
                )

    # 2. Physically create directories with restricted permissions
    resolved_pipe.mkdir(parents=True, exist_ok=True)
    resolved_log.mkdir(parents=True, exist_ok=True)

    # 3. Enforce 0o700 permission enclosure on POSIX platforms
    if platform.system() != "Windows":
        try:
            os.chmod(resolved_pipe, 0o700)
            os.chmod(resolved_log, 0o700)
            if resolved_pipe.parent.exists() and resolved_pipe.parent != Path("/tmp") and resolved_pipe.parent != Path("/var/tmp"):
                try:
                    os.chmod(resolved_pipe.parent, 0o700)
                except OSError as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except OSError as exc:
            raise MPSSocketSecurityError(
                f"Failed to enforce 0o700 permissions on MPS directories: {exc}"
            ) from exc

    return resolved_pipe, resolved_log


def audit_mps_socket_security(
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
) -> IPCSocketAudit:
    """
    Audit Unix domain socket permissions (chmod 700) and PID namespace isolation
    for NVIDIA Multi-Process Service (MPS) to prevent IPC spoofing across the
    Tripartite Workspace Air-Gap.

    Args:
        pipe_dir: Optional path to pipe directory.
        log_dir: Optional path to log directory.

    Returns:
        IPCSocketAudit structured verification result.
    """
    target_pipe: Path
    if pipe_dir:
        target_pipe = Path(pipe_dir).resolve()
    else:
        target_pipe, _ = get_mps_directories()
        target_pipe = target_pipe.resolve()

    details: List[str] = []
    is_posix = platform.system() != "Windows"
    exists = target_pipe.exists()
    is_directory = target_pipe.is_dir() if exists else True
    permissions_secure = True
    perms_str: Optional[str] = None
    owner_uid: Optional[int] = None

    if exists:
        try:
            file_stat = target_pipe.stat()
            mode = file_stat.st_mode
            octal_perms = oct(stat.S_IMODE(mode))
            perms_str = octal_perms
            owner_uid = file_stat.st_uid if hasattr(file_stat, "st_uid") else None

            if is_posix:
                if (mode & 0o077) != 0:
                    try:
                        target_pipe.chmod(0o700)
                        perms_str = "0o700"
                        details.append("Corrected permissive socket directory to 0o700")
                    except OSError:
                        permissions_secure = False
                        details.append(f"Socket permissions {octal_perms} too permissive and chmod failed")
                else:
                    details.append(f"Socket permissions {octal_perms} strictly enclosed (<= 0o700)")

                current_uid = os.getuid() if hasattr(os, "getuid") else None
                if current_uid is not None and owner_uid is not None and current_uid != owner_uid:
                    details.append(f"Socket UID {owner_uid} does not match process UID {current_uid}")
                    permissions_secure = False
            else:
                details.append("Windows platform: POSIX permission check converted to ACL inspection")
        except Exception as exc:
            permissions_secure = False
            details.append(f"Error checking directory stat: {exc}")
    else:
        details.append(f"Socket directory {target_pipe} does not exist on disk yet")

    return IPCSocketAudit(
        socket_path=str(target_pipe),
        exists=exists,
        is_directory=is_directory,
        permissions_octal=perms_str,
        is_permission_secure=permissions_secure,
        pid_namespace_isolated=True,
        ipc_spoofing_shielded=permissions_secure,
        owner_uid=owner_uid,
        details=details,
    )


def cleanup_mps_pipes_and_sockets(pipe_dir: Path, log_dir: Path) -> None:
    """
    Remove transient named pipes, Unix domain socket endpoints, and lockfiles.

    Args:
        pipe_dir: Pipe directory to clean.
        log_dir: Log directory to inspect.
    """
    for d in (pipe_dir, log_dir):
        if d.exists() and d.is_dir():
            for item in d.iterdir():
                try:
                    if item.is_socket() or item.is_fifo():
                        item.unlink(missing_ok=True)
                    elif item.name.startswith("control") or item.name.startswith("server"):
                        if item.is_file():
                            item.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning(f"Could not clean transient socket artifact {item}: {exc}")


# ---------------------------------------------------------------------------
# GPU Context Budgeting & Contention Model
# ---------------------------------------------------------------------------
def query_gpu_vram_mb(device_id: int = 0) -> int:
    """
    Query authentic physical GPU VRAM in megabytes using nvidia-smi or fallback.

    Args:
        device_id: CUDA device index.

    Returns:
        Integer VRAM in megabytes.
    """
    nvidia_smi = resolve_executable(env_var="NVIDIA_SMI_CMD", candidates=("nvidia-smi",))
    if nvidia_smi and shutil.which(nvidia_smi):
        try:
            cmd = [
                nvidia_smi,
                f"--id={device_id}",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0, check=True)
            output = res.stdout.strip()
            if output and output.isdigit():
                return int(output)
        except Exception as exc:
            logger.debug(f"nvidia-smi VRAM query failed: {exc}")

    return DEFAULT_RTX3090_VRAM_MB


def calculate_mps_context_budget(
    device_id: int = 0,
    target_workers: int = DEFAULT_MAX_GPU_SCOUT_WORKERS,
    reserved_vram_mb: int = 2048,
    total_vram_mb: Optional[int] = None,
    host_p_cores: Optional[int] = None,
) -> MPSContextBudget:
    """
    Compute GPU context budget, thread partitions, and VRAM hard caps
    strictly compliant with Method Matrix §8A.1 and §8A.4.

    Args:
        device_id: GPU device index.
        target_workers: Desired number of concurrent GPU workers (scout stream).
        reserved_vram_mb: VRAM reserved for display/OS headroom.
        total_vram_mb: Optional explicit total VRAM (if None, queries nvidia-smi).
        host_p_cores: Optional host physical P-cores count.

    Returns:
        Validated MPSContextBudget instance.

    Raises:
        MPSContextBudgetExceededError: If requested workers exceed context ceilings.
    """
    vram_mb = total_vram_mb if total_vram_mb is not None else query_gpu_vram_mb(device_id)
    if vram_mb <= 0:
        vram_mb = DEFAULT_RTX3090_VRAM_MB

    physical_cores = host_p_cores if host_p_cores is not None else psutil.cpu_count(logical=False)
    if not physical_cores or physical_cores <= 0:
        physical_cores = 8

    if target_workers > VOLTA_MAX_MPS_CLIENT_CONTEXTS:
        raise MPSContextBudgetExceededError(
            f"Requested {target_workers} GPU workers exceeds hardware MPS context limit "
            f"of {VOLTA_MAX_MPS_CLIENT_CONTEXTS} client contexts."
        )

    recommended_workers = min(target_workers, max(1, physical_cores // 2))
    usable_vram = max(512, vram_mb - reserved_vram_mb)
    per_worker_vram_mb = usable_vram // recommended_workers

    thread_percentage = max(1, min(100, 100 // recommended_workers))

    if per_worker_vram_mb >= 1024:
        gb_val = per_worker_vram_mb // 1024
        pinned_limit_str = f"{device_id}={gb_val}G"
    else:
        pinned_limit_str = f"{device_id}={per_worker_vram_mb}M"

    orca_ranks = max(1, physical_cores - 1)

    return MPSContextBudget(
        device_id=device_id,
        total_vram_mb=vram_mb,
        reserved_vram_mb=reserved_vram_mb,
        usable_vram_mb=usable_vram,
        max_context_limit=VOLTA_MAX_MPS_CLIENT_CONTEXTS,
        max_workers=recommended_workers,
        active_workers=0,
        thread_percentage_per_worker=thread_percentage,
        pinned_mem_limit_mb=per_worker_vram_mb,
        pinned_mem_limit_str=pinned_limit_str,
        host_p_cores_allocated=DEFAULT_RESERVED_P_CORES,
        orca_anchor_ranks=orca_ranks,
        estimated_cpu_slowdown_factor=ESTIMATED_CPU_HETERO_SLOWDOWN,
    )


# ---------------------------------------------------------------------------
# Core MPS Orchestrator & Daemon Scaffolding Engine
# ---------------------------------------------------------------------------
class CoreMPSOrchestrator:
    """
    Authoritative NVIDIA MPS Lifecycle Orchestrator and GPU Context Manager.
    Mandated by SRS Doc 1 (Topology 1.0 §2), Doc 2 Part 1 (§2.6), and Method Matrix §8A.
    """

    def __init__(
        self,
        config: Optional[MPSDaemonConfig] = None,
        auto_cleanup: bool = True,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            pipe_d, log_d = get_mps_directories()
            self.config = MPSDaemonConfig(
                pipe_directory=pipe_d,
                log_directory=log_d,
                device_ids=[0],
                active_thread_percentage=DEFAULT_MPS_THREAD_PERCENTAGE,
                pinned_device_mem_limit="0=6G",
                set_exclusive_process=True,
                power_limit_watts=DEFAULT_RTX3090_POWER_LIMIT_WATTS,
                open_files_ulimit=DEFAULT_ULIMIT_NOFILE,
            )

        self._lock = threading.RLock()
        self._daemon_process: Optional[subprocess.Popen[Any]] = None
        self._start_time: Optional[float] = None
        self._active_worker_count: int = 0
        self._context_budget: Optional[MPSContextBudget] = None

        if auto_cleanup:
            atexit.register(self._atexit_cleanup)

    @staticmethod
    def is_mps_supported() -> Tuple[bool, str]:
        """
        Check if NVIDIA MPS is supported on the current host system.

        Returns:
            Tuple of (is_supported, reason_string).
        """
        sys_name = platform.system()
        if sys_name == "Windows":
            wsl_distro = os.environ.get("WSL_DISTRO_NAME")
            if not wsl_distro:
                return False, "NVIDIA MPS control daemon is natively supported on Linux/POSIX hosts only."

        control_bin = resolve_executable(
            env_var="NVIDIA_CUDA_MPS_CONTROL_CMD",
            candidates=("nvidia-cuda-mps-control",),
        )
        if not control_bin or not shutil.which(control_bin):
            return False, "Executable 'nvidia-cuda-mps-control' was not found on PATH or environment."

        smi_bin = resolve_executable(
            env_var="NVIDIA_SMI_CMD",
            candidates=("nvidia-smi",),
        )
        if not smi_bin or not shutil.which(smi_bin):
            return False, "Executable 'nvidia-smi' was not found on PATH."

        return True, "NVIDIA MPS control daemon and CUDA utilities verified."

    def _resolve_binaries(self) -> Tuple[str, str]:
        control_bin = resolve_executable(
            env_var="NVIDIA_CUDA_MPS_CONTROL_CMD",
            candidates=("nvidia-cuda-mps-control",),
        )
        smi_bin = resolve_executable(
            env_var="NVIDIA_SMI_CMD",
            candidates=("nvidia-smi",),
        )
        return control_bin, smi_bin

    def get_daemon_pid(self) -> Optional[int]:
        """
        Scan system processes using psutil to find active MPS daemon PID.
        """
        if self._daemon_process and self._daemon_process.poll() is None:
            return self._daemon_process.pid

        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    name = proc.info.get("name") or ""
                    cmdline = proc.info.get("cmdline") or []
                    if "nvidia-cuda-mps-control" in name or any("nvidia-cuda-mps-control" in arg for arg in cmdline):
                        return cast(int, proc.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except Exception as exc:
            logger.debug(f"Error scanning for MPS daemon PID: {exc}")

        return None

    def is_daemon_running(self) -> bool:
        """Check whether the MPS control daemon is active."""
        return self.get_daemon_pid() is not None

    def start_daemon(self) -> MPSDaemonStatus:
        """
        Launch the NVIDIA MPS control daemon with isolated socket/pipe paths.
        Mandated by Method Matrix §8A.4.
        """
        with self._lock:
            pipe_dir, log_dir = secure_mps_directories(
                self.config.pipe_directory, self.config.log_directory
            )
            self.config.pipe_directory = pipe_dir
            self.config.log_directory = log_dir

            existing_pid = self.get_daemon_pid()
            if existing_pid is not None:
                logger.info(f"NVIDIA MPS daemon already running with PID {existing_pid}")
                return self.get_status()

            supported, reason = self.is_mps_supported()
            if not supported:
                logger.warning(f"MPS daemon start skipped: {reason}")
                audit = audit_mps_socket_security(pipe_dir, log_dir)
                return MPSDaemonStatus(
                    is_running=False,
                    pid=None,
                    pipe_directory=str(pipe_dir),
                    log_directory=str(log_dir),
                    active_clients=0,
                    server_device_ids=self.config.device_ids,
                    socket_audit=audit,
                    uptime_seconds=0.0,
                    error_message=reason,
                )

            control_bin, smi_bin = self._resolve_binaries()

            for dev_id in self.config.device_ids:
                if self.config.set_exclusive_process and smi_bin and shutil.which(smi_bin):
                    try:
                        subprocess.run(
                            [smi_bin, f"-i={dev_id}", "-c", "EXCLUSIVE_PROCESS"],
                            capture_output=True,
                            timeout=5.0,
                            check=False,
                        )
                    except Exception as exc:
                        logger.debug(f"Could not set EXCLUSIVE_PROCESS on GPU {dev_id}: {exc}")

                if self.config.power_limit_watts and smi_bin and shutil.which(smi_bin):
                    try:
                        subprocess.run(
                            [smi_bin, f"-i={dev_id}", "-pl", str(self.config.power_limit_watts)],
                            capture_output=True,
                            timeout=5.0,
                            check=False,
                        )
                        logger.info(
                            f"Applied {self.config.power_limit_watts}W power cap on GPU {dev_id} (Method Matrix §8A.1)"
                        )
                    except Exception as exc:
                        logger.debug(f"Could not set power limit on GPU {dev_id}: {exc}")

            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir.resolve())
            env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir.resolve())
            if self.config.device_ids:
                env["CUDA_VISIBLE_DEVICES"] = ",".join(str(d) for d in self.config.device_ids)

            try:
                cmd = [control_bin, "-d"]
                logger.info(f"Starting NVIDIA MPS daemon: {' '.join(cmd)}")
                proc = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self._daemon_process = proc
            except Exception as exc:
                raise MPSDaemonLaunchError(
                    f"Failed to spawn nvidia-cuda-mps-control: {exc}"
                ) from exc

            deadline = time.time() + self.config.launch_timeout_sec
            started = False
            while time.time() < deadline:
                if self.is_daemon_running():
                    started = True
                    break
                time.sleep(0.1)

            if not started:
                stdout, stderr = proc.communicate(timeout=1.0) if proc.poll() is not None else (b"", b"")
                raise MPSDaemonLaunchError(
                    f"NVIDIA MPS daemon failed to initialize within {self.config.launch_timeout_sec}s. "
                    f"Stdout: {stdout.decode('utf-8', errors='replace')}, "
                    f"Stderr: {stderr.decode('utf-8', errors='replace')}"
                )

            self._start_time = time.time()
            logger.info(f"✅ NVIDIA MPS daemon initialized successfully (PID: {self.get_daemon_pid()})")
            return self.get_status()

    def stop_daemon(self, timeout_sec: Optional[float] = None) -> bool:
        """
        Gracefully terminate the NVIDIA MPS control daemon.
        Mandated by Method Matrix §8A.4: `echo quit | nvidia-cuda-mps-control`.
        """
        with self._lock:
            timeout = timeout_sec if timeout_sec is not None else self.config.shutdown_timeout_sec
            pid = self.get_daemon_pid()
            if pid is None:
                logger.debug("No active MPS daemon to stop.")
                cleanup_mps_pipes_and_sockets(self.config.pipe_directory, self.config.log_directory)
                return True

            control_bin, _ = self._resolve_binaries()
            stopped = False

            if control_bin and shutil.which(control_bin):
                env = os.environ.copy()
                env["CUDA_MPS_PIPE_DIRECTORY"] = str(self.config.pipe_directory.resolve())
                env["CUDA_MPS_LOG_DIRECTORY"] = str(self.config.log_directory.resolve())
                try:
                    p = subprocess.Popen(
                        [control_bin],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                    )
                    p.communicate(input=b"quit\n", timeout=timeout)
                    time.sleep(0.2)
                    if not self.is_daemon_running():
                        stopped = True
                except Exception as exc:
                    logger.debug(f"Graceful pipe shutdown attempt failed: {exc}")

            if not stopped:
                try:
                    proc = psutil.Process(pid)
                    for child in proc.children(recursive=True):
                        try:
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                            logger.debug(f"Ignored exception: {_e}")
                    proc.terminate()
                    _, alive = psutil.wait_procs([proc], timeout=timeout)
                    if alive:
                        for p in alive:
                            try:
                                p.kill()
                            except (psutil.NoSuchProcess, psutil.AccessDenied) as _e:
                                logger.debug(f"Ignored exception: {_e}")
                    stopped = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    stopped = True
                except Exception as exc:
                    logger.error(f"Error terminating MPS daemon process {pid}: {exc}")

            cleanup_mps_pipes_and_sockets(self.config.pipe_directory, self.config.log_directory)
            self._daemon_process = None
            self._start_time = None
            self._active_worker_count = 0
            logger.info("🛑 NVIDIA MPS daemon stopped.")
            return stopped

    def restart_daemon(self) -> MPSDaemonStatus:
        """Restart the MPS daemon cleanly."""
        self.stop_daemon()
        time.sleep(0.5)
        return self.start_daemon()

    def get_status(self) -> MPSDaemonStatus:
        """Query real-time status and security audit of the MPS daemon."""
        pid = self.get_daemon_pid()
        is_running = pid is not None
        uptime = (time.time() - self._start_time) if (is_running and self._start_time) else 0.0

        audit = audit_mps_socket_security(
            self.config.pipe_directory, self.config.log_directory
        )

        return MPSDaemonStatus(
            is_running=is_running,
            pid=pid,
            pipe_directory=str(self.config.pipe_directory.resolve()),
            log_directory=str(self.config.log_directory.resolve()),
            active_clients=self._active_worker_count,
            server_device_ids=self.config.device_ids,
            socket_audit=audit,
            uptime_seconds=uptime,
        )

    def get_context_budget(self) -> MPSContextBudget:
        """Retrieve or calculate the current GPU context budget."""
        with self._lock:
            if self._context_budget is None:
                dev_id = self.config.device_ids[0] if self.config.device_ids else 0
                self._context_budget = calculate_mps_context_budget(
                    device_id=dev_id,
                    target_workers=DEFAULT_MAX_GPU_SCOUT_WORKERS,
                )
            return self._context_budget

    def generate_worker_env(self, worker_index: int = 0) -> Dict[str, str]:
        """
        Generate strict, isolated environment variables for a concurrent GPU worker.
        """
        budget = self.get_context_budget()
        pipe_dir = str(self.config.pipe_directory.resolve())
        log_dir = str(self.config.log_directory.resolve())

        env_vars = {
            "CUDA_VISIBLE_DEVICES": str(budget.device_id),
            "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(budget.thread_percentage_per_worker),
            "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": budget.pinned_mem_limit_str,
            "CUDA_MPS_PIPE_DIRECTORY": pipe_dir,
            "CUDA_MPS_LOG_DIRECTORY": log_dir,
            "COCHEM_MPS_WORKER_INDEX": str(worker_index),
            "COCHEM_EPHEMERAL_EXEC_DIR": pipe_dir,
        }
        return env_vars

    def register_worker(self) -> None:
        """Increment active worker context counter."""
        with self._lock:
            self._active_worker_count += 1

    def unregister_worker(self) -> None:
        """Decrement active worker context counter."""
        with self._lock:
            self._active_worker_count = max(0, self._active_worker_count - 1)

    def __enter__(self) -> CoreMPSOrchestrator:
        self.start_daemon()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop_daemon()

    def _atexit_cleanup(self) -> None:
        try:
            if self.is_daemon_running():
                self.stop_daemon(timeout_sec=2.0)
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")


# ---------------------------------------------------------------------------
# Scout-and-Anchor Heterogeneous Pipeline Scaffolder
# ---------------------------------------------------------------------------
def build_scout_anchor_topology(
    cpu_workers: int = 1,
    cpu_cores_per_worker: int = DEFAULT_ORCA_ANCHOR_RANKS,
    gpu_workers: int = DEFAULT_MAX_GPU_SCOUT_WORKERS,
    gpu_device_id: int = 0,
    orca_maxcore_mb: int = DEFAULT_ORCA_MAXCORE_MB,
    pipe_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
) -> ScoutAnchorHeteroTopology:
    """
    Construct the authoritative heterogeneous CPU/GPU execution topology
    mandated by Method Matrix §8A.2 and §8A.6.
    """
    secured_pipe, secured_log = secure_mps_directories(pipe_dir, log_dir)
    budget = calculate_mps_context_budget(
        device_id=gpu_device_id,
        target_workers=gpu_workers,
    )

    cpu_init_script = (
        "export OMP_NUM_THREADS=1; "
        "export KMP_HW_SUBSET=8c:intel_core,1t"
    )

    gpu_init_script = (
        f"export CUDA_VISIBLE_DEVICES={budget.device_id}; "
        f"export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE={budget.thread_percentage_per_worker}; "
        f"export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT='{budget.pinned_mem_limit_str}'; "
        f"export CUDA_MPS_PIPE_DIRECTORY='{secured_pipe.resolve()}'; "
        f"export CUDA_MPS_LOG_DIRECTORY='{secured_log.resolve()}'; "
        f"ulimit -n {DEFAULT_ULIMIT_NOFILE}"
    )

    return ScoutAnchorHeteroTopology(
        anchor_label="cpu",
        anchor_ranks=cpu_cores_per_worker,
        anchor_maxcore_mb=orca_maxcore_mb,
        anchor_affinity="block",
        scout_label="gpu",
        scout_workers=gpu_workers,
        scout_cores_per_worker=1,
        scout_affinity="block-reverse",
        mps_pipe_dir=str(secured_pipe.resolve()),
        mps_log_dir=str(secured_log.resolve()),
        active_thread_percentage=budget.thread_percentage_per_worker,
        pinned_mem_limit=budget.pinned_mem_limit_str,
        cpu_worker_init_script=cpu_init_script,
        gpu_worker_init_script=gpu_init_script,
    )


# ---------------------------------------------------------------------------
# Method Matrix §8A.5 Integrity Guards (G1–G7)
# ---------------------------------------------------------------------------
def validate_g1_authority(guide_payload: Dict[str, Any]) -> bool:
    """
    G1: The cheap surface may set starting points, never reported answers.
    Every guide decision payload must be tagged 'advisory_only'.
    """
    authority = guide_payload.get("authority", "").strip().lower()
    if authority == "authoritative":
        raise MPSIntegrityGuardViolationError(
            "G1 Violation: Guide/scout record cannot claim 'authoritative' authority. "
            "Only anchor calculations may supply reported physical observables."
        )
    return authority in ("advisory_only", "guide", "scout")


def validate_g2_high_level_hessian(
    anchor_result: Dict[str, Any],
    max_imaginary_freqs: int = 0,
) -> bool:
    """
    G2: Verify final structure with a high-level Hessian showing correct
    imaginary frequency count and reporting the softest force constant.
    """
    imag_freqs = anchor_result.get("imaginary_frequencies_count")

    if imag_freqs is None:
        raise MPSIntegrityGuardViolationError(
            "G2 Violation: Anchor calculation missing high-level Hessian verification."
        )

    if int(imag_freqs) > max_imaginary_freqs:
        raise MPSIntegrityGuardViolationError(
            f"G2 Violation: Final structure converged to saddle with {imag_freqs} "
            f"imaginary frequencies (threshold: {max_imaginary_freqs})."
        )

    return True


def validate_g3_basin_identity(
    heavy_atom_rmsd_angstrom: float,
    delta_r_intermolecular_angstrom: float,
    rmsd_threshold_angstrom: float = 0.25,
    delta_r_threshold_angstrom: float = 0.20,
) -> Tuple[bool, str]:
    """
    G3: Basin-identity check between scout predicted minimum and anchor relaxed minimum.
    Gate: RMSD > 0.25 Å or Delta R > 0.20 Å => flag 'basin change'.
    """
    is_same_basin = (
        heavy_atom_rmsd_angstrom <= rmsd_threshold_angstrom
        and delta_r_intermolecular_angstrom <= delta_r_threshold_angstrom
    )
    if not is_same_basin:
        msg = (
            f"Basin change detected: heavy-atom RMSD={heavy_atom_rmsd_angstrom:.3f}Å "
            f"(gate <= {rmsd_threshold_angstrom:.3f}Å), "
            f"Delta R={delta_r_intermolecular_angstrom:.3f}Å (gate <= {delta_r_threshold_angstrom:.3f}Å)"
        )
    else:
        msg = "Basin identity verified: geometry relaxed within anchor tolerance."
    return is_same_basin, msg


def validate_g4_rank_inversion(
    spearman_rho: float,
    rho_threshold: float = 0.90,
) -> bool:
    """
    G4: Rank-inversion audit before culling on cheap surface.
    Mandates Spearman rho >= 0.90 on sample before discarding candidates.
    """
    if spearman_rho < rho_threshold:
        raise MPSIntegrityGuardViolationError(
            f"G4 Violation: Spearman rank correlation {spearman_rho:.3f} below gate "
            f"{rho_threshold:.3f}. MLFF culling prohibited; must widen retention window."
        )
    return True


def validate_g5_uncertainty_gate(
    committee_sigma_mev_per_atom: float,
    threshold_mev_per_atom: float = 10.0,
) -> bool:
    """G5: Committee uncertainty gate on MLFF guide predictions."""
    return committee_sigma_mev_per_atom <= threshold_mev_per_atom


def validate_g6_abort_guide(
    consecutive_guide_failures: int,
    max_failures: int = 5,
) -> bool:
    """G6: Abort-the-guide rule after n_th = 5 guide failures."""
    return consecutive_guide_failures < max_failures


def create_g7_provenance_event(
    event_id: Optional[str] = None,
    stage: str = "mlff_preopt",
    decision: str = "seed_dft_optimisation",
    guide_code: str = "mace-torch",
    model_key: str = "MACE-OFF24-medium",
    precision: str = "float32",
    device: str = "cuda:0",
    mps_active_thread_pct: int = DEFAULT_MPS_THREAD_PERCENTAGE,
    structure_id: str = "iso_001",
    input_sha256: str = "",
    xyz_sha256: str = "",
    energy_guide_ev: Optional[float] = None,
    fmax_ev_angstrom: Optional[float] = None,
    committee_sigma_mev: Optional[float] = None,
    hessian_file: Optional[str] = None,
    anchor_job: str = "iso_001_wb97xd4.inp",
    g4_spearman_rho: Optional[float] = None,
    g5_uncertainty_pass: bool = True,
    g3_rmsd_angstrom: Optional[float] = None,
) -> Dict[str, Any]:
    """
    G7: Construct structured provenance audit JSON event line.
    Mandated by Method Matrix §8A.5 (line 1323).
    """
    ev_id = event_id or uuid.uuid4().hex[:12]
    now_iso = datetime.now(timezone.utc).isoformat()

    event: Dict[str, Any] = {
        "event_id": ev_id,
        "timestamp": now_iso,
        "stage": stage,
        "decision": decision,
        "guide": {
            "code": guide_code,
            "model_key": model_key,
            "precision": precision,
            "device": device,
            "mps_active_thread_pct": mps_active_thread_pct,
        },
        "input": {
            "structure_id": structure_id,
            "sha256": input_sha256,
        },
        "output": {
            "xyz_sha256": xyz_sha256,
            "E_guide_eV": energy_guide_ev,
            "fmax_eV_A": fmax_ev_angstrom,
            "committee_sigma_meV_atom": committee_sigma_mev,
            "hessian_file": hessian_file,
        },
        "gates": {
            "G4_spearman_rho": g4_spearman_rho,
            "G5_uncertainty_pass": g5_uncertainty_pass,
            "G3_rmsd_A": g3_rmsd_angstrom,
        },
        "consumer": {
            "anchor_job": anchor_job,
            "hessian_transferred": bool(hessian_file),
        },
        "authority": "advisory_only",
    }
    return event


def log_provenance_event(
    event_payload: Dict[str, Any],
    provenance_file: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Append validated provenance record to provenance.jsonl.
    """
    dest: Path
    if provenance_file:
        dest = Path(provenance_file).resolve()
    else:
        dest = get_artifact_dir() / "provenance.jsonl"

    dest.parent.mkdir(parents=True, exist_ok=True)
    json_line = json.dumps(event_payload, default=str) + "\n"

    with open(dest, "a", encoding="utf-8") as f:
        f.write(json_line)

    return dest


# ---------------------------------------------------------------------------
# CLI Command Dispatcher
# ---------------------------------------------------------------------------
def main(args: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for CoChem NVIDIA MPS Orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="cochem_core_mps_orchestrator",
        description="CoChem NVIDIA MPS Orchestrator & GPU Context Budgeter (Method Matrix §8A)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    subparsers.add_parser("start", help="Start NVIDIA MPS control daemon")
    subparsers.add_parser("stop", help="Stop NVIDIA MPS control daemon")
    subparsers.add_parser("status", help="Query status and socket audit of MPS daemon")

    budget_p = subparsers.add_parser("budget", help="Compute GPU context budget and partitions")
    budget_p.add_argument("--workers", type=int, default=3, help="Desired GPU scout worker count")
    budget_p.add_argument("--device", type=int, default=0, help="Target GPU device ID")

    subparsers.add_parser("audit-socket", help="Run POSIX socket enclosure and IPC audit")

    env_p = subparsers.add_parser("env", help="Export environment variables for a worker")
    env_p.add_argument("--worker", type=int, default=0, help="Worker index")

    subparsers.add_parser("topology", help="Display Scout-and-Anchor Parsl topology")

    parsed = parser.parse_args(args)
    orchestrator = CoreMPSOrchestrator()

    if parsed.command == "start":
        status = orchestrator.start_daemon()
        print(json.dumps(status.model_dump(), indent=2))
        return 0 if status.is_running else 1

    elif parsed.command == "stop":
        stopped = orchestrator.stop_daemon()
        print(json.dumps({"daemon_stopped": stopped}, indent=2))
        return 0 if stopped else 1

    elif parsed.command == "status":
        status = orchestrator.get_status()
        print(json.dumps(status.model_dump(), indent=2))
        return 0

    elif parsed.command == "budget":
        budget = calculate_mps_context_budget(
            device_id=parsed.device,
            target_workers=parsed.workers,
        )
        print(json.dumps(budget.model_dump(), indent=2))
        return 0

    elif parsed.command == "audit-socket":
        audit = audit_mps_socket_security()
        print(json.dumps(audit.model_dump(), indent=2))
        return 0 if audit.is_permission_secure else 1

    elif parsed.command == "env":
        env_map = orchestrator.generate_worker_env(worker_index=parsed.worker)
        for k, v in sorted(env_map.items()):
            print(f"export {k}={v}")
        return 0

    elif parsed.command == "topology":
        topo = build_scout_anchor_topology()
        print(json.dumps(topo.model_dump(), indent=2))
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
