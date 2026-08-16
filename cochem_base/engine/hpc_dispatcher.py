import asyncio
import concurrent.futures
from typing import Any, Callable, Dict, Optional
import uuid

class HPCDispatcher:
    """
    A dispatcher for high-performance computing tasks that handles queuing 
    and asynchronous execution using an underlying thread or process pool.
    """
    def __init__(self, max_workers: int = 4):
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, asyncio.Future] = {}
        self.results: Dict[str, Any] = {}
        
    async def dispatch(self, func: Callable, *args, **kwargs) -> str:
        """
        Dispatch a task for asynchronous execution.
        Returns a task ID that can be used to query the status or retrieve the result.
        """
        task_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        
        # We run the function in the thread pool executor
        future = loop.run_in_executor(self.executor, lambda: func(*args, **kwargs))
        self.tasks[task_id] = future
        
        # Optional callback to store results when done
        def _on_done(fut):
            try:
                self.results[task_id] = fut.result()
            except Exception as e:
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
        if timeout is not None:
            result = await asyncio.wait_for(future, timeout=timeout)
        else:
            result = await future
            
        if isinstance(result, Exception):
            raise result
        return result

    def get_status(self, task_id: str) -> str:
        """
        Check the status of a task without waiting.
        """
        if task_id not in self.tasks:
            return "UNKNOWN"
            
        future = self.tasks[task_id]
        if future.done():
            return "COMPLETED"
        return "RUNNING"
        
    def shutdown(self, wait: bool = True):
        """
        Shutdown the dispatcher and underlying executor.
        """
        self.executor.shutdown(wait=wait)
