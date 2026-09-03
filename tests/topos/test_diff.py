"""Physical acceptance tests for topology diff tool and MCCS graph matching."""

from __future__ import annotations

import pytest

from cochem.topos.diff import compute_topology_diff
from cochem.topos.models import TopologyDelta


def test_topology_diff_benzene_to_phenol() -> None:
    """REQ-TOPOS-005: Verify MCCS detection and delta mutation tracking between benzene and phenol."""
    benzene_smiles = "c1ccccc1"
    phenol_smiles = "Oc1ccccc1"
    diff = compute_topology_diff(mol_a_smiles=benzene_smiles, mol_b_smiles=phenol_smiles)
    assert isinstance(diff, TopologyDelta)
    # The 6 benzene ring carbons should be mapped
    assert len(diff.atom_mapping) >= 6
    # Subgraph additions in phenol should capture the hydroxyl (-OH) synthon
    assert len(diff.subgraph_additions) >= 1
    assert any("O" in sub.elements for sub in diff.subgraph_additions)


def test_topology_diff_identical_molecules() -> None:
    """REQ-TOPOS-005: Verify self-comparison yields zero additions, deletions, or mutations."""
    diff = compute_topology_diff("c1ccccc1", "c1ccccc1")
    assert len(diff.atom_mapping) == 6
    assert len(diff.element_mutations) == 0
    assert len(diff.bond_order_mutations) == 0
    assert len(diff.subgraph_additions) == 0
    assert len(diff.subgraph_deletions) == 0


def test_topology_diff_substituent_deletion() -> None:
    """REQ-TOPOS-005: Verify substituent deletion tracking from toluene to benzene."""
    diff = compute_topology_diff("Cc1ccccc1", "c1ccccc1")
    assert len(diff.atom_mapping) >= 6
    assert len(diff.subgraph_deletions) >= 1
    assert any("C" in sub.elements for sub in diff.subgraph_deletions)
