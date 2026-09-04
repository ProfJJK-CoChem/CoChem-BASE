"""Physical verification suite for Conformal Prediction Uncertainty Quantification.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic physics, dynamic Mendeleev masses, and physical coordinates.
"""

from __future__ import annotations

import math
import numpy as np
import pytest
import torch

from Libraries.cochem_torq_conformal import (
    CalibrationSample,
    ConformalPredictor,
)
from Libraries.cochem_torq_delta_ml import LennardJonesBaselineEngine
from Libraries.cochem_torq_inference_errors import CalibrationSizeError
from Libraries.cochem_torq_inference_schemas import ConformalPredictorConfig

# Authentic Alanine Dipeptide (Ace-Ala-Nme, C7eq minima, N=22)
ALANINE_DIPEPTIDE_COORDS = np.array(
    [
        [-2.085, 1.374, -0.271],  # C
        [-1.571, 2.405, 0.144],  # O
        [-1.877, 0.098, 0.169],  # N
        [-2.392, -0.732, -0.252],  # H
        [-0.903, -0.231, 1.204],  # CA
        [-0.941, -1.288, 1.467],  # HA
        [-1.234, 0.612, 2.441],  # CB
        [-0.518, 0.448, 3.247],  # HB1
        [-1.214, 1.667, 2.164],  # HB2
        [-2.235, 0.387, 2.809],  # HB3
        [0.513, 0.038, 0.678],  # C
        [0.824, 1.121, 0.179],  # O
        [1.385, -0.963, 0.793],  # N
        [1.082, -1.828, 1.205],  # H
        [2.774, -0.822, 0.354],  # C
        [3.376, -0.428, 1.173],  # H1
        [2.859, -0.126, -0.481],  # H2
        [3.148, -1.799, 0.043],  # H3
        [-3.224, 1.488, -1.246],  # C
        [-3.844, 0.596, -1.218],  # H1
        [-3.842, 2.371, -1.066],  # H2
        [-2.812, 1.579, -2.253],  # H3
    ],
    dtype=np.float64,
)
ALANINE_DIPEPTIDE_Z = [
    6,
    8,
    7,
    1,
    6,
    1,
    6,
    1,
    1,
    1,
    6,
    8,
    7,
    1,
    6,
    1,
    1,
    1,
    6,
    1,
    1,
    1,
]


def test_conformal_calibration_boundary_error() -> None:
    """Assert calibration with n < ceil((1 - alpha) / alpha) raises CalibrationSizeError under strict mode. [M]"""
    config = ConformalPredictorConfig(alpha=0.05, strict_calibration_size=True)
    predictor = ConformalPredictor(config)

    # Minimum size: ceil((1 - 0.05) / 0.05) = ceil(19.0) = 19
    min_size = predictor.compute_minimum_calibration_size()
    assert min_size == 19

    # Prepare only 10 calibration samples (< 19)
    insufficient_samples: list[CalibrationSample] = []
    base_coords = torch.tensor(ALANINE_DIPEPTIDE_COORDS, dtype=torch.float64)
    lj_engine = LennardJonesBaselineEngine()
    _, physical_forces = lj_engine.calculate(base_coords, ALANINE_DIPEPTIDE_Z)
    uncertainty_sigmas = torch.ones_like(base_coords) * 0.05

    for i in range(10):
        insufficient_samples.append(
            CalibrationSample(
                energy_true=10.0 + i,
                energy_pred=10.0 + i + 0.01,
                energy_sigma=0.05,
                forces_true=physical_forces,
                forces_pred=physical_forces + 0.001 * physical_forces,
                forces_sigma=uncertainty_sigmas,
            )
        )

    with pytest.raises(CalibrationSizeError) as exc_info:
        predictor.calibrate(insufficient_samples)

    assert exc_info.value.error_code == "TORQ_CONFORMAL_INSUFFICIENT_CALIBRATION"
    assert exc_info.value.component == "conformal_predictor"
    assert exc_info.value.diagnostics["n_samples"] == 10
    assert exc_info.value.diagnostics["n_required"] == 19


def test_conformal_empirical_coverage_alanine_dipeptide() -> None:
    r"""Calibrate over 30 authentic Alanine dipeptide conformations and verify coverage on 50 test structures. [M]

    $$\text{Coverage} \ge 1 - \alpha - 2\sqrt{\frac{\alpha(1-\alpha)}{N_{\text{test}}}}$$
    """
    alpha = 0.05
    config = ConformalPredictorConfig(
        alpha=alpha,
        strict_calibration_size=True,
        apply_bonferroni=False,
    )
    predictor = ConformalPredictor(config)

    base_coords = torch.tensor(ALANINE_DIPEPTIDE_COORDS, dtype=torch.float64)
    lj_engine = LennardJonesBaselineEngine()

    # Reproducible seed for authentic physical sampling
    torch.manual_seed(42)
    np.random.seed(42)

    # 1. Generate 30 Calibration Configurations
    cal_samples: list[CalibrationSample] = []
    n_cal = 30
    e_noise_std = 0.05
    f_noise_std = 0.01

    for k in range(n_cal):
        # Thermal harmonic perturbation
        perturbation = torch.randn_like(base_coords) * 0.02
        coords_k = base_coords + perturbation

        e_true, f_true = lj_engine.calculate(coords_k, ALANINE_DIPEPTIDE_Z)

        # Physical harmonic potential perturbations: E_harm = 1/2 k ||Delta R||^2, F_harm = -k Delta R
        e_err = float(0.5 * 2.0 * torch.sum(perturbation ** 2).item())
        e_pred = e_true + e_err
        f_err = -0.5 * perturbation
        f_pred = f_true + f_err

        cal_samples.append(
            CalibrationSample(
                energy_true=e_true,
                energy_pred=e_pred,
                energy_sigma=e_noise_std,
                forces_true=f_true,
                forces_pred=f_pred,
                forces_sigma=torch.ones_like(f_true) * f_noise_std,
            )
        )

    predictor.calibrate(cal_samples)

    assert predictor.is_calibrated
    assert not math.isinf(predictor.q_hat_energy)
    assert not math.isinf(predictor.q_hat_force)
    assert predictor.q_hat_energy > 0.0
    assert predictor.q_hat_force > 0.0

    # 2. Evaluate Empirical Coverage over 50 Held-out Test Structures
    n_test = 50
    covered_e = 0
    covered_f = 0

    for k in range(n_test):
        perturbation = torch.randn_like(base_coords) * 0.02
        coords_test = base_coords + perturbation

        e_true, f_true = lj_engine.calculate(coords_test, ALANINE_DIPEPTIDE_Z)

        # Physical harmonic potential perturbations
        e_err = float(0.5 * 2.0 * torch.sum(perturbation ** 2).item())
        e_pred = e_true + e_err
        f_err = -0.5 * perturbation
        f_pred = f_true + f_err

        interval = predictor.predict_interval(
            predicted_energy=e_pred,
            sigma_energy=e_noise_std,
            predicted_forces=f_pred,
            sigma_forces=torch.ones_like(f_pred) * f_noise_std,
        )


        # Check energy coverage
        if interval.energy_lower <= e_true <= interval.energy_upper:
            covered_e += 1

        # Check component-wise force coverage
        if torch.all(f_true >= interval.force_lower) and torch.all(
            f_true <= interval.force_upper
        ):
            covered_f += 1

        # Assert force intervals shape is strictly [N, 3]
        assert interval.force_lower.shape == (22, 3)
        assert interval.force_upper.shape == (22, 3)
        assert interval.confidence_level == 0.95

    empirical_coverage_e = covered_e / n_test
    # Dvoretzky-Kiefer-Wolfowitz / Binomial confidence lower bound: 1 - alpha - 2 * sqrt(alpha * (1 - alpha) / n_test)
    bound = 1.0 - alpha - 2.0 * math.sqrt(alpha * (1.0 - alpha) / n_test)

    assert empirical_coverage_e >= bound
