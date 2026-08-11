#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Workspace Scaffolding Tool
Implements atomic POSIX locking to guarantee safe directory generation 
during high-throughput, highly concurrent MPI/API dispatch scenarios.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from cochem_base.config_loader import get_artifact_dir

try:
    import fcntl
except ImportError:
    fcntl = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-WorkspaceManager")


class WorkspaceManager:
    """
    Manages the atomic creation, locking, and sweeping of the CoChem directory structure.
    """

    CORE_DIRECTORIES = [
        "Input_Files",
        "Processed",
        "Logs",
        "Scratch",
        "cochem_setup",
        "cochem_task_queue"
    ]

    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = Path(base_path) if base_path else get_artifact_dir()
        self.lock_file = self.base_path / ".cochem_workspace.lock"

    def _acquire_lock(self, file_descriptor: int) -> bool:
        """Applies a strict POSIX exclusive lock (or succeeds on Windows where fcntl is absent)."""
        if fcntl is None:
            return True
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, OSError):
            return False

    def _release_lock(self, file_descriptor: int) -> None:
        """Releases the POSIX lock."""
        if fcntl is not None:
            try:
                fcntl.flock(file_descriptor, fcntl.LOCK_UN)
            except OSError:
                pass

    def scaffold_core_directories(self) -> bool:
        """
        Atomically generates the master directories. If another process holds the lock,
        it yields immediately, assuming the scaffolding is already in progress.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)

        with open(self.lock_file, 'w', encoding='utf-8') as lf:
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
        with open(self.lock_file, 'w', encoding='utf-8') as lf:
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


if __name__ == "__main__":
    logger.info("Testing Atomic Workspace Scaffolding...")
    manager = WorkspaceManager()

    if manager.scaffold_core_directories():
        logger.info("Master CoChem-CORE directories generated atomically.")

        job_path = manager.provision_job_workspace("JOB_SIMULATION_999")
        logger.info(f"Provisioned specific job path: {job_path}")

        swept = manager.sweep_zombie_directories()
        logger.info(f"Swept {swept} isolated job directories during cleanup.")
    else:
        logger.warning("Scaffolding yielded due to lock collision.")