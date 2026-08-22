#!/usr/bin/env python3
"""CoChem-BASE: High-Throughput WebGL Binary Streaming Interface.

Protocol: BrowserStreaming-014
Implements framed TCP binary streaming, Pydantic v2 validation,
sparsity matrix routing, and real-time bidirectional telemetry.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import struct
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

STREAMING_PROTOCOL_VERSION = "BrowserStreaming-014"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_SOCKET_TIMEOUT = 10.0
HEADER_SIZE = 4
HEADER_STRUCT = ">I"
MAX_PACKET_SIZE = 64 * 1024 * 1024  # 64 MB


class WebGLStreamError(Exception):
    """Base exception for WebGL streaming errors."""


class WebGLConnectionError(WebGLStreamError, ConnectionError):
    """Exception raised when socket connection fails or disconnects unexpectedly."""


class WebGLPacketError(WebGLStreamError, ValueError):
    """Exception raised on packet framing, length mismatch, or header decoding errors."""


class WebGLSerializationError(WebGLStreamError, ValueError):
    """Exception raised when packet payload fails JSON serialization or deserialization."""


def pack_frame(payload_bytes: bytes) -> bytes:
    """Prepends a 4-byte big-endian unsigned integer length prefix to payload bytes."""
    payload_len = len(payload_bytes)
    if payload_len > MAX_PACKET_SIZE:
        raise WebGLPacketError(
            f"Payload size {payload_len} bytes exceeds maximum allowed packet size of {MAX_PACKET_SIZE} bytes."
        )
    return struct.pack(HEADER_STRUCT, payload_len) + payload_bytes


def unpack_frame_header(header_bytes: bytes) -> int:
    """Unpacks a 4-byte header into the integer payload length."""
    if len(header_bytes) != HEADER_SIZE:
        raise WebGLPacketError(f"Header must be exactly {HEADER_SIZE} bytes, got {len(header_bytes)} bytes.")
    (length,) = struct.unpack(HEADER_STRUCT, header_bytes)
    if length > MAX_PACKET_SIZE:
        raise WebGLPacketError(f"Payload length {length} exceeds MAX_PACKET_SIZE ({MAX_PACKET_SIZE}).")
    return length


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Reads exactly num_bytes from a connected TCP socket."""
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(min(num_bytes - len(buf), 65536))
        if not chunk:
            raise WebGLConnectionError("Socket closed prematurely while reading expected bytes.")
        buf.extend(chunk)
    return bytes(buf)


class WebGLPacket(BaseModel):
    """Pydantic model representing a framed WebGL telemetry / coordinate datagram."""

    model_config = ConfigDict(extra="allow")

    protocol: str = STREAMING_PROTOCOL_VERSION
    timestamp: float = Field(default_factory=time.time)
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_payload(
        cls, payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> WebGLPacket:
        """Factory constructor for WebGLPacket."""
        return cls(payload=payload, metadata=metadata or {})

    def to_json_bytes(self) -> bytes:
        """Serializes WebGLPacket to UTF-8 encoded JSON bytes."""
        return self.model_dump_json().encode("utf-8")

    @classmethod
    def from_json_bytes(cls, data: bytes) -> WebGLPacket:
        """Deserializes WebGLPacket from JSON bytes."""
        try:
            return cls.model_validate_json(data.decode("utf-8"))
        except Exception as e:
            raise WebGLSerializationError(f"Failed to deserialize WebGLPacket from JSON: {e}") from e

    def to_framed_bytes(self) -> bytes:
        """Returns length-prefixed binary frame for network transport."""
        return pack_frame(self.to_json_bytes())

    @classmethod
    def from_framed_bytes(cls, frame: bytes) -> WebGLPacket:
        """Extracts and deserializes a WebGLPacket from framed bytes."""
        if len(frame) < HEADER_SIZE:
            raise WebGLPacketError(f"Frame must have at least {HEADER_SIZE} bytes.")
        expected_len = unpack_frame_header(frame[:HEADER_SIZE])
        payload_data = frame[HEADER_SIZE:]
        if len(payload_data) != expected_len:
            raise WebGLPacketError(
                f"Payload length mismatch: expected {expected_len}, got {len(payload_data)}"
            )
        return cls.from_json_bytes(payload_data)

    def payload_size(self) -> int:
        """Returns the length in bytes of the JSON payload."""
        return len(self.to_json_bytes())


class WebGLStreamer:
    """High-throughput TCP streamer for BrowserStreaming-014 WebGL datagrams."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = DEFAULT_SOCKET_TIMEOUT,
        tcp_nodelay: bool = True,
        auto_reconnect: bool = False,
    ) -> None:
        self.host: str = host or os.environ.get("COCHEM_WEBGL_HOST", DEFAULT_HOST)
        self.port: int = int(port or os.environ.get("COCHEM_WEBGL_PORT", DEFAULT_PORT))
        self.timeout: float = float(timeout)
        self.tcp_nodelay: bool = tcp_nodelay
        self.auto_reconnect: bool = auto_reconnect

        self.sock: Optional[socket.socket] = None
        self._connected: bool = False

        self.packets_sent: int = 0
        self.bytes_sent: int = 0
        self.packets_received: int = 0
        self.bytes_received: int = 0
        self.last_stream_time: Optional[float] = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self.sock is not None

    @property
    def connected(self) -> bool:
        return self.is_connected

    @property
    def endpoint(self) -> Tuple[str, int]:
        return (self.host, self.port)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "connected": self.is_connected,
            "packets_sent": self.packets_sent,
            "bytes_sent": self.bytes_sent,
            "packets_received": self.packets_received,
            "bytes_received": self.bytes_received,
            "last_stream_time": self.last_stream_time,
        }

    def reset_stats(self) -> None:
        """Resets network packet and byte transmission counters."""
        self.packets_sent = 0
        self.bytes_sent = 0
        self.packets_received = 0
        self.bytes_received = 0

    def connect(self) -> None:
        """Establishes TCP stream connection with the WebGL client/server endpoint."""
        if self.is_connected:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        if self.tcp_nodelay:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        try:
            sock.connect((self.host, self.port))
            self.sock = sock
            self._connected = True
            logger.info(f"Connected to WebGL endpoint at {self.host}:{self.port}")
        except OSError as e:
            self._connected = False
            self.sock = None
            logger.error(f"Failed to connect to WebGL client at {self.host}:{self.port}: {e}")
            raise WebGLConnectionError(
                f"Failed to connect to WebGL client at {self.host}:{self.port}: {e}"
            ) from e

    def disconnect(self) -> None:
        """Closes the active TCP connection."""
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError as e:
                logger.warning(f"Error closing WebGL socket: {e}")
            self.sock = None
        self._connected = False
        logger.info("Disconnected from WebGL client")

    def close(self) -> None:
        """Alias for disconnect()."""
        self.disconnect()

    def reconnect(self) -> None:
        """Closes current connection and re-establishes a fresh socket."""
        self.disconnect()
        self.connect()

    def stream_data(
        self, data_packet: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Streams a dictionary payload as a framed WebGLPacket.

        Returns total bytes sent.
        """
        if not self.is_connected:
            if self.auto_reconnect:
                self.connect()
            else:
                raise WebGLConnectionError("Not connected to WebGL client endpoint")

        packet = WebGLPacket.from_payload(payload=data_packet, metadata=metadata)
        framed_bytes = packet.to_framed_bytes()

        try:
            assert self.sock is not None
            self.sock.sendall(framed_bytes)
            num_bytes = len(framed_bytes)
            self.packets_sent += 1
            self.bytes_sent += num_bytes
            self.last_stream_time = time.time()
            return num_bytes
        except OSError as e:
            self._connected = False
            self.disconnect()
            raise WebGLConnectionError(f"Stream interrupted due to socket error: {e}") from e

    def stream_batch(self, batch: List[Union[Dict[str, Any], WebGLPacket]]) -> int:
        """Streams a list of dictionary payloads or WebGLPacket objects."""
        total_bytes = 0
        for item in batch:
            if isinstance(item, WebGLPacket):
                framed = item.to_framed_bytes()
                if not self.is_connected:
                    if self.auto_reconnect:
                        self.connect()
                    else:
                        raise WebGLConnectionError("Not connected to WebGL client endpoint")
                try:
                    assert self.sock is not None
                    self.sock.sendall(framed)
                    total_bytes += len(framed)
                    self.packets_sent += 1
                    self.bytes_sent += len(framed)
                    self.last_stream_time = time.time()
                except OSError as e:
                    self._connected = False
                    self.disconnect()
                    raise WebGLConnectionError(f"Batch stream interrupted: {e}") from e
            elif isinstance(item, dict):
                total_bytes += self.stream_data(item)
        return total_bytes

    def stream_sparsity_payload(self, matrix_or_payload: Any) -> int:
        """Streams a WebSparsityMatrix or BrowserSparsityPayload with metadata routing."""
        if hasattr(matrix_or_payload, "to_browser_format"):
            browser_payload = matrix_or_payload.to_browser_format()
            payload_dict = browser_payload.model_dump()
        elif hasattr(matrix_or_payload, "model_dump"):
            payload_dict = matrix_or_payload.model_dump()
        elif isinstance(matrix_or_payload, dict):
            payload_dict = matrix_or_payload
        else:
            raise TypeError(f"Unsupported sparsity matrix type: {type(matrix_or_payload)}")

        return self.stream_data(payload_dict, metadata={"content_type": "sparsity"})

    def receive_packet(self, timeout: Optional[float] = None) -> WebGLPacket:
        """Receives and unpacks a single framed WebGLPacket from the connected socket."""
        if not self.is_connected:
            raise WebGLConnectionError("Not connected to WebGL client endpoint")

        assert self.sock is not None
        if timeout is not None:
            self.sock.settimeout(timeout)
        else:
            self.sock.settimeout(self.timeout)

        try:
            header = recv_exact(self.sock, HEADER_SIZE)
            payload_len = unpack_frame_header(header)
            payload_bytes = recv_exact(self.sock, payload_len)

            packet = WebGLPacket.from_json_bytes(payload_bytes)
            self.packets_received += 1
            self.bytes_received += HEADER_SIZE + payload_len
            return packet
        except (socket.timeout, TimeoutError) as e:
            raise TimeoutError(f"Socket timed out waiting for WebGL packet: {e}") from e
        except OSError as e:
            self._connected = False
            self.disconnect()
            raise WebGLConnectionError(f"Socket receive error: {e}") from e

    def _flush(self) -> None:
        """Compatibility no-op for file-like stream flush calls."""

    def __enter__(self) -> WebGLStreamer:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()

    def __repr__(self) -> str:
        return f"WebGLStreamer(endpoint='{self.host}:{self.port}', connected={self.is_connected}, packets_sent={self.packets_sent})"
