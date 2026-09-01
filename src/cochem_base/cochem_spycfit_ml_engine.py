# -*- coding: utf-8 -*-
"""CoChem-SpycFit ML: JAX Autodiff Physics Engine, GP Regressor & Parity Auditor.

Provides:
- Dynamic hardware discovery & Pure JAX x64 float precision configuration
- Exact analytical Jacobians for asymmetric rotor transitions
- Scikit-learn Gaussian Process Regression for O-C residual shifts
- Dual-engine JAX vs SPFIT parity verification with 0.1 kHz threshold
- Smart scan information gain scoring & resolvability clustering filter

Authoritative Standards:
- Pure JAX Mandate (jax.config.update('jax_enable_x64', True))
- Dual-Engine Parity Bridge (FR-3.1.1, FR-3.1.3)
- ML Active Learning Loop (FR-3.2.1, FR-3.2.2, FR-3.2.3)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence, Tuple

import jax
import jax.numpy as jnp
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

# Pure JAX Mandate: Enforce float64 precision immediately
jax.config.update("jax_enable_x64", True)  # type: ignore[no-untyped-call]

logger = logging.getLogger("cochem.spycfit.ml.engine")


def discover_hardware_hierarchy() -> Dict[str, Any]:
    """Discover available execution hardware and report device hierarchy."""
    devices = jax.devices()
    backend = jax.default_backend()

    cuda_avail = any("gpu" in str(d).lower() or "cuda" in str(d).lower() for d in devices)
    mps_avail = any("mps" in str(d).lower() for d in devices)
    tpu_avail = any("tpu" in str(d).lower() for d in devices)

    return {
        "primary_device": str(devices[0]) if devices else "none",
        "available_devices": [str(d) for d in devices],
        "backend": backend,
        "x64_enabled": bool(jax.config.read("jax_enable_x64")),  # type: ignore[no-untyped-call]
        "cuda_available": cuda_avail,
        "mps_available": mps_avail,
        "tpu_available": tpu_avail,
    }


def _calculate_asymmetric_energy(A: Any, B: Any, C: Any, j: int, ka: int, kc: int) -> Any:
    """Analytical rigid-rotor energy for asymmetric top levels (J=0, 1, 2)."""
    if j == 0:
        return jnp.array(0.0, dtype=jnp.float64)
    elif j == 1:
        if ka == 0 and kc == 1:
            return B + C
        elif ka == 1 and kc == 1:
            return A + C
        elif ka == 1 and kc == 0:
            return A + B
        else:
            return B + C
    elif j == 2:
        if ka == 0 and kc == 2:
            return 2.0 * (A + B + C) - 2.0 * jnp.sqrt((B - C)**2 + (A - C)*(A - B))
        elif ka == 1 and kc == 2:
            return A + B + 4.0 * C
        elif ka == 1 and kc == 1:
            return A + 4.0 * B + C
        elif ka == 2 and kc == 1:
            return 4.0 * A + B + C
        elif ka == 2 and kc == 0:
            return 2.0 * (A + B + C) + 2.0 * jnp.sqrt((B - C)**2 + (A - C)*(A - B))
        else:
            return 2.0 * (B + C)
    else:
        avg_bc = 0.5 * (B + C)
        return avg_bc * j * (j + 1) + (A - avg_bc) * (ka**2)


def compute_rigid_rotor_frequencies(
    A: float,
    B: float,
    C: float,
    transitions: Sequence[Tuple[int, int, int, int, int, int]],
) -> np.ndarray:
    """Calculate theoretical rigid rotor transition frequencies (in MHz) using JAX."""
    A_j = jnp.asarray(A, dtype=jnp.float64)
    B_j = jnp.asarray(B, dtype=jnp.float64)
    C_j = jnp.asarray(C, dtype=jnp.float64)

    freqs = []
    for (jp, kap, kcp, jpp, kapp, kcpp) in transitions:
        e_upper = _calculate_asymmetric_energy(A_j, B_j, C_j, jp, kap, kcp)
        e_lower = _calculate_asymmetric_energy(A_j, B_j, C_j, jpp, kapp, kcpp)
        freq = e_upper - e_lower
        freqs.append(freq)

    return np.array([float(f) for f in freqs], dtype=np.float64)


def compute_analytical_jacobian(
    A: float,
    B: float,
    C: float,
    transitions: Sequence[Tuple[int, int, int, int, int, int]],
) -> np.ndarray:
    """Compute exact analytical Jacobian d(frequency)/d(A, B, C) via JAX autodiff."""
    params = jnp.array([A, B, C], dtype=jnp.float64)

    def _freq_vector(p: jnp.ndarray) -> jnp.ndarray:
        a_val, b_val, c_val = p[0], p[1], p[2]
        res = []
        for (jp, kap, kcp, jpp, kapp, kcpp) in transitions:
            e_up = _calculate_asymmetric_energy(a_val, b_val, c_val, jp, kap, kcp)
            e_low = _calculate_asymmetric_energy(a_val, b_val, c_val, jpp, kapp, kcpp)
            res.append(e_up - e_low)
        return jnp.stack(res)

    jac_fn = jax.jacobian(_freq_vector)
    jac_matrix = jac_fn(params)
    return np.array(jac_matrix, dtype=np.float64)


class GaussianProcessSpectralRegressor:
    """Gaussian Process Regressor for learning O-C residual shifts on assignment commits."""

    def __init__(self, alpha: float = 1e-4, random_state: int = 42) -> None:
        self.alpha = alpha
        self.random_state = random_state
        self.kernel = ConstantKernel(1.0, (1e-3, 1e3)) * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e2)) + WhiteKernel(noise_level=alpha)
        self.model = GaussianProcessRegressor(
            kernel=self.kernel,
            alpha=self.alpha,
            random_state=self.random_state,
            n_restarts_optimizer=2,
            normalize_y=True,
        )
        self.is_fitted = False

    @staticmethod
    def extract_features(transitions: Sequence[Dict[str, Any]]) -> np.ndarray:
        """Extract spectroscopic quantum and dipole feature vectors."""
        feature_rows = []
        for t in transitions:
            row = [
                float(t.get("j_prime", 0)),
                float(t.get("ka_prime", 0)),
                float(t.get("kc_prime", 0)),
                float(t.get("j_double_prime", 0)),
                float(t.get("ka_double_prime", 0)),
                float(t.get("kc_double_prime", 0)),
                float(t.get("mu_a", 0.0)),
                float(t.get("mu_b", 0.0)),
                float(t.get("mu_c", 0.0)),
                float(t.get("lower_energy_cm", 0.0)),
            ]
            feature_rows.append(row)
        return np.array(feature_rows, dtype=np.float64)

    def fit(self, training_transitions: Sequence[Dict[str, Any]]) -> GaussianProcessSpectralRegressor:
        """Train GP regressor on committed assignment O-C residuals."""
        if not training_transitions:
            raise ValueError("Cannot fit GP on empty transition list")
        X = self.extract_features(training_transitions)
        y = np.array([float(t.get("residual_mhz", 0.0)) for t in training_transitions], dtype=np.float64)
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict_shift(self, query_transitions: Sequence[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Predict frequency shift (in MHz) and standard deviation uncertainty."""
        if not self.is_fitted:
            raise RuntimeError("GaussianProcessSpectralRegressor is not fitted yet")
        X = self.extract_features(query_transitions)
        mean_pred, std_pred = self.model.predict(X, return_std=True)
        return mean_pred, std_pred

    def tag_predictions(
        self,
        query_transitions: Sequence[Dict[str, Any]],
        ab_initio: bool = False,
    ) -> List[Dict[str, Any]]:
        """Tag predicted transitions as [TORQ] (ab initio) or [ML] (GP-corrected)."""
        tagged_list = []
        if ab_initio or not self.is_fitted:
            for t in query_transitions:
                item = dict(t)
                item["tag"] = "[TORQ]"
                item["ml_corrected_freq_mhz"] = item.get("calc_freq_mhz", 0.0)
                item["uncertainty_mhz"] = 0.0
                tagged_list.append(item)
        else:
            shifts, sigmas = self.predict_shift(query_transitions)
            for i, t in enumerate(query_transitions):
                item = dict(t)
                calc_f = item.get("calc_freq_mhz", 0.0)
                item["tag"] = "[ML]"
                item["ml_shift_mhz"] = float(shifts[i])
                item["ml_corrected_freq_mhz"] = float(calc_f + shifts[i])
                item["uncertainty_mhz"] = float(sigmas[i])
                tagged_list.append(item)
        return tagged_list


def evaluate_dual_engine_parity(
    jax_constants: Dict[str, float],
    spfit_constants: Dict[str, float],
    threshold_khz: float = 0.1,
) -> Dict[str, Any]:
    """Compare JAX and SPFIT constants and enforce dual-engine parity."""
    deltas_khz = {}
    max_delta = 0.0

    for k, jax_val in jax_constants.items():
        if k in spfit_constants:
            spfit_val = spfit_constants[k]
            d_khz = abs(jax_val - spfit_val) * 1000.0
            deltas_khz[k] = float(d_khz)
            if d_khz > max_delta:
                max_delta = d_khz

    warning = max_delta > threshold_khz
    return {
        "parity_passed": not warning,
        "parity_warning": warning,
        "max_delta_khz": float(max_delta),
        "threshold_khz": float(threshold_khz),
        "deltas_khz": deltas_khz,
    }


def calculate_information_gain(covariance_matrix: np.ndarray, jacobian: np.ndarray) -> np.ndarray:
    """Calculate Information Gain score based on Jacobian sensitivity and covariance."""
    var_contributions = np.einsum("ij,jk,ik->i", jacobian, covariance_matrix, jacobian)
    return np.asarray(np.sqrt(np.maximum(var_contributions, 1e-12)), dtype=np.float64)


def apply_resolvability_filter(
    frequencies: np.ndarray,
    intensities: np.ndarray,
    instrument_resolution_mhz: float = 0.05,
) -> np.ndarray:
    """Penalize clustered transitions below experimental resolution linewidth."""
    n = len(frequencies)
    weights = np.ones(n, dtype=np.float64)
    min_separation = 2.0 * instrument_resolution_mhz

    for i in range(n):
        diffs = np.abs(frequencies - frequencies[i])
        diffs[i] = np.inf
        closest_dist = np.min(diffs)
        if closest_dist < min_separation:
            penalty = closest_dist / min_separation
            weights[i] = max(0.1, float(penalty))

    return weights


def rank_scan_windows(
    candidate_transitions: Sequence[Dict[str, Any]],
    covariance_matrix: np.ndarray,
    jacobian: np.ndarray,
    window_size_mhz: float = 500.0,
) -> List[Dict[str, Any]]:
    """Rank hardware-aware chunked scan regions by aggregated Information Gain."""
    if not candidate_transitions:
        return []

    scores = calculate_information_gain(covariance_matrix, jacobian)
    freqs = np.array([float(t.get("freq_mhz", 0.0)) for t in candidate_transitions])
    min_f = np.min(freqs)
    max_f = np.max(freqs)

    windows = []
    curr_start = min_f
    while curr_start <= max_f:
        curr_end = curr_start + window_size_mhz
        mask = (freqs >= curr_start) & (freqs < curr_end)
        count = int(np.sum(mask))
        if count > 0:
            total_gain = float(np.sum(scores[mask]))
            windows.append({
                "start_freq_mhz": float(curr_start),
                "end_freq_mhz": float(curr_end),
                "transition_count": count,
                "total_info_gain": total_gain,
            })
        curr_start += window_size_mhz

    windows.sort(key=lambda w: w["total_info_gain"], reverse=True)
    return windows
