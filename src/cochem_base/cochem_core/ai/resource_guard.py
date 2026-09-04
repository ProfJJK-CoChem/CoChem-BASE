# cochem_canvas_target: cochem_core/ai/resource_guard.py
"""
CoChem-BASE AI Integrations - RESOURCE_GUARD Hardware Safety Evaluator.

Enforces mathematical memory safety, physical resource constraints, and OS/container-aware
hardware limits before any AI or Large Language Model (LLM) inference engine is instantiated.

Core Responsibilities:
1. Dynamic Hardware and OS Polling:
   - Polls HardwareSchema from $HOME/CoChem_Artifacts/Registry/cochem_system_config.json.
   - On Windows: Queries Win32 Kernel32 GlobalMemoryStatusEx and psutil.
   - On Linux/Containers: Inspects cgroups v1/v2 (/sys/fs/cgroup/memory.max and
     /sys/fs/cgroup/memory/memory.limit_in_bytes) for container memory ceilings.
   - On all platforms: Probes NVIDIA NVML (pynvml) for real-time VRAM allocation and active GPU compute jobs.
2. Active Calculation Engine Interception:
   - Detects running quantum chemistry solvers (ORCA, xTB, CFOUR, AIMNet2, MACE, PySCF, etc.)
     and registered active jobs.
   - Locks local LLM execution if Total RAM < 8.0 GB or VRAM is contested by scientific calculations.
3. Seamless Degradation and Failover:
   - Automatically re-routes intercepted or constrained requests to Tier 2 (EXTERNAL_API)
     or Tier 3 (DRY_RUN) without raising unhandled fatal exceptions.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field

warnings.filterwarnings("ignore", category=FutureWarning, module="pynvml")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*pynvml.*")

logger = logging.getLogger("CoChem.AI.ResourceGuard")

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

DEFAULT_MIN_RAM_GB: float = 8.0
DEFAULT_MIN_AVAILABLE_RAM_GB: float = 2.0
DEFAULT_MIN_VRAM_GB: float = 0.0

CGROUP_V2_MAX_PATH: str = "/sys/fs/cgroup/memory.max"
CGROUP_V1_LIMIT_PATH: str = "/sys/fs/cgroup/memory/memory.limit_in_bytes"

# Known computational chemistry, physics, and machine learning force field solver binaries
CALCULATION_ENGINE_STEMS: set[str] = {
    "orca",
    "orca_chelpg",
    "orca_gstep",
    "orca_scf",
    "orca_vpot",
    "orca_casscf",
    "orca_property",
    "orca_cis",
    "orca_mrci",
    "orca_md",
    "orca_mp2",
    "orca_opt",
    "orca_anfreq",
    "orca_soc",
    "xtb",
    "cfour",
    "aimnet2",
    "mace",
    "mace-off",
    "mace_off",
    "mpirun",
    "mpiexec",
    "pyscf",
    "nwchem",
    "gaussian",
    "g16",
    "g09",
    "qchem",
    "turbomole",
    "molpro",
    "gamess",
    "spycfit",
    "crest",
    "censo",
}


# =============================================================================
# TYPED DECISION MODEL
# =============================================================================

class ResourceGuardDecision(BaseModel):
    """
    Immutable typed decision model output by the RESOURCE_GUARD hardware safety evaluator.
    Enforces rigid memory-safety bounds before routing or initializing AI/LLM models.
    """
    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    allow_local_llm: bool = Field(
        ...,
        description="Whether local LLM weight instantiation is authorized under current hardware bounds"
    )
    execution_mode: str = Field(
        ...,
        description="Assigned execution mode: 'LOCAL_LLM', 'EXTERNAL_API', or 'DRY_RUN'"
    )
    total_ram_gb: float = Field(
        ...,
        ge=0.0,
        description="Total physical host RAM or container RAM ceiling in gigabytes"
    )
    available_ram_gb: float = Field(
        ...,
        ge=0.0,
        description="Real-time available unallocated RAM in gigabytes"
    )
    is_container: bool = Field(
        default=False,
        description="Whether execution is taking place inside a Docker/OCI/LXC container"
    )
    container_ram_limit_gb: Optional[float] = Field(
        default=None,
        description="Enforced cgroups container memory limit in GB, or None if unconstrained"
    )
    vram_gb: float = Field(
        default=0.0,
        ge=0.0,
        description="Total video RAM across detected NVIDIA GPU devices in gigabytes"
    )
    available_vram_gb: float = Field(
        default=0.0,
        ge=0.0,
        description="Real-time available unallocated video RAM in gigabytes"
    )
    gpu_device_count: int = Field(
        default=0,
        ge=0,
        description="Number of detected NVIDIA/CUDA GPU devices"
    )
    active_calculation_detected: bool = Field(
        default=False,
        description="Whether active quantum or classical calculation engines were detected"
    )
    intercepted: bool = Field(
        default=False,
        description="Whether the request was intercepted/overridden due to safety constraints"
    )
    reason: str = Field(
        default="",
        description="Diagnostic explanation for the resource guard verdict and mode assignment"
    )
    hardware_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resolved HardwareSchema configuration payload if available"
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured telemetry, probe data, and diagnostics"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize decision model to standard Python dictionary."""
        return self.model_dump()

    def to_json(self) -> str:
        """Serialize decision model to formatted JSON string."""
        return self.model_dump_json(indent=2)


# =============================================================================
# HARDWARE & OPERATING SYSTEM PROBES
# =============================================================================

def is_container_environment() -> bool:
    """
    Detects whether the current Python runtime is executing inside a containerized environment
    (Docker, Podman, Kubernetes, LXC, GitHub Actions, or VS Code Dev Containers/Codespaces).
    """
    # 1. Check known container indicator filesystem markers
    for indicator in ("/.dockerenv", "/run/.containerenv"):
        try:
            if Path(indicator).exists():
                return True
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    # 2. Check environment variables
    env_vars = ("CONTAINER", "DOCKER_CONTAINER", "KUBERNETES_SERVICE_HOST", "CODESPACES", "GITHUB_ACTIONS")
    for var in env_vars:
        if os.environ.get(var):
            return True

    # 3. Check Linux cgroup process markers
    cgroup_paths = ("/proc/1/cgroup", "/proc/self/cgroup")
    for cgroup_path in cgroup_paths:
        try:
            p = Path(cgroup_path)
            if p.exists() and p.is_file():
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                if any(token in content for token in ("docker", "containerd", "kubepods", "lxc", "pod")):
                    return True
        except Exception as _e:
            logger.debug(f"Ignored exception: {_e}")

    return False


def read_cgroup_memory_limit(
    cgroup_v2_path: Optional[Union[str, Path]] = None,
    cgroup_v1_path: Optional[Union[str, Path]] = None,
) -> Optional[float]:
    """
    Reads container memory limits from Linux cgroups (v2 memory.max or v1 memory.limit_in_bytes).
    Returns the memory limit in gigabytes (GB), or None if unconstrained / non-container host.
    """
    v2_target = Path(cgroup_v2_path) if cgroup_v2_path else Path(CGROUP_V2_MAX_PATH)
    v1_target = Path(cgroup_v1_path) if cgroup_v1_path else Path(CGROUP_V1_LIMIT_PATH)

    # 1. Try cgroups v2 (memory.max)
    try:
        if v2_target.exists() and v2_target.is_file():
            content = v2_target.read_text(encoding="utf-8", errors="ignore").strip()
            if content and content != "max" and content.isdigit():
                bytes_limit = int(content)
                if bytes_limit > 0:
                    return round(bytes_limit / (1024 ** 3), 3)
    except Exception as e:
        logger.debug(f"Failed to read cgroups v2 memory.max at {v2_target}: {e}")

    # 2. Try cgroups v1 (memory.limit_in_bytes)
    try:
        if v1_target.exists() and v1_target.is_file():
            content = v1_target.read_text(encoding="utf-8", errors="ignore").strip()
            if content and content.isdigit():
                bytes_limit = int(content)
                # In cgroups v1, unlimited memory is commonly set to near 2^63 - 1
                if 0 < bytes_limit < 9_000_000_000_000_000_000:
                    return round(bytes_limit / (1024 ** 3), 3)
    except Exception as e:
        logger.debug(f"Failed to read cgroups v1 memory.limit_in_bytes at {v1_target}: {e}")

    return None


def probe_windows_memory() -> Tuple[float, float]:
    """
    Queries Windows Kernel32 GlobalMemoryStatusEx API for exact physical and available RAM.
    Falls back cleanly to psutil if ctypes call fails or is unavailable.
    Returns (total_ram_gb, available_ram_gb).
    """
    if platform.system() == "Windows":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            windll = getattr(ctypes, "windll", None)
            if windll is not None and hasattr(windll, "kernel32"):
                kernel32 = windll.kernel32
                if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_gb = stat.ullTotalPhys / (1024 ** 3)
                    avail_gb = stat.ullAvailPhys / (1024 ** 3)
                    return round(total_gb, 3), round(avail_gb, 3)
        except Exception as e:
            logger.debug(f"Windows GlobalMemoryStatusEx query encountered non-fatal error: {e}")

    # Portable psutil fallback
    try:
        vm = psutil.virtual_memory()
        return round(vm.total / (1024 ** 3), 3), round(vm.available / (1024 ** 3), 3)
    except Exception as e:
        logger.debug(f"psutil virtual_memory query failed: {e}")
        return 0.0, 0.0


def probe_host_memory() -> Tuple[float, float]:
    """
    Probes host system memory dynamically based on active OS platform.
    Returns (total_ram_gb, available_ram_gb).
    """
    if platform.system() == "Windows":
        return probe_windows_memory()

    try:
        vm = psutil.virtual_memory()
        return round(vm.total / (1024 ** 3), 3), round(vm.available / (1024 ** 3), 3)
    except Exception as e:
        logger.debug(f"POSIX memory polling failed: {e}")
        return 0.0, 0.0


def probe_nvidia_vram() -> Tuple[float, float, int, List[Dict[str, Any]]]:
    """
    Polls NVIDIA NVML via pynvml for real-time video memory (total & available) and GPU processes.
    Catches all missing libraries, driver mismatches, and GPU absence gracefully.
    Returns (total_vram_gb, available_vram_gb, gpu_device_count, gpu_processes).
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import pynvml

        pynvml.nvmlInit()
        try:
            device_count = int(pynvml.nvmlDeviceGetCount())
            total_bytes = 0
            free_bytes = 0
            processes: List[Dict[str, Any]] = []

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_bytes += int(mem_info.total)
                free_bytes += int(mem_info.free)

                # Query active compute processes
                try:
                    comp_procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                    for cp in comp_procs:
                        proc_name = "unknown"
                        try:
                            proc_name = psutil.Process(cp.pid).name()
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")
                        processes.append({
                            "device_index": i,
                            "pid": cp.pid,
                            "used_memory_bytes": getattr(cp, "usedGpuMemory", 0),
                            "used_memory_gb": round(getattr(cp, "usedGpuMemory", 0) / (1024 ** 3), 3),
                            "process_name": proc_name,
                            "type": "compute",
                        })
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

                # Query active graphics processes
                try:
                    gfx_procs = pynvml.nvmlDeviceGetGraphicsRunningProcesses(handle)
                    for gp in gfx_procs:
                        proc_name = "unknown"
                        try:
                            proc_name = psutil.Process(gp.pid).name()
                        except Exception as _e:
                            logger.debug(f"Ignored exception: {_e}")
                        processes.append({
                            "device_index": i,
                            "pid": gp.pid,
                            "used_memory_bytes": getattr(gp, "usedGpuMemory", 0),
                            "used_memory_gb": round(getattr(gp, "usedGpuMemory", 0) / (1024 ** 3), 3),
                            "process_name": proc_name,
                            "type": "graphics",
                        })
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

            total_vram_gb = round(total_bytes / (1024 ** 3), 3)
            available_vram_gb = round(free_bytes / (1024 ** 3), 3)
            return total_vram_gb, available_vram_gb, device_count, processes
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
    except Exception as e:
        logger.debug(f"NVIDIA NVML polling unavailable or failed: {e}")
        return 0.0, 0.0, 0, []


# =============================================================================
# ACTIVE CALCULATION & CONFLICT DETECTION
# =============================================================================

def detect_active_calculations(
    config_active_jobs: Optional[Dict[str, Any]] = None,
    scan_process_table: bool = True,
    gpu_processes: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, List[str]]:
    """
    Scans the system for active quantum chemistry or machine learning force field calculation jobs.
    Evaluates:
    1. Active jobs registered in cochem_system_config.json.
    2. Active GPU compute processes tracked via NVML.
    3. Host process table scanning for recognized quantum calculation binaries.
    Returns (active_detected, reason_list).
    """
    active_reasons: List[str] = []

    # 1. Inspect registered active jobs in system config
    if config_active_jobs and isinstance(config_active_jobs, dict):
        for job_id, job_info in config_active_jobs.items():
            if isinstance(job_info, dict):
                status = str(job_info.get("status", "")).strip().lower()
                # If job is not explicitly in an inactive terminal state, consider it active
                if status not in ("completed", "finished", "failed", "cancelled", "terminated", "inactive"):
                    active_reasons.append(
                        f"Registered job '{job_id}' in state '{status or 'active'}'"
                    )
            elif job_info:
                active_reasons.append(f"Registered active job entry '{job_id}'")

    # 2. Inspect active GPU compute processes
    if gpu_processes:
        for gp in gpu_processes:
            pname = gp.get("process_name", "").lower().replace(".exe", "")
            if any(engine_stem in pname for engine_stem in CALCULATION_ENGINE_STEMS):
                active_reasons.append(
                    f"GPU calculation process '{pname}' (PID: {gp.get('pid')}) using {gp.get('used_memory_gb', 0)} GB VRAM"
                )
            elif gp.get("type") == "compute" and gp.get("used_memory_gb", 0) > 0.5:
                active_reasons.append(
                    f"GPU compute process '{pname}' (PID: {gp.get('pid')}) allocating {gp.get('used_memory_gb', 0)} GB VRAM"
                )

    # 3. Inspect host OS process table
    if scan_process_table:
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    pname = str(proc.info.get("name") or "").lower().replace(".exe", "")
                    if pname in CALCULATION_ENGINE_STEMS or any(
                        pname.startswith(stem + "_") or pname == stem for stem in CALCULATION_ENGINE_STEMS
                    ):
                        active_reasons.append(f"Active binary '{pname}' (PID: {proc.info.get('pid')})")
                        continue

                    # Check command line arguments for python invocations of quantum engines
                    cmdline = proc.info.get("cmdline")
                    if cmdline and isinstance(cmdline, list):
                        cmdline_str = " ".join(cmdline).lower()
                        for stem in ("orca", "xtb", "aimnet2", "mace", "pyscf", "spycfit"):
                            if stem in cmdline_str and any(flag in cmdline_str for flag in (".inp", ".py", "run_", "calc")):
                                active_reasons.append(f"Active Python calculation engine invocation matching '{stem}' (PID: {proc.info.get('pid')})")
                                break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as _e:
                    logger.debug(f"Ignored exception: {_e}")
        except Exception as e:
            logger.debug(f"Process table iteration encountered non-fatal error: {e}")

    return bool(active_reasons), active_reasons


# =============================================================================
# CONFIGURATION RESOLUTION
# =============================================================================

def resolve_cochem_system_config(
    config_path: Optional[Union[str, Path]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    """
    Discovers and parses cochem_system_config.json to retrieve the HardwareSchema and active_jobs.
    Follows authoritative resolution hierarchy:
    1. Explicit custom config_path parameter.
    2. COCHEM_CONFIG environment variable.
    3. $HOME/CoChem_Artifacts/Registry/cochem_system_config.json
    4. $HOME/cochem_artifacts/Registry/cochem_system_config.json
    5. $COCHEM_ARTIFACT_DIR/Registry/cochem_system_config.json
    6. Local repository cochem_system_config.json
    Returns (hardware_schema_dict, active_jobs_dict, resolved_path_str).
    Never raises an exception on missing or corrupted files.
    """
    candidates: List[Path] = []

    if config_path:
        candidates.append(Path(os.path.expandvars(str(config_path))).expanduser().resolve())

    env_config = os.environ.get("COCHEM_CONFIG")
    if env_config:
        candidates.append(Path(os.path.expandvars(env_config)).expanduser().resolve())

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        art_path = Path(os.path.expandvars(env_art)).expanduser()
        candidates.append(art_path / "Registry" / "cochem_system_config.json")
        candidates.append(art_path / "cochem_system_config.json")

    home = Path.home()
    candidates.append(home / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json")
    candidates.append(home / "cochem_artifacts" / "Registry" / "cochem_system_config.json")
    candidates.append(home / "CoChem_Artifacts" / "cochem_system_config.json")

    # Repo-relative fallback paths
    current_dir = Path(__file__).resolve().parent
    repo_candidates = [
        current_dir.parent.parent / "cochem_system_config.json",
        current_dir.parent.parent / "Registry" / "cochem_system_config.json",
        Path.cwd() / "cochem_system_config.json",
        Path.cwd() / "Registry" / "cochem_system_config.json",
    ]
    candidates.extend(repo_candidates)

    for target in candidates:
        try:
            if target.exists() and target.is_file():
                content = target.read_text(encoding="utf-8")
                raw_data = json.loads(content)
                if isinstance(raw_data, dict):
                    hardware = raw_data.get("hardware")
                    active_jobs = raw_data.get("active_jobs", {})
                    return (
                        hardware if isinstance(hardware, dict) else None,
                        active_jobs if isinstance(active_jobs, dict) else {},
                        str(target),
                    )
        except Exception as e:
            logger.debug(f"Failed to load or parse candidate system config at {target}: {e}")

    return None, None, None


# =============================================================================
# MAIN RESOURCE GUARD EVALUATION
# =============================================================================

def evaluate_resource_guard(
    config_path: Optional[Union[str, Path]] = None,
    requested_mode: str = "LOCAL_LLM",
    min_ram_gb: float = DEFAULT_MIN_RAM_GB,
    min_vram_gb: float = DEFAULT_MIN_VRAM_GB,
    min_available_ram_gb: float = DEFAULT_MIN_AVAILABLE_RAM_GB,
    fallback_mode: Optional[str] = None,
    custom_cgroup_v2_path: Optional[Union[str, Path]] = None,
    custom_cgroup_v1_path: Optional[Union[str, Path]] = None,
    scan_process_table: bool = True,
    system_config_override: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> ResourceGuardDecision:
    """
    Authoritative hardware safety gateway for AI/LLM models in CoChem-BASE.

    Evaluates host physical RAM, cgroups container limits, real-time VRAM allocation via NVML,
    and active quantum chemistry calculation conflicts to guarantee computational physics priority.

    Interception Rules:
    - If Effective Total RAM < 8.0 GB (or min_ram_gb) -> Override local LLM to False, intercept request.
    - If Active Calculation Detected (process or config) -> Override local LLM to False, intercept request.
    - If Available Host RAM < min_available_ram_gb -> Override local LLM to False, intercept request.
    - If Available VRAM < min_vram_gb -> Override local LLM to False, intercept request.

    Failover Strategy:
    - Fails over seamlessly to EXTERNAL_API (if API key configured) or DRY_RUN mode.
    - Never raises fatal exceptions under any condition.
    """
    try:
        # 1. Probing Host Physical RAM
        host_total_ram_gb, host_available_ram_gb = probe_host_memory()

        # 2. Container & Cgroups Probing
        is_container = is_container_environment()
        cgroup_ram_limit_gb = read_cgroup_memory_limit(
            cgroup_v2_path=custom_cgroup_v2_path,
            cgroup_v1_path=custom_cgroup_v1_path,
        )

        # Calculate effective total RAM (respecting container ceilings)
        if cgroup_ram_limit_gb is not None and cgroup_ram_limit_gb < host_total_ram_gb:
            effective_total_ram_gb = cgroup_ram_limit_gb
            effective_available_ram_gb = min(host_available_ram_gb, cgroup_ram_limit_gb)
        else:
            effective_total_ram_gb = host_total_ram_gb
            effective_available_ram_gb = host_available_ram_gb

        # 3. Probing NVIDIA GPU & VRAM via NVML
        vram_gb, available_vram_gb, gpu_count, gpu_processes = probe_nvidia_vram()

        # 4. Resolve System Configuration & HardwareSchema
        hw_schema: Optional[Dict[str, Any]]
        active_jobs: Optional[Dict[str, Any]]
        resolved_config_path: Optional[str]

        if system_config_override is not None:
            hw_schema = system_config_override.get("hardware")
            active_jobs = system_config_override.get("active_jobs", {})
            resolved_config_path = "[OVERRIDE_IN_MEMORY]"
        else:
            hw_schema, active_jobs, resolved_config_path = resolve_cochem_system_config(config_path)

        # 5. Detect Active Calculations & Conflicts
        active_calc_detected, active_reasons = detect_active_calculations(
            config_active_jobs=active_jobs,
            scan_process_table=scan_process_table,
            gpu_processes=gpu_processes,
        )

        # 6. Evaluate Resource Guard Invariants
        intercept_reasons: List[str] = []

        # Criterion A: Total RAM Safety Threshold (< 8.0 GB default)
        if effective_total_ram_gb < min_ram_gb:
            if cgroup_ram_limit_gb is not None and cgroup_ram_limit_gb < min_ram_gb:
                intercept_reasons.append(
                    f"Container memory ceiling ({cgroup_ram_limit_gb:.2f} GB) is below safety threshold ({min_ram_gb:.2f} GB)"
                )
            else:
                intercept_reasons.append(
                    f"Total system RAM ({effective_total_ram_gb:.2f} GB) is below minimum safety threshold ({min_ram_gb:.2f} GB)"
                )

        # Criterion B: Active Calculation Contention
        if active_calc_detected:
            intercept_reasons.append(
                f"Active calculation detected ({'; '.join(active_reasons)}). VRAM and compute memory locked for chemistry engine execution."
            )

        # Criterion C: Available Real-Time RAM Threshold
        if effective_available_ram_gb < min_available_ram_gb:
            intercept_reasons.append(
                f"Available RAM ({effective_available_ram_gb:.2f} GB) is below runtime threshold ({min_available_ram_gb:.2f} GB)"
            )

        # Criterion D: Minimum VRAM Threshold
        if min_vram_gb > 0.0 and available_vram_gb < min_vram_gb:
            intercept_reasons.append(
                f"Available VRAM ({available_vram_gb:.2f} GB) is below required model allocation ({min_vram_gb:.2f} GB)"
            )

        # 7. Compute Final Verdict & Fallback Execution Mode
        if intercept_reasons:
            intercepted = True
            allow_local_llm = False
            combined_reason = "INTERCEPTED: " + " | ".join(intercept_reasons)

            # Determine failover mode
            if fallback_mode:
                execution_mode = fallback_mode.upper()
            else:
                has_api_key = bool(
                    os.environ.get("GEMINI_API_KEY")
                    or os.environ.get("OPENAI_API_KEY")
                    or os.environ.get("ANTHROPIC_API_KEY")
                    or os.environ.get("COCHEM_AI_API_KEY")
                )
                execution_mode = "EXTERNAL_API" if has_api_key else "DRY_RUN"
        else:
            intercepted = False
            allow_local_llm = True
            execution_mode = requested_mode.upper()
            combined_reason = (
                f"Hardware safety criteria satisfied: RAM ({effective_total_ram_gb:.2f} GB) and "
                f"VRAM ({vram_gb:.2f} GB) meet safety parameters and no conflicting calculations are active."
            )

        telemetry_details = {
            "os_target": platform.system(),
            "resolved_config_path": resolved_config_path,
            "host_total_ram_gb": host_total_ram_gb,
            "host_available_ram_gb": host_available_ram_gb,
            "cgroup_ram_limit_gb": cgroup_ram_limit_gb,
            "gpu_processes": gpu_processes,
            "active_reasons": active_reasons,
            "intercept_reasons": intercept_reasons,
        }

        return ResourceGuardDecision(
            allow_local_llm=allow_local_llm,
            execution_mode=execution_mode,
            total_ram_gb=effective_total_ram_gb,
            available_ram_gb=effective_available_ram_gb,
            is_container=is_container,
            container_ram_limit_gb=cgroup_ram_limit_gb,
            vram_gb=vram_gb,
            available_vram_gb=available_vram_gb,
            gpu_device_count=gpu_count,
            active_calculation_detected=active_calc_detected,
            intercepted=intercepted,
            reason=combined_reason,
            hardware_schema=hw_schema,
            details=telemetry_details,
        )

    except Exception as exc:
        logger.error(f"CRITICAL: Unexpected exception in evaluate_resource_guard: {exc}", exc_info=True)
        # Guarantees seamless failover without raising fatal exceptions
        return ResourceGuardDecision(
            allow_local_llm=False,
            execution_mode=fallback_mode.upper() if fallback_mode else "DRY_RUN",
            total_ram_gb=0.0,
            available_ram_gb=0.0,
            is_container=False,
            container_ram_limit_gb=None,
            vram_gb=0.0,
            available_vram_gb=0.0,
            gpu_device_count=0,
            active_calculation_detected=False,
            intercepted=True,
            reason=f"FATAL_GUARD_FAILOVER: Evaluation aborted due to internal exception: {exc}",
            hardware_schema=None,
            details={"error": str(exc), "type": type(exc).__name__},
        )
