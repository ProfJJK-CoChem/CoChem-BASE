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

class NuclideResolutionError(CoChemError):
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
    """Deterministically parse and canonicalize a nuclide string.

    Args:
        token_str: Raw nuclide token string (e.g., '13C', 'D', 'T', '18O', 'Cl', 'c').
        token: Optional keyword-only alias for token_str.

    Returns:
        Canonicalized NuclideToken instance.

    Raises:
        InvalidNuclideSymbolError: If syntax is malformed, contains non-alphanumeric
            characters, non-positive mass, or the chemical symbol is not recognized in the periodic table.
    """
    raw = token if token is not None else token_str
    if not isinstance(raw, str):
        raise InvalidNuclideSymbolError(
            str(raw),
            f"Nuclide token must be a string, got {type(raw).__name__}: {raw!r}",
        )

    cleaned = raw.strip()
    if not cleaned:
        raise InvalidNuclideSymbolError(raw, "Empty nuclide token is prohibited.")

    match = NUCLIDE_REGEX.match(cleaned)
    if not match:
        raise InvalidNuclideSymbolError(
            cleaned,
            "Token violates regex invariant R_nuclide (^(\\d+)?([A-Za-z]+)$)",
        )

    raw_mass_num, raw_symbol = match.groups()

    # Parse mass number A
    mass_number: Optional[int] = None
    if raw_mass_num is not None:
        mass_number = int(raw_mass_num)
        if mass_number <= 0:
            raise InvalidNuclideSymbolError(
                cleaned,
                f"Physical mass number must be positive non-zero, got {mass_number}.",
            )

    # Canonicalize symbol casing: s[0].upper() + s[1:].lower()
    canonical_symbol = raw_symbol[0].upper() + raw_symbol[1:].lower()

    # Disambiguate Hydrogen isotope aliases ('D', 'T')
    is_alias = False
    upper_symbol = raw_symbol.upper()
    if upper_symbol in H_ISOTOPE_ALIASES:
        target_elem, alias_a = H_ISOTOPE_ALIASES[upper_symbol]
        if mass_number is not None and mass_number != alias_a:
            raise InvalidNuclideSymbolError(
                cleaned,
                f"Contradictory mass number {mass_number} specified for Hydrogen alias {upper_symbol!r} (expected {alias_a}).",
            )
        canonical_symbol = target_elem
        mass_number = alias_a
        is_alias = True

    # Validate that canonical_symbol exists in periodic table via dynamic Mendeleev lookup
    _validate_element_symbol(canonical_symbol)

    return NuclideToken(
        symbol=canonical_symbol,
        mass_number=mass_number,
        is_isotope_alias=is_alias,
        raw_token=cleaned,
    )


# ============================================================================
# Dynamic Mendeleev Binding & Validation (WBS 1.2.2)
# ============================================================================

@functools.lru_cache(maxsize=1024)
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

@functools.lru_cache(maxsize=1024)
def disambiguate_mass(token: Union[str, NuclideToken]) -> float:
    """Dynamically resolve exact atomic or isotopic mass in unified atomic mass units (u).

    For queries carrying an explicit mass number A, returns exact physical isotopic mass
    from AME2020 via mendeleev (precision +/- 1e-8 u).
    For queries without an explicit mass number, returns IUPAC standard terrestrial
    atomic weight (elem.atomic_weight). For transuranics/synthetic elements lacking
    terrestrial atomic weight, returns the mass of the most stable isotope (elem.mass).

    Args:
        token: Nuclide token string (e.g., '13C', 'D', '34S', 'O') or NuclideToken.

    Returns:
        Exact mass in unified atomic mass units (u, Daltons) as float.

    Raises:
        IsotopeNotFoundError: If explicit mass number A is not present in database.
        InvalidNuclideSymbolError: If nuclide symbol syntax is invalid.
        NuclideDatabaseError: If database query fails.
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
        # Search for exact isotope
        isotopes = getattr(elem, "isotopes", [])
        matched_iso = None
        for iso in isotopes:
            if getattr(iso, "mass_number", None) == parsed.mass_number:
                matched_iso = iso
                break

        if matched_iso is None or getattr(matched_iso, "mass", None) is None:
            raise IsotopeNotFoundError(parsed.symbol, parsed.mass_number)
        return float(matched_iso.mass)

    # Fallback to IUPAC standard terrestrial atomic weight
    atomic_weight = getattr(elem, "atomic_weight", None)
    if atomic_weight is not None:
        return float(atomic_weight)

    # For synthetic or radioactive elements lacking standard atomic weight (e.g. Tc, Pm, transuranics)
    nominal_mass = getattr(elem, "mass", None)
    if nominal_mass is not None:
        return float(nominal_mass)

    raise NuclideResolutionError(
        f"Unable to resolve standard atomic weight or isotope mass for element {parsed.symbol!r}."
    )


@functools.lru_cache(maxsize=1024)
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


@functools.lru_cache(maxsize=1024)
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


@functools.lru_cache(maxsize=1024)
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
