Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TOPOS\.in-progress\10_01_escalation_iso_recycle.md.
Original prompt:
# Task: Implement Isotopologue Hessian Recycling (`cochem_topos_iso_recycle.py`)

## Target Output File
`${COCHEM_WORKSPACE}\GitHub-Repo\CoChem-TOPOS\escalation\cochem_topos_iso_recycle.py`

## Objective
Mathematically extrapolate pre-existing quantum data to generate new insights (isotopologues) without additional compute cost.

## Context & Architecture Rules
This module (Stage 4.1) exploits the Born-Oppenheimer approximation, injecting exact masses into the Cartesian Hessian tensor to instantly diagonalize isotopologue vibrational frequencies.

**Compliance Directives:**
- **Air-Gap Enforcement**: ALL paths (including `landscape.h5`) MUST be resolved dynamically via `os.environ` (e.g., `COCHEM_WORKSPACE`) or `pathlib.Path.home()`. Force all outputs into a configurable artifacts directory. NO hardcoded absolute paths.
- **Rigorous Typing**: Apply exhaustive Python 3.10+ type hints.
- **Graceful Failure**: Use robust error handling (`try/except`). Replace `print()` with `logging`.
- No mock data, stubs, or placeholders are allowed.

## Execution Directives
Implement the `cochem_topos_iso_recycle.py` script with the following capabilities:

1. **Baseline Hessian Extraction**: Extract the converged, baseline Cartesian Hessian tensor (H, 3Nx3N matrix) directly from `landscape.h5` SWMR database.
2. **Exact Mass Injection**: Read requested isotopologue substitutions and query the `mendeleev` library to inject exact mono-isotopic masses into the atomic mass array.
3. **First-Order Isotopic Mass Perturbation**: Compute the mass-weighted Hessian matrix (F): $F_{ij} = H_{ij} / \sqrt{m_i m_j}$.
4. **Eigen-Decomposition**: Utilize `scipy.linalg.eigh` to diagonalize F to yield exact isotopologue vibrational frequencies ($\nu \propto \sqrt{\lambda}$) and Zero-Point Vibrational Energies (ZPE) in milliseconds.
5. **SWMR State Update**: Securely append derived isotopologue frequencies and thermal corrections to the `/isotopologues/` group in `landscape.h5`.

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

def enforce_precision_tier(mode: PrecisionMode = PrecisionMode.FP64, set_torch_default: bool = False) -> None:
    """
    Explicitly mandate FP64 (or configured mode) precision across all execution tiers.
    Sets JAX_ENABLE_X64=True/False in the environment.
    """
    if mode == PrecisionMode.FP64:
        os.environ["JAX_ENABLE_X64"] = "True"
        if set_torch_default and torch is not None:
            try:
                torch.set_default_dtype(torch.float64)
            except Exception as e:
                logger.debug(f"Could not set torch default dtype to float64: {e}")
    elif mode == PrecisionMode.FP32:
        os.environ["JAX_ENABLE_X64"] = "False"
        if set_torch_default and torch is not None:
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
        orig_jax = os.environ.get("JAX_ENABLE_X64")
        orig_torch = torch.get_default_dtype() if torch is not None else None
        try:
            enforce_precision_tier(PrecisionMode.FP64, set_torch_default=True)
            assert os.environ["JAX_ENABLE_X64"] == "True"
            if torch is not None:
                assert torch.get_default_dtype() == torch.float64
        finally:
            if orig_jax is not None:
                os.environ["JAX_ENABLE_X64"] = orig_jax
            else:
                os.environ.pop("JAX_ENABLE_X64", None)
            if torch is not None and orig_torch is not None:
                torch.set_default_dtype(orig_torch)


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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_topos\cochem_topos_iso_recycle.py ---
"""
CoChem-TOPOS: Stage 4.1 - Isotopologue Hessian Recycling & Isotopic Perturbation Engine
(cochem_topos_iso_recycle.py)

Leverages the Born-Oppenheimer potential energy surface (PES) mass invariance to mathematically
bypass the need for multi-day quantum electronic frequency recalculations for heavy isotopes
(e.g., Deuterium, 13C, 15N, 18O, 34S, 37Cl).

Execution Directives:
1. Baseline Cartesian Hessian Extraction:
   - Reads converged 3Nx3N Cartesian Hessian tensors and equilibrium geometries directly from
     `landscape.h5` across the Interaction/Mechanics layer.
2. Exact Mono-Isotopic Mass Injection:
   - Queries `mendeleev` for exact, high-precision isotopic masses in Daltons (e.g. 1H=1.00782503 Da,
     D=2.01410178 Da, 12C=12.00000000 Da, 13C=13.00335484 Da, 16O=15.99491462 Da, 18O=17.99915961 Da).
3. First-Order Isotopic Mass Perturbation:
   - Computes the mass-weighted Hessian matrix F_ij = H_ij / sqrt(m_i * m_j).
   - Solves the secular eigenvalue equation F L = L Lambda via scipy.linalg.eigh.
4. Harmonic Thermochemistry & Zero-Point Energy (ZPE):
   - Computes exact harmonic vibrational frequencies (cm^-1), Zero-Point Energies (ZPE in Hartree,
     kcal/mol, kJ/mol, eV), and thermal vibrational free energy corrections at arbitrary temperatures.
5. Kinetic & Thermodynamic Isotope Effects (KIE / TIE):
   - Evaluates semiclassical Bigeleisen-Mayer isotope effect ratios with optional Wigner tunneling corrections.
6. SWMR HDF5 Persistence Layer:
   - Persists calculated isotopologue ensembles directly to `/isotopologues/{geom_id}/{isotopologue_id}`
     with process-safe file locks and SHA-256 provenance hashing.

Strictly complies with the Tripartite Air-Gap Policy and Zero-Mock Mandate.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import math
import os
import re
import time
from collections.abc import Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import h5py
import mendeleev  # type: ignore[import-untyped]
import numpy as np
from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from scipy import linalg as sla  # type: ignore[import-untyped]

# Internal Mechanics Memory Subsystem Imports
try:
    from mechanics.cochem_topos_memory import (
        GeometryRecord,
        ToposHDF5MemoryManager,
    )
except ImportError:
    try:
        from cochem_topos.cochem_topos_memory import (  # type: ignore[import-not-found,no-redef]
            GeometryRecord,
            ToposHDF5MemoryManager,
        )
    except ImportError:
        try:
            from cochem_topos_memory import (  # type: ignore[import-not-found,no-redef]
                GeometryRecord,
                ToposHDF5MemoryManager,
            )
        except ImportError:
            GeometryRecord = None  # type: ignore[assignment,misc]
            ToposHDF5MemoryManager = None  # type: ignore[assignment,misc]

# Module Logger
logger = logging.getLogger("CoChem.TOPOS.IsoRecycle")


# ============================================================================
# Physical Constants & Unit Conversion Factors (CODATA 2018 / 2022 Standards)
# ============================================================================

SPEED_OF_LIGHT_CM_S: float = 2.99792458e10
PLANCK_CONSTANT_J_S: float = 6.62607015e-34
HBAR_J_S: float = 1.054571817e-34
AVOGADRO_NUMBER: float = 6.02214076e23
BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
GAS_CONSTANT_R_J_MOL_K: float = 8.314462618
GAS_CONSTANT_R_CAL_MOL_K: float = 1.98720425864083

# Mass & Energy Conversions
AMU_TO_KG: float = 1.66053906660e-27
EV_TO_JOULE: float = 1.602176634e-19
HARTREE_TO_JOULE: float = 4.3597447222071e-18
HARTREE_TO_KCAL_MOL: float = 627.5094740631
HARTREE_TO_KJ_MOL: float = 2625.4996394799
HARTREE_TO_EV: float = 27.211386245988
HARTREE_TO_CM1: float = 219474.63136320
BOHR_TO_ANGSTROM: float = 0.529177210903
ANGSTROM_TO_METER: float = 1.0e-10

# Frequency Conversion Factors for various input Hessian units to cm^-1:
# Derived from exact CODATA constants: nu = sqrt(k_SI / m_SI) / (2 * pi * c)
# where k_SI = k_unit * UNIT_TO_JOULE / UNIT_TO_METER^2, m_SI = m_amu * AMU_TO_KG
HESSIAN_EV_ANGSTROM2_TO_CM1: float = math.sqrt(
    EV_TO_JOULE / (ANGSTROM_TO_METER**2 * AMU_TO_KG)
) / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
HESSIAN_HARTREE_BOHR2_TO_CM1: float = math.sqrt(
    HARTREE_TO_JOULE / ((BOHR_TO_ANGSTROM * ANGSTROM_TO_METER) ** 2 * AMU_TO_KG)
) / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
HESSIAN_HARTREE_ANGSTROM2_TO_CM1: float = math.sqrt(
    HARTREE_TO_JOULE / (ANGSTROM_TO_METER**2 * AMU_TO_KG)
) / (2.0 * math.pi * SPEED_OF_LIGHT_CM_S)
HESSIAN_SI_TO_CM1: float = math.sqrt(1.0 / AMU_TO_KG) / (
    2.0 * math.pi * SPEED_OF_LIGHT_CM_S
)


class HessianUnit(str, Enum):
    """Supported physical units for input Cartesian Hessian matrices."""
    EV_PER_ANGSTROM2 = "ev_angstrom2"
    HARTREE_PER_BOHR2 = "hartree_bohr2"
    HARTREE_PER_ANGSTROM2 = "hartree_angstrom2"
    J_PER_M2 = "j_m2"


HESSIAN_UNIT_FACTORS: dict[HessianUnit, float] = {
    HessianUnit.EV_PER_ANGSTROM2: HESSIAN_EV_ANGSTROM2_TO_CM1,
    HessianUnit.HARTREE_PER_BOHR2: HESSIAN_HARTREE_BOHR2_TO_CM1,
    HessianUnit.HARTREE_PER_ANGSTROM2: HESSIAN_HARTREE_ANGSTROM2_TO_CM1,
    HessianUnit.J_PER_M2: HESSIAN_SI_TO_CM1,
}

# ============================================================================
# Exact Mono-Isotopic Mass Resolution via Mendeleev
# ============================================================================


@lru_cache(maxsize=1024)
def get_exact_isotopic_mass(
    symbol_or_z: str | int,
    mass_number: int | None = None,
) -> float:
    """Query Mendeleev to retrieve the exact monoisotopic mass (Daltons).

    Supports isotope symbols such as 'D', 'T', '13C', '18O', '15N', '37Cl',
    or passing atomic symbol and optional integer mass_number explicitly.
    """
    if isinstance(symbol_or_z, int | np.integer):
        z = int(symbol_or_z)
        if z < 1 or z > 118:
            raise ValueError(f"Atomic number Z={z} is out of physical range [1, 118].")
        el = mendeleev.element(z)
        sym = str(el.symbol)
    elif isinstance(symbol_or_z, str):
        s = symbol_or_z.strip()
        if not s:
            raise ValueError("Empty element symbol string provided.")

        if s.isdigit():
            z = int(s)
            if z < 1 or z > 118:
                raise ValueError(f"Atomic number Z={z} is out of physical range [1, 118].")
            el = mendeleev.element(z)
            sym = str(el.symbol)
        else:
            match = re.match(r"^(\d+)([A-Za-z]+)$", s)
            if match:
                prefix_mass_num = int(match.group(1))
                parsed_sym = match.group(2).capitalize()
                sym = parsed_sym
                if mass_number is None:
                    mass_number = prefix_mass_num
            else:
                s_upper = s.upper()
                if s_upper in ("D", "2H"):
                    return 2.014101778
                if s_upper in ("T", "3H"):
                    return 3.016049281
                sym = s.capitalize()
    else:
        raise TypeError(f"Expected str or int for element identifier, got {type(symbol_or_z).__name__}.")

    if sym in ("D", "T") or (sym == "H" and mass_number in (2, 3)):
        if sym == "D" or mass_number == 2:
            return 2.014101778
        if sym == "T" or mass_number == 3:
            return 3.016049281

    try:
        el = mendeleev.element(sym)
    except Exception as exc:
        raise ValueError(f"Element symbol '{sym}' not recognized by Mendeleev database: {exc}") from exc

    if mass_number is not None:
        target_iso = next((i for i in el.isotopes if i.mass_number == mass_number), None)
        if target_iso is None or target_iso.mass is None:
            raise ValueError(f"No isotope with mass number {mass_number} found for element '{sym}'.")
        return float(target_iso.mass)

    abundant_isotopes = [
        iso for iso in el.isotopes if iso.abundance is not None and iso.abundance > 0
    ]
    if abundant_isotopes:
        primary_iso = max(abundant_isotopes, key=lambda x: x.abundance)
        return float(primary_iso.mass)

    valid_isotopes = [iso for iso in el.isotopes if iso.mass is not None]
    if valid_isotopes:
        stable_iso = max(
            valid_isotopes, key=lambda x: (x.half_life if x.half_life is not None else 0)
        )
        return float(stable_iso.mass)

    if el.atomic_weight is not None:
        return float(el.atomic_weight)

    return float(el.atomic_number)


def get_isotopic_masses(
    symbols_or_zs: Sequence[str | int],
    substitutions: Optional[Dict[Union[int, str], Union[str, int, float]]] = None,
) -> np.ndarray:
    """Construct a 1D NumPy array of isotopic masses for an atomic sequence.

    Applies optional dictionary substitutions:
    - Index-based: `{1: 'D', 2: 18}`
    - Element-based: `{'H': 'D', 'C': 13}`
    - Direct float mass override: `{0: 2.014101778}`
    """
    masses: list[float] = []
    subs = substitutions or {}

    for idx, sym_or_z in enumerate(symbols_or_zs):
        if idx in subs:
            sub_val = subs[idx]
            if isinstance(sub_val, float | int | np.floating | np.integer) and not isinstance(sub_val, bool):
                val = float(sub_val)
                if isinstance(sub_val, int | np.integer) and val <= 300:
                    masses.append(get_exact_isotopic_mass(sym_or_z, mass_number=int(val)))
                else:
                    masses.append(val)
            elif isinstance(sub_val, str):
                masses.append(get_exact_isotopic_mass(sub_val))
            else:
                raise TypeError(f"Invalid substitution type for index {idx}: {type(sub_val)}")
            continue

        norm_sym = str(sym_or_z).strip().capitalize()
        if norm_sym in subs:
            sub_val = subs[norm_sym]
            if isinstance(sub_val, int | np.integer):
                masses.append(get_exact_isotopic_mass(norm_sym, mass_number=int(sub_val)))
            elif isinstance(sub_val, float | np.floating):
                masses.append(float(sub_val))
            elif isinstance(sub_val, str):
                masses.append(get_exact_isotopic_mass(sub_val))
            else:
                raise TypeError(f"Invalid element substitution type for {norm_sym}: {type(sub_val)}")
            continue

        masses.append(get_exact_isotopic_mass(sym_or_z))

    return np.array(masses, dtype=np.float64)


# ============================================================================
# Pydantic Schemas & Data Models
# ============================================================================


class IsotopeSubstitution(BaseModel):
    """Metadata for an individual isotopic substitution site."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    atom_index: int
    element_symbol: str
    mass_number: int
    exact_mass_da: float
    baseline_mass_da: float


class IsotopologueDefinition(BaseModel):
    """Specification defining an isotopologue candidate."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    isotopologue_id: str
    substitutions: Dict[Union[int, str], Union[str, int, float]] = Field(default_factory=dict)
    custom_masses: Optional[List[float]] = None
    description: str = ""


class NormalMode(BaseModel):
    """Vibrational normal mode eigenvector, frequency, and properties."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    mode_index: int
    frequency_cm1: float
    eigenvalue: float
    is_imaginary: bool
    is_vibrational: bool
    reduced_mass_amu: float = 0.0
    force_constant_mdyn_angstrom: float = 0.0
    mass_weighted_displacement: List[List[float]] = Field(default_factory=list)
    cartesian_displacement: List[List[float]] = Field(default_factory=list)


class ThermochemicalCorrections(BaseModel):
    """Harmonic vibrational thermochemical corrections at temperature T."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    temperature_k: float
    pressure_atm: float = 1.0
    zpe_hartree: float
    zpe_kcal_mol: float
    zpe_kj_mol: float
    zpe_ev: float
    thermal_energy_hartree: float
    thermal_enthalpy_hartree: float
    thermal_free_energy_hartree: float
    entropy_cal_mol_k: float
    heat_capacity_cal_mol_k: float
    vibrational_partition_function: float


class VibrationalAnalysis(BaseModel):
    """Complete vibrational and normal mode analysis container."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    frequencies_cm1: List[float]
    eigenvalues: List[float]
    num_imaginary: int
    has_imaginary_modes: bool
    zpe_hartree: float
    zpe_kcal_mol: float
    zpe_kj_mol: float
    zpe_ev: float
    modes: List[NormalMode] = Field(default_factory=list)

    @classmethod
    def from_frequencies(
        cls,
        frequencies_cm1: Sequence[float],
        eigenvalues: Sequence[float],
        modes: Optional[List[NormalMode]] = None,
    ) -> VibrationalAnalysis:
        """Construct VibrationalAnalysis from frequency and eigenvalue arrays."""
        freqs = [float(f) for f in frequencies_cm1]
        eigs = [float(e) for e in eigenvalues]

        positive_freqs = [f for f in freqs if f > 0.0]
        sum_freqs_cm1 = sum(positive_freqs)

        zpe_cm1 = 0.5 * sum_freqs_cm1
        zpe_ha = zpe_cm1 / HARTREE_TO_CM1
        zpe_kcal = zpe_ha * HARTREE_TO_KCAL_MOL
        zpe_kj = zpe_ha * HARTREE_TO_KJ_MOL
        zpe_ev = zpe_ha * HARTREE_TO_EV

        num_imag = sum(1 for f in freqs if f < 0.0)

        return cls(
            frequencies_cm1=freqs,
            eigenvalues=eigs,
            num_imaginary=num_imag,
            has_imaginary_modes=(num_imag > 0),
            zpe_hartree=zpe_ha,
            zpe_kcal_mol=zpe_kcal,
            zpe_kj_mol=zpe_kj,
            zpe_ev=zpe_ev,
            modes=modes or [],
        )

    def compute_thermochemistry(
        self,
        temperature_k: float = 298.15,
        pressure_atm: float = 1.0,
        low_freq_cutoff_cm1: float = 10.0,
    ) -> ThermochemicalCorrections:
        """Evaluate harmonic vibrational partition functions and thermal corrections."""
        if temperature_k <= 0.0:
            raise ValueError(f"Temperature must be strictly positive, got {temperature_k} K.")

        beta_factor = (PLANCK_CONSTANT_J_S * SPEED_OF_LIGHT_CM_S) / BOLTZMANN_CONSTANT_J_K

        u_vib_j_mol = 0.0
        cv_vib_j_mol_k = 0.0
        s_vib_j_mol_k = 0.0
        ln_q_vib = 0.0

        for nu in self.frequencies_cm1:
            if nu <= low_freq_cutoff_cm1:
                continue

            x = (beta_factor * nu) / temperature_k
            if x <= 0:
                continue

            if x > 100.0:
                u_vib_j_mol += 0.0
                cv_vib_j_mol_k += 0.0
                s_vib_j_mol_k += 0.0
                ln_q_vib += 0.0
            else:
                exp_x = math.exp(x)
                denom = exp_x - 1.0
                if denom > 1e-15:
                    u_vib_j_mol += GAS_CONSTANT_R_J_MOL_K * temperature_k * (x / denom)
                    cv_vib_j_mol_k += GAS_CONSTANT_R_J_MOL_K * (x**2) * (exp_x / (denom**2))
                    s_vib_j_mol_k += GAS_CONSTANT_R_J_MOL_K * ((x / denom) - math.log(1.0 - math.exp(-x)))
                    ln_q_vib += -math.log(1.0 - math.exp(-x))

        u_vib_ha = u_vib_j_mol / (HARTREE_TO_JOULE * AVOGADRO_NUMBER)
        thermal_energy_ha = self.zpe_hartree + u_vib_ha
        thermal_enthalpy_ha = thermal_energy_ha

        s_vib_cal = s_vib_j_mol_k / 4.184
        cv_vib_cal = cv_vib_j_mol_k / 4.184

        ts_j_mol = temperature_k * s_vib_j_mol_k
        ts_ha = ts_j_mol / (HARTREE_TO_JOULE * AVOGADRO_NUMBER)
        thermal_free_energy_ha = thermal_enthalpy_ha - ts_ha

        q_vib = math.exp(min(ln_q_vib, 700.0))

        return ThermochemicalCorrections(
            temperature_k=temperature_k,
            pressure_atm=pressure_atm,
            zpe_hartree=self.zpe_hartree,
            zpe_kcal_mol=self.zpe_kcal_mol,
            zpe_kj_mol=self.zpe_kj_mol,
            zpe_ev=self.zpe_ev,
            thermal_energy_hartree=thermal_energy_ha,
            thermal_enthalpy_hartree=thermal_enthalpy_ha,
            thermal_free_energy_hartree=thermal_free_energy_ha,
            entropy_cal_mol_k=s_vib_cal,
            heat_capacity_cal_mol_k=cv_vib_cal,
            vibrational_partition_function=q_vib,
        )


class IsotopologueRecycleResult(BaseModel):
    """Comprehensive result container for an isotopologue recycling calculation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    geom_id: str
    isotopologue_id: str
    symbols: List[str]
    baseline_masses: List[float]
    substituted_masses: List[float]
    baseline_zpe_kcal_mol: float
    isotopologue_zpe_kcal_mol: float
    delta_zpe_kcal_mol: float
    baseline_frequencies_cm1: List[float]
    isotopologue_frequencies_cm1: List[float]
    vibrational_analysis: VibrationalAnalysis
    thermochemistry_298k: ThermochemicalCorrections
    substitutions_applied: List[IsotopeSubstitution] = Field(default_factory=list)
    calculation_time_ms: float = 0.0
    provenance_sha256: str = ""


class HarmonicKIE(BaseModel):
    """Kinetic Isotope Effect (KIE) estimation between light and heavy isotopologues."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    temperature_k: float
    kie_ratio: float
    delta_zpe_diff_kcal_mol: float
    reactant_light_zpe_kcal_mol: float
    ts_light_zpe_kcal_mol: float
    reactant_heavy_zpe_kcal_mol: float
    ts_heavy_zpe_kcal_mol: float
    wigner_tunneling_correction_light: float = 1.0
    wigner_tunneling_correction_heavy: float = 1.0


class BatchRecycleReport(BaseModel):
    """Aggregated report for batch isotopologue recycling."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    geom_id: str
    total_calculated: int
    results: List[IsotopologueRecycleResult]
    baseline_level_of_theory: str = "Unknown"
    timestamp: float = Field(default_factory=time.time)

# ============================================================================
# Core Mathematical Functions
# ============================================================================


def mass_weight_hessian(
    hessian: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """Construct the mass-weighted Cartesian Hessian matrix F.

    Equation:
        F_ij = H_ij / sqrt(m_i * m_j)
    where m_i is the mass of the atom corresponding to Cartesian coordinate i.
    """
    H = np.asarray(hessian, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)

    if H.ndim != 2 or H.shape[0] != H.shape[1]:
        raise ValueError(f"Hessian must be a square 2D matrix, got shape {H.shape}.")

    n_coords = H.shape[0]
    n_atoms = len(m)

    if n_coords != 3 * n_atoms:
        raise ValueError(
            f"Dimension mismatch: Hessian shape {H.shape} incompatible with {n_atoms} atom masses (expected {3 * n_atoms}x{3 * n_atoms})."
        )

    if np.any(m <= 0.0):
        raise ValueError("All atomic masses must be strictly positive.")

    m_coords = np.repeat(m, 3)
    inv_sqrt_m = 1.0 / np.sqrt(m_coords)

    F = H * np.outer(inv_sqrt_m, inv_sqrt_m)
    F = 0.5 * (F + F.T)
    return F


def project_translations_rotations(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """Construct the Eckart translational and rotational projection operator P.

    Projects out 6 (or 5 for linear) zero-frequency external modes:
        P = I - D * (D^T * D)^-1 * D^T
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)
    n_atoms = len(m)

    if coords.shape != (n_atoms, 3):
        raise ValueError(f"Coordinates shape {coords.shape} != ({n_atoms}, 3).")

    total_mass = float(np.sum(m))
    com = np.sum(coords * m[:, np.newaxis], axis=0) / total_mass
    r = coords - com

    m_coords = np.repeat(m, 3)
    sqrt_m = np.sqrt(m_coords)

    D = np.zeros((3 * n_atoms, 6), dtype=np.float64)
    for i in range(n_atoms):
        s_m = np.sqrt(m[i])
        D[3 * i + 0, 0] = s_m
        D[3 * i + 1, 1] = s_m
        D[3 * i + 2, 2] = s_m

        rx, ry, rz = r[i]
        D[3 * i + 1, 3] = -rz * s_m
        D[3 * i + 2, 3] = ry * s_m
        D[3 * i + 0, 4] = rz * s_m
        D[3 * i + 2, 4] = -rx * s_m
        D[3 * i + 0, 5] = -ry * s_m
        D[3 * i + 1, 5] = rx * s_m

    # Use SVD to isolate non-zero singular vectors (handles non-linear rank 6 and linear/diatomic rank 5)
    u, s, _ = np.linalg.svd(D, full_matrices=False)
    q = u[:, s > 1e-7]
    I = np.eye(3 * n_atoms, dtype=np.float64)
    P = I - q @ q.T
    return P


def recycle_hessian_frequencies(
    hessian: Union[np.ndarray, Sequence[Sequence[float]]],
    symbols: Sequence[str | int],
    coordinates: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    substitutions: Optional[Dict[Union[int, str], Union[str, int, float]]] = None,
    custom_masses: Optional[Sequence[float]] = None,
    unit: Union[HessianUnit, str] = HessianUnit.EV_PER_ANGSTROM2,
    project_tr: bool = False,
    temperature_k: float = 298.15,
) -> VibrationalAnalysis:
    """Core mathematical kernel to compute exact vibrational frequencies and normal modes.

    First-Order Isotopic Mass Perturbation:
    1. Injects exact mono-isotopic masses into the mass array.
    2. Constructs the mass-weighted Hessian F = M^{-1/2} H M^{-1/2}.
    3. Solves the secular eigenvalue problem F L = L Lambda via scipy.linalg.eigh.
    4. Converts eigenvalues to wavenumbers (cm^-1) and Zero-Point Energies.
    """
    H = np.asarray(hessian, dtype=np.float64)
    n_atoms = len(symbols)

    if H.shape != (3 * n_atoms, 3 * n_atoms):
        raise ValueError(
            f"Dimension mismatch: Hessian shape {H.shape} incompatible with {n_atoms} symbols."
        )

    if not np.all(np.isfinite(H)):
        raise ValueError("Hessian contains non-finite values (NaN or Inf).")

    if custom_masses is not None:
        masses = np.asarray(custom_masses, dtype=np.float64)
        if len(masses) != n_atoms:
            raise ValueError(f"Custom masses length {len(masses)} != atom count {n_atoms}.")
    else:
        masses = get_isotopic_masses(symbols, substitutions=substitutions)

    F = mass_weight_hessian(H, masses)

    if project_tr and coordinates is not None:
        P = project_translations_rotations(coordinates, masses)
        F = P @ F @ P
        F = 0.5 * (F + F.T)

    eigenvalues, eigenvectors = sla.eigh(F)

    if isinstance(unit, str):
        unit = HessianUnit(unit.lower())
    conversion_factor = HESSIAN_UNIT_FACTORS.get(unit, HESSIAN_EV_ANGSTROM2_TO_CM1)

    frequencies_cm1: list[float] = []
    modes: list[NormalMode] = []
    m_coords = np.repeat(masses, 3)

    for idx, eigval in enumerate(eigenvalues):
        is_imag = eigval < 0.0
        abs_eig = abs(eigval)

        freq_magnitude = conversion_factor * math.sqrt(abs_eig)
        freq_signed = -freq_magnitude if is_imag else freq_magnitude

        frequencies_cm1.append(freq_signed)

        mw_vec = eigenvectors[:, idx]
        cart_vec = mw_vec / np.sqrt(m_coords)
        norm_cart = np.linalg.norm(cart_vec)
        if norm_cart > 1e-15:
            cart_vec = cart_vec / norm_cart

        mw_disp = mw_vec.reshape((n_atoms, 3)).tolist()
        cart_disp = cart_vec.reshape((n_atoms, 3)).tolist()

        # Standard Gaussian normal mode reduced mass mu = 1 / sum(l_cart_norm^2 / m_i)
        sum_disp_sq = sum(np.sum(np.array(cart_disp[i])**2) / masses[i] for i in range(n_atoms))
        red_mass = (1.0 / sum_disp_sq) if sum_disp_sq > 1e-15 else 0.0

        is_vib = abs(freq_magnitude) > 10.0

        # Harmonic force constant in mdyn/Angstrom: k = 4*pi^2*c^2*AMU_TO_KG/100 * nu^2 * mu
        # Constant factor = 5.89183044236737e-7 mdyn/(Angstrom * cm^-2 * amu)
        k_force_constant = (
            5.89183044236737e-7 * (freq_magnitude**2) * red_mass
            if red_mass > 0.0
            else 0.0
        )

        mode = NormalMode(
            mode_index=idx,
            frequency_cm1=freq_signed,
            eigenvalue=float(eigval),
            is_imaginary=is_imag,
            is_vibrational=is_vib,
            reduced_mass_amu=float(red_mass),
            force_constant_mdyn_angstrom=float(k_force_constant),
            mass_weighted_displacement=mw_disp,
            cartesian_displacement=cart_disp,
        )
        modes.append(mode)

    analysis = VibrationalAnalysis.from_frequencies(
        frequencies_cm1=frequencies_cm1,
        eigenvalues=eigenvalues.tolist(),
        modes=modes,
    )

    return analysis


def calculate_harmonic_kie(
    reactant_light: VibrationalAnalysis,
    ts_light: VibrationalAnalysis,
    reactant_heavy: VibrationalAnalysis,
    ts_heavy: VibrationalAnalysis,
    temperature_k: float = 298.15,
) -> HarmonicKIE:
    """Calculate the semiclassical Kinetic Isotope Effect (k_light / k_heavy).

    Uses the Bigeleisen-Mayer harmonic approximation:
        KIE = (Q_TS_light / Q_React_light) / (Q_TS_heavy / Q_React_heavy) * exp(-DeltaDeltaZPE / (k_B T))
    with Wigner tunneling corrections along the imaginary TS mode.
    """
    if temperature_k <= 0:
        raise ValueError(f"Temperature must be positive, got {temperature_k} K.")

    zpe_r_l = reactant_light.zpe_kcal_mol
    zpe_ts_l = ts_light.zpe_kcal_mol
    zpe_r_h = reactant_heavy.zpe_kcal_mol
    zpe_ts_h = ts_heavy.zpe_kcal_mol

    delta_zpe_light = zpe_ts_l - zpe_r_l
    delta_zpe_heavy = zpe_ts_h - zpe_r_h
    delta_delta_zpe_kcal = delta_zpe_light - delta_zpe_heavy

    r_cal = GAS_CONSTANT_R_CAL_MOL_K
    zpe_factor = math.exp(min(max(-delta_delta_zpe_kcal * 1000.0 / (r_cal * temperature_k), -500.0), 500.0))

    thermo_r_l = reactant_light.compute_thermochemistry(temperature_k)
    thermo_ts_l = ts_light.compute_thermochemistry(temperature_k)
    thermo_r_h = reactant_heavy.compute_thermochemistry(temperature_k)
    thermo_ts_h = ts_heavy.compute_thermochemistry(temperature_k)

    q_ratio_light = thermo_ts_l.vibrational_partition_function / max(thermo_r_l.vibrational_partition_function, 1e-15)
    q_ratio_heavy = thermo_ts_h.vibrational_partition_function / max(thermo_r_h.vibrational_partition_function, 1e-15)

    q_factor = q_ratio_light / max(q_ratio_heavy, 1e-15)

    beta_factor = (PLANCK_CONSTANT_J_S * SPEED_OF_LIGHT_CM_S) / BOLTZMANN_CONSTANT_J_K

    def _get_wigner(analysis: VibrationalAnalysis) -> float:
        imag_modes = [abs(f) for f in analysis.frequencies_cm1 if f < 0.0]
        if not imag_modes:
            return 1.0
        max_imag = max(imag_modes)
        u_star = (beta_factor * max_imag) / temperature_k
        return 1.0 + (1.0 / 24.0) * (u_star**2)

    tun_l = _get_wigner(ts_light)
    tun_h = _get_wigner(ts_heavy)
    tun_factor = tun_l / max(tun_h, 1e-15)

    total_kie = zpe_factor * q_factor * tun_factor

    return HarmonicKIE(
        temperature_k=temperature_k,
        kie_ratio=float(total_kie),
        delta_zpe_diff_kcal_mol=float(-delta_delta_zpe_kcal),
        reactant_light_zpe_kcal_mol=zpe_r_l,
        ts_light_zpe_kcal_mol=zpe_ts_l,
        reactant_heavy_zpe_kcal_mol=zpe_r_h,
        ts_heavy_zpe_kcal_mol=zpe_ts_h,
        wigner_tunneling_correction_light=tun_l,
        wigner_tunneling_correction_heavy=tun_h,
    )

# ============================================================================
# High-Level Orchestrator & SWMR HDF5 Persistence Engine
# ============================================================================


class ToposIsotopologueRecycler:
    """High-level orchestrator for Isotopologue Hessian Recycling (Stage 4.1).

    Features:
    - Reads baseline Cartesian Hessian tensors directly from `landscape.h5`.
    - Generates standard isotopologue suites (D, 13C, 15N, 18O, etc.).
    - Executes high-speed batch mass-weighted secular diagonalization.
    - Persists computed isotopologue states to `landscape.h5` with thread/process locks.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        memory_manager: Optional[Any] = None,
    ) -> None:
        if memory_manager is not None:
            self.memory_manager = memory_manager
            self.db_path = Path(memory_manager.db_path)
        else:
            resolved_path = self._resolve_db_path(db_path)
            self.db_path = resolved_path
            if ToposHDF5MemoryManager is not None:
                self.memory_manager = ToposHDF5MemoryManager(db_path=self.db_path)
            else:
                self.memory_manager = None

        self.lock_path = Path(f"{self.db_path}.lock")
        self.lock = FileLock(str(self.lock_path))
        logger.info(f"ToposIsotopologueRecycler initialized for datastore at {self.db_path}")

    @staticmethod
    def _resolve_db_path(db_path: Optional[Union[str, Path]] = None) -> Path:
        if db_path is not None:
            return Path(db_path).resolve()
        workspace_env = os.getenv("COCHEM_WORKSPACE")
        if workspace_env:
            return (Path(workspace_env).resolve() / "artifacts" / "Databases" / "landscape.h5").resolve()
        return (Path.cwd().resolve() / "artifacts" / "Databases" / "landscape.h5").resolve()

    def get_baseline_geometry(self, geom_id: str) -> Tuple[List[str], np.ndarray, np.ndarray, float, Dict[str, Any]]:
        """Extract baseline symbols, coordinates, Hessian, and energy from HDF5 database."""
        if self.memory_manager is not None:
            record = self.memory_manager.read_geometry(geom_id)
            if record is not None and record.hessian is not None and len(record.hessian) > 0:
                symbols = [mendeleev.element(z).symbol for z in record.atomic_numbers]
                coords = np.array(record.coords, dtype=np.float64)
                hessian = np.array(record.hessian, dtype=np.float64)
                return symbols, coords, hessian, record.energy, record.metadata

        with self.lock:
            with h5py.File(self.db_path, "r") as f:
                if "geometries" not in f or geom_id not in f["geometries"]:
                    raise KeyError(f"Geometry record '{geom_id}' not found in {self.db_path}.")

                g = f["geometries"][geom_id]
                atomic_numbers = g["atomic_numbers"][:].astype(int).tolist()
                coords = g["coordinates"][:].astype(float)
                energy = float(g.attrs.get("electronic_energy_hartree", 0.0))

                if "hessian_matrix" not in g:
                    raise ValueError(f"Geometry '{geom_id}' does not have a computed Hessian in {self.db_path}.")

                hessian = g["hessian_matrix"][:].astype(float)
                symbols = [mendeleev.element(z).symbol for z in atomic_numbers]
                meta = json.loads(g.attrs.get("metadata_json", "{}"))

                return symbols, coords, hessian, energy, meta

    def recycle_single(
        self,
        geom_id: str,
        definition: IsotopologueDefinition,
        unit: Union[HessianUnit, str] = HessianUnit.EV_PER_ANGSTROM2,
        save_to_hdf5: bool = True,
        temperature_k: float = 298.15,
    ) -> IsotopologueRecycleResult:
        """Execute isotopic Hessian recycling for a single isotopologue candidate."""
        t_start = time.perf_counter()
        symbols, coords, hessian, energy, meta = self.get_baseline_geometry(geom_id)

        baseline_masses = get_isotopic_masses(symbols).tolist()
        baseline_analysis = recycle_hessian_frequencies(
            hessian=hessian,
            symbols=symbols,
            coordinates=coords,
            unit=unit,
            temperature_k=temperature_k,
        )

        if definition.custom_masses is not None:
            sub_masses = list(definition.custom_masses)
        else:
            sub_masses = get_isotopic_masses(symbols, substitutions=definition.substitutions).tolist()

        iso_analysis = recycle_hessian_frequencies(
            hessian=hessian,
            symbols=symbols,
            coordinates=coords,
            custom_masses=sub_masses,
            unit=unit,
            temperature_k=temperature_k,
        )

        thermo = iso_analysis.compute_thermochemistry(temperature_k=temperature_k)
        t_duration = (time.perf_counter() - t_start) * 1000.0

        subs_applied: list[IsotopeSubstitution] = []
        for idx, (m_base, m_sub) in enumerate(zip(baseline_masses, sub_masses)):
            if abs(m_base - m_sub) > 1e-4:
                sym = symbols[idx]
                subs_applied.append(
                    IsotopeSubstitution(
                        atom_index=idx,
                        element_symbol=sym,
                        mass_number=int(round(m_sub)),
                        exact_mass_da=m_sub,
                        baseline_mass_da=m_base,
                    )
                )

        delta_zpe = iso_analysis.zpe_kcal_mol - baseline_analysis.zpe_kcal_mol

        prov_dict = {
            "geom_id": geom_id,
            "isotopologue_id": definition.isotopologue_id,
            "substituted_masses": sub_masses,
            "zpe_kcal_mol": iso_analysis.zpe_kcal_mol,
            "frequencies_cm1": iso_analysis.frequencies_cm1,
        }
        prov_hash = hashlib.sha256(json.dumps(prov_dict, sort_keys=True).encode("utf-8")).hexdigest()

        result = IsotopologueRecycleResult(
            geom_id=geom_id,
            isotopologue_id=definition.isotopologue_id,
            symbols=symbols,
            baseline_masses=baseline_masses,
            substituted_masses=sub_masses,
            baseline_zpe_kcal_mol=baseline_analysis.zpe_kcal_mol,
            isotopologue_zpe_kcal_mol=iso_analysis.zpe_kcal_mol,
            delta_zpe_kcal_mol=delta_zpe,
            baseline_frequencies_cm1=baseline_analysis.frequencies_cm1,
            isotopologue_frequencies_cm1=iso_analysis.frequencies_cm1,
            vibrational_analysis=iso_analysis,
            thermochemistry_298k=thermo,
            substitutions_applied=subs_applied,
            calculation_time_ms=t_duration,
            provenance_sha256=prov_hash,
        )

        if save_to_hdf5:
            self.save_to_hdf5(result)

        return result

    def recycle_batch(
        self,
        geom_id: str,
        definitions: Sequence[IsotopologueDefinition],
        unit: Union[HessianUnit, str] = HessianUnit.EV_PER_ANGSTROM2,
        save_to_hdf5: bool = True,
        temperature_k: float = 298.15,
    ) -> BatchRecycleReport:
        """Batch calculate a series of isotopologues against a single baseline Hessian."""
        results: list[IsotopologueRecycleResult] = []
        for defn in definitions:
            res = self.recycle_single(
                geom_id=geom_id,
                definition=defn,
                unit=unit,
                save_to_hdf5=save_to_hdf5,
                temperature_k=temperature_k,
            )
            results.append(res)

        return BatchRecycleReport(
            geom_id=geom_id,
            total_calculated=len(results),
            results=results,
        )

    def generate_standard_isotopologues(self, geom_id: str) -> List[IsotopologueDefinition]:
        """Automatically construct standard isotopologue suites (D, 13C, 15N, 18O)."""
        symbols, _, _, _, _ = self.get_baseline_geometry(geom_id)
        definitions: list[IsotopologueDefinition] = []

        if "H" in symbols:
            definitions.append(
                IsotopologueDefinition(
                    isotopologue_id="PerDeuterated_D",
                    substitutions={"H": "D"},
                    description="Complete per-deuteration of all hydrogen centers.",
                )
            )
            for idx, sym in enumerate(symbols):
                if sym == "H":
                    definitions.append(
                        IsotopologueDefinition(
                            isotopologue_id=f"Mono_D_site_{idx}",
                            substitutions={idx: "D"},
                            description=f"Single deuterium substitution at atom index {idx}.",
                        )
                    )

        if "C" in symbols:
            definitions.append(
                IsotopologueDefinition(
                    isotopologue_id="Per13C",
                    substitutions={"C": 13},
                    description="Uniform 13C substitution across all carbon centers.",
                )
            )
            for idx, sym in enumerate(symbols):
                if sym == "C":
                    definitions.append(
                        IsotopologueDefinition(
                            isotopologue_id=f"Mono_13C_site_{idx}",
                            substitutions={idx: 13},
                            description=f"Single 13C substitution at carbon index {idx}.",
                        )
                    )

        if "O" in symbols:
            definitions.append(
                IsotopologueDefinition(
                    isotopologue_id="Per18O",
                    substitutions={"O": 18},
                    description="Uniform 18O substitution across all oxygen centers.",
                )
            )
            definitions.append(
                IsotopologueDefinition(
                    isotopologue_id="Per17O",
                    substitutions={"O": 17},
                    description="Uniform 17O substitution across all oxygen centers.",
                )
            )

        if "N" in symbols:
            definitions.append(
                IsotopologueDefinition(
                    isotopologue_id="Per15N",
                    substitutions={"N": 15},
                    description="Uniform 15N substitution across all nitrogen centers.",
                )
            )

        return definitions

    def save_to_hdf5(self, result: IsotopologueRecycleResult) -> None:
        """Persist calculated isotopologue data into landscape.h5 under /isotopologues/."""
        max_retries = 10
        for attempt in range(max_retries):
            try:
                with self.lock:
                    with h5py.File(self.db_path, "a", libver="latest") as f:
                        if "isotopologues" not in f:
                            iso_root = f.create_group("isotopologues")
                        else:
                            iso_root = f["isotopologues"]

                        if result.geom_id not in iso_root:
                            geom_grp = iso_root.create_group(result.geom_id)
                        else:
                            geom_grp = iso_root[result.geom_id]

                        if result.isotopologue_id in geom_grp:
                            del geom_grp[result.isotopologue_id]

                        iso_grp = geom_grp.create_group(result.isotopologue_id)

                        iso_grp.create_dataset(
                            "frequencies_cm1",
                            data=np.array(result.isotopologue_frequencies_cm1, dtype=np.float64),
                        )
                        iso_grp.create_dataset(
                            "baseline_frequencies_cm1",
                            data=np.array(result.baseline_frequencies_cm1, dtype=np.float64),
                        )
                        iso_grp.create_dataset(
                            "substituted_masses",
                            data=np.array(result.substituted_masses, dtype=np.float64),
                        )
                        iso_grp.create_dataset(
                            "eigenvalues",
                            data=np.array(result.vibrational_analysis.eigenvalues, dtype=np.float64),
                        )

                        iso_grp.attrs["zpe_hartree"] = result.vibrational_analysis.zpe_hartree
                        iso_grp.attrs["zpe_kcal_mol"] = result.vibrational_analysis.zpe_kcal_mol
                        iso_grp.attrs["zpe_kj_mol"] = result.vibrational_analysis.zpe_kj_mol
                        iso_grp.attrs["zpe_ev"] = result.vibrational_analysis.zpe_ev
                        iso_grp.attrs["delta_zpe_kcal_mol"] = result.delta_zpe_kcal_mol
                        iso_grp.attrs["baseline_zpe_kcal_mol"] = result.baseline_zpe_kcal_mol
                        iso_grp.attrs["provenance_sha256"] = result.provenance_sha256
                        iso_grp.attrs["updated_at"] = time.time()

                        f.flush()
                logger.debug(f"Persisted isotopologue [{result.geom_id}][{result.isotopologue_id}] to {self.db_path}")
                return
            except Exception as exc:
                if attempt < max_retries - 1:
                    time.sleep(0.02 * (attempt + 1))
                else:
                    logger.error(f"Failed to persist isotopologue {result.isotopologue_id}: {exc}")
                    raise RuntimeError(f"HDF5 persistence failure: {exc}") from exc

    def read_isotopologue_from_hdf5(
        self,
        geom_id: str,
        isotopologue_id: str,
    ) -> Optional[IsotopologueRecycleResult]:
        """Read a persisted isotopologue calculation from landscape.h5."""
        try:
            with self.lock:
                with h5py.File(self.db_path, "r") as f:
                    if (
                        "isotopologues" not in f
                        or geom_id not in f["isotopologues"]
                        or isotopologue_id not in f["isotopologues"][geom_id]
                    ):
                        return None

                    iso_grp = f["isotopologues"][geom_id][isotopologue_id]
                    freqs = iso_grp["frequencies_cm1"][:].astype(float).tolist()
                    if "baseline_frequencies_cm1" in iso_grp:
                        base_freqs = iso_grp["baseline_frequencies_cm1"][:].astype(float).tolist()
                    else:
                        base_freqs = []
                    sub_masses = iso_grp["substituted_masses"][:].astype(float).tolist()
                    eigenvals = iso_grp["eigenvalues"][:].astype(float).tolist()

                    zpe_kcal = float(iso_grp.attrs.get("zpe_kcal_mol", 0.0))
                    base_zpe_kcal = float(iso_grp.attrs.get("baseline_zpe_kcal_mol", 0.0))
                    delta_zpe = float(iso_grp.attrs.get("delta_zpe_kcal_mol", 0.0))
                    prov_hash = str(iso_grp.attrs.get("provenance_sha256", ""))

            vib = VibrationalAnalysis.from_frequencies(frequencies_cm1=freqs, eigenvalues=eigenvals)
            thermo = vib.compute_thermochemistry()

            symbols, coords, hessian, _, _ = self.get_baseline_geometry(geom_id)
            base_masses = get_isotopic_masses(symbols).tolist()
            if not base_freqs:
                base_analysis = recycle_hessian_frequencies(
                    hessian=hessian,
                    symbols=symbols,
                    coordinates=coords,
                )
                base_freqs = base_analysis.frequencies_cm1

            return IsotopologueRecycleResult(
                geom_id=geom_id,
                isotopologue_id=isotopologue_id,
                symbols=symbols,
                baseline_masses=base_masses,
                substituted_masses=sub_masses,
                baseline_zpe_kcal_mol=base_zpe_kcal,
                isotopologue_zpe_kcal_mol=zpe_kcal,
                delta_zpe_kcal_mol=delta_zpe,
                baseline_frequencies_cm1=base_freqs,
                isotopologue_frequencies_cm1=freqs,
                vibrational_analysis=vib,
                thermochemistry_298k=thermo,
                provenance_sha256=prov_hash,
            )
        except Exception as exc:
            logger.error(f"Error reading isotopologue [{geom_id}][{isotopologue_id}]: {exc}")
            return None

    def list_isotopologues(self, geom_id: str) -> List[str]:
        """List all persisted isotopologue IDs for a given geometry in landscape.h5."""
        try:
            with self.lock:
                with h5py.File(self.db_path, "r") as f:
                    if "isotopologues" not in f or geom_id not in f["isotopologues"]:
                        return []
                    return list(f["isotopologues"][geom_id].keys())
        except Exception as exc:
            logger.error(f"Error listing isotopologues for {geom_id}: {exc}")
            return []


--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_topos_iso_recycle.py ---
"""
Unit tests for CoChem-TOPOS Isotopologue Hessian Recycling (Stage 4.1: cochem_topos_iso_recycle.py).

Validates First-Order Isotopic Mass Perturbation, Born-Oppenheimer PES invariance,
exact mono-isotopic mass injection via Mendeleev, mass-weighted Hessian diagonalization,
ZPE / vibrational thermochemistry calculations, KIE predictions, and HDF5 SWMR persistence.

Strictly complies with the Tripartite Air-Gap Policy and Zero-Mock Mandate.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

try:
    from escalation.cochem_topos_iso_recycle import (
        HESSIAN_UNIT_FACTORS,
        HessianUnit,
        IsotopeSubstitution,
        IsotopologueDefinition,
        IsotopologueRecycleResult,
        NormalMode,
        ThermochemicalCorrections,
        ToposIsotopologueRecycler,
        VibrationalAnalysis,
        calculate_harmonic_kie,
        get_exact_isotopic_mass,
        get_isotopic_masses,
        mass_weight_hessian,
        project_translations_rotations,
        recycle_hessian_frequencies,
    )
except ImportError:
    from cochem_topos.cochem_topos_iso_recycle import (  # type: ignore[no-redef]
        HESSIAN_UNIT_FACTORS,
        HessianUnit,
        IsotopeSubstitution,
        IsotopologueDefinition,
        IsotopologueRecycleResult,
        NormalMode,
        ThermochemicalCorrections,
        ToposIsotopologueRecycler,
        VibrationalAnalysis,
        calculate_harmonic_kie,
        get_exact_isotopic_mass,
        get_isotopic_masses,
        mass_weight_hessian,
        project_translations_rotations,
        recycle_hessian_frequencies,
    )

try:
    from mechanics.cochem_topos_memory import GeometryRecord, ToposHDF5MemoryManager
except ImportError:
    from cochem_topos.cochem_topos_memory import (  # type: ignore[no-redef]
        GeometryRecord,
        ToposHDF5MemoryManager,
    )


# ============================================================================
# 1. Tests for Mass Retrieval & Mendeleev Resolution
# ============================================================================


class TestIsotopicMassResolution:
    """Verifies exact mono-isotopic mass querying and error handling."""

    def test_standard_element_monoisotopic_masses(self) -> None:
        """Confirms ground state monoisotopic masses for common organic elements."""
        assert pytest.approx(get_exact_isotopic_mass("H"), rel=1e-6) == 1.007825032
        assert pytest.approx(get_exact_isotopic_mass("C"), rel=1e-6) == 12.000000000
        assert pytest.approx(get_exact_isotopic_mass("N"), rel=1e-6) == 14.003074004
        assert pytest.approx(get_exact_isotopic_mass("O"), rel=1e-6) == 15.994914620
        assert pytest.approx(get_exact_isotopic_mass("S"), rel=1e-6) == 31.972071000

    def test_heavy_isotope_masses(self) -> None:
        """Confirms exact masses for heavy isotopic variants."""
        assert pytest.approx(get_exact_isotopic_mass("D"), rel=1e-6) == 2.014101778
        assert pytest.approx(get_exact_isotopic_mass("H", mass_number=2), rel=1e-6) == 2.014101778
        assert pytest.approx(get_exact_isotopic_mass("T"), rel=1e-6) == 3.016049281
        assert pytest.approx(get_exact_isotopic_mass("C", mass_number=13), rel=1e-6) == 13.003354835
        assert pytest.approx(get_exact_isotopic_mass("13C"), rel=1e-6) == 13.003354835
        assert pytest.approx(get_exact_isotopic_mass("O", mass_number=18), rel=1e-6) == 17.999159613
        assert pytest.approx(get_exact_isotopic_mass("18O"), rel=1e-6) == 17.999159613
        assert pytest.approx(get_exact_isotopic_mass("N", mass_number=15), rel=1e-6) == 15.000108899
        assert pytest.approx(get_exact_isotopic_mass("Cl", mass_number=37), rel=1e-6) == 36.96590260

    def test_get_isotopic_masses_sequence(self) -> None:
        """Tests mass array generation for molecular symbol lists."""
        symbols = ["O", "H", "H"]
        masses = get_isotopic_masses(symbols)
        assert len(masses) == 3
        assert pytest.approx(masses[0], rel=1e-5) == 15.994915
        assert pytest.approx(masses[1], rel=1e-5) == 1.007825
        assert pytest.approx(masses[2], rel=1e-5) == 1.007825

    def test_get_isotopic_masses_with_substitutions(self) -> None:
        """Tests mass array generation with explicit index substitutions."""
        symbols = ["O", "H", "H"]
        substitutions = {1: "D", 2: 2}
        masses = get_isotopic_masses(symbols, substitutions=substitutions)
        assert pytest.approx(masses[0], rel=1e-5) == 15.994915
        assert pytest.approx(masses[1], rel=1e-5) == 2.014102
        assert pytest.approx(masses[2], rel=1e-5) == 2.014102

    def test_numpy_integer_substitutions(self) -> None:
        """Confirms NumPy integer mass numbers resolve to exact monoisotopic masses."""
        symbols = ["H"]
        masses_py_int = get_isotopic_masses(symbols, substitutions={0: 2})
        masses_np_int = get_isotopic_masses(symbols, substitutions={0: np.int64(2)})
        assert pytest.approx(masses_py_int[0], rel=1e-6) == 2.014101778
        assert pytest.approx(masses_np_int[0], rel=1e-6) == 2.014101778
        assert pytest.approx(masses_py_int[0]) == masses_np_int[0]

    def test_invalid_symbol_or_isotope_raises(self) -> None:
        """Confirms invalid chemical symbols or unphysical mass numbers raise ValueError."""
        with pytest.raises(ValueError, match="not recognized"):
            get_exact_isotopic_mass("Unobtanium")

        with pytest.raises(ValueError, match="No isotope with mass number"):
            get_exact_isotopic_mass("H", mass_number=999)


# ============================================================================
# 2. Tests for Mass-Weighted Hessian & Eigendecomposition
# ============================================================================


class TestMassWeightedHessianAndFrequencies:
    """Verifies mass weighting, diagonalization, and frequency extraction."""

    @pytest.fixture
    def harmonic_diatomic_co(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Fixture providing an analytical 1D-like harmonic oscillator for CO."""
        coords = np.array([
            [0.0, 0.0, 0.0],       # C (index 0)
            [0.0, 0.0, 1.1283],    # O (index 1)
        ], dtype=np.float64)
        symbols = ["C", "O"]

        k = 11.58
        H = np.zeros((6, 6), dtype=np.float64)
        H[2, 2] = k
        H[5, 5] = k
        H[2, 5] = -k
        H[5, 2] = -k
        return H, coords, symbols

    def test_mass_weighted_hessian_scaling(self, harmonic_diatomic_co) -> None:
        """Confirms mass-weighting scaling formula."""
        H, coords, symbols = harmonic_diatomic_co
        m_C = get_exact_isotopic_mass("C")
        m_O = get_exact_isotopic_mass("O")
        masses = np.array([m_C, m_O])

        F = mass_weight_hessian(H, masses)
        assert F.shape == (6, 6)
        assert pytest.approx(F[2, 2]) == H[2, 2] / m_C
        assert pytest.approx(F[5, 5]) == H[5, 5] / m_O
        assert pytest.approx(F[2, 5]) == H[2, 5] / np.sqrt(m_C * m_O)
        assert pytest.approx(F[5, 2]) == H[5, 2] / np.sqrt(m_C * m_O)
        np.testing.assert_allclose(F, F.T, atol=1e-12)

    def test_diatomic_frequency_and_isotopic_shift(self, harmonic_diatomic_co) -> None:
        """Confirms exact isotopic frequency ratio follows reduced mass ratio."""
        H, coords, symbols = harmonic_diatomic_co
        res_12c16o = recycle_hessian_frequencies(
            hessian=H,
            symbols=symbols,
            coordinates=coords,
            unit=HessianUnit.EV_PER_ANGSTROM2,
        )
        res_13c16o = recycle_hessian_frequencies(
            hessian=H,
            symbols=symbols,
            coordinates=coords,
            substitutions={0: 13},
            unit=HessianUnit.EV_PER_ANGSTROM2,
        )

        m_C12 = get_exact_isotopic_mass("12C")
        m_C13 = get_exact_isotopic_mass("13C")
        m_O16 = get_exact_isotopic_mass("16O")

        mu_12 = (m_C12 * m_O16) / (m_C12 + m_O16)
        mu_13 = (m_C13 * m_O16) / (m_C13 + m_O16)
        theoretical_ratio = np.sqrt(mu_12 / mu_13)

        vib_12 = max(res_12c16o.frequencies_cm1)
        vib_13 = max(res_13c16o.frequencies_cm1)
        actual_ratio = vib_13 / vib_12

        assert pytest.approx(actual_ratio, rel=1e-4) == theoretical_ratio
        assert vib_12 > vib_13

    def test_all_hessian_units_consistency(self) -> None:
        """Confirms identical physical frequency across all supported input Hessian units."""
        # 1D harmonic oscillator with k = 1000 N/m (J/m^2)
        # 1000 N/m = 1000 J/m^2 = 62.4150907446 eV/Angstrom^2
        # 1000 N/m = 0.642283088 Hartree/Bohr^2 (1 Hartree = 4.3597447e-18 J, 1 Bohr = 0.5291772e-10 m)
        k_si = 1000.0  # J/m^2
        k_ev_ang2 = k_si * (1.0e-20 / 1.602176634e-19)
        k_ha_bohr2 = k_si * ((0.529177210903e-10)**2 / 4.3597447222071e-18)
        k_ha_ang2 = k_si * (1.0e-20 / 4.3597447222071e-18)

        symbols = ["C", "O"]
        coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.13]])

        def _make_h(k_val: float) -> np.ndarray:
            h = np.zeros((6, 6), dtype=np.float64)
            h[2, 2] = k_val
            h[5, 5] = k_val
            h[2, 5] = -k_val
            h[5, 2] = -k_val
            return h

        res_si = recycle_hessian_frequencies(_make_h(k_si), symbols, coords, unit=HessianUnit.J_PER_M2)
        res_ev = recycle_hessian_frequencies(_make_h(k_ev_ang2), symbols, coords, unit=HessianUnit.EV_PER_ANGSTROM2)
        res_ha_bohr = recycle_hessian_frequencies(_make_h(k_ha_bohr2), symbols, coords, unit=HessianUnit.HARTREE_PER_BOHR2)
        res_ha_ang = recycle_hessian_frequencies(_make_h(k_ha_ang2), symbols, coords, unit=HessianUnit.HARTREE_PER_ANGSTROM2)

        freq_si = max(res_si.frequencies_cm1)
        freq_ev = max(res_ev.frequencies_cm1)
        freq_ha_bohr = max(res_ha_bohr.frequencies_cm1)
        freq_ha_ang = max(res_ha_ang.frequencies_cm1)

        assert pytest.approx(freq_si, rel=1e-4) == 1573.34
        assert pytest.approx(freq_ev, rel=1e-4) == freq_si
        assert pytest.approx(freq_ha_bohr, rel=1e-4) == freq_si
        assert pytest.approx(freq_ha_ang, rel=1e-4) == freq_si

    def test_water_triatomic_isotopologue_series(self) -> None:
        """Tests water vibrational recycling across H2O, HDO, D2O, and H2_18O."""
        symbols = ["O", "H", "H"]
        coords = np.array([
            [0.0000, 0.0000, 0.1173],
            [0.0000, 0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ], dtype=np.float64)

        N = 3
        H = np.zeros((3 * N, 3 * N), dtype=np.float64)
        k_str = 35.0
        k_bend = 5.0

        d1 = coords[1] - coords[0]
        u1 = d1 / np.linalg.norm(d1)
        H_str1 = k_str * np.outer(u1, u1)

        d2 = coords[2] - coords[0]
        u2 = d2 / np.linalg.norm(d2)
        H_str2 = k_str * np.outer(u2, u2)

        H[0:3, 0:3] += H_str1 + H_str2
        H[3:6, 3:6] += H_str1
        H[0:3, 3:6] -= H_str1
        H[3:6, 0:3] -= H_str1

        H[6:9, 6:9] += H_str2
        H[0:3, 6:9] -= H_str2
        H[6:9, 0:3] -= H_str2

        H[3:6, 6:9] += k_bend * np.eye(3)
        H[6:9, 3:6] += k_bend * np.eye(3)
        H[3:6, 3:6] += k_bend * np.eye(3)
        H[6:9, 6:9] += k_bend * np.eye(3)

        res_h2o = recycle_hessian_frequencies(H, symbols, coords, unit=HessianUnit.EV_PER_ANGSTROM2)
        res_hdo = recycle_hessian_frequencies(H, symbols, coords, substitutions={1: "D"}, unit=HessianUnit.EV_PER_ANGSTROM2)
        res_d2o = recycle_hessian_frequencies(H, symbols, coords, substitutions={1: "D", 2: "D"}, unit=HessianUnit.EV_PER_ANGSTROM2)
        res_h2_18o = recycle_hessian_frequencies(H, symbols, coords, substitutions={0: 18}, unit=HessianUnit.EV_PER_ANGSTROM2)

        assert res_h2o.zpe_kcal_mol > res_h2_18o.zpe_kcal_mol
        assert res_h2_18o.zpe_kcal_mol > res_hdo.zpe_kcal_mol
        assert res_hdo.zpe_kcal_mol > res_d2o.zpe_kcal_mol

        h2o_vib_max = max(res_h2o.frequencies_cm1)
        d2o_vib_max = max(res_d2o.frequencies_cm1)
        assert pytest.approx(d2o_vib_max / h2o_vib_max, rel=0.1) == 1.0 / np.sqrt(2.0)


# ============================================================================
# 3. Tests for Thermochemistry, ZPE, and KIE
# ============================================================================


class TestThermochemistryAndKIE:
    """Verifies harmonic partition functions, thermodynamic corrections, and KIE."""

    def test_zpe_unit_conversions(self) -> None:
        """Confirms mathematical consistency of ZPE across Ha, kcal/mol, kJ/mol, and eV."""
        freqs = [3657.05, 1594.75, 3755.93]
        eigenvals = [1.0, 2.0, 3.0]
        vib = VibrationalAnalysis.from_frequencies(frequencies_cm1=freqs, eigenvalues=eigenvals)

        assert pytest.approx(vib.zpe_hartree, rel=1e-4) == 0.0205211
        assert pytest.approx(vib.zpe_kcal_mol, rel=1e-4) == vib.zpe_hartree * 627.509474
        assert pytest.approx(vib.zpe_kj_mol, rel=1e-4) == vib.zpe_hartree * 2625.49964
        assert pytest.approx(vib.zpe_ev, rel=1e-4) == vib.zpe_hartree * 27.211386

    def test_thermochemical_corrections_temperature(self) -> None:
        """Confirms thermal energy and entropy increase monotonically with temperature."""
        freqs = [500.0, 1000.0, 1500.0, 3000.0]
        vib = VibrationalAnalysis.from_frequencies(frequencies_cm1=freqs, eigenvalues=[1, 2, 3, 4])

        thermo_298 = vib.compute_thermochemistry(temperature_k=298.15)
        thermo_500 = vib.compute_thermochemistry(temperature_k=500.0)

        assert thermo_500.thermal_energy_hartree > thermo_298.thermal_energy_hartree
        assert thermo_500.entropy_cal_mol_k > thermo_298.entropy_cal_mol_k
        assert thermo_500.heat_capacity_cal_mol_k > thermo_298.heat_capacity_cal_mol_k

    def test_harmonic_kie_calculation(self) -> None:
        """Confirms semi-classical primary KIE (k_H / k_D > 1.0) due to ZPE difference."""
        freqs_react_H = [3000.0, 1000.0, 500.0]
        freqs_ts_H = [1500.0, 1000.0, 500.0]

        freqs_react_D = [3000.0 / np.sqrt(2.0), 1000.0, 500.0]
        freqs_ts_D = [1500.0 / np.sqrt(2.0), 1000.0, 500.0]

        vib_react_H = VibrationalAnalysis.from_frequencies(freqs_react_H, [1, 1, 1])
        vib_ts_H = VibrationalAnalysis.from_frequencies(freqs_ts_H, [1, 1, 1])
        vib_react_D = VibrationalAnalysis.from_frequencies(freqs_react_D, [1, 1, 1])
        vib_ts_D = VibrationalAnalysis.from_frequencies(freqs_ts_D, [1, 1, 1])

        kie_298 = calculate_harmonic_kie(
            reactant_light=vib_react_H,
            ts_light=vib_ts_H,
            reactant_heavy=vib_react_D,
            ts_heavy=vib_ts_D,
            temperature_k=298.15,
        )

        assert kie_298.kie_ratio > 1.0
        assert kie_298.delta_zpe_diff_kcal_mol > 0.0

    def test_harmonic_kie_with_wigner_tunneling(self) -> None:
        """Confirms Wigner tunneling calculation when transition states have imaginary modes."""
        freqs_react_H = [3000.0, 1000.0, 500.0]
        freqs_ts_H = [-1200.0, 1000.0, 500.0]

        freqs_react_D = [3000.0 / np.sqrt(2.0), 1000.0, 500.0]
        freqs_ts_D = [-1200.0 / np.sqrt(2.0), 1000.0, 500.0]

        vib_react_H = VibrationalAnalysis.from_frequencies(freqs_react_H, [1, 1, 1])
        vib_ts_H = VibrationalAnalysis.from_frequencies(freqs_ts_H, [-1, 1, 1])
        vib_react_D = VibrationalAnalysis.from_frequencies(freqs_react_D, [1, 1, 1])
        vib_ts_D = VibrationalAnalysis.from_frequencies(freqs_ts_D, [-1, 1, 1])

        kie = calculate_harmonic_kie(
            reactant_light=vib_react_H,
            ts_light=vib_ts_H,
            reactant_heavy=vib_react_D,
            ts_heavy=vib_ts_D,
            temperature_k=298.15,
        )

        assert kie.wigner_tunneling_correction_light > kie.wigner_tunneling_correction_heavy
        assert kie.wigner_tunneling_correction_heavy > 1.0
        assert kie.kie_ratio > 1.0


# ============================================================================
# 4. Tests for ToposIsotopologueRecycler & HDF5 SWMR Persistence
# ============================================================================


class TestToposIsotopologueRecyclerHDF5:
    """Verifies database extraction, batch calculation, and SWMR persistence."""

    @pytest.fixture
    def sample_h5_database(self, tmp_path: Path) -> tuple[Path, str]:
        """Creates an authentic HDF5 database with a converged water geometry & Hessian."""
        db_path = tmp_path / "landscape.h5"
        geom_id = "geom_water_cochem_opt"

        symbols = ["O", "H", "H"]
        atomic_numbers = [8, 1, 1]
        coords = [
            [0.0000, 0.0000, 0.1173],
            [0.0000, 0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ]
        hessian = (np.eye(9) * 15.0).tolist()
        energy = -76.4321

        mem = ToposHDF5MemoryManager(db_path=db_path)
        record = GeometryRecord(
            geom_id=geom_id,
            atomic_numbers=atomic_numbers,
            coords=coords,
            energy=energy,
            hessian=hessian,
            metadata={"level_of_theory": "wB97M-V/def2-TZVPP"},
        )
        mem.write_geometry(record)
        return db_path, geom_id

    def test_recycler_extract_and_recycle_from_hdf5(self, sample_h5_database) -> None:
        """Confirms extraction of baseline Hessian from HDF5 and calculation of isotopologues."""
        db_path, geom_id = sample_h5_database
        recycler = ToposIsotopologueRecycler(db_path=db_path)

        definitions = [
            IsotopologueDefinition(isotopologue_id="D2O", substitutions={1: "D", 2: "D"}),
            IsotopologueDefinition(isotopologue_id="H2_18O", substitutions={0: 18}),
            IsotopologueDefinition(isotopologue_id="HDO", substitutions={1: "D"}),
        ]

        report = recycler.recycle_batch(geom_id=geom_id, definitions=definitions, save_to_hdf5=True)

        assert report.total_calculated == 3
        assert len(report.results) == 3

        d2o_res = next(r for r in report.results if r.isotopologue_id == "D2O")
        assert d2o_res.isotopologue_zpe_kcal_mol < d2o_res.baseline_zpe_kcal_mol
        assert d2o_res.delta_zpe_kcal_mol < 0.0

        with h5py.File(db_path, "r") as f:
            assert "isotopologues" in f
            assert geom_id in f["isotopologues"]
            iso_grp = f["isotopologues"][geom_id]
            assert "D2O" in iso_grp
            assert "H2_18O" in iso_grp
            assert "HDO" in iso_grp

            d2o_grp = iso_grp["D2O"]
            assert "frequencies_cm1" in d2o_grp
            assert "baseline_frequencies_cm1" in d2o_grp
            assert "substituted_masses" in d2o_grp
            assert d2o_grp.attrs["zpe_kcal_mol"] == d2o_res.isotopologue_zpe_kcal_mol

    def test_recycler_read_persisted_isotopologue(self, sample_h5_database) -> None:
        """Confirms reading saved isotopologue data from HDF5 preserving distinct baseline and isotopologue freqs."""
        db_path, geom_id = sample_h5_database
        recycler = ToposIsotopologueRecycler(db_path=db_path)

        iso_def = IsotopologueDefinition(isotopologue_id="PerDeuterated", substitutions={"H": "D"})
        res_write = recycler.recycle_single(geom_id=geom_id, definition=iso_def, save_to_hdf5=True)

        res_read = recycler.read_isotopologue_from_hdf5(geom_id=geom_id, isotopologue_id="PerDeuterated")
        assert res_read is not None
        assert res_read.isotopologue_id == "PerDeuterated"
        assert pytest.approx(res_read.isotopologue_zpe_kcal_mol, rel=1e-5) == res_write.isotopologue_zpe_kcal_mol
        assert res_read.isotopologue_frequencies_cm1 == res_write.isotopologue_frequencies_cm1
        assert res_read.baseline_frequencies_cm1 == res_write.baseline_frequencies_cm1
        # For deuterated water, baseline (H2O) frequencies and isotopologue (D2O) frequencies must differ
        assert res_read.baseline_frequencies_cm1 != res_read.isotopologue_frequencies_cm1

    def test_generate_standard_isotopologue_ensemble(self, sample_h5_database) -> None:
        """Verifies automatic generation of standard isotopologue suites."""
        db_path, geom_id = sample_h5_database
        recycler = ToposIsotopologueRecycler(db_path=db_path)

        defs = recycler.generate_standard_isotopologues(geom_id=geom_id)
        assert len(defs) >= 4
        iso_ids = [d.isotopologue_id for d in defs]
        assert any("D2O" in i or "PerD" in i for i in iso_ids)
        assert any("18O" in i for i in iso_ids)


# ============================================================================
# 5. Tests for Edge Cases & Mathematical Robustness
# ============================================================================


class TestRecyclerEdgeCases:
    """Validates edge cases: dimension mismatch, non-symmetric Hessians, imaginary modes."""

    def test_dimension_mismatch_raises(self) -> None:
        """Confirms 3N x 3N dimension mismatch with N atoms raises ValueError."""
        H = np.eye(6)
        symbols = ["O", "H", "H"]
        coords = np.zeros((3, 3))

        with pytest.raises(ValueError, match="Dimension mismatch"):
            recycle_hessian_frequencies(H, symbols, coords)

    def test_imaginary_frequencies_handling(self) -> None:
        """Confirms negative eigenvalues (transition state) are flagged as imaginary."""
        H = np.diag([-5.0, 10.0, 10.0, 10.0, 10.0, 10.0])
        symbols = ["C", "H"]
        coords = np.zeros((2, 3))

        res = recycle_hessian_frequencies(H, symbols, coords, unit=HessianUnit.EV_PER_ANGSTROM2)
        assert res.num_imaginary == 1
        assert res.has_imaginary_modes is True
        assert any(f < 0 for f in res.frequencies_cm1)

    def test_translation_rotation_projection_nonlinear(self) -> None:
        """Confirms TR projector zeros out 6 external degrees of freedom for non-linear molecules."""
        coords = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ], dtype=np.float64)
        masses = np.array([12.0, 1.0, 1.0])
        A = np.random.RandomState(42).randn(9, 9)
        H = A.T @ A

        P = project_translations_rotations(coords, masses)
        assert P.shape == (9, 9)
        assert pytest.approx(np.trace(P)) == 3.0  # 3N - 6 = 9 - 6 = 3
        np.testing.assert_allclose(P @ P, P, atol=1e-10)

    def test_translation_rotation_projection_linear_diatomic(self) -> None:
        """Confirms TR projector preserves 1 vibrational mode for linear diatomics (3N - 5 = 1)."""
        coords = np.array([
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 1.1283],
        ], dtype=np.float64)
        masses = np.array([12.0, 16.0])
        symbols = ["C", "O"]

        P = project_translations_rotations(coords, masses)
        assert P.shape == (6, 6)
        assert pytest.approx(np.trace(P)) == 1.0  # 3N - 5 = 6 - 5 = 1
        np.testing.assert_allclose(P @ P, P, atol=1e-10)

        # Confirm stretching vibration is preserved under projection
        k = 11.58
        H = np.zeros((6, 6), dtype=np.float64)
        H[2, 2] = k
        H[5, 5] = k
        H[2, 5] = -k
        H[5, 2] = -k

        res = recycle_hessian_frequencies(H, symbols, coords, project_tr=True, unit=HessianUnit.EV_PER_ANGSTROM2)
        non_zero_freqs = [f for f in res.frequencies_cm1 if abs(f) > 10.0]
        assert len(non_zero_freqs) == 1
        assert pytest.approx(non_zero_freqs[0], rel=1e-4) == 677.7076

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.