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

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(SOCKET_PATH)
    server.setblocking(False)
    
    loop = asyncio.get_running_loop()
    try:
        while True:
            try:
                data = await asyncio.wait_for(loop.sock_recv(server, 4096), timeout=0.5)
                if data:
                    payload = data.decode('utf-8')
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