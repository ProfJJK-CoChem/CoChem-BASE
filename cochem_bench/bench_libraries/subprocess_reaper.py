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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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
