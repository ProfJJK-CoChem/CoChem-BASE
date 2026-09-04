"""Authoritative CODATA 2018 / 2022 IEEE-754 FP64 Physical Conversion Constants.

Provides single repository source of truth for energy, coordinate, and rotational inertia conversions.
Strictly adheres to Method Matrix §4.4, §5, §8B and authoritative CODATA recommendations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import scipy.constants


@dataclass(frozen=True)
class _UnitConversionConstants:
    """Authoritative physical constants at full IEEE-754 double precision."""

    HARTREE_TO_EV: float = 27.211386245981
    HARTREE_TO_JOULE: float = 4.359744722206e-18
    HARTREE_TO_KCAL_MOL: float = 627.5094740631
    KCAL_MOL_TO_HARTREE: float = 1.0 / 627.5094740631
    HARTREE_TO_CM_INV: float = 219474.63136320
    BOHR_TO_ANGSTROM: float = 0.529177210903
    ANGSTROM_TO_BOHR: float = 1.0 / 0.529177210903
    AMU_TO_KG: float = 1.66053906660e-27
    PLANCK_CONSTANT: float = 6.62607015e-34
    SPEED_OF_LIGHT_CM_S: float = 29979245800.0
    ROTATIONAL_INERTIA_CONVERSION: float = 505379.0084350172


UnitConversionConstants: Final[_UnitConversionConstants] = _UnitConversionConstants()

# Top-level module exports for ergonomic direct imports
HARTREE_TO_EV: Final[float] = UnitConversionConstants.HARTREE_TO_EV
HARTREE_TO_JOULE: Final[float] = UnitConversionConstants.HARTREE_TO_JOULE
HARTREE_TO_KCAL_MOL: Final[float] = UnitConversionConstants.HARTREE_TO_KCAL_MOL
KCAL_MOL_TO_HARTREE: Final[float] = UnitConversionConstants.KCAL_MOL_TO_HARTREE
HARTREE_TO_CM_INV: Final[float] = UnitConversionConstants.HARTREE_TO_CM_INV
BOHR_TO_ANGSTROM: Final[float] = UnitConversionConstants.BOHR_TO_ANGSTROM
ANGSTROM_TO_BOHR: Final[float] = UnitConversionConstants.ANGSTROM_TO_BOHR
AMU_TO_KG: Final[float] = UnitConversionConstants.AMU_TO_KG
PLANCK_CONSTANT: Final[float] = UnitConversionConstants.PLANCK_CONSTANT
SPEED_OF_LIGHT_CM_S: Final[float] = UnitConversionConstants.SPEED_OF_LIGHT_CM_S
ROTATIONAL_INERTIA_CONVERSION: Final[float] = UnitConversionConstants.ROTATIONAL_INERTIA_CONVERSION

__all__ = [
    "UnitConversionConstants",
    "HARTREE_TO_EV",
    "HARTREE_TO_JOULE",
    "HARTREE_TO_KCAL_MOL",
    "KCAL_MOL_TO_HARTREE",
    "HARTREE_TO_CM_INV",
    "BOHR_TO_ANGSTROM",
    "ANGSTROM_TO_BOHR",
    "AMU_TO_KG",
    "PLANCK_CONSTANT",
    "SPEED_OF_LIGHT_CM_S",
    "ROTATIONAL_INERTIA_CONVERSION",
]
