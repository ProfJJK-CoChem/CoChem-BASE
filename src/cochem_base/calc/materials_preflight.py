"""Product M Crystal Symmetry & Reciprocal Density Gate.

Authoritative Materials Preflight Validation Engine for CoChem-BASE (Task L3.2.3).
Enforces physical and crystallographic boundary invariants for Product M (Solid-State Materials):
- Non-degenerate unit cell volume: V_cell = |a_1 . (a_2 x a_3)| > 1.0e-6 A^3 [M]
- Reciprocal lattice vectors: b_i = 2*pi * (a_j x a_k) / V_cell [M]
- Monkhorst-Pack reciprocal k-point linear density: rho_{k,i} = k_i / |b_i| >= 0.04 A^-1 [M]
- Gamma-point integration ceiling: kmesh = (1, 1, 1) mandates V_cell > 2000.0 A^3 [M]
- Vacuum separation in non-periodic dimensions (slabs / wires) >= 15.0 A [M]
- Dynamic atomic masses and numbers retrieved exclusively via Mendeleev library [M]
- Analytical metric tensor crystal system detection with optional spglib interface [M]

Method Matrix Reference: Sections 1.2, 2.2, 3.0, and 4.4.
"""

from __future__ import annotations

import datetime
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from mendeleev import element  # type: ignore[import-untyped]

from cochem_base.exceptions import (
    InvalidPeriodicCellError,
    ProductDomainBoundaryViolation,
    ReciprocalDensityViolation,
)

# Authoritative physical thresholds for Product M
MIN_UNIT_CELL_VOLUME_ANG3: float = 1.0e-6
MIN_RECIPROCAL_K_DENSITY_ANG_INV: float = 0.04  # rho_k >= 0.04 A^-1
GAMMA_POINT_VOLUME_CEILING_ANG3: float = 2000.0  # Gamma-only mandates V > 2000 A^3
MIN_VACUUM_SEPARATION_ANG: float = 15.0  # Vacuum padding >= 15.0 A for non-periodic dimensions


def compute_cell_volume(lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]]) -> float:
    """Calculates the scalar triple product volume of the unit cell: V_cell = |a_1 . (a_2 x a_3)|.

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 array where row vectors are direct lattice vectors a_1, a_2, a_3 in Angstroms.

    Returns
    -------
    float
        Unit cell volume in Angstroms^3 [M].

    Raises
    ------
    InvalidPeriodicCellError
        If lattice vectors have invalid dimensions or contain non-finite numbers (NaN/Inf).
    """
    arr = np.asarray(lattice_vectors, dtype=np.float64)
    if arr.shape != (3, 3):
        raise InvalidPeriodicCellError(
            f"Lattice vectors must have shape (3, 3), got {arr.shape} [M].",
            details={"shape": arr.shape},
        )
    if not np.all(np.isfinite(arr)):
        raise InvalidPeriodicCellError(
            "Lattice vectors contain non-finite values (NaN or Inf) [M].",
            details={"lattice_vectors": arr.tolist()},
        )
    a1, a2, a3 = arr[0], arr[1], arr[2]
    signed_volume = float(np.dot(a1, np.cross(a2, a3)))
    return abs(signed_volume)


compute_scalar_triple_product_volume = compute_cell_volume


def compute_reciprocal_vectors(
    lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]],
    cell_volume: Optional[float] = None,
) -> np.ndarray:
    """Computes the reciprocal lattice vectors b_1, b_2, b_3 in 1/Angstroms.

    Formulas:
        b_1 = 2*pi * (a_2 x a_3) / (a_1 . (a_2 x a_3))
        b_2 = 2*pi * (a_3 x a_1) / (a_1 . (a_2 x a_3))
        b_3 = 2*pi * (a_1 x a_2) / (a_1 . (a_2 x a_3))

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 array of direct lattice row vectors in Angstroms.
    cell_volume : Optional[float]
        Optional precomputed cell volume in Angstroms^3.

    Returns
    -------
    np.ndarray
        3x3 array where row vectors are reciprocal vectors b_1, b_2, b_3 in 1/Angstroms [M].

    Raises
    ------
    InvalidPeriodicCellError
        If unit cell volume is non-positive or degenerate.
    """
    arr = np.asarray(lattice_vectors, dtype=np.float64)
    if arr.shape != (3, 3):
        raise InvalidPeriodicCellError(
            f"Lattice vectors must have shape (3, 3), got {arr.shape} [M].",
            details={"shape": arr.shape},
        )
    if not np.all(np.isfinite(arr)):
        raise InvalidPeriodicCellError(
            "Lattice vectors contain non-finite values (NaN or Inf) [M].",
            details={"lattice_vectors": arr.tolist()},
        )

    a1, a2, a3 = arr[0], arr[1], arr[2]
    denom = float(np.dot(a1, np.cross(a2, a3)))
    if not math.isfinite(denom) or abs(denom) <= MIN_UNIT_CELL_VOLUME_ANG3:
        raise InvalidPeriodicCellError(
            f"Unit cell volume V_cell = {abs(denom):.6e} A^3 is degenerate or non-positive (<= 1.0e-6 A^3) [M].",
            details={"volume": abs(denom), "threshold": MIN_UNIT_CELL_VOLUME_ANG3},
        )

    b1 = 2.0 * math.pi * np.cross(a2, a3) / denom
    b2 = 2.0 * math.pi * np.cross(a3, a1) / denom
    b3 = 2.0 * math.pi * np.cross(a1, a2) / denom

    return np.array([b1, b2, b3], dtype=np.float64)


compute_reciprocal_lattice_vectors = compute_reciprocal_vectors


def compute_kmesh_density(
    lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]],
    kmesh: Tuple[int, int, int],
) -> np.ndarray:
    """Computes the reciprocal linear k-point density rho_{k,i} = k_i / |b_i| for each axis.

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 array of direct lattice row vectors in Angstroms.
    kmesh : Tuple[int, int, int]
        Number of k-points along each reciprocal axis (k_1, k_2, k_3).

    Returns
    -------
    np.ndarray
        Array of shape (3,) with linear reciprocal densities (rho_{k,1}, rho_{k,2}, rho_{k,3}) in Angstroms [M].

    Raises
    ------
    ReciprocalDensityViolation
        If k-mesh counts are non-positive.
    """
    recip = compute_reciprocal_vectors(lattice_vectors)
    b_norms = np.linalg.norm(recip, axis=1)

    densities_list: List[float] = []
    for i in range(3):
        k_val = int(kmesh[i])
        if k_val < 1:
            raise ReciprocalDensityViolation(
                f"k-point mesh count along axis {i+1} must be positive integer, got {k_val} [M].",
                details={"axis": i + 1, "k_count": k_val},
            )
        densities_list.append(float(k_val) / float(b_norms[i]))

    return np.array(densities_list, dtype=np.float64)


def compute_vacuum_separation(
    lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]],
    coordinates: Optional[Union[np.ndarray, Sequence[Sequence[float]]]],
    axis: int,
) -> float:
    """Calculates physical vacuum separation along a specified non-periodic lattice axis.

    The perpendicular cell height is h_i = 2*pi / |b_i| = V_cell / |a_j x a_k|.
    If coordinates are provided, vacuum separation is h_i - (max(proj) - min(proj)).
    If coordinates are None, vacuum separation equals the full perpendicular cell height h_i.

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 direct lattice row vectors.
    coordinates : Optional[Union[np.ndarray, Sequence[Sequence[float]]]]
        Cartesian coordinates of atoms in Angstroms, shape (N, 3).
    axis : int
        0-indexed axis (0, 1, or 2) corresponding to the non-periodic direction.

    Returns
    -------
    float
        Vacuum separation in Angstroms [M].

    Raises
    ------
    InvalidPeriodicCellError
        If the reciprocal lattice vector along the selected axis is degenerate.
    ProductDomainBoundaryViolation
        If coordinates array shape is not (N, 3) or contains non-finite values.
    """
    if axis not in (0, 1, 2):
        raise ProductDomainBoundaryViolation(
            f"Axis index must be 0, 1, or 2, got {axis} [M].",
            details={"axis": axis},
        )

    recip = compute_reciprocal_vectors(lattice_vectors)
    b_vec = recip[axis]
    b_norm = float(np.linalg.norm(b_vec))
    if not math.isfinite(b_norm) or b_norm <= 1e-12:
        raise InvalidPeriodicCellError(
            f"Degenerate reciprocal lattice vector along axis {axis+1} [M]."
        )

    # Interplanar spacing / perpendicular cell height h_i = 2*pi / |b_i|
    h_i = 2.0 * math.pi / b_norm

    if coordinates is None or len(coordinates) == 0:
        return h_i

    coords_arr = np.asarray(coordinates, dtype=np.float64)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ProductDomainBoundaryViolation(
            f"Coordinates array must have shape (N, 3), got {coords_arr.shape} [M]."
        )
    if not np.all(np.isfinite(coords_arr)):
        raise ProductDomainBoundaryViolation(
            "Coordinates array contains non-finite values (NaN or Inf) [M].",
            details={"axis": axis + 1},
        )

    # Unit normal vector along reciprocal direction
    unit_normal = b_vec / b_norm
    projections = np.dot(coords_arr, unit_normal)
    thickness = float(np.max(projections) - np.min(projections))

    vacuum = h_i - thickness
    return max(vacuum, 0.0)


def detect_crystal_symmetry(
    lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]],
    coordinates: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    atomic_numbers: Optional[Sequence[int]] = None,
    atomic_symbols: Optional[Sequence[str]] = None,
    symprec: float = 1e-3,
) -> Dict[str, Any]:
    """Detects crystal symmetry and classifies the Bravais crystal system.

    Interfaces cleanly with spglib or ase if installed; performs exact analytical
    metric tensor analysis without synthetic assumptions.

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 array of direct lattice row vectors in Angstroms.
    coordinates : Optional[Union[np.ndarray, Sequence[Sequence[float]]]]
        Cartesian coordinates of atoms, shape (N, 3).
    atomic_numbers : Optional[Sequence[int]]
        Atomic numbers Z for each atom.
    atomic_symbols : Optional[Sequence[str]]
        Element symbols for each atom (resolved to Z via Mendeleev if numbers not provided).
    symprec : float
        Symmetry tolerance in Angstroms.

    Returns
    -------
    Dict[str, Any]
        Crystal symmetry telemetry dictionary.
    """
    arr = np.asarray(lattice_vectors, dtype=np.float64)
    if not np.all(np.isfinite(arr)) or arr.shape != (3, 3):
        raise InvalidPeriodicCellError(
            "Lattice vectors must be finite 3x3 array [M].",
            details={"shape": arr.shape},
        )

    # Metric tensor G = A . A^T
    metric_tensor = np.dot(arr, arr.T)

    a = float(np.sqrt(metric_tensor[0, 0]))
    b = float(np.sqrt(metric_tensor[1, 1]))
    c = float(np.sqrt(metric_tensor[2, 2]))

    cos_alpha = np.clip(metric_tensor[1, 2] / (b * c), -1.0, 1.0)
    cos_beta = np.clip(metric_tensor[0, 2] / (a * c), -1.0, 1.0)
    cos_gamma = np.clip(metric_tensor[0, 1] / (a * b), -1.0, 1.0)

    alpha_deg = float(np.degrees(np.arccos(cos_alpha)))
    beta_deg = float(np.degrees(np.arccos(cos_beta)))
    gamma_deg = float(np.degrees(np.arccos(cos_gamma)))

    tol_len = 1e-3
    tol_ang = 0.5  # degrees

    def _eq(x: float, y: float) -> bool:
        return abs(x - y) <= tol_len

    def _is_ang(x: float, target: float) -> bool:
        return abs(x - target) <= tol_ang

    all_90 = _is_ang(alpha_deg, 90.0) and _is_ang(beta_deg, 90.0) and _is_ang(gamma_deg, 90.0)
    all_eq = _eq(a, b) and _eq(b, c)

    if all_eq and all_90:
        crystal_system = "Cubic"
    elif (_eq(a, b) or _eq(b, c) or _eq(a, c)) and all_90:
        crystal_system = "Tetragonal"
    elif all_90:
        crystal_system = "Orthorhombic"
    elif (
        (_eq(a, b) and _is_ang(alpha_deg, 90.0) and _is_ang(beta_deg, 90.0) and _is_ang(gamma_deg, 120.0))
        or (_eq(b, c) and _is_ang(beta_deg, 90.0) and _is_ang(gamma_deg, 90.0) and _is_ang(alpha_deg, 120.0))
        or (_eq(a, c) and _is_ang(alpha_deg, 90.0) and _is_ang(gamma_deg, 90.0) and _is_ang(beta_deg, 120.0))
    ):
        crystal_system = "Hexagonal"
    elif all_eq and _eq(alpha_deg, beta_deg) and _eq(beta_deg, gamma_deg) and not all_90:
        crystal_system = "Rhombohedral"
    elif (
        (_is_ang(alpha_deg, 90.0) and _is_ang(gamma_deg, 90.0) and not _is_ang(beta_deg, 90.0))
        or (_is_ang(alpha_deg, 90.0) and _is_ang(beta_deg, 90.0) and not _is_ang(gamma_deg, 90.0))
        or (_is_ang(beta_deg, 90.0) and _is_ang(gamma_deg, 90.0) and not _is_ang(alpha_deg, 90.0))
    ):
        crystal_system = "Monoclinic"
    else:
        crystal_system = "Triclinic"

    numbers_list: Optional[List[int]] = None
    if atomic_numbers is not None:
        numbers_list = [int(z) for z in atomic_numbers]
    elif atomic_symbols is not None:
        numbers_list = [int(element(s.strip().capitalize()).atomic_number) for s in atomic_symbols]

    space_group_symbol: Optional[str] = None
    space_group_number: Optional[int] = None
    symmetry_method = "metric_tensor_analytical"

    if coordinates is not None and numbers_list is not None and len(coordinates) == len(numbers_list):
        coords_arr = np.asarray(coordinates, dtype=np.float64)
        if np.all(np.isfinite(coords_arr)):
            scaled_pos = np.dot(coords_arr, np.linalg.inv(arr)) % 1.0
            try:
                import spglib  # type: ignore[import-untyped]
                cell_tuple = (arr, scaled_pos, numbers_list)
                dataset = spglib.get_symmetry_dataset(cell_tuple, symprec=symprec)
                if dataset is not None:
                    space_group_symbol = str(dataset.get("international"))
                    space_group_number = int(dataset.get("number"))
                    symmetry_method = "spglib_rigorous"
            except (ImportError, Exception):
                pass

    return {
        "crystal_system": crystal_system,
        "lattice_parameters": {
            "a": a,
            "b": b,
            "c": c,
            "alpha": alpha_deg,
            "beta": beta_deg,
            "gamma": gamma_deg,
        },
        "metric_tensor": metric_tensor.tolist(),
        "space_group_symbol": space_group_symbol,
        "space_group_number": space_group_number,
        "symmetry_method": symmetry_method,
    }


def validate_product_m_invariants(
    lattice_vectors: Union[np.ndarray, Sequence[Sequence[float]]],
    kmesh: Tuple[int, int, int],
    pbc: Tuple[bool, bool, bool] = (True, True, True),
    coordinates: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    atomic_symbols: Optional[Sequence[str]] = None,
    atomic_numbers: Optional[Sequence[int]] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Validates Product M solid-state materials boundary invariants.

    Enforces:
    1. Unit cell volume V_cell = |a_1 . (a_2 x a_3)| > 1.0e-6 A^3.
       Fails closed with InvalidPeriodicCellError if non-positive, degenerate, or non-finite.
    2. Reciprocal lattice vectors b_1, b_2, b_3 calculated via exact cross-product formulas.
    3. Monkhorst-Pack reciprocal linear k-point density rho_{k,i} = k_i / |b_i| >= 0.04 A^-1
       along all periodic axes. Raises ReciprocalDensityViolation if under-resolved.
    4. Gamma-point invariant: If kmesh = (1, 1, 1), requires V_cell > 2000.0 A^3.
       Raises ReciprocalDensityViolation if selected for sub-2000 A^3 cells.
    5. Non-periodic dimensions: For axes where pbc[i] is False, verifies vacuum separation >= 15.0 A.
       Raises ProductDomainBoundaryViolation if vacuum is under 15.0 A.
    6. Symmetry analysis: Evaluates metric tensor and interfaces with spglib if present.

    Parameters
    ----------
    lattice_vectors : Union[np.ndarray, Sequence[Sequence[float]]]
        3x3 array or list of lattice row vectors in Angstroms.
    kmesh : Tuple[int, int, int]
        Monkhorst-Pack k-point grid dimensions (k_1, k_2, k_3).
    pbc : Tuple[bool, bool, bool]
        Periodic boundary condition flags for axes (a, b, c). Default is (True, True, True).
    coordinates : Optional[Union[np.ndarray, Sequence[Sequence[float]]]]
        Cartesian coordinates of atoms in Angstroms (shape N, 3).
    atomic_symbols : Optional[Sequence[str]]
        Element symbols for atoms (resolved dynamically via Mendeleev).
    atomic_numbers : Optional[Sequence[int]]
        Atomic numbers for atoms.
    symbols : Optional[Sequence[str]]
        Alias for atomic_symbols.

    Returns
    -------
    Dict[str, Any]
        Structured validation telemetry dictionary.

    Raises
    ------
    InvalidPeriodicCellError
        If unit cell volume is non-positive, degenerate, or non-finite.
    ReciprocalDensityViolation
        If reciprocal k-point density is below 0.04 A^-1 or Gamma-point is misused.
    ProductDomainBoundaryViolation
        If vacuum separation along any non-periodic dimension is less than 15.0 A.
    """
    if atomic_symbols is None and symbols is not None:
        atomic_symbols = symbols

    arr = np.asarray(lattice_vectors, dtype=np.float64)
    if arr.shape != (3, 3):
        raise InvalidPeriodicCellError(
            f"Lattice vectors array must have shape (3, 3), got {arr.shape} [M].",
            details={"shape": arr.shape},
        )
    if not np.all(np.isfinite(arr)):
        raise InvalidPeriodicCellError(
            "Lattice vectors array contains non-finite values (NaN or Inf) [M].",
            details={"lattice_vectors": arr.tolist()},
        )

    # 1. Scalar triple product cell volume
    v_cell = compute_cell_volume(arr)
    if v_cell <= MIN_UNIT_CELL_VOLUME_ANG3:
        raise InvalidPeriodicCellError(
            f"Unit cell volume V_cell = {v_cell:.6e} A^3 is degenerate or non-positive "
            f"(<= {MIN_UNIT_CELL_VOLUME_ANG3:.1e} A^3) [M].",
            details={"volume": v_cell, "threshold": MIN_UNIT_CELL_VOLUME_ANG3},
        )

    # 2. Reciprocal lattice vectors: b_i = 2*pi * (a_j x a_k) / V_cell
    recip = compute_reciprocal_vectors(arr)
    b_norms = [float(np.linalg.norm(recip[i])) for i in range(3)]

    # 3. Reciprocal linear k-point density: rho_{k,i} = k_i / |b_i|
    densities = compute_kmesh_density(arr, kmesh)

    checked_invariants = [
        f"unit_cell_volume_non_degenerate (V_cell = {v_cell:.3f} A^3 > 1e-6 A^3)",
        "reciprocal_lattice_vectors_calculated",
    ]

    for i in range(3):
        if pbc[i]:
            rho_val = float(densities[i])
            if rho_val < MIN_RECIPROCAL_K_DENSITY_ANG_INV:
                raise ReciprocalDensityViolation(
                    f"Reciprocal linear k-point density along axis {i+1} is under-resolved: "
                    f"rho_k = {rho_val:.5f} A^-1 < {MIN_RECIPROCAL_K_DENSITY_ANG_INV:.5f} A^-1 threshold "
                    f"(k={kmesh[i]}, |b|={b_norms[i]:.4f} A^-1) [M].",
                    details={
                        "axis": i + 1,
                        "k_count": kmesh[i],
                        "b_norm": b_norms[i],
                        "rho_k": rho_val,
                        "threshold": MIN_RECIPROCAL_K_DENSITY_ANG_INV,
                    },
                )
            checked_invariants.append(
                f"reciprocal_density_axis_{i+1} (rho_k = {rho_val:.4f} >= {MIN_RECIPROCAL_K_DENSITY_ANG_INV} A^-1)"
            )

    # 4. Gamma-Point Invariant: If k = (1, 1, 1), verify V_cell > 2000.0 A^3
    is_gamma_only = (int(kmesh[0]) == 1 and int(kmesh[1]) == 1 and int(kmesh[2]) == 1)
    if is_gamma_only:
        if v_cell <= GAMMA_POINT_VOLUME_CEILING_ANG3:
            raise ReciprocalDensityViolation(
                f"Gamma-point sampling (1x1x1) is physically unphysical for sub-2000 A^3 unit cells "
                f"(V_cell = {v_cell:.2f} A^3 <= {GAMMA_POINT_VOLUME_CEILING_ANG3:.1f} A^3) [M]. "
                f"Brillouin zone integration requires dispersive k-point mesh sampling.",
                details={
                    "kmesh": kmesh,
                    "volume": v_cell,
                    "threshold": GAMMA_POINT_VOLUME_CEILING_ANG3,
                },
            )
        checked_invariants.append(
            f"gamma_point_supercell_volume_valid (V_cell = {v_cell:.1f} > 2000.0 A^3)"
        )

    # 5. Non-periodic dimensions & vacuum separation (>= 15.0 A)
    coords_arr: Optional[np.ndarray] = None
    if coordinates is not None:
        coords_arr = np.asarray(coordinates, dtype=np.float64)

    vacuum_separations: Dict[str, float] = {}
    for i in range(3):
        if not pbc[i]:
            vac_sep = compute_vacuum_separation(arr, coords_arr, axis=i)
            vacuum_separations[f"axis_{i+1}"] = vac_sep
            if vac_sep < MIN_VACUUM_SEPARATION_ANG:
                raise ProductDomainBoundaryViolation(
                    f"Vacuum separation along non-periodic axis {i+1} is {vac_sep:.3f} A, "
                    f"which is below the mandatory {MIN_VACUUM_SEPARATION_ANG:.1f} A threshold [M].",
                    details={
                        "axis": i + 1,
                        "vacuum_separation_ang": vac_sep,
                        "threshold": MIN_VACUUM_SEPARATION_ANG,
                        "pbc": pbc,
                    },
                )
            checked_invariants.append(
                f"vacuum_separation_axis_{i+1} ({vac_sep:.2f} A >= {MIN_VACUUM_SEPARATION_ANG} A)"
            )

    # 6. Crystal symmetry detection
    symmetry_telemetry = detect_crystal_symmetry(
        lattice_vectors=arr,
        coordinates=coords_arr,
        atomic_symbols=atomic_symbols,
        atomic_numbers=atomic_numbers,
    )
    checked_invariants.append(
        f"crystal_symmetry_classified ({symmetry_telemetry['crystal_system']})"
    )

    return {
        "status": "VALID",
        "product_category": "PRODUCT_M",
        "cell_volume_ang3": v_cell,
        "cell_volume_angstrom3": v_cell,
        "cell_volume": v_cell,
        "lattice_vectors": arr.tolist(),
        "reciprocal_vectors": recip.tolist(),
        "reciprocal_lattice_vectors": recip.tolist(),
        "reciprocal_vector_norms": b_norms,
        "reciprocal_lengths_angstrom_inv": tuple(b_norms),
        "kmesh": list(kmesh),
        "kmesh_linear_density_ang": [float(d) for d in densities],
        "k_densities": [float(d) for d in densities],
        "pbc": list(pbc),
        "vacuum_separations_ang": vacuum_separations,
        "vacuum_separation_angstrom": vacuum_separations,
        "crystal_system": symmetry_telemetry["crystal_system"].lower(),
        "symmetry": symmetry_telemetry,
        "checked_invariants": checked_invariants,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
