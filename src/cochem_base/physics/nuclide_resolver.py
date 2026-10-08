"""
CoChem Physical Nuclide Resolver & Dynamic Mendeleev Binding Engine.
WBS 1.2.1: Regex Tokenization & Nuclide Mass Disambiguation Engine
WBS 1.2.2: Dynamic Mendeleev Database Query Binding & Isotope Fallback

Authoritative physical module providing deterministic nuclide token parsing,
symbol canonicalization, dynamic atomic and isotopic mass resolution via the
authoritative mendeleev SQLite database, Pyykko single-bond covalent radii conversion,
and thread-safe LRU caching.

Strictly adheres to Method Matrix v4.1, CoChem Anti-Spoofing Protocol v4,
and Council Emergency Session 010 Directives (PCA-01 - PCA-06).
Zero hardcoded mass dictionaries permitted.
"""
from __future__ import annotations

import functools
import re
from numbers import Integral
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

try:
    from cochem_base.exceptions import CoChemError
except ImportError:
    class CoChemError(Exception):
        """Fallback root exception if cochem_base.exceptions cannot be imported."""
        pass

try:
    import mendeleev
    from mendeleev import element as _mendeleev_element
    HAS_MENDELEEV = True
except ImportError:
    mendeleev = None  # type: ignore
    _mendeleev_element = None  # type: ignore
    HAS_MENDELEEV = False


# ============================================================================
# Exception Hierarchy (Task 1.2.1 Section 5)
# ============================================================================

class NuclideResolutionError(CoChemError, ValueError):
    """Base exception for all nuclide resolution and mass evaluation errors."""
    pass


class InvalidNuclideSymbolError(NuclideResolutionError):
    """Raised when an input nuclide symbol or token violates physical syntax."""

    def __init__(self, token_str: str, reason: Optional[str] = None) -> None:
        self.token_str = str(token_str)
        self.reason = reason
        if reason is not None:
            message = f"Nuclide token '{token_str}' rejected: {reason}"
        else:
            if " " in self.token_str:
                message = self.token_str
            else:
                message = f"Nuclide token '{token_str}' rejected: Invalid syntax or unrecognized element"
        super().__init__(message)


class InvalidNuclideError(InvalidNuclideSymbolError):
    """Alias for InvalidNuclideSymbolError to maintain ecosystem compatibility."""
    pass


class IsotopeNotFoundError(NuclideResolutionError):
    """Raised when an explicit mass number does not correspond to a known isotope."""

    def __init__(self, symbol: str, mass_number: Optional[int] = None) -> None:
        self.symbol = str(symbol)
        self.mass_number = mass_number
        if mass_number is not None:
            message = f"Isotope {symbol}-{mass_number} does not exist in Mendeleev database"
        else:
            if " " in self.symbol:
                message = self.symbol
            else:
                message = f"Isotope for element '{symbol}' does not exist in Mendeleev database"
        super().__init__(message)


class NuclideDatabaseError(NuclideResolutionError):
    """Raised when the underlying Mendeleev database is unreachable or corrupt."""
    pass


# ============================================================================
# Constants & Regular Expression Invariants
# ============================================================================

# Strictly compiled regular expression invariant: R_nuclide = ^(\d+)?([A-Za-z]+)$
# Group 1: Optional leading integer representing mass number A
# Group 2: One or more alphabetic characters representing chemical symbol
NUCLIDE_REGEX: re.Pattern[str] = re.compile(r"^(\d+)?([A-Za-z]+)$")

# IUPAC recognized hydrogen isotopic shorthand aliases
H_ISOTOPE_ALIASES: Dict[str, Tuple[str, int]] = {
    "D": ("H", 2),
    "T": ("H", 3),
}


# ============================================================================
# Data Structures
# ============================================================================

@dataclass(frozen=True, slots=True)
class NuclideToken:
    """Immutable, slot-optimized nuclide token representing parsed physical identity.

    Attributes:
        symbol: IUPAC canonicalized chemical element symbol (e.g., 'H', 'C', 'Cl').
        mass_number: Optional integer mass number A (e.g., 13 for 13C, 2 for D).
        is_isotope_alias: True if resolved via shorthand alias ('D', 'T').
        raw_token: Original raw input string before normalization (excluded from equality comparisons).
    """
    symbol: str
    mass_number: Optional[int] = None
    is_isotope_alias: bool = False
    raw_token: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if self.mass_number is not None and (
            isinstance(self.mass_number, bool) or not isinstance(self.mass_number, Integral) or self.mass_number <= 0
        ):
            raise InvalidNuclideSymbolError(
                f"{self.mass_number}{self.symbol}",
                "Mass number must be a positive non-zero integer",
            )


# ============================================================================
# Tokenization & Parsing (WBS 1.2.1)
# ============================================================================

def parse_nuclide(token_str: str = "", *, token: Optional[str] = None) -> NuclideToken:
    """Return the typed real-nucleus view of the canonical alias normalizer."""
    from cochem_base.physics.isotopes import normalize_nuclide_symbol
    raw = token if token is not None else token_str
    normalized = normalize_nuclide_symbol(raw)
    if normalized.is_ghost:
        raise InvalidNuclideSymbolError(str(raw), "Ghost basis centers are not real nuclei")
    cleaned = raw.strip()
    is_alias = re.fullmatch(r"(?:[0-9]+[_-]?)?[dDtT](?:[_-]?[0-9]+)?", cleaned) is not None
    return NuclideToken(normalized.canonical_symbol, normalized.mass_number, is_alias, cleaned)


# ============================================================================
# Dynamic Mendeleev Binding & Validation (WBS 1.2.2)
# ============================================================================

@functools.lru_cache(maxsize=4096, typed=True)
def get_element(symbol: str) -> Any:
    """Retrieve mendeleev Element model object with thread-safe LRU caching.

    Args:
        symbol: Canonicalized chemical element symbol (e.g. 'C', 'Fe', 'Cl').

    Returns:
        Mendeleev Element object.

    Raises:
        NuclideDatabaseError: If mendeleev library is not installed or database fails.
        InvalidNuclideSymbolError: If symbol does not exist in the periodic table.
    """
    if not HAS_MENDELEEV or _mendeleev_element is None:
        raise NuclideDatabaseError(
            "Mendeleev database backend is unavailable. Dynamic mass resolution requires mendeleev."
        )

    try:
        elem = _mendeleev_element(symbol)
        if elem is None:
            raise InvalidNuclideSymbolError(symbol, f"Chemical symbol {symbol!r} not found in IUPAC periodic table.")
        return elem
    except Exception as exc:
        if isinstance(exc, (InvalidNuclideSymbolError, NuclideDatabaseError)):
            raise
        # Mendeleev raises generic exceptions or ValueError/KeyError on missing element
        raise InvalidNuclideSymbolError(
            symbol, f"Unrecognized chemical element symbol {symbol!r}: {exc}"
        ) from exc


def get_mendeleev_element(symbol: str) -> Any:
    """Alias for get_element compliant with Council PCA specifications."""
    return get_element(symbol)


def _validate_element_symbol(symbol: str) -> None:
    """Internal validator verifying that symbol exists in the IUPAC periodic table."""
    get_element(symbol)


# ============================================================================
# Mass Disambiguation & Physical Property Resolution (WBS 1.2.1 & 1.2.2)
# ============================================================================

@functools.lru_cache(maxsize=4096, typed=True)
def disambiguate_mass(token: Union[str, NuclideToken]) -> float:
    """Resolve a measured assigned/principal isotope, never an averaged weight.

    Elements without a measured natural isotope require an explicit assignment.
    """
    if isinstance(token, str):
        parsed = parse_nuclide(token)
    elif isinstance(token, NuclideToken):
        parsed = token
    else:
        raise InvalidNuclideSymbolError(str(token), "Expected str or NuclideToken")
    get_element(parsed.symbol)
    from cochem_base.physics.isotopes import get_isotope_mass
    try:
        return get_isotope_mass(parsed.symbol, parsed.mass_number)
    except ValueError as error:
        if parsed.mass_number is not None:
            raise IsotopeNotFoundError(parsed.symbol, parsed.mass_number) from error
        raise NuclideResolutionError(str(error)) from error


@functools.lru_cache(maxsize=4096, typed=True)
def resolve_covalent_radius(token: Union[str, NuclideToken]) -> Optional[float]:
    """Dynamically resolve single-bond covalent radius in Angstroms (A).

    Queries elem.covalent_radius_pyykko (relativistic single-bond radius in picometers)
    with fallback to elem.covalent_radius, converting dynamically from pm to Angstroms
    (r_A = r_pm * 0.01).

    Args:
        token: Nuclide token string or NuclideToken.

    Returns:
        Covalent radius in Angstroms as float, or None if unavailable.
    """
    if isinstance(token, str):
        parsed = parse_nuclide(token)
    elif isinstance(token, NuclideToken):
        parsed = token
    else:
        raise InvalidNuclideSymbolError(
            str(token),
            f"Expected str or NuclideToken, got {type(token).__name__}: {token!r}",
        )

    elem = get_element(parsed.symbol)

    r_pm = getattr(elem, "covalent_radius_pyykko", None)
    if r_pm is None:
        r_pm = getattr(elem, "covalent_radius", None)

    if r_pm is not None:
        # Convert picometers to Angstroms: 1 pm = 1e-12 m = 0.01 A
        return float(r_pm) * 0.01

    return None


@functools.lru_cache(maxsize=4096, typed=True)
def resolve_vdw_radius(token: Union[str, NuclideToken]) -> Optional[float]:
    """Dynamically resolve van der Waals radius in Angstroms (A).

    Queries elem.vdw_radius in picometers and converts to Angstroms (r_A = r_pm * 0.01).

    Args:
        token: Nuclide token string or NuclideToken.

    Returns:
        Van der Waals radius in Angstroms as float, or None if unavailable.
    """
    if isinstance(token, str):
        parsed = parse_nuclide(token)
    elif isinstance(token, NuclideToken):
        parsed = token
    else:
        raise InvalidNuclideSymbolError(
            str(token),
            f"Expected str or NuclideToken, got {type(token).__name__}: {token!r}",
        )

    elem = get_element(parsed.symbol)
    r_pm = getattr(elem, "vdw_radius", None)
    if r_pm is not None:
        return float(r_pm) * 0.01
    return None


@functools.lru_cache(maxsize=4096, typed=True)
def get_nuclide_spin_and_quadrupole(
    token: Union[str, NuclideToken]
) -> Tuple[Optional[float], Optional[float]]:
    """Retrieve nuclear spin (I) and electric quadrupole moment (Q in barns).

    Args:
        token: Nuclide token string or NuclideToken.

    Returns:
        Tuple of (nuclear_spin, quadrupole_moment_barns).
    """
    if isinstance(token, str):
        parsed = parse_nuclide(token)
    elif isinstance(token, NuclideToken):
        parsed = token
    else:
        raise InvalidNuclideSymbolError(
            str(token),
            f"Expected str or NuclideToken, got {type(token).__name__}: {token!r}",
        )

    elem = get_element(parsed.symbol)
    if parsed.mass_number is not None:
        for iso in getattr(elem, "isotopes", []):
            if getattr(iso, "mass_number", None) == parsed.mass_number:
                spin = getattr(iso, "spin", None)
                quad = getattr(iso, "quadrupole_moment", None)
                spin_val = float(spin) if spin is not None else None
                quad_val = float(quad) if quad is not None else None
                return spin_val, quad_val

    # If no mass number specified, check most abundant isotope
    isotopes = getattr(elem, "isotopes", [])
    if isotopes:
        abundant_iso = max(isotopes, key=lambda i: getattr(i, "abundance", 0.0) or 0.0)
        spin = getattr(abundant_iso, "spin", None)
        quad = getattr(abundant_iso, "quadrupole_moment", None)
        spin_val = float(spin) if spin is not None else None
        quad_val = float(quad) if quad is not None else None
        return spin_val, quad_val

    return None, None


__all__ = [
    "HAS_MENDELEEV",
    "H_ISOTOPE_ALIASES",
    "NUCLIDE_REGEX",
    "CoChemError",
    "InvalidNuclideError",
    "InvalidNuclideSymbolError",
    "IsotopeNotFoundError",
    "NuclideDatabaseError",
    "NuclideResolutionError",
    "NuclideToken",
    "disambiguate_mass",
    "get_element",
    "get_mendeleev_element",
    "get_nuclide_spin_and_quadrupole",
    "parse_nuclide",
    "resolve_covalent_radius",
    "resolve_vdw_radius",
]
