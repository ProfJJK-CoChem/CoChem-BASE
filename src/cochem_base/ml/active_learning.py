"""Active Learning and Batch Diversity Subsystem (Suggestion #51, #138 / Method Matrix v4 §10.8 [M])."""

from __future__ import annotations

from typing import Optional

import numpy as np

from cochem_base.core_engine.cochem_core_auto_pes import (
    ActiveLearningConfig,
    ActiveLearningEngine,
    ActiveLearningSelectionResult,
    GeometryFeaturizer,
    sequential_repulsion_selector,
)
from cochem_base.schemas import ActiveLearningBatchConfig


class ActiveLearningManager(ActiveLearningEngine):
    """Unified Active Learning Manager coordinating batch acquisition, spatial repulsion, and pool triage. [M]"""

    def __init__(
        self,
        featurizer: Optional[GeometryFeaturizer] = None,
        config: Optional[ActiveLearningConfig] = None,
        batch_config: Optional[ActiveLearningBatchConfig] = None,
    ) -> None:
        super().__init__(
            featurizer=featurizer,
            config=config,
            batch_config=batch_config,
        )
        self.provenance = "[M]"

    def coordinate_batch_acquisition(
        self,
        candidate_pool: np.ndarray,
        uncertainties: np.ndarray,
        batch_config: Optional[ActiveLearningBatchConfig] = None,
    ) -> list[int]:
        """Coordinate batch point acquisition with spatial repulsion and uncertainty balancing. [M]"""
        return self.select_batch(
            candidate_pool=candidate_pool,
            uncertainties=uncertainties,
            batch_config=batch_config,
        )


__all__ = [
    "ActiveLearningBatchConfig",
    "ActiveLearningConfig",
    "ActiveLearningEngine",
    "ActiveLearningManager",
    "ActiveLearningSelectionResult",
    "sequential_repulsion_selector",
]
