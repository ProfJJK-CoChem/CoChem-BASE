#!/usr/bin/env python3
"""Run reviewed installed TOPOS public providers under verified BASE authority.

Geometry hypotheses remain distinct from measured native electronic energies,
searches and derivatives invoked through the versioned scientific receiver.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace


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
    text = data.decode("utf-8-sig")
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
    if importlib.util.find_spec("topos") is not None:
        return _execute_current_geometry(data, output)
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


def _execute_current_geometry(data: bytes, output: Path) -> dict:
    """Use the current TOPOS public graph API without inferring an electronic state."""
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    provider = importlib.import_module("topos.chemistry")
    text = data.decode("utf-8-sig")
    lines = text.splitlines()
    if not lines or not lines[0].strip().isdigit():
        raise ValueError("XYZ requires its explicit atom count")
    count = int(lines[0].strip())
    if (not 1 <= count <= MAX_ATOMS or len(lines) < count + 2
            or any(row.strip() for row in lines[count + 2:])
            or any(len(row.split()) != 4 for row in lines[2:count + 2])):
        raise ValueError("XYZ must contain exactly one complete geometry")
    identity = parse_geometry_identity(text)
    # The geometry API consumes only these structural attributes. No charge or
    # spin is guessed from XYZ: this is deliberately not a molecular RunRequest.
    geometry = SimpleNamespace(symbols=list(identity.elements), isotopes=list(identity.mass_numbers),
                               coordinates=[list(row) for row in identity.coordinates_angstrom], bonds=[])
    diagnostics = provider.validate_chemistry(geometry)
    graph = provider.molecular_graph(geometry)
    import networkx as nx
    fragments = [sorted(group) for group in nx.connected_components(graph)]
    nodes = [{"index": index, "element": item["symbol"], "isotope": item["isotope"]}
             for index, item in sorted(graph.nodes(data=True))]
    edges = [{"atom1": min(left, right), "atom2": max(left, right), "order": item["order"], "kind": item["kind"]}
             for left, right, item in graph.edges(data=True)]
    edges.sort(key=lambda edge: (edge["atom1"], edge["atom2"]))
    hypothesis = {"nodes": nodes, "edges": edges, "source": graph.graph["source"]}
    digest = hashlib.sha256(json.dumps(hypothesis, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    result = {"status": "success", "atom_count": count, "is_complex": len(fragments) > 1,
              "topology_hash": digest, "topology_hash_scope": "ordered TOPOS distance-hypothesis graph; not molecular identity",
              "fragments": fragments, "graph": hypothesis, "geometry_diagnostics": diagnostics,
              "nuclear_identity": identity.metadata}
    report = {"schema_version": "cochem.module-operation/1", "module_id": "topos", "operation": "geometry_analysis",
              "input_sha256": hashlib.sha256(data).hexdigest(),
              "scope": "Current TOPOS public Pyykko-radius graph hypothesis and physical geometry diagnostics. Charge, spin, bonding, energy and binding are not inferred from XYZ.",
              "result": result, "provider_file": str(Path(provider.__file__).resolve())}
    _write_exclusive_json(output, report)
    return report


def capabilities() -> dict:
    """Import the installed reviewed receiver; filenames alone grant no operation."""
    operations, source, metadata = [], None, {}
    if importlib.util.find_spec("topos") is not None:
        provider = importlib.import_module("topos.base_provider")
        metadata = provider.metadata()
        approved = {"energy", "gradient", "optimize", "search", "frequency", "thermochemistry", "association", "matrix"}
        if (metadata.get("module_id") != "topos" or metadata.get("integration_contract") != "cochem.module-handoff/1"
                or not callable(getattr(provider, "execute_handoff", None))):
            raise ValueError("Installed TOPOS does not expose the reviewed BASE receiver")
        advertised = metadata.get("operations")
        if not isinstance(advertised, list) or any(not isinstance(item, str) for item in advertised):
            raise ValueError("Installed TOPOS operation metadata is invalid")
        operations = sorted(set(advertised) & approved)
        from topos.base_integration import inspect_ecosystem
        ecosystem = inspect_ecosystem().to_dict()
        if not ecosystem["available"]:
            operations = []
        metadata["mandatory_ecosystem"] = ecosystem
        from topos.method_matrix import load_catalog, resolved_recipe
        from topos.data.runtime_recipes import EXECUTABLE_ROWS
        catalog = load_catalog()
        simple_recipes = []
        for row in catalog.rows:
            if row.row_id not in EXECUTABLE_ROWS:
                continue
            steps, required = resolved_recipe(row)
            if required == ["molecule"] and len(steps) == 1 and steps[0].engine in {"xtb", "orca"}:
                step = steps[0]
                simple_recipes.append({"row_id": row.row_id, "matrix_revision": catalog.revision,
                    "catalog_source_sha256": catalog.source_sha256, "label": row.method_text,
                    "engine": step.engine, "method": step.method, "basis": step.basis,
                    "auxiliary_basis": step.auxiliary_basis, "profile_id": step.profile_id,
                    "matrix_product": "A", "matrix_inputs": {}, "scope": "Compiled recipe; actual engines and outcomes require per-run validation"})
        metadata["student_matrix_recipes"] = simple_recipes
        geometry_provider = importlib.import_module("topos.chemistry")
        if callable(getattr(geometry_provider, "molecular_graph", None)) and callable(getattr(geometry_provider, "validate_chemistry", None)):
            operations.append("geometry_analysis")
        source = Path(provider.__file__).resolve()
    else:
        try:
            provider = importlib.import_module("core_engine.01_INGEST_GC")
        except ModuleNotFoundError:
            provider = None
        if provider is not None and callable(getattr(provider, "process_input_geometry", None)):
            operations = ["geometry_analysis"]
            source = Path(provider.__file__).resolve()
    if source is None:
        raise ValueError("No compatible installed TOPOS receiver is available")
    return {"schema_version": "cochem.module-capabilities/1", "module_id": "topos",
            "operations": operations, "provider_file": str(source),
            "provider_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "provider_metadata": metadata, "scientific_execution_verified": False}


def execute_handoff(handoff: Path, output: Path, registry: Path | None = None) -> dict:
    """Use TOPOS's receiver and mandatory BASE Stage 0 authority for science."""
    provider = importlib.import_module("topos.base_provider")
    from topos.config import SystemConfig

    # Validate the complete handoff inside the actual provider before calculation.
    request, provenance = provider.request_from_handoff(handoff)
    configuration = SystemConfig(execution_backend="base", base_registry_path=registry,
                                 max_threads=request.threads, max_memory_mb=request.memory_mb)
    outcome = provider.execute_handoff(handoff, output.parent / "provider-runs", config=configuration)
    record, receipt = outcome["record"], outcome["receipt"]
    if (receipt.get("artifact_sha256") != provenance["artifact_sha256"]
            or receipt.get("handoff_id") != provenance["handoff_id"]
            or receipt.get("status") != record.get("status")):
        raise ValueError("TOPOS consumption receipt differs from its original BASE handoff")
    # Completed science must have real engine attempts and executable identities;
    # rejected/unavailable/partial outcomes retain their honest provider status.
    if record.get("status") == "completed":
        if receipt.get("execution_provider") != "CoChem-BASE":
            raise ValueError("TOPOS did not execute through mandatory BASE authority")
        attempts = record.get("attempts", [])
        real = [attempt for attempt in attempts if attempt.get("metadata", {}).get("execution_kind") == "real"]
        if not real or any(not attempt.get("metadata", {}).get("executable_sha256") for attempt in real):
            raise ValueError("Completed TOPOS result lacks actual native executable provenance")
    source = Path(provider.__file__).resolve()
    report = {"schema_version": "cochem.module-operation/1", "module_id": "topos",
              "operation": request.purpose, "input_sha256": provenance["artifact_sha256"],
              "provider_file": str(source), "provider_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "status": record["status"],
              "scope": "Actual installed TOPOS workflow through audited BASE execution; accuracy is limited to the selected protocol and retained validation evidence.",
              "result": outcome}
    _write_exclusive_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--artifact", type=Path)
    modes.add_argument("--handoff", type=Path)
    modes.add_argument("--capabilities", action="store_true")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--torq-sidecar", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        # This argument is created from BASE's reviewed installation receipt.
        # It is never accepted from scientific request options or inherited roots.
        os.environ.pop("COCHEM_TORQ_SIDECAR", None)
        if arguments.torq_sidecar is not None:
            os.environ["COCHEM_TORQ_SIDECAR"] = str(arguments.torq_sidecar.resolve(strict=True))
        if arguments.capabilities:
            _write_exclusive_json(arguments.output, capabilities())
        elif arguments.handoff:
            execute_handoff(arguments.handoff, arguments.output, arguments.registry)
        else:
            execute(arguments.artifact, arguments.output)
    except (ImportError, OSError, ValueError, TypeError) as exc:
        print(f"TOPOS geometry ingestion failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
