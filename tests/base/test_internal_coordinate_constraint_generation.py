"""CoChem-BASE: Test Internal Coordinate Constraint Generation.

Compliant with Method Matrix v4 §9A.1-§9A.2 and Anti-Spoofing Protocol v2.
Verifies Deliverable 3:
1. Canonical constraint generation in cochem_base.geometry.constraints.
2. Full extraction of intramolecular bonds ({ B u v C }), angles ({ A i j k C }),
   and proper dihedrals ({ D i j k l C }) for both Monomer A and Monomer B.
3. Strict preservation of intermolecular degrees of freedom (zero intermolecular constraints).
"""

import re
import pytest
from cochem_base.geometry.constraints import (
    format_orca_frozen_monomer_constraints_block,
    generate_frozen_monomer_constraints,
)
from cochem_base.schemas import ConstraintPayload
from Libraries.cochem_torq_constraints import (
    generate_orca_frozen_monomer_constraints_block,
)


def test_formic_acid_water_full_internal_coordinate_freezing():
    """Verify complete freezing of intramolecular degrees of freedom for formic acid and water

    while strictly excluding all intermolecular coordinates from constraints.
    """
    # Authentic planar cyclic dimer geometry of Formic Acid ... Water
    # Monomer A (Formic acid, atoms 0-4):
    # 0: C, 1: O (carbonyl), 2: O (hydroxyl), 3: H (formyl), 4: H (hydroxyl)
    # Monomer B (Water, atoms 5-7):
    # 5: O, 6: H, 7: H
    symbols = ["C", "O", "O", "H", "H", "O", "H", "H"]
    coords = [
        [-0.1347, 1.3469, 0.0000],   # 0: C
        [1.0267, 0.9995, 0.0000],    # 1: O=
        [-1.1578, 0.5186, 0.0000],   # 2: O-H
        [-0.3472, 2.4273, 0.0000],   # 3: H-C
        [-0.8174, -0.4140, 0.0000],  # 4: H-O
        [0.2227, -1.8906, 0.0000],   # 5: Ow
        [1.0487, -1.3789, 0.0000],   # 6: Hw
        [0.3807, -2.8443, 0.0000],   # 7: Hw
    ]

    atoms_a = [0, 1, 2, 3, 4]
    atoms_b = [5, 6, 7]

    constraints = generate_frozen_monomer_constraints(
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        symbols=symbols,
        coordinates=coords,
    )

    assert isinstance(constraints, ConstraintPayload)

    # Monomer A (Formic acid) has 4 covalent bonds: (0, 1), (0, 2), (0, 3), (2, 4)
    # Monomer B (Water) has 2 covalent bonds: (5, 6), (5, 7)
    # Total intramolecular bonds = 6
    assert len(constraints.bonds) == 6

    # Formic acid has valence angles: (1, 0, 2), (1, 0, 3), (2, 0, 3), (0, 2, 4) -> 4 angles
    # Water has 1 valence angle: (6, 5, 7)
    # Total valence angles = 5
    assert len(constraints.angles) == 5

    # Formic acid has proper dihedrals about C-O bond (0, 2): (1, 0, 2, 4) and (3, 0, 2, 4)
    assert len(constraints.dihedrals) == 2

    # Verify zero intermolecular constraints exist
    set_a = set(atoms_a)
    set_b = set(atoms_b)

    for u, v in constraints.bonds:
        assert (u in set_a and v in set_a) or (u in set_b and v in set_b), (
            f"Intermolecular bond constraint detected between {u} and {v}"
        )

    for i, j, k in constraints.angles:
        assert (i in set_a and j in set_a and k in set_a) or (
            i in set_b and j in set_b and k in set_b
        ), f"Intermolecular angle constraint detected: ({i}, {j}, {k})"

    for i, j, k, l in constraints.dihedrals:
        assert (i in set_a and j in set_a and k in set_a and l in set_a) or (
            i in set_b and j in set_b and k in set_b and l in set_b
        ), f"Intermolecular dihedral constraint detected: ({i}, {j}, {k}, {l})"

    # Generate full ORCA %geom constraint block
    orca_block = format_orca_frozen_monomer_constraints_block(constraints)

    assert "%geom" in orca_block
    assert "TolMaxG 1e-5" in orca_block
    assert "TolE 1e-7" in orca_block
    assert "TolRMSG 3e-6" in orca_block
    assert "Constraints" in orca_block
    assert "{ B " in orca_block
    assert "{ A " in orca_block
    assert "{ D " in orca_block
    assert "end" in orca_block

    # Test compatibility via cochem_torq_constraints
    torq_block = generate_orca_frozen_monomer_constraints_block(
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        symbols=symbols,
        coordinates=coords,
    )
    assert "{ B " in torq_block
    assert "{ A " in torq_block
    assert "{ D " in torq_block
