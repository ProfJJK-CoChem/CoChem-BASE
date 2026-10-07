"""Audit observed data and API execution without manufacturing missing evidence."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
import time
from typing import Any

import h5py
import numpy as np
import psutil

from cochem_base.core_engine.cochem_core_context_compressor import lttb_downsample_xy


logger = logging.getLogger("cochem-audit-runner")


class PhysicalAuditUnavailableError(RuntimeError):
    """Required measured input or a real API response is unavailable."""


def verify_physical_lttb_decimation(
    real_h5_path: Path,
    *,
    x_dataset: str = "/physical_spectra/wavenumbers",
    y_dataset: str = "/physical_spectra/absorbance",
    threshold: int = 500,
) -> dict[str, Any]:
    """Measure decimation of caller-supplied HDF5 observations.

    Missing datasets, nonfinite observations, and insufficient rows fail. This
    verifies transformation integrity; it cannot attest how a caller acquired
    their input measurements. The report identifies the exact source file.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 3 <= threshold <= 500:
        raise ValueError("Audit threshold must be an integer from 3 through the 500-point context limit")
    path = Path(real_h5_path).resolve()
    if not path.is_file():
        raise PhysicalAuditUnavailableError(f"Required physical HDF5 archive is absent: {path}")
    try:
        with h5py.File(path, "r") as archive:
            x = np.asarray(archive[x_dataset][()], dtype=np.float64)
            y = np.asarray(archive[y_dataset][()], dtype=np.float64)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise PhysicalAuditUnavailableError(f"Cannot load physical observations from {path}: {exc}") from exc
    if x.ndim != 1 or y.ndim != 1 or x.shape != y.shape or x.size < threshold:
        raise PhysicalAuditUnavailableError("Physical observations require matching one-dimensional arrays with at least threshold rows")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(np.diff(x) <= 0):
        raise PhysicalAuditUnavailableError("Physical observations must be finite with strictly increasing x coordinates")

    started = time.perf_counter()
    reduced = lttb_downsample_xy(x, y, threshold=threshold, use_numba=False)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if reduced.shape != (threshold, 2):
        raise RuntimeError("LTTB output has an invalid shape")
    indices = np.searchsorted(x, reduced[:, 0])
    if np.any(indices >= x.size) or not np.array_equal(x[indices], reduced[:, 0]) or not np.array_equal(y[indices], reduced[:, 1]):
        raise RuntimeError("LTTB output contains points absent from physical input")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    report = {
        "source": str(path), "source_sha256": digest.hexdigest(),
        "x_dataset": x_dataset, "y_dataset": y_dataset,
        "input_points": int(x.size), "output_points": int(reduced.shape[0]),
        "elapsed_ms": elapsed_ms,
    }
    logger.info("LTTB transformation verified: %d measured input rows, %d selected rows, %.3f ms", x.size, reduced.shape[0], elapsed_ms)
    return report


def validate_physical_api_response(response: Any) -> None:
    """Reject offline templates and fallback responses as network evidence."""
    if (
        response.tier != 2 or not response.success or not response.text.strip()
        or response.engine_name != "AIAPIRouter"
        or response.metadata.get("router_fallback")
    ):
        raise PhysicalAuditUnavailableError("A successful live API response is required; offline or fallback output is not network evidence")


def verify_physical_api_router_network() -> None:
    """Require a configured API and a successful live response for this audit."""
    from .api_router import AIAPIRouter, ApiRouterConfig

    router = AIAPIRouter(config=ApiRouterConfig(
        max_prompt_tokens=100, retry_max_delay_seconds=2.0, max_retries=1,
    ))
    try:
        if not router.is_available():
            raise PhysicalAuditUnavailableError("API audit unavailable: no configured API credential")
        response = router.generate(prompt="Return a brief connectivity acknowledgement.", system_prompt="Connectivity audit.")
        validate_physical_api_response(response)
    finally:
        router.unload()
    logger.info("API audit verified a successful live response")


def verify_immutable_pid_sampling() -> dict[str, Any]:
    """Record this process's real status and memory; this is local telemetry."""
    process = psutil.Process(os.getpid())
    status = process.status()
    if status not in (psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING):
        raise RuntimeError(f"Audit process is not running normally: {status}")
    return {"pid": process.pid, "status": status, "rss_bytes": process.memory_info().rss}


def execute_audit(artifacts_dir: Path) -> dict[str, Any]:
    """Require physical input before making the explicitly requested API call."""
    decimation = verify_physical_lttb_decimation(Path(artifacts_dir) / "landscape.h5")
    verify_physical_api_router_network()
    return {"lttb": decimation, "process": verify_immutable_pid_sampling(), "api_verified": True}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts_dir", type=Path, help="Existing directory containing measured landscape.h5 observations")
    arguments = parser.parse_args()
    execute_audit(arguments.artifacts_dir)
