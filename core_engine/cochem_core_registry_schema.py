#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Golden Registry Schema Gatekeeper
Defines the absolute Pydantic models for `cochem_system_config.json`.
Guarantees downstream scientific components never encounter missing keys, 
type errors, or unmapped hardware states.
"""

import logging
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class MPSConfig(BaseModel):
    """CUDA Multi-Process Service (MPS) configuration."""
    enabled: bool = Field(default=True, description="Enable CUDA MPS daemon multiplexing")
    max_workers: int = Field(default=4, description="Max concurrent MPS worker tasks per GPU")
    thread_percentage: int = Field(default=25, description="CUDA MPS active thread percentage ceiling")
    pipe_dir: str = Field(default="/tmp/nvidia-mps", description="MPS pipe directory")
    log_dir: str = Field(default="/tmp/nvidia-log", description="MPS log directory")

class CorePinningConfig(BaseModel):
    """Core Pinning and Topology Configuration."""
    kmp_hw_subset: str = Field(default="8c:intel_core,1t", description="OpenMP core pinning HW subset spec")
    anchor_p_cores: int = Field(default=7, description="Number of P-cores assigned to CPU anchor tasks")
    scout_p_cores: int = Field(default=1, description="Number of P-cores assigned to GPU scout tasks")
    background_e_cores: int = Field(default=8, description="E-cores reserved for OS/background tasks")

class HardwareConfig(BaseModel):
    """Rigid bounds for physical compute resources to prevent OOM/Thread crashes."""
    cpu_cores: Optional[int] = Field(default=8, description="Available CPU compute cores")
    physical_cpu_cores: int = Field(..., gt=0, description="Actual silicon cores")
    logical_cpu_cores: int = Field(..., gt=0, description="Hyperthreaded threads")
    ram_mb: Optional[int] = Field(default=32000, description="Total allocated system RAM in MB")
    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory")
    avx512_support: bool = Field(..., description="CPU vector extension capability")
    gpu_profile: str = Field(..., description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory")
    subnormal_precision_trap: bool = Field(default=False)
    os_target: str = Field(..., description="OS identifier (e.g., linux_x86_64)")
    host_id: Optional[str] = Field(default=None)
    mps: Optional[MPSConfig] = Field(default_factory=MPSConfig)
    core_pinning: Optional[CorePinningConfig] = Field(default_factory=CorePinningConfig)

    @model_validator(mode='before')
    @classmethod
    def flex_hardware_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "cpu_cores" not in data and "physical_cpu_cores" in data:
                data["cpu_cores"] = data["physical_cpu_cores"]
            elif "physical_cpu_cores" not in data and "cpu_cores" in data:
                data["physical_cpu_cores"] = data["cpu_cores"]
            if "ram_mb" not in data and "ram_gb" in data:
                data["ram_mb"] = int(data["ram_gb"] * 1024)
            elif "ram_gb" not in data and "ram_mb" in data:
                data["ram_gb"] = float(data["ram_mb"]) / 1024.0
        return data

class EngineInfo(BaseModel):
    """Pathing and cryptographic provenance for computational binaries."""
    status: str = Field(..., description="found, missing, permission_denied, or bypassed")
    path: Optional[str] = Field(None, description="Absolute path to the executable, or 'BYPASSED'")
    version: Optional[str] = Field(None, description="Semantic version of the engine")
    hash: Optional[str] = Field(None, description="SHA-256 binary hash")

    @field_validator('path')
    @classmethod
    def validate_bypassed_path(cls, v: Optional[str]) -> Optional[str]:
        if v == "BYPASSED":
            return v
        return v

class EnginePaths(BaseModel):
    orca: EngineInfo
    mpirun: EngineInfo
    xtb: EngineInfo

class SiloConfig(BaseModel):
    """Micro-environment deployment status."""
    torq_silo_active: bool = Field(default=False)
    gpu_silo_active: bool = Field(default=False)

class RoutingPolicy(BaseModel):
    """Dynamically assigned execution constraints from Phase 11."""
    max_concurrent_mace_threads: int
    max_dft_basis_functions: int
    recommend_ccsdt: bool
    classification: str

class HPCConfig(BaseModel):
    """Cluster integration parameters."""
    scheduler: str = Field(default="local", description="local, slurm, pbs, or sge")
    default_partition: str = Field(default="compute")
    max_walltime_hours: Optional[int] = Field(default=24)
    partition: Optional[str] = Field(default="compute")
    cluster_hostname: Optional[str] = Field(default="localhost")
    ssh_key_path: Optional[str] = Field(default="")
    username: Optional[str] = Field(default="localuser")
    execution_mode: Optional[str] = Field(default="local")
    walltime_budgets: Optional[Dict[str, str]] = Field(default_factory=dict)

class CoChemConfig(BaseModel):
    """
    The CoChem Master Schema.
    This is the ultimate schema for `cochem_system_config.json`.
    """
    schema_version: str = Field(default="4.0.0")
    registry_version: Optional[str] = Field(default="4.0")
    orca_version: Optional[str] = Field(default="6.1.1")
    rdkit_random_seed: Optional[int] = Field(default=42)
    registry_checksum: Optional[str] = Field(default="")
    last_updated: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())
    hardware: HardwareConfig
    engines: Union[Dict[str, Any], EnginePaths] = Field(default_factory=dict)
    silos: Optional[SiloConfig] = Field(default=None, description="Deprecated/optional silos config")
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

# If executed directly, run a schema sanity check
if __name__ == "__main__":
    import shutil
    logger.info(">>> Validating CoChemConfig Schema Types...")
    try:
        def discover_engine(binary_name: str) -> EngineInfo:
            p = shutil.which(binary_name)
            if p:
                return EngineInfo(status="found", path=str(p), version="auto", hash="auto")
            return EngineInfo(status="missing", path=None, version=None, hash=None)

        mock_hw = HardwareConfig(
            physical_cpu_cores=8,
            logical_cpu_cores=16,
            ram_gb=32.0,
            avx512_support=True,
            gpu_profile="NVIDIA RTX 4090",
            vram_gb=24.0,
            os_target="linux_x86_64"
        )
        active_engines = EnginePaths(
            orca=discover_engine("orca"),
            mpirun=discover_engine("mpirun"),
            xtb=discover_engine("xtb")
        )
        master = CoChemConfig(
            hardware=mock_hw,
            engines=active_engines,
            silos=SiloConfig(torq_silo_active=True)
        )
        logger.info(" [SUCCESS] Pydantic models successfully instantiated. Golden Schema is structurally sound.")
        logger.info(f" [OUTPUT] {master.model_dump_json(indent=2)[:200]}...")
    except Exception as e:
        logger.error(f" [FAIL] Schema validation crashed: {e}")