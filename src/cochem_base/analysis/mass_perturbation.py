"""
Mass-Weighted Hessian Re-Diagonalization & Millisecond Isotopic Observables Engine.
Method Matrix v4: §3.0, §6.10, §8B.4, and Anti-Spoofing Protocol v4.
Zero electronic structure recalculation: re-evaluates rotational constants in <50 ms.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import h5py
except ImportError:
    h5py = None

from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2
from cochem_base.physics.isotopes import parse_nuclide_token
from cochem_base.spectroscopy.isotopologue import (
    IsotopologueSpectroscopyEngine,
    IsotopologueResult as SpectroscopicResult,
)

INERTIA_CONVERSION_MHZ_AMU_ANG2 = C_ROT_MHZ_U_ANG2


@dataclass
class IsotopologueResult(SpectroscopicResult):
    """Spectroscopic observables plus planar moments in u Angstrom²."""

    P_aa: float = 0.0
    P_bb: float = 0.0
    P_cc: float = 0.0


def compute_isotopologue_observables(
    parent_hessian: Optional[np.ndarray] = None,
    geometry: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    symbols: Optional[Sequence[str]] = None,
    isotopic_substitution: Optional[Dict[int, Union[str, int, Tuple[str, int]]]] = None,
    h5_path: Optional[Union[str, Path]] = None,
    *,
    vibrational_corrections_mhz: Optional[Tuple[float, float, float]] = None,
    correction_source: Optional[str] = None,
) -> IsotopologueResult:
    """Re-weights and re-diagonalizes parent Cartesian Hessian under isotopic mass perturbation. [M]

    Executes in <50 ms, avoiding costly electronic re-calculation (§8B.4).
    """
    t_start = time.perf_counter()

    if h5_path is not None and (parent_hessian is None or geometry is None or symbols is None):
        h5_path = Path(h5_path)
        if h5py is None:
            raise RuntimeError("h5py is required to load the parent Hessian")
        # SWMR readers must not acquire the writer's exclusive lock.
        with h5py.File(h5_path, "r", libver="latest", swmr=True) as f:
            if parent_hessian is None and "hessian" in f:
                parent_hessian = np.array(f["hessian"], dtype=np.float64)
            if geometry is None and "coordinates" in f:
                geometry = np.array(f["coordinates"], dtype=np.float64)
            if symbols is None and "symbols" in f:
                symbols = [s.decode() if isinstance(s, bytes) else str(s) for s in f["symbols"]]

    if geometry is None or symbols is None:
        raise ValueError("Geometry coordinates and element symbols are mandatory.")

    normalized_substitution = {}
    for index, replacement in (isotopic_substitution or {}).items():
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(symbols):
            raise ValueError(f"Invalid isotopic substitution index: {index}")
        base_symbol, _ = parse_nuclide_token(symbols[index])
        if isinstance(replacement, str):
            normalized_substitution[index] = replacement
        elif isinstance(replacement, int) and not isinstance(replacement, bool):
            normalized_substitution[index] = f"{replacement}{base_symbol}"
        elif isinstance(replacement, tuple) and len(replacement) == 2:
            element_symbol, number = replacement
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                raise ValueError("Isotope mass number must be a positive integer")
            normalized_substitution[index] = f"{number}{element_symbol}"
        else:
            raise ValueError("Isotopic substitution must be a nuclide, mass number, or (element, mass number)")

    engine = IsotopologueSpectroscopyEngine(list(symbols), geometry, parent_hessian)
    result = engine.compute_observables(
        normalized_substitution,
        vibrational_corrections_mhz=vibrational_corrections_mhz,
        correction_source=correction_source,
    )
    return IsotopologueResult(
        **{**vars(result), "execution_walltime_ms": (time.perf_counter() - t_start) * 1000.0},
        P_aa=0.5 * (result.I_b + result.I_c - result.I_a),
        P_bb=0.5 * (result.I_a + result.I_c - result.I_b),
        P_cc=0.5 * (result.I_a + result.I_b - result.I_c),
    )
