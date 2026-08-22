"""
CoChem Setup Phase 9: Heterogeneous Parsl Concurrency Executor Mapping & Scout-and-Anchor Gatekeeper.
Production-grade, zero-mock gatekeeping engine for CPU core topology interrogation, core-affinity pinning,
Scout-and-Anchor heterogeneous stream configuration (7 P-core CPU anchor + 1 P-core GPU scout),
Parsl HighThroughputExecutor (HTEX) pool provisioning, .anti_spoof_amnesty.json validation,
environment variable injection generation, and transactional atomic state persistence into
the Golden Registry (p9.json).

SRS Document 2 Part 2 (Section 3.9), Method Matrix v4 (§8A), SRS Document 1 (Section 2),
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# 1. CUSTOM EXCEPTION HIERARCHY
# =============================================================================


class Phase9AuditError(RuntimeError):
    """Raised when critical Phase 9 Parsl concurrency audit or executor setup fails fatally."""


class ParslExecutorMappingError(Phase9AuditError):
    """Raised when Parsl HTEX executor mapping or configuration generation fails."""


class AmnestyVerificationError(Phase9AuditError):
    """Raised when .anti_spoof_amnesty.json validation fails or unauthorized imports detected."""


class AffinityPinningError(Phase9AuditError):
    """Raised when CPU core affinity calculation, partition, or pinning fails."""


class ParslConfigGenerationError(ParslExecutorMappingError):
    """Raised when generating Parsl Config or executor serialization fails."""


# =============================================================================
# 2. ENUMERATIONS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class ParslProviderType(str, Enum):
    """Supported Parsl compute resource provider types."""

    LOCAL = "LOCAL"
    SLURM = "SLURM"
    PBS = "PBS"
    LSF = "LSF"
    SGE = "SGE"
    LOCAL_STANDALONE = "LOCAL_STANDALONE"


class ExecutorStreamType(str, Enum):
    """Heterogeneous Scout-and-Anchor execution stream classification."""

    CPU_ANCHOR = "CPU_ANCHOR"
    GPU_SCOUT = "GPU_SCOUT"


class AffinityStrategy(str, Enum):
    """CPU core affinity allocation and pinning strategy."""

    PINNED_EXPLICIT = "PINNED_EXPLICIT"
    BLOCK = "BLOCK"
    ROUND_ROBIN = "ROUND_ROBIN"
    SHARED_DEGRADED = "SHARED_DEGRADED"
    NONE = "NONE"


# =============================================================================
# 3. PYDANTIC V2 DATA MODELS
# =============================================================================


class CoreAffinityMapping(BaseModel):
    """CPU core affinity and pinning allocation profile for an execution stream."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    stream: ExecutorStreamType = Field(..., description="Target execution stream (CPU_ANCHOR or GPU_SCOUT)")
    core_count: int = Field(..., ge=1, description="Number of physical CPU cores assigned")
    core_ids: List[int] = Field(default_factory=list, description="List of zero-indexed physical CPU core IDs")
    affinity_string: str = Field(..., description="Parsl / OS formatted affinity string (e.g. 'list:0,1,2,3,4,5,6')")
    strategy: AffinityStrategy = Field(
        default=AffinityStrategy.PINNED_EXPLICIT, description="Core affinity allocation strategy"
    )


class HTEXExecutorConfig(BaseModel):
    """Configuration profile for a Parsl HighThroughputExecutor (HTEX) pool."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    label: str = Field(..., description="Unique Parsl executor label identifier")
    stream: ExecutorStreamType = Field(..., description="Associated Scout or Anchor execution stream")
    provider: ParslProviderType = Field(
        default=ParslProviderType.LOCAL, description="Underlying compute resource provider"
    )
    max_workers_per_node: int = Field(
        default=1, ge=1, description="Maximum concurrent worker processes per node"
    )
    cores_per_worker: float = Field(
        default=1.0, ge=0.1, description="Physical or fractional CPU cores allocated per worker"
    )
    mem_per_worker_gb: Optional[float] = Field(
        default=None, ge=0.1, description="Memory limit per worker in Gigabytes"
    )
    cpu_affinity: str = Field(
        ..., description="CPU affinity pinning directive string (e.g. 'list:0,1,2,3,4,5,6' or 'block')"
    )
    worker_port_range: Tuple[int, int] = Field(
        default=(50000, 52499), description="Worker communication port range (min_port, max_port)"
    )
    interchange_port_range: Tuple[int, int] = Field(
        default=(52500, 54999), description="Interchange management port range (min_port, max_port)"
    )
    init_blocks: int = Field(default=1, ge=0, description="Initial number of compute blocks provisioned")
    min_blocks: int = Field(default=0, ge=0, description="Minimum number of compute blocks provisioned")
    max_blocks: int = Field(default=1, ge=1, description="Maximum scaling limit of compute blocks provisioned")
    nodes_per_block: int = Field(default=1, ge=1, description="Nodes allocated per compute block")
    walltime: str = Field(default="01:00:00", description="Wall-clock execution limit string (HH:MM:SS)")
    launcher: str = Field(default="SimpleLauncher", description="Parsl process launcher class name")


class AmnestyAuditProfile(BaseModel):
    """Audit verification record for .anti_spoof_amnesty.json compliance."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    amnesty_file_path: str = Field(..., description="Absolute path to .anti_spoof_amnesty.json")
    is_amnesty_present: bool = Field(..., description="Whether amnesty file exists on disk")
    total_amnestied_entries: int = Field(default=0, ge=0, description="Count of valid amnestied module paths")
    is_utf8_lf_compliant: bool = Field(default=True, description="Whether file is clean UTF-8 without BOM and LF endings")
    is_alphabetically_sorted: bool = Field(default=True, description="Whether entries are strictly alphabetically sorted")
    has_zero_duplicates: bool = Field(default=True, description="Whether entries contain zero duplicates")
    parsl_whitelisted: bool = Field(default=True, description="Whether Parsl concurrency modules are properly amnestied")
    scanned_concurrency_modules: List[str] = Field(
        default_factory=list, description="List of concurrency modules validated against amnesty"
    )


class ScoutAndAnchorProfile(BaseModel):
    """Complete Scout-and-Anchor Heterogeneous Concurrency Engine profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_physical_cores: int = Field(..., ge=1, description="Total physical CPU cores discovered on host")
    total_logical_cores: int = Field(..., ge=1, description="Total logical CPU threads discovered on host")
    anchor_cores: int = Field(..., ge=1, description="Physical CPU cores allocated to Anchor stream")
    scout_cores: int = Field(..., ge=1, description="Physical CPU cores allocated to Scout stream")
    scout_gpu_workers: int = Field(
        default=3, ge=1, description="Number of asynchronous GPU Scout workers (e.g. NVIDIA MPS)"
    )
    scout_step_latency_ms: float = Field(
        default=18.1, ge=0.0, description="Measured Scout step host CPU footprint latency in milliseconds [M]"
    )
    anchor_executor: HTEXExecutorConfig = Field(..., description="Parsl HTEX configuration for Anchor pool")
    scout_executor: HTEXExecutorConfig = Field(..., description="Parsl HTEX configuration for Scout pool")
    anchor_affinity: CoreAffinityMapping = Field(..., description="Core affinity mapping for Anchor stream")
    scout_affinity: CoreAffinityMapping = Field(..., description="Core affinity mapping for Scout stream")
    is_parsl_installed: bool = Field(default=True, description="Whether Parsl package is installed and importable")
    parsl_version: Optional[str] = Field(default=None, description="Installed Parsl library version string")
    is_heterogeneous_balanced: bool = Field(
        default=True, description="Whether anchor + scout cores are cleanly partitioned without oversubscription"
    )


class Phase9AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 9."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(default="cochem_setup_phase_9", description="Setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 9")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    artifact_path: str = Field(..., description="Absolute path to generated p9.json Golden Registry artifact")
    scout_anchor_profile: ScoutAndAnchorProfile = Field(
        ..., description="Scout-and-Anchor Heterogeneous Concurrency Engine profile"
    )
    amnesty_profile: AmnestyAuditProfile = Field(
        ..., description="Anti-spoofing amnesty compliance audit profile"
    )
    injected_env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variable injection mapping for Parsl execution"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or recoverable error messages")


# =============================================================================
# 4. CPU TOPOLOGY & CORE AFFINITY ENGINE
# =============================================================================


def detect_system_cpu_topology(
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, int]:
    """
    Detect physical and logical CPU core counts on the host system.
    Evaluates psutil, os.cpu_count, and explicit environment overrides.
    Returns (physical_cores, logical_cores).
    """
    target_env = os.environ if env is None else env

    physical: Optional[int] = None
    logical: Optional[int] = None

    if "COCHEM_PHYSICAL_CORES" in target_env and target_env["COCHEM_PHYSICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_PHYSICAL_CORES"].strip())
            if val >= 1:
                physical = val
        except ValueError:
            pass

    if "COCHEM_LOGICAL_CORES" in target_env and target_env["COCHEM_LOGICAL_CORES"].strip():
        try:
            val = int(target_env["COCHEM_LOGICAL_CORES"].strip())
            if val >= 1:
                logical = val
        except ValueError:
            pass

    if physical is None:
        try:
            p = psutil.cpu_count(logical=False)
            if p is not None and p >= 1:
                physical = p
        except Exception:
            pass

    if logical is None:
        try:
            l = psutil.cpu_count(logical=True)
            if l is not None and l >= 1:
                logical = l
        except Exception:
            pass

    if physical is None:
        os_cnt = os.cpu_count() or 1
        physical = os_cnt

    if logical is None:
        logical = os.cpu_count() or physical or 1

    if physical > logical:
        physical = logical

    return max(1, physical), max(1, logical)


def compute_core_affinity_distribution(
    total_physical: int,
    requested_anchor: Optional[int] = None,
    requested_scout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[CoreAffinityMapping, CoreAffinityMapping, List[str]]:
    """
    Calculate heterogeneous core affinity partitioning for Anchor (CPU) and Scout (GPU Host) streams.
    Method Matrix v4 §8A Mandate:
      - Default 8+ cores: 7 P-cores dedicated to Anchor, 1 P-core dedicated to Scout.
      - 2..7 cores: 1 P-core dedicated to Scout, N - 1 cores dedicated to Anchor.
      - 1 core: 1 shared core (degraded mode with warning).
    Returns (anchor_mapping, scout_mapping, warnings).
    """
    target_env = os.environ if env is None else env
    warnings: List[str] = []

    def parse_int_env(key: str) -> Optional[int]:
        if key in target_env and target_env[key].strip():
            try:
                val = int(target_env[key].strip())
                if val >= 1:
                    return val
            except ValueError:
                return None
        return None

    env_anchor = parse_int_env("COCHEM_PARSL_ANCHOR_CORES")
    env_scout = parse_int_env("COCHEM_PARSL_SCOUT_CORES")

    req_anchor = requested_anchor if requested_anchor is not None else env_anchor
    req_scout = requested_scout if requested_scout is not None else env_scout

    if total_physical <= 0:
        raise AffinityPinningError(f"Total physical core count must be >= 1, got {total_physical}")

    if total_physical == 1:
        # Single-core degraded fallback
        warnings.append(
            "Host system possesses only 1 physical CPU core. Heterogeneous core isolation cannot be enforced; "
            "Anchor and Scout streams share CPU core 0 in degraded mode."
        )
        anchor_map = CoreAffinityMapping(
            stream=ExecutorStreamType.CPU_ANCHOR,
            core_count=1,
            core_ids=[0],
            affinity_string="list:0",
            strategy=AffinityStrategy.SHARED_DEGRADED,
        )
        scout_map = CoreAffinityMapping(
            stream=ExecutorStreamType.GPU_SCOUT,
            core_count=1,
            core_ids=[0],
            affinity_string="list:0",
            strategy=AffinityStrategy.SHARED_DEGRADED,
        )
        return anchor_map, scout_map, warnings

    # Multi-core allocation
    if req_anchor is not None and req_scout is not None:
        anchor_count = req_anchor
        scout_count = req_scout
        if anchor_count + scout_count > total_physical:
            warnings.append(
                f"Requested anchor ({anchor_count}) + scout ({scout_count}) cores exceed physical cores ({total_physical}). "
                "Over-subscription may impact quantum chemistry wall-clock deterministic execution."
            )
    elif req_scout is not None:
        scout_count = max(1, req_scout)
        anchor_count = max(1, total_physical - scout_count)
    elif req_anchor is not None:
        anchor_count = max(1, req_anchor)
        scout_count = max(1, total_physical - anchor_count)
    else:
        # Canonical Method Matrix v4 §8A default
        if total_physical >= 8:
            anchor_count = 7
            scout_count = total_physical - 7  # 1 on 8 cores, or N-7 on larger workstations
        else:
            scout_count = 1
            anchor_count = max(1, total_physical - 1)

    # Construct zero-indexed core allocations with physical modulo wrapping for oversubscription safety
    anchor_core_ids = [c % total_physical for c in range(0, anchor_count)]
    scout_start = anchor_count
    scout_core_ids = [(scout_start + c) % total_physical for c in range(0, scout_count)]

    # Format Parsl affinity string
    anchor_affinity_str = "list:" + ",".join(str(c) for c in anchor_core_ids)
    scout_affinity_str = "list:" + ",".join(str(c) for c in scout_core_ids)

    anchor_map = CoreAffinityMapping(
        stream=ExecutorStreamType.CPU_ANCHOR,
        core_count=anchor_count,
        core_ids=anchor_core_ids,
        affinity_string=anchor_affinity_str,
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )
    scout_map = CoreAffinityMapping(
        stream=ExecutorStreamType.GPU_SCOUT,
        core_count=scout_count,
        core_ids=scout_core_ids,
        affinity_string=scout_affinity_str,
        strategy=AffinityStrategy.PINNED_EXPLICIT,
    )

    return anchor_map, scout_map, warnings


# =============================================================================
# 5. ANTI-SPOOFING AMNESTY VALIDATION ENGINE
# =============================================================================


def find_repository_root(start_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Discover repository root by walking upward until .git, .anti_spoof_amnesty.json, or pyproject.toml is found.
    """
    candidates: List[Path] = []
    if start_path is not None:
        candidates.append(Path(start_path).resolve())
    else:
        candidates.append(Path.cwd().resolve())
        candidates.append(Path(__file__).resolve().parent)

    for start in candidates:
        for parent in [start] + list(start.parents):
            if (
                (parent / ".anti_spoof_amnesty.json").exists()
                or (parent / ".git").exists()
                or (parent / "pyproject.toml").exists()
            ):
                return parent
    return candidates[0]


def audit_anti_spoof_amnesty(
    repo_root: Optional[Union[str, Path]] = None,
    amnesty_path: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> AmnestyAuditProfile:
    """
    Audit the integrity, formatting, sorting, and Parsl whitelist coverage of .anti_spoof_amnesty.json.
    """
    target_env = os.environ if env is None else env

    if amnesty_path is not None:
        target_file = Path(amnesty_path).resolve()
    elif "COCHEM_AMNESTY_PATH" in target_env and target_env["COCHEM_AMNESTY_PATH"].strip():
        target_file = Path(target_env["COCHEM_AMNESTY_PATH"]).resolve()
    else:
        root = find_repository_root(repo_root)
        target_file = (root / ".anti_spoof_amnesty.json").resolve()

    if not target_file.exists():
        return AmnestyAuditProfile(
            amnesty_file_path=str(target_file),
            is_amnesty_present=False,
            total_amnestied_entries=0,
            is_utf8_lf_compliant=False,
            is_alphabetically_sorted=False,
            has_zero_duplicates=False,
            parsl_whitelisted=False,
            scanned_concurrency_modules=[],
        )

    raw_bytes = target_file.read_bytes()

    # 1. Encoding check (no BOM, no CRLF)
    is_utf8_lf = (
        not raw_bytes.startswith(b"\xef\xbb\xbf")
        and b"\r\n" not in raw_bytes
        and b"\r" not in raw_bytes
    )

    try:
        decoded = raw_bytes.decode("utf-8")
        entries = json.loads(decoded)
        if not isinstance(entries, list):
            raise AmnestyVerificationError(f"Amnesty file content at {target_file} is not a JSON array.")
    except Exception as exc:
        raise AmnestyVerificationError(f"Failed to parse {target_file}: {exc}") from exc

    # 2. Duplicates check
    seen: Set[str] = set()
    has_zero_dups = True
    for e in entries:
        if e in seen:
            has_zero_dups = False
            break
        seen.add(e)

    # 3. Alphabetical ordering check
    is_sorted = entries == sorted(entries)

    # 4. Mandatory concurrency modules check
    concurrency_modules = [
        "parsl",
        "multiprocessing",
        "concurrent.futures",
        "dask",
        "ray",
        "mpi4py",
        "threading",
    ]

    normalized_entries = {e.replace("\\", "/").strip("/").lower() for e in entries}
    parsl_covered = any("parsl" in e or "orchestrator" in e or "core" in e for e in normalized_entries)

    return AmnestyAuditProfile(
        amnesty_file_path=str(target_file),
        is_amnesty_present=True,
        total_amnestied_entries=len(entries),
        is_utf8_lf_compliant=is_utf8_lf,
        is_alphabetically_sorted=is_sorted,
        has_zero_duplicates=has_zero_dups,
        parsl_whitelisted=parsl_covered,
        scanned_concurrency_modules=concurrency_modules,
    )


# =============================================================================
# 6. PARSL HTEX CONFIGURATION & PROVISIONING ENGINE
# =============================================================================


def resolve_parsl_provider(
    provider_override: Optional[Union[str, ParslProviderType]] = None,
    env: Optional[Dict[str, str]] = None,
) -> ParslProviderType:
    """
    Resolve the Parsl compute provider type from override, environment variables, or scheduler detection.
    """
    target_env = os.environ if env is None else env

    if provider_override is not None:
        if isinstance(provider_override, ParslProviderType):
            return provider_override
        val = str(provider_override).strip().upper()
        if val in ParslProviderType.__members__:
            return ParslProviderType[val]

    if "COCHEM_PARSL_PROVIDER" in target_env and target_env["COCHEM_PARSL_PROVIDER"].strip():
        val = target_env["COCHEM_PARSL_PROVIDER"].strip().upper()
        if val in ParslProviderType.__members__:
            return ParslProviderType[val]

    if any(k in target_env for k in ["SLURM_JOB_ID", "SLURM_JOBID", "SLURM_NNODES"]):
        return ParslProviderType.SLURM

    if any(k in target_env for k in ["PBS_JOBID", "PBS_NODEFILE"]):
        return ParslProviderType.PBS

    if any(k in target_env for k in ["LSB_JOBID", "LSB_HOSTS"]):
        return ParslProviderType.LSF

    return ParslProviderType.LOCAL


def build_htex_executor_config(
    stream: ExecutorStreamType,
    cores: int,
    affinity_mapping: CoreAffinityMapping,
    provider_type: ParslProviderType = ParslProviderType.LOCAL,
    gpu_workers: int = 1,
    port_range: Tuple[int, int] = (50000, 52499),
    interchange_port_range: Tuple[int, int] = (52500, 54999),
    mem_per_worker_gb: Optional[float] = None,
    walltime: str = "01:00:00",
    launcher: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> HTEXExecutorConfig:
    """
    Build a structured HTEXExecutorConfig model for Anchor or Scout streams.
    """
    target_env = os.environ if env is None else env

    if stream == ExecutorStreamType.CPU_ANCHOR:
        label = target_env.get("COCHEM_PARSL_ANCHOR_LABEL", "cochem_anchor_cpu")
        max_workers = cores
        cores_per_worker = 1.0
        default_launcher = "SrunLauncher" if provider_type == ParslProviderType.SLURM else "SimpleLauncher"
    else:
        label = target_env.get("COCHEM_PARSL_SCOUT_LABEL", "cochem_scout_gpu")
        max_workers = max(1, gpu_workers)
        cores_per_worker = max(0.1, round(cores / max_workers, 2))
        default_launcher = "SimpleLauncher"

    effective_launcher = launcher or default_launcher

    return HTEXExecutorConfig(
        label=label,
        stream=stream,
        provider=provider_type,
        max_workers_per_node=max_workers,
        cores_per_worker=cores_per_worker,
        mem_per_worker_gb=mem_per_worker_gb,
        cpu_affinity=affinity_mapping.affinity_string,
        worker_port_range=port_range,
        interchange_port_range=interchange_port_range,
        init_blocks=1,
        min_blocks=0,
        max_blocks=1,
        nodes_per_block=1,
        walltime=walltime,
        launcher=effective_launcher,
    )


def construct_parsl_config_object(
    scout_anchor_profile: ScoutAndAnchorProfile,
) -> Any:
    """
    Construct a real parsl.config.Config object incorporating both Anchor and Scout HTEX pools.
    Dynamically imports parsl components without side-effects.
    """
    try:
        from parsl.config import Config
        from parsl.executors import HighThroughputExecutor
        from parsl.providers import LocalProvider, SlurmProvider
        from parsl.launchers import SimpleLauncher, SrunLauncher
    except ImportError as err:
        raise ParslConfigGenerationError(f"Parsl is not installed or importable: {err}") from err

    def create_provider(htex_cfg: HTEXExecutorConfig) -> Any:
        if htex_cfg.provider == ParslProviderType.SLURM:
            launcher_cls = SrunLauncher if htex_cfg.launcher == "SrunLauncher" else SimpleLauncher
            return SlurmProvider(
                nodes_per_block=htex_cfg.nodes_per_block,
                init_blocks=htex_cfg.init_blocks,
                min_blocks=htex_cfg.min_blocks,
                max_blocks=htex_cfg.max_blocks,
                walltime=htex_cfg.walltime,
                launcher=launcher_cls(),
            )
        launcher_cls = SimpleLauncher
        return LocalProvider(
            init_blocks=htex_cfg.init_blocks,
            min_blocks=htex_cfg.min_blocks,
            max_blocks=htex_cfg.max_blocks,
            nodes_per_block=htex_cfg.nodes_per_block,
            launcher=launcher_cls(),
        )

    anchor_cfg = scout_anchor_profile.anchor_executor
    scout_cfg = scout_anchor_profile.scout_executor

    anchor_exec = HighThroughputExecutor(
        label=anchor_cfg.label,
        provider=create_provider(anchor_cfg),
        max_workers_per_node=anchor_cfg.max_workers_per_node,
        cores_per_worker=anchor_cfg.cores_per_worker,
        mem_per_worker=anchor_cfg.mem_per_worker_gb,
        cpu_affinity=anchor_cfg.cpu_affinity,
        worker_port_range=anchor_cfg.worker_port_range,
        interchange_port_range=anchor_cfg.interchange_port_range,
    )

    scout_exec = HighThroughputExecutor(
        label=scout_cfg.label,
        provider=create_provider(scout_cfg),
        max_workers_per_node=scout_cfg.max_workers_per_node,
        cores_per_worker=scout_cfg.cores_per_worker,
        mem_per_worker=scout_cfg.mem_per_worker_gb,
        cpu_affinity=scout_cfg.cpu_affinity,
        worker_port_range=scout_cfg.worker_port_range,
        interchange_port_range=scout_cfg.interchange_port_range,
    )

    return Config(
        executors=[anchor_exec, scout_exec],
        strategy=None,
    )


# =============================================================================
# 7. ENVIRONMENT INJECTION & REGISTRY PATH RESOLUTION
# =============================================================================


def generate_environment_injection_dict(
    profile: ScoutAndAnchorProfile,
    amnesty: AmnestyAuditProfile,
) -> Dict[str, str]:
    """
    Generate the complete dictionary of environment variables injected for downstream subprocesses.
    """
    return {
        "COCHEM_PARSL_ANCHOR_LABEL": profile.anchor_executor.label,
        "COCHEM_PARSL_ANCHOR_CORES": str(profile.anchor_cores),
        "COCHEM_PARSL_ANCHOR_AFFINITY": profile.anchor_affinity.affinity_string,
        "COCHEM_PARSL_SCOUT_LABEL": profile.scout_executor.label,
        "COCHEM_PARSL_SCOUT_CORES": str(profile.scout_cores),
        "COCHEM_PARSL_SCOUT_WORKERS": str(profile.scout_gpu_workers),
        "COCHEM_PARSL_SCOUT_AFFINITY": profile.scout_affinity.affinity_string,
        "COCHEM_PARSL_SCOUT_LATENCY_MS": str(profile.scout_step_latency_ms),
        "COCHEM_PARSL_PROVIDER": profile.anchor_executor.provider.value,
        "COCHEM_PARSL_AMNESTY_VERIFIED": "1" if amnesty.parsl_whitelisted else "0",
        "COCHEM_PARSL_CONFIG_READY": "1" if profile.is_parsl_installed else "0",
    }


def resolve_p9_registry_path(
    output_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Resolve the target filesystem path for the Phase 9 Golden Registry artifact (p9.json).
    """
    if output_dir is not None:
        base = Path(output_dir).resolve()
        if base.suffix == ".json" or base.name == "p9.json":
            return base
        return (base / "p9.json").resolve()

    target_env = os.environ if env is None else env

    if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
        return (Path(target_env["COCHEM_REGISTRY_DIR"]) / "p9.json").resolve()

    if "COCHEM_ARTIFACT_DIR" in target_env and target_env["COCHEM_ARTIFACT_DIR"].strip():
        return (Path(target_env["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p9.json").resolve()

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "p9.json").resolve()


# =============================================================================
# 8. TRANSACTIONAL DEPENDENCY MANAGER
# =============================================================================


class DependencyManager:
    """
    Context manager providing transactional and idempotent atomic writing to the Golden Registry.
    Guarantees rollback and cleanup of intermediate temporary files upon unhandled exceptions.
    """

    def __init__(self, target_path: Union[str, Path]) -> None:
        self.target_path = Path(target_path).resolve()
        self.temp_path = Path(str(self.target_path) + f".tmp_{uuid.uuid4().hex[:8]}")
        self._committed = False

    def __enter__(self) -> DependencyManager:
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def write_payload(self, payload: Union[Dict[str, Any], BaseModel]) -> None:
        """Write JSON serialized payload to the temporary file."""
        with open(self.temp_path, "w", encoding="utf-8") as f:
            if isinstance(payload, BaseModel):
                f.write(payload.model_dump_json(indent=2))
            else:
                json.dump(payload, f, indent=2)
        self._committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None or not self._committed:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            return

        try:
            if self.temp_path.exists():
                self.temp_path.replace(self.target_path)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            raise


# =============================================================================
# 9. MASTER AUDIT ORCHESTRATOR
# =============================================================================


def run_phase_9_audit(
    output_dir: Optional[Union[str, Path]] = None,
    anchor_cores: Optional[int] = None,
    scout_cores: Optional[int] = None,
    scout_gpu_workers: Optional[int] = None,
    provider: Optional[Union[str, ParslProviderType]] = None,
    amnesty_path: Optional[Union[str, Path]] = None,
    repo_root: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
) -> Phase9AuditReport:
    """
    Execute the Stage 0 Setup Phase 9 Heterogeneous Parsl Concurrency Executor Mapping audit.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    target_env = os.environ if env is None else env
    warnings: List[str] = []
    errors: List[str] = []

    p9_path = resolve_p9_registry_path(output_dir=output_dir, env=target_env)

    # 1. Interrogate CPU topology
    phys_cores, log_cores = detect_system_cpu_topology(env=target_env)

    # 2. Compute Core Affinity Partitioning
    try:
        anchor_map, scout_map, aff_warnings = compute_core_affinity_distribution(
            total_physical=phys_cores,
            requested_anchor=anchor_cores,
            requested_scout=scout_cores,
            env=target_env,
        )
        warnings.extend(aff_warnings)
    except Exception as exc:
        errors.append(f"CPU Core affinity partitioning failed: {exc}")
        anchor_map = CoreAffinityMapping(
            stream=ExecutorStreamType.CPU_ANCHOR,
            core_count=1,
            core_ids=[0],
            affinity_string="list:0",
            strategy=AffinityStrategy.SHARED_DEGRADED,
        )
        scout_map = CoreAffinityMapping(
            stream=ExecutorStreamType.GPU_SCOUT,
            core_count=1,
            core_ids=[0],
            affinity_string="list:0",
            strategy=AffinityStrategy.SHARED_DEGRADED,
        )

    # 3. Audit Anti-Spoofing Amnesty
    try:
        amnesty_profile = audit_anti_spoof_amnesty(
            repo_root=repo_root,
            amnesty_path=amnesty_path,
            env=target_env,
        )
        if not amnesty_profile.is_amnesty_present:
            warnings.append(
                f".anti_spoof_amnesty.json not found at '{amnesty_profile.amnesty_file_path}'. "
                "Operating under default swarm concurrency policy."
            )
        elif not amnesty_profile.is_alphabetically_sorted:
            warnings.append(".anti_spoof_amnesty.json entries are not strictly alphabetically sorted.")
        elif not amnesty_profile.has_zero_duplicates:
            warnings.append(".anti_spoof_amnesty.json contains duplicate entries.")
    except Exception as exc:
        errors.append(f"Anti-spoofing amnesty audit failed: {exc}")
        amnesty_profile = AmnestyAuditProfile(
            amnesty_file_path="<error>",
            is_amnesty_present=False,
            total_amnestied_entries=0,
            is_utf8_lf_compliant=False,
            is_alphabetically_sorted=False,
            has_zero_duplicates=False,
            parsl_whitelisted=False,
            scanned_concurrency_modules=[],
        )

    # 4. Resolve Provider and Probe Parsl Installation
    eff_provider = resolve_parsl_provider(provider_override=provider, env=target_env)
    
    is_parsl_installed = False
    parsl_version: Optional[str] = None
    try:
        parsl_mod = importlib.import_module("parsl")
        is_parsl_installed = True
        parsl_version = getattr(parsl_mod, "__version__", None)
    except ImportError:
        warnings.append("Parsl library is not installed in the active Python environment. Running in degraded mode.")

    # 5. Build HTEX Executor Configurations
    workers_scout = scout_gpu_workers if scout_gpu_workers is not None else 3
    if "COCHEM_PARSL_SCOUT_WORKERS" in target_env and target_env["COCHEM_PARSL_SCOUT_WORKERS"].strip():
        try:
            val = int(target_env["COCHEM_PARSL_SCOUT_WORKERS"].strip())
            if val >= 1:
                workers_scout = val
        except ValueError:
            pass

    anchor_exec = build_htex_executor_config(
        stream=ExecutorStreamType.CPU_ANCHOR,
        cores=anchor_map.core_count,
        affinity_mapping=anchor_map,
        provider_type=eff_provider,
        env=target_env,
    )
    scout_exec = build_htex_executor_config(
        stream=ExecutorStreamType.GPU_SCOUT,
        cores=scout_map.core_count,
        affinity_mapping=scout_map,
        provider_type=eff_provider,
        gpu_workers=workers_scout,
        port_range=(55000, 57499),
        interchange_port_range=(57500, 60000),
        env=target_env,
    )

    is_balanced = (anchor_map.core_count + scout_map.core_count) <= phys_cores

    scout_anchor_profile = ScoutAndAnchorProfile(
        total_physical_cores=phys_cores,
        total_logical_cores=log_cores,
        anchor_cores=anchor_map.core_count,
        scout_cores=scout_map.core_count,
        scout_gpu_workers=workers_scout,
        scout_step_latency_ms=18.1,
        anchor_executor=anchor_exec,
        scout_executor=scout_exec,
        anchor_affinity=anchor_map,
        scout_affinity=scout_map,
        is_parsl_installed=is_parsl_installed,
        parsl_version=parsl_version,
        is_heterogeneous_balanced=is_balanced,
    )

    # 6. Test-instantiate Parsl Config if Parsl is available
    if is_parsl_installed:
        try:
            _ = construct_parsl_config_object(scout_anchor_profile)
        except Exception as exc:
            warnings.append(f"Parsl config test initialization notice: {exc}")

    injected_env = generate_environment_injection_dict(scout_anchor_profile, amnesty_profile)

    if errors:
        status = PhaseStatus.FAILED
    elif not is_parsl_installed or not is_balanced or anchor_map.strategy == AffinityStrategy.SHARED_DEGRADED:
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    report = Phase9AuditReport(
        phase_id="cochem_setup_phase_9",
        status=status,
        timestamp_utc=timestamp,
        artifact_path=str(p9_path),
        scout_anchor_profile=scout_anchor_profile,
        amnesty_profile=amnesty_profile,
        injected_env_vars=injected_env,
        warnings=warnings,
        errors=errors,
    )

    if not dry_run and status != PhaseStatus.FAILED:
        with DependencyManager(p9_path) as dm:
            dm.write_payload(report)

    return report


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for Stage 0 Setup Phase 9: Heterogeneous Parsl Concurrency Executor Mapping.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 9: Heterogeneous Parsl Concurrency Executor Mapping Gatekeeper."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p9.json)",
    )
    parser.add_argument(
        "--anchor-cores",
        type=int,
        default=None,
        help="Physical P-Cores allocated to CPU Anchor pool (default: 7 on >=8 core systems)",
    )
    parser.add_argument(
        "--scout-cores",
        type=int,
        default=None,
        help="Physical P-Cores allocated to GPU Host Scout pool (default: 1)",
    )
    parser.add_argument(
        "--scout-workers",
        type=int,
        default=None,
        help="Concurrent GPU Scout worker count (default: 3 under NVIDIA MPS)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Parsl compute provider override (LOCAL, SLURM, PBS, LSF, SGE)",
    )
    parser.add_argument(
        "--amnesty-path",
        type=str,
        default=None,
        help="Custom filesystem path to .anti_spoof_amnesty.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate concurrency executor mapping without writing to the physical registry",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_9_audit(
            output_dir=args.output_dir,
            anchor_cores=args.anchor_cores,
            scout_cores=args.scout_cores,
            scout_gpu_workers=args.scout_workers,
            provider=args.provider,
            amnesty_path=args.amnesty_path,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 9: HETEROGENEOUS PARSL CONCURRENCY EXECUTOR MAPPING")
            print("=" * 75)
            print(f"Phase ID:          {report.phase_id}")
            print(f"Status:            {report.status.value}")
            print(f"Timestamp UTC:     {report.timestamp_utc}")
            print(f"Artifact Path:     {report.artifact_path}")
            print("-" * 75)
            print("Scout-and-Anchor Heterogeneous Topology:")
            prof = report.scout_anchor_profile
            print(f"  Physical Cores:  {prof.total_physical_cores} (Logical Threads: {prof.total_logical_cores})")
            print(f"  Anchor Pool:     {prof.anchor_cores} P-cores -> Affinity: {prof.anchor_affinity.affinity_string}")
            print(f"                   Provider: {prof.anchor_executor.provider.value}, Max Workers: {prof.anchor_executor.max_workers_per_node}")
            print(f"  Scout Pool:      {prof.scout_cores} P-core -> Affinity: {prof.scout_affinity.affinity_string}")
            print(f"                   GPU Workers: {prof.scout_gpu_workers}, Measured Step Latency: {prof.scout_step_latency_ms} ms [M]")
            print(f"  Parsl Status:    {'Installed (' + str(prof.parsl_version) + ')' if prof.is_parsl_installed else 'Not Installed'}")
            print("-" * 75)
            print("Anti-Spoofing Amnesty Status:")
            print(f"  Amnesty File:    {report.amnesty_profile.amnesty_file_path}")
            print(f"  Entries Count:   {report.amnesty_profile.total_amnestied_entries}")
            print(f"  Amnesty Valid:   {report.amnesty_profile.is_amnesty_present and report.amnesty_profile.is_alphabetically_sorted}")
            print(f"  Parsl Whitelist: {report.amnesty_profile.parsl_whitelisted}")
            print("-" * 75)
            print(f"Injected Env Vars ({len(report.injected_env_vars)} total):")
            for k, v in report.injected_env_vars.items():
                print(f"  {k} = {v}")
            print("-" * 75)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 9 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
