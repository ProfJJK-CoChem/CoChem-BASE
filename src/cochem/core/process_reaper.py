"""Cross-platform process lifecycle manager and zombie reaper daemon.

Provenance & Specifications:
- Method Matrix [M]: Reliable termination of orphaned QM/MM worker subprocesses.
- OS Containment [D]: Windows Job Objects and Linux PDEATHSIG containment primitives.
- Telemetry [E]: Progressive escalation (SIGTERM -> SIGKILL) with CPU/memory footprint capture.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import psutil

from src.cochem.orchestration.sqlite_queue import SQLiteTaskQueue

logger = logging.getLogger(__name__)

DEFAULT_GRACE_TIMEOUT_SEC: float = 5.0
DEFAULT_TIMEOUT_GRACE_PERIOD_SEC: float = 30.0


def set_pdeathsig(sig: int = signal.SIGTERM) -> bool:
    """Set PR_SET_PDEATHSIG on Linux/WSL via ctypes to ensure child termination on parent exit."""
    if sys.platform.startswith("linux"):
        try:
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            PR_SET_PDEATHSIG = 1
            ret = libc.prctl(PR_SET_PDEATHSIG, sig)
            return ret == 0
        except Exception as err:
            logger.debug("Failed to set PR_SET_PDEATHSIG: %s", err)
            return False
    return False


def get_pdeathsig_preexec_fn(sig: int = signal.SIGTERM) -> Optional[Any]:
    """Return a preexec callable suitable for subprocess.Popen to establish parent death signals on Linux."""
    if not sys.platform.startswith("linux"):
        return None

    def _preexec() -> None:
        set_pdeathsig(sig)

    return _preexec


@dataclass(frozen=True)
class ProcessMetadata:
    """Immutable snapshot of tracked process identity and origin."""

    pid: int
    ppid: int
    create_time: float
    task_id: Optional[str] = None


class ProcessTreeManager:
    """Manages process hierarchies and guarantees complete subtree termination."""

    def __init__(self) -> None:
        self._tracked: Dict[int, ProcessMetadata] = {}
        self._job_handle: Optional[Any] = None
        self._init_platform_containment()

    def _init_platform_containment(self) -> None:
        """Initialize platform-specific containment primitives."""
        if sys.platform == "win32":
            try:
                import win32job  # type: ignore[import-untyped]
                self._job_handle = win32job.CreateJobObject(None, "")
                extended_info = win32job.QueryInformationJobObject(
                    self._job_handle, win32job.JobObjectExtendedLimitInformation
                )
                extended_info["BasicLimitInformation"][
                    "LimitFlags"
                ] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                win32job.SetInformationJobObject(
                    self._job_handle,
                    win32job.JobObjectExtendedLimitInformation,
                    extended_info,
                )
            except Exception as err:
                logger.debug("Windows Job Object initialization bypassed: %s", err)
                self._job_handle = None

    def register_process(
        self,
        proc: Union[psutil.Process, int],
        task_id: Optional[str] = None,
    ) -> ProcessMetadata:
        """Register a child process for lifecycle tracking."""
        p = proc if isinstance(proc, psutil.Process) else psutil.Process(proc)
        pid = p.pid
        ppid = p.ppid()
        ctime = p.create_time()

        if sys.platform == "win32" and self._job_handle is not None:
            try:
                import win32api  # type: ignore[import-untyped]
                import win32con  # type: ignore[import-untyped]
                import win32job  # type: ignore[import-untyped]
                process_handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
                win32job.AssignProcessToJobObject(self._job_handle, process_handle)
            except Exception as assign_err:
                logger.debug("Could not assign PID %d to Windows Job Object: %s", pid, assign_err)

        metadata = ProcessMetadata(
            pid=pid,
            ppid=ppid,
            create_time=ctime,
            task_id=task_id,
        )
        self._tracked[pid] = metadata
        return metadata

    def unregister_process(self, pid: int) -> None:
        """Remove process from active tracking register."""
        self._tracked.pop(pid, None)

    def is_alive(self, pid: int) -> bool:
        """Check if process exists and create_time matches registered snapshot."""
        meta = self._tracked.get(pid)
        if not psutil.pid_exists(pid):
            return False
        try:
            p = psutil.Process(pid)
            if meta is not None and abs(p.create_time() - meta.create_time) > 1.0:
                return False  # PID was recycled by OS
            return bool(p.is_running() and p.status() != psutil.STATUS_ZOMBIE)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def terminate_tree(
        self,
        pid: int,
        grace_timeout_sec: float = DEFAULT_GRACE_TIMEOUT_SEC,
    ) -> Dict[str, Any]:
        """Progressive termination escalation sequence: SIGTERM -> wait -> SIGKILL."""
        metrics: Dict[str, Any] = {
            "pid": pid,
            "cpu_time": 0.0,
            "resident_memory_mb": 0.0,
            "terminated_children_count": 0,
            "success": False,
        }

        if not psutil.pid_exists(pid):
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        # Verify against PID recycling
        meta = self._tracked.get(pid)
        if meta is not None and abs(parent.create_time() - meta.create_time) > 1.0:
            self.unregister_process(pid)
            metrics["success"] = True
            return metrics

        # Gather resource telemetry before termination
        try:
            cpu_times = parent.cpu_times()
            metrics["cpu_time"] = cpu_times.user + cpu_times.system
            metrics["resident_memory_mb"] = parent.memory_info().rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logger.debug("Could not sample telemetry before terminating PID %d", pid)

        # Collect child subtree
        try:
            children = parent.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            children = []

        all_processes = children + [parent]
        metrics["terminated_children_count"] = len(children)

        # Step 1: Issue SIGTERM / terminate()
        for p in all_processes:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Step 2: Await graceful termination
        gone, alive = psutil.wait_procs(all_processes, timeout=grace_timeout_sec)

        # Step 3: Issue SIGKILL / kill() for remaining stubborn processes
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Final wait
        if alive:
            psutil.wait_procs(alive, timeout=1.0)

        self.unregister_process(pid)
        metrics["success"] = True
        return metrics


class ZombieReaperDaemon:
    """Watchdog daemon sweeping orphaned subprocesses and reclaiming expired task leases."""

    def __init__(
        self,
        queue: Optional[SQLiteTaskQueue] = None,
        tree_manager: Optional[ProcessTreeManager] = None,
        parent_pid: Optional[int] = None,
        grace_period_sec: float = DEFAULT_TIMEOUT_GRACE_PERIOD_SEC,
        interval_sec: float = 5.0,
    ) -> None:
        self.queue = queue
        self.tree_manager = tree_manager or ProcessTreeManager()
        self.parent_pid = parent_pid or os.getpid()
        self.grace_period_sec = grace_period_sec
        self.interval_sec = interval_sec

    def is_orphan(self, pid: int) -> bool:
        """Classify process as orphaned by checking PPID and parent liveness."""
        try:
            if not psutil.pid_exists(pid):
                return False
            if self.parent_pid is not None and not psutil.pid_exists(self.parent_pid):
                return True
            p = psutil.Process(pid)
            ppid = p.ppid()
            if ppid == 1:
                return True
            if self.parent_pid is not None and ppid != self.parent_pid:
                if not psutil.pid_exists(ppid):
                    return True
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def sweep_orphans(self) -> List[int]:
        """Perform a single sweep across tracked processes and reclaim expired tasks."""
        terminated_pids: List[int] = []

        # 1. Sweep tracked processes
        active_pids = list(self.tree_manager._tracked.keys())
        for pid in active_pids:
            if not self.tree_manager.is_alive(pid):
                self.tree_manager.unregister_process(pid)
                continue

            meta = self.tree_manager._tracked.get(pid)
            task_id = meta.task_id if meta is not None else None

            # Check orphan conditions
            if self.is_orphan(pid):
                metrics = self.tree_manager.terminate_tree(pid)
                terminated_pids.append(pid)
                if self.queue is not None and task_id is not None:
                    self.queue.fail_task(
                        task_id,
                        f"Process {pid} orphaned and terminated: CPU={metrics['cpu_time']:.2f}s, RAM={metrics['resident_memory_mb']:.1f}MB",
                        can_retry=True,
                    )

        # 2. Reclaim expired task leases from SQLite queue
        if self.queue is not None:
            self.queue.reclaim_orphaned_tasks(timeout_grace_sec=self.grace_period_sec)

        return terminated_pids

    def run_watchdog_loop(self, max_iterations: Optional[int] = None) -> List[int]:
        """Execute sweep loop for up to max_iterations or indefinitely if None."""
        all_reaped: List[int] = []
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            iterations += 1
            terminated = self.sweep_orphans()
            all_reaped.extend(terminated)
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(self.interval_sec)
        return all_reaped

