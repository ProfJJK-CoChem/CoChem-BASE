"""Physical cascade failure must never manufacture a stationary energy surface."""
import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule

from cochem_base.topology.cochem_topos_crusher import (
    PhysicalCascadeCalculator, PhysicalCascadeError, RotationalSieve, TopologyCrusher,
    compute_dipole_moment, get_molsym_point_group,
)


def _hydroxyl_radical():
    radical = Atoms("OH", positions=[[0, 0, 0], [0, 0, 0.97]])
    radical.info["multiplicity"] = 2
    return radical


def test_unavailable_actual_backend_paths_raise_with_diagnostics(tmp_path):
    calculator = PhysicalCascadeCalculator(
        xtb_executable=tmp_path / "unavailable_xtb",
        mace_model=tmp_path / "unavailable_mace.model",
    )
    radical = _hydroxyl_radical()
    radical.calc = calculator
    with pytest.raises(PhysicalCascadeError) as raised:
        radical.get_forces()
    assert calculator.results == {}
    assert len(raised.value.engine_failures) == 3
    assert "unavailable_xtb" in str(raised.value)
    assert "unavailable_mace.model" in str(raised.value)
    assert "open-shell" in str(raised.value)


def test_failed_calculation_cannot_reuse_previous_physical_results(tmp_path):
    calculator = PhysicalCascadeCalculator(
        xtb_executable=tmp_path / "unavailable_xtb",
        mace_model=tmp_path / "unavailable_mace.model",
    )
    # RDKit performs an actual force-field calculation for closed-shell water.
    water = molecule("H2O")
    water.calc = calculator
    assert np.isfinite(water.get_potential_energy())
    assert water.get_forces().shape == (3, 3)
    assert calculator.results["backend"] == "RDKit MMFF94/UFF"
    radical = _hydroxyl_radical()
    radical.calc = calculator
    with pytest.raises(PhysicalCascadeError):
        radical.get_potential_energy()
    assert calculator.results == {}


@pytest.mark.parametrize("metadata", [{"multiplicity": 3}, {"charge": 1, "multiplicity": 2}])
def test_changed_electronic_state_invalidates_cached_neutral_energy(tmp_path, metadata):
    calculator = PhysicalCascadeCalculator(xtb_executable=tmp_path / "missing_xtb")
    water = molecule("H2O")
    water.calc = calculator
    assert np.isfinite(water.get_potential_energy())
    water.info.update(metadata)
    with pytest.raises(PhysicalCascadeError, match="does not parameterize molecular charge or spin"):
        water.get_potential_energy()
    assert calculator.results == {}


@pytest.mark.parametrize("metadata", [
    {"charge": 0.5}, {"charge": True}, {"multiplicity": 0},
    {"multiplicity": 2}, {"uhf": -1}, {"spin": 0.5},
])
def test_invalid_electronic_state_cannot_return_cached_physical_energy(tmp_path, metadata):
    calculator = PhysicalCascadeCalculator(xtb_executable=tmp_path / "missing_xtb")
    water = molecule("H2O")
    water.calc = calculator
    assert np.isfinite(water.get_potential_energy())
    water.info.update(metadata)
    with pytest.raises(ValueError, match="Molecular"):
        water.get_potential_energy()
    assert calculator.results == {}


def test_dipole_requires_explicit_charge_evidence():
    water = molecule("H2O")
    with pytest.raises(ValueError, match="explicit partial charges"):
        compute_dipole_moment(water.get_chemical_symbols(), water.positions)
    for charges in ([0.1], [np.nan, 0, 0]):
        with pytest.raises(ValueError, match="one finite supplied partial charge"):
            compute_dipole_moment(water.get_chemical_symbols(), water.positions, charges)


def test_rotational_sieve_records_missing_dipole_instead_of_inventing_it():
    water = molecule("H2O")
    accepted, rotation_delta, dipole_delta = RotationalSieve().evaluate_match(
        water.get_chemical_symbols(), water.positions,
        water.get_chemical_symbols(), water.positions,
    )
    assert accepted and rotation_delta == 0
    assert dipole_delta is None


def test_conformer_pipeline_preserves_absent_dipole_and_real_energy(tmp_path):
    water = molecule("H2O")
    # A perturbed molecule can inherit obsolete metadata. Its live calculator
    # must remain the authority for the new geometry's energy.
    water.info["energy_kcal"] = float("nan")
    water.calc = PhysicalCascadeCalculator(
        xtb_executable=tmp_path / "missing_xtb", mace_model=tmp_path / "missing_mace",
    )
    crusher = TopologyCrusher()
    record = crusher.process_conformer(water, source_engine="RDKit")
    assert np.isfinite(record.energy_kcal)
    assert crusher.accepted_basins[0].dipole_moment is None
    assert record.dipole_diff_debye is None
    assert any("Dipole unavailable" in entry for entry in record.audit_trail)
    duplicate = crusher.process_conformer(water, source_engine="RDKit")
    assert duplicate.status == "duplicate" and duplicate.dipole_diff_debye is None


def test_legacy_union_rejects_absent_energy_before_starting_search():
    with pytest.raises(ValueError, match="Conformer energy unavailable"):
        TopologyCrusher().deduplicate_ensemble_union(molecule("H2O"))


def test_shake_uses_actual_reference_geometry_and_constrains_bond_lengths():
    water = molecule("H2O")
    water.translate([4, 2, -3])
    result = TopologyCrusher()._apply_shake_constraints(water)
    np.testing.assert_array_equal(result.positions, water.positions)
    displaced = result.positions.copy()
    displaced[1] += [0.01, 0.02, 0.03]
    result.set_positions(displaced)
    for pair in ((0, 1), (0, 2)):
        assert result.get_distance(*pair) == pytest.approx(water.get_distance(*pair), abs=1e-10)


def test_neb_cannot_manufacture_a_barrier_from_geometry():
    from cochem_base.exceptions import EcosystemDependencyError

    water = molecule("H2O")
    with pytest.raises(EcosystemDependencyError, match="NEB barrier unavailable"):
        TopologyCrusher()._execute_jax_neb(water, water.copy())


def test_crusher_symmetry_failure_cannot_be_labeled_c1():
    from cochem_base.intake.cochem_molsym_eckart_aligner import SymmetryAnalysisError

    with pytest.raises(SymmetryAnalysisError):
        get_molsym_point_group(["H"], [[np.nan, 0, 0]])
