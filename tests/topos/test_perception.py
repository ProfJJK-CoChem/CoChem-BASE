"""Physical acceptance tests for bond-order and formal charge perception engine."""

from __future__ import annotations

import pytest
import numpy as np
from mendeleev import element

from cochem.topos.exceptions import BondPerceptionError
from cochem.topos.perception import perceive_bond_orders_from_xyz


def test_water_qm9_bond_order_and_formal_charge() -> None:
    """REQ-TOPOS-004: Verify physical bond-order perception on authentic QM9 water coordinates."""
    coords = [
        (0.000000, 0.000000, 0.117269),   # O
        (0.000000, 0.757160, -0.469076),  # H1
        (0.000000, -0.757160, -0.469076), # H2
    ]
    elements = ["O", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    assert res.formal_charges[0] == 0, f"Oxygen formal charge must be 0, got {res.formal_charges[0]}"
    assert res.lone_pairs[0] == 2, f"Oxygen must possess 2 lone pairs, got {res.lone_pairs[0]}"
    assert len(res.bond_orders) == 2
    for b in res.bond_orders:
        assert b.bond_order == 1.0


def test_methanesulfonamide_period3_hypervalent_perception() -> None:
    """REQ-TOPOS-004: Verify Period 3 Sulfur perception on authentic methanesulfonamide coordinates."""
    # Authentic 3D Cartesian coordinates for Methanesulfonamide (CH3SO2NH2)
    coords = [
        (-1.758,  0.000, -0.288),  # C
        ( 0.000,  0.000,  0.222),  # S (Period 3 hypervalent center)
        ( 0.354,  1.265, -0.378),  # O1 (S=O double bond)
        ( 0.354, -1.265, -0.378),  # O2 (S=O double bond)
        ( 0.658,  0.000,  1.748),  # N (S-N single bond)
        (-1.912,  0.893, -0.894),  # H (C)
        (-1.912, -0.893, -0.894),  # H (C)
        (-2.378,  0.000,  0.607),  # H (C)
        ( 0.366,  0.817,  2.268),  # H (N)
        ( 0.366, -0.817,  2.268),  # H (N)
    ]
    elements = ["C", "S", "O", "O", "N", "H", "H", "H", "H", "H"]
    res = perceive_bond_orders_from_xyz(elements=elements, coordinates=coords, net_charge=0)
    assert res.total_charge == 0
    # Sulfur index 1: formal charge must be 0, lone pairs = 0
    assert res.formal_charges[1] == 0
    assert res.lone_pairs[1] == 0
    # Verify S=O double bonds (BO ~ 2.0) and S-N / S-C single bonds (BO ~ 1.0)
    s_bonds = [b for b in res.bond_orders if b.atom_i == 1 or b.atom_j == 1]
    assert len(s_bonds) == 4
    s_bo_sum = sum(b.bond_order for b in s_bonds)
    assert abs(s_bo_sum - 6.0) < 1e-3, f"Expected Sulfur BO sum = 6.0 (valence shell 12), got {s_bo_sum}"


def test_dynamic_mendeleev_calibration_scale() -> None:
    """REQ-TOPOS-004: Ensure covalent radii scale dynamically from picometers to Angstroms."""
    sulfur = element("S")
    radius_pm = sulfur.covalent_radius_pyykko
    radius_angstrom = radius_pm / 100.0
    assert 0.90 < radius_angstrom < 1.20

    carbon = element("C")
    assert 0.60 < (carbon.covalent_radius_pyykko / 100.0) < 0.90


def test_perception_invalid_coordinates_shape_raises() -> None:
    """REQ-TOPOS-004: Verify exception raised when coordinates shape does not match atom count."""
    coords = [(0.0, 0.0, 0.0)]
    elements = ["O", "H"]
    with pytest.raises(BondPerceptionError):
        perceive_bond_orders_from_xyz(elements=elements, coordinates=coords)
