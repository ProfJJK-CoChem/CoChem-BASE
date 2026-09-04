import os
os.environ["JAX_ENABLE_X64"] = "True"

import pytest
import torch
from mendeleev import element

from Libraries.cochem_torq_conformal import CalibrationSample, ConformalPredictor
from cochem_base.exceptions import ConformalCalibrationError
from cochem_base.schemas import ConformalCalibrationConfig


def test_conformal_force_sample_complexity_and_coverage():
    """Verify pooled atomic force observation complexity n >= 20 and empirical coverage (Suggestion #54 / Method Matrix v4 §12.5, §19 [M], [D])."""
    # Dynamic Mendeleev check: H and O in water
    h_elem = element("H")
    o_elem = element("O")
    assert h_elem.atomic_number == 1
    assert o_elem.atomic_number == 8

    torch.manual_seed(42)

    # 1. Ten water molecules: 3 atoms each -> 30 atomic force observations (>= 20 threshold) [M]
    n_waters_calib = 10
    n_atoms_per_water = 3
    calib_samples = []
    for _ in range(n_waters_calib):
        f_true = torch.zeros((n_atoms_per_water, 3), dtype=torch.float64)
        # Add bounded noise as model error
        f_err = torch.randn((n_atoms_per_water, 3), dtype=torch.float64) * 0.05
        f_pred = f_true + f_err
        f_sigma = torch.ones((n_atoms_per_water, 3), dtype=torch.float64) * 0.05

        calib_samples.append(
            CalibrationSample(
                energy_true=-76.4,
                energy_pred=-76.39,
                energy_sigma=0.01,
                forces_true=f_true,
                forces_pred=f_pred,
                forces_sigma=f_sigma,
            )
        )

    cfg = ConformalCalibrationConfig(
        significance_level=0.05,
        hypothesis_scope="marginal",
        min_calibration_observations=20,
    )
    predictor = ConformalPredictor(config=cfg)

    # Calibrate on 30 pooled observations: must succeed
    metrics = predictor.calibrate(calib_samples)
    assert predictor.q_hat_force is not None
    assert predictor.q_hat_force > 0.0

    # 2. Evaluate empirical coverage on 100 held-out test configurations [D]
    n_test = 100
    covered_atoms = 0
    total_test_atoms = n_test * n_atoms_per_water

    for _ in range(n_test):
        f_true = torch.zeros((n_atoms_per_water, 3), dtype=torch.float64)
        f_err = torch.randn((n_atoms_per_water, 3), dtype=torch.float64) * 0.05
        f_pred = f_true + f_err
        f_sigma = torch.ones((n_atoms_per_water, 3), dtype=torch.float64) * 0.05

        interval = predictor.predict_forces(f_pred, f_sigma)
        # Non-conformity score: ||F_true - F_pred|| / sigma
        res_norm = torch.norm(f_true - f_pred, p=2, dim=-1)
        sigma_norm = torch.mean(f_sigma, dim=-1)
        scores = res_norm / (sigma_norm + 1e-4)

        for s in scores:
            if s.item() <= predictor.q_hat_force:
                covered_atoms += 1

    empirical_coverage = covered_atoms / total_test_atoms
    assert empirical_coverage >= 0.90, f"Empirical coverage {empirical_coverage:.3f} fell below statistical expectation"

    # 3. Insufficient sample size check: 4 water molecules -> 12 observations (< 20 threshold) [M]
    predictor_fail = ConformalPredictor(config=cfg)
    calib_insufficient = calib_samples[:4]
    with pytest.raises(ConformalCalibrationError) as exc_info:
        predictor_fail.calibrate(calib_insufficient)

    assert "Insufficient pooled calibration observations" in str(exc_info.value)
    assert "received n=12" in str(exc_info.value)
