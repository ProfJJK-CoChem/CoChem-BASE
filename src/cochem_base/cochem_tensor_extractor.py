# -*- coding: utf-8 -*-
"""CoChem Stage 5.0 / Phase 6: Moment of Inertia Tensor & Rotational Constant Extractor.

Authoritative Module for CoChem-BASE / CoChem-TORQ (Phase 6).
Implements exact moment of inertia tensor evaluation, principal axis diagonalization,
Cartesian singularity protections for linear rotors, Ray's asymmetry parameter analysis,
and dynamic representation switching (I^r <-> III^r) compliant with Method Matrix standards.

Authoritative Standards:
- CODATA 2022 fundamental physical constants
- CIAAW / IUPAC Standard Atomic Weights & Exact Mono-Isotopic Masses
- Method Matrix (Section 13.2, 13.5, 20.2): Rotational observables & representation switching
- King, Hainer, & Cross, J. Chem. Phys. 11, 27 (1943) (Asymmetric Rotor Representations)
- Gordy & Cook, Microwave Molecular Spectra, 3rd Ed., Wiley (1984)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from cochem_base.exceptions import (
    CoChemIntegrityError,
    ProvenanceErrorCode,
)

logger = logging.getLogger("cochem.tensor_extractor")

# =============================================================================
# 1. Fundamental Physical Constants (CODATA 2022 Exact Recommended Values)
# =============================================================================

# Planck constant h in J * s (exact SI definition)
PLANCK_H = 6.62607015e-34

# Unified atomic mass unit in kg (CODATA 2022)
AMU_KG = 1.66053906660e-27

# Speed of light in vacuum in cm / s (exact SI definition)
SPEED_OF_LIGHT_CM_S = 29979245800.0

# Inertia to rotational constant conversion factor in MHz * amu * Angstrom^2:
# C_rot = h / (8 * pi^2 * u * 1e-20) * 1e-6 MHz = 505379.0084350172 MHz * amu * Angstrom^2
INERTIA_CONVERSION_AMU_ANG2_MHZ = 505379.0084350172

# Inertia to rotational constant conversion factor in GHz * amu * Angstrom^2:
INERTIA_CONVERSION_AMU_ANG2_GHZ = 505.3790084350172

# Inertia to rotational constant conversion factor in cm^-1 * amu * Angstrom^2:
INERTIA_CONVERSION_AMU_ANG2_CM1 = 16.85762920252


# =============================================================================
# 2. Dynamic Mendeleev Exact Mono-Isotopic & Atomic Masses (amu / Daltons)
# =============================================================================

from collections.abc import Mapping
try:
    from mendeleev import element as _mendeleev_element
except ImportError:
    _mendeleev_element = None


class _DynamicMendeleevMassMap(Mapping):
    """Dynamic isotopic and atomic mass mapping backed by the Mendeleev library."""

    def __getitem__(self, key: str) -> float:
        if not key or not isinstance(key, str):
            raise KeyError(key)
        sym = str(key).strip()
        if not sym:
            raise KeyError(key)

        # Hydrogen isotopes
        if sym.upper() in {"D", "2H"}:
            if _mendeleev_element is not None:
                try:
                    for iso in getattr(_mendeleev_element("H"), "isotopes", []):
                        if iso.mass_number == 2:
                            return float(iso.mass)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
            return 2.01410177812

        if sym.upper() in {"T", "3H"}:
            if _mendeleev_element is not None:
                try:
                    for iso in getattr(_mendeleev_element("H"), "isotopes", []):
                        if iso.mass_number == 3:
                            return float(iso.mass)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")
            return 3.01604928132

        # Specific isotope notation like "13C", "35Cl", "14N", "16O"
        import re
        m = re.match(r"^(\d+)([A-Za-z]+)$", sym)
        if m:
            mass_num = int(m.group(1))
            el_sym = m.group(2).capitalize()
            if _mendeleev_element is not None:
                try:
                    el = _mendeleev_element(el_sym)
                    for iso in getattr(el, "isotopes", []):
                        if iso.mass_number == mass_num and iso.mass is not None:
                            return float(iso.mass)
                    if el.mass is not None:
                        return float(el.mass)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

        cleaned = "".join([c for c in sym if c.isalpha()]).capitalize()
        if cleaned:
            if _mendeleev_element is not None:
                try:
                    el = _mendeleev_element(cleaned)
                    # For mono-isotopic queries, return most abundant isotope mass if available
                    if getattr(el, "isotopes", None):
                        abundances = [
                            (getattr(iso, "abundance", 0.0) or 0.0, float(iso.mass))
                            for iso in el.isotopes
                            if iso.mass is not None
                        ]
                        if abundances:
                            abundances.sort(key=lambda x: x[0], reverse=True)
                            return abundances[0][1]
                    if el.mass is not None:
                        return float(el.mass)
                except Exception as _e:
                    logger.debug(f"Ignored exception: {_e}")

        raise KeyError(key)

    def __iter__(self):
        return iter([
            "H", "1H", "D", "2H", "T", "3H", "He", "3He", "4He", "Li", "6Li", "7Li",
            "Be", "9Be", "B", "10B", "11B", "C", "12C", "13C", "14C", "N", "14N", "15N",
            "O", "16O", "17O", "18O", "F", "19F", "Ne", "20Ne", "21Ne", "22Ne", "Na", "23Na",
            "Mg", "24Mg", "25Mg", "26Mg", "Al", "27Al", "Si", "28Si", "29Si", "30Si",
            "P", "31P", "S", "32S", "33S", "34S", "36S", "Cl", "35Cl", "37Cl",
            "Ar", "36Ar", "38Ar", "40Ar", "K", "39K", "40K", "41K", "Ca", "40Ca", "42Ca", "44Ca",
            "Sc", "Ti", "48Ti", "V", "51V", "Cr", "52Cr", "Mn", "55Mn", "Fe", "56Fe", "54Fe", "57Fe",
            "Co", "59Co", "Ni", "58Ni", "60Ni", "Cu", "63Cu", "65Cu", "Zn", "64Zn", "66Zn",
            "Ga", "Ge", "As", "75As", "Se", "80Se", "Br", "79Br", "81Br", "Kr", "84Kr",
            "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "I", "127I", "Xe", "132Xe", "Cs", "133Cs", "Ba", "138Ba"
        ])

    def __len__(self):
        return 118

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            self[key]
            return True
        except (KeyError, Exception):
            return False

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


CIAAW_ISOTOPIC_MASSES: Mapping[str, float] = _DynamicMendeleevMassMap()


def resolve_atomic_mass(symbol_or_mass: Union[str, float, int]) -> float:
    """Resolve atomic mass dynamically via Mendeleev library or direct float value."""
    if isinstance(symbol_or_mass, (int, float)):
        return float(symbol_or_mass)
    sym = str(symbol_or_mass).strip()
    if not sym:
        return 12.0
    try:
        return float(CIAAW_ISOTOPIC_MASSES[sym])
    except Exception:
        cleaned = "".join([c for c in sym if c.isalpha()])
        if cleaned:
            try:
                return float(CIAAW_ISOTOPIC_MASSES[cleaned])
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")
    # Default fallback to carbon-12 mass if unknown
    logger.warning("Unrecognized atomic symbol '%s'; defaulting to 12.0 amu.", sym)
    return 12.0


# =============================================================================
# 3. Data Transfer Objects and Result Containers
# =============================================================================

@dataclass
class CartesianProtectionResult:
    """Structured result of linear rotor collinearity detection and Cartesian protection."""

    is_linear: bool
    collinear_axis: Optional[str]
    angle_deviation_deg: float
    original_coordinates: np.ndarray
    pivoted_coordinates: np.ndarray
    cylindrical_coordinates: Optional[np.ndarray] = None
    applied_protection: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "is_linear": bool(self.is_linear),
            "collinear_axis": self.collinear_axis,
            "angle_deviation_deg": float(self.angle_deviation_deg),
            "original_coordinates": self.original_coordinates.tolist(),
            "pivoted_coordinates": self.pivoted_coordinates.tolist(),
            "cylindrical_coordinates": self.cylindrical_coordinates.tolist() if self.cylindrical_coordinates is not None else None,
            "applied_protection": bool(self.applied_protection),
            "metadata": self.metadata,
        }


@dataclass
class RepresentationSwitchResult:
    """Structured representation switch analysis based on Ray's asymmetry parameter."""

    ray_kappa: float
    recommended_representation: str
    rotor_type: str
    axis_mapping: Dict[str, str]
    wang_subblocks: Dict[str, str]
    is_prolate: bool
    is_oblate: bool
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass
class InertiaTensorResult:
    """Comprehensive moment of inertia tensor extraction and rotational constant analysis."""

    moments_of_inertia_amu_ang2: Dict[str, float]
    rotational_constants_mhz: Dict[str, float]
    rotational_constants_ghz: Dict[str, float]
    rotational_constants_cm1: Dict[str, float]
    principal_axes: np.ndarray
    center_of_mass: np.ndarray
    total_mass_amu: float
    planar_moments_amu_ang2: Dict[str, float]
    inertial_defect_amu_ang2: float
    ray_asymmetry_kappa: float
    rotor_type: str
    representation: RepresentationSwitchResult
    cartesian_protection: CartesianProtectionResult
    is_linear: bool
    is_planar: bool
    raw_inertia_matrix: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to JSON-compliant dictionary."""
        return {
            "moments_of_inertia_amu_ang2": self.moments_of_inertia_amu_ang2,
            "rotational_constants_mhz": self.rotational_constants_mhz,
            "rotational_constants_ghz": self.rotational_constants_ghz,
            "rotational_constants_cm1": self.rotational_constants_cm1,
            "principal_axes": self.principal_axes.tolist(),
            "center_of_mass": self.center_of_mass.tolist(),
            "total_mass_amu": float(self.total_mass_amu),
            "planar_moments_amu_ang2": self.planar_moments_amu_ang2,
            "inertial_defect_amu_ang2": float(self.inertial_defect_amu_ang2),
            "ray_asymmetry_kappa": float(self.ray_asymmetry_kappa),
            "rotor_type": self.rotor_type,
            "representation": self.representation.to_dict(),
            "cartesian_protection": self.cartesian_protection.to_dict(),
            "is_linear": bool(self.is_linear),
            "is_planar": bool(self.is_planar),
            "raw_inertia_matrix": self.raw_inertia_matrix.tolist(),
        }


# =============================================================================
# 4. Core Mathematical Algorithms
# =============================================================================

def calculate_center_of_mass(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """Calculate the 3D center-of-mass vector in Angstroms."""
    coords = np.asarray(coordinates, dtype=np.float64)
    m = np.asarray(masses, dtype=np.float64)
    total_m = float(np.sum(m))
    if total_m <= 0.0:
        raise CoChemIntegrityError(
            message="Total molecular mass must be positive.",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )
    com: np.ndarray = np.sum(coords * m[:, np.newaxis], axis=0) / total_m
    return np.asarray(com, dtype=np.float64)


def translate_to_center_of_mass(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Translate Cartesian coordinates to center-of-mass origin.

    Returns:
        Tuple of (centered_coordinates, com_vector).
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    com = calculate_center_of_mass(coords, masses)
    centered = coords - com
    return centered, com


def build_inertia_tensor(
    centered_coordinates: np.ndarray,
    masses: np.ndarray,
) -> np.ndarray:
    """Construct 3x3 symmetric Moment of Inertia Tensor in amu * Angstrom^2.

    I_xx = sum m_i (y_i^2 + z_i^2)
    I_yy = sum m_i (x_i^2 + z_i^2)
    I_zz = sum m_i (x_i^2 + y_i^2)
    I_xy = - sum m_i x_i y_i
    I_xz = - sum m_i x_i z_i
    I_yz = - sum m_i y_i z_i
    """
    x = centered_coordinates[:, 0]
    y = centered_coordinates[:, 1]
    z = centered_coordinates[:, 2]

    i_xx = np.sum(masses * (y**2 + z**2))
    i_yy = np.sum(masses * (x**2 + z**2))
    i_zz = np.sum(masses * (x**2 + y**2))
    i_xy = -np.sum(masses * x * y)
    i_xz = -np.sum(masses * x * z)
    i_yz = -np.sum(masses * y * z)

    return np.array([
        [i_xx, i_xy, i_xz],
        [i_xy, i_yy, i_yz],
        [i_xz, i_yz, i_zz],
    ], dtype=np.float64)


def apply_cartesian_protections(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    masses_or_symbols: Optional[Union[Sequence[str], Sequence[float]]] = None,
    angle_threshold_deg: float = 175.0,
) -> CartesianProtectionResult:
    """Pivots linear rotors to a 2D cylindrical projection when near-180 deg linear singularities are detected.

    Maintains mathematical stability during matrix diagonalizations without corrupting physical coordinates.

    Args:
        coordinates: (N, 3) Cartesian coordinates in Angstroms.
        masses_or_symbols: Optional masses or atomic symbols.
        angle_threshold_deg: Threshold in degrees (default 175.0 deg) above which an angle is considered linear.

    Returns:
        CartesianProtectionResult with aligned coordinates, cylindrical projection, and linearity metadata.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    num_atoms = coords.shape[0]

    if masses_or_symbols is not None:
        masses = np.array([resolve_atomic_mass(s) for s in masses_or_symbols], dtype=np.float64)
    else:
        masses = np.ones(num_atoms, dtype=np.float64)

    # 1 or 2 atoms are unconditionally collinear/linear
    if num_atoms <= 2:
        is_linear = True
        max_angle_dev = 0.0
    else:
        # Check collinearity via principal moments or angle inspection
        centered, _ = translate_to_center_of_mass(coords, masses)
        raw_i = build_inertia_tensor(centered, masses)
        eigvals, _ = np.linalg.eigh(raw_i)
        eigvals = np.sort(np.maximum(0.0, eigvals))

        # Inertia ratio check: if smallest moment I_1 is negligibly small compared to I_3
        ratio = eigvals[0] / max(1e-12, eigvals[2])

        # Bond angle check along consecutive atom triplets
        angles: List[float] = []
        for i in range(num_atoms - 2):
            v1 = coords[i] - coords[i + 1]
            v2 = coords[i + 2] - coords[i + 1]
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 > 1e-6 and norm2 > 1e-6:
                cos_th = np.dot(v1, v2) / (norm1 * norm2)
                cos_th = np.clip(cos_th, -1.0, 1.0)
                ang_deg = float(np.degrees(np.arccos(cos_th)))
                angles.append(ang_deg)

        min_ang = min(angles) if angles else 180.0
        # For collinear atoms, angle between consecutive bonds is ~ 180 deg
        is_collinear_angles = (min_ang >= angle_threshold_deg) if angles else True
        is_linear = (ratio < 1e-4) or is_collinear_angles
        max_angle_dev = abs(180.0 - min_ang) if angles else 0.0

    if is_linear:
        # Align molecular axis to the Z-axis
        centered, _ = translate_to_center_of_mass(coords, masses)
        if num_atoms >= 2:
            # Axis vector from first atom to last atom
            axis_vec = centered[-1] - centered[0]
            norm_ax = np.linalg.norm(axis_vec)
            if norm_ax < 1e-6:
                axis_vec = np.array([0.0, 0.0, 1.0])
            else:
                axis_vec = axis_vec / norm_ax
        else:
            axis_vec = np.array([0.0, 0.0, 1.0])

        # Rotation matrix aligning axis_vec to [0, 0, 1]
        z_target = np.array([0.0, 0.0, 1.0])
        v_cross = np.cross(axis_vec, z_target)
        s = np.linalg.norm(v_cross)
        c = np.dot(axis_vec, z_target)

        if s < 1e-8:
            if c < 0.0:
                # 180 degree flip
                rot_mat = np.array([[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]])
            else:
                rot_mat = np.eye(3)
        else:
            vx = np.array([
                [0, -v_cross[2], v_cross[1]],
                [v_cross[2], 0, -v_cross[0]],
                [-v_cross[1], v_cross[0], 0],
            ])
            rot_mat = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s**2))

        pivoted = centered @ rot_mat.T

        # 2D cylindrical projection (r, z)
        r_cyl = np.sqrt(pivoted[:, 0]**2 + pivoted[:, 1]**2)
        z_cyl = pivoted[:, 2]
        cylindrical = np.column_stack((r_cyl, z_cyl))

        return CartesianProtectionResult(
            is_linear=True,
            collinear_axis="Z",
            angle_deviation_deg=max_angle_dev,
            original_coordinates=coords,
            pivoted_coordinates=pivoted,
            cylindrical_coordinates=cylindrical,
            applied_protection=True,
            metadata={
                "pivoted_axis": "Z",
                "axis_vector": axis_vec.tolist(),
                "rotation_matrix": rot_mat.tolist(),
            },
        )

    return CartesianProtectionResult(
        is_linear=False,
        collinear_axis=None,
        angle_deviation_deg=max_angle_dev,
        original_coordinates=coords,
        pivoted_coordinates=coords,
        cylindrical_coordinates=None,
        applied_protection=False,
        metadata={"linearity": "non_linear_asymmetric_or_symmetric_top"},
    )


def dynamic_representation_switch(
    a_mhz: float,
    b_mhz: float,
    c_mhz: float,
    threshold: float = 1e-4,
) -> RepresentationSwitchResult:
    """Automatically analyzes Ray's asymmetry parameter and seamlessly shifts between standard representations.

    Ray's asymmetry parameter: kappa = (2B - A - C) / (A - C).
    - Prolate limit (kappa = -1): representation I^r (x=b, y=c, z=a)
    - Oblate limit (kappa = +1): representation III^r (x=a, y=b, z=c)

    Args:
        a_mhz: Rotational constant A in MHz.
        b_mhz: Rotational constant B in MHz.
        c_mhz: Rotational constant C in MHz.
        threshold: Tolerance threshold for degeneracy / spherical top classification.

    Returns:
        RepresentationSwitchResult with recommended representation, kappa, rotor classification, and axis mappings.
    """
    # Guard against linear rotor with A -> inf
    if math.isinf(a_mhz) or a_mhz > 1e12:
        return RepresentationSwitchResult(
            ray_kappa=-1.0,
            recommended_representation="Ir",
            rotor_type="linear",
            axis_mapping={"x": "b", "y": "c", "z": "a"},
            wang_subblocks={"E+": "symmetric", "E-": "antisymmetric"},
            is_prolate=True,
            is_oblate=False,
            description="Linear rotor with infinite A-constant; defaulting to I^r representation.",
        )

    # Check spherical top: A ~ B ~ C
    if abs(a_mhz - b_mhz) < threshold and abs(b_mhz - c_mhz) < threshold:
        return RepresentationSwitchResult(
            ray_kappa=0.0,
            recommended_representation="Ir",
            rotor_type="spherical_top",
            axis_mapping={"x": "b", "y": "c", "z": "a"},
            wang_subblocks={"A1": "spherical_isotropic"},
            is_prolate=False,
            is_oblate=False,
            description="Spherical top (A = B = C); isotropic rotational symmetry.",
        )

    denom = a_mhz - c_mhz
    if denom <= 0.0:
        kappa = 0.0
    else:
        kappa = (2.0 * b_mhz - a_mhz - c_mhz) / denom

    kappa = float(np.clip(kappa, -1.0, 1.0))

    if abs(b_mhz - c_mhz) < threshold or kappa <= -0.99999:
        rotor_type = "prolate_symmetric"
        recommended = "Ir"
        axis_mapping = {"x": "b", "y": "c", "z": "a"}
        desc = "Prolate symmetric top (B = C, kappa = -1); I^r representation optimal."
        is_prolate = True
        is_oblate = False
    elif abs(a_mhz - b_mhz) < threshold or kappa >= 0.99999:
        rotor_type = "oblate_symmetric"
        recommended = "IIIr"
        axis_mapping = {"x": "a", "y": "b", "z": "c"}
        desc = "Oblate symmetric top (A = B, kappa = +1); III^r representation optimal."
        is_prolate = False
        is_oblate = True
    elif kappa < 0.0:
        rotor_type = "prolate_asymmetric"
        recommended = "Ir"
        axis_mapping = {"x": "b", "y": "c", "z": "a"}
        desc = f"Prolate asymmetric top (kappa = {kappa:.4f} < 0); I^r representation selected."
        is_prolate = True
        is_oblate = False
    else:
        rotor_type = "oblate_asymmetric"
        recommended = "IIIr"
        axis_mapping = {"x": "a", "y": "b", "z": "c"}
        desc = f"Oblate asymmetric top (kappa = {kappa:.4f} >= 0); III^r representation selected."
        is_prolate = False
        is_oblate = True

    wang_blocks = {
        "E+": "Even-J, Even-Ka/Kc (A-type)",
        "E-": "Even-J, Odd-Ka/Kc (B-type)",
        "O+": "Odd-J, Even-Ka/Kc (C-type)",
        "O-": "Odd-J, Odd-Ka/Kc (Hybrid)",
    }

    return RepresentationSwitchResult(
        ray_kappa=kappa,
        recommended_representation=recommended,
        rotor_type=rotor_type,
        axis_mapping=axis_mapping,
        wang_subblocks=wang_blocks,
        is_prolate=is_prolate,
        is_oblate=is_oblate,
        description=desc,
    )


def diagonalize_inertia_tensor(
    coordinates: Union[np.ndarray, Sequence[Sequence[float]]],
    masses_or_symbols: Union[Sequence[str], Sequence[float]],
    unit: str = "MHz",
    apply_protection: bool = True,
    angle_threshold_deg: float = 175.0,
) -> InertiaTensorResult:
    """Constructs moment of inertia tensor, diagonalizes it, and extracts rotational constants.

    Uses exact CODATA 2022 constants and CIAAW mono-isotopic masses.
    Coordinates must be in Angstroms, masses in amu.

    Args:
        coordinates: (N, 3) Cartesian coordinates in Angstroms.
        masses_or_symbols: Sequence of atom masses (float) or element symbols (str).
        unit: Unit of rotational constants ('MHz', 'GHz', or 'cm-1').
        apply_protection: If True, applies Cartesian linear protections.
        angle_threshold_deg: Threshold for collinearity protection.

    Returns:
        InertiaTensorResult with principal moments, rotational constants, principal axes, COM, and symmetry.
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 3:
        raise CoChemIntegrityError(
            message=f"Coordinates must have shape (N, 3), got {coords.shape}",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    num_atoms = coords.shape[0]
    if len(masses_or_symbols) != num_atoms:
        raise CoChemIntegrityError(
            message=f"Number of masses/symbols ({len(masses_or_symbols)}) does not match atom count ({num_atoms})",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    masses = np.array([resolve_atomic_mass(m) for m in masses_or_symbols], dtype=np.float64)
    total_mass = float(np.sum(masses))

    # Center of mass translation
    centered_coords, com = translate_to_center_of_mass(coords, masses)

    # Cartesian protection check
    if apply_protection:
        prot_res = apply_cartesian_protections(
            coordinates=coords,
            masses_or_symbols=masses_or_symbols,
            angle_threshold_deg=angle_threshold_deg,
        )
    else:
        prot_res = CartesianProtectionResult(
            is_linear=False,
            collinear_axis=None,
            angle_deviation_deg=0.0,
            original_coordinates=coords,
            pivoted_coordinates=coords,
            applied_protection=False,
        )

    # Build raw inertia tensor
    raw_tensor = build_inertia_tensor(centered_coords, masses)

    # Diagonalize Hermitian/symmetric inertia tensor
    eigvals, eigvecs = np.linalg.eigh(raw_tensor)

    # Ensure strictly non-negative eigenvalues
    eigvals = np.maximum(0.0, eigvals)

    # Sort eigenvalues in ascending order I_a <= I_b <= I_c
    sort_idx = np.argsort(eigvals)
    sorted_eigvals = eigvals[sort_idx]
    sorted_eigvecs = eigvecs[:, sort_idx]

    i_a = float(sorted_eigvals[0])
    i_b = float(sorted_eigvals[1])
    i_c = float(sorted_eigvals[2])

    is_linear = bool(prot_res.is_linear or (i_a < 1e-4) or (i_a / max(1e-12, i_c) < 1e-4))

    # Calculate rotational constants
    if is_linear:
        a_mhz = float("inf")
        b_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / max(1e-12, i_b)
        c_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / max(1e-12, i_c)

        a_ghz = float("inf")
        b_ghz = INERTIA_CONVERSION_AMU_ANG2_GHZ / max(1e-12, i_b)
        c_ghz = INERTIA_CONVERSION_AMU_ANG2_GHZ / max(1e-12, i_c)

        a_cm1 = float("inf")
        b_cm1 = INERTIA_CONVERSION_AMU_ANG2_CM1 / max(1e-12, i_b)
        c_cm1 = INERTIA_CONVERSION_AMU_ANG2_CM1 / max(1e-12, i_c)
    else:
        a_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / max(1e-12, i_a)
        b_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / max(1e-12, i_b)
        c_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / max(1e-12, i_c)

        a_ghz = INERTIA_CONVERSION_AMU_ANG2_GHZ / max(1e-12, i_a)
        b_ghz = INERTIA_CONVERSION_AMU_ANG2_GHZ / max(1e-12, i_b)
        c_ghz = INERTIA_CONVERSION_AMU_ANG2_GHZ / max(1e-12, i_c)

        a_cm1 = INERTIA_CONVERSION_AMU_ANG2_CM1 / max(1e-12, i_a)
        b_cm1 = INERTIA_CONVERSION_AMU_ANG2_CM1 / max(1e-12, i_b)
        c_cm1 = INERTIA_CONVERSION_AMU_ANG2_CM1 / max(1e-12, i_c)

    # Planar moments: P_g = 1/2 (sum I - 2 I_g)
    p_a = 0.5 * (i_b + i_c - i_a)
    p_b = 0.5 * (i_a + i_c - i_b)
    p_c = 0.5 * (i_a + i_b - i_c)

    # Inertial defect: Delta = I_c - I_a - I_b
    inertial_defect = i_c - i_a - i_b
    is_planar = bool(abs(inertial_defect) < 0.1 and not is_linear)

    # Dynamic representation switch
    rep_res = dynamic_representation_switch(a_mhz, b_mhz, c_mhz)

    moments_dict = {"I_a": i_a, "I_b": i_b, "I_c": i_c}
    rot_mhz = {"A": a_mhz, "B": b_mhz, "C": c_mhz}
    rot_ghz = {"A": a_ghz, "B": b_ghz, "C": c_ghz}
    rot_cm1 = {"A": a_cm1, "B": b_cm1, "C": c_cm1}
    planar_dict = {"P_a": float(p_a), "P_b": float(p_b), "P_c": float(p_c)}

    return InertiaTensorResult(
        moments_of_inertia_amu_ang2=moments_dict,
        rotational_constants_mhz=rot_mhz,
        rotational_constants_ghz=rot_ghz,
        rotational_constants_cm1=rot_cm1,
        principal_axes=sorted_eigvecs,
        center_of_mass=com,
        total_mass_amu=total_mass,
        planar_moments_amu_ang2=planar_dict,
        inertial_defect_amu_ang2=float(inertial_defect),
        ray_asymmetry_kappa=rep_res.ray_kappa,
        rotor_type=rep_res.rotor_type,
        representation=rep_res,
        cartesian_protection=prot_res,
        is_linear=is_linear,
        is_planar=is_planar,
        raw_inertia_matrix=raw_tensor,
    )


# =============================================================================
# 5. TorqTensorExtractor Production Engine Class
# =============================================================================

class TorqTensorExtractor:
    """Production Moment of Inertia Tensor and Rotational Constant Extractor.

    Encapsulates geometry parsing, atomic mass resolution, center-of-mass alignment,
    Cartesian protections for linear rotor singularities, matrix diagonalization,
    and dynamic representation switching.
    """

    def __init__(
        self,
        coordinates: Union[np.ndarray, Sequence[Sequence[float]], pd.DataFrame],
        symbols: Optional[Sequence[str]] = None,
        masses: Optional[Sequence[float]] = None,
        unit: str = "MHz",
        angle_threshold_deg: float = 175.0,
    ) -> None:
        """Initialize TorqTensorExtractor.

        Args:
            coordinates: (N, 3) coordinate array, list of tuples, or DataFrame.
            symbols: Optional list of atomic element symbols (e.g. ['O', 'H', 'H']).
            masses: Optional list of numerical masses in amu.
            unit: Output unit ('MHz', 'GHz', or 'cm-1').
            angle_threshold_deg: Angle threshold for collinear protection.
        """
        if isinstance(coordinates, pd.DataFrame):
            # Extract coordinates and symbols from DataFrame if present
            col_names = [str(c).lower() for c in coordinates.columns]
            if "x" in col_names and "y" in col_names and "z" in col_names:
                coords_np = coordinates[["x", "y", "z"]].to_numpy(dtype=np.float64)
            else:
                coords_np = coordinates.iloc[:, :3].to_numpy(dtype=np.float64)

            if symbols is None and ("symbol" in col_names or "element" in col_names):
                sym_col = "symbol" if "symbol" in col_names else "element"
                symbols = coordinates[sym_col].tolist()
            self._coordinates = coords_np
        else:
            self._coordinates = np.asarray(coordinates, dtype=np.float64)

        num_atoms = self._coordinates.shape[0]

        if masses is not None:
            self._masses = [float(m) for m in masses]
            self._symbols = list(symbols) if symbols is not None else [f"X{i}" for i in range(num_atoms)]
        elif symbols is not None:
            self._symbols = [str(s).strip() for s in symbols]
            self._masses = [resolve_atomic_mass(s) for s in self._symbols]
        else:
            self._symbols = ["C"] * num_atoms
            self._masses = [12.0] * num_atoms

        self._unit = unit
        self._angle_threshold = angle_threshold_deg
        self._result: Optional[InertiaTensorResult] = None

    def extract(self) -> InertiaTensorResult:
        """Execute extraction and return comprehensive InertiaTensorResult."""
        if self._result is None:
            self._result = diagonalize_inertia_tensor(
                coordinates=self._coordinates,
                masses_or_symbols=self._masses,
                unit=self._unit,
                apply_protection=True,
                angle_threshold_deg=self._angle_threshold,
            )
        return self._result

    def get_rotational_constants(self, unit: Optional[str] = None) -> Dict[str, float]:
        """Return rotational constants in requested unit (default: self._unit)."""
        res = self.extract()
        target_u = unit if unit is not None else self._unit
        if target_u.lower() == "ghz":
            return res.rotational_constants_ghz
        elif target_u.lower() in ("cm-1", "cm_1", "wavenumbers"):
            return res.rotational_constants_cm1
        return res.rotational_constants_mhz

    def get_moments_of_inertia(self) -> Dict[str, float]:
        """Return principal moments of inertia in amu * Angstrom^2."""
        return self.extract().moments_of_inertia_amu_ang2

    def get_planar_moments(self) -> Dict[str, float]:
        """Return planar moments P_a, P_b, P_c in amu * Angstrom^2."""
        return self.extract().planar_moments_amu_ang2

    def get_inertial_defect(self) -> float:
        """Return inertial defect Delta = I_c - I_a - I_b in amu * Angstrom^2."""
        return self.extract().inertial_defect_amu_ang2

    def get_ray_asymmetry(self) -> float:
        """Return Ray's asymmetry parameter kappa."""
        return self.extract().ray_asymmetry_kappa

    def get_representation(self) -> RepresentationSwitchResult:
        """Return dynamic representation switch analysis."""
        return self.extract().representation

    def get_principal_axes(self) -> np.ndarray:
        """Return 3x3 principal axes transformation matrix."""
        return self.extract().principal_axes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete extraction result to dictionary."""
        return self.extract().to_dict()

    def to_json(self, filepath: Optional[Union[str, Path]] = None, indent: int = 2) -> str:
        """Serialize extraction result to JSON string and optionally save to file."""
        data = self.to_dict()
        json_str = json.dumps(data, indent=indent)
        if filepath is not None:
            p = Path(filepath).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        return json_str

    def to_dataframe(self) -> pd.DataFrame:
        """Convert principal inertia parameters to a single-row Pandas DataFrame."""
        d = self.to_dict()
        flat_record = {
            "I_a": d["moments_of_inertia_amu_ang2"]["I_a"],
            "I_b": d["moments_of_inertia_amu_ang2"]["I_b"],
            "I_c": d["moments_of_inertia_amu_ang2"]["I_c"],
            "A_MHz": d["rotational_constants_mhz"]["A"],
            "B_MHz": d["rotational_constants_mhz"]["B"],
            "C_MHz": d["rotational_constants_mhz"]["C"],
            "P_a": d["planar_moments_amu_ang2"]["P_a"],
            "P_b": d["planar_moments_amu_ang2"]["P_b"],
            "P_c": d["planar_moments_amu_ang2"]["P_c"],
            "inertial_defect": d["inertial_defect_amu_ang2"],
            "ray_kappa": d["ray_asymmetry_kappa"],
            "rotor_type": d["rotor_type"],
            "representation": d["representation"]["recommended_representation"],
            "is_linear": d["is_linear"],
            "is_planar": d["is_planar"],
            "total_mass": d["total_mass_amu"],
        }
        return pd.DataFrame([flat_record])


__all__ = [
    "AMU_KG",
    "CIAAW_ISOTOPIC_MASSES",
    "CartesianProtectionResult",
    "INERTIA_CONVERSION_AMU_ANG2_CM1",
    "INERTIA_CONVERSION_AMU_ANG2_GHZ",
    "INERTIA_CONVERSION_AMU_ANG2_MHZ",
    "InertiaTensorResult",
    "PLANCK_H",
    "RepresentationSwitchResult",
    "SPEED_OF_LIGHT_CM_S",
    "TorqTensorExtractor",
    "apply_cartesian_protections",
    "build_inertia_tensor",
    "calculate_center_of_mass",
    "diagonalize_inertia_tensor",
    "dynamic_representation_switch",
    "resolve_atomic_mass",
    "translate_to_center_of_mass",
]
