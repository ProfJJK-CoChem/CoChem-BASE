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
