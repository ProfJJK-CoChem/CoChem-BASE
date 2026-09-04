"""
CoChem Ecosystem Authoritative Pydantic Data Schemas.
Compliant with Method Matrix v4, FAIR Data Standards, and Anti-Spoofing Directives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GradientPayload(BaseModel):
    """Pydantic schema for gradient and Hessian calculation outputs.

    Enforces anti-spoofing validation to prevent unphysical all-zero gradients.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    energy: float = Field(description="Electronic energy in Hartrees")
    gradient: List[Any] = Field(
        default_factory=list,
        description="Cartesian energy gradients in Eh/Bohr",
    )
    hessian: Optional[List[Any]] = Field(
        default=None,
        description="Optional Cartesian Hessian matrix elements in Eh/Bohr^2",
    )
    scf_tole: float = Field(
        default=1e-7,
        description="SCF energy convergence threshold in Hartrees",
    )
    geometry: str = Field(
        default="",
        description="Optimized Cartesian XYZ geometry string",
    )
    geom_block: Optional[str] = Field(
        default=None,
        description="Associated %geom block",
    )
    forces: Optional[List[Any]] = Field(
        default=None,
        description="Atomic forces (nabla E = -F)",
    )
    status: str = Field(
        default="SUCCESS",
        description="Execution status",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages collected during calculation",
    )

    @field_validator("gradient")
    @classmethod
    def validate_gradient(cls, v: Any) -> Any:
        if not v:
            return v
        arr = np.asarray(v)
        if arr.size > 0 and np.all(arr == 0.0):
            raise ValueError("Spoofing detected: Fake 0.0 gradients are strictly prohibited.")
        return v


class QuantumJobSpec(BaseModel):
    """Standardized multi-job definition for quantum electronic structure calculations,

    including discrete single-point counterpoise evaluations (E_AB^{AB}, E_A^{AB}, E_B^{AB}).
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True, arbitrary_types_allowed=True)

    job_id: str = Field(description="Unique job identifier")
    symbols: List[str] = Field(description="Atomic symbols")
    coordinates: List[Any] = Field(description="Cartesian coordinates in Angstroms")
    charge: int = Field(default=0, description="Total molecular charge")
    multiplicity: int = Field(default=1, description="Spin multiplicity (2S + 1)")
    method: str = Field(default="wB97M-V", description="Quantum chemistry method / DFT functional")
    basis_set: str = Field(default="def2-TZVP", description="Primary basis set")
    aux_basis: Optional[str] = Field(default="def2/J", description="Auxiliary basis set")
    ghost_atom_indices: Optional[List[int]] = Field(
        default=None,
        description="Indices of atoms treated as ghost centers (basis functions only)",
    )
    job_type: str = Field(
        default="SP",
        description="Calculation type: 'SP', 'OPT', 'FREQ', 'CP_E_AB_AB', 'CP_E_A_AB', 'CP_E_B_AB'",
    )
    extra_options: str = Field(default="", description="Additional engine directives or keywords")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual job metadata")


class ConstraintPayload(BaseModel):
    """Structured payload for monomer internal coordinate constraint definitions."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    bonds: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Frozen distance pairs (u, v) using 0-based indices",
    )
    angles: List[Tuple[int, int, int]] = Field(
        default_factory=list,
        description="Frozen valence angle triplets (i, j, k) with apex j using 0-based indices",
    )
    dihedrals: List[Tuple[int, int, int, int]] = Field(
        default_factory=list,
        description="Frozen proper dihedral quartets (i, j, k, l) using 0-based indices",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Constraint metadata")


class ConformerEnsemblePayload(BaseModel):
    """Unified container for conformer geometries, energies, and origin engine tags."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    ensemble_id: str = Field(description="Ensemble identifier")
    conformers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of conformer dictionaries (symbols, coordinates, energies, moments)",
    )
    origin_engine: str = Field(
        default="UNION",
        description="Origin engine tag (e.g. 'GOAT', 'CREST', 'UNION')",
    )
    temperature_k: float = Field(default=298.15, description="Temperature in Kelvin")
    provenance_tag: str = Field(default="[M]", description="Method Matrix provenance tag")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ensemble metadata")


__all__ = [
    "GradientPayload",
    "QuantumJobSpec",
    "ConstraintPayload",
    "ConformerEnsemblePayload",
]
