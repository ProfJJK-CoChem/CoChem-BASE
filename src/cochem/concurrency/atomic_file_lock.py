"""Cross-platform atomic file lock using filelock."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from filelock import FileLock, Timeout


class AtomicFileLock:
    """POSIX/Windows-agnostic file lock wrapper around FileLock."""

    def __init__(self, lock_path: Path | str, timeout: float = 10.0, **kwargs: Any) -> None:
        self.lock_path = Path(lock_path)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._lock = FileLock(str(self.lock_path), timeout=timeout)

    def __enter__(self) -> AtomicFileLock:
        self._lock.acquire(timeout=self.timeout)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._lock.release()

    def acquire(self, timeout: float | None = None) -> None:
        t = self.timeout if timeout is None else timeout
        self._lock.acquire(timeout=t)

    def release(self) -> None:
        self._lock.release()
