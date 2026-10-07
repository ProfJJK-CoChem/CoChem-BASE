"""Scientific policy regressions; these do not claim an external engine benchmark.

Geometry checks exercise actual molecular internal-coordinate derivatives. Text
cases exercise parser grammar and rejection paths, not simulated quantum results.
"""

import numpy as np
import pytest

from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer
from cochem_base.calc.cochem_calc_input_generator import MoleculeInput, generate_orca_input
from cochem_base.calc.cochem_calc_output_parser import QuantumParser
from cochem_base.exceptions import (
    GeometryConvergenceError,
    GridSpecificationError,
    MissingDataError,
    MissingDispersionError,
    MethodologyViolationError,
    RedundantDispersionError,
    SpinContaminationError,
    TrajectoryDriftViolationError,
)
from cochem_base.geometry.constraints import (
    build_reference_co2_h2o_complex,
    build_wilson_b_matrix,
    formulate_recipe_r2_wilson_constraints,
    generate_frozen_monomer_constraints,
    validate_trajectory_monomer_drift,
)
from cochem_base.geometry.fragment_partitioner import generate_frozen_monomer_orca_block
from cochem_base.mm.quadrature_manager import GridStage, QuadratureManager


def molecule(**options):
    symbols, coordinates, _, _ = build_reference_co2_h2o_complex()
    return MoleculeInput(basin_id="policy", elements=symbols, coordinates=coordinates.tolist(), **options)


def test_grid_dimer_partition_uses_covalent_connectivity():
    from cochem_base.calc.cochem_grid_convergence import auto_partition_dimer
    symbols, coordinates, _, _ = build_reference_co2_h2o_complex()
    assert auto_partition_dimer(symbols, coordinates) == ([0, 1, 2], [3, 4, 5])
    # A single connected water molecule cannot be split at an arbitrary x plane.
    with pytest.raises(MethodologyViolationError, match="exactly two"):
        auto_partition_dimer(symbols[3:], coordinates[3:])
    # Nor may a third monomer be silently merged into the second fragment.
    with pytest.raises(MethodologyViolationError, match="found 3"):
        auto_partition_dimer(["He", "He", "He"], np.array([[0, 0, 0], [5, 0, 0], [10, 0, 0]]))


def test_grid_isotope_lookup_cannot_substitute_average_mass():
    from cochem_base.calc.cochem_grid_convergence import get_dynamic_atomic_mass
    with pytest.raises(ValueError):
        get_dynamic_atomic_mass("C", mass_number=999)


def test_grid_report_cannot_attest_missing_scf_or_grid_evidence():
    from cochem_base.calc.cochem_grid_convergence import GridConvergenceAnalyzer
    symbols, coordinates, _, _ = build_reference_co2_h2o_complex()
    analyzer = GridConvergenceAnalyzer("connectivity-and-evidence-contract")
    # Zero is just an arithmetic input for this rejection test, not a solver result.
    result = analyzer.evaluate_grid_point("DEFGRID3", 0.0, symbols, coordinates)
    assert result.scf_converged is None
    report = analyzer.compile_convergence_report([result])
    assert not report.method_matrix_compliant
    assert any("SCF" in finding for finding in report.compliance_summary)
    with pytest.raises(ValueError, match="covalent connectivity"):
        analyzer.evaluate_grid_point("DEFGRID3", 0.0, symbols, coordinates, [0, 1], [2, 3, 4, 5])


def test_grid_benchmark_requires_real_evidence_before_writing(tmp_path):
    from cochem_base.calc.cochem_grid_convergence import execute_grid_convergence_benchmark
    with pytest.raises(MissingDataError, match="Real ORCA"):
        execute_grid_convergence_benchmark(output_dir=tmp_path)
    with pytest.raises(MissingDataError, match="separately executed"):
        execute_grid_convergence_benchmark(
            output_dir=tmp_path,
            grid_outputs={"DEFGRID2": tmp_path / "absent-2.out", "DEFGRID3": tmp_path / "absent-3.out"},
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("stage", (1, 2, 3))
def test_explicit_grid_stage_written_once(stage, tmp_path, configured_registry):
    deck = generate_orca_input(molecule(grid_stage=stage), tmp_path).read_text()
    assert deck.upper().count("DEFGRID") == 1
    assert f"DEFGRID{stage}" in deck


@pytest.mark.parametrize("keyword", ("DEFGRID1 Freq", "DEFGRID2 VPT2", "DEFGRID2 AnFreq", "DEFGRID4", "GRID4", "DEFGRID1 DEFGRID3"))
def test_invalid_or_conflicting_grid_requests_fail(keyword):
    with pytest.raises(GridSpecificationError):
        molecule(theory_level=f"r2SCAN-3c {keyword}")


def test_explicit_tight_grid_preserved_and_freq_flag_executes(tmp_path, configured_registry):
    model = molecule(theory_level="r2SCAN-3c DEFGRID3", is_freq=True)
    deck = generate_orca_input(model, tmp_path).read_text()
    assert "Freq" in deck
    assert deck.upper().count("DEFGRID") == 1
    assert "DEFGRID3" in deck


@pytest.mark.parametrize("recipe, functional, grid", (("R1", "r2SCAN-3c", "DEFGRID1"), ("R2", "wB97M-V", "DEFGRID3")))
def test_recipes_freeze_both_monomers(recipe, functional, grid, tmp_path, configured_registry):
    deck = generate_orca_input(molecule(recipe=recipe), tmp_path).read_text()
    assert functional in deck
    assert grid in deck
    assert "{B 0 1 C}" in deck
    assert "{B 3 4 C}" in deck
    assert "{B 0 3 C}" not in deck
    assert "{C " not in deck


@pytest.mark.parametrize("keyword", ("Calc_Hess true", "calchess TRUE", "Calc_Hess 1"))
def test_forbidden_hessian_rejected_without_rewriting(keyword):
    with pytest.raises(ValueError, match="Calc_Hess true"):
        molecule(theory_level=f"r2SCAN-3c {keyword}")


def test_read_hessian_requires_checkpoint(tmp_path):
    with pytest.raises(ValueError, match="checkpoint"):
        molecule(initial_hessian="READ", hessian_file=tmp_path / "absent.hess")


@pytest.mark.parametrize("functional", ("wB97M-V D3BJ", "wB97X-V D4", "ωB97M-V-D3"))
def test_dispersion_gate_rejects_separate_and_embedded_flags(functional):
    with pytest.raises(RedundantDispersionError):
        ElectronicSanitizer.sanitize_dft_dispersion(functional, is_complex=True)


def test_composite_dispersion_and_native_vv10_do_not_inject_empirical_atm():
    ElectronicSanitizer.sanitize_dft_dispersion("r2SCAN-3c", is_complex=True)
    vv10 = ElectronicSanitizer.sanitize_dft_dispersion("wB97M-V", is_complex=True, num_monomers=3)
    assert vv10["requires_atm_3body"] is False
    with pytest.raises(MissingDispersionError):
        ElectronicSanitizer.sanitize_dft_dispersion("PBE0 def2-QZVPP", is_complex=True)


@pytest.mark.parametrize("functional", ("B3LYP D3", "PBE0-D3ZERO"))
def test_standard_hybrids_require_mandated_damping(functional):
    with pytest.raises(MissingDispersionError, match="D3BJ or D4"):
        ElectronicSanitizer.sanitize_dft_dispersion(functional, is_complex=True)


@pytest.mark.parametrize("method", ("MP2 cc-pVTZ", "DLPNO-CCSD(T) cc-pVQZ", "GFN2-xTB", "CASSCF NEVPT2"))
def test_dft_dispersion_gate_does_not_inject_d4_into_other_methods(method):
    result = ElectronicSanitizer.sanitize_dft_dispersion(method, is_complex=True)
    assert result["has_empirical_dispersion"] is False


def test_declared_product_policy_reaches_input_boundary():
    with pytest.raises(ValueError, match="periodic"):
        molecule(product_class="B", tier=4)
    with pytest.raises(MethodologyViolationError):
        molecule(product_class="A", tier=5, implicit_solvation="CPCM(Water)")
    molecule(product_class="A", tier=4, implicit_solvation="CPCM(Water)")
    with pytest.raises(MethodologyViolationError):
        molecule(product_class="C", tier=5)
    molecule(product_class="C", tier=5, cbs_cardinal_pair=(3, 4), theory_level="wB97M-V def2-QZVPP")


def test_inclusive_spin_boundary_requests_t9():
    with pytest.raises(SpinContaminationError) as caught:
        ElectronicSanitizer.diagnose_spin_contamination(0.825, multiplicity=2)
    assert caught.value.details["routing_tier"] == "T9"
    assert caught.value.details["is_pure"] is False


@pytest.mark.parametrize("observed", (float("nan"), float("inf"), -0.1))
def test_invalid_spin_measurements_never_pass(observed):
    with pytest.raises(ValueError):
        ElectronicSanitizer.diagnose_spin_contamination(observed, multiplicity=2)


@pytest.mark.parametrize("multiplicity", (2, True))
def test_molecular_spin_parity_and_type_checked_at_boundary(multiplicity):
    with pytest.raises(ValueError):
        molecule(multiplicity=multiplicity)


def test_final_nan_evidence_cannot_reuse_preceding_pure_or_converged_value(tmp_path):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "nonfinite_grammar.out"
    log.write_text("dE=1e-9\ndE=NaN\nORCA TERMINATED NORMALLY\n")
    assert parser.verify_scf_convergence(log) is False
    log.write_text("Expectation value of <S**2> : 0.75\nExpectation value of <S**2> : NaN\nIdeal value S*(S+1) : 0.75\n")
    with pytest.raises(ValueError):
        parser.check_spin_contamination(log)


def test_fortran_exponents_preserved_in_energy_and_scf_table(tmp_path):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "energy_grammar.out"
    log.write_text("Last Energy change ... -1.23D-09\nSCF CONVERGED AFTER 4 CYCLES\nFINAL SINGLE POINT ENERGY -1.234D+02\nORCA TERMINATED NORMALLY\n")
    assert parser.verify_scf_convergence(log)
    result = parser.parse_to_qcschema(log, "grammar", "unused-for-parser-grammar-test")
    assert result.properties.return_energy == -123.4
    assert result.properties.scf_iterations == 4


def test_quantum_parser_uses_relative_spin_and_requires_evidence(tmp_path):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "spin_grammar.out"
    log.write_text("Expectation value of <S**2> : 8.25D-1\nIdeal value S*(S+1) : 7.5D-1\n")
    with pytest.raises(SpinContaminationError):
        parser.check_spin_contamination(log)
    log.write_text("UKS\nORCA TERMINATED NORMALLY\n")
    with pytest.raises(MissingDataError):
        parser.check_spin_contamination(log)


# Exact relevant excerpts from the native ORCA 6.1.1 water HF/STO-3G run.
# Full output SHA-256:
# 9471dbfc9461b192960fa5201f13fb1efd760ac953ad46d4ccc37ffb3dadc1ff
# Excerpts test classification grammar only; physical acceptance uses full logs.
_NATIVE_RHF_STATE_EXCERPT = """  Marcos Casanova-Páez   : Triplet and SCS-CIS(D). UHF-(DLPNO)-IP/EA/STEOM-CCSD. UHF-CVS-IP/STEOM-CCSD
  Dipayan Datta          : RHF DLPNO-CCSD density
------------
SCF SETTINGS
------------
General Settings:
 Hartree-Fock type      HFTyp           .... RHF
 Total Charge           Charge          ....    0
 Multiplicity           Mult            ....    1
 Number of Electrons    NEL             ....   10
"""


@pytest.mark.parametrize("multiplicity", (None, 1))
def test_native_restricted_singlet_is_not_reclassified_by_orca_credits(tmp_path, multiplicity):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "native_rhf_state_excerpt.out"
    log.write_text(_NATIVE_RHF_STATE_EXCERPT)
    assert parser.check_spin_contamination(log, multiplicity=multiplicity)


@pytest.mark.parametrize("reference", ("UHF", "UKS", "ROHF", "unknown"))
def test_open_shell_or_unknown_scf_reference_still_requires_spin_measurement(tmp_path, reference):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "reference_rejection_grammar.out"
    # Only the actual settings field changes; RHF in the credits cannot exempt it.
    log.write_text(_NATIVE_RHF_STATE_EXCERPT.replace(".... RHF", f".... {reference}"))
    with pytest.raises(MissingDataError):
        parser.check_spin_contamination(log, multiplicity=1)


@pytest.mark.parametrize("state,multiplicity", [
    ("RHF\n", 1),
    ("|  1> ! RHF\n|  2> * xyz 0 1\n", 1),
    (" Hartree-Fock type HFTyp .... RHF\n", 1),
    (" Multiplicity Mult .... 1\n", 1),
    (" Hartree-Fock type HFTyp .... RHF\n Multiplicity Mult .... 3\n", 1),
    (" Hartree-Fock type HFTyp .... RHF\n Multiplicity Mult .... 1\n", 3),
    (" Hartree-Fock type HFTyp .... RHF\n Multiplicity Mult .... 1\n"
     " Hartree-Fock type HFTyp .... UHF\n Multiplicity Mult .... 1\n", 1),
    (" Hartree-Fock type HFTyp .... RHF\n Multiplicity Mult .... 1\n"
     " Hartree-Fock type HFTyp .... RHF\n", 1),
])
def test_missing_or_conflicting_scf_state_cannot_exempt_spin_evidence(tmp_path, state, multiplicity):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "incomplete_state_grammar.out"
    log.write_text(state)
    with pytest.raises(MissingDataError):
        parser.check_spin_contamination(log, multiplicity=multiplicity)


def test_restricted_scf_settings_never_override_measured_contamination(tmp_path):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "contaminated_restricted_state_grammar.out"
    log.write_text(_NATIVE_RHF_STATE_EXCERPT + "Expectation value of <S**2> : 0.06\n")
    with pytest.raises(SpinContaminationError):
        parser.check_spin_contamination(log, multiplicity=1)


def test_stationarity_requires_all_five_actual_values(tmp_path):
    parser = QuantumParser(str(tmp_path))
    log = tmp_path / "convergence_grammar.out"
    table = """Geometry convergence
Energy change -1e-8
RMS gradient 2e-6
MAX gradient 8e-6
RMS step 4e-5
MAX step 8e-5
THE OPTIMIZATION HAS CONVERGED
"""
    log.write_text(table)
    assert len(parser.verify_geometry_convergence(log)) == 5
    log.write_text(table.replace("MAX step 8e-5", "MAX step 2e-4"))
    with pytest.raises(GeometryConvergenceError):
        parser.verify_geometry_convergence(log)
    log.write_text(table.replace("RMS gradient 2e-6", ""))
    with pytest.raises(GeometryConvergenceError):
        parser.verify_geometry_convergence(log)
    log.write_text("ORCA TERMINATED NORMALLY\n")
    with pytest.raises(MissingDataError):
        parser.parse_residual_gradients(log)


def test_grid_progression_requires_physical_stage_two_evidence():
    assert QuadratureManager.determine_next_stage(1, 1e-4, -1e-6) == GridStage.STAGE_2
    assert QuadratureManager.determine_next_stage(2, 1e-5, -1e-7) == GridStage.STAGE_2
    assert QuadratureManager.determine_next_stage(2, 1e-5, -1e-7, 0.01) == GridStage.STAGE_3
    with pytest.raises(GridSpecificationError):
        QuadratureManager.determine_next_stage(1, -1, -1e-8)


def test_linear_and_nonlinear_wilson_rank_and_rigid_motion_invariance():
    _, coordinates, co2, water = build_reference_co2_h2o_complex()
    payload = formulate_recipe_r2_wilson_constraints()
    b_matrix = build_wilson_b_matrix(payload, coordinates)
    assert np.linalg.matrix_rank(b_matrix[:, :9]) == 4  # Linear CO2: 3N-5.
    assert np.linalg.matrix_rank(b_matrix[:, 9:]) == 3  # Nonlinear water: 3N-6.
    for indices in (co2, water):
        indices = list(indices)
        for axis in np.eye(3):
            translation = np.zeros_like(coordinates)
            translation[indices] = axis
            rotation = np.zeros_like(coordinates)
            rotation[indices] = np.cross(axis, coordinates[indices])
            np.testing.assert_allclose(b_matrix @ translation.ravel(), 0, atol=1e-12)
            np.testing.assert_allclose(b_matrix @ rotation.ravel(), 0, atol=1e-12)


def test_torsions_are_constrained_in_fragment_serializer():
    symbols = ["H", "O", "O", "H", "Ar"]
    coords = np.array([[0.9, 0.8, 0], [0, 0.7, 0], [0, -0.7, 0], [-0.9, -0.8, 0.6], [4, 0, 0]])
    payload = generate_frozen_monomer_constraints([0, 1, 2, 3], [4], symbols=symbols, coordinates=coords)
    matrix = build_wilson_b_matrix(payload, coords)
    assert np.linalg.matrix_rank(matrix) == 6
    np.testing.assert_array_equal(matrix[:, 12:], 0)
    deck = generate_frozen_monomer_orca_block([[0, 1, 2, 3], [4]], symbols, coords)
    assert "{ D 0 1 2 3 C }" in deck


@pytest.mark.parametrize("fragments", ([], [[0, 1, 2]], [[True, 2]], [[0, 1, 3], [2, 4, 5]]))
def test_fragment_serializer_rejects_empty_partial_or_disconnected_partitions(fragments):
    symbols, coords, _, _ = build_reference_co2_h2o_complex()
    with pytest.raises((ValueError, MethodologyViolationError)):
        generate_frozen_monomer_orca_block(fragments, symbols, coords)


def test_trajectory_threshold_rejects_tiny_internal_drift_but_allows_rigid_motion():
    _, coords, _, water = build_reference_co2_h2o_complex()
    moved = coords.copy()
    moved[list(water)] += [0.05, -0.2, 0.3]
    assert validate_trajectory_monomer_drift(np.array([coords, moved]), water)[0]
    moved[4] += 2e-6 * (moved[4] - moved[3]) / np.linalg.norm(moved[4] - moved[3])
    with pytest.raises(TrajectoryDriftViolationError):
        validate_trajectory_monomer_drift([coords, moved], water, raise_on_violation=True)


@pytest.mark.parametrize("bad", ([], [[[float("nan"), 0, 0]]], [[[float("inf"), 0, 0]]]))
def test_absent_or_invalid_trajectory_cannot_establish_compliance(bad):
    with pytest.raises(ValueError):
        validate_trajectory_monomer_drift(bad, [0])
