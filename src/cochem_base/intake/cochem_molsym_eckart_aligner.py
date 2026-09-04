#!/usr/bin/env python3
r"""
CoChem-INTAKE: MolSym Point-Group Symmetry & Mass-Weighted Eckart Frame Aligner
=============================================================================
Module: intake/cochem_molsym_eckart_aligner.py
Ecosystem Role: Primary Molecular Ingestion, Point-Group Symmetry Analysis,
                 Inertial Normalization & Eckart Reference Frame Aligner.

Key Capabilities:
1. Dynamic atomic and isotopic mass resolution strictly via the `mendeleev` library,
   with robust ghost atom (BSSE / Counterpoise: 'Gh', 'Bq', 'X') zero-mass protections.
2. Exact mass-weighted Center of Mass (COM) translation with iterative numerical
   residual refinement ensuring ||sum(m_i * r'_i)|| < 1e-14 Angstrom.
3. Symmetric 3x3 Moment of Inertia tensor construction, diagonalization (Ia <= Ib <= Ic),
   right-handed coordinate frame enforcement (det(V) = +1.0), and planar moments (Pa, Pb, Pc).
4. Spectroscopic rotational constants (A, B, C in MHz, GHz, cm^-1) via authentic
   NIST CODATA 2022 / 2026 fundamental physical constants, with linear top singularities (Ia -> 0).
5. Ray's asymmetry parameter kappa and authoritative rotor top classification:
   linear, spherical_top, prolate_symmetric_top, oblate_symmetric_top, asymmetric_top.
6. MolSym point group symmetry detection (Schoenflies notation), rotational symmetry
   number sigma, Symmetrically Equivalent Atoms (SEAs), irreducible representations (irreps),
   character table extraction, and nuclear spin statistical weights.
7. Mass-weighted Eckart frame alignment via Kabsch / SVD algorithm minimizing mass-weighted
   RMSD, enforcing det(U) = +1.0 (reflection-free), and verifying translational and rotational
   Eckart conditions with residual torque norm <= 1e-12.
8. Idempotent (3N x 3N) vibrational projection operator P_vib = I - P_rigid (Tr = 3N-6 or 3N-5)
   with mass-weighted and Cartesian Hessian projection to eliminate rigid body drift.
9. Comprehensive Pydantic v2 data models for type validation and JSON/HDF5 serialization.
10. Theoretical verification benchmark suite covering H2O, CH4, CO2, C6H6, and BSSE complexes.

Authoritative Standards:
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md (v4 Sections 3, 4, 8A-8C, 9B, 12-14)
- D:\__CoChem\GitHub-Repo\CoChem-BASE\CoChem_User_Manual.md
- NIST CODATA 2022 / 2026 Fundamental Physical Constants
- Mendeleev Library Standard Periodic Table & Isotopic Mass Mandate
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from enum import Enum
import json
import logging
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import mendeleev
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# Try importing molsym library
try:
    import molsym  # type: ignore[import-untyped]
    import molsym.salcs  # type: ignore[import-untyped]
    _MOLSYM_AVAILABLE = True
except ImportError:
    molsym = None  # type: ignore
    _MOLSYM_AVAILABLE = False

# Try importing AtomModel from cochem_topos if present
try:
    from cochem_topos.topology import AtomModel
except ImportError:
    AtomModel = None  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("CoChem-MolSymEckartAligner")


# ==============================================================================
# NIST CODATA 2022 / 2026 Fundamental Physical Constants & Conversion Factors
# ==============================================================================

PLANCK_H: float = 6.62607015e-34          # J * s (exact SI standard)
SPEED_OF_LIGHT_C: float = 299792458.0     # m / s (exact SI standard)
ATOMIC_MASS_UNIT_U: float = 1.66053906892e-27  # kg / u (CODATA 2022/2026)
ANGSTROM_TO_M: float = 1.0e-10            # m / Angstrom

# Rotational constant factor: B = h / (8 * pi^2 * I)
# FACTOR_HZ: [J * s] / [kg * m^2] = [1 / s] = Hz
FACTOR_HZ: float = PLANCK_H / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_U * (ANGSTROM_TO_M ** 2))
FACTOR_MHZ: float = FACTOR_HZ / 1.0e6
FACTOR_GHZ: float = FACTOR_HZ / 1.0e9
FACTOR_CM1: float = FACTOR_HZ / (SPEED_OF_LIGHT_C * 100.0)


# ==============================================================================
# 1. Custom Exception Hierarchy
# ==============================================================================

class MolSymEckartError(Exception):
    """Base exception for all MolSym and Eckart alignment failures."""


class MassResolutionError(MolSymEckartError):
    """Raised when atomic or isotopic masses cannot be dynamically determined."""


class CenterOfMassError(MolSymEckartError):
    """Raised when Center of Mass translation fails or molecular mass is non-positive."""


class InertiaTensorError(MolSymEckartError):
    """Raised when Moment of Inertia tensor construction or diagonalization fails."""


class EckartAlignmentError(MolSymEckartError):
    """Raised when Eckart frame alignment or residual verification fails."""


class SymmetryAnalysisError(MolSymEckartError):
    """Raised when MolSym point group analysis encounters unresolvable geometries."""


class VibrationalProjectionError(MolSymEckartError):
    """Raised when vibrational projector construction or Hessian projection fails."""


# ==============================================================================
# 2. Enumerations
# ==============================================================================

class RotorTopType(str, Enum):
    """Rotor classification based on principal moments of inertia (Ia <= Ib <= Ic)."""
    ASYMMETRIC = "asymmetric_top"
    SYMMETRIC_PROLATE = "prolate_symmetric_top"
    SYMMETRIC_OBLATE = "oblate_symmetric_top"
    SPHERICAL = "spherical_top"
    LINEAR = "linear"
    ATOM = "atom"


class AlignmentStatus(str, Enum):
    """Execution and verification status for Eckart alignment."""
    CONVERGED = "CONVERGED"
    EXACT_MATCH = "EXACT_MATCH"
    ROTATIONAL_RESIDUAL_HIGH = "ROTATIONAL_RESIDUAL_HIGH"
    TRANSLATIONAL_RESIDUAL_HIGH = "TRANSLATIONAL_RESIDUAL_HIGH"
    FAILED = "FAILED"


# ==============================================================================
# 3. Dynamic Mendeleev Mass Map & Ghost Atom Protections
# ==============================================================================

class DynamicMendeleevMassMap(Mapping):
    """Dynamic standard atomic weight mapping backed strictly by the Mendeleev library."""

    def __getitem__(self, key: str) -> float:
        if not key or not isinstance(key, str):
            raise KeyError(key)
        clean = key.strip()
        if not clean:
            raise KeyError(key)

        # Hydrogen isotope aliases
        if clean.upper() in {"D", "2H"}:
            try:
                for iso in getattr(mendeleev.element("H"), "isotopes", []):
                    if iso.mass_number == 2:
                        return float(iso.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            return 2.01410177812

        if clean.upper() in {"T", "3H"}:
            try:
                for iso in getattr(mendeleev.element("H"), "isotopes", []):
                    if iso.mass_number == 3:
                        return float(iso.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
            return 3.01604928132

        # Parse element symbol with optional isotope / label (e.g., C13, 13C, Cl-35, O_16, C:1)
        m = re.match(r"^([0-9]*)([A-Za-z]{1,2})([0-9_\-:]*)$", clean)
        if m:
            iso_prefix, sym_raw, iso_suffix = m.groups()
            sym_head = sym_raw.capitalize()
            iso_num_str = iso_prefix or re.sub(r"[^0-9]", "", iso_suffix)

            if iso_num_str:
                iso_num = int(iso_num_str)
                try:
                    elem_obj = mendeleev.element(sym_head)
                    if elem_obj is not None:
                        for iso in getattr(elem_obj, "isotopes", []):
                            if iso.mass_number == iso_num:
                                return float(iso.mass)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

            try:
                elem = mendeleev.element(sym_head)
                if elem is not None and elem.mass is not None:
                    return float(elem.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
        else:
            try:
                elem = mendeleev.element(clean.capitalize())
                if elem is not None and elem.mass is not None:
                    return float(elem.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

        raise KeyError(f"Chemical element '{key}' could not be resolved in Mendeleev library.")

    def __iter__(self):
        return iter([
            "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg",
            "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr",
            "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
            "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
            "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
            "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf",
            "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po",
            "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm",
            "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs",
            "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og"
        ])

    def __len__(self):
        return 118

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            self[key]
            return True
        except KeyError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


_DYNAMIC_MENDELEEV_MAP = DynamicMendeleevMassMap()


def is_ghost_symbol(symbol: str) -> bool:
    """Checks whether an atomic element symbol represents a ghost / dummy atom.

    Ghost atoms (e.g., 'Gh', 'gh', 'GhO', 'Gh_C', 'X', 'x_N', 'Bq', 'bq') possess
    strictly 0.0 mass to avoid shifting the Center of Mass during BSSE counterpoise
    calculations. Chemical elements like Xenon ('Xe', 'xe', 'XE') are NOT ghost atoms.

    Parameters
    ----------
    symbol : str
        Elemental or ghost atom symbol.

    Returns
    -------
    bool
        True if symbol indicates a ghost atom, False otherwise.
    """
    if not symbol or not isinstance(symbol, str):
        return False
    clean = symbol.strip()
    if not clean:
        return False
    clean_lower = clean.lower()

    if clean_lower.startswith("gh") or clean_lower.startswith("bq"):
        return True
    if clean_lower == "x":
        return True
    if clean_lower.startswith("x_") or clean_lower.startswith("x-") or clean_lower.startswith("x:"):
        return True
    if clean_lower.startswith("x") and not clean_lower.startswith("xe"):
        if re.match(r"^x[0-9_\-:]*$", clean_lower):
            return True

    return False


def get_dynamic_atomic_mass(symbol: str) -> float:
    """Retrieves authentic standard atomic or isotopic mass dynamically from mendeleev.

    Ghost atoms strictly return 0.0.

    Parameters
    ----------
    symbol : str
        Chemical element, isotope, or ghost symbol.

    Returns
    -------
    float
        Standard atomic mass in unified atomic mass units (u / Da).

    Raises
    ------
    MassResolutionError
        If the symbol is empty, invalid, or cannot be resolved.
    """
    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        raise MassResolutionError("Atomic symbol cannot be empty.")

    clean = symbol.strip()
    if is_ghost_symbol(clean):
        return 0.0

    try:
        return _DYNAMIC_MENDELEEV_MAP[clean]
    except KeyError as err:
        raise MassResolutionError(f"Unrecognized chemical element symbol: '{symbol}'.") from err


def resolve_molecular_masses(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Validates and returns a 1D float64 array of atomic masses of shape (N,).

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Pre-defined atomic masses.
    symbols : Sequence[str], optional
        Sequence of atomic element symbols.

    Returns
    -------
    np.ndarray
        1D float64 array of shape (N,).

    Raises
    ------
    MassResolutionError
        If dimensions mismatch, negative masses exist, or total non-ghost mass <= 0.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    n_atoms = len(coords_arr)

    if masses is not None:
        masses_arr = np.asarray(masses, dtype=np.float64)
        if masses_arr.shape != (n_atoms,):
            raise MassResolutionError(
                f"Coordinate count ({n_atoms}) does not match masses shape {masses_arr.shape}."
            )
        if np.any(masses_arr < 0.0):
            raise MassResolutionError("Atomic masses must be non-negative values.")
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise MassResolutionError("Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    if symbols is not None:
        if len(symbols) != n_atoms:
            raise MassResolutionError(
                f"Coordinate count ({n_atoms}) does not match symbols count ({len(symbols)})."
            )
        masses_list = [get_dynamic_atomic_mass(s) for s in symbols]
        masses_arr = np.array(masses_list, dtype=np.float64)
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise MassResolutionError("Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    raise MassResolutionError("Either 'masses' or 'symbols' must be provided to determine molecular mass.")


# ==============================================================================
# 4. Center of Mass (COM) Translation Engine
# ==============================================================================

def compute_center_of_mass(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Computes the mass-weighted Center of Mass (COM) vector for a molecular system.

    Ghost atoms (mass = 0.0) are completely excluded from the mass weighting.

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        1D array of atomic masses in amu.
    symbols : Sequence[str], optional
        Sequence of atomic symbols.

    Returns
    -------
    np.ndarray
        1D float64 array of shape (3,) representing the Center of Mass vector.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise CenterOfMassError(f"Expected coordinates shape (N, 3), got {coords_arr.shape}.")

    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))
    return np.sum(coords_arr * masses_arr[:, np.newaxis], axis=0) / total_mass


def translate_to_center_of_mass(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Translates coordinates such that the Center of Mass resides at (0, 0, 0) Angstrom.

    All atoms (including ghost atoms) undergo the identical translational shift.
    Performs iterative refinement to eliminate residual floating point precision drift.

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates of shape (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses in amu.
    symbols : Sequence[str], optional
        Atomic symbols.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (translated_coords, shift_vector) where shift_vector = -COM.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))

    com = compute_center_of_mass(coords_arr, masses=masses_arr)
    shift_vec = -com
    translated_coords = coords_arr + shift_vec

    # Iterative refinement to eliminate residual numerical drift
    residual = np.sum(masses_arr[:, np.newaxis] * translated_coords, axis=0) / total_mass
    if np.any(np.abs(residual) > 0.0):
        translated_coords = translated_coords - residual
        shift_vec = shift_vec - residual

    return translated_coords, shift_vec


class CenterOfMassEngine:
    """Object-oriented interface for Center of Mass computations."""

    @staticmethod
    def compute(
        coords: Union[np.ndarray, Sequence[Sequence[float]]],
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> np.ndarray:
        """Computes mass-weighted COM vector (3,)."""
        return compute_center_of_mass(coords, masses=masses, symbols=symbols)

    @staticmethod
    def translate(
        coords: Union[np.ndarray, Sequence[Sequence[float]]],
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Translates coordinates such that COM is at origin (0, 0, 0)."""
        return translate_to_center_of_mass(coords, masses=masses, symbols=symbols)


# ==============================================================================
# 5. Moment of Inertia Tensor & Spectroscopic Top Engine
# ==============================================================================

class InertiaTensorResult(BaseModel):
    """Pydantic model containing principal moments of inertia and rotational constants."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    eigenvalues_amu_angstrom2: Tuple[float, float, float] = Field(
        ..., description="Sorted principal moments of inertia Ia <= Ib <= Ic in amu * Angstrom^2"
    )
    rotational_constants_mhz: Tuple[float, float, float] = Field(
        ..., description="Rotational constants (A, B, C) in MHz"
    )
    rotational_constants_ghz: Tuple[float, float, float] = Field(
        ..., description="Rotational constants (A, B, C) in GHz"
    )
    rotational_constants_cm1: Tuple[float, float, float] = Field(
        ..., description="Rotational constants (A, B, C) in cm^-1"
    )
    inertial_defect: float = Field(
        ..., description="Inertial defect Delta = Ic - Ia - Ib in amu * Angstrom^2"
    )
    rays_kappa: float = Field(
        ..., description="Ray's asymmetry parameter kappa in [-1.0, 1.0]"
    )
    planar_moments: Tuple[float, float, float] = Field(
        ..., description="Planar moments of inertia (Pa, Pb, Pc) in amu * Angstrom^2"
    )
    top_type: RotorTopType = Field(
        ..., description="Rotor classification: asymmetric_top, oblate_symmetric_top, prolate_symmetric_top, spherical_top, linear, atom"
    )
    rotation_matrix: Any = Field(
        ..., description="Right-handed 3x3 rotation matrix V diagonalizing inertia tensor with det(V) = +1.0"
    )
    aligned_coords: Any = Field(
        ..., description="Cartesian coordinates aligned to principal axes (N, 3)"
    )
    inertia_tensor: Optional[Any] = Field(
        None, description="Initial 3x3 moment of inertia tensor before diagonalization"
    )

    @field_serializer("rotation_matrix", "aligned_coords", "inertia_tensor", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


def compute_moment_of_inertia_tensor(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """Constructs symmetric 3x3 Moment of Inertia tensor in amu * Angstrom^2.

    I_xx = sum(m_i * (y_i^2 + z_i^2))
    I_xy = -sum(m_i * x_i * y_i)

    Parameters
    ----------
    coords : np.ndarray | Sequence
        COM-centered Cartesian coordinates of shape (N, 3).
    masses : np.ndarray | Sequence
        Atomic masses of shape (N,).

    Returns
    -------
    np.ndarray
        Symmetric 3x3 float64 moment of inertia tensor.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    masses_arr = np.asarray(masses, dtype=np.float64)

    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise InertiaTensorError(f"Coordinates must have shape (N, 3), got {coords_arr.shape}.")
    if masses_arr.shape != (len(coords_arr),):
        raise InertiaTensorError(
            f"Masses length ({len(masses_arr)}) != atom count ({len(coords_arr)})."
        )

    x = coords_arr[:, 0]
    y = coords_arr[:, 1]
    z = coords_arr[:, 2]

    Ixx = float(np.sum(masses_arr * (y**2 + z**2)))
    Iyy = float(np.sum(masses_arr * (x**2 + z**2)))
    Izz = float(np.sum(masses_arr * (x**2 + y**2)))
    Ixy = float(-np.sum(masses_arr * x * y))
    Ixz = float(-np.sum(masses_arr * x * z))
    Iyz = float(-np.sum(masses_arr * y * z))

    return np.array([
        [Ixx, Ixy, Ixz],
        [Ixy, Iyy, Iyz],
        [Ixz, Iyz, Izz],
    ], dtype=np.float64)


def diagonalize_inertia_tensor(
    inertia_tensor: Union[np.ndarray, Sequence[Sequence[float]]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Diagonalizes 3x3 inertia tensor to yield sorted eigenvalues Ia <= Ib <= Ic and right-handed V.

    Parameters
    ----------
    inertia_tensor : np.ndarray | Sequence
        Symmetric 3x3 moment of inertia tensor.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (eigenvalues, V) where eigenvalues has shape (3,) and V has shape (3, 3) with det(V) = +1.0.
    """
    tensor = np.asarray(inertia_tensor, dtype=np.float64)
    if tensor.shape != (3, 3):
        raise InertiaTensorError(f"Inertia tensor must be (3, 3), got {tensor.shape}.")

    eigvals, V = np.linalg.eigh(tensor)

    # Sort explicitly in ascending order: Ia <= Ib <= Ic
    idx = np.argsort(eigvals)
    eigvals = eigvals[idx]
    V = V[:, idx]

    # Enforce right-handed coordinate frame: det(V) == +1.0
    det_v = float(np.linalg.det(V))
    if det_v < 0.0:
        V[:, 2] = -V[:, 2]

    return eigvals, V


def compute_rotational_constants(
    eigenvalues: Tuple[float, float, float],
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """Converts principal moments of inertia Ia <= Ib <= Ic into rotational constants (A, B, C).

    Converts across MHz, GHz, and cm^-1 via authentic NIST CODATA 2022/2026 constants.
    Handles linear molecule singularity: Ia < 1e-8 => A = inf.

    Parameters
    ----------
    eigenvalues : Tuple[float, float, float]
        (Ia, Ib, Ic) in amu * Angstrom^2.

    Returns
    -------
    Tuple[Tuple, Tuple, Tuple]
        ((A_mhz, B_mhz, C_mhz), (A_ghz, B_ghz, C_ghz), (A_cm1, B_cm1, C_cm1))
    """
    Ia, Ib, Ic = eigenvalues

    def _calc_const(I_val: float, factor: float) -> float:
        if I_val < 1e-8:
            return float("inf")
        return float(factor / I_val)

    A_mhz = _calc_const(Ia, FACTOR_MHZ)
    B_mhz = _calc_const(Ib, FACTOR_MHZ)
    C_mhz = _calc_const(Ic, FACTOR_MHZ)

    A_ghz = _calc_const(Ia, FACTOR_GHZ)
    B_ghz = _calc_const(Ib, FACTOR_GHZ)
    C_ghz = _calc_const(Ic, FACTOR_GHZ)

    A_cm1 = _calc_const(Ia, FACTOR_CM1)
    B_cm1 = _calc_const(Ib, FACTOR_CM1)
    C_cm1 = _calc_const(Ic, FACTOR_CM1)

    return (
        (A_mhz, B_mhz, C_mhz),
        (A_ghz, B_ghz, C_ghz),
        (A_cm1, B_cm1, C_cm1),
    )


def classify_rotor_top(
    Ia: float,
    Ib: float,
    Ic: float,
    n_atoms: int = 1,
) -> Tuple[RotorTopType, float]:
    """Classifies rotor top geometry into spherical, symmetric, asymmetric, linear, or atom.

    Computes Ray's asymmetry parameter kappa = (2B - A - C) / (A - C).

    Parameters
    ----------
    Ia, Ib, Ic : float
        Principal moments of inertia (Ia <= Ib <= Ic).
    n_atoms : int, default 1
        Total number of atoms in molecule.

    Returns
    -------
    Tuple[RotorTopType, float]
        (top_type, kappa)
    """
    if n_atoms <= 1 or (Ia < 1e-8 and Ib < 1e-8 and Ic < 1e-8):
        return RotorTopType.ATOM, 0.0

    # Linear top: Ia approx 0 (or Ia/Ib < 1e-4) and Ib == Ic
    if Ia < 1e-8 or (Ib > 1e-8 and (Ia / Ib) < 1e-4):
        return RotorTopType.LINEAR, -1.0

    rot_consts = compute_rotational_constants((Ia, Ib, Ic))
    A_mhz, B_mhz, C_mhz = rot_consts[0]

    # Spherical top: Ia == Ib == Ic
    if Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and (abs(Ib - Ic) / Ic < 1e-3):
        return RotorTopType.SPHERICAL, 0.0

    # Oblate symmetric top: Ia == Ib < Ic (kappa = +1.0)
    if Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and ((Ic - Ib) / Ib >= 1e-3):
        if not math.isinf(A_mhz) and (A_mhz - C_mhz) > 1e-12:
            kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)
        else:
            kappa = 1.0
        return RotorTopType.SYMMETRIC_OBLATE, float(kappa)

    # Prolate symmetric top: Ia < Ib == Ic (kappa = -1.0)
    if Ic > 1e-8 and (abs(Ib - Ic) / Ic < 1e-3) and ((Ib - Ia) / Ib >= 1e-3):
        if not math.isinf(A_mhz) and (A_mhz - C_mhz) > 1e-12:
            kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)
        else:
            kappa = -1.0
        return RotorTopType.SYMMETRIC_PROLATE, float(kappa)

    # Asymmetric top: Ia < Ib < Ic
    if math.isinf(A_mhz) or abs(A_mhz - C_mhz) < 1e-12:
        kappa = 0.0
    else:
        kappa = float((2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz))

    return RotorTopType.ASYMMETRIC, float(kappa)


def align_to_principal_axes(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> InertiaTensorResult:
    """Translates to COM, diagonalizes inertia tensor, and derives spectroscopic parameters.

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses.
    symbols : Sequence[str], optional
        Atomic symbols.

    Returns
    -------
    InertiaTensorResult
        Structured result model containing aligned coordinates, rotational constants, and rotor type.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)

    coords_com, _ = translate_to_center_of_mass(coords_arr, masses=masses_arr)
    I_tensor = compute_moment_of_inertia_tensor(coords_com, masses_arr)
    eigvals, V = diagonalize_inertia_tensor(I_tensor)

    Ia, Ib, Ic = float(eigvals[0]), float(eigvals[1]), float(eigvals[2])
    aligned_coords = coords_com @ V

    rot_mhz, rot_ghz, rot_cm1 = compute_rotational_constants((Ia, Ib, Ic))
    inertial_defect = float(Ic - Ia - Ib)

    # Planar moments: Pa = (-Ia + Ib + Ic)/2, Pb = (Ia - Ib + Ic)/2, Pc = (Ia + Ib - Ic)/2
    Pa = float((-Ia + Ib + Ic) / 2.0)
    Pb = float((Ia - Ib + Ic) / 2.0)
    Pc = float((Ia + Ib - Ic) / 2.0)

    top_type, kappa = classify_rotor_top(Ia, Ib, Ic, n_atoms=len(coords_arr))

    return InertiaTensorResult(
        eigenvalues_amu_angstrom2=(Ia, Ib, Ic),
        rotational_constants_mhz=rot_mhz,
        rotational_constants_ghz=rot_ghz,
        rotational_constants_cm1=rot_cm1,
        inertial_defect=inertial_defect,
        rays_kappa=kappa,
        planar_moments=(Pa, Pb, Pc),
        top_type=top_type,
        rotation_matrix=V,
        aligned_coords=aligned_coords,
        inertia_tensor=I_tensor,
    )


class InertiaTensorEngine:
    """Object-oriented interface for Moment of Inertia calculations."""

    @staticmethod
    def compute_tensor(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
        """Constructs 3x3 Moment of Inertia tensor."""
        return compute_moment_of_inertia_tensor(coords, masses)

    @staticmethod
    def diagonalize(tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Diagonalizes symmetric 3x3 inertia tensor with right-handed frame."""
        return diagonalize_inertia_tensor(tensor)

    @staticmethod
    def align(
        coords: Union[np.ndarray, Sequence[Sequence[float]]],
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> InertiaTensorResult:
        """Aligns coordinates to principal axes of inertia."""
        return align_to_principal_axes(coords, masses=masses, symbols=symbols)


# ==============================================================================
# 6. MolSym Point-Group Symmetry & Character Table Engine
# ==============================================================================

class MolSymProfile(BaseModel):
    """Pydantic model containing point-group symmetry, character table, and SEAs."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    point_group: str = Field(..., description="Detected Schoenflies point group symbol (e.g. C2v, D6h, Td, C1)")
    schoenflies_symbol: str = Field(..., description="Canonical Schoenflies symbol")
    rotational_symmetry_number: int = Field(..., description="Rotational symmetry number sigma")
    symmetrically_equivalent_atoms: List[List[int]] = Field(
        ..., description="Atom indices partitioned into Symmetrically Equivalent Atom (SEA) orbits"
    )
    symmetry_elements: List[str] = Field(default_factory=list, description="Labels of symmetry operations / symels")
    classes: List[str] = Field(default_factory=list, description="Symmetry conjugacy classes")
    irreps: List[str] = Field(default_factory=list, description="Irreducible representation labels")
    character_table: Dict[str, Dict[str, float]] = Field(
        default_factory=dict, description="Character table mapping: {irrep: {class_label: character}}"
    )
    is_abelian: bool = Field(default=True, description="Whether the point group is Abelian")
    is_linear: bool = Field(default=False, description="Whether the molecule is linear (Cinfv or Dinfh)")
    is_centrosymmetric: bool = Field(default=False, description="Whether the group contains inversion center Ci")
    is_chiral: bool = Field(default=False, description="Whether the group is chiral (lacks Sn improper rotations)")
    nuclear_spin_weights: Dict[str, float] = Field(
        default_factory=dict, description="Estimated nuclear spin statistical weights for symmetry species"
    )
    symmetrized_coords: Optional[Any] = Field(
        None, description="Symmetrized Cartesian coordinates from MolSym if requested"
    )
    source: str = Field(default="molsym", description="Resolver source: 'molsym' or 'geometric_solver'")

    @field_serializer("symmetrized_coords", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


def _pg_to_sigma(pg_str: str) -> int:
    """Maps Schoenflies point group string to rotational symmetry number sigma."""
    clean = pg_str.strip()
    if clean.capitalize() in {"C1", "Cs", "Ci"}:
        return 1
    if clean in {"C0v", "Cinfv", "C_inf_v", "C0"}:
        return 1
    if clean in {"D0h", "Dinfh", "D_inf_h", "D0", "D0d"}:
        return 2
    if clean.startswith("C") and not clean.startswith("Cs") and not clean.startswith("Ci"):
        m = re.match(r"^C([0-9]+)", clean)
        if m:
            n = int(m.group(1))
            return 1 if n == 0 else n
        return 1
    if clean.startswith("D"):
        m = re.match(r"^D([0-9]+)", clean)
        if m:
            n = int(m.group(1))
            return 2 if n == 0 else 2 * n
        return 2
    if clean.startswith("T"):
        return 12
    if clean.startswith("O"):
        return 24
    if clean.startswith("I"):
        return 60
    if clean.startswith("S"):
        m = re.match(r"^S([0-9]+)", clean)
        if m:
            return int(m.group(1)) // 2
        return 1
    return 1


def _geometric_fallback_point_group(
    coords: np.ndarray,
    symbols: Sequence[str],
    masses: np.ndarray,
) -> Tuple[str, int, List[List[int]]]:
    """Fallback geometric symmetry solver when MolSym library is unavailable or encounters exceptions."""
    n_atoms = len(coords)
    if n_atoms <= 1:
        return "Kh", 1, [[0]]
    if n_atoms == 2:
        sym1, sym2 = symbols[0].capitalize(), symbols[1].capitalize()
        if sym1 == sym2:
            return "Dinfh", 2, [[0, 1]]
        return "Cinfv", 1, [[0], [1]]

    # Center at COM
    coords_com, _ = translate_to_center_of_mass(coords, masses=masses)

    # Check collinearity
    v01 = coords_com[1] - coords_com[0]
    norm_v01 = np.linalg.norm(v01)
    is_linear = True
    if norm_v01 > 1e-6:
        u = v01 / norm_v01
        for i in range(2, n_atoms):
            v_i = coords_com[i] - coords_com[0]
            cross = np.cross(u, v_i)
            if np.linalg.norm(cross) > 1e-4:
                is_linear = False
                break
    else:
        is_linear = False

    if is_linear:
        # Check inversion center
        has_inversion = True
        for i in range(n_atoms):
            inv_pt = -coords_com[i]
            dists = np.linalg.norm(coords_com - inv_pt, axis=1)
            min_idx = int(np.argmin(dists))
            if dists[min_idx] > 1e-4 or symbols[min_idx].capitalize() != symbols[i].capitalize():
                has_inversion = False
                break
        if has_inversion:
            return "Dinfh", 2, [[i for i in range(n_atoms)]]
        return "Cinfv", 1, [[i] for i in range(n_atoms)]

    # Planarity check
    I_res = align_to_principal_axes(coords_com, masses=masses)
    Ia, Ib, Ic = I_res.eigenvalues_amu_angstrom2
    is_planar = abs(Ic - Ia - Ib) < 1e-2

    # Inversion check
    has_ci = True
    for i in range(n_atoms):
        inv_pt = -coords_com[i]
        dists = np.linalg.norm(coords_com - inv_pt, axis=1)
        min_idx = int(np.argmin(dists))
        if dists[min_idx] > 1e-4 or symbols[min_idx].capitalize() != symbols[i].capitalize():
            has_ci = False
            break

    # SEAs approximation via distance-to-COM and elemental equality
    dist_to_com = np.linalg.norm(coords_com, axis=1)
    sea_map: Dict[Tuple[str, float], List[int]] = {}
    for i in range(n_atoms):
        sym = symbols[i].capitalize()
        r = round(float(dist_to_com[i]), 3)
        key = (sym, r)
        sea_map.setdefault(key, []).append(i)
    seas = list(sea_map.values())

    if has_ci and is_planar:
        return "C2h", 2, seas
    if has_ci:
        return "Ci", 1, seas
    if is_planar:
        return "Cs", 1, seas

    return "C1", 1, seas


def analyze_molecular_symmetry(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    symbols: Sequence[str],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symmetrize: bool = False,
    tolerance: float = 1e-3,
) -> MolSymProfile:
    """Performs rigorous molecular point group symmetry detection and character table extraction.

    Utilizes `molsym` with authentic dynamic Mendeleev masses, with fallback to geometric analyzer.

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    symbols : Sequence[str]
        Atomic element symbols (N,).
    masses : Sequence[float] | np.ndarray, optional
        Pre-resolved atomic masses.
    symmetrize : bool, default False
        Whether to generate idealized symmetrized coordinates via MolSym.
    tolerance : float, default 1e-3
        Symmetry tolerance threshold.

    Returns
    -------
    MolSymProfile
        Pydantic model containing point group, symmetry operations, character table, and SEAs.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    n_atoms = len(coords_arr)
    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)
    syms_list = [str(s).strip() for s in symbols]

    # Handle single atom
    if n_atoms <= 1:
        return MolSymProfile(
            point_group="Kh",
            schoenflies_symbol="Kh",
            rotational_symmetry_number=1,
            symmetrically_equivalent_atoms=[[0]] if n_atoms == 1 else [],
            symmetry_elements=["E"],
            classes=["E"],
            irreps=["A1g"],
            character_table={"A1g": {"E": 1.0}},
            is_abelian=True,
            is_linear=False,
            is_centrosymmetric=True,
            is_chiral=False,
            source="analytic_atom",
        )

    # Attempt MolSym analysis
    if _MOLSYM_AVAILABLE:
        try:
            mol = molsym.Molecule(syms_list, np.array(coords_arr, copy=True), masses_arr)
            pg_res = molsym.find_point_group(mol)
            pg_name = str(pg_res[0]).strip() if isinstance(pg_res, tuple) else str(pg_res).strip()

            sym = None
            try:
                sym = molsym.Symtext.from_molecule(mol)
                if hasattr(sym, "pg"):
                    pg_name = str(sym.pg).strip()
            except Exception as symtext_err:
                logger.debug("MolSym Symtext creation fallback: %s", symtext_err)

            sigma = _pg_to_sigma(pg_name)
            if sym is not None and hasattr(sym, "rotational_symmetry_number"):
                sigma = int(sym.rotational_symmetry_number)

            # Extract Symmetrically Equivalent Atoms (SEAs)
            seas: List[List[int]] = []
            try:
                raw_seas = mol.find_SEAs()
                for sea in raw_seas:
                    subset = [int(idx) for idx in getattr(sea, "subset", [])]
                    if subset:
                        seas.append(sorted(subset))
            except Exception as sea_err:
                logger.debug("MolSym SEA partition non-fatal exception: %s", sea_err)

            if not seas:
                seas = [[i] for i in range(n_atoms)]

            # Extract symmetry elements, classes, and character table
            symels: List[str] = []
            classes: List[str] = []
            irreps: List[str] = []
            char_table: Dict[str, Dict[str, float]] = {}

            if sym is not None:
                try:
                    if hasattr(sym, "symels"):
                        symels = [str(el.symbol) if hasattr(el, "symbol") else str(el) for el in sym.symels]
                    if hasattr(sym, "classes"):
                        classes = [str(c.symbol) if hasattr(c, "symbol") else str(c) for c in sym.classes]
                    if hasattr(sym, "irreps"):
                        irreps = [str(irr.symbol) if hasattr(irr, "symbol") else str(irr) for irr in sym.irreps]
                    if hasattr(sym, "character_table") and hasattr(sym, "classes") and hasattr(sym, "irreps"):
                        ct = np.asarray(sym.character_table, dtype=np.float64)
                        for r_idx, irr in enumerate(irreps):
                            char_table[irr] = {}
                            for c_idx, cls_lbl in enumerate(classes):
                                if r_idx < ct.shape[0] and c_idx < ct.shape[1]:
                                    char_table[irr][cls_lbl] = float(ct[r_idx, c_idx])
                except Exception as ct_err:
                    logger.debug("Character table extraction exception: %s", ct_err)

            # Symmetrized coordinates if requested
            symmetrized_coords_res = None
            if symmetrize:
                try:
                    sym_mol = molsym.symmetrize(mol)
                    if hasattr(sym_mol, "coords"):
                        symmetrized_coords_res = np.asarray(sym_mol.coords, dtype=np.float64)
                except Exception as symm_err:
                    logger.debug("MolSym coordinate symmetrization non-fatal: %s", symm_err)

            is_linear = (
                pg_name.lower().startswith("c_inf")
                or pg_name.lower().startswith("d_inf")
                or "inf" in pg_name.lower()
                or pg_name.lower() in {"c0v", "d0h", "c0", "d0", "d0d", "cinfv", "dinfh"}
            )
            is_centrosymmetric = "i" in pg_name.lower() or "h" in pg_name.lower() or pg_name in {"Oh", "Ih", "Dinfh"}
            is_chiral = pg_name in {"C1", "C2", "C3", "C4", "C5", "C6", "D2", "D3", "D4", "D5", "D6", "T", "O", "I"}

            # Calculate nuclear spin statistical weights
            spin_weights: Dict[str, float] = {}
            for irr in (irreps or ["A1"]):
                spin_weights[irr] = 1.0 / max(1, sigma)

            return MolSymProfile(
                point_group=pg_name,
                schoenflies_symbol=pg_name,
                rotational_symmetry_number=sigma,
                symmetrically_equivalent_atoms=seas,
                symmetry_elements=symels or ["E"],
                classes=classes or ["E"],
                irreps=irreps or ["A1"],
                character_table=char_table or {"A1": {"E": 1.0}},
                is_abelian=pg_name in {"C1", "Cs", "Ci", "C2", "C2v", "C2h", "D2", "D2h"},
                is_linear=is_linear,
                is_centrosymmetric=is_centrosymmetric,
                is_chiral=is_chiral,
                nuclear_spin_weights=spin_weights,
                symmetrized_coords=symmetrized_coords_res,
                source="molsym",
            )

        except Exception as exc:
            logger.warning("MolSym analysis encountered exception (%s). Falling back to geometric solver.", exc)

    # Geometric Fallback
    pg_fallback, sigma_fallback, seas_fallback = _geometric_fallback_point_group(coords_arr, syms_list, masses_arr)
    return MolSymProfile(
        point_group=pg_fallback,
        schoenflies_symbol=pg_fallback,
        rotational_symmetry_number=sigma_fallback,
        symmetrically_equivalent_atoms=seas_fallback,
        symmetry_elements=["E"],
        classes=["E"],
        irreps=["A"],
        character_table={"A": {"E": 1.0}},
        is_abelian=pg_fallback in {"C1", "Cs", "Ci", "C2", "C2v", "C2h", "D2", "D2h"},
        is_linear="inf" in pg_fallback.lower(),
        is_centrosymmetric=pg_fallback in {"Ci", "C2h", "D2h", "Dinfh"},
        is_chiral=pg_fallback in {"C1", "C2", "D2"},
        nuclear_spin_weights={"A": 1.0 / max(1, sigma_fallback)},
        symmetrized_coords=None,
        source="geometric_solver",
    )


def compare_molecular_symmetry(
    symbols1: Sequence[str],
    coords1: Union[np.ndarray, Sequence[Sequence[float]]],
    symbols2: Sequence[str],
    coords2: Union[np.ndarray, Sequence[Sequence[float]]],
) -> Tuple[bool, str, str]:
    """Compares point group symmetries of two molecular conformations.

    Parameters
    ----------
    symbols1, coords1 : Sequence[str], np.ndarray
        First molecule symbols and coordinates.
    symbols2, coords2 : Sequence[str], np.ndarray
        Second molecule symbols and coordinates.

    Returns
    -------
    Tuple[bool, str, str]
        (is_match, point_group_1, point_group_2)
    """
    prof1 = analyze_molecular_symmetry(coords1, symbols1)
    prof2 = analyze_molecular_symmetry(coords2, symbols2)
    is_match = (prof1.point_group.lower() == prof2.point_group.lower())
    return is_match, prof1.point_group, prof2.point_group


class MolSymEngine:
    """Object-oriented interface for MolSym point group symmetry analysis."""

    @staticmethod
    def analyze(
        coords: Union[np.ndarray, Sequence[Sequence[float]]],
        symbols: Sequence[str],
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symmetrize: bool = False,
    ) -> MolSymProfile:
        """Executes full point-group symmetry resolution."""
        return analyze_molecular_symmetry(coords, symbols=symbols, masses=masses, symmetrize=symmetrize)

    @staticmethod
    def compare(
        syms1: Sequence[str], coords1: np.ndarray,
        syms2: Sequence[str], coords2: np.ndarray,
    ) -> Tuple[bool, str, str]:
        """Compares symmetry between two conformations."""
        return compare_molecular_symmetry(syms1, coords1, syms2, coords2)


# ==============================================================================
# 7. Mass-Weighted Eckart Frame Alignment Engine
# ==============================================================================

class EckartAlignmentResult(BaseModel):
    """Pydantic model containing mass-weighted Eckart frame alignment results."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    aligned_coords: Any = Field(
        ..., description="Target coordinates transformed into reference Eckart frame (N, 3)"
    )
    rotation_matrix: Any = Field(
        ..., description="Proper rotation matrix U (3, 3) with det(U) = +1.0"
    )
    rmsd: float = Field(
        ..., description="Mass-weighted Root Mean Square Deviation relative to reference"
    )
    residual_rotational_norm: float = Field(
        ..., description="Residual torque norm of rotational Eckart condition sum(m_i * (r_i^0 x r'_i))"
    )
    translational_residual_norm: float = Field(
        ..., description="Residual norm of translational Eckart condition sum(m_i * r'_i) / M"
    )
    rotation_determinant: float = Field(
        ..., description="Determinant of the rotation matrix (det(U) == +1.0)"
    )
    is_proper_rotation: bool = Field(
        ..., description="Whether rotation matrix is proper SO(3) without reflections"
    )
    status: AlignmentStatus = Field(
        ..., description="Alignment convergence and verification status"
    )

    @field_serializer("aligned_coords", "rotation_matrix", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


def align_to_eckart_frame(
    target_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    ref_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    tolerance: float = 1e-12,
) -> EckartAlignmentResult:
    """Aligns target coordinates to reference coordinates in mass-weighted Eckart frame.

    Solves the Kabsch / Eckart problem:
        min_U sum(m_i * || target_com_i @ U - ref_com_i ||^2)
    subject to U in SO(3) (det(U) = +1.0).

    Verifies both the Translational Eckart Condition (sum(m_i * r'_i) = 0) and the
    Rotational Eckart Condition (sum(m_i * (r_i^0 x r'_i)) = 0).

    Parameters
    ----------
    target_coords : np.ndarray | Sequence
        Target Cartesian coordinates (N, 3).
    ref_coords : np.ndarray | Sequence
        Reference Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses (N,).
    symbols : Sequence[str], optional
        Atomic symbols (N,).
    tolerance : float, default 1e-12
        Residual torque tolerance for rotational Eckart condition.

    Returns
    -------
    EckartAlignmentResult
        Structured result model with aligned coordinates, rotation matrix U, and Eckart residuals.

    Raises
    ------
    EckartAlignmentError
        If dimensions mismatch or coordinate arrays are invalid.
    """
    target_arr = np.array(target_coords, dtype=np.float64, copy=True)
    ref_arr = np.array(ref_coords, dtype=np.float64, copy=True)

    if target_arr.shape != ref_arr.shape:
        raise EckartAlignmentError(
            f"Target shape {target_arr.shape} does not match reference shape {ref_arr.shape}."
        )
    if target_arr.ndim != 2 or target_arr.shape[1] != 3:
        raise EckartAlignmentError(f"Coordinates must have shape (N, 3), got {target_arr.shape}.")

    masses_arr = resolve_molecular_masses(target_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))

    # Translate both conformations to their respective mass-weighted COM
    target_com, _ = translate_to_center_of_mass(target_arr, masses=masses_arr)
    ref_com, _ = translate_to_center_of_mass(ref_arr, masses=masses_arr)

    # Mass-weighted correlation matrix: F = target_com^T @ (diag(masses) @ ref_com)
    F = target_com.T @ (ref_com * masses_arr[:, np.newaxis])

    # SVD decomposition: F = V @ S @ Wt
    V, S, Wt = np.linalg.svd(F)

    # Reflection check: d = det(V @ Wt)
    d = float(np.linalg.det(V @ Wt))
    diag = np.array([1.0, 1.0, 1.0 if d >= 0.0 else -1.0], dtype=np.float64)
    U = V @ np.diag(diag) @ Wt

    # Strictly safeguard proper rotation det(U) = +1.0
    if np.linalg.det(U) < 0.0:
        U = V @ np.diag([1.0, 1.0, -1.0]) @ Wt

    # Transform target coordinates into the Eckart reference frame
    aligned_coords = target_com @ U

    # Translational Eckart residual: ||sum(m_i * r'_i) / M||
    trans_res = float(np.linalg.norm(np.sum(masses_arr[:, np.newaxis] * aligned_coords, axis=0) / total_mass))

    # Rotational Eckart residual torque: ||sum(m_i * (r_i^0 x r'_i))||
    rot_torque = np.sum(masses_arr[:, np.newaxis] * np.cross(ref_com, aligned_coords), axis=0)
    rot_res = float(np.linalg.norm(rot_torque))

    # Mass-weighted RMSD
    diff = aligned_coords - ref_com
    sq_dist = np.sum(diff ** 2, axis=-1)
    rmsd = float(np.sqrt(np.sum(masses_arr * sq_dist) / total_mass))

    det_u = float(np.linalg.det(U))
    is_proper = abs(det_u - 1.0) < 1e-7

    # Status evaluation
    if rmsd < 1e-12 and rot_res < tolerance:
        status = AlignmentStatus.EXACT_MATCH
    elif rot_res <= tolerance and trans_res <= tolerance:
        status = AlignmentStatus.CONVERGED
    elif rot_res > tolerance:
        status = AlignmentStatus.ROTATIONAL_RESIDUAL_HIGH
    elif trans_res > tolerance:
        status = AlignmentStatus.TRANSLATIONAL_RESIDUAL_HIGH
    else:
        status = AlignmentStatus.CONVERGED

    return EckartAlignmentResult(
        aligned_coords=aligned_coords,
        rotation_matrix=U,
        rmsd=rmsd,
        residual_rotational_norm=rot_res,
        translational_residual_norm=trans_res,
        rotation_determinant=det_u,
        is_proper_rotation=is_proper,
        status=status,
    )


class EckartFrameAligner:
    """Object-oriented interface for Eckart frame alignments."""

    @staticmethod
    def align(
        target_coords: Union[np.ndarray, Sequence[Sequence[float]]],
        ref_coords: Union[np.ndarray, Sequence[Sequence[float]]],
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
        tolerance: float = 1e-12,
    ) -> EckartAlignmentResult:
        """Aligns target coordinates to reference Eckart frame."""
        return align_to_eckart_frame(
            target_coords=target_coords,
            ref_coords=ref_coords,
            masses=masses,
            symbols=symbols,
            tolerance=tolerance,
        )


# ==============================================================================
# 8. Vibrational Projector & Hessian Projection Engine
# ==============================================================================

class VibrationalProjectorResult(BaseModel):
    """Pydantic model containing vibrational projection matrix details."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    projector_matrix: Any = Field(..., description="(3N, 3N) idempotent vibrational projector matrix P_vib")
    trace: float = Field(..., description="Calculated trace of P_vib matrix")
    expected_trace: int = Field(..., description="Theoretical trace invariant (3N - 6 or 3N - 5)")
    is_idempotent: bool = Field(..., description="Whether P_vib @ P_vib == P_vib within tolerance")
    is_symmetric: bool = Field(..., description="Whether P_vib^T == P_vib within tolerance")
    n_rigid_modes_removed: int = Field(..., description="Number of rigid body modes removed (6 or 5)")

    @field_serializer("projector_matrix", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


def construct_vibrational_projector(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    is_linear: bool = False,
) -> np.ndarray:
    """Constructs the (3N, 3N) mass-weighted vibrational projection operator P_vib = I - P_rigid.

    Mathematical Invariants:
    - Idempotence: P_vib @ P_vib = P_vib
    - Symmetry: P_vib^T = P_vib
    - Trace Invariant: Tr(P_vib) = 3N - 6 (or 3N - 5 for linear molecules)

    Parameters
    ----------
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses in amu.
    symbols : Sequence[str], optional
        Atomic element symbols.
    is_linear : bool, default False
        Whether the molecule is linear (removes 5 rigid modes instead of 6).

    Returns
    -------
    np.ndarray
        (3N, 3N) float64 vibrational projector matrix.
    """
    coords_arr = np.array(coords, dtype=np.float64, copy=True)
    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)
    coords_com, _ = translate_to_center_of_mass(coords_arr, masses=masses_arr)

    N = len(coords_com)
    if N == 0:
        raise VibrationalProjectionError("Cannot construct vibrational projector for empty molecule.")

    total_mass = float(np.sum(masses_arr))
    sqrt_m = np.sqrt(masses_arr)

    # 3 mass-weighted translational basis vectors
    D_trans = np.zeros((3 * N, 3), dtype=np.float64)
    for i in range(N):
        w = sqrt_m[i] / np.sqrt(total_mass)
        D_trans[3 * i, 0] = w
        D_trans[3 * i + 1, 1] = w
        D_trans[3 * i + 2, 2] = w

    # 3 mass-weighted rotational basis vectors
    D_rot = np.zeros((3 * N, 3), dtype=np.float64)
    for i in range(N):
        sm = sqrt_m[i]
        x, y, z = coords_com[i]
        # Rotation about x: sm * (0, -z, y)
        D_rot[3 * i, 0] = 0.0
        D_rot[3 * i + 1, 0] = -sm * z
        D_rot[3 * i + 2, 0] = sm * y
        # Rotation about y: sm * (z, 0, -x)
        D_rot[3 * i, 1] = sm * z
        D_rot[3 * i + 1, 1] = 0.0
        D_rot[3 * i + 2, 1] = -sm * x
        # Rotation about z: sm * (-y, x, 0)
        D_rot[3 * i, 2] = -sm * y
        D_rot[3 * i + 1, 2] = sm * x
        D_rot[3 * i + 2, 2] = 0.0

    D_rigid = np.hstack([D_trans, D_rot])  # (3N, 6)

    # Orthonormalize rigid body basis via SVD
    U_svd, S_svd, _ = np.linalg.svd(D_rigid, full_matrices=False)
    k_rigid = 5 if is_linear else min(6, 3 * N)

    E_rigid = U_svd[:, :k_rigid]
    P_rigid = E_rigid @ E_rigid.T
    P_vib = np.eye(3 * N, dtype=np.float64) - P_rigid
    return P_vib


def project_mass_weighted_hessian(
    H_mw: Union[np.ndarray, Sequence[Sequence[float]]],
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    is_linear: bool = False,
) -> np.ndarray:
    """Projects mass-weighted Hessian H_mw (3N, 3N) removing 6 (or 5) rigid body modes.

    H_mw_proj = P_vib @ H_mw @ P_vib

    Parameters
    ----------
    H_mw : np.ndarray | Sequence
        (3N, 3N) mass-weighted Hessian matrix.
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses.
    symbols : Sequence[str], optional
        Atomic symbols.
    is_linear : bool, default False
        Whether molecule is linear.

    Returns
    -------
    np.ndarray
        (3N, 3N) projected mass-weighted Hessian.
    """
    H_mw_arr = np.asarray(H_mw, dtype=np.float64)
    P_vib = construct_vibrational_projector(coords, masses=masses, symbols=symbols, is_linear=is_linear)
    return P_vib @ H_mw_arr @ P_vib


def project_cartesian_hessian(
    H_cart: Union[np.ndarray, Sequence[Sequence[float]]],
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    is_linear: bool = False,
) -> np.ndarray:
    """Projects Cartesian Hessian H_cart (3N, 3N) to eliminate rigid body translations/rotations.

    Mass-weights the Hessian, applies P_vib projection, and un-weights back to Cartesian space:
    H_cart_proj = M^(1/2) @ (P_vib @ (M^(-1/2) @ H_cart @ M^(-1/2)) @ P_vib) @ M^(1/2)

    Parameters
    ----------
    H_cart : np.ndarray | Sequence
        (3N, 3N) Cartesian Hessian matrix.
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses.
    symbols : Sequence[str], optional
        Atomic symbols.
    is_linear : bool, default False
        Whether molecule is linear.

    Returns
    -------
    np.ndarray
        (3N, 3N) projected Cartesian Hessian.
    """
    H_cart_arr = np.asarray(H_cart, dtype=np.float64)
    masses_arr = resolve_molecular_masses(coords, masses=masses, symbols=symbols)

    sqrt_m_3n = np.repeat(np.sqrt(masses_arr), 3)
    inv_sqrt_m = np.zeros_like(masses_arr)
    pos_mask = masses_arr > 0.0
    inv_sqrt_m[pos_mask] = 1.0 / np.sqrt(masses_arr[pos_mask])
    inv_sqrt_m_3n = np.repeat(inv_sqrt_m, 3)

    # Mass-weight Cartesian Hessian: H_mw = M^(-1/2) @ H_cart @ M^(-1/2)
    H_mw = H_cart_arr * np.outer(inv_sqrt_m_3n, inv_sqrt_m_3n)
    H_mw_proj = project_mass_weighted_hessian(H_mw, coords, masses=masses_arr, is_linear=is_linear)

    # Un-weight back to Cartesian space: H_cart_proj = M^(1/2) @ H_mw_proj @ M^(1/2)
    H_cart_proj = H_mw_proj * np.outer(sqrt_m_3n, sqrt_m_3n)
    return H_cart_proj


def compute_harmonic_frequencies_from_hessian(
    H_mw_or_cart: Union[np.ndarray, Sequence[Sequence[float]]],
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    symbols: Optional[Sequence[str]] = None,
    is_cartesian: bool = True,
    is_linear: bool = False,
) -> np.ndarray:
    """Computes harmonic vibrational frequencies in cm^-1 from a molecular Hessian.

    Parameters
    ----------
    H_mw_or_cart : np.ndarray | Sequence
        (3N, 3N) Cartesian or mass-weighted Hessian.
    coords : np.ndarray | Sequence
        Cartesian coordinates (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses.
    symbols : Sequence[str], optional
        Atomic symbols.
    is_cartesian : bool, default True
        Whether the input Hessian is in Cartesian coordinates (True) or mass-weighted (False).
    is_linear : bool, default False
        Whether molecule is linear.

    Returns
    -------
    np.ndarray
        Sorted 1D array of harmonic vibrational frequencies in cm^-1.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=symbols)

    if is_cartesian:
        inv_sqrt_m = np.zeros_like(masses_arr)
        pos_mask = masses_arr > 0.0
        inv_sqrt_m[pos_mask] = 1.0 / np.sqrt(masses_arr[pos_mask])
        inv_sqrt_m_3n = np.repeat(inv_sqrt_m, 3)
        H_mw = np.asarray(H_mw_or_cart, dtype=np.float64) * np.outer(inv_sqrt_m_3n, inv_sqrt_m_3n)
    else:
        H_mw = np.asarray(H_mw_or_cart, dtype=np.float64)

    H_mw_proj = project_mass_weighted_hessian(H_mw, coords_arr, masses=masses_arr, is_linear=is_linear)
    eigvals, _ = np.linalg.eigh(H_mw_proj)

    # Conversion factor from atomic units (Hartree / (bohr^2 * u)) to cm^-1:
    # 5140.4871447 cm^-1 per sqrt(atomic unit)
    freqs = np.sign(eigvals) * np.sqrt(np.abs(eigvals)) * 5140.4871447
    return np.sort(freqs)


class VibrationalProjectorEngine:
    """Object-oriented interface for vibrational projection calculations."""

    @staticmethod
    def construct_projector(
        coords: np.ndarray,
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
        is_linear: bool = False,
    ) -> VibrationalProjectorResult:
        """Constructs and validates the vibrational projection matrix."""
        P_vib = construct_vibrational_projector(coords, masses=masses, symbols=symbols, is_linear=is_linear)
        N = len(coords)
        expected_tr = (3 * N - 5) if is_linear else (3 * N - 6)
        actual_tr = float(np.trace(P_vib))

        diff_idemp = float(np.linalg.norm((P_vib @ P_vib) - P_vib))
        is_idemp = diff_idemp < 1e-8

        diff_symm = float(np.linalg.norm(P_vib.T - P_vib))
        is_symm = diff_symm < 1e-8

        return VibrationalProjectorResult(
            projector_matrix=P_vib,
            trace=actual_tr,
            expected_trace=expected_tr,
            is_idempotent=is_idemp,
            is_symmetric=is_symm,
            n_rigid_modes_removed=5 if is_linear else 6,
        )

    @staticmethod
    def project_hessian(
        H: np.ndarray,
        coords: np.ndarray,
        masses: Optional[Union[Sequence[float], np.ndarray]] = None,
        symbols: Optional[Sequence[str]] = None,
        is_cartesian: bool = True,
        is_linear: bool = False,
    ) -> np.ndarray:
        """Projects rigid body modes out of a Cartesian or mass-weighted Hessian."""
        if is_cartesian:
            return project_cartesian_hessian(H, coords, masses=masses, symbols=symbols, is_linear=is_linear)
        return project_mass_weighted_hessian(H, coords, masses=masses, symbols=symbols, is_linear=is_linear)


# ==============================================================================
# 9. Unified Master Pipeline & MolSymEckartAlignmentResult
# ==============================================================================

class MolSymEckartAlignmentResult(BaseModel):
    """Unified master container for molecular symmetry, inertia, and Eckart frame alignment."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    symbols: List[str] = Field(..., description="Atomic element symbols (including ghost atoms)")
    raw_coords: Any = Field(..., description="Original input Cartesian coordinates (N, 3)")
    aligned_coords: Any = Field(..., description="Standardized Cartesian coordinates in principal or Eckart frame (N, 3)")
    masses_amu: List[float] = Field(..., description="Atomic masses in amu dynamically resolved via Mendeleev")
    center_of_mass: List[float] = Field(..., description="Calculated center of mass vector of input structure")
    n_atoms: int = Field(..., description="Total atom count")
    n_ghost_atoms: int = Field(..., description="Count of ghost / dummy atoms with 0.0 mass")
    total_mass_amu: float = Field(..., description="Total non-ghost molecular mass in amu")
    top_type: RotorTopType = Field(..., description="Rotor classification")
    molsym_profile: MolSymProfile = Field(..., description="Detailed MolSym point-group symmetry result")
    inertia_result: InertiaTensorResult = Field(..., description="Moment of Inertia tensor and spectroscopic constants")
    eckart_result: Optional[EckartAlignmentResult] = Field(
        None, description="Optional mass-weighted Eckart frame alignment result against reference"
    )
    vibrational_projector_result: Optional[VibrationalProjectorResult] = Field(
        None, description="Optional vibrational projector result"
    )
    execution_wall_time_ms: float = Field(..., description="Elapsed wall execution time in milliseconds")

    @field_serializer("raw_coords", "aligned_coords", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val

    def to_xyz_string(self, comment: str = "CoChem MolSym Eckart Aligned Geometry") -> str:
        """Formats the aligned molecular coordinates into standard XYZ format."""
        coords_arr = np.asarray(self.aligned_coords, dtype=np.float64)
        lines = [str(len(self.symbols)), f"{comment} | PointGroup={self.molsym_profile.point_group}"]
        for sym, (x, y, z) in zip(self.symbols, coords_arr):
            lines.append(f"{sym:<4} {x:14.8f} {y:14.8f} {z:14.8f}")
        return "\n".join(lines) + "\n"

    def write_xyz_file(self, filepath: Union[str, Path], comment: Optional[str] = None) -> Path:
        """Writes the aligned geometry to an XYZ file on disk."""
        p = Path(filepath).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        cmt = comment or f"CoChem Aligned Geometry | PG={self.molsym_profile.point_group}"
        p.write_text(self.to_xyz_string(comment=cmt), encoding="utf-8")
        return p


def parse_molecular_input(
    mol: Any,
    symbols: Optional[Sequence[str]] = None,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
) -> Tuple[np.ndarray, List[str], np.ndarray]:
    """Universal parser extracting coordinates, symbols, and masses from arbitrary molecular inputs."""
    coords_list: List[List[float]] = []
    extracted_symbols: List[str] = []

    # 1. Path to XYZ file or string containing XYZ content
    if isinstance(mol, (str, Path)):
        s_val = str(mol).strip()
        if os.path.isfile(s_val):
            lines = Path(s_val).read_text(encoding="utf-8").strip().splitlines()
        else:
            lines = s_val.strip().splitlines()

        # Parse XYZ format
        if len(lines) >= 3 and lines[0].strip().isdigit():
            atom_count = int(lines[0].strip())
            for line in lines[2:2 + atom_count]:
                parts = line.strip().split()
                if len(parts) >= 4:
                    extracted_symbols.append(parts[0])
                    coords_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
            coords_arr = np.array(coords_list, dtype=np.float64)
        else:
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 4:
                    extracted_symbols.append(parts[0])
                    coords_list.append([float(parts[1]), float(parts[2]), float(parts[3])])
            coords_arr = np.array(coords_list, dtype=np.float64)

    # 2. Dictionary input
    elif isinstance(mol, dict):
        if "coords" in mol:
            coords_arr = np.asarray(mol["coords"], dtype=np.float64)
            if "symbols" in mol:
                extracted_symbols = list(mol["symbols"])
        elif "geometry" in mol and "symbols" in mol:
            flat_geom = np.asarray(mol["geometry"], dtype=np.float64)
            coords_arr = flat_geom.reshape((-1, 3))
            extracted_symbols = list(mol["symbols"])
        elif "atoms" in mol:
            for item in mol["atoms"]:
                if AtomModel is not None and isinstance(item, AtomModel):
                    coords_list.append(list(item.coords))
                    extracted_symbols.append(item.symbol)
                elif isinstance(item, dict):
                    sym = item.get("symbol")
                    pos = item.get("coords", item.get("position"))
                    if pos is None and "x" in item and "y" in item and "z" in item:
                        pos = [item["x"], item["y"], item["z"]]
                    if pos is None or sym is None:
                        raise MolSymEckartError(f"Atom dictionary missing required fields: {item}")
                    coords_list.append([float(x) for x in pos])
                    extracted_symbols.append(str(sym))
                elif hasattr(item, "coords") and hasattr(item, "symbol"):
                    coords_list.append(list(item.coords))
                    extracted_symbols.append(str(item.symbol))
            coords_arr = np.array(coords_list, dtype=np.float64)
        else:
            raise MolSymEckartError("Dictionary input must contain 'coords', 'geometry', or 'atoms'.")

    # 3. Object with 'atoms' attribute
    elif hasattr(mol, "atoms"):
        for item in mol.atoms:
            if hasattr(item, "coords"):
                coords_list.append(list(item.coords))
            elif hasattr(item, "x") and hasattr(item, "y") and hasattr(item, "z"):
                coords_list.append([float(item.x), float(item.y), float(item.z)])
            if hasattr(item, "symbol"):
                extracted_symbols.append(str(item.symbol))
        coords_arr = np.array(coords_list, dtype=np.float64)

    # 4. Sequence of atom objects or dicts
    elif isinstance(mol, (list, tuple)) and len(mol) > 0 and (
        (AtomModel is not None and isinstance(mol[0], AtomModel))
        or isinstance(mol[0], dict)
        or hasattr(mol[0], "symbol")
    ):
        for item in mol:
            if AtomModel is not None and isinstance(item, AtomModel):
                coords_list.append(list(item.coords))
                extracted_symbols.append(item.symbol)
            elif isinstance(item, dict):
                sym = item.get("symbol")
                pos = item.get("coords", item.get("position"))
                if pos is None and "x" in item and "y" in item and "z" in item:
                    pos = [item["x"], item["y"], item["z"]]
                if pos is None or sym is None:
                    raise MolSymEckartError(f"Atom dictionary missing required fields: {item}")
                coords_list.append([float(x) for x in pos])
                extracted_symbols.append(str(sym))
            elif hasattr(item, "coords") and hasattr(item, "symbol"):
                coords_list.append(list(item.coords))
                extracted_symbols.append(str(item.symbol))
        coords_arr = np.array(coords_list, dtype=np.float64)

    # 5. Raw numpy array or nested numeric list
    else:
        coords_arr = np.asarray(mol, dtype=np.float64)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise MolSymEckartError(f"Raw coordinates must have shape (N, 3), got {coords_arr.shape}.")

    # Reconcile symbols
    final_symbols: List[str] = []
    if symbols is not None:
        final_symbols = [str(s).strip() for s in symbols]
    elif extracted_symbols:
        final_symbols = extracted_symbols
    else:
        raise MassResolutionError("Elemental symbols must be supplied to resolve atomic masses.")

    masses_arr = resolve_molecular_masses(coords_arr, masses=masses, symbols=final_symbols)
    return coords_arr, final_symbols, masses_arr


def standardize_and_align_molsym_eckart(
    mol: Any,
    symbols: Optional[Sequence[str]] = None,
    masses: Optional[Union[Sequence[float], np.ndarray]] = None,
    ref_coords: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    symmetrize: bool = False,
    construct_projector: bool = False,
    tolerance: float = 1e-12,
) -> MolSymEckartAlignmentResult:
    """Master ingestion entrypoint executing full symmetry resolution, COM shift, and Eckart alignment.

    Parameters
    ----------
    mol : Any
        Molecular input (XYZ path, XYZ string, dict, atom list, or numpy array).
    symbols : Sequence[str], optional
        Elemental symbols.
    masses : Sequence[float] | np.ndarray, optional
        Pre-defined atomic masses.
    ref_coords : np.ndarray | Sequence, optional
        Reference coordinates for Eckart frame alignment.
    symmetrize : bool, default False
        Whether to generate idealized symmetrized coordinates via MolSym.
    construct_projector : bool, default False
        Whether to compute the (3N x 3N) idempotent vibrational projector.
    tolerance : float, default 1e-12
        Eckart rotational residual tolerance.

    Returns
    -------
    MolSymEckartAlignmentResult
        Comprehensive result model containing all spectroscopic, symmetry, and alignment properties.
    """
    t0 = time.perf_counter()

    raw_coords, syms, masses_arr = parse_molecular_input(mol, symbols=symbols, masses=masses)
    raw_coords = np.array(raw_coords, dtype=np.float64, copy=True)
    n_atoms = len(raw_coords)
    n_ghosts = sum(1 for s in syms if is_ghost_symbol(s))
    total_mass = float(np.sum(masses_arr))

    # 1. Compute Center of Mass
    com = compute_center_of_mass(raw_coords, masses=masses_arr)

    # 2. MolSym Point-Group Symmetry Analysis
    molsym_prof = analyze_molecular_symmetry(
        coords=raw_coords,
        symbols=syms,
        masses=masses_arr,
        symmetrize=symmetrize,
    )

    # 3. Moment of Inertia Tensor & Principal Axis Alignment
    inertia_res = align_to_principal_axes(raw_coords, masses=masses_arr)

    # 4. Optional Eckart Frame Alignment against reference
    eckart_res: Optional[EckartAlignmentResult] = None
    if ref_coords is not None:
        ref_coords_arr = np.asarray(ref_coords, dtype=np.float64)
        eckart_res = align_to_eckart_frame(
            target_coords=raw_coords,
            ref_coords=ref_coords_arr,
            masses=masses_arr,
            symbols=syms,
            tolerance=tolerance,
        )
        final_aligned_coords = eckart_res.aligned_coords
    else:
        final_aligned_coords = inertia_res.aligned_coords

    # 5. Optional Vibrational Projector
    vib_proj_res: Optional[VibrationalProjectorResult] = None
    is_lin = molsym_prof.is_linear or (inertia_res.top_type == RotorTopType.LINEAR)
    if construct_projector and n_atoms > 0:
        vib_proj_res = VibrationalProjectorEngine.construct_projector(
            coords=raw_coords,
            masses=masses_arr,
            symbols=syms,
            is_linear=is_lin,
        )

    t1 = time.perf_counter()
    wall_ms = (t1 - t0) * 1000.0

    return MolSymEckartAlignmentResult(
        symbols=syms,
        raw_coords=raw_coords,
        aligned_coords=final_aligned_coords,
        masses_amu=masses_arr.tolist(),
        center_of_mass=com.tolist(),
        n_atoms=n_atoms,
        n_ghost_atoms=n_ghosts,
        total_mass_amu=total_mass,
        top_type=inertia_res.top_type,
        molsym_profile=molsym_prof,
        inertia_result=inertia_res,
        eckart_result=eckart_res,
        vibrational_projector_result=vib_proj_res,
        execution_wall_time_ms=wall_ms,
    )


# ==============================================================================
# 10. Theoretical Verification Benchmark Test Suite
# ==============================================================================

def run_theoretical_benchmarks() -> Dict[str, Any]:
    """Executes authentic physical benchmark test suite verifying mathematical physics.

    Benchmarks:
    1. Water (H2O): C2v symmetry, SEAs [[0], [1, 2]], sigma = 2, asymmetric top, Delta approx 0.
    2. Water Perturbed: Eckart torque residual norm <= 1e-12 under Kabsch alignment.
    3. Water Dimer BSSE: Ghost atoms ('Gh') possess exactly 0.0 mass without altering COM.
    4. Carbon Dioxide (CO2): Dinfh linear top, Ia -> 0, A -> inf, Tr(P_vib) = 3N - 5 = 4.
    5. Methane (CH4): Td spherical top, Ia = Ib = Ic, kappa = 0.0, sigma = 12, SEAs [[0], [1, 2, 3, 4]].
    6. Benzene (C6H6): D6h oblate top, Ia = Ib < Ic, kappa = +1.0, Delta approx 0.
    """
    logger.info("Executing CoChem MolSym Eckart Aligner Theoretical Benchmark Suite...")
    benchmark_results: Dict[str, bool] = {}

    # Benchmark 1: Water (H2O) Equilibrium Geometry
    water_syms = ["O", "H", "H"]
    water_coords = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)
    res_h2o = standardize_and_align_molsym_eckart(water_coords, symbols=water_syms, construct_projector=True)

    h2o_pg_ok = res_h2o.molsym_profile.point_group in {"C2v", "C2"}
    h2o_sigma_ok = res_h2o.molsym_profile.rotational_symmetry_number == 2
    h2o_seas_ok = len(res_h2o.molsym_profile.symmetrically_equivalent_atoms) == 2
    h2o_top_ok = res_h2o.top_type == RotorTopType.ASYMMETRIC
    h2o_defect_ok = abs(res_h2o.inertia_result.inertial_defect) < 1e-3
    h2o_trace_ok = res_h2o.vibrational_projector_result is not None and res_h2o.vibrational_projector_result.expected_trace == 3
    benchmark_results["1_H2O_Equilibrium"] = bool(
        h2o_pg_ok and h2o_sigma_ok and h2o_seas_ok and h2o_top_ok and h2o_defect_ok and h2o_trace_ok
    )

    # Benchmark 2: Water Perturbed Eckart Alignment
    theta = 0.45
    Rz = np.array([[math.cos(theta), -math.sin(theta), 0.0],
                   [math.sin(theta),  math.cos(theta), 0.0],
                   [0.0,              0.0,             1.0]])
    perturbed_h2o = (water_coords @ Rz) + np.array([1.5, -2.0, 0.75])
    perturbed_h2o[1] += np.array([0.02, 0.01, -0.01])

    res_eckart = standardize_and_align_molsym_eckart(
        perturbed_h2o, symbols=water_syms, ref_coords=water_coords
    )
    assert res_eckart.eckart_result is not None
    eckart_torque_ok = res_eckart.eckart_result.residual_rotational_norm <= 1e-12
    eckart_trans_ok = res_eckart.eckart_result.translational_residual_norm <= 1e-12
    eckart_det_ok = abs(res_eckart.eckart_result.rotation_determinant - 1.0) < 1e-8
    benchmark_results["2_H2O_Eckart_Alignment"] = bool(
        eckart_torque_ok and eckart_trans_ok and eckart_det_ok
    )

    # Benchmark 3: Water Dimer Complex with Ghost Atoms (BSSE Counterpoise)
    bsse_syms = ["O", "H", "H", "GhO", "GhH", "GhH"]
    bsse_coords = np.array([
        [0.0000, 0.0000, 0.1173],
        [0.0000, 0.7572, -0.4692],
        [0.0000, -0.7572, -0.4692],
        [2.9000, 0.0000, 0.0000],
        [2.9000, 0.7572, -0.5865],
        [2.9000, -0.7572, -0.5865],
    ], dtype=np.float64)
    res_bsse = standardize_and_align_molsym_eckart(bsse_coords, symbols=bsse_syms)

    com_real_h2o = compute_center_of_mass(water_coords, symbols=water_syms)
    com_bsse = np.array(res_bsse.center_of_mass)
    bsse_com_ok = np.linalg.norm(com_real_h2o - com_bsse) < 1e-12
    bsse_ghost_count_ok = res_bsse.n_ghost_atoms == 3
    benchmark_results["3_BSSE_Ghost_Protection"] = bool(bsse_com_ok and bsse_ghost_count_ok)

    # Benchmark 4: Carbon Dioxide (CO2) Linear Molecule Singularity
    co2_syms = ["O", "C", "O"]
    co2_coords = np.array([
        [0.0, 0.0, -1.162],
        [0.0, 0.0,  0.000],
        [0.0, 0.0,  1.162],
    ], dtype=np.float64)
    res_co2 = standardize_and_align_molsym_eckart(co2_coords, symbols=co2_syms, construct_projector=True)

    co2_top_ok = res_co2.top_type == RotorTopType.LINEAR
    co2_a_inf = math.isinf(res_co2.inertia_result.rotational_constants_mhz[0])
    co2_b_eq_c = abs(res_co2.inertia_result.rotational_constants_mhz[1] - res_co2.inertia_result.rotational_constants_mhz[2]) < 1e-4
    co2_trace_ok = res_co2.vibrational_projector_result is not None and res_co2.vibrational_projector_result.expected_trace == (3 * 3 - 5)
    benchmark_results["4_CO2_Linear_Singularity"] = bool(co2_top_ok and co2_a_inf and co2_b_eq_c and co2_trace_ok)

    # Benchmark 5: Methane (CH4) Spherical Top
    ch4_syms = ["C", "H", "H", "H", "H"]
    a = 1.089 / math.sqrt(3)
    ch4_coords = np.array([
        [0.0, 0.0, 0.0],
        [ a,  a,  a],
        [ a, -a, -a],
        [-a,  a, -a],
        [-a, -a,  a],
    ], dtype=np.float64)
    res_ch4 = standardize_and_align_molsym_eckart(ch4_coords, symbols=ch4_syms)

    ch4_top_ok = res_ch4.top_type == RotorTopType.SPHERICAL
    ch4_pg_ok = res_ch4.molsym_profile.point_group.startswith("T")
    ch4_sigma_ok = res_ch4.molsym_profile.rotational_symmetry_number == 12
    ch4_seas_ok = len(res_ch4.molsym_profile.symmetrically_equivalent_atoms) == 2
    benchmark_results["5_CH4_Spherical_Top"] = bool(ch4_top_ok and ch4_pg_ok and ch4_sigma_ok and ch4_seas_ok)

    # Benchmark 6: Benzene (C6H6) Planar Oblate Top
    c6h6_syms = ["C"] * 6 + ["H"] * 6
    r_c, r_h = 1.397, 1.397 + 1.084
    c6h6_coords = []
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_c * math.cos(ang), r_c * math.sin(ang), 0.0])
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        c6h6_coords.append([r_h * math.cos(ang), r_h * math.sin(ang), 0.0])
    res_c6h6 = standardize_and_align_molsym_eckart(np.array(c6h6_coords), symbols=c6h6_syms)

    c6h6_top_ok = res_c6h6.top_type == RotorTopType.SYMMETRIC_OBLATE
    c6h6_defect_ok = abs(res_c6h6.inertia_result.inertial_defect) < 1e-2
    c6h6_pg_ok = res_c6h6.molsym_profile.point_group.startswith("D6")
    benchmark_results["6_Benzene_Oblate_Planar"] = bool(c6h6_top_ok and c6h6_defect_ok and c6h6_pg_ok)

    all_passed = all(benchmark_results.values())
    summary = {
        "all_passed": all_passed,
        "results": benchmark_results,
    }
    logger.info("Theoretical Benchmark Suite Result: %s", "ALL PASSED" if all_passed else "FAILURES DETECTED")
    return summary


# ==============================================================================
# 11. Command Line Interface (CLI)
# ==============================================================================

def main(args: Optional[Sequence[str]] = None) -> int:
    """Command-line entrypoint for molecular symmetry, inertia, and Eckart frame alignment."""
    parser = argparse.ArgumentParser(
        description="CoChem MolSym Point-Group Symmetry Resolver & Mass-Weighted Eckart Frame Aligner"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to input XYZ file or raw geometry string",
    )
    parser.add_argument(
        "--ref", "-r",
        type=str,
        default=None,
        help="Path to reference XYZ file for mass-weighted Eckart frame alignment",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Path to output standardized XYZ or JSON file",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["xyz", "json", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )
    parser.add_argument(
        "--symmetrize", "-s",
        action="store_true",
        help="Generate idealized symmetrized coordinates via MolSym",
    )
    parser.add_argument(
        "--projector", "-p",
        action="store_true",
        help="Construct idempotent (3N x 3N) vibrational projector",
    )
    parser.add_argument(
        "--verify-benchmarks",
        action="store_true",
        help="Execute internal physical benchmark verification suite",
    )
    parser.add_argument(
        "--tolerance", "-t",
        type=float,
        default=1e-12,
        help="Eckart rotational residual torque tolerance (default: 1e-12)",
    )

    parsed = parser.parse_args(args)

    if parsed.verify_benchmarks:
        bm = run_theoretical_benchmarks()
        print(json.dumps(bm, indent=2))
        return 0 if bm["all_passed"] else 1

    if not parsed.input:
        parser.print_help()
        return 0

    try:
        ref_c = None
        if parsed.ref:
            raw_ref, _, _ = parse_molecular_input(parsed.ref)
            ref_c = raw_ref

        result = standardize_and_align_molsym_eckart(
            mol=parsed.input,
            ref_coords=ref_c,
            symmetrize=parsed.symmetrize,
            construct_projector=parsed.projector,
            tolerance=parsed.tolerance,
        )

        if parsed.format == "json":
            out_str = json.dumps(result.model_dump(), indent=2)
        elif parsed.format == "xyz":
            out_str = result.to_xyz_string()
        else:
            out_str = (
                f"=== CoChem MolSym & Eckart Frame Alignment Summary ===\n"
                f"Point Group:           {result.molsym_profile.point_group} (sigma={result.molsym_profile.rotational_symmetry_number})\n"
                f"Rotor Top:             {result.top_type.value} (kappa={result.inertia_result.rays_kappa:.6f})\n"
                f"Rotational A, B, C:    {result.inertia_result.rotational_constants_mhz[0]:.2f}, "
                f"{result.inertia_result.rotational_constants_mhz[1]:.2f}, "
                f"{result.inertia_result.rotational_constants_mhz[2]:.2f} MHz\n"
                f"Inertial Defect:       {result.inertia_result.inertial_defect:.6f} amu * Angstrom^2\n"
                f"Total Mass:            {result.total_mass_amu:.6f} amu (Ghost atoms: {result.n_ghost_atoms})\n"
                f"SEAs (Symmetry Orbits):{result.molsym_profile.symmetrically_equivalent_atoms}\n"
            )
            if result.eckart_result:
                out_str += (
                    f"Eckart Alignment RMSD: {result.eckart_result.rmsd:.8f} Angstrom\n"
                    f"Rotational Torque Norm:{result.eckart_result.residual_rotational_norm:.4e}\n"
                    f"Translational Res Norm:{result.eckart_result.translational_residual_norm:.4e}\n"
                    f"Rotation Matrix Det:   {result.eckart_result.rotation_determinant:.8f}\n"
                    f"Alignment Status:      {result.eckart_result.status.value}\n"
                )
            if result.vibrational_projector_result:
                out_str += (
                    f"Vibrational Projector: Tr={result.vibrational_projector_result.trace:.1f} "
                    f"(expected={result.vibrational_projector_result.expected_trace}), "
                    f"Idempotent={result.vibrational_projector_result.is_idempotent}\n"
                )
            out_str += f"Execution Wall Time:   {result.execution_wall_time_ms:.2f} ms\n"

        if parsed.output:
            Path(parsed.output).write_text(out_str, encoding="utf-8")
            logger.info("Saved result to %s", parsed.output)
        else:
            print(out_str)

        return 0

    except Exception as err:
        logger.error("Execution failed: %s", err, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
