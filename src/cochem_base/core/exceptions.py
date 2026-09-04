"""Authoritative Core Domain Exceptions for CoChem-BASE.

Provides physical invariant exceptions for isotopic stability, empirical radii,
and domain perceptions adhering to Method Matrix v4 §6.10, §8C, and §20.
"""

from __future__ import annotations


class IsotopeStabilityError(ValueError):
    """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""

    pass


class RadiusNotFoundError(KeyError):
    """Raised when empirical covalent or van der Waals radius is unavailable for an element."""

    pass


__all__ = [
    "IsotopeStabilityError",
    "RadiusNotFoundError",
]
