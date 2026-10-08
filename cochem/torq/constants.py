"""CODATA 2022 Physical Constants and Unit Conversions for CoChem-TORQ."""

from __future__ import annotations

from cochem_base.core import cochem_constants as _constants

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

# Energy Conversions [M]
HARTREE_TO_EV: float = _constants.HARTREE_TO_EV
EV_TO_JOULE: float = _constants.HARTREE_TO_JOULE / HARTREE_TO_EV

# Length Conversions [M]
BOHR_TO_ANGSTROM: float = _constants.BOHR_TO_ANGSTROM
ANGSTROM_TO_METER: float = _constants.ANGSTROM_TO_METER

# Force Conversions [D], [M]
HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM: float = (
    HARTREE_TO_EV / BOHR_TO_ANGSTROM
)  # ~51.4220674763 eV/Angstrom [D]
EV_PER_ANGSTROM_TO_NEWTON: float = EV_TO_JOULE / ANGSTROM_TO_METER

# Stress and Pressure Conversions [M], [D]
EV_PER_ANGSTROM3_TO_GPA: float = EV_TO_JOULE / ANGSTROM_TO_METER**3 / 1e9

# Multipole Moment Conversions [M]
# The Debye is exactly 10^-21/c coulomb metre; avoid a rounded second table.
DEBYE_PER_EAA: float = EV_TO_JOULE * ANGSTROM_TO_METER / (1e-21 / _constants.SPEED_OF_LIGHT_M_S)
