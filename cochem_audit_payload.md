Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-TORQ\.in-progress\Perfected_Task 11 Statistical Mechanics & SPCAT Bridge (Stage 5.1).md.
Original prompt:
# Generated Prompt (Dry Run)
Source: Perfected_Task 11 Statistical Mechanics & SPCAT Bridge (Stage 5.1).md
Target Repo: D:\__CoChem\GitHub-Repo\CoChem-TORQ

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\exceptions.py ---
"""Ecosystem-wide exception and warning definitions for CoChem.

Provides hierarchical error types, standardized error codes, structured
metadata payload serialization, polymorphic deserialization registries,
pickle support for multiprocessing, and exception wrapper utilities compliant
with CoChem Method Matrix standards.
"""

from __future__ import annotations

import asyncio
import functools
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)


class ProvenanceErrorCode(str, Enum):
    """Standardized error codes for CoChem provenance, engine, and infrastructure errors."""

    # Method Matrix & Provenance
    METHOD_MATRIX_VIOLATION_DEFGRID = "METHOD_MATRIX_VIOLATION_DEFGRID"
    EXCEPTION_DEFLECTION_BLOCKED = "EXCEPTION_DEFLECTION_BLOCKED"
    MISSING_DATA = "MISSING_DATA"
    SPIN_CONTAMINATION_EXCEEDED = "SPIN_CONTAMINATION_EXCEEDED"
    UNSUPPORTED_METHOD = "UNSUPPORTED_METHOD"
    DISPERSION_MISSING = "DISPERSION_MISSING"
    INVALID_HESSIAN_STRATEGY = "INVALID_HESSIAN_STRATEGY"
    FROZEN_MONOMER_VIOLATION = "FROZEN_MONOMER_VIOLATION"
    PATHOLOGY_CLASH = "PATHOLOGY_CLASH"
    TRIAGE_OVERRIDE_SPIN = "TRIAGE_OVERRIDE_SPIN"
    AUTOFIT_LIMIT_EXCEEDED = "AUTOFIT_LIMIT_EXCEEDED"
    EVALUATION_TIMEOUT = "EVALUATION_TIMEOUT"
    QCSCHEMA_VALIDATION_FAILED = "QCSCHEMA_VALIDATION_FAILED"
    BSSE_CORRECTION_FAILED = "BSSE_CORRECTION_FAILED"

    # Infrastructure & Security
    HDF5_SWMR_LOCK_TIMEOUT = "HDF5_SWMR_LOCK_TIMEOUT"
    REGISTRY_LOCK_TIMEOUT = "REGISTRY_LOCK_TIMEOUT"
    INTEGRITY_VIOLATION = "INTEGRITY_VIOLATION"
    CONFIG_VALIDATION_FAILED = "CONFIG_VALIDATION_FAILED"
    PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
    TELEMETRY_FAILURE = "TELEMETRY_FAILURE"
    DISK_QUOTA_EXCEEDED = "DISK_QUOTA_EXCEEDED"

    # Engine & Math
    CONVERGENCE_FAILURE = "CONVERGENCE_FAILURE"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    HARDWARE_DETECTION_FAILED = "HARDWARE_DETECTION_FAILED"
    SINGULARITY_DETECTED = "SINGULARITY_DETECTED"
    PRECISION_VIOLATION = "PRECISION_VIOLATION"
    LAM_TRIGGER = "LAM_TRIGGER"
    FORTRAN_OVERFLOW = "FORTRAN_OVERFLOW"
    SPCAT_BRIDGE_ERROR = "SPCAT_BRIDGE_ERROR"
    AIRGAP_VIOLATION = "AIRGAP_VIOLATION"

    @classmethod
    def from_str(cls, code: Union[str, ProvenanceErrorCode]) -> ProvenanceErrorCode:
        """Convert a string or enum instance into a ProvenanceErrorCode.

        Args:
            code: String error code or existing ProvenanceErrorCode instance.

        Returns:
            The matching ProvenanceErrorCode enum instance.

        Raises:
            ValueError: If the code does not match any valid ProvenanceErrorCode.
        """
        if isinstance(code, cls):
            return code
        if isinstance(code, str):
            cleaned = code.strip()
            try:
                return cls(cleaned)
            except ValueError:
                try:
                    return cls[cleaned.upper()]
                except KeyError:
                    raise ValueError(f"Unknown ProvenanceErrorCode: {code!r}") from None
        raise ValueError(f"Expected str or ProvenanceErrorCode, got {type(code).__name__}: {code!r}")

    @classmethod
    def has_code(cls, code: Union[str, Any]) -> bool:
        """Check if a given string or object corresponds to a valid ProvenanceErrorCode.

        Args:
            code: String or object to check.

        Returns:
            True if code matches a known ProvenanceErrorCode value or name, False otherwise.
        """
        if isinstance(code, cls):
            return True
        if isinstance(code, str):
            cleaned = code.strip()
            if cleaned in cls._value2member_map_:
                return True
            if cleaned.upper() in cls.__members__:
                return True
        return False


def format_error_message(
    error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Format a standardized CoChem error message string.

    Args:
        error_code: Optional ProvenanceErrorCode enum or string code.
        message: Descriptive error message text.
        details: Optional dictionary containing contextual metadata.

    Returns:
        Formatted error message string, e.g. '[E: CODE] Message (details: k=v)'.
    """
    code_str: Optional[str] = None
    if error_code is not None:
        code_str = error_code.value if isinstance(error_code, ProvenanceErrorCode) else str(error_code).strip()

    prefix = f"[E: {code_str}] " if code_str else ""
    base = f"{prefix}{message}"
    if details:
        details_str = ", ".join(f"{k}={v!r}" for k, v in sorted(details.items()))
        return f"{base} (details: {details_str})"
    return base


def format_warning_message(
    warning_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Format a standardized CoChem warning message string.

    Args:
        warning_code: Optional ProvenanceErrorCode enum or string code.
        message: Descriptive warning message text.
        details: Optional dictionary containing contextual metadata.

    Returns:
        Formatted warning message string, e.g. '[W: CODE] Message (details: k=v)'.
    """
    code_str: Optional[str] = None
    if warning_code is not None:
        code_str = warning_code.value if isinstance(warning_code, ProvenanceErrorCode) else str(warning_code).strip()

    prefix = f"[W: {code_str}] " if code_str else ""
    base = f"{prefix}{message}"
    if details:
        details_str = ", ".join(f"{k}={v!r}" for k, v in sorted(details.items()))
        return f"{base} (details: {details_str})"
    return base


def _reconstruct_cochem_error(
    cls: Type[CoChemError],
    message: str,
    error_code: Optional[Union[ProvenanceErrorCode, str]],
    details: Optional[Dict[str, Any]],
    timestamp: Optional[str],
) -> CoChemError:
    """Helper function to reconstruct a CoChemError instance during unpickling.

    Args:
        cls: The CoChemError subclass to instantiate.
        message: The original unformatted error message.
        error_code: Optional error code.
        details: Optional details dictionary.
        timestamp: Optional ISO 8601 UTC timestamp string.

    Returns:
        Reconstructed CoChemError (or subclass) instance.
    """
    return cls(
        message=message,
        error_code=error_code,
        details=details,
        timestamp=timestamp,
    )


# Polymorphic exception registry for deserialization
_EXCEPTION_REGISTRY: Dict[str, Type[CoChemError]] = {}


class CoChemError(Exception):
    """Root exception for all CoChem ecosystem errors.

    Attributes:
        message: Human-readable error description.
        error_code: Optional ProvenanceErrorCode or string identifier.
        details: Supplementary structured metadata key-value pairs.
        timestamp: ISO 8601 UTC timestamp of error creation.
        formatted_message: Fully formatted message including code prefix and details.
    """

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register all subclasses dynamically for polymorphic deserialization."""
        super().__init_subclass__(**kwargs)
        _EXCEPTION_REGISTRY[cls.__name__] = cls

    def __init__(
        self,
        message: str,
        error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.message: str = str(message)

        raw_code = error_code if error_code is not None else self.default_error_code
        if isinstance(raw_code, str):
            try:
                self.error_code: Optional[Union[ProvenanceErrorCode, str]] = ProvenanceErrorCode(raw_code)
            except ValueError:
                self.error_code = raw_code
        elif isinstance(raw_code, ProvenanceErrorCode):
            self.error_code = raw_code
        else:
            self.error_code = None

        self.details: Dict[str, Any] = dict(details) if details is not None else {}
        self.timestamp: str = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
        self.formatted_message: str = format_error_message(self.error_code, self.message, self.details)
        super().__init__(self.formatted_message)

    def __str__(self) -> str:
        return self.formatted_message

    def __repr__(self) -> str:
        parts = [repr(self.message)]
        if self.error_code is not None:
            parts.append(f"error_code={self.error_code!r}")
        if self.details:
            parts.append(f"details={self.details!r}")
        return f"{self.__class__.__name__}({', '.join(parts)})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception attributes into a structured dictionary.

        Returns:
            Dictionary containing error_type, error_code, message, details, and timestamp.
        """
        code_val = self.error_code.value if isinstance(self.error_code, ProvenanceErrorCode) else self.error_code
        return {
            "error_type": self.__class__.__name__,
            "error_code": code_val,
            "message": self.message,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CoChemError:
        """Deserialize a structured dictionary into a CoChemError or appropriate subclass.

        Polymorphically instantiates the target subclass if registered in _EXCEPTION_REGISTRY.

        Args:
            data: Dictionary containing error_type, error_code, message, details, and optional timestamp.

        Returns:
            Instantiated CoChemError (or subclass) instance.
        """
        error_type = data.get("error_type")
        target_cls: Type[CoChemError] = cls
        if error_type and error_type in _EXCEPTION_REGISTRY:
            target_cls = _EXCEPTION_REGISTRY[error_type]
        elif cls is CoChemError and error_type:
            target_cls = CoChemError

        message = str(data.get("message", ""))
        error_code = data.get("error_code")
        details = data.get("details")
        timestamp = data.get("timestamp")

        return target_cls(
            message=message,
            error_code=error_code,
            details=details if isinstance(details, dict) else None,
            timestamp=timestamp if isinstance(timestamp, str) else None,
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize exception attributes into a JSON string.

        Args:
            indent: Optional indentation level for pretty-printing.

        Returns:
            JSON string representation of the exception payload.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> CoChemError:
        """Deserialize a JSON string into a CoChemError or appropriate subclass.

        Args:
            json_str: JSON formatted string containing serialized error payload.

        Returns:
            Deserialized CoChemError (or subclass) instance.

        Raises:
            ValueError: If the JSON payload is not a valid dictionary object.
        """
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        return cls.from_dict(data)

    def __reduce__(self) -> Tuple[Any, Tuple[Any, ...]]:
        """Pickle serialization helper for multiprocessing compatibility.

        Preserves class identity, message, error_code, details, and timestamp
        across process boundaries without redundant formatting prefixes.

        Returns:
            Tuple of (reconstructor_callable, args_tuple).
        """
        return (
            _reconstruct_cochem_error,
            (
                self.__class__,
                self.message,
                self.error_code,
                self.details,
                self.timestamp,
            ),
        )


# Register base error in registry
_EXCEPTION_REGISTRY["CoChemError"] = CoChemError

# Backwards compatibility alias
CoChemBaseError = CoChemError
_EXCEPTION_REGISTRY["CoChemBaseError"] = CoChemError


# =====================================================================
# Provenance & Method Matrix Exceptions
# =====================================================================

class ProvenanceError(CoChemError):
    """Base error for provenance tracking and Method Matrix compliance violations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = None


class MethodMatrixViolationError(ProvenanceError):
    """Raised when a calculation violates Method Matrix standards (e.g. DEFGRID, unsupported functionals)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID
    )


class ExceptionDeflectionBlockedError(ProvenanceError):
    """Raised when an attempt to deflect or silently suppress an exception is detected and blocked."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.EXCEPTION_DEFLECTION_BLOCKED
    )


class AntiSpoofingViolationError(ProvenanceError):
    """Raised when audit trail or telemetry spoofing / tampering is detected."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class MissingDataError(ProvenanceError, KeyError):
    """Raised when required provenance, basis set, or calculation dataset is missing."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = ProvenanceErrorCode.MISSING_DATA


class FrozenMonomerViolationError(MethodMatrixViolationError):
    """Raised when frozen monomer constraints or coordinates are improperly modified."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.FROZEN_MONOMER_VIOLATION
    )


class UnsupportedMethodError(MethodMatrixViolationError):
    """Raised when an unsupported quantum chemistry method, functional, or basis set is requested."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.UNSUPPORTED_METHOD
    )


class TriagePathologyError(ProvenanceError):
    """Raised when automated triage encounters geometric pathology or severe steric clashes."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PATHOLOGY_CLASH
    )


class BSSECorrectionError(MethodMatrixViolationError):
    """Raised when counterpoise or basis set superposition error (BSSE) correction fails or is inconsistent."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.BSSE_CORRECTION_FAILED
    )


# =====================================================================
# Infrastructure & Storage Exceptions
# =====================================================================

class HDF5LockTimeoutError(CoChemError, TimeoutError):
    """Raised when acquiring an HDF5 SWMR file lock times out."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT
    )


class RegistryLockError(CoChemError, TimeoutError):
    """Raised when registry lock acquisition or release times out or fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.REGISTRY_LOCK_TIMEOUT
    )


class SecurityIntegrityError(CoChemError, PermissionError):
    """Raised for security and integrity validation failures (e.g. checksum mismatch, unauthorized access)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INTEGRITY_VIOLATION
    )


class ConfigError(CoChemError, ValueError):
    """Raised when configuration loading, schema validation, or parsing fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONFIG_VALIDATION_FAILED
    )


class PathTraversalError(SecurityIntegrityError):
    """Raised when path traversal attacks or directory escape attempts are detected."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
    )


class TelemetryTransportError(CoChemError, ConnectionError):
    """Raised when telemetry transport fails to send/receive metric packets or socket fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.TELEMETRY_FAILURE
    )


class QCSchemaValidationError(ConfigError):
    """Raised when QCSchema input/output topology, molecule, or wave function fails validation."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.QCSCHEMA_VALIDATION_FAILED
    )


class DiskQuotaError(CoChemError, OSError):
    """Raised when available disk space in Scratch or workspace is below the required threshold."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.DISK_QUOTA_EXCEEDED
    )

    def __init__(
        self,
        message: Optional[Union[str, float]] = None,
        error_code: Optional[Union[ProvenanceErrorCode, str]] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        *,
        required_gb: Optional[float] = None,
        available_gb: Optional[float] = None,
        path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> None:
        merged_details: Dict[str, Any] = dict(details) if details is not None else {}

        if isinstance(message, (int, float)) and required_gb is None:
            required_gb = float(message)
            msg_val = None
        else:
            msg_val = str(message) if message is not None else None

        req = required_gb if required_gb is not None else merged_details.get("required_gb", 50.0)
        avail = available_gb if available_gb is not None else merged_details.get("available_gb", 0.0)
        p = path if path is not None else merged_details.get("path")

        self.required_gb: float = float(req) if req is not None else 50.0
        self.available_gb: float = float(avail) if avail is not None else 0.0
        self.path: Optional[Union[str, Path]] = Path(p) if isinstance(p, (str, Path)) else None

        merged_details["required_gb"] = self.required_gb
        merged_details["available_gb"] = self.available_gb
        if self.path is not None:
            merged_details["path"] = str(self.path)

        if msg_val is None:
            p_str = str(self.path) if self.path is not None else "workspace"
            msg = (
                f"Insufficient scratch disk quota at {p_str}: "
                f"required {self.required_gb:.2f} GB, available {self.available_gb:.2f} GB"
            )
        else:
            msg = msg_val

        super().__init__(
            message=msg,
            error_code=error_code if error_code is not None else self.default_error_code,
            details=merged_details,
            timestamp=timestamp,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["required_gb"] = self.required_gb
        d["available_gb"] = self.available_gb
        d["path"] = str(self.path) if self.path is not None else None
        return d


# =====================================================================
# Engine & Math Exceptions
# =====================================================================

class ConvergenceError(CoChemError, RuntimeError):
    """Raised when SCF, geometry optimization, or numerical convergence fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.CONVERGENCE_FAILURE
    )


class SpinContaminationError(CoChemError, ValueError):
    """Raised when <S^2> spin contamination exceeds allowed thresholds for open-shell calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPIN_CONTAMINATION_EXCEEDED
    )


class DispersionMissingError(MethodMatrixViolationError):
    """Raised when required dispersion correction (e.g. D3BJ, D4) is omitted in DFT calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.DISPERSION_MISSING
    )


class InvalidHessianStrategyError(CoChemError, ValueError):
    """Raised when an invalid Hessian strategy is specified for frequency or transition state calculations."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY
    )


class SingularityError(CoChemError, ValueError):
    """Raised when numerical matrix singularity or ill-conditioned linear algebra operations occur."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SINGULARITY_DETECTED
    )


class OutOfMemoryGateError(CoChemError, MemoryError):
    """Raised when pre-flight memory gating predicts insufficient RAM/VRAM for a calculation."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.OUT_OF_MEMORY
    )


class HardwareDetectionError(CoChemError, RuntimeError):
    """Raised when CPU/GPU/accelerator hardware topology detection fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.HARDWARE_DETECTION_FAILED
    )


class DispatcherError(CoChemError, RuntimeError):
    """Raised when calculation engine dispatch, executable resolution, or job execution fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.UNSUPPORTED_METHOD
    )


class CoChemPrecisionError(ProvenanceError):
    """Raised when JAX or numerical float precision is violated (e.g. non-float64 execution or precision downgrade)."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.PRECISION_VIOLATION
    )


class LAMTriggerError(CoChemError):
    """Raised when a fundamental vibrational frequency is below 50 cm^-1, triggering Phase 7 DVR solvers."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.LAM_TRIGGER
    )


class FortranOverflowError(CoChemError, ValueError):
    """Raised when a parameter value exceeds Double Precision limits (|val| > 1e308) for SPCAT."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.FORTRAN_OVERFLOW
    )


class SPCATBridgeError(CoChemError):
    """Raised when SPCAT formatting, parameter validation, or .var/.int file generation fails."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.SPCAT_BRIDGE_ERROR
    )


class AirGapViolationError(CoChemError, PermissionError):
    """Raised when runtime code attempts to write scratch/log artifacts into Ring 1 static repository."""

    default_error_code: Optional[Union[ProvenanceErrorCode, str]] = (
        ProvenanceErrorCode.AIRGAP_VIOLATION
    )


# =====================================================================
# Warnings
# =====================================================================

class CoChemWarning(UserWarning):
    """Base warning category for the CoChem ecosystem."""

    pass


class MethodMatrixWarning(CoChemWarning):
    """Issued when a calculation configuration deviates from Method Matrix recommendations but is non-fatal."""

    pass


class ConvergenceWarning(CoChemWarning):
    """Issued when numerical convergence is slow, oscillatory, or near the threshold limit."""

    pass


class CoChemDeprecationWarning(CoChemWarning, DeprecationWarning):
    """Issued when deprecated features, APIs, or legacy configuration options are accessed."""

    pass


class HardwareWarning(CoChemWarning):
    """Issued when hardware topology, memory headroom, or acceleration features are degraded."""

    pass


class SecurityWarning(CoChemWarning):
    """Issued for non-fatal security boundary, path sanitization, or permission concerns."""

    pass


# =====================================================================
# Utilities, Boundaries, and Decorators
# =====================================================================

def wrap_exception(
    exc: BaseException,
    target_cls: Type[CoChemError] = CoChemError,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> CoChemError:
    """Wrap an existing exception into a CoChemError subclass, chaining cause and preserving context.

    Args:
        exc: The original exception to wrap.
        target_cls: The destination CoChemError subclass (defaults to CoChemError).
        default_code: Fallback error code if the original exception does not have one.
        message: Optional custom message override. If None, inherits str(exc).
        details: Optional additional metadata dictionary to merge.

    Returns:
        An instance of target_cls chained to exc via __cause__.
    """
    if isinstance(exc, target_cls) and message is None and default_code is None and details is None:
        return exc

    extracted_code = getattr(exc, "error_code", default_code)
    extracted_details: Dict[str, Any] = {}
    exc_details = getattr(exc, "details", None)
    if isinstance(exc_details, dict):
        extracted_details.update(exc_details)
    if details:
        extracted_details.update(details)

    msg = message if message is not None else str(exc)
    code = default_code if default_code is not None else extracted_code

    wrapped = target_cls(
        message=msg,
        error_code=code,
        details=extracted_details if extracted_details else None,
    )
    wrapped.__cause__ = exc
    return wrapped


@contextmanager
def cochem_error_boundary(
    target_cls: Type[CoChemError] = CoChemError,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
) -> Iterator[None]:
    """Context manager boundary that catches exceptions and wraps them into CoChemError.

    Args:
        target_cls: Target CoChemError subclass to wrap into.
        default_code: Fallback error code if the original exception lacks one.
        message: Optional custom message override.
        details: Optional additional metadata dictionary to attach.
        reraise: If True, raises the wrapped exception; if False, suppresses it.
        exclude: Optional exception class or tuple of classes to exclude from wrapping.

    Yields:
        None

    Raises:
        CoChemError: The wrapped exception if reraise is True and an exception was caught.
    """
    try:
        yield
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise
        if exclude is not None and isinstance(exc, exclude):
            raise
        wrapped = wrap_exception(
            exc=exc,
            target_cls=target_cls,
            default_code=default_code,
            message=message,
            details=details,
        )
        if reraise:
            raise wrapped from exc


F = TypeVar("F", bound=Callable[..., Any])


@overload
def cochem_error_handler(
    target_cls_or_fn: Type[CoChemError],
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Callable[[F], F]:
    ...


@overload
def cochem_error_handler(
    target_cls_or_fn: None = None,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Callable[[F], F]:
    ...


@overload
def cochem_error_handler(
    target_cls_or_fn: F,
) -> F:
    ...


def cochem_error_handler(
    target_cls_or_fn: Optional[Union[Type[CoChemError], Callable[..., Any]]] = None,
    default_code: Optional[Union[ProvenanceErrorCode, str]] = None,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reraise: bool = True,
    exclude: Optional[Union[Type[BaseException], Tuple[Type[BaseException], ...]]] = None,
    *,
    target_cls: Optional[Type[CoChemError]] = None,
) -> Any:
    """Decorator to wrap function executions inside a CoChem error boundary.

    Supports both synchronous functions and asynchronous coroutine functions.
    Can be used with or without arguments:
        @cochem_error_handler
        def my_func(): ...

        @cochem_error_handler(target_cls=ConvergenceError)
        def my_func(): ...

        @cochem_error_handler(ConvergenceError)
        def my_func(): ...

        @cochem_error_handler(reraise=False)
        def my_func(): ...

    Args:
        target_cls_or_fn: Target CoChemError subclass to wrap into, or decorated function if bare decorator.
        default_code: Fallback error code if an unhandled exception is raised.
        message: Optional custom error message override.
        details: Optional additional structured metadata to attach.
        reraise: If True (default), re-raises wrapped CoChemError; if False, returns None on failure.
        exclude: Optional exception class or tuple of classes to bypass wrapping.
        target_cls: Keyword-only alias for target CoChemError subclass.

    Returns:
        Decorated function or decorator callable.
    """
    if callable(target_cls_or_fn) and not (
        isinstance(target_cls_or_fn, type) and issubclass(target_cls_or_fn, CoChemError)
    ):
        # Bare decorator usage: @cochem_error_handler
        bare_fn = cast(Callable[..., Any], target_cls_or_fn)
        effective_target_cls: Type[CoChemError] = target_cls or CoChemError

        if asyncio.iscoroutinefunction(bare_fn):

            @functools.wraps(bare_fn)
            async def async_bare_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_target_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return await bare_fn(*args, **kwargs)

            return cast(Any, async_bare_wrapper)
        else:

            @functools.wraps(bare_fn)
            def sync_bare_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_target_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return bare_fn(*args, **kwargs)

            return cast(Any, sync_bare_wrapper)

    if target_cls is not None:
        effective_cls = target_cls
    elif isinstance(target_cls_or_fn, type) and issubclass(target_cls_or_fn, CoChemError):
        effective_cls = target_cls_or_fn
    else:
        effective_cls = CoChemError

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                with cochem_error_boundary(
                    target_cls=effective_cls,
                    default_code=default_code,
                    message=message,
                    details=details,
                    reraise=reraise,
                    exclude=exclude,
                ):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


__all__ = [
    # Registries
    "_EXCEPTION_REGISTRY",
    # Error Codes
    "ProvenanceErrorCode",
    # Root Exceptions
    "CoChemError",
    "CoChemBaseError",
    # Provenance & Method Matrix Exceptions
    "ProvenanceError",
    "MethodMatrixViolationError",
    "ExceptionDeflectionBlockedError",
    "AntiSpoofingViolationError",
    "MissingDataError",
    "FrozenMonomerViolationError",
    "UnsupportedMethodError",
    "TriagePathologyError",
    "BSSECorrectionError",
    # Infrastructure & Storage Exceptions
    "HDF5LockTimeoutError",
    "RegistryLockError",
    "SecurityIntegrityError",
    "ConfigError",
    "PathTraversalError",
    "TelemetryTransportError",
    "QCSchemaValidationError",
    "DiskQuotaError",
    # Engine & Math Exceptions
    "ConvergenceError",
    "SpinContaminationError",
    "DispersionMissingError",
    "InvalidHessianStrategyError",
    "SingularityError",
    "OutOfMemoryGateError",
    "HardwareDetectionError",
    "DispatcherError",
    "CoChemPrecisionError",
    "LAMTriggerError",
    "FortranOverflowError",
    "SPCATBridgeError",
    "AirGapViolationError",
    # Warnings
    "CoChemWarning",
    "MethodMatrixWarning",
    "ConvergenceWarning",
    "CoChemDeprecationWarning",
    "HardwareWarning",
    "SecurityWarning",
    # Utilities, Boundaries, Decorators, and Serialization Helpers
    "format_error_message",
    "format_warning_message",
    "wrap_exception",
    "cochem_error_boundary",
    "cochem_error_handler",
    "_reconstruct_cochem_error",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\cochem_spcat_bridge.py ---
"""Re-export module for cochem_spcat_bridge within the cochem_base package hierarchy."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure root path is accessible
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cochem_spcat_bridge import (  # noqa: E402
    CODATA2022,
    CONSTANTS,
    PICKETT_PARAMETER_CODES,
    PartitionFunctionResult,
    SPCATParameter,
    SPCATPayload,
    SymmetryDivisorResult,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    compute_coupled_partition_functions,
    compute_sha256,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_provenance_manifest,
    generate_spcat_var,
    low_frequency_lam_trap,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

__all__ = [
    "CODATA2022",
    "CONSTANTS",
    "SymmetryDivisorResult",
    "PartitionFunctionResult",
    "SPCATParameter",
    "SPCATPayload",
    "PICKETT_PARAMETER_CODES",
    "low_frequency_lam_trap",
    "apply_symmetry_divisors",
    "calculate_rotational_partition_function",
    "calculate_vibrational_partition_function",
    "vibrational_partition_coupling",
    "compute_coupled_partition_functions",
    "fortran_overflow_guard",
    "format_fortran_double",
    "fortran_double_precision_formatter",
    "generate_spcat_var",
    "generate_spcat_int",
    "validate_airgap_boundary",
    "compute_sha256",
    "generate_spcat_provenance_manifest",
    "build_complete_spcat_payload",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_spcat_bridge.py ---
"""Stage 5.1: Statistical Mechanics & Pickett SPCAT Bridge.

Authoritative Module for CoChem-BASE / CoChem-TORQ (Phase 8 / Stage 5.1).
Implements the mathematical statistical mechanics translation layer and rigid
Fortran-77 ASCII parameter generators (.var and .int) for Pickett's SPCAT/SPFIT suite.

Key Capabilities:
1. Exact CODATA 2022 fundamental physical constants for all thermodynamic and rotational formulations.
2. Low-frequency Large Amplitude Motion (LAM) trap (< 50 cm^-1) requiring Phase 7 DVR solvers.
3. MolSym point-group symmetry resolver, rotational symmetry numbers (sigma),
   and nuclear spin statistical weights (e.g. H2O ortho/para 3:1 ratio).
4. Strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin statistical weights.
5. Vibrational partition coupling across temperature gradients with automatic LAM mode dropping.
6. Double Precision Fortran overflow guard (|val| > 1e308) blocking corrupt VPT2 parameters.
7. Rigid character alignment and 'D' exponent formatting for Pickett's ASCII files (.var / .int).
8. Tripartite Filesystem Air-Gap compliance and SHA-256 cryptographic provenance manifests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    import molsym  # type: ignore[import-untyped]

    _MOLSYM_AVAILABLE = True
except ImportError:
    _MOLSYM_AVAILABLE = False

from cochem_base.config_loader import (
    get_base_root,
    get_repo_root,
)
from cochem_base.exceptions import (
    AirGapViolationError,
    FortranOverflowError,
    LAMTriggerError,
    ProvenanceErrorCode,
    SPCATBridgeError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. Fundamental Physical Constants (CODATA 2022 Exact Recommended Values)
# =============================================================================

@dataclass(frozen=True)
class CODATA2022:
    """Exact fundamental physical constants from CODATA 2022 recommended values."""

    # Planck constant (exact, SI definition 2019) [J * s]
    H: float = 6.62607015e-34
    # Boltzmann constant (exact, SI definition 2019) [J * K^-1]
    K_B: float = 1.380649e-23
    # Speed of light in vacuum (exact) [m * s^-1]
    C_M_S: float = 299792458.0
    # Speed of light in vacuum (exact) [cm * s^-1]
    C_CM_S: float = 29979245800.0
    # Rotational constant factor C_rot = h / (8 * pi^2) in [MHz * u * Angstrom^2]
    # h / (8 * pi^2 * u * 1e-20) * 1e-6 MHz = 505379.008435
    C_ROT: float = 505379.008435
    # Avogadro constant (exact) [mol^-1]
    N_A: float = 6.02214076e23
    # Atomic mass constant [kg]
    AMU_KG: float = 1.66053906660e-27
    # h * c / k_B conversion factor [K * cm]
    # (6.62607015e-34 * 29979245800.0) / 1.380649e-23 = 1.4387768775039336
    HC_OVER_KB: float = 1.4387768775039336
    # k_B / h factor for rotational partition function [Hz / K] = [s^-1 * K^-1]
    KB_OVER_H: float = 1.380649e-23 / 6.62607015e-34  # ~ 20836619124.62 Hz/K


CONSTANTS = CODATA2022()


# =============================================================================
# 2. Data Structures and Transfer Objects
# =============================================================================

@dataclass
class SymmetryDivisorResult:
    """Structured result of point-group symmetry resolution and spin weight assignment."""

    point_group: str
    sigma: int
    spin_statistical_weights: List[int]
    spin_weight_ratio_str: str
    effective_divisor: float
    guardrail_status: str
    equivalent_atom_groups: Dict[str, List[int]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to serializable dictionary."""
        return asdict(self)


@dataclass
class PartitionFunctionResult:
    """Structured internal partition function evaluation across a temperature grid."""

    temperatures: List[float]
    q_rot: Dict[float, float]
    q_vib: Dict[float, float]
    q_total: Dict[float, float]
    dropped_lam_frequencies: List[float] = field(default_factory=list)
    stiff_frequencies: List[float] = field(default_factory=list)
    is_dvr_coupled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to serializable dictionary."""
        return asdict(self)


@dataclass
class SPCATParameter:
    """Rigidly formatted parameter record for Pickett's SPCAT .var/.par file."""

    param_id: int
    value: float
    uncertainty: float
    label: str
    formatted_line: str


@dataclass
class SPCATPayload:
    """Complete package of SPCAT input files, cryptographic hashes, and provenance manifest."""

    molecule_name: str
    var_content: str
    int_contents: Dict[float, str]
    provenance_manifest: Dict[str, Any]
    sha256_var: str
    sha256_int: Dict[float, str]
    var_filepath: Optional[str] = None
    int_filepaths: Dict[float, str] = field(default_factory=dict)
    provenance_filepath: Optional[str] = None


# Point group to rotational symmetry number sigma mapping
_POINT_GROUP_SIGMAS: Dict[str, int] = {
    "C1": 1, "Cs": 1, "Ci": 1,
    "C2": 2, "C2v": 2, "C2h": 2,
    "C3": 3, "C3v": 3, "C3h": 3,
    "C4": 4, "C4v": 4, "C4h": 4,
    "C5": 5, "C5v": 5, "C5h": 5,
    "C6": 6, "C6v": 6, "C6h": 6,
    "D2": 4, "D2h": 4, "D2d": 4,
    "D3": 6, "D3h": 6, "D3d": 6,
    "D4": 8, "D4h": 8, "D4d": 8,
    "D5": 10, "D5h": 10, "D5d": 10,
    "D6": 12, "D6h": 12, "D6d": 12,
    "Td": 12, "Th": 12,
    "Oh": 24, "O": 24,
    "Ih": 60, "I": 60,
    "Cinfv": 1, "Dinfh": 2, "Kh": 1,
}


def _pg_to_sigma(pg: str) -> int:
    """Resolve rotational symmetry number sigma from Schoenflies point group string."""
    clean = pg.strip()
    return _POINT_GROUP_SIGMAS.get(clean, 1)


# =============================================================================
# 3. Low-Frequency LAM Trap (Physical Guardrail against RRHO Failure)
# =============================================================================

def low_frequency_lam_trap(
    harmonic_frequencies: Sequence[float],
    threshold_cm1: float = 50.0,
    zero_mode_cutoff: float = 1e-4,
) -> List[float]:
    """Trap vibrational normal mode frequencies below threshold (< 50 cm^-1).

    Under the Rigid-Rotor Harmonic-Oscillator (RRHO) approximation, low-frequency
    vibrational modes (< 50 cm^-1) correspond to Large Amplitude Motions (LAM)
    such as methyl internal rotation, ring puckering, or low-barrier torsion.
    Simple harmonic partition functions diverge and fail catastrophically for LAM.
    This guardrail intercepts these modes, raises a LAMTriggerError with
    LAM_TRIGGER error code, and demands execution of Phase 7 DVR solvers.

    Args:
        harmonic_frequencies: Sequence of vibrational normal mode frequencies (cm^-1).
        threshold_cm1: Critical LAM frequency threshold in cm^-1 (default: 50.0).
        zero_mode_cutoff: Tolerance below which modes are treated as zero/translational (default: 1e-4).

    Returns:
        Validated list of stiff vibrational frequencies (all >= threshold_cm1).

    Raises:
        LAMTriggerError: If any genuine vibrational mode is below threshold_cm1.
    """
    flagged_lam_modes: List[float] = []
    stiff_modes: List[float] = []

    for raw_freq in harmonic_frequencies:
        freq = float(raw_freq)
        # Skip pure zero / translational-rotational residual modes
        if abs(freq) <= zero_mode_cutoff:
            continue
        if freq < threshold_cm1:
            flagged_lam_modes.append(freq)
        else:
            stiff_modes.append(freq)

    if flagged_lam_modes:
        min_lam = min(flagged_lam_modes)
        error_msg = (
            f"LAM detected: vibrational frequency {min_lam:.2f} cm^-1 is below "
            f"threshold {threshold_cm1:.1f} cm^-1. Rigid-Rotor Harmonic-Oscillator (RRHO) "
            f"approximation is invalid. Phase 7 DVR solvers are physically required."
        )
        logger.warning("[LAM_TRIGGER] %s (Flagged modes: %s)", error_msg, flagged_lam_modes)
        raise LAMTriggerError(
            message=error_msg,
            error_code=ProvenanceErrorCode.LAM_TRIGGER,
            details={
                "flagged_frequencies": [float(f) for f in flagged_lam_modes],
                "threshold_cm1": float(threshold_cm1),
                "stiff_frequencies_count": len(stiff_modes),
                "total_frequencies_evaluated": len(harmonic_frequencies),
                "min_lam_frequency": float(min_lam),
            },
        )

    return stiff_modes


# =============================================================================
# 4. MolSym Symmetry Solver & Nuclear Spin Statistical Weights
# =============================================================================

def _resolve_nuclear_spin_ratio(
    point_group: str,
    symbols: Sequence[str],
    equivalent_groups: Dict[str, List[int]],
) -> Tuple[List[int], str]:
    """Derive nuclear spin statistical weights and ratio string from point group and equivalent atoms.

    Args:
        point_group: Schoenflies point group string (e.g. 'C2v', 'C3v', 'Cs', 'D2h').
        symbols: List of element symbols.
        equivalent_groups: Mapping of group label to atom indices.

    Returns:
        Tuple of (spin_statistical_weights_list, ratio_string e.g. '3 1').
    """
    pg_clean = point_group.strip()

    # Determine spin of equivalent hydrogen/halogen atoms
    h_indices: List[int] = [i for i, sym in enumerate(symbols) if sym.strip() in ("H", "1H")]

    if pg_clean in ("C2v", "C2", "C2h"):
        # For H2O, CH2O, H2S, etc. with 2 equivalent protons:
        # Ortho (symmetric, I_tot=1, wt=3) : Para (antisymmetric, I_tot=0, wt=1)
        if len(h_indices) >= 2:
            return [3, 1], "3 1"
        return [1, 1], "1 1"

    elif pg_clean in ("C3v", "C3", "D3h"):
        # For NH3, CH3X (3 equivalent protons, I = 1/2):
        # A1/A2 (ortho, I_tot=3/2, wt=4), E (para, I_tot=1/2, wt=2) -> ratio 4:2 = 2:1
        if len(h_indices) >= 3:
            return [4, 2], "2 1"
        return [1, 1], "1 1"

    elif pg_clean in ("D2h", "D2", "D2d"):
        # For Ethylene (C2H4, 4 protons):
        # 7 (B3u), 3 (Ag), 3 (B1g), 3 (B2u)
        if len(h_indices) >= 4:
            return [7, 3, 3, 3], "7 3 3 3"
        return [3, 1], "3 1"

    elif pg_clean in ("C1", "Cs", "Ci"):
        # Asymmetric / planar with no non-trivial rotational symmetry (sigma = 1)
        return [1], "1"

    elif pg_clean in ("Td", "Oh", "Ih"):
        if len(h_indices) >= 4:
            return [5, 2, 3], "5 2 3"
        return [1, 1, 1], "1 1 1"

    # Default fallback
    return [1], "1"


def apply_symmetry_divisors(
    geometry_array: Union[np.ndarray, Sequence[Sequence[float]], Sequence[float]],
    symbols: Optional[Sequence[str]] = None,
    use_nuclear_spin: bool = False,
    enforce_guardrail: bool = True,
) -> SymmetryDivisorResult:
    """Resolve molecular point group, rotational symmetry number (sigma), and nuclear spin weights.

    Interfaces with MolSym to identify Schoenflies point group (e.g. C2v for H2O),
    computes the rotational symmetry divisor sigma (e.g. sigma=2 for H2O), and assigns
    the nuclear spin statistical weights ratio (e.g. '3 1' for H2O ortho/para).

    Double-Counting Guardrail:
    Enforces a strict selection rule: apply EITHER the exact nuclear spin statistical
    weights OR the classical 1/sigma divisor to the partition function, but NEVER both
    simultaneously. Applying both would artificially deflate the state density twice,
    since exact nuclear spin weights already account for point-group symmetry.

    Args:
        geometry_array: Cartesian coordinates of atoms in Angstroms (shape N x 3 or flattened).
        symbols: List of atom element symbols (e.g. ['O', 'H', 'H']).
        use_nuclear_spin: If True, uses exact nuclear spin weights and sets effective_divisor=1.0.
        enforce_guardrail: If True, validates and enforces the double-counting selection rule.

    Returns:
        SymmetryDivisorResult containing point group, sigma, spin weights, ratio string,
        effective divisor, and guardrail status.

    Raises:
        SPCATBridgeError: If MolSym resolution or geometry parsing fails.
    """
    flat_coords: List[float] = []
    if isinstance(geometry_array, np.ndarray):
        flat_coords = [float(x) for x in geometry_array.flatten()]
    else:
        for item in geometry_array:
            if isinstance(item, (list, tuple, np.ndarray, Sequence)):
                for x in item:
                    flat_coords.append(float(x))
            else:
                flat_coords.append(float(item))

    if len(flat_coords) % 3 != 0:
        raise SPCATBridgeError(
            message=f"Invalid flattened coordinate size {len(flat_coords)}, must be multiple of 3",
            error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
        )

    coords_np = np.array(flat_coords).reshape(-1, 3)
    num_atoms = coords_np.shape[0]

    if symbols is None:
        symbols = ["X"] * num_atoms
    elif len(symbols) != num_atoms:
        raise SPCATBridgeError(
            message=f"Symbols length ({len(symbols)}) does not match atom count ({num_atoms})",
            error_code=ProvenanceErrorCode.SPCAT_BRIDGE_ERROR,
        )

    point_group = "C1"
    sigma = 1
    equivalent_groups: Dict[str, List[int]] = {}

    if _MOLSYM_AVAILABLE:
        try:
            schema = {
                "symbols": [str(s).strip() for s in symbols],
                "geometry": flat_coords,
            }
            mol = molsym.Molecule.from_schema(schema)
            try:
                sym = molsym.Symtext.from_molecule(mol)
                point_group = str(sym.pg).strip()
                sigma = int(sym.rotational_symmetry_number)
            except Exception:
                pg_info = molsym.find_point_group(mol)
                point_group = str(pg_info[0]).strip()
                sigma = _pg_to_sigma(point_group)

            # Extract symmetry equivalent atom sets
            try:
                seas = mol.find_SEAs()
                for idx, sea in enumerate(seas):
                    subset = [int(i) for i in getattr(sea, "subset", [])]
                    equivalent_groups[f"SEA_{idx}"] = subset
            except Exception as sea_err:
                logger.debug("MolSym find_SEAs non-fatal error: %s", sea_err)

        except Exception as err:
            logger.warning("MolSym analysis encountered exception: %s. Falling back to geometric solver.", err)
            point_group, sigma = _fallback_point_group_solver(coords_np, symbols)
    else:
        point_group, sigma = _fallback_point_group_solver(coords_np, symbols)

    spin_weights, ratio_str = _resolve_nuclear_spin_ratio(point_group, symbols, equivalent_groups)

    # Enforce Double-Counting Guardrail
    if use_nuclear_spin:
        effective_divisor = 1.0
        guardrail_status = "GUARDRAIL_ENFORCED_EXACT_NUCLEAR_SPIN_APPLIED_SIGMA_BYPASSED"
    else:
        effective_divisor = float(sigma)
        guardrail_status = "GUARDRAIL_ENFORCED_CLASSICAL_SIGMA_APPLIED"

    return SymmetryDivisorResult(
        point_group=point_group,
        sigma=sigma,
        spin_statistical_weights=spin_weights,
        spin_weight_ratio_str=ratio_str,
        effective_divisor=effective_divisor,
        guardrail_status=guardrail_status,
        equivalent_atom_groups=equivalent_groups,
        metadata={
            "num_atoms": num_atoms,
            "symbols": list(symbols),
            "use_nuclear_spin": bool(use_nuclear_spin),
            "enforce_guardrail": bool(enforce_guardrail),
        },
    )


def _fallback_point_group_solver(
    coords: np.ndarray, symbols: Sequence[str]
) -> Tuple[str, int]:
    """Fallback geometric symmetry analyzer when MolSym is unavailable or coordinates are approximate."""
    num_atoms = coords.shape[0]
    if num_atoms == 1:
        return "Kh", 1
    if num_atoms == 2:
        return ("Dinfh", 2) if symbols[0] == symbols[1] else ("Cinfv", 1)

    com = np.mean(coords, axis=0)
    centered = coords - com

    # Check for planar C2v geometry (e.g. H2O: 3 atoms, 2 identical)
    if num_atoms == 3:
        unique_syms = set(symbols)
        if len(unique_syms) == 2:
            sym_counts = {s: symbols.count(s) for s in unique_syms}
            eq_sym = [s for s, c in sym_counts.items() if c == 2][0]
            eq_indices = [i for i, s in enumerate(symbols) if s == eq_sym]
            d1 = float(np.sqrt(np.sum((centered[eq_indices[0]] - centered[[i for i in range(3) if i not in eq_indices][0]]) ** 2)))
            d2 = float(np.sqrt(np.sum((centered[eq_indices[1]] - centered[[i for i in range(3) if i not in eq_indices][0]]) ** 2)))
            if abs(d1 - d2) < 1e-2:
                return "C2v", 2

    # Check for pyramidal C3v geometry (e.g. NH3: 4 atoms, 3 identical)
    if num_atoms == 4:
        unique_syms = set(symbols)
        if len(unique_syms) == 2:
            sym_counts = {s: symbols.count(s) for s in unique_syms}
            eq_sym_list = [s for s, c in sym_counts.items() if c == 3]
            if eq_sym_list:
                eq_indices = [i for i, s in enumerate(symbols) if s == eq_sym_list[0]]
                d1 = float(np.sqrt(np.sum((centered[eq_indices[0]] - centered[eq_indices[1]]) ** 2)))
                d2 = float(np.sqrt(np.sum((centered[eq_indices[1]] - centered[eq_indices[2]]) ** 2)))
                d3 = float(np.sqrt(np.sum((centered[eq_indices[2]] - centered[eq_indices[0]]) ** 2)))
                if abs(d1 - d2) < 1e-2 and abs(d2 - d3) < 1e-2:
                    return "C3v", 3

    return "Cs", 1


# =============================================================================
# 5. Statistical Mechanics Partition Functions & Vibrational Coupling
# =============================================================================

def calculate_rotational_partition_function(
    a_mhz: float,
    b_mhz: float,
    c_mhz: float,
    temp_k: float,
    sigma: float = 1.0,
    is_linear: bool = False,
) -> float:
    """Calculate rotational partition function Q_rot(T) using exact CODATA 2022 constants.

    Formulations:
    - Asymmetric Top: Q_rot(T) = (sqrt(pi) / sigma) * (k_B * T / (h * 1e6))^(3/2) / sqrt(A * B * C)
    - Linear Rotor:   Q_rot(T) = (k_B * T) / (sigma * (h * 1e6) * B)

    Args:
        a_mhz: Rotational constant A in MHz.
        b_mhz: Rotational constant B in MHz.
        c_mhz: Rotational constant C in MHz.
        temp_k: Thermodynamic temperature in Kelvin.
        sigma: Rotational symmetry number (default: 1.0).
        is_linear: True if molecule is a linear rotor.

    Returns:
        Rotational partition function Q_rot(T) (dimensionless).
    """
    if temp_k <= 0.0:
        return 1.0

    sigma_eff = max(1.0, float(sigma))
    kb_over_h_mhz = CONSTANTS.K_B / (CONSTANTS.H * 1e6)

    if is_linear:
        b_eff = max(1e-12, float(b_mhz))
        return (kb_over_h_mhz * temp_k) / (sigma_eff * b_eff)

    a_eff = max(1e-12, float(a_mhz))
    b_eff = max(1e-12, float(b_mhz))
    c_eff = max(1e-12, float(c_mhz))

    factor = (kb_over_h_mhz * temp_k) ** 1.5
    abc_sqrt = math.sqrt(a_eff * b_eff * c_eff)
    q_rot = (math.sqrt(math.pi) / sigma_eff) * (factor / abc_sqrt)
    return float(q_rot)


def calculate_vibrational_partition_function(
    frequencies_cm1: Sequence[float],
    temp_k: float,
    exclude_frequencies: Optional[Sequence[float]] = None,
) -> float:
    """Calculate vibrational partition function Q_vib(T) referenced to ZPVE.

    Q_vib(T) = prod_{i, nu_i not in exclude} [ 1 / (1 - exp(- h * c * nu_i / (k_B * T))) ]

    Args:
        frequencies_cm1: Sequence of normal mode harmonic frequencies in cm^-1.
        temp_k: Thermodynamic temperature in Kelvin.
        exclude_frequencies: Frequencies to drop (e.g. LAM modes handled by DVR).

    Returns:
        Vibrational partition function Q_vib(T) (dimensionless).
    """
    if temp_k <= 0.0:
        return 1.0

    excluded_set: List[float] = [float(x) for x in exclude_frequencies] if exclude_frequencies else []
    q_vib = 1.0
    hc_over_kb = CONSTANTS.HC_OVER_KB  # ~ 1.4387768775 K*cm

    for raw_f in frequencies_cm1:
        f = float(raw_f)
        if f <= 0.0:
            continue
        if any(abs(f - excl) < 0.1 for excl in excluded_set):
            continue

        x = (hc_over_kb * f) / temp_k
        if x > 500.0:
            factor = 1.0
        else:
            exp_neg_x = math.exp(-x)
            factor = 1.0 / (1.0 - exp_neg_x)

        q_vib *= factor

    return float(q_vib)


def vibrational_partition_coupling(
    q_rot_dvr: Union[Dict[float, float], Sequence[float], float, Callable[[float], float]],
    q_vib_orca: Union[Dict[float, float], Sequence[float], np.ndarray, float],
    temp_array: Sequence[float],
    lam_frequency: Optional[float] = None,
    all_frequencies: Optional[Sequence[float]] = None,
) -> Dict[float, float]:
    """Compute total coupled internal partition function Q_total(T) = Q_vib(T) * Q_rot(T).

    When Phase 7 DVR rotational partition functions are coupled with ORCA harmonic
    frequencies, any identified LAM frequency (nu_lam < 50 cm^-1) is explicitly
    dropped from the Q_vib product to prevent thermodynamic double-counting.

    Args:
        q_rot_dvr: Precomputed DVR rotational partition function mapping {T: Q_rot},
                   callable f(T), list matching temp_array, or scalar.
        q_vib_orca: Precomputed Q_vib mapping {T: Q_vib}, list of harmonic frequencies (cm^-1),
                    or scalar.
        temp_array: Sequence of temperatures in Kelvin (e.g. [2.0, 10.0, 50.0, 298.15]).
        lam_frequency: Specific LAM mode frequency (cm^-1) to drop from Q_vib.
        all_frequencies: Full set of normal mode harmonic frequencies (cm^-1).

    Returns:
        Dictionary mapping temperature T -> Q_total(T).
    """
    results: Dict[float, float] = {}
    temps = [float(t) for t in temp_array]

    excluded: List[float] = []
    if lam_frequency is not None:
        excluded.append(float(lam_frequency))

    is_freq_list = False
    raw_freqs: List[float] = []
    if isinstance(q_vib_orca, (list, tuple, np.ndarray)):
        arr = np.array(q_vib_orca, dtype=float)
        if arr.ndim == 1 and arr.size > 0 and not isinstance(q_rot_dvr, (list, tuple, np.ndarray)):
            is_freq_list = True
            raw_freqs = [float(x) for x in arr]
    elif all_frequencies is not None:
        is_freq_list = True
        raw_freqs = [float(x) for x in all_frequencies]

    for idx, t in enumerate(temps):
        if callable(q_rot_dvr):
            q_rot_val = float(q_rot_dvr(t))
        elif isinstance(q_rot_dvr, dict):
            q_rot_val = float(q_rot_dvr.get(t, 1.0))
        elif isinstance(q_rot_dvr, (list, tuple, np.ndarray)):
            q_rot_val = float(q_rot_dvr[idx]) if idx < len(q_rot_dvr) else 1.0
        elif isinstance(q_rot_dvr, (int, float)):
            q_rot_val = float(q_rot_dvr)
        else:
            q_rot_val = 1.0

        if is_freq_list:
            q_vib_val = calculate_vibrational_partition_function(
                frequencies_cm1=raw_freqs,
                temp_k=t,
                exclude_frequencies=excluded,
            )
        elif isinstance(q_vib_orca, dict):
            q_vib_val = float(q_vib_orca.get(t, 1.0))
        elif isinstance(q_vib_orca, (list, tuple, np.ndarray)):
            q_vib_val = float(q_vib_orca[idx]) if idx < len(q_vib_orca) else 1.0
        elif isinstance(q_vib_orca, (int, float)):
            q_vib_val = float(q_vib_orca)
        else:
            q_vib_val = 1.0

        results[t] = float(q_rot_val * q_vib_val)

    return results


def compute_coupled_partition_functions(
    a_mhz: float,
    b_mhz: float,
    c_mhz: float,
    frequencies_cm1: Sequence[float],
    temp_array: Sequence[float],
    sigma: float = 1.0,
    lam_frequency: Optional[float] = None,
    is_dvr: bool = False,
) -> PartitionFunctionResult:
    """Compute complete coupled partition functions with metadata tracking."""
    temps = [float(t) for t in temp_array]
    q_rot_dict: Dict[float, float] = {}
    q_vib_dict: Dict[float, float] = {}
    q_total_dict: Dict[float, float] = {}

    excluded = [float(lam_frequency)] if lam_frequency is not None else []
    stiff = [f for f in frequencies_cm1 if not any(abs(f - ex) < 0.1 for ex in excluded)]

    for t in temps:
        q_r = calculate_rotational_partition_function(a_mhz, b_mhz, c_mhz, t, sigma=sigma)
        q_v = calculate_vibrational_partition_function(frequencies_cm1, t, exclude_frequencies=excluded)
        q_rot_dict[t] = q_r
        q_vib_dict[t] = q_v
        q_total_dict[t] = q_r * q_v

    return PartitionFunctionResult(
        temperatures=temps,
        q_rot=q_rot_dict,
        q_vib=q_vib_dict,
        q_total=q_total_dict,
        dropped_lam_frequencies=excluded,
        stiff_frequencies=stiff,
        is_dvr_coupled=bool(is_dvr),
    )


# =============================================================================
# 6. Fortran Overflow Guard
# =============================================================================

def fortran_overflow_guard(
    tensor_dictionary: Union[Dict[str, Any], Sequence[Any], float, int, np.ndarray],
    max_limit: float = 1e308,
    clamp_on_overflow: bool = False,
) -> Any:
    """Trap values exceeding Double Precision mathematical ceilings (|val| > 1e308).

    Un-deperturbed resonances from VPT2 or divergent perturbation calculations can
    yield wildly oscillating constants that exceed Fortran REAL*8 limits (~10^308),
    causing SPCAT to crash or emit 'NON-POSITIVE DEFINITE' matrix errors.
    This guard actively scans incoming parameter tensors, logs a CRITICAL warning,
    and raises FortranOverflowError to block corrupted parameters.

    Args:
        tensor_dictionary: Dictionary, nested list, array, or scalar of parameters.
        max_limit: Hard double precision magnitude limit (default: 1e308).
        clamp_on_overflow: If True, clamps value to +/- max_limit instead of raising.

    Returns:
        Validated (and optionally clamped) data structure.

    Raises:
        FortranOverflowError: If any value exceeds max_limit and clamp_on_overflow is False.
    """
    def _inspect_and_guard(val: Any, path: str) -> Any:
        if isinstance(val, dict):
            return {k: _inspect_and_guard(v, f"{path}.{k}" if path else str(k)) for k, v in val.items()}
        elif isinstance(val, (list, tuple)):
            return [_inspect_and_guard(item, f"{path}[{i}]") for i, item in enumerate(val)]
        elif isinstance(val, np.ndarray):
            try:
                max_val = float(np.max(np.abs(val))) if val.size > 0 else 0.0
                if max_val > max_limit or math.isinf(max_val) or math.isnan(max_val):
                    msg = (
                        f"CRITICAL: Fortran Double Precision overflow detected in array '{path}': "
                        f"max magnitude {max_val} exceeds limit {max_limit:.1e}"
                    )
                    logger.critical("[FORTRAN_OVERFLOW] %s", msg)
                    if clamp_on_overflow:
                        return np.clip(val, -max_limit, max_limit)
                    raise FortranOverflowError(
                        message=msg,
                        error_code=ProvenanceErrorCode.FORTRAN_OVERFLOW,
                        details={"path": path, "max_magnitude": float(max_val), "limit": float(max_limit)},
                    )
            except (TypeError, ValueError):
                pass
            return val
        elif isinstance(val, (int, float)):
            fval = float(val)
            if math.isinf(fval) or math.isnan(fval) or abs(fval) > max_limit:
                msg = (
                    f"CRITICAL: Fortran Double Precision overflow detected for parameter '{path}': "
                    f"value {fval} exceeds hard limit {max_limit:.1e}"
                )
                logger.critical("[FORTRAN_OVERFLOW] %s", msg)
                if clamp_on_overflow:
                    return math.copysign(max_limit, fval) if not math.isnan(fval) else 0.0
                raise FortranOverflowError(
                    message=msg,
                    error_code=ProvenanceErrorCode.FORTRAN_OVERFLOW,
                    details={"parameter": path, "value": str(val), "limit": float(max_limit)},
                )
            return val
        return val

    return _inspect_and_guard(tensor_dictionary, "")


# =============================================================================
# 7. Fortran Double Precision Formatter & Alignment Engine
# =============================================================================

def format_fortran_double(
    val: float,
    width: int = 22,
    precision: int = 15,
    compact: bool = False,
) -> str:
    """Convert a Python float into strict Fortran Double Precision scientific notation ('D').

    Examples:
        1.567e-05 -> '1.567D-05' (compact) or ' 1.567000000000000D-05' (fixed width).

    Args:
        val: Numerical float value.
        width: Field width for right alignment (ignored if compact=True).
        precision: Decimal precision in mantissa.
        compact: If True, returns minimal scientific representation without trailing zeros.

    Returns:
        Formatted Fortran Double Precision string.
    """
    fval = float(val)
    if fval == 0.0:
        base = "0.000D+00" if compact else f"0.{'0' * precision}D+00"
        return base if compact else f"{base:>{width}}"

    sci_str = f"{fval:.{precision}e}"
    if "e" in sci_str or "E" in sci_str:
        mantissa, exponent = sci_str.replace("E", "e").split("e")
        exp_int = int(exponent)
        exp_sign = "+" if exp_int >= 0 else "-"
        exp_formatted = f"{exp_sign}{abs(exp_int):02d}"
        if compact:
            parts = mantissa.split(".")
            if len(parts) == 2:
                dec = parts[1].rstrip("0")
                if len(dec) < 3:
                    dec = dec.ljust(3, "0")
                mantissa = f"{parts[0]}.{dec}"
            return f"{mantissa}D{exp_formatted}"
        else:
            return f"{f'{mantissa}D{exp_formatted}':>{width}}"

    formatted = f"{sci_str}".replace("e", "D").replace("E", "D")
    return formatted if compact else f"{formatted:>{width}}"


def fortran_double_precision_formatter(
    val_or_id: Any,
    val: Optional[float] = None,
    uncertainty: float = 0.0,
    label: str = "",
    width: int = 22,
    precision: int = 15,
    compact: bool = False,
) -> Union[str, List[str]]:
    """Format single floats, parameter lines, or parameter dictionaries into Pickett Fortran strings.

    Signatures supported:
    1. Single float value:
       `fortran_double_precision_formatter(0.00001567)` -> `'1.567D-05'`
    2. Parameter line:
       `fortran_double_precision_formatter(20000, 0.00001567, uncertainty=1e-7, label="DJ")`
       -> `'     20000   1.567000000000000D-05   1.000000000000000D-07  / DJ'`
    3. Dictionary of parameters:
       `fortran_double_precision_formatter({'20000': 1.567e-5, '10000': 435360.0})` -> list of lines

    Args:
        val_or_id: Numerical float value, integer parameter ID (e.g. 20000), or parameter dict.
        val: Parameter value when val_or_id is a parameter ID.
        uncertainty: Estimated uncertainty in MHz (default: 0.0).
        label: Descriptive comment label (e.g. 'DJ', 'A').
        width: Column width for numbers (default: 22).
        precision: Mantissa precision (default: 15).
        compact: If True, uses compact scientific notation (e.g. '1.567D-05').

    Returns:
        Formatted Fortran string or list of formatted lines.
    """
    if isinstance(val_or_id, dict):
        lines: List[str] = []
        for p_id, p_val in val_or_id.items():
            if isinstance(p_val, (tuple, list)):
                p_v = float(p_val[0])
                p_u = float(p_val[1]) if len(p_val) > 1 else 0.0
                p_lbl = str(p_val[2]) if len(p_val) > 2 else ""
            else:
                p_v = float(p_val)
                p_u = 0.0
                p_lbl = ""
            line = fortran_double_precision_formatter(
                val_or_id=p_id,
                val=p_v,
                uncertainty=p_u,
                label=p_lbl,
                width=width,
                precision=precision,
                compact=compact,
            )
            lines.append(str(line))
        return lines

    if val is not None:
        param_id_int = int(val_or_id)
        val_str = format_fortran_double(val, width=width, precision=precision, compact=compact)
        unc_str = format_fortran_double(uncertainty, width=width, precision=precision, compact=compact)
        lbl_part = f"  / {label}" if label else ""
        return f"{param_id_int:>10}  {val_str}  {unc_str}{lbl_part}"

    if isinstance(val_or_id, (int, float)):
        return format_fortran_double(float(val_or_id), width=width, precision=precision, compact=compact)

    return str(val_or_id)


# =============================================================================
# 8. Pickett SPCAT .var and .int ASCII Generation
# =============================================================================

PICKETT_PARAMETER_CODES: Dict[str, int] = {
    "B_C_AVG": 10000,
    "B_MINUS_C": 30000,
    "A_REDUCED": 20000,
    "A": 20000,
    "B": 10000,
    "C": 30000,
    "DJ": 200,
    "DJK": 1100,
    "DK": 2000,
    "d1": 40100,
    "d2": 41000,
    "DELTA_J": 200,
    "DELTA_JK": 1100,
    "DELTA_K": 2000,
    "delta_j": 40100,
    "delta_k": 41000,
}


def generate_spcat_var(
    molecule_name: str,
    parameters: Dict[str, Any],
    title: Optional[str] = None,
    nopt: int = 0,
    nwarn: int = 0,
    erpar: float = 1.0,
    wtfac: float = 1.0,
    scale: float = 1.0,
    maxit: int = 50,
    filepath: Optional[Union[str, Path]] = None,
) -> str:
    """Generate exact Pickett SPCAT .var ASCII parameter file content."""
    guarded_params = fortran_overflow_guard(parameters)

    title_str = title if title else f"{molecule_name} Ground State - CoChem SPCAT Bridge"

    param_records: List[SPCATParameter] = []
    for key, val in guarded_params.items():
        if isinstance(val, (tuple, list)):
            v = float(val[0])
            u = float(val[1]) if len(val) > 1 else 1e-4
            lbl = str(val[2]) if len(val) > 2 else str(key)
        else:
            v = float(val)
            u = 1e-4
            lbl = str(key)

        if str(key).isdigit():
            p_id = int(key)
        elif key in PICKETT_PARAMETER_CODES:
            p_id = PICKETT_PARAMETER_CODES[key]
        else:
            p_id = 10000

        line_str = fortran_double_precision_formatter(
            val_or_id=p_id,
            val=v,
            uncertainty=u,
            label=lbl,
            width=22,
            precision=15,
            compact=False,
        )
        param_records.append(SPCATParameter(p_id, v, u, lbl, str(line_str)))

    npar = len(param_records)
    nline = 100

    erpar_str = format_fortran_double(erpar, width=22, precision=15)
    wtfac_str = format_fortran_double(wtfac, width=22, precision=15)
    scale_str = format_fortran_double(scale, width=22, precision=15)

    control_line = f"{npar:>4}{nline:>6}{nopt:>5}{nwarn:>5}  {erpar_str}  {wtfac_str}  {scale_str}{maxit:>5}"

    var_lines = [title_str, control_line]
    for p in param_records:
        var_lines.append(p.formatted_line)

    content = "\n".join(var_lines) + "\n"

    if filepath is not None:
        target = Path(filepath).resolve()
        validate_airgap_boundary(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target.with_suffix(f".tmp_{os.getpid()}_{int(datetime.now().timestamp())}")
        temp_file.write_text(content, encoding="utf-8")
        temp_file.replace(target)

    return content


def generate_spcat_int(
    molecule_name: str,
    dipoles: Union[Dict[str, float], Sequence[float]],
    temperatures: Union[float, Sequence[float]] = 298.15,
    tag: int = 1,
    ver: int = 1,
    ibx: int = 0,
    nq: int = 0,
    rrot: float = 0.0,
    tem: float = 0.0,
    sthk: float = 0.0,
    wtk: float = 0.0,
    title: Optional[str] = None,
    filepath_template: Optional[Union[str, Path]] = None,
) -> Dict[float, str]:
    """Generate exact Pickett SPCAT .int ASCII intensity files for target temperatures."""
    temps = [float(temperatures)] if isinstance(temperatures, (int, float)) else [float(t) for t in temperatures]

    if isinstance(dipoles, dict):
        mu_a = float(dipoles.get("mu_a", dipoles.get("a", dipoles.get("mua", 0.0))))
        mu_b = float(dipoles.get("mu_b", dipoles.get("b", dipoles.get("mub", 0.0))))
        mu_c = float(dipoles.get("mu_c", dipoles.get("c", dipoles.get("muc", 0.0))))
    else:
        d_list = [float(x) for x in dipoles]
        mu_a = d_list[0] if len(d_list) > 0 else 0.0
        mu_b = d_list[1] if len(d_list) > 1 else 0.0
        mu_c = d_list[2] if len(d_list) > 2 else 0.0

    fortran_overflow_guard({"mu_a": mu_a, "mu_b": mu_b, "mu_c": mu_c})

    results: Dict[float, str] = {}

    for t in temps:
        title_str = title if title else f"{molecule_name} Ground State - CoChem SPCAT Bridge (T={t:.2f}K)"

        control_line = (
            f"{tag:>3}{ver:>3}{ibx:>3}{nq:>3}"
            f"  {rrot:>6.1f}  {tem:>6.1f}  {sthk:>6.1f}  {wtk:>6.1f}  {t:>8.2f}"
        )

        int_lines = [
            title_str,
            control_line,
            f"  1  {mu_a:>12.6f}   / mua",
            f"  2  {mu_b:>12.6f}   / mub",
            f"  3  {mu_c:>12.6f}   / muc",
        ]

        content = "\n".join(int_lines) + "\n"
        results[t] = content

        if filepath_template is not None:
            path_str = str(filepath_template).format(T=f"{t:.1f}", temp=f"{t:.1f}", molecule=molecule_name)
            target = Path(path_str).resolve()
            validate_airgap_boundary(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_file = target.with_suffix(f".tmp_{os.getpid()}_{int(datetime.now().timestamp())}")
            temp_file.write_text(content, encoding="utf-8")
            temp_file.replace(target)

    return results


# =============================================================================
# 9. Tripartite Filesystem Air-Gap & Cryptographic Provenance Manifest
# =============================================================================

def validate_airgap_boundary(target_path: Union[str, Path]) -> Path:
    """Validate that target output path adheres to the Tripartite Air-Gap isolation boundary.

    Ring 1: Static Repository Root (Domain A) is read-only for runtime scratch/log files.
    Directly writing volatile simulation scratch files into Ring 1 static repository
    (outside authorized test/scratch directories) raises an AirGapViolationError.

    Args:
        target_path: Target filesystem path to validate.

    Returns:
        Resolved absolute Path.

    Raises:
        AirGapViolationError: If target attempts to write directly into protected Ring 1 static root.
    """
    resolved = Path(target_path).resolve()
    base_root = get_base_root().resolve()
    repo_root = get_repo_root().resolve()

    # Check if target is located within static execution boundaries
    for root_dir in (base_root, repo_root):
        try:
            rel = resolved.relative_to(root_dir)
            rel_parts = rel.parts
            if not rel_parts:
                continue
            # If target is within CoChem-BASE root
            if rel_parts[0] == "CoChem-BASE":
                sub_parts = rel_parts[1:]
            else:
                sub_parts = rel_parts

            if sub_parts and sub_parts[0] in ("test_suite", "tests", ".pytest_cache", "scratch"):
                return resolved

            raise AirGapViolationError(
                message=f"Air-Gap violation: forbidden write into Ring 1 static execution tier: {resolved}",
                error_code=ProvenanceErrorCode.AIRGAP_VIOLATION,
                details={
                    "path": str(resolved),
                    "ring": "Ring 1 (Domain A)",
                    "base_root": str(base_root),
                    "repo_root": str(repo_root),
                },
            )
        except ValueError:
            pass

    return resolved


def compute_sha256(content: Union[str, bytes]) -> str:
    """Compute deterministic SHA-256 hexadecimal hash string."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def generate_spcat_provenance_manifest(
    molecule_name: str,
    var_content: str,
    int_contents: Dict[float, str],
    symmetry_result: SymmetryDivisorResult,
    partition_results: Dict[float, float],
    output_path: Optional[Union[str, Path]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate SHA-256 cryptographic provenance manifest for SPCAT execution package."""
    sha256_var = compute_sha256(var_content)
    sha256_int = {str(t): compute_sha256(c) for t, c in int_contents.items()}

    manifest: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "stage": "Stage 5.1 (Statistical Mechanics & SPCAT Bridge)",
        "molecule_name": molecule_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "codata_constants": {
            "h_j_s": CONSTANTS.H,
            "k_b_j_k": CONSTANTS.K_B,
            "c_cm_s": CONSTANTS.C_CM_S,
            "c_rot_mhz_u_ang2": CONSTANTS.C_ROT,
            "hc_over_kb_k_cm": CONSTANTS.HC_OVER_KB,
        },
        "symmetry": symmetry_result.to_dict(),
        "partition_functions": {str(k): v for k, v in partition_results.items()},
        "cryptographic_hashes": {
            "sha256_var": sha256_var,
            "sha256_int": sha256_int,
        },
        "airgap_rings": {
            "ring_1_domain_a": "Static Execution Tier (Read-Only Repo)",
            "ring_2_domain_c": "Ephemeral Scratch Tier (RAM-Disk /dev/shm)",
            "ring_3_domain_b": "Dynamic Artifact Vault ($COCHEM_ARTIFACTS_DIR)",
        },
        "metadata": extra_metadata if extra_metadata is not None else {},
    }

    if output_path is not None:
        target = Path(output_path).resolve()
        validate_airgap_boundary(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_file = target.with_suffix(f".tmp_{os.getpid()}_{int(datetime.now().timestamp())}")
        temp_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temp_file.replace(target)

    return manifest


def build_complete_spcat_payload(
    molecule_name: str,
    geometry: Union[np.ndarray, Sequence[Sequence[float]]],
    symbols: Sequence[str],
    rotational_constants_mhz: Dict[str, float],
    dipoles_debye: Dict[str, float],
    harmonic_frequencies_cm1: Sequence[float],
    temperatures: Sequence[float] = (2.0, 10.0, 50.0, 298.15),
    quartic_distortion: Optional[Dict[str, float]] = None,
    lam_frequency: Optional[float] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> SPCATPayload:
    """Build complete, fully validated, air-gapped SPCAT execution payload with provenance manifest."""
    sym_res = apply_symmetry_divisors(geometry_array=geometry, symbols=symbols)

    a = float(rotational_constants_mhz.get("A", 0.0))
    b = float(rotational_constants_mhz.get("B", 0.0))
    c = float(rotational_constants_mhz.get("C", 0.0))
    part_res = compute_coupled_partition_functions(
        a_mhz=a,
        b_mhz=b,
        c_mhz=c,
        frequencies_cm1=harmonic_frequencies_cm1,
        temp_array=temperatures,
        sigma=sym_res.sigma,
        lam_frequency=lam_frequency,
    )

    combined_params: Dict[str, Any] = {
        "A": a,
        "B": b,
        "C": c,
    }
    if quartic_distortion:
        combined_params.update(quartic_distortion)

    var_path = Path(output_dir) / f"{molecule_name}.var" if output_dir else None
    var_content = generate_spcat_var(
        molecule_name=molecule_name,
        parameters=combined_params,
        filepath=var_path,
    )

    int_tpl = Path(output_dir) / f"{molecule_name}_{{T}}K.int" if output_dir else None
    int_contents = generate_spcat_int(
        molecule_name=molecule_name,
        dipoles=dipoles_debye,
        temperatures=temperatures,
        filepath_template=int_tpl,
    )

    prov_path = Path(output_dir) / f"{molecule_name}_spcat_provenance.json" if output_dir else None
    manifest = generate_spcat_provenance_manifest(
        molecule_name=molecule_name,
        var_content=var_content,
        int_contents=int_contents,
        symmetry_result=sym_res,
        partition_results=part_res.q_total,
        output_path=prov_path,
    )

    return SPCATPayload(
        molecule_name=molecule_name,
        var_content=var_content,
        int_contents=int_contents,
        provenance_manifest=manifest,
        sha256_var=compute_sha256(var_content),
        sha256_int={t: compute_sha256(c) for t, c in int_contents.items()},
        var_filepath=str(var_path) if var_path else None,
        int_filepaths={t: str(Path(output_dir) / f"{molecule_name}_{t:.1f}K.int") for t in temperatures} if output_dir else {},
        provenance_filepath=str(prov_path) if prov_path else None,
    )


__all__ = [
    "CODATA2022",
    "CONSTANTS",
    "SymmetryDivisorResult",
    "PartitionFunctionResult",
    "SPCATParameter",
    "SPCATPayload",
    "PICKETT_PARAMETER_CODES",
    "low_frequency_lam_trap",
    "apply_symmetry_divisors",
    "calculate_rotational_partition_function",
    "calculate_vibrational_partition_function",
    "vibrational_partition_coupling",
    "compute_coupled_partition_functions",
    "fortran_overflow_guard",
    "format_fortran_double",
    "fortran_double_precision_formatter",
    "generate_spcat_var",
    "generate_spcat_int",
    "validate_airgap_boundary",
    "compute_sha256",
    "generate_spcat_provenance_manifest",
    "build_complete_spcat_payload",
]

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_spcat_bridge.py ---
"""Rigorous Authentic Physics Unit and Integration Tests for Stage 5.1: Statistical Mechanics & SPCAT Bridge.

Tests validate:
1. Low-Frequency LAM Trap (< 50 cm^-1) throwing LAMTriggerError / LAM_TRIGGER code.
2. MolSym point-group symmetry resolution (C2v, sigma=2) and nuclear spin statistical weights ('3 1').
3. Strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin statistical weights.
4. Vibrational partition coupling across temperature gradients with automatic LAM mode dropping.
5. Exact CODATA 2022 fundamental physical constants.
6. Fortran Double Precision overflow guard (|val| > 1e308) raising FortranOverflowError.
7. Rigid character alignment and 'D' exponent formatting for parameter lines.
8. Complete Pickett SPCAT .var and .int ASCII file generation.
9. Tripartite Filesystem Air-Gap compliance and SHA-256 cryptographic provenance manifests.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cochem_base.config_loader import get_base_root
from cochem_base.exceptions import (
    AirGapViolationError,
    FortranOverflowError,
    LAMTriggerError,
    ProvenanceErrorCode,
)
from cochem_spcat_bridge import (
    CONSTANTS,
    SPCATPayload,
    apply_symmetry_divisors,
    build_complete_spcat_payload,
    calculate_rotational_partition_function,
    calculate_vibrational_partition_function,
    format_fortran_double,
    fortran_double_precision_formatter,
    fortran_overflow_guard,
    generate_spcat_int,
    generate_spcat_var,
    low_frequency_lam_trap,
    validate_airgap_boundary,
    vibrational_partition_coupling,
)

# =============================================================================
# 1. Authentic Physical Test Data (Water H2O & Ammonia NH3)
# =============================================================================

# Real experimental / ab initio Cartesian geometry for Water (H2O in Angstroms)
H2O_GEOMETRY = np.array([
    [0.000000,  0.000000,  0.117300],  # Oxygen (O)
    [0.000000,  0.757200, -0.469200],  # Hydrogen (H1)
    [0.000000, -0.757200, -0.469200],  # Hydrogen (H2)
], dtype=np.float64)
H2O_SYMBOLS = ["O", "H", "H"]

# Real rotational constants for H2O (MHz)
H2O_A_MHZ = 825360.0   # ~ 27.877 cm^-1
H2O_B_MHZ = 435360.0   # ~ 14.522 cm^-1
H2O_C_MHZ = 278130.0   # ~ 9.277 cm^-1

# Real normal mode harmonic vibrational frequencies for H2O (cm^-1)
H2O_HARMONIC_FREQUENCIES = [1594.75, 3657.05, 3755.93]  # Bend, sym stretch, asym stretch

# Real dipole moment for H2O in Debye (directed along b-axis in standard orientation)
H2O_DIPOLES = {"mu_a": 0.0, "mu_b": 1.8546, "mu_c": 0.0}

# Quartic centrifugal distortion constants for H2O (Watson A-reduction in MHz)
H2O_WATSON_A = {
    "DJ": 1.567e-5,
    "DJK": -5.230e-5,
    "DK": 2.890e-4,
    "d1": 3.450e-6,
    "d2": 1.120e-5,
}


# =============================================================================
# 2. Test Low-Frequency LAM Trap (Physical Guardrail against RRHO Failure)
# =============================================================================

def test_low_frequency_lam_trap_triggers_on_low_mode() -> None:
    """Pass test frequency array containing [3100.0, 1500.0, 105.0, 24.5] cm^-1 to low_frequency_lam_trap.

    Assert that the function correctly identifies 24.5 cm^-1, halts the standard RRHO flow,
    and raises a LAMTriggerError with error_code LAM_TRIGGER indicating that DVR treatment
    is physically required.
    """
    frequencies = [3100.0, 1500.0, 105.0, 24.5]

    with pytest.raises(LAMTriggerError) as exc_info:
        low_frequency_lam_trap(frequencies)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.LAM_TRIGGER or str(err.error_code) == "LAM_TRIGGER"
    assert "24.50 cm^-1" in err.message or "24.5" in str(err.details.get("flagged_frequencies", []))
    assert err.details["threshold_cm1"] == 50.0
    assert 24.5 in err.details["flagged_frequencies"]
    assert "DVR" in err.message


def test_low_frequency_lam_trap_passes_on_stiff_modes() -> None:
    """Verify that authentic stiff vibrational frequencies (>= 50 cm^-1) pass cleanly."""
    stiff_modes = low_frequency_lam_trap(H2O_HARMONIC_FREQUENCIES)
    assert len(stiff_modes) == 3
    assert stiff_modes == H2O_HARMONIC_FREQUENCIES


def test_low_frequency_lam_trap_multiple_lam_modes() -> None:
    """Verify detection when multiple low torsional frequencies are present."""
    frequencies = [2800.0, 1200.0, 42.1, 15.3, 0.0]
    with pytest.raises(LAMTriggerError) as exc_info:
        low_frequency_lam_trap(frequencies, threshold_cm1=50.0)

    flagged = exc_info.value.details["flagged_frequencies"]
    assert 15.3 in flagged
    assert 42.1 in flagged
    assert 0.0 not in flagged


# =============================================================================
# 3. Test MolSym Point-Group & Nuclear Spin Statistical Weights
# =============================================================================

def test_molsym_spin_and_divisor_validation_h2o() -> None:
    """Feed aligned Cartesian coordinates of Water (H2O) to apply_symmetry_divisors().

    Assert that MolSym correctly identifies the C2v point group.
    Assert the returned divisor is exactly sigma = 2.
    Assert the returned spin statistical weight string correctly evaluates to the
    Ortho/Para ratio of '3 1'.
    """
    res = apply_symmetry_divisors(geometry_array=H2O_GEOMETRY, symbols=H2O_SYMBOLS)

    assert res.point_group == "C2v"
    assert res.sigma == 2
    assert res.spin_statistical_weights == [3, 1]
    assert res.spin_weight_ratio_str == "3 1"
    assert res.effective_divisor == 2.0
    assert "GUARDRAIL_ENFORCED" in res.guardrail_status


def test_symmetry_double_counting_guardrail_selection() -> None:
    """Enforce strict Double-Counting Guardrail between 1/sigma divisor and nuclear spin weights.

    When nuclear spin weights are explicitly applied, classical 1/sigma divisor must be bypassed
    (effective_divisor = 1.0) to prevent double-deflating the state density.
    """
    res_classical = apply_symmetry_divisors(H2O_GEOMETRY, H2O_SYMBOLS, use_nuclear_spin=False)
    assert res_classical.sigma == 2
    assert res_classical.effective_divisor == 2.0
    assert res_classical.guardrail_status == "GUARDRAIL_ENFORCED_CLASSICAL_SIGMA_APPLIED"

    res_spin = apply_symmetry_divisors(H2O_GEOMETRY, H2O_SYMBOLS, use_nuclear_spin=True)
    assert res_spin.sigma == 2
    assert res_spin.effective_divisor == 1.0
    assert res_spin.guardrail_status == "GUARDRAIL_ENFORCED_EXACT_NUCLEAR_SPIN_APPLIED_SIGMA_BYPASSED"


def test_molsym_symmetry_ammonia_c3v() -> None:
    """Verify symmetry and spin weights for Ammonia (NH3) in C3v."""
    r_nh = 1.012
    theta_hnh = math.radians(106.68)
    sin_beta = math.sqrt(2.0 / 3.0 * (1.0 - math.cos(theta_hnh)))
    cos_beta = math.sqrt(1.0 - sin_beta**2)
    r_xy = r_nh * sin_beta
    z_h = -r_nh * cos_beta
    coords_nh3 = np.array([
        [0.0, 0.0, 0.0],
        [r_xy, 0.0, z_h],
        [-r_xy * 0.5, r_xy * math.sqrt(3) / 2.0, z_h],
        [-r_xy * 0.5, -r_xy * math.sqrt(3) / 2.0, z_h],
    ], dtype=float)
    symbols_nh3 = ["N", "H", "H", "H"]

    res = apply_symmetry_divisors(coords_nh3, symbols_nh3)
    assert res.point_group == "C3v"
    assert res.sigma == 3
    assert res.spin_weight_ratio_str in ("2 1", "4 2")


# =============================================================================
# 4. Test Fortran Double Precision Formatter & String Alignment
# =============================================================================

def test_fortran_string_alignment_and_type() -> None:
    """Pass quartic centrifugal distortion parameter (DJ = 0.00001567 MHz) to fortran_double_precision_formatter().

    Assert that the output string strictly uses the 'D' identifier (e.g. 1.567D-05)
    and that the parameter identifier code (e.g. 20000) is right-aligned to exactly
    the correct column index (width 10) without a single space of deviation.
    """
    dj_val = 0.00001567
    param_id = 20000

    compact_str = fortran_double_precision_formatter(dj_val, compact=True)
    assert "D-05" in compact_str
    assert "1.567" in compact_str
    assert "e" not in compact_str
    assert "E" not in compact_str

    line = fortran_double_precision_formatter(
        val_or_id=param_id,
        val=dj_val,
        uncertainty=1.0e-7,
        label="DJ",
        width=22,
        precision=15,
        compact=False,
    )

    assert line[:10] == "     20000", f"Expected '     20000', got '{line[:10]}'"
    assert "D-05" in line
    assert "D-07" in line
    assert "/ DJ" in line


def test_format_fortran_double_various_scales() -> None:
    """Verify Fortran Double Precision scientific string formatting across orders of magnitude."""
    assert format_fortran_double(0.0, compact=True) == "0.000D+00"
    assert "D+05" in format_fortran_double(825360.0, compact=True)
    assert "D-09" in format_fortran_double(1.234e-9, compact=True)
    assert "D+00" in format_fortran_double(1.0, compact=True)


# =============================================================================
# 5. Test Fortran Double Precision Overflow Guard
# =============================================================================

def test_fortran_overflow_guard_intercepts_unphysical_value() -> None:
    """Intentionally feed an unphysically massive parameter (1.5e310) representing a failed perturbation calculation.

    Assert that fortran_overflow_guard() intercepts the value before formatting,
    logs the critical error, and raises FortranOverflowError / blocks corrupted parameters.
    """
    corrupt_params = {
        "A": 825360.0,
        "B": 435360.0,
        "C": 278130.0,
        "DJ": 1.5e310,  # Exceeds IEEE 754 Double Precision limit (1e308)
    }

    with pytest.raises(FortranOverflowError) as exc_info:
        fortran_overflow_guard(corrupt_params)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.FORTRAN_OVERFLOW or str(err.error_code) == "FORTRAN_OVERFLOW"
    assert "DJ" in str(err.details.get("parameter", ""))
    val_str = str(err.details.get("value", "")).lower()
    assert "inf" in val_str or "310" in val_str or "1.5" in val_str


def test_fortran_overflow_guard_valid_dictionary() -> None:
    """Verify that physically realistic parameters pass the overflow guard untouched."""
    valid_params = {
        "A": 825360.0,
        "B": 435360.0,
        "C": 278130.0,
        "DJ": 1.567e-5,
        "DJK": -5.23e-5,
    }
    checked = fortran_overflow_guard(valid_params)
    assert checked["A"] == 825360.0
    assert checked["DJ"] == 1.567e-5


# =============================================================================
# 6. Test Partition Functions & Vibrational Partition Coupling
# =============================================================================

def test_exact_codata_2022_constants() -> None:
    """Validate exact CODATA 2022 constants used throughout the bridge."""
    assert CONSTANTS.H == 6.62607015e-34
    assert CONSTANTS.K_B == 1.380649e-23
    assert CONSTANTS.C_CM_S == 29979245800.0
    assert abs(CONSTANTS.C_ROT - 505379.008435) < 1e-4
    assert abs(CONSTANTS.HC_OVER_KB - 1.4387768775) < 1e-6


def test_rotational_partition_function_water() -> None:
    """Calculate rotational partition function Q_rot(T) for H2O at 298.15 K."""
    temp = 298.15
    q_rot = calculate_rotational_partition_function(
        a_mhz=H2O_A_MHZ,
        b_mhz=H2O_B_MHZ,
        c_mhz=H2O_C_MHZ,
        temp_k=temp,
        sigma=2.0,
    )
    # For H2O at 298.15 K with sigma=2, classical Q_rot ~ 43-45
    assert 40.0 < q_rot < 50.0


def test_vibrational_partition_coupling_drops_lam_frequency() -> None:
    """Verify vibrational_partition_coupling drops LAM frequency (< 50 cm^-1) when coupled with DVR.

    Demonstrates prevention of thermodynamic double-counting when DVR solves the low-frequency mode.
    """
    temps = [2.0, 10.0, 50.0, 298.15]
    all_freqs = [3100.0, 1500.0, 105.0, 24.5]  # Contains LAM mode 24.5 cm^-1
    lam_mode = 24.5

    # DVR rotational partition functions across temperature grid
    q_rot_dvr = {2.0: 1.05, 10.0: 4.8, 50.0: 35.2, 298.15: 185.0}

    # Coupled calculation with LAM mode dropped
    q_total_coupled = vibrational_partition_coupling(
        q_rot_dvr=q_rot_dvr,
        q_vib_orca=all_freqs,
        temp_array=temps,
        lam_frequency=lam_mode,
    )

    q_vib_with_lam = calculate_vibrational_partition_function(all_freqs, 298.15)
    q_vib_without_lam = calculate_vibrational_partition_function(all_freqs, 298.15, exclude_frequencies=[lam_mode])

    assert q_vib_without_lam < q_vib_with_lam
    expected_q_total_298 = q_rot_dvr[298.15] * q_vib_without_lam
    assert math.isclose(q_total_coupled[298.15], expected_q_total_298, rel_tol=1e-6)


# =============================================================================
# 7. Test Pickett SPCAT .var and .int ASCII Generation
# =============================================================================

def test_generate_spcat_var_content(tmp_path: Path) -> None:
    """Verify complete Pickett SPCAT .var file formatting, parameter codes, and control cards."""
    var_file = tmp_path / "H2O.var"
    params = {
        "A": H2O_A_MHZ,
        "B": H2O_B_MHZ,
        "C": H2O_C_MHZ,
        "DJ": 1.567e-5,
    }

    content = generate_spcat_var(
        molecule_name="H2O",
        parameters=params,
        filepath=var_file,
    )

    assert var_file.exists()
    lines = content.strip().split("\n")
    assert len(lines) >= 6

    # Line 1: Header title
    assert "H2O Ground State - CoChem SPCAT Bridge" in lines[0]

    # Line 2: Control line (NPAR, NLINE, NOPT, NWARN, ERPAR, WTFAC, SCALE, MAXIT)
    control_parts = lines[1].split()
    assert control_parts[0] == "4"
    assert "D+00" in lines[1]

    # Parameter lines
    assert any("20000" in line and "D+05" in line for line in lines)
    assert any("200" in line and "1.567" in line and "D-05" in line for line in lines)


def test_generate_spcat_int_content(tmp_path: Path) -> None:
    """Verify complete Pickett SPCAT .int file generation with temperature as 9th parameter on Line 2."""
    temps = [2.0, 298.15]
    tpl = tmp_path / "H2O_{T}K.int"

    int_dict = generate_spcat_int(
        molecule_name="H2O",
        dipoles=H2O_DIPOLES,
        temperatures=temps,
        filepath_template=tpl,
    )

    assert 2.0 in int_dict
    assert 298.15 in int_dict

    f_298 = tmp_path / "H2O_298.1K.int"
    assert f_298.exists()

    content_298 = int_dict[298.15]
    lines = content_298.strip().split("\n")
    assert len(lines) == 5

    # Line 2: Control line with 298.15 as 9th parameter
    ctrl = lines[1].split()
    assert len(ctrl) == 9
    assert ctrl[8] == "298.15"

    # Line 3, 4, 5: Dipole moments
    assert "1" in lines[2] and "0.000000" in lines[2] and "/ mua" in lines[2]
    assert "2" in lines[3] and "1.854600" in lines[3] and "/ mub" in lines[3]
    assert "3" in lines[4] and "0.000000" in lines[4] and "/ muc" in lines[4]


# =============================================================================
# 8. Test Tripartite Air-Gap Compliance & Provenance Manifest
# =============================================================================

def test_tripartite_airgap_boundary_enforcement() -> None:
    """Assert validate_airgap_boundary blocks direct runtime writes to Ring 1 static repository root."""
    base_root = get_base_root().resolve()
    forbidden_target = base_root / "corrupt_scratch.tmp"

    with pytest.raises(AirGapViolationError) as exc_info:
        validate_airgap_boundary(forbidden_target)

    err = exc_info.value
    assert err.error_code == ProvenanceErrorCode.AIRGAP_VIOLATION or str(err.error_code) == "AIRGAP_VIOLATION"
    assert "Ring 1" in str(err.details.get("ring", "")) or "Air-Gap violation" in err.message


def test_build_complete_spcat_payload_end_to_end(tmp_path: Path) -> None:
    """Execute end-to-end payload synthesis for authentic H2O and verify complete bundle."""
    payload = build_complete_spcat_payload(
        molecule_name="H2O",
        geometry=H2O_GEOMETRY,
        symbols=H2O_SYMBOLS,
        rotational_constants_mhz={"A": H2O_A_MHZ, "B": H2O_B_MHZ, "C": H2O_C_MHZ},
        dipoles_debye=H2O_DIPOLES,
        harmonic_frequencies_cm1=H2O_HARMONIC_FREQUENCIES,
        temperatures=[2.0, 10.0, 50.0, 298.15],
        quartic_distortion=H2O_WATSON_A,
        output_dir=tmp_path,
    )

    assert isinstance(payload, SPCATPayload)
    assert payload.molecule_name == "H2O"
    assert (tmp_path / "H2O.var").exists()
    assert (tmp_path / "H2O_2.0K.int").exists()
    assert (tmp_path / "H2O_298.1K.int").exists()
    assert (tmp_path / "H2O_spcat_provenance.json").exists()

    prov_data = json.loads((tmp_path / "H2O_spcat_provenance.json").read_text(encoding="utf-8"))
    assert prov_data["stage"] == "Stage 5.1 (Statistical Mechanics & SPCAT Bridge)"
    assert prov_data["symmetry"]["point_group"] == "C2v"
    assert prov_data["symmetry"]["sigma"] == 2
    assert prov_data["symmetry"]["spin_weight_ratio_str"] == "3 1"
    assert prov_data["cryptographic_hashes"]["sha256_var"] == payload.sha256_var
    assert len(prov_data["partition_functions"]) == 4


def test_linear_rotor_partition_function() -> None:
    """Validate linear rotor partition function formula Q_rot = k_B * T / (sigma * h * B)."""
    # Carbon monoxide (CO, linear, B ~ 57635.968 MHz, sigma=1)
    b_co_mhz = 57635.968
    temp = 298.15
    q_rot_co = calculate_rotational_partition_function(
        a_mhz=0.0,
        b_mhz=b_co_mhz,
        c_mhz=b_co_mhz,
        temp_k=temp,
        sigma=1.0,
        is_linear=True,
    )
    # Expected: (k_B / (h * 1e6)) * 298.15 / 57635.968 ~ 107.78
    expected = (CONSTANTS.K_B / (CONSTANTS.H * 1e6)) * temp / b_co_mhz
    assert math.isclose(q_rot_co, expected, rel_tol=1e-6)
    assert 105.0 < q_rot_co < 110.0


def test_cochem_base_reexport_parity() -> None:
    """Verify that cochem_base.cochem_spcat_bridge re-exports all core functions and constants."""
    import cochem_base.cochem_spcat_bridge as csb

    assert hasattr(csb, "low_frequency_lam_trap")
    assert hasattr(csb, "apply_symmetry_divisors")
    assert hasattr(csb, "calculate_rotational_partition_function")
    assert hasattr(csb, "calculate_vibrational_partition_function")
    assert hasattr(csb, "vibrational_partition_coupling")
    assert hasattr(csb, "fortran_overflow_guard")
    assert hasattr(csb, "fortran_double_precision_formatter")
    assert hasattr(csb, "generate_spcat_var")
    assert hasattr(csb, "generate_spcat_int")
    assert hasattr(csb, "build_complete_spcat_payload")
    assert csb.CONSTANTS.H == CONSTANTS.H


Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.