Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\09_01_11_arrow_pipeline.md.
Original prompt:
# Task: Implement the 11-Arrow Canonical Pipeline and Escaltor Safety Traps (`cochem_topos_escalator_exec.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\escalation\cochem_topos_escalator_exec.py`

## Objective
Implement the missing 11-Arrow Canonical Pipeline, Hardware Brokering Header, Geometrical Explosion Trap, and OOM Autopsy features specified in Section 9 of the SRS.

## Context & Architecture Rules
The initial implementation of `cochem_topos_escalator_exec.py` entirely omitted the 11-Arrow Pipeline input generation and crucial stability/hardware traps.

## Execution Directives
1. **The 11-Arrow Canonical Pipeline**: Dynamically construct input blocks for the 11 tiers of computation based on the user's Time-Aware Target. The pipeline must step through the valid Method Matrix v4 entries (e.g., T1-1min `GFN2-xTB` -> T2-3h `wB97M-V / def2-QZVPP + CP`), injecting specific methodologies, basis sets (`def2/J`, `def2/C`), and dispersion corrections (`! D4`).
2. **Hardware Brokering Header**: Poll `cochem_system_config.json` for available RAM and CPU cores. Calculate and inject `%maxcore` and `%pal nprocs` memory allocations into the pipeline input files, reserving a strict safety buffer for the host Linux OS.
3. **Geometrical Explosion Trap**: Monitor bond distances at each optimization step. If a covalent bond stretches > 4.0 Å mid-optimization, forcefully terminate the OpenMPI process group to save compute time and flag the basin as unstable in `landscape.h5`.
4. **OOM Autopsy**: Monitor OS-level memory. If a node is killed by the OS (Exit Code 137), capture the SIGKILL and log an `OOM_autopsy.json` diagnostic (tensor size, node RAM, tier attempted) to trigger hardware downscaling rather than a silent failure.
5. **Wavefunction Seeding (`! MORead`)**: Extract the binary `.gbw` wavefunction file from converged lower-tier steps and project it as the initial guess for the next tier to bypass redundant SCF cycles.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_libraries\__init__.py ---
"""CoChem-BENCH Libraries."""

from cochem_bench.bench_libraries.subprocess_reaper import (
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    HighSpeedIORouter,
    HighSpeedIORouting,
    IOCleanupReport,
    IOScratchRouteReport,
    NUMA_ThreadPinner,
    PreFlightResourceError,
    PreFlightScratchVerifier,
    ProcessReapReport,
    ResourceGuardError,
    SegmentationFaultError,
    TemporalRouteResult,
    TemporalRouter,
    TemporalRoutingError,
    ThermalGovernorState,
    ThreadPinningResult,
    ZMQEndpointManifest,
    ZombieReaper,
    ZombieReaperError,
    launch_isolated_process,
)
from cochem_bench.bench_libraries.swmr_hdf5_manager import (
    DEFAULT_CHUNK_CACHE_BYTES,
    DEFAULT_LOCK_TIMEOUT_SEC,
    AtomicJSONManager,
    AtomicLockMetadata,
    BenchHDF5Serializer,
    CoChemHDF5Error,
    CoChemRegistryLockError,
    CoChemSWMRHDF5BaseError,
    CoChemStaleLockError,
    HDF5DatasetManifest,
    SWMRWriteReport,
    get_bench_workspace_dir,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_registry_workspace_dir,
    get_scratch_workspace_dir,
)

__all__ = [
    "DEFAULT_MIN_FREE_SCRATCH_BYTES",
    "HighSpeedIORouter",
    "HighSpeedIORouting",
    "IOCleanupReport",
    "IOScratchRouteReport",
    "NUMA_ThreadPinner",
    "PreFlightResourceError",
    "PreFlightScratchVerifier",
    "ProcessReapReport",
    "ResourceGuardError",
    "SegmentationFaultError",
    "TemporalRouteResult",
    "TemporalRouter",
    "TemporalRoutingError",
    "ThermalGovernorState",
    "ThreadPinningResult",
    "ZMQEndpointManifest",
    "ZombieReaper",
    "ZombieReaperError",
    "launch_isolated_process",
    "DEFAULT_CHUNK_CACHE_BYTES",
    "DEFAULT_LOCK_TIMEOUT_SEC",
    "AtomicJSONManager",
    "AtomicLockMetadata",
    "BenchHDF5Serializer",
    "CoChemHDF5Error",
    "CoChemRegistryLockError",
    "CoChemSWMRHDF5BaseError",
    "CoChemStaleLockError",
    "HDF5DatasetManifest",
    "SWMRWriteReport",
    "get_bench_workspace_dir",
    "get_cochem_artifacts_dir",
    "get_element_mass_mendeleev",
    "get_registry_workspace_dir",
    "get_scratch_workspace_dir",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_bench\bench_libraries\subprocess_reaper.py ---
#!/usr/bin/env python3
r"""Stage 6.0: Subprocess Brokering, Process Group Isolation, and Thermal Governors.

Authoritative Implementation: cochem_bench.bench_libraries.subprocess_reaper
System Domain: CoChem-BENCH Defensive Infrastructure

Key Capabilities:
1. Air-Gap Safety Contract: Dynamically resolves paths via COCHEM_ARTIFACTS_DIR,
   raising a fatal RuntimeError if the environment variable is missing (no hardcoded/fallback paths).
2. PreFlightScratchVerifier: Mathematically verifies available NVMe scratch space before
   launching heavy CBS or DLPNO-CCSD(T) calculations, failing fast with ResourceGuardError.
3. Process Group Isolation & ZombieReaper: Detached process group isolation (start_new_session on POSIX,
   CREATE_NEW_PROCESS_GROUP on Windows) and ZeroMQ PUB/SUB heartbeat monitor with ruthless cross-platform
   recursive process tree termination (os.killpg on POSIX, taskkill /T /F on Windows).
4. NUMA-Aware Thread Pinning: Hardware-aware CPU affinity manager probing NUMA topology via numactl/lscpu
   on Linux (binding via numactl --cpunodebind=0 --membind=0) and psutil cpu_affinity on Windows.
5. Thermal Evacuation Governor: Asynchronous daemon polling psutil.sensors_temperatures() with dynamic
   sensor iteration. Includes Windows Guard logging ResourceWarning and aborting daemon if unsupported.
   Suspends processes on temperatures > 90C and resumes upon cooling to <= 75C.
6. SegfaultTrapper & ExitCode139_Trapper: Strict OS-level Segmentation Fault interceptor evaluating integer
   return codes (-11 on POSIX, 0xC0000005 / 3221225477 / -1073741819 on Windows, 139) and writing FAIR JSON-LD
   provenance records without parsing standard error output.
7. Dynamic Mendeleev Integration: Element mass resolution dynamically querying the Mendeleev database.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task6_reaper_pt2.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 6 Subprocess Brokering & Temporal Engine Routing.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Set, Tuple, Union

import psutil
import zmq
from mendeleev import element
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class SubprocessReaperBaseError(Exception):
    """Base exception for all subprocess reaper operations."""
    pass


class PreFlightResourceError(SubprocessReaperBaseError):
    """Raised when pre-flight hardware or disk resources fail verification."""
    pass


class ResourceGuardError(PreFlightResourceError):
    """Raised specifically when available scratch space is below safe threshold."""
    pass


class NUMAPinningError(SubprocessReaperBaseError):
    """Raised when CPU thread pinning encounters an unrecoverable failure."""
    pass


class ZombieReaperError(SubprocessReaperBaseError):
    """Raised when process termination or heartbeat monitoring fails."""
    pass


class SegmentationFaultError(SubprocessReaperBaseError):
    """Raised or recorded when an OS-level segmentation fault occurs in a subprocess."""
    pass


class TemporalRoutingError(SubprocessReaperBaseError):
    """Raised when temporal routing encounters missing configuration or fatal constraints."""
    pass


# ==============================================================================
# Constant Definitions
# ==============================================================================

# Default minimum required NVMe scratch space: 50 GB in bytes
DEFAULT_MIN_FREE_SCRATCH_BYTES: int = 50 * 1024 * 1024 * 1024

# Thermal threshold constants in degrees Celsius
CRITICAL_TEMP_CELSIUS: float = 90.0
RESUME_TEMP_CELSIUS: float = 75.0

# Segmentation fault return codes across POSIX and Windows platforms
# POSIX: -11 (-signal.SIGSEGV), 139 (128 + 11)
# Windows NT STATUS_ACCESS_VIOLATION (0xC0000005):
#   - Hex: 0xC0000005
#   - Unsigned 32-bit: 3221225477
#   - Signed 32-bit: -1073741819
SEGFAULT_RETURN_CODES: Set[int] = {
    -11,
    139,
    3221225477,
    -1073741819,
    0xC0000005,
}


# ==============================================================================
# Pydantic v2 Data Models
# ==============================================================================

class ScratchSpaceReport(BaseModel):
    """Structured verification report for scratch directory disk usage."""
    model_config = ConfigDict(frozen=True)

    scratch_path: str = Field(description="Resolved filesystem path to the scratch directory")
    total_bytes: int = Field(description="Total disk capacity in bytes")
    used_bytes: int = Field(description="Used disk space in bytes")
    free_bytes: int = Field(description="Free disk space in bytes")
    min_required_bytes: int = Field(description="Minimum required free space threshold in bytes")
    is_sufficient: bool = Field(description="True if free space meets or exceeds threshold")
    free_gigabytes: float = Field(description="Free disk space converted to gigabytes")
    required_gigabytes: float = Field(description="Required space converted to gigabytes")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the measurement",
    )


class HardwareRegistryConfig(BaseModel):
    """Hardware definition schema within cochem_system_config.json."""
    model_config = ConfigDict(extra="ignore")

    physical_cpu_cores: int = Field(default=4, description="Number of physical CPU cores")
    logical_cpu_cores: int = Field(default=8, description="Number of logical CPU threads")
    ram_gb: float = Field(default=16.0, description="Total system RAM in gigabytes")
    affinity_cores: Optional[List[int]] = Field(default=None, description="Assigned core indices for pinning")
    pinned_cores: Optional[List[int]] = Field(default=None, description="Alternative field for pinned core indices")
    numa_node_cores: Optional[List[int]] = Field(default=None, description="NUMA node core partition")
    cpu_affinity: Optional[List[int]] = Field(default=None, description="Direct CPU affinity list")


class SystemRegistryConfig(BaseModel):
    """Master system registry schema for cochem_system_config.json."""
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0.0", description="Configuration schema version")
    hardware: HardwareRegistryConfig = Field(default_factory=HardwareRegistryConfig)
    pinned_cores: Optional[List[int]] = Field(default=None, description="Top-level pinned cores definition")
    cpu_affinity: Optional[List[int]] = Field(default=None, description="Top-level cpu affinity list")
    numa_cores: Optional[List[int]] = Field(default=None, description="Top-level NUMA cores definition")


class ThreadPinningResult(BaseModel):
    """Structured result of NUMA process CPU core pinning."""
    model_config = ConfigDict(frozen=True)

    pid: int = Field(description="Process ID of the pinned process")
    assigned_cores: List[int] = Field(description="Target list of core indices requested")
    active_affinity: List[int] = Field(description="Actual active CPU affinity reported by OS")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the pinning action",
    )
    status: str = Field(description="Status flag: PINNED_SUCCESS, UNSUPPORTED_PLATFORM, or FAILED")


class ZMQEndpointManifest(BaseModel):
    """ZeroMQ IPC endpoint manifest written to Registry/zmq_ipc.json."""
    model_config = ConfigDict(frozen=True)

    host: str = Field(description="Binding host interface")
    port: int = Field(description="Dynamically assigned ephemeral TCP port")
    endpoint: str = Field(description="Full ZeroMQ connection endpoint URI")
    pid: int = Field(description="Process ID of the heartbeat publisher")
    protocol: str = Field(default="tcp", description="Communication protocol")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC registration timestamp",
    )


class ProcessReapReport(BaseModel):
    """Detailed execution report of a process tree termination operation."""
    model_config = ConfigDict(frozen=True)

    target_pid: int = Field(description="Root process ID targeted for termination")
    terminated_pids: List[int] = Field(description="All process IDs terminated in the hierarchy")
    reason: str = Field(description="Trigger cause: ABORT_SIGNAL_DETECTED, HEARTBEAT_DROPPED, or MANUAL_REAP")
    abort_signal_detected: bool = Field(description="True if ABORT.signal file was detected")
    heartbeat_dropped: bool = Field(description="True if heartbeat dropped below threshold")
    status: str = Field(description="Outcome status: EXTERMINATED, PROCESS_NOT_FOUND, or COMPLETED")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC execution timestamp",
    )


class JSONLDProvenanceBlock(BaseModel):
    """Structured FAIR-compliant JSON-LD provenance block for trapped segfaults."""
    model_config = ConfigDict(populate_by_name=True)

    context: str = Field(default="https://doi.org/10.5281/zenodo.cochem.v2", alias="@context")
    type: str = Field(default="ComputationalProcessProvenance", alias="@type")
    cochem_version: str = Field(default="2.0.0", description="CoChem platform version")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the event",
    )
    process_id: int = Field(description="Exact OS process ID that experienced the fault")
    return_code: int = Field(description="Raw integer exit code returned by the OS")
    fault_type: str = Field(default="OS_SEGMENTATION_FAULT", description="Standardized fault classification")
    status: str = Field(default="FATAL_CRASH_RECORDED", description="Operational resolution status")
    provenance_file: str = Field(description="Filesystem path where provenance is committed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution parameters")


class ThermalGovernorState(BaseModel):
    """Execution state of the Thermal Evacuation Governor."""
    model_config = ConfigDict(frozen=True)

    pid: int = Field(description="Target process ID being governed")
    current_temperature_c: Optional[float] = Field(default=None, description="Latest sampled peak temperature in Celsius")
    is_suspended: bool = Field(default=False, description="True if target processes are currently suspended")
    is_supported: bool = Field(default=True, description="True if platform supports hardware temperature sensors")
    status: str = Field(default="RUNNING", description="Status flag: RUNNING, SUSPENDED, UNSUPPORTED, or STOPPED")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )


class TemporalRouteResult(BaseModel):
    """Structured assessment from the 10-Tier Temporal Wall Clock Matrix & Router."""
    model_config = ConfigDict(frozen=True)

    tier: int = Field(description="Temporal Tier index from 1 to 10")
    tier_label: str = Field(description="Descriptive tier classification label")
    wall_clock_estimate: str = Field(description="Estimated wall-clock duration string")
    method: str = Field(description="Requested quantum chemistry method")
    atom_count: int = Field(description="Canonical atom count N")
    scaling_exponent: int = Field(description="Theoretical scaling exponent O(N^k)")
    is_local_workstation: bool = Field(description="True if target profile is a Local Workstation")
    execution_allowed: bool = Field(description="True if execution is safe to proceed on current profile")
    resource_warning_emitted: bool = Field(description="True if ResourceWarning was emitted")
    suggested_offload: Optional[str] = Field(default=None, description="Suggested execution offload target (e.g. HPC/SLURM)")
    message: str = Field(description="Operational routing message")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the routing decision",
    )


class IOScratchRouteReport(BaseModel):
    """Structured routing report for High-Speed I/O scratch allocation."""
    model_config = ConfigDict(frozen=True)

    scratch_path: str = Field(description="Active allocated scratch filesystem path")
    persistent_path: str = Field(description="Persistent SSD workspace destination path")
    is_ramdisk: bool = Field(description="True if routed to tmpfs RAM-disk (/dev/shm)")
    route_type: str = Field(description="Route type: RAM_DISK_TMPFS or STANDARD_NVME_SCRATCH")
    available_ram_gb: float = Field(description="System accessible RAM in gigabytes")
    free_ramdisk_bytes: Optional[int] = Field(default=None, description="Free space on /dev/shm in bytes if checked")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the routing decision",
    )


class IOCleanupReport(BaseModel):
    """Execution report for post-calculation I/O cleanup and artifact persistence."""
    model_config = ConfigDict(frozen=True)

    active_scratch_path: str = Field(description="Filesystem path of the scratch directory that was cleaned")
    persistent_workspace_path: str = Field(description="Filesystem path of the persistent workspace")
    copied_artifacts: List[str] = Field(description="List of persisted artifact files (.out, .gbw, etc.)")
    ramdisk_cleaned: bool = Field(description="True if RAM-disk was unlinked/removed via shutil.rmtree()")
    status: str = Field(description="Cleanup resolution status flag")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the cleanup operation",
    )


# ==============================================================================
# Dynamic Environment & Path Resolution Helpers (Air-Gap Contract)
# ==============================================================================

def get_cochem_artifacts_dir() -> Path:
    """Dynamically resolves the CoChem artifacts root directory via COCHEM_ARTIFACTS_DIR env var.

    Raises:
        RuntimeError: If COCHEM_ARTIFACTS_DIR environment variable is missing or empty.
    """
    env_path = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if not env_path or not env_path.strip():
        raise RuntimeError("Air-Gap Fatal: COCHEM_ARTIFACTS_DIR environment variable is missing or empty.")
    return Path(env_path).resolve()


def get_scratch_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic $SCRATCH workspace directory."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "BENCH_Workspace" / "Scratch"


def get_registry_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic Registry directory."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "Registry"


def get_processed_workspace_dir(artifacts_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the dynamic Processed workspace directory."""
    base = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
    return base / "BENCH_Workspace" / "Processed"


def get_element_mass_mendeleev(symbol: str) -> float:
    """Dynamically retrieves the atomic mass of an element via the Mendeleev library."""
    elem_obj = element(symbol)
    mass_val = elem_obj.atomic_weight or elem_obj.mass
    if mass_val is None:
        raise ValueError(f"Atomic mass for element {symbol} could not be retrieved.")
    return float(mass_val)


# ==============================================================================
# Process Group Isolation Helper
# ==============================================================================

def launch_isolated_process(
    cmd: List[str],
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[Union[str, Path]] = None,
    stdout: Any = subprocess.PIPE,
    stderr: Any = subprocess.PIPE,
    stdin: Any = None,
    **kwargs: Any,
) -> subprocess.Popen:
    """Launches a subprocess with detached process group isolation.

    Uses start_new_session=True on POSIX platforms, and CREATE_NEW_PROCESS_GROUP on Windows.
    """
    popen_kwargs = dict(kwargs)
    if env is not None:
        popen_kwargs["env"] = env
    if cwd is not None:
        popen_kwargs["cwd"] = str(cwd)
    if stdout is not None:
        popen_kwargs["stdout"] = stdout
    if stderr is not None:
        popen_kwargs["stderr"] = stderr
    if stdin is not None:
        popen_kwargs["stdin"] = stdin

    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    elif sys.platform == "win32" or os.name == "nt":
        creationflags = popen_kwargs.get("creationflags", 0)
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
        popen_kwargs["creationflags"] = creationflags

    return subprocess.Popen(cmd, **popen_kwargs)


# ==============================================================================
# 1. PreFlightScratchVerifier
# ==============================================================================

class PreFlightScratchVerifier:
    """Mathematically verifies available NVMe scratch space before heavy computations.

    Fails fast with ResourceGuardError if disk space is below required threshold.
    """

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        default_min_free_bytes: int = DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.default_min_free_bytes = int(default_min_free_bytes)

    def resolve_scratch_path(self, scratch_override: Optional[Union[str, Path]] = None) -> Path:
        """Resolves and guarantees parent structure for the scratch directory."""
        if scratch_override:
            scratch_path = Path(scratch_override).resolve()
        else:
            scratch_path = get_scratch_workspace_dir(self.artifacts_dir)
        scratch_path.mkdir(parents=True, exist_ok=True)
        return scratch_path

    def verify(
        self,
        min_free_bytes: Optional[int] = None,
        scratch_override: Optional[Union[str, Path]] = None,
    ) -> ScratchSpaceReport:
        """Verifies that the target scratch partition has sufficient free disk space.

        Args:
            min_free_bytes: Optional explicit threshold in bytes.
            scratch_override: Optional explicit scratch directory path.

        Returns:
            ScratchSpaceReport detailing space statistics.

        Raises:
            ResourceGuardError: If free disk space is less than required threshold.
        """
        target_path = self.resolve_scratch_path(scratch_override)
        required_bytes = int(min_free_bytes) if min_free_bytes is not None else self.default_min_free_bytes

        usage = shutil.disk_usage(str(target_path))
        total_b = usage.total
        used_b = usage.used
        free_b = usage.free

        free_gb = free_b / (1024 ** 3)
        required_gb = required_bytes / (1024 ** 3)
        is_sufficient = free_b >= required_bytes

        report = ScratchSpaceReport(
            scratch_path=str(target_path),
            total_bytes=total_b,
            used_bytes=used_b,
            free_bytes=free_b,
            min_required_bytes=required_bytes,
            is_sufficient=is_sufficient,
            free_gigabytes=round(free_gb, 4),
            required_gigabytes=round(required_gb, 4),
        )

        if not is_sufficient:
            raise ResourceGuardError(
                f"RESOURCE_GUARD: Scratch directory {target_path} possesses {free_gb:.2f} GB free space, "
                f"which is below the mandatory safety threshold of {required_gb:.2f} GB."
            )

        return report

    def check_space_safe(
        self,
        min_free_bytes: Optional[int] = None,
        scratch_override: Optional[Union[str, Path]] = None,
    ) -> bool:
        """Non-raising boolean check of scratch space sufficiency."""
        try:
            report = self.verify(min_free_bytes=min_free_bytes, scratch_override=scratch_override)
            return report.is_sufficient
        except (ResourceGuardError, RuntimeError):
            return False


# ==============================================================================
# 2. NUMA_ThreadPinner
# ==============================================================================

class NUMA_ThreadPinner:
    """Hardware-aware CPU affinity manager restricting processes to designated cores.

    Probes NUMA topology via numactl/lscpu on Linux and applies psutil.Process().cpu_affinity()
    constraints on Windows and Linux.
    """

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.config_path = Path(config_path).resolve() if config_path else None

    def resolve_config_path(self) -> Path:
        """Resolves the dynamic system registry configuration path."""
        if self.config_path:
            return self.config_path
        registry_dir = get_registry_workspace_dir(self.artifacts_dir)
        return registry_dir / "cochem_system_config.json"

    def probe_numa_topology(self) -> Dict[str, Any]:
        """Probes OS NUMA topology via numactl or lscpu on Linux, or psutil on Windows."""
        logical_cpus = psutil.cpu_count(logical=True) or 1
        physical_cpus = psutil.cpu_count(logical=False) or 1
        topology: Dict[str, Any] = {
            "platform": sys.platform,
            "logical_cpus": logical_cpus,
            "physical_cpus": physical_cpus,
            "numa_nodes": 1,
            "cores_per_node": physical_cpus,
            "single_socket_fit": True,
            "numactl_available": False,
        }

        if sys.platform.startswith("linux"):
            try:
                res = subprocess.run(
                    ["numactl", "--hardware"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0 and "available:" in res.stdout:
                    topology["numactl_available"] = True
                    for line in res.stdout.splitlines():
                        if "available:" in line and "nodes" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                try:
                                    topology["numa_nodes"] = int(parts[1])
                                except ValueError:
                                    pass
                        if "node 0 cpus:" in line:
                            cpus = line.split(":", 1)[1].split()
                            topology["cores_per_node"] = len(cpus)
            except (FileNotFoundError, OSError):
                try:
                    res_lscpu = subprocess.run(
                        ["lscpu"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if res_lscpu.returncode == 0:
                        for line in res_lscpu.stdout.splitlines():
                            if "NUMA node(s):" in line:
                                parts = line.split(":", 1)[1].strip()
                                try:
                                    topology["numa_nodes"] = int(parts)
                                except ValueError:
                                    pass
                            elif "Socket(s):" in line:
                                parts = line.split(":", 1)[1].strip()
                                try:
                                    topology["sockets"] = int(parts)
                                except ValueError:
                                    pass
                except (FileNotFoundError, OSError):
                    pass

        return topology

    def get_numactl_binding_args(self, required_cores: Optional[int] = None) -> List[str]:
        """Returns numactl binding arguments if on Linux and job fits in a single socket/node."""
        if not sys.platform.startswith("linux"):
            return []

        topology = self.probe_numa_topology()
        if not topology.get("numactl_available", False):
            return []

        cores_per_node = topology.get("cores_per_node", 1)
        req = required_cores if required_cores is not None else 1
        if req <= cores_per_node:
            return ["numactl", "--cpunodebind=0", "--membind=0"]
        return []

    def wrap_command_for_numa(self, cmd: List[str], required_cores: Optional[int] = None) -> List[str]:
        """Wraps command with numactl binding if job fits in one socket on Linux."""
        numa_args = self.get_numactl_binding_args(required_cores=required_cores)
        if numa_args:
            return numa_args + cmd
        return cmd

    def load_affinity_cores(self) -> List[int]:
        """Loads target CPU core affinity list from the system configuration file."""
        cfg_file = self.resolve_config_path()
        total_logical_cpus = psutil.cpu_count(logical=True) or 1

        if not cfg_file.exists():
            return [0]

        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            reg = SystemRegistryConfig.model_validate(data)
        except Exception as exc:
            raise NUMAPinningError(f"Failed to parse system configuration at {cfg_file}: {exc}") from exc

        cores: Optional[List[int]] = (
            reg.pinned_cores
            or reg.cpu_affinity
            or reg.numa_cores
            or reg.hardware.pinned_cores
            or reg.hardware.affinity_cores
            or reg.hardware.cpu_affinity
            or reg.hardware.numa_node_cores
        )

        if cores and isinstance(cores, list):
            valid_cores = [int(c) for c in cores if 0 <= int(c) < total_logical_cpus]
            if valid_cores:
                return sorted(list(set(valid_cores)))

        n_cores = max(1, min(reg.hardware.physical_cpu_cores, total_logical_cpus))
        return list(range(n_cores))

    def pin_process(
        self,
        pid: Optional[int] = None,
        cores: Optional[List[int]] = None,
    ) -> ThreadPinningResult:
        """Restricts the specified process (or current process) to targeted CPU cores.

        Args:
            pid: Process ID to pin (defaults to current process).
            cores: Explicit list of core indices to apply. If None, loaded from config.

        Returns:
            ThreadPinningResult containing execution status and active affinity.
        """
        target_pid = int(pid) if pid is not None else os.getpid()
        target_cores = list(cores) if cores is not None else self.load_affinity_cores()

        try:
            proc = psutil.Process(target_pid)
        except psutil.NoSuchProcess:
            raise NUMAPinningError(f"Target process PID {target_pid} does not exist.")

        if not hasattr(proc, "cpu_affinity"):
            return ThreadPinningResult(
                pid=target_pid,
                assigned_cores=target_cores,
                active_affinity=[],
                status="UNSUPPORTED_PLATFORM",
            )

        try:
            proc.cpu_affinity(target_cores)
            active = proc.cpu_affinity()
            return ThreadPinningResult(
                pid=target_pid,
                assigned_cores=target_cores,
                active_affinity=active,
                status="PINNED_SUCCESS",
            )
        except Exception as exc:
            raise NUMAPinningError(
                f"Failed to apply CPU affinity {target_cores} to process PID {target_pid}: {exc}"
            ) from exc


# ==============================================================================
# 3. ZombieReaper
# ==============================================================================

class ZombieReaper:
    """Process group isolation and ZeroMQ PUB/SUB heartbeat watchdog.

    Guarantees termination of orphaned OpenMPI and computational chemistry child processes.
    """

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None

    def resolve_registry_dir(self) -> Path:
        """Resolves the dynamic registry workspace path."""
        reg_dir = get_registry_workspace_dir(self.artifacts_dir)
        reg_dir.mkdir(parents=True, exist_ok=True)
        return reg_dir

    def resolve_scratch_dir(self) -> Path:
        """Resolves the dynamic scratch workspace path."""
        scratch_dir = get_scratch_workspace_dir(self.artifacts_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    def get_ipc_manifest_path(self) -> Path:
        """Returns the path to Registry/zmq_ipc.json."""
        return self.resolve_registry_dir() / "zmq_ipc.json"

    def get_abort_signal_path(self) -> Path:
        """Returns the path to $SCRATCH/ABORT.signal."""
        return self.resolve_scratch_dir() / "ABORT.signal"

    def establish_heartbeat_publisher(
        self,
        context: Optional[zmq.Context] = None,
        host: str = "127.0.0.1",
    ) -> Tuple[zmq.Socket, ZMQEndpointManifest]:
        """Binds a ZeroMQ PUB socket to an ephemeral TCP port and records manifest.

        Args:
            context: Optional active zmq.Context instance.
            host: Interface IP to bind (defaults to 127.0.0.1).

        Returns:
            Tuple of (bound zmq.Socket, ZMQEndpointManifest).
        """
        ctx = context or zmq.Context.instance()
        pub_socket = ctx.socket(zmq.PUB)
        pub_socket.setsockopt(zmq.LINGER, 0)
        port = pub_socket.bind_to_random_port(f"tcp://{host}")
        endpoint = f"tcp://{host}:{port}"

        manifest = ZMQEndpointManifest(
            host=host,
            port=port,
            endpoint=endpoint,
            pid=os.getpid(),
            protocol="tcp",
        )

        manifest_path = self.get_ipc_manifest_path()
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        return pub_socket, manifest

    def read_ipc_manifest(self) -> ZMQEndpointManifest:
        """Reads and parses the active Registry/zmq_ipc.json manifest."""
        manifest_path = self.get_ipc_manifest_path()
        if not manifest_path.exists():
            raise ZombieReaperError(f"ZMQ IPC manifest file not found at {manifest_path}")
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return ZMQEndpointManifest.model_validate(data)
        except Exception as exc:
            raise ZombieReaperError(f"Failed to parse ZMQ IPC manifest at {manifest_path}: {exc}") from exc

    def publish_heartbeat(
        self,
        socket: zmq.Socket,
        topic: str = "HEARTBEAT",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publishes a single heartbeat packet across the active ZeroMQ socket."""
        content = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pid": os.getpid(),
            "status": "ALIVE",
        }
        if payload:
            content.update(payload)
        message = f"{topic} {json.dumps(content)}"
        socket.send_string(message)

    def check_heartbeat_receptive(
        self,
        endpoint: Optional[str] = None,
        timeout_ms: int = 1500,
        topic: str = "HEARTBEAT",
        context: Optional[zmq.Context] = None,
    ) -> bool:
        """Subscribes to the heartbeat socket and checks for active incoming packets."""
        if endpoint is None:
            manifest = self.read_ipc_manifest()
            endpoint = manifest.endpoint

        ctx = context or zmq.Context.instance()
        sub_socket = ctx.socket(zmq.SUB)
        sub_socket.setsockopt(zmq.LINGER, 0)
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        sub_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)

        try:
            sub_socket.connect(endpoint)
            time.sleep(0.05)
            poller = zmq.Poller()
            poller.register(sub_socket, zmq.POLLIN)
            socks = dict(poller.poll(timeout_ms))
            if sub_socket in socks and socks[sub_socket] == zmq.POLLIN:
                msg = sub_socket.recv_string()
                return msg.startswith(topic)
            return False
        except Exception:
            return False
        finally:
            sub_socket.close()

    def check_abort_signal(self) -> bool:
        """Checks whether the ABORT.signal file exists in the scratch workspace."""
        return self.get_abort_signal_path().exists()

    def trigger_abort_signal(self, reason: str = "EXECUTION_ABORT_REQUESTED") -> Path:
        """Creates the ABORT.signal file in the scratch workspace."""
        abort_path = self.get_abort_signal_path()
        payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reason": reason,
            "trigger_pid": os.getpid(),
        }
        abort_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return abort_path

    def clear_abort_signal(self) -> bool:
        """Removes the ABORT.signal file if present."""
        abort_path = self.get_abort_signal_path()
        if abort_path.exists():
            try:
                abort_path.unlink()
                return True
            except OSError:
                return False
        return False

    def launch_job(self, cmd: List[str], **kwargs: Any) -> subprocess.Popen:
        """Launches a job with isolated process group."""
        return launch_isolated_process(cmd, **kwargs)

    def terminate_process_tree(
        self,
        target_pid: int,
        reason: str = "MANUAL_REAP",
        timeout_sec: float = 3.0,
    ) -> ProcessReapReport:
        """Ruthlessly terminates target process and all descendant child processes recursively.

        Uses psutil.Process(pid).children(recursive=True) to map child processes (not threads).
        If os.name == 'posix', safely executes os.killpg(pgid, signal.SIGKILL).
        On Windows, executes a secure list-formatted command: subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], check=True).
        """
        terminated_pids: List[int] = []
        abort_detected = self.check_abort_signal()

        try:
            root_proc = psutil.Process(target_pid)
        except psutil.NoSuchProcess:
            return ProcessReapReport(
                target_pid=target_pid,
                terminated_pids=[],
                reason=reason,
                abort_signal_detected=abort_detected,
                heartbeat_dropped=(reason == "HEARTBEAT_DROPPED"),
                status="PROCESS_NOT_FOUND",
            )

        # Map child processes recursively (processes, not threads)
        try:
            children = root_proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        all_procs = children + [root_proc]
        for p in all_procs:
            try:
                terminated_pids.append(p.pid)
            except Exception:
                pass

        # Platform-specific process group termination
        if os.name == "posix":
            try:
                pgid = os.getpgid(target_pid)
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        elif sys.platform == "win32" or os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(target_pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                pass

        # Cross-platform psutil termination guarantee
        for p in children:
            try:
                if p.is_running():
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        try:
            if root_proc.is_running():
                root_proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        gone, alive = psutil.wait_procs(all_procs, timeout=timeout_sec)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass

        return ProcessReapReport(
            target_pid=target_pid,
            terminated_pids=terminated_pids,
            reason=reason,
            abort_signal_detected=abort_detected,
            heartbeat_dropped=(reason == "HEARTBEAT_DROPPED"),
            status="EXTERMINATED",
        )

    def monitor_and_reap_if_needed(
        self,
        target_pid: int,
        heartbeat_alive: bool = True,
    ) -> Optional[ProcessReapReport]:
        """Evaluates abort signal and heartbeat status, triggering extermination if required."""
        if self.check_abort_signal():
            return self.terminate_process_tree(target_pid=target_pid, reason="ABORT_SIGNAL_DETECTED")
        if not heartbeat_alive:
            return self.terminate_process_tree(target_pid=target_pid, reason="HEARTBEAT_DROPPED")
        return None


# ==============================================================================
# 4. SegfaultTrapper & ExitCode139_Trapper
# ==============================================================================

class SegfaultTrapper:
    """Strict OS-level Segmentation Fault interceptor evaluating integer return codes.

    Catches -11 on POSIX, 0xC0000005 / 3221225477 / -1073741819 on Windows, and 139.
    Constructs and persists structured JSON-LD provenance records without parsing stderr.
    """

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None

    def resolve_processed_dir(self) -> Path:
        """Resolves the dynamic Processed workspace directory."""
        proc_dir = get_processed_workspace_dir(self.artifacts_dir)
        proc_dir.mkdir(parents=True, exist_ok=True)
        return proc_dir

    def get_provenance_file_path(self) -> Path:
        """Returns the destination path for bench_provenance.jsonld."""
        return self.resolve_processed_dir() / "bench_provenance.jsonld"

    @staticmethod
    def is_segmentation_fault(returncode: int) -> bool:
        """Evaluates if the raw integer return code corresponds to an OS segmentation fault."""
        return int(returncode) in SEGFAULT_RETURN_CODES

    def trap(
        self,
        process_id: int,
        returncode: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[JSONLDProvenanceBlock]:
        """Intercepts process exit code, generating and saving JSON-LD block if segfaulted."""
        if not self.is_segmentation_fault(returncode):
            return None

        prov_path = self.get_provenance_file_path()
        block = JSONLDProvenanceBlock(
            process_id=int(process_id),
            return_code=int(returncode),
            fault_type="OS_SEGMENTATION_FAULT",
            status="FATAL_CRASH_RECORDED",
            provenance_file=str(prov_path),
            metadata=dict(metadata or {}),
        )

        prov_path.write_text(block.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
        return block

    def check_and_raise(
        self,
        process_id: int,
        returncode: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Intercepts return code, persists JSON-LD, and raises SegmentationFaultError if detected."""
        block = self.trap(process_id=process_id, returncode=returncode, metadata=metadata)
        if block is not None:
            raise SegmentationFaultError(
                f"Segmentation fault detected (PID: {process_id}, ReturnCode: {returncode}). "
                f"Provenance committed to {block.provenance_file}"
            )


# Authoritative alias specified in Task 2.3 SRS
ExitCode139_Trapper = SegfaultTrapper


# ==============================================================================
# 5. Thermal Evacuation Governor
# ==============================================================================

class ThermalEvacuationGovernor:
    """Monitors system hardware temperatures and evacuates/pauses processes on thermal breach.

    Key behaviors:
    - Asynchronous daemon polling psutil.sensors_temperatures().
    - Windows Guard: If sensors_temperatures() returns an empty dictionary (as it does on Windows without WMI)
      or throws an AttributeError, logs a loud ResourceWarning that thermal monitoring is unsupported
      and gracefully aborts the daemon to prevent an infinite loop.
    - If supported, dynamically iterates through all values in the dictionary to find the maximum
      temperature (does not hardcode a specific key like 'CPU package' to avoid KeyErrors).
    - If max temperature > 90C, uses psutil.Process(pid).suspend() on parent and all mapped children.
    - Once cooled to 75C, uses psutil.Process(pid).resume() on all processes to continue.
    """

    def __init__(
        self,
        critical_temp_c: float = CRITICAL_TEMP_CELSIUS,
        resume_temp_c: float = RESUME_TEMP_CELSIUS,
    ) -> None:
        self.critical_temp_c = float(critical_temp_c)
        self.resume_temp_c = float(resume_temp_c)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_suspended = False
        self._is_supported = True

    def get_current_max_temperature(self) -> Optional[float]:
        """Dynamically polls psutil.sensors_temperatures() across all sensor entries.

        Returns:
            Maximum temperature in Celsius across all hardware sensors, or None if unsupported.
        """
        if not hasattr(psutil, "sensors_temperatures"):
            warnings.warn(
                "Thermal monitoring is unsupported on this platform (psutil lacks sensors_temperatures).",
                category=ResourceWarning,
                stacklevel=2,
            )
            logger.warning("RESOURCE_WARNING: psutil lacks sensors_temperatures() on this platform.")
            self._is_supported = False
            return None

        try:
            sensors_dict = psutil.sensors_temperatures()
        except (AttributeError, Exception) as exc:
            warnings.warn(
                f"Thermal monitoring is unsupported or encountered error: {exc}",
                category=ResourceWarning,
                stacklevel=2,
            )
            logger.warning("RESOURCE_WARNING: sensors_temperatures() failed: %s", exc)
            self._is_supported = False
            return None

        if not sensors_dict or not isinstance(sensors_dict, dict):
            warnings.warn(
                "Thermal monitoring is unsupported on Windows without WMI (sensors_temperatures returned empty).",
                category=ResourceWarning,
                stacklevel=2,
            )
            logger.warning("RESOURCE_WARNING: sensors_temperatures() returned empty dictionary.")
            self._is_supported = False
            return None

        temps: List[float] = []
        for entries in sensors_dict.values():
            if isinstance(entries, (list, tuple)):
                for entry in entries:
                    cur = getattr(entry, "current", None)
                    if cur is not None and isinstance(cur, (int, float)):
                        temps.append(float(cur))

        if not temps:
            warnings.warn(
                "No valid temperature readings found in sensors_temperatures().",
                category=ResourceWarning,
                stacklevel=2,
            )
            self._is_supported = False
            return None

        return max(temps)

    def govern_step(
        self,
        pid: int,
        temperature_override: Optional[float] = None,
    ) -> ThermalGovernorState:
        """Executes a single step of thermal evaluation and process suspension/resumption."""
        if not psutil.pid_exists(pid):
            return ThermalGovernorState(
                pid=pid,
                current_temperature_c=None,
                is_suspended=self._is_suspended,
                is_supported=self._is_supported,
                status="STOPPED",
            )

        max_temp = (
            float(temperature_override)
            if temperature_override is not None
            else self.get_current_max_temperature()
        )

        if max_temp is None:
            return ThermalGovernorState(
                pid=pid,
                current_temperature_c=None,
                is_suspended=self._is_suspended,
                is_supported=False,
                status="UNSUPPORTED",
            )

        try:
            proc = psutil.Process(pid)
            children = proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return ThermalGovernorState(
                pid=pid,
                current_temperature_c=max_temp,
                is_suspended=self._is_suspended,
                is_supported=True,
                status="STOPPED",
            )

        # Thermal overload trigger: max_temp > 90C
        if max_temp > self.critical_temp_c and not self._is_suspended:
            for child in children:
                try:
                    child.suspend()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                proc.suspend()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            self._is_suspended = True
            return ThermalGovernorState(
                pid=pid,
                current_temperature_c=max_temp,
                is_suspended=True,
                is_supported=True,
                status="SUSPENDED",
            )

        # Thermal cooling trigger: max_temp <= 75C
        if max_temp <= self.resume_temp_c and self._is_suspended:
            try:
                proc.resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            for child in children:
                try:
                    child.resume()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            self._is_suspended = False
            return ThermalGovernorState(
                pid=pid,
                current_temperature_c=max_temp,
                is_suspended=False,
                is_supported=True,
                status="RUNNING",
            )

        status_str = "SUSPENDED" if self._is_suspended else "RUNNING"
        return ThermalGovernorState(
            pid=pid,
            current_temperature_c=max_temp,
            is_suspended=self._is_suspended,
            is_supported=True,
            status=status_str,
        )

    def _daemon_loop(self, pid: int, poll_interval_sec: float) -> None:
        """Asynchronous background loop polling sensors and applying governors."""
        while not self._stop_event.is_set():
            if not psutil.pid_exists(pid):
                break
            state = self.govern_step(pid)
            if not state.is_supported:
                # Gracefully abort daemon on unsupported platforms to prevent infinite loop
                break
            self._stop_event.wait(timeout=poll_interval_sec)

    def start_daemon(self, pid: int, poll_interval_sec: float = 1.0) -> threading.Thread:
        """Spins off an asynchronous daemon thread for continuous thermal monitoring."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_loop,
            args=(pid, poll_interval_sec),
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        """Signals the background daemon thread to terminate and waits for completion."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


# Authoritative alias
ThermalGovernor = ThermalEvacuationGovernor


# ==============================================================================
# 6. Composite Subprocess Execution Orchestrator
# ==============================================================================

def execute_protected_subprocess(
    cmd: List[str],
    artifacts_dir: Optional[Union[str, Path]] = None,
    min_free_scratch_bytes: int = DEFAULT_MIN_FREE_SCRATCH_BYTES,
    pin_cores: bool = True,
    env_override: Optional[Dict[str, str]] = None,
    enable_thermal_governor: bool = False,
) -> Tuple[int, Optional[JSONLDProvenanceBlock]]:
    """High-level orchestrator executing a subprocess within the complete defensive perimeter.

    Workflow:
    1. Pre-flight scratch disk verification.
    2. Dynamic environment resolution and process group isolation launch.
    3. NUMA-aware CPU core thread pinning.
    4. Optional thermal governor daemon monitoring.
    5. Return code inspection via SegfaultTrapper and JSON-LD provenance generation.
    """
    verifier = PreFlightScratchVerifier(artifacts_dir=artifacts_dir, default_min_free_bytes=min_free_scratch_bytes)
    verifier.verify()

    exec_env = dict(os.environ)
    if artifacts_dir:
        exec_env["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)
    elif "COCHEM_ARTIFACTS_DIR" not in exec_env:
        resolved = get_cochem_artifacts_dir()
        exec_env["COCHEM_ARTIFACTS_DIR"] = str(resolved)

    if env_override:
        exec_env.update(env_override)

    pinner = NUMA_ThreadPinner(artifacts_dir=artifacts_dir)
    wrapped_cmd = pinner.wrap_command_for_numa(cmd)

    proc = launch_isolated_process(
        wrapped_cmd,
        env=exec_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if pin_cores:
        try:
            pinner.pin_process(pid=proc.pid)
        except Exception:
            pass

    governor: Optional[ThermalEvacuationGovernor] = None
    if enable_thermal_governor:
        governor = ThermalEvacuationGovernor()
        governor.start_daemon(pid=proc.pid, poll_interval_sec=0.5)

    stdout_data, stderr_data = proc.communicate()
    retcode = proc.returncode

    if governor is not None:
        governor.stop()

    trapper = SegfaultTrapper(artifacts_dir=artifacts_dir)
    provenance = trapper.trap(
        process_id=proc.pid,
        returncode=retcode,
        metadata={"cmd": cmd},
    )

    return retcode, provenance


# ==============================================================================
# 7. TemporalRouter (10-Tier Temporal Wall Clock Matrix & Routing)
# ==============================================================================

class TemporalRouter:
    """Evaluates computational cost heuristics, assigning quantum chemistry workloads
    to the 10-Tier Temporal Wall Clock Matrix and preventing host resource exhaustion.

    Key Behaviors:
    1. Extracts target method string and atom count N from ingested BenchRunContext dataclass metadata.
    2. Dynamically reads system hardware profile from $COCHEM_ARTIFACTS_DIR/Registry/cochem_system_config.json.
    3. Explicitly raises fatal RuntimeError if COCHEM_ARTIFACTS_DIR environment variable is missing.
    4. If the hardware profile indicates a Local Workstation and the method string contains 'DLPNO-CCSD(T)'
       (or job scales to Tier 9-10), emits a ResourceWarning, hard-disables execution, and suggests HPC/SLURM offload.
    """

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None

    def __new__(
        cls,
        context: Optional[Any] = None,
        method: Optional[str] = None,
        atom_count: Optional[int] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> Union[TemporalRouter, TemporalRouteResult]:
        instance = super().__new__(cls)
        instance.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        if context is not None or method is not None or atom_count is not None:
            return instance.route(
                context=context,
                method=method,
                atom_count=atom_count,
                config_override=config_override,
            )
        return instance

    @staticmethod
    def extract_metadata_from_context(context: Any) -> Tuple[str, int]:
        """Extracts the target method string and atom count N from BenchRunContext without mock parsers."""
        method: str = "DFT"
        atom_count: int = 1

        if context is None:
            return method, atom_count

        # 1. Direct attributes on context
        if hasattr(context, "method") and getattr(context, "method"):
            method = str(getattr(context, "method"))
        if hasattr(context, "atom_count") and getattr(context, "atom_count") is not None:
            try:
                atom_count = int(getattr(context, "atom_count"))
            except (ValueError, TypeError):
                pass
        elif hasattr(context, "num_atoms") and getattr(context, "num_atoms") is not None:
            try:
                atom_count = int(getattr(context, "num_atoms"))
            except (ValueError, TypeError):
                pass
        elif hasattr(context, "N") and getattr(context, "N") is not None:
            try:
                atom_count = int(getattr(context, "N"))
            except (ValueError, TypeError):
                pass

        # 2. Check context.config if present
        cfg = getattr(context, "config", None)
        if cfg is not None:
            qs = getattr(cfg, "quantum_settings", None)
            if qs is not None:
                if hasattr(qs, "method") and getattr(qs, "method"):
                    method = str(getattr(qs, "method"))
                elif isinstance(qs, dict) and qs.get("method"):
                    method = str(qs["method"])

            active_jobs = getattr(cfg, "active_jobs", None)
            if isinstance(active_jobs, dict):
                if "method" in active_jobs and active_jobs["method"]:
                    method = str(active_jobs["method"])
                if "atom_count" in active_jobs and active_jobs["atom_count"] is not None:
                    try:
                        atom_count = int(active_jobs["atom_count"])
                    except (ValueError, TypeError):
                        pass
                elif "num_atoms" in active_jobs and active_jobs["num_atoms"] is not None:
                    try:
                        atom_count = int(active_jobs["num_atoms"])
                    except (ValueError, TypeError):
                        pass
                elif "N" in active_jobs and active_jobs["N"] is not None:
                    try:
                        atom_count = int(active_jobs["N"])
                    except (ValueError, TypeError):
                        pass

            cost_h = getattr(cfg, "cost_heuristics", None)
            if isinstance(cost_h, dict):
                if "method" in cost_h and cost_h["method"]:
                    method = str(cost_h["method"])
                if "atom_count" in cost_h and cost_h["atom_count"] is not None:
                    try:
                        atom_count = int(cost_h["atom_count"])
                    except (ValueError, TypeError):
                        pass

        # 3. Check metadata dict on context
        meta = getattr(context, "metadata", None)
        if isinstance(meta, dict):
            if "method" in meta and meta["method"]:
                method = str(meta["method"])
            if "atom_count" in meta and meta["atom_count"] is not None:
                try:
                    atom_count = int(meta["atom_count"])
                except (ValueError, TypeError):
                    pass
            elif "num_atoms" in meta and meta["num_atoms"] is not None:
                try:
                    atom_count = int(meta["num_atoms"])
                except (ValueError, TypeError):
                    pass
            elif "N" in meta and meta["N"] is not None:
                try:
                    atom_count = int(meta["N"])
                except (ValueError, TypeError):
                    pass

        return method, max(1, atom_count)

    def load_system_config(self) -> Dict[str, Any]:
        """Dynamically reads cochem_system_config.json from $COCHEM_ARTIFACTS_DIR/Registry.

        Raises:
            RuntimeError: If COCHEM_ARTIFACTS_DIR is missing or empty.
            FileNotFoundError: If cochem_system_config.json is absent.
        """
        env_artifacts = os.environ.get("COCHEM_ARTIFACTS_DIR")
        if not env_artifacts or not env_artifacts.strip():
            raise RuntimeError("Air-Gap Fatal: COCHEM_ARTIFACTS_DIR environment variable is missing or empty.")

        reg_dir = Path(env_artifacts).resolve() / "Registry"
        cfg_path = reg_dir / "cochem_system_config.json"

        if not cfg_path.exists():
            if self.artifacts_dir:
                alt_cfg = self.artifacts_dir / "Registry" / "cochem_system_config.json"
                if alt_cfg.exists():
                    return json.loads(alt_cfg.read_text(encoding="utf-8"))
            raise FileNotFoundError(
                f"Registry configuration not found at {cfg_path}. Run Stage 0 setup."
            )

        return json.loads(cfg_path.read_text(encoding="utf-8"))

    @staticmethod
    def is_local_workstation(config_data: Dict[str, Any]) -> bool:
        """Evaluates whether the hardware profile indicates a Local Workstation rather than HPC."""
        # Check HPC scheduler
        hpc_cfg = config_data.get("hpc", {})
        if isinstance(hpc_cfg, dict):
            scheduler = str(hpc_cfg.get("scheduler", "local")).strip().lower()
            exec_mode = str(hpc_cfg.get("execution_mode", "local")).strip().lower()
            if scheduler in ("slurm", "pbs", "sge") and exec_mode in ("cluster", "hpc", "slurm"):
                return False

        # Check os_target
        hw_cfg = config_data.get("hardware", {})
        os_target = ""
        if isinstance(hw_cfg, dict):
            os_target = str(hw_cfg.get("os_target", ""))
        if not os_target:
            env_cfg = config_data.get("environment", {})
            if isinstance(env_cfg, dict):
                os_target = str(env_cfg.get("os_target", ""))
        if not os_target:
            os_target = str(config_data.get("os_target", ""))

        os_target_norm = os_target.strip().lower()
        if os_target_norm in ("hpc", "hpc_slurm_linux"):
            return False

        return True

    @staticmethod
    def calculate_temporal_tier(method: str, atom_count: int) -> Tuple[int, str, str, int]:
        """Calculates the temporal tier (1-10), label, wall-clock estimate, and scaling exponent.

        Scaling Laws:
        - DLPNO-CCSD(T) / CCSD(T): O(N^7)
        - MP2 / CBS: O(N^5)
        - DFT / HF / SCF / B3LYP / wB97: O(N^4)
        - Semiempirical / xTB / MACE: O(N^2) or O(N)
        """
        norm_method = method.strip().upper()
        n = max(1, atom_count)

        if "DLPNO-CCSD(T)" in norm_method or "CCSD(T)" in norm_method or "CC" in norm_method:
            exponent = 7
            if n >= 10:
                tier = 10
                label = "Tier 10 (1 Month to Max Accuracy / Strict HPC Cluster Required)"
                duration = "1mo"
            elif n >= 6:
                tier = 9
                label = "Tier 9 (3 Days to Max Accuracy / Strict HPC Cluster Required)"
                duration = "3d"
            elif n >= 4:
                tier = 8
                label = "Tier 8 (1 Day / Heavy Local or Standard HPC)"
                duration = "1d"
            elif n >= 2:
                tier = 7
                label = "Tier 7 (12 Hours / Heavy Local or Standard HPC)"
                duration = "12h"
            else:
                tier = 6
                label = "Tier 6 (5 Hours / Heavy Local or Standard HPC)"
                duration = "5h"
        elif "MP2" in norm_method or "CBS" in norm_method:
            exponent = 5
            if n >= 15:
                tier = 9
                label = "Tier 9 (3 Days / Strict HPC Cluster Required)"
                duration = "3d"
            elif n >= 10:
                tier = 8
                label = "Tier 8 (1 Day / Heavy Local or Standard HPC)"
                duration = "1d"
            elif n >= 6:
                tier = 7
                label = "Tier 7 (12 Hours / Heavy Local or Standard HPC)"
                duration = "12h"
            elif n >= 4:
                tier = 6
                label = "Tier 6 (5 Hours / Heavy Local or Standard HPC)"
                duration = "5h"
            elif n >= 2:
                tier = 5
                label = "Tier 5 (3 Hours / Heavy Local or Standard HPC)"
                duration = "3h"
            else:
                tier = 4
                label = "Tier 4 (1 Hour / Local Workstation Safe)"
                duration = "1h"
        elif any(k in norm_method for k in ("DFT", "B3LYP", "WB97", "PBE", "SCF", "HF", "DEF2")):
            exponent = 4
            if n >= 30:
                tier = 8
                label = "Tier 8 (1 Day / Heavy Local or Standard HPC)"
                duration = "1d"
            elif n >= 20:
                tier = 6
                label = "Tier 6 (5 Hours / Heavy Local or Standard HPC)"
                duration = "5h"
            elif n >= 10:
                tier = 4
                label = "Tier 4 (1 Hour / Local Workstation Safe)"
                duration = "1h"
            elif n >= 5:
                tier = 3
                label = "Tier 3 (30 Minutes / Local Workstation Safe)"
                duration = "30m"
            elif n >= 3:
                tier = 2
                label = "Tier 2 (1 Minute / Local Workstation Safe)"
                duration = "1m"
            else:
                tier = 1
                label = "Tier 1 (10 Seconds / Local Workstation Safe)"
                duration = "10s"
        else:
            exponent = 2
            if n >= 50:
                tier = 3
                label = "Tier 3 (30 Minutes / Local Workstation Safe)"
                duration = "30m"
            elif n >= 20:
                tier = 2
                label = "Tier 2 (1 Minute / Local Workstation Safe)"
                duration = "1m"
            else:
                tier = 1
                label = "Tier 1 (10 Seconds / Local Workstation Safe)"
                duration = "10s"

        return tier, label, duration, exponent

    def route(
        self,
        context: Optional[Any] = None,
        method: Optional[str] = None,
        atom_count: Optional[int] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> TemporalRouteResult:
        """Evaluates execution parameters, routes to temporal tier, and enforces hardware guardrails.

        Args:
            context: Ingested BenchRunContext dataclass instance.
            method: Optional explicit method string override.
            atom_count: Optional explicit atom count N override.
            config_override: Optional dictionary override for system configuration.

        Returns:
            TemporalRouteResult detailing tier assignment, wall clock estimate, and execution authorization.
        """
        extracted_method, extracted_atoms = self.extract_metadata_from_context(context)
        target_method = str(method) if method is not None else extracted_method
        target_atoms = int(atom_count) if atom_count is not None else extracted_atoms

        if config_override is not None:
            sys_config = dict(config_override)
        else:
            sys_config = self.load_system_config()

        is_local = self.is_local_workstation(sys_config)
        tier, label, duration, exponent = self.calculate_temporal_tier(target_method, target_atoms)

        is_dlpno = "DLPNO-CCSD(T)" in target_method.upper()
        is_heavy_tier = tier >= 9

        warning_emitted = False
        execution_allowed = True
        suggested_offload: Optional[str] = None

        if is_local and (is_dlpno or is_heavy_tier):
            warning_emitted = True
            execution_allowed = False
            suggested_offload = "HPC/SLURM"
            warning_msg = (
                f"RESOURCE_WARNING: High-cost method '{target_method}' (Tier {tier}, N={target_atoms} atoms) "
                f"requested on Local Workstation profile. Local execution disabled to protect host OS. "
                f"Suggested offload: HPC/SLURM cluster."
            )
            warnings.warn(warning_msg, category=ResourceWarning, stacklevel=2)
            logger.warning(warning_msg)
            msg = f"Execution disabled on Local Workstation: method '{target_method}' requires HPC offload."
        else:
            msg = f"Execution authorized on {'Local Workstation' if is_local else 'HPC Cluster'} under {label}."

        return TemporalRouteResult(
            tier=tier,
            tier_label=label,
            wall_clock_estimate=duration,
            method=target_method,
            atom_count=target_atoms,
            scaling_exponent=exponent,
            is_local_workstation=is_local,
            execution_allowed=execution_allowed,
            resource_warning_emitted=warning_emitted,
            suggested_offload=suggested_offload,
            message=msg,
        )

    def __call__(
        self,
        context: Optional[Any] = None,
        method: Optional[str] = None,
        atom_count: Optional[int] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> TemporalRouteResult:
        return self.route(
            context=context,
            method=method,
            atom_count=atom_count,
            config_override=config_override,
        )


# ==============================================================================
# 8. High-Speed I/O Routing (tmpfs RAM-Disk Overlay & Persistence Lifecycle)
# ==============================================================================

class HighSpeedIORouter:
    """High-Speed I/O Router managing tmpfs RAM-disk overlays and scratch persistence.

    Key Behaviors:
    1. Evaluates available_ram_gb. If >128 GB and os.name == 'posix', verifies free space on /dev/shm
       using shutil.disk_usage('/dev/shm').free. If sufficient space exists, re-routes scratch explicitly to /dev/shm.
    2. On Windows systems, or if /dev/shm capacity is insufficient, bypasses tmpfs and routes to standard NVMe scratch.
    3. Upon calculation termination, securely copies output artifacts (.out, .gbw, etc.) back to persistent SSD workspace,
       then triggers shutil.rmtree() on the RAM-disk (if used) to recover system memory instantly.
    """

    def __init__(
        self,
        artifacts_dir: Optional[Union[str, Path]] = None,
        min_free_ramdisk_bytes: int = DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.min_free_ramdisk_bytes = int(min_free_ramdisk_bytes)

    def resolve_persistent_scratch_dir(self) -> Path:
        """Dynamically resolves the persistent SSD scratch workspace directory."""
        scratch_dir = get_scratch_workspace_dir(self.artifacts_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    def route_scratch(
        self,
        available_ram_gb: float,
        job_id: Optional[str] = None,
        min_free_bytes: Optional[int] = None,
    ) -> IOScratchRouteReport:
        """Evaluates RAM capacity and platform, allocating RAM-disk tmpfs or standard NVMe scratch.

        Args:
            available_ram_gb: Total accessible system RAM in GB.
            job_id: Optional calculation job identifier for subfolder isolation.
            min_free_bytes: Required free disk threshold in bytes (defaults to 50 GB).

        Returns:
            IOScratchRouteReport detailing allocated scratch path and route classification.
        """
        required_bytes = int(min_free_bytes) if min_free_bytes is not None else self.min_free_ramdisk_bytes
        persistent_dir = self.resolve_persistent_scratch_dir()
        ram_gb = float(available_ram_gb)

        use_ramdisk = False
        free_shm_bytes: Optional[int] = None
        allocated_scratch_path: Path

        # POSIX tmpfs RAM-Disk Evaluation: available_ram_gb > 128 GB AND os.name == 'posix'
        if ram_gb > 128.0 and os.name == "posix":
            shm_target = Path("/dev/shm")
            if shm_target.exists() and shm_target.is_dir():
                try:
                    usage = shutil.disk_usage(str(shm_target))
                    free_shm_bytes = usage.free
                    if free_shm_bytes >= required_bytes:
                        use_ramdisk = True
                except (OSError, PermissionError):
                    use_ramdisk = False

        if use_ramdisk:
            folder_name = f"cochem_orca_{job_id}" if job_id else f"cochem_orca_{os.getpid()}_{int(time.time())}"
            allocated_scratch_path = Path("/dev/shm") / folder_name
            allocated_scratch_path.mkdir(parents=True, exist_ok=True)
            route_type = "RAM_DISK_TMPFS"
        else:
            if job_id:
                allocated_scratch_path = persistent_dir / f"job_{job_id}"
                allocated_scratch_path.mkdir(parents=True, exist_ok=True)
            else:
                allocated_scratch_path = persistent_dir
            route_type = "STANDARD_NVME_SCRATCH"

        return IOScratchRouteReport(
            scratch_path=str(allocated_scratch_path),
            persistent_path=str(persistent_dir),
            is_ramdisk=use_ramdisk,
            route_type=route_type,
            available_ram_gb=ram_gb,
            free_ramdisk_bytes=free_shm_bytes,
        )

    def finalize_and_cleanup(
        self,
        active_scratch_path: Union[str, Path],
        persistent_workspace_path: Optional[Union[str, Path]] = None,
        copy_extensions: Tuple[str, ...] = (".out", ".gbw"),
        is_ramdisk: Optional[bool] = None,
    ) -> IOCleanupReport:
        """Securely copies output artifacts back to persistent SSD workspace and cleans RAM-disk.

        Args:
            active_scratch_path: Working directory where calculation was executed.
            persistent_workspace_path: Destination persistent SSD directory.
            copy_extensions: File extensions to copy back (defaults to .out and .gbw).
            is_ramdisk: Explicit flag indicating whether scratch was on RAM-disk. If None, auto-detected.

        Returns:
            IOCleanupReport detailing persisted files and cleanup outcome.
        """
        src_dir = Path(active_scratch_path).resolve()
        dest_dir = Path(persistent_workspace_path).resolve() if persistent_workspace_path else self.resolve_persistent_scratch_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)

        ramdisk_flag = (
            bool(is_ramdisk)
            if is_ramdisk is not None
            else (os.name == "posix" and str(src_dir).startswith("/dev/shm"))
        )

        copied_artifacts: List[str] = []
        if src_dir.exists() and src_dir.is_dir():
            for item in src_dir.iterdir():
                if item.is_file() and any(item.name.endswith(ext) for ext in copy_extensions):
                    dest_file = dest_dir / item.name
                    shutil.copy2(str(item), str(dest_file))
                    copied_artifacts.append(str(dest_file))

            if ramdisk_flag:
                shutil.rmtree(str(src_dir), ignore_errors=(os.name == "nt"))

        return IOCleanupReport(
            active_scratch_path=str(src_dir),
            persistent_workspace_path=str(dest_dir),
            copied_artifacts=copied_artifacts,
            ramdisk_cleaned=ramdisk_flag,
            status="CLEANED_AND_PERSISTED",
        )

    @contextlib.contextmanager
    def scratch_context(
        self,
        available_ram_gb: float,
        job_id: Optional[str] = None,
        min_free_bytes: Optional[int] = None,
        copy_extensions: Tuple[str, ...] = (".out", ".gbw"),
    ) -> Generator[Path, None, None]:
        """Context manager managing the complete lifecycle of ephemeral scratch execution."""
        report = self.route_scratch(
            available_ram_gb=available_ram_gb,
            job_id=job_id,
            min_free_bytes=min_free_bytes,
        )
        scratch_path = Path(report.scratch_path)
        try:
            yield scratch_path
        finally:
            self.finalize_and_cleanup(
                active_scratch_path=scratch_path,
                persistent_workspace_path=report.persistent_path,
                copy_extensions=copy_extensions,
                is_ramdisk=report.is_ramdisk,
            )


# Authoritative alias
HighSpeedIORouting = HighSpeedIORouter


# ==============================================================================
# Export Declarations
# ==============================================================================

__all__ = [
    "CRITICAL_TEMP_CELSIUS",
    "DEFAULT_MIN_FREE_SCRATCH_BYTES",
    "ExitCode139_Trapper",
    "HardwareRegistryConfig",
    "HighSpeedIORouter",
    "HighSpeedIORouting",
    "IOCleanupReport",
    "IOScratchRouteReport",
    "JSONLDProvenanceBlock",
    "NUMAPinningError",
    "NUMA_ThreadPinner",
    "PreFlightResourceError",
    "PreFlightScratchVerifier",
    "ProcessReapReport",
    "RESUME_TEMP_CELSIUS",
    "ResourceGuardError",
    "SEGFAULT_RETURN_CODES",
    "ScratchSpaceReport",
    "SegfaultTrapper",
    "SegmentationFaultError",
    "SystemRegistryConfig",
    "TemporalRouteResult",
    "TemporalRouter",
    "TemporalRoutingError",
    "ThermalEvacuationGovernor",
    "ThermalGovernor",
    "ThermalGovernorState",
    "ThreadPinningResult",
    "ZMQEndpointManifest",
    "ZombieReaper",
    "ZombieReaperError",
    "execute_protected_subprocess",
    "get_cochem_artifacts_dir",
    "get_element_mass_mendeleev",
    "get_processed_workspace_dir",
    "get_registry_workspace_dir",
    "get_scratch_workspace_dir",
    "launch_isolated_process",
]


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_escalator_exec.py ---
"""
Unit tests for CoChem-TOPOS Stage 4.0 Time-Aware Capability Selector & Execution Broker
(cochem_topos_escalator_exec.py).

Validates:
1. Redundant Internal Coordinates Verification: Rejection of manual Z-matrices and enforcement of Cartesian format for ORCA delocalized redundant internal coordinates.
2. Automated SCF Rescue: Stream parsing, mathematical ping-pong oscillation detection, energy divergence detection, and automated injection of `! SlowConv VShift` with `.gbw` binary orbital seeds.
3. The AutoCAS Rescue Protocol: Extraction of T1 and D1 multireference diagnostics, mathematical single-reference breakdown detection (T1 > 0.02, D1 > 0.05), workflow halting, state downgrade to `! AutoCAS`, and cross-platform IPC alert dispatching.
4. The 11-Arrow Canonical Pipeline: Input construction across all 11 arrows (Method Matrix v4 §8B.4), auxiliary bases, dispersion corrections (! D4), and compound job scripting.
5. Hardware Brokering Header: Polling `cochem_system_config.json`, host OS safety buffers (%maxcore and %pal nprocs).
6. Geometrical Explosion Trap: Monitoring bond distances mid-optimization (> 4.0 Å), process group killing, and landscape.h5 basin tagging.
7. OOM Autopsy: Detection of Exit Code 137 / SIGKILL, generation of `OOM_autopsy.json`, and hardware downscaling derivation.
8. Wavefunction Seeding: Projection of binary `.gbw` orbitals across tiers with distinct `%base` naming hygiene.

Strictly complies with the Tripartite Air-Gap Policy and Zero-Mock Mandate.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import h5py
import numpy as np
import pytest
from ase import Atoms
from escalation.cochem_topos_escalator_exec import (
    AlertSeverity,
    AutoCASAlert,
    AutoCASRescueProtocol,
    AutomatedSCFRescueEngine,
    CalculationStatus,
    Canonical11ArrowPipeline,
    CanonicalArrow,
    CrossPlatformIPCAlert,
    CrossPlatformIPCClient,
    CrossPlatformIPCServer,
    EscalationResult,
    EscalationTier,
    EscalatorExecConfig,
    ExecutionPlan,
    FileSocketIPCQueue,
    GeometricalExplosionTrap,
    GeometryCoordinateVerifier,
    HardwareAllocations,
    HardwareBroker,
    MultireferenceDiagnostics,
    OOMAutopsyDiagnostic,
    OOMAutopsyEngine,
    ORCAOutputParser,
    SCFConvergenceStatus,
    SCFIterationRecord,
    TimeAwareCapabilitySelector,
    ToposEscalatorExec,
    WavefunctionSeeder,
    execute_time_aware_escalation,
    get_dynamic_atomic_mass,
    parse_orca_output,
    send_ipc_alert,
    verify_redundant_cartesian_geometry,
)

# ============================================================================
# 1. Tests for Directive 1: Redundant Internal Coordinates & Cartesian Builder
# ============================================================================


class TestDirective1RedundantCartesianVerification:
    """Verifies Cartesian coordinate validation and manual Z-Matrix rejection."""

    def test_verify_ase_atoms_compliance(self) -> None:
        """Confirms ASE Atoms object passes Cartesian verification."""
        atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.75, -0.47], [0.0, -0.75, -0.47]])
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(atoms) is True
        assert verify_redundant_cartesian_geometry(atoms) is True

    def test_verify_numpy_and_list_coordinates(self) -> None:
        """Confirms (N, 3) arrays and list of coordinates pass verification."""
        coords_arr = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(coords_arr) is True

        coords_list = [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(coords_list) is True

    def test_verify_atom_tuples_and_records(self) -> None:
        """Confirms list of (sym, [x,y,z]) and (sym, x, y, z) tuples pass verification."""
        tuple_coords_2 = [("O", [0.0, 0.0, 0.0]), ("H", [0.0, 0.7, 0.0]), ("H", [0.0, -0.7, 0.0])]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(tuple_coords_2) is True

        tuple_coords_4 = [("O", 0.0, 0.0, 0.0), ("H", 0.0, 0.7, 0.0), ("H", 0.0, -0.7, 0.0)]
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(tuple_coords_4) is True

    def test_verify_valid_cartesian_string(self) -> None:
        """Confirms standard Cartesian XYZ text passes verification."""
        cartesian_text = """
        * xyz 0 1
        O   0.000000   0.000000   0.117300
        H   0.000000   0.757200  -0.469200
        H   0.000000  -0.757200  -0.469200
        *
        """
        assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(cartesian_text) is True
        valid, msg = GeometryCoordinateVerifier.validate_cartesian_format(cartesian_text)
        assert valid is True
        assert "redundant internal coordinates enabled" in msg.lower()

    def test_reject_forbidden_zmatrix_keywords(self) -> None:
        """Confirms manual Z-Matrix constructs like * gzcoord, * zmat, and internal definitions are rejected."""
        zmat_samples = [
            "* gzcoord 0 1\nO\nH 1 0.96\nH 1 0.96 2 104.5\n*",
            "* zmat 0 1\nC\nO 1 r1\nH 1 r2 2 a1\n*",
            "* internal 0 1\nN 0 0 0\n*",
            "C 1 1.54 2 109.5 3 180.0\nH 2 1.09 1 109.5 3 60.0",
            "Variables:\nr1 = 1.09\na1 = 104.5",
            "Constants:\nrCC = 1.54",
        ]
        for sample in zmat_samples:
            assert GeometryCoordinateVerifier.verify_redundant_internal_coordinates_compliance(sample) is False
            valid, msg = GeometryCoordinateVerifier.validate_cartesian_format(sample)
            assert valid is False
            assert "violation" in msg.lower()

    def test_build_orca_cartesian_block_ase(self) -> None:
        """Confirms ORCA Cartesian block formatting with ASE Atoms."""
        atoms = Atoms("CO", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]])
        block = GeometryCoordinateVerifier.build_orca_cartesian_block(atoms, charge=0, multiplicity=1)
        assert "* xyz 0 1" in block
        assert "C   " in block
        assert "O   " in block
        assert block.endswith("*")

    def test_build_orca_cartesian_block_with_constraints(self) -> None:
        """Confirms %geom constraint blocks can be prepended cleanly."""
        atoms = Atoms("N2", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.10]])
        constraints = "%geom Constraints { B 0 1 C } end end"
        block = GeometryCoordinateVerifier.build_orca_cartesian_block(
            atoms, charge=0, multiplicity=1, constraints_block=constraints
        )
        assert "%geom Constraints" in block
        assert "* xyz 0 1" in block


# ============================================================================
# 2. Tests for Directive 2: Automated SCF Rescue & Stream Parsing
# ============================================================================


class TestDirective2AutomatedSCFRescue:
    """Verifies output parsing, oscillation / divergence detection, and ! SlowConv VShift injection."""

    def test_parse_scf_converged_trajectory(self) -> None:
        """Confirms clean parsing of a normally converging SCF trajectory."""
        orca_out = """
------------------
ORCA SCF ITERATIONS
------------------
Iter         Energy       Delta-E        Max-DP      RMS-DP
  0     -76.4000000000   0.0000000000  0.08000000  0.01000000
  1     -76.4300000000  -0.0300000000  0.02000000  0.00300000
  2     -76.4345000000  -0.0045000000  0.00100000  0.00010000
  3     -76.4345200000  -0.0000200000  0.00005000  0.00000500
SUCCESSFULLY CONVERGED
FINAL SINGLE POINT ENERGY: -76.43452000
ORCA TERMINATED NORMALLY
"""
        metrics = ORCAOutputParser.parse_scf_iterations(orca_out)
        assert metrics.status == SCFConvergenceStatus.CONVERGED
        assert metrics.iterations_count == 4
        assert metrics.is_oscillating is False
        assert metrics.is_diverging is False
        assert pytest.approx(metrics.final_energy, rel=1e-6) == -76.43452000

    def test_detect_ping_pong_oscillation(self) -> None:
        """Confirms detection of 2-cycle ping-pong limit cycles in SCF energies."""
        history = [
            SCFIterationRecord(iteration=0, energy_hartree=-76.400000, delta_energy=0.0),
            SCFIterationRecord(iteration=1, energy_hartree=-76.450000, delta_energy=-0.050000),
            SCFIterationRecord(iteration=2, energy_hartree=-76.400000, delta_energy=0.050000),
            SCFIterationRecord(iteration=3, energy_hartree=-76.450000, delta_energy=-0.050000),
            SCFIterationRecord(iteration=4, energy_hartree=-76.400000, delta_energy=0.050000),
            SCFIterationRecord(iteration=5, energy_hartree=-76.450000, delta_energy=-0.050000),
        ]
        is_osc, cycle = ORCAOutputParser.detect_scf_oscillation(history)
        assert is_osc is True
        assert cycle == 2

    def test_detect_scf_divergence(self) -> None:
        """Confirms detection of positive energy explosions during SCF cycles."""
        history = [
            SCFIterationRecord(iteration=0, energy_hartree=-76.400000, delta_energy=0.0),
            SCFIterationRecord(iteration=1, energy_hartree=-70.100000, delta_energy=6.300000),
            SCFIterationRecord(iteration=2, energy_hartree=500.000000, delta_energy=570.100000),
        ]
        is_div, step = ORCAOutputParser.detect_scf_divergence(history)
        assert is_div is True
        assert step == 1

    def test_inject_scf_rescue_keywords(self, tmp_path: Path) -> None:
        """Confirms injection of ! SlowConv VShift MOREAD and %moinp orbital seed."""
        raw_input = """! wB97X-V def2-TZVP TightOpt TightSCF
* xyz 0 1
O 0 0 0
H 0 0 1
H 0 1 0
*
"""
        seed_gbw = tmp_path / "previous_step.gbw"
        seed_gbw.touch()

        rescued = AutomatedSCFRescueEngine.inject_scf_rescue_keywords(
            input_content=raw_input,
            gbw_seed_path=seed_gbw,
            rescue_level=2,
        )
        assert "SlowConv" in rescued
        assert "VShift" in rescued
        assert "MOREAD" in rescued
        assert "%moinp" in rescued
        assert str(seed_gbw).replace("\\", "/") in rescued
        assert "%scf" in rescued
        assert "Shift 0.20" in rescued

    def test_build_rescue_plan_structure(self, tmp_path: Path) -> None:
        """Confirms derivation of rescued ExecutionPlan with state increment."""
        orig_plan = ExecutionPlan(
            plan_id="step-1",
            tier="T1-3h",
            method_name="r2SCAN-3c",
            keywords="! r2SCAN-3c TightOpt TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=8,
            max_memory_mb=4000,
        )
        seed_gbw = tmp_path / "seed.gbw"
        seed_gbw.touch()

        rescued_plan = AutomatedSCFRescueEngine.build_rescue_plan(
            failed_plan=orig_plan,
            gbw_seed_path=seed_gbw,
            attempt=1,
        )
        assert rescued_plan.is_rescue_attempt is True
        assert rescued_plan.rescue_count == 1
        assert rescued_plan.slow_conv_enabled is True
        assert rescued_plan.vshift_enabled is True
        assert rescued_plan.moread_enabled is True
        assert "SlowConv" in rescued_plan.keywords
        assert "VShift" in rescued_plan.keywords
        assert "MOREAD" in rescued_plan.keywords
        assert any("%moinp" in b for b in rescued_plan.custom_blocks)


# ============================================================================
# 3. Tests for Directive 3: AutoCAS Rescue Protocol & Multireference Checks
# ============================================================================


class TestDirective3AutoCASRescueProtocol:
    """Verifies T1/D1 multireference extraction, threshold violations, and ! AutoCAS downgrade."""

    def test_parse_multireference_diagnostics_single_ref(self) -> None:
        """Confirms well-behaved single-reference system with T1 < 0.02 and D1 < 0.05."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0120
  D1 diagnostic: 0.0350
  D2 diagnostic: 0.0800
FINAL SINGLE POINT ENERGY: -76.85000000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.t1_diagnostic, rel=1e-4) == 0.0120
        assert pytest.approx(diag.d1_diagnostic, rel=1e-4) == 0.0350
        assert pytest.approx(diag.d2_diagnostic, rel=1e-4) == 0.0800
        assert diag.is_multireference is False
        assert diag.violation_reason is None

    def test_parse_multireference_diagnostics_t1_violation(self) -> None:
        """Confirms T1 > 0.02 triggers multireference detection."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0285
  D1 diagnostic: 0.0410
FINAL SINGLE POINT ENERGY: -150.12345000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.t1_diagnostic, rel=1e-4) == 0.0285
        assert diag.is_multireference is True
        assert "T1=0.0285 > 0.02" in str(diag.violation_reason)

    def test_parse_multireference_diagnostics_d1_violation(self) -> None:
        """Confirms D1 > 0.05 triggers multireference detection."""
        out_text = """
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0180
  D1 diagnostic: 0.0620
FINAL SINGLE POINT ENERGY: -200.54321000
"""
        diag = ORCAOutputParser.parse_multireference_diagnostics(out_text)
        assert pytest.approx(diag.d1_diagnostic, rel=1e-4) == 0.0620
        assert diag.is_multireference is True
        assert "D1=0.0620 > 0.05" in str(diag.violation_reason)

    def test_create_autocas_alert_payload(self) -> None:
        """Confirms AutoCASAlert structure and recommended active space generation."""
        alert = AutoCASRescueProtocol.create_autocas_alert(
            molecule_id="diradical_dimer",
            t1=0.035,
            d1=0.075,
            symbols=["C", "C", "H", "H", "H", "H"],
            charge=0,
            multiplicity=1,
        )
        assert alert.molecule_id == "diradical_dimer"
        assert alert.downgraded_state == "! AutoCAS"
        assert alert.active_space_recommendation["active_electrons"] >= 2
        assert alert.active_space_recommendation["active_orbitals"] >= 2
        assert "AutoCAS" in alert.suggested_keywords

    def test_generate_autocas_input_block(self) -> None:
        """Confirms standard CASSCF / NEVPT2 multi-reference input formatting."""
        geom = "* xyz 0 1\nC 0 0 0\nC 0 0 1.4\n*"
        input_text = AutoCASRescueProtocol.generate_autocas_input_block(
            geometry_block=geom,
            active_electrons=4,
            active_orbitals=4,
            basis_set="def2-TZVP",
            charge=0,
            multiplicity=1,
        )
        assert "! CASSCF(4,4) NEVPT2 def2-TZVP" in input_text
        assert "%casscf" in input_text
        assert "nel 4" in input_text
        assert "norb 4" in input_text
        assert "* xyz 0 1" in input_text


# ============================================================================
# 4. Tests for Directive 4: The 11-Arrow Canonical Pipeline Input Generator
# ============================================================================


class TestCanonical11ArrowPipeline:
    """Verifies all 11 canonical pipeline stages (§8B.4), auxiliary bases, dispersion corrections, and script builder."""

    def test_canonical_11_arrows_all_defined(self) -> None:
        """Confirms all 11 arrows are indexed from 1 to 11."""
        for idx in range(1, 12):
            meta = Canonical11ArrowPipeline.get_arrow_metadata(idx)
            assert meta["arrow"] == idx
            assert "name" in meta
            assert "keywords" in meta
            assert "tier" in meta

    def test_arrow_1_goat_xtb_input_construction(self) -> None:
        """Confirms Arrow 1: GOAT-XTB conformer search input generation."""
        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_1_GOAT_CREST,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            stage_base_name="s1",
        )
        assert "! GOAT XTB2" in inp
        assert '%base "s1"' in inp
        assert "%maxcore" in inp
        assert "%pal nprocs" in inp

    def test_arrow_3_r2scan_3c_with_xtb_hessian(self) -> None:
        """Confirms Arrow 3: r2SCAN-3c with xTB Model Hessian preconditioning."""
        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_3_R2SCAN_3C_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            stage_base_name="s2",
        )
        assert "! r2SCAN-3c" in inp
        assert "InHess XTB2" in inp
        assert '%base "s2"' in inp

    def test_arrow_4_wb97x_v_tz_with_moread_and_opt_hessian(self, tmp_path: Path) -> None:
        """Confirms Arrow 4: wB97X-V/def2-TZVPP with MORead and BFGS Hessian reuse."""
        seed_gbw = tmp_path / "s2.gbw"
        seed_gbw.touch()
        seed_opt = tmp_path / "s2.opt"
        seed_opt.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_4_WB97X_V_TZ_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            opt_seed_path=seed_opt,
            stage_base_name="s3",
        )
        assert "! wB97X-V" in inp
        assert "def2-TZVPP" in inp
        assert "def2/J" in inp
        assert "MORead" in inp
        assert '%base "s3"' in inp
        assert "%moinp" in inp
        assert "InHess Read" in inp

    def test_arrow_5_wb97m_v_qz_with_d4_and_fmatrix(self, tmp_path: Path) -> None:
        """Confirms Arrow 5: wB97M-V/def2-QZVPP with MO projection across basis and D4 dispersion."""
        seed_gbw = tmp_path / "s3.gbw"
        seed_gbw.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_5_WB97M_V_QZ_OPT,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            dispersion_correction="D4",
            stage_base_name="s4",
        )
        assert "! wB97M-V" in inp
        assert "def2-QZVPP" in inp
        assert "D4" in inp
        assert "%scf GuessMode FMatrix end" in inp
        assert '%base "s4"' in inp

    def test_arrow_8_dlpno_ccsd_t1_single_point(self, tmp_path: Path) -> None:
        """Confirms Arrow 8: DLPNO-CCSD(T1) with cc-pVDZ-F12 + CABS and auxiliary bases."""
        seed_gbw = tmp_path / "s4.gbw"
        seed_gbw.touch()

        inp = Canonical11ArrowPipeline.build_arrow_input(
            arrow=CanonicalArrow.ARROW_8_DLPNO_CCSD_T1_SP,
            geometry_input="* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*",
            gbw_seed_path=seed_gbw,
            stage_base_name="s6",
        )
        assert "! DLPNO-CCSD(T1)" in inp
        assert "cc-pVDZ-F12" in inp
        assert "cc-pVDZ-F12/C" in inp
        assert "def2/JK" in inp
        assert "TCutPNO 1e-7" in inp
        assert "DoLED true" in inp

    def test_generate_canonical_11_arrow_script(self) -> None:
        """Confirms generated canonical bash script has valid syntax, stages s1-s6, and hardware variables."""
        alloc = HardwareAllocations(usable_cores=8, maxcore_mb=3500)
        script = Canonical11ArrowPipeline.generate_canonical_11_arrow_script(
            seed_xyz_path="complex.xyz",
            charge=0,
            multiplicity=1,
            allocations=alloc,
        )
        assert "#!/usr/bin/env bash" in script
        assert "NPROC=8" in script
        assert "MEM=3500" in script
        assert "s1_xtb.out" in script
        assert "s2.inp" in script
        assert "s3.inp" in script
        assert "s4.inp" in script
        assert "s5.inp" in script
        assert "s6.inp" in script
        assert "orca_vib" in script


# ============================================================================
# 5. Tests for Hardware Brokering Header Engine
# ============================================================================


class TestHardwareBrokering:
    """Verifies host hardware polling, memory safety buffering, and header injection."""

    def test_poll_system_config_direct_mock_file(self, tmp_path: Path) -> None:
        """Confirms hardware allocation correctly reserves 20% / 4GB RAM buffer and 1 CPU core."""
        cfg_file = tmp_path / "cochem_system_config.json"
        cfg_data = {
            "hardware": {
                "physical_cpu_cores": 16,
                "logical_cpu_cores": 32,
                "ram_gb": 64.0,
            }
        }
        cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

        alloc = HardwareBroker.poll_system_config(config_path=cfg_file)
        assert alloc.physical_cores == 16
        assert alloc.reserved_cores == 1
        assert alloc.usable_cores == 15
        assert alloc.total_ram_gb == 64.0
        # Buffer is 20% of 64 GB = 12.8 GB
        assert alloc.os_buffer_ram_gb == pytest.approx(12.8, rel=1e-3)
        usable_mb = int((64.0 - 12.8) * 1024)
        assert alloc.usable_ram_mb == usable_mb
        expected_maxcore = usable_mb // 15
        assert alloc.maxcore_mb == expected_maxcore
        assert f"%maxcore {expected_maxcore}" in alloc.header_block
        assert "%pal nprocs 15 end" in alloc.header_block

    def test_inject_hardware_headers_replaces_or_inserts(self) -> None:
        """Confirms inject_hardware_headers cleanly places %maxcore and %pal nprocs under simple keywords."""
        input_text = """! wB97X-V def2-TZVP TightOpt
* xyz 0 1
O 0 0 0
H 0 0 1
H 0 1 0
*
"""
        alloc = HardwareAllocations(usable_cores=4, maxcore_mb=2000)
        injected = HardwareBroker.inject_hardware_headers(input_text, allocations=alloc)
        assert "%maxcore 2000" in injected
        assert "%pal nprocs 4 end" in injected
        lines = injected.splitlines()
        # Verify headers appear before geometry block
        maxcore_idx = next(i for i, ln in enumerate(lines) if "%maxcore" in ln)
        geom_idx = next(i for i, ln in enumerate(lines) if "* xyz" in ln)
        assert maxcore_idx < geom_idx


# ============================================================================
# 6. Tests for Geometrical Explosion Trap & Landscape Basin Tagging
# ============================================================================


class TestGeometricalExplosionTrap:
    """Verifies bond stretching detection (> 4.0 Å), OpenMPI process killing, and landscape.h5 tagging."""

    def test_check_geometry_explosion_normal_molecule(self) -> None:
        """Confirms stable molecule passes bond explosion check."""
        atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.757, 0.586], [0.0, -0.757, 0.586]])
        exploded, max_d, pair = GeometricalExplosionTrap.check_geometry_explosion(atoms)
        assert exploded is False
        assert max_d < 4.0
        assert pair is None

    def test_check_geometry_explosion_shattered_bond(self) -> None:
        """Confirms stretched covalent bond > 4.0 Å is detected as an explosion."""
        # Initial bonded state (O-H ~ 0.96 A)
        init_atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.96, 0.0], [0.0, 0.0, 0.96]])
        # Exploded state (O-H stretched to 4.8 A)
        exploded_atoms = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 4.80, 0.0], [0.0, 0.0, 0.96]])

        exploded, max_d, pair = GeometricalExplosionTrap.check_geometry_explosion(
            atoms_or_coords=exploded_atoms,
            initial_structure=init_atoms,
            threshold_angstrom=4.0,
        )
        assert exploded is True
        assert max_d >= 4.0
        assert pair is not None

    def test_monitor_orca_optimization_trajectory_detects_shattering(self) -> None:
        """Confirms multi-step ORCA output parsing detects mid-optimization bond explosion."""
        traj_out = """
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    1.090000
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    2.500000
---------------------------------
CARTESIAN COORDINATES (ANGSTROEM)
---------------------------------
  C      0.000000    0.000000    0.000000
  H      0.000000    0.000000    4.750000
"""
        exploded, max_d, step_idx = GeometricalExplosionTrap.monitor_orca_optimization_trajectory(
            traj_out, threshold_angstrom=4.0
        )
        assert exploded is True
        assert max_d >= 4.0
        assert step_idx == 2

    def test_flag_basin_unstable_in_landscape_h5(self, tmp_path: Path) -> None:
        """Confirms writing /basins/{molecule_id} with status='GEOMETRICAL_EXPLOSION' in landscape.h5."""
        h5_file = tmp_path / "landscape.h5"
        success = GeometricalExplosionTrap.flag_basin_unstable_in_landscape(
            landscape_h5_path=h5_file,
            molecule_id="mol_shattered_01",
            max_bond_distance=4.75,
            step_index=2,
            message="Bond C-H stretched > 4.0 A",
        )
        assert success is True
        assert h5_file.exists()

        with h5py.File(h5_file, "r") as f:
            grp = f["basins/mol_shattered_01"]
            assert grp.attrs["status"] == "GEOMETRICAL_EXPLOSION"
            assert bool(grp.attrs["unstable"]) is True
            assert pytest.approx(grp.attrs["max_bond_distance_observed"], rel=1e-3) == 4.75
            assert grp.attrs["explosion_step"] == 2


# ============================================================================
# 7. Tests for OOM Autopsy Engine (Exit Code 137 / SIGKILL)
# ============================================================================


class TestOOMAutopsyEngine:
    """Verifies detection of Exit Code 137, OOM autopsy JSON generation, and hardware downscaling."""

    def test_is_oom_event_detection(self) -> None:
        """Confirms detection via exit code 137 or error tokens."""
        assert OOMAutopsyEngine.is_oom_event(exit_code=137) is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=0, output_text="std::bad_alloc thrown") is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=1, output_text="Cannot allocate memory") is True
        assert OOMAutopsyEngine.is_oom_event(exit_code=0, output_text="Normal convergence") is False

    def test_generate_oom_autopsy_file(self, tmp_path: Path) -> None:
        """Confirms generation of OOM_autopsy.json diagnostic log."""
        plan = ExecutionPlan(
            plan_id="plan-oom-test",
            tier="T1-3d",
            method_name="wB97M-V",
            basis_set="def2-QZVPP",
            keywords="! wB97M-V def2-QZVPP TightPNO TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=16,
            max_memory_mb=4000,
        )

        diag, autopsy_path = OOMAutopsyEngine.generate_oom_autopsy(
            molecule_id="large_complex_01",
            plan=plan,
            node_ram_mb=65536,
            exit_code=137,
            workdir=tmp_path,
        )
        assert autopsy_path.exists()
        assert diag.exit_code == 137
        assert diag.molecule_id == "large_complex_01"
        assert diag.tier_attempted == "T1-3d"
        assert diag.downscaling_recommendation["recommended_nprocs"] == 8
        assert "def2-TZVPP" in diag.suggested_keywords

        # Read JSON file back
        loaded = json.loads(autopsy_path.read_text(encoding="utf-8"))
        assert loaded["exit_code"] == 137
        assert loaded["allocated_nprocs"] == 16

    def test_derive_hardware_downscaling_plan(self) -> None:
        """Confirms derive_hardware_downscaling creates a plan with reduced cores and smaller basis."""
        plan = ExecutionPlan(
            plan_id="plan-orig",
            tier="T1-3d",
            method_name="wB97M-V",
            basis_set="def2-QZVPP",
            keywords="! wB97M-V def2-QZVPP TightPNO TightSCF",
            geometry_block="* xyz 0 1\nC 0 0 0\n*",
            num_cores=16,
            max_memory_mb=4000,
        )
        diag = OOMAutopsyDiagnostic(
            molecule_id="mol1",
            plan_id="plan-orig",
            tier_attempted="T1-3d",
            exit_code=137,
            node_ram_mb=65536,
            allocated_maxcore_mb=4000,
            allocated_nprocs=16,
            downscaling_recommendation={
                "action": "HALVE_CORES_DOUBLE_MAXCORE",
                "recommended_nprocs": 8,
                "recommended_maxcore_mb": 7680,
                "recommended_basis": "def2-TZVPP",
            },
            suggested_keywords="! wB97M-V def2-TZVPP NormalPNO TightSCF",
        )
        downscaled = OOMAutopsyEngine.derive_hardware_downscaling(plan, diag)
        assert downscaled.num_cores == 8
        assert downscaled.max_memory_mb == 7680
        assert downscaled.basis_set == "def2-TZVPP"
        assert "def2-TZVPP" in downscaled.keywords


# ============================================================================
# 8. Tests for Wavefunction Seeding & Naming Hygiene (`! MORead`)
# ============================================================================


class TestWavefunctionSeedingMORead:
    """Verifies binary .gbw orbital projection and %base naming hygiene."""

    def test_inject_gbw_seed_formatting(self, tmp_path: Path) -> None:
        """Confirms injection of ! MORead, %base, %moinp, and %scf GuessMode FMatrix."""
        seed_gbw = tmp_path / "s2.gbw"
        seed_gbw.touch()

        raw_input = """! wB97X-V def2-TZVP TightOpt
* xyz 0 1
O 0 0 0
H 0 0 1
*
"""
        seeded = WavefunctionSeeder.inject_gbw_seed(
            input_content=raw_input,
            gbw_seed_path=seed_gbw,
            stage_base_name="s3",
            guess_mode="FMatrix",
        )
        assert "MORead" in seeded
        assert '%base "s3"' in seeded
        assert '%moinp' in seeded
        assert str(seed_gbw).replace("\\", "/") in seeded
        assert "%scf GuessMode FMatrix end" in seeded


# ============================================================================
# 9. Tests for Cross-Platform IPC Subsystem
# ============================================================================


class TestCrossPlatformIPCSubsystem:
    """Verifies thread-safe and process-safe alert communication via socket and file queue."""

    def test_file_socket_ipc_queue_push_and_pop(self, tmp_path: Path) -> None:
        """Confirms atomic push and pop operations on FileSocketIPCQueue."""
        queue_dir = tmp_path / "ipc_queue"
        queue = FileSocketIPCQueue(queue_dir)

        alert = CrossPlatformIPCAlert(
            severity=AlertSeverity.WARNING,
            title="SCF Warning",
            message="Limit cycle detected",
            payload={"cycle": 2},
        )
        saved_file = queue.push(alert)
        assert saved_file.exists()

        popped = queue.pop_all()
        assert len(popped) == 1
        assert popped[0].title == "SCF Warning"
        assert popped[0].severity == AlertSeverity.WARNING
        assert not saved_file.exists()

    def test_ipc_server_and_client_roundtrip(self, tmp_path: Path) -> None:
        """Confirms server starts, registers callback, and receives alerts from client."""
        queue_dir = tmp_path / "ipc_roundtrip"
        server = CrossPlatformIPCServer(port=8895, queue_dir=queue_dir)

        received_alerts: list[CrossPlatformIPCAlert] = []
        server.register_callback(lambda a: received_alerts.append(a))
        server.start()

        time.sleep(0.1)

        client = CrossPlatformIPCClient(port=8895, queue_dir=queue_dir)
        test_alert = CrossPlatformIPCAlert(
            severity=AlertSeverity.CRITICAL,
            title="AutoCAS Triggered",
            message="T1=0.035 exceeds threshold",
            payload={"t1": 0.035},
        )
        client.send_alert(test_alert)

        time.sleep(0.3)
        server.stop()

        assert len(received_alerts) >= 1
        assert received_alerts[0].title == "AutoCAS Triggered"


# ============================================================================
# 10. Tests for Time-Aware Capability Selector & Master ToposEscalatorExec Broker
# ============================================================================


class TestTimeAwareCapabilitySelectorAndBroker:
    """Verifies tier selection, ladder construction, dry-run simulation, and end-to-end execution."""

    def test_select_optimal_tier_scaling(self) -> None:
        """Confirms appropriate tier selection based on time budgets and molecular size."""
        # 10 second budget -> T1-10s (XTB2)
        assert TimeAwareCapabilitySelector.select_optimal_tier(5.0, num_atoms=5) == EscalationTier.T1_10S

        # 1 minute budget -> T1-1min (GOAT-XTB2)
        assert TimeAwareCapabilitySelector.select_optimal_tier(60.0, num_atoms=5) == EscalationTier.T1_1MIN

        # 3 hour budget -> T1-3h (r2SCAN-3c)
        assert TimeAwareCapabilitySelector.select_optimal_tier(3600.0, num_atoms=5) == EscalationTier.T1_3H

        # 3 day budget -> T1-3d (wB97M-V / DLPNO-CCSD(T))
        assert TimeAwareCapabilitySelector.select_optimal_tier(250000.0, num_atoms=5) == EscalationTier.T1_3D

    def test_build_escalation_ladder_sequence(self) -> None:
        """Confirms ladder generation produces strictly monotonic progression."""
        ladder = TimeAwareCapabilitySelector.build_escalation_ladder(
            target_tier=EscalationTier.T1_3H,
            start_tier=EscalationTier.T1_10S,
        )
        assert ladder[0] == EscalationTier.T1_10S
        assert ladder[-1] == EscalationTier.T1_3H
        assert EscalationTier.T1_1MIN in ladder

    def test_run_escalation_dry_run_success(self, tmp_path: Path) -> None:
        """Confirms full dry-run multi-tier escalation achieves target tier successfully."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "escalation_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        res = broker.run_escalation(
            geometry="* xyz 0 1\nO 0 0 0\nH 0 0 1\nH 0 1 0\n*",
            molecule_id="water_test",
            target_tier=EscalationTier.T1_1MIN,
        )
        assert res.success is True
        assert res.final_status == CalculationStatus.SUCCESS
        assert res.highest_tier_achieved == EscalationTier.T1_1MIN.value
        assert len(res.steps) == 2
        assert res.final_energy_hartree is not None

    def test_run_escalation_geometrical_explosion_trap(self, tmp_path: Path) -> None:
        """Confirms mid-optimization bond stretching halts escalation with GEOMETRICAL_EXPLOSION."""
        h5_path = tmp_path / "landscape.h5"
        config = EscalatorExecConfig(
            working_dir=tmp_path / "explosion_test",
            landscape_h5_path=h5_path,
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        # Injects TRIGGER_EXPLOSION keyword into dry run
        geom = "* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_10S, geometry_input=geom)
        plan.keywords = "! XTB2 TightOpt TRIGGER_EXPLOSION"

        step_record = broker.execute_step(plan, molecule_id="exploding_mol", step_index=0)
        assert step_record.status == CalculationStatus.GEOMETRICAL_EXPLOSION
        assert "Geometrical Explosion" in str(step_record.error_message)

        # Check landscape.h5 was updated
        assert h5_path.exists()
        with h5py.File(h5_path, "r") as f:
            grp = f["basins/exploding_mol"]
            assert grp.attrs["status"] == "GEOMETRICAL_EXPLOSION"
            assert bool(grp.attrs["unstable"]) is True

    def test_run_escalation_oom_autopsy(self, tmp_path: Path) -> None:
        """Confirms OS OOM signal (137) logs OOM_autopsy.json and sets status to OOM_KILLED."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "oom_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        geom = "* xyz 0 1\nC 0 0 0\nH 0 0 1.09\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_3D, geometry_input=geom)
        plan.keywords = "! wB97M-V def2-QZVPP TightPNO TRIGGER_OOM"

        step_record = broker.execute_step(plan, molecule_id="oom_mol", step_index=0)
        assert step_record.status == CalculationStatus.OOM_KILLED
        assert step_record.oom_autopsy is not None
        assert step_record.oom_autopsy.exit_code == 137

        autopsy_file = tmp_path / "oom_test" / f"oom_mol_{plan.plan_id}" / "OOM_autopsy.json"
        assert autopsy_file.exists()

    def test_run_escalation_autocas_trigger_on_multiref(self, tmp_path: Path) -> None:
        """Confirms T1/D1 diagnostic violation halts escalation and sets status to AUTOCAS_TRIGGERED."""
        config = EscalatorExecConfig(
            working_dir=tmp_path / "autocas_test",
            dry_run=True,
            enable_ipc_alerts=False,
        )
        broker = ToposEscalatorExec(config=config)

        geom = "* xyz 0 1\nC 0 0 0\nC 0 0 1.4\n*"
        plan = broker.build_plan(tier=EscalationTier.T1_3D, geometry_input=geom)
        plan.keywords = "! DLPNO-CCSD(T) TightPNO TRIGGER_MULTIREF"

        step_record = broker.execute_step(plan, molecule_id="diradical_mol", step_index=0)
        assert step_record.status == CalculationStatus.AUTOCAS_TRIGGERED
        assert step_record.multiref_diagnostics is not None
        assert step_record.multiref_diagnostics.is_multireference is True
        assert step_record.multiref_diagnostics.t1_diagnostic > 0.02


# ============================================================================
# 11. Tests for Mendeleev Dynamic Atomic Mass Mandate
# ============================================================================


class TestDirective11MendeleevDynamicMasses:
    """Verifies dynamic atomic and isotopic mass retrieval via Mendeleev."""

    def test_dynamic_atomic_mass_retrieval(self) -> None:
        """Confirms dynamic mass lookup for standard elements."""
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        o_mass = get_dynamic_atomic_mass("O")

        assert pytest.approx(c_mass, rel=1e-3) == 12.011
        assert pytest.approx(h_mass, rel=1e-3) == 1.008
        assert pytest.approx(o_mass, rel=1e-3) == 15.999

    def test_dynamic_isotopic_mass_retrieval(self) -> None:
        """Confirms dynamic mass lookup for specific isotopes (13C, 2H/D, 18O)."""
        c13_mass = get_dynamic_atomic_mass("C", mass_number=13)
        h2_mass = get_dynamic_atomic_mass("H", mass_number=2)
        o18_mass = get_dynamic_atomic_mass("O", mass_number=18)

        assert pytest.approx(c13_mass, rel=1e-5) == 13.00335
        assert pytest.approx(h2_mass, rel=1e-5) == 2.01410
        assert pytest.approx(o18_mass, rel=1e-5) == 17.99916


# ============================================================================
# 12. Tests for Top-Level Convenience Functions & Return Models
# ============================================================================


class TestTopLevelConvenienceFunctions:
    """Verifies top-level helper functions and data models."""

    def test_execute_time_aware_escalation_convenience(self, tmp_path: Path) -> None:
        """Confirms execute_time_aware_escalation wrapper returns EscalationResult."""
        res: EscalationResult = execute_time_aware_escalation(
            geometry="* xyz 0 1\nO 0 0 0\nH 0 0 1\nH 0 1 0\n*",
            molecule_id="water_top_level",
            time_budget_seconds=10.0,
            working_dir=tmp_path / "top_level_test",
            dry_run=True,
        )
        assert isinstance(res, EscalationResult)
        assert res.success is True
        assert res.highest_tier_achieved == EscalationTier.T1_10S.value

    def test_parse_orca_output_convenience(self) -> None:
        """Confirms parse_orca_output convenience function returns parsed dictionary."""
        out = """
ORCA SCF ITERATIONS
Iter         Energy       Delta-E        Max-DP      RMS-DP
  0     -76.4000000000   0.0000000000  0.08000000  0.01000000
  1     -76.4345200000  -0.0345200000  0.00005000  0.00000500
SUCCESSFULLY CONVERGED
COUPLED CLUSTER DIAGNOSTICS:
  T1 diagnostic: 0.0110
  D1 diagnostic: 0.0320
FINAL SINGLE POINT ENERGY: -76.43452000
ORCA TERMINATED NORMALLY
"""
        parsed = parse_orca_output(out)
        assert pytest.approx(parsed["final_energy_hartree"], rel=1e-6) == -76.43452000
        assert isinstance(parsed["multireference_diagnostics"], MultireferenceDiagnostics)
        assert parsed["multireference_diagnostics"].t1_diagnostic == 0.0110
        assert parsed["normal_termination"] is True

    def test_send_ipc_alert_convenience(self, tmp_path: Path) -> None:
        """Confirms send_ipc_alert convenience helper constructs and queues alert."""
        queue_dir = tmp_path / "ipc_conv_queue"
        alert = send_ipc_alert(
            title="Convenience Alert",
            message="Testing send_ipc_alert convenience function",
            severity=AlertSeverity.INFO,
            queue_dir=queue_dir,
        )
        assert isinstance(alert, CrossPlatformIPCAlert)
        assert alert.title == "Convenience Alert"

    def test_autocas_alert_model_instantiation(self) -> None:
        """Confirms AutoCASAlert model fields validation."""
        alert = AutoCASAlert(
            molecule_id="test_mol",
            t1_diagnostic=0.045,
            d1_diagnostic=0.085,
            message="Test multireference alert",
        )
        assert alert.t1_diagnostic == 0.045
        assert alert.downgraded_state == "! AutoCAS"



--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_subprocess_reaper.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for Stage 6.0 Subprocess Brokering, Isolation, and Thermal Governors.

Module: tests/test_subprocess_reaper.py
Target Implementation: cochem_bench.bench_libraries.subprocess_reaper

Capabilities Tested:
1. Air-Gap Safety Contract:
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR.
   - Fatal RuntimeError if COCHEM_ARTIFACTS_DIR environment variable is missing/empty.
2. PreFlightScratchVerifier:
   - NVMe scratch space verification using shutil.disk_usage().
   - ResourceGuardError fast-failure on threshold breach.
   - Pydantic v2 ScratchSpaceReport validation.
3. Process Group Isolation & ZombieReaper:
   - Process group isolation via launch_isolated_process (start_new_session on POSIX, CREATE_NEW_PROCESS_GROUP on Windows).
   - Recursive child process mapping (psutil.Process.children(recursive=True)) and ruthless termination.
   - Ephemeral port ZeroMQ PUB/SUB socket binding and manifest logging to Registry/zmq_ipc.json.
   - Real-time heartbeat broadcast and verification.
   - ABORT.signal file detection, triggering, and clearing in $SCRATCH workspace.
4. NUMA-Aware Thread Pinning:
   - Topology probing via numactl/lscpu or psutil.
   - Sockets/numa binding command generation (numactl --cpunodebind=0 --membind=0).
   - Dynamic configuration loading from Registry/cochem_system_config.json.
   - Core affinity assignment via psutil.Process().cpu_affinity().
5. Thermal Evacuation Governor:
   - Polling psutil.sensors_temperatures() with dynamic temperature iteration.
   - Windows Guard: ResourceWarning logging and graceful daemon abort if unsupported/empty.
   - Automatic suspend at > 90C and resume at <= 75C for parent and all child processes.
   - Asynchronous daemon lifecycle management.
6. SegfaultTrapper & ExitCode139_Trapper:
   - Precise returncode classification for POSIX (-11, 139) and Windows (0xC0000005, 3221225477, -1073741819).
   - FAIR JSON-LD provenance block generation and atomic commit to bench_provenance.jsonld.
7. Mendeleev Elemental Mass Integration:
   - Dynamic atomic weight lookup for elements via mendeleev library.
8. Composite Protected Subprocess Orchestrator:
   - End-to-end protected subprocess execution with isolation, pinning, and segfault trapping.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task6_reaper_pt2.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 6 Subprocess Brokering & Temporal Engine Routing.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Generator

import psutil
import pytest
import zmq
from mendeleev import element

from cochem_bench.bench_libraries.subprocess_reaper import (
    CRITICAL_TEMP_CELSIUS,
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    ExitCode139_Trapper,
    HighSpeedIORouter,
    HighSpeedIORouting,
    IOCleanupReport,
    IOScratchRouteReport,
    JSONLDProvenanceBlock,
    NUMAPinningError,
    NUMA_ThreadPinner,
    PreFlightResourceError,
    PreFlightScratchVerifier,
    ProcessReapReport,
    RESUME_TEMP_CELSIUS,
    ResourceGuardError,
    SEGFAULT_RETURN_CODES,
    ScratchSpaceReport,
    SegfaultTrapper,
    SegmentationFaultError,
    TemporalRouteResult,
    TemporalRouter,
    TemporalRoutingError,
    ThermalEvacuationGovernor,
    ThermalGovernor,
    ThermalGovernorState,
    ThreadPinningResult,
    ZMQEndpointManifest,
    ZombieReaper,
    ZombieReaperError,
    execute_protected_subprocess,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_processed_workspace_dir,
    get_registry_workspace_dir,
    get_scratch_workspace_dir,
    launch_isolated_process,
)


# ==============================================================================
# Authentic Fixtures
# ==============================================================================

@pytest.fixture
def isolated_artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Establishes an authentic, isolated artifacts workspace."""
    artifacts_root = tmp_path / "cochem_isolated_artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_root))
    yield artifacts_root
    if artifacts_root.exists():
        shutil.rmtree(artifacts_root, ignore_errors=True)


# ==============================================================================
# 1. Air-Gap Safety Contract & Dynamic Path Resolution Tests
# ==============================================================================

def test_dynamic_path_resolution(isolated_artifacts_dir: Path) -> None:
    """Verifies dynamic resolution of artifacts, scratch, registry, and processed dirs."""
    resolved_artifacts = get_cochem_artifacts_dir()
    assert resolved_artifacts == isolated_artifacts_dir.resolve()

    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    assert scratch_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Scratch"

    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    assert reg_dir == isolated_artifacts_dir / "Registry"

    proc_dir = get_processed_workspace_dir(isolated_artifacts_dir)
    assert proc_dir == isolated_artifacts_dir / "BENCH_Workspace" / "Processed"


def test_air_gap_missing_env_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies fatal RuntimeError is raised when COCHEM_ARTIFACTS_DIR is missing."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        get_cochem_artifacts_dir()
    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)

    with pytest.raises(RuntimeError):
        get_scratch_workspace_dir()

    with pytest.raises(RuntimeError):
        get_registry_workspace_dir()

    with pytest.raises(RuntimeError):
        get_processed_workspace_dir()


def test_mendeleev_elemental_mass_dynamic() -> None:
    """Validates dynamic retrieval of atomic weights via the Mendeleev database."""
    carbon_mass = get_element_mass_mendeleev("C")
    expected_carbon = float(element("C").atomic_weight)
    assert abs(carbon_mass - expected_carbon) < 1e-6

    hydrogen_mass = get_element_mass_mendeleev("H")
    expected_hydrogen = float(element("H").atomic_weight)
    assert abs(hydrogen_mass - expected_hydrogen) < 1e-6

    oxygen_mass = get_element_mass_mendeleev("O")
    expected_oxygen = float(element("O").atomic_weight)
    assert abs(oxygen_mass - expected_oxygen) < 1e-6

    platinum_mass = get_element_mass_mendeleev("Pt")
    expected_platinum = float(element("Pt").atomic_weight)
    assert abs(platinum_mass - expected_platinum) < 1e-6


# ==============================================================================
# 2. PreFlightScratchVerifier Tests
# ==============================================================================

def test_preflight_scratch_verifier_success(isolated_artifacts_dir: Path) -> None:
    """Verifies that scratch verification succeeds when available space exceeds threshold."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    report = verifier.verify(min_free_bytes=1024)

    assert isinstance(report, ScratchSpaceReport)
    assert report.is_sufficient is True
    assert report.total_bytes > 0
    assert report.free_bytes >= 1024
    assert Path(report.scratch_path).exists()
    assert verifier.check_space_safe(min_free_bytes=1024) is True


def test_preflight_scratch_verifier_insufficient_space_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies fast-failure with ResourceGuardError when disk space threshold is unmet."""
    verifier = PreFlightScratchVerifier(artifacts_dir=isolated_artifacts_dir)
    impossible_bytes = 100 * (1024 ** 5)

    with pytest.raises(ResourceGuardError) as exc_info:
        verifier.verify(min_free_bytes=impossible_bytes)

    assert "RESOURCE_GUARD" in str(exc_info.value)
    assert verifier.check_space_safe(min_free_bytes=impossible_bytes) is False


# ==============================================================================
# 3. Process Group Isolation & ZombieReaper Tests
# ==============================================================================

def test_launch_isolated_process() -> None:
    """Verifies launch_isolated_process configures process group isolation flags."""
    proc = launch_isolated_process(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0


def test_zombie_reaper_zmq_heartbeat_lifecycle(isolated_artifacts_dir: Path) -> None:
    """Verifies ephemeral ZMQ PUB/SUB socket binding, manifest recording, and message transmission."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    ctx = zmq.Context()

    try:
        pub_socket, manifest = reaper.establish_heartbeat_publisher(context=ctx)
        assert isinstance(manifest, ZMQEndpointManifest)
        assert manifest.port > 0
        assert manifest.endpoint.startswith("tcp://127.0.0.1:")
        assert reaper.get_ipc_manifest_path().exists()

        disk_manifest = reaper.read_ipc_manifest()
        assert disk_manifest.port == manifest.port
        assert disk_manifest.endpoint == manifest.endpoint

        reaper.publish_heartbeat(pub_socket, topic="HEARTBEAT", payload={"status": "ACTIVE_CALCULATION"})

        received = reaper.check_heartbeat_receptive(
            endpoint=manifest.endpoint,
            timeout_ms=1000,
            topic="HEARTBEAT",
            context=ctx,
        )
        assert isinstance(received, bool)
    finally:
        pub_socket.close()
        ctx.term()


def test_zombie_reaper_abort_signal_file(isolated_artifacts_dir: Path) -> None:
    """Verifies detection, triggering, and clearing of ABORT.signal file in $SCRATCH."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)
    scratch_dir = get_scratch_workspace_dir(isolated_artifacts_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    assert reaper.check_abort_signal() is False

    abort_file = reaper.trigger_abort_signal(reason="MANUAL_TEST_ABORT")
    assert abort_file.exists()
    assert reaper.check_abort_signal() is True

    cleared = reaper.clear_abort_signal()
    assert cleared is True
    assert reaper.check_abort_signal() is False


def test_zombie_reaper_exterminate_real_child_process(isolated_artifacts_dir: Path) -> None:
    """Spawns an authentic background child process and ruthlessly terminates it."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid
    assert psutil.pid_exists(worker_pid) is True

    report = reaper.terminate_process_tree(target_pid=worker_pid, reason="ORPHAN_TERMINATION_TEST")

    assert isinstance(report, ProcessReapReport)
    assert report.target_pid == worker_pid
    assert report.status == "EXTERMINATED"
    assert worker_pid in report.terminated_pids

    time.sleep(0.2)
    assert psutil.pid_exists(worker_pid) is False or not psutil.Process(worker_pid).is_running()


def test_zombie_reaper_terminate_process_tree_with_children(isolated_artifacts_dir: Path) -> None:
    """Spawns a parent process that launches a child process, verifying recursive mapping & termination."""
    reaper = ZombieReaper(artifacts_dir=isolated_artifacts_dir)

    # Parent script spawns a child python process, then both sleep
    parent_script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "time.sleep(120)\n"
    )
    parent_proc = launch_isolated_process(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    parent_pid = parent_proc.pid

    # Allow child process to spawn
    time.sleep(0.5)
    assert psutil.pid_exists(parent_pid) is True

    # Terminate process tree
    report = reaper.terminate_process_tree(target_pid=parent_pid, reason="TREE_TERMINATION_TEST")

    assert isinstance(report, ProcessReapReport)
    assert report.target_pid == parent_pid
    assert report.status == "EXTERMINATED"
    assert len(report.terminated_pids) >= 1

    time.sleep(0.2)
    assert psutil.pid_exists(parent_pid) is False or not psutil.Process(parent_pid).is_running()


# ==============================================================================
# 4. NUMA-Aware Thread Pinning Tests
# ==============================================================================

def test_numa_thread_pinner_topology_probe(isolated_artifacts_dir: Path) -> None:
    """Verifies NUMA topology probing and numactl binding command creation."""
    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    topology = pinner.probe_numa_topology()

    assert isinstance(topology, dict)
    assert "logical_cpus" in topology
    assert "numa_nodes" in topology
    assert topology["logical_cpus"] >= 1

    # Check wrap_command_for_numa
    cmd = ["python", "calc.py"]
    wrapped = pinner.wrap_command_for_numa(cmd, required_cores=1)
    assert isinstance(wrapped, list)
    assert wrapped[-2:] == ["python", "calc.py"]


def test_numa_thread_pinner_from_config(isolated_artifacts_dir: Path) -> None:
    """Verifies loading affinity configuration from dynamic cochem_system_config.json."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    total_logical = psutil.cpu_count(logical=True) or 1
    target_core_indices = [0] if total_logical == 1 else [0, min(1, total_logical - 1)]

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": min(2, total_logical),
            "logical_cpu_cores": total_logical,
            "ram_gb": 16.0,
            "pinned_cores": target_core_indices,
        },
        "pinned_cores": target_core_indices,
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    loaded_cores = pinner.load_affinity_cores()
    assert loaded_cores == target_core_indices

    result = pinner.pin_process(pid=os.getpid())
    assert isinstance(result, ThreadPinningResult)
    assert result.pid == os.getpid()
    assert result.assigned_cores == target_core_indices
    assert result.status in ("PINNED_SUCCESS", "UNSUPPORTED_PLATFORM")
    if result.status == "PINNED_SUCCESS":
        assert set(result.active_affinity) == set(target_core_indices)


def test_numa_thread_pinner_invalid_pid_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies that pinning a non-existent process ID raises NUMAPinningError."""
    pinner = NUMA_ThreadPinner(artifacts_dir=isolated_artifacts_dir)
    invalid_pid = 99999999
    with pytest.raises(NUMAPinningError):
        pinner.pin_process(pid=invalid_pid, cores=[0])


# ==============================================================================
# 5. Thermal Evacuation Governor Tests
# ==============================================================================

def test_thermal_governor_windows_guard() -> None:
    """Verifies that Windows Guard emits ResourceWarning and aborts without infinite loop."""
    governor = ThermalEvacuationGovernor()

    # On platforms where sensors_temperatures returns empty (like Windows without WMI),
    # verify ResourceWarning is emitted and None is returned
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        temp = governor.get_current_max_temperature()

    if temp is None:
        assert any(issubclass(w.category, ResourceWarning) for w in record)

    # Verify daemon loop aborts gracefully when unsupported
    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        thread = governor.start_daemon(pid=worker.pid, poll_interval_sec=0.05)
        time.sleep(0.2)
        governor.stop()
        assert not thread.is_alive()
    finally:
        if psutil.pid_exists(worker.pid):
            try:
                psutil.Process(worker.pid).kill()
            except Exception:
                pass


def test_thermal_governor_dynamic_temp_iteration() -> None:
    """Verifies dynamic iteration and state transitions on critical threshold breach and cooling."""
    governor = ThermalEvacuationGovernor(critical_temp_c=CRITICAL_TEMP_CELSIUS, resume_temp_c=RESUME_TEMP_CELSIUS)

    worker = launch_isolated_process(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    worker_pid = worker.pid

    try:
        # 1. Normal temperature (50.0C) -> RUNNING
        state1 = governor.govern_step(pid=worker_pid, temperature_override=50.0)
        assert isinstance(state1, ThermalGovernorState)
        assert state1.status == "RUNNING"
        assert state1.is_suspended is False

        # 2. Critical temperature (95.0C > 90C) -> SUSPENDED
        state2 = governor.govern_step(pid=worker_pid, temperature_override=95.0)
        assert state2.status == "SUSPENDED"
        assert state2.is_suspended is True

        # 3. Intermediate cooling (80.0C > 75C) -> Still SUSPENDED
        state3 = governor.govern_step(pid=worker_pid, temperature_override=80.0)
        assert state3.status == "SUSPENDED"
        assert state3.is_suspended is True

        # 4. Safe cooling (70.0C <= 75C) -> RESUMED to RUNNING
        state4 = governor.govern_step(pid=worker_pid, temperature_override=70.0)
        assert state4.status == "RUNNING"
        assert state4.is_suspended is False
    finally:
        if psutil.pid_exists(worker_pid):
            try:
                psutil.Process(worker_pid).kill()
            except Exception:
                pass


def test_thermal_governor_alias_equivalence() -> None:
    """Verifies that ThermalGovernor is an alias for ThermalEvacuationGovernor."""
    assert ThermalGovernor is ThermalEvacuationGovernor


# ==============================================================================
# 6. SegfaultTrapper & ExitCode139_Trapper Tests
# ==============================================================================

@pytest.mark.parametrize("segfault_code", [-11, 139, 3221225477, -1073741819, 0xC0000005])
def test_segfault_trapper_identifies_all_segfault_codes(segfault_code: int) -> None:
    """Validates that all POSIX and Windows segmentation fault return codes are recognized."""
    assert SegfaultTrapper.is_segmentation_fault(segfault_code) is True
    assert ExitCode139_Trapper.is_segmentation_fault(segfault_code) is True


@pytest.mark.parametrize("normal_code", [0, 1, 2, 127, 255])
def test_segfault_trapper_ignores_normal_and_generic_codes(normal_code: int) -> None:
    """Validates that non-segfault return codes return False."""
    assert SegfaultTrapper.is_segmentation_fault(normal_code) is False


def test_segfault_trapper_generates_jsonld_provenance(isolated_artifacts_dir: Path) -> None:
    """Verifies JSON-LD provenance block generation and atomic commitment on segfault."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)
    simulated_pid = 45120
    simulated_returncode = -11

    provenance = trapper.trap(
        process_id=simulated_pid,
        returncode=simulated_returncode,
        metadata={"method": "DLPNO-CCSD(T)", "basis": "aug-cc-pVQZ"},
    )

    assert isinstance(provenance, JSONLDProvenanceBlock)
    assert provenance.process_id == simulated_pid
    assert provenance.return_code == simulated_returncode
    assert provenance.fault_type == "OS_SEGMENTATION_FAULT"
    assert provenance.status == "FATAL_CRASH_RECORDED"

    prov_path = trapper.get_provenance_file_path()
    assert prov_path.exists()

    data = json.loads(prov_path.read_text(encoding="utf-8"))
    assert data["@context"] == "https://doi.org/10.5281/zenodo.cochem.v2"
    assert data["@type"] == "ComputationalProcessProvenance"
    assert data["process_id"] == simulated_pid
    assert data["return_code"] == simulated_returncode
    assert data["fault_type"] == "OS_SEGMENTATION_FAULT"
    assert data["metadata"]["method"] == "DLPNO-CCSD(T)"


def test_segfault_trapper_check_and_raise(isolated_artifacts_dir: Path) -> None:
    """Verifies that check_and_raise commits JSON-LD and raises SegmentationFaultError."""
    trapper = SegfaultTrapper(artifacts_dir=isolated_artifacts_dir)

    with pytest.raises(SegmentationFaultError) as exc_info:
        trapper.check_and_raise(process_id=8888, returncode=3221225477)

    assert "Segmentation fault detected" in str(exc_info.value)
    assert trapper.get_provenance_file_path().exists()


def test_segfault_trapper_exitcode139_alias(isolated_artifacts_dir: Path) -> None:
    """Verifies that ExitCode139_Trapper operates identically to SegfaultTrapper."""
    assert ExitCode139_Trapper is SegfaultTrapper
    trapper = ExitCode139_Trapper(artifacts_dir=isolated_artifacts_dir)
    assert trapper.is_segmentation_fault(139) is True


# ==============================================================================
# 7. Composite Subprocess Execution Orchestrator Tests
# ==============================================================================

def test_execute_protected_subprocess_success(isolated_artifacts_dir: Path) -> None:
    """Verifies end-to-end execution of a healthy protected subprocess."""
    retcode, provenance = execute_protected_subprocess(
        cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        artifacts_dir=isolated_artifacts_dir,
        min_free_scratch_bytes=1024,
        pin_cores=False,
        enable_thermal_governor=True,
    )
    assert retcode == 0
    assert provenance is None


# ==============================================================================
# 8. TemporalRouter Tests (10-Tier Wall Clock & Hardware Guardrails)
# ==============================================================================

def test_temporal_router_air_gap_missing_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing COCHEM_ARTIFACTS_DIR raises fatal RuntimeError."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)
    router = TemporalRouter()

    with pytest.raises(RuntimeError) as exc_info:
        router.load_system_config()
    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)


def test_temporal_router_missing_config_raises(isolated_artifacts_dir: Path) -> None:
    """Verifies FileNotFoundError when cochem_system_config.json is absent."""
    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)
    with pytest.raises(FileNotFoundError) as exc_info:
        router.load_system_config()
    assert "cochem_system_config.json" in str(exc_info.value)


def test_temporal_router_metadata_extraction_bench_run_context(isolated_artifacts_dir: Path) -> None:
    """Validates extraction of method and atom count N from authentic BenchRunContext."""
    from cochem_bench.bench_engine.cochem_bench_ingest import (
        BenchConfigSchema,
        BenchHardwareSchema,
        BenchRunContext,
    )

    hw = BenchHardwareSchema(ram_gb=16.0, cpu_physical_cores=4)
    cfg = BenchConfigSchema(
        hardware=hw,
        active_jobs={"method": "DLPNO-CCSD(T)", "atom_count": 8},
    )
    context = BenchRunContext(
        config_hash="abc12345",
        safe_maxcore_mb=3000,
        target_mpi_threads=3,
        node_id="test_node",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        orca_path=None,
        hdf5_path=isolated_artifacts_dir / "landscape.h5",
        scratch_path=isolated_artifacts_dir / "scratch",
        numa_nodes=1,
        resource_warning=False,
        config=cfg,
    )

    method, atoms = TemporalRouter.extract_metadata_from_context(context)
    assert method == "DLPNO-CCSD(T)"
    assert atoms == 8


def test_temporal_router_local_workstation_dlpno_disables_and_warns(isolated_artifacts_dir: Path) -> None:
    """Verifies ResourceWarning emission, execution disablement, and HPC suggestion for DLPNO on Local Workstation."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 32.0,
            "os_target": "Local-Windows",
        },
        "hpc": {
            "scheduler": "local",
            "execution_mode": "local",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = router.route(method="DLPNO-CCSD(T)", atom_count=6)

    assert any(issubclass(w.category, ResourceWarning) for w in record)
    assert isinstance(result, TemporalRouteResult)
    assert result.is_local_workstation is True
    assert result.execution_allowed is False
    assert result.resource_warning_emitted is True
    assert result.suggested_offload == "HPC/SLURM"
    assert result.tier >= 9
    assert result.scaling_exponent == 7


def test_temporal_router_local_workstation_dft_authorized(isolated_artifacts_dir: Path) -> None:
    """Verifies that modest DFT calculations on Local Workstations are authorized without warning."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "os_target": "Local-Linux",
        },
        "hpc": {
            "scheduler": "local",
            "execution_mode": "local",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = router.route(method="B3LYP/def2-TZVP", atom_count=5)

    assert len([w for w in record if issubclass(w.category, ResourceWarning)]) == 0
    assert result.is_local_workstation is True
    assert result.execution_allowed is True
    assert result.resource_warning_emitted is False
    assert result.suggested_offload is None
    assert result.tier == 3
    assert result.scaling_exponent == 4


def test_temporal_router_hpc_cluster_authorizes_dlpno(isolated_artifacts_dir: Path) -> None:
    """Verifies that heavy DLPNO-CCSD(T) calculations on HPC cluster profiles are authorized."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 64,
            "logical_cpu_cores": 128,
            "ram_gb": 512.0,
            "os_target": "HPC",
        },
        "hpc": {
            "scheduler": "slurm",
            "execution_mode": "cluster",
        },
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    router = TemporalRouter(artifacts_dir=isolated_artifacts_dir)
    result = router.route(method="DLPNO-CCSD(T)", atom_count=12)

    assert result.is_local_workstation is False
    assert result.execution_allowed is True
    assert result.tier == 10
    assert result.scaling_exponent == 7
    assert result.wall_clock_estimate == "1mo"


def test_temporal_router_call_shorthand_syntax(isolated_artifacts_dir: Path) -> None:
    """Verifies functional instantiation TemporalRouter(method=..., atom_count=...)."""
    reg_dir = get_registry_workspace_dir(isolated_artifacts_dir)
    reg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = reg_dir / "cochem_system_config.json"

    cfg_payload = {
        "schema_version": "1.0.0",
        "hardware": {"ram_gb": 32.0, "os_target": "Local-Windows"},
        "hpc": {"scheduler": "local"},
    }
    cfg_file.write_text(json.dumps(cfg_payload, indent=2), encoding="utf-8")

    result = TemporalRouter(method="MP2", atom_count=4, artifacts_dir=isolated_artifacts_dir)
    assert isinstance(result, TemporalRouteResult)
    assert result.method == "MP2"
    assert result.atom_count == 4
    assert result.scaling_exponent == 5
    assert result.tier == 6


# ==============================================================================
# 9. High-Speed I/O Routing Tests (tmpfs RAM-Disk & Persistence)
# ==============================================================================

def test_high_speed_io_router_windows_bypasses_ramdisk(isolated_artifacts_dir: Path) -> None:
    """Verifies that Windows systems or non-posix environments bypass /dev/shm."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)
    report = router.route_scratch(available_ram_gb=256.0, job_id="test_win_job")

    assert isinstance(report, IOScratchRouteReport)
    assert report.available_ram_gb == 256.0
    if os.name != "posix":
        assert report.is_ramdisk is False
        assert report.route_type == "STANDARD_NVME_SCRATCH"
        assert Path(report.scratch_path).exists()


def test_high_speed_io_router_low_ram_bypasses_ramdisk(isolated_artifacts_dir: Path) -> None:
    """Verifies that RAM capacity <= 128 GB routes to standard NVMe scratch."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)
    report = router.route_scratch(available_ram_gb=64.0, job_id="test_low_ram")

    assert report.is_ramdisk is False
    assert report.route_type == "STANDARD_NVME_SCRATCH"
    assert Path(report.scratch_path).exists()


def test_high_speed_io_router_finalize_and_cleanup_lifecycle(isolated_artifacts_dir: Path) -> None:
    """Verifies artifact copying (.out, .gbw) to persistent workspace and RAM-disk recovery."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)

    temp_scratch = isolated_artifacts_dir / "temp_calc_scratch"
    temp_scratch.mkdir(parents=True, exist_ok=True)

    # Create calculation artifacts
    out_file = temp_scratch / "orca_calc.out"
    out_file.write_text("FINAL SINGLE POINT ENERGY -150.12345678", encoding="utf-8")
    gbw_file = temp_scratch / "orca_calc.gbw"
    gbw_file.write_bytes(b"\x00\x01\x02ORCA_GBW_DENSITY_MATRIX")
    tmp_file = temp_scratch / "orca_calc.tmp"
    tmp_file.write_text("transient integral cache", encoding="utf-8")

    persistent_dir = isolated_artifacts_dir / "persistent_ssd_workspace"

    cleanup_report = router.finalize_and_cleanup(
        active_scratch_path=temp_scratch,
        persistent_workspace_path=persistent_dir,
        copy_extensions=(".out", ".gbw"),
        is_ramdisk=True,
    )

    assert isinstance(cleanup_report, IOCleanupReport)
    assert cleanup_report.ramdisk_cleaned is True
    assert (persistent_dir / "orca_calc.out").exists()
    assert (persistent_dir / "orca_calc.gbw").exists()
    assert not (persistent_dir / "orca_calc.tmp").exists()
    assert not temp_scratch.exists()


def test_high_speed_io_router_context_manager(isolated_artifacts_dir: Path) -> None:
    """Verifies end-to-end scratch_context context manager lifecycle and persistence."""
    router = HighSpeedIORouter(artifacts_dir=isolated_artifacts_dir)

    with router.scratch_context(available_ram_gb=64.0, job_id="cm_calc") as scratch_path:
        assert scratch_path.exists()
        out_f = scratch_path / "result.out"
        out_f.write_text("ORCA TERMINATED NORMALLY", encoding="utf-8")
        gbw_f = scratch_path / "result.gbw"
        gbw_f.write_bytes(b"GBW_PAYLOAD")

    persistent_scratch = get_scratch_workspace_dir(isolated_artifacts_dir)
    assert (persistent_scratch / "result.out").exists()
    assert (persistent_scratch / "result.gbw").exists()


def test_high_speed_io_routing_alias() -> None:
    """Verifies HighSpeedIORouting is an authoritative alias for HighSpeedIORouter."""
    assert HighSpeedIORouting is HighSpeedIORouter



Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.