Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc5_06_phase11_memory_router_prompt.md.
Original prompt:
# Context
You are tasked with writing the setup orchestration script `cochem_setup_phase_11.py` for CoChem-BASE.

# Goal
Create `cochem_setup_phase_11.py` to perform Phase 11: Memory Router & Adaptive Tiering.

# Requirements
- Dynamically establish engine RAM constraints based on the Phase 2 audit findings.
- Prioritize `cgroupv2` (specifically `/sys/fs/cgroup/memory.max`) before falling back to `psutil` to prevent hypervisor spoofing and guarantee reliable scaling.
- Implement the constraint algorithm for OpenMPI and DFT maximum safe memory allocations: `%maxcore = int(((Total_RAM_GB * 1024) * 0.80) / CPU_Physical_Cores)`.
- This ensures exactly 20% of system RAM is reserved strictly for the OS and Jupyter UI to prevent systemic freezing.
- Save the locked constraints in an intermediate state file.

# Constraints
- Target filepath: `D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_11.py`
- DO NOT use any mocks, stubs, or placeholder values in your code. Write real implementation logic.
- Ensure strict adherence to the Tripartite Workspace Air-Gap and Method Matrix rules.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_11.py ---
"""
CoChem Setup Phase 11: Memory Router & Adaptive Tiering (The OOM Shield Gatekeeper).
Production-grade, zero-mock gatekeeping engine for bounded host and container memory discovery,
Linux cgroups v1 & v2 memory constraint parsing (/sys/fs/cgroup/memory.max & memory.limit_in_bytes),
HPC job memory limit detection (Slurm, PBS, LSF), flat OS/Jupyter safety buffer allocation (4-8 GB),
active calculation core division scaling (%maxcore), NUMA multi-tier RAM classification, multi-engine
target directive generation (ORCA, PySCF, xTB, Gaussian, CFOUR, MACE-Torch, OpenMPI), environment
variable injection generation, and transactional atomic persistence into the Golden Registry (p11.json).

SRS Document 2 Part 2 (Section 3.11), SRS Document 5 (Section 4.2), Method Matrix v4,
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Threshold above which cgroup v1 values are treated as unlimited (e.g. 0x7FFFFFFFFFFFF000)
CGROUP_V1_UNLIMITED_THRESHOLD: int = 2**62
# Fallback flat reserve constants in Megabytes (MB)
DEFAULT_MIN_OS_RESERVE_MB: int = 4096  # 4 GB minimum reserve for modern OS / Jupyter / agent council
DEFAULT_MAX_OS_RESERVE_MB: int = 8192  # 8 GB maximum reserve on massive nodes


# =============================================================================
# 1. CUSTOM EXCEPTION HIERARCHY
# =============================================================================


class Phase11AuditError(RuntimeError):
    """Raised when critical Phase 11 memory routing or OOM Shield gatekeeper audit fails fatally."""


class MemoryDiscoveryError(Phase11AuditError):
    """Raised when host physical or virtual memory topology cannot be safely discovered."""


class CGroupLimitError(Phase11AuditError):
    """Raised when Linux cgroups v1/v2 memory bounds or constraints encounter fatal errors."""


class EngineBudgetError(Phase11AuditError):
    """Raised when calculation memory budget synthesis fails or encounters unphysical bounds."""


class NUMADiscoveryError(Phase11AuditError):
    """Raised when NUMA node hardware topology parsing encounters an irrecoverable error."""


# =============================================================================
# 2. ENUMERATIONS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class CGroupVersion(str, Enum):
    """Detected Linux control groups (cgroups) architecture version."""

    V1 = "V1"
    V2 = "V2"
    HYBRID = "HYBRID"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MemoryTier(str, Enum):
    """Tier classification for memory routing and adaptive offloading."""

    TIER_1_LOCAL_NUMA = "TIER_1_LOCAL_NUMA"
    TIER_2_REMOTE_NUMA = "TIER_2_REMOTE_NUMA"
    TIER_3_SWAP_STORAGE = "TIER_3_SWAP_STORAGE"


class EngineTarget(str, Enum):
    """Supported computational chemistry and machine learning solver engines."""

    ORCA = "ORCA"
    PYSCF = "PYSCF"
    XTB = "XTB"
    GAUSSIAN = "GAUSSIAN"
    CFOUR = "CFOUR"
    MACE_TORCH = "MACE_TORCH"
    OPENMPI = "OPENMPI"
    GENERIC = "GENERIC"


class NUMABalanceStatus(str, Enum):
    """Memory balance classification across multiple physical NUMA nodes."""

    BALANCED = "BALANCED"
    ASYMMETRIC = "ASYMMETRIC"
    UNIFIED_UMA = "UNIFIED_UMA"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# 3. PYDANTIC V2 DATA MODELS
# =============================================================================


class CGroupMemoryProfile(BaseModel):
    """Linux control group (cgroups v1/v2) memory hierarchy constraint record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    cgroup_version: CGroupVersion = Field(..., description="Detected cgroups architecture")
    memory_limit_bytes: Optional[int] = Field(
        default=None, ge=0, description="Hard memory limit enforced by cgroups (bytes)"
    )
    memory_max_bytes: Optional[int] = Field(
        default=None, ge=0, description="cgroups v2 memory.max limit in bytes"
    )
    memory_high_bytes: Optional[int] = Field(
        default=None, ge=0, description="cgroups v2 memory.high throttling boundary in bytes"
    )
    memory_current_bytes: Optional[int] = Field(
        default=None, ge=0, description="cgroups current active memory usage in bytes"
    )
    swap_limit_bytes: Optional[int] = Field(
        default=None, ge=0, description="cgroups memory+swap limit in bytes"
    )
    is_cgroup_constrained: bool = Field(
        default=False, description="Whether cgroup limits actively constrain memory below host RAM"
    )
    cgroup_path: Optional[str] = Field(
        default=None, description="Filesystem path to the primary cgroup constraint file"
    )


class HostMemoryProfile(BaseModel):
    """Host physical and virtual memory topology inspection record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_ram_bytes: int = Field(..., ge=0, description="Total physical RAM in bytes")
    available_ram_bytes: int = Field(..., ge=0, description="Currently available physical RAM in bytes")
    free_ram_bytes: int = Field(..., ge=0, description="Completely unallocated physical RAM in bytes")
    swap_total_bytes: int = Field(default=0, ge=0, description="Total swap space in bytes")
    swap_free_bytes: int = Field(default=0, ge=0, description="Free swap space in bytes")
    effective_system_ram_bytes: int = Field(
        ..., ge=0, description="Effective system RAM accounting for physical limits"
    )
    hpc_scheduler_detected: Optional[str] = Field(
        default=None, description="HPC workload scheduler detected (Slurm, PBS, LSF, etc.)"
    )
    hpc_job_memory_limit_bytes: Optional[int] = Field(
        default=None, ge=0, description="HPC scheduler job memory ceiling in bytes"
    )
    bounded_total_ram_bytes: int = Field(
        ..., ge=0, description="Strictly bounded total memory accounting for cgroups and HPC limits"
    )
    bounded_total_ram_mb: float = Field(
        ..., ge=0.0, description="Bounded total memory in Megabytes [MB]"
    )
    bounded_total_ram_gb: float = Field(
        ..., ge=0.0, description="Bounded total memory in Gigabytes [GB]"
    )


class NumaNodeProfile(BaseModel):
    """Physical NUMA node memory and CPU affinity mapping."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    node_id: int = Field(..., ge=0, description="NUMA node physical identifier index (e.g. 0, 1)")
    total_ram_mb: float = Field(..., ge=0.0, description="Total physical RAM assigned to this NUMA node [MB]")
    free_ram_mb: float = Field(..., ge=0.0, description="Free physical RAM on this NUMA node [MB]")
    cpu_core_ids: List[int] = Field(
        default_factory=list, description="List of logical/physical CPU core IDs local to this NUMA node"
    )
    is_local: bool = Field(default=True, description="Whether this node is local to active process affinity")


class MultiTierMemoryProfile(BaseModel):
    """Multi-tier NUMA memory topology and hierarchy profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    numa_nodes_count: int = Field(default=1, ge=1, description="Number of detected NUMA nodes")
    numa_nodes: List[NumaNodeProfile] = Field(
        default_factory=list, description="List of individual NUMA node profiles"
    )
    numa_balance_status: NUMABalanceStatus = Field(
        default=NUMABalanceStatus.UNIFIED_UMA, description="Memory symmetry classification across nodes"
    )
    tier_1_local_ram_mb: float = Field(
        ..., ge=0.0, description="Tier 1 Fast Local NUMA Node RAM in Megabytes [MB]"
    )
    tier_2_remote_ram_mb: float = Field(
        default=0.0, ge=0.0, description="Tier 2 Cross-Socket Remote NUMA RAM in Megabytes [MB]"
    )
    tier_3_swap_mb: float = Field(
        default=0.0, ge=0.0, description="Tier 3 NVMe/Disk Swap Space in Megabytes [MB]"
    )
    is_numa_aware: bool = Field(
        default=False, description="Whether host possesses multiple distinct NUMA memory domains"
    )


class EngineMemoryBudget(BaseModel):
    """Formatted memory directive configuration for a specific quantum or ML engine."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    engine: EngineTarget = Field(..., description="Target computational engine identifier")
    primary_directive_name: str = Field(
        ..., description="Engine-native configuration directive (e.g. %maxcore, max_memory)"
    )
    directive_value_formatted: str = Field(
        ..., description="Fully formatted input block directive (e.g. '%maxcore 7168')"
    )
    allocated_per_core_mb: int = Field(
        ..., ge=0, description="Calculated memory allocation per active calculation core [MB]"
    )
    allocated_total_job_mb: int = Field(
        ..., ge=0, description="Calculated total memory allocation across all active cores [MB]"
    )
    env_var_name: str = Field(
        ..., description="Standardized environment variable name for engine memory injection"
    )
    env_var_value: str = Field(
        ..., description="Environment variable string value for runtime export"
    )
    notes: str = Field(
        default="", description="Technical rationale, safety buffers, and constraints explanation"
    )


class OOMShieldScalingProfile(BaseModel):
    """
    The OOM Shield Dynamic Memory Scaling Profile.
    Applies flat 4-8 GB OS/Jupyter safety buffer reservation and partitions available memory
    specifically across active calculation cores rather than all physical cores.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_physical_cores: int = Field(
        ..., ge=1, description="Total physical CPU cores available on the host"
    )
    active_job_cores: int = Field(
        ..., ge=1, description="Active job calculation cores requested for this run"
    )
    bounded_total_ram_mb: float = Field(
        ..., ge=0.0, description="Total bounded system RAM available to the job [MB]"
    )
    os_jupyter_reserve_mb: int = Field(
        ..., ge=0, description="Flat memory buffer strictly reserved for OS/Jupyter/UI [MB]"
    )
    reserve_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Fraction of bounded memory reserved for OS safety"
    )
    allocatable_ram_mb: int = Field(
        ..., ge=0, description="Net allocatable memory available for quantum/ML calculation [MB]"
    )
    allocatable_ram_gb: float = Field(
        ..., ge=0.0, description="Net allocatable memory available for calculation [GB]"
    )
    baseline_80pct_maxcore_mb: int = Field(
        ..., ge=0, description="Baseline %maxcore calculated dividing by total physical cores [MB]"
    )
    active_core_maxcore_mb: int = Field(
        ..., ge=0, description="Dynamic %maxcore calculated dividing across active calculation cores [MB]"
    )
    memory_gain_vs_baseline_pct: float = Field(
        ..., description="Percentage memory gain achieved by dynamic active core routing vs baseline"
    )
    shield_active: bool = Field(
        default=True, description="Whether the OOM Shield active core routing guardrail is engaged"
    )


class Phase2AuditFindings(BaseModel):
    """Audited hardware baseline findings loaded from Phase 2 (p2.json)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    loaded_from: str = Field(..., description="Filesystem path of the loaded p2.json artifact")
    status: str = Field(..., description="Phase 2 execution status (e.g. PASSED, DEGRADED)")
    total_physical_ram_bytes: int = Field(..., ge=0, description="Total physical RAM audited in Phase 2")
    effective_memory_bytes: int = Field(..., ge=0, description="Effective memory accounting for constraints")
    physical_cores: int = Field(..., ge=1, description="Physical CPU cores audited in Phase 2")
    logical_cores: int = Field(..., ge=1, description="Logical CPU cores audited in Phase 2")
    is_cgroup_constrained: bool = Field(default=False, description="Whether cgroups constraint was detected in Phase 2")
    gpu_available: bool = Field(default=False, description="Whether compute GPU was detected in Phase 2")


class Phase11AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 11."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(default="cochem_setup_phase_11", description="Setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 11")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    artifact_path: str = Field(
        ..., description="Absolute path to generated p11.json Golden Registry artifact"
    )
    phase_2_findings: Optional[Phase2AuditFindings] = Field(
        default=None, description="Audited baseline findings loaded from Phase 2 (p2.json)"
    )
    host_memory: HostMemoryProfile = Field(
        ..., description="Host and container bounded physical RAM profile"
    )
    cgroup_profile: CGroupMemoryProfile = Field(
        ..., description="Linux cgroups v1/v2 memory bounds profile"
    )
    numa_profile: MultiTierMemoryProfile = Field(
        ..., description="Multi-tier NUMA memory topology profile"
    )
    oom_shield: OOMShieldScalingProfile = Field(
        ..., description="The OOM Shield dynamic active-core scaling profile"
    )
    engine_budgets: Dict[str, EngineMemoryBudget] = Field(
        default_factory=dict, description="Multi-engine configuration directives and memory budgets"
    )
    injected_env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variable injection key-value mappings"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal resource warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal execution errors")


# =============================================================================
# 4. TRANSACTIONAL DEPENDENCY MANAGER
# =============================================================================


class DependencyManager:
    """
    Idempotent transactional context manager for managing temporary filesystem
    artifacts and executing atomic JSON state persistence.
    Rolls back staged temporary files/directories if an exception occurs during execution.
    """

    def __init__(self) -> None:
        self._tracked_temp_files: List[Path] = []
        self._tracked_temp_dirs: List[Path] = []

    def __enter__(self) -> DependencyManager:
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        if exc_type is not None:
            self.rollback()

    def track_temp_file(self, path: Union[str, Path]) -> Path:
        """Register a temporary file to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_files:
            self._tracked_temp_files.append(p)
        return p

    def track_temp_dir(self, path: Union[str, Path]) -> Path:
        """Register a temporary directory to be rolled back on failure."""
        p = Path(path).resolve()
        if p not in self._tracked_temp_dirs:
            self._tracked_temp_dirs.append(p)
        return p

    def create_temp_file(
        self,
        suffix: str = ".tmp",
        prefix: str = "cochem_p11_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create a tracked temporary file."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        fd, temp_path_str = tempfile.mkstemp(
            suffix=suffix,
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        os.close(fd)
        temp_path = Path(temp_path_str).resolve()
        self.track_temp_file(temp_path)
        return temp_path

    def rollback(self) -> None:
        """Execute safe rollback by unlinking tracked temporary files and directories."""
        for temp_file in self._tracked_temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in self._tracked_temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: BaseModel,
        indent: int = 2,
    ) -> Path:
        """
        Atomically write Pydantic model JSON payload to target destination using
        ephemeral temporary file and atomic replace.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        temp_file = self.create_temp_file(
            suffix=".tmp",
            prefix=f"{target.name}_",
            directory=target.parent,
        )

        json_text = data.model_dump_json(indent=indent)
        temp_file.write_text(json_text, encoding="utf-8")

        # Atomic replacement
        shutil.move(str(temp_file), str(target))
        if temp_file in self._tracked_temp_files:
            self._tracked_temp_files.remove(temp_file)

        # Apply standard directory permissions
        try:
            os.chmod(target, 0o644)
        except OSError:
            pass

        return target


# =============================================================================
# 5. DISCOVERY & PARSING FUNCTIONS (ZERO-MOCK)
# =============================================================================


def find_repository_root(start_path: Optional[Union[str, Path]] = None) -> Path:
    """Find repository root by walking upward looking for .git or pyproject.toml."""
    current = Path(start_path or Path.cwd()).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists() or (parent / "pytest.ini").exists():
            return parent
    return current


def resolve_p11_registry_path(
    output_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Resolve the absolute target path for the Phase 11 Golden Registry artifact (p11.json).
    Priority: explicit output_dir -> COCHEM_REGISTRY_DIR -> COCHEM_ARTIFACT_DIR -> fallback.
    """
    target_env = os.environ if env is None else env

    if output_dir is not None and str(output_dir).strip():
        out_p = Path(output_dir).resolve()
        if out_p.name.endswith(".json"):
            out_p.parent.mkdir(parents=True, exist_ok=True)
            return out_p
        out_p.mkdir(parents=True, exist_ok=True)
        return out_p / "p11.json"

    if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
        dest = (Path(target_env["COCHEM_REGISTRY_DIR"]) / "p11.json").resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    if "COCHEM_ARTIFACT_DIR" in target_env and target_env["COCHEM_ARTIFACT_DIR"].strip():
        dest = (Path(target_env["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p11.json").resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    repo_root = find_repository_root()
    dest = (repo_root / "artifacts" / "registry" / "p11.json").resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def get_absolute_physical_ram() -> int:
    """
    Define absolute physical RAM bypassing virtualized/swap memory traps.
    Utilizes POSIX sysconf SC_PHYS_PAGES * SC_PAGE_SIZE when available,
    falling back to psutil.virtual_memory().total.
    """
    if hasattr(os, "sysconf") and hasattr(os, "sysconf_names"):
        try:
            if "SC_PHYS_PAGES" in os.sysconf_names and "SC_PAGE_SIZE" in os.sysconf_names:
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                if pages > 0 and page_size > 0:
                    return int(pages * page_size)
        except (ValueError, OSError, AttributeError):
            pass

    vmem = psutil.virtual_memory()
    return int(vmem.total)


def load_phase_2_audit_findings(
    p2_path: Optional[Union[str, Path]] = None,
    registry_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Optional[Phase2AuditFindings]:
    """
    Dynamically discover and load Phase 2 Hardware & Resource Gatekeeper findings from p2.json.
    Searches explicit paths, environment variable locations, and standard registry candidate directories.
    """
    target_env = os.environ if env is None else env
    candidates: List[Path] = []

    if p2_path is not None and str(p2_path).strip():
        candidates.append(Path(p2_path).resolve())
    else:
        if registry_dir is not None and str(registry_dir).strip():
            r_dir = Path(registry_dir).resolve()
            if r_dir.name.endswith(".json"):
                candidates.append(r_dir)
            else:
                candidates.append(r_dir / "p2.json")

        if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
            candidates.append(Path(target_env["COCHEM_REGISTRY_DIR"]).resolve() / "p2.json")

        if "COCHEM_ARTIFACT_DIR" in target_env and target_env["COCHEM_ARTIFACT_DIR"].strip():
            candidates.append(Path(target_env["COCHEM_ARTIFACT_DIR"]).resolve() / "Registry" / "p2.json")

        repo_root = find_repository_root()
        candidates.append(repo_root / "artifacts" / "registry" / "p2.json")
        candidates.append(repo_root / "Registry" / "p2.json")
        candidates.append(Path.cwd() / "Registry" / "p2.json")
        candidates.append(Path.cwd() / ".agent_artifacts" / "Registry" / "p2.json")
        candidates.append(Path.home() / "CoChem_Artifacts" / "Registry" / "p2.json")

    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "memory" in data and "cpu" in data:
                    mem_data = data.get("memory", {})
                    cpu_data = data.get("cpu", {})
                    gpu_data = data.get("gpu", {})
                    status_val = str(data.get("status", "PASSED"))

                    tot_ram = int(mem_data.get("total_bytes") or psutil.virtual_memory().total)
                    eff_ram = int(mem_data.get("effective_memory_bytes") or tot_ram)
                    phys_cores = int(cpu_data.get("physical_cores") or psutil.cpu_count(logical=False) or 1)
                    log_cores = int(cpu_data.get("logical_cores") or psutil.cpu_count(logical=True) or 1)
                    is_cg = bool(mem_data.get("is_cgroup_constrained", False))
                    gpu_avail = bool(gpu_data.get("available", False))

                    return Phase2AuditFindings(
                        loaded_from=str(candidate.resolve()),
                        status=status_val,
                        total_physical_ram_bytes=tot_ram,
                        effective_memory_bytes=eff_ram,
                        physical_cores=phys_cores,
                        logical_cores=log_cores,
                        is_cgroup_constrained=is_cg,
                        gpu_available=gpu_avail,
                    )
            except Exception:
                continue

    return None


def parse_proc_meminfo(proc_root: Optional[Path] = None) -> Dict[str, int]:
    """
    Parse Linux /proc/meminfo into a key-value dictionary of memory statistics in bytes.
    Returns empty dict on non-Linux or when file does not exist.
    """
    base_dir = proc_root or Path("/proc")
    meminfo_path = base_dir / "meminfo"

    if not meminfo_path.exists():
        return {}

    parsed: Dict[str, int] = {}
    try:
        lines = meminfo_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, rest = line.split(":", 1)
            parts = rest.strip().split()
            if not parts:
                continue
            val_str = parts[0]
            unit = parts[1].lower() if len(parts) > 1 else ""

            try:
                val = int(val_str)
                if unit == "kb":
                    val *= 1024
                elif unit == "mb":
                    val *= 1024 * 1024
                elif unit == "gb":
                    val *= 1024 * 1024 * 1024
                parsed[key.strip()] = val
            except ValueError:
                pass
    except (OSError, UnicodeDecodeError):
        pass

    return parsed


def parse_cgroup_memory_bounds(cgroup_root: Optional[Path] = None) -> CGroupMemoryProfile:
    """
    Interrogate Linux control groups (cgroups v1 and v2) for hard memory limits,
    high watermark throttling bounds, and current usage.
    """
    if platform.system() != "Linux" and cgroup_root is None:
        return CGroupMemoryProfile(
            cgroup_version=CGroupVersion.NOT_APPLICABLE,
            memory_limit_bytes=None,
            memory_max_bytes=None,
            memory_high_bytes=None,
            memory_current_bytes=None,
            swap_limit_bytes=None,
            is_cgroup_constrained=False,
            cgroup_path=None,
        )

    root = cgroup_root or Path("/sys/fs/cgroup")
    if not root.exists():
        return CGroupMemoryProfile(
            cgroup_version=CGroupVersion.NOT_AVAILABLE,
            memory_limit_bytes=None,
            memory_max_bytes=None,
            memory_high_bytes=None,
            memory_current_bytes=None,
            swap_limit_bytes=None,
            is_cgroup_constrained=False,
            cgroup_path=None,
        )

    # 1. Probe Cgroups v2: memory.max, memory.high, memory.current
    v2_max_file = root / "memory.max"
    v2_high_file = root / "memory.high"
    v2_current_file = root / "memory.current"

    if v2_max_file.exists():
        max_bytes: Optional[int] = None
        high_bytes: Optional[int] = None
        current_bytes: Optional[int] = None
        is_constrained = False

        try:
            content = v2_max_file.read_text(encoding="utf-8").strip()
            if content and content != "max":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    max_bytes = val
                    is_constrained = True
        except (ValueError, OSError):
            pass

        if v2_high_file.exists():
            try:
                high_content = v2_high_file.read_text(encoding="utf-8").strip()
                if high_content and high_content != "max":
                    val = int(high_content)
                    if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                        high_bytes = val
            except (ValueError, OSError):
                pass

        if v2_current_file.exists():
            try:
                cur_content = v2_current_file.read_text(encoding="utf-8").strip()
                if cur_content:
                    current_bytes = int(cur_content)
            except (ValueError, OSError):
                pass

        return CGroupMemoryProfile(
            cgroup_version=CGroupVersion.V2,
            memory_limit_bytes=max_bytes,
            memory_max_bytes=max_bytes,
            memory_high_bytes=high_bytes,
            memory_current_bytes=current_bytes,
            swap_limit_bytes=None,
            is_cgroup_constrained=is_constrained,
            cgroup_path=str(v2_max_file),
        )

    # 2. Probe Cgroups v1: memory/memory.limit_in_bytes, memory/memory.memsw.limit_in_bytes
    v1_mem_dir = root / "memory" if (root / "memory").is_dir() else root
    v1_limit_file = v1_mem_dir / "memory.limit_in_bytes"
    v1_memsw_file = v1_mem_dir / "memory.memsw.limit_in_bytes"
    v1_usage_file = v1_mem_dir / "memory.usage_in_bytes"

    if v1_limit_file.exists():
        limit_bytes: Optional[int] = None
        swap_bytes: Optional[int] = None
        usage_bytes: Optional[int] = None
        is_constrained = False

        try:
            content = v1_limit_file.read_text(encoding="utf-8").strip()
            if content and content != "-1":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    limit_bytes = val
                    is_constrained = True
        except (ValueError, OSError):
            pass

        if v1_memsw_file.exists():
            try:
                sw_content = v1_memsw_file.read_text(encoding="utf-8").strip()
                if sw_content and sw_content != "-1":
                    val = int(sw_content)
                    if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                        swap_bytes = val
            except (ValueError, OSError):
                pass

        if v1_usage_file.exists():
            try:
                u_content = v1_usage_file.read_text(encoding="utf-8").strip()
                if u_content:
                    usage_bytes = int(u_content)
            except (ValueError, OSError):
                pass

        return CGroupMemoryProfile(
            cgroup_version=CGroupVersion.V1,
            memory_limit_bytes=limit_bytes,
            memory_max_bytes=limit_bytes,
            memory_high_bytes=None,
            memory_current_bytes=usage_bytes,
            swap_limit_bytes=swap_bytes,
            is_cgroup_constrained=is_constrained,
            cgroup_path=str(v1_limit_file),
        )

    return CGroupMemoryProfile(
        cgroup_version=CGroupVersion.NOT_AVAILABLE,
        memory_limit_bytes=None,
        memory_max_bytes=None,
        memory_high_bytes=None,
        memory_current_bytes=None,
        swap_limit_bytes=None,
        is_cgroup_constrained=False,
        cgroup_path=None,
    )


def _parse_memory_string_to_bytes(mem_str: str) -> Optional[int]:
    """Helper to parse memory strings like '64GB', '32768MB', '1048576KB', '65536' into bytes."""
    mem_str = mem_str.strip().upper()
    if not mem_str:
        return None

    # Check for unit suffix
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$", mem_str)
    if not match:
        return None

    num = float(match.group(1))
    unit = match.group(2)

    if unit in ("GB", "G"):
        return int(num * 1024 * 1024 * 1024)
    elif unit in ("MB", "M"):
        return int(num * 1024 * 1024)
    elif unit in ("KB", "K"):
        return int(num * 1024)
    elif unit in ("TB", "T"):
        return int(num * 1024 * 1024 * 1024 * 1024)
    else:
        # Default is Megabytes in HPC schedulers like Slurm (e.g. SLURM_MEM_PER_NODE=65536)
        if num > 1048576:  # If very large, assume bytes
            return int(num)
        return int(num * 1024 * 1024)


def detect_hpc_memory_limits() -> Tuple[Optional[str], Optional[int]]:
    """
    Detect HPC scheduler job memory limits from environment variables (Slurm, PBS, LSF, SGE).
    Returns (scheduler_name, limit_in_bytes) or (None, None).
    """
    # 1. Slurm
    if "SLURM_JOB_ID" in os.environ or "SLURM_JOBID" in os.environ:
        if "SLURM_MEM_PER_NODE" in os.environ:
            val = _parse_memory_string_to_bytes(os.environ["SLURM_MEM_PER_NODE"])
            if val:
                return "Slurm", val
        if "SLURM_MEM_PER_CPU" in os.environ:
            val_per_cpu = _parse_memory_string_to_bytes(os.environ["SLURM_MEM_PER_CPU"])
            cpus = int(os.environ.get("SLURM_CPUS_ON_NODE", os.environ.get("SLURM_JOB_CPUS_PER_NODE", "1")))
            if val_per_cpu:
                return "Slurm", val_per_cpu * cpus
        return "Slurm", None

    # 2. PBS / Torque
    if "PBS_JOBID" in os.environ or "PBS_JOBNAME" in os.environ:
        if "PBS_MEM" in os.environ:
            val = _parse_memory_string_to_bytes(os.environ["PBS_MEM"])
            if val:
                return "PBS", val
        if "PBS_RESOURCE_LIST" in os.environ:
            # e.g. "mem=64gb,ncpus=16"
            res = os.environ["PBS_RESOURCE_LIST"]
            for token in res.split(","):
                if token.startswith("mem="):
                    val = _parse_memory_string_to_bytes(token.split("=", 1)[1])
                    if val:
                        return "PBS", val
        return "PBS", None

    # 3. LSF
    if "LSB_JOBID" in os.environ:
        if "LSB_JOB_MEMLIMIT" in os.environ:
            val = _parse_memory_string_to_bytes(os.environ["LSB_JOB_MEMLIMIT"])
            if val:
                return "LSF", val
        return "LSF", None

    return None, None


def audit_host_memory(
    cgroup_root: Optional[Path] = None,
    proc_root: Optional[Path] = None,
    phase_2_findings: Optional[Phase2AuditFindings] = None,
) -> Tuple[HostMemoryProfile, CGroupMemoryProfile]:
    """
    Audit host physical memory, /proc/meminfo statistics, container cgroup bounds,
    and HPC workload constraints to compute strictly bounded total memory.
    Prioritizes cgroupv2 (/sys/fs/cgroup/memory.max) before falling back to psutil.
    """
    # 1. Probe cgroups FIRST to prevent hypervisor spoofing
    cg_profile = parse_cgroup_memory_bounds(cgroup_root=cgroup_root)

    # 2. Determine base physical memory (integrating Phase 2 audit findings if available)
    if phase_2_findings is not None and phase_2_findings.total_physical_ram_bytes > 0:
        total_bytes = phase_2_findings.total_physical_ram_bytes
    else:
        total_bytes = get_absolute_physical_ram()

    vmem = psutil.virtual_memory()
    smem = psutil.swap_memory()

    available_bytes = int(vmem.available)
    free_bytes = int(vmem.free)
    swap_total = int(smem.total)
    swap_free = int(smem.free)

    # Enhance with /proc/meminfo if available on Linux
    proc_data = parse_proc_meminfo(proc_root=proc_root)
    if proc_data:
        if "MemTotal" in proc_data and phase_2_findings is None:
            total_bytes = proc_data["MemTotal"]
        if "MemAvailable" in proc_data:
            available_bytes = proc_data["MemAvailable"]
        if "MemFree" in proc_data:
            free_bytes = proc_data["MemFree"]
        if "SwapTotal" in proc_data:
            swap_total = proc_data["SwapTotal"]
        if "SwapFree" in proc_data:
            swap_free = proc_data["SwapFree"]

    hpc_scheduler, hpc_limit_bytes = detect_hpc_memory_limits()

    # Determine bounded total RAM
    bounded_bytes = total_bytes
    if cg_profile.memory_limit_bytes is not None and cg_profile.memory_limit_bytes < bounded_bytes:
        bounded_bytes = cg_profile.memory_limit_bytes

    if hpc_limit_bytes is not None and hpc_limit_bytes < bounded_bytes:
        bounded_bytes = hpc_limit_bytes

    bounded_mb = round(bounded_bytes / (1024 * 1024), 2)
    bounded_gb = round(bounded_bytes / (1024 * 1024 * 1024), 2)

    host_profile = HostMemoryProfile(
        total_ram_bytes=total_bytes,
        available_ram_bytes=available_bytes,
        free_ram_bytes=free_bytes,
        swap_total_bytes=swap_total,
        swap_free_bytes=swap_free,
        effective_system_ram_bytes=total_bytes,
        hpc_scheduler_detected=hpc_scheduler,
        hpc_job_memory_limit_bytes=hpc_limit_bytes,
        bounded_total_ram_bytes=bounded_bytes,
        bounded_total_ram_mb=bounded_mb,
        bounded_total_ram_gb=bounded_gb,
    )

    return host_profile, cg_profile


def discover_numa_topology(sys_root: Optional[Path] = None) -> MultiTierMemoryProfile:
    """
    Discover physical NUMA node topology via Linux sysfs (/sys/devices/system/node/).
    Gracefully degrades to Unified UMA profile on single-socket or non-Linux systems.
    """
    base_dir = sys_root or Path("/sys/devices/system/node")
    nodes: List[NumaNodeProfile] = []

    if base_dir.exists() and base_dir.is_dir():
        node_entries = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("node")])
        for node_dir in node_entries:
            try:
                node_id = int(node_dir.name.replace("node", ""))
            except ValueError:
                continue

            node_total_mb = 0.0
            node_free_mb = 0.0
            cpu_ids: List[int] = []

            # Parse node meminfo
            meminfo_file = node_dir / "meminfo"
            if meminfo_file.exists():
                try:
                    for line in meminfo_file.read_text(encoding="utf-8").splitlines():
                        if "MemTotal" in line:
                            parts = line.split()
                            if len(parts) >= 4:
                                node_total_mb = round(float(parts[3]) / 1024.0, 2)
                        elif "MemFree" in line:
                            parts = line.split()
                            if len(parts) >= 4:
                                node_free_mb = round(float(parts[3]) / 1024.0, 2)
                except (OSError, ValueError):
                    pass

            # Parse node cpulist (e.g. "0-7,16-23")
            cpulist_file = node_dir / "cpulist"
            if cpulist_file.exists():
                try:
                    cpulist_str = cpulist_file.read_text(encoding="utf-8").strip()
                    for segment in cpulist_str.split(","):
                        if "-" in segment:
                            s_start, s_end = segment.split("-", 1)
                            cpu_ids.extend(range(int(s_start), int(s_end) + 1))
                        elif segment.isdigit():
                            cpu_ids.append(int(segment))
                except (OSError, ValueError):
                    pass

            nodes.append(
                NumaNodeProfile(
                    node_id=node_id,
                    total_ram_mb=node_total_mb,
                    free_ram_mb=node_free_mb,
                    cpu_core_ids=cpu_ids,
                    is_local=(node_id == 0),
                )
            )

    if not nodes:
        # Fallback to Unified Memory Architecture (UMA)
        vmem = psutil.virtual_memory()
        smem = psutil.swap_memory()
        total_mb = round(vmem.total / (1024 * 1024), 2)
        free_mb = round(vmem.available / (1024 * 1024), 2)
        swap_mb = round(smem.total / (1024 * 1024), 2)
        cpu_count = psutil.cpu_count(logical=True) or 1

        node0 = NumaNodeProfile(
            node_id=0,
            total_ram_mb=total_mb,
            free_ram_mb=free_mb,
            cpu_core_ids=list(range(cpu_count)),
            is_local=True,
        )
        return MultiTierMemoryProfile(
            numa_nodes_count=1,
            numa_nodes=[node0],
            numa_balance_status=NUMABalanceStatus.UNIFIED_UMA,
            tier_1_local_ram_mb=total_mb,
            tier_2_remote_ram_mb=0.0,
            tier_3_swap_mb=swap_mb,
            is_numa_aware=False,
        )

    # Compute multi-tier statistics
    tier_1_local = sum(n.total_ram_mb for n in nodes if n.is_local)
    tier_2_remote = sum(n.total_ram_mb for n in nodes if not n.is_local)
    smem = psutil.swap_memory()
    tier_3_swap = round(smem.total / (1024 * 1024), 2)

    balance = NUMABalanceStatus.BALANCED
    if len(nodes) > 1:
        totals = [n.total_ram_mb for n in nodes if n.total_ram_mb > 0]
        if totals and (max(totals) - min(totals)) > 1024:  # > 1 GB difference
            balance = NUMABalanceStatus.ASYMMETRIC

    return MultiTierMemoryProfile(
        numa_nodes_count=len(nodes),
        numa_nodes=nodes,
        numa_balance_status=balance,
        tier_1_local_ram_mb=tier_1_local,
        tier_2_remote_ram_mb=tier_2_remote,
        tier_3_swap_mb=tier_3_swap,
        is_numa_aware=(len(nodes) > 1),
    )


# =============================================================================
# 6. THE OOM SHIELD MATHEMATICAL SCALING ALGORITHMS
# =============================================================================


def compute_os_jupyter_reserve(
    total_ram_mb: float,
    custom_reserve_mb: Optional[int] = None,
) -> int:
    """
    Compute flat OS/Jupyter safety buffer reservation in Megabytes.
    Reserves a flat 4-8 GB for OS and interactive agent council/Jupyter needs instead of wasting
    fixed percentage buffers on massive nodes (e.g. 20% on a 1 TB node wastes 200 GB).

    For medium-to-large memory systems (>= 16384 MB / 16 GB):
      OS_Reserve_MB = clamp(4096, 8192, int(0.15 * total_ram_mb))
    For constrained memory systems (< 16384 MB):
      OS_Reserve_MB = max(1024, min(int(0.20 * total_ram_mb), int(total_ram_mb - 512)))
    """
    if custom_reserve_mb is not None and custom_reserve_mb > 0:
        # Clamp custom reservation to leave at least 512 MB for calculations
        return max(512, min(custom_reserve_mb, int(total_ram_mb - 512)))

    if total_ram_mb >= 16384.0:  # >= 16 GB
        # 15% scaled reservation clamped strictly between 4096 MB (4 GB) and 8192 MB (8 GB)
        reserve = int(0.15 * total_ram_mb)
        return max(DEFAULT_MIN_OS_RESERVE_MB, min(reserve, DEFAULT_MAX_OS_RESERVE_MB))
    else:
        # For lower-memory nodes (< 16 GB), reserve 20% ensuring at least 512 MB remains allocatable
        reserve = int(0.20 * total_ram_mb)
        max_safe_reserve = max(512, int(total_ram_mb - 512))
        return max(1024, min(reserve, max_safe_reserve)) if total_ram_mb > 1536 else max(256, int(total_ram_mb - 512))


def compute_oom_shield_scaling(
    host_mem: HostMemoryProfile,
    total_physical_cores: int,
    active_cores: Optional[int] = None,
    os_reserve_mb: Optional[int] = None,
) -> OOMShieldScalingProfile:
    """
    Apply the OOM Shield Dynamic Memory Scaling Algorithm.
    Divides allocatable memory specifically across *active calculation cores* rather than total physical cores,
    while reserving a flat 4-8 GB OS/Jupyter safety buffer.

    Formulas:
      Total_RAM_MB = host_mem.bounded_total_ram_mb
      OS_Reserve_MB = compute_os_jupyter_reserve(Total_RAM_MB, os_reserve_mb)
      Allocatable_RAM_MB = max(512, Total_RAM_MB - OS_Reserve_MB)
      Baseline_%maxcore_MB = int(((Total_RAM_GB * 1024) * 0.80) / Total_Physical_Cores)
      Active_Core_Maxcore_MB = int(Allocatable_RAM_MB / Active_Job_Cores)
    """
    total_cores = max(1, total_physical_cores)

    # Clamp active cores to valid physical range [1, total_physical_cores]
    if active_cores is None:
        calc_active_cores = total_cores
    elif active_cores <= 0:
        calc_active_cores = 1
    else:
        calc_active_cores = min(active_cores, total_cores)

    bounded_total_mb = host_mem.bounded_total_ram_mb
    bounded_total_gb = host_mem.bounded_total_ram_gb

    reserve_mb = compute_os_jupyter_reserve(bounded_total_mb, custom_reserve_mb=os_reserve_mb)
    allocatable_mb = max(512, int(bounded_total_mb - reserve_mb))
    allocatable_gb = round(allocatable_mb / 1024.0, 2)
    reserve_ratio = round(reserve_mb / max(1.0, bounded_total_mb), 4)

    # Baseline 80% formula divided by total physical cores (Document 5 Section 4.2)
    baseline_maxcore_mb = int(((bounded_total_gb * 1024.0) * 0.80) / total_cores)

    # CoChem Dynamic OOM Shield formula divided across active calculation cores
    active_maxcore_mb = int(allocatable_mb / calc_active_cores)

    # Calculate memory gain percentage
    if baseline_maxcore_mb > 0:
        gain_pct = round(((active_maxcore_mb - baseline_maxcore_mb) / baseline_maxcore_mb) * 100.0, 1)
    else:
        gain_pct = 0.0

    return OOMShieldScalingProfile(
        total_physical_cores=total_cores,
        active_job_cores=calc_active_cores,
        bounded_total_ram_mb=bounded_total_mb,
        os_jupyter_reserve_mb=reserve_mb,
        reserve_ratio=reserve_ratio,
        allocatable_ram_mb=allocatable_mb,
        allocatable_ram_gb=allocatable_gb,
        baseline_80pct_maxcore_mb=baseline_maxcore_mb,
        active_core_maxcore_mb=active_maxcore_mb,
        memory_gain_vs_baseline_pct=gain_pct,
        shield_active=True,
    )


# =============================================================================
# 7. MULTI-ENGINE TARGET MEMORY TRANSLATORS
# =============================================================================


def build_engine_memory_budgets(
    allocatable_ram_mb: int,
    active_core_maxcore_mb: int,
    active_cores: int,
) -> Dict[str, EngineMemoryBudget]:
    """
    Synthesize engine-native memory configuration directives and environment variables
    for all supported quantum chemistry and machine learning solvers.
    """
    budgets: Dict[str, EngineMemoryBudget] = {}

    # 1. ORCA (%maxcore is per-core memory in MB)
    budgets["ORCA"] = EngineMemoryBudget(
        engine=EngineTarget.ORCA,
        primary_directive_name="%maxcore",
        directive_value_formatted=f"%maxcore {active_core_maxcore_mb}",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=active_core_maxcore_mb * active_cores,
        env_var_name="ORCA_MAXCORE",
        env_var_value=str(active_core_maxcore_mb),
        notes=f"Calculated for {active_cores} active core(s) with flat OS buffer",
    )

    # 2. PySCF (max_memory is total job memory in MB)
    budgets["PYSCF"] = EngineMemoryBudget(
        engine=EngineTarget.PYSCF,
        primary_directive_name="max_memory",
        directive_value_formatted=f"mol.max_memory = {allocatable_ram_mb}",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="PYSCF_MAX_MEMORY",
        env_var_value=str(allocatable_ram_mb),
        notes="Global process memory ceiling for lib/pyscf integral caches",
    )

    # 3. xTB (--memory is total job memory in MB)
    budgets["XTB"] = EngineMemoryBudget(
        engine=EngineTarget.XTB,
        primary_directive_name="--memory",
        directive_value_formatted=f"--memory {allocatable_ram_mb}m",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="XTB_MAX_MEMORY",
        env_var_value=str(allocatable_ram_mb),
        notes="Extended Tight Binding total calculation memory envelope",
    )

    # 4. Gaussian (%mem is total memory in MB or GB)
    budgets["GAUSSIAN"] = EngineMemoryBudget(
        engine=EngineTarget.GAUSSIAN,
        primary_directive_name="%mem",
        directive_value_formatted=f"%mem={allocatable_ram_mb}MB",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="GAUSS_MEMDEF",
        env_var_value=str(allocatable_ram_mb * 1024 * 1024),  # Gaussian bytes
        notes="Gaussian %memLink0 directive and GAUSS_MEMDEF byte ceiling",
    )

    # 5. CFOUR (MEMORY_SIZE is double precision words = 8 bytes per word)
    cfour_words = int((allocatable_ram_mb * 1024 * 1024) / 8)
    budgets["CFOUR"] = EngineMemoryBudget(
        engine=EngineTarget.CFOUR,
        primary_directive_name="MEMORY_SIZE",
        directive_value_formatted=f"MEMORY_SIZE = {cfour_words}",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="CFOUR_MEMORY_SIZE",
        env_var_value=str(cfour_words),
        notes="Coupled-Cluster integral memory array in 64-bit float words",
    )

    # 6. MACE-Torch (Host pinned RAM for MLFF GPU offloading)
    budgets["MACE_TORCH"] = EngineMemoryBudget(
        engine=EngineTarget.MACE_TORCH,
        primary_directive_name="COCHEM_MACE_HOST_RAM_MB",
        directive_value_formatted=f"Host VRAM Offload Buffer: {allocatable_ram_mb} MB",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="COCHEM_MACE_HOST_RAM_MB",
        env_var_value=str(allocatable_ram_mb),
        notes="Allocatable host system memory for GPU tensor dataset buffering",
    )

    # 7. OpenMPI (MPI Shared memory and buffer limits)
    budgets["OPENMPI"] = EngineMemoryBudget(
        engine=EngineTarget.OPENMPI,
        primary_directive_name="OMPI_MCA_btl_vader_single_copy_mechanism",
        directive_value_formatted="OMPI_MCA_btl_vader_single_copy_mechanism = none",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="OMPI_MCA_btl_vader_single_copy_mechanism",
        env_var_value="none",
        notes="Bypasses kernel CMA traps across isolated memory namespaces",
    )

    # 8. Generic CoChem Engine
    budgets["GENERIC"] = EngineMemoryBudget(
        engine=EngineTarget.GENERIC,
        primary_directive_name="COCHEM_MAXCORE_MB",
        directive_value_formatted=f"COCHEM_MAXCORE_MB={active_core_maxcore_mb}",
        allocated_per_core_mb=active_core_maxcore_mb,
        allocated_total_job_mb=allocatable_ram_mb,
        env_var_name="COCHEM_MAXCORE_MB",
        env_var_value=str(active_core_maxcore_mb),
        notes="Standard CoChem per-core memory envelope for custom solvers",
    )

    return budgets


def generate_environment_injection_dict(
    oom_shield: OOMShieldScalingProfile,
    budgets: Dict[str, EngineMemoryBudget],
) -> Dict[str, str]:
    """
    Generate comprehensive runtime environment variable injection mapping.
    """
    env_dict: Dict[str, str] = {}

    # Engine specific allocations
    for engine_key, budget in budgets.items():
        if budget.env_var_name and budget.env_var_value:
            env_dict[budget.env_var_name] = budget.env_var_value

    # System-level CoChem OOM Shield variables
    env_dict["COCHEM_MAXCORE_MB"] = str(oom_shield.active_core_maxcore_mb)
    env_dict["COCHEM_ALLOCATABLE_RAM_MB"] = str(oom_shield.allocatable_ram_mb)
    env_dict["COCHEM_ALLOCATABLE_RAM_GB"] = str(oom_shield.allocatable_ram_gb)
    env_dict["COCHEM_SAFETY_BUFFER_MB"] = str(oom_shield.os_jupyter_reserve_mb)
    env_dict["COCHEM_ACTIVE_CORES"] = str(oom_shield.active_job_cores)
    env_dict["COCHEM_TOTAL_RAM_MB"] = str(int(oom_shield.bounded_total_ram_mb))
    env_dict["COCHEM_OOM_SHIELD_STATUS"] = "ACTIVE" if oom_shield.shield_active else "INACTIVE"

    return env_dict


# =============================================================================
# 8. AUDIT EXECUTION ENGINE & CLI
# =============================================================================


def run_phase_11_audit(
    output_dir: Optional[Union[str, Path]] = None,
    active_cores: Optional[int] = None,
    os_reserve_mb: Optional[int] = None,
    cgroup_root: Optional[Path] = None,
    proc_root: Optional[Path] = None,
    sys_root: Optional[Path] = None,
    p2_path: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> Phase11AuditReport:
    """
    Execute comprehensive Setup Phase 11 Memory Router & OOM Shield Gatekeeper Audit.
    Discovers hardware limits, computes dynamic %maxcore scaling across active job cores,
    formats multi-engine directives, and persists state into Golden Registry (p11.json).
    """
    warnings: List[str] = []
    errors: List[str] = []
    status = PhaseStatus.PASSED

    # 0. Ingest Phase 2 Audit Findings if available
    p2_findings = load_phase_2_audit_findings(p2_path=p2_path, registry_dir=output_dir)
    if p2_findings is not None:
        warnings.append(
            f"Phase 2 audit findings loaded from {p2_findings.loaded_from} (Status: {p2_findings.status})"
        )

    # 1. Audit Host Memory & CGroup Bounds
    try:
        host_mem, cg_profile = audit_host_memory(
            cgroup_root=cgroup_root,
            proc_root=proc_root,
            phase_2_findings=p2_findings,
        )
    except Exception as exc:
        raise MemoryDiscoveryError(f"Fatal error discovering host/container memory: {exc}") from exc

    if cg_profile.is_cgroup_constrained:
        warnings.append(
            f"Execution memory actively bounded by Linux cgroups ({cg_profile.cgroup_version.value}) "
            f"to {round((cg_profile.memory_limit_bytes or 0)/(1024*1024*1024), 2)} GB"
        )

    if host_mem.hpc_scheduler_detected:
        warnings.append(
            f"HPC Workload Scheduler detected: {host_mem.hpc_scheduler_detected} "
            f"(Job Memory Limit: {round((host_mem.hpc_job_memory_limit_bytes or 0)/(1024*1024*1024), 2) if host_mem.hpc_job_memory_limit_bytes else 'Unlimited'} GB)"
        )

    # 2. Discover NUMA Topology
    try:
        numa_profile = discover_numa_topology(sys_root=sys_root)
    except Exception as exc:
        warnings.append(f"NUMA topology discovery degraded: {exc}")
        numa_profile = MultiTierMemoryProfile(
            numa_nodes_count=1,
            numa_nodes=[],
            numa_balance_status=NUMABalanceStatus.UNKNOWN,
            tier_1_local_ram_mb=host_mem.bounded_total_ram_mb,
            tier_2_remote_ram_mb=0.0,
            tier_3_swap_mb=round(host_mem.swap_total_bytes / (1024 * 1024), 2),
            is_numa_aware=False,
        )

    # 3. Interrogate CPU Physical Cores (utilizing Phase 2 findings if available)
    if p2_findings is not None and p2_findings.physical_cores > 0:
        physical_cores = p2_findings.physical_cores
    else:
        physical_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 1

    # 4. Compute OOM Shield Scaling Profile
    try:
        oom_shield = compute_oom_shield_scaling(
            host_mem=host_mem,
            total_physical_cores=physical_cores,
            active_cores=active_cores,
            os_reserve_mb=os_reserve_mb,
        )
    except Exception as exc:
        raise EngineBudgetError(f"Fatal error computing OOM Shield scaling parameters: {exc}") from exc

    # 5. Build Multi-Engine Memory Budgets
    try:
        engine_budgets = build_engine_memory_budgets(
            allocatable_ram_mb=oom_shield.allocatable_ram_mb,
            active_core_maxcore_mb=oom_shield.active_core_maxcore_mb,
            active_cores=oom_shield.active_job_cores,
        )
    except Exception as exc:
        raise EngineBudgetError(f"Fatal error building multi-engine memory budgets: {exc}") from exc

    # 6. Generate Environment Variable Injections
    injected_env_vars = generate_environment_injection_dict(
        oom_shield=oom_shield,
        budgets=engine_budgets,
    )

    # Determine artifact destination path
    artifact_path = resolve_p11_registry_path(output_dir=output_dir)

    timestamp_now = datetime.now(timezone.utc).isoformat()

    report = Phase11AuditReport(
        phase_id="cochem_setup_phase_11",
        status=status,
        timestamp_utc=timestamp_now,
        artifact_path=str(artifact_path),
        phase_2_findings=p2_findings,
        host_memory=host_mem,
        cgroup_profile=cg_profile,
        numa_profile=numa_profile,
        oom_shield=oom_shield,
        engine_budgets=engine_budgets,
        injected_env_vars=injected_env_vars,
        warnings=warnings,
        errors=errors,
    )

    # 7. Transactional State Persistence into Golden Registry
    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(artifact_path, report)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    """Command-line interface entry point for Setup Phase 11."""
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 11: Memory Router & OOM Shield Gatekeeper",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p11.json)",
    )
    parser.add_argument(
        "--p2-path",
        type=str,
        default=None,
        help="Path to Phase 2 audit state artifact (p2.json) to ingest baseline hardware constraints",
    )
    parser.add_argument(
        "--active-cores",
        type=int,
        default=None,
        help="Active job calculation cores requested for this calculation (default: all physical cores)",
    )
    parser.add_argument(
        "--os-reserve-mb",
        type=int,
        default=None,
        help="Custom flat OS/Jupyter safety buffer reserve in Megabytes (default: dynamic 4096-8192 MB)",
    )
    parser.add_argument(
        "--cgroup-root",
        type=str,
        default=None,
        help="Custom root directory for Linux cgroups inspection (e.g. /sys/fs/cgroup)",
    )
    parser.add_argument(
        "--proc-root",
        type=str,
        default=None,
        help="Custom root directory for /proc inspection (e.g. /proc)",
    )
    parser.add_argument(
        "--sys-root",
        type=str,
        default=None,
        help="Custom root directory for sysfs NUMA node inspection (e.g. /sys/devices/system/node)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate audit without persisting state to p11.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        cg_root = Path(args.cgroup_root) if args.cgroup_root else None
        p_root = Path(args.proc_root) if args.proc_root else None
        s_root = Path(args.sys_root) if args.sys_root else None

        report = run_phase_11_audit(
            output_dir=args.output_dir,
            active_cores=args.active_cores,
            os_reserve_mb=args.os_reserve_mb,
            cgroup_root=cg_root,
            proc_root=p_root,
            sys_root=s_root,
            p2_path=args.p2_path,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 11: MEMORY ROUTER & OOM SHIELD GATEKEEPER")
            print("=" * 75)
            print(f"Phase ID:          {report.phase_id}")
            print(f"Status:            {report.status.value}")
            print(f"Timestamp UTC:     {report.timestamp_utc}")
            print(f"Artifact Path:     {report.artifact_path}")
            print("-" * 75)
            print("Host & Container Bounded Memory Profile:")
            hm = report.host_memory
            print(f"  Physical RAM:    {hm.total_ram_bytes / (1024**3):.2f} GB ({hm.available_ram_bytes / (1024**3):.2f} GB available)")
            print(f"  Swap Space:      {hm.swap_total_bytes / (1024**3):.2f} GB ({hm.swap_free_bytes / (1024**3):.2f} GB free)")
            cg = report.cgroup_profile
            print(f"  CGroup Version:  {cg.cgroup_version.value} (Constrained: {cg.is_cgroup_constrained})")
            if cg.memory_limit_bytes:
                print(f"  CGroup Limit:    {cg.memory_limit_bytes / (1024**3):.2f} GB")
            print(f"  Bounded RAM:     {hm.bounded_total_ram_gb:.2f} GB ({hm.bounded_total_ram_mb:.1f} MB)")
            print("-" * 75)
            print("NUMA Multi-Tier Memory Topology:")
            numa = report.numa_profile
            print(f"  NUMA Nodes:      {numa.numa_nodes_count} (Aware: {numa.is_numa_aware}, Balance: {numa.numa_balance_status.value})")
            print(f"  Tier 1 Local:    {numa.tier_1_local_ram_mb / 1024:.2f} GB")
            print(f"  Tier 2 Remote:   {numa.tier_2_remote_ram_mb / 1024:.2f} GB")
            print(f"  Tier 3 Swap:     {numa.tier_3_swap_mb / 1024:.2f} GB")
            print("-" * 75)
            print("OOM Shield Memory Partitioning Profile:")
            oom = report.oom_shield
            print(f"  CPU Cores:       {oom.total_physical_cores} Physical Cores / {oom.active_job_cores} Active Job Core(s)")
            print(f"  OS Safety Buffer: {oom.os_jupyter_reserve_mb} MB ({oom.reserve_ratio * 100:.1f}%) [Flat 4-8 GB Reserved]")
            print(f"  Allocatable RAM: {oom.allocatable_ram_mb} MB ({oom.allocatable_ram_gb:.2f} GB)")
            print(f"  Baseline %maxcore (All Cores): {oom.baseline_80pct_maxcore_mb} MB/core")
            print(f"  OOM Shield %maxcore (Active):  {oom.active_core_maxcore_mb} MB/core")
            print(f"  Memory Gain:     +{oom.memory_gain_vs_baseline_pct:.1f}% vs baseline")
            print("-" * 75)
            print("Multi-Engine Target Directives:")
            for eng_name, bud in report.engine_budgets.items():
                print(f"  [{eng_name:10}] {bud.directive_value_formatted:<35} | {bud.env_var_name}={bud.env_var_value}")
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
        sys.stderr.write(f"\n[FATAL PHASE 11 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_11.py ---
"""
Unit test suite for CoChem Setup Phase 11: Memory Router & Adaptive Tiering (The OOM Shield).
Strict Zero-Mock Mandate: Real filesystem operations, real temporary directories, real memory
hierarchy and cgroup v1/v2 parsing, real NUMA topology discovery, real active core memory
scaling mathematics, real multi-engine target directives (ORCA, PySCF, xTB, Gaussian, CFOUR,
MACE-Torch, OpenMPI), real environment variable injection dictionaries, and transactional
atomic state persistence into the Golden Registry (p11.json).

SRS Document 2 Part 2 (Section 3.11), SRS Document 5 (Section 4.2), Method Matrix v4,
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_11 import (
    CGroupLimitError,
    CGroupMemoryProfile,
    CGroupVersion,
    DependencyManager,
    EngineBudgetError,
    EngineMemoryBudget,
    EngineTarget,
    HostMemoryProfile,
    MemoryDiscoveryError,
    MemoryTier,
    MultiTierMemoryProfile,
    NUMABalanceStatus,
    NUMADiscoveryError,
    NumaNodeProfile,
    OOMShieldScalingProfile,
    Phase2AuditFindings,
    Phase11AuditError,
    Phase11AuditReport,
    PhaseStatus,
    audit_host_memory,
    build_engine_memory_budgets,
    compute_os_jupyter_reserve,
    compute_oom_shield_scaling,
    detect_hpc_memory_limits,
    discover_numa_topology,
    find_repository_root,
    generate_environment_injection_dict,
    get_absolute_physical_ram,
    load_phase_2_audit_findings,
    main,
    parse_cgroup_memory_bounds,
    parse_proc_meminfo,
    resolve_p11_registry_path,
    run_phase_11_audit,
)


def make_temp_dir() -> tempfile.TemporaryDirectory:
    """Create a temporary directory with Windows cleanup resilience."""
    if hasattr(tempfile.TemporaryDirectory, "_ignore_cleanup_errors") or platform.system() == "Windows":
        try:
            return tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        except TypeError:
            pass
    return tempfile.TemporaryDirectory()


# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 11 exception classes inherit from Phase11AuditError and RuntimeError."""
    err1 = Phase11AuditError("Phase 11 fatal error")
    assert isinstance(err1, RuntimeError)

    err2 = MemoryDiscoveryError("Memory discovery failed")
    assert isinstance(err2, Phase11AuditError)
    assert isinstance(err2, RuntimeError)

    err3 = CGroupLimitError("Cgroup limit error")
    assert isinstance(err3, Phase11AuditError)
    assert isinstance(err3, RuntimeError)

    err4 = EngineBudgetError("Engine budget error")
    assert isinstance(err4, Phase11AuditError)
    assert isinstance(err4, RuntimeError)

    err5 = NUMADiscoveryError("NUMA discovery error")
    assert isinstance(err5, Phase11AuditError)
    assert isinstance(err5, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_cgroup_version_enum() -> None:
    """Verify CGroupVersion enum values."""
    assert CGroupVersion.V1.value == "V1"
    assert CGroupVersion.V2.value == "V2"
    assert CGroupVersion.HYBRID.value == "HYBRID"
    assert CGroupVersion.NOT_AVAILABLE.value == "NOT_AVAILABLE"
    assert CGroupVersion.NOT_APPLICABLE.value == "NOT_APPLICABLE"


def test_memory_tier_enum() -> None:
    """Verify MemoryTier enum values."""
    assert MemoryTier.TIER_1_LOCAL_NUMA.value == "TIER_1_LOCAL_NUMA"
    assert MemoryTier.TIER_2_REMOTE_NUMA.value == "TIER_2_REMOTE_NUMA"
    assert MemoryTier.TIER_3_SWAP_STORAGE.value == "TIER_3_SWAP_STORAGE"


def test_engine_target_enum() -> None:
    """Verify EngineTarget enum values."""
    assert EngineTarget.ORCA.value == "ORCA"
    assert EngineTarget.PYSCF.value == "PYSCF"
    assert EngineTarget.XTB.value == "XTB"
    assert EngineTarget.GAUSSIAN.value == "GAUSSIAN"
    assert EngineTarget.CFOUR.value == "CFOUR"
    assert EngineTarget.MACE_TORCH.value == "MACE_TORCH"
    assert EngineTarget.OPENMPI.value == "OPENMPI"
    assert EngineTarget.GENERIC.value == "GENERIC"


def test_numa_balance_status_enum() -> None:
    """Verify NUMABalanceStatus enum values."""
    assert NUMABalanceStatus.BALANCED.value == "BALANCED"
    assert NUMABalanceStatus.ASYMMETRIC.value == "ASYMMETRIC"
    assert NUMABalanceStatus.UNIFIED_UMA.value == "UNIFIED_UMA"
    assert NUMABalanceStatus.UNKNOWN.value == "UNKNOWN"


# =============================================================================
# 2. PYDANTIC V2 DATA MODEL TESTS
# =============================================================================


def test_cgroup_memory_profile_model() -> None:
    """Verify CGroupMemoryProfile creation, serialization, and strict validation."""
    profile = CGroupMemoryProfile(
        cgroup_version=CGroupVersion.V2,
        memory_limit_bytes=34359738368,
        memory_max_bytes=34359738368,
        memory_high_bytes=32212254720,
        memory_current_bytes=4294967296,
        swap_limit_bytes=None,
        is_cgroup_constrained=True,
        cgroup_path="/sys/fs/cgroup/memory.max",
    )
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.is_cgroup_constrained is True
    assert profile.memory_limit_bytes == 34359738368

    # Verify extra="forbid" raises ValidationError
    with pytest.raises(ValidationError):
        CGroupMemoryProfile(
            cgroup_version=CGroupVersion.V2,
            is_cgroup_constrained=False,
            unauthorized_extra_field=123,
        )


def test_host_memory_profile_model() -> None:
    """Verify HostMemoryProfile validation and computed properties."""
    host = HostMemoryProfile(
        total_ram_bytes=68719476736,  # 64 GB
        available_ram_bytes=51539607552,  # 48 GB
        free_ram_bytes=42949672960,  # 40 GB
        swap_total_bytes=8589934592,  # 8 GB
        swap_free_bytes=8589934592,
        effective_system_ram_bytes=68719476736,
        hpc_scheduler_detected=None,
        hpc_job_memory_limit_bytes=None,
        bounded_total_ram_bytes=68719476736,
        bounded_total_ram_mb=65536.0,
        bounded_total_ram_gb=64.0,
    )
    assert host.bounded_total_ram_gb == 64.0
    assert host.bounded_total_ram_mb == 65536.0

    # Test rejection of negative memory
    with pytest.raises(ValidationError):
        HostMemoryProfile(
            total_ram_bytes=-100,
            available_ram_bytes=100,
            free_ram_bytes=100,
            swap_total_bytes=0,
            swap_free_bytes=0,
            effective_system_ram_bytes=100,
            bounded_total_ram_bytes=100,
            bounded_total_ram_mb=100.0,
            bounded_total_ram_gb=0.1,
        )


def test_numa_node_profile_model() -> None:
    """Verify NumaNodeProfile creation and strict validation."""
    node = NumaNodeProfile(
        node_id=0,
        total_ram_mb=32768.0,
        free_ram_mb=28000.0,
        cpu_core_ids=[0, 1, 2, 3, 4, 5, 6, 7],
        is_local=True,
    )
    assert node.node_id == 0
    assert len(node.cpu_core_ids) == 8
    assert node.is_local is True

    with pytest.raises(ValidationError):
        NumaNodeProfile(
            node_id=-1,
            total_ram_mb=1024.0,
            free_ram_mb=512.0,
            cpu_core_ids=[],
            is_local=True,
        )


def test_multi_tier_memory_profile_model() -> None:
    """Verify MultiTierMemoryProfile validation."""
    node0 = NumaNodeProfile(node_id=0, total_ram_mb=32768.0, free_ram_mb=28000.0, cpu_core_ids=[0, 1], is_local=True)
    profile = MultiTierMemoryProfile(
        numa_nodes_count=1,
        numa_nodes=[node0],
        numa_balance_status=NUMABalanceStatus.UNIFIED_UMA,
        tier_1_local_ram_mb=32768.0,
        tier_2_remote_ram_mb=0.0,
        tier_3_swap_mb=8192.0,
        is_numa_aware=False,
    )
    assert profile.numa_nodes_count == 1
    assert profile.tier_1_local_ram_mb == 32768.0


def test_engine_memory_budget_model() -> None:
    """Verify EngineMemoryBudget validation and formatting."""
    budget = EngineMemoryBudget(
        engine=EngineTarget.ORCA,
        primary_directive_name="%maxcore",
        directive_value_formatted="%maxcore 7168",
        allocated_per_core_mb=7168,
        allocated_total_job_mb=28672,
        env_var_name="ORCA_MAXCORE",
        env_var_value="7168",
        notes="Safe 4-core allocation with flat 4GB OS buffer",
    )
    assert budget.engine == EngineTarget.ORCA
    assert budget.allocated_per_core_mb == 7168
    assert budget.allocated_total_job_mb == 28672


def test_oom_shield_scaling_profile_model() -> None:
    """Verify OOMShieldScalingProfile mathematical constraints."""
    profile = OOMShieldScalingProfile(
        total_physical_cores=16,
        active_job_cores=4,
        bounded_total_ram_mb=65536.0,
        os_jupyter_reserve_mb=8192,
        reserve_ratio=0.125,
        allocatable_ram_mb=57344,
        allocatable_ram_gb=56.0,
        baseline_80pct_maxcore_mb=3276,
        active_core_maxcore_mb=14336,
        memory_gain_vs_baseline_pct=337.6,
        shield_active=True,
    )
    assert profile.active_core_maxcore_mb == 14336
    assert profile.baseline_80pct_maxcore_mb == 3276
    assert profile.memory_gain_vs_baseline_pct > 0.0


# =============================================================================
# 3. LOW-LEVEL DISCOVERY & PARSING TESTS (ZERO-MOCK)
# =============================================================================


def test_parse_proc_meminfo_with_real_files(tmp_path: Path) -> None:
    """Verify parsing of Linux /proc/meminfo formatted content."""
    proc_dir = tmp_path / "proc"
    proc_dir.mkdir()
    meminfo_file = proc_dir / "meminfo"

    content = (
        "MemTotal:       65860884 kB\n"
        "MemFree:        34812320 kB\n"
        "MemAvailable:   52384112 kB\n"
        "Buffers:          524288 kB\n"
        "Cached:         18234560 kB\n"
        "SwapTotal:       8388604 kB\n"
        "SwapFree:        8388604 kB\n"
    )
    meminfo_file.write_text(content, encoding="utf-8")

    parsed = parse_proc_meminfo(proc_root=proc_dir)
    assert parsed["MemTotal"] == 65860884 * 1024
    assert parsed["MemFree"] == 34812320 * 1024
    assert parsed["MemAvailable"] == 52384112 * 1024
    assert parsed["SwapTotal"] == 8388604 * 1024


def test_parse_proc_meminfo_missing_file(tmp_path: Path) -> None:
    """Verify graceful handling when /proc/meminfo does not exist."""
    empty_dir = tmp_path / "empty_proc"
    empty_dir.mkdir()
    parsed = parse_proc_meminfo(proc_root=empty_dir)
    assert parsed == {}


def test_parse_cgroup_v2_memory_bounds(tmp_path: Path) -> None:
    """Verify parsing of cgroups v2 memory bounds (memory.max, memory.high, memory.current)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)

    (cg_dir / "memory.max").write_text("34359738368\n", encoding="utf-8")  # 32 GB
    (cg_dir / "memory.high").write_text("30064771072\n", encoding="utf-8")  # 28 GB
    (cg_dir / "memory.current").write_text("4294967296\n", encoding="utf-8")  # 4 GB

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.memory_max_bytes == 34359738368
    assert profile.memory_high_bytes == 30064771072
    assert profile.memory_current_bytes == 4294967296
    assert profile.memory_limit_bytes == 34359738368
    assert profile.is_cgroup_constrained is True


def test_parse_cgroup_v2_max_string_unconstrained(tmp_path: Path) -> None:
    """Verify cgroups v2 with 'max' token correctly identifies unconstrained memory."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("max\n", encoding="utf-8")

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V2
    assert profile.memory_max_bytes is None
    assert profile.memory_limit_bytes is None
    assert profile.is_cgroup_constrained is False


def test_parse_cgroup_v1_memory_bounds(tmp_path: Path) -> None:
    """Verify parsing of cgroups v1 memory bounds (memory.limit_in_bytes, memory.memsw.limit_in_bytes)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)

    (cg_dir / "memory.limit_in_bytes").write_text("17179869184\n", encoding="utf-8")  # 16 GB
    (cg_dir / "memory.memsw.limit_in_bytes").write_text("21474836480\n", encoding="utf-8")  # 20 GB

    profile = parse_cgroup_memory_bounds(cgroup_root=cg_dir)
    assert profile.cgroup_version == CGroupVersion.V1
    assert profile.memory_limit_bytes == 17179869184
    assert profile.swap_limit_bytes == 21474836480
    assert profile.is_cgroup_constrained is True


def test_detect_hpc_memory_limits_slurm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Slurm HPC job memory limit resolution via environment variables."""
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_MEM_PER_NODE", "65536")  # 64 GB in MB

    scheduler, mem_bytes = detect_hpc_memory_limits()
    assert scheduler == "Slurm"
    assert mem_bytes == 65536 * 1024 * 1024


def test_detect_hpc_memory_limits_pbs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify PBS HPC job memory limit resolution via environment variables."""
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.setenv("PBS_JOBID", "789012")
    monkeypatch.setenv("PBS_MEM", "32gb")

    scheduler, mem_bytes = detect_hpc_memory_limits()
    assert scheduler == "PBS"
    assert mem_bytes == 32 * 1024 * 1024 * 1024


def test_discover_numa_topology_sysfs(tmp_path: Path) -> None:
    """Verify NUMA node discovery using real sysfs directory hierarchy."""
    sys_dir = tmp_path / "sys" / "devices" / "system" / "node"
    sys_dir.mkdir(parents=True)

    # Node 0
    node0_dir = sys_dir / "node0"
    node0_dir.mkdir()
    (node0_dir / "meminfo").write_text(
        "Node 0 MemTotal:       32930442 kB\n"
        "Node 0 MemFree:        28192000 kB\n",
        encoding="utf-8",
    )
    (node0_dir / "cpulist").write_text("0-7\n", encoding="utf-8")

    # Node 1
    node1_dir = sys_dir / "node1"
    node1_dir.mkdir()
    (node1_dir / "meminfo").write_text(
        "Node 1 MemTotal:       32930442 kB\n"
        "Node 1 MemFree:        29100000 kB\n",
        encoding="utf-8",
    )
    (node1_dir / "cpulist").write_text("8-15\n", encoding="utf-8")

    profile = discover_numa_topology(sys_root=sys_dir)
    assert profile.numa_nodes_count == 2
    assert profile.is_numa_aware is True
    assert profile.numa_balance_status in (NUMABalanceStatus.BALANCED, NUMABalanceStatus.ASYMMETRIC)
    assert len(profile.numa_nodes) == 2
    assert profile.numa_nodes[0].cpu_core_ids == [0, 1, 2, 3, 4, 5, 6, 7]
    assert profile.numa_nodes[1].cpu_core_ids == [8, 9, 10, 11, 12, 13, 14, 15]


def test_discover_numa_topology_fallback_uma(tmp_path: Path) -> None:
    """Verify NUMA discovery graceful fallback to Unified UMA when no sysfs nodes exist."""
    empty_sys = tmp_path / "empty_sys"
    empty_sys.mkdir()
    profile = discover_numa_topology(sys_root=empty_sys)
    assert profile.numa_nodes_count == 1
    assert profile.is_numa_aware is False
    assert profile.numa_balance_status == NUMABalanceStatus.UNIFIED_UMA


# =============================================================================
# 4. MATHEMATICAL GUARDRAIL & OOM SHIELD TESTS
# =============================================================================


def test_compute_os_jupyter_reserve_large_systems() -> None:
    """Verify flat OS/Jupyter reservation bounds on medium and large RAM systems."""
    # 64 GB system (65536 MB): 15% is 9830.4 MB, clamped to max 8192 MB (8 GB)
    res_64g = compute_os_jupyter_reserve(65536.0)
    assert res_64g == 8192

    # 32 GB system (32768 MB): 15% is 4915.2 MB, within [4096, 8192] -> 4915 MB
    res_32g = compute_os_jupyter_reserve(32768.0)
    assert 4096 <= res_32g <= 8192

    # 16 GB system (16384 MB): 15% is 2457.6 MB, clamped to min 4096 MB (4 GB)
    res_16g = compute_os_jupyter_reserve(16384.0)
    assert res_16g == 4096


def test_compute_os_jupyter_reserve_low_ram_systems() -> None:
    """Verify OS/Jupyter reservation scales safely on constrained RAM systems (< 16 GB)."""
    # 8 GB system (8192 MB): 20% is 1638 MB
    res_8g = compute_os_jupyter_reserve(8192.0)
    assert res_8g == 1638
    assert (8192 - res_8g) >= 512

    # 2 GB system (2048 MB): leaves at least 512 MB for calculation
    res_2g = compute_os_jupyter_reserve(2048.0)
    assert res_2g <= (2048 - 512)
    assert (2048 - res_2g) >= 512


def test_compute_os_jupyter_reserve_custom_override() -> None:
    """Verify user-provided custom OS reservation override."""
    res_custom = compute_os_jupyter_reserve(65536.0, custom_reserve_mb=6000)
    assert res_custom == 6000


def test_compute_oom_shield_scaling_active_vs_physical() -> None:
    """
    Verify OOM Shield mathematical division: dividing allocatable memory across active cores
    vs total physical cores, guaranteeing significant memory gains for targeted calculations.
    """
    host_mem = HostMemoryProfile(
        total_ram_bytes=68719476736,  # 64 GB
        available_ram_bytes=60129542144,
        free_ram_bytes=55834574848,
        swap_total_bytes=8589934592,
        swap_free_bytes=8589934592,
        effective_system_ram_bytes=68719476736,
        hpc_scheduler_detected=None,
        hpc_job_memory_limit_bytes=None,
        bounded_total_ram_bytes=68719476736,
        bounded_total_ram_mb=65536.0,
        bounded_total_ram_gb=64.0,
    )

    # 16 physical cores, but user requests 4 active cores for calculation
    shield = compute_oom_shield_scaling(
        host_mem=host_mem,
        total_physical_cores=16,
        active_cores=4,
        os_reserve_mb=8192,
    )

    assert shield.total_physical_cores == 16
    assert shield.active_job_cores == 4
    assert shield.os_jupyter_reserve_mb == 8192
    assert shield.allocatable_ram_mb == 57344  # 65536 - 8192

    # Baseline 80% formula divided by 16 physical cores:
    # int((64 * 1024 * 0.80) / 16) = int(52428.8 / 16) = 3276 MB
    assert shield.baseline_80pct_maxcore_mb == 3276

    # Active core division: int(57344 / 4) = 14336 MB
    assert shield.active_core_maxcore_mb == 14336

    # Memory gain should be ~337%
    assert shield.memory_gain_vs_baseline_pct > 300.0
    assert shield.shield_active is True


def test_compute_oom_shield_scaling_active_cores_clamping() -> None:
    """Verify active cores input clamping to valid physical core range [1, physical_cores]."""
    host_mem = HostMemoryProfile(
        total_ram_bytes=17179869184,  # 16 GB
        available_ram_bytes=15032385536,
        free_ram_bytes=12884901888,
        swap_total_bytes=0,
        swap_free_bytes=0,
        effective_system_ram_bytes=17179869184,
        bounded_total_ram_bytes=17179869184,
        bounded_total_ram_mb=16384.0,
        bounded_total_ram_gb=16.0,
    )

    # Requesting 0 cores clamps to 1 core
    shield_zero = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=8, active_cores=0)
    assert shield_zero.active_job_cores == 1

    # Requesting 32 cores on an 8-core host clamps to 8 cores
    shield_over = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=8, active_cores=32)
    assert shield_over.active_job_cores == 8


# =============================================================================
# 5. MULTI-ENGINE BUDGET SYNTHESIZER TESTS
# =============================================================================


def test_build_engine_memory_budgets() -> None:
    """Verify synthesis of multi-engine memory directives and environment variables."""
    budgets = build_engine_memory_budgets(
        allocatable_ram_mb=57344,
        active_core_maxcore_mb=14336,
        active_cores=4,
    )

    # 1. ORCA
    orca = budgets["ORCA"]
    assert orca.engine == EngineTarget.ORCA
    assert orca.primary_directive_name == "%maxcore"
    assert orca.directive_value_formatted == "%maxcore 14336"
    assert orca.allocated_per_core_mb == 14336
    assert orca.env_var_name == "ORCA_MAXCORE"
    assert orca.env_var_value == "14336"

    # 2. PySCF
    pyscf = budgets["PYSCF"]
    assert pyscf.engine == EngineTarget.PYSCF
    assert pyscf.primary_directive_name == "max_memory"
    assert "57344" in pyscf.directive_value_formatted
    assert pyscf.env_var_name == "PYSCF_MAX_MEMORY"
    assert pyscf.env_var_value == "57344"

    # 3. xTB
    xtb = budgets["XTB"]
    assert xtb.engine == EngineTarget.XTB
    assert xtb.primary_directive_name == "--memory"
    assert xtb.directive_value_formatted == "--memory 57344m"
    assert xtb.env_var_name == "XTB_MAX_MEMORY"
    assert xtb.env_var_value == "57344"

    # 4. Gaussian
    gauss = budgets["GAUSSIAN"]
    assert gauss.engine == EngineTarget.GAUSSIAN
    assert gauss.primary_directive_name == "%mem"
    assert gauss.env_var_name == "GAUSS_MEMDEF"

    # 5. CFOUR
    cfour = budgets["CFOUR"]
    assert cfour.engine == EngineTarget.CFOUR
    assert cfour.primary_directive_name == "MEMORY_SIZE"

    # 6. MACE-Torch
    mace = budgets["MACE_TORCH"]
    assert mace.engine == EngineTarget.MACE_TORCH
    assert mace.env_var_name == "COCHEM_MACE_HOST_RAM_MB"

    # 7. OpenMPI
    mpi = budgets["OPENMPI"]
    assert mpi.engine == EngineTarget.OPENMPI


def test_generate_environment_injection_dict() -> None:
    """Verify comprehensive environment variable injection dictionary synthesis."""
    shield = OOMShieldScalingProfile(
        total_physical_cores=16,
        active_job_cores=4,
        bounded_total_ram_mb=65536.0,
        os_jupyter_reserve_mb=8192,
        reserve_ratio=0.125,
        allocatable_ram_mb=57344,
        allocatable_ram_gb=56.0,
        baseline_80pct_maxcore_mb=3276,
        active_core_maxcore_mb=14336,
        memory_gain_vs_baseline_pct=337.6,
        shield_active=True,
    )
    budgets = build_engine_memory_budgets(
        allocatable_ram_mb=57344,
        active_core_maxcore_mb=14336,
        active_cores=4,
    )

    env_dict = generate_environment_injection_dict(oom_shield=shield, budgets=budgets)

    assert "ORCA_MAXCORE" in env_dict
    assert env_dict["ORCA_MAXCORE"] == "14336"
    assert env_dict["PYSCF_MAX_MEMORY"] == "57344"
    assert env_dict["XTB_MAX_MEMORY"] == "57344"
    assert env_dict["COCHEM_MAXCORE_MB"] == "14336"
    assert env_dict["COCHEM_ALLOCATABLE_RAM_MB"] == "57344"
    assert env_dict["COCHEM_SAFETY_BUFFER_MB"] == "8192"
    assert env_dict["COCHEM_ACTIVE_CORES"] == "4"
    assert env_dict["COCHEM_TOTAL_RAM_MB"] == "65536"
    assert env_dict["COCHEM_OOM_SHIELD_STATUS"] == "ACTIVE"


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER & REGISTRY TESTS
# =============================================================================


def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify DependencyManager rolls back and unlinks tracked temp files on exception."""
    temp_target = tmp_path / "will_be_deleted.tmp"
    temp_target.write_text("ephemeral data", encoding="utf-8")

    assert temp_target.exists()

    with pytest.raises(RuntimeError):
        with DependencyManager() as dm:
            dm.track_temp_file(temp_target)
            raise RuntimeError("Simulated failure during execution")

    # Target should be cleaned up by rollback
    assert not temp_target.exists()


def test_dependency_manager_normal_exit(tmp_path: Path) -> None:
    """Verify DependencyManager retains files upon successful execution."""
    temp_target = tmp_path / "will_survive.tmp"
    temp_target.write_text("permanent data", encoding="utf-8")

    with DependencyManager() as dm:
        dm.track_temp_file(temp_target)
        # Normal exit without exception

    assert temp_target.exists()


def test_resolve_p11_registry_path_custom_and_default(tmp_path: Path) -> None:
    """Verify resolution of p11.json Golden Registry artifact destination path."""
    custom_dir = tmp_path / "custom_registry"
    p11_path = resolve_p11_registry_path(output_dir=custom_dir)
    assert p11_path.name == "p11.json"
    assert p11_path.parent == custom_dir.resolve()


# =============================================================================
# 7. INTEGRATION AUDIT RUNNER & CLI TESTS
# =============================================================================


def test_run_phase_11_audit_full_flow(tmp_path: Path) -> None:
    """Verify end-to-end execution of Phase 11 audit, state validation, and p11.json persistence."""
    output_dir = tmp_path / "artifacts" / "registry"

    report = run_phase_11_audit(
        output_dir=output_dir,
        active_cores=4,
        os_reserve_mb=None,
        dry_run=False,
    )

    assert report.phase_id == "cochem_setup_phase_11"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.oom_shield.shield_active is True
    assert report.oom_shield.active_job_cores >= 1
    assert report.oom_shield.allocatable_ram_mb > 0
    assert len(report.engine_budgets) >= 7
    assert len(report.injected_env_vars) >= 8

    # Verify p11.json exists on disk and parses cleanly with Pydantic
    p11_file = Path(report.artifact_path)
    assert p11_file.exists()
    raw_data = json.loads(p11_file.read_text(encoding="utf-8"))
    re_parsed_report = Phase11AuditReport.model_validate(raw_data)
    assert re_parsed_report.phase_id == "cochem_setup_phase_11"


def test_run_phase_11_audit_dry_run(tmp_path: Path) -> None:
    """Verify dry_run produces a valid report without writing p11.json to disk."""
    output_dir = tmp_path / "dry_run_registry"

    report = run_phase_11_audit(
        output_dir=output_dir,
        active_cores=2,
        dry_run=True,
    )

    assert report.phase_id == "cochem_setup_phase_11"
    p11_file = output_dir / "p11.json"
    assert not p11_file.exists()


def test_main_cli_execution_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI main entry point with --json and --dry-run flags."""
    out_dir = tmp_path / "cli_reg"
    exit_code = main(["--output-dir", str(out_dir), "--active-cores", "2", "--dry-run", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    parsed_json = json.loads(captured.out)
    assert parsed_json["phase_id"] == "cochem_setup_phase_11"
    assert "oom_shield" in parsed_json


def test_main_cli_execution_human_readable(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI main entry point human-readable summary output."""
    out_dir = tmp_path / "cli_reg_human"
    exit_code = main(["--output-dir", str(out_dir), "--active-cores", "4", "--dry-run"])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "COCHEM SETUP PHASE 11: MEMORY ROUTER & OOM SHIELD GATEKEEPER" in captured.out
    assert "OOM Shield Memory Partitioning Profile:" in captured.out
    assert "Multi-Engine Target Directives:" in captured.out


# =============================================================================
# 8. PHASE 2 AUDIT INGESTION & ZERO-SPOOF CGROUP V2 TESTS
# =============================================================================


def test_phase_2_audit_findings_model() -> None:
    """Verify Phase2AuditFindings model strict validation and field constraints."""
    findings = Phase2AuditFindings(
        loaded_from="/path/to/p2.json",
        status="PASSED",
        total_physical_ram_bytes=68719476736,
        effective_memory_bytes=68719476736,
        physical_cores=16,
        logical_cores=32,
        is_cgroup_constrained=False,
        gpu_available=True,
    )
    assert findings.status == "PASSED"
    assert findings.physical_cores == 16
    assert findings.gpu_available is True

    # Forbid extra fields
    with pytest.raises(ValidationError):
        Phase2AuditFindings(
            loaded_from="/path/to/p2.json",
            status="PASSED",
            total_physical_ram_bytes=68719476736,
            effective_memory_bytes=68719476736,
            physical_cores=16,
            logical_cores=32,
            unauthorized_key=123,
        )


def test_get_absolute_physical_ram_positive() -> None:
    """Verify get_absolute_physical_ram returns positive integer byte count."""
    ram = get_absolute_physical_ram()
    assert isinstance(ram, int)
    assert ram > 0


def test_load_phase_2_audit_findings_valid(tmp_path: Path) -> None:
    """Verify load_phase_2_audit_findings accurately parses authentic Phase 2 p2.json."""
    p2_file = tmp_path / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "timestamp_utc": "2026-08-22T00:00:00Z",
        "memory": {
            "total_bytes": 137438953472,  # 128 GB
            "available_bytes": 120000000000,
            "effective_memory_bytes": 137438953472,
            "is_cgroup_constrained": False,
        },
        "cpu": {
            "physical_cores": 32,
            "logical_cores": 64,
            "architecture": "x86_64",
        },
        "gpu": {
            "available": True,
            "devices": [],
        },
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    findings = load_phase_2_audit_findings(p2_path=p2_file)
    assert findings is not None
    assert findings.status == "PASSED"
    assert findings.total_physical_ram_bytes == 137438953472
    assert findings.physical_cores == 32
    assert findings.logical_cores == 64
    assert findings.gpu_available is True


def test_load_phase_2_audit_findings_corrupt_or_missing(tmp_path: Path) -> None:
    """Verify graceful None return on missing or corrupt p2.json files."""
    missing_path = tmp_path / "nonexistent_p2.json"
    assert load_phase_2_audit_findings(p2_path=missing_path) is None

    corrupt_path = tmp_path / "corrupt_p2.json"
    corrupt_path.write_text("{ corrupt json data ...", encoding="utf-8")
    assert load_phase_2_audit_findings(p2_path=corrupt_path) is None


def test_load_phase_2_audit_findings_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify load_phase_2_audit_findings discovers p2.json via COCHEM_REGISTRY_DIR."""
    reg_dir = tmp_path / "env_registry"
    reg_dir.mkdir()
    p2_file = reg_dir / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 68719476736, "effective_memory_bytes": 68719476736},
        "cpu": {"physical_cores": 8, "logical_cores": 16},
        "gpu": {"available": False},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")
    monkeypatch.setenv("COCHEM_REGISTRY_DIR", str(reg_dir))

    findings = load_phase_2_audit_findings()
    assert findings is not None
    assert findings.physical_cores == 8
    assert findings.total_physical_ram_bytes == 68719476736


def test_run_phase_11_audit_with_p2_path(tmp_path: Path) -> None:
    """Verify run_phase_11_audit integrates Phase 2 findings into report and baseline."""
    p2_file = tmp_path / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 68719476736, "effective_memory_bytes": 68719476736},
        "cpu": {"physical_cores": 16, "logical_cores": 32},
        "gpu": {"available": True},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    out_dir = tmp_path / "p11_out"
    report = run_phase_11_audit(output_dir=out_dir, p2_path=p2_file, active_cores=4)

    assert report.phase_2_findings is not None
    assert report.phase_2_findings.physical_cores == 16
    assert report.phase_2_findings.total_physical_ram_bytes == 68719476736
    assert report.oom_shield.total_physical_cores == 16
    assert report.oom_shield.active_job_cores == 4


def test_openmpi_dft_constraint_algorithm_exact_20pct_reservation() -> None:
    """
    Verify the constraint algorithm for OpenMPI and DFT maximum safe memory allocations:
      %maxcore = int(((Total_RAM_GB * 1024) * 0.80) / CPU_Physical_Cores)
    ensuring exactly 20% of system RAM is reserved strictly for OS/Jupyter UI.
    """
    # 64 GB RAM, 16 physical cores
    total_ram_gb = 64.0
    cpu_cores = 16
    expected_maxcore = int(((total_ram_gb * 1024.0) * 0.80) / cpu_cores)
    # int((65536 * 0.80) / 16) = int(52428.8 / 16) = 3276 MB

    host_mem = HostMemoryProfile(
        total_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        available_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        free_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        swap_total_bytes=0,
        swap_free_bytes=0,
        effective_system_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        bounded_total_ram_bytes=int(total_ram_gb * 1024 * 1024 * 1024),
        bounded_total_ram_mb=total_ram_gb * 1024.0,
        bounded_total_ram_gb=total_ram_gb,
    )

    shield = compute_oom_shield_scaling(host_mem=host_mem, total_physical_cores=cpu_cores)
    assert shield.baseline_80pct_maxcore_mb == expected_maxcore
    assert shield.baseline_80pct_maxcore_mb == 3276


def test_cgroup_v2_priority_over_psutil_hypervisor_anti_spoof(tmp_path: Path) -> None:
    """
    Verify cgroupv2 /sys/fs/cgroup/memory.max strictly bounds total RAM before psutil
    to prevent hypervisor spoofing and guarantee reliable scaling.
    """
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # Write a constrained 16 GB limit into cgroups v2 memory.max
    (cg_dir / "memory.max").write_text("17179869184\n", encoding="utf-8")

    host_mem, cg_prof = audit_host_memory(cgroup_root=cg_dir)
    assert cg_prof.cgroup_version == CGroupVersion.V2
    assert cg_prof.memory_max_bytes == 17179869184
    assert cg_prof.is_cgroup_constrained is True
    # Bounded total RAM must strictly respect cgroup ceiling
    assert host_mem.bounded_total_ram_bytes <= 17179869184
    assert host_mem.bounded_total_ram_gb <= 16.0


def test_main_cli_with_p2_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Verify CLI --p2-path parameter propagates to JSON output report."""
    p2_file = tmp_path / "cli_p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "memory": {"total_bytes": 34359738368, "effective_memory_bytes": 34359738368},
        "cpu": {"physical_cores": 8, "logical_cores": 16},
        "gpu": {"available": False},
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    out_dir = tmp_path / "cli_p2_reg"
    exit_code = main(["--output-dir", str(out_dir), "--p2-path", str(p2_file), "--dry-run", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    parsed_json = json.loads(captured.out)
    assert parsed_json["phase_2_findings"] is not None
    assert parsed_json["phase_2_findings"]["physical_cores"] == 8

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.