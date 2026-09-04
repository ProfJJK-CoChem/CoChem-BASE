"""Authoritative Physical Constants Bridge & Central Registry Integration.
Strictly adheres to Method Matrix v4, CODATA 2022, and Zero-Mock Protocol.
Exposes authoritative rotational constant factor and re-exports PhysicalConstantsRegistry.
"""

from __future__ import annotations

from cochem.core.cochem_constants import (
    C_ROT_MHZ_U_ANG2,
    ElementProperties,
    PhysicalConstant,
    PhysicalConstantsRegistry,
    element,
)

__all__ = [
    "C_ROT_MHZ_U_ANG2",
    "PhysicalConstant",
    "ElementProperties",
    "PhysicalConstantsRegistry",
    "element",
]
