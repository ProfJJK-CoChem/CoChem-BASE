"""
CoChem-TORQ: Phase 2 Exact Eckart Frame Aligner
================================================
Enforces strict geometric normalization before spatial mapping begins,
securing the rotational reference frame and principal axes of inertia.

Authoritative Standards:
- Method Matrix: Stage 1.0 - 2.0 Eckart Frame & Spectroscopic Constants
- Planck Constant / NIST CODATA 2022 / 2026 Fundamental Constants
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from cochem_torq_vault import CIAAW_ISOTOPIC_MASSES

logger = logging.getLogger("CoChem-TORQ.Alignment")

# Fundamental Conversion Constant:
# h / (8 * pi^2 * u * A^2) in MHz (CODATA 2022 / Method Matrix Standard)
INERTIA_CONVERSION_AMU_ANG2_MHZ: float = 505379.0084350172


def translate_com_to_origin(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    masses: Optional[Sequence[float]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Translates molecular Cartesian coordinates so that the Center of Mass (COM),
    calculated with exact mono-isotopic CIAAW masses, resides precisely at (0, 0, 0) Angstrom.
    Returns (centered_coordinates, com_vector).
    """
    coords = np.asarray(coordinates, dtype=np.float64)
    n_atoms = len(symbols)
    if coords.shape != (n_atoms, 3):
        raise ValueError(f"Shape mismatch: {coords.shape} for {n_atoms} symbols")

    if masses is not None:
        mass_arr = np.asarray(masses, dtype=np.float64)
    else:
        mass_arr = np.array(
            [CIAAW_ISOTOPIC_MASSES.get(s.capitalize(), 12.0) for s in symbols], dtype=np.float64
        )

    total_mass = float(np.sum(mass_arr))
    if total_mass <= 0.0:
        raise ValueError("Total molecular mass must be greater than zero.")

    com = np.sum(coords * mass_arr[:, np.newaxis], axis=0) / total_mass
    centered_coords = coords - com

    logger.debug("Translated COM %s to origin (total mass: %.4f amu)", com, total_mass)
    return centered_coords, com


def diagonalize_principal_axes(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    masses: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """
    Constructs the 3x3 Moment of Inertia Tensor, diagonalizes it (Ia <= Ib <= Ic),
    and rotates the molecular coordinates to the principal axis frame.
    Calculates principal rotational constants (A, B, C in MHz & GHz), Ray's asymmetry
    parameter kappa, and the inertial planar defect Delta.
    """
    centered_coords, com = translate_com_to_origin(symbols, coordinates, masses)

    if masses is not None:
        mass_arr = np.asarray(masses, dtype=np.float64)
    else:
        mass_arr = np.array(
            [CIAAW_ISOTOPIC_MASSES.get(s.capitalize(), 12.0) for s in symbols], dtype=np.float64
        )

    x = centered_coords[:, 0]
    y = centered_coords[:, 1]
    z = centered_coords[:, 2]

    # Moment of inertia tensor components
    I_xx = float(np.sum(mass_arr * (y**2 + z**2)))
    I_yy = float(np.sum(mass_arr * (x**2 + z**2)))
    I_zz = float(np.sum(mass_arr * (x**2 + y**2)))
    I_xy = float(-np.sum(mass_arr * x * y))
    I_xz = float(-np.sum(mass_arr * x * z))
    I_yz = float(-np.sum(mass_arr * y * z))

    I_tensor = np.array(
        [
            [I_xx, I_xy, I_xz],
            [I_xy, I_yy, I_yz],
            [I_xz, I_yz, I_zz],
        ],
        dtype=np.float64,
    )

    # Diagonalize symmetric inertia tensor
    eigvals, eigvecs = np.linalg.eigh(I_tensor)

    # Sort eigenvalues so that I_a <= I_b <= I_c
    order = np.argsort(eigvals)
    sorted_eigvals = eigvals[order]
    rot_mat = eigvecs[:, order]

    # Enforce right-handed coordinate frame: det(R) == +1
    if np.linalg.det(rot_mat) < 0:
        rot_mat[:, 2] = -rot_mat[:, 2]

    # Transform coordinates to principal axis frame: r' = r @ R
    aligned_coords = centered_coords @ rot_mat

    I_a = float(sorted_eigvals[0])
    I_b = float(sorted_eigvals[1])
    I_c = float(sorted_eigvals[2])

    # Rotational constants in MHz
    A_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / I_a if I_a > 1e-4 else float("inf")
    B_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / I_b if I_b > 1e-4 else float("inf")
    C_mhz = INERTIA_CONVERSION_AMU_ANG2_MHZ / I_c if I_c > 1e-4 else float("inf")

    # Rotational constants in GHz
    A_ghz = A_mhz / 1000.0
    B_ghz = B_mhz / 1000.0
    C_ghz = C_mhz / 1000.0

    # Ray's asymmetry parameter kappa = (2B - A - C) / (A - C)
    if math.isinf(A_mhz) or abs(A_mhz - C_mhz) < 1e-6:
        kappa = -1.0 if abs(A_mhz - B_mhz) < 1e-6 else 1.0
    else:
        kappa = float((2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz))

    # Inertial planar defect Delta = I_c - I_a - I_b (amu * Angstrom^2)
    inertial_defect = float(I_c - I_a - I_b)

    # Rotor classification
    if I_a < 1e-4:
        top_type = "linear"
    elif abs(I_a - I_b) < 1e-3 and abs(I_b - I_c) < 1e-3:
        top_type = "spherical_top"
    elif abs(I_a - I_b) < 1e-3:
        top_type = "oblate_symmetric_top"
    elif abs(I_b - I_c) < 1e-3:
        top_type = "prolate_symmetric_top"
    else:
        top_type = "asymmetric_top"

    logger.info(
        "Diagonalized inertia tensor: I_a=%.4f, I_b=%.4f, I_c=%.4f (A=%.2f, B=%.2f, C=%.2f MHz, kappa=%.4f)",
        I_a,
        I_b,
        I_c,
        A_mhz,
        B_mhz,
        C_mhz,
        kappa,
    )

    return {
        "aligned_coordinates": aligned_coords,
        "com_vector": com,
        "inertia_tensor": I_tensor,
        "principal_moments_amu_ang2": (I_a, I_b, I_c),
        "rotational_constants_mhz": (A_mhz, B_mhz, C_mhz),
        "rotational_constants_ghz": (A_ghz, B_ghz, C_ghz),
        "asymmetry_parameter_kappa": kappa,
        "inertial_defect_amu_ang2": inertial_defect,
        "rotation_matrix": rot_mat,
        "top_type": top_type,
    }


def align_eckart_frame(
    coordinates: np.ndarray,
    symbols: Sequence[str],
    masses: Optional[Sequence[float]] = None,
) -> np.ndarray:
    """Helper alias returning aligned coordinates in the principal inertia / Eckart frame."""
    res = diagonalize_principal_axes(symbols=symbols, coordinates=coordinates, masses=masses)
    return res["aligned_coordinates"]

