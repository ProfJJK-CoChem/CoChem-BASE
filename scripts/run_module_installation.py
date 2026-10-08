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
    _redact,
    default_root,
    fetch_module,
    install_module,
    load_manifest,
)


def run_batch(*, action: str, modules: list[str], manifest: Path,
              root: Path, output: Path, require_source_token: bool = False) -> dict:
    """Attempt every selected module, without discarding earlier outcomes."""
    if action not in {"fetch", "install", "geometry_analysis"}:
        raise ValueError("Unsupported module action.")
    output = output.expanduser().resolve()
    if output == REPOSITORY_ROOT or output.is_relative_to(REPOSITORY_ROOT):
        raise ValueError("Module evidence must be written outside the BASE source checkout.")
    catalog_document = load_manifest(manifest)
    catalog = catalog_document["modules"]
    selected = list(dict.fromkeys(modules))
    if not selected or any(name not in catalog for name in selected):
        raise ValueError("Select module IDs from the reviewed distribution manifest.")
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
    if require_source_token and not os.environ.get("COCHEM_SOURCE_CREDENTIAL"):
        report["configuration_error"] = (
            "Instructor-configured source access is unavailable. Authorize this private project for Contents read "
            "access to the selected module sources."
        )
        _atomic_json(report_path, report)
        print(report["configuration_error"], flush=True)
        return report
    installer = fetch_module if operation == "fetch" else install_module
    for name in selected:
        spec = catalog[name]
        try:
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
    parser.add_argument("--action", choices=("fetch", "install", "geometry_analysis"), required=True)
    parser.add_argument("--modules", nargs="+", default=os.environ.get("MODULE_IDS", "").split())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument("--output", type=Path, default=default_root().parent / "evidence")
    parser.add_argument("--require-source-token", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_batch(action=args.action, modules=args.modules, manifest=args.manifest,
                           root=args.root, output=args.output,
                           require_source_token=args.require_source_token)
    except (OSError, ValueError) as error:
        print(_redact(f"Module batch configuration failed: {error}"), flush=True)
        return 1
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
