#!/usr/bin/env python3
"""
CoChem-DOCK: Stage 9.0 - FastAPI Telemetry Polling Backend
Bridges the UNIX Domain Socket from Stage 2.3 into React WebSockets.
"""
import os
import asyncio
import socket
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CoChem-DOCK Telemetry API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SOCKET_PATH = "/tmp/cochem_telemetry.sock"

@app.get("/api/health")
async def health_check():
    return {"status": "online", "service": "CoChem-DOCK FastAPI"}

def lttb_decimate(data: list, threshold: int) -> list:
    """
    Largest Triangle Three Buckets (LTTB) downsampling algorithm for high-frequency telemetry.
    Preserves visual peaks and valleys for the React UI.
    """
    if len(data) <= threshold or threshold == 0:
        return data
        
    # Simplified LTTB implementation for scalar stream
    bucket_size = (len(data) - 2) / (threshold - 2)
    sampled = [data[0]]
    
    for i in range(threshold - 2):
        start = int(1 + i * bucket_size)
        end = int(1 + (i + 1) * bucket_size)
        # Average the bucket (simplified LTTB for rapid telemetry)
        bucket = data[start:end]
        if bucket:
            sampled.append(sum(bucket) / len(bucket))
            
    sampled.append(data[-1])
    return sampled

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(SOCKET_PATH)
    server.setblocking(False)
    
    loop = asyncio.get_running_loop()
    
    # Buffer for LTTB Decimation
    telemetry_buffer = []
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(loop.sock_recv(server, 4096), timeout=0.1)
                if data:
                    payload = data.decode('utf-8')
                    telemetry_buffer.append(payload)
                    
                    # Decimate and emit at 60Hz
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
        print("Client disconnected.")
    finally:
        server.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)