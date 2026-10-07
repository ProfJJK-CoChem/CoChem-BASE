"""Physical artifact preservation and rejection at future-module boundaries."""
import hashlib
import json
from pathlib import Path

import pytest

from cochem_base.interfaces.artifact_handoff import prepare_module_handoff, load_module_handoff
from cochem_base.interfaces.module_registry import get_module_capability, list_module_capabilities


@pytest.fixture
def geometry(tmp_path):
    path = tmp_path / "water.xyz"
    path.write_text("3\nUser supplied XYZ geometry, no calculated energy\nO 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043\n")
    return path


def test_base_legacy_consolidation_and_future_states_are_explicit():
    assert get_module_capability("CoChem-UNITY").module_id == "base"
    assert get_module_capability("base").status.value == "available"
    for entry in list_module_capabilities():
        assert entry.execution_verified is False
        if entry.module_id != "base":
            assert entry.status.value in {"not_installed", "installed_pending_integration", "conflicting_providers"}
            assert entry.operations == ()
    with pytest.raises(ValueError, match="Unknown ecosystem"):
        get_module_capability("../../unknown")


def test_handoff_copies_real_geometry_and_detects_changed_bytes(geometry, tmp_path):
    folder = tmp_path / "handoff"
    record = prepare_module_handoff("TORQ", geometry, folder, operation="torsional_scan", options={"requested_by": "BASE"})
    assert record.artifact.sha256 == hashlib.sha256(geometry.read_bytes()).hexdigest()
    assert record.artifact.metadata["atom_count"] == 3
    assert record.artifact.metadata["coordinates_unit"] == "angstrom"
    loaded = load_module_handoff(folder / "handoff.json")
    assert loaded == record
    geometry.write_text("Modified original input after publication")
    assert load_module_handoff(folder / "handoff.json") == record
    (folder / "artifact.xyz").write_text("Altered copied artifact")
    with pytest.raises(ValueError, match="integrity verification failed"):
        load_module_handoff(folder / "handoff.json")


@pytest.mark.parametrize("contents", ["2\nIncomplete\nO 0 0 0\n", "1\nNonfinite\nH nan 0 0\n", "1\nInvalid element\nXx 0 0 0\n"])
def test_invalid_geometry_does_not_publish_a_handoff(contents, tmp_path):
    source = tmp_path / "invalid.xyz"
    source.write_text(contents)
    with pytest.raises(ValueError):
        prepare_module_handoff("topos", source, tmp_path / "handoff", operation="conformer_search")
    assert not (tmp_path / "handoff").exists()


def test_existing_destination_is_preserved(geometry, tmp_path):
    directory = tmp_path / "existing"
    directory.mkdir()
    marker = directory / "user.txt"
    marker.write_text("Preserve this file")
    with pytest.raises(FileExistsError):
        prepare_module_handoff("topos", geometry, directory, operation="ingest")
    assert marker.read_text() == "Preserve this file"


def test_manifest_cannot_redirect_to_an_external_artifact(geometry, tmp_path):
    folder = tmp_path / "package"
    prepare_module_handoff("topos", geometry, folder, operation="ingest")
    manifest = folder / "handoff.json"
    contents = json.loads(manifest.read_text())
    contents["artifact"]["filename"] = "../water.xyz"
    manifest.write_text(json.dumps(contents))
    with pytest.raises(ValueError, match="inside its package"):
        load_module_handoff(manifest)


def test_runtime_handoff_cannot_write_into_repository(geometry):
    from cochem.core.context import AirGapViolationError
    checkout = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError):
        prepare_module_handoff("torq", geometry, checkout / "forbidden_handoff", operation="ingest")


def test_gui_prepares_actual_input_without_submitting_future_job(geometry, tmp_path):
    from ui.voila_layout.cochem_gui import CoChemGUI
    gui = CoChemGUI()
    gui.state.active_view = "modules"
    assert gui.main_content.children == (gui.view_modules,)
    gui.module_recipient.value = "torq"
    gui.module_artifact.value = str(geometry)
    gui.module_output.value = str(tmp_path / "packages")
    gui.btn_module_handoff.click()
    record = load_module_handoff(gui._last_module_handoff_path)
    assert record.module_id == "torq"
    assert record.scientific_execution_performed is False
    assert "Pending integration" in gui.module_handoff_status.value
    assert "Download validated handoff package" in gui.module_handoff_status.value
    assert not list(tmp_path.rglob("result.json"))


@pytest.mark.parametrize("field,value", [("execution_verified", True), ("status", "available")])
def test_pending_handoff_cannot_claim_verified_future_execution(geometry, tmp_path, field, value):
    folder = tmp_path / "package"
    prepare_module_handoff("torq", geometry, folder, operation="ingest")
    manifest = folder / "handoff.json"
    data = json.loads(manifest.read_text())
    data["capability"][field] = value
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_module_handoff(manifest)


@pytest.mark.parametrize("filename", ["gaas_fractional.json", "gaas_ordered.cif"])
def test_periodic_gui_and_handoff_preserve_real_lattice_input(filename, tmp_path):
    from cochem_base.calc.periodic import ingest_periodic_structure
    from ui.voila_layout.cochem_gui import CoChemGUI
    source = Path(__file__).resolve().parents[2] / "examples" / "product_b" / filename
    structure = ingest_periodic_structure(source)
    folder = tmp_path / "package"
    record = prepare_module_handoff("base", source, folder, operation="periodic_ingestion")
    assert record.artifact.kind == "periodic_structure"
    assert record.artifact.metadata["structure_sha256"] == structure.source.structure_sha256
    assert record.artifact.metadata["source_coordinate_system"] == "fractional"
    assert record.artifact.metadata["source_coordinate_units"] == "dimensionless"
    assert record.artifact.metadata["canonical_coordinates_unit"] == "angstrom"
    assert load_module_handoff(folder / "handoff.json") == record
    gui = CoChemGUI()
    gui.state.active_view = "periodic"
    assert gui.main_content.children == (gui.view_periodic,)
    gui.periodic_input_path.value = str(source)
    gui.btn_periodic_inspect.click()
    assert gui._periodic_structure == structure
    assert "Fractional coordinates" in gui.periodic_structure_status.value
    assert structure.source.source_sha256 in gui.periodic_structure_status.value
    assert not list(tmp_path.rglob("result.json"))
    exported = tmp_path / "validated-structure.json"
    exported.write_text(structure.model_dump_json())
    exported_package = tmp_path / "exported-package"
    exported_record = prepare_module_handoff("base", exported, exported_package, operation="periodic_ingestion")
    assert exported_record.artifact.metadata == record.artifact.metadata
    assert load_module_handoff(exported_package / "handoff.json") == exported_record
