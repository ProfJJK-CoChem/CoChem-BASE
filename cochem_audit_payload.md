Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part2_05c_orchestrator_phase_7_prompt.md.
Original prompt:
﻿# CoChem-BASE Coding Prompt: cochem_setup_phase_7.py

## 1. Goal
Implement the file `cochem_setup_phase_7.py` based on the Software Requirements Specification (SRS) - CoChem-BASE (Document 2 Part 2).

## 2. Target Filepath
`D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_7.py`

## 3. Context & Ecosystem Role
HPC Env Injection

## 4. Deliverable Functions
Handles HPC Slurm/PBS Environment Variable Injection (e.g. `SLURM_MEM_PER_NODE`, `$SLURM_TMPDIR`).

## 5. Strict Constraints & Anti-Spoofing
- **Workspace Rules:** Strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.
- **No Mocks or Stubs:** Do NOT use placeholders, mock data, or stub logic (e.g., `pass`, `NotImplementedError`, or fake hardcoded values).
- **Fully Functional:** The code must be production-ready and fully implement the deliverables.
- **Error Handling:** Must degrade gracefully and handle errors according to the SRS without crashing silently.
- **Autonomy:** Do not delegate to the user. Execute the complete implementation.
- **Verification:** Ensure your code runs in the physical constraints as defined.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\__init__.py ---
"""
CoChem Orchestrator Package.
Provides multi-phase environment gatekeeping, initialization, and deployment pipeline.
"""

from __future__ import annotations

from orchestrator.cochem_setup_phase_1 import (
    DependencyManager,
    FilesystemAudit,
    KernelLimitsAudit,
    OSProfile,
    Phase1AuditReport,
    PhaseStatus,
    ToolchainItem,
    WSL9PMountError,
    audit_filesystem,
    audit_kernel_limits,
    audit_toolchains,
    interrogate_os,
    run_phase_1_audit,
)
from orchestrator.cochem_setup_phase_1 import (
    main as phase_1_main,
)
from orchestrator.cochem_setup_phase_2 import (
    CPUAudit,
    GPUDevice,
    GPUProfile,
    IEEE754PrecisionAudit,
    MemoryAudit,
    Phase2AuditError,
    Phase2AuditReport,
    audit_cpu,
    audit_gpus,
    audit_memory,
    parse_cgroup_cpu_quota,
    parse_cgroup_memory_limit,
    probe_amd_gpus,
    probe_intel_gpus,
    probe_nvidia_gpus,
    resolve_p2_registry_path,
    run_phase_2_audit,
    verify_ieee754_subnormal_precision,
)
from orchestrator.cochem_setup_phase_2 import (
    main as phase_2_main,
)
from orchestrator.cochem_setup_phase_3 import (
    BinaryEngineItem,
    ContainerAudit,
    EngineStatus,
    EngineTrack,
    EngineTrackSummary,
    EnvironmentFingerprint,
    Phase3AuditError,
    Phase3AuditReport,
    audit_all_engines,
    audit_container_sifs,
    audit_single_binary,
    build_track_summaries,
    compute_environment_fingerprint,
    resolve_p3_registry_path,
    run_phase_3_audit,
)
from orchestrator.cochem_setup_phase_3 import (
    main as phase_3_main,
)
from orchestrator.cochem_setup_phase_4 import (
    DynamicVersionWalkingResult,
    DynamicVersionWalkStep,
    IPCSecurityAudit,
    ManifestFilterAudit,
    MendeleevMassRecord,
    Phase4AuditError,
    Phase4AuditReport,
    SiloAuditItem,
    SiloConfig,
    SiloProvisioningError,
    SiloStatus,
    SiloType,
    VersionWalkingError,
    audit_ipc_and_mps_security,
    audit_micro_silos,
    enforce_python_version,
    execute_dynamic_version_walking,
    filter_silos_by_manifest,
    get_default_silo_configs,
    get_native_memory_env_vars,
    get_native_stack_flags,
    get_silo_executable_path,
    inject_silo_stack_and_env_flags,
    load_deployment_manifest,
    provision_micro_silo,
    resolve_p4_registry_path,
    resolve_silo_base_directory,
    run_phase_4_audit,
    scan_local_fallback_binaries,
    verify_mendeleev_authority,
)
from orchestrator.cochem_setup_phase_4 import (
    main as phase_4_main,
)
from orchestrator.cochem_setup_phase_5 import (
    GPUDeviceVRAM,
    MPSControlError,
    MPSDaemonAudit,
    MPSStatus,
    Phase5AuditError,
    Phase5AuditReport,
    VRAMAllocationError,
    VRAMBudgetReport,
    build_pinned_memory_limit_string,
    calculate_vram_budget,
    configure_mps_device_limit,
    discover_mps_binaries,
    enforce_socket_directory_permissions,
    generate_mps_activation_scripts,
    get_current_username,
    inject_mps_environment_variables,
    probe_gpu_devices_vram,
    probe_mps_daemon_status,
    resolve_mps_log_directory,
    resolve_mps_pipe_directory,
    resolve_p5_registry_path,
    run_phase_5_audit,
    start_mps_daemon,
    stop_mps_daemon,
)
from orchestrator.cochem_setup_phase_5 import (
    main as phase_5_main,
)
from orchestrator.cochem_setup_phase_6 import (
    ArchiveSchemaAudit,
    DatabaseBackend,
    DatabaseProvisioningError,
    DiskQuotaError,
    HDF5FilterProfile,
    LockingVerificationError,
    Phase6AuditError,
    Phase6AuditReport,
    StorageMode,
    StoragePathProfile,
    SWMRRuntimeAudit,
    enforce_storage_permissions,
    probe_swmr_locking_capabilities,
    provision_archive_pes_db,
    provision_runtime_active_db,
    resolve_databases_directory,
    resolve_p6_registry_path,
    resolve_scratch_directory,
    run_phase_6_audit,
    verify_disk_quota,
)
from orchestrator.cochem_setup_phase_6 import (
    main as phase_6_main,
)
from orchestrator.cochem_setup_phase_7 import (
    HPCMemoryParseError,
    HPCMemoryProfile,
    HPCSchedulerType,
    HPCScratchAllocationError,
    HPCScratchProfile,
    HPCThreadAffinityProfile,
    HPCTopologyError,
    HPCTopologyProfile,
    Phase7AuditError,
    Phase7AuditReport,
    compute_thread_affinity_profile,
    detect_hpc_scheduler,
    generate_environment_injection_dict,
    parse_hpc_memory_limit,
    parse_slurm_nodelist,
    parse_slurm_tasks_per_node,
    resolve_hpc_scratch_directory,
    resolve_p7_registry_path,
    run_phase_7_audit,
)
from orchestrator.cochem_setup_phase_7 import (
    main as phase_7_main,
)

__all__ = [
    "ArchiveSchemaAudit",
    "BinaryEngineItem",
    "CPUAudit",
    "ContainerAudit",
    "DatabaseBackend",
    "DatabaseProvisioningError",
    "DependencyManager",
    "DiskQuotaError",
    "DynamicVersionWalkStep",
    "DynamicVersionWalkingResult",
    "EngineStatus",
    "EngineTrack",
    "EngineTrackSummary",
    "EnvironmentFingerprint",
    "FilesystemAudit",
    "GPUDevice",
    "GPUDeviceVRAM",
    "GPUProfile",
    "HDF5FilterProfile",
    "HPCMemoryParseError",
    "HPCMemoryProfile",
    "HPCSchedulerType",
    "HPCScratchAllocationError",
    "HPCScratchProfile",
    "HPCThreadAffinityProfile",
    "HPCTopologyError",
    "HPCTopologyProfile",
    "IEEE754PrecisionAudit",
    "IPCSecurityAudit",
    "KernelLimitsAudit",
    "LockingVerificationError",
    "MPSControlError",
    "MPSDaemonAudit",
    "MPSStatus",
    "ManifestFilterAudit",
    "MemoryAudit",
    "MendeleevMassRecord",
    "OSProfile",
    "Phase1AuditReport",
    "Phase2AuditError",
    "Phase2AuditReport",
    "Phase3AuditError",
    "Phase3AuditReport",
    "Phase4AuditError",
    "Phase4AuditReport",
    "Phase5AuditError",
    "Phase5AuditReport",
    "Phase6AuditError",
    "Phase6AuditReport",
    "Phase7AuditError",
    "Phase7AuditReport",
    "PhaseStatus",
    "SiloAuditItem",
    "SiloConfig",
    "SiloProvisioningError",
    "SiloStatus",
    "SiloType",
    "StorageMode",
    "StoragePathProfile",
    "SWMRRuntimeAudit",
    "ToolchainItem",
    "VRAMAllocationError",
    "VRAMBudgetReport",
    "VersionWalkingError",
    "WSL9PMountError",
    "audit_all_engines",
    "audit_container_sifs",
    "audit_cpu",
    "audit_filesystem",
    "audit_gpus",
    "audit_ipc_and_mps_security",
    "audit_kernel_limits",
    "audit_memory",
    "audit_micro_silos",
    "audit_single_binary",
    "audit_toolchains",
    "build_pinned_memory_limit_string",
    "build_track_summaries",
    "calculate_vram_budget",
    "compute_environment_fingerprint",
    "compute_thread_affinity_profile",
    "configure_mps_device_limit",
    "detect_hpc_scheduler",
    "discover_mps_binaries",
    "enforce_python_version",
    "enforce_socket_directory_permissions",
    "enforce_storage_permissions",
    "execute_dynamic_version_walking",
    "filter_silos_by_manifest",
    "generate_environment_injection_dict",
    "generate_mps_activation_scripts",
    "get_current_username",
    "get_default_silo_configs",
    "get_native_memory_env_vars",
    "get_native_stack_flags",
    "get_silo_executable_path",
    "inject_mps_environment_variables",
    "inject_silo_stack_and_env_flags",
    "interrogate_os",
    "load_deployment_manifest",
    "parse_cgroup_cpu_quota",
    "parse_cgroup_memory_limit",
    "parse_hpc_memory_limit",
    "parse_slurm_nodelist",
    "parse_slurm_tasks_per_node",
    "phase_1_main",
    "phase_2_main",
    "phase_3_main",
    "phase_4_main",
    "phase_5_main",
    "phase_6_main",
    "phase_7_main",
    "probe_amd_gpus",
    "probe_gpu_devices_vram",
    "probe_intel_gpus",
    "probe_mps_daemon_status",
    "probe_nvidia_gpus",
    "probe_swmr_locking_capabilities",
    "provision_archive_pes_db",
    "provision_micro_silo",
    "provision_runtime_active_db",
    "resolve_databases_directory",
    "resolve_hpc_scratch_directory",
    "resolve_mps_log_directory",
    "resolve_mps_pipe_directory",
    "resolve_p2_registry_path",
    "resolve_p3_registry_path",
    "resolve_p4_registry_path",
    "resolve_p5_registry_path",
    "resolve_p6_registry_path",
    "resolve_p7_registry_path",
    "resolve_scratch_directory",
    "resolve_silo_base_directory",
    "run_phase_1_audit",
    "run_phase_2_audit",
    "run_phase_3_audit",
    "run_phase_4_audit",
    "run_phase_5_audit",
    "run_phase_6_audit",
    "run_phase_7_audit",
    "scan_local_fallback_binaries",
    "start_mps_daemon",
    "stop_mps_daemon",
    "verify_disk_quota",
    "verify_ieee754_subnormal_precision",
    "verify_mendeleev_authority",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_7.py ---
"""
CoChem Setup Phase 7: HPC Environment Variable Injection & Execution Topology Gatekeeper.
Production-grade, zero-mock gatekeeping engine for HPC cluster scheduler detection (Slurm, PBS,
LSF, SGE, Local Standalone), bracketed node range expansion (e.g. node[01-03,05]), multiplier
task distribution parsing (e.g. 4(x2),2), memory allocation resolving (SLURM_MEM_PER_NODE,
SLURM_MEM_PER_CPU, cgroups v1/v2 limits, physical RAM fallback), hierarchical scratch mapping
($SLURM_TMPDIR, $TMPDIR, $SCRATCH, %TEMP%), thread & process core affinity binding computation
(OMP, MKL, OpenBLAS, BLIS, KMP_AFFINITY), and transactional atomic persistence into the
Golden Registry (p7.json).

SRS Document 2 Part 2 (Section 3.7), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase7AuditError(RuntimeError):
    """Raised when critical phase 7 HPC environment audit or setup fails fatally."""


class HPCTopologyError(RuntimeError):
    """Raised when node list, task allocation, or CPU topology parsing fails."""


class HPCMemoryParseError(RuntimeError):
    """Raised when memory specification string or cgroup limit fails to parse."""


class HPCScratchAllocationError(RuntimeError):
    """Raised when scratch directory allocation, validation, or permission fails."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class HPCSchedulerType(str, Enum):
    """Supported High-Performance Computing workload scheduler classification."""

    SLURM = "SLURM"
    PBS = "PBS"
    LSF = "LSF"
    SGE = "SGE"
    LOCAL_STANDALONE = "LOCAL_STANDALONE"


class HPCTopologyProfile(BaseModel):
    """Parsed multi-node and multi-core execution topology profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scheduler: HPCSchedulerType = Field(..., description="Active HPC workload scheduler")
    job_id: Optional[str] = Field(default=None, description="HPC Cluster Job ID if scheduled")
    num_nodes: int = Field(..., ge=1, description="Total number of physical or virtual nodes allocated")
    node_list: List[str] = Field(default_factory=list, description="List of unique hostnames in allocation")
    tasks_per_node: List[int] = Field(
        default_factory=list, description="Number of parallel worker tasks/processes mapped to each node"
    )
    total_tasks: int = Field(..., ge=1, description="Total parallel MPI/worker tasks across all nodes")
    cpus_per_task: int = Field(
        default=1, ge=1, description="Number of OpenMP/threading CPU cores assigned per worker task"
    )
    cpus_on_node: int = Field(
        default=1, ge=1, description="Total CPU cores available on primary execution node"
    )
    is_heterogeneous: bool = Field(
        default=False, description="Whether task distribution across nodes is non-uniform"
    )


class HPCMemoryProfile(BaseModel):
    """Parsed HPC memory allocation and cgroup threshold profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    mem_per_node_mb: Optional[float] = Field(
        default=None, ge=0.0, description="Memory limit allocated per node in Megabytes"
    )
    mem_per_cpu_mb: Optional[float] = Field(
        default=None, ge=0.0, description="Memory limit allocated per CPU core in Megabytes"
    )
    cgroup_limit_bytes: Optional[int] = Field(
        default=None, ge=0, description="Cgroup v1/v2 memory limit in bytes if containerized"
    )
    physical_ram_bytes: int = Field(
        ..., ge=0, description="Total host physical RAM in bytes"
    )
    effective_usable_memory_mb: float = Field(
        ..., ge=0.0, description="Effective usable memory limit in Megabytes for driver budgeting"
    )
    source: str = Field(
        ..., description="Resolution source (e.g. SLURM_MEM_PER_NODE, CGROUP, PHYSICAL_RAM)"
    )


class HPCScratchProfile(BaseModel):
    """Hierarchically resolved fast ephemeral scratch directory profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scratch_directory: str = Field(..., description="Resolved absolute filesystem path to scratch directory")
    is_accessible: bool = Field(default=True, description="Whether directory exists and is accessible")
    is_writable: bool = Field(default=True, description="Whether directory is verified writable")
    free_disk_space_gb: float = Field(
        default=0.0, ge=0.0, description="Available free disk space on scratch filesystem in GB"
    )
    source_variable: str = Field(
        ..., description="Environment variable source (e.g. SLURM_TMPDIR, TMPDIR, SCRATCH, TEMP, FALLBACK)"
    )


class HPCThreadAffinityProfile(BaseModel):
    """OpenMP, Intel MKL, OpenBLAS, BLIS, and process core binding profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    omp_num_threads: int = Field(..., ge=1, description="OMP_NUM_THREADS core allocation count")
    mkl_num_threads: int = Field(..., ge=1, description="MKL_NUM_THREADS linear algebra thread count")
    openblas_num_threads: int = Field(..., ge=1, description="OPENBLAS_NUM_THREADS thread count")
    blis_num_threads: int = Field(default=1, ge=1, description="BLIS_NUM_THREADS thread count")
    omp_places: str = Field(default="cores", description="OMP_PLACES thread placement hardware policy")
    omp_proc_bind: str = Field(default="close", description="OMP_PROC_BIND thread binding policy")
    kmp_affinity: str = Field(
        default="granularity=fine,compact,1,0", description="Intel KMP_AFFINITY configuration string"
    )
    kmp_blocktime: int = Field(
        default=0, ge=0, description="Intel KMP_BLOCKTIME delay in milliseconds to eliminate CPU spinning"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict, description="Dictionary of thread binding environment variable key-value pairs"
    )


class Phase7AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 7."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(default="cochem_setup_phase_7", description="Unique setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 7")
    scheduler_detected: HPCSchedulerType = Field(..., description="Detected cluster workload scheduler")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of execution")
    artifact_path: str = Field(..., description="Absolute path to generated p7.json Golden Registry artifact")
    topology: HPCTopologyProfile = Field(..., description="Execution node and core allocation topology")
    memory: HPCMemoryProfile = Field(..., description="Memory ceiling and allocation profile")
    scratch: HPCScratchProfile = Field(..., description="Resolved ephemeral scratch space profile")
    affinity: HPCThreadAffinityProfile = Field(..., description="Thread and core affinity bindings profile")
    injected_env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Complete environment injection dictionary for subprocess execution"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or recoverable error messages")


# =============================================================================
# 3. HPC SCHEDULER DETECTION ENGINE
# =============================================================================


def detect_hpc_scheduler(env: Optional[Dict[str, str]] = None) -> HPCSchedulerType:
    """
    Detect the active High-Performance Computing workload scheduler from the environment.
    Evaluates Slurm, PBS, LSF, SGE, explicit CoChem scheduler override, or Local Standalone.
    """
    target_env = os.environ if env is None else env

    # 1. Explicit CoChem override
    if "COCHEM_HPC_SCHEDULER" in target_env:
        val = target_env["COCHEM_HPC_SCHEDULER"].strip().upper()
        if val in HPCSchedulerType.__members__:
            return HPCSchedulerType[val]
        for member in HPCSchedulerType:
            if member.value == val:
                return member

    # 2. Slurm Workload Manager detection
    slurm_vars = [
        "SLURM_JOB_ID",
        "SLURM_JOBID",
        "SLURM_NNODES",
        "SLURM_NODELIST",
        "SLURM_JOB_NODELIST",
        "SLURM_TASKS_PER_NODE",
    ]
    if any(k in target_env and target_env[k].strip() for k in slurm_vars):
        return HPCSchedulerType.SLURM

    # 3. PBS Pro / OpenPBS / Torque detection
    pbs_vars = ["PBS_JOBID", "PBS_NODEFILE", "PBS_NUM_NODES", "PBS_ENVIRONMENT"]
    if any(k in target_env and target_env[k].strip() for k in pbs_vars):
        return HPCSchedulerType.PBS

    # 4. IBM Spectrum LSF detection
    lsf_vars = ["LSB_JOBID", "LSB_HOSTS", "LSB_MCPU_HOSTS", "LSB_DJOB_NUMPROC"]
    if any(k in target_env and target_env[k].strip() for k in lsf_vars):
        return HPCSchedulerType.LSF

    # 5. Sun Grid Engine (SGE / UGE / Son of Grid Engine) detection
    sge_vars = ["PE_HOSTFILE", "SGE_CELL", "SGE_CLUSTER_NAME"]
    if any(k in target_env and target_env[k].strip() for k in sge_vars):
        return HPCSchedulerType.SGE
    if "JOB_ID" in target_env and ("NSLOTS" in target_env or "NHOSTS" in target_env):
        return HPCSchedulerType.SGE

    return HPCSchedulerType.LOCAL_STANDALONE


# =============================================================================
# 4. TOPOLOGY PARSING: NODES & TASK MULTIPLIERS
# =============================================================================


def _split_top_level_commas(s: str) -> List[str]:
    """Split string by commas only outside square brackets [...]."""
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for char in s:
        if char == "[":
            depth += 1
            current.append(char)
        elif char == "]":
            if depth > 0:
                depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    if current:
        part = "".join(current).strip()
        if part:
            parts.append(part)
    return parts


def _expand_single_node_spec(spec: str) -> List[str]:
    """
    Expand a single bracketed or plain node specification, supporting nested or multiple brackets.
    Examples:
    'node[01-03,05]' -> ['node01', 'node02', 'node03', 'node05']
    'c[1-2]n[3-4]' -> ['c1n3', 'c1n4', 'c2n3', 'c2n4']
    'head01' -> ['head01']
    """
    if "[" not in spec:
        return [spec]

    # Find the first bracket pair: prefix[range_spec]suffix
    m = re.search(r"^(.*?)\[(.*?)\](.*)$", spec)
    if not m:
        raise HPCTopologyError(f"Malformed node expression: '{spec}'")

    prefix, inner, suffix = m.group(1), m.group(2), m.group(3)
    inner_items = inner.split(",")
    expanded_current: List[str] = []

    for item in inner_items:
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            range_parts = item.split("-")
            if len(range_parts) != 2:
                raise HPCTopologyError(f"Invalid range in node expression: '{item}' in '{spec}'")
            start_str, end_str = range_parts[0].strip(), range_parts[1].strip()
            if not start_str.isdigit() or not end_str.isdigit():
                raise HPCTopologyError(f"Non-numeric range in node expression: '{item}' in '{spec}'")

            start_val, end_val = int(start_str), int(end_str)
            if start_val > end_val:
                raise HPCTopologyError(
                    f"Descending range not allowed in node expression: '{item}' in '{spec}'"
                )
            width = len(start_str)
            for num in range(start_val, end_val + 1):
                expanded_current.append(f"{prefix}{num:0{width}d}")
        else:
            expanded_current.append(f"{prefix}{item}")

    # Recursively expand with suffix in case of multiple bracket groups (e.g. c[1-2]n[3-4])
    result: List[str] = []
    for base in expanded_current:
        for full in _expand_single_node_spec(base + suffix):
            result.append(full)

    return result


def parse_slurm_nodelist(nodelist_str: str) -> List[str]:
    """
    Parse and expand a Slurm nodelist string into an explicit list of hostnames.
    Handles bracketed ranges, comma-separated lists, padding, and multi-bracket expressions.
    Examples:
    - 'node[01-03,05]' -> ['node01', 'node02', 'node03', 'node05']
    - 'node[01-02],gpu[05-06],head01' -> ['node01', 'node02', 'gpu05', 'gpu06', 'head01']
    """
    raw = nodelist_str.strip()
    if not raw:
        return []

    # Check matching brackets
    if raw.count("[") != raw.count("]"):
        raise HPCTopologyError(f"Mismatched brackets in Slurm nodelist: '{nodelist_str}'")

    top_level_segments = _split_top_level_commas(raw)
    nodes: List[str] = []
    for segment in top_level_segments:
        nodes.extend(_expand_single_node_spec(segment))

    return nodes


def parse_slurm_tasks_per_node(tasks_str: str, num_nodes: Optional[int] = None) -> List[int]:
    """
    Parse a Slurm SLURM_TASKS_PER_NODE string containing multipliers into an integer list.
    Examples:
    - '4(x2),2' -> [4, 4, 2]
    - '8(x3),4(x2),2' -> [8, 8, 8, 4, 4, 2]
    - '16' with num_nodes=3 -> [16, 16, 16]
    - '4,4,2' -> [4, 4, 2]
    """
    raw = tasks_str.strip()
    if not raw:
        raise HPCTopologyError("Empty SLURM_TASKS_PER_NODE string provided")

    segments = raw.split(",")
    result: List[int] = []

    pattern = re.compile(r"^\s*(\d+)(?:\s*\(\s*x\s*(\d+)\s*\))?\s*$")
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        m = pattern.match(seg)
        if not m:
            raise HPCTopologyError(f"Invalid tasks-per-node expression: '{seg}' in '{tasks_str}'")

        val = int(m.group(1))
        multiplier = int(m.group(2)) if m.group(2) else 1
        result.extend([val] * multiplier)

    if not result:
        raise HPCTopologyError(f"No valid tasks parsed from: '{tasks_str}'")

    # If a single task number was specified (e.g. '16') without multiplier but num_nodes > 1
    if len(result) == 1 and num_nodes is not None and num_nodes > 1 and "(x" not in raw:
        result = [result[0]] * num_nodes

    return result


def parse_slurm_topology(env: Dict[str, str]) -> HPCTopologyProfile:
    """Parse complete multi-node execution topology from Slurm environment variables."""
    job_id = env.get("SLURM_JOB_ID") or env.get("SLURM_JOBID")
    nodelist_raw = env.get("SLURM_NODELIST") or env.get("SLURM_JOB_NODELIST", "")
    node_list = parse_slurm_nodelist(nodelist_raw)

    num_nodes_env = env.get("SLURM_NNODES") or env.get("SLURM_STEP_NUM_NODES")
    num_nodes = int(num_nodes_env) if num_nodes_env and num_nodes_env.isdigit() else len(node_list)
    if num_nodes < 1:
        num_nodes = 1

    if not node_list:
        node_list = [f"node{i+1:02d}" for i in range(num_nodes)]

    tasks_raw = env.get("SLURM_TASKS_PER_NODE", "")
    if tasks_raw:
        tasks_per_node = parse_slurm_tasks_per_node(tasks_raw, num_nodes=num_nodes)
    else:
        ntasks_env = env.get("SLURM_NTASKS")
        if ntasks_env and ntasks_env.isdigit():
            ntasks = int(ntasks_env)
            base_t = max(1, ntasks // num_nodes)
            tasks_per_node = [base_t] * num_nodes
        else:
            tasks_per_node = [1] * num_nodes

    cpus_per_task_env = env.get("SLURM_CPUS_PER_TASK")
    cpus_per_task = (
        int(cpus_per_task_env) if cpus_per_task_env and cpus_per_task_env.isdigit() else 1
    )

    cpus_on_node_env = env.get("SLURM_CPUS_ON_NODE")
    cpus_on_node = (
        int(cpus_on_node_env)
        if cpus_on_node_env and cpus_on_node_env.isdigit()
        else (os.cpu_count() or 1)
    )

    total_tasks = sum(tasks_per_node)
    is_heterogeneous = len(set(tasks_per_node)) > 1

    return HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id=job_id,
        num_nodes=num_nodes,
        node_list=node_list,
        tasks_per_node=tasks_per_node,
        total_tasks=total_tasks,
        cpus_per_task=cpus_per_task,
        cpus_on_node=cpus_on_node,
        is_heterogeneous=is_heterogeneous,
    )


def parse_pbs_topology(env: Dict[str, str]) -> HPCTopologyProfile:
    """Parse complete multi-node execution topology from PBS environment variables."""
    job_id = env.get("PBS_JOBID")
    nodefile = env.get("PBS_NODEFILE")

    node_list: List[str] = []
    tasks_per_node: List[int] = []

    if nodefile and Path(nodefile).exists():
        raw_lines = [
            line.strip()
            for line in Path(nodefile).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # Preserve discovery order of unique nodes
        seen: List[str] = []
        for line in raw_lines:
            if line not in seen:
                seen.append(line)
        node_list = seen
        tasks_per_node = [raw_lines.count(n) for n in node_list]
        num_nodes = len(node_list)
    else:
        num_nodes_env = env.get("PBS_NUM_NODES")
        num_nodes = int(num_nodes_env) if num_nodes_env and num_nodes_env.isdigit() else 1
        ppn_env = env.get("PBS_NUM_PPN")
        ppn = int(ppn_env) if ppn_env and ppn_env.isdigit() else 1
        node_list = [f"pbs_node{i+1:02d}" for i in range(num_nodes)]
        tasks_per_node = [ppn] * num_nodes

    total_tasks = sum(tasks_per_node) if tasks_per_node else 1
    cpus_on_node = tasks_per_node[0] if tasks_per_node else (os.cpu_count() or 1)
    is_heterogeneous = len(set(tasks_per_node)) > 1

    return HPCTopologyProfile(
        scheduler=HPCSchedulerType.PBS,
        job_id=job_id,
        num_nodes=num_nodes,
        node_list=node_list,
        tasks_per_node=tasks_per_node,
        total_tasks=total_tasks,
        cpus_per_task=1,
        cpus_on_node=cpus_on_node,
        is_heterogeneous=is_heterogeneous,
    )


def parse_lsf_topology(env: Dict[str, str]) -> HPCTopologyProfile:
    """Parse complete multi-node execution topology from LSF environment variables."""
    job_id = env.get("LSB_JOBID")
    hosts_str = env.get("LSB_HOSTS", "")

    node_list: List[str] = []
    tasks_per_node: List[int] = []

    if hosts_str:
        hosts = hosts_str.split()
        seen: List[str] = []
        for h in hosts:
            if h not in seen:
                seen.append(h)
        node_list = seen
        tasks_per_node = [hosts.count(n) for n in node_list]
        num_nodes = len(node_list)
    else:
        num_nodes = 1
        node_list = [platform.node() or "localhost"]
        djob_num = env.get("LSB_DJOB_NUMPROC")
        t = int(djob_num) if djob_num and djob_num.isdigit() else 1
        tasks_per_node = [t]

    total_tasks = sum(tasks_per_node)
    cpus_on_node = tasks_per_node[0] if tasks_per_node else (os.cpu_count() or 1)
    is_heterogeneous = len(set(tasks_per_node)) > 1

    return HPCTopologyProfile(
        scheduler=HPCSchedulerType.LSF,
        job_id=job_id,
        num_nodes=num_nodes,
        node_list=node_list,
        tasks_per_node=tasks_per_node,
        total_tasks=total_tasks,
        cpus_per_task=1,
        cpus_on_node=cpus_on_node,
        is_heterogeneous=is_heterogeneous,
    )


def parse_sge_topology(env: Dict[str, str]) -> HPCTopologyProfile:
    """Parse complete multi-node execution topology from SGE environment variables."""
    job_id = env.get("JOB_ID")
    pe_hostfile = env.get("PE_HOSTFILE")

    node_list: List[str] = []
    tasks_per_node: List[int] = []

    if pe_hostfile and Path(pe_hostfile).exists():
        # SGE PE_HOSTFILE format: <hostname> <slots> <queue> <arch>
        raw_lines = [
            line.strip().split()
            for line in Path(pe_hostfile).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        node_list = [parts[0] for parts in raw_lines]
        tasks_per_node = [int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1 for parts in raw_lines]
        num_nodes = len(node_list)
    else:
        nhosts_env = env.get("NHOSTS")
        num_nodes = int(nhosts_env) if nhosts_env and nhosts_env.isdigit() else 1
        nslots_env = env.get("NSLOTS")
        nslots = int(nslots_env) if nslots_env and nslots_env.isdigit() else 1
        node_list = [f"sge_node{i+1:02d}" for i in range(num_nodes)]
        tasks_per_node = [max(1, nslots // num_nodes)] * num_nodes

    total_tasks = sum(tasks_per_node)
    cpus_on_node = tasks_per_node[0] if tasks_per_node else (os.cpu_count() or 1)
    is_heterogeneous = len(set(tasks_per_node)) > 1

    return HPCTopologyProfile(
        scheduler=HPCSchedulerType.SGE,
        job_id=job_id,
        num_nodes=num_nodes,
        node_list=node_list,
        tasks_per_node=tasks_per_node,
        total_tasks=total_tasks,
        cpus_per_task=1,
        cpus_on_node=cpus_on_node,
        is_heterogeneous=is_heterogeneous,
    )


def parse_standalone_topology(env: Dict[str, str]) -> HPCTopologyProfile:
    """Parse local standalone workstation/server topology."""
    host_cpus = os.cpu_count() or 1
    return HPCTopologyProfile(
        scheduler=HPCSchedulerType.LOCAL_STANDALONE,
        job_id=None,
        num_nodes=1,
        node_list=[platform.node() or "localhost"],
        tasks_per_node=[1],
        total_tasks=1,
        cpus_per_task=host_cpus,
        cpus_on_node=host_cpus,
        is_heterogeneous=False,
    )


def parse_topology(env: Optional[Dict[str, str]] = None) -> HPCTopologyProfile:
    """Dispatch topology resolution based on detected HPC workload scheduler."""
    target_env = os.environ if env is None else env
    scheduler = detect_hpc_scheduler(target_env)

    if scheduler == HPCSchedulerType.SLURM:
        return parse_slurm_topology(target_env)
    elif scheduler == HPCSchedulerType.PBS:
        return parse_pbs_topology(target_env)
    elif scheduler == HPCSchedulerType.LSF:
        return parse_lsf_topology(target_env)
    elif scheduler == HPCSchedulerType.SGE:
        return parse_sge_topology(target_env)
    else:
        return parse_standalone_topology(target_env)


# =============================================================================
# 5. MEMORY ALLOCATION & CGROUP LIMIT ENGINE
# =============================================================================

CGROUP_V1_UNLIMITED_THRESHOLD = 9223372036854770000


def parse_memory_string_to_mb(val_str: str) -> float:
    """
    Parse a memory string (e.g. '64000', '64000M', '64G', '128000MB', '128GB', '1T') into Megabytes.
    Default unit for bare integer (Slurm standard) is Megabytes (MB).
    """
    raw = val_str.strip()
    if not raw:
        raise HPCMemoryParseError("Empty memory specification string provided")

    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]*)$", raw)
    if not m:
        raise HPCMemoryParseError(f"Cannot parse memory specification: '{val_str}'")

    num_val = float(m.group(1))
    unit = m.group(2).upper()

    if unit in ("", "M", "MB", "MIB"):
        return num_val
    elif unit in ("G", "GB", "GIB"):
        return num_val * 1024.0
    elif unit in ("T", "TB", "TIB"):
        return num_val * 1024.0 * 1024.0
    elif unit in ("K", "KB", "KIB"):
        return num_val / 1024.0
    elif unit in ("B", "BYTES"):
        return num_val / (1024.0 * 1024.0)
    else:
        raise HPCMemoryParseError(f"Unknown memory unit: '{unit}' in '{val_str}'")


def get_physical_ram_bytes() -> int:
    """Detect total host physical RAM in bytes."""
    try:
        return psutil.virtual_memory().total
    except Exception:
        try:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except Exception:
            return 8 * 1024 * 1024 * 1024


def parse_cgroup_memory_limit(cgroup_root: Optional[Path] = None) -> Optional[int]:
    """
    Parse Linux cgroups v1 or v2 memory limit in bytes.
    Returns None if unlimited, unavailable, or non-Linux.
    """
    root = cgroup_root if cgroup_root is not None else Path("/")

    # 1. Cgroups v2: memory.max
    v2_candidates = [
        root / "sys" / "fs" / "cgroup" / "memory.max",
        root / "memory.max",
        root / "sys" / "fs" / "cgroup" / "memory" / "memory.max",
    ]
    for p in v2_candidates:
        if p.exists() and p.is_file():
            try:
                content = p.read_text(encoding="utf-8").strip()
                if content and content != "max":
                    limit = int(content)
                    if limit < CGROUP_V1_UNLIMITED_THRESHOLD:
                        return limit
            except Exception:
                pass

    # 2. Cgroups v1: memory.limit_in_bytes
    v1_candidates = [
        root / "sys" / "fs" / "cgroup" / "memory" / "memory.limit_in_bytes",
        root / "memory.limit_in_bytes",
    ]
    for p in v1_candidates:
        if p.exists() and p.is_file():
            try:
                content = p.read_text(encoding="utf-8").strip()
                if content:
                    limit = int(content)
                    if limit < CGROUP_V1_UNLIMITED_THRESHOLD:
                        return limit
            except Exception:
                pass

    return None


def parse_hpc_memory_limit(
    env: Optional[Dict[str, str]] = None,
    cgroup_root: Optional[Path] = None,
    tasks_per_node: Optional[List[int]] = None,
    cpus_per_task: int = 1,
) -> HPCMemoryProfile:
    """
    Resolve memory allocation envelope across Slurm/HPC variables, cgroup limits, and physical RAM.
    """
    target_env = os.environ if env is None else env
    physical_ram = get_physical_ram_bytes()
    physical_ram_mb = physical_ram / (1024.0 * 1024.0)

    # 1. Check SLURM_MEM_PER_NODE
    if "SLURM_MEM_PER_NODE" in target_env and target_env["SLURM_MEM_PER_NODE"].strip():
        raw_val = target_env["SLURM_MEM_PER_NODE"].strip()
        mem_mb = parse_memory_string_to_mb(raw_val)
        return HPCMemoryProfile(
            mem_per_node_mb=mem_mb,
            mem_per_cpu_mb=None,
            cgroup_limit_bytes=None,
            physical_ram_bytes=physical_ram,
            effective_usable_memory_mb=mem_mb,
            source="SLURM_MEM_PER_NODE",
        )

    # 2. Check SLURM_MEM_PER_CPU
    if "SLURM_MEM_PER_CPU" in target_env and target_env["SLURM_MEM_PER_CPU"].strip():
        raw_val = target_env["SLURM_MEM_PER_CPU"].strip()
        cpu_mb = parse_memory_string_to_mb(raw_val)
        tasks_on_node = tasks_per_node[0] if tasks_per_node else 1
        total_cpus = tasks_on_node * max(1, cpus_per_task)
        mem_mb = cpu_mb * total_cpus
        return HPCMemoryProfile(
            mem_per_node_mb=mem_mb,
            mem_per_cpu_mb=cpu_mb,
            cgroup_limit_bytes=None,
            physical_ram_bytes=physical_ram,
            effective_usable_memory_mb=mem_mb,
            source="SLURM_MEM_PER_CPU",
        )

    # 3. Check Cgroups v1/v2 container memory limit
    cgroup_bytes = parse_cgroup_memory_limit(cgroup_root)
    if cgroup_bytes is not None and cgroup_bytes > 0:
        cgroup_mb = cgroup_bytes / (1024.0 * 1024.0)
        effective_mb = min(physical_ram_mb, cgroup_mb)
        return HPCMemoryProfile(
            mem_per_node_mb=None,
            mem_per_cpu_mb=None,
            cgroup_limit_bytes=cgroup_bytes,
            physical_ram_bytes=physical_ram,
            effective_usable_memory_mb=round(effective_mb, 2),
            source="CGROUP",
        )

    # 4. Fallback to physical host RAM
    return HPCMemoryProfile(
        mem_per_node_mb=None,
        mem_per_cpu_mb=None,
        cgroup_limit_bytes=None,
        physical_ram_bytes=physical_ram,
        effective_usable_memory_mb=round(physical_ram_mb, 2),
        source="PHYSICAL_RAM",
    )


# =============================================================================
# 6. HIERARCHICAL SCRATCH DIRECTORY MAPPING
# =============================================================================


def resolve_hpc_scratch_directory(
    override: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> HPCScratchProfile:
    """
    Hierarchically resolve, scaffold, and validate the fast node-local Ephemeral Scratch directory.
    Resolution priority:
    1. Explicit override argument.
    2. $COCHEM_SCRATCH_DIR
    3. $SLURM_TMPDIR (HPC Slurm)
    4. $TMPDIR (PBS / LSF / SGE / Linux)
    5. $SCRATCH (Cluster shared or local scratch)
    6. %TEMP% / %TMP% (Windows NT)
    7. Fallback: Path.home() / "CoChem_Artifacts" / "Scratch"
    """
    target_env = os.environ if env is None else env
    source_var = "FALLBACK"
    target_path: Optional[Path] = None

    if override:
        target_path = Path(override).resolve()
        source_var = "OVERRIDE"
    elif "COCHEM_SCRATCH_DIR" in target_env and target_env["COCHEM_SCRATCH_DIR"].strip():
        target_path = Path(target_env["COCHEM_SCRATCH_DIR"]).resolve()
        source_var = "COCHEM_SCRATCH_DIR"
    elif "SLURM_TMPDIR" in target_env and target_env["SLURM_TMPDIR"].strip():
        target_path = Path(target_env["SLURM_TMPDIR"]).resolve()
        source_var = "SLURM_TMPDIR"
    elif "TMPDIR" in target_env and target_env["TMPDIR"].strip():
        target_path = Path(target_env["TMPDIR"]).resolve()
        source_var = "TMPDIR"
    elif "SCRATCH" in target_env and target_env["SCRATCH"].strip():
        scratch_base = Path(target_env["SCRATCH"]).resolve()
        target_path = scratch_base / "CoChem_Scratch"
        source_var = "SCRATCH"
    elif platform.system() == "Windows" and "TEMP" in target_env and target_env["TEMP"].strip():
        target_path = Path(target_env["TEMP"]).resolve()
        source_var = "TEMP"
    elif platform.system() == "Windows" and "TMP" in target_env and target_env["TMP"].strip():
        target_path = Path(target_env["TMP"]).resolve()
        source_var = "TMP"
    else:
        target_path = (Path.home() / "CoChem_Artifacts" / "Scratch").resolve()
        source_var = "FALLBACK"

    # Scaffolding and permission assertion
    target_path.mkdir(parents=True, exist_ok=True)

    is_accessible = target_path.exists() and target_path.is_dir()
    is_writable = False
    probe_file = target_path / f".cochem_scratch_probe_{uuid.uuid4().hex[:8]}"

    try:
        probe_file.write_text("cochem_scratch_probe", encoding="utf-8")
        is_writable = True
    except Exception:
        is_writable = False
    finally:
        if probe_file.exists():
            try:
                probe_file.unlink()
            except Exception:
                pass

    free_gb = 0.0
    try:
        usage = shutil.disk_usage(str(target_path))
        free_gb = round(usage.free / (1024.0 ** 3), 3)
    except Exception:
        free_gb = 0.0

    return HPCScratchProfile(
        scratch_directory=str(target_path),
        is_accessible=is_accessible,
        is_writable=is_writable,
        free_disk_space_gb=free_gb,
        source_variable=source_var,
    )


# =============================================================================
# 7. THREAD AFFINITY & CORE BINDINGS ENGINE
# =============================================================================


def compute_thread_affinity_profile(
    topology: HPCTopologyProfile,
    places_policy: str = "cores",
    proc_bind: str = "close",
) -> HPCThreadAffinityProfile:
    """
    Calculate optimal OpenMP, Intel MKL, OpenBLAS, BLIS, and process core affinity bindings
    based on the allocated CPU topology and task distribution.
    """
    cpus_per_task = topology.cpus_per_task
    tasks_on_node = topology.tasks_per_node[0] if topology.tasks_per_node else 1
    cpus_on_node = topology.cpus_on_node

    if cpus_per_task > 1:
        omp_threads = cpus_per_task
    elif cpus_on_node > 0 and tasks_on_node > 0:
        omp_threads = max(1, cpus_on_node // tasks_on_node)
    else:
        omp_threads = 1

    mkl_threads = omp_threads
    openblas_threads = omp_threads
    blis_threads = omp_threads

    valid_binds = ["close", "spread", "master", "compact", "scatter", "true", "false"]
    chosen_bind = proc_bind.lower() if proc_bind.lower() in valid_binds else "close"

    kmp_bind = chosen_bind
    if kmp_bind in ["close", "compact"]:
        kmp_affinity = "granularity=fine,compact,1,0"
    elif kmp_bind in ["spread", "scatter"]:
        kmp_affinity = "granularity=fine,scatter"
    else:
        kmp_affinity = "granularity=fine,compact,1,0"

    kmp_blocktime = 0

    env_vars: Dict[str, str] = {
        "OMP_NUM_THREADS": str(omp_threads),
        "MKL_NUM_THREADS": str(mkl_threads),
        "OPENBLAS_NUM_THREADS": str(openblas_threads),
        "BLIS_NUM_THREADS": str(blis_threads),
        "OMP_PLACES": places_policy,
        "OMP_PROC_BIND": chosen_bind,
        "KMP_AFFINITY": kmp_affinity,
        "KMP_BLOCKTIME": str(kmp_blocktime),
    }

    return HPCThreadAffinityProfile(
        omp_num_threads=omp_threads,
        mkl_num_threads=mkl_threads,
        openblas_num_threads=openblas_threads,
        blis_num_threads=blis_threads,
        omp_places=places_policy,
        omp_proc_bind=chosen_bind,
        kmp_affinity=kmp_affinity,
        kmp_blocktime=kmp_blocktime,
        environment_variables=env_vars,
    )


def generate_environment_injection_dict(
    topology: HPCTopologyProfile,
    memory: HPCMemoryProfile,
    scratch: HPCScratchProfile,
    affinity: HPCThreadAffinityProfile,
) -> Dict[str, str]:
    """
    Generate the complete production environment variable injection dictionary for subprocess execution.
    """
    injected: Dict[str, str] = dict(affinity.environment_variables)

    injected["COCHEM_SCRATCH_DIR"] = scratch.scratch_directory
    injected["COCHEM_HPC_SCHEDULER"] = topology.scheduler.value
    injected["COCHEM_NUM_NODES"] = str(topology.num_nodes)
    injected["COCHEM_TOTAL_TASKS"] = str(topology.total_tasks)
    injected["COCHEM_CPUS_PER_TASK"] = str(topology.cpus_per_task)
    injected["COCHEM_CPUS_ON_NODE"] = str(topology.cpus_on_node)
    injected["COCHEM_MEMORY_PER_NODE_MB"] = f"{memory.effective_usable_memory_mb:.1f}"

    if topology.job_id:
        injected["COCHEM_JOB_ID"] = str(topology.job_id)

    # Standard HPC scratch compatibility
    if topology.scheduler == HPCSchedulerType.SLURM:
        injected["SLURM_TMPDIR"] = scratch.scratch_directory
    else:
        injected["TMPDIR"] = scratch.scratch_directory

    return injected


# =============================================================================
# 8. REGISTRY RESOLUTION & TRANSACTIONAL DEPENDENCY MANAGER
# =============================================================================


def resolve_p7_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve the target filesystem path for the Phase 7 Golden Registry artifact (p7.json).
    """
    if output_dir:
        base = Path(output_dir).resolve()
        if base.name == "p7.json":
            return base
        return base / "p7.json"

    if "COCHEM_REGISTRY_DIR" in os.environ and os.environ["COCHEM_REGISTRY_DIR"].strip():
        return (Path(os.environ["COCHEM_REGISTRY_DIR"]) / "p7.json").resolve()

    if "COCHEM_ARTIFACT_DIR" in os.environ and os.environ["COCHEM_ARTIFACT_DIR"].strip():
        return (Path(os.environ["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p7.json").resolve()

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "p7.json").resolve()


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
                if self.target_path.exists():
                    try:
                        self.target_path.unlink()
                    except Exception:
                        pass
                self.temp_path.rename(self.target_path)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            raise


# =============================================================================
# 9. MASTER PHASE 7 AUDIT ORCHESTRATOR
# =============================================================================


def run_phase_7_audit(
    output_dir: Optional[Union[str, Path]] = None,
    scratch_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    cgroup_root: Optional[Union[str, Path]] = None,
    places_policy: str = "cores",
    proc_bind: str = "close",
    dry_run: bool = False,
) -> Phase7AuditReport:
    """
    Execute the Stage 0 Setup Phase 7 HPC environment injection & topology audit.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    target_env = os.environ if env is None else env
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Resolve registry artifact path
    p7_path = resolve_p7_registry_path(output_dir)

    # 2. Detect scheduler & parse topology
    try:
        scheduler = detect_hpc_scheduler(target_env)
        topology = parse_topology(target_env)
    except Exception as exc:
        errors.append(f"HPC topology parsing failed: {exc}")
        topology = HPCTopologyProfile(
            scheduler=HPCSchedulerType.LOCAL_STANDALONE,
            job_id=None,
            num_nodes=1,
            node_list=[platform.node() or "localhost"],
            tasks_per_node=[1],
            total_tasks=1,
            cpus_per_task=1,
            cpus_on_node=1,
            is_heterogeneous=False,
        )
        scheduler = HPCSchedulerType.LOCAL_STANDALONE

    # 3. Parse memory limits
    cgroup_path = Path(cgroup_root) if cgroup_root else None
    try:
        memory = parse_hpc_memory_limit(
            env=target_env,
            cgroup_root=cgroup_path,
            tasks_per_node=topology.tasks_per_node,
            cpus_per_task=topology.cpus_per_task,
        )
    except Exception as exc:
        errors.append(f"HPC memory allocation parsing failed: {exc}")
        memory = HPCMemoryProfile(
            mem_per_node_mb=None,
            mem_per_cpu_mb=None,
            cgroup_limit_bytes=None,
            physical_ram_bytes=get_physical_ram_bytes(),
            effective_usable_memory_mb=8192.0,
            source="PHYSICAL_RAM",
        )

    # 4. Resolve scratch directory
    try:
        scratch = resolve_hpc_scratch_directory(override=scratch_dir, env=target_env)
        if not scratch.is_writable:
            warnings.append(
                f"Scratch directory '{scratch.scratch_directory}' is not writable; execution may degrade."
            )
    except Exception as exc:
        errors.append(f"Scratch directory resolution failed: {exc}")
        scratch = HPCScratchProfile(
            scratch_directory=str(Path.home() / "CoChem_Artifacts" / "Scratch"),
            is_accessible=False,
            is_writable=False,
            free_disk_space_gb=0.0,
            source_variable="FALLBACK",
        )

    # 5. Compute thread & core bindings
    affinity = compute_thread_affinity_profile(
        topology=topology,
        places_policy=places_policy,
        proc_bind=proc_bind,
    )

    # 6. Generate environment injection dictionary
    injected_env = generate_environment_injection_dict(
        topology=topology,
        memory=memory,
        scratch=scratch,
        affinity=affinity,
    )

    # 7. Determine status
    if errors:
        status = PhaseStatus.FAILED
    elif warnings or not scratch.is_writable:
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    report = Phase7AuditReport(
        phase_id="cochem_setup_phase_7",
        status=status,
        scheduler_detected=scheduler,
        timestamp_utc=timestamp,
        artifact_path=str(p7_path),
        topology=topology,
        memory=memory,
        scratch=scratch,
        affinity=affinity,
        injected_env_vars=injected_env,
        warnings=warnings,
        errors=errors,
    )

    # 8. Transactional persistence into Golden Registry
    if not dry_run and status != PhaseStatus.FAILED:
        with DependencyManager(p7_path) as dm:
            dm.write_payload(report)

    return report


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for Stage 0 Setup Phase 7: HPC Environment Injection Gatekeeper.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 7: HPC Environment Variable Injection Gatekeeper."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p7.json)",
    )
    parser.add_argument(
        "--scratch-dir",
        type=str,
        default=None,
        help="Custom directory path for node-local scratch ($SLURM_TMPDIR / $TMPDIR)",
    )
    parser.add_argument(
        "--places",
        type=str,
        default="cores",
        help="OMP_PLACES hardware policy (cores, threads, sockets)",
    )
    parser.add_argument(
        "--proc-bind",
        type=str,
        default="close",
        help="OMP_PROC_BIND binding policy (close, spread, master)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate HPC audit without modifying physical registry",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_7_audit(
            output_dir=args.output_dir,
            scratch_dir=args.scratch_dir,
            places_policy=args.places,
            proc_bind=args.proc_bind,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 7: HPC ENVIRONMENT & TOPOLOGY GATEKEEPER")
            print("=" * 75)
            print(f"Phase ID:          {report.phase_id}")
            print(f"Status:            {report.status.value}")
            print(f"Scheduler:         {report.scheduler_detected.value}")
            print(f"Timestamp UTC:     {report.timestamp_utc}")
            print(f"Artifact Path:     {report.artifact_path}")
            print("-" * 75)
            print("Execution Topology:")
            print(f"  Job ID:          {report.topology.job_id or 'N/A'}")
            print(f"  Nodes Allocated: {report.topology.num_nodes} (Nodes: {', '.join(report.topology.node_list[:5])}{'...' if len(report.topology.node_list) > 5 else ''})")
            print(f"  Total Tasks:     {report.topology.total_tasks} (Tasks/Node: {report.topology.tasks_per_node})")
            print(f"  CPUs/Task:       {report.topology.cpus_per_task}")
            print(f"  CPUs on Node:    {report.topology.cpus_on_node}")
            print(f"  Heterogeneous:   {report.topology.is_heterogeneous}")
            print("-" * 75)
            print("Memory & Scratch Architecture:")
            print(f"  Memory Ceiling:  {report.memory.effective_usable_memory_mb:.1f} MB (Source: {report.memory.source})")
            print(f"  Scratch Dir:     {report.scratch.scratch_directory}")
            print(f"  Scratch Source:  {report.scratch.source_variable}")
            print(f"  Scratch Space:   {report.scratch.free_disk_space_gb:.1f} GB (Writable: {report.scratch.is_writable})")
            print("-" * 75)
            print("Thread & Core Bindings:")
            print(f"  OMP_NUM_THREADS: {report.affinity.omp_num_threads}")
            print(f"  MKL_NUM_THREADS: {report.affinity.mkl_num_threads}")
            print(f"  OMP_PLACES:      {report.affinity.omp_places}")
            print(f"  OMP_PROC_BIND:   {report.affinity.omp_proc_bind}")
            print(f"  KMP_AFFINITY:    {report.affinity.kmp_affinity}")
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
        sys.stderr.write(f"\n[FATAL PHASE 7 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_7.py ---
"""
Unit test suite for CoChem Setup Phase 7: HPC Environment Variable Injection & Topology Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, real temporary directories, real environment
variable dictionary evaluation, real bracketed nodelist range expansions, real multiplier task
parsing, real cgroup limit hierarchy evaluation, real thread affinity generation, and transactional
atomic state persistence into the Golden Registry (p7.json).

SRS Document 2 Part 2 (Section 3.7), Method Matrix v4, and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_7 import (
    DependencyManager,
    HPCMemoryParseError,
    HPCMemoryProfile,
    HPCSchedulerType,
    HPCScratchAllocationError,
    HPCScratchProfile,
    HPCThreadAffinityProfile,
    HPCTopologyError,
    HPCTopologyProfile,
    Phase7AuditError,
    Phase7AuditReport,
    PhaseStatus,
    _expand_single_node_spec,
    _split_top_level_commas,
    compute_thread_affinity_profile,
    detect_hpc_scheduler,
    generate_environment_injection_dict,
    get_physical_ram_bytes,
    main,
    parse_cgroup_memory_limit,
    parse_hpc_memory_limit,
    parse_lsf_topology,
    parse_memory_string_to_mb,
    parse_pbs_topology,
    parse_sge_topology,
    parse_slurm_nodelist,
    parse_slurm_tasks_per_node,
    parse_slurm_topology,
    parse_standalone_topology,
    parse_topology,
    resolve_hpc_scratch_directory,
    resolve_p7_registry_path,
    run_phase_7_audit,
)


# Helper for Windows temp directory cleanup resilience
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
    """Verify custom Phase 7 exception classes inherit from RuntimeError."""
    err1 = Phase7AuditError("Phase 7 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = HPCTopologyError("HPC topology parsing failed")
    assert isinstance(err2, RuntimeError)
    err3 = HPCMemoryParseError("Memory parsing failed")
    assert isinstance(err3, RuntimeError)
    err4 = HPCScratchAllocationError("Scratch allocation failed")
    assert isinstance(err4, RuntimeError)


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum values and validation."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus.BYPASSED.value == "BYPASSED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_hpc_scheduler_type_enum() -> None:
    """Verify HPCSchedulerType enum members and string representations."""
    assert HPCSchedulerType.SLURM.value == "SLURM"
    assert HPCSchedulerType.PBS.value == "PBS"
    assert HPCSchedulerType.LSF.value == "LSF"
    assert HPCSchedulerType.SGE.value == "SGE"
    assert HPCSchedulerType.LOCAL_STANDALONE.value == "LOCAL_STANDALONE"
    assert HPCSchedulerType("SLURM") is HPCSchedulerType.SLURM

    with pytest.raises(ValueError):
        HPCSchedulerType("UNKNOWN_SCHEDULER")


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_hpc_topology_profile_validation() -> None:
    """Test HPCTopologyProfile defaults, constraints, and extra field prohibition."""
    profile = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123456",
        num_nodes=2,
        node_list=["node01", "node02"],
        tasks_per_node=[8, 8],
        total_tasks=16,
        cpus_per_task=4,
        cpus_on_node=32,
        is_heterogeneous=False,
    )
    assert profile.scheduler == HPCSchedulerType.SLURM
    assert profile.job_id == "123456"
    assert profile.num_nodes == 2
    assert profile.total_tasks == 16
    assert profile.cpus_per_task == 4
    assert profile.cpus_on_node == 32
    assert profile.is_heterogeneous is False

    # Negative num_nodes constraint
    with pytest.raises(ValidationError):
        HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            num_nodes=0,
            total_tasks=1,
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            num_nodes=1,
            total_tasks=1,
            unauthorized_field=True,  # type: ignore[call-arg]
        )


def test_hpc_memory_profile_validation() -> None:
    """Test HPCMemoryProfile field validation and serialization."""
    profile = HPCMemoryProfile(
        mem_per_node_mb=64000.0,
        mem_per_cpu_mb=4000.0,
        cgroup_limit_bytes=None,
        physical_ram_bytes=137438953472,
        effective_usable_memory_mb=64000.0,
        source="SLURM_MEM_PER_NODE",
    )
    assert profile.mem_per_node_mb == 64000.0
    assert profile.effective_usable_memory_mb == 64000.0
    assert profile.source == "SLURM_MEM_PER_NODE"

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCMemoryProfile(
            physical_ram_bytes=1000,
            effective_usable_memory_mb=1000.0,
            source="PHYSICAL_RAM",
            forbidden_attr="test",  # type: ignore[call-arg]
        )


def test_hpc_scratch_profile_validation() -> None:
    """Test HPCScratchProfile field validation."""
    profile = HPCScratchProfile(
        scratch_directory="/tmp/slurm_scratch",
        is_accessible=True,
        is_writable=True,
        free_disk_space_gb=250.5,
        source_variable="SLURM_TMPDIR",
    )
    assert profile.scratch_directory == "/tmp/slurm_scratch"
    assert profile.free_disk_space_gb == 250.5
    assert profile.source_variable == "SLURM_TMPDIR"

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        HPCScratchProfile(
            scratch_directory="/tmp",
            source_variable="TEMP",
            invalid_flag=True,  # type: ignore[call-arg]
        )


def test_hpc_thread_affinity_profile_validation() -> None:
    """Test HPCThreadAffinityProfile field validation and defaults."""
    profile = HPCThreadAffinityProfile(
        omp_num_threads=8,
        mkl_num_threads=8,
        openblas_num_threads=8,
        blis_num_threads=8,
        omp_places="cores",
        omp_proc_bind="close",
        kmp_affinity="granularity=fine,compact,1,0",
        kmp_blocktime=0,
        environment_variables={"OMP_NUM_THREADS": "8"},
    )
    assert profile.omp_num_threads == 8
    assert profile.kmp_blocktime == 0
    assert profile.omp_places == "cores"

    # Constraint violation: negative threads
    with pytest.raises(ValidationError):
        HPCThreadAffinityProfile(
            omp_num_threads=0,
            mkl_num_threads=1,
            openblas_num_threads=1,
        )


def test_phase_7_audit_report_roundtrip_serialization() -> None:
    """Test Phase7AuditReport construction and JSON serialization roundtrip."""
    with make_temp_dir() as tmpdir:
        art_path = Path(tmpdir) / "p7.json"
        topology = HPCTopologyProfile(
            scheduler=HPCSchedulerType.SLURM,
            job_id="998877",
            num_nodes=2,
            node_list=["node01", "node02"],
            tasks_per_node=[4, 4],
            total_tasks=8,
            cpus_per_task=2,
            cpus_on_node=8,
            is_heterogeneous=False,
        )
        memory = HPCMemoryProfile(
            mem_per_node_mb=32000.0,
            physical_ram_bytes=68719476736,
            effective_usable_memory_mb=32000.0,
            source="SLURM_MEM_PER_NODE",
        )
        scratch = HPCScratchProfile(
            scratch_directory=str(Path(tmpdir) / "scratch"),
            is_accessible=True,
            is_writable=True,
            free_disk_space_gb=100.0,
            source_variable="SLURM_TMPDIR",
        )
        affinity = HPCThreadAffinityProfile(
            omp_num_threads=2,
            mkl_num_threads=2,
            openblas_num_threads=2,
            blis_num_threads=2,
            omp_places="cores",
            omp_proc_bind="close",
            kmp_affinity="granularity=fine,compact,1,0",
            kmp_blocktime=0,
            environment_variables={"OMP_NUM_THREADS": "2"},
        )
        report = Phase7AuditReport(
            phase_id="cochem_setup_phase_7",
            status=PhaseStatus.PASSED,
            scheduler_detected=HPCSchedulerType.SLURM,
            timestamp_utc="2026-08-21T00:00:00Z",
            artifact_path=str(art_path),
            topology=topology,
            memory=memory,
            scratch=scratch,
            affinity=affinity,
            injected_env_vars={"OMP_NUM_THREADS": "2", "COCHEM_HPC_SCHEDULER": "SLURM"},
            warnings=[],
            errors=[],
        )

        json_str = report.model_dump_json(indent=2)
        parsed_dict = json.loads(json_str)
        assert parsed_dict["phase_id"] == "cochem_setup_phase_7"
        assert parsed_dict["status"] == "PASSED"
        assert parsed_dict["scheduler_detected"] == "SLURM"
        assert parsed_dict["topology"]["total_tasks"] == 8

        # Roundtrip deserialization
        restored = Phase7AuditReport.model_validate(parsed_dict)
        assert restored.status == PhaseStatus.PASSED
        assert restored.topology.num_nodes == 2


# =============================================================================
# 3. HPC SCHEDULER DETECTION ENGINE TESTS
# =============================================================================


def test_detect_hpc_scheduler_explicit_override() -> None:
    """Verify explicit COCHEM_HPC_SCHEDULER override has top priority."""
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "SLURM"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "PBS"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "LSF"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "SGE"}) == HPCSchedulerType.SGE
    assert (
        detect_hpc_scheduler({"COCHEM_HPC_SCHEDULER": "LOCAL_STANDALONE"})
        == HPCSchedulerType.LOCAL_STANDALONE
    )


def test_detect_hpc_scheduler_slurm() -> None:
    """Verify Slurm scheduler detection from standard environment variables."""
    assert detect_hpc_scheduler({"SLURM_JOB_ID": "12345"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_JOBID": "12345"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_NNODES": "4"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_NODELIST": "node[01-04]"}) == HPCSchedulerType.SLURM
    assert detect_hpc_scheduler({"SLURM_TASKS_PER_NODE": "4(x4)"}) == HPCSchedulerType.SLURM


def test_detect_hpc_scheduler_pbs() -> None:
    """Verify PBS scheduler detection from PBS variables."""
    assert detect_hpc_scheduler({"PBS_JOBID": "pbs123.cluster"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_NODEFILE": "/var/spool/pbs/aux/123"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_NUM_NODES": "2"}) == HPCSchedulerType.PBS
    assert detect_hpc_scheduler({"PBS_ENVIRONMENT": "PBS_BATCH"}) == HPCSchedulerType.PBS


def test_detect_hpc_scheduler_lsf() -> None:
    """Verify LSF scheduler detection from LSB variables."""
    assert detect_hpc_scheduler({"LSB_JOBID": "lsf9988"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_HOSTS": "hostA hostA hostB"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_MCPU_HOSTS": "hostA 2 hostB 2"}) == HPCSchedulerType.LSF
    assert detect_hpc_scheduler({"LSB_DJOB_NUMPROC": "4"}) == HPCSchedulerType.LSF


def test_detect_hpc_scheduler_sge() -> None:
    """Verify SGE scheduler detection from SGE variables."""
    assert detect_hpc_scheduler({"PE_HOSTFILE": "/tmp/pe_hosts"}) == HPCSchedulerType.SGE
    assert detect_hpc_scheduler({"SGE_CELL": "default"}) == HPCSchedulerType.SGE
    assert detect_hpc_scheduler({"JOB_ID": "5544", "NSLOTS": "16"}) == HPCSchedulerType.SGE


def test_detect_hpc_scheduler_local_standalone() -> None:
    """Verify Local Standalone fallback when no HPC scheduler variables are present."""
    assert detect_hpc_scheduler({}) == HPCSchedulerType.LOCAL_STANDALONE
    assert detect_hpc_scheduler({"PATH": "/usr/bin", "USER": "test"}) == HPCSchedulerType.LOCAL_STANDALONE


# =============================================================================
# 4. SLURM NODELIST & TASK PARSER TESTS
# =============================================================================


def test_split_top_level_commas() -> None:
    """Test splitting strings by commas outside bracket groups."""
    assert _split_top_level_commas("node01,node02,node03") == ["node01", "node02", "node03"]
    assert _split_top_level_commas("node[01-03,05],gpu[01-02],head01") == [
        "node[01-03,05]",
        "gpu[01-02]",
        "head01",
    ]
    assert _split_top_level_commas("  node[01-02] ,  node03  ") == ["node[01-02]", "node03"]
    assert _split_top_level_commas("") == []


def test_expand_single_node_spec() -> None:
    """Test expanding single bracketed specifications."""
    assert _expand_single_node_spec("node01") == ["node01"]
    assert _expand_single_node_spec("node[01-03]") == ["node01", "node02", "node03"]
    assert _expand_single_node_spec("node[01-03,05]") == ["node01", "node02", "node03", "node05"]
    assert _expand_single_node_spec("gpu[001-002,005-006]") == [
        "gpu001",
        "gpu002",
        "gpu005",
        "gpu006",
    ]
    assert _expand_single_node_spec("c[1-2]n[3-4]") == ["c1n3", "c1n4", "c2n3", "c2n4"]
    assert _expand_single_node_spec("node[01-02]-ib0") == ["node01-ib0", "node02-ib0"]


def test_parse_slurm_nodelist_valid_cases() -> None:
    """Test complete Slurm nodelist parsing across multiple formats."""
    # Single node
    assert parse_slurm_nodelist("node01") == ["node01"]

    # Comma-separated list
    assert parse_slurm_nodelist("node01,node02,node03") == ["node01", "node02", "node03"]

    # Simple range
    assert parse_slurm_nodelist("node[01-04]") == ["node01", "node02", "node03", "node04"]

    # Multiple ranges with single nodes in brackets
    assert parse_slurm_nodelist("node[01-03,05,08-10]") == [
        "node01",
        "node02",
        "node03",
        "node05",
        "node08",
        "node09",
        "node10",
    ]

    # Mixed groups with commas outside brackets
    assert parse_slurm_nodelist("node[01-02],gpu[05-06],head01") == [
        "node01",
        "node02",
        "gpu05",
        "gpu06",
        "head01",
    ]

    # Empty string
    assert parse_slurm_nodelist("") == []
    assert parse_slurm_nodelist("   ") == []


def test_parse_slurm_nodelist_error_handling() -> None:
    """Test error handling on malformed nodelist strings."""
    # Mismatched brackets
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[01-03")

    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node01]")

    # Descending range
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[05-02]")

    # Non-numeric range
    with pytest.raises(HPCTopologyError):
        parse_slurm_nodelist("node[ab-cd]")


def test_parse_slurm_tasks_per_node_valid() -> None:
    """Test parsing of Slurm SLURM_TASKS_PER_NODE with multipliers."""
    # Multipliers
    assert parse_slurm_tasks_per_node("4(x2),2") == [4, 4, 2]
    assert parse_slurm_tasks_per_node("8(x3),4(x2),2") == [8, 8, 8, 4, 4, 2]
    assert parse_slurm_tasks_per_node("4(x2), 2(x2)") == [4, 4, 2, 2]

    # Comma list without multiplier
    assert parse_slurm_tasks_per_node("4,4,2") == [4, 4, 2]

    # Single value with num_nodes expansion
    assert parse_slurm_tasks_per_node("16", num_nodes=3) == [16, 16, 16]
    assert parse_slurm_tasks_per_node("16", num_nodes=1) == [16]
    assert parse_slurm_tasks_per_node("16") == [16]


def test_parse_slurm_tasks_per_node_errors() -> None:
    """Test error handling for invalid tasks-per-node strings."""
    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("   ")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("invalid_string")

    with pytest.raises(HPCTopologyError):
        parse_slurm_tasks_per_node("4(x)")


# =============================================================================
# 5. SCHEDULER TOPOLOGY PARSERS
# =============================================================================


def test_parse_slurm_topology() -> None:
    """Test full Slurm topology parsing from environment dictionary."""
    env = {
        "SLURM_JOB_ID": "998877",
        "SLURM_NODELIST": "compute[01-02]",
        "SLURM_NNODES": "2",
        "SLURM_TASKS_PER_NODE": "8(x2)",
        "SLURM_CPUS_PER_TASK": "4",
        "SLURM_CPUS_ON_NODE": "32",
    }
    topo = parse_slurm_topology(env)
    assert topo.scheduler == HPCSchedulerType.SLURM
    assert topo.job_id == "998877"
    assert topo.num_nodes == 2
    assert topo.node_list == ["compute01", "compute02"]
    assert topo.tasks_per_node == [8, 8]
    assert topo.total_tasks == 16
    assert topo.cpus_per_task == 4
    assert topo.cpus_on_node == 32
    assert topo.is_heterogeneous is False


def test_parse_slurm_topology_heterogeneous() -> None:
    """Test heterogeneous Slurm topology detection."""
    env = {
        "SLURM_JOB_ID": "112233",
        "SLURM_NODELIST": "node[01-03]",
        "SLURM_TASKS_PER_NODE": "8(x2),4",
        "SLURM_CPUS_PER_TASK": "1",
    }
    topo = parse_slurm_topology(env)
    assert topo.num_nodes == 3
    assert topo.tasks_per_node == [8, 8, 4]
    assert topo.total_tasks == 20
    assert topo.is_heterogeneous is True


def test_parse_pbs_topology_with_nodefile() -> None:
    """Test PBS topology parsing with real filesystem PBS_NODEFILE."""
    with make_temp_dir() as tmpdir:
        nodefile = Path(tmpdir) / "pbs_nodefile"
        nodefile.write_text("pbs_node01\npbs_node01\npbs_node02\npbs_node02\n", encoding="utf-8")

        env = {
            "PBS_JOBID": "12345.pbs_master",
            "PBS_NODEFILE": str(nodefile),
        }
        topo = parse_pbs_topology(env)
        assert topo.scheduler == HPCSchedulerType.PBS
        assert topo.job_id == "12345.pbs_master"
        assert topo.num_nodes == 2
        assert topo.node_list == ["pbs_node01", "pbs_node02"]
        assert topo.tasks_per_node == [2, 2]
        assert topo.total_tasks == 4


def test_parse_pbs_topology_env_fallback() -> None:
    """Test PBS topology parsing with environment variables fallback."""
    env = {
        "PBS_JOBID": "67890.pbs_master",
        "PBS_NUM_NODES": "3",
        "PBS_NUM_PPN": "8",
    }
    topo = parse_pbs_topology(env)
    assert topo.scheduler == HPCSchedulerType.PBS
    assert topo.num_nodes == 3
    assert topo.tasks_per_node == [8, 8, 8]
    assert topo.total_tasks == 24


def test_parse_lsf_topology() -> None:
    """Test LSF topology parsing with LSB_HOSTS."""
    env = {
        "LSB_JOBID": "887766",
        "LSB_HOSTS": "lsf_host1 lsf_host1 lsf_host1 lsf_host1 lsf_host2 lsf_host2",
    }
    topo = parse_lsf_topology(env)
    assert topo.scheduler == HPCSchedulerType.LSF
    assert topo.job_id == "887766"
    assert topo.num_nodes == 2
    assert topo.node_list == ["lsf_host1", "lsf_host2"]
    assert topo.tasks_per_node == [4, 2]
    assert topo.total_tasks == 6
    assert topo.is_heterogeneous is True


def test_parse_sge_topology_with_pe_hostfile() -> None:
    """Test SGE topology parsing with real filesystem PE_HOSTFILE."""
    with make_temp_dir() as tmpdir:
        pe_file = Path(tmpdir) / "pe_hostfile"
        pe_file.write_text(
            "sge_node01 4 all.q lx-amd64\nsge_node02 4 all.q lx-amd64\n",
            encoding="utf-8",
        )

        env = {
            "JOB_ID": "443322",
            "PE_HOSTFILE": str(pe_file),
        }
        topo = parse_sge_topology(env)
        assert topo.scheduler == HPCSchedulerType.SGE
        assert topo.job_id == "443322"
        assert topo.num_nodes == 2
        assert topo.node_list == ["sge_node01", "sge_node02"]
        assert topo.tasks_per_node == [4, 4]
        assert topo.total_tasks == 8


def test_parse_standalone_topology() -> None:
    """Test standalone workstation topology parsing."""
    topo = parse_standalone_topology({})
    assert topo.scheduler == HPCSchedulerType.LOCAL_STANDALONE
    assert topo.job_id is None
    assert topo.num_nodes == 1
    assert topo.total_tasks == 1
    assert topo.cpus_per_task == (os.cpu_count() or 1)


def test_parse_topology_dispatcher() -> None:
    """Test parse_topology dispatcher across schedulers."""
    assert parse_topology({"SLURM_JOB_ID": "123"}).scheduler == HPCSchedulerType.SLURM
    assert parse_topology({"PBS_JOBID": "123"}).scheduler == HPCSchedulerType.PBS
    assert parse_topology({"LSB_JOBID": "123"}).scheduler == HPCSchedulerType.LSF
    assert parse_topology({"PE_HOSTFILE": "/tmp/pe"}).scheduler == HPCSchedulerType.SGE
    assert parse_topology({}).scheduler == HPCSchedulerType.LOCAL_STANDALONE


# =============================================================================
# 6. MEMORY ALLOCATION & CGROUP LIMIT TESTS
# =============================================================================


def test_parse_memory_string_to_mb_valid() -> None:
    """Test memory string parsing to Megabytes."""
    # Bare integer (MB default)
    assert parse_memory_string_to_mb("64000") == 64000.0

    # MB
    assert parse_memory_string_to_mb("64000M") == 64000.0
    assert parse_memory_string_to_mb("64000MB") == 64000.0
    assert parse_memory_string_to_mb("64000MiB") == 64000.0

    # GB
    assert parse_memory_string_to_mb("64G") == 65536.0
    assert parse_memory_string_to_mb("64GB") == 65536.0
    assert parse_memory_string_to_mb("128G") == 131072.0

    # TB
    assert parse_memory_string_to_mb("1T") == 1048576.0
    assert parse_memory_string_to_mb("1TB") == 1048576.0

    # KB
    assert parse_memory_string_to_mb("65536K") == 64.0
    assert parse_memory_string_to_mb("65536KB") == 64.0

    # Bytes
    assert parse_memory_string_to_mb("1048576B") == 1.0


def test_parse_memory_string_to_mb_errors() -> None:
    """Test error handling on invalid memory strings."""
    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("")

    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("invalid")

    with pytest.raises(HPCMemoryParseError):
        parse_memory_string_to_mb("64XYZ")


def test_get_physical_ram_bytes() -> None:
    """Verify physical host RAM probe returns positive byte count."""
    ram = get_physical_ram_bytes()
    assert isinstance(ram, int)
    assert ram > 0


def test_parse_cgroup_memory_limit_v2_and_v1() -> None:
    """Test parsing cgroup v1 and v2 limits using real temporary files."""
    with make_temp_dir() as tmpdir:
        root = Path(tmpdir)

        # Cgroups v2: memory.max
        cgroup_v2_dir = root / "sys" / "fs" / "cgroup"
        cgroup_v2_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_v2_dir / "memory.max").write_text("34359738368\n", encoding="utf-8")  # 32 GB

        limit_v2 = parse_cgroup_memory_limit(root)
        assert limit_v2 == 34359738368

        # When memory.max is "max" (unlimited)
        (cgroup_v2_dir / "memory.max").write_text("max\n", encoding="utf-8")
        assert parse_cgroup_memory_limit(root) is None

        # Cgroups v1: memory.limit_in_bytes
        (cgroup_v2_dir / "memory.max").unlink()
        cgroup_v1_dir = root / "sys" / "fs" / "cgroup" / "memory"
        cgroup_v1_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_v1_dir / "memory.limit_in_bytes").write_text(
            "17179869184\n", encoding="utf-8"
        )  # 16 GB

        limit_v1 = parse_cgroup_memory_limit(root)
        assert limit_v1 == 17179869184


def test_parse_hpc_memory_limit_slurm_per_node() -> None:
    """Test memory limit resolution from SLURM_MEM_PER_NODE."""
    env = {"SLURM_MEM_PER_NODE": "64G"}
    profile = parse_hpc_memory_limit(env=env)
    assert profile.mem_per_node_mb == 65536.0
    assert profile.effective_usable_memory_mb == 65536.0
    assert profile.source == "SLURM_MEM_PER_NODE"


def test_parse_hpc_memory_limit_slurm_per_cpu() -> None:
    """Test memory limit resolution from SLURM_MEM_PER_CPU."""
    env = {"SLURM_MEM_PER_CPU": "4000M"}
    # 8 tasks on node, 2 cpus per task = 16 total cpus -> 64000 MB
    profile = parse_hpc_memory_limit(
        env=env,
        tasks_per_node=[8],
        cpus_per_task=2,
    )
    assert profile.mem_per_cpu_mb == 4000.0
    assert profile.mem_per_node_mb == 64000.0
    assert profile.effective_usable_memory_mb == 64000.0
    assert profile.source == "SLURM_MEM_PER_CPU"


def test_parse_hpc_memory_limit_cgroup() -> None:
    """Test memory limit resolution constrained by cgroups."""
    with make_temp_dir() as tmpdir:
        root = Path(tmpdir)
        cgroup_dir = root / "sys" / "fs" / "cgroup"
        cgroup_dir.mkdir(parents=True, exist_ok=True)
        (cgroup_dir / "memory.max").write_text("17179869184\n", encoding="utf-8")  # 16 GB

        profile = parse_hpc_memory_limit(env={}, cgroup_root=root)
        assert profile.cgroup_limit_bytes == 17179869184
        assert profile.source == "CGROUP"
        assert abs(profile.effective_usable_memory_mb - 16384.0) < 1.0


def test_parse_hpc_memory_limit_physical_ram_fallback() -> None:
    """Test memory limit fallback to host physical RAM."""
    profile = parse_hpc_memory_limit(env={})
    assert profile.source == "PHYSICAL_RAM"
    assert profile.physical_ram_bytes > 0
    assert profile.effective_usable_memory_mb > 0.0


# =============================================================================
# 7. HIERARCHICAL SCRATCH DIRECTORY MAPPING TESTS
# =============================================================================


def test_resolve_hpc_scratch_directory_override() -> None:
    """Test explicit override parameter for scratch directory."""
    with make_temp_dir() as tmpdir:
        custom_scratch = Path(tmpdir) / "custom_scratch"
        profile = resolve_hpc_scratch_directory(override=custom_scratch)
        assert profile.scratch_directory == str(custom_scratch.resolve())
        assert profile.source_variable == "OVERRIDE"
        assert profile.is_accessible is True
        assert profile.is_writable is True
        assert profile.free_disk_space_gb > 0.0


def test_resolve_hpc_scratch_directory_env_hierarchy() -> None:
    """Test priority order across environment variables."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)
        dir_cochem = tmp_path / "cochem_scratch"
        dir_slurm = tmp_path / "slurm_scratch"
        dir_tmpdir = tmp_path / "tmpdir_scratch"
        dir_scratch = tmp_path / "scratch_base"
        dir_temp = tmp_path / "temp_scratch"

        # 1. COCHEM_SCRATCH_DIR priority over SLURM_TMPDIR
        env1 = {
            "COCHEM_SCRATCH_DIR": str(dir_cochem),
            "SLURM_TMPDIR": str(dir_slurm),
        }
        prof1 = resolve_hpc_scratch_directory(env=env1)
        assert prof1.source_variable == "COCHEM_SCRATCH_DIR"
        assert prof1.scratch_directory == str(dir_cochem.resolve())

        # 2. SLURM_TMPDIR priority over TMPDIR
        env2 = {
            "SLURM_TMPDIR": str(dir_slurm),
            "TMPDIR": str(dir_tmpdir),
        }
        prof2 = resolve_hpc_scratch_directory(env=env2)
        assert prof2.source_variable == "SLURM_TMPDIR"
        assert prof2.scratch_directory == str(dir_slurm.resolve())

        # 3. TMPDIR priority over SCRATCH
        env3 = {
            "TMPDIR": str(dir_tmpdir),
            "SCRATCH": str(dir_scratch),
        }
        prof3 = resolve_hpc_scratch_directory(env=env3)
        assert prof3.source_variable == "TMPDIR"
        assert prof3.scratch_directory == str(dir_tmpdir.resolve())

        # 4. SCRATCH creates CoChem_Scratch subfolder
        env4 = {
            "SCRATCH": str(dir_scratch),
        }
        prof4 = resolve_hpc_scratch_directory(env=env4)
        assert prof4.source_variable == "SCRATCH"
        assert prof4.scratch_directory == str((dir_scratch / "CoChem_Scratch").resolve())


def test_resolve_hpc_scratch_directory_fallback() -> None:
    """Test default fallback scratch directory resolution."""
    prof = resolve_hpc_scratch_directory(env={})
    assert prof.source_variable in ("FALLBACK", "TEMP", "TMP")
    assert Path(prof.scratch_directory).exists()
    assert prof.is_accessible is True


# =============================================================================
# 8. THREAD AFFINITY & PROCESS CORE BINDINGS TESTS
# =============================================================================


def test_compute_thread_affinity_profile_multithreaded_task() -> None:
    """Test thread affinity calculation when cpus_per_task > 1."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123",
        num_nodes=1,
        node_list=["node01"],
        tasks_per_node=[2],
        total_tasks=2,
        cpus_per_task=8,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    affinity = compute_thread_affinity_profile(topology, places_policy="cores", proc_bind="close")
    assert affinity.omp_num_threads == 8
    assert affinity.mkl_num_threads == 8
    assert affinity.openblas_num_threads == 8
    assert affinity.blis_num_threads == 8
    assert affinity.omp_places == "cores"
    assert affinity.omp_proc_bind == "close"
    assert affinity.kmp_affinity == "granularity=fine,compact,1,0"
    assert affinity.kmp_blocktime == 0
    assert affinity.environment_variables["OMP_NUM_THREADS"] == "8"
    assert affinity.environment_variables["MKL_NUM_THREADS"] == "8"


def test_compute_thread_affinity_profile_spread_policy() -> None:
    """Test thread affinity calculation with spread/scatter binding policy."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="123",
        num_nodes=1,
        node_list=["node01"],
        tasks_per_node=[1],
        total_tasks=1,
        cpus_per_task=16,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    affinity = compute_thread_affinity_profile(
        topology, places_policy="threads", proc_bind="spread"
    )
    assert affinity.omp_places == "threads"
    assert affinity.omp_proc_bind == "spread"
    assert affinity.kmp_affinity == "granularity=fine,scatter"


def test_generate_environment_injection_dict() -> None:
    """Test generation of complete environment variable injection dictionary."""
    topology = HPCTopologyProfile(
        scheduler=HPCSchedulerType.SLURM,
        job_id="998877",
        num_nodes=2,
        node_list=["node01", "node02"],
        tasks_per_node=[8, 8],
        total_tasks=16,
        cpus_per_task=2,
        cpus_on_node=16,
        is_heterogeneous=False,
    )
    memory = HPCMemoryProfile(
        mem_per_node_mb=64000.0,
        physical_ram_bytes=68719476736,
        effective_usable_memory_mb=64000.0,
        source="SLURM_MEM_PER_NODE",
    )
    scratch = HPCScratchProfile(
        scratch_directory="/tmp/slurm_scratch",
        is_accessible=True,
        is_writable=True,
        free_disk_space_gb=100.0,
        source_variable="SLURM_TMPDIR",
    )
    affinity = compute_thread_affinity_profile(topology)

    injected = generate_environment_injection_dict(topology, memory, scratch, affinity)

    assert injected["OMP_NUM_THREADS"] == "2"
    assert injected["MKL_NUM_THREADS"] == "2"
    assert injected["COCHEM_SCRATCH_DIR"] == "/tmp/slurm_scratch"
    assert injected["COCHEM_HPC_SCHEDULER"] == "SLURM"
    assert injected["COCHEM_NUM_NODES"] == "2"
    assert injected["COCHEM_TOTAL_TASKS"] == "16"
    assert injected["COCHEM_CPUS_PER_TASK"] == "2"
    assert injected["COCHEM_CPUS_ON_NODE"] == "16"
    assert injected["COCHEM_MEMORY_PER_NODE_MB"] == "64000.0"
    assert injected["COCHEM_JOB_ID"] == "998877"
    assert injected["SLURM_TMPDIR"] == "/tmp/slurm_scratch"


# =============================================================================
# 9. REGISTRY PATH & TRANSACTIONAL DEPENDENCY MANAGER TESTS
# =============================================================================


def test_resolve_p7_registry_path() -> None:
    """Test Phase 7 Golden Registry path resolution."""
    with make_temp_dir() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Custom directory argument
        p1 = resolve_p7_registry_path(tmp_path)
        assert p1 == (tmp_path / "p7.json").resolve()

        # Direct file argument
        p2 = resolve_p7_registry_path(tmp_path / "p7.json")
        assert p2 == (tmp_path / "p7.json").resolve()


def test_dependency_manager_atomic_commit() -> None:
    """Test transactional commit of p7.json payload via DependencyManager."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "Registry" / "p7.json"

        with DependencyManager(target) as dm:
            dm.write_payload({"phase_id": "cochem_setup_phase_7", "status": "PASSED"})

        assert target.exists()
        content = json.loads(target.read_text(encoding="utf-8"))
        assert content["phase_id"] == "cochem_setup_phase_7"
        assert content["status"] == "PASSED"


def test_dependency_manager_rollback_on_exception() -> None:
    """Test that DependencyManager cleans up temporary files when an exception occurs."""
    with make_temp_dir() as tmpdir:
        target = Path(tmpdir) / "Registry" / "p7.json"

        with pytest.raises(RuntimeError):
            with DependencyManager(target) as dm:
                dm.write_payload({"status": "CORRUPTED"})
                raise RuntimeError("Simulated calculation crash")

        # Destination must not exist
        assert not target.exists()
        # No orphan temp files left
        assert len(list(target.parent.glob("*.tmp_*"))) == 0


# =============================================================================
# 10. MASTER PHASE 7 AUDIT END-TO-END TESTS
# =============================================================================


def test_run_phase_7_audit_slurm_end_to_end() -> None:
    """Test full Phase 7 audit execution in a Slurm cluster environment."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        scratch_dir = Path(tmpdir) / "Scratch"

        env = {
            "SLURM_JOB_ID": "556677",
            "SLURM_NODELIST": "gpu_node[01-02]",
            "SLURM_NNODES": "2",
            "SLURM_TASKS_PER_NODE": "4(x2)",
            "SLURM_CPUS_PER_TASK": "4",
            "SLURM_CPUS_ON_NODE": "16",
            "SLURM_MEM_PER_NODE": "128G",
            "SLURM_TMPDIR": str(scratch_dir),
        }

        report = run_phase_7_audit(
            output_dir=out_dir,
            scratch_dir=scratch_dir,
            env=env,
            places_policy="cores",
            proc_bind="close",
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.SLURM
        assert report.topology.job_id == "556677"
        assert report.topology.num_nodes == 2
        assert report.topology.node_list == ["gpu_node01", "gpu_node02"]
        assert report.topology.total_tasks == 8
        assert report.topology.cpus_per_task == 4
        assert report.affinity.omp_num_threads == 4
        assert report.memory.mem_per_node_mb == 131072.0
        assert report.scratch.scratch_directory == str(scratch_dir.resolve())
        assert report.scratch.is_writable is True
        assert len(report.errors) == 0

        # Verify registry artifact persistence
        registry_file = out_dir / "p7.json"
        assert registry_file.exists()
        saved = json.loads(registry_file.read_text(encoding="utf-8"))
        assert saved["scheduler_detected"] == "SLURM"
        assert saved["topology"]["total_tasks"] == 8


def test_run_phase_7_audit_pbs_end_to_end() -> None:
    """Test full Phase 7 audit execution in a PBS environment."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        nodefile = Path(tmpdir) / "pbs_nodes"
        nodefile.write_text("pbs_n1\npbs_n1\npbs_n2\npbs_n2\n", encoding="utf-8")

        env = {
            "PBS_JOBID": "1234.pbs_server",
            "PBS_NODEFILE": str(nodefile),
            "TMPDIR": str(Path(tmpdir) / "pbs_scratch"),
        }

        report = run_phase_7_audit(
            output_dir=out_dir,
            env=env,
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.PBS
        assert report.topology.num_nodes == 2
        assert report.topology.total_tasks == 4


def test_run_phase_7_audit_standalone_end_to_end() -> None:
    """Test full Phase 7 audit execution in local standalone workstation mode."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"

        report = run_phase_7_audit(
            output_dir=out_dir,
            env={},
            dry_run=False,
        )

        assert report.status == PhaseStatus.PASSED
        assert report.scheduler_detected == HPCSchedulerType.LOCAL_STANDALONE
        assert report.topology.num_nodes == 1
        assert report.topology.total_tasks == 1
        assert (out_dir / "p7.json").exists()


def test_run_phase_7_audit_dry_run() -> None:
    """Test dry-run mode does not create physical registry file."""
    with make_temp_dir() as tmpdir:
        out_dir = Path(tmpdir) / "Registry"
        report = run_phase_7_audit(
            output_dir=out_dir,
            env={},
            dry_run=True,
        )
        assert report.status == PhaseStatus.PASSED
        assert not (out_dir / "p7.json").exists()


# =============================================================================
# 11. CLI ENTRYPOINT TESTS
# =============================================================================


def test_main_cli_success() -> None:
    """Test main CLI entrypoint with standard dry-run argument."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--dry-run"])
        assert ret == 0


def test_main_cli_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """Test main CLI entrypoint with --json flag."""
    with make_temp_dir() as tmpdir:
        out_dir = str(Path(tmpdir) / "Registry")
        ret = main(["--output-dir", out_dir, "--dry-run", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["phase_id"] == "cochem_setup_phase_7"
        assert "topology" in data
        assert "memory" in data
        assert "affinity" in data

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.