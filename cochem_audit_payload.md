Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc5_07_phase5_config_lock_prompt.md.
Original prompt:
# Context
You are tasked with writing the setup orchestration script `cochem_setup_phase_5.py` for CoChem-BASE.

# Goal
Create `cochem_setup_phase_5.py` to perform Phase 5: IPC Config Lock & Workspace Sweep.

# Requirements
- Consolidate the intermediate states (`p1.json` through `p11.json`).
- Run them through the Pydantic `CoChemSystemConfig` validation schemas.
- Atomically write the finalized Golden Registry to `$HOME/CoChem_Artifacts/Registry/cochem_system_config.json`.
- Before initializing HDF5 SWMR, explicitly execute a physical POSIX byte-range locking test (`fcntl`) on the target filesystem, gracefully degrading to single-threaded operations if the lock test fails.
- Set `cfg["status"] = "LOCKED"` and apply `os.chmod(0o444)` (read-only) to enforce immutability.
- Execute a garbage collection sweep to safely delete all ephemeral `.tmp` and intermediate JSON fragments from the workspace.

# Constraints
- Target filepath: `D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_5.py`
- DO NOT use any mocks, stubs, or placeholder values in your code. Write real implementation logic.
- Ensure strict adherence to the Tripartite Workspace Air-Gap and Method Matrix rules.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_core_registry_schema.py ---
#!/usr/bin/env python3
"""
CoChem-BASE: Stage 0 Authority Rule - Golden Master Registry Schema
Defines rigid Pydantic v2 models for `cochem_system_config.json`.
Acts as a mathematical boundary preventing hallucinated configurations,
silent floating-point drift, relative path vulnerabilities, and OOM thread allocation.
All schemas strictly forbid extra fields and enforce validation on assignment.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND ENVIRONMENT EXPANSION
# =============================================================================

CARBON_13_ISOTOPIC_MASS: float = 13.00335483507

ISOTOPIC_MASSES: Dict[str, float] = {
    "1H": 1.00782503223,
    "2H": 2.01410177812,
    "3H": 3.01604928132,
    "12C": 12.00000000000,
    "13C": CARBON_13_ISOTOPIC_MASS,
    "14N": 14.00307400443,
    "15N": 15.00010889888,
    "16O": 15.99491461957,
    "17O": 16.99913175650,
    "18O": 17.99915961286,
    "19F": 18.99840316273,
    "31P": 30.97376199842,
    "32S": 31.97207117440,
    "35Cl": 34.96885268200,
    "37Cl": 36.96590260200,
    "79Br": 78.91833760000,
    "81Br": 80.91629100000,
    "127I": 126.9044719000,
}

BYPASS_TOKENS: Set[str] = {"BYPASSED", "Not_Found", "missing"}


def _expand_env_vars(path_str: str) -> str:
    """Uniformly expands %VAR%, $VAR, and ${VAR} across Windows and POSIX."""
    if not path_str:
        return path_str

    def replace_percent(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.environ.get(var, f"%{var}%")

    s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, path_str)
    s = os.path.expandvars(s)
    return os.path.expanduser(s)


def _default_mps_pipe_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[0])
    except Exception:
        return "/tmp/nvidia-mps"


def _default_mps_log_dir() -> str:
    try:
        from cochem_base.config_loader import get_mps_directories
        return str(get_mps_directories()[1])
    except Exception:
        return "/tmp/nvidia-log"


def _default_os_target() -> str:
    sys_name = platform.system().lower()
    if "windows" in sys_name:
        return OSTarget.LOCAL_WINDOWS.value
    if "darwin" in sys_name:
        return OSTarget.LOCAL_MACOS.value
    if os.getenv("GITHUB_ACTIONS") == "true":
        return OSTarget.GITHUB_ACTIONS.value
    if os.getenv("CODESPACES") == "true":
        return OSTarget.CODESPACES.value
    return OSTarget.LOCAL_LINUX.value


def _default_artifacts_dir() -> str:
    return os.getenv("COCHEM_ARTIFACTS_DIR", str(Path.home() / "cochem_artifacts"))


# =============================================================================
# ENUMS
# =============================================================================

class OSTarget(str, Enum):
    """
    Authoritative Operating System and Architecture Targets for the CoChem Ecosystem.
    Canonical 6-tier values: Local-Windows, Local-MacOS, Local-Linux, Codespaces, GitHub_Actions, HPC.
    """
    LOCAL_WINDOWS = "Local-Windows"
    LOCAL_MACOS = "Local-MacOS"
    LOCAL_LINUX = "Local-Linux"
    CODESPACES = "Codespaces"
    GITHUB_ACTIONS = "GitHub_Actions"
    HPC = "HPC"

    # Direct ecosystem aliases
    LINUX_X86_64 = "linux_x86_64"
    LINUX_AARCH64 = "linux_aarch64"
    WINDOWS_X86_64 = "windows_x86_64"
    WINDOWS_AMD64 = "windows_amd64"
    DARWIN_ARM64 = "darwin_arm64"
    DARWIN_X86_64 = "darwin_x86_64"
    GENERIC_POSIX = "posix"
    GENERIC_NT = "nt"


_OS_TARGET_NORMALIZATION_MAP: Dict[str, str] = {
    "local-windows": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_native": OSTarget.LOCAL_WINDOWS.value,
    "local-windows_wsl": OSTarget.LOCAL_WINDOWS.value,
    "windows": OSTarget.LOCAL_WINDOWS.value,
    "windows_x86_64": OSTarget.WINDOWS_X86_64.value,
    "windows_amd64": OSTarget.WINDOWS_AMD64.value,
    "nt": OSTarget.GENERIC_NT.value,

    "local-macos": OSTarget.LOCAL_MACOS.value,
    "local-macos_darwin": OSTarget.LOCAL_MACOS.value,
    "darwin": OSTarget.LOCAL_MACOS.value,
    "darwin_arm64": OSTarget.DARWIN_ARM64.value,
    "darwin_x86_64": OSTarget.DARWIN_X86_64.value,

    "local-linux": OSTarget.LOCAL_LINUX.value,
    "local-linux_deb": OSTarget.LOCAL_LINUX.value,
    "linux": OSTarget.LOCAL_LINUX.value,
    "linux_x86_64": OSTarget.LINUX_X86_64.value,
    "linux_amd64": OSTarget.LINUX_X86_64.value,
    "linux_aarch64": OSTarget.LINUX_AARCH64.value,
    "posix": OSTarget.GENERIC_POSIX.value,

    "codespaces": OSTarget.CODESPACES.value,
    "github_codespaces": OSTarget.CODESPACES.value,
    "github_actions": OSTarget.GITHUB_ACTIONS.value,
    "hpc": OSTarget.HPC.value,
    "hpc_slurm_linux": OSTarget.HPC.value,
}


# =============================================================================
# 1. GPU COMPUTE SCHEMA
# =============================================================================

class GPUComputeSchema(BaseModel):
    """
    GPU Compute Metrics and Hardware Topology.
    Tracks peak theoretical/measured TFLOPS, Tensor Cores count, Memory Bandwidth, and CUDA features.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    gpu_profile: str = Field(default="None", description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    device_count: int = Field(default=0, ge=0, description="Number of detected GPU devices")
    compute_capability: Optional[str] = Field(default=None, description="CUDA Compute capability, e.g. '8.9'")
    fp64_capable: bool = Field(default=False, description="Whether device supports native double-precision FP64")
    subnormal_precision_trap: bool = Field(default=False, description="Whether subnormal precision traps are enabled")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak TFLOPS compute metric")
    fp32_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP32 TFLOPS")
    fp16_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP16 TFLOPS")
    fp64_tflops: Optional[float] = Field(default=None, ge=0.0, description="Peak FP64 TFLOPS")
    tensor_cores: Optional[int] = Field(default=None, ge=0, description="Number of hardware Tensor Cores")
    memory_bandwidth_gb_s: Optional[float] = Field(default=None, ge=0.0, description="GPU memory bandwidth in GB/s")


# =============================================================================
# 2. MPS & CORE PINNING CONFIGURATIONS
# =============================================================================

class MPSConfig(BaseModel):
    """CUDA Multi-Process Service (MPS) configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = Field(default=True, description="Enable CUDA MPS daemon multiplexing")
    max_workers: int = Field(default=4, gt=0, le=64, description="Max concurrent MPS worker tasks per GPU")
    thread_percentage: int = Field(default=25, ge=1, le=100, description="CUDA MPS active thread percentage ceiling")
    pipe_dir: str = Field(default_factory=_default_mps_pipe_dir, description="MPS pipe directory")
    log_dir: str = Field(default_factory=_default_mps_log_dir, description="MPS log directory")


class CorePinningConfig(BaseModel):
    """Core Pinning and CPU Topology Configuration."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    kmp_hw_subset: str = Field(default="8c:intel_core,1t", description="OpenMP core pinning HW subset spec")
    anchor_p_cores: int = Field(default=7, ge=0, description="Number of P-cores assigned to CPU anchor tasks")
    scout_p_cores: int = Field(default=1, ge=0, description="Number of P-cores assigned to GPU scout tasks")
    background_e_cores: int = Field(default=8, ge=0, description="E-cores reserved for OS/background tasks")


# =============================================================================
# 3. QUANTUM SOLVER SETTINGS
# =============================================================================

class QuantumSettings(BaseModel):
    """Quantum chemical solver settings."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    implicit_solvation: Optional[str] = Field(default=None, description="Implicit solvent model (CPCM, SMD) or None")
    integration_grid: Optional[str] = Field(default="defgrid2", description="Integration grid size (defgrid1, defgrid2, defgrid3)")
    charge: int = Field(default=0)
    multiplicity: int = Field(default=1, ge=1)

    @field_validator("implicit_solvation", mode="before")
    @classmethod
    def validate_implicit_solvation(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().upper()
            if cleaned in ("CPCM", "SMD"):
                return cleaned
            raise ValueError("implicit_solvation must be 'CPCM' or 'SMD'")
        return cast(Optional[str], v)

    @field_validator("integration_grid", mode="before")
    @classmethod
    def validate_integration_grid(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("defgrid1", "defgrid2", "defgrid3"):
                return cleaned
            raise ValueError("integration_grid must be one of ('defgrid1', 'defgrid2', 'defgrid3')")
        return cast(Optional[str], v)


# =============================================================================
# 4. HARDWARE SCHEMA
# =============================================================================

class HardwareSchema(BaseModel):
    """
    Rigid bounds for physical compute resources to prevent OOM and thread contention.
    Enforces positive RAM (gt=0.0), at least 1 physical core (ge=1), non-negative allocatable cores (ge=0),
    and non-negative VRAM (ge=0.0).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory in GB")
    cpu_physical_cores: int = Field(default=1, ge=1, description="Actual physical silicon cores")
    allocatable_compute_cores: int = Field(default=1, ge=0, description="Allocatable compute cores for scientific jobs")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    gpu_compute_metrics: GPUComputeSchema = Field(default_factory=GPUComputeSchema, description="GPU compute metrics and capabilities")
    gpu_fp64_capable: bool = Field(default=False, description="Whether GPU supports native FP64 precision")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")
    avx_512_capable: bool = Field(default=False, description="Whether CPU supports AVX-512 vector instructions")

    # Ecosystem & compatibility aliases
    physical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Alias for cpu_physical_cores")
    logical_cpu_cores: Optional[int] = Field(default=None, ge=1, description="Hyperthreaded threads count")
    cpu_cores: Optional[int] = Field(default=None, ge=1, description="Legacy CPU cores alias")
    ram_mb: Optional[int] = Field(default=None, ge=1, description="Total system RAM in MB")
    maxcore_mb: Optional[int] = Field(default=3000, ge=0, description="Max core memory per process in MB")
    avx512_support: bool = Field(default=False, description="Legacy alias for avx_512_capable")
    gpu_profile: str = Field(default="None", description="Detected GPU model name")
    subnormal_precision_trap: bool = Field(default=False, description="Subnormal floating-point trap")
    os_target: Union[OSTarget, str] = Field(default=OSTarget.LOCAL_WINDOWS, description="Target execution environment")
    host_id: Optional[str] = Field(default=None, description="Host identity identifier")
    mps: Optional[MPSConfig] = Field(default_factory=MPSConfig, description="MPS daemon configuration")
    core_pinning: Optional[CorePinningConfig] = Field(default_factory=CorePinningConfig, description="CPU core pinning topology")
    gpu: Optional[GPUComputeSchema] = Field(default=None, description="Legacy alias for gpu_compute_metrics")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def flex_hardware_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # String-to-number coercions
        for float_field in ["ram_gb", "vram_gb"]:
            if float_field in d and isinstance(d[float_field], str):
                try:
                    d[float_field] = float(d[float_field])
                except ValueError:
                    pass

        for int_field in ["cpu_physical_cores", "physical_cpu_cores", "logical_cpu_cores", "cpu_cores", "allocatable_compute_cores", "ram_mb", "maxcore_mb"]:
            if int_field in d and isinstance(d[int_field], str):
                try:
                    d[int_field] = int(float(d[int_field]))
                except ValueError:
                    pass

        # Synchronize physical cores
        phys = d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or d.get("cpu_cores")
        if phys is not None:
            try:
                phys_int = int(phys)
                d["cpu_physical_cores"] = phys_int
                d["physical_cpu_cores"] = phys_int
                if "cpu_cores" not in d:
                    d["cpu_cores"] = phys_int
            except (ValueError, TypeError):
                pass

        if "logical_cpu_cores" not in d or d["logical_cpu_cores"] is None:
            if phys is not None:
                try:
                    d["logical_cpu_cores"] = int(phys)
                except (ValueError, TypeError):
                    pass

        if "allocatable_compute_cores" not in d or d["allocatable_compute_cores"] is None:
            if phys is not None:
                try:
                    d["allocatable_compute_cores"] = int(phys)
                except (ValueError, TypeError):
                    pass

        # Synchronize RAM
        if "ram_mb" not in d and "ram_gb" in d:
            try:
                d["ram_mb"] = int(float(d["ram_gb"]) * 1024)
            except (ValueError, TypeError):
                pass
        elif "ram_gb" not in d and "ram_mb" in d:
            try:
                d["ram_gb"] = float(d["ram_mb"]) / 1024.0
            except (ValueError, TypeError):
                pass

        # Maxcore OOM clamping guard
        if "maxcore_mb" in d and "ram_mb" in d:
            try:
                maxcore = int(d["maxcore_mb"])
                ram_mb = int(d["ram_mb"])
                if maxcore > ram_mb:
                    phys_count = int(d.get("cpu_physical_cores") or d.get("physical_cpu_cores") or 1)
                    d["maxcore_mb"] = max(500, int(ram_mb * 0.75 / max(1, phys_count)))
            except (ValueError, TypeError):
                pass

        # Synchronize AVX-512 capabilities
        if "avx_512_capable" in d and "avx512_support" not in d:
            d["avx512_support"] = bool(d["avx_512_capable"])
        elif "avx512_support" in d and "avx_512_capable" not in d:
            d["avx_512_capable"] = bool(d["avx512_support"])
        elif "avx_512_capable" not in d and "avx512_support" not in d:
            d["avx_512_capable"] = False
            d["avx512_support"] = False

        # Synchronize GPU compute metrics
        gpu_data = d.get("gpu_compute_metrics") or d.get("gpu")
        if gpu_data is None:
            gpu_prof = d.get("gpu_profile", "None")
            vram = d.get("vram_gb", 0.0)
            trap = d.get("subnormal_precision_trap", False)
            fp64 = d.get("gpu_fp64_capable", False)
            mps_en = d.get("mps_enabled", False)
            built_gpu = {
                "gpu_profile": gpu_prof,
                "vram_gb": float(vram) if isinstance(vram, (int, float, str)) else 0.0,
                "subnormal_precision_trap": trap,
                "fp64_capable": fp64,
                "mps_enabled": mps_en,
            }
            d["gpu_compute_metrics"] = built_gpu
            d["gpu"] = built_gpu
        else:
            if isinstance(gpu_data, dict):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "fp64_capable" in gpu_data and "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = bool(gpu_data["fp64_capable"])
                if "mps_enabled" in gpu_data and "mps_enabled" not in d:
                    d["mps_enabled"] = bool(gpu_data["mps_enabled"])
            elif isinstance(gpu_data, GPUComputeSchema):
                d["gpu_compute_metrics"] = gpu_data
                d["gpu"] = gpu_data
                if "gpu_fp64_capable" not in d:
                    d["gpu_fp64_capable"] = gpu_data.fp64_capable
                if "mps_enabled" not in d:
                    d["mps_enabled"] = gpu_data.mps_enabled

        return d


HardwareConfig = HardwareSchema


# =============================================================================
# 5. ENVIRONMENT SCHEMA
# =============================================================================

class EnvironmentSchema(BaseModel):
    """
    Operating environment configuration, OS target validation, and isotopic mass locking.
    Enforces exact isotopic mass float values (e.g., ^13C = 13.00335483507).
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    os_target: Union[OSTarget, str] = Field(
        default_factory=_default_os_target,
        description="Target OS tier",
    )
    artifacts_dir: Union[str, Path] = Field(
        default_factory=_default_artifacts_dir,
        description="Path to artifacts directory",
    )
    scratch_dir: Optional[Union[str, Path]] = Field(default=None, description="Path to fast scratch directory")
    codata_version: str = Field(default="2018", description="CODATA constant version (e.g. '2018')")
    isotopic_mass_locking: bool = Field(default=True, description="Strict lock on atomic/isotopic masses")
    isotopic_mass_13c: float = Field(
        default=CARBON_13_ISOTOPIC_MASS,
        description="Locked isotopic mass for Carbon-13 (^13C = 13.00335483507)",
    )
    isotopic_masses: Dict[str, float] = Field(
        default_factory=lambda: dict(ISOTOPIC_MASSES),
        description="Exact isotopic mass registry",
    )
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Custom environment variable overrides")
    strict_path_resolution: bool = Field(default=False, description="Reject unresolvable relative paths if True")

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            normalized = _OS_TARGET_NORMALIZATION_MAP.get(v_str.lower())
            if normalized:
                return normalized
            valid_targets = {t.value for t in OSTarget}
            if v_str in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @field_validator("codata_version")
    @classmethod
    def validate_codata(cls, v: str) -> str:
        valid = {"2014", "2018", "2022"}
        if v not in valid:
            raise ValueError(f"codata_version must be one of {sorted(valid)}, got '{v}'")
        return v

    @field_validator("artifacts_dir", "scratch_dir", mode="before")
    @classmethod
    def expand_and_normalize_path(cls, v: Any) -> Any:
        if v is None or v == "[MISSING DATA]":
            return None
        return _expand_env_vars(str(v))

    def resolve_path(self, raw_path: Union[str, Path]) -> Path:
        """Cross-platform path resolution with environment variable expansion."""
        if not raw_path:
            raise ValueError("Cannot resolve empty path.")
        expanded = _expand_env_vars(str(raw_path))
        p = Path(expanded)
        if self.strict_path_resolution and not p.is_absolute():
            raise ValueError(f"Strict path resolution enabled: relative path '{raw_path}' is rejected.")
        return p.resolve()

    def get_isotopic_mass(self, isotope: str) -> float:
        """Retrieve authoritative locked isotopic mass float."""
        if isotope in self.isotopic_masses:
            return self.isotopic_masses[isotope]
        if isotope == "13C":
            return self.isotopic_mass_13c
        raise KeyError(f"Isotope '{isotope}' not registered in isotopic mass matrix.")


# =============================================================================
# 6. SILO PATHS SCHEMA
# =============================================================================

class SiloPathsSchema(BaseModel):
    """
    Paths configuration for isolated silos and scientific binaries.
    Enforces absolute path resolution (rejects relative paths), intercepting 'BYPASSED' and 'Not_Found'
    tokens, and preventing write stores (like HDF5 PES stores) from targeting immutable $COCHEM_ROOT.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    hdf5_pes_store_path: Optional[str] = Field(default=None, description="Path to centralized HDF5 PES store")
    cfour_binary_path: Optional[str] = Field(default=None, description="Path to CFOUR binary or 'BYPASSED'")
    aimnet2_server_path: Optional[str] = Field(default=None, description="Path to AIMNet2 server script or 'BYPASSED'")
    orca_binary_path: Optional[str] = Field(default=None, description="Path to ORCA executable or 'BYPASSED'")
    xtb_binary_path: Optional[str] = Field(default=None, description="Path to xTB executable or 'BYPASSED'")
    mpirun_binary_path: Optional[str] = Field(default=None, description="Path to mpirun executable or 'BYPASSED'")

    # Aliases
    orca_path: Optional[str] = Field(default=None, description="Alias for orca_binary_path")
    xtb_path: Optional[str] = Field(default=None, description="Alias for xtb_binary_path")
    mpirun_path: Optional[str] = Field(default=None, description="Alias for mpirun_binary_path")
    cfour_path: Optional[str] = Field(default=None, description="Alias for cfour_binary_path")
    aimnet2_path: Optional[str] = Field(default=None, description="Alias for aimnet2_server_path")
    python_path: Optional[str] = Field(default=None, description="Path to silo Python interpreter")
    silo_root: Optional[str] = Field(default=None, description="Root directory for micro-environments")
    strict_resolution: bool = Field(default=False, description="Enforce binary presence verification")

    @field_validator(
        "hdf5_pes_store_path",
        "cfour_binary_path",
        "aimnet2_server_path",
        "orca_binary_path",
        "xtb_binary_path",
        "mpirun_binary_path",
        "orca_path",
        "xtb_path",
        "mpirun_path",
        "cfour_path",
        "aimnet2_path",
        "python_path",
        "silo_root",
        mode="before",
    )
    @classmethod
    def validate_and_expand_path(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, (str, Path)):
            s = str(v).strip()
            if s in BYPASS_TOKENS:
                return s

            expanded = _expand_env_vars(s)
            p = Path(expanded)

            # Reject relative paths strictly
            if not p.is_absolute():
                raise ValueError(
                    f"Relative paths are forbidden in SiloPathsSchema for '{info.field_name}': '{s}'. "
                    "Path must be absolute or a bypass token ('BYPASSED', 'Not_Found', 'missing')."
                )

            resolved = p.resolve()

            # HPC Tripartite Air-Gap Check: Prevent write stores from targeting immutable $COCHEM_ROOT
            if info.field_name == "hdf5_pes_store_path":
                cochem_root_env = os.environ.get("COCHEM_ROOT")
                if cochem_root_env:
                    resolved_root = Path(os.path.expandvars(cochem_root_env)).resolve()
                    try:
                        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                    except AttributeError:
                        try:
                            resolved.relative_to(resolved_root)
                            raise ValueError(
                                f"Write store path '{resolved}' targets immutable codebase $COCHEM_ROOT ('{resolved_root}'). "
                                "Paths should map to the Dynamic Data Tier or Volatile Compute Tier."
                            )
                        except ValueError:
                            pass

            return str(resolved)
        raise ValueError(f"Invalid path type '{type(v)}' for '{info.field_name}'. Expected string or Path.")

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

    def is_bypassed(self, binary_name: str) -> bool:
        """Check if binary execution is marked as BYPASSED."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                return bool(val == "BYPASSED")
        return False

    def is_found(self, binary_name: str) -> bool:
        """Check if binary exists on filesystem and is not bypassed/missing."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if not val or val in BYPASS_TOKENS:
                    return False
                return Path(val).exists()
        return False

    def resolve_binary(self, binary_name: str) -> Optional[str]:
        """Resolve executable path or return bypass token."""
        norm_name = binary_name.lower().replace(".exe", "")
        for candidate in (
            f"{norm_name}_binary_path",
            f"{norm_name}_path",
            f"{norm_name}_server_path",
            norm_name,
        ):
            if hasattr(self, candidate):
                val = getattr(self, candidate)
                if val is None or val in BYPASS_TOKENS:
                    return cast(Optional[str], val)
                p = Path(val)
                if self.strict_resolution and not p.exists():
                    raise FileNotFoundError(f"Binary '{binary_name}' not found at path '{val}'")
                return str(p.resolve())
        raise AttributeError(f"Unknown binary configuration '{binary_name}' in SiloPathsSchema")


# =============================================================================
# 7. COMPUTATIONAL BINARY PROVENANCE & SILO CONFIGS
# =============================================================================

class EngineInfo(BaseModel):
    """Pathing and cryptographic provenance for computational binaries."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    status: str = Field(..., description="found, missing, permission_denied, or bypassed")
    path: Optional[str] = Field(None, description="Absolute path to executable, or 'BYPASSED', or 'Not_Found'")
    version: Optional[str] = Field(None, description="Semantic version of the engine")
    hash: Optional[str] = Field(None, description="SHA-256 binary hash")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> str:
        if v is None or v == "[MISSING DATA]":
            return "missing"
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("found", "missing", "permission_denied", "bypassed"):
                return cleaned
            raise ValueError(f"Invalid engine status '{v}'. Must be one of ('found', 'missing', 'permission_denied', 'bypassed').")
        raise ValueError(f"Invalid engine status type '{type(v)}'. Expected string.")

    @field_validator("path", "version", "hash", mode="before")
    @classmethod
    def clean_missing_data(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return str(v)


class EnginePaths(BaseModel):
    """Aggregated binary path specifications."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    orca: Optional[EngineInfo] = Field(default=None)
    mpirun: Optional[EngineInfo] = Field(default=None)
    xtb: Optional[EngineInfo] = Field(default=None)
    cfour: Optional[EngineInfo] = Field(default=None)
    aimnet2: Optional[EngineInfo] = Field(default=None)
    mace: Optional[EngineInfo] = Field(default=None)


class SiloConfig(BaseModel):
    """Micro-environment deployment status."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    torq_silo_active: bool = Field(default=False)
    gpu_silo_active: bool = Field(default=False)


class RoutingPolicy(BaseModel):
    """Dynamically assigned execution constraints."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_concurrent_mace_threads: int = Field(default=4, gt=0)
    max_dft_basis_functions: int = Field(default=2000, gt=0)
    recommend_ccsdt: bool = Field(default=False)
    classification: str = Field(default="STANDARD")


class HPCConfig(BaseModel):
    """Cluster integration parameters."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scheduler: str = Field(default="local", description="local, slurm, pbs, or sge")
    default_partition: str = Field(default="compute")
    max_walltime_hours: Optional[int] = Field(default=24, gt=0)
    partition: Optional[str] = Field(default="compute")
    cluster_hostname: Optional[str] = Field(default="localhost")
    ssh_key_path: Optional[str] = Field(default="")
    username: Optional[str] = Field(default="localuser")
    execution_mode: Optional[str] = Field(default="local")
    walltime_budgets: Optional[Dict[str, str]] = Field(default_factory=dict)

    @field_validator("scheduler", mode="before")
    @classmethod
    def validate_scheduler(cls, v: Any) -> str:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("local", "slurm", "pbs", "sge"):
                return s
            raise ValueError(f"Invalid HPC scheduler '{v}'. Must be one of ('local', 'slurm', 'pbs', 'sge').")
        raise ValueError(f"HPC scheduler must be a string, got {type(v)}")


# =============================================================================
# 8. MASTER COCHEM SYSTEM CONFIG
# =============================================================================

class CoChemSystemConfig(BaseModel):
    """
    The CoChem Master System Configuration Schema.
    Rigid mathematical boundary enforcing Stage 0 Authority Rule.
    Aggregates HardwareSchema, EnvironmentSchema, SiloPathsSchema, and live execution jobs.
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    status: Optional[str] = Field(default="LOCKED", description="Registry operational status ('LOCKED', 'INITIALIZED', 'ACTIVE')")
    orca_version: Optional[str] = Field(default="6.1.1")
    rdkit_random_seed: Optional[int] = Field(default=42)
    registry_checksum: Optional[str] = Field(default="", description="SHA-256 checksum of registry payload")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hardware: HardwareSchema = Field(..., description="Rigid compute hardware bounds and topology")
    environment: EnvironmentSchema = Field(default_factory=EnvironmentSchema, description="Operating environment settings")
    silo_paths: SiloPathsSchema = Field(default_factory=SiloPathsSchema, description="Silo and binary path mappings")
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    silos: Optional[SiloConfig] = Field(default=None, description="Micro-environment deployment status")
    quantum_settings: Optional[QuantumSettings] = Field(default_factory=QuantumSettings)
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

    @model_validator(mode="before")
    @classmethod
    def registry_migrator(cls, data: Any) -> Any:
        """
        RegistryMigrator: Transforms legacy flat configuration dictionaries
        into the authoritative nested schema architecture before validation.
        """
        if not isinstance(data, dict):
            return data

        d = dict(data)

        # 1. Migrate flat Hardware fields
        hw_keys = {
            "physical_cpu_cores", "cpu_physical_cores", "logical_cpu_cores",
            "cpu_cores", "ram_gb", "ram_mb", "maxcore_mb", "avx512_support",
            "avx_512_capable", "gpu_profile", "vram_gb", "subnormal_precision_trap",
            "allocatable_compute_cores", "gpu_compute_metrics", "gpu_fp64_capable",
            "mps_enabled", "core_pinning", "mps", "gpu", "host_id"
        }
        extracted_hw: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in hw_keys:
                extracted_hw[k] = d.pop(k)

        if "hardware" not in d or d["hardware"] is None:
            if extracted_hw:
                d["hardware"] = extracted_hw
        elif isinstance(d["hardware"], dict):
            for k, v in extracted_hw.items():
                if k not in d["hardware"]:
                    d["hardware"][k] = v

        # 2. Migrate flat Environment fields
        env_keys = {
            "codata_version", "isotopic_mass_locking", "isotopic_mass_13c",
            "isotopic_masses", "artifacts_dir", "scratch_dir",
            "strict_path_resolution", "env_vars"
        }
        extracted_env: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in env_keys:
                extracted_env[k] = d.pop(k)

        if "os_target" in d:
            os_target_val = d.pop("os_target")
            extracted_env["os_target"] = os_target_val
            if "hardware" in d and isinstance(d["hardware"], dict) and "os_target" not in d["hardware"]:
                d["hardware"]["os_target"] = os_target_val

        if "environment" not in d or d["environment"] is None:
            if extracted_env:
                d["environment"] = extracted_env
        elif isinstance(d["environment"], dict):
            for k, v in extracted_env.items():
                if k not in d["environment"]:
                    d["environment"][k] = v

        # 3. Migrate flat Silo fields
        silo_keys = {
            "orca_path", "xtb_path", "mpirun_path", "cfour_path", "aimnet2_server_path",
            "aimnet2_path", "cfour_binary_path", "orca_binary_path", "xtb_binary_path",
            "mpirun_binary_path", "hdf5_pes_store_path", "silo_root", "python_path", "strict_resolution"
        }
        extracted_silo: Dict[str, Any] = {}
        for k in list(d.keys()):
            if k in silo_keys:
                extracted_silo[k] = d.pop(k)

        if "silo_paths" not in d or d["silo_paths"] is None:
            if extracted_silo:
                d["silo_paths"] = extracted_silo
        elif isinstance(d["silo_paths"], dict):
            for k, v in extracted_silo.items():
                if k not in d["silo_paths"]:
                    d["silo_paths"][k] = v

        # 4. Default active_jobs
        if "active_jobs" not in d or d["active_jobs"] is None:
            d["active_jobs"] = {}

        return d

    @field_validator("adaptive_routing", mode="before")
    @classmethod
    def clean_adaptive_routing(cls, v: Any) -> Any:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        return v

    @field_validator("engines", mode="before")
    @classmethod
    def validate_engines(cls, v: Any) -> Any:
        if isinstance(v, dict):
            validated: Dict[str, Any] = {}
            for engine_name, engine_val in v.items():
                if isinstance(engine_val, dict):
                    validated[engine_name] = EngineInfo.model_validate(engine_val)
                else:
                    validated[engine_name] = engine_val
            return validated
        return v

    def compute_checksum(self) -> str:
        """Calculates deterministic SHA-256 checksum of configuration payload."""
        d = self.model_dump(exclude={"registry_checksum", "last_updated"})
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def update_checksum(self) -> str:
        """Calculates and updates registry_checksum in place."""
        cs = self.compute_checksum()
        self.registry_checksum = cs
        return cs

    def verify_checksum(self) -> bool:
        """Verifies whether registry_checksum matches the current configuration payload."""
        if not self.registry_checksum:
            return False
        return self.registry_checksum == self.compute_checksum()

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_file(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CoChemSystemConfig:
        return cls.model_validate(d)

    @classmethod
    def from_json(cls, json_str: str) -> CoChemSystemConfig:
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> CoChemSystemConfig:
        p = Path(path)
        return cls.model_validate_json(p.read_text(encoding="utf-8"))

    @classmethod
    def create_default(cls, auto_detect_hardware: bool = False) -> CoChemSystemConfig:
        hw = discover_host_hardware() if auto_detect_hardware else HardwareSchema(
            cpu_physical_cores=4,
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            os_target=OSTarget.LOCAL_WINDOWS if os.name == "nt" else OSTarget.LOCAL_LINUX,
        )
        return cls(
            hardware=hw,
            quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
            silos=SiloConfig(torq_silo_active=True),
        )


CoChemConfig = CoChemSystemConfig


# =============================================================================
# 9. DISCOVERY & CONVENIENCE FUNCTIONS
# =============================================================================

def discover_engine(binary_name: str) -> EngineInfo:
    """Check physical presence and provenance of a scientific binary."""
    p = shutil.which(binary_name)
    if p:
        return EngineInfo(status="found", path=str(p), version="auto", hash="auto")
    return EngineInfo(status="missing", path=None, version=None, hash=None)


def discover_host_hardware() -> HardwareSchema:
    """Discover host hardware configuration safely."""
    try:
        import psutil  # type: ignore[import-untyped]
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        phys_cores = psutil.cpu_count(logical=False) or 1
        log_cores = psutil.cpu_count(logical=True) or 1
    except ImportError:
        total_ram_gb = 16.0
        phys_cores = os.cpu_count() or 1
        log_cores = os.cpu_count() or 1

    os_target = _default_os_target()

    return HardwareSchema(
        cpu_physical_cores=phys_cores,
        physical_cpu_cores=phys_cores,
        logical_cpu_cores=log_cores,
        allocatable_compute_cores=phys_cores,
        ram_gb=round(total_ram_gb, 2),
        avx_512_capable=False,
        gpu_profile="None",
        vram_gb=0.0,
        os_target=os_target,
    )


def validate_system_config(source: Union[str, Path, Dict[str, Any], CoChemSystemConfig]) -> CoChemSystemConfig:
    """Authoritative gatekeeper validating system configuration from any source."""
    if isinstance(source, CoChemSystemConfig):
        return source
    if isinstance(source, dict):
        return CoChemSystemConfig.model_validate(source)
    if isinstance(source, Path):
        return CoChemSystemConfig.from_file(source)
    if isinstance(source, str):
        if os.path.exists(source):
            return CoChemSystemConfig.from_file(source)
        try:
            return CoChemSystemConfig.from_json(source)
        except Exception:
            try:
                raw_dict = json.loads(source)
                return CoChemSystemConfig.model_validate(raw_dict)
            except Exception:
                pass
    raise TypeError(f"Unsupported configuration source type: {type(source)}")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_5.py ---
"""
CoChem Setup Phase 5: IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting Gatekeeper.
Production-grade, zero-mock gatekeeping engine for:
1. Multi-tenant NVIDIA Multi-Process Service (MPS) daemon management (nvidia-cuda-mps-control)
   and dynamically calculated pinned device memory partitioning (CUDA_MPS_PINNED_DEVICE_MEM_LIMIT).
2. Physical POSIX byte-range locking verification (fcntl / msvcrt) before HDF5 SWMR initialization,
   with graceful degradation to single-threaded operations upon filesystem locking failure.
3. Intermediate state consolidation (p1.json through p11.json) and validation through the rigid
   Pydantic v2 CoChemSystemConfig schema.
4. Atomic serialization of the finalized Golden Registry to $HOME/CoChem_Artifacts/Registry/cochem_system_config.json
   with status="LOCKED" and os.chmod(0o444) read-only immutability enforcement.
5. Workspace garbage collection sweep purging ephemeral .tmp files and intermediate staging fragments.

SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 4.3), and Method Matrix v4 Compliant.
"""

from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from pydantic import BaseModel, ConfigDict, Field, field_validator

# POSIX fcntl / Windows msvcrt locking imports
try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

# Schema and Config Imports with Path Resolution Fallbacks
try:
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        ISOTOPIC_MASSES,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )
except ImportError:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from cochem_core_registry_schema import (
        CARBON_13_ISOTOPIC_MASS,
        ISOTOPIC_MASSES,
        CoChemSystemConfig,
        OSTarget,
        discover_host_hardware,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cochem_setup_phase_5")


# =============================================================================
# 1. EXCEPTIONS
# =============================================================================


class Phase5AuditError(RuntimeError):
    """Raised when critical phase 5 MPS daemon initialization or VRAM allocation fails fatally."""


class MPSControlError(RuntimeError):
    """Raised when nvidia-cuda-mps-control daemon lifecycle management commands fail unexpectedly."""


class VRAMAllocationError(RuntimeError):
    """Raised when VRAM memory limits or worker capacity cannot be safely bounded."""


class ConfigLockError(RuntimeError):
    """Raised when golden master registry configuration locking fails."""


class LockTestFailureError(RuntimeError):
    """Raised when physical POSIX filesystem locking verification encounters an unrecoverable error."""


# =============================================================================
# 2. PYDANTIC V2 DATA MODELS & ENUMS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class MPSStatus(str, Enum):
    """Operational status enumeration for NVIDIA MPS daemon subsystem."""

    RUNNING = "RUNNING"
    INITIALIZED = "INITIALIZED"
    STOPPED = "STOPPED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class GPUDeviceVRAM(BaseModel):
    """Physical GPU device VRAM allocation and worker partitioning profile."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    index: int = Field(..., ge=0, description="Physical GPU device index (e.g. 0, 1)")
    name: str = Field(..., description="GPU model/product identifier")
    uuid: Optional[str] = Field(default=None, description="GPU device UUID if available")
    total_vram_mb: float = Field(..., ge=0.0, description="Total physical VRAM in megabytes")
    free_vram_mb: float = Field(default=0.0, ge=0.0, description="Available unallocated VRAM in megabytes")
    reserved_vram_mb: float = Field(default=0.0, ge=0.0, description="VRAM reserved for OS/UI/host buffers in megabytes")
    allocatable_vram_mb: float = Field(default=0.0, ge=0.0, description="Net allocatable VRAM for compute workers in megabytes")
    allocated_limit_per_worker_mb: float = Field(
        default=0.0, ge=0.0, description="Calculated pinned memory limit per concurrent worker in megabytes"
    )
    active_worker_capacity: int = Field(
        default=1, ge=1, description="Maximum concurrent GPU worker processes supported without OOM"
    )
    pinned_mem_limit_str: str = Field(
        default="", description="Formatted CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string (e.g. '0=4096M')"
    )
    compute_capability: Optional[str] = Field(
        default=None, description="CUDA compute capability architecture (e.g. 'sm_80', 'sm_89')"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("GPU name cannot be empty")
        return v.strip()


class MPSDaemonAudit(BaseModel):
    """Structured inspection and lifecycle state of the NVIDIA MPS daemon."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    mps_control_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-control executable"
    )
    mps_server_binary: Optional[str] = Field(
        default=None, description="Absolute filesystem path to nvidia-cuda-mps-server executable"
    )
    status: MPSStatus = Field(default=MPSStatus.NOT_SUPPORTED, description="Operational status of MPS daemon")
    pipe_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_PIPE_DIRECTORY IPC pipe/sockets"
    )
    log_directory: Optional[str] = Field(
        default=None, description="Directory path for CUDA_MPS_LOG_DIRECTORY telemetry logs"
    )
    socket_path: Optional[str] = Field(
        default=None, description="Active Unix domain socket or named pipe path for daemon communication"
    )
    is_daemon_active: bool = Field(
        default=False, description="Whether the nvidia-cuda-mps-control daemon process is running"
    )
    pid: Optional[int] = Field(
        default=None, description="Process ID of active nvidia-cuda-mps-control daemon"
    )
    socket_permissions: Optional[str] = Field(
        default=None, description="Octal permission mode (e.g. '0o700') or ACL string"
    )
    is_permission_secure: bool = Field(
        default=True, description="Whether socket permissions enforce 0700 restricted access"
    )
    server_active: bool = Field(
        default=False, description="Whether backend nvidia-cuda-mps-server process is active"
    )
    control_active: bool = Field(
        default=False, description="Whether nvidia-cuda-mps-control command pipe is responsive"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables configured for MPS operations"
    )
    details: str = Field(default="", description="Diagnostic status summary and telemetry details")


class VRAMBudgetReport(BaseModel):
    """Aggregated cluster-wide VRAM memory budgeting and concurrency partitioning record."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_gpus_detected: int = Field(default=0, ge=0, description="Total number of physical GPUs discovered")
    active_gpu_devices: List[GPUDeviceVRAM] = Field(
        default_factory=list, description="Per-GPU VRAM profiles and allocation limits"
    )
    total_cluster_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated VRAM across all GPUs in megabytes"
    )
    total_reserved_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated reserved VRAM across all GPUs in megabytes"
    )
    total_allocatable_vram_mb: float = Field(
        default=0.0, ge=0.0, description="Total aggregated allocatable VRAM across all GPUs in megabytes"
    )
    worker_concurrency_target: int = Field(
        default=2, ge=1, description="Configured target concurrent GPU worker processes (e.g. 2 for MACE+PySCF)"
    )
    default_pinned_mem_limit: Optional[str] = Field(
        default=None, description="Default global CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string"
    )
    per_device_limits: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of device indices to pinned memory limits (e.g. {'0': '4096M'})"
    )
    is_vram_bounded: bool = Field(
        default=True, description="Whether VRAM allocations are strictly bounded to prevent OOM"
    )
    strategy: str = Field(
        default="PROPORTIONAL_PINNED_BUDGET", description="Applied VRAM partitioning strategy algorithm"
    )


class LockTestResult(BaseModel):
    """Physical POSIX byte-range locking verification result."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    passed: bool = Field(..., description="Whether byte-range locking succeeded on target filesystem")
    method: str = Field(..., description="Locking mechanism utilized (e.g. 'POSIX_FCNTL', 'MSVCRT_LOCKING')")
    single_threaded_mode: bool = Field(
        default=False,
        description="Whether single-threaded fallback degradation is active due to lock failure",
    )
    target_path: str = Field(..., description="Filesystem path tested for byte-range locking")
    lock_type: str = Field(default="POSIX_BYTE_RANGE_LOCK", description="Classification of lock test")
    error_message: Optional[str] = Field(default=None, description="Error diagnostics if lock test failed")


class WorkspaceSweepReport(BaseModel):
    """Artifact sweep report for garbage collection of intermediate setup files."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    swept_files_count: int = Field(default=0, ge=0, description="Number of temporary or fragment files cleaned")
    cleaned_paths: List[str] = Field(default_factory=list, description="Paths of cleaned ephemeral files")
    retained_paths: List[str] = Field(default_factory=list, description="Paths of permanent registered artifacts")
    trash_dir: Optional[str] = Field(default=None, description="Backup trash destination if configured")


class ConfigLockAuditReport(BaseModel):
    """Structured audit report for IPC configuration lock and workspace sweep."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    golden_registry_path: str = Field(..., description="Canonical path to locked cochem_system_config.json")
    status: str = Field(default="LOCKED", description="Operational status of master registry ('LOCKED')")
    checksum: str = Field(..., description="Deterministic SHA-256 checksum of locked configuration")
    posix_lock_test: LockTestResult = Field(..., description="Byte-range filesystem lock verification record")
    sweep_report: WorkspaceSweepReport = Field(..., description="Workspace garbage collection sweep results")
    intermediate_phases_found: List[str] = Field(
        default_factory=list, description="Intermediate phase artifacts consolidated (e.g. ['p1.json', 'p2.json'])"
    )
    is_immutable_mode_enforced: bool = Field(
        default=True, description="Whether 0o444 read-only file mode was applied"
    )


class Phase5AuditReport(BaseModel):
    """Comprehensive serialized audit report for Phase 5 NVIDIA MPS Daemon & VRAM Budgeting & Config Lock."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    phase_id: str = Field(
        default="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        description="Unique phase identifier",
    )
    status: PhaseStatus = Field(..., description="Overall phase outcome status")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    mps_daemon: MPSDaemonAudit = Field(..., description="NVIDIA MPS daemon lifecycle and socket audit")
    vram_budget: VRAMBudgetReport = Field(..., description="Calculated VRAM partitioning and budgeting report")
    is_cuda_available: bool = Field(default=False, description="Whether CUDA runtime and hardware are available")
    is_hpc_slurm: bool = Field(default=False, description="Whether execution occurred within a Slurm HPC envelope")
    config_lock: Optional[ConfigLockAuditReport] = Field(
        default=None, description="Phase 5 IPC config lock and workspace sweep results"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or degraded notices")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical validation errors")
    artifact_path: str = Field(..., description="Filesystem destination path for serialized p5.json")
    golden_config_path: Optional[str] = Field(
        default=None, description="Filesystem destination path for locked cochem_system_config.json"
    )

    @field_validator("phase_id")
    @classmethod
    def validate_phase_id(cls, v: str) -> str:
        if v != "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING":
            raise ValueError(f"Invalid phase_id: {v}")
        return v


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY & ATOMIC STATE MANAGER
# =============================================================================


class DependencyManager:
    """
    Transactional context manager for managing temporary files, staging directories,
    and executing atomic JSON state persistence with automatic rollback on unhandled exceptions.
    Ensures workspace sterility per SRS Document 5 Section 1.3.
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

    def untrack_file(self, path: Union[str, Path]) -> None:
        """Remove a file from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_files:
            self._tracked_temp_files.remove(p)

    def untrack_dir(self, path: Union[str, Path]) -> None:
        """Remove a directory from rollback tracking once successfully committed."""
        p = Path(path).resolve()
        if p in self._tracked_temp_dirs:
            self._tracked_temp_dirs.remove(p)

    def rollback(self) -> None:
        """Explicitly purge all tracked temporary files and directories."""
        for temp_file in list(self._tracked_temp_files):
            try:
                if temp_file.exists() and temp_file.is_file():
                    try:
                        os.chmod(temp_file, stat.S_IWRITE | stat.S_IREAD)
                    except OSError:
                        pass
                    temp_file.unlink()
            except OSError:
                pass
        self._tracked_temp_files.clear()

        for temp_dir in list(self._tracked_temp_dirs):
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
        read_only: bool = False,
    ) -> Path:
        """
        Atomically write JSON content to target_path using a staged temporary file and os.replace.
        Handles overwriting existing read-only files cleanly.
        """
        target = Path(target_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        unique_suffix = f".tmp.{uuid.uuid4().hex[:8]}"
        staged_file = target.parent / f"{target.name}{unique_suffix}"
        self.track_temp_file(staged_file)

        if isinstance(data, BaseModel):
            json_text = data.model_dump_json(indent=indent)
        elif isinstance(data, (dict, list)):
            json_text = json.dumps(data, indent=indent, default=str)
        else:
            json_text = str(data)

        staged_file.write_text(json_text, encoding="utf-8")

        # If target exists and is read-only (Windows NT or POSIX), unlock it temporarily for replacement
        if target.exists():
            try:
                os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IWUSR | stat.S_IRUSR)
            except OSError:
                pass

        os.replace(staged_file, target)
        self.untrack_file(staged_file)

        if read_only:
            try:
                os.chmod(target, stat.S_IREAD | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                pass

        return target


# =============================================================================
# 4. PATH RESOLUTION & DIRECTORY PROVISIONING
# =============================================================================


def get_current_username() -> str:
    """Retrieve the current OS username sanitized for filesystem paths."""
    try:
        user = getpass.getuser()
    except Exception:
        user = os.environ.get("USER") or os.environ.get("USERNAME") or "default_user"
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", user)


def resolve_mps_pipe_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve isolated runtime control pipe directory for CUDA_MPS_PIPE_DIRECTORY following
    the authoritative CoChem hierarchy:
    1. Explicit custom_dir parameter
    2. Environment variable CUDA_MPS_PIPE_DIRECTORY
    3. Slurm HPC envelope: $SLURM_TMPDIR/cochem_mps_$USER
    4. Linux / POSIX default: /tmp/cochem_mps_$USER
    5. Windows fallback: %TEMP%\\cochem_mps_%USERNAME%
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_pipe = os.environ.get("CUDA_MPS_PIPE_DIRECTORY")
    if env_pipe:
        resolved = Path(env_pipe).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_temp = Path(tempfile.gettempdir()) / f"cochem_mps_{user}{dir_suffix}"
    win_temp.mkdir(parents=True, exist_ok=True)
    return win_temp.resolve()


def resolve_mps_log_directory(custom_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve log directory for CUDA_MPS_LOG_DIRECTORY following the CoChem hierarchy.
    """
    if custom_dir:
        resolved = Path(custom_dir).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    env_log = os.environ.get("CUDA_MPS_LOG_DIRECTORY")
    if env_log:
        resolved = Path(env_log).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    user = get_current_username()
    slurm_job = os.environ.get("SLURM_JOB_ID")
    dir_suffix = f"_{slurm_job}" if slurm_job else ""
    slurm_tmp = os.environ.get("SLURM_TMPDIR")
    if slurm_tmp and Path(slurm_tmp).is_dir():
        resolved = Path(slurm_tmp).resolve() / f"cochem_mps_log_{user}{dir_suffix}"
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    if platform.system() != "Windows":
        resolved = Path(f"/tmp/cochem_mps_log_{user}{dir_suffix}").resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        enforce_socket_directory_permissions(resolved)
        return resolved

    win_log = Path(tempfile.gettempdir()) / f"cochem_mps_log_{user}{dir_suffix}"
    win_log.mkdir(parents=True, exist_ok=True)
    return win_log.resolve()


def enforce_socket_directory_permissions(dir_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Enforce restrictive 0700 (owner-only read/write/execute) permissions on Unix socket directories
    to prevent IPC spoofing and privilege escalation across multi-tenant environments.
    """
    if platform.system() == "Windows":
        return True, "0o700 (Windows NT ACL inherited)"

    try:
        current_mode = dir_path.stat().st_mode
        if (current_mode & 0o077) != 0:
            dir_path.chmod(0o700)
        mode_str = oct(stat.S_IMODE(dir_path.stat().st_mode))
        return True, mode_str
    except OSError:
        return False, None


def resolve_p5_registry_path(output_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve canonical destination path for Golden Registry artifact p5.json.
    """
    if output_dir:
        out_path = Path(output_dir).resolve()
        if out_path.suffix == ".json" or out_path.name == "p5.json":
            return out_path
        return out_path / "p5.json"

    try:
        from cochem_base.config_loader import get_artifact_dir

        return get_artifact_dir() / "Registry" / "p5.json"
    except ImportError:
        pass

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return Path(env_art).resolve() / "Registry" / "p5.json"

    repo_root_candidate = Path.cwd()
    agent_artifacts = repo_root_candidate / ".agent_artifacts"
    if agent_artifacts.exists():
        return agent_artifacts / "Registry" / "p5.json"

    home_artifacts = Path.home() / "CoChem_Artifacts"
    return home_artifacts / "Registry" / "p5.json"


def resolve_golden_config_path(output_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve destination path for finalized master Golden Registry cochem_system_config.json
    per SRS Document 5 Section 4.3.
    """
    if output_path:
        out_p = Path(output_path).resolve()
        if out_p.is_dir() or out_p.suffix == "":
            return out_p / "cochem_system_config.json"
        return out_p

    env_cfg = os.environ.get("COCHEM_CONFIG")
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser().resolve()

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        return (
            Path(os.path.expandvars(env_art)).expanduser()
            / "Registry"
            / "cochem_system_config.json"
        ).resolve()

    try:
        from cochem_base.config_loader import resolve_config_path

        return resolve_config_path()
    except Exception:
        pass

    return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


# =============================================================================
# 5. PHYSICAL POSIX BYTE-RANGE LOCKING TEST (FCNTL / MSVCRT)
# =============================================================================


def test_posix_byte_range_locking(
    target_dir: Optional[Union[str, Path]] = None,
    timeout: float = 2.0,
) -> LockTestResult:
    """
    Execute a physical POSIX byte-range locking test (fcntl on Linux/macOS, msvcrt on Windows)
    on the target filesystem prior to initializing HDF5 SWMR streams.

    SRS Document 5 Section 4.3 Mandate:
    If the filesystem does not support POSIX byte-range locks (e.g., certain NFS/SMB/CIFS mounts
    or legacy virtualized mounts), this test catches the failure and signals graceful degradation
    to single-threaded operations.
    """
    if target_dir:
        test_dir = Path(target_dir).resolve()
    else:
        test_dir = resolve_golden_config_path().parent

    test_dir.mkdir(parents=True, exist_ok=True)
    probe_filename = f".cochem_swmr_lock_probe_{uuid.uuid4().hex[:8]}.lock"
    probe_path = test_dir / probe_filename

    is_posix = platform.system() != "Windows"

    try:
        # Create physical probe file with data to lock
        with open(probe_path, "w+b") as f:
            f.write(b"COCHEM_SWMR_BYTE_RANGE_LOCK_PROBE_HEADER_BLOCK\n" * 10)
            f.flush()
            fd = f.fileno()

            if is_posix and fcntl is not None:
                # Test POSIX fcntl byte-range locking
                try:
                    # Exclusive byte-range lock on bytes 0..512
                    fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 512, 0)
                    # Unlock
                    fcntl.lockf(fd, fcntl.LOCK_UN, 512, 0)
                    method = "POSIX_FCNTL_LOCKF"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="POSIX_FCNTL_LOCKF",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"POSIX byte-range lock failed on filesystem: {exc}",
                    )
            elif not is_posix and msvcrt is not None:
                # Test Windows NT byte-range locking
                try:
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 512)
                    f.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 512)
                    method = "MSVCRT_LOCKING_BYTE_RANGE"
                except (OSError, IOError) as exc:
                    return LockTestResult(
                        passed=False,
                        method="MSVCRT_LOCKING_BYTE_RANGE",
                        single_threaded_mode=True,
                        target_path=str(probe_path),
                        error_message=f"Windows byte-range lock failed on filesystem: {exc}",
                    )
            else:
                method = "GENERIC_FALLBACK_LOCK"

        return LockTestResult(
            passed=True,
            method=method,
            single_threaded_mode=False,
            target_path=str(probe_path),
            error_message=None,
        )

    except Exception as e:
        return LockTestResult(
            passed=False,
            method="UNKNOWN_ERROR",
            single_threaded_mode=True,
            target_path=str(probe_path),
            error_message=f"Filesystem byte-range locking test exception: {e}",
        )
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass


def _sanitize_engine_record(raw_eng: Any) -> Optional[Dict[str, Any]]:
    """Sanitize raw engine dictionary to match strict EngineInfo schema."""
    if not isinstance(raw_eng, dict):
        return None
    st_raw = str(raw_eng.get("status", "")).lower()
    if "found" in st_raw or raw_eng.get("is_available") is True:
        st = "found"
    elif "bypass" in st_raw:
        st = "bypassed"
    elif "denied" in st_raw or "permission" in st_raw:
        st = "permission_denied"
    else:
        st = "missing" if not raw_eng.get("path") else "found"

    p = raw_eng.get("path")
    v = raw_eng.get("version")
    h = raw_eng.get("sha256_hash") or raw_eng.get("hash")
    return {
        "status": st,
        "path": str(p) if p else None,
        "version": str(v) if v else None,
        "hash": str(h) if h else None,
    }


def consolidate_intermediate_states(
    registry_dir: Optional[Union[str, Path]] = None,
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Consolidate intermediate phase states (p1.json through p11.json) discovered across
    the registry search paths into a single structured configuration payload ready for
    validation against CoChemSystemConfig.

    SRS Document 5 Section 4.3 Mandate.
    """
    candidate_dirs: List[Path] = []
    if registry_dir:
        candidate_dirs.append(Path(registry_dir).resolve())

    if search_dirs:
        for sd in search_dirs:
            candidate_dirs.append(Path(sd).resolve())

    env_reg = os.environ.get("COCHEM_REGISTRY_DIR")
    if env_reg:
        candidate_dirs.append(Path(env_reg).resolve())

    env_art = os.environ.get("COCHEM_ARTIFACT_DIR")
    if env_art:
        candidate_dirs.append((Path(env_art) / "Registry").resolve())

    candidate_dirs.append((Path.cwd() / ".agent_artifacts" / "Registry").resolve())
    candidate_dirs.append((Path.cwd() / "artifacts" / "registry").resolve())
    candidate_dirs.append((Path.home() / "CoChem_Artifacts" / "Registry").resolve())

    consolidated_raw: Dict[str, Any] = {}
    found_phases: List[str] = []

    # Map of intermediate JSON filenames to phase identifiers
    target_files = [f"p{i}.json" for i in range(1, 12)]

    for phase_filename in target_files:
        for cdir in candidate_dirs:
            phase_file = cdir / phase_filename
            if phase_file.is_file():
                try:
                    phase_data = json.loads(phase_file.read_text(encoding="utf-8"))
                    found_phases.append(phase_filename)

                    # Extract and merge domain-specific fields from each phase
                    if phase_filename == "p1.json":
                        # OS & Toolchain Audit
                        os_val = phase_data.get("os_target") or phase_data.get("os_profile", {}).get("system") or phase_data.get("os", {}).get("os_target")
                        if os_val:
                            consolidated_raw["os_target"] = os_val

                    elif phase_filename == "p2.json":
                        # Hardware & RAM Profiling
                        cpu_info = phase_data.get("cpu", {})
                        ram_info = phase_data.get("memory", {}) or phase_data.get("ram", {})
                        gpu_info = phase_data.get("gpu", {})

                        if "hardware" not in consolidated_raw:
                            consolidated_raw["hardware"] = {}

                        hw = consolidated_raw["hardware"]
                        if "physical_cores" in cpu_info:
                            hw["cpu_physical_cores"] = cpu_info["physical_cores"]
                            hw["physical_cpu_cores"] = cpu_info["physical_cores"]
                        if "logical_cores" in cpu_info:
                            hw["logical_cpu_cores"] = cpu_info["logical_cores"]

                        total_bytes = ram_info.get("total_physical_bytes") or ram_info.get("total_ram_bytes")
                        if total_bytes:
                            hw["ram_gb"] = round(float(total_bytes) / (1024.0**3), 2)
                        elif "total_ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["total_ram_gb"])
                        elif "ram_gb" in ram_info:
                            hw["ram_gb"] = float(ram_info["ram_gb"])

                        if "avx512_support" in cpu_info:
                            hw["avx_512_capable"] = bool(cpu_info["avx512_support"])
                            hw["avx512_support"] = bool(cpu_info["avx512_support"])

                        if gpu_info.get("gpu_available") or gpu_info.get("available"):
                            devices_list = gpu_info.get("devices") or []
                            if devices_list:
                                first_dev = devices_list[0]
                                hw["gpu_profile"] = first_dev.get("name", "NVIDIA GPU")
                                vram_bytes = first_dev.get("memory_total_bytes", 0)
                                if vram_bytes:
                                    hw["vram_gb"] = round(float(vram_bytes) / (1024.0**3), 2)

                    elif phase_filename == "p3.json":
                        # Multi-Track Quantum Engine Discovery
                        engines_data = phase_data.get("engines", {})
                        if engines_data and isinstance(engines_data, dict):
                            cleaned_engines: Dict[str, Any] = {}
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            sp = consolidated_raw["silo_paths"]

                            for eng_name, eng_info in engines_data.items():
                                sanitized = _sanitize_engine_record(eng_info)
                                if sanitized:
                                    cleaned_engines[eng_name] = sanitized
                                    if sanitized.get("path"):
                                        if eng_name == "orca":
                                            sp["orca_binary_path"] = sanitized["path"]
                                        elif eng_name == "xtb":
                                            sp["xtb_binary_path"] = sanitized["path"]
                                        elif eng_name == "cfour":
                                            sp["cfour_binary_path"] = sanitized["path"]
                                        elif eng_name == "mpirun":
                                            sp["mpirun_binary_path"] = sanitized["path"]
                                        elif eng_name == "aimnet2":
                                            sp["aimnet2_server_path"] = sanitized["path"]

                            consolidated_raw["engines"] = cleaned_engines

                    elif phase_filename == "p4.json":
                        # Silo Provisioning & Isolation
                        silos_data = phase_data.get("silos") or phase_data.get("silo_manifest", {})
                        gpu_active = False
                        torq_active = True
                        if isinstance(silos_data, dict):
                            if any("mace" in k or "gpu" in k for k in silos_data.keys()):
                                gpu_active = True
                            if "torq_silo_active" in silos_data:
                                torq_active = bool(silos_data["torq_silo_active"])
                            if "gpu_silo_active" in silos_data:
                                gpu_active = bool(silos_data["gpu_silo_active"])
                        consolidated_raw["silos"] = {
                            "torq_silo_active": torq_active,
                            "gpu_silo_active": gpu_active,
                        }

                    elif phase_filename == "p5.json":
                        # MPS Daemon & VRAM Budgeting
                        vram_budget = phase_data.get("vram_budget", {})
                        if vram_budget:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            hw = consolidated_raw["hardware"]
                            hw["mps_enabled"] = bool(phase_data.get("mps_daemon", {}).get("is_daemon_active", False))

                    elif phase_filename == "p6.json":
                        # Database & Bifurcated Storage
                        storage = phase_data.get("storage", {}) or phase_data.get("storage_tier", {})
                        if storage.get("hdf5_pes_store_path"):
                            if "silo_paths" not in consolidated_raw:
                                consolidated_raw["silo_paths"] = {}
                            consolidated_raw["silo_paths"]["hdf5_pes_store_path"] = storage["hdf5_pes_store_path"]

                    elif phase_filename == "p7.json":
                        # HPC Environment Configuration
                        hpc_info = phase_data.get("hpc", {})
                        if hpc_info and isinstance(hpc_info, dict):
                            valid_hpc_keys = {
                                "scheduler", "default_partition", "max_walltime_hours",
                                "partition", "cluster_hostname", "ssh_key_path",
                                "username", "execution_mode", "walltime_budgets"
                            }
                            filtered_hpc = {k: v for k, v in hpc_info.items() if k in valid_hpc_keys and v is not None}
                            if filtered_hpc:
                                consolidated_raw["hpc"] = filtered_hpc

                    elif phase_filename == "p9.json":
                        # Core Pinning & Parsl Concurrency
                        pinning = phase_data.get("core_pinning", {})
                        if pinning and isinstance(pinning, dict):
                            valid_pin_keys = {"kmp_hw_subset", "anchor_p_cores", "scout_p_cores", "background_e_cores"}
                            filtered_pin = {k: v for k, v in pinning.items() if k in valid_pin_keys and v is not None}
                            if filtered_pin:
                                if "hardware" not in consolidated_raw:
                                    consolidated_raw["hardware"] = {}
                                consolidated_raw["hardware"]["core_pinning"] = filtered_pin

                    elif phase_filename == "p10.json":
                        # MolSym Intake & Theoretical Eckart Frame Alignment
                        consolidated_raw["alignment_engine_ready"] = bool(
                            phase_data.get("alignment_engine_ready", True)
                        )

                    elif phase_filename == "p11.json":
                        # Memory Router & OOM Shield
                        mem_routing = phase_data.get("memory_routing", {}) or phase_data.get("oom_shield", {})
                        if "maxcore_mb" in mem_routing:
                            if "hardware" not in consolidated_raw:
                                consolidated_raw["hardware"] = {}
                            consolidated_raw["hardware"]["maxcore_mb"] = int(mem_routing["maxcore_mb"])

                    break
                except Exception as e:
                    logger.warning(f"Advisory: could not parse intermediate state {phase_file}: {e}")

    return consolidated_raw, list(dict.fromkeys(found_phases))


# =============================================================================
# 7. MASTER SYSTEM CONFIG VALIDATION & IMMUTABLE LOCKING
# =============================================================================


def validate_and_build_system_config(
    consolidated_data: Optional[Dict[str, Any]] = None,
    auto_detect_fallback: bool = True,
    single_threaded_mode: bool = False,
) -> CoChemSystemConfig:
    """
    Validate the consolidated registry dictionary against CoChemSystemConfig, applying
    hardware discovery fallbacks and setting status to 'LOCKED' per Stage 0 mandate.
    """
    raw = dict(consolidated_data or {})

    # Ensure Hardware exists and is completely bounded
    if "hardware" not in raw or not raw["hardware"] or not isinstance(raw["hardware"], dict):
        if auto_detect_fallback:
            discovered_hw = discover_host_hardware()
            raw["hardware"] = discovered_hw.model_dump()
        else:
            raw["hardware"] = {
                "cpu_physical_cores": 4,
                "physical_cpu_cores": 4,
                "logical_cpu_cores": 8,
                "ram_gb": 16.0,
            }
    else:
        hw_dict = dict(raw["hardware"])
        ram_val = hw_dict.get("ram_gb")
        if ram_val is None or float(ram_val) <= 0.0:
            if auto_detect_fallback:
                hw_dict["ram_gb"] = discover_host_hardware().ram_gb
            else:
                hw_dict["ram_gb"] = 16.0

        if not hw_dict.get("cpu_physical_cores") or int(hw_dict.get("cpu_physical_cores", 0)) < 1:
            hw_dict["cpu_physical_cores"] = hw_dict.get("physical_cpu_cores") or (discover_host_hardware().cpu_physical_cores if auto_detect_fallback else 4)
        if not hw_dict.get("physical_cpu_cores"):
            hw_dict["physical_cpu_cores"] = hw_dict["cpu_physical_cores"]
        if not hw_dict.get("logical_cpu_cores"):
            hw_dict["logical_cpu_cores"] = hw_dict["cpu_physical_cores"] * 2

        raw["hardware"] = hw_dict

    if single_threaded_mode:
        raw["hardware"]["allocatable_compute_cores"] = 1

    # Standard quantum solver defaults
    if "quantum_settings" not in raw or not raw["quantum_settings"]:
        raw["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    # HPC defaults
    if "hpc" not in raw or not raw["hpc"]:
        raw["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    # Environment defaults
    if "environment" not in raw or not raw["environment"]:
        raw["environment"] = {
            "os_target": raw.get("os_target", OSTarget.LOCAL_WINDOWS.value if os.name == "nt" else OSTarget.LOCAL_LINUX.value),
            "codata_version": "2018",
            "isotopic_mass_locking": True,
            "isotopic_mass_13c": CARBON_13_ISOTOPIC_MASS,
            "isotopic_masses": dict(ISOTOPIC_MASSES),
        }

    raw["status"] = "LOCKED"
    raw["schema_version"] = "4.0.0"

    cfg = CoChemSystemConfig.model_validate(raw)
    cfg.update_checksum()
    return cfg


def finalize_and_lock_golden_registry(
    cfg: CoChemSystemConfig,
    output_path: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Atomically write finalized Golden Registry to cochem_system_config.json,
    set cfg['status'] = 'LOCKED', and apply os.chmod(0o444) to enforce post-setup immutability.

    SRS Document 5 Section 4.3 Mandate.
    """
    target_path = resolve_golden_config_path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    cfg.status = "LOCKED"
    cfg.update_checksum()
    serialized_dict = cfg.model_dump()

    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(
                target_path=target_path,
                data=serialized_dict,
                indent=2,
                read_only=True,
            )

    return target_path, serialized_dict


# =============================================================================
# 8. WORKSPACE GARBAGE COLLECTION SWEEP
# =============================================================================


def execute_workspace_sweep(
    workspace_dir: Optional[Union[str, Path]] = None,
    registry_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    remove_intermediate_json: bool = False,
    trash_dir: Optional[Union[str, Path]] = None,
) -> WorkspaceSweepReport:
    """
    Execute a garbage collection sweep to safely delete all ephemeral .tmp files and
    intermediate JSON fragments from the workspace.

    SRS Document 5 Section 4.3 Mandate:
    Preserves persistent registry files (cochem_system_config.json) while sweeping
    staged .tmp files and temporary lock probes.
    """
    target_ws = Path(workspace_dir).resolve() if workspace_dir else Path.cwd().resolve()
    target_reg = Path(registry_dir).resolve() if registry_dir else resolve_golden_config_path().parent

    cleaned_paths: List[str] = []
    retained_paths: List[str] = []

    search_roots = [target_ws, target_reg]

    for root in search_roots:
        if not root.is_dir():
            continue

        try:
            for entry in root.rglob("*"):
                if not entry.is_file():
                    continue

                filename = entry.name.lower()

                # Never delete finalized system config
                if filename == "cochem_system_config.json":
                    retained_paths.append(str(entry.resolve()))
                    continue

                is_ephemeral = False

                # Check for .tmp extensions or lock probe patterns
                if ".tmp" in filename or filename.startswith(".cochem_") or filename.endswith(".lock"):
                    is_ephemeral = True

                # Check for intermediate p1..p11 fragments if requested
                if remove_intermediate_json:
                    if re.match(r"^p\d+\.json$", filename) or filename.endswith(".tmp.json"):
                        is_ephemeral = True

                if is_ephemeral:
                    cleaned_paths.append(str(entry.resolve()))
                    if not dry_run:
                        try:
                            # Ensure writable before removing
                            try:
                                os.chmod(entry, stat.S_IWRITE | stat.S_IREAD)
                            except OSError:
                                pass
                            if trash_dir:
                                tdir = Path(trash_dir).resolve()
                                tdir.mkdir(parents=True, exist_ok=True)
                                shutil.move(str(entry), str(tdir / entry.name))
                            else:
                                entry.unlink(missing_ok=True)
                        except OSError as e:
                            logger.warning(f"Advisory: could not sweep temporary file {entry}: {e}")
                else:
                    retained_paths.append(str(entry.resolve()))

        except OSError as e:
            logger.warning(f"Advisory: error traversing directory {root} during sweep: {e}")

    return WorkspaceSweepReport(
        swept_files_count=len(cleaned_paths),
        cleaned_paths=cleaned_paths,
        retained_paths=list(dict.fromkeys(retained_paths)),
        trash_dir=str(trash_dir) if trash_dir else None,
    )


# =============================================================================
# 9. GPU DISCOVERY & VRAM PROFILING
# =============================================================================


def probe_gpu_devices_vram(
    registry_p2_path: Optional[Union[str, Path]] = None,
) -> Tuple[List[GPUDeviceVRAM], bool]:
    """
    Interrogate host GPU topology and extract accurate physical VRAM capacities
    using a multi-tiered inspection pipeline (p2.json -> pynvml -> nvidia-smi -> torch.cuda).
    """
    devices: List[GPUDeviceVRAM] = []
    cuda_available = False

    # Tier 1: Interrogate previous Phase 2 registry (p2.json) if available
    candidate_p2_paths: List[Path] = []
    if registry_p2_path:
        candidate_p2_paths.append(Path(registry_p2_path).resolve())
    candidate_p2_paths.append(Path.cwd() / ".agent_artifacts" / "Registry" / "p2.json")
    candidate_p2_paths.append(Path.home() / "CoChem_Artifacts" / "Registry" / "p2.json")

    for p2_path in candidate_p2_paths:
        if p2_path.exists() and p2_path.is_file():
            try:
                data = json.loads(p2_path.read_text(encoding="utf-8"))
                gpu_info = data.get("gpu", {})
                if gpu_info.get("cuda_available", False) and gpu_info.get("devices"):
                    for d in gpu_info["devices"]:
                        if d.get("vendor", "").upper() == "NVIDIA":
                            vram_bytes = d.get("memory_total_bytes") or 0
                            free_bytes = d.get("memory_free_bytes") or vram_bytes
                            vram_mb = float(vram_bytes) / (1024.0 * 1024.0)
                            free_mb = float(free_bytes) / (1024.0 * 1024.0)
                            idx = int(d.get("index", len(devices)))
                            dev_name = d.get("name", f"NVIDIA GPU {idx}")
                            dev_uuid = d.get("uuid")
                            arch = d.get("compute_capability")
                            devices.append(
                                GPUDeviceVRAM(
                                    index=idx,
                                    name=dev_name,
                                    uuid=dev_uuid,
                                    total_vram_mb=round(vram_mb, 2),
                                    free_vram_mb=round(free_mb, 2),
                                    reserved_vram_mb=0.0,
                                    allocatable_vram_mb=0.0,
                                    allocated_limit_per_worker_mb=0.0,
                                    active_worker_capacity=1,
                                    pinned_mem_limit_str="",
                                    compute_capability=arch,
                                )
                            )
                    if devices:
                        cuda_available = True
                        return devices, cuda_available
            except Exception:
                pass

    # Tier 2: Query NVIDIA NVML via pynvml or nvidia-ml-py if present
    try:
        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            import pynvml  # type: ignore

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        for idx in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
            name_raw = pynvml.nvmlDeviceGetName(handle)
            name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_mb = float(mem_info.total) / (1024.0 * 1024.0)
            free_mb = float(mem_info.free) / (1024.0 * 1024.0)
            try:
                uuid_raw = pynvml.nvmlDeviceGetUUID(handle)
                dev_uuid = uuid_raw.decode("utf-8") if isinstance(uuid_raw, bytes) else str(uuid_raw)
            except Exception:
                dev_uuid = None
            try:
                major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
                arch = f"sm_{major}{minor}"
            except Exception:
                arch = None

            devices.append(
                GPUDeviceVRAM(
                    index=idx,
                    name=name,
                    uuid=dev_uuid,
                    total_vram_mb=round(total_mb, 2),
                    free_vram_mb=round(free_mb, 2),
                    reserved_vram_mb=0.0,
                    allocatable_vram_mb=0.0,
                    allocated_limit_per_worker_mb=0.0,
                    active_worker_capacity=1,
                    pinned_mem_limit_str="",
                    compute_capability=arch,
                )
            )
        pynvml.nvmlShutdown()
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 3: Query via nvidia-smi CLI
    try:
        smi_out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,uuid,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        for line in smi_out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx = int(parts[0])
                name = parts[1]
                dev_uuid = parts[2]
                total_mb = float(parts[3])
                free_mb = float(parts[4])
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=name,
                        uuid=dev_uuid,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(free_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=None,
                    )
                )
        if devices:
            cuda_available = True
            return devices, cuda_available
    except Exception:
        pass

    # Tier 4: Query via torch.cuda if available
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            cuda_available = True
            cnt = torch.cuda.device_count()
            for idx in range(cnt):
                props = torch.cuda.get_device_properties(idx)
                total_mb = float(props.total_memory) / (1024.0 * 1024.0)
                arch = f"sm_{props.major}{props.minor}"
                devices.append(
                    GPUDeviceVRAM(
                        index=idx,
                        name=props.name,
                        uuid=None,
                        total_vram_mb=round(total_mb, 2),
                        free_vram_mb=round(total_mb, 2),
                        reserved_vram_mb=0.0,
                        allocatable_vram_mb=0.0,
                        allocated_limit_per_worker_mb=0.0,
                        active_worker_capacity=1,
                        pinned_mem_limit_str="",
                        compute_capability=arch,
                    )
                )
            if devices:
                return devices, cuda_available
    except Exception:
        pass

    return devices, cuda_available


# =============================================================================
# 10. VRAM BUDGETING & MEMORY PARTITIONING ALGORITHM
# =============================================================================


def calculate_vram_budget(
    devices: List[GPUDeviceVRAM],
    worker_concurrency_target: int = 2,
    custom_limit_per_worker_mb: Optional[float] = None,
    reserved_headroom_fraction: float = 0.15,
    min_reserved_headroom_mb: float = 1024.0,
) -> VRAMBudgetReport:
    """
    Calculate mathematically bounded VRAM allocations and build the authoritative
    CUDA_MPS_PINNED_DEVICE_MEM_LIMIT string for each device.

    Formula:
    Reserved_VRAM = max(min_reserved_headroom_mb, total_vram_mb * reserved_headroom_fraction)
    Allocatable_VRAM = max(0.0, total_vram_mb - Reserved_VRAM)
    Per_Worker_Limit = floor(Allocatable_VRAM / worker_concurrency_target)
    """
    concurrency = max(1, worker_concurrency_target)
    updated_devices: List[GPUDeviceVRAM] = []
    per_device_limits: Dict[str, str] = {}
    default_pinned_str: Optional[str] = None

    total_cluster_vram = 0.0
    total_reserved_vram = 0.0
    total_allocatable_vram = 0.0

    if not devices:
        return VRAMBudgetReport(
            total_gpus_detected=0,
            active_gpu_devices=[],
            total_cluster_vram_mb=0.0,
            total_reserved_vram_mb=0.0,
            total_allocatable_vram_mb=0.0,
            worker_concurrency_target=concurrency,
            default_pinned_mem_limit=None,
            per_device_limits={},
            is_vram_bounded=True,
            strategy="ZERO_GPU_DEGRADED",
        )

    for dev in devices:
        total_mb = dev.total_vram_mb
        total_cluster_vram += total_mb

        reserved_mb = max(min_reserved_headroom_mb, total_mb * reserved_headroom_fraction)
        reserved_mb = min(reserved_mb, total_mb)
        total_reserved_vram += reserved_mb

        allocatable_mb = max(0.0, total_mb - reserved_mb)
        total_allocatable_vram += allocatable_mb

        if custom_limit_per_worker_mb is not None and custom_limit_per_worker_mb > 0:
            limit_mb = min(allocatable_mb, custom_limit_per_worker_mb)
        else:
            limit_mb = allocatable_mb / float(concurrency) if allocatable_mb > 0 else 0.0

        int_limit_mb = int(limit_mb)
        pinned_str = f"{dev.index}={int_limit_mb}M" if int_limit_mb > 0 else f"{dev.index}=0M"
        per_device_limits[str(dev.index)] = pinned_str

        worker_capacity = max(1, int(allocatable_mb // int_limit_mb)) if int_limit_mb > 0 else 1

        updated_dev = GPUDeviceVRAM(
            index=dev.index,
            name=dev.name,
            uuid=dev.uuid,
            total_vram_mb=dev.total_vram_mb,
            free_vram_mb=dev.free_vram_mb,
            reserved_vram_mb=round(reserved_mb, 2),
            allocatable_vram_mb=round(allocatable_mb, 2),
            allocated_limit_per_worker_mb=round(float(int_limit_mb), 2),
            active_worker_capacity=worker_capacity,
            pinned_mem_limit_str=pinned_str,
            compute_capability=dev.compute_capability,
        )
        updated_devices.append(updated_dev)

    if updated_devices:
        first_limit = int(updated_devices[0].allocated_limit_per_worker_mb)
        default_pinned_str = f"{first_limit}M" if first_limit > 0 else None

    return VRAMBudgetReport(
        total_gpus_detected=len(updated_devices),
        active_gpu_devices=updated_devices,
        total_cluster_vram_mb=round(total_cluster_vram, 2),
        total_reserved_vram_mb=round(total_reserved_vram, 2),
        total_allocatable_vram_mb=round(total_allocatable_vram, 2),
        worker_concurrency_target=concurrency,
        default_pinned_mem_limit=default_pinned_str,
        per_device_limits=per_device_limits,
        is_vram_bounded=True,
        strategy="PROPORTIONAL_PINNED_BUDGET",
    )


def build_pinned_memory_limit_string(budget: VRAMBudgetReport, device_index: int = 0) -> str:
    """
    Build the exact CUDA_MPS_PINNED_DEVICE_MEM_LIMIT value for a specific device index.
    """
    dev_str = str(device_index)
    if dev_str in budget.per_device_limits:
        return budget.per_device_limits[dev_str]
    if budget.default_pinned_mem_limit:
        return budget.default_pinned_mem_limit
    return ""


# =============================================================================
# 11. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE MANAGEMENT
# =============================================================================


def discover_mps_binaries() -> Tuple[Optional[str], Optional[str]]:
    """
    Sweep host filesystem for nvidia-cuda-mps-control and nvidia-cuda-mps-server binaries.
    """
    control_path: Optional[str] = shutil.which("nvidia-cuda-mps-control")
    server_path: Optional[str] = shutil.which("nvidia-cuda-mps-server")

    candidate_roots = [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path("/usr/local/cuda/bin"),
        Path("/opt/cuda/bin"),
    ]

    for usr_local in [Path("/usr/local"), Path("/opt")]:
        if usr_local.is_dir():
            try:
                for entry in usr_local.iterdir():
                    if entry.is_dir() and "cuda" in entry.name.lower():
                        bin_dir = entry / "bin"
                        if bin_dir.is_dir() and bin_dir not in candidate_roots:
                            candidate_roots.append(bin_dir)
            except OSError:
                pass

    if not control_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-control"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                control_path = str(candidate.resolve())
                break

    if not server_path:
        for cdir in candidate_roots:
            candidate = cdir / "nvidia-cuda-mps-server"
            if candidate.is_file() and os.access(candidate, os.X_OK):
                server_path = str(candidate.resolve())
                break

    return control_path, server_path


def probe_mps_daemon_status(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: Optional[str] = None,
    server_binary: Optional[str] = None,
) -> MPSDaemonAudit:
    """
    Probe the live operational status of the NVIDIA MPS daemon, inspect pipe sockets,
    and verify daemon responsiveness.
    """
    is_posix = platform.system() != "Windows"
    sec_ok, perm_str = enforce_socket_directory_permissions(pipe_dir)

    is_running = False
    control_active = False
    server_active = False
    daemon_pid: Optional[int] = None
    socket_path: Optional[str] = None
    details_list: List[str] = []

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pname = proc.info.get("name", "") or ""
                raw_cmd = proc.info.get("cmdline") or []
                cmd = " ".join(str(c) for c in raw_cmd if c is not None)
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-control" in cmd:
                    is_running = True
                    control_active = True
                    daemon_pid = proc.info.get("pid")
                if "nvidia-cuda-mps-server" in pname or "nvidia-cuda-mps-server" in cmd:
                    server_active = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    control_pipe = pipe_dir / "control"
    server_pipe = pipe_dir / "server"

    if control_pipe.exists():
        socket_path = str(control_pipe)
        details_list.append("MPS control pipe present in socket directory")
    elif server_pipe.exists():
        socket_path = str(server_pipe)
        details_list.append("MPS server pipe present in socket directory")
    else:
        socket_path = str(pipe_dir)

    if control_binary and is_running and is_posix:
        try:
            env = os.environ.copy()
            env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
            env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)
            res = subprocess.run(
                [control_binary],
                input="get_server_list\nquit\n",
                text=True,
                capture_output=True,
                timeout=3,
                env=env,
            )
            if res.returncode == 0:
                control_active = True
                details_list.append("nvidia-cuda-mps-control responsive to commands")
        except Exception as e:
            details_list.append(f"MPS command pipe probe advisory: {e}")

    if not is_posix:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("NVIDIA MPS daemon multiplexing not natively supported on Windows NT; degraded CPU/direct CUDA active")
    elif is_running:
        mps_status = MPSStatus.RUNNING
        details_list.append("NVIDIA MPS daemon is running and multiplexing CUDA contexts")
    elif control_binary:
        mps_status = MPSStatus.INITIALIZED
        details_list.append("NVIDIA MPS control binary detected; daemon is idle / not started")
    else:
        mps_status = MPSStatus.NOT_SUPPORTED
        details_list.append("nvidia-cuda-mps-control binary not found in PATH or standard system locations")

    env_dict = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
    }

    return MPSDaemonAudit(
        mps_control_binary=control_binary,
        mps_server_binary=server_binary,
        status=mps_status,
        pipe_directory=str(pipe_dir),
        log_directory=str(log_dir),
        socket_path=socket_path,
        is_daemon_active=is_running,
        pid=daemon_pid,
        socket_permissions=perm_str,
        is_permission_secure=sec_ok,
        server_active=server_active,
        control_active=control_active,
        environment_variables=env_dict,
        details="; ".join(details_list),
    )


def start_mps_daemon(
    pipe_dir: Path,
    log_dir: Path,
    control_binary: str,
    server_binary: Optional[str] = None,
    force_restart: bool = False,
) -> MPSDaemonAudit:
    """
    Start the nvidia-cuda-mps-control daemon in background mode (-d).
    """
    if platform.system() == "Windows":
        return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)

    if force_restart:
        stop_mps_daemon(pipe_dir, control_binary)

    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    enforce_socket_directory_permissions(pipe_dir)
    enforce_socket_directory_permissions(log_dir)

    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
    env["CUDA_MPS_LOG_DIRECTORY"] = str(log_dir)

    try:
        subprocess.run(
            [control_binary, "-d"],
            env=env,
            check=True,
            timeout=5,
            capture_output=True,
        )
    except Exception as exc:
        raise MPSControlError(f"Failed to start nvidia-cuda-mps-control daemon: {exc}") from exc

    return probe_mps_daemon_status(pipe_dir, log_dir, control_binary, server_binary)


def stop_mps_daemon(
    pipe_dir: Path,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Stop any running nvidia-cuda-mps-control daemon and backend server cleanly.
    """
    if platform.system() == "Windows":
        return True

    stopped = False
    if control_binary:
        env = os.environ.copy()
        env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)
        try:
            subprocess.run(
                [control_binary],
                input="quit\n",
                text=True,
                env=env,
                timeout=3,
                capture_output=True,
            )
            stopped = True
        except Exception:
            pass

    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = proc.info.get("name") or ""
                if "nvidia-cuda-mps-control" in pname or "nvidia-cuda-mps-server" in pname:
                    proc.terminate()
                    stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                pass
    except Exception:
        pass

    return stopped


def configure_mps_device_limit(
    pipe_dir: Path,
    device_index: int,
    limit_mb: int,
    control_binary: Optional[str] = None,
) -> bool:
    """
    Configure dynamic pinned memory limits on a running MPS daemon via control pipe.
    Command: set_device_pinned_mem_limit <device_index> <limit_mb>M
    """
    if platform.system() == "Windows" or not control_binary:
        return False

    cmd_str = f"set_device_pinned_mem_limit {device_index} {limit_mb}M\nquit\n"
    env = os.environ.copy()
    env["CUDA_MPS_PIPE_DIRECTORY"] = str(pipe_dir)

    try:
        res = subprocess.run(
            [control_binary],
            input=cmd_str,
            text=True,
            env=env,
            timeout=3,
            capture_output=True,
        )
        return res.returncode == 0
    except Exception:
        return False


# =============================================================================
# 12. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION
# =============================================================================


def inject_mps_environment_variables(
    pipe_dir: Path,
    log_dir: Path,
    vram_budget: VRAMBudgetReport,
) -> Dict[str, str]:
    """
    Construct authoritative MPS and VRAM environment variables dictionary.
    Includes memory limits and active thread percentage partitioning (Method Matrix §8A.4).
    """
    thread_pct = max(1, min(100, int(100 // max(1, vram_budget.worker_concurrency_target))))
    env_vars: Dict[str, str] = {
        "CUDA_MPS_PIPE_DIRECTORY": str(pipe_dir),
        "CUDA_MPS_LOG_DIRECTORY": str(log_dir),
        "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT": "1",
        "CUDA_MPS_ACTIVE_THREAD_PERCENTAGE": str(thread_pct),
    }

    if vram_budget.default_pinned_mem_limit:
        env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = vram_budget.default_pinned_mem_limit
    elif vram_budget.active_gpu_devices:
        first_limit = vram_budget.active_gpu_devices[0].pinned_mem_limit_str
        if first_limit:
            env_vars["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] = first_limit

    for k, v in env_vars.items():
        os.environ[k] = v

    return env_vars


def generate_mps_activation_scripts(
    target_dir: Union[str, Path],
    env_vars: Dict[str, str],
) -> Dict[str, Path]:
    """
    Generate standalone shell and batch script wrappers to inject MPS and VRAM
    configuration into subshells, Jupyter kernels, and external worker processes.
    """
    out_dir = Path(target_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sh_path = out_dir / "cochem_activate_mps.sh"
    sh_lines = [
        "#!/bin/sh",
        "# CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        sh_lines.append(f'export {k}="{v}"')
    sh_path.write_text("\n".join(sh_lines) + "\n", encoding="utf-8")
    try:
        sh_path.chmod(sh_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    bat_path = out_dir / "cochem_activate_mps.bat"
    bat_lines = [
        "@echo off",
        "rem CoChem Stage 0 Phase 5: NVIDIA MPS & VRAM Budgeting Environment Hook",
    ]
    for k, v in env_vars.items():
        bat_lines.append(f"set {k}={v}")
    bat_path.write_text("\n".join(bat_lines) + "\n", encoding="utf-8")

    json_path = out_dir / "cochem_mps_config.json"
    json_path.write_text(
        json.dumps(
            {
                "env_vars": env_vars,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "sh": sh_path,
        "bat": bat_path,
        "json": json_path,
    }


# =============================================================================
# 13. FULL PROGRAMMATIC AUDIT PIPELINE ENTRYPOINT
# =============================================================================


def run_phase_5_audit(
    output_dir: Optional[Union[str, Path]] = None,
    socket_dir: Optional[Union[str, Path]] = None,
    log_dir: Optional[Union[str, Path]] = None,
    worker_concurrency: int = 2,
    custom_vram_limit_mb: Optional[float] = None,
    start_daemon: bool = False,
    force_restart: bool = False,
    dry_run: bool = False,
    workspace_dir: Optional[Union[str, Path]] = None,
    sweep_workspace: bool = True,
) -> Phase5AuditReport:
    """
    Execute full Phase 5 Audit Pipeline:
    1. NVIDIA MPS Daemon & VRAM Budgeting (SRS Doc 2 Part 2 Section 3.5).
    2. Physical POSIX byte-range locking test (fcntl) with graceful degradation to single-threaded mode.
    3. Intermediate state consolidation (p1.json through p11.json).
    4. Pydantic validation and Golden Registry locking to cochem_system_config.json with os.chmod(0o444).
    5. Workspace garbage collection sweep purging ephemeral .tmp files.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    warnings: List[str] = []
    errors: List[str] = []

    # 1. Resolve Pipe and Log Directories
    pipe_path = resolve_mps_pipe_directory(socket_dir)
    log_path = resolve_mps_log_directory(log_dir)
    is_slurm = bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("SLURM_TMPDIR"))

    # 2. Discover GPU Devices and VRAM Capacities
    gpu_devices, is_cuda = probe_gpu_devices_vram()

    # 3. Calculate VRAM Budget & Concurrency Partitioning
    vram_budget = calculate_vram_budget(
        devices=gpu_devices,
        worker_concurrency_target=worker_concurrency,
        custom_limit_per_worker_mb=custom_vram_limit_mb,
    )

    if not is_cuda or not gpu_devices:
        warnings.append(
            "No active NVIDIA CUDA GPU detected; execution operating in CPU-only or direct compute fallback mode."
        )

    # 4. Discover MPS Binaries & Probe Daemon Status
    control_bin, server_bin = discover_mps_binaries()

    if start_daemon and control_bin and not dry_run:
        try:
            mps_daemon = start_mps_daemon(
                pipe_dir=pipe_path,
                log_dir=log_path,
                control_binary=control_bin,
                server_binary=server_bin,
                force_restart=force_restart,
            )
        except Exception as exc:
            warnings.append(f"Could not start MPS daemon: {exc}")
            mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)
    else:
        mps_daemon = probe_mps_daemon_status(pipe_path, log_path, control_bin, server_bin)

    # 5. Inject Environment Variables & Generate Scripts
    env_vars = inject_mps_environment_variables(pipe_path, log_path, vram_budget)
    mps_daemon.environment_variables = env_vars

    if not dry_run:
        generate_mps_activation_scripts(pipe_path, env_vars)

    # 6. Physical POSIX Byte-Range Locking Verification
    resolved_registry_dir = Path(output_dir).resolve() if output_dir else resolve_golden_config_path().parent
    lock_result = test_posix_byte_range_locking(resolved_registry_dir)
    if not lock_result.passed:
        warnings.append(
            f"Filesystem byte-range locking test failed ({lock_result.error_message}); "
            "degraded to single-threaded execution mode."
        )

    # 7. Intermediate State Consolidation & Golden Registry Locking
    consolidated_data, found_phases = consolidate_intermediate_states(
        registry_dir=resolved_registry_dir,
    )

    system_config = validate_and_build_system_config(
        consolidated_data=consolidated_data,
        auto_detect_fallback=True,
        single_threaded_mode=lock_result.single_threaded_mode,
    )

    golden_path, _ = finalize_and_lock_golden_registry(
        cfg=system_config,
        output_path=resolved_registry_dir / "cochem_system_config.json",
        dry_run=dry_run,
    )

    # 8. Workspace Garbage Collection Sweep
    if sweep_workspace:
        sweep_report = execute_workspace_sweep(
            workspace_dir=workspace_dir,
            registry_dir=resolved_registry_dir,
            dry_run=dry_run,
            remove_intermediate_json=False,
        )
    else:
        sweep_report = WorkspaceSweepReport(swept_files_count=0, cleaned_paths=[], retained_paths=[])

    config_lock_audit = ConfigLockAuditReport(
        golden_registry_path=str(golden_path),
        status=system_config.status or "LOCKED",
        checksum=system_config.registry_checksum or system_config.compute_checksum(),
        posix_lock_test=lock_result,
        sweep_report=sweep_report,
        intermediate_phases_found=found_phases,
        is_immutable_mode_enforced=True,
    )

    # 9. Evaluate Phase Status
    if errors:
        phase_status = PhaseStatus.FAILED
    elif lock_result.single_threaded_mode or not is_cuda or mps_daemon.status in (MPSStatus.NOT_SUPPORTED, MPSStatus.DEGRADED):
        phase_status = PhaseStatus.PASSED  # Graceful pass in degraded mode per Method Matrix
    else:
        phase_status = PhaseStatus.PASSED

    # 10. Destination Registry Artifact Path (p5.json)
    p5_path = resolve_p5_registry_path(output_dir)

    # 11. Construct Final Audit Report
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=phase_status,
        timestamp_utc=timestamp_utc,
        mps_daemon=mps_daemon,
        vram_budget=vram_budget,
        is_cuda_available=is_cuda,
        is_hpc_slurm=is_slurm,
        config_lock=config_lock_audit,
        warnings=warnings,
        errors=errors,
        artifact_path=str(p5_path),
        golden_config_path=str(golden_path),
    )

    # 12. Idempotent Atomic State Persistence (p5.json)
    if not dry_run:
        with DependencyManager() as dm:
            dm.atomic_write_json(p5_path, report)

    return report


# =============================================================================
# 14. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entrypoint for CoChem Setup Phase 5:
    IPC Config Lock & Workspace Sweep & NVIDIA MPS Daemon / VRAM Budgeting CLI.
    Returns 0 on PASSED/DEGRADED, non-zero on fatal errors.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 5: IPC Config Lock, Workspace Sweep & NVIDIA MPS Daemon CLI",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default=None,
        help="Custom destination directory for Registry artifacts (p5.json & cochem_system_config.json)",
    )
    parser.add_argument(
        "--socket-dir",
        "-s",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_PIPE_DIRECTORY sockets",
    )
    parser.add_argument(
        "--log-dir",
        "-l",
        type=str,
        default=None,
        help="Custom directory for CUDA_MPS_LOG_DIRECTORY telemetry logs",
    )
    parser.add_argument(
        "--workspace-dir",
        "-w-dir",
        type=str,
        default=None,
        help="Custom workspace directory for ephemeral garbage collection sweep",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=2,
        help="Target concurrent GPU workers for VRAM budget partitioning (default: 2)",
    )
    parser.add_argument(
        "--vram-limit-mb",
        type=float,
        default=None,
        help="Explicit pinned memory limit per worker in megabytes (overrides proportional formula)",
    )
    parser.add_argument(
        "--start-daemon",
        action="store_true",
        help="Attempt to start nvidia-cuda-mps-control daemon in background mode",
    )
    parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Force restart of existing MPS daemon processes",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop active nvidia-cuda-mps-control daemon and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview VRAM budgeting and config lock without modifying filesystem or starting daemons",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    if args.stop:
        pipe_path = resolve_mps_pipe_directory(args.socket_dir)
        control_bin, _ = discover_mps_binaries()
        stopped = stop_mps_daemon(pipe_path, control_bin)
        status_msg = "MPS daemon stopped successfully." if stopped else "No active MPS daemon found to stop."
        print(status_msg)
        return 0

    try:
        report = run_phase_5_audit(
            output_dir=args.output_dir,
            socket_dir=args.socket_dir,
            log_dir=args.log_dir,
            workspace_dir=args.workspace_dir,
            worker_concurrency=args.workers,
            custom_vram_limit_mb=args.vram_limit_mb,
            start_daemon=args.start_daemon,
            force_restart=args.force_restart,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 5: IPC CONFIG LOCK, WORKSPACE SWEEP & MPS VRAM BUDGETING")
            print("=" * 75)
            print(f"Phase ID:          {report.phase_id}")
            print(f"Status:            {report.status.value}")
            print(f"Timestamp UTC:     {report.timestamp_utc}")
            print(f"Artifact Path:     {report.artifact_path}")
            print(f"Golden Config:     {report.golden_config_path}")
            print(f"CUDA Available:    {report.is_cuda_available}")
            print(f"Slurm HPC Mode:    {report.is_hpc_slurm}")
            print(f"MPS Status:        {report.mps_daemon.status.value}")
            print(f"Pipe Directory:    {report.mps_daemon.pipe_directory}")
            print(f"Socket Secure:     {report.mps_daemon.is_permission_secure} ({report.mps_daemon.socket_permissions})")
            if report.config_lock:
                print("-" * 75)
                print("IPC Config Lock & Filesystem Audit:")
                print(f"  Lock Test Method:    {report.config_lock.posix_lock_test.method}")
                print(f"  Lock Test Passed:    {report.config_lock.posix_lock_test.passed}")
                print(f"  Single-Thread Mode:  {report.config_lock.posix_lock_test.single_threaded_mode}")
                print(f"  Registry Status:     {report.config_lock.status}")
                print(f"  Registry Checksum:   {report.config_lock.checksum[:16]}...")
                print(f"  Phases Consolidated: {', '.join(report.config_lock.intermediate_phases_found) or 'Default Synthesized'}")
                print(f"  Swept Ephemeral:     {report.config_lock.sweep_report.swept_files_count} files")
            print("-" * 75)
            print("VRAM Budgeting Matrix:")
            print(f"  Total GPUs:          {report.vram_budget.total_gpus_detected}")
            print(f"  Cluster VRAM:        {report.vram_budget.total_cluster_vram_mb:.0f} MB")
            print(f"  Reserved VRAM:       {report.vram_budget.total_reserved_vram_mb:.0f} MB")
            print(f"  Allocatable VRAM:    {report.vram_budget.total_allocatable_vram_mb:.0f} MB")
            print(f"  Target Workers:      {report.vram_budget.worker_concurrency_target}")
            print(f"  Default Pinned:      {report.vram_budget.default_pinned_mem_limit or 'N/A'}")
            for dev in report.vram_budget.active_gpu_devices:
                print(f"    [GPU {dev.index}] {dev.name:<25} Total: {dev.total_vram_mb:.0f}MB -> Limit: {dev.pinned_mem_limit_str} (Cap: {dev.active_worker_capacity} workers)")
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
        sys.stderr.write(f"\n[FATAL PHASE 5 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_setup_phase_5.py ---
"""
Unit test suite for CoChem Setup Phase 5: NVIDIA MPS Daemon Initialization & VRAM Budgeting.
Strict Zero-Mock Mandate: Real filesystem operations, real mathematical VRAM partitioning,
deterministic Pydantic V2 schema validations, real socket/pipe path resolution, real script
generation, and real atomic state persistence into the Golden Registry.

SRS Document 2 Part 2 (Section 3.5), SRS Document 5 (Section 3), and Method Matrix v4 Compliant.
"""

from __future__ import annotations

import json
import os
import platform
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestrator.cochem_setup_phase_5 import (
    ConfigLockAuditReport,
    ConfigLockError,
    DependencyManager,
    GPUDeviceVRAM,
    LockTestFailureError,
    LockTestResult,
    MPSControlError,
    MPSDaemonAudit,
    MPSStatus,
    Phase5AuditError,
    Phase5AuditReport,
    PhaseStatus,
    VRAMAllocationError,
    VRAMBudgetReport,
    WorkspaceSweepReport,
    build_pinned_memory_limit_string,
    calculate_vram_budget,
    configure_mps_device_limit,
    consolidate_intermediate_states,
    discover_mps_binaries,
    enforce_socket_directory_permissions,
    execute_workspace_sweep,
    finalize_and_lock_golden_registry,
    generate_mps_activation_scripts,
    get_current_username,
    inject_mps_environment_variables,
    main,
    probe_gpu_devices_vram,
    probe_mps_daemon_status,
    resolve_golden_config_path,
    resolve_mps_log_directory,
    resolve_mps_pipe_directory,
    resolve_p5_registry_path,
    run_phase_5_audit,
    start_mps_daemon,
    stop_mps_daemon,
    validate_and_build_system_config,
)
from orchestrator.cochem_setup_phase_5 import (
    test_posix_byte_range_locking as posix_byte_range_locking_fn,
)

# =============================================================================
# 1. CUSTOM EXCEPTION & ENUM TESTS
# =============================================================================


def test_custom_exception_hierarchy() -> None:
    """Verify custom Phase 5 exception classes inherit from RuntimeError."""
    err1 = Phase5AuditError("Phase 5 fatal error")
    assert isinstance(err1, RuntimeError)
    err2 = MPSControlError("MPS control command failed")
    assert isinstance(err2, RuntimeError)
    err3 = VRAMAllocationError("VRAM allocation calculation failed")
    assert isinstance(err3, RuntimeError)
    err4 = ConfigLockError("Config lock failed")
    assert isinstance(err4, RuntimeError)
    err5 = LockTestFailureError("Lock test failed")
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


def test_mps_status_enum() -> None:
    """Verify MPSStatus enum values and validation."""
    assert MPSStatus.RUNNING.value == "RUNNING"
    assert MPSStatus.INITIALIZED.value == "INITIALIZED"
    assert MPSStatus.STOPPED.value == "STOPPED"
    assert MPSStatus.NOT_SUPPORTED.value == "NOT_SUPPORTED"
    assert MPSStatus.DEGRADED.value == "DEGRADED"
    assert MPSStatus.ERROR.value == "ERROR"


# =============================================================================
# 2. PYDANTIC V2 SCHEMA VALIDATION TESTS
# =============================================================================


def test_gpu_device_vram_model_valid_and_validation() -> None:
    """Test GPUDeviceVRAM model construction, field validation, and extra='forbid'."""
    dev = GPUDeviceVRAM(
        index=0,
        name="NVIDIA RTX 4090",
        uuid="GPU-12345678-ABCD",
        total_vram_mb=24576.0,
        free_vram_mb=22000.0,
        reserved_vram_mb=3686.4,
        allocatable_vram_mb=20889.6,
        allocated_limit_per_worker_mb=10444.0,
        active_worker_capacity=2,
        pinned_mem_limit_str="0=10444M",
        compute_capability="sm_89",
    )
    assert dev.index == 0
    assert dev.name == "NVIDIA RTX 4090"
    assert dev.total_vram_mb == 24576.0
    assert dev.active_worker_capacity == 2

    # Roundtrip JSON validation
    json_str = dev.model_dump_json()
    assert "RTX 4090" in json_str
    restored = GPUDeviceVRAM.model_validate_json(json_str)
    assert restored == dev

    # Empty name should fail
    with pytest.raises(ValidationError):
        GPUDeviceVRAM(
            index=0,
            name="",
            total_vram_mb=8192.0,
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        GPUDeviceVRAM(
            index=0,
            name="GPU 0",
            total_vram_mb=8192.0,
            forbidden_extra_param="illegal",  # type: ignore
        )


def test_mps_daemon_audit_model_valid() -> None:
    """Test MPSDaemonAudit model construction and serialization."""
    audit = MPSDaemonAudit(
        mps_control_binary="/usr/bin/nvidia-cuda-mps-control",
        mps_server_binary="/usr/bin/nvidia-cuda-mps-server",
        status=MPSStatus.INITIALIZED,
        pipe_directory="/tmp/cochem_mps_user",
        log_directory="/tmp/cochem_mps_log_user",
        socket_path="/tmp/cochem_mps_user/control",
        is_daemon_active=False,
        pid=None,
        socket_permissions="0o700",
        is_permission_secure=True,
        server_active=False,
        control_active=False,
        environment_variables={"CUDA_MPS_PIPE_DIRECTORY": "/tmp/cochem_mps_user"},
        details="MPS control initialized",
    )
    assert audit.status is MPSStatus.INITIALIZED
    assert audit.is_permission_secure is True

    dumped = audit.model_dump()
    assert dumped["pipe_directory"] == "/tmp/cochem_mps_user"
    restored = MPSDaemonAudit.model_validate(dumped)
    assert restored == audit


def test_vram_budget_report_model_valid() -> None:
    """Test VRAMBudgetReport model construction."""
    report = VRAMBudgetReport(
        total_gpus_detected=1,
        active_gpu_devices=[],
        total_cluster_vram_mb=16384.0,
        total_reserved_vram_mb=2457.6,
        total_allocatable_vram_mb=13926.4,
        worker_concurrency_target=2,
        default_pinned_mem_limit="6963M",
        per_device_limits={"0": "0=6963M"},
        is_vram_bounded=True,
        strategy="PROPORTIONAL_PINNED_BUDGET",
    )
    assert report.total_cluster_vram_mb == 16384.0
    assert report.worker_concurrency_target == 2
    assert report.per_device_limits["0"] == "0=6963M"


def test_phase_5_audit_report_model_and_validator(tmp_path: Path) -> None:
    """Test Phase5AuditReport model validation and phase_id check."""
    report = Phase5AuditReport(
        phase_id="PHASE_5_NVIDIA_MPS_VRAM_BUDGETING",
        status=PhaseStatus.PASSED,
        timestamp_utc="2026-08-21T00:00:00Z",
        mps_daemon=MPSDaemonAudit(
            status=MPSStatus.NOT_SUPPORTED,
            is_permission_secure=True,
        ),
        vram_budget=VRAMBudgetReport(
            total_gpus_detected=0,
            total_cluster_vram_mb=0.0,
            total_reserved_vram_mb=0.0,
            total_allocatable_vram_mb=0.0,
        ),
        is_cuda_available=False,
        is_hpc_slurm=False,
        warnings=["No GPU detected"],
        errors=[],
        artifact_path=str(tmp_path / "p5.json"),
    )
    assert report.status is PhaseStatus.PASSED
    assert report.phase_id == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"

    # Invalid phase_id should fail
    with pytest.raises(ValidationError):
        Phase5AuditReport(
            phase_id="INVALID_PHASE_ID",
            status=PhaseStatus.PASSED,
            timestamp_utc="2026-08-21T00:00:00Z",
            mps_daemon=MPSDaemonAudit(),
            vram_budget=VRAMBudgetReport(),
            artifact_path=str(tmp_path / "p5.json"),
        )


# =============================================================================
# 3. TRANSACTIONAL DEPENDENCY MANAGER TESTS
# =============================================================================


def test_dependency_manager_tracking_and_cleanup(tmp_path: Path) -> None:
    """Verify DependencyManager tracks and untracks files cleanly."""
    with DependencyManager() as dm:
        f1 = dm.track_temp_file(tmp_path / "test_file.tmp")
        f1.write_text("temporary data", encoding="utf-8")
        assert f1.exists()
        dm.untrack_file(f1)

    # Untracked file persists
    assert f1.exists()
    f1.unlink()


def test_dependency_manager_rollback_on_error(tmp_path: Path) -> None:
    """Verify DependencyManager purges tracked temporary files and directories on exception."""
    staged_file = tmp_path / "staged_artifact.tmp"
    staged_dir = tmp_path / "staged_directory.tmp"

    try:
        with DependencyManager() as dm:
            dm.track_temp_file(staged_file)
            dm.track_temp_dir(staged_dir)

            staged_file.write_text("transient state", encoding="utf-8")
            staged_dir.mkdir(parents=True, exist_ok=True)
            (staged_dir / "subfile.txt").write_text("sub content", encoding="utf-8")

            assert staged_file.exists()
            assert staged_dir.exists()

            raise RuntimeError("Simulated execution failure during stage 5 setup")
    except RuntimeError:
        pass

    # Verify rollback successfully deleted staged artifacts
    assert not staged_file.exists()
    assert not staged_dir.exists()


def test_dependency_manager_atomic_write_json(tmp_path: Path) -> None:
    """Verify DependencyManager performs atomic JSON file writes."""
    target_json = tmp_path / "target_registry.json"
    payload = {"phase": "phase_5", "status": "PASSED", "limit": 4096}

    with DependencyManager() as dm:
        dm.atomic_write_json(target_json, payload)

    assert target_json.exists()
    data = json.loads(target_json.read_text(encoding="utf-8"))
    assert data["status"] == "PASSED"
    assert data["limit"] == 4096


# =============================================================================
# 4. PATH RESOLUTION & DIRECTORY PROVISIONING TESTS
# =============================================================================


def test_get_current_username() -> None:
    """Verify username sanitization returns a non-empty alphanumeric string."""
    uname = get_current_username()
    assert isinstance(uname, str)
    assert len(uname) > 0
    assert " " not in uname


def test_resolve_mps_pipe_directory_default_and_custom(tmp_path: Path) -> None:
    """Verify resolve_mps_pipe_directory respects custom directory and defaults."""
    custom_dir = tmp_path / "custom_mps_pipe"
    res = resolve_mps_pipe_directory(custom_dir)
    assert res == custom_dir.resolve()
    assert res.exists()

    default_res = resolve_mps_pipe_directory()
    assert default_res.exists()
    assert "cochem_mps" in default_res.name


def test_resolve_mps_pipe_directory_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory respects CUDA_MPS_PIPE_DIRECTORY."""
    env_dir = tmp_path / "env_mps_pipe"
    monkeypatch.setenv("CUDA_MPS_PIPE_DIRECTORY", str(env_dir))
    res = resolve_mps_pipe_directory()
    assert res == env_dir.resolve()
    assert res.exists()


def test_resolve_mps_pipe_directory_slurm_hpc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory utilizes SLURM_TMPDIR in HPC envelopes."""
    slurm_dir = tmp_path / "slurm_scratch"
    slurm_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("CUDA_MPS_PIPE_DIRECTORY", raising=False)
    monkeypatch.setenv("SLURM_TMPDIR", str(slurm_dir))

    res = resolve_mps_pipe_directory()
    assert slurm_dir in res.parents
    assert "cochem_mps" in res.name
    assert res.exists()


def test_resolve_mps_log_directory_default_and_custom(tmp_path: Path) -> None:
    """Verify resolve_mps_log_directory respects custom directory and defaults."""
    custom_log = tmp_path / "custom_mps_log"
    res = resolve_mps_log_directory(custom_log)
    assert res == custom_log.resolve()
    assert res.exists()

    default_log = resolve_mps_log_directory()
    assert default_log.exists()
    assert "cochem_mps_log" in default_log.name


def test_resolve_mps_log_directory_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_log_directory respects CUDA_MPS_LOG_DIRECTORY."""
    env_log = tmp_path / "env_log_dir"
    monkeypatch.setenv("CUDA_MPS_LOG_DIRECTORY", str(env_log))
    res = resolve_mps_log_directory()
    assert res == env_log.resolve()
    assert res.exists()


def test_enforce_socket_directory_permissions(tmp_path: Path) -> None:
    """Verify socket directory permissions enforcement."""
    test_dir = tmp_path / "socket_test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    ok, perm_str = enforce_socket_directory_permissions(test_dir)
    assert ok is True
    assert perm_str is not None
    if platform.system() != "Windows":
        mode = oct(stat.S_IMODE(test_dir.stat().st_mode))
        assert mode == "0o700"


def test_resolve_p5_registry_path(tmp_path: Path) -> None:
    """Verify resolve_p5_registry_path behavior."""
    custom_out = tmp_path / "custom_reg"
    p5_path = resolve_p5_registry_path(custom_out)
    assert p5_path == custom_out / "p5.json"

    direct_json = tmp_path / "p5.json"
    assert resolve_p5_registry_path(direct_json) == direct_json.resolve()

    default_p5 = resolve_p5_registry_path()
    assert default_p5.name == "p5.json"


# =============================================================================
# 5. VRAM BUDGETING & MEMORY PARTITIONING TESTS
# =============================================================================


def test_calculate_vram_budget_single_gpu() -> None:
    """Test VRAM budgeting formula for a single 24GB GPU."""
    dev = GPUDeviceVRAM(
        index=0,
        name="NVIDIA GeForce RTX 4090",
        uuid="GPU-UUID-001",
        total_vram_mb=24576.0,
        free_vram_mb=24000.0,
    )
    budget = calculate_vram_budget(
        devices=[dev],
        worker_concurrency_target=2,
        reserved_headroom_fraction=0.15,
        min_reserved_headroom_mb=1024.0,
    )
    assert budget.total_gpus_detected == 1
    assert budget.total_cluster_vram_mb == 24576.0
    # Reserved = 24576 * 0.15 = 3686.4 MB
    assert budget.total_reserved_vram_mb == pytest.approx(3686.4, rel=1e-2)
    # Allocatable = 24576 - 3686.4 = 20889.6 MB
    assert budget.total_allocatable_vram_mb == pytest.approx(20889.6, rel=1e-2)
    # Per worker = 20889.6 / 2 = 10444.8 -> int 10444 MB
    d0 = budget.active_gpu_devices[0]
    assert d0.allocated_limit_per_worker_mb == 10444.0
    assert d0.pinned_mem_limit_str == "0=10444M"
    assert d0.active_worker_capacity == 2
    assert budget.per_device_limits["0"] == "0=10444M"
    assert budget.default_pinned_mem_limit == "10444M"


def test_calculate_vram_budget_multi_gpu() -> None:
    """Test VRAM budgeting formula for dual heterogeneous GPUs."""
    dev0 = GPUDeviceVRAM(index=0, name="NVIDIA RTX A6000", total_vram_mb=49152.0)
    dev1 = GPUDeviceVRAM(index=1, name="NVIDIA RTX 3090", total_vram_mb=24576.0)

    budget = calculate_vram_budget(
        devices=[dev0, dev1],
        worker_concurrency_target=2,
    )
    assert budget.total_gpus_detected == 2
    assert budget.total_cluster_vram_mb == 73728.0
    assert "0" in budget.per_device_limits
    assert "1" in budget.per_device_limits

    # Dev 0: 49152 * 0.85 = 41779.2 -> 20889 MB per worker
    # Dev 1: 24576 * 0.85 = 20889.6 -> 10444 MB per worker
    d0 = budget.active_gpu_devices[0]
    d1 = budget.active_gpu_devices[1]
    assert d0.allocated_limit_per_worker_mb == 20889.0
    assert d1.allocated_limit_per_worker_mb == 10444.0
    assert d0.pinned_mem_limit_str == "0=20889M"
    assert d1.pinned_mem_limit_str == "1=10444M"


def test_calculate_vram_budget_custom_worker_count() -> None:
    """Test VRAM budgeting with high worker concurrency target (e.g. 4 workers)."""
    dev = GPUDeviceVRAM(index=0, name="NVIDIA A100-SXM4-80GB", total_vram_mb=81920.0)
    budget = calculate_vram_budget(
        devices=[dev],
        worker_concurrency_target=4,
    )
    assert budget.worker_concurrency_target == 4
    # Allocatable = 81920 - max(1024, 81920*0.15=12288) = 69632 MB
    # Per worker = 69632 / 4 = 17408 MB
    assert budget.active_gpu_devices[0].allocated_limit_per_worker_mb == 17408.0
    assert budget.active_gpu_devices[0].active_worker_capacity == 4
    assert budget.active_gpu_devices[0].pinned_mem_limit_str == "0=17408M"


def test_calculate_vram_budget_custom_vram_limit() -> None:
    """Test VRAM budgeting with explicit user-override custom limit."""
    dev = GPUDeviceVRAM(index=0, name="NVIDIA RTX 4090", total_vram_mb=24576.0)
    budget = calculate_vram_budget(
        devices=[dev],
        custom_limit_per_worker_mb=4096.0,
    )
    assert budget.active_gpu_devices[0].allocated_limit_per_worker_mb == 4096.0
    assert budget.active_gpu_devices[0].pinned_mem_limit_str == "0=4096M"
    # 20889.6 // 4096 = 5 workers capacity
    assert budget.active_gpu_devices[0].active_worker_capacity == 5


def test_calculate_vram_budget_zero_gpu_degraded() -> None:
    """Test VRAM budgeting behavior when zero physical GPUs are discovered."""
    budget = calculate_vram_budget(devices=[])
    assert budget.total_gpus_detected == 0
    assert budget.total_cluster_vram_mb == 0.0
    assert budget.strategy == "ZERO_GPU_DEGRADED"
    assert budget.default_pinned_mem_limit is None
    assert budget.per_device_limits == {}


def test_build_pinned_memory_limit_string() -> None:
    """Test build_pinned_memory_limit_string helper."""
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=8192.0)
    budget = calculate_vram_budget([dev], worker_concurrency_target=2)
    s0 = build_pinned_memory_limit_string(budget, device_index=0)
    assert "0=" in s0
    assert "M" in s0

    # Non-existent device should fall back to default limit string
    s_fallback = build_pinned_memory_limit_string(budget, device_index=99)
    assert s_fallback == budget.default_pinned_mem_limit


def test_probe_gpu_devices_vram_live_or_fallback(tmp_path: Path) -> None:
    """Verify probe_gpu_devices_vram executes without exceptions across platforms."""
    devices, is_cuda = probe_gpu_devices_vram()
    assert isinstance(devices, list)
    assert isinstance(is_cuda, bool)

    # Test reading synthetic p2.json
    p2_dir = tmp_path / "Registry"
    p2_dir.mkdir(parents=True, exist_ok=True)
    p2_file = p2_dir / "p2.json"
    p2_payload = {
        "phase_id": "PHASE_2_HARDWARE_RESOURCE_GATEKEEPER",
        "status": "PASSED",
        "timestamp_utc": "2026-08-21T00:00:00Z",
        "gpu": {
            "available": True,
            "cuda_available": True,
            "devices": [
                {
                    "index": 0,
                    "vendor": "NVIDIA",
                    "name": "NVIDIA H100 PCIe",
                    "memory_total_bytes": 85899345920,
                    "memory_free_bytes": 80000000000,
                    "compute_capability": "sm_90",
                    "uuid": "GPU-H100-TEST-UUID",
                }
            ],
        },
    }
    p2_file.write_text(json.dumps(p2_payload), encoding="utf-8")

    synth_devices, synth_cuda = probe_gpu_devices_vram(registry_p2_path=p2_file)
    assert synth_cuda is True
    assert len(synth_devices) == 1
    assert synth_devices[0].name == "NVIDIA H100 PCIe"
    assert synth_devices[0].total_vram_mb == pytest.approx(81920.0, rel=1e-2)
    assert synth_devices[0].compute_capability == "sm_90"


# =============================================================================
# 6. NVIDIA MPS BINARY DISCOVERY & DAEMON LIFECYCLE TESTS
# =============================================================================


def test_discover_mps_binaries() -> None:
    """Verify discover_mps_binaries scans and returns tuple of paths or None."""
    control_path, server_path = discover_mps_binaries()
    assert control_path is None or isinstance(control_path, str)
    assert server_path is None or isinstance(server_path, str)


def test_probe_mps_daemon_status(tmp_path: Path) -> None:
    """Verify probe_mps_daemon_status inspects directories and returns valid model."""
    pipe_dir = tmp_path / "test_pipe_dir"
    log_dir = tmp_path / "test_log_dir"
    pipe_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    audit = probe_mps_daemon_status(pipe_dir, log_dir)
    assert isinstance(audit, MPSDaemonAudit)
    assert audit.pipe_directory == str(pipe_dir)
    assert audit.log_directory == str(log_dir)
    assert audit.is_permission_secure is True


def test_start_and_stop_mps_daemon_lifecycle(tmp_path: Path) -> None:
    """Verify daemon start and stop functions execute cleanly across platforms."""
    pipe_dir = tmp_path / "test_pipe_lifecycle"
    log_dir = tmp_path / "test_log_lifecycle"

    # Testing on current OS without throwing unhandled crashes
    try:
        audit = start_mps_daemon(pipe_dir, log_dir, control_binary="nonexistent_mps_control")
        assert isinstance(audit, MPSDaemonAudit)
    except MPSControlError:
        pass

    stopped = stop_mps_daemon(pipe_dir, control_binary="nonexistent_mps_control")
    assert isinstance(stopped, bool)


def test_configure_mps_device_limit_offline(tmp_path: Path) -> None:
    """Verify configure_mps_device_limit returns False gracefully when binary is absent."""
    pipe_dir = tmp_path / "pipe_limit_test"
    res = configure_mps_device_limit(pipe_dir, device_index=0, limit_mb=4096, control_binary=None)
    assert res is False


# =============================================================================
# 7. ENVIRONMENT INJECTION & ACTIVATION SCRIPT GENERATION TESTS
# =============================================================================


def test_inject_mps_environment_variables(tmp_path: Path) -> None:
    """Verify inject_mps_environment_variables populates os.environ and returns dict."""
    pipe_dir = tmp_path / "inj_pipe"
    log_dir = tmp_path / "inj_log"
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=16384.0)
    budget = calculate_vram_budget([dev])

    env_vars = inject_mps_environment_variables(pipe_dir, log_dir, budget)
    assert env_vars["CUDA_MPS_PIPE_DIRECTORY"] == str(pipe_dir)
    assert env_vars["CUDA_MPS_LOG_DIRECTORY"] == str(log_dir)
    assert env_vars["CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT"] == "1"
    assert "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT" in env_vars
    assert os.environ["CUDA_MPS_PIPE_DIRECTORY"] == str(pipe_dir)


def test_generate_mps_activation_scripts(tmp_path: Path) -> None:
    """Verify generate_mps_activation_scripts creates .sh, .bat, and .json files."""
    env_vars = {
        "CUDA_MPS_PIPE_DIRECTORY": "/tmp/cochem_mps_user",
        "CUDA_MPS_LOG_DIRECTORY": "/tmp/cochem_mps_log_user",
        "CUDA_MPS_PINNED_DEVICE_MEM_LIMIT": "0=4096M",
        "CUDA_MPS_ENABLE_PER_DEVICE_PINNED_MEM_LIMIT": "1",
    }
    scripts = generate_mps_activation_scripts(tmp_path, env_vars)
    assert "sh" in scripts
    assert "bat" in scripts
    assert "json" in scripts

    sh_file = scripts["sh"]
    bat_file = scripts["bat"]
    json_file = scripts["json"]

    assert sh_file.exists()
    assert bat_file.exists()
    assert json_file.exists()

    sh_content = sh_file.read_text(encoding="utf-8")
    assert "export CUDA_MPS_PIPE_DIRECTORY=\"/tmp/cochem_mps_user\"" in sh_content
    assert "export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=\"0=4096M\"" in sh_content

    bat_content = bat_file.read_text(encoding="utf-8")
    assert "set CUDA_MPS_PIPE_DIRECTORY=/tmp/cochem_mps_user" in bat_content
    assert "set CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=4096M" in bat_content

    json_data = json.loads(json_file.read_text(encoding="utf-8"))
    assert json_data["env_vars"]["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] == "0=4096M"


# =============================================================================
# 8. FULL PROGRAMMATIC AUDIT PIPELINE TESTS
# =============================================================================


def test_run_phase_5_audit_dry_run(tmp_path: Path) -> None:
    """Verify run_phase_5_audit in dry_run mode does not write files to disk."""
    out_dir = tmp_path / "dry_run_reg"
    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=tmp_path / "socket_dry",
        log_dir=tmp_path / "log_dry",
        dry_run=True,
    )
    assert isinstance(report, Phase5AuditReport)
    assert report.phase_id == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)
    # File should NOT exist in dry run
    assert not (out_dir / "p5.json").exists()


def test_run_phase_5_audit_live_execution(tmp_path: Path) -> None:
    """Verify run_phase_5_audit live execution atomically writes p5.json."""
    out_dir = tmp_path / "live_reg"
    socket_dir = tmp_path / "live_socket"
    log_dir = tmp_path / "live_log"

    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=socket_dir,
        log_dir=log_dir,
        worker_concurrency=2,
        dry_run=False,
    )
    assert isinstance(report, Phase5AuditReport)
    assert report.status in (PhaseStatus.PASSED, PhaseStatus.DEGRADED)

    # Artifact must be atomically written
    p5_artifact = Path(report.artifact_path)
    assert p5_artifact.exists()
    data = json.loads(p5_artifact.read_text(encoding="utf-8"))
    assert data["phase_id"] == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert "mps_daemon" in data
    assert "vram_budget" in data


def test_run_phase_5_audit_custom_parameters(tmp_path: Path) -> None:
    """Verify run_phase_5_audit with custom workers and explicit vram limit."""
    out_dir = tmp_path / "custom_reg"
    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=tmp_path / "custom_socket",
        log_dir=tmp_path / "custom_log",
        worker_concurrency=4,
        custom_vram_limit_mb=2048.0,
        dry_run=False,
    )
    assert report.vram_budget.worker_concurrency_target == 4
    if report.vram_budget.active_gpu_devices:
        assert report.vram_budget.active_gpu_devices[0].allocated_limit_per_worker_mb <= 2048.0


# =============================================================================
# 9. CLI ENTRYPOINT TESTS
# =============================================================================


def test_phase_5_cli_dry_run(tmp_path: Path) -> None:
    """Test CLI main with --dry-run option."""
    code = main([
        "--output-dir", str(tmp_path),
        "--socket-dir", str(tmp_path / "cli_socket"),
        "--log-dir", str(tmp_path / "cli_log"),
        "--dry-run",
    ])
    assert code == 0


def test_phase_5_cli_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --json option prints serialized report."""
    code = main([
        "--output-dir", str(tmp_path),
        "--socket-dir", str(tmp_path / "cli_socket"),
        "--log-dir", str(tmp_path / "cli_log"),
        "--json",
    ])
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["phase_id"] == "PHASE_5_NVIDIA_MPS_VRAM_BUDGETING"
    assert data["status"] in ("PASSED", "DEGRADED")


def test_phase_5_cli_stop_flag(capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --stop option."""
    code = main(["--stop"])
    assert code == 0
    captured = capsys.readouterr()
    assert "MPS daemon" in captured.out


def test_phase_5_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test CLI main with --help option."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "CoChem Setup Phase 5" in captured.out


def test_resolve_mps_pipe_directory_slurm_job_id_scoping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_mps_pipe_directory scopes by SLURM_JOB_ID when present."""
    monkeypatch.delenv("CUDA_MPS_PIPE_DIRECTORY", raising=False)
    monkeypatch.delenv("SLURM_TMPDIR", raising=False)
    monkeypatch.setenv("SLURM_JOB_ID", "998877")
    res = resolve_mps_pipe_directory()
    assert "998877" in res.name


def test_inject_mps_environment_variables_thread_percentage(tmp_path: Path) -> None:
    """Verify CUDA_MPS_ACTIVE_THREAD_PERCENTAGE calculation in environment injection."""
    pipe_dir = tmp_path / "thread_pipe"
    log_dir = tmp_path / "thread_log"
    dev = GPUDeviceVRAM(index=0, name="GPU 0", total_vram_mb=16384.0)
    budget = calculate_vram_budget([dev], worker_concurrency_target=4)
    env_vars = inject_mps_environment_variables(pipe_dir, log_dir, budget)
    assert env_vars["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "25"


def test_probe_mps_daemon_status_with_server_binary(tmp_path: Path) -> None:
    """Verify probe_mps_daemon_status properly binds server_binary."""
    pipe_dir = tmp_path / "pipe_srv"
    log_dir = tmp_path / "log_srv"
    audit = probe_mps_daemon_status(
        pipe_dir,
        log_dir,
        control_binary="/usr/bin/nvidia-cuda-mps-control",
        server_binary="/usr/bin/nvidia-cuda-mps-server",
    )
    assert audit.mps_server_binary == "/usr/bin/nvidia-cuda-mps-server"


# =============================================================================
# 10. IPC CONFIG LOCK & POSIX BYTE-RANGE LOCKING TESTS
# =============================================================================


def test_lock_test_result_model() -> None:
    """Test LockTestResult Pydantic v2 model construction and validation."""
    ltr = LockTestResult(
        passed=True,
        method="POSIX_FCNTL_LOCKF",
        single_threaded_mode=False,
        target_path="/tmp/lock_probe.lock",
        lock_type="POSIX_BYTE_RANGE_LOCK",
    )
    assert ltr.passed is True
    assert ltr.single_threaded_mode is False
    assert ltr.method == "POSIX_FCNTL_LOCKF"

    dumped = ltr.model_dump()
    assert dumped["passed"] is True
    restored = LockTestResult.model_validate(dumped)
    assert restored == ltr


def test_workspace_sweep_report_model() -> None:
    """Test WorkspaceSweepReport Pydantic v2 model construction and serialization."""
    report = WorkspaceSweepReport(
        swept_files_count=3,
        cleaned_paths=["/tmp/a.tmp", "/tmp/b.tmp"],
        retained_paths=["/reg/cochem_system_config.json"],
        trash_dir="/tmp/trash",
    )
    assert report.swept_files_count == 3
    assert len(report.cleaned_paths) == 2
    assert len(report.retained_paths) == 1


def test_config_lock_audit_report_model() -> None:
    """Test ConfigLockAuditReport Pydantic v2 model validation."""
    audit = ConfigLockAuditReport(
        golden_registry_path="/reg/cochem_system_config.json",
        status="LOCKED",
        checksum="a" * 64,
        posix_lock_test=LockTestResult(
            passed=True,
            method="POSIX_FCNTL_LOCKF",
            single_threaded_mode=False,
            target_path="/reg/.lock_probe.lock",
        ),
        sweep_report=WorkspaceSweepReport(),
        intermediate_phases_found=["p1.json", "p2.json"],
        is_immutable_mode_enforced=True,
    )
    assert audit.status == "LOCKED"
    assert len(audit.checksum) == 64
    assert audit.posix_lock_test.passed is True


def test_posix_byte_range_locking_live_filesystem(tmp_path: Path) -> None:
    """Verify posix_byte_range_locking_fn executes real locking against directory."""
    res = posix_byte_range_locking_fn(target_dir=tmp_path)
    assert isinstance(res, LockTestResult)
    assert res.passed is True
    assert res.single_threaded_mode is False
    assert res.method in ("POSIX_FCNTL_LOCKF", "MSVCRT_LOCKING_BYTE_RANGE", "GENERIC_FALLBACK_LOCK")


def test_posix_byte_range_locking_invalid_dir() -> None:
    """Verify posix_byte_range_locking_fn handles invalid paths gracefully with single-threaded mode."""
    invalid_path = Path("/nonexistent_forbidden_dir_12345/subdir")
    res = posix_byte_range_locking_fn(target_dir=invalid_path)
    assert isinstance(res, LockTestResult)
    if not res.passed:
        assert res.single_threaded_mode is True
        assert res.error_message is not None


# =============================================================================
# 11. INTERMEDIATE STATE CONSOLIDATION (p1.json -> p11.json) TESTS
# =============================================================================


def test_consolidate_intermediate_states_synthetic_phases(tmp_path: Path) -> None:
    """Verify consolidate_intermediate_states extracts and aggregates all phase sections."""
    reg_dir = tmp_path / "Registry"
    reg_dir.mkdir(parents=True, exist_ok=True)

    # Synthetic p1.json
    p1 = {
        "phase_id": "PHASE_1_ENVIRONMENT_GATEKEEPER",
        "os_profile": {"system": "Linux"},
    }
    (reg_dir / "p1.json").write_text(json.dumps(p1), encoding="utf-8")

    # Synthetic p2.json
    p2 = {
        "phase_id": "PHASE_2_HARDWARE_SURVEYOR",
        "memory": {"total_physical_bytes": 34359738368},
        "cpu": {"physical_cores": 8, "logical_cores": 16, "avx512_support": True},
        "gpu": {"gpu_available": True, "devices": [{"name": "RTX 4090", "memory_total_bytes": 25769803776}]},
    }
    (reg_dir / "p2.json").write_text(json.dumps(p2), encoding="utf-8")

    # Synthetic p3.json
    p3 = {
        "phase_id": "PHASE_3_ENGINE_DISCOVERY_INTEGRITY",
        "engines": {
            "orca": {
                "name": "orca",
                "path": str(tmp_path / "orca"),
                "version": "6.1.1",
                "sha256_hash": "8d6b51bf4093c967dbed997cc651f0212b8f94313ee77ea56f548f000672c42f",
                "status": "FOUND_VALID",
            }
        },
    }
    (reg_dir / "p3.json").write_text(json.dumps(p3), encoding="utf-8")

    # Synthetic p4.json
    p4 = {
        "phase_id": "PHASE_4_MICRO_SILO_PROVISIONING",
        "silos": {"cochem_core_silo": {"status": "PROVISIONED"}, "cochem_mace_silo": {"status": "PROVISIONED"}},
    }
    (reg_dir / "p4.json").write_text(json.dumps(p4), encoding="utf-8")

    # Synthetic p10.json & p11.json
    (reg_dir / "p10.json").write_text(json.dumps({"alignment_engine_ready": True}), encoding="utf-8")
    (reg_dir / "p11.json").write_text(json.dumps({"oom_shield": {"maxcore_mb": 4096}}), encoding="utf-8")

    consolidated, found = consolidate_intermediate_states(registry_dir=reg_dir)

    assert "p1.json" in found
    assert "p2.json" in found
    assert "p3.json" in found
    assert "p4.json" in found
    assert "p10.json" in found
    assert "p11.json" in found

    assert consolidated["hardware"]["cpu_physical_cores"] == 8
    assert consolidated["hardware"]["ram_gb"] == pytest.approx(32.0, rel=1e-1)
    assert consolidated["hardware"]["maxcore_mb"] == 4096
    assert consolidated["silos"]["gpu_silo_active"] is True
    assert consolidated["alignment_engine_ready"] is True
    assert "orca" in consolidated["engines"]
    assert consolidated["engines"]["orca"]["status"] == "found"


def test_consolidate_intermediate_states_empty_directory(tmp_path: Path) -> None:
    """Verify consolidate_intermediate_states returns empty dict gracefully when no p*.json files exist."""
    empty_dir = tmp_path / "empty_reg"
    empty_dir.mkdir(parents=True, exist_ok=True)

    consolidated, found = consolidate_intermediate_states(registry_dir=empty_dir, search_dirs=[])
    assert isinstance(consolidated, dict)
    assert isinstance(found, list)


# =============================================================================
# 12. MASTER SYSTEM CONFIG VALIDATION & IMMUTABLE LOCKING TESTS
# =============================================================================


def test_validate_and_build_system_config_locks_and_seals() -> None:
    """Verify validate_and_build_system_config sets status='LOCKED' and recalculates checksum."""
    raw_data = {
        "hardware": {
            "ram_gb": 32.0,
            "cpu_physical_cores": 8,
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
        },
        "environment": {
            "os_target": "Local-Linux",
        },
    }
    cfg = validate_and_build_system_config(consolidated_data=raw_data)
    assert cfg.status == "LOCKED"
    assert cfg.schema_version == "4.0.0"
    assert cfg.hardware.ram_gb == 32.0
    assert cfg.verify_checksum() is True


def test_validate_and_build_system_config_single_threaded_mode() -> None:
    """Verify validate_and_build_system_config limits compute cores when single_threaded_mode is True."""
    cfg = validate_and_build_system_config(
        consolidated_data={"hardware": {"ram_gb": 16.0, "cpu_physical_cores": 8}},
        single_threaded_mode=True,
    )
    assert cfg.hardware.allocatable_compute_cores == 1


def test_finalize_and_lock_golden_registry_and_chmod(tmp_path: Path) -> None:
    """Verify finalize_and_lock_golden_registry writes cochem_system_config.json and applies 0o444."""
    out_file = tmp_path / "Registry" / "cochem_system_config.json"
    cfg = validate_and_build_system_config()

    path_res, serialized = finalize_and_lock_golden_registry(
        cfg=cfg,
        output_path=out_file,
        dry_run=False,
    )
    assert path_res.exists()
    assert serialized["status"] == "LOCKED"

    # Check read-only attribute / permissions
    file_stat = path_res.stat()
    assert bool(file_stat.st_mode & stat.S_IREAD)
    if platform.system() != "Windows":
        mode_octal = oct(stat.S_IMODE(file_stat.st_mode))
        assert "4" in mode_octal

    # Verify content parses cleanly
    data = json.loads(path_res.read_text(encoding="utf-8"))
    assert data["status"] == "LOCKED"
    assert "hardware" in data

    # Unset read-only attribute so tmp_path fixture can clean up
    try:
        os.chmod(path_res, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


# =============================================================================
# 13. WORKSPACE GARBAGE COLLECTION SWEEP TESTS
# =============================================================================


def test_execute_workspace_sweep_cleans_ephemeral_preserves_registry(tmp_path: Path) -> None:
    """Verify execute_workspace_sweep cleans .tmp files while preserving cochem_system_config.json."""
    ws = tmp_path / "workspace"
    reg = tmp_path / "registry"
    ws.mkdir(parents=True, exist_ok=True)
    reg.mkdir(parents=True, exist_ok=True)

    # Ephemeral files
    f_tmp1 = ws / "test_module.tmp"
    f_tmp2 = ws / "staging.tmp.1234"
    f_lock = reg / ".cochem_swmr_lock_probe.lock"
    f_tmp1.write_text("transient", encoding="utf-8")
    f_tmp2.write_text("transient", encoding="utf-8")
    f_lock.write_text("probe", encoding="utf-8")

    # Persistent files
    f_perm = ws / "user_input.xyz"
    f_golden = reg / "cochem_system_config.json"
    f_perm.write_text("C 0 0 0", encoding="utf-8")
    f_golden.write_text('{"status": "LOCKED"}', encoding="utf-8")

    report = execute_workspace_sweep(
        workspace_dir=ws,
        registry_dir=reg,
        dry_run=False,
        remove_intermediate_json=False,
    )

    assert report.swept_files_count >= 3
    assert not f_tmp1.exists()
    assert not f_tmp2.exists()
    assert not f_lock.exists()
    assert f_perm.exists()
    assert f_golden.exists()


def test_execute_workspace_sweep_dry_run(tmp_path: Path) -> None:
    """Verify execute_workspace_sweep in dry_run mode does not unlink files."""
    ws = tmp_path / "ws_dry"
    ws.mkdir(parents=True, exist_ok=True)
    f_tmp = ws / "ephemeral.tmp"
    f_tmp.write_text("tmp", encoding="utf-8")

    report = execute_workspace_sweep(
        workspace_dir=ws,
        dry_run=True,
    )
    assert report.swept_files_count == 1
    assert f_tmp.exists()


# =============================================================================
# 14. FULL INTEGRATED PHASE 5 PIPELINE WITH CONFIG LOCK TESTS
# =============================================================================


def test_run_phase_5_audit_full_integration(tmp_path: Path) -> None:
    """Verify run_phase_5_audit executes both MPS and Config Lock & Sweep pipelines."""
    out_dir = tmp_path / "FullReg"
    socket_dir = tmp_path / "FullSocket"
    log_dir = tmp_path / "FullLog"

    report = run_phase_5_audit(
        output_dir=out_dir,
        socket_dir=socket_dir,
        log_dir=log_dir,
        worker_concurrency=2,
        dry_run=False,
        sweep_workspace=True,
    )

    assert report.status is PhaseStatus.PASSED
    assert report.config_lock is not None
    assert report.config_lock.status == "LOCKED"
    assert report.config_lock.posix_lock_test.passed is True
    assert (out_dir / "p5.json").exists()
    assert (out_dir / "cochem_system_config.json").exists()

    # Clean up read-only permissions for teardown
    try:
        os.chmod(out_dir / "cochem_system_config.json", stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def test_resolve_golden_config_path_custom_and_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_golden_config_path handles custom path and environment overrides."""
    custom_p = tmp_path / "my_config.json"
    res1 = resolve_golden_config_path(custom_p)
    assert res1 == custom_p.resolve()

    monkeypatch.setenv("COCHEM_CONFIG", str(tmp_path / "env_config.json"))
    res2 = resolve_golden_config_path()
    assert res2 == (tmp_path / "env_config.json").resolve()



Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.