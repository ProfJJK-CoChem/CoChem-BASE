#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Golden Registry Schema Gatekeeper
Defines the absolute Pydantic models for `cochem_system_config.json`.
Guarantees downstream scientific components never encounter missing keys,
type errors, or unmapped hardware states.
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
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


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


class OSTarget(str, Enum):
    """Supported Operating System and Architecture Targets."""
    LINUX_X86_64 = "linux_x86_64"
    LINUX_AARCH64 = "linux_aarch64"
    WINDOWS_X86_64 = "windows_x86_64"
    WINDOWS_AMD64 = "windows_amd64"
    DARWIN_ARM64 = "darwin_arm64"
    DARWIN_X86_64 = "darwin_x86_64"
    GENERIC_POSIX = "posix"
    GENERIC_NT = "nt"


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


class GPUComputeSchema(BaseModel):
    """GPU Compute Metrics and Topology."""
    gpu_profile: str = Field(default="None", description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory in GB")
    device_count: int = Field(default=0, ge=0, description="Number of detected GPU devices")
    compute_capability: Optional[str] = Field(default=None, description="CUDA Compute capability, e.g. '8.9'")
    fp64_capable: bool = Field(default=False, description="Whether device supports native double-precision FP64")
    subnormal_precision_trap: bool = Field(default=False, description="Whether subnormal precision traps are enabled")
    mps_enabled: bool = Field(default=False, description="Whether CUDA MPS is enabled")


class MPSConfig(BaseModel):
    """CUDA Multi-Process Service (MPS) configuration."""
    enabled: bool = Field(default=True, description="Enable CUDA MPS daemon multiplexing")
    max_workers: int = Field(default=4, gt=0, le=64, description="Max concurrent MPS worker tasks per GPU")
    thread_percentage: int = Field(default=25, ge=1, le=100, description="CUDA MPS active thread percentage ceiling")
    pipe_dir: str = Field(default_factory=_default_mps_pipe_dir, description="MPS pipe directory")
    log_dir: str = Field(default_factory=_default_mps_log_dir, description="MPS log directory")


class CorePinningConfig(BaseModel):
    """Core Pinning and Topology Configuration."""
    kmp_hw_subset: str = Field(default="8c:intel_core,1t", description="OpenMP core pinning HW subset spec")
    anchor_p_cores: int = Field(default=7, ge=0, description="Number of P-cores assigned to CPU anchor tasks")
    scout_p_cores: int = Field(default=1, ge=0, description="Number of P-cores assigned to GPU scout tasks")
    background_e_cores: int = Field(default=8, ge=0, description="E-cores reserved for OS/background tasks")


class QuantumSettings(BaseModel):
    """Quantum chemical solver settings."""
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
        return v

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
        return v


class HardwareSchema(BaseModel):
    """Rigid bounds for physical compute resources to prevent OOM/Thread crashes."""
    cpu_cores: Optional[int] = Field(default=None, gt=0, description="Available CPU cores alias")
    physical_cpu_cores: int = Field(..., gt=0, description="Actual silicon cores")
    logical_cpu_cores: int = Field(..., gt=0, description="Hyperthreaded threads")
    ram_mb: Optional[int] = Field(default=None, gt=0, description="Total allocated system RAM in MB")
    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory in GB")
    maxcore_mb: Optional[int] = Field(default=3000, gt=0, description="Max core memory in MB per process")
    avx512_support: bool = Field(default=False, description="CPU vector extension capability")
    gpu_profile: str = Field(default="None", description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory")
    subnormal_precision_trap: bool = Field(default=False)
    os_target: Union[OSTarget, str] = Field(..., description="OS identifier (e.g., linux_x86_64, windows_amd64)")
    host_id: Optional[str] = Field(default=None)
    mps: Optional[MPSConfig] = Field(default_factory=MPSConfig)
    core_pinning: Optional[CorePinningConfig] = Field(default_factory=CorePinningConfig)
    gpu: Optional[GPUComputeSchema] = Field(default_factory=GPUComputeSchema)

    @field_validator("os_target", mode="before")
    @classmethod
    def validate_os_target(cls, v: Any) -> str:
        if isinstance(v, OSTarget):
            return v.value
        if isinstance(v, str):
            v_str = v.strip()
            if v_str == "[MISSING DATA]":
                return v_str
            valid_targets = {t.value for t in OSTarget} | {
                "windows", "linux", "darwin", "linux_x86_64", "windows_x86_64",
                "windows_amd64", "linux_amd64", "darwin_arm64", "darwin_x86_64", "posix", "nt",
                "local-windows", "local-windows_native", "local-windows_wsl",
                "local-macos", "local-macos_darwin", "local-linux", "local-linux_deb",
                "codespaces", "github_codespaces", "github_actions", "hpc", "hpc_slurm_linux"
            }
            if v_str.lower() in valid_targets:
                return v_str
            raise ValueError(f"Invalid OS target '{v}'. Must be a valid OS platform identifier.")
        raise ValueError(f"OS target must be a string or OSTarget enum, got {type(v)}")

    @model_validator(mode="before")
    @classmethod
    def flex_hardware_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for float_field in ["ram_gb", "vram_gb"]:
                if float_field in data and isinstance(data[float_field], str):
                    try:
                        data[float_field] = float(data[float_field])
                    except ValueError:
                        pass
            for int_field in ["cpu_cores", "physical_cpu_cores", "logical_cpu_cores", "ram_mb", "maxcore_mb"]:
                if int_field in data and isinstance(data[int_field], str):
                    try:
                        data[int_field] = int(float(data[int_field]))
                    except ValueError:
                        pass

            if "cpu_cores" not in data and "physical_cpu_cores" in data:
                data["cpu_cores"] = data["physical_cpu_cores"]
            elif "physical_cpu_cores" not in data and "cpu_cores" in data:
                data["physical_cpu_cores"] = data["cpu_cores"]

            if "logical_cpu_cores" not in data or data["logical_cpu_cores"] is None:
                phys = data.get("physical_cpu_cores") or data.get("cpu_cores")
                if phys is not None:
                    try:
                        data["logical_cpu_cores"] = int(phys)
                    except (ValueError, TypeError):
                        pass

            if "ram_mb" not in data and "ram_gb" in data:
                try:
                    data["ram_mb"] = int(float(data["ram_gb"]) * 1024)
                except (ValueError, TypeError):
                    pass
            elif "ram_gb" not in data and "ram_mb" in data:
                try:
                    data["ram_gb"] = float(data["ram_mb"]) / 1024.0
                except (ValueError, TypeError):
                    pass

            if "maxcore_mb" in data and "ram_mb" in data:
                try:
                    maxcore = int(data["maxcore_mb"])
                    ram_mb = int(data["ram_mb"])
                    if maxcore > ram_mb:
                        phys = int(data.get("physical_cpu_cores") or data.get("cpu_cores") or 1)
                        data["maxcore_mb"] = max(500, int(ram_mb * 0.75 / max(1, phys)))
                except (ValueError, TypeError):
                    pass

            if "gpu" not in data or data["gpu"] is None:
                gpu_prof = data.get("gpu_profile", "None")
                vram = data.get("vram_gb", 0.0)
                trap = data.get("subnormal_precision_trap", False)
                data["gpu"] = {
                    "gpu_profile": gpu_prof,
                    "vram_gb": float(vram) if isinstance(vram, (int, float, str)) else 0.0,
                    "subnormal_precision_trap": trap,
                }
        return data


HardwareConfig = HardwareSchema


class EnvironmentSchema(BaseModel):
    """Operating environment configuration and cross-platform path resolution."""
    os_target: Union[OSTarget, str] = Field(
        default_factory=lambda: f"{platform.system().lower()}_{platform.machine().lower()}",
        description="Target OS identifier",
    )
    artifacts_dir: Union[str, Path] = Field(
        default_factory=lambda: os.getenv("COCHEM_ARTIFACTS_DIR", str(Path.home() / "cochem_artifacts")),
        description="Path to artifacts directory",
    )
    scratch_dir: Optional[Union[str, Path]] = Field(default=None, description="Path to fast scratch directory")
    codata_version: str = Field(default="2018", description="CODATA constant version (e.g., '2018')")
    isotopic_mass_locking: bool = Field(default=True, description="Strict lock on atomic/isotopic masses via Mendeleev")
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
            valid_targets = {t.value for t in OSTarget} | {
                "windows", "linux", "darwin", "linux_x86_64", "windows_x86_64",
                "windows_amd64", "linux_amd64", "darwin_arm64", "darwin_x86_64", "posix", "nt",
                "local-windows", "local-windows_native", "local-windows_wsl",
                "local-macos", "local-macos_darwin", "local-linux", "local-linux_deb",
                "codespaces", "github_codespaces", "github_actions", "hpc", "hpc_slurm_linux"
            }
            if v_str.lower() in valid_targets:
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


class SiloPathsSchema(BaseModel):
    """Paths configuration for isolated silos and scientific binaries."""
    orca_path: Optional[str] = Field(default=None, description="Path to ORCA executable or 'BYPASSED'")
    xtb_path: Optional[str] = Field(default=None, description="Path to xTB executable or 'BYPASSED'")
    mpirun_path: Optional[str] = Field(default=None, description="Path to mpirun executable or 'BYPASSED'")
    cfour_path: Optional[str] = Field(default=None, description="Path to CFOUR executable or 'BYPASSED'")
    aimnet2_server_path: Optional[str] = Field(default=None, description="Path to AIMNet2 server script or 'BYPASSED'")
    python_path: Optional[str] = Field(default=None, description="Path to silo Python interpreter")
    silo_root: Optional[str] = Field(default=None, description="Root directory for micro-environments")
    hdf5_pes_store_path: Optional[str] = Field(default=None, description="Path to centralized HDF5 PES store")
    strict_resolution: bool = Field(default=False, description="Enforce binary presence verification")

    @field_validator("orca_path", "xtb_path", "mpirun_path", "cfour_path", "aimnet2_server_path", "python_path", "silo_root", "hdf5_pes_store_path", mode="before")
    @classmethod
    def validate_and_expand_path(cls, v: Any) -> Optional[str]:
        if v is None or v == "" or v == "[MISSING DATA]":
            return None
        if isinstance(v, str):
            s = v.strip()
            if s in ("BYPASSED", "Not_Found", "missing"):
                return s
            return _expand_env_vars(s)
        return str(v)

    def is_bypassed(self, binary_name: str) -> bool:
        attr = f"{binary_name}_path" if not binary_name.endswith("_path") else binary_name
        val = getattr(self, attr, None)
        return val == "BYPASSED"

    def is_found(self, binary_name: str) -> bool:
        attr = f"{binary_name}_path" if not binary_name.endswith("_path") else binary_name
        val = getattr(self, attr, None)
        if not val or val in ("BYPASSED", "Not_Found", "missing"):
            return False
        return Path(val).exists()

    def resolve_binary(self, binary_name: str) -> Optional[str]:
        attr = f"{binary_name}_path" if not binary_name.endswith("_path") else binary_name
        if not hasattr(self, attr):
            raise AttributeError(f"Unknown binary configuration '{binary_name}'")
        val = getattr(self, attr)
        if val is None or val in ("BYPASSED", "Not_Found", "missing"):
            return val
        p = Path(val)
        if self.strict_resolution and not p.exists():
            raise FileNotFoundError(f"Binary '{binary_name}' not found at path '{val}'")
        return str(p.resolve())


class EngineInfo(BaseModel):
    """Pathing and cryptographic provenance for computational binaries."""
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
    orca: Optional[EngineInfo] = Field(default=None)
    mpirun: Optional[EngineInfo] = Field(default=None)
    xtb: Optional[EngineInfo] = Field(default=None)
    cfour: Optional[EngineInfo] = Field(default=None)
    aimnet2: Optional[EngineInfo] = Field(default=None)
    mace: Optional[EngineInfo] = Field(default=None)


class SiloConfig(BaseModel):
    """Micro-environment deployment status."""
    torq_silo_active: bool = Field(default=False)
    gpu_silo_active: bool = Field(default=False)


class RoutingPolicy(BaseModel):
    """Dynamically assigned execution constraints from Phase 11."""
    max_concurrent_mace_threads: int = Field(default=4, gt=0)
    max_dft_basis_functions: int = Field(default=2000, gt=0)
    recommend_ccsdt: bool = Field(default=False)
    classification: str = Field(default="STANDARD")


class HPCConfig(BaseModel):
    """Cluster integration parameters."""
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
        return v


class CoChemSystemConfig(BaseModel):
    """
    The CoChem Master Schema.
    This is the ultimate schema for `cochem_system_config.json`.
    """
    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    orca_version: Optional[str] = Field(default="6.1.1")
    rdkit_random_seed: Optional[int] = Field(default=42)
    registry_checksum: Optional[str] = Field(default="")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hardware: HardwareSchema
    environment: Optional[EnvironmentSchema] = Field(default_factory=EnvironmentSchema)
    silo_paths: Optional[SiloPathsSchema] = Field(default_factory=SiloPathsSchema)
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    silos: Optional[SiloConfig] = Field(default=None, description="Deprecated/optional silos config")
    quantum_settings: Optional[QuantumSettings] = Field(default_factory=QuantumSettings)
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

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
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            os_target="windows_x86_64" if os.name == "nt" else "linux_x86_64",
        )
        return cls(
            hardware=hw,
            quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
            silos=SiloConfig(torq_silo_active=True),
        )


CoChemConfig = CoChemSystemConfig


def discover_engine(binary_name: str) -> EngineInfo:
    p = shutil.which(binary_name)
    if p:
        return EngineInfo(status="found", path=str(p), version="auto", hash="auto")
    return EngineInfo(status="missing", path=None, version=None, hash=None)


def discover_host_hardware() -> HardwareSchema:
    try:
        import psutil  # type: ignore[import-untyped]
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        phys_cores = psutil.cpu_count(logical=False) or 1
        log_cores = psutil.cpu_count(logical=True) or 1
    except ImportError:
        total_ram_gb = 16.0
        phys_cores = os.cpu_count() or 1
        log_cores = os.cpu_count() or 1

    os_target = f"{platform.system().lower()}_{platform.machine().lower()}"

    return HardwareSchema(
        physical_cpu_cores=phys_cores,
        logical_cpu_cores=log_cores,
        ram_gb=round(total_ram_gb, 2),
        avx512_support=False,
        gpu_profile="None",
        vram_gb=0.0,
        os_target=os_target,
    )


def validate_system_config(source: Union[str, Path, Dict[str, Any], CoChemSystemConfig]) -> CoChemSystemConfig:
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
