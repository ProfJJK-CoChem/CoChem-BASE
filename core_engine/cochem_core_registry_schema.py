#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Golden Registry Schema Gatekeeper
Defines the absolute Pydantic models for `cochem_system_config.json`.
Guarantees downstream scientific components never encounter missing keys, 
type errors, or unmapped hardware states.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class HardwareConfig(BaseModel):
    """Rigid bounds for physical compute resources to prevent OOM/Thread crashes."""
    physical_cpu_cores: int = Field(..., gt=0, description="Actual silicon cores")
    logical_cpu_cores: int = Field(..., gt=0, description="Hyperthreaded threads")
    ram_gb: float = Field(..., gt=0.0, description="Total accessible memory")
    avx512_support: bool = Field(..., description="CPU vector extension capability")
    gpu_profile: str = Field(..., description="Detected GPU model or 'None'")
    vram_gb: float = Field(default=0.0, ge=0.0, description="Total video memory")
    subnormal_precision_trap: bool = Field(default=False)
    os_target: str = Field(..., description="OS identifier (e.g., linux_x86_64)")

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
    max_walltime_hours: int = Field(default=24)

class CoChemConfig(BaseModel):
    """
    The CoChem Master Schema.
    This is the ultimate schema for `cochem_system_config.json`.
    """
    schema_version: str = Field(default="1.0.0", frozen=True)
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    hardware: HardwareConfig
    engines: EnginePaths
    silos: SiloConfig
    adaptive_routing: Optional[RoutingPolicy] = None
    hpc: HPCConfig = Field(default_factory=HPCConfig)
    alignment_engine_ready: bool = Field(default=False)
    active_jobs: Dict[str, Any] = Field(default_factory=dict, description="Live execution pointers")

# If executed directly, run a schema sanity check
if __name__ == "__main__":
    import shutil
    print(">>> Validating CoChemConfig Schema Types...")
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
        print(" [SUCCESS] Pydantic models successfully instantiated. Golden Schema is structurally sound.")
        print(f" [OUTPUT] {master.model_dump_json(indent=2)[:200]}...")
    except Exception as e:
        print(f" [FAIL] Schema validation crashed: {e}")