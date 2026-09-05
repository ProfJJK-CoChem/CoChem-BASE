"""Zero-mock unit test for FP64 Gram Matrix Condition-Number Floor & Chunked Batching in KRR.

SRS Chunk 14 / Suggestion #137 / Method Matrix v4 §13.2 [M], [D].
Zero-Mock Mandate v3: Completely authentic numerical conditioning and IEEE-754 FP64 stability.
"""

from __future__ import annotations

import numpy as np

from cochem_base.core_engine.cochem_core_auto_pes import (
    ExactKernelRidgeEstimator,
    KernelType,
)
from cochem_base.schemas import KrrRegularizationConfig


def test_krr_gram_matrix_condition_number_floor_and_cholesky_stability() -> None:
    """Verify condition-number floor (alpha_anchor >= 1e-8) and Tikhonov jitter (eps=1e-9) solve via Cholesky [M], [D]."""
    n_samples = 150
    n_features = 12

    # Deterministic physical Morse coordinates y = exp(-R / lambda) with clusters near dissociation (y ~ 0)
    grid_r = np.array(
        [[0.8 + 0.05 * i + 0.02 * j for j in range(n_features)] for i in range(n_samples)],
        dtype=np.float64,
    )
    X = np.exp(-grid_r / 1.5)
    # Near-dissociation points where R > 15 A => y ~ 1e-5
    X[:30, :] = 1e-5 * np.array(
        [[1.0 + 0.01 * (i + j) for j in range(n_features)] for i in range(30)],
        dtype=np.float64,
    )

    # Potential energies with asymptotic zero dissociation
    y = -1.0 * np.exp(-5.0 * np.sum(X, axis=1))
    y[:30] = 0.0  # Asymptotic zero anchor points

    reg_cfg = KrrRegularizationConfig(
        anchor_alpha_floor=1e-8,
        jitter_epsilon=1e-9,
        max_jitter_escalation=1e-4,
    )

    estimator = ExactKernelRidgeEstimator(
        kernel_type=KernelType.RBF,
        alpha=1e-7,
        asymptotic_zero=True,
        reg_config=reg_cfg,
    )

    # Fitting must succeed via Cholesky factorization without exception
    estimator.fit(X, y)
    assert estimator.is_fitted is True
    assert estimator.weights is not None
    assert estimator.weights.shape == (n_samples,)
    assert not np.isnan(estimator.weights).any()
    assert not np.isinf(estimator.weights).any()

    # Prediction must execute accurately on training data
    preds = estimator.predict(X, batch_size=64)
    rmse = float(np.sqrt(np.mean((preds - y) ** 2)))
    assert rmse < 0.05, f"KRR fitting accuracy too low: RMSE {rmse:.4f}"


def test_krr_chunked_batch_evaluation_transient_memory() -> None:
    """Verify chunked batching processes evaluation data without overflowing memory [D]."""
    n_train = 50
    n_test = 500
    n_dim = 8

    grid_train = np.array(
        [[1.0 + 0.04 * i + 0.01 * j for j in range(n_dim)] for i in range(n_train)],
        dtype=np.float64,
    )
    X_train = np.exp(-grid_train / 1.5)
    y_train = np.sum(X_train ** 2, axis=1)

    estimator = ExactKernelRidgeEstimator(kernel_type=KernelType.RBF, alpha=1e-5)
    estimator.fit(X_train, y_train)

    grid_test = np.array(
        [[0.9 + 0.01 * i + 0.02 * j for j in range(n_dim)] for i in range(n_test)],
        dtype=np.float64,
    )
    X_test = np.exp(-grid_test / 1.5)

    # Predict with small batch_size to test chunking loop
    preds_chunked = estimator.predict(X_test, batch_size=64)
    # Predict with full batch
    preds_full = estimator.predict(X_test, batch_size=n_test)

    # Chunked and full evaluations must yield identical numerical results
    assert np.allclose(preds_chunked, preds_full, atol=1e-12)
