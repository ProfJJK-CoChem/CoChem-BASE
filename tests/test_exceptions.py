"""Unit tests for the CoChem-BASE exceptions and warnings module."""

from __future__ import annotations

import asyncio
import json
import pickle
import warnings
from typing import Any, Dict

import pytest

from cochem_base.exceptions import (
    AntiSpoofingViolationError,
    BSSECorrectionError,
    CoChemBaseError,
    CoChemDeprecationWarning,
    CoChemError,
    CoChemWarning,
    ConfigError,
    ConvergenceError,
    ConvergenceWarning,
    DispatcherError,
    DispersionMissingError,
    ExceptionDeflectionBlockedError,
    FrozenMonomerViolationError,
    HardwareDetectionError,
    HardwareWarning,
    HDF5LockTimeoutError,
    InvalidHessianStrategyError,
    MethodMatrixViolationError,
    MethodMatrixWarning,
    MissingDataError,
    OutOfMemoryGateError,
    PathTraversalError,
    ProvenanceError,
    ProvenanceErrorCode,
    QCSchemaValidationError,
    RegistryLockError,
    SecurityIntegrityError,
    SecurityWarning,
    SingularityError,
    SpinContaminationError,
    TelemetryTransportError,
    TriagePathologyError,
    UnsupportedMethodError,
    cochem_error_boundary,
    cochem_error_handler,
    format_error_message,
    format_warning_message,
    wrap_exception,
)
from cochem_base.exceptions import (
    __all__ as exported_symbols,
)


class TestProvenanceErrorCode:
    """Tests for ProvenanceErrorCode enumeration members and behaviors."""

    def test_all_expected_error_codes_present(self) -> None:
        expected_members = {
            # Method Matrix & Provenance
            "METHOD_MATRIX_VIOLATION_DEFGRID": "METHOD_MATRIX_VIOLATION_DEFGRID",
            "EXCEPTION_DEFLECTION_BLOCKED": "EXCEPTION_DEFLECTION_BLOCKED",
            "MISSING_DATA": "MISSING_DATA",
            "SPIN_CONTAMINATION_EXCEEDED": "SPIN_CONTAMINATION_EXCEEDED",
            "UNSUPPORTED_METHOD": "UNSUPPORTED_METHOD",
            "DISPERSION_MISSING": "DISPERSION_MISSING",
            "INVALID_HESSIAN_STRATEGY": "INVALID_HESSIAN_STRATEGY",
            "FROZEN_MONOMER_VIOLATION": "FROZEN_MONOMER_VIOLATION",
            "PATHOLOGY_CLASH": "PATHOLOGY_CLASH",
            "TRIAGE_OVERRIDE_SPIN": "TRIAGE_OVERRIDE_SPIN",
            "AUTOFIT_LIMIT_EXCEEDED": "AUTOFIT_LIMIT_EXCEEDED",
            "EVALUATION_TIMEOUT": "EVALUATION_TIMEOUT",
            "QCSCHEMA_VALIDATION_FAILED": "QCSCHEMA_VALIDATION_FAILED",
            "BSSE_CORRECTION_FAILED": "BSSE_CORRECTION_FAILED",
            # Infrastructure & Security
            "HDF5_SWMR_LOCK_TIMEOUT": "HDF5_SWMR_LOCK_TIMEOUT",
            "REGISTRY_LOCK_TIMEOUT": "REGISTRY_LOCK_TIMEOUT",
            "INTEGRITY_VIOLATION": "INTEGRITY_VIOLATION",
            "CONFIG_VALIDATION_FAILED": "CONFIG_VALIDATION_FAILED",
            "PATH_TRAVERSAL_DETECTED": "PATH_TRAVERSAL_DETECTED",
            "TELEMETRY_FAILURE": "TELEMETRY_FAILURE",
            # Engine & Math
            "CONVERGENCE_FAILURE": "CONVERGENCE_FAILURE",
            "OUT_OF_MEMORY": "OUT_OF_MEMORY",
            "HARDWARE_DETECTION_FAILED": "HARDWARE_DETECTION_FAILED",
            "SINGULARITY_DETECTED": "SINGULARITY_DETECTED",
        }

        for name, value in expected_members.items():
            assert hasattr(ProvenanceErrorCode, name), f"Missing enum member: {name}"
            enum_val = getattr(ProvenanceErrorCode, name)
            assert enum_val.value == value
            assert isinstance(enum_val, str)

    def test_enum_instantiation_from_str(self) -> None:
        code = ProvenanceErrorCode("HDF5_SWMR_LOCK_TIMEOUT")
        assert code == ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT
        assert code == "HDF5_SWMR_LOCK_TIMEOUT"

    def test_invalid_enum_code_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            ProvenanceErrorCode("NON_EXISTENT_CODE")

    def test_from_str_classmethod(self) -> None:
        assert (
            ProvenanceErrorCode.from_str("METHOD_MATRIX_VIOLATION_DEFGRID")
            == ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID
        )
        assert (
            ProvenanceErrorCode.from_str("pathology_clash")
            == ProvenanceErrorCode.PATHOLOGY_CLASH
        )
        assert (
            ProvenanceErrorCode.from_str("  BSSE_CORRECTION_FAILED  ")
            == ProvenanceErrorCode.BSSE_CORRECTION_FAILED
        )
        assert (
            ProvenanceErrorCode.from_str(ProvenanceErrorCode.SINGULARITY_DETECTED)
            == ProvenanceErrorCode.SINGULARITY_DETECTED
        )

        with pytest.raises(ValueError, match="Unknown ProvenanceErrorCode"):
            ProvenanceErrorCode.from_str("INVALID_NONEXISTENT_CODE")

        with pytest.raises(ValueError, match="Expected str or ProvenanceErrorCode"):
            ProvenanceErrorCode.from_str(12345)  # type: ignore[arg-type]

    def test_has_code_classmethod(self) -> None:
        assert ProvenanceErrorCode.has_code("PATHOLOGY_CLASH") is True
        assert ProvenanceErrorCode.has_code("pathology_clash") is True
        assert ProvenanceErrorCode.has_code("  BSSE_CORRECTION_FAILED  ") is True
        assert ProvenanceErrorCode.has_code(ProvenanceErrorCode.OUT_OF_MEMORY) is True
        assert ProvenanceErrorCode.has_code("UNKNOWN_CODE") is False
        assert ProvenanceErrorCode.has_code(12345) is False
        assert ProvenanceErrorCode.has_code(None) is False


class TestFormatMessages:
    """Tests for format_error_message and format_warning_message utilities."""

    def test_format_without_code_or_details(self) -> None:
        msg = format_error_message(message="Simple error")
        assert msg == "Simple error"

    def test_format_with_enum_error_code(self) -> None:
        msg = format_error_message(
            error_code=ProvenanceErrorCode.SINGULARITY_DETECTED,
            message="Matrix is singular",
        )
        assert msg == "[E: SINGULARITY_DETECTED] Matrix is singular"

    def test_format_with_str_error_code(self) -> None:
        msg = format_error_message(
            error_code="CUSTOM_CODE",
            message="Custom error occurred",
        )
        assert msg == "[E: CUSTOM_CODE] Custom error occurred"

    def test_format_with_details(self) -> None:
        details: Dict[str, Any] = {"iteration": 100, "energy_diff": 1e-4}
        msg = format_error_message(
            error_code=ProvenanceErrorCode.CONVERGENCE_FAILURE,
            message="SCF did not converge",
            details=details,
        )
        assert msg == "[E: CONVERGENCE_FAILURE] SCF did not converge (details: energy_diff=0.0001, iteration=100)"

    def test_format_with_empty_details(self) -> None:
        msg = format_error_message(
            error_code=ProvenanceErrorCode.MISSING_DATA,
            message="File missing",
            details={},
        )
        assert msg == "[E: MISSING_DATA] File missing"

    def test_format_warning_message(self) -> None:
        msg = format_warning_message(
            warning_code=ProvenanceErrorCode.HARDWARE_DETECTION_FAILED,
            message="GPU NVML probe fell back to CPU",
            details={"fallback": "CPU", "device_count": 0},
        )
        assert msg == "[W: HARDWARE_DETECTION_FAILED] GPU NVML probe fell back to CPU (details: device_count=0, fallback='CPU')"

    def test_format_warning_message_simple(self) -> None:
        msg = format_warning_message(message="Generic warning message")
        assert msg == "Generic warning message"


class TestCoChemErrorBase:
    """Tests for root CoChemError exception class."""

    def test_basic_initialization(self) -> None:
        err = CoChemError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.error_code is None
        assert err.details == {}
        assert isinstance(err.timestamp, str)
        assert str(err) == "Something went wrong"
        assert repr(err) == "CoChemError('Something went wrong')"

    def test_initialization_with_enum_code_and_details(self) -> None:
        details = {"basis": "def2-TZVP", "charge": 0}
        err = CoChemError(
            message="Method error",
            error_code=ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID,
            details=details,
        )
        assert err.message == "Method error"
        assert err.error_code == ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID
        assert err.details == details
        assert str(err) == (
            "[E: METHOD_MATRIX_VIOLATION_DEFGRID] Method error "
            "(details: basis='def2-TZVP', charge=0)"
        )
        assert "error_code=<ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID" in repr(err)

    def test_initialization_with_string_code_conversion(self) -> None:
        err = CoChemError("Missing item", error_code="MISSING_DATA")
        assert err.error_code == ProvenanceErrorCode.MISSING_DATA
        assert isinstance(err.error_code, ProvenanceErrorCode)

    def test_initialization_with_unknown_string_code(self) -> None:
        err = CoChemError("Custom error", error_code="CUSTOM_UNKNOWN_CODE")
        assert err.error_code == "CUSTOM_UNKNOWN_CODE"
        assert str(err) == "[E: CUSTOM_UNKNOWN_CODE] Custom error"

    def test_to_dict_serialization(self) -> None:
        err = CoChemError(
            message="Storage lock timeout",
            error_code=ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT,
            details={"timeout_s": 5.0, "lock_file": "/tmp/lock"},
            timestamp="2026-08-18T12:00:00+00:00",
        )
        data = err.to_dict()
        assert data == {
            "error_type": "CoChemError",
            "error_code": "HDF5_SWMR_LOCK_TIMEOUT",
            "message": "Storage lock timeout",
            "details": {"timeout_s": 5.0, "lock_file": "/tmp/lock"},
            "timestamp": "2026-08-18T12:00:00+00:00",
        }

    def test_to_dict_without_code(self) -> None:
        err = CoChemError("Generic message", timestamp="2026-08-18T12:00:00+00:00")
        data = err.to_dict()
        assert data == {
            "error_type": "CoChemError",
            "error_code": None,
            "message": "Generic message",
            "details": {},
            "timestamp": "2026-08-18T12:00:00+00:00",
        }

    def test_from_dict_polymorphism(self) -> None:
        data = {
            "error_type": "BSSECorrectionError",
            "error_code": "BSSE_CORRECTION_FAILED",
            "message": "Monomer counterpoise failed",
            "details": {"monomer_idx": 1},
            "timestamp": "2026-08-18T12:00:00+00:00",
        }
        inst = CoChemError.from_dict(data)
        assert isinstance(inst, BSSECorrectionError)
        assert isinstance(inst, MethodMatrixViolationError)
        assert inst.error_code == ProvenanceErrorCode.BSSE_CORRECTION_FAILED
        assert inst.message == "Monomer counterpoise failed"
        assert inst.details == {"monomer_idx": 1}
        assert inst.timestamp == "2026-08-18T12:00:00+00:00"

    def test_to_json_and_from_json(self) -> None:
        orig = TriagePathologyError(
            message="Steric clash detected",
            details={"distance_angstrom": 0.45},
            timestamp="2026-08-18T12:00:00+00:00",
        )
        json_str = orig.to_json(indent=2)
        parsed = json.loads(json_str)
        assert parsed["error_type"] == "TriagePathologyError"
        assert parsed["error_code"] == "PATHOLOGY_CLASH"

        restored = CoChemError.from_json(json_str)
        assert isinstance(restored, TriagePathologyError)
        assert restored.message == orig.message
        assert restored.error_code == orig.error_code
        assert restored.details == orig.details
        assert restored.timestamp == orig.timestamp

    def test_from_json_invalid_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Expected JSON object"):
            CoChemError.from_json("[\"not\", \"a\", \"dict\"]")

    def test_pickle_roundtrip_multiprocessing(self) -> None:
        orig = MethodMatrixViolationError(
            message="Unsupported functional",
            error_code=ProvenanceErrorCode.UNSUPPORTED_METHOD,
            details={"functional": "LDA-old"},
            timestamp="2026-08-18T12:00:00+00:00",
        )
        pickled_bytes = pickle.dumps(orig)
        restored = pickle.loads(pickled_bytes)

        assert isinstance(restored, MethodMatrixViolationError)
        assert restored.message == orig.message
        assert restored.error_code == orig.error_code
        assert restored.details == orig.details
        assert restored.timestamp == orig.timestamp
        assert str(restored) == str(orig)

    def test_alias_cochem_base_error(self) -> None:
        assert CoChemBaseError is CoChemError
        err = CoChemBaseError("Alias error")
        assert isinstance(err, CoChemError)


class TestProvenanceAndMethodMatrixExceptions:
    """Tests for Provenance and Method Matrix domain exceptions."""

    def test_provenance_error_default(self) -> None:
        err = ProvenanceError("Provenance trace lost")
        assert err.error_code is None
        assert isinstance(err, CoChemError)
        assert str(err) == "Provenance trace lost"

    def test_method_matrix_violation_error(self) -> None:
        err = MethodMatrixViolationError("DEFGRID violation")
        assert err.error_code == ProvenanceErrorCode.METHOD_MATRIX_VIOLATION_DEFGRID
        assert isinstance(err, ProvenanceError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: METHOD_MATRIX_VIOLATION_DEFGRID] DEFGRID violation"

    def test_exception_deflection_blocked_error(self) -> None:
        err = ExceptionDeflectionBlockedError("Silent suppression blocked")
        assert err.error_code == ProvenanceErrorCode.EXCEPTION_DEFLECTION_BLOCKED
        assert isinstance(err, ProvenanceError)
        assert str(err) == "[E: EXCEPTION_DEFLECTION_BLOCKED] Silent suppression blocked"

    def test_anti_spoofing_violation_error(self) -> None:
        err = AntiSpoofingViolationError("Audit trail hash mismatch")
        assert err.error_code == ProvenanceErrorCode.INTEGRITY_VIOLATION
        assert isinstance(err, ProvenanceError)
        assert str(err) == "[E: INTEGRITY_VIOLATION] Audit trail hash mismatch"

    def test_missing_data_error(self) -> None:
        err = MissingDataError("Basis set 'def2-QZVPP' not found")
        assert err.error_code == ProvenanceErrorCode.MISSING_DATA
        assert isinstance(err, ProvenanceError)
        assert isinstance(err, KeyError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: MISSING_DATA] Basis set 'def2-QZVPP' not found"

    def test_frozen_monomer_violation_error(self) -> None:
        err = FrozenMonomerViolationError("Attempted to relax frozen monomer core")
        assert err.error_code == ProvenanceErrorCode.FROZEN_MONOMER_VIOLATION
        assert isinstance(err, MethodMatrixViolationError)
        assert isinstance(err, ProvenanceError)
        assert str(err) == "[E: FROZEN_MONOMER_VIOLATION] Attempted to relax frozen monomer core"

    def test_unsupported_method_error(self) -> None:
        err = UnsupportedMethodError("Functional 'B3LYP-old' unsupported")
        assert err.error_code == ProvenanceErrorCode.UNSUPPORTED_METHOD
        assert isinstance(err, MethodMatrixViolationError)
        assert isinstance(err, ProvenanceError)
        assert str(err) == "[E: UNSUPPORTED_METHOD] Functional 'B3LYP-old' unsupported"

    def test_triage_pathology_error(self) -> None:
        err = TriagePathologyError("Severe steric clash in geometry")
        assert err.error_code == ProvenanceErrorCode.PATHOLOGY_CLASH
        assert isinstance(err, ProvenanceError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: PATHOLOGY_CLASH] Severe steric clash in geometry"

    def test_bsse_correction_error(self) -> None:
        err = BSSECorrectionError("Counterpoise calculation failed")
        assert err.error_code == ProvenanceErrorCode.BSSE_CORRECTION_FAILED
        assert isinstance(err, MethodMatrixViolationError)
        assert isinstance(err, ProvenanceError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: BSSE_CORRECTION_FAILED] Counterpoise calculation failed"


class TestInfrastructureAndStorageExceptions:
    """Tests for Infrastructure and Storage domain exceptions."""

    def test_hdf5_lock_timeout_error(self) -> None:
        err = HDF5LockTimeoutError("Lock timeout after 30s")
        assert err.error_code == ProvenanceErrorCode.HDF5_SWMR_LOCK_TIMEOUT
        assert isinstance(err, TimeoutError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: HDF5_SWMR_LOCK_TIMEOUT] Lock timeout after 30s"

    def test_registry_lock_error(self) -> None:
        err = RegistryLockError("Registry locked by PID 1234")
        assert err.error_code == ProvenanceErrorCode.REGISTRY_LOCK_TIMEOUT
        assert isinstance(err, TimeoutError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: REGISTRY_LOCK_TIMEOUT] Registry locked by PID 1234"

    def test_security_integrity_error(self) -> None:
        err = SecurityIntegrityError("SHA-256 signature mismatch")
        assert err.error_code == ProvenanceErrorCode.INTEGRITY_VIOLATION
        assert isinstance(err, PermissionError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: INTEGRITY_VIOLATION] SHA-256 signature mismatch"

    def test_config_error(self) -> None:
        err = ConfigError("Invalid memory_limit parameter")
        assert err.error_code == ProvenanceErrorCode.CONFIG_VALIDATION_FAILED
        assert isinstance(err, ValueError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: CONFIG_VALIDATION_FAILED] Invalid memory_limit parameter"

    def test_path_traversal_error(self) -> None:
        err = PathTraversalError("Path '../etc/passwd' escapes sandbox")
        assert err.error_code == ProvenanceErrorCode.PATH_TRAVERSAL_DETECTED
        assert isinstance(err, SecurityIntegrityError)
        assert isinstance(err, PermissionError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: PATH_TRAVERSAL_DETECTED] Path '../etc/passwd' escapes sandbox"

    def test_telemetry_transport_error(self) -> None:
        err = TelemetryTransportError("Unable to reach UDP socket")
        assert err.error_code == ProvenanceErrorCode.TELEMETRY_FAILURE
        assert isinstance(err, ConnectionError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: TELEMETRY_FAILURE] Unable to reach UDP socket"

    def test_qcschema_validation_error(self) -> None:
        err = QCSchemaValidationError("Topology missing atomic numbers")
        assert err.error_code == ProvenanceErrorCode.QCSCHEMA_VALIDATION_FAILED
        assert isinstance(err, ConfigError)
        assert isinstance(err, ValueError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: QCSCHEMA_VALIDATION_FAILED] Topology missing atomic numbers"


class TestEngineAndMathExceptions:
    """Tests for Quantum Chemistry Engine and Math domain exceptions."""

    def test_convergence_error(self) -> None:
        err = ConvergenceError("SCF failed to converge in 128 cycles")
        assert err.error_code == ProvenanceErrorCode.CONVERGENCE_FAILURE
        assert isinstance(err, RuntimeError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: CONVERGENCE_FAILURE] SCF failed to converge in 128 cycles"

    def test_spin_contamination_error(self) -> None:
        err = SpinContaminationError("<S^2> = 1.05 exceeds threshold 0.75")
        assert err.error_code == ProvenanceErrorCode.SPIN_CONTAMINATION_EXCEEDED
        assert isinstance(err, ValueError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: SPIN_CONTAMINATION_EXCEEDED] <S^2> = 1.05 exceeds threshold 0.75"

    def test_dispersion_missing_error(self) -> None:
        err = DispersionMissingError("DFT calculation with wb97x omitted D3BJ dispersion")
        assert err.error_code == ProvenanceErrorCode.DISPERSION_MISSING
        assert isinstance(err, MethodMatrixViolationError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: DISPERSION_MISSING] DFT calculation with wb97x omitted D3BJ dispersion"

    def test_invalid_hessian_strategy_error(self) -> None:
        err = InvalidHessianStrategyError("Hessian strategy 'RANDOM' is invalid")
        assert err.error_code == ProvenanceErrorCode.INVALID_HESSIAN_STRATEGY
        assert isinstance(err, ValueError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: INVALID_HESSIAN_STRATEGY] Hessian strategy 'RANDOM' is invalid"

    def test_singularity_error(self) -> None:
        err = SingularityError("Overlap matrix S is rank deficient")
        assert err.error_code == ProvenanceErrorCode.SINGULARITY_DETECTED
        assert isinstance(err, ValueError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: SINGULARITY_DETECTED] Overlap matrix S is rank deficient"

    def test_out_of_memory_gate_error(self) -> None:
        err = OutOfMemoryGateError("Calculation requires 64GB RAM, only 16GB available")
        assert err.error_code == ProvenanceErrorCode.OUT_OF_MEMORY
        assert isinstance(err, MemoryError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: OUT_OF_MEMORY] Calculation requires 64GB RAM, only 16GB available"

    def test_hardware_detection_error(self) -> None:
        err = HardwareDetectionError("Failed to probe NVIDIA NVML")
        assert err.error_code == ProvenanceErrorCode.HARDWARE_DETECTION_FAILED
        assert isinstance(err, RuntimeError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: HARDWARE_DETECTION_FAILED] Failed to probe NVIDIA NVML"

    def test_dispatcher_error(self) -> None:
        err = DispatcherError("ORCA binary not found in PATH")
        assert err.error_code == ProvenanceErrorCode.UNSUPPORTED_METHOD
        assert isinstance(err, RuntimeError)
        assert isinstance(err, CoChemError)
        assert str(err) == "[E: UNSUPPORTED_METHOD] ORCA binary not found in PATH"


class TestWarnings:
    """Tests for CoChem warning hierarchy and emission."""

    def test_warning_inheritance_hierarchy(self) -> None:
        assert issubclass(CoChemWarning, UserWarning)
        assert issubclass(MethodMatrixWarning, CoChemWarning)
        assert issubclass(ConvergenceWarning, CoChemWarning)
        assert issubclass(CoChemDeprecationWarning, CoChemWarning)
        assert issubclass(CoChemDeprecationWarning, DeprecationWarning)
        assert issubclass(HardwareWarning, CoChemWarning)
        assert issubclass(SecurityWarning, CoChemWarning)

    def test_warning_emission(self) -> None:
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            warnings.warn("Grid density is minimal", MethodMatrixWarning, stacklevel=2)
            warnings.warn("SCF oscillates near threshold", ConvergenceWarning, stacklevel=2)
            warnings.warn("Legacy option 'use_legacy_grid' is deprecated", CoChemDeprecationWarning, stacklevel=2)
            warnings.warn("GPU memory headroom tight", HardwareWarning, stacklevel=2)
            warnings.warn("Insecure temp permissions", SecurityWarning, stacklevel=2)

            assert len(recorded) == 5
            assert issubclass(recorded[0].category, MethodMatrixWarning)
            assert issubclass(recorded[1].category, ConvergenceWarning)
            assert issubclass(recorded[2].category, CoChemDeprecationWarning)
            assert issubclass(recorded[3].category, HardwareWarning)
            assert issubclass(recorded[4].category, SecurityWarning)


class TestWrapExceptionUtility:
    """Tests for wrap_exception utility."""

    def test_wrap_standard_exception_to_cochem_error(self) -> None:
        orig = ValueError("Invalid matrix dimension")
        wrapped = wrap_exception(orig, target_cls=SingularityError)

        assert isinstance(wrapped, SingularityError)
        assert isinstance(wrapped, ValueError)
        assert wrapped.__cause__ is orig
        assert wrapped.error_code == ProvenanceErrorCode.SINGULARITY_DETECTED
        assert "Invalid matrix dimension" in str(wrapped)

    def test_wrap_with_message_override(self) -> None:
        orig = RuntimeError("Low-level crash")
        wrapped = wrap_exception(
            orig,
            target_cls=ConvergenceError,
            message="High level convergence failure",
            details={"step": 5},
        )

        assert isinstance(wrapped, ConvergenceError)
        assert wrapped.__cause__ is orig
        assert wrapped.message == "High level convergence failure"
        assert wrapped.details == {"step": 5}
        assert str(wrapped) == "[E: CONVERGENCE_FAILURE] High level convergence failure (details: step=5)"

    def test_wrap_idempotent_when_matching_target_class_and_no_overrides(self) -> None:
        orig = ConvergenceError("SCF failed")
        wrapped = wrap_exception(orig, target_cls=ConvergenceError)
        assert wrapped is orig

    def test_wrap_preserves_and_merges_existing_details(self) -> None:
        orig = CoChemError("Original error", details={"a": 1, "b": 2})
        wrapped = wrap_exception(orig, target_cls=CoChemError, details={"b": 3, "c": 4})

        assert wrapped is not orig
        assert wrapped.__cause__ is orig
        assert wrapped.details == {"a": 1, "b": 3, "c": 4}

    def test_wrap_with_custom_default_code(self) -> None:
        orig = FileNotFoundError("Missing file")
        wrapped = wrap_exception(
            orig,
            target_cls=CoChemError,
            default_code=ProvenanceErrorCode.MISSING_DATA,
        )
        assert wrapped.error_code == ProvenanceErrorCode.MISSING_DATA
        assert wrapped.__cause__ is orig


class TestErrorBoundaryAndDecorators:
    """Tests for cochem_error_boundary and cochem_error_handler."""

    def test_boundary_success(self) -> None:
        with cochem_error_boundary():
            x = 1 + 1
        assert x == 2

    def test_boundary_wraps_standard_exception(self) -> None:
        with pytest.raises(SingularityError) as exc_info:
            with cochem_error_boundary(
                target_cls=SingularityError,
                message="Matrix operation failed",
                details={"dim": 4},
            ):
                raise ZeroDivisionError("division by zero")

        err = exc_info.value
        assert isinstance(err, SingularityError)
        assert err.error_code == ProvenanceErrorCode.SINGULARITY_DETECTED
        assert "Matrix operation failed" in str(err)
        assert err.details == {"dim": 4}
        assert isinstance(err.__cause__, ZeroDivisionError)

    def test_boundary_suppress_when_reraise_false(self) -> None:
        with cochem_error_boundary(reraise=False):
            raise ValueError("Suppressed error")

    def test_boundary_exclude_exception(self) -> None:
        with pytest.raises(KeyError):
            with cochem_error_boundary(
                target_cls=ConvergenceError,
                exclude=(KeyError,),
            ):
                raise KeyError("Bypassed key error")

    def test_decorator_sync_bare(self) -> None:
        @cochem_error_handler
        def faulty_add(a: int, b: int) -> int:
            if a < 0:
                raise ValueError("Negative a")
            return a + b

        assert faulty_add(2, 3) == 5

        with pytest.raises(CoChemError) as exc_info:
            faulty_add(-1, 3)
        assert isinstance(exc_info.value, CoChemError)
        assert "Negative a" in str(exc_info.value)

    def test_decorator_sync_parameterized(self) -> None:
        @cochem_error_handler(
            target_cls=ConvergenceError,
            details={"subsystem": "scf_driver"},
        )
        def run_scf() -> None:
            raise RuntimeError("Damping failed")

        with pytest.raises(ConvergenceError) as exc_info:
            run_scf()
        err = exc_info.value
        assert isinstance(err, ConvergenceError)
        assert err.error_code == ProvenanceErrorCode.CONVERGENCE_FAILURE
        assert err.details == {"subsystem": "scf_driver"}

    def test_decorator_sync_suppress(self) -> None:
        @cochem_error_handler(reraise=False)
        def run_fail() -> str:
            raise ValueError("Should not crash")

        res = run_fail()
        assert res is None

    def test_decorator_sync_positional_class(self) -> None:
        @cochem_error_handler(ConvergenceError)
        def run_scf_positional() -> None:
            raise ArithmeticError("Numeric overflow")

        with pytest.raises(ConvergenceError) as exc_info:
            run_scf_positional()
        assert isinstance(exc_info.value, ConvergenceError)
        assert exc_info.value.error_code == ProvenanceErrorCode.CONVERGENCE_FAILURE

    def test_decorator_sync_empty_call(self) -> None:
        @cochem_error_handler()
        def run_generic_fail() -> None:
            raise KeyError("missing key")

        with pytest.raises(CoChemError) as exc_info:
            run_generic_fail()
        assert isinstance(exc_info.value, CoChemError)

    def test_decorator_async_bare(self) -> None:
        @cochem_error_handler
        async def async_job(val: int) -> int:
            await asyncio.sleep(0.01)
            if val < 0:
                raise ValueError("Negative val")
            return val * 2

        assert asyncio.run(async_job(10)) == 20

        with pytest.raises(CoChemError):
            asyncio.run(async_job(-5))

    def test_decorator_async_parameterized(self) -> None:
        @cochem_error_handler(
            target_cls=QCSchemaValidationError,
            details={"schema": "v2"},
        )
        async def async_validate() -> None:
            await asyncio.sleep(0.01)
            raise ValueError("Invalid basis name")

        with pytest.raises(QCSchemaValidationError) as exc_info:
            asyncio.run(async_validate())
        err = exc_info.value
        assert isinstance(err, QCSchemaValidationError)
        assert err.error_code == ProvenanceErrorCode.QCSCHEMA_VALIDATION_FAILED
        assert err.details == {"schema": "v2"}


class TestExportIntegrity:
    """Tests to ensure __all__ matches exports."""

    def test_all_symbols_exported_exist_in_module(self) -> None:
        import cochem_base.exceptions as exc_mod

        for symbol_name in exported_symbols:
            assert hasattr(exc_mod, symbol_name), f"Exported symbol '{symbol_name}' not found in module"

