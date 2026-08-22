#!/usr/bin/env python3
"""CoChem-BASE: High Performance Computing Task Dispatcher.

Provides asynchronous task dispatching, thread pool execution,
robust task tracking, and safe process shutdown.
"""

from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
from enum import Enum
import logging
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Enumeration for asynchronous HPC task states."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return self.value


class HPCDispatcher:
    """A dispatcher for high-performance computing tasks that handles queuing

    and asynchronous execution across worker threads.
    """

    def __init__(self, max_workers: int = 4) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, asyncio.Future] = {}
        self.results: Dict[str, Any] = {}
        self.is_shutdown: bool = False

        atexit.register(self._cleanup)

    @property
    def all_task_ids(self) -> List[str]:
        return list(self.tasks.keys())

    def _cleanup(self) -> None:
        """Ensure executor is shutdown on exit to prevent zombies."""
        if not self.is_shutdown:
            logger.info("Cleaning up HPCDispatcher and shutting down executor.")
            self.shutdown(wait=False)

    def __enter__(self) -> HPCDispatcher:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown(wait=True)

    async def __aenter__(self) -> HPCDispatcher:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown(wait=True)

    async def dispatch(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """Dispatch a task for asynchronous execution.

        Returns a task ID that can be used to query status or retrieve results.
        """
        if self.is_shutdown:
            raise RuntimeError("Cannot dispatch task to a shut-down HPCDispatcher")

        task_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()

        logger.info(f"Dispatching task {task_id}")
        future = loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))
        self.tasks[task_id] = future

        def _on_done(fut: asyncio.Future) -> None:
            try:
                self.results[task_id] = fut.result()
                logger.info(f"Task {task_id} completed successfully.")
            except concurrent.futures.CancelledError:
                logger.warning(f"Task {task_id} was cancelled.")
                self.results[task_id] = Exception("Task was cancelled")
            except Exception as e:
                logger.error(f"Task {task_id} failed with error: {e}")
                self.results[task_id] = e

        future.add_done_callback(_on_done)
        return task_id

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Wait for a task to complete and return its result."""
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task ID: {task_id}")

        future = self.tasks[task_id]
        if timeout is not None:
            await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        else:
            await future

        return future.result()

    def get_status(self, task_id: str) -> TaskStatus:
        """Check the status of a task without waiting."""
        if task_id not in self.tasks:
            return TaskStatus.UNKNOWN

        future = self.tasks[task_id]
        if future.done():
            if future.cancelled():
                return TaskStatus.CANCELLED
            if future.exception() is not None:
                return TaskStatus.FAILED
            return TaskStatus.COMPLETED
        return TaskStatus.RUNNING

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the dispatcher and underlying executor."""
        if not self.is_shutdown:
            logger.info(f"Shutting down HPCDispatcher (wait={wait}).")
            self.is_shutdown = True
            self.executor.shutdown(wait=wait, cancel_futures=True)
