"""CoChem Concurrency and OS-level file locking module."""

from __future__ import annotations

from cochem.concurrency.atomic_file_lock import AtomicFileLock

__all__ = ["AtomicFileLock", "EphemeralScratchSession", "resolve_hpc_safe_scratch"]


def __getattr__(name: str):
    """Load optional TORQ scratch helpers only when they are requested."""
    if name in {"EphemeralScratchSession", "resolve_hpc_safe_scratch"}:
        from importlib import import_module
        return getattr(import_module("Libraries.cochem_torq_environment"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
