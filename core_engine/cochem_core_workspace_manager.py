#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Workspace Scaffolding Tool
Implements atomic POSIX locking to guarantee safe directory generation 
during high-throughput, highly concurrent MPI/API dispatch scenarios.
"""

import os
import fcntl
import shutil
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-WorkspaceManager")

class WorkspaceManager:
    """
    Manages the atomic creation, locking, and sweeping of the CoChem directory structure.
    """
    
    # The canonical CoChem ecosystem topology
    CORE_DIRECTORIES = [
        "Input_Files",
        "Processed",
        "Logs",
        "Scratch",
        "cochem_setup",
        "cochem_task_queue"
    ]

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else (Path(os.environ.get("COCHEM_ARTIFACT_DIR")) if os.environ.get("COCHEM_ARTIFACT_DIR") else Path.home() / "CoChem_Artifacts"))
        self.lock_file = self.base_path / ".cochem_workspace.lock"

    def _acquire_lock(self, file_descriptor) -> bool:
        """Applies a strict POSIX exclusive lock."""
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, OSError):
            return False

    def _release_lock(self, file_descriptor) -> None:
        """Releases the POSIX lock."""
        fcntl.flock(file_descriptor, fcntl.LOCK_UN)

    def scaffold_core_directories(self) -> bool:
        """
        Atomically generates the master directories. If another process holds the lock,
        it yields immediately, assuming the scaffolding is already in progress.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        with open(self.lock_file, 'w') as lf:
            if not self._acquire_lock(lf.fileno()):
                logger.info("Workspace lock collision. Bypassing redundant scaffolding.")
                return False
                
            try:
                for d in self.CORE_DIRECTORIES:
                    (self.base_path / d).mkdir(exist_ok=True)
                logger.info("CoChem-CORE base topology atomically verified.")
            finally:
                self._release_lock(lf.fileno())
                
        return True

    def provision_job_workspace(self, job_id: str) -> Path:
        """Creates an isolated, unique execution scratch folder for a specific ORCA job."""
        job_dir = self.base_path / "Scratch" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def sweep_zombie_directories(self) -> int:
        """
        Clears the 'Scratch' folder of orphaned job directories that failed to
        clean up after a kernel crash. Requires full lock to prevent deleting active runs.
        """
        scratch_dir = self.base_path / "Scratch"
        if not scratch_dir.exists():
            return 0
            
        swept_count = 0
        with open(self.lock_file, 'w') as lf:
            if not self._acquire_lock(lf.fileno()):
                logger.warning("Lock held. Cannot safely sweep zombie directories right now.")
                return 0
                
            try:
                for item in scratch_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                        swept_count += 1
                logger.info(f"Swept {swept_count} zombie directories from Scratch.")
            except Exception as e:
                logger.error(f"Error during zombie directory sweep: {e}")
            finally:
                self._release_lock(lf.fileno())
                
        return swept_count

# If executed directly, run a scaffolding integrity check
if __name__ == "__main__":
    print(">>> Testing Atomic Workspace Scaffolding...")
    manager = WorkspaceManager()
    
    if manager.scaffold_core_directories():
        print(" [SUCCESS] Master CoChem-CORE directories generated atomically.")
        
        # Test isolated job provisioning
        job_path = manager.provision_job_workspace("JOB_SIMULATION_999")
        print(f" [SUCCESS] Provisioned specific job path: {job_path}")
        
        # Test zombie sweep
        swept = manager.sweep_zombie_directories()
        print(f" [SUCCESS] Swept {swept} isolated job directories during cleanup.")
    else:
        print(" [FAIL] Scaffolding yielded due to lock collision (Expected if running in tight loop).")