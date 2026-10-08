#!/usr/bin/env python3
"""Run an independent module batch and retain partial receipts on failure.

A failed source checkout or package installation keeps the overall job failed.
Successful receipts and individual diagnostics are written after every attempt;
none of these outcomes establish scientific accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.manage_modules import (
    DEFAULT_MANIFEST,
    REPOSITORY_ROOT,
    _atomic_json,
    _paths,
    _redact,
    default_root,
    fetch_module,
    install_module,
    load_manifest,
)


def retain_setup_evidence(spec: dict, root: Path, output: Path) -> dict:
    """Retain raw audit files for the selected runtime, without copying engines.

    This is evidence transport, including interrupted setup. It does not replace
    the core installer's verification or turn a partial audit into authority.
    """
    # Check the declared paths before resolving them: resolution alone would
    # hide a redirected parent and place files outside the uploaded evidence.
    for declared in (root.expanduser().absolute(), output.expanduser().absolute()):
        if any(part.is_symlink() for part in (declared, *declared.parents)):
            raise ValueError("Setup evidence source and destination parents may not redirect through symbolic links")
    _, location, _, _ = _paths("topos", spec, root)
    runtime = location / "runtime"
    if runtime.is_symlink():
        raise ValueError("Setup audit source may not redirect through symbolic links")
    output = output.expanduser()
    if output.is_symlink() or output.exists():
        raise ValueError("Choose a fresh directory for retained setup evidence")
    output = output.resolve()
    if output == REPOSITORY_ROOT or output.is_relative_to(REPOSITORY_ROOT) or output.is_relative_to(runtime.resolve()):
        raise ValueError("Retained setup evidence must be outside source and native runtime directories")
    selected = []
    missing = []
    for name in ("setup-receipt.json", "mandatory-validation.json", "mandatory-deployment.json"):
        candidate = runtime / name
        if candidate.exists() or candidate.is_symlink():
            selected.append(candidate)
        else:
            missing.append(name)
    for name, suffixes in (("Registry", {".json", ".sha256"}),
                           ("setup-logs", {".json", ".log", ".txt", ".stdout", ".stderr"})):
        folder = runtime / name
        if folder.is_symlink():
            raise ValueError("Setup audit directories may not redirect through symbolic links")
        if folder.is_dir():
            for candidate in sorted(folder.rglob("*")):
                if candidate.is_symlink():
                    raise ValueError("Setup audit members may not redirect through symbolic links")
                if candidate.is_file() and candidate.suffix in suffixes:
                    selected.append(candidate)
        else:
            missing.append(name + "/")
    if len(selected) > 512:
        raise ValueError("Setup audit source exceeds the file limit")
    total = 0
    inventory = {}
    for source in selected:
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(runtime.resolve()):
            raise ValueError("Setup audit member is not a confined regular file")
        size = source.stat().st_size
        total += size
        if total > 128 * 1024 * 1024:
            raise ValueError("Setup audit exceeds the 128 MiB retention limit")
        relative = source.relative_to(runtime).as_posix()
        with source.open("rb") as stream:
            payload = stream.read(size + 1)
        if len(payload) != size:
            raise ValueError("Setup audit member changed during bounded reading")
        digest = hashlib.sha256(payload).hexdigest()
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
        if source.read_bytes() != payload or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Setup audit member changed during retention")
        inventory[relative] = {"sha256": digest, "size_bytes": len(payload), "source_path": str(source)}
    report = {"schema_version": "cochem.retained-mandatory-setup/1", "revision": spec["revision"],
              "original_runtime": str(runtime), "status": "retained" if inventory else "unavailable",
              "files": inventory, "missing_members": missing, "total_bytes": total,
              "scope": "Raw setup audit retention; no new installation or scientific authority assertion"}
    output.mkdir(parents=True, exist_ok=True)
    _atomic_json(output / "retention.json", report)
    return report


def run_batch(*, action: str, modules: list[str], manifest: Path,
              root: Path, output: Path, require_source_token: bool = False,
              ecosystem_kit: Path | None = None) -> dict:
    """Attempt every selected module, without discarding earlier outcomes."""
    if action not in {"fetch", "install", "geometry_analysis", "topos_request"}:
        raise ValueError("Unsupported module action.")
    output = output.expanduser().resolve()
    if output == REPOSITORY_ROOT or output.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Module evidence must be written outside the BASE source checkout.")
    catalog_document = load_manifest(manifest)
    catalog = catalog_document["modules"]
    selected = list(dict.fromkeys(modules))
    if not selected or any(name not in catalog for name in selected):
        raise ValueError("Select module IDs from the reviewed distribution manifest.")
    if action == "topos_request" and selected != ["topos"]:
        raise ValueError("The typed TOPOS action selects TOPOS only; its kit installs all three mandatory packages")
    if action == "geometry_analysis" and "topos" in selected:
        raise ValueError("Select topos_request and supply the full TOPOS request; geometry_analysis is a legacy module operation")
    if action != "fetch" and "topos" in selected and ecosystem_kit is None:
        raise ValueError("TOPOS installation requires an explicit verified ecosystem kit directory")
    output.mkdir(parents=True, exist_ok=True)
    manifest_output = output / "module-distribution.json"
    report_path = output / "installations.json"
    if any(path.exists() or path.is_symlink() for path in (manifest_output, report_path)):
        raise ValueError("Module evidence already exists; choose a fresh output directory for this run.")
    # Save the exact reviewed input before starting network/build operations.
    manifest_bytes = manifest.read_bytes()
    try:
        with manifest_output.open("xb") as stream:
            stream.write(manifest_bytes)
    except FileExistsError as error:
        raise ValueError("Module evidence already exists; choose a fresh output directory for this run.") from error
    operation = "fetch" if action == "fetch" else "install"
    report = {
        "schema_version": "cochem.module-batch/1", "action": action,
        "operation": operation, "selected_modules": selected,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "modules": [], "failures": [], "completed": False, "success": False,
        "scientific_accuracy_established": False,
    }
    _atomic_json(report_path, report)
    if require_source_token and not os.environ.get("COCHEM_SOURCE_READ_TOKEN"):
        report["configuration_error"] = (
            "Configure COCHEM_SOURCE_READ_TOKEN for this repository with Contents read "
            "access to the selected module sources."
        )
        _atomic_json(report_path, report)
        print(report["configuration_error"], flush=True)
        return report
    installer = fetch_module if operation == "fetch" else install_module
    for name in selected:
        spec = catalog[name]
        try:
            if name == "topos" and operation == "install":
                receipt = installer(name, spec, root, ecosystem_kit=ecosystem_kit)
            else:
                receipt = installer(name, spec, root)
        except Exception as error:
            # Git/build diagnostics can contain credential values. Redact before
            # both truncation and persistence; never emit an unsanitized traceback.
            failure = {"module_id": name, "repository": spec["repository"],
                       "revision": spec["revision"], "error_type": type(error).__name__,
                       "message": _redact(str(error))[-12000:]}
            report["failures"].append(failure)
            summary = {"module": name, "status": "failed", **failure}
        else:
            report["modules"].append(receipt)
            summary = {"module": name, "status": receipt["status"], "revision": receipt["revision"]}
        # Persist before logging so already completed modules survive interruption.
        _atomic_json(report_path, report)
        print(json.dumps(summary, sort_keys=True), flush=True)
    report["completed"] = True
    report["success"] = not report["failures"]
    _atomic_json(report_path, report)
    print(f"Module {operation}: {len(report['modules'])} succeeded, "
          f"{len(report['failures'])} failed. Evidence: {report_path}", flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=("fetch", "install", "geometry_analysis", "topos_request"), required=True)
    parser.add_argument("--ecosystem-kit", type=Path, help="Extracted reviewed mandatory BASE/TOPOS/TORQ kit")
    parser.add_argument("--modules", nargs="+", default=os.environ.get("MODULE_IDS", "").split())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument("--output", type=Path, default=default_root().parent / "evidence")
    parser.add_argument("--require-source-token", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_batch(action=args.action, modules=args.modules, manifest=args.manifest,
                           root=args.root, output=args.output,
                           require_source_token=args.require_source_token, ecosystem_kit=args.ecosystem_kit)
    except (OSError, ValueError) as error:
        print(_redact(f"Module batch configuration failed: {error}"), flush=True)
        return 1
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
