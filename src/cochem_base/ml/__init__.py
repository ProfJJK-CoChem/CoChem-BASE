"""CoChem Unified Machine Learning Package (cochem_base.ml).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Consolidated shared ML primitives across the ecosystem.
"""

from __future__ import annotations

from cochem_base.ml import active_learning, baselines, conformal, krr
from cochem_base.ml.active_learning import (
    ActiveLearningBatchConfig,
    ActiveLearningConfig,
    ActiveLearningEngine,
    ActiveLearningManager,
    ActiveLearningSelectionResult,
    sequential_repulsion_selector,
)
from cochem_base.ml.baselines import (
    BaselinePhysicsEngine,
    DeltaMLDispersionConfig,
    DispersionD3Config,
    DispersionD3Layer,
    EMTBaselineEngine,
    GFN2xTBEngine,
    LennardJonesBaselineEngine,
    PM6Engine,
    UnitHarmonizer,
    compute_coordination_numbers,
)
from cochem_base.ml.conformal import (
    CalibrationSample,
    ConformalCalibrationConfig,
    ConformalCalibrationError,
    ConformalInterval,
    ConformalPredictor,
    ConformalPredictorConfig,
)
from cochem_base.ml.krr import (
    ExactKernelRidgeEstimator,
    KernelRidgeModel,
    KernelType,
    KrrRegularizationConfig,
)

__all__ = [
    # Submodules
    "active_learning",
    "baselines",
    "conformal",
    "krr",
    # Conformal
    "CalibrationSample",
    "ConformalCalibrationConfig",
    "ConformalCalibrationError",
    "ConformalInterval",
    "ConformalPredictor",
    "ConformalPredictorConfig",
    # KRR
    "ExactKernelRidgeEstimator",
    "KernelRidgeModel",
    "KernelType",
    "KrrRegularizationConfig",
    # Active Learning
    "ActiveLearningBatchConfig",
    "ActiveLearningConfig",
    "ActiveLearningEngine",
    "ActiveLearningManager",
    "ActiveLearningSelectionResult",
    "sequential_repulsion_selector",
    # Baselines
    "BaselinePhysicsEngine",
    "DeltaMLDispersionConfig",
    "DispersionD3Config",
    "DispersionD3Layer",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    "compute_coordination_numbers",
]
