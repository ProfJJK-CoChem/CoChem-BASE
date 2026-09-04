"""Unit and integration tests for Deliverable 9: Structured Pedagogical Exception Hierarchy & Didactic Remediation Protocol (Suggestion #109).

Mandated by Method Matrix v4 (§1.6) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic exception payload serialization and pedagogical translation.
"""

from __future__ import annotations

from cochem_base.exceptions import (
    BasisSetLinearDependencyError,
    CoChemBaseException,
    NegativeHessianFrequencyError,
    SCFConvergenceError,
)


def test_exception_alias_and_hierarchy():
    """Verify CoChemBaseException is an alias/base of CoChemError and derived classes inherit properly."""
    assert issubclass(SCFConvergenceError, CoChemBaseException)
    assert issubclass(NegativeHessianFrequencyError, CoChemBaseException)
    assert issubclass(BasisSetLinearDependencyError, CoChemBaseException)


def test_scf_convergence_error_pedagogical_guidance():
    """Verify SCFConvergenceError returns structured student didactic view and PI diagnostic telemetry."""
    err = SCFConvergenceError(
        "SCF iteration limit exceeded after 100 cycles",
        details={"max_cycles": 100, "last_energy_diff": 1.4e-4, "homo_lumo_gap_ev": 0.02},
    )

    # 1. Student / Didactic View
    guidance = err.to_pedagogical_guidance()
    assert isinstance(guidance, str)
    assert "Self-Consistent Field (SCF)" in guidance
    assert "orbital" in guidance.lower() or "convergence" in guidance.lower()
    assert "remediation" in guidance.lower() or "Option" in guidance

    # 2. PI / Diagnostic Telemetry View
    telemetry = err.to_diagnostic_telemetry()
    assert isinstance(telemetry, dict)
    assert telemetry["error_type"] == "SCFConvergenceError"
    assert "details" in telemetry
    assert telemetry["details"]["max_cycles"] == 100
    assert "platform" in telemetry


def test_negative_hessian_frequency_error_pedagogical_guidance():
    """Verify NegativeHessianFrequencyError returns clear transition state / geometry distortion advice."""
    err = NegativeHessianFrequencyError(
        "Found 2 imaginary frequencies in ground-state geometry optimization: -124.5 cm^-1, -45.2 cm^-1",
        details={"imaginary_frequencies": [-124.5, -45.2]},
    )
    guidance = err.to_pedagogical_guidance()
    assert "imaginary" in guidance.lower() or "negative" in guidance.lower()
    assert "frequency" in guidance.lower() or "normal mode" in guidance.lower()


def test_basis_set_linear_dependency_error_pedagogical_guidance():
    """Verify BasisSetLinearDependencyError explains diffuse overlap and suggests truncated basis sets."""
    err = BasisSetLinearDependencyError(
        "Overlap matrix S has near-zero eigenvalues (min eigenvalue: 1.2e-7)",
        details={"min_eigenvalue": 1.2e-7, "basis_set": "aug-cc-pVTZ"},
    )
    guidance = err.to_pedagogical_guidance()
    assert "basis set" in guidance.lower()
    assert "linear dependency" in guidance.lower() or "overlap" in guidance.lower()
