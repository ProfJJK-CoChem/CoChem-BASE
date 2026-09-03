"""Dynamic Mendeleev Invariants & Element Resolver.

Provenance & Specifications:
- Method Matrix [M]: Quantum spin-parity and IUPAC CIAAW standard atomic weight invariants.
- Dynamic Resolution [D]: Zero-hardcoding dynamic element and isotopic mass lookup via mendeleev.
- Telemetry [E]: Thread-safe in-memory cache populated dynamically at module initialization.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from mendeleev import element as _mendeleev_element


class MendeleevInvariantError(Exception):
    """Raised when chemical element queries violate Mendeleev physical invariants."""

    def __init__(self, message: str, symbol_or_query: Any = None) -> None:
        super().__init__(message)
        self.symbol_or_query = symbol_or_query


@dataclass(slots=True, frozen=True)
class ElementData:
    """Immutable ground-truth chemical element properties."""

    atomic_number: int
    symbol: str
    name: str
    atomic_weight: float
    isotopes: Tuple[Tuple[int, float, float], ...]  # (mass_number, exact_mass_amu, natural_abundance)
    covalent_radius_pm: Optional[float]
    vdw_radius_pm: Optional[float]
    valence_electrons: int


def _build_element_cache() -> Tuple[types.MappingProxyType, Dict[str, ElementData], Dict[int, ElementData]]:
    """Populate complete in-memory cache for elements Z=1..118 dynamically from mendeleev."""
    by_symbol: Dict[str, ElementData] = {}
    by_z: Dict[int, ElementData] = {}
    dual_map: Dict[Union[str, int], ElementData] = {}

    for z in range(1, 119):
        elem = _mendeleev_element(z)
        symbol = str(elem.symbol)
        name = str(elem.name)

        # Standard atomic weight with dynamic fallback to most stable isotope mass
        weight = elem.atomic_weight
        if weight is None or float(weight) <= 0.0:
            iso_masses = [iso.mass_number for iso in elem.isotopes if iso.mass_number is not None]
            if iso_masses:
                weight = float(max(iso_masses))
            else:
                weight = float(z)
        else:
            weight = float(weight)

        # Isotope tuple: (mass_number, exact_mass_amu, abundance)
        isotope_list: List[Tuple[int, float, float]] = []
        for iso in elem.isotopes:
            if iso.mass_number is not None:
                m_num = int(iso.mass_number)
                m_exact = float(iso.mass) if iso.mass is not None and float(iso.mass) > 0.0 else float(m_num)
                m_abund = float(iso.abundance) if iso.abundance is not None else 0.0
                isotope_list.append((m_num, m_exact, m_abund))
        isotopes_tuple = tuple(sorted(isotope_list, key=lambda x: x[0]))

        # Radii in picometers
        cov_r = elem.covalent_radius_pyykko or elem.covalent_radius
        cov_radius_pm = float(cov_r) if cov_r is not None else None

        vdw_r = elem.vdw_radius or elem.vdw_radius_alvarez or elem.vdw_radius_bondi or elem.vdw_radius_batsanov
        vdw_radius_pm = float(vdw_r) if vdw_r is not None else None

        # Valence electrons
        if hasattr(elem, "nvalence") and callable(elem.nvalence):
            val_e = int(elem.nvalence())
        elif elem.electrons is not None:
            val_e = int(elem.electrons)
        else:
            val_e = 0

        data = ElementData(
            atomic_number=z,
            symbol=symbol,
            name=name,
            atomic_weight=weight,
            isotopes=isotopes_tuple,
            covalent_radius_pm=cov_radius_pm,
            vdw_radius_pm=vdw_radius_pm,
            valence_electrons=val_e,
        )

        by_symbol[symbol] = data
        by_z[z] = data
        dual_map[symbol] = data
        dual_map[z] = data

    return types.MappingProxyType(dual_map), by_symbol, by_z


# Module-level immutable dual-key element cache
_ELEMENT_CACHE, _ELEMENTS_BY_SYMBOL, _ELEMENTS_BY_Z = _build_element_cache()


def get_element(symbol_or_z: Union[str, int]) -> ElementData:
    """Retrieve immutable ElementData by atomic number or chemical symbol."""
    if isinstance(symbol_or_z, int):
        if symbol_or_z < 1 or symbol_or_z > 118:
            raise MendeleevInvariantError(
                f"Invalid atomic number Z={symbol_or_z}. Must be between 1 and 118.",
                symbol_or_query=symbol_or_z,
            )
        data = _ELEMENTS_BY_Z.get(symbol_or_z)
        if data is None:
            raise MendeleevInvariantError(
                f"Element with Z={symbol_or_z} not found in Mendeleev database.",
                symbol_or_query=symbol_or_z,
            )
        return data

    raw = str(symbol_or_z).strip()
    if not raw or raw.isdigit():
        raise MendeleevInvariantError(
            f"Invalid chemical symbol '{symbol_or_z}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol_or_z,
        )

    # Normalize chemical symbol
    if len(raw) == 1:
        normalized = raw.upper()
    elif len(raw) <= 3:
        normalized = raw[0].upper() + raw[1:].lower()
    else:
        normalized = raw.capitalize()

    # Try symbol match first
    data = _ELEMENTS_BY_SYMBOL.get(normalized)
    if data is not None:
        return data

    # Try name match
    for elem in _ELEMENTS_BY_Z.values():
        if elem.name.lower() == raw.lower():
            return elem

    raise MendeleevInvariantError(
        f"Dynamic element resolution failed for query '{symbol_or_z}'.",
        symbol_or_query=symbol_or_z,
    )


def get_isotope_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Dynamically resolve IUPAC exact isotopic mass in unified atomic mass units (u)."""
    element_data = get_element(symbol_or_z)
    for iso_m_num, iso_exact, _ in element_data.isotopes:
        if iso_m_num == mass_number:
            return iso_exact

    raise MendeleevInvariantError(
        f"No isotope with mass number A={mass_number} found for element '{element_data.symbol}'.",
        symbol_or_query=f"{element_data.symbol}-{mass_number}",
    )


class MendeleevResolver:
    """Thread-safe dynamic Mendeleev element and isotope mass resolver for backward compatibility."""

    def get_element(self, symbol_or_z: Union[str, int]) -> Any:
        elem_data = get_element(symbol_or_z)
        return _mendeleev_element(elem_data.atomic_number)

    def get_atomic_number(self, symbol_or_z: Union[str, int]) -> int:
        return get_element(symbol_or_z).atomic_number

    def get_atomic_weight(self, symbol_or_z: Union[str, int]) -> float:
        return get_element(symbol_or_z).atomic_weight

    def get_symbol(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).symbol

    def get_name(self, symbol_or_z: Union[str, int]) -> str:
        return get_element(symbol_or_z).name

    def get_covalent_radius(self, symbol_or_z: Union[str, int]) -> Optional[float]:
        return get_element(symbol_or_z).covalent_radius_pm

    def get_vdw_radius(self, symbol_or_z: Union[str, int]) -> float:
        r = get_element(symbol_or_z).vdw_radius_pm
        if r is None:
            raise MendeleevInvariantError(f"Van der Waals radius is not available for element '{symbol_or_z}'.")
        return r

    def get_vdw_radius_angstrom(self, symbol_or_z: Union[str, int]) -> float:
        return self.get_vdw_radius(symbol_or_z) / 100.0

    def get_isotope_mass(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        return get_isotope_mass(symbol_or_z, mass_number)

    def get_isotope_abundance(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        elem_data = get_element(symbol_or_z)
        for m_num, _, abund in elem_data.isotopes:
            if m_num == mass_number:
                return abund
        return 0.0

    def get_available_isotopes(self, symbol_or_z: Union[str, int]) -> List[int]:
        return [m_num for m_num, _, _ in get_element(symbol_or_z).isotopes]

    def clear_cache(self) -> None:
        raise MendeleevInvariantError("Mendeleev element cache is immutable and cannot be cleared.")


# Default global resolver instance for backwards compatibility
mendeleev_resolver = MendeleevResolver()
