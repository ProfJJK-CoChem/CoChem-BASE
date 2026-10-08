#!/usr/bin/env python3
"""Run bounded real ORCA R1, DFT-grid and PySCF spin-recovery acceptance.

Every calculation uses the canonical BASE CLI and an audited host registry.
These small molecules verify numerical execution and publication contracts;
they do not establish experimental accuracy or a general active-space policy.
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

from cochem_base.calc.calculation_service import (
    CalculationMatrixConfig, _external_run_path, parse_run_geometry,
    validate_frozen_monomer_trajectory,
)
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.scientific_telemetry import read_scientific_results


ROOT = Path(__file__).resolve().parents[1]
WATER = "O 0 0 0\nH 0 -0.757 0.587\nH 0 0.757 0.587\n"
DIMER = "O 0 0 0\nH 0 0.757 0.586\nH 0 -0.757 0.586\nO 0 0 2.95\nH 0.757 0 3.536\nH -0.757 0 3.536\n"
STRETCHED_H3 = "H 0 0 -2\nH 0 0 0\nH 0 0 2.1\n"
GRID_TOLERANCE_HARTREE = 1e-5


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def cases(pyscf_python: Path, pyscf_version: str) -> list[tuple[str, dict]]:
    jobs = [("r1-water-dimer", {
        "geometry": DIMER, "engine": "orca", "method": "r2SCAN-3c", "basis_set": None,
        "recipe": "R1", "is_opt": True, "grid_stage": 1, "timeout_seconds": 900,
    })]
    for method in ("B3LYP-D4", "wB97M-V"):
        for grid in (1, 2, 3):
            jobs.append((f"{method.lower()}-grid{grid}", {
                "geometry": WATER, "engine": "orca", "method": method,
                "basis_set": "def2-SVP", "is_opt": False, "grid_stage": grid, "timeout_seconds": 180,
            }))
    jobs.append(("h3-uhf-nevpt2", {
        "geometry": STRETCHED_H3, "engine": "orca", "method": "UHF", "basis_set": "6-31G",
        "is_opt": False, "multiplicity": 2, "timeout_seconds": 180,
        "t9_fallback": {
            "python_executable": str(pyscf_python), "pyscf_version": pyscf_version,
            "method": "NEVPT2", "basis": "6-31g", "active_electrons": 3,
            "active_orbitals": [0, 1, 2],
            "active_space_rationale": (
                "Neutral stretched H3 doublet: three electrons and the three lowest "
                "converged ROHF orbitals as the explicit starting valence CAS(3,3); "
                "CASSCF optimizes the orbitals. This choice is specific to this acceptance molecule."
            ),
            "threads": 1, "memory_mb": 1024, "timeout_seconds": 180,
        },
    }))
    return jobs


def verify_hashes(directory: Path) -> dict[str, str]:
    inventory = {}
    for artifact in sorted(directory.rglob("*")):
        if artifact.is_file() and not artifact.name.endswith(".sha256"):
            stamp = artifact.with_name(artifact.name + ".sha256")
            digest = sha256(artifact)
            require(stamp.is_file() and stamp.read_text().split()[0] == digest,
                    f"Invalid published artifact checksum: {artifact}")
            inventory[str(artifact.relative_to(directory))] = digest
    require(bool(inventory), "No published artifacts")
    return inventory


def verify_telemetry(result: dict, elements: list[str], *, optimization: bool = False) -> None:
    telemetry = read_scientific_results(result["telemetry_job_id"], store_path=result["telemetry_path"])
    count = len(telemetry["energy_hartree"])
    require(telemetry["elements"] == elements and (count > 1 if optimization else count == 1),
            "HDF5 molecule or trajectory length differs from the submitted operation")
    require(float(telemetry["energy_hartree"][-1]) == result["energy_hartree"],
            "HDF5 energy differs from accepted native evidence")


def verify_grid_lifecycle(directory: Path, config: dict, result: dict) -> dict:
    """Verify every actual stage and its native derivatives/restart provenance."""
    from cochem_base.calc.cochem_calc_input_generator import build_internal_coordinate_constraints
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser
    from cochem_base.calc.grid_execution import _native_constraint_state, _promotion_evidence
    from cochem_base.calc.orca_derivatives import accept_gradient

    lifecycle = read_json(directory / "grid_lifecycle.json")
    require(lifecycle["status"] == "EXECUTION_VERIFIED" and lifecycle["method_unchanged"] is True,
            "Quadrature lifecycle did not complete unchanged")
    initial = config["grid_stage"]
    expected = list(range(initial, 4)) if config["is_opt"] and config.get("recipe") == "R1" else [initial]
    require(lifecycle["stages"] == expected and lifecycle["grids"] == [f"DEFGRID{s}" for s in expected]
            and lifecycle["dynamic"] is (len(expected) > 1), "Actual grid progression differs from the requested operation")
    require(result["grid_lifecycle"]["completed_stages"] == lifecycle["completed_stages"]
            and result["grid_lifecycle"]["final_grid"] == f"DEFGRID{expected[-1]}", "Result lost its measured grid provenance")
    completed = lifecycle["completed_stages"]
    require(len(completed) == len(expected), "One or more native refinement stages are missing")
    elements, original = parse_run_geometry(config["geometry"])
    constraints = build_internal_coordinate_constraints(elements, original, list(range(len(elements)))) if config.get("recipe") else []
    original_state, previous_wavefunction = None, None
    checks = []
    for index, (stage, record) in enumerate(zip(expected, completed, strict=True)):
        native = directory / record["directory"]
        require(native.resolve().is_relative_to(directory.resolve()), "Native grid evidence escaped publication")
        decks, logs, waves = list(native.glob("*_job.inp")), list(native.glob("*_job.out")), list(native.glob("*_job.gbw"))
        require(len(decks) == len(logs) == len(waves) == 1, "Grid stage lacks unique actual input/output/wavefunction")
        require(record["grid"] == f"DEFGRID{stage}" and record["converged"] is True
                and record["input_sha256"] == sha256(decks[0]) and record["log_sha256"] == sha256(logs[0])
                and record["wavefunction_sha256"] == sha256(waves[0]), "Grid stage native artifact provenance differs")
        keywords = next(line.split() for line in decks[0].read_text().splitlines() if line.startswith("!"))
        require([token for token in keywords if token.startswith("DEFGRID")] == [f"DEFGRID{stage}"],
                "A refinement stage executed a different native grid")
        parser = QuantumParser(str(native))
        require(parser.verify_scf_convergence(logs[0]), "A refinement stage lacks independently accepted native SCF evidence")
        energies = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-+\d.EeDd]+)", logs[0].read_text())
        require(bool(energies) and float(energies[-1].replace("D", "E").replace("d", "e")) == record["energy_hartree"],
                "Grid energy differs from its actual native output")
        if config["is_opt"]:
            convergence = parser.verify_geometry_convergence(logs[0])
            require(convergence == record["native_quintuple_convergence"], "Refinement convergence table provenance differs")
            stage_result = read_json(native / "stage_result.json")
            derivative = accept_gradient(native / stage_result["gradient_artifact"]["filename"], elements,
                                         stage_result["coordinates_angstrom"], stage_result["energy_hartree"], required=True)
            require(derivative["gradients_hartree_per_bohr"] == stage_result["gradients_hartree_per_bohr"],
                    "Stage gradients differ from its actual geometry-bound native checkpoint")
            if constraints:
                state = _native_constraint_state(decks[0], constraints, read_json(native / "stage_handoff.json")["geometry"]["coordinates_angstrom"])
                if original_state is None:
                    original_state = state
                state["original_input_sha256"] = original_state["original_input_sha256"]
                projected = stage_result["constraint_gradient_artifact"]
                require(sha256(directory / projected["filename"]) == projected["sha256"], "Derived Wilson gradient artifact changed")
                decomposition = read_json(directory / projected["filename"])
                require(decomposition["gradient_checkpoint_sha256"] == derivative["gradient_artifact"]["sha256"]
                        and decomposition["raw_gradients_hartree_per_bohr"] == derivative["gradients_hartree_per_bohr"]
                        and decomposition["original_input_sha256"] == original_state["original_input_sha256"],
                        "Wilson decomposition lost its original input or actual raw gradient provenance")
            else:
                state = None
            if stage < expected[-1]:
                trajectory = list(native.glob("*_job_trj.xyz"))
                require(len(trajectory) == 1, "Stage lacks its actual optimizer trajectory")
                # Actual XYZ frames supply displacement; they never stand in for derivatives.
                lines = trajectory[0].read_text().splitlines()
                frames = [parse_run_geometry("\n".join(lines[i:i + len(elements) + 2]))[1]
                          for i in range(0, len(lines), len(elements) + 2)]
                promotion = _promotion_evidence(stage, stage_result,
                    [{"coordinates_angstrom": frame} for frame in frames], convergence, constraint_state=state)
                require(promotion["next_grid"] == record["promotion"]["next_grid"] and record["promotion"]["accepted"] is True,
                        "Refinement lacks measured promotion through the unchanged scientific gate")
                require(promotion["measured_max_gradient_hartree_per_bohr"] == record["promotion"]["measured_max_gradient_hartree_per_bohr"],
                        "Promotion gradient differs from the accepted actual checkpoint")
        handoff = read_json(native / "stage_handoff.json")
        if index:
            wave = handoff["wavefunction"]
            require(wave["source_sha256"] == previous_wavefunction and wave["native_readback_verified"] is True
                    and wave["after_execution_sha256"] == sha256(native / "previous-stage.gbw"), "Native wavefunction handoff changed")
        previous_wavefunction = sha256(waves[0])
        checks.append({"grid": record["grid"], "energy_hartree": record["energy_hartree"],
                       "input_sha256": record["input_sha256"], "output_sha256": record["log_sha256"],
                       "gradient_evaluations": record["gradient_evaluations"], "promotion": record.get("promotion")})
    return {"grids": lifecycle["grids"], "final_grid": lifecycle["grids"][-1], "stages": checks}


def verify_native(directory: Path, config: dict, binary_hash: str) -> dict:
    execution, result = read_json(directory / "execution.json"), read_json(directory / "result.json")
    authority = read_json(directory / "execution_authority.json")
    require(execution["status"] == "EXECUTION_VERIFIED" and result["converged"] is True,
            "Native calculation was not accepted")
    require(result["method"] == config["method"] and result["engine"] == "orca", "Method provenance changed")
    require(authority["binary_sha256"] == binary_hash and authority["cores"] == 1 and authority["maxcore_mb"] == 1024,
            "Native execution authority differs from requested binary/resources")
    lifecycle = verify_grid_lifecycle(directory, config, result)
    decks, logs, schemas = list(directory.glob("*_job.inp")), list(directory.glob("*_job.out")), list(directory.glob("*_qcschema.json"))
    require(len(decks) == len(logs) == len(schemas) == 1, "Missing unique ORCA input/output/QCSchema")
    deck, log = decks[0].read_text(), logs[0].read_text(errors="replace")
    keywords = next(line.split() for line in deck.splitlines() if line.startswith("!"))
    require([word for word in keywords if word.startswith("DEFGRID")] == [lifecycle["final_grid"]],
            "Actual native deck used a different quadrature grid")
    if config["method"] == "B3LYP-D4":
        require("B3LYP" in keywords and "D4" in keywords and "B3LYP-D4" not in keywords,
                "B3LYP-D4 was not rendered as native ORCA functional/correction keywords")
    elif config["method"] == "wB97M-V":
        require("wB97M-V" in keywords and not {"D3", "D3BJ", "D4"}.intersection(keywords),
                "Native VV10 functional was modified or given redundant dispersion")
    require(set(re.findall(r"Program Version\s+(\d+\.\d+\.\d+)", log)) == {"6.1.1"},
            "Actual calculation did not report ORCA 6.1.1")
    require(log.count("ORCA TERMINATED NORMALLY") == 1, "ORCA did not terminate normally once")
    require(bool(re.search(r"ConvCheckMode\s+\.+\s+All-Criteria", log))
            and bool(re.search(r"ConvForced\s+\.+\s+1\b", log)), "Native SCF did not use all-criteria convergence")
    cycles = re.findall(r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES", log)
    require(bool(cycles), "No genuine SCF convergence evidence")
    energies = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-+\d.EeDd]+)", log)
    require(bool(energies), "No native final energy")
    energy = float(energies[-1].replace("D", "E").replace("d", "e"))
    schema = read_json(schemas[0])
    require(math.isfinite(energy) and energy == result["energy_hartree"] == schema["properties"]["return_energy"],
            "ORCA, published result and QCSchema energies disagree")
    require(schema["provenance"]["log_sha256"] == sha256(logs[0]), "QCSchema output hash mismatch")
    elements, coordinates = parse_run_geometry(config["geometry"])
    require(elements == result["elements"], "Published atomic identities/order changed")
    verify_telemetry(result, elements, optimization=config["is_opt"])
    evidence = {"energy_hartree": energy, "scf_cycles": [int(value) for value in cycles],
                "input_sha256": sha256(decks[0]), "output_sha256": sha256(logs[0]),
                "grid_lifecycle": lifecycle,
                "telemetry_path": result["telemetry_path"], "telemetry_job_id": result["telemetry_job_id"]}
    if config.get("recipe") == "R1":
        require("THE OPTIMIZATION HAS CONVERGED" in log, "R1 lacks actual optimization convergence")
        trajectories = list(directory.glob("*_job_trj.xyz"))
        require(len(trajectories) == 1, "R1 lacks a unique real trajectory")
        drift = validate_frozen_monomer_trajectory(trajectories[0], elements, coordinates, result["coordinates_angstrom"])
        require(drift["frame_count"] > 1, "R1 did not produce multiple optimization frames")
        final = result["coordinates_angstrom"]
        initial_distance, final_distance = math.dist(coordinates[0], coordinates[3]), math.dist(final[0], final[3])
        require(abs(final_distance - initial_distance) > 1e-4, "R1 froze intermolecular translation")
        evidence.update(frozen_monomer_integrity=drift, initial_oo_distance_angstrom=initial_distance,
                        final_oo_distance_angstrom=final_distance)
    return evidence


def verify_t9(directory: Path, binary_hash: str, pyscf_hash: str) -> dict:
    execution = read_json(directory / "execution.json")
    require(execution["status"] == "T9_FALLBACK_VERIFIED" and execution["original_single_reference_rejected"] is True,
            "The contaminated primary was not rejected and replaced by verified recovery")
    authority = read_json(directory / "execution_authority.json")
    require(authority["binary_sha256"] == binary_hash and authority["cores"] == 1 and authority["maxcore_mb"] == 1024,
            "Primary binary/allocation mismatch")
    log = (directory / "process_stdout.log").read_text(errors="replace")
    require(set(re.findall(r"Program Version\s+(\d+\.\d+\.\d+)", log)) == {"6.1.1"}, "Missing real ORCA identity")
    measured = re.findall(r"Expectation value of <S\*\*2>\s*:\s*([-+\d.EeDd]+)", log)
    require(bool(measured), "Recovery lacks genuine primary spin telemetry")
    observed = float(measured[-1].replace("D", "E"))
    rejected = read_json(directory / "t9/rejected_single_reference.json")
    require(rejected["status"] == "REJECTED" and rejected["details"]["s2_observed"] == observed,
            "T9 trigger does not match native spin evidence")
    require(abs(observed - 0.75) / 0.75 >= 0.1, "Primary was not actually contaminated")
    recovery = read_json(directory / "t9/t9_verified.json")
    require(recovery["scf_converged"] is True and recovery["casscf_converged"] is True, "Recovery did not converge")
    require(recovery["active_electrons"] == 3 and recovery["active_orbitals"] == [0, 1, 2], "CAS changed")
    require(recovery["method"] == "NEVPT2" and recovery["nevpt2_correction_hartree"] < 0, "Missing genuine NEVPT2 correction")
    require(abs(recovery["spin_square"] - 0.75) < 1e-6, "Recovery did not restore the requested doublet spin")
    require(recovery["input_sha256"] == sha256(directory / "t9/t9_input.json"), "T9 input provenance mismatch")
    require(read_json(directory / "t9/execution_authority.json")["binary_sha256"] == pyscf_hash, "PySCF interpreter mismatch")
    verify_telemetry(recovery, ["H", "H", "H"])
    return {"primary_spin_square": observed, "primary_rejected": True,
            "primary_output_sha256": sha256(directory / "process_stdout.log"), "recovery": recovery}


def run_acceptance(registry: Path, output: Path, pyscf_python: Path, pyscf_version: str = "2.14.0") -> dict:
    output = _external_run_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "Select a fresh scientific acceptance report path")
    work = Path(tempfile.mkdtemp(prefix="orca-scientific-", dir=output.parent))
    started = time.monotonic()
    report = {"status": "failed", "scientific_accuracy_established": False,
              "scope": "Actual frozen R1 optimization, DFT quadrature refinement and explicit CAS(3,3)/NEVPT2 recovery",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "work_directory": str(work),
              "registry_path": str(registry.resolve()), "calculations": {}}
    try:
        orca = authorize_engine_execution("orca", registry_path=registry, cores=1, maxcore_mb=1024)
        pyscf = authorize_engine_execution("pyscf", registry_path=registry, executable=str(pyscf_python), cores=1, maxcore_mb=1024)
        report.update(registry_sha256=sha256(registry), orca_binary_sha256=orca.binary_sha256,
                      pyscf_interpreter_sha256=pyscf.binary_sha256)
        environment = dict(os.environ, COCHEM_CONFIG=str(registry.resolve()))
        for name, options in cases(pyscf_python, pyscf_version):
            directory = work / name
            directory.mkdir()
            config = CalculationMatrixConfig(**options)
            config_file = directory / "matrix.json"
            config_file.write_text(config.model_dump_json(indent=2))
            command = [sys.executable, str(ROOT / "cli.py"), "run", "--config", str(config_file),
                       "--threads", "1", "--maxcore-mb", "1024", "--device", "cpu", "--scratch", str(directory / "scratch"),
                       "--output", str(directory / "published"), "--json"]
            entry = {"status": "started", "command": command, "config_sha256": sha256(config_file), "directory": str(directory)}
            report["calculations"][name] = entry
            completed = safe_subprocess_run(command, cwd=work, env=environment, timeout=options["timeout_seconds"] + 300,
                                            capture_output=True, text=True, check=False, load_full_stdout=True, required_disk_gb=0.1)
            (directory / "cli.stdout.log").write_text(completed.stdout or "")
            (directory / "cli.stderr.log").write_text(completed.stderr or "")
            entry["returncode"] = completed.returncode
            require(completed.returncode == 0, f"{name} failed; diagnostics retained in {directory}")
            published = directory / "published"
            entry["artifact_sha256"] = verify_hashes(published)
            entry["evidence"] = (verify_t9(published, orca.binary_sha256, pyscf.binary_sha256) if name == "h3-uhf-nevpt2"
                                 else verify_native(published, options, orca.binary_sha256))
            entry["status"] = "passed"
        report["grid_refinement"] = {}
        for method in ("b3lyp-d4", "wb97m-v"):
            energies = [report["calculations"][f"{method}-grid{stage}"]["evidence"]["energy_hartree"] for stage in (1, 2, 3)]
            difference = abs(energies[2] - energies[1])
            report["grid_refinement"][method] = {
                "energies_hartree": energies, "grid1_to_grid2_delta_hartree": energies[1] - energies[0],
                "grid2_to_grid3_delta_hartree": energies[2] - energies[1], "tolerance_hartree": GRID_TOLERANCE_HARTREE,
                "scope": "Numerical energy stability for this fixed water geometry and def2-SVP basis only",
            }
            require(difference <= GRID_TOLERANCE_HARTREE, f"{method} water grid2→grid3 energy change exceeds the declared tolerance")
        require(sha256(registry) == report["registry_sha256"], "Registry changed during acceptance")
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
    parser.add_argument("--pyscf-python", required=True, type=Path)
    parser.add_argument("--pyscf-version", default="2.14.0")
    args = parser.parse_args()
    try:
        report = run_acceptance(args.registry, args.output, args.pyscf_python, args.pyscf_version)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Scientific acceptance FAILED: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.output), "work_directory": report["work_directory"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
