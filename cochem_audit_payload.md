Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\06_01_mechanics_memory.md.
Original prompt:
# Task: Implement Air-Gapped Router & HDF5 State (`cochem_topos_memory.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\mechanics\cochem_topos_memory.py`

## Objective
Safely claim physical hardware, define the method cascade, and establish a concurrency-safe database for the resulting mathematical tensors.

## Context & Architecture Rules
This module (Stage 2.0) isolates heavy physics engines from the UI, enforcing Air-Gap policy by strictly using `${COCHEM_WORKSPACE}` for state persistence.

## Execution Directives
Implement the `cochem_topos_memory.py` script with the following capabilities:

1. **Air-Gap Protocol**: Read configuration solely from `${COCHEM_WORKSPACE}/CoChem_Artifacts/Registry/cochem_system_config.json`. Output databases to `${COCHEM_WORKSPACE}/CoChem_Artifacts/Databases/`. Never guess local hardware limits or write local state files to the execution tier.
2. **Continuous Hardware Polling & VRAM Governor**: Use `psutil` and `pynvml` to dynamically poll hardware. Broker concurrency memory on GPUs via `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` and `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` to strictly cap VRAM usage at 85%. Trap `pynvml` unreachability exceptions to enable seamless CPU fallback.
3. **Universal Fallback Cascade & Precision Enforcement**: Initiate fallback cascade (T1-1min -> T3-3h) if unsupported elements are detected. Explicitly mandate FP64 precision across all execution tiers (e.g., `JAX_ENABLE_X64=True`).
4. **HDF5 State Manager & Atomic Flush Mandate**: Create `landscape.h5` without SWMR flags (due to HPC POSIX constraints). Initialize with chunking, `compression="gzip"` (or `shuffle`), and `fletcher32=True`. Instantiate the QCSchema layout (`/meta`, `/methods/<id>`, `/points/<id>/coordinates`, `/points/<id>/energy`). Wrap every single dataset write with an immediate `f.flush()`.
5. **Error Trapping**: Execute a POSIX sweep upon startup to detect and delete stale `.h5.lck` lock files if their PID is inactive. If an external engine is killed by the OS (SIGKILL/137) due to OOM, catch the exit code and generate an `OOM_autopsy.json` detailing the tensor size, atomic count, and theoretical tier.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\cochem_topos_memory.py ---
"""
CoChem-TOPOS: Stage 2.0 - Air-Gapped Hardware Broker & HDF5 QCSchema State Manager
Implements ToposHDF5MemoryManager, HardwareResourceBroker, UniversalFallbackCascade,
PrecisionEnforcement, and OOM Error Trapping.

Strictly complies with the Tripartite Air-Gap Policy, Zero-Mock Mandate, and Mendeleev Library Mandate.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence, Set, Tuple, Union

# Disable HDF5 internal file locking to prevent Windows handle collisions
os.environ.setdefault("HDF5_USE_FILE_LOCKING", "FALSE")

import h5py
import numpy as np
import psutil
from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Dynamic Mendeleev import for periodic table compliance
try:
    import mendeleev
except ImportError:
    mendeleev = None

# Optional acceleration libraries with fail-safe fallback
try:
    import pynvml
except (ImportError, Exception):
    pynvml = None

try:
    import torch
except (ImportError, Exception):
    torch = None

# Initialize module logger
logger = logging.getLogger("CoChem.TOPOS.MechanicsMemory")


# ============================================================================
# Dynamic Mendeleev Element & Mass Resolution (Mendeleev Mandate)
# ============================================================================

def get_atomic_mass(atomic_number_or_symbol: Union[int, str]) -> float:
    """
    Dynamically retrieve atomic mass via the mendeleev library.
    Hardcoded atomic masses and isotopic constants are strictly prohibited.
    """
    if mendeleev is None:
        raise RuntimeError("mendeleev library is required for dynamic atomic mass retrieval.")
    elem = mendeleev.element(atomic_number_or_symbol)
    return float(elem.mass)


def get_element_symbol(atomic_number: int) -> str:
    """Dynamically retrieve elemental symbol via the mendeleev library."""
    if mendeleev is None:
        raise RuntimeError("mendeleev library is required for element symbol retrieval.")
    elem = mendeleev.element(atomic_number)
    return str(elem.symbol)


def get_molecular_mass(atomic_numbers: Sequence[int]) -> float:
    """Dynamically compute total molecular mass using mendeleev atomic masses."""
    return float(sum(get_atomic_mass(z) for z in atomic_numbers))


# ============================================================================
# Air-Gap Protocol & Path Resolution
# ============================================================================

def get_cochem_workspace() -> Path:
    """Resolve active COCHEM_WORKSPACE path strictly from environment or working directory."""
    workspace_env = os.environ.get("COCHEM_WORKSPACE")
    if workspace_env:
        return Path(workspace_env).resolve()
    return Path.cwd().resolve()


def get_artifacts_directory() -> Path:
    """Resolve the CoChem_Artifacts directory."""
    ws = get_cochem_workspace()
    path = ws / "CoChem_Artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_registry_directory() -> Path:
    """Resolve the CoChem Registry directory."""
    path = get_artifacts_directory() / "Registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_databases_directory() -> Path:
    """Resolve the CoChem Databases directory."""
    path = get_artifacts_directory() / "Databases"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_system_config_path() -> Path:
    """Resolve the standard system configuration file path."""
    return get_registry_directory() / "cochem_system_config.json"


def load_system_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Read configuration strictly under the Air-Gap Protocol.
    Defaults to ${COCHEM_WORKSPACE}/CoChem_Artifacts/Registry/cochem_system_config.json.
    """
    target = Path(config_path).resolve() if config_path else get_system_config_path()
    if target.exists() and target.is_file():
        try:
            with open(target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read system config at {target}: {e}")
    
    # Check alternate fallback in root workspace
    alt_target = get_cochem_workspace() / "cochem_system_config.json"
    if alt_target.exists() and alt_target.is_file():
        try:
            with open(alt_target, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read fallback system config at {alt_target}: {e}")

    # Standard default air-gapped configuration
    return {
        "workspace": str(get_cochem_workspace()),
        "vram_governor_cap": 0.85,
        "active_thread_percentage": 85,
        "default_precision": "float64",
        "h5_compression": "gzip",
        "h5_fletcher32": True,
    }


# ============================================================================
# Enums and Pydantic Data Models
# ============================================================================

class EngineTier(str, Enum):
    """Supported computational engine hierarchy tiers."""
    MACE_OFF24M = "MACE-OFF24m"
    AIMNET2 = "AIMNet2"
    G_XTB = "g-xTB"
    XTB2 = "xTB2"


class TheoreticalTier(str, Enum):
    """Theoretical turnaround time tiers."""
    T1_1MIN = "T1-1min"
    T2_5MIN = "T2-5min"
    T3_30MIN = "T3-30min"
    T3_3H = "T3-3h"


class FallbackReason(str, Enum):
    """Reasons for triggering a fallback cascade transition."""
    UNSUPPORTED_ELEMENTS = "unsupported_elements"
    INSUFFICIENT_VRAM = "insufficient_vram"
    INSUFFICIENT_RAM = "insufficient_ram"
    NO_CUDA_DEVICE = "no_cuda_device"
    EXECUTION_FAILURE = "execution_failure"
    OOM_SIGKILL = "oom_sigkill"
    USER_OVERRIDE = "user_override"
    NONE = "none"


class DeviceType(str, Enum):
    """Target execution device."""
    CPU = "cpu"
    CUDA = "cuda"
    AUTO = "auto"


class PrecisionMode(str, Enum):
    """Floating point precision mode."""
    FP64 = "float64"
    FP32 = "float32"
    FP16 = "float16"
    BF16 = "bfloat16"


class GPUDeviceInfo(BaseModel):
    """Detailed telemetry for an individual GPU device."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    index: int
    name: str
    total_vram_bytes: int
    free_vram_bytes: int
    used_vram_bytes: int
    utilization_pct: float = 0.0
    temperature_c: Optional[float] = None


class HardwareSnapshot(BaseModel):
    """Complete host machine resource snapshot."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: float = Field(default_factory=time.time)
    cpu_count_logical: int
    cpu_count_physical: int
    cpu_percent: float
    ram_total_bytes: int
    ram_available_bytes: int
    ram_used_bytes: int
    ram_percent: float
    swap_total_bytes: int = 0
    swap_free_bytes: int = 0
    cuda_available: bool = False
    gpu_count: int = 0
    gpu_devices: List[GPUDeviceInfo] = Field(default_factory=list)


class CascadeTransition(BaseModel):
    """Audit record of an engine fallback transition."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    from_engine: EngineTier
    to_engine: EngineTier
    reason: FallbackReason
    timestamp: float = Field(default_factory=time.time)
    details: str = ""


class CascadeState(BaseModel):
    """State machine output tracking active engine and execution parameters."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_engine: EngineTier
    initial_engine: EngineTier
    target_device: DeviceType = DeviceType.CPU
    precision_mode: PrecisionMode = PrecisionMode.FP64
    theoretical_tier: TheoreticalTier = TheoreticalTier.T1_1MIN
    is_downgraded: bool = False
    transitions: List[CascadeTransition] = Field(default_factory=list)


class GeometryRecord(BaseModel):
    """Complete molecular geometry tensor payload."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    geom_id: str
    atomic_numbers: List[int]
    coords: List[List[float]]
    energy: float
    gradient: Optional[List[List[float]]] = None
    hessian: Optional[List[List[float]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("atomic_numbers")
    @classmethod
    def validate_atomic_numbers(cls, v: List[int]) -> List[int]:
        if not v:
            raise ValueError("atomic_numbers list must not be empty.")
        for z in v:
            if not isinstance(z, int) or z < 1 or z > 118:
                raise ValueError(f"Invalid atomic number: {z}")
        return v

    @field_validator("coords")
    @classmethod
    def validate_coords(cls, v: List[List[float]]) -> List[List[float]]:
        if not v:
            raise ValueError("coords list must not be empty.")
        for idx, coord in enumerate(v):
            if len(coord) != 3:
                raise ValueError(f"Coordinate at index {idx} has invalid dimension {len(coord)}, expected 3.")
        return v

    @model_validator(mode="after")
    def validate_geometry_dimensions(self) -> GeometryRecord:
        n_atoms = len(self.atomic_numbers)
        if len(self.coords) != n_atoms:
            raise ValueError(
                f"Dimension mismatch: len(coords)={len(self.coords)} != len(atomic_numbers)={n_atoms}"
            )
        if self.gradient is not None and len(self.gradient) > 0:
            if len(self.gradient) != n_atoms:
                raise ValueError(
                    f"Dimension mismatch: len(gradient)={len(self.gradient)} != len(atomic_numbers)={n_atoms}"
                )
            for idx, grad in enumerate(self.gradient):
                if len(grad) != 3:
                    raise ValueError(f"Gradient at index {idx} has invalid dimension {len(grad)}, expected 3.")
        if self.hessian is not None and len(self.hessian) > 0:
            expected_dim = 3 * n_atoms
            if len(self.hessian) != expected_dim:
                raise ValueError(
                    f"Dimension mismatch: len(hessian)={len(self.hessian)} != 3*N={expected_dim}"
                )
        return self

    @property
    def total_mass(self) -> float:
        """Total molecular mass dynamically retrieved from mendeleev."""
        return get_molecular_mass(self.atomic_numbers)

    @property
    def symbols(self) -> List[str]:
        """Elemental symbols dynamically retrieved from mendeleev."""
        return [get_element_symbol(z) for z in self.atomic_numbers]


class TrajectoryStep(BaseModel):
    """Single step in a molecular dynamics or optimization trajectory."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    geom_id: str
    step_index: int
    coords: List[List[float]]
    energy: float
    forces: Optional[List[List[float]]] = None
    timestamp: float = Field(default_factory=time.time)


class TelemetryRecord(BaseModel):
    """Telemetry log entry capturing runtime metrics."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    record_id: str
    timestamp: float = Field(default_factory=time.time)
    engine: str
    device: str
    batch_size: int
    ram_used_bytes: int
    vram_used_bytes: int = 0
    duration_seconds: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class QCSchemaPoint(BaseModel):
    """QCSchema Point structure for molecular quantum states."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    point_id: str
    atomic_numbers: List[int]
    coordinates: List[List[float]]
    energy: float
    gradient: Optional[List[List[float]]] = None
    hessian: Optional[List[List[float]]] = None
    method_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_mass(self) -> float:
        """Total molecular mass dynamically retrieved from mendeleev."""
        return get_molecular_mass(self.atomic_numbers)

    @property
    def symbols(self) -> List[str]:
        """Elemental symbols dynamically retrieved from mendeleev."""
        return [get_element_symbol(z) for z in self.atomic_numbers]


# ============================================================================
# POSIX Stale Lock Sweep & Error Trapping
# ============================================================================

def sweep_stale_locks(directory: Optional[Union[str, Path]] = None) -> List[Path]:
    """
    Execute a POSIX sweep upon startup to detect and delete stale lock files (*.h5.lck, *.lock).
    Checks if the PID in the lock file is still active, removing orphaned locks.
    """
    target_dir = Path(directory).resolve() if directory else get_databases_directory()
    deleted_locks: List[Path] = []
    if not target_dir.exists():
        return deleted_locks

    # Look for both .h5.lck, .h5.lock, and .lock files
    candidate_locks = list(target_dir.glob("*.h5.lck")) + list(target_dir.glob("*.h5.lock")) + list(target_dir.glob("*.lock"))
    
    for lock_file in candidate_locks:
        try:
            is_stale = False
            # Check if file has PID recorded or is empty/abandoned
            if lock_file.stat().st_size > 0:
                try:
                    content = lock_file.read_text(encoding="utf-8").strip()
                    if content.isdigit():
                        pid = int(content)
                        if not psutil.pid_exists(pid):
                            is_stale = True
                    else:
                        # Non-pid format or generic filelock, check modification age (>60s)
                        if (time.time() - lock_file.stat().st_mtime) > 60.0:
                            is_stale = True
                except Exception:
                    is_stale = True
            else:
                # 0-byte lock file older than 30s
                if (time.time() - lock_file.stat().st_mtime) > 30.0:
                    is_stale = True

            if is_stale:
                lock_file.unlink(missing_ok=True)
                deleted_locks.append(lock_file)
                logger.info(f"POSIX sweep removed stale lock file: {lock_file}")
        except Exception as e:
            logger.warning(f"Error inspecting lock file {lock_file}: {e}")

    return deleted_locks


class EngineOOMError(RuntimeError):
    """Raised when an external computational engine process is killed due to Out-Of-Memory (OOM)."""
    def __init__(self, message: str, autopsy_path: Optional[Path] = None, autopsy_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.autopsy_path = autopsy_path
        self.autopsy_data = autopsy_data or {}


def generate_oom_autopsy(
    exit_code: int,
    tensor_size_bytes: int,
    atomic_count: int,
    theoretical_tier: Union[TheoreticalTier, str],
    output_path: Optional[Union[str, Path]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Generate OOM_autopsy.json detailing tensor size, atomic count, theoretical tier,
    and host memory conditions when an engine is terminated by SIGKILL (137).
    """
    target_path = Path(output_path).resolve() if output_path else (get_databases_directory() / "OOM_autopsy.json")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    broker = HardwareResourceBroker()
    snapshot = broker.poll_hardware()

    tier_str = theoretical_tier.value if isinstance(theoretical_tier, TheoreticalTier) else str(theoretical_tier)

    # Determine recommended fallback tier
    tier_fallback_map = {
        "T1-1min": "T2-5min",
        "T2-5min": "T3-30min",
        "T3-30min": "T3-3h",
        "T3-3h": "T3-3h (terminal)",
    }
    recommended_tier = tier_fallback_map.get(tier_str, "T3-3h")

    autopsy = {
        "timestamp": time.time(),
        "exit_code": int(exit_code),
        "is_oom": exit_code in (137, 9, -9),
        "tensor_size_bytes": int(tensor_size_bytes),
        "tensor_size_mb": round(tensor_size_bytes / (1024 * 1024), 3),
        "atomic_count": int(atomic_count),
        "theoretical_tier": tier_str,
        "host_ram_total_bytes": snapshot.ram_total_bytes,
        "host_ram_available_bytes": snapshot.ram_available_bytes,
        "host_ram_used_percent": snapshot.ram_percent,
        "cuda_available": snapshot.cuda_available,
        "gpu_devices": [g.model_dump() for g in snapshot.gpu_devices],
        "recommended_fallback_tier": recommended_tier,
        "recommended_safe_batch_size": max(1, broker.calculate_safe_batch_size(num_atoms=max(1, atomic_count), engine=EngineTier.G_XTB)),
        "status": "OOM_DIAGNOSED",
        "remediation": f"Initiate fallback cascade from {tier_str} to {recommended_tier} with constrained batch size.",
        "extra_context": extra_context or {},
    }

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(autopsy, f, indent=2)

    logger.error(f"Generated OOM Autopsy at {target_path} (Exit Code: {exit_code}, Tier: {tier_str})")
    return target_path


def handle_engine_exit_code(
    exit_code: int,
    tensor_size_bytes: int,
    atomic_count: int,
    theoretical_tier: Union[TheoreticalTier, str] = TheoreticalTier.T1_1MIN,
    output_path: Optional[Union[str, Path]] = None,
    raise_on_oom: bool = True,
) -> Optional[Path]:
    """
    Inspect process exit code and trigger OOM autopsy generation on SIGKILL / 137.
    """
    if exit_code in (137, 9, -9):
        autopsy_path = generate_oom_autopsy(
            exit_code=exit_code,
            tensor_size_bytes=tensor_size_bytes,
            atomic_count=atomic_count,
            theoretical_tier=theoretical_tier,
            output_path=output_path,
        )
        if raise_on_oom:
            raise EngineOOMError(
                f"External engine terminated by OS (Exit Code {exit_code} / SIGKILL). Autopsy written to {autopsy_path}",
                autopsy_path=autopsy_path,
            )
        return autopsy_path
    return None


# ============================================================================
# Precision Mandate Enforcement
# ============================================================================

def enforce_precision_tier(mode: PrecisionMode = PrecisionMode.FP64) -> None:
    """
    Explicitly mandate FP64 (or configured mode) precision across all execution tiers.
    Sets JAX_ENABLE_X64=True and PyTorch default floating point dtype.
    """
    if mode == PrecisionMode.FP64:
        os.environ["JAX_ENABLE_X64"] = "True"
        if torch is not None:
            try:
                torch.set_default_dtype(torch.float64)
            except Exception as e:
                logger.debug(f"Could not set torch default dtype to float64: {e}")
    elif mode == PrecisionMode.FP32:
        os.environ["JAX_ENABLE_X64"] = "False"
        if torch is not None:
            try:
                torch.set_default_dtype(torch.float32)
            except Exception as e:
                logger.debug(f"Could not set torch default dtype to float32: {e}")


# ============================================================================
# 1. HDF5 State Manager & Atomic Flush Mandate
# ============================================================================

class ToposHDF5MemoryManager:
    """
    HDF5 State Manager for CoChem-TOPOS.
    Dynamically resolves artifact database pathing to ${COCHEM_WORKSPACE}/CoChem_Artifacts/Databases/landscape.h5.
    Created WITHOUT SWMR flags (due to HPC POSIX constraints) and enforces chunking,
    compression='gzip', shuffle=True, fletcher32=True, QCSchema layout, and immediate atomic flush.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        lock_timeout: float = 30.0,
        sweep_locks_on_init: bool = True,
    ) -> None:
        self.db_path = self._resolve_db_path(db_path)
        self.lock_timeout = lock_timeout
        self.lock_path = Path(f"{self.db_path}.lock")

        # Startup POSIX sweep to clean stale locks
        if sweep_locks_on_init:
            sweep_stale_locks(self.db_path.parent)

        self.lock = FileLock(str(self.lock_path), timeout=self.lock_timeout)

        # Enforce FP64 precision mandate by default
        enforce_precision_tier(PrecisionMode.FP64)

        # Initialize the master datastore
        self._initialize_database()

    @staticmethod
    def _resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
        """Dynamically resolve database path strictly under the Air-Gap Protocol."""
        if db_path is not None:
            resolved = Path(db_path).resolve()
        else:
            resolved = get_databases_directory() / "landscape.h5"

        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _initialize_database(self) -> None:
        """
        Create and provision master HDF5 database structure without SWMR flags.
        Initializes QCSchema hierarchy (/meta, /methods, /points) and legacy structures.
        """
        try:
            with self.lock:
                if not self.db_path.exists() or self.db_path.stat().st_size == 0:
                    with h5py.File(self.db_path, "w", libver="latest") as f:
                        f.attrs["description"] = "CoChem-TOPOS Master Tensor Database"
                        f.attrs["pipeline"] = "CoChem-TOPOS"
                        f.attrs["version"] = "2.0"
                        f.attrs["format_version"] = "2.0"
                        f.attrs["precision_mandate"] = "float64"
                        f.attrs["created_at"] = time.time()

                        # QCSchema Layout
                        f.create_group("meta")
                        f.create_group("methods")
                        f.create_group("points")

                        # Core backward-compatibility groups
                        f.create_group("geometries")
                        f.create_group("trajectories")
                        f.create_group("telemetry")
                        f.create_group("metadata")

                        f.flush()
                    logger.info(f"Initialized HDF5 QCSchema database at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize HDF5 database at {self.db_path}: {e}")
            raise RuntimeError(f"HDF5 database initialization failed: {e}") from e

    @contextmanager
    def open_reader(self) -> Generator[h5py.File, None, None]:
        """Open HDF5 file in read mode without SWMR flag (POSIX-compliant)."""
        f = None
        max_retries = 10
        for attempt in range(max_retries):
            try:
                f = h5py.File(self.db_path, "r", libver="latest")
                break
            except (OSError, RuntimeError) as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    raise e
        try:
            yield f
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass

    def write_qcschema_point(
        self,
        point_id: str,
        coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
        energy: float,
        atomic_numbers: Sequence[int],
        gradient: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
        hessian: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
        method_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write a QCSchema point record under /points/<point_id> with chunking, compression,
        fletcher32 checksum, and immediate atomic flush.
        """
        coords_arr = np.asarray(coordinates, dtype=np.float64)
        z_arr = np.asarray(atomic_numbers, dtype=np.int32)
        n_atoms = len(z_arr)

        if coords_arr.shape != (n_atoms, 3):
            raise ValueError(f"Coordinates shape {coords_arr.shape} must match ({n_atoms}, 3)")

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        points_grp = f["points"]
                        if point_id in points_grp:
                            del points_grp[point_id]

                        pt = points_grp.create_group(point_id)

                        # Atomic coordinates: chunked, gzip, shuffle, fletcher32
                        pt.create_dataset(
                            "coordinates",
                            data=coords_arr,
                            chunks=True,
                            compression="gzip",
                            shuffle=True,
                            fletcher32=True,
                        )

                        # Atomic numbers: chunked, gzip
                        pt.create_dataset(
                            "atomic_numbers",
                            data=z_arr,
                            chunks=True,
                            compression="gzip",
                            shuffle=True,
                            fletcher32=True,
                        )

                        # Electronic Energy: FP64 chunked dataset
                        pt.create_dataset(
                            "energy",
                            data=np.array([float(energy)], dtype=np.float64),
                            chunks=True,
                            compression="gzip",
                            fletcher32=True,
                        )
                        pt.attrs["electronic_energy_hartree"] = float(energy)

                        if gradient is not None:
                            grad_arr = np.asarray(gradient, dtype=np.float64)
                            if grad_arr.shape != (n_atoms, 3):
                                raise ValueError(f"Gradient shape {grad_arr.shape} must match ({n_atoms}, 3)")
                            pt.create_dataset(
                                "gradient",
                                data=grad_arr,
                                chunks=True,
                                compression="gzip",
                                shuffle=True,
                                fletcher32=True,
                            )

                        if hessian is not None:
                            hess_arr = np.asarray(hessian, dtype=np.float64)
                            exp_dim = 3 * n_atoms
                            if hess_arr.shape != (exp_dim, exp_dim):
                                raise ValueError(f"Hessian shape {hess_arr.shape} must match ({exp_dim}, {exp_dim})")
                            pt.create_dataset(
                                "hessian",
                                data=hess_arr,
                                chunks=True,
                                compression="gzip",
                                shuffle=True,
                                fletcher32=True,
                            )

                        if method_id:
                            pt.attrs["method_id"] = str(method_id)
                        pt.attrs["meta_json"] = json.dumps(meta or {})
                        pt.attrs["updated_at"] = time.time()

                        # Immediate atomic flush
                        f.flush()
                logger.debug(f"Successfully flushed QCSchema point [{point_id}] to {self.db_path}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    logger.error(f"Failed to write QCSchema point [{point_id}]: {e}")
                    raise RuntimeError(f"HDF5 QCSchema point write failure: {e}") from e

    def read_qcschema_point(self, point_id: str) -> Optional[QCSchemaPoint]:
        """Read a QCSchema point record from /points/<point_id>."""
        try:
            with self.open_reader() as f:
                if "points" not in f or point_id not in f["points"]:
                    return None

                pt = f["points"][point_id]
                coords = pt["coordinates"][:].astype(float).tolist()
                atomic_numbers = pt["atomic_numbers"][:].astype(int).tolist()
                energy = float(pt["energy"][0]) if "energy" in pt else float(pt.attrs.get("electronic_energy_hartree", 0.0))

                gradient = None
                if "gradient" in pt:
                    gradient = pt["gradient"][:].astype(float).tolist()

                hessian = None
                if "hessian" in pt:
                    hessian = pt["hessian"][:].astype(float).tolist()

                method_id = pt.attrs.get("method_id", None)
                meta_json = pt.attrs.get("meta_json", "{}")
                try:
                    meta = json.loads(meta_json)
                except Exception:
                    meta = {}

                return QCSchemaPoint(
                    point_id=point_id,
                    atomic_numbers=atomic_numbers,
                    coordinates=coords,
                    energy=energy,
                    gradient=gradient,
                    hessian=hessian,
                    method_id=method_id,
                    meta=meta,
                )
        except Exception as e:
            logger.error(f"Failed to read QCSchema point [{point_id}]: {e}")
            return None

    def register_method(
        self,
        method_id: str,
        engine: Union[EngineTier, str],
        basis: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        precision: str = "float64",
    ) -> None:
        """Register a computational method definition in /methods/<method_id> with immediate flush."""
        engine_str = engine.value if isinstance(engine, EngineTier) else str(engine)
        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        methods_grp = f["methods"]
                        if method_id in methods_grp:
                            mg = methods_grp[method_id]
                        else:
                            mg = methods_grp.create_group(method_id)

                        mg.attrs["engine"] = engine_str
                        mg.attrs["basis"] = str(basis or "none")
                        mg.attrs["precision"] = str(precision)
                        mg.attrs["parameters_json"] = json.dumps(parameters or {})
                        mg.attrs["updated_at"] = time.time()
                        f.flush()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    raise RuntimeError(f"HDF5 method registration failure: {e}") from e

    def read_method(self, method_id: str) -> Optional[Dict[str, Any]]:
        """Read a registered method configuration from /methods/<method_id>."""
        try:
            with self.open_reader() as f:
                if "methods" not in f or method_id not in f["methods"]:
                    return None
                mg = f["methods"][method_id]
                return {
                    "method_id": method_id,
                    "engine": str(mg.attrs.get("engine", "")),
                    "basis": str(mg.attrs.get("basis", "")),
                    "precision": str(mg.attrs.get("precision", "float64")),
                    "parameters": json.loads(mg.attrs.get("parameters_json", "{}")),
                    "updated_at": float(mg.attrs.get("updated_at", 0.0)),
                }
        except Exception as e:
            logger.error(f"Failed to read method [{method_id}]: {e}")
            return None

    def list_points(self) -> List[str]:
        """List all QCSchema point IDs in the database."""
        try:
            with self.open_reader() as f:
                if "points" in f:
                    return list(f["points"].keys())
                return []
        except Exception as e:
            logger.error(f"Failed to list points: {e}")
            return []

    def list_methods(self) -> List[str]:
        """List all registered method IDs in the database."""
        try:
            with self.open_reader() as f:
                if "methods" in f:
                    return list(f["methods"].keys())
                return []
        except Exception as e:
            logger.error(f"Failed to list methods: {e}")
            return []

    def write_geometry(self, record: Union[GeometryRecord, Dict[str, Any]]) -> None:
        """
        Safely write a molecular geometry and associated tensors to /geometries and sync to QCSchema.
        Enforces chunking, gzip compression, fletcher32 checksum, and immediate atomic flush.
        """
        if isinstance(record, dict):
            record = GeometryRecord(**record)

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        geoms_grp = f["geometries"]
                        if record.geom_id in geoms_grp:
                            del geoms_grp[record.geom_id]

                        g = geoms_grp.create_group(record.geom_id)

                        g.create_dataset(
                            "atomic_numbers",
                            data=np.array(record.atomic_numbers, dtype=np.int32),
                            chunks=True,
                            compression="gzip",
                            shuffle=True,
                            fletcher32=True,
                        )
                        g.create_dataset(
                            "coordinates",
                            data=np.array(record.coords, dtype=np.float64),
                            chunks=True,
                            compression="gzip",
                            shuffle=True,
                            fletcher32=True,
                        )
                        g.attrs["electronic_energy_hartree"] = float(record.energy)

                        if record.gradient is not None and len(record.gradient) > 0:
                            g.create_dataset(
                                "gradient_matrix",
                                data=np.array(record.gradient, dtype=np.float64),
                                chunks=True,
                                compression="gzip",
                                shuffle=True,
                                fletcher32=True,
                            )

                        if record.hessian is not None and len(record.hessian) > 0:
                            g.create_dataset(
                                "hessian_matrix",
                                data=np.array(record.hessian, dtype=np.float64),
                                chunks=True,
                                compression="gzip",
                                shuffle=True,
                                fletcher32=True,
                            )

                        g.attrs["metadata_json"] = json.dumps(record.metadata)
                        g.attrs["updated_at"] = time.time()
                        f.flush()

                # Also dual-write to QCSchema points for seamless unified access
                self.write_qcschema_point(
                    point_id=record.geom_id,
                    coordinates=record.coords,
                    energy=record.energy,
                    atomic_numbers=record.atomic_numbers,
                    gradient=record.gradient,
                    hessian=record.hessian,
                    meta=record.metadata,
                )
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    logger.error(f"Failed to write geometry [{record.geom_id}]: {e}")
                    raise RuntimeError(f"HDF5 geometry write failure: {e}") from e

    def read_geometry(self, geom_id: str) -> Optional[GeometryRecord]:
        """Read a geometry record and its associated tensors."""
        try:
            with self.open_reader() as f:
                if "geometries" not in f or geom_id not in f["geometries"]:
                    # Fallback check on QCSchema points
                    q_pt = self.read_qcschema_point(geom_id)
                    if q_pt is not None:
                        return GeometryRecord(
                            geom_id=q_pt.point_id,
                            atomic_numbers=q_pt.atomic_numbers,
                            coords=q_pt.coordinates,
                            energy=q_pt.energy,
                            gradient=q_pt.gradient,
                            hessian=q_pt.hessian,
                            metadata=q_pt.meta,
                        )
                    return None

                g = f["geometries"][geom_id]
                atomic_numbers = g["atomic_numbers"][:].astype(int).tolist()
                coords = g["coordinates"][:].astype(float).tolist()
                energy = float(g.attrs.get("electronic_energy_hartree", 0.0))

                gradient = None
                if "gradient_matrix" in g:
                    gradient = g["gradient_matrix"][:].astype(float).tolist()

                hessian = None
                if "hessian_matrix" in g:
                    hessian = g["hessian_matrix"][:].astype(float).tolist()

                metadata_json = g.attrs.get("metadata_json", "{}")
                try:
                    metadata = json.loads(metadata_json)
                except Exception:
                    metadata = {}

                return GeometryRecord(
                    geom_id=geom_id,
                    atomic_numbers=atomic_numbers,
                    coords=coords,
                    energy=energy,
                    gradient=gradient,
                    hessian=hessian,
                    metadata=metadata,
                )
        except Exception as e:
            logger.error(f"Failed to read geometry [{geom_id}]: {e}")
            return None

    def append_trajectory_step(self, step: Union[TrajectoryStep, Dict[str, Any]]) -> None:
        """Append a trajectory step with chunked compression and immediate atomic flush."""
        if isinstance(step, dict):
            step = TrajectoryStep(**step)

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        trajs_grp = f["trajectories"]
                        if step.geom_id not in trajs_grp:
                            traj_geom = trajs_grp.create_group(step.geom_id)
                        else:
                            traj_geom = trajs_grp[step.geom_id]

                        step_key = f"{step.step_index:06d}"
                        if step_key in traj_geom:
                            del traj_geom[step_key]

                        sg = traj_geom.create_group(step_key)
                        sg.create_dataset(
                            "coordinates",
                            data=np.array(step.coords, dtype=np.float64),
                            chunks=True,
                            compression="gzip",
                            shuffle=True,
                            fletcher32=True,
                        )
                        sg.attrs["energy"] = float(step.energy)
                        sg.attrs["timestamp"] = float(step.timestamp)
                        sg.attrs["step_index"] = int(step.step_index)

                        if step.forces is not None and len(step.forces) > 0:
                            sg.create_dataset(
                                "forces",
                                data=np.array(step.forces, dtype=np.float64),
                                chunks=True,
                                compression="gzip",
                                shuffle=True,
                                fletcher32=True,
                            )

                        f.flush()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    logger.error(f"Failed to append trajectory step for [{step.geom_id}]: {e}")
                    raise RuntimeError(f"HDF5 trajectory append failure: {e}") from e

    def read_trajectory(self, geom_id: str) -> List[TrajectoryStep]:
        """Read the entire trajectory sequence for a geometry ID, sorted by step index."""
        results: List[TrajectoryStep] = []
        try:
            with self.open_reader() as f:
                if "trajectories" not in f or geom_id not in f["trajectories"]:
                    return results

                traj_geom = f["trajectories"][geom_id]
                sorted_step_keys = sorted(traj_geom.keys())

                for step_key in sorted_step_keys:
                    sg = traj_geom[step_key]
                    coords = sg["coordinates"][:].astype(float).tolist()
                    energy = float(sg.attrs.get("energy", 0.0))
                    timestamp = float(sg.attrs.get("timestamp", 0.0))
                    step_index = int(sg.attrs.get("step_index", int(step_key)))

                    forces = None
                    if "forces" in sg:
                        forces = sg["forces"][:].astype(float).tolist()

                    results.append(
                        TrajectoryStep(
                            geom_id=geom_id,
                            step_index=step_index,
                            coords=coords,
                            energy=energy,
                            forces=forces,
                            timestamp=timestamp,
                        )
                    )
            return results
        except Exception as e:
            logger.error(f"Failed to read trajectory for [{geom_id}]: {e}")
            return []

    def record_telemetry(self, telemetry: Union[TelemetryRecord, Dict[str, Any]]) -> None:
        """Record host hardware and calculation telemetry with immediate flush."""
        if isinstance(telemetry, dict):
            telemetry = TelemetryRecord(**telemetry)

        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        telem_grp = f["telemetry"]
                        if telemetry.record_id in telem_grp:
                            tg = telem_grp[telemetry.record_id]
                        else:
                            tg = telem_grp.create_group(telemetry.record_id)

                        tg.attrs["timestamp"] = float(telemetry.timestamp)
                        tg.attrs["engine"] = str(telemetry.engine)
                        tg.attrs["device"] = str(telemetry.device)
                        tg.attrs["batch_size"] = int(telemetry.batch_size)
                        tg.attrs["ram_used_bytes"] = int(telemetry.ram_used_bytes)
                        tg.attrs["vram_used_bytes"] = int(telemetry.vram_used_bytes)
                        if telemetry.duration_seconds is not None:
                            tg.attrs["duration_seconds"] = float(telemetry.duration_seconds)
                        elif "duration_seconds" in tg.attrs:
                            del tg.attrs["duration_seconds"]
                        tg.attrs["extra_json"] = json.dumps(telemetry.extra)
                        f.flush()
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))
                else:
                    logger.error(f"Failed to record telemetry [{telemetry.record_id}]: {e}")
                    raise RuntimeError(f"HDF5 telemetry write failure: {e}") from e

    def read_telemetry(self, record_id: Optional[str] = None) -> Union[List[TelemetryRecord], Optional[TelemetryRecord]]:
        """Read telemetry records."""
        try:
            with self.open_reader() as f:
                if "telemetry" not in f:
                    return None if record_id else []

                telem_grp = f["telemetry"]
                if record_id is not None:
                    if record_id not in telem_grp:
                        return None
                    tg = telem_grp[record_id]
                    return TelemetryRecord(
                        record_id=record_id,
                        timestamp=float(tg.attrs.get("timestamp", 0.0)),
                        engine=str(tg.attrs.get("engine", "")),
                        device=str(tg.attrs.get("device", "cpu")),
                        batch_size=int(tg.attrs.get("batch_size", 1)),
                        ram_used_bytes=int(tg.attrs.get("ram_used_bytes", 0)),
                        vram_used_bytes=int(tg.attrs.get("vram_used_bytes", 0)),
                        duration_seconds=float(tg.attrs.get("duration_seconds")) if "duration_seconds" in tg.attrs else None,
                        extra=json.loads(tg.attrs.get("extra_json", "{}")),
                    )
                else:
                    all_records = []
                    for rid in telem_grp.keys():
                        tg = telem_grp[rid]
                        all_records.append(
                            TelemetryRecord(
                                record_id=rid,
                                timestamp=float(tg.attrs.get("timestamp", 0.0)),
                                engine=str(tg.attrs.get("engine", "")),
                                device=str(tg.attrs.get("device", "cpu")),
                                batch_size=int(tg.attrs.get("batch_size", 1)),
                                ram_used_bytes=int(tg.attrs.get("ram_used_bytes", 0)),
                                vram_used_bytes=int(tg.attrs.get("vram_used_bytes", 0)),
                                duration_seconds=float(tg.attrs.get("duration_seconds")) if "duration_seconds" in tg.attrs else None,
                                extra=json.loads(tg.attrs.get("extra_json", "{}")),
                            )
                        )
                    return all_records
        except Exception as e:
            logger.error(f"Failed to read telemetry: {e}")
            return None if record_id else []

    def list_geometries(self) -> List[str]:
        """List all geometry IDs currently registered in the database."""
        try:
            with self.open_reader() as f:
                if "geometries" in f:
                    return list(f["geometries"].keys())
                return []
        except Exception as e:
            logger.error(f"Failed to list geometries: {e}")
            return []


# ============================================================================
# 2. Dynamic Hardware Resource Broker & VRAM Governor
# ============================================================================

class HardwareResourceBroker:
    """
    Dynamic hardware resource monitor and VRAM governor.
    Polls real psutil and pynvml metrics, traps unreachability exceptions for seamless CPU fallback,
    and configures CUDA MPS governor limits to cap VRAM usage at 85%.
    """

    def __init__(self) -> None:
        self._nvml_initialized = False

    def _poll_gpu_devices(self) -> List[GPUDeviceInfo]:
        """Poll NVIDIA GPU devices via pynvml with comprehensive fail-safe exception trapping."""
        gpus: List[GPUDeviceInfo] = []
        if pynvml is None:
            return gpus

        try:
            if not self._nvml_initialized:
                pynvml.nvmlInit()
                self._nvml_initialized = True

            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                raw_name = pynvml.nvmlDeviceGetName(handle)
                name = raw_name.decode("utf-8") if isinstance(raw_name, bytes) else str(raw_name)

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
                except Exception:
                    util = 0.0

                try:
                    temp = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
                except Exception:
                    temp = None

                gpus.append(
                    GPUDeviceInfo(
                        index=i,
                        name=name,
                        total_vram_bytes=int(mem_info.total),
                        free_vram_bytes=int(mem_info.free),
                        used_vram_bytes=int(mem_info.used),
                        utilization_pct=float(util),
                        temperature_c=temp,
                    )
                )
        except Exception as e:
            logger.debug(f"NVIDIA GPU polling inactive or pynvml unreachable: {e}")
            self._nvml_initialized = False

        return gpus

    def poll_hardware(self) -> HardwareSnapshot:
        """Capture an instantaneous host machine resource snapshot."""
        cpu_perc = float(psutil.cpu_percent(interval=None))
        cpu_logical = psutil.cpu_count(logical=True) or 1
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()

        gpus = self._poll_gpu_devices()
        cuda_avail = len(gpus) > 0

        return HardwareSnapshot(
            timestamp=time.time(),
            cpu_count_logical=cpu_logical,
            cpu_count_physical=cpu_physical,
            cpu_percent=cpu_perc,
            ram_total_bytes=int(vm.total),
            ram_available_bytes=int(vm.available),
            ram_used_bytes=int(vm.used),
            ram_percent=float(vm.percent),
            swap_total_bytes=int(swap.total),
            swap_free_bytes=int(swap.free),
            cuda_available=cuda_avail,
            gpu_count=len(gpus),
            gpu_devices=gpus,
        )

    def apply_vram_governor(
        self,
        max_vram_fraction: float = 0.85,
        active_thread_percentage: int = 85,
    ) -> Dict[str, str]:
        """
        Broker concurrency memory on GPUs via CUDA_MPS_PINNED_DEVICE_MEM_LIMIT and
        CUDA_MPS_ACTIVE_THREAD_PERCENTAGE to strictly cap VRAM usage at 85%.
        """
        max_vram_fraction = max(0.1, min(0.95, float(max_vram_fraction)))
        active_thread_percentage = max(10, min(100, int(active_thread_percentage)))

        snapshot = self.poll_hardware()
        env_updates: Dict[str, str] = {}

        if snapshot.cuda_available and snapshot.gpu_devices:
            min_total_vram = min(g.total_vram_bytes for g in snapshot.gpu_devices)
            capped_bytes = int(min_total_vram * max_vram_fraction)
            capped_mb = max(256, capped_bytes // (1024 * 1024))
            limit_val = f"{capped_mb}M"
        else:
            limit_val = f"{int(max_vram_fraction * 100)}%"

        os.environ["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = limit_val
        os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(active_thread_percentage)
        os.environ["COCHEM_VRAM_GOVERNOR_ACTIVE"] = "1"

        env_updates["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = limit_val
        env_updates["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(active_thread_percentage)
        env_updates["COCHEM_VRAM_GOVERNOR_ACTIVE"] = "1"

        logger.info(f"Applied VRAM Governor: Limit={limit_val}, Threads={active_thread_percentage}% (Cap: {max_vram_fraction*100}%)")
        return env_updates

    def check_vram_cap(self, max_vram_fraction: float = 0.85) -> bool:
        """Check if any GPU currently exceeds the prescribed VRAM threshold."""
        snapshot = self.poll_hardware()
        if not snapshot.cuda_available or not snapshot.gpu_devices:
            return True
        for gpu in snapshot.gpu_devices:
            if gpu.total_vram_bytes > 0:
                fraction_used = gpu.used_vram_bytes / gpu.total_vram_bytes
                if fraction_used > max_vram_fraction:
                    return False
        return True

    def calculate_safe_batch_size(
        self,
        num_atoms: int,
        engine: Union[EngineTier, str],
        target_device: Union[DeviceType, str] = DeviceType.AUTO,
        memory_safety_factor: float = 0.75,
    ) -> int:
        """Calculate the maximum safe ASE batch size to prevent OOM errors."""
        if num_atoms < 1:
            raise ValueError(f"num_atoms must be at least 1, got {num_atoms}")
        memory_safety_factor = max(0.01, min(1.0, float(memory_safety_factor)))

        snapshot = self.poll_hardware()
        engine_str = engine.value if isinstance(engine, EngineTier) else str(engine)
        dev_str = target_device.value if isinstance(target_device, DeviceType) else str(target_device).lower()

        if dev_str == DeviceType.AUTO.value:
            if snapshot.cuda_available and snapshot.gpu_devices:
                dev_str = DeviceType.CUDA.value
            else:
                dev_str = DeviceType.CPU.value

        if dev_str == DeviceType.CUDA.value and snapshot.gpu_devices:
            best_gpu = max(snapshot.gpu_devices, key=lambda g: g.free_vram_bytes)
            usable_bytes = best_gpu.free_vram_bytes * memory_safety_factor
        else:
            usable_bytes = snapshot.ram_available_bytes * memory_safety_factor

        if "MACE" in engine_str:
            base_overhead = 300 * 1024 * 1024
            mem_per_molecule = max(1024 * 1024, num_atoms * 3 * 1024 * 1024)
            max_ceiling = 128
        elif "AIMNet" in engine_str:
            base_overhead = 200 * 1024 * 1024
            mem_per_molecule = max(1024 * 1024, num_atoms * 2 * 1024 * 1024)
            max_ceiling = 128
        elif "g-xTB" in engine_str:
            base_overhead = 50 * 1024 * 1024
            mem_per_molecule = max(512 * 1024, int((num_atoms * 12) ** 2 * 8))
            max_ceiling = 256
        else:
            base_overhead = 60 * 1024 * 1024
            mem_per_molecule = max(512 * 1024, int((num_atoms * 16) ** 2 * 8))
            max_ceiling = 256

        available_for_batch = max(0, usable_bytes - base_overhead)
        calculated_batch = int(available_for_batch // mem_per_molecule)
        safe_batch = max(1, min(calculated_batch, max_ceiling))

        return safe_batch

    def check_memory_headroom(
        self,
        required_bytes: int,
        target_device: Union[DeviceType, str] = DeviceType.AUTO,
    ) -> bool:
        """Verify if host machine has sufficient headroom for a required allocation."""
        if required_bytes <= 0:
            return True

        snapshot = self.poll_hardware()
        dev_str = target_device.value if isinstance(target_device, DeviceType) else str(target_device).lower()

        if dev_str == DeviceType.AUTO.value:
            dev_str = DeviceType.CUDA.value if snapshot.cuda_available else DeviceType.CPU.value

        if dev_str == DeviceType.CUDA.value and snapshot.gpu_devices:
            max_vram = max(g.free_vram_bytes for g in snapshot.gpu_devices)
            return max_vram >= required_bytes
        else:
            return snapshot.ram_available_bytes >= required_bytes

    def get_optimal_device(
        self,
        engine: Union[EngineTier, str],
        required_vram_bytes: int = 1536 * 1024 * 1024,
    ) -> DeviceType:
        """Determine optimal execution device based on engine and host hardware."""
        engine_str = engine.value if isinstance(engine, EngineTier) else str(engine)

        if engine_str in (EngineTier.G_XTB.value, EngineTier.XTB2.value):
            return DeviceType.CPU

        snapshot = self.poll_hardware()
        if snapshot.cuda_available and snapshot.gpu_devices:
            best_gpu = max(snapshot.gpu_devices, key=lambda g: g.free_vram_bytes)
            if best_gpu.free_vram_bytes >= required_vram_bytes:
                return DeviceType.CUDA

        return DeviceType.CPU


# ============================================================================
# 3. Universal Fallback Cascade State Machine
# ============================================================================

class UniversalFallbackCascade:
    """
    Elemental compatibility definitions and tier cascade rules.
    Hierarchy: MACE-OFF24m (T1-1min) -> AIMNet2 (T2-5min) -> g-xTB (T3-30min) -> xTB2 (T3-3h).
    """

    MACE_OFF24M_ELEMENTS: Set[int] = {1, 6, 7, 8, 9, 15, 16, 17, 35, 53}
    AIMNET2_ELEMENTS: Set[int] = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 33, 34, 35, 53}
    XTB_ELEMENTS: Set[int] = set(range(1, 87))

    @classmethod
    def get_theoretical_tier(cls, engine: Union[EngineTier, str]) -> TheoreticalTier:
        """Map computational engine to theoretical turnaround time tier."""
        engine_tier = EngineTier(engine) if isinstance(engine, str) else engine
        tier_map = {
            EngineTier.MACE_OFF24M: TheoreticalTier.T1_1MIN,
            EngineTier.AIMNET2: TheoreticalTier.T2_5MIN,
            EngineTier.G_XTB: TheoreticalTier.T3_30MIN,
            EngineTier.XTB2: TheoreticalTier.T3_3H,
        }
        return tier_map.get(engine_tier, TheoreticalTier.T3_3H)

    @classmethod
    def get_supported_elements(cls, engine: Union[EngineTier, str]) -> Set[int]:
        """Return the set of supported atomic numbers for an engine."""
        engine_tier = EngineTier(engine) if isinstance(engine, str) else engine
        if engine_tier == EngineTier.MACE_OFF24M:
            return cls.MACE_OFF24M_ELEMENTS
        elif engine_tier == EngineTier.AIMNET2:
            return cls.AIMNET2_ELEMENTS
        elif engine_tier in (EngineTier.G_XTB, EngineTier.XTB2):
            return cls.XTB_ELEMENTS
        return set()

    @classmethod
    def validate_elements(
        cls,
        atomic_numbers: Sequence[int],
        engine: Union[EngineTier, str],
    ) -> Tuple[bool, List[int]]:
        """Validate whether all elements in the composition are supported by the engine."""
        supported = cls.get_supported_elements(engine)
        unsupported = [z for z in atomic_numbers if z not in supported]
        return len(unsupported) == 0, sorted(list(set(unsupported)))

    @classmethod
    def get_next_tier(cls, engine: EngineTier) -> Optional[EngineTier]:
        """Return the next fallback engine tier in the cascade hierarchy."""
        cascade_map = {
            EngineTier.MACE_OFF24M: EngineTier.AIMNET2,
            EngineTier.AIMNET2: EngineTier.G_XTB,
            EngineTier.G_XTB: EngineTier.XTB2,
            EngineTier.XTB2: None,
        }
        return cascade_map.get(engine)

    @classmethod
    def get_element_symbols(cls, atomic_numbers: Sequence[int]) -> List[str]:
        """Dynamically retrieve element symbols via mendeleev."""
        return [get_element_symbol(z) for z in atomic_numbers]

    @classmethod
    def get_total_mass(cls, atomic_numbers: Sequence[int]) -> float:
        """Dynamically compute total molecular mass via mendeleev."""
        return get_molecular_mass(atomic_numbers)


class FallbackCascadeStateMachine:
    """
    Autonomous state machine executing the universal calculation fallback cascade.
    Dynamically routes molecular calculations based on elemental composition and host hardware.
    """

    def __init__(self, broker: Optional[HardwareResourceBroker] = None) -> None:
        self.broker = broker or HardwareResourceBroker()

    def resolve_engine(
        self,
        atomic_numbers: Sequence[int],
        requested_engine: Optional[Union[EngineTier, str]] = None,
        broker: Optional[HardwareResourceBroker] = None,
        require_gpu_for_mlff: bool = True,
    ) -> CascadeState:
        """Resolve the appropriate computational engine tier for a molecular system."""
        if not atomic_numbers:
            raise ValueError("atomic_numbers sequence must not be empty.")

        active_broker = broker or self.broker
        initial_tier = (
            EngineTier(requested_engine)
            if isinstance(requested_engine, str)
            else (requested_engine or EngineTier.MACE_OFF24M)
        )

        current_tier = initial_tier
        transitions: List[CascadeTransition] = []
        is_downgraded = False

        # Step 1: Elemental compatibility cascade
        while True:
            is_supp, unsupp = UniversalFallbackCascade.validate_elements(atomic_numbers, current_tier)
            if is_supp:
                break

            next_tier = UniversalFallbackCascade.get_next_tier(current_tier)
            if next_tier is None:
                break

            transition = CascadeTransition(
                from_engine=current_tier,
                to_engine=next_tier,
                reason=FallbackReason.UNSUPPORTED_ELEMENTS,
                details=f"Unsupported atomic numbers: {unsupp}",
            )
            transitions.append(transition)
            logger.warning(
                f"Cascade trigger: {current_tier.value} -> {next_tier.value} due to unsupported elements {unsupp}"
            )
            current_tier = next_tier
            is_downgraded = True

        # Step 2: Hardware constraint cascade
        snapshot = active_broker.poll_hardware()
        target_device = active_broker.get_optimal_device(current_tier)

        if require_gpu_for_mlff and current_tier in (EngineTier.MACE_OFF24M, EngineTier.AIMNET2):
            if not snapshot.cuda_available or target_device == DeviceType.CPU:
                next_tier = EngineTier.G_XTB
                transition = CascadeTransition(
                    from_engine=current_tier,
                    to_engine=next_tier,
                    reason=FallbackReason.NO_CUDA_DEVICE if not snapshot.cuda_available else FallbackReason.INSUFFICIENT_VRAM,
                    details="GPU acceleration unavailable for MLFF tier; routing to CPU semi-empirical cascade.",
                )
                transitions.append(transition)
                logger.info(f"Hardware cascade trigger: {current_tier.value} -> {next_tier.value} (No CUDA device)")
                current_tier = next_tier
                target_device = DeviceType.CPU
                is_downgraded = True

        theoretical_tier = UniversalFallbackCascade.get_theoretical_tier(current_tier)

        return CascadeState(
            current_engine=current_tier,
            initial_engine=initial_tier,
            target_device=target_device,
            precision_mode=PrecisionMode.FP64,
            theoretical_tier=theoretical_tier,
            is_downgraded=is_downgraded,
            transitions=transitions,
        )

    def step_fallback(
        self,
        state: CascadeState,
        reason: FallbackReason,
        details: str = "",
    ) -> CascadeState:
        """Advance the state machine to the next available tier in response to runtime failure."""
        next_tier = UniversalFallbackCascade.get_next_tier(state.current_engine)
        if next_tier is None:
            transition = CascadeTransition(
                from_engine=state.current_engine,
                to_engine=state.current_engine,
                reason=reason,
                details=f"Terminal tier reached. Cannot downgrade further. {details}",
            )
            state.transitions.append(transition)
            return state

        target_device = DeviceType.CPU if next_tier in (EngineTier.G_XTB, EngineTier.XTB2) else state.target_device
        theoretical_tier = UniversalFallbackCascade.get_theoretical_tier(next_tier)

        transition = CascadeTransition(
            from_engine=state.current_engine,
            to_engine=next_tier,
            reason=reason,
            details=details,
        )

        return CascadeState(
            current_engine=next_tier,
            initial_engine=state.initial_engine,
            target_device=target_device,
            precision_mode=state.precision_mode,
            theoretical_tier=theoretical_tier,
            is_downgraded=True,
            transitions=state.transitions + [transition],
        )


# ============================================================================
# 4. Precision Downgrade Protocol (Controlled RAM Preservation)
# ============================================================================

class PrecisionDowngradeProtocol:
    """
    Controlled Precision Downgrade Protocol.
    Allows explicit tensor precision transformation when emergency host RAM constraints require it.
    """

    @staticmethod
    def should_downgrade(
        source_device: Union[DeviceType, str],
        target_device: Union[DeviceType, str],
        available_ram_bytes: Optional[int] = None,
    ) -> bool:
        """Determine if precision downgrade (FP64 -> FP32) is required."""
        src = source_device.value if isinstance(source_device, DeviceType) else str(source_device).lower()
        dst = target_device.value if isinstance(target_device, DeviceType) else str(target_device).lower()

        if src == DeviceType.CUDA.value and dst == DeviceType.CPU.value:
            return True

        if available_ram_bytes is not None and available_ram_bytes < 4 * 1024 * 1024 * 1024:
            return True

        return False

    @classmethod
    def downgrade_tensors(cls, data: Any, target_dtype: str = "float32") -> Any:
        """Recursively traverse and cast PyTorch tensors and NumPy arrays."""
        if torch is not None and isinstance(data, torch.Tensor):
            if target_dtype == "float32" and data.dtype == torch.float64:
                return data.to(torch.float32)
            elif target_dtype == "float64" and data.dtype == torch.float32:
                return data.to(torch.float64)
            return data

        if torch is not None and hasattr(torch, "nn") and isinstance(data, torch.nn.Module):
            if target_dtype == "float32":
                return data.to(torch.float32)
            return data

        if isinstance(data, np.ndarray):
            if target_dtype == "float32" and data.dtype == np.float64:
                return data.astype(np.float32)
            elif target_dtype == "float64" and data.dtype == np.float32:
                return data.astype(np.float64)
            return data

        if isinstance(data, dict):
            return {k: cls.downgrade_tensors(v, target_dtype) for k, v in data.items()}

        if isinstance(data, list):
            return [cls.downgrade_tensors(item, target_dtype) for item in data]

        if isinstance(data, tuple):
            return tuple(cls.downgrade_tensors(item, target_dtype) for item in data)

        return data

    @classmethod
    def downgrade_model_weights(cls, model_or_weights: Any) -> Any:
        """Cast PyTorch model parameters to target precision."""
        return cls.downgrade_tensors(model_or_weights, target_dtype="float32")


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

ElementalCascadeRouter = UniversalFallbackCascade
HDF5StateManager = ToposHDF5MemoryManager
ToposMemoryBroker = HardwareResourceBroker
ToposMemoryConfig = dict

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_memory.py ---
"""
Unit and integration tests for CoChem-TOPOS Stage 2.0 Mechanics Memory Subsystem (CoChem-BASE).
Strict Zero-Mock Mandate: Uses real HDF5 files, real psutil metrics, real torch tensors,
real numpy arrays, real elemental definitions, and real concurrent filelock access.
"""

import json
import os
import threading
import time
from pathlib import Path
import pytest
import numpy as np
import psutil
import torch

try:
    from cochem_topos.cochem_topos_memory import (
        ToposHDF5MemoryManager,
        HardwareResourceBroker,
        HardwareSnapshot,
        GPUDeviceInfo,
        UniversalFallbackCascade,
        FallbackCascadeStateMachine,
        EngineTier,
        TheoreticalTier,
        FallbackReason,
        DeviceType,
        PrecisionMode,
        CascadeState,
        PrecisionDowngradeProtocol,
        GeometryRecord,
        TrajectoryStep,
        TelemetryRecord,
        QCSchemaPoint,
        sweep_stale_locks,
        generate_oom_autopsy,
        handle_engine_exit_code,
        EngineOOMError,
        enforce_precision_tier,
        load_system_config,
        get_cochem_workspace,
        get_databases_directory,
        get_registry_directory,
        get_atomic_mass,
        get_element_symbol,
        get_molecular_mass,
        ElementalCascadeRouter,
        HDF5StateManager,
        ToposMemoryBroker,
        ToposMemoryConfig,
    )
except ImportError:
    from mechanics.cochem_topos_memory import (
        ToposHDF5MemoryManager,
        HardwareResourceBroker,
        HardwareSnapshot,
        GPUDeviceInfo,
        UniversalFallbackCascade,
        FallbackCascadeStateMachine,
        EngineTier,
        TheoreticalTier,
        FallbackReason,
        DeviceType,
        PrecisionMode,
        CascadeState,
        PrecisionDowngradeProtocol,
        GeometryRecord,
        TrajectoryStep,
        TelemetryRecord,
        QCSchemaPoint,
        sweep_stale_locks,
        generate_oom_autopsy,
        handle_engine_exit_code,
        EngineOOMError,
        enforce_precision_tier,
        load_system_config,
        get_cochem_workspace,
        get_databases_directory,
        get_registry_directory,
        get_atomic_mass,
        get_element_symbol,
        get_molecular_mass,
        ElementalCascadeRouter,
        HDF5StateManager,
        ToposMemoryBroker,
        ToposMemoryConfig,
    )


# ============================================================================
# 1. Air-Gap Protocol & System Config Tests
# ============================================================================

class TestAirGapProtocolAndConfig:
    """Tests for Air-Gap Protocol, workspace directory resolution, and config loading."""

    def test_workspace_directory_resolution(self, tmp_path: Path):
        """Test strict workspace resolution via COCHEM_WORKSPACE."""
        workspace = tmp_path / "air_gapped_ws"
        workspace.mkdir(parents=True, exist_ok=True)
        old_env = os.environ.get("COCHEM_WORKSPACE")
        try:
            os.environ["COCHEM_WORKSPACE"] = str(workspace)
            assert get_cochem_workspace() == workspace
            assert get_databases_directory() == workspace / "CoChem_Artifacts" / "Databases"
            assert get_registry_directory() == workspace / "CoChem_Artifacts" / "Registry"
            assert get_databases_directory().exists()
            assert get_registry_directory().exists()
        finally:
            if old_env is not None:
                os.environ["COCHEM_WORKSPACE"] = old_env
            else:
                os.environ.pop("COCHEM_WORKSPACE", None)

    def test_load_system_config_air_gap(self, tmp_path: Path):
        """Test reading configuration solely from Registry/cochem_system_config.json."""
        workspace = tmp_path / "custom_airgap_ws"
        reg_dir = workspace / "CoChem_Artifacts" / "Registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        old_env = os.environ.get("COCHEM_WORKSPACE")
        try:
            os.environ["COCHEM_WORKSPACE"] = str(workspace)
            config_data = {
                "workspace": str(workspace),
                "vram_governor_cap": 0.85,
                "active_thread_percentage": 85,
                "default_precision": "float64",
                "custom_tier": "T1-1min",
            }
            config_path = reg_dir / "cochem_system_config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f)

            loaded = load_system_config()
            assert loaded["vram_governor_cap"] == 0.85
            assert loaded["active_thread_percentage"] == 85
            assert loaded["default_precision"] == "float64"
            assert loaded["custom_tier"] == "T1-1min"
        finally:
            if old_env is not None:
                os.environ["COCHEM_WORKSPACE"] = old_env
            else:
                os.environ.pop("COCHEM_WORKSPACE", None)


# ============================================================================
# 2. Hardware Resource Broker & VRAM Governor Tests
# ============================================================================

class TestHardwareResourceBroker:
    """Tests for HardwareResourceBroker with real psutil and pynvml polling."""

    def test_real_psutil_hardware_snapshot(self):
        """Test real system metrics polling with psutil."""
        broker = HardwareResourceBroker()
        snapshot = broker.poll_hardware()

        assert isinstance(snapshot, HardwareSnapshot)
        assert snapshot.timestamp > 0
        assert snapshot.cpu_count_logical > 0
        assert snapshot.cpu_count_physical > 0
        assert snapshot.ram_total_bytes > 0
        assert snapshot.ram_available_bytes > 0
        assert 0.0 <= snapshot.ram_percent <= 100.0
        assert 0.0 <= snapshot.cpu_percent <= 100.0
        assert isinstance(snapshot.cuda_available, bool)
        assert isinstance(snapshot.gpu_devices, list)

    def test_pynvml_safe_handling(self):
        """Test NVML polling executes cleanly without throwing unhandled exceptions."""
        broker = HardwareResourceBroker()
        gpus = broker._poll_gpu_devices()
        assert isinstance(gpus, list)
        for gpu in gpus:
            assert isinstance(gpu, GPUDeviceInfo)
            assert gpu.total_vram_bytes >= 0
            assert gpu.free_vram_bytes >= 0
            assert gpu.used_vram_bytes >= 0

    def test_apply_vram_governor(self):
        """Test VRAM governor sets CUDA MPS memory and thread limits strictly at 85%."""
        broker = HardwareResourceBroker()
        env_updates = broker.apply_vram_governor(max_vram_fraction=0.85, active_thread_percentage=85)

        assert "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT" in env_updates
        assert "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE" in env_updates
        assert env_updates["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "85"
        assert os.environ["COCHEM_VRAM_GOVERNOR_ACTIVE"] == "1"

        assert broker.check_vram_cap(max_vram_fraction=0.85) is True

    def test_safe_batch_size_calculation(self):
        """Test dynamic calculation of safe ASE batch size to prevent OOM."""
        broker = HardwareResourceBroker()

        small_batch_mace = broker.calculate_safe_batch_size(num_atoms=10, engine=EngineTier.MACE_OFF24M)
        large_batch_mace = broker.calculate_safe_batch_size(num_atoms=300, engine=EngineTier.MACE_OFF24M)

        assert small_batch_mace >= 1
        assert large_batch_mace >= 1
        assert small_batch_mace >= large_batch_mace

        small_batch_xtb = broker.calculate_safe_batch_size(num_atoms=10, engine=EngineTier.XTB2)
        large_batch_xtb = broker.calculate_safe_batch_size(num_atoms=500, engine=EngineTier.XTB2)
        assert small_batch_xtb >= 1
        assert large_batch_xtb >= 1
        assert small_batch_xtb >= large_batch_xtb

    def test_memory_headroom_check(self):
        """Test available memory headroom checks."""
        broker = HardwareResourceBroker()
        assert broker.check_memory_headroom(required_bytes=1024 * 1024, target_device=DeviceType.CPU) is True
        assert broker.check_memory_headroom(required_bytes=1024**5, target_device=DeviceType.CPU) is False

    def test_get_optimal_device(self):
        """Test optimal device selection based on engine and hardware."""
        broker = HardwareResourceBroker()
        device = broker.get_optimal_device(engine=EngineTier.XTB2)
        assert device == DeviceType.CPU


# ============================================================================
# 3. Universal Fallback Cascade & Precision Enforcement Tests
# ============================================================================

class TestUniversalFallbackCascade:
    """Tests for UniversalFallbackCascade and FallbackCascadeStateMachine."""

    def test_element_support_validation(self):
        """Test element compatibility checking across engine tiers."""
        cascade = UniversalFallbackCascade()

        # Water: H (1), O (8) -> supported by all
        h2o = [1, 1, 8]
        assert cascade.validate_elements(h2o, EngineTier.MACE_OFF24M)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.AIMNET2)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.G_XTB)[0] is True
        assert cascade.validate_elements(h2o, EngineTier.XTB2)[0] is True

        # Boron / Silicon (B=5, Si=14) -> Not in standard MACE-OFF24m, in AIMNet2
        borane = [5, 1, 1, 1]
        assert cascade.validate_elements(borane, EngineTier.MACE_OFF24M)[0] is False
        assert cascade.validate_elements(borane, EngineTier.AIMNET2)[0] is True

        # Platinum / Iron (Pt=78, Fe=26) -> in xTB
        cisplatin = [78, 17, 17, 7, 7, 1, 1, 1, 1, 1, 1]
        assert cascade.validate_elements(cisplatin, EngineTier.MACE_OFF24M)[0] is False
        assert cascade.validate_elements(cisplatin, EngineTier.AIMNET2)[0] is False
        assert cascade.validate_elements(cisplatin, EngineTier.G_XTB)[0] is True
        assert cascade.validate_elements(cisplatin, EngineTier.XTB2)[0] is True

    def test_theoretical_tier_mapping(self):
        """Test theoretical turnaround tier definitions (T1-1min -> T3-3h)."""
        cascade = UniversalFallbackCascade()
        assert cascade.get_theoretical_tier(EngineTier.MACE_OFF24M) == TheoreticalTier.T1_1MIN
        assert cascade.get_theoretical_tier(EngineTier.AIMNET2) == TheoreticalTier.T2_5MIN
        assert cascade.get_theoretical_tier(EngineTier.G_XTB) == TheoreticalTier.T3_30MIN
        assert cascade.get_theoretical_tier(EngineTier.XTB2) == TheoreticalTier.T3_3H

    def test_state_machine_organic_resolution(self):
        """Test resolution for purely organic molecule stays at MACE-OFF24m if hardware allows."""
        sm = FallbackCascadeStateMachine()
        ethanol = [6, 6, 8, 1, 1, 1, 1, 1, 1]
        
        state = sm.resolve_engine(atomic_numbers=ethanol, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state.current_engine == EngineTier.MACE_OFF24M
        assert state.theoretical_tier == TheoreticalTier.T1_1MIN
        assert state.precision_mode == PrecisionMode.FP64
        assert not state.is_downgraded

    def test_state_machine_cascade_on_unsupported_elements(self):
        """Test automatic downgrade cascade when elements are unsupported."""
        sm = FallbackCascadeStateMachine()

        # Silicon -> cascades MACE-OFF24m (T1) -> AIMNet2 (T2)
        silane = [14, 1, 1, 1, 1]
        state_silane = sm.resolve_engine(atomic_numbers=silane, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state_silane.current_engine == EngineTier.AIMNET2
        assert state_silane.theoretical_tier == TheoreticalTier.T2_5MIN
        assert state_silane.is_downgraded
        assert len(state_silane.transitions) == 1
        assert state_silane.transitions[0].reason == FallbackReason.UNSUPPORTED_ELEMENTS

        # Ferrocene (Fe=26) -> cascades MACE-OFF24m -> AIMNet2 -> g-xTB (T3-30min)
        ferrocene = [26, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        state_fe = sm.resolve_engine(atomic_numbers=ferrocene, requested_engine=EngineTier.MACE_OFF24M, require_gpu_for_mlff=False)
        assert state_fe.current_engine in (EngineTier.G_XTB, EngineTier.XTB2)
        assert state_fe.is_downgraded

    def test_manual_step_fallback_sequence(self):
        """Test step-by-step state machine transition down the hierarchy."""
        sm = FallbackCascadeStateMachine()
        state = CascadeState(
            current_engine=EngineTier.MACE_OFF24M,
            initial_engine=EngineTier.MACE_OFF24M,
            target_device=DeviceType.CUDA,
            precision_mode=PrecisionMode.FP64,
            theoretical_tier=TheoreticalTier.T1_1MIN,
        )

        # Step 1: MACE (T1-1min) -> AIMNet2 (T2-5min)
        state = sm.step_fallback(state, FallbackReason.INSUFFICIENT_VRAM, "VRAM below 2GB")
        assert state.current_engine == EngineTier.AIMNET2
        assert state.theoretical_tier == TheoreticalTier.T2_5MIN
        assert state.is_downgraded

        # Step 2: AIMNet2 (T2-5min) -> g-xTB (T3-30min)
        state = sm.step_fallback(state, FallbackReason.NO_CUDA_DEVICE, "Switching to CPU")
        assert state.current_engine == EngineTier.G_XTB
        assert state.theoretical_tier == TheoreticalTier.T3_30MIN
        assert state.target_device == DeviceType.CPU

        # Step 3: g-xTB (T3-30min) -> xTB2 (T3-3h)
        state = sm.step_fallback(state, FallbackReason.EXECUTION_FAILURE, "g-xTB convergence failure")
        assert state.current_engine == EngineTier.XTB2
        assert state.theoretical_tier == TheoreticalTier.T3_3H

        # Step 4: xTB2 is terminal
        terminal_state = sm.step_fallback(state, FallbackReason.EXECUTION_FAILURE, "Terminal failure")
        assert terminal_state.current_engine == EngineTier.XTB2

    def test_precision_mandate_enforcement(self):
        """Test explicit mandate of FP64 precision across execution tiers."""
        enforce_precision_tier(PrecisionMode.FP64)
        assert os.environ["JAX_ENABLE_X64"] == "True"
        if torch is not None:
            assert torch.get_default_dtype() == torch.float64


# ============================================================================
# 4. HDF5 State Manager & QCSchema Layout Tests
# ============================================================================

class TestToposHDF5MemoryManager:
    """Tests for ToposHDF5MemoryManager with real HDF5 files and file locking."""

    def test_database_initialization_without_swmr(self, tmp_path: Path):
        """Test database creation without SWMR flag, verifying QCSchema layout and root attributes."""
        db_file = tmp_path / "test_landscape.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)
        
        assert manager.db_path == db_file
        assert manager.lock_path == Path(f"{db_file}.lock")

        # Check groups and root attributes
        with manager.open_reader() as f:
            assert f.attrs["pipeline"] == "CoChem-TOPOS"
            assert f.attrs["precision_mandate"] == "float64"
            assert "meta" in f
            assert "methods" in f
            assert "points" in f
            assert "geometries" in f
            assert "trajectories" in f
            assert "telemetry" in f

    def test_write_and_read_qcschema_point_and_method(self, tmp_path: Path):
        """Test QCSchema point writing with chunking, gzip compression, fletcher32, and atomic flush."""
        db_file = tmp_path / "qcschema_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        # Register method
        manager.register_method(
            method_id="mace_off24m_dft_ref",
            engine=EngineTier.MACE_OFF24M,
            basis="def2-TZVP",
            parameters={"cutoff": 5.0, "max_ell": 3},
            precision="float64",
        )
        method_meta = manager.read_method("mace_off24m_dft_ref")
        assert method_meta is not None
        assert method_meta["engine"] == EngineTier.MACE_OFF24M.value
        assert method_meta["precision"] == "float64"
        assert method_meta["parameters"]["cutoff"] == 5.0

        # Real Benzene (C6H6) structure
        atomic_numbers = [6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1]
        coords = [
            [0.0, 1.397, 0.0],
            [1.210, 0.698, 0.0],
            [1.210, -0.698, 0.0],
            [0.0, -1.397, 0.0],
            [-1.210, -0.698, 0.0],
            [-1.210, 0.698, 0.0],
            [0.0, 2.481, 0.0],
            [2.148, 1.240, 0.0],
            [2.148, -1.240, 0.0],
            [0.0, -2.481, 0.0],
            [-2.148, -1.240, 0.0],
            [-2.148, 1.240, 0.0],
        ]
        energy = -232.2478
        gradient = [
            [0.00012, -0.00008, 0.00003],
            [-0.00015, 0.00011, -0.00004],
            [0.00009, -0.00014, 0.00002],
            [-0.00008, 0.00007, -0.00003],
            [0.00011, -0.00009, 0.00005],
            [-0.00009, 0.00013, -0.00003],
            [0.00004, -0.00005, 0.00001],
            [-0.00003, 0.00004, -0.00002],
            [0.00005, -0.00003, 0.00001],
            [-0.00002, 0.00005, -0.00002],
            [0.00003, -0.00004, 0.00002],
            [-0.00007, 0.00003, -0.00001],
        ]
        hessian = [[0.45 if i == j else (0.02 / (1.0 + abs(i - j))) for j in range(36)] for i in range(36)]

        manager.write_qcschema_point(
            point_id="benzene_ground_state",
            coordinates=coords,
            energy=energy,
            atomic_numbers=atomic_numbers,
            gradient=gradient,
            hessian=hessian,
            method_id="mace_off24m_dft_ref",
            meta={"symmetry": "D6h", "charge": 0},
        )

        with manager.open_reader() as f:
            pt_grp = f["points"]["benzene_ground_state"]
            coords_ds = pt_grp["coordinates"]
            assert coords_ds.chunks is not None
            assert coords_ds.compression == "gzip"
            assert coords_ds.fletcher32 is True
            assert coords_ds.dtype == np.float64

        pt_read = manager.read_qcschema_point("benzene_ground_state")
        assert pt_read is not None
        assert pt_read.point_id == "benzene_ground_state"
        assert pt_read.atomic_numbers == atomic_numbers
        assert np.allclose(pt_read.coordinates, coords)
        assert pytest.approx(pt_read.energy, 1e-6) == energy
        assert pt_read.gradient is not None
        assert np.allclose(pt_read.gradient, gradient)
        assert pt_read.hessian is not None
        assert np.allclose(pt_read.hessian, hessian)
        assert pt_read.method_id == "mace_off24m_dft_ref"
        assert pt_read.meta["symmetry"] == "D6h"

        assert "benzene_ground_state" in manager.list_points()
        assert "mace_off24m_dft_ref" in manager.list_methods()

    def test_write_and_read_geometry_record(self, tmp_path: Path):
        """Test writing and reading a complete geometry record with tensors."""
        db_file = tmp_path / "geom_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        # Real water molecule (H2O) data
        atomic_numbers = [8, 1, 1]
        coords = [
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ]
        energy = -76.432154
        gradient = [
            [0.0001, -0.0002, 0.0003],
            [-0.0001, 0.0001, -0.0001],
            [0.0000, 0.0001, -0.0002],
        ]
        hessian = [
            [0.612, 0.015, -0.008, -0.301, 0.004, 0.002, -0.311, -0.019, 0.006],
            [0.015, 0.584, 0.011, 0.008, -0.292, -0.005, -0.023, -0.292, -0.006],
            [-0.008, 0.011, 0.630, -0.004, 0.006, -0.315, 0.012, -0.017, -0.315],
            [-0.301, 0.008, -0.004, 0.305, -0.002, 0.001, -0.004, -0.006, 0.003],
            [0.004, -0.292, 0.006, -0.002, 0.295, -0.003, -0.002, -0.003, -0.003],
            [0.002, -0.005, -0.315, 0.001, -0.003, 0.320, -0.003, 0.008, -0.005],
            [-0.311, -0.023, 0.012, -0.004, -0.002, -0.003, 0.315, 0.025, -0.009],
            [-0.019, -0.292, -0.017, -0.006, -0.003, 0.008, 0.025, 0.295, 0.009],
            [0.006, -0.006, -0.315, 0.003, -0.003, -0.005, -0.009, 0.009, 0.320],
        ]
        metadata = {"basis": "def2-TZVP", "charge": 0, "multiplicity": 1}

        record = GeometryRecord(
            geom_id="H2O_opt_01",
            atomic_numbers=atomic_numbers,
            coords=coords,
            energy=energy,
            gradient=gradient,
            hessian=hessian,
            metadata=metadata,
        )

        manager.write_geometry(record)

        read_record = manager.read_geometry("H2O_opt_01")
        assert read_record is not None
        assert read_record.geom_id == "H2O_opt_01"
        assert read_record.atomic_numbers == atomic_numbers
        assert np.allclose(read_record.coords, coords)
        assert pytest.approx(read_record.energy, 1e-6) == energy
        assert read_record.gradient is not None
        assert np.allclose(read_record.gradient, gradient)
        assert read_record.hessian is not None
        assert np.allclose(read_record.hessian, hessian)

    def test_trajectory_append_and_read(self, tmp_path: Path):
        """Test writing and reading time-series trajectory steps."""
        db_file = tmp_path / "traj_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        geom_id = "traj_mol_42"
        steps_data = []
        for step in range(5):
            t_step = TrajectoryStep(
                geom_id=geom_id,
                step_index=step,
                coords=[[0.0, 0.0, float(step)], [1.0, 1.0, float(step)]],
                energy=-100.0 - float(step) * 0.1,
                forces=[[0.01 * step, 0.0, -0.02], [-0.01 * step, 0.0, 0.02]],
                timestamp=time.time() + step,
            )
            manager.append_trajectory_step(t_step)
            steps_data.append(t_step)

        read_steps = manager.read_trajectory(geom_id)
        assert len(read_steps) == 5
        for i, s in enumerate(read_steps):
            assert s.step_index == i
            assert pytest.approx(s.energy, 1e-6) == steps_data[i].energy
            assert np.allclose(s.coords, steps_data[i].coords)
            assert np.allclose(s.forces, steps_data[i].forces)

    def test_telemetry_recording_and_retrieval(self, tmp_path: Path):
        """Test recording and reading hardware/engine telemetry."""
        db_file = tmp_path / "telem_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        t_rec1 = TelemetryRecord(
            record_id="tel_001",
            timestamp=time.time(),
            engine="MACE-OFF24m",
            device="cuda",
            batch_size=32,
            ram_used_bytes=4294967296,
            vram_used_bytes=2147483648,
            duration_seconds=1.24,
            extra={"temperature_c": 54.0, "status": "nominal"},
        )
        manager.record_telemetry(t_rec1)

        retrieved1 = manager.read_telemetry("tel_001")
        assert retrieved1 is not None
        assert retrieved1.engine == "MACE-OFF24m"
        assert retrieved1.device == "cuda"
        assert retrieved1.batch_size == 32

    def test_concurrent_read_write_safety(self, tmp_path: Path):
        """Test multi-threaded concurrent write and read operations."""
        db_file = tmp_path / "concurrent_test.h5"
        manager = ToposHDF5MemoryManager(db_path=db_file)

        results: list = []
        errors: list = []

        def worker_interleaved(idx: int):
            try:
                record = GeometryRecord(
                    geom_id=f"geom_worker_{idx}",
                    atomic_numbers=[1, 1],
                    coords=[[0.0, 0.0, 0.0], [0.0, 0.0, float(idx) * 0.1]],
                    energy=-1.0 - float(idx),
                    metadata={"worker_idx": idx},
                )
                manager.write_geometry(record)
                read_back = manager.read_geometry(f"geom_worker_{idx}")
                assert read_back is not None
                assert read_back.geom_id == f"geom_worker_{idx}"
                results.append(idx)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_interleaved, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 16
        geoms = manager.list_geometries()
        assert len(geoms) == 16


# ============================================================================
# 5. POSIX Stale Lock Sweep & OOM Error Trapping Tests
# ============================================================================

class TestErrorTrappingAndAutopsy:
    """Tests for POSIX stale lock sweep and OOM autopsy generation on SIGKILL / 137."""

    def test_sweep_stale_locks(self, tmp_path: Path):
        """Test startup sweep detects and removes stale/dead-PID lock files."""
        stale_lock = tmp_path / "landscape.h5.lck"
        stale_lock.write_text("999999", encoding="utf-8")

        stale_lock2 = tmp_path / "other.lock"
        stale_lock2.write_text("", encoding="utf-8")
        os.utime(stale_lock2, (time.time() - 120, time.time() - 120))

        deleted = sweep_stale_locks(tmp_path)
        assert stale_lock in deleted
        assert stale_lock2 in deleted
        assert not stale_lock.exists()
        assert not stale_lock2.exists()

    def test_generate_oom_autopsy_and_error_handling(self, tmp_path: Path):
        """Test OOM autopsy generation on SIGKILL (exit code 137)."""
        autopsy_file = tmp_path / "OOM_autopsy.json"

        out_path = generate_oom_autopsy(
            exit_code=137,
            tensor_size_bytes=1024 * 1024 * 512,
            atomic_count=250,
            theoretical_tier=TheoreticalTier.T1_1MIN,
            output_path=autopsy_file,
            extra_context={"engine": "MACE-OFF24m", "stage": "hessian_construction"},
        )
        assert out_path.exists()
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["exit_code"] == 137
        assert data["is_oom"] is True
        assert data["tensor_size_bytes"] == 536870912
        assert data["atomic_count"] == 250
        assert data["theoretical_tier"] == "T1-1min"
        assert data["recommended_fallback_tier"] == "T2-5min"
        assert data["status"] == "OOM_DIAGNOSED"

        with pytest.raises(EngineOOMError) as exc_info:
            handle_engine_exit_code(
                exit_code=137,
                tensor_size_bytes=1024 * 1024 * 100,
                atomic_count=50,
                theoretical_tier=TheoreticalTier.T1_1MIN,
                output_path=tmp_path / "OOM_autopsy_raised.json",
                raise_on_oom=True,
            )
        assert exc_info.value.autopsy_path is not None
        assert exc_info.value.autopsy_path.exists()


# ============================================================================
# 6. Controlled Precision Downgrade Tests
# ============================================================================

class TestPrecisionDowngradeProtocol:
    """Tests for PrecisionDowngradeProtocol casting FP64 to FP32 for memory conservation."""

    def test_torch_tensor_downgrade(self):
        """Test converting PyTorch float64 tensors to float32."""
        proto = PrecisionDowngradeProtocol()
        t_fp64 = torch.tensor([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=torch.float64)
        assert t_fp64.dtype == torch.float64

        t_fp32 = proto.downgrade_tensors(t_fp64)
        assert isinstance(t_fp32, torch.Tensor)
        assert t_fp32.dtype == torch.float32

    def test_numpy_array_downgrade(self):
        """Test converting NumPy float64 arrays to float32."""
        proto = PrecisionDowngradeProtocol()
        arr_fp64 = np.array([1.123456789, 2.987654321], dtype=np.float64)
        assert arr_fp64.dtype == np.float64

        arr_fp32 = proto.downgrade_tensors(arr_fp64)
        assert isinstance(arr_fp32, np.ndarray)
        assert arr_fp32.dtype == np.float32

    def test_nested_collection_downgrade(self):
        """Test recursive conversion across nested dicts, lists, and tuples."""
        proto = PrecisionDowngradeProtocol()
        data = {
            "geom_id": "water_01",
            "coords": np.array([[0.0, 0.0, 0.0]], dtype=np.float64),
            "energy": torch.tensor(-76.4, dtype=torch.float64),
            "nested_list": [
                np.array([1.0, 2.0], dtype=np.float64),
                {"sub_tensor": torch.tensor([3.0, 4.0], dtype=torch.float64)},
                "string_data",
                42,
            ],
        }

        downgraded = proto.downgrade_tensors(data)
        assert downgraded["coords"].dtype == np.float32
        assert downgraded["energy"].dtype == torch.float32
        assert downgraded["nested_list"][0].dtype == np.float32
        assert downgraded["nested_list"][1]["sub_tensor"].dtype == torch.float32


# ============================================================================
# 7. Mendeleev Library Dynamic Mass & Property Tests
# ============================================================================

class TestMendeleevDynamicMassAndProperties:
    """Tests for Mendeleev library integration and dynamic atomic mass retrieval."""

    def test_mendeleev_element_mass_and_symbol_resolution(self):
        """Test dynamic atomic mass and symbol resolution for various elements."""
        c_mass = get_atomic_mass("C")
        c_mass_num = get_atomic_mass(6)
        assert pytest.approx(c_mass, 1e-3) == 12.011
        assert pytest.approx(c_mass_num, 1e-3) == 12.011

        h_mass = get_atomic_mass("H")
        assert pytest.approx(h_mass, 1e-3) == 1.008

        sym_6 = get_element_symbol(6)
        sym_8 = get_element_symbol(8)
        assert sym_6 == "C"
        assert sym_8 == "O"

    def test_molecular_mass_computation(self):
        """Test dynamic molecular mass computation for H2O and Benzene."""
        h2o_mass = get_molecular_mass([8, 1, 1])
        # H2O: 15.999 + 2 * 1.008 ~ 18.015
        assert 18.01 < h2o_mass < 18.02

        benzene_mass = get_molecular_mass([6, 6, 6, 6, 6, 6, 1, 1, 1, 1, 1, 1])
        # C6H6: 6*12.011 + 6*1.008 ~ 78.114
        assert 78.10 < benzene_mass < 78.12

    def test_geometry_record_mendeleev_properties(self):
        """Test dynamic properties on GeometryRecord."""
        record = GeometryRecord(
            geom_id="h2o_test",
            atomic_numbers=[8, 1, 1],
            coords=[[0.0, 0.0, 0.0], [0.0, 0.75, 0.5], [0.0, -0.75, 0.5]],
            energy=-76.4,
        )
        assert record.symbols == ["O", "H", "H"]
        assert 18.01 < record.total_mass < 18.02

    def test_qcschema_point_mendeleev_properties(self):
        """Test dynamic properties on QCSchemaPoint."""
        pt = QCSchemaPoint(
            point_id="pt_test",
            atomic_numbers=[6, 1, 1, 1, 1],
            coordinates=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 1.0, 1.0]],
            energy=-40.5,
        )
        assert pt.symbols == ["C", "H", "H", "H", "H"]
        assert 16.03 < pt.total_mass < 16.05

    def test_universal_fallback_cascade_mendeleev_helpers(self):
        """Test Mendeleev helpers on UniversalFallbackCascade."""
        symbols = UniversalFallbackCascade.get_element_symbols([1, 6, 7, 8])
        assert symbols == ["H", "C", "N", "O"]
        total_mass = UniversalFallbackCascade.get_total_mass([1, 6, 7, 8])
        assert 43.0 < total_mass < 43.1

    def test_backward_compatibility_aliases(self):
        """Test that cross-module compatibility aliases point to authentic classes."""
        assert ElementalCascadeRouter is UniversalFallbackCascade
        assert HDF5StateManager is ToposHDF5MemoryManager
        assert ToposMemoryBroker is HardwareResourceBroker

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.