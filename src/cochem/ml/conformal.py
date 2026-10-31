"""BASE compatibility exports; unsupported TORQ science stays unavailable.

No sibling checkout or cross-environment Python objects are imported.
"""

from __future__ import annotations

from cochem_base.exceptions import ConformalCalibrationError
from cochem_base.ml._legacy_api import unavailable_attribute
from cochem_base.schemas import ConformalCalibrationConfig

_UNAVAILABLE = (
    "CalibrationSample",
    "ConformalInterval",
    "ConformalPredictor",
    "ConformalPredictorConfig",
)


def __getattr__(name: str):
    return unavailable_attribute(__name__, name, _UNAVAILABLE)


__all__ = ["ConformalCalibrationConfig", "ConformalCalibrationError"]
