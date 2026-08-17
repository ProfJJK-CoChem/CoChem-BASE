import json
import os
import socket
import struct
import time


class WebGLStreamer:
    """
    Streams molecular or topological data to a browser.
    Supports BrowserStreaming-014.
    """
    def __init__(self, host=None, port=None):
        self.host = host or os.environ.get("COCHEM_WEBGL_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("COCHEM_WEBGL_PORT", "8080"))
        self.sock = None
        self.connected = False

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((self.host, self.port))
            self.connected = True
        except Exception as e:
            self.connected = False
            self.sock = None
            raise ConnectionError(f"Failed to connect to WebGL client at {self.host}:{self.port}") from e

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
        self.connected = False

    def stream_data(self, data_packet):
        if not self.sock or not self.connected:
            raise ConnectionError("Not connected to WebGL client endpoint")

        formatted_packet = {
            "protocol": "BrowserStreaming-014",
            "timestamp": time.time(),
            "payload": data_packet
        }
        json_bytes = json.dumps(formatted_packet).encode('utf-8')
        packet = struct.pack(f">I{len(json_bytes)}s", len(json_bytes), json_bytes)
        self.sock.sendall(packet)

    def _flush(self):
        """TCP sockets send eagerly; retained for file-like compatibility."""
        return None

