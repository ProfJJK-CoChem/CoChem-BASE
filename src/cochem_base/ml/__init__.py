"""Supported BASE ML primitives and explicit unavailable legacy boundaries.

Local KRR, neural PES, active learning and data-only configuration retain their
proper BASE implementations. TORQ scientific Python objects are not imported.
"""

from __future__ import annotations

from importlib import import_module

from ._legacy_api import unavailable_attribute

_MODULES = {"active_learning", "baselines", "conformal", "krr"}
_EXPORTS = {
    "ActiveLearningBatchConfig": ("cochem_base.ml.active_learning", "ActiveLearningBatchConfig"),
    "ActiveLearningConfig": ("cochem_base.ml.active_learning", "ActiveLearningConfig"),
    "ActiveLearningEngine": ("cochem_base.ml.active_learning", "ActiveLearningEngine"),
    "ActiveLearningManager": ("cochem_base.ml.active_learning", "ActiveLearningManager"),
    "ActiveLearningSelectionResult": (
        "cochem_base.ml.active_learning",
        "ActiveLearningSelectionResult",
    ),
    "sequential_repulsion_selector": (
        "cochem_base.ml.active_learning",
        "sequential_repulsion_selector",
    ),
    "DeltaMLDispersionConfig": ("cochem_base.ml.baselines", "DeltaMLDispersionConfig"),
    "ConformalCalibrationConfig": ("cochem_base.ml.conformal", "ConformalCalibrationConfig"),
    "ConformalCalibrationError": ("cochem_base.ml.conformal", "ConformalCalibrationError"),
    "ExactKernelRidgeEstimator": ("cochem_base.ml.krr", "ExactKernelRidgeEstimator"),
    "KernelRidgeModel": ("cochem_base.ml.krr", "KernelRidgeModel"),
    "KernelType": ("cochem_base.ml.krr", "KernelType"),
    "KrrRegularizationConfig": ("cochem_base.ml.krr", "KrrRegularizationConfig"),
}
_UNAVAILABLE = (
    "BaselinePhysicsEngine",
    "DispersionD3Config",
    "DispersionD3Layer",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    "compute_coordination_numbers",
    "CalibrationSample",
    "ConformalInterval",
    "ConformalPredictor",
    "ConformalPredictorConfig",
)


def __getattr__(name: str):
    if name in _MODULES:
        value = import_module(f"{__name__}.{name}")
    elif name in _EXPORTS:
        module_name, attribute = _EXPORTS[name]
        value = getattr(import_module(module_name), attribute)
    else:
        return unavailable_attribute(__name__, name, _UNAVAILABLE)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "active_learning",
    "baselines",
    "conformal",
    "krr",
    "ConformalCalibrationConfig",
    "ConformalCalibrationError",
    "ExactKernelRidgeEstimator",
    "KernelRidgeModel",
    "KernelType",
    "KrrRegularizationConfig",
    "ActiveLearningBatchConfig",
    "ActiveLearningConfig",
    "ActiveLearningEngine",
    "ActiveLearningManager",
    "ActiveLearningSelectionResult",
    "sequential_repulsion_selector",
    "DeltaMLDispersionConfig",
]
