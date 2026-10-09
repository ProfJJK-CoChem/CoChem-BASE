"""Vectorized Committee Ensemble Models (Suggestion #61 / Method Matrix v4 §8A.2 [M], [D])."""

from __future__ import annotations

from cochem_base.numerics.committee_ensemble import (
    CommitteeEnsemble,
    CommitteePrediction,
    compute_committee_moments,
    get_available_vram_mb,
)
from cochem_base.schemas import CommitteeEnsembleConfig

__all__ = [
    "CommitteeEnsemble",
    "CommitteeEnsembleConfig",
    "CommitteePrediction",
    "compute_committee_moments",
    "get_available_vram_mb",
]
