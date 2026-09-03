"""Physical acceptance tests for ECFP4 / Morgan topological fingerprint generation."""

from __future__ import annotations

import pytest

from cochem.topos.fingerprint import (
    compute_dice_similarity,
    compute_tanimoto_similarity,
    generate_ecfp4_fingerprint,
)
from cochem.topos.models import ECFP4FingerprintPayload


def test_ecfp4_fingerprint_generation() -> None:
    """REQ-TOPOS-006: Verify ECFP4 fingerprint calculation and de-duplication."""
    # Generate fingerprint for Pyridine
    fp = generate_ecfp4_fingerprint(smiles="c1ccncc1", radius=2, n_bits=2048)
    assert isinstance(fp, ECFP4FingerprintPayload)
    assert len(fp.bit_vector_2048) == 2048
    assert len(fp.bit_vector_1024) == 1024
    assert len(fp.on_bits_2048) > 0
    assert fp.features_de_duplicated >= 0
    assert len(fp.count_vector) == len(fp.on_bits_2048)


def test_ecfp4_tanimoto_and_dice_similarity() -> None:
    """REQ-TOPOS-006: Verify Tanimoto and Dice similarity between pyridine and benzene."""
    fp_pyr = generate_ecfp4_fingerprint(smiles="c1ccncc1", radius=2, n_bits=2048)
    fp_benz = generate_ecfp4_fingerprint(smiles="c1ccccc1", radius=2, n_bits=2048)

    tanimoto = compute_tanimoto_similarity(fp_pyr, fp_benz)
    dice = compute_dice_similarity(fp_pyr, fp_benz)

    # Physical similarity bounds for related aromatic scaffolds
    assert 0.0 < tanimoto < 1.0, f"Expected 0.0 < T < 1.0, got {tanimoto}"
    assert 0.0 < dice < 1.0, f"Expected 0.0 < D < 1.0, got {dice}"
    assert dice > tanimoto, "Dice coefficient should be strictly greater than Tanimoto"

    # Self-similarity must be exactly 1.0
    assert compute_tanimoto_similarity(fp_pyr, fp_pyr) == 1.0
    assert compute_dice_similarity(fp_pyr, fp_pyr) == 1.0
