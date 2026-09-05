"""Unit and integration tests for Deliverable 7: CFOUR Cartesian-to-Z-Matrix Translation &
`*CFOUR(COORD=CARTESIAN, UNITS=ANGSTROM)` Deck Generation (Suggestion #117).

Method Matrix v4 (§13, §14) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Authentic CFOUR input deck synthesis and coordinate validation.
"""
from __future__ import annotations

import pytest

from ui.voila_layout.cochem_gui_serializer import (
    cartesian_to_zmatrix,
    serialize_cfour_input,
    validate_interatomic_distances,
)

WATER_XYZ = """O   0.00000000   0.00000000   0.11779000
H   0.00000000   0.75545300  -0.47116100
H   0.00000000  -0.75545300  -0.47116100
"""

def test_cfour_cartesian_deck_units_angstrom():
    spec = {
        "method": "CCSD(T)",
        "basis": "jun-cc-pVTZ",
        "geometry": WATER_XYZ,
        "ref": "RHF",
        "title": "Water Monomer CFOUR CCSD(T)",
    }
    deck = serialize_cfour_input(spec)

    assert "*CFOUR" in deck
    assert "COORD=CARTESIAN" in deck
    assert "UNITS=ANGSTROM" in deck
    assert "CALC=CCSD(T)" in deck
    assert "BASIS=JUN-CC-PVTZ" in deck
    assert "O" in deck and "H" in deck

def test_cfour_interatomic_distance_validation():
    coords = [
        [0.0, 0.0, 0.1178],
        [0.0, 0.7555, -0.4712],
        [0.0, -0.7555, -0.4712],
    ]
    validate_interatomic_distances(coords)

    clashing_coords = [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.3],
    ]
    with pytest.raises(ValueError, match="Interatomic distance"):
        validate_interatomic_distances(clashing_coords)

def test_cfour_zmatrix_generator():
    symbols = ["O", "H", "H"]
    coords = [
        [0.0, 0.0, 0.11779],
        [0.0, 0.755453, -0.471161],
        [0.0, -0.755453, -0.471161],
    ]
    zmat_lines = cartesian_to_zmatrix(symbols, coords)
    assert len(zmat_lines) >= 3
    assert zmat_lines[0].startswith("O")
    assert zmat_lines[1].startswith("H 1")
    assert zmat_lines[2].startswith("H 1")
