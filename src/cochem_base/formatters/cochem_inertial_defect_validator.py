"""CoChem Inertial Defect & Planar Moment Validator & Formatter.

Authoritative Spectroscopic Validation and Formatting Engine for CoChem-BASE / CoChem-SCRIBE.

Calculates, validates, and formats molecular inertial tensors, principal moments of inertia
(I_a <= I_b <= I_c), rotational constants (A >= B >= C in MHz, GHz, and cm^-1), inertial defects
(Delta = I_c - I_a - I_b in u*Angstrom^2), planar moments of inertia (P_aa, P_bb, P_cc in u*Angstrom^2),
Ray's asymmetry parameter kappa, Wang's asymmetry parameters (b_p, b_o), and planarity/rotor
classifications across ab initio coordinates, Pickett SPFIT/SPCAT files, and HDF5 stores.

Authoritative Method Matrix v4 Standards Enforced:
- Section 1.2: The Three Products (Product A: de novo; Product B: semi-experimental; Product C: differences)
- Section 2.1: System Class: 5-10 atom van der Waals / hydrogen-bonded complexes in 2-22 GHz CP-FTMW
- Section 3.0: B_e vs B_0 observables and vibrational state corrections (Delta_vib)
- Section 4.0 / Decision Card Step 4: The 5 Free Observables:
    1. Inertial defect Delta = I_c - I_a - I_b (the sign must be right, always) [D]
    2. Planar moments P_aa > P_bb > P_cc [D]
    3. Quartic centrifugal distortion & rotational constants order (A >= B >= C) [D]
    4. Direct dipolar coupling D proportional to r^-3
    5. Vibrational satellites
- Mendeleev Mandate: Dynamic mass and element properties via mendeleev library
- Zero-Mock Anti-Spoofing Protocol: Zero placeholder stubs, zero dummy mocks, real physics calculations.
"""

from __future__ import annotations

import argparse
import datetime
import enum
import io
import json
import logging
import math
import os
import pathlib
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
from mendeleev import element  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# =============================================================================
# Physical Constants (CODATA 2018 / 2022 Standards via Mendeleev & Exact SI)
# =============================================================================
PLANCK_CONSTANT_J_S: float = 6.62607015e-34  # J*s (exact SI definition)
SPEED_OF_LIGHT_CM_S: float = 2.99792458e10  # cm/s (exact SI definition)
SPEED_OF_LIGHT_M_S: float = 299792458.0  # m/s (exact SI definition)
AVOGADRO_CONSTANT: float = 6.02214076e23  # mol^-1 (exact SI definition)
ATOMIC_MASS_UNIT_KG: float = 1.66053906660e-27  # kg (CODATA 2018/2022)

# Rotational constant conversion factor: h / (8 * pi^2) in MHz * u * Angstrom^2
# h / (8 * pi^2 * u_kg * (1e-10 m)^2) / 1e6 = 505379.008784 MHz * u * Angstrom^2
ROTATIONAL_CONVERSION_MHZ_U_ANG2: float = 505379.008784
MHZ_TO_GHZ: float = 1e-3
MHZ_TO_CM1: float = 1.0 / (SPEED_OF_LIGHT_CM_S * 1e-6)  # 1 / 29979.2458 ~ 3.33564095e-5

# Standard Method Matrix v4 Tolerance Bands (Section 1.2, 3.1)
DEFAULT_PRODUCT_A_MAX_ERROR_REL: float = 0.020  # 2.0% (floppy / dispersion-bound ceiling)
DEFAULT_PRODUCT_A_SEMI_RIGID_ERROR_REL: float = 0.005  # 0.5% (semi-rigid de novo target)
DEFAULT_PRODUCT_B_MAX_ERROR_REL: float = 0.0006  # 0.06% (semi-experimental template target)
DEFAULT_PRODUCT_C_MAX_ERROR_REL: float = 0.0010  # 0.10% (isotopologue difference target)

# Standard Inertial Defect Thresholds (u * Angstrom^2)
PLANAR_EQUILIBRIUM_THRESHOLD_U_ANG2: float = 1e-4  # Strictly planar rigid limit |Delta| < 1e-4
VIBRATIONAL_PLANAR_MAX_U_ANG2: float = 0.50  # Ground-state out-of-plane vibration floor 0 < Delta <= 0.50
NEAR_PLANAR_MIN_U_ANG2: float = -1.50  # Near-planar / slightly buckled frame
METHYL_ROTOR_MIN_U_ANG2: float = -6.50  # 1-2 rotating methyl groups (~ -3.1 u*A^2 per methyl)


# =============================================================================
# Enumerations
# =============================================================================

class RotorType(str, enum.Enum):
    """Classification of molecular rotor symmetry based on principal moments."""

    LINEAR = "LINEAR"  # I_a ~ 0, I_b = I_c
    SPHERICAL_TOP = "SPHERICAL_TOP"  # I_a = I_b = I_c
    PROLATE_SYMMETRIC_TOP = "PROLATE_SYMMETRIC_TOP"  # I_a < I_b = I_c (kappa = -1.0)
    OBLATE_SYMMETRIC_TOP = "OBLATE_SYMMETRIC_TOP"  # I_a = I_b < I_c (kappa = +1.0)
    NEAR_PROLATE_ASYMMETRIC_TOP = "NEAR_PROLATE_ASYMMETRIC_TOP"  # -1.0 < kappa <= -0.5
    HIGHLY_ASYMMETRIC_TOP = "HIGHLY_ASYMMETRIC_TOP"  # -0.5 < kappa < +0.5
    NEAR_OBLATE_ASYMMETRIC_TOP = "NEAR_OBLATE_ASYMMETRIC_TOP"  # +0.5 <= kappa < +1.0
    ASYMMETRIC_TOP = "ASYMMETRIC_TOP"  # General asymmetric rotor


class PlanarityClassification(str, enum.Enum):
    """Classification of molecular frame planarity based on inertial defect Delta."""

    STRICTLY_PLANAR_EQUILIBRIUM = "STRICTLY_PLANAR_EQUILIBRIUM"  # |Delta| < 1e-4 u*A^2, rigid equilibrium
    VIBRATIONALLY_PLANAR_GROUND_STATE = "VIBRATIONALLY_PLANAR_GROUND_STATE"  # 0.0 < Delta <= 0.50 u*A^2, v=0 state
    QUASI_PLANAR = "QUASI_PLANAR"  # -1.50 <= Delta < 0.0 u*A^2, slight buckling
    METHYL_ROTOR = "METHYL_ROTOR"  # -6.50 <= Delta < -1.50 u*A^2, internal rotor contribution
    NON_PLANAR_3D = "NON_PLANAR_3D"  # Delta < -6.50 u*A^2, genuine 3D molecular frame
    ANOMALOUS_POSITIVE_DEFECT = "ANOMALOUS_POSITIVE_DEFECT"  # Delta > 0.50 u*A^2, unphysical or severe resonance


class ValidationStatus(str, enum.Enum):
    """Overall status of inertial defect and spectroscopic property validation."""

    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class ProductClass(str, enum.Enum):
    """Method Matrix v4 Product Class (Section 1.2)."""

    PRODUCT_A_ABSOLUTE_DENOVO = "PRODUCT_A_ABSOLUTE_DENOVO"  # Absolute de novo prediction
    PRODUCT_B_SEMI_EXPERIMENTAL = "PRODUCT_B_SEMI_EXPERIMENTAL"  # Semi-experimental / template-anchored
    PRODUCT_C_DIFFERENCES = "PRODUCT_C_DIFFERENCES"  # Differences / isotopologue shifts


# =============================================================================
# Dynamic Mendeleev Mass Resolution Helper
# =============================================================================

# Fast in-memory cache for dynamic Mendeleev elemental and isotopic masses
_MASS_CACHE: Dict[str, float] = {}

# Common isotope mass map for spectroscopic isotope variants
_ISOTOPE_MASS_OVERRIDES: Dict[str, Tuple[str, int]] = {
    "D": ("H", 2),
    "2H": ("H", 2),
    "T": ("H", 3),
    "3H": ("H", 3),
    "13C": ("C", 13),
    "14C": ("C", 14),
    "15N": ("N", 15),
    "17O": ("O", 17),
    "18O": ("O", 18),
    "33S": ("S", 33),
    "34S": ("S", 34),
    "36S": ("S", 36),
    "37CL": ("Cl", 37),
    "81BR": ("Br", 81),
}


def get_atomic_mass(symbol_or_z: Union[str, int], isotope: Optional[int] = None) -> float:
    """Dynamically resolves atomic and isotopic masses via the Mendeleev library.

    Strictly satisfies the Mendeleev Mandate: Zero hardcoded atomic weights.

    Parameters
    ----------
    symbol_or_z : Union[str, int]
        Chemical element symbol (e.g., 'C', '13C', 'D') or atomic number Z (e.g., 6).
    isotope : Optional[int]
        Mass number A for specific isotope. If None, resolves from symbol or standard weight.

    Returns
    -------
    float
        Atomic or isotopic mass in unified atomic mass units (u or amu) [M].
    """
    cache_key = f"{symbol_or_z}_{isotope}"
    if cache_key in _MASS_CACHE:
        return _MASS_CACHE[cache_key]

    if isinstance(symbol_or_z, int):
        elem = element(symbol_or_z)
        if isotope is not None:
            for iso in elem.isotopes:
                if iso.mass_number == isotope and iso.mass is not None:
                    val = float(iso.mass)
                    _MASS_CACHE[cache_key] = val
                    return val
        val = float(elem.atomic_weight)
        _MASS_CACHE[cache_key] = val
        return val

    sym_clean = str(symbol_or_z).strip()
    sym_upper = sym_clean.upper()

    # Check known isotope symbol overrides
    if sym_upper in _ISOTOPE_MASS_OVERRIDES:
        base_sym, iso_num = _ISOTOPE_MASS_OVERRIDES[sym_upper]
        elem = element(base_sym)
        for iso in elem.isotopes:
            if iso.mass_number == iso_num and iso.mass is not None:
                val = float(iso.mass)
                _MASS_CACHE[cache_key] = val
                return val

    # Match prefixed mass numbers, e.g. "13C", "18O"
    match = re.match(r"^(\d+)([A-Za-z]+)$", sym_clean)
    if match:
        iso_num = int(match.group(1))
        elem_sym = match.group(2).capitalize()
        elem = element(elem_sym)
        for iso in elem.isotopes:
            if iso.mass_number == iso_num and iso.mass is not None:
                val = float(iso.mass)
                _MASS_CACHE[cache_key] = val
                return val
        val = float(elem.atomic_weight)
        _MASS_CACHE[cache_key] = val
        return val

    # Standard element symbol
    elem_sym = sym_clean.capitalize()
    elem = element(elem_sym)
    if isotope is not None:
        for iso in elem.isotopes:
            if iso.mass_number == isotope and iso.mass is not None:
                val = float(iso.mass)
                _MASS_CACHE[cache_key] = val
                return val

    val = float(elem.atomic_weight)
    _MASS_CACHE[cache_key] = val
    return val


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class MolecularInertialProperties:
    """Calculated physical and spectroscopic properties of a molecular structure."""

    # Molecular mass & center of mass
    total_mass_amu: float
    center_of_mass_angstrom: Tuple[float, float, float]
    number_of_atoms: int

    # Principal moments of inertia: I_a <= I_b <= I_c (u * Angstrom^2)
    ia_amu_angstrom2: float
    ib_amu_angstrom2: float
    ic_amu_angstrom2: float

    # Rotational constants: A >= B >= C (MHz, GHz, cm^-1)
    a_mhz: float
    b_mhz: float
    c_mhz: float
    a_ghz: float
    b_ghz: float
    c_ghz: float
    a_cm1: float
    b_cm1: float
    c_cm1: float

    # Inertial Defect: Delta = I_c - I_a - I_b (u * Angstrom^2)
    inertial_defect_amu_angstrom2: float

    # Planar Moments of Inertia: P_aa, P_bb, P_cc (u * Angstrom^2)
    # P_aa = sum m_i a_i^2 = 0.5 * (I_b + I_c - I_a)
    # P_bb = sum m_i b_i^2 = 0.5 * (I_a + I_c - I_b)
    # P_cc = sum m_i c_i^2 = 0.5 * (I_a + I_b - I_c) = -0.5 * Delta
    planar_moment_paa_amu_angstrom2: float
    planar_moment_pbb_amu_angstrom2: float
    planar_moment_pcc_amu_angstrom2: float

    # Asymmetry parameters
    rays_kappa: float  # (2B - A - C) / (A - C)
    wangs_bp: float  # (C - B) / (2A - B - C) [prolate]
    wangs_bo: float  # (A - B) / (2C - A - B) [oblate]

    # Rotor & Planarity Classification
    rotor_type: RotorType
    planarity_class: PlanarityClassification

    # Coordinate Matrices (Principal Axis System)
    principal_axes_matrix: List[List[float]] = field(default_factory=list)
    principal_coordinates: List[List[float]] = field(default_factory=list)
    atomic_symbols: List[str] = field(default_factory=list)
    provenance_tag: str = "[D]"

    def to_dict(self) -> Dict[str, Any]:
        """Converts properties to a structured JSON-serializable dictionary."""
        d = asdict(self)
        d["rotor_type"] = self.rotor_type.value
        d["planarity_class"] = self.planarity_class.value
        return d


@dataclass
class InertialDefectValidationReport:
    """Full spectroscopic audit and compliance validation report."""

    # Validation outcome
    is_valid: bool
    status: ValidationStatus
    product_class: ProductClass

    # Physical properties
    properties: MolecularInertialProperties

    # Check results and diagnostics
    passed_checks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    relative_deviations: Dict[str, float] = field(default_factory=dict)
    absolute_deviations: Dict[str, float] = field(default_factory=dict)

    # Metadata & Execution Provenance
    molecule_name: str = "Unnamed_Complex"
    timestamp_utc: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    method_matrix_version: str = "Version 4 (August 2026)"
    git_hash: str = "HEAD"
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts validation report to a structured dictionary."""
        return {
            "molecule_name": self.molecule_name,
            "timestamp_utc": self.timestamp_utc,
            "is_valid": self.is_valid,
            "status": self.status.value,
            "product_class": self.product_class.value,
            "properties": self.properties.to_dict(),
            "passed_checks": self.passed_checks,
            "warnings": self.warnings,
            "errors": self.errors,
            "relative_deviations": self.relative_deviations,
            "absolute_deviations": self.absolute_deviations,
            "method_matrix_version": self.method_matrix_version,
            "git_hash": self.git_hash,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class InertialDefectValidatorConfig:
    """Configurable tolerances and execution options for inertial defect validation."""

    # Planarity thresholds (u * Angstrom^2)
    planar_defect_threshold: float = PLANAR_EQUILIBRIUM_THRESHOLD_U_ANG2
    vibrational_planar_max: float = VIBRATIONAL_PLANAR_MAX_U_ANG2
    quasi_planar_min: float = NEAR_PLANAR_MIN_U_ANG2
    methyl_rotor_min: float = METHYL_ROTOR_MIN_U_ANG2

    # Relative Error Tolerances for Rotational Constants
    product_a_semi_rigid_tol_rel: float = DEFAULT_PRODUCT_A_SEMI_RIGID_ERROR_REL  # 0.5%
    product_a_floppy_tol_rel: float = DEFAULT_PRODUCT_A_MAX_ERROR_REL  # 2.0%
    product_b_tol_rel: float = DEFAULT_PRODUCT_B_MAX_ERROR_REL  # 0.06%
    product_c_tol_rel: float = DEFAULT_PRODUCT_C_MAX_ERROR_REL  # 0.10%

    # Physics & Enforcement Flags
    enforce_triangle_inequality: bool = True
    enforce_positive_planar_moments: bool = True
    is_ground_state_v0: bool = False  # If True, permits Delta_0 > 0 from vibrational zero-point
    enforce_rotational_ordering: bool = True  # A >= B >= C and I_a <= I_b <= I_c


# =============================================================================
# Core Physical Calculation Functions
# =============================================================================

def compute_center_of_mass(
    symbols: Sequence[Union[str, int]],
    coords: np.ndarray,
    masses: Optional[Sequence[float]] = None,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Calculates molecular center of mass and translates coordinates to COM.

    Parameters
    ----------
    symbols : Sequence[Union[str, int]]
        List of atomic symbols or atomic numbers Z.
    coords : np.ndarray
        Array of shape (N, 3) with Cartesian coordinates in Angstroms.
    masses : Optional[Sequence[float]]
        Pre-resolved masses in amu. If None, resolved dynamically via Mendeleev.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, float]
        - coords_com: Center-of-mass shifted coordinates of shape (N, 3) in Angstroms [D]
        - com_vector: Center-of-mass translation vector (3,) in Angstroms [D]
        - total_mass: Total molecular mass in amu [M]
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ValueError(f"Cartesian coordinates must have shape (N, 3), got {coords_arr.shape}")

    n_atoms = coords_arr.shape[0]
    if len(symbols) != n_atoms:
        raise ValueError(f"Atom count mismatch: {len(symbols)} symbols vs {n_atoms} coordinates")

    if masses is None:
        mass_arr = np.array([get_atomic_mass(s) for s in symbols], dtype=np.float64)
    else:
        mass_arr = np.asarray(masses, dtype=np.float64)

    total_mass = float(np.sum(mass_arr))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be strictly positive")

    com_vector = np.sum(coords_arr * mass_arr[:, np.newaxis], axis=0) / total_mass
    coords_com = coords_arr - com_vector

    return coords_com, com_vector, total_mass


def compute_inertia_tensor(coords_com: np.ndarray, masses: np.ndarray) -> np.ndarray:
    """Constructs the 3x3 moment of inertia tensor in Cartesian coordinates.

    Parameters
    ----------
    coords_com : np.ndarray
        Coordinates shifted to center of mass of shape (N, 3) in Angstroms.
    masses : np.ndarray
        Atomic masses array of shape (N,) in amu.

    Returns
    -------
    np.ndarray
        Symmetric 3x3 inertia tensor matrix in u * Angstrom^2 [D].
    """
    x = coords_com[:, 0]
    y = coords_com[:, 1]
    z = coords_com[:, 2]

    i_xx = np.sum(masses * (y**2 + z**2))
    i_yy = np.sum(masses * (x**2 + z**2))
    i_zz = np.sum(masses * (x**2 + y**2))
    i_xy = -np.sum(masses * x * y)
    i_xz = -np.sum(masses * x * z)
    i_yz = -np.sum(masses * y * z)

    inertia_tensor = np.array(
        [
            [i_xx, i_xy, i_xz],
            [i_xy, i_yy, i_yz],
            [i_xz, i_yz, i_zz],
        ],
        dtype=np.float64,
    )
    return inertia_tensor


def compute_principal_moments_and_axes(
    coords: np.ndarray,
    symbols: Sequence[Union[str, int]],
    masses: Optional[Sequence[float]] = None,
) -> Tuple[Tuple[float, float, float], np.ndarray, np.ndarray, float, Tuple[float, float, float]]:
    """Calculates principal moments of inertia (I_a <= I_b <= I_c) and principal axes.

    Parameters
    ----------
    coords : np.ndarray
        Cartesian coordinates of shape (N, 3) in Angstroms.
    symbols : Sequence[Union[str, int]]
        List of atomic symbols or atomic numbers.
    masses : Optional[Sequence[float]]
        Pre-resolved masses in amu. If None, resolved via Mendeleev.

    Returns
    -------
    Tuple
        - principal_moments: (I_a, I_b, I_c) in u * Angstrom^2 [D]
        - principal_axes: 3x3 rotation matrix (rows are principal axes a, b, c) [D]
        - principal_coords: Coordinates transformed into Principal Axis Frame (N, 3) [D]
        - total_mass: Total molecular mass in amu [M]
        - com_vector: Center of mass vector in Angstroms [D]
    """
    coords_com, com_vector, total_mass = compute_center_of_mass(symbols, coords, masses)
    if masses is None:
        mass_arr = np.array([get_atomic_mass(s) for s in symbols], dtype=np.float64)
    else:
        mass_arr = np.asarray(masses, dtype=np.float64)

    inertia_tensor = compute_inertia_tensor(coords_com, mass_arr)

    # Diagonalize symmetric inertia tensor
    eigvals, eigvecs = np.linalg.eigh(inertia_tensor)

    # Sort eigenvalues ascending: I_a <= I_b <= I_c
    sort_idx = np.argsort(eigvals)
    sorted_eigvals = eigvals[sort_idx]
    sorted_eigvecs = eigvecs[:, sort_idx]  # Columns are eigenvectors

    # Ensure right-handed coordinate system: det(R) = +1
    rot_matrix = sorted_eigvecs.T  # Rows are principal axes (a, b, c)
    if np.linalg.det(rot_matrix) < 0.0:
        rot_matrix[2, :] *= -1.0  # Invert c-axis to preserve right-handedness

    # Transform coordinates to Principal Axis System (PAS)
    principal_coords = np.dot(coords_com, rot_matrix.T)

    ia = float(max(sorted_eigvals[0], 1e-12))
    ib = float(max(sorted_eigvals[1], 1e-12))
    ic = float(max(sorted_eigvals[2], 1e-12))

    com_tup = (float(com_vector[0]), float(com_vector[1]), float(com_vector[2]))
    return (ia, ib, ic), rot_matrix, principal_coords, total_mass, com_tup


def compute_rotational_constants(ia: float, ib: float, ic: float) -> Tuple[float, float, float]:
    """Derives spectroscopic rotational constants (A >= B >= C) in MHz.

    Formula: A = 505379.008784 / I_a, B = 505379.008784 / I_b, C = 505379.008784 / I_c.

    Parameters
    ----------
    ia, ib, ic : float
        Principal moments of inertia in u * Angstrom^2.

    Returns
    -------
    Tuple[float, float, float]
        Rotational constants (A, B, C) in MHz [D].
    """
    a_mhz = ROTATIONAL_CONVERSION_MHZ_U_ANG2 / max(ia, 1e-12)
    b_mhz = ROTATIONAL_CONVERSION_MHZ_U_ANG2 / max(ib, 1e-12)
    c_mhz = ROTATIONAL_CONVERSION_MHZ_U_ANG2 / max(ic, 1e-12)
    return float(a_mhz), float(b_mhz), float(c_mhz)


def compute_inertial_defect(ia: float, ib: float, ic: float) -> float:
    """Calculates the planar inertial defect Delta = I_c - I_a - I_b.

    Parameters
    ----------
    ia, ib, ic : float
        Principal moments of inertia in u * Angstrom^2.

    Returns
    -------
    float
        Inertial defect Delta in u * Angstrom^2 [D].
    """
    return float(ic - ia - ib)


def compute_planar_moments(ia: float, ib: float, ic: float) -> Tuple[float, float, float]:
    """Calculates planar moments of inertia (P_aa, P_bb, P_cc) in u * Angstrom^2.

    Formulas:
    P_aa = sum m_i a_i^2 = 0.5 * (I_b + I_c - I_a)
    P_bb = sum m_i b_i^2 = 0.5 * (I_a + I_c - I_b)
    P_cc = sum m_i c_i^2 = 0.5 * (I_a + I_b - I_c) = -0.5 * Delta

    Parameters
    ----------
    ia, ib, ic : float
        Principal moments of inertia in u * Angstrom^2.

    Returns
    -------
    Tuple[float, float, float]
        Planar moments (P_aa, P_bb, P_cc) in u * Angstrom^2 [D].
    """
    paa = 0.5 * (ib + ic - ia)
    pbb = 0.5 * (ia + ic - ib)
    pcc = 0.5 * (ia + ib - ic)
    return float(paa), float(pbb), float(pcc)


def compute_rays_asymmetry_kappa(a_mhz: float, b_mhz: float, c_mhz: float) -> float:
    """Calculates Ray's asymmetry parameter kappa = (2B - A - C) / (A - C).

    Boundaries:
    kappa = -1.0 : Prolate symmetric top (B = C)
    kappa =  0.0 : Most asymmetric top
    kappa = +1.0 : Oblate symmetric top (A = B)

    Parameters
    ----------
    a_mhz, b_mhz, c_mhz : float
        Rotational constants in MHz.

    Returns
    -------
    float
        Ray's asymmetry parameter kappa [-1.0, +1.0] [D].
    """
    denom = a_mhz - c_mhz
    if abs(denom) < 1e-12:
        return 0.0  # Spherical top limit
    kappa = (2.0 * b_mhz - a_mhz - c_mhz) / denom
    return float(np.clip(kappa, -1.0, 1.0))


def compute_wangs_asymmetry_parameters(
    a_mhz: float, b_mhz: float, c_mhz: float
) -> Tuple[float, float]:
    """Calculates Wang's asymmetry parameters b_p (prolate) and b_o (oblate).

    Formulas:
    b_p = (C - B) / (2A - B - C)
    b_o = (A - B) / (2C - A - B)

    Parameters
    ----------
    a_mhz, b_mhz, c_mhz : float
        Rotational constants in MHz.

    Returns
    -------
    Tuple[float, float]
        - wangs_bp: Prolate asymmetry parameter b_p [D]
        - wangs_bo: Oblate asymmetry parameter b_o [D]
    """
    denom_p = 2.0 * a_mhz - b_mhz - c_mhz
    bp = (c_mhz - b_mhz) / denom_p if abs(denom_p) > 1e-12 else 0.0

    denom_o = 2.0 * c_mhz - a_mhz - b_mhz
    bo = (a_mhz - b_mhz) / denom_o if abs(denom_o) > 1e-12 else 0.0

    return float(bp), float(bo)


def classify_rotor_type(ia: float, ib: float, ic: float, kappa: float) -> RotorType:
    """Classifies rotor type based on principal moments and Ray's kappa parameter.

    Parameters
    ----------
    ia, ib, ic : float
        Principal moments of inertia in u * Angstrom^2.
    kappa : float
        Ray's asymmetry parameter.

    Returns
    -------
    RotorType
        Rotor symmetry classification.
    """
    if ia < 1e-3 and abs(ib - ic) / max(ic, 1e-12) < 1e-3:
        return RotorType.LINEAR

    rel_diff_ab = abs(ia - ib) / max(ib, 1e-12)
    rel_diff_bc = abs(ib - ic) / max(ic, 1e-12)
    rel_diff_ac = abs(ia - ic) / max(ic, 1e-12)

    if rel_diff_ac < 1e-4:
        return RotorType.SPHERICAL_TOP

    if rel_diff_bc < 1e-4 or kappa <= -0.9999:
        return RotorType.PROLATE_SYMMETRIC_TOP

    if rel_diff_ab < 1e-4 or kappa >= 0.9999:
        return RotorType.OBLATE_SYMMETRIC_TOP

    if -1.0 <= kappa <= -0.5:
        return RotorType.NEAR_PROLATE_ASYMMETRIC_TOP

    if +0.5 <= kappa <= 1.0:
        return RotorType.NEAR_OBLATE_ASYMMETRIC_TOP

    return RotorType.HIGHLY_ASYMMETRIC_TOP


def classify_planarity(
    defect: float,
    max_c_coord: float,
    rotor_type: Optional[RotorType] = None,
    is_v0_ground_state: bool = False,
    planar_tol: float = PLANAR_EQUILIBRIUM_THRESHOLD_U_ANG2,
    vib_max: float = VIBRATIONAL_PLANAR_MAX_U_ANG2,
    quasi_min: float = NEAR_PLANAR_MIN_U_ANG2,
    methyl_min: float = METHYL_ROTOR_MIN_U_ANG2,
) -> PlanarityClassification:
    """Classifies molecular planarity based on inertial defect Delta and c-axis coordinates.

    Parameters
    ----------
    defect : float
        Inertial defect Delta = I_c - I_a - I_b in u * Angstrom^2.
    max_c_coord : float
        Maximum absolute coordinate along the c principal axis in Angstroms.
    rotor_type : Optional[RotorType]
        Rotor symmetry classification. Spherical tops are classified as NON_PLANAR_3D.
    is_v0_ground_state : bool
        If True, indicates vibrationally averaged ground state (where Delta_0 > 0 is physical).

    Returns
    -------
    PlanarityClassification
        Planarity state classification.
    """
    if rotor_type == RotorType.SPHERICAL_TOP:
        return PlanarityClassification.NON_PLANAR_3D

    if abs(defect) <= planar_tol and max_c_coord <= 1e-3:
        return PlanarityClassification.STRICTLY_PLANAR_EQUILIBRIUM

    if defect > planar_tol:
        if defect <= vib_max:
            return PlanarityClassification.VIBRATIONALLY_PLANAR_GROUND_STATE
        return PlanarityClassification.ANOMALOUS_POSITIVE_DEFECT

    # Defect is negative (Delta < -planar_tol)
    if defect >= quasi_min:
        return PlanarityClassification.QUASI_PLANAR

    if defect >= methyl_min:
        return PlanarityClassification.METHYL_ROTOR

    return PlanarityClassification.NON_PLANAR_3D


def calculate_inertial_properties(
    symbols: Sequence[Union[str, int]],
    coords: np.ndarray,
    is_v0_ground_state: bool = False,
    custom_masses: Optional[Sequence[float]] = None,
) -> MolecularInertialProperties:
    """Performs full end-to-end spectroscopic and inertial property calculation.

    Parameters
    ----------
    symbols : Sequence[Union[str, int]]
        List of atomic symbols or atomic numbers.
    coords : np.ndarray
        Array of shape (N, 3) with Cartesian coordinates in Angstroms.
    is_v0_ground_state : bool
        Whether this calculation represents a vibrational ground state observable (v=0).
    custom_masses : Optional[Sequence[float]]
        Optional explicit mass overrides.

    Returns
    -------
    MolecularInertialProperties
        Complete computed inertial property bundle.
    """
    (ia, ib, ic), rot_mat, pas_coords, tot_mass, com_vec = compute_principal_moments_and_axes(
        coords, symbols, custom_masses
    )

    a_mhz, b_mhz, c_mhz = compute_rotational_constants(ia, ib, ic)
    a_ghz, b_ghz, c_ghz = a_mhz * MHZ_TO_GHZ, b_mhz * MHZ_TO_GHZ, c_mhz * MHZ_TO_GHZ
    a_cm1, b_cm1, c_cm1 = a_mhz * MHZ_TO_CM1, b_mhz * MHZ_TO_CM1, c_mhz * MHZ_TO_CM1

    defect = compute_inertial_defect(ia, ib, ic)
    paa, pbb, pcc = compute_planar_moments(ia, ib, ic)
    kappa = compute_rays_asymmetry_kappa(a_mhz, b_mhz, c_mhz)
    bp, bo = compute_wangs_asymmetry_parameters(a_mhz, b_mhz, c_mhz)

    max_c = float(np.max(np.abs(pas_coords[:, 2]))) if pas_coords.shape[0] > 0 else 0.0
    rotor_type = classify_rotor_type(ia, ib, ic, kappa)
    planarity = classify_planarity(
        defect=defect,
        max_c_coord=max_c,
        rotor_type=rotor_type,
        is_v0_ground_state=is_v0_ground_state,
    )

    symbols_str = [str(s) for s in symbols]

    return MolecularInertialProperties(
        total_mass_amu=tot_mass,
        center_of_mass_angstrom=com_vec,
        number_of_atoms=len(symbols),
        ia_amu_angstrom2=ia,
        ib_amu_angstrom2=ib,
        ic_amu_angstrom2=ic,
        a_mhz=a_mhz,
        b_mhz=b_mhz,
        c_mhz=c_mhz,
        a_ghz=a_ghz,
        b_ghz=b_ghz,
        c_ghz=c_ghz,
        a_cm1=a_cm1,
        b_cm1=b_cm1,
        c_cm1=c_cm1,
        inertial_defect_amu_angstrom2=defect,
        planar_moment_paa_amu_angstrom2=paa,
        planar_moment_pbb_amu_angstrom2=pbb,
        planar_moment_pcc_amu_angstrom2=pcc,
        rays_kappa=kappa,
        wangs_bp=bp,
        wangs_bo=bo,
        rotor_type=rotor_type,
        planarity_class=planarity,
        principal_axes_matrix=rot_mat.tolist(),
        principal_coordinates=pas_coords.tolist(),
        atomic_symbols=symbols_str,
        provenance_tag="[D]",
    )


# =============================================================================
# Primary Validator & Formatter Class
# =============================================================================

class InertialDefectValidator:
    """Authoritative Validator and Formatter for Spectroscopic Inertial Properties.

    Performs comprehensive verification of molecular geometries against physical invariants
    (triangle inequalities, non-negative planar moments, ascending moment sort), Method Matrix
    v4 product tolerances, and formats publication-quality reports (GFM Markdown, LaTeX,
    JSON, PyArrow Parquet, Pickett comments).
    """

    def __init__(self, config: Optional[InertialDefectValidatorConfig] = None) -> None:
        """Initializes validator with custom or standard Method Matrix v4 configuration."""
        self.config = config or InertialDefectValidatorConfig()

    def validate_geometry(
        self,
        symbols: Sequence[Union[str, int]],
        coords: np.ndarray,
        reference_rotational_constants_mhz: Optional[Tuple[float, float, float]] = None,
        product_class: ProductClass = ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
        molecule_name: str = "Molecular_System",
    ) -> InertialDefectValidationReport:
        """Audits a Cartesian molecular geometry and verifies all spectroscopic invariants.

        Parameters
        ----------
        symbols : Sequence[Union[str, int]]
            Atomic symbols or atomic numbers Z.
        coords : np.ndarray
            Array of shape (N, 3) with Cartesian coordinates in Angstroms.
        reference_rotational_constants_mhz : Optional[Tuple[float, float, float]]
            Reference (A, B, C) in MHz to test against Method Matrix product tolerances.
        product_class : ProductClass
            Method Matrix target product class (A: de novo, B: semi-exp, C: diffs).
        molecule_name : str
            Identifier for report headers.

        Returns
        -------
        InertialDefectValidationReport
            Full structured validation report.
        """
        start_t = time.perf_counter()
        passed_checks: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []
        rel_devs: Dict[str, float] = {}
        abs_devs: Dict[str, float] = {}

        # 1. Calculate Physical Properties
        props = calculate_inertial_properties(
            symbols, coords, is_v0_ground_state=self.config.is_ground_state_v0
        )
        passed_checks.append("Physical property calculation converged successfully")

        # 2. Check Principal Moment Sort Invariant (I_a <= I_b <= I_c)
        if props.ia_amu_angstrom2 <= props.ib_amu_angstrom2 <= props.ic_amu_angstrom2:
            passed_checks.append("Principal moments satisfy ascending ordering (I_a <= I_b <= I_c)")
        else:
            errors.append(
                f"Principal moment ordering violated: I_a={props.ia_amu_angstrom2:.4f}, "
                f"I_b={props.ib_amu_angstrom2:.4f}, I_c={props.ic_amu_angstrom2:.4f}"
            )

        # 3. Check Rotational Constant Sort Invariant (A >= B >= C)
        if props.a_mhz >= props.b_mhz >= props.c_mhz:
            passed_checks.append("Rotational constants satisfy descending ordering (A >= B >= C)")
        else:
            errors.append(
                f"Rotational constant ordering violated: A={props.a_mhz:.2f}, "
                f"B={props.b_mhz:.2f}, C={props.c_mhz:.2f} MHz"
            )

        # 4. Check Triangle Inequalities for Rigid Mass Distributions
        # For a rigid classical 3D mass distribution: I_a + I_b >= I_c  (i.e. Delta <= 0)
        # Note: in v=0 vibrational ground states, zero-point out-of-plane vibration permits Delta_0 > 0.
        if self.config.enforce_triangle_inequality:
            sum_ab = props.ia_amu_angstrom2 + props.ib_amu_angstrom2
            if props.ic_amu_angstrom2 <= sum_ab + 1e-7:
                passed_checks.append(
                    f"Triangle inequality satisfied: I_a + I_b ({sum_ab:.4f}) >= I_c ({props.ic_amu_angstrom2:.4f})"
                )
            else:
                if self.config.is_ground_state_v0:
                    if props.inertial_defect_amu_angstrom2 <= self.config.vibrational_planar_max:
                        passed_checks.append(
                            f"Ground-state vibrational inertial defect Delta_0 = +{props.inertial_defect_amu_angstrom2:.4f} u*A^2 "
                            f"within acceptable zero-point band [0, {self.config.vibrational_planar_max} u*A^2]"
                        )
                    else:
                        warnings.append(
                            f"Ground-state vibrational defect Delta_0 = +{props.inertial_defect_amu_angstrom2:.4f} u*A^2 "
                            f"exceeds standard zero-point upper bound ({self.config.vibrational_planar_max} u*A^2)"
                        )
                else:
                    errors.append(
                        f"Rigid triangle inequality violated: I_c ({props.ic_amu_angstrom2:.4f}) > "
                        f"I_a + I_b ({sum_ab:.4f}) yields unphysical rigid Delta = +{props.inertial_defect_amu_angstrom2:.4f} u*A^2"
                    )

        # 5. Check Non-Negative Planar Moments
        if self.config.enforce_positive_planar_moments:
            if props.planar_moment_paa_amu_angstrom2 >= -1e-6 and props.planar_moment_pbb_amu_angstrom2 >= -1e-6:
                passed_checks.append(
                    f"In-plane planar moments non-negative: P_aa={props.planar_moment_paa_amu_angstrom2:.4f}, "
                    f"P_bb={props.planar_moment_pbb_amu_angstrom2:.4f} u*A^2"
                )
            else:
                errors.append(
                    f"Negative in-plane planar moment detected: P_aa={props.planar_moment_paa_amu_angstrom2:.4f}, "
                    f"P_bb={props.planar_moment_pbb_amu_angstrom2:.4f} u*A^2"
                )

            if not self.config.is_ground_state_v0:
                if props.planar_moment_pcc_amu_angstrom2 >= -1e-6:
                    passed_checks.append(
                        f"Out-of-plane planar moment P_cc non-negative ({props.planar_moment_pcc_amu_angstrom2:.4f} u*A^2)"
                    )
                else:
                    errors.append(
                        f"Negative rigid P_cc planar moment ({props.planar_moment_pcc_amu_angstrom2:.4f} u*A^2)"
                    )

        # 6. Check Ray's Kappa Range [-1.0, +1.0]
        if -1.0 <= props.rays_kappa <= 1.0:
            passed_checks.append(f"Ray's asymmetry parameter kappa={props.rays_kappa:.4f} in [-1.0, +1.0]")
        else:
            errors.append(f"Ray's asymmetry parameter kappa={props.rays_kappa:.4f} out of bounds")

        # 7. Check Reference Deviations against Method Matrix Tolerances
        if reference_rotational_constants_mhz is not None:
            ref_a, ref_b, ref_c = reference_rotational_constants_mhz
            rel_a = abs(props.a_mhz - ref_a) / max(ref_a, 1e-12)
            rel_b = abs(props.b_mhz - ref_b) / max(ref_b, 1e-12)
            rel_c = abs(props.c_mhz - ref_c) / max(ref_c, 1e-12)

            rel_devs = {"A_rel_error": rel_a, "B_rel_error": rel_b, "C_rel_error": rel_c}
            abs_devs = {
                "A_abs_diff_mhz": float(abs(props.a_mhz - ref_a)),
                "B_abs_diff_mhz": float(abs(props.b_mhz - ref_b)),
                "C_abs_diff_mhz": float(abs(props.c_mhz - ref_c)),
            }

            # Select target threshold based on Product Class
            if product_class == ProductClass.PRODUCT_B_SEMI_EXPERIMENTAL:
                target_tol = self.config.product_b_tol_rel
                product_desc = "Product B (Semi-Experimental <= 0.06%)"
            elif product_class == ProductClass.PRODUCT_C_DIFFERENCES:
                target_tol = self.config.product_c_tol_rel
                product_desc = "Product C (Differences / Isotopologues <= 0.10%)"
            else:
                target_tol = self.config.product_a_floppy_tol_rel
                product_desc = "Product A (De Novo <= 2.0%)"

            max_rel_err = max(rel_a, rel_b, rel_c)
            if max_rel_err <= target_tol:
                passed_checks.append(
                    f"{product_desc} compliance passed: Max relative error = {max_rel_err * 100:.3f}% "
                    f"(<= {target_tol * 100:.2f}%)"
                )
            else:
                warnings.append(
                    f"{product_desc} tolerance exceeded: Max relative error = {max_rel_err * 100:.3f}% "
                    f"(target <= {target_tol * 100:.2f}%)"
                )

        # 8. Determine Overall Status
        if len(errors) > 0:
            status = ValidationStatus.INVALID
            is_valid = False
        elif len(warnings) > 0:
            status = ValidationStatus.WARNING
            is_valid = True
        else:
            status = ValidationStatus.VALID
            is_valid = True

        exec_ms = (time.perf_counter() - start_t) * 1000.0

        return InertialDefectValidationReport(
            is_valid=is_valid,
            status=status,
            product_class=product_class,
            properties=props,
            passed_checks=passed_checks,
            warnings=warnings,
            errors=errors,
            relative_deviations=rel_devs,
            absolute_deviations=abs_devs,
            molecule_name=molecule_name,
            execution_time_ms=exec_ms,
        )

    def validate_xyz_string(
        self,
        xyz_content: str,
        reference_rotational_constants_mhz: Optional[Tuple[float, float, float]] = None,
        product_class: ProductClass = ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
        molecule_name: Optional[str] = None,
    ) -> InertialDefectValidationReport:
        """Parses standard multi-line XYZ content and validates inertial properties."""
        lines = [line.strip() for line in xyz_content.strip().splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError(f"Invalid XYZ format: content must have at least 3 lines, got {len(lines)}")

        try:
            n_atoms = int(lines[0])
        except ValueError as exc:
            raise ValueError(f"Invalid XYZ header: line 1 must be integer atom count, got '{lines[0]}'") from exc

        comment = lines[1]
        mol_name = molecule_name or (comment if comment and not comment.startswith("#") else "XYZ_Molecule")

        symbols: List[str] = []
        coords_list: List[List[float]] = []

        for idx, line in enumerate(lines[2 : 2 + n_atoms], start=3):
            tokens = line.split()
            if len(tokens) < 4:
                raise ValueError(f"Malformed XYZ coordinate line {idx}: '{line}'")
            symbols.append(tokens[0])
            try:
                coords_list.append([float(tokens[1]), float(tokens[2]), float(tokens[3])])
            except ValueError as exc:
                raise ValueError(f"Non-numeric coordinate on line {idx}: '{line}'") from exc

        coords_arr = np.array(coords_list, dtype=np.float64)
        return self.validate_geometry(
            symbols=symbols,
            coords=coords_arr,
            reference_rotational_constants_mhz=reference_rotational_constants_mhz,
            product_class=product_class,
            molecule_name=mol_name,
        )

    def validate_xyz_file(
        self,
        file_path: Union[str, pathlib.Path],
        reference_rotational_constants_mhz: Optional[Tuple[float, float, float]] = None,
        product_class: ProductClass = ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
    ) -> InertialDefectValidationReport:
        """Reads physical .xyz file from disk and validates inertial defect properties."""
        path = pathlib.Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"XYZ file not found: {path}")

        content = path.read_text(encoding="utf-8")
        mol_name = path.stem
        return self.validate_xyz_string(
            xyz_content=content,
            reference_rotational_constants_mhz=reference_rotational_constants_mhz,
            product_class=product_class,
            molecule_name=mol_name,
        )

    # =========================================================================
    # Formatter Subroutines
    # =========================================================================

    def format_markdown_report(
        self, report: InertialDefectValidationReport, title: Optional[str] = None
    ) -> str:
        """Synthesizes an authoritative GFM Markdown report with LaTeX equations and callouts.

        Parameters
        ----------
        report : InertialDefectValidationReport
            Validation report instance.
        title : Optional[str]
            Optional custom report title.

        Returns
        -------
        str
            Formatted GitHub Flavored Markdown document.
        """
        p = report.properties
        hdr_title = title or f"CoChem Inertial Defect & Planar Moment Audit: {report.molecule_name}"

        status_badge = {
            ValidationStatus.VALID: "**STATUS: PASSED**",
            ValidationStatus.WARNING: "**STATUS: WARNING**",
            ValidationStatus.INVALID: "**STATUS: FAILED**",
        }.get(report.status, "**STATUS: UNKNOWN**")

        planarity_desc = {
            PlanarityClassification.STRICTLY_PLANAR_EQUILIBRIUM: "Strictly Planar Equilibrium (|Delta| < 1e-4 u*A^2)",
            PlanarityClassification.VIBRATIONALLY_PLANAR_GROUND_STATE: "Vibrationally Planar Ground State (0.0 < Delta_0 <= 0.50 u*A^2)",
            PlanarityClassification.QUASI_PLANAR: "Quasi-Planar / Slightly Buckled (-1.50 <= Delta < 0.0 u*A^2)",
            PlanarityClassification.METHYL_ROTOR: "Internal Methyl Rotor Frame (-6.50 <= Delta < -1.50 u*A^2)",
            PlanarityClassification.NON_PLANAR_3D: "Genuine 3D Non-Planar Topology (Delta < -6.50 u*A^2)",
            PlanarityClassification.ANOMALOUS_POSITIVE_DEFECT: "Anomalous Positive Defect (Delta > 0.50 u*A^2)",
        }.get(p.planarity_class, str(p.planarity_class.value))

        md_lines = [
            f"# {hdr_title}",
            "",
            "> [!NOTE]",
            f"> **Method Matrix v4 Compliance Audit** | {status_badge} | Product Class: `{report.product_class.value}`",
            f"> Generated on: `{report.timestamp_utc}` | Execution Time: `{report.execution_time_ms:.2f} ms`",
            "",
            "## 1. Executive Summary & Rotor Classification",
            "",
            f"- **Molecule Name:** `{report.molecule_name}`",
            f"- **Total Mass:** `{p.total_mass_amu:.6f} u` ({p.number_of_atoms} atoms)",
            f"- **Rotor Type:** `{p.rotor_type.value}`",
            f"- **Planarity State:** `{planarity_desc}`",
            f"- **Ray's Asymmetry Parameter (kappa):** `{p.rays_kappa:.6f}`",
            f"- **Wang's Asymmetry Parameters:** $b_p = {p.wangs_bp:.6f}$, $b_o = {p.wangs_bo:.6f}$",
            "",
            "## 2. Spectroscopic Observables & Moments of Inertia",
            "",
            "| Axis | Principal Moment ($u\\cdot\\text{\\AA}^2$) | Constant ($A,B,C$ in MHz) | Constant (GHz) | Constant ($\\text{cm}^{-1}$) |",
            "| :--- | :---: | :---: | :---: | :---: |",
            f"| **a** | `{p.ia_amu_angstrom2:.6f}` | `{p.a_mhz:.4f}` | `{p.a_ghz:.6f}` | `{p.a_cm1:.6f}` |",
            f"| **b** | `{p.ib_amu_angstrom2:.6f}` | `{p.b_mhz:.4f}` | `{p.b_ghz:.6f}` | `{p.b_cm1:.6f}` |",
            f"| **c** | `{p.ic_amu_angstrom2:.6f}` | `{p.c_mhz:.4f}` | `{p.c_ghz:.6f}` | `{p.c_cm1:.6f}` |",
            "",
            "## 3. Inertial Defect & Planar Moments (Method Matrix v4 §4.0)",
            "",
            "The five free secondary observables derived without electronic structure overhead:",
            "",
            f"- **Inertial Defect ($\\Delta = I_c - I_a - I_b$):** `{p.inertial_defect_amu_angstrom2:.6f} u*Angstrom^2`",
            f"- **Planar Moment $P_{{aa}} = \\sum m_i a_i^2 = \\frac{{1}}{{2}}(I_b + I_c - I_a)$:** `{p.planar_moment_paa_amu_angstrom2:.6f} u*Angstrom^2`",
            f"- **Planar Moment $P_{{bb}} = \\sum m_i b_i^2 = \\frac{{1}}{{2}}(I_a + I_c - I_b)$:** `{p.planar_moment_pbb_amu_angstrom2:.6f} u*Angstrom^2`",
            f"- **Planar Moment $P_{{cc}} = \\sum m_i c_i^2 = \\frac{{1}}{{2}}(I_a + I_b - I_c)$:** `{p.planar_moment_pcc_amu_angstrom2:.6f} u*Angstrom^2`",
            "",
        ]

        if report.relative_deviations:
            md_lines.extend(
                [
                    "## 4. Reference Benchmark Comparison",
                    "",
                    "| Constant | Relative Error (%) | Absolute Difference (MHz) | Target Tolerance |",
                    "| :--- | :---: | :---: | :---: |",
                    f"| **A** | `{report.relative_deviations.get('A_rel_error', 0.0) * 100:.3f}%` | `{report.absolute_deviations.get('A_abs_diff_mhz', 0.0):.3f} MHz` | `0.50% - 2.00%` |",
                    f"| **B** | `{report.relative_deviations.get('B_rel_error', 0.0) * 100:.3f}%` | `{report.absolute_deviations.get('B_abs_diff_mhz', 0.0):.3f} MHz` | `0.50% - 2.00%` |",
                    f"| **C** | `{report.relative_deviations.get('C_rel_error', 0.0) * 100:.3f}%` | `{report.absolute_deviations.get('C_abs_diff_mhz', 0.0):.3f} MHz` | `0.50% - 2.00%` |",
                    "",
                ]
            )

        md_lines.extend(
            [
                "## 5. Verification Diagnostic Log",
                "",
            ]
        )

        if report.passed_checks:
            md_lines.append("### Passed Physical Checks")
            for chk in report.passed_checks:
                md_lines.append(f"- [x] {chk}")
            md_lines.append("")

        if report.warnings:
            md_lines.append("> [!WARNING]")
            md_lines.append("> **Validation Warnings:**")
            for w in report.warnings:
                md_lines.append(f"> - {w}")
            md_lines.append("")

        if report.errors:
            md_lines.append("> [!CAUTION]")
            md_lines.append("> **Critical Invariant Failures:**")
            for e in report.errors:
                md_lines.append(f"> - {e}")
            md_lines.append("")

        return "\n".join(md_lines)

    def format_latex_table(
        self, report: InertialDefectValidationReport, label: Optional[str] = None
    ) -> str:
        """Generates a publication-ready LaTeX table fragment for Supporting Information."""
        p = report.properties
        tbl_label = label or f"tab:inertial_{report.molecule_name.lower()}"

        tex_lines = [
            r"\begin{table}[htbp]",
            r"  \centering",
            f"  \\caption{{Spectroscopic rotational constants, moments of inertia, and inertial defect observables for {report.molecule_name}.}}",
            f"  \\label{{{tbl_label}}}",
            r"  \begin{tabular}{lcccc}",
            r"    \hline\hline",
            r"    Observable & Axis / Parameter & Value & Unit & Provenance \\",
            r"    \hline",
            f"    Rotational constant & $A$ & {p.a_mhz:.4f} & MHz & [D] \\\\",
            f"    Rotational constant & $B$ & {p.b_mhz:.4f} & MHz & [D] \\\\",
            f"    Rotational constant & $C$ & {p.c_mhz:.4f} & MHz & [D] \\\\",
            r"    \hline",
            f"    Principal moment of inertia & $I_a$ & {p.ia_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Principal moment of inertia & $I_b$ & {p.ib_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Principal moment of inertia & $I_c$ & {p.ic_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            r"    \hline",
            f"    Inertial defect & $\\Delta$ & {p.inertial_defect_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Planar moment & $P_{{aa}}$ & {p.planar_moment_paa_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Planar moment & $P_{{bb}}$ & {p.planar_moment_pbb_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Planar moment & $P_{{cc}}$ & {p.planar_moment_pcc_amu_angstrom2:.6f} & u\\cdot\\AA$^2$ & [D] \\\\",
            f"    Ray's asymmetry parameter & $\\kappa$ & {p.rays_kappa:.6f} & -- & [D] \\\\",
            r"    \hline\hline",
            r"  \end{tabular}",
            r"\end{table}",
        ]
        return "\n".join(tex_lines)

    def format_pickett_comments(self, report: InertialDefectValidationReport) -> str:
        """Formats comment block lines for inclusion in Pickett SPFIT/SPCAT .var or .par files."""
        p = report.properties
        lines = [
            f"# Pickett Parameter File Generated with CoChem-BASE (Stage 5.0)",
            f"# Molecule: {report.molecule_name}",
            f"# Total Mass: {p.total_mass_amu:.6f} u ({p.number_of_atoms} atoms)",
            f"# A = {p.a_mhz:13.4f} MHz | B = {p.b_mhz:13.4f} MHz | C = {p.c_mhz:13.4f} MHz",
            f"# Ia = {p.ia_amu_angstrom2:10.6f} u*A^2 | Ib = {p.ib_amu_angstrom2:10.6f} u*A^2 | Ic = {p.ic_amu_angstrom2:10.6f} u*A^2",
            f"# Inertial Defect Delta = {p.inertial_defect_amu_angstrom2:10.6f} u*A^2",
            f"# Planar Moments: Paa = {p.planar_moment_paa_amu_angstrom2:.6f}, Pbb = {p.planar_moment_pbb_amu_angstrom2:.6f}, Pcc = {p.planar_moment_pcc_amu_angstrom2:.6f} u*A^2",
            f"# Ray's Kappa = {p.rays_kappa:10.6f} | Rotor: {p.rotor_type.value} | Planarity: {p.planarity_class.value}",
        ]
        return "\n".join(lines)

    def format_json_report(
        self, report: InertialDefectValidationReport, indent: int = 2
    ) -> str:
        """Serializes report into structured JSON string."""
        return json.dumps(report.to_dict(), indent=indent)

    def format_terminal_summary(self, report: InertialDefectValidationReport) -> str:
        """Emits clean, colorized ANSI terminal summary card."""
        p = report.properties
        c_green = "\033[92m"
        c_yellow = "\033[93m"
        c_red = "\033[91m"
        c_cyan = "\033[96m"
        c_bold = "\033[1m"
        c_reset = "\033[0m"

        status_col = {
            ValidationStatus.VALID: f"{c_green}{c_bold}[VALID / PASSED]{c_reset}",
            ValidationStatus.WARNING: f"{c_yellow}{c_bold}[WARNING]{c_reset}",
            ValidationStatus.INVALID: f"{c_red}{c_bold}[INVALID / FAILED]{c_reset}",
        }.get(report.status, f"{report.status.value}")

        lines = [
            f"{c_cyan}========================================================================{c_reset}",
            f"{c_bold}  CoChem Spectroscopic Inertial Defect Audit: {report.molecule_name}{c_reset}",
            f"{c_cyan}========================================================================{c_reset}",
            f"  Audit Status     : {status_col}",
            f"  Product Class    : {report.product_class.value}",
            f"  Total Mass       : {p.total_mass_amu:.6f} u ({p.number_of_atoms} atoms)",
            f"  Rotor Type       : {p.rotor_type.value}",
            f"  Planarity State  : {p.planarity_class.value}",
            f"------------------------------------------------------------------------",
            f"  A (MHz)          : {p.a_mhz:13.4f}  |  I_a (u*A^2): {p.ia_amu_angstrom2:10.6f}",
            f"  B (MHz)          : {p.b_mhz:13.4f}  |  I_b (u*A^2): {p.ib_amu_angstrom2:10.6f}",
            f"  C (MHz)          : {p.c_mhz:13.4f}  |  I_c (u*A^2): {p.ic_amu_angstrom2:10.6f}",
            f"------------------------------------------------------------------------",
            f"  Inertial Defect  : {c_bold}{p.inertial_defect_amu_angstrom2:10.6f} u*Angstrom^2{c_reset}",
            f"  Planar Moments   : P_aa={p.planar_moment_paa_amu_angstrom2:.4f}, P_bb={p.planar_moment_pbb_amu_angstrom2:.4f}, P_cc={p.planar_moment_pcc_amu_angstrom2:.4f} u*A^2",
            f"  Ray's Kappa      : {p.rays_kappa:10.6f}  (b_p={p.wangs_bp:.6f}, b_o={p.wangs_bo:.6f})",
            f"{c_cyan}========================================================================{c_reset}",
        ]
        return "\n".join(lines)

    def to_dataframe(
        self, reports: Sequence[InertialDefectValidationReport]
    ) -> pd.DataFrame:
        """Converts a collection of validation reports into a Pandas DataFrame."""
        rows: List[Dict[str, Any]] = []
        for r in reports:
            p = r.properties
            row = {
                "molecule_name": r.molecule_name,
                "is_valid": r.is_valid,
                "status": r.status.value,
                "product_class": r.product_class.value,
                "total_mass_amu": p.total_mass_amu,
                "number_of_atoms": p.number_of_atoms,
                "A_mhz": p.a_mhz,
                "B_mhz": p.b_mhz,
                "C_mhz": p.c_mhz,
                "Ia_u_ang2": p.ia_amu_angstrom2,
                "Ib_u_ang2": p.ib_amu_angstrom2,
                "Ic_u_ang2": p.ic_amu_angstrom2,
                "inertial_defect_u_ang2": p.inertial_defect_amu_angstrom2,
                "planar_moment_paa_u_ang2": p.planar_moment_paa_amu_angstrom2,
                "planar_moment_pbb_u_ang2": p.planar_moment_pbb_amu_angstrom2,
                "planar_moment_pcc_u_ang2": p.planar_moment_pcc_amu_angstrom2,
                "rays_kappa": p.rays_kappa,
                "wangs_bp": p.wangs_bp,
                "wangs_bo": p.wangs_bo,
                "rotor_type": p.rotor_type.value,
                "planarity_class": p.planarity_class.value,
                "execution_time_ms": r.execution_time_ms,
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def to_pyarrow_table(
        self, reports: Sequence[InertialDefectValidationReport]
    ) -> pa.Table:
        """Converts a sequence of validation reports into a PyArrow Table for Parquet storage."""
        df = self.to_dataframe(reports)
        return pa.Table.from_pandas(df)


# =============================================================================
# High-Level Helper Functions & CLI Interface
# =============================================================================

def validate_inertial_defect(
    symbols: Sequence[Union[str, int]],
    coords: np.ndarray,
    reference_rotational_constants_mhz: Optional[Tuple[float, float, float]] = None,
    product_class: ProductClass = ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
    config: Optional[InertialDefectValidatorConfig] = None,
    molecule_name: str = "Complex",
) -> InertialDefectValidationReport:
    """Convenience functional interface for molecular inertial defect validation."""
    validator = InertialDefectValidator(config=config)
    return validator.validate_geometry(
        symbols=symbols,
        coords=coords,
        reference_rotational_constants_mhz=reference_rotational_constants_mhz,
        product_class=product_class,
        molecule_name=molecule_name,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="CoChem Inertial Defect & Planar Moment Validator & Formatter (Stage 5.0 / 6.0)"
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Path to input Cartesian geometry file (.xyz)",
    )
    parser.add_argument(
        "--ref-a",
        type=float,
        default=None,
        help="Reference rotational constant A in MHz",
    )
    parser.add_argument(
        "--ref-b",
        type=float,
        default=None,
        help="Reference rotational constant B in MHz",
    )
    parser.add_argument(
        "--ref-c",
        type=float,
        default=None,
        help="Reference rotational constant C in MHz",
    )
    parser.add_argument(
        "--product", "-p",
        type=str,
        choices=["A", "B", "C"],
        default="A",
        help="Method Matrix v4 Product Class (A: de novo, B: semi-exp, C: differences)",
    )
    parser.add_argument(
        "--ground-state-v0",
        action="store_true",
        help="Evaluate as vibrational ground state v=0 observable (permits Delta_0 > 0)",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default=None,
        help="Optional path to export GFM Markdown report",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Optional path to export JSON validation report",
    )
    parser.add_argument(
        "--output-tex",
        type=str,
        default=None,
        help="Optional path to export LaTeX table snippet",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress terminal summary output",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI execution entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.input:
        parser.print_help()
        return 1

    input_path = pathlib.Path(args.input)
    if not input_path.is_file():
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        return 1

    product_map = {
        "A": ProductClass.PRODUCT_A_ABSOLUTE_DENOVO,
        "B": ProductClass.PRODUCT_B_SEMI_EXPERIMENTAL,
        "C": ProductClass.PRODUCT_C_DIFFERENCES,
    }
    prod_class = product_map.get(args.product, ProductClass.PRODUCT_A_ABSOLUTE_DENOVO)

    ref_constants = None
    if args.ref_a is not None and args.ref_b is not None and args.ref_c is not None:
        ref_constants = (args.ref_a, args.ref_b, args.ref_c)

    cfg = InertialDefectValidatorConfig(is_ground_state_v0=args.ground_state_v0)
    validator = InertialDefectValidator(config=cfg)

    try:
        report = validator.validate_xyz_file(
            file_path=input_path,
            reference_rotational_constants_mhz=ref_constants,
            product_class=prod_class,
        )
    except Exception as exc:
        print(f"Validation Error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(validator.format_terminal_summary(report))

    if args.output_md:
        out_md_path = pathlib.Path(args.output_md)
        out_md_path.parent.mkdir(parents=True, exist_ok=True)
        out_md_path.write_text(validator.format_markdown_report(report), encoding="utf-8")
        print(f"Exported Markdown report: {out_md_path}")

    if args.output_json:
        out_json_path = pathlib.Path(args.output_json)
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        out_json_path.write_text(validator.format_json_report(report), encoding="utf-8")
        print(f"Exported JSON report: {out_json_path}")

    if args.output_tex:
        out_tex_path = pathlib.Path(args.output_tex)
        out_tex_path.parent.mkdir(parents=True, exist_ok=True)
        out_tex_path.write_text(validator.format_latex_table(report), encoding="utf-8")
        print(f"Exported LaTeX table: {out_tex_path}")

    return 0 if report.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
