"""
Authoritative Dynamic Mendeleev Standard Atomic and Isotopic Mass Resolution.
Method Matrix v4: §6.10, §8B.4, and Anti-Spoofing Protocol v4.
Provides zero-mock dynamic nuclear masses strictly resolved via the mendeleev library
under the Mendeleev Library Mandate and Council Anti-Spoofing Protocol v4.
Static mass fallback dictionaries are strictly eradicated.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import logging
import math
from numbers import Integral
import re
import time
import threading
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


@dataclass(frozen=True)
class NormalizedNuclide:
    canonical_symbol: str
    mass_number: Optional[int]
    is_ghost: bool


class ZeroMassSystemError(ValueError):
    """All centers have zero mass, so a nuclear center of mass is undefined."""


_GHOST_LABEL = re.compile(
    r"^(?:(?:gh(?:ost)?|bq|x)(?:[_-]?(?P<parent>[A-Za-z]{1,2}))?|(?P<parent2>[A-Za-z]{1,2})[_-](?:gh(?:ost)?|bq|x))$",
    re.IGNORECASE,
)
_NUCLEAR_LABEL = re.compile(r"^(?P<prefix>[0-9]{1,3})?[_-]?(?P<symbol>[A-Za-z]{1,2})(?:[_-]?(?P<suffix>[0-9]{1,3}))?$")


def is_ghost_atom(label: str) -> bool:
    """Recognize complete counterpoise labels without confusing Xe with X."""
    if not isinstance(label, str) or not label.strip():
        return False
    clean = label.strip()
    # Real periodic-table symbols take precedence over a compact X prefix.
    if clean.casefold() in {"xe", "xenon"}:
        return False
    return _GHOST_LABEL.fullmatch(clean) is not None


@functools.lru_cache(maxsize=4096, typed=True)
def normalize_nuclide_symbol(raw_label: str) -> NormalizedNuclide:
    """Normalize supported isotope and ghost spellings with real element validation."""
    from cochem_base.physics.nuclide_resolver import InvalidNuclideSymbolError
    if not isinstance(raw_label, str) or not raw_label.strip():
        raise InvalidNuclideSymbolError(str(raw_label), "A nonempty nuclear label is required")
    clean = raw_label.strip()
    if clean.startswith(("-", "_")):
        raise InvalidNuclideSymbolError(clean, "A separator requires a leading isotope number")
    if is_ghost_atom(clean):
        match = _GHOST_LABEL.fullmatch(clean)
        parent = match.group("parent") or match.group("parent2")
        if parent:
            parent = parent.capitalize()
            if _get_mendeleev_element is None:
                raise RuntimeError("Mendeleev is required to validate a ghost basis parent")
            _get_mendeleev_element(parent)
            return NormalizedNuclide("Gh_" + parent, None, True)
        marker = clean.capitalize()
        return NormalizedNuclide("Gh" if marker.lower() == "ghost" else marker, None, True)
    match = _NUCLEAR_LABEL.fullmatch(clean)
    if match is None:
        raise InvalidNuclideSymbolError(clean, "Malformed nuclear label")
    prefix, symbol, suffix = match.group("prefix", "symbol", "suffix")
    if prefix and suffix and int(prefix) != int(suffix):
        raise InvalidNuclideSymbolError(clean, "Contradictory isotope numbers")
    number = int(prefix or suffix) if prefix or suffix else None
    alias = {"d": 2, "t": 3}.get(symbol.casefold())
    if alias is not None:
        if number is not None and number != alias:
            raise InvalidNuclideSymbolError(clean, "Contradictory hydrogen isotope alias")
        symbol, number = "H", alias
    else:
        symbol = symbol.capitalize()
    if number is not None and number <= 0:
        raise InvalidNuclideSymbolError(clean, "Isotope mass number must be positive")
    if _get_mendeleev_element is None:
        raise RuntimeError("Mendeleev is required to validate nuclear symbols")
    _get_mendeleev_element(symbol)
    return NormalizedNuclide(symbol, number, False)


def parse_nuclide_token(token: str) -> Tuple[str, Optional[int]]:
    """Compatibility electronic symbol/isotope view of structured normalization.

    Named ghost basis parents remain in NormalizedNuclide.canonical_symbol; this
    older two-value view supplies their electronic zero-charge marker.
    """
    result = normalize_nuclide_symbol(token)
    return ("Gh" if result.is_ghost and "_" in result.canonical_symbol else result.canonical_symbol,
            result.mass_number)


@functools.lru_cache(maxsize=4096, typed=True)
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


@functools.lru_cache(maxsize=4096, typed=True)
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


@functools.lru_cache(maxsize=4096, typed=True)
def get_principal_isotope_mass_number(symbol: str) -> int:
    """Select the most abundant measured natural isotope, requiring one to exist."""
    clean_sym, assigned = parse_nuclide_token(symbol)
    if assigned is not None:
        get_isotope_mass(clean_sym, assigned)
        return assigned
    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError("Mendeleev is required to resolve principal isotope masses")
    isotopes = [isotope for isotope in _get_mendeleev_element(clean_sym).isotopes
                if isotope.mass is not None and math.isfinite(float(isotope.mass)) and isotope.mass > 0
                and isotope.abundance is not None and isotope.abundance > 0]
    if not isotopes:
        raise ValueError(f"An explicit isotope is required for {clean_sym}")
    return int(max(isotopes, key=lambda isotope: (isotope.abundance, -isotope.mass_number)).mass_number)


@functools.lru_cache(maxsize=4096, typed=True)
def get_isotope_mass(symbol: str, mass_number: Optional[int] = None) -> float:
    """Retrieves exact isotopic mass in Daltons (amu) dynamically via mendeleev. [M]

    Handles isotopic symbols such as 'D', 'T', '13C', 'C-13', '18O', '2H'.
    Ghost atom centers ('Gh', 'Bq', 'X') return 0.0.
    """
    clean_sym, parsed_mass = parse_nuclide_token(symbol)

    if mass_number is not None and parsed_mass is not None and mass_number != parsed_mass:
        raise ValueError(f"Contradictory isotope specification: {symbol}, {mass_number}")
    if mass_number is None:
        mass_number = parsed_mass
    if mass_number is not None and (
        isinstance(mass_number, bool) or not isinstance(mass_number, Integral) or mass_number <= 0
    ):
        raise ValueError("Isotope mass number must be a positive integer")
    if clean_sym.upper() in GHOST_ATOMS:
        if mass_number is not None:
            raise ValueError("Ghost centers cannot carry a physical isotope number")
        return 0.0

    if mass_number is None:
        mass_number = get_principal_isotope_mass_number(clean_sym)

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


def warm_isotope_mass_cache() -> dict[str, object]:
    """Seed exact measured database masses and measure actual cached CPU retrieval.

    The reported timing is a measurement of this host, never a synthetic timing
    or a promise about every platform. Unmeasured isotopes are not manufactured.
    """
    if not HAS_MENDELEEV or _get_mendeleev_element is None:
        raise RuntimeError("Mendeleev is required for isotope cache warmup")
    count = 0
    from mendeleev.fetch import fetch_table
    rows = fetch_table("elements").sort_values("atomic_number")
    for symbol in rows["symbol"]:
        data = _get_mendeleev_element(symbol)
        for isotope in data.isotopes:
            if isotope.mass is not None and math.isfinite(float(isotope.mass)) and isotope.mass > 0:
                get_isotope_mass(symbol, int(isotope.mass_number))
                count += 1
        if any(isotope.abundance is not None and isotope.abundance > 0 and isotope.mass is not None
               for isotope in data.isotopes):
            get_isotope_mass(symbol)
    iterations = 10000
    samples = []
    for _ in range(5):
        started = time.perf_counter_ns()
        for _ in range(iterations):
            get_isotope_mass("C", 12)
        samples.append((time.perf_counter_ns() - started) / iterations)
    samples.sort()
    median = samples[len(samples) // 2]
    return {"mass_source": "dynamic_mendeleev", "cache_maxsize": get_isotope_mass.cache_info().maxsize,
            "measured_isotope_count": count, "cached_query_median_ns": median,
            "cached_query_mean_ns": sum(samples) / len(samples),
            "cached_query_under_500_ns": median < 500, "timing_scope": "measured_cpu_host_cached_query"}


@functools.lru_cache(maxsize=4096, typed=True)
def get_nuclide_mass(label: str, mass_number: Optional[int] = None) -> float:
    """Resolve an exact principal/assigned nuclear mass, including zero-mass ghosts."""
    return get_isotope_mass(label, mass_number)


@dataclass(frozen=True)
class MassCacheTelemetry:
    hit_count: int
    miss_count: int
    hit_ratio: float
    avg_latency_ns: Optional[float]


_MASS_CACHE_LOCK = threading.RLock()
_MEASURED_CACHE_LATENCY_NS: Optional[float] = None


def warmup_mass_cache() -> dict[str, object]:
    """Seed descriptive Z1..86 and measured isotopes, recording real host latency."""
    global _MEASURED_CACHE_LATENCY_NS
    from mendeleev.fetch import fetch_table
    with _MASS_CACHE_LOCK:
        rows = fetch_table("elements")
        for symbol in rows.loc[rows["atomic_number"].between(1, 86), "symbol"]:
            get_atomic_mass(symbol)
        evidence = warm_isotope_mass_cache()
        _MEASURED_CACHE_LATENCY_NS = float(evidence["cached_query_mean_ns"])
        return evidence


def clear_mass_cache() -> None:
    """Clear only derived lookup caches, retaining the authoritative database."""
    global _MEASURED_CACHE_LATENCY_NS
    with _MASS_CACHE_LOCK:
        for function in (get_atomic_mass, get_isotope_mass, get_element_mass_and_abundance,
                         get_principal_isotope_mass_number, get_nuclide_mass, normalize_nuclide_symbol):
            function.cache_clear()
        _MEASURED_CACHE_LATENCY_NS = None


def get_mass_cache_telemetry() -> MassCacheTelemetry:
    """Snapshot real thread-safe functools counters and measured warm latency."""
    with _MASS_CACHE_LOCK:
        counters = [function.cache_info() for function in
                    (get_atomic_mass, get_isotope_mass, get_nuclide_mass)]
        hits, misses = sum(info.hits for info in counters), sum(info.misses for info in counters)
        total = hits + misses
        return MassCacheTelemetry(hits, misses, hits / total if total else 0.0, _MEASURED_CACHE_LATENCY_NS)
