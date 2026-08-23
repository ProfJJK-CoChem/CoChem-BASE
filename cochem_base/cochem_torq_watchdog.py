"""
CoChem-BASE Proxy for cochem_torq_watchdog
"""

from cochem_torq_watchdog import (
    dynamic_memory_backoff,
    execute_grid_collapse,
    monitor_stdout_stream,
)

__all__ = [
    "monitor_stdout_stream",
    "execute_grid_collapse",
    "dynamic_memory_backoff",
]
