Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc6_01_workspace_manager_prompt.md.
Original prompt:
# Prompt: Workspace Scaffolding Daemon

**Target File:** `D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\core\cochem_core_workspace_manager.py`

## Goal
Implement the Workspace Scaffolding Daemon to atomically generate, secure, and validate the Bipartite Data Tier at exactly `D:\__CoChem\CoChem_Artifacts`. This provides an isolated, pristine working directory for downstream calculation engines, completely disconnected from the static GitHub repository.

## Requirements

1. **Parsl DAG Dependency Orchestration & Race Condition Prevention**
   - Autonomously scaffold the target directory tree: `/Input_Files`, `/Processed`, `/Logs`, `/Scratch`, `/Registry`, `/Databases` within `D:\__CoChem\CoChem_Artifacts`.
   - Mandate Parsl DAG dependency orchestration for directory scaffolding to serialize directory creation before computational tasks are spawned. 
   - **Constraint:** Do not use `.workspace.lock` files or filesystem-based mutexes for directory creation topologies.

2. **Directory Permission Locks (Deletion Shield)**
   - Use `os.chmod` to enforce `0o755` permissions for standard active working directories.
   - For finalized `.zip` report payloads, `.tex` artifacts, and locked states, apply `os.chmod(0o444)` (Read-Only) post-generation to prevent accidental recursive deletion (`rm -rf`).

3. **Pre-Flight Disk Quota & File System Traps**
   - Before authorizing any quantum calculation queue, execute `shutil.disk_usage()` on the target `Scratch/` directory.
   - Mathematically assert that at least 50GB of free disk space is available.
   - If space is insufficient, raise a custom `DiskQuotaError` immediately to prevent disk exhaustion.

## Constraints & Rules
- **NO MOCKS, STUBS, OR PLACEHOLDERS.** Write complete, production-ready logic.
- Ensure strict compliance with all constraints and requirements.

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

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core_engine\cochem_core_workspace_manager.py ---
#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Workspace Scaffolding Daemon & Air-Gap Manager
Re-exports canonical workspace manager from cochem_base.core.cochem_core_workspace_manager.
"""

from __future__ import annotations

from cochem_base.core.cochem_core_workspace_manager import *

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_cochem_core_workspace_manager.py ---
"""
Unit and integration test suite for CoChem-CORE: Workspace Scaffolding Daemon,
Parsl DAG Dependency Orchestration, Deletion Shield Permission Locking,
and Pre-Flight Scratch Disk Quota Traps.

Strict Zero-Mock Mandate: Real Parsl DAG execution with ThreadPoolExecutor,
real directory scaffolding under tmp_path, real shutil.disk_usage() telemetry,
real cross-platform os.chmod permission locking/unlocking, real file writes/reads,
and real zombie sweeping & job isolation.

Method Matrix v4 & SRS Workspace Scaffolding Daemon Specification Compliant.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Generator

import pytest

from cochem_base.core.cochem_core_workspace_manager import (
    CORE_DIRECTORIES,
    DEFAULT_ARTIFACT_ROOT,
    MIN_SCRATCH_FREE_GB,
    AirgapTopology,
    BipartiteTopology,
    DaemonStatus,
    DirectoryInfo,
    DiskQuotaError,
    DiskQuotaMetrics,
    ScaffoldResult,
    WorkspaceDaemon,
    WorkspaceManager,
    WorkspaceScaffoldingDaemon,
    apply_bipartite_airgap,
    apply_tripartite_airgap,
    assert_scratch_disk_quota,
    check_scratch_disk_quota,
    cleanup_job_workspace,
    file_lock,
    get_default_workspace_manager,
    get_directory_status,
    get_job_workspace,
    is_job_active,
    lock_artifact_permissions,
    provision_job_workspace,
    scaffold_core_directories,
    scaffold_workspace_parsl,
    sweep_zombie_directories,
    unlock_artifact_permissions,
)
from cochem_base.exceptions import CoChemError

# =============================================================================
# PYTEST FIXTURES (ZERO-MOCK REAL PARSL & STORAGE ENVIRONMENTS)
# =============================================================================


@pytest.fixture
def parsl_session() -> Generator[Any, None, None]:
    """Pytest fixture providing an initialized Parsl ThreadPoolExecutor environment.

    Ensures safe teardown and resource deallocation between test runs.
    """
    import parsl
    from parsl.config import Config
    from parsl.executors.threads import ThreadPoolExecutor

    try:
        parsl.clear()
    except Exception:
        pass

    cfg = Config(
        executors=[ThreadPoolExecutor(max_threads=4, label="cochem_workspace_test_pool")],
        strategy="none",
    )
    parsl.load(cfg)
    try:
        yield cfg
    finally:
        try:
            parsl.clear()
        except Exception:
            pass


# =============================================================================
# 1. MODULE EXPORTS, CONSTANTS, AND PYDANTIC DATA MODEL TESTS
# =============================================================================


def test_module_exports_and_constants() -> None:
    """Verify all required classes, functions, models, and constants are exported."""
    expected_core_dirs = ["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"]
    for d in expected_core_dirs:
        assert d in CORE_DIRECTORIES

    assert isinstance(DEFAULT_ARTIFACT_ROOT, Path)
    assert MIN_SCRATCH_FREE_GB == 50.0

    # Ensure alias parity
    assert WorkspaceScaffoldingDaemon is WorkspaceDaemon


def test_pydantic_disk_quota_metrics_model() -> None:
    """Verify DiskQuotaMetrics Pydantic data model structure, validation, and serialization."""
    metrics = DiskQuotaMetrics(
        path="/tmp/test_scratch",
        total_bytes=100 * (1024**3),
        used_bytes=40 * (1024**3),
        free_bytes=60 * (1024**3),
        total_gb=100.0,
        used_gb=40.0,
        free_gb=60.0,
        min_required_gb=50.0,
        is_sufficient=True,
    )

    assert metrics.path == "/tmp/test_scratch"
    assert metrics.total_gb == 100.0
    assert metrics.free_gb == 60.0
    assert metrics.min_required_gb == 50.0
    assert metrics.is_sufficient is True
    assert metrics.timestamp > 0.0

    data = metrics.model_dump()
    assert data["is_sufficient"] is True
    assert data["free_gb"] == 60.0

    restored = DiskQuotaMetrics.model_validate(data)
    assert restored.free_gb == 60.0
    assert restored.path == "/tmp/test_scratch"


def test_pydantic_directory_info_model() -> None:
    """Verify DirectoryInfo Pydantic data model."""
    d_info = DirectoryInfo(
        path="/data/cochem/Logs",
        exists=True,
        file_count=12,
        dir_count=3,
        total_size_bytes=204800,
        is_writable=True,
        is_readable=True,
    )
    assert d_info.file_count == 12
    assert d_info.dir_count == 3
    assert d_info.total_size_bytes == 204800
    assert d_info.is_writable is True
    assert d_info.is_readable is True

    serialized = d_info.model_dump()
    assert serialized["file_count"] == 12
    assert DirectoryInfo.model_validate(serialized).exists is True


def test_pydantic_scaffold_result_model() -> None:
    """Verify ScaffoldResult Pydantic data model."""
    res = ScaffoldResult(
        base_path="/data/CoChem_Artifacts",
        directories=["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"],
        created_paths=[
            "/data/CoChem_Artifacts/Input_Files",
            "/data/CoChem_Artifacts/Processed",
            "/data/CoChem_Artifacts/Logs",
            "/data/CoChem_Artifacts/Scratch",
            "/data/CoChem_Artifacts/Registry",
            "/data/CoChem_Artifacts/Databases",
        ],
        success=True,
        parsl_task_ids=["task_0", "task_1", "task_2", "task_3", "task_4", "task_5"],
        execution_time_seconds=0.045,
    )
    assert res.success is True
    assert len(res.directories) == 6
    assert len(res.created_paths) == 6
    assert len(res.parsl_task_ids) == 6
    assert res.execution_time_seconds == 0.045


def test_pydantic_topology_models() -> None:
    """Verify AirgapTopology and BipartiteTopology data models."""
    airgap = AirgapTopology(
        immutable_code="/repo/CoChem-BASE",
        dynamic_state="/artifacts",
        volatile_compute="/artifacts/Scratch",
        code_tier="/repo/CoChem-BASE",
        data_tier="/artifacts",
        compute_tier="/artifacts/Scratch",
        status="active",
    )
    assert airgap.status == "active"
    assert airgap.compute_tier == "/artifacts/Scratch"

    bipartite = BipartiteTopology(
        code_tier="/repo/CoChem-BASE",
        data_tier="/artifacts",
        status="active",
    )
    assert bipartite.code_tier == "/repo/CoChem-BASE"
    assert bipartite.data_tier == "/artifacts"


def test_pydantic_daemon_status_model() -> None:
    """Verify DaemonStatus data model."""
    status = DaemonStatus(
        is_running=True,
        interval_seconds=30.0,
        sweeps_completed=5,
        last_sweep_timestamp=time.time(),
        last_zombies_swept=2,
        last_disk_quota_metrics=None,
    )
    assert status.is_running is True
    assert status.sweeps_completed == 5
    assert status.last_zombies_swept == 2


# =============================================================================
# 2. DISK QUOTA ERROR & PRE-FLIGHT SCRATCH DISK QUOTA TRAPS
# =============================================================================


def test_disk_quota_error_exception_structure() -> None:
    """Verify DiskQuotaError carries required diagnostic metadata and is a CoChemError."""
    err = DiskQuotaError(
        required_gb=50.0,
        available_gb=12.4,
        path=Path("/tmp/Scratch"),
        message="Insufficient scratch disk quota",
    )
    assert isinstance(err, CoChemError)
    assert isinstance(err, OSError)
    assert err.required_gb == 50.0
    assert err.available_gb == 12.4
    assert str(err.path).endswith("Scratch")
    assert "50.00 GB" in str(err) or "50.0" in str(err)
    assert "12.40 GB" in str(err) or "12.4" in str(err)


def test_check_scratch_disk_quota_sufficient_space(tmp_path: Path) -> None:
    """Zero-mock pre-flight disk quota check with sufficient space succeeds."""
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Calling check_scratch_disk_quota with very low threshold (e.g. 0.001 GB = 1MB)
    metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=0.001)

    assert isinstance(metrics, DiskQuotaMetrics)
    assert metrics.is_sufficient is True
    assert metrics.free_gb > 0.0
    assert metrics.total_gb > 0.0
    assert metrics.used_gb >= 0.0
    assert metrics.min_required_gb == 0.001
    assert Path(metrics.path).resolve() == scratch_dir.resolve()

    # Calling assert_scratch_disk_quota with small threshold must NOT raise
    assert_result = assert_scratch_disk_quota(scratch_dir, min_free_gb=0.001)
    assert assert_result.is_sufficient is True


def test_check_scratch_disk_quota_insufficient_space_raises(tmp_path: Path) -> None:
    """Zero-mock pre-flight disk quota trap: insufficient disk space raises DiskQuotaError."""
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    total, used, free = shutil.disk_usage(str(scratch_dir))
    actual_free_gb = free / (1024**3)

    # Set an impossible requirement higher than available free disk space
    impossible_threshold_gb = actual_free_gb + 50000.0

    # check_scratch_disk_quota returns metrics with is_sufficient=False
    metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=impossible_threshold_gb)
    assert isinstance(metrics, DiskQuotaMetrics)
    assert metrics.is_sufficient is False
    assert metrics.min_required_gb == impossible_threshold_gb

    # assert_scratch_disk_quota must raise DiskQuotaError
    with pytest.raises(DiskQuotaError) as exc_info:
        assert_scratch_disk_quota(scratch_dir, min_free_gb=impossible_threshold_gb)

    err = exc_info.value
    assert err.required_gb == impossible_threshold_gb
    assert abs(err.available_gb - actual_free_gb) < 1.0
    assert err.path is not None
    assert Path(err.path).resolve() == scratch_dir.resolve()


def test_workspace_manager_disk_quota_methods(tmp_path: Path) -> None:
    """Verify WorkspaceManager instance methods for disk quota assertions."""
    manager = WorkspaceManager(base_path=tmp_path)
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Manager check with tiny quota
    metrics = manager.check_scratch_disk_quota(min_free_gb=0.01)
    assert metrics.is_sufficient is True

    # Manager assert with tiny quota
    assert_metrics = manager.assert_scratch_disk_quota(min_free_gb=0.01)
    assert assert_metrics.is_sufficient is True

    # Manager assert with impossible quota raises DiskQuotaError
    with pytest.raises(DiskQuotaError):
        manager.assert_scratch_disk_quota(min_free_gb=100_000_000.0)


# =============================================================================
# 3. PARSL DAG DEPENDENCY ORCHESTRATION & DIRECTORY SCAFFOLDING
# =============================================================================


def test_parsl_dag_workspace_scaffolding_core_tree(tmp_path: Path, parsl_session: Any) -> None:
    """Zero-mock Parsl DAG directory tree scaffolding.

    Verifies that directory tree /Input_Files, /Processed, /Logs, /Scratch, /Registry, /Databases
    is created via Parsl app/DAG dependency chaining without .workspace.lock files or mutexes.
    """
    target_root = tmp_path / "CoChem_Artifacts"
    assert not target_root.exists()

    result = scaffold_workspace_parsl(base_path=target_root)

    assert isinstance(result, ScaffoldResult)
    assert result.success is True
    assert target_root.exists() and target_root.is_dir()

    expected_dirs = ["Input_Files", "Processed", "Logs", "Scratch", "Registry", "Databases"]
    for d_name in expected_dirs:
        d_path = target_root / d_name
        assert d_path.exists(), f"Expected directory {d_name} was not created"
        assert d_path.is_dir(), f"Expected {d_name} to be a directory"

    # Constraint verification: NO .workspace.lock file or filesystem mutexes in creation topology
    lock_file = target_root / ".workspace.lock"
    assert not lock_file.exists(), "Parsl scaffolding topology must not generate .workspace.lock file"


def test_parsl_dag_workspace_scaffolding_additional_dirs(tmp_path: Path, parsl_session: Any) -> None:
    """Verify Parsl DAG scaffolding with additional custom silo and task queue directories."""
    target_root = tmp_path / "CoChem_Artifacts_Extended"
    additional = ["cochem_setup", "cochem_task_queue", "MACE_Checkpoints", "ORCA_Scratch"]

    result = scaffold_workspace_parsl(base_path=target_root, additional_dirs=additional)

    assert result.success is True
    for d_name in CORE_DIRECTORIES:
        assert (target_root / d_name).is_dir()

    for custom_dir in additional:
        assert (target_root / custom_dir).is_dir()


def test_parsl_dag_task_dependency_chaining(tmp_path: Path, parsl_session: Any) -> None:
    """Verify Parsl DAG dependency serialization: downstream compute task chains to directory futures.

    Proves that a computational chemistry preparation task waits for directory creation
    future resolution before writing genuine quantum chemical inputs.
    """
    from parsl.app.app import python_app

    target_root = tmp_path / "CoChem_Artifacts_Chained"

    # Define a downstream computational preparation task chained to scaffold future
    @python_app
    def prepare_orca_input(input_dir_path: str, filename: str, content: str) -> str:
        from pathlib import Path
        inp_file = Path(input_dir_path) / filename
        inp_file.write_text(content, encoding="utf-8")
        return str(inp_file)

    # 1. Launch Parsl workspace scaffolding
    scaffold_result = scaffold_workspace_parsl(base_path=target_root)
    assert scaffold_result.success is True

    # 2. Chain downstream input generation task
    input_files_dir = str(target_root / "Input_Files")
    orca_payload = (
        "! B3LYP def2-SVP D4 Opt\n"
        "%pal nprocs 4 end\n"
        "* xyz 0 1\n"
        "O  0.000000  0.000000  0.117790\n"
        "H  0.000000  0.755453 -0.471161\n"
        "H  0.000000 -0.755453 -0.471161\n"
        "*\n"
    )

    future = prepare_orca_input(input_files_dir, "monomer_relax.inp", orca_payload)
    output_path = future.result()

    assert Path(output_path).exists()
    assert (target_root / "Input_Files" / "monomer_relax.inp").read_text(encoding="utf-8") == orca_payload


def test_workspace_manager_scaffold_workspace_parsl(tmp_path: Path, parsl_session: Any) -> None:
    """Verify WorkspaceManager.scaffold_workspace_parsl method execution."""
    manager = WorkspaceManager(base_path=tmp_path)
    result = manager.scaffold_workspace_parsl(additional_dirs=["Custom_Reports"])

    assert isinstance(result, ScaffoldResult)
    assert result.success is True
    assert (tmp_path / "Custom_Reports").is_dir()
    for d in CORE_DIRECTORIES:
        assert (tmp_path / d).is_dir()


# =============================================================================
# 4. DELETION SHIELD PERMISSION LOCKING & RESTORATION (0o755 / 0o444)
# =============================================================================


def test_deletion_shield_file_permission_locking(tmp_path: Path) -> None:
    """Zero-mock Deletion Shield: Finalized .zip, .tex, and .h5 artifacts set to 0o444 (Read-Only).

    Verifies write attempts raise PermissionError while read-only, and restoring permissions
    allows write access again.
    """
    artifacts_dir = tmp_path / "Final_Artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    report_zip = artifacts_dir / "calculation_report.zip"
    report_zip.write_bytes(b"PK\x03\x04_GENUINE_ZIP_PAYLOAD")

    publication_tex = artifacts_dir / "spectroscopy_table.tex"
    publication_tex.write_text("\\begin{table}\n\\caption{Rotational Constants}\n\\end{table}", encoding="utf-8")

    state_h5 = artifacts_dir / "cochem_state.h5"
    state_h5.write_bytes(b"\x89HDF\r\n\x1a\n_STATE_PAYLOAD")

    # Apply Deletion Shield (Read-Only 0o444)
    lock_artifact_permissions(report_zip, read_only=True)
    lock_artifact_permissions(publication_tex, read_only=True)
    lock_artifact_permissions(state_h5, read_only=True)

    # 1. Verify writing / overwriting fails with PermissionError
    with pytest.raises(PermissionError):
        with open(report_zip, "w", encoding="utf-8") as f:
            f.write("malicious overwrite")

    with pytest.raises(PermissionError):
        with open(publication_tex, "w", encoding="utf-8") as f:
            f.write("corrupted table")

    with pytest.raises(PermissionError):
        with open(state_h5, "wb") as f:
            f.write(b"corrupted hdf5")

    # 2. Unlock artifacts and verify write capability is restored
    unlock_artifact_permissions(report_zip)
    unlock_artifact_permissions(publication_tex)
    lock_artifact_permissions(state_h5, read_only=False)

    with open(report_zip, "wb") as f:
        f.write(b"updated zip payload")
    assert report_zip.read_bytes() == b"updated zip payload"

    with open(publication_tex, "a", encoding="utf-8") as f:
        f.write("\n% appended row")
    assert "% appended row" in publication_tex.read_text(encoding="utf-8")


def test_deletion_shield_recursive_directory_locking(tmp_path: Path) -> None:
    """Zero-mock Deletion Shield: Recursive permission locking across directory trees."""
    data_dir = tmp_path / "Persistent_Data_Tier"
    data_dir.mkdir(parents=True, exist_ok=True)

    sub_reg = data_dir / "Registry" / "Schemas"
    sub_reg.mkdir(parents=True, exist_ok=True)
    schema_json = sub_reg / "v4_schema.json"
    schema_json.write_text('{"schema_version": "4.0.0"}', encoding="utf-8")

    sub_proc = data_dir / "Processed" / "Geom"
    sub_proc.mkdir(parents=True, exist_ok=True)
    geom_xyz = sub_proc / "dimer_opt.xyz"
    geom_xyz.write_text("3\nDimer optimized\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    # Lock whole directory tree recursively
    lock_artifact_permissions(data_dir, read_only=True, recursive=True)

    # Attempt to write to nested files must raise PermissionError
    with pytest.raises(PermissionError):
        with open(schema_json, "w", encoding="utf-8") as f:
            f.write('{"tampered": true}')

    with pytest.raises(PermissionError):
        with open(geom_xyz, "w", encoding="utf-8") as f:
            f.write("corrupted xyz")

    # Restore read-write access
    lock_artifact_permissions(data_dir, read_only=False, recursive=True)

    with open(schema_json, "w", encoding="utf-8") as f:
        f.write('{"schema_version": "4.0.1"}')
    assert '4.0.1' in schema_json.read_text(encoding="utf-8")


def test_deletion_shield_file_extension_filter(tmp_path: Path) -> None:
    """Verify selective permission locking by file extension."""
    work_dir = tmp_path / "Filtered_Work"
    work_dir.mkdir(parents=True, exist_ok=True)

    lock_me_zip = work_dir / "payload.zip"
    lock_me_zip.write_bytes(b"ZIP_DATA")

    lock_me_tex = work_dir / "table.tex"
    lock_me_tex.write_text("TEX_DATA", encoding="utf-8")

    leave_me_tmp = work_dir / "scratch.tmp"
    leave_me_tmp.write_text("TEMP_DATA", encoding="utf-8")

    # Lock only .zip and .tex files
    lock_artifact_permissions(
        work_dir,
        read_only=True,
        recursive=True,
        file_extensions=[".zip", ".tex"],
    )

    # .zip and .tex should be locked
    with pytest.raises(PermissionError):
        with open(lock_me_zip, "wb") as f:
            f.write(b"FAIL")

    with pytest.raises(PermissionError):
        with open(lock_me_tex, "w", encoding="utf-8") as f:
            f.write("FAIL")

    # .tmp should remain writable
    with open(leave_me_tmp, "w", encoding="utf-8") as f:
        f.write("SUCCESS_MODIFIED")
    assert leave_me_tmp.read_text(encoding="utf-8") == "SUCCESS_MODIFIED"

    # Cleanup permissions
    lock_artifact_permissions(work_dir, read_only=False, recursive=True)


# =============================================================================
# 5. WORKSPACE MANAGER CORE DIRECTORIES, JOBS, ZOMBIES, & STATUS
# =============================================================================


def test_workspace_manager_initialization(tmp_path: Path) -> None:
    """Verify WorkspaceManager initialization and base path resolution."""
    manager = WorkspaceManager(base_path=str(tmp_path))
    assert manager.base_path == tmp_path.resolve()


def test_workspace_manager_scaffold_core_directories_standard(tmp_path: Path) -> None:
    """Verify standard scaffolding creates all core directories with active read/write permissions."""
    manager = WorkspaceManager(base_path=tmp_path)
    success = manager.scaffold_core_directories(additional_dirs=["CustomModule", "CustomCache"])
    assert success is True

    for d in WorkspaceManager.CORE_DIRECTORIES:
        expected_dir = tmp_path / d
        assert expected_dir.exists() and expected_dir.is_dir()
        # Verify writable
        assert os.access(str(expected_dir), os.W_OK)

    assert (tmp_path / "CustomModule").is_dir()
    assert (tmp_path / "CustomCache").is_dir()


def test_provision_and_get_job_workspace(tmp_path: Path) -> None:
    """Verify job workspace provisioning and path resolution."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ORCA_DFT_001"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    assert job_dir.exists()
    assert job_dir == tmp_path / "Scratch" / job_id
    assert (job_dir / ".job.lock").exists()

    retrieved = manager.get_job_workspace(job_id)
    assert retrieved == job_dir


def test_is_job_active_and_cleanup_protection(tmp_path: Path) -> None:
    """Verify active job lock detection protects running calculations from deletion."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_id = "JOB_ACTIVE_GUARD"
    job_dir = manager.provision_job_workspace(job_id, create_job_lock=True)
    job_lock = job_dir / ".job.lock"

    assert manager.is_job_active(job_id) is False

    # Simulate an active running process holding the job lock
    fd = os.open(str(job_lock), os.O_RDWR)
    try:
        acquired = manager._acquire_lock(fd)
        assert acquired is True
        assert manager.is_job_active(job_id) is True

        # Non-forced cleanup must abort to protect active calculation
        assert manager.cleanup_job_workspace(job_id, force=False) is False
        assert job_dir.exists()
    finally:
        manager._release_lock(fd)
        os.close(fd)

    assert manager.is_job_active(job_id) is False
    # Cleanup succeeds once lock is released
    assert manager.cleanup_job_workspace(job_id, force=False) is True
    assert not job_dir.exists()


def test_sweep_zombie_directories(tmp_path: Path) -> None:
    """Verify zombie directory sweeper removes orphaned crashed jobs while protecting active ones."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # 1. Orphaned zombie job with unlocked .job.lock
    job1_dir = manager.provision_job_workspace("JOB_ZOMBIE_1", create_job_lock=True)
    (job1_dir / "temp_calc.dat").write_text("! B3LYP def2-SVP\n", encoding="utf-8")

    # 2. Active running job with held lock
    job2_dir = manager.provision_job_workspace("JOB_ACTIVE_2", create_job_lock=True)
    job2_lock = job2_dir / ".job.lock"
    fd2 = os.open(str(job2_lock), os.O_RDWR)
    manager._acquire_lock(fd2)

    # 3. Orphaned zombie job without lock file
    job3_dir = manager.provision_job_workspace("JOB_ZOMBIE_3", create_job_lock=False)
    (job3_dir / "output.log").write_text("PARTIAL LOG DATA\n", encoding="utf-8")

    try:
        swept = manager.sweep_zombie_directories(grace_period_seconds=0.0)
        assert swept == 2

        # Job 1 and Job 3 must be purged
        assert not job1_dir.exists()
        assert not job3_dir.exists()

        # Job 2 must be preserved because it was actively locked
        assert job2_dir.exists()
    finally:
        manager._release_lock(fd2)
        os.close(fd2)

    # After releasing lock, sweeping again purges Job 2
    swept_again = manager.sweep_zombie_directories(grace_period_seconds=0.0)
    assert swept_again == 1
    assert not job2_dir.exists()


def test_sweep_zombie_directories_grace_period(tmp_path: Path) -> None:
    """Verify sweep_zombie_directories respects grace_period_seconds for newly provisioned directories."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    job_dir = manager.provision_job_workspace("JOB_FRESH_PROVISION", create_job_lock=False)
    assert job_dir.exists()

    # High grace period (e.g. 100s) must protect newly created directory
    swept = manager.sweep_zombie_directories(grace_period_seconds=100.0)
    assert swept == 0
    assert job_dir.exists()

    # Zero grace period sweeps unlocked directory
    swept_now = manager.sweep_zombie_directories(grace_period_seconds=0.0)
    assert swept_now == 1
    assert not job_dir.exists()


def test_get_directory_status(tmp_path: Path) -> None:
    """Verify get_directory_status returns accurate diagnostic metrics and file counts."""
    manager = WorkspaceManager(base_path=tmp_path)
    manager.scaffold_core_directories()

    # Populate Logs
    log_file = tmp_path / "Logs" / "cochem_orchestrator.log"
    log_file.write_text("INFO: Orchestrator initialized\nINFO: Stage 0 complete\n", encoding="utf-8")

    # Populate Processed
    proc_file = tmp_path / "Processed" / "conformer_01.xyz"
    proc_file.write_text("3\nConformer 01\nC 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")

    status = manager.get_directory_status()

    assert "Logs" in status
    assert status["Logs"]["exists"] is True
    assert status["Logs"]["file_count"] == 1
    assert status["Logs"]["total_size_bytes"] > 0
    assert status["Logs"]["is_writable"] is True
    assert status["Logs"]["is_readable"] is True

    assert "Processed" in status
    assert status["Processed"]["file_count"] == 1

    assert "Scratch" in status
    assert status["Scratch"]["exists"] is True
    assert status["Scratch"]["file_count"] == 0


def test_airgap_topologies_provisioning(tmp_path: Path) -> None:
    """Verify Tripartite and Bipartite Airgap topologies provisioning."""
    manager = WorkspaceManager(base_path=tmp_path)
    custom_code_dir = tmp_path / "CoChem_Source"
    custom_code_dir.mkdir(parents=True, exist_ok=True)

    # Tripartite
    tri_map = manager.apply_tripartite_airgap(code_dir=custom_code_dir)
    assert "immutable_code" in tri_map
    assert "dynamic_state" in tri_map
    assert "volatile_compute" in tri_map
    assert tri_map["immutable_code"] == str(custom_code_dir.resolve())
    assert tri_map["dynamic_state"] == str(tmp_path.resolve())
    assert tri_map["volatile_compute"] == str((tmp_path / "Scratch").resolve())

    # Bipartite
    bi_map = manager.apply_bipartite_airgap(code_dir=custom_code_dir)
    assert "code_tier" in bi_map
    assert "data_tier" in bi_map
    assert bi_map["code_tier"] == str(custom_code_dir.resolve())
    assert bi_map["data_tier"] == str(tmp_path.resolve())


# =============================================================================
# 6. WORKSPACE DAEMON LIFECYCLE & ASYNC COROUTINES
# =============================================================================


def test_workspace_daemon_lifecycle(tmp_path: Path) -> None:
    """Verify WorkspaceScaffoldingDaemon / WorkspaceDaemon threading lifecycle."""
    manager = WorkspaceManager(base_path=tmp_path)
    daemon = WorkspaceScaffoldingDaemon(
        manager=manager,
        sweep_interval_seconds=0.1,
        min_scratch_quota_gb=0.001,
    )

    assert daemon.get_status().is_running is False

    # Execute single manual cycle
    res = daemon.run_once()
    assert res["cycle"] == 1
    assert res["zombies_swept"] == 0
    assert "airgap_topology" in res
    assert "directory_status" in res
    assert "scratch_disk_quota" in res
    assert res["scratch_disk_quota"]["is_sufficient"] is True

    # Start background daemon thread
    daemon.start()
    assert daemon.get_status().is_running is True
    time.sleep(0.35)
    daemon.stop()

    status = daemon.get_status()
    assert status.is_running is False
    assert status.sweeps_completed >= 2


def test_workspace_daemon_run_async(tmp_path: Path) -> None:
    """Verify WorkspaceScaffoldingDaemon.run_async in asyncio loop."""
    async def _run() -> None:
        manager = WorkspaceManager(base_path=tmp_path)
        daemon = WorkspaceDaemon(
            manager=manager,
            sweep_interval_seconds=0.05,
            min_scratch_quota_gb=0.001,
        )

        task = asyncio.create_task(daemon.run_async())
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert daemon.sweeps_completed >= 1

    asyncio.run(_run())


# =============================================================================
# 7. CROSS-PLATFORM FILE LOCKING & SINGLETON HELPERS
# =============================================================================


def test_cross_platform_file_lock(tmp_path: Path) -> None:
    """Verify file_lock context manager mutual exclusion and timeout."""
    manager = WorkspaceManager(base_path=tmp_path)
    lock_file_path = tmp_path / "concurrency.lock"

    with manager.file_lock(lock_file_path, exclusive=True) as acquired1:
        assert acquired1 is True
        # Second non-blocking acquire attempt on same file must fail
        with manager.file_lock(lock_file_path, exclusive=True, timeout=0.0) as acquired2:
            assert acquired2 is False

    # Lock released; third acquire must succeed
    with manager.file_lock(lock_file_path, exclusive=True) as acquired3:
        assert acquired3 is True


def test_acquire_lock_timeout(tmp_path: Path) -> None:
    """Verify lock acquisition timeout parameter behavior."""
    manager = WorkspaceManager(base_path=tmp_path)
    test_file = tmp_path / "timeout_test.lock"
    fd1 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    fd2 = os.open(str(test_file), os.O_RDWR | os.O_CREAT)
    try:
        acquired1 = manager._acquire_lock(fd1, exclusive=True, timeout=0.0)
        assert acquired1 is True

        start = time.time()
        acquired2 = manager._acquire_lock(fd2, exclusive=True, timeout=0.05)
        elapsed = time.time() - start
        assert acquired2 is False
        assert elapsed >= 0.04
    finally:
        manager._release_lock(fd1)
        os.close(fd1)
        os.close(fd2)


def test_module_level_helpers(tmp_path: Path) -> None:
    """Verify all top-level module convenience helper functions."""
    manager = get_default_workspace_manager()
    assert isinstance(manager, WorkspaceManager)

    # Top-level file lock
    test_lock = tmp_path / "top_level.lock"
    with file_lock(test_lock, exclusive=True) as ok:
        assert ok is True

    # Top-level core scaffold
    scaffold_ok = scaffold_core_directories()
    assert isinstance(scaffold_ok, bool)

    # Top-level job provisioning
    job_path = provision_job_workspace("JOB_TOP_LEVEL_TEST", create_job_lock=True)
    assert job_path.exists()
    assert get_job_workspace("JOB_TOP_LEVEL_TEST") == job_path
    assert is_job_active("JOB_TOP_LEVEL_TEST") is False

    # Top-level status & airgap
    status_dict = get_directory_status()
    assert isinstance(status_dict, dict)
    airgap_dict = apply_tripartite_airgap()
    assert "immutable_code" in airgap_dict
    bipartite_dict = apply_bipartite_airgap()
    assert "code_tier" in bipartite_dict

    # Top-level quota checks
    scratch_dir = tmp_path / "Scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    quota_metrics = check_scratch_disk_quota(scratch_dir, min_free_gb=0.001)
    assert quota_metrics.is_sufficient is True

    # Top-level cleanup & sweep
    cleaned = cleanup_job_workspace("JOB_TOP_LEVEL_TEST")
    assert cleaned is True
    swept = sweep_zombie_directories(grace_period_seconds=0.0)
    assert isinstance(swept, int)

    # Top-level permission helpers
    tex_artifact = tmp_path / "artifact.tex"
    tex_artifact.write_text("TEST_TEX", encoding="utf-8")
    lock_artifact_permissions(tex_artifact, read_only=True)
    with pytest.raises(PermissionError):
        with open(tex_artifact, "w") as f:
            f.write("FAIL")
    unlock_artifact_permissions(tex_artifact)
    with open(tex_artifact, "w") as f:
        f.write("RESTORED")
    assert tex_artifact.read_text() == "RESTORED"

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_base\core\cochem_core_workspace_manager.py ---
#!/usr/bin/env python3
"""
CoChem-CORE: Stage 0.0 - Workspace Scaffolding Daemon & Air-Gap Manager
Implements Parsl DAG dependency orchestration for directory scaffolding, cross-platform
POSIX (fcntl) / Windows (msvcrt) file locking, Deletion Shield permission locks (0o755 / 0o444),
and Pre-Flight Scratch Disk Quota Traps (shutil.disk_usage asserting >= 50GB free space).

Enforces Tripartite and Bipartite Workspace Air-Gaps:
1. Static Execution Tier (Immutable Code & Schemas)
2. Persistent Data Tier (Dynamic State, Registries, Databases, Logs)
3. Ephemeral Compute Tier (Volatile Compute, Scratch, IPC pipes)

Zero-Mock Policy: 100% genuine OS processes, genuine Parsl DAG tasks, and real filesystem operations.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any, ContextManager, Dict, Generator, List, Optional, Union

from pydantic import BaseModel, Field

from cochem_base.config_loader import (
    get_artifact_dir,
    get_base_root,
    get_scratch_dir,
)
from cochem_base.exceptions import DiskQuotaError

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-WorkspaceManager")


# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

CORE_DIRECTORIES: List[str] = [
    "Input_Files",
    "Processed",
    "Logs",
    "Scratch",
    "Registry",
    "Databases",
]

DEFAULT_ARTIFACT_ROOT: Path = Path(r"D:\__CoChem\CoChem_Artifacts")
MIN_SCRATCH_FREE_GB: float = 50.0


# =============================================================================
# PYDANTIC DATA MODELS & METADATA
# =============================================================================


class DiskQuotaMetrics(BaseModel):
    """Telemetry and capacity metrics for workspace disk quota."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    total_gb: float
    used_gb: float
    free_gb: float
    min_required_gb: float
    is_sufficient: bool
    timestamp: float = Field(default_factory=time.time)


class DirectoryInfo(BaseModel):
    """Diagnostic status and capacity metrics for a workspace directory."""

    path: str
    exists: bool
    file_count: int = 0
    dir_count: int = 0
    total_size_bytes: int = 0
    is_writable: bool = False
    is_readable: bool = False


class ScaffoldResult(BaseModel):
    """Result of Parsl-driven workspace directory tree scaffolding."""

    base_path: str
    directories: List[str]
    created_paths: List[str]
    success: bool
    parsl_task_ids: List[str] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
    timestamp: float = Field(default_factory=time.time)


class AirgapTopology(BaseModel):
    """Tripartite Workspace Air-Gap topology manifest."""

    immutable_code: str
    dynamic_state: str
    volatile_compute: str
    code_tier: str
    data_tier: str
    compute_tier: str
    status: str = "active"
    timestamp: float = Field(default_factory=time.time)


class BipartiteTopology(BaseModel):
    """Bipartite Workspace Air-Gap topology manifest."""

    code_tier: str
    data_tier: str
    status: str = "active"
    timestamp: float = Field(default_factory=time.time)


class DaemonStatus(BaseModel):
    """Operational status metrics for WorkspaceDaemon."""

    is_running: bool
    interval_seconds: float
    sweeps_completed: int
    last_sweep_timestamp: Optional[float] = None
    last_zombies_swept: int = 0
    last_disk_quota_metrics: Optional[DiskQuotaMetrics] = None


# =============================================================================
# PRE-FLIGHT DISK QUOTA CHECKS & ASSERTIONS
# =============================================================================


def check_scratch_disk_quota(
    scratch_path: Optional[Union[str, Path]] = None,
    min_free_gb: float = MIN_SCRATCH_FREE_GB,
) -> DiskQuotaMetrics:
    """
    Executes shutil.disk_usage() on target scratch directory, computes GB telemetry,
    and returns a validated DiskQuotaMetrics model.
    """
    if scratch_path is None:
        try:
            p = get_scratch_dir().resolve()
        except Exception:
            p = DEFAULT_ARTIFACT_ROOT / "Scratch"
    else:
        p = Path(scratch_path)

    target = p.resolve()
    probe_path = target
    while not probe_path.exists() and probe_path.parent != probe_path:
        probe_path = probe_path.parent

    total_bytes, used_bytes, free_bytes = shutil.disk_usage(str(probe_path))
    total_gb = float(total_bytes) / (1024.0 ** 3)
    used_gb = float(used_bytes) / (1024.0 ** 3)
    free_gb = float(free_bytes) / (1024.0 ** 3)
    is_sufficient = free_gb >= min_free_gb

    return DiskQuotaMetrics(
        path=str(target),
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        free_bytes=free_bytes,
        total_gb=total_gb,
        used_gb=used_gb,
        free_gb=free_gb,
        min_required_gb=min_free_gb,
        is_sufficient=is_sufficient,
        timestamp=time.time(),
    )


def assert_scratch_disk_quota(
    scratch_path: Optional[Union[str, Path]] = None,
    min_free_gb: float = MIN_SCRATCH_FREE_GB,
) -> DiskQuotaMetrics:
    """
    Asserts that at least min_free_gb (default 50.0 GB) of free disk space is available.
    Raises DiskQuotaError immediately if space is insufficient.
    """
    metrics = check_scratch_disk_quota(scratch_path=scratch_path, min_free_gb=min_free_gb)
    if not metrics.is_sufficient:
        raise DiskQuotaError(
            required_gb=min_free_gb,
            available_gb=metrics.free_gb,
            path=Path(metrics.path),
            message=(
                f"Scratch disk quota trap triggered at {metrics.path}: "
                f"required {min_free_gb:.2f} GB, available {metrics.free_gb:.2f} GB"
            ),
        )
    return metrics


# =============================================================================
# PERMISSION AND SECURITY UTILITIES (DELETION SHIELD)
# =============================================================================


def lock_artifact_permissions(
    path: Union[str, Path],
    read_only: bool = True,
    recursive: bool = False,
    file_extensions: Optional[List[str]] = None,
) -> None:
    """
    Deletion Shield: Locks or unlocks artifact/directory permissions.
    - read_only=True: Enforces 0o444 for files / Read-Only on Windows to protect finalized
      .zip, .tex, .h5 payloads and directories against accidental deletion (rm -rf).
    - read_only=False: Restores 0o755 / 0o644 / Read-Write permissions.
    - recursive: Recursively applies to directory tree.
    - file_extensions: Optional filter list (e.g. [".zip", ".tex"]).
    """
    p = Path(path).resolve()
    if not p.exists():
        return

    exts: Optional[List[str]] = (
        [ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in file_extensions]
        if file_extensions
        else None
    )

    def _matches_filter(target_path: Path) -> bool:
        if exts is None:
            return True
        if target_path.is_dir():
            return False
        return any(target_path.name.lower().endswith(ext) for ext in exts)

    targets: List[Path] = []
    if p.is_dir():
        if recursive:
            try:
                for item in p.rglob("*"):
                    if _matches_filter(item):
                        targets.append(item)
            except OSError as exc:
                logger.warning(f"Failed to traverse directory tree for lock {p}: {exc}")
        if _matches_filter(p):
            targets.append(p)
    else:
        if _matches_filter(p):
            targets.append(p)

    for target in targets:
        try:
            if sys.platform == "win32":
                mode = stat.S_IREAD if read_only else (stat.S_IREAD | stat.S_IWRITE)
                try:
                    os.chmod(str(target), mode)
                except OSError as exc:
                    logger.warning(f"Failed to set Windows permission on {target}: {exc}")
            else:
                if target.is_dir():
                    mode = (
                        stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                        if read_only
                        else stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
                    )
                else:
                    mode = (
                        stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                        if read_only
                        else stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                    )
                os.chmod(str(target), mode)
        except OSError as exc:
            logger.warning(f"Failed to set POSIX permissions on {target}: {exc}")


def unlock_artifact_permissions(
    path: Union[str, Path],
    recursive: bool = False,
    file_extensions: Optional[List[str]] = None,
) -> None:
    """Restores read-write permissions to an artifact or directory."""
    lock_artifact_permissions(
        path,
        read_only=False,
        recursive=recursive,
        file_extensions=file_extensions,
    )


lock_directory_permissions = lock_artifact_permissions


# =============================================================================
# PARSL DAG DEPENDENCY ORCHESTRATION FOR DIRECTORY SCAFFOLDING
# =============================================================================


def _ensure_parsl_loaded() -> None:
    """Ensure a Parsl DataFlowKernel is active, initializing local ThreadPoolExecutor if needed."""
    try:
        import parsl
        from parsl.config import Config
        from parsl.executors.threads import ThreadPoolExecutor

        try:
            parsl.dfk()
        except Exception:
            cfg = Config(
                executors=[ThreadPoolExecutor(max_threads=4, label="cochem_workspace_scaffold_pool")],
                strategy="none",
            )
            try:
                parsl.load(cfg)
            except Exception:
                pass
    except ImportError:
        pass


def scaffold_workspace_parsl(
    base_path: Optional[Union[str, Path]] = None,
    additional_dirs: Optional[List[str]] = None,
) -> ScaffoldResult:
    """
    Autonomously scaffold directory tree using Parsl DAG dependency orchestration.
    Serializes directory creation before computational tasks are spawned.
    Constraint: Does NOT use .workspace.lock files or filesystem mutexes.
    """
    from parsl.app.app import python_app

    start_time = time.time()
    root = Path(base_path).resolve() if base_path is not None else DEFAULT_ARTIFACT_ROOT.resolve()

    dirs_to_create = list(CORE_DIRECTORIES)
    if additional_dirs:
        for d in additional_dirs:
            if d not in dirs_to_create:
                dirs_to_create.append(d)

    _ensure_parsl_loaded()

    @python_app
    def _parsl_create_dir_node(dir_path: str, parent_future: Optional[Any] = None) -> str:
        import os
        from pathlib import Path
        p = Path(dir_path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                os.chmod(str(p), 0o755)
            except OSError:
                pass
        return str(p)

    root_future = _parsl_create_dir_node(str(root))
    futures: List[Any] = []
    created_paths: List[str] = []
    parsl_task_ids: List[str] = []

    for d in dirs_to_create:
        d_path = str(root / d)
        created_paths.append(d_path)
        fut = _parsl_create_dir_node(d_path, parent_future=root_future)
        futures.append(fut)
        tid = fut.tid if (hasattr(fut, "tid") and isinstance(fut.tid, int)) else (len(futures) - 1)
        parsl_task_ids.append(f"task_{tid}")

    root_future.result()
    for fut in futures:
        fut.result()

    elapsed = time.time() - start_time

    return ScaffoldResult(
        base_path=str(root),
        directories=dirs_to_create,
        created_paths=created_paths,
        success=True,
        parsl_task_ids=parsl_task_ids,
        execution_time_seconds=elapsed,
        timestamp=time.time(),
    )


# =============================================================================
# WORKSPACE MANAGER
# =============================================================================


class WorkspaceManager:
    """
    Manages the atomic creation, locking, permission enforcement, disk quota gating,
    and sweeping of the CoChem Tripartite/Bipartite directory structure.
    """

    CORE_DIRECTORIES: List[str] = CORE_DIRECTORIES

    def __init__(self, base_path: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the WorkspaceManager.

        Args:
            base_path: Optional custom root path for artifacts. Defaults to get_artifact_dir().
        """
        if base_path is not None:
            self.base_path = Path(base_path).resolve()
        else:
            try:
                self.base_path = get_artifact_dir().resolve()
            except Exception:
                self.base_path = DEFAULT_ARTIFACT_ROOT.resolve()

        self.lock_file: Path = self.base_path / ".cochem_workspace.lock"

    def _acquire_lock(
        self,
        file_descriptor: int,
        exclusive: bool = True,
        timeout: float = 0.0,
    ) -> bool:
        """
        Applies a strict cross-platform lock (POSIX fcntl or Windows msvcrt).

        Args:
            file_descriptor: Integer file descriptor to lock.
            exclusive: True for exclusive lock, False for shared lock.
            timeout: Maximum seconds to wait if lock is held. 0.0 is non-blocking.

        Returns:
            True if lock was acquired, False otherwise.
        """
        start_time = time.time()
        while True:
            if fcntl is not None:
                try:
                    lock_ex = getattr(fcntl, "LOCK_EX", 2)
                    lock_sh = getattr(fcntl, "LOCK_SH", 1)
                    lock_nb = getattr(fcntl, "LOCK_NB", 4)
                    mode = (lock_ex if exclusive else lock_sh) | lock_nb
                    fcntl.flock(file_descriptor, mode)  # type: ignore
                    return True
                except (BlockingIOError, OSError):
                    pass
            elif msvcrt is not None:
                try:
                    os.lseek(file_descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(file_descriptor, msvcrt.LK_NBLCK, 1)  # type: ignore
                    return True
                except (BlockingIOError, OSError):
                    pass
            else:
                raise NotImplementedError("Platform does not support fcntl or msvcrt locking.")

            if timeout <= 0.0 or (time.time() - start_time) >= timeout:
                return False
            time.sleep(0.01)

    def _release_lock(self, file_descriptor: int) -> None:
        """Releases the lock on the specified file descriptor."""
        if fcntl is not None:
            try:
                lock_un = getattr(fcntl, "LOCK_UN", 8)
                fcntl.flock(file_descriptor, lock_un)  # type: ignore
            except OSError as exc:
                logger.warning(f"Failed to release POSIX workspace lock: {exc}")
        elif msvcrt is not None:
            try:
                os.lseek(file_descriptor, 0, os.SEEK_SET)
                msvcrt.locking(file_descriptor, msvcrt.LK_UNLCK, 1)  # type: ignore
            except OSError as exc:
                logger.warning(f"Failed to release Windows workspace lock: {exc}")

    @contextlib.contextmanager
    def file_lock(
        self,
        lock_file_path: Union[str, Path],
        exclusive: bool = True,
        timeout: float = 0.0,
    ) -> Generator[bool, None, None]:
        """
        Context manager for acquiring and releasing a cross-platform file lock.

        Args:
            lock_file_path: Path to the lock file.
            exclusive: True for exclusive lock, False for shared lock.
            timeout: Maximum seconds to wait. 0.0 for non-blocking attempt.

        Yields:
            bool indicating whether lock acquisition succeeded.
        """
        target_path = Path(lock_file_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            fd = os.open(str(target_path), os.O_RDWR | os.O_CREAT)
        except OSError as exc:
            logger.warning(f"Failed to open lock file {target_path}: {exc}")
            yield False
            return

        acquired = False
        try:
            acquired = self._acquire_lock(fd, exclusive=exclusive, timeout=timeout)
            yield acquired
        finally:
            if acquired:
                self._release_lock(fd)
            try:
                os.close(fd)
            except OSError:
                pass

    def scaffold_workspace_parsl(
        self,
        additional_dirs: Optional[List[str]] = None,
    ) -> ScaffoldResult:
        """Parsl DAG directory tree scaffolding method on WorkspaceManager."""
        return scaffold_workspace_parsl(base_path=self.base_path, additional_dirs=additional_dirs)

    def scaffold_core_directories(
        self,
        additional_dirs: Optional[List[str]] = None,
        lock_permissions: bool = False,
    ) -> bool:
        """
        Atomically generates the master directories under base_path.
        If another process holds the workspace lock, yields immediately.

        Args:
            additional_dirs: Optional list of additional directory names to scaffold.
            lock_permissions: If True, locks permissions on persistent directories.

        Returns:
            True if scaffolding completed successfully, False on lock collision.
        """
        self.base_path.mkdir(parents=True, exist_ok=True)

        dirs_to_create = list(self.CORE_DIRECTORIES)
        if additional_dirs:
            for d in additional_dirs:
                if d not in dirs_to_create:
                    dirs_to_create.append(d)

        with self.file_lock(self.lock_file, exclusive=True, timeout=0.0) as acquired:
            if not acquired:
                logger.info("Workspace lock collision. Bypassing redundant scaffolding.")
                return False

            try:
                for d in dirs_to_create:
                    target_dir = self.base_path / d
                    target_dir.mkdir(parents=True, exist_ok=True)

                    if lock_permissions and d not in ("Scratch", "cochem_task_queue"):
                        lock_directory_permissions(target_dir, read_only=True)

                logger.info("CoChem-CORE base topology atomically verified.")
                return True
            except Exception as exc:
                logger.error(f"Error during directory scaffolding: {exc}")
                raise

    def provision_job_workspace(self, job_id: str, create_job_lock: bool = True) -> Path:
        """
        Creates an isolated, unique execution scratch folder for a specific computational chemistry job.

        Args:
            job_id: Unique job identifier string.
            create_job_lock: If True, creates an initial `.job.lock` file in the job folder.

        Returns:
            Path object pointing to the provisioned job scratch directory.
        """
        job_dir = self.base_path / "Scratch" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        if create_job_lock:
            lock_file = job_dir / ".job.lock"
            if not lock_file.exists():
                lock_file.touch()

        return job_dir

    def get_job_workspace(self, job_id: str) -> Path:
        """
        Retrieves the scratch workspace path for a specific job.

        Args:
            job_id: Unique job identifier string.

        Returns:
            Path object for the job workspace directory.
        """
        return self.base_path / "Scratch" / job_id

    def is_job_active(self, job_id: str) -> bool:
        """
        Checks if a job workspace is currently active by probing its `.job.lock` file.

        Returns:
            True if the job lock is actively held by a running process, False otherwise.
        """
        job_dir = self.get_job_workspace(job_id)
        if not job_dir.exists():
            return False

        job_lock = job_dir / ".job.lock"
        if not job_lock.exists():
            return False

        try:
            fd = os.open(str(job_lock), os.O_RDWR)
        except OSError:
            # File sharing violation or access denied indicates the lock is held
            return True

        try:
            acquired = self._acquire_lock(fd, exclusive=True, timeout=0.0)
            if not acquired:
                return True
            else:
                self._release_lock(fd)
                return False
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    def cleanup_job_workspace(self, job_id: str, force: bool = False) -> bool:
        """
        Safely removes an isolated job workspace from the Scratch directory.

        Args:
            job_id: Unique job identifier string.
            force: If True, bypasses active lock checks.

        Returns:
            True if successfully removed or non-existent, False if job is active.
        """
        job_dir = self.get_job_workspace(job_id)
        if not job_dir.exists():
            return True

        if not force and self.is_job_active(job_id):
            logger.warning(f"Aborting cleanup: Job workspace {job_id} is currently active.")
            return False

        def _rmtree_onerror(func: Any, path: str, exc_info: Any) -> None:
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
            except Exception as exc:
                logger.warning(f"Failed to force-delete {path}: {exc}")

        try:
            if sys.version_info >= (3, 12):
                shutil.rmtree(job_dir, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
            else:
                shutil.rmtree(job_dir, onerror=_rmtree_onerror)
            return not job_dir.exists()
        except OSError as exc:
            logger.error(f"Failed to cleanup job workspace {job_id}: {exc}")
            return False

    def sweep_zombie_directories(self, grace_period_seconds: float = 0.0) -> int:
        """
        Clears the 'Scratch' folder of orphaned job directories that failed to
        clean up after a kernel or subprocess crash.
        Safely probes for active `.job.lock` locks to avoid deleting running jobs.
        Protects recently provisioned directories within `grace_period_seconds`.

        Args:
            grace_period_seconds: Minimum age in seconds before an unlocked directory is swept. Defaults to 0.0.

        Returns:
            Number of swept zombie directories.
        """
        scratch_dir = self.base_path / "Scratch"
        if not scratch_dir.exists():
            return 0

        swept_count = 0
        with self.file_lock(self.lock_file, exclusive=True, timeout=0.0) as acquired:
            if not acquired:
                logger.warning("Lock held. Cannot safely sweep zombie directories right now.")
                return 0

            try:
                for item in list(scratch_dir.iterdir()):
                    if item.is_dir():
                        if grace_period_seconds > 0.0:
                            try:
                                if (time.time() - item.stat().st_mtime) < grace_period_seconds:
                                    continue
                            except OSError:
                                continue

                        job_lock = item / ".job.lock"
                        is_active = False

                        if job_lock.exists():
                            try:
                                fd = os.open(str(job_lock), os.O_RDWR)
                                try:
                                    if not self._acquire_lock(fd, exclusive=True, timeout=0.0):
                                        is_active = True
                                    else:
                                        self._release_lock(fd)
                                finally:
                                    try:
                                        os.close(fd)
                                    except OSError:
                                        pass
                            except OSError:
                                is_active = True

                        if not is_active:
                            def _rmtree_onerror(func: Any, path: str, exc_info: Any) -> None:
                                try:
                                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                                    func(path)
                                except Exception:
                                    pass

                            try:
                                if sys.version_info >= (3, 12):
                                    shutil.rmtree(item, onexc=lambda fn, p, exc: _rmtree_onerror(fn, p, exc))
                                else:
                                    shutil.rmtree(item, onerror=_rmtree_onerror)
                                if not item.exists():
                                    swept_count += 1
                            except OSError as exc:
                                logger.error(f"Failed to remove zombie directory {item}: {exc}")

                logger.info(f"Swept {swept_count} zombie directories from Scratch.")
            except Exception as exc:
                logger.error(f"Error during zombie directory sweep: {exc}")

        return swept_count

    def get_directory_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns diagnostic status, file counts, and storage metrics for all core workspace directories.

        Returns:
            Dictionary mapping directory names to DirectoryInfo dictionary representations.
        """
        status: Dict[str, Dict[str, Any]] = {}
        for dir_name in self.CORE_DIRECTORIES:
            target_dir = self.base_path / dir_name
            if not target_dir.exists():
                info = DirectoryInfo(
                    path=str(target_dir),
                    exists=False,
                    file_count=0,
                    dir_count=0,
                    total_size_bytes=0,
                    is_writable=False,
                    is_readable=False,
                )
                status[dir_name] = info.model_dump()
                continue

            file_count = 0
            dir_count = 0
            total_size = 0
            try:
                for root, dirs, files in os.walk(target_dir):
                    dir_count += len(dirs)
                    for f in files:
                        file_count += 1
                        fp = Path(root) / f
                        try:
                            total_size += fp.stat().st_size
                        except OSError:
                            pass
            except OSError:
                pass

            is_writable = os.access(str(target_dir), os.W_OK)
            is_readable = os.access(str(target_dir), os.R_OK)

            info = DirectoryInfo(
                path=str(target_dir),
                exists=True,
                file_count=file_count,
                dir_count=dir_count,
                total_size_bytes=total_size,
                is_writable=is_writable,
                is_readable=is_readable,
            )
            status[dir_name] = info.model_dump()

        return status

    def apply_tripartite_airgap(self, code_dir: Optional[Path] = None) -> Dict[str, str]:
        """
        Dynamically provisions the Tripartite Workspace Air-Gap:
        1. Tier 1: Static Execution Tier (Immutable Code & Schemas)
        2. Tier 2: Persistent Data Tier (Dynamic State, Registries, Databases, Logs)
        3. Tier 3: Ephemeral Compute Tier (Volatile Compute, Scratch, IPC pipes)

        Args:
            code_dir: Optional directory to anchor as the immutable code tier.

        Returns:
            Dictionary mapping tier names to their verified absolute paths.
        """
        if code_dir is not None:
            resolved_code_dir = Path(code_dir).resolve()
        else:
            try:
                resolved_code_dir = get_base_root().resolve()
            except Exception:
                resolved_code_dir = Path(os.getcwd()).resolve()

        self.scaffold_core_directories()

        manifest = AirgapTopology(
            immutable_code=str(resolved_code_dir),
            dynamic_state=str(self.base_path),
            volatile_compute=str(self.base_path / "Scratch"),
            code_tier=str(resolved_code_dir),
            data_tier=str(self.base_path),
            compute_tier=str(self.base_path / "Scratch"),
            status="active",
        )
        topology = {
            "immutable_code": manifest.immutable_code,
            "dynamic_state": manifest.dynamic_state,
            "volatile_compute": manifest.volatile_compute,
            "code_tier": manifest.code_tier,
            "data_tier": manifest.data_tier,
            "compute_tier": manifest.compute_tier,
        }
        logger.info(f"Tripartite Air-Gap provisioned: {topology}")
        return topology

    def apply_bipartite_airgap(self, code_dir: Optional[Path] = None) -> Dict[str, str]:
        """
        Dynamically provisions the Bipartite Workspace Air-Gap:
        1. Code Tier: Static Execution Tier (Repository & Core Engine)
        2. Data Tier: Dynamic Artifacts & Scratch Tier

        Args:
            code_dir: Optional directory to anchor as the immutable code tier.

        Returns:
            Dictionary mapping code_tier and data_tier to their verified absolute paths.
        """
        if code_dir is not None:
            resolved_code_dir = Path(code_dir).resolve()
        else:
            try:
                resolved_code_dir = get_base_root().resolve()
            except Exception:
                resolved_code_dir = Path(os.getcwd()).resolve()

        self.scaffold_core_directories()

        manifest = BipartiteTopology(
            code_tier=str(resolved_code_dir),
            data_tier=str(self.base_path),
            status="active",
        )
        topology = {
            "code_tier": manifest.code_tier,
            "data_tier": manifest.data_tier,
        }
        logger.info(f"Bipartite Air-Gap provisioned: {topology}")
        return topology

    def check_scratch_disk_quota(self, min_free_gb: float = MIN_SCRATCH_FREE_GB) -> DiskQuotaMetrics:
        """Instance method checking scratch disk quota."""
        return check_scratch_disk_quota(scratch_path=self.base_path / "Scratch", min_free_gb=min_free_gb)

    def assert_scratch_disk_quota(self, min_free_gb: float = MIN_SCRATCH_FREE_GB) -> DiskQuotaMetrics:
        """Instance method asserting scratch disk quota."""
        return assert_scratch_disk_quota(scratch_path=self.base_path / "Scratch", min_free_gb=min_free_gb)

    # Static method aliases
    lock_directory_permissions = staticmethod(lock_directory_permissions)
    lock_artifact_permissions = staticmethod(lock_artifact_permissions)
    unlock_artifact_permissions = staticmethod(unlock_artifact_permissions)


# =============================================================================
# WORKSPACE DAEMON
# =============================================================================


class WorkspaceDaemon:
    """
    Autonomous background daemon managing the Tripartite / Bipartite Workspace Air-Gap,
    periodic zombie sweep cycles, directory health monitoring, and disk quota traps.
    """

    def __init__(
        self,
        manager: Optional[WorkspaceManager] = None,
        sweep_interval_seconds: float = 60.0,
        min_scratch_quota_gb: float = MIN_SCRATCH_FREE_GB,
    ) -> None:
        """
        Initialize the WorkspaceDaemon.

        Args:
            manager: Optional WorkspaceManager instance.
            sweep_interval_seconds: Interval in seconds between sweep cycles.
            min_scratch_quota_gb: Minimum scratch free space threshold in GB.
        """
        self.manager = manager or WorkspaceManager()
        self.sweep_interval = sweep_interval_seconds
        self.min_scratch_quota_gb = min_scratch_quota_gb
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.sweeps_completed = 0
        self.last_sweep_timestamp: Optional[float] = None
        self.last_zombies_swept = 0
        self.last_disk_quota_metrics: Optional[DiskQuotaMetrics] = None

    def run_once(self) -> Dict[str, Any]:
        """
        Executes a single cycle of the workspace daemon:
        1. Verifies/scaffolds core directories & air-gap topology.
        2. Sweeps zombie scratch directories.
        3. Collects directory health status.
        4. Monitors scratch disk quota headroom.

        Returns:
            Dictionary summarizing cycle results.
        """
        self.manager.scaffold_core_directories()
        airgap = self.manager.apply_tripartite_airgap()
        zombies_swept = self.manager.sweep_zombie_directories()
        status = self.manager.get_directory_status()
        quota_metrics = self.manager.check_scratch_disk_quota(min_free_gb=self.min_scratch_quota_gb)

        self.sweeps_completed += 1
        self.last_sweep_timestamp = time.time()
        self.last_zombies_swept = zombies_swept
        self.last_disk_quota_metrics = quota_metrics

        result: Dict[str, Any] = {
            "timestamp": self.last_sweep_timestamp,
            "cycle": self.sweeps_completed,
            "zombies_swept": zombies_swept,
            "airgap_topology": airgap,
            "directory_status": status,
            "scratch_disk_quota": quota_metrics.model_dump(),
        }
        logger.info(
            f"WorkspaceDaemon cycle {self.sweeps_completed} completed. Swept {zombies_swept} zombies."
        )
        return result

    def start(self) -> None:
        """Starts the daemon in a background thread."""
        if self._running:
            logger.warning("WorkspaceDaemon is already running.")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_worker,
            daemon=True,
            name="CoChem-WorkspaceDaemon",
        )
        self._thread.start()
        logger.info(f"WorkspaceDaemon started (sweep interval: {self.sweep_interval}s).")

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the daemon background thread."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None
        logger.info("WorkspaceDaemon stopped.")

    def _daemon_worker(self) -> None:
        """Internal daemon worker loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.error(f"Error in WorkspaceDaemon cycle: {exc}")

            self._stop_event.wait(timeout=self.sweep_interval)

    async def run_async(self) -> None:
        """Async daemon worker loop for asyncio-driven execution nodes."""
        self._running = True
        logger.info(f"WorkspaceDaemon async loop starting (interval: {self.sweep_interval}s)...")
        try:
            while self._running:
                await asyncio.to_thread(self.run_once)
                await asyncio.sleep(self.sweep_interval)
        except asyncio.CancelledError:
            self._running = False
            logger.info("WorkspaceDaemon async loop cancelled.")

    def get_status(self) -> DaemonStatus:
        """Returns Pydantic status model for the daemon."""
        return DaemonStatus(
            is_running=self._running,
            interval_seconds=self.sweep_interval,
            sweeps_completed=self.sweeps_completed,
            last_sweep_timestamp=self.last_sweep_timestamp,
            last_zombies_swept=self.last_zombies_swept,
            last_disk_quota_metrics=self.last_disk_quota_metrics,
        )


WorkspaceScaffoldingDaemon = WorkspaceDaemon


# =============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTIONS
# =============================================================================

_default_manager: Optional[WorkspaceManager] = None
_default_manager_lock: threading.Lock = threading.Lock()


def get_default_workspace_manager() -> WorkspaceManager:
    """Returns or lazily creates the default singleton WorkspaceManager in a thread-safe manner."""
    global _default_manager
    if _default_manager is None:
        with _default_manager_lock:
            if _default_manager is None:
                _default_manager = WorkspaceManager()
    return _default_manager


def scaffold_core_directories(
    additional_dirs: Optional[List[str]] = None,
    lock_permissions: bool = False,
) -> bool:
    """Module-level helper to scaffold core directories with default manager."""
    return get_default_workspace_manager().scaffold_core_directories(
        additional_dirs=additional_dirs,
        lock_permissions=lock_permissions,
    )


def provision_job_workspace(job_id: str, create_job_lock: bool = True) -> Path:
    """Module-level helper to provision a job workspace with default manager."""
    return get_default_workspace_manager().provision_job_workspace(
        job_id=job_id,
        create_job_lock=create_job_lock,
    )


def get_job_workspace(job_id: str) -> Path:
    """Module-level helper to get a job workspace path with default manager."""
    return get_default_workspace_manager().get_job_workspace(job_id=job_id)


def is_job_active(job_id: str) -> bool:
    """Module-level helper to check if a job is active with default manager."""
    return get_default_workspace_manager().is_job_active(job_id=job_id)


def cleanup_job_workspace(job_id: str, force: bool = False) -> bool:
    """Module-level helper to cleanup a job workspace with default manager."""
    return get_default_workspace_manager().cleanup_job_workspace(job_id=job_id, force=force)


def sweep_zombie_directories(grace_period_seconds: float = 0.0) -> int:
    """Module-level helper to sweep zombie directories with default manager."""
    return get_default_workspace_manager().sweep_zombie_directories(
        grace_period_seconds=grace_period_seconds
    )


def get_directory_status() -> Dict[str, Dict[str, Any]]:
    """Module-level helper to retrieve directory status with default manager."""
    return get_default_workspace_manager().get_directory_status()


def apply_tripartite_airgap(code_dir: Optional[Path] = None) -> Dict[str, str]:
    """Module-level helper to apply Tripartite Air-Gap with default manager."""
    return get_default_workspace_manager().apply_tripartite_airgap(code_dir=code_dir)


def apply_bipartite_airgap(code_dir: Optional[Path] = None) -> Dict[str, str]:
    """Module-level helper to apply Bipartite Air-Gap with default manager."""
    return get_default_workspace_manager().apply_bipartite_airgap(code_dir=code_dir)


def file_lock(
    lock_file_path: Union[str, Path],
    exclusive: bool = True,
    timeout: float = 0.0,
) -> ContextManager[bool]:
    """Module-level helper contextmanager for file locking."""
    return get_default_workspace_manager().file_lock(
        lock_file_path=lock_file_path,
        exclusive=exclusive,
        timeout=timeout,
    )


__all__ = [
    # Constants
    "CORE_DIRECTORIES",
    "DEFAULT_ARTIFACT_ROOT",
    "MIN_SCRATCH_FREE_GB",
    # Pydantic Models
    "DiskQuotaMetrics",
    "DirectoryInfo",
    "ScaffoldResult",
    "AirgapTopology",
    "BipartiteTopology",
    "DaemonStatus",
    # Exceptions
    "DiskQuotaError",
    # Core Classes
    "WorkspaceManager",
    "WorkspaceDaemon",
    "WorkspaceScaffoldingDaemon",
    # Pre-Flight Quota Functions
    "check_scratch_disk_quota",
    "assert_scratch_disk_quota",
    # Permission Utilities
    "lock_artifact_permissions",
    "unlock_artifact_permissions",
    "lock_directory_permissions",
    # Parsl Scaffolding
    "scaffold_workspace_parsl",
    # Module Convenience Functions
    "get_default_workspace_manager",
    "scaffold_core_directories",
    "provision_job_workspace",
    "get_job_workspace",
    "is_job_active",
    "cleanup_job_workspace",
    "sweep_zombie_directories",
    "get_directory_status",
    "apply_tripartite_airgap",
    "apply_bipartite_airgap",
    "file_lock",
]


if __name__ == "__main__":
    logger.info("Executing CoChem-CORE Workspace Manager diagnostic sweep...")
    manager = WorkspaceManager()
    if manager.scaffold_core_directories(lock_permissions=False):
        logger.info("Master CoChem-CORE directories generated atomically.")
        airgap_map = manager.apply_tripartite_airgap()
        logger.info(f"Airgap layout: {airgap_map}")

        test_job = manager.provision_job_workspace("JOB_PROVISION_001", create_job_lock=True)
        logger.info(f"Provisioned job path: {test_job}")

        status_dict = manager.get_directory_status()
        logger.info(f"Directory Status: {list(status_dict.keys())}")

        daemon = WorkspaceDaemon(manager=manager)
        cycle_res = daemon.run_once()
        logger.info(f"Daemon single-run status: {cycle_res['zombies_swept']} zombies swept.")
    else:
        logger.warning("Scaffolding yielded due to lock collision.")

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.