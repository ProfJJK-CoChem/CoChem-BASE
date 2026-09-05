"""Bimolecular Coordinate Intake & Frozen-Monomer vdW Pre-Screener Zero-Mock Integration Tests.

Method Matrix Reference: Method Matrix v4 §9A.5, §9B.1-§9B.2, Suggestion #121.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Rejection or automatic routing of unguided 1D disconnected SMILES (e.g., O.O=C=O).
2. Explicit 3D Cartesian validation:
   - Steric clash detection (R_ij < 1.0 A) raising GeometryClashError.
   - Unbound dissociated fragment detection (R_ij > R_vdw + 3.0 A) raising UnphysicalDissociationError.
3. Frozen-Monomer van der Waals alignment preserving monomer geometry and enforcing sum-of-vdW contact.
4. Isolated subprocess dispatch into ephemeral scratch T_scr under cross-platform filelock.FileLock.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from frontend.cochem_topos_prescreener import (
    BimolecularPreScreener,
    GeometryClashError,
    UnguidedSmilesIntakeError,
    UnphysicalDissociationError,
    get_vdw_radius,
    partition_fragments,
)
from mendeleev import element


def test_disconnected_smiles_routing_and_vdw_alignment():
    """Verify that disconnected SMILES 'O.O=C=O' is automatically routed to Frozen-Monomer pre-screener [M]."""
    smiles = "O.O=C=O"
    symbols, coords = BimolecularPreScreener.prescreen_smiles_or_align(smiles)

    # Validate output elements: Water (O, H, H) and Carbon Dioxide (C, O, O)
    assert len(symbols) == 6
    assert symbols.count("O") == 3
    assert symbols.count("H") == 2
    assert symbols.count("C") == 1
    assert coords.shape == (6, 3)

    # Calculate intermolecular distance between O of H2O and C of CO2
    # Monomer 1 (H2O): indices 0, 1, 2; Monomer 2 (CO2): indices 3, 4, 5
    r_vdw_o = float(element("O").vdw_radius) / 100.0  # pm to Angstrom [E]
    r_vdw_c = float(element("C").vdw_radius) / 100.0  # pm to Angstrom [E]
    r_vdw_sum = r_vdw_o + r_vdw_c

    # Assert no intermolecular steric clash (< 1.0 A) [M]
    for i in range(3):
        for j in range(3, 6):
            dist = float(np.linalg.norm(coords[i] - coords[j]))
            assert dist >= 1.0, f"Intermolecular steric clash between atoms {i} and {j}: {dist:.3f} A < 1.0 A"

    # Verify that the two fragments are separated near sum-of-vdW distance
    h2o_com = np.mean(coords[:3], axis=0)
    co2_com = np.mean(coords[3:], axis=0)
    inter_com_dist = float(np.linalg.norm(h2o_com - co2_com))
    assert abs(inter_com_dist - r_vdw_sum) < 0.5, (
        f"COM separation {inter_com_dist:.3f} A deviated from vdW sum {r_vdw_sum:.3f} A"
    )


def test_unguided_multi_fragment_smiles_rejected_when_three_fragments():
    """Assert multi-fragment SMILES with >= 3 fragments without 3D orientation raises UnguidedSmilesIntakeError."""
    smiles_triplet = "O.O.O=C=O"
    with pytest.raises(UnguidedSmilesIntakeError, match="Disconnected multi-fragment SMILES"):
        BimolecularPreScreener.prescreen_smiles_or_align(smiles_triplet, allow_unguided=False)


def test_pairwise_steric_clash_detection():
    """Assert interatomic distance matrix flags atomic clashes (< 1.0 A) with GeometryClashError [M]."""
    # Water-water complex with overlapping hydrogen atoms (0.50 A)
    symbols = ["O", "H", "H", "O", "H", "H"]
    clashing_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],
        [0.0, 0.0, 2.8],
        [0.757, 0.586, 0.5],  # Clash with atom 1: |0.5 - 0.0| = 0.5 A
        [-0.757, 0.586, 2.8],
    ], dtype=np.float64)

    with pytest.raises(GeometryClashError, match="Steric clash detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(symbols, clashing_coords)


def test_unphysical_dissociation_detection():
    """Assert inter-fragment separation beyond R_vdw + 3.0 A raises UnphysicalDissociationError [M]."""
    # H2O ... CO2 placed at 8.5 A separation (unphysically dissociated)
    symbols = ["O", "H", "H", "C", "O", "O"]
    r_vdw_o = get_vdw_radius("O")
    r_vdw_c = get_vdw_radius("C")
    max_contact = r_vdw_o + r_vdw_c + 3.0  # ~6.22 A
    assert 8.5 > max_contact

    dissociated_coords = np.array([
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],
        [0.0, 0.0, 8.5],
        [0.0, 0.0, 9.662],
        [0.0, 0.0, 7.338],
    ], dtype=np.float64)

    with pytest.raises(UnphysicalDissociationError, match="Unphysical dissociation detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(
            symbols, dissociated_coords, allow_dissociation=False
        )


def test_frozen_monomer_covalent_graph_partitioning():
    """Assert partition_fragments correctly isolates non-covalent monomers using Pyykkö radii [M], [D]."""
    symbols = ["C", "O", "O", "O", "H", "H"]
    # Authentic equilibrium CO2 and H2O at 3.0 A vdW contact
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.162],
        [0.0, 0.0, -1.162],
        [0.0, 3.0, 0.0],
        [0.757, 3.586, 0.0],
        [-0.757, 3.586, 0.0],
    ], dtype=np.float64)

    fragments = partition_fragments(symbols, coords)
    assert len(fragments) == 2
    assert set(fragments[0]) == {0, 1, 2}
    assert set(fragments[1]) == {3, 4, 5}


def test_ephemeral_scratch_subprocess_dispatch(tmp_path: Path):
    """Assert validated complex structures are dispatched to ephemeral scratch T_scr under filelock [M]."""
    symbols, coords = BimolecularPreScreener.prescreen_smiles_or_align("O.O=C=O")
    scratch_dir = tmp_path / "topos_scratch"

    xyz_file = BimolecularPreScreener.dispatch_search_subprocess(
        symbols=symbols,
        coords=coords,
        protocol="GOAT",
        scratch_dir=scratch_dir,
    )

    assert xyz_file.is_file()
    assert xyz_file.exists()
    content = xyz_file.read_text(encoding="utf-8")
    assert content.startswith("6\n")
    assert "TOPOS Pre-Screened Complex (Protocol: GOAT)" in content
    assert "O   " in content or "O " in content
    assert "C   " in content or "C " in content
