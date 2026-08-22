#!/usr/bin/env python3
"""
CoChem-BASE: Distributed IPC and Single-Master HDF5 Data Architecture.

This module provides:
1. SWMR Eradication: Strict elimination of HDF5 SWMR on NFS/Lustre distributed filesystems.
2. Real-Time IPC: Local scratch SQLite Write-Ahead Logging (WAL) and ZeroMQ streaming.
3. Single Master Node Enforcement: Writes to landscape.h5 are strictly gatekept to Rank 0 / Master.
4. Rigorous HDF5 Filtering: Mandatory gzip+shuffle+fletcher32 filters on all serialized datasets.
5. Full QCSchema Compliance: Lossless round-trip serialization of QCSchema v1/v2 records (AtomicResult, Wavefunction, OptimizationResult).
6. VRAM Offloading & Tensor Stripping: Automatic detachment and conversion of PyTorch/JAX tensors to pure host-RAM NumPy arrays and Python scalars.
7. Landscape Database Management: Comprehensive basin, calculation, and trajectory persistence in Databases/landscape.h5.

Zero-Mock Policy: 100% genuine OS processes, genuine atomic file locks, real SQLite WAL, and real HDF5 operations.
"""

from __future__ import annotations

import ast
import io
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union, cast

import h5py
import numpy as np
import zmq
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Optional deep learning & chemistry imports
try:
    import torch
except ImportError:
    torch = None

try:
    import jax
    import jax.numpy as jnp
except ImportError:
    jax = None
    jnp = None

try:
    import qcelemental as qcel
    try:
        from qcelemental.models.v2 import AtomicResult as QCElAtomicResult
        from qcelemental.models.v2 import Molecule as QCElMolecule
        from qcelemental.models.v2 import OptimizationResult as QCElOptimizationResult
    except (ImportError, RuntimeError):
        from qcelemental.models import AtomicResult as QCElAtomicResult  # type: ignore
        from qcelemental.models import Molecule as QCElMolecule  # type: ignore
        from qcelemental.models import OptimizationResult as QCElOptimizationResult  # type: ignore
except ImportError:
    qcel = None
    QCElAtomicResult = None
    QCElMolecule = None
    QCElOptimizationResult = None

from cochem_base.config_loader import (
    get_artifact_dir,
    get_scratch_dir,
    resolve_mapped_path,
)
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock

logger = logging.getLogger("CoChem-HDF5Manager")


# =============================================================================
# TYPED EXCEPTIONS
# =============================================================================

class HDF5ManagerError(Exception):
    """Base exception for all HDF5 data architecture and IPC operations."""


class NonMasterWriteRejectionError(HDF5ManagerError, PermissionError):
    """Raised when a non-master compute node attempts direct HDF5 writes."""


class HDF5FilterViolationError(HDF5ManagerError, ValueError):
    """Raised when a dataset is created without mandatory gzip+shuffle+fletcher32 filters."""


class QCSchemaValidationError(HDF5ManagerError, ValueError):
    """Raised when a payload fails QCSchema validation."""


class IPCRuntimeError(HDF5ManagerError, RuntimeError):
    """Raised when real-time IPC streaming or queueing encounters an error."""


class DatasetNotFoundError(HDF5ManagerError, KeyError):
    """Raised when a requested dataset or record is not found in HDF5."""


# =============================================================================
# 1. SWMR ERADICATION & AUDIT VERIFICATION
# =============================================================================

def verify_no_swmr_usage(module_or_obj: Any = None) -> bool:
    """Audits the module AST and runtime flags to ensure HDF5 SWMR mode is completely eradicated."""
    if module_or_obj is None:
        import cochem_base.core.cochem_core_hdf5_manager as current_mod
        module_or_obj = current_mod

    if isinstance(module_or_obj, Path):
        src = module_or_obj.read_text(encoding="utf-8")
    elif isinstance(module_or_obj, str):
        if "\n" in module_or_obj or not os.path.exists(module_or_obj):
            src = module_or_obj
        else:
            src = Path(module_or_obj).read_text(encoding="utf-8")
    elif hasattr(module_or_obj, "__file__") and module_or_obj.__file__:
        src = Path(module_or_obj.__file__).read_text(encoding="utf-8")
    else:
        import inspect
        src = inspect.getsource(module_or_obj)

    parsed = ast.parse(src)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "swmr" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    raise HDF5ManagerError("SWMR Violation: swmr activation flag detected in codebase.")
                if kw.arg == "libver" and isinstance(kw.value, ast.Constant) and kw.value.value == "latest":
                    raise HDF5ManagerError("SWMR Violation: libver latest flag detected in codebase.")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "swmr_mode":
                    raise HDF5ManagerError("SWMR Violation: swmr_mode assignment detected in codebase.")

    return True


# =============================================================================
# 2. VRAM OFFLOADING & TENSOR STRIPPING
# =============================================================================

def strip_tensor_to_numpy(val: Any) -> Any:
    """Recursively converts PyTorch and JAX autograd variables to pure host RAM NumPy arrays or Python scalars.

    Ensures the master node strictly interacts with system RAM, keeping GPU VRAM clear.
    """
    if val is None:
        return None

    # 1. PyTorch Tensor stripping
    if torch is not None and isinstance(val, torch.Tensor):
        cpu_tensor = val.detach().cpu()
        if cpu_tensor.ndim == 0:
            item = cpu_tensor.item()
            return int(item) if isinstance(item, int) else float(item)
        return np.ascontiguousarray(cpu_tensor.numpy())

    # 2. JAX Array stripping
    if jax is not None and jnp is not None:
        if isinstance(val, (jax.Array, jnp.ndarray)):
            arr = np.asarray(val)
            if arr.ndim == 0:
                item = arr.item()
                return int(item) if isinstance(item, int) else float(item)
            return np.ascontiguousarray(arr)

    # 3. NumPy arrays
    if isinstance(val, np.ndarray):
        if val.ndim == 0:
            item = val.item()
            return int(item) if isinstance(item, int) else float(item)
        return np.ascontiguousarray(val)

    if isinstance(val, np.generic):
        return val.item()

    # 4. Standard Python primitives
    if isinstance(val, (int, float, str, bool, bytes)):
        return val

    # 5. Pydantic models
    if isinstance(val, BaseModel):
        dumped = val.model_dump()
        return sanitize_for_host_ram(dumped)

    # 6. Containers
    if isinstance(val, dict):
        return {str(k): strip_tensor_to_numpy(v) for k, v in val.items()}

    if isinstance(val, (list, tuple, set)):
        converted = [strip_tensor_to_numpy(item) for item in val]
        return type(val)(converted) if not isinstance(val, set) else set(converted)

    return val


def sanitize_for_host_ram(payload: Any) -> Any:
    """Deeply sanitizes any payload structure to guarantee complete VRAM offloading."""
    return strip_tensor_to_numpy(payload)


# =============================================================================
# 3. REAL-TIME IPC: SQLITE WAL ON LOCAL SCRATCH
# =============================================================================

class SQLiteWALQueue:
    """High-throughput, process-safe real-time IPC queue using SQLite in Write-Ahead Logging (WAL) mode.

    Isolates real-time data streaming and IPC from persistent storage bottlenecks on shared filesystems.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        if db_path is not None:
            self.db_path = resolve_mapped_path(db_path)
        else:
            self.db_path = get_scratch_dir() / "cochem_ipc_wal.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level=None,  # Autocommit / fine-grained transactions
                check_same_thread=False,
            )
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=10000;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return cast(sqlite3.Connection, self._local.conn)

    def _init_database(self) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ipc_stream_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    sender_node TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    binary_payload BLOB,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at REAL NOT NULL,
                    processed_at REAL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ipc_topic_status
                ON ipc_stream_records(topic, status, created_at);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ipc_wavefunction_staging (
                    record_id TEXT PRIMARY KEY,
                    molecule_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    binary_arrays BLOB,
                    created_at REAL NOT NULL
                );
                """
            )

    def get_journal_mode(self) -> str:
        """Returns active SQLite journal mode."""
        conn = self._get_connection()
        cursor = conn.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        return str(row[0]) if row else "unknown"

    def push(
        self,
        topic: str,
        payload: Any,
        sender: str = "worker",
        stream_id: Optional[str] = None,
        binary_data: Optional[bytes] = None,
    ) -> int:
        """Pushes a sanitized record onto the IPC stream."""
        clean_payload = sanitize_for_host_ram(payload)
        json_str = json.dumps(clean_payload)
        s_id = stream_id or f"stream_{time.time_ns()}"
        now = time.time()

        conn = self._get_connection()
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO ipc_stream_records
                (stream_id, topic, sender_node, payload_json, binary_payload, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?);
                """,
                (s_id, topic, sender, json_str, binary_data, now),
            )
            return cursor.lastrowid or 0

    def pop_pending(self, topic: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Atomically retrieves and marks pending records as processed."""
        conn = self._get_connection()
        with conn:
            if topic is not None:
                cursor = conn.execute(
                    """
                    SELECT id, stream_id, topic, sender_node, payload_json, binary_payload, created_at
                    FROM ipc_stream_records
                    WHERE status = 'pending' AND topic = ?
                    ORDER BY id ASC LIMIT ?;
                    """,
                    (topic, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, stream_id, topic, sender_node, payload_json, binary_payload, created_at
                    FROM ipc_stream_records
                    WHERE status = 'pending'
                    ORDER BY id ASC LIMIT ?;
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            if not rows:
                return []

            ids = [r[0] for r in rows]
            now = time.time()
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"""
                UPDATE ipc_stream_records
                SET status = 'processed', processed_at = ?
                WHERE id IN ({placeholders});
                """,
                [now, *ids],
            )

            records: List[Dict[str, Any]] = []
            for r in rows:
                records.append({
                    "id": r[0],
                    "stream_id": r[1],
                    "topic": r[2],
                    "sender_node": r[3],
                    "payload": json.loads(r[4]),
                    "binary_payload": r[5],
                    "created_at": r[6],
                })
            return records

    def drain_all(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Drains all pending records in batches."""
        all_records: List[Dict[str, Any]] = []
        while True:
            batch = self.pop_pending(topic=topic, limit=500)
            if not batch:
                break
            all_records.extend(batch)
        return all_records

    def count_pending(self, topic: Optional[str] = None) -> int:
        """Returns the number of pending records in the queue."""
        conn = self._get_connection()
        if topic is not None:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM ipc_stream_records WHERE status = 'pending' AND topic = ?;",
                (topic,),
            )
        else:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM ipc_stream_records WHERE status = 'pending';"
            )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def clear(self) -> None:
        """Clears all records from the queue."""
        conn = self._get_connection()
        with conn:
            conn.execute("DELETE FROM ipc_stream_records;")
            conn.execute("DELETE FROM ipc_wavefunction_staging;")

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None


# =============================================================================
# 4. REAL-TIME IPC: ZEROMQ STREAMING
# =============================================================================

class ZMQRealTimeStreamer:
    """Low-latency ZeroMQ real-time streaming endpoint for physics & wavefunction telemetry."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5577) -> None:
        self.host = host
        self.port = port
        self._ctx: Optional[zmq.Context[Any]] = None
        self._socket: Optional[zmq.Socket[Any]] = None
        self._lock = threading.Lock()

    def _get_context(self) -> zmq.Context[Any]:
        if self._ctx is None:
            self._ctx = zmq.Context.instance()
        return self._ctx

    def bind_pull(self, ready_event: Optional[threading.Event] = None) -> None:
        """Binds a PULL socket on master to collect streams from worker nodes."""
        with self._lock:
            ctx = self._get_context()
            sock = ctx.socket(zmq.PULL)
            sock.setsockopt(zmq.LINGER, 1000)
            sock.bind(f"tcp://{self.host}:{self.port}")
            self._socket = sock
            if ready_event is not None:
                ready_event.set()

    def connect_push(self) -> None:
        """Connects a PUSH socket on a worker node to stream to the master collector."""
        with self._lock:
            ctx = self._get_context()
            sock = ctx.socket(zmq.PUSH)
            sock.setsockopt(zmq.LINGER, 1000)
            sock.connect(f"tcp://{self.host}:{self.port}")
            self._socket = sock

    def send_record(
        self,
        topic: str,
        metadata: Dict[str, Any],
        array: Optional[np.ndarray] = None,
        timeout_ms: int = 5000,
    ) -> None:
        """Sends a multipart frame: topic, metadata JSON, and optional binary NumPy buffer."""
        if self._socket is None:
            raise IPCRuntimeError("ZMQ socket is not connected or bound.")

        clean_meta = sanitize_for_host_ram(metadata)
        json_bytes = json.dumps(clean_meta).encode("utf-8")
        topic_bytes = topic.encode("utf-8")

        frames: List[bytes] = [topic_bytes, json_bytes]
        if array is not None:
            clean_arr = strip_tensor_to_numpy(array)
            buf = io.BytesIO()
            np.save(buf, clean_arr, allow_pickle=False)
            frames.append(buf.getvalue())
        else:
            frames.append(b"")

        self._socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
        try:
            self._socket.send_multipart(frames)
        except zmq.error.Again as e:
            raise IPCRuntimeError(f"ZMQ send timed out after {timeout_ms}ms") from e

    def recv_record(self, timeout_ms: int = 5000) -> Optional[Dict[str, Any]]:
        """Receives a multipart frame with topic, metadata, and optional NumPy array."""
        if self._socket is None:
            raise IPCRuntimeError("ZMQ socket is not connected or bound.")

        self._socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        try:
            parts = self._socket.recv_multipart()
            if len(parts) < 3:
                return None

            topic = parts[0].decode("utf-8")
            metadata = json.loads(parts[1].decode("utf-8"))
            array: Optional[np.ndarray] = None

            if parts[2] and len(parts[2]) > 0:
                buf = io.BytesIO(parts[2])
                array = np.load(buf, allow_pickle=False)

            return {
                "topic": topic,
                "metadata": metadata,
                "array": array,
            }
        except zmq.error.Again:
            return None

    def close(self) -> None:
        """Closes the active socket with a brief linger to ensure in-flight messages flush."""
        with self._lock:
            if self._socket is not None:
                try:
                    self._socket.close(linger=1000)
                except Exception:
                    pass
                self._socket = None


# =============================================================================
# 5. SINGLE MASTER NODE DETECTION & WRITE GATEKEEPER
# =============================================================================

def is_master_node() -> bool:
    """Determines whether the current execution process is the designated master node (Rank 0 / Standalone)."""
    override = os.environ.get("COCHEM_IS_MASTER")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")

    slurm_procid = os.environ.get("SLURM_PROCID")
    if slurm_procid is not None:
        return slurm_procid.strip() == "0"

    for rank_var in ["OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK", "MV2_COMM_WORLD_RANK"]:
        val = os.environ.get(rank_var)
        if val is not None:
            return val.strip() == "0"

    return True


# =============================================================================
# 6. RIGOROUS HDF5 FILTERING (gzip + shuffle + fletcher32)
# =============================================================================

def verify_dataset_filters(dset: h5py.Dataset) -> Tuple[bool, Dict[str, Any]]:
    """Verifies that an HDF5 dataset strictly enforces chunking, gzip compression, shuffle, and fletcher32."""
    compression = getattr(dset, "compression", None)
    compression_opts = getattr(dset, "compression_opts", None)
    shuffle = getattr(dset, "shuffle", False)
    fletcher32 = getattr(dset, "fletcher32", False)
    chunks = getattr(dset, "chunks", None)

    details = {
        "compression": compression,
        "compression_opts": compression_opts,
        "shuffle": shuffle,
        "fletcher32": fletcher32,
        "chunks": chunks,
    }

    is_valid = (
        compression == "gzip"
        and shuffle is True
        and fletcher32 is True
        and chunks is not None
    )
    return is_valid, details


def _normalize_dataset_for_filters(data: Any) -> np.ndarray:
    """Normalizes input data into fixed-size atomic NumPy types suitable for HDF5 shuffle filter."""
    clean_data = strip_tensor_to_numpy(data)
    if isinstance(clean_data, (list, tuple)):
        if len(clean_data) > 0 and all(isinstance(x, str) for x in clean_data):
            max_len = max(len(s.encode("utf-8")) for s in clean_data) if clean_data else 1
            str_dtype = f"S{max(8, max_len + 1)}"
            return np.array([s.encode("utf-8") for s in clean_data], dtype=str_dtype)

    if not isinstance(clean_data, np.ndarray):
        arr: np.ndarray = np.asarray(clean_data)
    else:
        arr = clean_data

    if arr.dtype.kind == "U":
        max_item_len = max(len(str(x).encode("utf-8")) for x in arr.flat) if arr.size > 0 else 1
        str_dtype = f"S{max(8, max_item_len + 1)}"
        arr = np.array([str(x).encode("utf-8") for x in arr.flat], dtype=str_dtype).reshape(arr.shape)

    if arr.ndim == 0:
        arr = arr.reshape((1,))

    return cast(np.ndarray, arr)



def write_dataset_filtered(
    group: Union[h5py.Group, h5py.File],
    dataset_name: str,
    data: Any,
    compression: Optional[str] = "gzip",
    compression_opts: int = 6,
    shuffle: bool = True,
    fletcher32: bool = True,
    chunks: Optional[Any] = True,
    attrs: Optional[Dict[str, Any]] = None,
    strict: bool = True,
) -> h5py.Dataset:
    """Creates or overwrites an HDF5 dataset enforcing mandatory gzip+shuffle+fletcher32 filters.

    Raises HDF5FilterViolationError if filters are missing or bypassed when strict=True.
    """
    clean_data = _normalize_dataset_for_filters(data)

    if strict:
        if compression != "gzip":
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must use gzip compression (got: {compression})"
            )
        if not shuffle:
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must have shuffle=True"
            )
        if not fletcher32:
            raise HDF5FilterViolationError(
                f"Dataset '{dataset_name}' must have fletcher32=True checksum filter"
            )

    if dataset_name in group:
        del group[dataset_name]

    dset = group.create_dataset(
        dataset_name,
        data=clean_data,
        compression="gzip" if compression == "gzip" else None,
        compression_opts=compression_opts if compression == "gzip" else None,
        shuffle=shuffle,
        fletcher32=fletcher32,
        chunks=chunks,
    )

    if attrs:
        for k, v in attrs.items():
            clean_v = strip_tensor_to_numpy(v)
            if isinstance(clean_v, (int, float, str, bool)):
                dset.attrs[k] = clean_v
            else:
                dset.attrs[k] = json.dumps(clean_v)

    return dset


# =============================================================================
# 7. FULL QCSCHEMA SPECIFICATION MODELS
# =============================================================================

class QCSchemaDriver(str, Enum):
    ENERGY = "energy"
    GRADIENT = "gradient"
    HESSIAN = "hessian"
    PROPERTIES = "properties"


class QCSchemaModel(BaseModel):
    """QCSchema quantum chemistry model specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: str = Field(..., description="Electronic structure method, e.g., r2SCAN-3c, B3LYP, CCSD(T)")
    basis: Optional[str] = Field(None, description="Primary orbital basis set")


class QCSchemaMolecule(BaseModel):
    """QCSchema v1/v2 Molecular specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbols: List[str] = Field(..., description="Atomic element symbols")
    geometry: List[float] = Field(..., description="Flattened Cartesian atomic coordinates in Bohr")
    molecular_charge: float = Field(default=0.0, description="Total molecular charge")
    molecular_multiplicity: int = Field(default=1, ge=1, description="Total spin multiplicity")
    mass_numbers: Optional[List[int]] = Field(default=None, description="Optional mass numbers for isotopes")
    real: Optional[List[bool]] = Field(default=None, description="Ghost atom indicators")
    connectivity: Optional[List[Tuple[int, int, float]]] = Field(default=None, description="Connectivity graph")

    @field_validator("geometry", mode="before")
    @classmethod
    def validate_geometry(cls, v: Any) -> List[float]:
        cleaned = strip_tensor_to_numpy(v)
        if isinstance(cleaned, np.ndarray):
            return [float(x) for x in cleaned.flatten()]
        if isinstance(cleaned, list):
            flat: List[float] = []
            for item in cleaned:
                if isinstance(item, (list, tuple, np.ndarray)):
                    flat.extend(float(x) for x in item)
                else:
                    flat.append(float(item))
            return flat
        raise ValueError("Invalid geometry format")


class QCSchemaProperties(BaseModel):
    """QCSchema output properties specification."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    return_energy: Optional[float] = Field(default=None, description="Final return energy in Hartrees")
    scf_total_energy: Optional[float] = Field(default=None, description="Total SCF energy in Hartrees")
    nuclear_repulsion_energy: Optional[float] = Field(default=None, description="Nuclear repulsion energy")
    scf_iterations: Optional[int] = Field(default=None, description="Number of SCF cycles")
    dipole: Optional[List[float]] = Field(default=None, description="Dipole moment components in Debye")


class QCSchemaWavefunction(BaseModel):
    """QCSchema Wavefunction and Orbital data container."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    basis: Optional[str] = Field(None, description="Basis set specification")
    orbitals_a: Optional[Any] = Field(None, description="Alpha molecular orbital coefficients")
    orbitals_b: Optional[Any] = Field(None, description="Beta molecular orbital coefficients")
    occupations_a: Optional[Any] = Field(None, description="Alpha orbital occupations")
    occupations_b: Optional[Any] = Field(None, description="Beta orbital occupations")
    density_a: Optional[Any] = Field(None, description="Alpha electron density matrix")
    density_b: Optional[Any] = Field(None, description="Beta electron density matrix")
    fock_a: Optional[Any] = Field(None, description="Alpha Fock matrix")
    fock_b: Optional[Any] = Field(None, description="Beta Fock matrix")


class QCSchemaAtomicResult(BaseModel):
    """QCSchema v1/v2 AtomicResult standard execution record."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_name: str = Field(default="qcschema_output", description="QCSchema protocol identifier")
    schema_version: int = Field(default=1, description="QCSchema protocol version")
    molecule: QCSchemaMolecule = Field(..., description="Target molecular specification")
    driver: QCSchemaDriver = Field(..., description="Execution calculation driver")
    model: QCSchemaModel = Field(..., description="Computational model specification")
    return_result: Union[float, List[float], List[List[float]], Dict[str, Any]] = Field(
        ..., description="Primary calculation output result"
    )
    properties: QCSchemaProperties = Field(default_factory=QCSchemaProperties, description="Computed properties")
    wavefunction: Optional[QCSchemaWavefunction] = Field(default=None, description="Wavefunction records")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Execution provenance metadata")
    stdout: Optional[str] = Field(default=None, description="Captured standard output")
    stderr: Optional[str] = Field(default=None, description="Captured standard error")
    success: bool = Field(default=True, description="Calculation success status")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error details if execution failed")


class QCSchemaOptimizationResult(BaseModel):
    """QCSchema v1/v2 Geometry Optimization standard execution record."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_name: str = Field(default="qcschema_optimization_output", description="QCSchema protocol identifier")
    schema_version: int = Field(default=1, description="QCSchema protocol version")
    initial_molecule: QCSchemaMolecule = Field(..., description="Starting unrelaxed geometry")
    final_molecule: QCSchemaMolecule = Field(..., description="Converged geometry")
    trajectory: List[QCSchemaAtomicResult] = Field(default_factory=list, description="Optimization steps")
    energies: List[float] = Field(default_factory=list, description="Energy per optimization step")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Execution provenance metadata")
    success: bool = Field(default=True, description="Optimization convergence success status")


# =============================================================================
# 8. BASIN RECORDS SCHEMA
# =============================================================================

class BasinRecord(BaseModel):
    """Pydantic model for HDF5 Basin Record schema enforcement."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    molecule_name: str = Field(..., description="Name or identifier of the molecule")
    xyz_coordinates: Optional[Any] = Field(None, description="Atomic coordinates array or list")
    energy: float = Field(..., description="Total energy of the basin in Hartrees")
    symmetry_group: str = Field(default="C1", description="Point group symmetry")
    LAM_TRIGGER_REQUIRED: bool = Field(default=False, description="Large Amplitude Motion trigger flag")

    @field_validator("xyz_coordinates", mode="before")
    @classmethod
    def validate_xyz(cls, v: Any) -> Any:
        return strip_tensor_to_numpy(v)


# =============================================================================
# 9. MASTER WRITE GATEKEEPER & MASTER DATA AGGREGATOR
# =============================================================================

def resolve_landscape_h5_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolves the authoritative path to landscape.h5."""
    if custom_path is not None:
        p = resolve_mapped_path(custom_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    env_path = os.environ.get("COCHEM_LANDSCAPE_H5")
    if env_path:
        p = resolve_mapped_path(env_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    artifact_dir = get_artifact_dir()
    db_dir = artifact_dir / "Databases"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "landscape.h5"


class MasterWriteGatekeeper:
    """Enforces that HDF5 writes are strictly executed by the master node.

    Worker nodes attempting direct writes are either rejected with NonMasterWriteRejectionError
    or forwarded cleanly through the local SQLite WAL queue to be aggregated asynchronously.
    """

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        self.lock_path = Path(str(self.h5_path) + ".lock")
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)

    @property
    def is_master(self) -> bool:
        return is_master_node()

    def write_basin(
        self,
        basin_id: str,
        record: Union[BasinRecord, Dict[str, Any]],
        allow_ipc_forward: bool = True,
    ) -> Union[bool, int]:
        """Writes a basin record to HDF5 if master, or forwards to IPC stream if worker."""
        if not isinstance(record, BasinRecord):
            record = BasinRecord(**record)

        if self.is_master:
            with AtomicFileLock(self.lock_path, timeout=15.0):
                with h5py.File(self.h5_path, "a") as f:
                    grp = f.require_group(f"basins/{basin_id}")
                    grp.attrs["molecule_name"] = record.molecule_name
                    grp.attrs["energy"] = float(record.energy)
                    grp.attrs["symmetry_group"] = record.symmetry_group
                    grp.attrs["LAM_TRIGGER_REQUIRED"] = bool(record.LAM_TRIGGER_REQUIRED)
                    if record.xyz_coordinates is not None:
                        coords = strip_tensor_to_numpy(record.xyz_coordinates)
                        write_dataset_filtered(
                            grp,
                            "xyz_coordinates",
                            coords,
                            compression="gzip",
                            compression_opts=6,
                            shuffle=True,
                            fletcher32=True,
                        )
            return True

        if not allow_ipc_forward:
            raise NonMasterWriteRejectionError(
                f"Direct HDF5 write denied: Process is not the master node. Target: {self.h5_path}"
            )

        rec_dict = record.model_dump()
        rec_id = self.ipc_queue.push(
            topic="basin_stream",
            payload={"basin_id": basin_id, "data": rec_dict},
            sender=f"worker_pid_{os.getpid()}",
        )
        return rec_id


class MasterDataAggregator:
    """Master node collector service that drains SQLite WAL streams and serializes data into landscape.h5."""

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)
        self.gatekeeper = MasterWriteGatekeeper(h5_path=self.h5_path, ipc_db_path=ipc_db_path)

    def aggregate_pending(self, topic: Optional[str] = None, limit: int = 500) -> int:
        """Pulls pending records from SQLite WAL and writes them cleanly to HDF5 on the master node."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("MasterDataAggregator can only execute on the master node.")

        records = self.ipc_queue.pop_pending(topic=topic, limit=limit)
        if not records:
            return 0

        for r in records:
            topic_name = r.get("topic")
            payload = r.get("payload", {})

            if topic_name == "basin_stream":
                basin_id = payload.get("basin_id")
                basin_data = payload.get("data")
                if basin_id and basin_data:
                    self.gatekeeper.write_basin(basin_id, basin_data, allow_ipc_forward=False)

            elif topic_name == "qcschema_stream":
                calc_id = payload.get("calc_id")
                qcschema_data = payload.get("data")
                if calc_id and qcschema_data:
                    manager = CoChemHDF5Manager(h5_path=self.h5_path)
                    manager.write_qcschema_result(calc_id, qcschema_data)

            elif topic_name in ("optimization_stream", "trajectory_stream"):
                opt_id = payload.get("opt_id") or payload.get("trajectory_id")
                opt_data = payload.get("data")
                if opt_id and opt_data:
                    manager = CoChemHDF5Manager(h5_path=self.h5_path)
                    manager.write_qcschema_optimization_result(opt_id, opt_data)

        return len(records)


# =============================================================================
# 10. HIGH-LEVEL COCHEM HDF5 ARCHITECTURE MANAGER
# =============================================================================

class CoChemHDF5Manager:
    """Master HDF5 Data Architecture Manager for the CoChem ecosystem.

    Provides high-performance, single-master, filter-enforced data serialization,
    QCSchema compliance, and real-time IPC streaming.
    """

    SCHEMA_VERSION = "4.0.0"

    def __init__(
        self,
        h5_path: Optional[Union[str, Path]] = None,
        ipc_db_path: Optional[Union[str, Path]] = None,
        strict_filters: bool = True,
    ) -> None:
        self.h5_path = resolve_landscape_h5_path(h5_path)
        self.lock_path = Path(str(self.h5_path) + ".lock")
        self.strict_filters = strict_filters
        self.ipc_queue = SQLiteWALQueue(db_path=ipc_db_path)
        self.gatekeeper = MasterWriteGatekeeper(h5_path=self.h5_path, ipc_db_path=ipc_db_path)
        self._init_landscape_file()

    def _init_landscape_file(self) -> None:
        """Initializes the landscape HDF5 file topology with atomic locking."""
        if not is_master_node():
            return

        with AtomicFileLock(self.lock_path, timeout=15.0):
            with h5py.File(self.h5_path, "a") as f:
                if "version" not in f.attrs:
                    f.attrs["version"] = self.SCHEMA_VERSION
                    f.attrs["created_at"] = datetime.now(timezone.utc).isoformat()
                for grp in ["basins", "calculations", "molecules", "trajectories", "physics"]:
                    if grp not in f:
                        f.create_group(grp)

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic, lock-protected transaction on landscape.h5."""
        if mode in ("w", "a", "r+") and not is_master_node():
            raise NonMasterWriteRejectionError(
                f"Write transaction denied: Process is not the master node. Target: {self.h5_path}"
            )

        with AtomicFileLock(self.lock_path, timeout=15.0):
            with h5py.File(self.h5_path, mode) as f:
                yield f

    def write_dataset_filtered(
        self,
        group_path: str,
        dataset_name: str,
        data: Any,
        compression: Optional[str] = "gzip",
        compression_opts: int = 6,
        shuffle: bool = True,
        fletcher32: bool = True,
        chunks: Optional[Any] = True,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Writes a filtered dataset to the HDF5 store under group_path."""
        with self.transaction("a") as f:
            grp = f.require_group(group_path)
            write_dataset_filtered(
                grp,
                dataset_name,
                data,
                compression=compression,
                compression_opts=compression_opts,
                shuffle=shuffle,
                fletcher32=fletcher32,
                chunks=chunks,
                attrs=attrs,
                strict=self.strict_filters,
            )

    # -------------------------------------------------------------------------
    # Basin Operations
    # -------------------------------------------------------------------------

    def write_basin_record(self, basin_id: str, record: Union[BasinRecord, Dict[str, Any]]) -> None:
        """Writes a BasinRecord into landscape.h5."""
        self.gatekeeper.write_basin(basin_id, record, allow_ipc_forward=False)

    def read_basin_record(self, basin_id: str) -> BasinRecord:
        """Reads a BasinRecord from landscape.h5."""
        with self.transaction("r") as f:
            grp_path = f"basins/{basin_id}"
            if grp_path not in f:
                raise DatasetNotFoundError(f"Basin record '{basin_id}' not found.")
            grp = f[grp_path]
            coords: Optional[np.ndarray] = None
            if "xyz_coordinates" in grp:
                coords = grp["xyz_coordinates"][()]

            return BasinRecord(
                molecule_name=str(grp.attrs.get("molecule_name", "")),
                xyz_coordinates=coords,
                energy=float(grp.attrs.get("energy", 0.0)),
                symmetry_group=str(grp.attrs.get("symmetry_group", "C1")),
                LAM_TRIGGER_REQUIRED=bool(grp.attrs.get("LAM_TRIGGER_REQUIRED", False)),
            )

    def list_basins(self) -> List[str]:
        """Lists all registered basin IDs."""
        with self.transaction("r") as f:
            if "basins" in f:
                return list(f["basins"].keys())
            return []

    # -------------------------------------------------------------------------
    # QCSchema Serialization & Deserialization
    # -------------------------------------------------------------------------

    def write_qcschema_result(
        self,
        calc_id: str,
        result: Union[QCSchemaAtomicResult, Dict[str, Any], Any],
    ) -> None:
        """Serializes a QCSchema AtomicResult (v1 or v2) or QCElemental model into landscape.h5."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("Only master node can commit QCSchema results to HDF5.")

        if isinstance(result, QCSchemaAtomicResult):
            atomic_res = result
        elif isinstance(result, dict):
            # Check if dict is in v2 format (has input_data)
            if "input_data" in result and "molecule" in result:
                inp_data = result["input_data"]
                spec = inp_data.get("specification", {}) if isinstance(inp_data, dict) else getattr(inp_data, "specification", {})
                driver = inp_data.get("driver") or getattr(spec, "driver", None) or (spec.get("driver") if isinstance(spec, dict) else "energy")
                model_spec = inp_data.get("model") or getattr(spec, "model", None) or (spec.get("model") if isinstance(spec, dict) else {"method": "unknown"})
                if isinstance(model_spec, dict):
                    model_obj = QCSchemaModel(**model_spec)
                else:
                    model_obj = QCSchemaModel(method=getattr(model_spec, "method", "unknown"), basis=getattr(model_spec, "basis", None))

                mol_data = result["molecule"]
                if isinstance(mol_data, dict):
                    mol_obj = QCSchemaMolecule(
                        symbols=mol_data.get("symbols", []),
                        geometry=mol_data.get("geometry", []),
                        molecular_charge=float(mol_data.get("molecular_charge", 0.0)),
                        molecular_multiplicity=int(mol_data.get("molecular_multiplicity", 1)),
                    )
                else:
                    mol_obj = QCSchemaMolecule(
                        symbols=list(getattr(mol_data, "symbols", [])),
                        geometry=list(getattr(mol_data, "geometry", [])),
                        molecular_charge=float(getattr(mol_data, "molecular_charge", 0.0)),
                        molecular_multiplicity=int(getattr(mol_data, "molecular_multiplicity", 1)),
                    )

                props_data = result.get("properties", {})
                props_dict = props_data.model_dump() if hasattr(props_data, "model_dump") else (props_data if isinstance(props_data, dict) else props_data.dict())

                driver_val = driver.value if hasattr(driver, "value") else str(driver or "energy")
                atomic_res = QCSchemaAtomicResult(
                    schema_name=str(result.get("schema_name", "qcschema_output")),
                    schema_version=int(result.get("schema_version", 1)),
                    molecule=mol_obj,
                    driver=QCSchemaDriver(driver_val),
                    model=model_obj,
                    return_result=result.get("return_result", 0.0),
                    properties=QCSchemaProperties(**props_dict),
                    provenance=result.get("provenance", {}) if isinstance(result.get("provenance"), dict) else {},
                    success=bool(result.get("success", True)),
                )
            else:
                atomic_res = QCSchemaAtomicResult.model_validate(result)
        elif hasattr(result, "input_data") and hasattr(result, "molecule"):
            # Object is a v2 AtomicResult (e.g. qcelemental v2)
            inp_data = result.input_data
            spec = getattr(inp_data, "specification", None)
            raw_driver = getattr(inp_data, "driver", None) or getattr(spec, "driver", "energy")
            driver_val = raw_driver.value if hasattr(raw_driver, "value") else str(raw_driver or "energy")
            model_spec = getattr(inp_data, "model", None) or getattr(spec, "model", None)
            if model_spec is not None:
                method = getattr(model_spec, "method", "unknown")
                basis = getattr(model_spec, "basis", None)
            else:
                method = "unknown"
                basis = None
            model_obj = QCSchemaModel(method=method, basis=basis)

            mol_data = result.molecule
            mol_obj = QCSchemaMolecule(
                symbols=list(getattr(mol_data, "symbols", [])),
                geometry=list(getattr(mol_data, "geometry", [])),
                molecular_charge=float(getattr(mol_data, "molecular_charge", 0.0)),
                molecular_multiplicity=int(getattr(mol_data, "molecular_multiplicity", 1)),
            )

            props_data = getattr(result, "properties", {})
            props_dict = props_data.model_dump() if hasattr(props_data, "model_dump") else (props_data if isinstance(props_data, dict) else props_data.dict())

            atomic_res = QCSchemaAtomicResult(
                schema_name="qcschema_output",
                schema_version=1,
                molecule=mol_obj,
                driver=QCSchemaDriver(driver_val),
                model=model_obj,
                return_result=getattr(result, "return_result", 0.0),
                properties=QCSchemaProperties(**props_dict),
                success=bool(getattr(result, "success", True)),
            )
        elif QCElAtomicResult is not None and isinstance(result, QCElAtomicResult):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            atomic_res = QCSchemaAtomicResult.model_validate(dumped)
        else:
            atomic_res = QCSchemaAtomicResult.model_validate(result)


        with self.transaction("a") as f:
            calc_grp = f.require_group(f"calculations/{calc_id}")
            calc_grp.attrs["schema_name"] = atomic_res.schema_name
            calc_grp.attrs["schema_version"] = atomic_res.schema_version
            calc_grp.attrs["driver"] = atomic_res.driver.value if hasattr(atomic_res.driver, "value") else str(atomic_res.driver)
            calc_grp.attrs["method"] = atomic_res.model.method
            if atomic_res.model.basis:
                calc_grp.attrs["basis"] = atomic_res.model.basis
            calc_grp.attrs["success"] = atomic_res.success
            if isinstance(atomic_res.return_result, (int, float)):
                calc_grp.attrs["return_result"] = float(atomic_res.return_result)
            elif isinstance(atomic_res.return_result, (list, tuple, np.ndarray)):
                arr_res = np.asarray(cast(Any, atomic_res.return_result))
                if arr_res.size > 20:
                    write_dataset_filtered(
                        calc_grp,
                        "return_result",
                        arr_res,
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )
                else:
                    calc_grp.attrs["return_result"] = json.dumps(atomic_res.return_result)
            else:
                calc_grp.attrs["return_result"] = json.dumps(atomic_res.return_result)

            # Molecule group
            mol_grp = calc_grp.require_group("molecule")
            mol_grp.attrs["molecular_charge"] = atomic_res.molecule.molecular_charge
            mol_grp.attrs["molecular_multiplicity"] = atomic_res.molecule.molecular_multiplicity

            write_dataset_filtered(
                mol_grp,
                "symbols",
                atomic_res.molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                mol_grp,
                "geometry",
                np.array(atomic_res.molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Properties group
            prop_grp = calc_grp.require_group("properties")
            prop_dict = atomic_res.properties.model_dump()
            for pk, pv in prop_dict.items():
                if pv is not None:
                    if isinstance(pv, (int, float, str, bool)):
                        prop_grp.attrs[pk] = pv
                    else:
                        prop_grp.attrs[pk] = json.dumps(pv)

            # Wavefunction group (if present)
            if atomic_res.wavefunction is not None:
                wf_grp = calc_grp.require_group("wavefunction")
                if atomic_res.wavefunction.basis:
                    wf_grp.attrs["basis"] = atomic_res.wavefunction.basis

                wf_fields = [
                    ("orbitals_a", atomic_res.wavefunction.orbitals_a),
                    ("orbitals_b", atomic_res.wavefunction.orbitals_b),
                    ("occupations_a", atomic_res.wavefunction.occupations_a),
                    ("occupations_b", atomic_res.wavefunction.occupations_b),
                    ("density_a", atomic_res.wavefunction.density_a),
                    ("density_b", atomic_res.wavefunction.density_b),
                    ("fock_a", atomic_res.wavefunction.fock_a),
                    ("fock_b", atomic_res.wavefunction.fock_b),
                ]
                for wname, wval in wf_fields:
                    if wval is not None:
                        warr = strip_tensor_to_numpy(wval)
                        write_dataset_filtered(
                            wf_grp,
                            wname,
                            warr,
                            compression="gzip",
                            compression_opts=6,
                            shuffle=True,
                            fletcher32=True,
                        )

    def read_qcschema_result(self, calc_id: str) -> QCSchemaAtomicResult:
        """Reads a QCSchema AtomicResult from landscape.h5."""
        with self.transaction("r") as f:
            calc_path = f"calculations/{calc_id}"
            if calc_path not in f:
                raise DatasetNotFoundError(f"Calculation result '{calc_id}' not found.")

            calc_grp = f[calc_path]
            schema_name = str(calc_grp.attrs.get("schema_name", "qcschema_output"))
            schema_version = int(calc_grp.attrs.get("schema_version", 1))
            driver_str = str(calc_grp.attrs.get("driver", "energy"))
            method = str(calc_grp.attrs.get("method", ""))
            basis = calc_grp.attrs.get("basis")
            success = bool(calc_grp.attrs.get("success", True))

            if "return_result" in calc_grp:
                res_data = calc_grp["return_result"][()]
                return_result: Union[float, Any] = res_data.tolist() if isinstance(res_data, np.ndarray) else res_data
            else:
                raw_res = calc_grp.attrs.get("return_result")
                return_result = (
                    float(raw_res) if isinstance(raw_res, (int, float)) else json.loads(str(raw_res))
                )

            # Molecule
            mol_grp = calc_grp["molecule"]
            symbols_dset = mol_grp["symbols"][()]
            symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in symbols_dset]
            geom = mol_grp["geometry"][()].tolist()
            mol = QCSchemaMolecule(
                symbols=symbols,
                geometry=geom,
                molecular_charge=float(mol_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(mol_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Properties
            prop_grp = calc_grp.get("properties")
            prop_kwargs: Dict[str, Any] = {}
            if prop_grp is not None:
                for k, v in prop_grp.attrs.items():
                    prop_kwargs[k] = v
            props = QCSchemaProperties(**prop_kwargs)

            # Wavefunction
            wf: Optional[QCSchemaWavefunction] = None
            if "wavefunction" in calc_grp:
                wf_grp = calc_grp["wavefunction"]
                wf_kwargs: Dict[str, Any] = {"basis": wf_grp.attrs.get("basis")}
                for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                    if wname in wf_grp:
                        wf_kwargs[wname] = wf_grp[wname][()]
                wf = QCSchemaWavefunction(**wf_kwargs)

            return QCSchemaAtomicResult(
                schema_name=schema_name,
                schema_version=schema_version,
                molecule=mol,
                driver=QCSchemaDriver(driver_str),
                model=QCSchemaModel(method=method, basis=str(basis) if basis else None),
                return_result=return_result,
                properties=props,
                wavefunction=wf,
                success=success,
            )

    def list_calculations(self) -> List[str]:
        """Lists all calculation IDs."""
        with self.transaction("r") as f:
            if "calculations" in f:
                return list(f["calculations"].keys())
            return []

    # -------------------------------------------------------------------------
    # QCSchema OptimizationResult Serialization & Deserialization
    # -------------------------------------------------------------------------

    def write_qcschema_optimization_result(
        self,
        opt_id: str,
        result: Union[QCSchemaOptimizationResult, Dict[str, Any], Any],
    ) -> None:
        """Serializes a QCSchema OptimizationResult (v1 or v2) or QCElemental model into landscape.h5."""
        if not is_master_node():
            raise NonMasterWriteRejectionError("Only master node can commit Optimization results to HDF5.")

        if isinstance(result, QCSchemaOptimizationResult):
            opt_res = result
        elif isinstance(result, dict):
            init_mol_data = result.get("initial_molecule", {})
            init_mol = init_mol_data if isinstance(init_mol_data, QCSchemaMolecule) else QCSchemaMolecule.model_validate(init_mol_data)

            final_mol_data = result.get("final_molecule", {})
            final_mol = final_mol_data if isinstance(final_mol_data, QCSchemaMolecule) else QCSchemaMolecule.model_validate(final_mol_data)

            raw_traj = result.get("trajectory", [])
            traj_list: List[QCSchemaAtomicResult] = []
            for step in raw_traj:
                if isinstance(step, QCSchemaAtomicResult):
                    traj_list.append(step)
                elif isinstance(step, dict):
                    traj_list.append(QCSchemaAtomicResult.model_validate(step))
                elif hasattr(step, "model_dump"):
                    traj_list.append(QCSchemaAtomicResult.model_validate(step.model_dump()))

            energies = result.get("energies", [])
            if not energies and traj_list:
                energies = [
                    float(st.properties.return_energy) if st.properties.return_energy is not None
                    else (float(st.return_result) if isinstance(st.return_result, (int, float)) else 0.0)
                    for st in traj_list
                ]

            opt_res = QCSchemaOptimizationResult(
                schema_name=str(result.get("schema_name", "qcschema_optimization_output")),
                schema_version=int(result.get("schema_version", 1)),
                initial_molecule=init_mol,
                final_molecule=final_mol,
                trajectory=traj_list,
                energies=[float(e) for e in energies],
                provenance=result.get("provenance", {}) if isinstance(result.get("provenance"), dict) else {},
                success=bool(result.get("success", True)),
            )
        elif hasattr(result, "trajectory") and hasattr(result, "final_molecule"):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            opt_res = QCSchemaOptimizationResult.model_validate(dumped)
        elif QCElOptimizationResult is not None and isinstance(result, QCElOptimizationResult):
            dumped = result.model_dump() if hasattr(result, "model_dump") else result.dict()
            opt_res = QCSchemaOptimizationResult.model_validate(dumped)
        else:
            opt_res = QCSchemaOptimizationResult.model_validate(result)

        with self.transaction("a") as f:
            opt_grp = f.require_group(f"trajectories/{opt_id}")
            opt_grp.attrs["schema_name"] = opt_res.schema_name
            opt_grp.attrs["schema_version"] = opt_res.schema_version
            opt_grp.attrs["success"] = opt_res.success
            opt_grp.attrs["provenance"] = json.dumps(opt_res.provenance)

            # Initial Molecule
            init_grp = opt_grp.require_group("initial_molecule")
            init_grp.attrs["molecular_charge"] = opt_res.initial_molecule.molecular_charge
            init_grp.attrs["molecular_multiplicity"] = opt_res.initial_molecule.molecular_multiplicity
            write_dataset_filtered(
                init_grp,
                "symbols",
                opt_res.initial_molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                init_grp,
                "geometry",
                np.array(opt_res.initial_molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Final Molecule
            final_grp = opt_grp.require_group("final_molecule")
            final_grp.attrs["molecular_charge"] = opt_res.final_molecule.molecular_charge
            final_grp.attrs["molecular_multiplicity"] = opt_res.final_molecule.molecular_multiplicity
            write_dataset_filtered(
                final_grp,
                "symbols",
                opt_res.final_molecule.symbols,
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )
            write_dataset_filtered(
                final_grp,
                "geometry",
                np.array(opt_res.final_molecule.geometry, dtype=np.float64),
                compression="gzip",
                compression_opts=6,
                shuffle=True,
                fletcher32=True,
            )

            # Energies
            if opt_res.energies:
                write_dataset_filtered(
                    opt_grp,
                    "energies",
                    np.array(opt_res.energies, dtype=np.float64),
                    compression="gzip",
                    compression_opts=6,
                    shuffle=True,
                    fletcher32=True,
                )

            # Trajectory steps
            if opt_res.trajectory:
                steps_grp = opt_grp.require_group("steps")
                for i, step_item in enumerate(opt_res.trajectory):
                    step_grp = steps_grp.require_group(f"step_{i:04d}")
                    step_grp.attrs["schema_name"] = step_item.schema_name
                    step_grp.attrs["schema_version"] = step_item.schema_version
                    step_grp.attrs["driver"] = step_item.driver.value if hasattr(step_item.driver, "value") else str(step_item.driver)
                    step_grp.attrs["method"] = step_item.model.method
                    if step_item.model.basis:
                        step_grp.attrs["basis"] = step_item.model.basis
                    step_grp.attrs["success"] = step_item.success

                    if isinstance(step_item.return_result, (int, float)):
                        step_grp.attrs["return_result"] = float(step_item.return_result)
                    elif isinstance(step_item.return_result, (list, tuple, np.ndarray)):
                        arr_res = np.asarray(cast(Any, step_item.return_result))
                        if arr_res.size > 20:
                            write_dataset_filtered(
                                step_grp,
                                "return_result",
                                arr_res,
                                compression="gzip",
                                compression_opts=6,
                                shuffle=True,
                                fletcher32=True,
                            )
                        else:
                            step_grp.attrs["return_result"] = json.dumps(step_item.return_result)
                    else:
                        step_grp.attrs["return_result"] = json.dumps(step_item.return_result)

                    step_mol_grp = step_grp.require_group("molecule")
                    step_mol_grp.attrs["molecular_charge"] = step_item.molecule.molecular_charge
                    step_mol_grp.attrs["molecular_multiplicity"] = step_item.molecule.molecular_multiplicity
                    write_dataset_filtered(
                        step_mol_grp,
                        "symbols",
                        step_item.molecule.symbols,
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )
                    write_dataset_filtered(
                        step_mol_grp,
                        "geometry",
                        np.array(step_item.molecule.geometry, dtype=np.float64),
                        compression="gzip",
                        compression_opts=6,
                        shuffle=True,
                        fletcher32=True,
                    )

                    step_prop_grp = step_grp.require_group("properties")
                    for pk, pv in step_item.properties.model_dump().items():
                        if pv is not None:
                            if isinstance(pv, (int, float, str, bool)):
                                step_prop_grp.attrs[pk] = pv
                            else:
                                step_prop_grp.attrs[pk] = json.dumps(pv)

                    if step_item.wavefunction is not None:
                        step_wf_grp = step_grp.require_group("wavefunction")
                        if step_item.wavefunction.basis:
                            step_wf_grp.attrs["basis"] = step_item.wavefunction.basis
                        for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                            wval = getattr(step_item.wavefunction, wname, None)
                            if wval is not None:
                                write_dataset_filtered(
                                    step_wf_grp,
                                    wname,
                                    strip_tensor_to_numpy(wval),
                                    compression="gzip",
                                    compression_opts=6,
                                    shuffle=True,
                                    fletcher32=True,
                                )

    def read_qcschema_optimization_result(self, opt_id: str) -> QCSchemaOptimizationResult:
        """Reads a QCSchema OptimizationResult from landscape.h5."""
        with self.transaction("r") as f:
            opt_path = f"trajectories/{opt_id}"
            if opt_path not in f:
                raise DatasetNotFoundError(f"Optimization trajectory '{opt_id}' not found.")

            opt_grp = f[opt_path]
            schema_name = str(opt_grp.attrs.get("schema_name", "qcschema_optimization_output"))
            schema_version = int(opt_grp.attrs.get("schema_version", 1))
            success = bool(opt_grp.attrs.get("success", True))
            raw_prov = opt_grp.attrs.get("provenance", "{}")
            prov = json.loads(raw_prov) if isinstance(raw_prov, str) else (raw_prov or {})

            # Initial Molecule
            init_grp = opt_grp["initial_molecule"]
            init_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in init_grp["symbols"][()]]
            init_geom = init_grp["geometry"][()].tolist()
            init_mol = QCSchemaMolecule(
                symbols=init_syms,
                geometry=init_geom,
                molecular_charge=float(init_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(init_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Final Molecule
            final_grp = opt_grp["final_molecule"]
            final_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in final_grp["symbols"][()]]
            final_geom = final_grp["geometry"][()].tolist()
            final_mol = QCSchemaMolecule(
                symbols=final_syms,
                geometry=final_geom,
                molecular_charge=float(final_grp.attrs.get("molecular_charge", 0.0)),
                molecular_multiplicity=int(final_grp.attrs.get("molecular_multiplicity", 1)),
            )

            # Energies
            energies: List[float] = []
            if "energies" in opt_grp:
                energies = opt_grp["energies"][()].tolist()

            # Steps
            traj: List[QCSchemaAtomicResult] = []
            if "steps" in opt_grp:
                steps_grp = opt_grp["steps"]
                step_keys = sorted(steps_grp.keys())
                for sk in step_keys:
                    s_grp = steps_grp[sk]
                    s_name = str(s_grp.attrs.get("schema_name", "qcschema_output"))
                    s_ver = int(s_grp.attrs.get("schema_version", 1))
                    s_driver = str(s_grp.attrs.get("driver", "energy"))
                    s_method = str(s_grp.attrs.get("method", ""))
                    s_basis = s_grp.attrs.get("basis")
                    s_success = bool(s_grp.attrs.get("success", True))

                    if "return_result" in s_grp:
                        s_res_data = s_grp["return_result"][()]
                        s_return_result: Union[float, Any] = s_res_data.tolist() if isinstance(s_res_data, np.ndarray) else s_res_data
                    else:
                        s_raw_res = s_grp.attrs.get("return_result")
                        s_return_result = (
                            float(s_raw_res) if isinstance(s_raw_res, (int, float)) else json.loads(str(s_raw_res))
                        )

                    s_mol_grp = s_grp["molecule"]
                    s_syms = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in s_mol_grp["symbols"][()]]
                    s_geom = s_mol_grp["geometry"][()].tolist()
                    s_mol = QCSchemaMolecule(
                        symbols=s_syms,
                        geometry=s_geom,
                        molecular_charge=float(s_mol_grp.attrs.get("molecular_charge", 0.0)),
                        molecular_multiplicity=int(s_mol_grp.attrs.get("molecular_multiplicity", 1)),
                    )

                    s_prop_grp = s_grp.get("properties")
                    s_prop_kwargs: Dict[str, Any] = {}
                    if s_prop_grp is not None:
                        for pk, pv in s_prop_grp.attrs.items():
                            s_prop_kwargs[pk] = pv
                    s_props = QCSchemaProperties(**s_prop_kwargs)

                    s_wf: Optional[QCSchemaWavefunction] = None
                    if "wavefunction" in s_grp:
                        s_wf_grp = s_grp["wavefunction"]
                        s_wf_kwargs: Dict[str, Any] = {"basis": s_wf_grp.attrs.get("basis")}
                        for wname in ["orbitals_a", "orbitals_b", "occupations_a", "occupations_b", "density_a", "density_b", "fock_a", "fock_b"]:
                            if wname in s_wf_grp:
                                s_wf_kwargs[wname] = s_wf_grp[wname][()]
                        s_wf = QCSchemaWavefunction(**s_wf_kwargs)

                    traj.append(QCSchemaAtomicResult(
                        schema_name=s_name,
                        schema_version=s_ver,
                        molecule=s_mol,
                        driver=QCSchemaDriver(s_driver),
                        model=QCSchemaModel(method=s_method, basis=str(s_basis) if s_basis else None),
                        return_result=s_return_result,
                        properties=s_props,
                        wavefunction=s_wf,
                        success=s_success,
                    ))

            return QCSchemaOptimizationResult(
                schema_name=schema_name,
                schema_version=schema_version,
                initial_molecule=init_mol,
                final_molecule=final_mol,
                trajectory=traj,
                energies=energies,
                provenance=prov,
                success=success,
            )

    def list_trajectories(self) -> List[str]:
        """Lists all optimization trajectory IDs."""
        with self.transaction("r") as f:
            if "trajectories" in f:
                return list(f["trajectories"].keys())
            return []

    # -------------------------------------------------------------------------
    # Real-Time IPC & Streaming Delegates
    # -------------------------------------------------------------------------

    def stream_to_master(self, topic: str, payload: Any, binary_data: Optional[bytes] = None) -> int:
        """Streams a record to the master collector via the local scratch SQLite WAL queue."""
        return self.ipc_queue.push(topic=topic, payload=payload, binary_data=binary_data)

    def aggregate_ipc_stream(self, topic: Optional[str] = None, limit: int = 500) -> int:
        """Drains pending IPC records and serializes them into HDF5 on the master node."""
        aggregator = MasterDataAggregator(h5_path=self.h5_path, ipc_db_path=self.ipc_queue.db_path)
        return aggregator.aggregate_pending(topic=topic, limit=limit)

    def verify_file_integrity(self) -> Dict[str, Any]:
        """Verifies Fletcher32 checksums and mandatory filter compliance for all datasets in the file."""
        report: Dict[str, Any] = {
            "total_datasets": 0,
            "valid_datasets": 0,
            "filter_violations": [],
            "corrupted_datasets": [],
        }

        with self.transaction("r") as f:
            def visitor(name: str, obj: Any) -> None:
                if isinstance(obj, h5py.Dataset):
                    report["total_datasets"] += 1
                    valid_filters, details = verify_dataset_filters(obj)
                    if not valid_filters:
                        report["filter_violations"].append({"path": name, "details": details})
                    else:
                        try:
                            _ = obj[()]
                            report["valid_datasets"] += 1
                        except Exception as e:
                            report["corrupted_datasets"].append({"path": name, "error": str(e)})

            f.visititems(visitor)

        return report


# Backward-compatible alias
HDF5OntologyEnforcer = CoChemHDF5Manager
