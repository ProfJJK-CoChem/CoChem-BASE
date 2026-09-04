#!/usr/bin/env python3
"""CoChem-TOPOS Alignment Engine: Legacy PAF & Dual-Frame Eckart Spectroscopic Alignment.

Module: intake/topos_alignment.py
Ecosystem Role: Legacy Principal Axis Frame (PAF) alignment script referenced in
                SRS Document 2 Rectification Matrix; superseded by
                intake/cochem_topos_alignment.py for Dual-Frame Eckart alignment.
                Maintains full backward compatibility for legacy PAF invocations,
                direct CLI execution, and re-exports canonical symbols from
                intake.cochem_topos_alignment.

Authoritative Standards:
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\Method_Matrix.md (v4 Sections 3, 4, 8B, 9B, 12-14)
- D:\\__CoChem\\GitHub-Repo\\CoChem-BASE\\CoChem_User_Manual.md
- NIST CODATA 2022 / 2026 Fundamental Physical Constants
"""

from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import mendeleev
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# Ensure repository root and intake directory are in sys.path
_current_dir = Path(__file__).resolve().parent
_repo_dir = _current_dir.parent
if str(_repo_dir) not in sys.path:
    sys.path.insert(0, str(_repo_dir))
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

try:
    from cochem_topos.topology import AtomModel
except ImportError:
    AtomModel = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-ToposAlignment-Legacy")


# ==============================================================================
# NIST CODATA 2022 / 2026 Fundamental Physical Constants & Conversion Factors
# ==============================================================================

PLANCK_H: float = 6.62607015e-34          # J * s (exact SI standard)
SPEED_OF_LIGHT_C: float = 299792458.0     # m / s (exact SI standard)
ATOMIC_MASS_UNIT_U: float = 1.66053906892e-27  # kg / u (CODATA 2022/2026)
ANGSTROM_TO_M: float = 1.0e-10            # m / Angstrom

# Conversion factor: factor_hz / I(amu * A^2) = B (Hz)
# B = h / (8 * pi^2 * I)
FACTOR_HZ: float = PLANCK_H / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_U * (ANGSTROM_TO_M ** 2))
FACTOR_MHZ: float = FACTOR_HZ / 1.0e6
FACTOR_GHZ: float = FACTOR_HZ / 1.0e9
FACTOR_CM1: float = FACTOR_HZ / (SPEED_OF_LIGHT_C * 100.0)


# ==============================================================================
# Ghost Atom & Atomic Weight Resolution Helpers
# ==============================================================================

def is_ghost_symbol(symbol: str) -> bool:
    """Checks whether an atomic element symbol represents a ghost atom.

    Ghost atoms (e.g., 'Gh', 'gh', 'GhO', 'Gh_C', 'X', 'x_N', 'Bq') possess
    strictly 0.0 mass to avoid shifting the Center of Mass during BSSE counterpoise
    calculations. Chemical elements like Xenon ('Xe', 'xe') are NOT ghost atoms.

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
    clean = symbol.strip().lower()
    if clean.startswith("gh") or clean.startswith("bq") or clean == "bq":
        return True
    if clean == "x" or clean.startswith("x_") or clean.startswith("x-") or clean.startswith("x:"):
        return True
    if clean.startswith("x") and not clean.startswith("xe"):
        return True
    return False


def get_physical_mass(symbol: str) -> float:
    """Retrieves authentic standard atomic weight from mendeleev.

    Ghost atoms strictly return 0.0.

    Parameters
    ----------
    symbol : str
        Chemical element or ghost symbol.

    Returns
    -------
    float
        Standard atomic mass in unified atomic mass units (u / Da).

    Raises
    ------
    ValueError
        If the symbol is empty, unrecognized, or invalid.
    """
    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("[MISSING DATA] Atomic symbol cannot be empty.")

    clean = symbol.strip()
    if is_ghost_symbol(clean):
        return 0.0

    # Standard Mendeleev lookup
    try:
        elem = mendeleev.element(clean)
        if elem is not None and elem.mass is not None:
            return float(elem.mass)
    except Exception:
        import re
        match = re.match(r"^([A-Z][a-z]?)", clean)
        if match:
            try:
                elem = mendeleev.element(match.group(1))
                if elem is not None and elem.mass is not None:
                    return float(elem.mass)
            except Exception as _e:
                logger.debug(f"Ignored exception: {_e}")

    raise ValueError(f"[INVALID DATA] Unrecognized chemical element symbol: '{symbol}'.")


def resolve_atomic_masses(
    coords: np.ndarray,
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Resolves and validates atomic masses array matching given coordinates.

    Parameters
    ----------
    coords : np.ndarray
        Array of Cartesian coordinates of shape (N, 3).
    masses : Sequence[float] | np.ndarray, optional
        Pre-computed atomic masses.
    symbols : Sequence[str], optional
        Sequence of element symbols corresponding to each coordinate.

    Returns
    -------
    np.ndarray
        1D float64 array of atomic masses of shape (N,).

    Raises
    ------
    ValueError
        If dimensions mismatch, negative masses exist, or total non-ghost mass is <= 0.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    n_atoms = len(coords_arr)

    if masses is not None:
        masses_arr = np.asarray(masses, dtype=np.float64)
        if masses_arr.shape != (n_atoms,):
            raise ValueError(
                f"[DIMENSION MISMATCH] Coordinate count ({n_atoms}) does not match masses shape {masses_arr.shape}."
            )
        if np.any(masses_arr < 0.0):
            raise ValueError("[PHYSICAL ERROR] Atomic masses must be non-negative positive values.")
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise ValueError("[PHYSICAL ERROR] Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    if symbols is not None:
        if len(symbols) != n_atoms:
            raise ValueError(
                f"[DIMENSION MISMATCH] Coordinate count ({n_atoms}) does not match symbols count ({len(symbols)})."
            )
        masses_list = [get_physical_mass(s) for s in symbols]
        masses_arr = np.array(masses_list, dtype=np.float64)
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise ValueError("[PHYSICAL ERROR] Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    raise ValueError("[MISSING DATA] Either 'masses' or 'symbols' must be provided to determine molecular mass.")


# ==============================================================================
# 1. Center of Mass Translation Engine
# ==============================================================================

def compute_center_of_mass(
    coords: np.ndarray,
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """Computes the mass-weighted Center of Mass (COM) vector for a molecular system.

    Ghost atoms (mass = 0.0) are completely excluded from the mass weighting.

    Parameters
    ----------
    coords : np.ndarray
        Array of shape (N, 3) representing Cartesian coordinates in Angstroms.
    masses : Sequence[float] | np.ndarray, optional
        1D array of atomic masses in amu.
    symbols : Sequence[str], optional
        Sequence of atomic symbols.

    Returns
    -------
    np.ndarray
        1D float64 array of shape (3,) representing the Center of Mass vector.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ValueError(f"[INVALID SHAPE] Expected coordinates shape (N, 3), got {coords_arr.shape}.")

    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = np.sum(masses_arr)

    com = np.sum(coords_arr * masses_arr[:, np.newaxis], axis=0) / total_mass
    return com


def translate_to_center_of_mass(
    coords: np.ndarray,
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Translates molecular coordinates such that the Center of Mass is at (0, 0, 0).

    All atoms (including ghost atoms) undergo the identical translational shift.

    Parameters
    ----------
    coords : np.ndarray
        Array of shape (N, 3) representing Cartesian coordinates.
    masses : Sequence[float] | np.ndarray, optional
        Atomic masses in amu.
    symbols : Sequence[str], optional
        Atomic element symbols.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        A tuple of (translated_coords, shift_vector) where shift_vector = -COM.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = np.sum(masses_arr)

    com = compute_center_of_mass(coords_arr, masses=masses_arr)
    shift_vec = -com
    translated_coords = coords_arr + shift_vec

    # Iterative refinement to eliminate residual floating point precision drift
    residual = np.sum(masses_arr[:, np.newaxis] * translated_coords, axis=0) / total_mass
    if np.any(np.abs(residual) > 0.0):
        translated_coords = translated_coords - residual
        shift_vec = shift_vec - residual

    return translated_coords, shift_vec


class CenterOfMassTranslator:
    """High-level object-oriented interface for Center of Mass computations."""

    @staticmethod
    def compute_center_of_mass(
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> np.ndarray:
        """Computes the mass-weighted Center of Mass vector (3,)."""
        return compute_center_of_mass(coords, masses=masses, symbols=symbols)

    @staticmethod
    def translate(
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Translates coordinates such that COM is at origin (0, 0, 0)."""
        return translate_to_center_of_mass(coords, masses=masses, symbols=symbols)


# ==============================================================================
# 2. Moment of Inertia Tensor & Spectroscopic Top Engine (PAF)
# ==============================================================================

class InertiaTensorResult(BaseModel):
    """Pydantic model containing detailed principal moment of inertia results."""
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
    top_type: str = Field(
        ..., description="Rotor classification: asymmetric_top, oblate_symmetric_top, prolate_symmetric_top, spherical_top, linear"
    )
    rotation_matrix: Any = Field(
        ..., description="Right-handed 3x3 rotation matrix V diagonalizing inertia tensor with det = +1.0"
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


class MomentOfInertiaEngine:
    """Moment of Inertia Tensor Construction, Diagonalization, and Rotor Classification."""

    @staticmethod
    def compute_moment_of_inertia_tensor(coords: np.ndarray, masses: np.ndarray) -> np.ndarray:
        """Constructs the symmetric 3x3 Moment of Inertia tensor in amu * Angstrom^2.

        I_xx = sum(m_i * (y_i^2 + z_i^2))
        I_xy = -sum(m_i * x_i * y_i)

        Parameters
        ----------
        coords : np.ndarray
            COM-centered coordinates of shape (N, 3).
        masses : np.ndarray
            Atomic masses of shape (N,).

        Returns
        -------
        np.ndarray
            Symmetric 3x3 float64 moment of inertia tensor.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        masses_arr = np.asarray(masses, dtype=np.float64)

        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise ValueError(f"[INVALID SHAPE] Coordinates must have shape (N, 3), got {coords_arr.shape}.")
        if masses_arr.shape != (len(coords_arr),):
            raise ValueError(
                f"[DIMENSION MISMATCH] Masses length ({len(masses_arr)}) != atom count ({len(coords_arr)})."
            )

        x = coords_arr[:, 0]
        y = coords_arr[:, 1]
        z = coords_arr[:, 2]

        Ixx = np.sum(masses_arr * (y**2 + z**2))
        Iyy = np.sum(masses_arr * (x**2 + z**2))
        Izz = np.sum(masses_arr * (x**2 + y**2))
        Ixy = -np.sum(masses_arr * x * y)
        Ixz = -np.sum(masses_arr * x * z)
        Iyz = -np.sum(masses_arr * y * z)

        tensor = np.array([
            [Ixx, Ixy, Ixz],
            [Ixy, Iyy, Iyz],
            [Ixz, Iyz, Izz],
        ], dtype=np.float64)
        return tensor

    @staticmethod
    def diagonalize_inertia_tensor(inertia_tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Diagonalizes 3x3 inertia tensor to yield sorted eigenvalues Ia <= Ib <= Ic and right-handed V.

        Parameters
        ----------
        inertia_tensor : np.ndarray
            Symmetric 3x3 inertia tensor.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            (eigenvalues, V) where eigenvalues has shape (3,) and V has shape (3, 3) with det(V) = +1.0.
        """
        tensor = np.asarray(inertia_tensor, dtype=np.float64)
        if tensor.shape != (3, 3):
            raise ValueError(f"[INVALID SHAPE] Inertia tensor must be (3, 3), got {tensor.shape}.")

        eigvals, V = np.linalg.eigh(tensor)

        # Sort explicitly in ascending order
        idx = np.argsort(eigvals)
        eigvals = eigvals[idx]
        V = V[:, idx]

        # Enforce right-handed coordinate frame: if det(V) < 0, negate the third column
        det_v = np.linalg.det(V)
        if det_v < 0.0:
            V[:, 2] = -V[:, 2]

        return eigvals, V

    def align_to_principal_axes(
        self,
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> InertiaTensorResult:
        """Translates to COM, diagonalizes inertia tensor, and derives spectroscopic rotor parameters.

        Parameters
        ----------
        coords : np.ndarray
            Array of shape (N, 3) with Cartesian coordinates.
        masses : Sequence[float] | np.ndarray, optional
            Atomic masses.
        symbols : Sequence[str], optional
            Atomic symbols.

        Returns
        -------
        InertiaTensorResult
            Structured result containing aligned coordinates, principal moments, rotational constants, and rotor type.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)

        coords_com, _ = translate_to_center_of_mass(coords_arr, masses=masses_arr)
        I_tensor = self.compute_moment_of_inertia_tensor(coords_com, masses_arr)
        eigvals, V = self.diagonalize_inertia_tensor(I_tensor)

        Ia, Ib, Ic = float(eigvals[0]), float(eigvals[1]), float(eigvals[2])

        # Aligned coordinates in principal axis frame
        aligned_coords = coords_com @ V

        # Calculate rotational constants A, B, C
        if Ia < 1e-8:
            A_mhz = float("inf")
            A_ghz = float("inf")
            A_cm1 = float("inf")
        else:
            A_mhz = FACTOR_MHZ / Ia
            A_ghz = FACTOR_GHZ / Ia
            A_cm1 = FACTOR_CM1 / Ia

        if Ib < 1e-8:
            B_mhz = float("inf")
            B_ghz = float("inf")
            B_cm1 = float("inf")
        else:
            B_mhz = FACTOR_MHZ / Ib
            B_ghz = FACTOR_GHZ / Ib
            B_cm1 = FACTOR_CM1 / Ib

        if Ic < 1e-8:
            C_mhz = float("inf")
            C_ghz = float("inf")
            C_cm1 = float("inf")
        else:
            C_mhz = FACTOR_MHZ / Ic
            C_ghz = FACTOR_GHZ / Ic
            C_cm1 = FACTOR_CM1 / Ic

        rot_mhz = (A_mhz, B_mhz, C_mhz)
        rot_ghz = (A_ghz, B_ghz, C_ghz)
        rot_cm1 = (A_cm1, B_cm1, C_cm1)

        # Inertial defect: Delta = Ic - Ia - Ib (Method Matrix v4 Step 4)
        inertial_defect = float(Ic - Ia - Ib)

        # Planar moments: Pa = (-Ia + Ib + Ic)/2, Pb = (Ia - Ib + Ic)/2, Pc = (Ia + Ib - Ic)/2
        Pa = float((-Ia + Ib + Ic) / 2.0)
        Pb = float((Ia - Ib + Ic) / 2.0)
        Pc = float((Ia + Ib - Ic) / 2.0)
        planar_moments = (Pa, Pb, Pc)

        # Rotor classification
        if Ia < 1e-8 or (Ib > 1e-8 and (Ia / Ib) < 1e-4):
            top_type = "linear"
            rays_kappa = -1.0
        elif Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and (abs(Ib - Ic) / Ic < 1e-3):
            top_type = "spherical_top"
            rays_kappa = 0.0
        elif Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and ((Ic - Ib) / Ib >= 1e-3):
            top_type = "oblate_symmetric_top"
            rays_kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz) if (A_mhz - C_mhz) != 0 else 1.0
        elif Ic > 1e-8 and (abs(Ib - Ic) / Ic < 1e-3) and ((Ib - Ia) / Ib >= 1e-3):
            top_type = "prolate_symmetric_top"
            rays_kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz) if (A_mhz - C_mhz) != 0 else -1.0
        else:
            top_type = "asymmetric_top"
            if math.isinf(A_mhz) or abs(A_mhz - C_mhz) < 1e-12:
                rays_kappa = -1.0 if math.isinf(A_mhz) else 0.0
            else:
                rays_kappa = float((2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz))

        return InertiaTensorResult(
            eigenvalues_amu_angstrom2=(Ia, Ib, Ic),
            rotational_constants_mhz=rot_mhz,
            rotational_constants_ghz=rot_ghz,
            rotational_constants_cm1=rot_cm1,
            inertial_defect=inertial_defect,
            rays_kappa=rays_kappa,
            planar_moments=planar_moments,
            top_type=top_type,
            rotation_matrix=V,
            aligned_coords=aligned_coords,
            inertia_tensor=I_tensor,
        )


# ==============================================================================
# 3. Legacy PAF Alignment Engine (Sign-Permutation & Conformer Matching)
# ==============================================================================

class PAFAlignmentResult(BaseModel):
    """Pydantic model containing legacy Principal Axis Frame alignment results."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    aligned_coords: Any = Field(..., description="PAF-aligned Cartesian coordinates (N, 3)")
    rotation_matrix: Any = Field(..., description="Proper rotation matrix (3, 3) in SO(3)")
    eigenvalues_amu_angstrom2: Tuple[float, float, float] = Field(..., description="Principal moments Ia <= Ib <= Ic")
    rotational_constants_mhz: Tuple[float, float, float] = Field(..., description="Rotational constants (A, B, C) in MHz")
    top_type: str = Field(..., description="Rotor classification")
    inertial_defect: float = Field(..., description="Inertial defect Delta in amu * Angstrom^2")
    rays_kappa: float = Field(..., description="Ray's asymmetry parameter kappa")
    rmsd_to_reference: Optional[float] = Field(None, description="RMSD to reference conformation if ref provided")

    @field_serializer("aligned_coords", "rotation_matrix", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


class LegacyPAFAligner:
    """Legacy Principal Axis Frame (PAF) Aligner.

    Performs Center-of-Mass translation, moment of inertia tensor construction,
    diagonalization, and optional sign permutation alignment across proper SO(3)
    rotations to minimize RMSD against reference structures.
    """

    def __init__(self) -> None:
        self.inertia_engine = MomentOfInertiaEngine()

    def align_single(
        self,
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> PAFAlignmentResult:
        """Aligns a single molecular geometry to its canonical Principal Axis Frame (PAF).

        Parameters
        ----------
        coords : np.ndarray
            Cartesian coordinates (N, 3).
        masses : Sequence[float] | np.ndarray, optional
            Atomic masses.
        symbols : Sequence[str], optional
            Atomic symbols.

        Returns
        -------
        PAFAlignmentResult
            Structured result containing PAF-aligned coordinates and spectroscopic parameters.
        """
        res = self.inertia_engine.align_to_principal_axes(coords, masses=masses, symbols=symbols)
        return PAFAlignmentResult(
            aligned_coords=res.aligned_coords,
            rotation_matrix=res.rotation_matrix,
            eigenvalues_amu_angstrom2=res.eigenvalues_amu_angstrom2,
            rotational_constants_mhz=res.rotational_constants_mhz,
            top_type=res.top_type,
            inertial_defect=res.inertial_defect,
            rays_kappa=res.rays_kappa,
            rmsd_to_reference=None,
        )

    def align_conformation_pair(
        self,
        target_coords: np.ndarray,
        ref_coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
    ) -> PAFAlignmentResult:
        """Aligns target coordinates to a reference conformation using the 4 proper SO(3) PAF sign permutations.

        Sign permutations:
        s in {(+1, +1, +1), (+1, -1, -1), (-1, +1, -1), (-1, -1, +1)}

        Parameters
        ----------
        target_coords : np.ndarray
            Target Cartesian coordinates (N, 3).
        ref_coords : np.ndarray
            Reference Cartesian coordinates (N, 3).
        masses : Sequence[float] | np.ndarray, optional
            Atomic masses.
        symbols : Sequence[str], optional
            Atomic symbols.

        Returns
        -------
        PAFAlignmentResult
            Optimal PAF alignment minimizing mass-weighted RMSD to reference.
        """
        target_arr = np.asarray(target_coords, dtype=np.float64)
        ref_arr = np.asarray(ref_coords, dtype=np.float64)
        masses_arr = resolve_atomic_masses(target_arr, masses=masses, symbols=symbols)
        total_mass = np.sum(masses_arr)

        # Center both at COM
        target_com, _ = translate_to_center_of_mass(target_arr, masses=masses_arr)
        ref_com, _ = translate_to_center_of_mass(ref_arr, masses=masses_arr)

        # Compute PAF frames
        I_target = self.inertia_engine.compute_moment_of_inertia_tensor(target_com, masses_arr)
        eig_target, V_target = self.inertia_engine.diagonalize_inertia_tensor(I_target)

        I_ref = self.inertia_engine.compute_moment_of_inertia_tensor(ref_com, masses_arr)
        eig_ref, V_ref = self.inertia_engine.diagonalize_inertia_tensor(I_ref)

        ref_paf = ref_com @ V_ref

        # 4 proper SO(3) sign permutations preserving det = +1
        sign_permutations = [
            np.diag([1.0, 1.0, 1.0]),
            np.diag([1.0, -1.0, -1.0]),
            np.diag([-1.0, 1.0, -1.0]),
            np.diag([-1.0, -1.0, 1.0]),
        ]

        best_rmsd = float("inf")
        best_aligned = target_com @ V_target
        best_rot = V_target

        for S in sign_permutations:
            V_cand = V_target @ S
            cand_aligned = target_com @ V_cand
            diff = cand_aligned - ref_paf
            cand_rmsd = float(np.sqrt(np.sum(masses_arr * np.sum(diff**2, axis=-1)) / total_mass))
            if cand_rmsd < best_rmsd:
                best_rmsd = cand_rmsd
                best_aligned = cand_aligned
                best_rot = V_cand

        res = self.inertia_engine.align_to_principal_axes(target_arr, masses=masses_arr)
        return PAFAlignmentResult(
            aligned_coords=best_aligned,
            rotation_matrix=best_rot,
            eigenvalues_amu_angstrom2=res.eigenvalues_amu_angstrom2,
            rotational_constants_mhz=res.rotational_constants_mhz,
            top_type=res.top_type,
            inertial_defect=res.inertial_defect,
            rays_kappa=res.rays_kappa,
            rmsd_to_reference=best_rmsd,
        )


# Backward compatibility aliases
PAFAligner = LegacyPAFAligner
PAFAlignmentEngine = LegacyPAFAligner


# ==============================================================================
# 4. Eckart Frame Aligner Engine (Dual-Frame Eckart & Kabsch SVD)
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

    @field_serializer("aligned_coords", "rotation_matrix", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


class EckartFrameAligner:
    """Mass-weighted Eckart Frame Aligner satisfying translational and rotational Eckart conditions."""

    @staticmethod
    def align(
        target_coords: np.ndarray,
        ref_coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        tolerance: float = 1e-12,
    ) -> EckartAlignmentResult:
        """Aligns target coordinates to reference coordinates in mass-weighted Eckart frame.

        Solves the Kabsch / Eckart problem:
            min_U sum(m_i * || target_com_i @ U - ref_com_i ||^2)
        subject to U in SO(3) (det(U) = +1.0).

        Parameters
        ----------
        target_coords : np.ndarray
            Target Cartesian coordinates (N, 3).
        ref_coords : np.ndarray
            Reference Cartesian coordinates (N, 3).
        masses : Sequence[float] | np.ndarray, optional
            Atomic masses (N,).
        symbols : Sequence[str], optional
            Atomic symbols (N,).
        tolerance : float, default 1e-12
            Convergence tolerance for residuals.

        Returns
        -------
        EckartAlignmentResult
            Structured result containing aligned target coordinates, rotation matrix U, and Eckart residual norms.
        """
        target_arr = np.asarray(target_coords, dtype=np.float64)
        ref_arr = np.asarray(ref_coords, dtype=np.float64)

        if target_arr.shape != ref_arr.shape:
            raise ValueError(
                f"[DIMENSION MISMATCH] Target shape {target_arr.shape} does not match reference shape {ref_arr.shape}."
            )
        if target_arr.ndim != 2 or target_arr.shape[1] != 3:
            raise ValueError(f"[INVALID SHAPE] Coordinates must have shape (N, 3), got {target_arr.shape}.")

        masses_arr = resolve_atomic_masses(target_arr, masses=masses, symbols=symbols)
        total_mass = np.sum(masses_arr)

        # Center both conformations at their respective mass-weighted COM
        target_com, _ = translate_to_center_of_mass(target_arr, masses=masses_arr)
        ref_com, _ = translate_to_center_of_mass(ref_arr, masses=masses_arr)

        # Mass-weighted correlation matrix: F = target_com^T @ (diag(masses) @ ref_com)
        F = target_com.T @ (ref_com * masses_arr[:, np.newaxis])

        # SVD: F = V @ S @ Wt
        V, S, Wt = np.linalg.svd(F)

        # Proper rotation check to avoid reflections: d = det(V @ Wt)
        d = float(np.linalg.det(V @ Wt))
        diag = np.array([1.0, 1.0, 1.0 if d >= 0.0 else -1.0], dtype=np.float64)
        U = V @ np.diag(diag) @ Wt

        # Safeguard strictly det(U) = +1.0
        if np.linalg.det(U) < 0.0:
            U = V @ np.diag([1.0, 1.0, -1.0]) @ Wt

        # Aligned coordinates
        aligned_coords = target_com @ U

        # Translational Eckart condition residual: sum(m_i * r'_i) / M
        trans_res = float(np.linalg.norm(np.sum(masses_arr[:, np.newaxis] * aligned_coords, axis=0) / total_mass))

        # Rotational Eckart condition residual torque: sum(m_i * (ref_com x aligned_coords))
        rot_torque = np.sum(masses_arr[:, np.newaxis] * np.cross(ref_com, aligned_coords), axis=0)
        rot_res = float(np.linalg.norm(rot_torque))

        # Mass-weighted RMSD
        diff = aligned_coords - ref_com
        sq_dist = np.sum(diff**2, axis=-1)
        rmsd = float(np.sqrt(np.sum(masses_arr * sq_dist) / total_mass))

        return EckartAlignmentResult(
            aligned_coords=aligned_coords,
            rotation_matrix=U,
            rmsd=rmsd,
            residual_rotational_norm=rot_res,
            translational_residual_norm=trans_res,
        )


def align_to_eckart_frame(
    target_coords: np.ndarray,
    ref_coords: np.ndarray,
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
    tolerance: float = 1e-12,
) -> EckartAlignmentResult:
    """Convenience functional wrapper for mass-weighted Eckart frame alignment."""
    return EckartFrameAligner.align(
        target_coords=target_coords,
        ref_coords=ref_coords,
        masses=masses,
        symbols=symbols,
        tolerance=tolerance,
    )


# ==============================================================================
# 5. Vibrational Projector Engine
# ==============================================================================

class VibrationalProjector:
    """Constructs idempotent vibrational projection matrices P_vib and projects Cartesian/mass-weighted Hessians."""

    @staticmethod
    def construct_vibrational_projector(
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        is_linear: bool = False,
    ) -> np.ndarray:
        """Constructs (3N, 3N) mass-weighted vibrational projection operator P_vib = I - P_rigid.

        Properties:
        - Idempotent: P_vib @ P_vib = P_vib
        - Symmetric: P_vib^T = P_vib
        - Trace invariant: Tr(P_vib) = 3N - 6 (or 3N - 5 for linear molecules)

        Parameters
        ----------
        coords : np.ndarray
            Molecular coordinates (N, 3).
        masses : Sequence[float] | np.ndarray, optional
            Atomic masses in amu.
        symbols : Sequence[str], optional
            Atomic symbols.
        is_linear : bool, default False
            Whether the molecule is linear (5 rigid body modes instead of 6).

        Returns
        -------
        np.ndarray
            (3N, 3N) float64 vibrational projector matrix.
        """
        coords_arr = np.asarray(coords, dtype=np.float64)
        masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)
        coords_com, _ = translate_to_center_of_mass(coords_arr, masses=masses_arr)

        N = len(coords_com)
        total_mass = np.sum(masses_arr)
        sqrt_m = np.sqrt(masses_arr)

        # 3 mass-weighted translational basis vectors
        D_trans = np.array([[0.0, 0.0, 0.0] for _ in range(3 * N)], dtype=np.float64)
        for i in range(N):
            w = sqrt_m[i] / np.sqrt(total_mass)
            D_trans[3 * i, 0] = w
            D_trans[3 * i + 1, 1] = w
            D_trans[3 * i + 2, 2] = w

        # 3 mass-weighted rotational basis vectors
        D_rot = np.array([[0.0, 0.0, 0.0] for _ in range(3 * N)], dtype=np.float64)
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

        # SVD orthonormalization
        U_svd, _, _ = np.linalg.svd(D_rigid, full_matrices=False)
        k_rigid = 5 if is_linear else min(6, 3 * N)

        E_rigid = U_svd[:, :k_rigid]
        P_rigid = E_rigid @ E_rigid.T
        I_3N = np.array([[1.0 if i == j else 0.0 for j in range(3 * N)] for i in range(3 * N)], dtype=np.float64)
        P_vib = I_3N - P_rigid
        return P_vib

    def project_mass_weighted_hessian(
        self,
        H_mw: np.ndarray,
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        is_linear: bool = False,
    ) -> np.ndarray:
        """Projects mass-weighted Hessian H_mw (3N, 3N) removing 6 (or 5) rigid body translational/rotational modes.

        H_mw_proj = P_vib @ H_mw @ P_vib

        Parameters
        ----------
        H_mw : np.ndarray
            (3N, 3N) mass-weighted Hessian.
        coords : np.ndarray
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
        P_vib = self.construct_vibrational_projector(coords, masses=masses, symbols=symbols, is_linear=is_linear)
        return P_vib @ H_mw_arr @ P_vib

    def project_cartesian_hessian(
        self,
        H_cart: np.ndarray,
        coords: np.ndarray,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        symbols: Optional[Sequence[str]] = None,
        is_linear: bool = False,
    ) -> np.ndarray:
        """Projects Cartesian Hessian H_cart (3N, 3N) removing rigid body modes via mass-weighting and unweighting.

        Parameters
        ----------
        H_cart : np.ndarray
            (3N, 3N) Cartesian Hessian.
        coords : np.ndarray
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
        masses_arr = resolve_atomic_masses(coords, masses=masses, symbols=symbols)
        sqrt_m_3n = np.repeat(np.sqrt(masses_arr), 3)
        inv_sqrt_m = np.zeros_like(masses_arr)
        pos_mask = masses_arr > 0.0
        inv_sqrt_m[pos_mask] = 1.0 / np.sqrt(masses_arr[pos_mask])
        inv_sqrt_m_3n = np.repeat(inv_sqrt_m, 3)

        # Mass-weight Cartesian Hessian: H_mw = M^(-1/2) @ H_cart @ M^(-1/2)
        H_mw = H_cart_arr * np.outer(inv_sqrt_m_3n, inv_sqrt_m_3n)
        H_mw_proj = self.project_mass_weighted_hessian(H_mw, coords, masses=masses_arr, is_linear=is_linear)
        # Restore to Cartesian space: H_cart_proj = M^(1/2) @ H_mw_proj @ M^(1/2)
        H_cart_proj = H_mw_proj * np.outer(sqrt_m_3n, sqrt_m_3n)
        return H_cart_proj


# ==============================================================================
# 6. Unified Standardization Pipeline & ToposAlignmentResult
# ==============================================================================

class ToposAlignmentResult(BaseModel):
    """Unified result container for molecular topology standardization and alignment."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    aligned_coords: Any = Field(
        ..., description="Principal-axis aligned Cartesian coordinates (N, 3)"
    )
    center_of_mass: Any = Field(
        ..., description="Center of mass vector (3,) (zeros for aligned frame)"
    )
    n_atoms: int = Field(
        ..., description="Total atom count (including ghost atoms)"
    )
    n_ghost_atoms: int = Field(
        ..., description="Number of ghost atoms"
    )
    top_type: str = Field(
        ..., description="Rotor classification: asymmetric_top, oblate_symmetric_top, prolate_symmetric_top, spherical_top, linear"
    )
    inertial_defect: float = Field(
        ..., description="Inertial defect Delta in amu * Angstrom^2"
    )
    rays_kappa: float = Field(
        ..., description="Ray's asymmetry parameter kappa in [-1.0, 1.0]"
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
    eigenvalues_amu_angstrom2: Tuple[float, float, float] = Field(
        ..., description="Principal moments of inertia Ia <= Ib <= Ic"
    )
    planar_moments: Tuple[float, float, float] = Field(
        ..., description="Planar moments (Pa, Pb, Pc)"
    )
    rotation_matrix: Any = Field(
        ..., description="Principal axes rotation matrix V (3, 3)"
    )
    inertia_tensor_result: InertiaTensorResult = Field(
        ..., description="Detailed moment of inertia result"
    )
    eckart_alignment_result: Optional[EckartAlignmentResult] = Field(
        None, description="Optional Eckart frame alignment result"
    )

    @field_serializer("aligned_coords", "center_of_mass", "rotation_matrix", check_fields=False)
    def _serialize_numpy(self, val: Any) -> Any:
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val


def standardize_molecular_topology(
    mol: Any,
    symbols: Optional[Sequence[str]] = None,
    masses: Optional[Sequence[float] | np.ndarray] = None,
    ref_coords: Optional[np.ndarray] = None,
    is_linear: Optional[bool] = None,
) -> ToposAlignmentResult:
    """Standardizes molecular topology by shifting to COM, aligning to principal axes, and optionally performing Eckart frame alignment.

    Accepts:
    - Sequence of AtomModel or atom dicts
    - Dict with 'coords' and 'symbols' or 'atoms'
    - MolecularGraph object
    - Raw numpy array of coordinates (with symbols or masses provided)

    Parameters
    ----------
    mol : Any
        Molecular representation (AtomModel sequence, dict, MolecularGraph, or numpy array).
    symbols : Sequence[str], optional
        Explicit elemental symbols.
    masses : Sequence[float] | np.ndarray, optional
        Explicit atomic masses.
    ref_coords : np.ndarray, optional
        Reference coordinates for optional Eckart frame alignment.
    is_linear : bool, optional
        Explicit linear molecule override.

    Returns
    -------
    ToposAlignmentResult
        Comprehensive standardized alignment result model.
    """
    coords_list: List[List[float]] = []
    extracted_symbols: List[str] = []

    # 1. Parse mol input
    if isinstance(mol, dict):
        if "coords" in mol:
            coords_arr = np.asarray(mol["coords"], dtype=np.float64)
            if "symbols" in mol:
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
                    if pos is None:
                        raise ValueError(f"[INVALID DATA] Atom dictionary missing coordinates: {item}")
                    if sym is None:
                        raise ValueError(f"[INVALID DATA] Atom dictionary missing atomic symbol: {item}")
                    coords_list.append([float(x) for x in pos])
                    extracted_symbols.append(str(sym))
                elif hasattr(item, "coords") and hasattr(item, "symbol"):
                    coords_list.append(list(item.coords))
                    extracted_symbols.append(str(item.symbol))
            coords_arr = np.array(coords_list, dtype=np.float64)
        else:
            raise ValueError("[INVALID DATA] Dict molecular input must contain 'coords' or 'atoms'.")

    elif hasattr(mol, "atoms"):
        for item in mol.atoms:
            if hasattr(item, "coords"):
                coords_list.append(list(item.coords))
            elif hasattr(item, "x") and hasattr(item, "y") and hasattr(item, "z"):
                coords_list.append([float(item.x), float(item.y), float(item.z)])
            if hasattr(item, "symbol"):
                extracted_symbols.append(str(item.symbol))
        coords_arr = np.array(coords_list, dtype=np.float64)

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
                if pos is None:
                    raise ValueError(f"[INVALID DATA] Atom dictionary missing coordinates: {item}")
                if sym is None:
                    raise ValueError(f"[INVALID DATA] Atom dictionary missing atomic symbol: {item}")
                coords_list.append([float(x) for x in pos])
                extracted_symbols.append(str(sym))
            elif hasattr(item, "coords") and hasattr(item, "symbol"):
                coords_list.append(list(item.coords))
                extracted_symbols.append(str(item.symbol))
        coords_arr = np.array(coords_list, dtype=np.float64)

    else:
        coords_arr = np.asarray(mol, dtype=np.float64)
        if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
            raise ValueError(f"[INVALID SHAPE] Input coordinates must have shape (N, 3), got {coords_arr.shape}.")

    # Resolve symbols
    if symbols is not None:
        final_symbols = list(symbols)
    elif extracted_symbols:
        final_symbols = extracted_symbols
    else:
        final_symbols = None

    # Count ghost atoms
    n_atoms = len(coords_arr)
    if final_symbols is not None:
        n_ghost_atoms = sum(1 for s in final_symbols if is_ghost_symbol(s))
    elif masses is not None:
        n_ghost_atoms = sum(1 for m in masses if m == 0.0)
    else:
        n_ghost_atoms = 0

    # Resolve masses
    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=final_symbols)

    # Center of mass and principal axes alignment
    inertia_engine = MomentOfInertiaEngine()
    inertia_res = inertia_engine.align_to_principal_axes(coords_arr, masses=masses_arr)

    # Optional Eckart frame alignment if ref_coords provided
    eckart_res: Optional[EckartAlignmentResult] = None
    if ref_coords is not None:
        aligner = EckartFrameAligner()
        eckart_res = aligner.align(coords_arr, ref_coords=ref_coords, masses=masses_arr)

    # Center of mass of standardized aligned molecule is (0, 0, 0)
    aligned_com = np.array([0.0, 0.0, 0.0], dtype=np.float64)

    return ToposAlignmentResult(
        aligned_coords=inertia_res.aligned_coords,
        center_of_mass=aligned_com,
        n_atoms=n_atoms,
        n_ghost_atoms=n_ghost_atoms,
        top_type=inertia_res.top_type,
        inertial_defect=inertia_res.inertial_defect,
        rays_kappa=inertia_res.rays_kappa,
        rotational_constants_mhz=inertia_res.rotational_constants_mhz,
        rotational_constants_ghz=inertia_res.rotational_constants_ghz,
        rotational_constants_cm1=inertia_res.rotational_constants_cm1,
        eigenvalues_amu_angstrom2=inertia_res.eigenvalues_amu_angstrom2,
        planar_moments=inertia_res.planar_moments,
        rotation_matrix=inertia_res.rotation_matrix,
        inertia_tensor_result=inertia_res,
        eckart_alignment_result=eckart_res,
    )


# Object-oriented pipeline wrapper
class ToposAlignment:
    """Object-oriented wrapper for molecular topology standardization and alignment."""

    @staticmethod
    def standardize(
        mol: Any,
        symbols: Optional[Sequence[str]] = None,
        masses: Optional[Sequence[float] | np.ndarray] = None,
        ref_coords: Optional[np.ndarray] = None,
        is_linear: Optional[bool] = None,
    ) -> ToposAlignmentResult:
        """Standardizes molecular coordinates and aligns to principal axes / Eckart frame."""
        return standardize_molecular_topology(
            mol=mol,
            symbols=symbols,
            masses=masses,
            ref_coords=ref_coords,
            is_linear=is_linear,
        )


ToposAlignmentEngine = ToposAlignment


# ==============================================================================
# 7. File Parsers & Formatters (XYZ)
# ==============================================================================

def parse_xyz_text(text: str) -> Tuple[np.ndarray, List[str], str]:
    """Parses standard multi-line XYZ formatted string into coordinates and symbols.

    Parameters
    ----------
    text : str
        XYZ content string.

    Returns
    -------
    Tuple[np.ndarray, List[str], str]
        (coordinates (N, 3), symbols list (N,), comment string)
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        raise ValueError("[INVALID DATA] Empty XYZ input.")

    # Try parsing atom count from first line
    try:
        n_atoms = int(lines[0])
        comment = lines[1] if len(lines) > 1 else ""
        atom_lines = lines[2:2 + n_atoms] if len(lines) >= 2 + n_atoms else lines[2:]
    except ValueError:
        comment = ""
        atom_lines = lines

    coords_list: List[List[float]] = []
    symbols_list: List[str] = []

    for idx, line in enumerate(atom_lines):
        parts = line.split()
        if len(parts) < 4:
            continue
        sym = parts[0]
        try:
            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            continue
        symbols_list.append(sym)
        coords_list.append([x, y, z])

    if not coords_list:
        raise ValueError("[INVALID DATA] No valid atom coordinate lines parsed from XYZ.")

    return np.array(coords_list, dtype=np.float64), symbols_list, comment


def format_aligned_xyz(symbols: Sequence[str], coords: np.ndarray, comment: str = "") -> str:
    """Formats atomic symbols and Cartesian coordinates into standard XYZ format.

    Parameters
    ----------
    symbols : Sequence[str]
        Atomic element symbols.
    coords : np.ndarray
        Array of shape (N, 3) representing coordinates.
    comment : str, optional
        Comment line text.

    Returns
    -------
    str
        Standard XYZ formatted text.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    n_atoms = len(symbols)
    if coords_arr.shape != (n_atoms, 3):
        raise ValueError(f"[DIMENSION MISMATCH] Symbols length ({n_atoms}) != coords shape {coords_arr.shape}.")

    lines = [str(n_atoms), comment or "CoChem-TOPOS Aligned Geometry"]
    for sym, (x, y, z) in zip(symbols, coords_arr):
        lines.append(f"{sym:<4s} {x:14.8f} {y:14.8f} {z:14.8f}")
    return "\n".join(lines) + "\n"


def write_aligned_xyz(
    file_path: Union[str, Path],
    symbols: Sequence[str],
    coords: np.ndarray,
    comment: str = "",
) -> Path:
    """Writes aligned coordinates to an XYZ file on disk.

    Parameters
    ----------
    file_path : Union[str, Path]
        Target file path.
    symbols : Sequence[str]
        Atomic symbols.
    coords : np.ndarray
        Coordinates array (N, 3).
    comment : str, optional
        Comment text.

    Returns
    -------
    Path
        Resolved output file path.
    """
    out_p = Path(file_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    xyz_str = format_aligned_xyz(symbols, coords, comment=comment)
    out_p.write_text(xyz_str, encoding="utf-8")
    return out_p


# ==============================================================================
# 8. Command-Line Interface (CLI) Entrypoint
# ==============================================================================

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint for legacy PAF and Eckart molecular topology alignment.

    Parameters
    ----------
    argv : Sequence[str], optional
        Command line arguments.

    Returns
    -------
    int
        0 on success, non-zero on failure.
    """
    parser = argparse.ArgumentParser(
        description="CoChem-TOPOS: Legacy PAF & Dual-Frame Eckart Molecular Alignment CLI"
    )
    parser.add_argument("input_file", type=str, help="Path to input molecular geometry (.xyz)")
    parser.add_argument("--ref", "-r", type=str, default="", help="Optional reference geometry (.xyz) for Eckart alignment")
    parser.add_argument("--mode", "-m", choices=["paf", "eckart", "standardize"], default="standardize", help="Alignment mode")
    parser.add_argument("--output-xyz", "-o", type=str, default="", help="Optional output path for aligned .xyz geometry")
    parser.add_argument("--output-json", "-j", type=str, default="", help="Optional output path for JSON alignment report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    in_path = Path(args.input_file).resolve()
    if not in_path.is_file():
        logger.error(f"Input file not found: {in_path}")
        return 1

    try:
        coords, symbols, comment = parse_xyz_text(in_path.read_text(encoding="utf-8"))
        logger.info(f"Loaded {len(coords)} atoms from {in_path.name}")

        ref_coords = None
        if args.ref:
            ref_path = Path(args.ref).resolve()
            if not ref_path.is_file():
                logger.error(f"Reference file not found: {ref_path}")
                return 1
            ref_coords, ref_symbols, _ = parse_xyz_text(ref_path.read_text(encoding="utf-8"))
            logger.info(f"Loaded reference with {len(ref_coords)} atoms from {ref_path.name}")

        # Execute alignment based on mode
        if args.mode == "paf" and ref_coords is None:
            paf_aligner = LegacyPAFAligner()
            paf_res = paf_aligner.align_single(coords, symbols=symbols)
            aligned_coords = np.asarray(paf_res.aligned_coords)
            logger.info(f"Rotor Classification: {paf_res.top_type}")
            logger.info(f"Rotational Constants (A, B, C) MHz: {paf_res.rotational_constants_mhz}")
            logger.info(f"Inertial Defect (amu*A^2): {paf_res.inertial_defect:.6f}")
            logger.info(f"Ray's Asymmetry Kappa: {paf_res.rays_kappa:.6f}")
            report_data = paf_res.model_dump()

        elif args.mode == "paf" and ref_coords is not None:
            paf_aligner = LegacyPAFAligner()
            paf_res = paf_aligner.align_conformation_pair(coords, ref_coords, symbols=symbols)
            aligned_coords = np.asarray(paf_res.aligned_coords)
            logger.info(f"PAF Pair RMSD: {paf_res.rmsd_to_reference:.6f} A")
            logger.info(f"Rotor Classification: {paf_res.top_type}")
            logger.info(f"Rotational Constants (A, B, C) MHz: {paf_res.rotational_constants_mhz}")
            report_data = paf_res.model_dump()

        else:
            result = standardize_molecular_topology(
                mol=coords,
                symbols=symbols,
                ref_coords=ref_coords,
            )
            aligned_coords = np.asarray(result.aligned_coords)
            logger.info(f"Topology Standardized: {result.top_type}")
            logger.info(f"Rotational Constants (A, B, C) MHz: {result.rotational_constants_mhz}")
            logger.info(f"Inertial Defect (amu*A^2): {result.inertial_defect:.6f}")
            logger.info(f"Ray's Asymmetry Kappa: {result.rays_kappa:.6f}")
            if result.eckart_alignment_result:
                logger.info(f"Eckart Alignment RMSD: {result.eckart_alignment_result.rmsd:.6f} A")
                logger.info(f"Rotational Torque Residual: {result.eckart_alignment_result.residual_rotational_norm:.3e}")
            report_data = result.model_dump()

        # Output XYZ
        if args.output_xyz:
            out_xyz_path = Path(args.output_xyz).resolve()
            write_aligned_xyz(out_xyz_path, symbols, aligned_coords, comment=f"Aligned via CoChem-TOPOS ({args.mode})")
            logger.info(f"Wrote aligned geometry to {out_xyz_path}")

        # Output JSON
        if args.output_json:
            out_json_path = Path(args.output_json).resolve()
            out_json_path.parent.mkdir(parents=True, exist_ok=True)
            out_json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
            logger.info(f"Wrote alignment JSON report to {out_json_path}")

        return 0

    except Exception as exc:
        logger.error(f"Alignment failed: {exc}", exc_info=args.verbose)
        return 1


# ==============================================================================
# Public API Manifest
# ==============================================================================

__all__ = [
    # Physical Constants
    "PLANCK_H",
    "SPEED_OF_LIGHT_C",
    "ATOMIC_MASS_UNIT_U",
    "ANGSTROM_TO_M",
    "FACTOR_HZ",
    "FACTOR_MHZ",
    "FACTOR_GHZ",
    "FACTOR_CM1",
    # Mass & Ghost Symbol Helpers
    "is_ghost_symbol",
    "get_physical_mass",
    "resolve_atomic_masses",
    # Center of Mass
    "compute_center_of_mass",
    "translate_to_center_of_mass",
    "CenterOfMassTranslator",
    # Moment of Inertia & Spectroscopic Rotor Engine
    "InertiaTensorResult",
    "MomentOfInertiaEngine",
    # Legacy PAF Alignment Engine
    "PAFAlignmentResult",
    "LegacyPAFAligner",
    "PAFAligner",
    "PAFAlignmentEngine",
    # Eckart Frame Aligner
    "EckartAlignmentResult",
    "EckartFrameAligner",
    "align_to_eckart_frame",
    # Vibrational Projector
    "VibrationalProjector",
    # Unified Pipeline
    "ToposAlignmentResult",
    "ToposAlignment",
    "ToposAlignmentEngine",
    "standardize_molecular_topology",
    # Parsers & Formatters
    "parse_xyz_text",
    "format_aligned_xyz",
    "write_aligned_xyz",
    # CLI
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
