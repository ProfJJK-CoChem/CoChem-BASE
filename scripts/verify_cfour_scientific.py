#!/usr/bin/env python3
"""Run real CFOUR BASE CLI, derivative and OpenMP acceptance calculations.

Reference water values originate in the privately compiled CFOUR 2.1 build's
native testsuite validation report. They establish reproducibility of this
build and bounded numerical contracts, never general experimental accuracy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np

from cochem_base.calc.calculation_service import CalculationMatrixConfig, _external_run_path, parse_run_geometry
from cochem_base.calc.cfour_execution import BOHR_ANGSTROM, OPTIMIZATION_FORCE_TOLERANCE, read_cfour_gradient
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.scientific_telemetry import read_scientific_results


ROOT = Path(__file__).resolve().parents[1]
HF_REFERENCE_ENERGY_HARTREE = -76.02361502689199
CCSD_T_REFERENCE_ENERGY_HARTREE = -75.0131049206411
HF_REFERENCE_FREQUENCIES_CM1 = [1769.6262, 4147.5734, 4264.5915]
REFERENCE_SOURCE_SHA256 = "3c596dcdb866d500d3c37e602d8e5491deea6cfad9e4595c50dfc08b4088944a"
# The supplied native reference inputs used CFOUR's rounded ANGSTROM conversion.
# Its actual MOL output proves R/|r_H-r_O| = 0.5291771, while BASE serializes
# CODATA bohr directly. Reproduce those reference *nuclear coordinates* instead
# of changing an energy tolerance to hide a geometry mismatch.
REFERENCE_ANGSTROM_CONVERSION = 0.5291771


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def water(distance: float, angle: float) -> np.ndarray:
    theta = math.radians(angle / 2)
    return np.array([[0., 0., 0.], [0., -distance * math.sin(theta), distance * math.cos(theta)],
                     [0., distance * math.sin(theta), distance * math.cos(theta)]])


def geometry(coordinates: np.ndarray) -> str:
    return "\n".join(symbol + " " + " ".join(format(float(value), ".17g") for value in row)
                     for symbol, row in zip(["O", "H", "H"], coordinates, strict=True)) + "\n"


def verify_hashes(directory: Path) -> dict[str, str]:
    inventory = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.name.endswith(".sha256"):
            digest = sha256(path)
            stamp = path.with_name(path.name + ".sha256")
            require(stamp.is_file() and stamp.read_text().split()[0] == digest,
                    f"Invalid published calculation checksum: {path}")
            inventory[str(path.relative_to(directory))] = digest
    require(bool(inventory), "No scientific calculation artifacts were published")
    return inventory


def verify_native(directory: Path, options: dict, binary_hash: str, threads: int) -> dict:
    execution, result = read_json(directory / "execution.json"), read_json(directory / "result.json")
    authority = read_json(directory / "execution_authority.json")
    require(execution["status"] == "EXECUTION_VERIFIED" and result["converged"] is True,
            "Native CFOUR calculation was not accepted")
    require(authority["binary_sha256"] == binary_hash and authority["cores"] == threads,
            "CFOUR binary/resources differ from the execution authorization")
    require(result["engine"] == "cfour" and result["method"] == options["method"], "Engine/method provenance changed")
    require(result["requested_threads"] == threads and result["parallel_model"] == "OpenMP; no MPI launcher",
            "Requested threading model was changed")
    require(result["native_evaluations"] and result["scientific_accuracy_established"] is False,
            "Native evaluation evidence is missing or overstates accuracy")
    for native in result["native_evaluations"]:
        for field in ("input_artifact", "output_artifact"):
            record = native[field]
            require(sha256(directory / record["filename"]) == record["sha256"], "Native input/output digest changed")
        require(native["electronic_convergence_verified"] is True, "Native convergence evidence is incomplete")
    elements, _ = parse_run_geometry(options["geometry"])
    require(result["elements"] == elements, "CFOUR output atoms were reordered")
    telemetry = read_scientific_results(result["telemetry_job_id"], store_path=result["telemetry_path"])
    require(telemetry["elements"] == elements and float(telemetry["energy_hartree"][-1]) == result["energy_hartree"],
            "CFOUR HDF5 identity or final energy differs from native evidence")
    if options.get("is_opt"):
        optimization = result["optimization_evidence"]
        require(optimization["converged"] and optimization["evaluations"] > 1
                and optimization["maximum_atomic_gradient_hartree_per_bohr"] <= OPTIMIZATION_FORCE_TOLERANCE,
                "The optimizer lacks measured stationary-geometry convergence")
        trajectory_record = optimization["trajectory_artifact"]
        trajectory_path = directory / trajectory_record["filename"]
        require(sha256(trajectory_path) == trajectory_record["sha256"], "Optimization trajectory digest changed")
        trajectory = json.loads(trajectory_path.read_text())
        require(len(trajectory) == optimization["evaluations"], "Actual gradient evaluations are missing from the trajectory")
        require(len(telemetry["energy_hartree"]) > 1, "Optimization trajectory telemetry is missing")
        require(result["energy_hartree"] < trajectory[0]["energy_hartree"], "The distorted water geometry was not minimized")
    if options.get("is_freq"):
        from cochem_base.spectroscopy.artifacts import load_hessian_artifact
        from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine
        hessian = result["hessian_artifact"]
        require(hessian["shape"] == [9, 9] and hessian["rigid_mode_count"] == 6,
                "Water CFOUR Hessian dimensions/rigid projection changed")
        require(hessian["native_spectrum_max_difference_cm1"] <= hessian["frequency_consistency_tolerance_cm1"],
                "Native CFOUR spectrum is inconsistent with the actual Hessian")
        require(sha256(directory / hessian["filename"]) == hessian["sha256"], "Hessian artifact changed")
        bundle_record = result["hessian_bundle_artifact"]
        bundle = load_hessian_artifact(directory / bundle_record["filename"])
        require(bundle.sha256 == bundle_record["sha256"] and list(bundle.symbols) == elements,
                "Canonical BASE harmonic bundle identity changed")
        parent = IsotopologueSpectroscopyEngine(elements, bundle.coordinates_angstrom, bundle.hessian_hartree_bohr2).compute_observables()
        require(np.allclose(parent.harmonic_frequencies_cm1, result["harmonic_frequencies_cm1"], atol=1e-8, rtol=0),
                "Published CFOUR bundle cannot reproduce its harmonic spectrum through BASE's canonical isotope interface")
    return result


def run_acceptance(registry: Path, output: Path) -> dict:
    output = _external_run_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "Select a fresh CFOUR scientific acceptance report path")
    work = Path(tempfile.mkdtemp(prefix="cfour-scientific-", dir=output.parent))
    report = {"status": "failed", "scientific_accuracy_established": False,
              "scope": "Real BASE CLI closed-shell CFOUR energies, analytic-gradient finite difference, HF optimization/harmonic Hessian, and one/two NCC OpenMP threads",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "work_directory": str(work),
              "registry_path": str(registry.resolve()), "calculations": {}, "mpi_tested": False,
              "reference_provenance": {"source_sha256": REFERENCE_SOURCE_SHA256,
                "source": "Privately compiled CFOUR 2.1 native testsuite cases 001/004, cfour-build-validation-report.json",
                "native_reference_angstrom_conversion": REFERENCE_ANGSTROM_CONVERSION,
                "coordinate_conversion": "Match the actual upstream MOL bohr geometry; BASE serialization uses CODATA bohr",
                "angstrom_reference_geometry_scale": BOHR_ANGSTROM / REFERENCE_ANGSTROM_CONVERSION}}
    started = time.monotonic()
    try:
        serial = authorize_engine_execution("cfour", registry_path=registry, cores=1, maxcore_mb=512)
        parallel = authorize_engine_execution("cfour", registry_path=registry, cores=2, maxcore_mb=512)
        require(serial.binary_sha256 == parallel.binary_sha256, "Serial/parallel CFOUR binaries differ")
        report.update(registry_sha256=sha256(registry), cfour_binary_sha256=serial.binary_sha256)
        environment = dict(os.environ, COCHEM_CONFIG=str(registry.resolve()))

        def calculate(name: str, coordinates: np.ndarray, *, method: str = "HF", basis: str = "6-31G**",
                      is_opt: bool = False, is_freq: bool = False, threads: int = 1) -> dict:
            directory = work / name
            directory.mkdir()
            options = {"geometry": geometry(coordinates), "engine": "cfour", "method": method,
                       "basis_set": basis, "is_opt": is_opt, "is_freq": is_freq, "timeout_seconds": 600,
                       "initial_hessian": "BFGS" if is_opt else "XTB2"}
            config = CalculationMatrixConfig(**options)
            config_file = directory / "matrix.json"
            config_file.write_text(config.model_dump_json(indent=2))
            command = [sys.executable, str(ROOT / "cli.py"), "run", "--config", str(config_file),
                       "--threads", str(threads), "--maxcore-mb", "512", "--scratch", str(directory / "scratch"),
                       "--output", str(directory / "published"), "--json"]
            entry = {"status": "started", "command": command, "configuration_sha256": sha256(config_file)}
            report["calculations"][name] = entry
            completed = safe_subprocess_run(command, cwd=work, env=environment, timeout=900,
                                            capture_output=True, text=True, check=False, load_full_stdout=True, required_disk_gb=0.1)
            (directory / "cli.stdout.log").write_text(completed.stdout or "")
            (directory / "cli.stderr.log").write_text(completed.stderr or "")
            entry["returncode"] = completed.returncode
            require(completed.returncode == 0, f"{name} failed; genuine diagnostics retained in {directory}")
            published = directory / "published"
            entry["artifact_sha256"] = verify_hashes(published)
            result = verify_native(published, options, serial.binary_sha256, threads)
            entry.update(status="passed", energy_hartree=result["energy_hartree"], result_sha256=sha256(published / "result.json"),
                         published_directory=str(published), operation=result["operation"])
            return result

        reference_geometry = water(.943056371100 * BOHR_ANGSTROM / REFERENCE_ANGSTROM_CONVERSION, 105.968771873000)
        fixed = calculate("water-hf-reference-energy", reference_geometry)
        require(abs(fixed["energy_hartree"] - HF_REFERENCE_ENERGY_HARTREE) <= 2e-8,
                "CFOUR HF energy differs from the native testsuite reference beyond 2e-8 Eh")
        distorted = water(1.05, 105)
        measured = calculate("water-hf-analytic-gradient", distorted)
        step_angstrom = 1e-4
        plus, minus = distorted.copy(), distorted.copy()
        plus[1, 1] += step_angstrom
        minus[1, 1] -= step_angstrom
        above = calculate("water-hf-fd-plus", plus)
        below = calculate("water-hf-fd-minus", minus)
        numerical_gradient = (above["energy_hartree"] - below["energy_hartree"]) / (2 * step_angstrom) * BOHR_ANGSTROM
        analytic_gradient = measured["gradients_hartree_per_bohr"][1][1]
        difference = abs(analytic_gradient - numerical_gradient)
        report["gradient_finite_difference"] = {"atom_index": 1, "axis": "y", "step_angstrom": step_angstrom,
            "analytic_hartree_per_bohr": analytic_gradient, "finite_difference_hartree_per_bohr": numerical_gradient,
            "absolute_difference_hartree_per_bohr": difference, "tolerance_hartree_per_bohr": 3e-6}
        require(difference <= 3e-6, "Measured CFOUR analytic gradient sign/units disagree with an actual energy finite difference")
        optimized = calculate("water-hf-optimization-and-harmonic", distorted, is_opt=True, is_freq=True)
        require(abs(optimized["energy_hartree"] - HF_REFERENCE_ENERGY_HARTREE) <= 2e-8,
                "CFOUR-backed optimization failed to reproduce the HF minimum energy")
        harmonic = calculate("water-hf-reference-harmonic", reference_geometry, is_freq=True)
        require(np.allclose(harmonic["hessian_artifact"]["native_vibrational_frequencies_cm1"],
                            HF_REFERENCE_FREQUENCIES_CM1, atol=.25, rtol=0), "Native CFOUR harmonic reference spectrum changed")
        cc_geometry = water(.96 * BOHR_ANGSTROM / REFERENCE_ANGSTROM_CONVERSION, 104.5)
        mp2 = calculate("water-mp2", cc_geometry, method="MP2", basis="STO-3G")
        ccsd = calculate("water-ccsd", cc_geometry, method="CCSD", basis="STO-3G")
        one = calculate("water-ccsd-t-omp1", cc_geometry, method="CCSD(T)", basis="STO-3G")
        two = calculate("water-ccsd-t-omp2", cc_geometry, method="CCSD(T)", basis="STO-3G", threads=2)
        require(ccsd["energy_hartree"] < mp2["energy_hartree"] and one["energy_hartree"] < ccsd["energy_hartree"],
                "Actual correlated water energies do not show the reference calculation's correlation corrections")
        require(abs(one["energy_hartree"] - CCSD_T_REFERENCE_ENERGY_HARTREE) <= 2e-8,
                "CFOUR NCC CCSD(T) energy differs from its native reference")
        delta = abs(one["energy_hartree"] - two["energy_hartree"])
        report["openmp_comparison"] = {"threads": [1, 2], "difference_hartree": delta, "tolerance_hartree": 1e-10}
        require(delta <= 1e-10, "One/two-thread NCC energies exceed the declared reproducibility tolerance")
        # Replay an actual native checkpoint against a different molecule geometry.
        # This is a rejection check, not invented derivative reference data.
        actual_gradient = work / "water-hf-analytic-gradient/published" / measured["gradient_artifact"]["filename"]
        try:
            read_cfour_gradient(actual_gradient, ["O", "H", "H"], reference_geometry)
        except ValueError:
            report["geometry_binding_rejection"] = "passed"
        else:
            raise RuntimeError("A derivative checkpoint from different nuclear geometry was accepted")
        require(sha256(registry) == report["registry_sha256"], "Golden Registry changed during acceptance")
        from cochem_base.core.cochem_core_registry_manager import AtomicFileLock
        telemetry = Path(two["telemetry_path"]).resolve(strict=True)
        telemetry_snapshot = work / "scientific-results.h5"
        with AtomicFileLock(str(telemetry) + ".lock", timeout=10.0):
            shutil.copyfile(telemetry, telemetry_snapshot)
        report["telemetry_snapshot"] = {"path": str(telemetry_snapshot), "sha256": sha256(telemetry_snapshot),
                                        "scope": "Actual HDF5 store copied after all acceptance calculations"}
        report["status"] = "passed"
        return report
    except Exception as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = run_acceptance(args.registry, args.output)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"CFOUR scientific acceptance FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.output), "work_directory": report["work_directory"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
