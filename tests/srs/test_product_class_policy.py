"""Selected Chunk 17 product meanings and non-bypassable methodology gates."""
import pytest

from cochem_base.exceptions import MethodologyViolationError
from cochem_base.theory_matrix import (
    COMPLEXITY_TIERS,
    PRODUCT_CLASS_SPECS,
    LegacyMolecularProductClass,
    ProductClass,
    validate_method_matrix_compliance,
    validate_product_class_policy,
)


def test_product_taxonomy_is_explicit() -> None:
    assert "Materials" in ProductClass.PRODUCT_B.value
    assert "plane_wave" == PRODUCT_CLASS_SPECS[ProductClass.PRODUCT_B]["periodic_basis"]
    assert LegacyMolecularProductClass.PARENT_ANCHORED.value == "Parent-Anchored Complex"
    assert set(COMPLEXITY_TIERS) == {f"T{index}" for index in range(10)}


def test_screening_requires_solvation_and_tier_cap() -> None:
    assert validate_product_class_policy("A", tier="T4", solvation="SMD")
    with pytest.raises(MethodologyViolationError, match="capped"):
        validate_product_class_policy("A", tier="T5", solvation="CPCM")
    with pytest.raises(MethodologyViolationError, match="solvation"):
        validate_product_class_policy("A", tier="T3")


def test_periodic_materials_require_paw_and_plane_waves() -> None:
    assert validate_product_class_policy("B", tier="T4", periodic=True, basis="plane-wave", pseudopotential="PAW")
    with pytest.raises(MethodologyViolationError, match="plane-wave"):
        validate_product_class_policy("B", tier="T4", periodic=True, basis="def2-SVP", pseudopotential="PAW")
    with pytest.raises(MethodologyViolationError, match="PAW"):
        validate_product_class_policy("B", tier="T4", periodic=True, basis="plane-wave", pseudopotential="norm-conserving")
    with pytest.raises(MethodologyViolationError, match="Periodic"):
        validate_product_class_policy("A", tier="T4", periodic=True, solvation="SMD")


def test_spectroscopy_requires_cbs_pair_and_relaxed_ml_geometry() -> None:
    assert validate_product_class_policy("C", tier="T8", cbs_cardinal_pair=(3, 4))
    with pytest.raises(MethodologyViolationError, match="CBS"):
        validate_product_class_policy("C", tier="T8")
    with pytest.raises(MethodologyViolationError, match="relaxation"):
        validate_product_class_policy("C", tier="T8", cbs_cardinal_pair=(4, 5), geometry_source="MLFF")
    assert validate_product_class_policy("C", tier="T8", cbs_cardinal_pair=(4, 5), geometry_source="MLFF", ab_initio_relaxed=True)


@pytest.mark.parametrize("method", ["PBE0", "pbe0", "B3LYP"])
def test_dispersion_policy_closes_case_and_method_gaps(method: str) -> None:
    with pytest.raises(MethodologyViolationError):
        validate_method_matrix_compliance(method, num_fragments=2)


def test_vv10_and_legacy_override_bypasses_are_closed() -> None:
    for overrides in ({"unphysical_override": True}, {"allow_undispersed_legacy": True}):
        with pytest.raises(MethodologyViolationError, match="cannot be disabled"):
            validate_method_matrix_compliance("B3LYP", 2, **overrides)
    with pytest.raises(MethodologyViolationError):
        validate_method_matrix_compliance("wB97M-V D4", 2)
    assert validate_method_matrix_compliance("wB97M-V", 2)
    assert validate_method_matrix_compliance("PBE0-D4", 2)
    assert validate_method_matrix_compliance("CCSD(T)", 2)


def test_product_cannot_hide_high_cost_method_under_a_lower_tier() -> None:
    with pytest.raises(MethodologyViolationError, match="does not match"):
        validate_product_class_policy("A", tier="T4", method="wB97M-V def2-QZVPP", solvation="CPCM(Water)")
    assert validate_product_class_policy("A", tier="T4", method="B3LYP D3BJ def2-TZVP", solvation="CPCM(Water)")
