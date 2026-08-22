"""
CoChem Setup Phase 5: NVIDIA MPS Daemon Initialization & VRAM Budgeting Gatekeeper.
Production-grade, zero-mock gatekeeping engine for multi-tenant NVIDIA Multi-Process Service (MPS)
daemon management (nvidia-cuda-mps-control), isolated runtime Unix socket and named pipe provisioning
(CUDA_MPS_PIPE_DIRECTORY, CUDA_MPS_LOG_DIRECTORY), dynamically calculated pinned device memory partitioning
(CUDA_MPS_PINNED_DEVICE_MEM_LIMIT), multi-process GPU concurrency shielding for MACE-OFF23 and gpu4pyscf
workers, cross-platform and CPU-only graceful degradation, and transactional atomic state persistence
into the Golden Registry.

SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 3), and Method Matrix v4 Compliant.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase5AuditError(RuntimeError):
    """Raised when critical phase 5 MPS daemon initialization or VRAM allocation fails fatally."""


class MPSControlError(RuntimeError):
    """Raised when nvidia-cuda-mps-control daemon lifecycle management commands fail unexpectedly."""


class VRAMAllocationError(RuntimeError):
    """Raised when VRAM memory limits or worker capacity cannot be safely bounded."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class MPSStatus(str, Enum):
    """Operational status enumeration for NVIDIA MPS daemon subsystem."""

    RUNNING = "RUNNING"
    INITIALIZED = "INITIALIZED"
    STOPPED = "STOPPED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class GPUDeviceVRAM(BaseModel):
    """Physical GPU device VRAM allocation and worker partitioning profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    index: int = Field(..., ge=0, description="Physical GPU device index (e.g. 0, 1)")
    name: str = Field(..., description="GPU model/product identifier")
    uuid: Optional[str] = Field(default=None, description="GPU device UUID if available")
    total_vram_mb: float = Field(..., ge=0.0, description="Total physical VRAM in megabytes")
    free_vram_mb: float = Field(default=0.0, ge=0.0, description="Available unallocated VRAM in megabytes")
    reserved_vram_mb: float = Field(default=0.0, ge=0.0, description="VRAM reserved for OS/UI/host buffers in megabytes")
    allocatable_vram_mb: float = Field(default=0.0, ge=0.0, description="Net allocatable VRAM for compute workers in megabytes")
    allocated_limit_per_worker_mb: float = Field(
        default=0.0, ge=0.0, description="Calculated pinned memory limit per concurrent worker in megabytes"
    )
    active_worker_capacity: int = Field(
        default=1, ge=1, description="Maximum concurrent GPU worker processes supported without OOM"
    )
    pinned_mem_limit_str: str = Field(
        default="", description="Formatted CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string (e.g. '0=4096M')"
    )
    compute_capability: Optional[str] = Field(
        default=None, description="CUDA compute capability architecture (e.g. 'sm_80', 'sm_89')"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GPU name cannot be empty")
        return v.strip()


class MPSDaemonAudit(BaseModel):
    """Structured inspection and lifecycle state of the NVIDIA MPS daemon."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    mps_control_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-control executable"
    )
    mps_server_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-server executable"
    )
    status: MPSStatus = Field(default=MPSStatus.NOT_SUPPORTED, description="Operational status of MPS daemon")
    pipe_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_PIPE_DIRECTORY IPC pipe/sockets"
    )
    log_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_LOG_DIRECTORY telemetry logs"
    )
    socket_path: Optional[str] = Field(
        default=None, description="Active Unix domain socket or named pipe path for daemon communication"
    )
    is_daemon_active: bool = Field(
        default=False, description="Whether the nvidia-cuda-mps-control daemon process is running"
    )
    pid: Optional[int] = Field(
        default=None, description="Process ID of active nvidia-cuda-mps-control daemon"
    )
    socket_permissions: Optional[str] = Field(
        default=None, description="Octal permission mode (e.g. '0o700') or ACL string"
    )
    is_permission_secure: bool = Field(
        default=True, description="Whether socket permissions enforce 0700 restricted access"
    )
    server_active: bool = Field(
        default=False, description="Whether backend nvidia-cuda-mps-server process is active"
    )
    control_active: bool = Field(
        default=False, description="Whether nvidia-cuda-mps-control command pipe is responsive"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables configured for MPS operations"
    )
    details: str = Field(default="", description="Diagnostic status summary and telemetry details")


class VRAMBudgetReport(BaseModel):
    """Aggregated cluster-wide VRAM memory budgeting and concurrency partitioning record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_gpus_detected: int = Field(default=0, ge=0, description="Total number of physical GPUs discovered")
    active_gpu_devices: List[GPUDeviceVRAM] = Field(
        default_factory=list, description="Per-GPU VRAM profiles and allocation limits"
    )
    total_cluster_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated VRAM across all GPUs in megabytes"
    )
    total_reserved_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated reserved VRAM across all GPUs in megabytes"
    )
    total_allocatable_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated allocatable VRAM across all GPUs in megabytes"
    )
    worker_concurrency_target: int = Field(
        default=2, ge=1, description="Configured target concurrent GPU worker processes (e.g. 2 for MACE+PySCF)"
    )
    default_pinned_mem_limit: Optional[str] = Field(
        default=None, description="Default global CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string"
    )
    per_device_limits: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of device indices to pinned memory limits (e.g. {'0': '4096M'})"
    )
    is_vram_bounded: bool = Field(
        default=True, description="Whether VRAM allocations are strictly bounded to prevent OOM"
    )
    strategy: str = Field(
        default="PROPORTIONAL_PINNED_BUDGET", description="Applied VRAM partitioning strategy algorithm"
    )


class Phase5AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 5 NVIDIA MPS Daemon & VRAM Budgeting."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(
        default="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        description="Unique phase identifier",
    )
    status: PhaseStatus = Field(..., description="Overall phase outcome status")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    mps_daemon: MPSDaemonAudit = Field(..., description="NVIDIA MPS daemon lifecycle and socket audit")
    vram_budget: VRAMBudgetReport = Field(..., description="Calculated VRAM partitioning and budgeting report")
    is_cuda_available: bool = Field(default=False, description="Whether CUDA runtime and hardware are available")
    is_hpc_slurm: bool = Field(default=False, description="Whether execution occurred within a Slurm HPC envelope")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p5.json")

    @field_validator("phase_id")
    @classmethod
    def validate_phase_id(cls, v: str) -> str:
        if v != "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING":
            raise ValueError(f"Invalid phase_id: {v}")
        return v


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY & ATOMIC STATE MANAGER
# =============================================================================


class DependencyManager:
    """
    Transactional context manager for managing temporary files, staging directories,
    and executing atomic JSON state persistence with automatic rollback on unhandled exceptions.
    Ensures workspace sterility per SRS Document 5 Section 1.3.
    """

    def __init__(self) -> None:
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None:
            self.rollback()

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def untrack_file(self, path: Union[str, Path]) -> None:
        """Remove a file from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_files:
            self._tracked_temp_files.remove(p)

    def untrack_dir(self, path: Union[str, Path]) -> None:
        """Remove a directory from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_dirs:
            self._tracked_temp_dirs.remove(p)

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in list(self._tracked_temp_files):
            try:
                if temp_file.exists() and temp_file.is_file():
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in list(self._tracked_temp_dirs):
            try:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        if isinstance(data, BaseModel):
            json_text = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            json_text = json.dumps(data, indent=indent, default=str)
        else:
            json_text = str(data)

        staged_file.write_text(json_text, encoding="utf-8")
        os.replace(staged_file, target)
        self.untrack_file(staged_file)

        return target


# =============================================================================
# 4. PATH RESOLUTION & DIRECTORY PROVISIONING
# =============================================================================


def get_current_username() -> str:
    """Retrieve the current OS username sanitized for filesystem paths."""
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "default_user"
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", user)


def resolve_mps_pipe_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve isolated runtime control pipe directory for CUDA_MPS_PIPE_DIRECTORY following
    the authoritative CoChem hierarchy:
    1. Explicit custom_dir parameter
    2. Environment variable CUDA_MPS_PIPE_DIRECTORY
    3. Slurm HPC envelope: $SLURM_TMPDIR/cochem_mps_$USER
    4. Linux / POSIX default: /tmp/cochem_mps_$USER
    5. Windows fallback: %TEMP%\\cochem_mps_%USERNAME%
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_pipe = os.environ.get("CUDA_MPS_PIPE_DIRECTORY")
    if env_pipe:
        resolved = Path(env_pipe).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_temp = Path(tempfile.gettempdir()) / f"cochem_mps_{user}{dir_suffix}"
    win_temp.mkdir(parents=True, exist_ok=True)
    return win_temp.resolve()


def resolve_mps_log_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve log directory for CUDA_MPS_LOG_DIRECTORY following the CoChem hierarchy.
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_log = os.environ.get("CUDA_MPS_LOG_DIRECTORY")
    if env_log:
        resolved = Path(env_log).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_log_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_log_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_log = Path(tempfile.gettempdir()) / f"cochem_mps_log_{user}{dir_suffix}"
    win_log.mkdir(parents=True, exist_ok=True)
    return win_log.resolve()


def enforce_socket_directory_permissions(dir_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Enforce restrictive 0700 (owner-only read/write/execute) permissions on Unix socket directories
    to prevent IPC spoofing and privilege escalation across multi-tenant environments.
    """
    if platform.system() == "Windows":
        return True, "0o700 (Windows NT ACL inherited)"

    try:
        current_mode = dir_path.stat().st_mode
        if (current_mode & 0o077) != 0:
            dir_path.chmod(0o700)
        mode_str = oct(stat.S_IMODE(dir_path.stat().st_mode))
        return True, mode_str
    except OSError:
        return False, None


def resolve_p5_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve canonical destination path for Golden Registry artifact p5.json.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.suffix == ".json" or out_path.name == "p5.json":
            return out_path
        return out_path / "p5.json"

    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p5.json"
    except ImportError:
        pass

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p5.json"

    repo_root = Path.cwd()
    agent_artifacts = repo_root / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p5.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p5.json"


# =============================================================================
# 5. GPU DISCOVERY & VRAM PROFILING
# =============================================================================


def probe_gpu_devices_vram(
    registry_p2_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[GPUDeviceVRAM], bool]:
    """
    Interrogate host GPU topology and extract accurate physical VRAM capacities
    using a multi-tiered inspection pipeline (p2.json -> pynvml -> nvidia-smi -> torch.cuda).
    """
    devices: List[GPUDeviceVRAM] = []
    cuda_available = False

    # Tier 1: Interrogate previous Phase 2 registry (p2.json) if available
    candidate_p2_paths: List[Path] = []
    if registry_p2_path:
        candidate_p2_paths.append(Path(registry_p2_path).resolve())
    candidate_p2_paths.append(Path.cwd() / ".agent_artifacts" / "Registry" / "p2.json")
    candidate_p2_paths.append(Path.home() / "CoChem_Artifacts" / "Registry" / "p2.json")

    for p2_path in candidate_p2_paths:
        if p2_path.exists() and p2_path.is_file():
            try:
                data = json.loads(p2_path.read_text(encoding="utf-8"))
                gpu_info = data.get("gpu", {})
                if gpu_info.get("cuda_available", False) and gpu_info.get("devices"):
                    for d in gpu_info["devices"]:
                        if d.get("vendor", "").upper() == "NVIDIA":
                            vram_bytes = d.get("memory_total_bytes") or 0
                            free_bytes = d.get("memory_free_bytes") or vram_bytes
                            vram_mb = float(vram_bytes) / (1024.0 * 1024.0)
                            free_mb = float(free_bytes) / (1024.0 * 1024.0)
                            idx = int(d.get("index", len(devices)))
                            dev_name = d.get("name", f"NVIDIA GPU {idx}")
                            dev_uuid = d.get("uuid")
                            arch = d.get("compute_capability")
                            devices.append(
                                GPUDeviceVRAM(
                                    index=idx,
                                    name=dev_name,
                                    uuid=dev_uuid,
                                    total_vram_mb=round(vram_mb, 2),
                                    free_vram_mb=round(free_mb, 2),
                                    reserved_vram_mb=0.0,
                                    allocatable_vram_mb=0.0,
                                    allocated_limit_per_worker_mb=0.0,
                                    active_worker_capacity=1,
                                    pinned_mem_limit_str="",
                                    compute_capability=arch,
                                )
                            )
                    if devices:
                        cuda_available = True
                        return devices, cuda_available
            except Exception:
                pass

    # Tier 2: Query NVIDIA NVML via pynvml or nvidia-ml-py if present
    try:
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            import pynvml  # type: ignore

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for idx in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            name_raw = pynvml.nvmlDeviceGetName(handle)
            name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_mb = float(mem_info.total) / (1024.0 * 1024.0)
            free_mb = float(mem_info.free) / (1024.0 * 1024.0)
            try:
                uuid_raw = pynvml.nvmlDeviceGetUUID(handle)
                dev_uuid = uuid_raw.decode("utf-8") if isinstance(uuid_raw, bytes) else str(uuid_raw)
            except Exception:
                dev_uuid = None
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                arch = f"sm_{major}{minor}"
            except Exception:
                arch = None

            devices.append(
                GPUDeviceVRAM(
                    index=idx,
                    name=name,
                    uuid=dev_uuid,
                    total_vram_mb=round(total_mb, 2),
                    free_vram_mb=round(free_mb, 2),
                    reserved_vram_mb=0.0,
                    allocatable_vram_mb=0.0,
                    allocated_limit_per_worker_mb=0.0,
                    active_worker_capacity=1,
                    pinned_mem_limit_str="",
                    compute_capability=arch,
                )
            )
        pynvml.nvmlShutdown()
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 3: Query via nvidia-smi CLI
    try:
        smi_out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,uuid,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        for line in smi_out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx = int(parts[0])
                name = parts[1]
                dev_uuid = parts[2]
                total_mb = float(parts[3])
                free_mb = float(parts[4])
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=name,
                        uuid=dev_uuid,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(free_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=None,
                    )
                )
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 4: Query via torch.cuda if available
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            cuda_available = True
            cnt = torch.cuda.device_count()
            for idx in range(cnt):
                props = torch.cuda.get_device_properties(idx)
                total_mb = float(props.total_memory) / (1024.0 * 1024.0)
                arch = f"sm_{props.major}{props.minor}"
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=props.name,
                        uuid=None,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(total_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=arch,
                    )
                )
            if devices:
                return devices, cuda_available
    except Exception:
        pass

    return devices, cuda_available


# =============================================================================
# 6. VRAM BUDGETING & MEMORY PARTITIONING ALGORITHM
# =============================================================================


def calculate_vram_budget(
    devices: List[GPUDeviceVRAM],
    worker_concurrency_target: int = 2,
    custom_limit_per_worker_mb: Optional[float] = None,
    reserved_headroom_fraction: float = 0.15,
    min_reserved_headroom_mb: float = 1024.0,
) -> VRAMBudgetReport:
    """
    Calculate mathematically bounded VRAM allocations and build the authoritative
    CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string for each device.

    Formula:
    Reserved_VRAM = max(min_reserved_headroom_mb, total_vram_mb * reserved_headroom_fraction)
    Allocatable_VRAM = max(0.0, total_vram_mb - Reserved_VRAM)
    Per_Worker_Limit = floor(Allocatable_VRAM / worker_concurrency_target)
    """
    concurrency = max(1, worker_concurrency_target)
    updated_devices: List[GPUDeviceVRAM] = []
    per_device_limits: Dict[str, str] = {}
    default_pinned_str: Optional[str] = None

    total_cluster_vram = 0.0
    total_reserved_vram = 0.0
    total_allocatable_vram = 0.0

    if not devices:
        return VRAMBudgetReport(
            total_gpus_detected=0,
            active_gpu_devices=[],
            total_cluster_vram_mb=0.0,
            total_reserved_vram_mb=0.0,
            total_allocatable_vram_mb=0.0,
            worker_concurrency_target=concurrency,
            default_pinned_mem_limit=None,
            per_device_limits={},
            is_vram_bounded=True,
            strategy="ZERO_GPU_DEGRADED",
        )

    for dev in devices:
        total_mb = dev.total_vram_mb
        total_cluster_vram += total_mb

        reserved_mb = max(min_reserved_headroom_mb, total_mb * reserved_headroom_fraction)
        reserved_mb = min(reserved_mb, total_mb)
        total_reserved_vram += reserved_mb

        allocatable_mb = max(0.0, total_mb - reserved_mb)
        total_allocatable_vram += allocatable_mb

        if custom_limit_per_worker_mb is not None and custom_limit_per_worker_mb > 0:
            limit_mb = min(allocatable_mb, custom_limit_per_worker_mb)
        else:
            limit_mb = allocatable_mb / float(concurrency) if allocatable_mb > 0 else 0.0

        int_limit_mb = int(limit_mb)
        pinned_str = f"{dev.index}={int_limit_mb}M" if int_limit_mb > 0 else f"{dev.index}=0M"
        per_device_limits[str(dev.index)] = pinned_str

        worker_capacity = max(1, int(allocatable_mb // int_limit_mb)) if int_limit_mb > 0 else 1

        updated_dev = GPUDeviceVRAM(
            index=dev.index,
            name=dev.name,
            uuid=dev.uuid,
            total_vram_mb=dev.total_vram_mb,
            free_vram_mb=dev.free_vram_mb,
            reserved_vram_mb=round(reserved_mb, 2),
            allocatable_vram_mb=round(allocatable_mb, 2),
            allocated_limit_per_worker_mb=round(float(int_limit_mb), 2),
            active_worker_capacity=worker_capacity,
            pinned_mem_limit_str=pinned_str,
            compute_capability=dev.compute_capability,
        )
        updated_devices.append(updated_dev)

    if updated_devices:
        first_limit = int(updated_devices[0].allocated_limit_per_worker_mb)
        default_pinned_str = f"{first_limit}M" if first_limit > 0 else None

    return VRAMBudgetReport(
        total_gpus_detected=len(updated_devices),
        active_gpu_devices=updated_devices,
        total_cluster_vram_mb=round(total_cluster_vram, 2),
        total_reserved_vram_mb=round(total_reserved_vram, 2),
        total_allocatable_vram_mb=round(total_allocatable_vram, 2),
        worker_concurrency_target=concurrency,
        default_pinned_mem_limit=default_pinned_str,
        per_device_limits=per_device_limits,
        is_vram_bounded=True,
        strategy="PROPORTIONAL_PINNED_BUDGET",
    )


def build_pinned_memory_limit_string(budget: VRAMBudgetReport, device_index: int = 0) -> str:
    """
    Build the exact CUDA_MPS_PINNED_DEVICE_MEM_LIMIT value for a specific device index.
    """
    dev_str = str(device_index)
    if dev_str in budget.per_device_limits:
        return budget.per_device_limits[dev_str]
    if budget.default_pinned_mem_limit:
        return budget.default_pinned_mem_limit
    return ""


# =============================================================================
# 7. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE MANAGEMENT
# =============================================================================


def discover_mps_binaries() -> Tuple[Optional[str], Optional[str]]:
    """
    Sweep host filesystem for nvidia-cuda-mps-control and nvidia-cuda-mps-server binaries.
    """
    control_path: Optional[str] = shutil.which("nvidia-cuda-mps-control")
    server_path: Optional[str] = shutil.which("nvidia-cuda-mps-server")

    candidate_roots = [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/usr/local/cuda/bin"),
        Path("/opt/cuda/bin"),
    ]

    for usr_local in [Path("/usr/local"), Path("/opt")]:
        if usr_local.is_dir():
            try:
                for entry in usr_local.iterdir():
                    if entry.is_dir() and "cuda" in entry.name.lower():
                        bin_dir = entry / "bin"
                        if bin_dir.is_dir() and bin_dir not in candidate_roots:
                            candidate_roots.append(bin_dir)
            except OSError:
                pass

    if not control_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-control"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                control_path = str(candidate.resolve())
                break

    if not server_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-server"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                server_path = str(candidate.resolve())
                break

    return control_path, server_path


def probe_mps_daemon_status(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: Optional[str] = None,
    server_binary: Optional[str] = None,
) -> MPSDaemonAudit:
    """
    Probe the live operational status of the NVIDIA MPS daemon, inspect pipe sockets,
    and verify daemon responsiveness.
    """
    is_posix = platform.system() != "Windows"
    sec_ok, perm_str = enforce_socket_directory_permissions(pipe_dir)

    is_running = False
    control_active = False
    server_active = False
    daemon_pid: Optional[int] = None
    socket_path: Optional[str] = None
    details_list: List[str] = []

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pname = proc.info.get("name", "") or ""
                raw_cmd = proc.info.get("cmdline") or []
                cmd = " ".join(str(c) for c in raw_cmd if c is not None)
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-control" in cmd:
                    is_running = True
                    control_active = True
                    daemon_pid = proc.info.get("pid")
                if "nvidia-cuda-mps-server" in pname or "nvidia-cuda-mps-server" in cmd:
                    server_active = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    control_pipe = pipe_dir / "control"
    server_pipe = pipe_dir / "server"

    if control_pipe.exists():
        socket_path = str(control_pipe)
        details_list.append("MPS control pipe present in socket directory")
    elif server_pipe.exists():
        socket_path = str(server_pipe)
        details_list.append("MPS server pipe present in socket directory")
    else:
        socket_path = str(pipe_dir)

    if control_binary and is_running and is_posix:
        try:
            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
            env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)
            res = subprocess.run(
                [control_binary],
                input="get_server_list\nquit\n",
                text=True,
                capture_output=True,
                timeout=3,
                env=env,
            )
            if res.returncode == 0:
                control_active = True
                details_list.append("nvidia-cuda-mps-control responsive to commands")
        except Exception as e:
            details_list.append(f"MPS command pipe probe advisory: {e}")

    if not is_posix:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("NVIDIA MPS daemon multiplexing not natively supported on Windows NT; degraded CPU/direct CUDA active")
    elif is_running:
        mps_status = MPSStatus.RUNNING
        details_list.append("NVIDIA MPS daemon is running and multiplexing CUDA contexts")
    elif control_binary:
        mps_status = MPSStatus.INITIALIZED
        details_list.append("NVIDIA MPS control binary detected; daemon is idle / not started")
    else:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("nvidia-cuda-mps-control binary not found in PATH or standard system locations")

    env_dict = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
    }

    return MPSDaemonAudit(
        mps_control_binary=control_binary,
        mps_server_binary=server_binary,
        status=mps_status,
        pipe_directory=str(pipe_dir),
        log_directory=str(log_dir),
        socket_path=socket_path,
        is_daemon_active=is_running,
        pid=daemon_pid,
        socket_permissions=perm_str,
        is_permission_secure=sec_ok,
        server_active=server_active,
        control_active=control_active,
        environment_variables=env_dict,
        details="; ".join(details_list),
    )


def start_mps_daemon(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: str,
    server_binary: Optional[str] = None,
    force_restart: bool = False,
) -> MPSDaemonAudit:
    """
    Start the nvidia-cuda-mps-control daemon in background mode (-d).
    """
    if platform.system() == "Windows":
        return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)

    if force_restart:
        stop_mps_daemon(pipe_dir, control_binary)

    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    enforce_socket_directory_permissions(pipe_dir)
    enforce_socket_directory_permissions(log_dir)

    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
    env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)

    try:
        subprocess.run(
            [control_binary, "-d"],
            env=env,
            check=True,
            timeout=5,
            capture_output=True,
        )
    except Exception as exc:
        raise MPSControlError(f"Failed to start nvidia-cuda-mps-control daemon: {exc}") from exc

    return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)


def stop_mps_daemon(
    pipe_dir: Path,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Stop any running nvidia-cuda-mps-control daemon and backend server cleanly.
    """
    if platform.system() == "Windows":
        return True

    stopped = False
    if control_binary:
        env = os.environ.copy()
        env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
        try:
            subprocess.run(
                [control_binary],
                input="quit\n",
                text=True,
                env=env,
                timeout=3,
                capture_output=True,
            )
            stopped = True
        except Exception:
            pass

    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info.get("name") or ""
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-server" in pname:
                    proc.terminate()
                    stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    return stopped


def configure_mps_device_limit(
    pipe_dir: Path,
    device_index: int,
    limit_mb: int,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Configure dynamic pinned memory limits on a running MPS daemon via control pipe.
    Command: set_device_pinned_mem_limit <device_index> <limit_mb>M
    """
    if platform.system() == "Windows" or not control_binary:
        return False

    cmd_str = f"set_device_pinned_mem_limit {device_index} {limit_mb}M\nquit\n"
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)

    try:
        res = subprocess.run(
            [control_binary],
            input=cmd_str,
            text=True,
            env=env,
            timeout=3,
            capture_output=True,
        )
        return res.returncode == 0
    except Exception:
        return False


# =============================================================================
# 8. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION
# =============================================================================


def inject_mps_environment_variables(
    pipe_dir: Path,
    log_dir: Path,
    vram_budget: VRAMBudgetReport,
) -> Dict[str, str]:
    """
    Construct authoritative MPS and VRAM environment variables dictionary.
    Includes memory limits and active thread percentage partitioning (Method Matrix §8A.4).
    """
    thread_pct = max(1, min(100, int(100 // max(1, vram_budget.worker_concurrency_target))))
    env_vars: Dict[str, str] = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
        "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT": "1",
        "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(thread_pct),
    }

    if vram_budget.default_pinned_mem_limit:
        env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = vram_budget.default_pinned_mem_limit
    elif vram_budget.active_gpu_devices:
        first_limit = vram_budget.active_gpu_devices[0].pinned_mem_limit_str
        if first_limit:
            env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = first_limit

    for k, v in env_vars.items():
        os.environ[k] = v

    return env_vars


def generate_mps_activation_scripts(
    target_dir: Union[str, Path],
    env_vars: Dict[str, str],
) -> Dict[str, Path]:
    """
    Generate standalone shell and batch script wrappers to inject MPS and VRAM
    configuration into subshells, Jupyter kernels, and external worker processes.
    """
    out_dir = Path(target_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sh_path = out_dir / "cochem_activate_mps.sh"
    sh_lines = [
        "#!/bin/sh",
        "# CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        sh_lines.append(f'export {k}="{v}"')
    sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
    try:
        sh_path.chmod(sh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    bat_path = out_dir / "cochem_activate_mps.bat"
    bat_lines = [
        "@echo off",
        "rem CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        bat_lines.append(f"set {k}={v}")
    bat_path.write_text("\n".join(bat_lines) + "\n", encoding="utf-8")

    json_path = out_dir / "cochem_mps_config.json"
    json_path.write_text(
        json.dumps(
            {
                "env_vars": env_vars,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "sh": sh_path,
        "bat": bat_path,
        "json": json_path,
    }


# =============================================================================
# 9. PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_5_audit(
    output_dir: Optional[Union[str, Path]] = None,
    socket_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
    worker_concurrency: int = 2,
    custom_vram_limit_mb: Optional[float] = None,
    start_daemon: bool = False,
    force_restart: bool = False,
    dry_run: bool = False,
) -> Phase5AuditReport:
    """
    Execute full Phase 5 NVIDIA MPS Daemon Initialization & VRAM Budgeting Audit.
    Probes physical GPUs and VRAM capacities, calculates mathematical per-worker VRAM
    partitioning limits, initializes/audits the nvidia-cuda-mps-control daemon and Unix
    sockets at /tmp/cochem_mps_$USER (or $SLURM_TMPDIR), generates activation hooks,
    and atomically persists p5.json into the Golden Registry.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Resolve Pipe and Log Directories
    pipe_path = resolve_mps_pipe_directory(socket_dir)
    log_path = resolve_mps_log_directory(log_dir)

    is_slurm = bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_TMPDIR"))

    # 2. Discover GPU Devices and VRAM Capacities
    gpu_devices, is_cuda = probe_gpu_devices_vram()

    # 3. Calculate VRAM Budget & Concurrency Partitioning
    vram_budget = calculate_vram_budget(
        devices=gpu_devices,
        worker_concurrency_target=worker_concurrency,
        custom_limit_per_worker_mb=custom_vram_limit_mb,
    )

    if not is_cuda or not gpu_devices:
        warnings.append(
            "No active NVIDIA CUDA GPU detected; execution operating in CPU-only or direct compute fallback mode."
        )

    # 4. Discover MPS Binaries & Probe Daemon Status
    control_bin, server_bin = discover_mps_binaries()

    if start_daemon and control_bin and not dry_run:
        try:
            mps_daemon = start_mps_daemon(
                pipe_dir=pipe_path,
                log_dir=log_path,
                control_binary=control_bin,
                server_binary=server_bin,
                force_restart=force_restart,
            )
        except Exception as exc:
            warnings.append(f"Could not start MPS daemon: {exc}")
            mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)
    else:
        mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)

    # 5. Inject Environment Variables & Generate Scripts
    env_vars = inject_mps_environment_variables(pipe_path, log_path, vram_budget)
    mps_daemon.environment_variables = env_vars

    if not dry_run:
        generate_mps_activation_scripts(pipe_path, env_vars)

    # 6. Evaluate Phase Status
    if errors:
        phase_status = PhaseStatus.FAILED
    elif not is_cuda or mps_daemon.status in (MPSStatus.NOT_SUPPORTED, MPSStatus.DEGRADED):
        phase_status = PhaseStatus.PASSED  # Graceful pass in degraded/CPU mode
    else:
        phase_status = PhaseStatus.PASSED

    # 7. Destination Registry Artifact Path
    p5_path = resolve_p5_registry_path(output_dir)

    # 8. Construct Final Audit Report
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=phase_status,
        timestamp_utc=timestamp_utc,
        mps_daemon=mps_daemon,
        vram_budget=vram_budget,
        is_cuda_available=is_cuda,
        is_hpc_slurm=is_slurm,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p5_path),
    )

    # 9. Idempotent Atomic State Persistence
    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(p5_path, report)

    return report


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 5: NVIDIA MPS Daemon & VRAM Budgeting.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 5: NVIDIA MPS Daemon & VRAM Budgeting CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry/p5.json",
    )
    parser.add_argument(
        "--socket-dir",
        "-s",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_PIPE_DIRECTORY sockets",
    )
    parser.add_argument(
        "--log-dir",
        "-l",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_LOG_DIRECTORY telemetry logs",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=2,
        help="Target concurrent GPU workers for VRAM budget partitioning (default: 2)",
    )
    parser.add_argument(
        "--vram-limit-mb",
        type=float,
        default=None,
        help="Explicit pinned memory limit per worker in megabytes (overrides proportional formula)",
    )
    parser.add_argument(
        "--start-daemon",
        action="store_true",
        help="Attempt to start nvidia-cuda-mps-control daemon in background mode",
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Force restart of existing MPS daemon processes",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop active nvidia-cuda-mps-control daemon and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview VRAM budgeting without modifying filesystem or starting daemons",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    if args.stop:
        pipe_path = resolve_mps_pipe_directory(args.socket_dir)
        control_bin, _ = discover_mps_binaries()
        stopped = stop_mps_daemon(pipe_path, control_bin)
        status_msg = "MPS daemon stopped successfully." if stopped else "No active MPS daemon found to stop."
        print(status_msg)
        return 0

    try:
        report = run_phase_5_audit(
            output_dir=args.output_dir,
            socket_dir=args.socket_dir,
            log_dir=args.log_dir,
            worker_concurrency=args.workers,
            custom_vram_limit_mb=args.vram_limit_mb,
            start_daemon=args.start_daemon,
            force_restart=args.force_restart,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 5: NVIDIA MPS DAEMON & VRAM BUDGETING")
            print("=" * 75)
            print(f"Phase ID:        {report.phase_id}")
            print(f"Status:          {report.status.value}")
            print(f"Timestamp UTC:   {report.timestamp_utc}")
            print(f"Artifact Path:   {report.artifact_path}")
            print(f"CUDA Available:  {report.is_cuda_available}")
            print(f"Slurm HPC Mode:  {report.is_hpc_slurm}")
            print(f"MPS Status:      {report.mps_daemon.status.value}")
            print(f"Pipe Directory:  {report.mps_daemon.pipe_directory}")
            print(f"Socket Secure:   {report.mps_daemon.is_permission_secure} ({report.mps_daemon.socket_permissions})")
            print("-" * 75)
            print("VRAM Budgeting Matrix:")
            print(f"  Total GPUs:        {report.vram_budget.total_gpus_detected}")
            print(f"  Cluster VRAM:      {report.vram_budget.total_cluster_vram_mb:.0f} MB")
            print(f"  Reserved VRAM:     {report.vram_budget.total_reserved_vram_mb:.0f} MB")
            print(f"  Allocatable VRAM:  {report.vram_budget.total_allocatable_vram_mb:.0f} MB")
            print(f"  Target Workers:    {report.vram_budget.worker_concurrency_target}")
            print(f"  Default Pinned:    {report.vram_budget.default_pinned_mem_limit or 'N/A'}")
            for dev in report.vram_budget.active_gpu_devices:
                print(f"    [GPU {dev.index}] {dev.name:<25} Total: {dev.total_vram_mb:.0f}MB -> Limit: {dev.pinned_mem_limit_str} (Cap: {dev.active_worker_capacity} workers)")
            print("-" * 75)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 5 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

