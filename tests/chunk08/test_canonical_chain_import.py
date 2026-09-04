# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit test for Deliverable 8 (Suggestion #78):
Canonical State-Chaining Engine Consolidation.
Verifies that cochem_topos.chain and cochem_torq.chain successfully resolve
classes (Chain, StateChainingAuditor, ArrowState) from cochem_base.chain.
"""

from __future__ import annotations

import sys
import pytest

from cochem_base.chain import (
    Chain as BaseChain,
    StateChainingAuditor as BaseStateChainingAuditor,
    ArrowState as BaseArrowState,
)


def test_canonical_chain_import_from_satellites() -> None:
    """Verify that importing Chain, StateChainingAuditor, and ArrowState

    from cochem_topos.chain and cochem_torq.chain yields the identical classes.
    """
    import chain as topos_chain
    import Libraries.chain as torq_chain

    # Verify TOPOS chain imports match cochem_base.chain
    assert topos_chain.Chain is BaseChain
    assert topos_chain.StateChainingAuditor is BaseStateChainingAuditor
    assert topos_chain.ArrowState is BaseArrowState

    # Verify TORQ chain imports match cochem_base.chain
    assert torq_chain.Chain is BaseChain
    assert torq_chain.StateChainingAuditor is BaseStateChainingAuditor
    assert torq_chain.ArrowState is BaseArrowState
