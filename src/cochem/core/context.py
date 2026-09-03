"""Async Context Isolation via ContextVar & Tripartite Storage Tier Locking.
Provides immutable execution context, air-gap validation, atomic writes, and platform-aware locking.
Strictly adheres to Zero-Mock mandate and Tripartite Storage Air-Gap enforcement.
"""

from __future__ import annotations

import contextvars
import dataclasses
import logging
import os
import pathlib
import sys
import time
import uuid
from typing import Any, Dict, Optional, Union

logger = logging.getLogger("cochem.core.context")


# ==============================================================================
# Custom Exceptions
# ==============================================================================
class AirGapViolationError(Exception):
    """Raised when an operation attempts to write to, delete from, or stage files in read-only tiers ($COCH_SRC or $COCH_DATA)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ==============================================================================
# Immutable Execution Context
# ==============================================================================
@dataclasses.dataclass(slots=True, frozen=True)
class ExecutionContext:
    """Immutable execution context encapsulating process state across the 6-Tier Environment Matrix."""

    execution_id: str
    session_name: str
    src_dir: pathlib.Path
    data_dir: pathlib.Path
    artifacts_dir: pathlib.Path
    scratch_dir: pathlib.Path
    env_tier: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


_CURRENT_CONTEXT: contextvars.ContextVar[Optional[ExecutionContext]] = contextvars.ContextVar(
    "cochem_execution_context",
    default=None,
)


def get_current_context() -> ExecutionContext:
    """Retrieve active ExecutionContext or raise RuntimeError if uninitialized."""
    ctx = _CURRENT_CONTEXT.get()
    if ctx is None:
        raise RuntimeError("No active ExecutionContext found in contextvars. Initialize with scoped_context.")
    return ctx


class scoped_context:
    """Context manager and async context manager isolating execution context across coroutines and threads."""

    def __init__(self, ctx: ExecutionContext) -> None:
        self.ctx: ExecutionContext = ctx
        self._token: Optional[contextvars.Token[Optional[ExecutionContext]]] = None

    def __enter__(self) -> ExecutionContext:
        self._token = _CURRENT_CONTEXT.set(self.ctx)
        return self.ctx

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._token is not None:
            _CURRENT_CONTEXT.reset(self._token)
            self._token = None

    async def __aenter__(self) -> ExecutionContext:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


def assert_writable_path(
    target_path: Union[pathlib.Path, str],
    ctx: Optional[ExecutionContext] = None,
) -> None:
    """Validate that target_path does not violate read-only Air-Gap boundaries ($COCH_SRC, $COCH_DATA)."""
    active_ctx = ctx or _CURRENT_CONTEXT.get()
    if active_ctx is None:
        return

    resolved_target = pathlib.Path(target_path).resolve()
    resolved_src = active_ctx.src_dir.resolve()
    resolved_data = active_ctx.data_dir.resolve()

    if resolved_target == resolved_src or resolved_src in resolved_target.parents:
        raise AirGapViolationError(
            f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only codebase tier ($COCH_SRC='{resolved_src}')."
        )

    if resolved_target == resolved_data or resolved_data in resolved_target.parents:
        raise AirGapViolationError(
            f"Air-Gap Violation: Target path '{resolved_target}' falls within read-only baseline data tier ($COCH_DATA='{resolved_data}')."
        )


# ==============================================================================
# Atomic File Staging & HPC Prohibition
# ==============================================================================
class AtomicWrite:
    """Context manager providing atomic file replacement mechanics via temporary local staging."""

    def __init__(self, target_path: Union[pathlib.Path, str]) -> None:
        self.target: pathlib.Path = pathlib.Path(target_path).resolve()
        assert_writable_path(self.target)
        self.tmp_path: pathlib.Path = self.target.with_name(f"{self.target.name}.{uuid.uuid4().hex[:8]}.tmp")

    def __enter__(self) -> pathlib.Path:
        self.target.parent.mkdir(parents=True, exist_ok=True)
        if not self.tmp_path.exists():
            self.tmp_path.touch()
        return self.tmp_path

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None and self.tmp_path.exists():
            try:
                with open(self.tmp_path, "a+b") as f:
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(self.tmp_path, self.target)
            except Exception as replace_err:
                if self.tmp_path.exists():
                    try:
                        self.tmp_path.unlink()
                    except OSError:
                        pass
                raise replace_err
        else:
            if self.tmp_path.exists():
                try:
                    self.tmp_path.unlink()
                except OSError:
                    pass


class FileLock:
    """Cross-process file locking for Local/Cloud tiers (Tier 1-4) with strict HPC tier prohibition."""

    def __init__(
        self,
        lock_path: Union[pathlib.Path, str],
        timeout_sec: float = 10.0,
    ) -> None:
        self.lock_path: pathlib.Path = pathlib.Path(lock_path).resolve()
        self.timeout_sec: float = max(0.1, float(timeout_sec))
        self._fd: Optional[int] = None

        # Verify against HPC distributed filesystem lock prohibition
        active_ctx = _CURRENT_CONTEXT.get()
        if active_ctx is not None:
            tier_str = active_ctx.env_tier.upper()
            if "TIER 5" in tier_str or "TIER 6" in tier_str:
                raise RuntimeError(
                    f"Distributed POSIX/Windows file locks are prohibited in HPC {active_ctx.env_tier} (Lustre/GPFS/NFS). "
                    "Calculations must stage I/O locally in $SLURM_TMPDIR and publish via AtomicWrite."
                )

    def acquire(self) -> bool:
        """Acquire physical cross-process file lock within timeout window."""
        assert_writable_path(self.lock_path)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        start_epoch = time.time()
        flags = os.O_RDWR | os.O_CREAT
        self._fd = os.open(str(self.lock_path), flags, 0o666)

        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                    return True
                else:
                    import fcntl

                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return True
            except (OSError, IOError) as lock_err:
                if (time.time() - start_epoch) >= self.timeout_sec:
                    if self._fd is not None:
                        os.close(self._fd)
                        self._fd = None
                    raise TimeoutError(
                        f"Timed out after {self.timeout_sec}s acquiring lock on {self.lock_path}"
                    ) from lock_err
                time.sleep(0.05)

    def release(self) -> None:
        """Release lock handle and close file descriptor."""
        if self._fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    try:
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl

                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
                os.close(self._fd)
            finally:
                self._fd = None

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()
