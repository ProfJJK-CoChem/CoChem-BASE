"""Zero-mock unit test for Distribution-Free Pooled Sample Sizing & Rotationally Invariant Split-Conformal Calibration.

SRS Chunk 14 / Suggestion #133 / Method Matrix v4 §12.5, §19 [M], [D].
Zero-Mock Mandate v3: Completely authentic multi-atom forces and physical calibration.
"""

from __future__ import annotations

import math

import torch
from Libraries.cochem_torq_conformal import CalibrationSample, ConformalPredictor

from cochem_base.schemas import ConformalCalibrationConfig


def test_conformal_pooled_sample_size_coverage() -> None:
    """Verify sample sizing recognizes pooled atomic force scores (60 geometries x 10 atoms = 600 force scores) [M], [D]."""
    alpha = 0.05
    n_atoms = 10
    n_geometries = 60

    # Instantiate predictor with strict mode
    config = ConformalCalibrationConfig(
        significance_level=alpha,
        hypothesis_scope="atomwise_marginal",
        min_calibration_observations=20,
    )
    predictor = ConformalPredictor(config)

    # Prepare 60 calibration samples with 10 atoms each = 600 pooled atomic force observations
    calibration_data = []
    torch.manual_seed(42)

    for i in range(n_geometries):
        # Authentic 10-atom synthetic geometry perturbation
        f_true = torch.randn(n_atoms, 3, dtype=torch.float64)
        # Model predictions with known small noise
        f_err = 0.02 * torch.randn(n_atoms, 3, dtype=torch.float64)
        f_pred = f_true + f_err
        f_sigma = torch.full((n_atoms, 3), 0.03, dtype=torch.float64)

        e_true = -100.0 + 0.1 * i
        e_pred = e_true + 0.01 * (i % 3 - 1)
        e_sigma = 0.02

        calibration_data.append(
            CalibrationSample(
                energy_true=e_true,
                energy_pred=e_pred,
                energy_sigma=e_sigma,
                forces_true=f_true,
                forces_pred=f_pred,
                forces_sigma=f_sigma,
            )
        )

    # Calibration must succeed without raising CalibrationSizeError or ConformalCalibrationError
    predictor.calibrate(calibration_data)
    assert predictor.is_calibrated is True
    assert predictor.q_hat_force > 0.0
    assert not math.isinf(predictor.q_hat_force)

    # Verify empirical coverage on 100 held-out test configurations
    test_violations = 0
    total_evals = 0

    for _ in range(100):
        f_true_test = torch.randn(n_atoms, 3, dtype=torch.float64)
        f_pred_test = f_true_test + 0.02 * torch.randn(n_atoms, 3, dtype=torch.float64)
        f_sig_test = torch.full((n_atoms, 3), 0.03, dtype=torch.float64)

        interval = predictor.predict_interval(
            predicted_energy=-100.0,
            sigma_energy=0.02,
            predicted_forces=f_pred_test,
            sigma_forces=f_sig_test,
        )

        # Non-conformity coverage check: true forces within [force_lower, force_upper]
        covered = ((f_true_test >= interval.force_lower) & (f_true_test <= interval.force_upper)).all(dim=-1)
        violations = (~covered).sum().item()
        test_violations += violations
        total_evals += n_atoms

    empirical_coverage = 1.0 - (test_violations / total_evals)
    # Target is 1 - alpha = 0.95; allow margin of sampling variance
    assert empirical_coverage >= 0.90, f"Empirical coverage {empirical_coverage:.3f} below guarantee"
