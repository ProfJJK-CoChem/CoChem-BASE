"""Physical acceptance tests for retrosynthetic topological fragmentation (BRICS and RECAP)."""

from __future__ import annotations

import pytest

from cochem.topos.fragmentation import fragment_by_brics, fragment_by_recap
from cochem.topos.models import SynthonRecord


def test_brics_fragmentation_aspirin() -> None:
    """REQ-TOPOS-003: Verify BRICS ester cleavage on Aspirin."""
    # Aspirin: 2-acetoxybenzoic acid (contains ester cleavage rule L3)
    synthons = fragment_by_brics(smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert len(synthons) >= 2
    for syn in synthons:
        assert isinstance(syn, SynthonRecord)
        assert len(syn.attachment_sites) >= 1
        assert syn.attachment_sites[0].polarity in ["donor", "acceptor", "neutral"]
        assert len(syn.elements) == len(syn.coordinates)


def test_brics_attachment_site_directionality_and_vectors() -> None:
    """REQ-TOPOS-003: Verify attachment site polar directionality and 3D connection vectors."""
    synthons = fragment_by_brics(smiles="CC(=O)Oc1ccccc1C(=O)O")
    polarities = [site.polarity for s in synthons for site in s.attachment_sites]
    # Aspirin fragments contain acceptor (carbonyl L1/L6), donor (ester oxygen L3), and neutral (aromatic L16)
    assert "acceptor" in polarities
    assert "donor" in polarities
    assert "neutral" in polarities

    # Verify non-zero connection vectors
    for syn in synthons:
        for site in syn.attachment_sites:
            vec = site.connection_vector
            norm = (vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) ** 0.5
            assert norm > 0.1, f"Connection vector length {norm} is physically too small"


def test_recap_fragmentation() -> None:
    """REQ-TOPOS-003: Verify RECAP retrosynthetic fragmentation."""
    synthons = fragment_by_recap(smiles="CC(=O)Oc1ccccc1C(=O)O")
    assert len(synthons) >= 2
    for syn in synthons:
        assert isinstance(syn, SynthonRecord)
        assert len(syn.elements) == len(syn.coordinates)
