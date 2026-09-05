"""Semi-empirical Hamiltonians, Empirical Baselines & Dispersion Layers (Suggestion #60, #138, #139 / Method Matrix v4 §9A.5 [M], [D])."""

from __future__ import annotations

from Libraries.cochem_torq_delta_ml import (
    BaselinePhysicsEngine,
    DeltaMLEngine,
    EMTBaselineEngine,
    GFN2xTBEngine,
    LennardJonesBaselineEngine,
    PM6Engine,
    UnitHarmonizer,
)
from Libraries.cochem_torq_dispersion_d3 import (
    DispersionD3Layer,
    compute_coordination_numbers,
)
from Libraries.cochem_torq_inference_schemas import DispersionD3Config

from cochem_base.schemas import DeltaMLDispersionConfig

__all__ = [
    "BaselinePhysicsEngine",
    "DeltaMLDispersionConfig",
    "DeltaMLEngine",
    "DispersionD3Config",
    "DispersionD3Layer",
    "EMTBaselineEngine",
    "GFN2xTBEngine",
    "LennardJonesBaselineEngine",
    "PM6Engine",
    "UnitHarmonizer",
    "compute_coordination_numbers",
]
