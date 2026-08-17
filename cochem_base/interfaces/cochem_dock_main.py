#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - FastAPI Telemetry Polling Backend
Bridges the UNIX Domain Socket from Stage 2.3 into React WebSockets.
"""
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from cochem_base.telemetry_transport import (
    close_telemetry_server_socket,
    create_telemetry_server_socket,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-DOCK")

app = FastAPI(title="CoChem-DOCK Telemetry API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TelemetryEvent(BaseModel):
    type: str = Field(default="unknown")
    energy_hartree: Optional[float] = None


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "online", "service": "CoChem-DOCK FastAPI"}


def lttb_decimate(data: List[str], threshold: int) -> List[str]:
    """
    Largest Triangle Three Buckets (LTTB) downsampling algorithm for high-frequency telemetry.
    Preserves visual peaks and valleys for the React UI.
    """
    if len(data) <= threshold or threshold == 0:
        return data

    parsed_data: List[Tuple[int, str, float]] = []

    for idx, item in enumerate(data):
        try:
            obj = json.loads(item)
            event = TelemetryEvent(**obj)
            if event.type == "scf_step" and event.energy_hartree is not None:
                parsed_data.append((idx, item, event.energy_hartree))
        except (json.JSONDecodeError, ValueError, TypeError, ValidationError):
            # Not a valid scf_step or malformed telemetry, keep it in the stream without downsampling
            pass

    if len(parsed_data) <= threshold or threshold == 0:
        return data

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


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await websocket.accept()
    server, socket_path = create_telemetry_server_socket()

    loop = asyncio.get_running_loop()
    telemetry_buffer: List[str] = []

    try:
        while True:
            try:
                data = await asyncio.wait_for(loop.sock_recv(server, 4096), timeout=0.1)
                if data:
                    payload = data.decode('utf-8')
                    telemetry_buffer.append(payload)

                    if len(telemetry_buffer) > 100:
                        decimated = lttb_decimate(telemetry_buffer, 20)
                        await websocket.send_json({"type": "lttb_batch", "data": decimated})
                        telemetry_buffer.clear()
                    else:
                        await websocket.send_text(payload)

            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
    finally:
        close_telemetry_server_socket(server, socket_path)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("COCHEM_DOCK_HOST", "127.0.0.1"),
        port=int(os.environ.get("COCHEM_DOCK_PORT", "8000")),
    )
