"""
CoChem-TORQ: Phase 1 Environment Bootstrapper & Air-Gap Enforcement
====================================================================
Establishes the secure runtime perimeter, dynamic directory mapping,
and inter-process communication (IPC) scratch buffer cleanup.

Authoritative Standards:
- Method Matrix: Stage 0.0 Runtime Environment & Provenance Guardrails
- CoChem User Manual: Air-gap assertions and dynamic path resolution
"""

from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from cochem_base.exceptions import AirGapViolationError, ProvenanceErrorCode


class TorqAirgapViolationError(AirGapViolationError):
    """Raised when the execution directory overlaps with the artifact output directory."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
            details=details,
        )


def init_torq_logger(
    name: str = "CoChem-TORQ",
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Configures and returns a structured logger for the CoChem-TORQ pipeline,
    eliminating arbitrary print statements across the runtime.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="[%(asctime)s | %(name)s | %(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


_logger = init_torq_logger()


def resolve_torq_environment() -> Dict[str, Path]:
    """
    Dynamically maps runtime and artifact directories via environment variables
    (COCHEM_ARTIFACTS, COCHEM_TORQ_LIB, COCHEM_SCRATCH, COCHEM_UPLOADS) or standard user fallbacks.
    Zero hardcoded paths are allowed.
    """
    base_user_cochem = Path.home() / ".cochem"

    artifacts_env = os.environ.get("COCHEM_ARTIFACTS")
    artifacts_dir = (
        Path(artifacts_env).resolve()
        if artifacts_env
        else (base_user_cochem / "artifacts").resolve()
    )

    torq_lib_env = os.environ.get("COCHEM_TORQ_LIB")
    torq_lib_dir = (
        Path(torq_lib_env).resolve() if torq_lib_env else (base_user_cochem / "torq_lib").resolve()
    )

    scratch_env = os.environ.get("COCHEM_SCRATCH")
    scratch_dir = (
        Path(scratch_env).resolve() if scratch_env else (base_user_cochem / "scratch").resolve()
    )

    uploads_env = os.environ.get("COCHEM_UPLOADS")
    uploads_dir = (
        Path(uploads_env).resolve() if uploads_env else (base_user_cochem / "uploads").resolve()
    )

    paths = {
        "artifacts": artifacts_dir,
        "torq_lib": torq_lib_dir,
        "scratch": scratch_dir,
        "uploads": uploads_dir,
    }

    for name, p in paths.items():
        p.mkdir(parents=True, exist_ok=True)
        _logger.debug("Resolved %s directory to: %s", name, p)

    return paths


def verify_airgap(
    exec_dir: Optional[Union[str, Path]] = None,
    artifact_dir: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Mathematically asserts that the execution directory (cwd) is strictly separated
    from the artifact directory using Path.resolve(). Throws TorqAirgapViolationError
    if an air-gap breach is detected.
    """
    resolved_exec = Path(exec_dir or Path.cwd()).resolve()

    if artifact_dir is not None:
        resolved_artifact = Path(artifact_dir).resolve()
    else:
        env_dirs = resolve_torq_environment()
        resolved_artifact = env_dirs["artifacts"].resolve()

    # Rule 1: Execution directory cannot be identical to the artifact directory
    if resolved_exec == resolved_artifact:
        msg = f"Airgap violation: Execution directory {resolved_exec} is identical to artifact directory {resolved_artifact}."
        _logger.error(msg)
        raise TorqAirgapViolationError(
            message=msg,
            details={
                "field": "artifact_dir",
                "value": str(resolved_artifact),
                "expected": f"Distinct non-overlapping path from {resolved_exec}",
            },
        )

    # Rule 2: Execution directory cannot be located inside artifact directory
    try:
        resolved_exec.relative_to(resolved_artifact)
        msg = f"Airgap violation: Execution directory {resolved_exec} is located inside artifact directory {resolved_artifact}."
        _logger.error(msg)
        raise TorqAirgapViolationError(
            message=msg,
            details={
                "field": "exec_dir",
                "value": str(resolved_exec),
                "expected": f"Path outside of {resolved_artifact}",
            },
        )
    except ValueError:
        pass

    _logger.info("Airgap verified: exec=%s <-> artifact=%s", resolved_exec, resolved_artifact)
    return True


def cleanup_ipc_buffers(scratch_dir: Union[str, Path]) -> int:
    """
    Scans and purges cross-platform memory-mapped IPC buffers and temporary files
    (.shm, .ipc, .lock, .tmp, .mmap) from the designated scratch directory.
    """
    target_dir = Path(scratch_dir).resolve()
    if not target_dir.exists():
        return 0

    reaped_count = 0
    target_extensions = {".shm", ".ipc", ".lock", ".tmp", ".mmap"}

    try:
        for entry in list(target_dir.iterdir()):
            if entry.is_file() and (
                entry.suffix.lower() in target_extensions or ".ipc_" in entry.name
            ):
                try:
                    entry.unlink(missing_ok=True)
                    reaped_count += 1
                    _logger.debug("Purged IPC buffer file: %s", entry)
                except OSError as err:
                    _logger.warning("Could not unlink IPC buffer %s: %s", entry, err)
    except OSError as err:
        _logger.error("Error reading scratch directory for IPC cleanup: %s", err)

    return reaped_count


def register_ipc_cleanup(scratch_dir: Optional[Union[str, Path]] = None) -> Callable[[], None]:
    """
    Registers an atexit garbage collection hook to purge memory-mapped IPC scratch
    buffers upon both clean and dirty exits. Returns the cleanup callable.
    """
    if scratch_dir is None:
        env_dirs = resolve_torq_environment()
        target = env_dirs["scratch"]
    else:
        target = Path(scratch_dir).resolve()

    def _cleanup_hook() -> None:
        count = cleanup_ipc_buffers(target)
        if count > 0:
            _logger.info("Atexit hook cleaned up %d IPC scratch buffer(s) in %s", count, target)

    atexit.register(_cleanup_hook)
    _logger.debug("Registered atexit IPC cleanup hook for %s", target)
    return _cleanup_hook
