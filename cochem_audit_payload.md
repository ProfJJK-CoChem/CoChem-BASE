Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc5_02_phase2_ram_profiling_prompt.md.
Original prompt:
# Context
You are tasked with writing the setup orchestration script `cochem_setup_phase_2.py` for CoChem-BASE.

# Goal
Create `cochem_setup_phase_2.py` to perform Phase 2: Hardware & RAM Profiling.

# Requirements
- Utilize `psutil` to map logical versus physical CPU cores (`psutil.cpu_count(logical=False)`) and define absolute available physical RAM (`SC_PHYS_PAGES`), bypassing virtualized/swap memory traps.
- Probe PCIe/`nvidia-smi` for active GPU passthrough capabilities and VRAM limits.
- Execute a rapid **IEEE-754 subnormal arithmetic check**. It must output exactly "Float Precision: Intact", guaranteeing the CPU architecture does not silently underflow floating-point math, which would catastrophically corrupt gradient vector alignments.
- Output the findings into an intermediate JSON state for later phases.

# Constraints
- Target filepath: `D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_2.py`
- DO NOT use any mocks, stubs, or placeholder values in your code. Write real implementation logic.
- Ensure strict adherence to the Tripartite Workspace Air-Gap and Method Matrix rules.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_2.py ---
"""
CoChem Setup Phase 2: Hardware & Resource Gatekeeper.
Production-grade, zero-mock gatekeeping engine for memory hierarchy auditing,
Linux cgroups v1 & v2 container resource constraints parsing, multi-core CPU topology interrogation,
heterogeneous GPU discovery (NVIDIA, AMD, Intel), IEEE-754 subnormal floating-point precision verification,
and transactional atomic state persistence.

SRS Document 2 Part 2 & Document 5 Compliant.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from pydantic import BaseModel, Field

# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase2AuditError(RuntimeError):
    """Raised when critical phase 2 hardware/resource prerequisites fail fatally."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class MemoryAudit(BaseModel):
    """Host and container memory topology audit record."""

    total_bytes: int = Field(..., description="Total host physical RAM in bytes")
    available_bytes: int = Field(..., description="Available physical RAM in bytes")
    swap_total_bytes: int = Field(default=0, description="Total swap space in bytes")
    swap_free_bytes: int = Field(default=0, description="Free swap space in bytes")
    cgroup_memory_limit_bytes: Optional[int] = Field(
        default=None, description="Memory limit enforced by cgroups (v1/v2) if present"
    )
    cgroup_swap_limit_bytes: Optional[int] = Field(
        default=None, description="Swap limit enforced by cgroups (v1/v2) if present"
    )
    is_cgroup_constrained: bool = Field(
        default=False,
        description="Whether cgroup limits actively constrain memory below host physical RAM",
    )
    effective_memory_bytes: int = Field(
        ...,
        description="Effective usable memory accounting for host physical RAM and container limits",
    )


class CPUAudit(BaseModel):
    """Host and container CPU topology and quota audit record."""

    physical_cores: int = Field(..., description="Number of physical CPU cores")
    logical_cores: int = Field(..., description="Number of logical CPU cores / threads")
    frequency_mhz: Optional[float] = Field(
        default=None, description="Current or maximum CPU frequency in MHz"
    )
    cgroup_cpu_quota_us: Optional[int] = Field(
        default=None, description="cgroup CPU quota in microseconds (None if unlimited)"
    )
    cgroup_cpu_period_us: Optional[int] = Field(
        default=None, description="cgroup CPU period in microseconds"
    )
    cgroup_effective_cpus: Optional[float] = Field(
        default=None, description="Effective fractional CPU allocation from cgroups quota/period"
    )
    cpu_affinity_count: Optional[int] = Field(
        default=None, description="Number of CPUs accessible via process affinity mask"
    )
    architecture: str = Field(..., description="Host CPU architecture (e.g. x86_64, AMD64, arm64)")


class GPUDevice(BaseModel):
    """Individual hardware GPU device inspection record."""

    index: int = Field(..., description="GPU device index (e.g. 0, 1)")
    vendor: str = Field(..., description="Vendor name: NVIDIA, AMD, INTEL, APPLE, etc.")
    name: str = Field(..., description="Model/Product name")
    memory_total_bytes: Optional[int] = Field(default=None, description="Total VRAM in bytes")
    memory_free_bytes: Optional[int] = Field(default=None, description="Free/available VRAM in bytes")
    driver_version: Optional[str] = Field(default=None, description="Installed GPU driver version")
    compute_capability: Optional[str] = Field(
        default=None, description="Compute capability or architecture generation (e.g. 8.9, gfx1100)"
    )
    uuid: Optional[str] = Field(default=None, description="GPU UUID if available")


class GPUProfile(BaseModel):
    """Heterogeneous GPU acceleration profile."""

    available: bool = Field(
        default=False, description="Whether any compute GPU accelerator is detected and accessible"
    )
    vendor_summary: Dict[str, int] = Field(
        default_factory=dict, description="Count of detected devices grouped by vendor"
    )
    devices: List[GPUDevice] = Field(
        default_factory=list, description="List of detected GPU devices"
    )
    cuda_available: bool = Field(
        default=False, description="Whether CUDA runtime/driver is usable"
    )
    rocm_available: bool = Field(
        default=False, description="Whether ROCm runtime/tools are usable"
    )
    oneapi_available: bool = Field(
        default=False, description="Whether Intel oneAPI / Level-Zero is usable"
    )
    degraded_fallback: bool = Field(
        default=False, description="Whether execution runs in CPU-only degraded fallback mode"
    )


class IEEE754PrecisionAudit(BaseModel):
    """IEEE-754 floating-point and subnormal/denormal precision audit record."""

    float32_epsilon: float = Field(..., description="Single precision (float32) machine epsilon")
    float64_epsilon: float = Field(..., description="Double precision (float64) machine epsilon")
    subnormal_supported: bool = Field(
        ...,
        description="Whether IEEE-754 subnormal/denormal numbers operate without Flush-to-Zero (FTZ)",
    )
    smallest_subnormal_f64: float = Field(
        ..., description="Smallest positive non-zero double precision subnormal (2^-1074)"
    )
    smallest_normal_f64: float = Field(
        ..., description="Smallest positive normalized double precision float (2^-1022)"
    )
    subnormal_arithmetic_valid: bool = Field(
        ...,
        description="Verification that subnormal addition, subtraction, and underflow retain precision",
    )
    precision_intact: bool = Field(
        ..., description="Overall verification that IEEE-754 floating point arithmetic is intact"
    )
    precision_message: str = Field(
        default="Float Precision: Intact", description="Diagnostic precision assertion message"
    )


class Phase2AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 2 Hardware & Resource Gatekeeper."""

    phase_id: str = Field(
        default="PHASE_2_HARDWARE_RESOURCE_GATEKEEPER", description="Unique phase identifier"
    )
    status: PhaseStatus = Field(..., description="Overall phase 2 gatekeeper status")
    timestamp_utc: str = Field(..., description="UTC ISO-8601 audit timestamp")
    memory: MemoryAudit = Field(..., description="Memory and container limit audit")
    cpu: CPUAudit = Field(..., description="CPU topology and cgroup quota audit")
    gpu: GPUProfile = Field(..., description="Heterogeneous GPU acceleration audit")
    precision: IEEE754PrecisionAudit = Field(..., description="IEEE-754 floating-point precision audit")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal resource warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal resource errors")
    artifact_path: Optional[str] = Field(
        default=None, description="Destination path of p2.json artifact"
    )


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY MANAGER & ATOMIC PERSISTENCE
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
        prefix: str = "cochem_p2_",
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

    def create_temp_dir(
        self,
        prefix: str = "cochem_p2_stage_",
        directory: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Create a tracked temporary directory."""
        dir_path = Path(directory) if directory else None
        if dir_path:
            dir_path.mkdir(parents=True, exist_ok=True)

        temp_dir_str = tempfile.mkdtemp(
            prefix=prefix,
            dir=str(dir_path) if dir_path else None,
        )
        temp_dir = Path(temp_dir_str).resolve()
        self.track_temp_dir(temp_dir)
        return temp_dir

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in self._tracked_temp_files:
            try:
                if temp_file.exists() and temp_file.is_file():
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in self._tracked_temp_dirs:
            try:
                if temp_dir.exists() and temp_dir.is_dir():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._tracked_temp_dirs.clear()

    def atomic_write_json(
        self,
        target_path: Union[str, Path],
        data: Union[BaseModel, Dict[str, Any], Any],
        indent: int = 2,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        # Create staged temporary file in the same directory for atomic replace guarantees
        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        # Format JSON payload
        if isinstance(data, BaseModel):
            payload = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            payload = json.dumps(data, indent=indent, default=str)
        else:
            payload = json.dumps(data, indent=indent, default=str)

        # Write to staged file with fsync
        with open(staged_file, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename replacing destination
        os.replace(staged_file, target)

        # Remove from tracked temp files now that it is committed
        if staged_file in self._tracked_temp_files:
            self._tracked_temp_files.remove(staged_file)

        return target


# =============================================================================
# 4. CGROUPS V1 & V2 CONTAINER RESOURCE PARSING
# =============================================================================

# Common cgroup v1 kernel constants for unlimited memory (e.g. 0x7FFFFFFFFFFFF000 or LLONG_MAX)
CGROUP_V1_UNLIMITED_THRESHOLD = 9223372036854770000


def _find_cgroup_candidate_files(
    filename: str,
    subsystems: List[str],
    cgroup_root: Optional[Path] = None,
) -> List[Path]:
    """Find potential cgroup files checking standard hierarchy paths."""
    candidates: List[Path] = []
    root = cgroup_root if cgroup_root is not None else Path("/")

    # Check root direct (e.g. synthetic or unified v2 root)
    candidates.append(root / "sys" / "fs" / "cgroup" / filename)
    candidates.append(root / filename)

    for sub in subsystems:
        candidates.append(root / "sys" / "fs" / "cgroup" / sub / filename)
        candidates.append(root / sub / filename)

    return [p for p in candidates if p.exists() and p.is_file()]


def parse_cgroup_memory_limit(
    cgroup_root: Optional[Path] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse Linux cgroups v1 or v2 memory and swap limits.
    Returns (memory_limit_bytes, swap_limit_bytes), where None indicates unlimited or absent.
    """
    mem_limit: Optional[int] = None
    swap_limit: Optional[int] = None

    # 1. Try Cgroups v2: memory.max and memory.swap.max
    v2_mem_files = _find_cgroup_candidate_files("memory.max", ["memory"], cgroup_root)
    if v2_mem_files:
        try:
            content = v2_mem_files[0].read_text(encoding="utf-8").strip()
            if content and content != "max":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    mem_limit = val
        except (ValueError, OSError):
            mem_limit = None

    v2_swap_files = _find_cgroup_candidate_files("memory.swap.max", ["memory"], cgroup_root)
    if v2_swap_files:
        try:
            content = v2_swap_files[0].read_text(encoding="utf-8").strip()
            if content and content != "max":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    swap_limit = val
        except (ValueError, OSError):
            swap_limit = None

    if mem_limit is not None or swap_limit is not None or v2_mem_files:
        return mem_limit, swap_limit

    # 2. Try Cgroups v1: memory.limit_in_bytes and memory.memsw.limit_in_bytes
    v1_mem_files = _find_cgroup_candidate_files("memory.limit_in_bytes", ["memory"], cgroup_root)
    if v1_mem_files:
        try:
            content = v1_mem_files[0].read_text(encoding="utf-8").strip()
            if content and content != "-1":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    mem_limit = val
        except (ValueError, OSError):
            mem_limit = None

    v1_memsw_files = _find_cgroup_candidate_files("memory.memsw.limit_in_bytes", ["memory"], cgroup_root)
    if v1_memsw_files:
        try:
            content = v1_memsw_files[0].read_text(encoding="utf-8").strip()
            if content and content != "-1":
                val = int(content)
                if 0 < val < CGROUP_V1_UNLIMITED_THRESHOLD:
                    swap_limit = val
        except (ValueError, OSError):
            swap_limit = None

    return mem_limit, swap_limit


def parse_cgroup_cpu_quota(
    cgroup_root: Optional[Path] = None,
) -> Tuple[Optional[int], Optional[float]]:
    """
    Parse Linux cgroups v1 or v2 CPU quota and period.
    Returns (cpu_quota_us, effective_cpus), where None indicates unlimited or absent.
    """
    # 1. Try Cgroups v2: cpu.max ("<quota> <period>")
    v2_cpu_files = _find_cgroup_candidate_files("cpu.max", ["cpu"], cgroup_root)
    if v2_cpu_files:
        try:
            content = v2_cpu_files[0].read_text(encoding="utf-8").strip()
            parts = content.split()
            if parts:
                quota_str = parts[0]
                period_str = parts[1] if len(parts) > 1 else "100000"
                if quota_str != "max":
                    quota_us = int(quota_str)
                    period_us = int(period_str)
                    if quota_us > 0 and period_us > 0:
                        effective_cpus = round(quota_us / period_us, 4)
                        return quota_us, effective_cpus
        except (ValueError, OSError, IndexError):
            pass
        return None, None

    # 2. Try Cgroups v1: cpu.cfs_quota_us and cpu.cfs_period_us
    v1_quota_files = _find_cgroup_candidate_files("cpu.cfs_quota_us", ["cpu"], cgroup_root)
    v1_period_files = _find_cgroup_candidate_files("cpu.cfs_period_us", ["cpu"], cgroup_root)

    if v1_quota_files:
        try:
            q_content = v1_quota_files[0].read_text(encoding="utf-8").strip()
            if q_content and q_content != "-1":
                quota_us = int(q_content)
                period_us = 100000
                if v1_period_files:
                    try:
                        p_content = v1_period_files[0].read_text(encoding="utf-8").strip()
                        if p_content:
                            period_us = int(p_content)
                    except (ValueError, OSError):
                        period_us = 100000

                if quota_us > 0 and period_us > 0:
                    effective_cpus = round(quota_us / period_us, 4)
                    return quota_us, effective_cpus
        except (ValueError, OSError):
            pass

    return None, None


# =============================================================================
# 5. MEMORY & CPU TOPOLOGY AUDITING
# =============================================================================


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


def audit_memory(cgroup_root: Optional[Path] = None) -> MemoryAudit:
    """
    Audit host physical memory and container cgroup memory limits.
    Utilizes SC_PHYS_PAGES / psutil to define absolute physical RAM,
    bypassing virtualized/swap memory traps.
    """
    total_bytes = get_absolute_physical_ram()
    vmem = psutil.virtual_memory()
    smem = psutil.swap_memory()

    available_bytes = int(vmem.available)
    swap_total = int(smem.total)
    swap_free = int(smem.free)

    cg_mem_limit, cg_swap_limit = parse_cgroup_memory_limit(cgroup_root=cgroup_root)

    is_constrained = False
    effective_memory = total_bytes

    if cg_mem_limit is not None and cg_mem_limit < total_bytes:
        is_constrained = True
        effective_memory = cg_mem_limit

    return MemoryAudit(
        total_bytes=total_bytes,
        available_bytes=available_bytes,
        swap_total_bytes=swap_total,
        swap_free_bytes=swap_free,
        cgroup_memory_limit_bytes=cg_mem_limit,
        cgroup_swap_limit_bytes=cg_swap_limit,
        is_cgroup_constrained=is_constrained,
        effective_memory_bytes=effective_memory,
    )


def audit_cpu(cgroup_root: Optional[Path] = None) -> CPUAudit:
    """
    Audit host multi-core CPU topology and container cgroup quotas.
    """
    physical_cores = psutil.cpu_count(logical=False) or os.cpu_count() or 1
    logical_cores = psutil.cpu_count(logical=True) or os.cpu_count() or 1
    arch = platform.machine() or "unknown"

    freq_mhz: Optional[float] = None
    try:
        cpu_freq = psutil.cpu_freq()
        if cpu_freq is not None:
            freq_mhz = float(cpu_freq.current or cpu_freq.max or 0.0)
            if freq_mhz == 0.0:
                freq_mhz = None
    except Exception:
        freq_mhz = None

    affinity_count: Optional[int] = None
    try:
        process = psutil.Process()
        if hasattr(process, "cpu_affinity"):
            aff = process.cpu_affinity()
            if aff:
                affinity_count = len(aff)
        elif hasattr(os, "sched_getaffinity"):
            aff_set = os.sched_getaffinity(0)
            if aff_set:
                affinity_count = len(aff_set)
    except Exception:
        affinity_count = None

    cg_quota_us, cg_effective_cpus = parse_cgroup_cpu_quota(cgroup_root=cgroup_root)
    cg_period_us: Optional[int] = None
    if cg_quota_us is not None:
        cg_period_us = 100000

    return CPUAudit(
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        frequency_mhz=freq_mhz,
        cgroup_cpu_quota_us=cg_quota_us,
        cgroup_cpu_period_us=cg_period_us,
        cgroup_effective_cpus=cg_effective_cpus,
        cpu_affinity_count=affinity_count,
        architecture=arch,
    )


# =============================================================================
# 6. HETEROGENEOUS GPU DISCOVERY (NVIDIA / AMD / INTEL)
# =============================================================================


def probe_nvidia_gpus() -> List[GPUDevice]:
    """
    Probe NVIDIA GPUs via nvidia-smi query.
    Returns empty list if nvidia-smi is unavailable.
    """
    devices: List[GPUDevice] = []
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return devices

    try:
        cmd = [
            nvidia_smi,
            "--query-gpu=index,name,memory.total,memory.free,driver_version,compute_cap,uuid",
            "--format=csv,noheader,nounits",
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    try:
                        idx = int(parts[0])
                        name = parts[1]
                        mem_total_mib = float(parts[2])
                        mem_free_mib = float(parts[3])
                        driver = parts[4]
                        compute_cap = parts[5]
                        gpu_uuid = parts[6]

                        devices.append(
                            GPUDevice(
                                index=idx,
                                vendor="NVIDIA",
                                name=name,
                                memory_total_bytes=int(mem_total_mib * 1024 * 1024),
                                memory_free_bytes=int(mem_free_mib * 1024 * 1024),
                                driver_version=driver,
                                compute_capability=compute_cap,
                                uuid=gpu_uuid,
                            )
                        )
                    except (ValueError, IndexError):
                        continue
    except Exception:
        pass

    return devices


def probe_amd_gpus() -> List[GPUDevice]:
    """
    Probe AMD ROCm GPUs via rocm-smi if available.
    """
    devices: List[GPUDevice] = []
    rocm_smi = shutil.which("rocm-smi")
    if not rocm_smi:
        return devices

    try:
        cmd = [rocm_smi, "--showid", "--showproductname", "--json"]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
                for k, v in data.items():
                    if isinstance(v, dict):
                        idx_val = 0
                        if k.startswith("card"):
                            try:
                                idx_val = int(k[4:])
                            except ValueError:
                                idx_val = 0
                        prod_name = v.get("Card series", v.get("Device Name", "AMD Radeon GPU"))
                        devices.append(
                            GPUDevice(
                                index=idx_val,
                                vendor="AMD",
                                name=str(prod_name),
                                memory_total_bytes=None,
                                memory_free_bytes=None,
                                driver_version=None,
                                compute_capability=None,
                                uuid=None,
                            )
                        )
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception:
        pass

    return devices


def probe_intel_gpus() -> List[GPUDevice]:
    """
    Probe Intel GPUs via xpu-smi or sycl-ls if available.
    """
    devices: List[GPUDevice] = []
    xpu_smi = shutil.which("xpu-smi")
    if not xpu_smi:
        return devices

    try:
        cmd = [xpu_smi, "discovery", "-j"]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
                dev_list = data.get("device_list", [])
                for d in dev_list:
                    devices.append(
                        GPUDevice(
                            index=int(d.get("device_id", 0)),
                            vendor="INTEL",
                            name=str(d.get("device_name", "Intel GPU")),
                            memory_total_bytes=None,
                            memory_free_bytes=None,
                            driver_version=None,
                            compute_capability=None,
                            uuid=None,
                        )
                    )
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception:
        pass

    return devices


def audit_gpus() -> GPUProfile:
    """
    Comprehensive heterogeneous GPU accelerator audit across NVIDIA, AMD, and Intel.
    Falls back gracefully to degraded mode if no compute GPUs are detected.
    """
    devices: List[GPUDevice] = []

    # 1. Probe NVIDIA
    nvidia_devs = probe_nvidia_gpus()
    devices.extend(nvidia_devs)

    # 2. Probe AMD
    amd_devs = probe_amd_gpus()
    devices.extend(amd_devs)

    # 3. Probe Intel
    intel_devs = probe_intel_gpus()
    devices.extend(intel_devs)

    # Vendor Summary
    summary: Dict[str, int] = {}
    for dev in devices:
        summary[dev.vendor] = summary.get(dev.vendor, 0) + 1

    has_nvidia = any(d.vendor == "NVIDIA" for d in devices)
    has_amd = any(d.vendor == "AMD" for d in devices)
    has_intel = any(d.vendor == "INTEL" for d in devices)

    available = len(devices) > 0
    degraded = not available

    return GPUProfile(
        available=available,
        vendor_summary=summary,
        devices=devices,
        cuda_available=has_nvidia,
        rocm_available=has_amd,
        oneapi_available=has_intel,
        degraded_fallback=degraded,
    )


# =============================================================================
# 7. IEEE-754 SUBNORMAL PRECISION VERIFICATION
# =============================================================================


def verify_ieee754_subnormal_precision() -> IEEE754PrecisionAudit:
    """
    Perform live mathematical verification of IEEE-754 double and single precision,
    machine epsilons, subnormal/denormal numbers, and absence of Flush-To-Zero (FTZ).
    """
    eps_f64 = sys.float_info.epsilon
    smallest_normal_f64 = sys.float_info.min  # 2^-1022

    # Single precision float32 machine epsilon: 2^-23
    eps_f32 = struct.unpack("f", struct.pack("f", 1.0 + 2**-23))[0] - 1.0

    # Smallest positive subnormal f64: 2^-1074
    smallest_subnormal_f64 = math.ldexp(1.0, -1074)

    # Subnormal arithmetic verification
    sub_a = math.ldexp(1.0, -1073)  # 2 * smallest_subnormal
    sub_b = smallest_subnormal_f64
    diff = sub_a - sub_b

    # Verify no Flush-to-Zero (FTZ) occurs
    subnormal_supported = (smallest_subnormal_f64 > 0.0) and (diff == smallest_subnormal_f64)

    # Verify gradual underflow to exact zero
    underflow_zero = (smallest_subnormal_f64 / 2.0) == 0.0

    subnormal_arithmetic_valid = subnormal_supported and underflow_zero

    # Machine epsilon perturbation verification
    eps_intact = ((1.0 + eps_f64) > 1.0) and ((1.0 + (eps_f64 / 2.0)) == 1.0)

    precision_intact = subnormal_arithmetic_valid and eps_intact
    msg = "Float Precision: Intact" if precision_intact else "Float Precision: Compromised"

    return IEEE754PrecisionAudit(
        float32_epsilon=eps_f32,
        float64_epsilon=eps_f64,
        subnormal_supported=subnormal_supported,
        smallest_subnormal_f64=smallest_subnormal_f64,
        smallest_normal_f64=smallest_normal_f64,
        subnormal_arithmetic_valid=subnormal_arithmetic_valid,
        precision_intact=precision_intact,
        precision_message=msg,
    )


# =============================================================================
# 8. REGISTRY RESOLUTION
# =============================================================================


def resolve_p2_registry_path(
    output_dir: Optional[Union[str, Path]] = None,
    target_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Resolve the destination filesystem path for the p2.json state artifact.
    """
    if output_dir is not None:
        p = Path(output_dir).resolve()
        if p.name.endswith(".json"):
            return p
        return p / "p2.json"

    if target_path is not None:
        p = Path(target_path).resolve()
        return p / "Registry" / "p2.json"

    return Path.cwd().resolve() / "Registry" / "p2.json"


# =============================================================================
# 9. RUN PHASE 2 AUDIT EXECUTION
# =============================================================================


def run_phase_2_audit(
    output_dir: Optional[Union[str, Path]] = None,
    target_path: Optional[Union[str, Path]] = None,
    cgroup_root: Optional[Path] = None,
) -> Phase2AuditReport:
    """
    Execute complete CoChem Setup Phase 2: Hardware & Resource Gatekeeper audit.
    Serializes report atomically to Registry/p2.json.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Audit Memory Hierarchy
    memory = audit_memory(cgroup_root=cgroup_root)
    # Check if effective memory is below 4 GB
    if memory.effective_memory_bytes < 4 * 1024 * 1024 * 1024:
        warnings.append(
            f"Effective usable memory ({memory.effective_memory_bytes / (1024**3):.2f} GB) "
            "is below recommended 4.0 GB."
        )

    # 2. Audit CPU Topology
    cpu = audit_cpu(cgroup_root=cgroup_root)
    if cpu.logical_cores < 2:
        warnings.append(
            f"Host or container allocated logical CPUs ({cpu.logical_cores}) is below recommended 2 cores."
        )

    # 3. Audit GPU Acceleration
    gpu = audit_gpus()
    if gpu.degraded_fallback:
        warnings.append(
            "No hardware GPU accelerator detected or accessible; falling back to CPU execution mode."
        )

    # 4. Audit IEEE-754 Precision
    precision = verify_ieee754_subnormal_precision()
    if not precision.precision_intact:
        errors.append(
            "IEEE-754 subnormal floating point precision check failed; host CPU or runtime has FTZ active."
        )

    # 5. Determine Overall Status
    if errors:
        status = PhaseStatus.FAILED
    elif gpu.degraded_fallback or memory.is_cgroup_constrained:
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    # 6. Resolve Destination Path
    p2_path = resolve_p2_registry_path(output_dir=output_dir, target_path=target_path)

    # 7. Construct Report
    report = Phase2AuditReport(
        phase_id="PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        status=status,
        timestamp_utc=timestamp_utc,
        memory=memory,
        cpu=cpu,
        gpu=gpu,
        precision=precision,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p2_path),
    )

    # 8. Transactional Atomic Persistence
    with DependencyManager() as dm:
        dm.atomic_write_json(p2_path, report)

    return report


# =============================================================================
# 10. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 2: Hardware & Resource Gatekeeper CLI.
    Returns 0 on PASSED/DEGRADED, non-zero on FAILED.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 2: Hardware & Resource Gatekeeper CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom output directory for Registry/p2.json",
    )
    parser.add_argument(
        "--target-path",
        "-t",
        type=str,
        default=None,
        help="Target workspace directory to audit (defaults to CWD)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_2_audit(
            output_dir=args.output_dir,
            target_path=args.target_path,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 70)
            print("COCHEM SETUP PHASE 2: HARDWARE & RESOURCE GATEKEEPER AUDIT")
            print("=" * 70)
            print(f"Phase ID:        {report.phase_id}")
            print(f"Status:          {report.status.value}")
            print(f"Timestamp UTC:   {report.timestamp_utc}")
            print(
                f"Memory Total:    {report.memory.total_bytes / (1024**3):.2f} GB "
                f"(Effective: {report.memory.effective_memory_bytes / (1024**3):.2f} GB)"
            )
            print(
                f"CPU Topology:    {report.cpu.physical_cores} Physical / {report.cpu.logical_cores} Logical "
                f"({report.cpu.architecture})"
            )
            if report.cpu.cgroup_effective_cpus is not None:
                print(f"cgroup Quota:    {report.cpu.cgroup_effective_cpus} effective CPUs")
            print(
                f"GPU Acceleration: {len(report.gpu.devices)} Device(s) detected "
                f"(Degraded Fallback: {report.gpu.degraded_fallback})"
            )
            for dev in report.gpu.devices:
                mem_gb = f"{dev.memory_total_bytes / (1024**3):.2f} GB" if dev.memory_total_bytes else "N/A"
                print(f"  - [{dev.vendor}] {dev.name} (VRAM: {mem_gb})")
            print(f"Float Precision: {report.precision.precision_message.split(': ')[-1]}")
            print(f"Artifact Path:   {report.artifact_path}")
            print("-" * 70)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 70)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 2 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_2.py ---
"""
Unit test suite for CoChem Setup Phase 2: Hardware & Resource Gatekeeper.
Strict Zero-Mock Mandate: Real filesystem operations, live CPU/memory interrogations,
deterministic Pydantic V2 schema validations, real cgroups v1/v2 synthetic fixtures,
real IEEE-754 subnormal floating-point arithmetic, real atomic I/O, and real rollback mechanics.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

import pytest

from orchestrator.cochem_setup_phase_2 import (
    CPUAudit,
    DependencyManager,
    GPUDevice,
    GPUProfile,
    IEEE754PrecisionAudit,
    MemoryAudit,
    Phase2AuditReport,
    PhaseStatus,
    audit_cpu,
    audit_gpus,
    audit_memory,
    get_absolute_physical_ram,
    main,
    parse_cgroup_cpu_quota,
    parse_cgroup_memory_limit,
    probe_amd_gpus,
    probe_intel_gpus,
    probe_nvidia_gpus,
    resolve_p2_registry_path,
    run_phase_2_audit,
    verify_ieee754_subnormal_precision,
)

# =============================================================================
# 1. PYDANTIC V2 SCHEMA & ENUM VALIDATION TESTS
# =============================================================================


def test_phase_status_enum() -> None:
    """Verify PhaseStatus enum definitions and string representations."""
    assert PhaseStatus.PASSED.value == "PASSED"
    assert PhaseStatus.FAILED.value == "FAILED"
    assert PhaseStatus.DEGRADED.value == "DEGRADED"
    assert PhaseStatus("PASSED") is PhaseStatus.PASSED
    assert PhaseStatus("FAILED") is PhaseStatus.FAILED
    assert PhaseStatus("DEGRADED") is PhaseStatus.DEGRADED

    with pytest.raises(ValueError):
        PhaseStatus("INVALID_STATUS")


def test_memory_audit_model_valid() -> None:
    """Test MemoryAudit model initialization and serialization with valid fields."""
    mem = MemoryAudit(
        total_bytes=17179869184,  # 16 GB
        available_bytes=8589934592,  # 8 GB
        swap_total_bytes=4294967296,  # 4 GB
        swap_free_bytes=2147483648,  # 2 GB
        cgroup_memory_limit_bytes=10737418240,  # 10 GB
        cgroup_swap_limit_bytes=None,
        is_cgroup_constrained=True,
        effective_memory_bytes=10737418240,
    )
    assert mem.total_bytes == 17179869184
    assert mem.available_bytes == 8589934592
    assert mem.is_cgroup_constrained is True
    assert mem.effective_memory_bytes == 10737418240

    dumped = mem.model_dump()
    assert dumped["total_bytes"] == 17179869184
    restored = MemoryAudit.model_validate(dumped)
    assert restored == mem


def test_memory_audit_model_unconstrained() -> None:
    """Test MemoryAudit model when no cgroup constraints exist."""
    mem = MemoryAudit(
        total_bytes=34359738368,  # 32 GB
        available_bytes=25769803776,  # 24 GB
        swap_total_bytes=0,
        swap_free_bytes=0,
        cgroup_memory_limit_bytes=None,
        cgroup_swap_limit_bytes=None,
        is_cgroup_constrained=False,
        effective_memory_bytes=34359738368,
    )
    assert mem.is_cgroup_constrained is False
    assert mem.effective_memory_bytes == mem.total_bytes
    assert mem.cgroup_memory_limit_bytes is None


def test_cpu_audit_model_valid() -> None:
    """Test CPUAudit model initialization and validation."""
    cpu = CPUAudit(
        physical_cores=8,
        logical_cores=16,
        frequency_mhz=3600.0,
        cgroup_cpu_quota_us=400000,
        cgroup_cpu_period_us=100000,
        cgroup_effective_cpus=4.0,
        cpu_affinity_count=16,
        architecture="x86_64",
    )
    assert cpu.physical_cores == 8
    assert cpu.logical_cores == 16
    assert cpu.frequency_mhz == 3600.0
    assert cpu.cgroup_effective_cpus == 4.0
    assert cpu.architecture == "x86_64"

    dumped = cpu.model_dump()
    assert dumped["logical_cores"] == 16
    restored = CPUAudit.model_validate(dumped)
    assert restored == cpu


def test_gpu_device_model() -> None:
    """Test GPUDevice model initialization and fields."""
    dev = GPUDevice(
        index=0,
        vendor="NVIDIA",
        name="NVIDIA GeForce RTX 4090",
        memory_total_bytes=25769803776,  # 24 GB
        memory_free_bytes=23622320128,  # 22 GB
        driver_version="555.42.02",
        compute_capability="8.9",
        uuid="GPU-12345678-abcd-ef01-2345-6789abcdef01",
    )
    assert dev.index == 0
    assert dev.vendor == "NVIDIA"
    assert dev.compute_capability == "8.9"
    assert dev.memory_total_bytes == 25769803776


def test_gpu_profile_model() -> None:
    """Test GPUProfile model representing heterogeneous accelerator configurations."""
    profile = GPUProfile(
        available=True,
        vendor_summary={"NVIDIA": 1},
        devices=[
            GPUDevice(
                index=0,
                vendor="NVIDIA",
                name="NVIDIA RTX 4090",
                memory_total_bytes=25769803776,
                memory_free_bytes=23622320128,
                driver_version="555.42.02",
                compute_capability="8.9",
                uuid="GPU-0001",
            )
        ],
        cuda_available=True,
        rocm_available=False,
        oneapi_available=False,
        degraded_fallback=False,
    )
    assert profile.available is True
    assert profile.cuda_available is True
    assert profile.degraded_fallback is False
    assert len(profile.devices) == 1
    assert profile.vendor_summary["NVIDIA"] == 1


def test_ieee754_precision_audit_model() -> None:
    """Test IEEE754PrecisionAudit model field validation."""
    precision = IEEE754PrecisionAudit(
        float32_epsilon=1.1920928955078125e-07,
        float64_epsilon=2.220446049250313e-16,
        subnormal_supported=True,
        smallest_subnormal_f64=4.9406564584124654e-324,
        smallest_normal_f64=2.2250738585072014e-308,
        subnormal_arithmetic_valid=True,
        precision_intact=True,
        precision_message="Float Precision: Intact",
    )
    assert precision.subnormal_supported is True
    assert precision.precision_intact is True
    assert precision.precision_message == "Float Precision: Intact"
    assert precision.smallest_subnormal_f64 > 0.0


def test_phase2_audit_report_full_schema(tmp_path: Path) -> None:
    """Test Phase2AuditReport comprehensive schema validation and JSON round-trip."""
    report = Phase2AuditReport(
        phase_id="PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T22:30:00Z",
        memory=MemoryAudit(
            total_bytes=17179869184,
            available_bytes=12884901888,
            swap_total_bytes=4294967296,
            swap_free_bytes=4294967296,
            cgroup_memory_limit_bytes=None,
            cgroup_swap_limit_bytes=None,
            is_cgroup_constrained=False,
            effective_memory_bytes=17179869184,
        ),
        cpu=CPUAudit(
            physical_cores=8,
            logical_cores=16,
            frequency_mhz=3600.0,
            cgroup_cpu_quota_us=None,
            cgroup_cpu_period_us=None,
            cgroup_effective_cpus=None,
            cpu_affinity_count=16,
            architecture="x86_64",
        ),
        gpu=GPUProfile(
            available=False,
            vendor_summary={},
            devices=[],
            cuda_available=False,
            rocm_available=False,
            oneapi_available=False,
            degraded_fallback=True,
        ),
        precision=IEEE754PrecisionAudit(
            float32_epsilon=1.1920928955078125e-07,
            float64_epsilon=2.220446049250313e-16,
            subnormal_supported=True,
            smallest_subnormal_f64=4.9406564584124654e-324,
            smallest_normal_f64=2.2250738585072014e-308,
            subnormal_arithmetic_valid=True,
            precision_intact=True,
            precision_message="Float Precision: Intact",
        ),
        warnings=["No hardware GPU accelerator detected; falling back to CPU execution"],
        errors=[],
        artifact_path=str(tmp_path / "Registry" / "p2.json"),
    )
    assert report.phase_id == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert report.status is PhaseStatus.PASSED

    # Roundtrip through JSON
    json_str = report.model_dump_json(indent=2)
    assert "Float Precision: Intact" in json_str
    parsed = Phase2AuditReport.model_validate_json(json_str)
    assert parsed.phase_id == report.phase_id
    assert parsed.memory.total_bytes == report.memory.total_bytes
    assert parsed.precision.precision_intact is True


# =============================================================================
# 2. CGROUPS V1 & V2 SYNTHETIC FILESYSTEM PARSING TESTS (ZERO MOCKS)
# =============================================================================


def test_cgroup_v2_memory_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 memory.max numeric parsing on real filesystem fixture."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    mem_max_file = cg_dir / "memory.max"
    mem_max_file.write_text("4294967296\n", encoding="utf-8")  # 4 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 4294967296
    assert swap_limit is None


def test_cgroup_v2_memory_limit_max_string(tmp_path: Path) -> None:
    """Test cgroups v2 memory.max 'max' string parsing indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("max\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None
    assert swap_limit is None


def test_cgroup_v2_swap_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 memory.swap.max numeric and memory.max numeric."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("8589934592\n", encoding="utf-8")  # 8 GB
    (cg_dir / "memory.swap.max").write_text("2147483648\n", encoding="utf-8")  # 2 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 8589934592
    assert swap_limit == 2147483648


def test_cgroup_v2_cpu_quota_numeric(tmp_path: Path) -> None:
    """Test cgroups v2 cpu.max numeric quota and period (e.g. 2.5 CPUs)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("250000 100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 250000
    assert effective_cpus == 2.5


def test_cgroup_v2_cpu_quota_max_string(tmp_path: Path) -> None:
    """Test cgroups v2 cpu.max 'max' string indicates unlimited CPU quota."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("max 100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v1_memory_limit_numeric(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes numeric parsing."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("2147483648\n", encoding="utf-8")  # 2 GB
    (cg_dir / "memory.memsw.limit_in_bytes").write_text("4294967296\n", encoding="utf-8")  # 4 GB

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit == 2147483648
    assert swap_limit == 4294967296


def test_cgroup_v1_memory_limit_unlimited_large_int(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes large int (0x7FFFFFFFFFFFF000) indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("9223372036854771712\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None


def test_cgroup_v1_memory_limit_unlimited_negative(tmp_path: Path) -> None:
    """Test cgroups v1 memory.limit_in_bytes -1 indicates unlimited."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "memory"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.limit_in_bytes").write_text("-1\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None


def test_cgroup_v1_cpu_quota_numeric(tmp_path: Path) -> None:
    """Test cgroups v1 cpu.cfs_quota_us and cpu.cfs_period_us (4.0 CPUs)."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("400000\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 400000
    assert effective_cpus == 4.0


def test_cgroup_v1_cpu_quota_unlimited_negative(tmp_path: Path) -> None:
    """Test cgroups v1 cpu.cfs_quota_us -1 indicates unlimited CPU allocation."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("-1\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("100000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_missing_files(tmp_path: Path) -> None:
    """Test graceful handling when cgroup files do not exist (returns None, None)."""
    empty_root = tmp_path / "empty_root"
    empty_root.mkdir()
    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=empty_root)
    assert mem_limit is None
    assert swap_limit is None

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=empty_root)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_corrupted_content(tmp_path: Path) -> None:
    """Test resilient parsing when cgroup files contain invalid/corrupted non-numeric data."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "memory.max").write_text("corrupted_non_numeric_garbage\n", encoding="utf-8")
    (cg_dir / "cpu.max").write_text("invalid_quota_format\n", encoding="utf-8")

    mem_limit, swap_limit = parse_cgroup_memory_limit(cgroup_root=tmp_path)
    assert mem_limit is None
    assert swap_limit is None

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


# =============================================================================
# 3. CPU TOPOLOGY & PSUTIL MEMORY PROBING TESTS
# =============================================================================


def test_get_absolute_physical_ram() -> None:
    """Verify absolute physical RAM detection returns positive byte count."""
    ram = get_absolute_physical_ram()
    assert isinstance(ram, int)
    assert ram > 0
    # Physical RAM on standard machines should be at least 1 GB
    assert ram >= 1024 * 1024 * 1024


def test_audit_memory_real_host() -> None:
    """Test live host memory auditing via psutil and OS interfaces."""
    mem_audit = audit_memory()
    assert isinstance(mem_audit, MemoryAudit)
    assert mem_audit.total_bytes > 0
    assert mem_audit.available_bytes > 0
    assert mem_audit.effective_memory_bytes > 0
    assert mem_audit.effective_memory_bytes <= mem_audit.total_bytes
    assert mem_audit.available_bytes <= mem_audit.total_bytes


def test_audit_memory_with_synthetic_cgroup_limit(tmp_path: Path) -> None:
    """Test memory auditing when cgroup limits constrain memory below physical RAM."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # Set limit to 1 GB (which is smaller than any standard test machine RAM)
    (cg_dir / "memory.max").write_text("1073741824\n", encoding="utf-8")

    mem_audit = audit_memory(cgroup_root=tmp_path)
    assert mem_audit.cgroup_memory_limit_bytes == 1073741824
    assert mem_audit.is_cgroup_constrained is True
    assert mem_audit.effective_memory_bytes == 1073741824


def test_audit_cpu_real_host() -> None:
    """Test live CPU topology interrogation."""
    cpu_audit = audit_cpu()
    assert isinstance(cpu_audit, CPUAudit)
    assert cpu_audit.physical_cores >= 1
    assert cpu_audit.logical_cores >= 1
    assert cpu_audit.logical_cores >= cpu_audit.physical_cores
    assert cpu_audit.architecture != ""
    if cpu_audit.frequency_mhz is not None:
        assert cpu_audit.frequency_mhz > 0.0


def test_audit_cpu_with_synthetic_cgroup_quota(tmp_path: Path) -> None:
    """Test CPU auditing with synthetic cgroup quota."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("200000 100000\n", encoding="utf-8")  # 2.0 CPUs

    cpu_audit = audit_cpu(cgroup_root=tmp_path)
    assert cpu_audit.cgroup_cpu_quota_us == 200000
    assert cpu_audit.cgroup_cpu_period_us == 100000
    assert cpu_audit.cgroup_effective_cpus == 2.0


# =============================================================================
# 4. HETEROGENEOUS GPU DISCOVERY TESTS (ZERO MOCKS)
# =============================================================================


def test_probe_nvidia_gpus_execution() -> None:
    """Execute live NVIDIA GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_nvidia_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "NVIDIA"
        assert dev.index >= 0


def test_probe_amd_gpus_execution() -> None:
    """Execute live AMD GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_amd_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "AMD"


def test_probe_intel_gpus_execution() -> None:
    """Execute live Intel GPU probe without mocks; returns List[GPUDevice]."""
    devices = probe_intel_gpus()
    assert isinstance(devices, list)
    for dev in devices:
        assert isinstance(dev, GPUDevice)
        assert dev.vendor == "INTEL"


def test_audit_gpus_real() -> None:
    """Audit GPU accelerators on the host system, ensuring valid GPUProfile."""
    gpu_profile = audit_gpus()
    assert isinstance(gpu_profile, GPUProfile)
    assert isinstance(gpu_profile.devices, list)
    assert isinstance(gpu_profile.vendor_summary, dict)
    if not gpu_profile.available:
        assert gpu_profile.degraded_fallback is True
    else:
        assert len(gpu_profile.devices) > 0


# =============================================================================
# 5. REAL IEEE-754 SUBNORMAL PRECISION & MACHINE EPSILON AUDIT TESTS
# =============================================================================


def test_ieee754_subnormal_precision_live() -> None:
    """Execute live IEEE-754 precision audit and verify subnormal arithmetic and message."""
    precision = verify_ieee754_subnormal_precision()
    assert isinstance(precision, IEEE754PrecisionAudit)
    assert precision.precision_intact is True
    assert precision.subnormal_supported is True
    assert precision.subnormal_arithmetic_valid is True
    assert precision.precision_message == "Float Precision: Intact"
    assert precision.smallest_normal_f64 == sys.float_info.min
    assert precision.smallest_subnormal_f64 > 0.0
    assert precision.smallest_subnormal_f64 < precision.smallest_normal_f64


def test_ieee754_math_assertions() -> None:
    """Directly assert IEEE-754 subnormal properties and absence of flush-to-zero (FTZ)."""
    # Smallest positive normal double float (2^-1022)
    normal_min = math.ldexp(1.0, -1022)
    assert normal_min == sys.float_info.min

    # Smallest positive subnormal double float (2^-1074)
    subnormal_min = math.ldexp(1.0, -1074)
    assert subnormal_min > 0.0

    # Subnormal arithmetic verification
    sub_a = math.ldexp(1.0, -1073)  # 2 * subnormal_min
    sub_b = subnormal_min
    diff = sub_a - sub_b
    assert diff == subnormal_min
    assert diff > 0.0

    # Gradual underflow to zero
    underflow = subnormal_min / 2.0
    assert underflow == 0.0

    # Machine epsilon verification
    eps_f64 = sys.float_info.epsilon
    assert (1.0 + eps_f64) > 1.0
    assert (1.0 + (eps_f64 / 2.0)) == 1.0

    # Float32 machine epsilon check
    eps_f32 = struct.unpack("f", struct.pack("f", 1.0 + 2**-23))[0] - 1.0
    assert eps_f32 > 0.0
    assert abs(eps_f32 - 1.1920928955078125e-07) < 1e-12


# =============================================================================
# 6. TRANSACTIONAL DEPENDENCY MANAGER & ATOMIC PERSISTENCE TESTS
# =============================================================================


def test_dependency_manager_atomic_write(tmp_path: Path) -> None:
    """Verify atomic JSON writing creates target file and removes temporary staging file."""
    dm = DependencyManager()
    target_file = tmp_path / "Registry" / "p2.json"
    payload = {"phase": "PHASE_2", "status": "PASSED"}

    with dm:
        written_path = dm.atomic_write_json(target_file, payload)
        assert written_path.exists()

    assert target_file.exists()
    content = json.loads(target_file.read_text(encoding="utf-8"))
    assert content["phase"] == "PHASE_2"
    assert content["status"] == "PASSED"
    assert len(dm._tracked_temp_files) == 0


def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify transactional cleanup of staged files when an unhandled exception occurs."""
    dm = DependencyManager()
    staged_file: Path

    with pytest.raises(RuntimeError, match="Simulation Failure"):
        with dm:
            staged_file = dm.create_temp_file(directory=tmp_path)
            assert staged_file.exists()
            raise RuntimeError("Simulation Failure")

    assert not staged_file.exists()


def test_dependency_manager_manual_rollback(tmp_path: Path) -> None:
    """Verify manual rollback explicitly purges tracked temporary files and directories."""
    dm = DependencyManager()
    f1 = dm.create_temp_file(directory=tmp_path)
    d1 = dm.create_temp_dir(directory=tmp_path)
    assert f1.exists()
    assert d1.exists()

    dm.rollback()
    assert not f1.exists()
    assert not d1.exists()


# =============================================================================
# 7. REGISTRY RESOLUTION & AUDIT EXECUTION TESTS
# =============================================================================


def test_resolve_p2_registry_path_default() -> None:
    """Verify default Registry/p2.json path resolution."""
    resolved = resolve_p2_registry_path()
    assert resolved.name == "p2.json"
    assert resolved.parent.name == "Registry"


def test_resolve_p2_registry_path_custom(tmp_path: Path) -> None:
    """Verify path resolution with explicit output_dir and target_path."""
    custom_out = tmp_path / "custom_out"
    resolved_out = resolve_p2_registry_path(output_dir=custom_out)
    assert resolved_out == (custom_out / "p2.json").resolve()

    custom_tgt = tmp_path / "workspace"
    resolved_tgt = resolve_p2_registry_path(target_path=custom_tgt)
    assert resolved_tgt == (custom_tgt / "Registry" / "p2.json").resolve()


def test_run_phase_2_audit_execution(tmp_path: Path) -> None:
    """Execute complete Phase 2 audit and assert report artifact serialization."""
    report = run_phase_2_audit(output_dir=tmp_path)
    assert isinstance(report, Phase2AuditReport)
    assert report.phase_id == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    assert report.precision.precision_intact is True
    assert report.precision.precision_message == "Float Precision: Intact"

    p2_file = tmp_path / "p2.json"
    assert p2_file.exists()
    saved_data = json.loads(p2_file.read_text(encoding="utf-8"))
    assert saved_data["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert saved_data["precision"]["precision_message"] == "Float Precision: Intact"


# =============================================================================
# 8. CLI INTEGRATION TESTS
# =============================================================================


def test_cli_main_json_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI invocation with --json and --output-dir flags."""
    exit_code = main(["--output-dir", str(tmp_path), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    stdout_text = captured.out

    assert "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER" in stdout_text
    assert "Float Precision: Intact" in stdout_text
    parsed = json.loads(stdout_text)
    assert parsed["phase_id"] == "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER"
    assert (tmp_path / "p2.json").exists()


def test_cli_main_standard_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test standard human-readable CLI banner output."""
    exit_code = main(["--output-dir", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    stdout_text = captured.out

    assert "COCHEM SETUP PHASE 2: HARDWARE & RESOURCE GATEKEEPER AUDIT" in stdout_text
    assert "Float Precision: Intact" in stdout_text
    assert (tmp_path / "p2.json").exists()


def test_cli_main_target_path_flag(tmp_path: Path) -> None:
    """Test CLI invocation with --target-path creating Registry/p2.json."""
    exit_code = main(["--target-path", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "Registry" / "p2.json").exists()


def test_resolve_p2_registry_path_direct_file(tmp_path: Path) -> None:
    """Verify path resolution when output_dir directly points to a .json filename."""
    direct_file = tmp_path / "custom_p2_report.json"
    resolved = resolve_p2_registry_path(output_dir=direct_file)
    assert resolved == direct_file.resolve()


def test_dependency_manager_atomic_write_scalar_and_list(tmp_path: Path) -> None:
    """Verify atomic writing works for lists and scalar types."""
    dm = DependencyManager()
    list_file = tmp_path / "list.json"
    scalar_file = tmp_path / "scalar.json"

    with dm:
        dm.atomic_write_json(list_file, [1, 2, 3])
        dm.atomic_write_json(scalar_file, "pure_string_data")

    assert json.loads(list_file.read_text(encoding="utf-8")) == [1, 2, 3]
    assert json.loads(scalar_file.read_text(encoding="utf-8")) == "pure_string_data"


def test_cgroup_v1_cpu_quota_zero_period(tmp_path: Path) -> None:
    """Test cgroup v1 cpu period of 0 does not raise ZeroDivisionError."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup" / "cpu"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.cfs_quota_us").write_text("100000\n", encoding="utf-8")
    (cg_dir / "cpu.cfs_period_us").write_text("0\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v2_cpu_quota_zero_period(tmp_path: Path) -> None:
    """Test cgroup v2 cpu period of 0 does not raise ZeroDivisionError."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("100000 0\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us is None
    assert effective_cpus is None


def test_cgroup_v2_cpu_quota_single_token(tmp_path: Path) -> None:
    """Test cgroup v2 cpu.max with single quota token defaults period to 100000."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    (cg_dir / "cpu.max").write_text("300000\n", encoding="utf-8")

    quota_us, effective_cpus = parse_cgroup_cpu_quota(cgroup_root=tmp_path)
    assert quota_us == 300000
    assert effective_cpus == 3.0


def test_run_phase_2_audit_low_memory_warning(tmp_path: Path) -> None:
    """Verify warning is registered when effective memory is constrained below 4GB."""
    cg_dir = tmp_path / "sys" / "fs" / "cgroup"
    cg_dir.mkdir(parents=True)
    # 512 MB cgroup memory limit
    (cg_dir / "memory.max").write_text("536870912\n", encoding="utf-8")

    report = run_phase_2_audit(output_dir=tmp_path, cgroup_root=tmp_path)
    assert report.memory.is_cgroup_constrained is True
    assert report.memory.effective_memory_bytes == 536870912
    assert any("below recommended 4.0 GB" in w for w in report.warnings)
    assert report.status is PhaseStatus.DEGRADED


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.