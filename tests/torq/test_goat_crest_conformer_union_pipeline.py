"""Legacy compatibility uses real retained pools and fails closed before engines.

Actual CREST/GOAT execution is covered by the native broker acceptance profile;
these tests never fabricate a successful quantum calculation.
"""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_torq.conformer.orchestrator import (
    ConformerOrchestrator, deduplicate_union_ensemble, kabsch_rmsd,
)


def _native_pool():
    data = json.loads((Path(__file__).parents[1] / "data/conformer_pool_native_topos_xtb.json").read_text())
    return [{"symbols": row["molecule"]["symbols"], "coordinates": row["molecule"]["coordinates"],
             "energy_hartree": row["energy_hartree"], "charge": row["molecule"]["charge"],
             "multiplicity": row["molecule"]["multiplicity"], "comparison_protocol": row["comparison_protocol"]}
            for row in data["candidates"]]


def test_orchestrator_preserves_interface_and_requires_explicit_state():
    assert issubclass(ConformerOrchestrator, ConformerGenerator)
    record = _native_pool()[0]
    with pytest.raises(ValueError, match="explicit integer charge and multiplicity"):
        ConformerOrchestrator().generate_conformers(record["symbols"], record["coordinates"], ensemble_id="no-fabricated-result")


def test_compatibility_union_uses_actual_pool_and_canonical_proper_rotations():
    records = _native_pool()
    rigid = deepcopy(records[0])
    rigid["coordinates"] = (np.array(rigid["coordinates"]) @ np.array([[.8, -.6, 0], [.6, .8, 0], [0, 0, 1]]) + [4, 3, 2]).tolist()
    assert kabsch_rmsd(np.array(records[0]["coordinates"]), np.array(rigid["coordinates"])) < 1e-10
    assert len(deduplicate_union_ensemble(records + [rigid])) == 2
    with pytest.raises(ValueError, match="SRS"):
        deduplicate_union_ensemble(records, delta_b_rel_threshold=.005, rmsd_threshold=.15)


def test_unmeasured_seed_is_retained_as_data_without_a_fake_energy():
    record = _native_pool()[0]
    record.pop("energy_hartree")
    second = deepcopy(record)
    result = deduplicate_union_ensemble([record, second])
    assert len(result) == 2
    assert all("energy_hartree" not in row for row in result)
