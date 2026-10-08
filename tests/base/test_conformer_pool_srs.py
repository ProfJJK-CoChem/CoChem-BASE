"""Chunk 17/Task 1 sieve contracts from retained, genuine TOPOS/xTB observations.

Rigid transforms, altered labels and missing metadata exercise mathematical or
admission contracts; they are never represented as new chemistry calculations.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import numpy as np
import pytest

from cochem_base.intake.conformer_deduplication import (
    ConformerCandidate, ConformerDeduplicator, build_covalent_graph,
    compute_conformer_rotational_constants, compute_weisfeiler_lehman_hash,
    hungarian_assignment_rmsd, rotational_constants_agree,
)
from cochem_base.intake.conformer_engine import sieve_ingested_records
from cochem_base.topos_runner import _parse_xyz


@pytest.fixture(scope="module")
def native_pool():
    path = Path(__file__).parents[1] / "data/conformer_pool_native_topos_xtb.json"
    payload = json.loads(path.read_text())
    assert payload["source_kind"] == "authentic BASE-installed TOPOS/xTB native acceptance"
    return payload


def _records(payload):
    return [{"symbols": item["molecule"]["symbols"], "coords": item["molecule"]["coordinates"],
             "charge": item["molecule"]["charge"], "multiplicity": item["molecule"]["multiplicity"],
             "source_sha256": payload["source_result_sha256"], "source_filename": "native-topos-result.json",
             "record_index": index, "imported_energy": item["energy_hartree"], "imported_energy_unit": "hartree",
             "comparison_protocol": item["comparison_protocol"]} for index, item in enumerate(payload["candidates"])]


def test_native_energy_window_retains_full_exclusion_lineage(native_pool):
    items = _records(native_pool)
    candidates = [ConformerCandidate(str(i), row["symbols"], np.array(row["coords"]), row["imported_energy"],
                  charge=0, multiplicity=1, comparison_protocol=row["comparison_protocol"]) for i, row in enumerate(items)]
    result = ConformerDeduplicator(energy_window_kcal=.1).sieve(candidates, require_comparable_protocol=True)
    assert result.candidates == tuple(candidates)
    assert len(result.retained) == 1
    assert result.retained[0].energy == min(row["imported_energy"] for row in items)
    assert {item.disposition for item in result.decisions} == {"retained", "outside-energy-window"}
    excluded = next(item for item in result.decisions if item.disposition == "outside-energy-window")
    assert excluded.relative_energy_kcal > .1


def test_scientific_candidate_is_immutable_without_mutating_caller_arrays(native_pool):
    row = _records(native_pool)[0]
    coordinates = np.array(row["coords"])
    candidate = ConformerCandidate("native", row["symbols"], coordinates, row["imported_energy"],
                                  metadata={"lineage": {"source": row["source_sha256"]}})
    assert coordinates.flags.writeable
    with pytest.raises(FrozenInstanceError):
        candidate.energy = 0
    with pytest.raises(ValueError):
        candidate.coordinates.flags.writeable = True
    with pytest.raises(TypeError):
        candidate.metadata["lineage"]["source"] = "changed"
    coordinates[0] += [3, 4, 5]
    np.testing.assert_array_equal(candidate.coordinates, row["coords"])


def test_canonical_union_preserves_originals_and_every_member(native_pool):
    records = _records(native_pool)
    original = deepcopy(records)
    rigid = deepcopy(records[0])
    rotation = np.array([[.8, -.6, 0], [.6, .8, 0], [0, 0, 1]])
    rigid["coords"] = (np.array(rigid["coords"]) @ rotation + [7, -4, 3]).tolist()
    rigid["record_index"] = 2
    records.append(rigid)
    result = sieve_ingested_records(records)
    assert records[:2] == original
    assert result["records"] == records
    assert result["count"] == 3 and result["unique_count"] == 2
    assert len(set(result["member_ids"])) == len(result["decisions"]) == 3
    duplicate = next(row for row in result["decisions"] if row["disposition"] == "duplicate")
    assert duplicate["representative_id"] in result["member_ids"]
    assert duplicate["rmsd_angstrom"] < 1e-10
    assert all(len(row["wl_hash"]) == 64 for row in result["decisions"])


@pytest.mark.parametrize("missing", ["imported_energy", "charge", "multiplicity", "comparison_protocol"])
def test_unknown_scientific_context_is_retained_without_zero_defaults(native_pool, missing):
    records = _records(native_pool)
    records[0].pop(missing)
    records[1] = deepcopy(records[0])
    records[1]["record_index"] = 1
    result = sieve_ingested_records(records)
    assert result["unique_count"] == 2
    assert {row["disposition"] for row in result["decisions"]} == {"unranked-energy"}
    assert all(row["relative_energy_kcal"] is None for row in result["decisions"])
    assert missing not in result["records"][0]


def test_legacy_broker_seed_has_no_observed_energy_and_native_pool_requires_one(native_pool, tmp_path):
    row = _records(native_pool)[0]
    path = tmp_path / "original.xyz"
    text = str(len(row["symbols"])) + "\nOriginal coordinate record; energy not provided\n" + "".join(
        label + " " + " ".join(format(value, ".17g") for value in coord) + "\n"
        for label, coord in zip(row["symbols"], row["coords"], strict=True))
    path.write_text("\ufeff" + text, encoding="utf-8")
    parsed = _parse_xyz(path, require_energy=False)
    assert parsed[0].energy is None
    with pytest.raises(ValueError, match="Missing engine energy"):
        _parse_xyz(path, require_energy=True)


def test_stage2_batch_preserves_unranked_originals_and_sieve_decisions(native_pool, tmp_path):
    from cochem_base.intake.cochem_stage2_ingestor import Stage2Ingestor

    records = _records(native_pool)
    path = tmp_path / "student-pool.xyz"
    path.write_text("".join(str(len(row["symbols"])) + "\nCoordinate observations, no declared energy/state\n" + "".join(
        label + " " + " ".join(format(value, ".17g") for value in coord) + "\n"
        for label, coord in zip(row["symbols"], row["coords"], strict=True)) for row in records))
    systems = Stage2Ingestor(max_workers=1).process_directory(tmp_path)
    assert len(systems) == 1
    result = systems[0]
    assert result.total_input_conformers == result.unique_conformer_count == 2
    assert len(result.conformer_pool_sieve["records"]) == 2
    assert {row["disposition"] for row in result.conformer_pool_sieve["decisions"]} == {"unranked-energy"}
    assert result.unique_conformer_names == ["student-pool.xyz#1", "student-pool.xyz#2"]
    assert "validated distinct minima" in result.qualification.lower()
    result.model_dump_json()


def test_different_explicit_states_and_protocols_are_independent(native_pool):
    first = _records(native_pool)[0]
    different_protocol = deepcopy(first)
    different_protocol.update(record_index=1, comparison_protocol="independently declared Hamiltonian")
    different_spin = deepcopy(first)
    different_spin.update(record_index=2, multiplicity=3)
    result = sieve_ingested_records([first, different_protocol, different_spin])
    assert result["unique_count"] == 3
    assert all(row["relative_energy_kcal"] == 0 for row in result["decisions"])


def test_all_principal_axes_are_required(native_pool):
    row = _records(native_pool)[0]
    constants = compute_conformer_rotational_constants(row["symbols"], np.array(row["coords"]))
    assert rotational_constants_agree(constants, constants, .0005)
    for axis in (0, 2):
        altered = list(constants)
        altered[axis] *= 1.001
        assert not rotational_constants_agree(constants, altered, .0005)
    assert rotational_constants_agree((float("inf"), constants[1], constants[1]),
                                      (float("inf"), constants[1], constants[1]), .0005)
    assert not rotational_constants_agree((float("inf"),)*3, (float("inf"),)*3, .0005)


def test_hungarian_assignment_respects_reordered_nuclear_labels(native_pool):
    row = _records(native_pool)[0]
    coords, symbols = np.array(row["coords"]), row["symbols"]
    permutation = [3, 5, 4, 0, 2, 1]
    reordered = coords[permutation] + [3, 4, -2]
    _, mapping = hungarian_assignment_rmsd(coords, reordered, symbols, symbols_b=[symbols[i] for i in permutation])
    assert set(mapping) == set(mapping.values()) == set(range(len(symbols)))
    assert all(symbols[index] == symbols[permutation[target]] for index, target in mapping.items())


def test_ghosts_keep_identity_without_mass_or_physical_bonds(native_pool):
    row = _records(native_pool)[0]
    coords = np.array(row["coords"])
    constants = compute_conformer_rotational_constants(row["symbols"], coords)
    with_ghost = np.vstack([coords, coords[0]])
    graph = build_covalent_graph(row["symbols"] + ["Gh"], with_ghost)
    assert graph.degree[len(coords)] == 0
    np.testing.assert_allclose(compute_conformer_rotational_constants(row["symbols"] + ["Gh"], with_ghost), constants)
    assert compute_weisfeiler_lehman_hash(row["symbols"], coords) != compute_weisfeiler_lehman_hash(row["symbols"] + ["Gh"], with_ghost)
    with pytest.raises(ValueError, match="overlap"):
        build_covalent_graph(["H", "H"], [[0, 0, 0], [.4, 0, 0]])
    with pytest.raises(ValueError, match="positive finite physical nuclear mass"):
        compute_conformer_rotational_constants(["Gh"], np.zeros((1, 3)))


@pytest.mark.parametrize("change", [
    {"source_sha256": "unverified"}, {"record_index": -1}, {"imported_energy": True},
    {"imported_energy_unit": "unknown"}, {"multiplicity": False},
])
def test_incomplete_or_contradictory_pool_observations_reject(native_pool, change):
    row = _records(native_pool)[0]
    row.update(change)
    with pytest.raises(ValueError):
        sieve_ingested_records([row])
    with pytest.raises(ValueError, match="conflicts"):
        sieve_ingested_records(_records(native_pool), charge=1)
