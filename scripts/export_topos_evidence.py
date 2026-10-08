"""Export a bound TOPOS snapshot, never a recursive native execution directory.

The installed BASE controller verifies the mandatory receiver before and after
export. Only that receiver's Python imports TOPOS. Missing operation receipts
remain explicit unavailable exports; this tool never guesses a run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import shutil
import tempfile
from pathlib import Path


def _declared_path(path: Path) -> Path:
    path = path.expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Evidence paths cannot traverse symbolic links")
    return path.resolve()


def _hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _copy_bound(source: Path, destination: Path, expected_sha256: str) -> dict:
    source = _declared_path(source)
    if not source.is_file():
        raise ValueError("Expected a regular bound evidence member")
    before = _hash(source)
    if before != expected_sha256:
        raise ValueError("Evidence differs from its verified original identity")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
    if _hash(source) != before or _hash(destination) != before:
        raise ValueError("Evidence changed during export")
    return {"sha256": before, "size_bytes": destination.stat().st_size}


def child_export(source: Path, destination: Path) -> dict:
    """Executed by the verified installed receiver; storage proof, not new science."""
    from cochem_base.interfaces.artifact_handoff import load_module_handoff
    from scripts.mandatory_ecosystem import _json
    from topos.actions.hosted_worker import stage_committed_run
    from topos.base_provider import request_from_handoff
    from topos.cfour_artifacts import validate_scientific_export_membership
    from topos.storage import RunStore, atomic_json, digest_json

    source, destination = _declared_path(source), _declared_path(destination)
    manifest_path = _declared_path(source / "handoff/handoff.json")
    operation_path = _declared_path(source / "execution/operation.json")
    operation_hash = _hash(operation_path)
    operation = _json(operation_path)
    handoff = load_module_handoff(manifest_path)
    request, provenance = request_from_handoff(manifest_path)
    expected_request = digest_json(request.model_dump(mode="json"))
    folder = _declared_path(Path(str(operation.get("run_directory", ""))))
    if (not folder.is_relative_to(source / "execution/runs") or not folder.is_dir()
            or not (folder / "CURRENT.json").is_file()):
        raise ValueError("Operation run directory escapes its assigned execution tree")
    store = RunStore(folder)
    with store.lock:
        manifest, record = store.verify(), store.load()
        consumption = record.get("metadata", {}).get("base_consumption", {})
        if (operation.get("schema_version") != "cochem.mandatory-module-operation/1"
                or operation.get("module_id") != "topos" or operation.get("published") is not False
                or operation.get("provider") != "topos.base_provider:provider"
                or operation.get("handoff_id") != handoff.handoff_id
                or operation.get("operation") != handoff.operation
                or operation.get("input_sha256") != handoff.artifact.sha256
                or operation.get("run_snapshot_id") != manifest["snapshot_id"]
                or operation.get("status") != record["status"]
                or operation.get("validation_status") != record["validation_status"]
                or operation.get("execution_provider") != record.get("metadata", {}).get("execution_provider")
                or operation.get("consumption_receipt") != consumption
                or consumption.get("handoff_id") != handoff.handoff_id
                or consumption.get("manifest_file_sha256") != provenance["manifest_file_sha256"]
                or consumption.get("artifact_sha256") != handoff.artifact.sha256
                or consumption.get("execution_request_sha256") != expected_request
                or consumption.get("run_id") != record["run_id"]
                or digest_json(record["request"]) != expected_request):
            raise ValueError("Export identity differs from the exact handoff, request or final committed operation")
        # Required new collection policy: no fallback to historical GENBAS-bearing
        # ledgers or a guessed filename/extension filter. Shared TOPOS staging
        # invokes the same guard so every hosted channel has this boundary.
        validate_scientific_export_membership(record, manifest)
    staged = stage_committed_run(folder, destination, expected_request)
    if (staged["run_id"] != record["run_id"] or staged["snapshot_id"] != operation["run_snapshot_id"]
            or _hash(operation_path) != operation_hash):
        raise ValueError("Operation or committed snapshot changed during export")
    files = {"operation.json": _copy_bound(operation_path, destination / "operation.json", operation_hash),
             "handoff/handoff.json": _copy_bound(manifest_path, destination / "handoff/handoff.json", provenance["manifest_file_sha256"])}
    filename = handoff.artifact.filename
    files["handoff/" + filename] = _copy_bound(source / "handoff" / filename, destination / "handoff" / filename, handoff.artifact.sha256)
    for relative in staged["relative_paths"]:
        path = destination / relative
        files[relative] = {"sha256": _hash(path), "size_bytes": path.stat().st_size}
    receipt = {"schema_version": "cochem.topos-scientific-export/1", "status": "exported",
               "run": staged, "execution_request_sha256": expected_request,
               "handoff_id": handoff.handoff_id, "operation_sha256": operation_hash,
               "files": files, "snapshot_storage_verified": True,
               "native_execution_performed_by_exporter": False,
               "native_rerun_self_contained": False, "publication_authorized": False,
               "scope": "Exact committed scientific RunStore and bound handoff; controlled runtime dependencies remain external; no new scientific validation"}
    atomic_json(destination / "export.json", receipt)
    return receipt


def export_installed_topos(source: Path, destination: Path, module_root: Path, *, timeout: float = 180) -> dict:
    from scripts.manage_modules import (
        _atomic_json,
        _digest_json,
        _redact,
        load_manifest,
    )
    from scripts.mandatory_ecosystem import _Budget, _json, _setup_environment, verify

    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Export timeout must be positive and finite")
    source, destination = _declared_path(source), _declared_path(destination)
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Choose a fresh separate export directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    operation = _declared_path(source / "execution/operation.json")
    if not operation.is_file():
        destination.mkdir()
        receipt = {"schema_version": "cochem.topos-scientific-export/1", "status": "unavailable",
                   "reason": "No completed receiver operation receipt; native directories were not searched or uploaded",
                   "snapshot_storage_verified": False, "native_execution_performed_by_exporter": False,
                   "native_rerun_self_contained": False, "publication_authorized": False}
        _atomic_json(destination / "export.json", receipt)
        return receipt
    budget = _Budget(timeout)
    spec = load_manifest()["modules"]["topos"]
    temporary = None
    try:
        installation = verify(spec, module_root, budget=budget)
        temporary = Path(tempfile.mkdtemp(prefix=".pending-scientific-export-", dir=source.parent))
        command = [installation["python_path"], "-I", "-B", str(Path(__file__).resolve()),
                   "--child", "--source", str(source), "--output", str(temporary)]
        budget.run(command, env=_setup_environment(), label="Verified TOPOS scientific snapshot export")
        receipt = _json(temporary / "export.json")
        if (receipt.get("schema_version") != "cochem.topos-scientific-export/1"
                or receipt.get("status") != "exported"
                or receipt.get("snapshot_storage_verified") is not True
                or receipt.get("native_execution_performed_by_exporter") is not False
                or receipt.get("native_rerun_self_contained") is not False
                or receipt.get("publication_authorized") is not False
                or not isinstance(receipt.get("files"), dict)):
            raise ValueError("Receiver did not produce a verified scientific snapshot export")
        after = verify(spec, module_root, budget=budget)
        if after != installation:
            raise ValueError("Mandatory installation authority changed during export")
        controller_file = temporary / "controller-verification.json"
        _atomic_json(controller_file, {
            "schema_version": "cochem.topos-export-controller/1",
            "installation_receipt_sha256": _digest_json(installation),
            "source_pins": installation["source_pins"],
            "runtime_identity": installation["runtime_identity"],
            "scope": "Installed mandatory receiver identity verified before and after export"})
        receipt["files"][controller_file.name] = {
            "sha256": _hash(controller_file), "size_bytes": controller_file.stat().st_size}
        _atomic_json(temporary / "export.json", receipt)
        os.replace(temporary, destination)
        temporary = None
        return receipt
    except Exception as exc:
        try:
            destination.mkdir(exist_ok=False)
            _atomic_json(destination / "export-failure.json", {
                "schema_version": "cochem.topos-scientific-export/1", "status": "failed",
                "snapshot_storage_verified": False, "publication_authorized": False,
                "native_execution_performed_by_exporter": False, "error": _redact(str(exc)),
                "scope": "Export failed closed; no raw native directory fallback"})
        except (OSError, TypeError, ValueError) as receipt_error:
            logging.getLogger(__name__).warning("Cannot retain export failure receipt: %s", _redact(str(receipt_error)))
        raise
    finally:
        if temporary is not None:
            # Preserve the primary export failure; this private staging folder is
            # outside every uploaded root and can be disposed with the runner.
            shutil.rmtree(temporary, ignore_errors=True)


def main(argv=None) -> int:
    from scripts.manage_modules import default_root

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    result = child_export(args.source, args.output) if args.child else export_installed_topos(
        args.source, args.output, args.root)
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
