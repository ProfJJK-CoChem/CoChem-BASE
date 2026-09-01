"""CoChem-GEOM: Raw GEOM MsgPack Dataset Parser and Quantum Chemistry Log Extraction Engine.
==========================================================================================
Provides safe streaming deserialization for massive MsgPack conformer archives,
extracts QM properties (DFT, GFN2-xTB, ORCA, Gaussian), computes SHA-256 provenance hashes,
dynamically queries Mendeleev isotopic masses with LRU caching, calculates Boltzmann ensemble distributions,
and constructs SE(3)-equivariant geometric tensor representations.

Authoritative Standards:
- Method Matrix v4: Data Ingestion & Spectroscopic Conformer Graph Contracts
- Mendeleev Library Mandate: Dynamic atomic mass & monoisotopic resolution (No hardcoding)
- SE(3) Equivariance & Invariance: Separation of spatial pos vs non-spatial node features
- State Immutability: Pure functional geometric transformations (immutable operations)
- SWEBOK v3 / ISO 25010 Software Quality Standards
- Provenance Tags: [M] Measured/Theoretical, [D] Derived/Calculated, [E] Expert Estimate
- Safe MsgPack Streaming: Unpacker streaming with raw=False to prevent out-of-memory errors
"""

from __future__ import annotations

from dataclasses import dataclass, field
import functools
import hashlib
import io
import logging
import math
import os
from pathlib import Path
import pickle
import re
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple, Union

from mendeleev import element
import msgpack
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator
import torch

try:
    from rdkit import Chem
except ImportError:
    Chem = None  # Optional fallback if rdkit is omitted in lightweight environments

from cochem_geom.data.featurizer import (
    ATOMIC_MASS_UNIT_KG,
    ATOMIC_NUMBER_TO_SYMBOL,
    BOLTZMANN_CONSTANT_EV_K,
    BOLTZMANN_CONSTANT_J_K,
    DEFAULT_ELEMENT_TYPES,
    DEFAULT_GRAPH_CUTOFF_ANGSTROM,
    DEFAULT_MAX_NEIGHBORS,
    ELEMENT_TYPE_TO_INDEX,
    EV_TO_CM_MINUS_ONE,
    EV_TO_HARTREE,
    EV_TO_KCAL_MOL,
    HARTREE_TO_EV,
    HARTREE_TO_KCAL_MOL,
    HARTREE_TO_KJ_MOL,
    INDEX_TO_ELEMENT_TYPE,
    KCAL_MOL_TO_EV,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ,
    SPEED_OF_LIGHT_M_S,
    STANDARD_TEMPERATURE_K,
    SYMBOL_TO_ATOMIC_NUMBER,
    MolecularData,
    MolecularFeaturizer,
    MolecularGraphConfig,
    MolecularInput,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. Fundamental Constants and Buffer Configurations
# ==============================================================================

DEFAULT_MAX_BUFFER_SIZE: int = 1024 * 1024 * 1024
"""Default maximum streaming buffer size for msgpack unpacker (1 GB) [E]."""

DEFAULT_CHUNK_SIZE_BYTES: int = 65536
"""Default chunk size for streaming SHA-256 checksum computation in bytes [E]."""


# ==============================================================================
# 2. Dynamic Mendeleev Mass and Property Resolution Functions (LRU Cached)
# ==============================================================================


@functools.lru_cache(maxsize=256)
def get_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query standard atomic weight from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol (e.g., 'C', 'O') or atomic number Z (e.g., 6, 8).

    Returns
    -------
    float
        Standard atomic mass in Daltons.
    """
    el = element(symbol_or_z)
    if el.atomic_weight is not None:
        return float(el.atomic_weight)
    if el.isotopes:
        return float(el.isotopes[0].mass)
    raise ValueError(f"Standard atomic mass not found for element '{symbol_or_z}'")


@functools.lru_cache(maxsize=256)
def get_monoisotopic_mass(symbol_or_z: Union[str, int]) -> float:
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


@functools.lru_cache(maxsize=512)
def get_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically query exact mass of a specific isotope from mendeleev [M].

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol or atomic number Z.
    mass_number : int
        Isotopic mass number A (protons + neutrons).

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


@functools.lru_cache(maxsize=256)
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


@functools.lru_cache(maxsize=256)
def get_pauling_electronegativity(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Pauling electronegativity from mendeleev [M]."""
    el = element(symbol_or_z)
    if el.en_pauling is not None:
        return float(el.en_pauling)
    return 0.0


@functools.lru_cache(maxsize=256)
def get_vdw_radius_angstrom(symbol_or_z: Union[str, int]) -> float:
    """Dynamically query Van der Waals radius in Angstroms [M]."""
    el = element(symbol_or_z)
    if el.vdw_radius_alvarez is not None:
        return float(el.vdw_radius_alvarez) / 100.0
    if el.vdw_radius is not None:
        return float(el.vdw_radius) / 100.0
    return 1.7


# ==============================================================================
# 3. Energy Conversion Pure Functions
# ==============================================================================


def hartree_to_ev(energy_hartree: float) -> float:
    """Convert energy from Hartree to electron-volts [D]."""
    return float(energy_hartree * HARTREE_TO_EV)


def ev_to_hartree(energy_ev: float) -> float:
    """Convert energy from electron-volts to Hartree [D]."""
    return float(energy_ev * EV_TO_HARTREE)


def hartree_to_kcal_mol(energy_hartree: float) -> float:
    """Convert energy from Hartree to kcal/mol [D]."""
    return float(energy_hartree * HARTREE_TO_KCAL_MOL)


def kcal_mol_to_hartree(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to Hartree [D]."""
    return float(energy_kcal_mol * KCAL_MOL_TO_HARTREE)


def kcal_mol_to_ev(energy_kcal_mol: float) -> float:
    """Convert energy from kcal/mol to electron-volts [D]."""
    return float(energy_kcal_mol * KCAL_MOL_TO_EV)


def ev_to_kcal_mol(energy_ev: float) -> float:
    """Convert energy from electron-volts to kcal/mol [D]."""
    return float(energy_ev * EV_TO_KCAL_MOL)


# ==============================================================================
# 4. Cryptographic SHA-256 Provenance Hashing
# ==============================================================================


def compute_file_sha256(file_path: Union[str, Path], chunk_size: int = DEFAULT_CHUNK_SIZE_BYTES) -> str:
    """Compute cryptographic SHA-256 hex digest of a file via chunked streaming [M].

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the target file.
    chunk_size : int
        Buffer size for stream reading.

    Returns
    -------
    str
        64-character lowercase hexadecimal SHA-256 checksum string.
    """
    path = Path(file_path).expanduser().resolve()
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute cryptographic SHA-256 hex digest of in-memory byte buffer [M].

    Parameters
    ----------
    data : bytes
        Raw binary data.

    Returns
    -------
    str
        64-character lowercase hexadecimal SHA-256 checksum string.
    """
    return hashlib.sha256(data).hexdigest()


def compute_structure_sha256(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    atomic_numbers: Sequence[int],
    precision_decimals: int = 6,
) -> str:
    """Compute deterministic SHA-256 fingerprint of molecular structure and atomic composition [M].

    Parameters
    ----------
    coords : Union[np.ndarray, Sequence[Sequence[float]]]
        Cartesian coordinates of shape (N, 3) in Angstroms.
    atomic_numbers : Sequence[int]
        Atomic numbers Z of length N.
    precision_decimals : int
        Rounding precision for Cartesian coordinates in decimal places [E].

    Returns
    -------
    str
        64-character hexadecimal SHA-256 hash string.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    rounded_coords = np.round(coords_arr, decimals=precision_decimals)

    buffer = io.BytesIO()
    for z_val, row in zip(atomic_numbers, rounded_coords):
        buffer.write(f"{int(z_val)}:{row[0]:.{precision_decimals}f},{row[1]:.{precision_decimals}f},{row[2]:.{precision_decimals}f}\n".encode("utf-8"))

    return hashlib.sha256(buffer.getvalue()).hexdigest()


# ==============================================================================
# 5. Spectroscopic Moment of Inertia and Rotational Constants
# ==============================================================================


def compute_center_of_mass(coords: np.ndarray, masses: Sequence[float]) -> np.ndarray:
    """Compute center of mass coordinates in Angstroms [D].

    Parameters
    ----------
    coords : np.ndarray
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float]
        Atomic masses in Daltons of length N.

    Returns
    -------
    np.ndarray
        Center of mass vector of shape (3,).
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = np.asarray(masses, dtype=np.float64)
    total_mass = np.sum(masses_arr)
    if total_mass <= 0.0:
        raise ValueError(f"Total molecular mass must be positive, got {total_mass}")
    return np.sum(coords_arr * masses_arr[:, np.newaxis], axis=0) / total_mass


def compute_moment_of_inertia_tensor(coords: np.ndarray, masses: Sequence[float]) -> np.ndarray:
    """Compute 3x3 moment of inertia tensor in units of u * Angstrom^2 [D].

    Parameters
    ----------
    coords : np.ndarray
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float]
        Atomic masses in Daltons of length N.

    Returns
    -------
    np.ndarray
        Inertia tensor of shape (3, 3).
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = np.asarray(masses, dtype=np.float64)

    com = compute_center_of_mass(coords_arr, masses_arr)
    rel_coords = coords_arr - com  # Shift to center-of-mass frame

    x, y, z = rel_coords[:, 0], rel_coords[:, 1], rel_coords[:, 2]
    m = masses_arr

    ixx = np.sum(m * (y**2 + z**2))
    iyy = np.sum(m * (x**2 + z**2))
    izz = np.sum(m * (x**2 + y**2))
    ixy = -np.sum(m * x * y)
    ixz = -np.sum(m * x * z)
    iyz = -np.sum(m * y * z)

    return np.array(
        [[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]],
        dtype=np.float64,
    )


def compute_rotational_constants(
    coords: np.ndarray,
    masses: Sequence[float],
) -> np.ndarray:
    """Compute spectroscopic rotational constants (A, B, C) in MHz from 3D coordinates [D].

    Rotational constant factor: h / (8 * pi^2) = 505379.008784 MHz * u * Angstrom^2.
    Principal moments sorted such that Ia <= Ib <= Ic, yielding A >= B >= C.

    Parameters
    ----------
    coords : np.ndarray
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float]
        Atomic masses in Daltons of length N.

    Returns
    -------
    np.ndarray
        Rotational constants array of shape (3,) in MHz: [A, B, C].
    """
    inertia_tensor = compute_moment_of_inertia_tensor(coords, masses)
    eigenvalues = np.linalg.eigvalsh(inertia_tensor)
    eigenvalues = np.sort(np.maximum(eigenvalues, 1e-12))  # Ensure sorted positive moments

    ia, ib, ic = eigenvalues[0], eigenvalues[1], eigenvalues[2]

    # Convert principal moments to rotational constants in MHz
    a_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ia) if ia > 1e-6 else float("inf")
    b_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ib) if ib > 1e-6 else float("inf")
    c_const = float(ROTATIONAL_CONSTANT_MHZ_U_ANGSTROM_SQ / ic) if ic > 1e-6 else float("inf")

    # If linear or degenerate rotor with infinite constant, clamp gracefully
    a_out = a_const if not math.isinf(a_const) else (b_const if not math.isinf(b_const) else 0.0)
    b_out = b_const if not math.isinf(b_const) else 0.0
    c_out = c_const if not math.isinf(c_const) else 0.0

    return np.array([a_out, b_out, c_out], dtype=np.float32)


# ==============================================================================
# 6. Thermodynamic Boltzmann Weighting Pure Function
# ==============================================================================


def calculate_boltzmann_weights(
    energies: Union[Sequence[float], np.ndarray, torch.Tensor],
    temperature_k: float = STANDARD_TEMPERATURE_K,
    energy_unit: str = "ev",
) -> np.ndarray:
    """Compute normalized Boltzmann thermodynamic probability distribution [M]/[D].

    Parameters
    ----------
    energies : Union[Sequence[float], np.ndarray, torch.Tensor]
        Conformer total or relative energies.
    temperature_k : float
        Absolute temperature in Kelvin (standard T = 298.15 K) [M].
    energy_unit : str
        Unit of input energies: 'ev', 'hartree', or 'kcal_mol'.

    Returns
    -------
    np.ndarray
        Normalized Boltzmann probabilities of shape (len(energies),) summing to 1.0.
    """
    if isinstance(energies, torch.Tensor):
        e_arr = energies.detach().cpu().numpy().astype(np.float64)
    else:
        e_arr = np.asarray(energies, dtype=np.float64)

    if len(e_arr) == 0:
        return np.empty((0,), dtype=np.float32)
    if len(e_arr) == 1:
        return np.ones((1,), dtype=np.float32)

    unit_lower = energy_unit.lower()
    if unit_lower in ("hartree", "eh", "au"):
        e_ev = e_arr * HARTREE_TO_EV
    elif unit_lower in ("kcal/mol", "kcal_mol", "kcal"):
        e_ev = e_arr * KCAL_MOL_TO_EV
    else:
        e_ev = e_arr

    # Thermodynamic constant in eV: k_B * T
    kt_ev = BOLTZMANN_CONSTANT_EV_K * temperature_k
    if kt_ev <= 1e-12:
        weights = np.zeros_like(e_ev, dtype=np.float32)
        min_idx = int(np.nanargmin(e_ev)) if np.any(np.isfinite(e_ev)) else 0
        weights[min_idx] = 1.0
        return weights

    # Numerically stable relative energy shift by minimum
    min_e = np.nanmin(e_ev) if np.any(np.isfinite(e_ev)) else 0.0
    delta_e = e_ev - min_e

    # Exponentiate with numerical clamp to prevent underflow issues
    exponent = -delta_e / kt_ev
    clipped_exp = np.clip(exponent, -700.0, 0.0)
    exp_terms = np.exp(clipped_exp)
    partition_function = np.nansum(exp_terms)

    if partition_function <= 0.0 or not np.isfinite(partition_function):
        weights = np.zeros_like(e_ev, dtype=np.float32)
        min_idx = int(np.nanargmin(e_ev)) if np.any(np.isfinite(e_ev)) else 0
        weights[min_idx] = 1.0
        return weights

    probabilities = exp_terms / partition_function
    return probabilities.astype(np.float32)


# ==============================================================================
# 7. Intermediate Conformer & Molecule Domain Data Models
# ==============================================================================


@dataclass(frozen=True, slots=True)
class ConformerRecord:
    """Represents a single 3D geometric conformation and its quantum chemical observables.

    Attributes
    ----------
    conformer_id : int
        Unique sequential integer identifier within the molecular ensemble.
    coords : np.ndarray
        Spatial Cartesian coordinates of shape (N, 3) in Angstroms [M].
    energy : float
        Total ground-state electronic energy in eV [M].
    relative_energy : float
        Energy relative to global minimum conformer in eV [D].
    boltzmann_weight : float
        Normalized thermodynamic probability at standard temperature [M].
    forces : Optional[np.ndarray]
        Spatial gradient vector forces of shape (N, 3) in eV/Angstrom [D].
    dipole : Optional[np.ndarray]
        Electric dipole moment vector of shape (3,) in Debye [D].
    rotational_constants : Optional[np.ndarray]
        Principal spectroscopic rotational constants (A, B, C) of shape (3,) in MHz [D].
    qm_method : Optional[str]
        Method identifier (e.g. 'DFT/wB97M-V/def2-QZVPP', 'GFN2-xTB') [M].
    source_hash : Optional[str]
        Cryptographic SHA-256 provenance hash of source calculation or file [M].
    s2_spin : Optional[float]
        Total spin angular momentum expectation value <S^2> [D].
    frequencies : Optional[np.ndarray]
        Harmonic vibrational frequencies in wavenumbers (cm^-1) [D].
    metadata : Dict[str, Any]
        Arbitrary metadata dictionary.
    """

    conformer_id: int
    coords: np.ndarray
    energy: float
    relative_energy: float
    boltzmann_weight: float
    forces: Optional[np.ndarray] = None
    dipole: Optional[np.ndarray] = None
    rotational_constants: Optional[np.ndarray] = None
    qm_method: Optional[str] = None
    source_hash: Optional[str] = None
    s2_spin: Optional[float] = None
    frequencies: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.coords.ndim != 2 or self.coords.shape[1] != 3:
            raise ValueError(f"Conformer coordinates must have shape (N, 3), got {self.coords.shape}")
        if self.forces is not None:
            if self.forces.ndim != 2 or self.forces.shape != self.coords.shape:
                raise ValueError(
                    f"Forces shape {self.forces.shape} does not match coordinates shape {self.coords.shape}"
                )
        if self.dipole is not None and self.dipole.shape != (3,):
            raise ValueError(f"Dipole moment must have shape (3,), got {self.dipole.shape}")
        if self.rotational_constants is not None and self.rotational_constants.shape != (3,):
            raise ValueError(
                f"Rotational constants must have shape (3,), got {self.rotational_constants.shape}"
            )

    @property
    def num_atoms(self) -> int:
        """Number of atom centers N."""
        return int(self.coords.shape[0])

    def clone(self) -> ConformerRecord:
        """Deep copy of ConformerRecord ensuring memory independence."""
        return ConformerRecord(
            conformer_id=self.conformer_id,
            coords=np.copy(self.coords),
            energy=self.energy,
            relative_energy=self.relative_energy,
            boltzmann_weight=self.boltzmann_weight,
            forces=np.copy(self.forces) if self.forces is not None else None,
            dipole=np.copy(self.dipole) if self.dipole is not None else None,
            rotational_constants=(
                np.copy(self.rotational_constants)
                if self.rotational_constants is not None
                else None
            ),
            qm_method=self.qm_method,
            source_hash=self.source_hash,
            s2_spin=self.s2_spin,
            frequencies=np.copy(self.frequencies) if self.frequencies is not None else None,
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert conformer record to serializable dictionary."""
        return {
            "conformer_id": self.conformer_id,
            "coords": self.coords.tolist(),
            "energy": self.energy,
            "relative_energy": self.relative_energy,
            "boltzmann_weight": self.boltzmann_weight,
            "forces": self.forces.tolist() if self.forces is not None else None,
            "dipole": self.dipole.tolist() if self.dipole is not None else None,
            "rotational_constants": (
                self.rotational_constants.tolist()
                if self.rotational_constants is not None
                else None
            ),
            "qm_method": self.qm_method,
            "source_hash": self.source_hash,
            "s2_spin": self.s2_spin,
            "frequencies": self.frequencies.tolist() if self.frequencies is not None else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class MoleculeRecord:
    """Represents a topological molecular entity and its 3D conformational ensemble.

    Attributes
    ----------
    smiles : str
        Canonical IUPAC SMILES string.
    n_atoms : int
        Total number of atoms N (including explicit hydrogens).
    atomic_numbers : np.ndarray
        Atomic numbers Z of shape (N,) with dtype np.int64.
    formal_charges : np.ndarray
        Formal atomic charges of shape (N,) with dtype np.int64.
    symbols : List[str]
        IUPAC chemical element symbols of length N.
    conformers : List[ConformerRecord]
        List of valid 3D conformer states.
    total_charge : int
        Net molecular charge.
    spin_multiplicity : int
        Spin multiplicity (2S + 1).
    tags : Dict[str, str]
        Metadata annotation tags.
    """

    smiles: str
    n_atoms: int
    atomic_numbers: np.ndarray
    formal_charges: np.ndarray
    symbols: List[str]
    conformers: List[ConformerRecord] = field(default_factory=list)
    total_charge: int = 0
    spin_multiplicity: int = 1
    tags: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.symbols) != self.n_atoms:
            raise ValueError(
                f"Symbols length ({len(self.symbols)}) does not match n_atoms ({self.n_atoms})"
            )
        if self.atomic_numbers.shape != (self.n_atoms,):
            raise ValueError(
                f"Atomic numbers shape {self.atomic_numbers.shape} does not match n_atoms ({self.n_atoms})"
            )
        for conf in self.conformers:
            if conf.coords.shape[0] != self.n_atoms:
                raise ValueError(
                    f"Conformer atom count {conf.coords.shape[0]} does not match topology {self.n_atoms}"
                )

    @property
    def num_conformers(self) -> int:
        """Total number of conformers in the ensemble."""
        return len(self.conformers)

    def get_lowest_energy_conformer(self) -> Optional[ConformerRecord]:
        """Retrieve the global energy minimum conformer in the ensemble [D]."""
        if not self.conformers:
            return None
        return min(self.conformers, key=lambda c: c.energy)

    def clone(self) -> MoleculeRecord:
        """Deep copy of MoleculeRecord."""
        return MoleculeRecord(
            smiles=self.smiles,
            n_atoms=self.n_atoms,
            atomic_numbers=np.copy(self.atomic_numbers),
            formal_charges=np.copy(self.formal_charges),
            symbols=list(self.symbols),
            conformers=[c.clone() for c in self.conformers],
            total_charge=self.total_charge,
            spin_multiplicity=self.spin_multiplicity,
            tags=dict(self.tags),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert molecule record to serializable dictionary."""
        return {
            "smiles": self.smiles,
            "n_atoms": self.n_atoms,
            "atomic_numbers": self.atomic_numbers.tolist(),
            "formal_charges": self.formal_charges.tolist(),
            "symbols": list(self.symbols),
            "conformers": [c.to_dict() for c in self.conformers],
            "total_charge": self.total_charge,
            "spin_multiplicity": self.spin_multiplicity,
            "tags": dict(self.tags),
        }


# ==============================================================================
# 8. Pydantic v2 Quantum Chemistry Output Log Model
# ==============================================================================


class QMOutputRecord(BaseModel):
    """Pydantic v2 data contract for parsed quantum chemistry output log files."""

    program: str = Field(..., description="Quantum chemistry software (ORCA, xTB, Gaussian, etc.) [M]")
    converged: bool = Field(..., description="True if geometry or SCF converged successfully [M]")
    total_energy_hartree: Optional[float] = Field(default=None, description="Final electronic energy in Hartree [M]")
    total_energy_ev: Optional[float] = Field(default=None, description="Final electronic energy in eV [D]")
    relative_energy_ev: Optional[float] = Field(default=None, description="Relative energy in eV [D]")
    symbols: List[str] = Field(default_factory=list, description="IUPAC chemical element symbols [M]")
    atomic_numbers: List[int] = Field(default_factory=list, description="Atomic numbers Z [M]")
    positions: Optional[Any] = Field(default=None, description="Cartesian coordinates (N, 3) in Angstroms [M]")
    forces: Optional[Any] = Field(default=None, description="Atomic forces (N, 3) in eV/Angstrom [D]")
    dipole: Optional[Any] = Field(default=None, description="Dipole vector (3,) in Debye [D]")
    rotational_constants: Optional[Any] = Field(
        default=None, description="Rotational constants (A, B, C) in MHz [D]"
    )
    s2_calculated: Optional[float] = Field(default=None, description="Calculated <S^2> expectation value [D]")
    s2_expected: Optional[float] = Field(default=None, description="Exact theoretical <S^2> = S(S+1) [D]")
    frequencies: Optional[Any] = Field(default=None, description="Harmonic vibrational frequencies in cm^-1 [D]")
    sha256_hash: str = Field(..., description="SHA-256 hash of log content or source file [M]")
    method: Optional[str] = Field(default=None, description="Computational functional or method [M]")
    basis: Optional[str] = Field(default=None, description="Basis set specification [M]")
    walltime_seconds: Optional[float] = Field(default=None, description="Elapsed wall-clock runtime in seconds [M]")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional program metadata")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


# ==============================================================================
# 9. MsgPack Streaming Serialization & Deserialization Engine
# ==============================================================================


def deserialize_geom_archive(
    file_path: Union[str, Path],
    max_buffer_size: int = DEFAULT_MAX_BUFFER_SIZE,
) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
    """Safely stream unpacked records sequentially from a GEOM MsgPack archive without OOM.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the `.msgpack` archive file.
    max_buffer_size : int
        Maximum unpacker buffer size in bytes (default 1 GB) [E].

    Yields
    ------
    Tuple[str, Dict[str, Any]]
        Tuple of (smiles_string, raw_molecule_data_dict).
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"MsgPack archive file does not exist: {path}")

    with open(path, "rb") as f:
        unpacker = msgpack.Unpacker(f, raw=False, max_buffer_size=max_buffer_size)
        for raw_obj in unpacker:
            if isinstance(raw_obj, dict):
                # Check if it's a single molecule payload or a dict of molecules
                if "conformers" in raw_obj or "geom" in raw_obj:
                    smiles_val = str(raw_obj.get("smiles", "UNKNOWN"))
                    yield smiles_val, raw_obj
                else:
                    # Top-level dictionary mapping SMILES -> data
                    for smiles, mol_data in raw_obj.items():
                        if isinstance(mol_data, dict):
                            yield str(smiles), mol_data
                        else:
                            yield str(smiles), {"data": mol_data}
            elif isinstance(raw_obj, (list, tuple)):
                if len(raw_obj) >= 2 and isinstance(raw_obj[0], str) and isinstance(raw_obj[1], dict):
                    yield str(raw_obj[0]), raw_obj[1]
                else:
                    for entry in raw_obj:
                        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                            yield str(entry[0]), entry[1]
                        elif isinstance(entry, dict) and "smiles" in entry:
                            yield str(entry["smiles"]), entry


def deserialize_geom_bytes(
    data: bytes,
    max_buffer_size: int = DEFAULT_MAX_BUFFER_SIZE,
) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
    """Stream unpacked records from an in-memory MsgPack byte buffer.

    Parameters
    ----------
    data : bytes
        Binary MsgPack data payload.
    max_buffer_size : int
        Maximum unpacker buffer size in bytes [E].

    Yields
    ------
    Tuple[str, Dict[str, Any]]
        Tuple of (smiles_string, raw_molecule_data_dict).
    """
    stream = io.BytesIO(data)
    unpacker = msgpack.Unpacker(stream, raw=False, max_buffer_size=max_buffer_size)
    for raw_obj in unpacker:
        if isinstance(raw_obj, dict):
            if "conformers" in raw_obj or "geom" in raw_obj:
                smiles_val = str(raw_obj.get("smiles", "UNKNOWN"))
                yield smiles_val, raw_obj
            else:
                for smiles, mol_data in raw_obj.items():
                    if isinstance(mol_data, dict):
                        yield str(smiles), mol_data
                    else:
                        yield str(smiles), {"data": mol_data}
        elif isinstance(raw_obj, (list, tuple)):
            if len(raw_obj) >= 2 and isinstance(raw_obj[0], str) and isinstance(raw_obj[1], dict):
                yield str(raw_obj[0]), raw_obj[1]
            else:
                for entry in raw_obj:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        yield str(entry[0]), entry[1]
                    elif isinstance(entry, dict) and "smiles" in entry:
                        yield str(entry["smiles"]), entry


def serialize_geom_archive(
    file_path: Union[str, Path],
    records: Union[Dict[str, Any], Sequence[Tuple[str, Dict[str, Any]]]],
) -> int:
    """Serialize molecular records into a binary MsgPack archive file using stream packing.

    Parameters
    ----------
    file_path : Union[str, Path]
        Target `.msgpack` file path.
    records : Union[Dict[str, Any], Sequence[Tuple[str, Dict[str, Any]]]]
        Mapping or sequence of (SMILES, data_dict) to write.

    Returns
    -------
    int
        Count of molecules written to the archive.
    """
    path = Path(file_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(records, dict):
        records_dict = records
    else:
        records_dict = {smiles: data for smiles, data in records}

    with open(path, "wb") as f:
        packed = msgpack.packb(records_dict, use_bin_type=True)
        f.write(packed)

    return len(records_dict)


def serialize_geom_bytes(
    records: Union[Dict[str, Any], Sequence[Tuple[str, Dict[str, Any]]]],
) -> bytes:
    """Serialize molecular records into an in-memory MsgPack byte buffer.

    Parameters
    ----------
    records : Union[Dict[str, Any], Sequence[Tuple[str, Dict[str, Any]]]]
        Mapping or sequence of records.

    Returns
    -------
    bytes
        Packed binary data.
    """
    if isinstance(records, dict):
        records_dict = records
    else:
        records_dict = {smiles: data for smiles, data in records}

    return bytes(msgpack.packb(records_dict, use_bin_type=True))


# ==============================================================================
# 10. Conformer Ensemble & Raw GEOM Parsing Engine
# ==============================================================================


def _extract_coords_from_raw_conformer(raw_conf: Dict[str, Any], expected_n_atoms: Optional[int] = None) -> np.ndarray:
    """Extract and format 3D coordinates from raw conformer dictionary into (N, 3) float32 array."""
    coords_raw = None
    if "geom" in raw_conf:
        coords_raw = raw_conf["geom"]
    elif "xyz" in raw_conf:
        coords_raw = raw_conf["xyz"]
    elif "rdkit_coords" in raw_conf:
        coords_raw = raw_conf["rdkit_coords"]
    elif "coordinates" in raw_conf:
        coords_raw = raw_conf["coordinates"]
    elif "positions" in raw_conf:
        coords_raw = raw_conf["positions"]
    elif "rdkit_mol" in raw_conf or "mol" in raw_conf:
        mol_obj = raw_conf.get("rdkit_mol") or raw_conf.get("mol")
        if isinstance(mol_obj, bytes):
            try:
                mol_obj = pickle.loads(mol_obj)
            except (pickle.UnpicklingError, TypeError, ValueError):
                if Chem is not None:
                    try:
                        mol_obj = Chem.Mol(mol_obj)
                    except (TypeError, ValueError, RuntimeError):
                        mol_obj = None
        if mol_obj is not None and hasattr(mol_obj, "GetConformer"):
            try:
                conf = mol_obj.GetConformer()
                coords_raw = conf.GetPositions()
            except (ValueError, RuntimeError, AttributeError):
                coords_raw = None

    if coords_raw is None:
        raise ValueError(f"Could not locate 3D coordinates in conformer dictionary keys: {list(raw_conf.keys())}")

    if isinstance(coords_raw, dict) and "xyz" in coords_raw:
        coords_raw = coords_raw["xyz"]

    arr = np.asarray(coords_raw, dtype=np.float32)

    # Flattened array of length 3N -> reshape to (N, 3)
    if arr.ndim == 1:
        if arr.shape[0] % 3 != 0:
            raise ValueError(f"Flattened coordinate array size {arr.shape[0]} is not divisible by 3")
        arr = arr.reshape(-1, 3)

    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"Expected (N, 3) coordinate array, got {arr.shape}")

    if expected_n_atoms is not None and arr.shape[0] != expected_n_atoms:
        raise ValueError(f"Coordinate atom count {arr.shape[0]} does not match expected {expected_n_atoms}")

    return arr


def _extract_energy_from_raw_conformer(raw_conf: Dict[str, Any], default_unit: str = "hartree") -> float:
    """Extract total electronic energy and convert to eV [M]/[D]."""
    energy_raw = None
    for key in ("totalenergy", "total_energy", "energy", "electronic_energy", "dft_energy", "xtb_energy"):
        if key in raw_conf and raw_conf[key] is not None:
            try:
                energy_raw = float(raw_conf[key])
                break
            except (ValueError, TypeError):
                continue

    if energy_raw is None:
        return 0.0

    unit = default_unit.lower()
    if unit in ("hartree", "eh", "au"):
        return hartree_to_ev(energy_raw)
    elif unit in ("kcal/mol", "kcal_mol", "kcal"):
        return kcal_mol_to_ev(energy_raw)
    return energy_raw


def _extract_forces_from_raw_conformer(raw_conf: Dict[str, Any], n_atoms: int) -> Optional[np.ndarray]:
    """Extract atomic forces from conformer record and convert to (N, 3) eV/Angstrom."""
    forces_raw = None
    for key in ("forces", "gradient", "grad", "atomic_forces"):
        if key in raw_conf and raw_conf[key] is not None:
            forces_raw = raw_conf[key]
            break

    if forces_raw is None:
        return None

    try:
        arr = np.asarray(forces_raw, dtype=np.float32)
        if arr.ndim == 1 and arr.shape[0] == 3 * n_atoms:
            arr = arr.reshape(n_atoms, 3)
        if arr.shape == (n_atoms, 3):
            return arr
    except (ValueError, TypeError) as exc:
        logger.debug("Failed to reshape forces array: %s", exc)
    return None


def _extract_dipole_from_raw_conformer(raw_conf: Dict[str, Any]) -> Optional[np.ndarray]:
    """Extract electric dipole vector (3,) in Debye."""
    for key in ("dipole", "dipole_moment", "electric_dipole", "mu"):
        if key in raw_conf and raw_conf[key] is not None:
            try:
                arr = np.asarray(raw_conf[key], dtype=np.float32)
                if arr.ndim == 1 and arr.shape[0] == 3:
                    return arr
            except (ValueError, TypeError) as exc:
                logger.debug("Failed to parse dipole array: %s", exc)
    return None


def _extract_rotational_constants_from_raw_conformer(raw_conf: Dict[str, Any]) -> Optional[np.ndarray]:
    """Extract rotational constants (A, B, C) in MHz."""
    for key in ("rotational_constants", "rotationalconstants", "rot_consts", "rotconsts"):
        if key in raw_conf and raw_conf[key] is not None:
            try:
                arr = np.asarray(raw_conf[key], dtype=np.float32)
                if arr.ndim == 1 and arr.shape[0] == 3:
                    return arr
            except (ValueError, TypeError) as exc:
                logger.debug("Failed to parse rotational constants array: %s", exc)
    return None


def _resolve_topology_from_smiles_or_data(
    smiles: str,
    raw_data: Dict[str, Any],
    fallback_n_atoms: Optional[int] = None,
) -> Tuple[List[str], np.ndarray, np.ndarray, int]:
    """Resolve atomic symbols, atomic numbers Z, and formal charges for a molecule."""
    symbols: List[str] = []
    atomic_numbers_list: List[int] = []
    formal_charges_list: List[int] = []

    # 1. Check if explicitly provided in raw data dictionary
    if "elements" in raw_data and isinstance(raw_data["elements"], list):
        symbols = [str(s).capitalize() for s in raw_data["elements"]]
        atomic_numbers_list = [SYMBOL_TO_ATOMIC_NUMBER.get(s, 6) for s in symbols]
        formal_charges_list = [0] * len(symbols)
    elif "atomic_numbers" in raw_data and isinstance(raw_data["atomic_numbers"], list):
        atomic_numbers_list = [int(z) for z in raw_data["atomic_numbers"]]
        symbols = [ATOMIC_NUMBER_TO_SYMBOL.get(z, "C") for z in atomic_numbers_list]
        formal_charges_list = [0] * len(symbols)

    # 2. If RDKit is installed and symbols not resolved, extract topology with explicit hydrogens
    if not symbols and Chem is not None and smiles:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                mol = Chem.AddHs(mol)
                for atom in mol.GetAtoms():
                    z = atom.GetAtomicNum()
                    sym = atom.GetSymbol()
                    fc = atom.GetFormalCharge()
                    atomic_numbers_list.append(z)
                    symbols.append(sym)
                    formal_charges_list.append(fc)
        except Exception as e:
            logger.debug(f"RDKit parsing bypassed for SMILES '{smiles}': {e}")

    # 3. Robust regex tokenizer fallback: handle bracketed atoms, halogens, organic set, and lowercase aromatics
    if not symbols and smiles:
        token_pattern = re.compile(r'\[([A-Z][a-z]?)[^\]]*\]|(Cl|Br)|([BCNOPSFI])|([bcnops])')
        aromatic_map = {'b': 'B', 'c': 'C', 'n': 'N', 'o': 'O', 'p': 'P', 's': 'S'}
        for match in token_pattern.finditer(smiles):
            bracket, halogen, upper, lower = match.groups()
            sym_tok = None
            if bracket:
                sym_tok = bracket.capitalize()
            elif halogen:
                sym_tok = halogen.capitalize()
            elif upper:
                sym_tok = upper
            elif lower:
                sym_tok = aromatic_map[lower]

            if sym_tok and sym_tok in SYMBOL_TO_ATOMIC_NUMBER:
                symbols.append(sym_tok)
                atomic_numbers_list.append(SYMBOL_TO_ATOMIC_NUMBER[sym_tok])
                formal_charges_list.append(0)

    # 4. Fallback if counts mismatch or still empty
    if fallback_n_atoms is not None:
        if len(symbols) != fallback_n_atoms:
            if len(symbols) < fallback_n_atoms:
                needed = fallback_n_atoms - len(symbols)
                for _ in range(needed):
                    symbols.append("H")
                    atomic_numbers_list.append(1)
                    formal_charges_list.append(0)
            else:
                symbols = symbols[:fallback_n_atoms]
                atomic_numbers_list = atomic_numbers_list[:fallback_n_atoms]
                formal_charges_list = formal_charges_list[:fallback_n_atoms]

    n_atoms = len(symbols)
    atomic_numbers = np.array(atomic_numbers_list, dtype=np.int64)
    formal_charges = np.array(formal_charges_list, dtype=np.int64)

    return symbols, atomic_numbers, formal_charges, n_atoms


def parse_geom_raw_molecule(
    smiles: str,
    raw_data: Dict[str, Any],
    temperature_k: float = STANDARD_TEMPERATURE_K,
    default_energy_unit: str = "hartree",
) -> MoleculeRecord:
    """Parse raw GEOM molecule dictionary into validated MoleculeRecord and ConformerRecord ensemble.

    Parameters
    ----------
    smiles : str
        Canonical SMILES string.
    raw_data : Dict[str, Any]
        Raw GEOM molecule dictionary containing conformers list.
    temperature_k : float
        Temperature for Boltzmann weighting in Kelvin [M].
    default_energy_unit : str
        Energy unit in raw dictionary ('hartree', 'kcal_mol', or 'ev').

    Returns
    -------
    MoleculeRecord
        Immutable molecule record containing child conformer records.
    """
    raw_conformers = raw_data.get("conformers", [])
    if not raw_conformers:
        if "geom" in raw_data or "xyz" in raw_data or "rdkit_mol" in raw_data:
            raw_conformers = [raw_data]

    # Pre-flight check first conformer to identify atom count
    fallback_n_atoms = None
    if raw_conformers:
        first_conf = raw_conformers[0]
        try:
            first_coords = _extract_coords_from_raw_conformer(first_conf)
            fallback_n_atoms = first_coords.shape[0]
        except Exception:
            pass

    symbols, atomic_numbers, formal_charges, n_atoms = _resolve_topology_from_smiles_or_data(
        smiles, raw_data, fallback_n_atoms=fallback_n_atoms
    )

    masses = [get_atomic_mass(s) for s in symbols]

    parsed_conformers_temp: List[Dict[str, Any]] = []
    energies_ev: List[float] = []

    for conf_idx, raw_conf in enumerate(raw_conformers):
        try:
            coords = _extract_coords_from_raw_conformer(raw_conf, expected_n_atoms=n_atoms)
        except Exception as e:
            logger.debug(f"Skipping conformer {conf_idx} of '{smiles}': {e}")
            continue

        energy_ev = _extract_energy_from_raw_conformer(raw_conf, default_unit=default_energy_unit)
        forces = _extract_forces_from_raw_conformer(raw_conf, n_atoms)
        dipole = _extract_dipole_from_raw_conformer(raw_conf)
        rot_consts = _extract_rotational_constants_from_raw_conformer(raw_conf)

        # Dynamically compute rotational constants from coordinates and Mendeleev masses if absent
        if rot_consts is None and n_atoms >= 2:
            rot_consts = compute_rotational_constants(coords, masses)

        qm_method = raw_conf.get("method") or raw_conf.get("qm_method")
        source_hash = raw_conf.get("source_hash") or compute_structure_sha256(coords, atomic_numbers.tolist())
        s2_spin = raw_conf.get("s2") or raw_conf.get("s2_spin")
        if s2_spin is not None:
            s2_spin = float(s2_spin)

        parsed_conformers_temp.append(
            {
                "conformer_id": conf_idx,
                "coords": coords,
                "energy": energy_ev,
                "forces": forces,
                "dipole": dipole,
                "rotational_constants": rot_consts,
                "qm_method": qm_method,
                "source_hash": source_hash,
                "s2_spin": s2_spin,
                "metadata": dict(raw_conf.get("metadata", {})),
            }
        )
        energies_ev.append(energy_ev)

    if not parsed_conformers_temp:
        raise ValueError(f"Zero valid conformers could be extracted for molecule '{smiles}'")

    # Compute Boltzmann thermodynamic weights and relative energies across ensemble
    boltzmann_weights = calculate_boltzmann_weights(energies_ev, temperature_k=temperature_k, energy_unit="ev")
    min_energy_ev = min(energies_ev)

    conformer_records: List[ConformerRecord] = []
    for item, b_weight in zip(parsed_conformers_temp, boltzmann_weights):
        rel_energy = item["energy"] - min_energy_ev
        rec = ConformerRecord(
            conformer_id=item["conformer_id"],
            coords=item["coords"],
            energy=item["energy"],
            relative_energy=rel_energy,
            boltzmann_weight=float(b_weight),
            forces=item["forces"],
            dipole=item["dipole"],
            rotational_constants=item["rotational_constants"],
            qm_method=item["qm_method"],
            source_hash=item["source_hash"],
            s2_spin=item["s2_spin"],
            metadata=item["metadata"],
        )
        conformer_records.append(rec)

    total_charge = int(raw_data.get("charge", 0))
    spin_multiplicity = int(raw_data.get("spin_multiplicity", 1))
    tags = {str(k): str(v) for k, v in raw_data.get("tags", {}).items()}

    return MoleculeRecord(
        smiles=smiles,
        n_atoms=n_atoms,
        atomic_numbers=atomic_numbers,
        formal_charges=formal_charges,
        symbols=symbols,
        conformers=conformer_records,
        total_charge=total_charge,
        spin_multiplicity=spin_multiplicity,
        tags=tags,
    )


# ==============================================================================
# 11. Quantum Chemistry Output Log Parsers (ORCA, xTB, Gaussian)
# ==============================================================================


def parse_qm_log_text(
    log_text: str,
    filename: Optional[str] = None,
    program: Optional[str] = None,
) -> QMOutputRecord:
    """Parse quantum chemistry calculation output log text (ORCA, xTB, Gaussian) [M]/[D].

    Parameters
    ----------
    log_text : str
        Full log file text content.
    filename : Optional[str]
        Source filename for provenance tracking.
    program : Optional[str]
        Optional program hint ('ORCA', 'xTB', 'Gaussian'). Auto-detected if None.

    Returns
    -------
    QMOutputRecord
        Pydantic data contract containing extracted energies, geometry, forces, dipoles, frequencies, and SHA-256 hash.
    """
    sha256_hash = hashlib.sha256(log_text.encode("utf-8")).hexdigest()

    # Program auto-detection
    detected_prog = program
    if detected_prog is None:
        if "O   R   C   A" in log_text or "ORCA" in log_text:
            detected_prog = "ORCA"
        elif "X T B" in log_text or "xTB" in log_text or "GFN" in log_text:
            detected_prog = "xTB"
        elif "Gaussian" in log_text or "Entering Gaussian System" in log_text:
            detected_prog = "Gaussian"
        else:
            detected_prog = "Unknown"

    total_energy_hartree: Optional[float] = None
    converged = False
    symbols: List[str] = []
    atomic_numbers: List[int] = []
    positions_list: List[List[float]] = []
    dipole_arr: Optional[np.ndarray] = None
    rot_consts_arr: Optional[np.ndarray] = None
    s2_val: Optional[float] = None
    forces_list: Optional[List[List[float]]] = None
    freqs_list: List[float] = []

    if detected_prog == "ORCA":
        # 1. Total Electronic Energy (Hartree)
        e_matches = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-\d\.]+(?:[eE][+-]?\d+)?)", log_text)
        if e_matches:
            total_energy_hartree = float(e_matches[-1])

        # 2. Rigorous Convergence Check: must not fail optimization
        has_normal_term = "ORCA TERMINATED NORMALLY" in log_text
        has_opt_conv = "OPTIMIZATION HAS CONVERGED" in log_text or "*** OPTIMIZATION RUN DONE ***" in log_text or "HURRAY" in log_text
        has_opt_fail = "THE OPTIMIZATION HAS NOT CONVERGED" in log_text or "FAILED TO CONVERGE" in log_text
        if (has_normal_term or has_opt_conv) and not has_opt_fail:
            converged = True

        # 3. Cartesian Coordinates (Angstroms)
        coord_blocks = re.findall(
            r"CARTESIAN COORDINATES \(ANGSTROEM\)\s*\n-+\s*\n([\s\S]*?)\n\s*\n",
            log_text,
        )
        if not coord_blocks:
            coord_blocks = re.findall(
                r"CARTESIAN COORDINATES \(ANGSTROEM\)\s*\n-+\s*\n([\s\S]*?)(?:-{4,}|$)",
                log_text,
            )
        if coord_blocks:
            last_block = coord_blocks[-1]
            for line in last_block.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 4:
                    sym = parts[0].capitalize()
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        symbols.append(sym)
                        atomic_numbers.append(SYMBOL_TO_ATOMIC_NUMBER.get(sym, 0))
                        positions_list.append([x, y, z])
                    except ValueError:
                        continue

        # 4. Dipole Moment (Debye)
        dipole_match = re.search(r"Total Dipole Moment\s*:\s*([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", log_text)
        if dipole_match:
            dipole_arr = np.array(
                [float(dipole_match.group(1)), float(dipole_match.group(2)), float(dipole_match.group(3))],
                dtype=np.float32,
            )

        # 5. Rotational Constants (MHz)
        rot_match = re.search(r"Rotational constants in MHz\s*:\s*([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", log_text)
        if rot_match:
            rot_consts_arr = np.array(
                [float(rot_match.group(1)), float(rot_match.group(2)), float(rot_match.group(3))],
                dtype=np.float32,
            )

        # 6. Spin Expectation Value <S^2>
        s2_match = re.search(r"Expectation value of <S\*\*2>\s*:\s*([-\d\.]+)", log_text)
        if s2_match:
            s2_val = float(s2_match.group(1))

        # 7. Vibrational Frequencies (cm^-1)
        freq_matches = re.findall(r"\d+:\s+([-\d\.]+)\s+cm\*\*-1", log_text)
        if freq_matches:
            freqs_list = [float(f) for f in freq_matches]

    elif detected_prog == "xTB":
        # 1. Total Energy (Hartree)
        e_match = re.search(r"TOTAL ENERGY\s+([-\d\.]+(?:[eE][+-]?\d+)?)", log_text)
        if e_match:
            total_energy_hartree = float(e_match.group(1))

        # 2. Convergence
        if ("normal termination of xtb" in log_text or "GEOMETRY OPTIMIZATION CONVERGED" in log_text) and "FAILED" not in log_text:
            converged = True

        # 3. Dipole Moment (Debye)
        dipole_match = re.search(r"full:\s+([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", log_text)
        if dipole_match:
            dipole_arr = np.array(
                [float(dipole_match.group(1)), float(dipole_match.group(2)), float(dipole_match.group(3))],
                dtype=np.float32,
            )

        # 4. Rotational Constants (MHz)
        rot_match = re.search(r"rotational constants \(MHz\):\s*\n\s*([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", log_text)
        if rot_match:
            rot_consts_arr = np.array(
                [float(rot_match.group(1)), float(rot_match.group(2)), float(rot_match.group(3))],
                dtype=np.float32,
            )

        # 5. Coordinates from final structure block
        struct_match = re.search(r"final structure:\s*\n([\s\S]*?)(?:\n\s*\n|normal termination)", log_text)
        if struct_match:
            for line in struct_match.group(1).strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 4:
                    sym = parts[0].capitalize()
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        symbols.append(sym)
                        atomic_numbers.append(SYMBOL_TO_ATOMIC_NUMBER.get(sym, 0))
                        positions_list.append([x, y, z])
                    except ValueError:
                        continue

        # 6. Vibrational Frequencies (cm^-1)
        freq_block_match = re.search(r"harmonic frequencies \(cm-1\)\s*\n([\s\S]*?)(?:\n\s*\n|reduced masses|\$|\Z)", log_text)
        if freq_block_match:
            for line in freq_block_match.group(1).splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        freqs_list.append(float(parts[-1]))
                    except ValueError:
                        pass

    elif detected_prog == "Gaussian":
        # 1. Total Energy (Hartree)
        e_matches = re.findall(r"SCF Done:\s+E\([^\)]+\)\s*=\s*([-\d\.]+(?:[dDeE][+-]?\d+)?)", log_text)
        if e_matches:
            e_str = e_matches[-1].replace("D", "E").replace("d", "e")
            total_energy_hartree = float(e_str)

        # 2. Convergence
        if ("Normal termination of Gaussian" in log_text or "Optimization completed." in log_text) and "Error termination" not in log_text:
            converged = True

        # 3. Rotational Constants (GHZ -> convert to MHz by * 1000)
        rot_match = re.search(r"Rotational constants \(GHZ\):\s*([-\d\.]+)\s+([-\d\.]+)\s+([-\d\.]+)", log_text)
        if rot_match:
            rot_consts_arr = np.array(
                [float(rot_match.group(1)) * 1000.0, float(rot_match.group(2)) * 1000.0, float(rot_match.group(3)) * 1000.0],
                dtype=np.float32,
            )

        # 4. Dipole Moment (Debye)
        dipole_match = re.search(r"Dipole moment[^\n]*\n\s*X=\s*([-\d\.]+)\s+Y=\s*([-\d\.]+)\s+Z=\s*([-\d\.]+)", log_text)
        if dipole_match:
            dipole_arr = np.array(
                [float(dipole_match.group(1)), float(dipole_match.group(2)), float(dipole_match.group(3))],
                dtype=np.float32,
            )

        # 5. Standard or Input Orientation Coordinates
        blocks = re.findall(
            r"(?:Standard|Input)\s+orientation:\s*\n\s*-+\s*\n\s*Center\s+Atomic[^\n]*\n\s*Number\s+Number[^\n]*\n\s*-+\s*\n([\s\S]*?)\n\s*-+",
            log_text,
        )
        if blocks:
            last_block = blocks[-1]
            for line in last_block.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 6:
                    try:
                        z = int(parts[1])
                        sym = ATOMIC_NUMBER_TO_SYMBOL.get(z, "X")
                        x, y, z_coord = float(parts[3]), float(parts[4]), float(parts[5])
                        symbols.append(sym)
                        atomic_numbers.append(z)
                        positions_list.append([x, y, z_coord])
                    except ValueError:
                        continue

        # 6. Vibrational Frequencies (cm^-1)
        freq_matches = re.findall(r"Frequencies\s*--\s+([-\d\.\s]+)", log_text)
        for block in freq_matches:
            for tok in block.split():
                try:
                    freqs_list.append(float(tok))
                except ValueError:
                    pass

    # Assemble positions array
    positions_arr = np.array(positions_list, dtype=np.float32) if positions_list else np.empty((0, 3), dtype=np.float32)
    forces_arr = np.array(forces_list, dtype=np.float32) if forces_list else None
    frequencies_arr = np.array(freqs_list, dtype=np.float32) if freqs_list else None

    # Total energy in eV
    total_energy_ev = hartree_to_ev(total_energy_hartree) if total_energy_hartree is not None else None

    return QMOutputRecord(
        program=detected_prog,
        converged=converged,
        total_energy_hartree=total_energy_hartree,
        total_energy_ev=total_energy_ev,
        relative_energy_ev=0.0,
        symbols=symbols,
        atomic_numbers=atomic_numbers,
        positions=positions_arr,
        forces=forces_arr,
        dipole=dipole_arr,
        rotational_constants=rot_consts_arr,
        s2_calculated=s2_val,
        s2_expected=0.0,
        frequencies=frequencies_arr,
        sha256_hash=sha256_hash,
        metadata={"filename": filename} if filename else {},
    )


def parse_qm_output(
    file_path: Union[str, Path],
    program: Optional[str] = None,
) -> QMOutputRecord:
    """Parse quantum chemistry calculation output file from disk [M].

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to `.out` or `.log` file.
    program : Optional[str]
        Optional program type ('ORCA', 'xTB', 'Gaussian').

    Returns
    -------
    QMOutputRecord
        Parsed calculation record.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"QM output file does not exist: {path}")

    log_text = path.read_text(encoding="utf-8", errors="replace")
    return parse_qm_log_text(log_text, filename=path.name, program=program)


# ==============================================================================
# 12. State Immutability & SE(3) Pure Transformations
# ==============================================================================


def translate_conformer(
    conformer: ConformerRecord,
    translation_vector: Union[np.ndarray, Sequence[float]],
) -> ConformerRecord:
    """Translate 3D conformer coordinates immutably without mutating the input object.

    Spatial coordinates: pos_new = pos + t.
    Non-spatial scalar properties (energy, relative energy, weight, S^2) and
    vector observables (forces, dipole) remain strictly invariant under spatial translation.

    Parameters
    ----------
    conformer : ConformerRecord
        Input conformer state.
    translation_vector : Union[np.ndarray, Sequence[float]]
        3D translation vector (3,).

    Returns
    -------
    ConformerRecord
        New independent ConformerRecord with translated coordinates.
    """
    t_arr = np.asarray(translation_vector, dtype=conformer.coords.dtype)
    new_coords = conformer.coords + t_arr  # Immutable pure addition

    return ConformerRecord(
        conformer_id=conformer.conformer_id,
        coords=new_coords,
        energy=conformer.energy,
        relative_energy=conformer.relative_energy,
        boltzmann_weight=conformer.boltzmann_weight,
        forces=np.copy(conformer.forces) if conformer.forces is not None else None,
        dipole=np.copy(conformer.dipole) if conformer.dipole is not None else None,
        rotational_constants=(
            np.copy(conformer.rotational_constants)
            if conformer.rotational_constants is not None
            else None
        ),
        qm_method=conformer.qm_method,
        source_hash=conformer.source_hash,
        s2_spin=conformer.s2_spin,
        frequencies=np.copy(conformer.frequencies) if conformer.frequencies is not None else None,
        metadata=dict(conformer.metadata),
    )


def rotate_conformer(
    conformer: ConformerRecord,
    rotation_matrix: Union[np.ndarray, Sequence[Sequence[float]]],
) -> ConformerRecord:
    """Rotate 3D conformer coordinates and vector properties immutably.

    Spatial coordinates and vector forces/dipoles rotate covariantly:
    pos_new = pos @ R^T, forces_new = forces @ R^T, dipole_new = dipole @ R^T.
    Scalar properties (energy, relative energy, weight, S^2) remain strictly invariant.

    Parameters
    ----------
    conformer : ConformerRecord
        Input conformer state.
    rotation_matrix : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 orthogonal rotation matrix R (SO(3)).

    Returns
    -------
    ConformerRecord
        New independent ConformerRecord with rotated spatial attributes.
    """
    r_arr = np.asarray(rotation_matrix, dtype=conformer.coords.dtype)
    if r_arr.shape != (3, 3):
        raise ValueError(f"Rotation matrix must have shape (3, 3), got {r_arr.shape}")

    new_coords = conformer.coords @ r_arr.T

    new_forces = None
    if conformer.forces is not None:
        new_forces = conformer.forces @ r_arr.T

    new_dipole = None
    if conformer.dipole is not None:
        new_dipole = conformer.dipole @ r_arr.T

    return ConformerRecord(
        conformer_id=conformer.conformer_id,
        coords=new_coords,
        energy=conformer.energy,
        relative_energy=conformer.relative_energy,
        boltzmann_weight=conformer.boltzmann_weight,
        forces=new_forces,
        dipole=new_dipole,
        rotational_constants=(
            np.copy(conformer.rotational_constants)
            if conformer.rotational_constants is not None
            else None
        ),
        qm_method=conformer.qm_method,
        source_hash=conformer.source_hash,
        s2_spin=conformer.s2_spin,
        frequencies=np.copy(conformer.frequencies) if conformer.frequencies is not None else None,
        metadata=dict(conformer.metadata),
    )


# ==============================================================================
# 13. PyTorch Geometric & MolecularData Interoperability
# ==============================================================================


def conformer_to_molecular_data(
    molecule: MoleculeRecord,
    conformer: ConformerRecord,
    config: Optional[MolecularGraphConfig] = None,
) -> MolecularData:
    """Convert parsed MoleculeRecord and ConformerRecord into canonical MolecularData graph container.

    Parameters
    ----------
    molecule : MoleculeRecord
        Parent molecular topology.
    conformer : ConformerRecord
        Target 3D conformer state.
    config : Optional[MolecularGraphConfig]
        Graph construction and featurization configuration.

    Returns
    -------
    MolecularData
        PyG-compatible geometric tensor data container.
    """
    featurizer = MolecularFeaturizer(config=config)

    mol_input = MolecularInput(
        symbols=molecule.symbols,
        positions=conformer.coords.tolist(),
        atomic_numbers=molecule.atomic_numbers.tolist(),
        formal_charges=molecule.formal_charges.tolist(),
        total_charge=molecule.total_charge,
        spin_multiplicity=molecule.spin_multiplicity,
        energy=conformer.energy,
        forces=conformer.forces.tolist() if conformer.forces is not None else None,
        dipole=conformer.dipole.tolist() if conformer.dipole is not None else None,
        rotational_constants=(
            conformer.rotational_constants.tolist()
            if conformer.rotational_constants is not None
            else None
        ),
        weight=conformer.boltzmann_weight,
        tags=molecule.tags,
    )

    data = featurizer.featurize(mol_input)
    data.metadata["conformer_id"] = conformer.conformer_id
    data.metadata["smiles"] = molecule.smiles
    if conformer.source_hash:
        data.metadata["source_hash"] = conformer.source_hash
    if conformer.qm_method:
        data.metadata["qm_method"] = conformer.qm_method
    if conformer.s2_spin is not None:
        data.metadata["s2_spin"] = conformer.s2_spin

    return data


def ensemble_to_molecular_data(
    molecule: MoleculeRecord,
    config: Optional[MolecularGraphConfig] = None,
) -> List[MolecularData]:
    """Convert entire conformational ensemble of a molecule into a list of MolecularData objects.

    Parameters
    ----------
    molecule : MoleculeRecord
        Parent molecular topology and conformers.
    config : Optional[MolecularGraphConfig]
        Featurization configuration.

    Returns
    -------
    List[MolecularData]
        List of PyG data objects, one per conformer.
    """
    return [conformer_to_molecular_data(molecule, conf, config=config) for conf in molecule.conformers]


def molecular_data_to_conformer(
    data: MolecularData,
    conformer_id: int = 0,
) -> ConformerRecord:
    """Extract ConformerRecord from MolecularData tensor container.

    Parameters
    ----------
    data : MolecularData
        MolecularData graph tensor container.
    conformer_id : int
        Sequential conformer ID.

    Returns
    -------
    ConformerRecord
        Extracted ConformerRecord.
    """
    coords_np = data.pos.detach().cpu().numpy().astype(np.float32)
    energy_val = float(data.y.item()) if data.y is not None else 0.0
    weight_val = float(data.weight.item()) if data.weight is not None else 1.0

    forces_np = data.forces.detach().cpu().numpy().astype(np.float32) if data.forces is not None else None
    dipole_np = data.dipole.detach().cpu().numpy().astype(np.float32) if data.dipole is not None else None
    rot_np = (
        data.rotational_constants.detach().cpu().numpy().astype(np.float32)
        if data.rotational_constants is not None
        else None
    )

    return ConformerRecord(
        conformer_id=conformer_id,
        coords=coords_np,
        energy=energy_val,
        relative_energy=0.0,
        boltzmann_weight=weight_val,
        forces=forces_np,
        dipole=dipole_np,
        rotational_constants=rot_np,
        qm_method=data.metadata.get("qm_method"),
        source_hash=data.metadata.get("source_hash"),
        s2_spin=data.metadata.get("s2_spin"),
        metadata=dict(data.metadata),
    )
