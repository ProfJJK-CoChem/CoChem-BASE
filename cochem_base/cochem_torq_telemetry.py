"""
CoChem-BASE Telemetry Interface Proxy.
Exposes all functions and symbols from cochem_torq_telemetry.
"""

from cochem_torq_telemetry import (
    TELEMETRY_BUFFER,
    export_crash_animation,
    generate_plotly_3d_carousels,
    stream_webhook_events,
)

__all__ = [
    "stream_webhook_events",
    "generate_plotly_3d_carousels",
    "export_crash_animation",
    "TELEMETRY_BUFFER",
]
