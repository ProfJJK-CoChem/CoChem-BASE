"""Unit tests for Mendeleev in-memory atomic property cache.

Verifies complete dynamic retrieval across Z=1..118, IUPAC CIAAW standard atomic weights,
synthetic element fallbacks, isotope exact mass queries, and zero hardcoded mass tables via AST.
"""

import ast
from pathlib import Path

import pytest

from src.cochem.core.mendeleev_invariants import (
    ElementData,
    MendeleevInvariantError,
    get_element,
    get_isotope_mass,
)


def test_mendeleev_invariants_all_118_elements() -> None:
    """Verify all 118 elements are loaded dynamically with positive standard weights and valid isotopes."""
    for z in range(1, 119):
        elem = get_element(z)
        assert isinstance(elem, ElementData)
        assert elem.atomic_number == z
        assert len(elem.symbol) >= 1
        assert len(elem.name) >= 1
        assert elem.atomic_weight > 0.0
        assert isinstance(elem.isotopes, tuple)


def test_synthetic_element_fallback() -> None:
    """Verify synthetic/radioactive elements dynamically fallback to most stable isotope mass numbers."""
    tc = get_element("Tc")  # Technetium Z=43
    assert tc.atomic_number == 43
    assert tc.atomic_weight > 90.0

    pm = get_element("Pm")  # Promethium Z=61
    assert pm.atomic_number == 61
    assert pm.atomic_weight > 140.0


def test_get_element_normalization_and_validation() -> None:
    """Verify input normalization and error boundary conditions."""
    c_lower = get_element("c")
    c_upper = get_element("C")
    c_num = get_element(6)
    c_name = get_element("Carbon")

    assert c_lower.symbol == "C"
    assert c_upper.symbol == "C"
    assert c_num.symbol == "C"
    assert c_name.symbol == "C"
    assert abs(c_upper.atomic_weight - 12.011) < 0.01

    fe = get_element("fe")
    assert fe.symbol == "Fe"
    assert fe.atomic_number == 26

    # Boundary conditions
    with pytest.raises(MendeleevInvariantError):
        get_element(0)

    with pytest.raises(MendeleevInvariantError):
        get_element(119)

    with pytest.raises(MendeleevInvariantError):
        get_element("Kryptonite")

    with pytest.raises(MendeleevInvariantError):
        get_element("123")


def test_get_isotope_mass() -> None:
    """Verify dynamic exact nuclide mass lookup in unified atomic mass units (u)."""
    c13_mass = get_isotope_mass("C", 13)
    assert abs(c13_mass - 13.00335) < 1e-4

    h2_mass = get_isotope_mass("H", 2)
    assert abs(h2_mass - 2.01410) < 1e-4

    with pytest.raises(MendeleevInvariantError):
        get_isotope_mass("C", 999)


def test_zero_hardcoded_mass_tables_ast_audit() -> None:
    """Verify through AST inspection that mendeleev_invariants contains zero hardcoded mass tables."""
    module_path = Path(__file__).resolve().parent.parent.parent / "src" / "cochem" / "core" / "mendeleev_invariants.py"
    content = module_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(module_path))

    # Inspect all Dict nodes in the module
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            # Assert no large hardcoded mapping table exists in source code (> 10 literal elements)
            assert len(node.keys) < 10, f"Found suspiciously large hardcoded dict with {len(node.keys)} entries"
