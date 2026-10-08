"""Real handoff/snapshot transport with cancelled, unexecuted control ledgers.

No EngineResult, energy, engine output or installed-runtime success is fabricated.
"""
from __future__ import annotations

import pytest
from scripts import export_topos_evidence as export

pytest.importorskip("topos", reason="Requires the mandatory TOPOS receiver for snapshot integration")
pytest.importorskip("topos.cfour_artifacts", reason="Requires the scientific-only CFOUR export policy")

from topos.models import Artifact, Attempt, RunRecord, RunRequest
from topos.storage import RunStore, atomic_json, digest_json, file_digest


@pytest.fixture
def cancelled_handoff(tmp_path):
    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    from topos.base_provider import request_from_handoff

    source = tmp_path / "controlled/topos"
    geometry = tmp_path / "input.xyz"
    geometry.write_text("2\nDeclared geometry for unexecuted transport test\nH 0 0 0\nH 0 0 0.74\n")
    declared = RunRequest(molecule={"symbols": ["H", "H"], "coordinates": [[0, 0, 0], [0, 0, 0.74]],
                                    "charge": 0, "multiplicity": 1}, purpose="energy")
    handoff = prepare_module_handoff("topos", geometry, source / "handoff", operation="energy",
        options={"topos_request": declared.model_dump(mode="json")})
    request, provenance = request_from_handoff(source / "handoff/handoff.json")
    record = RunRecord(request=request, status="cancelled", metadata={
        "execution_provider": "unexecuted-transport-fixture", "native_execution_performed": False})
    folder = source / "execution/runs" / record.run_id
    store = RunStore(folder)
    original = store.commit(record)
    consumption = {"schema_version": "topos-base-consumption/0.1.0", "handoff_id": handoff.handoff_id,
        "manifest_file_sha256": provenance["manifest_file_sha256"], "artifact_sha256": handoff.artifact.sha256,
        "declared_request_sha256": provenance["declared_request_sha256"],
        "execution_request_sha256": digest_json(request.model_dump(mode="json")), "run_id": record.run_id,
        "status": "cancelled", "validation_status": "not-evaluated",
        "execution_provider": record.metadata["execution_provider"],
        "source_snapshot_sha256": original["snapshot_id"], "transport_fixture": True}
    receipt_file = folder / "base-consumption-receipt.json"
    atomic_json(receipt_file, consumption)
    record.artifacts.append(Artifact(path=receipt_file.name, sha256=file_digest(receipt_file),
        size_bytes=receipt_file.stat().st_size, role="base-consumption-receipt"))
    record.metadata["base_consumption"] = consumption
    final = store.commit(record)
    assert final["snapshot_id"] != original["snapshot_id"]
    operation = {"schema_version": "cochem.mandatory-module-operation/1", "module_id": "topos",
        "operation": "energy", "handoff_id": handoff.handoff_id, "input_sha256": handoff.artifact.sha256,
        "status": "cancelled", "validation_status": "not-evaluated", "published": False,
        "provider": "topos.base_provider:provider", "consumption_receipt": consumption,
        "run_directory": str(folder), "run_snapshot_id": final["snapshot_id"],
        "execution_provider": record.metadata["execution_provider"], "transport_fixture": True}
    operation_file = source / "execution/operation.json"
    atomic_json(operation_file, operation)
    return source, folder, record, operation_file, operation


def test_exact_final_snapshot_copies_without_raw_execution_tree(cancelled_handoff, tmp_path):
    source, folder, record, _, operation = cancelled_handoff
    scratch = folder / "attempts/unexecuted-native-scratch"
    scratch.mkdir(parents=True)
    (scratch / "GENBAS").write_text("Transport marker, not an actual basis library")
    (scratch / "scratch-link").symlink_to(tmp_path, target_is_directory=True)
    destination = tmp_path / "export"
    destination.mkdir()
    receipt = export.child_export(source, destination)
    assert receipt["status"] == "exported"
    assert receipt["native_execution_performed_by_exporter"] is False
    assert receipt["publication_authorized"] is False
    assert receipt["run"]["status"] == "cancelled"
    assert receipt["run"]["validation_status"] == "not-evaluated"
    assert receipt["run"]["snapshot_id"] == operation["run_snapshot_id"]
    copied = RunStore(destination / "run")
    assert copied.load() == record.model_dump(mode="json")
    assert copied.verify() == RunStore(folder).verify()
    assert {p.name for p in (destination / "run/snapshots").iterdir()} == {operation["run_snapshot_id"]}
    assert not any(p.name == "GENBAS" or p.is_symlink() for p in destination.rglob("*"))
    assert (scratch / "GENBAS").exists() and (scratch / "scratch-link").is_symlink()
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    assert actual == set(receipt["files"]) | {"export.json"}


@pytest.mark.parametrize("field", ["earlier-snapshot", "request", "handoff", "status", "provider", "published"])
def test_operation_identity_mutations_cannot_publish_snapshot(cancelled_handoff, tmp_path, field):
    source, _, _, operation_file, operation = cancelled_handoff
    if field == "earlier-snapshot":
        operation["run_snapshot_id"] = operation["consumption_receipt"]["source_snapshot_sha256"]
    elif field == "request":
        operation["consumption_receipt"]["execution_request_sha256"] = "0" * 64
    elif field == "handoff":
        operation["handoff_id"] = "0" * 32
    elif field == "provider":
        operation["provider"] = "wrong.provider"
    elif field == "published":
        operation["published"] = True
    else:
        operation["status"] = "completed"
    atomic_json(operation_file, operation)
    target = tmp_path / "export"
    target.mkdir()
    with pytest.raises(ValueError, match="Export identity"):
        export.child_export(source, target)
    assert not list(target.iterdir())


def test_operation_run_path_cannot_point_at_an_external_snapshot(cancelled_handoff, tmp_path):
    source, folder, _, operation_file, operation = cancelled_handoff
    operation["run_directory"] = str(tmp_path / "external")
    atomic_json(operation_file, operation)
    target = tmp_path / "export"
    target.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        export.child_export(source, target)
    assert RunStore(folder).verify()
    assert not list(target.iterdir())


def test_old_cfour_artifact_membership_cannot_export_without_policy(cancelled_handoff, tmp_path):
    source, folder, record, operation_file, operation = cancelled_handoff
    # A cancelled ledger references only a control marker, never invented stdout.
    marker = folder / "unexecuted-control.txt"
    marker.write_text("No native engine was launched")
    record.attempts.append(Attempt(run_id=record.run_id, engine="cfour", method="unexecuted-control",
        status="cancelled", artifacts=[Artifact(path=marker.name, sha256=file_digest(marker),
        size_bytes=marker.stat().st_size, role="transport-control")]))
    operation["run_snapshot_id"] = RunStore(folder).commit(record)["snapshot_id"]
    atomic_json(operation_file, operation)
    target = tmp_path / "export"
    target.mkdir()
    with pytest.raises(ValueError, match="explicit scientific-only"):
        export.child_export(source, target)
    assert not list(target.iterdir())


def test_operation_symlink_is_rejected_before_read(cancelled_handoff, tmp_path):
    source, _, _, operation_file, _ = cancelled_handoff
    moved = operation_file.with_suffix(".original")
    operation_file.rename(moved)
    operation_file.symlink_to(moved)
    target = tmp_path / "export"
    with pytest.raises(ValueError, match="symbolic"):
        export.export_installed_topos(source, target, tmp_path / "Modules")
    assert not target.exists()


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, -1])
def test_export_timeout_is_finite_and_positive(tmp_path, timeout):
    with pytest.raises(ValueError, match="positive and finite"):
        export.export_installed_topos(tmp_path / "source", tmp_path / "output", tmp_path / "Modules", timeout=timeout)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("name", ["GENBAS", "ECPDATA", "genbas"])
@pytest.mark.parametrize("boundary", ["base-export", "topos-staging"])
def test_reserved_basis_name_cannot_export_even_without_cfour_attempt(cancelled_handoff, tmp_path, name, boundary):
    source, folder, record, operation_file, operation = cancelled_handoff
    marker = folder / name
    marker.write_text("Transport marker only; no licensed library bytes")
    record.artifacts.append(Artifact(path=name, sha256=file_digest(marker),
        size_bytes=marker.stat().st_size, role="transport-control"))
    assert not record.attempts
    operation["run_snapshot_id"] = RunStore(folder).commit(record)["snapshot_id"]
    atomic_json(operation_file, operation)
    target = tmp_path / "export"
    target.mkdir()
    with pytest.raises(ValueError, match="Licensed CFOUR basis bytes"):
        if boundary == "base-export":
            export.child_export(source, target)
        else:
            from topos.actions.hosted_worker import stage_committed_run

            stage_committed_run(folder, target, digest_json(record.request.model_dump(mode="json")))
    assert not list(target.iterdir())
