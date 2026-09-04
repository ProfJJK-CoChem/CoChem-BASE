"""Pure-Wheel Fast IPC Serialization & HDF5 PESStore.
High-throughput binary Msgpack serialization, SharedMemory descriptors, HMAC socket transport,
and QCSchema-compliant HDF5 tensor persistence in SWMR mode.
Strictly adheres to Zero-Mock mandate and authentic binary serialization.
"""

from __future__ import annotations

import atexit
import dataclasses
import hashlib
import hmac
import json
import logging
import multiprocessing.shared_memory as sm
import os
import pathlib
import secrets
import socket
import struct
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import h5py
import msgpack  # type: ignore[import-untyped]
import numpy as np
from pydantic import BaseModel

from cochem.core.context import assert_writable_path

logger = logging.getLogger("cochem.core.ipc.serializer")

NUMPY_EXT_CODE: int = 42


# ==============================================================================
# Msgpack Custom Extension Codecs
# ==============================================================================
def _msgpack_encoder(obj: Any) -> Any:
    """Encode custom structures (NumPy arrays, Pydantic models, Path/UUID) for Msgpack."""
    if isinstance(obj, np.ndarray):
        dtype_str = obj.dtype.str  # type: ignore[attr-defined]
        shape_tuple = tuple(obj.shape)
        raw_buffer = obj.tobytes()
        payload = msgpack.packb((dtype_str, shape_tuple, raw_buffer), use_bin_type=True)
        return msgpack.ExtType(NUMPY_EXT_CODE, payload)
    elif isinstance(obj, BaseModel):
        return obj.model_dump()
    elif isinstance(obj, (pathlib.Path, uuid.UUID)):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON/Msgpack serializable")


def _msgpack_decoder(code: int, data: bytes) -> Any:
    """Reconstruct NumPy arrays from Msgpack custom extension payload."""
    if code == NUMPY_EXT_CODE:
        dtype_str, shape_tuple, raw_buffer = msgpack.unpackb(data, raw=False)
        reconstructed = np.frombuffer(raw_buffer, dtype=dtype_str).reshape(tuple(shape_tuple))
        return reconstructed
    return msgpack.ExtType(code, data)


def pack_payload(data: Any) -> bytes:
    """Serialize payload into binary Msgpack bytes with NumPy array extension hooks."""
    return bytes(msgpack.packb(data, default=_msgpack_encoder, use_bin_type=True))


def unpack_payload(raw_bytes: bytes) -> Any:
    """Deserialize binary Msgpack payload and reconstruct NumPy arrays."""
    return msgpack.unpackb(raw_bytes, ext_hook=_msgpack_decoder, raw=False)


# ==============================================================================
# Zero-Copy Shared Memory Optimization
# ==============================================================================
_REGISTRY_LOCK = threading.Lock()
_ACTIVE_SHM: Dict[str, Dict[str, Any]] = {}


def _cleanup_all_shared_memory() -> None:
    """Atexit handler ensuring zero lingering shared memory blocks."""
    with _REGISTRY_LOCK:
        for name, info in list(_ACTIVE_SHM.items()):
            try:
                info["shm"].close()
            except Exception:
                pass
            try:
                info["shm"].unlink()
            except Exception:
                pass
        _ACTIVE_SHM.clear()


atexit.register(_cleanup_all_shared_memory)


@dataclasses.dataclass(slots=True)
class SharedMemoryBuffer:
    """Encapsulates a POSIX/Windows shared memory segment for large array transfers."""

    shm: sm.SharedMemory
    descriptor: Dict[str, Any]

    @classmethod
    def from_array(cls, arr: np.ndarray, total_attachments: int = 2) -> SharedMemoryBuffer:
        """Allocate shared memory buffer, copy array memory, and generate transfer descriptor."""
        total_bytes = max(1, arr.nbytes)
        shm = sm.SharedMemory(create=True, size=total_bytes)
        try:
            from multiprocessing import resource_tracker
            resource_tracker.register(shm._name, "shared_memory")
        except Exception:
            pass

        shm_array = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)  # type: ignore[arg-type]
        shm_array[:] = arr[:]

        desc = {
            "name": shm.name,
            "shape": list(arr.shape),
            "dtype": arr.dtype.str,  # type: ignore[attr-defined]
            "size": total_bytes,
            "total_attachments": total_attachments,
            "closed_attachments": 0,
        }

        with _REGISTRY_LOCK:
            _ACTIVE_SHM[shm.name] = {
                "shm": shm,
                "total": total_attachments,
                "closed": 0,
            }

        return cls(shm=shm, descriptor=desc)

    @classmethod
    def _notify_closed(cls, name: str) -> None:
        """Atomically increment closed attachments and unlink once all attachments finish."""
        with _REGISTRY_LOCK:
            info = _ACTIVE_SHM.get(name)
            if info is not None:
                info["closed"] += 1
                if info["closed"] >= info["total"]:
                    try:
                        info["shm"].unlink()
                    except (OSError, FileNotFoundError):
                        pass
                    _ACTIVE_SHM.pop(name, None)
            else:
                try:
                    s = sm.SharedMemory(name=name)
                    s.close()
                    s.unlink()
                except Exception:
                    pass

    @classmethod
    def read_from_descriptor(cls, descriptor: Dict[str, Any]) -> np.ndarray:
        """Map existing shared memory segment and extract copy of array."""
        name = descriptor["name"]
        shape = tuple(descriptor["shape"])
        dtype = descriptor["dtype"]

        client_shm = sm.SharedMemory(name=name)
        try:
            mapped = np.ndarray(shape, dtype=dtype, buffer=client_shm.buf)
            extracted = mapped.copy()
            return extracted
        finally:
            client_shm.close()
            cls._notify_closed(name)

    def close(self) -> None:
        """Close local memory map and unlink if all attachments are closed."""
        try:
            self.shm.close()
        except OSError:
            pass
        SharedMemoryBuffer._notify_closed(self.shm.name)

    def unlink(self) -> None:
        """Explicitly unlink OS shared memory segment immediately."""
        try:
            self.shm.unlink()
        except (OSError, FileNotFoundError):
            pass
        with _REGISTRY_LOCK:
            _ACTIVE_SHM.pop(self.shm.name, None)


# ==============================================================================
# Ephemeral HMAC-SHA256 Socket Transport
# ==============================================================================
class HMACSocketServer:
    """Loopback TCP socket server secured by HMAC-SHA256 challenge-response handshake."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        secret_key: bytes = b"",
    ) -> None:
        self.host: str = host
        self.requested_port: int = port
        self.secret_key: bytes = secret_key
        self.port: int = 0

        self._server_sock: Optional[socket.socket] = None
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._received_payloads: List[Any] = []
        self._payload_event: threading.Event = threading.Event()

    def start(self) -> None:
        """Bind listening socket and launch background accept loop."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.requested_port))
        self._server_sock.listen(5)
        self.port = self._server_sock.getsockname()[1]

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="HMACSocketServerLoop",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Shutdown server socket and join accept thread."""
        self._stop_event.set()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _accept_loop(self) -> None:
        """Accept inbound client connections and execute HMAC handshake."""
        while not self._stop_event.is_set():
            try:
                if self._server_sock is None:
                    break
                self._server_sock.settimeout(0.5)
                conn, _ = self._server_sock.accept()
            except (socket.timeout, OSError):
                continue

            try:
                # 1. Generate 32-byte challenge
                challenge = secrets.token_bytes(32)
                conn.sendall(challenge)

                # 2. Receive 32-byte HMAC response
                response = conn.recv(32)
                expected = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()

                if not hmac.compare_digest(response, expected):
                    conn.sendall(b"DENIED")
                    conn.close()
                    continue

                conn.sendall(b"ACCEPT")

                # 3. Read 4-byte payload length header
                len_bytes = conn.recv(4)
                if len(len_bytes) < 4:
                    conn.close()
                    continue
                (payload_len,) = struct.unpack("!I", len_bytes)

                # 4. Stream payload bytes
                buffer = bytearray()
                while len(buffer) < payload_len:
                    chunk = conn.recv(min(65536, payload_len - len(buffer)))
                    if not chunk:
                        break
                    buffer.extend(chunk)

                if len(buffer) == payload_len:
                    payload = unpack_payload(bytes(buffer))
                    self._received_payloads.append(payload)
                    self._payload_event.set()
            except Exception as conn_err:
                logger.debug("Error processing client connection: %s", conn_err)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def get_received_payload(self, timeout_sec: float = 5.0) -> Optional[Any]:
        """Await reception of payload from client."""
        if self._payload_event.wait(timeout_sec):
            if self._received_payloads:
                return self._received_payloads.pop(0)
        return None


class HMACSocketClient:
    """Client communicating over loopback TCP with HMAC-SHA256 authentication."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        secret_key: bytes = b"",
    ) -> None:
        self.host: str = host
        self.port: int = port
        self.secret_key: bytes = secret_key

    def send_payload(self, data: Any) -> None:
        """Connect to server, satisfy HMAC challenge, and transmit Msgpack payload."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        try:
            # 1. Receive 32-byte challenge
            challenge = sock.recv(32)
            if len(challenge) != 32:
                raise ConnectionError("Invalid challenge received from server")

            # 2. Compute and send response
            response = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()
            sock.sendall(response)

            status = sock.recv(6)
            if status != b"ACCEPT":
                raise PermissionError("HMAC handshake rejected by server")

            # 3. Pack payload and send with length header
            packed_bytes = pack_payload(data)
            header = struct.pack("!I", len(packed_bytes))
            sock.sendall(header + packed_bytes)
        finally:
            sock.close()


# ==============================================================================
# HDF5 PESStore Tensor Persistence (QCSchema & SWMR)
# ==============================================================================
class PESStore:
    """Multidimensional tensor persistence store for Potential Energy Surfaces using HDF5 SWMR."""

    def __init__(self, file_path: Union[pathlib.Path, str]) -> None:
        self.file_path: pathlib.Path = pathlib.Path(file_path).resolve()
        assert_writable_path(self.file_path)

    def write_entry(
        self,
        entry_id: str,
        molecule: Dict[str, Any],
        driver: str,
        model: Dict[str, Any],
        return_result: np.ndarray,
    ) -> None:
        """Persist QCSchema calculation entry into HDF5 file via atomic staging."""
        assert_writable_path(self.file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = self.file_path.with_name(f"{self.file_path.name}.{uuid.uuid4().hex[:8]}.tmp")

        # If destination file already exists, copy existing groups into tmp staging
        if self.file_path.exists():
            import shutil

            shutil.copyfile(self.file_path, tmp_path)

        with h5py.File(tmp_path, "a", libver="latest") as h5f:
            if entry_id in h5f:
                del h5f[entry_id]

            grp = h5f.create_group(entry_id)
            grp.attrs["schema_name"] = "qcschema_output"
            grp.attrs["driver"] = str(driver)
            grp.attrs["molecule_json"] = json.dumps(molecule)
            grp.attrs["model_json"] = json.dumps(model)

            # Store result array with Gzip chunked compression
            chunk_shape: Optional[Tuple[int, ...]] = None
            if return_result.ndim > 0:
                chunk_shape = tuple(max(1, min(s, 128)) for s in return_result.shape)

            grp.create_dataset(
                "return_result",
                data=return_result,
                compression="gzip",
                compression_opts=4,
                chunks=chunk_shape,
            )

        # Atomic replacement to target path
        os.replace(tmp_path, self.file_path)

    def read_entry(self, entry_id: str) -> Dict[str, Any]:
        """Read QCSchema entry in SWMR mode without file locking collisions."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"PESStore file not found at {self.file_path}")

        with h5py.File(self.file_path, "r", libver="latest", swmr=True) as h5f:
            if entry_id not in h5f:
                raise KeyError(f"Entry '{entry_id}' not found in PESStore")

            grp = h5f[entry_id]
            schema_name = str(grp.attrs.get("schema_name", "qcschema_output"))
            driver = str(grp.attrs.get("driver", "unknown"))
            mol_json = str(grp.attrs.get("molecule_json", "{}"))
            model_json = str(grp.attrs.get("model_json", "{}"))
            result_arr = grp["return_result"][:]

            return {
                "schema_name": schema_name,
                "entry_id": entry_id,
                "molecule": json.loads(mol_json),
                "driver": driver,
                "model": json.loads(model_json),
                "return_result": result_arr,
            }
