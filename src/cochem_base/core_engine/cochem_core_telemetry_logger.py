#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
CoChem-CORE: Stage 4.0 - Telemetry, Stability, & Provenance Logger
The Black Box of the CoChem ecosystem.

Implements:
- Rotating JSON-LD provenance stream handler (Logs/cochem_telemetry_stream.jsonl)
- Global sys.excepthook interception with structured crash diagnostics & JSON-LD provenance
- Real-time psutil RAM RSS / CPU load & pynvml NVIDIA GPU VRAM telemetry on crash
- Emergency .flush() and .close() on all open HDF5 pointers during hard crashes
- Strict zero-SWMR enforcement (swmr=True prohibited under all circumstances)
- Original hook (sys.__excepthook__) chaining preserving Jupyter Notebook visual tracebacks
- Plaintext RotatingFileHandler with strict 5 MB file size limit and 3 rolling backups
- Exit Code 139 / Segfault / Access Violation recognition with 256-byte stderr hex-dumping
- Cryptographic HMAC-SHA256 signing of provenance blocks to prevent log spoofing
- Secure IPC streaming (ZeroMQ PUB/SUB and native IPC sockets/pipes)
- Numerical instability regex traps (NaN, Infinity, overlap near-linear dependence, wavefunction saddle point)
- SCF convergence oscillation (ping-pong) preemption
- Read-only immutability locking
"""

from __future__ import annotations

import atexit
import contextlib
import gc
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import platform
import re
import secrets
import socket
import stat
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

from cochem_base.config_loader import get_artifact_dir, get_scratch_dir

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-TelemetryLogger")

# Comprehensive cross-platform segmentation fault, abort, access violation, and stack overflow codes
CRITICAL_SEGFAULT_EXIT_CODES = {
    139, 134, 135, 136,             # POSIX SIGSEGV, SIGABRT, SIGBUS, SIGFPE
    -11, -6, -7, -8,                 # Subprocess negative signals
    0xC0000005, 3221225477, -1073741819,  # Windows STATUS_ACCESS_VIOLATION (unsigned & signed)
    0xC00000FD, 3221225725, -1073741571,  # Windows STATUS_STACK_OVERFLOW
    0xC000001D, 3221225501, -1073741795,  # Windows STATUS_ILLEGAL_INSTRUCTION
    0xC000002E, 3221225518, -1073741778,  # Windows STATUS_DATATYPE_MISALIGNMENT
}

DEFAULT_STREAM_FILENAME = "cochem_telemetry_stream.jsonl"
DEFAULT_MAX_STREAM_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

DEFAULT_ROTATING_LOG_FILENAME = "cochem_execution.log"
DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024  # Strict 5 MB limit
DEFAULT_LOG_BACKUP_COUNT = 3             # Maximum 3 rolling backups (e.g. .log, .log.1, .log.2, .log.3)

# Module-level session secret key for cryptographic log signing
_MODULE_SESSION_KEY: bytes = secrets.token_bytes(32)


def get_default_secret_key() -> bytes:
    """Retrieves the active HMAC secret key from environment or uses module session secret."""
    env_key = os.environ.get("COCHEM_TELEMETRY_SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")
    return _MODULE_SESSION_KEY


def resolve_telemetry_log_dir(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves the telemetry log directory.
    Hierarchy:
    1. Explicit custom_path parameter
    2. COCHEM_SCRATCH_DIR / COCHEM_SCRATCH environment variable -> $COCHEM_SCRATCH_DIR/CoChem_Artifacts/Logs
    3. get_scratch_dir() / "CoChem_Artifacts" / "Logs"
    4. Fallback: get_artifact_dir() / "Logs"
    """
    if custom_path is not None:
        p = Path(custom_path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    env_scratch = os.environ.get("COCHEM_SCRATCH_DIR") or os.environ.get("COCHEM_SCRATCH")
    if env_scratch:
        p = (Path(env_scratch).resolve() / "CoChem_Artifacts" / "Logs").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    try:
        p = (get_scratch_dir() / "CoChem_Artifacts" / "Logs").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass

    try:
        p = (get_artifact_dir() / "Logs").resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass

    fallback = (Path.home() / "CoChem_Artifacts" / "Logs").resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def capture_crash_telemetry_metrics() -> Dict[str, Any]:
    """
    Captures process RSS RAM usage, CPU load (via psutil), and GPU VRAM footprint (via pynvml)
    at the exact millisecond of failure.
    Gracefully handles environments without NVIDIA GPU or missing drivers.
    """
    metrics: Dict[str, Any] = {
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "timestamp_epoch_ms": int(time.time() * 1000),
    }

    # 1. Process CPU and RAM Telemetry via psutil
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        metrics["ram_rss_bytes"] = mem_info.rss
        metrics["ram_rss_mb"] = round(mem_info.rss / (1024 * 1024), 2)
        metrics["ram_vms_bytes"] = mem_info.vms
        metrics["ram_vms_mb"] = round(mem_info.vms / (1024 * 1024), 2)
        metrics["process_cpu_percent"] = proc.cpu_percent(interval=None)
        metrics["system_cpu_percent"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        metrics["system_ram_total_bytes"] = vm.total
        metrics["system_ram_used_bytes"] = vm.used
        metrics["system_ram_percent"] = vm.percent
    except Exception as psutil_err:
        metrics["psutil_error"] = str(psutil_err)

    # 2. NVIDIA GPU VRAM Telemetry via pynvml
    gpu_metrics: List[Dict[str, Any]] = []
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            metrics["nvidia_gpu_count"] = device_count
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util = util.gpu
                    mem_util = util.memory
                except Exception:
                    gpu_util = 0
                    mem_util = 0
                gpu_metrics.append({
                    "gpu_index": i,
                    "gpu_name": name,
                    "vram_used_bytes": mem_info.used,
                    "vram_total_bytes": mem_info.total,
                    "vram_free_bytes": mem_info.free,
                    "vram_used_mb": round(mem_info.used / (1024 * 1024), 2),
                    "vram_total_mb": round(mem_info.total / (1024 * 1024), 2),
                    "vram_utilization_percent": gpu_util,
                    "memory_utilization_percent": mem_util,
                })
            metrics["gpus"] = gpu_metrics
            metrics["pynvml_status"] = "ACTIVE"
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
    except Exception as nvml_err:
        metrics["nvidia_gpu_count"] = 0
        metrics["gpus"] = []
        metrics["pynvml_status"] = f"Unavailable/Inactive: {nvml_err}"

    return metrics


def force_flush_and_close_hdf5_pointers() -> int:
    """
    Forces an immediate .flush() and .close() on any open HDF5 file pointers
    to prevent file corruption during hard crashes.
    Returns the count of HDF5 pointers successfully closed.
    """
    closed_count = 0
    h5py_mod = sys.modules.get("h5py")
    if h5py_mod is not None:
        try:
            for obj in gc.get_objects():
                try:
                    if isinstance(obj, getattr(h5py_mod, "File", ())):
                        if getattr(obj, "id", None) is not None and getattr(obj.id, "valid", False):
                            filename_str = str(getattr(obj, "filename", obj))
                            try:
                                obj.flush()
                            except Exception as flush_err:
                                logger.debug(f"Failed to flush open HDF5 pointer {filename_str}: {flush_err}")
                            try:
                                obj.close()
                                closed_count += 1
                                logger.warning(f"Enforced emergency crash closure on open HDF5 file: {filename_str}")
                            except Exception as close_err:
                                logger.error(f"Failed to close open HDF5 pointer {filename_str}: {close_err}")
                except Exception:
                    continue
        except Exception as exc:
            logger.error(f"Error inspecting open HDF5 pointers during crash: {exc}")
    return closed_count


@contextlib.contextmanager
def safe_h5py_open(
    name: Union[str, Path, os.PathLike[Any]],
    mode: str = "r",
    driver: Optional[str] = None,
    libver: Optional[str] = None,
    userblock_size: Optional[int] = None,
    swmr: bool = False,
    **kwargs: Any,
) -> Iterator[Any]:
    """
    Context manager for HDF5 files enforcing strict closure on exit and crash.
    Mandates zero SWMR usage: raises ValueError if swmr=True under any circumstances.
    """
    if swmr or kwargs.get("swmr", False):
        raise ValueError(
            "CRITICAL METHOD MATRIX VIOLATION: swmr=True is strictly prohibited for HDF5 in CoChem under any circumstances. "
            "Use SQLite WAL or ZeroMQ for concurrent metadata state instead."
        )
    import h5py
    f = h5py.File(str(name), mode=mode, driver=driver, libver=libver, userblock_size=userblock_size, swmr=False, **kwargs)
    try:
        yield f
    finally:
        if getattr(f, "id", None) is not None and getattr(f.id, "valid", False):
            try:
                f.flush()
            finally:
                f.close()


def get_plaintext_rotating_handler(
    log_dir: Optional[Union[str, Path]] = None,
    filename: str = DEFAULT_ROTATING_LOG_FILENAME,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> logging.handlers.RotatingFileHandler:
    """
    Creates and returns a plaintext RotatingFileHandler configured with a strict 5 MB
    file size limit and a maximum of 3 rolling backups.
    """
    resolved_dir = resolve_telemetry_log_dir(log_dir)
    target_file = resolved_dir / filename
    handler = logging.handlers.RotatingFileHandler(
        filename=str(target_file),
        mode="a",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=False,
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(process)d:%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


def setup_cochem_rotating_logger(
    log_dir: Optional[Union[str, Path]] = None,
    filename: str = DEFAULT_ROTATING_LOG_FILENAME,
    max_bytes: int = DEFAULT_MAX_LOG_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
    logger_name: str = "CoChem",
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Attaches the 5 MB / 3 backup plaintext RotatingFileHandler to the designated logger.
    """
    target_logger = logging.getLogger(logger_name)
    target_logger.setLevel(level)
    handler = get_plaintext_rotating_handler(
        log_dir=log_dir,
        filename=filename,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    # Avoid duplicate handlers for the same target log file
    for existing_h in list(target_logger.handlers):
        if isinstance(existing_h, logging.handlers.RotatingFileHandler):
            if existing_h.baseFilename == handler.baseFilename:
                target_logger.removeHandler(existing_h)
    target_logger.addHandler(handler)
    return target_logger



def compute_provenance_digest(data: Union[Dict[str, Any], str, bytes]) -> str:
    """Computes a deterministic SHA-256 cryptographic digest of a payload."""
    if isinstance(data, dict):
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        raw_bytes = canonical.encode("utf-8")
    elif isinstance(data, str):
        raw_bytes = data.encode("utf-8")
    else:
        raw_bytes = data
    return hashlib.sha256(raw_bytes).hexdigest()


def sign_provenance_block(
    data: Dict[str, Any],
    secret_key: Optional[Union[str, bytes]] = None,
) -> Dict[str, Any]:
    """
    Cryptographically signs a JSON-LD provenance block using HMAC-SHA256.
    Ensures log tampering and spoofing are physically detectable.
    """
    key_bytes = secret_key.encode("utf-8") if isinstance(secret_key, str) else (secret_key or get_default_secret_key())
    
    # Create canonical representation without existing signature fields
    block_copy = dict(data)
    block_copy.pop("signature", None)
    block_copy["signature_algorithm"] = "HMAC-SHA256"
    if "signature_timestamp" not in block_copy:
        block_copy["signature_timestamp"] = datetime.now(timezone.utc).isoformat()
    
    canonical_json = json.dumps(block_copy, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    sig_digest = hmac.new(key_bytes, canonical_json.encode("utf-8"), hashlib.sha256).hexdigest()
    block_copy["signature"] = sig_digest
    return block_copy


def verify_provenance_signature(
    signed_data: Dict[str, Any],
    secret_key: Optional[Union[str, bytes]] = None,
) -> bool:
    """
    Verifies the cryptographic HMAC-SHA256 signature of a JSON-LD provenance block.
    Returns True if valid, False if tampered, corrupted, or unsigned.
    """
    if not isinstance(signed_data, dict) or "signature" not in signed_data:
        return False
    
    signature = signed_data["signature"]
    if not isinstance(signature, str):
        return False
    
    key_bytes = secret_key.encode("utf-8") if isinstance(secret_key, str) else (secret_key or get_default_secret_key())
    
    # Reconstruct canonical body without signature field
    payload = {k: v for k, v in signed_data.items() if k != "signature"}
    canonical_json = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    expected_sig = hmac.new(key_bytes, canonical_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_sig)


class RotatingJsonlSink:
    """
    Thread-safe rotating JSONL sink streaming structured JSON-LD provenance events.
    Automatically rotates log files when file size crosses max_bytes threshold.
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        max_bytes: int = DEFAULT_MAX_STREAM_BYTES,
        backup_count: int = DEFAULT_BACKUP_COUNT,
        secret_key: Optional[Union[str, bytes]] = None,
    ) -> None:
        self.file_path = Path(file_path).resolve()
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.secret_key = secret_key
        self._lock = threading.Lock()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.file_path, "a", encoding="utf-8")

    def write_entry(self, record: Dict[str, Any], sign: bool = True) -> Dict[str, Any]:
        """Writes a single JSON-LD structured entry to the stream with rotation check."""
        with self._lock:
            if sign:
                final_record = sign_provenance_block(record, self.secret_key)
            else:
                final_record = record

            encoded = json.dumps(final_record, ensure_ascii=False) + "\n"
            encoded_bytes_len = len(encoded.encode("utf-8"))

            if self.file_path.exists():
                try:
                    current_size = self.file_path.stat().st_size
                    if current_size + encoded_bytes_len >= self.max_bytes:
                        self.rotate()
                except OSError:
                    pass

            self._fp.write(encoded)
            self._fp.flush()
            return final_record

    def rotate(self) -> None:
        """Performs physical file rotation: file.jsonl -> file.jsonl.1 -> file.jsonl.N."""
        if self._fp and not self._fp.closed:
            self._fp.flush()
            self._fp.close()

        for i in range(self.backup_count - 1, 0, -1):
            sfn = self.file_path.parent / f"{self.file_path.name}.{i}"
            dfn = self.file_path.parent / f"{self.file_path.name}.{i + 1}"
            if sfn.exists():
                if dfn.exists():
                    try:
                        os.chmod(str(dfn), 0o666)
                        dfn.unlink()
                    except OSError:
                        pass
                try:
                    os.chmod(str(sfn), 0o666)
                    sfn.rename(dfn)
                except OSError:
                    pass

        dfn1 = self.file_path.parent / f"{self.file_path.name}.1"
        if self.file_path.exists():
            if dfn1.exists():
                try:
                    os.chmod(str(dfn1), 0o666)
                    dfn1.unlink()
                except OSError:
                    pass
            try:
                os.chmod(str(self.file_path), 0o666)
                self.file_path.rename(dfn1)
            except OSError:
                pass

        self._fp = open(self.file_path, "a", encoding="utf-8")

    def flush(self) -> None:
        """Flushes underlying stream buffer."""
        with self._lock:
            if self._fp and not self._fp.closed:
                self._fp.flush()

    def close(self) -> None:
        """Closes stream file descriptor."""
        with self._lock:
            if self._fp and not self._fp.closed:
                self._fp.flush()
                self._fp.close()


class TelemetryIPCStreamer:
    """
    Secure IPC Streamer for broadcasting structured telemetry events to external listeners.
    Supports ZeroMQ PUB sockets and cross-platform native TCP / datagram IPC sockets.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        transport: str = "auto",
        secret_key: Optional[Union[str, bytes]] = None,
    ) -> None:
        self.transport_mode = transport.lower()
        self.endpoint = endpoint
        self.secret_key = secret_key
        self._lock = threading.Lock()
        self._active = False
        
        self._zmq_context: Optional[Any] = None
        self._zmq_socket: Optional[Any] = None
        
        self._socket_server: Optional[socket.socket] = None
        self._target_port: Optional[int] = None
        self._bound_endpoint: Optional[str] = None

    def start(self) -> str:
        """Initializes and binds the secure IPC streaming channel."""
        with self._lock:
            if self._active and self._bound_endpoint:
                return self._bound_endpoint

            use_zmq = (self.transport_mode in ("zmq", "zeromq") or (self.transport_mode == "auto" and HAS_ZMQ))
            if use_zmq and HAS_ZMQ:
                try:
                    self._zmq_context = zmq.Context()
                    self._zmq_socket = self._zmq_context.socket(zmq.PUB)
                    bind_target = self.endpoint or "tcp://127.0.0.1:0"
                    if ":0" in bind_target:
                        port = self._zmq_socket.bind_to_random_port("tcp://127.0.0.1")
                        self._bound_endpoint = f"tcp://127.0.0.1:{port}"
                    else:
                        self._zmq_socket.bind(bind_target)
                        self._bound_endpoint = bind_target
                    self.transport_mode = "zmq"
                    self._active = True
                    logger.info(f"Telemetry ZeroMQ IPC Streamer bound to {self._bound_endpoint}")
                    return self._bound_endpoint
                except Exception as e:
                    logger.warning(f"Failed to initialize ZeroMQ streamer: {e}. Falling back to native socket.")

            # Native Socket Transport Fallback
            target_port = 0
            if self.endpoint and ":" in self.endpoint:
                try:
                    target_port = int(self.endpoint.split(":")[-1].replace("/", ""))
                except ValueError:
                    target_port = 0

            if target_port == 0:
                # Pick an available port for the channel
                temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                temp_sock.bind(("127.0.0.1", 0))
                target_port = temp_sock.getsockname()[1]
                temp_sock.close()

            self._target_port = target_port
            self._socket_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket_server.bind(("127.0.0.1", 0))  # Sender binds to ephemeral port
            self._bound_endpoint = f"udp://127.0.0.1:{target_port}"
            self.transport_mode = "socket"
            self._active = True
            logger.info(f"Telemetry Native IPC Streamer bound to channel {self._bound_endpoint}")
            return self._bound_endpoint

    def publish_event(self, event_type: str, payload: Dict[str, Any], sign: bool = True) -> bool:
        """Broadcasts a telemetry event envelope over the active IPC channel."""
        with self._lock:
            if not self._active:
                return False

            envelope = {
                "@context": "https://w3id.org/ro/qcschema",
                "@type": "TelemetryEventEnvelope",
                "event_type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
            if sign:
                envelope = sign_provenance_block(envelope, self.secret_key)

            encoded_json = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

            try:
                if self.transport_mode == "zmq" and self._zmq_socket is not None:
                    self._zmq_socket.send_multipart([
                        event_type.encode("utf-8"),
                        encoded_json
                    ], flags=getattr(zmq, "NOBLOCK", 0))
                    return True
                elif self._socket_server is not None and self._target_port:
                    self._socket_server.sendto(encoded_json, ("127.0.0.1", self._target_port))
                    return True
            except Exception as exc:
                logger.debug(f"IPC publish error: {exc}")
                return False
            return False

    def close(self) -> None:
        """Shuts down and frees IPC streaming resources."""
        with self._lock:
            self._active = False
            if self._zmq_socket is not None:
                try:
                    self._zmq_socket.close(linger=0)
                except Exception:
                    pass
                self._zmq_socket = None
            if self._zmq_context is not None:
                try:
                    self._zmq_context.term()
                except Exception:
                    pass
                self._zmq_context = None
            if self._socket_server is not None:
                try:
                    self._socket_server.close()
                except Exception:
                    pass
                self._socket_server = None


class TelemetryIPCListener:
    """
    Secure IPC Listener for receiving and cryptographically verifying telemetry events.
    Supports ZeroMQ SUB sockets and native datagram IPC listeners.
    """

    def __init__(
        self,
        endpoint: str,
        transport: str = "auto",
        secret_key: Optional[Union[str, bytes]] = None,
    ) -> None:
        self.endpoint = endpoint
        self.transport_mode = transport.lower()
        self.secret_key = secret_key
        self._lock = threading.Lock()
        self._active = False
        
        self._zmq_context: Optional[Any] = None
        self._zmq_socket: Optional[Any] = None
        self._socket: Optional[socket.socket] = None

    def start(self) -> None:
        """Connects and starts listening on the IPC streaming channel."""
        with self._lock:
            if self._active:
                return

            use_zmq = (self.transport_mode in ("zmq", "zeromq") or (self.transport_mode == "auto" and "tcp://" in self.endpoint and HAS_ZMQ))
            if use_zmq and HAS_ZMQ:
                try:
                    self._zmq_context = zmq.Context()
                    self._zmq_socket = self._zmq_context.socket(zmq.SUB)
                    self._zmq_socket.connect(self.endpoint)
                    self._zmq_socket.setsockopt(zmq.SUBSCRIBE, b"")
                    self.transport_mode = "zmq"
                    self._active = True
                    return
                except Exception as e:
                    logger.warning(f"Failed to connect ZeroMQ listener: {e}")

            if self.endpoint.startswith("udp://") or ":" in self.endpoint:
                port_str = self.endpoint.split(":")[-1].replace("/", "")
                port = int(port_str)
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.bind(("127.0.0.1", port))
                self._socket.settimeout(0.5)
                self.transport_mode = "socket"
                self._active = True

    def recv_event(self, timeout: Optional[float] = 1.0, verify_signature: bool = True) -> Optional[Dict[str, Any]]:
        """Receives a single event and verifies its cryptographic provenance signature."""
        if not self._active:
            self.start()

        if self.transport_mode == "zmq" and self._zmq_socket is not None:
            poller = zmq.Poller()
            poller.register(self._zmq_socket, zmq.POLLIN)
            timeout_ms = int(timeout * 1000) if timeout is not None else 1000
            socks = dict(poller.poll(timeout_ms))
            if self._zmq_socket in socks and socks[self._zmq_socket] == zmq.POLLIN:
                parts = self._zmq_socket.recv_multipart()
                if len(parts) >= 2:
                    raw_data = parts[1].decode("utf-8")
                else:
                    raw_data = parts[0].decode("utf-8")
                data = json.loads(raw_data)
                if not isinstance(data, dict):
                    return None
                if verify_signature and not verify_provenance_signature(data, self.secret_key):
                    logger.warning("Spoofed or corrupted telemetry event received over IPC! Signature verification failed.")
                    return None
                return data
            return None

        if self._socket is not None:
            try:
                self._socket.settimeout(timeout or 1.0)
                raw_bytes, _ = self._socket.recvfrom(65536)
                data = json.loads(raw_bytes.decode("utf-8"))
                if not isinstance(data, dict):
                    return None
                if verify_signature and not verify_provenance_signature(data, self.secret_key):
                    logger.warning("Spoofed or corrupted telemetry event received over IPC! Signature verification failed.")
                    return None
                return data
            except (socket.timeout, OSError):
                return None

        return None

    def close(self) -> None:
        """Closes IPC listener resources."""
        with self._lock:
            self._active = False
            if self._zmq_socket is not None:
                try:
                    self._zmq_socket.close(linger=0)
                except Exception:
                    pass
                self._zmq_socket = None
            if self._zmq_context is not None:
                try:
                    self._zmq_context.term()
                except Exception:
                    pass
                self._zmq_context = None
            if self._socket is not None:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None


# Global excepthook state
_GLOBAL_ORIGINAL_EXCEPTHOOK: Optional[Callable[..., Any]] = None
_GLOBAL_CHAIN_EXCEPTHOOK: bool = True
_GLOBAL_TELEMETRY_LOGGER: Optional[TelemetryLogger] = None
_GLOBAL_HOOK_LOCK = threading.Lock()


def _cochem_excepthook_handler(exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
    """
    Internal global excepthook handler intercepting uncaught Python crashes:
    1. Forcibly flushes and closes any open HDF5 pointers to guarantee zero file corruption.
    2. Captures psutil RAM/CPU and pynvml VRAM metrics at the exact millisecond of failure.
    3. Records cryptographically signed JSON-LD crash diagnostics to the telemetry stream.
    4. Invokes the original hook (sys.__excepthook__) to preserve visual tracebacks for Jupyter Notebook users.
    """
    global _GLOBAL_TELEMETRY_LOGGER, _GLOBAL_ORIGINAL_EXCEPTHOOK, _GLOBAL_CHAIN_EXCEPTHOOK
    
    # 1. Force flush and close open HDF5 file pointers
    try:
        force_flush_and_close_hdf5_pointers()
    except Exception as h5_err:
        logger.error(f"Error during emergency HDF5 closure in excepthook: {h5_err}")

    # 2. Record crash diagnostics with full hardware telemetry
    try:
        active_logger = _GLOBAL_TELEMETRY_LOGGER
        if active_logger is None:
            active_logger = TelemetryLogger()

        active_logger.record_crash_diagnostics(exc_type, exc_value, exc_traceback)
    except Exception as hook_err:
        logger.error(f"Error executing telemetry crash hook: {hook_err}")

    # 3. Chain to original excepthook or sys.__excepthook__ to preserve visual tracebacks for Jupyter Notebook users
    if _GLOBAL_CHAIN_EXCEPTHOOK:
        if _GLOBAL_ORIGINAL_EXCEPTHOOK and callable(_GLOBAL_ORIGINAL_EXCEPTHOOK):
            _GLOBAL_ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_traceback)
        elif hasattr(sys, "__excepthook__") and sys.__excepthook__ is not None:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)


def install_global_excepthook(
    logger_instance: Optional[TelemetryLogger] = None,
    chain: bool = True,
) -> None:
    """
    Globally intercepts sys.excepthook to trap fatal unhandled Python crashes,
    streaming structured diagnostics & JSON-LD provenance to the telemetry pipeline.
    """
    global _GLOBAL_ORIGINAL_EXCEPTHOOK, _GLOBAL_CHAIN_EXCEPTHOOK, _GLOBAL_TELEMETRY_LOGGER
    with _GLOBAL_HOOK_LOCK:
        _GLOBAL_TELEMETRY_LOGGER = logger_instance
        _GLOBAL_CHAIN_EXCEPTHOOK = chain
        if sys.excepthook != _cochem_excepthook_handler:
            _GLOBAL_ORIGINAL_EXCEPTHOOK = sys.excepthook
            sys.excepthook = _cochem_excepthook_handler
            logger.info("Global Telemetry crash excepthook armed.")


def uninstall_global_excepthook() -> None:
    """Restores the original system sys.excepthook handler."""
    global _GLOBAL_ORIGINAL_EXCEPTHOOK, _GLOBAL_CHAIN_EXCEPTHOOK, _GLOBAL_TELEMETRY_LOGGER
    with _GLOBAL_HOOK_LOCK:
        if sys.excepthook == _cochem_excepthook_handler:
            if _GLOBAL_ORIGINAL_EXCEPTHOOK is not None:
                sys.excepthook = _GLOBAL_ORIGINAL_EXCEPTHOOK
            elif hasattr(sys, "__excepthook__"):
                sys.excepthook = sys.__excepthook__
        _GLOBAL_ORIGINAL_EXCEPTHOOK = None
        _GLOBAL_CHAIN_EXCEPTHOOK = True
        _GLOBAL_TELEMETRY_LOGGER = None
        logger.info("Global Telemetry crash excepthook unarmed.")


@contextlib.contextmanager
def trap_unhandled_exceptions(
    logger_instance: Optional[TelemetryLogger] = None,
    chain: bool = False,
) -> Iterator[None]:
    """Context manager scoping sys.excepthook crash trapping within a code block."""
    install_global_excepthook(logger_instance=logger_instance, chain=chain)
    try:
        yield
    finally:
        uninstall_global_excepthook()


class TelemetryLogger:
    """
    CoChem-CORE Telemetry, Stability, & Provenance Logger (The Black Box).
    Features:
    - Rotating JSON-LD provenance log handler ($COCHEM_SCRATCH_DIR/CoChem_Artifacts/Logs/cochem_telemetry_stream.jsonl)
    - Plaintext RotatingFileHandler with strict 5 MB file size limit and 3 backups (cochem_execution.log)
    - Global sys.excepthook interception & structured crash diagnostics (psutil RSS RAM/CPU + pynvml GPU VRAM)
    - Emergency HDF5 pointer flushing and closure on hard crash with strict zero-SWMR mandate
    - Cross-platform Exit Code 139 / Access Violation 256-byte stderr hex-dumps
    - Cryptographic HMAC-SHA256 signing preventing log tampering
    - Real-time numerical instability regex traps (NaN, Infinity, overlap, saddle points)
    - SCF oscillation (ping-pong) preemption
    - Read-only immutability file locking
    """

    def __init__(
        self,
        log_dir: Optional[Union[str, Path]] = None,
        verbosity: str = "info",
        secret_key: Optional[Union[str, bytes]] = None,
        enable_stream: bool = True,
        stream_file: Optional[str] = DEFAULT_STREAM_FILENAME,
        max_stream_bytes: int = DEFAULT_MAX_STREAM_BYTES,
        stream_backup_count: int = DEFAULT_BACKUP_COUNT,
        enable_rotating_handler: bool = True,
        rotating_log_filename: str = DEFAULT_ROTATING_LOG_FILENAME,
        max_rotating_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
        rotating_log_backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
    ) -> None:
        self.log_dir = resolve_telemetry_log_dir(log_dir)
        self.verbosity = verbosity.lower()
        self.secret_key = secret_key

        self._lock = threading.Lock()
        self.warnings_count = 0
        self.errors_count = 0
        self._trap_events: List[Dict[str, Any]] = []

        # Regex Traps for Numerical Instability (strictly word bounded to avoid matching 'Infrared')
        self.nan_trap = re.compile(r'\b(NaN|Infinity|-?Inf)\b', re.IGNORECASE)
        self.overlap_trap = re.compile(r'(eigenvalue.*?<\s*1\.?0*e-0?[6-9]|linear dependence)', re.IGNORECASE)
        self.saddle_trap = re.compile(r'(internal instability|symmetry breaking|saddle point)', re.IGNORECASE)

        # Extract delta E values to catch ping-pong convergence failure
        self.delta_e_pattern = re.compile(r'dE\s*=\s*([-+]?\d*\.\d+[eE]?[-+]?\d*)')
        self.scf_history: deque[float] = deque(maxlen=5)

        # Rotating JSONL provenance stream sink ($COCHEM_SCRATCH_DIR/CoChem_Artifacts/Logs/cochem_telemetry_stream.jsonl)
        self.stream_path = (self.log_dir / (stream_file or DEFAULT_STREAM_FILENAME)).resolve()
        if enable_stream:
            self.sink: Optional[RotatingJsonlSink] = RotatingJsonlSink(
                file_path=self.stream_path,
                max_bytes=max_stream_bytes,
                backup_count=stream_backup_count,
                secret_key=self.secret_key,
            )
        else:
            self.sink = None

        # Plaintext RotatingFileHandler (strict 5 MB limit, max 3 rolling backups)
        self.rotating_log_path = (self.log_dir / rotating_log_filename).resolve()
        if enable_rotating_handler:
            self.rotating_handler: Optional[logging.handlers.RotatingFileHandler] = get_plaintext_rotating_handler(
                log_dir=self.log_dir,
                filename=rotating_log_filename,
                max_bytes=max_rotating_log_bytes,
                backup_count=rotating_log_backup_count,
            )
            # Attach handler to module logger
            if not any(
                isinstance(h, logging.handlers.RotatingFileHandler) and getattr(h, "baseFilename", "") == str(self.rotating_log_path)
                for h in logger.handlers
            ):
                logger.addHandler(self.rotating_handler)
        else:
            self.rotating_handler = None

        # Secure IPC Streamer
        self.ipc_streamer: Optional[TelemetryIPCStreamer] = None

    def __enter__(self) -> TelemetryLogger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def is_clean(self) -> bool:
        """Returns True if zero errors have been triggered."""
        with self._lock:
            return self.errors_count == 0

    def get_trap_events(self) -> List[Dict[str, Any]]:
        """Returns recorded trap events."""
        with self._lock:
            return list(self._trap_events)

    def reset_history(self) -> None:
        """Resets counters and histories."""
        with self._lock:
            self.warnings_count = 0
            self.errors_count = 0
            self.scf_history.clear()
            self._trap_events.clear()

    def _get_hardware_provenance(self) -> Dict[str, Any]:
        """Captures static node identifiers for reproducibility."""
        logical_cores = os.cpu_count() or 1
        return {
            "node_hostname": platform.node(),
            "kernel_version": platform.release(),
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "logical_cpu_cores": logical_cores,
        }

    def start_ipc_stream(self, endpoint: Optional[str] = None, transport: str = "auto") -> Optional[str]:
        """Initializes and activates the secure IPC telemetry streaming channel."""
        with self._lock:
            if self.ipc_streamer is None:
                self.ipc_streamer = TelemetryIPCStreamer(
                    endpoint=endpoint,
                    transport=transport,
                    secret_key=self.secret_key,
                )
            return self.ipc_streamer.start()

    def stop_ipc_stream(self) -> None:
        """Stops and closes the IPC streaming channel."""
        with self._lock:
            if self.ipc_streamer is not None:
                self.ipc_streamer.close()
                self.ipc_streamer = None

    def emit_telemetry_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        sign: bool = True,
    ) -> Dict[str, Any]:
        """
        Emits a structured JSON-LD event into the rotating telemetry stream
        and broadcasts over secure IPC if armed.
        """
        entry: Dict[str, Any] = {
            "@context": "https://w3id.org/ro/qcschema",
            "@type": "ComputationalJobTelemetry",
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provenance": self._get_hardware_provenance(),
            **payload,
        }

        if self.sink:
            final_entry = self.sink.write_entry(entry, sign=sign)
        elif sign:
            final_entry = sign_provenance_block(entry, self.secret_key)
        else:
            final_entry = entry

        if self.ipc_streamer:
            self.ipc_streamer.publish_event(event_type, final_entry, sign=False)

        return final_entry

    def record_crash_diagnostics(
        self,
        exc_type: Any,
        exc_value: Any,
        exc_traceback: Any,
        job_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Builds, cryptographically signs, and logs comprehensive JSON-LD crash diagnostics
        when a fatal unhandled Python crash or memory fault occurs.
        Captures process RSS RAM usage, CPU load, and NVIDIA GPU VRAM footprint.
        """
        with self._lock:
            self.errors_count += 1

            if exc_traceback is not None:
                tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            else:
                tb_lines = [f"{exc_type}: {exc_value}"]

            type_str = exc_type.__name__ if hasattr(exc_type, "__name__") else str(exc_type)
            msg_str = str(exc_value)

            # Capture live hardware metrics (RSS RAM, CPU, VRAM)
            hw_telemetry = capture_crash_telemetry_metrics()

            crash_payload: Dict[str, Any] = {
                "@context": "https://w3id.org/ro/qcschema",
                "@type": "FatalCrashDiagnostics",
                "event_type": "UNHANDLED_PYTHON_CRASH",
                "job_id": job_name or f"fatal_crash_pid_{os.getpid()}",
                "status": "CRASHED",
                "pid": os.getpid(),
                "thread_id": threading.get_ident(),
                "exception_type": type_str,
                "exception_message": msg_str,
                "traceback": tb_lines,
                "provenance": self._get_hardware_provenance(),
                "hardware_metrics": hw_telemetry,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._trap_events.append({
                "type": "FATAL_UNHANDLED_CRASH",
                "exception": type_str,
                "message": msg_str,
                "hardware_metrics": hw_telemetry,
            })

            logger.critical(
                f"FATAL UNHANDLED PYTHON CRASH: {type_str} - {msg_str} | "
                f"RAM RSS: {hw_telemetry.get('ram_rss_mb', 'N/A')} MB | "
                f"CPU: {hw_telemetry.get('process_cpu_percent', 'N/A')}% | "
                f"GPU Status: {hw_telemetry.get('pynvml_status', 'OK')}"
            )

            if self.sink:
                signed_crash = self.sink.write_entry(crash_payload, sign=True)
            else:
                signed_crash = sign_provenance_block(crash_payload, self.secret_key)

            if self.ipc_streamer:
                self.ipc_streamer.publish_event("FATAL_PYTHON_CRASH", signed_crash, sign=False)

            return signed_crash

    def install_excepthook(self, chain: bool = True) -> None:
        """Arms global sys.excepthook to route unhandled crashes through this logger instance."""
        install_global_excepthook(logger_instance=self, chain=chain)

    def uninstall_excepthook(self) -> None:
        """Restores original sys.excepthook."""
        uninstall_global_excepthook()

    def process_stream_chunk(self, chunk: str) -> bool:
        """
        Analyzes a streaming block of text.
        Returns False if a fatal numerical trap is sprung.
        """
        with self._lock:
            if self.nan_trap.search(chunk):
                logger.error("FATAL: NaN/Infinity detected in matrix operation. Triggering abort.")
                self.errors_count += 1
                self._trap_events.append({"type": "FATAL_NAN_INFINITY", "chunk": chunk})
                if self.sink:
                    self.sink.write_entry({
                        "@context": "https://w3id.org/ro/qcschema",
                        "@type": "NumericalTrapEvent",
                        "trap_type": "FATAL_NAN_INFINITY",
                        "chunk": chunk,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }, sign=True)
                return False

            if self.overlap_trap.search(chunk):
                logger.warning("WARNING: Near-linear dependence in basis set detected.")
                self.warnings_count += 1
                self._trap_events.append({"type": "WARN_NEAR_LINEAR_DEPENDENCE", "chunk": chunk})
                if self.sink:
                    self.sink.write_entry({
                        "@context": "https://w3id.org/ro/qcschema",
                        "@type": "NumericalTrapEvent",
                        "trap_type": "WARN_NEAR_LINEAR_DEPENDENCE",
                        "chunk": chunk,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }, sign=True)

            if self.saddle_trap.search(chunk):
                logger.warning("WARNING: Wavefunction instability detected. Check spin state.")
                self.warnings_count += 1
                self._trap_events.append({"type": "WARN_WAVEFUNCTION_INSTABILITY", "chunk": chunk})
                if self.sink:
                    self.sink.write_entry({
                        "@context": "https://w3id.org/ro/qcschema",
                        "@type": "NumericalTrapEvent",
                        "trap_type": "WARN_WAVEFUNCTION_INSTABILITY",
                        "chunk": chunk,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }, sign=True)

            # Ping-Pong Check
            match = self.delta_e_pattern.search(chunk)
            if match:
                try:
                    de = float(match.group(1))
                    self.scf_history.append(de)
                    if len(self.scf_history) == 5:
                        # Count sign reversals between consecutive iterations
                        sign_flips = sum(
                            1 for i in range(len(self.scf_history) - 1)
                            if self.scf_history[i] * self.scf_history[i + 1] < 0
                        )
                        abs_last = abs(self.scf_history[-1])
                        # Trigger abort if energy changes alternate sign (sign_flips >= 3) and magnitude remains un-converged (> 1e-3)
                        if sign_flips >= 3 and abs_last > 1e-3:
                            logger.error("FATAL: SCF Oscillation (Ping-Pong) detected. Triggering abort.")
                            self.errors_count += 1
                            self._trap_events.append({"type": "FATAL_SCF_OSCILLATION", "chunk": chunk})
                            if self.sink:
                                self.sink.write_entry({
                                    "@context": "https://w3id.org/ro/qcschema",
                                    "@type": "NumericalTrapEvent",
                                    "trap_type": "FATAL_SCF_OSCILLATION",
                                    "chunk": chunk,
                                    "history": list(self.scf_history),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }, sign=True)
                            return False
                except ValueError:
                    pass

            return True

    def _generate_json_ld_footer(self, job_name: str, exit_code: int, config_hash: str) -> str:
        """Generates the signed QCSchema compliant JSON-LD footer."""
        status = "SUCCESS" if exit_code == 0 else ("CRASHED" if exit_code in CRITICAL_SEGFAULT_EXIT_CODES else "FAILED")
        ld_block = {
            "@context": "https://w3id.org/ro/qcschema",
            "@type": "ComputationalJobTelemetry",
            "job_id": job_name,
            "provenance": self._get_hardware_provenance(),
            "execution_hash": config_hash,
            "exit_code": exit_code,
            "status": status,
            "timestamp_end": datetime.now(timezone.utc).isoformat(),
        }
        signed_ld = sign_provenance_block(ld_block, self.secret_key)
        return f"\n\n# --- COCHEM JSON-LD PROVENANCE FOOTER ---\n# {json.dumps(signed_ld, ensure_ascii=False)}\n"

    def aggregate_and_lock(
        self,
        job_name: str,
        stdout_history: Sequence[str],
        stderr_history: Sequence[str],
        exit_code: int,
        active_hash: str,
    ) -> str:
        """
        Assembles the final log, performs 256-byte hex dumping if a segfault occurred,
        appends the cryptographically signed JSON-LD footer, and locks the file as Read-Only.
        """
        log_path = self.log_dir / f"{job_name}_telemetry.log"
        if log_path.exists():
            try:
                os.chmod(str(log_path), stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"--- CoChem-CORE Telemetry Trace for {job_name} ---\n")
            f.write(f"Exit Code: {exit_code}\n\n")

            for line in stdout_history:
                f.write(line + "\n")

            if exit_code in CRITICAL_SEGFAULT_EXIT_CODES:
                f.write(f"\n\n!!! CRITICAL SEGMENTATION FAULT / CRASH (Exit Code: {exit_code}) !!!\n")
                f.write("Dumping last 256 bytes of STDERR as Hexadecimal Trace:\n")
                raw_err = "".join(stderr_history[-20:]).encode('utf-8', errors='replace')
                if not raw_err:
                    raw_err = b"Segmentation fault (core dumped)\n"
                
                # Take last 256 bytes, zero-padded if buffer is shorter
                target_bytes = raw_err[-256:] if len(raw_err) >= 256 else raw_err.ljust(256, b"\x00")
                for i in range(0, 256, 16):
                    chunk = target_bytes[i:i + 16]
                    hex_str = chunk.hex(' ')
                    f.write(f"0x{i:04X}: {hex_str}\n")

            footer = self._generate_json_ld_footer(job_name, exit_code, active_hash)
            f.write(footer)

        logger.info(f"Log finalized and archived: {log_path}")

        # Stream finalized event to cochem_telemetry_stream.jsonl
        if self.sink:
            self.sink.write_entry({
                "@context": "https://w3id.org/ro/qcschema",
                "@type": "JobTelemetryFinalized",
                "job_id": job_name,
                "exit_code": exit_code,
                "log_path": str(log_path),
                "execution_hash": active_hash,
                "status": "SUCCESS" if exit_code == 0 else ("CRASHED" if exit_code in CRITICAL_SEGFAULT_EXIT_CODES else "FAILED"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "warnings_count": self.warnings_count,
                "errors_count": self.errors_count,
                "trap_events": self.get_trap_events(),
            }, sign=True)

        if self.ipc_streamer:
            self.ipc_streamer.publish_event("JOB_FINALIZED", {
                "job_id": job_name,
                "exit_code": exit_code,
                "log_path": str(log_path),
                "execution_hash": active_hash,
                "status": "SUCCESS" if exit_code == 0 else ("CRASHED" if exit_code in CRITICAL_SEGFAULT_EXIT_CODES else "FAILED"),
            })

        # Apply immutability lock (read-only)
        try:
            os.chmod(str(log_path), stat.S_IREAD)
            logger.info(f"Immutability lock (read-only) applied to {log_path}")
        except OSError as e:
            logger.warning(f"Could not set read-only permissions on {log_path}: {e}")

        return str(log_path)

    def close(self) -> None:
        """Flushes and closes underlying sink, rotating handler, and IPC resources."""
        if self.sink is not None:
            self.sink.close()
            self.sink = None
        if self.rotating_handler is not None:
            try:
                self.rotating_handler.flush()
                self.rotating_handler.close()
                if self.rotating_handler in logger.handlers:
                    logger.removeHandler(self.rotating_handler)
            except Exception:
                pass
            self.rotating_handler = None
        self.stop_ipc_stream()


__all__ = [
    "CRITICAL_SEGFAULT_EXIT_CODES",
    "DEFAULT_BACKUP_COUNT",
    "DEFAULT_LOG_BACKUP_COUNT",
    "DEFAULT_MAX_LOG_BYTES",
    "DEFAULT_MAX_STREAM_BYTES",
    "DEFAULT_ROTATING_LOG_FILENAME",
    "DEFAULT_STREAM_FILENAME",
    "HAS_PSUTIL",
    "HAS_PYNVML",
    "HAS_ZMQ",
    "RotatingJsonlSink",
    "TelemetryIPCListener",
    "TelemetryIPCStreamer",
    "TelemetryLogger",
    "capture_crash_telemetry_metrics",
    "compute_provenance_digest",
    "force_flush_and_close_hdf5_pointers",
    "get_default_secret_key",
    "get_plaintext_rotating_handler",
    "install_global_excepthook",
    "resolve_telemetry_log_dir",
    "safe_h5py_open",
    "setup_cochem_rotating_logger",
    "sign_provenance_block",
    "trap_unhandled_exceptions",
    "uninstall_global_excepthook",
    "verify_provenance_signature",
]

