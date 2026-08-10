# cochem_canvas_target: core_engine/cochem_core_job_manager.py
"""
Job manager module for CoChem-CORE.
Manages the lifecycle of computational chemistry jobs with temporal tiers and hardware awareness.
"""

import asyncio
import signal
import sys
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class JobManager:
    """
    Manages the lifecycle of computational chemistry jobs with temporal tiers and hardware awareness.
    
    Implements 10 temporal wall-clock tiers from 10 seconds to 1 month, with SIGTERM/SIGKILL enforcement
    for proper job lifecycle management and resource control.
    """
    
    # Temporal tiers in seconds (10 authoritative v4 wall-clock budgets per §12.1)
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
    
    def __init__(self, max_job_history: int = 1000):
        """Initialize the job manager."""
        self.jobs = {}
        self.job_counter = 0
        self.active_processes = {}  # Track running subprocesses
        self.max_job_history = max_job_history
        
    async def submit_job(self, job_config: dict) -> str:
        """Submit a new job to the system with temporal tier assignment."""
        self.purge_completed_jobs(max_age_seconds=86400.0)
        job_id = f"job_{self.job_counter}"
        self.job_counter += 1
        
        logger.info(f"📤 Submitting job {job_id}")
        
        # Assign temporal tier based on job complexity or configuration
        temporal_tier = self._assign_temporal_tier(job_config)
        
        self.jobs[job_id] = {
            'config': job_config,
            'status': 'submitted',
            'created_at': time.time(),
            'job_id': job_id,
            'temporal_tier': temporal_tier,
            'max_duration': self.TEMPORAL_TIERS[temporal_tier - 1]  # Duration in seconds
        }
        
        return job_id
        
    def _assign_temporal_tier(self, job_config: dict) -> int:
        """
        Assign a temporal tier based on v4 Product Class decision tree & target accuracy windows (§1.1-1.5).
        Returns 1-based tier index (1 to 10).
        """
        product_class = job_config.get('product_class', 'Product_A_DeNovo')
        is_isotopologue = job_config.get('is_isotopologue', False)
        has_parent_anchor = job_config.get('has_parent_anchor', False)
        floppy_monomer = job_config.get('floppy_monomer', False)
        atom_count = job_config.get('n_atoms') or job_config.get('atom_count') or 10

        # Product Class C: Differences & Isotopologues (Shortcuts per §6.10)
        if product_class in ('Product_C_Differences', 'Class_C') or is_isotopologue:
            if atom_count < 20:
                return 1  # T1-10s
            else:
                return 2  # T1-1min

        # Product Class B: Semi-Experimental / Template Anchored (§1.3)
        if product_class in ('Product_B_SemiExperimental', 'Class_B') or has_parent_anchor:
            if atom_count < 30:
                return 3  # T1-30min
            else:
                return 4  # T1-1h

        # Product Class A: De Novo Absolute (§1.2)
        if floppy_monomer:
            if atom_count > 50:
                return 8  # T3-3d
            return 6     # T2-12h
        else:
            if atom_count < 15:
                return 4  # T1-1h
            elif atom_count < 40:
                return 5  # T2-3h
            elif atom_count < 80:
                return 6  # T2-12h
            else:
                return 7  # T3-1d

    def purge_completed_jobs(self, max_age_seconds: float = 3600.0) -> int:
        """Evict completed or failed jobs older than max_age_seconds from memory to prevent memory leak."""
        now = time.time()
        to_delete = []
        for job_id, info in self.jobs.items():
            if info.get('status') in ('completed', 'failed', 'cancelled'):
                completed_at = info.get('completed_at', info.get('created_at'))
                if (now - completed_at) > max_age_seconds:
                    to_delete.append(job_id)

        for jid in to_delete:
            del self.jobs[jid]
        return len(to_delete)
        
    async def start_job(self, job_id: str):
        """Start a submitted job using asyncio subprocess execution."""
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found")
            return
            
        job = self.jobs[job_id]
        logger.info(f"▶️  Starting job {job_id} with temporal tier {job['temporal_tier']}")
        
        try:
            # Get the command from job configuration
            command = job['config'].get('command', ['echo', 'no command'])
            
            # Execute the command asynchronously using subprocess
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.active_processes[job_id] = {
                'process': process,
                'start_time': time.time(),
                'max_duration': job['max_duration']
            }
            
            job['status'] = 'running'
            job['started_at'] = time.time()
            
            # Schedule the timeout enforcement
            asyncio.create_task(self._enforce_timeout(job_id))
            
            logger.info(f"Job {job_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")
            job['status'] = 'failed'
            
    async def _enforce_timeout(self, job_id: str):
        """Enforce timeout with asyncio.wait_for and platform-safe termination."""
        if job_id not in self.active_processes:
            return
            
        process_info = self.active_processes[job_id]
        process = process_info['process']
        max_duration = process_info['max_duration']
        
        try:
            # Wrap wait in asyncio.wait_for instead of busy polling loop
            await asyncio.wait_for(process.wait(), timeout=max_duration)
            logger.info(f"Job {job_id} completed with return code {process.returncode}")
            self._complete_job(job_id, process.returncode)

        except asyncio.TimeoutError:
            logger.warning(f"⏰ Job {job_id} timeout reached ({max_duration}s), terminating process")
            try:
                if sys.platform == "win32":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
                await asyncio.sleep(2)
                if process.returncode is None:
                    logger.warning(f"💥 Job {job_id} still running after terminate, killing process")
                    if sys.platform == "win32":
                        process.kill()
                    else:
                        process.send_signal(signal.SIGKILL)
            except Exception as sig_error:
                logger.error(f"Error terminating job {job_id}: {sig_error}")
            
            await process.wait()
            self._complete_job(job_id, process.returncode or -1)

        except Exception as e:
            logger.error(f"Error in timeout enforcement for job {job_id}: {e}")
            self._complete_job(job_id, -1)
            
    def _complete_job(self, job_id: str, return_code: int):
        """Mark a job as completed and clean up resources."""
        if job_id in self.jobs:
            logger.info(f"✅ Completing job {job_id} with return code {return_code}")
            self.jobs[job_id]['status'] = 'completed'
            self.jobs[job_id]['completed_at'] = time.time()
            self.jobs[job_id]['return_code'] = return_code
            
        # Clean up active process
        if job_id in self.active_processes:
            del self.active_processes[job_id]
            
    def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get the status of a specific job."""
        return self.jobs.get(job_id)
        
    def cancel_job(self, job_id: str):
        """Cancel a running or pending job."""
        if job_id in self.jobs:
            logger.info(f"❌ Cancelling job {job_id}")
            self.jobs[job_id]['status'] = 'cancelled'
            
            # If the job is running, terminate the process
            if job_id in self.active_processes:
                try:
                    process = self.active_processes[job_id]['process']
                    if sys.platform == "win32":
                        process.kill()
                    else:
                        process.send_signal(signal.SIGKILL)
                    del self.active_processes[job_id]
                except Exception as e:
                    logger.error(f"Error cancelling job {job_id}: {e}")

            
    def list_jobs(self) -> List[Dict]:
        """List all current jobs."""
        return list(self.jobs.values())
        
    async def monitor_active_jobs(self):
        """Monitor and report on active jobs."""
        while True:
            active_jobs = [job for job in self.jobs.values() if job['status'] == 'running']
            if active_jobs:
                logger.info(f"📊 Currently running jobs: {len(active_jobs)}")
                for job in active_jobs:
                    elapsed_time = time.time() - job['started_at']
                    logger.info(f"   Job {job['job_id']}: {elapsed_time:.1f}s elapsed")
            else:
                logger.info("📭 No active jobs")
            await asyncio.sleep(30)  # Check every 30 seconds

async def main():
    """Main entry point for the job manager."""
    logger.info("Starting CoChem-CORE Job Manager")
    
    job_manager = JobManager()
    
    # Example usage
    job_config1 = {
        'type': 'dft_calculation',
        'molecule': 'water.xyz',
        'method': 'B3LYP',
        'basis': 'def2-SVP',
        'command': ['echo', 'Running DFT calculation...']
    }
    
    job_config2 = {
        'type': 'quick_analysis',
        'command': ['sleep', '5']  # Quick test job
    }
    
    job_id1 = await job_manager.submit_job(job_config1)
    job_id2 = await job_manager.submit_job(job_config2)
    
    # Start jobs asynchronously
    await job_manager.start_job(job_id1)
    await job_manager.start_job(job_id2)
    
    # Monitor jobs for a while
    logger.info("Monitoring jobs...")
    await asyncio.sleep(10)
    
    # Cancel one job
    job_manager.cancel_job(job_id2)
    
    logger.info("Job manager completed")

if __name__ == "__main__":
    asyncio.run(main())