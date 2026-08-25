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
import hashlib
import json
import logging
import os
import re
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


class OSFaultError(SegmentationFaultError):
    """Raised when an OS-level fault (Segfault, OOM, Access Violation) is trapped."""
    pass


class StreamTrapError(SubprocessReaperBaseError):
    """Base exception raised when an active stream regex trap intercepts an anomaly."""
    pass


class LinearDependenceFaultError(StreamTrapError):
    """Raised when eigenvalues < 10^-6 is detected in ORCA output stream."""
    pass


class EnergyMatrixNaNInfFaultError(StreamTrapError):
    """Raised when NaN or Inf appears in energy matrices or output stream."""
    pass


class SCFPingPongOscillationError(StreamTrapError):
    """Raised when a 2-cycle SCF ping-pong oscillation is detected."""
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

# POSIX Out-Of-Memory (OOM) Killer codes: -9 (-SIGKILL), 137 (128 + 9)
OOM_RETURN_CODES: Set[int] = {-9, 137}

# Comprehensive OS-level fault trap return codes
OS_FAULT_RETURN_CODES: Set[int] = SEGFAULT_RETURN_CODES | OOM_RETURN_CODES

# Active stream regex trap patterns
LINEAR_DEPENDENCE_PATTERN: str = r"eigenvalues\s*<\s*10\^-6|eigenvalues < 10\^-6"
NAN_INF_PATTERN: str = r"\b(?:NaN|Inf|Infinity|-NaN|-Inf)\b"
SCF_DELTA_E_PATTERN: str = r"(?:Delta-E|DELTA-E|DE|Delta E)\s*[:=]?\s*([+-]?\d+\.\d+(?:[eE][+-]?\d+)?)|^\s*\d+\s+[-+]?\d+\.\d+\s+([-+]?\d+\.\d+(?:[eE][+-]?\d+)?)"
SLOWCONV_SOSCF_KEYWORD: str = "! SlowConv SOSCF"

# Standard trap classification identifiers
ORCA_LINEAR_DEPENDENCE_FAULT: str = "ORCA_LINEAR_DEPENDENCE_FAULT"
ENERGY_MATRIX_NAN_INF_FAULT: str = "ENERGY_MATRIX_NAN_INF_FAULT"
SCF_PING_PONG_OSCILLATION: str = "SCF_PING_PONG_OSCILLATION"


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


class StreamTrapEvent(BaseModel):
    """Structured event record emitted when an active stream regex trap triggers."""
    model_config = ConfigDict(frozen=True)

    trap_type: str = Field(description="Trap identifier: ORCA_LINEAR_DEPENDENCE_FAULT, ENERGY_MATRIX_NAN_INF_FAULT, or SCF_PING_PONG_OSCILLATION")
    line_content: str = Field(description="Raw line content that triggered the trap")
    pid: Optional[int] = Field(default=None, description="Process ID that was intercepted")
    rescued_input: Optional[str] = Field(default=None, description="Rescued ORCA input string with injected directives if applicable")
    delta_e_history: List[float] = Field(default_factory=list, description="Historical Delta-E trajectory for ping-pong analysis")
    message: str = Field(description="Operational diagnostic message")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of the trap event",
    )


class StreamTrapReport(BaseModel):
    """Execution report from monitoring an active subprocess stream."""
    model_config = ConfigDict(frozen=True)

    pid: int = Field(description="Target process ID monitored")
    trapped: bool = Field(description="True if any trap was triggered during stream execution")
    event: Optional[StreamTrapEvent] = Field(default=None, description="Detailed trap event if triggered")
    reaped: bool = Field(default=False, description="True if process tree was terminated by ZombieReaper")
    rescued_input: Optional[str] = Field(default=None, description="Rescued input string if ping-pong trap triggered")
    lines_processed: int = Field(default=0, description="Total number of stream lines parsed")
    delta_e_cycles: List[float] = Field(default_factory=list, description="All parsed Delta-E cycles")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
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
    hex_dump: Optional[str] = Field(default=None, description="Formatted 256-byte POSIX hex dump from tail scratch/stderr buffer")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution parameters")


class ProvenanceFooterPayload(BaseModel):
    """Structured FAIR-compliant JSON-LD Provenance Footer committed upon calculation finalization."""
    model_config = ConfigDict(populate_by_name=True)

    context: str = Field(default="https://doi.org/10.5281/zenodo.cochem.v2", alias="@context")
    type: str = Field(default="BenchmarkProvenanceFooter", alias="@type")
    cochem_version: str = Field(default="2.0.0", alias="CoChem_Version")
    orca_binary_hash: str = Field(description="SHA-256 hash of the ORCA binary executable", alias="ORCA_Binary_Hash")
    hardware_profile: Dict[str, Any] = Field(description="Hardware profile configuration", alias="Hardware_Profile")
    geometry_hash: str = Field(description="SHA-256 hash of the starting geometry coordinates", alias="Geometry_Hash")
    composite_methodology: Union[str, Dict[str, Any]] = Field(description="Composite protocol mathematical methodology", alias="Composite_Methodology")
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of calculation finalization",
    )


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
# Hex Dumping & SHA-256 Cryptographic Helpers
# ==============================================================================

def format_hex_dump(data: Union[bytes, bytearray], bytes_per_line: int = 16) -> str:
    """Formats raw binary bytes into a POSIX-compliant canonical hex-dump string (hexdump -C style)."""
    if not data:
        return ""
    raw = bytes(data)
    lines: List[str] = []
    for offset in range(0, len(raw), bytes_per_line):
        chunk = raw[offset : offset + bytes_per_line]
        if len(chunk) > 8:
            first_8 = " ".join(f"{b:02x}" for b in chunk[:8])
            second_8 = " ".join(f"{b:02x}" for b in chunk[8:])
            hex_part = f"{first_8:<23}  {second_8:<23}"
        else:
            hex_part = f"{' '.join(f'{b:02x}' for b in chunk):<48}"
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{offset:08x}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)


def extract_tail_hex_dump(
    data_or_file: Union[bytes, bytearray, str, Path],
    max_bytes: int = 256,
) -> str:
    """Extracts the final max_bytes from binary data or a dump file and converts to a hex-dump string."""
    if isinstance(data_or_file, Path) or (isinstance(data_or_file, str) and not data_or_file.startswith("\n") and Path(data_or_file).is_file()):
        p = Path(data_or_file)
        if not p.exists() or not p.is_file():
            return ""
        size = p.stat().st_size
        offset = max(0, size - max_bytes)
        with p.open("rb") as fh:
            fh.seek(offset)
            raw = fh.read(max_bytes)
        return format_hex_dump(raw)
    elif isinstance(data_or_file, (bytes, bytearray)):
        raw = bytes(data_or_file)[-max_bytes:]
        return format_hex_dump(raw)
    elif isinstance(data_or_file, str):
        raw = data_or_file.encode("utf-8", errors="replace")[-max_bytes:]
        return format_hex_dump(raw)
    return ""


def find_scratch_dump_file(scratch_dir: Path) -> Optional[Path]:
    """Finds the most recent dump file (.tmp, stderr, .err, .log) in the scratch workspace."""
    if not scratch_dir.exists() or not scratch_dir.is_dir():
        return None
    candidates: List[Tuple[float, Path]] = []
    for item in scratch_dir.iterdir():
        if item.is_file():
            lname = item.name.lower()
            if lname.endswith(".tmp") or lname.endswith(".err") or "stderr" in lname or lname.endswith(".dump"):
                try:
                    mtime = item.stat().st_mtime
                    candidates.append((mtime, item))
                except OSError:
                    pass
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None


def compute_sha256_hash(data: Union[str, bytes, bytearray, Path]) -> str:
    """Computes SHA-256 hexadecimal digest for string, bytes, or file content."""
    if isinstance(data, Path) or (isinstance(data, str) and not data.startswith("\n") and Path(data).is_file()):
        p = Path(data)
        hasher = hashlib.sha256()
        with p.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    elif isinstance(data, (bytes, bytearray)):
        return hashlib.sha256(data).hexdigest()
    elif isinstance(data, str):
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    else:
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


def compute_geometry_hash(geometry: Union[str, bytes, bytearray, Path, Any]) -> str:
    """Computes SHA-256 hash of starting geometry coordinates / XYZ string."""
    if isinstance(geometry, str):
        cleaned = "\n".join(line.strip() for line in geometry.strip().splitlines() if line.strip())
        return compute_sha256_hash(cleaned)
    return compute_sha256_hash(geometry)


def compute_orca_binary_hash(binary_path_or_identifier: Union[str, bytes, bytearray, Path]) -> str:
    """Computes SHA-256 hash of ORCA binary executable or binary identifier."""
    return compute_sha256_hash(binary_path_or_identifier)


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

    def kill_process_group(self, target_pid: int) -> None:
        """Kills process group using os.killpg on POSIX or taskkill /T /F on Windows."""
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

    def reap_on_linear_dependence(self, target_pid: int) -> ProcessReapReport:
        """Issues Zombie Reaper kill command and logs ORCA_LINEAR_DEPENDENCE_FAULT."""
        logger.error(
            "ORCA_LINEAR_DEPENDENCE_FAULT: Intercepted eigenvalues < 10^-6 for PID %s. Reaping process tree.",
            target_pid,
        )
        return self.terminate_process_tree(target_pid=target_pid, reason=ORCA_LINEAR_DEPENDENCE_FAULT)

    def reap_on_nan_inf(self, target_pid: int) -> ProcessReapReport:
        """Issues Zombie Reaper kill command and logs ENERGY_MATRIX_NAN_INF_FAULT."""
        logger.error(
            "ENERGY_MATRIX_NAN_INF_FAULT: Intercepted NaN or Inf in energy matrix for PID %s. Reaping process tree.",
            target_pid,
        )
        return self.terminate_process_tree(target_pid=target_pid, reason=ENERGY_MATRIX_NAN_INF_FAULT)

    def reap_and_requeue_ping_pong(
        self,
        target_pid: int,
        orca_input: str,
    ) -> Tuple[ProcessReapReport, str]:
        """Terminates process tree for SCF ping-pong oscillation and injects ! SlowConv SOSCF rescue."""
        logger.warning(
            "SCF_PING_PONG_OSCILLATION: Intercepted 2-cycle ping-pong limit cycle for PID %s. Reaping and re-queuing.",
            target_pid,
        )
        report = self.terminate_process_tree(target_pid=target_pid, reason=SCF_PING_PONG_OSCILLATION)
        trap = ActiveStreamRegexTrap(reaper=self, artifacts_dir=self.artifacts_dir)
        rescued_input = trap.inject_slowconv_soscf(orca_input)
        return report, rescued_input

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
    """Strict OS-level Segmentation Fault and OOM interceptor evaluating integer return codes.

    Catches:
    - POSIX Segfaults: -11, 139
    - POSIX OOM: -9, 137
    - Windows Access Violations: 0xC0000005, 3221225477, -1073741819

    Extracts tail 256-byte binary dump from scratch files, formats POSIX hex-dump,
    logs error, and commits FAIR JSON-LD provenance.
    """

    def __init__(self, artifacts_dir: Optional[Union[str, Path]] = None) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None

    def resolve_processed_dir(self) -> Path:
        """Resolves the dynamic Processed workspace directory."""
        proc_dir = get_processed_workspace_dir(self.artifacts_dir)
        proc_dir.mkdir(parents=True, exist_ok=True)
        return proc_dir

    def resolve_scratch_dir(self) -> Path:
        """Resolves the dynamic Scratch workspace directory."""
        scratch_dir = get_scratch_workspace_dir(self.artifacts_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    def get_provenance_file_path(self) -> Path:
        """Returns the destination path for bench_provenance.jsonld."""
        return self.resolve_processed_dir() / "bench_provenance.jsonld"

    @staticmethod
    def is_segmentation_fault(returncode: int) -> bool:
        """Evaluates if the raw integer return code corresponds to an OS segmentation fault."""
        return int(returncode) in SEGFAULT_RETURN_CODES

    @staticmethod
    def is_oom_fault(returncode: int) -> bool:
        """Evaluates if the raw integer return code corresponds to an OS Out-Of-Memory fault."""
        return int(returncode) in OOM_RETURN_CODES

    @staticmethod
    def is_os_fault(returncode: int) -> bool:
        """Evaluates if the raw integer return code corresponds to any trapped OS fault."""
        return int(returncode) in OS_FAULT_RETURN_CODES

    def extract_scratch_hex_dump(
        self,
        scratch_dir: Optional[Union[str, Path]] = None,
        max_bytes: int = 256,
    ) -> Optional[str]:
        """Locates scratch dump files (.tmp, stderr, .err), tails the final 256 bytes, and converts to hex dump."""
        target_dir = Path(scratch_dir).resolve() if scratch_dir else self.resolve_scratch_dir()
        dump_file = find_scratch_dump_file(target_dir)
        if dump_file is not None and dump_file.exists():
            hex_str = extract_tail_hex_dump(dump_file, max_bytes=max_bytes)
            if hex_str:
                return hex_str
        return None

    def trap(
        self,
        process_id: int,
        returncode: int,
        metadata: Optional[Dict[str, Any]] = None,
        stderr_data: Optional[Union[bytes, str]] = None,
        scratch_override: Optional[Union[str, Path]] = None,
    ) -> Optional[JSONLDProvenanceBlock]:
        """Intercepts process exit code, extracts tail hex dump, and saves JSON-LD provenance block."""
        if not self.is_os_fault(returncode):
            return None

        hex_dump_str: Optional[str] = None
        if stderr_data is not None:
            hex_dump_str = extract_tail_hex_dump(stderr_data, max_bytes=256)
        else:
            try:
                hex_dump_str = self.extract_scratch_hex_dump(scratch_dir=scratch_override, max_bytes=256)
            except Exception:
                hex_dump_str = None

        fault_type = "OS_OOM_FAULT" if self.is_oom_fault(returncode) else "OS_SEGMENTATION_FAULT"

        if hex_dump_str:
            logger.error(
                "OS_FAULT_TRAPPED: Fault %s detected (PID %s, ReturnCode %s). Tail 256-byte hex dump:\n%s",
                fault_type,
                process_id,
                returncode,
                hex_dump_str,
            )

        prov_path = self.get_provenance_file_path()
        meta = dict(metadata or {})
        if hex_dump_str:
            meta["hex_dump"] = hex_dump_str

        block = JSONLDProvenanceBlock(
            process_id=int(process_id),
            return_code=int(returncode),
            fault_type=fault_type,
            status="FATAL_CRASH_RECORDED",
            provenance_file=str(prov_path),
            hex_dump=hex_dump_str,
            metadata=meta,
        )

        prov_path.write_text(block.model_dump_json(by_alias=True, indent=2), encoding="utf-8")
        return block

    def check_and_raise(
        self,
        process_id: int,
        returncode: int,
        metadata: Optional[Dict[str, Any]] = None,
        stderr_data: Optional[Union[bytes, str]] = None,
        scratch_override: Optional[Union[str, Path]] = None,
    ) -> None:
        """Intercepts return code, persists JSON-LD, and raises SegmentationFaultError if detected."""
        block = self.trap(
            process_id=process_id,
            returncode=returncode,
            metadata=metadata,
            stderr_data=stderr_data,
            scratch_override=scratch_override,
        )
        if block is not None:
            dump_msg = f"\nHex Dump:\n{block.hex_dump}" if block.hex_dump else ""
            raise SegmentationFaultError(
                f"Segmentation fault detected (PID: {process_id}, ReturnCode: {returncode}).{dump_msg} "
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
# 9. Active Stream Regex Traps & Anomaly Watchdogs
# ==============================================================================

class ActiveStreamRegexTrap:
    """Active subprocess stderr/stdout polling watchdog and regex trap.

    Interrogates stream output for fatal mathematical faults and divergence traps:
    1. Linear Dependence: eigenvalues < 10^-6 -> triggers Zombie Reaper and logs ORCA_LINEAR_DEPENDENCE_FAULT.
    2. NaN / Inf Output: NaN / Inf detected in energy matrices -> instantly kills calculation.
    3. SCF Ping-Pong Trap: Tracks last 5 SCF Delta-E cycles. If signs alternate perfectly while
       magnitude is constant, kills the job and returns re-queued input injecting '! SlowConv SOSCF'.
    """

    def __init__(
        self,
        reaper: Optional[ZombieReaper] = None,
        artifacts_dir: Optional[Union[str, Path]] = None,
        ping_pong_tolerance: float = 1e-4,
    ) -> None:
        self.artifacts_dir = Path(artifacts_dir).resolve() if artifacts_dir else None
        self.reaper = reaper or ZombieReaper(artifacts_dir=self.artifacts_dir)
        self.ping_pong_tolerance = float(ping_pong_tolerance)
        self.delta_e_history: List[float] = []
        self._linear_dep_re = re.compile(LINEAR_DEPENDENCE_PATTERN, re.IGNORECASE)
        self._nan_inf_re = re.compile(NAN_INF_PATTERN)

    def detect_linear_dependence(self, text: str) -> bool:
        """Evaluates whether text contains the literal string 'eigenvalues < 10^-6'."""
        if "eigenvalues < 10^-6" in text:
            return True
        return bool(self._linear_dep_re.search(text))

    def detect_nan_inf(self, text: str) -> bool:
        """Evaluates whether text contains NaN or Inf numeric tokens."""
        return bool(self._nan_inf_re.search(text))

    def extract_delta_e(self, line: str) -> Optional[float]:
        """Attempts to parse SCF Delta-E value from an ORCA output iteration line."""
        stripped = line.strip()
        if not stripped:
            return None

        parts = stripped.split()
        if len(parts) >= 3 and parts[0].isdigit():
            try:
                val = float(parts[2])
                return val
            except (ValueError, IndexError):
                pass

        if "Delta-E" in line or "DELTA-E" in line or "Delta E" in line:
            m = re.search(r"(?:Delta-E|DELTA-E|DE|Delta E)\s*[:=]?\s*([+-]?\d+\.\d+(?:[eE][+-]?\d+)?)", line)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass

        return None

    def detect_ping_pong_oscillation(
        self,
        delta_e_cycles: Optional[List[float]] = None,
        tolerance: Optional[float] = None,
    ) -> bool:
        """Checks if the last 5 SCF Delta-E cycles exhibit 2-cycle ping-pong oscillation.

        Criteria:
        1. At least 5 recorded cycles.
        2. Signs alternate strictly across all consecutive pairs in the 5-cycle window.
        3. Magnitude is constant within specified tolerance.
        """
        history = list(delta_e_cycles) if delta_e_cycles is not None else list(self.delta_e_history)
        if len(history) < 5:
            return False

        last_5 = history[-5:]
        tol = tolerance if tolerance is not None else self.ping_pong_tolerance

        # 1. Non-zero checks and alternating signs
        for i in range(4):
            v1 = last_5[i]
            v2 = last_5[i + 1]
            if abs(v1) < 1e-12 or abs(v2) < 1e-12:
                return False
            if (v1 * v2) >= 0:
                return False

        # 2. Constant magnitude check
        mags = [abs(x) for x in last_5]
        max_m = max(mags)
        min_m = min(mags)

        if (max_m - min_m) <= tol:
            return True

        if max_m > 0 and ((max_m - min_m) / max_m) <= 0.05:
            return True

        return False

    def inject_slowconv_soscf(self, orca_input: str) -> str:
        """Injects '! SlowConv SOSCF' into the ORCA input text for SCF rescue."""
        if not orca_input or not orca_input.strip():
            return f"{SLOWCONV_SOSCF_KEYWORD}\n"

        lines = orca_input.splitlines()
        keyword_line_idx = -1

        for idx, l in enumerate(lines):
            stripped = l.strip()
            if stripped.startswith("!"):
                keyword_line_idx = idx
                break

        if keyword_line_idx >= 0:
            kw_line = lines[keyword_line_idx]
            kw_upper = kw_line.upper()
            additions: List[str] = []
            if "SLOWCONV" not in kw_upper:
                additions.append("SlowConv")
            if "SOSCF" not in kw_upper:
                additions.append("SOSCF")

            if additions:
                prefix = kw_line[: kw_line.find("!") + 1]
                rest = kw_line[kw_line.find("!") + 1 :].strip()
                if rest:
                    new_kw = f"{prefix} {' '.join(additions)} {rest}".strip()
                else:
                    new_kw = f"{prefix} {' '.join(additions)}".strip()
                lines[keyword_line_idx] = new_kw
            return "\n".join(lines)
        else:
            return f"{SLOWCONV_SOSCF_KEYWORD}\n{orca_input}"

    def process_line(
        self,
        line: str,
        pid: Optional[int] = None,
        orca_input: Optional[str] = None,
    ) -> Optional[StreamTrapEvent]:
        """Evaluates a single line against active stream regex traps, executing reaps if triggered."""
        # 1. Linear dependence trap
        if self.detect_linear_dependence(line):
            logger.error("ORCA_LINEAR_DEPENDENCE_FAULT detected: %s", line.strip())
            if pid is not None:
                self.reaper.kill_process_group(pid)
                self.reaper.terminate_process_tree(pid, reason=ORCA_LINEAR_DEPENDENCE_FAULT)

            return StreamTrapEvent(
                trap_type=ORCA_LINEAR_DEPENDENCE_FAULT,
                line_content=line.strip(),
                pid=pid,
                message="Linear dependence overlap detected: eigenvalues < 10^-6. Job terminated.",
            )

        # 2. NaN / Inf trap
        if self.detect_nan_inf(line):
            logger.error("ENERGY_MATRIX_NAN_INF_FAULT detected: %s", line.strip())
            if pid is not None:
                self.reaper.kill_process_group(pid)
                self.reaper.terminate_process_tree(pid, reason=ENERGY_MATRIX_NAN_INF_FAULT)

            return StreamTrapEvent(
                trap_type=ENERGY_MATRIX_NAN_INF_FAULT,
                line_content=line.strip(),
                pid=pid,
                message="NaN/Inf numeric singularity detected in energy matrix. Job terminated.",
            )

        # 3. Ping-Pong trap
        de = self.extract_delta_e(line)
        if de is not None:
            self.delta_e_history.append(de)
            if self.detect_ping_pong_oscillation():
                rescued_input = self.inject_slowconv_soscf(orca_input or "")
                logger.warning("SCF_PING_PONG_OSCILLATION detected. Re-queuing with ! SlowConv SOSCF.")
                if pid is not None:
                    self.reaper.kill_process_group(pid)
                    self.reaper.terminate_process_tree(pid, reason=SCF_PING_PONG_OSCILLATION)

                return StreamTrapEvent(
                    trap_type=SCF_PING_PONG_OSCILLATION,
                    line_content=line.strip(),
                    pid=pid,
                    rescued_input=rescued_input,
                    delta_e_history=list(self.delta_e_history[-5:]),
                    message="2-cycle SCF ping-pong oscillation detected. Job terminated and re-queued with ! SlowConv SOSCF.",
                )

        return None

    def poll_stream(
        self,
        stream: Any,
        pid: Optional[int] = None,
        orca_input: Optional[str] = None,
    ) -> Generator[str, None, Optional[StreamTrapEvent]]:
        """Yields lines from stream while checking regex traps on each line."""
        for raw_line in stream:
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line)
            event = self.process_line(line, pid=pid, orca_input=orca_input)
            yield line
            if event is not None:
                return event
        return None

    def monitor_process(
        self,
        proc: subprocess.Popen,
        orca_input: Optional[str] = None,
        poll_interval_sec: float = 0.01,
    ) -> StreamTrapReport:
        """Monitors a running subprocess stdout/stderr streams, applying regex traps."""
        lines_count = 0
        trapped_event: Optional[StreamTrapEvent] = None

        if proc.stdout:
            while proc.poll() is None:
                line = proc.stdout.readline()
                if not line:
                    time.sleep(poll_interval_sec)
                    continue
                line_str = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line)
                lines_count += 1
                event = self.process_line(line_str, pid=proc.pid, orca_input=orca_input)
                if event is not None:
                    trapped_event = event
                    break

        return StreamTrapReport(
            pid=proc.pid,
            trapped=trapped_event is not None,
            event=trapped_event,
            reaped=trapped_event is not None,
            rescued_input=trapped_event.rescued_input if trapped_event else None,
            lines_processed=lines_count,
            delta_e_cycles=list(self.delta_e_history),
        )


# Authoritative alias
StreamRegexTrap = ActiveStreamRegexTrap


# ==============================================================================
# 10. JSON-LD Provenance Footer Appender
# ==============================================================================

def append_jsonld_provenance_footer(
    orca_binary_hash: str,
    hardware_profile: Union[Dict[str, Any], HardwareRegistryConfig, BaseModel],
    geometry_hash: str,
    composite_methodology: Union[str, Dict[str, Any]],
    cochem_version: str = "2.0.0",
    artifacts_dir: Optional[Union[str, Path]] = None,
    destination_path: Optional[Union[str, Path]] = None,
) -> Tuple[ProvenanceFooterPayload, Path]:
    """Appends a structured FAIR JSON-LD provenance footer to Processed/bench_provenance.jsonld.

    Guarantees persistence of:
    - CoChem_Version
    - ORCA_Binary_Hash (SHA-256)
    - Hardware_Profile
    - Geometry_Hash
    - Composite_Methodology

    Raises:
        RuntimeError: If COCHEM_ARTIFACTS_DIR is missing and artifacts_dir is not provided.
    """
    if destination_path is not None:
        target_path = Path(destination_path).resolve()
    else:
        base_dir = Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
        target_path = base_dir / "Processed" / "bench_provenance.jsonld"

    target_path.parent.mkdir(parents=True, exist_ok=True)

    hw_data: Dict[str, Any]
    if isinstance(hardware_profile, BaseModel):
        hw_data = hardware_profile.model_dump()
    elif isinstance(hardware_profile, dict):
        hw_data = dict(hardware_profile)
    else:
        hw_data = {"profile": str(hardware_profile)}

    payload = ProvenanceFooterPayload(
        CoChem_Version=cochem_version,
        ORCA_Binary_Hash=str(orca_binary_hash),
        Hardware_Profile=hw_data,
        Geometry_Hash=str(geometry_hash),
        Composite_Methodology=composite_methodology,
    )

    # Read existing entries if present to maintain valid JSON-LD ledger array
    existing_entries: List[Dict[str, Any]] = []
    if target_path.exists():
        try:
            content = target_path.read_text(encoding="utf-8").strip()
            if content:
                loaded = json.loads(content)
                if isinstance(loaded, list):
                    existing_entries = loaded
                elif isinstance(loaded, dict):
                    existing_entries = [loaded]
        except Exception:
            existing_entries = []

    payload_dict = payload.model_dump(by_alias=True)
    existing_entries.append(payload_dict)

    target_path.write_text(json.dumps(existing_entries, indent=2), encoding="utf-8")

    # Also mirror to BENCH_Workspace/Processed if target is Processed
    if destination_path is None:
        try:
            bench_processed = (
                Path(artifacts_dir).resolve() if artifacts_dir else get_cochem_artifacts_dir()
            ) / "BENCH_Workspace" / "Processed" / "bench_provenance.jsonld"
            bench_processed.parent.mkdir(parents=True, exist_ok=True)
            bench_processed.write_text(json.dumps(existing_entries, indent=2), encoding="utf-8")
        except Exception:
            pass

    return payload, target_path


# Authoritative alias
JSONLDProvenanceFooter = ProvenanceFooterPayload


# ==============================================================================
# Export Declarations
# ==============================================================================

__all__ = [
    "ActiveStreamRegexTrap",
    "CRITICAL_TEMP_CELSIUS",
    "DEFAULT_MIN_FREE_SCRATCH_BYTES",
    "ENERGY_MATRIX_NAN_INF_FAULT",
    "EnergyMatrixNaNInfFaultError",
    "ExitCode139_Trapper",
    "HardwareRegistryConfig",
    "HighSpeedIORouter",
    "HighSpeedIORouting",
    "IOCleanupReport",
    "IOScratchRouteReport",
    "JSONLDProvenanceBlock",
    "JSONLDProvenanceFooter",
    "LINEAR_DEPENDENCE_PATTERN",
    "LinearDependenceFaultError",
    "NAN_INF_PATTERN",
    "NUMAPinningError",
    "NUMA_ThreadPinner",
    "OOM_RETURN_CODES",
    "ORCA_LINEAR_DEPENDENCE_FAULT",
    "OSFaultError",
    "OS_FAULT_RETURN_CODES",
    "PreFlightResourceError",
    "PreFlightScratchVerifier",
    "ProcessReapReport",
    "ProvenanceFooterPayload",
    "RESUME_TEMP_CELSIUS",
    "ResourceGuardError",
    "SCF_DELTA_E_PATTERN",
    "SCF_PING_PONG_OSCILLATION",
    "SCFPingPongOscillationError",
    "SEGFAULT_RETURN_CODES",
    "SLOWCONV_SOSCF_KEYWORD",
    "ScratchSpaceReport",
    "SegfaultTrapper",
    "SegmentationFaultError",
    "StreamRegexTrap",
    "StreamTrapError",
    "StreamTrapEvent",
    "StreamTrapReport",
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
    "append_jsonld_provenance_footer",
    "compute_geometry_hash",
    "compute_orca_binary_hash",
    "compute_sha256_hash",
    "execute_protected_subprocess",
    "extract_tail_hex_dump",
    "find_scratch_dump_file",
    "format_hex_dump",
    "get_cochem_artifacts_dir",
    "get_element_mass_mendeleev",
    "get_processed_workspace_dir",
    "get_registry_workspace_dir",
    "get_scratch_workspace_dir",
    "launch_isolated_process",
]

