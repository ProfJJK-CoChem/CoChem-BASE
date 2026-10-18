"""Scientific recovery advice must preserve evidence and calculation standards.

These tests exercise actual exception objects and their public serialization API;
they do not claim to execute an electronic-structure calculation.
"""

import json

import pytest

from cochem_base.exceptions import (
    BasisSetLinearDependencyError,
    CFOURExecutionError,
    CoChemError,
    ConvergenceError,
    GeometryConvergenceError,
    GridSpecificationError,
    HessianSpecificationError,
    InvalidHessianStrategyError,
    InvalidPeriodicCellError,
    InvalidRotationalAnchorError,
    KraitchmanSingularityError,
    LAMTriggerError,
    NegativeHessianFrequencyError,
    OntologicalCollisionError,
    ORCAExecutionError,
    OutOfMemoryGateError,
    ReciprocalDensityViolation,
    SCFConvergenceError,
    SpinContaminationError,
    TriagePathologyError,
)


@pytest.mark.parametrize("error_type", [SCFConvergenceError, ConvergenceError, ORCAExecutionError, CFOURExecutionError])
def test_scf_guidance_keeps_final_grid_and_does_not_invent_orbital_diagnosis(error_type):
    advice = error_type("SCF did not converge after 100 cycles").to_pedagogical_guidance()
    assert "Self-Consistent Field (SCF)" in advice
    assert "possible" in advice.lower()
    assert "DEFGRID3" in advice
    assert "DEFGRID2" not in advice.upper()
    assert "HOMO-LUMO gap closure" not in advice
    assert "near-converged" in advice
    assert "charge" in advice and "multiplicity" in advice


@pytest.mark.parametrize("error", [GeometryConvergenceError(), ConvergenceError("Geometry optimization did not converge")])
def test_geometry_convergence_is_not_misreported_as_electronic_failure(error):
    advice = error.to_pedagogical_guidance()
    assert "geometry" in advice.lower()
    assert "forces" in advice
    assert "Self-Consistent Field (SCF)" not in advice
    assert "DEFGRID3" in advice


@pytest.mark.parametrize("error_type", [BasisSetLinearDependencyError, ORCAExecutionError, CFOURExecutionError])
def test_overlap_matrix_failure_is_not_misreported_as_overlapping_atoms(error_type):
    advice = error_type("Basis set linear dependency: overlap matrix has near-zero eigenvalues").to_pedagogical_guidance()
    assert "basis set" in advice
    assert "SThresh" in advice and "DiffSThresh" in advice
    assert "THRESH 1e-6" not in advice
    assert "nuclear overlap" not in advice
    assert "diffuse" in advice and "binding" in advice


@pytest.mark.parametrize("error_type", [HessianSpecificationError, InvalidHessianStrategyError])
def test_hessian_configuration_is_not_evidence_of_an_imaginary_frequency(error_type):
    advice = error_type("Invalid initial Hessian choice").to_pedagogical_guidance()
    assert "starting" in advice
    assert "Lindh" in advice
    assert "imaginary frequency encountered" not in advice
    assert "Calc_Hess true" in advice


@pytest.mark.parametrize("error_type", [NegativeHessianFrequencyError, ORCAExecutionError, CFOURExecutionError])
def test_frequency_guidance_distinguishes_linear_molecules_and_numerical_noise(error_type):
    advice = error_type("Imaginary vibrational frequency in final analysis").to_pedagogical_guidance()
    assert "3N-6" in advice and "nonlinear" in advice
    assert "3N-5" in advice and "linear" in advice
    assert "isolated atom" in advice
    assert "numerical" in advice and "DEFGRID3" in advice
    assert "transition state" in advice and "connect" in advice
    assert "analytical Hessian" not in advice


def test_large_amplitude_motion_is_not_invented_as_an_imaginary_mode():
    advice = LAMTriggerError("Large-amplitude motion requires further analysis").to_pedagogical_guidance()
    assert "large-amplitude" in advice.lower()
    assert "harmonic" in advice
    assert "imaginary frequency encountered" not in advice


def test_other_matrix_singularities_are_not_invented_as_diffuse_basis_failure():
    advice = KraitchmanSingularityError("Isotopic coordinate solution is singular").to_pedagogical_guidance()
    assert "basis set linear dependency" not in advice
    assert "Technical diagnostics" in advice


@pytest.mark.parametrize("message", ["Negative allocation size", "SCF converged normally; property unavailable", "Cell service unavailable"])
def test_unrelated_keywords_do_not_create_a_scientific_diagnosis(message):
    advice = ORCAExecutionError(message).to_pedagogical_guidance()
    assert "Technical diagnostics" in advice


def test_typed_failure_takes_precedence_over_incidental_scf_text():
    advice = InvalidRotationalAnchorError("SCF convergence failed in the supplied reference").to_pedagogical_guidance()
    assert "rotational constants" in advice
    assert "Self-Consistent Field (SCF)" not in advice


@pytest.mark.parametrize("error_type", [OutOfMemoryGateError, ORCAExecutionError, CFOURExecutionError])
def test_memory_error_with_scf_context_does_not_suggest_scf_recovery(error_type):
    advice = error_type("SCF converged; memory allocation failed").to_pedagogical_guidance()
    assert "memory" in advice
    assert "per process" in advice
    assert "operating system" in advice
    assert "Self-Consistent Field (SCF)" not in advice


def test_domain_guidance_uses_current_chunk17_product_definitions():
    advice = OntologicalCollisionError().to_pedagogical_guidance()
    assert "Product B" in advice and "materials" in advice
    assert "Product C" in advice and "spectroscopic" in advice
    assert "Product M" not in advice


def test_kpoint_guidance_does_not_enlarge_the_physical_cell_to_evade_the_gate():
    advice = ReciprocalDensityViolation().to_pedagogical_guidance()
    assert "k-point" in advice
    assert "convergence" in advice
    assert "same physical cell" in advice
    assert "2000" not in advice


def test_rotational_guidance_allows_real_symmetric_and_linear_rotors():
    advice = InvalidRotationalAnchorError().to_pedagogical_guidance()
    assert "A >= B >= C" in advice
    assert "symmetric" in advice and "linear" in advice
    assert "A > B > C" not in advice


@pytest.mark.parametrize("error", [
    SCFConvergenceError("Electronic convergence failed"),
    GeometryConvergenceError(),
    BasisSetLinearDependencyError("Overlap matrix is singular"),
    NegativeHessianFrequencyError("Imaginary frequency"),
    HessianSpecificationError(),
    OutOfMemoryGateError("Insufficient memory"),
    OntologicalCollisionError(),
    ReciprocalDensityViolation(),
    InvalidRotationalAnchorError(),
    InvalidPeriodicCellError(),
    GridSpecificationError(),
    SpinContaminationError("Spin check failed"),
    TriagePathologyError("Atomic clash"),
    LAMTriggerError("Large-amplitude motion"),
    CoChemError("Unclassified calculation failure"),
])
def test_student_guidance_preserves_original_diagnostic_payload_and_requests_evidence_retention(error):
    before = error.to_json()
    advice = error.to_pedagogical_guidance()
    assert "Next step:" in advice
    assert "original input" in advice
    assert "calculation output" in advice
    assert error.to_json() == before
    restored = CoChemError.from_json(before)
    assert type(restored) is type(error)
    assert restored.to_json() == before
    diagnostic = error.to_diagnostic_telemetry()
    for key, value in json.loads(before).items():
        assert diagnostic[key] == value
