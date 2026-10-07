"""Validate immutable test inputs without waiving arbitrary runtime artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def validate_source_fixtures(root: Path, manifest: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("fixtures"), list):
        raise ValueError("Invalid source-fixture manifest schema")
    seen: set[str] = set()
    records = []
    for entry in payload["fixtures"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] not in (("tests",), ("examples",)):
            raise ValueError(f"Source fixture must be a specific test input: {relative}")
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root / relative.parts[0]):
            raise ValueError(f"Source fixture escapes test tree: {relative}")
        name = relative.as_posix()
        if name in seen:
            raise ValueError(f"Duplicate source fixture: {name}")
        seen.add(name)
        for field in ("purpose", "provenance_status", "provenance"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Source fixture requires explicit {field}: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry.get("sha256"):
            raise ValueError(f"Source fixture content changed: {name}")
        records.append(dict(entry))
    return records
