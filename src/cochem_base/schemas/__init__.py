"""
CoChem Ecosystem Authoritative Pydantic Data Schemas.
Compliant with Method Matrix v4, FAIR Data Standards, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator


from cochem_base.schemas.quantum import (
    ConformerEnsemblePayload,
    ConstraintPayload,
    CounterpoiseResult,
    GradientPayload,
    QuantumJobSpec,
)


# =====================================================================
# Chunk 6 Ecosystem Schemas (Suggestions #51-#60)
# =====================================================================

from typing import Literal


class ActiveLearningBatchConfig(BaseModel):
    """Configuration for sequential furthest-point repulsion active learning batch selection. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    batch_size: int = Field(default=32, ge=1, le=512)
    repulsion_length_scale: float = Field(
        default=0.5,
        gt=0.0,
        alias="repulsion_radius",
        description="Spatial repulsion radius sigma_repulse in Angstroms",
    )
    diversity_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    kernel_type: Literal["gaussian", "morse"] = "gaussian"


class HardwareTelemetryReport(BaseModel):
    """Authentic live hardware telemetry report queried from OS and GPU driver. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_count: int = Field(ge=0)
    gpu_available: bool
    device_name: str
    vram_total_mb: float = Field(ge=0.0)
    vram_free_mb: float = Field(ge=0.0)
    selected_runtime: Literal["cuda", "mps", "cpu", "onnx_cpu"]
    provenance: str = Field(default="[M]", description="W3C provenance tag [M]")


class ANI2xCutoffConfig(BaseModel):
    """Configuration for ANI-2x continuous radial envelope and self-interaction diagonal masking. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius: float = Field(default=5.2, gt=1.0, le=10.0, description="Radial cutoff in Angstroms")
    envelope_type: Literal["cosine", "quintic"] = "cosine"
    mask_self_interactions: bool = True


class ConformalCalibrationConfig(BaseModel):
    """Configuration for split-conformal prediction calibration and quantile evaluation. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    significance_level: float = Field(default=0.05, gt=0.0, lt=1.0)
    hypothesis_scope: Literal["marginal", "atomwise_bonferroni", "atomwise_marginal"] = "marginal"
    min_calibration_observations: int = Field(
        default=50,
        ge=20,
        description="Must satisfy n >= ceil((1 - alpha) / alpha) to guarantee valid quantile evaluation",
    )


class ForceMatchingLossConfig(BaseModel):
    """Configuration for multi-task energy and force Huber matching loss normalization. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    energy_weight: float = Field(default=1.0, ge=0.0)
    force_weight: float = Field(default=10.0, ge=0.0)
    huber_delta_energy: float = Field(default=0.01, gt=0.0)
    huber_delta_force: float = Field(default=0.05, gt=0.0)
    normalization_mode: Literal["atom_norm", "coordinate_component"] = "atom_norm"
    virial_weight: float = Field(default=0.0, ge=0.0)


class GoatExploreDaemonConfig(BaseModel):
    """Configuration for persistent ORCA GOAT-EXPLORE daemon and stochastic hopping. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    socket_path: str
    scratch_dir: str
    max_hopping_steps: int = Field(default=100, ge=1)
    tight_opt_threshold: bool = True
    rmsd_dedup_threshold: float = Field(default=0.15, gt=0.0)


class PipSymmetryConfig(BaseModel):
    """Configuration for Permutation Invariant Polynomial (PIP) closed subgroup orbit averaging. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_symmetric_order: int = Field(
        default=120,
        ge=2,
        description="Upper bound before invoking subgroup orbit averaging",
    )
    subgroup_type: Literal["full", "alternating", "automorphism_wreath"] = "automorphism_wreath"
    invariance_tolerance: float = Field(
        default=1e-14,
        gt=0.0,
        description="Permutation invariance tolerance in Eh",
    )


class KrrRegularizationConfig(BaseModel):
    """Configuration for Kernel Ridge Regression condition-number floor and diagonal Tikhonov jitter. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_alpha: float = Field(default=1e-6, gt=0.0)
    anchor_alpha_floor: float = Field(default=1e-8, gt=0.0)
    jitter_epsilon: float = Field(default=1e-9, gt=0.0)
    max_jitter_escalation: float = Field(default=1e-6, gt=0.0)


class DeltaMLDispersionConfig(BaseModel):
    """Configuration for Becke-Johnson damped D3 dispersion baseline augmentation in Delta-ML. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    use_d3_dispersion: bool = True
    damping_scheme: Literal["bj", "zero"] = "bj"
    s6_scale: float = Field(default=1.0, ge=0.0)
    s8_scale: float = Field(default=0.0, ge=0.0)


# =====================================================================
# Chunk 7 Ecosystem Schemas (Suggestions #61-#70)
# =====================================================================

import datetime
from pathlib import Path


class CommitteeEnsembleConfig(BaseModel):
    """Configuration for vectorized active learning committee ensemble inference. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    num_models_m: int = Field(default=8, ge=2, le=32, description="Number of committee models M [E]")
    vectorized: bool = True
    vram_headroom_threshold_mb: float = Field(default=2048.0, ge=512.0)
    concurrency_mode: Literal["vmap", "cuda_streams", "serial"] = "vmap"
    max_batch_size: int = Field(default=128, ge=1)
    max_concurrent_models_vram: int = Field(default=2, ge=1)
    synchronize_cuda_streams: bool = True


class OETFallbackAlertManifest(BaseModel):
    """Provenance audit manifest emitted when OET socket disconnect triggers physical fallback. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calculation_base: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    trigger_event: str
    fallback_calculator: str
    provenance_tag: str = "[E]"
    host_telemetry: Dict[str, Any]
    scratch_alert_file: str
    staged_artifact_file: str


class HDF5PersistenceConfig(BaseModel):
    """Configuration for two-tier thread-safe and process-safe HDF5 persistence store. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lock_timeout_seconds: float = Field(default=60.0, ge=1.0)
    retry_backoff_base_seconds: float = Field(default=0.05, ge=0.001)
    compression_filter: str = "gzip"
    compression_level: int = Field(default=4, ge=1, le=9)
    enable_fletcher32: bool = True
    enable_shuffle: bool = True


class GpuScoutExecutorConfig(BaseModel):
    """Configuration for OS-aware heterogeneous GPU scout concurrency across the 6-Tier Matrix. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    platform_os: Literal["windows", "darwin", "linux"]
    enable_mps: bool
    mps_pipe_dir: str
    max_concurrent_gpu_tasks: int = Field(default=1, ge=1)
    min_vram_headroom_mb: float = Field(default=1536.0, ge=512.0)


class JobRouteConfig(BaseModel):
    """Routing specification mapping jobs to heterogeneous Parsl executors. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_type: Literal["heavy_qm_opt", "fast_potential_scan", "single_point", "frequency"]
    assigned_executor: Literal["cochem_anchor_cpu", "cochem_scout_gpu", "local_fallback"]
    cpu_core_pinning: Optional[List[int]] = None
    scratch_dir: str
    timeout_seconds: float = Field(default=3600.0, ge=10.0)


class ExecutionRouteResult(BaseModel):
    """Execution result returned by Parsl execution broker routing. [M]"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    task_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str
    assigned_executor: Optional[str] = None
    executor_used: Optional[str] = None
    scratch_dir: Union[str, Path]
    returncode: int = 0
    future: Optional[Any] = None
    output: Optional[Any] = None
    telemetry: Optional[Dict[str, Any]] = None

    @property
    def effective_task_id(self) -> str:
        return self.task_id or self.job_id or ""

    @property
    def effective_executor(self) -> str:
        return self.assigned_executor or self.executor_used or ""



class MultiSeedGoatConfig(BaseModel):
    """Configuration for asynchronous multi-seed GOAT conformational exploration via Parsl queues. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_structures: List[str] = Field(min_length=1)
    max_concurrent_seeds: int = Field(default=4, ge=1)
    rmsd_threshold_angstrom: float = Field(default=0.15, gt=0.0)
    energy_window_kcal_mol: float = Field(default=6.0, gt=0.0)


class TorqPipelineCliArgs(BaseModel):
    """Validated CLI argument model for high-performance SLURM batch pipeline entrypoints. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_geometry: Path
    output_directory: Path
    theory_level: str = "B3LYP-D4/def2-TZVP"
    cpus_per_task: int = Field(default=1, ge=1)
    memory_mb: int = Field(default=4096, ge=1024)
    scratch_dir: Path


__all__ = [
    "GradientPayload",
    "QuantumJobSpec",
    "ConstraintPayload",
    "ConformerEnsemblePayload",
    "CounterpoiseResult",
    "ActiveLearningBatchConfig",
    "HardwareTelemetryReport",
    "ANI2xCutoffConfig",
    "ConformalCalibrationConfig",
    "ForceMatchingLossConfig",
    "GoatExploreDaemonConfig",
    "PipSymmetryConfig",
    "KrrRegularizationConfig",
    "DeltaMLDispersionConfig",
    "CommitteeEnsembleConfig",
    "OETFallbackAlertManifest",
    "HDF5PersistenceConfig",
    "GpuScoutExecutorConfig",
    "JobRouteConfig",
    "ExecutionRouteResult",
    "MultiSeedGoatConfig",
    "TorqPipelineCliArgs",
]
