"""Pydantic v2 Schemas and Data Models for CoChem-TORQ."""

from __future__ import annotations

from pathlib import Path
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical


class TorqModelConfig(BaseModel):
    """Configuration schema for TORQ machine learning potential backbones."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_name: Literal["schnet", "mace", "nequip", "cartesian_equivariant"] = Field(
        default="cartesian_equivariant",
        description="Architecture backbone type [E]",
    )
    r_max: float = Field(
        default=5.0,
        gt=0.0,
        le=10.0,
        description="Cutoff radius in Angstroms [E]",
    )
    num_radial_basis: int = Field(
        default=32,
        ge=8,
        le=128,
        description="Number of radial basis functions [E]",
    )
    num_channels: int = Field(
        default=64,
        ge=16,
        le=512,
        description="Hidden feature dimensionality [E]",
    )
    num_layers: int = Field(
        default=3,
        ge=1,
        le=8,
        description="Number of interaction layers [E]",
    )
    l_max: int = Field(
        default=2,
        ge=0,
        le=3,
        description="Maximum spherical tensor degree [M]",
    )
    charge_neutral: bool = Field(
        default=True,
        description="Enforce molecular charge neutrality [M]",
    )


class AtomicConfigurationInput(BaseModel):
    """Input representation of atomic structure for potential evaluations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    atomic_numbers: List[int] = Field(
        min_length=1,
        description="IUPAC atomic numbers Z [M]",
    )
    coordinates: List[Tuple[float, float, float]] = Field(
        min_length=1,
        description="Cartesian coordinates in Angstroms [M]",
    )
    pbc: Tuple[bool, bool, bool] = Field(
        default=(False, False, False),
        description="Periodic boundary conditions [M]",
    )
    cell: Optional[List[List[float]]] = Field(
        default=None,
        description="3x3 unit cell vectors in Angstroms [M]",
    )
    total_charge: float = Field(
        default=0.0,
        description="Net molecular charge in elementary charge units [M]",
    )


class PotentialEnergyOutput(BaseModel):
    """Output energy, forces, and virial stress from potential evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    energy: float = Field(description="Scalar potential energy in eV [M]")
    forces: List[Tuple[float, float, float]] = Field(
        description="Negative energy gradients in eV/Angstrom [M]"
    )
    stress: Optional[List[float]] = Field(
        default=None,
        description="Voigt 6-vector virial stress in eV/Angstrom^3 [M]",
    )


class ObservableOutput(BaseModel):
    """Differentiable electronic observables output schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dipole_vector: Tuple[float, float, float] = Field(
        description="Electric dipole moment vector in Debye [M]"
    )
    polarizability_tensor: List[List[float]] = Field(
        description="3x3 symmetric polarizability tensor in Angstrom^3 [M]"
    )
    mean_polarizability: float = Field(
        description="Isotropic polarizability scalar in Angstrom^3 [M]"
    )
    anisotropy: float = Field(
        description="Polarizability tensor anisotropy in Angstrom^3 [D]"
    )


class HDF5PersistenceConfig(BaseModel):
    """Configuration for dual-locked thread-safe and process-safe HDF5 storage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: Path = Field(description="Target .h5 file path")
    compression: str = Field(default="gzip", description="HDF5 compression filter")
    compression_opts: int = Field(default=4, ge=0, le=9)
    lock_timeout_seconds: float = Field(default=30.0, gt=0.0)
