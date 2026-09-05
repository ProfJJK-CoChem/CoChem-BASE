"""CoChem-TOPOS: Test Two-Stage Integration Grid Tightening & Decoupled Frequencies.

Compliant with Method Matrix v4 §4.4, §8B, and Anti-Spoofing Directives.
Verifies Deliverable 5:
1. Canonical GridPolicy schema and grid validation across workflow phases.
2. Two-stage dynamic grid tightening (Stage 1 defgrid1 loose -> Stage 2 defgrid3 tight %geom).
3. Rejection of defgrid1 for vibrational frequency calculations (! Freq).
"""

import pytest
from cochem_base.config.grid_policy import GridPolicy, WorkflowPhase
from cascade_engine.cochem_topos_cascade_orchestrator import (
    build_two_stage_optimization_decks,
    build_vibrational_frequency_deck,
    validate_frequency_grid,
)


def test_canonical_grid_policy_validation():
    """Verify GridPolicy schema and phase-specific integration grid validation."""
    # Pre-optimization permits defgrid1 and defgrid3
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_PREOPT, "defgrid1") is True
    assert GridPolicy.validate_grid("PHASE_PREOPT", "defgrid1") is True
    assert GridPolicy.validate_grid("preopt", "defgrid3") is True

    # Final optimization strictly forbids defgrid1
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_FINALOPT, "defgrid1") is False
    assert GridPolicy.validate_grid("PHASE_FINALOPT", "defgrid1") is False
    assert GridPolicy.validate_grid("finalopt", "defgrid3") is True

    # Frequency evaluation strictly forbids defgrid1
    assert GridPolicy.validate_grid(WorkflowPhase.PHASE_NUMFREQ, "defgrid1") is False
    assert GridPolicy.validate_grid("numfreq", "defgrid1") is False
    assert GridPolicy.validate_grid("numfreq", "defgrid3") is True

    # Deprecated Grid3 / Grid5 nomenclature is unconditionally prohibited
    assert GridPolicy.validate_grid("preopt", "grid3") is False
    assert GridPolicy.validate_grid("finalopt", "grid5") is False


def test_two_stage_optimization_deck_construction():
    """Verify Stage 1 uses defgrid1 loose convergence and Stage 2 uses defgrid3 tight %geom."""
    symbols = ["O", "H", "H"]
    coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

    stage1_deck, stage2_deck = build_two_stage_optimization_decks(
        atoms=None,
        functional="r2SCAN-3c",
    )

    # Stage 1 assertions: defgrid1 with loose convergence
    assert "! r2SCAN-3c Opt" in stage1_deck
    assert "! defgrid1" in stage1_deck
    assert "TolE 1e-4" in stage1_deck
    assert "TolMaxG 1e-3" in stage1_deck
    assert "InHess XTB2" in stage1_deck
    assert "Freq" not in stage1_deck  # No Freq in Stage 1

    # Stage 2 assertions: defgrid3 with tight %geom thresholds
    assert "! r2SCAN-3c Opt" in stage2_deck
    assert "! defgrid3" in stage2_deck
    assert "TolMaxG 1e-5" in stage2_deck
    assert "TolE 1e-7" in stage2_deck
    assert "TolRMSG 3e-6" in stage2_deck
    assert "TolRMSD 5e-5" in stage2_deck
    assert "TolMaxD 1e-4" in stage2_deck
    assert "InHess XTB2" in stage2_deck
    assert "Freq" not in stage2_deck  # Decoupled from Freq!


def test_vibrational_frequencies_strictly_reject_defgrid1():
    """Verify vibrational frequency calculations reject defgrid1 and require defgrid3."""
    # Deck with ! Freq and defgrid1 must be rejected
    invalid_deck = "! r2SCAN-3c Freq\n! defgrid1\n"
    assert validate_frequency_grid(invalid_deck) is False

    # Deck with ! Freq and defgrid3 is accepted
    valid_deck = "! r2SCAN-3c Freq\n! defgrid3\n"
    assert validate_frequency_grid(valid_deck) is True

    # Deck builder raises ValueError when attempting defgrid1 with Freq
    with pytest.raises(ValueError) as excinfo:
        build_vibrational_frequency_deck(functional="r2SCAN-3c", grid="defgrid1")
    assert "defgrid1" in str(excinfo.value)
    assert "strictly prohibited" in str(excinfo.value)

    # Clean creation on defgrid3
    freq_deck = build_vibrational_frequency_deck(functional="r2SCAN-3c", grid="defgrid3")
    assert "! r2SCAN-3c Freq" in freq_deck
    assert "! defgrid3" in freq_deck
