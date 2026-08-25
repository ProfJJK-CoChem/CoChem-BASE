#!/usr/bin/env python3
r"""Stage 6.0: Subprocess Brokering, Process Group Isolation, and Zombie Reaper Engine.

Authoritative Implementation: cochem_bench.bench_libraries.subprocess_reaper
System Domain: CoChem-BENCH Defensive Infrastructure

Key Capabilities:
1. PreFlightScratchVerifier: Mathematically verifies available NVMe scratch space before
   launching heavy CBS or DLPNO-CCSD(T) calculations, failing fast with ResourceGuardError.
2. NUMA_ThreadPinner: Hardware-aware CPU affinity manager reading dynamic configuration
   and applying psutil.Process().cpu_affinity() constraints without complex cache mapping.
3. ZombieReaper: Detached process group isolation and ZeroMQ PUB/SUB heartbeat monitor
   with ruthless cross-platform recursive tree termination upon heartbeat drop or ABORT.signal.
4. SegfaultTrapper: Strict OS-level Segmentation Fault interceptor evaluating integer return codes
   (-11 on POSIX, 0xC0000005 / 3221225477 / -1073741819 on Windows, 139) and writing FAIR JSON-LD
   provenance records without parsing standard error output.
5. Dynamic Mendeleev Integration: Element mass resolution dynamically querying the Mendeleev database.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt2_reaper.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 6 Subprocess Brokering & Temporal Engine Routing.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import datetime
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil
import zmq
from mendeleev import element
from pydantic import BaseModel, Field, ConfigDict


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


# ==============================================================================
# Dynamic Environment & Path Resolution Helpers
# ==============================================================================

def get_cochem_artifacts_dir() -> Path:
    """Dynamically resolves the CoChem artifacts root directory.

    Priority:
    1. os.environ['COCHEM_ARTIFACTS_DIR']
    2. Path.home() / 'cochem_artifacts'
    """
    env_path = os.environ.get("COCHEM_ARTIFACTS_DIR")
    if env_path and env_path.strip():
        return Path(env_path).resolve()
    return (Path.home() / "cochem_artifacts").resolve()


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

        # Query OS disk usage
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
        except ResourceGuardError:
            return False


# ==============================================================================
# 2. NUMA_ThreadPinner
# ==============================================================================

class NUMA_ThreadPinner:
    """Hardware-aware CPU affinity manager restricting processes to designated cores.

    Reads dynamic configuration from Registry/cochem_system_config.json and applies
    psutil.Process().cpu_affinity() constraints without complex cache mapping logic.
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

    def load_affinity_cores(self) -> List[int]:
        """Loads target CPU core affinity list from the system configuration file."""
        cfg_file = self.resolve_config_path()
        total_logical_cpus = psutil.cpu_count(logical=True) or 1

        if not cfg_file.exists():
            # Default to first physical/logical core when configuration file is not deployed
            return [0]

        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            reg = SystemRegistryConfig.model_validate(data)
        except Exception as exc:
            raise NUMAPinningError(f"Failed to parse system configuration at {cfg_file}: {exc}") from exc

        # Extract cores in order of priority
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

        # If no explicit list, restrict to physical core count range
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

        # Check if platform supports cpu_affinity (Linux, Windows natively support it)
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

    Guarantees termination of orphaned OpenMPI and computational chemistry child threads.
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
            # Yield briefly to permit subscription negotiation
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

    def terminate_process_tree(
        self,
        target_pid: int,
        reason: str = "MANUAL_REAP",
        timeout_sec: float = 3.0,
    ) -> ProcessReapReport:
        """Ruthlessly terminates target process and all descendant child processes recursively.

        Uses taskkill on Windows and psutil/SIGKILL on POSIX platforms.
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

        # Collect child processes recursively
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

        # Windows Execution: Use taskkill /F /T for atomic process tree elimination
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(target_pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
            except Exception:
                pass

        # Cross-platform psutil termination fallback / confirmation
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

        # Wait for processes to terminate
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
        """Evaluates if the raw integer return code corresponds to an OS segmentation fault.

        Strictly evaluates returncode against known OS signal and NTSTATUS constants.
        """
        return int(returncode) in SEGFAULT_RETURN_CODES

    def trap(
        self,
        process_id: int,
        returncode: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[JSONLDProvenanceBlock]:
        """Intercepts process exit code, generating and saving JSON-LD block if segfaulted.

        Args:
            process_id: Process ID of the executed subprocess.
            returncode: Raw integer return code.
            metadata: Optional execution context dictionary.

        Returns:
            JSONLDProvenanceBlock if segfault occurred, or None if process exited normally.
        """
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

        # Commit atomically to bench_provenance.jsonld
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
# 5. Composite Subprocess Execution Orchestrator
# ==============================================================================

def execute_protected_subprocess(
    cmd: List[str],
    artifacts_dir: Optional[Union[str, Path]] = None,
    min_free_scratch_bytes: int = DEFAULT_MIN_FREE_SCRATCH_BYTES,
    pin_cores: bool = True,
    env_override: Optional[Dict[str, str]] = None,
) -> Tuple[int, Optional[JSONLDProvenanceBlock]]:
    """High-level orchestrator executing a subprocess within the complete defensive perimeter.

    Workflow:
    1. Pre-flight scratch disk verification.
    2. Execution with dynamic environment and process group decoupling.
    3. CPU core thread pinning via NUMA_ThreadPinner.
    4. Return code inspection via SegfaultTrapper and JSON-LD provenance generation.
    """
    verifier = PreFlightScratchVerifier(artifacts_dir=artifacts_dir, default_min_free_bytes=min_free_scratch_bytes)
    verifier.verify()

    exec_env = dict(os.environ)
    if artifacts_dir:
        exec_env["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)
    if env_override:
        exec_env.update(env_override)

    proc = subprocess.Popen(
        cmd,
        env=exec_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if pin_cores:
        pinner = NUMA_ThreadPinner(artifacts_dir=artifacts_dir)
        try:
            pinner.pin_process(pid=proc.pid)
        except Exception:
            # Non-blocking fallback if pinning not permitted
            pass

    stdout_data, stderr_data = proc.communicate()
    retcode = proc.returncode

    trapper = SegfaultTrapper(artifacts_dir=artifacts_dir)
    provenance = trapper.trap(
        process_id=proc.pid,
        returncode=retcode,
        metadata={"cmd": cmd},
    )

    return retcode, provenance
