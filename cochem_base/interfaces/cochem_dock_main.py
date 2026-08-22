#!/usr/bin/env python3
"""CoChem-DOCK: Stage 9.0 - FastAPI Telemetry Polling Backend.

Bridges Unix domain socket / UDP telemetry transport into React WebSockets,
providing LTTB decimation, streaming health checks, and telemetry statistics.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, Union

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cochem_base.telemetry_transport import (
    close_telemetry_server_socket,
    create_telemetry_server_socket,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-DOCK")

_START_TIME = time.time()


class TelemetryEvent(BaseModel):
    """Pydantic model for structural validation of incoming telemetry events."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(default="unknown")
    step: Optional[int] = None
    energy_hartree: Optional[float] = None
    delta_energy: Optional[float] = None
    max_gradient: Optional[float] = None
    rms_gradient: Optional[float] = None
    walltime_seconds: Optional[float] = None
    timestamp: Optional[float] = None


TelemetryMessage = TelemetryEvent


class HealthResponse(BaseModel):
    """Schema for /api/health endpoint response."""

    status: str = "online"
    service: str = "CoChem-DOCK FastAPI"
    transport: str = "udp" if os.name == "nt" else "unix"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0


class TelemetryBatchPayload(BaseModel):
    """Schema for LTTB-decimated batched telemetry payloads."""

    type: str = "lttb_batch"
    data: List[str] = Field(default_factory=list)
    count: int = 0


class TelemetryStatsResponse(BaseModel):
    """Schema for /api/telemetry/stats endpoint response."""

    active: bool = True
    transport: str = "udp" if os.name == "nt" else "unix"
    socket_path: Optional[str] = None
    udp_host: Optional[str] = None
    udp_port: Optional[int] = None


def lttb_decimate(data: List[str], threshold: int) -> List[str]:
    """Largest Triangle Three Buckets (LTTB) downsampling algorithm for high-frequency telemetry.

    Preserves visual peaks and valleys for the React UI.
    """
    if len(data) <= threshold or threshold <= 0:
        return data

    parsed_data: List[Tuple[int, str, float]] = []

    for idx, item in enumerate(data):
        try:
            obj = json.loads(item)
            if isinstance(obj, dict):
                event = TelemetryEvent.model_validate(obj)
                if event.type == "scf_step" and event.energy_hartree is not None:
                    parsed_data.append((idx, item, event.energy_hartree))
        except (json.JSONDecodeError, ValueError, TypeError, ValidationError):
            pass

    if len(parsed_data) <= threshold or threshold <= 0:
        return data

    if threshold == 1:
        return [parsed_data[0][1]]
    if threshold == 2:
        return [parsed_data[0][1], parsed_data[-1][1]]

    bucket_size = (len(parsed_data) - 2) / (threshold - 2)
    sampled_indices: Set[int] = {parsed_data[0][0]}

    a = 0
    for i in range(threshold - 2):
        bucket_start = int(1 + i * bucket_size)
        bucket_end = min(int(1 + (i + 1) * bucket_size), len(parsed_data) - 1)
        next_bucket_start = int(1 + (i + 1) * bucket_size)
        next_bucket_end = min(int(1 + (i + 2) * bucket_size), len(parsed_data))

        avg_x, avg_y, count = 0.0, 0.0, 0
        for j in range(next_bucket_start, next_bucket_end):
            avg_x += j
            avg_y += parsed_data[j][2]
            count += 1

        if count > 0:
            avg_x /= count
            avg_y /= count

        max_area, max_area_index = -1.0, bucket_start
        for j in range(bucket_start, bucket_end):
            point_b_y = parsed_data[j][2]
            point_a_y = parsed_data[a][2]

            area = abs(a * (point_b_y - avg_y) + j * (avg_y - point_a_y) + avg_x * (point_a_y - point_b_y)) * 0.5
            if area > max_area:
                max_area = area
                max_area_index = j

        sampled_indices.add(parsed_data[max_area_index][0])
        a = max_area_index

    sampled_indices.add(parsed_data[-1][0])

    parsed_indices: Set[int] = {p[0] for p in parsed_data}
    result: List[str] = []
    for idx, item in enumerate(data):
        if idx in sampled_indices or idx not in parsed_indices:
            result.append(item)

    return result


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    yield


def create_app() -> FastAPI:
    app_instance = FastAPI(title="CoChem-DOCK Telemetry API", lifespan=lifespan)
    app_instance.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app_instance.get("/api/health", response_model=HealthResponse)
    async def _health_check() -> Dict[str, Any]:
        return await health_check()

    @app_instance.get("/api/telemetry/stats", response_model=TelemetryStatsResponse)
    async def _telemetry_stats() -> Dict[str, Any]:
        return await telemetry_stats()

    @app_instance.websocket("/ws/telemetry")
    async def _websocket_telemetry(
        websocket: WebSocket, buffer_threshold: int = 100, decimate_target: int = 20
    ) -> None:
        await websocket_telemetry(websocket, buffer_threshold=buffer_threshold, decimate_target=decimate_target)

    return app_instance


app = create_app()


async def health_check() -> Dict[str, Any]:
    uptime = time.time() - _START_TIME
    transport = "udp" if os.name == "nt" else "unix"
    return {
        "status": "online",
        "service": "CoChem-DOCK FastAPI",
        "transport": transport,
        "version": "0.1.0",
        "uptime_seconds": round(uptime, 2),
    }


async def telemetry_stats() -> Dict[str, Any]:
    transport = "udp" if os.name == "nt" else "unix"
    if transport == "unix":
        return {"active": True, "transport": "unix", "socket_path": "/tmp/cochem_telemetry.sock"}
    return {"active": True, "transport": "udp", "udp_host": "127.0.0.1", "udp_port": 54321}


async def websocket_telemetry(
    websocket: WebSocket, buffer_threshold: int = 100, decimate_target: int = 20
) -> None:
    await websocket.accept()
    server, socket_path = create_telemetry_server_socket()
    server.setblocking(False)

    loop = asyncio.get_running_loop()
    telemetry_buffer: List[str] = []

    async def _listen_client() -> None:
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
                elif msg == "flush":
                    if telemetry_buffer:
                        decimated = lttb_decimate(telemetry_buffer, decimate_target)
                        await websocket.send_json({"type": "lttb_batch", "data": decimated, "count": len(decimated)})
                        telemetry_buffer.clear()
        except WebSocketDisconnect:
            pass

    async def _listen_socket() -> None:
        try:
            while True:
                try:
                    data = await loop.sock_recv(server, 4096)
                    if data:
                        payload = data.decode("utf-8")
                        telemetry_buffer.append(payload)
                        if len(telemetry_buffer) >= buffer_threshold:
                            decimated = lttb_decimate(telemetry_buffer, decimate_target)
                            await websocket.send_json({"type": "lttb_batch", "data": decimated, "count": len(decimated)})
                            telemetry_buffer.clear()
                        else:
                            await websocket.send_text(payload)
                except (BlockingIOError, InterruptedError):
                    await asyncio.sleep(0.01)
                except Exception:
                    await asyncio.sleep(0.01)
        except WebSocketDisconnect:
            pass

    t_client = asyncio.create_task(_listen_client())
    t_socket = asyncio.create_task(_listen_socket())

    try:
        done, pending = await asyncio.wait([t_client, t_socket], return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except Exception as e:
        logger.error(f"WebSocket telemetry session error: {e}")
    finally:
        t_client.cancel()
        t_socket.cancel()
        close_telemetry_server_socket(server, socket_path)


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server(
        host=os.environ.get("COCHEM_DOCK_HOST", "127.0.0.1"),
        port=int(os.environ.get("COCHEM_DOCK_PORT", "8000")),
    )

