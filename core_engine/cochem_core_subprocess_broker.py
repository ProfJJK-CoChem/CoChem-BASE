#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 3.0 - The Subprocess Broker
Implements: Non-blocking IPC Execution, Win32 Job Objects / POSIX Process Group Reaper,
OOM Preemption Polling, ZeroMQ Heartbeat Publisher with CurveZMQ / IPC, NUMA-Aware CPU Pinning,
Pre-Flight Disk Quota & 64KB SHA-256 Binary Probe, RAM-Disk Overlay Routing, Directory Lockdown,
and Dead-Man's Switch Daemon Transition.
Provides `safe_subprocess_run`, `register_popen_process`, `CPUTopologyManager`,
`RAMDiskOverlayManager`, `ZMQHeartbeatManager`, `DeadMansSwitchWatchdog`, and `SubprocessBroker`.
"""

from __future__ import annotations

import atexit
import ctypes
import hashlib
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

if platform.system() == "Windows":
    from ctypes import wintypes

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

try:
    from cochem_base.exceptions import DiskQuotaError
except ImportError:
    class DiskQuotaError(OSError):  # type: ignore
        """Fallback definition for DiskQuotaError if cochem_base.exceptions is unavailable."""
        default_error_code = "DISK_QUOTA_EXCEEDED"

        def __init__(
            self,
            message: Optional[Union[str, float]] = None,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            timestamp: Optional[str] = None,
            *,
            required_gb: Optional[float] = None,
            available_gb: Optional[float] = None,
            path: Optional[Union[str, Path]] = None,
            **kwargs: Any,
        ) -> None:
            self.required_gb: float = float(required_gb) if required_gb is not None else 50.0
            self.available_gb: float = float(available_gb) if available_gb is not None else 0.0
            self.path: Optional[Path] = Path(path) if path is not None else None
            p_str = str(self.path) if self.path is not None else "workspace"
            msg = message if isinstance(message, str) else (
                f"Insufficient scratch disk quota at {p_str}: "
                f"required {self.required_gb:.2f} GB, available {self.available_gb:.2f} GB"
            )
            super().__init__(msg)

from cochem_base.config_loader import (
    get_artifact_dir,
    get_ramdisk_dir,
    get_runtime_dir,
    resolve_mapped_path,
)

try:
    from core_engine.cochem_core_telemetry_logger import TelemetryLogger
except ImportError:
    try:
        from cochem_core_telemetry_logger import TelemetryLogger  # type: ignore
    except ImportError:
        TelemetryLogger = None  # type: ignore

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Broker")

# Global Popen process tracking for zombie sweeping
_GLOBAL_ACTIVE_POPEN_PROCESSES: List[subprocess.Popen] = []
_GLOBAL_TRACKING_LOCK = threading.RLock()


# =====================================================================
# Win32 Job Object Definitions (Windows-only)
# =====================================================================

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001
PROCESS_ALL_ACCESS = 0x1F0FFF


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


class WindowsJobObject:
    """Encapsulates a Win32 Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.

    Guarantees OS-level atomic termination of all child and spawned grandchild
    processes when the job object handle is closed or the parent crashes.
    """

    def __init__(self, kill_on_close: bool = True) -> None:
        self.handle: Optional[int] = None
        self._is_windows = platform.system() == "Windows"
        if not self._is_windows:
            return

        try:
            self.handle = ctypes.windll.kernel32.CreateJobObjectW(None, None)
            if not self.handle:
                logger.warning("Failed to create Win32 Job Object.")
                return

            if kill_on_close:
                info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                res = ctypes.windll.kernel32.SetInformationJobObject(
                    self.handle,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info),
                )
                if not res:
                    logger.warning("Failed to set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on Job Object.")
        except Exception as exc:
            logger.warning(f"Error initializing WindowsJobObject: {exc}")
            self.handle = None

    def assign_pid(self, pid: int) -> bool:
        """Assigns an active process PID to the Win32 Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            proc_handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_SET_QUOTA | PROCESS_TERMINATE,
                False,
                pid,
            )
            if not proc_handle:
                proc_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not proc_handle:
                return False

            res = ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, proc_handle)
            ctypes.windll.kernel32.CloseHandle(proc_handle)
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to assign PID {pid} to Job Object: {exc}")
            return False

    def assign_popen(self, proc: subprocess.Popen) -> bool:
        """Assigns a subprocess.Popen instance to the Win32 Job Object."""
        return self.assign_pid(proc.pid)

    def set_kill_on_close(self, enable: bool = True) -> bool:
        """Dynamically enables or disables JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE on the Job Object."""
        if not self._is_windows or not self.handle:
            return False
        try:
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE if enable else 0
            res = ctypes.windll.kernel32.SetInformationJobObject(
                self.handle,
                JobObjectExtendedLimitInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            return bool(res)
        except Exception as exc:
            logger.debug(f"Failed to update Job Object limit flags: {exc}")
            return False

    def close(self) -> None:
        """Closes the Job Object handle, terminating all assigned processes if kill_on_close is set."""
        if self._is_windows and self.handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self.handle)
            except Exception:
                pass
            self.handle = None

    def __enter__(self) -> WindowsJobObject:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# =====================================================================
# Process Tracking and Zombie Reaper
# =====================================================================

def get_active_popen_processes() -> List[subprocess.Popen]:
    """Returns a list of currently running subprocess.Popen processes tracked globally."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        return list(_GLOBAL_ACTIVE_POPEN_PROCESSES)


def register_popen_process(proc: subprocess.Popen) -> None:
    """Registers a Popen child process for automatic zombie cleanup on script exit."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
        if proc.poll() is None and proc not in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.append(proc)


def unregister_popen_process(proc: subprocess.Popen) -> None:
    """Unregisters a Popen child process from global tracking."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    with _GLOBAL_TRACKING_LOCK:
        if proc in _GLOBAL_ACTIVE_POPEN_PROCESSES:
            _GLOBAL_ACTIVE_POPEN_PROCESSES.remove(proc)


def kill_process_tree(pid: int, timeout: float = 3.0) -> None:
    """Terminates a process and all of its recursive child processes."""
    if HAS_PSUTIL:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            try:
                parent.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            procs_to_wait = [p for p in children + [parent] if psutil.pid_exists(p.pid)]
            if procs_to_wait:
                gone, alive = psutil.wait_procs(procs_to_wait, timeout=timeout)
                for p in alive:
                    try:
                        p.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except (ProcessLookupError, PermissionError, OSError):
            pass
    else:
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            elif hasattr(os, "killpg") and hasattr(os, "getpgid"):
                try:
                    getpgid_fn = getattr(os, "getpgid", None)
                    killpg_fn = getattr(os, "killpg", None)
                    if getpgid_fn is not None and killpg_fn is not None:
                        killpg_fn(getpgid_fn(pid), signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def cleanup_zombie_processes() -> int:
    """Atexit / Signal hook to terminate any dangling Popen child process trees."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    count = 0
    with _GLOBAL_TRACKING_LOCK:
        active_list = list(_GLOBAL_ACTIVE_POPEN_PROCESSES)
        _GLOBAL_ACTIVE_POPEN_PROCESSES.clear()

    for proc in active_list:
        if proc.poll() is None:
            try:
                pid = proc.pid
                kill_process_tree(pid)
                count += 1
                logger.info(f"Terminated background child process PID {pid}")
            except (ProcessLookupError, PermissionError, OSError) as e:
                logger.warning(f"Failed to terminate process PID {proc.pid}: {e}")
    return count


class ZombieReaper:
    """Global and instance zombie sweeper with signal handlers and Win32 Job Object integration."""

    @staticmethod
    def reap_all() -> int:
        """Invokes global process cleanup."""
        return cleanup_zombie_processes()

    @staticmethod
    def reap_pid(pid: int, timeout: float = 3.0) -> None:
        """Kills a specific process tree."""
        kill_process_tree(pid, timeout=timeout)


def _signal_cleanup_handler(signum: int, frame: Any) -> None:
    logger.info(f"Received signal {signum}. Triggering zombie reaper cleanup...")
    cleanup_zombie_processes()
    sys.exit(128 + signum)


def _register_signal_handlers() -> None:
    try:
        if threading.current_thread() is threading.main_thread():
            for sig_name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
                if hasattr(signal, sig_name):
                    sig = getattr(signal, sig_name)
                    try:
                        signal.signal(sig, _signal_cleanup_handler)
                    except (ValueError, OSError, RuntimeError):
                        pass
    except Exception:
        pass


atexit.register(cleanup_zombie_processes)
_register_signal_handlers()


# =====================================================================
# NUMA-Aware Hardware Thread-Pinning & Oversubscription Prevention
# =====================================================================

def detect_cpu_topology() -> Dict[str, Any]:
    """Evaluates physical host CPU topology (cores, sockets, NUMA nodes).

    Returns a structured dictionary containing logical cores, physical cores,
    sockets, NUMA nodes with mapped CPU core IDs, and multi-threading ratio.
    """
    logical_cores = psutil.cpu_count(logical=True) if HAS_PSUTIL else (os.cpu_count() or 1)
    physical_cores = (psutil.cpu_count(logical=False) if HAS_PSUTIL else None) or logical_cores

    numa_nodes: List[Dict[str, Any]] = []
    sockets = 1

    if platform.system() == "Linux":
        node_dir = Path("/sys/devices/system/node")
        if node_dir.is_dir():
            for entry in sorted(node_dir.glob("node[0-9]*")):
                try:
                    node_id = int(entry.name.replace("node", ""))
                    cpulist_file = entry / "cpulist"
                    cpus: List[int] = []
                    if cpulist_file.exists():
                        raw = cpulist_file.read_text(encoding="utf-8").strip()
                        for part in raw.split(","):
                            if "-" in part:
                                start, end = map(int, part.split("-"))
                                cpus.extend(range(start, end + 1))
                            elif part.isdigit():
                                cpus.append(int(part))
                    numa_nodes.append({"node_id": node_id, "cpus": cpus})
                except Exception:
                    pass
            if numa_nodes:
                sockets = max(1, len(numa_nodes))

    elif platform.system() == "Windows":
        try:
            highest_node = wintypes.ULONG()
            if ctypes.windll.kernel32.GetNumaHighestNodeNumber(ctypes.byref(highest_node)):
                total_nodes = highest_node.value + 1
                sockets = max(1, total_nodes)
                cores_per_node = max(1, logical_cores // total_nodes)
                for nid in range(total_nodes):
                    node_cpus = list(range(nid * cores_per_node, min(logical_cores, (nid + 1) * cores_per_node)))
                    numa_nodes.append({"node_id": nid, "cpus": node_cpus})
        except Exception:
            pass

    if not numa_nodes:
        numa_nodes.append({"node_id": 0, "cpus": list(range(logical_cores))})
        sockets = 1

    return {
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "sockets": sockets,
        "numa_nodes": numa_nodes,
        "is_numa": len(numa_nodes) > 1,
        "threads_per_core": max(1, logical_cores // max(1, physical_cores)),
    }


class CPUTopologyManager:
    """Evaluates physical host topology (cores, sockets, NUMA nodes) and manages core allocations."""

    def __init__(self, topology: Optional[Dict[str, Any]] = None) -> None:
        self.topology = topology or detect_cpu_topology()
        self.logical_cores: int = self.topology.get("logical_cores", 1)
        self.physical_cores: int = self.topology.get("physical_cores", 1)
        self.sockets: int = self.topology.get("sockets", 1)
        self.numa_nodes: List[Dict[str, Any]] = self.topology.get("numa_nodes", [])
        self.is_numa: bool = self.topology.get("is_numa", False)

    def get_topology(self) -> Dict[str, Any]:
        """Returns cached CPU topology specification."""
        return dict(self.topology)

    def get_numa_node_for_core(self, core_id: int) -> int:
        """Determines the NUMA node index for a given CPU core."""
        for node in self.numa_nodes:
            if core_id in node.get("cpus", []):
                return int(node.get("node_id", 0))
        return 0

    def allocate_cores(self, count: int, numa_node: Optional[int] = None) -> List[int]:
        """Allocates contiguous CPU cores respecting NUMA node boundaries."""
        if numa_node is not None:
            for node in self.numa_nodes:
                if node.get("node_id") == numa_node:
                    cpus: List[int] = list(node.get("cpus", []))
                    return cpus[:count] if count <= len(cpus) else cpus
        all_cpus: List[int] = [c for node in self.numa_nodes for c in node.get("cpus", [])]
        if not all_cpus:
            all_cpus = list(range(self.logical_cores))
        return all_cpus[:count]

    def pin_process(self, pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
        """Pins an active process to designated CPU cores."""
        return enforce_cpu_affinity(pid, cpu_cores)

    def calculate_thread_affinity(self, rank: int, threads_per_rank: int) -> List[int]:
        """Calculates thread pinning offsets for multi-rank execution."""
        start_core = (rank * threads_per_rank) % max(1, self.logical_cores)
        return [(start_core + i) % self.logical_cores for i in range(threads_per_rank)]


def enforce_cpu_affinity(pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
    """Pins a process to specified CPU cores using OS-level affinity control.

    Gracefully handles macOS Darwin (which does not support process CPU affinity)
    and Windows processor group constraints without raising unhandled exceptions.
    """
    if cpu_cores is None or len(cpu_cores) == 0:
        return True
    if not HAS_PSUTIL:
        logger.warning("psutil unavailable; cannot enforce CPU affinity.")
        return False
    try:
        proc = psutil.Process(pid)
        proc.cpu_affinity(cpu_cores)
        logger.info(f"Pinned PID {pid} to CPU cores {cpu_cores} [M]")
        return True
    except (AttributeError, NotImplementedError):
        # Graceful handling for macOS Darwin where cpu_affinity is unsupported
        logger.debug(f"CPU affinity control is not supported on this platform ({platform.system()}).")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError) as e:
        logger.warning(f"Failed to set CPU affinity on PID {pid}: {e}")
        return False


def detect_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    cmd: Optional[Union[str, List[str]]] = None,
) -> bool:
    """Detects if an OpenMPI, MPICH, SLURM, or ORCA multi-rank MPI environment is active."""
    target_env = env if env is not None else os.environ

    # Check for OpenMPI / PMI / SLURM / MPI multi-process variables
    mpi_size_vars = ("OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "SLURM_NTASKS", "MPI_SIZE", "OMPI_UNIVERSE_SIZE", "MV2_COMM_WORLD_SIZE")
    for var in mpi_size_vars:
        val = target_env.get(var)
        if val is not None:
            try:
                if int(val) > 1:
                    return True
            except ValueError:
                pass

    mpi_rank_indicators = ("MPI_LOCALRANKID", "OMPI_COMM_WORLD_RANK", "PMI_RANK", "PMIX_RANK", "SLURM_PROCID")
    for var in mpi_rank_indicators:
        if var in target_env:
            return True

    mpirun_in_use = target_env.get("MPIRUN_IN_USE", "").strip().lower()
    if mpirun_in_use in ("1", "true", "yes"):
        return True

    # Inspect command line for MPI runners or multi-rank flags
    if cmd is not None:
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        cmd_lower = cmd_str.lower()
        mpi_executables = ("mpirun", "mpiexec", "orterun", "srun", "aprun", "oshrun")
        for mpi_bin in mpi_executables:
            parts = cmd_lower.split()
            if mpi_bin in parts or any(part.endswith(f"/{mpi_bin}") or part.endswith(f"\\{mpi_bin}") or part.endswith(f"/{mpi_bin}.exe") or part.endswith(f"\\{mpi_bin}.exe") for part in parts):
                return True
        if "%pal" in cmd_lower or "nprocs" in cmd_lower:
            return True

    return False


def sanitize_mpi_environment(
    env: Optional[Dict[str, str]] = None,
    force_single_thread: bool = False,
    cmd: Optional[Union[str, List[str]]] = None,
) -> Dict[str, str]:
    """Sanitizes environment variables for MPI workloads to prevent core oversubscription.

    When multi-rank MPI execution is detected or force_single_thread is True, forces:
    OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
    VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1", BLIS_NUM_THREADS="1".
    """
    target_env = dict(env) if env is not None else os.environ.copy()

    if force_single_thread or detect_mpi_environment(target_env, cmd=cmd):
        target_env["OMP_NUM_THREADS"] = "1"
        target_env["MKL_NUM_THREADS"] = "1"
        target_env["OPENBLAS_NUM_THREADS"] = "1"
        target_env["VECLIB_MAXIMUM_THREADS"] = "1"
        target_env["NUMEXPR_NUM_THREADS"] = "1"
        target_env["BLIS_NUM_THREADS"] = "1"
        logger.info("Sanitized MPI environment: forced OMP/MKL/OPENBLAS/VECLIB/NUMEXPR/BLIS=1 to prevent oversubscription.")

    return target_env


# =====================================================================
# Pre-Flight Disk Quota, 64KB SHA-256 Probe & RAM-Disk Routing
# =====================================================================

def lock_directory_permissions(target_dir: Union[str, Path]) -> bool:
    """Applies strict directory access controls: chmod 0o700 on POSIX or icacls on Windows."""
    path = Path(target_dir).resolve()
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Could not create directory {path} to lock permissions: {exc}")
            return False

    if platform.system() != "Windows":
        try:
            os.chmod(str(path), 0o700)
            return True
        except OSError as exc:
            logger.warning(f"Failed to chmod 0o700 on {path}: {exc}")
            return False
    else:
        try:
            username = os.environ.get("USERNAME") or os.environ.get("USER") or "Everyone"
            cmd = ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(OI)(CI)F"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5.0)
            return res.returncode == 0
        except Exception as exc:
            logger.warning(f"Failed to lock Windows ACLs on {path}: {exc}")
            return False


def verify_scratch_quota_and_io(target_dir: Union[str, Path], required_gb: float = 50.0) -> bool:
    """Executes pre-flight storage quota assertion and 64KB unbuffered SHA-256 binary probe.

    Raises DiskQuotaError if available storage is less than required_gb.
    Raises IOError if binary readback SHA-256 checksum fails.
    """
    target_path = Path(target_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    usage = shutil.disk_usage(str(target_path))
    free_gb = usage.free / (1024 ** 3)

    if free_gb < required_gb:
        logger.error(f"Insufficient scratch disk space at {target_path}: {free_gb:.2f} GB free, {required_gb:.2f} GB required.")
        raise DiskQuotaError(required_gb=required_gb, available_gb=free_gb, path=target_path)

    probe_file = target_path / f".cochem_io_probe_{os.getpid()}_{int(time.time() * 1000)}.tmp"
    probe_data = os.urandom(64 * 1024)  # 64 KB physical binary probe
    expected_hash = hashlib.sha256(probe_data).hexdigest()

    try:
        with open(probe_file, "wb") as f:
            f.write(probe_data)
            f.flush()
            os.fsync(f.fileno())

        with open(probe_file, "rb") as f:
            read_back_data = f.read()

        read_hash = hashlib.sha256(read_back_data).hexdigest()

        if expected_hash != read_hash:
            raise IOError(f"Scratch I/O integrity probe failed: SHA-256 mismatch at {target_path}")

        logger.info(f"Verified scratch quota and I/O at {target_path} ({free_gb:.2f} GB free, {required_gb:.2f} GB required) [M]")
        return True
    except (OSError, IOError) as exc:
        logger.error(f"Scratch I/O verification error at {target_path}: {exc}")
        raise
    finally:
        probe_file.unlink(missing_ok=True)


def verify_scratch_io(scratch_dir: Union[str, Path], required_mb: int = 100) -> bool:
    """Backward-compatible scratch I/O verification wrapper."""
    required_gb = required_mb / 1024.0
    try:
        return verify_scratch_quota_and_io(scratch_dir, required_gb=required_gb)
    except (DiskQuotaError, IOError, OSError):
        return False


class RAMDiskOverlayManager:
    """Manages high-speed RAM-disk execution overlays and quantum artifact provenance synchronization."""

    def __init__(self, threshold_ram_gb: float = 128.0) -> None:
        self.threshold_ram_gb = threshold_ram_gb

    def get_total_host_ram_gb(self) -> float:
        """Returns physical host memory in Gigabytes."""
        if HAS_PSUTIL:
            total_bytes: float = float(psutil.virtual_memory().total)
            return float(total_bytes / (1024 ** 3))
        return 0.0

    def is_ramdisk_eligible(self, min_ram_gb: Optional[float] = None) -> bool:
        """Checks if host RAM exceeds the minimum provisioning threshold."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        return self.get_total_host_ram_gb() >= threshold

    def provision_overlay(
        self,
        job_name: str,
        required_gb: float = 4.0,
        min_ram_gb: Optional[float] = None,
        fallback_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Autonomously provisions a high-speed RAM-disk overlay directory if eligible."""
        threshold = min_ram_gb if min_ram_gb is not None else self.threshold_ram_gb
        target_fallback = Path(fallback_dir).resolve() if fallback_dir is not None else (get_artifact_dir() / "Scratch")

        if self.is_ramdisk_eligible(threshold):
            ramdisk_path = get_ramdisk_dir()
            if ramdisk_path is not None and ramdisk_path.is_dir():
                try:
                    free_gb = shutil.disk_usage(str(ramdisk_path)).free / (1024 ** 3)
                    if free_gb > (required_gb * 1.2):
                        job_overlay_dir = ramdisk_path / f"cochem_{job_name}_{int(time.time() * 1000)}"
                        job_overlay_dir.mkdir(parents=True, exist_ok=True)
                        lock_directory_permissions(job_overlay_dir)
                        logger.info(
                            f"Provisioned RAM-disk execution directory: {job_overlay_dir} "
                            f"(Host RAM: {self.get_total_host_ram_gb():.1f} GB >= {threshold} GB)"
                        )
                        return job_overlay_dir
                except Exception as exc:
                    logger.debug(f"RAM-disk overlay check skipped: {exc}")

        target_fallback.mkdir(parents=True, exist_ok=True)
        lock_directory_permissions(target_fallback)
        return target_fallback

    def sync_and_cleanup(self, overlay_path: Path, permanent_path: Path) -> Dict[str, str]:
        """Synchronizes quantum artifacts from overlay back to permanent workspace and deletes overlay."""
        permanent_path.mkdir(parents=True, exist_ok=True)
        hashes: Dict[str, str] = {}

        if overlay_path != permanent_path and overlay_path.exists():
            logger.info(f"Syncing artifacts from RAM-disk {overlay_path} to permanent workspace {permanent_path}...")
            for item in overlay_path.iterdir():
                dest_path = permanent_path / item.name
                try:
                    if item.is_dir():
                        shutil.copytree(item, dest_path, dirs_exist_ok=True)
                    elif item.is_file():
                        shutil.copy2(item, dest_path)
                except Exception as exc:
                    logger.warning(f"Error copying artifact {item} to {dest_path}: {exc}")

            hashes = self.hash_artifacts(permanent_path)
            shutil.rmtree(overlay_path, ignore_errors=True)
        else:
            hashes = self.hash_artifacts(permanent_path)

        return hashes

    @staticmethod
    def hash_artifacts(target_dir: Path) -> Dict[str, str]:
        """Generates SHA-256 checksums for quantum chemistry artifacts."""
        hashes: Dict[str, str] = {}
        if not target_dir.exists():
            return hashes

        valid_suffixes = {".out", ".gbw", ".xyz", ".log", ".dat", ".json", ".h5", ".molden", ".cube"}
        for file_path in sorted(target_dir.iterdir()):
            if file_path.is_file() and (file_path.suffix in valid_suffixes or file_path.name.endswith(".out")):
                try:
                    hasher = hashlib.sha256()
                    with open(file_path, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    file_hash = hasher.hexdigest()
                    hashes[file_path.name] = file_hash
                    logger.info(f"Generated SHA-256 hash for {file_path.name}: {file_hash} [M]")
                except OSError as err:
                    logger.warning(f"Failed to hash {file_path.name}: {err}")
        return hashes


# =====================================================================
# ZeroMQ Heartbeat Integration & Dead-Man's Switch Watchdog
# =====================================================================

class ZMQHeartbeatManager:
    """ZeroMQ heartbeat publisher with CurveZMQ security on Windows and IPC on POSIX."""

    def __init__(self, job_id: str = "cochem_job") -> None:
        self.job_id = job_id
        self.endpoint: Optional[str] = None
        self.server_public: Optional[bytes] = None
        self.server_secret: Optional[bytes] = None
        self.client_public: Optional[bytes] = None
        self.client_secret: Optional[bytes] = None
        self.curve_enabled: bool = False

        self._context: Optional[Any] = None
        self._socket: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(
        self,
        endpoint: Optional[str] = None,
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        use_curve: bool = True,
    ) -> str:
        """Binds and starts the background heartbeat publisher."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return ""

        self.stop()
        self._stop_event.clear()

        try:
            self._context = zmq.Context()
            self._socket = self._context.socket(zmq.PUB)

            if endpoint is None:
                if platform.system() == "Windows":
                    if use_curve and hasattr(zmq, "curve_keypair"):
                        try:
                            self.server_public, self.server_secret = zmq.curve_keypair()
                            self.client_public, self.client_secret = zmq.curve_keypair()
                            self._socket.curve_secretkey = self.server_secret
                            self._socket.curve_publickey = self.server_public
                            self._socket.curve_server = True
                            self.curve_enabled = True
                        except Exception as curve_err:
                            logger.debug(f"CurveZMQ initialization fallback: {curve_err}")
                            self.curve_enabled = False

                    port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                    self.endpoint = f"tcp://127.0.0.1:{port}"
                else:
                    try:
                        ipc_dir = get_runtime_dir() / "ipc"
                    except Exception:
                        ipc_dir = Path(tempfile.gettempdir()) / "cochem_ipc"
                    ipc_dir.mkdir(parents=True, exist_ok=True)
                    lock_directory_permissions(ipc_dir)
                    ipc_path = ipc_dir / f"cochem_heartbeat_{self.job_id}.ipc"
                    self.endpoint = f"ipc://{ipc_path}"
                    try:
                        self._socket.bind(self.endpoint)
                    except Exception:
                        # Fallback to loopback TCP if IPC is unsupported in sandbox
                        port = self._socket.bind_to_random_port("tcp://127.0.0.1")
                        self.endpoint = f"tcp://127.0.0.1:{port}"
            else:
                if endpoint.endswith(":*"):
                    base = endpoint[:-2]
                    port = self._socket.bind_to_random_port(base)
                    self.endpoint = f"{base}:{port}"
                else:
                    self.endpoint = endpoint
                    self._socket.bind(self.endpoint)

        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat publisher socket: {err}", exc_info=True)
            self.stop()
            return ""

        def heartbeat_worker() -> None:
            while not self._stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "job_id": self.job_id,
                    "metadata": metadata or {},
                }
                try:
                    if self._socket is not None:
                        self._socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat publish error: {ex}")
                self._stop_event.wait(interval_sec)

        self._thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._thread.start()
        logger.info(f"ZeroMQ heartbeat publisher started on {self.endpoint} [M]")
        return self.endpoint or ""

    def publish_heartbeat(self, status: str = "alive", extra: Optional[Dict[str, Any]] = None) -> None:
        """Publishes an immediate heartbeat frame."""
        if self._socket is None or not HAS_ZMQ:
            return
        payload: Dict[str, Any] = {
            "status": status,
            "timestamp": time.time(),
            "pid": os.getpid(),
            "job_id": self.job_id,
            "extra": extra or {},
        }
        try:
            self._socket.send_multipart([
                b"heartbeat",
                json.dumps(payload).encode("utf-8"),
            ])
        except Exception as exc:
            logger.debug(f"Error publishing direct heartbeat: {exc}")

    def stop(self) -> None:
        """Stops the heartbeat worker and cleans up ZeroMQ sockets."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._socket is not None:
            try:
                self._socket.close(linger=0)
            except Exception:
                pass
            self._socket = None
        if self._context is not None:
            try:
                self._context.term()
            except Exception:
                pass
            self._context = None
        if self.endpoint and self.endpoint.startswith("ipc://"):
            try:
                raw_ipc_path = self.endpoint.replace("ipc://", "")
                Path(raw_ipc_path).unlink(missing_ok=True)
            except Exception:
                pass

    def __enter__(self) -> ZMQHeartbeatManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


class DeadMansSwitchWatchdog:
    """Background watchdog monitoring heartbeats to safeguard against orchestrator disconnection.

    If timeout expires and the child process is running, transitions the job
    to a detached daemon mode without killing the physics calculation.
    """

    def __init__(
        self,
        job_id: str,
        proc: Optional[subprocess.Popen] = None,
        timeout: float = 60.0,
        check_interval: float = 1.0,
        on_timeout: str = "daemonize",
    ) -> None:
        self.job_id = job_id
        self.proc = proc
        self.timeout = timeout
        self.check_interval = check_interval
        self.on_timeout = on_timeout
        self.last_ping: float = time.time()
        self.is_daemonized: bool = False

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def ping(self) -> None:
        """Resets the dead-man's switch expiration timer."""
        self.last_ping = time.time()

    def start(self) -> None:
        """Starts the watchdog monitor thread."""
        self._stop_event.clear()
        self.last_ping = time.time()

        def watchdog_loop() -> None:
            while not self._stop_event.is_set():
                elapsed = time.time() - self.last_ping
                if elapsed > self.timeout:
                    if self.proc is not None and self.proc.poll() is None:
                        if self.on_timeout == "daemonize":
                            self.is_daemonized = True
                            # Unregister process from active reaper tracking so it is not killed on parent exit
                            unregister_popen_process(self.proc)
                            logger.warning(
                                f"Dead-man's switch triggered for job '{self.job_id}' (PID {self.proc.pid}). "
                                f"No heartbeat received in {elapsed:.1f}s. "
                                f"Transitioning job to detached background daemon to allow physics completion."
                            )
                        elif self.on_timeout == "kill":
                            logger.error(
                                f"Dead-man's switch triggered for job '{self.job_id}' (PID {self.proc.pid}). "
                                f"No heartbeat received in {elapsed:.1f}s. Terminating process tree."
                            )
                            kill_process_tree(self.proc.pid)
                    break
                self._stop_event.wait(self.check_interval)

        self._thread = threading.Thread(target=watchdog_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the watchdog monitor thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> DeadMansSwitchWatchdog:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()


# =====================================================================
# Safe Subprocess Execution
# =====================================================================

def safe_subprocess_run(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
    cpu_affinity: Optional[List[int]] = None,
    required_disk_gb: Optional[float] = None,
    sanitize_mpi: bool = True,
    use_job_object: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Executes a subprocess safely with explicit check, timeout, explicit cwd validation,

    MPI oversubscription sanitization, pre-flight disk quota assertion, hardware CPU affinity pinning,
    Win32 Job Object binding, global tracking registration, and robust exception handling.
    """
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise FileNotFoundError(f"Subprocess working directory does not exist: {cwd_path}")
        cwd_str = str(cwd_path)
    else:
        cwd_str = None
        cwd_path = Path.cwd()

    if required_disk_gb is not None and required_disk_gb > 0:
        verify_scratch_quota_and_io(cwd_path, required_gb=required_disk_gb)

    parsed_cmd: Union[List[str], str]
    if isinstance(cmd, str) and not kwargs.get("shell", False):
        if platform.system() == "Windows":
            parsed_cmd = cmd
        else:
            parsed_cmd = shlex.split(cmd, posix=True)
    else:
        parsed_cmd = cmd

    target_env = env.copy() if env is not None else os.environ.copy()
    if sanitize_mpi:
        target_env = sanitize_mpi_environment(target_env, cmd=parsed_cmd)

    popen_args: Dict[str, Any] = {
        "cwd": cwd_str,
        "env": target_env,
        "text": text,
        **kwargs,
    }
    if capture_output:
        popen_args["stdout"] = subprocess.PIPE
        popen_args["stderr"] = subprocess.PIPE

    job_obj = WindowsJobObject() if (use_job_object and platform.system() == "Windows") else None

    proc = subprocess.Popen(parsed_cmd, **popen_args)
    register_popen_process(proc)

    if job_obj is not None:
        job_obj.assign_popen(proc)

    if cpu_affinity is not None:
        enforce_cpu_affinity(proc.pid, cpu_affinity)

    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
        ret = proc.returncode
        if check and ret != 0:
            raise subprocess.CalledProcessError(ret, cmd, output=stdout_data, stderr=stderr_data)
        return subprocess.CompletedProcess(args=cmd, returncode=ret, stdout=stdout_data, stderr=stderr_data)
    except subprocess.TimeoutExpired:
        kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            pass
        logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess '{cmd}' failed with returncode {e.returncode}: {e.stderr}")
        raise
    except OSError as e:
        logger.error(f"Subprocess execution error for '{cmd}': {e}")
        raise
    finally:
        unregister_popen_process(proc)
        if job_obj is not None:
            job_obj.close()


# =====================================================================
# Subprocess Broker Core Engine
# =====================================================================

class SubprocessBroker:
    """Subprocess execution manager for computational quantum chemistry workloads.

    Handles process lifecycles, memory safety, heartbeats, dead-man's switch watchdogs,
    RAM-disk overlays, CPU affinity pinning, and artifact provenance hashing.
    """

    def __init__(
        self,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        memory_limit_gb: float = 8.0,
        total_ram_threshold_gb: float = 128.0,
    ) -> None:
        default_work_dir = get_artifact_dir() / "Scratch"
        self.cwd = resolve_mapped_path(cwd, default_work_dir) if cwd is not None else default_work_dir
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.env = env if env is not None else os.environ.copy()
        self.memory_limit_bytes = memory_limit_gb * (1024 ** 3)
        self.total_ram_threshold_gb = total_ram_threshold_gb

        self.topology_manager = CPUTopologyManager()
        self.ramdisk_manager = RAMDiskOverlayManager(threshold_ram_gb=total_ram_threshold_gb)

        if TelemetryLogger is not None:
            self.telemetry: Optional[Any] = TelemetryLogger()
        else:
            self.telemetry = None

        self.active_processes: List[subprocess.Popen] = []
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # ZeroMQ heartbeat publisher components
        self.heartbeat_manager: Optional[ZMQHeartbeatManager] = None
        self._zmq_thread: Optional[threading.Thread] = None
        self._zmq_stop_event = threading.Event()
        self._zmq_context: Optional[Any] = None
        self._zmq_socket: Optional[Any] = None

        # Register instance reaper
        self._atexit_reaper = atexit.register(self.execute_zombie_reaper)

    def __enter__(self) -> SubprocessBroker:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Stops background monitors and reaps lingering subprocesses."""
        self.stop_oom_monitor()
        self.stop_zmq_heartbeat()
        if self.heartbeat_manager is not None:
            self.heartbeat_manager.stop()
            self.heartbeat_manager = None
        self.execute_zombie_reaper()
        try:
            atexit.unregister(self.execute_zombie_reaper)
        except Exception:
            pass

    def verify_scratch_io(self, target_dir: Optional[Union[str, Path]] = None, required_mb: int = 100) -> bool:
        """Verifies read/write availability on the current working scratch directory or specific target."""
        check_dir = target_dir if target_dir is not None else self.cwd
        return verify_scratch_io(check_dir, required_mb=required_mb)

    def verify_scratch_quota_and_io(self, target_dir: Optional[Union[str, Path]] = None, required_gb: float = 50.0) -> bool:
        """Verifies storage quota and physical 64KB I/O responsiveness."""
        check_dir = target_dir if target_dir is not None else self.cwd
        return verify_scratch_quota_and_io(check_dir, required_gb=required_gb)

    def _allocate_scratch_space(self, job_name: str, required_mb: int = 4000) -> Path:
        """Allocate a mapped host RAM disk when available and threshold is met, falling back to workspace."""
        required_gb = required_mb / 1024.0
        return self.ramdisk_manager.provision_overlay(
            job_name=job_name,
            required_gb=required_gb,
            min_ram_gb=self.total_ram_threshold_gb,
            fallback_dir=self.cwd,
        )

    def start_oom_monitor(self, check_interval: float = 2.0, threshold_mb: float = 1024.0) -> None:
        """Background thread checking system RAM and broker process tree to preemptively kill before panic."""
        if not HAS_PSUTIL:
            logger.warning("psutil not available. OOM Preemption disabled.")
            return

        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        threshold_bytes = threshold_mb * (1024 * 1024)

        def monitor_loop() -> None:
            while not self._stop_event.is_set():
                try:
                    mem = psutil.virtual_memory()
                    if mem.available < threshold_bytes:
                        logger.error(f"CRITICAL OOM IMMINENT. Available RAM: {mem.available / 1e6:.1f} MB")
                        self.execute_zombie_reaper()
                    else:
                        with self._lock:
                            active_pids = [p.pid for p in self.active_processes if p.poll() is None]
                        total_rss = 0
                        for pid in active_pids:
                            try:
                                proc = psutil.Process(pid)
                                total_rss += proc.memory_info().rss
                                for child in proc.children(recursive=True):
                                    total_rss += child.memory_info().rss
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        if total_rss > self.memory_limit_bytes:
                            logger.error(
                                f"Broker process tree memory exceeded limit: {total_rss / 1e6:.1f} MB > "
                                f"{self.memory_limit_bytes / 1e6:.1f} MB. Preempting active processes."
                            )
                            self.execute_zombie_reaper()
                except Exception as exc:
                    logger.debug(f"OOM poll error: {exc}")
                self._stop_event.wait(check_interval)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_oom_monitor(self) -> None:
        """Stops the active OOM preemption monitor thread."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None

    def start_zmq_heartbeat(
        self,
        port: int = 5557,
        host: str = "127.0.0.1",
        interval_sec: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Starts a background ZeroMQ PUB heartbeat publisher emitting telemetry metadata."""
        if not HAS_ZMQ:
            logger.warning("ZeroMQ (pyzmq) not available. Heartbeat publisher disabled.")
            return

        self.stop_zmq_heartbeat()
        self._zmq_stop_event.clear()

        try:
            self._zmq_context = zmq.Context()
            self._zmq_socket = self._zmq_context.socket(zmq.PUB)
            self._zmq_socket.bind(f"tcp://{host}:{port}")
        except Exception as err:
            logger.error(f"Failed to bind ZeroMQ heartbeat socket on {host}:{port}: {err}")
            self.stop_zmq_heartbeat()
            return

        def heartbeat_worker() -> None:
            while not self._zmq_stop_event.is_set():
                alive_payload: Dict[str, Any] = {
                    "status": "alive",
                    "timestamp": time.time(),
                    "pid": os.getpid(),
                    "active_processes": len(self.active_processes),
                    "metadata": metadata or {},
                }
                try:
                    if self._zmq_socket is not None:
                        self._zmq_socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8"),
                        ])
                except Exception as ex:
                    logger.debug(f"ZeroMQ heartbeat send error: {ex}")
                self._zmq_stop_event.wait(interval_sec)

        self._zmq_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        self._zmq_thread.start()
        logger.info(f"ZeroMQ heartbeat publisher started on tcp://{host}:{port} [M]")

    def stop_zmq_heartbeat(self) -> None:
        """Stops the ZeroMQ heartbeat publisher and releases socket resources."""
        self._zmq_stop_event.set()
        if self._zmq_thread is not None:
            self._zmq_thread.join(timeout=2.0)
            self._zmq_thread = None
        if self._zmq_socket is not None:
            try:
                self._zmq_socket.close(linger=0)
            except Exception:
                pass
            self._zmq_socket = None
        if self._zmq_context is not None:
            try:
                self._zmq_context.term()
            except Exception:
                pass
            self._zmq_context = None

    def execute_zombie_reaper(self) -> int:
        """Hard kills all managed subprocesses and their orphaned children."""
        count = 0
        with self._lock:
            procs = list(self.active_processes)
            self.active_processes.clear()

        if not procs:
            return 0

        logger.info("Executing SubprocessBroker Zombie Reaper Protocol...")
        for proc in procs:
            if proc.poll() is None:
                try:
                    pid = proc.pid
                    kill_process_tree(pid)
                    unregister_popen_process(proc)
                    count += 1
                    logger.info(f"Reaped managed process tree PID {pid}")
                except (ProcessLookupError, PermissionError, OSError) as e:
                    logger.warning(f"Reaper failed on PID {proc.pid}: {e}")
            else:
                unregister_popen_process(proc)

        return count

    def garbage_collect_core_dumps(self, execution_dir: Optional[Union[str, Path]] = None) -> int:
        """Sweeps massive binary core.* files generated by Fortran segfaults."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        count = 0
        if not target_dir.exists():
            return 0
        for file in target_dir.glob("core.*"):
            if file.is_file():
                try:
                    file.unlink()
                    count += 1
                except OSError as err:
                    logger.debug(f"Unable to unlink core file {file}: {err}")
        if count > 0:
            logger.info(f"Garbage collection swept {count} binary dump(s).")
        return count

    def hash_quantum_artifacts(self, execution_dir: Optional[Union[str, Path]] = None) -> Dict[str, str]:
        """Calculates SHA-256 cryptographic provenance digests for all quantum chemistry artifacts."""
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        return RAMDiskOverlayManager.hash_artifacts(target_dir)

    def execute(
        self,
        payload_command: Union[str, List[str]],
        job_name: str = "cochem_job",
        timeout: Optional[float] = None,
        cpu_affinity: Optional[List[int]] = None,
        required_disk_gb: float = 0.05,
        dead_man_timeout: float = 60.0,
        daemonize_on_timeout: bool = True,
    ) -> int:
        """Dispatches an execution payload in an isolated process group with telemetry monitoring.

        Allocates high-speed RAM-disk if available, executes payload with dead-man's switch watchdog,
        enforces timeout, streams stdout/stderr, and copies artifacts back upon completion.
        """
        exec_path = self._allocate_scratch_space(job_name)
        verify_scratch_quota_and_io(exec_path, required_gb=max(0.01, required_disk_gb))

        cmd_str: str
        command: Union[str, List[str]]
        if isinstance(payload_command, str):
            if platform.system() == "Windows":
                command = payload_command
            else:
                command = shlex.split(payload_command, posix=True)
            cmd_str = payload_command
        else:
            command = payload_command
            cmd_str = " ".join(payload_command)

        sanitized_env = sanitize_mpi_environment(self.env, cmd=command)

        logger.info(f"Dispatching '{job_name}' to broker in {exec_path}...")

        stdout_hist: List[str] = []
        stderr_hist: List[str] = []

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(exec_path),
            "env": sanitized_env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if hasattr(os, "setsid") and platform.system() != "Windows":
            popen_kwargs["preexec_fn"] = os.setsid

        process: Optional[subprocess.Popen] = None
        job_obj = WindowsJobObject() if platform.system() == "Windows" else None
        watchdog: Optional[DeadMansSwitchWatchdog] = None
        exit_code: int = 0

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            with self._lock:
                self.active_processes.append(process)
            register_popen_process(process)

            if job_obj is not None:
                job_obj.assign_popen(process)

            if cpu_affinity is not None:
                enforce_cpu_affinity(process.pid, cpu_affinity)

            watchdog = DeadMansSwitchWatchdog(
                job_id=job_name,
                proc=process,
                timeout=dead_man_timeout,
                on_timeout="daemonize" if daemonize_on_timeout else "kill",
            )
            watchdog.start()

            def _stream_stdout() -> None:
                if process and process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        clean_line = line.strip()
                        stdout_hist.append(clean_line)
                        if self.telemetry and not self.telemetry.process_stream_chunk(clean_line):
                            logger.error("Telemetry trap triggered. Preempting process.")
                            kill_process_tree(process.pid)
                            break

            def _stream_stderr() -> None:
                if process and process.stderr:
                    for line in iter(process.stderr.readline, ''):
                        if watchdog:
                            watchdog.ping()
                        stderr_hist.append(line.strip())

            t_stdout = threading.Thread(target=_stream_stdout, daemon=True)
            t_stderr = threading.Thread(target=_stream_stderr, daemon=True)

            t_stdout.start()
            t_stderr.start()

            if timeout is not None and timeout > 0:
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    logger.error(f"Process '{job_name}' timed out after {timeout} seconds.")
                    kill_process_tree(process.pid)
                    try:
                        process.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        pass
                    exit_code = -124
            else:
                process.wait()
                exit_code = process.returncode

            t_stdout.join(timeout=2.0)
            t_stderr.join(timeout=2.0)

        except KeyboardInterrupt:
            logger.error("Keyboard Interrupt. Triggering Reaper.")
            self.execute_zombie_reaper()
            exit_code = -1
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            logger.error(f"Dispatch Exception: {e}")
            self.execute_zombie_reaper()
            exit_code = -2
        finally:
            if watchdog is not None:
                watchdog.stop()

            if job_obj is not None:
                if watchdog is not None and watchdog.is_daemonized:
                    job_obj.set_kill_on_close(False)
                job_obj.close()

            if process is not None:
                with self._lock:
                    if process in self.active_processes:
                        self.active_processes.remove(process)
                unregister_popen_process(process)

            # Compute genuine cryptographic dispatch audit hash
            dispatch_seed = f"{job_name}:{cmd_str}:{exit_code}:{time.time()}".encode('utf-8')
            dispatch_hash = hashlib.sha256(dispatch_seed).hexdigest()

            if self.telemetry:
                self.telemetry.aggregate_and_lock(job_name, stdout_hist, stderr_hist, exit_code, dispatch_hash)

            if not (watchdog is not None and watchdog.is_daemonized):
                self.garbage_collect_core_dumps(exec_path)
                self.ramdisk_manager.sync_and_cleanup(exec_path, self.cwd)
            else:
                logger.info(
                    f"Job '{job_name}' daemonized (PID {process.pid if process else 'N/A'}); "
                    f"preserving execution directory {exec_path} for active background completion."
                )

        return exit_code


__all__ = [
    "SubprocessBroker",
    "safe_subprocess_run",
    "register_popen_process",
    "unregister_popen_process",
    "get_active_popen_processes",
    "cleanup_zombie_processes",
    "kill_process_tree",
    "enforce_cpu_affinity",
    "detect_cpu_topology",
    "CPUTopologyManager",
    "detect_mpi_environment",
    "sanitize_mpi_environment",
    "verify_scratch_io",
    "verify_scratch_quota_and_io",
    "lock_directory_permissions",
    "RAMDiskOverlayManager",
    "ZMQHeartbeatManager",
    "DeadMansSwitchWatchdog",
    "WindowsJobObject",
    "ZombieReaper",
    "DiskQuotaError",
    "HAS_PSUTIL",
    "HAS_ZMQ",
]


if __name__ == "__main__":
    broker = SubprocessBroker()
    logger.info("Broker Initialized and protections armed.")
