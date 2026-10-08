#!/usr/bin/env python3
"""Validate a bounded Classroom request and run its real licensed calculation.

The input is a CalculationMatrixConfig JSON document, never an ORCA deck or
shell command. Runtime data and scientific evidence stay outside the checkout.
The preflight-only mode uses the standard library before BASE is installed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
from typing import Any

# The pre-installation preflight loads one reviewed local module directly because
# interfaces/__init__.py imports the installed scientific dependencies.
def _request_contract():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "src/cochem_base/interfaces/actions_jobs.py"
    spec = importlib.util.spec_from_file_location("cochem_actions_request_contract", path)
    if spec is None or spec.loader is None:
        raise ImportError("The shared Actions request validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_contract = _request_contract()
MAX_JOB_BYTES = _contract.MAX_JOB_BYTES
validate_resources = _contract.validate_resources
preflight_configuration = _contract.preflight_configuration
validate_configuration = _contract.validate_configuration
decode_configuration = _contract.decode_configuration

def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_job_file(repository: Path, job_file: str) -> tuple[Path, bytes, dict[str, Any]]:
    """Reject traversal, symlink components, special files and oversized JSON."""
    repository = repository.resolve(strict=True)
    relative = PurePosixPath(job_file)
    if (not job_file or "\\" in job_file or any(ord(char) < 32 for char in job_file) or relative.is_absolute()
            or any(part in (".", "..") for part in job_file.split("/"))
            or relative.suffix != ".json"):
        raise ValueError("job_file must be a repository-relative .json path without traversal")
    source = repository
    for component in relative.parts:
        source = source / component
        if source.is_symlink():
            raise ValueError("Job inputs cannot use symlinks")
    if not source.resolve(strict=True).is_relative_to(repository):
        raise ValueError("Job input escapes the repository")
    metadata = source.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Job input must be a regular file")
    if metadata.st_size > MAX_JOB_BYTES:
        raise ValueError("Job JSON exceeds the 256 KiB limit")
    with source.open("rb") as stream:
        contents = stream.read(MAX_JOB_BYTES + 1)
    if len(contents) > MAX_JOB_BYTES:
        raise ValueError("Job JSON exceeds the 256 KiB limit")
    data = decode_configuration(contents)
    return source, contents, data


def _atomic_write(destination: Path, contents: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".job-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run_job(repository: Path, job_file: str, *, registry: Path, output: Path,
            cores: int = 2, maxcore_mb: int = 512, engine: str = "orca") -> dict[str, Any]:
    from cochem_base.calc.calculation_service import _external_run_path, run_calculation
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results

    output = _external_run_path(output)
    if output.is_relative_to(repository.resolve()):
        raise ValueError("Calculation output must be outside the submitted repository")
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": "cochem.actions-calculation/1", "status": "failed",
        "scientific_execution_performed": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_job_file": job_file, "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_sha": os.environ.get("GITHUB_SHA"), "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "requested_cores": cores, "requested_maxcore_mb": maxcore_mb,
    }
    try:
        validate_resources(cores, maxcore_mb)
        _, contents, data = read_job_file(repository, job_file)
        _atomic_write(output / "submitted-job.json", contents)
        report["submitted_job_sha256"] = sha256(output / "submitted-job.json")
        _atomic_write(output / "submitted-job.json.sha256",
                      f"{report['submitted_job_sha256']}  submitted-job.json\n".encode())
        config = validate_configuration(contents, data)
        if config.engine != engine:
            raise ValueError(f"The {engine.upper()} workflow requires engine='{engine}'")
        report["engine"] = engine
        validated = output / "validated-job.json"
        _atomic_write(validated, (config.model_dump_json(indent=2) + "\n").encode())
        authority = authorize_engine_execution(engine, registry_path=registry, cores=cores,
                                               maxcore_mb=maxcore_mb)
        report.update(engine_binary_sha256=authority.binary_sha256, registry_sha256=sha256(registry),
                      operation="harmonic_frequencies" if config.is_freq else "optimization" if config.is_opt else "single_point")
        result = run_calculation(validated, scratch=output / "scratch", output=output / "calculation",
                                 registry_path=registry, threads=cores, maxcore_mb=maxcore_mb, device="cpu")
        if result["status"] != "EXECUTION_VERIFIED":
            raise RuntimeError(f"Requested calculation was not completed: {result['status']}")
        report["scientific_execution_performed"] = True
        if result.get("operation") != report["operation"]:
            raise RuntimeError("Completed operation differs from the requested scientific operation")
        publication = output / "calculation"
        accepted = json.loads((publication / "result.json").read_text())
        actual_authority = json.loads((publication / "execution_authority.json").read_text())
        if (actual_authority["cores"] != cores or actual_authority["maxcore_mb"] != maxcore_mb
                or actual_authority["binary_sha256"] != authority.binary_sha256):
            raise RuntimeError("Published execution allocation or engine differs from the authorized job")
        if config.is_freq:
            frequencies = accepted.get("harmonic_frequencies_cm1")
            masses = accepted.get("principal_isotope_masses_u")
            hessian = accepted.get("hessian_artifact", {})
            atom_count = len(accepted.get("elements", []))
            if (not isinstance(frequencies, list) or not all(math.isfinite(value) for value in frequencies)
                    or len(masses or []) != atom_count
                    or not all(math.isfinite(value) and value > 0 for value in masses)
                    or hessian.get("shape") != [3 * atom_count, 3 * atom_count]
                    or len(frequencies) != 3 * atom_count - hessian.get("rigid_mode_count", -1)
                    or hessian.get("unit") != "hartree/bohr^2"):
                raise RuntimeError("Requested frequencies lack finite modes, principal masses or the physical Hessian")
            report.update(harmonic_frequencies_cm1=frequencies, principal_isotope_masses_u=masses,
                          hessian_artifact=hessian,
                          optimization_performed=accepted.get("optimization_performed", False))
        energy = accepted["energy_hartree"]
        if accepted.get("engine") != engine or accepted.get("converged") is not True or not math.isfinite(energy):
            raise RuntimeError(f"Missing converged finite {engine.upper()} result")
        store = Path(accepted["telemetry_path"])
        telemetry = read_scientific_results(accepted["telemetry_job_id"], store_path=store)
        # Optimization legitimately retains all streamed geometry/energy frames.
        # The final converged result must be the last record, not the only record.
        metadata = telemetry.get("metadata", [])
        if (telemetry["elements"] != accepted["elements"] or len(telemetry["energy_hartree"]) < 1
                or float(telemetry["energy_hartree"][-1]) != energy or not metadata
                or metadata[-1].get("converged") is not True
                or metadata[-1].get("operation") != report["operation"]
                or telemetry["coordinates_angstrom"][-1].tolist() != accepted["coordinates_angstrom"]):
            raise RuntimeError("Canonical scientific archive differs from the published engine result")
        report["scientific_archive_record_count"] = len(telemetry["energy_hartree"])
        shutil.copy2(store, output / "complexes.h5")
        shutil.copy2(registry, output / "stage0-registry.json")
        report.update(status="passed", scientific_execution_performed=True, energy_hartree=energy,
                      execution=result, telemetry_job_id=accepted["telemetry_job_id"],
                      archive="complexes.h5")
        return report
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        _atomic_write(output / "calculation-report.json",
                      (json.dumps(report, indent=2, allow_nan=False) + "\n").encode())
        manifest = {path.relative_to(output).as_posix(): {"sha256": sha256(path), "size_bytes": path.stat().st_size}
                    for path in sorted(output.rglob("*")) if path.is_file() and path.name != "publication-manifest.json"}
        _atomic_write(output / "publication-manifest.json",
                      (json.dumps(manifest, indent=2) + "\n").encode())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--job-file", required=True)
    parser.add_argument("--engine", choices=("orca", "cfour"), default="orca")
    parser.add_argument("--cores", type=int, default=2)
    parser.add_argument("--maxcore-mb", type=int, default=512)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.preflight_only:
            validate_resources(arguments.cores, arguments.maxcore_mb)
            _, _, data = read_job_file(arguments.repository, arguments.job_file)
            if data.get("engine", "orca") != arguments.engine:
                raise ValueError(f"The {arguments.engine.upper()} workflow requires engine='{arguments.engine}'")
            preflight_configuration(data)
            print("Input path, JSON and resource preflight passed; full scientific validation follows Stage 0 setup.")
        else:
            if arguments.registry is None or arguments.output is None:
                parser.error("--registry and --output are required for execution")
            report = run_job(arguments.repository, arguments.job_file, registry=arguments.registry,
                             output=arguments.output, cores=arguments.cores, maxcore_mb=arguments.maxcore_mb,
                             engine=arguments.engine)
            print(json.dumps(report, indent=2))
    except Exception as error:
        print(f"{arguments.engine.upper()} calculation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
