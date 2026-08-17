import asyncio
import concurrent.futures
import uuid
import logging
import atexit
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class HPCDispatcher:
    """
    A dispatcher for high-performance computing tasks that handles queuing
    and asynchronous execution.
    """
    def __init__(self, max_workers: int = 4):
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.max_workers = max_workers
        # Note: Depending on whether tasks are I/O bound (subprocess) or CPU bound,
        # ProcessPoolExecutor may be preferred. Keeping ThreadPoolExecutor for now
        # assuming tasks are subprocess wrappers, but logging its use.
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, asyncio.Future] = {}
        self.results: Dict[str, Any] = {}
        
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Ensure executor is shutdown on exit to prevent zombies."""
        logger.info("Cleaning up HPCDispatcher and shutting down executor.")
        self.executor.shutdown(wait=False, cancel_futures=True)

    async def dispatch(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        """
        Dispatch a task for asynchronous execution.
        Returns a task ID that can be used to query the status or retrieve the result.
        """
        task_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()

        logger.info(f"Dispatching task {task_id}")
        # Run the function in the executor
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
                logger.error(f"Task {task_id} failed with error: {e}", exc_info=True)
                self.results[task_id] = e

        future.add_done_callback(_on_done)
        return task_id

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Wait for a task to complete and return its result.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task ID: {task_id}")

        future = self.tasks[task_id]
        try:
            if timeout is not None:
                await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
            else:
                await future
        except asyncio.TimeoutError as e:
            logger.error(f"Task {task_id} timed out after {timeout}s.")
            raise e
        
        # If the task raised an exception, await future will raise it.
        # If we reach here, it means the future completed successfully.
        return future.result()

    def get_status(self, task_id: str) -> str:
        """
        Check the status of a task without waiting.
        """
        if task_id not in self.tasks:
            return "UNKNOWN"

        future = self.tasks[task_id]
        if future.done():
            if future.cancelled():
                return "CANCELLED"
            elif future.exception() is not None:
                return "FAILED"
            return "COMPLETED"
        return "RUNNING"

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the dispatcher and underlying executor.
        """
        logger.info(f"Shutting down HPCDispatcher (wait={wait}).")
        self.executor.shutdown(wait=wait, cancel_futures=True)
