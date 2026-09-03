"""Centralized Physical Constants & Dynamic Mendeleev Registry.
Strictly adheres to Mendeleev Mandate and CODATA 2018 Dynamic Lookup.
Zero hardcoding of atomic masses or periodic tables.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any, Dict, Optional

import scipy.constants
from mendeleev import element


@dataclass(frozen=True)
class PhysicalConstant:
    """Immutable representation of a physical constant with CODATA provenance."""

    name: str
    symbol: str
    value: float
    uncertainty: float
    unit: str
    provenance: str
    source: str = "CODATA 2018 / scipy.constants"


@dataclass(frozen=True)
class ElementProperties:
    """Immutable elemental structure dynamically populated from Mendeleev database."""

    atomic_number: int
    symbol: str
    name: str
    atomic_weight: float
    covalent_radius_pyykko: Optional[float]
    vdw_radius_bondi: Optional[float]
    provenance: str = "[M]"


class PhysicalConstantsRegistry:
    """Authoritative scientific registry for physical constants and elemental data."""

    STANDARD_TEMPERATURE_K: float = 298.15
    STANDARD_PRESSURE_PA: float = 101325.0

    _CONVENTIONAL_SYMBOLS: Dict[str, str] = {
        "Planck constant": "h",
        "Boltzmann constant": "k_B",
        "speed of light in vacuum": "c",
        "Avogadro constant": "N_A",
        "elementary charge": "e",
        "molar gas constant": "R",
        "atomic mass constant": "u",
    }

    @staticmethod
    @functools.lru_cache(maxsize=256)
    def get_constant(name: str) -> PhysicalConstant:
        """Query physical constant dynamically from scipy CODATA 2018 database."""
        if name not in scipy.constants.physical_constants:
            raise KeyError(f"Constant '{name}' not found in CODATA 2018 registry.")

        val, unit, unc = scipy.constants.physical_constants[name]
        provenance = "[E]" if unc == 0.0 else "[D]"
        symbol = PhysicalConstantsRegistry._CONVENTIONAL_SYMBOLS.get(name, name)

        return PhysicalConstant(
            name=name,
            symbol=symbol,
            value=float(val),
            uncertainty=float(unc),
            unit=str(unit),
            provenance=provenance,
            source="CODATA 2018 / scipy.constants",
        )

    @staticmethod
    @functools.lru_cache(maxsize=128)
    def get_element(symbol_or_z: Any) -> ElementProperties:
        """Dynamically retrieve element properties from Mendeleev library."""
        elem = element(symbol_or_z)

        covalent_val = getattr(elem, "covalent_radius_pyykko", None)
        vdw_val = getattr(elem, "vdw_radius_bondi", None)

        covalent_radius: Optional[float] = (
            float(covalent_val) if covalent_val is not None else None
        )
        vdw_radius: Optional[float] = (
            float(vdw_val) if vdw_val is not None else None
        )

        return ElementProperties(
            atomic_number=int(elem.atomic_number),
            symbol=str(elem.symbol),
            name=str(elem.name),
            atomic_weight=float(elem.mass),
            covalent_radius_pyykko=covalent_radius,
            vdw_radius_bondi=vdw_radius,
            provenance="[M]",
        )

    @staticmethod
    @functools.lru_cache(maxsize=128)
    def get_element_mass(symbol: str) -> float:
        """Dynamically retrieve IUPAC standard atomic mass from Mendeleev."""
        elem = element(symbol)
        return float(elem.mass)
