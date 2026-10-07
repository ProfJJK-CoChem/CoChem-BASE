"""Native Stage 0 service shared with the Voilà installer."""

from __future__ import annotations

import argparse
import os
import threading
from pathlib import Path
from typing import Callable


def _run_setup(
    artifact_dir: str | Path,
    *,
    min_disk_space_gb: float = 50.0,
    skip_heavy: bool = False,
    on_event: Callable[[dict], None] | None = None,
    phases: list[int] | None = None,
) -> dict:
    """Execute native phase functions and return their actual structured summary.

    Events are ``phase_start``, ``phase_result`` and ``setup_complete``. This
    service installs free Python dependencies; ORCA/CFOUR are only discovered
    if separately provisioned. It does not accept or infer third-party licenses.
    A partial phase selection never replaces the Golden Registry.
    """
    from cochem_base.cli import action_setup

    if min_disk_space_gb <= 0:
        raise ValueError("A positive workload storage requirement is required")
    if phases is not None and (not phases or any(p not in range(1, 12) for p in phases)):
        raise ValueError("Setup phases must be a nonempty subset of 1 through 11")
    result = {}

    def emit(event: dict) -> None:
        if event["event"] == "setup_complete":
            result.update(event["summary"])
        if on_event is not None:
            on_event(event)

    args = argparse.Namespace(
        artifact_dir=str(Path(artifact_dir).absolute()),
        all=phases is None,
        phase=phases,
        dry_run=False,
        clean=False,
        skip_heavy=skip_heavy,
        skip_iops=False,
        skip_eckart=False,
        verbose=False,
        json=True,
        native_service=True,
        min_disk_space_gb=min_disk_space_gb,
    )
    action_setup(args, on_event=emit)
    if not result:
        raise RuntimeError("Setup did not return completion evidence")
    return result


_SETUP_LOCK = threading.RLock()
_SETUP_ENVIRONMENT_KEYS = (
    "COCHEM_ARTIFACT_DIR",
    "COCHEM_BASE_ROOT",
    "PATH",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "CUDA_MPS_PIPE_DIRECTORY",
    "CUDA_MPS_LOG_DIRECTORY",
    "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT",
    "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE",
    "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT",
)


def run_setup(
    artifact_dir: str | Path,
    *,
    min_disk_space_gb: float = 50.0,
    skip_heavy: bool = False,
    on_event: Callable[[dict], None] | None = None,
    phases: list[int] | None = None,
) -> dict:
    """Run native setup with its temporary process environment restored on exit.

    Registry selection for future jobs remains explicit; a partial or failed
    installation must never redirect later calculations to its scratch registry.
    """
    with _SETUP_LOCK:
        previous = {key: os.environ.get(key) for key in _SETUP_ENVIRONMENT_KEYS}
        try:
            return _run_setup(
                artifact_dir,
                min_disk_space_gb=min_disk_space_gb,
                skip_heavy=skip_heavy,
                on_event=on_event,
                phases=phases,
            )
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
