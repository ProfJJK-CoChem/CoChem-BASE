"""Comprehensive Zero-Mock Physical Test Suite for cochem_base.interfaces.web_streaming.

Validates Pydantic v2 WebGLPacket models, binary protocol framing (BrowserStreaming-014),
real TCP loopback socket communication, bidirectional data streaming, error handling,
telemetry stats, context manager protocol, LF line endings, and path sanitization.
"""

from __future__ import annotations

import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import cochem_base.interfaces as interfaces
from cochem_base.interfaces.web_matrices import BrowserSparsityPayload, SparsityDimensions, WebSparsityMatrix
from cochem_base.interfaces.web_streaming import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SOCKET_TIMEOUT,
    HEADER_SIZE,
    HEADER_STRUCT,
    MAX_PACKET_SIZE,
    STREAMING_PROTOCOL_VERSION,
    WebGLConnectionError,
    WebGLPacket,
    WebGLPacketError,
    WebGLSerializationError,
    WebGLStreamer,
    WebGLStreamError,
    pack_frame,
    recv_exact,
    unpack_frame_header,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def target_file_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/web_streaming.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "web_streaming.py"
    assert path.is_file(), f"Target file does not exist at {path}"
    return path


@pytest.fixture
def target_test_path() -> Path:
    """Return the absolute path to test_suite/test_web_streaming.py."""
    path = Path(__file__).resolve()
    assert path.is_file(), f"Test file does not exist at {path}"
    return path


# ============================================================================
# Section 1: File Encoding, LF Line Endings, and Zero Path Leakage
# ============================================================================


def test_file_encoding_and_lf_line_endings(target_file_path: Path, target_test_path: Path) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for file_path in [target_file_path, target_test_path]:
        raw = file_path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {file_path.name}"
        assert b"\n" in raw, f"Missing newline characters in {file_path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {file_path.name}"

        content = file_path.read_text(encoding="utf-8")
        assert len(content) > 200, f"File {file_path.name} content is unexpectedly small."


def test_zero_personal_path_leaks(target_file_path: Path, target_test_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in target files."""
    patterns = leak_patterns()
    for file_path in [target_file_path, target_test_path]:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {file_path.name}: {leaks}"


# ============================================================================
# Section 2: Module Exports & Protocol Constants
# ============================================================================


def test_protocol_constants() -> None:
    """Verify protocol constants match BrowserStreaming-014 specification."""
    assert STREAMING_PROTOCOL_VERSION == "BrowserStreaming-014"
    assert DEFAULT_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 8080
    assert DEFAULT_SOCKET_TIMEOUT == 10.0
    assert HEADER_SIZE == 4
    assert MAX_PACKET_SIZE == 64 * 1024 * 1024


def test_interface_lazy_exports() -> None:
    """Verify WebGLPacket and WebGLStreamer are accessible via cochem_base.interfaces."""
    assert interfaces.WebGLPacket is WebGLPacket
    assert interfaces.WebGLStreamer is WebGLStreamer


# ============================================================================
# Section 3: Low-Level Framing Utilities
# ============================================================================


def test_pack_frame_valid() -> None:
    """Verify pack_frame prepends a 4-byte big-endian unsigned integer."""
    payload = b'{"key": "value"}'
    framed = pack_frame(payload)
    assert len(framed) == len(payload) + 4
    length = struct.unpack(">I", framed[:4])[0]
    assert length == len(payload)
    assert framed[4:] == payload


def test_pack_frame_exceeds_max_size() -> None:
    """Verify pack_frame raises WebGLPacketError when payload exceeds MAX_PACKET_SIZE."""
    with pytest.raises(WebGLPacketError, match="exceeds maximum allowed packet size"):
        pack_frame(b"x" * (MAX_PACKET_SIZE + 1))


def test_unpack_frame_header_valid() -> None:
    """Verify unpack_frame_header accurately extracts integer length."""
    header = struct.pack(">I", 12345)
    assert unpack_frame_header(header) == 12345


def test_unpack_frame_header_invalid_length() -> None:
    """Verify unpack_frame_header raises WebGLPacketError on wrong header length."""
    with pytest.raises(WebGLPacketError, match="must be exactly 4 bytes"):
        unpack_frame_header(b"\x00\x00\x01")


def test_unpack_frame_header_exceeds_max() -> None:
    """Verify unpack_frame_header rejects lengths exceeding MAX_PACKET_SIZE."""
    header = struct.pack(">I", MAX_PACKET_SIZE + 100)
    with pytest.raises(WebGLPacketError, match="exceeds MAX_PACKET_SIZE"):
        unpack_frame_header(header)


# ============================================================================
# Section 4: Pydantic Model WebGLPacket Validation & Serialization
# ============================================================================


def test_webgl_packet_defaults() -> None:
    """Verify WebGLPacket initializes with correct defaults."""
    packet = WebGLPacket(payload={"type": "ping"})
    assert packet.protocol == "BrowserStreaming-014"
    assert isinstance(packet.timestamp, float)
    assert packet.timestamp > 0
    assert packet.payload == {"type": "ping"}
    assert packet.metadata == {}


def test_webgl_packet_from_payload() -> None:
    """Verify factory method WebGLPacket.from_payload."""
    packet = WebGLPacket.from_payload(
        payload={"orbitals": [1.0, 2.0, 3.0]},
        metadata={"source": "test_orca"},
    )
    assert packet.payload["orbitals"] == [1.0, 2.0, 3.0]
    assert packet.metadata["source"] == "test_orca"
    assert packet.protocol == "BrowserStreaming-014"


def test_webgl_packet_json_roundtrip() -> None:
    """Verify packet serializes to JSON bytes and reconstructs accurately."""
    original = WebGLPacket(
        protocol="BrowserStreaming-014",
        payload={"atom": "C", "coords": [0.0, 0.0, 0.0]},
        metadata={"mol_id": 42},
    )
    json_bytes = original.to_json_bytes()
    reconstructed = WebGLPacket.from_json_bytes(json_bytes)
    assert reconstructed.protocol == original.protocol
    assert reconstructed.payload == original.payload
    assert reconstructed.metadata == original.metadata
    assert abs(reconstructed.timestamp - original.timestamp) < 1e-4


def test_webgl_packet_framed_roundtrip() -> None:
    """Verify binary framing round-trip (>I prefix + JSON payload)."""
    packet = WebGLPacket(payload={"status": "converged", "energy": -76.42})
    framed = packet.to_framed_bytes()
    assert len(framed) > 4
    unpacked = WebGLPacket.from_framed_bytes(framed)
    assert unpacked.payload == packet.payload


def test_webgl_packet_from_framed_bytes_invalid() -> None:
    """Verify from_framed_bytes raises appropriate exceptions for corrupt frames."""
    # Frame too short
    with pytest.raises(WebGLPacketError, match="must have at least 4 bytes"):
        WebGLPacket.from_framed_bytes(b"\x00\x01")

    # Header specifies 100 bytes but only 5 provided
    corrupt_frame = struct.pack(">I", 100) + b"hello"
    with pytest.raises(WebGLPacketError, match="length mismatch"):
        WebGLPacket.from_framed_bytes(corrupt_frame)

    # Valid length prefix but corrupt JSON
    bad_json = b"{not-valid-json}"
    bad_frame = struct.pack(">I", len(bad_json)) + bad_json
    with pytest.raises(WebGLSerializationError):
        WebGLPacket.from_framed_bytes(bad_frame)


def test_webgl_packet_payload_size() -> None:
    """Verify payload_size returns accurate byte length."""
    packet = WebGLPacket(payload={"test": 123})
    assert packet.payload_size() == len(packet.to_json_bytes())


# ============================================================================
# Section 5: WebGLStreamer Configuration & State Properties
# ============================================================================


def test_webgl_streamer_initialization_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify WebGLStreamer defaults and environment variable overrides."""
    monkeypatch.delenv("COCHEM_WEBGL_HOST", raising=False)
    monkeypatch.delenv("COCHEM_WEBGL_PORT", raising=False)

    streamer = WebGLStreamer()
    assert streamer.host == "127.0.0.1"
    assert streamer.port == 8080
    assert streamer.timeout == 10.0
    assert streamer.tcp_nodelay is True
    assert streamer.auto_reconnect is False
    assert streamer.is_connected is False
    assert streamer.endpoint == ("127.0.0.1", 8080)
    assert streamer.packets_sent == 0
    assert streamer.bytes_sent == 0
    assert streamer.packets_received == 0
    assert streamer.bytes_received == 0
    assert streamer.last_stream_time is None


def test_webgl_streamer_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify WebGLStreamer reads host/port from environment."""
    monkeypatch.setenv("COCHEM_WEBGL_HOST", "192.168.1.100")
    monkeypatch.setenv("COCHEM_WEBGL_PORT", "9999")

    streamer = WebGLStreamer()
    assert streamer.host == "192.168.1.100"
    assert streamer.port == 9999


def test_webgl_streamer_disconnected_stream_raises() -> None:
    """Verify stream_data raises WebGLConnectionError when not connected."""
    streamer = WebGLStreamer(host="127.0.0.1", port=9999, auto_reconnect=False)
    with pytest.raises(WebGLConnectionError, match="Not connected to WebGL client endpoint"):
        streamer.stream_data({"key": "val"})

    with pytest.raises(WebGLConnectionError, match="Not connected to WebGL client endpoint"):
        streamer.receive_packet()


def test_webgl_streamer_property_mutations() -> None:
    """Verify property setters update state properly when disconnected."""
    streamer = WebGLStreamer(host="127.0.0.1", port=8080)
    streamer.host = "10.0.0.1"
    streamer.port = 8888
    streamer.timeout = 5.0
    streamer.auto_reconnect = True

    assert streamer.host == "10.0.0.1"
    assert streamer.port == 8888
    assert streamer.timeout == 5.0
    assert streamer.auto_reconnect is True


def test_webgl_streamer_stats_and_repr() -> None:
    """Verify streamer.stats dictionary and repr string format."""
    streamer = WebGLStreamer(host="127.0.0.1", port=8080)
    stats = streamer.stats
    assert stats["host"] == "127.0.0.1"
    assert stats["port"] == 8080
    assert stats["connected"] is False
    assert stats["packets_sent"] == 0
    assert "WebGLStreamer(endpoint='127.0.0.1:8080'" in repr(streamer)


# ============================================================================
# Section 6: Physical Loopback TCP Socket Streaming (Zero-Mock)
# ============================================================================


class LocalLoopbackServer:
    """Helper thread-based TCP loopback server for physical Zero-Mock testing."""

    def __init__(self) -> None:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_sock.listen(1)
        self.host, self.port = self.server_sock.getsockname()
        self.client_sock: socket.socket | None = None
        self.received_frames: list[bytes] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start accepting connections on a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self.server_sock.settimeout(3.0)
            self.client_sock, _ = self.server_sock.accept()
            self.client_sock.settimeout(3.0)
            while not self._stop_event.is_set():
                header = self.client_sock.recv(4)
                if not header:
                    break
                (length,) = struct.unpack(">I", header)
                payload = b""
                while len(payload) < length:
                    chunk = self.client_sock.recv(min(length - len(payload), 4096))
                    if not chunk:
                        break
                    payload += chunk
                self.received_frames.append(payload)
        except (TimeoutError, OSError):
            pass

    def send_frame(self, frame_bytes: bytes) -> None:
        """Send framed bytes from server to connected client."""
        if self.client_sock:
            self.client_sock.sendall(frame_bytes)

    def stop(self) -> None:
        """Shutdown and close sockets."""
        self._stop_event.set()
        if self.client_sock:
            try:
                self.client_sock.close()
            except OSError:
                pass
        try:
            self.server_sock.close()
        except OSError:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


def test_physical_stream_data_loopback() -> None:
    """Test real loopback socket transmission of WebGL data packets."""
    server = LocalLoopbackServer()
    server.start()

    try:
        streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
        assert streamer.is_connected is False

        streamer.connect()
        assert streamer.is_connected is True
        assert streamer.connected is True
        assert streamer.sock is not None

        # Send test payload
        payload = {"molecule": "H2O", "atoms": ["H", "H", "O"], "energy": -76.4}
        bytes_sent = streamer.stream_data(payload, metadata={"job": "opt"})

        assert bytes_sent > 0
        assert streamer.packets_sent == 1
        assert streamer.bytes_sent == bytes_sent
        assert streamer.last_stream_time is not None

        # Give server time to accumulate
        time.sleep(0.1)

        assert len(server.received_frames) == 1
        received_packet = WebGLPacket.from_json_bytes(server.received_frames[0])
        assert received_packet.payload == payload
        assert received_packet.metadata == {"job": "opt"}
        assert received_packet.protocol == "BrowserStreaming-014"

        streamer.disconnect()
        assert streamer.is_connected is False
    finally:
        server.stop()


def test_physical_context_manager() -> None:
    """Test WebGLStreamer with statement context manager protocol."""
    server = LocalLoopbackServer()
    server.start()

    try:
        with WebGLStreamer(host=server.host, port=server.port, timeout=2.0) as streamer:
            assert streamer.is_connected is True
            streamer.stream_data({"step": 1})
            streamer.stream_data({"step": 2})

        # Disconnected automatically after context exit
        assert streamer.is_connected is False
        time.sleep(0.1)
        assert len(server.received_frames) == 2
    finally:
        server.stop()


def test_physical_stream_batch() -> None:
    """Test streaming batch of packets across real socket."""
    server = LocalLoopbackServer()
    server.start()

    try:
        streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
        streamer.connect()

        batch: list[dict[str, Any] | WebGLPacket] = [
            {"frame": 1, "progress": 0.25},
            WebGLPacket(payload={"frame": 2, "progress": 0.50}),
            {"frame": 3, "progress": 0.75},
            WebGLPacket(payload={"frame": 4, "progress": 1.00}),
        ]

        total_bytes = streamer.stream_batch(batch)
        assert total_bytes > 0
        assert streamer.packets_sent == 4

        time.sleep(0.1)
        assert len(server.received_frames) == 4
        streamer.disconnect()
    finally:
        server.stop()


def test_physical_stream_sparsity_payload() -> None:
    """Test streaming sparse matrix payloads (BrowserSparsityPayload and WebSparsityMatrix)."""
    server = LocalLoopbackServer()
    server.start()

    try:
        # Create real WebSparsityMatrix
        matrix = WebSparsityMatrix(rows=3, cols=3)
        matrix.add_element(0, 0, 1.5)
        matrix.add_element(1, 2, 3.7)

        streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
        streamer.connect()

        # Stream via matrix instance
        bytes_sent1 = streamer.stream_sparsity_payload(matrix)
        assert bytes_sent1 > 0

        # Stream via BrowserSparsityPayload
        payload_obj = matrix.to_browser_format()
        bytes_sent2 = streamer.stream_sparsity_payload(payload_obj)
        assert bytes_sent2 > 0

        time.sleep(0.1)
        assert len(server.received_frames) == 2

        # Verify received sparsity format
        packet1 = WebGLPacket.from_json_bytes(server.received_frames[0])
        assert packet1.metadata["content_type"] == "sparsity"
        reconstructed_payload = BrowserSparsityPayload.model_validate(packet1.payload)
        reconstructed_mat = reconstructed_payload.to_matrix()
        assert reconstructed_mat.get_element(0, 0) == pytest.approx(1.5)
        assert reconstructed_mat.get_element(1, 2) == pytest.approx(3.7)

        streamer.disconnect()
    finally:
        server.stop()


def test_physical_bidirectional_receive_packet() -> None:
    """Test streamer.receive_packet over loopback socket."""
    server = LocalLoopbackServer()
    server.start()

    try:
        streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
        streamer.connect()
        time.sleep(0.05)

        # Server sends a framed packet back to the client
        send_packet = WebGLPacket(payload={"ack": "ready", "session_id": "sess-99"})
        server.send_frame(send_packet.to_framed_bytes())

        received = streamer.receive_packet(timeout=2.0)
        assert received.payload == {"ack": "ready", "session_id": "sess-99"}
        assert streamer.packets_received == 1
        assert streamer.bytes_received > 0

        streamer.disconnect()
    finally:
        server.stop()


def test_connection_refused_error() -> None:
    """Test WebGLStreamer raises WebGLConnectionError when port is unreachable."""
    # Port 1 is reserved and typically refused on localhost
    streamer = WebGLStreamer(host="127.0.0.1", port=1, timeout=0.5)
    with pytest.raises(WebGLConnectionError, match="Failed to connect to WebGL client"):
        streamer.connect()
    assert streamer.is_connected is False


def test_reconnect_and_reset_stats() -> None:
    """Test streamer reconnect and reset_stats functionality."""
    server = LocalLoopbackServer()
    server.start()

    try:
        streamer = WebGLStreamer(host=server.host, port=server.port, timeout=2.0)
        streamer.connect()
        streamer.stream_data({"test": 1})
        assert streamer.packets_sent == 1

        streamer.reset_stats()
        assert streamer.packets_sent == 0
        assert streamer.bytes_sent == 0

        streamer.reconnect()
        assert streamer.is_connected is True
        streamer.stream_data({"test": 2})
        assert streamer.packets_sent == 1

        streamer.close()
        assert streamer.is_connected is False
    finally:
        server.stop()
