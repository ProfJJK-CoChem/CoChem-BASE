import subprocess
import threading
import queue

class TaskDispatcher:
    """Subprocess dispatcher and task queue management for CoChem-BASE"""
    
    def __init__(self):
        self.task_queue = queue.Queue()
        self.results = {}
        self.worker_thread = None
        self._stop_event = threading.Event()

    def submit_task(self, task_id, command):
        """Submit a shell command as a task."""
        self.task_queue.put((task_id, command))

    def start_worker(self):
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self._stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

    def stop_worker(self):
        self._stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task_id, command = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                # Dispatch subprocess
                print(f"[Dispatcher] Running task {task_id}: {command}")
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate()
                self.results[task_id] = {
                    "status": "success" if process.returncode == 0 else "error",
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": process.returncode
                }
            except Exception as e:
                self.results[task_id] = {
                    "status": "exception",
                    "error": str(e)
                }
            finally:
                self.task_queue.task_done()
