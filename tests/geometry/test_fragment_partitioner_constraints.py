"""
Zero-Mock Physical Verification Test Suite: Fragment Partitioner & Frozen Monomers.
Validating Suggestion #40 (Chunk 4).

Method Matrix v4 & Anti-Spoofing Protocols v2:
- Zero-Mock Mandate: Authentic execution only without test doubles.
- Authentic CO2...H2O van der Waals complex (R = 2.836 A).
- Method Matrix §4.4 tightened convergence thresholds.
- Method Matrix §8B.3 & §9A.5 absolute ban on Calc_Hess true raising MethodologyViolationError.
"""

from pathlib import Path
import pytest
import numpy as np

from cochem_base.geometry.fragment_partitioner import (
    detect_molecular_fragments,
    generate_frozen_monomer_orca_block,
    get_covalent_radius_angstrom,
)
from cochem_base.exceptions import MethodologyViolationError


def test_co2_water_fragment_partitioning_and_frozen_constraints():
    """Test 7: Fragment detection and ORCA Recipe R1/R2 frozen monomer constraint generation.

    Verifies:
    1. CO2...H2O complex (6 atoms, R = 2.836 A) partitions into exactly 2 monomers.
    2. Monomer 1 is CO2 (atoms 0, 1, 2); Monomer 2 is H2O (atoms 3, 4, 5).
    3. Generated ORCA block contains tightened 5-threshold convergence criteria.
    4. Internal degrees of freedom are frozen while intermolecular separation R is free.
    5. Calc_Hess true triggers immediate MethodologyViolationError.
    """
    # 1. Genuine physical geometry of CO2...H2O complex (R_CO...O = 2.836 A)
    # Atoms 0, 1, 2: CO2 (C=O approx 1.16 A, linear)
    # Atoms 3, 4, 5: H2O (separated by R = 2.836 A along Z axis)
    symbols = ["C", "O", "O", "O", "H", "H"]
    coords = [
        [0.000,  0.000, -1.418],   # 0: C (CO2)
        [0.000,  1.160, -1.418],   # 1: O1 (CO2)
        [0.000, -1.160, -1.418],   # 2: O2 (CO2)
        [0.000,  0.000,  1.418],   # 3: O (H2O, distance to C is 1.418 - (-1.418) = 2.836 A)
        [0.000,  0.757,  2.004],   # 4: H1 (H2O)
        [0.000, -0.757,  2.004],   # 5: H2 (H2O)
    ]

    # 2. Detect molecular fragments
    fragments = detect_molecular_fragments(symbols, coords, cov_scale=1.25)
    assert len(fragments) == 2
    assert fragments[0] == [0, 1, 2]  # CO2
    assert fragments[1] == [3, 4, 5]  # H2O

    # 3. Generate frozen monomer ORCA block
    orca_block = generate_frozen_monomer_orca_block(
        fragments=fragments,
        symbols=symbols,
        coordinates_angstrom=coords,
        initial_hessian="XTB2",
    )

    # Verify tightened 5-threshold convergence block (Method Matrix §4.4)
    assert "%geom" in orca_block
    assert "TolMaxG 1e-5" in orca_block
    assert "TolRMSG 3e-6" in orca_block
    assert "TolMaxD 1e-4" in orca_block
    assert "TolRMSD 5e-5" in orca_block
    assert "TolE    1e-7" in orca_block
    assert "InHess  XTB2" in orca_block

    # Verify monomer internal constraints exist
    assert "Constraints" in orca_block
    # Bonds within CO2: { B 0 1 C } and { B 0 2 C }
    assert "{ B 0 1 C }" in orca_block
    assert "{ B 0 2 C }" in orca_block
    # Bonds within H2O: { B 3 4 C } and { B 3 5 C }
    assert "{ B 3 4 C }" in orca_block
    assert "{ B 3 5 C }" in orca_block
    # Crucial: Intermolecular distance R between CO2 and H2O (e.g. atoms 0 and 3) must NOT be constrained!
    assert "{ B 0 3 C }" not in orca_block
    assert "{ B 1 3 C }" not in orca_block

    # 4. Strict prohibition: Calc_Hess true must raise MethodologyViolationError (§8B.3)
    bad_deck = "! B3LYP def2-TZVP OPT\n%geom Calc_Hess true end\n* xyz 0 1\nO 0 0 0\n*\n"
    with pytest.raises(MethodologyViolationError) as exc_info:
        generate_frozen_monomer_orca_block(
            fragments=fragments,
            symbols=symbols,
            coordinates_angstrom=coords,
            input_deck_to_validate=bad_deck,
        )
    assert "Calc_Hess true" in str(exc_info.value)
    assert "strictly prohibited" in str(exc_info.value)
