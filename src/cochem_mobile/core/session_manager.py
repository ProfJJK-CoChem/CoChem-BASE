"""Thin-Client Interface & Resilient Session Manager (REQ-MOB-001).

Implements decoupled kernel session lifecycle, monotonic sequence indexing,
durable ring-buffer message spooling, heartbeat watchdog, and transparent
cellular/tab-suspension reconnect replay.
"""

from __future__ import annotations

import collections
import hashlib
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, List, Optional


class SessionState(str, Enum):
    """Lifecycle state of a thin-client session."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISCONNECTED = "disconnected"
    TERMINATED = "terminated"


class SessionSecurityError(Exception):
    """Raised on invalid session token or unauthorized session access."""


@dataclass(frozen=True)
class SpooledMessage:
    """Monotonically sequenced message spooled in the session ring buffer."""
    seq_id: int
    timestamp: float
    topic: str
    payload: Dict[str, Any]
    msg_hash: str

    @classmethod
    def create(cls, seq_id: int, topic: str, payload: Dict[str, Any]) -> SpooledMessage:
        ts = time.time()
        ser = json.dumps(payload, sort_keys=True)
        h = hashlib.sha256(f"{seq_id}:{ts:.6f}:{topic}:{ser}".encode("utf-8")).hexdigest()
        return cls(
            seq_id=seq_id,
            timestamp=ts,
            topic=topic,
            payload=payload,
            msg_hash=h,
        )


class ClientSession:
    """Stateful thin-client session with ring buffer and heartbeat tracking."""

    def __init__(
        self,
        session_id: str,
        auth_token: str,
        client_metadata: Optional[Dict[str, Any]] = None,
        max_buffer_size: int = 1000,
    ) -> None:
        self.session_id = session_id
        self.auth_token = auth_token
        self.client_metadata = dict(client_metadata or {})
        self.max_buffer_size = max(1, max_buffer_size)
        self.created_at = time.time()
        self.last_heartbeat = self.created_at
        self.state = SessionState.ACTIVE
        self._seq_counter = 0
        self._buffer: Deque[SpooledMessage] = collections.deque(maxlen=self.max_buffer_size)
        self._lock = threading.RLock()

    def record_heartbeat(self, timestamp: Optional[float] = None) -> None:
        """Update last heartbeat timestamp and transition state to ACTIVE if not terminated."""
        with self._lock:
            if self.state != SessionState.TERMINATED:
                self.last_heartbeat = timestamp if timestamp is not None else time.time()
                self.state = SessionState.ACTIVE

    def spool(self, topic: str, payload: Dict[str, Any]) -> SpooledMessage:
        """Atomically append a message with a monotonic sequence identifier."""
        with self._lock:
            self._seq_counter += 1
            msg = SpooledMessage.create(
                seq_id=self._seq_counter,
                topic=topic,
                payload=payload,
            )
            self._buffer.append(msg)
            return msg

    def get_messages_since(self, since_seq_id: int) -> List[SpooledMessage]:
        """Fetch all spooled messages strictly after since_seq_id."""
        with self._lock:
            return [m for m in self._buffer if m.seq_id > since_seq_id]

    def get_all_buffered(self) -> List[SpooledMessage]:
        """Return a snapshot of the current ring buffer."""
        with self._lock:
            return list(self._buffer)

    @property
    def latest_seq_id(self) -> int:
        with self._lock:
            return self._seq_counter


class SessionManager:
    """Thread-safe manager for mobile thin-client sessions."""

    def __init__(
        self,
        heartbeat_timeout_seconds: float = 60.0,
        disconnect_timeout_seconds: float = 300.0,
    ) -> None:
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self.disconnect_timeout = disconnect_timeout_seconds
        self._sessions: Dict[str, ClientSession] = {}
        self._lock = threading.RLock()

    def create_session(
        self,
        client_metadata: Optional[Dict[str, Any]] = None,
        max_buffer_size: int = 1000,
    ) -> ClientSession:
        """Initialize a new thin-client session with a secure cryptographic token."""
        with self._lock:
            session_id = str(uuid.uuid4())
            auth_token = secrets.token_hex(32)
            session = ClientSession(
                session_id=session_id,
                auth_token=auth_token,
                client_metadata=client_metadata,
                max_buffer_size=max_buffer_size,
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str, auth_token: Optional[str] = None) -> ClientSession:
        """Retrieve an existing session, verifying auth token if supplied."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session '{session_id}' does not exist.")
            if auth_token is not None and not secrets.compare_digest(session.auth_token, auth_token):
                raise SessionSecurityError(f"Invalid authentication token for session '{session_id}'.")
            return session

    def record_heartbeat(
        self,
        session_id: str,
        auth_token: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Record heartbeat from thin client."""
        with self._lock:
            session = self.get_session(session_id, auth_token)
            session.record_heartbeat(timestamp=timestamp)
            return True

    def spool(self, session_id: str, topic: str, payload: Dict[str, Any]) -> SpooledMessage:
        """Spool a message to a session ring buffer."""
        with self._lock:
            session = self.get_session(session_id)
            return session.spool(topic, payload)

    def replay_messages(
        self,
        session_id: str,
        since_seq_id: int,
        auth_token: Optional[str] = None,
    ) -> List[SpooledMessage]:
        """Replay missed messages for transparent reconnection."""
        with self._lock:
            session = self.get_session(session_id, auth_token)
            session.record_heartbeat()
            return session.get_messages_since(since_seq_id)

    def terminate_session(self, session_id: str, auth_token: Optional[str] = None) -> bool:
        """Explicitly terminate and remove a session."""
        with self._lock:
            session = self.get_session(session_id, auth_token)
            session.state = SessionState.TERMINATED
            self._sessions.pop(session_id, None)
            return True

    def sweep_stale_sessions(self, now: Optional[float] = None) -> List[str]:
        """Audit active sessions, updating states to SUSPENDED or DISCONNECTED and purging dead ones."""
        current_time = now if now is not None else time.time()
        purged: List[str] = []

        with self._lock:
            for sid, sess in list(self._sessions.items()):
                idle_duration = current_time - sess.last_heartbeat
                if sess.state == SessionState.TERMINATED:
                    purged.append(sid)
                    self._sessions.pop(sid, None)
                elif idle_duration > self.disconnect_timeout:
                    sess.state = SessionState.DISCONNECTED
                    purged.append(sid)
                    self._sessions.pop(sid, None)
                elif idle_duration > self.heartbeat_timeout:
                    sess.state = SessionState.SUSPENDED

        return purged

    @property
    def active_session_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if s.state == SessionState.ACTIVE)
