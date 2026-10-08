#!/usr/bin/env python3
"""Consume a Codespaces staging receipt in its owning private Actions project."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_LIMIT = 48 * 1024


def load_workflow_receipt(engine: str) -> dict[str, Any]:
    from scripts.private_engine_assets import load_staging_receipt, validate_actions_context

    raw = os.environ.get("COCHEM_STAGING_RECEIPT", "").encode("utf-8")
    expected = os.environ.get("COCHEM_STAGING_RECEIPT_SHA256", "")
    task = os.environ.get("COCHEM_STAGING_TASK_ID", "")
    if (
        not raw or len(raw) > RECEIPT_LIMIT
        or re.fullmatch(r"[0-9a-f]{64}", expected) is None
        or re.fullmatch(r"[0-9a-f]{32}", task) is None
    ):
        raise ValueError("Supply the exact private staging receipt, checksum, and task identity.")
    receipt = load_staging_receipt(raw, expected)
    if receipt["engine"] != engine or receipt["task_id"] != task:
        raise ValueError("The workflow engine/task differs from its immutable staging receipt.")
    validate_actions_context(receipt)
    return receipt


def _outside_checkout(path: Path) -> Path:
    selected = path.expanduser().absolute()
    if any(parent.is_symlink() for parent in (selected, *selected.parents)):
        raise ValueError("Engine evidence paths must not use symbolic links.")
    resolved = selected.resolve()
    if resolved.is_relative_to(ROOT):
        raise ValueError("Licensed downloads and private descriptors belong outside the checkout.")
    return resolved


def consume(engine: str, archive: Path, descriptor: Path, receipt_output: Path) -> dict[str, Any]:
    from scripts.private_engine_assets import consume_staged_asset

    if engine not in ("orca", "cfour"):
        raise ValueError("Use the explicit ORCA or CFOUR provisioning route.")
    receipt = load_workflow_receipt(engine)
    archive, descriptor, receipt_output = [
        _outside_checkout(path) for path in (archive, descriptor, receipt_output)
    ]
    if any(path.exists() for path in (archive, descriptor, receipt_output)):
        raise ValueError("A staging consumption must not overwrite an existing file.")
    approved = receipt["approved_distribution"]
    if archive.name != approved["archive_name"]:
        raise ValueError("The destination archive name differs from the reviewed distribution.")
    encoded = json.dumps(
        approved, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != receipt["approved_distribution_sha256"]:
        raise ValueError("The staged approved distribution identity differs.")
    descriptor.parent.mkdir(parents=True, exist_ok=True)
    with descriptor.open("xb") as output:
        output.write(encoded)
    try:
        if engine == "orca":
            from scripts.provision_orca import load_distribution_manifest
        else:
            from scripts.provision_cfour import load_distribution_manifest
        actual = load_distribution_manifest(descriptor)
        if actual != approved:
            raise ValueError("The private distribution descriptor changed during validation.")
        consume_staged_asset(receipt, destination=archive)
        if not archive.is_file() or archive.is_symlink():
            raise ValueError("The staged transfer returned no actual regular archive.")
        checksum = hashlib.sha256()
        with archive.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(block)
        if (
            checksum.hexdigest() != approved["sha256"]
            or archive.stat().st_size != receipt["destination"]["size_bytes"]
        ):
            raise ValueError("The received archive differs from its original approved bytes.")
        receipt_output.parent.mkdir(parents=True, exist_ok=True)
        with receipt_output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    except BaseException:
        archive.unlink(missing_ok=True)
        descriptor.unlink(missing_ok=True)
        raise
    return {
        "engine": engine, "task_id": receipt["task_id"],
        "archive_path": str(archive), "descriptor_path": str(descriptor),
        "archive_sha256": checksum.hexdigest(),
        "scientific_calculation_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("orca", "cfour"), required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    consume(args.engine, args.archive, args.descriptor, args.receipt_output)
    print("Original approved staged asset bytes verified in the owning private project.")
    print("Archive integrity is separate from native installation and calculation acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
