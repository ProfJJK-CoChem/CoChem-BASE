"""Periodic BASE ingestion examples, independent of downstream materials solvers."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from cochem.core.cochem_constants import BOHR_TO_ANGSTROM
from cochem_base.calc.periodic import PeriodicStructure, ingest_periodic_structure, parse_periodic_structure
from cochem_base.calc.periodic_execution import PeriodicCalculationConfig, write_periodic_input

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/product_b"
JSON_EXAMPLE = EXAMPLES / "gaas_fractional.json"
CIF_EXAMPLE = EXAMPLES / "gaas_ordered.cif"
PSEUDO_ROOT = Path(os.environ.get("COCHEM_QE_PSEUDO_DIR", "/workspace/cochem-runtime/qe-pseudo"))
PAW_FILES = {"Ga": PSEUDO_ROOT / "Ga.pbe-dn-kjpaw_psl.0.2.upf", "As": PSEUDO_ROOT / "As.pbe-n-kjpaw_psl.0.2.upf"}
HAS_PAW = all(path.is_file() for path in PAW_FILES.values())


def _parse(updates=None):
    raw = json.loads(JSON_EXAMPLE.read_text())
    raw.update(updates or {})
    return parse_periodic_structure(json.dumps(raw), format="json")


def test_nonorthogonal_json_round_trip_preserves_units_and_original_bytes():
    structure = ingest_periodic_structure(JSON_EXAMPLE)
    assert structure.source.source_sha256 == hashlib.sha256(JSON_EXAMPLE.read_bytes()).hexdigest()
    assert structure.source.input_coordinate_units == "dimensionless"
    np.testing.assert_allclose(structure.coordinates_angstrom, [[0, 0, 0], [1.4125] * 3], rtol=0, atol=1e-14)
    np.testing.assert_allclose(structure.coordinates_fractional, [[0, 0, 0], [.25] * 3], rtol=0, atol=1e-14)
    restored = PeriodicStructure.model_validate_json(structure.model_dump_json())
    assert restored == structure
    altered = structure.model_dump(mode="json")
    altered["coordinates_angstrom"][1][0] += .01
    with pytest.raises(ValueError, match="provenance digest"):
        PeriodicStructure.model_validate(altered)


def test_cif_and_json_describe_same_cell_metric_without_inventing_cartesian_orientation():
    left = ingest_periodic_structure(JSON_EXAMPLE)
    right = ingest_periodic_structure(CIF_EXAMPLE)
    assert left.elements == right.elements == ("Ga", "As")
    assert right.source.source_sha256 == hashlib.sha256(CIF_EXAMPLE.read_bytes()).hexdigest()
    cell_a, cell_b = np.asarray(left.cell_angstrom), np.asarray(right.cell_angstrom)
    np.testing.assert_allclose(cell_a @ cell_a.T, cell_b @ cell_b.T, atol=1e-13, rtol=0)
    np.testing.assert_allclose(left.coordinates_fractional, right.coordinates_fractional, atol=1e-14, rtol=0)
    assert np.linalg.det(cell_a) == pytest.approx(np.linalg.det(cell_b), abs=1e-12)


def test_explicit_bohr_cell_and_cartesian_positions_convert_via_canonical_constant():
    original = ingest_periodic_structure(JSON_EXAMPLE)
    converted = _parse({"cell_units": "bohr", "cell": (np.asarray(original.cell_angstrom) / BOHR_TO_ANGSTROM).tolist(),
        "coordinate_system": "cartesian", "coordinate_units": "bohr",
        "positions": (np.asarray(original.coordinates_angstrom) / BOHR_TO_ANGSTROM).tolist()})
    np.testing.assert_allclose(converted.cell_angstrom, original.cell_angstrom, atol=1e-14, rtol=0)
    np.testing.assert_allclose(converted.coordinates_angstrom, original.coordinates_angstrom, atol=1e-14, rtol=0)
    assert converted.source.input_cell_units == converted.source.input_coordinate_units == "bohr"


@pytest.mark.parametrize("changes,match", [
    ({"cell": [[1, 0, 0], [0, 1, 0], [0, 0, 0]]}, "nondegenerate"),
    ({"cell": [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]}, "right handed"),
    ({"positions": [[0, 0, 0], [2, -1, 4]]}, "coincide"),
    ({"occupancies": [1, .5]}, "Partial occupancy"),
    ({"coordinate_units": "angstrom"}, "dimensionless"),
    ({"pbc": [True, False, True]}, "three periodic"),
    ({"disorder": True}, "Extra inputs"),
])
def test_ambiguous_or_invalid_periodic_structure_is_rejected(changes, match):
    with pytest.raises(ValueError, match=match):
        _parse(changes)


def test_duplicate_json_key_is_rejected_instead_of_silently_overwriting_cell():
    content = JSON_EXAMPLE.read_text().replace('"cell_units": "angstrom"', '"cell_units": "angstrom", "cell_units": "bohr"')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_periodic_structure(content, format="json")


@pytest.mark.parametrize("replacement,match", [
    ("As1 As 0.25 0.25 0.25 0.5", "partial/unknown"),
    ("As1 As 0.25 0.25 0.25 ?", "partial/unknown"),
    ("As1 As 1 0 0 1", "coincide"),
])
def test_cif_does_not_hide_partial_occupancy_or_duplicate_lattice_sites(replacement, match):
    content = CIF_EXAMPLE.read_text().replace("As1 As 0.25 0.25 0.25 1", replacement)
    with pytest.raises(ValueError, match=match):
        parse_periodic_structure(content, format="cif")


def test_cif_disorder_and_multiple_blocks_require_explicit_resolution():
    content = CIF_EXAMPLE.read_text().replace("_atom_site_occupancy", "_atom_site_disorder_group\n_atom_site_occupancy")
    content = content.replace("Ga1 Ga 0 0 0 1", "Ga1 Ga 0 0 0 A 1").replace("As1 As 0.25 0.25 0.25 1", "As1 As 0.25 0.25 0.25 A 1")
    with pytest.raises(ValueError, match="disorder"):
        parse_periodic_structure(content, format="cif")
    with pytest.raises(ValueError, match="exactly one"):
        parse_periodic_structure(CIF_EXAMPLE.read_text() + CIF_EXAMPLE.read_text().replace("data_gaas", "data_second"), format="cif")


def test_ingested_structure_provenance_is_enforced_before_a_deck_is_written(tmp_path):
    assert HAS_PAW, "Install the official PAW input files with .scripts/install_qe_paw.py before acceptance tests"
    structure = ingest_periodic_structure(JSON_EXAMPLE)
    settings = {"pseudopotentials": {s: {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for s, p in PAW_FILES.items()}}
    request = structure.to_calculation_config(settings)
    config = PeriodicCalculationConfig.model_validate(request["periodic"])
    xyz = np.asarray(structure.coordinates_angstrom).copy()
    xyz[1, 0] += .01
    with pytest.raises(ValueError, match="ingested source provenance"):
        write_periodic_input(structure.elements, xyz, config, directory=tmp_path / "tampered")
    assert not (tmp_path / "tampered").exists()
    deck = write_periodic_input(structure.elements, structure.coordinates_angstrom, config, directory=tmp_path / "accepted")
    assert "CELL_PARAMETERS angstrom" in deck.read_text()
    provenance = json.loads((deck.parent / "periodic-input.json").read_text())
    assert provenance["periodic"]["structure_provenance"] == structure.source.model_dump(mode="json")
    with pytest.raises(ValueError, match="cannot overwrite"):
        structure.to_calculation_config({**settings, "cell_angstrom": np.eye(3).tolist()})


@pytest.mark.parametrize("old,new,match", [
    ('element="Ga"', 'element="As"', "element or PAW type"),
    ('pseudo_type="PAW"', 'pseudo_type="US"', "element or PAW type"),
    ('is_paw="T"', 'is_paw="F"', "is_paw"),
    ('has_so="F"', 'has_so="T"', "Spin-orbit"),
    ('functional=" SLA  PW   PBX  PBC"', 'functional="LDA"', "PBE PAW"),
])
def test_authenticated_but_incompatible_pseudopotential_header_is_rejected(tmp_path, old, new, match):
    assert HAS_PAW, "Install the official PAW input files with .scripts/install_qe_paw.py before acceptance tests"
    path = tmp_path / "contradictory.upf"
    original = PAW_FILES["Ga"].read_text()
    assert old in original
    path.write_text(original.replace(old, new, 1))
    settings = {"pseudopotentials": {s: {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for s, p in PAW_FILES.items()}}
    settings["pseudopotentials"]["Ga"] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    structure = ingest_periodic_structure(JSON_EXAMPLE)
    config = PeriodicCalculationConfig.model_validate(structure.to_calculation_config(settings)["periodic"])
    with pytest.raises(ValueError, match=match):
        write_periodic_input(structure.elements, structure.coordinates_angstrom, config, directory=tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
