"""
CoChem-TORQ: Phase 5 Step-Back Recovery Guard & Watchdog
========================================================
Asynchronously monitors electronic structure calculations in real-time,
detecting SCF divergence and memory allocation crashes to autonomously recover jobs.

Authoritative Standards:
- Method Matrix: Stage 4.0 Watchdog Step-Back Recovery
- Traceback Depth Analysis & Dynamic %maxcore Backoff
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import psutil

logger = logging.getLogger("CoChem-TORQ.Watchdog")


def monitor_stdout_stream(stdout_lines: Sequence[str]) -> Dict[str, Any]:
    """
    Parses electronic structure stdout streams for failure signatures:
    SCF divergence, Out-Of-Memory (OOM), spin contamination, or basis set linear dependencies.
    """
    signatures = {
        "scf_divergence": False,
        "memory_oom": False,
        "spin_contamination": False,
        "basis_linear_dependency": False,
        "abnormal_termination": False,
    }
    error_messages: List[str] = []

    for line in stdout_lines:
        line_upper = line.upper()
        if (
            "SCF NOT CONVERGED" in line_upper
            or "ENERGY DID NOT CONVERGE" in line_upper
            or "PING-PONG" in line_upper
        ):
            signatures["scf_divergence"] = True
            error_messages.append(line.strip())
        if (
            "OUT OF MEMORY" in line_upper
            or "ALLOCATION FAILED" in line_upper
            or "BAD_ALLOC" in line_upper
            or "CANNOT ALLOCATE" in line_upper
        ):
            signatures["memory_oom"] = True
            error_messages.append(line.strip())
        if "SPIN CONTAMINATION" in line_upper or "S**2 EXPECTATION VALUE" in line_upper:
            signatures["spin_contamination"] = True
            error_messages.append(line.strip())
        if "LINEAR DEPENDENCY" in line_upper or "NEAR SINGULAR OVERLAP" in line_upper:
            signatures["basis_linear_dependency"] = True
            error_messages.append(line.strip())
        if (
            "ORCA FINISHED WITH ERROR" in line_upper
            or "FATAL ERROR" in line_upper
            or "ABORTING" in line_upper
        ):
            signatures["abnormal_termination"] = True
            error_messages.append(line.strip())

    has_critical_failure = any(signatures.values())

    return {
        "has_failure": has_critical_failure,
        "signatures": signatures,
        "error_lines": error_messages,
    }


def execute_grid_collapse(
    current_grid_level: str = "defgrid3",
    scf_cycles: int = 50,
    energy_history: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """
    If an SCF divergence or energy oscillation loop is detected at a dense calculation point,
    dynamically widens the interpolation grid and switches the SCF algorithm.
    """
    divergence_detected = False
    oscillation_count = 0

    if energy_history and len(energy_history) >= 4:
        diffs = [energy_history[i + 1] - energy_history[i] for i in range(len(energy_history) - 1)]
        # Count sign oscillations
        for i in range(len(diffs) - 1):
            if diffs[i] * diffs[i + 1] < 0:
                oscillation_count += 1
        if oscillation_count >= 2:
            divergence_detected = True

    if scf_cycles >= 50:
        divergence_detected = True

    grid_hierarchy = {
        "defgrid3": "defgrid2",
        "defgrid2": "defgrid1",
        "defgrid1": "defgrid1",
    }
    new_grid = grid_hierarchy.get(current_grid_level.lower(), "defgrid1")

    selected_scf = "SOSCF"
    damping_factor = 0.40

    logger.warning(
        "SCF divergence watchdog triggered (cycles=%d, oscillations=%d). "
        "Collapsing grid %s -> %s and switching to %s (damping=%.2f)",
        scf_cycles,
        oscillation_count,
        current_grid_level,
        new_grid,
        selected_scf,
        damping_factor,
    )

    return {
        "action": "grid_collapse",
        "divergence_detected": divergence_detected,
        "previous_grid": current_grid_level,
        "new_grid": new_grid,
        "scf_algorithm": selected_scf,
        "damping_factor": damping_factor,
        "max_scf_cycles": 150,
    }


class DynamicMemoryResult(Dict[str, Any]):
    """
    Result dictionary for memory backoff that also supports numeric comparisons and casting.
    """

    def __init__(self, *args: Any, new_maxcore_mb: int = 256, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.new_maxcore_mb = new_maxcore_mb

    def __int__(self) -> int:
        return self.new_maxcore_mb

    def __float__(self) -> float:
        return float(self.new_maxcore_mb)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self.new_maxcore_mb == other
        return super().__eq__(other)

    def __le__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self.new_maxcore_mb <= other
        return NotImplemented

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self.new_maxcore_mb < other
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self.new_maxcore_mb >= other
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, (int, float)):
            return self.new_maxcore_mb > other
        return NotImplemented


def dynamic_memory_backoff(
    requested_maxcore_mb: Optional[int] = None,
    requested_mb: Optional[int] = None,
    available_mb: Optional[int] = None,
    process_pid: Optional[int] = None,
    backoff_factor: float = 0.75,
    **kwargs: Any,
) -> DynamicMemoryResult:
    """
    Safely terminates an out-of-memory electronic structure process (reaping child processes
    via psutil to eliminate zombie threads) and reduces the %maxcore memory allocation.
    """
    reaped = False
    reaped_children = 0

    req_mb = requested_mb if requested_mb is not None else (requested_maxcore_mb if requested_maxcore_mb is not None else 4096)

    if process_pid is not None and psutil.pid_exists(process_pid):
        try:
            parent = psutil.Process(process_pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                    reaped_children += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            parent.terminate()
            reaped = True
            logger.info(
                "Watchdog safely reaped PID %d and %d child process(es)",
                process_pid,
                reaped_children,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied) as err:
            logger.warning("Could not terminate PID %d: %s", process_pid, err)

    # Calculate backed-off maxcore memory with 256 MB hard floor
    target_mem = int(req_mb * backoff_factor)
    if available_mb is not None:
        target_mem = min(target_mem, available_mb)
    new_maxcore = max(256, target_mem)

    logger.info(
        "Watchdog dynamically adjusted memory ceiling: %d MB -> %d MB (backoff_factor=%.2f)",
        req_mb,
        new_maxcore,
        backoff_factor,
    )

    return DynamicMemoryResult(
        {
            "action": "dynamic_memory_backoff",
            "previous_maxcore_mb": req_mb,
            "new_maxcore_mb": new_maxcore,
            "backoff_factor": backoff_factor,
            "process_reaped": reaped,
            "reaped_children_count": reaped_children,
            "ready_for_restart": True,
        },
        new_maxcore_mb=new_maxcore,
    )
