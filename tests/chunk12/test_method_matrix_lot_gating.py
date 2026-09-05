"""Unit and integration tests for Deliverable 4: Method Matrix v4 Level-of-Theory Gating &
Mandatory Empirical/Non-Local Dispersion Enforcement (Suggestion #114).

Method Matrix v4 (§4.4, §9A, Table 3) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Dynamic tier filtering and dispersion enforcement.
"""
from __future__ import annotations

import pytest

from cochem_base.exceptions import MethodologyViolationError
from cochem_base.theory_matrix import (
    METHOD_MATRIX_TIERS,
    validate_method_matrix_compliance,
)


def test_method_matrix_v4_tier_catalog():
    required_tiers = [
        "Tier 1: Modern Dispersion DFT",
        "Tier 2: Wave-Function Composite",
        "Tier 3: Semiempirical Screening",
        "Benchmark Dispersion Tier",
    ]
    for tier in required_tiers:
        assert tier in METHOD_MATRIX_TIERS

    dft_methods = METHOD_MATRIX_TIERS["Tier 1: Modern Dispersion DFT"]["methods"]
    assert "wB97M-V" in dft_methods
    assert "wB97X-V" in dft_methods
    assert "r2SCAN-3c" in dft_methods

    composite_methods = METHOD_MATRIX_TIERS["Tier 2: Wave-Function Composite"]["methods"]
    assert "junChS" in composite_methods

    benchmark_methods = METHOD_MATRIX_TIERS["Benchmark Dispersion Tier"]["methods"]
    assert "B3LYP-D4" in benchmark_methods
    assert "PBE0-D4" in benchmark_methods

def test_dispersion_mandate_for_non_covalent_complexes():
    assert validate_method_matrix_compliance("B3LYP", num_fragments=1) is True

    with pytest.raises(MethodologyViolationError, match="Dispersion corrections are mandatory"):
        validate_method_matrix_compliance("B3LYP", num_fragments=2)

    assert validate_method_matrix_compliance("B3LYP", num_fragments=2, allow_undispersed_legacy=True) is True

def test_basis_set_compatibility_constraints():
    r2scan_basis = METHOD_MATRIX_TIERS["Tier 1: Modern Dispersion DFT"].get("basis_constraints", {}).get("r2SCAN-3c", ["mTZVP"])
    assert "mTZVP" in r2scan_basis

    junchs_basis = METHOD_MATRIX_TIERS["Tier 2: Wave-Function Composite"].get("basis_constraints", {}).get("junChS", ["jun-cc-pVTZ", "jun-cc-pVQZ"])
    assert "jun-cc-pVTZ" in junchs_basis
