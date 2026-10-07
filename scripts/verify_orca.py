#!/usr/bin/env python3
"""Run real serial and two-process ORCA jobs through the canonical BASE CLI.

Requires a completed Stage 0 registry for this host and ORCA 6.1.1. Absence of
either is an acceptance failure, never a skipped or simulated calculation.
This checks installation, MPI execution, provenance and BASE publication; a
small HF/STO-3G calculation does not establish spectroscopic accuracy.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from cochem_base.calc.calculation_service import CalculationMatrixConfig, _external_run_path
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run


ROOT = Path(__file__).resolve().parents[1]
WATER = "O 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n"
EXPECTED_VERSION = "6.1.1"
ENERGY_TOLERANCE_HARTREE = 1e-8


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_publication(directory: Path, *, cores: int, binary_hash: str) -> dict:
    """Validate actual published evidence without trusting exit status alone."""
    execution = json.loads((directory / "execution.json").read_text(encoding="utf-8"))
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    authority = json.loads((directory / "execution_authority.json").read_text(encoding="utf-8"))
    require(execution["status"] == "EXECUTION_VERIFIED", "BASE did not certify execution")
    require(result["engine"] == "orca" and result["converged"] is True, "Missing converged ORCA result")
    require(result["elements"] == ["O", "H", "H"], "Published molecule differs from submitted water")
    require(authority["cores"] == cores, "Published allocation differs from requested process count")
    require(authority["binary_sha256"] == binary_hash, "Published executable differs from audited ORCA")
    decks = list(directory.glob("*_job.inp"))
    logs = list(directory.glob("*_job.out"))
    schemas = list(directory.glob("*_qcschema.json"))
    require(len(decks) == len(logs) == len(schemas) == 1, "Missing unique input/output/QCSchema evidence")
    deck, log, schema_path = decks[0], logs[0], schemas[0]
    require(bool(re.search(rf"\bnprocs\s+{cores}\b", deck.read_text())), "ORCA deck has incorrect MPI allocation")
    content = log.read_text(encoding="utf-8", errors="replace")
    versions = re.findall(r"\bProgram Version\s+(\d+\.\d+\.\d+)\b", content, flags=re.I)
    require(bool(versions) and set(versions) == {EXPECTED_VERSION}, "Real calculation did not report ORCA 6.1.1")
    require(content.count("ORCA TERMINATED NORMALLY") == 1, "Missing unique ORCA normal termination")
    require(bool(re.search(r"SCF CONVERGED AFTER\s+\d+\s+CYCLES", content, flags=re.I)), "Missing actual SCF convergence")
    if cores > 1:
        require(bool(re.search(rf"Program running with\s+{cores}\s+parallel MPI-processes", content, flags=re.I)),
                "ORCA output does not confirm the requested parallel MPI execution")
    printed = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+(?:[EeDd][-+]?\d+)?)", content)
    require(len(printed) == 1, "Expected one single-point energy from the real engine")
    energy = float(printed[0].replace("D", "E").replace("d", "e"))
    require(math.isfinite(energy), "Nonfinite electronic energy")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    require(energy == result["energy_hartree"] == schema["properties"]["return_energy"],
            "Published energies disagree with actual ORCA output")
    require(schema["properties"]["scf_iterations"] > 0, "Missing physical SCF iterations")
    require(schema["provenance"]["log_sha256"] == sha256(log), "QCSchema output provenance mismatch")
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results

    telemetry = read_scientific_results(result["telemetry_job_id"], store_path=result["telemetry_path"])
    require(telemetry["elements"] == ["O", "H", "H"] and len(telemetry["energy_hartree"]) == 1,
            "Canonical HDF5 archive is missing the completed water calculation")
    require(float(telemetry["energy_hartree"][0]) == energy, "HDF5 archive energy differs from ORCA output")
    for artifact in directory.rglob("*"):
        if artifact.is_file() and not artifact.name.endswith(".sha256"):
            stamp = artifact.with_name(artifact.name + ".sha256")
            require(stamp.is_file() and stamp.read_text().split()[0] == sha256(artifact),
                    f"Invalid published artifact checksum: {artifact.name}")
    return {"cores": cores, "energy_hartree": energy, "version": versions[0],
            "normal_termination": True, "scf_converged": True,
            "scf_iterations": schema["properties"]["scf_iterations"],
            "input_sha256": sha256(deck), "output_sha256": sha256(log),
            "telemetry_path": result["telemetry_path"], "telemetry_job_id": result["telemetry_job_id"],
            "output_directory": str(directory), "execution_authority": authority}


def run_acceptance(registry: Path, output: Path, *, timeout: float = 180.0) -> dict:
    """Retain a failed report on every attempted acceptance, including preflight."""
    output = _external_run_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "Acceptance report already exists; select a fresh output path")
    work = Path(tempfile.mkdtemp(prefix="orca-acceptance-", dir=output.parent))
    started = time.monotonic()
    report = {"status": "failed", "scope": "ORCA installation, MPI and BASE execution/publication",
              "scientific_accuracy_established": False, "expected_version": EXPECTED_VERSION,
              "method": "HF", "basis": "STO-3G", "charge": 0, "multiplicity": 1,
              "geometry_angstrom": WATER, "work_directory": str(work),
              "registry_path": str(registry.resolve()), "calculations": {},
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "github_run_id": os.environ.get("GITHUB_RUN_ID"),
              "github_sha": os.environ.get("GITHUB_SHA")}
    try:
        require(math.isfinite(timeout) and timeout > 0, "Timeout must be positive and finite")
        # Two-process authority must be available before either calculation starts.
        authority = authorize_engine_execution("orca", registry_path=registry, cores=2)
        report.update(binary_path=authority.executable, binary_sha256=authority.binary_sha256,
                      registry_sha256=sha256(registry))
        if os.environ.get("COCHEM_ORCA_PROVENANCE"):
            provenance = Path(os.environ["COCHEM_ORCA_PROVENANCE"])
            report["provisioning_provenance"] = json.loads(provenance.read_text(encoding="utf-8"))
            report["provisioning_provenance_sha256"] = sha256(provenance)
        config = CalculationMatrixConfig(geometry=WATER, engine="orca", method="HF",
                                         basis_set="STO-3G", is_opt=False, timeout_seconds=timeout)
        config_path = work / "water.json"
        config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        environment = dict(os.environ, COCHEM_CONFIG=str(registry.resolve()),
                           ORCA_CMD=authority.executable, ORCA_PATH=authority.executable,
                           COCHEM_ORCA_BIN=authority.executable,
                           OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        environment["PATH"] = str(Path(authority.executable).parent) + os.pathsep + environment.get("PATH", "")
        for label, cores in (("serial", 1), ("parallel", 2)):
            output_directory = work / label
            command = [sys.executable, str(ROOT / "cli.py"), "run", "--config", str(config_path),
                       "--threads", str(cores), "--device", "cpu", "--scratch", str(work / "scratch"),
                       "--output", str(output_directory), "--json"]
            completed = safe_subprocess_run(command, cwd=work, env=environment, timeout=timeout + 90,
                                            capture_output=True, text=True, check=False,
                                            load_full_stdout=True, required_disk_gb=0.1)
            (work / f"{label}.stdout.log").write_text(completed.stdout or "", encoding="utf-8")
            (work / f"{label}.stderr.log").write_text(completed.stderr or "", encoding="utf-8")
            require(completed.returncode == 0, f"BASE {label} calculation exited {completed.returncode}; see {work}")
            cli_result = json.loads(completed.stdout)
            require(cli_result["status"] == "EXECUTION_VERIFIED", f"BASE {label} execution was not verified")
            require(not Path(cli_result["scratch_dir"]).exists(), "Successful scratch directory was not cleaned")
            report["calculations"][label] = validate_publication(
                output_directory, cores=cores, binary_hash=authority.binary_sha256)
        difference = abs(report["calculations"]["serial"]["energy_hartree"] -
                         report["calculations"]["parallel"]["energy_hartree"])
        report.update(energy_difference_hartree=difference,
                      energy_tolerance_hartree=ENERGY_TOLERANCE_HARTREE)
        require(difference <= ENERGY_TOLERANCE_HARTREE, "Serial and parallel energies disagree beyond 1e-8 Eh")
        require(sha256(Path(authority.executable)) == authority.binary_sha256, "ORCA executable changed during acceptance")
        report["status"] = "passed"
        return report
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        report = run_acceptance(args.registry, args.output, timeout=args.timeout)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ORCA acceptance FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
