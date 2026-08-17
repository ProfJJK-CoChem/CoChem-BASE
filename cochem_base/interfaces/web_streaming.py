import json
import logging
import os
import socket
import struct
import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class WebGLPacket(BaseModel):
    protocol: str = "BrowserStreaming-014"
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any]

class WebGLStreamer:
    """
    Streams molecular or topological data to a browser.
    Supports BrowserStreaming-014.
    """
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        self.host: str = host or os.environ.get("COCHEM_WEBGL_HOST", "127.0.0.1")
        self.port: int = int(port or os.environ.get("COCHEM_WEBGL_PORT", "8080"))
        self.sock: Optional[socket.socket] = None
        self.connected: bool = False

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        try:
            self.sock.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to WebGL client at {self.host}:{self.port}")
        except OSError as e:
            self.connected = False
            self.sock = None
            logger.error(f"Failed to connect to WebGL client at {self.host}:{self.port}: {e}")
            raise ConnectionError(f"Failed to connect to WebGL client at {self.host}:{self.port}") from e

    def disconnect(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError as e:
                logger.warning(f"Error closing socket: {e}")
            self.sock = None
        self.connected = False
        logger.info("Disconnected from WebGL client")

    def stream_data(self, data_packet: Dict[str, Any]) -> None:
        if not self.sock or not self.connected:
            raise ConnectionError("Not connected to WebGL client endpoint")

        try:
            packet_model = WebGLPacket(payload=data_packet)
            json_str = packet_model.model_dump_json() if hasattr(packet_model, "model_dump_json") else packet_model.json()
            json_bytes = json_str.encode("utf-8")
            packet = struct.pack(f">I{len(json_bytes)}s", len(json_bytes), json_bytes)
            self.sock.sendall(packet)
        except OSError as e:
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
            logger.error(f"Failed to send data stream: {e}")
            raise ConnectionError("Stream interrupted due to socket error") from e

    def _flush(self) -> None:
        """TCP sockets send eagerly; retained for file-like compatibility."""
        pass

