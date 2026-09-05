"""CoChem-TORQ: Test Absolute Prohibition of Calc_Hess true.

Compliant with Method Matrix v4 §8B.3 and Anti-Spoofing Protocol v2.
Verifies Deliverable 7:
1. Unconditional detection and excising of Calc_Hess true during optimization (! Opt) routines.
2. Automated substitution of model Hessian (InHess XTB2 or InHess Lindh).
3. Emission of structured Method Matrix violation warning.
"""

import logging
import pytest
from Libraries.cochem_torq_compiler import TorqDeckSanitizer, sanitize_orca_deck


def test_prohibition_calc_hess_true_substitutes_inhess_xtb2(caplog):
    """Pass an ORCA deck containing ! Opt and Calc_Hess true; assert stripping, substitution, and warning."""
    dirty_deck = (
        "! r2SCAN-3c Opt defgrid3 TightSCF\n"
        "%geom\n"
        "  TolE 1e-7\n"
        "  TolMaxG 1e-5\n"
        "  Calc_Hess true\n"
        "end\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    with caplog.at_level(logging.WARNING):
        clean_deck, excised = sanitize_orca_deck(dirty_deck, xtb_available=True)

    assert excised is True
    assert "Calc_Hess true" not in clean_deck
    assert "Calc_Hess" not in clean_deck
    assert "InHess XTB2" in clean_deck
    assert "METHOD_MATRIX_VIOLATION" in caplog.text


def test_prohibition_calc_hess_true_substitutes_inhess_lindh_fallback(caplog):
    """When xTB is unavailable, assert InHess Lindh is substituted."""
    dirty_deck = (
        "! wB97M-V def2-TZVP Opt\n"
        "Calc_Hess = true\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    with caplog.at_level(logging.WARNING):
        clean_deck, excised = sanitize_orca_deck(dirty_deck, xtb_available=False)

    assert excised is True
    assert "Calc_Hess" not in clean_deck
    assert "InHess Lindh" in clean_deck
    assert "METHOD_MATRIX_VIOLATION" in caplog.text


def test_clean_optimization_deck_preserved():
    """Verify that a compliant deck with InHess XTB2 is not mutated."""
    compliant_deck = (
        "! r2SCAN-3c Opt defgrid3\n"
        "%geom\n"
        "  TolE 1e-7\n"
        "  TolMaxG 1e-5\n"
        "  InHess XTB2\n"
        "end\n"
        "* xyz 0 1\n"
        "O  0.0 0.0 0.1177\n"
        "H  0.0 0.7554 -0.4708\n"
        "H  0.0 -0.7554 -0.4708\n"
        "*\n"
    )

    clean_deck, excised = sanitize_orca_deck(compliant_deck)
    assert excised is False
    assert clean_deck.strip() == compliant_deck.strip()
