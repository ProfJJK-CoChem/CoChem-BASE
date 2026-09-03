"""Pydantic v2 schemas and validation contracts for TORQ Training Dynamics.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Enforces frozen=True, extra="forbid", and strict validation invariants.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrainingDynamicsConfig(BaseModel):
    """Configuration contract for MLFF training dynamics and autograd checkpointing. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_size: int = Field(default=32, ge=1, description="Per-device batch size [M]")
    gradient_checkpointing: bool = Field(default=True, description="Enable activation recomputation [D]")
    mixed_precision_dtype: Literal["bfloat16", "float16", "float32"] = Field(
        default="bfloat16", description="AMP precision [M]"
    )
    max_gradient_norm: float = Field(default=1.0, gt=0.0, description="Gradient clipping norm ceiling [M]")
    energy_loss_weight: float = Field(default=1.0, ge=0.0, description="Loss weight for potential energy [M]")
    force_loss_weight: float = Field(default=100.0, ge=0.0, description="Loss weight for atomic forces [M]")
    learning_rate: float = Field(default=1e-3, gt=0.0, description="Initial optimizer learning rate [M]")
    weight_decay: float = Field(default=1e-5, ge=0.0, description="AdamW weight decay regularization [M]")


class TransferLearningConfig(BaseModel):
    """Configuration contract for ANI-2x domain adaptation and parameter transfer. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_model_path: Path = Field(..., description="Local path to pre-trained ANI-2x weights [M]")
    expected_sha256: str = Field(
        ...,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="Cryptographic SHA-256 hash [M]",
    )
    freeze_symmetry_functions: bool = Field(default=True, description="Freeze AEV feature extractor [M]")
    layer_decay_rate: float = Field(default=0.8, gt=0.0, le=1.0, description="LLRD decay factor [M]")
    new_species_atomic_numbers: List[int] = Field(
        default_factory=list, description="New atomic numbers Z to initialize [M]"
    )

    @field_validator("new_species_atomic_numbers")
    @classmethod
    def validate_atomic_numbers(cls, v: List[int]) -> List[int]:
        """Ensure all atomic numbers satisfy 1 <= Z <= 118 and return sorted unique values."""
        for z in v:
            if z < 1 or z > 118:
                raise ValueError(f"Atomic number Z={z} must be between 1 and 118 inclusive.")
        return sorted(list(set(v)))


class TorchScriptExportConfig(BaseModel):
    """Configuration contract for dedicated C++ TorchScript compilation and parity verification. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    export_path: Path = Field(..., description="Destination path for serialized TorchScript .pt model [M]")
    energy_relative_tolerance: float = Field(
        default=1e-6, gt=0.0, description="Max relative energy error [M]"
    )
    force_parity_tolerance_hartree_angstrom: float = Field(
        default=1e-6,
        gt=0.0,
        description="Max absolute force error in Hartree/Å evaluated in float64 [M]",
    )
    validate_against_fixtures: bool = Field(
        default=True, description="Execute validation before finalizing export [M]"
    )


class DistributedEarlyStoppingConfig(BaseModel):
    """Configuration contract for multi-GPU deadlock-free distributed early stopping. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    patience_epochs: int = Field(default=15, ge=1, description="Epochs to wait before early termination [M]")
    min_delta_hartree: float = Field(
        default=1e-5, ge=0.0, description="Minimum validation loss improvement in Hartree [M]"
    )
    synchronize_ranks: Literal[True] = Field(
        default=True, description="Mandatory broadcast early exit flag across all DDP ranks [D]"
    )


class LossLandscapeConfig(BaseModel):
    """Configuration contract for scale-invariant filter-normalized loss surface profiling. [M]"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_resolution: int = Field(default=25, ge=5, le=100, description="Grid points per axis [M]")
    range_min: float = Field(default=-1.0, description="Normalized coordinate min [M]")
    range_max: float = Field(default=1.0, description="Normalized coordinate max [M]")
    filter_normalization: bool = Field(
        default=True, description="Normalize random directions by filter Frobenius norm [D]"
    )
    output_plot_path: Path = Field(..., description="Destination path for rendered contour plot [M]")

    @model_validator(mode="after")
    def validate_coordinate_range(self) -> LossLandscapeConfig:
        """Verify range_min is strictly less than range_max."""
        if self.range_min >= self.range_max:
            raise ValueError(
                f"range_min ({self.range_min}) must be strictly less than range_max ({self.range_max})."
            )
        return self
