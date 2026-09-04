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
import atexit
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def sweep_zombies() -> None:
    if psutil is None:
        return
    for p in psutil.process_iter(['pid', 'status']):
        try:
            if p.info['status'] == psutil.STATUS_ZOMBIE:
                p.wait(timeout=1)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied, KeyError) as _e:
            logger.debug(f"Ignored exception: {_e}")

atexit.register(sweep_zombies)

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
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

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
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

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
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

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
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
            return

        try:
            if self.temp_path.exists():
                if self.target_path.exists():
                    try:
                        self.target_path.unlink()
                    except Exception as _e:
                        logger.debug(f"Ignored exception: {_e}")
                self.temp_path.rename(self.target_path)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
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
            logger.info(report.model_dump_json(indent=2))
        else:
            logger.info("=" * 75)
            logger.info("COCHEM SETUP PHASE 7: HPC ENVIRONMENT & TOPOLOGY GATEKEEPER")
            logger.info("=" * 75)
            logger.info(f"Phase ID:          {report.phase_id}")
            logger.info(f"Status:            {report.status.value}")
            logger.info(f"Scheduler:         {report.scheduler_detected.value}")
            logger.info(f"Timestamp UTC:     {report.timestamp_utc}")
            logger.info(f"Artifact Path:     {report.artifact_path}")
            logger.info("-" * 75)
            logger.info("Execution Topology:")
            logger.info(f"  Job ID:          {report.topology.job_id or 'N/A'}")
            logger.info(f"  Nodes Allocated: {report.topology.num_nodes} (Nodes: {', '.join(report.topology.node_list[:5])}{'...' if len(report.topology.node_list) > 5 else ''})")
            logger.info(f"  Total Tasks:     {report.topology.total_tasks} (Tasks/Node: {report.topology.tasks_per_node})")
            logger.info(f"  CPUs/Task:       {report.topology.cpus_per_task}")
            logger.info(f"  CPUs on Node:    {report.topology.cpus_on_node}")
            logger.info(f"  Heterogeneous:   {report.topology.is_heterogeneous}")
            logger.info("-" * 75)
            logger.info("Memory & Scratch Architecture:")
            logger.info(f"  Memory Ceiling:  {report.memory.effective_usable_memory_mb:.1f} MB (Source: {report.memory.source})")
            logger.info(f"  Scratch Dir:     {report.scratch.scratch_directory}")
            logger.info(f"  Scratch Source:  {report.scratch.source_variable}")
            logger.info(f"  Scratch Space:   {report.scratch.free_disk_space_gb:.1f} GB (Writable: {report.scratch.is_writable})")
            logger.info("-" * 75)
            logger.info("Thread & Core Bindings:")
            logger.info(f"  OMP_NUM_THREADS: {report.affinity.omp_num_threads}")
            logger.info(f"  MKL_NUM_THREADS: {report.affinity.mkl_num_threads}")
            logger.info(f"  OMP_PLACES:      {report.affinity.omp_places}")
            logger.info(f"  OMP_PROC_BIND:   {report.affinity.omp_proc_bind}")
            logger.info(f"  KMP_AFFINITY:    {report.affinity.kmp_affinity}")
            logger.info("-" * 75)
            logger.info(f"Injected Env Vars ({len(report.injected_env_vars)} total):")
            for k, v in report.injected_env_vars.items():
                logger.info(f"  {k} = {v}")
            logger.info("-" * 75)
            logger.info(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                logger.warning(f"  - {w}")
            logger.info(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                logger.error(f"  - {e}")
            logger.info("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        logger.error(f"\n[FATAL PHASE 7 ERROR]\n{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
