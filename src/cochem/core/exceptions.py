"""Authoritative Core Exception Hierarchy for CoChem Core.

Adheres to:
- Method Matrix [M] & Provenance Standards
- Zero-Mock Anti-Spoofing Protocol
- Dynamic Mendeleev Invariant Mandate
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from cochem_base.exceptions import (
        CoChemError,
        MissingDataError as BaseMissingDataError,
        SingularityError,
    )
except ImportError:
    class CoChemError(Exception):
        pass

    class BaseMissingDataError(CoChemError, KeyError):
        pass

    class SingularityError(CoChemError, ValueError):
        pass


class MissingDataError(BaseMissingDataError):
    """Raised when required element, isotope, basis set, or calculation data is missing."""

    def __init__(self, message: str, symbol_or_query: Optional[Any] = None) -> None:
        super().__init__(message)
        self.message = message
        self.symbol_or_query = symbol_or_query


class MendeleevInvariantError(MissingDataError):
    """Raised when chemical element or isotopic queries violate Mendeleev physical invariants."""

    pass


class RotationalGridInstabilityError(CoChemError, ValueError):
    """Raised when Cartesian DFT integration grid breaks rotational invariance or induces imaginary modes."""

    def __init__(self, message: str, delta_cm1: Optional[float] = None) -> None:
        super().__init__(message)
        self.message = message
        self.delta_cm1 = delta_cm1


class JobTimeoutError(CoChemError, TimeoutError):
    """Raised when an asynchronous calculation or subprocess job exceeds temporal limits."""

    pass


__all__ = [
    "CoChemError",
    "MissingDataError",
    "MendeleevInvariantError",
    "RotationalGridInstabilityError",
    "JobTimeoutError",
]
