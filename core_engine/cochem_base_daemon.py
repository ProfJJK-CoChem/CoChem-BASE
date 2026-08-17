"""ZeroMQ PUB/SUB Daemon for CoChem Base async telemetry and state broadcasts."""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import zmq
import zmq.asyncio
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class TelemetryPayload(BaseModel):
    """Generic Pydantic model for ZeroMQ telemetry payloads."""
    model_config = ConfigDict(extra="allow")


class ZeroMQDaemon:
    """Async ZeroMQ PUB/SUB daemon for handling telemetry and state broadcasts.

    Sets up a PUB socket on port 5555 (default) and SUB socket on port 5556 (default).
    """

    def __init__(
        self,
        pub_port: int = 5555,
        sub_port: int = 5556,
        host: str = "127.0.0.1",
    ) -> None:
        self.pub_port = pub_port
        self.sub_port = sub_port
        self.host = host
        self.ctx: Optional[zmq.asyncio.Context] = None
        self.pub_socket: Optional[zmq.asyncio.Socket] = None
        self.sub_socket: Optional[zmq.asyncio.Socket] = None
        self._running = False

    async def start(self) -> None:
        """Initialize sockets and bind/connect ports."""
        self.ctx = zmq.asyncio.Context()
        self.pub_socket = self.ctx.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://{self.host}:{self.pub_port}")

        self.sub_socket = self.ctx.socket(zmq.SUB)
        self.sub_socket.bind(f"tcp://{self.host}:{self.sub_port}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self._running = True
        logger.info(f"ZeroMQDaemon started: PUB on {self.host}:{self.pub_port}, SUB on {self.host}:{self.sub_port}")

    async def start_pub_server(self, port: int = 5555) -> None:
        """Start the PUB server socket on specified port."""
        self.pub_port = port
        if not self.ctx:
            self.ctx = zmq.asyncio.Context()
        if not self.pub_socket:
            self.pub_socket = self.ctx.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://{self.host}:{self.pub_port}")
        self._running = True
        logger.info(f"PUB server bound to {self.host}:{self.pub_port}")

    async def start_sub_listener(self, port: int = 5556) -> None:
        """Start the SUB listener socket on specified port."""
        self.sub_port = port
        if not self.ctx:
            self.ctx = zmq.asyncio.Context()
        if not self.sub_socket:
            self.sub_socket = self.ctx.socket(zmq.SUB)
            self.sub_socket.bind(f"tcp://{self.host}:{self.sub_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._running = True
        logger.info(f"SUB listener bound to {self.host}:{self.sub_port}")

    async def stop(self) -> None:
        """Close sockets and terminate context."""
        self._running = False
        if self.pub_socket:
            self.pub_socket.close()
            self.pub_socket = None
        if self.sub_socket:
            self.sub_socket.close()
            self.sub_socket = None
        if self.ctx:
            self.ctx.term()
            self.ctx = None
        logger.info("ZeroMQDaemon stopped")

    async def publish(self, topic: str, data: Dict[str, Any]) -> None:
        """Publish a JSON payload on the given topic."""
        if not self.pub_socket or not self._running:
            raise RuntimeError("ZeroMQDaemon is not running")
        
        # Structural validation: throws ValidationError on bad data.
        payload = TelemetryPayload.model_validate(data).model_dump_json()
        await self.pub_socket.send_multipart([topic.encode("utf-8"), payload.encode("utf-8")])

    async def broadcast_state(self, topic: str, payload: Dict[str, Any]) -> None:
        """Broadcast state payload on specified topic."""
        await self.publish(topic, payload)

    async def recv_message(self) -> Tuple[str, Dict[str, Any]]:
        """Receive a topic and JSON payload from SUB socket."""
        if not self.sub_socket or not self._running:
            raise RuntimeError("ZeroMQDaemon is not running")
        parts = await self.sub_socket.recv_multipart()
        topic = parts[0].decode("utf-8")
        payload_str = parts[1].decode("utf-8")
        
        # Pydantic boundary validation. Let ValidationError propagate if malformed.
        data = TelemetryPayload.model_validate_json(payload_str).model_dump()
        return topic, data

    async def listen_for_events(self) -> Tuple[str, Dict[str, Any]]:
        """Listen for incoming telemetry events on SUB socket."""
        return await self.recv_message()

    async def heartbeat_loop(self, interval_sec: float = 1.0) -> None:
        """Async heartbeat loop for periodic status broadcasts."""
        while self._running:
            await self.publish("heartbeat", {"status": "ok"})
            await asyncio.sleep(interval_sec)


# Backward-compatible alias
BaseDaemon = ZeroMQDaemon
