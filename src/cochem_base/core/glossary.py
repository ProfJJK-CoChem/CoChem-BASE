"""Authoritative CODATA 2018 / 2022 IEEE-754 FP64 Physical Conversion Constants & Method Matrix Glossary.

Provides single repository source of truth for energy, coordinate, and rotational inertia conversions,
as well as canonical composite calculation fidelity tiers defined in Method Matrix v4 (§9A, Table 3).
Strictly adheres to Method Matrix §4.4, §5, §8B, §9A and authoritative CODATA recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class CalculationFidelity(str, Enum):
    """Authoritative Method Matrix v4 calculation fidelity tiers and canonical composite recipes [D]."""

    # Low / Semiempirical Tiers
    XTB1 = "XTB1"
    XTB2 = "XTB2"
    PM6 = "PM6"
    AM1 = "AM1"

    # Single Reference / Mean Field
    R_HF = "R_HF"
    U_HF = "U_HF"
    R_DFT = "R_DFT"
    U_DFT = "U_DFT"
    RO_DFT = "RO_DFT"

    # Correlated Wavefunction
    MP2 = "MP2"
    DLPNO_CCSD_T = "DLPNO_CCSD_T"
    CCSD_T = "CCSD_T"
    CCSD_T_F12 = "CCSD_T_F12"
    CASSCF = "CASSCF"
    NEVPT2 = "NEVPT2"

    # Method Matrix v4 Canonical Composite Tiers (Table 3 & §9A)
    JUNCHS = "junChS"
    JUNCHS_F12 = "junChS-F12"
    CHS = "ChS"
    CHS_F12 = "ChS-F12"
    T3_10S = "T3-10s"
    T3_1MIN = "T3-1min"
    T3_30MIN = "T3-30min"
    T3_3H = "T3-3h"
    T3_12H = "T3-12h"
    T4_1D = "T4-1d"
    R2 = "R2"

    # Custom / Open QCSchema Specification
    CUSTOM_COMPOSITE = "CUSTOM_COMPOSITE"


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
    "CalculationFidelity",
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
