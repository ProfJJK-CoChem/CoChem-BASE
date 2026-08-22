#!/usr/bin/env python3
"""CoChem-DOCK: Stage 9.0 - Legacy entrypoint for FastAPI Telemetry Backend.

Re-exports canonical symbols from cochem_base.interfaces.cochem_dock_main.
"""

from __future__ import annotations

from cochem_base.interfaces.cochem_dock_main import (
    HealthResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryMessage,
    TelemetryStatsResponse,
    app,
    create_app,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)

__all__ = [
    "HealthResponse",
    "TelemetryBatchPayload",
    "TelemetryEvent",
    "TelemetryMessage",
    "TelemetryStatsResponse",
    "app",
    "create_app",
    "health_check",
    "lifespan",
    "logger",
    "lttb_decimate",
    "run_server",
    "telemetry_stats",
    "websocket_telemetry",
]

if __name__ == "__main__":
    run_server()

