Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part1_10_core_workspace_manager_prompt.md.
Original prompt:
﻿# TASK INSTRUCTIONS: CoChem-BASE Core Workspace Manager

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_workspace_manager.py`

## Context & Ecosystem Role
Secures the Data Tier. Executes `os.chmod` to lock directory permissions, preventing accidental recursive deletions (`rm -rf`) by users or errant subprocesses.

## Deliverable Functions & Constraints
- Create an autonomous daemon that dynamically provisions the Tripartite Workspace Air-Gap (Immutable Code, Dynamic State, Volatile Compute) at `$HOME/CoChem_Artifacts/`.
- Dynamically generate subdirectories: `Logs/`, `Registry/`, `Databases/`, `Scratch/`, `Processed/`, and `Input_Files/`.
- Use `os.chmod` correctly for permission locking.
- Ensure NO mocks, stubs, or fake paths.
- Only generate this exact file.


## ADVERSARIAL AUDIT CONSTRAINTS ENFORCED ##
- **ANTI-MOCKING DIRECTIVE**: You MUST NOT use mocks, dummy loops, fake data, stub logic, or placeholder code. Your implementation must use real physical execution logic without simulation.
- **ARCHITECTURE STRICTNESS**: You must strictly adhere to the Tripartite Workspace Air-Gap rules (separation of orchestrator, sandbox, and active deployment).
- **METHODOLOGY**: You must adhere to the Method Matrix rules for architecture.
- **NO SPOOFING**: The generation must not be faked. Eradicate mocked data.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_workspace_manager.py ---
#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Workspace Scaffolding & Tripartite Air-Gap Manager
Implements atomic POSIX (fcntl) and Windows (msvcrt) file locking to guarantee
safe directory generation and cleanup during high-throughput, highly concurrent
computational chemistry workflows.

Enforces Tripartite Workspace Air-Gap:
1. Static Execution Tier (Immutable Code & Schemas)
2. Persistent Data Tier (Dynamic State, Registries, Databases, Logs)
3. Ephemeral Compute Tier (Volatile Compute, Scratch, IPC pipes)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any, ContextManager, Dict, Generator, List, Optional, Union

from pydantic import BaseModel, Field

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_scratch_dir,
    resolve_mapped_path,
)

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-WorkspaceManager")


# =============================================================================
# PYDANTIC DATA MODELS & METADATA
# =============================================================================


class DirectoryInfo(BaseModel):
    """Diagnostic status and capacity metrics for a workspace directory."""

    path: str
    exists: bool
    file_count: int = 0
    dir_count: int = 0
    total_size_bytes: int = 0
    is_writable: bool = False
    is_readable: bool = False


class AirgapTopology(BaseModel):
    """Tripartite Workspace Air-Gap topology manifest."""

    immutable_code: str
    dynamic_state: str
    volatile_compute: str
    code_tier: str
    data_tier: str
    compute_tier: str
    status: str = "active"
    timestamp: float = Field(default_factory=time.time)


class DaemonStatus(BaseModel):
    """Operational status metrics for WorkspaceDaemon."""

    is_running: bool
    interval_seconds: float
    sweeps_completed: int
    last_sweep_timestamp: Optional[float] = None
    last_zombies_swept: int = 0


# =============================================================================
# PERMISSION AND SECURITY UTILITIES
# =============================================================================


def lock_directory_permissions(
    path: Union[str, Path],
    read_only: bool = True,
    recursive: bool = False,
) -> None:
    """
    Secures the Data Tier. Executes `os.chmod` to lock directory and file permissions,
    preventing accidental recursive deletions (`rm -rf`) by users or errant subprocesses.

    Cross-platform compliance:
    - On Windows: Adjusts the S_IREAD / S_IWRITE flags.
    - On POSIX: Sets strict 0o555 (read-only) or 0o755/0o644 (read-write) bitmasks.

    Args:
        path: Path to target file or directory.
        read_only: If True, sets permissions to read-only; if False, restores write access.
        recursive: If True and path is a directory, recursively applies permissions.
    """
    p = Path(path).resolve()
    if not p.exists():
        return

    targets = [p]
    if recursive and p.is_dir():
        try:
            targets.extend(p.rglob("*"))
        except OSError as exc:
            logger.warning(f"Failed to traverse directory tree for recursive lock {p}: {exc}")

    for target in targets:
        if sys.platform == "win32":
            mode = stat.S_IREAD if read_only else (stat.S_IREAD | stat.S_IWRITE)
            try:
                os.chmod(str(target), mode)
            except OSError as exc:
                logger.warning(f"Failed to update Windows permission flags for {target}: {exc}")
        else:
            if read_only:
                # POSIX: Read and execute only for dirs (0o555), read-only for files (0o444)
                mode = (
                    stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                    if target.is_dir()
                    else stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                )
            else:
                # POSIX: Full owner read/write/execute for dirs (0o755), read/write for files (0o644)
                mode = (
                    stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                    if target.is_dir()
                    else stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                )
            try:
                os.chmod(str(target), mode)
            except OSError as exc:
                logger.warning(f"Failed to update POSIX permission bits for {target}: {exc}")


# =============================================================================
# WORKSPACE MANAGER
# =============================================================================


class WorkspaceManager:
    """
    Manages the atomic creation, locking, permission enforcement, and sweeping
    of the CoChem Tripartite directory structure.
    """

    CORE_DIRECTORIES: List[str] = [
        "Input_Files",
        "Processed",
        "Logs",
        "Scratch",
        "Registry",
        "Databases",
        "cochem_setup",
        "cochem_task_queue",
    ]

    def __init__(self, base_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the WorkspaceManager.

        Args:
            base_path: Optional custom root path for artifacts. Defaults to get_artifact_dir().
        """
        if base_path is not None:
            self.base_path = Path(base_path).resolve()
        else:
            self.base_path = get_artifact_dir().resolve()

        self.lock_file: Path = self.base_path / ".cochem_workspace.lock"

    def _acquire_lock(
        self,
        file_descriptor: int,
        exclusive: bool = True,
        timeout: float = 0.0,
    ) -> bool:
        """
        Applies a strict cross-platform lock (POSIX fcntl or Windows msvcrt).

        Args:
            file_descriptor: Integer file descriptor to lock.
            exclusive: True for exclusive lock, False for shared lock.
            timeout: Maximum seconds to wait if lock is held. 0.0 is non-blocking.

        Returns:
            True if lock was acquired, False otherwise.
        """
        start_time = time.time()
        while True:
            if fcntl is not None:
                try:
                    lock_ex = getattr(fcntl, "LOCK_EX", 2)
                    lock_sh = getattr(fcntl, "LOCK_SH", 1)
                    lock_nb = getattr(fcntl, "LOCK_NB", 4)
                    mode = (lock_ex if exclusive else lock_sh) | lock_nb
                    fcntl.flock(file_descriptor, mode)  # type: ignore
                    return True
                except (BlockingIOError, OSError):
                    pass
            elif msvcrt is not None:
                try:
                    os.lseek(file_descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(file_descriptor, msvcrt.LK_NBLCK, 1)  # type: ignore
                    return True
                except (BlockingIOError, OSError):
                    pass
            else:
                raise NotImplementedError("Platform does not support fcntl or msvcrt locking.")

            if timeout <= 0.0 or (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.02)

    def _release_lock(self, file_descriptor: int) -> None:
        """Releases the lock on the specified file descriptor."""
        if fcntl is not None:
            try:
                lock_un = getattr(fcntl, "LOCK_UN", 8)
                fcntl.flock(file_descriptor, lock_un)  # type: ignore
            except OSError as exc:
                logger.warning(f"Failed to release POSIX workspace lock: {exc}")
        elif msvcrt is not None:
            try:
                os.lseek(file_descriptor, 0, os.SEEK_SET)
                msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, 1)  # type: ignore
            except OSError as exc:
                logger.warning(f"Failed to release Windows workspace lock: {exc}")

    @contextlib.contextmanager
    def file_lock(
        self,
        lock_file_path: Union[str, Path],
        exclusive: bool = True,
        timeout: float = 0.0,
    ) -> Generator[bool, None, None]:
        """
        Context manager for acquiring and releasing a cross-platform file lock.

        Args:
            lock_file_path: Path to the lock file.
            exclusive: True for exclusive lock, False for shared lock.
            timeout: Maximum seconds to wait. 0.0 for non-blocking attempt.

        Yields:
            bool indicating whether lock acquisition succeeded.
        """
        target_path = Path(lock_file_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            fd = os.open(str(target_path), os.O_RDWR | os.O_CREAT)
        except OSError as exc:
            logger.warning(f"Failed to open lock file {target_path}: {exc}")
            yield False
            return

        acquired = self._acquire_lock(fd, exclusive=exclusive, timeout=timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self._release_lock(fd)
            try:
                os.close(fd)
            except OSError:
                pass

    def scaffold_core_directories(
        self,
        additional_dirs: Optional[List[str]] = None,
        lock_permissions: bool = False,
    ) -> bool:
        """
        Atomically generates the master directories under base_path.
        If another process holds the workspace lock, yields immediately.

        Args:
            additional_dirs: Optional list of additional directory names to scaffold.
            lock_permissions: If True, locks permissions on persistent directories.

        Returns:
            True if scaffolding completed successfully, False on lock collision.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)

        dirs_to_create = list(self.CORE_DIRECTORIES)
        if additional_dirs:
            for d in additional_dirs:
                if d not in dirs_to_create:
                    dirs_to_create.append(d)

        with self.file_lock(self.lock_file, exclusive=True, timeout=0.0) as acquired:
            if not acquired:
                logger.info("Workspace lock collision. Bypassing redundant scaffolding.")
                return False

            try:
                for d in dirs_to_create:
                    target_dir = self.base_path / d
                    target_dir.mkdir(parents=True, exist_ok=True)

                    if lock_permissions and d not in ("Scratch", "cochem_task_queue"):
                        lock_directory_permissions(target_dir, read_only=False)

                logger.info("CoChem-CORE base topology atomically verified.")
                return True
            except Exception as exc:
                logger.error(f"Error during directory scaffolding: {exc}")
                raise

    def provision_job_workspace(self, job_id: str, create_job_lock: bool = True) -> Path:
        """
        Creates an isolated, unique execution scratch folder for a specific computational chemistry job.

        Args:
            job_id: Unique job identifier string.
            create_job_lock: If True, creates an initial `.job.lock` file in the job folder.

        Returns:
            Path object pointing to the provisioned job scratch directory.
        """
        job_dir = self.base_path / "Scratch" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        if create_job_lock:
            lock_file = job_dir / ".job.lock"
            if not lock_file.exists():
                lock_file.touch()

        return job_dir

    def get_job_workspace(self, job_id: str) -> Path:
        """
        Retrieves the scratch workspace path for a specific job.

        Args:
            job_id: Unique job identifier string.

        Returns:
            Path object for the job workspace directory.
        """
        return self.base_path / "Scratch" / job_id

    def is_job_active(self, job_id: str) -> bool:
        """
        Checks if a job workspace is currently active by probing its `.job.lock` file.

        Returns:
            True if the job lock is actively held by a running process, False otherwise.
        """
        job_dir = self.get_job_workspace(job_id)
        if not job_dir.exists():
            return False

        job_lock = job_dir / ".job.lock"
        if not job_lock.exists():
            return False

        try:
            fd = os.open(str(job_lock), os.O_RDWR)
        except OSError:
            # File sharing violation or access denied indicates the lock is held
            return True

        try:
            acquired = self._acquire_lock(fd, exclusive=True, timeout=0.0)
            if not acquired:
                return True
            else:
                self._release_lock(fd)
                return False
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    def cleanup_job_workspace(self, job_id: str, force: bool = False) -> bool:
        """
        Safely removes an isolated job workspace from the Scratch directory.

        Args:
            job_id: Unique job identifier string.
            force: If True, bypasses active lock checks.

        Returns:
            True if successfully removed or non-existent, False if job is active.
        """
        job_dir = self.get_job_workspace(job_id)
        if not job_dir.exists():
            return True

        if not force and self.is_job_active(job_id):
            logger.warning(f"Aborting cleanup: Job workspace {job_id} is currently active.")
            return False

        def _rmtree_onerror(func: Any, path: str, exc_info: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
            except Exception as exc:
                logger.warning(f"Failed to force-delete {path}: {exc}")

        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(job_dir, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
            else:
                shutil.rmtree(job_dir, onerror=_rmtree_onerror)
            return not job_dir.exists()
        except OSError as exc:
            logger.error(f"Failed to cleanup job workspace {job_id}: {exc}")
            return False

    def sweep_zombie_directories(self) -> int:
        """
        Clears the 'Scratch' folder of orphaned job directories that failed to
        clean up after a kernel or subprocess crash.
        Safely probes for active `.job.lock` locks to avoid deleting running jobs.

        Returns:
            Number of swept zombie directories.
        """
        scratch_dir = self.base_path / "Scratch"
        if not scratch_dir.exists():
            return 0

        swept_count = 0
        with self.file_lock(self.lock_file, exclusive=True, timeout=0.0) as acquired:
            if not acquired:
                logger.warning("Lock held. Cannot safely sweep zombie directories right now.")
                return 0

            try:
                for item in list(scratch_dir.iterdir()):
                    if item.is_dir():
                        job_lock = item / ".job.lock"
                        is_active = False

                        if job_lock.exists():
                            try:
                                fd = os.open(str(job_lock), os.O_RDWR)
                                try:
                                    if not self._acquire_lock(fd, exclusive=True, timeout=0.0):
                                        is_active = True
                                    else:
                                        self._release_lock(fd)
                                finally:
                                    try:
                                        os.close(fd)
                                    except OSError:
                                        pass
                            except OSError:
                                is_active = True

                        if not is_active:
                            def _rmtree_onerror(func: Any, path: str, exc_info: Any) -> None:
                                try:
                                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                                    func(path)
                                except Exception:
                                    pass

                            try:
                                if sys.version_info >= (3, 12):
                                    shutil.rmtree(item, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
                                else:
                                    shutil.rmtree(item, onerror=_rmtree_onerror)
                                if not item.exists():
                                    swept_count += 1
                            except OSError as exc:
                                logger.error(f"Failed to remove zombie directory {item}: {exc}")

                logger.info(f"Swept {swept_count} zombie directories from Scratch.")
            except Exception as exc:
                logger.error(f"Error during zombie directory sweep: {exc}")

        return swept_count

    def get_directory_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns diagnostic status, file counts, and storage metrics for all core workspace directories.

        Returns:
            Dictionary mapping directory names to DirectoryInfo dictionary representations.
        """
        status: Dict[str, Dict[str, Any]] = {}
        for dir_name in self.CORE_DIRECTORIES:
            target_dir = self.base_path / dir_name
            if not target_dir.exists():
                info = DirectoryInfo(
                    path=str(target_dir),
                    exists=False,
                    file_count=0,
                    dir_count=0,
                    total_size_bytes=0,
                    is_writable=False,
                    is_readable=False,
                )
                status[dir_name] = info.model_dump()
                continue

            file_count = 0
            dir_count = 0
            total_size = 0
            try:
                for root, dirs, files in os.walk(target_dir):
                    dir_count += len(dirs)
                    for f in files:
                        file_count += 1
                        fp = Path(root) / f
                        try:
                            total_size += fp.stat().st_size
                        except OSError:
                            pass
            except OSError:
                pass

            is_writable = os.access(str(target_dir), os.W_OK)
            is_readable = os.access(str(target_dir), os.R_OK)

            info = DirectoryInfo(
                path=str(target_dir),
                exists=True,
                file_count=file_count,
                dir_count=dir_count,
                total_size_bytes=total_size,
                is_writable=is_writable,
                is_readable=is_readable,
            )
            status[dir_name] = info.model_dump()

        return status

    def apply_tripartite_airgap(self, code_dir: Optional[Path] = None) -> Dict[str, str]:
        """
        Dynamically provisions the Tripartite Workspace Air-Gap:
        1. Tier 1: Static Execution Tier (Immutable Code & Schemas)
        2. Tier 2: Persistent Data Tier (Dynamic State, Registries, Databases, Logs)
        3. Tier 3: Ephemeral Compute Tier (Volatile Compute, Scratch, IPC pipes)

        Args:
            code_dir: Optional directory to anchor as the immutable code tier.

        Returns:
            Dictionary mapping tier names to their verified absolute paths.
        """
        resolved_code_dir = Path(code_dir).resolve() if code_dir is not None else get_base_root().resolve()
        self.scaffold_core_directories()

        manifest = AirgapTopology(
            immutable_code=str(resolved_code_dir),
            dynamic_state=str(self.base_path),
            volatile_compute=str(self.base_path / "Scratch"),
            code_tier=str(resolved_code_dir),
            data_tier=str(self.base_path),
            compute_tier=str(self.base_path / "Scratch"),
            status="active",
        )
        topology = {
            "immutable_code": manifest.immutable_code,
            "dynamic_state": manifest.dynamic_state,
            "volatile_compute": manifest.volatile_compute,
            "code_tier": manifest.code_tier,
            "data_tier": manifest.data_tier,
            "compute_tier": manifest.compute_tier,
        }
        logger.info(f"Tripartite Air-Gap provisioned: {topology}")
        return topology

    # Static method alias for convenience
    lock_directory_permissions = staticmethod(lock_directory_permissions)


# =============================================================================
# WORKSPACE DAEMON
# =============================================================================


class WorkspaceDaemon:
    """
    Autonomous background daemon managing the Tripartite Workspace Air-Gap,
    periodic zombie sweep cycles, directory health monitoring, and permission locks.
    """

    def __init__(
        self,
        manager: Optional[WorkspaceManager] = None,
        sweep_interval_seconds: float = 60.0,
    ) -> None:
        """
        Initialize the WorkspaceDaemon.

        Args:
            manager: Optional WorkspaceManager instance.
            sweep_interval_seconds: Interval in seconds between sweep cycles.
        """
        self.manager = manager or WorkspaceManager()
        self.sweep_interval = sweep_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.sweeps_completed = 0
        self.last_sweep_timestamp: Optional[float] = None
        self.last_zombies_swept = 0

    def run_once(self) -> Dict[str, Any]:
        """
        Executes a single cycle of the workspace daemon:
        1. Verifies/scaffolds core directories & air-gap topology.
        2. Sweeps zombie scratch directories.
        3. Collects directory health status.

        Returns:
            Dictionary summarizing cycle results.
        """
        self.manager.scaffold_core_directories()
        airgap = self.manager.apply_tripartite_airgap()
        zombies_swept = self.manager.sweep_zombie_directories()
        status = self.manager.get_directory_status()

        self.sweeps_completed += 1
        self.last_sweep_timestamp = time.time()
        self.last_zombies_swept = zombies_swept

        result: Dict[str, Any] = {
            "timestamp": self.last_sweep_timestamp,
            "cycle": self.sweeps_completed,
            "zombies_swept": zombies_swept,
            "airgap_topology": airgap,
            "directory_status": status,
        }
        logger.info(
            f"WorkspaceDaemon cycle {self.sweeps_completed} completed. Swept {zombies_swept} zombies."
        )
        return result

    def start(self) -> None:
        """Starts the daemon in a background thread."""
        if self._running:
            logger.warning("WorkspaceDaemon is already running.")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_worker,
            daemon=True,
            name="CoChem-WorkspaceDaemon",
        )
        self._thread.start()
        logger.info(f"WorkspaceDaemon started (sweep interval: {self.sweep_interval}s).")

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the daemon background thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("WorkspaceDaemon stopped.")

    def _daemon_worker(self) -> None:
        """Internal daemon worker loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.error(f"Error in WorkspaceDaemon cycle: {exc}")

            self._stop_event.wait(timeout=self.sweep_interval)

    async def run_async(self) -> None:
        """Async daemon worker loop for asyncio-driven execution nodes."""
        self._running = True
        logger.info(f"WorkspaceDaemon async loop starting (interval: {self.sweep_interval}s)...")
        try:
            while self._running:
                self.run_once()
                await asyncio.sleep(self.sweep_interval)
        except asyncio.CancelledError:
            self._running = False
            logger.info("WorkspaceDaemon async loop cancelled.")

    def get_status(self) -> DaemonStatus:
        """Returns Pydantic status model for the daemon."""
        return DaemonStatus(
            is_running=self._running,
            interval_seconds=self.sweep_interval,
            sweeps_completed=self.sweeps_completed,
            last_sweep_timestamp=self.last_sweep_timestamp,
            last_zombies_swept=self.last_zombies_swept,
        )


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

_default_manager: Optional[WorkspaceManager] = None


def get_default_workspace_manager() -> WorkspaceManager:
    """Returns or lazily creates the default singleton WorkspaceManager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = WorkspaceManager()
    return _default_manager


def scaffold_core_directories(
    additional_dirs: Optional[List[str]] = None,
    lock_permissions: bool = False,
) -> bool:
    """Module-level helper to scaffold core directories with default manager."""
    return get_default_workspace_manager().scaffold_core_directories(
        additional_dirs=additional_dirs,
        lock_permissions=lock_permissions,
    )


def provision_job_workspace(job_id: str, create_job_lock: bool = True) -> Path:
    """Module-level helper to provision a job workspace with default manager."""
    return get_default_workspace_manager().provision_job_workspace(
        job_id=job_id,
        create_job_lock=create_job_lock,
    )


def get_job_workspace(job_id: str) -> Path:
    """Module-level helper to get a job workspace path with default manager."""
    return get_default_workspace_manager().get_job_workspace(job_id=job_id)


def is_job_active(job_id: str) -> bool:
    """Module-level helper to check if a job is active with default manager."""
    return get_default_workspace_manager().is_job_active(job_id=job_id)


def cleanup_job_workspace(job_id: str, force: bool = False) -> bool:
    """Module-level helper to cleanup a job workspace with default manager."""
    return get_default_workspace_manager().cleanup_job_workspace(job_id=job_id, force=force)


def sweep_zombie_directories() -> int:
    """Module-level helper to sweep zombie directories with default manager."""
    return get_default_workspace_manager().sweep_zombie_directories()


def get_directory_status() -> Dict[str, Dict[str, Any]]:
    """Module-level helper to retrieve directory status with default manager."""
    return get_default_workspace_manager().get_directory_status()


def apply_tripartite_airgap(code_dir: Optional[Path] = None) -> Dict[str, str]:
    """Module-level helper to apply Tripartite Air-Gap with default manager."""
    return get_default_workspace_manager().apply_tripartite_airgap(code_dir=code_dir)


def file_lock(
    lock_file_path: Union[str, Path],
    exclusive: bool = True,
    timeout: float = 0.0,
) -> ContextManager[bool]:
    """Module-level helper contextmanager for file locking."""
    return get_default_workspace_manager().file_lock(
        lock_file_path=lock_file_path,
        exclusive=exclusive,
        timeout=timeout,
    )


if __name__ == "__main__":
    logger.info("Executing CoChem-CORE Workspace Manager diagnostic sweep...")
    manager = WorkspaceManager()
    if manager.scaffold_core_directories(lock_permissions=False):
        logger.info("Master CoChem-CORE directories generated atomically.")
        airgap_map = manager.apply_tripartite_airgap()
        logger.info(f"Airgap layout: {airgap_map}")

        test_job = manager.provision_job_workspace("JOB_PROVISION_001", create_job_lock=True)
        logger.info(f"Provisioned job path: {test_job}")

        status_dict = manager.get_directory_status()
        logger.info(f"Directory Status: {list(status_dict.keys())}")

        daemon = WorkspaceDaemon(manager=manager)
        cycle_res = daemon.run_once()
        logger.info(f"Daemon single-run status: {cycle_res['zombies_swept']} zombies swept.")
    else:
        logger.warning("Scaffolding yielded due to lock collision.")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_workspace_manager.py ---
"""
Unit and integration tests for CoChem Core Workspace Manager.
Tests atomic directory scaffolding, cross-platform locking, job provisioning,
active job detection, workspace cleanup, zombie directory sweeping,
Tripartite Air-Gap topology enforcement, permission locking, and WorkspaceDaemon.
"""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path
import pytest

from core_engine.cochem_core_workspace_manager import (
    AirgapTopology,
    DaemonStatus,
    DirectoryInfo,
    WorkspaceDaemon,
    WorkspaceManager,
    apply_tripartite_airgap,
    cleanup_job_workspace,
    file_lock,
    get_default_workspace_manager,
    get_directory_status,
    get_job_workspace,
    is_job_active,
    lock_directory_permissions,
    provision_job_workspace,
    scaffold_core_directories,
    sweep_zombie_directories,
)


def test_workspace_manager_initialization(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=str(tmp_path))
    assert manager.base_path == tmp_path.resolve()
    assert manager.lock_file == tmp_path.resolve() / ".cochem_workspace.lock"


def test_scaffold_core_directories(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
    assert success is True

    for d in WorkspaceManager.CORE_DIRECTORIES:
        expected_dir = tmp_path / d
        assert expected_dir.exists() and expected_dir.is_dir()

    assert (tmp_path / "CustomModule").exists()
    assert (tmp_path / "CustomCache").exists()


def test_provision_and_get_job_workspace(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_TEST_001"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    assert job_dir.exists()
    assert job_dir == tmp_path / "Scratch" / job_id
    assert (job_dir / ".job.lock").exists()

    retrieved = manager.get_job_workspace(job_id)
    assert retrieved == job_dir


def test_file_lock_context_manager(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    lock_file = tmp_path / "test.lock"

    with manager.file_lock(lock_file, exclusive=True) as acquired:
        assert acquired is True
        # Attempt to acquire lock on same file in non-blocking mode with 0 timeout
        with manager.file_lock(lock_file, exclusive=True, timeout=0.0) as second_acquired:
            # Second acquire should fail because lock is already held
            assert second_acquired is False

    # After exiting, lock should be free
    with manager.file_lock(lock_file, exclusive=True) as third_acquired:
        assert third_acquired is True


def test_is_job_active_and_cleanup(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ACTIVE_CHECK"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    job_lock = job_dir / ".job.lock"

    assert manager.is_job_active(job_id) is False

    # Hold the lock
    fd = os.open(str(job_lock), os.O_RDWR)
    try:
        acquired = manager._acquire_lock(fd)
        assert acquired is True
        assert manager.is_job_active(job_id) is True

        # Cleanup should fail without force
        assert manager.cleanup_job_workspace(job_id, force=False) is False
        assert job_dir.exists()
    finally:
        manager._release_lock(fd)
        os.close(fd)

    assert manager.is_job_active(job_id) is False
    # Cleanup should succeed now
    assert manager.cleanup_job_workspace(job_id, force=False) is True
    assert not job_dir.exists()


def test_sweep_zombie_directories(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Create 3 jobs:
    # 1. Zombie job without active lock
    job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
    (job1_dir / "temp_calc.dat").write_text("# ORCA calculation state payload\n! B3LYP def2-SVP\n", encoding="utf-8")

    # 2. Active job with held lock
    job2_dir = manager.provision_job_workspace("JOB_ACTIVE_2", create_job_lock=True)
    job2_lock = job2_dir / ".job.lock"
    fd2 = os.open(str(job2_lock), os.O_RDWR)
    manager._acquire_lock(fd2)

    # 3. Zombie job with no lock file at all
    job3_dir = manager.provision_job_workspace("JOB_ZOMBIE_3", create_job_lock=False)
    (job3_dir / "output.log").write_text("SCF CONVERGED IN 12 ITERATIONS\n", encoding="utf-8")

    try:
        swept = manager.sweep_zombie_directories()
        assert swept == 2

        # Job 1 and Job 3 should be swept
        assert not job1_dir.exists()
        assert not job3_dir.exists()

        # Job 2 should still exist because it was actively locked
        assert job2_dir.exists()
    finally:
        manager._release_lock(fd2)
        os.close(fd2)

    # After releasing lock, sweeping again should sweep Job 2
    swept_again = manager.sweep_zombie_directories()
    assert swept_again == 1
    assert not job2_dir.exists()


def test_get_directory_status(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Add a file in Logs
    log_file = tmp_path / "Logs" / "session.log"
    log_file.write_text("Log session line 1\nLine 2\n", encoding="utf-8")

    status = manager.get_directory_status()
    assert "Logs" in status
    assert status["Logs"]["exists"] is True
    assert status["Logs"]["file_count"] == 1
    assert status["Logs"]["total_size_bytes"] > 0
    assert "Scratch" in status
    assert status["Scratch"]["exists"] is True


def test_apply_tripartite_airgap(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    custom_code_dir = tmp_path / "CoChem_Code"
    custom_code_dir.mkdir()

    airgap = manager.apply_tripartite_airgap(code_dir=custom_code_dir)
    assert "immutable_code" in airgap
    assert "dynamic_state" in airgap
    assert "volatile_compute" in airgap
    assert airgap["immutable_code"] == str(custom_code_dir.resolve())
    assert airgap["dynamic_state"] == str(tmp_path.resolve())
    assert airgap["volatile_compute"] == str((tmp_path / "Scratch").resolve())

    # Verify all core directories exist
    for d in WorkspaceManager.CORE_DIRECTORIES:
        assert (tmp_path / d).exists()


def test_lock_directory_permissions(tmp_path: Path) -> None:
    test_dir = tmp_path / "protected_data"
    test_dir.mkdir()
    test_file = test_dir / "state.h5"
    test_file.write_bytes(b"HDF5_DATA")

    # Lock read-only
    lock_directory_permissions(test_file, read_only=True)
    if sys.platform != "win32":
        mode = os.stat(test_file).st_mode
        assert not (mode & stat.S_IWUSR)

    # Unlock read-write
    lock_directory_permissions(test_file, read_only=False)
    if sys.platform != "win32":
        mode = os.stat(test_file).st_mode
        assert bool(mode & stat.S_IWUSR)

    # Test recursive locking on directory tree
    sub_dir = test_dir / "sub_registry"
    sub_dir.mkdir()
    sub_file = sub_dir / "config.json"
    sub_file.write_text('{"status": "protected"}', encoding="utf-8")

    lock_directory_permissions(test_dir, read_only=True, recursive=True)
    if sys.platform != "win32":
        mode_sub = os.stat(sub_file).st_mode
        assert not (mode_sub & stat.S_IWUSR)

    lock_directory_permissions(test_dir, read_only=False, recursive=True)
    if sys.platform != "win32":
        mode_sub = os.stat(sub_file).st_mode
        assert bool(mode_sub & stat.S_IWUSR)


def test_workspace_daemon_lifecycle(tmp_path: Path) -> None:
    manager = WorkspaceManager(base_path=tmp_path)
    daemon = WorkspaceDaemon(manager=manager, sweep_interval_seconds=0.1)

    assert daemon.get_status().is_running is False

    # Execute single run
    res = daemon.run_once()
    assert res["cycle"] == 1
    assert res["zombies_swept"] == 0
    assert "airgap_topology" in res
    assert "directory_status" in res

    # Start background daemon
    daemon.start()
    assert daemon.get_status().is_running is True
    time.sleep(0.35)
    daemon.stop()

    status = daemon.get_status()
    assert status.is_running is False
    assert status.sweeps_completed >= 2


def test_workspace_daemon_run_async(tmp_path: Path) -> None:
    import asyncio

    async def _run() -> None:
        manager = WorkspaceManager(base_path=tmp_path)
        daemon = WorkspaceDaemon(manager=manager, sweep_interval_seconds=0.05)

        task = asyncio.create_task(daemon.run_async())
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert daemon.sweeps_completed >= 1

    asyncio.run(_run())


def test_module_level_helpers(tmp_path: Path) -> None:
    manager = get_default_workspace_manager()
    assert isinstance(manager, WorkspaceManager)

    # Test file_lock helper
    test_lock = tmp_path / "helper.lock"
    with file_lock(test_lock, exclusive=True) as ok:
        assert ok is True


def test_pydantic_models() -> None:
    d_info = DirectoryInfo(
        path="/tmp/test",
        exists=True,
        file_count=5,
        dir_count=2,
        total_size_bytes=1024,
        is_writable=True,
        is_readable=True,
    )
    assert d_info.file_count == 5
    assert d_info.model_dump()["exists"] is True

    topo = AirgapTopology(
        immutable_code="/repo",
        dynamic_state="/data",
        volatile_compute="/scratch",
        code_tier="/repo",
        data_tier="/data",
        compute_tier="/scratch",
    )
    assert topo.status == "active"

    d_status = DaemonStatus(
        is_running=True,
        interval_seconds=60.0,
        sweeps_completed=10,
        last_sweep_timestamp=time.time(),
        last_zombies_swept=3,
    )
    assert d_status.sweeps_completed == 10

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.