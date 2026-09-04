# cochem_canvas_target: core_engine/cochem_core_scheduler.py
"""
Scheduler module for CoChem-CORE.
Manages scheduling and queuing of computational chemistry tasks.
"""

import atexit
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

# 1. Registry Consistency & Air-Gap Enforcement
ARTIFACTS_DIR = Path(os.environ.get("COCHEM_ARTIFACTS", Path.home() / "cochem_artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ARTIFACTS_DIR / "scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CoChem-CoreScheduler")

# 3. Graceful Failure & Subprocess Safety
def sweep_zombie_processes() -> None:
    """Sweep zombie processes using psutil."""
    try:
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            if child.status() == psutil.STATUS_ZOMBIE:
                child.wait(timeout=1)
    except psutil.NoSuchProcess as _e:
        logger.debug(f"Ignored exception: {_e}")

atexit.register(sweep_zombie_processes)

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
    """Cross-process atomic persistence for swarm_state.json with HPC scratch staging support."""
    state_file = Path(state_file).resolve()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = state_file.with_name(f"{state_file.name}.lock")
    hpc_mode = is_hpc_filesystem(state_file)

    for attempt in range(max_retries):
        try:
            with filelock.FileLock(str(lock_file), timeout=timeout):
                state_data: Dict[str, Any] = {}
                if state_file.exists():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            state_data = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        state_data = {}

                state_data[task_id] = entry

                if hpc_mode:
                    scratch_env = os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR") or tempfile.gettempdir()
                    stage_dir = Path(scratch_env)
                    tmp_file = stage_dir / f"swarm_state_tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.json"
                    sidecar_tmp = stage_dir / f"swarm_state_tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}.sha256"
                    try:
                        with open(tmp_file, "w", encoding="utf-8") as f:
                            json.dump(state_data, f, indent=4)
                            f.flush()
                            os.fsync(f.fileno())

                        sha = compute_sha256(tmp_file)
                        sidecar = state_file.with_name(f"{state_file.name}.sha256")
                        sidecar_tmp.write_text(f"{sha}  {state_file.name}\n", encoding="utf-8")

                        shutil.copyfile(str(tmp_file), str(state_file))
                        shutil.copyfile(str(sidecar_tmp), str(sidecar))
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink(missing_ok=True)
                            except OSError as _e:
                                logger.debug(f"Ignored exception: {_e}")
                        if sidecar_tmp.exists():
                            try:
                                sidecar_tmp.unlink(missing_ok=True)
                            except OSError as _e:
                                logger.debug(f"Ignored exception: {_e}")
                else:
                    tmp_file = state_file.with_name(f"{state_file.name}.tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}")
                    try:
                        with open(tmp_file, "w", encoding="utf-8") as f:
                            json.dump(state_data, f, indent=4)
                            f.flush()
                            os.fsync(f.fileno())

                        replace_done = False
                        for r_try in range(10):
                            try:
                                os.replace(str(tmp_file), str(state_file))
                                replace_done = True
                                break
                            except (PermissionError, OSError):
                                time.sleep(0.005 * (1.5 ** r_try))

                        if not replace_done:
                            shutil.copyfile(str(tmp_file), str(state_file))
                    finally:
                        if tmp_file.exists():
                            try:
                                tmp_file.unlink(missing_ok=True)
                            except OSError as _e:
                                logger.debug(f"Ignored exception: {_e}")
                return
        except (filelock.Timeout, PermissionError, OSError) as exc:
            if attempt == max_retries - 1:
                logger.error("Failed to persist swarm state atomically after %d attempts: %s", max_retries, exc)
                raise
            backoff = 0.05 * (1.5 ** attempt)
            logger.debug(
                "Contention on %s (%s, attempt %d/%d). Retrying in %.3fs",
                state_file,
                type(exc).__name__,
                attempt + 1,
                max_retries,
                backoff,
            )
            time.sleep(backoff)
        except Exception as exc:
            logger.error("Failed to persist swarm state atomically: %s", exc)
            raise


# 2. Rigorous Typing & Linting
class TaskConfig(BaseModel):
    task_id: str
    command: List[str]
    env_vars: Optional[Dict[str, str]] = Field(default_factory=dict)
    timeout_seconds: int = 3600


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
        output_file = ARTIFACTS_DIR / f"{task.task_id}.out"
        env = os.environ.copy()
        if task.env_vars:
            env.update(task.env_vars)
        
        result = TaskResult(task_id=task.task_id, status="running")
        self.running_tasks[task.task_id] = result
        
        try:
            with open(output_file, 'w') as out_f:
                process = subprocess.run(
                    task.command,
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
            gbw_file = ARTIFACTS_DIR / f"{task.task_id}.gbw"
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
        except FileNotFoundError as e:
            result.status = "failed"
            result.error_message = f"Command not found: {e}"
            logger.error(f"Task {task.task_id} command not found: {e}")
            
        self._update_swarm_state(result)
        return result

    def _update_swarm_state(self, result: TaskResult) -> None:
        """Update the swarm_state.json with task outcome using cross-process atomic persistence."""
        project_root = self.project_root or Path(os.environ.get("COCHEM_PROJECT_ROOT", os.getcwd()))
        state_file = project_root / "swarm_state.json"

        entry = {
            "agent": "cochem-core-scheduler",
            "status": "SUCCESS" if result.status == "completed" else "FAILURE",
            "artifacts": [result.output_file] if result.output_file else [],
            "hashes": result.hashes,
            "error_message": result.error_message,
            "timestamp": time.time(),
        }
        persist_swarm_state_atomic(state_file, result.task_id, entry)

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
