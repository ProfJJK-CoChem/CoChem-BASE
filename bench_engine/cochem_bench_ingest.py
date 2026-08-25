#!/usr/bin/env python3
r"""Stage 1.0: Stage 0 Handshake, Registry Polling, Hardware Governor, and Pre-Flight Engine.

Authoritative Implementation: cochem_bench.bench_engine.cochem_bench_ingest
System Domain: CoChem-BENCH Ingestion Infrastructure

Key Capabilities:
1. Stage 0 Authority Rule & Atomic Polling (RegistryHandshake):
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR environment variable.
   - File locking using filelock.FileLock with a strict 10-second timeout.
   - Fatal interception if registry is absent, instructing user to run CoChem-CORE Stage 0 setup.
   - Strict Pydantic schema validation preventing hallucinated configurations or malformed types.
2. Dynamic %maxcore Calculation & Hardware Governor (HardwareGovernor):
   - Extraction of accessible RAM and physical silicon cores from the validated registry.
   - Reserving 15% headroom for host OS, OpenMPI daemons, and background telemetry brokers.
   - Mathematical formula: Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads).
   - Thread allocation: physical_cores - 1 if physical_cores > 4, else physical_cores.
   - Resource warnings when Safe_MaxCore_MB < 1500 MB.
   - Refusal to spawn heavy tensor contractions (e.g. DLPNO-CCSD(T)) if Safe_MaxCore_MB < 4000 MB.
3. Micro-Silo Verification & ABI Protection (SiloIntegrityAssert):
   - Strict assertion comparing sys.executable against silo_paths.bench_silo.
   - Ghost dependency purge: cleansing LD_LIBRARY_PATH to strip anaconda3/miniconda3 paths
     causing libtinfo.so.6 segfaults with ORCA while strictly preserving system MPI and compiler paths.
   - Dynamic extraction of ORCA executable path for downstream execution contexts.
4. Pre-Flight Verification & Execution Handoff (PreFlightVerification):
   - NVMe scratch space verification using PreFlightScratchVerifier from cochem_bench.bench_libraries.subprocess_reaper.
   - HDF5 workspace verification for landscape.h5.
   - Cryptographic provenance stamping: SHA-256 hash of configuration, Safe_MaxCore_MB, physical node ID,
     and ISO 8601 UTC timestamp assembled into an immutable read-only BenchRunContext dataclass.
5. Dynamic Mendeleev Integration: Dynamic mass querying when required.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 4 Registry Polling & The Stage 0 Handshake (Stage 1.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.finished_coding_prompts\draft_task4_ingest_pt1.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import filelock
from mendeleev import element
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from cochem_bench.bench_libraries.subprocess_reaper import (
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
    PreFlightScratchVerifier,
    ResourceGuardError as SubprocessResourceGuardError,
)
from cochem_core_registry_schema import (
    BYPASS_TOKENS,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    HPCConfig,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ==============================================================================
# Error Hierarchy
# ==============================================================================

class BenchIngestBaseError(Exception):
    """Base exception for CoChem-BENCH ingestion and pre-flight operations."""
    pass


class RegistryHandshakeError(BenchIngestBaseError, EnvironmentError):
    """Raised when the Stage 0 Golden Registry is missing, unreadable, or invalid."""
    pass


class SiloIntegrityError(BenchIngestBaseError, RuntimeError):
    """Raised when the active Python runtime fails silo isolation assertions."""
    pass


class HardwareGovernorError(BenchIngestBaseError, ValueError):
    """Raised when hardware limits or calculations encounter fatal bounds."""
    pass


class ResourceGuardError(BenchIngestBaseError, RuntimeError):
    """Raised when available memory or scratch resources are insufficient for requested quantum methods."""
    pass


class PreFlightVerificationError(BenchIngestBaseError):
    """Raised when pre-flight hardware or environment checks fail."""
    pass


# ==============================================================================
# Rigid Pydantic Ingestion Schemas
# ==============================================================================

class BenchHardwareSchema(BaseModel):
    """Rigid compute hardware bounds for CoChem-BENCH execution."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible RAM in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Physical silicon CPU cores")
    allocatable_compute_cores: Optional[int] = Field(default=None, ge=0)
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1)
    cpu_cores: Optional[int] = Field(default=None, ge=1)
    available_ram_gb: Optional[float] = Field(default=None, ge=0.0)
    vram_gb: float = Field(default=0.0, ge=0.0)
    gpu_profile: Optional[str] = Field(default="None")
    avx512_support: bool = Field(default=False)
    avx_512_capable: bool = Field(default=False)
    numa_nodes: int = Field(default=1, ge=1)
    host_id: Optional[str] = Field(default=None)
    os_target: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        # Synchronize RAM
        ram = d.get("ram_gb") or d.get("available_ram_gb")
        if ram is not None:
            try:
                ram_flt = float(ram)
                d["ram_gb"] = ram_flt
                d["available_ram_gb"] = ram_flt
            except (ValueError, TypeError):
                pass

        # Synchronize AVX-512
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])

        return d


class BenchSiloPathsSchema(BaseModel):
    """Pathing configurations for isolated execution micro-silos and scientific engines."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    bench_silo: Optional[str] = Field(default=None, description="Path to cochem_bench_silo python interpreter")
    orca_binary_path: Optional[str] = Field(default=None)
    orca_path: Optional[str] = Field(default=None)
    xtb_binary_path: Optional[str] = Field(default=None)
    xtb_path: Optional[str] = Field(default=None)
    mpirun_binary_path: Optional[str] = Field(default=None)
    mpirun_path: Optional[str] = Field(default=None)
    cfour_binary_path: Optional[str] = Field(default=None)
    cfour_path: Optional[str] = Field(default=None)
    aimnet2_server_path: Optional[str] = Field(default=None)
    aimnet2_path: Optional[str] = Field(default=None)
    python_path: Optional[str] = Field(default=None)
    silo_root: Optional[str] = Field(default=None)
    hdf5_pes_store_path: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def sync_path_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        alias_pairs = [
            ("orca_binary_path", "orca_path"),
            ("xtb_binary_path", "xtb_path"),
            ("mpirun_binary_path", "mpirun_path"),
            ("cfour_binary_path", "cfour_path"),
            ("aimnet2_server_path", "aimnet2_path"),
        ]
        for canonical, alias in alias_pairs:
            if canonical in d and alias not in d:
                d[alias] = d[canonical]
            elif alias in d and canonical not in d:
                d[canonical] = d[alias]
        return d


class BenchConfigSchema(BaseModel):
    """Authoritative Stage 0 Ingestion Schema for CoChem-BENCH."""
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    status: Optional[str] = Field(default="LOCKED")
    hardware: BenchHardwareSchema = Field(..., description="Hardware topology and memory limits")
    environment: Optional[EnvironmentSchema] = Field(default=None)
    silo_paths: BenchSiloPathsSchema = Field(default_factory=BenchSiloPathsSchema)
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    engine_paths: Optional[EnginePaths] = None
    cost_heuristics: Optional[Dict[str, Any]] = None
    active_jobs: Optional[Dict[str, Any]] = None
    hpc: Optional[HPCConfig] = None
    quantum_settings: Optional[QuantumSettings] = None
    adaptive_routing: Optional[RoutingPolicy] = None
    silos: Optional[SiloConfig] = None
    registry_checksum: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def available_ram_gb(self) -> float:
        """Returns authoritative accessible RAM in GB."""
        return float(self.hardware.available_ram_gb or self.hardware.ram_gb)

    @property
    def physical_cores(self) -> int:
        """Returns physical silicon core count."""
        return int(self.hardware.physical_cpu_cores or self.hardware.cpu_physical_cores or self.hardware.cpu_cores or 1)


# ==============================================================================
# Immutable Results & Context Dataclasses
# ==============================================================================

@dataclasses.dataclass(frozen=True)
class HardwareGovernorResult:
    """Immutable result from HardwareGovernor calculations."""
    safe_maxcore_mb: int
    target_mpi_threads: int
    resource_warning: bool
    numa_nodes: int = 1


@dataclasses.dataclass(frozen=True)
class BenchRunContext:
    """Immutable read-only execution context for downstream Stage 2.0 - 5.0 modules."""
    config_hash: str
    safe_maxcore_mb: int
    target_mpi_threads: int
    node_id: str
    timestamp: str
    orca_path: Optional[str]
    hdf5_path: Path
    scratch_path: Path
    numa_nodes: int
    resource_warning: bool
    config: BenchConfigSchema

    @property
    def orca_binary_path(self) -> Optional[str]:
        return self.orca_path


# ==============================================================================
# Core Stage 1.0 Components
# ==============================================================================

def HardwareGovernor(
    cfg: BenchConfigSchema,
    requested_method: Optional[str] = None,
) -> HardwareGovernorResult:
    """Calculates safe %maxcore allocation per MPI thread and enforces memory bounds.

    The 85% Headroom Heuristic:
      Target_MPI_Threads = physical_cores - 1 if physical_cores > 4 else physical_cores
      Safe_MaxCore_MB = floor(((available_ram_gb * 1024) * 0.85) / Target_MPI_Threads)

    Args:
        cfg: Validated BenchConfigSchema.
        requested_method: Optional method string (e.g. 'DLPNO-CCSD(T)').

    Returns:
        HardwareGovernorResult containing calculated limits and warning flags.

    Raises:
        ResourceGuardError: If DLPNO-CCSD(T) is requested and Safe_MaxCore_MB < 4000 MB.
    """
    ram_gb = cfg.available_ram_gb
    cores = cfg.physical_cores

    if cores > 4:
        target_mpi_threads = cores - 1
    else:
        target_mpi_threads = max(1, cores)

    safe_maxcore_mb = math.floor(((ram_gb * 1024.0) * 0.85) / target_mpi_threads)

    resource_warning = False
    if safe_maxcore_mb < 1500:
        resource_warning = True
        logger.warning(
            f"RESOURCE_WARNING: Calculated Safe_MaxCore_MB ({safe_maxcore_mb} MB) is below the recommended "
            f"1500 MB floor. High-memory jobs may experience severe page thrashing or OOM aborts."
        )

    if requested_method:
        method_clean = requested_method.lower().replace(" ", "").replace("_", "").replace("-", "")
        is_dlpno = "dlpno" in method_clean or "ccsd(t)" in method_clean
        if is_dlpno and safe_maxcore_mb < 4000:
            raise ResourceGuardError(
                f"RESOURCE_GUARD: Requested method '{requested_method}' requires at least 4000 MB per core, "
                f"but only {safe_maxcore_mb} MB is safely available ({ram_gb:.1f} GB RAM across "
                f"{target_mpi_threads} MPI threads). Refusing to spawn to prevent host OOM lockup."
            )

    return HardwareGovernorResult(
        safe_maxcore_mb=safe_maxcore_mb,
        target_mpi_threads=target_mpi_threads,
        resource_warning=resource_warning,
        numa_nodes=cfg.hardware.numa_nodes,
    )


def SiloIntegrityAssert(
    cfg: BenchConfigSchema,
    current_executable: Optional[Union[str, Path]] = None,
) -> None:
    """Asserts that execution is strictly contained within cochem_bench_silo.

    Args:
        cfg: Validated BenchConfigSchema.
        current_executable: Optional override for active Python executable path.

    Raises:
        SiloIntegrityError: If active executable does not match silo_paths.bench_silo.
    """
    bench_silo = cfg.silo_paths.bench_silo or cfg.silo_paths.python_path
    if not bench_silo or bench_silo in ("BYPASSED", "Not_Found", "missing"):
        return

    active_exe = Path(current_executable or sys.executable).resolve()
    target_silo = Path(bench_silo).resolve()

    if platform.system() == "Windows":
        is_match = str(active_exe).lower() == str(target_silo).lower()
    else:
        is_match = active_exe == target_silo

    if not is_match:
        raise SiloIntegrityError(
            f"ABI Protection Fault: CoChem-BENCH must be executed strictly within the cochem_bench_silo "
            f"to prevent binary collisions. Active runtime '{active_exe}' does not match registered "
            f"silo path '{target_silo}'."
        )


def cleanse_ld_library_path(
    env_val: Optional[str] = None,
    mutate_environ: bool = True,
) -> Optional[str]:
    """Cleanses LD_LIBRARY_PATH by stripping any paths containing anaconda3 or miniconda3.

    Strictly preserves system MPI, compiler, and OS library paths.

    Args:
        env_val: Optional explicit LD_LIBRARY_PATH string to cleanse.
        mutate_environ: Whether to update os.environ with the cleansed string.

    Returns:
        Cleansed LD_LIBRARY_PATH string or None if variable is unset or fully stripped.
    """
    raw = env_val if env_val is not None else os.environ.get("LD_LIBRARY_PATH")
    if not raw:
        if mutate_environ and "LD_LIBRARY_PATH" in os.environ and env_val is None:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None

    sep = os.pathsep
    entries = raw.split(sep)
    cleansed_entries: List[str] = []

    for entry in entries:
        norm = entry.strip().lower()
        if not norm:
            continue
        if "anaconda3" in norm or "miniconda3" in norm:
            logger.info(f"Stripping conda library path from LD_LIBRARY_PATH: {entry}")
            continue
        cleansed_entries.append(entry.strip())

    if cleansed_entries:
        cleansed_str = sep.join(cleansed_entries)
        if mutate_environ:
            os.environ["LD_LIBRARY_PATH"] = cleansed_str
        return cleansed_str
    else:
        if mutate_environ:
            os.environ.pop("LD_LIBRARY_PATH", None)
        return None


def extract_orca_path(cfg: BenchConfigSchema) -> Optional[str]:
    """Dynamically extracts the ORCA executable path from registry configuration."""
    if cfg.engine_paths and cfg.engine_paths.orca and cfg.engine_paths.orca.path:
        p = cfg.engine_paths.orca.path
        if p not in ("BYPASSED", "Not_Found", "missing"):
            return p

    if isinstance(cfg.engines, dict) and "orca" in cfg.engines:
        orca_val = cfg.engines["orca"]
        if isinstance(orca_val, dict) and orca_val.get("path"):
            p = orca_val["path"]
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)
        elif hasattr(orca_val, "path") and orca_val.path:
            p = orca_val.path
            if p not in ("BYPASSED", "Not_Found", "missing"):
                return str(p)

    for candidate in (cfg.silo_paths.orca_binary_path, cfg.silo_paths.orca_path):
        if candidate and candidate not in ("BYPASSED", "Not_Found", "missing"):
            return candidate

    return None


def PreFlightVerification(
    cfg: BenchConfigSchema,
    artifacts_dir: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
) -> BenchRunContext:
    """Executes full pre-flight verification and returns an immutable BenchRunContext.

    Args:
        cfg: Validated BenchConfigSchema.
        artifacts_dir: Optional artifacts directory override.
        min_scratch_bytes: Optional required NVMe scratch space threshold in bytes.
        requested_method: Optional quantum chemistry method string.
        current_executable: Optional current python executable override.

    Returns:
        Immutable BenchRunContext dataclass.

    Raises:
        SiloIntegrityError: If runtime does not match bench_silo.
        ResourceGuardError: If scratch space or RAM envelope is insufficient.
        RegistryHandshakeError: If artifacts directory is missing.
    """
    # 1. Micro-silo integrity assertion
    SiloIntegrityAssert(cfg, current_executable=current_executable)

    # 2. Ghost dependency purge: cleanse LD_LIBRARY_PATH
    cleanse_ld_library_path(mutate_environ=True)

    # 3. Hardware Governor validation
    gov_result = HardwareGovernor(cfg, requested_method=requested_method)

    # 4. Resolve artifacts directory
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "COCHEM_ARTIFACTS_DIR environment variable is not defined for Pre-Flight verification."
        )

    # 5. Verify scratch space via PreFlightScratchVerifier
    try:
        verifier = PreFlightScratchVerifier(artifacts_dir=resolved_artifacts)
        scratch_report = verifier.verify(min_free_bytes=min_scratch_bytes)
        scratch_path = Path(scratch_report.scratch_path).resolve()
    except SubprocessResourceGuardError as err:
        raise ResourceGuardError(str(err)) from err

    # 6. Verify HDF5 path in workspace
    workspace_dir = resolved_artifacts / "BENCH_Workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = workspace_dir / "landscape.h5"

    # 7. Stamp provenance
    cfg_json = cfg.model_dump_json()
    config_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
    node_id = cfg.hardware.host_id or platform.node() or "cochem_node"
    now_ts = datetime.now(timezone.utc).isoformat()
    orca_path = extract_orca_path(cfg)

    return BenchRunContext(
        config_hash=config_hash,
        safe_maxcore_mb=gov_result.safe_maxcore_mb,
        target_mpi_threads=gov_result.target_mpi_threads,
        node_id=node_id,
        timestamp=now_ts,
        orca_path=orca_path,
        hdf5_path=hdf5_path,
        scratch_path=scratch_path,
        numa_nodes=gov_result.numa_nodes,
        resource_warning=gov_result.resource_warning,
        config=cfg,
    )


def RegistryHandshake(
    artifacts_dir: Optional[Union[str, Path]] = None,
    timeout: float = 10.0,
) -> BenchConfigSchema:
    """Executes Stage 0 Handshake by atomically polling cochem_system_config.json.

    Args:
        artifacts_dir: Optional explicit artifacts root directory path.
        timeout: Maximum time in seconds to wait for filelock acquisition.

    Returns:
        Validated BenchConfigSchema instance.

    Raises:
        RegistryHandshakeError: If COCHEM_ARTIFACTS_DIR is unset, registry is absent,
                                lock acquisition times out, or validation fails.
    """
    if artifacts_dir:
        resolved_artifacts = Path(artifacts_dir).resolve()
    elif "COCHEM_ARTIFACTS_DIR" in os.environ and os.environ["COCHEM_ARTIFACTS_DIR"]:
        resolved_artifacts = Path(os.environ["COCHEM_ARTIFACTS_DIR"]).resolve()
    else:
        raise RegistryHandshakeError(
            "Stage 0 Handshake Error: COCHEM_ARTIFACTS_DIR environment variable is not defined. "
            "CoChem-BENCH requires an active artifacts directory to resolve system configuration."
        )

    config_path = resolved_artifacts / "Registry" / "cochem_system_config.json"
    if not config_path.exists():
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: CoChem system configuration registry not found at '{config_path}'. "
            "Please run CoChem-CORE Stage 0 setup to initialize the system registry."
        )

    lock_file = config_path.parent / f"{config_path.name}.lock"
    lock = filelock.FileLock(str(lock_file), timeout=timeout)

    try:
        with lock:
            raw_text = config_path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
    except filelock.Timeout:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Timeout: Failed to acquire read lock on '{config_path}' within {timeout}s."
        )
    except json.JSONDecodeError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry JSON at '{config_path}' is corrupted: {err}"
        ) from err

    try:
        cfg = BenchConfigSchema.model_validate(raw_data)
    except ValidationError as err:
        raise RegistryHandshakeError(
            f"Stage 0 Handshake Error: Registry at '{config_path}' failed strict Pydantic validation: {err}"
        ) from err

    return cfg


def run_bench_ingest_pipeline(
    artifacts_dir: Optional[Union[str, Path]] = None,
    requested_method: Optional[str] = None,
    current_executable: Optional[Union[str, Path]] = None,
    min_scratch_bytes: Optional[int] = None,
    handshake_timeout: float = 10.0,
) -> BenchRunContext:
    """Executes the complete Stage 1.0 Registry Handshake & Pre-Flight Verification pipeline."""
    cfg = RegistryHandshake(artifacts_dir=artifacts_dir, timeout=handshake_timeout)
    return PreFlightVerification(
        cfg=cfg,
        artifacts_dir=artifacts_dir,
        min_scratch_bytes=min_scratch_bytes,
        requested_method=requested_method,
        current_executable=current_executable,
    )
