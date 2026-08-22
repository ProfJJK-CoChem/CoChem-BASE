#!/usr/bin/env python3
"""CoChem-CORE: Stage 0 Authority Rule & Master Registry Manager.

Provides thread-safe and process-safe atomic file locking, cryptographic SHA-256
checksum enforcement, dynamic environment variable interpolation, legacy schema migration,
active jobs lifecycle tracking, HDF5 state registry operations, lineage DAGs, PRNG seed locking,
embedded basis set archival, Mendeleev isotopic mass queries, and ZeroMQ config broadcast.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Union, cast

import h5py
import zmq
from pydantic import BaseModel

try:
    from mendeleev import element
except ImportError:
    element = None

try:
    from qcelemental import periodictable as pt  # type: ignore
except ImportError:
    pt = None

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_config_path,
    resolve_mapped_path,
)
from cochem_core_registry_schema import (
    CoChemSystemConfig,
)

logger = logging.getLogger("CoChem-RegistryManager")


# =============================================================================
# TYPED REGISTRY EXCEPTIONS
# =============================================================================

class RegistryError(Exception):
    """Base exception for all registry and state manager operations."""


class RegistryLockError(RegistryError):
    """Raised when atomic file locking fails."""


class CoChemLockTimeoutError(RegistryLockError, TimeoutError):
    """Raised when acquiring an atomic file lock exceeds the configured timeout."""


RegistryLockTimeoutError = CoChemLockTimeoutError


class RegistryMissingError(RegistryError, FileNotFoundError):
    """Stage 0 Guardrail: Raised when the master registry configuration file is missing."""


class RegistryCorruptionError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry integrity checksum verification fails."""


class RegistryParseError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry JSON is malformed or unparseable."""


class RecordNotFoundError(RegistryError, KeyError, ValueError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError, KeyError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError, ValueError):
    """Raised when schema migration encounters an unrecoverable failure."""


class IsotopeStabilityError(RegistryError):
    """Raised when isotopic mass resolution fails or mass record is missing."""


# =============================================================================
# ATOMIC FILE LOCKING
# =============================================================================

class AtomicFileLock:
    """Process-safe, thread-safe, cross-platform atomic file lock.

    Combines thread-level RLock serialization per canonical path with OS-level
    atomic file creation (os.O_CREAT | os.O_EXCL), exponential backoff,
    thread-local re-entrancy tracking, and stale-lock auto-reaping.
    """

    _tls = threading.local()
    _path_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_path_lock(cls, path_str: str) -> threading.RLock:
        with cls._meta_lock:
            if path_str not in cls._path_locks:
                cls._path_locks[path_str] = threading.RLock()
            return cls._path_locks[path_str]

    def __init__(
        self,
        lock_path: Union[str, Path],
        timeout: float = 10.0,
        stale_timeout: float = 60.0,
    ) -> None:
        self.lock_path = Path(lock_path).resolve()
        self.timeout = float(timeout)
        self.stale_timeout = float(stale_timeout)
        self._fd: Optional[int] = None
        self._depth: int = 0
        self._thread_lock_acquired: bool = False

    @property
    def _is_locked(self) -> bool:
        path_str = str(self.lock_path)
        if hasattr(self._tls, "held") and self._tls.held.get(path_str, 0) > 0:
            return True
        return self._depth > 0

    def acquire(self) -> bool:
        """Acquires the atomic lock before timeout. Raises CoChemLockTimeoutError on failure."""
        if not hasattr(self._tls, "held"):
            self._tls.held = {}
        if not hasattr(self._tls, "fds"):
            self._tls.fds = {}

        path_str = str(self.lock_path)

        # Thread-local re-entrancy
        if self._tls.held.get(path_str, 0) > 0:
            self._tls.held[path_str] += 1
            self._depth += 1
            return True

        start_time = time.time()
        thread_lock = self._get_path_lock(path_str)

        # 1. Acquire in-process thread lock
        remaining = max(0.001, self.timeout - (time.time() - start_time))
        if not thread_lock.acquire(timeout=remaining):
            raise CoChemLockTimeoutError(
                f"Could not acquire thread lock on '{self.lock_path}' within {self.timeout}s"
            )

        self._thread_lock_acquired = True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        backoff = 0.005

        # 2. Acquire OS-level file lock
        while (time.time() - start_time) < self.timeout:
            try:
                self._fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                payload = f"{os.getpid()}:{threading.get_ident()}:{time.time()}\n"
                os.write(self._fd, payload.encode("utf-8"))
                self._depth = 1
                self._tls.held[path_str] = 1
                self._tls.fds[path_str] = self._fd
                return True
            except FileExistsError:
                try:
                    mtime = self.lock_path.stat().st_mtime
                    if (time.time() - mtime) > self.stale_timeout:
                        try:
                            self.lock_path.unlink(missing_ok=True)
                            logger.info(f"Reaped stale lock file: {self.lock_path}")
                        except OSError:
                            pass
                except (OSError, FileNotFoundError):
                    pass
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)
            except PermissionError:
                # Windows handle collision during race
                try:
                    if self.lock_path.exists():
                        mtime = self.lock_path.stat().st_mtime
                        if (time.time() - mtime) > self.stale_timeout:
                            try:
                                self.lock_path.unlink(missing_ok=True)
                            except OSError:
                                pass
                except Exception:
                    pass
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)
            except Exception as e:
                logger.debug(f"Transient error acquiring lock on {self.lock_path}: {e}")
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)

        # Failed OS-level acquisition: release in-process thread lock
        self._thread_lock_acquired = False
        thread_lock.release()
        raise CoChemLockTimeoutError(
            f"Could not acquire atomic lock on '{self.lock_path}' within {self.timeout}s"
        )

    def release(self) -> None:
        """Releases the lock file safely."""
        path_str = str(self.lock_path)
        if not hasattr(self._tls, "held") or self._tls.held.get(path_str, 0) <= 0:
            if self._depth > 0:
                self._depth -= 1
            if self._thread_lock_acquired:
                self._thread_lock_acquired = False
                try:
                    self._get_path_lock(path_str).release()
                except RuntimeError:
                    pass
            return

        self._depth -= 1
        self._tls.held[path_str] -= 1
        if self._tls.held[path_str] > 0:
            return

        del self._tls.held[path_str]

        fd = None
        if hasattr(self._tls, "fds") and path_str in self._tls.fds:
            fd = self._tls.fds.pop(path_str)
        elif self._fd is not None:
            fd = self._fd
            self._fd = None

        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self._fd = None

        try:
            if self.lock_path.exists():
                self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass

        if self._thread_lock_acquired:
            self._thread_lock_acquired = False
            try:
                self._get_path_lock(path_str).release()
            except RuntimeError:
                pass

    def __enter__(self) -> AtomicFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# =============================================================================
# ENVIRONMENT VARIABLE INTERPOLATION & ATOMIC JSON WRITER
# =============================================================================

def interpolate_env_vars(raw_data: Any) -> Any:
    """Uniformly expands %VAR%, $VAR, ${VAR}, and ~ across Windows and POSIX environments.

    Supports string, dictionary, list, or primitive data structures.
    """
    if isinstance(raw_data, str):
        def replace_percent(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_braced(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_dollar(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, raw_data)
        s = re.sub(r"\$\{([A-Za-z0-9_]+)\}", replace_braced, s)
        s = re.sub(r"\$([A-Za-z0-9_]+)", replace_dollar, s)
        if s.startswith("~"):
            s = os.path.expanduser(s)
        return s
    elif isinstance(raw_data, dict):
        return {k: interpolate_env_vars(v) for k, v in raw_data.items()}
    elif isinstance(raw_data, list):
        return [interpolate_env_vars(item) for item in raw_data]
    return raw_data


def atomic_write_json(
    file_path: Union[str, Path],
    data: Union[Dict[str, Any], BaseModel, str],
    lock_timeout: float = 10.0,
) -> None:
    """Writes JSON data atomically via staging file and os.replace."""
    target = Path(file_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = str(target) + ".lock"

    if isinstance(data, BaseModel):
        content = data.model_dump_json(indent=2)
    elif isinstance(data, dict):
        content = json.dumps(data, indent=2)
    elif isinstance(data, str):
        content = data
    else:
        content = json.dumps(data, indent=2)

    with AtomicFileLock(lock_file, timeout=lock_timeout):
        temp_file = target.parent / f"{target.name}.tmp.{uuid.uuid4().hex}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, target)
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass


# =============================================================================
# ENVIRONMENT FINGERPRINTING & SCHEMA MIGRATION
# =============================================================================

def _sanitize_path_leakages(payload_str: str) -> str:
    """Sanitizes local absolute directory paths from serialized environment payloads."""
    p1 = r'[A-Za-z]:(?:\\\\|\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p1, "[SANITIZED_PATH]", payload_str)
    p2 = r'/(?:home|Users|root|tmp|var|opt|usr|etc|Volumes)/[^",}\]\r\n]*'
    sanitized = re.sub(p2, "[SANITIZED_PATH]", sanitized)
    p3 = r'(?:\\\\\\\\|//|\\\\)[^",}\]\r\n]*'
    sanitized = re.sub(p3, "[SANITIZED_PATH]", sanitized)
    p4 = r'(?:\\\\|/)?(?:Users|AppData|Documents|Desktop)(?:\\\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p4, "[SANITIZED_PATH]", sanitized)
    return sanitized


def hash_environment(
    exclude_paths: bool = True,
    tracked_packages: Optional[Sequence[str]] = None,
    tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generates a deterministic cryptographic SHA-256 fingerprint of the host environment."""
    try:
        from cochem_base.provenance.hashing import hash_environment as _h_env

        rec = _h_env(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )
        return cast(
            Dict[str, Any],
            rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__),
        )
    except Exception:
        py_ver = platform.python_version()
        py_impl = platform.python_implementation()
        os_sys = platform.system()
        os_rel = platform.release()
        os_arch = platform.machine()
        cpu_cnt = os.cpu_count() or 1
        total_ram = 0

        try:
            import psutil  # type: ignore[import-untyped]
            total_ram = psutil.virtual_memory().total
        except Exception:
            total_ram = 16 * 1024 * 1024 * 1024

        canonical_payload = {
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "os_architecture": os_arch,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "tracked_packages": list(tracked_packages or []),
            "tracked_engines": tracked_engines
            if isinstance(tracked_engines, dict)
            else list(tracked_engines or []),
        }

        serialized = json.dumps(canonical_payload, sort_keys=True)
        if exclude_paths:
            serialized = _sanitize_path_leakages(serialized)

        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return {
            "sha256_hash": sha256_hash,
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "metadata": {"os_architecture": os_arch},
        }


def migrate_schema(
    config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig],
) -> CoChemSystemConfig:
    """Upgrades legacy JSON schemas (0.1, 1.0.0, 2.0.0) to current target schema (4.0.0)."""
    if isinstance(config_source, CoChemSystemConfig):
        return config_source

    if isinstance(config_source, (str, Path)):
        p = Path(config_source)
        if p.is_file():
            raw_text = p.read_text(encoding="utf-8")
            raw_dict = json.loads(raw_text)
        else:
            raw_dict = json.loads(str(config_source))
    elif isinstance(config_source, dict):
        raw_dict = dict(config_source)
    else:
        raise SchemaMigrationError(
            f"Unsupported config source type for migration: {type(config_source)}"
        )

    raw_dict = interpolate_env_vars(raw_dict)
    raw_dict["schema_version"] = "4.0.0"

    if "quantum_settings" not in raw_dict or raw_dict["quantum_settings"] is None:
        raw_dict["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    if "hpc" not in raw_dict or raw_dict["hpc"] is None:
        raw_dict["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    try:
        cfg = CoChemSystemConfig.model_validate(raw_dict)
        cfg.update_checksum()
        return cfg
    except Exception as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e


# =============================================================================
# MASTER NODE & ZEROMQ BROADCAST
# =============================================================================

def is_master_node() -> bool:
    """Determines whether current execution process is the master node (Rank 0 / Standalone)."""
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


def broadcast_system_config(
    config: Optional[Union[CoChemSystemConfig, Dict[str, Any]]] = None,
    port: int = 5555,
    host: str = "0.0.0.0",
    topic: str = "cochem_system_config",
    config_path: Optional[Union[str, Path]] = None,
    repeat_count: int = 5,
    repeat_interval: float = 0.05,
    ready_event: Optional[threading.Event] = None,
) -> str:
    """Broadcasts validated system configuration over ZeroMQ PUB socket for HPC worker nodes."""
    if config is None:
        config = load_system_config(config_path)

    if isinstance(config, dict):
        validated_cfg = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        validated_cfg = config
    else:
        raise TypeError(f"Invalid config type for broadcast: {type(config)}")

    json_payload = validated_cfg.model_dump_json()

    ctx = zmq.Context.instance()
    pub_socket = ctx.socket(zmq.PUB)
    pub_socket.setsockopt(zmq.LINGER, 1000)
    try:
        pub_socket.bind(f"tcp://{host}:{port}")
        if ready_event is not None:
            ready_event.set()
        time.sleep(0.15)
        for _ in range(max(1, repeat_count)):
            pub_socket.send_multipart([topic.encode("utf-8"), json_payload.encode("utf-8")])
            time.sleep(repeat_interval)
    finally:
        pub_socket.close()

    return validated_cfg.compute_checksum()


def receive_system_config_broadcast(
    master_host: str = "127.0.0.1",
    port: int = 5555,
    topic: str = "cochem_system_config",
    timeout_ms: int = 5000,
) -> CoChemSystemConfig:
    """Receives system configuration from master ZeroMQ broadcast."""
    ctx = zmq.Context.instance()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.setsockopt(zmq.LINGER, 0)
    try:
        sub_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sub_socket.connect(f"tcp://{master_host}:{port}")
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        time.sleep(0.05)
        parts = sub_socket.recv_multipart()
        json_str = parts[1].decode("utf-8")
        return CoChemSystemConfig.model_validate_json(json_str)
    except zmq.error.Again as e:
        raise TimeoutError(
            f"ZeroMQ config broadcast timed out after {timeout_ms}ms from {master_host}:{port}"
        ) from e
    finally:
        sub_socket.close()


# =============================================================================
# SYSTEM CONFIGURATION I/O & STAGE 0 GUARDRAILS
# =============================================================================

def get_default_config_path() -> Path:
    """Resolves the default system configuration file path."""
    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path
        return resolve_config_path()
    except Exception:
        return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


def load_system_config(
    config_path: Optional[Union[str, Path]] = None,
    verify_integrity: bool = True,
) -> CoChemSystemConfig:
    """Loads and validates cochem_system_config.json with environment variable expansion and integrity checks.

    Enforces Stage 0 Guardrail:
    - If file is missing, logs violation and raises RegistryMissingError.
    - If JSON is malformed, logs violation and raises RegistryParseError.
    - If checksum verification fails, logs violation and raises RegistryCorruptionError.
    """
    target_path = Path(config_path or get_default_config_path()).resolve()
    if not target_path.is_file():
        logger.critical(f"Stage 0 Guardrail: Master registry not found at: {target_path}")
        raise RegistryMissingError(f"Stage 0 Guardrail: Master registry not found at '{target_path}'")

    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        try:
            raw_text = target_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.critical(f"Stage 0 Guardrail: Failed to read registry at {target_path}: {e}")
            raise RegistryMissingError(f"Stage 0 Guardrail: Failed to read registry at '{target_path}': {e}") from e

        try:
            parsed_json = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical(f"Stage 0 Guardrail: Malformed registry JSON at {target_path}: {e}")
            raise RegistryParseError(f"Stage 0 Guardrail: Unparseable registry JSON at '{target_path}': {e}") from e

        if not isinstance(parsed_json, dict):
            logger.critical(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__} at {target_path}"
            )
            raise RegistryParseError(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__}"
            )

        interpolated_dict = interpolate_env_vars(parsed_json)

        try:
            config = migrate_schema(interpolated_dict)
        except Exception as e:
            logger.critical(f"Stage 0 Guardrail: Schema validation error for {target_path}: {e}")
            raise SchemaMigrationError(f"Stage 0 Guardrail: Schema validation error for '{target_path}': {e}") from e

        if verify_integrity and "registry_checksum" in parsed_json and parsed_json["registry_checksum"]:
            expected = parsed_json["registry_checksum"]
            computed = config.compute_checksum()
            if expected != computed:
                logger.critical(
                    f"Stage 0 Guardrail: Registry corruption at {target_path} (expected checksum '{expected}', computed '{computed}')"
                )
                raise RegistryCorruptionError(
                    f"Stage 0 Guardrail: Registry corruption at '{target_path}' (expected '{expected}', computed '{computed}')"
                )

        return config


def save_system_config(
    config: Union[CoChemSystemConfig, Dict[str, Any]],
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Saves system configuration atomically with updated SHA-256 checksum."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    if isinstance(config, dict):
        cfg_model = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        cfg_model = config
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    cfg_model.last_updated = datetime.now(timezone.utc).isoformat()
    checksum = cfg_model.update_checksum()
    atomic_write_json(target_path, cfg_model, lock_timeout=10.0)
    return checksum


def update_system_config(
    config_path: Optional[Union[str, Path]] = None,
    **updates: Any,
) -> CoChemSystemConfig:
    """Atomically updates fields within cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    with AtomicFileLock(lock_file, timeout=10.0):
        current = load_system_config(target_path, verify_integrity=False)
        current_dict = current.model_dump()
        current_dict.update(updates)
        updated_cfg = migrate_schema(current_dict)
        save_system_config(updated_cfg, target_path)
        return updated_cfg


# =============================================================================
# ACTIVE JOBS LIFECYCLE MANAGEMENT
# =============================================================================

def register_active_job(
    job_id: str,
    job_data: Union[Dict[str, Any], BaseModel],
    config_path: Optional[Union[str, Path]] = None,
) -> None:
    """Registers an active execution job into cochem_system_config.json under active_jobs."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")

    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
    if "registered_at" not in payload:
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()

    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        cfg.active_jobs[job_id] = payload
        save_system_config(cfg, target_path)


def get_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves an active job record from cochem_system_config.json, or None if not found."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return None
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return cfg.active_jobs.get(job_id)


def list_active_jobs(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Returns all active jobs recorded in cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return dict(cfg.active_jobs)


def remove_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Removes an active job from cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return False
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id in cfg.active_jobs:
            del cfg.active_jobs[job_id]
            save_system_config(cfg, target_path)
            return True
        return False


def update_active_job(
    job_id: str,
    status: str,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Updates status and additional fields of an active job in cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id not in cfg.active_jobs:
            raise RecordNotFoundError(f"Cannot update non-existent active job '{job_id}'")
        job_record = dict(cfg.active_jobs[job_id])
        job_record["status"] = status
        job_record.update(kwargs)
        job_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        cfg.active_jobs[job_id] = job_record
        save_system_config(cfg, target_path)
        return job_record


# =============================================================================
# MASTER REGISTRY MANAGER CLASS
# =============================================================================

class RegistryManager:
    """Consolidated state registry manager using HDF5, Atomic File Locks, and ZeroMQ Broadcasts."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self, config_path: Optional[str] = None, registry_path: Optional[str] = None
    ) -> None:
        if config_path:
            self.config_path = str(resolve_config_path(Path(config_path)))
        else:
            self.config_path = str(resolve_config_path())

        if registry_path:
            self.registry_path = str(
                resolve_mapped_path(registry_path, get_artifact_dir() / "Registry")
            )
        else:
            self.registry_path = str(get_artifact_dir() / "Registry" / "cochem_registry.h5")

        self.lock_path = self.registry_path + ".lock"
        self._ensure_registry_exists()

    def _ensure_registry_exists(self) -> None:
        """Ensure the HDF5 registry file and required groups exist, with atomic locking."""
        try:
            Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
            with AtomicFileLock(self.lock_path, timeout=10.0):
                if not os.path.exists(self.registry_path):
                    with h5py.File(self.registry_path, "w") as h5:
                        h5.attrs["created"] = datetime.now(timezone.utc).isoformat()
                        h5.attrs["version"] = self.SCHEMA_VERSION
                        h5.create_group("jobs")
                        h5.create_group("hardware_profiles")
                        h5.create_group("basis_sets")
                        h5.create_group("embedded_basis_sets")
                        h5.create_group("provenance")
                        h5.create_group("seeds")
                        h5.create_group("metadata")
                    logger.info(f"Created new registry file: {self.registry_path}")
                else:
                    with h5py.File(self.registry_path, "a") as h5:
                        if "version" not in h5.attrs:
                            h5.attrs["version"] = self.SCHEMA_VERSION
                        for grp in [
                            "jobs",
                            "hardware_profiles",
                            "basis_sets",
                            "embedded_basis_sets",
                            "provenance",
                            "seeds",
                            "metadata",
                        ]:
                            if grp not in h5:
                                h5.create_group(grp)
        except Exception as e:
            logger.error(f"Failed to initialize registry: {e}")
            raise RuntimeError(f"Registry initialization failed: {e}") from e

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic transaction over the HDF5 registry using AtomicFileLock."""
        with AtomicFileLock(self.lock_path, timeout=10.0):
            with h5py.File(self.registry_path, mode) as h5:
                yield h5

    def get_registry_stats(self) -> Dict[str, Any]:
        """Returns statistics on active registry record groups."""
        with self.transaction("r") as h5:
            jobs_c = len(h5["jobs"]) if "jobs" in h5 else 0
            hw_c = len(h5["hardware_profiles"]) if "hardware_profiles" in h5 else 0
            prov_c = len(h5["provenance"]) if "provenance" in h5 else 0
            basis_c = (
                len(h5["embedded_basis_sets"])
                if "embedded_basis_sets" in h5
                else (len(h5["basis_sets"]) if "basis_sets" in h5 else 0)
            )
            seeds_c = len(h5["seeds"]) if "seeds" in h5 else 0
            ver = h5.attrs.get("version", self.SCHEMA_VERSION)
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8")
            return {
                "jobs_count": jobs_c,
                "hardware_profiles_count": hw_c,
                "provenance_count": prov_c,
                "basis_sets_count": basis_c,
                "seeds_count": seeds_c,
                "version": str(ver),
            }

    # =========================================================================
    # System Configuration Delegates
    # =========================================================================

    def load_system_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        verify_integrity: bool = True,
    ) -> CoChemSystemConfig:
        """Loads system configuration using the authoritative Stage 0 loader."""
        return load_system_config(config_path or self.config_path, verify_integrity=verify_integrity)

    def save_system_config(
        self,
        config: Union[CoChemSystemConfig, Dict[str, Any]],
        config_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Saves system configuration atomically with updated SHA-256 checksum."""
        return save_system_config(config, config_path or self.config_path)

    def update_system_config(self, **updates: Any) -> CoChemSystemConfig:
        """Atomically updates fields within cochem_system_config.json."""
        return update_system_config(config_path=self.config_path, **updates)

    def register_active_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers an active execution job in cochem_system_config.json."""
        register_active_job(job_id, job_data, config_path=self.config_path)

    def get_active_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an active execution job from cochem_system_config.json."""
        return get_active_job(job_id, config_path=self.config_path)

    def list_active_jobs(self) -> Dict[str, Any]:
        """Lists all active execution jobs in cochem_system_config.json."""
        return list_active_jobs(config_path=self.config_path)

    def remove_active_job(self, job_id: str) -> bool:
        """Removes an active execution job from cochem_system_config.json."""
        return remove_active_job(job_id, config_path=self.config_path)

    def update_active_job(self, job_id: str, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Updates an active execution job in cochem_system_config.json."""
        return update_active_job(job_id, status, config_path=self.config_path, **kwargs)

    def poll_system_config(
        self,
        master_host: str = "127.0.0.1",
        zmq_port: int = 5555,
        timeout_ms: int = 2000,
    ) -> CoChemSystemConfig:
        """Polls configuration: Master reads disk directly; Worker receives ZMQ broadcast with disk fallback."""
        if is_master_node():
            return self.load_system_config()
        try:
            return receive_system_config_broadcast(
                master_host=master_host, port=zmq_port, timeout_ms=timeout_ms
            )
        except Exception as e:
            logger.debug(f"Worker ZMQ poll failed, falling back to disk read: {e}")
            return self.load_system_config()

    def broadcast_config(
        self,
        port: int = 5555,
        host: str = "0.0.0.0",
        topic: str = "cochem_system_config",
    ) -> str:
        """Broadcasts current configuration via ZeroMQ."""
        cfg = self.load_system_config(verify_integrity=False)
        return broadcast_system_config(cfg, port=port, host=host, topic=topic)

    def receive_config_broadcast(
        self,
        master_host: str = "127.0.0.1",
        port: int = 5555,
        topic: str = "cochem_system_config",
        timeout_ms: int = 5000,
    ) -> CoChemSystemConfig:
        """Subscribes and receives configuration broadcast via ZeroMQ."""
        return receive_system_config_broadcast(
            master_host=master_host, port=port, topic=topic, timeout_ms=timeout_ms
        )

    def hash_environment(
        self,
        exclude_paths: bool = True,
        tracked_packages: Optional[Sequence[str]] = None,
        tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Calculates environmental hash for state tracking."""
        return hash_environment(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )

    def migrate_schema(
        self, config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig]
    ) -> CoChemSystemConfig:
        """Migrates schema to 4.0.0."""
        return migrate_schema(config_source)

    # =========================================================================
    # Isotopic Mass & Mendeleev/QCElemental Queries
    # =========================================================================

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """Dynamically fetches exact isotopic masses via Mendeleev, QCElemental, or periodic tables."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if mass_number is not None and not isinstance(mass_number, int):
            raise ValueError("Mass number must be an integer.")

        if clean_sym.upper() == "D":
            if mass_number is not None and mass_number != 2:
                raise ValueError(f"Isotope {mass_number}D not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            if mass_number is not None and mass_number != 3:
                raise ValueError(f"Isotope {mass_number}T not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 3

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    if mass_number is not None:
                        for iso in elem.isotopes:
                            if iso.mass_number == mass_number:
                                if iso.mass is None:
                                    raise IsotopeStabilityError(
                                        f"Isotope {mass_number}{clean_sym} has no stable mass record in Mendeleev."
                                    )
                                return float(iso.mass)
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        )

                    if hasattr(elem, "mass") and elem.mass is not None:
                        return float(elem.mass)
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} lacks a valid default atomic mass binding."
                    )
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.debug(f"Mendeleev query failed for '{clean_sym}', attempting fallback: {e}")

        if pt is not None:
            try:
                if mass_number is not None:
                    target = f"{formatted_sym}{mass_number}"
                    try:
                        return float(pt.to_mass(target))
                    except Exception as e:
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        ) from e
                try:
                    return float(pt.to_mass(formatted_sym))
                except Exception as e:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from e
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.error(f"Failed to query QCElemental for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(
                    f"Isotopic mass resolution failed for {clean_sym}: {e}"
                ) from e

        raise IsotopeStabilityError(
            f"Element {clean_sym} not found in Mendeleev or QCElemental database."
        )

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if clean_sym.upper() in ("D", "T"):
            clean_sym = "H"
            formatted_sym = "H"

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    isotopes = []
                    for iso in elem.isotopes:
                        isotopes.append(
                            {
                                "mass_number": int(iso.mass_number),
                                "mass": float(iso.mass) if iso.mass is not None else None,
                                "abundance": float(iso.abundance)
                                if getattr(iso, "abundance", None) is not None
                                else None,
                            }
                        )
                    return isotopes
            except Exception as e:
                logger.debug(f"Mendeleev isotopes query failed for '{clean_sym}': {e}")

        if pt is not None:
            try:
                isotopes = []
                try:
                    pt.to_mass(formatted_sym)
                except Exception as err:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from err

                pattern = re.compile(rf"^{formatted_sym}(\d+)$")
                if hasattr(pt, "_eliso2mass"):
                    for k, m in pt._eliso2mass.items():
                        mat = pattern.match(k)
                        if mat:
                            isotopes.append(
                                {
                                    "mass_number": int(mat.group(1)),
                                    "mass": float(m),
                                    "abundance": None,
                                }
                            )
                return sorted(isotopes, key=lambda x: x["mass_number"])
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev or QCElemental.")

    # =========================================================================
    # HDF5 Registry Operations
    # =========================================================================

    def register_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers a calculation job record in the HDF5 registry."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job ID must be a non-empty string.")

        payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
        if "registered_at" not in payload:
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id in jobs_grp:
                del jobs_grp[job_id]
            dset = jobs_grp.create_dataset(
                job_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )
            dset.attrs["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered job record, or None if not found."""
        with self.transaction("r") as h5:
            if "jobs" not in h5 or job_id not in h5["jobs"]:
                return None
            val = h5["jobs"][job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def update_job_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Updates the status and additional fields of an existing job record."""
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id not in jobs_grp:
                raise RecordNotFoundError(f"Cannot update status for non-existent job '{job_id}'")
            val = jobs_grp[job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            rec = json.loads(text)
            rec["status"] = status
            rec.update(kwargs)
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            del jobs_grp[job_id]
            jobs_grp.create_dataset(
                job_id, data=json.dumps(rec), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Returns all registered jobs with job_id included."""
        results = []
        with self.transaction("r") as h5:
            if "jobs" in h5:
                for k in h5["jobs"].keys():
                    val = h5["jobs"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["job_id"] = k
                    results.append(data)
        return results

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the registry."""
        with self.transaction("a") as h5:
            if "jobs" in h5 and job_id in h5["jobs"]:
                del h5["jobs"][job_id]
                return True
            return False

    def register_hardware_profile(
        self, profile_id: str, profile_data: Union[Dict[str, Any], BaseModel]
    ) -> None:
        """Registers a host/node hardware configuration profile."""
        if not profile_id or not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile ID must be a non-empty string.")

        payload = (
            profile_data.model_dump() if isinstance(profile_data, BaseModel) else dict(profile_data)
        )
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(payload)

        with self.transaction("a") as h5:
            hw_grp = h5["hardware_profiles"]
            if profile_id in hw_grp:
                del hw_grp[profile_id]
            hw_grp.create_dataset(
                profile_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_hardware_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered hardware profile by ID."""
        with self.transaction("r") as h5:
            if "hardware_profiles" not in h5 or profile_id not in h5["hardware_profiles"]:
                return None
            val = h5["hardware_profiles"][profile_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_all_hardware_profiles(self) -> List[Dict[str, Any]]:
        """Returns all hardware profiles."""
        results = []
        with self.transaction("r") as h5:
            if "hardware_profiles" in h5:
                for k in h5["hardware_profiles"].keys():
                    val = h5["hardware_profiles"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["profile_id"] = k
                    results.append(data)
        return results

    def delete_hardware_profile(self, profile_id: str) -> bool:
        """Deletes a hardware profile from the registry."""
        with self.transaction("a") as h5:
            if "hardware_profiles" in h5 and profile_id in h5["hardware_profiles"]:
                del h5["hardware_profiles"][profile_id]
                return True
            return False

    def add_provenance_record(self, record_id: str, record_data: Dict[str, Any]) -> str:
        """Adds a cryptographic/workflow provenance record and returns a unique lineage UUID."""
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string.")

        lineage_uuid = f"lin_{uuid.uuid4().hex}"
        payload = dict(record_data)
        payload["record_id"] = record_id
        payload["lineage_uuid"] = lineage_uuid
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            prov_grp = h5["provenance"]
            if record_id in prov_grp:
                del prov_grp[record_id]
            prov_grp.create_dataset(
                record_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

        return lineage_uuid

    def get_provenance_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a provenance record by ID."""
        with self.transaction("r") as h5:
            if "provenance" not in h5 or record_id not in h5["provenance"]:
                return None
            val = h5["provenance"][record_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_lineage_chain(self, leaf_record_id: str) -> List[Dict[str, Any]]:
        """Traces the backward DAG lineage chain from leaf to root with cycle protection."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}
        visited = set()

        curr = rec_by_id.get(curr_id)
        while curr is not None:
            curr_uuid = curr.get("lineage_uuid")
            if curr_uuid in visited:
                logger.warning(f"Provenance cycle detected at record {curr_id}")
                break
            if curr_uuid:
                visited.add(curr_uuid)
            chain.append(curr)
            parent_uuid = curr.get("parent_uuid")
            if not parent_uuid or parent_uuid not in all_prov:
                break
            curr = all_prov.get(parent_uuid)

        return chain

    def get_all_provenance_records(self) -> List[Dict[str, Any]]:
        """Returns all provenance records."""
        results = []
        with self.transaction("r") as h5:
            if "provenance" in h5:
                for k in h5["provenance"].keys():
                    val = h5["provenance"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    results.append(data)
        return results

    def delete_provenance_record(self, record_id: str) -> bool:
        """Deletes a provenance record."""
        with self.transaction("a") as h5:
            if "provenance" in h5 and record_id in h5["provenance"]:
                del h5["provenance"][record_id]
                return True
            return False

    def lock_prng_seed(
        self, seed: int, scope: str = "global", metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Locks a pseudorandom number generator seed into the registry."""
        if not isinstance(seed, int):
            raise ValueError("PRNG seed must be an integer.")

        payload = {
            "seed": seed,
            "scope": scope,
            "metadata": metadata or {},
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.transaction("a") as h5:
            seeds_grp = h5["seeds"]
            if scope in seeds_grp:
                del seeds_grp[scope]
            seeds_grp.create_dataset(
                scope, data=json.dumps(payload), dtype=h5py.string_dtype(encoding="utf-8")
            )

        return seed

    def get_locked_seed(self, scope: str = "global") -> Optional[int]:
        """Retrieves a locked PRNG seed for a given scope."""
        with self.transaction("r") as h5:
            if "seeds" not in h5 or scope not in h5["seeds"]:
                return None
            val = h5["seeds"][scope][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[int], json.loads(text).get("seed"))

    def verify_prng_seed(self, seed: int, scope: str = "global") -> bool:
        """Verifies if an active seed matches the registered locked seed for a scope."""
        locked = self.get_locked_seed(scope)
        return locked is not None and locked == seed

    def list_locked_seeds(self) -> Dict[str, int]:
        """Returns all locked seeds mapped by scope."""
        res = {}
        with self.transaction("r") as h5:
            if "seeds" in h5:
                for k in h5["seeds"].keys():
                    val = h5["seeds"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    res[k] = json.loads(text).get("seed")
        return res

    def embed_basis_set_archive(
        self,
        h5_path: Optional[str] = None,
        basis_file_path: str = "",
        label: str = "",
        is_content: bool = False,
    ) -> None:
        """Embeds full basis set text into the HDF5 archive to prevent link rot."""
        if not label or not isinstance(label, str) or not label.strip():
            raise ValueError("Basis set label must be a non-empty string.")

        clean_label = label.strip()

        if is_content:
            raw_text = basis_file_path
        else:
            p = Path(basis_file_path)
            if not p.is_file():
                raise FileNotFoundError(f"Basis set file not found: {p}")
            raw_text = p.read_text(encoding="utf-8")

        mapped_h5 = Path(h5_path or self.registry_path)
        with AtomicFileLock(str(mapped_h5) + ".lock", timeout=10.0):
            with h5py.File(mapped_h5, "a") as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")
                grp = h5["embedded_basis_sets"]
                if clean_label in grp:
                    del grp[clean_label]
                grp.create_dataset(
                    clean_label, data=raw_text, dtype=h5py.string_dtype(encoding="utf-8")
                )

    def has_embedded_basis_set(self, label: str) -> bool:
        """Checks if a basis set label exists in the registry."""
        with self.transaction("r") as h5:
            return "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]

    def get_embedded_basis_set(self, label: str) -> str:
        """Retrieves embedded basis set content."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" not in h5 or label not in h5["embedded_basis_sets"]:
                raise BasisSetNotFoundError(f"Basis set '{label}' not found in registry.")
            val = h5["embedded_basis_sets"][label][()]
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

    def list_embedded_basis_sets(self) -> List[str]:
        """Lists all embedded basis set labels."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" in h5:
                return list(h5["embedded_basis_sets"].keys())
            return []

    def delete_embedded_basis_set(self, label: str) -> bool:
        """Deletes an embedded basis set."""
        with self.transaction("a") as h5:
            if "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]:
                del h5["embedded_basis_sets"][label]
                return True
            return False

    def migrate_legacy_schema(self) -> Dict[str, Any]:
        """Upgrades legacy HDF5 schema files to 1.0.0."""
        with self.transaction("a") as h5:
            prev_ver = h5.attrs.get("version", "0.1")
            if isinstance(prev_ver, bytes):
                prev_ver = prev_ver.decode("utf-8")

            h5.attrs["version"] = self.SCHEMA_VERSION
            h5.attrs["migrated_at"] = datetime.now(timezone.utc).isoformat()

            for grp in [
                "hardware_profiles",
                "basis_sets",
                "embedded_basis_sets",
                "provenance",
                "seeds",
                "metadata",
            ]:
                if grp not in h5:
                    h5.create_group(grp)

            return {
                "previous_version": str(prev_ver),
                "current_version": self.SCHEMA_VERSION,
                "status": "migrated",
            }

    def set_metadata(self, key: str, value: Any) -> None:
        """Sets arbitrary metadata key/value into the registry."""
        with self.transaction("a") as h5:
            meta_grp = h5["metadata"]
            if key in meta_grp:
                del meta_grp[key]
            meta_grp.create_dataset(
                key, data=json.dumps(value), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieves arbitrary metadata value."""
        with self.transaction("r") as h5:
            if "metadata" not in h5 or key not in h5["metadata"]:
                return default
            val = h5["metadata"][key][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)


__all__ = [
    "AtomicFileLock",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "IsotopeStabilityError",
    "RecordNotFoundError",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "atomic_write_json",
    "broadcast_system_config",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
]
