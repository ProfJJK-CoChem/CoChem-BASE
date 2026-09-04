# cochem_canvas_target: core_engine/cochem_core_job_manager.py
"""
Job manager module for CoChem-CORE.
Manages the lifecycle of computational chemistry jobs with temporal tiers and hardware awareness.
"""

import asyncio
import logging
import signal
import sys
import time
import atexit
import psutil
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JobConfig(BaseModel):
    command: List[str] = Field(default_factory=lambda: ["echo", "no command"])
    product_class: str = "Product_A_DeNovo"
    is_isotopologue: bool = False
    has_parent_anchor: bool = False
    floppy_monomer: bool = False
    atom_count: Optional[int] = None
    n_atoms: Optional[int] = None
    temporal_tier_override: Optional[int] = None
    max_duration_override: Optional[int] = None
    job_name: Optional[str] = None
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None

class JobInfo(BaseModel):
    config: JobConfig
    status: str
    created_at: float
    job_id: str
    temporal_tier: int
    max_duration: int
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    return_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None


class JobManager:
    """
    Manages the lifecycle of computational chemistry jobs with temporal tiers and hardware awareness.

    Implements 10 temporal wall-clock tiers from 10 seconds to 1 month, with SIGTERM/SIGKILL enforcement
    for proper job lifecycle management and resource control.
    """

    TEMPORAL_TIERS = [
        10,       # Tier 1: T1-10s (Conformer search / MLFF pre-relax)
        60,       # Tier 2: T1-1min (Fast screening / xTB Hessian)
        1800,     # Tier 3: T1-30min (Medium Opt / r2SCAN-3c)
        3600,     # Tier 4: T1-1h (Tight Opt / B97-3c / PBE0-D4)
        10800,    # Tier 5: T2-3h (PES scan / CI-NEB path)
        43200,    # Tier 6: T2-12h (DLPNO-CCSD(T) / High-level Opt)
        86400,    # Tier 7: T3-1d (Composite equilibrium geometry / B_e)
        259200,   # Tier 8: T3-3d (Full VPT2 anharmonic force field)
        604800,   # Tier 9: T4-1w (Active learning PES store construction)
        2592000   # Tier 10: T4-1mo (De novo benchmark target execution)
    ]

    def __init__(self, max_job_history: int = 1000, poll_interval: float = 0.1, **kwargs: Any) -> None:
        """Initialize the job manager."""
        self.jobs: Dict[str, JobInfo] = {}
        self.job_counter = 0
        self.active_processes: Dict[str, Dict[str, Any]] = {}
        self.max_job_history = max_job_history
        self.poll_interval = poll_interval
        atexit.register(self._cleanup_all_processes)

    def _cleanup_all_processes(self) -> None:
        """Atexit handler to ensure all running subprocesses are terminated upon exit."""
        for job_id, process_info in self.active_processes.items():
            process = process_info.get('process')
            if process and process.pid:
                self._kill_process_tree(process.pid)
            logger.info("Swept all zombie processes on exit.")

    def _kill_process_tree(self, pid: int) -> None:
        """Kill a process and all its children to prevent zombie processes."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess as _e:
                    logger.debug(f"Ignored exception: {_e}")
            try:
                parent.kill()
            except psutil.NoSuchProcess as _e:
                logger.debug(f"Ignored exception: {_e}")
        except psutil.NoSuchProcess as _e:
            logger.debug(f"Ignored exception: {_e}")

    async def submit_job(self, job_config_input: Union[Dict[str, Any], JobConfig]) -> str:
        """Submit a new job to the system with temporal tier assignment."""
        if isinstance(job_config_input, JobConfig):
            job_config = job_config_input
        else:
            try:
                job_config = JobConfig(**job_config_input)
            except ValidationError as e:
                logger.error(f"Invalid job configuration: {e}")
                raise ValueError(f"Invalid job configuration: {e}")

        self.purge_completed_jobs(max_age_seconds=86400.0)
        job_id = f"job_{self.job_counter}"
        self.job_counter += 1

        logger.info(f"📤 Submitting job {job_id}")

        temporal_tier = self._assign_temporal_tier(job_config)
        max_duration = job_config.max_duration_override if job_config.max_duration_override is not None else self.TEMPORAL_TIERS[temporal_tier - 1]

        # Enforce max_job_history
        while len(self.jobs) >= self.max_job_history:
            oldest_key = next(iter(self.jobs))
            del self.jobs[oldest_key]

        self.jobs[job_id] = JobInfo(
            config=job_config,
            status='submitted',
            created_at=time.time(),
            job_id=job_id,
            temporal_tier=temporal_tier,
            max_duration=max_duration
        )

        return job_id

    def _assign_temporal_tier(self, job_config: JobConfig) -> int:
        """
        Assign a temporal tier based on v4 Product Class decision tree & target accuracy windows (§1.1-1.5).
        Returns 1-based tier index (1 to 10).
        """
        if job_config.temporal_tier_override is not None:
            return job_config.temporal_tier_override

        product_class = job_config.product_class
        is_isotopologue = job_config.is_isotopologue
        has_parent_anchor = job_config.has_parent_anchor
        floppy_monomer = job_config.floppy_monomer
        atom_count = job_config.n_atoms if job_config.n_atoms is not None else (job_config.atom_count if job_config.atom_count is not None else 10)

        if product_class in ('Product_D_ActiveLearning', 'Class_D'):
            if atom_count > 50:
                return 10
            return 9

        if product_class in ('Product_C_Differences', 'Class_C') or is_isotopologue:
            if atom_count < 20:
                return 1
            else:
                return 2

        if product_class in ('Product_B_SemiExperimental', 'Class_B') or has_parent_anchor:
            if atom_count < 30:
                return 3
            else:
                return 4

        if floppy_monomer:
            if atom_count > 50:
                return 8
            return 6
        else:
            if atom_count < 15:
                return 4
            elif atom_count < 40:
                return 5
            elif atom_count < 80:
                return 6
            else:
                return 7

    def purge_completed_jobs(self, max_age_seconds: float = 3600.0) -> int:
        """Evict completed or failed jobs older than max_age_seconds from memory to prevent memory leak."""
        now = time.time()
        to_delete = []
        for job_id, info in self.jobs.items():
            if info.status in ('completed', 'failed', 'cancelled', 'timed_out'):
                completed_at = info.completed_at if info.completed_at else info.created_at
                if (now - completed_at) >= max_age_seconds:
                    to_delete.append(job_id)

        for jid in to_delete:
            del self.jobs[jid]
        return len(to_delete)

    def clear_history(self) -> int:
        """Clear all finished jobs from history."""
        to_delete = [jid for jid, info in self.jobs.items() if info.status in ('completed', 'failed', 'cancelled', 'timed_out')]
        for jid in to_delete:
            del self.jobs[jid]
        return len(to_delete)

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get the JobInfo instance for a specific job."""
        return self.jobs.get(job_id)

    def get_completed_jobs(self) -> List[JobInfo]:
        """Get all completed, failed, timed out, or cancelled jobs."""
        return [job for job in self.jobs.values() if job.status in ('completed', 'failed', 'cancelled', 'timed_out')]

    def get_failed_jobs(self) -> List[JobInfo]:
        """Get all failed jobs."""
        return [job for job in self.jobs.values() if job.status in ('failed', 'timed_out')]

    def get_running_jobs(self) -> List[JobInfo]:
        """Get all currently running jobs."""
        return [job for job in self.jobs.values() if job.status == 'running']

    async def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> Optional[JobInfo]:
        """Wait for a job to finish and return its JobInfo."""
        start_wait = time.time()
        while True:
            job = self.jobs.get(job_id)
            if not job:
                return None
            if job.status in ('completed', 'failed', 'cancelled', 'timed_out'):
                return job
            if timeout is not None and (time.time() - start_wait) > timeout:
                return job
            await asyncio.sleep(0.05)

    async def run_job(self, job_id: str, timeout: Optional[float] = None) -> Optional[JobInfo]:
        """Run a job asynchronously and wait for its completion."""
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found")
            return None

        job = self.jobs[job_id]
        if timeout is not None:
            job.max_duration = int(timeout)
        if job_id not in self.active_processes:
            await self.start_job(job_id)

        proc_info = self.active_processes.get(job_id)
        if proc_info and "task" in proc_info:
            await proc_info["task"]

        return self.jobs.get(job_id, job)

    async def start_job(self, job_id: str) -> None:
        """Start a submitted job using asyncio subprocess execution."""
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found")
            return

        job = self.jobs[job_id]
        logger.info(f"▶️  Starting job {job_id} with temporal tier {job.temporal_tier}")

        command = job.config.command
        if not command:
            job.status = 'failed'
            job.error = 'Job command list cannot be empty'
            job.completed_at = time.time()
            return

        import os
        if job.config.cwd and not os.path.isdir(job.config.cwd):
            job.status = 'failed'
            job.error = 'Specified working directory does not exist'
            job.completed_at = time.time()
            return

        try:
            merged_env = None
            if job.config.env:
                merged_env = os.environ.copy()
                merged_env.update(job.config.env)

            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=job.config.cwd,
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            job.status = 'running'
            job.started_at = time.time()

            task = asyncio.create_task(self._unified_reader(job_id, process, float(job.max_duration)))

            self.active_processes[job_id] = {
                'process': process,
                'start_time': time.time(),
                'max_duration': job.max_duration,
                'task': task,
            }

            logger.info(f"Job {job_id} started successfully")

        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            job.status = 'failed'
            job.error = str(e)
            job.completed_at = time.time()

    async def _unified_reader(
        self, job_id: str, process: asyncio.subprocess.Process, timeout: float
    ) -> Tuple[str, str, int]:
        """Consolidated single-task stream reader and timeout watchdog."""
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
            out_str = stdout_bytes.decode('utf-8', errors='replace')
            err_str = stderr_bytes.decode('utf-8', errors='replace')
            ret = process.returncode or 0
            if job_id in self.jobs:
                self.jobs[job_id].stdout = out_str
                self.jobs[job_id].stderr = err_str
                self.jobs[job_id].return_code = ret
            logger.info(f"Job {job_id} completed with return code {ret}")
            self._complete_job(job_id, ret)
            return out_str, err_str, ret
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Job {job_id} timeout reached ({timeout}s), terminating process tree")
            try:
                if process.pid:
                    self._kill_process_tree(process.pid)
            except Exception as sig_error:
                logger.error(f"Error terminating job {job_id}: {sig_error}")

            await process.wait()
            if job_id in self.jobs:
                self.jobs[job_id].status = 'timed_out'
                self.jobs[job_id].error = f"Job {job_id} exceeded temporal maximum duration ({timeout}s)"
                self.jobs[job_id].return_code = -1
            self._complete_job(job_id, -1, timed_out=True)
            return "", f"Job {job_id} exceeded temporal maximum duration ({timeout}s)", -1
        except Exception as e:
            logger.error(f"Error in unified reader for job {job_id}: {e}")
            self._complete_job(job_id, -1)
            return "", str(e), -1
        finally:
            if job_id in self.jobs:
                self.jobs[job_id].completed_at = time.time()
                self.jobs[job_id].duration = self.jobs[job_id].completed_at - (self.jobs[job_id].started_at or self.jobs[job_id].created_at)
            self.active_processes.pop(job_id, None)

    async def _enforce_timeout(self, job_id: str) -> None:
        """Deprecated alias pointing to unified reader task."""
        proc_info = self.active_processes.get(job_id)
        if proc_info and "task" in proc_info:
            await proc_info["task"]

    def _complete_job(self, job_id: str, return_code: int, timed_out: bool = False) -> None:
        """Mark a job as completed or failed and clean up resources."""
        if job_id in self.jobs:
            logger.info(f"✅ Completing job {job_id} with return code {return_code}")
            if timed_out:
                self.jobs[job_id].status = 'timed_out'
            elif self.jobs[job_id].status != 'cancelled':
                self.jobs[job_id].status = 'completed' if return_code == 0 else 'failed'
            self.jobs[job_id].completed_at = time.time()
            self.jobs[job_id].return_code = return_code
            self.jobs[job_id].duration = self.jobs[job_id].completed_at - (self.jobs[job_id].started_at or self.jobs[job_id].created_at)

        if job_id in self.active_processes:
            del self.active_processes[job_id]

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a specific job."""
        job = self.jobs.get(job_id)
        if job:
            return job.model_dump() if hasattr(job, "model_dump") else job.dict()
        return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job. Returns True if found and cancelled."""
        if job_id in self.jobs:
            logger.info(f"❌ Cancelling job {job_id}")
            self.jobs[job_id].status = 'cancelled'
            self.jobs[job_id].completed_at = time.time()

            if job_id in self.active_processes:
                try:
                    process = self.active_processes[job_id]['process']
                    if process and process.pid:
                        self._kill_process_tree(process.pid)
                    del self.active_processes[job_id]
                except Exception as e:
                    logger.error(f"Error cancelling job {job_id}: {e}")
            return True
        return False

    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all current jobs with optional status filter."""
        jobs_list = self.jobs.values()
        if status is not None:
            jobs_list = [j for j in jobs_list if j.status == status]
        return [job.model_dump() if hasattr(job, "model_dump") else job.dict() for job in jobs_list]

    async def monitor_active_jobs(self) -> None:
        """Monitor and report on active jobs."""
        while True:
            active_jobs = [job for job in self.jobs.values() if job.status == 'running']
            if active_jobs:
                logger.info(f"📊 Currently running jobs: {len(active_jobs)}")
                for job in active_jobs:
                    elapsed_time = time.time() - (job.started_at or time.time())
                    logger.info(f"   Job {job.job_id}: {elapsed_time:.1f}s elapsed")
            else:
                logger.info("📭 No active jobs")
            await asyncio.sleep(30)
