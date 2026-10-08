"""Real MolSym classification and explicit failure of the removed heuristic."""
import numpy as np
import pytest
from ase.build import molecule

from cochem_base.intake.cochem_molsym_eckart_aligner import (
    SymmetryBackendUnavailableError,
    MassResolutionError,
    _geometric_fallback_point_group,
    analyze_molecular_symmetry,
    compute_center_of_mass,
    get_dynamic_atomic_mass,
)


@pytest.mark.parametrize("formula", ["H2O", "CH4", "C6H6"])
def test_former_heuristic_cannot_claim_a_point_group(formula):
    atoms = molecule(formula)
    symbols = atoms.get_chemical_symbols()
    masses = np.array([get_dynamic_atomic_mass(symbol) for symbol in symbols])
    with pytest.raises(SymmetryBackendUnavailableError, match="CoChem-BASE\\[symmetry\\]"):
        _geometric_fallback_point_group(atoms.positions, symbols, masses)
    # The optional backend has no role in the independent COM mathematics.
    np.testing.assert_allclose(compute_center_of_mass(atoms.positions, masses=masses),
                               np.average(atoms.positions, axis=0, weights=masses), atol=np.finfo(np.float64).eps)


@pytest.mark.parametrize("formula,point_group,sigma,centrosymmetric", [
    ("H2O", "C2v", 2, False),
    ("CH4", "Td", 12, False),
    ("C6H6", "D6h", 12, True),
    ("CO2", "D0h", 2, True),
])
def test_real_backend_classifies_reference_molecular_symmetry(formula, point_group, sigma, centrosymmetric):
    pytest.importorskip("molsym", reason="Install CoChem-BASE[symmetry] for authoritative point-group tests")
    atoms = molecule(formula)
    original = atoms.positions.copy()
    result = analyze_molecular_symmetry(atoms.positions, atoms.get_chemical_symbols())
    assert result.point_group == point_group
    assert result.rotational_symmetry_number == sigma
    assert result.is_centrosymmetric is centrosymmetric
    assert result.source == "molsym" and result.backend_version
    assert result.nuclear_spin_weights == {}
    assert "nuclear_spin_weights" in result.unavailable_properties
    if formula == "CO2":
        assert result.is_linear
        assert result.character_table == {}
        assert "infinite_group_character_table" in result.unavailable_properties
    else:
        assert len(result.symmetry_elements) >= sigma
        assert result.character_table
    np.testing.assert_array_equal(atoms.positions, original)


@pytest.mark.parametrize("tolerance", [np.nan, np.inf, 0, -1, True])
def test_symmetry_tolerance_must_be_physical(tolerance):
    atoms = molecule("H2O")
    with pytest.raises(ValueError):
        analyze_molecular_symmetry(atoms.positions, atoms.get_chemical_symbols(), tolerance=tolerance)


@pytest.mark.parametrize("label", ["999C", "C999", "C_999", "13C12", "H0"])
def test_unavailable_or_contradictory_isotope_never_becomes_standard_weight(label):
    with pytest.raises(MassResolutionError):
        get_dynamic_atomic_mass(label)


@pytest.mark.parametrize("label", ["13C", "C13", "C-13", "C_13", "C:13"])
def test_legacy_mass_map_uses_exact_dynamic_isotopes(label):
    from cochem_base.physics.isotopes import get_isotope_mass

    assert get_dynamic_atomic_mass(label) == get_isotope_mass("C", 13)
