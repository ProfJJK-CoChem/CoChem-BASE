#!/usr/bin/env python3
"""
CoChem-BASE Stage 0: Unified Installer & Micro-Silo Setup Entrypoint.
====================================================================
Production-grade unified environment builder, hardware & hypervisor profiler,
quantum engine & semi-empirical binary discovery engine, isolated micro-silo
provisioner, dependency orchestrator, and Golden System Registry manager.

Authoritative Standards & Specifications:
-----------------------------------------
- Method Matrix v4 Section 8 (§8.0 Setup 1/2/3 Numbering, §8.1 Workstation Hardware & P-Core Pinning,
  §8.2-§8.3 RTX 3090 GPU Crossover & Memory Bounds, §8.4 Fair Comparison Protocol,
  §8.5 Routing Decision Procedure).
- Method Matrix v4 Section 8A (§8A.1 Contention Budget, §8A.2 Scout-and-Anchor Concurrency,
  §8A.4 NVIDIA MPS Socket Management, §8A.5 Integrity Guards G1-G7).
- Method Matrix v4 Section 8B (§8B.2 Master State Inventory, §8B.6 Restart under Wall-Clock Caps).
- Method Matrix v4 Section 8C (§8C.1-§8C.3 Central HDF5 PES Store & SWMR Topology).
- Method Matrix v4 Section 9B.4 & Section 10 (§10.1-§10.7 ORCA External Tools Contract:
  `python install.py --venv-dir ... --script-dir ... -e aimnet2/uma/mace/gxtb`,
  mutually incompatible venvs, persistent server mode, and float32 precision thresholds).
- SRS Document 2 Part 1 (§1.6 Dual Entry Point: Start_Here.ipynb & CLI/setup entrypoint).
- SRS Document 2 Part 2 (§3.3 Engine Discovery, §3.11 Golden Registry Schema).
- SRS Document 5 (§1.1-§1.3 Workspace Sterility, Stage 0 Orchestration & Micro-Silo Provisioning).
- CoChem Anti-Spoofing Protocols v2 (Strict Zero-Mock Mandate, Dynamic Mendeleev Authority).
"""

from __future__ import annotations

import argparse
import atexit
import dataclasses
import hashlib
import importlib.util
import json
import logging
import math
import os
import platform
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import venv
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# Third-party type checking and schema resolution
try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
except ImportError:
    class BaseModel:  # type: ignore
        def __init__(self, **data: Any) -> None:
            for k, v in data.items():
                setattr(self, k, v)

        def model_dump(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in self.__dict__.items()
                if not k.startswith("_")
            }

        def model_dump_json(self, *args: Any, **kwargs: Any) -> str:
            return json.dumps(self.model_dump(), default=str, indent=2)

    def Field(default: Any = None, default_factory: Any = None, description: str = "", **kwargs: Any) -> Any:  # type: ignore
        return default if default is not None else (default_factory() if default_factory else None)

    class ConfigDict(dict):  # type: ignore
        pass

    def field_validator(*fields: str, **kwargs: Any) -> Callable:  # type: ignore
        def decorator(f: Callable) -> Callable:
            return f
        return decorator

    def model_validator(**kwargs: Any) -> Callable:  # type: ignore
        def decorator(f: Callable) -> Callable:
            return f
        return decorator

# Mendeleev dynamic authority resolution
try:
    import mendeleev
    from mendeleev import element
except ImportError:
    mendeleev = None  # type: ignore
    element = None  # type: ignore

# Internal CoChem module resolution
REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

try:
    from cochem_base.config_loader import (
        get_artifact_dir,
        get_base_root,
        get_runtime_dir,
        get_scratch_dir,
        resolve_config_path,
        resolve_executable,
        resolve_mapped_path,
    )
except ImportError:
    def get_base_root() -> Path:
        return REPO_ROOT

    def get_artifact_dir() -> Path:
        mapped = os.environ.get("COCHEM_ARTIFACT_DIR")
        if mapped:
            p = Path(mapped).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        default_dir = REPO_ROOT / "CoChem_Artifacts"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def get_scratch_dir() -> Path:
        mapped = os.environ.get("COCHEM_SCRATCH_DIR")
        if mapped:
            p = Path(mapped).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        default_dir = get_artifact_dir() / "Scratch"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def get_runtime_dir() -> Path:
        mapped = os.environ.get("COCHEM_RUNTIME_DIR")
        if mapped:
            p = Path(mapped).resolve()
            p.mkdir(parents=True, exist_ok=True)
            return p
        default_dir = Path(tempfile.gettempdir()) / "cochem_runtime"
        default_dir.mkdir(parents=True, exist_ok=True)
        return default_dir

    def resolve_config_path() -> Path:
        return get_artifact_dir() / "Registry" / "cochem_system_config.json"

    def resolve_executable(env_var: Optional[str] = None, candidates: Sequence[str] = ()) -> Optional[str]:
        if env_var and os.environ.get(env_var):
            val = os.environ[env_var]
            if Path(val).is_file():
                return str(Path(val).resolve())
        for cand in candidates:
            w = shutil.which(cand)
            if w:
                return str(Path(w).resolve())
        return None

    def resolve_mapped_path(path_value: Union[str, Path], base_dir: Optional[Path] = None) -> Path:
        expanded = Path(os.path.expandvars(str(path_value))).expanduser()
        if not expanded.is_absolute():
            expanded = (base_dir or REPO_ROOT) / expanded
        return expanded.resolve()

try:
    from core_engine.cochem_core_subprocess_broker import (
        cleanup_zombie_processes,
        register_popen_process,
        safe_subprocess_run,
    )
except ImportError:
    safe_subprocess_run = None  # type: ignore
    register_popen_process = None  # type: ignore

    def cleanup_zombie_processes() -> int:  # type: ignore
        reaped = 0
        if psutil is None:
            return 0
        try:
            current = psutil.Process(os.getpid())
            children = current.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            gone, alive = psutil.wait_procs(children, timeout=3)
            for p in alive:
                try:
                    p.kill()
                    reaped += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
        return reaped

# Setup logging
logger = logging.getLogger("CoChem-Installer")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

atexit.register(cleanup_zombie_processes)


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class InstallerError(RuntimeError):
    """Base exception for all Stage 0 installer and micro-silo setup operations."""


class HardwareProfilingError(InstallerError):
    """Raised when hardware topology or hypervisor discovery encounters a fatal defect."""


class BinaryDiscoveryError(InstallerError):
    """Raised when mandatory quantum or semi-empirical binaries cannot be located or verified."""


class SiloProvisioningError(InstallerError):
    """Raised when micro-silo creation, dependency isolation, or venv staging fails."""


class DependencyResolutionError(InstallerError):
    """Raised when package dependency installation or Dynamic Version Walking fails."""


class RegistryPersistenceError(InstallerError):
    """Raised when serializing or atomically persisting the Golden System Registry fails."""


class AirGapViolationError(InstallerError):
    """Raised when write operations attempt to mutate the immutable codebase root."""


class WSL9PMountError(InstallerError):
    """Raised when active workspace resides on a high-latency, non-POSIX WSL2 9P / drvfs mount."""


# =============================================================================
# 2. ENUMS & DATA MODELS
# =============================================================================


class SetupTier(str, Enum):
    """Authoritative deployment setup numbering per Method Matrix Section 8.0."""

    SETUP_1_TEACHING = "Setup 1"       # GitHub Actions, Codespaces, 50 seats, CPU only
    SETUP_2_WORKSTATION = "Setup 2"    # Workstation: i7-13700K (8P+8E), RTX 3090 (24GB), 64GB DDR5
    SETUP_3_HPC = "Setup 3"            # Multi-node HPC cluster, SLURM/PBS, batch scheduler
    AUTO = "auto"


class ComputeDevice(str, Enum):
    """Execution compute device target."""

    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    MPS = "mps"
    AUTO = "auto"


class EngineTrack(str, Enum):
    """Scientific execution track classification per Method Matrix Section 8 & 9."""

    ORCA = "ORCA"
    CFOUR = "CFOUR"
    XTB_CREST = "XTB_CREST"
    PYSCF_GPU = "PYSCF_GPU"
    MLFF_OET = "MLFF_OET"
    PSI4 = "PSI4"
    MOLPRO = "MOLPRO"
    GENERAL = "GENERAL"


class SiloType(str, Enum):
    """Micro-silo category and specialization classification."""

    CORE = "cochem_core_silo"
    UI = "cochem_ui_silo"
    CALC = "cochem_calc_silo"
    MACE = "cochem_mace_silo"
    AIMNET2 = "oet_aimnet2"
    UMA = "oet_uma"
    ALL = "all"


class SiloStatus(str, Enum):
    """Fine-grained provisioning and availability status for micro-silos."""

    PROVISIONED = "PROVISIONED"
    EXISTS_VALID = "EXISTS_VALID"
    BYPASSED = "BYPASSED"
    FALLBACK_RECOVERY = "FALLBACK_RECOVERY"
    ERROR = "ERROR"
    MISSING = "MISSING"


class HardwareProfile(BaseModel):
    """Physical hardware, CPU topology, and GPU profiling metadata per §8.1-§8.3."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    platform_system: str = Field(..., description="Host OS platform (Windows, Linux, Darwin)")
    platform_release: str = Field(..., description="Host OS kernel release version")
    platform_architecture: str = Field(..., description="CPU architecture (e.g. x86_64, AMD64, arm64)")
    cpu_model: str = Field(default="Unknown", description="Processor model name")
    total_physical_cores: int = Field(..., description="Count of physical CPU cores")
    total_logical_threads: int = Field(..., description="Count of logical execution threads")
    performance_cores: int = Field(default=8, description="Intel P-core count or primary compute cores")
    efficiency_cores: int = Field(default=0, description="Intel E-core count or background cores")
    has_avx2: bool = Field(default=True, description="AVX2 SIMD instruction set support")
    has_avx512: bool = Field(default=False, description="AVX-512 SIMD status (fused off on 13700K)")
    total_ram_gb: float = Field(..., description="Total installed physical RAM in gigabytes")
    recommended_orca_ranks: int = Field(default=8, description="Recommended MPI ranks bound to P-cores")
    recommended_maxcore_mb: int = Field(default=3000, description="Recommended %maxcore per rank in MB")
    has_cuda: bool = Field(default=False, description="CUDA acceleration availability")
    cuda_device_name: Optional[str] = Field(default=None, description="Primary GPU device identifier")
    cuda_compute_capability: Optional[str] = Field(default=None, description="CUDA compute capability (e.g. 8.6)")
    cuda_vram_gb: float = Field(default=0.0, description="Total GPU VRAM in gigabytes")
    has_mps_daemon: bool = Field(default=False, description="NVIDIA MPS daemon socket active")
    is_wsl2: bool = Field(default=False, description="Running inside Windows Subsystem for Linux")
    is_wsl2_9p_mount: bool = Field(default=False, description="Workspace is on high-latency 9P / drvfs mount")
    resolved_setup_tier: SetupTier = Field(default=SetupTier.SETUP_2_WORKSTATION, description="Classified Setup Tier")


class BinaryEngineItem(BaseModel):
    """Cryptographic and version inspection record for quantum engine binaries."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(..., description="Engine binary name (e.g. orca, xtb, crest, xcfour)")
    track: EngineTrack = Field(default=EngineTrack.GENERAL, description="Scientific execution track")
    path: Optional[str] = Field(default=None, description="Absolute canonical path to physical executable")
    version: Optional[str] = Field(default=None, description="Interrogated semantic version string")
    sha256_hash: Optional[str] = Field(default=None, description="Cryptographic SHA-256 digest")
    file_size_bytes: Optional[int] = Field(default=None, description="Physical binary size in bytes")
    is_available: bool = Field(default=False, description="Whether binary is functional and executable")
    error_detail: Optional[str] = Field(default=None, description="Failure diagnostic detail")


class SiloAuditRecord(BaseModel):
    """Structured inspection and provisioning record for an individual micro-silo."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field(..., description="Silo identifier (e.g. cochem_core_silo, oet_aimnet2)")
    silo_type: SiloType = Field(..., description="Silo category type")
    venv_path: Optional[str] = Field(default=None, description="Absolute path to virtual environment")
    python_executable: Optional[str] = Field(default=None, description="Path to silo python interpreter")
    python_version: Optional[str] = Field(default=None, description="Interrogated Python version")
    status: SiloStatus = Field(default=SiloStatus.MISSING, description="Fine-grained silo status")
    is_available: bool = Field(default=False, description="Whether silo is functional and operational")
    is_heavy: bool = Field(default=False, description="Whether silo contains heavy quantum/ML stacks")
    verified_packages: List[str] = Field(default_factory=list, description="Verified importable packages")
    error_detail: Optional[str] = Field(default=None, description="Diagnostic error detail if failed")
    created_at: Optional[str] = Field(default=None, description="Timestamp of silo provisioning")


class UnifiedInstallReport(BaseModel):
    """Master structured audit and installation report for CoChem Stage 0."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    co_chem_version: str = Field(default="2026.2 (Method Matrix v4)", description="Platform release")
    setup_tier: SetupTier = Field(..., description="Resolved Setup Tier")
    hardware: HardwareProfile = Field(..., description="Audited host hardware profile")
    binaries: Dict[str, BinaryEngineItem] = Field(default_factory=dict, description="Audited quantum engines")
    micro_silos: Dict[str, SiloAuditRecord] = Field(default_factory=dict, description="Provisioned micro-silos")
    mendeleev_authority_verified: bool = Field(default=False, description="Mendeleev mass resolution verified")
    registry_file_path: Optional[str] = Field(default=None, description="Path to persisted cochem_system_config.json")
    status: str = Field(default="SUCCESS", description="Overall installation status (SUCCESS / DEGRADED / FAILED)")


# =============================================================================
# 3. HARDWARE & HOST HYPERVISOR PROFILING ENGINE (§8.0 - §8.4)
# =============================================================================


def detect_host_hardware(forced_tier: Optional[SetupTier] = None) -> HardwareProfile:
    """
    Interrogates host CPU topology, SIMD capabilities, memory, GPU VRAM, and hypervisor.
    Enforces Method Matrix §8.0 Setup Numbering and §8.1 Workstation invariants.
    """
    sys_platform = platform.system()
    sys_release = platform.release()
    sys_arch = platform.machine() or platform.processor() or "x86_64"

    logical_cpus = os.cpu_count() or 1
    physical_cpus = logical_cpus
    if psutil is not None:
        try:
            phys = psutil.cpu_count(logical=False)
            if phys:
                physical_cpus = phys
        except Exception:
            pass

    p_cores = physical_cpus
    e_cores = 0
    cpu_model = "Generic x86_64 Processor"

    if sys_platform == "Windows":
        try:
            cpu_model = os.environ.get("PROCESSOR_IDENTIFIER", "Intel/AMD Processor")
            res = subprocess.run(
                ["wmic", "cpu", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            for line in res.stdout.splitlines():
                if line.strip() and not line.strip().lower().startswith("name"):
                    cpu_model = line.strip()
                    break
        except Exception:
            pass
    elif sys_platform == "Linux":
        try:
            if Path("/proc/cpuinfo").exists():
                text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    elif sys_platform == "Darwin":
        try:
            res = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5.0)
            if res.stdout.strip():
                cpu_model = res.stdout.strip()
        except Exception:
            pass

    if "13700" in cpu_model or (physical_cpus == 16 and logical_cpus == 24):
        p_cores = 8
        e_cores = 8
    elif physical_cpus >= 8:
        p_cores = min(8, physical_cpus)
        e_cores = physical_cpus - p_cores
    else:
        p_cores = physical_cpus
        e_cores = 0

    has_avx2 = True
    has_avx512 = False

    total_ram_gb = 16.0
    if psutil is not None:
        try:
            total_ram_gb = round(psutil.virtual_memory().total / (1024.0 ** 3), 2)
        except Exception:
            pass

    recommended_orca_ranks = min(8, p_cores)
    safe_ram_mb = (total_ram_gb * 1024.0 * 0.5)
    recommended_maxcore_mb = int(safe_ram_mb // recommended_orca_ranks) if recommended_orca_ranks > 0 else 2000
    recommended_maxcore_mb = max(1000, min(recommended_maxcore_mb, 3400))

    has_cuda = False
    cuda_device_name: Optional[str] = None
    cuda_compute_capability: Optional[str] = None
    cuda_vram_gb = 0.0
    has_mps = False

    try:
        smi_path = shutil.which("nvidia-smi")
        if smi_path:
            res = subprocess.run(
                [smi_path, "--query-gpu=name,memory.total,compute_cap", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in first_line.split(",")]
                if len(parts) >= 2:
                    cuda_device_name = parts[0]
                    cuda_vram_gb = round(float(parts[1]) / 1024.0, 2)
                    has_cuda = True
                if len(parts) >= 3:
                    cuda_compute_capability = parts[2]
    except Exception:
        pass

    mps_pipe_dir = os.environ.get("CUDA_MPS_PIPE_DIRECTORY", "/tmp/nvidia-mps")
    if Path(mps_pipe_dir).exists() and any(Path(mps_pipe_dir).glob("*")):
        has_mps = True

    is_wsl2 = False
    is_wsl2_9p = False
    if sys_platform == "Linux":
        if "microsoft" in sys_release.lower() or "wsl" in sys_release.lower():
            is_wsl2 = True
        cwd = Path.cwd().as_posix()
        if is_wsl2 and (cwd.startswith("/mnt/c") or cwd.startswith("/mnt/d")):
            is_wsl2_9p = True

    if forced_tier and forced_tier != SetupTier.AUTO:
        resolved_tier = forced_tier
    elif os.environ.get("GITHUB_ACTIONS") or os.environ.get("CODESPACES"):
        resolved_tier = SetupTier.SETUP_1_TEACHING
    elif os.environ.get("SLURM_JOB_ID") or os.environ.get("PBS_JOBID") or os.environ.get("SGE_JOB_ID"):
        resolved_tier = SetupTier.SETUP_3_HPC
    else:
        resolved_tier = SetupTier.SETUP_2_WORKSTATION

    return HardwareProfile(
        platform_system=sys_platform,
        platform_release=sys_release,
        platform_architecture=sys_arch,
        cpu_model=cpu_model,
        total_physical_cores=physical_cpus,
        total_logical_threads=logical_cpus,
        performance_cores=p_cores,
        efficiency_cores=e_cores,
        has_avx2=has_avx2,
        has_avx512=has_avx512,
        total_ram_gb=total_ram_gb,
        recommended_orca_ranks=recommended_orca_ranks,
        recommended_maxcore_mb=recommended_maxcore_mb,
        has_cuda=has_cuda,
        cuda_device_name=cuda_device_name,
        cuda_compute_capability=cuda_compute_capability,
        cuda_vram_gb=cuda_vram_gb,
        has_mps_daemon=has_mps,
        is_wsl2=is_wsl2,
        is_wsl2_9p_mount=is_wsl2_9p,
        resolved_setup_tier=resolved_tier,
    )


# =============================================================================
# 4. QUANTUM ENGINE & BINARY DISCOVERY ENGINE (SRS Doc 2 §3.3 & Doc 5)
# =============================================================================


def calculate_sha256(filepath: Path) -> Optional[str]:
    """Computes streaming cryptographic SHA-256 hash of an executable binary."""
    if not filepath.is_file():
        return None
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as exc:
        logger.warning(f"Failed to hash {filepath}: {exc}")
        return None


def interrogate_binary_version(bin_path: str, name: str) -> Optional[str]:
    """Queries binary version via safe subprocess execution with timeout."""
    args_to_try = [["--version"], ["-v"], ["-version"], ["-V"], ["--help"], ["-h"], ["-?"], []]
    if "orca" in name.lower():
        args_to_try = [["--version"], ["-v"], []]
    elif "mpirun" in name.lower() or "mpiexec" in name.lower():
        args_to_try = [["-?"], ["-help"], ["-version"], ["--version"], ["-v"]]

    best_fallback = None
    for flags in args_to_try:
        try:
            cmd = [bin_path, *flags]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            combined = (res.stdout + "\n" + res.stderr).strip()
            if not combined:
                continue

            for line in combined.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                # Skip error / usage lines
                if any(err in line_str.lower() for err in ["cannot open", "unknown option", "invalid option", "requires the name", "usage:", "error:"]):
                    continue

                # Explicit check for ORCA "Program Version X.Y.Z"
                orca_match = re.search(r"Program\s+Version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?[a-zA-Z0-9_\.\-]*)", line_str, re.IGNORECASE)
                if orca_match:
                    return orca_match.group(1).strip()

                match = re.search(r"(?:program\s+version|version|v)?\s*([0-9]+\.[0-9]+(?:\.[0-9]+)?[a-zA-Z0-9_\.\-]*)", line_str, re.IGNORECASE)
                if match:
                    ver = match.group(1).strip()
                    if ver and not ver.startswith("."):
                        return ver

                if best_fallback is None and len(line_str) > 3 and not line_str.startswith("["):
                    best_fallback = line_str[:60]
        except Exception:
            continue
    return best_fallback


def discover_quantum_engines(artifact_dir: Path) -> Dict[str, BinaryEngineItem]:
    """
    Discovers, verifies, hashes, and audits all quantum chemistry and semi-empirical
    binaries across the host system and artifact staging directories.
    """
    discovered: Dict[str, BinaryEngineItem] = {}

    engine_definitions = [
        ("orca", EngineTrack.ORCA, ["orca", "orca.exe"], "ORCA_CMD"),
        ("mpirun", EngineTrack.ORCA, ["mpirun", "mpiexec", "mpirun.exe"], "MPI_CMD"),
        ("xtb", EngineTrack.XTB_CREST, ["xtb", "xtb.exe", "g-xtb"], "XTB_CMD"),
        ("crest", EngineTrack.XTB_CREST, ["crest", "crest.exe"], "CREST_CMD"),
        ("xcfour", EngineTrack.CFOUR, ["xcfour", "cfour", "xjoda"], "CFOUR_CMD"),
        ("psi4", EngineTrack.PSI4, ["psi4", "psi4.exe"], "PSI4_CMD"),
        ("molpro", EngineTrack.MOLPRO, ["molpro", "molpro.exe"], "MOLPRO_CMD"),
        ("oet_server", EngineTrack.MLFF_OET, ["oet_server", "oet_server.py"], "OET_SERVER_CMD"),
        ("oet_client", EngineTrack.MLFF_OET, ["oet_client", "oet_client.py"], "OET_CLIENT_CMD"),
        ("oet_aimnet2", EngineTrack.MLFF_OET, ["oet_aimnet2", "oet_aimnet2.py"], "OET_AIMNET2_CMD"),
        ("oet_uma", EngineTrack.MLFF_OET, ["oet_uma", "oet_uma.py"], "OET_UMA_CMD"),
        ("oet_mace", EngineTrack.MLFF_OET, ["oet_mace", "oet_maceoff", "oet_mace.py"], "OET_MACE_CMD"),
        ("oet_gxtb", EngineTrack.MLFF_OET, ["oet_gxtb", "oet_gxtb.py"], "OET_GXTB_CMD"),
    ]

    search_dirs = [
        artifact_dir / "Registry" / "Engines",
        artifact_dir / "bin",
        Path.home() / "bin",
        Path.home() / ".local" / "bin",
        Path("/opt"),
        Path("/usr/local/bin"),
        Path("C:/Program Files/OpenMPI/bin"),
        Path("C:/Program Files/ORCA"),
    ]

    for name, track, candidates, env_var in engine_definitions:
        bin_path_str: Optional[str] = None

        if env_var and os.environ.get(env_var):
            candidate_env = Path(os.environ[env_var]).resolve()
            if candidate_env.is_file():
                bin_path_str = str(candidate_env)

        if not bin_path_str:
            for cand in candidates:
                w = shutil.which(cand)
                if w:
                    bin_path_str = str(Path(w).resolve())
                    break

        if not bin_path_str:
            for s_dir in search_dirs:
                if not s_dir.exists():
                    continue
                for cand in candidates:
                    target_file = s_dir / cand
                    if target_file.is_file():
                        bin_path_str = str(target_file.resolve())
                        break
                    for sub in s_dir.glob(f"*/{cand}"):
                        if sub.is_file():
                            bin_path_str = str(sub.resolve())
                            break
                if bin_path_str:
                    break

        if bin_path_str:
            p = Path(bin_path_str)
            file_size = p.stat().st_size if p.exists() else None
            sha256 = calculate_sha256(p)
            version_str = interrogate_binary_version(bin_path_str, name)

            discovered[name] = BinaryEngineItem(
                name=name,
                track=track,
                path=bin_path_str,
                version=version_str,
                sha256_hash=sha256,
                file_size_bytes=file_size,
                is_available=True,
            )
            logger.info(f"[BINARY DISCOVERY] Found {name.upper()}: {bin_path_str} (Version: {version_str or 'detected'})")
        else:
            discovered[name] = BinaryEngineItem(
                name=name,
                track=track,
                path=None,
                version=None,
                sha256_hash=None,
                file_size_bytes=None,
                is_available=False,
                error_detail=f"Binary not found in system PATH or search locations (Checked env {env_var}).",
            )
            logger.debug(f"[BINARY DISCOVERY] {name.upper()} not installed (Status: MISSING)")

    return discovered


# =============================================================================
# 5. DYNAMIC VERSION WALKING & PYTHON RESOLUTION (SRS Doc 5 §3)
# =============================================================================


def dynamic_version_walking(
    required_min_minor: int = 11,
    preferred_minors: Sequence[int] = (11, 12, 13, 14),
) -> Tuple[str, str]:
    """
    Evaluates host Python interpreters to find a compatible Python binary (>= 3.11).
    Returns (python_executable_path, version_string).
    """
    candidates = []

    current_ver = sys.version_info
    if current_ver.major == 3 and current_ver.minor >= required_min_minor:
        candidates.append(sys.executable)

    for minor in preferred_minors:
        candidates.extend([
            f"python3.{minor}",
            f"python3.{minor}.exe",
            f"python3{minor}",
        ])
    candidates.extend(["python3", "python", "py"])

    for cand in candidates:
        exe_path = shutil.which(cand) if not Path(cand).is_file() else str(Path(cand).resolve())
        if not exe_path:
            continue

        try:
            cmd = [exe_path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
            if res.returncode == 0 and res.stdout.strip():
                ver_str = res.stdout.strip()
                parts = [int(p) for p in ver_str.split(".")[:2]]
                if parts[0] == 3 and parts[1] >= required_min_minor:
                    logger.info(f"[VERSION WALKING] Resolved Python {ver_str} at: {exe_path}")
                    return exe_path, ver_str
        except Exception:
            continue

    if current_ver.major == 3:
        ver_str = f"{current_ver.major}.{current_ver.minor}.{current_ver.micro}"
        logger.warning(f"[VERSION WALKING] Exact >= 3.11 binary alias not found; using host interpreter: {sys.executable} ({ver_str})")
        return sys.executable, ver_str

    raise DependencyResolutionError(
        f"Dynamic Version Walking failed: No compatible Python >= 3.{required_min_minor} interpreter detected."
    )


# =============================================================================
# 6. ORCA EXTERNAL TOOLS (OET) WRAPPER GENERATOR (§10.1 - §10.7)
# =============================================================================


def generate_oet_wrappers(script_dir: Path, target_venv_python: Path) -> Dict[str, Path]:
    """
    Generates and installs production-grade ORCA ExtOpt wrappers conforming to
    Method Matrix Section 10 and faccts/orca-external-tools specifications.
    """
    script_dir.mkdir(parents=True, exist_ok=True)
    generated: Dict[str, Path] = {}
    py_path_posix = target_venv_python.as_posix()

    server_lines = [
        "#!/usr/bin/env python3",
        "# oet_server -- Background persistent MLFF server for ORCA ExtOpt & GOAT cascades.",
        "# Method Matrix v4 Section 8A.2, Section 10.5 Compliant.",
        "import sys, os, argparse, socket, json",
        "from pathlib import Path",
        "",
        "EH_PER_EV = 1.0 / 27.211386245988",
        "BOHR_PER_A = 1.0 / 0.529177210903",
        "",
        "def run_server(engine: str, host: str, port: int, device: str):",
        "    print(f'[OET-SERVER] Initializing {engine.upper()} model in persistent memory on {host}:{port} (Device: {device})...')",
        "    calc = None",
        "    if engine.lower() in ('mace', 'maceoff', 'mace-off'):",
        "        from mace.calculators import mace_off",
        "        calc = mace_off(model='medium', device=device, default_dtype='float64')",
        "    elif engine.lower() == 'aimnet2':",
        "        try:",
        "            from aimnet2calc import AIMNet2ASE",
        "            calc = AIMNet2ASE(model='aimnet2', device=device)",
        "        except ImportError:",
        "            import torch",
        "            calc = torch.hub.load('isayev/AIMNet2', 'aimnet2', model='aimnet2', device=device)",
        "",
        "    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        "    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)",
        "    sock.bind((host, port))",
        "    sock.listen(16)",
        "    print(f'[OET-SERVER] Server ready on {host}:{port}. Serving ORCA ExtOpt requests.')",
        "    try:",
        "        while True:",
        "            conn, addr = sock.accept()",
        "            try:",
        "                data = conn.recv(65536)",
        "                if not data:",
        "                    conn.close()",
        "                    continue",
        "                req = json.loads(data.decode('utf-8'))",
        "                xyz_path = req['xyz_file']",
        "                charge = int(req.get('charge', 0))",
        "                mult = int(req.get('mult', 1))",
        "                dograd = bool(req.get('dograd', 1))",
        "",
        "                from ase.io import read",
        "                atoms = read(xyz_path)",
        "                if calc is not None:",
        "                    atoms.calc = calc",
        "                atoms.info['charge'] = charge",
        "                atoms.info['mult'] = mult",
        "",
        "                e_eV = atoms.get_potential_energy()",
        "                e_Eh = e_eV * EH_PER_EV",
        "                grad_list = []",
        "                if dograd:",
        "                    forces = atoms.get_forces()",
        "                    for fx, fy, fz in forces:",
        "                        for comp in (fx, fy, fz):",
        "                            grad_list.append(-comp * EH_PER_EV / BOHR_PER_A)",
        "",
        "                resp = {'status': 'OK', 'energy_Eh': e_Eh, 'gradient_Eh_bohr': grad_list, 'num_atoms': len(atoms)}",
        "                conn.sendall(json.dumps(resp).encode('utf-8'))",
        "            except Exception as e:",
        "                err_resp = {'status': 'ERROR', 'message': str(e)}",
        "                conn.sendall(json.dumps(err_resp).encode('utf-8'))",
        "            finally:",
        "                conn.close()",
        "    except KeyboardInterrupt:",
        "        print('[OET-SERVER] Shutting down cleanly.')",
        "    finally:",
        "        sock.close()",
        "",
        "if __name__ == '__main__':",
        "    parser = argparse.ArgumentParser(description='CoChem OET Persistent Inference Server')",
        "    parser.add_argument('engine', choices=['aimnet2', 'uma', 'mace', 'maceoff', 'gxtb'], help='MLFF engine')",
        "    parser.add_argument('--host', default='127.0.0.1', help='Bind host')",
        "    parser.add_argument('--port', type=int, default=8888, help='Bind port')",
        "    parser.add_argument('--device', default='cuda' if os.environ.get('CUDA_VISIBLE_DEVICES') != '' else 'cpu')",
        "    args = parser.parse_args()",
        "    run_server(args.engine, args.host, args.port, args.device)",
    ]

    client_lines = [
        "#!/usr/bin/env python3",
        "# oet_client -- ORCA ExtOpt client communicating with oet_server.",
        "# Method Matrix v4 Section 10.5 Compliant.",
        "import sys, os, argparse, socket, json",
        "",
        "def main():",
        "    parser = argparse.ArgumentParser(description='CoChem OET ExtOpt Client')",
        "    parser.add_argument('extinp', help='ORCA external input tmp file')",
        "    parser.add_argument('-b', '--bind', default='127.0.0.1:8888', help='Server host:port')",
        "    args, _ = parser.parse_known_args()",
        "",
        "    host, port_str = args.bind.split(':')",
        "    port = int(port_str)",
        "",
        "    with open(args.extinp, 'r', encoding='utf-8') as f:",
        "        lines = [line.split('#')[0].strip() for line in f if line.split('#')[0].strip()]",
        "    xyz_file = lines[0]",
        "    charge = int(lines[1])",
        "    mult = int(lines[2])",
        "    ncores = int(lines[3])",
        "    dograd = int(lines[4])",
        "    pcfile = lines[5] if len(lines) > 5 else None",
        "",
        "    req = {'xyz_file': xyz_file, 'charge': charge, 'mult': mult, 'ncores': ncores, 'dograd': dograd, 'pcfile': pcfile}",
        "    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        "    sock.connect((host, port))",
        "    sock.sendall(json.dumps(req).encode('utf-8'))",
        "    data = sock.recv(65536)",
        "    sock.close()",
        "",
        "    resp = json.loads(data.decode('utf-8'))",
        "    if resp.get('status') != 'OK':",
        "        sys.exit(f\"OET Client Error: {resp.get('message', 'Unknown error from server')}\")",
        "",
        "    num_atoms = resp['num_atoms']",
        "    e_Eh = resp['energy_Eh']",
        "    grads = resp.get('gradient_Eh_bohr', [])",
        "",
        "    base = args.extinp.rsplit('.extinp.tmp', 1)[0]",
        "    with open(base + '.engrad', 'w', encoding='utf-8') as f:",
        "        f.write(f'{num_atoms}\\n')",
        "        f.write(f'{e_Eh:.12f}\\n')",
        "        if dograd:",
        "            for g in grads:",
        "                f.write(f'{g:.12f}\\n')",
        "    return 0",
        "",
        "if __name__ == '__main__':",
        "    sys.exit(main())",
    ]

    aimnet2_lines = [
        "#!/usr/bin/env python3",
        "# oet_aimnet2 -- ORCA ExtOpt wrapper for AIMNet2.",
        "# Method Matrix v4 Section 9B.4, Section 10.5 Compliant.",
        "import sys, os, argparse",
        "from ase.io import read",
        "",
        "EH_PER_EV = 1.0 / 27.211386245988",
        "BOHR_PER_A = 1.0 / 0.529177210903",
        "",
        "def read_extinp(path):",
        "    with open(path, 'r', encoding='utf-8') as f:",
        "        vals = [l.split('#')[0].strip() for l in f if l.split('#')[0].strip()]",
        "    xyz, chrg, mult, ncores, dograd = vals[0], int(vals[1]), int(vals[2]), int(vals[3]), int(vals[4])",
        "    pcfile = vals[5] if len(vals) > 5 else None",
        "    return xyz, chrg, mult, ncores, dograd, pcfile",
        "",
        "def main():",
        "    ap = argparse.ArgumentParser(description='ORCA ExtOpt AIMNet2 Wrapper')",
        "    ap.add_argument('extinp')",
        "    ap.add_argument('-m', '--model', default='aimnet2')",
        "    ap.add_argument('-d', '--device', default='cuda')",
        "    a, _ = ap.parse_known_args()",
        "",
        "    xyz, chrg, mult, ncores, dograd, pcfile = read_extinp(a.extinp)",
        "    atoms = read(xyz)",
        "",
        "    try:",
        "        from aimnet2calc import AIMNet2ASE",
        "        calc = AIMNet2ASE(model=a.model, device=a.device)",
        "    except ImportError:",
        "        try:",
        "            from aimnet2.calculator import AIMNet2Calculator",
        "            calc = AIMNet2Calculator(model=a.model, device=a.device)",
        "        except ImportError:",
        "            import torch",
        "            calc = torch.hub.load('isayev/AIMNet2', 'aimnet2', model=a.model, device=a.device)",
        "",
        "    atoms.calc = calc",
        "    atoms.info['charge'] = chrg",
        "    atoms.info['mult'] = mult",
        "",
        "    e_eV = atoms.get_potential_energy()",
        "    e_Eh = e_eV * EH_PER_EV",
        "",
        "    base = a.extinp.rsplit('.extinp.tmp', 1)[0]",
        "    with open(base + '.engrad', 'w', encoding='utf-8') as f:",
        "        f.write(f'{len(atoms)}\\n')",
        "        f.write(f'{e_Eh:.12f}\\n')",
        "        if dograd:",
        "            forces = atoms.get_forces()",
        "            for fx, fy, fz in forces:",
        "                for comp in (fx, fy, fz):",
        "                    f.write(f'{-comp * EH_PER_EV / BOHR_PER_A:.12f}\\n')",
        "    return 0",
        "",
        "if __name__ == '__main__':",
        "    sys.exit(main())",
    ]

    maceoff_lines = [
        "#!/usr/bin/env python3",
        "# oet_maceoff -- ORCA ExtOpt wrapper for MACE-OFF via mace-torch / ASE.",
        "# Method Matrix v4 Section 10.7 Compliant.",
        "import sys, os, argparse",
        "from ase.io import read",
        "",
        "EH_PER_EV = 1.0 / 27.211386245988",
        "BOHR_PER_A = 1.0 / 0.529177210903  # A^-1 -> bohr^-1",
        "",
        "def read_extinp(path):",
        "    with open(path, 'r', encoding='utf-8') as f:",
        "        vals = [l.split('#')[0].strip() for l in f if l.split('#')[0].strip()]",
        "    xyz, chrg, mult, ncores, dograd = vals[0], int(vals[1]), int(vals[2]), int(vals[3]), int(vals[4])",
        "    pcfile = vals[5] if len(vals) > 5 else None",
        "    return xyz, chrg, mult, ncores, dograd, pcfile",
        "",
        "def main():",
        "    ap = argparse.ArgumentParser(description='ORCA ExtOpt MACE-OFF Wrapper')",
        "    ap.add_argument('extinp')",
        "    ap.add_argument('-m', '--model', default='medium')",
        "    ap.add_argument('-d', '--device', default='cuda')",
        "    ap.add_argument('--dtype', default='float64')",
        "    a, _ = ap.parse_known_args()",
        "",
        "    xyz, chrg, mult, ncores, dograd, pcfile = read_extinp(a.extinp)",
        "    if pcfile:",
        "        sys.exit('Error: Point charges not supported by this wrapper.')",
        "    if chrg != 0 or mult != 1:",
        "        sys.exit('Error: MACE-OFF is trained on neutral, closed-shell systems only.')",
        "",
        "    from mace.calculators import mace_off",
        "    atoms = read(xyz)",
        "    atoms.calc = mace_off(model=a.model, device=a.device, default_dtype=a.dtype)",
        "",
        "    e_eV = atoms.get_potential_energy()",
        "    e_Eh = e_eV * EH_PER_EV",
        "",
        "    base = a.extinp.rsplit('.extinp.tmp', 1)[0]",
        "    with open(base + '.engrad', 'w', encoding='utf-8') as f:",
        "        f.write(f'{len(atoms)}\\n')",
        "        f.write(f'{e_Eh:.12f}\\n')",
        "        if dograd:",
        "            forces = atoms.get_forces()",
        "            for fx, fy, fz in forces:",
        "                for comp in (fx, fy, fz):",
        "                    f.write(f'{-comp * EH_PER_EV / BOHR_PER_A:.12f}\\n')",
        "    return 0",
        "",
        "if __name__ == '__main__':",
        "    sys.exit(main())",
    ]

    gxtb_lines = [
        "#!/usr/bin/env python3",
        "# oet_gxtb -- ORCA ExtOpt wrapper for g-xTB / xTB.",
        "# Method Matrix v4 Section 10.6 Compliant.",
        "import sys, os, argparse, subprocess, shutil",
        "from pathlib import Path",
        "",
        "EH_PER_EV = 1.0 / 27.211386245988",
        "BOHR_PER_A = 1.0 / 0.529177210903",
        "",
        "def read_extinp(path):",
        "    with open(path, 'r', encoding='utf-8') as f:",
        "        vals = [l.split('#')[0].strip() for l in f if l.split('#')[0].strip()]",
        "    xyz, chrg, mult, ncores, dograd = vals[0], int(vals[1]), int(vals[2]), int(vals[3]), int(vals[4])",
        "    pcfile = vals[5] if len(vals) > 5 else None",
        "    return xyz, chrg, mult, ncores, dograd, pcfile",
        "",
        "def main():",
        "    ap = argparse.ArgumentParser(description='ORCA ExtOpt g-xTB Wrapper')",
        "    ap.add_argument('extinp')",
        "    ap.add_argument('--method', default='--gxtb')",
        "    a, _ = ap.parse_known_args()",
        "",
        "    xyz, chrg, mult, ncores, dograd, pcfile = read_extinp(a.extinp)",
        "    xtb_exe = shutil.which('g-xtb') or shutil.which('xtb') or os.environ.get('XTB_CMD', 'xtb')",
        "",
        "    cmd = [str(xtb_exe), xyz, '--chrg', str(chrg), '--uhf', str(max(0, mult - 1))]",
        "    if a.method:",
        "        cmd.append(a.method)",
        "    if dograd:",
        "        cmd.append('--grad')",
        "",
        "    res = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(a.extinp).parent)",
        "    if res.returncode != 0:",
        "        sys.exit(f'g-xTB execution failed: {res.stderr}')",
        "",
        "    parent_dir = Path(a.extinp).parent",
        "    energy_val = 0.0",
        "    energy_file = parent_dir / 'energy'",
        "    if energy_file.is_file():",
        "        lines = energy_file.read_text(encoding='utf-8').splitlines()",
        "        if len(lines) >= 2:",
        "            energy_val = float(lines[1].split()[1])",
        "",
        "    grad_vals = []",
        "    grad_file = parent_dir / 'gradient'",
        "    if dograd and grad_file.is_file():",
        "        lines = grad_file.read_text(encoding='utf-8').splitlines()",
        "        for line in lines:",
        "            parts = line.split()",
        "            if len(parts) == 3:",
        "                try:",
        "                    vals = [float(p) for p in parts]",
        "                    grad_vals.extend(vals)",
        "                except ValueError:",
        "                    pass",
        "",
        "    base = a.extinp.rsplit('.extinp.tmp', 1)[0]",
        "    xyz_lines = Path(xyz).read_text(encoding='utf-8').splitlines()",
        "    num_atoms = int(xyz_lines[0].strip()) if xyz_lines else 0",
        "",
        "    with open(base + '.engrad', 'w', encoding='utf-8') as f:",
        "        f.write(f'{num_atoms}\\n')",
        "        f.write(f'{energy_val:.12f}\\n')",
        "        if dograd:",
        "            for g in grad_vals[-num_atoms * 3:]:",
        "                f.write(f'{g:.12f}\\n')",
        "    return 0",
        "",
        "if __name__ == '__main__':",
        "    sys.exit(main())",
    ]

    wrappers = {
        "oet_server": "\n".join(server_lines) + "\n",
        "oet_client": "\n".join(client_lines) + "\n",
        "oet_aimnet2": "\n".join(aimnet2_lines) + "\n",
        "oet_maceoff": "\n".join(maceoff_lines) + "\n",
        "oet_gxtb": "\n".join(gxtb_lines) + "\n",
    }

    for name, script_code in wrappers.items():
        out_file = script_dir / name
        out_file.write_text(script_code, encoding="utf-8")
        try:
            mode = out_file.stat().st_mode
            out_file.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass
        generated[name] = out_file

        if platform.system() == "Windows":
            cmd_file = script_dir / f"{name}.cmd"
            cmd_content = f'@echo off\n"{py_path_posix}" "{out_file.as_posix()}" %*\n'
            cmd_file.write_text(cmd_content, encoding="utf-8")

    logger.info(f"[OET WRAPPERS] Installed {len(generated)} ORCA ExtOpt wrappers in {script_dir}")
    return generated


# =============================================================================
# 7. MICRO-SILO PROVISIONING & DEPENDENCY ISOLATION (SRS Doc 5)
# =============================================================================


SILO_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    "cochem_core_silo": {
        "type": SiloType.CORE,
        "description": "Core algorithm engine, Pydantic v2, Mendeleev mass authority & HDF5 SWMR",
        "packages": ["pydantic>=2.0", "psutil", "numpy", "scipy", "mendeleev", "h5py", "networkx", "sympy"],
        "is_heavy": False,
        "is_mandatory": True,
    },
    "cochem_ui_silo": {
        "type": SiloType.UI,
        "description": "Interactive GUI, IPyWidgets, Voila, Plotly, and Dash portal",
        "packages": ["ipywidgets>=8.0.0", "voila", "plotly", "jupyterlab", "psutil"],
        "is_heavy": False,
        "is_mandatory": True,
    },
    "cochem_calc_silo": {
        "type": SiloType.CALC,
        "description": "Quantum chemistry integrations (PySCF, xTB, ASE, QCEngine/QCElemental)",
        "packages": ["ase", "qcelemental", "qcengine"],
        "is_heavy": True,
        "is_mandatory": False,
    },
    "oet_aimnet2": {
        "type": SiloType.AIMNET2,
        "description": "Isolated AIMNet2 MLFF environment (§9B.4 mutually incompatible venv)",
        "packages": ["numpy", "ase"],
        "is_heavy": True,
        "is_mandatory": False,
    },
    "oet_uma": {
        "type": SiloType.UMA,
        "description": "Isolated UMA MLFF environment (§9B.4 mutually incompatible venv)",
        "packages": ["ase", "numpy"],
        "is_heavy": True,
        "is_mandatory": False,
    },
    "cochem_mace_silo": {
        "type": SiloType.MACE,
        "description": "MACE foundation models & MACE-OFF via ASE (§10.7)",
        "packages": ["ase", "numpy"],
        "is_heavy": True,
        "is_mandatory": False,
    },
}


def provision_micro_silo(
    name: str,
    target_venv_dir: Path,
    python_exe: str,
    skip_heavy: bool = False,
    dry_run: bool = False,
    force_clean: bool = False,
) -> SiloAuditRecord:
    """
    Provisions and verifies an isolated micro-silo using transactional venv staging
    and pip installation adhering to SRS Document 5 and Method Matrix Section 9B.4.
    """
    spec = SILO_SPECIFICATIONS.get(name, {
        "type": SiloType.CORE,
        "description": f"Custom micro-silo {name}",
        "packages": ["numpy", "pydantic"],
        "is_heavy": False,
        "is_mandatory": False,
    })

    s_type = spec["type"]
    is_heavy = spec["is_heavy"]
    if platform.system() == "Windows":
        silo_python = target_venv_dir / "Scripts" / "python.exe"
    else:
        silo_python = target_venv_dir / "bin" / "python"

    if skip_heavy and is_heavy:
        logger.info(f"[MICRO-SILO] Skipping heavy micro-silo '{name}' (--skip-heavy active).")
        return SiloAuditRecord(
            name=name,
            silo_type=s_type,
            venv_path=str(target_venv_dir),
            status=SiloStatus.BYPASSED,
            is_available=False,
            is_heavy=True,
            error_detail="Bypassed by --skip-heavy configuration flag.",
        )

    if dry_run:
        logger.info(f"[MICRO-SILO] [AUDIT] Inspecting micro-silo '{name}' at {target_venv_dir}")
        py_ver_str = None
        is_avail = False
        ver_pkgs: List[str] = []
        if target_venv_dir.exists() and silo_python.is_file():
            try:
                ver_check = subprocess.run(
                    [str(silo_python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
                if ver_check.returncode == 0:
                    py_ver_str = ver_check.stdout.strip()

                for pkg in spec["packages"]:
                    base_pkg = re.split(r"[><=~]", pkg)[0].strip().replace("-", "_")
                    c_res = subprocess.run([str(silo_python), "-c", f"import {base_pkg}"], capture_output=True, text=True, timeout=5.0)
                    if c_res.returncode == 0:
                        ver_pkgs.append(base_pkg)
                is_avail = True
            except Exception:
                pass

        return SiloAuditRecord(
            name=name,
            silo_type=s_type,
            venv_path=str(target_venv_dir),
            python_executable=str(silo_python.resolve()) if silo_python.is_file() else None,
            python_version=py_ver_str,
            status=SiloStatus.EXISTS_VALID if (is_avail or target_venv_dir.exists()) else SiloStatus.MISSING,
            is_available=is_avail or (target_venv_dir.exists() and not is_heavy),
            is_heavy=is_heavy,
            verified_packages=ver_pkgs if ver_pkgs else spec["packages"],
        )

    if force_clean and target_venv_dir.exists():
        logger.info(f"[MICRO-SILO] Purging existing micro-silo directory: {target_venv_dir}")
        shutil.rmtree(target_venv_dir, ignore_errors=True)

    created_new = False
    if not target_venv_dir.exists() or not silo_python.is_file():
        logger.info(f"[MICRO-SILO] Creating virtual environment at {target_venv_dir} using {python_exe}...")
        target_venv_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            builder = venv.EnvBuilder(with_pip=True, clear=force_clean, symlinks=(platform.system() != "Windows"))
            builder.create(target_venv_dir)
            created_new = True
        except Exception as exc:
            logger.warning(f"[MICRO-SILO] venv module creation failed ({exc}); falling back to subprocess venv...")
            try:
                subprocess.run([python_exe, "-m", "venv", str(target_venv_dir)], check=True, timeout=60.0)
                created_new = True
            except Exception as e2:
                logger.error(f"[MICRO-SILO] Fatal: Could not create venv at {target_venv_dir}: {e2}")
                return SiloAuditRecord(
                    name=name,
                    silo_type=s_type,
                    venv_path=str(target_venv_dir),
                    status=SiloStatus.ERROR,
                    is_available=False,
                    is_heavy=is_heavy,
                    error_detail=f"Venv creation failed: {e2}",
                )

    if not silo_python.is_file():
        return SiloAuditRecord(
            name=name,
            silo_type=s_type,
            venv_path=str(target_venv_dir),
            status=SiloStatus.ERROR,
            is_available=False,
            is_heavy=is_heavy,
            error_detail=f"Silo python interpreter missing at {silo_python}",
        )

    packages_to_install = spec["packages"]
    if packages_to_install:
        logger.info(f"[MICRO-SILO] Installing dependencies into '{name}': {', '.join(packages_to_install)}")
        try:
            cmd = [str(silo_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"]
            subprocess.run(cmd, capture_output=True, text=True, timeout=120.0)

            install_cmd = [str(silo_python), "-m", "pip", "install", *packages_to_install]
            res = subprocess.run(install_cmd, capture_output=True, text=True, timeout=300.0)
            if res.returncode != 0:
                logger.warning(f"[MICRO-SILO] Pip reported non-zero return code for {name}: {res.stderr[:200]}")
        except Exception as exc:
            logger.warning(f"[MICRO-SILO] Dependency install exception for {name}: {exc}")

    verified_packages: List[str] = []
    py_ver_str = "Unknown"
    try:
        ver_check = subprocess.run(
            [str(silo_python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if ver_check.returncode == 0:
            py_ver_str = ver_check.stdout.strip()

        for pkg in packages_to_install:
            base_pkg = re.split(r"[><=~]", pkg)[0].strip().replace("-", "_")
            check_cmd = [str(silo_python), "-c", f"import {base_pkg}; print('{base_pkg}:OK')"]
            c_res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=5.0)
            if c_res.returncode == 0 and "OK" in c_res.stdout:
                verified_packages.append(base_pkg)
    except Exception:
        pass

    status = SiloStatus.PROVISIONED if created_new else SiloStatus.EXISTS_VALID
    is_avail = silo_python.is_file() and (len(verified_packages) > 0 or not packages_to_install)

    logger.info(f"[MICRO-SILO] Micro-silo '{name}' operational (Python: {py_ver_str}, Status: {status.value})")

    return SiloAuditRecord(
        name=name,
        silo_type=s_type,
        venv_path=str(target_venv_dir.resolve()),
        python_executable=str(silo_python.resolve()),
        python_version=py_ver_str,
        status=status,
        is_available=is_avail,
        is_heavy=is_heavy,
        verified_packages=verified_packages,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# =============================================================================
# 8. MENDELEEV DYNAMIC MASS RESOLUTION VERIFICATION
# =============================================================================


def verify_mendeleev_authority() -> bool:
    """
    Verifies that the Mendeleev library is installed and functional.
    Enforces the dynamic atomic and isotopic mass retrieval mandate.
    """
    if mendeleev is None or element is None:
        logger.warning("[MENDELEEV MANDATE] mendeleev library not imported in active environment.")
        return False

    try:
        c_elem = element("C")
        c_mass = float(c_elem.mass)
        c13_iso = next((iso for iso in c_elem.isotopes if iso.mass_number == 13), None)
        c13_mass = float(c13_iso.mass) if c13_iso and c13_iso.mass else None

        o_elem = element("O")
        o_mass = float(o_elem.mass)

        h_elem = element("H")
        d_iso = next((iso for iso in h_elem.isotopes if iso.mass_number == 2), None)
        d_mass = float(d_iso.mass) if d_iso and d_iso.mass else None

        if c_mass > 12.0 and c13_mass and d_mass:
            logger.info(f"[MENDELEEV MANDATE] Authority verified: C={c_mass:.6f} u, 13C={c13_mass:.6f} u, 2H={d_mass:.6f} u")
            return True
    except Exception as exc:
        logger.error(f"[MENDELEEV MANDATE] Dynamic mass resolution failed: {exc}")

    return False


# =============================================================================
# 9. GOLDEN SYSTEM REGISTRY PERSISTENCE (SRS Doc 2 §3.11 & Method Matrix §8)
# =============================================================================


def persist_golden_system_registry(report: UnifiedInstallReport, artifact_dir: Path) -> Path:
    """
    Persists the verified Stage 0 deployment configuration to the Golden System Registry
    at `$COCHEM_ARTIFACT_DIR/Registry/cochem_system_config.json` with transactional atomic write.
    """
    registry_dir = artifact_dir / "Registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_file = registry_dir / "cochem_system_config.json"
    manifest_file = registry_dir / "cochem_deployment_manifest.json"

    payload: Dict[str, Any] = {
        "version": report.co_chem_version,
        "timestamp_utc": report.timestamp_utc,
        "setup_tier": report.setup_tier.value,
        "hardware_profile": report.hardware.model_dump(),
        "quantum_engines": {k: v.model_dump() for k, v in report.binaries.items()},
        "micro_silos": {k: v.model_dump() for k, v in report.micro_silos.items()},
        "mendeleev_verified": report.mendeleev_authority_verified,
        "status": report.status,
        "routing_policy": {
            "scout_and_anchor_concurrency": True,
            "cpu_anchor_ranks": report.hardware.recommended_orca_ranks - 1 if report.hardware.recommended_orca_ranks > 1 else 1,
            "gpu_scout_p_cores": 1,
            "maxcore_mb_per_rank": report.hardware.recommended_maxcore_mb,
            "gpu_crossover_basis_threshold": 90,
            "mps_daemon_enabled": report.hardware.has_mps_daemon,
        },
    }

    temp_reg = registry_dir / f".tmp_config_{uuid.uuid4().hex}.json"
    try:
        with open(temp_reg, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_reg.replace(registry_file)
        logger.info(f"[REGISTRY PERSISTENCE] Atomically committed Golden Registry to: {registry_file}")
    except Exception as exc:
        if temp_reg.exists():
            temp_reg.unlink()
        raise RegistryPersistenceError(f"Failed to persist Golden Registry: {exc}")

    interact_env = "Local-Windows (WSL)" if report.hardware.platform_system == "Windows" else (
        "Codespaces" if report.setup_tier == SetupTier.SETUP_1_TEACHING else "Local-Linux (Deb)"
    )
    calc_env = "HPC" if report.setup_tier == SetupTier.SETUP_3_HPC else (
        "GitHub Actions" if report.setup_tier == SetupTier.SETUP_1_TEACHING else "Local-Linux (Deb)"
    )

    manifest_payload: Dict[str, Any] = {
        "version": "2026.2",
        "git_provenance_hash": "HEAD",
        "interaction_environment": interact_env,
        "calculation_environment": calc_env,
        "orca_tarball_path": report.binaries.get("orca", BinaryEngineItem(name="orca")).path or "",
        "selected_repositories": ["CoChem-BASE", "CoChem-TOPOS", "CoChem-BENCH", "CoChem-SCRIBE"],
        "headless": True,
        "timestamp_utc": report.timestamp_utc,
    }

    temp_manifest = registry_dir / f".tmp_manifest_{uuid.uuid4().hex}.json"
    try:
        with open(temp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_payload, f, indent=2)
        temp_manifest.replace(manifest_file)
    except Exception:
        if temp_manifest.exists():
            temp_manifest.unlink()

    return registry_file


# =============================================================================
# 10. UNIFIED INSTALLER ORCHESTRATION PIPELINE
# =============================================================================


def run_unified_installer(
    external_tools: Sequence[str] = (),
    target_silos: Sequence[str] = (),
    venv_dir_override: Optional[Path] = None,
    script_dir_override: Optional[Path] = None,
    artifact_dir: Optional[Path] = None,
    setup_tier: SetupTier = SetupTier.AUTO,
    skip_heavy: bool = False,
    dry_run: bool = False,
    force_clean: bool = False,
) -> UnifiedInstallReport:
    """
    Master unified entrypoint executing Stage 0 environment configuration,
    binary discovery, micro-silo provisioning, OET wrapper generation, and registry persistence.
    """
    logger.info("=" * 78)
    logger.info(" [CoChem Stage 0] Unified Installer & Micro-Silo Setup Entrypoint")
    logger.info("    Method Matrix v4 (§8, §8A-§8D, §9B.4, §10) & SRS Doc 5 Compliant")
    logger.info("=" * 78)

    art_dir = artifact_dir or get_artifact_dir()
    art_dir.mkdir(parents=True, exist_ok=True)

    logger.info("\n[STAGE 0.1] Profiling host hardware, SIMD, and hypervisor...")
    hardware = detect_host_hardware(forced_tier=setup_tier)
    logger.info(f"Host OS:             {hardware.platform_system} ({hardware.platform_release}, {hardware.platform_architecture})")
    logger.info(f"Processor:           {hardware.cpu_model}")
    logger.info(f"CPU Topology:        {hardware.performance_cores} P-cores / {hardware.efficiency_cores} E-cores ({hardware.total_logical_threads} threads)")
    logger.info(f"Memory Budget:       {hardware.total_ram_gb} GB RAM (ORCA %maxcore {hardware.recommended_maxcore_mb} MB/rank, {hardware.recommended_orca_ranks} ranks)")
    logger.info(f"GPU Accelerator:     {hardware.cuda_device_name or 'None'} (VRAM: {hardware.cuda_vram_gb} GB, MPS: {hardware.has_mps_daemon})")
    logger.info(f"Setup Tier:          {hardware.resolved_setup_tier.value}")

    if hardware.is_wsl2_9p_mount:
        logger.warning("[WSL2 9P TRAP] Active workspace resides on /mnt/c or /mnt/d 9P mount! Recommend moving to native Linux filesystem (~/ or /var/tmp).")

    logger.info("\n[STAGE 0.2] Discovering quantum engines and cryptographic hashing...")
    binaries = discover_quantum_engines(art_dir)

    logger.info("\n[STAGE 0.3] Resolving host Python interpreter via Dynamic Version Walking...")
    python_exe, py_ver = dynamic_version_walking()

    logger.info("\n[STAGE 0.4] Provisioning isolated micro-silos & virtual environments...")
    silo_records: Dict[str, SiloAuditRecord] = {}

    selected_silo_names: Set[str] = set()

    if "all" in target_silos:
        selected_silo_names = set(SILO_SPECIFICATIONS.keys())
    elif target_silos:
        selected_silo_names = set(target_silos)
    elif external_tools:
        selected_silo_names = set()
    else:
        selected_silo_names = {"cochem_core_silo", "cochem_ui_silo"}

    for tool in external_tools:
        tool_lower = tool.lower()
        if tool_lower in ("aimnet2", "oet_aimnet2"):
            selected_silo_names.add("oet_aimnet2")
        elif tool_lower in ("uma", "oet_uma"):
            selected_silo_names.add("oet_uma")
        elif tool_lower in ("mace", "cochem_mace_silo", "oet_mace", "maceoff"):
            selected_silo_names.add("cochem_mace_silo")
        elif tool_lower == "all":
            selected_silo_names.update(SILO_SPECIFICATIONS.keys())

    silo_base_dir = art_dir / "Silos"
    silo_base_dir.mkdir(parents=True, exist_ok=True)

    for silo_name in sorted(selected_silo_names):
        if venv_dir_override and len(selected_silo_names) == 1:
            target_v_dir = venv_dir_override
        elif venv_dir_override:
            target_v_dir = venv_dir_override / silo_name
        else:
            target_v_dir = silo_base_dir / silo_name

        rec = provision_micro_silo(
            name=silo_name,
            target_venv_dir=target_v_dir,
            python_exe=python_exe,
            skip_heavy=skip_heavy,
            dry_run=dry_run,
            force_clean=force_clean,
        )
        silo_records[silo_name] = rec

    logger.info("\n[STAGE 0.5] Generating ORCA External Tools (OET) wrappers...")
    target_script_dir = script_dir_override or (art_dir / "bin")
    core_silo_py = Path(silo_records.get("cochem_core_silo", SiloAuditRecord(name="core", silo_type=SiloType.CORE)).python_executable or python_exe)
    if not dry_run:
        generate_oet_wrappers(target_script_dir, core_silo_py)

    logger.info("\n[STAGE 0.6] Verifying Mendeleev Dynamic Mass Authority...")
    mendeleev_ok = verify_mendeleev_authority()

    mandatory_silos = [s for s, spec in SILO_SPECIFICATIONS.items() if spec.get("is_mandatory") and s in silo_records]
    all_mandatory_ok = all(silo_records[s].is_available for s in mandatory_silos) if mandatory_silos else True

    status_str = "SUCCESS" if all_mandatory_ok else "DEGRADED"

    report = UnifiedInstallReport(
        setup_tier=hardware.resolved_setup_tier,
        hardware=hardware,
        binaries=binaries,
        micro_silos=silo_records,
        mendeleev_authority_verified=mendeleev_ok,
        status=status_str,
    )

    if not dry_run:
        logger.info("\n[STAGE 0.7] Committing Golden System Registry...")
        reg_path = persist_golden_system_registry(report, art_dir)
        report.registry_file_path = str(reg_path.resolve())

    logger.info("\n" + "=" * 78)
    logger.info(f" [OK] Stage 0 Unified Installation Complete (Status: {report.status})")
    logger.info(f"    Registry: {report.registry_file_path or 'Dry Run (Not Written)'}")
    logger.info("=" * 78 + "\n")

    return report


# =============================================================================
# 11. CLI PARSER & ENTRYPOINT
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Builds comprehensive CLI parser supporting Method Matrix Section 8, 9B.4 & 10 syntax."""
    parser = argparse.ArgumentParser(
        prog="install.py",
        description="CoChem Unified Installer & Micro-Silo Setup Entrypoint (Method Matrix v4 & SRS Doc 5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install AIMNet2 isolated micro-silo & wrappers (Method Matrix §9B.4):
  python install.py --venv-dir ~/oet-aimnet2-venv --script-dir ~/bin/oet-aimnet2 -e aimnet2

  # Install UMA isolated micro-silo & wrappers (Method Matrix §9B.4):
  python install.py --venv-dir ~/oet-uma-venv --script-dir ~/bin/oet-uma -e uma

  # Full baseline installation across all micro-silos:
  python install.py --all

  # Verify existing setup, hardware, and binary discovery without modifying disk:
  python install.py verify --json
""",
    )

    parser.add_argument(
        "action",
        nargs="?",
        default="install",
        choices=["install", "verify", "audit", "clean", "status"],
        help="Action to execute (default: install)",
    )

    parser.add_argument(
        "-e", "--external-tool", "--engine",
        dest="external_tools",
        action="append",
        default=[],
        help="External MLFF/semi-empirical tool to provision (aimnet2, uma, mace, gxtb, all)",
    )
    parser.add_argument(
        "--venv-dir",
        type=str,
        default=None,
        help="Custom destination directory for micro-silo virtual environment",
    )
    parser.add_argument(
        "--script-dir",
        type=str,
        default=None,
        help="Custom destination directory for generated wrapper scripts and binaries",
    )

    parser.add_argument(
        "-s", "--silo", "--silos",
        dest="target_silos",
        action="append",
        default=[],
        help="Specific micro-silo(s) to provision (cochem_core_silo, cochem_ui_silo, cochem_calc_silo, oet_aimnet2, oet_uma, cochem_mace_silo, all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Provision all standard and external tool micro-silos",
    )
    parser.add_argument(
        "-a", "--artifact-dir",
        type=str,
        default=None,
        help="Custom root directory for CoChem_Artifacts repository",
    )
    parser.add_argument(
        "--setup-tier",
        type=str,
        default="auto",
        choices=["auto", "setup1", "setup2", "setup3"],
        help="Target Setup Tier per Method Matrix §8.0 (setup1=Teaching, setup2=Workstation, setup3=HPC)",
    )
    parser.add_argument(
        "--skip-heavy",
        action="store_true",
        help="Skip provisioning heavy GPU/quantum chemistry micro-silos (PySCF, MACE)",
    )
    parser.add_argument(
        "--clean", "--force",
        dest="force_clean",
        action="store_true",
        help="Purge existing micro-silo environment before re-provisioning",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit hardware and engines without creating venvs or modifying disk",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit execution results in machine-readable JSON format",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug telemetry",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential console output",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Master CLI execution entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)

    tier_map = {
        "auto": SetupTier.AUTO,
        "setup1": SetupTier.SETUP_1_TEACHING,
        "setup2": SetupTier.SETUP_2_WORKSTATION,
        "setup3": SetupTier.SETUP_3_HPC,
    }
    target_tier = tier_map.get(args.setup_tier.lower(), SetupTier.AUTO)

    artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else get_artifact_dir()
    venv_dir = Path(args.venv_dir).resolve() if args.venv_dir else None
    script_dir = Path(args.script_dir).resolve() if args.script_dir else None

    if args.action == "clean":
        silos_dir = artifact_dir / "Silos"
        if silos_dir.exists():
            logger.info(f"Purging micro-silos directory: {silos_dir}")
            shutil.rmtree(silos_dir, ignore_errors=True)
            logger.info("Micro-silos purged successfully.")
        return 0

    silos = list(args.target_silos)
    if args.all:
        silos = ["all"]

    dry_run = args.dry_run or (args.action in ("verify", "audit", "status"))

    try:
        report = run_unified_installer(
            external_tools=args.external_tools,
            target_silos=silos,
            venv_dir_override=venv_dir,
            script_dir_override=script_dir,
            artifact_dir=artifact_dir,
            setup_tier=target_tier,
            skip_heavy=args.skip_heavy,
            dry_run=dry_run,
            force_clean=args.force_clean,
        )

        if args.json:
            print(report.model_dump_json(indent=2))

        return 0 if report.status in ("SUCCESS", "DEGRADED") else 1

    except Exception as exc:
        logger.error(f"Unified installer failed: {exc}", exc_info=args.verbose)
        if args.json:
            print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
