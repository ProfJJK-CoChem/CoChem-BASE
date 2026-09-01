#!/usr/bin/env python3
"""CoChem-DOCK: Stage 9.0 - Legacy FastAPI Server Script.

Legacy FastAPI server script referenced in SRS Document 2 Rectification Matrix;
superseded by interfaces/cochem_dock_main.py for HPC Dual-Mode queue.
Maintains full backward compatibility for legacy entrypoint invocations and
re-exports canonical symbols from cochem_base.interfaces.cochem_dock_main.
Compliant with Method Matrix v4 Section 8A.
"""

from __future__ import annotations

import os

from cochem_base.interfaces.cochem_dock_main import (
    DualModeJobQueue,
    HealthResponse,
    JobCancelResponse,
    JobListResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryMessage,
    TelemetryStatsResponse,
    app,
    create_app,
    default_job_queue,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)

# Legacy alias compatibility
dock_app = app

__all__ = [
    "DualModeJobQueue",
    "HealthResponse",
    "JobCancelResponse",
    "JobListResponse",
    "JobStatusResponse",
    "JobSubmitRequest",
    "JobSubmitResponse",
    "TelemetryBatchPayload",
    "TelemetryEvent",
    "TelemetryMessage",
    "TelemetryStatsResponse",
    "app",
    "create_app",
    "default_job_queue",
    "dock_app",
    "health_check",
    "lifespan",
    "logger",
    "lttb_decimate",
    "run_server",
    "telemetry_stats",
    "websocket_telemetry",
]

if __name__ == "__main__":
    run_server(
        host=os.environ.get("COCHEM_DOCK_HOST", "127.0.0.1"),
        port=int(os.environ.get("COCHEM_DOCK_PORT", "8000")),
    )
