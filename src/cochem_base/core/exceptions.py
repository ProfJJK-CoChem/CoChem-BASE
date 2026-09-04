"""Authoritative Core Domain Exceptions for CoChem-BASE.

Provides physical invariant exceptions for isotopic stability, empirical radii,
and domain perceptions adhering to Method Matrix v4 §6.10, §8C, and §20.
Includes machine-actionable error codes for automated ETL triage.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class CoChemError(Exception):
    """Base error class for all CoChem operations with machine-actionable error codes."""

    def __init__(
        self,
        message: str,
        error_code: str = "COCHEM_E_GENERIC",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"[{error_code}] {message}")
        self.message: str = message
        self.error_code: str = error_code
        self.details: Dict[str, Any] = details if details is not None else {}


class CoordinateShapeError(CoChemError):
    """Raised when molecular coordinate arrays violate dimensionality constraints (e.g. not N x 3)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_INVALID_COORD_SHAPE", details=details)


class AirGapBoundaryError(CoChemError):
    """Raised when an operation attempts to write to a read-only or out-of-tier filesystem boundary."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_AIRGAP_BREACH", details=details)


class SchemaMigrationError(CoChemError):
    """Raised when deserializing a payload lacking a valid migration path to current schema_version."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_SCHEMA_MIGRATION_FAILED", details=details)


class PESStorageError(CoChemError):
    """Raised when HDF5 SWMR store operations fail or encounter lock contention."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_PES_STORAGE_FAILURE", details=details)


class ProcessReaperError(CoChemError):
    """Raised when process termination or resource sampling fails unexpectedly."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_PROCESS_REAPER_FAILURE", details=details)


class SubprocessBrokerError(CoChemError):
    """Raised when isolated subprocess execution fails pre-flight or runtime contracts."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_SUBPROCESS_BROKER_FAILURE", details=details)


class ThermodynamicsParameterError(CoChemError):
    """Raised when required quasi-harmonic parameters are missing from thermodynamic calculations."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_THERMO_PARAM_MISSING", details=details)


class IsotopeMassResolutionError(CoChemError):
    """Raised when requested isotope cannot be resolved to physical mass."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_ISOTOPE_NOT_FOUND", details=details)


class IsotopeStabilityError(CoChemError, ValueError):
    """Raised when a requested isotope cannot be physically resolved to an isotopic nuclear mass."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_ISOTOPE_STABILITY", details=details)


class RadiusNotFoundError(CoChemError, KeyError):
    """Raised when empirical covalent or van der Waals radius is unavailable for an element."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="COCHEM_E_RADIUS_NOT_FOUND", details=details)


__all__ = [
    "CoChemError",
    "CoordinateShapeError",
    "AirGapBoundaryError",
    "SchemaMigrationError",
    "PESStorageError",
    "ProcessReaperError",
    "SubprocessBrokerError",
    "ThermodynamicsParameterError",
    "IsotopeMassResolutionError",
    "IsotopeStabilityError",
    "RadiusNotFoundError",
]
