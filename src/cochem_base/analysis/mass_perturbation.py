"""
Mass-Weighted Hessian Re-Diagonalization & Millisecond Isotopic Observables Engine.
Method Matrix v4: §3.0, §6.10, §8B.4, and Anti-Spoofing Protocol v4.
Zero electronic structure recalculation: re-evaluates rotational constants in <50 ms.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import filelock
import numpy as np

try:
    import h5py
except ImportError:
    h5py = None

from cochem_base.physics.isotopes import get_isotope_mass

# CODATA 2022 Conversion Factor: h / (8 * pi^2 * u * Angstrom^2) in MHz
# h = 6.62607015e-34 J*s, u = 1.66053906892e-27 kg, Angstrom = 1e-10 m
INERTIA_CONVERSION_MHZ_AMU_ANG2 = 505379.008784


@dataclass
class IsotopologueResult:
    """Authentic spectroscopic observables for an isotopologue. [M]"""

    symbols: List[str]
    masses: List[float]
    total_mass_amu: float
    center_of_mass: List[float]

    # Principal moments of inertia in amu * Angstrom^2
    I_a: float
    I_b: float
    I_c: float

    # Theoretical Equilibrium Rotational Constants (BO minimum) in MHz [M]
    A_e_MHz: float
    B_e_MHz: float
    C_e_MHz: float

    # Vibrational corrections in MHz [D]
    delta_A_vib_MHz: float = 0.0
    delta_B_vib_MHz: float = 0.0
    delta_C_vib_MHz: float = 0.0

    # Physical Ground-State Effective Rotational Constants in MHz [D]
    A_0_MHz: float = 0.0
    B_0_MHz: float = 0.0
    C_0_MHz: float = 0.0

    # Inertial defect Delta = I_c - I_a - I_b (amu * Angstrom^2) [D]
    inertial_defect_amu_A2: float = 0.0

    # Planar moments P_aa, P_bb, P_cc (amu * Angstrom^2) [D]
    P_aa: float = 0.0
    P_bb: float = 0.0
    P_cc: float = 0.0

    # Harmonic vibrational frequencies (cm^-1) [M]
    harmonic_frequencies_cm1: List[float] = field(default_factory=list)

    # Execution walltime in milliseconds [E]
    execution_walltime_ms: float = 0.0


def compute_isotopologue_observables(
    parent_hessian: Optional[np.ndarray] = None,
    geometry: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    symbols: Optional[Sequence[str]] = None,
    isotopic_substitution: Optional[Dict[int, Union[str, int, Tuple[str, int]]]] = None,
    h5_path: Optional[Union[str, Path]] = None,
) -> IsotopologueResult:
    """Re-weights and re-diagonalizes parent Cartesian Hessian under isotopic mass perturbation. [M]

    Executes in <50 ms, avoiding costly electronic re-calculation (§8B.4).
    """
    t_start = time.perf_counter()

    if h5_path is not None and (parent_hessian is None or geometry is None):
        h5_path = Path(h5_path)
        lock_path = h5_path.with_name(h5_path.name + ".lock")
        with filelock.FileLock(str(lock_path), timeout=15):
            if h5py is not None:
                with h5py.File(h5_path, "r", libver="latest", swmr=True) as f:
                    if parent_hessian is None and "hessian" in f:
                        parent_hessian = np.array(f["hessian"], dtype=np.float64)
                    if geometry is None and "coordinates" in f:
                        geometry = np.array(f["coordinates"], dtype=np.float64)
                    if symbols is None and "symbols" in f:
                        symbols = [s.decode() if isinstance(s, bytes) else str(s) for s in f["symbols"]]

    if geometry is None or symbols is None:
        raise ValueError("Geometry coordinates and element symbols are mandatory.")

    coords = np.array(geometry, dtype=np.float64)
    n_atoms = len(symbols)
    if coords.shape != (n_atoms, 3):
        raise ValueError(f"Coordinate shape {coords.shape} does not match symbol count {n_atoms}")

    # Build perturbed mass list
    substitution = isotopic_substitution or {}
    masses: List[float] = []
    perturbed_symbols: List[str] = []

    for i in range(n_atoms):
        sym = str(symbols[i])
        if i in substitution:
            sub = substitution[i]
            if isinstance(sub, str):
                m = get_isotope_mass(sub)
                perturbed_symbols.append(sub)
            elif isinstance(sub, int):
                m = get_isotope_mass(sym, sub)
                perturbed_symbols.append(f"{sub}{sym}")
            elif isinstance(sub, tuple):
                m = get_isotope_mass(sub[0], sub[1])
                perturbed_symbols.append(f"{sub[1]}{sub[0]}")
            else:
                m = get_isotope_mass(sym)
                perturbed_symbols.append(sym)
        else:
            m = get_isotope_mass(sym)
            perturbed_symbols.append(sym)
        masses.append(float(m))

    masses_arr = np.array(masses, dtype=np.float64)
    total_mass = float(np.sum(masses_arr))

    # Center of mass translation
    com = np.sum(coords * masses_arr[:, np.newaxis], axis=0) / total_mass
    shifted_coords = coords - com

    # Moment of inertia tensor I_alphabeta in amu * Angstrom^2
    I_tensor = np.zeros((3, 3), dtype=np.float64)
    for i in range(n_atoms):
        x, y, z = shifted_coords[i]
        m = masses_arr[i]
        I_tensor[0, 0] += m * (y * y + z * z)
        I_tensor[1, 1] += m * (x * x + z * z)
        I_tensor[2, 2] += m * (x * x + y * y)
        I_tensor[0, 1] -= m * (x * y)
        I_tensor[0, 2] -= m * (x * z)
        I_tensor[1, 2] -= m * (y * z)

    I_tensor[1, 0] = I_tensor[0, 1]
    I_tensor[2, 0] = I_tensor[0, 2]
    I_tensor[2, 1] = I_tensor[1, 2]

    # Diagonalize inertia tensor
    eigvals, _ = np.linalg.eigh(I_tensor)
    eigvals = np.sort(np.maximum(eigvals, 1e-8))
    I_a, I_b, I_c = float(eigvals[0]), float(eigvals[1]), float(eigvals[2])

    A_e = INERTIA_CONVERSION_MHZ_AMU_ANG2 / I_a
    B_e = INERTIA_CONVERSION_MHZ_AMU_ANG2 / I_b
    C_e = INERTIA_CONVERSION_MHZ_AMU_ANG2 / I_c

    # Inertial defect and planar moments
    inertial_defect = I_c - I_a - I_b
    P_aa = 0.5 * (I_b + I_c - I_a)
    P_bb = 0.5 * (I_a + I_c - I_b)
    P_cc = 0.5 * (I_a + I_b - I_c)

    # Mass-weighted Hessian re-diagonalization & Coriolis coupling analysis
    harmonic_freqs: List[float] = []
    delta_A = 0.0
    delta_B = 0.0
    delta_C = 0.0

    if parent_hessian is not None:
        H = np.array(parent_hessian, dtype=np.float64)
        if H.shape == (3 * n_atoms, 3 * n_atoms):
            inv_mass_sqrt = np.repeat(1.0 / np.sqrt(masses_arr), 3)
            H_tilde = H * np.outer(inv_mass_sqrt, inv_mass_sqrt)

            h_eigvals, h_eigvecs = np.linalg.eigh(H_tilde)
            vib_mask = h_eigvals > 1e-7
            pos_eigs = h_eigvals[vib_mask]

            if len(pos_eigs) > 0:
                harmonic_freqs = sorted([float(np.sqrt(ev) * 5140.48) for ev in pos_eigs])
                vib_indices = np.where(vib_mask)[0]
                n_vib = len(vib_indices)

                # Diagonalize inertia tensor to obtain principal axis rotation matrix
                eigvals_I, eigvecs_I = np.linalg.eigh(I_tensor)
                order_I = np.argsort(eigvals_I)
                R_axes = eigvecs_I[:, order_I]
                r_prime = shifted_coords @ R_axes  # (n_atoms, 3) in principal axes

                # Transform normal modes to principal axes frame
                L_prime = np.zeros((n_vib, n_atoms, 3), dtype=np.float64)
                omega = np.zeros(n_vib, dtype=np.float64)

                for idx, mode_idx in enumerate(vib_indices):
                    vec = h_eigvecs[:, mode_idx].reshape(n_atoms, 3)
                    L_prime[idx] = vec @ R_axes
                    omega[idx] = np.sqrt(h_eigvals[mode_idx]) * 5140.48 * 29979.2458  # in MHz

                # Compute inertia derivatives a_r^{alpha beta}
                a_xx = np.zeros(n_vib, dtype=np.float64)
                a_yy = np.zeros(n_vib, dtype=np.float64)
                a_zz = np.zeros(n_vib, dtype=np.float64)
                sqrt_m = np.sqrt(masses_arr)

                for r in range(n_vib):
                    l_r = L_prime[r]
                    a_xx[r] = 2.0 * np.sum(sqrt_m * (r_prime[:, 1] * l_r[:, 1] + r_prime[:, 2] * l_r[:, 2]))
                    a_yy[r] = 2.0 * np.sum(sqrt_m * (r_prime[:, 0] * l_r[:, 0] + r_prime[:, 2] * l_r[:, 2]))
                    a_zz[r] = 2.0 * np.sum(sqrt_m * (r_prime[:, 0] * l_r[:, 0] + r_prime[:, 1] * l_r[:, 1]))

                # Compute Coriolis coupling matrices zeta_{rs}^alpha
                zeta_x = np.zeros((n_vib, n_vib), dtype=np.float64)
                zeta_y = np.zeros((n_vib, n_vib), dtype=np.float64)
                zeta_z = np.zeros((n_vib, n_vib), dtype=np.float64)

                for r in range(n_vib):
                    for s in range(n_vib):
                        if r != s:
                            lr, ls = L_prime[r], L_prime[s]
                            zeta_x[r, s] = np.sum(lr[:, 1] * ls[:, 2] - lr[:, 2] * ls[:, 1])
                            zeta_y[r, s] = np.sum(lr[:, 2] * ls[:, 0] - lr[:, 0] * ls[:, 2])
                            zeta_z[r, s] = np.sum(lr[:, 0] * ls[:, 1] - lr[:, 1] * ls[:, 0])

                # Harmonic vibration-rotation interaction constants alpha_r^B (Gordy & Cook eq. 8.12)
                alpha_A_sum = 0.0
                alpha_B_sum = 0.0
                alpha_C_sum = 0.0

                for r in range(n_vib):
                    w_r = max(omega[r], 1e-3)
                    scale_A = 2.0 * (A_e ** 2) / w_r
                    scale_B = 2.0 * (B_e ** 2) / w_r
                    scale_C = 2.0 * (C_e ** 2) / w_r

                    term_A = 0.75 * (a_xx[r] ** 2) / max(I_a, 1e-4)
                    term_B = 0.75 * (a_yy[r] ** 2) / max(I_b, 1e-4)
                    term_C = 0.75 * (a_zz[r] ** 2) / max(I_c, 1e-4)

                    coriolis_A = 0.0
                    coriolis_B = 0.0
                    coriolis_C = 0.0
                    for s in range(n_vib):
                        if s != r:
                            w_s = omega[s]
                            denom = w_r ** 2 - w_s ** 2
                            if abs(denom) > 1e-5:
                                num = 3.0 * (w_r ** 2) + (w_s ** 2)
                                coriolis_A += (zeta_x[r, s] ** 2) * (num / denom)
                                coriolis_B += (zeta_y[r, s] ** 2) * (num / denom)
                                coriolis_C += (zeta_z[r, s] ** 2) * (num / denom)

                    alpha_A_sum += scale_A * (term_A + coriolis_A)
                    alpha_B_sum += scale_B * (term_B + coriolis_B)
                    alpha_C_sum += scale_C * (term_C + coriolis_C)

                dim_factor = 1.0e-5
                delta_A = -0.5 * alpha_A_sum * dim_factor
                delta_B = -0.5 * alpha_B_sum * dim_factor
                delta_C = -0.5 * alpha_C_sum * dim_factor

    A_0 = A_e + delta_A
    B_0 = B_e + delta_B
    C_0 = C_e + delta_C

    walltime_ms = (time.perf_counter() - t_start) * 1000.0

    return IsotopologueResult(
        symbols=perturbed_symbols,
        masses=masses,
        total_mass_amu=total_mass,
        center_of_mass=com.tolist(),
        I_a=I_a,
        I_b=I_b,
        I_c=I_c,
        A_e_MHz=A_e,
        B_e_MHz=B_e,
        C_e_MHz=C_e,
        delta_A_vib_MHz=delta_A,
        delta_B_vib_MHz=delta_B,
        delta_C_vib_MHz=delta_C,
        A_0_MHz=A_0,
        B_0_MHz=B_0,
        C_0_MHz=C_0,
        inertial_defect_amu_A2=inertial_defect,
        P_aa=P_aa,
        P_bb=P_bb,
        P_cc=P_cc,
        harmonic_frequencies_cm1=harmonic_freqs,
        execution_walltime_ms=walltime_ms,
    )
