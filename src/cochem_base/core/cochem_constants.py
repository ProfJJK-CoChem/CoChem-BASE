"""Authoritative Physical Constants Bridge & Central Registry Integration.
Strictly adheres to Method Matrix v4, CODATA 2022, and Zero-Mock Protocol.
Exposes authoritative rotational constant factor and re-exports PhysicalConstantsRegistry.
"""

from __future__ import annotations

from cochem.core.cochem_constants import (
    ANGSTROM_TO_BOHR,
    ANGSTROM_TO_METER,
    ATOMIC_MASS_UNIT_KG,
    AVOGADRO_CONSTANT,
    BOHR_TO_ANGSTROM,
    BOHR_TO_METER,
    BOLTZMANN_CONSTANT_J_K,
    C_ROT_MHZ_U_ANG2,
    HARTREE_TO_CM_INV,
    HARTREE_TO_EV,
    HARTREE_TO_JOULE,
    HARTREE_TO_KCAL_MOL,
    KCAL_MOL_TO_HARTREE,
    PLANCK_CONSTANT_J_S,
    SPEED_OF_LIGHT_CM_S,
    SPEED_OF_LIGHT_M_S,
    ElementProperties,
    PhysicalConstant,
    PhysicalConstantsRegistry,
    element,
)

__all__ = [
    "ANGSTROM_TO_BOHR", "ANGSTROM_TO_METER", "ATOMIC_MASS_UNIT_KG",
    "AVOGADRO_CONSTANT", "BOHR_TO_ANGSTROM", "BOHR_TO_METER",
    "BOLTZMANN_CONSTANT_J_K", "HARTREE_TO_CM_INV", "HARTREE_TO_EV",
    "HARTREE_TO_JOULE", "HARTREE_TO_KCAL_MOL", "KCAL_MOL_TO_HARTREE",
    "PLANCK_CONSTANT_J_S", "SPEED_OF_LIGHT_CM_S", "SPEED_OF_LIGHT_M_S",
    "C_ROT_MHZ_U_ANG2",
    "PhysicalConstant",
    "ElementProperties",
    "PhysicalConstantsRegistry",
    "element",
]
