"""BASE compatibility exports; unsupported TORQ science stays unavailable.

No sibling checkout or cross-environment Python objects are imported.
"""

from __future__ import annotations

from cochem_base.core_engine.cochem_core_auto_pes import ExactKernelRidgeEstimator
from cochem_base.ml._legacy_api import unavailable_attribute
from cochem_base.schemas import ANI2xCutoffConfig, ForceMatchingLossConfig, KrrRegularizationConfig

_UNAVAILABLE = (
    "ANI2xModel",
    "ForceMatchingLoss",
    "compute_angular_cosine_similarity",
    "compute_conservative_forces",
    "cosine_cutoff_envelope",
    "huber_force_loss",
    "huber_scalar_loss",
    "quintic_c2_envelope",
)


def __getattr__(name: str):
    return unavailable_attribute(__name__, name, _UNAVAILABLE)


__all__ = [
    "ANI2xCutoffConfig",
    "ExactKernelRidgeEstimator",
    "ForceMatchingLossConfig",
    "KrrRegularizationConfig",
]
