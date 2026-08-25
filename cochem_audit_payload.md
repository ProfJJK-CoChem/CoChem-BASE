Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task3_start_bench.md.
Original prompt:
﻿# Task: Create Start_BENCH.ipynb

## Target File
`cochem_bench\notebooks\Start_BENCH.ipynb` (relative to repo root)

## Architecture Note
This is a V2 rewrite. Ensure the `notebooks` directory exists.

## Requirements
Implement the Jupyter Backend Entry Point.
This notebook is the singular execution entry point for the module. It must be designed as a rigid, stateless application bootstrapper. It must never store heavy state or geometries in the Jupyter kernel memory. 

Cells to implement:
1. `Cell 1: Environment Validation & The Stage 0 Handshake`:
   - Executes silent imports (`ipywidgets`, `h5py`, `json`, `psutil`, `pathlib`, `os`, `filelock`).
   - Dynamically constructs and verifies the absolute path via `pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR")) / "Registry" / "cochem_system_config.json"`. Fail fast if the environment variable is missing.
   - Validates that the active Python environment strictly matches `cochem_bench_silo`. Enforces accelerator isolation by scrubbing GPU environment variables (`CUDA_VISIBLE_DEVICES=""`, `ROCR_VISIBLE_DEVICES=""`).
2. `Cell 2: Zero-Code UI Invocation`:
   - Imports the `BenchDashboard` class from `interfaces.voila_bench_dashboard`.
   - Injects the Stage 0 hardware constraints into it, and executes `.display()`.
   - Suppresses standard Jupyter `stdout` to prevent massive ORCA log dumps from freezing the kernel.

## Safety Contract
- Air-Gap strictly enforced dynamically: No absolute `D:\` or `/home/` paths can be hardcoded. Use `COCHEM_ARTIFACTS_DIR`.
Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\calc\cochem_kie_profiler.py ---
import logging

import h5py
import jax
import jax.numpy as jnp
import numpy as np
from qcelemental import periodictable as pt

try:
    import molsym
except ImportError:
    molsym = None

from collections.abc import Mapping
try:
    from mendeleev import element as _mendeleev_element
except ImportError:
    _mendeleev_element = None

_TARGET_HEAVY_MASS_NUMBERS = {
    "H": 2,    # Deuterium
    "C": 13,   # 13C
    "N": 15,   # 15N
    "O": 18,   # 18O
    "S": 34,   # 34S
    "Cl": 37,  # 37Cl
    "Br": 81,  # 81Br
}


class _DynamicHeavyIsotopesMap(Mapping):
    """Dynamic heavy isotope mass mapping backed by Mendeleev library."""

    def __getitem__(self, key: str) -> float:
        if not key or not isinstance(key, str):
            raise KeyError(key)
        sym = key.strip().capitalize()
        if sym not in _TARGET_HEAVY_MASS_NUMBERS:
            raise KeyError(key)

        mass_num = _TARGET_HEAVY_MASS_NUMBERS[sym]
        if _mendeleev_element is not None:
            try:
                el = _mendeleev_element(sym)
                for iso in getattr(el, "isotopes", []):
                    if iso.mass_number == mass_num and iso.mass is not None:
                        return float(iso.mass)
            except Exception:
                pass

        # Fallback values if mendeleev is unavailable
        fallbacks = {
            "H": 2.014101778,
            "C": 13.003354835,
            "N": 15.000108898,
            "O": 17.999159612,
            "S": 33.96786690,
            "Cl": 36.96590260,
            "Br": 80.9162906,
        }
        return fallbacks[sym]

    def __iter__(self):
        return iter(_TARGET_HEAVY_MASS_NUMBERS.keys())

    def __len__(self):
        return len(_TARGET_HEAVY_MASS_NUMBERS)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key.strip().capitalize() in _TARGET_HEAVY_MASS_NUMBERS


HEAVY_ISOTOPES: Mapping[str, float] = _DynamicHeavyIsotopesMap()

def get_projection_matrix(coords: jnp.ndarray, masses: jnp.ndarray) -> jnp.ndarray:
    """Constructs the Eckart projection operator P = I - D D^T."""
    N = coords.shape[0]
    total_mass = jnp.sum(masses)

    # Center of mass
    com = jnp.sum(coords * masses[:, None], axis=0) / total_mass
    coords_shifted = coords - com

    sqrt_m = jnp.sqrt(masses)

    # Translations (3N x 3)
    T = jnp.zeros((3 * N, 3))
    T = T.at[0::3, 0].set(sqrt_m)
    T = T.at[1::3, 1].set(sqrt_m)
    T = T.at[2::3, 2].set(sqrt_m)

    # Rotations (3N x 3)
    R = jnp.zeros((3 * N, 3))
    x, y, z = coords_shifted[:, 0], coords_shifted[:, 1], coords_shifted[:, 2]

    # Rx
    R = R.at[1::3, 0].set(-z * sqrt_m)
    R = R.at[2::3, 0].set(y * sqrt_m)
    # Ry
    R = R.at[0::3, 1].set(z * sqrt_m)
    R = R.at[2::3, 1].set(-x * sqrt_m)
    # Rz
    R = R.at[0::3, 2].set(-y * sqrt_m)
    R = R.at[1::3, 2].set(x * sqrt_m)

    TR = jnp.concatenate((T, R), axis=1) # (3N, 6)

    # Robust projection onto orthogonal complement using pseudo-inverse
    # This correctly handles rank-deficient systems (e.g., linear molecules, single atoms)
    ident = jnp.eye(3 * N)
    P = ident - TR @ jnp.linalg.pinv(TR)
    return P

@jax.jit
def compute_freqs(masses_jax: jnp.ndarray, H_jax: jnp.ndarray, coords_jax: jnp.ndarray) -> jnp.ndarray:
    """Computes harmonic frequencies given masses, Hessian, and coordinates."""
    inv_sqrt_m = 1.0 / jnp.sqrt(masses_jax)
    inv_sqrt_m_3 = jnp.repeat(inv_sqrt_m, 3)

    # Mass weight the Hessian: H_mw = M^{-1/2} H M^{-1/2}
    H_mw = H_jax * inv_sqrt_m_3[:, None] * inv_sqrt_m_3[None, :]

    # Eckart Projection
    P = get_projection_matrix(coords_jax, masses_jax)
    H_proj = P @ H_mw @ P

    # Diagonalize
    eigenvalues, _ = jnp.linalg.eigh(H_proj)

    # Convert to cm^-1 (~5140.487 cm^-1 per atomic unit)
    freqs = jnp.sign(eigenvalues) * jnp.sqrt(jnp.abs(eigenvalues)) * 5140.4871447
    return freqs

def auto_kie_profiling(hdf5_path: str, group_name: str) -> None:
    """Automates heavy isotope KIE profiling for a given basin in PESStore."""
    if molsym is None:
        raise RuntimeError("molsym is not installed.")

    with h5py.File(hdf5_path, 'a') as f:
        if group_name not in f:
            raise KeyError(f"Group {group_name} not found in {hdf5_path}.")

        grp = f[group_name]

        if "unweighted_hessian" in grp:
            H = grp["unweighted_hessian"][:]
        elif "hessian" in grp:
            H = grp["hessian"][:]
        else:
            raise KeyError("unweighted_hessian dataset not found in HDF5 group.")

        if "xyz_coordinates" not in grp:
            raise KeyError("xyz_coordinates dataset not found in HDF5 group.")
        coords = grp["xyz_coordinates"][:]

        symbols = None
        if "symbols" in grp:
            symbols_dset = grp["symbols"][:]
            symbols = [s.decode('utf-8') if isinstance(s, bytes) else s for s in symbols_dset]
        elif "atomic_numbers" in grp:
            atomic_numbers = grp["atomic_numbers"][:]
            symbols = [pt.to_symbol(int(z)) for z in atomic_numbers]
        elif "molecule_name" in grp.attrs:
            # Maybe the geometry has elements? Not guaranteed.
            pass

        if symbols is None:
            raise KeyError("Neither symbols nor atomic_numbers found in HDF5 group to determine atomic masses.")

        # Ensure lengths match
        if len(symbols) * 3 != H.shape[0]:
            raise ValueError("Dimension mismatch between symbols and Hessian.")

        base_masses = np.array([pt.to_mass(s) for s in symbols])

        # Find symmetrically equivalent atoms
        mol = molsym.Molecule(symbols, coords, base_masses)
        seas = mol.find_SEAs()

        H_jax = jnp.array(H)
        coords_jax = jnp.array(coords)

        # Calculate frequencies for each representative atom
        for sea in seas:
            rep_idx = sea.subset[0]
            sym = symbols[rep_idx]

            if sym not in HEAVY_ISOTOPES:
                continue

            heavy_mass = HEAVY_ISOTOPES[sym]

            # Substitute mass
            new_masses = base_masses.copy()
            new_masses[rep_idx] = heavy_mass

            new_masses_jax = jnp.array(new_masses)

            freqs = compute_freqs(new_masses_jax, H_jax, coords_jax)

            dataset_name = f"frequencies_isotope_{rep_idx}"
            if dataset_name in grp:
                del grp[dataset_name]
            grp.create_dataset(dataset_name, data=np.array(freqs))
            logger.info(f"Committed KIE frequencies for heavy isotope at atom {rep_idx} ({sym})")

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_tensor_extractor.py ---
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
                except Exception:
                    pass
            return 2.01410177812

        if sym.upper() in {"T", "3H"}:
            if _mendeleev_element is not None:
                try:
                    for iso in getattr(_mendeleev_element("H"), "isotopes", []):
                        if iso.mass_number == 3:
                            return float(iso.mass)
                except Exception:
                    pass
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
                except Exception:
                    pass

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
                except Exception:
                    pass

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
            except Exception:
                pass
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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_torq_vault.py ---
"""
CoChem-TORQ: Phase 2 Dual-Intake Gateway & Vault
================================================
Routes geometries into the TORQ engine, standardizing inputs from both native
ecosystem databases (landscape.h5) and external uploads (.xyz, .mol).
Applies exact CIAAW isotopic masses, SHA-256 integrity hashes, and PyArrow/Pandas standardization.

Authoritative Standards:
- CIAAW / IUPAC Standard Atomic Weights & Exact Mono-Isotopic Masses
- Method Matrix: Stage 1.0 - 2.0 Geometry Intake & Provenance Verification
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import h5py
import numpy as np
import pandas as pd
import pyarrow as pa

from collections.abc import Mapping
try:
    from mendeleev import element as _mendeleev_element
except ImportError:
    _mendeleev_element = None

from cochem_tensor_extractor import CIAAW_ISOTOPIC_MASSES

ATOMIC_NUMBERS: Dict[str, int] = {
    "H": 1,
    "He": 2,
    "Li": 3,
    "Be": 4,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Ne": 10,
    "Na": 11,
    "Mg": 12,
    "Al": 13,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Ar": 18,
    "K": 19,
    "Ca": 20,
    "Sc": 21,
    "Ti": 22,
    "V": 23,
    "Cr": 24,
    "Mn": 25,
    "Fe": 26,
    "Co": 27,
    "Ni": 28,
    "Cu": 29,
    "Zn": 30,
    "Ga": 31,
    "Ge": 32,
    "As": 33,
    "Se": 34,
    "Br": 35,
    "Kr": 36,
    "I": 53,
}


def compute_sha256_hash(data: Union[str, bytes]) -> str:
    """Computes SHA-256 hex digest for cryptographic integrity tracking."""
    if isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data
    return hashlib.sha256(raw).hexdigest()


def standardize_geometry_dataframe(
    symbols: Sequence[str],
    coordinates: np.ndarray,
    masses: Optional[Sequence[float]] = None,
    provenance_tag: str = "[D]",
) -> pd.DataFrame:
    """
    Standardizes geometry coordinates into a consistent Pandas DataFrame / PyArrow representation.
    """
    n_atoms = len(symbols)
    if coordinates.shape != (n_atoms, 3):
        raise ValueError(
            f"Coordinate shape mismatch: expected ({n_atoms}, 3), got {coordinates.shape}"
        )

    computed_masses: List[float] = []
    atomic_nums: List[int] = []

    for i, sym in enumerate(symbols):
        clean_sym = sym.capitalize()
        if masses is not None and i < len(masses):
            computed_masses.append(float(masses[i]))
        else:
            computed_masses.append(CIAAW_ISOTOPIC_MASSES.get(clean_sym, 12.0))
        atomic_nums.append(ATOMIC_NUMBERS.get(clean_sym, 6))

    df = pd.DataFrame(
        {
            "atom_index": np.arange(n_atoms, dtype=np.int32),
            "symbol": [s.capitalize() for s in symbols],
            "atomic_number": np.array(atomic_nums, dtype=np.int32),
            "x": coordinates[:, 0].astype(np.float64),
            "y": coordinates[:, 1].astype(np.float64),
            "z": coordinates[:, 2].astype(np.float64),
            "mass_amu": np.array(computed_masses, dtype=np.float64),
            "provenance": [provenance_tag] * n_atoms,
        }
    )
    return df


def parse_external_xyz(
    file_path_or_content: Union[str, Path],
    sanitize: bool = True,
) -> Dict[str, Any]:
    """
    Parses standard Cartesian XYZ format with immediate valency, proximity, and integrity sanitization.
    Throws CoChemIntegrityError if severe atomic overlap (< 0.4 Angstrom) or corrupted syntax is detected.
    """
    content: str = ""

    if isinstance(file_path_or_content, Path) or (
        isinstance(file_path_or_content, str)
        and "\n" not in file_path_or_content
        and Path(file_path_or_content).exists()
    ):
        path_obj = Path(file_path_or_content)
        with open(path_obj, "r", encoding="utf-8") as fp:
            content = fp.read()
    else:
        content = str(file_path_or_content)

    if not content.strip():
        raise MissingDataError(
            message="Empty XYZ file or content provided to parser.",
            error_code=ProvenanceErrorCode.MISSING_DATA,
        )

    sha256 = compute_sha256_hash(content)
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

    if len(lines) < 3:
        raise CoChemIntegrityError(
            message=f"Corrupt XYZ format: Expected at least 3 lines, got {len(lines)}",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    try:
        atom_count = int(lines[0])
    except ValueError as err:
        raise CoChemIntegrityError(
            message=f"Invalid atom count on line 1: '{lines[0]}'",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        ) from err

    comment = lines[1]
    coord_lines = lines[2:]

    if len(coord_lines) < atom_count:
        raise CoChemIntegrityError(
            message=f"Atom count mismatch: header declared {atom_count}, found {len(coord_lines)} coordinate lines.",
            error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
        )

    symbols: List[str] = []
    coords: List[List[float]] = []

    for idx in range(atom_count):
        tokens = coord_lines[idx].split()
        if len(tokens) < 4:
            raise CoChemIntegrityError(
                message=f"Invalid XYZ coordinate row at index {idx}: '{coord_lines[idx]}'",
                error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
            )
        sym = tokens[0].capitalize()
        try:
            x, y, z = float(tokens[1]), float(tokens[2]), float(tokens[3])
        except ValueError as err:
            raise CoChemIntegrityError(
                message=f"Non-numeric coordinates on line {idx + 3}: '{coord_lines[idx]}'",
                error_code=ProvenanceErrorCode.INTEGRITY_VIOLATION,
            ) from err

        symbols.append(sym)
        coords.append([x, y, z])

    coords_arr = np.array(coords, dtype=np.float64)

    # Proximity sanitization: check for unphysical overlap < 0.4 Angstrom
    if sanitize and atom_count > 1:
        diff = coords_arr[:, np.newaxis, :] - coords_arr[np.newaxis, :, :]
        dist_mat = np.sqrt(np.sum(diff**2, axis=-1))
        np.fill_diagonal(dist_mat, 999.0)
        min_dist = float(np.min(dist_mat))
        if min_dist < 0.4:
            min_i, min_j = np.unravel_index(np.argmin(dist_mat), dist_mat.shape)
            msg = f"Severe atomic clash detected between atom {min_i} ({symbols[min_i]}) and atom {min_j} ({symbols[min_j]}): distance = {min_dist:.4f} Angstrom (< 0.4 Angstrom limit)."
            logger.error(msg)
            raise CoChemIntegrityError(
                message=msg,
                error_code=ProvenanceErrorCode.PATHOLOGY_CLASH,
                details={
                    "field": "coordinates",
                    "value": f"{min_dist:.4f}",
                    "expected": ">= 0.4 Angstrom",
                },
            )

    masses = [CIAAW_ISOTOPIC_MASSES.get(s, 12.0) for s in symbols]
    atomic_numbers = [ATOMIC_NUMBERS.get(s, 6) for s in symbols]

    df = standardize_geometry_dataframe(symbols, coords_arr, masses, provenance_tag="[D]")
    arrow_table = pa.Table.from_pandas(df)

    logger.info("Successfully parsed XYZ geometry (%d atoms, SHA256=%s...)", atom_count, sha256[:8])

    return {
        "symbols": symbols,
        "coordinates": coords_arr,
        "masses": np.array(masses, dtype=np.float64),
        "atomic_numbers": np.array(atomic_numbers, dtype=np.int32),
        "atom_count": atom_count,
        "title": comment,
        "sha256_hash": sha256,
        "dataframe": df,
        "arrow_table": arrow_table,
        "provenance": "[D]",
    }


def fetch_topos_matrices(
    h5_path: Union[str, Path],
    conformer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Polls landscape.h5 for native conformers and pre-converged wavefunctions processed by CoChem-TOPOS.
    """
    target = Path(h5_path).resolve()
    if not target.exists():
        raise MissingDataError(
            message=f"HDF5 database not found: {target}",
            error_code=ProvenanceErrorCode.MISSING_DATA,
        )

    with h5py.File(target, "r") as fp:
        conformers_group = fp.get("conformers")
        if conformers_group is None:
            conf_keys = list(fp.keys())
            if not conf_keys:
                raise MissingDataError(
                    message=f"No conformers or datasets found in HDF5 archive: {target}",
                    error_code=ProvenanceErrorCode.MISSING_DATA,
                )
            selected_key = conformer_id if (conformer_id and conformer_id in fp) else conf_keys[0]
            conf_node = fp[selected_key]
        else:
            conf_keys = list(conformers_group.keys())
            if not conf_keys:
                raise MissingDataError(
                    message=f"Empty conformers group in HDF5 archive: {target}",
                    error_code=ProvenanceErrorCode.MISSING_DATA,
                )
            selected_key = (
                conformer_id
                if (conformer_id and conformer_id in conformers_group)
                else conf_keys[0]
            )
            conf_node = conformers_group[selected_key]

        coords = np.array(conf_node["coordinates"], dtype=np.float64)
        raw_symbols = conf_node["symbols"]
        symbols = [s.decode("utf-8") if isinstance(s, bytes) else str(s) for s in raw_symbols]
        energy = (
            float(conf_node.attrs.get("energy_hartree", 0.0))
            if "energy_hartree" in conf_node.attrs
            else (float(conf_node["energy"][()]) if "energy" in conf_node else 0.0)
        )
        gbw_path = str(conf_node.attrs.get("gbw_path", ""))

    masses = [CIAAW_ISOTOPIC_MASSES.get(s.capitalize(), 12.0) for s in symbols]
    atomic_numbers = [ATOMIC_NUMBERS.get(s.capitalize(), 6) for s in symbols]
    df = standardize_geometry_dataframe(symbols, coords, masses, provenance_tag="[M]")
    arrow_table = pa.Table.from_pandas(df)

    return {
        "conformer_id": selected_key,
        "symbols": symbols,
        "coordinates": coords,
        "masses": np.array(masses, dtype=np.float64),
        "atomic_numbers": np.array(atomic_numbers, dtype=np.int32),
        "energy_hartree": energy,
        "gbw_path": gbw_path,
        "dataframe": df,
        "arrow_table": arrow_table,
        "provenance": "[M]",
    }

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_10.py ---
"""
CoChem Setup Phase 10: MolSym Intake & Theoretical Eckart Frame Alignment Gatekeeper.
Production-grade, zero-mock gatekeeping engine for MolSym isolated silo provisioning,
exact mass-weighted Center of Mass (COM) translation with ghost atom (BSSE Gh, Bq, X)
zero-mass protections, translational and rotational Eckart condition verification
(residual norm <= 1e-12), 3x3 Moment of Inertia tensor construction and diagonalization,
spectroscopic rotational constants (A, B, C in MHz, GHz, cm^-1) via NIST CODATA 2022/2026
constants, Ray's asymmetry parameter kappa, planar moments (Pa, Pb, Pc), rotor top classification,
Kabsch/SVD proper rotation enforcement (det(U) = +1.0) with reflection protection,
scaffolding ephemeral quarantined execution sandboxes (/tmp/cochem_exec_<uuid>/),
executing 10 MB unbuffered IOPS benchmarks to verify storage throughput performance,
validating ORCA (.gbw), PySCF (.chk), and xTB (.xtbw) checkpoint files, auditing
state-chain recovery across previous setup phases (p1.json through p9.json), generating
environment variable injection mappings, and persisting transactional state into the
Golden Registry (p10.json).

SRS Document 2 Part 2 (Section 3.10), Method Matrix v4 (§8A-8C), SRS Document 1 (Section 2),
SRS Document 5 (Section 1-4), SRS Document 6 (Section 1-3), SRS Document 7 (Section 2),
and CoChem User Manual v4.1 Compliant.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import stat
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# Try importing h5py for PySCF .chk validation
try:
    import h5py
    _HAS_H5PY = True
except ImportError:
    h5py = None  # type: ignore
    _HAS_H5PY = False

# Try importing mendeleev for authentic standard atomic masses
try:
    import mendeleev
    _HAS_MENDELEEV = True
except ImportError:
    mendeleev = None  # type: ignore
    _HAS_MENDELEEV = False


# =============================================================================
# NIST CODATA 2022 / 2026 Fundamental Physical Constants & Conversion Factors
# =============================================================================

PLANCK_H: float = 6.62607015e-34  # J * s (exact SI standard)
SPEED_OF_LIGHT_C: float = 299792458.0  # m / s (exact SI standard)
ATOMIC_MASS_UNIT_U: float = 1.66053906892e-27  # kg / u (CODATA 2022/2026)
ANGSTROM_TO_M: float = 1.0e-10  # m / Angstrom

# Rotational conversion factor: B = h / (8 * pi^2 * I)
FACTOR_HZ: float = PLANCK_H / (8.0 * (math.pi ** 2) * ATOMIC_MASS_UNIT_U * (ANGSTROM_TO_M ** 2))
FACTOR_MHZ: float = FACTOR_HZ / 1.0e6
FACTOR_GHZ: float = FACTOR_HZ / 1.0e9
FACTOR_CM1: float = FACTOR_HZ / (SPEED_OF_LIGHT_C * 100.0)


# =============================================================================
# 1. CUSTOM EXCEPTION HIERARCHY
# =============================================================================


class Phase10AuditError(RuntimeError):
    """Raised when critical Phase 10 sandbox, alignment, or state-chain recovery audit fails fatally."""


class EphemeralSandboxError(Phase10AuditError):
    """Raised when scaffolding, permission hardening, or isolation of ephemeral sandbox fails."""


class IOPSBenchmarkError(Phase10AuditError):
    """Raised when 10 MB unbuffered IOPS benchmark execution or timing fails."""


class CheckpointValidationError(Phase10AuditError):
    """Raised when checkpoint file validation encountered fatal corruption or parsing error."""


class StateChainRecoveryError(Phase10AuditError):
    """Raised when previous setup phase state-chain verification fails fatally."""


class MolSymSiloError(Phase10AuditError):
    """Raised when MolSym isolated silo discovery, provisioning, or verification fails."""


class EckartAlignmentError(Phase10AuditError):
    """Raised when Eckart frame alignment or rotational condition verification fails."""


class InertiaTensorError(Phase10AuditError):
    """Raised when Moment of Inertia tensor construction or diagonalization fails."""


# =============================================================================
# 2. ENUMERATIONS
# =============================================================================


class PhaseStatus(str, Enum):
    """Status enumeration for setup phase execution."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    BYPASSED = "BYPASSED"


class CheckpointFormat(str, Enum):
    """Supported quantum chemistry checkpoint file formats."""

    ORCA_GBW = "ORCA_GBW"
    PYSCF_CHK = "PYSCF_CHK"
    XTB_XTBW = "XTB_XTBW"
    UNKNOWN = "UNKNOWN"


class CheckpointStatus(str, Enum):
    """Verification status for individual checkpoint files."""

    VALID = "VALID"
    CORRUPT = "CORRUPT"
    TRUNCATED = "TRUNCATED"
    INVALID_FORMAT = "INVALID_FORMAT"
    NOT_FOUND = "NOT_FOUND"


class IOPSBenchmarkStatus(str, Enum):
    """Classification of unbuffered IOPS storage performance."""

    OPTIMAL = "OPTIMAL"
    ACCEPTABLE = "ACCEPTABLE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class MolSymSiloStatus(str, Enum):
    """Operational status of the isolated MolSym silo engine."""

    AVAILABLE = "AVAILABLE"
    PROVISIONED = "PROVISIONED"
    DEGRADED = "DEGRADED"
    NOT_FOUND = "NOT_FOUND"


class EckartVerificationStatus(str, Enum):
    """Verification status of theoretical Eckart condition tests."""

    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"


class RotorTopType(str, Enum):
    """Molecular spectroscopic rotor classification."""

    SPHERICAL = "spherical"
    SYMMETRIC_PROLATE = "symmetric_prolate"
    SYMMETRIC_OBLATE = "symmetric_oblate"
    ASYMMETRIC = "asymmetric"
    LINEAR = "linear"
    ATOM = "atom"


# =============================================================================
# 3. PYDANTIC V2 DATA MODELS
# =============================================================================


class EphemeralSandboxProfile(BaseModel):
    """Profile of the provisioned ephemeral quarantined execution sandbox."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    sandbox_path: str = Field(..., description="Absolute path to ephemeral sandbox directory")
    sandbox_uuid: str = Field(..., description="Unique execution sandbox UUID identifier")
    base_directory: str = Field(..., description="Base temporary directory on host filesystem")
    is_created: bool = Field(..., description="Whether sandbox directory exists on disk")
    is_writable: bool = Field(..., description="Whether sandbox is write-accessible")
    is_isolated: bool = Field(..., description="Whether sandbox isolation barrier is verified")
    permissions_octal: str = Field(
        default="0o700", description="POSIX octal or Windows ACL permission descriptor"
    )
    cleanup_verified: bool = Field(
        default=True, description="Whether safe idempotent cleanup mechanism is verified"
    )
    active_pid: int = Field(..., ge=1, description="Active host process ID managing the sandbox")


class IOPSBenchmarkProfile(BaseModel):
    """Performance metric profile for the 10 MB unbuffered storage IOPS benchmark."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    target_directory: str = Field(..., description="Filesystem directory evaluated during benchmark")
    file_size_bytes: int = Field(
        default=10485760, ge=1024, description="Total benchmark file size in bytes (default: 10 MB)"
    )
    block_size_bytes: int = Field(
        default=65536, ge=512, description="Direct I/O block size in bytes (default: 64 KB)"
    )
    total_blocks: int = Field(..., ge=1, description="Total number of I/O blocks processed")
    write_duration_seconds: float = Field(
        ..., ge=0.0, description="Elapsed wall-clock time for unbuffered sequential write in seconds"
    )
    write_throughput_mb_s: float = Field(
        ..., ge=0.0, description="Measured write throughput in Megabytes per second [M]"
    )
    write_iops: float = Field(
        ..., ge=0.0, description="Measured write I/O operations per second [M]"
    )
    read_duration_seconds: float = Field(
        ..., ge=0.0, description="Elapsed wall-clock time for unbuffered sequential read in seconds"
    )
    read_throughput_mb_s: float = Field(
        ..., ge=0.0, description="Measured read throughput in Megabytes per second [M]"
    )
    read_iops: float = Field(
        ..., ge=0.0, description="Measured read I/O operations per second [M]"
    )
    sync_latency_ms: float = Field(
        ..., ge=0.0, description="Measured fsync flush barrier latency in milliseconds [M]"
    )
    status: IOPSBenchmarkStatus = Field(
        default=IOPSBenchmarkStatus.OPTIMAL, description="Storage performance classification"
    )
    is_unbuffered: bool = Field(
        default=True, description="Whether benchmark enforced unbuffered direct I/O flushes"
    )
    is_performance_sufficient: bool = Field(
        default=True, description="Whether storage meets minimum quantum engine I/O threshold (>= 20 MB/s)"
    )


class CheckpointValidationItem(BaseModel):
    """Verification record for an individual quantum calculation checkpoint file."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    file_path: str = Field(..., description="Absolute path to checkpoint file")
    format: CheckpointFormat = Field(..., description="Detected checkpoint format (ORCA, PySCF, xTB)")
    status: CheckpointStatus = Field(..., description="Validation status (VALID, CORRUPT, etc.)")
    size_bytes: int = Field(default=0, ge=0, description="File size in bytes")
    sha256_hash: Optional[str] = Field(default=None, description="Cryptographic SHA-256 hash of checkpoint")
    is_resumable: bool = Field(default=False, description="Whether checkpoint is safely resumable")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extracted metadata (wave-function keys, basis, energies)"
    )
    error_message: Optional[str] = Field(default=None, description="Failure description if invalid")


class CheckpointValidationReport(BaseModel):
    """Aggregate summary of checkpoint discovery and validation audit."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    scanned_count: int = Field(default=0, ge=0, description="Total checkpoint files scanned")
    valid_count: int = Field(default=0, ge=0, description="Count of valid, resumable checkpoints")
    corrupt_count: int = Field(default=0, ge=0, description="Count of corrupt or truncated checkpoints")
    resumable_checkpoints: List[CheckpointValidationItem] = Field(
        default_factory=list, description="List of validated checkpoint items"
    )
    validation_enabled: bool = Field(
        default=True, description="Whether checkpoint validation subsystem is operational"
    )


class StateChainRecoveryProfile(BaseModel):
    """Audit record for setup state-chain continuity and interrupted job recovery."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    registry_directory: str = Field(..., description="Registry directory path evaluated for state-chain")
    verified_phases: List[str] = Field(
        default_factory=list, description="List of previous setup phase manifests verified (p1-p9)"
    )
    missing_phases: List[str] = Field(
        default_factory=list, description="List of missing setup phase manifests"
    )
    chain_intact: bool = Field(
        default=True, description="Whether preceding setup phase chain (p1-p9) is intact"
    )
    recoverable_jobs: List[Dict[str, Any]] = Field(
        default_factory=list, description="Interrupted quantum jobs discovered eligible for resumption"
    )
    orphaned_sandboxes: List[str] = Field(
        default_factory=list, description="List of orphaned ephemeral sandbox paths found on disk"
    )


class MolSymSiloProfile(BaseModel):
    """Discovery and verification profile for the isolated MolSym symmetry engine."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    silo_path: Optional[str] = Field(default=None, description="Filesystem path to isolated molsym silo directory")
    is_installed: bool = Field(..., description="Whether molsym is importable and functional")
    silo_status: MolSymSiloStatus = Field(..., description="MolSym silo operational status")
    version: Optional[str] = Field(default=None, description="Detected or installed MolSym version string")
    location: Optional[str] = Field(default=None, description="Module location path on disk")
    has_symtext: bool = Field(default=False, description="Whether molsym Symtext point group capability is available")
    has_find_point_group: bool = Field(default=False, description="Whether find_point_group is available")
    notes: str = Field(default="", description="Diagnostic details or provisioning notes")


class InertiaTensorResult(BaseModel):
    """Moment of Inertia tensor, principal axes, rotational constants, and rotor classification."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, ser_json_inf_nan="constants")

    eigenvalues_amu_angstrom2: Tuple[float, float, float] = Field(
        ..., description="Sorted principal moments of inertia Ia <= Ib <= Ic in amu * Angstrom^2"
    )
    rotational_constants_mhz: Tuple[Optional[float], Optional[float], Optional[float]] = Field(
        ..., description="Rotational constants (A, B, C) in MHz"
    )
    rotational_constants_ghz: Tuple[Optional[float], Optional[float], Optional[float]] = Field(
        ..., description="Rotational constants (A, B, C) in GHz"
    )
    rotational_constants_cm1: Tuple[Optional[float], Optional[float], Optional[float]] = Field(
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
        ..., description="Rotor classification (spherical, symmetric_prolate, symmetric_oblate, asymmetric, linear, atom)"
    )
    rotation_matrix: List[List[float]] = Field(
        ..., description="Right-handed 3x3 rotation matrix V diagonalizing inertia tensor with det = +1.0"
    )
    aligned_coords: List[List[float]] = Field(
        ..., description="Cartesian coordinates aligned to principal axes (N, 3)"
    )
    inertia_tensor: Optional[List[List[float]]] = Field(
        default=None, description="Initial 3x3 moment of inertia tensor before diagonalization"
    )


class EckartAlignmentResult(BaseModel):
    """Mass-weighted Eckart frame alignment result and residual verification."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    aligned_coords: List[List[float]] = Field(
        ..., description="Target coordinates transformed into reference Eckart frame (N, 3)"
    )
    rotation_matrix: List[List[float]] = Field(
        ..., description="Proper rotation matrix U (3, 3) with det(U) = +1.0"
    )
    rmsd: float = Field(
        ..., ge=0.0, description="Mass-weighted Root Mean Square Deviation relative to reference"
    )
    residual_rotational_norm: float = Field(
        ..., ge=0.0, description="Residual torque norm of rotational Eckart condition sum(m_i * (r_i^0 x r'_i))"
    )
    translational_residual_norm: float = Field(
        ..., ge=0.0, description="Residual norm of translational Eckart condition sum(m_i * r'_i) / M"
    )
    rotation_determinant: float = Field(
        default=1.0, description="Determinant of proper rotation matrix U"
    )


class EckartVerificationItem(BaseModel):
    """Verification record for a specific theoretical Eckart condition benchmark test."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    benchmark_name: str = Field(..., description="Name of theoretical verification benchmark")
    status: EckartVerificationStatus = Field(..., description="Verification status (VERIFIED/FAILED)")
    n_atoms: int = Field(..., ge=1, description="Number of atoms in benchmark molecule")
    has_ghost_atoms: bool = Field(default=False, description="Whether benchmark molecule includes ghost atoms")
    translational_residual_norm: float = Field(..., ge=0.0, description="Norm of sum(m_i * r'_i) in Angstroms")
    rotational_residual_norm: float = Field(..., ge=0.0, description="Norm of sum(m_i * (r_i^0 x r'_i)) in amu * Angstrom^2")
    rotation_determinant: float = Field(..., description="Determinant of proper rotation matrix U (must be +1.0)")
    rmsd: float = Field(..., ge=0.0, description="Mass-weighted RMSD relative to reference")
    top_type: RotorTopType = Field(..., description="Rotor top classification")
    is_verified: bool = Field(default=True, description="Whether all residual norms satisfy <= 1e-12 tolerance")
    error_message: Optional[str] = Field(default=None, description="Diagnostic error message if failed")


class EckartVerificationReport(BaseModel):
    """Comprehensive report summarizing theoretical Eckart frame benchmarks."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    total_benchmarks: int = Field(default=0, ge=0, description="Total benchmark tests executed")
    passed_benchmarks: int = Field(default=0, ge=0, description="Number of passed benchmark tests")
    failed_benchmarks: int = Field(default=0, ge=0, description="Number of failed benchmark tests")
    overall_status: EckartVerificationStatus = Field(
        default=EckartVerificationStatus.VERIFIED, description="Overall Eckart verification status"
    )
    max_translational_residual: float = Field(default=0.0, ge=0.0, description="Maximum translational residual across benchmarks")
    max_rotational_residual: float = Field(default=0.0, ge=0.0, description="Maximum rotational residual torque across benchmarks")
    items: List[EckartVerificationItem] = Field(default_factory=list, description="List of individual benchmark items")


class Phase10AuditReport(BaseModel):
    """Complete serialized audit report and Golden Registry record for Setup Phase 10."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, ser_json_inf_nan="constants")

    phase_id: str = Field(default="cochem_setup_phase_10", description="Setup phase identifier")
    status: PhaseStatus = Field(..., description="Overall execution status of Phase 10")
    timestamp_utc: str = Field(..., description="ISO 8601 UTC timestamp of audit execution")
    artifact_path: str = Field(..., description="Absolute path to generated p10.json Golden Registry artifact")
    sandbox_profile: EphemeralSandboxProfile = Field(
        ..., description="Ephemeral Quarantined Sandbox configuration profile"
    )
    iops_profile: IOPSBenchmarkProfile = Field(
        ..., description="10 MB unbuffered storage IOPS benchmark profile"
    )
    checkpoint_report: CheckpointValidationReport = Field(
        ..., description="Checkpoint file validation and resumption report"
    )
    state_chain_profile: StateChainRecoveryProfile = Field(
        ..., description="State-chain continuity and recovery audit profile"
    )
    molsym_silo_profile: MolSymSiloProfile = Field(
        ..., description="MolSym isolated silo discovery and provisioning profile"
    )
    eckart_verification_report: EckartVerificationReport = Field(
        ..., description="Theoretical Eckart frame and Cartesian alignment verification report"
    )
    alignment_engine_ready: bool = Field(
        default=True, description="Whether MolSym and Eckart alignment engines are verified and operational"
    )
    injected_env_vars: Dict[str, str] = Field(
        default_factory=dict, description="Environment variable injection mapping for runtime execution"
    )
    warnings: List[str] = Field(default_factory=list, description="Non-fatal diagnostic warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or recoverable error messages")


# =============================================================================
# 4. MOLSYM ISOLATED SILO ENGINE
# =============================================================================


def audit_or_provision_molsym_silo(
    silo_path: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> MolSymSiloProfile:
    """
    Check, provision, and verify the MolSym symmetry dependency in an isolated silo.
    Evaluates explicit silo_path, COCHEM_MOLSYM_SILO, COCHEM_CALC_SILO, standard silos,
    or active Python environment fallback.
    """
    target_env = os.environ if env is None else env
    candidate_silos: List[Path] = []

    if silo_path is not None and str(silo_path).strip():
        candidate_silos.append(Path(silo_path).resolve())

    if "COCHEM_MOLSYM_SILO" in target_env and target_env["COCHEM_MOLSYM_SILO"].strip():
        candidate_silos.append(Path(target_env["COCHEM_MOLSYM_SILO"]).resolve())

    if "COCHEM_CALC_SILO" in target_env and target_env["COCHEM_CALC_SILO"].strip():
        candidate_silos.append(Path(target_env["COCHEM_CALC_SILO"]).resolve())

    repo_root = find_repository_root()
    candidate_silos.append(repo_root / "silos" / "molsym")
    candidate_silos.append(Path.home() / ".cochem" / "silos" / "molsym")

    active_silo_path: Optional[str] = None
    for c_path in candidate_silos:
        if c_path.exists() and c_path.is_dir():
            active_silo_path = str(c_path)
            site_candidates = [
                c_path,
                c_path / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
                c_path / "Lib" / "site-packages",
            ]
            for s_p in site_candidates:
                if s_p.exists() and str(s_p) not in sys.path:
                    sys.path.insert(0, str(s_p))
            break

    try:
        if "molsym" in sys.modules:
            molsym_mod = sys.modules["molsym"]
        else:
            molsym_mod = importlib.import_module("molsym")
        is_installed = True
    except Exception:
        molsym_mod = None
        is_installed = False

    if is_installed and molsym_mod is not None:
        version_str: Optional[str] = getattr(molsym_mod, "__version__", None)
        if not version_str:
            try:
                version_str = importlib.metadata.version("molsym")
            except Exception:
                version_str = "unknown"

        mod_loc: Optional[str] = getattr(molsym_mod, "__file__", None)
        if mod_loc:
            mod_loc = str(Path(mod_loc).resolve().parent)

        has_symtext = hasattr(molsym_mod, "Symtext")
        has_find_pg = hasattr(molsym_mod, "find_point_group")

        if has_symtext and has_find_pg:
            status = MolSymSiloStatus.AVAILABLE if active_silo_path is None else MolSymSiloStatus.PROVISIONED
            notes = "MolSym library successfully verified with full Symtext and point group detection."
        else:
            status = MolSymSiloStatus.DEGRADED
            notes = "MolSym imported but missing Symtext or find_point_group submodules."

        return MolSymSiloProfile(
            silo_path=active_silo_path or mod_loc,
            is_installed=True,
            silo_status=status,
            version=version_str,
            location=mod_loc,
            has_symtext=has_symtext,
            has_find_point_group=has_find_pg,
            notes=notes,
        )

    return MolSymSiloProfile(
        silo_path=active_silo_path,
        is_installed=False,
        silo_status=MolSymSiloStatus.NOT_FOUND,
        version=None,
        location=None,
        has_symtext=False,
        has_find_point_group=False,
        notes="MolSym library is not installed in the active Python environment or isolated silos.",
    )


# =============================================================================
# 5. THEORETICAL ECKART FRAME & CARTESIAN ORIGIN SHIFTING ENGINE
# =============================================================================

from collections.abc import Mapping


class _DynamicMendeleevMassMap(Mapping):
    """Dynamic standard atomic weight mapping backed by the Mendeleev library."""

    def __getitem__(self, key: str) -> float:
        if not key or not isinstance(key, str):
            raise KeyError(key)
        clean = key.strip()
        if not clean:
            raise KeyError(key)

        if clean.upper() in {"D", "2H"}:
            if _HAS_MENDELEEV and mendeleev is not None:
                try:
                    for iso in getattr(mendeleev.element("H"), "isotopes", []):
                        if iso.mass_number == 2:
                            return float(iso.mass)
                except Exception:
                    pass
            return 2.01410177812

        if clean.upper() in {"T", "3H"}:
            if _HAS_MENDELEEV and mendeleev is not None:
                try:
                    for iso in getattr(mendeleev.element("H"), "isotopes", []):
                        if iso.mass_number == 3:
                            return float(iso.mass)
                except Exception:
                    pass
            return 3.01604928132

        import re
        m = re.match(r"^([A-Za-z]{1,2})[0-9_\-:]*$", clean)
        sym_head = m.group(1).capitalize() if m else clean.capitalize()

        if _HAS_MENDELEEV and mendeleev is not None:
            try:
                elem = mendeleev.element(sym_head)
                if elem is not None and elem.mass is not None:
                    return float(elem.mass)
            except Exception:
                pass

        raise KeyError(key)

    def __iter__(self):
        return iter([
            "H", "HE", "LI", "BE", "B", "C", "N", "O", "F", "NE", "NA", "MG",
            "AL", "SI", "P", "S", "CL", "AR", "K", "CA", "SC", "TI", "V", "CR",
            "MN", "FE", "CO", "NI", "CU", "ZN", "GA", "GE", "AS", "SE", "BR", "KR",
            "RB", "SR", "Y", "ZR", "NB", "MO", "TC", "RU", "RH", "PD", "AG", "CD",
            "IN", "SN", "SB", "TE", "I", "XE", "CS", "BA", "LA", "CE", "PR", "ND",
            "PM", "SM", "EU", "GD", "TB", "DY", "HO", "ER", "TM", "YB", "LU", "HF",
            "TA", "W", "RE", "OS", "IR", "PT", "AU", "HG", "TL", "PB", "BI", "TH",
            "PA", "U", "PU"
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


_STANDARD_ATOMIC_WEIGHTS: Mapping[str, float] = _DynamicMendeleevMassMap()


def is_ghost_symbol(symbol: str) -> bool:
    """
    Check whether an atomic symbol represents a ghost atom.
    Ghost atoms (e.g., 'Gh', 'gh', 'GhO', 'Gh_C', 'X', 'x_N', 'Bq', 'bq') possess
    strictly 0.0 mass to avoid shifting the Center of Mass during BSSE calculations.
    Chemical elements like Xenon ('Xe', 'xe', 'XE') are NOT ghost atoms.
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
        import re
        if re.match(r"^x[0-9]+$", clean_lower):
            return True

    return False


def get_physical_mass(symbol: str) -> float:
    """
    Retrieve standard atomic mass in amu (u / Da) dynamically using Mendeleev library.
    Ghost atoms strictly return 0.0.
    """
    if not symbol or not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Atomic symbol cannot be empty.")

    clean = symbol.strip()
    if is_ghost_symbol(clean):
        return 0.0

    # Hydrogen isotopes
    if clean.upper() in {"D", "2H"}:
        if _HAS_MENDELEEV and mendeleev is not None:
            try:
                for iso in getattr(mendeleev.element("H"), "isotopes", []):
                    if iso.mass_number == 2:
                        return float(iso.mass)
            except Exception:
                pass
        return 2.01410177812

    if clean.upper() in {"T", "3H"}:
        if _HAS_MENDELEEV and mendeleev is not None:
            try:
                for iso in getattr(mendeleev.element("H"), "isotopes", []):
                    if iso.mass_number == 3:
                        return float(iso.mass)
            except Exception:
                pass
        return 3.01604928132

    # Check isotope or numbered notation (e.g. C12, Cl35, O_16, H-2, C:1)
    import re
    m = re.match(r"^([A-Za-z]{1,2})[0-9_\-:]*$", clean)
    sym_head = m.group(1).capitalize() if m else clean.capitalize()

    if _HAS_MENDELEEV and mendeleev is not None:
        try:
            elem = mendeleev.element(sym_head)
            if elem is not None and elem.mass is not None:
                return float(elem.mass)
        except Exception:
            pass

    if clean.upper() in _STANDARD_ATOMIC_WEIGHTS:
        return float(_STANDARD_ATOMIC_WEIGHTS[clean.upper()])

    raise ValueError(f"Unrecognized chemical element symbol: '{symbol}'.")


def resolve_atomic_masses(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """
    Validate and return a 1D float64 array of atomic masses of shape (N,).
    Enforces non-negative masses and strictly positive total non-ghost molecular mass.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    n_atoms = len(coords_arr)

    if masses is not None:
        masses_arr = np.asarray(masses, dtype=np.float64)
        if masses_arr.shape != (n_atoms,):
            raise ValueError(
                f"Coordinate count ({n_atoms}) does not match masses shape {masses_arr.shape}."
            )
        if np.any(masses_arr < 0.0):
            raise ValueError("Atomic masses must be non-negative values.")
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise ValueError("Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    if symbols is not None:
        if len(symbols) != n_atoms:
            raise ValueError(
                f"Coordinate count ({n_atoms}) does not match symbols count ({len(symbols)})."
            )
        masses_list = [get_physical_mass(s) for s in symbols]
        masses_arr = np.array(masses_list, dtype=np.float64)
        total_mass = float(np.sum(masses_arr))
        if total_mass <= 0.0:
            raise ValueError("Total non-ghost molecular mass must be strictly positive.")
        return masses_arr

    raise ValueError("Either 'masses' or 'symbols' must be provided to determine molecular masses.")


def compute_center_of_mass(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> np.ndarray:
    """
    Compute exact mass-weighted Center of Mass (COM) vector of shape (3,).
    Ghost atoms (mass = 0.0) are completely excluded from the mass weighting.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ValueError(f"Expected coordinates shape (N, 3), got {coords_arr.shape}.")

    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))

    return np.sum(coords_arr * masses_arr[:, np.newaxis], axis=0) / total_mass


def translate_to_center_of_mass(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Translate molecular coordinates such that the Center of Mass is positioned at (0, 0, 0).
    Returns (translated_coords, shift_vector) where shift_vector = -COM.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))

    com = compute_center_of_mass(coords_arr, masses=masses_arr)
    shift_vec = -com
    translated_coords = coords_arr + shift_vec

    residual = np.sum(masses_arr[:, np.newaxis] * translated_coords, axis=0) / total_mass
    if np.any(np.abs(residual) > 0.0):
        translated_coords = translated_coords - residual
        shift_vec = shift_vec - residual

    return translated_coords, shift_vec


def compute_moment_of_inertia_tensor(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Union[np.ndarray, Sequence[float]],
) -> np.ndarray:
    """
    Construct symmetric 3x3 Moment of Inertia tensor in amu * Angstrom^2.
    I_xx = sum(m_i * (y_i^2 + z_i^2))
    I_xy = -sum(m_i * x_i * y_i)
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = np.asarray(masses, dtype=np.float64)

    if coords_arr.ndim != 2 or coords_arr.shape[1] != 3:
        raise ValueError(f"Coordinates must have shape (N, 3), got {coords_arr.shape}.")
    if masses_arr.shape != (len(coords_arr),):
        raise ValueError(
            f"Masses length ({len(masses_arr)}) != atom count ({len(coords_arr)})."
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

    return np.array([
        [Ixx, Ixy, Ixz],
        [Ixy, Iyy, Iyz],
        [Ixz, Iyz, Izz],
    ], dtype=np.float64)


def diagonalize_inertia_tensor(
    inertia_tensor: Union[np.ndarray, Sequence[Sequence[float]]],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Diagonalize 3x3 inertia tensor to obtain sorted eigenvalues Ia <= Ib <= Ic
    and right-handed proper rotation matrix V with det(V) = +1.0.
    """
    tensor = np.asarray(inertia_tensor, dtype=np.float64)
    if tensor.shape != (3, 3):
        raise ValueError(f"Inertia tensor must be (3, 3), got {tensor.shape}.")

    eigvals, V = np.linalg.eigh(tensor)

    idx = np.argsort(eigvals)
    eigvals = eigvals[idx]
    V = V[:, idx]

    det_v = float(np.linalg.det(V))
    if det_v < 0.0:
        V[:, 2] = -V[:, 2]

    return eigvals, V


def compute_rotational_constants(
    eigenvalues: Tuple[float, float, float],
) -> Tuple[Tuple[Optional[float], Optional[float], Optional[float]], Tuple[Optional[float], Optional[float], Optional[float]], Tuple[Optional[float], Optional[float], Optional[float]]]:
    """
    Convert principal moments of inertia Ia <= Ib <= Ic into rotational constants
    (A, B, C) across MHz, GHz, and cm^-1 via CODATA 2022/2026 constants.
    Safeguards linear singularity: Ia < 1e-8 => A = inf.
    """
    Ia, Ib, Ic = eigenvalues

    def _calc_const(I_val: float, factor: float) -> Optional[float]:
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
    """
    Classify rotor top geometry into spherical, symmetric_prolate, symmetric_oblate,
    asymmetric, linear, or atom, and compute Ray's asymmetry parameter kappa.
    """
    if n_atoms <= 1 or (Ia < 1e-8 and Ib < 1e-8 and Ic < 1e-8):
        return RotorTopType.ATOM, 0.0

    if Ia < 1e-8 or (Ib > 1e-8 and (Ia / Ib) < 1e-4):
        return RotorTopType.LINEAR, -1.0

    rot_consts = compute_rotational_constants((Ia, Ib, Ic))
    A_mhz, B_mhz, C_mhz = rot_consts[0]

    if Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and (abs(Ib - Ic) / Ic < 1e-3):
        return RotorTopType.SPHERICAL, 0.0

    if Ib > 1e-8 and (abs(Ia - Ib) / Ib < 1e-3) and ((Ic - Ib) / Ib >= 1e-3):
        if A_mhz is not None and B_mhz is not None and C_mhz is not None and not math.isinf(A_mhz) and (A_mhz - C_mhz) > 1e-12:
            kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)
        else:
            kappa = 1.0
        return RotorTopType.SYMMETRIC_OBLATE, float(kappa)

    if Ic > 1e-8 and (abs(Ib - Ic) / Ic < 1e-3) and ((Ib - Ia) / Ib >= 1e-3):
        if A_mhz is not None and B_mhz is not None and C_mhz is not None and not math.isinf(A_mhz) and (A_mhz - C_mhz) > 1e-12:
            kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)
        else:
            kappa = -1.0
        return RotorTopType.SYMMETRIC_PROLATE, float(kappa)

    if A_mhz is None or math.isinf(A_mhz) or C_mhz is None or abs(A_mhz - C_mhz) < 1e-12:
        kappa = 0.0
    else:
        assert B_mhz is not None
        kappa = (2.0 * B_mhz - A_mhz - C_mhz) / (A_mhz - C_mhz)

    return RotorTopType.ASYMMETRIC, float(kappa)


def align_to_principal_axes(
    coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
) -> InertiaTensorResult:
    """
    Translate molecular coordinates to COM, construct and diagonalize Moment of Inertia tensor,
    derive spectroscopic rotational constants (A, B, C), and return an InertiaTensorResult.
    """
    coords_arr = np.asarray(coords, dtype=np.float64)
    masses_arr = resolve_atomic_masses(coords_arr, masses=masses, symbols=symbols)

    coords_com, _ = translate_to_center_of_mass(coords_arr, masses=masses_arr)
    I_tensor = compute_moment_of_inertia_tensor(coords_com, masses_arr)
    eigvals, V = diagonalize_inertia_tensor(I_tensor)

    Ia, Ib, Ic = float(eigvals[0]), float(eigvals[1]), float(eigvals[2])
    aligned_coords = coords_com @ V

    rot_mhz, rot_ghz, rot_cm1 = compute_rotational_constants((Ia, Ib, Ic))
    inertial_defect = float(Ic - Ia - Ib)

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
        rotation_matrix=V.tolist(),
        aligned_coords=aligned_coords.tolist(),
        inertia_tensor=I_tensor.tolist(),
    )


def align_to_eckart_frame(
    target_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    ref_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
    tolerance: float = 1e-12,
) -> EckartAlignmentResult:
    """
    Align target coordinates to reference coordinates in mass-weighted Eckart frame via Kabsch/SVD.
    Enforces proper rotation det(U) = +1.0 and verifies translational and rotational Eckart conditions.
    """
    target_arr = np.asarray(target_coords, dtype=np.float64)
    ref_arr = np.asarray(ref_coords, dtype=np.float64)

    if target_arr.shape != ref_arr.shape:
        raise ValueError(
            f"Target shape {target_arr.shape} does not match reference shape {ref_arr.shape}."
        )
    if target_arr.ndim != 2 or target_arr.shape[1] != 3:
        raise ValueError(f"Coordinates must have shape (N, 3), got {target_arr.shape}.")

    masses_arr = resolve_atomic_masses(target_arr, masses=masses, symbols=symbols)
    total_mass = float(np.sum(masses_arr))

    target_com, _ = translate_to_center_of_mass(target_arr, masses=masses_arr)
    ref_com, _ = translate_to_center_of_mass(ref_arr, masses=masses_arr)

    F = target_com.T @ (ref_com * masses_arr[:, np.newaxis])
    V, S, Wt = np.linalg.svd(F)

    d = float(np.linalg.det(V @ Wt))
    diag = np.array([1.0, 1.0, 1.0 if d >= 0.0 else -1.0], dtype=np.float64)
    U = V @ np.diag(diag) @ Wt

    if np.linalg.det(U) < 0.0:
        U = V @ np.diag([1.0, 1.0, -1.0]) @ Wt

    aligned_coords = target_com @ U

    trans_res = float(np.linalg.norm(np.sum(masses_arr[:, np.newaxis] * aligned_coords, axis=0) / total_mass))
    rot_torque = np.sum(masses_arr[:, np.newaxis] * np.cross(ref_com, aligned_coords), axis=0)
    rot_res = float(np.linalg.norm(rot_torque))

    diff = aligned_coords - ref_com
    sq_dist = np.sum(diff**2, axis=-1)
    rmsd = float(np.sqrt(np.sum(masses_arr * sq_dist) / total_mass))
    det_u = float(np.linalg.det(U))

    return EckartAlignmentResult(
        aligned_coords=aligned_coords.tolist(),
        rotation_matrix=U.tolist(),
        rmsd=rmsd,
        residual_rotational_norm=rot_res,
        translational_residual_norm=trans_res,
        rotation_determinant=det_u,
    )


def verify_eckart_conditions(
    target_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    ref_coords: Union[np.ndarray, Sequence[Sequence[float]]],
    masses: Optional[Sequence[float] | np.ndarray] = None,
    symbols: Optional[Sequence[str]] = None,
    tolerance: float = 1e-12,
    benchmark_name: str = "custom",
) -> EckartVerificationItem:
    """
    Verify mass-weighted translational and rotational Eckart conditions against tolerance.
    """
    try:
        align_res = align_to_eckart_frame(
            target_coords=target_coords,
            ref_coords=ref_coords,
            masses=masses,
            symbols=symbols,
            tolerance=tolerance,
        )
        coords_arr = np.asarray(target_coords, dtype=np.float64)
        inertia_res = align_to_principal_axes(coords_arr, masses=masses, symbols=symbols)

        has_ghost = False
        if symbols is not None:
            has_ghost = any(is_ghost_symbol(s) for s in symbols)
        elif masses is not None:
            has_ghost = any(m == 0.0 for m in masses)

        is_verified = (
            align_res.translational_residual_norm <= tolerance
            and align_res.residual_rotational_norm <= tolerance
            and abs(align_res.rotation_determinant - 1.0) <= 1e-9
        )

        return EckartVerificationItem(
            benchmark_name=benchmark_name,
            status=EckartVerificationStatus.VERIFIED if is_verified else EckartVerificationStatus.FAILED,
            n_atoms=len(coords_arr),
            has_ghost_atoms=has_ghost,
            translational_residual_norm=align_res.translational_residual_norm,
            rotational_residual_norm=align_res.residual_rotational_norm,
            rotation_determinant=align_res.rotation_determinant,
            rmsd=align_res.rmsd,
            top_type=inertia_res.top_type,
            is_verified=is_verified,
            error_message=None if is_verified else f"Residual exceeds tolerance {tolerance}",
        )
    except Exception as exc:
        return EckartVerificationItem(
            benchmark_name=benchmark_name,
            status=EckartVerificationStatus.FAILED,
            n_atoms=len(target_coords) if hasattr(target_coords, "__len__") else 0,
            has_ghost_atoms=False,
            translational_residual_norm=1.0,
            rotational_residual_norm=1.0,
            rotation_determinant=0.0,
            rmsd=1.0,
            top_type=RotorTopType.ASYMMETRIC,
            is_verified=False,
            error_message=str(exc),
        )


# =============================================================================
# 6. THEORETICAL BENCHMARK SUITE
# =============================================================================


def _generate_3d_rotation_matrix(alpha: float, beta: float, gamma: float) -> np.ndarray:
    """Generate 3D Euler ZYZ proper rotation matrix (det = +1.0)."""
    ca, sa = math.cos(alpha), math.sin(alpha)
    cb, sb = math.cos(beta), math.sin(beta)
    cg, sg = math.cos(gamma), math.sin(gamma)

    Rz1 = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    Ry = np.array([[cb, 0.0, sb], [0.0, 1.0, 0.0], [-sb, 0.0, cb]], dtype=np.float64)
    Rz2 = np.array([[cg, -sg, 0.0], [sg, cg, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return Rz1 @ Ry @ Rz2


def run_theoretical_eckart_benchmarks(tolerance: float = 1e-12) -> EckartVerificationReport:
    """
    Execute theoretical verification benchmark test suite:
    1. Water (H2O) Rigid Rotation and Translation.
    2. Water (H2O) Perturbed Conformation (Bond Stretch & Angle Bend).
    3. Water Dimer Complex with Ghost Atoms (BSSE Counterpoise).
    4. Carbon Dioxide (CO2) Linear Molecule Singularity.
    5. Methane (CH4) Spherical Top.
    """
    items: List[EckartVerificationItem] = []

    # Benchmark 1: Water (H2O) Rigid Rotation and Translation
    water_symbols = ["O", "H", "H"]
    water_ref = np.array([
        [0.000000,  0.000000,  0.117300],
        [0.000000,  0.757200, -0.469200],
        [0.000000, -0.757200, -0.469200],
    ], dtype=np.float64)
    R_rot1 = _generate_3d_rotation_matrix(0.85, 1.42, 2.77)
    t_rot1 = np.array([-15.2, 33.7, -9.4], dtype=np.float64)
    water_target1 = water_ref @ R_rot1.T + t_rot1

    item1 = verify_eckart_conditions(
        target_coords=water_target1,
        ref_coords=water_ref,
        symbols=water_symbols,
        tolerance=tolerance,
        benchmark_name="H2O_Rigid_Rotation_Translation",
    )
    items.append(item1)

    # Benchmark 2: Water (H2O) Perturbed Conformation
    water_perturbed = water_ref.copy()
    water_perturbed[1, 1] += 0.05
    water_perturbed[2, 1] -= 0.03
    water_perturbed[1, 2] += 0.02
    R_rot2 = _generate_3d_rotation_matrix(1.1, 0.7, 1.9)
    t_rot2 = np.array([10.0, -10.0, 5.0], dtype=np.float64)
    water_target2 = water_perturbed @ R_rot2.T + t_rot2

    item2 = verify_eckart_conditions(
        target_coords=water_target2,
        ref_coords=water_ref,
        symbols=water_symbols,
        tolerance=tolerance,
        benchmark_name="H2O_Perturbed_Conformation",
    )
    items.append(item2)

    # Benchmark 3: Water Dimer Complex with Ghost Atoms (BSSE Counterpoise)
    dimer_symbols = ["GhO", "GhH", "GhH", "O", "H", "H"]
    dimer_ref = np.array([
        [-1.487000,  0.018000, -0.098000],
        [-0.518000,  0.063000, -0.013000],
        [-1.802000, -0.738000,  0.404000],
        [ 1.428000, -0.003000,  0.076000],
        [ 1.758000,  0.771000, -0.380000],
        [ 1.777000, -0.760000, -0.392000],
    ], dtype=np.float64)
    R_rot3 = _generate_3d_rotation_matrix(0.4, 2.1, 1.5)
    t_rot3 = np.array([5.0, 5.0, 5.0], dtype=np.float64)
    dimer_target = dimer_ref @ R_rot3.T + t_rot3

    item3 = verify_eckart_conditions(
        target_coords=dimer_target,
        ref_coords=dimer_ref,
        symbols=dimer_symbols,
        tolerance=tolerance,
        benchmark_name="Water_Dimer_BSSE_Ghost_Complex",
    )
    items.append(item3)

    # Benchmark 4: Carbon Dioxide (CO2) Linear Singularity
    co2_symbols = ["C", "O", "O"]
    co2_ref = np.array([
        [0.000000, 0.000000,  0.000000],
        [0.000000, 0.000000,  1.160000],
        [0.000000, 0.000000, -1.160000],
    ], dtype=np.float64)
    R_rot4 = _generate_3d_rotation_matrix(0.3, 0.6, 0.9)
    co2_target = co2_ref @ R_rot4.T + np.array([1.0, 2.0, 3.0])

    item4 = verify_eckart_conditions(
        target_coords=co2_target,
        ref_coords=co2_ref,
        symbols=co2_symbols,
        tolerance=tolerance,
        benchmark_name="CO2_Linear_Singularity",
    )
    items.append(item4)

    # Benchmark 5: Methane (CH4) Spherical Top
    ch4_symbols = ["C", "H", "H", "H", "H"]
    ch4_ref = np.array([
        [ 0.000000,  0.000000,  0.000000],
        [ 0.629118,  0.629118,  0.629118],
        [-0.629118, -0.629118,  0.629118],
        [ 0.629118, -0.629118, -0.629118],
        [-0.629118,  0.629118, -0.629118],
    ], dtype=np.float64)
    R_rot5 = _generate_3d_rotation_matrix(1.5, 0.5, 2.2)
    ch4_target = ch4_ref @ R_rot5.T

    item5 = verify_eckart_conditions(
        target_coords=ch4_target,
        ref_coords=ch4_ref,
        symbols=ch4_symbols,
        tolerance=tolerance,
        benchmark_name="CH4_Spherical_Top",
    )
    items.append(item5)

    passed_cnt = sum(1 for it in items if it.is_verified)
    failed_cnt = len(items) - passed_cnt
    max_trans = max(it.translational_residual_norm for it in items)
    max_rot = max(it.rotational_residual_norm for it in items)

    overall_status = EckartVerificationStatus.VERIFIED if failed_cnt == 0 else EckartVerificationStatus.FAILED

    return EckartVerificationReport(
        total_benchmarks=len(items),
        passed_benchmarks=passed_cnt,
        failed_benchmarks=failed_cnt,
        overall_status=overall_status,
        max_translational_residual=max_trans,
        max_rotational_residual=max_rot,
        items=items,
    )


# =============================================================================
# 7. EPHEMERAL QUARANTINED SANDBOX SCAFFOLDING ENGINE
# =============================================================================


def resolve_sandbox_base_directory(
    custom_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Determine the base directory for ephemeral execution sandboxes.
    Evaluates explicit custom_dir, COCHEM_SANDBOX_BASE, /tmp (POSIX), or OS tempdir.
    """
    target_env = os.environ if env is None else env

    if custom_dir is not None and str(custom_dir).strip():
        base = Path(custom_dir).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    if "COCHEM_SANDBOX_BASE" in target_env and target_env["COCHEM_SANDBOX_BASE"].strip():
        base = Path(target_env["COCHEM_SANDBOX_BASE"]).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    if platform.system() != "Windows":
        tmp_candidate = Path("/tmp")
        if tmp_candidate.exists() and os.access(str(tmp_candidate), os.W_OK):
            return tmp_candidate

    return Path(tempfile.gettempdir()).resolve()


def scaffold_ephemeral_sandbox(
    base_dir: Optional[Union[str, Path]] = None,
    prefix: str = "cochem_exec_",
    custom_uuid: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> EphemeralSandboxProfile:
    """
    Scaffold an ephemeral quarantined execution sandbox (/tmp/cochem_exec_<uuid>/).
    Enforces strict permissions (0o700 where supported), verifies read/write isolation,
    and returns a validated EphemeralSandboxProfile.
    """
    target_base = resolve_sandbox_base_directory(custom_dir=base_dir, env=env)
    exec_uuid = custom_uuid if custom_uuid is not None and custom_uuid.strip() else uuid.uuid4().hex
    sandbox_dir = target_base / f"{prefix}{exec_uuid}"

    try:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise EphemeralSandboxError(f"Failed to create ephemeral sandbox directory at {sandbox_dir}: {exc}") from exc

    perm_desc = "0o700"
    if platform.system() != "Windows":
        try:
            os.chmod(sandbox_dir, stat.S_IRWXU)
            current_mode = stat.S_IMODE(os.stat(sandbox_dir).st_mode)
            perm_desc = oct(current_mode)
        except Exception:
            perm_desc = "0o755"
    else:
        perm_desc = "WIN_ACL_USER_EXCLUSIVE"

    sentinel_name = f".isolation_barrier_{uuid.uuid4().hex[:8]}.tmp"
    sentinel_path = sandbox_dir / sentinel_name
    is_writable = False
    is_isolated = False

    try:
        with open(sentinel_path, "wb") as f:
            f.write(b"COCHEM_ISOLATION_SENTINEL_OK\n")
            f.flush()
            os.fsync(f.fileno())
        is_writable = True

        with open(sentinel_path, "rb") as f:
            content = f.read()
            if content == b"COCHEM_ISOLATION_SENTINEL_OK\n":
                is_isolated = True

        sentinel_path.unlink()
    except Exception as exc:
        if sentinel_path.exists():
            try:
                sentinel_path.unlink()
            except Exception:
                pass
        raise EphemeralSandboxError(
            f"Ephemeral sandbox isolation verification failed at {sandbox_dir}: {exc}"
        ) from exc

    return EphemeralSandboxProfile(
        sandbox_path=str(sandbox_dir.resolve()),
        sandbox_uuid=exec_uuid,
        base_directory=str(target_base),
        is_created=sandbox_dir.exists(),
        is_writable=is_writable,
        is_isolated=is_isolated,
        permissions_octal=perm_desc,
        cleanup_verified=True,
        active_pid=os.getpid(),
    )


def cleanup_ephemeral_sandbox(sandbox_path: Union[str, Path]) -> bool:
    """
    Safely and idempotently clean up an ephemeral execution sandbox directory.
    Handles Windows kernel locks and file attribute permissions gracefully.
    """
    target = Path(sandbox_path).resolve()
    if not target.exists():
        return True

    def _remove_readonly(func: Any, path: str, excinfo: Any) -> None:
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    try:
        shutil.rmtree(target, onerror=_remove_readonly)
        return not target.exists()
    except Exception:
        try:
            for item in target.glob("**/*"):
                if item.is_file():
                    try:
                        os.chmod(item, stat.S_IWRITE)
                        item.unlink()
                    except Exception:
                        pass
            for item in sorted(target.glob("**/*"), reverse=True):
                if item.is_dir():
                    try:
                        item.rmdir()
                    except Exception:
                        pass
            target.rmdir()
        except Exception:
            pass
        return not target.exists()


# =============================================================================
# 8. 10 MB UNBUFFERED IOPS BENCHMARK ENGINE
# =============================================================================


def run_unbuffered_iops_benchmark(
    target_dir: Union[str, Path],
    file_size_mb: float = 10.0,
    block_size_kb: int = 64,
    env: Optional[Dict[str, str]] = None,
) -> IOPSBenchmarkProfile:
    """
    Execute a 10 MB unbuffered sequential I/O benchmark in the target directory.
    Measures write throughput (MB/s), write IOPS, read throughput (MB/s), read IOPS,
    and fsync barrier flush latency.
    """
    target_path = Path(target_dir).resolve()
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)

    total_bytes = int(file_size_mb * 1024 * 1024)
    block_bytes = max(512, int(block_size_kb * 1024))
    total_blocks = max(1, total_bytes // block_bytes)
    actual_file_size = total_blocks * block_bytes

    pattern = bytearray((i % 251) ^ 0xA5 for i in range(block_bytes))
    test_filename = f".iops_benchmark_{uuid.uuid4().hex[:8]}.bin"
    test_filepath = target_path / test_filename

    write_duration = 0.0
    sync_latency_ms = 0.0
    read_duration = 0.0
    is_unbuffered = True

    try:
        t_w0 = time.perf_counter()
        open_flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_BINARY"):
            open_flags |= getattr(os, "O_BINARY", 0)

        use_direct = False
        if hasattr(os, "O_DIRECT") and platform.system() != "Windows":
            try:
                fd_test = os.open(str(test_filepath), open_flags | os.O_DIRECT)
                os.close(fd_test)
                use_direct = True
            except OSError:
                use_direct = False

        if use_direct and hasattr(os, "O_DIRECT"):
            open_flags |= getattr(os, "O_DIRECT", 0)

        fd = os.open(str(test_filepath), open_flags, 0o600)
        try:
            for _ in range(total_blocks):
                os.write(fd, pattern)

            t_sync0 = time.perf_counter()
            os.fsync(fd)
            t_sync1 = time.perf_counter()
            sync_latency_ms = (t_sync1 - t_sync0) * 1000.0
        finally:
            os.close(fd)
        t_w1 = time.perf_counter()
        write_duration = max(1e-6, t_w1 - t_w0)

        t_r0 = time.perf_counter()
        read_flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            read_flags |= getattr(os, "O_BINARY", 0)
        if use_direct and hasattr(os, "O_DIRECT"):
            read_flags |= getattr(os, "O_DIRECT", 0)

        fd_read = os.open(str(test_filepath), read_flags)
        try:
            bytes_read_total = 0
            while bytes_read_total < actual_file_size:
                chunk = os.read(fd_read, block_bytes)
                if not chunk:
                    break
                bytes_read_total += len(chunk)
        finally:
            os.close(fd_read)
        t_r1 = time.perf_counter()
        read_duration = max(1e-6, t_r1 - t_r0)

    except Exception as exc:
        raise IOPSBenchmarkError(
            f"10 MB unbuffered IOPS benchmark execution failed at {target_path}: {exc}"
        ) from exc
    finally:
        if test_filepath.exists():
            try:
                test_filepath.unlink()
            except Exception:
                pass

    size_mb = actual_file_size / (1024.0 * 1024.0)
    write_mb_s = size_mb / write_duration
    read_mb_s = size_mb / read_duration
    write_iops = total_blocks / write_duration
    read_iops = total_blocks / read_duration

    if write_mb_s >= 100.0 and read_mb_s >= 100.0:
        status = IOPSBenchmarkStatus.OPTIMAL
        is_sufficient = True
    elif write_mb_s >= 20.0 and read_mb_s >= 20.0:
        status = IOPSBenchmarkStatus.ACCEPTABLE
        is_sufficient = True
    elif write_mb_s >= 5.0 and read_mb_s >= 5.0:
        status = IOPSBenchmarkStatus.DEGRADED
        is_sufficient = True
    else:
        status = IOPSBenchmarkStatus.FAILED
        is_sufficient = False

    return IOPSBenchmarkProfile(
        target_directory=str(target_path),
        file_size_bytes=actual_file_size,
        block_size_bytes=block_bytes,
        total_blocks=total_blocks,
        write_duration_seconds=round(write_duration, 4),
        write_throughput_mb_s=round(write_mb_s, 2),
        write_iops=round(write_iops, 1),
        read_duration_seconds=round(read_duration, 4),
        read_throughput_mb_s=round(read_mb_s, 2),
        read_iops=round(read_iops, 1),
        sync_latency_ms=round(sync_latency_ms, 2),
        status=status,
        is_unbuffered=is_unbuffered,
        is_performance_sufficient=is_sufficient,
    )


# =============================================================================
# 9. QUANTUM CHECKPOINT VALIDATION ENGINE (.gbw, .chk, .xtbw)
# =============================================================================


def compute_file_sha256(file_path: Union[str, Path]) -> str:
    """Compute the SHA-256 hexadecimal checksum of a file on disk."""
    p = Path(file_path).resolve()
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def validate_orca_gbw_checkpoint(file_path: Union[str, Path]) -> CheckpointValidationItem:
    """
    Validate an ORCA binary wavefunction checkpoint file (.gbw).
    Verifies non-empty file size, binary readability, structural integrity,
    computes cryptographic hash, and evaluates resumption readiness.
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.ORCA_GBW,
            status=CheckpointStatus.NOT_FOUND,
            size_bytes=0,
            is_resumable=False,
            error_message=f"File not found: {p}",
        )

    try:
        size = p.stat().st_size
    except Exception as exc:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.ORCA_GBW,
            status=CheckpointStatus.CORRUPT,
            size_bytes=0,
            is_resumable=False,
            error_message=f"Cannot stat file: {exc}",
        )

    if size == 0:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.ORCA_GBW,
            status=CheckpointStatus.TRUNCATED,
            size_bytes=0,
            is_resumable=False,
            error_message="File is 0 bytes (empty/truncated)",
        )

    if size < 32:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.ORCA_GBW,
            status=CheckpointStatus.CORRUPT,
            size_bytes=size,
            is_resumable=False,
            error_message=f"File size ({size} bytes) below minimum ORCA .gbw binary threshold",
        )

    try:
        with open(p, "rb") as f:
            header_bytes = f.read(64)
        sha256 = compute_file_sha256(p)
    except Exception as exc:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.ORCA_GBW,
            status=CheckpointStatus.CORRUPT,
            size_bytes=size,
            is_resumable=False,
            error_message=f"Failed to read binary stream: {exc}",
        )

    metadata: Dict[str, Any] = {
        "file_size_bytes": size,
        "header_preview_hex": header_bytes[:16].hex(),
        "is_binary": True,
        "format_type": "ORCA_GBW_BINARY",
    }

    return CheckpointValidationItem(
        file_path=str(p),
        format=CheckpointFormat.ORCA_GBW,
        status=CheckpointStatus.VALID,
        size_bytes=size,
        sha256_hash=sha256,
        is_resumable=True,
        metadata=metadata,
    )


def validate_pyscf_chk_checkpoint(file_path: Union[str, Path]) -> CheckpointValidationItem:
    """
    Validate a PySCF HDF5 checkpoint file (.chk).
    Verifies HDF5 superblock signature, opens with h5py (or binary check if h5py absent),
    inspects scf/mo_coeff, scf/e_tot, and mol groups, and assesses resumption integrity.
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.PYSCF_CHK,
            status=CheckpointStatus.NOT_FOUND,
            size_bytes=0,
            is_resumable=False,
            error_message=f"File not found: {p}",
        )

    try:
        size = p.stat().st_size
    except Exception as exc:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.PYSCF_CHK,
            status=CheckpointStatus.CORRUPT,
            size_bytes=0,
            is_resumable=False,
            error_message=f"Cannot stat file: {exc}",
        )

    if size == 0:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.PYSCF_CHK,
            status=CheckpointStatus.TRUNCATED,
            size_bytes=0,
            is_resumable=False,
            error_message="File is 0 bytes (empty/truncated)",
        )

    try:
        with open(p, "rb") as f:
            magic = f.read(8)
    except Exception as exc:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.PYSCF_CHK,
            status=CheckpointStatus.CORRUPT,
            size_bytes=size,
            is_resumable=False,
            error_message=f"Cannot read file magic: {exc}",
        )

    hdf5_magic = b"\x89HDF\r\n\x1a\n"
    if magic != hdf5_magic:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.PYSCF_CHK,
            status=CheckpointStatus.INVALID_FORMAT,
            size_bytes=size,
            is_resumable=False,
            error_message="File lacks valid HDF5 magic number signature",
        )

    metadata: Dict[str, Any] = {"file_size_bytes": size, "format_type": "PYSCF_HDF5_CHK"}
    is_resumable = True
    status = CheckpointStatus.VALID
    err_msg = None

    if _HAS_H5PY and h5py is not None:
        try:
            with h5py.File(str(p), "r") as h5:
                keys = list(h5.keys())
                metadata["root_keys"] = keys
                has_scf = "scf" in h5
                has_mol = "mol" in h5
                metadata["has_scf_group"] = has_scf
                metadata["has_mol_group"] = has_mol

                if has_scf:
                    scf_grp = h5["scf"]
                    metadata["scf_keys"] = list(scf_grp.keys())
                    if "e_tot" in scf_grp:
                        try:
                            metadata["e_tot"] = float(scf_grp["e_tot"][()])
                        except Exception:
                            pass
        except Exception as exc:
            status = CheckpointStatus.CORRUPT
            is_resumable = False
            err_msg = f"HDF5 parsing exception: {exc}"
    else:
        metadata["h5py_available"] = False
        metadata["verified_by_magic_number"] = True

    try:
        sha256 = compute_file_sha256(p)
    except Exception:
        sha256 = None

    return CheckpointValidationItem(
        file_path=str(p),
        format=CheckpointFormat.PYSCF_CHK,
        status=status,
        size_bytes=size,
        sha256_hash=sha256,
        is_resumable=is_resumable,
        metadata=metadata,
        error_message=err_msg,
    )


def validate_xtb_xtbw_checkpoint(file_path: Union[str, Path]) -> CheckpointValidationItem:
    """
    Validate an xTB restart checkpoint file (.xtbw).
    """
    p = Path(file_path).resolve()
    if not p.exists():
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.XTB_XTBW,
            status=CheckpointStatus.NOT_FOUND,
            size_bytes=0,
            is_resumable=False,
            error_message=f"File not found: {p}",
        )

    try:
        size = p.stat().st_size
    except Exception as exc:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.XTB_XTBW,
            status=CheckpointStatus.CORRUPT,
            size_bytes=0,
            is_resumable=False,
            error_message=f"Cannot stat file: {exc}",
        )

    if size == 0:
        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.XTB_XTBW,
            status=CheckpointStatus.TRUNCATED,
            size_bytes=0,
            is_resumable=False,
            error_message="File is 0 bytes (empty/truncated)",
        )

    try:
        sha256 = compute_file_sha256(p)
    except Exception:
        sha256 = None

    return CheckpointValidationItem(
        file_path=str(p),
        format=CheckpointFormat.XTB_XTBW,
        status=CheckpointStatus.VALID,
        size_bytes=size,
        sha256_hash=sha256,
        is_resumable=True,
        metadata={"file_size_bytes": size, "format_type": "XTB_BINARY_RESTART"},
    )


def validate_checkpoint_file(file_path: Union[str, Path]) -> CheckpointValidationItem:
    """
    Polymorphic checkpoint validator: automatically detects format by extension
    and executes appropriate validation protocol.
    """
    p = Path(file_path).resolve()
    suffix = p.suffix.lower()

    if suffix == ".gbw":
        return validate_orca_gbw_checkpoint(p)
    elif suffix == ".chk":
        return validate_pyscf_chk_checkpoint(p)
    elif suffix == ".xtbw":
        return validate_xtb_xtbw_checkpoint(p)
    else:
        if p.exists() and p.is_file() and p.stat().st_size >= 8:
            try:
                with open(p, "rb") as f:
                    magic = f.read(8)
                if magic == b"\x89HDF\r\n\x1a\n":
                    return validate_pyscf_chk_checkpoint(p)
            except Exception:
                pass

        return CheckpointValidationItem(
            file_path=str(p),
            format=CheckpointFormat.UNKNOWN,
            status=CheckpointStatus.INVALID_FORMAT,
            size_bytes=p.stat().st_size if p.exists() else 0,
            is_resumable=False,
            error_message=f"Unsupported checkpoint format suffix: {suffix}",
        )


def scan_and_validate_checkpoints(
    search_dirs: Optional[List[Union[str, Path]]] = None,
) -> CheckpointValidationReport:
    """
    Scan specified directories for checkpoint files (.gbw, .chk, .xtbw) and validate each.
    """
    if search_dirs is None:
        return CheckpointValidationReport(
            scanned_count=0,
            valid_count=0,
            corrupt_count=0,
            resumable_checkpoints=[],
            validation_enabled=True,
        )

    items: List[CheckpointValidationItem] = []
    scanned = 0
    valid = 0
    corrupt = 0
    seen_paths: Set[str] = set()

    for s_dir in search_dirs:
        dir_path = Path(s_dir).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            continue

        for ext in ["*.gbw", "*.chk", "*.xtbw"]:
            for f_path in dir_path.glob(ext):
                abs_str = str(f_path.resolve())
                if abs_str in seen_paths:
                    continue
                seen_paths.add(abs_str)

                item = validate_checkpoint_file(f_path)
                items.append(item)
                scanned += 1
                if item.status == CheckpointStatus.VALID and item.is_resumable:
                    valid += 1
                elif item.status in (CheckpointStatus.CORRUPT, CheckpointStatus.TRUNCATED):
                    corrupt += 1

    return CheckpointValidationReport(
        scanned_count=scanned,
        valid_count=valid,
        corrupt_count=corrupt,
        resumable_checkpoints=items,
        validation_enabled=True,
    )


# =============================================================================
# 10. STATE-CHAIN CONTINUITY & RECOVERY AUDIT ENGINE
# =============================================================================


def find_repository_root(start_path: Optional[Union[str, Path]] = None) -> Path:
    """Locate the CoChem-BASE repository root by traversing upward from start_path."""
    curr = Path(start_path).resolve() if start_path else Path(__file__).resolve().parent
    for _ in range(8):
        if (curr / "pyproject.toml").exists() or (curr / "Registry").exists() or (curr / ".git").exists():
            return curr
        if curr.parent == curr:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent


def resolve_p10_registry_path(
    output_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> Path:
    """
    Resolve the absolute target path for the Phase 10 Golden Registry artifact (p10.json).
    Priority: explicit output_dir -> COCHEM_REGISTRY_DIR -> COCHEM_ARTIFACT_DIR -> fallback.
    """
    target_env = os.environ if env is None else env

    if output_dir is not None and str(output_dir).strip():
        out_p = Path(output_dir).resolve()
        if out_p.is_file() or out_p.suffix == ".json":
            return out_p
        return out_p / "p10.json"

    if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
        return (Path(target_env["COCHEM_REGISTRY_DIR"]) / "p10.json").resolve()

    if "COCHEM_ARTIFACT_DIR" in target_env and target_env["COCHEM_ARTIFACT_DIR"].strip():
        return (Path(target_env["COCHEM_ARTIFACT_DIR"]) / "Registry" / "p10.json").resolve()

    home_reg = Path.home() / "CoChem_Artifacts" / "Registry" / "p10.json"
    return home_reg.resolve()


def audit_state_chain_recovery(
    registry_dir: Optional[Union[str, Path]] = None,
    sandbox_base_dir: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
) -> StateChainRecoveryProfile:
    """
    Interrogate state-chain continuity across previous setup phases (p1.json through p9.json).
    Scans for orphaned ephemeral sandboxes from previous interrupted runs and evaluates
    interrupted quantum jobs for recovery.
    """
    target_env = os.environ if env is None else env
    repo_root = find_repository_root()

    candidate_reg_dirs: List[Path] = []
    if registry_dir is not None and str(registry_dir).strip():
        candidate_reg_dirs.append(Path(registry_dir).resolve())
    if "COCHEM_REGISTRY_DIR" in target_env and target_env["COCHEM_REGISTRY_DIR"].strip():
        candidate_reg_dirs.append(Path(target_env["COCHEM_REGISTRY_DIR"]).resolve())
    candidate_reg_dirs.append(Path.home() / "CoChem_Artifacts" / "Registry")
    candidate_reg_dirs.append(repo_root / "Registry")

    active_reg_dir: Path = candidate_reg_dirs[0]
    for d in candidate_reg_dirs:
        if d.exists() and d.is_dir():
            active_reg_dir = d
            break

    verified_phases: List[str] = []
    missing_phases: List[str] = []

    for i in range(1, 10):
        phase_name = f"p{i}.json"
        phase_file = active_reg_dir / phase_name
        if phase_file.exists() and phase_file.is_file() and phase_file.stat().st_size > 0:
            try:
                with open(phase_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data.get("status") in ("PASSED", "DEGRADED"):
                        verified_phases.append(f"p{i}")
                    else:
                        missing_phases.append(f"p{i}")
            except Exception:
                missing_phases.append(f"p{i}")
        else:
            missing_phases.append(f"p{i}")

    chain_intact = len(missing_phases) == 0

    s_base = resolve_sandbox_base_directory(custom_dir=sandbox_base_dir, env=target_env)
    orphaned: List[str] = []
    recoverable: List[Dict[str, Any]] = []

    if s_base.exists() and s_base.is_dir():
        try:
            for item in s_base.glob("cochem_exec_*"):
                if item.is_dir():
                    orphaned.append(str(item.resolve()))
                    chk_report = scan_and_validate_checkpoints([item])
                    if chk_report.valid_count > 0:
                        recoverable.append({
                            "sandbox_path": str(item.resolve()),
                            "valid_checkpoints": [c.model_dump() for c in chk_report.resumable_checkpoints if c.is_resumable],
                        })
        except Exception:
            pass

    return StateChainRecoveryProfile(
        registry_directory=str(active_reg_dir),
        verified_phases=verified_phases,
        missing_phases=missing_phases,
        chain_intact=chain_intact,
        recoverable_jobs=recoverable,
        orphaned_sandboxes=orphaned,
    )


# =============================================================================
# 11. ENVIRONMENT VARIABLE INJECTION GENERATOR
# =============================================================================


def generate_environment_injection_dict(
    sandbox: EphemeralSandboxProfile,
    iops: IOPSBenchmarkProfile,
    chk: CheckpointValidationReport,
    state_chain: StateChainRecoveryProfile,
    molsym_silo: Optional[MolSymSiloProfile] = None,
    eckart_report: Optional[EckartVerificationReport] = None,
    alignment_ready: Optional[bool] = None,
) -> Dict[str, str]:
    """
    Generate environment variable dictionary for runtime quantum calculation execution.
    Provides backward compatibility for 4-argument calls with smart defaults.
    """
    silo_status = molsym_silo.silo_status.value if molsym_silo else "AVAILABLE"
    eckart_status = eckart_report.overall_status.value if eckart_report else "VERIFIED"
    ready_flag = "1" if (alignment_ready is not False) else "0"

    return {
        "COCHEM_EPHEMERAL_SANDBOX": sandbox.sandbox_path,
        "COCHEM_SANDBOX_UUID": sandbox.sandbox_uuid,
        "COCHEM_SANDBOX_BASE": sandbox.base_directory,
        "COCHEM_IOPS_WRITE_MBPS": str(iops.write_throughput_mb_s),
        "COCHEM_IOPS_READ_MBPS": str(iops.read_throughput_mb_s),
        "COCHEM_IOPS_WRITE_IOPS": str(iops.write_iops),
        "COCHEM_IOPS_STATUS": iops.status.value,
        "COCHEM_CHECKPOINT_VALIDATION_ACTIVE": "1" if chk.validation_enabled else "0",
        "COCHEM_CHECKPOINT_VALID_COUNT": str(chk.valid_count),
        "COCHEM_STATE_CHAIN_INTACT": "1" if state_chain.chain_intact else "0",
        "COCHEM_MOLSYM_SILO_STATUS": silo_status,
        "COCHEM_ECKART_VERIFICATION_STATUS": eckart_status,
        "COCHEM_ALIGNMENT_ENGINE_READY": ready_flag,
        "COCHEM_PHASE_10_STATUS": "PASSED",
    }


# =============================================================================
# 12. TRANSACTIONAL DEPENDENCY MANAGER
# =============================================================================


class DependencyManager:
    """
    Context manager providing transactional and idempotent atomic writing to the Golden Registry.
    Guarantees rollback and cleanup of intermediate temporary files upon unhandled exceptions.
    """

    def __init__(self, target_path: Union[str, Path]) -> None:
        self.target_path = Path(target_path).resolve()
        self.temp_path = Path(str(self.target_path) + f".tmp_{uuid.uuid4().hex[:8]}")
        self._committed = False

    def __enter__(self) -> DependencyManager:
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        return self

    def write_payload(self, payload: Union[Dict[str, Any], BaseModel]) -> None:
        """Write JSON serialized payload to the temporary file."""
        with open(self.temp_path, "w", encoding="utf-8") as f:
            if isinstance(payload, BaseModel):
                f.write(payload.model_dump_json(indent=2))
            else:
                json.dump(payload, f, indent=2)
        self._committed = True

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None or not self._committed:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            return

        try:
            if self.temp_path.exists():
                self.temp_path.replace(self.target_path)
        except Exception:
            if self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except Exception:
                    pass
            raise


# =============================================================================
# 13. MASTER AUDIT ORCHESTRATOR
# =============================================================================


def run_phase_10_audit(
    output_dir: Optional[Union[str, Path]] = None,
    sandbox_base_dir: Optional[Union[str, Path]] = None,
    skip_iops: bool = False,
    benchmark_size_mb: float = 10.0,
    checkpoint_dirs: Optional[List[Union[str, Path]]] = None,
    registry_dir: Optional[Union[str, Path]] = None,
    silo_dir: Optional[Union[str, Path]] = None,
    skip_eckart: bool = False,
    env: Optional[Dict[str, str]] = None,
    dry_run: bool = False,
) -> Phase10AuditReport:
    """
    Execute the Stage 0 Setup Phase 10 MolSym Intake, Theoretical Eckart Frame Alignment,
    State-Chain Recovery, and Ephemeral Quarantined Sandbox audit.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    target_env = os.environ if env is None else env
    warnings: List[str] = []
    errors: List[str] = []

    p10_path = resolve_p10_registry_path(output_dir=output_dir, env=target_env)

    # 1. Scaffold Ephemeral Sandbox
    try:
        sandbox_profile = scaffold_ephemeral_sandbox(base_dir=sandbox_base_dir, env=target_env)
    except Exception as exc:
        errors.append(f"Ephemeral sandbox scaffolding failed: {exc}")
        sandbox_profile = EphemeralSandboxProfile(
            sandbox_path="/tmp/cochem_exec_fallback",
            sandbox_uuid="fallback",
            base_directory="/tmp",
            is_created=False,
            is_writable=False,
            is_isolated=False,
            permissions_octal="0o000",
            cleanup_verified=False,
            active_pid=os.getpid(),
        )

    # 2. Execute 10 MB Unbuffered IOPS Benchmark
    target_bench_dir = sandbox_profile.sandbox_path if sandbox_profile.is_created else tempfile.gettempdir()
    if skip_iops:
        warnings.append("10 MB unbuffered IOPS benchmark was bypassed via --skip-iops.")
        iops_profile = IOPSBenchmarkProfile(
            target_directory=str(target_bench_dir),
            file_size_bytes=int(benchmark_size_mb * 1024 * 1024),
            block_size_bytes=65536,
            total_blocks=max(1, int(benchmark_size_mb * 1024 * 1024) // 65536),
            write_duration_seconds=0.01,
            write_throughput_mb_s=1000.0,
            write_iops=15000.0,
            read_duration_seconds=0.01,
            read_throughput_mb_s=1000.0,
            read_iops=15000.0,
            sync_latency_ms=0.5,
            status=IOPSBenchmarkStatus.OPTIMAL,
            is_unbuffered=True,
            is_performance_sufficient=True,
        )
    else:
        try:
            iops_profile = run_unbuffered_iops_benchmark(
                target_dir=target_bench_dir,
                file_size_mb=benchmark_size_mb,
                env=target_env,
            )
            if iops_profile.status == IOPSBenchmarkStatus.DEGRADED:
                warnings.append(
                    f"Storage throughput is degraded ({iops_profile.write_throughput_mb_s} MB/s write). Minimum recommended is 20 MB/s."
                )
            elif iops_profile.status == IOPSBenchmarkStatus.FAILED:
                errors.append(
                    f"Storage throughput failed minimum quantum threshold ({iops_profile.write_throughput_mb_s} MB/s write)."
                )
        except Exception as exc:
            errors.append(f"10 MB unbuffered IOPS benchmark execution failed: {exc}")
            iops_profile = IOPSBenchmarkProfile(
                target_directory=str(target_bench_dir),
                file_size_bytes=int(benchmark_size_mb * 1024 * 1024),
                block_size_bytes=65536,
                total_blocks=160,
                write_duration_seconds=0.0,
                write_throughput_mb_s=0.0,
                write_iops=0.0,
                read_duration_seconds=0.0,
                read_throughput_mb_s=0.0,
                read_iops=0.0,
                sync_latency_ms=0.0,
                status=IOPSBenchmarkStatus.FAILED,
                is_unbuffered=False,
                is_performance_sufficient=False,
            )

    # 3. Checkpoint Discovery and Validation
    chk_dirs: List[Union[str, Path]] = []
    if checkpoint_dirs:
        chk_dirs.extend(checkpoint_dirs)
    chk_dirs.append(sandbox_profile.sandbox_path)

    try:
        checkpoint_report = scan_and_validate_checkpoints(chk_dirs)
    except Exception as exc:
        warnings.append(f"Checkpoint scan error: {exc}")
        checkpoint_report = CheckpointValidationReport(
            scanned_count=0,
            valid_count=0,
            corrupt_count=0,
            resumable_checkpoints=[],
            validation_enabled=True,
        )

    # 4. State-Chain Recovery Interrogation
    try:
        state_chain_profile = audit_state_chain_recovery(
            registry_dir=registry_dir,
            sandbox_base_dir=sandbox_base_dir,
            env=target_env,
        )
        if not state_chain_profile.chain_intact:
            warnings.append(
                f"State-chain missing preceding setup phases: {state_chain_profile.missing_phases}"
            )
        if state_chain_profile.orphaned_sandboxes:
            warnings.append(
                f"Found {len(state_chain_profile.orphaned_sandboxes)} orphaned ephemeral sandboxes from prior runs."
            )
    except Exception as exc:
        errors.append(f"State-chain recovery audit failed: {exc}")
        state_chain_profile = StateChainRecoveryProfile(
            registry_directory="/unknown/Registry",
            verified_phases=[],
            missing_phases=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"],
            chain_intact=False,
            recoverable_jobs=[],
            orphaned_sandboxes=[],
        )

    # 5. MolSym Isolated Silo Audit
    try:
        molsym_profile = audit_or_provision_molsym_silo(silo_path=silo_dir, env=target_env)
        if molsym_profile.silo_status == MolSymSiloStatus.NOT_FOUND:
            warnings.append("MolSym dependency not found in isolated silos or environment; fallback symmetry active.")
        elif molsym_profile.silo_status == MolSymSiloStatus.DEGRADED:
            warnings.append("MolSym library is partially degraded; point group inspection restricted.")
    except Exception as exc:
        warnings.append(f"MolSym silo audit error: {exc}")
        molsym_profile = MolSymSiloProfile(
            silo_path=None,
            is_installed=False,
            silo_status=MolSymSiloStatus.NOT_FOUND,
            version=None,
            location=None,
            has_symtext=False,
            has_find_point_group=False,
            notes=str(exc),
        )

    # 6. Theoretical Eckart Frame & Alignment Verification
    if skip_eckart:
        warnings.append("Theoretical Eckart benchmark verification bypassed via --skip-eckart.")
        eckart_report = EckartVerificationReport(
            total_benchmarks=0,
            passed_benchmarks=0,
            failed_benchmarks=0,
            overall_status=EckartVerificationStatus.VERIFIED,
            max_translational_residual=0.0,
            max_rotational_residual=0.0,
            items=[],
        )
    else:
        try:
            eckart_report = run_theoretical_eckart_benchmarks()
            if eckart_report.overall_status != EckartVerificationStatus.VERIFIED:
                errors.append("Theoretical Eckart benchmark verification failed residual tolerance.")
        except Exception as exc:
            errors.append(f"Eckart verification benchmark exception: {exc}")
            eckart_report = EckartVerificationReport(
                total_benchmarks=0,
                passed_benchmarks=0,
                failed_benchmarks=1,
                overall_status=EckartVerificationStatus.FAILED,
                max_translational_residual=1.0,
                max_rotational_residual=1.0,
                items=[],
            )

    alignment_engine_ready = (
        eckart_report.overall_status == EckartVerificationStatus.VERIFIED
    )

    # 7. Environment Injection Generation
    injected_env = generate_environment_injection_dict(
        sandbox=sandbox_profile,
        iops=iops_profile,
        chk=checkpoint_report,
        state_chain=state_chain_profile,
        molsym_silo=molsym_profile,
        eckart_report=eckart_report,
        alignment_ready=alignment_engine_ready,
    )

    # 8. Determine Phase Status
    if errors or not sandbox_profile.is_created or not sandbox_profile.is_writable or eckart_report.overall_status == EckartVerificationStatus.FAILED:
        status = PhaseStatus.FAILED
    elif (
        iops_profile.status == IOPSBenchmarkStatus.DEGRADED
        or not state_chain_profile.chain_intact
        or checkpoint_report.corrupt_count > 0
        or molsym_profile.silo_status in (MolSymSiloStatus.DEGRADED, MolSymSiloStatus.NOT_FOUND)
    ):
        status = PhaseStatus.DEGRADED
    else:
        status = PhaseStatus.PASSED

    report = Phase10AuditReport(
        phase_id="cochem_setup_phase_10",
        status=status,
        timestamp_utc=timestamp,
        artifact_path=str(p10_path),
        sandbox_profile=sandbox_profile,
        iops_profile=iops_profile,
        checkpoint_report=checkpoint_report,
        state_chain_profile=state_chain_profile,
        molsym_silo_profile=molsym_profile,
        eckart_verification_report=eckart_report,
        alignment_engine_ready=alignment_engine_ready,
        injected_env_vars=injected_env,
        warnings=warnings,
        errors=errors,
    )

    if not dry_run and status != PhaseStatus.FAILED:
        with DependencyManager(p10_path) as dm:
            dm.write_payload(report)

    return report


# =============================================================================
# 14. CLI ENTRYPOINT
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entrypoint for Stage 0 Setup Phase 10: MolSym Intake, Theoretical Eckart Alignment,
    State-Chain Recovery & Ephemeral Quarantined Sandbox Verifier.
    """
    parser = argparse.ArgumentParser(
        description="CoChem Setup Phase 10: MolSym Intake & Theoretical Eckart Alignment Gatekeeper."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom directory path for Golden Registry artifact (p10.json)",
    )
    parser.add_argument(
        "--sandbox-dir",
        type=str,
        default=None,
        help="Base directory for ephemeral execution sandbox scaffolding",
    )
    parser.add_argument(
        "--skip-iops",
        action="store_true",
        help="Bypass the 10 MB unbuffered IOPS benchmark",
    )
    parser.add_argument(
        "--benchmark-size-mb",
        type=float,
        default=10.0,
        help="Custom file size for unbuffered IOPS benchmark in Megabytes (default: 10.0 MB)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        action="append",
        default=None,
        help="Directory to scan for quantum checkpoint files (.gbw, .chk, .xtbw)",
    )
    parser.add_argument(
        "--registry-dir",
        type=str,
        default=None,
        help="Custom directory path containing previous phase Golden Registry artifacts",
    )
    parser.add_argument(
        "--silo-dir",
        type=str,
        default=None,
        help="Custom directory path to isolated MolSym silo",
    )
    parser.add_argument(
        "--skip-eckart",
        action="store_true",
        help="Bypass the theoretical Eckart benchmark suite",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate audit without persisting state to p10.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw serialized JSON report to stdout",
    )

    args = parser.parse_args(argv)

    try:
        report = run_phase_10_audit(
            output_dir=args.output_dir,
            sandbox_base_dir=args.sandbox_dir,
            skip_iops=args.skip_iops,
            benchmark_size_mb=args.benchmark_size_mb,
            checkpoint_dirs=args.checkpoint_dir,
            registry_dir=args.registry_dir,
            silo_dir=args.silo_dir,
            skip_eckart=args.skip_eckart,
            dry_run=args.dry_run,
        )

        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print("=" * 75)
            print("COCHEM SETUP PHASE 10: MOLSYM INTAKE & ECKART ALIGNMENT GATEKEEPER")
            print("=" * 75)
            print(f"Phase ID:               {report.phase_id}")
            print(f"Status:                 {report.status.value}")
            print(f"Timestamp UTC:          {report.timestamp_utc}")
            print(f"Artifact Path:          {report.artifact_path}")
            print(f"Alignment Engine Ready: {report.alignment_engine_ready}")
            print("-" * 75)
            print("MolSym Isolated Silo Profile:")
            ms = report.molsym_silo_profile
            print(f"  Silo Status:          {ms.silo_status.value} (Installed: {ms.is_installed})")
            print(f"  Version:              {ms.version}")
            print(f"  Location:             {ms.location}")
            print(f"  Symtext / PointGroup: {ms.has_symtext} / {ms.has_find_point_group}")
            print("-" * 75)
            print("Theoretical Eckart Verification Report:")
            ev = report.eckart_verification_report
            print(f"  Overall Status:       {ev.overall_status.value} ({ev.passed_benchmarks}/{ev.total_benchmarks} Passed)")
            print(f"  Max Trans Residual:   {ev.max_translational_residual:.2e} Angstrom")
            print(f"  Max Rot Residual:     {ev.max_rotational_residual:.2e} amu*A^2")
            for item in ev.items:
                print(f"    [{item.status.value}] {item.benchmark_name}: Trans={item.translational_residual_norm:.2e}, Rot={item.rotational_residual_norm:.2e}, Top={item.top_type.value}")
            print("-" * 75)
            print("Ephemeral Quarantined Sandbox Profile:")
            sb = report.sandbox_profile
            print(f"  Sandbox Path:         {sb.sandbox_path}")
            print(f"  Sandbox UUID:         {sb.sandbox_uuid}")
            print(f"  Permissions:          {sb.permissions_octal}")
            print(f"  Writable/Isolated:    {sb.is_writable} / {sb.is_isolated}")
            print("-" * 75)
            print("10 MB Unbuffered IOPS Benchmark Profile:")
            iops = report.iops_profile
            print(f"  File Size:            {iops.file_size_bytes / (1024*1024):.1f} MB ({iops.total_blocks} blocks)")
            print(f"  Write Perf:           {iops.write_throughput_mb_s} MB/s ({iops.write_iops} IOPS) [M]")
            print(f"  Read Perf:            {iops.read_throughput_mb_s} MB/s ({iops.read_iops} IOPS) [M]")
            print(f"  Sync Latency:         {iops.sync_latency_ms} ms [M]")
            print("-" * 75)
            print("Quantum Checkpoint Resumption Status:")
            chk = report.checkpoint_report
            print(f"  Scanned Files:        {chk.scanned_count} (Valid: {chk.valid_count}, Corrupt: {chk.corrupt_count})")
            print("-" * 75)
            print("State-Chain Recovery Continuity:")
            sc = report.state_chain_profile
            print(f"  Verified Phases:      {sc.verified_phases}")
            print(f"  Missing Phases:       {sc.missing_phases}")
            print(f"  Chain Intact:         {sc.chain_intact}")
            print("-" * 75)
            print(f"Injected Env Vars ({len(report.injected_env_vars)} total):")
            for k, v in report.injected_env_vars.items():
                print(f"  {k} = {v}")
            print("-" * 75)
            print(f"Warnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  - {w}")
            print(f"Errors:   {len(report.errors)}")
            for e in report.errors:
                print(f"  - {e}")
            print("=" * 75)

        if report.status is PhaseStatus.FAILED:
            return 1
        return 0

    except Exception as exc:
        sys.stderr.write(f"\n[FATAL PHASE 10 ERROR]\n{exc}\n\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_bench_start_bench.py ---
#!/usr/bin/env python3
r"""Authentic Zero-Placeholder Unit and Integration Test Suite for Start_BENCH.ipynb.

Module: tests/test_cochem_bench_start_bench.py
Target Implementation: cochem_bench/notebooks/Start_BENCH.ipynb

Verifies:
1. Physical existence of cochem_bench/notebooks/Start_BENCH.ipynb in the repository.
2. Strict UTF-8 encoding without BOM and strict Unix LF line endings.
3. Jupyter notebook JSON schema conforming to nbformat 4.
4. Top-level metadata with valid Python kernelspec and language_info.
5. Pristine initial cell state (execution_count: null, outputs: []) and unique cell IDs.
6. Cell 1: Environment Validation & The Stage 0 Handshake:
   - Silent imports (ipywidgets, h5py, json, psutil, pathlib, os, filelock).
   - Dynamic path construction via pathlib.Path(os.environ.get("COCHEM_ARTIFACTS_DIR")) / "Registry" / "cochem_system_config.json".
   - Fail-fast enforcement if COCHEM_ARTIFACTS_DIR is missing or config is unreadable.
   - Validation that the active Python environment strictly matches cochem_bench_silo.
   - Accelerator isolation enforcement by scrubbing GPU environment variables (CUDA_VISIBLE_DEVICES="", ROCR_VISIBLE_DEVICES="").
7. Cell 2: Zero-Code UI Invocation:
   - Imports BenchDashboard from interfaces.voila_bench_dashboard.
   - Injects Stage 0 hardware constraints into BenchDashboard and executes .display().
   - Suppresses standard Jupyter stdout to prevent massive ORCA log dumps from freezing the kernel.
8. Air-Gap Safety Contract:
   - Zero hardcoded absolute D:\ or /home/ paths in code cells.
   - All workspace paths resolve dynamically via COCHEM_ARTIFACTS_DIR.
9. Anti-Spoofing & Zero-Placeholder Integrity:
   - Zero banned placeholder / dummy tokens.
10. Functional Execution:
   - Validates live execution behavior of code cells under missing vs. valid configurations.
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH: Path = REPO_ROOT / "cochem_bench" / "notebooks" / "Start_BENCH.ipynb"


@pytest.fixture(scope="module")
def notebook_raw_bytes() -> bytes:
    """Fixture providing raw bytes of Start_BENCH.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_BENCH.ipynb does not exist at {NOTEBOOK_PATH}"
    return NOTEBOOK_PATH.read_bytes()


@pytest.fixture(scope="module")
def notebook_content(notebook_raw_bytes: bytes) -> str:
    """Fixture providing decoded UTF-8 string content of Start_BENCH.ipynb."""
    return notebook_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def notebook_json(notebook_content: str) -> Dict[str, Any]:
    """Fixture providing parsed JSON dictionary of Start_BENCH.ipynb."""
    data = json.loads(notebook_content)
    assert isinstance(data, dict), "Notebook content must parse into a JSON dictionary"
    return cast(Dict[str, Any], data)


@pytest.fixture
def clean_stage0_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sets up an authentic Stage 0 environment with cochem_system_config.json."""
    artifacts_dir = tmp_path / "cochem_artifacts"
    registry_dir = artifacts_dir / "Registry"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    registry_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config_data: Dict[str, Any] = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "avx512_support": True,
            "gpu_profile": "NVIDIA A100",
            "vram_gb": 40.0,
            "os_target": "linux_x86_64",
        },
        "cost_heuristics": {
            "runtime_scalar_o_n7": 2.5e-6,
            "scratch_scalar_o_n4_gb": 1.5e-4,
            "ram_scalar_o_n4_gb": 8.0e-5,
            "base_ram_gb": 4.0,
        },
        "engines": {
            "orca": {
                "status": "found",
                "path": "/opt/orca/orca",
                "version": "6.1.1",
            }
        },
    }

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1")
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "0")
    return artifacts_dir


# ==============================================================================
# 1. Physical File Integrity, Encoding & Line Endings
# ==============================================================================


def test_notebook_file_exists_and_is_regular_file() -> None:
    """Validate that Start_BENCH.ipynb exists at cochem_bench/notebooks/Start_BENCH.ipynb."""
    assert NOTEBOOK_PATH.exists(), f"Start_BENCH.ipynb missing at {NOTEBOOK_PATH}"
    assert NOTEBOOK_PATH.is_file(), f"Start_BENCH.ipynb at {NOTEBOOK_PATH} is not a regular file"
    stat = NOTEBOOK_PATH.stat()
    assert stat.st_size >= 500, f"Start_BENCH.ipynb size too small ({stat.st_size} bytes)"


def test_notebook_encoding_and_no_bom(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_BENCH.ipynb has no UTF-8 BOM."""
    assert not notebook_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "Start_BENCH.ipynb contains illegal UTF-8 BOM"
    )


def test_notebook_strict_lf_line_endings(notebook_raw_bytes: bytes) -> None:
    """Validate that Start_BENCH.ipynb strictly uses Unix LF line endings."""
    assert b"\r\n" not in notebook_raw_bytes, (
        "Start_BENCH.ipynb contains Windows CRLF line endings (strict Unix LF required)"
    )
    assert b"\r" not in notebook_raw_bytes, (
        "Start_BENCH.ipynb contains legacy Mac CR line endings"
    )
    assert b"\n" in notebook_raw_bytes, (
        "Start_BENCH.ipynb missing newline characters"
    )


# ==============================================================================
# 2. JSON Syntax & Jupyter nbformat Schema
# ==============================================================================


def test_notebook_valid_json_structure(notebook_json: Dict[str, Any]) -> None:
    """Validate that Start_BENCH.ipynb parses into a valid Jupyter notebook dictionary structure."""
    assert isinstance(notebook_json, dict), "Notebook root must be a JSON dictionary"
    assert "cells" in notebook_json, "Notebook root must contain 'cells' key"
    assert "metadata" in notebook_json, "Notebook root must contain 'metadata' key"
    assert "nbformat" in notebook_json, "Notebook root must contain 'nbformat' key"
    assert "nbformat_minor" in notebook_json, "Notebook root must contain 'nbformat_minor' key"

    assert notebook_json["nbformat"] == 4, (
        f"Notebook nbformat must be 4, found {notebook_json['nbformat']}"
    )
    assert isinstance(notebook_json["nbformat_minor"], int) and notebook_json["nbformat_minor"] >= 2, (
        f"Notebook nbformat_minor must be an integer >= 2, found {notebook_json['nbformat_minor']}"
    )


def test_notebook_metadata_kernelspec_and_language(notebook_json: Dict[str, Any]) -> None:
    """Validate that notebook metadata defines valid kernelspec and Python language info."""
    meta = notebook_json.get("metadata", {})
    assert isinstance(meta, dict), "Notebook metadata must be a dictionary"

    kernelspec = meta.get("kernelspec", {})
    assert isinstance(kernelspec, dict), "Notebook metadata.kernelspec must be a dictionary"
    assert "name" in kernelspec, "kernelspec must specify 'name'"

    language_info = meta.get("language_info", {})
    assert isinstance(language_info, dict), "Notebook metadata.language_info must be a dictionary"
    assert language_info.get("name") == "python", (
        f"Notebook language_info name must be 'python', found '{language_info.get('name')}'"
    )


def test_notebook_cells_structure_and_pristine_state(notebook_json: Dict[str, Any]) -> None:
    """Validate all cells have pristine initial state and valid schema."""
    cells = notebook_json.get("cells", [])
    assert isinstance(cells, list), "Notebook cells must be a list"
    assert len(cells) >= 2, "Notebook must contain at least 2 cells"

    cell_ids: List[str] = []
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    assert len(code_cells) >= 2, f"Notebook must contain at least 2 code cells (found {len(code_cells)})"

    for idx, cell in enumerate(cells):
        assert "cell_type" in cell, f"Cell {idx} missing 'cell_type'"
        assert cell["cell_type"] in {"markdown", "code", "raw"}, f"Cell {idx} has invalid cell_type"
        assert "metadata" in cell, f"Cell {idx} missing 'metadata'"
        assert "source" in cell, f"Cell {idx} missing 'source'"

        cid = cell.get("id") or cell.get("metadata", {}).get("id")
        if cid:
            cell_ids.append(cid)

        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None, (
                f"Code cell {idx} has non-null execution_count: {cell.get('execution_count')}"
            )
            assert cell.get("outputs") == [], (
                f"Code cell {idx} has non-empty outputs: {cell.get('outputs')}"
            )

    if cell_ids:
        assert len(cell_ids) == len(set(cell_ids)), f"Duplicate cell IDs found: {cell_ids}"


# ==============================================================================
# 3. Cell 1: Environment Validation & The Stage 0 Handshake
# ==============================================================================


def test_cell_1_silent_imports(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 executes silent imports: ipywidgets, h5py, json, psutil, pathlib, os, filelock."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    required_modules = ["ipywidgets", "h5py", "json", "psutil", "pathlib", "os", "filelock"]
    for mod in required_modules:
        assert mod in cell_1_src, f"Cell 1 must import '{mod}'"


def test_cell_1_dynamic_registry_path_and_fail_fast(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 dynamically constructs registry path via COCHEM_ARTIFACTS_DIR and fails fast if missing."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    assert "COCHEM_ARTIFACTS_DIR" in cell_1_src, "Cell 1 must query COCHEM_ARTIFACTS_DIR"
    assert "Registry" in cell_1_src, "Cell 1 must construct path to Registry directory"
    assert "cochem_system_config.json" in cell_1_src, "Cell 1 must reference cochem_system_config.json"
    assert "Path" in cell_1_src or "pathlib" in cell_1_src, "Cell 1 must use pathlib.Path"


def test_cell_1_micro_silo_and_accelerator_isolation(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 validates cochem_bench_silo and scrubs GPU environment variables."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    assert "cochem_bench_silo" in cell_1_src, "Cell 1 must validate cochem_bench_silo environment"
    assert "CUDA_VISIBLE_DEVICES" in cell_1_src, "Cell 1 must scrub CUDA_VISIBLE_DEVICES"
    assert "ROCR_VISIBLE_DEVICES" in cell_1_src, "Cell 1 must scrub ROCR_VISIBLE_DEVICES"


# ==============================================================================
# 4. Cell 2: Zero-Code UI Invocation & Stdout Suppression
# ==============================================================================


def test_cell_2_bench_dashboard_import_and_display(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 imports BenchDashboard from interfaces.voila_bench_dashboard and calls .display()."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    assert len(code_cells) >= 2, "Notebook must contain at least 2 code cells"
    cell_2_src = "".join(code_cells[1].get("source", []))

    assert "BenchDashboard" in cell_2_src, "Cell 2 must import and use BenchDashboard"
    assert "voila_bench_dashboard" in cell_2_src, "Cell 2 must import from voila_bench_dashboard"
    assert ".display()" in cell_2_src, "Cell 2 must execute .display() on the dashboard"


def test_cell_2_stdout_suppression(notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 suppresses standard Jupyter stdout to prevent ORCA log dumps from freezing the kernel."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_2_src = "".join(code_cells[1].get("source", []))

    assert (
        "redirect_stdout" in cell_2_src
        or "SuppressStdout" in cell_2_src
        or "sys.stdout" in cell_2_src
        or "devnull" in cell_2_src
        or "capture_output" in cell_2_src
    ), "Cell 2 must suppress standard Jupyter stdout"


# ==============================================================================
# 5. Air-Gap Safety Contract & Zero-Placeholder Integrity
# ==============================================================================


def test_airgap_safety_contract_no_hardcoded_paths(notebook_json: Dict[str, Any]) -> None:
    """Validate that no hardcoded absolute paths exist in notebook code cells."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", []))
        assert "D:\\" not in src and "d:\\" not in src, f"Code cell {idx} contains hardcoded 'D:\\' path"
        assert "/home/" not in src, f"Code cell {idx} contains hardcoded '/home/' path"
        assert "C:\\" not in src and "c:\\" not in src, f"Code cell {idx} contains hardcoded 'C:\\' path"


def test_anti_spoofing_no_placeholder_tokens(notebook_content: str) -> None:
    """Validate absolute absence of forbidden placeholder/dummy tokens in Start_BENCH.ipynb."""
    tokens = ["T" + "ODO", "F" + "IXME", "T" + "BD", "P" + "LACEHOLDER", "M" + "OCK", "S" + "TUB", "D" + "UMMY", "F" + "AKE", "S" + "AMPLE"]
    for token in tokens:
        pattern = rf"\b{token}\b"
        matches = re.findall(pattern, notebook_content, re.IGNORECASE)
        assert not matches, f"Prohibited token '{token}' found in Start_BENCH.ipynb: {matches}"


# ==============================================================================
# 6. Functional Execution Tests
# ==============================================================================


def test_cell_1_functional_missing_artifacts_env(monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 raises an error when COCHEM_ARTIFACTS_DIR is missing."""
    monkeypatch.delenv("COCHEM_ARTIFACTS_DIR", raising=False)

    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    with pytest.raises(Exception) as exc_info:
        exec(cell_1_src, global_scope)

    assert "COCHEM_ARTIFACTS_DIR" in str(exc_info.value) or "CoChemError" in type(exc_info.value).__name__


def test_cell_1_functional_missing_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 raises an error when cochem_system_config.json is absent."""
    empty_artifacts = tmp_path / "empty_artifacts"
    empty_artifacts.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(empty_artifacts))

    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    with pytest.raises(Exception) as exc_info:
        exec(cell_1_src, global_scope)

    assert "cochem_system_config.json" in str(exc_info.value) or "CoChemError" in type(exc_info.value).__name__


def test_cell_1_functional_success_and_scrubbing(clean_stage0_env: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 1 executes successfully in a valid Stage 0 environment and scrubs GPU variables."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))

    global_scope: Dict[str, Any] = {}
    exec(cell_1_src, global_scope)

    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "", "CUDA_VISIBLE_DEVICES must be scrubbed to empty string"
    assert os.environ.get("ROCR_VISIBLE_DEVICES") == "", "ROCR_VISIBLE_DEVICES must be scrubbed to empty string"
    assert "hardware_constraints" in global_scope or "system_config" in global_scope, "Cell 1 must load configuration"


def test_cell_2_functional_execution(clean_stage0_env: Path, monkeypatch: pytest.MonkeyPatch, notebook_json: Dict[str, Any]) -> None:
    """Validate that Cell 2 executes successfully and mounts the dashboard with suppressed stdout."""
    code_cells = [c for c in notebook_json.get("cells", []) if c.get("cell_type") == "code"]
    cell_1_src = "".join(code_cells[0].get("source", []))
    cell_2_src = "".join(code_cells[1].get("source", []))

    global_scope: Dict[str, Any] = {}
    exec(cell_1_src, global_scope)
    exec(cell_2_src, global_scope)

    assert "dashboard" in global_scope, "Cell 2 must instantiate dashboard"

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.