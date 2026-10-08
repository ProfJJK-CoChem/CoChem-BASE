"""CoChem Quantum Schemas Module.

Compliant with Method Matrix v4, QCSchema specifications, and Anti-Spoofing Protocol v2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GradientPayload(BaseModel):
    """Pydantic schema for gradient and Hessian calculation outputs.

    Enforces anti-spoofing validation to prevent unphysical all-zero gradients.
    Screening tiers (T1-T3) leave hessian=None; target production tiers (T4/T5) populate it.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    energy: float = Field(..., allow_inf_nan=False, description="Measured electronic energy in Hartrees")
    energy_hartree: Optional[float] = Field(
        default=None,
        allow_inf_nan=False,
        description="Electronic energy in true atomic units (Hartree) per Method Matrix §8C",
    )
    gradient: List[Any] = Field(
        default_factory=list,
        description="Cartesian energy gradients in Eh/Bohr",
    )
    hessian: Optional[List[Any]] = Field(
        default=None,
        description="Cartesian force constant matrix; populated exclusively at production tiers (T4/T5).",
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

    @model_validator(mode="before")
    @classmethod
    def sync_energies(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "energy_hartree" in data and data["energy_hartree"] is not None:
                if data.get("energy") is None:
                    data["energy"] = float(data["energy_hartree"])
                elif float(data["energy"]) != float(data["energy_hartree"]):
                    raise ValueError("Conflicting measured energy and energy_hartree values")
            elif "energy" in data and data["energy"] is not None:
                data["energy_hartree"] = float(data["energy"])
        return data

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


class CounterpoiseResult(BaseModel):
    """Result payload for discrete 3-point and 5-point Boys-Bernardi counterpoise evaluations.

    Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    delta_e_cp: float = Field(description="Counterpoise-corrected interaction energy in Hartrees [M]")
    e_ab_ab: float = Field(description="Total electronic energy of complex AB in dimer basis [Hartree]")
    e_a_ab: float = Field(description="Total electronic energy of Monomer A in dimer basis (B ghosted) [Hartree]")
    e_b_ab: float = Field(description="Total electronic energy of Monomer B in dimer basis (A ghosted) [Hartree]")
    e_a_a: Optional[float] = Field(default=None, description="Monomer A in monomer A basis [Hartree]")
    e_b_b: Optional[float] = Field(default=None, description="Monomer B in monomer B basis [Hartree]")
    e_bsse: Optional[float] = Field(default=None, description="Basis Set Superposition Error (BSSE) [Hartree]")
    delta_e_raw: Optional[float] = Field(default=None, description="Uncorrected raw interaction energy [Hartree]")
    provenance_tag: str = Field(default="[M]", description="Method Matrix provenance tag")


__all__ = [
    "GradientPayload",
    "QuantumJobSpec",
    "ConstraintPayload",
    "ConformerEnsemblePayload",
    "CounterpoiseResult",
]
