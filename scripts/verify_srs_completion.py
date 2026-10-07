"""Genuine native acceptance for BASE grid, derivative and isotope integration.

Explicitly selecting an engine requires its freshly audited installation. Missing
engines, failed calculations or absent scientific records fail this acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np


WATER = "O 0 0 0\nH 0.96 0 0\nH -0.24038 0.92942 0"
ISOTOPE_WATER = WATER.replace("O ", "18O ", 1).replace("H ", "2H ")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def run_acceptance(engine: str, registry: Path, output: Path) -> dict:
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    from cochem_base.spectroscopy.artifacts import load_hessian_artifact
    from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine

    require(not output.exists(), "Acceptance output already exists; retain previous evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="srs-completion-", dir=output.parent))
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, timeout=10, check=False)
    changed = subprocess.run(["git", "diff", "--quiet", "HEAD", "--"], cwd=root,
                             capture_output=True, timeout=10, check=False)
    report = {"status": "failed", "engine": engine, "work_directory": str(work),
              "base_version": importlib.metadata.version("CoChem-BASE"),
              "acceptance_script_sha256": digest(Path(__file__)),
              "source_git_commit": revision.stdout.strip() if revision.returncode == 0 else None,
              "source_git_tracked_dirty": bool(changed.returncode) if revision.returncode == 0 else None,
              "registry_sha256": digest(registry), "scientific_accuracy_established": False,
              "scope": "Actual native grid progression, Cartesian derivative telemetry and isotope-bound harmonic ingestion",
              "calculations": {}}
    started = time.monotonic()
    cases = [("isotope-harmonic", {"geometry": ISOTOPE_WATER, "engine": engine,
              "method": "HF", "basis_set": "STO-3G", "is_opt": True, "is_freq": True,
              "initial_hessian": "BFGS" if engine == "cfour" else "Lindh", "timeout_seconds": 600})]
    if engine == "orca":
        cases.insert(0, ("measured-grid-progression", {"geometry": WATER, "engine": "orca",
            "method": "PBE", "basis_set": "def2-SVP", "is_opt": True, "grid_stage": 1,
            "initial_hessian": "Lindh", "timeout_seconds": 600}))
        cases.append(("xtb-live-gradient-optimization", {"geometry": ISOTOPE_WATER, "engine": "xtb",
            "method": "GFN2-xTB", "basis_set": None, "is_opt": True, "timeout_seconds": 600}))
    try:
        for name, configuration in cases:
            job = work / name
            job.mkdir()
            config = job / "input.json"
            config.write_text(json.dumps(configuration, indent=2))
            published = job / "published"
            environment = {**os.environ, "COCHEM_CONFIG": str(registry)}
            command = [sys.executable, "-m", "cochem_base.cli", "run", "--config", str(config),
                       "--threads", "1", "--maxcore-mb", "256", "--scratch", str(job / "scratch"),
                       "--output", str(published), "--json"]
            with (job / "cli.log").open("w") as stream:
                completed = subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                                           timeout=660, check=False)
            require(completed.returncode == 0, f"Actual {name} calculation failed; inspect {job / 'cli.log'}")
            execution = json.loads((published / "execution.json").read_text())
            result = json.loads((published / "result.json").read_text())
            require(execution["status"] == "EXECUTION_VERIFIED", "Calculation did not establish execution acceptance")
            records = read_scientific_results(result["telemetry_job_id"], store_path=result["telemetry_path"])
            require(len(records["gradient_record_indices"]) >= 2, "Native optimization omitted intermediate Cartesian gradients")
            require(np.isfinite(records["gradients_hartree_per_bohr"]).all(), "Gradient telemetry contains invalid vectors")
            require(abs(float(records["energy_hartree"][-1]) - result["energy_hartree"]) < 1e-10,
                    "Final native energy differs from canonical telemetry")
            require(np.allclose(records["coordinates_angstrom"][-1], result["coordinates_angstrom"],
                                atol=1e-12, rtol=0), "Final geometry differs from canonical telemetry")
            require(int(records["gradient_record_indices"][-1]) == len(records["energy_hartree"]) - 1,
                    "Final accepted geometry has no canonical Cartesian gradient")
            require(np.allclose(records["gradients_hartree_per_bohr"][-1], result["gradients_hartree_per_bohr"],
                                atol=1e-12, rtol=0), "Final derivative differs from canonical telemetry")
            inventory = {}
            for artifact in published.rglob("*"):
                if artifact.is_file() and not artifact.name.endswith(".sha256"):
                    checksum = artifact.with_name(artifact.name + ".sha256")
                    require(checksum.is_file() and checksum.read_text().split()[0] == digest(artifact),
                            f"Published artifact checksum disagrees: {artifact}")
                    inventory[str(artifact.relative_to(published))] = digest(artifact)
            summary = {"status": "passed", "energy_hartree": result["energy_hartree"],
                       "gradient_evaluations": len(records["gradient_record_indices"]),
                       "published_sha256": inventory, "telemetry_job_id": result["telemetry_job_id"]}
            if name == "measured-grid-progression":
                lifecycle = json.loads((published / "grid_lifecycle.json").read_text())
                require(lifecycle["grids"] == ["DEFGRID1", "DEFGRID2", "DEFGRID3"], "The three-stage grid lifecycle was not executed")
                require(len(lifecycle["completed_stages"]) == 3, "Grid stages did not all complete")
                summary["grid_lifecycle"] = lifecycle
            else:
                require(result["nuclides"] == ["18O", "2H", "2H"], "Input nuclides were lost in calculation results")
                require(records["nuclides"] == ["18O", "2H", "2H"], "Canonical telemetry lost isotope identity")
                summary["nuclides"] = result["nuclides"]
                if engine == "cfour":
                    native_result = json.loads((published / "cfour" / "result.json").read_text())
                    require(native_result["nuclides"] == result["nuclides"]
                            and native_result["nuclear_identity"] == result["nuclear_identity"],
                            "Standalone CFOUR result lost the canonical nuclear identity")
                if name == "isotope-harmonic":
                    bundles = list(published.rglob("*harmonic-hessian.npz"))
                    require(len(bundles) == 1, "Native harmonic result omitted its canonical Hessian bundle")
                    # Loading uses a process lock. Read an exact retained copy so
                    # validation cannot alter the published immutable inventory.
                    retained = job / "verification-harmonic-hessian.npz"
                    shutil.copy2(bundles[0], retained)
                    require(digest(retained) == digest(bundles[0]), "Hessian verification copy differs")
                    bundle = load_hessian_artifact(retained)
                    require(list(bundle.symbols) == ["18O", "2H", "2H"], "Hessian ingestion lost input isotope identity")
                    reanalysis = IsotopologueSpectroscopyEngine(list(bundle.symbols), bundle.coordinates_angstrom,
                        bundle.hessian_hartree_bohr2).compute_observables()
                    require(np.allclose(reanalysis.harmonic_frequencies_cm1, result["harmonic_frequencies_cm1"],
                                        atol=1e-8, rtol=0), "Isotope spectrum differs from measured Hessian reanalysis")
                    require(np.allclose(reanalysis.masses, result["harmonic_isotope_masses_u"],
                                        atol=1e-12, rtol=0), "Harmonic calculation lost selected isotope masses")
                    require(np.allclose(reanalysis.masses, records["selected_isotope_masses_u"],
                                        atol=1e-12, rtol=0), "Canonical archive lost selected isotope masses")
                    summary["harmonic_hessian_sha256"] = digest(bundles[0])
                    summary["harmonic_frequencies_cm1"] = result["harmonic_frequencies_cm1"]
            report["calculations"][name] = summary
        # Each result names the actual canonical store; use that authority rather
        # than guessing a storage layout when retaining the acceptance snapshot.
        archive = Path(result["telemetry_path"])
        shutil.copy2(archive, work / "scientific-results.h5")
        report.update(status="passed", elapsed_seconds=time.monotonic() - started,
                      telemetry_snapshot_sha256=digest(work / "scientific-results.h5"))
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error), elapsed_seconds=time.monotonic() - started)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("orca", "cfour"), required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_acceptance(arguments.engine, arguments.registry.resolve(), arguments.output.resolve())
    print(json.dumps({key: value for key, value in report.items() if key != "calculations"}, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
