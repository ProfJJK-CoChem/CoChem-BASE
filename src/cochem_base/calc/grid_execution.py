"""Execute measured ORCA quadrature refinement without changing the method.

The lifecycle refines only the integration grid. Each stage must independently
pass the ordinary SCF, spin, geometry and derivative acceptance gates. A finer
stage is never advertised as converged merely because an earlier one converged.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable

import numpy as np

from cochem_base.exceptions import GridSpecificationError
from cochem_base.mm.quadrature_manager import QuadratureManager


# Only identified native density functionals enter the dynamic route. HF and
# wavefunction methods have no DFT quadrature to refine. An unclassified custom
# method retains its validated fixed grid rather than being silently classified.
_DFT = frozenset({
    "PBE", "PBE-D4", "PBE0", "PBE0-D3BJ", "PBE0-D4", "B3LYP", "B3LYP-D3BJ",
    "B3LYP-D4", "WB97X", "WB97X-D3", "WB97X-D4", "WB97X-V", "WB97M-V",
    "REV-WB97M-V", "B97-3C", "R2SCAN-3C", "R2SCAN", "SCAN", "TPSS", "REVTPSS",
    "BP86", "BLYP", "PW91", "M06", "M06-L", "M06-2X", "PWPB95", "PWPB95-D4",
    "B2PLYP", "B2PLYP-D3", "B2PLYP-D3BJ", "DSD-PBEP86", "REVDSD-PBEP86-D4",
})
_TRANSITION_METALS = frozenset({
    "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Y", "Zr",
    "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "Hf", "Ta", "W", "Re",
    "Os", "Ir", "Pt", "Au", "Hg",
})


def quadrature_execution_plan(molecule: Any) -> dict[str, Any]:
    """Return the native grid sequence, respecting every effective minimum."""
    minimum = int(molecule.resolved_grid()[-1])
    if any(element in _TRANSITION_METALS for element in molecule.elements):
        minimum = 3  # Match the deck compiler's metal safeguard.
    tokens = set(molecule.theory_level.upper().split())
    is_dft = bool(tokens & _DFT)
    dynamic = bool(is_dft and molecule.is_opt and not molecule.is_freq
                   and not molecule.is_vpt2 and molecule.recipe != "R2" and minimum < 3)
    stages = list(range(minimum, 4)) if dynamic else [minimum]
    reason = ("measured_DFT_optimization_refinement" if dynamic else
              "spectroscopic_or_R2_DEFGRID3" if molecule.is_freq or molecule.is_vpt2 or molecule.recipe == "R2" else
              "effective_minimum_DEFGRID3" if minimum == 3 else
              "non_DFT_or_single_point_fixed_grid")
    return {"schema_version": 1, "grids": [f"DEFGRID{stage}" for stage in stages],
            "stages": stages, "dynamic": dynamic, "reason": reason,
            "method_unchanged": True, "initial_theory_level": molecule.theory_level,
            "minimum_grid": f"DEFGRID{minimum}", "scientific_accuracy_established": False}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def _digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _lifecycle_telemetry_summary(path: Path, lifecycle: dict[str, Any]) -> dict[str, Any]:
    """Bind large geometry/state provenance by hash without duplicating it in H5."""
    return {"schema_version": 1, "artifact": {"filename": path.name, "sha256": _digest(path)},
            "grids": lifecycle["grids"], "final_grid": lifecycle["grids"][-1],
            "dynamic": lifecycle["dynamic"], "method_unchanged": True,
            "completed_stages": [{key: stage[key] for key in (
                "grid", "energy_hartree", "gradient_evaluations", "converged", "input_sha256", "log_sha256",
                "wavefunction_sha256", "native_quintuple_convergence", "promotion",
            ) if key in stage} for stage in lifecycle["completed_stages"]]}


def _promotion_evidence(stage: int, accepted: dict[str, Any], records: list[dict[str, Any]],
                        convergence: dict[str, float]) -> dict[str, Any]:
    """Require measured final derivatives and displacement before tightening."""
    gradient = np.asarray(accepted["gradients_hartree_per_bohr"], dtype=float)
    if not records or gradient.ndim != 2 or gradient.shape[1] != 3 or not np.isfinite(gradient).all():
        raise GridSpecificationError("Grid promotion requires measured Cartesian gradient telemetry")
    maximum = float(np.max(np.abs(gradient)))
    # The final table is a native within-stage energy change, unlike the energy
    # offset between two different integration grids.
    energy_change = float(convergence["Energy change"])
    final = np.asarray(accepted["coordinates_angstrom"], dtype=float)
    prior = np.asarray(records[-2 if len(records) > 1 else -1]["coordinates_angstrom"], dtype=float)
    if prior.shape != final.shape or not np.isfinite(prior).all():
        raise GridSpecificationError("Grid promotion requires ordered, geometry-bound measured records")
    rmsd = float(np.sqrt(np.mean(np.sum((final - prior) ** 2, axis=1))))
    next_stage = QuadratureManager.determine_next_stage(stage, maximum, energy_change, rmsd)
    if int(next_stage) != stage + 1:
        raise GridSpecificationError("The measured gradient/energy/displacement did not permit grid promotion")
    return {"measured_max_gradient_hartree_per_bohr": maximum,
            "native_within_stage_energy_change_hartree": energy_change,
            "measured_last_step_cartesian_rmsd_angstrom": rmsd,
            "next_grid": f"DEFGRID{int(next_stage)}", "accepted": True}


def _stage_model(molecule: Any, stage: int, coordinates: Any) -> Any:
    """Validate a stage without loosening product, tier, SCF or Hessian policy."""
    from cochem_base.calc.cochem_calc_input_generator import MoleculeInput
    minimum = quadrature_execution_plan(molecule)["stages"][0]
    if isinstance(stage, bool) or not isinstance(stage, int) or not minimum <= stage <= 3:
        raise GridSpecificationError(f"A native execution stage cannot lower its effective DEFGRID{minimum} minimum")
    data = molecule.model_dump()
    data.update(grid_stage=stage, coordinates=coordinates,
                theory_level=re.sub(r"\bDEFGRID\d+\b", "", molecule.theory_level, flags=re.I).strip())
    return MoleculeInput.model_validate(data)


def execute_orca_calculation(
    config: Any, molecule: Any, *, directory: Path, authority: Any,
    environment: dict[str, str], capability: Any, registry_path: str | Path | None,
    cancellation_event: Any = None, on_event: Callable[[dict[str, Any]], None] | None = None,
    telemetry_job_id: str, nuclides: list[str] | None = None,
    published_directory: Path | None = None,
) -> dict[str, Any]:
    """Run fixed or staged ORCA decks through the same physical acceptance."""
    from cochem_base.analysis.electronic_sanitizer import SpinContaminationStreamValidator
    from cochem_base.calc.calculation_service import (
        _accept_orca_result, parse_run_geometry, validate_frozen_monomer_trajectory,
    )
    from cochem_base.calc.cochem_calc_input_generator import generate_orca_input
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser
    from cochem_base.calc.orca_derivatives import accept_gradient, accept_harmonic_hessian
    from cochem_base.core_engine.cochem_core_subprocess_broker import (
        SubprocessCancelledError, safe_subprocess_run,
    )
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.core_engine.gradient_telemetry import ORCAGradientStream

    plan = quadrature_execution_plan(molecule)
    _write_json(directory / "grid_lifecycle.plan.json", plan)
    started = time.monotonic()
    deadline = started + config.timeout_seconds
    coordinates = molecule.coordinates
    previous: tuple[Path, str] | None = None
    stage_results = []
    accepted = None

    def emit(event: dict[str, Any]) -> None:
        if on_event is not None:
            on_event(event)

    def remaining() -> float:
        if cancellation_event is not None and cancellation_event.is_set():
            raise SubprocessCancelledError("ORCA calculation was cancelled")
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise subprocess.TimeoutExpired([authority.executable], config.timeout_seconds)
        return budget

    for stage in plan["stages"]:
        remaining()
        # Every subprocess sees the same originally authorized binary/allocation.
        current = authorize_engine_execution(
            "orca", registry_path=registry_path, executable=authority.executable,
            cores=authority.cores, maxcore_mb=authority.maxcore_mb,
        )
        if asdict(current) != asdict(authority):
            raise RuntimeError("ORCA authority changed during quadrature refinement")
        stage_dir = directory / "grid_stages" / f"defgrid{stage}" if plan["dynamic"] else directory
        stage_dir.mkdir(parents=True, exist_ok=True)
        data = _stage_model(molecule, stage, coordinates)
        deck = generate_orca_input(data, stage_dir, registry_path=registry_path)
        transfers: dict[str, Any] = {"geometry": {"elements": data.elements,
                                                  "coordinates_angstrom": coordinates}}
        if previous is not None:
            prior_dir, prior_stem = previous
            prior_gbw = prior_dir / f"{prior_stem}.gbw"
            if not prior_gbw.is_file() or prior_gbw.stat().st_size == 0:
                raise RuntimeError("Converged ORCA stage omitted the wavefunction checkpoint for handoff")
            restart = stage_dir / "previous-stage.gbw"
            shutil.copy2(prior_gbw, restart)
            if _digest(prior_gbw) != _digest(restart):
                raise RuntimeError("ORCA wavefunction checkpoint changed during stage transfer")
            # ORCA's native MOREAD opens the input GBW with update access even
            # though its originating accepted checkpoint remains immutable.
            # Give only this job-owned copy write access and retain both hashes.
            restart.chmod(0o600)
            text = deck.read_text(encoding="utf-8")
            text = re.sub(r"(?m)^(![^\n]*)$", r"\1 MOREAD", text, count=1)
            deck.write_text(text + '\n%moinp "previous-stage.gbw"\n', encoding="utf-8")
            transfers["wavefunction"] = {"source": str(prior_gbw.relative_to(directory)),
                                           "source_sha256": _digest(prior_gbw),
                                           "input_copy_sha256": _digest(restart), "native_keyword": "MOREAD"}
        # An optimizer .opt file is a private native restart format, not a
        # portable Cartesian Hessian. Never relabel it as a .hess checkpoint.
        transfers["initial_hessian"] = {"native_policy": data.initial_hessian,
            "source_sha256": _digest(data.hessian_file) if data.hessian_file is not None else None,
            "portable_optimizer_hessian_available": False}
        _write_json(stage_dir / "stage_handoff.json", transfers)
        spin = SpinContaminationStreamValidator(config.multiplicity)
        stream = ORCAGradientStream(
            telemetry_job_id, data.elements, nuclides=nuclides,
            source_id=f"{telemetry_job_id}-defgrid{stage}", source_path=stage_dir / "native-gradient-evaluations.txt",
            metadata={"engine": "orca", "method": config.method, "basis_set": config.basis_set,
                      "source_artifact_relative_path": str((stage_dir / "native-gradient-evaluations.txt").relative_to(directory)),
                      "published_source_path": str(published_directory / (stage_dir / "native-gradient-evaluations.txt").relative_to(directory))
                                               if published_directory is not None else None,
                      "grid": f"DEFGRID{stage}", "record_kind": "native_gradient_evaluation"},
            on_record=lambda record: emit({"kind": "gradient", "grid": f"DEFGRID{stage}", **record}),
        )

        def stdout_line(line: str) -> None:
            spin(line)
            stream(line)
            emit({"kind": "log", "stream": "stdout", "grid": f"DEFGRID{stage}", "message": line})

        emit({"kind": "status", "status": "RUNNING", "engine": "orca", "grid": f"DEFGRID{stage}"})
        stage_started = time.monotonic()
        stage_timeout = remaining()
        result = safe_subprocess_run(
            [authority.executable, deck.name], cwd=stage_dir, timeout=stage_timeout, check=False,
            capture_output=True, text=True, env=environment, required_disk_gb=0.1,
            on_stdout_line=stdout_line,
            on_stderr_line=lambda line: emit({"kind": "log", "stream": "stderr", "message": line}),
            load_full_stdout=True, cancellation_event=cancellation_event,
            cpu_affinity=list(authority.cpu_affinity) or None,
        )
        schema = _accept_orca_result(result, stage_dir, data.basin_id, config)
        if previous is not None:
            if not re.search(r"^[ \t]*Guess MOs are being read from file:[ \t]+previous-stage\.gbw[ \t]*$",
                             result.stdout or "", flags=re.MULTILINE):
                raise RuntimeError("ORCA output did not verify reading the handed-off native wavefunction")
            transfers["wavefunction"]["native_readback_verified"] = True
            transfers["wavefunction"]["after_execution_sha256"] = _digest(restart)
            if _digest(prior_gbw) != transfers["wavefunction"]["source_sha256"]:
                raise RuntimeError("The accepted originating ORCA wavefunction changed during refinement")
            _write_json(stage_dir / "stage_handoff.json", transfers)
        _write_json(stage_dir / "trajectory_telemetry.json", stream.finish(required=config.is_opt))
        remaining()
        elements, final = data.elements, coordinates
        if config.is_opt:
            elements, final = parse_run_geometry((stage_dir / f"{data.basin_id}_job.xyz").read_text(encoding="utf-8"))
            if elements != data.elements:
                raise RuntimeError("ORCA output atom identities/order differ from the submitted geometry")
            if config.recipe is not None:
                _write_json(stage_dir / "frozen_monomer_integrity.json", validate_frozen_monomer_trajectory(
                    stage_dir / f"{data.basin_id}_job_trj.xyz", data.elements, molecule.coordinates, final,
                ))
        accepted = {"engine": "orca", "method": config.method, "converged": True,
                    "energy_hartree": schema["properties"]["return_energy"], "elements": elements,
                    "coordinates_angstrom": final, "operation": capability.operation,
                    "optimization_performed": config.is_opt}
        accepted.update(accept_gradient(
            stage_dir / f"{data.basin_id}_job.engrad", elements, final, accepted["energy_hartree"],
            required=config.is_opt or bool(re.search(r"\bENGRAD\b", data.theory_level, re.I)),
        ))
        if config.is_freq:
            accepted.update(accept_harmonic_hessian(
                stage_dir / f"{data.basin_id}_job.hess", stage_dir / f"{data.basin_id}_job.out",
                elements, final, optimized=config.is_opt, nuclides=nuclides,
            ))
        evidence = {"grid": f"DEFGRID{stage}", "directory": str(stage_dir.relative_to(directory)),
                    "energy_hartree": accepted["energy_hartree"], "coordinates_angstrom": final,
                    "gradient_evaluations": len(stream.records), "converged": True,
                    "timeout_remaining_at_launch_seconds": stage_timeout,
                    "native_stage_elapsed_seconds": time.monotonic() - stage_started,
                    "input_sha256": _digest(deck), "log_sha256": schema["provenance"]["log_sha256"],
                    "wavefunction_sha256": schema["provenance"].get("gbw_sha256"), "handoff": transfers}
        if config.is_opt:
            convergence = QuantumParser(str(stage_dir)).verify_geometry_convergence(stage_dir / f"{data.basin_id}_job.out")
            evidence["native_quintuple_convergence"] = convergence
            if plan["dynamic"] and stage < 3:
                evidence["promotion"] = _promotion_evidence(stage, accepted, stream.records, convergence)
        _write_json(stage_dir / "stage_result.json", {**accepted, "grid_evidence": evidence})
        stage_results.append(evidence)
        _write_json(directory / "grid_lifecycle.json", {**plan, "completed_stages": stage_results,
            "whole_operation_timeout_seconds": config.timeout_seconds,
            "observed_elapsed_seconds": time.monotonic() - started,
            "status": "EXECUTION_VERIFIED" if stage == plan["stages"][-1] else "REFINEMENT_PENDING"})
        emit({"kind": "status", "status": "GRID_STAGE_VERIFIED", "grid": f"DEFGRID{stage}",
              "energy_hartree": accepted["energy_hartree"]})
        coordinates = final
        previous = stage_dir, deck.stem
        remaining()
    if accepted is None:
        raise RuntimeError("ORCA lifecycle did not execute a stage")
    # Preserve the historic canonical artifact names for downstream ingestion;
    # the full stage directories and provenance remain separately retained.
    if plan["dynamic"]:
        final_dir = previous[0]
        for artifact in final_dir.iterdir():
            if artifact.is_file() and not artifact.is_symlink() and artifact.name not in {
                "stage_handoff.json", "stage_result.json", "previous-stage.gbw",
            }:
                shutil.copy2(artifact, directory / artifact.name)
    accepted["grid_lifecycle"] = {**plan, "completed_stages": stage_results, "final_grid": plan["grids"][-1],
                                  "whole_operation_timeout_seconds": config.timeout_seconds,
                                  "observed_elapsed_seconds": time.monotonic() - started}
    accepted["metadata"] = {key: accepted[key] for key in (
        "gradient_artifact", "hessian_artifact", "harmonic_frequencies_cm1", "principal_isotope_masses_u",
        "harmonic_frequency_provenance", "hessian_bundle_artifact", "harmonic_nuclides",
        "harmonic_isotope_masses_u",
    ) if key in accepted}
    accepted["metadata"]["grid_lifecycle"] = _lifecycle_telemetry_summary(directory / "grid_lifecycle.json", accepted["grid_lifecycle"])
    remaining()
    return accepted
