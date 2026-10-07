#!/usr/bin/env python3
"""Measure BASE PES interpolation using a predeclared genuine H2 quantum scan.

This bounded energy-fitting benchmark is not a vibrational-frequency prediction,
experimental comparison, dissociation-limit claim or universal accuracy promise.
Training and held-out geometries and the unchanged default fitting configuration
are recorded before calculations. No held-out label selects model parameters.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time

import numpy as np

from cochem_base.calc.calculation_service import _external_run_path
from cochem_base.calc.cochem_calc_output_parser import QuantumParser
from cochem_base.calc.recipe_r2_execution import validate_reference_output
from cochem_base.core_engine.cochem_core_auto_pes import (
    AutoPESOrchestrator, DeltaFittingConfig, HARTREE_TO_CM1,
)
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    safe_subprocess_run, sanitize_mpi_environment,
)
from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.core_engine.execution_authority import authorize_engine_execution


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(registry: Path, output: Path, *, timeout: float = 600) -> dict:
    output = _external_run_path(output)
    if output.exists():
        raise FileExistsError("Previous PES evidence cannot be overwritten")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("A finite positive calculation budget is required")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.stem + "-work")
    work.mkdir(exist_ok=False)
    # Thirty-two evenly spaced training geometries cover compressed through
    # substantially stretched H2. The thirty-one midpoints are never fitted.
    train_distances = np.linspace(0.55, 1.80, 32)
    held_distances = (train_distances[:-1] + train_distances[1:]) / 2
    fitting = DeltaFittingConfig()
    protocol = {
        "schema_version": "cochem.quantum-pes-protocol/1",
        "declared_utc": datetime.now(timezone.utc).isoformat(),
        "generator_sha256": digest(Path(__file__)), "symbols": ["H", "H"],
        "charge": 0, "multiplicity": 1, "bond_domain_angstrom": [0.55, 1.80],
        "train_distances_angstrom": train_distances.tolist(),
        "held_out_distances_angstrom": held_distances.tolist(),
        "lower_method": "ORCA RHF/STO-3G", "higher_method": "ORCA canonical CCSD(T)/cc-pVTZ",
        "scf_solver": "DIIS with NoTRAH/NoSOSCF so an initially stationary H2 guess still reports an actual successive-energy difference",
        "fitting_configuration": fitting.model_dump(mode="json"),
        "hyperparameter_selection": "Unchanged BASE defaults; median kernel lengthscale and offsets use training data only",
        "test_definition": "Both paired and standalone held-out energy RMSE and maximum absolute error <= 10 cm^-1",
        "limitations": "H2 two-electron one-dimensional interpolation; no nonzero triples, frequency, experiment, extrapolation or general molecular accuracy certification",
    }
    protocol_path = work / "predeclared-protocol.json"
    write_json(protocol_path, protocol)
    protocol_hash = digest(protocol_path)
    started = time.monotonic()
    report = {"status": "failed", "scientific_accuracy_established": False,
              "scope": protocol["limitations"], "protocol": protocol,
              "protocol_sha256": protocol_hash, "work_directory": str(work), "calculations": []}
    try:
        authority = authorize_engine_execution("orca", registry_path=registry, cores=1, maxcore_mb=1000)
        report.update(registry_path=str(registry.resolve()), registry_sha256=digest(registry),
                      binary_path=authority.executable, binary_sha256=authority.binary_sha256)
        environment = sanitize_mpi_environment(
            engine_runtime_environment("orca", executable=authority.executable), force_single_thread=True,
        )
        data = {}
        for label, distances in (("train", train_distances), ("held_out", held_distances)):
            geometries, low, high = [], [], []
            for index, distance in enumerate(distances):
                coordinates = [[0., 0., -float(distance) / 2], [0., 0., float(distance) / 2]]
                geometries.append(coordinates)
                point = {"partition": label, "index": index, "distance_angstrom": float(distance), "methods": {}}
                for method, keywords in (("low", "HF STO-3G"), ("high", "CCSD(T) cc-pVTZ")):
                    directory = work / label / f"point-{index:03d}" / method
                    directory.mkdir(parents=True)
                    deck = directory / "h2.inp"
                    deck.write_text(
                        f"! {keywords} VeryTightSCF NoTRAH NoSOSCF\n%pal nprocs 1 end\n%maxcore 1000\n"
                        "%scf TolE 1e-11 ConvCheckMode 0 ConvForced true MaxIter 200 end\n"
                        + ("%mdci STol 1e-9 MaxIter 100 end\n" if method == "high" else "")
                        + f"* xyz 0 1\nH 0 0 {-distance / 2:.15f}\nH 0 0 {distance / 2:.15f}\n*\n",
                        encoding="utf-8",
                    )
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError("Bounded quantum PES calculation budget expired")
                    completed = safe_subprocess_run(
                        authority.command([deck.name]), cwd=directory, env=environment,
                        timeout=remaining, capture_output=True, text=True, check=False,
                        load_full_stdout=True, required_disk_gb=0.1,
                        cpu_affinity=list(authority.cpu_affinity) or None,
                    )
                    log = directory / "h2.out"
                    log.write_text(completed.stdout or "", encoding="utf-8")
                    (directory / "stderr.log").write_text(completed.stderr or "", encoding="utf-8")
                    if completed.returncode:
                        raise RuntimeError(f"Real quantum scan calculation failed: {directory}")
                    parser = QuantumParser(str(directory))
                    parser.scf_threshold = 1e-8
                    if not parser.verify_scf_convergence(log):
                        raise RuntimeError(f"Quantum scan lacks accepted SCF convergence: {directory}")
                    if method == "high":
                        energy = validate_reference_output(log, "cc-pVTZ")["ccsdt_energy_hartree"]
                    else:
                        values = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-+]?\d+\.\d+(?:[EeDd][-+]?\d+)?)", completed.stdout or "")
                        if len(values) != 1:
                            raise RuntimeError("Expected one actual RHF single-point energy")
                        energy = float(values[0].replace("D", "E"))
                    if not math.isfinite(energy):
                        raise RuntimeError("Nonfinite quantum energy cannot enter PES fitting")
                    (low if method == "low" else high).append(energy)
                    point["methods"][method] = {
                        "energy_hartree": energy, "input_path": str(deck), "input_sha256": digest(deck),
                        "output_path": str(log), "output_sha256": digest(log), "scf_converged": True,
                    }
                report["calculations"].append(point)
                write_json(work / label / f"point-{index:03d}" / "evidence.json", point)
                print(f"{label} point {index + 1}/{len(distances)} completed at {distance:.6f} angstrom", flush=True)
            data[label] = (np.asarray(geometries), np.asarray(low), np.asarray(high))
        if digest(protocol_path) != protocol_hash:
            raise RuntimeError("Predeclared PES protocol changed during calculation")
        model, summary = AutoPESOrchestrator(
            symbols=["H", "H"], low_method=protocol["lower_method"], high_method=protocol["higher_method"],
            fit_config=fitting,
        ).fit_delta_surface_from_data(
            train_geoms=data["train"][0], train_low_energies=data["train"][1], train_high_energies=data["train"][2],
            held_out_geoms=data["held_out"][0], held_out_low_energies=data["held_out"][1], held_out_high_energies=data["held_out"][2],
        )
        paired = model.predict_total_energy(data["held_out"][0], v_low_eval=data["held_out"][1])
        standalone = model.predict_total_energy(data["held_out"][0], allow_unvalidated_baseline=True)
        metrics = {}
        for name, prediction in (("paired_correction", paired), ("standalone_prediction", standalone)):
            error = (prediction - data["held_out"][2]) * HARTREE_TO_CM1
            metrics[name] = {"rmse_cm1": float(np.sqrt(np.mean(error ** 2))),
                             "maximum_absolute_error_cm1": float(np.max(np.abs(error))),
                             "signed_errors_cm1": error.tolist(), "predicted_energies_hartree": prediction.tolist()}
        met = all(item["rmse_cm1"] <= 10 and item["maximum_absolute_error_cm1"] <= 10 for item in metrics.values())
        report.update(status="passed" if met else "measured_threshold_not_met", metrics=metrics,
                      bounded_10_cm1_target_met=met, fit_summary=summary.model_dump(mode="json"),
                      baseline_training_count=int(model.low_level_estimator.X_train.shape[0]),
                      correction_training_count=int(model.krr_estimator.X_train.shape[0]))
        return report
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        write_json(output, report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    try:
        report = run(args.registry, args.output, timeout=args.timeout)
    except Exception as error:
        print(f"Quantum PES acceptance failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "metrics": report["metrics"]}, indent=2))
    return 0 if report["bounded_10_cm1_target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
