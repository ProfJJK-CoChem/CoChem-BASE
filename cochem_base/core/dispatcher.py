import concurrent.futures
import logging
import os
import queue
import shlex
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from cochem_base.config_loader import get_artifact_dir, resolve_mapped_path
from core_engine.cochem_core_subprocess_broker import register_popen_process

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class TaskResult(BaseModel):
    status: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    error: Optional[str] = None


class TaskDispatcher:
    """Subprocess dispatcher and task queue management for CoChem-BASE"""

    def __init__(self, max_workers: Optional[int] = None, timeout_seconds: float = 300.0, working_dir: Optional[Union[str, Path]] = None) -> None:
        self.task_queue: queue.Queue = queue.Queue()
        self.results: Dict[str, Dict[str, Any]] = {}
        self.results_lock = threading.Lock()
        self.max_workers = max_workers or (os.cpu_count() or 4)
        self.timeout_seconds = timeout_seconds
        default_work_dir = get_artifact_dir() / "Scratch" / "dispatcher"
        self.working_dir = resolve_mapped_path(working_dir, default_work_dir) if working_dir is not None else default_work_dir
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self.executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def submit_task(self, task_id: str, command: Union[str, List[str]]) -> None:
        """Submit a command as a task."""
        self.task_queue.put((task_id, command))

    def start_worker(self) -> None:
        if self.executor is None:
            self._stop_event.clear()
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
            self._worker_thread = threading.Thread(target=self._queue_listener, daemon=True)
            self._worker_thread.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self.executor:
            self.executor.shutdown(wait=False)
            self.executor = None

    def _queue_listener(self) -> None:
        while not self._stop_event.is_set():
            try:
                task_id, command = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if self.executor:
                self.executor.submit(self._execute_task, task_id, command)

    def _execute_task(self, task_id: str, command: Union[str, List[str]]) -> None:
        try:
            logger.info(f"[Dispatcher] Running task {task_id}: {command}")
            if isinstance(command, str):
                cmd_args = shlex.split(command)
            else:
                cmd_args = command

            try:
                process = subprocess.Popen(
                    cmd_args,
                    cwd=str(self.working_dir),
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                register_popen_process(process)
            except OSError as e:
                res_obj = TaskResult(
                    status="error",
                    error=f"Failed to start process: {e}"
                )
                with self.results_lock:
                    self.results[task_id] = res_obj.model_dump()
                return

            try:
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                res_obj = TaskResult(
                    status="success" if process.returncode == 0 else "error",
                    stdout=stdout or "",
                    stderr=stderr or "",
                    returncode=process.returncode
                )
                res = res_obj.model_dump()
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                res_obj = TaskResult(
                    status="timeout",
                    stdout=stdout or "",
                    stderr=stderr or "",
                    returncode=-1,
                    error=f"Task timed out after {self.timeout_seconds} seconds"
                )
                res = res_obj.model_dump()

            with self.results_lock:
                self.results[task_id] = res

        except Exception as e:
            res_obj = TaskResult(
                status="exception",
                error=str(e)
            )
            with self.results_lock:
                self.results[task_id] = res_obj.model_dump()
        finally:
            self.task_queue.task_done()

    def get_result(self, task_id: str) -> Dict[str, Any]:
        with self.results_lock:
            return self.results.get(task_id, {})


class SubprocessBroker:
    """Internal Subprocess Broker for executing commands safely with timeout and sanitization."""

    def __init__(self, timeout_seconds: float = 300.0, working_dir: Optional[Union[str, Path]] = None) -> None:
        self.timeout_seconds = timeout_seconds
        default_work_dir = get_artifact_dir() / "Scratch" / "subprocess"
        self.working_dir = resolve_mapped_path(working_dir, default_work_dir) if working_dir is not None else default_work_dir
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def run_command(self, command: Union[str, List[str]], timeout: Optional[float] = None) -> Tuple[int, str, str]:
        if isinstance(command, str):
            cmd_args = shlex.split(command)
        else:
            cmd_args = command

        tout = timeout if timeout is not None else self.timeout_seconds
        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=str(self.working_dir),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            register_popen_process(proc)
        except OSError as e:
            raise RuntimeError(f"Failed to execute process: {e}") from e

        try:
            stdout, stderr = proc.communicate(timeout=tout)
            return proc.returncode, stdout, stderr
        except subprocess.TimeoutExpired as e:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise TimeoutError(f"Subprocess execution timed out after {tout} seconds") from e
