"""CODATA 2022 Physical Constants and Unit Conversions for CoChem-TORQ."""

from __future__ import annotations

# Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical

# Energy Conversions [M]
HARTREE_TO_EV: float = 27.211386245988  # [M] Exact CODATA 2022 Hartree energy in eV
EV_TO_JOULE: float = 1.602176634e-19  # [M] CODATA 2022 exact elementary charge / Joule definition

# Length Conversions [M]
BOHR_TO_ANGSTROM: float = 0.529177210903  # [M] CODATA 2022 Bohr radius in Angstroms
ANGSTROM_TO_METER: float = 1.0e-10  # [M] Exact Angstrom definition in meters

# Force Conversions [D], [M]
HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM: float = (
    HARTREE_TO_EV / BOHR_TO_ANGSTROM
)  # ~51.4220674763 eV/Angstrom [D]
EV_PER_ANGSTROM_TO_NEWTON: float = 1.602176634e-9  # [M] 1 eV/Angstrom in Newtons

# Stress and Pressure Conversions [M], [D]
EV_PER_ANGSTROM3_TO_GPA: float = 160.21766208  # [M] 1 eV/Angstrom^3 in Gigapascals

# Multipole Moment Conversions [M]
DEBYE_PER_EAA: float = 4.80320427  # [M] Conversion factor from e*Angstrom to Debye (1 e*Angstrom = 4.80320427 Debye)
