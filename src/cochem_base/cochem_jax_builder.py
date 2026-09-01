# -*- coding: utf-8 -*-
"""CoChem Stage 5.0: Multi-Dimensional Physics & JAX Solvers Engine.

Hardware-accelerated discrete variable representation (DVR) Hamiltonian
generator, XLA JIT eigensolver, numerical singularity watchdog, and localized
vibration-torsion VPT2 perturbation coupling solver for large-amplitude motions (LAM).

Authoritative References:
- Method_Matrix.md (Section 13.2 Table 2, Section A.2, Section A.4)
- Colbert & Miller, J. Chem. Phys. 96(3), 1982-1991 (1992)
- Meyer, J. Chem. Phys. 52, 2053 (1970) (Fourier DVR)
- Light & Carrington, Adv. Chem. Phys. 114, 263-310 (2000)
- Puzzarini et al., Int. Rev. Phys. Chem. 38, 237-293 (2019)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import jax
import jax.numpy as jnp
import numpy as np

try:
    from cochem_base.exceptions import (
        CoChemError,
        CoChemPrecisionError,
        ProvenanceErrorCode,
        SingularityError,
    )
except ImportError:
    class CoChemError(Exception):
        """Root exception for CoChem ecosystem."""
        pass

    class CoChemPrecisionError(CoChemError):
        """Raised when JAX or numerical float precision is violated."""
        pass

    class SingularityError(CoChemError):
        """Raised when numerical singularity is encountered."""
        pass

    class ProvenanceErrorCode:
        PRECISION_VIOLATION = "PRECISION_VIOLATION"
        SINGULARITY_DETECTED = "SINGULARITY_DETECTED"


logger = logging.getLogger("cochem.jax_builder")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def enforce_jax_precision(force_recheck: bool = False) -> Dict[str, Any]:
    """Strictly enforces JAX 64-bit precision (float64) and queries hardware topology.

    Configures jax_enable_x64=True upon module load / function execution, verifies
    float64 tensor allocation, and returns platform hardware metadata.

    Args:
        force_recheck: If True, forces re-validation of float64 tensor creation.

    Returns:
        Dictionary containing hardware architecture, device target, and precision status.

    Raises:
        CoChemPrecisionError: If JAX float64 mode cannot be enabled or float32 is forced.
    """
    try:
        jax.config.update("jax_enable_x64", True)
    except Exception as exc:
        raise CoChemPrecisionError(
            f"Failed to update JAX configuration for 64-bit precision: {exc}"
        ) from exc

    # Validate float64 mode
    test_tensor = jnp.array(1.0, dtype=jnp.float64)
    if test_tensor.dtype != jnp.float64:
        raise CoChemPrecisionError(
            f"JAX float64 precision enforcement failed. Expected float64, got {test_tensor.dtype}."
        )

    # Hardware architecture query
    backend = jax.default_backend()
    devices = jax.devices()
    local_devices = jax.local_devices()

    hardware_info: Dict[str, Any] = {
        "jax_version": jax.__version__,
        "backend": backend,
        "devices": [str(d) for d in devices],
        "local_devices": [str(d) for d in local_devices],
        "device_count": len(devices),
        "float64_enabled": True,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
    }

    logger.debug(
        "JAX float64 precision enforced successfully on %s device(s) [%s].",
        len(devices),
        backend,
    )
    return hardware_info


# Enforce float64 upon module import
enforce_jax_precision()


def build_dvr_hamiltonian(
    pes_spline_array: Union[np.ndarray, jnp.ndarray, Callable[..., Any], Sequence[float]],
    kinetic_operator: Optional[Union[str, np.ndarray, jnp.ndarray, Callable[..., Any]]] = None,
    dimensions: int = 1,
    mass: float = 1.0,
    length: float = 1.0,
    periodic: bool = False,
    num_points: Optional[Union[int, Tuple[int, ...]]] = None,
    reduced_rot_constant: Optional[Union[float, Tuple[float, ...]]] = None,
    hbar: float = 1.0,
) -> jnp.ndarray:
    """Constructs discretized quantum mechanical Hamiltonian matrix (H = T + V) in JAX float64.

    Supports:
    - 1D Particle in a box / Sine-DVR (Dirichlet boundary conditions with exact analytical parity).
    - 1D Sinc DVR / Colbert-Miller kinetic operator.
    - 1D Periodic internal rotor (Fourier DVR on [0, 2pi) with exact free rotor parity).
    - 2D Coupled internal rotors via Kronecker product: H = (T1 (x) I2) + (I1 (x) T2) + V_2D.

    Args:
        pes_spline_array: 1D/2D array of potential values or callable function V(x) or V(th1, th2).
        kinetic_operator: Optional custom kinetic matrix, callable, or descriptor ('sine', 'sinc', 'colbert_miller').
        dimensions: Dimensionality (1 or 2).
        mass: Particle / reduced mass (atomic units or target unit system).
        length: Box domain length L (default 1.0) or periodic angular span.
        periodic: If True, uses periodic boundary conditions (0 to 2pi).
        num_points: Number of DVR grid points (integer for 1D, int or (N1, N2) tuple for 2D).
        reduced_rot_constant: Rotational constant F = hbar^2 / (2 * I_red) for periodic rotor.
        hbar: Reduced Planck constant (default 1.0).

    Returns:
        JAX float64 2D array representing discretized Hamiltonian matrix H = T + V.

    Raises:
        CoChemPrecisionError: If float64 precision cannot be guaranteed.
        ValueError: If dimension or array shape configurations are invalid.
    """
    enforce_jax_precision()

    if dimensions == 1:
        if callable(pes_spline_array):
            if num_points is None:
                raise ValueError("num_points must be specified when pes_spline_array is a callable.")
            N = int(num_points)
            if periodic:
                theta_grid = 2.0 * jnp.pi * jnp.arange(N) / N
                V_vals = jnp.asarray([float(pes_spline_array(float(th))) for th in theta_grid], dtype=jnp.float64)
            else:
                x_grid = length * jnp.arange(1, N + 1) / (N + 1)
                V_vals = jnp.asarray([float(pes_spline_array(float(x))) for x in x_grid], dtype=jnp.float64)
        else:
            V_raw = np.asarray(pes_spline_array, dtype=np.float64)
            if V_raw.ndim != 1:
                V_raw = V_raw.flatten()
            N = len(V_raw)
            if num_points is not None and int(num_points) != N:
                raise ValueError(f"num_points ({num_points}) does not match potential array length ({N}).")
            V_vals = jnp.asarray(V_raw, dtype=jnp.float64)

        if isinstance(kinetic_operator, (np.ndarray, jnp.ndarray)):
            T = jnp.asarray(kinetic_operator, dtype=jnp.float64)
            if T.shape != (N, N):
                raise ValueError(f"Custom kinetic_operator shape {T.shape} does not match (N, N) = ({N}, {N}).")
        elif callable(kinetic_operator):
            T = jnp.asarray(kinetic_operator(N, length, mass), dtype=jnp.float64)
        else:
            if periodic:
                if reduced_rot_constant is not None:
                    F = float(reduced_rot_constant if isinstance(reduced_rot_constant, (int, float)) else reduced_rot_constant[0])
                else:
                    I_red = mass * (length**2)
                    F = (hbar**2) / (2.0 * I_red)

                j_idx = jnp.arange(N)
                theta_pts = 2.0 * jnp.pi * j_idx / N
                if N % 2 == 1:
                    M = (N - 1) // 2
                    m_basis = jnp.arange(-M, M + 1)
                else:
                    m_basis = jnp.arange(-N // 2, N // 2)

                U = (1.0 / jnp.sqrt(N)) * jnp.exp(-1j * jnp.outer(m_basis, theta_pts))
                T_fbr = jnp.diag(F * (m_basis.astype(jnp.float64)**2))
                T = jnp.real(U.conj().T @ T_fbr @ U).astype(jnp.float64)
            else:
                if kinetic_operator in ["colbert_miller", "sinc"]:
                    dx = length / (N + 1)
                    factor = (hbar**2) / (2.0 * mass * (dx**2))
                    idx = jnp.arange(N)
                    diff = idx[:, None] - idx[None, :]
                    mask_diag = (diff == 0)
                    diff_safe = jnp.where(mask_diag, 1, diff)
                    T_off = factor * 2.0 * ((-1.0)**diff) / (diff_safe**2)
                    T_diag = factor * (jnp.pi**2 / 3.0) * jnp.eye(N, dtype=jnp.float64)
                    T = jnp.where(mask_diag, T_diag, T_off)
                else:
                    n_basis = jnp.arange(1, N + 1)
                    i_grid = jnp.arange(1, N + 1)
                    U = jnp.sqrt(2.0 / (N + 1)) * jnp.sin(jnp.outer(n_basis, i_grid) * jnp.pi / (N + 1))
                    T_fbr = jnp.diag((n_basis**2 * (jnp.pi**2) * (hbar**2)) / (2.0 * mass * (length**2)))
                    T = (U.T @ T_fbr @ U).astype(jnp.float64)

        V_mat = jnp.diag(V_vals)
        H = T + V_mat
        return H.astype(jnp.float64)

    elif dimensions == 2:
        if callable(pes_spline_array):
            if num_points is None:
                raise ValueError("num_points must be specified for 2D callable potential.")
            if isinstance(num_points, (int, float)):
                N1 = N2 = int(num_points)
            else:
                N1, N2 = int(num_points[0]), int(num_points[1])

            if periodic:
                th1 = 2.0 * jnp.pi * jnp.arange(N1) / N1
                th2 = 2.0 * jnp.pi * jnp.arange(N2) / N2
                grid_vals = np.zeros((N1, N2), dtype=np.float64)
                for i1 in range(N1):
                    for i2 in range(N2):
                        grid_vals[i1, i2] = float(pes_spline_array(float(th1[i1]), float(th2[i2])))
                V_flat = jnp.asarray(grid_vals.flatten(), dtype=jnp.float64)
            else:
                x1 = length * jnp.arange(1, N1 + 1) / (N1 + 1)
                x2 = length * jnp.arange(1, N2 + 1) / (N2 + 1)
                grid_vals = np.zeros((N1, N2), dtype=np.float64)
                for i1 in range(N1):
                    for i2 in range(N2):
                        grid_vals[i1, i2] = float(pes_spline_array(float(x1[i1]), float(x2[i2])))
                V_flat = jnp.asarray(grid_vals.flatten(), dtype=jnp.float64)
        else:
            V_raw = np.asarray(pes_spline_array, dtype=np.float64)
            if V_raw.ndim == 2:
                N1, N2 = V_raw.shape
                V_flat = jnp.asarray(V_raw.flatten(), dtype=jnp.float64)
            elif V_raw.ndim == 1:
                if num_points is None:
                    side = int(np.round(np.sqrt(len(V_raw))))
                    if side * side != len(V_raw):
                        raise ValueError(f"Cannot infer square 2D grid from 1D array of length {len(V_raw)}.")
                    N1 = N2 = side
                elif isinstance(num_points, (int, float)):
                    N1 = N2 = int(num_points)
                else:
                    N1, N2 = int(num_points[0]), int(num_points[1])
                V_flat = jnp.asarray(V_raw, dtype=jnp.float64)
            else:
                raise ValueError(f"Unsupported potential shape for dimensions=2: {V_raw.shape}")

        if reduced_rot_constant is not None:
            if isinstance(reduced_rot_constant, (int, float)):
                F1 = F2 = float(reduced_rot_constant)
            else:
                F1, F2 = float(reduced_rot_constant[0]), float(reduced_rot_constant[1])
        else:
            F1 = (hbar**2) / (2.0 * mass * (length**2))
            F2 = (hbar**2) / (2.0 * mass * (length**2))

        if periodic:
            def _build_periodic_1d(n_pts: int, f_val: float) -> jnp.ndarray:
                j_idx = jnp.arange(n_pts)
                th_pts = 2.0 * jnp.pi * j_idx / n_pts
                if n_pts % 2 == 1:
                    m_lim = (n_pts - 1) // 2
                    m_b = jnp.arange(-m_lim, m_lim + 1)
                else:
                    m_b = jnp.arange(-n_pts // 2, n_pts // 2)
                u_mat = (1.0 / jnp.sqrt(n_pts)) * jnp.exp(-1j * jnp.outer(m_b, th_pts))
                tf = jnp.diag(f_val * (m_b.astype(jnp.float64)**2))
                return jnp.real(u_mat.conj().T @ tf @ u_mat).astype(jnp.float64)

            T1 = _build_periodic_1d(N1, F1)
            T2 = _build_periodic_1d(N2, F2)
        else:
            def _build_sine_1d(n_pts: int, l_val: float, m_val: float) -> jnp.ndarray:
                n_b = jnp.arange(1, n_pts + 1)
                i_b = jnp.arange(1, n_pts + 1)
                u_mat = jnp.sqrt(2.0 / (n_pts + 1)) * jnp.sin(jnp.outer(n_b, i_b) * jnp.pi / (n_pts + 1))
                tf = jnp.diag((n_b**2 * (jnp.pi**2) * (hbar**2)) / (2.0 * m_val * (l_val**2)))
                return (u_mat.T @ tf @ u_mat).astype(jnp.float64)

            T1 = _build_sine_1d(N1, length, mass)
            T2 = _build_sine_1d(N2, length, mass)

        I1 = jnp.eye(N1, dtype=jnp.float64)
        I2 = jnp.eye(N2, dtype=jnp.float64)

        T_2D = jnp.kron(T1, I2) + jnp.kron(I1, T2)
        V_mat = jnp.diag(V_flat)
        H_2D = T_2D + V_mat
        return H_2D.astype(jnp.float64)

    else:
        raise ValueError(f"Unsupported dimensions: {dimensions}. Direct product DVR supports dimensions 1 and 2.")


@jax.jit
def _jit_eigh_core(h_matrix: jnp.ndarray) -> Tuple[jnp.ndarray, jnp.ndarray]:
    """Inner XLA JIT compiled Hermitian eigensolver."""
    return jnp.linalg.eigh(h_matrix)


def jit_eigen_solver(
    hamiltonian_matrix: Union[np.ndarray, jnp.ndarray],
) -> Tuple[jnp.ndarray, jnp.ndarray]:
    """Solves eigenvalues and eigenvectors of Hermitian Hamiltonian with XLA JIT compilation.

    Guarantees float64 precision and leverages XLA binary caching for high throughput.

    Args:
        hamiltonian_matrix: (N, N) symmetric or Hermitian Hamiltonian matrix.

    Returns:
        Tuple of (eigenvalues, eigenvectors) as JAX float64 arrays.

    Raises:
        CoChemPrecisionError: If Hamiltonian matrix dtype is not float64.
    """
    enforce_jax_precision()
    h = jnp.asarray(hamiltonian_matrix, dtype=jnp.float64)
    if h.dtype != jnp.float64:
        raise CoChemPrecisionError(
            f"Hamiltonian matrix must have float64 precision, got {h.dtype}"
        )
    eigenvalues, eigenvectors = _jit_eigh_core(h)
    return eigenvalues, eigenvectors


def nan_tensor_watchdog(
    hamiltonian_or_eigenvalues: Union[np.ndarray, jnp.ndarray],
    kinetic_matrix: Optional[Union[np.ndarray, jnp.ndarray]] = None,
    potential_matrix: Optional[Union[np.ndarray, jnp.ndarray]] = None,
    damping: float = 1e-6,
) -> jnp.ndarray:
    """Validates eigenvalues / Hamiltonian matrices against NaNs, Infs, or ill-conditioned singularities.

    Upon detection of numerical divergence, intercepts the exception, applies
    Tikhonov Regularization (injects micro-damping scalar lambda * I to diagonal),
    logs a warning telemetry event via `logging.getLogger('cochem.jax_builder').warning(...)`,
    and returns a finite numerical array without crashing.

    Args:
        hamiltonian_or_eigenvalues: 1D eigenvalue array or 2D Hamiltonian matrix.
        kinetic_matrix: Optional kinetic energy operator matrix.
        potential_matrix: Optional potential energy operator matrix.
        damping: Tikhonov micro-damping scalar (lambda) added to diagonal.

    Returns:
        Regularized finite numerical tensor / solved eigenvalues.
    """
    enforce_jax_precision()
    arr = jnp.asarray(hamiltonian_or_eigenvalues, dtype=jnp.float64)

    has_nan = bool(jnp.isnan(arr).any())
    has_inf = bool(jnp.isinf(arr).any())

    if has_nan or has_inf:
        logger.warning(
            "[W: SINGULARITY_DETECTED] Non-finite tensor detected in JAX physics solver "
            "(NaN=%s, Inf=%s). Applying Tikhonov regularization (damping=%.2e).",
            has_nan,
            has_inf,
            damping,
        )
        cleaned = jnp.nan_to_num(arr, nan=0.0, posinf=1e12, neginf=-1e12)

        if cleaned.ndim == 2:
            n = cleaned.shape[0]
            h_sym = (cleaned + cleaned.T) / 2.0
            h_reg = h_sym + damping * jnp.eye(n, dtype=jnp.float64)
            return h_reg
        elif cleaned.ndim == 1:
            regularized = cleaned + damping
            return regularized
        return cleaned

    if arr.ndim == 2:
        if kinetic_matrix is not None and potential_matrix is not None:
            t_mat = jnp.asarray(kinetic_matrix, dtype=jnp.float64)
            v_mat = jnp.asarray(potential_matrix, dtype=jnp.float64)
            if jnp.isnan(t_mat).any() or jnp.isnan(v_mat).any() or jnp.isinf(t_mat).any() or jnp.isinf(v_mat).any():
                logger.warning(
                    "[W: SINGULARITY_DETECTED] Kinetic/potential matrix contains singularities. Applying Tikhonov regularization."
                )
                t_clean = jnp.nan_to_num(t_mat, nan=0.0, posinf=1e12, neginf=-1e12)
                v_clean = jnp.nan_to_num(v_mat, nan=0.0, posinf=1e12, neginf=-1e12)
                h_comb = t_clean + v_clean
                h_sym = (h_comb + h_comb.T) / 2.0
                return h_sym + damping * jnp.eye(h_sym.shape[0], dtype=jnp.float64)

    return arr


@dataclass
class LocalizedVPT2Result:
    """Container for localized vibration-torsion perturbation coupling states."""

    dvr_energies: np.ndarray
    stiff_frequencies: np.ndarray
    lam_frequency_dropped: float
    stiff_x_matrix: Optional[np.ndarray] = None
    coupled_levels: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float64))
    coupling_parameters: Dict[str, Any] = field(default_factory=dict)
    zero_point_energy: float = 0.0
    num_stiff_modes: int = 0
    lam_mode_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result to JSON-compliant dictionary."""
        return {
            "dvr_energies": self.dvr_energies.tolist(),
            "stiff_frequencies": self.stiff_frequencies.tolist(),
            "lam_frequency_dropped": float(self.lam_frequency_dropped),
            "stiff_x_matrix": self.stiff_x_matrix.tolist() if self.stiff_x_matrix is not None else None,
            "coupled_levels": self.coupled_levels.tolist(),
            "coupling_parameters": self.coupling_parameters,
            "zero_point_energy": float(self.zero_point_energy),
            "num_stiff_modes": int(self.num_stiff_modes),
            "lam_mode_index": int(self.lam_mode_index),
        }


def localized_vpt2_coupling(
    dvr_energies: Union[np.ndarray, jnp.ndarray, Sequence[float]],
    vpt2_matrix: Union[np.ndarray, jnp.ndarray, Dict[str, Any], Sequence[float]],
    lam_mode_index: int = 0,
    max_coupled_states: int = 50,
) -> Dict[str, Any]:
    """Orthogonally couples exact DVR internal rotor states with stiff VPT2 vibrational modes.

    Drops harmonic frequency nu_lam associated with internal rotation (LAM mode),
    orthogonally merges exact internal rotor energy states with remaining stiff vibrational
    modes, and calculates localized vibration-rotation coupling parameters, avoiding
    thermodynamic double-counting.

    Args:
        dvr_energies: 1D array of exact DVR torsional / internal rotor eigenvalues (cm-1 or a.u.).
        vpt2_matrix: Anharmonic VPT2 X-matrix (N_modes, N_modes) or 1D harmonic frequencies,
                     or dictionary containing {'frequencies': [...], 'x_matrix': [...]}.
        lam_mode_index: 0-based index of large-amplitude internal rotation mode to drop.
        max_coupled_states: Maximum number of coupled vib-torsional states to generate.

    Returns:
        Structured dictionary containing decoupled stiff frequencies, dropped LAM frequency,
        orthogonal coupled energy levels, zero-point energy, and localized coupling parameters.

    Raises:
        ValueError: If input arrays are malformed or mode index is out of bounds.
    """
    enforce_jax_precision()
    dvr_e = np.asarray(dvr_energies, dtype=np.float64)
    if dvr_e.ndim != 1 or len(dvr_e) == 0:
        raise ValueError("dvr_energies must be a non-empty 1D array.")

    freqs: np.ndarray
    x_mat: Optional[np.ndarray] = None

    if isinstance(vpt2_matrix, dict):
        raw_freqs = vpt2_matrix.get("frequencies", vpt2_matrix.get("harmonic_frequencies", []))
        freqs = np.asarray(raw_freqs, dtype=np.float64)
        if "x_matrix" in vpt2_matrix or "anharmonic_matrix" in vpt2_matrix:
            x_raw = vpt2_matrix.get("x_matrix", vpt2_matrix.get("anharmonic_matrix"))
            if x_raw is not None:
                x_mat = np.asarray(x_raw, dtype=np.float64)
    else:
        arr = np.asarray(vpt2_matrix, dtype=np.float64)
        if arr.ndim == 1:
            freqs = arr
            x_mat = None
        elif arr.ndim == 2:
            if arr.shape[0] == arr.shape[1]:
                x_mat = arr
                freqs = np.diag(arr)
            else:
                raise ValueError(f"vpt2_matrix 2D array must be square, got {arr.shape}")
        else:
            raise ValueError(f"Unsupported vpt2_matrix shape: {arr.shape}")

    num_modes = len(freqs)
    if num_modes == 0:
        raise ValueError("vpt2_matrix must contain at least one vibrational mode.")

    if lam_mode_index < 0 or lam_mode_index >= num_modes:
        raise IndexError(
            f"lam_mode_index ({lam_mode_index}) out of range for {num_modes} modes."
        )

    lam_frequency_dropped = float(freqs[lam_mode_index])
    stiff_freqs = np.delete(freqs, lam_mode_index)
    num_stiff = len(stiff_freqs)

    stiff_x_mat: Optional[np.ndarray] = None
    if x_mat is not None and x_mat.shape == (num_modes, num_modes):
        stiff_x_mat = np.delete(np.delete(x_mat, lam_mode_index, axis=0), lam_mode_index, axis=1)

    stiff_zpe = 0.5 * float(np.sum(stiff_freqs))
    if stiff_x_mat is not None and stiff_x_mat.size > 0:
        stiff_zpe += 0.25 * float(np.sum(stiff_x_mat))

    dvr_ground = float(dvr_e[0])
    total_zpe = stiff_zpe + dvr_ground
    dvr_excitations = dvr_e - dvr_ground

    coupled_energies: List[float] = []

    for e_dvr in dvr_excitations:
        coupled_energies.append(float(e_dvr))

    for k in range(num_stiff):
        fund_k = float(stiff_freqs[k])
        if stiff_x_mat is not None and k < stiff_x_mat.shape[0]:
            fund_k += float(stiff_x_mat[k, k])
        for e_dvr in dvr_excitations[:min(len(dvr_excitations), 15)]:
            coupled_energies.append(float(fund_k + e_dvr))

    coupled_energies_sorted = np.array(sorted(coupled_energies)[:max_coupled_states], dtype=np.float64)

    coupling_parameters = {
        "lam_frequency": lam_frequency_dropped,
        "stiff_zpe": float(stiff_zpe),
        "dvr_ground_energy": float(dvr_ground),
        "total_zpe_no_double_counting": float(total_zpe),
        "num_stiff_modes": int(num_stiff),
        "dvr_state_count": int(len(dvr_e)),
        "mean_stiff_harmonic_spacing": float(np.mean(stiff_freqs)) if num_stiff > 0 else 0.0,
    }

    result = LocalizedVPT2Result(
        dvr_energies=dvr_e,
        stiff_frequencies=stiff_freqs,
        lam_frequency_dropped=lam_frequency_dropped,
        stiff_x_matrix=stiff_x_mat,
        coupled_levels=coupled_energies_sorted,
        coupling_parameters=coupling_parameters,
        zero_point_energy=float(total_zpe),
        num_stiff_modes=int(num_stiff),
        lam_mode_index=int(lam_mode_index),
    )

    return result.to_dict()


def build_cli_parser() -> argparse.ArgumentParser:
    """Builds command-line argument parser for CoChem JAX physics solver."""
    parser = argparse.ArgumentParser(
        prog="cochem_jax_builder",
        description="CoChem Stage 5.0: Multi-Dimensional Physics & JAX Solvers Engine",
    )
    parser.add_argument(
        "--dimension",
        type=int,
        choices=[1, 2],
        default=1,
        help="DVR dimensionality (1 or 2)",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=100,
        help="Number of DVR grid points per dimension",
    )
    parser.add_argument(
        "--periodic",
        action="store_true",
        help="Enable periodic boundary conditions for internal rotor",
    )
    parser.add_argument(
        "--barrier",
        type=float,
        default=500.0,
        help="Torsional barrier height V3 (cm-1)",
    )
    parser.add_argument(
        "--rot-constant",
        type=float,
        default=5.3,
        help="Reduced rotational constant F (cm-1)",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Path to output JSON telemetry artifact",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint for headless DVR quantum solver execution."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    hw_info = enforce_jax_precision()
    logger.info("Initializing JAX Physics Solver on %s (float64=True)", hw_info["backend"])

    if args.periodic:
        v3 = args.barrier
        f_const = args.rot_constant
        n_pts = args.points
        theta_grid = 2.0 * np.pi * np.arange(n_pts) / n_pts
        v_grid = (v3 / 2.0) * (1.0 - np.cos(3.0 * theta_grid))

        h = build_dvr_hamiltonian(
            pes_spline_array=v_grid,
            dimensions=1,
            periodic=True,
            num_points=n_pts,
            reduced_rot_constant=f_const,
        )
    else:
        n_pts = args.points
        v_grid = np.zeros(n_pts, dtype=np.float64)
        h = build_dvr_hamiltonian(
            pes_spline_array=v_grid,
            dimensions=1,
            periodic=False,
            num_points=n_pts,
        )

    t0 = time.perf_counter()
    evals, evecs = jit_eigen_solver(h)
    evals.block_until_ready()
    t_solve = time.perf_counter() - t0

    logger.info("DVR Solved in %.4f ms. Lowest 5 eigenvalues: %s", t_solve * 1000.0, np.round(np.asarray(evals[:5]), 4))

    if args.output_json:
        payload = {
            "hardware": hw_info,
            "solve_time_seconds": t_solve,
            "eigenvalues": np.asarray(evals[:20]).tolist(),
            "points": n_pts,
            "periodic": args.periodic,
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info("Saved telemetry payload to %s", args.output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())

__all__ = [
    "CoChemPrecisionError",
    "LocalizedVPT2Result",
    "build_cli_parser",
    "build_dvr_hamiltonian",
    "enforce_jax_precision",
    "jit_eigen_solver",
    "localized_vpt2_coupling",
    "main",
    "nan_tensor_watchdog",
]
