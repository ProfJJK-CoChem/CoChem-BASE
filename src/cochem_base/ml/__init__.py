"""Shared machine-learning primitives with optional TORQ adapters loaded on demand.

Local kernel regression and active learning remain usable in the BASE micro-silo.
Accessing a TORQ-backed adapter still requires its real implementation.
"""
from __future__ import annotations

from importlib import import_module

_MODULES = {"active_learning", "baselines", "conformal", "krr"}
_EXPORTS = {
    'ActiveLearningBatchConfig': ('cochem_base.ml.active_learning', 'ActiveLearningBatchConfig'),
    'ActiveLearningConfig': ('cochem_base.ml.active_learning', 'ActiveLearningConfig'),
    'ActiveLearningEngine': ('cochem_base.ml.active_learning', 'ActiveLearningEngine'),
    'ActiveLearningManager': ('cochem_base.ml.active_learning', 'ActiveLearningManager'),
    'ActiveLearningSelectionResult': ('cochem_base.ml.active_learning', 'ActiveLearningSelectionResult'),
    'sequential_repulsion_selector': ('cochem_base.ml.active_learning', 'sequential_repulsion_selector'),
    'BaselinePhysicsEngine': ('cochem_base.ml.baselines', 'BaselinePhysicsEngine'),
    'DeltaMLDispersionConfig': ('cochem_base.ml.baselines', 'DeltaMLDispersionConfig'),
    'DispersionD3Config': ('cochem_base.ml.baselines', 'DispersionD3Config'),
    'DispersionD3Layer': ('cochem_base.ml.baselines', 'DispersionD3Layer'),
    'EMTBaselineEngine': ('cochem_base.ml.baselines', 'EMTBaselineEngine'),
    'GFN2xTBEngine': ('cochem_base.ml.baselines', 'GFN2xTBEngine'),
    'LennardJonesBaselineEngine': ('cochem_base.ml.baselines', 'LennardJonesBaselineEngine'),
    'PM6Engine': ('cochem_base.ml.baselines', 'PM6Engine'),
    'UnitHarmonizer': ('cochem_base.ml.baselines', 'UnitHarmonizer'),
    'compute_coordination_numbers': ('cochem_base.ml.baselines', 'compute_coordination_numbers'),
    'CalibrationSample': ('cochem_base.ml.conformal', 'CalibrationSample'),
    'ConformalCalibrationConfig': ('cochem_base.ml.conformal', 'ConformalCalibrationConfig'),
    'ConformalCalibrationError': ('cochem_base.ml.conformal', 'ConformalCalibrationError'),
    'ConformalInterval': ('cochem_base.ml.conformal', 'ConformalInterval'),
    'ConformalPredictor': ('cochem_base.ml.conformal', 'ConformalPredictor'),
    'ConformalPredictorConfig': ('cochem_base.ml.conformal', 'ConformalPredictorConfig'),
    'ExactKernelRidgeEstimator': ('cochem_base.ml.krr', 'ExactKernelRidgeEstimator'),
    'KernelRidgeModel': ('cochem_base.ml.krr', 'KernelRidgeModel'),
    'KernelType': ('cochem_base.ml.krr', 'KernelType'),
    'KrrRegularizationConfig': ('cochem_base.ml.krr', 'KrrRegularizationConfig'),
}


def __getattr__(name: str):
    if name in _MODULES:
        value = import_module(f"{__name__}.{name}")
    elif name in _EXPORTS:
        module_name, attribute = _EXPORTS[name]
        value = getattr(import_module(module_name), attribute)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))


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
