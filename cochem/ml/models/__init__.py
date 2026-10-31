"""BASE compatibility exports; unsupported TORQ science stays unavailable.

No sibling checkout or cross-environment Python objects are imported.
"""

from __future__ import annotations

from cochem_base.core_engine.cochem_core_auto_pes import ExactKernelRidgeEstimator
from cochem_base.ml._legacy_api import unavailable_attribute
from cochem_base.schemas import (
    ANI2xCutoffConfig,
    CommitteeEnsembleConfig,
    ForceMatchingLossConfig,
    KrrRegularizationConfig,
)

_UNAVAILABLE = (
    "ANI2xModel",
    "CommitteeEnsemble",
    "CommitteePrediction",
    "ForceMatchingLoss",
    "compute_angular_cosine_similarity",
    "compute_committee_moments",
    "compute_conservative_forces",
    "cosine_cutoff_envelope",
    "get_available_vram_mb",
    "huber_force_loss",
    "huber_scalar_loss",
    "quintic_c2_envelope",
)


def __getattr__(name: str):
    return unavailable_attribute(__name__, name, _UNAVAILABLE)


__all__ = [
    "ANI2xCutoffConfig",
    "CommitteeEnsembleConfig",
    "ExactKernelRidgeEstimator",
    "ForceMatchingLossConfig",
    "KrrRegularizationConfig",
]
