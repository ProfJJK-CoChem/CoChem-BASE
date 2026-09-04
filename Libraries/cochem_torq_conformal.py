"""Conformal Prediction Uncertainty Quantification Suite for CoChem-TORQ.

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Completely authentic mathematical conformal bounds and physical residuals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import torch

from Libraries.cochem_torq_inference_errors import CalibrationSizeError
from Libraries.cochem_torq_inference_schemas import ConformalInterval, ConformalPredictorConfig


@dataclass
class CalibrationSample:
    """Authentic physical calibration structure with true values and model predictions. [M]"""

    energy_true: float
    energy_pred: float
    energy_sigma: float
    forces_true: torch.Tensor  # Shape: [N, 3]
    forces_pred: torch.Tensor  # Shape: [N, 3]
    forces_sigma: torch.Tensor  # Shape: [N, 3] or [N]


class ConformalPredictor:
    """Inductive Conformal Prediction wrapper providing distribution-free finite-sample guarantees. [M]"""

    def __init__(self, config: Optional[ConformalPredictorConfig] = None) -> None:
        self.config = config or ConformalPredictorConfig()
        self.alpha = self.config.alpha
        self.eps_e = self.config.regularization_energy
        self.eps_f = self.config.regularization_force
        self.strict = self.config.strict_calibration_size
        self.apply_bonferroni = self.config.apply_bonferroni

        self.q_hat_energy: float = float("inf")
        self.q_hat_force: float = float("inf")
        self.is_calibrated: bool = False

    def compute_minimum_calibration_size(self, num_atoms: Optional[int] = None) -> int:
        r"""Compute exact minimum calibration sample size n_min. [M]

        $$n_{\min} = \left\lceil \frac{1 - \alpha}{\alpha} \right\rceil$$
        $$n_{\min}^{\text{eff}} = \left\lceil \frac{3N - \alpha}{\alpha} \right\rceil \text{ (if Bonferroni active)}$$
        """
        if self.apply_bonferroni and num_atoms is not None:
            num_components = 3 * num_atoms
            return math.ceil((num_components - self.alpha) / self.alpha)
        return math.ceil((1.0 - self.alpha) / self.alpha)

    def calibrate(self, calibration_data: Sequence[CalibrationSample]) -> None:
        r"""Compute non-conformity empirical quantiles over exchangeable calibration dataset. [D]

        Parameters
        ----------
        calibration_data : Sequence[CalibrationSample]
            Calibration configurations with ground-truth and predicted observables.
        """
        n_samples = len(calibration_data)
        if n_samples == 0:
            raise CalibrationSizeError(
                "Calibration dataset is empty",
                n_samples=0,
                n_required=self.compute_minimum_calibration_size(),
            )

        n_atoms = calibration_data[0].forces_true.shape[0]
        n_required = self.compute_minimum_calibration_size(num_atoms=n_atoms)

        if n_samples < n_required:
            if self.strict:
                raise CalibrationSizeError(
                    f"Insufficient calibration samples: received n={n_samples}, strictly requires n >= {n_required}",
                    n_samples=n_samples,
                    n_required=n_required,
                )
            # Permissive fallback: infinite interval
            self.q_hat_energy = float("inf")
            self.q_hat_force = float("inf")
            self.is_calibrated = True
            return

        # 1. Scalar Energy Non-Conformity Scores
        energy_scores: List[float] = []
        for sample in calibration_data:
            residual = abs(sample.energy_true - sample.energy_pred)
            s_e = residual / (sample.energy_sigma + self.eps_e)
            energy_scores.append(float(s_e))

        energy_scores.sort()
        # Finite-sample quantile index: p = ceil((n + 1)(1 - alpha))
        p_energy = math.ceil((n_samples + 1) * (1.0 - self.alpha))
        if p_energy <= n_samples:
            self.q_hat_energy = energy_scores[p_energy - 1]
        else:
            self.q_hat_energy = float("inf")

        # 2. Rotationally Invariant Per-Atom Force Non-Conformity Scores
        force_scores: List[float] = []
        for sample in calibration_data:
            f_true = sample.forces_true.to(dtype=torch.float64)
            f_pred = sample.forces_pred.to(dtype=torch.float64)
            f_sig = sample.forces_sigma.to(dtype=torch.float64)

            # Per-atom Euclidean norm difference: ||F_i - F_hat_i||_2
            diff = torch.norm(f_true - f_pred, dim=-1)  # [N]

            # Invariant per-atom sigma: sqrt(1/3 * sum_alpha sigma_alpha^2) if [N, 3], or [N]
            if f_sig.ndim == 2 and f_sig.shape[-1] == 3:
                sig_atom = torch.sqrt(torch.mean(f_sig ** 2, dim=-1))
            else:
                sig_atom = f_sig.view(-1)

            s_f = diff / (sig_atom + self.eps_f)
            force_scores.extend([float(v.item()) for v in s_f])

        force_scores.sort()
        n_force_scores = len(force_scores)

        # Quantile index for forces
        if self.apply_bonferroni:
            alpha_eff = self.alpha / (3.0 * n_atoms)
        else:
            alpha_eff = self.alpha

        p_force = math.ceil((n_force_scores + 1) * (1.0 - alpha_eff))
        if p_force <= n_force_scores:
            self.q_hat_force = force_scores[p_force - 1]
        else:
            self.q_hat_force = float("inf")

        self.is_calibrated = True

    def predict_interval(
        self,
        predicted_energy: float,
        sigma_energy: float,
        predicted_forces: torch.Tensor,
        sigma_forces: torch.Tensor,
    ) -> ConformalInterval:
        r"""Evaluate finite-sample distribution-free prediction intervals. [D]

        $$\mathcal{C}_E = [\hat{E} - \hat{q}_{1-\alpha}^E (\hat{\sigma}_E + \epsilon_E), \; \hat{E} + \hat{q}_{1-\alpha}^E (\hat{\sigma}_E + \epsilon_E)]$$
        $$\mathcal{C}_{\mathbf{F}, i, \alpha} = [\hat{F}_{i, \alpha} - \hat{q}^F (\hat{\sigma}_{F, i} + \epsilon_F), \; \hat{F}_{i, \alpha} + \hat{q}^F (\hat{\sigma}_{F, i} + \epsilon_F)]$$
        """
        if not self.is_calibrated:
            raise RuntimeError("ConformalPredictor must be calibrated before generating prediction intervals.")

        # Energy Interval
        if math.isinf(self.q_hat_energy):
            e_lower = float("-inf")
            e_upper = float("inf")
        else:
            delta_e = self.q_hat_energy * (sigma_energy + self.eps_e)
            e_lower = float(predicted_energy - delta_e)
            e_upper = float(predicted_energy + delta_e)

        # Force Interval
        device = predicted_forces.device
        dtype = predicted_forces.dtype

        if math.isinf(self.q_hat_force):
            f_lower = torch.full_like(predicted_forces, float("-inf"))
            f_upper = torch.full_like(predicted_forces, float("inf"))
        else:
            if sigma_forces.ndim == 2 and sigma_forces.shape[-1] == 3:
                sig_atom = torch.sqrt(torch.mean(sigma_forces ** 2, dim=-1, keepdim=True))
            else:
                sig_atom = sigma_forces.view(-1, 1)

            delta_f = self.q_hat_force * (sig_atom + self.eps_f)
            f_lower = predicted_forces - delta_f
            f_upper = predicted_forces + delta_f

        return ConformalInterval(
            energy_lower=e_lower,
            energy_upper=e_upper,
            force_lower=f_lower.to(dtype=dtype, device=device),
            force_upper=f_upper.to(dtype=dtype, device=device),
            confidence_level=float(1.0 - self.alpha),
        )
