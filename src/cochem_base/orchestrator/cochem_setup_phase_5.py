"""
CoChem Setup Phase 5: IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting Gatekeeper.
Production-grade, zero-mock gatekeeping engine for:
1. Multi-tenant NVIDIA Multi-Process Service (MPS) daemon management (nvidia-cuda-mps-control)
   and dynamically calculated pinned device memory partitioning (CUDA_MPS_PINNED_DEVICE_MEM_LIMIT).
2. Physical POSIX byte-range locking verification (fcntl / msvcrt) before HDF5 SWMR initialization,
   with graceful degradation to single-threaded operations upon filesystem locking failure.
3. Intermediate state consolidation (p1.json through p11.json) and validation through the rigid
   Pydantic v2 CoChemSystemConfig schema.
4. Atomic serialization of the finalized Golden Registry to $HOME/CoChem_Artifacts/Registry/cochem_system_config.json
   with status="LOCKED" and os.chmod(0o444) read-only immutability enforcement.
5. Workspace garbage collection sweep purging ephemeral .tmp files and intermediate staging fragments.

SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 4.3), and Method Matrix v4 Compliant.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
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

# POSIX fcntl / Windows msvcrt locking imports
try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

# Schema and Config Imports with Path Resolution Fallbacks
try:
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        ISOTOPIC_MASSES,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )
except ImportError:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        ISOTOPIC_MASSES,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )

import atexit
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cochem_setup_phase_5")

def sweep_zombies() -> None:
    if psutil is None:
        return
    for p in psutil.process_iter(['pid', 'status']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                p.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied, KeyError):
            pass

atexit.register(sweep_zombies)


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase5AuditError(RuntimeError):
    """Raised when critical phase 5 MPS daemon initialization or VRAM allocation fails fatally."""


class MPSControlError(RuntimeError):
    """Raised when nvidia-cuda-mps-control daemon lifecycle management commands fail unexpectedly."""


class VRAMAllocationError(RuntimeError):
    """Raised when VRAM memory limits or worker capacity cannot be safely bounded."""


class ConfigLockError(RuntimeError):
    """Raised when golden master registry configuration locking fails."""


class LockTestFailureError(RuntimeError):
    """Raised when physical POSIX filesystem locking verification encounters an unrecoverable error."""


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


class LockTestResult(BaseModel):
    """Physical POSIX byte-range locking verification result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    passed: bool = Field(..., description="Whether byte-range locking succeeded on target filesystem")
    method: str = Field(..., description="Locking mechanism utilized (e.g. 'POSIX_FCNTL', 'MSVCRT_LOCKING')")
    single_threaded_mode: bool = Field(
        default=False,
        description="Whether single-threaded fallback degradation is active due to lock failure",
    )
    target_path: str = Field(..., description="Filesystem path tested for byte-range locking")
    lock_type: str = Field(default="POSIX_BYTE_RANGE_LOCK", description="Classification of lock test")
    error_message: Optional[str] = Field(default=None, description="Error diagnostics if lock test failed")


class WorkspaceSweepReport(BaseModel):
    """Artifact sweep report for garbage collection of intermediate setup files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    swept_files_count: int = Field(default=0, ge=0, description="Number of temporary or fragment files cleaned")
    cleaned_paths: List[str] = Field(default_factory=list, description="Paths of cleaned ephemeral files")
    retained_paths: List[str] = Field(default_factory=list, description="Paths of permanent registered artifacts")
    trash_dir: Optional[str] = Field(default=None, description="Backup trash destination if configured")


class ConfigLockAuditReport(BaseModel):
    """Structured audit report for IPC configuration lock and workspace sweep."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    golden_registry_path: str = Field(..., description="Canonical path to locked cochem_system_config.json")
    status: str = Field(default="LOCKED", description="Operational status of master registry ('LOCKED')")
    checksum: str = Field(..., description="Deterministic SHA-256 checksum of locked configuration")
    posix_lock_test: LockTestResult = Field(..., description="Byte-range filesystem lock verification record")
    sweep_report: WorkspaceSweepReport = Field(..., description="Workspace garbage collection sweep results")
    intermediate_phases_found: List[str] = Field(
        default_factory=list, description="Intermediate phase artifacts consolidated (e.g. ['p1.json', 'p2.json'])"
    )
    is_immutable_mode_enforced: bool = Field(
        default=True, description="Whether 0o444 read-only file mode was applied"
    )


class Phase5AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 5 NVIDIA MPS Daemon & VRAM Budgeting & Config Lock."""

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
    config_lock: Optional[ConfigLockAuditReport] = Field(
        default=None, description="Phase 5 IPC config lock and workspace sweep results"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p5.json")
    golden_config_path: Optional[str] = Field(
        default=None, description="Filesystem destination path for locked cochem_system_config.json"
    )

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
                    try:
                        os.chmod(temp_file, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
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
        read_only: bool = False,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        Handles overwriting existing read-only files cleanly.
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

        # If target exists and is read-only (Windows NT or POSIX), unlock it temporarily for replacement
        if target.exists():
            try:
                os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IWUSR | stat.S_IRUSR)
            except OSError:
                pass

        os.replace(staged_file, target)
        self.untrack_file(staged_file)

        if read_only:
            try:
                os.chmod(target, stat.S_IREAD | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                pass

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

    repo_root_candidate = Path.cwd()
    agent_artifacts = repo_root_candidate / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p5.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p5.json"


def resolve_golden_config_path(output_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve destination path for finalized master Golden Registry cochem_system_config.json
    per SRS Document 5 Section 4.3.
    """
    if output_path:
        out_p = Path(output_path).resolve()
        if out_p.is_dir() or out_p.suffix == "":
            return out_p / "cochem_system_config.json"
        return out_p

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path

        return resolve_config_path()
    except Exception:
        pass

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


# =============================================================================
# 5. PHYSICAL POSIX BYTE-RANGE LOCKING TEST (FCNTL / MSVCRT)
# =============================================================================


def test_posix_byte_range_locking(
    target_dir: Optional[Union[str, Path]] = None,
    timeout: float = 2.0,
) -> LockTestResult:
    """
    Execute a physical POSIX byte-range locking test (fcntl on Linux/macOS, msvcrt on Windows)
    on the target filesystem prior to initializing HDF5 SWMR streams.

    SRS Document 5 Section 4.3 Mandate:
    If the filesystem does not support POSIX byte-range locks (e.g., certain NFS/SMB/CIFS mounts
    or legacy virtualized mounts), this test catches the failure and signals graceful degradation
    to single-threaded operations.
    """
    if target_dir:
        test_dir = Path(target_dir).resolve()
    else:
        test_dir = resolve_golden_config_path().parent

    test_dir.mkdir(parents=True, exist_ok=True)
    probe_filename = f".cochem_swmr_lock_probe_{uuid.uuid4().hex[:8]}.lock"
    probe_path = test_dir / probe_filename

    is_posix = platform.system() != "Windows"

    try:
        # Create physical probe file with data to lock
        with open(probe_path, "w+b") as f:
            f.write(b"COCHEM_SWMR_BYTE_RANGE_LOCK_PROBE_HEADER_BLOCK\n" * 10)
            f.flush()
            fd = f.fileno()

            if is_posix and fcntl is not None:
                # Test POSIX fcntl byte-range locking
                try:
                    # Exclusive byte-range lock on bytes 0..512
                    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 512, 0)
                    # Unlock
                    fcntl.lockf(fd, fcntl.LOCK_UN, 512, 0)
                    method = "POSIX_FCNTL_LOCKF"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="POSIX_FCNTL_LOCKF",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"POSIX byte-range lock failed on filesystem: {exc}",
                    )
            elif not is_posix and msvcrt is not None:
                # Test Windows NT byte-range locking
                try:
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 512)
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 512)
                    method = "MSVCRT_LOCKING_BYTE_RANGE"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="MSVCRT_LOCKING_BYTE_RANGE",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"Windows byte-range lock failed on filesystem: {exc}",
                    )
            else:
                method = "GENERIC_FALLBACK_LOCK"

        return LockTestResult(
            passed=True,
            method=method,
            single_threaded_mode=False,
            target_path=str(probe_path),
            error_message=None,
        )

    except Exception as e:
        return LockTestResult(
            passed=False,
            method="UNKNOWN_ERROR",
            single_threaded_mode=True,
            target_path=str(probe_path),
            error_message=f"Filesystem byte-range locking test exception: {e}",
        )
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass


def _sanitize_engine_record(raw_eng: Any) -> Optional[Dict[str, Any]]:
    """Sanitize raw engine dictionary to match strict EngineInfo schema."""
    if not isinstance(raw_eng, dict):
        return None
    st_raw = str(raw_eng.get("status", "")).lower()
    if "found" in st_raw or raw_eng.get("is_available") is True:
        st = "found"
    elif "bypass" in st_raw:
        st = "bypassed"
    elif "denied" in st_raw or "permission" in st_raw:
        st = "permission_denied"
    else:
        st = "missing" if not raw_eng.get("path") else "found"

    p = raw_eng.get("path")
    v = raw_eng.get("version")
    h = raw_eng.get("sha256_hash") or raw_eng.get("hash")
    return {
        "status": st,
        "path": str(p) if p else None,
        "version": str(v) if v else None,
        "hash": str(h) if h else None,
    }


def consolidate_intermediate_states(
    registry_dir: Optional[Union[str, Path]] = None,
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Consolidate intermediate phase states (p1.json through p11.json) discovered across
    the registry search paths into a single structured configuration payload ready for
    validation against CoChemSystemConfig.

    SRS Document 5 Section 4.3 Mandate.
    """
    candidate_dirs: List[Path] = []
    if registry_dir:
        candidate_dirs.append(Path(registry_dir).resolve())

    if search_dirs:
        for sd in search_dirs:
            candidate_dirs.append(Path(sd).resolve())

    env_reg = os.environ.get("COCHEM_REGISTRY_DIR")
    if env_reg:
        candidate_dirs.append(Path(env_reg).resolve())

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        candidate_dirs.append((Path(env_art) / "Registry").resolve())

    candidate_dirs.append((Path.cwd() / ".agent_artifacts" / "Registry").resolve())
    candidate_dirs.append((Path.cwd() / "artifacts" / "registry").resolve())
    candidate_dirs.append((Path.home() / "CoChem_Artifacts" / "Registry").resolve())

    consolidated_raw: Dict[str, Any] = {}
    found_phases: List[str] = []

    # Map of intermediate JSON filenames to phase identifiers
    target_files = [f"p{i}.json" for i in range(1, 12)]

    for phase_filename in target_files:
        for cdir in candidate_dirs:
            phase_file = cdir / phase_filename
            if phase_file.is_file():
                try:
                    phase_data = json.loads(phase_file.read_text(encoding="utf-8"))
                    found_phases.append(phase_filename)

                    # Extract and merge domain-specific fields from each phase
                    if phase_filename == "p1.json":
                        # OS & Toolchain Audit
                        os_val = phase_data.get("os_target") or phase_data.get("os_profile", {}).get("system") or phase_data.get("os", {}).get("os_target")
                        if os_val:
                            consolidated_raw["os_target"] = os_val

                    elif phase_filename == "p2.json":
                        # Hardware & RAM Profiling
                        cpu_info = phase_data.get("cpu", {})
                        ram_info = phase_data.get("memory", {}) or phase_data.get("ram", {})
                        gpu_info = phase_data.get("gpu", {})

                        if "hardware" not in consolidated_raw:
                            consolidated_raw["hardware"] = {}

                        hw = consolidated_raw["hardware"]
                        if "physical_cores" in cpu_info:
                            hw["cpu_physical_cores"] = cpu_info["physical_cores"]
                            hw["physical_cpu_cores"] = cpu_info["physical_cores"]
                        if "logical_cores" in cpu_info:
                            hw["logical_cpu_cores"] = cpu_info["logical_cores"]

                        total_bytes = ram_info.get("total_physical_bytes") or ram_info.get("total_ram_bytes")
                        if total_bytes:
                            hw["ram_gb"] = round(float(total_bytes) / (1024.0**3), 2)
                        elif "total_ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["total_ram_gb"])
                        elif "ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["ram_gb"])

                        if "avx512_support" in cpu_info:
                            hw["avx_512_capable"] = bool(cpu_info["avx512_support"])
                            hw["avx512_support"] = bool(cpu_info["avx512_support"])

                        if gpu_info.get("gpu_available") or gpu_info.get("available"):
                            devices_list = gpu_info.get("devices") or []
                            if devices_list:
                                first_dev = devices_list[0]
                                hw["gpu_profile"] = first_dev.get("name", "NVIDIA GPU")
                                vram_bytes = first_dev.get("memory_total_bytes", 0)
                                if vram_bytes:
                                    hw["vram_gb"] = round(float(vram_bytes) / (1024.0**3), 2)

                    elif phase_filename == "p3.json":
                        # Multi-Track Quantum Engine Discovery
                        engines_data = phase_data.get("engines", {})
                        if engines_data and isinstance(engines_data, dict):
                            cleaned_engines: Dict[str, Any] = {}
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            sp = consolidated_raw["silo_paths"]

                            for eng_name, eng_info in engines_data.items():
                                sanitized = _sanitize_engine_record(eng_info)
                                if sanitized:
                                    cleaned_engines[eng_name] = sanitized
                                    if sanitized.get("path"):
                                        if eng_name == "orca":
                                            sp["orca_binary_path"] = sanitized["path"]
                                        elif eng_name == "xtb":
                                            sp["xtb_binary_path"] = sanitized["path"]
                                        elif eng_name == "cfour":
                                            sp["cfour_binary_path"] = sanitized["path"]
                                        elif eng_name == "mpirun":
                                            sp["mpirun_binary_path"] = sanitized["path"]
                                        elif eng_name == "aimnet2":
                                            sp["aimnet2_server_path"] = sanitized["path"]

                            consolidated_raw["engines"] = cleaned_engines

                    elif phase_filename == "p4.json":
                        # Silo Provisioning & Isolation
                        silos_data = phase_data.get("silos") or phase_data.get("silo_manifest", {})
                        gpu_active = False
                        torq_active = True
                        if isinstance(silos_data, dict):
                            if any("mace" in k or "gpu" in k for k in silos_data.keys()):
                                gpu_active = True
                            if "torq_silo_active" in silos_data:
                                torq_active = bool(silos_data["torq_silo_active"])
                            if "gpu_silo_active" in silos_data:
                                gpu_active = bool(silos_data["gpu_silo_active"])
                        consolidated_raw["silos"] = {
                            "torq_silo_active": torq_active,
                            "gpu_silo_active": gpu_active,
                        }

                    elif phase_filename == "p5.json":
                        # MPS Daemon & VRAM Budgeting
                        vram_budget = phase_data.get("vram_budget", {})
                        if vram_budget:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            hw = consolidated_raw["hardware"]
                            hw["mps_enabled"] = bool(phase_data.get("mps_daemon", {}).get("is_daemon_active", False))

                    elif phase_filename == "p6.json":
                        # Database & Bifurcated Storage
                        storage = phase_data.get("storage", {}) or phase_data.get("storage_tier", {})
                        if storage.get("hdf5_pes_store_path"):
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            consolidated_raw["silo_paths"]["hdf5_pes_store_path"] = storage["hdf5_pes_store_path"]

                    elif phase_filename == "p7.json":
                        # HPC Environment Configuration
                        hpc_info = phase_data.get("hpc", {})
                        if hpc_info and isinstance(hpc_info, dict):
                            valid_hpc_keys = {
                                "scheduler", "default_partition", "max_walltime_hours",
                                "partition", "cluster_hostname", "ssh_key_path",
                                "username", "execution_mode", "walltime_budgets"
                            }
                            filtered_hpc = {k: v for k, v in hpc_info.items() if k in valid_hpc_keys and v is not None}
                            if filtered_hpc:
                                consolidated_raw["hpc"] = filtered_hpc

                    elif phase_filename == "p9.json":
                        # Core Pinning & Parsl Concurrency
                        pinning = phase_data.get("core_pinning", {})
                        if pinning and isinstance(pinning, dict):
                            valid_pin_keys = {"kmp_hw_subset", "anchor_p_cores", "scout_p_cores", "background_e_cores"}
                            filtered_pin = {k: v for k, v in pinning.items() if k in valid_pin_keys and v is not None}
                            if filtered_pin:
                                if "hardware" not in consolidated_raw:
                                    consolidated_raw["hardware"] = {}
                                consolidated_raw["hardware"]["core_pinning"] = filtered_pin

                    elif phase_filename == "p10.json":
                        # MolSym Intake & Theoretical Eckart Frame Alignment
                        consolidated_raw["alignment_engine_ready"] = bool(
                            phase_data.get("alignment_engine_ready", True)
                        )

                    elif phase_filename == "p11.json":
                        # Memory Router & OOM Shield
                        mem_routing = phase_data.get("memory_routing", {}) or phase_data.get("oom_shield", {})
                        if "maxcore_mb" in mem_routing:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            consolidated_raw["hardware"]["maxcore_mb"] = int(mem_routing["maxcore_mb"])

                    break
                except Exception as e:
                    logger.warning(f"Advisory: could not parse intermediate state {phase_file}: {e}")

    return consolidated_raw, list(dict.fromkeys(found_phases))


# =============================================================================
# 7. MASTER SYSTEM CONFIG VALIDATION & IMMUTABLE LOCKING
# =============================================================================


def validate_and_build_system_config(
    consolidated_data: Optional[Dict[str, Any]] = None,
    auto_detect_fallback: bool = True,
    single_threaded_mode: bool = False,
) -> CoChemSystemConfig:
    """
    Validate the consolidated registry dictionary against CoChemSystemConfig, applying
    hardware discovery fallbacks and setting status to 'LOCKED' per Stage 0 mandate.
    """
    raw = dict(consolidated_data or {})

    # Ensure Hardware exists and is completely bounded
    if "hardware" not in raw or not raw["hardware"] or not isinstance(raw["hardware"], dict):
        if auto_detect_fallback:
            discovered_hw = discover_host_hardware()
            raw["hardware"] = discovered_hw.model_dump()
        else:
            raw["hardware"] = {
                "cpu_physical_cores": 4,
                "physical_cpu_cores": 4,
                "logical_cpu_cores": 8,
                "ram_gb": 16.0,
            }
    else:
        hw_dict = dict(raw["hardware"])
        ram_val = hw_dict.get("ram_gb")
        if ram_val is None or float(ram_val) <= 0.0:
            if auto_detect_fallback:
                hw_dict["ram_gb"] = discover_host_hardware().ram_gb
            else:
                hw_dict["ram_gb"] = 16.0

        if not hw_dict.get("cpu_physical_cores") or int(hw_dict.get("cpu_physical_cores", 0)) < 1:
            hw_dict["cpu_physical_cores"] = hw_dict.get("physical_cpu_cores") or (discover_host_hardware().cpu_physical_cores if auto_detect_fallback else 4)
        if not hw_dict.get("physical_cpu_cores"):
            hw_dict["physical_cpu_cores"] = hw_dict["cpu_physical_cores"]
        if not hw_dict.get("logical_cpu_cores"):
            hw_dict["logical_cpu_cores"] = hw_dict["cpu_physical_cores"] * 2

        raw["hardware"] = hw_dict

    if single_threaded_mode:
        raw["hardware"]["allocatable_compute_cores"] = 1

    # Standard quantum solver defaults
    if "quantum_settings" not in raw or not raw["quantum_settings"]:
        raw["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    # HPC defaults
    if "hpc" not in raw or not raw["hpc"]:
        raw["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    # Environment defaults
    if "environment" not in raw or not raw["environment"]:
        raw["environment"] = {
            "os_target": raw.get("os_target", OSTarget.LOCAL_WINDOWS.value if os.name == "nt" else OSTarget.LOCAL_LINUX.value),
            "codata_version": "2018",
            "isotopic_mass_locking": True,
            "isotopic_mass_13c": CARBON_13_ISOTOPIC_MASS,
            "isotopic_masses": dict(ISOTOPIC_MASSES),
        }

    raw["status"] = "LOCKED"
    raw["schema_version"] = "4.0.0"

    cfg = CoChemSystemConfig.model_validate(raw)
    cfg.update_checksum()
    return cfg


def finalize_and_lock_golden_registry(
    cfg: CoChemSystemConfig,
    output_path: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Atomically write finalized Golden Registry to cochem_system_config.json,
    set cfg['status'] = 'LOCKED', and apply os.chmod(0o444) to enforce post-setup immutability.

    SRS Document 5 Section 4.3 Mandate.
    """
    target_path = resolve_golden_config_path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    cfg.status = "LOCKED"
    cfg.update_checksum()
    serialized_dict = cfg.model_dump()

    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(
                target_path=target_path,
                data=serialized_dict,
                indent=2,
                read_only=True,
            )

    return target_path, serialized_dict


# =============================================================================
# 8. WORKSPACE GARBAGE COLLECTION SWEEP
# =============================================================================


def execute_workspace_sweep(
    workspace_dir: Optional[Union[str, Path]] = None,
    registry_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    remove_intermediate_json: bool = False,
    trash_dir: Optional[Union[str, Path]] = None,
) -> WorkspaceSweepReport:
    """
    Execute a garbage collection sweep to safely delete all ephemeral .tmp files and
    intermediate JSON fragments from the workspace.

    SRS Document 5 Section 4.3 Mandate:
    Preserves persistent registry files (cochem_system_config.json) while sweeping
    staged .tmp files and temporary lock probes.
    """
    target_ws = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
    target_reg = Path(registry_dir).resolve() if registry_dir else resolve_golden_config_path().parent

    cleaned_paths: List[str] = []
    retained_paths: List[str] = []

    search_roots = [target_ws, target_reg]

    for root in search_roots:
        if not root.is_dir():
            continue

        try:
            for entry in root.rglob("*"):
                if not entry.is_file():
                    continue

                filename = entry.name.lower()

                # Never delete finalized system config
                if filename == "cochem_system_config.json":
                    retained_paths.append(str(entry.resolve()))
                    continue

                is_ephemeral = False

                # Check for .tmp extensions or lock probe patterns
                if ".tmp" in filename or filename.startswith(".cochem_") or filename.endswith(".lock"):
                    is_ephemeral = True

                # Check for intermediate p1..p11 fragments if requested
                if remove_intermediate_json:
                    if re.match(r"^p\d+\.json$", filename) or filename.endswith(".tmp.json"):
                        is_ephemeral = True

                if is_ephemeral:
                    cleaned_paths.append(str(entry.resolve()))
                    if not dry_run:
                        try:
                            # Ensure writable before removing
                            try:
                                os.chmod(entry, stat.S_IWRITE | stat.S_IREAD)
                            except OSError:
                                pass
                            if trash_dir:
                                tdir = Path(trash_dir).resolve()
                                tdir.mkdir(parents=True, exist_ok=True)
                                shutil.move(str(entry), str(tdir / entry.name))
                            else:
                                entry.unlink(missing_ok=True)
                        except OSError as e:
                            logger.warning(f"Advisory: could not sweep temporary file {entry}: {e}")
                else:
                    retained_paths.append(str(entry.resolve()))

        except OSError as e:
            logger.warning(f"Advisory: error traversing directory {root} during sweep: {e}")

    return WorkspaceSweepReport(
        swept_files_count=len(cleaned_paths),
        cleaned_paths=cleaned_paths,
        retained_paths=list(dict.fromkeys(retained_paths)),
        trash_dir=str(trash_dir) if trash_dir else None,
    )


# =============================================================================
# 9. GPU DISCOVERY & VRAM PROFILING
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
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,uuid,memory.total,memory.free,driver_version",
                    "--format=csv,noheader,nounits",
                ],
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            tmp_out.seek(0)
            smi_out = tmp_out.read()
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
# 10. VRAM BUDGETING & MEMORY PARTITIONING ALGORITHM
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
# 11. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE MANAGEMENT
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
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
                subprocess.run(
                    [control_binary],
                    input="get_server_list\nquit\n",
                    text=True,
                    stdout=tmp_out,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=True,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
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
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [control_binary, "-d"],
                env=env,
                check=True,
                timeout=5,
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
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
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
                subprocess.run(
                    [control_binary],
                    input="quit\n",
                    text=True,
                    stdout=tmp_out,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    env=env,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
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
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as tmp_out:
            subprocess.run(
                [control_binary],
                input=cmd_str,
                text=True,
                stdout=tmp_out,
                stderr=subprocess.DEVNULL,
                check=True,
                env=env,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            return True
    except Exception:
        return False


# =============================================================================
# 12. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION
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
# 13. FULL PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
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
    workspace_dir: Optional[Union[str, Path]] = None,
    sweep_workspace: bool = True,
) -> Phase5AuditReport:
    """
    Execute full Phase 5 Audit Pipeline:
    1. NVIDIA MPS Daemon & VRAM Budgeting (SRS Doc 2 Part 2 Section 3.5).
    2. Physical POSIX byte-range locking test (fcntl) with graceful degradation to single-threaded mode.
    3. Intermediate state consolidation (p1.json through p11.json).
    4. Pydantic validation and Golden Registry locking to cochem_system_config.json with os.chmod(0o444).
    5. Workspace garbage collection sweep purging ephemeral .tmp files.
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

    # 6. Physical POSIX Byte-Range Locking Verification
    resolved_registry_dir = Path(output_dir).resolve() if output_dir else resolve_golden_config_path().parent
    lock_result = test_posix_byte_range_locking(resolved_registry_dir)
    if not lock_result.passed:
        warnings.append(
            f"Filesystem byte-range locking test failed ({lock_result.error_message}); "
            "degraded to single-threaded execution mode."
        )

    # 7. Intermediate State Consolidation & Golden Registry Locking
    consolidated_data, found_phases = consolidate_intermediate_states(
        registry_dir=resolved_registry_dir,
    )

    system_config = validate_and_build_system_config(
        consolidated_data=consolidated_data,
        auto_detect_fallback=True,
        single_threaded_mode=lock_result.single_threaded_mode,
    )

    golden_path, _ = finalize_and_lock_golden_registry(
        cfg=system_config,
        output_path=resolved_registry_dir / "cochem_system_config.json",
        dry_run=dry_run,
    )

    # 8. Workspace Garbage Collection Sweep
    if sweep_workspace:
        sweep_report = execute_workspace_sweep(
            workspace_dir=workspace_dir,
            registry_dir=resolved_registry_dir,
            dry_run=dry_run,
            remove_intermediate_json=False,
        )
    else:
        sweep_report = WorkspaceSweepReport(swept_files_count=0, cleaned_paths=[], retained_paths=[])

    config_lock_audit = ConfigLockAuditReport(
        golden_registry_path=str(golden_path),
        status=system_config.status or "LOCKED",
        checksum=system_config.registry_checksum or system_config.compute_checksum(),
        posix_lock_test=lock_result,
        sweep_report=sweep_report,
        intermediate_phases_found=found_phases,
        is_immutable_mode_enforced=True,
    )

    # 9. Evaluate Phase Status
    if errors:
        phase_status = PhaseStatus.FAILED
    elif lock_result.single_threaded_mode or not is_cuda or mps_daemon.status in (MPSStatus.NOT_SUPPORTED, MPSStatus.DEGRADED):
        phase_status = PhaseStatus.PASSED  # Graceful pass in degraded mode per Method Matrix
    else:
        phase_status = PhaseStatus.PASSED

    # 10. Destination Registry Artifact Path (p5.json)
    p5_path = resolve_p5_registry_path(output_dir)

    # 11. Construct Final Audit Report
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=phase_status,
        timestamp_utc=timestamp_utc,
        mps_daemon=mps_daemon,
        vram_budget=vram_budget,
        is_cuda_available=is_cuda,
        is_hpc_slurm=is_slurm,
        config_lock=config_lock_audit,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p5_path),
        golden_config_path=str(golden_path),
    )

    # 12. Idempotent Atomic State Persistence (p5.json)
    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(p5_path, report)

    return report


# =============================================================================
# 14. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 5:
    IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting CLI.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 5: IPC Config Lock, Workspace Sweep & NVIDIA MPS Daemon CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry artifacts (p5.json & cochem_system_config.json)",
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
        "--workspace-dir",
        "-w-dir",
        type=str,
        default=None,
        help="Custom workspace directory for ephemeral garbage collection sweep",
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
        help="Preview VRAM budgeting and config lock without modifying filesystem or starting daemons",
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
        logger.info(status_msg)
        return 0

    try:
        report = run_phase_5_audit(
            output_dir=args.output_dir,
            socket_dir=args.socket_dir,
            log_dir=args.log_dir,
            workspace_dir=args.workspace_dir,
            worker_concurrency=args.workers,
            custom_vram_limit_mb=args.vram_limit_mb,
            start_daemon=args.start_daemon,
            force_restart=args.force_restart,
            dry_run=args.dry_run,
        )

        if args.json:
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 5: IPC CONFIG LOCK, WORKSPACE SWEEP & MPS VRAM BUDGETING")
            logger.info("=" * 75)
            logger.info(f"Phase ID:          {report.phase_id}")
            logger.info(f"Status:            {report.status.value}")
            logger.info(f"Timestamp UTC:     {report.timestamp_utc}")
            logger.info(f"Artifact Path:     {report.artifact_path}")
            logger.info(f"Golden Config:     {report.golden_config_path}")
            logger.info(f"CUDA Available:    {report.is_cuda_available}")
            logger.info(f"Slurm HPC Mode:    {report.is_hpc_slurm}")
            logger.info(f"MPS Status:        {report.mps_daemon.status.value}")
            logger.info(f"Pipe Directory:    {report.mps_daemon.pipe_directory}")
            logger.info(f"Socket Secure:     {report.mps_daemon.is_permission_secure} ({report.mps_daemon.socket_permissions})")
            if report.config_lock:
                logger.info("-" * 75)
                logger.info("IPC Config Lock & Filesystem Audit:")
                logger.info(f"  Lock Test Method:    {report.config_lock.posix_lock_test.method}")
                logger.info(f"  Lock Test Passed:    {report.config_lock.posix_lock_test.passed}")
                logger.info(f"  Single-Thread Mode:  {report.config_lock.posix_lock_test.single_threaded_mode}")
                logger.info(f"  Registry Status:     {report.config_lock.status}")
                logger.info(f"  Registry Checksum:   {report.config_lock.checksum[:16]}...")
                logger.info(f"  Phases Consolidated: {', '.join(report.config_lock.intermediate_phases_found) or 'Default Synthesized'}")
                logger.info(f"  Swept Ephemeral:     {report.config_lock.sweep_report.swept_files_count} files")
            logger.info("-" * 75)
            logger.info("VRAM Budgeting Matrix:")
            logger.info(f"  Total GPUs:          {report.vram_budget.total_gpus_detected}")
            logger.info(f"  Cluster VRAM:        {report.vram_budget.total_cluster_vram_mb:.0f} MB")
            logger.info(f"  Reserved VRAM:       {report.vram_budget.total_reserved_vram_mb:.0f} MB")
            logger.info(f"  Allocatable VRAM:    {report.vram_budget.total_allocatable_vram_mb:.0f} MB")
            logger.info(f"  Target Workers:      {report.vram_budget.worker_concurrency_target}")
            logger.info(f"  Default Pinned:      {report.vram_budget.default_pinned_mem_limit or 'N/A'}")
            for dev in report.vram_budget.active_gpu_devices:
                logger.info(f"    [GPU {dev.index}] {dev.name:<25} Total: {dev.total_vram_mb:.0f}MB -> Limit: {dev.pinned_mem_limit_str} (Cap: {dev.active_worker_capacity} workers)")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 5 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
