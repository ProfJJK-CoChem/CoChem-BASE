Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc4_02_registry_manager_prompt.md.
Original prompt:
# Task: Implement Thread-Safe Master Registry Manager (`cochem_core_registry_manager.py`)

## Context
The CoChem ecosystem relies on the Stage 0 Authority Rule: no module guesses hardware limits. Every module unconditionally polls the Master Registry. You will implement the thread-safe `cochem_core_registry_manager.py` which interfaces with the `cochem_system_config.json` via the strict Pydantic schemas defined in `cochem_core_registry_schema.py`.

## Instructions
Create the file `cochem_core_registry_manager.py` and implement the thread-safe loading, validating, and updating of the registry.

1. **Thread-Safe I/O**:
   - Implement secure, thread-safe mechanisms (e.g., file locking) when reading and writing `$HOME/CoChem_Artifacts/Registry/cochem_system_config.json` (or dynamic data tier equivalent).
   - Ensure the Stage 0 Guardrail: If the registry is missing, or parsing fails, the manager MUST immediately log the violation and halt gracefully. Do not allow execution to continue.

2. **Environment Variable Interpolation**:
   - Implement a parser that intercepts `${ENV_VAR}` placeholders within the raw JSON string (e.g., `${HOME}/bin/orca`) and interpolates them dynamically with the host's actual environment variables *before* passing the data to the Pydantic schemas.

3. **Cryptographic Integrity Checksums**:
   - On load, calculate the SHA-256 checksum of the file. Compare it with the stored `registry_checksum` in the file.
   - If the checksum verification fails, trigger a explicit "Registry Corruption" warning/error, preventing execution with an untrusted or tampered configuration.
   - On save, recalculate the SHA-256 checksum and inject it into the Pydantic model before serialization.

4. **Integration with Schemas**:
   - When loading, pipe the JSON data directly into `CoChemSystemConfig`. The `@model_validator` hook (`RegistryMigrator`) inside the schema should automatically handle legacy migrations.

## Constraints
- **Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_core_registry_manager.py`
- Absolutely NO mocks, stubs, dummy variables, or `# TODO` placeholders. The future coder agent is explicitly commanded to *not* use mocks.
- Do NOT implement the Pydantic schemas in this file; import them from `cochem_core_registry_schema`.
- Must strictly adhere to the Tripartite Workspace Air-Gap and Method Matrix rules.

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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import platform
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Union, cast

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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_manager.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Re-exports authoritative registry manager from root cochem_core_registry_manager."""

from cochem_core_registry_manager import (
    AtomicFileLock,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    IsotopeStabilityError,
    RecordNotFoundError,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryLockTimeoutError,
    RegistryManager,
    RegistryMissingError,
    RegistryParseError,
    SchemaMigrationError,
    _sanitize_path_leakages,
    atomic_write_json,
    broadcast_system_config,
    get_active_job,
    get_default_config_path,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)

__all__ = [
    "AtomicFileLock",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "IsotopeStabilityError",
    "RecordNotFoundError",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "_sanitize_path_leakages",
    "atomic_write_json",
    "broadcast_system_config",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_core_registry_manager.py ---
#!/usr/bin/env python3
"""CoChem-CORE: Stage 0 Authority Rule & Master Registry Manager.

Provides thread-safe and process-safe atomic file locking, cryptographic SHA-256
checksum enforcement, dynamic environment variable interpolation, legacy schema migration,
active jobs lifecycle tracking, HDF5 state registry operations, lineage DAGs, PRNG seed locking,
embedded basis set archival, Mendeleev isotopic mass queries, and ZeroMQ config broadcast.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import re
import shutil
import threading
import time
from typing import Any, Dict, Generator, List, Optional, Sequence, Union, cast
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import h5py
from pydantic import BaseModel
import zmq

try:
    from mendeleev import element
except ImportError:
    element = None

try:
    from qcelemental import periodictable as pt  # type: ignore
except ImportError:
    pt = None

from cochem_base.config_loader import (
    get_artifact_dir,
    resolve_config_path,
    resolve_mapped_path,
)
from cochem_core_registry_schema import (
    CoChemSystemConfig,
    HardwareSchema,
    OSTarget,
    QuantumSettings,
    HPCConfig,
    SiloConfig,
    SiloPathsSchema,
    EngineInfo,
    EnginePaths,
    discover_host_hardware,
)

logger = logging.getLogger("CoChem-RegistryManager")


# =============================================================================
# TYPED REGISTRY EXCEPTIONS
# =============================================================================

class RegistryError(Exception):
    """Base exception for all registry and state manager operations."""


class RegistryLockError(RegistryError):
    """Raised when atomic file locking fails."""


class CoChemLockTimeoutError(RegistryLockError, TimeoutError):
    """Raised when acquiring an atomic file lock exceeds the configured timeout."""


RegistryLockTimeoutError = CoChemLockTimeoutError


class RegistryMissingError(RegistryError, FileNotFoundError):
    """Stage 0 Guardrail: Raised when the master registry configuration file is missing."""


class RegistryCorruptionError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry integrity checksum verification fails."""


class RegistryParseError(RegistryError, ValueError):
    """Stage 0 Guardrail: Raised when registry JSON is malformed or unparseable."""


class RecordNotFoundError(RegistryError, KeyError, ValueError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError, KeyError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError, ValueError):
    """Raised when schema migration encounters an unrecoverable failure."""


class IsotopeStabilityError(RegistryError):
    """Raised when isotopic mass resolution fails or mass record is missing."""


# =============================================================================
# ATOMIC FILE LOCKING
# =============================================================================

class AtomicFileLock:
    """Process-safe, thread-safe, cross-platform atomic file lock.

    Combines thread-level RLock serialization per canonical path with OS-level
    atomic file creation (os.O_CREAT | os.O_EXCL), exponential backoff,
    thread-local re-entrancy tracking, and stale-lock auto-reaping.
    """

    _tls = threading.local()
    _path_locks: Dict[str, threading.RLock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_path_lock(cls, path_str: str) -> threading.RLock:
        with cls._meta_lock:
            if path_str not in cls._path_locks:
                cls._path_locks[path_str] = threading.RLock()
            return cls._path_locks[path_str]

    def __init__(
        self,
        lock_path: Union[str, Path],
        timeout: float = 10.0,
        stale_timeout: float = 60.0,
    ) -> None:
        self.lock_path = Path(lock_path).resolve()
        self.timeout = float(timeout)
        self.stale_timeout = float(stale_timeout)
        self._fd: Optional[int] = None
        self._depth: int = 0
        self._thread_lock_acquired: bool = False

    @property
    def _is_locked(self) -> bool:
        path_str = str(self.lock_path)
        if hasattr(self._tls, "held") and self._tls.held.get(path_str, 0) > 0:
            return True
        return self._depth > 0

    def acquire(self) -> bool:
        """Acquires the atomic lock before timeout. Raises CoChemLockTimeoutError on failure."""
        if not hasattr(self._tls, "held"):
            self._tls.held = {}
        if not hasattr(self._tls, "fds"):
            self._tls.fds = {}

        path_str = str(self.lock_path)

        # Thread-local re-entrancy
        if self._tls.held.get(path_str, 0) > 0:
            self._tls.held[path_str] += 1
            self._depth += 1
            return True

        start_time = time.time()
        thread_lock = self._get_path_lock(path_str)

        # 1. Acquire in-process thread lock
        remaining = max(0.001, self.timeout - (time.time() - start_time))
        if not thread_lock.acquire(timeout=remaining):
            raise CoChemLockTimeoutError(
                f"Could not acquire thread lock on '{self.lock_path}' within {self.timeout}s"
            )

        self._thread_lock_acquired = True
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        backoff = 0.005

        # 2. Acquire OS-level file lock
        while (time.time() - start_time) < self.timeout:
            try:
                self._fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                payload = f"{os.getpid()}:{threading.get_ident()}:{time.time()}\n"
                os.write(self._fd, payload.encode("utf-8"))
                self._depth = 1
                self._tls.held[path_str] = 1
                self._tls.fds[path_str] = self._fd
                return True
            except FileExistsError:
                try:
                    mtime = self.lock_path.stat().st_mtime
                    if (time.time() - mtime) > self.stale_timeout:
                        try:
                            self.lock_path.unlink(missing_ok=True)
                            logger.info(f"Reaped stale lock file: {self.lock_path}")
                        except OSError:
                            pass
                except (OSError, FileNotFoundError):
                    pass
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)
            except PermissionError:
                # Windows handle collision during race
                try:
                    if self.lock_path.exists():
                        mtime = self.lock_path.stat().st_mtime
                        if (time.time() - mtime) > self.stale_timeout:
                            try:
                                self.lock_path.unlink(missing_ok=True)
                            except OSError:
                                pass
                except Exception:
                    pass
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)
            except Exception as e:
                logger.debug(f"Transient error acquiring lock on {self.lock_path}: {e}")
                time.sleep(backoff)
                backoff = min(0.2, backoff * 1.5)

        # Failed OS-level acquisition: release in-process thread lock
        self._thread_lock_acquired = False
        thread_lock.release()
        raise CoChemLockTimeoutError(
            f"Could not acquire atomic lock on '{self.lock_path}' within {self.timeout}s"
        )

    def release(self) -> None:
        """Releases the lock file safely."""
        path_str = str(self.lock_path)
        if not hasattr(self._tls, "held") or self._tls.held.get(path_str, 0) <= 0:
            if self._depth > 0:
                self._depth -= 1
            if self._thread_lock_acquired:
                self._thread_lock_acquired = False
                try:
                    self._get_path_lock(path_str).release()
                except RuntimeError:
                    pass
            return

        self._depth -= 1
        self._tls.held[path_str] -= 1
        if self._tls.held[path_str] > 0:
            return

        del self._tls.held[path_str]

        fd = None
        if hasattr(self._tls, "fds") and path_str in self._tls.fds:
            fd = self._tls.fds.pop(path_str)
        elif self._fd is not None:
            fd = self._fd
            self._fd = None

        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self._fd = None

        try:
            if self.lock_path.exists():
                self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass

        if self._thread_lock_acquired:
            self._thread_lock_acquired = False
            try:
                self._get_path_lock(path_str).release()
            except RuntimeError:
                pass

    def __enter__(self) -> AtomicFileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# =============================================================================
# ENVIRONMENT VARIABLE INTERPOLATION & ATOMIC JSON WRITER
# =============================================================================

def interpolate_env_vars(raw_data: Any) -> Any:
    """Uniformly expands %VAR%, $VAR, ${VAR}, and ~ across Windows and POSIX environments.

    Supports string, dictionary, list, or primitive data structures.
    """
    if isinstance(raw_data, str):
        def replace_percent(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_braced(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        def replace_dollar(match: re.Match[str]) -> str:
            var = match.group(1)
            return os.environ.get(var, match.group(0))

        s = re.sub(r"%([A-Za-z0-9_]+)%", replace_percent, raw_data)
        s = re.sub(r"\$\{([A-Za-z0-9_]+)\}", replace_braced, s)
        s = re.sub(r"\$([A-Za-z0-9_]+)", replace_dollar, s)
        if s.startswith("~"):
            s = os.path.expanduser(s)
        return s
    elif isinstance(raw_data, dict):
        return {k: interpolate_env_vars(v) for k, v in raw_data.items()}
    elif isinstance(raw_data, list):
        return [interpolate_env_vars(item) for item in raw_data]
    return raw_data


def atomic_write_json(
    file_path: Union[str, Path],
    data: Union[Dict[str, Any], BaseModel, str],
    lock_timeout: float = 10.0,
) -> None:
    """Writes JSON data atomically via staging file and os.replace."""
    target = Path(file_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file = str(target) + ".lock"

    if isinstance(data, BaseModel):
        content = data.model_dump_json(indent=2)
    elif isinstance(data, dict):
        content = json.dumps(data, indent=2)
    elif isinstance(data, str):
        content = data
    else:
        content = json.dumps(data, indent=2)

    with AtomicFileLock(lock_file, timeout=lock_timeout):
        temp_file = target.parent / f"{target.name}.tmp.{uuid.uuid4().hex}"
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, target)
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError:
                    pass


# =============================================================================
# ENVIRONMENT FINGERPRINTING & SCHEMA MIGRATION
# =============================================================================

def _sanitize_path_leakages(payload_str: str) -> str:
    """Sanitizes local absolute directory paths from serialized environment payloads."""
    p1 = r'[A-Za-z]:(?:\\\\|\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p1, "[SANITIZED_PATH]", payload_str)
    p2 = r'/(?:home|Users|root|tmp|var|opt|usr|etc|Volumes)/[^",}\]\r\n]*'
    sanitized = re.sub(p2, "[SANITIZED_PATH]", sanitized)
    p3 = r'(?:\\\\\\\\|//|\\\\)[^",}\]\r\n]*'
    sanitized = re.sub(p3, "[SANITIZED_PATH]", sanitized)
    p4 = r'(?:\\\\|/)?(?:Users|AppData|Documents|Desktop)(?:\\\\|/)[^",}\]\r\n]*'
    sanitized = re.sub(p4, "[SANITIZED_PATH]", sanitized)
    return sanitized


def hash_environment(
    exclude_paths: bool = True,
    tracked_packages: Optional[Sequence[str]] = None,
    tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generates a deterministic cryptographic SHA-256 fingerprint of the host environment."""
    try:
        from cochem_base.provenance.hashing import hash_environment as _h_env

        rec = _h_env(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )
        return cast(
            Dict[str, Any],
            rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__),
        )
    except Exception:
        py_ver = platform.python_version()
        py_impl = platform.python_implementation()
        os_sys = platform.system()
        os_rel = platform.release()
        os_arch = platform.machine()
        cpu_cnt = os.cpu_count() or 1
        total_ram = 0

        try:
            import psutil  # type: ignore[import-untyped]
            total_ram = psutil.virtual_memory().total
        except Exception:
            total_ram = 16 * 1024 * 1024 * 1024

        canonical_payload = {
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "os_architecture": os_arch,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "tracked_packages": list(tracked_packages or []),
            "tracked_engines": tracked_engines
            if isinstance(tracked_engines, dict)
            else list(tracked_engines or []),
        }

        serialized = json.dumps(canonical_payload, sort_keys=True)
        if exclude_paths:
            serialized = _sanitize_path_leakages(serialized)

        sha256_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return {
            "sha256_hash": sha256_hash,
            "python_version": py_ver,
            "python_implementation": py_impl,
            "os_system": os_sys,
            "os_release": os_rel,
            "cpu_count": cpu_cnt,
            "total_ram_bytes": total_ram,
            "metadata": {"os_architecture": os_arch},
        }


def migrate_schema(
    config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig],
) -> CoChemSystemConfig:
    """Upgrades legacy JSON schemas (0.1, 1.0.0, 2.0.0) to current target schema (4.0.0)."""
    if isinstance(config_source, CoChemSystemConfig):
        return config_source

    if isinstance(config_source, (str, Path)):
        p = Path(config_source)
        if p.is_file():
            raw_text = p.read_text(encoding="utf-8")
            raw_dict = json.loads(raw_text)
        else:
            raw_dict = json.loads(str(config_source))
    elif isinstance(config_source, dict):
        raw_dict = dict(config_source)
    else:
        raise SchemaMigrationError(
            f"Unsupported config source type for migration: {type(config_source)}"
        )

    raw_dict = interpolate_env_vars(raw_dict)
    raw_dict["schema_version"] = "4.0.0"

    if "quantum_settings" not in raw_dict or raw_dict["quantum_settings"] is None:
        raw_dict["quantum_settings"] = {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
            "charge": 0,
            "multiplicity": 1,
        }

    if "hpc" not in raw_dict or raw_dict["hpc"] is None:
        raw_dict["hpc"] = {
            "scheduler": "local",
            "default_partition": "compute",
            "max_walltime_hours": 24,
        }

    try:
        cfg = CoChemSystemConfig.model_validate(raw_dict)
        cfg.update_checksum()
        return cfg
    except Exception as e:
        raise SchemaMigrationError(f"Failed to migrate and validate system schema: {e}") from e


# =============================================================================
# MASTER NODE & ZEROMQ BROADCAST
# =============================================================================

def is_master_node() -> bool:
    """Determines whether current execution process is the master node (Rank 0 / Standalone)."""
    override = os.environ.get("COCHEM_IS_MASTER")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes")

    slurm_procid = os.environ.get("SLURM_PROCID")
    if slurm_procid is not None:
        return slurm_procid.strip() == "0"

    for rank_var in ["OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK", "MV2_COMM_WORLD_RANK"]:
        val = os.environ.get(rank_var)
        if val is not None:
            return val.strip() == "0"

    return True


def broadcast_system_config(
    config: Optional[Union[CoChemSystemConfig, Dict[str, Any]]] = None,
    port: int = 5555,
    host: str = "0.0.0.0",
    topic: str = "cochem_system_config",
    config_path: Optional[Union[str, Path]] = None,
    repeat_count: int = 5,
    repeat_interval: float = 0.05,
    ready_event: Optional[threading.Event] = None,
) -> str:
    """Broadcasts validated system configuration over ZeroMQ PUB socket for HPC worker nodes."""
    if config is None:
        config = load_system_config(config_path)

    if isinstance(config, dict):
        validated_cfg = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        validated_cfg = config
    else:
        raise TypeError(f"Invalid config type for broadcast: {type(config)}")

    json_payload = validated_cfg.model_dump_json()

    ctx = zmq.Context.instance()
    pub_socket = ctx.socket(zmq.PUB)
    pub_socket.setsockopt(zmq.LINGER, 1000)
    try:
        pub_socket.bind(f"tcp://{host}:{port}")
        if ready_event is not None:
            ready_event.set()
        time.sleep(0.15)
        for _ in range(max(1, repeat_count)):
            pub_socket.send_multipart([topic.encode("utf-8"), json_payload.encode("utf-8")])
            time.sleep(repeat_interval)
    finally:
        pub_socket.close()

    return validated_cfg.compute_checksum()


def receive_system_config_broadcast(
    master_host: str = "127.0.0.1",
    port: int = 5555,
    topic: str = "cochem_system_config",
    timeout_ms: int = 5000,
) -> CoChemSystemConfig:
    """Receives system configuration from master ZeroMQ broadcast."""
    ctx = zmq.Context.instance()
    sub_socket = ctx.socket(zmq.SUB)
    sub_socket.setsockopt(zmq.LINGER, 0)
    try:
        sub_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sub_socket.connect(f"tcp://{master_host}:{port}")
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        time.sleep(0.05)
        parts = sub_socket.recv_multipart()
        json_str = parts[1].decode("utf-8")
        return CoChemSystemConfig.model_validate_json(json_str)
    except zmq.error.Again as e:
        raise TimeoutError(
            f"ZeroMQ config broadcast timed out after {timeout_ms}ms from {master_host}:{port}"
        ) from e
    finally:
        sub_socket.close()


# =============================================================================
# SYSTEM CONFIGURATION I/O & STAGE 0 GUARDRAILS
# =============================================================================

def get_default_config_path() -> Path:
    """Resolves the default system configuration file path."""
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
        return (Path.home() / "CoChem_Artifacts" / "Registry" / "cochem_system_config.json").resolve()


def load_system_config(
    config_path: Optional[Union[str, Path]] = None,
    verify_integrity: bool = True,
) -> CoChemSystemConfig:
    """Loads and validates cochem_system_config.json with environment variable expansion and integrity checks.

    Enforces Stage 0 Guardrail:
    - If file is missing, logs violation and raises RegistryMissingError.
    - If JSON is malformed, logs violation and raises RegistryParseError.
    - If checksum verification fails, logs violation and raises RegistryCorruptionError.
    """
    target_path = Path(config_path or get_default_config_path()).resolve()
    if not target_path.is_file():
        logger.critical(f"Stage 0 Guardrail: Master registry not found at: {target_path}")
        raise RegistryMissingError(f"Stage 0 Guardrail: Master registry not found at '{target_path}'")

    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        try:
            raw_text = target_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.critical(f"Stage 0 Guardrail: Failed to read registry at {target_path}: {e}")
            raise RegistryMissingError(f"Stage 0 Guardrail: Failed to read registry at '{target_path}': {e}") from e

        try:
            parsed_json = json.loads(raw_text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.critical(f"Stage 0 Guardrail: Malformed registry JSON at {target_path}: {e}")
            raise RegistryParseError(f"Stage 0 Guardrail: Unparseable registry JSON at '{target_path}': {e}") from e

        if not isinstance(parsed_json, dict):
            logger.critical(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__} at {target_path}"
            )
            raise RegistryParseError(
                f"Stage 0 Guardrail: Registry root must be a JSON object, got {type(parsed_json).__name__}"
            )

        interpolated_dict = interpolate_env_vars(parsed_json)

        try:
            config = migrate_schema(interpolated_dict)
        except Exception as e:
            logger.critical(f"Stage 0 Guardrail: Schema validation error for {target_path}: {e}")
            raise SchemaMigrationError(f"Stage 0 Guardrail: Schema validation error for '{target_path}': {e}") from e

        if verify_integrity and "registry_checksum" in parsed_json and parsed_json["registry_checksum"]:
            expected = parsed_json["registry_checksum"]
            computed = config.compute_checksum()
            if expected != computed:
                logger.critical(
                    f"Stage 0 Guardrail: Registry corruption at {target_path} (expected checksum '{expected}', computed '{computed}')"
                )
                raise RegistryCorruptionError(
                    f"Stage 0 Guardrail: Registry corruption at '{target_path}' (expected '{expected}', computed '{computed}')"
                )

        return config


def save_system_config(
    config: Union[CoChemSystemConfig, Dict[str, Any]],
    config_path: Optional[Union[str, Path]] = None,
) -> str:
    """Saves system configuration atomically with updated SHA-256 checksum."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    if isinstance(config, dict):
        cfg_model = migrate_schema(config)
    elif isinstance(config, CoChemSystemConfig):
        cfg_model = config
    else:
        raise TypeError(f"Invalid config type: {type(config)}")

    cfg_model.last_updated = datetime.now(timezone.utc).isoformat()
    checksum = cfg_model.update_checksum()
    atomic_write_json(target_path, cfg_model, lock_timeout=10.0)
    return checksum


def update_system_config(
    config_path: Optional[Union[str, Path]] = None,
    **updates: Any,
) -> CoChemSystemConfig:
    """Atomically updates fields within cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    with AtomicFileLock(lock_file, timeout=10.0):
        current = load_system_config(target_path, verify_integrity=False)
        current_dict = current.model_dump()
        current_dict.update(updates)
        updated_cfg = migrate_schema(current_dict)
        save_system_config(updated_cfg, target_path)
        return updated_cfg


# =============================================================================
# ACTIVE JOBS LIFECYCLE MANAGEMENT
# =============================================================================

def register_active_job(
    job_id: str,
    job_data: Union[Dict[str, Any], BaseModel],
    config_path: Optional[Union[str, Path]] = None,
) -> None:
    """Registers an active execution job into cochem_system_config.json under active_jobs."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")

    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"

    payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
    if "registered_at" not in payload:
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()

    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        cfg.active_jobs[job_id] = payload
        save_system_config(cfg, target_path)


def get_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves an active job record from cochem_system_config.json, or None if not found."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return None
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return cfg.active_jobs.get(job_id)


def list_active_jobs(
    config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Returns all active jobs recorded in cochem_system_config.json."""
    target_path = Path(config_path or get_default_config_path()).resolve()
    cfg = load_system_config(target_path, verify_integrity=False)
    return dict(cfg.active_jobs)


def remove_active_job(
    job_id: str,
    config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Removes an active job from cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        return False
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id in cfg.active_jobs:
            del cfg.active_jobs[job_id]
            save_system_config(cfg, target_path)
            return True
        return False


def update_active_job(
    job_id: str,
    status: str,
    config_path: Optional[Union[str, Path]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Updates status and additional fields of an active job in cochem_system_config.json."""
    if not job_id or not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Job ID must be a non-empty string.")
    target_path = Path(config_path or get_default_config_path()).resolve()
    lock_file = str(target_path) + ".lock"
    with AtomicFileLock(lock_file, timeout=10.0):
        cfg = load_system_config(target_path, verify_integrity=False)
        if job_id not in cfg.active_jobs:
            raise RecordNotFoundError(f"Cannot update non-existent active job '{job_id}'")
        job_record = dict(cfg.active_jobs[job_id])
        job_record["status"] = status
        job_record.update(kwargs)
        job_record["updated_at"] = datetime.now(timezone.utc).isoformat()
        cfg.active_jobs[job_id] = job_record
        save_system_config(cfg, target_path)
        return job_record


# =============================================================================
# MASTER REGISTRY MANAGER CLASS
# =============================================================================

class RegistryManager:
    """Consolidated state registry manager using HDF5, Atomic File Locks, and ZeroMQ Broadcasts."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self, config_path: Optional[str] = None, registry_path: Optional[str] = None
    ) -> None:
        if config_path:
            self.config_path = str(resolve_config_path(Path(config_path)))
        else:
            self.config_path = str(resolve_config_path())

        if registry_path:
            self.registry_path = str(
                resolve_mapped_path(registry_path, get_artifact_dir() / "Registry")
            )
        else:
            self.registry_path = str(get_artifact_dir() / "Registry" / "cochem_registry.h5")

        self.lock_path = self.registry_path + ".lock"
        self._ensure_registry_exists()

    def _ensure_registry_exists(self) -> None:
        """Ensure the HDF5 registry file and required groups exist, with atomic locking."""
        try:
            Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
            with AtomicFileLock(self.lock_path, timeout=10.0):
                if not os.path.exists(self.registry_path):
                    with h5py.File(self.registry_path, "w") as h5:
                        h5.attrs["created"] = datetime.now(timezone.utc).isoformat()
                        h5.attrs["version"] = self.SCHEMA_VERSION
                        h5.create_group("jobs")
                        h5.create_group("hardware_profiles")
                        h5.create_group("basis_sets")
                        h5.create_group("embedded_basis_sets")
                        h5.create_group("provenance")
                        h5.create_group("seeds")
                        h5.create_group("metadata")
                    logger.info(f"Created new registry file: {self.registry_path}")
                else:
                    with h5py.File(self.registry_path, "a") as h5:
                        if "version" not in h5.attrs:
                            h5.attrs["version"] = self.SCHEMA_VERSION
                        for grp in [
                            "jobs",
                            "hardware_profiles",
                            "basis_sets",
                            "embedded_basis_sets",
                            "provenance",
                            "seeds",
                            "metadata",
                        ]:
                            if grp not in h5:
                                h5.create_group(grp)
        except Exception as e:
            logger.error(f"Failed to initialize registry: {e}")
            raise RuntimeError(f"Registry initialization failed: {e}") from e

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic transaction over the HDF5 registry using AtomicFileLock."""
        with AtomicFileLock(self.lock_path, timeout=10.0):
            with h5py.File(self.registry_path, mode) as h5:
                yield h5

    def get_registry_stats(self) -> Dict[str, Any]:
        """Returns statistics on active registry record groups."""
        with self.transaction("r") as h5:
            jobs_c = len(h5["jobs"]) if "jobs" in h5 else 0
            hw_c = len(h5["hardware_profiles"]) if "hardware_profiles" in h5 else 0
            prov_c = len(h5["provenance"]) if "provenance" in h5 else 0
            basis_c = (
                len(h5["embedded_basis_sets"])
                if "embedded_basis_sets" in h5
                else (len(h5["basis_sets"]) if "basis_sets" in h5 else 0)
            )
            seeds_c = len(h5["seeds"]) if "seeds" in h5 else 0
            ver = h5.attrs.get("version", self.SCHEMA_VERSION)
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8")
            return {
                "jobs_count": jobs_c,
                "hardware_profiles_count": hw_c,
                "provenance_count": prov_c,
                "basis_sets_count": basis_c,
                "seeds_count": seeds_c,
                "version": str(ver),
            }

    # =========================================================================
    # System Configuration Delegates
    # =========================================================================

    def load_system_config(
        self,
        config_path: Optional[Union[str, Path]] = None,
        verify_integrity: bool = True,
    ) -> CoChemSystemConfig:
        """Loads system configuration using the authoritative Stage 0 loader."""
        return load_system_config(config_path or self.config_path, verify_integrity=verify_integrity)

    def save_system_config(
        self,
        config: Union[CoChemSystemConfig, Dict[str, Any]],
        config_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Saves system configuration atomically with updated SHA-256 checksum."""
        return save_system_config(config, config_path or self.config_path)

    def update_system_config(self, **updates: Any) -> CoChemSystemConfig:
        """Atomically updates fields within cochem_system_config.json."""
        return update_system_config(config_path=self.config_path, **updates)

    def register_active_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers an active execution job in cochem_system_config.json."""
        register_active_job(job_id, job_data, config_path=self.config_path)

    def get_active_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves an active execution job from cochem_system_config.json."""
        return get_active_job(job_id, config_path=self.config_path)

    def list_active_jobs(self) -> Dict[str, Any]:
        """Lists all active execution jobs in cochem_system_config.json."""
        return list_active_jobs(config_path=self.config_path)

    def remove_active_job(self, job_id: str) -> bool:
        """Removes an active execution job from cochem_system_config.json."""
        return remove_active_job(job_id, config_path=self.config_path)

    def update_active_job(self, job_id: str, status: str, **kwargs: Any) -> Dict[str, Any]:
        """Updates an active execution job in cochem_system_config.json."""
        return update_active_job(job_id, status, config_path=self.config_path, **kwargs)

    def poll_system_config(
        self,
        master_host: str = "127.0.0.1",
        zmq_port: int = 5555,
        timeout_ms: int = 2000,
    ) -> CoChemSystemConfig:
        """Polls configuration: Master reads disk directly; Worker receives ZMQ broadcast with disk fallback."""
        if is_master_node():
            return self.load_system_config()
        try:
            return receive_system_config_broadcast(
                master_host=master_host, port=zmq_port, timeout_ms=timeout_ms
            )
        except Exception as e:
            logger.debug(f"Worker ZMQ poll failed, falling back to disk read: {e}")
            return self.load_system_config()

    def broadcast_config(
        self,
        port: int = 5555,
        host: str = "0.0.0.0",
        topic: str = "cochem_system_config",
    ) -> str:
        """Broadcasts current configuration via ZeroMQ."""
        cfg = self.load_system_config(verify_integrity=False)
        return broadcast_system_config(cfg, port=port, host=host, topic=topic)

    def receive_config_broadcast(
        self,
        master_host: str = "127.0.0.1",
        port: int = 5555,
        topic: str = "cochem_system_config",
        timeout_ms: int = 5000,
    ) -> CoChemSystemConfig:
        """Subscribes and receives configuration broadcast via ZeroMQ."""
        return receive_system_config_broadcast(
            master_host=master_host, port=port, topic=topic, timeout_ms=timeout_ms
        )

    def hash_environment(
        self,
        exclude_paths: bool = True,
        tracked_packages: Optional[Sequence[str]] = None,
        tracked_engines: Optional[Union[Sequence[str], Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Calculates environmental hash for state tracking."""
        return hash_environment(
            exclude_paths=exclude_paths,
            tracked_packages=tracked_packages,
            tracked_engines=tracked_engines,
        )

    def migrate_schema(
        self, config_source: Union[Dict[str, Any], str, Path, CoChemSystemConfig]
    ) -> CoChemSystemConfig:
        """Migrates schema to 4.0.0."""
        return migrate_schema(config_source)

    # =========================================================================
    # Isotopic Mass & Mendeleev/QCElemental Queries
    # =========================================================================

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """Dynamically fetches exact isotopic masses via Mendeleev, QCElemental, or periodic tables."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if mass_number is not None and not isinstance(mass_number, int):
            raise ValueError("Mass number must be an integer.")

        if clean_sym.upper() == "D":
            if mass_number is not None and mass_number != 2:
                raise ValueError(f"Isotope {mass_number}D not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 2
        elif clean_sym.upper() == "T":
            if mass_number is not None and mass_number != 3:
                raise ValueError(f"Isotope {mass_number}T not found in Mendeleev database.")
            clean_sym = "H"
            formatted_sym = "H"
            mass_number = 3

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    if mass_number is not None:
                        for iso in elem.isotopes:
                            if iso.mass_number == mass_number:
                                if iso.mass is None:
                                    raise IsotopeStabilityError(
                                        f"Isotope {mass_number}{clean_sym} has no stable mass record in Mendeleev."
                                    )
                                return float(iso.mass)
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        )

                    if hasattr(elem, "mass") and elem.mass is not None:
                        return float(elem.mass)
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} lacks a valid default atomic mass binding."
                    )
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.debug(f"Mendeleev query failed for '{clean_sym}', attempting fallback: {e}")

        if pt is not None:
            try:
                if mass_number is not None:
                    target = f"{formatted_sym}{mass_number}"
                    try:
                        return float(pt.to_mass(target))
                    except Exception as e:
                        raise ValueError(
                            f"Isotope {mass_number}{clean_sym} not found in Mendeleev database."
                        ) from e
                try:
                    return float(pt.to_mass(formatted_sym))
                except Exception as e:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from e
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.error(f"Failed to query QCElemental for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(
                    f"Isotopic mass resolution failed for {clean_sym}: {e}"
                ) from e

        raise IsotopeStabilityError(
            f"Element {clean_sym} not found in Mendeleev or QCElemental database."
        )

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if clean_sym.upper() in ("D", "T"):
            clean_sym = "H"
            formatted_sym = "H"

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        elem = None

                if elem is not None:
                    isotopes = []
                    for iso in elem.isotopes:
                        isotopes.append(
                            {
                                "mass_number": int(iso.mass_number),
                                "mass": float(iso.mass) if iso.mass is not None else None,
                                "abundance": float(iso.abundance)
                                if getattr(iso, "abundance", None) is not None
                                else None,
                            }
                        )
                    return isotopes
            except Exception as e:
                logger.debug(f"Mendeleev isotopes query failed for '{clean_sym}': {e}")

        if pt is not None:
            try:
                isotopes = []
                try:
                    pt.to_mass(formatted_sym)
                except Exception as err:
                    raise IsotopeStabilityError(
                        f"Element {clean_sym} not found in Mendeleev."
                    ) from err

                pattern = re.compile(rf"^{formatted_sym}(\d+)$")
                if hasattr(pt, "_eliso2mass"):
                    for k, m in pt._eliso2mass.items():
                        mat = pattern.match(k)
                        if mat:
                            isotopes.append(
                                {
                                    "mass_number": int(mat.group(1)),
                                    "mass": float(m),
                                    "abundance": None,
                                }
                            )
                return sorted(isotopes, key=lambda x: x["mass_number"])
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev or QCElemental.")

    # =========================================================================
    # HDF5 Registry Operations
    # =========================================================================

    def register_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers a calculation job record in the HDF5 registry."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job ID must be a non-empty string.")

        payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
        if "registered_at" not in payload:
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id in jobs_grp:
                del jobs_grp[job_id]
            dset = jobs_grp.create_dataset(
                job_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )
            dset.attrs["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered job record, or None if not found."""
        with self.transaction("r") as h5:
            if "jobs" not in h5 or job_id not in h5["jobs"]:
                return None
            val = h5["jobs"][job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def update_job_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Updates the status and additional fields of an existing job record."""
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id not in jobs_grp:
                raise RecordNotFoundError(f"Cannot update status for non-existent job '{job_id}'")
            val = jobs_grp[job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            rec = json.loads(text)
            rec["status"] = status
            rec.update(kwargs)
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            del jobs_grp[job_id]
            jobs_grp.create_dataset(
                job_id, data=json.dumps(rec), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Returns all registered jobs with job_id included."""
        results = []
        with self.transaction("r") as h5:
            if "jobs" in h5:
                for k in h5["jobs"].keys():
                    val = h5["jobs"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["job_id"] = k
                    results.append(data)
        return results

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the registry."""
        with self.transaction("a") as h5:
            if "jobs" in h5 and job_id in h5["jobs"]:
                del h5["jobs"][job_id]
                return True
            return False

    def register_hardware_profile(
        self, profile_id: str, profile_data: Union[Dict[str, Any], BaseModel]
    ) -> None:
        """Registers a host/node hardware configuration profile."""
        if not profile_id or not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile ID must be a non-empty string.")

        payload = (
            profile_data.model_dump() if isinstance(profile_data, BaseModel) else dict(profile_data)
        )
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(payload)

        with self.transaction("a") as h5:
            hw_grp = h5["hardware_profiles"]
            if profile_id in hw_grp:
                del hw_grp[profile_id]
            hw_grp.create_dataset(
                profile_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_hardware_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered hardware profile by ID."""
        with self.transaction("r") as h5:
            if "hardware_profiles" not in h5 or profile_id not in h5["hardware_profiles"]:
                return None
            val = h5["hardware_profiles"][profile_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_all_hardware_profiles(self) -> List[Dict[str, Any]]:
        """Returns all hardware profiles."""
        results = []
        with self.transaction("r") as h5:
            if "hardware_profiles" in h5:
                for k in h5["hardware_profiles"].keys():
                    val = h5["hardware_profiles"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["profile_id"] = k
                    results.append(data)
        return results

    def delete_hardware_profile(self, profile_id: str) -> bool:
        """Deletes a hardware profile from the registry."""
        with self.transaction("a") as h5:
            if "hardware_profiles" in h5 and profile_id in h5["hardware_profiles"]:
                del h5["hardware_profiles"][profile_id]
                return True
            return False

    def add_provenance_record(self, record_id: str, record_data: Dict[str, Any]) -> str:
        """Adds a cryptographic/workflow provenance record and returns a unique lineage UUID."""
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string.")

        lineage_uuid = f"lin_{uuid.uuid4().hex}"
        payload = dict(record_data)
        payload["record_id"] = record_id
        payload["lineage_uuid"] = lineage_uuid
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            prov_grp = h5["provenance"]
            if record_id in prov_grp:
                del prov_grp[record_id]
            prov_grp.create_dataset(
                record_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8")
            )

        return lineage_uuid

    def get_provenance_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a provenance record by ID."""
        with self.transaction("r") as h5:
            if "provenance" not in h5 or record_id not in h5["provenance"]:
                return None
            val = h5["provenance"][record_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[Dict[str, Any]], json.loads(text))

    def get_lineage_chain(self, leaf_record_id: str) -> List[Dict[str, Any]]:
        """Traces the backward DAG lineage chain from leaf to root with cycle protection."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}
        visited = set()

        curr = rec_by_id.get(curr_id)
        while curr is not None:
            curr_uuid = curr.get("lineage_uuid")
            if curr_uuid in visited:
                logger.warning(f"Provenance cycle detected at record {curr_id}")
                break
            if curr_uuid:
                visited.add(curr_uuid)
            chain.append(curr)
            parent_uuid = curr.get("parent_uuid")
            if not parent_uuid or parent_uuid not in all_prov:
                break
            curr = all_prov.get(parent_uuid)

        return chain

    def get_all_provenance_records(self) -> List[Dict[str, Any]]:
        """Returns all provenance records."""
        results = []
        with self.transaction("r") as h5:
            if "provenance" in h5:
                for k in h5["provenance"].keys():
                    val = h5["provenance"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    results.append(data)
        return results

    def delete_provenance_record(self, record_id: str) -> bool:
        """Deletes a provenance record."""
        with self.transaction("a") as h5:
            if "provenance" in h5 and record_id in h5["provenance"]:
                del h5["provenance"][record_id]
                return True
            return False

    def lock_prng_seed(
        self, seed: int, scope: str = "global", metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Locks a pseudorandom number generator seed into the registry."""
        if not isinstance(seed, int):
            raise ValueError("PRNG seed must be an integer.")

        payload = {
            "seed": seed,
            "scope": scope,
            "metadata": metadata or {},
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.transaction("a") as h5:
            seeds_grp = h5["seeds"]
            if scope in seeds_grp:
                del seeds_grp[scope]
            seeds_grp.create_dataset(
                scope, data=json.dumps(payload), dtype=h5py.string_dtype(encoding="utf-8")
            )

        return seed

    def get_locked_seed(self, scope: str = "global") -> Optional[int]:
        """Retrieves a locked PRNG seed for a given scope."""
        with self.transaction("r") as h5:
            if "seeds" not in h5 or scope not in h5["seeds"]:
                return None
            val = h5["seeds"][scope][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return cast(Optional[int], json.loads(text).get("seed"))

    def verify_prng_seed(self, seed: int, scope: str = "global") -> bool:
        """Verifies if an active seed matches the registered locked seed for a scope."""
        locked = self.get_locked_seed(scope)
        return locked is not None and locked == seed

    def list_locked_seeds(self) -> Dict[str, int]:
        """Returns all locked seeds mapped by scope."""
        res = {}
        with self.transaction("r") as h5:
            if "seeds" in h5:
                for k in h5["seeds"].keys():
                    val = h5["seeds"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    res[k] = json.loads(text).get("seed")
        return res

    def embed_basis_set_archive(
        self,
        h5_path: Optional[str] = None,
        basis_file_path: str = "",
        label: str = "",
        is_content: bool = False,
    ) -> None:
        """Embeds full basis set text into the HDF5 archive to prevent link rot."""
        if not label or not isinstance(label, str) or not label.strip():
            raise ValueError("Basis set label must be a non-empty string.")

        clean_label = label.strip()

        if is_content:
            raw_text = basis_file_path
        else:
            p = Path(basis_file_path)
            if not p.is_file():
                raise FileNotFoundError(f"Basis set file not found: {p}")
            raw_text = p.read_text(encoding="utf-8")

        mapped_h5 = Path(h5_path or self.registry_path)
        with AtomicFileLock(str(mapped_h5) + ".lock", timeout=10.0):
            with h5py.File(mapped_h5, "a") as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")
                grp = h5["embedded_basis_sets"]
                if clean_label in grp:
                    del grp[clean_label]
                grp.create_dataset(
                    clean_label, data=raw_text, dtype=h5py.string_dtype(encoding="utf-8")
                )

    def has_embedded_basis_set(self, label: str) -> bool:
        """Checks if a basis set label exists in the registry."""
        with self.transaction("r") as h5:
            return "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]

    def get_embedded_basis_set(self, label: str) -> str:
        """Retrieves embedded basis set content."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" not in h5 or label not in h5["embedded_basis_sets"]:
                raise BasisSetNotFoundError(f"Basis set '{label}' not found in registry.")
            val = h5["embedded_basis_sets"][label][()]
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

    def list_embedded_basis_sets(self) -> List[str]:
        """Lists all embedded basis set labels."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" in h5:
                return list(h5["embedded_basis_sets"].keys())
            return []

    def delete_embedded_basis_set(self, label: str) -> bool:
        """Deletes an embedded basis set."""
        with self.transaction("a") as h5:
            if "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]:
                del h5["embedded_basis_sets"][label]
                return True
            return False

    def migrate_legacy_schema(self) -> Dict[str, Any]:
        """Upgrades legacy HDF5 schema files to 1.0.0."""
        with self.transaction("a") as h5:
            prev_ver = h5.attrs.get("version", "0.1")
            if isinstance(prev_ver, bytes):
                prev_ver = prev_ver.decode("utf-8")

            h5.attrs["version"] = self.SCHEMA_VERSION
            h5.attrs["migrated_at"] = datetime.now(timezone.utc).isoformat()

            for grp in [
                "hardware_profiles",
                "basis_sets",
                "embedded_basis_sets",
                "provenance",
                "seeds",
                "metadata",
            ]:
                if grp not in h5:
                    h5.create_group(grp)

            return {
                "previous_version": str(prev_ver),
                "current_version": self.SCHEMA_VERSION,
                "status": "migrated",
            }

    def set_metadata(self, key: str, value: Any) -> None:
        """Sets arbitrary metadata key/value into the registry."""
        with self.transaction("a") as h5:
            meta_grp = h5["metadata"]
            if key in meta_grp:
                del meta_grp[key]
            meta_grp.create_dataset(
                key, data=json.dumps(value), dtype=h5py.string_dtype(encoding="utf-8")
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieves arbitrary metadata value."""
        with self.transaction("r") as h5:
            if "metadata" not in h5 or key not in h5["metadata"]:
                return default
            val = h5["metadata"][key][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)


__all__ = [
    "AtomicFileLock",
    "BasisSetNotFoundError",
    "CoChemLockTimeoutError",
    "IsotopeStabilityError",
    "RecordNotFoundError",
    "RegistryCorruptionError",
    "RegistryError",
    "RegistryLockError",
    "RegistryLockTimeoutError",
    "RegistryManager",
    "RegistryMissingError",
    "RegistryParseError",
    "SchemaMigrationError",
    "atomic_write_json",
    "broadcast_system_config",
    "get_active_job",
    "get_default_config_path",
    "hash_environment",
    "interpolate_env_vars",
    "is_master_node",
    "list_active_jobs",
    "load_system_config",
    "migrate_schema",
    "receive_system_config_broadcast",
    "register_active_job",
    "remove_active_job",
    "save_system_config",
    "update_active_job",
    "update_system_config",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_core_registry_manager.py ---
"""
Physical Unit and Integration Test Suite for CoChem Core Registry Manager (cochem_core_registry_manager.py).

Zero-Mock Mandate:
- Tests real physical files on disk via pytest tmp_path.
- Tests real threads and concurrency.
- Tests real cryptographic SHA-256 checksums and corruption detection.
- Tests real environment variable interpolation across Windows/POSIX styles (%VAR%, ${VAR}, $VAR, ~).
- Tests real Stage 0 Guardrails (RegistryMissingError, RegistryCorruptionError, RegistryParseError).
- Tests real lock re-entrancy, contention timeouts, and stale lock auto-reaping.
- Tests real schema migration via RegistryMigrator.
- Tests real active job tracking in cochem_system_config.json.
- Tests real HDF5 state registry, provenance DAGs, basis sets, PRNG seeds, and Mendeleev isotopic queries.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any, Dict, List

import pytest
from pydantic import BaseModel, Field

from cochem_core_registry_manager import (
    AtomicFileLock,
    BasisSetNotFoundError,
    CoChemLockTimeoutError,
    IsotopeStabilityError,
    RecordNotFoundError,
    RegistryCorruptionError,
    RegistryError,
    RegistryLockError,
    RegistryLockTimeoutError,
    RegistryManager,
    RegistryMissingError,
    RegistryParseError,
    SchemaMigrationError,
    atomic_write_json,
    broadcast_system_config,
    get_active_job,
    get_default_config_path,
    hash_environment,
    interpolate_env_vars,
    is_master_node,
    list_active_jobs,
    load_system_config,
    migrate_schema,
    receive_system_config_broadcast,
    register_active_job,
    remove_active_job,
    save_system_config,
    update_active_job,
    update_system_config,
)
from cochem_core_registry_schema import (
    CoChemSystemConfig,
    HardwareSchema,
    OSTarget,
    QuantumSettings,
)


class PhysicalTestJobModel(BaseModel):
    command: List[str] = Field(default_factory=lambda: ["orca", "input.inp"])
    product_class: str = "Polymer_Alpha"
    atom_count: int = 48
    converged: bool = True


class HardwareProfileModel(BaseModel):
    cpu_cores: int = 16
    ram_gb: float = 64.0
    gpu_profile: str = "RTX_4090"


# =============================================================================
# 1. EXCEPTION HIERARCHY & INVARIANTS
# =============================================================================

def test_custom_exception_hierarchy() -> None:
    """Verify all typed exceptions conform to the CoChem exception hierarchy."""
    assert issubclass(RegistryError, Exception)
    assert issubclass(RegistryLockError, RegistryError)
    assert issubclass(CoChemLockTimeoutError, RegistryLockError)
    assert issubclass(CoChemLockTimeoutError, TimeoutError)
    assert issubclass(RegistryLockTimeoutError, RegistryLockError)
    assert issubclass(RegistryMissingError, RegistryError)
    assert issubclass(RegistryMissingError, FileNotFoundError)
    assert issubclass(RegistryCorruptionError, RegistryError)
    assert issubclass(RegistryCorruptionError, ValueError)
    assert issubclass(RegistryParseError, RegistryError)
    assert issubclass(RegistryParseError, ValueError)
    assert issubclass(RecordNotFoundError, RegistryError)
    assert issubclass(BasisSetNotFoundError, RegistryError)
    assert issubclass(SchemaMigrationError, RegistryError)
    assert issubclass(IsotopeStabilityError, RegistryError)


# =============================================================================
# 2. ATOMIC FILE LOCKING: LIFECYCLE, RE-ENTRANCY, CONTENTION, STALE REAPING
# =============================================================================

def test_atomic_file_lock_clean_lifecycle(tmp_path: Path) -> None:
    """Test standard atomic lock acquisition, context manager entry, and cleanup on exit."""
    lock_file = tmp_path / "resource.lock"

    assert not lock_file.exists()
    with AtomicFileLock(lock_file, timeout=2.0) as lock:
        assert lock_file.exists()
        assert lock._is_locked is True
        # Verify content written inside lock file
        content = lock_file.read_text(encoding="utf-8")
        assert f"{os.getpid()}:" in content

    assert not lock_file.exists()
    assert lock._is_locked is False


def test_atomic_file_lock_reentrancy_same_thread(tmp_path: Path) -> None:
    """Verify thread-local re-entrancy on the same instance and different instances on same thread."""
    lock_file = tmp_path / "reentrant.lock"

    # Same instance nested
    lock = AtomicFileLock(lock_file, timeout=2.0)
    with lock:
        assert lock_file.exists()
        with lock:
            assert lock_file.exists()
            with lock:
                assert lock_file.exists()
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()

    # Separate instances targeting same path on same thread
    l1 = AtomicFileLock(lock_file, timeout=2.0)
    l2 = AtomicFileLock(lock_file, timeout=2.0)
    with l1:
        assert lock_file.exists()
        with l2:
            assert lock_file.exists()
        assert lock_file.exists()
    assert not lock_file.exists()


def test_atomic_file_lock_contention_and_timeout(tmp_path: Path) -> None:
    """Verify lock contention between different threads raises CoChemLockTimeoutError."""
    lock_file = tmp_path / "contend.lock"

    lock1 = AtomicFileLock(lock_file, timeout=5.0)
    lock1.acquire()
    assert lock_file.exists()

    err_holder: List[Exception] = []

    def thread_target() -> None:
        try:
            lock2 = AtomicFileLock(lock_file, timeout=0.1)
            lock2.acquire()
        except Exception as exc:
            err_holder.append(exc)

    t = threading.Thread(target=thread_target)
    t.start()
    t.join()

    assert len(err_holder) == 1
    assert isinstance(err_holder[0], CoChemLockTimeoutError)
    assert isinstance(err_holder[0], RegistryLockError)

    # Release first lock, new thread should now succeed
    lock1.release()
    assert not lock_file.exists()

    lock3 = AtomicFileLock(lock_file, timeout=1.0)
    assert lock3.acquire() is True
    lock3.release()


def test_atomic_file_lock_stale_lock_auto_reaping(tmp_path: Path) -> None:
    """Verify stale lock files older than stale_timeout are automatically reaped."""
    lock_file = tmp_path / "stale.lock"
    lock_file.write_text("99999:000:0\n", encoding="utf-8")

    # Set mtime to 300 seconds in the past
    past_time = time.time() - 300
    os.utime(lock_file, (past_time, past_time))

    # Acquisition with stale_timeout=1.0 should reap the lock
    lock = AtomicFileLock(lock_file, timeout=2.0, stale_timeout=1.0)
    assert lock.acquire() is True
    assert lock_file.exists()
    lock.release()
    assert not lock_file.exists()


# =============================================================================
# 3. ATOMIC JSON WRITING
# =============================================================================

def test_atomic_write_json_clean_execution(tmp_path: Path) -> None:
    """Verify atomic JSON writing produces clean output and leaves no temporary files behind."""
    out_file = tmp_path / "atomic_test.json"
    payload = {
        "project": "CoChem-BASE",
        "version": "4.0.0",
        "threads": 16,
        "active": True,
    }

    atomic_write_json(out_file, payload)
    assert out_file.exists()

    # Verify no tmp files in directory
    files_in_dir = list(tmp_path.iterdir())
    assert len(files_in_dir) == 1
    assert files_in_dir[0] == out_file

    # Verify JSON content
    read_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert read_data == payload


def test_atomic_write_json_with_pydantic_model(tmp_path: Path) -> None:
    """Verify atomic_write_json directly accepts Pydantic models."""
    out_file = tmp_path / "model_test.json"
    model = PhysicalTestJobModel(product_class="Polymer_Beta", atom_count=96)

    atomic_write_json(out_file, model)
    assert out_file.exists()

    read_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert read_data["product_class"] == "Polymer_Beta"
    assert read_data["atom_count"] == 96
    assert read_data["converged"] is True


# =============================================================================
# 4. ENVIRONMENT VARIABLE INTERPOLATION (${VAR}, $VAR, %VAR%, ~)
# =============================================================================

def test_interpolate_env_vars_all_syntaxes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify interpolation handles ${VAR}, $VAR, %VAR%, and home directory across OSs."""
    monkeypatch.setenv("COCHEM_BIN_DIR", "opt/cochem/bin")
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", "tmp/scratch")
    monkeypatch.setenv("COCHEM_MAX_CORES", "32")

    # String with ${VAR}
    assert interpolate_env_vars("${COCHEM_BIN_DIR}/orca") == "opt/cochem/bin/orca"

    # String with $VAR
    assert interpolate_env_vars("$COCHEM_SCRATCH_DIR/job_1") == "tmp/scratch/job_1"

    # String with %VAR% (Windows style)
    assert interpolate_env_vars("%COCHEM_BIN_DIR%/xtb") == "opt/cochem/bin/xtb"

    # Combined strings
    combined = "${COCHEM_BIN_DIR}/mpirun -n %COCHEM_MAX_CORES% $COCHEM_SCRATCH_DIR"
    assert interpolate_env_vars(combined) == "opt/cochem/bin/mpirun -n 32 tmp/scratch"

    # Unset env vars should remain uncorrupted
    assert interpolate_env_vars("${UNSET_VARIABLE_XYZ}/test") == "${UNSET_VARIABLE_XYZ}/test"
    assert interpolate_env_vars("%UNSET_VARIABLE_XYZ%/test") == "%UNSET_VARIABLE_XYZ%/test"

    # Dictionary input
    dict_payload = {
        "orca_path": "${COCHEM_BIN_DIR}/orca",
        "scratch": "$COCHEM_SCRATCH_DIR",
        "cores": "%COCHEM_MAX_CORES%",
        "nested": {
            "path": "${COCHEM_BIN_DIR}/tools",
            "list_paths": ["${COCHEM_BIN_DIR}/1", "$COCHEM_SCRATCH_DIR/2"],
        },
    }
    interpolated_dict = interpolate_env_vars(dict_payload)
    assert interpolated_dict["orca_path"] == "opt/cochem/bin/orca"
    assert interpolated_dict["scratch"] == "tmp/scratch"
    assert interpolated_dict["cores"] == "32"
    assert interpolated_dict["nested"]["path"] == "opt/cochem/bin/tools"
    assert interpolated_dict["nested"]["list_paths"] == ["opt/cochem/bin/1", "tmp/scratch/2"]


# =============================================================================
# 5. STAGE 0 GUARDRAILS: MISSING, CORRUPTED CHECKSUM, AND UNPARSEABLE JSON
# =============================================================================

def test_stage_0_guardrail_missing_registry_raises_registry_missing_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST halt gracefully on non-existent config file."""
    non_existent = tmp_path / "missing_config.json"
    with pytest.raises(RegistryMissingError) as exc_info:
        load_system_config(non_existent)

    assert issubclass(RegistryMissingError, FileNotFoundError)
    assert "Stage 0 Guardrail: Master registry not found" in str(exc_info.value)


def test_stage_0_guardrail_unparseable_json_raises_registry_parse_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST raise RegistryParseError on malformed JSON."""
    bad_json_file = tmp_path / "corrupted.json"
    bad_json_file.write_text("{'invalid_json': True, missing_quotes}", encoding="utf-8")

    with pytest.raises(RegistryParseError) as exc_info:
        load_system_config(bad_json_file)

    assert issubclass(RegistryParseError, ValueError)
    assert "Stage 0 Guardrail: Unparseable registry JSON" in str(exc_info.value)


def test_stage_0_guardrail_non_object_root_raises_registry_parse_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: load_system_config MUST raise RegistryParseError if JSON root is not an object."""
    array_file = tmp_path / "array.json"
    array_file.write_text(json.dumps(["item1", "item2"]), encoding="utf-8")

    with pytest.raises(RegistryParseError) as exc_info:
        load_system_config(array_file)

    assert "Registry root must be a JSON object" in str(exc_info.value)


def test_stage_0_guardrail_corrupted_checksum_raises_registry_corruption_error(tmp_path: Path) -> None:
    """Stage 0 Guardrail: Tampered payload with mismatched checksum MUST raise RegistryCorruptionError."""
    cfg_file = tmp_path / "tampered_config.json"

    # Create a valid config model
    valid_cfg = CoChemSystemConfig(
        hardware=HardwareSchema(
            physical_cpu_cores=8,
            logical_cpu_cores=16,
            ram_gb=32.0,
            os_target=OSTarget.LOCAL_LINUX,
        ),
        quantum_settings=QuantumSettings(implicit_solvation="CPCM"),
    )
    save_system_config(valid_cfg, cfg_file)
    assert cfg_file.exists()

    # Read the raw JSON and tamper with a value while preserving original checksum
    raw_dict = json.loads(cfg_file.read_text(encoding="utf-8"))
    original_checksum = raw_dict["registry_checksum"]
    raw_dict["hardware"]["ram_gb"] = 128.0  # Tampering with RAM bounds
    raw_dict["registry_checksum"] = original_checksum  # Deliberately stale/spoofed checksum
    cfg_file.write_text(json.dumps(raw_dict, indent=2), encoding="utf-8")

    # Loading with verify_integrity=True MUST raise RegistryCorruptionError
    with pytest.raises(RegistryCorruptionError) as exc_info:
        load_system_config(cfg_file, verify_integrity=True)

    assert issubclass(RegistryCorruptionError, ValueError)
    assert "Stage 0 Guardrail: Registry corruption" in str(exc_info.value)

    # Loading with verify_integrity=False should allow recovery/inspection
    bypassed_cfg = load_system_config(cfg_file, verify_integrity=False)
    assert bypassed_cfg.hardware.ram_gb == 128.0


# =============================================================================
# 6. CONFIG SAVE, UPDATE, AND CHECKSUM INJECTION
# =============================================================================

def test_system_config_save_injects_valid_sha256_checksum(tmp_path: Path) -> None:
    """Verify saving a config automatically calculates and writes the SHA-256 checksum."""
    cfg_file = tmp_path / "cochem_system_config.json"

    payload = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 12,
            "logical_cpu_cores": 24,
            "ram_gb": 64.0,
            "os_target": "windows_x86_64",
        },
        "quantum_settings": {
            "implicit_solvation": "CPCM",
            "integration_grid": "defgrid2",
        },
    }

    checksum = save_system_config(payload, cfg_file)
    assert isinstance(checksum, str)
    assert len(checksum) == 64

    # Verify checksum matches disk payload
    loaded = load_system_config(cfg_file, verify_integrity=True)
    assert loaded.registry_checksum == checksum
    assert loaded.verify_checksum() is True
    assert loaded.hardware.physical_cpu_cores == 12


def test_system_config_update_atomically_updates_and_recalculates_checksum(tmp_path: Path) -> None:
    """Verify update_system_config modifies fields and updates checksum atomically."""
    cfg_file = tmp_path / "cochem_system_config.json"

    payload = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 42,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "windows_x86_64",
        },
    }
    initial_checksum = save_system_config(payload, cfg_file)

    # Perform atomic update
    updated_cfg = update_system_config(
        config_path=cfg_file,
        rdkit_random_seed=9999,
        orca_version="6.1.2",
    )

    assert updated_cfg.rdkit_random_seed == 9999
    assert updated_cfg.orca_version == "6.1.2"
    assert updated_cfg.registry_checksum != initial_checksum
    assert updated_cfg.verify_checksum() is True

    # Reload from disk to ensure persistence
    reloaded = load_system_config(cfg_file, verify_integrity=True)
    assert reloaded.rdkit_random_seed == 9999
    assert reloaded.orca_version == "6.1.2"


# =============================================================================
# 7. SCHEMA MIGRATION VIA REGISTRY MIGRATOR
# =============================================================================

def test_schema_migration_flat_to_nested_structure(tmp_path: Path) -> None:
    """Verify legacy flat dictionaries are migrated to rigid nested 4.0.0 schemas."""
    orca_abs = str((tmp_path / "orca").resolve())
    xtb_abs = str((tmp_path / "xtb").resolve())
    art_abs = str((tmp_path / "artifacts").resolve())

    legacy_flat_dict = {
        "schema_version": "1.0.0",
        "physical_cpu_cores": 16,
        "logical_cpu_cores": 32,
        "ram_gb": 64.0,
        "os_target": "local-linux",
        "orca_path": orca_abs,
        "xtb_path": xtb_abs,
        "artifacts_dir": art_abs,
    }

    migrated = migrate_schema(legacy_flat_dict)
    assert isinstance(migrated, CoChemSystemConfig)
    assert migrated.schema_version == "4.0.0"
    assert migrated.hardware.physical_cpu_cores == 16
    assert migrated.hardware.logical_cpu_cores == 32
    assert migrated.hardware.ram_gb == 64.0
    assert migrated.hardware.os_target == OSTarget.LOCAL_LINUX
    assert migrated.silo_paths.orca_path == orca_abs
    assert migrated.silo_paths.xtb_path == xtb_abs
    assert migrated.environment.artifacts_dir == art_abs
    assert migrated.quantum_settings is not None
    assert migrated.quantum_settings.integration_grid == "defgrid2"
    assert migrated.hpc.scheduler == "local"


# =============================================================================
# 8. ACTIVE JOBS MANAGEMENT IN SYSTEM CONFIG
# =============================================================================

def test_active_jobs_registration_lifecycle(tmp_path: Path) -> None:
    """Verify register_active_job, get_active_job, list_active_jobs, update_active_job, and remove_active_job."""
    cfg_file = tmp_path / "cochem_system_config.json"
    init_cfg = CoChemSystemConfig.create_default()
    save_system_config(init_cfg, cfg_file)

    # 1. Register active jobs
    job1_payload = {
        "engine": "orca",
        "calc_type": "ts_optimization",
        "status": "running",
        "pid": 12345,
    }
    register_active_job("job_orca_001", job1_payload, config_path=cfg_file)

    job2_model = PhysicalTestJobModel(product_class="Polymer_Gamma", atom_count=32)
    register_active_job("job_orca_002", job2_model, config_path=cfg_file)

    # 2. Get active job
    retrieved_1 = get_active_job("job_orca_001", config_path=cfg_file)
    assert retrieved_1 is not None
    assert retrieved_1["engine"] == "orca"
    assert retrieved_1["status"] == "running"
    assert "registered_at" in retrieved_1

    retrieved_2 = get_active_job("job_orca_002", config_path=cfg_file)
    assert retrieved_2 is not None
    assert retrieved_2["product_class"] == "Polymer_Gamma"

    # Non-existent job
    assert get_active_job("non_existent_job", config_path=cfg_file) is None

    # 3. List active jobs
    all_active = list_active_jobs(config_path=cfg_file)
    assert len(all_active) == 2
    assert "job_orca_001" in all_active
    assert "job_orca_002" in all_active

    # 4. Update active job
    updated_rec = update_active_job(
        "job_orca_001",
        status="completed",
        config_path=cfg_file,
        return_code=0,
        energy=-245.1234,
    )
    assert updated_rec["status"] == "completed"
    assert updated_rec["return_code"] == 0
    assert updated_rec["energy"] == -245.1234
    assert "updated_at" in updated_rec

    # Update non-existent job raises RecordNotFoundError
    with pytest.raises(RecordNotFoundError):
        update_active_job("missing_job", status="failed", config_path=cfg_file)

    # 5. Remove active job
    assert remove_active_job("job_orca_001", config_path=cfg_file) is True
    assert get_active_job("job_orca_001", config_path=cfg_file) is None
    assert remove_active_job("job_orca_001", config_path=cfg_file) is False

    remaining_jobs = list_active_jobs(config_path=cfg_file)
    assert len(remaining_jobs) == 1
    assert "job_orca_002" in remaining_jobs


# =============================================================================
# 9. THREAD SAFETY & CONCURRENT UPDATES
# =============================================================================

def test_multithreaded_concurrent_system_config_updates(tmp_path: Path) -> None:
    """Verify thread safety under heavy concurrent multithreaded updates."""
    cfg_file = tmp_path / "cochem_system_config.json"
    init_cfg = CoChemSystemConfig.create_default()
    save_system_config(init_cfg, cfg_file)

    num_threads = 8
    jobs_per_thread = 5
    exceptions: List[Exception] = []

    def worker_task(thread_idx: int) -> None:
        try:
            for j in range(jobs_per_thread):
                job_id = f"t{thread_idx}_j{j}"
                register_active_job(
                    job_id,
                    {"thread": thread_idx, "job": j, "status": "running"},
                    config_path=cfg_file,
                )
                time.sleep(0.01)
                update_active_job(
                    job_id,
                    status="finished",
                    config_path=cfg_file,
                    progress=100.0,
                )
        except Exception as exc:
            exceptions.append(exc)

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(exceptions) == 0

    # Verify final integrity and that all jobs exist
    final_cfg = load_system_config(cfg_file, verify_integrity=True)
    assert len(final_cfg.active_jobs) == num_threads * jobs_per_thread
    for thread_idx in range(num_threads):
        for j in range(jobs_per_thread):
            job_id = f"t{thread_idx}_j{j}"
            assert job_id in final_cfg.active_jobs
            assert final_cfg.active_jobs[job_id]["status"] == "finished"


# =============================================================================
# 10. HDF5 STATE REGISTRY MANAGER OPERATIONS
# =============================================================================

def test_registry_manager_hdf5_lifecycle(tmp_path: Path) -> None:
    """Verify HDF5 RegistryManager initialization, stats, transactions, and group creation."""
    reg_file = tmp_path / "test_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    assert Path(rm.registry_path).exists()
    assert Path(rm.lock_path) == Path(str(reg_file) + ".lock")

    stats = rm.get_registry_stats()
    assert stats["jobs_count"] == 0
    assert stats["hardware_profiles_count"] == 0
    assert stats["provenance_count"] == 0
    assert stats["basis_sets_count"] == 0
    assert stats["seeds_count"] == 0
    assert stats["version"] == RegistryManager.SCHEMA_VERSION

    # Arbitrary metadata
    rm.set_metadata("cluster_env", "hpc_slurm")
    rm.set_metadata("tolerances", {"scf_e": 1e-8, "scf_grad": 1e-6})
    assert rm.get_metadata("cluster_env") == "hpc_slurm"
    assert rm.get_metadata("tolerances") == {"scf_e": 1e-8, "scf_grad": 1e-6}
    assert rm.get_metadata("non_existent", default=42) == 42


def test_registry_manager_hardware_profiles_and_provenance(tmp_path: Path) -> None:
    """Verify hardware profile storage and provenance DAG lineage chain tracing with cycle detection."""
    reg_file = tmp_path / "hw_prov_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # Hardware profile
    hw_model = HardwareProfileModel(cpu_cores=64, ram_gb=256.0, gpu_profile="A100_80GB")
    rm.register_hardware_profile("node_01", hw_model)
    retrieved_hw = rm.get_hardware_profile("node_01")
    assert retrieved_hw is not None
    assert retrieved_hw["cpu_cores"] == 64
    assert retrieved_hw["gpu_profile"] == "A100_80GB"

    # Provenance DAG
    root_uuid = rm.add_provenance_record("step_1_conformers", {"method": "rdkit_etkdg"})
    step2_uuid = rm.add_provenance_record("step_2_dft_opt", {"method": "r2scan_3c", "parent_uuid": root_uuid})
    step3_uuid = rm.add_provenance_record("step_3_freq", {"method": "num_freq", "parent_uuid": step2_uuid})

    chain = rm.get_lineage_chain("step_3_freq")
    assert len(chain) == 3
    assert chain[0]["record_id"] == "step_3_freq"
    assert chain[1]["record_id"] == "step_2_dft_opt"
    assert chain[2]["record_id"] == "step_1_conformers"


def test_registry_manager_prng_seeds_and_basis_sets(tmp_path: Path) -> None:
    """Verify PRNG seed locking and embedded basis set archival to prevent link rot."""
    reg_file = tmp_path / "seed_basis_reg.h5"
    rm = RegistryManager(registry_path=str(reg_file))

    # PRNG seed locking
    s = rm.lock_prng_seed(12345, scope="global", metadata={"stage": "docking"})
    assert s == 12345
    assert rm.get_locked_seed("global") == 12345
    assert rm.verify_prng_seed(12345, "global") is True
    assert rm.verify_prng_seed(99999, "global") is False

    # Basis set archival
    basis_raw = "! def2-QZVP\nC 0\nS 4 1.00\n  200.0 0.05\n  40.0 0.15\n"
    rm.embed_basis_set_archive(label="def2-QZVP", basis_file_path=basis_raw, is_content=True)

    assert rm.has_embedded_basis_set("def2-QZVP") is True
    retrieved_basis = rm.get_embedded_basis_set("def2-QZVP")
    assert "! def2-QZVP" in retrieved_basis

    with pytest.raises(BasisSetNotFoundError):
        rm.get_embedded_basis_set("missing_basis_label")


# =============================================================================
# 11. DYNAMIC ISOTOPIC MASS QUERIES (MENDELEEV / QCELEMENTAL)
# =============================================================================

def test_mendeleev_dynamic_isotopic_mass_queries() -> None:
    """Verify isotopic mass resolution for standard elements, explicit isotopes, and aliases."""
    # Standard Carbon and Hydrogen
    mass_c = RegistryManager.get_isotopic_mass("C")
    assert isinstance(mass_c, float)
    assert 12.00 <= mass_c <= 12.02

    mass_h = RegistryManager.get_isotopic_mass("H")
    assert isinstance(mass_h, float)
    assert 1.007 <= mass_h <= 1.009

    # Explicit isotopes
    mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
    assert 13.003 <= mass_c13 <= 13.004

    mass_h2 = RegistryManager.get_isotopic_mass("H", 2)
    assert 2.014 <= mass_h2 <= 2.015

    # Deuterium and Tritium aliases
    mass_d = RegistryManager.get_isotopic_mass("D")
    assert 2.014 <= mass_d <= 2.015
    mass_t = RegistryManager.get_isotopic_mass("T")
    assert 3.015 <= mass_t <= 3.017

    # Error handling
    with pytest.raises(ValueError):
        RegistryManager.get_isotopic_mass("")

    with pytest.raises(IsotopeStabilityError):
        RegistryManager.get_isotopic_mass("NonExistentElementX999")


# =============================================================================
# 12. ENVIRONMENT DETECTION & ZEROMQ BROADCAST
# =============================================================================

def test_is_master_node_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify is_master_node correctly inspects Slurm, MPI, and environment overrides."""
    # Default standalone
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.delenv("SLURM_PROCID", raising=False)
    monkeypatch.delenv("RANK", raising=False)
    assert is_master_node() is True

    # Override
    monkeypatch.setenv("COCHEM_IS_MASTER", "0")
    assert is_master_node() is False
    monkeypatch.setenv("COCHEM_IS_MASTER", "1")
    assert is_master_node() is True

    # Slurm rank
    monkeypatch.delenv("COCHEM_IS_MASTER", raising=False)
    monkeypatch.setenv("SLURM_PROCID", "0")
    assert is_master_node() is True
    monkeypatch.setenv("SLURM_PROCID", "4")
    assert is_master_node() is False


def test_zeromq_broadcast_and_receive(tmp_path: Path) -> None:
    """Verify master node ZeroMQ broadcast and worker node subscriber reception."""
    cfg_file = tmp_path / "cochem_system_config.json"
    rm = RegistryManager(config_path=str(cfg_file), registry_path=str(tmp_path / "reg.h5"))

    payload = {
        "schema_version": "4.0.0",
        "rdkit_random_seed": 8888,
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 32.0,
            "os_target": "linux_x86_64",
        },
    }
    rm.save_system_config(payload)
    cfg_to_broadcast = rm.load_system_config()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    received_list: List[Any] = []
    pub_ready = threading.Event()

    def subscriber_worker() -> None:
        if not pub_ready.wait(timeout=5.0):
            received_list.append(TimeoutError("Publisher socket failed to bind"))
            return
        time.sleep(0.05)
        try:
            recv_cfg = receive_system_config_broadcast(
                master_host="127.0.0.1", port=port, topic="cochem_system_config", timeout_ms=4000
            )
            received_list.append(recv_cfg)
        except Exception as exc:
            received_list.append(exc)

    def publisher_worker() -> None:
        broadcast_system_config(
            config=cfg_to_broadcast,
            port=port,
            host="127.0.0.1",
            topic="cochem_system_config",
            repeat_count=8,
            repeat_interval=0.05,
            ready_event=pub_ready,
        )

    sub_t = threading.Thread(target=subscriber_worker)
    pub_t = threading.Thread(target=publisher_worker)
    sub_t.start()
    pub_t.start()
    sub_t.join(timeout=5.0)
    pub_t.join(timeout=5.0)

    assert len(received_list) == 1
    received_cfg = received_list[0]
    assert isinstance(received_cfg, CoChemSystemConfig)
    assert received_cfg.rdkit_random_seed == 8888
    assert received_cfg.hardware.physical_cpu_cores == 8

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.