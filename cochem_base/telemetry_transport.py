"""Cross-platform local telemetry datagram transport."""

import json
import socket
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cochem_base.config_loader import (
    get_telemetry_socket_path,
    get_telemetry_transport,
    get_telemetry_udp_address,
)


def send_telemetry_payload(payload: Dict[str, Any]) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    transport = get_telemetry_transport()
    if transport == "unix":
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
                client.sendto(encoded, str(get_telemetry_socket_path()))
            return
        except OSError:
            if "COCHEM_TELEMETRY_TRANSPORT" in __import__("os").environ:
                return
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.sendto(encoded, get_telemetry_udp_address())


def create_telemetry_server_socket() -> Tuple[socket.socket, Optional[Path]]:
    transport = get_telemetry_transport()
    if transport == "unix":
        socket_path = get_telemetry_socket_path()
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            socket_path.unlink(missing_ok=True)
        except OSError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        server.bind(str(socket_path))
        server.setblocking(False)
        return server, socket_path
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(get_telemetry_udp_address())
    server.setblocking(False)
    return server, None


def close_telemetry_server_socket(server: socket.socket, socket_path: Optional[Path]) -> None:
    server.close()
    if socket_path is not None:
        try:
            socket_path.unlink(missing_ok=True)
        except OSError:
            pass
