#!/usr/bin/env python3
"""Generate a genuine bounded H2 CBS reference and exercise BASE's R2 runner.

The reference is the minimum of HF/cc-pVQZ plus the T,Q Helgaker extrapolated
canonical CCSD(T) correlation energy. This is a declared finite-basis estimate,
not an experimental reference or certification of general spectroscopic accuracy.
Every evaluated point is calculated by the audited real ORCA executable.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import warnings

from scipy.optimize import minimize_scalar

from cochem_base.calc.calculation_service import _external_run_path
from cochem_base.calc.recipe_r2_execution import (
    CounterpoiseOrderingWarning, ResidualGradientWarning, execute_recipe_r2, validate_reference_output,
)
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.engine_environment import engine_runtime_environment
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    safe_subprocess_run, sanitize_mpi_environment,
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_r2_publication(result: dict) -> None:
    """Bind each final real energy to canonical telemetry, preserving trajectories."""
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results

    for leg, evidence in result["legs"].items():
        archived = read_scientific_results(evidence["telemetry_job_id"], store_path=evidence["telemetry_path"])
        # Optimizations stream genuine intermediate rows before the accepted
        # final result; single-point monomer/ghost legs have one final row.
        require(len(archived["energy_hartree"]) >= 1
                and float(archived["energy_hartree"][-1]) == evidence["energy_hartree"],
                f"Published R2 {leg} final energy differs from the real ORCA result")
        expected_atoms = len(result["elements"]) if leg == "dimer" else len(
            result["reference_evidence"]["monomers"][0 if leg.endswith("a") else 1]["atom_indices"]
        )
        require(len(archived["elements"]) == expected_atoms,
                f"R2 {leg} publication must contain only real nuclei, excluding ghost basis functions")


def generate_reference(registry: Path, directory: Path, *, timeout: float = 600) -> dict:
    """Perform scalar optimization, then independent finite-difference checks."""
    directory = _external_run_path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    authority = authorize_engine_execution("orca", registry_path=registry, cores=1, maxcore_mb=1000)
    environment = sanitize_mpi_environment(
        engine_runtime_environment("orca", executable=authority.executable), force_single_thread=True,
    )
    started = time.monotonic()
    deadline = started + timeout
    records = []

    def evaluate(distance: float) -> dict:
        require(math.isfinite(distance) and 0.65 < distance < 0.85, "H2 reference outside bounded domain")
        point = directory / f"point-{len(records):03d}"
        point.mkdir()
        result = {"distance_angstrom": float(distance), "basis_results": {}}
        for basis in ("cc-pVTZ", "cc-pVQZ"):
            work = point / basis
            work.mkdir()
            deck = work / "h2.inp"
            deck.write_text(
                f"! CCSD(T) {basis} VeryTightSCF\n%pal nprocs 1 end\n%maxcore 1000\n"
                "%scf TolE 1e-11 MaxIter 200 end\n"
                "%mdci STol 1e-9 MaxIter 100 end\n"
                f"* xyz 0 1\nH 0 0 {-distance / 2:.15f}\nH 0 0 {distance / 2:.15f}\n*\n",
                encoding="utf-8",
            )
            remaining = deadline - time.monotonic()
            require(remaining > 0, "Reference generation time budget expired")
            completed = safe_subprocess_run(
                authority.command([deck.name]), cwd=work, env=environment,
                timeout=remaining, capture_output=True, text=True, check=False,
                load_full_stdout=True, required_disk_gb=0.1,
                cpu_affinity=list(authority.cpu_affinity) or None,
            )
            output = work / "h2.out"
            output.write_text(completed.stdout or "", encoding="utf-8")
            (work / "stderr.log").write_text(completed.stderr or "", encoding="utf-8")
            require(completed.returncode == 0, f"Reference calculation failed: {work}")
            evidence = validate_reference_output(output, basis)
            result["basis_results"][basis] = {
                **evidence, "input_path": str(deck), "input_sha256": sha256(deck),
                "output_path": str(output), "output_sha256": sha256(output),
            }
        lower, upper = (result["basis_results"][basis] for basis in ("cc-pVTZ", "cc-pVQZ"))
        result["cbs_energy_hartree"] = upper["scf_energy_hartree"] + (
            4 ** 3 * upper["correlation_energy_hartree"]
            - 3 ** 3 * lower["correlation_energy_hartree"]
        ) / (4 ** 3 - 3 ** 3)
        records.append(result)
        write_json(point / "evaluation.json", result)
        print(f"H2 CBS point {len(records)}: r={distance:.9f} A E={result['cbs_energy_hartree']:.12f} Eh", flush=True)
        return result

    minimum = minimize_scalar(
        lambda r: evaluate(float(r))["cbs_energy_hartree"], bounds=(0.70, 0.79),
        method="bounded", options={"xatol": 2e-6, "maxiter": 18},
    )
    require(bool(minimum.success), "CBS scalar minimization did not converge")
    # Round to a precision that ORCA's six-decimal geometry block can bind.
    distance = round(float(minimum.x), 6)
    central = evaluate(distance)
    differences = []
    for step in (0.002, 0.001):
        low, high = evaluate(distance - step), evaluate(distance + step)
        derivative = (high["cbs_energy_hartree"] - low["cbs_energy_hartree"]) / (2 * step)
        curvature = (high["cbs_energy_hartree"] - 2 * central["cbs_energy_hartree"]
                     + low["cbs_energy_hartree"]) / step ** 2
        require(low["cbs_energy_hartree"] > central["cbs_energy_hartree"]
                and high["cbs_energy_hartree"] > central["cbs_energy_hartree"], "Reference minimum not bracketed")
        require(curvature > 0 and abs(derivative) < 2e-5, "Reference stationarity or positive curvature check failed")
        differences.append({"step_angstrom": step, "derivative_hartree_per_angstrom": derivative,
                            "curvature_hartree_per_angstrom2": curvature})
    require(abs(differences[0]["curvature_hartree_per_angstrom2"] /
                differences[1]["curvature_hartree_per_angstrom2"] - 1) < 0.005,
            "Finite-difference reference curvature failed step-size consistency")
    geometry = directory / "h2.xyz"
    geometry.write_text(f"2\nH2 minimum: HF(QZ)+Helgaker CCSD(T) correlation(T,Q); finite-basis estimate\n"
                        f"H 0 0 {-distance / 2:.12f}\nH 0 0 {distance / 2:.12f}\n", encoding="utf-8")
    reference = {
        "schema_version": "cochem.bounded-cbs-reference/1", "status": "passed",
        "geometry_protocol": "1D minimum of HF/cc-pVQZ + [64 Ecorr(CCSD(T)/QZ) - 27 Ecorr(CCSD(T)/TZ)]/37",
        "limitations": "Finite-basis CBS estimate for two-electron H2, not a general or experimental accuracy certificate",
        "independent_scientific_accuracy_established": False,
        "registry_path": str(registry.resolve()), "registry_sha256": sha256(registry),
        "binary_path": authority.executable, "binary_sha256": authority.binary_sha256,
        "cores": 1, "optimizer_bounds_angstrom": [0.70, 0.79],
        "optimizer_x_tolerance_angstrom": 2e-6, "optimizer_success": bool(minimum.success),
        "distance_angstrom": distance, "minimum": central,
        "finite_difference_checks": differences, "evaluations": records,
        "geometry_path": str(geometry), "geometry_sha256": sha256(geometry),
        "elapsed_seconds": time.monotonic() - started,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(directory / "reference-generation.json", reference)
    monomers = []
    for indices in ([0, 1], [2, 3]):
        monomers.append({
            "atom_indices": indices, "charge": 0, "multiplicity": 1,
            "method": "CCSD(T)/CBS", "basis_cardinal_pair": [3, 4], "basis_family": "cc-pVXZ",
            "source_uri": "urn:sha256:" + sha256(directory / "reference-generation.json"),
            "geometry_optimization_evidence": {"path": str(directory / "reference-generation.json"),
                                                "sha256": sha256(directory / "reference-generation.json")},
            "geometry": {"path": str(geometry), "sha256": sha256(geometry)},
            **{name: {"path": central["basis_results"][basis]["output_path"],
                       "sha256": central["basis_results"][basis]["output_sha256"]}
               for name, basis in (("lower_cardinal_output", "cc-pVTZ"), ("upper_cardinal_output", "cc-pVQZ"))},
        })
    manifest = directory / "r2-reference-manifest.json"
    write_json(manifest, {"schema_version": "cochem.r2-reference/1", "monomers": monomers})
    separation = 3.4
    dimer = directory / "h2-dimer.xyz"
    dimer.write_text(
        f"4\nT-shaped H2 dimer input; fixed generated reference bond\n"
        f"H 0 0 {-distance / 2:.12f}\nH 0 0 {distance / 2:.12f}\n"
        f"H {-distance / 2:.12f} 0 {separation}\nH {distance / 2:.12f} 0 {separation}\n",
        encoding="utf-8",
    )
    return {"reference_report": str(directory / "reference-generation.json"),
            "reference_manifest": str(manifest), "dimer_xyz": str(dimer)}


def run_acceptance(registry: Path, output: Path, *, reference_timeout: float = 600,
                   r2_timeout: float = 1800, reference_manifest: Path | None = None,
                   dimer_xyz: Path | None = None) -> dict:
    output = _external_run_path(output)
    require(not output.exists(), "Acceptance evidence already exists; use a fresh output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.stem + "-work")
    work.mkdir(exist_ok=False)
    report = {"status": "failed", "scope": "bounded real canonical-reference and five-leg R2 execution",
              "scientific_accuracy_established": False, "work_directory": str(work)}
    started = time.monotonic()
    try:
        require((reference_manifest is None) == (dimer_xyz is None),
                "Reference manifest and dimer XYZ must be supplied together")
        if reference_manifest is None:
            report["reference"] = generate_reference(registry, work / "reference", timeout=reference_timeout)
        else:
            report["reference"] = {
                "reference_manifest": str(reference_manifest.resolve(strict=True)),
                "dimer_xyz": str(dimer_xyz.resolve(strict=True)),
                "generation_repeated": False,
                "scope": "Supplied references are independently validated by BASE before execution",
            }
        from cochem_base.calc.calculation_service import parse_run_geometry
        report["dimer_input_sha256"] = sha256(Path(report["reference"]["dimer_xyz"]))
        symbols, xyz = parse_run_geometry(Path(report["reference"]["dimer_xyz"]).read_text())
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always", ResidualGradientWarning)
            warnings.simplefilter("always", CounterpoiseOrderingWarning)
            result = execute_recipe_r2(
                symbols, xyz, report["reference"]["reference_manifest"],
                work_dir=work / "r2", registry_path=registry, cores=1, maxcore_mb=1000,
                timeout_seconds=r2_timeout,
            )
        warning_observed = any(issubclass(item.category, ResidualGradientWarning) for item in observed)
        cp_warning_observed = any(issubclass(item.category, CounterpoiseOrderingWarning) for item in observed)
        require(cp_warning_observed == result["counterpoise_ordering_warning"]
                == (not result["counterpoise"]["variational_order_consistent"]),
                "Approximate counterpoise ordering must be reported without hiding its sign")
        expected_warning = result["residual_gradient_norm_hartree_per_bohr"] > result["residual_gradient_threshold"]
        require(result["residual_gradient_warning"] == expected_warning == warning_observed,
                "Frozen-coordinate strain must be reported consistently with the measured projected gradient")
        require(set(result["legs"]) == {"dimer", "monomer_a", "monomer_b", "ghost_a", "ghost_b"},
                "R2 lacks all five real calculation legs")
        require(result["frozen_monomer_integrity"]["maximum_internal_drift_angstrom"] < 1e-6,
                "Frozen-monomer physical integrity failed")
        require(sha256(Path(result["reference_evidence"]["manifest"])) ==
                result["reference_evidence"]["manifest_sha256"], "Reference changed during R2 execution")
        validate_r2_publication(result)
        report.update(status="passed", r2=result, residual_warning_observed=warning_observed,
                      counterpoise_ordering_warning_observed=cp_warning_observed)
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
    parser.add_argument("--reference-timeout", type=float, default=600)
    parser.add_argument("--r2-timeout", type=float, default=1800)
    parser.add_argument("--reference-manifest", type=Path)
    parser.add_argument("--dimer-xyz", type=Path)
    args = parser.parse_args()
    try:
        report = run_acceptance(args.registry, args.output, reference_timeout=args.reference_timeout,
                                r2_timeout=args.r2_timeout, reference_manifest=args.reference_manifest,
                                dimer_xyz=args.dimer_xyz)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"R2 acceptance FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
