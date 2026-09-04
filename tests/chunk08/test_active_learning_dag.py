# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 9 (Suggestion #79):
Active Learning & Delta-ML Execution DAG Integration.
Verifies that points with sigma_E <= 10.0 meV use Delta-ML predictions while
points with sigma_E > 10.0 meV query high-level CCSD(T) anchor jobs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import numpy as np
import pytest

from Libraries.cochem_torq_active_learning import (
    ActiveLearningOrchestrator,
    ActiveLearner,
)
from Libraries.cochem_torq_delta_ml import (
    DeltaMLEngine,
    DeltaMLCorrector,
)


def test_active_learning_uncertainty_gating() -> None:
    """Verify G5 epistemic uncertainty thresholding:

    - sigma_E <= 10.0 meV -> Delta-ML surrogate prediction
    - sigma_E > 10.0 meV -> trigger high-level anchor calculation
    """
    threshold_sigma_mev = 10.0

    # Low uncertainty candidate (sigma_E = 4.2 meV <= 10.0 meV)
    low_unc_sigma_mev = 4.2
    decision_low = ActiveLearner.evaluate_candidate_gating(
        sigma_e_mev=low_unc_sigma_mev,
        threshold_sigma_mev=threshold_sigma_mev,
    )
    assert decision_low["action"] == "SURROGATE_PREDICT"
    assert decision_low["query_anchor"] is False

    # High uncertainty candidate (sigma_E = 14.8 meV > 10.0 meV)
    high_unc_sigma_mev = 14.8
    decision_high = ActiveLearner.evaluate_candidate_gating(
        sigma_e_mev=high_unc_sigma_mev,
        threshold_sigma_mev=threshold_sigma_mev,
    )
    assert decision_high["action"] == "QUERY_ANCHOR"
    assert decision_high["query_anchor"] is True
