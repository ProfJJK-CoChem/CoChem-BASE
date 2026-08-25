Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md.
Original prompt:
﻿# Task: Update cochem_bench_ingest.py (Part 2: Silo & Pre-Flight)

## Target File
`cochem_bench\bench_engine\cochem_bench_ingest.py` (relative to repo root)

## Requirements
Append Silo Assertion and Pre-Flight checks to the existing file.

Functions/Components to implement:
1. `SiloIntegrityAssert()`:
   - Compare `sys.executable` against `silo_paths.bench_silo` from registry. Abort if mismatch.
   - Cleanse `LD_LIBRARY_PATH`: Implement logic to strip any paths containing `anaconda3` or `miniconda3` (which cause `libtinfo.so.6` segfaults with ORCA) while strictly preserving system MPI and compiler paths. Do NOT blindly pop the entire variable.
   - Extract `cfg.engine_paths.orca` from registry and store it securely in the `BenchRunContext` dataclass for downstream modules.
2. `Pre-Flight Verification`:
   - Import and call `PreFlightScratchVerifier()` from `cochem_bench.bench_libraries.subprocess_reaper` to check the NVMe capacity. Do not duplicate the `shutil.disk_usage()` logic here.
   - Verify HDF5 path `landscape.h5` in workspace.
   - Stamp provenance: hash of config, `Safe_MaxCore_MB`, physical node ID, and timestamp into a read-only `BenchRunContext` dataclass.

## Safety Contract
- Air-Gap strictly enforced dynamically: NO absolute paths. Use `COCHEM_ARTIFACTS_DIR`.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\__init__.py ---
"""CoChem Bench Engine: Core Scientific Extrapolation & Benchmark Engines (Stages 1.0 - 5.0)."""

from __future__ import annotations

# Stage 1.0 Ingest & Handshake
from bench_engine.cochem_bench_ingest import (
    BenchConfigSchema,
    BenchHardwareSchema,
    BenchRunContext,
    BenchSiloPathsSchema,
    HardwareGovernor,
    HardwareGovernorResult,
    PreFlightVerification,
    RegistryHandshake,
    ResourceGuardError,
    SiloIntegrityAssert,
    SiloIntegrityError,
    cleanse_ld_library_path,
    extract_orca_path,
    run_bench_ingest_pipeline,
)
# Stage 2.0 CBS
from bench_engine.cochem_bench_cbs import (
    CBSExtrapolationResult,
    DualBasisDispatcher,
    HelgakerExtrapolator,
    ResidualFitAnalyzer,
    SlowConvInterceptionResult,
    SlowConvInterceptor,
    commit_cbs_to_hdf5,
    read_cbs_from_hdf5,
    run_cbs_pipeline,
    CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL,
    PARAMETER_MATRIX,
)
# Stage 3.0 CV
from bench_engine.cochem_bench_cv import (
    CoreValenceMapper,
    CVCorrectionResult,
    DeltaExtractor,
    DualCorrelationEngine,
    commit_cv_to_hdf5,
    read_cv_from_hdf5,
    run_cv_pipeline,
)
# Stage 4.0 Relativistic & SOC
from bench_engine.cochem_bench_rel import (
    DeltaRelExtractor,
    RelCorrectionResult,
    RelativisticExecutionError,
    RelativisticHamiltonianInjector,
    RelativisticInputError,
    SpinOrbitCoupler,
    X2CDivergenceError,
    X2CHandler,
    commit_rel_to_hdf5,
    read_rel_from_hdf5,
    run_rel_pipeline,
    DEFAULT_RELATIVISTIC_Z_THRESHOLD,
    HARTREE_TO_KCAL_MOL,
)
# Stage 5.0 Exporter
from bench_engine.cochem_bench_export import (
    AirGapPackageMissingError,
    AirGapVerifier,
    CompositeAggregator,
    CompositeEnergyRecord,
    ExportPipelineResult,
    HDF5SchemaError,
    LaTeXExportConfig,
    MissingZPVEError,
    PublicationArchiver,
    ProvenanceStamper,
    SiunitxLaTeXCompiler,
    run_export_pipeline,
)

__all__ = [
    # Stage 1.0 Ingest & Handshake
    "BenchConfigSchema",
    "BenchHardwareSchema",
    "BenchRunContext",
    "BenchSiloPathsSchema",
    "HardwareGovernor",
    "HardwareGovernorResult",
    "PreFlightVerification",
    "RegistryHandshake",
    "ResourceGuardError",
    "SiloIntegrityError",
    "cleanse_ld_library_path",
    "extract_orca_path",
    "run_bench_ingest_pipeline",
    # Stage 2.0 CBS
    "DualBasisDispatcher",
    "HelgakerExtrapolator",
    "ResidualFitAnalyzer",
    "SlowConvInterceptor",
    "CBSExtrapolationResult",
    "SlowConvInterceptionResult",
    "commit_cbs_to_hdf5",
    "read_cbs_from_hdf5",
    "run_cbs_pipeline",
    "CBS_UNCERTAINTY_THRESHOLD_KCAL_MOL",
    "PARAMETER_MATRIX",
    # Stage 3.0 CV
    "CoreValenceMapper",
    "DualCorrelationEngine",
    "DeltaExtractor",
    "CVCorrectionResult",
    "commit_cv_to_hdf5",
    "read_cv_from_hdf5",
    "run_cv_pipeline",
    # Stage 4.0 Relativistic & SOC
    "RelativisticHamiltonianInjector",
    "X2CHandler",
    "X2CDivergenceError",
    "RelativisticExecutionError",
    "RelativisticInputError",
    "SpinOrbitCoupler",
    "DeltaRelExtractor",
    "RelCorrectionResult",
    "commit_rel_to_hdf5",
    "read_rel_from_hdf5",
    "run_rel_pipeline",
    "DEFAULT_RELATIVISTIC_Z_THRESHOLD",
    "HARTREE_TO_KCAL_MOL",
    # Stage 5.0 Exporter
    "CompositeAggregator",
    "CompositeEnergyRecord",
    "ExportPipelineResult",
    "SiunitxLaTeXCompiler",
    "LaTeXExportConfig",
    "ProvenanceStamper",
    "AirGapVerifier",
    "PublicationArchiver",
    "MissingZPVEError",
    "AirGapPackageMissingError",
    "HDF5SchemaError",
    "run_export_pipeline",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\bench_engine\cochem_bench_ingest.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_ingest.py ---
#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 1.0 Registry Ingestion & Pre-Flight Engine.

Module: tests/test_cochem_bench_ingest.py
Target Implementation: cochem_bench.bench_engine.cochem_bench_ingest

Authoritative Requirements & Standards:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 4 Registry Polling & The Stage 0 Handshake (Stage 1.0).txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.finished_coding_prompts\draft_task4_ingest_pt1.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task4_ingest_pt2.md
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import filelock
import pytest
from pydantic import ValidationError

from cochem_bench.bench_engine.cochem_bench_ingest import (
    BenchConfigSchema,
    BenchHardwareSchema,
    BenchRunContext,
    BenchSiloPathsSchema,
    HardwareGovernor,
    HardwareGovernorResult,
    PreFlightVerification,
    RegistryHandshake,
    ResourceGuardError,
    SiloIntegrityAssert,
    SiloIntegrityError,
    cleanse_ld_library_path,
    extract_orca_path,
    run_bench_ingest_pipeline,
)
from cochem_bench.bench_libraries.subprocess_reaper import (
    PreFlightScratchVerifier,
    DEFAULT_MIN_FREE_SCRATCH_BYTES,
)


# ==============================================================================
# Authentic Test Fixtures
# ==============================================================================

@pytest.fixture
def authentic_registry_data(tmp_path: Path) -> Dict[str, Any]:
    """Generates an authentic CoChem Stage 0 registry dictionary."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    scratch_dir = artifacts_dir / "Scratch"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    return {
        "schema_version": "4.0.0",
        "registry_version": "4.0",
        "status": "LOCKED",
        "hardware": {
            "ram_gb": 64.0,
            "cpu_physical_cores": 8,
            "allocatable_compute_cores": 7,
            "logical_cpu_cores": 16,
            "vram_gb": 24.0,
            "gpu_profile": "NVIDIA RTX 4090",
            "avx512_support": True,
            "host_id": "cochem-node-01",
            "numa_nodes": 1,
            "os_target": "Local-Windows" if platform.system() == "Windows" else "Local-Linux",
        },
        "environment": {
            "artifacts_dir": str(artifacts_dir),
            "scratch_dir": str(scratch_dir),
            "codata_version": "2018",
            "isotopic_mass_locking": True,
        },
        "silo_paths": {
            "bench_silo": str(Path(sys.executable).resolve()),
            "orca_binary_path": "C:\\ORCA\\orca.exe" if platform.system() == "Windows" else "/opt/orca/orca",
            "xtb_binary_path": "C:\\xTB\\xtb.exe" if platform.system() == "Windows" else "/opt/xtb/bin/xtb",
            "mpirun_binary_path": "C:\\MPI\\mpirun.exe" if platform.system() == "Windows" else "/usr/bin/mpirun",
        },
        "engines": {
            "orca": {
                "status": "found",
                "path": "C:\\ORCA\\orca.exe" if platform.system() == "Windows" else "/opt/orca/orca",
                "version": "6.1.1",
            },
            "xtb": {
                "status": "found",
                "path": "C:\\xTB\\xtb.exe" if platform.system() == "Windows" else "/opt/xtb/bin/xtb",
                "version": "6.7.0",
            },
        },
    }


@pytest.fixture
def stage0_environment(tmp_path: Path, authentic_registry_data: Dict[str, Any]) -> Generator[Path, None, None]:
    """Sets up an authentic filesystem environment with cochem_system_config.json."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    registry_dir = artifacts_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(authentic_registry_data, indent=2), encoding="utf-8")

    prev_artifacts = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(artifacts_dir)
    try:
        yield artifacts_dir
    finally:
        if prev_artifacts is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_artifacts
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


# ==============================================================================
# 1. Pydantic Schema Validation Tests
# ==============================================================================

def test_bench_config_schema_valid(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that authentic registry data parses correctly into BenchConfigSchema."""
    schema = BenchConfigSchema.model_validate(authentic_registry_data)
    assert schema.schema_version == "4.0.0"
    assert schema.hardware.ram_gb == 64.0
    assert schema.hardware.cpu_physical_cores == 8
    assert schema.available_ram_gb == 64.0
    assert schema.physical_cores == 8
    assert schema.silo_paths.bench_silo is not None
    assert schema.engines is not None


def test_bench_config_schema_invalid_ram_type(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that invalid non-numeric RAM types raise a strict ValidationError."""
    corrupted = dict(authentic_registry_data)
    corrupted["hardware"] = dict(corrupted["hardware"])
    corrupted["hardware"]["ram_gb"] = "not_a_number_and_invalid"

    with pytest.raises(ValidationError):
        BenchConfigSchema.model_validate(corrupted)


def test_bench_config_schema_missing_hardware(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that missing required hardware section raises ValidationError."""
    corrupted = dict(authentic_registry_data)
    del corrupted["hardware"]

    with pytest.raises(ValidationError):
        BenchConfigSchema.model_validate(corrupted)


# ==============================================================================
# 2. Stage 0 Registry Handshake Tests
# ==============================================================================

def test_registry_handshake_success(stage0_environment: Path) -> None:
    """Validate successful Stage 0 handshake from COCHEM_ARTIFACTS_DIR environment."""
    cfg = RegistryHandshake()
    assert isinstance(cfg, BenchConfigSchema)
    assert cfg.hardware.ram_gb == 64.0
    assert cfg.hardware.cpu_physical_cores == 8


def test_registry_handshake_with_explicit_artifacts_dir(stage0_environment: Path) -> None:
    """Validate successful Stage 0 handshake when passing artifacts_dir explicitly."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    assert isinstance(cfg, BenchConfigSchema)
    assert cfg.hardware.ram_gb == 64.0


def test_registry_handshake_missing_env_var() -> None:
    """Validate that missing COCHEM_ARTIFACTS_DIR env var raises fatal EnvironmentError."""
    prev_val = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ.pop("COCHEM_ARTIFACTS_DIR", None)
    try:
        with pytest.raises(EnvironmentError) as exc_info:
            RegistryHandshake()
        assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value)
    finally:
        if prev_val is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_val


def test_registry_handshake_missing_registry_file(tmp_path: Path) -> None:
    """Validate that missing cochem_system_config.json raises fatal EnvironmentError with Stage 0 instructions."""
    empty_artifacts = tmp_path / "empty_artifacts"
    empty_artifacts.mkdir(parents=True, exist_ok=True)
    prev_val = os.environ.get("COCHEM_ARTIFACTS_DIR")
    os.environ["COCHEM_ARTIFACTS_DIR"] = str(empty_artifacts)

    try:
        with pytest.raises(EnvironmentError) as exc_info:
            RegistryHandshake()
        msg = str(exc_info.value)
        assert "cochem_system_config.json" in msg
        assert "Stage 0" in msg
    finally:
        if prev_val is not None:
            os.environ["COCHEM_ARTIFACTS_DIR"] = prev_val
        else:
            os.environ.pop("COCHEM_ARTIFACTS_DIR", None)


def test_registry_handshake_filelock_behavior(stage0_environment: Path) -> None:
    """Validate that RegistryHandshake uses filelock without deadlocking."""
    config_path = stage0_environment / "Registry" / "cochem_system_config.json"
    lock_path = stage0_environment / "Registry" / "cochem_system_config.json.lock"

    lock = filelock.FileLock(str(lock_path), timeout=5.0)
    with lock:
        pass

    cfg = RegistryHandshake(artifacts_dir=stage0_environment, timeout=5.0)
    assert cfg.hardware.ram_gb == 64.0


# ==============================================================================
# 3. Hardware Governor Tests
# ==============================================================================

def test_hardware_governor_high_spec_node(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate %maxcore and MPI thread allocation on 8-core, 64 GB RAM system.

    Formula:
      Target_MPI_Threads = 8 - 1 = 7
      Safe_MaxCore_MB = floor(((64 * 1024) * 0.85) / 7) = floor(55705.6 / 7) = 7957 MB
    """
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    gov = HardwareGovernor(cfg)

    expected_threads = 7
    expected_maxcore = math.floor(((64.0 * 1024.0) * 0.85) / 7)  # 7957 MB

    assert gov.target_mpi_threads == expected_threads
    assert gov.safe_maxcore_mb == expected_maxcore
    assert not gov.resource_warning


def test_hardware_governor_low_core_node(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate %maxcore and thread allocation when physical cores <= 4.

    For physical_cores = 4:
      Target_MPI_Threads = 4
      Safe_MaxCore_MB = floor(((16 * 1024) * 0.85) / 4) = floor(13926.4 / 4) = 3481 MB
    """
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 4
    data["hardware"]["ram_gb"] = 16.0

    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg)

    assert gov.target_mpi_threads == 4
    assert gov.safe_maxcore_mb == math.floor(((16.0 * 1024.0) * 0.85) / 4)
    assert not gov.resource_warning


def test_hardware_governor_resource_warning_below_1500mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that Safe_MaxCore_MB < 1500 MB flags a resource warning."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 8.0

    # 8 cores -> 7 threads. (8 * 1024 * 0.85) / 7 = 6963.2 / 7 = 994 MB < 1500 MB
    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg)

    assert gov.safe_maxcore_mb < 1500
    assert gov.resource_warning is True


def test_hardware_governor_refuses_dlpno_ccsd_t_under_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that DLPNO-CCSD(T) is refused if Safe_MaxCore_MB < 4000 MB."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 24.0

    # 8 cores -> 7 threads. (24 * 1024 * 0.85) / 7 = 20889.6 / 7 = 2984 MB (< 4000 MB)
    cfg = BenchConfigSchema.model_validate(data)

    with pytest.raises(ResourceGuardError) as exc_info:
        HardwareGovernor(cfg, requested_method="DLPNO-CCSD(T)")
    assert "4000 MB" in str(exc_info.value)
    assert "DLPNO-CCSD(T)" in str(exc_info.value)


def test_hardware_governor_allows_dlpno_ccsd_t_above_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that DLPNO-CCSD(T) is permitted if Safe_MaxCore_MB >= 4000 MB."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    gov = HardwareGovernor(cfg, requested_method="DLPNO-CCSD(T)")
    assert gov.safe_maxcore_mb >= 4000
    assert not gov.resource_warning


def test_hardware_governor_allows_dft_under_4000mb(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that non-DLPNO methods (e.g. B3LYP-D4) are allowed even if < 4000 MB."""
    data = dict(authentic_registry_data)
    data["hardware"] = dict(data["hardware"])
    data["hardware"]["cpu_physical_cores"] = 8
    data["hardware"]["ram_gb"] = 24.0

    cfg = BenchConfigSchema.model_validate(data)
    gov = HardwareGovernor(cfg, requested_method="B3LYP-D4")
    assert gov.safe_maxcore_mb < 4000
    assert gov.safe_maxcore_mb >= 1500
    assert not gov.resource_warning


# ==============================================================================
# 4. Silo Integrity Assertion Tests
# ==============================================================================

def test_silo_integrity_assert_success(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that active executable matching bench_silo passes verification."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    SiloIntegrityAssert(cfg, current_executable=sys.executable)


def test_silo_integrity_assert_mismatch_raises(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that active executable mismatching bench_silo raises SiloIntegrityError."""
    data = dict(authentic_registry_data)
    data["silo_paths"] = dict(data["silo_paths"])
    data["silo_paths"]["bench_silo"] = "C:\\Different_Venv\\python.exe" if platform.system() == "Windows" else "/opt/different_venv/bin/python"

    cfg = BenchConfigSchema.model_validate(data)
    with pytest.raises(SiloIntegrityError) as exc_info:
        SiloIntegrityAssert(cfg, current_executable=sys.executable)

    msg = str(exc_info.value)
    assert "ABI Protection Fault" in msg
    assert "cochem_bench_silo" in msg


def test_silo_integrity_assert_bypassed_token(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate that 'BYPASSED' token in bench_silo skips the integrity check."""
    data = dict(authentic_registry_data)
    data["silo_paths"] = dict(data["silo_paths"])
    data["silo_paths"]["bench_silo"] = "BYPASSED"

    cfg = BenchConfigSchema.model_validate(data)
    SiloIntegrityAssert(cfg, current_executable="/foreign/bin/python")


# ==============================================================================
# 5. LD_LIBRARY_PATH Cleansing Tests
# ==============================================================================

def test_cleanse_ld_library_path_strips_anaconda_and_miniconda() -> None:
    """Validate that cleanse_ld_library_path strips conda paths while preserving system MPI."""
    sep = os.pathsep
    raw_path = sep.join([
        "/usr/lib/x86_64-linux-gnu",
        "/home/user/anaconda3/lib",
        "/opt/openmpi/lib",
        "/home/user/miniconda3/envs/test/lib",
        "/usr/local/gcc/lib64",
    ])

    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ["LD_LIBRARY_PATH"] = raw_path
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)

        assert cleansed is not None
        cleansed_parts = cleansed.split(sep)
        assert "/usr/lib/x86_64-linux-gnu" in cleansed_parts
        assert "/opt/openmpi/lib" in cleansed_parts
        assert "/usr/local/gcc/lib64" in cleansed_parts
        assert "/home/user/anaconda3/lib" not in cleansed_parts
        assert "/home/user/miniconda3/envs/test/lib" not in cleansed_parts

        assert os.environ.get("LD_LIBRARY_PATH") == cleansed
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)


def test_cleanse_ld_library_path_only_conda_paths() -> None:
    """Validate that if LD_LIBRARY_PATH contains only conda paths, it is safely purged."""
    sep = os.pathsep
    raw_path = sep.join([
        "/home/user/anaconda3/lib",
        "/home/user/miniconda3/lib",
    ])

    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ["LD_LIBRARY_PATH"] = raw_path
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)

        assert cleansed is None
        assert "LD_LIBRARY_PATH" not in os.environ
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)


def test_cleanse_ld_library_path_unset() -> None:
    """Validate that unset LD_LIBRARY_PATH is handled gracefully."""
    prev_ld = os.environ.get("LD_LIBRARY_PATH")
    os.environ.pop("LD_LIBRARY_PATH", None)
    try:
        cleansed = cleanse_ld_library_path(mutate_environ=True)
        assert cleansed is None
    finally:
        if prev_ld is not None:
            os.environ["LD_LIBRARY_PATH"] = prev_ld


# ==============================================================================
# 6. ORCA Path Extraction Tests
# ==============================================================================

def test_extract_orca_path_from_engines(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate extracting ORCA binary path from engines section."""
    cfg = BenchConfigSchema.model_validate(authentic_registry_data)
    orca_path = extract_orca_path(cfg)
    assert orca_path is not None
    assert "orca" in orca_path.lower()


def test_extract_orca_path_from_silo_paths(authentic_registry_data: Dict[str, Any]) -> None:
    """Validate extracting ORCA path from silo_paths when engines is empty."""
    data = dict(authentic_registry_data)
    data["engines"] = {}
    cfg = BenchConfigSchema.model_validate(data)
    orca_path = extract_orca_path(cfg)
    assert orca_path is not None
    assert "orca" in orca_path.lower()


# ==============================================================================
# 7. Pre-Flight Verification & Provenance Tests
# ==============================================================================

def test_preflight_verification_success(stage0_environment: Path) -> None:
    """Validate that PreFlightVerification executes scratch check, verifies HDF5, and returns BenchRunContext."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    context = PreFlightVerification(
        cfg=cfg,
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )

    assert isinstance(context, BenchRunContext)
    assert context.safe_maxcore_mb > 0
    assert context.target_mpi_threads > 0
    assert context.node_id != ""
    assert context.timestamp != ""
    assert context.config_hash != ""
    assert context.hdf5_path == stage0_environment / "BENCH_Workspace" / "landscape.h5"
    assert context.scratch_path.exists()
    assert not context.resource_warning


def test_preflight_context_immutability(stage0_environment: Path) -> None:
    """Validate that BenchRunContext is a frozen read-only dataclass."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    context = PreFlightVerification(
        cfg=cfg,
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.safe_maxcore_mb = 99999  # type: ignore[misc]


def test_preflight_insufficient_scratch_raises(stage0_environment: Path) -> None:
    """Validate that insufficient scratch disk space raises ResourceGuardError."""
    cfg = RegistryHandshake(artifacts_dir=stage0_environment)
    huge_bytes = 1024 * 1024 * 1024 * 1024 * 1024

    with pytest.raises(ResourceGuardError) as exc_info:
        PreFlightVerification(
            cfg=cfg,
            artifacts_dir=stage0_environment,
            min_scratch_bytes=huge_bytes,
            current_executable=sys.executable,
        )
    assert "RESOURCE_GUARD" in str(exc_info.value)


# ==============================================================================
# 8. End-to-End Pipeline Execution Tests
# ==============================================================================

def test_run_bench_ingest_pipeline_e2e(stage0_environment: Path) -> None:
    """Validate end-to-end execution of run_bench_ingest_pipeline."""
    context = run_bench_ingest_pipeline(
        artifacts_dir=stage0_environment,
        current_executable=sys.executable,
    )
    assert isinstance(context, BenchRunContext)
    assert context.safe_maxcore_mb == math.floor(((64.0 * 1024.0) * 0.85) / 7)
    assert context.target_mpi_threads == 7
    assert len(context.config_hash) == 64

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.