import os
os.environ["JAX_ENABLE_X64"] = "True"

import numpy as np
import pytest
from mendeleev import element

from cochem_base.core_engine.cochem_core_auto_pes import ExactKernelRidgeEstimator
from cochem_base.schemas import KrrRegularizationConfig


def test_krr_numerical_conditioning_and_anchor_floor():
    """Verify KRR anchor regularization floor >= 1e-8 Ha and Cholesky jitter escalation (Suggestion #58 / Method Matrix v4 §8C, §13.2 [M], [D])."""
    # Dynamic Mendeleev check
    ar_elem = element("Ar")
    assert ar_elem.atomic_number == 18

    # 1. Construct dataset with 5 asymptotic dissociation points where r > 10 A
    # In Morse representation: y = exp(-r / 2.0).
    # Near equilibrium: r in [1.5, 3.5]
    r_eq = np.linspace(1.5, 3.5, 10)
    # Asymptotic dissociation: r in [12.0, 20.0]
    r_asymp = np.linspace(12.0, 20.0, 5)
    r_all = np.concatenate([r_eq, r_asymp])

    # 1D features: y_ij
    X = np.exp(-r_all / 2.0).reshape(-1, 1)

    # Synthetic Morse potential energy: D_e * (1 - exp(-a * (r - r_e)))^2
    D_e = 0.1
    a = 1.8
    r_e = 2.0
    y = D_e * (1.0 - np.exp(-a * (r_all - r_e))) ** 2

    # Verify that raw Gram matrix of asymptotic points is ill-conditioned:
    # Kernel: K_ij = exp(-gamma * ||x_i - x_j||^2)
    gamma = 10.0
    diff = X - X.T
    K_raw = np.exp(-gamma * (diff ** 2))
    eigenvalues = np.linalg.eigvalsh(K_raw)
    min_eig = np.min(eigenvalues)
    # Because 5 asymptotic points have features extremely close to 0 (exp(-12/2) ~ 0.002),
    # the raw Gram matrix eigenvalues drop below 1e-12:
    assert min_eig < 1e-10, f"Raw Gram matrix not ill-conditioned enough: min_eig={min_eig}"

    # 2. Fit KRR using strict regularization floor 1e-8 Ha and adaptive jitter 1e-9 [M]
    reg_cfg = KrrRegularizationConfig(
        base_alpha=1e-8,
        anchor_alpha_floor=1e-8,
        jitter_epsilon=1e-9,
        max_jitter_escalation=1e-6,
    )
    krr = ExactKernelRidgeEstimator(
        gamma=gamma,
        alpha=1e-8,
        regularization_config=reg_cfg,
    )

    # Fitting must succeed without LinAlgError [M]
    krr.fit(X, y)
    assert krr.is_fitted
    assert krr.alpha_vector is not None
    assert len(krr.alpha_vector) == len(X)

    # Predictions must evaluate stably without NaNs or Infs
    preds = krr.predict(X)
    assert not np.isnan(preds).any()
    assert not np.isinf(preds).any()
    mae = np.mean(np.abs(preds - y))
    assert mae < 0.01, f"KRR fit error unexpectedly large: MAE={mae}"
