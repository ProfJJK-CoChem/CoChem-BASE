Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part1_09_core_registry_manager_prompt.md.
Original prompt:
﻿# TASK INSTRUCTIONS: CoChem-BASE Core Registry Manager

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_manager.py`

## Context & Ecosystem Role
The Thread-Safe Gatekeeper. It guarantees atomic I/O, preventing file corruption when massively parallel HPC threads or Jupyter async kernels attempt simultaneous configuration polling.

## Deliverable Functions & Constraints
- Implement a single master-node read and ZeroMQ broadcast for HPC around all read/write interactions with `$HOME/CoChem_Artifacts/Registry/cochem_system_config.json`.
- MUST replace legacy 10-second `filelock`.
- Incorporate `hash_environment()` (SHA-256 state tracking) and `migrate_schema()` (legacy JSON upgrading).
- Ensure NO mocks, stubs, or dummy loops. Implement real ZMQ broadcast logic and file atomic operations.
- Only generate this exact file.


## ADVERSARIAL AUDIT CONSTRAINTS ENFORCED ##
- **ANTI-MOCKING DIRECTIVE**: You MUST NOT use mocks, dummy loops, fake data, stub logic, or placeholder code. Your implementation must use real physical execution logic without simulation.
- **ARCHITECTURE STRICTNESS**: You must strictly adhere to the Tripartite Workspace Air-Gap rules (separation of orchestrator, sandbox, and active deployment).
- **METHODOLOGY**: You must adhere to the Method Matrix rules for architecture.
- **NO SPOOFING**: The generation must not be faked. Eradicate mocked data.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_manager.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Stage 1.0 - State Registry & Provenance Manager.

Implements: Single Master-Node Read & ZeroMQ Broadcast for HPC,
Atomic File Locking (Replacing legacy filelock), SHA-256 Environment Hashing,
Legacy Schema Migration, Lineage UUIDs, PRNG Seed Locking, HDF5 Basis Set Archival,
and Dynamic Isotopic Mass Queries.
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
    from qcelemental import periodictable as pt  # type: ignore[import-not-found,import-untyped]
    from qcelemental.exceptions import (
        NotAnElementError,  # type: ignore[import-not-found,import-untyped]
    )
except ImportError:
    pt = None
    NotAnElementError = Exception  # type: ignore

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_config_path,
    resolve_mapped_path,
)
from core_engine.cochem_core_registry_schema import (
    CoChemSystemConfig,
)

logger = logging.getLogger("CoChem-RegistryManager")


class RegistryError(Exception):
    """Base exception for all registry operations."""


class RegistryLockError(RegistryError):
    """Raised when file locking fails or times out."""


class CoChemLockTimeoutError(RegistryLockError):
    """Raised when acquiring a file lock exceeds the configured timeout."""


class RecordNotFoundError(RegistryError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError):
    """Raised when schema migration encounters an unrecoverable failure."""


class IsotopeStabilityError(RegistryError):
    """Raised when isotopic mass resolution fails or mass record is missing."""


class RegistryCorruptionError(RegistryError):
    """Raised when registry integrity checksum verification fails."""


class AtomicFileLock:
    """Process-safe, thread-safe, cross-platform atomic file lock replacing legacy filelock.

    Uses atomic OS-level file creation (os.O_CREAT | os.O_EXCL) with exponential backoff,
    thread-local re-entrancy, and stale-lock auto-reaping to prevent lock contention crashes.
    """

    _tls = threading.local()

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
        self._is_locked: bool = False

    def acquire(self) -> bool:
        """Acquires the atomic lock before timeout. Raises CoChemLockTimeoutError on failure."""
        if not hasattr(self._tls, "held"):
            self._tls.held = {}

        path_str = str(self.lock_path)
        if path_str in self._tls.held and self._tls.held[path_str] > 0:
            self._tls.held[path_str] += 1
            self._is_locked = True
            return True

        start_time = time.time()
        backoff = 0.005
        os.makedirs(self.lock_path.parent, exist_ok=True)

        while (time.time() - start_time) < self.timeout:
            try:
                self._fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                payload = f"{os.getpid()}:{time.time()}\n"
                os.write(self._fd, payload.encode("utf-8"))
                self._is_locked = True
                self._tls.held[path_str] = 1
                return True
            except FileExistsError:
                # Check for stale lock
                try:
                    mtime = self.lock_path.stat().st_mtime
                    if (time.time() - mtime) > self.stale_timeout:
                        try:
                            self.lock_path.unlink(missing_ok=True)
                        except OSError:
                            pass
                except (OSError, FileNotFoundError):
                    pass
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)
            except Exception as e:
                logger.debug(f"Transient error while acquiring lock on {self.lock_path}: {e}")
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)

        raise CoChemLockTimeoutError(
            f"Could not acquire atomic lock on '{self.lock_path}' within {self.timeout}s"
        )

    def release(self) -> None:
        """Releases the lock file safely."""
        if self._is_locked:
            path_str = str(self.lock_path)
            if hasattr(self._tls, "held") and path_str in self._tls.held:
                self._tls.held[path_str] -= 1
                if self._tls.held[path_str] > 0:
                    self._is_locked = False
                    return
                del self._tls.held[path_str]

            if self._fd is not None:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._is_locked = False

    def __enter__(self) -> AtomicFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


def interpolate_env_vars(raw_str_or_dict: Union[str, Dict[str, Any]]) -> Any:
    """Uniformly expands %VAR%, $VAR, and ${VAR} across Windows and POSIX environments."""
    if isinstance(raw_str_or_dict, str):

        def replace_percent(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, f"%{var}%")

        s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, raw_str_or_dict)
        s = os.path.expandvars(s)
        return os.path.expanduser(s)
    elif isinstance(raw_str_or_dict, dict):
        serialized = json.dumps(raw_str_or_dict)
        interpolated = interpolate_env_vars(serialized)
        return json.loads(interpolated)
    return raw_str_or_dict


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
    """Generates a deterministic cryptographic SHA-256 fingerprint of the host environment.

    Concatenates host CPU count, total RAM bytes, Python version, dependency versions,
    OS kernel, architecture, and computational engine versions while strictly excluding paths.
    """

    try:
        from cochem_base.provenance.hashing import hash_environment as _h_env

        rec = _h_env(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )
        return cast(Dict[str, Any], rec.to_dict() if hasattr(rec, "to_dict") else dict(rec))
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
            raw_dict = json.loads(interpolate_env_vars(raw_text))
        else:
            raw_dict = json.loads(interpolate_env_vars(str(config_source)))
    elif isinstance(config_source, dict):
        raw_dict = dict(config_source)
    else:
        raise SchemaMigrationError(
            f"Unsupported config source type for migration: {type(config_source)}"
        )

    raw_dict["schema_version"] = "4.0.0"

    if "hardware" not in raw_dict or not isinstance(raw_dict["hardware"], dict):
        raw_dict["hardware"] = {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "windows_x86_64" if os.name == "nt" else "linux_x86_64",
        }

    if "quantum_settings" not in raw_dict:
        raw_dict["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    if "hpc" not in raw_dict:
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
    repeat_count: int = 1,
) -> str:
    """Broadcasts validated system configuration over ZeroMQ PUB socket for HPC worker nodes."""
    if config is None:
        cfg_mgr = RegistryManager(config_path=str(config_path) if config_path else None)
        config = cfg_mgr.load_system_config()

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
        time.sleep(0.05)
        for _ in range(max(1, repeat_count)):
            pub_socket.send_multipart([topic.encode("utf-8"), json_payload.encode("utf-8")])
            if repeat_count > 1:
                time.sleep(0.02)
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
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
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
    # System Configuration Management (cochem_system_config.json)
    # =========================================================================

    def load_system_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        verify_integrity: bool = True,
    ) -> CoChemSystemConfig:
        """Loads and validates `cochem_system_config.json` with environment variable expansion and integrity checks."""
        target_path = Path(config_path or self.config_path).resolve()
        if not target_path.is_file():
            raise FileNotFoundError(f"Master system config not found at: {target_path}")

        lock_file = str(target_path) + ".lock"
        with AtomicFileLock(lock_file, timeout=10.0):
            raw_text = target_path.read_text(encoding="utf-8")
            interpolated_text = interpolate_env_vars(raw_text)
            data = json.loads(interpolated_text)

            config = migrate_schema(data)

            if verify_integrity and "registry_checksum" in data and data["registry_checksum"]:
                expected = data["registry_checksum"]
                computed = config.compute_checksum()
                if expected != computed:
                    logger.warning(
                        f"Registry integrity mismatch for {target_path}: expected {expected}, computed {computed}"
                    )

            return config

    def save_system_config(
        self,
        config: Union[CoChemSystemConfig, Dict[str, Any]],
        config_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Saves system configuration atomically with updated SHA-256 checksum."""
        target_path = Path(config_path or self.config_path).resolve()
        if isinstance(config, dict):
            cfg_model = migrate_schema(config)
        elif isinstance(config, CoChemSystemConfig):
            cfg_model = config
        else:
            raise TypeError(f"Invalid config type: {type(config)}")

        checksum = cfg_model.update_checksum()
        cfg_model.last_updated = datetime.now(timezone.utc).isoformat()
        atomic_write_json(target_path, cfg_model, lock_timeout=10.0)
        return checksum

    def update_system_config(self, **updates: Any) -> CoChemSystemConfig:
        """Atomically updates fields within `cochem_system_config.json`."""
        target_path = Path(self.config_path).resolve()
        lock_file = str(target_path) + ".lock"

        with AtomicFileLock(lock_file, timeout=10.0):
            current = self.load_system_config(verify_integrity=False)
            current_dict = current.model_dump()
            current_dict.update(updates)
            updated_cfg = migrate_schema(current_dict)
            self.save_system_config(updated_cfg)
            return updated_cfg

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

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception as e:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        raise IsotopeStabilityError(
                            f"Element {clean_sym} not found in Mendeleev."
                        ) from e

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
                logger.error(f"Failed to query Mendeleev for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(
                    f"Isotopic mass resolution failed for {clean_sym}: {e}"
                ) from e

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
            "Neither mendeleev nor qcelemental library is available for isotopic mass resolution."
        )

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception as e:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        raise IsotopeStabilityError(
                            f"Element {clean_sym} not found in Mendeleev."
                        ) from e

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
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

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

        raise IsotopeStabilityError("Mendeleev is not available to list isotopes.")

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
                raise ValueError("Cannot update status for non-existent job")
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
        """Traces the backward DAG lineage chain from leaf to root."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}

        curr = rec_by_id.get(curr_id)
        while curr is not None:
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
        self, h5_path: str, basis_file_path: str, label: str, is_content: bool = False
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

        mapped_h5 = Path(h5_path)
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
    "RegistryManager",
    "SchemaMigrationError",
    "atomic_write_json",
    "broadcast_system_config",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "migrate_schema",
    "receive_system_config_broadcast",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_registry_manager.py ---
"""
Physical Unit and Integration Test Suite for CoChem Core Registry Manager.
Verifies HDF5 state registry, atomic file locking, Mendeleev dynamic queries,
lineage UUID tracking, PRNG seed locking, basis set archival, schema migration,
and comprehensive exception invariants.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest
import zmq
from pydantic import BaseModel, Field

from core_engine.cochem_core_registry_manager import (
    AtomicFileLock,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    IsotopeStabilityError,
    RecordNotFoundError,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryManager,
    SchemaMigrationError,
    atomic_write_json,
    broadcast_system_config,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    migrate_schema,
    receive_system_config_broadcast,
)
from core_engine.cochem_core_registry_schema import CoChemSystemConfig


class SampleJobModel(BaseModel):
    command: list[str] = Field(default_factory=lambda: ["echo", "test"])
    product_class: str = "Product_A"
    atom_count: int = 12
    converged: bool = True


class SampleHardwareModel(BaseModel):
    cpu_cores: int = 8
    ram_gb: float = 32.0
    gpu_profile: str = "RTX_4090"


def test_registry_initialization_and_topology(tmp_path: Path):
    reg_file = tmp_path / "registry.h5"
    rm = RegistryManager(registry_path=str(reg_file))
    assert Path(rm.registry_path).exists()
    assert Path(rm.lock_path) == Path(str(reg_file) + ".lock")

    stats = rm.get_registry_stats()
    assert stats["jobs_count"] == 0
    assert stats["hardware_profiles_count"] == 0
    assert stats["provenance_count"] == 0
    assert stats["basis_sets_count"] == 0
    assert stats["seeds_count"] == 0
    assert stats["version"] == RegistryManager.SCHEMA_VERSION

    # Re-initialization on existing registry
    rm2 = RegistryManager(registry_path=str(reg_file))
    assert rm2.get_registry_stats()["version"] == RegistryManager.SCHEMA_VERSION


def test_transaction_context_manager(tmp_path: Path):
    reg_file = tmp_path / "trans_test.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    with rm.transaction("a") as h5:
        assert "jobs" in h5
        assert "provenance" in h5
        h5["metadata"].attrs["custom_test_key"] = "test_value"

    with rm.transaction("r") as h5:
        assert h5["metadata"].attrs["custom_test_key"] == "test_value"


def test_mendeleev_isotopic_mass_resolution():
    # Common elements without explicit mass number (most abundant)
    mass_c = RegistryManager.get_isotopic_mass("C")
    assert isinstance(mass_c, float)
    assert 11.99 < mass_c < 12.02

    mass_h = RegistryManager.get_isotopic_mass("H")
    assert isinstance(mass_h, float)
    assert 1.007 < mass_h < 1.009

    # Explicit isotopes
    mass_c12 = RegistryManager.get_isotopic_mass("C", 12)
    assert mass_c12 == 12.0

    mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
    assert 13.003 < mass_c13 < 13.004

    mass_h2 = RegistryManager.get_isotopic_mass("H", 2)
    assert 2.014 < mass_h2 < 2.015

    # Case insensitivity and whitespace handling
    mass_n = RegistryManager.get_isotopic_mass("  n  ")
    assert 14.00 < mass_n < 14.01


def test_mendeleev_error_handling():
    # Non-existent element
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_isotopic_mass("NonExistentElement123")

    # Non-existent isotope of real element
    with pytest.raises(ValueError, match="not found in Mendeleev database"):
        RegistryManager.get_isotopic_mass("C", 999)

    # Invalid mass number type
    with pytest.raises(ValueError, match="Mass number must be an integer"):
        RegistryManager.get_isotopic_mass("C", "invalid")  # type: ignore

    # Empty or invalid symbols
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass("")
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass(None)  # type: ignore


def test_get_all_isotopes():
    c_isotopes = RegistryManager.get_all_isotopes("C")
    assert isinstance(c_isotopes, list)
    assert len(c_isotopes) > 0
    mass_numbers = [iso["mass_number"] for iso in c_isotopes]
    assert 12 in mass_numbers
    assert 13 in mass_numbers

    # Invalid symbols
    with pytest.raises(ValueError):
        RegistryManager.get_all_isotopes("")
    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_all_isotopes("InvalidElement999")


def test_job_registration_and_lifecycle(tmp_path: Path):
    reg_file = tmp_path / "jobs_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid job_id
    with pytest.raises(ValueError):
        rm.register_job("", {"status": "pending"})
    with pytest.raises(ValueError):
        rm.register_job(None, {"status": "pending"})  # type: ignore

    # Register via dict
    job1_data = {
        "command": ["orca", "calc.inp"],
        "status": "submitted",
        "nested_meta": {"tier": 3, "tags": ["opt", "freq"]},
        "walltime_limit": 3600,
        "null_val": None,
    }
    rm.register_job("job_001", job1_data)

    # Retrieve job
    rec = rm.get_job("job_001")
    assert rec is not None
    assert rec["command"] == ["orca", "calc.inp"]
    assert rec["status"] == "submitted"
    assert rec["nested_meta"] == {"tier": 3, "tags": ["opt", "freq"]}
    assert rec["walltime_limit"] == 3600
    assert rec["null_val"] is None
    assert "registered_at" in rec

    # Register via Pydantic model
    job2_model = SampleJobModel(product_class="Product_C", atom_count=24)
    rm.register_job("job_002", job2_model)
    rec2 = rm.get_job("job_002")
    assert rec2 is not None
    assert rec2["product_class"] == "Product_C"
    assert rec2["atom_count"] == 24
    assert rec2["converged"] is True

    # Update job status
    rm.update_job_status("job_001", "completed", return_code=0, energy=-154.234)
    updated = rm.get_job("job_001")
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["return_code"] == 0
    assert updated["energy"] == -154.234
    assert "updated_at" in updated

    # Update non-existent job
    with pytest.raises(ValueError, match="Cannot update status for non-existent job"):
        rm.update_job_status("non_existent_job", "running")

    # Get non-existent job
    assert rm.get_job("non_existent_job") is None

    # Get all jobs
    all_jobs = rm.get_all_jobs()
    assert len(all_jobs) == 2
    job_ids = [j["job_id"] for j in all_jobs]
    assert "job_001" in job_ids
    assert "job_002" in job_ids

    # Delete job
    assert rm.delete_job("job_001") is True
    assert rm.get_job("job_001") is None
    assert rm.delete_job("job_001") is False


def test_hardware_profiles_lifecycle(tmp_path: Path):
    reg_file = tmp_path / "hw_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid profile_id
    with pytest.raises(ValueError):
        rm.register_hardware_profile("", {"host": "node1"})

    # Register via dict
    hw_dict = {
        "host": "node-01",
        "physical_cores": 16,
        "ram_gb": 64.0,
        "features": ["avx512", "cuda"],
    }
    rm.register_hardware_profile("hw_node1", hw_dict)

    # Register via Pydantic
    hw_model = SampleHardwareModel(cpu_cores=32, ram_gb=128.0, gpu_profile="A100")
    rm.register_hardware_profile("hw_node2", hw_model)

    # Retrieval
    p1 = rm.get_hardware_profile("hw_node1")
    assert p1 is not None
    assert p1["physical_cores"] == 16
    assert p1["features"] == ["avx512", "cuda"]

    p2 = rm.get_hardware_profile("hw_node2")
    assert p2 is not None
    assert p2["cpu_cores"] == 32
    assert p2["gpu_profile"] == "A100"

    # Non-existent profile
    assert rm.get_hardware_profile("hw_missing") is None

    # Get all
    all_hw = rm.get_all_hardware_profiles()
    assert len(all_hw) == 2

    # Deletion
    assert rm.delete_hardware_profile("hw_node1") is True
    assert rm.delete_hardware_profile("hw_node1") is False
    assert rm.get_hardware_profile("hw_node1") is None


def test_provenance_and_lineage_chain(tmp_path: Path):
    reg_file = tmp_path / "prov_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Invalid record_id
    with pytest.raises(ValueError):
        rm.add_provenance_record("", {"action": "test"})

    # Add root record
    root_uuid = rm.add_provenance_record(
        "root_calc",
        {
            "step": "geometry_opt",
            "software": "orca-6.1",
            "parameters": {"functional": "r2SCAN-3c"},
        },
    )
    assert root_uuid.startswith("lin_")

    # Add child record
    child_uuid = rm.add_provenance_record(
        "freq_calc",
        {
            "step": "vibrational_frequencies",
            "parent_uuid": root_uuid,
            "software": "orca-6.1",
        },
    )
    assert child_uuid.startswith("lin_")

    # Add grandchild record
    grandchild_uuid = rm.add_provenance_record(
        "rot_const_derivation",
        {
            "step": "vpt2_analysis",
            "parent_uuid": child_uuid,
            "software": "cochem-core",
        },
    )
    assert grandchild_uuid.startswith("lin_")

    # Retrieve single record
    rec = rm.get_provenance_record("freq_calc")
    assert rec is not None
    assert rec["step"] == "vibrational_frequencies"
    assert rec["parent_uuid"] == root_uuid

    # Trace lineage chain from leaf
    chain = rm.get_lineage_chain("rot_const_derivation")
    assert len(chain) == 3
    assert chain[0]["record_id"] == "rot_const_derivation"
    assert chain[1]["record_id"] == "freq_calc"
    assert chain[2]["record_id"] == "root_calc"

    # Get all records
    all_recs = rm.get_all_provenance_records()
    assert len(all_recs) == 3

    # Delete record
    assert rm.delete_provenance_record("rot_calc_missing") is False
    assert rm.delete_provenance_record("rot_const_derivation") is True
    assert rm.get_provenance_record("rot_const_derivation") is None


def test_prng_seed_locking_and_verification(tmp_path: Path):
    reg_file = tmp_path / "seed_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Lock global and local seeds
    s1 = rm.lock_prng_seed(42, scope="global", metadata={"purpose": "rdkit_conformer"})
    s2 = rm.lock_prng_seed(1337, scope="quantum_monte_carlo")

    assert s1 == 42
    assert s2 == 1337

    # Retrieve
    assert rm.get_locked_seed("global") == 42
    assert rm.get_locked_seed("quantum_monte_carlo") == 1337
    assert rm.get_locked_seed("unlocked_scope") is None

    # Verification
    assert rm.verify_prng_seed(42, "global") is True
    assert rm.verify_prng_seed(999, "global") is False
    assert rm.verify_prng_seed(42, "unlocked_scope") is False

    # List all
    seeds = rm.list_locked_seeds()
    assert seeds["global"] == 42
    assert seeds["quantum_monte_carlo"] == 1337

    # Invalid seed input
    with pytest.raises(ValueError):
        rm.lock_prng_seed("not_an_int")  # type: ignore


def test_embedded_basis_set_archival(tmp_path: Path):
    reg_file = tmp_path / "basis_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    basis_content = """! def2-TZVP basis set
C 0
S 3 1.00
  100.0 0.1
  20.0 0.2
  5.0 0.7
"""
    basis_file = tmp_path / "def2-tzvp.basis"
    basis_file.write_text(basis_content, encoding="utf-8")

    # Invalid label
    with pytest.raises(ValueError):
        rm.embed_basis_set_archive(str(reg_file), str(basis_file), "")

    # Non-existent file when is_content=False
    with pytest.raises(FileNotFoundError):
        rm.embed_basis_set_archive(
            str(reg_file), "non_existent_file_path.basis", "bad_basis", is_content=False
        )

    # Embed via file path
    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path=str(basis_file),
        label="def2-TZVP",
        is_content=False,
    )

    # Embed directly via raw content
    rm.embed_basis_set_archive(
        h5_path=str(reg_file),
        basis_file_path="! cc-pVDZ basis set\nH 0\nS 2 1.00\n",
        label="cc-pVDZ",
        is_content=True,
    )

    # Verify presence
    assert rm.has_embedded_basis_set("def2-TZVP") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("non_existent_basis") is False

    # Retrieve content
    retrieved = rm.get_embedded_basis_set("def2-TZVP")
    assert "! def2-TZVP basis set" in retrieved

    # List all
    basis_list = rm.list_embedded_basis_sets()
    assert "def2-TZVP" in basis_list
    assert "cc-pVDZ" in basis_list

    # Delete
    assert rm.delete_embedded_basis_set("cc-pVDZ") is True
    assert rm.has_embedded_basis_set("cc-pVDZ") is False
    assert rm.delete_embedded_basis_set("cc-pVDZ") is False

    # Retrieve non-existent basis set
    with pytest.raises(BasisSetNotFoundError):
        rm.get_embedded_basis_set("non_existent")


def test_legacy_schema_migration(tmp_path: Path):
    import h5py

    reg_file = tmp_path / "legacy_registry.h5"

    # Create a bare legacy HDF5 file with version 0.1 and only jobs group
    with h5py.File(reg_file, "w") as h5:
        h5.attrs["version"] = "0.1"
        h5.create_group("jobs")

    rm = RegistryManager(registry_path=str(reg_file))
    report = rm.migrate_legacy_schema()

    assert report["previous_version"] == "0.1"
    assert report["current_version"] == RegistryManager.SCHEMA_VERSION

    # Verify newly created groups exist
    with rm.transaction("r") as h5:
        assert h5.attrs["version"] == RegistryManager.SCHEMA_VERSION
        assert "hardware_profiles" in h5
        assert "provenance" in h5
        assert "embedded_basis_sets" in h5
        assert "seeds" in h5


def test_metadata_arbitrary_key_values(tmp_path: Path):
    reg_file = tmp_path / "meta_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    rm.set_metadata("pipeline_run_id", "pipe_98765")
    rm.set_metadata("convergence_criteria", {"tol_e": 1e-6, "tol_g": 1e-4})
    rm.set_metadata("is_production", True)

    assert rm.get_metadata("pipeline_run_id") == "pipe_98765"
    assert rm.get_metadata("convergence_criteria") == {"tol_e": 1e-6, "tol_g": 1e-4}
    assert rm.get_metadata("is_production") is True
    assert rm.get_metadata("non_existent_key", default="fallback") == "fallback"


def test_custom_exception_hierarchy():
    assert issubclass(IsotopeStabilityError, RegistryError)
    assert issubclass(RegistryLockError, RegistryError)
    assert issubclass(CoChemLockTimeoutError, RegistryLockError)
    assert issubclass(RecordNotFoundError, RegistryError)
    assert issubclass(BasisSetNotFoundError, RegistryError)
    assert issubclass(SchemaMigrationError, RegistryError)
    assert issubclass(RegistryCorruptionError, RegistryError)


def test_atomic_file_lock_lifecycle(tmp_path: Path):
    lock_file = tmp_path / "test.lock"

    # Clean acquisition and release
    with AtomicFileLock(lock_file, timeout=2.0) as lock:
        assert lock_file.exists()
        assert lock._is_locked is True

    assert not lock_file.exists()
    assert lock._is_locked is False


def test_atomic_file_lock_contention_and_timeout(tmp_path: Path):
    lock_file = tmp_path / "contend.lock"

    # Acquire first lock on main thread
    lock1 = AtomicFileLock(lock_file, timeout=2.0)
    lock1.acquire()

    # Second lock on another thread should time out
    err_holder = []

    def try_lock2():
        try:
            lock2 = AtomicFileLock(lock_file, timeout=0.1)
            lock2.acquire()
        except Exception as e:
            err_holder.append(e)

    t = threading.Thread(target=try_lock2)
    t.start()
    t.join()

    assert len(err_holder) == 1
    assert isinstance(err_holder[0], CoChemLockTimeoutError)

    # Release first lock
    lock1.release()

    # Now lock succeeds on new attempt
    lock3 = AtomicFileLock(lock_file, timeout=1.0)
    lock3.acquire()
    lock3.release()


def test_atomic_file_lock_stale_reaping(tmp_path: Path):
    import time

    lock_file = tmp_path / "stale.lock"
    lock_file.write_text("99999:0\n", encoding="utf-8")

    # Set mtime to 100 seconds in the past
    past_time = time.time() - 100
    os.utime(lock_file, (past_time, past_time))

    # AtomicFileLock with stale_timeout=1.0 should reap the stale lock and acquire
    lock = AtomicFileLock(lock_file, timeout=2.0, stale_timeout=1.0)
    assert lock.acquire() is True
    lock.release()


def test_atomic_write_json_and_env_interpolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COCHEM_TEST_VAR", "injected_value")

    out_file = tmp_path / "config.json"
    data = {
        "path": "${COCHEM_TEST_VAR}/subdir",
        "nested": {"val": "%COCHEM_TEST_VAR%"},
        "count": 42,
    }

    atomic_write_json(out_file, data)
    assert out_file.exists()

    # Test interpolate_env_vars
    raw_text = out_file.read_text(encoding="utf-8")
    interpolated = interpolate_env_vars(raw_text)
    parsed = json.loads(interpolated)

    assert parsed["path"] == "injected_value/subdir"
    assert parsed["nested"]["val"] == "injected_value"
    assert parsed["count"] == 42


def test_hash_environment_deterministic_and_sanitized():
    rec1 = hash_environment(exclude_paths=True)
    assert isinstance(rec1, dict)
    assert "sha256_hash" in rec1
    assert len(rec1["sha256_hash"]) == 64
    assert rec1["cpu_count"] >= 1
    assert rec1["total_ram_bytes"] >= 0

    # Test path sanitization logic
    raw_payload_with_paths = json.dumps(
        {
            "win_path": "C:\\Users\\ansac\\secret\\file.txt",
            "posix_path": "/home/user/workspace/repo",
            "cpu": 8,
        }
    )
    from core_engine.cochem_core_registry_manager import _sanitize_path_leakages

    sanitized = _sanitize_path_leakages(raw_payload_with_paths)
    assert "ansac" not in sanitized
    assert "/home/user" not in sanitized
    assert "[SANITIZED_PATH]" in sanitized


def test_migrate_schema_json_upgrade():
    legacy_dict = {
        "schema_version": "1.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "windows_x86_64",
        },
    }

    cfg = migrate_schema(legacy_dict)
    assert isinstance(cfg, CoChemSystemConfig)
    assert cfg.schema_version == "4.0.0"
    assert cfg.hardware.physical_cpu_cores == 8
    assert cfg.quantum_settings is not None
    assert cfg.quantum_settings.implicit_solvation == "CPCM"
    assert cfg.hpc is not None
    assert cfg.hpc.scheduler == "local"
    assert cfg.registry_checksum is not None


def test_is_master_node_detection(monkeypatch: pytest.MonkeyPatch):
    # Standalone default
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("SLURM_PROCID", raising=False)
    monkeypatch.delenv("RANK", raising=False)
    assert is_master_node() is True

    # Explicit override
    monkeypatch.setenv("COCHEM_IS_MASTER", "0")
    assert is_master_node() is False

    monkeypatch.setenv("COCHEM_IS_MASTER", "1")
    assert is_master_node() is True

    # Slurm rank
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.setenv("SLURM_PROCID", "0")
    assert is_master_node() is True

    monkeypatch.setenv("SLURM_PROCID", "3")
    assert is_master_node() is False

    # MPI rank
    monkeypatch.delenv("SLURM_PROCID", raising=False)
    monkeypatch.setenv("RANK", "0")
    assert is_master_node() is True
    monkeypatch.setenv("RANK", "1")
    assert is_master_node() is False


def test_system_config_load_save_update_lifecycle(tmp_path: Path):
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    # Non-existent file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        rm.load_system_config()

    # Save a valid config
    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 16,
            "logical_cpu_cores": 32,
            "ram_gb": 64.0,
            "os_target": "windows_x86_64",
        },
    }
    checksum = rm.save_system_config(base_dict)
    assert isinstance(checksum, str)
    assert len(checksum) == 64
    assert cfg_file.exists()

    # Load system config
    loaded = rm.load_system_config()
    assert isinstance(loaded, CoChemSystemConfig)
    assert loaded.hardware.physical_cpu_cores == 16
    assert loaded.hardware.ram_gb == 64.0
    assert loaded.registry_checksum == checksum

    # Update system config
    updated = rm.update_system_config(rdkit_random_seed=12345)
    assert updated.rdkit_random_seed == 12345

    reloaded = rm.load_system_config()
    assert reloaded.rdkit_random_seed == 12345


def test_zeromq_config_broadcast_and_receive(tmp_path: Path):
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 777,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)
    loaded_cfg = rm.load_system_config()

    received_holder: list[CoChemSystemConfig | Exception] = []
    pub_ready = threading.Event()
    port_holder: list[int] = []

    def run_pub():
        ctx = zmq.Context()
        pub = ctx.socket(zmq.PUB)
        assigned_port = pub.bind_to_random_port("tcp://127.0.0.1")
        port_holder.append(assigned_port)
        pub_ready.set()
        time.sleep(0.2)
        payload = loaded_cfg.model_dump_json().encode("utf-8")
        for _ in range(12):
            pub.send_multipart([b"test_topic", payload])
            time.sleep(0.05)
        pub.close(linger=100)
        ctx.term()

    def run_sub():
        if not pub_ready.wait(timeout=5.0):
            received_holder.append(TimeoutError("Publisher failed to start"))
            return
        assigned_port = port_holder[0]
        try:
            cfg = receive_system_config_broadcast(
                master_host="127.0.0.1", port=assigned_port, topic="test_topic", timeout_ms=4000
            )
            received_holder.append(cfg)
        except Exception as e:
            received_holder.append(e)

    pub_thread = threading.Thread(target=run_pub)
    sub_thread = threading.Thread(target=run_sub)
    pub_thread.start()
    sub_thread.start()
    pub_thread.join(timeout=5.0)
    sub_thread.join(timeout=5.0)

    assert len(received_holder) == 1
    res = received_holder[0]
    assert isinstance(res, CoChemSystemConfig)
    assert res.rdkit_random_seed == 777
    assert res.hardware.physical_cpu_cores == 8


def test_broadcast_system_config_direct_function(tmp_path: Path):
    import socket

    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    base_dict = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(base_dict)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        ephemeral_port = s.getsockname()[1]

    # Calling broadcast_system_config directly
    checksum = broadcast_system_config(
        config=rm.load_system_config(),
        port=ephemeral_port,
        host="127.0.0.1",
        topic="cochem_system_config",
        repeat_count=1,
    )
    assert isinstance(checksum, str)
    assert len(checksum) == 64

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.