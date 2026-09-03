"""Physical acceptance tests for Pydantic v2 domain models in CoChem-TOPOS."""

from __future__ import annotations

import json
from cochem.topos.models import (
    AttachmentSite,
    BondOrderEdge,
    BondPerceptionResult,
    ECFP4FingerprintPayload,
    ForceFieldAssignmentResult,
    MoleculeRecord,
    NonBondedParameter,
    SubgraphDeltaRecord,
    SynthonRecord,
    TopologyDelta,
)


def test_pydantic_v2_json_roundtrip_deserialization() -> None:
    """REQ-TOPOS-004: Verify JSON-safe serialization and deserialization without tuple key crash."""
    edge = BondOrderEdge(atom_i=0, atom_j=1, bond_order=1.0)
    res = BondPerceptionResult(
        bond_orders=[edge],
        formal_charges=[0, 0],
        lone_pairs=[2, 0],
        total_charge=0,
    )
    json_str = res.model_dump_json()
    reconstituted = BondPerceptionResult.model_validate_json(json_str)
    assert reconstituted.bond_orders[0].atom_i == 0
    assert reconstituted.bond_orders[0].bond_order == 1.0
    assert reconstituted.total_charge == 0


def test_molecule_record_serialization_and_properties() -> None:
    """REQ-TOPOS-001: Verify MoleculeRecord serialization and properties roundtrip."""
    rec = MoleculeRecord(
        name="water",
        elements=["O", "H", "H"],
        coordinates=[
            (0.000000, 0.000000, 0.117269),
            (0.000000, 0.757160, -0.469076),
            (0.000000, -0.757160, -0.469076),
        ],
        formal_charges=[0, 0, 0],
        partial_charges=[-0.834, 0.417, 0.417],
        bonds=[(0, 1, 1.0), (0, 2, 1.0)],
        properties={"source": "QM9", "formula": "H2O"},
    )
    assert rec.num_atoms == 3
    assert rec.num_bonds == 2

    raw_json = rec.model_dump_json()
    reconstituted = MoleculeRecord.model_validate_json(raw_json)
    assert reconstituted.name == "water"
    assert len(reconstituted.elements) == 3
    assert reconstituted.coordinates[0][2] == 0.117269
    assert reconstituted.properties["source"] == "QM9"


def test_topology_delta_roundtrip_and_markdown() -> None:
    """REQ-TOPOS-005: Verify TopologyDelta roundtrip and markdown table generation."""
    sub_add = SubgraphDeltaRecord(
        atom_indices=[6],
        elements=["O"],
        bonds=[],
        smiles="O",
    )
    delta = TopologyDelta(
        atom_mapping={0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5},
        element_mutations=[],
        bond_order_mutations=[(0, 1, 1.5, 2.0)],
        subgraph_additions=[sub_add],
        subgraph_deletions=[],
    )
    raw_json = delta.model_dump_json()
    reconstituted = TopologyDelta.model_validate_json(raw_json)
    assert len(reconstituted.atom_mapping) == 6
    assert reconstituted.atom_mapping[0] == 0
    assert len(reconstituted.subgraph_additions) == 1

    md_table = delta.to_markdown_table()
    assert "Topology Comparison Delta" in md_table
    assert "Mapped Core Atoms" in md_table
    assert "`O`" in md_table


def test_synthon_record_roundtrip() -> None:
    """REQ-TOPOS-003: Verify SynthonRecord and AttachmentSite roundtrip."""
    site = AttachmentSite(
        anchor_atom_idx=1,
        brics_class=3,
        polarity="donor",
        connection_vector=(1.2, 0.0, 0.0),
        severed_partner_element="C",
    )
    syn = SynthonRecord(
        smiles="[3*]Oc1ccccc1",
        elements=["O", "C", "C", "C", "C", "C", "C"],
        coordinates=[(0.0, 0.0, 0.0)] * 7,
        bonds=[(0, 1, 1.0), (1, 2, 1.5)],
        attachment_sites=[site],
        formal_charge=0,
    )
    raw_json = syn.model_dump_json()
    reconstituted = SynthonRecord.model_validate_json(raw_json)
    assert len(reconstituted.attachment_sites) == 1
    assert reconstituted.attachment_sites[0].polarity == "donor"
    assert reconstituted.attachment_sites[0].brics_class == 3


def test_forcefield_assignment_result_roundtrip() -> None:
    """REQ-TOPOS-002: Verify ForceFieldAssignmentResult and NonBondedParameter roundtrip."""
    param = NonBondedParameter(
        atom_type="ca",
        sigma_nm=0.339967,
        epsilon_kj_mol=0.359824,
        r_min_half_angstrom=1.9080,
        epsilon_kcal_mol=0.0860,
    )
    res = ForceFieldAssignmentResult(
        atom_types=["ca"],
        charges=[-0.06],
        bonded_parameters={},
        non_bonded_parameters=[param],
        forcefield_family="GAFF2",
        energy_unit="kcal/mol",
        distance_unit="angstrom",
        angle_unit="degrees",
    )
    raw_json = res.model_dump_json()
    reconstituted = ForceFieldAssignmentResult.model_validate_json(raw_json)
    assert reconstituted.forcefield_family == "GAFF2"
    assert reconstituted.non_bonded_parameters[0].atom_type == "ca"
    assert reconstituted.non_bonded_parameters[0].epsilon_kcal_mol == 0.0860


def test_ecfp4_payload_roundtrip() -> None:
    """REQ-TOPOS-006: Verify ECFP4FingerprintPayload roundtrip."""
    payload = ECFP4FingerprintPayload(
        bit_vector_1024=[1] + [0] * 1023,
        bit_vector_2048=[1] + [0] * 2047,
        on_bits_2048=[0],
        count_vector={0: 2},
        features_de_duplicated=4,
    )
    raw_json = payload.model_dump_json()
    reconstituted = ECFP4FingerprintPayload.model_validate_json(raw_json)
    assert len(reconstituted.bit_vector_2048) == 2048
    assert reconstituted.count_vector[0] == 2
    assert reconstituted.features_de_duplicated == 4
