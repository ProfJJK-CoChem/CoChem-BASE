"""
CoChem-BASE Proxy for cochem_torq_slicer
"""

from cochem_torq_slicer import (
    HARTREE_TO_CM1,
    HARTREE_TO_KCAL_MOL,
    KCAL_MOL_TO_CM1,
    fit_continuous_splines,
    wkb_tunneling_estimator,
)

__all__ = [
    "HARTREE_TO_KCAL_MOL",
    "HARTREE_TO_CM1",
    "KCAL_MOL_TO_CM1",
    "fit_continuous_splines",
    "wkb_tunneling_estimator",
]
