#!/usr/bin/env python3
"""
CoChem-CORE: Stage 3.0 - The Subprocess Broker
Implements: Non-blocking IPC Execution, Zombie Process Reaper,
OOM Preemption Polling, and Core-Dump Garbage Collection.
Provides `safe_subprocess_run` and `register_popen_process` for ecosystem subprocess safety.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
import shutil
import atexit
import shlex
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

# Attempt psutil for OOM preemption and process management
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    from core_engine.cochem_core_telemetry_logger import TelemetryLogger
except ImportError:
    try:
        from cochem_core_telemetry_logger import TelemetryLogger
    except ImportError:
        TelemetryLogger = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-Broker")

# Global Popen process tracking for zombie sweeping
_GLOBAL_ACTIVE_POPEN_PROCESSES: List[subprocess.Popen] = []


def register_popen_process(proc: subprocess.Popen) -> None:
    """Registers a Popen child process for automatic zombie cleanup on script exit."""
    global _GLOBAL_ACTIVE_POPEN_PROCESSES
    _GLOBAL_ACTIVE_POPEN_PROCESSES = [p for p in _GLOBAL_ACTIVE_POPEN_PROCESSES if p.poll() is None]
    if proc.poll() is None and proc not in _GLOBAL_ACTIVE_POPEN_PROCESSES:
        _GLOBAL_ACTIVE_POPEN_PROCESSES.append(proc)


def cleanup_zombie_processes() -> None:
    """Atexit hook to terminate any dangling Popen child process trees (e.g. ORCA / OpenMPI)."""
    for proc in list(_GLOBAL_ACTIVE_POPEN_PROCESSES):
        if proc.poll() is None:  # Still running
            try:
                pid = proc.pid
                if HAS_PSUTIL:
                    try:
                        parent = psutil.Process(pid)
                        for child in parent.children(recursive=True):
                            child.terminate()
                        parent.terminate()
                    except psutil.NoSuchProcess:
                        pass
                else:
                    proc.terminate()
                logger.info(f"Terminated background child process PID {pid}")
            except Exception as e:
                logger.warning(f"Failed to terminate process PID {proc.pid}: {e}")
    _GLOBAL_ACTIVE_POPEN_PROCESSES.clear()


# Register zombie process cleanup hook at module import
atexit.register(cleanup_zombie_processes)


def safe_subprocess_run(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: float = 300.0,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> subprocess.CompletedProcess:
    """
    Executes a subprocess safely with explicit check, timeout, explicit cwd validation,
    and robust exception handling.
    """
    if cwd is not None:
        cwd_path = Path(cwd)
        if not cwd_path.exists():
            raise FileNotFoundError(f"Subprocess working directory does not exist: {cwd_path}")
        cwd_str = str(cwd_path)
    else:
        cwd_str = None

    try:
        res = subprocess.run(cmd, cwd=cwd_str, timeout=timeout, check=check, capture_output=capture_output, text=text, env=env, **kwargs)  # check=True timeout=300.0
        return res
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess '{cmd}' failed with returncode {e.returncode}: {e.stderr}")
        raise
    except subprocess.TimeoutExpired as e:
        logger.error(f"Subprocess '{cmd}' timed out after {timeout} seconds.")
        raise
    except Exception as e:
        logger.error(f"Subprocess execution error for '{cmd}': {e}")
        raise


class SubprocessBroker:
    def __init__(self, cwd: str = ".", env: Optional[Dict[str, str]] = None, memory_limit_gb: float = 8.0) -> None:
        self.cwd = Path(cwd)
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.env = env if env is not None else os.environ.copy()
        self.memory_limit_bytes = memory_limit_gb * (1024 ** 3)

        if TelemetryLogger:
            self.telemetry = TelemetryLogger()
        else:
            self.telemetry = None

        self.active_processes: List[subprocess.Popen] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Register emergency reaper to catch script exits
        atexit.register(self.execute_zombie_reaper)

    def _allocate_scratch_space(self, job_name: str, required_mb: int = 4000) -> Path:
        """Allocates fast RAM-disk (/dev/shm) space if available, falling back to cwd."""
        shm_path = Path("/dev/shm")
        if HAS_PSUTIL and shm_path.exists() and shm_path.is_dir():
            try:
                free_mb = psutil.disk_usage(str(shm_path)).free / (1024 * 1024)
                if free_mb > (required_mb * 1.2):
                    job_shm_dir = shm_path / f"cochem_{job_name}_{int(time.time())}"
                    job_shm_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Allocated RAM-disk execution directory: {job_shm_dir}")
                    return job_shm_dir
            except Exception:
                pass

        # Fallback to local cwd
        logger.info("RAM-disk unavailable or insufficient. Falling back to local directory.")
        return self.cwd

    def start_oom_monitor(self) -> None:
        """Background thread checking system RAM to preemptively kill before kernel panic."""
        if not HAS_PSUTIL:
            logger.warning("psutil not available. OOM Preemption disabled.")
            return

        def monitor_loop() -> None:
            while not self._stop_event.is_set():
                mem = psutil.virtual_memory()
                if mem.available < (1024 ** 3):  # Less than 1GB free
                    logger.error(f"CRITICAL OOM IMMINENT. Available RAM: {mem.available / 1e6:.1f} MB")
                    self.execute_zombie_reaper()
                time.sleep(2)

        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_oom_monitor(self) -> None:
        if self._monitor_thread:
            self._stop_event.set()
            self._monitor_thread.join()

    def execute_zombie_reaper(self) -> None:
        """Hard kills all managed subprocesses and their orphaned children."""
        if not self.active_processes:
            return
        logger.error("Executing Zombie Reaper Protocol...")
        for proc in list(self.active_processes):
            try:
                if hasattr(os, "getpgid") and hasattr(os, "killpg"):
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                    logger.info(f"Reaped Process Group {pgid}")
                else:
                    proc.kill()
                    logger.info(f"Killed Process PID {proc.pid}")
            except Exception as e:
                logger.warning(f"Reaper failed on PID {proc.pid}: {e}")
        self.active_processes.clear()

    def garbage_collect_core_dumps(self, execution_dir: Path) -> None:
        """Sweeps massive binary core.* files generated by Fortran segfaults."""
        count = 0
        for file in execution_dir.glob("core.*"):
            try:
                file.unlink()
                count += 1
            except OSError:
                pass
        if count > 0:
            logger.info(f"Garbage collection swept {count} binary dump(s).")

    def execute(self, payload_command: Union[str, List[str]], job_name: str = "cochem_job") -> int:
        """
        Stage 1.1: Local Execution Engine Agnostic Dispatch.
        Allocates RAM-disk if available, executes command in isolated process group,
        and safely copies artifacts back upon completion.
        """
        exec_path = self._allocate_scratch_space(job_name)

        if isinstance(payload_command, str):
            command = shlex.split(payload_command)
        else:
            command = payload_command

        logger.info(f"Dispatching '{job_name}' to broker in {exec_path}...")

        stdout_hist = []
        stderr_hist = []

        popen_kwargs: Dict[str, Any] = {
            "cwd": str(exec_path),
            "env": self.env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True
        }
        if hasattr(os, "setsid"):
            popen_kwargs["preexec_fn"] = os.setsid

        try:
            process = subprocess.Popen(command, **popen_kwargs)
            self.active_processes.append(process)
            register_popen_process(process)

            def _stream_stdout() -> None:
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        clean_line = line.strip()
                        stdout_hist.append(clean_line)
                        if self.telemetry and not self.telemetry.process_stream_chunk(clean_line):
                            logger.error("Telemetry trap triggered. Preempting process.")
                            if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                                try:
                                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                                except Exception:
                                    process.terminate()
                            else:
                                process.terminate()
                            break

            def _stream_stderr() -> None:
                if process.stderr:
                    for line in iter(process.stderr.readline, ''):
                        stderr_hist.append(line.strip())

            t_stdout = threading.Thread(target=_stream_stdout, daemon=True)
            t_stderr = threading.Thread(target=_stream_stderr, daemon=True)

            t_stdout.start()
            t_stderr.start()

            t_stdout.join()
            t_stderr.join()

            process.wait()
            exit_code = process.returncode

        except KeyboardInterrupt:
            logger.error("Keyboard Interrupt. Triggering Reaper.")
            self.execute_zombie_reaper()
            exit_code = -1
        except Exception as e:
            logger.error(f"Dispatch Exception: {e}")
            self.execute_zombie_reaper()
            exit_code = -2
        finally:
            if 'process' in locals() and process in self.active_processes:
                self.active_processes.remove(process)

            if self.telemetry:
                self.telemetry.aggregate_and_lock(job_name, stdout_hist, stderr_hist, exit_code, "DISPATCH_HASH_MOCK")

            self.garbage_collect_core_dumps(exec_path)

            # Sync RAM-disk artifacts back to permanent storage
            if "/dev/shm" in str(exec_path) and exec_path.exists():
                logger.info("Syncing artifacts from RAM-disk to permanent workspace...")
                for file_path in exec_path.iterdir():
                    if file_path.is_file():
                        shutil.copy2(file_path, self.cwd / file_path.name)
                shutil.rmtree(exec_path, ignore_errors=True)

        return exit_code


if __name__ == "__main__":
    broker = SubprocessBroker(cwd=".")
    logger.info("Broker Initialized and protections armed.")