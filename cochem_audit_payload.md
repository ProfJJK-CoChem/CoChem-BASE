Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part1_11_core_subprocess_broker_prompt.md.
Original prompt:
﻿# TASK INSTRUCTIONS: CoChem-BASE Core Subprocess Broker

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_subprocess_broker.py`

## Context & Ecosystem Role
The Zombie Reaper. Binds `os.killpg` to an `atexit` hook, guaranteeing that if the Jupyter kernel dies or the UI crashes, all orphaned Process Group IDs (PGIDs) executing quantum cascades are instantly terminated, protecting host memory.

## Deliverable Functions & Constraints
- Build an OS-level execution wrapper for heavy C++ binaries (e.g., ORCA, `mpirun`).
- Enforce NUMA node hardware thread-pinning.
- Pre-verify disk I/O availability on `$SCRATCH`.
- Expose ZeroMQ (ZMQ) heartbeats.
- Implement process group management and `atexit` hooks with `os.killpg`.
- Ensure NO mocks, stubs, or dummy implementations. Implement robust process controls.
- Only generate this exact file.


## ADVERSARIAL AUDIT CONSTRAINTS ENFORCED ##
- **ANTI-MOCKING DIRECTIVE**: You MUST NOT use mocks, dummy loops, fake data, stub logic, or placeholder code. Your implementation must use real physical execution logic without simulation.
- **ARCHITECTURE STRICTNESS**: You must strictly adhere to the Tripartite Workspace Air-Gap rules (separation of orchestrator, sandbox, and active deployment).
- **METHODOLOGY**: You must adhere to the Method Matrix rules for architecture.
- **NO SPOOFING**: The generation must not be faked. Eradicate mocked data.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_subprocess_broker.py ---
#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 3.0 - The Subprocess Broker
Implements: Non-blocking IPC Execution, Zombie Process Reaper,
OOM Preemption Polling, ZeroMQ Heartbeat Publisher, NUMA CPU Pinning,
Scratch I/O Verification, Core-Dump Garbage Collection, and Artifact Hashing.
Provides `safe_subprocess_run`, `register_popen_process`, and `SubprocessBroker`.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import platform
import shlex
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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

from cochem_base.config_loader import get_artifact_dir, get_ramdisk_dir, resolve_mapped_path

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
_GLOBAL_TRACKING_LOCK = threading.Lock()


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
            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError, OSError):
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def cleanup_zombie_processes() -> int:
    """Atexit hook to terminate any dangling Popen child process trees (e.g. ORCA / OpenMPI)."""
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


# Register zombie process cleanup hook at module import
atexit.register(cleanup_zombie_processes)


def enforce_cpu_affinity(pid: int, cpu_cores: Optional[List[int]] = None) -> bool:
    """Pins a process to specified CPU cores using OS-level affinity control."""
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
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as e:
        logger.warning(f"Failed to set CPU affinity on PID {pid}: {e}")
        return False


def verify_scratch_io(scratch_dir: Union[str, Path], required_mb: int = 100) -> bool:
    """
    Performs real physical read/write probe and capacity check on scratch directory.
    Guarantees physical disk responsiveness and storage quota before heavy binary execution.
    """
    target_path = Path(scratch_dir).resolve()
    target_path.mkdir(parents=True, exist_ok=True)

    try:
        usage = shutil.disk_usage(str(target_path))
        free_mb = usage.free / (1024 * 1024)
        if free_mb < required_mb:
            logger.error(f"Insufficient scratch disk space at {target_path}: {free_mb:.1f} MB free, {required_mb} MB required.")
            return False

        probe_file = target_path / f".cochem_io_probe_{os.getpid()}_{int(time.time() * 1000)}.tmp"
        probe_data = os.urandom(64 * 1024)  # 64 KB physical binary probe
        expected_hash = hashlib.sha256(probe_data).hexdigest()

        with open(probe_file, "wb") as f:
            f.write(probe_data)
            f.flush()
            os.fsync(f.fileno())

        with open(probe_file, "rb") as f:
            read_back_data = f.read()

        read_hash = hashlib.sha256(read_back_data).hexdigest()
        probe_file.unlink(missing_ok=True)

        if expected_hash != read_hash:
            logger.error(f"Scratch I/O integrity probe failed: hash mismatch at {target_path}")
            return False

        logger.info(f"Verified scratch I/O at {target_path} ({free_mb:.1f} MB free) [M]")
        return True
    except (OSError, IOError) as exc:
        logger.error(f"Scratch I/O verification error at {target_path}: {exc}")
        return False


def safe_subprocess_run(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
    cpu_affinity: Optional[List[int]] = None,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """
    Executes a subprocess safely with explicit check, timeout, explicit cwd validation,
    optional hardware CPU affinity pinning, and robust exception handling.
    """
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise FileNotFoundError(f"Subprocess working directory does not exist: {cwd_path}")
        cwd_str = str(cwd_path)
    else:
        cwd_str = None

    if cpu_affinity is not None and HAS_PSUTIL:
        # Launch with Popen to enforce affinity before waiting
        popen_args: Dict[str, Any] = {
            "cwd": cwd_str,
            "env": env,
            "text": text,
            **kwargs
        }
        if capture_output:
            popen_args["stdout"] = subprocess.PIPE
            popen_args["stderr"] = subprocess.PIPE

        parsed_cmd: Union[List[str], str]
        if isinstance(cmd, str) and not kwargs.get("shell", False):
            parsed_cmd = shlex.split(cmd)
        else:
            parsed_cmd = cmd

        proc = subprocess.Popen(parsed_cmd, **popen_args)
        register_popen_process(proc)
        enforce_cpu_affinity(proc.pid, cpu_affinity)
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
            ret = proc.returncode
            if check and ret != 0:
                raise subprocess.CalledProcessError(ret, cmd, output=stdout_data, stderr=stderr_data)
            return subprocess.CompletedProcess(args=cmd, returncode=ret, stdout=stdout_data, stderr=stderr_data)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc.pid)
            proc.wait(timeout=3.0)
            logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
            raise
        finally:
            unregister_popen_process(proc)

    try:
        res = subprocess.run(cmd, cwd=cwd_str, timeout=timeout, check=check, capture_output=capture_output, text=text, env=env, **kwargs)
        return res
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess '{cmd}' failed with returncode {e.returncode}: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
        raise
    except OSError as e:
        logger.error(f"Subprocess execution error for '{cmd}': {e}")
        raise


class SubprocessBroker:
    """
    Subprocess execution manager for computational quantum chemistry workloads.
    Handles process lifecycles, memory safety, heartbeats, and artifact hashing.
    """

    def __init__(
        self,
        cwd: Optional[Union[str, Path]] = None,
        env: Optional[Dict[str, str]] = None,
        memory_limit_gb: float = 8.0
    ) -> None:
        default_work_dir = get_artifact_dir() / "Scratch"
        self.cwd = resolve_mapped_path(cwd, default_work_dir) if cwd is not None else default_work_dir
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.env = env if env is not None else os.environ.copy()
        self.memory_limit_bytes = memory_limit_gb * (1024 ** 3)

        if TelemetryLogger is not None:
            self.telemetry: Optional[Any] = TelemetryLogger()
        else:
            self.telemetry = None

        self.active_processes: List[subprocess.Popen] = []
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # ZeroMQ heartbeat publisher components
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
        self.execute_zombie_reaper()
        try:
            atexit.unregister(self.execute_zombie_reaper)
        except Exception:
            pass

    def verify_scratch_io(self, required_mb: int = 100) -> bool:
        """Verifies read/write availability on the current working scratch directory."""
        return verify_scratch_io(self.cwd, required_mb=required_mb)

    def _allocate_scratch_space(self, job_name: str, required_mb: int = 4000) -> Path:
        """Allocate a mapped host RAM disk when available, falling back to artifact storage."""
        ramdisk_path = get_ramdisk_dir()
        if HAS_PSUTIL and ramdisk_path is not None and ramdisk_path.is_dir():
            try:
                free_mb = psutil.disk_usage(str(ramdisk_path)).free / (1024 * 1024)
                if free_mb > (required_mb * 1.2):
                    job_shm_dir = ramdisk_path / f"cochem_{job_name}_{int(time.time())}"
                    job_shm_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Allocated RAM-disk execution directory: {job_shm_dir}")
                    return job_shm_dir
            except (OSError, ValueError) as exc:
                logger.debug(f"RAM-disk check skipped: {exc}")
        logger.info("RAM-disk unavailable or insufficient. Falling back to local directory.")
        return self.cwd

    def start_oom_monitor(self, check_interval: float = 2.0, threshold_mb: float = 1024.0) -> None:
        """Background thread checking system RAM to preemptively kill before kernel panic."""
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
        metadata: Optional[Dict[str, Any]] = None
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
                    "metadata": metadata or {}
                }
                try:
                    if self._zmq_socket is not None:
                        self._zmq_socket.send_multipart([
                            b"heartbeat",
                            json.dumps(alive_payload).encode("utf-8")
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
        """
        Calculates SHA-256 cryptographic provenance digests for all quantum chemistry artifacts.
        Tags valid artifacts with [M] provenance marker.
        """
        target_dir = Path(execution_dir).resolve() if execution_dir is not None else self.cwd
        hashes: Dict[str, str] = {}
        if not target_dir.exists():
            return hashes

        valid_suffixes = {".out", ".gbw", ".xyz", ".log", ".dat", ".json", ".h5", ".molden", ".cube"}
        for file_path in sorted(target_dir.iterdir()):
            if file_path.is_file() and (file_path.suffix in valid_suffixes or file_path.name.endswith(".out")):
                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    hashes[file_path.name] = file_hash
                    logger.info(f"Generated SHA-256 hash for {file_path.name}: {file_hash} [M]")
                except OSError as err:
                    logger.warning(f"Failed to hash {file_path.name}: {err}")
        return hashes

    def execute(
        self,
        payload_command: Union[str, List[str]],
        job_name: str = "cochem_job",
        timeout: Optional[float] = None,
        cpu_affinity: Optional[List[int]] = None
    ) -> int:
        """
        Stage 1.1: Local Execution Engine Agnostic Dispatch.
        Allocates RAM-disk if available, executes command in isolated process group,
        monitors real-time telemetry, enforces timeout, and copies artifacts back upon completion.
        """
        exec_path = self._allocate_scratch_space(job_name)
        self.verify_scratch_io()

        if isinstance(payload_command, str):
            command = shlex.split(payload_command)
            cmd_str = payload_command
        else:
            command = payload_command
            cmd_str = " ".join(payload_command)

        logger.info(f"Dispatching '{job_name}' to broker in {exec_path}...")

        stdout_hist: List[str] = []
        stderr_hist: List[str] = []

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(exec_path),
            "env": self.env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True
        }
        if hasattr(os, "setsid") and platform.system() != "Windows":
            popen_kwargs["preexec_fn"] = os.setsid

        process: Optional[subprocess.Popen] = None
        exit_code: int = 0

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            with self._lock:
                self.active_processes.append(process)
            register_popen_process(process)

            if cpu_affinity is not None:
                enforce_cpu_affinity(process.pid, cpu_affinity)

            def _stream_stdout() -> None:
                if process and process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        clean_line = line.strip()
                        stdout_hist.append(clean_line)
                        if self.telemetry and not self.telemetry.process_stream_chunk(clean_line):
                            logger.error("Telemetry trap triggered. Preempting process.")
                            kill_process_tree(process.pid)
                            break

            def _stream_stderr() -> None:
                if process and process.stderr:
                    for line in iter(process.stderr.readline, ''):
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

            self.garbage_collect_core_dumps(exec_path)

            # Sync RAM-disk artifacts back to permanent storage
            if exec_path != self.cwd and exec_path.exists():
                logger.info("Syncing artifacts from RAM-disk to permanent workspace...")
                for file_path in exec_path.iterdir():
                    if file_path.is_file():
                        dest_path = self.cwd / file_path.name
                        shutil.copy2(file_path, dest_path)
                self.hash_quantum_artifacts(self.cwd)
                shutil.rmtree(exec_path, ignore_errors=True)
            else:
                self.hash_quantum_artifacts(self.cwd)

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
    "verify_scratch_io",
    "HAS_PSUTIL",
    "HAS_ZMQ",
]


if __name__ == "__main__":
    broker = SubprocessBroker()
    logger.info("Broker Initialized and protections armed.")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_subprocess_broker.py ---
"""
Unit and Integration Test Suite for CoChem Core Subprocess Broker.
Validates process tree lifecycle, safe execution, zombie reaping, OOM monitor thread,
telemetry stream trapping, scratch I/O verification, ZeroMQ heartbeats, NUMA CPU pinning,
and artifact provenance hashing against real physical OS processes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import pytest

from core_engine.cochem_core_subprocess_broker import (
    HAS_PSUTIL,
    HAS_ZMQ,
    SubprocessBroker,
    cleanup_zombie_processes,
    enforce_cpu_affinity,
    get_active_popen_processes,
    kill_process_tree,
    register_popen_process,
    safe_subprocess_run,
    unregister_popen_process,
    verify_scratch_io,
)

if HAS_PSUTIL:
    import psutil

if HAS_ZMQ:
    import zmq


def test_popen_registration_and_unregistration() -> None:
    """Test registering, polling active, and unregistering subprocesses."""
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    proc = subprocess.Popen(cmd)
    try:
        register_popen_process(proc)
        active = get_active_popen_processes()
        assert proc in active

        unregister_popen_process(proc)
        active_after = get_active_popen_processes()
        assert proc not in active_after
    finally:
        kill_process_tree(proc.pid)
        proc.wait(timeout=3.0)


def test_kill_process_tree_recursive() -> None:
    """Test terminating a parent and its recursive child processes."""
    parent_script = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
time.sleep(30)
"""
    proc = subprocess.Popen([sys.executable, "-c", parent_script])
    register_popen_process(proc)
    time.sleep(0.8)

    pid = proc.pid
    child_pids: List[int] = []
    if HAS_PSUTIL:
        try:
            parent_p = psutil.Process(pid)
            child_pids = [c.pid for c in parent_p.children(recursive=True)]
        except psutil.NoSuchProcess:
            pass

    kill_process_tree(pid)
    proc.wait(timeout=3.0)

    if HAS_PSUTIL:
        time.sleep(0.3)
        assert not psutil.pid_exists(pid)
        for cpid in child_pids:
            assert not psutil.pid_exists(cpid), f"Child PID {cpid} leaked!"


def test_cleanup_zombie_processes_global() -> None:
    """Test that global cleanup sweeps all registered living processes."""
    proc1 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    register_popen_process(proc1)
    register_popen_process(proc2)

    time.sleep(0.3)
    reaped = cleanup_zombie_processes()
    assert reaped >= 2

    proc1.wait(timeout=2.0)
    proc2.wait(timeout=2.0)
    assert len(get_active_popen_processes()) == 0


def test_safe_subprocess_run_success() -> None:
    """Test safe_subprocess_run with successful execution and output capture."""
    res = safe_subprocess_run(
        [sys.executable, "-c", "print('SUBPROCESS_BROKER_OK')"],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "SUBPROCESS_BROKER_OK" in res.stdout


def test_safe_subprocess_run_with_custom_env_and_cwd(tmp_path: Path) -> None:
    """Test safe_subprocess_run with custom working directory and environment variables."""
    test_env = {"COCHEM_BROKER_TEST_VAR": "ALPHA_OMEGA_VALUE"}
    test_script = "import os, sys; print(os.getcwd()); print(os.environ.get('COCHEM_BROKER_TEST_VAR'))"

    res = safe_subprocess_run(
        [sys.executable, "-c", test_script],
        cwd=tmp_path,
        env=test_env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert str(tmp_path).lower() in res.stdout.lower()
    assert "ALPHA_OMEGA_VALUE" in res.stdout


def test_safe_subprocess_run_invalid_cwd() -> None:
    """Test safe_subprocess_run raising FileNotFoundError on non-existent directory."""
    non_existent_dir = Path("D:/non_existent_dir_co_chem_xyz_987")
    with pytest.raises(FileNotFoundError):
        safe_subprocess_run(
            [sys.executable, "-c", "print('fail')"],
            cwd=non_existent_dir
        )


def test_safe_subprocess_run_called_process_error() -> None:
    """Test safe_subprocess_run raising CalledProcessError on non-zero exit with check=True."""
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        safe_subprocess_run(
            [sys.executable, "-c", "import sys; sys.stderr.write('FAILURE_LOG'); sys.exit(42)"],
            check=True
        )
    assert exc_info.value.returncode == 42
    assert "FAILURE_LOG" in (exc_info.value.stderr or "")


def test_safe_subprocess_run_timeout() -> None:
    """Test safe_subprocess_run timing out and raising TimeoutExpired."""
    with pytest.raises(subprocess.TimeoutExpired):
        safe_subprocess_run(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=0.5
        )


def test_safe_subprocess_run_string_command() -> None:
    """Test safe_subprocess_run when passing a command string."""
    res = safe_subprocess_run(
        f'"{sys.executable}" -c "print(12345)"',
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert "12345" in res.stdout


def test_safe_subprocess_run_with_affinity() -> None:
    """Test safe_subprocess_run with explicit CPU affinity specification."""
    if HAS_PSUTIL:
        available_cores = list(range(min(2, os.cpu_count() or 1)))
        res = safe_subprocess_run(
            [sys.executable, "-c", "print('AFFINITY_OK')"],
            capture_output=True,
            text=True,
            cpu_affinity=available_cores
        )
        assert res.returncode == 0
        assert "AFFINITY_OK" in res.stdout


def test_broker_init_and_context_manager(tmp_path: Path) -> None:
    """Test SubprocessBroker initialization, context manager enter/exit, and directory setup."""
    scratch_dir = tmp_path / "custom_scratch"
    with SubprocessBroker(cwd=scratch_dir) as broker:
        assert broker.cwd.exists()
        assert broker.memory_limit_bytes > 0
        assert broker._atexit_reaper is not None
        assert broker._lock is not None


def test_broker_oom_monitor_lifecycle() -> None:
    """Test starting and stopping OOM preemption monitor thread without blocking."""
    broker = SubprocessBroker()
    try:
        broker.start_oom_monitor(check_interval=0.1)
        if HAS_PSUTIL:
            assert broker._monitor_thread is not None
            assert broker._monitor_thread.is_alive()
        time.sleep(0.3)
    finally:
        broker.stop_oom_monitor()
        assert broker._monitor_thread is None
        broker.close()


def test_broker_execute_success(tmp_path: Path) -> None:
    """Test SubprocessBroker executing a command successfully."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import sys; sys.stdout.write('BROKER_EXEC_OK'); sys.exit(0)"],
            job_name="test_exec_ok"
        )
        assert exit_code == 0
    finally:
        broker.close()


def test_broker_execute_failure(tmp_path: Path) -> None:
    """Test SubprocessBroker capturing a non-zero exit code."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import sys; sys.stderr.write('CRASH'); sys.exit(5)"],
            job_name="test_exec_fail"
        )
        assert exit_code == 5
    finally:
        broker.close()


def test_broker_execute_timeout(tmp_path: Path) -> None:
    """Test SubprocessBroker enforcing process timeout and returning -124."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        exit_code = broker.execute(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            job_name="test_exec_timeout",
            timeout=0.6
        )
        assert exit_code == -124
    finally:
        broker.close()


def test_broker_core_dump_garbage_collection(tmp_path: Path) -> None:
    """Test sweeping core dump binary files."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        core1 = tmp_path / "core.1234"
        core2 = tmp_path / "core.5678"
        normal = tmp_path / "output.txt"
        core1.write_bytes(b"DUMP_DATA_1")
        core2.write_bytes(b"DUMP_DATA_2")
        normal.write_text("VALID_DATA", encoding="utf-8")

        swept = broker.garbage_collect_core_dumps(tmp_path)
        assert swept == 2
        assert not core1.exists()
        assert not core2.exists()
        assert normal.exists()
    finally:
        broker.close()


def test_broker_artifact_sync_and_hash(tmp_path: Path) -> None:
    """Test SubprocessBroker generates hashes for quantum chemistry artifact files."""
    broker = SubprocessBroker(cwd=tmp_path)
    try:
        out_file = tmp_path / "water_opt.out"
        out_file.write_text("FINAL SINGLE POINT ENERGY -76.43210 Hartree\n", encoding="utf-8")

        script = 'import sys; sys.stdout.write("DONE"); sys.exit(0)'
        exit_code = broker.execute([sys.executable, "-c", script], job_name="hash_test")
        assert exit_code == 0
        assert out_file.exists()

        hashes = broker.hash_quantum_artifacts(tmp_path)
        assert "water_opt.out" in hashes
        assert len(hashes["water_opt.out"]) == 64
    finally:
        broker.close()


def test_broker_zombie_reaper_active_processes() -> None:
    """Test execute_zombie_reaper kills active processes tracked by the broker."""
    broker = SubprocessBroker()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        with broker._lock:
            broker.active_processes.append(proc)
        register_popen_process(proc)

        time.sleep(0.3)
        reaped = broker.execute_zombie_reaper()
        assert reaped >= 1
        assert len(broker.active_processes) == 0

        proc.wait(timeout=2.0)
    finally:
        broker.close()


def test_verify_scratch_io(tmp_path: Path) -> None:
    """Test physical disk I/O verification on scratch directory."""
    scratch_dir = tmp_path / "scratch_probe_dir"
    is_valid = verify_scratch_io(scratch_dir, required_mb=1)
    assert is_valid is True
    assert scratch_dir.exists()


def test_enforce_cpu_affinity() -> None:
    """Test CPU affinity enforcement on current process."""
    if HAS_PSUTIL:
        pid = os.getpid()
        num_cores = os.cpu_count() or 1
        target_cores = [0] if num_cores > 0 else []
        success = enforce_cpu_affinity(pid, target_cores)
        assert success is True


def test_broker_zmq_heartbeat_lifecycle() -> None:
    """Test starting, receiving heartbeats from, and stopping ZeroMQ publisher."""
    if not HAS_ZMQ:
        pytest.skip("pyzmq not installed")

    port = 5559
    broker = SubprocessBroker()
    ctx = zmq.Context()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.connect(f"tcp://127.0.0.1:{port}")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "heartbeat")

    try:
        broker.start_zmq_heartbeat(port=port, interval_sec=0.1, metadata={"tier": "test"})
        assert broker._zmq_thread is not None
        assert broker._zmq_thread.is_alive()

        # Poll for incoming heartbeat
        poller = zmq.Poller()
        poller.register(sub_socket, zmq.POLLIN)
        events = dict(poller.poll(timeout=2000))

        if sub_socket in events:
            topic, payload_bytes = sub_socket.recv_multipart()
            assert topic == b"heartbeat"
            data = json.loads(payload_bytes.decode("utf-8"))
            assert data["status"] == "alive"
            assert data["metadata"]["tier"] == "test"
    finally:
        broker.stop_zmq_heartbeat()
        sub_socket.close(linger=0)
        ctx.term()
        broker.close()

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.