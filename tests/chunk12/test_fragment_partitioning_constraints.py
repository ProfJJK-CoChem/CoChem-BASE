"""Unit and integration tests for Deliverable 9: Bimolecular van der Waals Fragment Partitioning,
Frozen-Monomer Constraints & Tightened Convergence Enforcement (Suggestion #119).

Method Matrix v4 (§4.4, §9A) and Anti-Spoofing Protocol v4.
Strict Zero-Mock Mandate: Covalent connectivity graph partitioning and frozen monomer constraints.
"""
from __future__ import annotations

import numpy as np
import pytest

from cochem_base.exceptions import MethodologyViolationError
from cochem_base.geometry.fragment_partitioner import (
    detect_molecular_fragments,
    generate_frozen_monomer_orca_block,
    validate_no_calc_hess,
)

CO2_H2O_SYMBOLS = ["C", "O", "O", "O", "H", "H"]
CO2_H2O_COORDS = np.array([
    [0.0000, 0.0000, 0.0000],
    [0.0000, 0.0000, 1.1620],
    [0.0000, 0.0000, -1.1620],
    [2.8360, 0.0000, 0.0000],
    [3.4120, 0.7555, 0.0000],
    [3.4120, -0.7555, 0.0000],
], dtype=np.float64)

def test_detect_molecular_fragments_co2_h2o():
    frags = detect_molecular_fragments(
        atomic_numbers_or_symbols=CO2_H2O_SYMBOLS,
        coordinates_angstrom=CO2_H2O_COORDS,
        cov_scale=1.15,
    )
    assert len(frags) == 2
    assert frags[0] == [0, 1, 2]
    assert frags[1] == [3, 4, 5]

def test_frozen_monomer_orca_constraints_block():
    frags = [[0, 1, 2], [3, 4, 5]]
    orca_block = generate_frozen_monomer_orca_block(
        fragments=frags,
        symbols=CO2_H2O_SYMBOLS,
        coordinates_angstrom=CO2_H2O_COORDS,
        initial_hessian="XTB2",
    )

    assert "TolMaxG 1e-5" in orca_block
    assert "TolE    1e-7" in orca_block
    assert "TolRMSG 3e-6" in orca_block
    assert "TolRMSD 5e-5" in orca_block
    assert "TolMaxD 1e-4" in orca_block
    assert "InHess  XTB2" in orca_block or "InHess  Lindh" in orca_block

    assert "Constraints" in orca_block
    assert "{ B 0 1 C }" in orca_block
    assert "{ B 0 2 C }" in orca_block

def test_strict_ban_on_calc_hess_true():
    validate_no_calc_hess("! wB97M-V def2-TZVP Opt\n%geom InHess XTB2 end")

    bad_decks = [
        "%geom Calc_Hess true end",
        "! Opt Calc_Hess true",
        "%geom calchess true end",
    ]
    for bad in bad_decks:
        with pytest.raises(MethodologyViolationError, match="Calc_Hess true' is strictly prohibited"):
            validate_no_calc_hess(bad)
