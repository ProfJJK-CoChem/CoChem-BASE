#!/usr/bin/env python3
"""Run the installed TOPOS geometry ingestor in its own Python environment.

This adapter exposes connectivity hashing only. It does not invoke the unvalidated
TOPOS thermodynamics, conformer-search, or remote-dispatch interfaces.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile


MAX_ATOMS = 2048
MAX_INPUT_BYTES = 2 * 1024 * 1024
SCOPE = (
    "Geometry connectivity heuristic using the pinned TOPOS empirical covalent "
    "radii and approximate dispersion weights; a topology hash and fragment flag "
    "are reported. This operation does not calculate energies, prove chemical "
    "bonding, run conformer searches, or validate scientific prediction accuracy."
)


def validate_xyz_bytes(data: bytes) -> int:
    """Require a complete, single-frame, finite, element-only XYZ geometry."""
    from ase.data import atomic_numbers

    if len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"XYZ input exceeds {MAX_INPUT_BYTES} bytes")
    text = data.decode("utf-8")
    lines = text.splitlines()
    if len(lines) < 3 or not lines[0].strip().isascii() or not lines[0].strip().isdigit():
        raise ValueError("XYZ requires an integer atom count, comment, and atom records")
    count = int(lines[0].strip())
    if not 1 <= count <= MAX_ATOMS:
        raise ValueError(f"XYZ atom count must be between 1 and {MAX_ATOMS}")
    if len(lines) < count + 2 or any(line.strip() for line in lines[count + 2 :]):
        raise ValueError("XYZ atom count must match exactly one complete geometry")
    for index, line in enumerate(lines[2 : count + 2], 1):
        fields = line.split()
        if len(fields) != 4 or fields[0] not in atomic_numbers or fields[0] == "X":
            raise ValueError(f"XYZ atom {index} needs a canonical element symbol and three coordinates")
        try:
            coordinates = [float(value) for value in fields[1:]]
        except ValueError as exc:
            raise ValueError(f"XYZ atom {index} has invalid Cartesian coordinates") from exc
        if not all(math.isfinite(value) and abs(value) <= 1e6 for value in coordinates):
            raise ValueError(f"XYZ atom {index} needs finite bounded Cartesian coordinates")
    return count


def _write_exclusive_json(output: Path, report: dict) -> None:
    """Publish a complete result atomically without overwriting an existing file."""
    payload = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".topos-result-", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def execute(artifact: Path, output: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing output: {output}")
    if not artifact.is_file():
        raise ValueError(f"XYZ artifact is not a regular file: {artifact}")
    with artifact.open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    count = validate_xyz_bytes(data)
    provider = importlib.import_module("core_engine.01_INGEST_GC")
    # Give the provider the exact bytes hashed here, avoiding a second read of a
    # user-editable input between validation and calculation.
    with tempfile.TemporaryDirectory(prefix="cochem-topos-ingest-") as working:
        copied_input = Path(working) / artifact.name
        copied_input.write_bytes(data)
        result = provider.process_input_geometry(str(copied_input))
    if not isinstance(result, dict) or result.get("status") != "success":
        raise ValueError(f"TOPOS rejected the geometry: {result}")
    if result.get("atom_count") != count:
        raise ValueError("TOPOS did not ingest the validated number of atoms")
    if not isinstance(result.get("is_complex"), bool) or not isinstance(result.get("topology_hash"), str):
        raise ValueError("TOPOS returned an invalid geometry-ingestion result")
    report = {
        "schema_version": "cochem.module-operation/1",
        "module_id": "topos",
        "operation": "geometry_analysis",
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "scope": SCOPE,
        "result": result,
        "provider_file": str(Path(provider.__file__).resolve()),
    }
    _write_exclusive_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        execute(arguments.artifact, arguments.output)
    except (ImportError, OSError, ValueError, TypeError) as exc:
        print(f"TOPOS geometry ingestion failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
