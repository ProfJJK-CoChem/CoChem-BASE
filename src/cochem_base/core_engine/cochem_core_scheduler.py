# cochem_canvas_target: core_engine/cochem_core_scheduler.py
"""
Scheduler module for CoChem-CORE.
Manages scheduling and queuing of computational chemistry tasks.
"""

import filelock
import hashlib
import json
import logging
import os
import psutil
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from cochem.core.context import assert_writable_path
from cochem_base.config_loader import get_artifact_dir, get_state_file_path
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock, atomic_write_json

# Runtime data is always outside source checkouts, including configured overrides.
ARTIFACTS_DIR = get_artifact_dir()
logger = logging.getLogger("CoChem-CoreScheduler")


class SchedulerStateError(ValueError):
    """Persistent scheduler state is invalid and must be preserved for recovery."""


# Preserve the legacy public helper without claiming other libraries' children.
from cochem_base.process_cleanup import reap_owned_children as sweep_zombie_processes


def compute_sha256(filepath: Path) -> str:
    """Generate SHA-256 hash for a file."""
    if not filepath.exists():
        return ""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_hpc_filesystem(path: Path) -> bool:
    """Detect if path resides on an HPC distributed filesystem (Lustre, GPFS, NFS, Slurm/PBS)."""
    if "SLURM_JOB_ID" in os.environ or "PBS_JOBID" in os.environ:
        return True
    path_str = str(path.resolve()).lower()
    for marker in ["/lustre", "/gpfs", "nfs", "gluster", "weka"]:
        if marker in path_str:
            return True
    return False


def persist_swarm_state_atomic(
    state_file: Union[str, Path],
    task_id: str,
    entry: Dict[str, Any],
    timeout: float = 10.0,
    max_retries: int = 10,
) -> None:
    """Atomically merge one task under the shared registry lock.

    Staging occurs beside the destination, including on HPC filesystems; copying
    from local scratch onto a live shared JSON file is never an atomic commit.
    Corrupt or unreadable prior state is preserved and reported to the caller.
    """
    # Validate serialization before acquiring a lock or changing any state.
    if not isinstance(task_id, str) or not task_id or not isinstance(entry, dict):
        raise SchedulerStateError("Task state requires a non-empty identifier and JSON object")
    try:
        json.dumps(entry, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise SchedulerStateError("Task state must contain finite JSON values") from exc
    state_file = Path(state_file).resolve()
    assert_writable_path(state_file)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with AtomicFileLock(str(state_file) + ".lock", timeout=timeout):
        state_data: Dict[str, Any] = {}
        if state_file.exists():
            try:
                state_data = json.loads(state_file.read_text(encoding="utf-8"))
                json.dumps(state_data, allow_nan=False)
            except (ValueError, UnicodeError) as exc:
                raise SchedulerStateError(f"Corrupt scheduler state preserved at {state_file}") from exc
            if not isinstance(state_data, dict):
                raise SchedulerStateError(f"Scheduler state must be a JSON object: {state_file}")
        state_data[task_id] = entry
        atomic_write_json(state_file, state_data, lock_timeout=timeout, max_retries=max_retries)


# 2. Rigorous Typing & Linting
class TaskConfig(BaseModel):
    task_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    command: List[str] = Field(min_length=1)
    env_vars: Optional[Dict[str, str]] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=3600, gt=0, strict=True)


class TaskResult(BaseModel):
    task_id: str
    status: str
    return_code: Optional[int] = None
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    hashes: Dict[str, str] = Field(default_factory=dict)


class CoreScheduler:
    """
    Schedules and manages computational tasks across the system.
    """
    _state_lock = threading.Lock()

    def __init__(self, max_workers: int = 4, project_root: Optional[Path] = None) -> None:
        """Initialize the scheduler with a thread-safe task queue."""
        self.max_workers = max_workers
        self.project_root = Path(project_root).resolve() if project_root is not None else None
        self.state_file = (self.project_root / "swarm_state.json" if self.project_root is not None
                           else get_state_file_path())
        assert_writable_path(self.state_file)
        self.task_queue: queue.Queue[TaskConfig] = queue.Queue()
        self.running_tasks: Dict[str, TaskResult] = {}
        self.is_running = False
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._scheduler_thread: Optional[threading.Thread] = None

    def add_task(self, task: TaskConfig) -> None:
        """Add a task to the scheduling queue."""
        logger.info(f"📥 Adding task {task.task_id} to queue")
        self.task_queue.put(task)


    def _execute_task(self, task: TaskConfig) -> TaskResult:
        """Execute a computational task safely using subprocess."""
        from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run

        task_root = get_artifact_dir() / "Scheduler"
        task_root.mkdir(parents=True, exist_ok=True)
        task_dir = Path(tempfile.mkdtemp(prefix=f"{task.task_id}_", dir=task_root))
        output_file = task_dir / f"{task.task_id}.out"
        env = os.environ.copy()
        if task.env_vars:
            env.update(task.env_vars)
        
        result = TaskResult(task_id=task.task_id, status="running", output_file=str(output_file))
        self.running_tasks[task.task_id] = result
        
        try:
            with open(output_file, 'w', encoding='utf-8') as out_f:
                process = safe_subprocess_run(
                    task.command,
                    cwd=task_dir,
                    capture_output=False,
                    env=env,
                    stdout=out_f,
                    stderr=subprocess.STDOUT,
                    timeout=task.timeout_seconds,
                    check=True
                )
            result.status = "completed"
            result.return_code = process.returncode
            result.output_file = str(output_file)
            
            # Generate hashes for .out and .gbw files if they exist
            result.hashes[str(output_file)] = compute_sha256(output_file)
            gbw_file = task_dir / f"{task.task_id}.gbw"
            if gbw_file.exists():
                result.hashes[str(gbw_file)] = compute_sha256(gbw_file)
                
            logger.info(f"✅ Task {task.task_id} completed successfully")
        except subprocess.TimeoutExpired as e:
            result.status = "timeout"
            result.error_message = f"Task timed out after {task.timeout_seconds}s"
            logger.error(f"Task {task.task_id} timeout: {e}")
        except subprocess.CalledProcessError as e:
            result.status = "failed"
            result.return_code = e.returncode
            result.error_message = f"Task failed with exit code {e.returncode}"
            logger.error(f"Task {task.task_id} failed: {e}")
        except OSError as e:
            result.status = "failed"
            result.error_message = f"Command could not execute: {e}"
            logger.error(f"Task {task.task_id} execution unavailable: {e}")
            
        self._update_swarm_state(result)
        return result

    def _update_swarm_state(self, result: TaskResult) -> None:
        """Update the swarm_state.json with task outcome using cross-process atomic persistence."""
        entry = {
            "agent": "cochem-core-scheduler",
            "status": "SUCCESS" if result.status == "completed" else "FAILURE",
            "artifacts": [result.output_file] if result.output_file else [],
            "hashes": result.hashes,
            "error_message": result.error_message,
            "timestamp": time.time(),
        }
        persist_swarm_state_atomic(self.state_file, result.task_id, entry)

    def schedule_next_task(self) -> Optional[TaskConfig]:
        """Schedule the next available task from thread-safe queue."""
        try:
            task = self.task_queue.get_nowait()
        except queue.Empty:
            return None

        logger.info(f"🕒 Scheduling task {task.task_id}")
        self._executor.submit(self._execute_task, task)
        self.task_queue.task_done()
        return task

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get the status of a specific task."""
        return self.running_tasks.get(task_id)

    def start_scheduling(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            return
        self.is_running = True
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("🔄 Scheduler started")

    def _scheduler_loop(self) -> None:
        """Continuously drain tasks from the queue using event-driven worker saturation."""
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            logger.info(f"🕒 Scheduling task {task.task_id}")
            self._executor.submit(self._execute_task, task)
            self.task_queue.task_done()

            # Worker saturation: immediately drain any pending tasks while running
            while self.is_running:
                try:
                    next_task = self.task_queue.get_nowait()
                    logger.info(f"🕒 Scheduling task {next_task.task_id}")
                    self._executor.submit(self._execute_task, next_task)
                    self.task_queue.task_done()
                except queue.Empty:
                    break

    def stop_scheduling(self) -> None:
        """Stop the scheduler and join background worker threads."""
        self.is_running = False
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=2.0)
            self._scheduler_thread = None
        self._executor.shutdown(wait=True)
        logger.info("🛑 Scheduler stopped")


def main() -> None:
    """Main entry point for the scheduler."""
    logger.info("Starting CoChem-CORE Scheduler")
    # Mocked data and fake workflows have been eradicated. 
    # Real execution driven by incoming requests is expected.
    logger.info("Ready to accept genuine workloads.")


if __name__ == "__main__":
    main()


__all__ = [
    "TaskConfig",
    "TaskResult",
    "CoreScheduler",
    "persist_swarm_state_atomic",
    "is_hpc_filesystem",
]
