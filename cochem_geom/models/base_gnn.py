"""CoChem-GEOM: Base 3D Graph Neural Network Architecture & Physical Data Contracts.
=====================================================================================
Establishes the foundational Tier 2 representation layer for geometric deep learning,
equivariant / invariant message passing, and physics-informed potential energy surface (PES)
modeling across the CoChem ecosystem (CoChem-GEOM and CoChem-BASE).

Key Architectural Components:
1. Physical Constants & Provenance Declarations (CODATA 2018/2022 standards):
   - Fundamental physical constants tagged with [M] (Measured), [D] (Derived), [E] (Expert Estimate).

2. Dynamic Mendeleev Library Atomic Mass Queries (Zero-Mock Mandate):
   - Dynamic mass resolution via `mendeleev.element` without hardcoded lookup tables.
   - Dynamic center-of-mass and moment-of-inertia tensor computations.

3. Pure State Immutability & SE(3) Operations:
   - Non-destructive Cartesian translations, SO(3) rotations, coordinate centering, and updates.
   - Strict functional semantics (`pos_new = pos + update`, never in-place `pos += update`).

4. Strict Separation of SE(3) Equivariance vs Invariance:
   - Spatial coordinates $\\mathbf{r} \\in \\mathbb{R}^{N \\times 3}$ transform equivariantly: $\\mathbf{r}' = \\mathbf{r} \\mathbf{R}^T + \\mathbf{t}$.
   - Scalar electronic energy $E \\in \\mathbb{R}$ is strictly invariant: $E(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) = E(\\mathbf{r})$.
   - Analytical interatomic forces $\\mathbf{F} = -\\nabla_{\\mathbf{r}} E$ transform equivariantly: $\\mathbf{F}' = \\mathbf{F} \\mathbf{R}^T$.
   - Latent node representations $\\mathbf{h} \\in \\mathbb{R}^{N \\times F}$ remain invariant.

5. Pydantic v2 Data Contracts & Dataclasses:
   - `GNNModelConfig`: Validated, frozen Pydantic v2 model configuration.
   - `ConformerInputContract`: Validated structural input contract for molecular geometries.
   - `GNNPredictionContract`: Validated output contract for energy and force predictions.
   - `GNNOutput`: Dataclass container for forward energy predictions and latent states.
   - `GNNForceOutput`: Dataclass container for joint energy and analytical force predictions.

6. Abstract Base Classes & Canonical Reference Models:
   - `BaseGNNLayer`: Abstract base class enforcing layer message passing signature.
   - `Base3DGNN`: Abstract base class enforcing `forward(data)` and `compute_forces(data)`.
   - `RadialBasisExpansion`: Gaussian radial basis function expansion with cosine envelope.
   - `Canonical3DInteractionBlock`: Invariant continuous-filter convolution layer.
   - `Equivariant3DInteractionBlock`: Equivariant coordinate and invariant feature message passing layer.
   - `Canonical3DGNN`: Reference production 3D GNN architecture (CFConv / SchNet-style).
   - `Equivariant3DGNN`: Reference production Equivariant 3D GNN architecture (EGNN-style).

Authoritative Standards & Directives:
- Method Matrix v4: Geometric Deep Learning & Spectroscopic Graph Contracts
- SWEBOK v3 / ISO 25010 Software Quality & Architecture Standards
- Zero-Mock Mandate: 100% authentic physical tensor mathematics and real execution
- Mendeleev Library Mandate: Dynamic atomic mass & isotopic resolution (NEVER hardcoded)
- State Immutability: Pure functional geometric transformations
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import abc
import copy
import dataclasses
import math
import os
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import mendeleev
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import torch
import torch.nn as nn
import torch.nn.functional as F


# ==============================================================================
# 1. Fundamental Physical Constants & Provenance Declarations (CODATA 2018/2022)
# ==============================================================================

SPEED_OF_LIGHT_M_S: float = 299792458.0
"""Speed of light in vacuum in meters per second (exact) [M]."""

PLANCK_CONSTANT_J_S: float = 6.62607015e-34
"""Planck constant in Joule seconds (exact) [M]."""

BOLTZMANN_CONSTANT_J_K: float = 1.380649e-23
"""Boltzmann constant in Joules per Kelvin (exact) [M]."""

BOLTZMANN_CONSTANT_EV_K: float = 8.617333262145e-5
"""Boltzmann constant in electron-volts per Kelvin [D]."""

ELEMENTARY_CHARGE_C: float = 1.602176634e-19
"""Elementary charge in Coulombs (exact) [M]."""

AVOGADRO_CONSTANT_MOL: float = 6.02214076e23
"""Avogadro constant per mole (exact) [M]."""

ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27
"""Unified atomic mass unit / Dalton in kilograms [M]."""

BOHR_RADIUS_ANGSTROM: float = 0.529177210903
"""Bohr radius in Angstroms [M]."""

HARTREE_TO_EV: float = 27.211386245988
"""Conversion factor from Hartree to electron-volts [D]."""

EV_TO_HARTREE: float = 1.0 / HARTREE_TO_EV
"""Conversion factor from electron-volts to Hartree [D]."""

HARTREE_TO_KCAL_MOL: float = 627.5094740631
"""Conversion factor from Hartree to kcal/mol [D]."""

KCAL_MOL_TO_EV: float = 0.0433641
"""Conversion factor from kcal/mol to electron-volts [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.0087
"""Conversion factor from inverse moment of inertia (u*Angstrom^2)^(-1) to MHz [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient reference temperature in Kelvin (25 deg C) [M]."""

DEFAULT_MAX_Z: int = 100
"""Maximum supported atomic number Z for embedding tables (1-100) [M]."""

DEFAULT_RBF_CUTOFF: float = 5.0
"""Default radial basis cutoff distance in Angstroms [E]."""

DEFAULT_NUM_RADIAL: int = 32
"""Default number of Gaussian radial basis kernels [E]."""

DEFAULT_HIDDEN_CHANNELS: int = 128
"""Default latent representation feature dimension [E]."""

DEFAULT_NUM_LAYERS: int = 4
"""Default number of interaction / message passing layers [E]."""


# ==============================================================================
# 2. Dynamic Mendeleev Library Atomic Mass Queries (Zero-Mock Mandate)
# ==============================================================================

_DYNAMIC_MASS_CACHE: Dict[str, float] = {}
_DYNAMIC_MONO_MASS_CACHE: Dict[str, float] = {}


def resolve_dynamic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev library [M].

    Hardcoded atomic weight tables are strictly forbidden by architectural mandate.

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons (unified atomic mass units).
    """
    key = str(symbol_or_z).strip().capitalize()
    if key in _DYNAMIC_MASS_CACHE:
        return _DYNAMIC_MASS_CACHE[key]

    elem = mendeleev.element(symbol_or_z)
    weight = elem.atomic_weight
    if weight is not None:
        mass_val = float(weight)
    elif elem.isotopes:
        most_abundant = max(
            elem.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            mass_val = float(most_abundant.mass)
        elif most_abundant.mass_number is not None:
            mass_val = float(most_abundant.mass_number)
        else:
            mass_val = float(elem.mass) if elem.mass is not None else 1.0
    elif elem.mass is not None:
        mass_val = float(elem.mass)
    else:
        raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")

    _DYNAMIC_MASS_CACHE[key] = mass_val
    return mass_val


def resolve_dynamic_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.

    Returns
    -------
    float
        Monoisotopic mass in Daltons.
    """
    key = str(symbol_or_z).strip().capitalize()
    if key in _DYNAMIC_MONO_MASS_CACHE:
        return _DYNAMIC_MONO_MASS_CACHE[key]

    elem = mendeleev.element(symbol_or_z)
    if elem.isotopes:
        most_abundant = max(
            elem.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            mass_val = float(most_abundant.mass)
            _DYNAMIC_MONO_MASS_CACHE[key] = mass_val
            return mass_val

    mass_val = resolve_dynamic_mass(symbol_or_z)
    _DYNAMIC_MONO_MASS_CACHE[key] = mass_val
    return mass_val


def get_atomic_masses(atomic_numbers: torch.Tensor) -> torch.Tensor:
    """Dynamically query atomic masses for a 1D tensor of atomic numbers [M].

    Parameters
    ----------
    atomic_numbers : torch.Tensor
        1D tensor of integer atomic numbers Z of shape [N].

    Returns
    -------
    torch.Tensor
        1D tensor of standard atomic masses in Daltons of shape [N] (float32).
    """
    z_list = atomic_numbers.detach().cpu().view(-1).tolist()
    mass_list = [resolve_dynamic_mass(int(z)) for z in z_list]
    return torch.tensor(mass_list, dtype=torch.float32, device=atomic_numbers.device)


def compute_center_of_mass(
    pos: torch.Tensor,
    masses: Optional[torch.Tensor] = None,
    atomic_numbers: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute the mass-weighted center of mass vector dynamically [D].

    $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_{i=1}^N m_i \\mathbf{r}_i}{\\sum_{i=1}^N m_i}$$

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    masses : Optional[torch.Tensor]
        Atomic masses [N]. If None and atomic_numbers is provided, resolved dynamically.
    atomic_numbers : Optional[torch.Tensor]
        Atomic numbers [N], used if masses is None.

    Returns
    -------
    torch.Tensor
        Center of mass vector [3].
    """
    if masses is None:
        if atomic_numbers is not None:
            masses = get_atomic_masses(atomic_numbers).to(device=pos.device, dtype=pos.dtype)
        else:
            masses = torch.ones(pos.size(0), dtype=pos.dtype, device=pos.device)
    else:
        masses = masses.to(device=pos.device, dtype=pos.dtype)

    total_mass = masses.sum()
    if total_mass <= 0.0:
        return pos.mean(dim=0)
    return (pos * masses.unsqueeze(-1)).sum(dim=0) / total_mass


def compute_moment_of_inertia_tensor(
    pos: torch.Tensor,
    masses: Optional[torch.Tensor] = None,
    atomic_numbers: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute the 3x3 mass-weighted moment of inertia tensor at the COM frame [D].

    $$I_{\\alpha \\beta} = \\sum_{i=1}^N m_i \\left( \\|\\mathbf{r}'_i\\|^2 \\delta_{\\alpha \\beta} - r'_{i, \\alpha} r'_{i, \\beta} \\right)$$

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    masses : Optional[torch.Tensor]
        Atomic masses [N].
    atomic_numbers : Optional[torch.Tensor]
        Atomic numbers [N].

    Returns
    -------
    torch.Tensor
        Symmetric 3x3 moment of inertia tensor in u * Angstrom^2.
    """
    com = compute_center_of_mass(pos, masses=masses, atomic_numbers=atomic_numbers)
    # Pure immutable subtraction
    r = pos - com.unsqueeze(0)

    if masses is None:
        if atomic_numbers is not None:
            m = get_atomic_masses(atomic_numbers).to(device=pos.device, dtype=pos.dtype)
        else:
            m = torch.ones(pos.size(0), dtype=pos.dtype, device=pos.device)
    else:
        m = masses.to(device=pos.device, dtype=pos.dtype)

    x, y, z = r[:, 0], r[:, 1], r[:, 2]

    i_xx = (m * (y**2 + z**2)).sum()
    i_yy = (m * (x**2 + z**2)).sum()
    i_zz = (m * (x**2 + y**2)).sum()
    i_xy = -(m * x * y).sum()
    i_xz = -(m * x * z).sum()
    i_yz = -(m * y * z).sum()

    tensor = torch.zeros((3, 3), dtype=pos.dtype, device=pos.device)
    tensor[0, 0] = i_xx
    tensor[1, 1] = i_yy
    tensor[2, 2] = i_zz
    tensor[0, 1] = i_xy
    tensor[1, 0] = i_xy
    tensor[0, 2] = i_xz
    tensor[2, 0] = i_xz
    tensor[1, 2] = i_yz
    tensor[2, 1] = i_yz

    return tensor


def compute_principal_rotational_constants(
    pos: torch.Tensor,
    masses: Optional[torch.Tensor] = None,
    atomic_numbers: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """Compute principal rotational constants (A >= B >= C) in MHz [D].

    $$A = \\frac{h}{8 \\pi^2 I_a}, \\quad B = \\frac{h}{8 \\pi^2 I_b}, \\quad C = \\frac{h}{8 \\pi^2 I_c}$$

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    masses : Optional[torch.Tensor]
        Atomic masses [N].
    atomic_numbers : Optional[torch.Tensor]
        Atomic numbers [N].

    Returns
    -------
    torch.Tensor
        Rotational constants tensor [A, B, C] in MHz of shape [3].
    """
    inertia_mat = compute_moment_of_inertia_tensor(pos, masses=masses, atomic_numbers=atomic_numbers)
    # Eigenvalues of symmetric positive semi-definite matrix
    eigenvalues = torch.linalg.eigvalsh(inertia_mat)
    # Principal moments: I_a <= I_b <= I_c -> A >= B >= C
    sorted_moments, _ = torch.sort(eigenvalues, descending=False)

    rot_consts = torch.zeros(3, dtype=pos.dtype, device=pos.device)
    for i in range(3):
        val = sorted_moments[i]
        if val > 1e-6:
            rot_consts[i] = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / val
        else:
            rot_consts[i] = 0.0

    return rot_consts


# ==============================================================================
# 3. Pure State Immutability & SE(3) Coordinate Operators
# ==============================================================================

def translate_coordinates(pos: torch.Tensor, shift: torch.Tensor) -> torch.Tensor:
    """Pure functional translation preserving strict state immutability [D].

    $$\\mathbf{r}' = \\mathbf{r} + \\mathbf{t}$$
    Enforces `pos_new = pos + shift` (never in-place mutation `pos += shift`).

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    shift : torch.Tensor
        Translation vector [3] or [1, 3].

    Returns
    -------
    torch.Tensor
        New translated coordinate tensor [N, 3].
    """
    return pos + shift.view(1, 3)


def rotate_coordinates(pos: torch.Tensor, rotation_matrix: torch.Tensor) -> torch.Tensor:
    """Pure functional 3D rotation applying an SO(3) orthogonal matrix [D].

    $$\\mathbf{r}' = \\mathbf{r} \\mathbf{R}^T$$

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    rotation_matrix : torch.Tensor
        Orthogonal SO(3) 3x3 rotation matrix.

    Returns
    -------
    torch.Tensor
        New rotated coordinate tensor [N, 3].
    """
    return torch.matmul(pos, rotation_matrix.T)


def center_coordinates(
    pos: torch.Tensor,
    masses: Optional[torch.Tensor] = None,
    atomic_numbers: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Pure functional coordinate centering subtracting the mass-weighted COM [D].

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    masses : Optional[torch.Tensor]
        Atomic masses [N].
    atomic_numbers : Optional[torch.Tensor]
        Atomic numbers [N].

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (pos_centered [N, 3], com_vector [3])
    """
    com = compute_center_of_mass(pos, masses=masses, atomic_numbers=atomic_numbers)
    return pos - com.unsqueeze(0), com


def apply_coordinate_delta(pos: torch.Tensor, delta: torch.Tensor) -> torch.Tensor:
    """Immutable coordinate update rule: `pos_new = pos + delta` [D].

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    delta : torch.Tensor
        Coordinate displacements [N, 3].

    Returns
    -------
    torch.Tensor
        New updated coordinate tensor [N, 3].
    """
    return pos + delta


def generate_random_so3_rotation(
    dtype: torch.dtype = torch.float32,
    device: Optional[Union[str, torch.device]] = None,
    seed: Optional[int] = None,
) -> torch.Tensor:
    """Generate a uniformly sampled random SO(3) rotation matrix via Haar measure [D].

    Guarantees $\\mathbf{R}^T \\mathbf{R} = \\mathbf{I}$ and $\\det(\\mathbf{R}) = +1.0$.

    Parameters
    ----------
    dtype : torch.dtype
        Target PyTorch floating point precision.
    device : Optional[Union[str, torch.device]]
        Target PyTorch device.
    seed : Optional[int]
        Optional deterministic random seed.

    Returns
    -------
    torch.Tensor
        Orthogonal SO(3) 3x3 rotation matrix.
    """
    rng = np.random.default_rng(seed) if seed is not None else np.random.default_rng()
    mat = rng.normal(size=(3, 3))
    q, r = np.linalg.qr(mat)
    d = np.diagonal(r)
    ph = d / np.abs(d)
    q = q * ph
    if np.linalg.det(q) < 0.0:
        q[:, 0] = -q[:, 0]
    dev = torch.device(device) if device is not None else torch.device("cpu")
    return torch.tensor(q, dtype=dtype, device=dev)


# ==============================================================================
# 4. Pydantic v2 Schemas & Data Contracts
# ==============================================================================

class GNNModelConfig(BaseModel):
    """Pydantic v2 configuration schema for 3D Graph Neural Network models."""

    model_name: str = Field(
        default="Base3DGNN",
        description="Architecture model identifier",
    )
    hidden_channels: int = Field(
        default=DEFAULT_HIDDEN_CHANNELS,
        ge=8,
        description="Dimension of latent hidden embeddings [E]",
    )
    num_layers: int = Field(
        default=DEFAULT_NUM_LAYERS,
        ge=1,
        description="Number of interaction / message passing layers [E]",
    )
    num_radial: int = Field(
        default=DEFAULT_NUM_RADIAL,
        ge=1,
        description="Number of Gaussian radial basis expansion kernels [E]",
    )
    cutoff: float = Field(
        default=DEFAULT_RBF_CUTOFF,
        gt=0.0,
        description="Spatial interaction cutoff distance in Angstroms [E]",
    )
    max_z: int = Field(
        default=DEFAULT_MAX_Z,
        ge=1,
        le=118,
        description="Maximum supported atomic number Z for embedding table [M]",
    )
    energy_weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Loss weight scaling factor for scalar energy [E]",
    )
    force_weight: float = Field(
        default=0.0,
        ge=0.0,
        description="Loss weight scaling factor for analytical forces [E]",
    )
    use_forces: bool = Field(
        default=True,
        description="Enable analytical force computation via autograd",
    )
    aggr: Literal["sum", "mean", "add"] = Field(
        default="sum",
        description="Graph-level atomic readout aggregation operator",
    )
    activation: Literal["silu", "relu", "gelu", "tanh"] = Field(
        default="silu",
        description="Nonlinear activation function for MLPs",
    )
    dropout: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Dropout probability for regularized layers [E]",
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )


class ConformerInputContract(BaseModel):
    """Pydantic v2 input data contract validating molecular conformer representations."""

    num_atoms: int = Field(
        ...,
        ge=1,
        description="Number of atoms in the molecular structure",
    )
    atomic_numbers: List[int] = Field(
        ...,
        min_length=1,
        description="Atomic numbers Z of length N [M]",
    )
    positions: List[List[float]] = Field(
        ...,
        min_length=1,
        description="Cartesian coordinates of shape (N, 3) in Angstroms [M]",
    )
    energy: Optional[float] = Field(
        default=None,
        description="Ground-truth electronic potential energy in eV or Hartree [D]",
    )
    forces: Optional[List[List[float]]] = Field(
        default=None,
        description="Ground-truth interatomic force vectors of shape (N, 3) in eV/Angstrom [D]",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Boltzmann thermodynamic or statistical sample weight [D]",
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @field_validator("atomic_numbers")
    @classmethod
    def validate_atomic_numbers(cls, v: List[int]) -> List[int]:
        for z in v:
            if z < 1 or z > 118:
                raise ValueError(f"Atomic number {z} out of valid chemical range [1, 118].")
        return v

    @model_validator(mode="after")
    def check_conformer_dimensions(self) -> ConformerInputContract:
        if len(self.atomic_numbers) != self.num_atoms:
            raise ValueError(
                f"atomic_numbers count ({len(self.atomic_numbers)}) != num_atoms ({self.num_atoms})"
            )
        if len(self.positions) != self.num_atoms:
            raise ValueError(
                f"positions count ({len(self.positions)}) != num_atoms ({self.num_atoms})"
            )
        for p in self.positions:
            if len(p) != 3:
                raise ValueError(f"Each position vector must have dimension 3; got {len(p)}")
        if self.forces is not None:
            if len(self.forces) != self.num_atoms:
                raise ValueError(
                    f"forces count ({len(self.forces)}) != num_atoms ({self.num_atoms})"
                )
            for f in self.forces:
                if len(f) != 3:
                    raise ValueError(f"Each force vector must have dimension 3; got {len(f)}")
        return self


class GNNPredictionContract(BaseModel):
    """Pydantic v2 validation contract for GNN energy and force predictions."""

    num_graphs: int = Field(
        ...,
        ge=1,
        description="Number of graphs / batch size",
    )
    total_energy: List[float] = Field(
        ...,
        min_length=1,
        description="Predicted total molecular energies of length B [D]",
    )
    num_nodes: Optional[int] = Field(
        default=None,
        ge=1,
        description="Total number of nodes across all graphs in batch",
    )
    forces: Optional[List[List[float]]] = Field(
        default=None,
        description="Predicted interatomic force vectors of shape (Total_N, 3) [D]",
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    @model_validator(mode="after")
    def check_predictions(self) -> GNNPredictionContract:
        if len(self.total_energy) != self.num_graphs:
            raise ValueError(
                f"total_energy count ({len(self.total_energy)}) != num_graphs ({self.num_graphs})"
            )
        for e in self.total_energy:
            if not math.isfinite(e):
                raise ValueError(f"Encountered non-finite energy prediction: {e}")
        if self.forces is not None:
            if self.num_nodes is not None and len(self.forces) != self.num_nodes:
                raise ValueError(
                    f"forces count ({len(self.forces)}) != num_nodes ({self.num_nodes})"
                )
            for f in self.forces:
                if len(f) != 3:
                    raise ValueError(f"Each force vector must have dimension 3; got {len(f)}")
                for comp in f:
                    if not math.isfinite(comp):
                        raise ValueError(f"Encountered non-finite force component: {comp}")
        return self


# ==============================================================================
# 5. Dataclass Output Contracts
# ==============================================================================

@dataclasses.dataclass
class GNNOutput:
    """Standardized output data contract for 3D GNN forward energy passes."""

    energy: torch.Tensor
    atomic_energies: Optional[torch.Tensor] = None
    node_features: Optional[torch.Tensor] = None
    pos_updated: Optional[torch.Tensor] = None
    dipole: Optional[torch.Tensor] = None
    rotational_constants: Optional[torch.Tensor] = None
    metadata: Optional[Dict[str, Any]] = None

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> GNNOutput:
        """Transfer all contained tensors to target device and precision immutably."""
        dev = torch.device(device) if device is not None else self.energy.device
        return GNNOutput(
            energy=(
                self.energy.to(device=dev, dtype=dtype)
                if dtype is not None
                else self.energy.to(device=dev)
            ),
            atomic_energies=(
                self.atomic_energies.to(device=dev, dtype=dtype)
                if self.atomic_energies is not None and dtype is not None
                else (self.atomic_energies.to(device=dev) if self.atomic_energies is not None else None)
            ),
            node_features=(
                self.node_features.to(device=dev, dtype=dtype)
                if self.node_features is not None and dtype is not None
                else (self.node_features.to(device=dev) if self.node_features is not None else None)
            ),
            pos_updated=(
                self.pos_updated.to(device=dev, dtype=dtype)
                if self.pos_updated is not None and dtype is not None
                else (self.pos_updated.to(device=dev) if self.pos_updated is not None else None)
            ),
            dipole=(
                self.dipole.to(device=dev, dtype=dtype)
                if self.dipole is not None and dtype is not None
                else (self.dipole.to(device=dev) if self.dipole is not None else None)
            ),
            rotational_constants=(
                self.rotational_constants.to(device=dev, dtype=dtype)
                if self.rotational_constants is not None and dtype is not None
                else (
                    self.rotational_constants.to(device=dev)
                    if self.rotational_constants is not None
                    else None
                )
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def detach(self) -> GNNOutput:
        """Detach all prediction tensors from autograd computation graph."""
        return GNNOutput(
            energy=self.energy.detach(),
            atomic_energies=(
                self.atomic_energies.detach() if self.atomic_energies is not None else None
            ),
            node_features=(
                self.node_features.detach() if self.node_features is not None else None
            ),
            pos_updated=(
                self.pos_updated.detach() if self.pos_updated is not None else None
            ),
            dipole=self.dipole.detach() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.detach()
                if self.rotational_constants is not None
                else None
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def clone(self) -> GNNOutput:
        """Deep copy all prediction tensors."""
        return GNNOutput(
            energy=self.energy.clone(),
            atomic_energies=(
                self.atomic_energies.clone() if self.atomic_energies is not None else None
            ),
            node_features=(
                self.node_features.clone() if self.node_features is not None else None
            ),
            pos_updated=(
                self.pos_updated.clone() if self.pos_updated is not None else None
            ),
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def as_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary representation."""
        res: Dict[str, Any] = {"energy": self.energy}
        if self.atomic_energies is not None:
            res["atomic_energies"] = self.atomic_energies
        if self.node_features is not None:
            res["node_features"] = self.node_features
        if self.pos_updated is not None:
            res["pos_updated"] = self.pos_updated
        if self.dipole is not None:
            res["dipole"] = self.dipole
        if self.rotational_constants is not None:
            res["rotational_constants"] = self.rotational_constants
        if self.metadata is not None:
            res["metadata"] = self.metadata
        return res

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        raise KeyError(f"Key '{key}' not found or is None in GNNOutput.")


@dataclasses.dataclass
class GNNForceOutput:
    """Standardized output data contract for joint energy and analytical force predictions."""

    energy: torch.Tensor
    forces: torch.Tensor
    atomic_energies: Optional[torch.Tensor] = None
    pos_updated: Optional[torch.Tensor] = None
    metadata: Optional[Dict[str, Any]] = None

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> GNNForceOutput:
        """Transfer all contained tensors to target device and precision immutably."""
        dev = torch.device(device) if device is not None else self.energy.device
        return GNNForceOutput(
            energy=(
                self.energy.to(device=dev, dtype=dtype)
                if dtype is not None
                else self.energy.to(device=dev)
            ),
            forces=(
                self.forces.to(device=dev, dtype=dtype)
                if dtype is not None
                else self.forces.to(device=dev)
            ),
            atomic_energies=(
                self.atomic_energies.to(device=dev, dtype=dtype)
                if self.atomic_energies is not None and dtype is not None
                else (self.atomic_energies.to(device=dev) if self.atomic_energies is not None else None)
            ),
            pos_updated=(
                self.pos_updated.to(device=dev, dtype=dtype)
                if self.pos_updated is not None and dtype is not None
                else (self.pos_updated.to(device=dev) if self.pos_updated is not None else None)
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def detach(self) -> GNNForceOutput:
        """Detach all prediction tensors from autograd computation graph."""
        return GNNForceOutput(
            energy=self.energy.detach(),
            forces=self.forces.detach(),
            atomic_energies=(
                self.atomic_energies.detach() if self.atomic_energies is not None else None
            ),
            pos_updated=(
                self.pos_updated.detach() if self.pos_updated is not None else None
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def clone(self) -> GNNForceOutput:
        """Deep copy all prediction tensors."""
        return GNNForceOutput(
            energy=self.energy.clone(),
            forces=self.forces.clone(),
            atomic_energies=(
                self.atomic_energies.clone() if self.atomic_energies is not None else None
            ),
            pos_updated=(
                self.pos_updated.clone() if self.pos_updated is not None else None
            ),
            metadata=copy.deepcopy(self.metadata) if self.metadata is not None else None,
        )

    def as_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary representation."""
        res: Dict[str, Any] = {"energy": self.energy, "forces": self.forces}
        if self.atomic_energies is not None:
            res["atomic_energies"] = self.atomic_energies
        if self.pos_updated is not None:
            res["pos_updated"] = self.pos_updated
        if self.metadata is not None:
            res["metadata"] = self.metadata
        return res

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        raise KeyError(f"Key '{key}' not found or is None in GNNForceOutput.")


# ==============================================================================
# 6. Graph Connectivity & Input Extraction Utilities
# ==============================================================================

def extract_gnn_inputs(
    data: Any,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor]]:
    """Extract standard geometric tensors (pos, z, batch, edge_index, x) immutably [D].

    Supports MolecularData, MolecularBatch, ConformerData, ConformerBatch, and Dict formats.

    Parameters
    ----------
    data : Any
        Input molecular data container or dictionary.

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor]]
        (pos [N, 3], z [N], batch [N], edge_index [2, E] or None, x [N, F] or None)
    """
    if isinstance(data, dict):
        pos = data["pos"]
        z = data["z"]
        batch = data.get("batch")
        edge_index = data.get("edge_index")
        x = data.get("x")
    else:
        pos = getattr(data, "pos")
        z = getattr(data, "z")
        batch = getattr(data, "batch", None)
        edge_index = getattr(data, "edge_index", None)
        x = getattr(data, "x", None)

    if batch is None:
        batch = torch.zeros(pos.size(0), dtype=torch.long, device=pos.device)

    return pos, z, batch, edge_index, x


def build_radius_graph(
    pos: torch.Tensor,
    batch: Optional[torch.Tensor] = None,
    cutoff: float = DEFAULT_RBF_CUTOFF,
    max_num_neighbors: int = 64,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Construct pairwise radius graph within each molecule in a batched representation [D].

    $$\\mathcal{E} = \\{ (i, j) \\mid \\|\\mathbf{r}_i - \\mathbf{r}_j\\| < r_{\\text{cut}}, \\; i \\neq j, \\; \\text{batch}(i) = \\text{batch}(j) \\}$$

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian coordinates [N, 3].
    batch : Optional[torch.Tensor]
        Graph assignment index [N].
    cutoff : float
        Radial cutoff distance in Angstroms [E].
    max_num_neighbors : int
        Maximum allowable neighbors per node [E].

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        (edge_index [2, E], edge_dist [E])
    """
    num_nodes = pos.size(0)
    if num_nodes == 0:
        empty_edges = torch.empty((2, 0), dtype=torch.long, device=pos.device)
        empty_dist = torch.empty((0,), dtype=pos.dtype, device=pos.device)
        return empty_edges, empty_dist

    if batch is None:
        batch = torch.zeros(num_nodes, dtype=torch.long, device=pos.device)

    # Pairwise difference vector [N, N, 3]
    diff = pos.unsqueeze(1) - pos.unsqueeze(0)
    dist = torch.norm(diff, p=2, dim=-1)  # [N, N]

    # Mask strictly within same molecule graph and strictly positive non-zero distance
    same_molecule = batch.unsqueeze(1) == batch.unsqueeze(0)
    mask = (dist < cutoff) & (dist > 1e-7) & same_molecule

    edge_index = mask.nonzero(as_tuple=False).t()  # [2, E]
    edge_dist = dist[mask]

    return edge_index, edge_dist


# ==============================================================================
# 7. Radial Basis Functions & Interaction Layers
# ==============================================================================

class RadialBasisExpansion(nn.Module):
    """Gaussian Radial Basis Function (RBF) expansion with smooth cosine envelope [D].

    $$\\phi_k(d) = \\exp\\left( -\\gamma (d - \\mu_k)^2 \\right) \\cdot f_{\\text{cut}}(d)$$
    $$f_{\\text{cut}}(d) = \\frac{1}{2} \\left( \\cos\\left( \\pi \\frac{d}{r_{\\text{cut}}} \\right) + 1 \\right)$$
    """

    def __init__(
        self,
        num_radial: int = DEFAULT_NUM_RADIAL,
        cutoff: float = DEFAULT_RBF_CUTOFF,
    ) -> None:
        super().__init__()
        self.num_radial = int(num_radial)
        self.cutoff = float(cutoff)

        centers = torch.linspace(0.0, self.cutoff, self.num_radial, dtype=torch.float32)
        self.register_buffer("centers", centers)
        gamma = float(self.num_radial / self.cutoff)
        self.register_buffer("gamma", torch.tensor(gamma, dtype=torch.float32))

    def forward(self, distances: torch.Tensor) -> torch.Tensor:
        """Expand 1D distances into smooth Gaussian basis features [D].

        Parameters
        ----------
        distances : torch.Tensor
            Pairwise Euclidean interatomic distances of shape [..., 1] or [...].

        Returns
        -------
        torch.Tensor
            Radial basis features of shape [..., num_radial].
        """
        if distances.dim() == 1:
            dist_exp = distances.unsqueeze(-1)
        else:
            dist_exp = distances

        # Centers: [num_radial]
        rbf = torch.exp(-self.gamma * (dist_exp - self.centers) ** 2)

        # Smooth polynomial cosine cutoff factor
        clamped_dist = torch.clamp(dist_exp / self.cutoff, max=1.0)
        cutoff_factor = 0.5 * (torch.cos(clamped_dist * math.pi) + 1.0)

        return rbf * cutoff_factor


class BaseGNNLayer(nn.Module, abc.ABC):
    """Abstract base class for 3D Graph Neural Network interaction and message passing layers."""

    @abc.abstractmethod
    def forward(
        self,
        h: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Execute a single layer message passing update immutably [D].

        Parameters
        ----------
        h : torch.Tensor
            Invariant node latent representations [N, hidden].
        pos : torch.Tensor
            Equivariant Cartesian coordinates [N, 3].
        edge_index : torch.Tensor
            Pairwise edge indices [2, E] (src, dst).
        edge_attr : Optional[torch.Tensor]
            Pairwise edge features or RBF expansions [E, D].
        **kwargs : Any
            Additional optional keyword arguments.

        Returns
        -------
        Tuple[torch.Tensor, torch.Tensor]
            Updated invariant node features `h_new` [N, hidden] and
            updated equivariant Cartesian coordinates `pos_new` [N, 3].
        """
        raise NotImplementedError


class Canonical3DInteractionBlock(BaseGNNLayer):
    """Continuous-filter convolutional interaction block (CFConv / SchNet-style) [D].

    Guarantees strict SE(3) invariance of node features and state immutability.
    $$\\mathbf{h}'_i = \\mathbf{h}_i + \\text{MLP}\\left( \\sum_{j \\in \\mathcal{N}(i)} W(d_{ij}) \\odot \\mathbf{h}_j \\right)$$
    """

    def __init__(
        self,
        hidden_channels: int = DEFAULT_HIDDEN_CHANNELS,
        num_radial: int = DEFAULT_NUM_RADIAL,
        activation: str = "silu",
    ) -> None:
        super().__init__()
        act_layer = nn.SiLU() if activation == "silu" else nn.ReLU()

        self.filter_network = nn.Sequential(
            nn.Linear(num_radial, hidden_channels),
            act_layer,
            nn.Linear(hidden_channels, hidden_channels),
        )
        self.atom_linear = nn.Linear(hidden_channels, hidden_channels)
        self.output_linear = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            act_layer,
            nn.Linear(hidden_channels, hidden_channels),
        )

    def forward(
        self,
        h: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Perform continuous-filter convolution message passing immutably [D]."""
        if edge_index.size(1) == 0 or edge_attr is None:
            return h, pos

        src, dst = edge_index[0], edge_index[1]
        w = self.filter_network(edge_attr)
        h_src = self.atom_linear(h)[src]
        messages = h_src * w

        # Scatter add aggregation over destination nodes
        agg = torch.zeros_like(h)
        agg.index_add_(0, dst, messages)

        update = self.output_linear(agg)
        h_new = h + update  # Pure immutable addition

        return h_new, pos


class Equivariant3DInteractionBlock(BaseGNNLayer):
    """Equivariant Graph Neural Network (EGNN) coordinate and feature update layer [D].

    Guarantees exact SE(3)/E(3) equivariance for coordinates and invariance for node representations:
    $$\\mathbf{m}_{ij} = \\phi_m(\\mathbf{h}_i, \\mathbf{h}_j, \\|\\mathbf{r}_i - \\mathbf{r}_j\\|^2)$$
    $$\\mathbf{r}'_i = \\mathbf{r}_i + \\sum_{j \\in \\mathcal{N}(i)} (\\mathbf{r}_i - \\mathbf{r}_j) \\phi_x(\\mathbf{m}_{ij})$$
    $$\\mathbf{h}'_i = \\mathbf{h}_i + \\phi_h(\\mathbf{h}_i, \\sum_{j \\in \\mathcal{N}(i)} \\mathbf{m}_{ij})$$
    """

    def __init__(
        self,
        hidden_channels: int = DEFAULT_HIDDEN_CHANNELS,
        edge_feat_dim: int = 0,
        activation: str = "silu",
    ) -> None:
        super().__init__()
        act_layer = nn.SiLU() if activation == "silu" else nn.ReLU()

        self.message_mlp = nn.Sequential(
            nn.Linear(hidden_channels * 2 + 1 + edge_feat_dim, hidden_channels),
            act_layer,
            nn.Linear(hidden_channels, hidden_channels),
            act_layer,
        )
        self.coord_mlp = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            act_layer,
            nn.Linear(hidden_channels, 1, bias=False),
        )
        self.node_mlp = nn.Sequential(
            nn.Linear(hidden_channels * 2, hidden_channels),
            act_layer,
            nn.Linear(hidden_channels, hidden_channels),
        )

    def forward(
        self,
        h: torch.Tensor,
        pos: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
        **kwargs: Any,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Perform equivariant coordinate and invariant feature message passing [D]."""
        if edge_index.size(1) == 0:
            return h, pos

        src, dst = edge_index[0], edge_index[1]
        diff = pos[src] - pos[dst]  # [E, 3]
        dist_sq = (diff**2).sum(dim=-1, keepdim=True)  # [E, 1]

        if edge_attr is not None:
            msg_input = torch.cat([h[src], h[dst], dist_sq, edge_attr], dim=-1)
        else:
            msg_input = torch.cat([h[src], h[dst], dist_sq], dim=-1)

        msg = self.message_mlp(msg_input)  # [E, hidden]

        # 1. Equivariant Coordinate Update
        coord_weights = self.coord_mlp(msg)  # [E, 1]
        coord_messages = diff * coord_weights  # [E, 3]
        coord_agg = torch.zeros_like(pos)
        coord_agg.index_add_(0, dst, coord_messages)
        pos_new = pos + coord_agg  # Pure immutable addition [E]

        # 2. Invariant Node Feature Update
        node_agg = torch.zeros_like(h)
        node_agg.index_add_(0, dst, msg)
        h_new = h + self.node_mlp(torch.cat([h, node_agg], dim=-1))

        return h_new, pos_new


# ==============================================================================
# 8. Abstract Base Class: Base3DGNN
# ==============================================================================

class Base3DGNN(nn.Module, abc.ABC):
    """Authoritative Abstract Base Class for 3D Molecular Graph Neural Networks in CoChem.

    Enforces:
    1. `forward(data) -> GNNOutput` forward energy evaluation signature.
    2. `compute_forces(data) -> GNNForceOutput` analytical force gradient derivation via autograd.
    3. SE(3) equivariance / invariance guarantees and pure state immutability.
    """

    def __init__(self, config: Optional[GNNModelConfig] = None) -> None:
        super().__init__()
        self.config: GNNModelConfig = config if config is not None else GNNModelConfig()
        self.cutoff: float = float(self.config.cutoff)

    @abc.abstractmethod
    def forward(
        self,
        data: Any,
    ) -> GNNOutput:
        """Forward pass predicting total molecular electronic potential energy [D].

        Parameters
        ----------
        data : Any
            Molecular graph container (MolecularData, MolecularBatch, ConformerData, ConformerBatch, or Dict).

        Returns
        -------
        GNNOutput
            Dataclass container with predicted energy and latent node representations.
        """
        raise NotImplementedError

    def compute_forces(
        self,
        data: Any,
    ) -> GNNForceOutput:
        """Compute analytical interatomic forces as the negative Cartesian gradient of energy [D].

        $$\\mathbf{F}_i = -\\nabla_{\\mathbf{r}_i} E_{\\text{total}} = -\\frac{\\partial E}{\\partial \\mathbf{r}_i}$$

        Guarantees exact SE(3) equivariance:
        $$\\mathbf{F}(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) = \\mathbf{F}(\\mathbf{r}) \\mathbf{R}^T$$

        Parameters
        ----------
        data : Any
            Input molecular data structure.

        Returns
        -------
        GNNForceOutput
            Dataclass containing predicted energy and analytical vector forces [N, 3].
        """
        if isinstance(data, dict):
            orig_pos = data["pos"]
        else:
            orig_pos = getattr(data, "pos")

        # Create cloned coordinate tensor requiring autograd gradients
        pos = orig_pos.clone().detach().requires_grad_(True)

        # Clone data container immutably with active grad coordinate tensor
        if isinstance(data, dict):
            data_grad = dict(data)
            data_grad["pos"] = pos
        else:
            data_grad = copy.copy(data)
            setattr(data_grad, "pos", pos)

        with torch.enable_grad():
            out = self.forward(data_grad)
            energy = out.energy

            # Analytical force derivation: F = - dE / dr
            forces = -torch.autograd.grad(
                outputs=energy.sum(),
                inputs=pos,
                create_graph=self.training,
                retain_graph=self.training,
            )[0]

        return GNNForceOutput(
            energy=energy,
            forces=forces,
            atomic_energies=out.atomic_energies,
            pos_updated=out.pos_updated,
            metadata=out.metadata,
        )

    def build_radius_graph(
        self,
        pos: torch.Tensor,
        batch: Optional[torch.Tensor] = None,
        cutoff: Optional[float] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Construct pairwise radius graph using model cutoff distance [D]."""
        c = cutoff if cutoff is not None else self.cutoff
        return build_radius_graph(pos, batch=batch, cutoff=c)

    def get_num_parameters(self, trainable_only: bool = True) -> int:
        """Calculate total number of model parameters [D]."""
        if trainable_only:
            return sum(p.numel() for p in self.parameters() if p.requires_grad)
        return sum(p.numel() for p in self.parameters())

    def get_device(self) -> torch.device:
        """Query host device of model parameters."""
        try:
            return next(self.parameters()).device
        except StopIteration:
            return torch.device("cpu")

    def get_dtype(self) -> torch.dtype:
        """Query floating point precision dtype of model parameters."""
        try:
            return next(self.parameters()).dtype
        except StopIteration:
            return torch.float32

    def verify_equivariance(
        self,
        data: Any,
        rotation_matrix: Optional[torch.Tensor] = None,
        translation_vector: Optional[torch.Tensor] = None,
        atol: float = 1e-4,
    ) -> Dict[str, Any]:
        """Verify SE(3) invariance and equivariance properties on this model instance [D]."""
        return verify_se3_equivariance(
            model=self,
            data=data,
            rotation_matrix=rotation_matrix,
            translation_vector=translation_vector,
            atol=atol,
        )


# ==============================================================================
# 9. Concrete Production Architectures
# ==============================================================================

class Canonical3DGNN(Base3DGNN):
    """Production-grade continuous-filter 3D Graph Neural Network (CFConv / SchNet) [D].

    Adheres strictly to the Zero-Mock mandate and Method Matrix v4.
    """

    def __init__(self, config: Optional[GNNModelConfig] = None) -> None:
        super().__init__(config)
        cfg = self.config

        self.embedding = nn.Embedding(cfg.max_z + 1, cfg.hidden_channels)
        self.rbf = RadialBasisExpansion(num_radial=cfg.num_radial, cutoff=cfg.cutoff)

        self.interactions = nn.ModuleList([
            Canonical3DInteractionBlock(
                hidden_channels=cfg.hidden_channels,
                num_radial=cfg.num_radial,
                activation=cfg.activation,
            )
            for _ in range(cfg.num_layers)
        ])

        act_layer = nn.SiLU() if cfg.activation == "silu" else nn.ReLU()
        self.readout = nn.Sequential(
            nn.Linear(cfg.hidden_channels, cfg.hidden_channels // 2),
            act_layer,
            nn.Linear(cfg.hidden_channels // 2, 1),
        )

    def forward(
        self,
        data: Any,
    ) -> GNNOutput:
        """Execute forward energy computation [D]."""
        pos, z, batch, edge_index, _ = extract_gnn_inputs(data)

        if edge_index is None or edge_index.size(1) == 0:
            edge_index, edge_dist = self.build_radius_graph(pos, batch)
        else:
            diff = pos[edge_index[0]] - pos[edge_index[1]]
            edge_dist = torch.norm(diff, p=2, dim=-1)

        h = self.embedding(z)

        if edge_index.size(1) > 0:
            edge_rbf = self.rbf(edge_dist)
            for interaction in self.interactions:
                h, _ = interaction(h, pos, edge_index, edge_rbf)

        atomic_energies = self.readout(h)  # [N, 1]

        # Aggregate atomic contributions per graph in batch
        num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
        total_energy = torch.zeros((num_graphs, 1), dtype=pos.dtype, device=pos.device)

        if self.config.aggr == "mean":
            counts = torch.zeros((num_graphs, 1), dtype=pos.dtype, device=pos.device)
            ones = torch.ones_like(atomic_energies)
            total_energy.index_add_(0, batch, atomic_energies)
            counts.index_add_(0, batch, ones)
            total_energy = total_energy / torch.clamp(counts, min=1.0)
        else:
            total_energy.index_add_(0, batch, atomic_energies)

        return GNNOutput(
            energy=total_energy,
            atomic_energies=atomic_energies,
            node_features=h,
            pos_updated=pos,
        )


class Equivariant3DGNN(Base3DGNN):
    """Production-grade Equivariant Graph Neural Network (EGNN) architecture [D].

    Guarantees SE(3) / E(3) coordinate update equivariance and energy invariance.
    """

    def __init__(self, config: Optional[GNNModelConfig] = None) -> None:
        super().__init__(config)
        cfg = self.config

        self.embedding = nn.Embedding(cfg.max_z + 1, cfg.hidden_channels)

        self.layers = nn.ModuleList([
            Equivariant3DInteractionBlock(
                hidden_channels=cfg.hidden_channels,
                activation=cfg.activation,
            )
            for _ in range(cfg.num_layers)
        ])

        act_layer = nn.SiLU() if cfg.activation == "silu" else nn.ReLU()
        self.readout = nn.Sequential(
            nn.Linear(cfg.hidden_channels, cfg.hidden_channels // 2),
            act_layer,
            nn.Linear(cfg.hidden_channels // 2, 1),
        )

    def forward(
        self,
        data: Any,
    ) -> GNNOutput:
        """Execute equivariant forward pass updating features and coordinates [D]."""
        pos, z, batch, edge_index, _ = extract_gnn_inputs(data)

        if edge_index is None or edge_index.size(1) == 0:
            edge_index, _ = self.build_radius_graph(pos, batch)

        h = self.embedding(z)
        cur_pos = pos

        for layer in self.layers:
            h, cur_pos = layer(h, cur_pos, edge_index)

        atomic_energies = self.readout(h)  # [N, 1]

        num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
        total_energy = torch.zeros((num_graphs, 1), dtype=pos.dtype, device=pos.device)

        if self.config.aggr == "mean":
            counts = torch.zeros((num_graphs, 1), dtype=pos.dtype, device=pos.device)
            ones = torch.ones_like(atomic_energies)
            total_energy.index_add_(0, batch, atomic_energies)
            counts.index_add_(0, batch, ones)
            total_energy = total_energy / torch.clamp(counts, min=1.0)
        else:
            total_energy.index_add_(0, batch, atomic_energies)

        return GNNOutput(
            energy=total_energy,
            atomic_energies=atomic_energies,
            node_features=h,
            pos_updated=cur_pos,
        )


# ==============================================================================
# 10. Mathematical Equivariance & Invariance Verification Engine
# ==============================================================================

def verify_se3_equivariance(
    model: Base3DGNN,
    data: Any,
    rotation_matrix: Optional[torch.Tensor] = None,
    translation_vector: Optional[torch.Tensor] = None,
    atol: float = 1e-4,
) -> Dict[str, Any]:
    """Mathematically verify SE(3) / E(3) equivariance and invariance properties of a 3D GNN [D].

    Verifies:
    1. Energy Invariance: $|E(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) - E(\\mathbf{r})| < \\epsilon$ [M]
    2. Force Equivariance: $\\|\\mathbf{F}(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) - \\mathbf{F}(\\mathbf{r}) \\mathbf{R}^T\\| < \\epsilon$ [D]
    3. Coordinate Equivariance: $\\|\\mathbf{r}'(\\mathbf{r} \\mathbf{R}^T + \\mathbf{t}) - (\\mathbf{r}'(\\mathbf{r}) \\mathbf{R}^T + \\mathbf{t})\\| < \\epsilon$ [D]
    4. Force Conservation: $\\|\\sum_{i=1}^N \\mathbf{F}_i\\| < \\epsilon$ [M]

    Parameters
    ----------
    model : Base3DGNN
        Instantiated 3D Graph Neural Network model.
    data : Any
        Input molecular data container.
    rotation_matrix : Optional[torch.Tensor]
        Orthogonal SO(3) 3x3 rotation matrix. Generated randomly if None.
    translation_vector : Optional[torch.Tensor]
        3D translation vector [3]. Generated randomly if None.
    atol : float
        Absolute tolerance bound for float32 tensor equality [E].

    Returns
    -------
    Dict[str, Any]
        Verification report with error norms and boolean pass flags.
    """
    orig_training = model.training
    model.eval()

    pos, z, batch, _, _ = extract_gnn_inputs(data)
    device = pos.device
    dtype = pos.dtype

    if rotation_matrix is None:
        rotation_matrix = generate_random_so3_rotation(dtype=dtype, device=device)
    else:
        rotation_matrix = rotation_matrix.to(device=device, dtype=dtype)

    if translation_vector is None:
        translation_vector = torch.randn(3, dtype=dtype, device=device)
    else:
        translation_vector = translation_vector.to(device=device, dtype=dtype)

    # 1. Evaluate un-transformed baseline
    force_out_base = model.compute_forces(data)
    energy_base = force_out_base.energy.detach()
    forces_base = force_out_base.forces.detach()
    pos_updated_base = force_out_base.pos_updated.detach() if force_out_base.pos_updated is not None else None

    # 2. Transform input coordinates: r_trans = r @ R.T + t
    pos_trans = rotate_coordinates(pos, rotation_matrix) + translation_vector.view(1, 3)

    if isinstance(data, dict):
        data_trans = dict(data)
        data_trans["pos"] = pos_trans
    else:
        data_trans = copy.copy(data)
        setattr(data_trans, "pos", pos_trans)

    # 3. Evaluate transformed structure
    force_out_trans = model.compute_forces(data_trans)
    energy_trans = force_out_trans.energy.detach()
    forces_trans = force_out_trans.forces.detach()
    pos_updated_trans = force_out_trans.pos_updated.detach() if force_out_trans.pos_updated is not None else None

    # 4. Check Energy Invariance
    energy_diff = torch.abs(energy_trans - energy_base).max().item()
    energy_invariant = bool(energy_diff < atol)

    # 5. Check Force Equivariance: F_expected = F_base @ R.T
    expected_forces = rotate_coordinates(forces_base, rotation_matrix)
    force_diff = torch.norm(forces_trans - expected_forces, p=2, dim=-1).max().item()
    force_equivariant = bool(force_diff < atol)

    # 6. Check Force Conservation (Translational invariance -> zero net force for isolated system)
    net_force = torch.norm(forces_base.sum(dim=0), p=2).item()
    forces_conserved = bool(net_force < atol * 10.0)

    # 7. Check Coordinate Equivariance (if updated)
    coord_diff = 0.0
    coord_equivariant = True
    if pos_updated_base is not None and pos_updated_trans is not None:
        expected_pos_trans = rotate_coordinates(pos_updated_base, rotation_matrix) + translation_vector.view(1, 3)
        coord_diff = torch.norm(pos_updated_trans - expected_pos_trans, p=2, dim=-1).max().item()
        coord_equivariant = bool(coord_diff < atol)

    model.train(orig_training)

    return {
        "energy_invariant": energy_invariant,
        "energy_max_diff": energy_diff,
        "force_equivariant": force_equivariant,
        "force_max_diff": force_diff,
        "coord_equivariant": coord_equivariant,
        "coord_max_diff": coord_diff,
        "forces_conserved": forces_conserved,
        "net_force_norm": net_force,
        "tolerance": atol,
        "all_passed": bool(
            energy_invariant and force_equivariant and coord_equivariant and forces_conserved
        ),
    }
