"""BASE atomic locking; retired TORQ scratch object exports are unavailable."""

from __future__ import annotations

from cochem.concurrency.atomic_file_lock import AtomicFileLock

__all__ = ["AtomicFileLock"]


def __getattr__(name: str):
    if name in {"EphemeralScratchSession", "resolve_hpc_safe_scratch"}:
        raise ImportError(
            f"{__name__}.{name} is unavailable: the retired TORQ scratch-object "
            "API is not imported across isolated environments. BASE scratch "
            "operations require cochem_base.core.scratch.admit_scratch and "
            "actual Stage 0 evidence; engine execution requires separate authorization."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
