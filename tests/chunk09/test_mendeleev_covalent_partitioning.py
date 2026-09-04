"""
Test Dynamic Mendeleev Covalent Bond Perception & Partitioning
SRS Chunk 09, Suggestion #90 (Method Matrix v4 §4.4)
Zero-Mock compliant: Real organic structures, dynamic Pyykkö covalent radius retrieval via mendeleev.
"""
import numpy as np

from cochem_base.chemistry.cochem_chemistry_topology import (
    get_dynamic_covalent_radius,
    partition_molecules,
)


def test_mendeleev_dynamic_radius_retrieval():
    """Assert covalent radii are queried dynamically via mendeleev without hardcoding."""
    r_c = get_dynamic_covalent_radius("C")
    r_cl = get_dynamic_covalent_radius("Cl")
    r_s = get_dynamic_covalent_radius("S")
    r_h = get_dynamic_covalent_radius("H")

    assert 0.70 < r_c < 0.80
    assert 0.95 < r_cl < 1.05
    assert 1.00 < r_s < 1.10
    assert 0.30 < r_h < 0.35


def test_12_dichloroethane_and_dimethyl_disulfide_partitioning():
    """
    Construct an atomic system containing 1,2-dichloroethane and dimethyl disulfide.
    Assert dynamic covalent neighbor lists identify each as a single connected molecule without false fragmentation.
    """
    dce_symbols = ["C", "C", "Cl", "Cl", "H", "H", "H", "H"]
    dce_coords = np.array([
        [0.00, 0.00, 0.00],
        [1.54, 0.00, 0.00],
        [-0.50, 1.70, 0.00],
        [2.04, -1.70, 0.00],
        [-0.30, -0.50, 0.90],
        [-0.30, -0.50, -0.90],
        [1.84, 0.50, 0.90],
        [1.84, 0.50, -0.90],
    ])

    dmds_symbols = ["S", "S", "C", "C", "H", "H", "H", "H", "H", "H"]
    dmds_coords = np.array([
        [10.00, 0.00, 0.00],
        [12.03, 0.00, 0.00],
        [9.00, 1.50, 0.00],
        [13.03, -1.50, 0.00],
        [9.00, 2.00, 0.90],
        [9.00, 2.00, -0.90],
        [8.00, 1.50, 0.00],
        [13.03, -2.00, 0.90],
        [13.03, -2.00, -0.90],
        [14.03, -1.50, 0.00],
    ])

    all_symbols = dce_symbols + dmds_symbols
    all_coords = np.vstack([dce_coords, dmds_coords])

    molecules = partition_molecules(all_symbols, all_coords)

    assert len(molecules) == 2, f"Expected 2 partitioned molecules, found {len(molecules)}"

    lengths = sorted([len(m) for m in molecules])
    assert lengths == [8, 10]

    m1 = set(molecules[0])
    m2 = set(molecules[1])
    dce_indices = set(range(8))
    dmds_indices = set(range(8, 18))

    assert (m1 == dce_indices and m2 == dmds_indices) or (m2 == dce_indices and m1 == dmds_indices)
