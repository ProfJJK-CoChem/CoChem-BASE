"""CoChem-GEOM: Molecular Data Featurizer and Geometric Deep Learning Data Contract.
=====================================================================================
Establishes the definitive data contract, Pydantic v2 validation models, and
PyTorch geometric tensor representations for rotational spectroscopy, quantum chemistry,
and equivariant neural network architectures.

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & monoisotopic resolution (No hardcoding)
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import torch


# ==============================================================================
# 1. Fundamental Physical Constants and Conversion Factors (CODATA 2018/2022)
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
"""Conversion factor from Hartree to kilocalories per mole [D]."""

KCAL_MOL_TO_HARTREE: float = 1.0 / HARTREE_TO_KCAL_MOL
"""Conversion factor from kilocalories per mole to Hartree [D]."""

KCAL_MOL_TO_EV: float = 0.04336411530877
"""Conversion factor from kilocalories per mole to electron-volts [D]."""

EV_TO_KCAL_MOL: float = 1.0 / KCAL_MOL_TO_EV
"""Conversion factor from electron-volts to kilocalories per mole [D]."""

HARTREE_TO_KJ_MOL: float = 2625.4996394799
"""Conversion factor from Hartree to kilojoules per mole [D]."""

EV_TO_CM_MINUS_ONE: float = 8065.54429
"""Conversion factor from electron-volts to wavenumbers (cm^-1) [D]."""

ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ: float = 505379.008784
"""Spectroscopic rotational constant conversion factor in MHz * u * Angstrom^2 [D]."""

STANDARD_TEMPERATURE_K: float = 298.15
"""Standard ambient temperature in Kelvin (25 deg C) [M]."""

DEFAULT_GRAPH_CUTOFF_ANGSTROM: float = 5.0
"""Default interatomic graph neighborhood cutoff in Angstroms [E]."""

DEFAULT_MAX_NEIGHBORS: int = 32
"""Default maximum neighbors per atom in radius graph [E]."""


# ==============================================================================
# 2. Deterministic Element and Atomic Typing Mappings
# ==============================================================================

SYMBOL_TO_ATOMIC_NUMBER: Dict[str, int] = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8,
    "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16,
    "Cl": 17, "Ar": 18, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24,
    "Mn": 25, "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32,
    "As": 33, "Se": 34, "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "Y": 39, "Zr": 40,
    "Nb": 41, "Mo": 42, "Tc": 43, "Ru": 44, "Rh": 45, "Pd": 46, "Ag": 47, "Cd": 48,
    "In": 49, "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "Xe": 54, "Cs": 55, "Ba": 56,
    "La": 57, "Ce": 58, "Pr": 59, "Nd": 60, "Pm": 61, "Sm": 62, "Eu": 63, "Gd": 64,
    "Tb": 65, "Dy": 66, "Ho": 67, "Er": 68, "Tm": 69, "Yb": 70, "Lu": 71, "Hf": 72,
    "Ta": 73, "W": 74, "Re": 75, "Os": 76, "Ir": 77, "Pt": 78, "Au": 79, "Hg": 80,
    "Tl": 81, "Pb": 82, "Bi": 83, "Po": 84, "At": 85, "Rn": 86, "Fr": 87, "Ra": 88,
    "Ac": 89, "Th": 90, "Pa": 91, "U": 92, "Np": 93, "Pu": 94, "Am": 95, "Cm": 96,
    "Bk": 97, "Cf": 98, "Es": 99, "Fm": 100, "Md": 101, "No": 102, "Lr": 103,
    "Rf": 104, "Db": 105, "Sg": 106, "Bh": 107, "Hs": 108, "Mt": 109, "Ds": 110,
    "Rg": 111, "Cn": 112, "Nh": 113, "Fl": 114, "Mc": 115, "Lv": 116, "Ts": 117, "Og": 118,
}
"""Deterministic mapping from IUPAC chemical symbols to atomic numbers Z."""

ATOMIC_NUMBER_TO_SYMBOL: Dict[int, str] = {
    z: sym for sym, z in SYMBOL_TO_ATOMIC_NUMBER.items()
}
"""Deterministic reverse mapping from atomic number Z to chemical symbol."""

DEFAULT_ELEMENT_TYPES: Dict[str, int] = {
    "H": 0,
    "C": 1,
    "N": 2,
    "O": 3,
    "F": 4,
    "P": 5,
    "S": 6,
    "Cl": 7,
    "Br": 8,
    "I": 9,
}
"""Deterministic 10-class core element type index mapping for organic and bio-inorganic systems."""

ELEMENT_TYPE_TO_INDEX: Dict[str, int] = dict(DEFAULT_ELEMENT_TYPES)
"""Alias for element type mapping."""

INDEX_TO_ELEMENT_TYPE: Dict[int, str] = {
    idx: sym for sym, idx in DEFAULT_ELEMENT_TYPES.items()
}
"""Reverse index-to-symbol mapping for core element types."""


# ==============================================================================
# 3. Dynamic Mendeleev Mass and Property Resolution Functions
# ==============================================================================


def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons (atomic mass units).
    """
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query exact mass of most abundant natural isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.

    Returns
    -------
    float
        Monoisotopic mass in Daltons to full precision.
    """
    el = element(symbol_or_z)
    if el.isotopes:
        most_abundant = max(
            el.isotopes,
            key=lambda iso: (iso.abundance if iso.abundance is not None else 0.0),
        )
        if most_abundant.mass is not None:
            return float(most_abundant.mass)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    raise ValueError(f"Monoisotopic mass not found for element '{symbol_or_z}'")


def get_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically query exact mass of a specific isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.
    mass_number : int
        Isotopic mass number A (protons + neutrons), e.g., 12 for C-12, 13 for C-13.

    Returns
    -------
    float
        Exact isotopic mass in Daltons.
    """
    el = element(symbol_or_z)
    for iso in el.isotopes:
        if iso.mass_number == mass_number:
            if iso.mass is not None:
                return float(iso.mass)
            return float(iso.mass_number)
    raise ValueError(
        f"Isotope with mass number {mass_number} not found for element '{symbol_or_z}'"
    )


def get_covalent_radius_angstrom(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Pyykko covalent single-bond radius in Angstroms [M]."""
    el = element(symbol_or_z)
    if el.covalent_radius_pyykko is not None:
        return float(el.covalent_radius_pyykko) / 100.0
    if el.covalent_radius_cordero is not None:
        return float(el.covalent_radius_cordero) / 100.0
    if el.covalent_radius_bragg is not None:
        return float(el.covalent_radius_bragg) / 100.0
    return 1.0


def get_pauling_electronegativity(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Pauling electronegativity from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.en_pauling is not None:
        return float(el.en_pauling)
    return 0.0


def get_vdw_radius_angstrom(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Van der Waals radius in Angstroms [M]."""
    el = element(symbol_or_z)
    if el.vdw_radius_alvarez is not None:
        return float(el.vdw_radius_alvarez) / 100.0
    if el.vdw_radius is not None:
        return float(el.vdw_radius) / 100.0
    return 1.7


# ==============================================================================
# 4. Energy Conversion Pure Functions
# ==============================================================================


def hartree_to_ev(energy_hartree: float) -> float:
    """Convert energy from Hartree to electron-volts [D]."""
    return energy_hartree * HARTREE_TO_EV


def ev_to_hartree(energy_ev: float) -> float:
    """Convert energy from electron-volts to Hartree [D]."""
    return energy_ev * EV_TO_HARTREE


def hartree_to_kcal_mol(energy_hartree: float) -> float:
    """Convert energy from Hartree to kcal/mol [D]."""
    return energy_hartree * HARTREE_TO_KCAL_MOL


def kcal_mol_to_hartree(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to Hartree [D]."""
    return energy_kcal_mol * KCAL_MOL_TO_HARTREE


def kcal_mol_to_ev(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to electron-volts [D]."""
    return energy_kcal_mol * KCAL_MOL_TO_EV


def ev_to_kcal_mol(energy_ev: float) -> float:
    """Convert energy from electron-volts to kcal/mol [D]."""
    return energy_ev * EV_TO_KCAL_MOL


# ==============================================================================
# 5. Pydantic v2 Data Contract Models
# ==============================================================================


class MolecularGraphConfig(BaseModel):
    """Pydantic v2 configuration model for molecular graph featurization."""

    cutoff_radius: float = Field(
        default=DEFAULT_GRAPH_CUTOFF_ANGSTROM,
        ge=0.1,
        le=50.0,
        description="Graph neighborhood radial cutoff distance in Angstroms [E]",
    )
    max_neighbors: Optional[int] = Field(
        default=DEFAULT_MAX_NEIGHBORS,
        ge=1,
        le=1024,
        description="Maximum incoming neighbor edges per atom node [E]",
    )
    include_charges: bool = Field(
        default=True,
        description="Include formal/partial atomic charges in node feature vector [D]",
    )
    include_masses: bool = Field(
        default=True,
        description="Include dynamically retrieved atomic masses in node features [M]",
    )
    include_covalent_radii: bool = Field(
        default=True,
        description="Include covalent radii in node features [M]",
    )
    include_electronegativity: bool = Field(
        default=True,
        description="Include Pauling electronegativity in node features [M]",
    )
    include_edge_distances: bool = Field(
        default=True,
        description="Include Euclidean interatomic distances in edge features [D]",
    )
    include_edge_vectors: bool = Field(
        default=False,
        description="Include directed displacement vectors in edge features [D]",
    )
    include_edge_rbf: bool = Field(
        default=True,
        description="Expand interatomic distances via Gaussian radial basis functions [D]",
    )
    num_rbf: int = Field(
        default=16,
        ge=2,
        le=256,
        description="Number of Gaussian radial basis function centers [E]",
    )
    rbf_gamma: Optional[float] = Field(
        default=None,
        description="Gaussian radial basis function kernel width parameter [E]",
    )
    directed: bool = Field(
        default=True,
        description="Construct directed pairwise edge graph (i->j and j->i)",
    )
    self_loops: bool = Field(
        default=False,
        description="Include self-loop edges (i->i) in graph connectivity",
    )
    dtype: str = Field(
        default="float32",
        description="Target floating point precision: 'float32' or 'float64'",
    )
    device: str = Field(
        default="cpu",
        description="Target PyTorch device: 'cpu' or 'cuda'",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )


class MolecularInput(BaseModel):
    """Pydantic v2 input data contract representing a valid molecular structure."""

    symbols: List[str] = Field(
        ...,
        min_length=1,
        description="List of IUPAC chemical element symbols (N atoms)",
    )
    positions: List[List[float]] = Field(
        ...,
        min_length=1,
        description="Cartesian coordinates in Angstroms of shape (N, 3) [M]",
    )
    atomic_numbers: Optional[List[int]] = Field(
        default=None,
        description="Optional pre-computed atomic numbers Z (N,)",
    )
    formal_charges: Optional[List[int]] = Field(
        default=None,
        description="Formal atomic charges per atom (N,) [D]",
    )
    partial_charges: Optional[List[float]] = Field(
        default=None,
        description="Partial atomic charges per atom (N,) [D]",
    )
    masses: Optional[List[float]] = Field(
        default=None,
        description="Atomic masses in Daltons (N,) [M]",
    )
    total_charge: int = Field(
        default=0,
        description="Total molecular net charge [D]",
    )
    spin_multiplicity: int = Field(
        default=1,
        ge=1,
        description="Total spin multiplicity (2S + 1) [D]",
    )
    energy: Optional[float] = Field(
        default=None,
        description="Ground-state electronic energy in Hartree or eV [D]",
    )
    forces: Optional[List[List[float]]] = Field(
        default=None,
        description="Atomic force vectors of shape (N, 3) in eV/Angstrom [D]",
    )
    dipole: Optional[List[float]] = Field(
        default=None,
        description="Electric dipole moment vector (3,) in Debye [D]",
    )
    rotational_constants: Optional[List[float]] = Field(
        default=None,
        description="Rotational constants (A, B, C) in MHz [D]",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Statistical or Boltzmann weighting factor [D]",
    )
    tags: Dict[str, str] = Field(
        default_factory=dict,
        description="User metadata and provenance annotation tags",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="forbid",
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        for sym in v:
            clean_sym = sym.capitalize()
            if clean_sym not in SYMBOL_TO_ATOMIC_NUMBER:
                raise ValueError(f"Unrecognized chemical element symbol: '{sym}'")
        return [s.capitalize() for s in v]

    @field_validator("positions")
    @classmethod
    def validate_positions(cls, v: List[List[float]]) -> List[List[float]]:
        for row_idx, coord in enumerate(v):
            if len(coord) != 3:
                raise ValueError(
                    f"Position at index {row_idx} has dimension {len(coord)}; exactly 3 required."
                )
        return v

    @model_validator(mode="after")
    def validate_matching_lengths(self) -> MolecularInput:
        n_atoms = len(self.symbols)
        if len(self.positions) != n_atoms:
            raise ValueError(
                f"Symbols length ({n_atoms}) does not match positions length ({len(self.positions)})."
            )
        if self.forces is not None:
            if len(self.forces) != n_atoms:
                raise ValueError(
                    f"Forces length ({len(self.forces)}) does not match positions length ({n_atoms})."
                )
            for f in self.forces:
                if len(f) != 3:
                    raise ValueError("Each force vector must have dimension 3.")
        if self.dipole is not None and len(self.dipole) != 3:
            raise ValueError(f"Dipole moment must have dimension 3; got {len(self.dipole)}.")
        if self.rotational_constants is not None and len(self.rotational_constants) != 3:
            raise ValueError(
                f"Rotational constants must have dimension 3 (A, B, C); got {len(self.rotational_constants)}."
            )
        return self


# ==============================================================================
# 6. Tensor Schema: MolecularData Container
# ==============================================================================


class MolecularData:
    """Canonical geometric PyTorch data container for molecular structures.

    Attributes
    ----------
    z : torch.Tensor
        Atomic numbers Z of shape (N,) with dtype torch.long.
    pos : torch.Tensor
        Spatial Cartesian coordinates in Angstroms of shape (N, 3).
    edge_index : torch.Tensor
        Graph connectivity edge indices of shape (2, E) with dtype torch.long.
    y : Optional[torch.Tensor]
        Scalar target properties (e.g. energy) of shape (1, ...).
    x : Optional[torch.Tensor]
        Non-spatial invariant node features of shape (N, F).
    edge_attr : Optional[torch.Tensor]
        Edge feature attributes of shape (E, D).
    weight : torch.Tensor
        Statistical weighting factor of shape (1,).
    forces : Optional[torch.Tensor]
        Spatial vector forces of shape (N, 3).
    dipole : Optional[torch.Tensor]
        Dipole vector of shape (3,) or (1, 3).
    rotational_constants : Optional[torch.Tensor]
        Rotational constants (A, B, C) of shape (3,).
    symbols : List[str]
        IUPAC chemical symbols of length N.
    metadata : Dict[str, Any]
        Arbitrary metadata dictionary.
    """

    def __init__(
        self,
        z: torch.Tensor,
        pos: torch.Tensor,
        edge_index: Optional[torch.Tensor] = None,
        y: Optional[torch.Tensor] = None,
        x: Optional[torch.Tensor] = None,
        edge_attr: Optional[torch.Tensor] = None,
        weight: Optional[torch.Tensor] = None,
        forces: Optional[torch.Tensor] = None,
        dipole: Optional[torch.Tensor] = None,
        rotational_constants: Optional[torch.Tensor] = None,
        symbols: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.z = z
        self.pos = pos
        self.edge_index = (
            edge_index
            if edge_index is not None
            else torch.empty((2, 0), dtype=torch.long, device=pos.device)
        )
        self.y = y
        self.x = x
        self.edge_attr = edge_attr
        self.weight = (
            weight
            if weight is not None
            else torch.tensor([1.0], dtype=pos.dtype, device=pos.device)
        )
        self.forces = forces
        self.dipole = dipole
        self.rotational_constants = rotational_constants
        self.symbols = symbols if symbols is not None else [
            ATOMIC_NUMBER_TO_SYMBOL.get(int(zi.item()), "X") for zi in z
        ]
        self.metadata = metadata if metadata is not None else {}

    @property
    def num_nodes(self) -> int:
        """Total number of atom nodes N in the molecular structure."""
        return int(self.pos.size(0))

    @property
    def num_edges(self) -> int:
        """Total number of directed graph edges E."""
        return int(self.edge_index.size(1)) if self.edge_index is not None else 0

    @property
    def atomic_numbers(self) -> torch.Tensor:
        """Alias for atomic numbers tensor z."""
        return self.z

    def clone(self) -> MolecularData:
        """Create an independent deep copy of all tensors and attributes."""
        return MolecularData(
            z=self.z.clone(),
            pos=self.pos.clone(),
            edge_index=self.edge_index.clone() if self.edge_index is not None else None,
            y=self.y.clone() if self.y is not None else None,
            x=self.x.clone() if self.x is not None else None,
            edge_attr=self.edge_attr.clone() if self.edge_attr is not None else None,
            weight=self.weight.clone() if self.weight is not None else None,
            forces=self.forces.clone() if self.forces is not None else None,
            dipole=self.dipole.clone() if self.dipole is not None else None,
            rotational_constants=(
                self.rotational_constants.clone()
                if self.rotational_constants is not None
                else None
            ),
            symbols=list(self.symbols),
            metadata=dict(self.metadata),
        )

    def to(
        self,
        device: Optional[Union[str, torch.device]] = None,
        dtype: Optional[torch.dtype] = None,
    ) -> MolecularData:
        """Transfer tensor attributes to specified device and dtype immutably."""
        new_pos = self.pos.to(device=device, dtype=dtype) if dtype is not None else self.pos.to(device=device)
        new_z = self.z.to(device=device)
        new_edge_index = self.edge_index.to(device=device) if self.edge_index is not None else None
        new_y = (
            self.y.to(device=device, dtype=dtype)
            if self.y is not None and dtype is not None
            else (self.y.to(device=device) if self.y is not None else None)
        )
        new_x = (
            self.x.to(device=device, dtype=dtype)
            if self.x is not None and dtype is not None
            else (self.x.to(device=device) if self.x is not None else None)
        )
        new_edge_attr = (
            self.edge_attr.to(device=device, dtype=dtype)
            if self.edge_attr is not None and dtype is not None
            else (self.edge_attr.to(device=device) if self.edge_attr is not None else None)
        )
        new_weight = (
            self.weight.to(device=device, dtype=dtype)
            if self.weight is not None and dtype is not None
            else (self.weight.to(device=device) if self.weight is not None else None)
        )
        new_forces = (
            self.forces.to(device=device, dtype=dtype)
            if self.forces is not None and dtype is not None
            else (self.forces.to(device=device) if self.forces is not None else None)
        )
        new_dipole = (
            self.dipole.to(device=device, dtype=dtype)
            if self.dipole is not None and dtype is not None
            else (self.dipole.to(device=device) if self.dipole is not None else None)
        )
        new_rot_consts = (
            self.rotational_constants.to(device=device, dtype=dtype)
            if self.rotational_constants is not None and dtype is not None
            else (self.rotational_constants.to(device=device) if self.rotational_constants is not None else None)
        )

        return MolecularData(
            z=new_z,
            pos=new_pos,
            edge_index=new_edge_index,
            y=new_y,
            x=new_x,
            edge_attr=new_edge_attr,
            weight=new_weight,
            forces=new_forces,
            dipole=new_dipole,
            rotational_constants=new_rot_consts,
            symbols=list(self.symbols),
            metadata=dict(self.metadata),
        )

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"Key '{key}' not present in MolecularData.")

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) and getattr(self, key) is not None

    def keys(self) -> List[str]:
        all_keys = [
            "z", "pos", "edge_index", "y", "x", "edge_attr",
            "weight", "forces", "dipole", "rotational_constants", "symbols", "metadata"
        ]
        return [k for k in all_keys if getattr(self, k) is not None]

    def items(self) -> List[Tuple[str, Any]]:
        return [(k, getattr(self, k)) for k in self.keys()]

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.keys()}

    def __repr__(self) -> str:
        attrs = [f"num_nodes={self.num_nodes}", f"num_edges={self.num_edges}"]
        if self.y is not None:
            attrs.append(f"y={list(self.y.shape)}")
        if self.x is not None:
            attrs.append(f"x={list(self.x.shape)}")
        if self.edge_attr is not None:
            attrs.append(f"edge_attr={list(self.edge_attr.shape)}")
        return f"MolecularData({', '.join(attrs)})"


# ==============================================================================
# 7. Pure Graph Construction and Radial Basis Functions
# ==============================================================================


def build_radius_graph(
    pos: torch.Tensor,
    cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    max_neighbors: Optional[int] = DEFAULT_MAX_NEIGHBORS,
    directed: bool = True,
    self_loops: bool = False,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Pure PyTorch radius neighborhood graph construction.

    Parameters
    ----------
    pos : torch.Tensor
        Cartesian atomic coordinates of shape (N, 3).
    cutoff : float
        Interatomic distance cutoff in Angstroms [E].
    max_neighbors : Optional[int]
        Maximum allowed neighbor edges per node [E].
    directed : bool
        If True, returns directed pairs (i, j).
    self_loops : bool
        If True, includes diagonal self-loops (i, i).

    Returns
    -------
    Tuple[torch.Tensor, torch.Tensor]
        edge_index of shape (2, E) and edge_distances of shape (E, 1) [D].
    """
    n_nodes = pos.size(0)
    if n_nodes <= 1:
        return (
            torch.empty((2, 0), dtype=torch.long, device=pos.device),
            torch.empty((0, 1), dtype=pos.dtype, device=pos.device),
        )

    # Compute pairwise Euclidean distance matrix
    # dist[i, j] = ||pos[i] - pos[j]||_2
    diff = pos.unsqueeze(1) - pos.unsqueeze(0)  # (N, N, 3)
    dist_matrix = torch.norm(diff, dim=-1)      # (N, N)

    mask = dist_matrix <= cutoff
    if not self_loops:
        mask = mask & (~torch.eye(n_nodes, dtype=torch.bool, device=pos.device))

    source_nodes: List[int] = []
    target_nodes: List[int] = []
    edge_dists: List[float] = []

    for i in range(n_nodes):
        neighbors = torch.where(mask[i])[0]
        if len(neighbors) == 0:
            continue
        neighbor_dists = dist_matrix[i, neighbors]
        if max_neighbors is not None and len(neighbors) > max_neighbors:
            sorted_indices = torch.argsort(neighbor_dists)[:max_neighbors]
            neighbors = neighbors[sorted_indices]
            neighbor_dists = neighbor_dists[sorted_indices]

        for j_node, d_val in zip(neighbors, neighbor_dists):
            source_nodes.append(i)
            target_nodes.append(int(j_node.item()))
            edge_dists.append(float(d_val.item()))

    if len(source_nodes) == 0:
        return (
            torch.empty((2, 0), dtype=torch.long, device=pos.device),
            torch.empty((0, 1), dtype=pos.dtype, device=pos.device),
        )

    edge_index = torch.tensor(
        [source_nodes, target_nodes], dtype=torch.long, device=pos.device
    )
    edge_distances = torch.tensor(
        edge_dists, dtype=pos.dtype, device=pos.device
    ).unsqueeze(-1)

    return edge_index, edge_distances


def compute_gaussian_rbf(
    distances: torch.Tensor,
    num_rbf: int = 16,
    cutoff: float = DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    gamma: Optional[float] = None,
) -> torch.Tensor:
    """Expand interatomic distances using Gaussian Radial Basis Functions [D].

    Parameters
    ----------
    distances : torch.Tensor
        Interatomic distances tensor of shape (E, 1) or (E,).
    num_rbf : int
        Number of Gaussian centers [E].
    cutoff : float
        Upper cutoff distance in Angstroms [E].
    gamma : Optional[float]
        RBF width parameter. Defaults to (1 / delta_mu^2) [E].

    Returns
    -------
    torch.Tensor
        RBF features of shape (E, num_rbf) with values in [0, 1] [D].
    """
    if distances.dim() == 1:
        distances = distances.unsqueeze(-1)

    centers = torch.linspace(
        0.0, cutoff, num_rbf, dtype=distances.dtype, device=distances.device
    )
    if gamma is None:
        delta = float(centers[1] - centers[0]) if num_rbf > 1 else 1.0
        gamma = 1.0 / (delta ** 2)

    # phi_k(d) = exp(-gamma * (d - mu_k)^2)
    diff = distances - centers.unsqueeze(0)  # (E, num_rbf)
    return torch.exp(-gamma * (diff ** 2))


# ==============================================================================
# 8. Physical and Spectroscopic Math Functions
# ==============================================================================


def compute_center_of_mass(positions: torch.Tensor, masses: torch.Tensor) -> torch.Tensor:
    """Compute center of mass Cartesian coordinate vector [D].

    $$\\mathbf{r}_{\\text{COM}} = \\frac{\\sum_i m_i \\mathbf{r}_i}{\\sum_i m_i}$$

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,) or (N, 1).

    Returns
    -------
    torch.Tensor
        Center-of-mass coordinate vector of shape (3,) [D].
    """
    if masses.dim() == 1:
        masses = masses.unsqueeze(-1)
    total_mass = masses.sum()
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive.")
    com = (positions * masses).sum(dim=0) / total_mass
    return com


def compute_moment_of_inertia_tensor(
    positions: torch.Tensor, masses: torch.Tensor
) -> torch.Tensor:
    """Construct the 3x3 Moment of Inertia tensor in COM frame [D].

    $$I_{\\alpha \\beta} = \\sum_i m_i \\left( r_i^2 \\delta_{\\alpha \\beta} - r_{i,\\alpha} r_{i,\\beta} \\right)$$

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,).

    Returns
    -------
    torch.Tensor
        Inertia tensor of shape (3, 3) in u * Angstrom^2 [D].
    """
    com = compute_center_of_mass(positions, masses)
    com_pos = positions - com.unsqueeze(0)

    m = masses.to(dtype=positions.dtype)
    x = com_pos[:, 0]
    y = com_pos[:, 1]
    z = com_pos[:, 2]

    i_xx = (m * (y ** 2 + z ** 2)).sum()
    i_yy = (m * (x ** 2 + z ** 2)).sum()
    i_zz = (m * (x ** 2 + y ** 2)).sum()

    i_xy = -(m * x * y).sum()
    i_xz = -(m * x * z).sum()
    i_yz = -(m * y * z).sum()

    inertia_tensor = torch.tensor(
        [
            [i_xx, i_xy, i_xz],
            [i_xy, i_yy, i_yz],
            [i_xz, i_yz, i_zz],
        ],
        dtype=positions.dtype,
        device=positions.device,
    )
    return inertia_tensor


def compute_principal_rotational_constants(
    positions: torch.Tensor, masses: torch.Tensor
) -> Tuple[float, float, float]:
    """Compute principal rotational constants A >= B >= C in MHz [D].

    Parameters
    ----------
    positions : torch.Tensor
        Atomic coordinates of shape (N, 3).
    masses : torch.Tensor
        Atomic masses of shape (N,).

    Returns
    -------
    Tuple[float, float, float]
        Principal rotational constants (A, B, C) in MHz [D].
    """
    inertia = compute_moment_of_inertia_tensor(positions, masses)
    eigenvalues = torch.linalg.eigvalsh(inertia)  # sorted ascending I_a <= I_b <= I_c

    i_a = float(eigenvalues[0].item())
    i_b = float(eigenvalues[1].item())
    i_c = float(eigenvalues[2].item())

    # Conversion constant: 505379.008784 MHz * u * Angstrom^2
    a = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_a if i_a > 1e-6 else float("inf")
    b = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_b if i_b > 1e-6 else float("inf")
    c = ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / i_c if i_c > 1e-6 else float("inf")

    return (a, b, c)


def calculate_boltzmann_weights(
    energies_hartree: Union[torch.Tensor, Sequence[float]],
    temperature_k: float = STANDARD_TEMPERATURE_K,
) -> torch.Tensor:
    """Calculate normalized Boltzmann statistical probability weights [D].

    $$p_i = \\frac{\\exp(-\\Delta E_i / k_B T)}{\\sum_j \\exp(-\\Delta E_j / k_B T)}$$

    Parameters
    ----------
    energies_hartree : Union[torch.Tensor, Sequence[float]]
        Electronic or free energies in Hartree.
    temperature_k : float
        Temperature in Kelvin (default 298.15 K) [M].

    Returns
    -------
    torch.Tensor
        Normalized probability weights summing to 1.0 [D].
    """
    if not isinstance(energies_hartree, torch.Tensor):
        energies_hartree = torch.tensor(energies_hartree, dtype=torch.float64)
    else:
        energies_hartree = energies_hartree.to(dtype=torch.float64)

    # Shift by ground state minimum for numerical stability
    min_e = energies_hartree.min()
    delta_e_hartree = energies_hartree - min_e
    delta_e_ev = delta_e_hartree * HARTREE_TO_EV

    kt_ev = BOLTZMANN_CONSTANT_EV_K * temperature_k
    exponent = -delta_e_ev / kt_ev
    unnormalized = torch.exp(exponent)
    weights = unnormalized / unnormalized.sum()
    return weights.to(dtype=torch.float32)


# ==============================================================================
# 9. Equivariant Transformations and State Immutability
# ==============================================================================


def translate_molecular_data(
    data: MolecularData,
    translation_vector: Union[torch.Tensor, Sequence[float]],
) -> MolecularData:
    """Translate molecular coordinates immutably (no in-place tensor modification).

    Separates spatial coordinates (which translate equivariantly) from non-spatial
    node features (which remain strictly invariant).

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    translation_vector : Union[torch.Tensor, Sequence[float]]
        3D translation vector (dx, dy, dz).

    Returns
    -------
    MolecularData
        New MolecularData instance with translated positions.
    """
    if not isinstance(translation_vector, torch.Tensor):
        translation_vector = torch.tensor(
            translation_vector, dtype=data.pos.dtype, device=data.pos.device
        )
    else:
        translation_vector = translation_vector.to(
            dtype=data.pos.dtype, device=data.pos.device
        )

    # Immutable addition (never in-place +=)
    new_pos = data.pos + translation_vector.view(1, 3)

    # Invariant features cloned without alteration
    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=data.forces.clone() if data.forces is not None else None,
        dipole=data.dipole.clone() if data.dipole is not None else None,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


def rotate_molecular_data(
    data: MolecularData,
    rotation_matrix: Union[torch.Tensor, Sequence[Sequence[float]]],
) -> MolecularData:
    """Rotate molecular coordinates and vectors equivariantly and immutably.

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    rotation_matrix : Union[torch.Tensor, Sequence[Sequence[float]]]
        3x3 orthogonal rotation matrix R in SO(3).

    Returns
    -------
    MolecularData
        New MolecularData instance with rotated coordinates and forces.
    """
    if not isinstance(rotation_matrix, torch.Tensor):
        r_matrix = torch.tensor(
            rotation_matrix, dtype=data.pos.dtype, device=data.pos.device
        )
    else:
        r_matrix = rotation_matrix.to(dtype=data.pos.dtype, device=data.pos.device)

    # Equivariant rotation: pos' = pos @ R^T
    new_pos = data.pos @ r_matrix.T

    # Rotate vector properties (forces, dipole) equivariantly
    new_forces = data.forces @ r_matrix.T if data.forces is not None else None
    new_dipole = data.dipole @ r_matrix.T if data.dipole is not None else None

    # Invariant features (scalar y, node features x, z, graph connectivity) unchanged
    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=new_forces,
        dipole=new_dipole,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


def center_of_mass_molecular_data(
    data: MolecularData,
    use_monoisotopic: bool = False,
) -> MolecularData:
    """Translate molecular coordinates to center of mass origin immutably.

    Parameters
    ----------
    data : MolecularData
        Source molecular data container.
    use_monoisotopic : bool
        If True, uses exact monoisotopic masses instead of standard atomic weights.

    Returns
    -------
    MolecularData
        New MolecularData centered at COM.
    """
    if use_monoisotopic:
        masses_list = [get_monoisotopic_mass(s) for s in data.symbols]
    else:
        masses_list = [get_atomic_mass(s) for s in data.symbols]

    masses_tensor = torch.tensor(
        masses_list, dtype=data.pos.dtype, device=data.pos.device
    )
    com = compute_center_of_mass(data.pos, masses_tensor)
    return translate_molecular_data(data, -com)


def eckart_align_molecular_data(
    data: MolecularData,
    reference: MolecularData,
    use_mass_weighting: bool = True,
) -> MolecularData:
    """Align molecular coordinates to reference structure via Kabsch SVD rotation [D].

    Parameters
    ----------
    data : MolecularData
        Source structure to align.
    reference : MolecularData
        Target reference structure.
    use_mass_weighting : bool
        If True, computes mass-weighted Eckart rotation.

    Returns
    -------
    MolecularData
        Aligned MolecularData rotated into the reference coordinate frame.
    """
    if use_mass_weighting:
        masses_list = [get_atomic_mass(s) for s in data.symbols]
    else:
        masses_list = [1.0 for _ in data.symbols]

    masses_tensor = torch.tensor(
        masses_list, dtype=data.pos.dtype, device=data.pos.device
    )

    data_com = compute_center_of_mass(data.pos, masses_tensor)
    ref_com = compute_center_of_mass(reference.pos, masses_tensor)

    p = data.pos - data_com.unsqueeze(0)
    q = reference.pos - ref_com.unsqueeze(0)

    if use_mass_weighting:
        m = masses_tensor.unsqueeze(-1)
        # Weighted covariance matrix H = P^T * W * Q
        h = (p * m).T @ q
    else:
        h = p.T @ q

    # SVD of covariance matrix
    u, s, v_t = torch.linalg.svd(h)
    d = torch.det(v_t.T @ u.T)

    correction = torch.eye(3, dtype=p.dtype, device=p.device)
    if d < 0:
        correction[2, 2] = -1.0

    # Optimal rotation matrix R = V * correction * U^T
    rot_matrix = v_t.T @ correction @ u.T

    # Rotate centered data and place in reference COM frame
    new_pos = p @ rot_matrix.T + ref_com.unsqueeze(0)

    # Rotate vector properties (forces, dipole) equivariantly
    new_forces = data.forces @ rot_matrix.T if data.forces is not None else None
    new_dipole = data.dipole @ rot_matrix.T if data.dipole is not None else None

    return MolecularData(
        z=data.z.clone(),
        pos=new_pos,
        edge_index=data.edge_index.clone() if data.edge_index is not None else None,
        y=data.y.clone() if data.y is not None else None,
        x=data.x.clone() if data.x is not None else None,
        edge_attr=data.edge_attr.clone() if data.edge_attr is not None else None,
        weight=data.weight.clone() if data.weight is not None else None,
        forces=new_forces,
        dipole=new_dipole,
        rotational_constants=(
            data.rotational_constants.clone()
            if data.rotational_constants is not None
            else None
        ),
        symbols=list(data.symbols),
        metadata=dict(data.metadata),
    )


# ==============================================================================
# 10. High-Level Molecular Featurizer API
# ==============================================================================


class MolecularFeaturizer:
    """Universal molecular graph featurizer for quantum chemistry and spectroscopy.

    Converts Pydantic validated MolecularInput instances, XYZ files, RDKit Mol objects,
    and ASE Atoms into canonical MolecularData PyTorch geometric containers.
    """

    def __init__(self, config: Optional[MolecularGraphConfig] = None) -> None:
        self.config = config if config is not None else MolecularGraphConfig()

    def featurize(self, mol_input: MolecularInput) -> MolecularData:
        """Featurize a validated MolecularInput instance into MolecularData [D].

        Parameters
        ----------
        mol_input : MolecularInput
            Validated molecular input structure.

        Returns
        -------
        MolecularData
            Canonical PyTorch geometric tensor container.
        """
        torch_dtype = torch.float64 if self.config.dtype == "float64" else torch.float32
        target_device = torch.device(self.config.device)

        n_atoms = len(mol_input.symbols)
        symbols = mol_input.symbols

        # 1. Atomic Numbers Z
        z_values = [
            SYMBOL_TO_ATOMIC_NUMBER[s] for s in symbols
        ]
        z_tensor = torch.tensor(z_values, dtype=torch.long, device=target_device)

        # 2. Spatial Cartesian Coordinates pos (N, 3)
        pos_tensor = torch.tensor(
            mol_input.positions, dtype=torch_dtype, device=target_device
        )

        # 3. Non-Spatial Invariant Node Features x (N, F)
        node_features_list: List[List[float]] = []
        for i, sym in enumerate(symbols):
            feat_row: List[float] = []

            # One-hot element type encoding (10 dimensions)
            type_idx = ELEMENT_TYPE_TO_INDEX.get(sym, -1)
            one_hot = [0.0] * len(DEFAULT_ELEMENT_TYPES)
            if 0 <= type_idx < len(DEFAULT_ELEMENT_TYPES):
                one_hot[type_idx] = 1.0
            feat_row.extend(one_hot)

            # Atomic mass [M]
            if self.config.include_masses:
                mass_val = (
                    mol_input.masses[i]
                    if mol_input.masses is not None
                    else get_atomic_mass(sym)
                )
                feat_row.append(float(mass_val))

            # Covalent radius [M]
            if self.config.include_covalent_radii:
                cov_radius = get_covalent_radius_angstrom(sym)
                feat_row.append(cov_radius)

            # Pauling electronegativity [M]
            if self.config.include_electronegativity:
                en = get_pauling_electronegativity(sym)
                feat_row.append(en)

            # Formal and partial charges [D]
            if self.config.include_charges:
                fc = (
                    float(mol_input.formal_charges[i])
                    if mol_input.formal_charges is not None
                    else 0.0
                )
                pc = (
                    float(mol_input.partial_charges[i])
                    if mol_input.partial_charges is not None
                    else 0.0
                )
                feat_row.extend([fc, pc])

            node_features_list.append(feat_row)

        x_tensor = torch.tensor(
            node_features_list, dtype=torch_dtype, device=target_device
        )

        # 4. Graph Edge Construction & Edge Attributes
        edge_index, edge_distances = build_radius_graph(
            pos_tensor,
            cutoff=self.config.cutoff_radius,
            max_neighbors=self.config.max_neighbors,
            directed=self.config.directed,
            self_loops=self.config.self_loops,
        )

        edge_attrs_list: List[torch.Tensor] = []
        if edge_index.size(1) > 0:
            if self.config.include_edge_distances:
                edge_attrs_list.append(edge_distances)

            if self.config.include_edge_rbf:
                rbf = compute_gaussian_rbf(
                    edge_distances,
                    num_rbf=self.config.num_rbf,
                    cutoff=self.config.cutoff_radius,
                    gamma=self.config.rbf_gamma,
                )
                edge_attrs_list.append(rbf)

            if self.config.include_edge_vectors:
                # Directed unit displacement vectors
                src, dst = edge_index[0], edge_index[1]
                disp = pos_tensor[dst] - pos_tensor[src]
                disp_norm = edge_distances.clamp(min=1e-8)
                unit_vectors = disp / disp_norm
                edge_attrs_list.append(unit_vectors)

        edge_attr_tensor = (
            torch.cat(edge_attrs_list, dim=-1)
            if edge_attrs_list
            else torch.empty((edge_index.size(1), 0), dtype=torch_dtype, device=target_device)
        )

        # 5. Target Property y
        y_tensor = (
            torch.tensor([mol_input.energy], dtype=torch_dtype, device=target_device)
            if mol_input.energy is not None
            else None
        )

        # 6. Forces, Dipole, Rotational Constants
        forces_tensor = (
            torch.tensor(mol_input.forces, dtype=torch_dtype, device=target_device)
            if mol_input.forces is not None
            else None
        )
        dipole_tensor = (
            torch.tensor(mol_input.dipole, dtype=torch_dtype, device=target_device)
            if mol_input.dipole is not None
            else None
        )
        rot_consts_tensor = (
            torch.tensor(
                mol_input.rotational_constants, dtype=torch_dtype, device=target_device
            )
            if mol_input.rotational_constants is not None
            else None
        )
        weight_tensor = torch.tensor(
            [mol_input.weight], dtype=torch_dtype, device=target_device
        )

        return MolecularData(
            z=z_tensor,
            pos=pos_tensor,
            edge_index=edge_index,
            y=y_tensor,
            x=x_tensor,
            edge_attr=edge_attr_tensor,
            weight=weight_tensor,
            forces=forces_tensor,
            dipole=dipole_tensor,
            rotational_constants=rot_consts_tensor,
            symbols=symbols,
            metadata=dict(mol_input.tags),
        )

    def featurize_batch(
        self, mol_inputs: Sequence[MolecularInput]
    ) -> List[MolecularData]:
        """Featurize multiple molecular inputs into a list of MolecularData."""
        return [self.featurize(inp) for inp in mol_inputs]

    def from_symbols_and_positions(
        self,
        symbols: Sequence[str],
        positions: Sequence[Sequence[float]],
        **kwargs: Any,
    ) -> MolecularData:
        """Construct and featurize MolecularData directly from symbols and coordinates."""
        mol_input = MolecularInput(
            symbols=list(symbols),
            positions=[list(p) for p in positions],
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_xyz(
        self,
        xyz_input: Union[str, Path],
        energy: Optional[float] = None,
        **kwargs: Any,
    ) -> MolecularData:
        """Parse standard .xyz file or string content and produce featurized MolecularData."""
        if isinstance(xyz_input, Path) or (isinstance(xyz_input, str) and os.path.exists(xyz_input)):
            content = Path(xyz_input).read_text(encoding="utf-8").strip()
        else:
            content = str(xyz_input).strip()

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError(f"XYZ content too short ({len(lines)} lines; minimum 3 lines required).")

        try:
            n_atoms = int(lines[0])
        except ValueError:
            raise ValueError(f"First line of XYZ must be integer atom count; got '{lines[0]}'.")

        atom_lines = lines[2: 2 + n_atoms]
        symbols: List[str] = []
        positions: List[List[float]] = []

        for line in atom_lines:
            parts = line.split()
            if len(parts) < 4:
                raise ValueError(f"Malformed XYZ atom coordinate line: '{line}'")
            symbols.append(parts[0])
            positions.append([float(parts[1]), float(parts[2]), float(parts[3])])

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            energy=energy,
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_rdkit(
        self,
        mol: Any,
        conf_id: int = -1,
        **kwargs: Any,
    ) -> MolecularData:
        """Extract atomic coordinates and elements from RDKit Mol object."""
        if mol is None:
            raise ValueError("RDKit Mol instance cannot be None.")

        conf = mol.GetConformer(conf_id)
        symbols: List[str] = []
        positions: List[List[float]] = []
        formal_charges: List[int] = []

        for i, atom in enumerate(mol.GetAtoms()):
            symbols.append(atom.GetSymbol())
            formal_charges.append(atom.GetFormalCharge())
            pos = conf.GetAtomPosition(i)
            positions.append([float(pos.x), float(pos.y), float(pos.z)])

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            formal_charges=formal_charges,
            **kwargs,
        )
        return self.featurize(mol_input)

    def from_ase(
        self,
        atoms: Any,
        **kwargs: Any,
    ) -> MolecularData:
        """Extract coordinates and chemical symbols from ASE Atoms object."""
        if atoms is None:
            raise ValueError("ASE Atoms instance cannot be None.")

        symbols = [str(sym) for sym in atoms.get_chemical_symbols()]
        positions = atoms.get_positions().tolist()

        mol_input = MolecularInput(
            symbols=symbols,
            positions=positions,
            **kwargs,
        )
        return self.featurize(mol_input)
