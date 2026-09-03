"""Pydantic v2 schemas and data contracts for CoChem-TORQ Inference, Active Learning, and Export.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Strongly typed, validated configurations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActiveLearningOrchestratorConfig(BaseModel):
    """Configuration contract for the active learning acquisition and deduplication engine. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_capacity_k: int = Field(
        default=64,
        ge=1,
        le=512,
        description="Active learning batch selection capacity K [E]",
    )
    force_uncertainty_threshold_ev_per_angstrom: float = Field(
        default=0.05,
        gt=0.0,
        description="Epistemic force standard deviation threshold theta_force in eV/Angstrom [E]",
    )
    energy_uncertainty_threshold_ev2_per_atom: float = Field(
        default=0.001,
        gt=0.0,
        description="QBC energy variance threshold theta_energy in eV^2/atom [E]",
    )
    stage_a_rmsd_threshold_angstrom: float = Field(
        default=0.125,
        gt=0.0,
        description="Method Matrix v4 Stage A geometric RMSD threshold delta_RMSD [M]",
    )
    stage_b_rotational_threshold: float = Field(
        default=0.001,
        gt=0.0,
        description="Method Matrix v4 Stage B relative rotational constant invariance delta_B/B (--bthr) [M]",
    )
    triage_tier: Literal["T3-10s", "T3-1h", "T3-12h", "T3O-1h", "T3O-12h"] = Field(
        default="T3-10s",
        description="Initial baseline QM routing tier [M]",
    )
    staging_manifest_dir: Path = Field(
        ...,
        description="Air-gapped manifest export directory in Ring 3 [M]",
    )

    @model_validator(mode="before")
    @classmethod
    def remap_legacy_field_names(cls, data: Any) -> Any:
        """Support field name aliases across specification revisions. [D]"""
        if isinstance(data, dict):
            mapped = dict(data)
            if "force_uncertainty_threshold" in mapped and "force_uncertainty_threshold_ev_per_angstrom" not in mapped:
                mapped["force_uncertainty_threshold_ev_per_angstrom"] = mapped.pop("force_uncertainty_threshold")
            if "energy_uncertainty_threshold" in mapped and "energy_uncertainty_threshold_ev2_per_atom" not in mapped:
                mapped["energy_uncertainty_threshold_ev2_per_atom"] = mapped.pop("energy_uncertainty_threshold")
            if "rmsd_dedup_threshold_angstrom" in mapped and "stage_a_rmsd_threshold_angstrom" not in mapped:
                mapped["stage_a_rmsd_threshold_angstrom"] = mapped.pop("rmsd_dedup_threshold_angstrom")
            return mapped
        return data

    @property
    def force_uncertainty_threshold(self) -> float:
        """Alias for force_uncertainty_threshold_ev_per_angstrom. [D]"""
        return self.force_uncertainty_threshold_ev_per_angstrom

    @property
    def energy_uncertainty_threshold(self) -> float:
        """Alias for energy_uncertainty_threshold_ev2_per_atom. [D]"""
        return self.energy_uncertainty_threshold_ev2_per_atom

    @property
    def rmsd_dedup_threshold_angstrom(self) -> float:
        """Alias for stage_a_rmsd_threshold_angstrom. [D]"""
        return self.stage_a_rmsd_threshold_angstrom


class ChunkedHDF5DataModuleConfig(BaseModel):
    """Configuration contract for chunked HDF5 PyTorch Lightning DataModule. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    h5_path: Path = Field(..., description="Path to chunked HDF5 dataset [M]")
    batch_size: int = Field(default=32, ge=1, description="Batch size per device [M]")
    num_workers: int = Field(
        default=2, ge=0, description="Number of dataloader worker processes [M]"
    )
    chunk_cache_bytes: int = Field(
        default=16 * 1024 * 1024,
        ge=1024 * 1024,
        description="HDF5 raw data chunk cache size rdcc_nbytes [E]",
    )
    chunk_cache_slots: int = Field(
        default=10007,
        ge=1009,
        description="Prime number of chunk cache hash slots rdcc_nslots [D]",
    )
    pin_memory: bool = Field(
        default=True,
        description="Pin host memory for non-blocking GPU transfer [M]",
    )
    train_val_test_split: List[float] = Field(
        default=[0.8, 0.1, 0.1],
        description="Train, validation, and test split ratios [M]",
    )

    @model_validator(mode="after")
    def validate_splits(self) -> "ChunkedHDF5DataModuleConfig":
        """Verify train, val, and test splits sum to unity within tolerance. [D]"""
        if abs(sum(self.train_val_test_split) - 1.0) > 1e-5:
            raise ValueError("train_val_test_split must sum to 1.0")
        return self


class CommitteeEnsembleConfig(BaseModel):
    """Configuration contract for Committee Ensemble uncertainty wrapper. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    num_models_m: int = Field(
        default=8, ge=2, le=32, description="Number of committee models M [E]"
    )
    max_concurrent_models_vram: int = Field(
        default=2,
        ge=1,
        description="Maximum models loaded into active VRAM simultaneously [E]",
    )
    synchronize_cuda_streams: bool = Field(
        default=True,
        description="Execute stream synchronization between model forward passes [D]",
    )


class C2SmoothCutoffConfig(BaseModel):
    """Configuration contract for C^2-smooth radial cutoff envelope. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius_rc: float = Field(
        default=5.0,
        gt=1.0,
        description="Radial cutoff boundary radius r_c in Angstroms [M]",
    )
    polynomial_degree: Literal[5] = Field(
        default=5,
        description="Degree of C^2 continuous switching polynomial [D]",
    )


class GNNGradientDebuggerConfig(BaseModel):
    """Configuration contract for message-passing GNN gradient health debugger. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exploding_grad_threshold: float = Field(
        default=1e3, gt=0.0, description="L2 gradient norm explosion threshold [D]"
    )
    vanishing_grad_threshold: float = Field(
        default=1e-7, gt=0.0, description="L2 gradient norm vanishing threshold [D]"
    )
    consecutive_vanishing_blocks: int = Field(
        default=3,
        ge=1,
        description="Consecutive layers below vanishing threshold before alert [D]",
    )
    enabled: bool = Field(
        default=True, description="Enable active hook monitoring [M]"
    )


class PBCRadialGraphConfig(BaseModel):
    """Configuration contract for periodic boundary condition graph engine. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cutoff_radius_rc: float = Field(
        default=5.0,
        gt=1.0,
        description="Radial graph cutoff radius in Angstroms [M]",
    )
    compute_virial_stress: bool = Field(
        default=True,
        description="Compute analytical unit cell virial stress tensor [D]",
    )
