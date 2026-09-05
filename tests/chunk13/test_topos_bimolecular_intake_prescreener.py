"""Unit tests for TOPOS Bimolecular Coordinate Intake & Frozen-Monomer vdW Pre-Screener (Suggestion #121).

Verifies:
- Rejection of unguided multi-fragment SMILES.
- Steric clash detection (R_ij < 1.0 A).
- Unphysical dissociation detection (R > R_vdw + 3.0 A).
- Frozen-monomer rigid-body docking alignment at sum-of-vdW contact.
- Ephemeral scratch sandbox dispatch under filelock.FileLock.
"""

from __future__ import annotations

import tempfile

import numpy as np
import pytest

from cochem_base.geometry.cochem_topos_prescreener import (
    BimolecularPreScreener,
    GeometryClashError,
    UnguidedSmilesIntakeError,
    UnphysicalDissociationError,
    get_covalent_radius,
    get_vdw_radius,
    partition_fragments,
)


def test_mendeleev_radii_dynamic_retrieval() -> None:
    """Verifies that dynamic vdW and covalent radii retrieval conforms to physical standards."""
    r_vdw_c = get_vdw_radius("C")
    r_vdw_h = get_vdw_radius("H")
    r_vdw_o = get_vdw_radius("O")

    assert 1.50 <= r_vdw_c <= 1.90
    assert 1.00 <= r_vdw_h <= 1.40
    assert 1.40 <= r_vdw_o <= 1.70

    r_cov_c = get_covalent_radius("C")
    r_cov_h = get_covalent_radius("H")
    assert 0.65 <= r_cov_c <= 0.85
    assert 0.25 <= r_cov_h <= 0.45


def test_reject_unguided_multi_fragment_smiles() -> None:
    """Verifies that unguided 1D multi-fragment SMILES (>2 fragments) are rejected."""
    with pytest.raises(UnguidedSmilesIntakeError, match="Disconnected multi-fragment SMILES"):
        BimolecularPreScreener.prescreen_smiles_or_align("O.O.O=C=O")


def test_bimolecular_smiles_docking_alignment() -> None:
    """Verifies that standard 2-fragment SMILES triggers Frozen-Monomer vdW docking alignment."""
    symbols, coords = BimolecularPreScreener.prescreen_smiles_or_align("O.O=C=O")

    assert len(symbols) == 6  # H2O (3) + CO2 (3)
    assert symbols == ["O", "H", "H", "C", "O", "O"]
    assert coords.shape == (6, 3)

    # Validate that resulting complex passes steric clash and dissociation checks
    result = BimolecularPreScreener.validate_cartesian_coordinates(symbols, coords)
    assert result["status"] == "VALID"
    assert result["fragment_count"] == 2
    assert result["min_distance_angstrom"] >= 1.0


def test_steric_clash_detection() -> None:
    """Verifies that severe steric overlap (< 1.0 A) raises GeometryClashError."""
    symbols = ["C", "H"]
    coords = np.array([[0.0, 0.0, 0.0], [0.50, 0.0, 0.0]])  # R = 0.5 A < 1.0 A

    with pytest.raises(GeometryClashError, match="Steric clash detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(symbols, coords)


def test_unphysical_dissociation_detection() -> None:
    """Verifies that unbound fragments separated by R > R_vdw + 3.0 A raise UnphysicalDissociationError."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    # Two water molecules separated by 10.0 A
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.75, 0.58, 0.0],
        [-0.75, 0.58, 0.0],
        [10.0, 0.0, 0.0],
        [10.75, 0.58, 0.0],
        [9.25, 0.58, 0.0],
    ])

    with pytest.raises(UnphysicalDissociationError, match="Unphysical dissociation detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(symbols, coords)

    # When allow_dissociation=True, it should pass
    res = BimolecularPreScreener.validate_cartesian_coordinates(symbols, coords, allow_dissociation=True)
    assert res["status"] == "VALID"
    assert res["fragment_count"] == 2


def test_partition_fragments() -> None:
    """Verifies covalent graph partitioning into discrete chemical fragments."""
    symbols = ["O", "H", "H", "C", "O", "O"]
    # Water at origin, CO2 shifted along Z
    coords = np.array([
        [0.0, 0.0, 0.0],
        [0.757, 0.586, 0.0],
        [-0.757, 0.586, 0.0],
        [0.0, 0.0, 3.2],
        [0.0, 0.0, 4.36],
        [0.0, 0.0, 2.04],
    ])
    frags = partition_fragments(symbols, coords)
    assert len(frags) == 2
    assert sorted(frags[0]) == [0, 1, 2]
    assert sorted(frags[1]) == [3, 4, 5]


def test_dispatch_search_subprocess_sandbox() -> None:
    """Verifies atomic writing of input XYZ in ephemeral scratch under filelock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        symbols = ["O", "H", "H"]
        coords = np.array([[0.0, 0.0, 0.0], [0.757, 0.586, 0.0], [-0.757, 0.586, 0.0]])
        xyz_path = BimolecularPreScreener.dispatch_search_subprocess(
            symbols, coords, protocol="GOAT", scratch_dir=tmpdir
        )
        assert xyz_path.is_file()
        content = xyz_path.read_text(encoding="utf-8")
        lines = content.strip().splitlines()
        assert lines[0] == "3"
        assert "GOAT" in lines[1]
        assert len(lines) == 5


def test_heavy_atom_clash_detection() -> None:
    """Verifies that heavy-atom bonds (e.g. C-C) with R < 1.00 A raise GeometryClashError."""
    symbols = ["C", "C"]
    coords = np.array([[0.0, 0.0, 0.0], [0.95, 0.0, 0.0]])  # R = 0.95 A < 1.00 A

    with pytest.raises(GeometryClashError, match="Steric clash detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(symbols, coords)


def test_unknown_smiles_unguided_intake_rejection() -> None:
    """Verifies that uncataloged or unparsable SMILES raise UnguidedSmilesIntakeError without fake stubbing."""
    with pytest.raises(UnguidedSmilesIntakeError, match="Explicit 3D Cartesian coordinates are required|cannot be passed directly"):
        BimolecularPreScreener.prescreen_smiles_or_align("O.[INVALID_SMILES%#*]")

    with pytest.raises(UnguidedSmilesIntakeError, match="Explicit 3D Cartesian coordinates are required"):
        BimolecularPreScreener.align_frozen_monomer_dimer("O", "[INVALID_SMILES%#*]")


def test_validate_cartesian_coordinates_with_custom_fragments() -> None:
    """Verifies that user-specified fragments are enforced for inter-fragment clash and separation."""
    symbols = ["H", "H"]
    coords = np.array([[0.0, 0.0, 0.0], [0.85, 0.0, 0.0]])

    # When treated as separate fragments, inter-fragment distance < 1.0 A raises GeometryClashError
    with pytest.raises(GeometryClashError, match="Steric clash detected"):
        BimolecularPreScreener.validate_cartesian_coordinates(
            symbols, coords, fragments=[[0], [1]]
        )

