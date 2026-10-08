#!/usr/bin/env python3
"""Accept the real BASE-to-installed-TOPOS student route with native xTB.

This is instructor/CI validation, not a command students need to run. It creates
two original monomer inputs and exercises the same data-only research service as
the GUI and Actions worker. A bounded search is not an exhaustive isomer search.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from cochem_base.interfaces.student_research import (
    SCHEMA, assemble_monomers, build_topos_request, execute_provider_request,
)

WATER = "3\nStudent-route acceptance starting geometry, angstrom\nO 0 0 0\nH .9572 0 0\nH -.23999 .9273 0\n"


def _run_case(name: str, xyz: str, request: dict, output: Path, *, root: Path,
              manifest: Path | None, registry: Path) -> dict:
    folder = output / name
    inputs = folder / "submitted/inputs"
    inputs.mkdir(parents=True)
    artifact = inputs / "geometry.xyz"
    artifact.write_text(xyz, encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    envelope = {"schema_version": SCHEMA, "module": "topos", "operation": request["purpose"],
                "artifact": "inputs/geometry.xyz", "artifact_sha256": digest,
                "options": {"topos_request": request}}
    (folder / "submitted/request.json").write_text(json.dumps(envelope, indent=2, allow_nan=False) + "\n")
    result = execute_provider_request(envelope, folder / "submitted", folder / "executed", root=root,
                                     manifest=manifest, registry=registry,
                                     resources={"cores": request["threads"], "memory_mb": request["memory_mb"],
                                                "budget_seconds": request["budget_seconds"]})
    if result["status"] != "completed" or not result["operation_performed"]:
        raise ValueError("Student TOPOS " + name + " did not complete: " + result["status"])
    record, receipt = result["result"]["record"], result["result"]["receipt"]
    if (record["status"] != "completed" or receipt["execution_provider"] != "CoChem-BASE"
            or receipt["artifact_sha256"] != digest or result["input_sha256"] != digest):
        raise ValueError("Native student result differs from the submitted source or BASE authority")
    attempts = [attempt for attempt in record["attempts"] if attempt["metadata"].get("execution_kind") == "real"]
    if not attempts or any(not attempt.get("engine_version") or len(attempt["metadata"].get("executable_sha256", "")) != 64 for attempt in attempts):
        raise ValueError("Native student result lacks executable/version provenance")
    energies = [candidate["energy_hartree"] for candidate in record["candidates"] if candidate["energy_hartree"] is not None]
    if not energies or any(isinstance(energy, bool) or not math.isfinite(energy) for energy in energies):
        raise ValueError("Native student result lacks finite measured candidate energies")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
        raise ValueError("Student starting geometry changed during provider execution")
    return {"operation": request["purpose"], "status": record["status"], "input_sha256": digest,
            "candidate_energies_hartree": energies, "real_native_attempts": len(attempts),
            "consumption_receipt": receipt, "module_revision": result["revision"],
            "provider_sha256": result["provider_sha256"], "result_file": str(folder / "executed/execution/result.json"),
            "result_sha256": hashlib.sha256((folder / "executed/execution/result.json").read_bytes()).hexdigest(),
            "electronic_weights_status": record.get("metadata", {}).get("electronic_weights_status")}


def accept(output: Path, *, root: Path, manifest: Path | None, registry: Path) -> dict:
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    energy = build_topos_request(WATER, operation="energy", charge=0, multiplicity=1,
                                 options={"threads": 1, "memory_mb": 1024, "budget_seconds": 60})
    assembled = assemble_monomers([{"xyz": WATER, "charge": 0, "multiplicity": 1}] * 2,
                                  separation_angstrom=4)
    search = assembled["topos_request"]
    search.update(purpose="search", threads=1, memory_mb=1024, budget_seconds=300,
                  n_candidates=2, seed=173, profile_id="xtb-tight-v1")
    cases = [_run_case("student-monomer-energy", WATER, energy, output, root=root, manifest=manifest, registry=registry),
             _run_case("student-monomers-complex-search", assembled["xyz"], search, output,
                       root=root, manifest=manifest, registry=registry)]
    report = {"schema_version": "cochem.student-research-acceptance/1", "status": "passed",
              "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(), "cases": cases,
              "scope": "Real isolated installed TOPOS, audited BASE authority and native xTB. Instructor acceptance, not an actual enrolled student pilot or universal chemistry-accuracy claim."}
    (output / "acceptance.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = accept(args.output, root=args.root, manifest=args.manifest, registry=args.registry.resolve(strict=True))
    print(json.dumps({"status": report["status"], "cases": len(report["cases"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
