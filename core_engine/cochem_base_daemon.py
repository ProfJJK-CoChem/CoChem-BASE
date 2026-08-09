"""ZeroMQ PUB/SUB Daemon for CoChem Base async telemetry and state broadcasts."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional
import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)


class ZeroMQDaemon:
    """Async ZeroMQ PUB/SUB daemon for handling telemetry and state broadcasts.
    
    Sets up a PUB socket on port 5555 (default) and SUB socket on port 5556 (default).
    """

    def __init__(
        self,
        pub_port: int = 5555,
        sub_port: int = 5556,
        host: str = "127.0.0.1",
    ):
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
        self.pub_socket.bind(f"tcp://*:{self.pub_port}")

        self.sub_socket = self.ctx.socket(zmq.SUB)
        self.sub_socket.bind(f"tcp://*:{self.sub_port}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self._running = True
        logger.info(f"ZeroMQDaemon started: PUB on port {self.pub_port}, SUB on port {self.sub_port}")

    async def start_pub_server(self, port: int = 5555) -> None:
        """Start the PUB server socket on specified port."""
        self.pub_port = port
        if not self.ctx:
            self.ctx = zmq.asyncio.Context()
        if not self.pub_socket:
            self.pub_socket = self.ctx.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{self.pub_port}")
        self._running = True
        logger.info(f"PUB server bound to port {self.pub_port}")

    async def start_sub_listener(self, port: int = 5556) -> None:
        """Start the SUB listener socket on specified port."""
        self.sub_port = port
        if not self.ctx:
            self.ctx = zmq.asyncio.Context()
        if not self.sub_socket:
            self.sub_socket = self.ctx.socket(zmq.SUB)
            self.sub_socket.bind(f"tcp://*:{self.sub_port}")
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._running = True
        logger.info(f"SUB listener bound to port {self.sub_port}")

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
        payload = json.dumps(data)
        await self.pub_socket.send_multipart([topic.encode("utf-8"), payload.encode("utf-8")])

    async def broadcast_state(self, topic: str, payload: Dict[str, Any]) -> None:
        """Broadcast state payload on specified topic."""
        await self.publish(topic, payload)

    async def recv_message(self) -> tuple[str, Dict[str, Any]]:
        """Receive a topic and JSON payload from SUB socket."""
        if not self.sub_socket or not self._running:
            raise RuntimeError("ZeroMQDaemon is not running")
        parts = await self.sub_socket.recv_multipart()
        topic = parts[0].decode("utf-8")
        data = json.loads(parts[1].decode("utf-8"))
        return topic, data

    async def listen_for_events(self) -> tuple[str, Dict[str, Any]]:
        """Listen for incoming telemetry events on SUB socket."""
        return await self.recv_message()

    async def heartbeat_loop(self, interval_sec: float = 1.0) -> None:
        """Async heartbeat loop for periodic status broadcasts."""
        while self._running:
            await self.publish("heartbeat", {"status": "ok"})
            await asyncio.sleep(interval_sec)


# Backward-compatible alias
BaseDaemon = ZeroMQDaemon

