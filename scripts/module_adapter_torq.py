#!/usr/bin/env python3
"""Transport validated requests to TORQ's installed canonical scientific provider.

This file owns request/artifact integrity checks only. TORQ owns all scientific
operations, including geometry analysis, scans and bond analysis. Invoke it with the module environment's Python and ``-I``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import importlib.util
import importlib
import inspect
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

_SYMBOL = re.compile(r"(?:[1-9][0-9]{0,2}[A-Z][a-z]?|[A-Z][a-z]?(?:-?[1-9][0-9]{0,2})?)\Z")
_MAX_ATOMS = 2000
_MAX_INPUT_BYTES = 2_000_000


def read_xyz(path: Path) -> tuple[list[str], list[list[float]], str]:
    """Read one complete Cartesian XYZ geometry, with coordinates in angstrom."""
    if not path.is_file():
        raise ValueError("The input artifact must be a regular XYZ file.")
    if path.stat().st_size > _MAX_INPUT_BYTES:
        raise ValueError("The XYZ artifact exceeds the 2 MB input limit.")
    raw = path.read_bytes()
    lines = raw.decode("utf-8-sig").splitlines()
    if len(lines) < 3 or not re.fullmatch(r"[1-9][0-9]*", lines[0].strip()):
        raise ValueError("XYZ must start with a positive atom count and a comment line.")
    count = int(lines[0].strip())
    if count < 2 or count > _MAX_ATOMS:
        raise ValueError(f"Rigid-rotor analysis requires 2 to {_MAX_ATOMS} atoms.")
    if len(lines) < count + 2 or any(line.strip() for line in lines[count + 2 :]):
        raise ValueError("XYZ must contain exactly the declared number of atom rows.")
    symbols: list[str] = []
    coordinates: list[list[float]] = []
    for number, line in enumerate(lines[2 : count + 2], start=3):
        fields = line.split()
        if len(fields) != 4 or not _SYMBOL.fullmatch(fields[0]):
            raise ValueError(f"Invalid XYZ atom row {number}; expected symbol and three coordinates.")
        try:
            position = [float(value) for value in fields[1:]]
        except ValueError as exc:
            raise ValueError(f"Invalid numeric coordinate on XYZ row {number}.") from exc
        if not all(math.isfinite(value) for value in position):
            raise ValueError(f"Nonfinite coordinate on XYZ row {number}.")
        label = fields[0]
        suffix = re.fullmatch(r"([A-Z][a-z]?)-?([1-9][0-9]{0,2})", label)
        symbols.append(suffix.group(2) + suffix.group(1) if suffix else {"D": "2H", "T": "3H"}.get(label, label))
        coordinates.append(position)
    for index, position in enumerate(coordinates):
        for previous in coordinates[:index]:
            if math.dist(position, previous) < 1e-8:
                raise ValueError("Two atoms occupy the same position; rigid-rotor input is invalid.")
    return symbols, coordinates, hashlib.sha256(raw).hexdigest()


def _publish_json(path: Path, payload: dict[str, Any]) -> None:
    """Publish a complete strict JSON file atomically, without overwriting one."""
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".torq-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # An atomic link fails if the destination already exists, including a
        # dangling symlink. It cannot replace an artifact created concurrently.
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


_EXTENSION_OPERATIONS = {"geometry_analysis", "research_scan", "wiberg_lowdin", "nbo_analysis", "wiberg_nao"}


def _extension_provider() -> tuple[dict, Any, Path] | None:
    """Admit only the installed distribution's versioned scientific entry point."""
    distribution = importlib.metadata.distribution("CoChem-TORQ")
    entries = [entry for entry in distribution.entry_points if entry.group == "cochem.modules" and entry.name == "torq"]
    if not entries:
        return None
    if len(entries) != 1:
        raise ValueError("TORQ has ambiguous scientific provider entry points.")
    entry = entries[0]
    if not entry.module.startswith("cochem_torq."):
        raise ValueError("TORQ provider must live in its installed scientific namespace.")
    metadata = entry.load()()
    if not isinstance(metadata, dict) or metadata.get("scientific_api_version") != "cochem.module-provider/1":
        return None  # Current upstream discovery-only metadata is not execution authority.
    if metadata.get("module_id") != "torq" or metadata.get("integration_contract") != "cochem.module-handoff/1":
        raise ValueError("TORQ scientific provider declares an incompatible integration contract.")
    operations = metadata.get("operations")
    if not isinstance(operations, list) or any(not isinstance(item, str) for item in operations) or len(set(operations)) != len(operations):
        raise ValueError("TORQ scientific operations must be an exact unique list.")
    handler = metadata.get("execute_handoff")
    if isinstance(handler, str):
        if not re.fullmatch(r"cochem_torq(?:\.[A-Za-z_][A-Za-z0-9_]*)+:[A-Za-z_][A-Za-z0-9_]*", handler):
            raise ValueError("TORQ scientific handler must be a qualified callable in its own namespace.")
        module_name, name = handler.split(":")
        handler = getattr(importlib.import_module(module_name), name)
    if not inspect.isfunction(handler) or not handler.__module__.startswith("cochem_torq."):
        raise ValueError("TORQ scientific handler is not an installed TORQ function.")
    signature = inspect.signature(handler)
    for name in ("handoff_path", "output_directory", "registry"):
        if name not in signature.parameters:
            raise ValueError("TORQ scientific handler must accept handoff_path, output_directory and registry.")
    source_name = inspect.getsourcefile(handler)
    if not source_name:
        raise ValueError("TORQ scientific handler has no auditable installed source file.")
    if Path(source_name).is_symlink():
        raise ValueError("TORQ scientific handler source cannot be a symlink.")
    source = Path(source_name).resolve(strict=True)
    distribution_root = Path(distribution.locate_file("")).resolve()
    if not source.is_relative_to(distribution_root) or source.is_symlink():
        raise ValueError("TORQ scientific handler is outside its installed distribution.")
    known_files = {Path(distribution.locate_file(item)).resolve(): item for item in distribution.files or []}
    record = known_files.get(source)
    if record is None:
        raise ValueError("TORQ scientific handler is absent from the installed wheel record.")
    recorded_hash = record.hash
    digest = hashlib.sha256(source.read_bytes()).digest()
    if (recorded_hash is None or recorded_hash.mode != "sha256"
            or recorded_hash.value != base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")):
        raise ValueError("TORQ scientific handler differs from its installed wheel record.")
    science = metadata.get("scientific_apis", {})
    if not isinstance(science, dict):
        raise ValueError("TORQ scientific operation metadata must be an exact mapping.")
    for operation in operations:
        definition = science.get(operation, {})
        if type(definition.get("available")) is not bool:
            raise ValueError("TORQ must explicitly observe scientific operation availability.")
        dependencies = definition.get("required_engines")
        supported = definition.get("supported_engines")
        if (not isinstance(dependencies, list) or any(item not in {"orca", "cfour", "pyscf", "nbo"} for item in dependencies)
                or not isinstance(supported, list) or (operation != "geometry_analysis" and not supported)
                or any(item not in {"orca", "pyscf"} for item in supported)):
            raise ValueError("TORQ must declare actual required runtimes and supported execution engines.")
        if not isinstance(definition.get("scope"), str) or not definition["scope"].strip():
            raise ValueError("TORQ scientific operation requires an explicit physical scope.")
        if definition["available"]:
            receipts = definition.get("runtime_receipts", {})
            if not isinstance(receipts, dict):
                raise ValueError("Available TORQ scientific operations require actual runtime receipts.")
            for dependency in dependencies:
                receipt = receipts.get(dependency, {})
                if receipt.get("available") is not True or not isinstance(receipt.get("version"), str) or not receipt["version"].strip():
                    raise ValueError(f"TORQ did not verify the required {dependency} runtime.")
                filename = receipt.get("executable_path") if dependency in {"orca", "cfour", "nbo"} else receipt.get("module_file")
                runtime = Path(filename or "")
                if runtime.is_symlink() or not runtime.is_file():
                    raise ValueError(f"TORQ's required {dependency} runtime is absent or is not a regular observed file.")
                if dependency in {"orca", "cfour", "nbo"} and not os.access(runtime, os.X_OK):
                    raise ValueError(f"TORQ's required {dependency} runtime is not executable.")
                with runtime.open("rb") as stream:
                    actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
                if receipt.get("sha256") != actual_hash:
                    raise ValueError(f"TORQ's required {dependency} runtime differs from its actual source receipt.")
    return metadata, handler, source

def capabilities() -> dict[str, Any]:
    """Expose only operations from the installed canonical scientific contract."""
    provider = _extension_provider()
    if provider is None:
        raise ValueError("The installed TORQ lacks the required canonical scientific provider contract.")
    metadata, _, source = provider
    science = metadata["scientific_apis"]
    return {"schema_version": "cochem.module-capabilities/1", "module_id": "torq",
            "operations": [name for name in metadata["operations"] if science[name]["available"]],
            "provider_file": str(source), "provider_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "provider_distribution": "CoChem-TORQ", "provider_version": importlib.metadata.version("CoChem-TORQ"),
            "integration_contract": "cochem.module-handoff/1",
            "scientific_api_version": metadata["scientific_api_version"], "scientific_apis": science,
            "provider_sources": [{"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}


def _load_handoff(path: Path) -> tuple[dict, Path, list[str], list[list[float]]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("The handoff must be a bounded retained JSON file.")
    record = json.loads(path.read_bytes())
    json.dumps(record, allow_nan=False)
    if (record.get("schema_version") != "cochem.module-handoff/1" or record.get("module_id") != "torq"
            or record.get("operation") not in _EXTENSION_OPERATIONS or record.get("scientific_execution_performed") is not False):
        raise ValueError("Unsupported TORQ research handoff.")
    reference = record.get("artifact", {})
    filename = reference.get("filename", "")
    if Path(filename).name != filename or reference.get("kind") != "geometry_xyz":
        raise ValueError("TORQ scans require an immutable XYZ handoff.")
    artifact = path.parent / filename
    if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size != reference.get("size_bytes"):
        raise ValueError("The handoff geometry is absent or has changed.")
    symbols, positions, digest = read_xyz(artifact)
    if digest != reference.get("sha256"):
        raise ValueError("The handoff geometry checksum has changed.")
    return record, artifact, symbols, positions


def execute_extension(handoff_path: Path, directory: Path, registry: Path | None) -> dict[str, Any]:
    """Delegate compatible future science only to the actual installed provider."""
    record, _, _, _ = _load_handoff(handoff_path)
    operation = record["operation"]
    provider = _extension_provider()
    if provider is None or operation not in capabilities()["operations"]:
        raise ValueError("The installed TORQ provider does not currently support this scientific operation.")
    metadata, handler, source = provider
    # Model, isotope, geometry and analysis mathematics belong to canonical TORQ.
    # BASE already validated the typed request before publishing this handoff.
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    payload = handler(handoff_path=handoff_path, output_directory=directory, registry=registry)
    json.dumps(payload, allow_nan=False)
    if (not isinstance(payload, dict) or payload.get("schema_version") != "cochem.module-operation/1"
            or payload.get("module_id") != "torq" or payload.get("operation") != operation
            or payload.get("input_sha256") != record["artifact"]["sha256"]
            or Path(payload.get("provider_file", "")).resolve() != source
            or payload.get("provider_sha256") != digest
            or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
        raise ValueError("The TORQ scientific operation receipt differs from its verified provider or input.")
    if _load_handoff(handoff_path)[0] != record:
        raise ValueError("The scientific handoff changed during TORQ execution.")
    return payload

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--handoff", type=Path)
    mode.add_argument("--capabilities", action="store_true")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if os.path.lexists(args.output):
            raise FileExistsError("The requested result artifact already exists.")
        if args.capabilities:
            payload = capabilities()
        else:
            payload = execute_extension(args.handoff, args.output.parent.resolve(), args.registry)
        _publish_json(args.output, payload)
    except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"TORQ operation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
