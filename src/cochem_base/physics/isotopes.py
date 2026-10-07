"""
Authoritative Dynamic Mendeleev Standard Atomic and Isotopic Mass Resolution.
Method Matrix v4: §6.10, §8B.4, and Anti-Spoofing Protocol v4.
Provides zero-mock dynamic nuclear masses strictly resolved via the mendeleev library
under the Mendeleev Library Mandate and Council Anti-Spoofing Protocol v4.
Static mass fallback dictionaries are strictly eradicated.
"""
from __future__ import annotations

import functools
import logging
import math
from numbers import Integral
import re
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    from cochem_base.physics.nuclide_resolver import get_element as _get_mendeleev_element
    HAS_MENDELEEV = True
except ImportError:
    _get_mendeleev_element = None
    HAS_MENDELEEV = False


def validate_pinned_tables_against_mendeleev() -> bool:
    """Verifies dynamic Mendeleev resolution integrity during Stage 0 setup. [M]

    Asserts dynamic database connectivity and high-precision physical retrieval
    under the Mendeleev Library Mandate.
    """
    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError("The 'mendeleev' library is required under the Mendeleev Library Mandate.")

    # Validate key elements resolve dynamically with non-null masses
    test_elements = ["H", "C", "N", "O", "S", "Cl"]
    for sym in test_elements:
        el = _get_mendeleev_element(sym)
        if el is None or el.mass is None:
            raise ValueError(f"Mendeleev failed to dynamically retrieve standard mass for {sym}")

        # Validate standard isotopes
        for iso in el.isotopes:
            if int(iso.mass_number) in (1, 2, 12, 13, 14, 16, 18) and iso.mass is not None:
                if iso.mass <= 0:
                    raise ValueError(f"Invalid non-physical mass for isotope {sym}-{iso.mass_number}")

    return True


GHOST_ATOMS: Set[str] = {"GH", "BQ", "X"}


def parse_nuclide_token(token: str) -> Tuple[str, Optional[int]]:
    """Normalizes nuclide token into canonical IUPAC element symbol and mass number. [M][D]

    Supports:
    - Standard symbols: 'C', 'O', 'Fe'
    - Common aliases: 'D' (H-2), 'T' (H-3)
    - Ghost / Counterpoise centers: 'Gh', 'Bq', 'X'
    - Prefix notation: '13C', '18O', '2H'
    - Hyphenated notation: 'C-13', 'H-2', 'Cl-35'
    - Suffix notation: 'C13', 'O18'
    """
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Nuclide token must be a nonempty string")
    clean = token.strip()
    upper = clean.upper()

    if upper in GHOST_ATOMS:
        return clean.capitalize(), None

    if upper == "D":
        return "H", 2
    if upper == "T":
        return "H", 3

    # Hyphenated format: 'C-13', 'Cl-35'
    m_hyphen = re.match(r"^([A-Za-z]+)-(\d+)$", clean)
    if m_hyphen:
        elem_str, iso_str = m_hyphen.groups()
        return elem_str.capitalize(), int(iso_str)

    # Prefix format: '13C', '2H'
    m_prefix = re.match(r"^(\d+)([A-Za-z]+)$", clean)
    if m_prefix:
        iso_str, elem_str = m_prefix.groups()
        return elem_str.capitalize(), int(iso_str)

    # Suffix format: 'C13', 'O18'
    m_suffix = re.match(r"^([A-Za-z]+)(\d+)$", clean)
    if m_suffix:
        elem_str, iso_str = m_suffix.groups()
        return elem_str.capitalize(), int(iso_str)

    return clean.capitalize(), None


@functools.lru_cache(maxsize=256)
def get_atomic_mass(symbol: str) -> float:
    """Retrieves standard atomic weight in Daltons (amu) dynamically via mendeleev. [M]"""
    clean_sym, mass_number = parse_nuclide_token(symbol)

    if clean_sym.upper() in GHOST_ATOMS:
        return 0.0

    if mass_number is not None:
        return get_isotope_mass(clean_sym, mass_number)

    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError(
            f"The 'mendeleev' library is required to dynamically resolve atomic masses "
            f"under the Mendeleev Library Mandate. Cannot resolve '{symbol}'."
        )

    try:
        el = _get_mendeleev_element(clean_sym)
        if el is not None and el.mass is not None:
            return float(el.mass)
    except Exception as exc:
        logger.error("Mendeleev standard atomic weight query failed for %s: %s", clean_sym, exc)
        raise ValueError(
            f"Standard atomic weight for element '{symbol}' could not be dynamically resolved via Mendeleev: {exc}"
        ) from exc

    raise ValueError(f"Standard atomic weight for element '{symbol}' not found in Mendeleev database.")


@functools.lru_cache(maxsize=256)
def get_element_mass_and_abundance(symbol: str) -> Tuple[float, float, int]:
    """Retrieves standard atomic mass, abundance, and atomic number Z dynamically via mendeleev. [M]"""
    clean_sym, mass_number = parse_nuclide_token(symbol)

    if clean_sym.upper() in GHOST_ATOMS:
        return 0.0, 1.0, 0

    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError(
            f"The 'mendeleev' library is required to dynamically resolve element properties "
            f"under the Mendeleev Library Mandate. Cannot resolve '{symbol}'."
        )
    try:
        el = _get_mendeleev_element(clean_sym)
        if el is not None and el.mass is not None:
            if mass_number is not None:
                for isotope in el.isotopes:
                    if isotope.mass_number == mass_number and isotope.mass is not None:
                        if isotope.abundance is None:
                            raise ValueError(f"Natural abundance unavailable for {symbol}")
                        return float(isotope.mass), float(isotope.abundance) / 100.0, int(el.atomic_number)
                raise ValueError(f"Isotope {symbol} not found in Mendeleev database")
            return float(el.mass), 1.0, int(el.atomic_number)
    except Exception as exc:
        logger.error("Mendeleev element property query failed for %s: %s", clean_sym, exc)
        raise ValueError(
            f"Element properties for '{clean_sym}' could not be dynamically resolved via Mendeleev: {exc}"
        ) from exc

    raise ValueError(f"Element properties for '{symbol}' not found in Mendeleev database.")


@functools.lru_cache(maxsize=512, typed=True)
def get_isotope_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Retrieves exact isotopic mass in Daltons (amu) dynamically via mendeleev. [M]

    Handles isotopic symbols such as 'D', 'T', '13C', 'C-13', '18O', '2H'.
    Ghost atom centers ('Gh', 'Bq', 'X') return 0.0.
    """
    clean_sym, parsed_mass = parse_nuclide_token(symbol)

    if clean_sym.upper() in GHOST_ATOMS:
        return 0.0

    if mass_number is not None and parsed_mass is not None and mass_number != parsed_mass:
        raise ValueError(f"Contradictory isotope specification: {symbol}, {mass_number}")
    if mass_number is None:
        mass_number = parsed_mass
    if mass_number is not None and (
        isinstance(mass_number, bool) or not isinstance(mass_number, Integral) or mass_number <= 0
    ):
        raise ValueError("Isotope mass number must be a positive integer")

    if mass_number is None:
        return get_atomic_mass(clean_sym)

    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError(
            f"The 'mendeleev' library is required to dynamically resolve isotopic masses "
            f"under the Mendeleev Library Mandate. Cannot resolve '{symbol}-{mass_number}'."
        )

    try:
        el = _get_mendeleev_element(clean_sym)
        if el is not None:
            for iso in el.isotopes:
                if int(iso.mass_number) == mass_number and iso.mass is not None:
                    mass = float(iso.mass)
                    if not math.isfinite(mass) or mass <= 0:
                        raise ValueError(f"Nonphysical isotope mass for {clean_sym}-{mass_number}")
                    return mass
    except Exception as exc:
        logger.error("Mendeleev isotope query failed for %s-%s: %s", clean_sym, mass_number, exc)
        raise ValueError(
            f"Isotopic mass for {clean_sym}-{mass_number} could not be dynamically resolved via Mendeleev: {exc}"
        ) from exc

    raise ValueError(f"Isotopic mass for {clean_sym}-{mass_number} not found in Mendeleev database.")
