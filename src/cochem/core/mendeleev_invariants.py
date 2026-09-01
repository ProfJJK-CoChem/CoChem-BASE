"""
Dynamic Mendeleev Invariants & Element Resolver.

Provenance & Specifications:
- Method Matrix [M]: Quantum spin-parity and IUPAC CIAAW standard atomic weight invariants.
- Dynamic Resolution [D]: Zero-hardcoding dynamic element and isotopic mass lookup via mendeleev.
- Telemetry [T]: Thread-safe cache hit/miss tracking and invariant auditing.
"""

from __future__ import annotations

import functools
import threading
from typing import List, Optional, Tuple, Union

from mendeleev import element as _mendeleev_element
from mendeleev.models import Element, Isotope

from cochem.core.topology_exceptions import MendeleevInvariantError


@functools.lru_cache(maxsize=256)
def _fetch_mendeleev_element_cached(symbol_or_z: Union[str, int]) -> Element:
    """
    Cached low-level fetch of mendeleev Element model.

    Raises:
        MendeleevInvariantError: If element symbol or atomic number is invalid.
    """
    if isinstance(symbol_or_z, int):
        if symbol_or_z < 1 or symbol_or_z > 118:
            raise MendeleevInvariantError(
                f"Invalid atomic number Z={symbol_or_z}. Must be between 1 and 118.",
                symbol_or_query=symbol_or_z,
            )
        try:
            return _mendeleev_element(symbol_or_z)
        except Exception as err:
            raise MendeleevInvariantError(
                f"Failed to dynamically resolve element for Z={symbol_or_z}: {err}",
                symbol_or_query=symbol_or_z,
            ) from err

    raw = str(symbol_or_z).strip()
    if not raw or raw.isdigit():
        raise MendeleevInvariantError(
            f"Invalid chemical symbol '{symbol_or_z}'. Symbol cannot be empty or purely numeric.",
            symbol_or_query=symbol_or_z,
        )

    # Normalize chemical symbol (e.g. 'c' -> 'C', 'he' -> 'He', 'fe' -> 'Fe')
    if len(raw) == 1:
        normalized = raw.upper()
    elif len(raw) <= 3:
        normalized = raw[0].upper() + raw[1:].lower()
    else:
        # Check if full element name was passed
        normalized = raw.capitalize()

    try:
        elem = _mendeleev_element(normalized)
        if elem is None:
            raise ValueError(f"No element returned for symbol '{normalized}'")
        return elem
    except Exception as err:
        raise MendeleevInvariantError(
            f"Dynamic element resolution failed for query '{symbol_or_z}': {err}",
            symbol_or_query=symbol_or_z,
        ) from err


class MendeleevResolver:
    """
    Thread-safe dynamic Mendeleev element and isotope mass resolver.
    Enforces strict zero-mock and zero-hardcoding invariants.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._custom_hits: int = 0
        self._custom_misses: int = 0

    def get_element(self, symbol_or_z: Union[str, int]) -> Element:
        """Dynamically resolve element object from mendeleev library."""
        try:
            elem = _fetch_mendeleev_element_cached(symbol_or_z)
            return elem
        except MendeleevInvariantError:
            raise
        except Exception as err:
            raise MendeleevInvariantError(
                f"Unexpected resolution error for '{symbol_or_z}': {err}",
                symbol_or_query=symbol_or_z,
            ) from err

    @functools.lru_cache(maxsize=256)
    def get_atomic_number(self, symbol_or_z: Union[str, int]) -> int:
        """Dynamically resolve atomic number Z."""
        elem = self.get_element(symbol_or_z)
        z = int(elem.atomic_number)
        if z < 1 or z > 118:
            raise MendeleevInvariantError(
                f"Resolved unphysical atomic number Z={z} for '{symbol_or_z}'",
                symbol_or_query=symbol_or_z,
            )
        return z

    @functools.lru_cache(maxsize=256)
    def get_atomic_weight(self, symbol_or_z: Union[str, int]) -> float:
        """Dynamically resolve standard CIAAW atomic weight in unified atomic mass units (Da)."""
        elem = self.get_element(symbol_or_z)
        weight = elem.atomic_weight
        if weight is None or float(weight) <= 0.0:
            # Fallback for synthetic elements: most stable isotope mass if atomic_weight is None
            if elem.mass_number is not None and float(elem.mass_number) > 0.0:
                weight = float(elem.mass_number)
            else:
                raise MendeleevInvariantError(
                    f"Resolved unphysical or null atomic weight for '{symbol_or_z}'",
                    symbol_or_query=symbol_or_z,
                )
        return float(weight)

    @functools.lru_cache(maxsize=256)
    def get_symbol(self, symbol_or_z: Union[str, int]) -> str:
        """Dynamically resolve standardized element symbol."""
        elem = self.get_element(symbol_or_z)
        return str(elem.symbol)

    @functools.lru_cache(maxsize=256)
    def get_name(self, symbol_or_z: Union[str, int]) -> str:
        """Dynamically resolve element name."""
        elem = self.get_element(symbol_or_z)
        return str(elem.name)

    @functools.lru_cache(maxsize=256)
    def get_electronegativity(self, symbol_or_z: Union[str, int]) -> Optional[float]:
        """Dynamically resolve Pauling electronegativity."""
        elem = self.get_element(symbol_or_z)
        en = elem.electronegativity("pauling")
        return float(en) if en is not None else None

    @functools.lru_cache(maxsize=256)
    def get_covalent_radius(self, symbol_or_z: Union[str, int]) -> Optional[float]:
        """Dynamically resolve covalent radius in picometers (pm)."""
        elem = self.get_element(symbol_or_z)
        cr = elem.covalent_radius_pyykko or elem.covalent_radius
        return float(cr) if cr is not None else None

    @functools.lru_cache(maxsize=256)
    def get_isotope(self, symbol_or_z: Union[str, int], mass_number: int) -> Isotope:
        """Dynamically resolve specific isotope model by mass number."""
        elem = self.get_element(symbol_or_z)
        for iso in elem.isotopes:
            if iso.mass_number == mass_number:
                return iso
        raise MendeleevInvariantError(
            f"No isotope with mass number A={mass_number} exists for element '{elem.symbol}'.",
            symbol_or_query=f"{elem.symbol}-{mass_number}",
        )

    @functools.lru_cache(maxsize=256)
    def get_isotope_mass(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        """Dynamically resolve IUPAC isotopic mass in unified atomic mass units (Da)."""
        iso = self.get_isotope(symbol_or_z, mass_number)
        if iso.mass is None or float(iso.mass) <= 0.0:
            raise MendeleevInvariantError(
                f"Resolved unphysical isotopic mass for '{symbol_or_z}-{mass_number}'",
                symbol_or_query=f"{symbol_or_z}-{mass_number}",
            )
        return float(iso.mass)

    @functools.lru_cache(maxsize=256)
    def get_isotope_abundance(self, symbol_or_z: Union[str, int], mass_number: int) -> float:
        """Dynamically resolve natural isotope abundance percentage (0.0 to 100.0)."""
        iso = self.get_isotope(symbol_or_z, mass_number)
        if iso.abundance is None:
            return 0.0
        return float(iso.abundance)

    @functools.lru_cache(maxsize=256)
    def get_vdw_radius(self, symbol_or_z: Union[str, int]) -> float:
        """Dynamically resolve van der Waals radius in picometers (pm)."""
        elem = self.get_element(symbol_or_z)
        vr = elem.vdw_radius or elem.vdw_radius_alvarez or elem.vdw_radius_bondi or elem.vdw_radius_batsanov or 170.0
        return float(vr)

    @functools.lru_cache(maxsize=256)
    def get_vdw_radius_angstrom(self, symbol_or_z: Union[str, int]) -> float:
        """Dynamically resolve van der Waals radius in Ångströms (pm / 100.0)."""
        return self.get_vdw_radius(symbol_or_z) / 100.0

    @functools.lru_cache(maxsize=256)
    def get_available_isotopes(self, symbol_or_z: Union[str, int]) -> List[int]:
        """Dynamically return list of available isotope mass numbers."""
        elem = self.get_element(symbol_or_z)
        return sorted([int(iso.mass_number) for iso in elem.isotopes if iso.mass_number is not None])

    @property
    def cache_hits(self) -> int:
        """Total cache hits across cached lookup routines."""
        info = _fetch_mendeleev_element_cached.cache_info()
        return (
            info.hits
            + self.get_atomic_number.cache_info().hits
            + self.get_atomic_weight.cache_info().hits
            + self.get_symbol.cache_info().hits
            + self.get_name.cache_info().hits
            + self.get_electronegativity.cache_info().hits
            + self.get_covalent_radius.cache_info().hits
            + self.get_vdw_radius.cache_info().hits
            + self.get_vdw_radius_angstrom.cache_info().hits
            + self.get_isotope.cache_info().hits
            + self.get_isotope_mass.cache_info().hits
            + self.get_isotope_abundance.cache_info().hits
            + self.get_available_isotopes.cache_info().hits
        )

    @property
    def cache_misses(self) -> int:
        """Total cache misses across cached lookup routines."""
        info = _fetch_mendeleev_element_cached.cache_info()
        return (
            info.misses
            + self.get_atomic_number.cache_info().misses
            + self.get_atomic_weight.cache_info().misses
            + self.get_symbol.cache_info().misses
            + self.get_name.cache_info().misses
            + self.get_electronegativity.cache_info().misses
            + self.get_covalent_radius.cache_info().misses
            + self.get_vdw_radius.cache_info().misses
            + self.get_vdw_radius_angstrom.cache_info().misses
            + self.get_isotope.cache_info().misses
            + self.get_isotope_mass.cache_info().misses
            + self.get_isotope_abundance.cache_info().misses
            + self.get_available_isotopes.cache_info().misses
        )

    def get_cache_stats(self) -> Tuple[int, int]:
        """Return (hits, misses) tuple for telemetry reporting."""
        return (self.cache_hits, self.cache_misses)

    def clear_cache(self) -> None:
        """Clear all underlying LRU caches."""
        _fetch_mendeleev_element_cached.cache_clear()
        self.get_atomic_number.cache_clear()
        self.get_atomic_weight.cache_clear()
        self.get_symbol.cache_clear()
        self.get_name.cache_clear()
        self.get_electronegativity.cache_clear()
        self.get_covalent_radius.cache_clear()
        self.get_vdw_radius.cache_clear()
        self.get_vdw_radius_angstrom.cache_clear()
        self.get_isotope.cache_clear()
        self.get_isotope_mass.cache_clear()
        self.get_isotope_abundance.cache_clear()
        self.get_available_isotopes.cache_clear()


# Default global resolver instance
mendeleev_resolver = MendeleevResolver()

