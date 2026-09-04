"""
Test Two-Stage Loose-to-Tight Optimization & Quadrature Grid Scheduling
SRS Chunk 09, Suggestion #84 (Method Matrix v4 §4.4)
Zero-Mock compliant: Real input deck validation, authentic exception checking.
"""
import pytest

from cochem_base.exceptions import MethodMatrixViolationError
from Libraries.cochem_catalog_compiler import validate_orca_deck


def test_stage1_preliminary_allows_defgrid1():
    """Verify that Stage 1 optimization input contains defgrid1 and passes when preliminary_opt=True."""
    deck_stage1 = """! B3LYP def2-SVP defgrid1 Opt
* xyz 0 1
O 0.000 0.000 0.000
H 0.000 0.757 0.586
H 0.000 -0.757 0.586
*
"""
    assert "defgrid1" in deck_stage1
    result = validate_orca_deck(deck_stage1, preliminary_opt=True, production_opt=False)
    assert result is True


def test_stage2_production_rejects_defgrid1():
    """Assert that cochem_catalog_compiler.py rejects defgrid1 when production_opt=True or Freq is present."""
    deck_invalid_prod = """! B3LYP def2-TZVP defgrid1 Opt
* xyz 0 1
O 0.000 0.000 0.000
H 0.000 0.757 0.586
H 0.000 -0.757 0.586
*
"""
    with pytest.raises(MethodMatrixViolationError) as exc_info:
        validate_orca_deck(deck_invalid_prod, preliminary_opt=False, production_opt=True)
    assert "defgrid1" in str(exc_info.value)
    assert "strictly prohibited" in str(exc_info.value)

    deck_invalid_freq = """! B3LYP def2-TZVP defgrid1 Freq
* xyz 0 1
O 0.000 0.000 0.000
H 0.000 0.757 0.586
H 0.000 -0.757 0.586
*
"""
    with pytest.raises(MethodMatrixViolationError):
        validate_orca_deck(deck_invalid_freq)


def test_stage2_production_accepts_defgrid3():
    """Verify that Stage 2 frequency / production input strictly contains defgrid3 and passes."""
    deck_stage2 = """! B3LYP def2-TZVP defgrid3 Opt Freq
* xyz 0 1
O 0.000 0.000 0.000
H 0.000 0.757 0.586
H 0.000 -0.757 0.586
*
"""
    assert "defgrid3" in deck_stage2
    result = validate_orca_deck(deck_stage2, preliminary_opt=False, production_opt=True)
    assert result is True
