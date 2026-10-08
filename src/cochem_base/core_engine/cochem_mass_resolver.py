"""Authoritative Dynamic Mendeleev Mass Resolver with LRU In-Memory Caching.

Complies strictly with:
- Method Matrix v4 §8A.4: Precomputation of masses on CPU before CUDA kernels without GPU context stalls.
- Dynamic Mendeleev Invariant Mandate: Dynamic atomic and isotopic mass retrieval using `mendeleev`.
- Zero-Mock Anti-Spoofing Protocol: Authentic physical mass resolution.
"""

from __future__ import annotations

from functools import lru_cache
from numbers import Integral
from typing import Union

import mendeleev
from cochem_base.core.exceptions import IsotopeMassResolutionError


@lru_cache(maxsize=4096, typed=True)
def get_dynamic_atomic_mass(symbol_or_z: Union[str, int]) -> float:
    """Return a dynamically measured assigned/principal isotope mass."""
    try:
        from cochem_base.physics.isotopes import get_isotope_mass
        symbol = mendeleev.element(symbol_or_z).symbol if isinstance(symbol_or_z, int) else symbol_or_z
        return get_isotope_mass(symbol)
    except Exception as exc:
        raise IsotopeMassResolutionError(
            f"Element '{symbol_or_z}' cannot be resolved via Mendeleev: {exc}",
            details={"element": symbol_or_z},
        ) from exc

@lru_cache(maxsize=4096, typed=True)
def get_dynamic_isotopic_mass(symbol_or_z: Union[str, int], mass_number: int) -> float:
    """Returns exact physical isotopic nuclear mass from Mendeleev with LRU memory caching.

    Guarantees zero fallback to terrestrial average atomic weights.
    """
    if isinstance(mass_number, bool) or not isinstance(mass_number, Integral) or mass_number <= 0:
        raise IsotopeMassResolutionError("Isotope mass number must be a positive integer.")
    try:
        from cochem_base.physics.isotopes import get_isotope_mass
        symbol = mendeleev.element(symbol_or_z).symbol if isinstance(symbol_or_z, int) else symbol_or_z
        return get_isotope_mass(symbol, mass_number)
    except Exception as exc:
        raise IsotopeMassResolutionError(
            f"Element '{symbol_or_z}' cannot be resolved via Mendeleev: {exc}",
            details={"element": symbol_or_z, "mass_number": mass_number},
        ) from exc

__all__ = [
    "get_dynamic_atomic_mass",
    "get_dynamic_isotopic_mass",
    "IsotopeMassResolutionError",
]
