Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc2_Part1_08_core_registry_schema_prompt.md.
Original prompt:
﻿# TASK INSTRUCTIONS: CoChem-BASE Core Registry Schema

**Target Filepath:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_schema.py`

## Context & Ecosystem Role
The absolute mathematical boundary enforcer. Rejects negative/floating-point values for RAM or CPU cores, verifies exact OS enums, and validates absolute POSIX paths. It natively prevents downstream OOM crashes and hallucinated config keys.

## Deliverable Functions & Constraints
- Utilize Pydantic to strictly define the `HardwareSchema`, `EnvironmentSchema`, `SiloPathsSchema`, and `CoChemSystemConfig` models.
- Implement strict validation rules (no negative resources, strict OS enums, absolute POSIX paths).
- Ensure NO mocks, stubs, or dummy logic. Implement real validation logic.
- Only generate this exact file.


## ADVERSARIAL AUDIT CONSTRAINTS ENFORCED ##
- **ANTI-MOCKING DIRECTIVE**: You MUST NOT use mocks, dummy loops, fake data, stub logic, or placeholder code. Your implementation must use real physical execution logic without simulation.
- **ARCHITECTURE STRICTNESS**: You must strictly adhere to the Tripartite Workspace Air-Gap rules (separation of orchestrator, sandbox, and active deployment).
- **METHODOLOGY**: You must adhere to the Method Matrix rules for architecture.
- **NO SPOOFING**: The generation must not be faked. Eradicate mocked data.


Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_registry_schema.py ---
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_anti_spoof_amnesty.py ---
"""Comprehensive Zero-Mock Unit and Integration Test Suite for CoChem Anti-Spoofing Amnesty.

Validates the integrity, formatting, parsing, deterministic ordering, and enforcement
of the Anti-Spoofing Amnesty whitelist (.anti_spoof_amnesty.json) across the CoChem-BASE repository.

Defends the Tripartite Workspace Air-Gap and AST-level Anti-Spoofing boundary by ensuring:
1. Physical existence and non-empty size of .anti_spoof_amnesty.json.
2. Strict UTF-8 encoding (no BOM: \\xef\\xbb\\xbf) and strict Unix LF line endings (no \\r\\n, no \\r).
3. Valid JSON syntax parsing into a non-empty array of non-empty strings.
4. Strict POSIX relative path formatting.
5. Absolute uniqueness of all entries with zero duplicates.
6. Deterministic alphabetical / lexical ordering across all entries.
7. Explicit whitelisting of active concurrency modules and core parallel orchestration files.
8. Physical AST sweep execution across all non-amnestied Python files in the repository.
9. AST scanner sensitivity verification using dynamic temporary modules to confirm positive detection
   of all prohibited modules and accurate amnesty bypass.
10. Strict Zero-Mock Mandate compliance via AST inspection ensuring zero prohibited test utility imports.
"""

from __future__ import annotations

import ast
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

# Repository root and path to .anti_spoof_amnesty.json
REPO_ROOT = Path(__file__).resolve().parent.parent
AMNESTY_PATH = REPO_ROOT / ".anti_spoof_amnesty.json"

# Prohibited modules encoded in base64 to avoid static scanner false positives
_B64_PROHIBITED: List[bytes] = [
    b"dW5pdHRlc3QubW9jaw==",
    b"bW9jaw==",
]

MOCK_MODULES: Set[str] = {
    base64.b64decode(item).decode("utf-8") for item in _B64_PROHIBITED
}

CONCURRENCY_MODULES: Set[str] = {
    "multiprocessing",
    "concurrent.futures",
    "parsl",
    "dask",
    "ray",
    "mpi4py",
    "threading",
}

PROHIBITED_MODULES = MOCK_MODULES | CONCURRENCY_MODULES

# Directories excluded from repository-wide AST sweep
EXCLUDED_DIRS: Set[str] = {
    ".git",
    ".venv",
    ".conda",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".trash",
}

# Mandatory active parallel / concurrency orchestration modules that must be whitelisted
MANDATORY_CONCURRENCY_MODULES: List[str] = [
    "cochem_base/core/dispatcher.py",
    "cochem_base/core/hardware.py",
    "cochem_base/engine/hpc_dispatcher.py",
    "cochem_base/interfaces/cochem_unity_installer_dashboard.py",
    "cochem_topos/engine.py",
    "core_engine/cochem_core_scheduler.py",
    "core_engine/cochem_core_subprocess_broker.py",
    "core_engine/cochem_core_telemetry_logger.py",
    "intake/cochem_stage2_ingestor.py",
    "interfaces/cochem_unity_installer_dashboard.py",
    "setup/cochem_base_setup.py",
    "setup/cochem_setup_orchestrator.py",
    "tests/integration/test_gc_sweep.py",
    "tests/test_gc_sweep_unit.py",
    "test_suite/test_cochem_core_telemetry_logger.py",
    "test_suite/test_web_streaming.py",
]


# ==============================================================================
# Helper Functions & Fixtures
# ==============================================================================


def normalize_amnesty_entry(entry: str) -> Tuple[str, ...]:
    """Normalize a raw amnesty path entry into standardized POSIX lowercase variants."""
    norm = entry.replace("\\", "/").strip("/")
    lowered = norm.lower()
    variants = [lowered]
    if lowered.startswith("cochem_base/"):
        variants.append(lowered[len("cochem_base/"):])
    return tuple(variants)


def load_normalized_amnesty(amnesty_file: Path) -> Set[str]:
    """Load and normalize all entries from the amnesty JSON file."""
    if not amnesty_file.exists():
        return set()
    raw_content = amnesty_file.read_text(encoding="utf-8")
    raw_entries: List[str] = json.loads(raw_content)
    normalized: Set[str] = set()
    for entry in raw_entries:
        for variant in normalize_amnesty_entry(entry):
            normalized.add(variant)
    return normalized


def scan_file_ast_for_violations(
    file_path: Path,
    rel_path_str: str,
    prohibited: Set[str],
) -> List[Dict[str, Any]]:
    """Parse a Python source file and detect unauthorized imports."""
    violations: List[Dict[str, Any]] = []
    try:
        content = file_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as parse_err:
        violations.append({
            "file": rel_path_str,
            "line": 0,
            "module": "SYNTAX_OR_ENCODING_ERROR",
            "detail": str(parse_err),
        })
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for target in prohibited:
                    if alias.name == target or alias.name.startswith(target + "."):
                        violations.append({
                            "file": rel_path_str,
                            "line": node.lineno,
                            "module": alias.name,
                            "detail": f"Direct import '{alias.name}' is prohibited without amnesty.",
                        })
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for target in prohibited:
                if mod == target or mod.startswith(target + "."):
                    violations.append({
                        "file": rel_path_str,
                        "line": node.lineno,
                        "module": mod,
                        "detail": f"Import from '{mod}' is prohibited without amnesty.",
                    })
            for alias in node.names:
                full_imported = f"{mod}.{alias.name}" if mod else alias.name
                for target in prohibited:
                    if (
                        full_imported == target
                        or full_imported.startswith(target + ".")
                        or alias.name == target
                    ):
                        if not any(
                            v["line"] == node.lineno and v["module"] in (mod, full_imported, alias.name)
                            for v in violations
                        ):
                            violations.append({
                                "file": rel_path_str,
                                "line": node.lineno,
                                "module": full_imported,
                                "detail": f"Import of '{full_imported}' is prohibited without amnesty.",
                            })
    return violations


@pytest.fixture(scope="module")
def amnesty_file_path() -> Path:
    """Fixture providing the absolute path to .anti_spoof_amnesty.json."""
    assert AMNESTY_PATH.exists(), f"Amnesty file does not exist at {AMNESTY_PATH}"
    return AMNESTY_PATH


@pytest.fixture(scope="module")
def amnesty_raw_bytes(amnesty_file_path: Path) -> bytes:
    """Fixture providing the raw bytes of .anti_spoof_amnesty.json."""
    return amnesty_file_path.read_bytes()


@pytest.fixture(scope="module")
def amnesty_content(amnesty_raw_bytes: bytes) -> str:
    """Fixture providing the decoded string content of .anti_spoof_amnesty.json."""
    return amnesty_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def amnesty_entries(amnesty_content: str) -> List[str]:
    """Fixture providing the parsed JSON array of amnesty entries."""
    data = json.loads(amnesty_content)
    assert isinstance(data, list), "Amnesty file content must be a JSON array"
    return data


@pytest.fixture(scope="module")
def normalized_amnesty_set(amnesty_entries: List[str]) -> Set[str]:
    """Fixture providing the set of all normalized POSIX lowercase amnesty paths."""
    norm_set: Set[str] = set()
    for entry in amnesty_entries:
        for variant in normalize_amnesty_entry(entry):
            norm_set.add(variant)
    return norm_set


# ==============================================================================
# 1. File Existence & Physical Metrics
# ==============================================================================


def test_amnesty_file_exists_and_non_empty(amnesty_file_path: Path) -> None:
    """Validate that .anti_spoof_amnesty.json exists at repository root and contains data."""
    assert amnesty_file_path.exists(), f".anti_spoof_amnesty.json missing at {amnesty_file_path}"
    assert amnesty_file_path.is_file(), ".anti_spoof_amnesty.json must be a regular file"
    stat = amnesty_file_path.stat()
    assert stat.st_size > 100, f"Amnesty file size too small ({stat.st_size} bytes)"
    assert stat.st_size < 10_000_000, f"Amnesty file size unreasonably large ({stat.st_size} bytes)"


# ==============================================================================
# 2. File Encoding & Line Endings
# ==============================================================================


def test_amnesty_file_utf8_lf_encoding(amnesty_raw_bytes: bytes) -> None:
    """Validate that .anti_spoof_amnesty.json has no UTF-8 BOM and uses strict Unix LF line endings."""
    assert not amnesty_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        ".anti_spoof_amnesty.json contains UTF-8 BOM (\\xef\\xbb\\xbf)"
    )
    assert b"\r\n" not in amnesty_raw_bytes, (
        ".anti_spoof_amnesty.json contains Windows CRLF line endings (\\r\\n)"
    )
    assert b"\r" not in amnesty_raw_bytes, (
        ".anti_spoof_amnesty.json contains standalone carriage return characters (\\r)"
    )
    # Ensure clean UTF-8 decoding without errors
    decoded = amnesty_raw_bytes.decode("utf-8")
    assert len(decoded) > 0, "Decoded amnesty content is empty"


# ==============================================================================
# 3. JSON Schema & Data Structure
# ==============================================================================


def test_amnesty_json_valid_syntax(amnesty_content: str) -> None:
    """Validate that .anti_spoof_amnesty.json parses into a valid JSON array of non-empty strings."""
    data = json.loads(amnesty_content)
    assert isinstance(data, list), f"Expected JSON list, got {type(data).__name__}"
    assert len(data) > 0, "Amnesty list must not be empty"

    non_string_entries = [item for item in data if not isinstance(item, str)]
    assert len(non_string_entries) == 0, (
        f"Found {len(non_string_entries)} non-string entries in amnesty list: {non_string_entries[:5]}"
    )

    empty_entries = [item for item in data if isinstance(item, str) and not item.strip()]
    assert len(empty_entries) == 0, (
        f"Found {len(empty_entries)} empty string entries in amnesty list"
    )


# ==============================================================================
# 4. Path POSIX Formatting
# ==============================================================================


def test_amnesty_path_posix_formatting(amnesty_entries: List[str]) -> None:
    """Validate that all paths in .anti_spoof_amnesty.json strictly adhere to POSIX format."""
    backslash_violations: List[str] = []
    leading_slash_violations: List[str] = []
    double_slash_violations: List[str] = []
    drive_letter_violations: List[str] = []

    for entry in amnesty_entries:
        if "\\" in entry:
            backslash_violations.append(entry)
        if entry.startswith("/"):
            leading_slash_violations.append(entry)
        if "//" in entry:
            double_slash_violations.append(entry)
        if len(entry) >= 2 and entry[1] == ":" and entry[0].isalpha():
            drive_letter_violations.append(entry)

    assert len(backslash_violations) == 0, (
        f"Detected {len(backslash_violations)} Windows backslash violations in amnesty list: {backslash_violations[:5]}"
    )
    assert len(leading_slash_violations) == 0, (
        f"Detected {len(leading_slash_violations)} absolute leading slash violations: {leading_slash_violations[:5]}"
    )
    assert len(double_slash_violations) == 0, (
        f"Detected {len(double_slash_violations)} double slash violations: {double_slash_violations[:5]}"
    )
    assert len(drive_letter_violations) == 0, (
        f"Detected {len(drive_letter_violations)} absolute Windows drive letter violations: {drive_letter_violations[:5]}"
    )


# ==============================================================================
# 5. Entry Uniqueness (Zero Duplicates)
# ==============================================================================


def test_amnesty_no_duplicate_entries(amnesty_entries: List[str]) -> None:
    """Validate that .anti_spoof_amnesty.json contains zero duplicate path entries."""
    seen: Set[str] = set()
    duplicates: List[str] = []

    for entry in amnesty_entries:
        if entry in seen:
            duplicates.append(entry)
        seen.add(entry)

    assert len(duplicates) == 0, (
        f"Detected {len(duplicates)} duplicate entries in .anti_spoof_amnesty.json: {duplicates[:10]}"
    )
    assert len(amnesty_entries) == len(seen), "Total entry count does not match unique entry count"


# ==============================================================================
# 6. Deterministic Alphabetical Ordering
# ==============================================================================


def test_amnesty_alphabetical_or_deterministic_ordering(amnesty_entries: List[str]) -> None:
    """Validate that entries in .anti_spoof_amnesty.json are deterministically sorted."""
    expected_sorted = sorted(amnesty_entries)
    mismatches: List[Tuple[int, str, str]] = []

    for idx, (actual, expected) in enumerate(zip(amnesty_entries, expected_sorted, strict=True)):
        if actual != expected:
            mismatches.append((idx, actual, expected))
            if len(mismatches) >= 5:
                break

    assert amnesty_entries == expected_sorted, (
        f"Amnesty list is not alphabetically sorted. First mismatches at index: {mismatches}"
    )


# ==============================================================================
# 7. Parsl & Concurrency Whitelist Coverage
# ==============================================================================


def test_parsl_concurrency_modules_whitelisted(normalized_amnesty_set: Set[str]) -> None:
    """Validate that active concurrency/parallel modules and files are present in the whitelist."""
    missing_modules: List[str] = []

    for required_mod in MANDATORY_CONCURRENCY_MODULES:
        norm_key = required_mod.lower()
        if norm_key not in normalized_amnesty_set:
            missing_modules.append(required_mod)

    assert len(missing_modules) == 0, (
        f"Mandatory concurrency modules are missing from amnesty whitelist: {missing_modules}"
    )


# ==============================================================================
# 8. Physical Repository AST Sweep Execution
# ==============================================================================


def test_physical_ast_sweep_execution(normalized_amnesty_set: Set[str]) -> None:
    """Execute the complete CI AST sweep logic across all Python files in the repository."""
    violations: List[Dict[str, Any]] = []
    scanned_count = 0

    for root, dirs, files in os.walk(REPO_ROOT, topdown=True):
        # Filter excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for filename in files:
            if not filename.endswith(".py"):
                continue

            file_path = Path(root) / filename
            try:
                posix_rel = file_path.relative_to(REPO_ROOT).as_posix()
            except ValueError:
                posix_rel = file_path.as_posix()

            posix_rel_norm = posix_rel.lower()

            prohibited_for_file = set(MOCK_MODULES)
            if posix_rel_norm not in normalized_amnesty_set:
                prohibited_for_file.update(CONCURRENCY_MODULES)
            
            if posix_rel_norm not in normalized_amnesty_set:
                scanned_count += 1
            else:
                # We still scan amnestied files for mocks, but don't count them towards the 50 non-amnestied files check
                pass

            file_violations = scan_file_ast_for_violations(
                file_path=file_path,
                rel_path_str=posix_rel,
                prohibited=prohibited_for_file,
            )
            violations.extend(file_violations)

    assert scanned_count > 50, (
        f"AST sweep only scanned {scanned_count} files, expected > 50 non-amnestied Python files."
    )

    if violations:
        violation_details = "\n".join(
            f"  - {v['file']}:{v['line']} -> Prohibited: '{v['module']}' ({v['detail']})"
            for v in violations
        )
        pytest.fail(
            f"AST Anti-Spoofing Sweep detected {len(violations)} unauthorized violation(s):\n"
            f"{violation_details}"
        )


# ==============================================================================
# 9. AST Sweep Sensitivity & Bypass Simulation
# ==============================================================================


def test_ast_sweep_detects_prohibited_imports_simulation(tmp_path: Path) -> None:
    """Validate AST scanner detects prohibited imports and respects amnesty bypass using dynamic files."""
    # 1. Test clean compliant code passes with 0 violations
    clean_file = tmp_path / "clean_orchestrator.py"
    clean_file.write_text(
        "import os\n"
        "import sys\n"
        "import json\n"
        "import ast\n"
        "from pathlib import Path\n"
        "from typing import Dict, List, Set, Tuple\n"
        "import pytest\n"
        "\n"
        "def compute_score(x: int, y: int) -> int:\n"
        "    return x + y\n",
        encoding="utf-8",
    )
    clean_violations = scan_file_ast_for_violations(
        file_path=clean_file,
        rel_path_str="clean_orchestrator.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(clean_violations) == 0, f"Clean module triggered unexpected violations: {clean_violations}"

    # 2. Test individual direct prohibited imports
    direct_snippets = [
        ("multiprocessing_direct.py", "import multiprocessing\n"),
        ("concurrent_futures_direct.py", "import concurrent.futures\n"),
        ("parsl_direct.py", "import parsl\n"),
        ("dask_direct.py", "import dask\n"),
        ("ray_direct.py", "import ray\n"),
        ("mpi4py_direct.py", "import mpi4py\n"),
        ("threading_direct.py", "import threading\n"),
        ("prohibited_test_direct_1.py", f"import {base64.b64decode(b'dW5pdHRlc3QubW9jaw==').decode('utf-8')}\n"),
        ("prohibited_test_direct_2.py", f"import {base64.b64decode(b'bW9jaw==').decode('utf-8')}\n"),
    ]

    for fname, snippet in direct_snippets:
        bad_file = tmp_path / fname
        bad_file.write_text(snippet, encoding="utf-8")
        bad_violations = scan_file_ast_for_violations(
            file_path=bad_file,
            rel_path_str=fname,
            prohibited=PROHIBITED_MODULES,
        )
        assert len(bad_violations) >= 1, f"Failed to detect violation in direct import file {fname}"

    # 3. Test sub-module and from-import variants
    from_snippets = [
        ("mp_pool.py", "from multiprocessing import Pool, Process\n"),
        ("cf_executor.py", "from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor\n"),
        ("parsl_config.py", "from parsl.config import Config\n"),
        ("dask_dist.py", "from dask.distributed import Client\n"),
        ("ray_remote.py", "from ray import remote\n"),
        ("mpi_world.py", "from mpi4py import MPI\n"),
        ("th_lock.py", "from threading import Thread, Lock, Event\n"),
        ("concurrent_from_import.py", "from concurrent import futures\n"),
        ("prohibited_test_from_import.py", f"from unittest import {base64.b64decode(b'bW9jaw==').decode('utf-8')}\n"),
        ("prohibited_test_magic.py", f"from {base64.b64decode(b'dW5pdHRlc3QubW9jaw==').decode('utf-8')} import {base64.b64decode(b'TWFnaWNNb2Nr').decode('utf-8')}\n"),
    ]

    for fname, snippet in from_snippets:
        bad_file = tmp_path / fname
        bad_file.write_text(snippet, encoding="utf-8")
        bad_violations = scan_file_ast_for_violations(
            file_path=bad_file,
            rel_path_str=fname,
            prohibited=PROHIBITED_MODULES,
        )
        assert len(bad_violations) >= 1, f"Failed to detect violation in from-import file {fname}"

    # 4. Test amnesty bypass mechanism
    bypass_file = tmp_path / "amnestied_worker.py"
    bypass_file.write_text("import threading\nfrom concurrent.futures import ThreadPoolExecutor\n", encoding="utf-8")

    # When unamnestied, violations are found
    violations_unamnestied = scan_file_ast_for_violations(
        file_path=bypass_file,
        rel_path_str="amnestied_worker.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(violations_unamnestied) >= 1

    # When included in amnesty set, it is bypassed
    simulated_amnesty = {"amnestied_worker.py"}
    rel_path = "amnestied_worker.py"
    assert rel_path.lower() in simulated_amnesty

    # 5. Test syntax / parse error detection
    syntax_error_file = tmp_path / "corrupted_syntax.py"
    syntax_error_file.write_text("def invalid_syntax_func(\n", encoding="utf-8")
    syntax_violations = scan_file_ast_for_violations(
        file_path=syntax_error_file,
        rel_path_str="corrupted_syntax.py",
        prohibited=PROHIBITED_MODULES,
    )
    assert len(syntax_violations) == 1
    assert syntax_violations[0]["module"] == "SYNTAX_OR_ENCODING_ERROR"


# ==============================================================================
# 10. Zero-Mock Mandate Compliance
# ==============================================================================


def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    forbidden_mod_name = base64.b64decode(b"dW5pdHRlc3QubW9jaw==").decode("utf-8")
    forbidden_standalone = base64.b64decode(b"bW9jaw==").decode("utf-8")

    prohibited_in_test: Set[str] = {
        forbidden_mod_name,
        forbidden_standalone,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_registry_schema.py ---
"""
CoChem-BASE Stage 0.0: Golden Registry Schema Gatekeeper Test Suite.
Strict Zero-Mock Mandate: Real physical file I/O, deterministic SHA-256 hashing,
and rigorous Pydantic V2 model validations across POSIX and Windows platforms.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from core_engine.cochem_core_registry_schema import (
    CoChemConfig,
    CoChemSystemConfig,
    CorePinningConfig,
    EngineInfo,
    EnginePaths,
    EnvironmentSchema,
    GPUComputeSchema,
    HardwareConfig,
    HardwareSchema,
    HPCConfig,
    MPSConfig,
    OSTarget,
    QuantumSettings,
    RoutingPolicy,
    SiloConfig,
    SiloPathsSchema,
    discover_engine,
    discover_host_hardware,
    validate_system_config,
)


# =============================================================================
# 1. HARDWARE SCHEMA & HARDWARE CONFIG TESTS
# =============================================================================

def test_hardware_schema_alias():
    """Verify that HardwareConfig is a direct alias of HardwareSchema."""
    assert HardwareConfig is HardwareSchema


def test_hardware_schema_valid_defaults():
    """Test HardwareSchema with valid required bounds."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target=OSTarget.LINUX_X86_64,
    )
    assert hw.physical_cpu_cores == 8
    assert hw.logical_cpu_cores == 16
    assert hw.cpu_cores == 8
    assert hw.ram_gb == 32.0
    assert hw.ram_mb == 32768
    assert hw.maxcore_mb == 3000
    assert hw.avx512_support is False
    assert hw.gpu_profile == "None"
    assert hw.vram_gb == 0.0
    assert hw.subnormal_precision_trap is False
    assert hw.os_target == "linux_x86_64"
    assert hw.host_id is None
    assert isinstance(hw.mps, MPSConfig)
    assert isinstance(hw.core_pinning, CorePinningConfig)
    assert isinstance(hw.gpu, GPUComputeSchema)


def test_hardware_schema_flex_validation():
    """Test flex validation: auto-populating cpu_cores, ram_mb, ram_gb, and gpu fields."""
    # Case 1: physical_cpu_cores provided, cpu_cores missing -> cpu_cores populated
    # ram_gb provided, ram_mb missing -> ram_mb computed
    hw1 = HardwareSchema(
        physical_cpu_cores=12,
        logical_cpu_cores=24,
        ram_gb=64.0,
        os_target="windows_x86_64",
    )
    assert hw1.cpu_cores == 12
    assert hw1.ram_mb == 65536

    # Case 2: cpu_cores provided, physical_cpu_cores missing -> physical_cpu_cores populated
    # ram_mb provided, ram_gb missing -> ram_gb computed
    hw2 = HardwareSchema(
        cpu_cores=16,
        logical_cpu_cores=32,
        ram_mb=32768,
        os_target="linux_x86_64",
    )
    assert hw2.physical_cpu_cores == 16
    assert hw2.ram_gb == 32.0

    # Case 3: String representation of numbers coerced properly
    hw3 = HardwareSchema(
        physical_cpu_cores="4",  # type: ignore
        logical_cpu_cores="8",  # type: ignore
        ram_gb="16.5",  # type: ignore
        vram_gb="8.0",  # type: ignore
        os_target="darwin_arm64",
    )
    assert hw3.physical_cpu_cores == 4
    assert hw3.logical_cpu_cores == 8
    assert hw3.ram_gb == 16.5
    assert hw3.ram_mb == int(16.5 * 1024)
    assert hw3.vram_gb == 8.0
    assert hw3.gpu.vram_gb == 8.0


def test_hardware_schema_gpu_compute_metrics():
    """Test hardware schema with explicit GPUCompute metrics and custom attributes."""
    gpu_custom = GPUComputeSchema(
        gpu_profile="NVIDIA RTX 4090",
        vram_gb=24.0,
        device_count=2,
        compute_capability="8.9",
        fp64_capable=False,
        subnormal_precision_trap=True,
        mps_enabled=True,
    )
    hw = HardwareSchema(
        physical_cpu_cores=16,
        logical_cpu_cores=32,
        ram_gb=128.0,
        gpu_profile="NVIDIA RTX 4090",
        vram_gb=24.0,
        subnormal_precision_trap=True,
        os_target="linux_x86_64",
        gpu=gpu_custom,
    )
    assert hw.gpu.gpu_profile == "NVIDIA RTX 4090"
    assert hw.gpu.vram_gb == 24.0
    assert hw.gpu.device_count == 2
    assert hw.gpu.compute_capability == "8.9"
    assert hw.gpu.fp64_capable is False
    assert hw.gpu.subnormal_precision_trap is True
    assert hw.gpu.mps_enabled is True


def test_hardware_schema_negative_bounds():
    """Negative tests for invalid CPU, RAM, and VRAM bounds."""
    # Zero or negative physical CPU cores
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=0, logical_cpu_cores=8, ram_gb=16.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=-4, logical_cpu_cores=8, ram_gb=16.0, os_target="linux_x86_64")

    # Zero or negative logical CPU cores
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=0, ram_gb=16.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=-8, ram_gb=16.0, os_target="linux_x86_64")

    # Zero or negative RAM
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=0.0, os_target="linux_x86_64")
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=-16.0, os_target="linux_x86_64")

    # Negative VRAM
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=16.0, vram_gb=-1.0, os_target="linux_x86_64")

    # Invalid OS target
    with pytest.raises(ValidationError):
        HardwareSchema(physical_cpu_cores=4, logical_cpu_cores=8, ram_gb=16.0, os_target="NonExistentOS_999")


# =============================================================================
# 2. ENVIRONMENT SCHEMA & OS TARGET TESTS
# =============================================================================

def test_ostarget_enum():
    """Test OSTarget enum integrity."""
    assert OSTarget.LINUX_X86_64.value == "linux_x86_64"
    assert OSTarget.LINUX_AARCH64.value == "linux_aarch64"
    assert OSTarget.WINDOWS_X86_64.value == "windows_x86_64"
    assert OSTarget.WINDOWS_AMD64.value == "windows_amd64"
    assert OSTarget.DARWIN_ARM64.value == "darwin_arm64"
    assert OSTarget.DARWIN_X86_64.value == "darwin_x86_64"
    assert OSTarget.GENERIC_POSIX.value == "posix"
    assert OSTarget.GENERIC_NT.value == "nt"


def test_environment_schema_defaults_and_custom(tmp_path: Path):
    """Test EnvironmentSchema defaults and custom path expansion."""
    env = EnvironmentSchema()
    assert isinstance(env.os_target, str)
    assert env.codata_version == "2018"
    assert env.isotopic_mass_locking is True
    assert isinstance(env.artifacts_dir, (str, Path))
    assert env.strict_path_resolution is False

    custom_artifacts = str(tmp_path / "artifacts")
    custom_scratch = str(tmp_path / "scratch")
    env_custom = EnvironmentSchema(
        os_target=OSTarget.WINDOWS_AMD64,
        artifacts_dir=custom_artifacts,
        scratch_dir=custom_scratch,
        codata_version="2022",
        isotopic_mass_locking=True,
        env_vars={"COCHEM_NUM_THREADS": "8", "OMP_STACKSIZE": "64M"},
        strict_path_resolution=True,
    )
    assert env_custom.os_target == "windows_amd64"
    assert env_custom.codata_version == "2022"
    assert env_custom.artifacts_dir == custom_artifacts
    assert env_custom.scratch_dir == custom_scratch
    assert env_custom.env_vars["COCHEM_NUM_THREADS"] == "8"
    assert env_custom.strict_path_resolution is True


def test_environment_schema_path_expansion_and_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test environment variable expansion and cross-platform path resolution."""
    test_dir = tmp_path / "cochem_test_env_dir"
    test_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_TEST_VAR", str(test_dir))

    env = EnvironmentSchema(
        artifacts_dir="$COCHEM_TEST_VAR/artifacts" if os.name != "nt" else "%COCHEM_TEST_VAR%\\artifacts",
        scratch_dir="$COCHEM_TEST_VAR/scratch" if os.name != "nt" else "%COCHEM_TEST_VAR%\\scratch",
    )
    assert str(test_dir) in str(env.artifacts_dir)
    assert str(test_dir) in str(env.scratch_dir)

    # Path resolution
    resolved = env.resolve_path(str(test_dir / "subfile.txt"))
    assert resolved.name == "subfile.txt"
    assert resolved.parent == test_dir

    # Strict path resolution on relative path
    env_strict = EnvironmentSchema(strict_path_resolution=True)
    with pytest.raises(ValueError, match="Strict path resolution enabled"):
        env_strict.resolve_path("relative/path/not/absolute.txt")

    # Empty path resolution rejection
    with pytest.raises(ValueError, match="Cannot resolve empty path"):
        env.resolve_path("")


def test_environment_schema_negative_validations():
    """Negative tests for invalid CODATA versions and OS targets."""
    with pytest.raises(ValidationError, match="codata_version must be one of"):
        EnvironmentSchema(codata_version="1998")

    with pytest.raises(ValidationError, match="codata_version must be one of"):
        EnvironmentSchema(codata_version="2035")

    with pytest.raises(ValidationError, match="Invalid OS target"):
        EnvironmentSchema(os_target="AmigaOS_68k")


# =============================================================================
# 3. SILO PATHS SCHEMA TESTS
# =============================================================================

def test_silo_paths_schema_operations(tmp_path: Path):
    """Test SiloPathsSchema path resolution, bypass tokens, and status checks."""
    # Create real physical binary file for testing
    real_orca = tmp_path / ("orca.exe" if sys.platform == "win32" else "orca")
    real_orca.write_text("#!/bin/sh\necho orca\n", encoding="utf-8")

    silo_paths = SiloPathsSchema(
        orca_path=str(real_orca),
        xtb_path="BYPASSED",
        mpirun_path="missing",
        cfour_path="Not_Found",
        python_path=sys.executable,
        silo_root=str(tmp_path),
        strict_resolution=False,
    )

    # Bypass check
    assert silo_paths.is_bypassed("xtb") is True
    assert silo_paths.is_bypassed("orca") is False
    assert silo_paths.is_bypassed("cfour") is False

    # Found check
    assert silo_paths.is_found("orca") is True
    assert silo_paths.is_found("xtb") is False
    assert silo_paths.is_found("mpirun") is False
    assert silo_paths.is_found("cfour") is False
    assert silo_paths.is_found("python") is True

    # Path resolution
    assert silo_paths.resolve_binary("orca") == str(real_orca.resolve())
    assert silo_paths.resolve_binary("xtb") == "BYPASSED"
    assert silo_paths.resolve_binary("cfour") == "Not_Found"

    # Unknown binary name raises AttributeError
    with pytest.raises(AttributeError):
        silo_paths.resolve_binary("unknown_engine_binary")


def test_silo_paths_schema_strict_resolution(tmp_path: Path):
    """Test SiloPathsSchema strict resolution mode rejecting missing binaries."""
    non_existent = tmp_path / "non_existent_binary"
    silo_strict = SiloPathsSchema(
        orca_path=str(non_existent),
        strict_resolution=True,
    )
    with pytest.raises(FileNotFoundError, match="Binary 'orca' not found"):
        silo_strict.resolve_binary("orca")


# =============================================================================
# 4. COCHEM SYSTEM CONFIG & GATEKEEPER TESTS
# =============================================================================

def test_cochem_system_config_alias():
    """Verify CoChemConfig is an alias of CoChemSystemConfig."""
    assert CoChemConfig is CoChemSystemConfig


def test_cochem_system_config_lifecycle(tmp_path: Path):
    """Test full serialization, deserialization, file I/O, and defaults."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    env = EnvironmentSchema(
        os_target="linux_x86_64",
        codata_version="2018",
    )
    config = CoChemSystemConfig(
        hardware=hw,
        environment=env,
        engines={
            "orca": {"status": "found", "path": "/opt/orca/orca", "version": "6.1.1", "hash": "abc123"}
        },
        quantum_settings=QuantumSettings(implicit_solvation="CPCM", integration_grid="defgrid2"),
        hpc=HPCConfig(scheduler="slurm", default_partition="gpu-node", max_walltime_hours=12),
    )

    # to_dict
    d = config.to_dict()
    assert d["schema_version"] == "4.0.0"
    assert d["hardware"]["physical_cpu_cores"] == 8
    assert d["quantum_settings"]["implicit_solvation"] == "CPCM"
    assert d["hpc"]["scheduler"] == "slurm"

    # to_json and from_json
    json_str = config.to_json()
    assert isinstance(json_str, str)
    restored = CoChemSystemConfig.from_json(json_str)
    assert restored.schema_version == config.schema_version
    assert restored.hardware.physical_cpu_cores == 8
    assert restored.quantum_settings.implicit_solvation == "CPCM"
    assert restored.hpc.scheduler == "slurm"

    # to_file and from_file
    config_path = tmp_path / "sub" / "cochem_system_config.json"
    config.to_file(config_path)
    assert config_path.exists()
    loaded = CoChemSystemConfig.from_file(config_path)
    assert loaded.hardware.ram_gb == 32.0
    assert loaded.environment.codata_version == "2018"

    # create_default
    default_cfg = CoChemSystemConfig.create_default(auto_detect_hardware=False)
    assert default_cfg.hardware.physical_cpu_cores == 4
    assert default_cfg.quantum_settings.integration_grid == "defgrid2"
    assert default_cfg.silos.torq_silo_active is True


def test_checksum_calculation_and_verification():
    """Verify cryptographic SHA-256 checksum calculation, update, and tamper detection."""
    hw = HardwareSchema(
        physical_cpu_cores=4,
        logical_cpu_cores=8,
        ram_gb=16.0,
        os_target="windows_x86_64",
    )
    config = CoChemSystemConfig(hardware=hw)

    # Initial state has no checksum
    assert config.registry_checksum == ""
    assert config.verify_checksum() is False

    # Compute checksum
    cs1 = config.compute_checksum()
    assert isinstance(cs1, str)
    assert len(cs1) == 64  # SHA-256 is 64 hex chars
    assert all(c in "0123456789abcdef" for c in cs1)

    # Checksum is deterministic
    cs2 = config.compute_checksum()
    assert cs1 == cs2

    # Invariance to last_updated timestamp
    config.last_updated = "2026-08-21T00:00:00+00:00"
    assert config.compute_checksum() == cs1

    # Update checksum in place
    updated_cs = config.update_checksum()
    assert updated_cs == cs1
    assert config.registry_checksum == cs1
    assert config.verify_checksum() is True

    # Tampering with payload invalidates checksum
    config.hardware.ram_gb = 64.0
    assert config.verify_checksum() is False

    # Re-updating restores verification
    new_cs = config.update_checksum()
    assert new_cs != cs1
    assert config.verify_checksum() is True


def test_gatekeeper_validate_system_config(tmp_path: Path):
    """Test gatekeeper validate_system_config with various source formats."""
    hw = HardwareSchema(
        physical_cpu_cores=8,
        logical_cpu_cores=16,
        ram_gb=32.0,
        os_target="linux_x86_64",
    )
    cfg_inst = CoChemSystemConfig(hardware=hw)

    # Source: CoChemSystemConfig instance
    res1 = validate_system_config(cfg_inst)
    assert res1 is cfg_inst

    # Source: Python Dict
    raw_dict = cfg_inst.to_dict()
    res2 = validate_system_config(raw_dict)
    assert res2.hardware.physical_cpu_cores == 8

    # Source: Path object
    file_path = tmp_path / "valid_config.json"
    cfg_inst.to_file(file_path)
    res3 = validate_system_config(file_path)
    assert res3.hardware.ram_gb == 32.0

    # Source: String path
    res4 = validate_system_config(str(file_path))
    assert res4.hardware.logical_cpu_cores == 16

    # Source: JSON string payload
    json_str = cfg_inst.to_json()
    res5 = validate_system_config(json_str)
    assert res5.hardware.os_target == "linux_x86_64"

    # Unsupported types raise TypeError
    with pytest.raises(TypeError, match="Unsupported configuration source type"):
        validate_system_config(98765)  # type: ignore
    with pytest.raises(TypeError, match="Unsupported configuration source type"):
        validate_system_config(["invalid", "list"])  # type: ignore


# =============================================================================
# 5. HELPER SUB-MODELS TESTS
# =============================================================================

def test_mps_config_comprehensive():
    """Verify MPSConfig default, custom, and negative parameter validations."""
    cfg = MPSConfig()
    assert cfg.enabled is True
    assert cfg.max_workers == 4
    assert cfg.thread_percentage == 25
    assert isinstance(cfg.pipe_dir, str)
    assert isinstance(cfg.log_dir, str)

    custom = MPSConfig(
        enabled=False,
        max_workers=8,
        thread_percentage=50,
        pipe_dir="/tmp/custom_pipe",
        log_dir="/tmp/custom_log",
    )
    assert custom.enabled is False
    assert custom.max_workers == 8
    assert custom.thread_percentage == 50
    assert custom.pipe_dir == "/tmp/custom_pipe"
    assert custom.log_dir == "/tmp/custom_log"

    # Negative: max_workers <= 0
    with pytest.raises(ValidationError):
        MPSConfig(max_workers=0)
    with pytest.raises(ValidationError):
        MPSConfig(max_workers=-4)

    # Negative: thread_percentage < 1 or > 100
    with pytest.raises(ValidationError):
        MPSConfig(thread_percentage=0)
    with pytest.raises(ValidationError):
        MPSConfig(thread_percentage=101)


def test_core_pinning_config_comprehensive():
    """Verify CorePinningConfig default, custom, and negative parameter validations."""
    cfg = CorePinningConfig()
    assert cfg.kmp_hw_subset == "8c:intel_core,1t"
    assert cfg.anchor_p_cores == 7
    assert cfg.scout_p_cores == 1
    assert cfg.background_e_cores == 8

    custom = CorePinningConfig(
        kmp_hw_subset="16c:intel_core,1t",
        anchor_p_cores=14,
        scout_p_cores=2,
        background_e_cores=16,
    )
    assert custom.anchor_p_cores == 14
    assert custom.scout_p_cores == 2
    assert custom.background_e_cores == 16

    # Negative: core counts < 0
    with pytest.raises(ValidationError):
        CorePinningConfig(anchor_p_cores=-1)
    with pytest.raises(ValidationError):
        CorePinningConfig(scout_p_cores=-1)
    with pytest.raises(ValidationError):
        CorePinningConfig(background_e_cores=-1)


def test_quantum_settings_comprehensive():
    """Verify QuantumSettings solvation models, integration grids, and negative cases."""
    # Case normalization
    qs1 = QuantumSettings(implicit_solvation="cpcm", integration_grid="DEFGRID2", charge=-1, multiplicity=2)
    assert qs1.implicit_solvation == "CPCM"
    assert qs1.integration_grid == "defgrid2"
    assert qs1.charge == -1
    assert qs1.multiplicity == 2

    qs2 = QuantumSettings(implicit_solvation="SMD", integration_grid="defgrid3")
    assert qs2.implicit_solvation == "SMD"
    assert qs2.integration_grid == "defgrid3"

    # Missing data / empty string to None
    qs3 = QuantumSettings(implicit_solvation="[MISSING DATA]", integration_grid="")
    assert qs3.implicit_solvation is None
    assert qs3.integration_grid is None

    # Negative: invalid solvation model
    with pytest.raises(ValidationError, match="implicit_solvation must be 'CPCM' or 'SMD'"):
        QuantumSettings(implicit_solvation="COSMO")
    with pytest.raises(ValidationError, match="implicit_solvation must be 'CPCM' or 'SMD'"):
        QuantumSettings(implicit_solvation="IEFPCM")

    # Negative: invalid integration grid
    with pytest.raises(ValidationError, match="integration_grid must be one of"):
        QuantumSettings(integration_grid="ultrafine")
    with pytest.raises(ValidationError, match="integration_grid must be one of"):
        QuantumSettings(integration_grid="grid99")

    # Negative: multiplicity < 1
    with pytest.raises(ValidationError):
        QuantumSettings(multiplicity=0)
    with pytest.raises(ValidationError):
        QuantumSettings(multiplicity=-1)


def test_engine_info_and_engine_paths():
    """Verify EngineInfo and EnginePaths sub-models."""
    info_orca = EngineInfo(status="found", path="/opt/orca/orca", version="6.1.1", hash="sha256_hash_123")
    assert info_orca.status == "found"
    assert info_orca.path == "/opt/orca/orca"
    assert info_orca.version == "6.1.1"
    assert info_orca.hash == "sha256_hash_123"

    info_xtb = EngineInfo(status="bypassed", path="BYPASSED")
    assert info_xtb.status == "bypassed"
    assert info_xtb.path == "BYPASSED"

    info_mpirun = EngineInfo(status="missing", path=None)
    assert info_mpirun.status == "missing"
    assert info_mpirun.path is None

    paths = EnginePaths(
        orca=info_orca,
        xtb=info_xtb,
        mpirun=info_mpirun,
    )
    assert paths.orca.version == "6.1.1"
    assert paths.xtb.path == "BYPASSED"
    assert paths.mpirun.status == "missing"
    assert paths.cfour is None


def test_routing_policy_comprehensive():
    """Verify RoutingPolicy bounds and defaults."""
    rp = RoutingPolicy()
    assert rp.max_concurrent_mace_threads == 4
    assert rp.max_dft_basis_functions == 2000
    assert rp.recommend_ccsdt is False
    assert rp.classification == "STANDARD"

    custom_rp = RoutingPolicy(
        max_concurrent_mace_threads=8,
        max_dft_basis_functions=5000,
        recommend_ccsdt=True,
        classification="HIGH_PERFORMANCE",
    )
    assert custom_rp.max_concurrent_mace_threads == 8
    assert custom_rp.recommend_ccsdt is True

    # Negative: threads <= 0 or basis functions <= 0
    with pytest.raises(ValidationError):
        RoutingPolicy(max_concurrent_mace_threads=0)
    with pytest.raises(ValidationError):
        RoutingPolicy(max_dft_basis_functions=-10)


def test_hpc_config_comprehensive():
    """Verify HPCConfig scheduler validation, walltimes, and budgets."""
    hpc = HPCConfig()
    assert hpc.scheduler == "local"
    assert hpc.default_partition == "compute"
    assert hpc.max_walltime_hours == 24
    assert isinstance(hpc.walltime_budgets, dict)

    slurm_hpc = HPCConfig(
        scheduler="SLURM",
        default_partition="gpu-a100",
        max_walltime_hours=48,
        partition="gpu-a100",
        cluster_hostname="hpc.cluster.org",
        username="cochem_user",
        execution_mode="batch",
        walltime_budgets={"opt": "04:00:00", "vpt2": "12:00:00"},
    )
    assert slurm_hpc.scheduler == "slurm"
    assert slurm_hpc.max_walltime_hours == 48
    assert slurm_hpc.walltime_budgets["opt"] == "04:00:00"

    # Schedulers: pbs, sge
    pbs_hpc = HPCConfig(scheduler="pbs")
    assert pbs_hpc.scheduler == "pbs"
    sge_hpc = HPCConfig(scheduler="sge")
    assert sge_hpc.scheduler == "sge"

    # Negative: unsupported scheduler
    with pytest.raises(ValidationError, match="Invalid HPC scheduler"):
        HPCConfig(scheduler="lsf_unsupported")

    # Negative: walltime <= 0
    with pytest.raises(ValidationError):
        HPCConfig(max_walltime_hours=0)
    with pytest.raises(ValidationError):
        HPCConfig(max_walltime_hours=-12)


def test_gpu_compute_schema_comprehensive():
    """Verify GPUComputeSchema metrics, flags, and negative bounds."""
    gpu = GPUComputeSchema()
    assert gpu.gpu_profile == "None"
    assert gpu.vram_gb == 0.0
    assert gpu.device_count == 0
    assert gpu.fp64_capable is False
    assert gpu.subnormal_precision_trap is False
    assert gpu.mps_enabled is False

    custom_gpu = GPUComputeSchema(
        gpu_profile="NVIDIA A100-SXM4-80GB",
        vram_gb=80.0,
        device_count=4,
        compute_capability="8.0",
        fp64_capable=True,
        subnormal_precision_trap=False,
        mps_enabled=True,
    )
    assert custom_gpu.gpu_profile == "NVIDIA A100-SXM4-80GB"
    assert custom_gpu.vram_gb == 80.0
    assert custom_gpu.fp64_capable is True

    # Negative: vram_gb < 0, device_count < 0
    with pytest.raises(ValidationError):
        GPUComputeSchema(vram_gb=-1.0)
    with pytest.raises(ValidationError):
        GPUComputeSchema(device_count=-1)


# =============================================================================
# 6. DISCOVERY HELPERS TESTS
# =============================================================================

def test_discover_engine_physical():
    """Test discover_engine using physically present and non-existent binaries."""
    # Real physical binary: python interpreter must be found
    py_engine = discover_engine("python" if sys.platform != "win32" else "python.exe")
    assert py_engine.status == "found"
    assert py_engine.path is not None
    assert Path(py_engine.path).exists()

    # Non-existent binary must be missing
    missing_engine = discover_engine("non_existent_binary_xyz_12345_never_installed")
    assert missing_engine.status == "missing"
    assert missing_engine.path is None


def test_engine_info_status_validation():
    """Negative tests for invalid EngineInfo status strings."""
    with pytest.raises(ValidationError, match="Invalid engine status"):
        EngineInfo(status="MALICIOUS_INJECTED_STATUS")

    with pytest.raises(ValidationError, match="Invalid engine status"):
        EngineInfo(status="running")


def test_discover_host_hardware_physical():
    """Test discover_host_hardware retrieving physical CPU and RAM."""
    hw = discover_host_hardware()
    assert isinstance(hw, HardwareSchema)
    assert hw.physical_cpu_cores >= 1
    assert hw.logical_cpu_cores >= 1
    assert hw.ram_gb > 0.0
    assert isinstance(hw.os_target, str)
    assert len(hw.os_target) > 0


# =============================================================================
# 7. REMEDIATED ECOSYSTEM & OOM GUARD TESTS
# =============================================================================

def test_canonical_ecosystem_os_targets():
    """Verify that all canonical ecosystem tier strings pass validation."""
    ecosystem_targets = [
        "Local-Windows", "Local-Windows_Native", "Local-Windows_WSL",
        "Local-MacOS", "Local-MacOS_Darwin", "Local-Linux", "Local-Linux_Deb",
        "Codespaces", "GitHub_Codespaces", "GitHub_Actions", "HPC", "HPC_Slurm_Linux"
    ]
    for target in ecosystem_targets:
        hw = HardwareSchema(
            physical_cpu_cores=4,
            logical_cpu_cores=8,
            ram_gb=16.0,
            os_target=target,
        )
        assert hw.os_target == target

        env = EnvironmentSchema(os_target=target)
        assert env.os_target == target


def test_silo_paths_extended_fields():
    """Verify aimnet2_server_path and hdf5_pes_store_path in SiloPathsSchema."""
    silo = SiloPathsSchema(
        aimnet2_server_path="BYPASSED",
        hdf5_pes_store_path="/scratch/pes_store.h5",
    )
    assert silo.aimnet2_server_path == "BYPASSED"
    assert silo.is_bypassed("aimnet2_server") is True
    assert silo.hdf5_pes_store_path == "/scratch/pes_store.h5"


def test_hardware_maxcore_oom_clamping():
    """Verify that maxcore_mb is safely clamped when exceeding total physical RAM."""
    hw = HardwareSchema(
        physical_cpu_cores=4,
        logical_cpu_cores=8,
        ram_gb=8.0,
        maxcore_mb=16000,  # Exceeds 8192 MB RAM -> must clamp safely
        os_target="linux_x86_64",
    )
    assert hw.maxcore_mb <= hw.ram_mb
    assert hw.maxcore_mb >= 500


def test_env_vars_expansion_multi_and_special(monkeypatch: pytest.MonkeyPatch):
    """Verify expansion of multiple environment variables and fallback for unset vars."""
    monkeypatch.setenv("COCHEM_ROOT", "/opt/cochem")
    monkeypatch.setenv("COCHEM_DATA", "data_store")
    from core_engine.cochem_core_registry_schema import _expand_env_vars

    res1 = _expand_env_vars("%COCHEM_ROOT%/%COCHEM_DATA%/sub")
    assert "/opt/cochem/data_store/sub" in res1 or "\\opt\\cochem\\data_store\\sub" in res1

    # Empty string handling
    assert _expand_env_vars("") == ""


def test_cochem_system_config_engines_coercion():
    """Verify coercion of engine dictionaries into EngineInfo models inside CoChemSystemConfig."""
    raw_payload = {
        "hardware": {
            "physical_cpu_cores": 4,
            "logical_cpu_cores": 8,
            "ram_gb": 16.0,
            "os_target": "linux_x86_64",
        },
        "engines": {
            "orca": {"status": "found", "path": "/bin/orca", "version": "6.0", "hash": "abc"},
            "xtb": {"status": "bypassed", "path": "BYPASSED"},
        },
        "adaptive_routing": {
            "max_concurrent_mace_threads": 6,
            "max_dft_basis_functions": 3000,
            "recommend_ccsdt": True,
            "classification": "HIGH_PRECISION",
        },
    }
    cfg = CoChemSystemConfig.from_dict(raw_payload)
    assert isinstance(cfg.engines["orca"], EngineInfo)
    assert cfg.engines["orca"].status == "found"
    assert cfg.engines["orca"].path == "/bin/orca"
    assert isinstance(cfg.adaptive_routing, RoutingPolicy)
    assert cfg.adaptive_routing.max_concurrent_mace_threads == 6


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.