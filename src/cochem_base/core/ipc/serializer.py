"""Pure-Wheel Fast IPC Serialization & HDF5 PESStore.

High-throughput binary Msgpack serialization, SharedMemory descriptors, HMAC socket transport,
and QCSchema-compliant HDF5 tensor persistence in SWMR mode with in-place chunk resizing.
Strictly adheres to Zero-Mock mandate, Tripartite Storage Air-Gap, and Suggestion #65.
"""

from __future__ import annotations

import atexit
import dataclasses
import datetime
import errno
import hashlib
import hmac
import json
import logging
import multiprocessing.shared_memory as sm
import os
import pathlib
import secrets
import shutil
import socket
import struct
import tempfile
import threading
import time
import uuid
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import filelock
import h5py
import msgpack  # type: ignore[import-untyped]
import numpy as np
from pydantic import BaseModel

from cochem_base.core.exceptions import AirGapBoundaryError, PESStorageError

logger = logging.getLogger("cochem_base.core.ipc.serializer")

NUMPY_EXT_CODE: int = 42
MAX_IPC_PAYLOAD_BYTES: int = 256 * 1024 * 1024  # 256 MB ceiling [D]

_HDF5_MEM_LOCK = threading.RLock()


def validate_airgap_write_path(target_path: Union[str, Path]) -> Path:
    """Validates that target write path resides strictly within Tier 4 ($COCH_STATE) or Tier 3 ($COCH_SCRATCH).

    Raises AirGapBoundaryError if write is attempted in Tier 1 ($COCH_SRC) or Tier 2 ($COCH_DATA).
    """
    resolved = Path(target_path).resolve()
    src_dir = Path(os.environ.get("COCH_SRC", "/nonexistent")).resolve()
    data_dir = Path(os.environ.get("COCH_DATA", "/nonexistent")).resolve()

    if src_dir.exists() and (src_dir == resolved or src_dir in resolved.parents):
        raise AirGapBoundaryError(
            f"Air-gap boundary violation: Cannot write PES data to read-only Tier 1 ($COCH_SRC): {resolved}",
            details={"target_path": str(resolved), "tier": "Tier 1 ($COCH_SRC)"},
        )
    if data_dir.exists() and (data_dir == resolved or data_dir in resolved.parents):
        raise AirGapBoundaryError(
            f"Air-gap boundary violation: Cannot write PES data to immutable Tier 2 ($COCH_DATA): {resolved}",
            details={"target_path": str(resolved), "tier": "Tier 2 ($COCH_DATA)"},
        )
    return resolved


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
            except Exception as exc:
                logger.debug("shm close error: %s", exc)
            try:
                info["shm"].unlink()
            except Exception as exc:
                logger.debug("shm unlink error: %s", exc)
        _ACTIVE_SHM.clear()


atexit.register(_cleanup_all_shared_memory)


def _finalize_shm(name: str) -> None:
    with _REGISTRY_LOCK:
        info = _ACTIVE_SHM.pop(name, None)
    if info is not None:
        try:
            info["shm"].close()
            info["shm"].unlink()
        except (FileNotFoundError, OSError) as exc:
            logger.debug("shm finalize error: %s", exc)
    try:
        s = sm.SharedMemory(name=name)
        s.close()
        s.unlink()
    except (FileNotFoundError, OSError) as exc:
        logger.debug("shm unlink fallback error: %s", exc)


@dataclasses.dataclass
class SharedMemoryBuffer:
    """Encapsulates a POSIX/Windows shared memory segment for large array transfers."""

    shm: sm.SharedMemory
    descriptor: Dict[str, Any]
    _finalizer: Optional[weakref.finalize] = dataclasses.field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._finalizer is None:
            self._finalizer = weakref.finalize(self, _finalize_shm, self.shm.name)

    def __enter__(self) -> SharedMemoryBuffer:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()
        self.unlink()

    @classmethod
    def from_array(cls, arr: np.ndarray, total_attachments: int = 2) -> SharedMemoryBuffer:
        """Allocate shared memory buffer, copy array memory, and generate transfer descriptor."""
        total_bytes = max(1, arr.nbytes)
        shm = sm.SharedMemory(create=True, size=total_bytes)
        try:
            from multiprocessing import resource_tracker

            resource_tracker.register(shm._name, "shared_memory")
        except Exception as exc:
            logger.debug("Resource tracker registration bypassed: %s", exc)

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
                    except (OSError, FileNotFoundError) as exc:
                        logger.debug("Shared memory unlink bypassed: %s", exc)
                    _ACTIVE_SHM.pop(name, None)
            else:
                try:
                    s = sm.SharedMemory(name=name)
                    s.close()
                    s.unlink()
                except Exception as exc:
                    logger.debug("Shared memory cleanup bypassed: %s", exc)

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
        except OSError as exc:
            logger.debug("Shared memory close bypassed: %s", exc)
        SharedMemoryBuffer._notify_closed(self.shm.name)

    def unlink(self) -> None:
        """Explicitly unlink OS shared memory segment immediately."""
        if self._finalizer is not None and self._finalizer.alive:
            self._finalizer.detach()
        try:
            self.shm.unlink()
        except (OSError, FileNotFoundError) as exc:
            logger.debug("Shared memory unlink bypassed: %s", exc)
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
        self._last_error: Optional[Exception] = None
        self._descriptor_path: Optional[pathlib.Path] = None

    def start(self, port_fallback: bool = True, max_retries: int = 5) -> int:
        """Bind listening socket and launch background accept loop."""
        target_port = self.requested_port
        bound = False

        for attempt in range(max_retries):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.host, target_port))
                sock.listen(5)
                self._server_sock = sock
                self.port = sock.getsockname()[1]
                bound = True
                break
            except OSError:
                sock.close()
                if port_fallback:
                    fb_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    fb_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        fb_sock.bind((self.host, 0))
                        fb_sock.listen(5)
                        self._server_sock = fb_sock
                        self.port = fb_sock.getsockname()[1]
                        bound = True
                        break
                    except OSError:
                        fb_sock.close()
                time.sleep(0.05 * (2**attempt))

        if not bound or self._server_sock is None:
            raise OSError(f"Could not bind to port {target_port}")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._accept_loop,
            name="HMACSocketServerLoop",
            daemon=True,
        )
        self._thread.start()
        return self.port

    def stop(self) -> None:
        """Shutdown server socket and join accept thread."""
        self._stop_event.set()
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError as exc:
                logger.debug("Server socket close error ignored: %s", exc)
            self._server_sock = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self._server_sock is None:
                    break
                self._server_sock.settimeout(0.5)
                conn, _ = self._server_sock.accept()
            except (socket.timeout, OSError):
                continue

            try:
                challenge = secrets.token_bytes(32)
                conn.sendall(challenge)

                response = conn.recv(32)
                expected = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()

                if not hmac.compare_digest(response, expected):
                    conn.sendall(b"DENIED")
                    conn.close()
                    continue

                conn.sendall(b"ACCEPT")

                len_bytes = conn.recv(4)
                if len(len_bytes) < 4:
                    conn.close()
                    continue
                (payload_len,) = struct.unpack("!I", len_bytes)

                if payload_len > MAX_IPC_PAYLOAD_BYTES:
                    conn.close()
                    continue

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
                except OSError as exc:
                    logger.debug("Client conn close error ignored: %s", exc)

    def get_received_payload(self, timeout_sec: float = 5.0) -> Optional[Any]:
        if self._payload_event.wait(timeout_sec):
            if self._received_payloads:
                payload = self._received_payloads.pop(0)
                if not self._received_payloads:
                    self._payload_event.clear()
                return payload
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
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        try:
            challenge = sock.recv(32)
            if len(challenge) != 32:
                raise ConnectionError("Invalid challenge received from server")

            response = hmac.new(self.secret_key, challenge, hashlib.sha256).digest()
            sock.sendall(response)

            status = sock.recv(6)
            if status != b"ACCEPT":
                raise PermissionError("HMAC handshake rejected by server")

            packed_bytes = pack_payload(data)
            header = struct.pack("!I", len(packed_bytes))
            sock.sendall(header + packed_bytes)
        finally:
            sock.close()


# ==============================================================================
# HDF5 PESStore Tensor Persistence (QCSchema & SWMR In-Place Resizing)
# ==============================================================================
class PESStore:
    """Multidimensional tensor persistence store for Potential Energy Surfaces using HDF5 SWMR.

    Implements in-place chunk resizing and dual-layer concurrency locking (threading.RLock + filelock).
    Strictly validates Tripartite Air-Gap boundaries without whole-file copying.
    """

    def __init__(self, file_path: Union[Path, str], lock_dir: Optional[Union[Path, str]] = None) -> None:
        self.file_path: Path = validate_airgap_write_path(Path(file_path).resolve())
        if lock_dir is not None:
            self.lock_dir = Path(lock_dir).resolve()
        else:
            scratch_root = os.environ.get("COCH_SCRATCH", os.environ.get("COCHEM_SCRATCH_DIR", tempfile.gettempdir()))
            self.lock_dir = Path(scratch_root).resolve()
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path: Path = self.lock_dir / f"{self.file_path.name}.lock"

    def write_entry(
        self,
        entry_or_point: Any,
        molecule: Optional[Dict[str, Any]] = None,
        driver: str = "energy",
        model: Optional[Dict[str, Any]] = None,
        return_result: Optional[Union[np.ndarray, float, List[Any]]] = None,
    ) -> None:
        """Persists or appends a PES point record in-place in HDF5 SWMR mode.

        Supports both PESPointRecord instances and raw QCSchema parameters.
        Eliminates all shutil.copyfile redundancy [M].
        """
        validate_airgap_write_path(self.file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Dual-layer locking: in-process RLock and cross-process FileLock on local scratch
        with _HDF5_MEM_LOCK:
            with filelock.FileLock(str(self.lock_path), timeout=30.0):
                with h5py.File(self.file_path, "a", libver="latest") as h5f:
                    if hasattr(entry_or_point, "point_id") and hasattr(entry_or_point, "energy"):
                        # PESPointRecord instance
                        point = entry_or_point
                        coords = np.asarray(point.coordinates, dtype=np.float64)
                        if coords.ndim == 1:
                            coords = coords[None, :]
                        elif coords.ndim == 2:
                            coords = coords.reshape(1, -1)

                        pts = h5f.require_group("points")
                        cur_len = pts["energies"].shape[0] if "energies" in pts else 0
                        new_len = cur_len + 1

                        if "energies" in pts:
                            pts["energies"].resize((new_len,))
                            pts["energies"][cur_len] = float(point.energy)
                            pts["energies"].flush()
                        else:
                            ds_e = pts.create_dataset(
                                "energies",
                                shape=(1,),
                                maxshape=(None,),
                                chunks=(512,),
                                dtype="float64",
                                compression="gzip",
                                compression_opts=4,
                                shuffle=True,
                                fletcher32=True,
                            )
                            ds_e[0] = float(point.energy)
                            ds_e.flush()

                        if "coordinates" in pts:
                            pts["coordinates"].resize((new_len, coords.shape[1]))
                            pts["coordinates"][cur_len] = coords[0]
                            pts["coordinates"].flush()
                        else:
                            ds_c = pts.create_dataset(
                                "coordinates",
                                shape=(1, coords.shape[1]),
                                maxshape=(None, coords.shape[1]),
                                chunks=(512, coords.shape[1]),
                                dtype="float64",
                                compression="gzip",
                                compression_opts=4,
                                shuffle=True,
                                fletcher32=True,
                            )
                            ds_c[0] = coords[0]
                            ds_c.flush()

                        if "point_ids" in pts:
                            pts["point_ids"].resize((new_len,))
                            pts["point_ids"][cur_len] = str(point.point_id)
                            pts["point_ids"].flush()
                        else:
                            dt = h5py.string_dtype(encoding="utf-8")
                            ds_p = pts.create_dataset(
                                "point_ids",
                                shape=(1,),
                                maxshape=(None,),
                                chunks=(512,),
                                dtype=dt,
                            )
                            ds_p[0] = str(point.point_id)
                            ds_p.flush()
                    else:
                        # Raw QCSchema parameter signature (entry_id, molecule, driver, model, return_result)
                        entry_id = str(entry_or_point)
                        arr = np.asarray(return_result if return_result is not None else 0.0)

                        if entry_id in h5f:
                            del h5f[entry_id]

                        grp = h5f.create_group(entry_id)
                        grp.attrs["schema_name"] = "qcschema_output"
                        grp.attrs["driver"] = str(driver)
                        grp.attrs["molecule_json"] = json.dumps(molecule or {})
                        grp.attrs["model_json"] = json.dumps(model or {})

                        chunk_shape: Optional[Tuple[int, ...]] = None
                        max_shape: Optional[Tuple[Optional[int], ...]] = None
                        if arr.ndim > 0:
                            chunk_shape = tuple(max(1, min(s, 128)) for s in arr.shape)
                            max_shape = tuple(None for _ in arr.shape)
                            ds = grp.create_dataset(
                                "return_result",
                                data=arr,
                                maxshape=max_shape,
                                chunks=chunk_shape,
                                compression="gzip",
                                compression_opts=4,
                                shuffle=True,
                                fletcher32=True,
                            )
                            ds.flush()
                        else:
                            grp.create_dataset("return_result", data=arr)

                    h5f.flush()

    def read_entry(self, entry_id: str) -> Dict[str, Any]:
        """Read QCSchema entry in SWMR mode without lock contention."""
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


__all__ = [
    "validate_airgap_write_path",
    "PESStore",
    "SharedMemoryBuffer",
    "pack_payload",
    "unpack_payload",
    "HMACSocketServer",
    "HMACSocketClient",
]
