"""Lazy supported BASE compatibility exports, without sibling TORQ imports."""

from __future__ import annotations

from importlib import import_module

from cochem_base.ml._legacy_api import unavailable_attribute

_MODULES = {
    "active_learning": "cochem_base.ml.active_learning",
    "baselines": "cochem_base.ml.baselines",
    "conformal": "cochem_base.ml.conformal",
    "krr": "cochem_base.ml.krr",
}
_EXPORTS = {
    "ActiveLearningBatchConfig": ("cochem_base.ml", "ActiveLearningBatchConfig"),
    "ActiveLearningConfig": ("cochem_base.ml", "ActiveLearningConfig"),
    "ActiveLearningEngine": ("cochem_base.ml", "ActiveLearningEngine"),
    "ActiveLearningManager": ("cochem_base.ml", "ActiveLearningManager"),
    "ActiveLearningSelectionResult": ("cochem_base.ml", "ActiveLearningSelectionResult"),
    "ConformalCalibrationConfig": ("cochem_base.ml", "ConformalCalibrationConfig"),
    "ConformalCalibrationError": ("cochem_base.ml", "ConformalCalibrationError"),
    "DeltaMLDispersionConfig": ("cochem_base.ml", "DeltaMLDispersionConfig"),
    "ExactKernelRidgeEstimator": ("cochem_base.ml", "ExactKernelRidgeEstimator"),
    "KernelRidgeModel": ("cochem_base.ml", "KernelRidgeModel"),
    "KernelType": ("cochem_base.ml", "KernelType"),
    "KrrRegularizationConfig": ("cochem_base.ml", "KrrRegularizationConfig"),
    "sequential_repulsion_selector": ("cochem_base.ml", "sequential_repulsion_selector"),
}
_UNAVAILABLE = (
    "BaselinePhysicsEngine",
    "CalibrationSample",
    "ConformalInterval",
    "ConformalPredictor",
    "ConformalPredictorConfig",
    "DispersionD3Config",
    "DispersionD3Layer",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    "compute_coordination_numbers",
)


def __getattr__(name: str):
    if name in _MODULES:
        value = import_module(_MODULES[name])
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
    "ActiveLearningBatchConfig",
    "ActiveLearningConfig",
    "ActiveLearningEngine",
    "ActiveLearningManager",
    "ActiveLearningSelectionResult",
    "ConformalCalibrationConfig",
    "ConformalCalibrationError",
    "DeltaMLDispersionConfig",
    "ExactKernelRidgeEstimator",
    "KernelRidgeModel",
    "KernelType",
    "KrrRegularizationConfig",
    "sequential_repulsion_selector",
]
