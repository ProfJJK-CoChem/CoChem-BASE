"""Real filesystem publication contracts, not native engine acceptance.

Engineering marker files exercise optional envelopes/sidecars and must never
be admitted as a scientific observation. Genuine producer tests run separately.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cochem_base.calc.calculation_service import (
    _external_run_path,
    _publish_run_artifacts,
    _retained_output_path,
)
from cochem_base.calc.local_publication import (
    ENVELOPES,
    INVENTORY,
    PREFIX,
    InputSnapshot,
    build_input_snapshot,
    digest,
    read_member,
    sidecar,
    verified_snapshot,
)
from cochem_base.interfaces.student_request import canonical_json, strict_json

GEOMETRY = "3\nConstructed test input only\nO 0 0 0\nH 0 -.757 .587\nH 0 .757 .587\n"
CONFIG = canonical_json({"geometry": GEOMETRY, "charge": 0, "multiplicity": 1})


def publication(tmp_path: Path, *, extra=None, snapshot=None):
    """Only publisher engineering marker bytes, not fabricated native outputs."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    marker = b'{"engineering_boundary_only":true}'
    (sandbox / "matrix_config.validated.json").write_bytes(marker)
    (sandbox / "input.xyz").write_text(GEOMETRY)
    (sandbox / "stderr.log").write_bytes(b"")
    for name, value in (extra or {}).items():
        path = sandbox / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    output = tmp_path / "published"
    receipt = {"status": "EXECUTION_VERIFIED", "engine": "xtb", "method": "GFN2-xTB",
        "operation": "single_point", "run_id": "job_" + "1" * 32, "dry_run": False,
        "config_file": str(tmp_path / "config.json"), "output_dir": str(output)}
    finalized = _publish_run_artifacts(sandbox, output, retained_receipt=receipt,
        submitted_config=CONFIG, input_snapshot=snapshot)
    return sandbox, output, finalized


def test_actual_final_staging_sidecars_and_acyclic_envelopes(tmp_path):
    sandbox, output, receipt = publication(tmp_path)
    assert receipt["retained_files"]["available"] is True
    inventory_raw = read_member(output, INVENTORY)
    inventory = strict_json(inventory_raw)
    actual = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    assert set(inventory["files"]) == actual - ENVELOPES
    assert receipt["retained_files"]["inventory_sha256"] == digest(inventory_raw)
    assert strict_json((output / "execution.json").read_bytes()) == receipt
    assert (sandbox / "execution.json").read_bytes() == (output / "execution.json").read_bytes()
    for name in actual:
        if name.endswith(".sha256"):
            assert read_member(output, name) == sidecar(name[:-7], read_member(output, name[:-7]))
    context = strict_json(read_member(output, PREFIX + "/input-context.json"))
    assert context["source_kind"] == "configuration_only"
    assert "original-source-and-selection-provenance-not-supplied" in context["exclusions"]
    assert not (output / "result.json").exists()  # This was never native acceptance.


@pytest.mark.parametrize("kind", ["unknown", "legacy-sidecar", "reserved", "invalid-context"])
def test_optional_feature_refusal_preserves_normal_native_members(tmp_path, kind):
    extra, snapshot = {}, None
    if kind == "unknown":
        extra["unexpected-private-config"] = b"Engineering unknown-role marker, not credentials"
    elif kind == "legacy-sidecar":
        extra["input.xyz.sha256"] = b"Legacy collision engineering marker"
    elif kind == "reserved":
        extra[PREFIX + "/inventory.json"] = b"Existing reserved-path native marker"
    else:
        snapshot = InputSnapshot.unavailable(CONFIG, source_kind="constructed_starting_geometry",
            code="CONSTRUCTION_PROVENANCE_UNVERIFIED", message="Known construction receipt missing")
    sandbox, output, receipt = publication(tmp_path, extra=extra, snapshot=snapshot)
    assert receipt["status"] == "EXECUTION_VERIFIED" and receipt["retained_files"]["available"] is False
    assert (output / "input.xyz").read_text() == GEOMETRY
    assert (output / "stderr.log").read_bytes() == b""
    assert strict_json((output / "execution.json").read_bytes()) == receipt
    if kind == "reserved":
        assert (output / PREFIX / "inventory.json").read_bytes() == extra[PREFIX + "/inventory.json"]
    if kind == "legacy-sidecar":
        # Whatever the existing copy traversal chose, it is not repaired to
        # manufacture checksum consistency. Both actual member names survive.
        assert (output / "input.xyz.sha256.sha256").is_file()
        inventory = strict_json(read_member(output, INVENTORY))
        assert any("checksum relationship" in reason for reason in inventory["unavailable_reasons"])


def test_fundamental_publication_failure_remains_a_failure(tmp_path):
    sandbox = tmp_path / "scratch"
    sandbox.mkdir()
    (sandbox / "native.txt").write_bytes(b"Existing publication engineering bytes")
    target = tmp_path / "already-published"
    target.mkdir()
    (target / "original").write_bytes(b"Do not replace")
    with pytest.raises(FileExistsError):
        _publish_run_artifacts(sandbox, target)
    assert (target / "original").read_bytes() == b"Do not replace"


def test_original_lexical_output_alias_is_refused_before_scaffolding(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"Outside output owner")
    alias = tmp_path / "alias"
    alias.symlink_to(outside, target_is_directory=True)
    requested = alias / "Results"
    authorized = _external_run_path(requested)
    assert authorized == outside / "Results"  # Old admission resolves aliases.
    with pytest.raises((ValueError, OSError)):
        _retained_output_path(requested, authorized=authorized)
    assert sentinel.read_bytes() == b"Outside output owner" and not (outside / "Results").exists()
    ordinary = tmp_path / "not-created-parent" / "Results"
    assert _retained_output_path(ordinary, authorized=_external_run_path(ordinary)) == ordinary.absolute()
    assert not ordinary.parent.exists()
    traversal = tmp_path / "not-created-parent" / ".." / "other"
    with pytest.raises(ValueError, match="lexical"):
        _retained_output_path(traversal, authorized=_external_run_path(traversal))
    assert not (tmp_path / "other").exists()


def test_native_publication_has_no_export_member_size_cap(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    marker = sandbox / "xtbrestart"
    with marker.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    (sandbox / "matrix_config.validated.json").write_bytes(b'{"engineering_boundary_only":true}')
    output = tmp_path / "published"
    receipt = {"status": "EXECUTION_VERIFIED", "engine": "xtb", "method": "GFN2-xTB",
        "operation": "single_point", "run_id": "job_" + "1" * 32, "dry_run": False,
        "config_file": str(tmp_path / "config.json"), "output_dir": str(output)}
    result = _publish_run_artifacts(sandbox, output, retained_receipt=receipt, submitted_config=CONFIG)
    assert result["status"] == "EXECUTION_VERIFIED" and result["retained_files"]["available"] is False
    assert (output / "xtbrestart").stat().st_size == marker.stat().st_size == 32 * 1024 * 1024 + 1
    assert (output / "xtbrestart.sha256").is_file()


def input_source():
    raw = GEOMETRY.encode()
    receipt = canonical_json({"origin": "canonical_ingestion", "source_sha256": digest(raw),
        "source_frame": 0, "sha256": digest(raw)})
    return {"filename": "starting.xyz", "format": "xyz", "content": raw}, {
        "record_index": 0, "geometry": raw, "receipt": receipt}


def test_original_selected_submitted_relation_and_electronic_state_are_separate():
    source, selected = input_source()
    snapshot = build_input_snapshot(submitted_config=CONFIG, source_kind="uploaded_record",
        source=source, selected_frame=selected)
    context = verified_snapshot(snapshot, CONFIG)
    assert context["relationship"] == "selected_frame_unchanged"
    assert context["submitted_state"] == {"charge": 0, "multiplicity": 1}
    assert context["source_encoded_state"] == {"charge": None, "multiplicity": None}
    edited = canonical_json({"geometry": GEOMETRY.replace(".757", ".800"), "charge": 0, "multiplicity": 1})
    changed = build_input_snapshot(submitted_config=edited, source_kind="uploaded_record", source=source, selected_frame=selected)
    assert strict_json(changed.metadata_bytes)["relationship"] == "edited_after_selection"
    assert dict(changed.files)[PREFIX + "/inputs/original.xyz"] == source["content"]
    with pytest.raises(ValueError, match="another submitted"):
        verified_snapshot(snapshot, edited)


def test_known_missing_context_and_forged_snapshot_never_downgrade_to_none():
    unavailable = InputSnapshot.unavailable(CONFIG, source_kind="assembled_starting_geometry",
        code="ASSEMBLED_SOURCE_CONTEXT_UNSUPPORTED", message="Assembly context is not supported by retained-files v1")
    assert verified_snapshot(unavailable, CONFIG)["available"] is False
    context = strict_json(build_input_snapshot(submitted_config=CONFIG).metadata_bytes)
    forged = InputSnapshot(canonical_json({**context, "source_kind": "uploaded_record"}), ())
    with pytest.raises((ValueError, KeyError)):
        verified_snapshot(forged, CONFIG)
    source, selected = input_source()
    with pytest.raises(ValueError, match="construction"):
        build_input_snapshot(submitted_config=CONFIG, source_kind="constructed_starting_geometry", source=source, selected_frame=selected)


def test_unavailable_channel_can_describe_oversized_snapshot_without_storing_its_bytes():
    oversized = b"Engineering size-boundary input " * 70000
    with pytest.raises(ValueError):
        build_input_snapshot(submitted_config=oversized)
    failure = InputSnapshot.unavailable(oversized, source_kind="uploaded_record",
        code="INPUT_SOURCE_UNVERIFIED", message="Submitted context exceeds the retained-file JSON limit")
    assert len(failure.metadata_bytes) < 1024 and failure.files == ()
    assert verified_snapshot(failure, oversized)["submitted_config_sha256"] == digest(oversized)


@pytest.mark.parametrize("unsafe", ["../outside", "/etc/passwd", "C:/private", "ambiguous\\name", "CON"])
def test_unsafe_members_are_never_read(tmp_path, unsafe):
    with pytest.raises(ValueError):
        read_member(tmp_path, unsafe)


def test_no_follow_or_hardlink_and_same_descriptor_size_bound(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"Private engineering sentinel")
    root = tmp_path / "owned"
    root.mkdir()
    (root / "linked").symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        read_member(root, "linked")
    (root / "hard").hardlink_to(outside)
    with pytest.raises(ValueError):
        read_member(root, "hard")
    (root / "ordinary").write_bytes(b"1234")
    with pytest.raises(ValueError):
        read_member(root, "ordinary", limit=3)
    assert outside.read_bytes() == b"Private engineering sentinel"
