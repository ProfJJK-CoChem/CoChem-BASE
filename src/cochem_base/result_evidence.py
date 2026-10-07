"""Validation of per-point convergence evidence and optional elapsed times."""

from typing import Any

import numpy as np


def normalize_point_evidence(converged: Any, wall_s: Any, npoints: int) -> tuple[np.ndarray, np.ndarray]:
    """Require measured convergence flags and preserve unknown elapsed times.

    HDF5 stores unmeasured elapsed times as NaN, distinct from measured zero.
    JSON-facing callers must convert this missing-value marker to ``None``.
    Scalar evidence applies to the whole submitted batch; vectors must contain
    exactly one value per point. Strings and numeric truthiness are not evidence.
    """
    if npoints <= 0:
        raise ValueError("At least one result point is required")
    if converged is None:
        raise ValueError("Explicit boolean convergence evidence is required")
    flags = np.asarray(converged)
    if flags.dtype.kind != "b":
        raise ValueError("Convergence evidence must contain only boolean values")
    if flags.ndim == 0:
        flags = np.full(npoints, flags.item(), dtype=bool)
    if flags.shape != (npoints,):
        raise ValueError("Convergence evidence must have one value per result point")

    if wall_s is None:
        elapsed = np.full(npoints, np.nan, dtype=np.float64)
    else:
        if np.asarray(wall_s).dtype.kind == "b":
            raise ValueError("Elapsed time must be a number of seconds, not a boolean")
        elapsed = np.asarray(wall_s, dtype=np.float64)
        if elapsed.ndim == 0:
            elapsed = np.full(npoints, elapsed.item(), dtype=np.float64)
        if elapsed.shape != (npoints,):
            raise ValueError("Elapsed time must have one value per result point")
        if np.any(np.isinf(elapsed)) or np.any(elapsed < 0):
            raise ValueError("Elapsed time must be nonnegative and finite, or NaN when unknown")
    return flags, elapsed
