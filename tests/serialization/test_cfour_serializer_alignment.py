"""
Zero-Mock Physical Validation Suite: CFOUR Deck Serialization and Coordinate Frame Alignment.
Method Matrix v4: §9, §13, §14, and SRS Chunk 4 Suggestion #38.
"""
import pytest
from pathlib import Path
from ui.voila_layout.cochem_gui_serializer import serialize_cfour_input, generate_geom_block


def test_cfour_serializer_trans_formic_acid_deck():
    """Validates that serialize_cfour_input produces authentic *CFOUR directives with

    COORD=CARTESIAN, SYMMETRY=OFF, and preserves exact 4-column Cartesian coordinates.
    """
    # Authentic physical equilibrium geometry of trans-formic acid (HCOOH)
    formic_acid_xyz = (
        "5\n"
        "trans-formic acid equilibrium\n"
        "C   0.12650000   0.39580000   0.00000000\n"
        "O   1.18970000  -0.15570000   0.00000000\n"
        "O  -1.04560000  -0.27410000   0.00000000\n"
        "H   0.13450000   1.48830000   0.00000000\n"
        "H  -1.78910000   0.34750000   0.00000000\n"
    )

    spec = {
        "title": "trans-Formic Acid CCSD(T)/ANO0 Frame Alignment",
        "method": "CCSD(T)",
        "basis": "ANO0",
        "geometry": formic_acid_xyz,
        "mult": 1,
        "ref": "RHF",
        "symmetry": "OFF",
        "vpt2": "OFF",
    }

    deck = serialize_cfour_input(spec)

    # 1. Directive validation
    assert "*CFOUR(CALC=CCSD(T),BASIS=ANO0,COORD=CARTESIAN,EXCITE=NONE" in deck
    assert "MULT=1,REF=RHF,SYMMETRY=OFF,VPT2=OFF)" in deck
    assert "SYMMETRY=OFF" in deck

    # 2. Coordinate preservation: All atoms present in order
    lines = [line.strip() for line in deck.splitlines() if line.strip()]
    atom_lines = [l for l in lines if l.startswith(("C ", "O ", "H "))]
    assert len(atom_lines) == 5, f"Expected 5 atom lines, found {len(atom_lines)}"

    elements = [l.split()[0] for l in atom_lines]
    assert elements == ["C", "O", "O", "H", "H"]

    # Verify C coordinate preservation
    c_parts = atom_lines[0].split()
    assert abs(float(c_parts[1]) - 0.1265) < 1e-6
    assert abs(float(c_parts[2]) - 0.3958) < 1e-6
    assert abs(float(c_parts[3]) - 0.0000) < 1e-6

    # Verify terminating blank lines per CFOUR specification
    assert deck.endswith("\n\n") or deck.endswith("\r\n\r\n")


def test_cfour_generate_geom_block_integration():
    """Validates generate_geom_block integration with CFOUR engine."""
    h2o_geom = "O 0.0 0.0 0.0\nH 0.0 0.757 -0.469\nH 0.0 -0.757 -0.469"
    deck = generate_geom_block(
        engine="CFOUR",
        method="CCSD(T)",
        basis="cc-pVTZ",
        geometry=h2o_geom,
        topos_heuristic="iMTD-GC",
        topos_dedup=0.05,
    )

    assert "CFOUR Geometry Parameters (Cartesian SYMMETRY=OFF Frame Alignment) [M]" in deck
    assert "*CFOUR(CALC=CCSD(T),BASIS=CC-PVTZ,COORD=CARTESIAN,EXCITE=NONE" in deck
    assert "SYMMETRY=OFF" in deck
    assert "0.00000000     0.00000000     0.00000000" in deck
    assert "0.75700000    -0.46900000" in deck
