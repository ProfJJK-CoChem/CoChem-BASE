"""Bounded optimization with actual xTB Cartesian gradients at every evaluation.

The native ANC optimizer exposes only a scalar gradient norm in its XYZ log.
BASE therefore uses SciPy BFGS with native ``--grad`` evaluations when complete
live vector telemetry is required. Line-search evaluations are explicitly
identified as evaluations, rather than fictitious accepted optimizer steps.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from typing import Any, Callable, Sequence

import numpy as np
from scipy.optimize import minimize

from cochem_base.calc.xtb_execution import accept_xtb_result, validate_xtb_config, write_xtb_input
from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError, safe_subprocess_run
from cochem_base.core_engine.execution_authority import RegistryAuthorityViolationError
from cochem_base.core_engine.scientific_telemetry import append_scientific_result
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity

# xTB/mctc-lib uses CODATA 2018. Do not silently replace its native coordinate
# convention when SciPy updates its default table (currently CODATA 2022).
BOHR_ANGSTROM = 0.529177210903


def read_xtb_gradient(path: Path, elements: Sequence[str], coordinates_angstrom: Any,
                      energy_hartree: float) -> dict[str, Any]:
    """Read the native Turbomole gradient, whose coordinates are explicitly Bohr."""
    raw = path.read_bytes()
    rows = [line.strip() for line in raw.decode("utf-8", errors="strict").splitlines() if line.strip()]
    n = len(elements)
    if len(rows) != 2 * n + 3 or rows[0] != "$grad" or rows[-1] != "$end":
        raise ValueError("xTB gradient must contain its complete ordered geometry and 3N Cartesian gradient")
    match = re.fullmatch(r"cycle\s*=\s*(\d+)\s+SCF energy\s*=\s*(\S+)\s+\|dE/dxyz\|\s*=\s*(\S+)", rows[1])
    if match is None or int(match[1]) != 1:
        raise ValueError("Native xTB gradient header is invalid")
    numeric = lambda v: float(v.replace("D", "E").replace("d", "e"))
    energy, source_norm = numeric(match[2]), numeric(match[3])
    native, gradients = [], []
    for symbol, row in zip(elements, rows[2:2 + n], strict=True):
        fields = row.split()
        if len(fields) != 4 or fields[3].capitalize() != symbol:
            raise ValueError("xTB gradient atom identities/order differ from submitted geometry")
        native.append([numeric(v) for v in fields[:3]])
    for row in rows[2 + n:2 + 2 * n]:
        fields = row.split()
        if len(fields) != 3:
            raise ValueError("xTB gradient contains an incomplete Cartesian vector")
        gradients.append([numeric(v) for v in fields])
    xyz, gradient = np.asarray(native) * BOHR_ANGSTROM, np.asarray(gradients)
    target = np.asarray(coordinates_angstrom)
    if (target.shape != xyz.shape or not np.isfinite(xyz).all() or not np.isfinite(gradient).all()
            or not np.isfinite([energy, source_norm, energy_hartree]).all()):
        raise ValueError("xTB gradient energy, geometry and vectors must be finite")
    if not np.allclose(xyz, target, rtol=0, atol=1e-9):
        raise ValueError("xTB Cartesian gradient does not belong to the submitted geometry")
    if abs(energy - energy_hartree) > 2e-8:
        raise ValueError("xTB gradient checkpoint and accepted electronic energy disagree")
    if abs(np.linalg.norm(gradient) - source_norm) > 1e-6:
        raise ValueError("xTB Cartesian gradient and printed native norm disagree")
    return {"gradients_hartree_per_bohr": gradient.tolist(),
            "native_coordinates_angstrom": xyz.tolist(), "gradient_energy_hartree": energy,
            "gradient_artifact": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_length": len(raw), "format": "xtb_native_turbomole_gradient",
                "unit": "hartree/bohr", "coordinates_unit": "bohr",
                "bohr_angstrom": BOHR_ANGSTROM, "coordinate_binding_tolerance_angstrom": 1e-9,
                "unit_authority": "xTB native Turbomole Cartesian-gradient protocol",
                "native_to_submitted_rotation": np.eye(3).tolist()}}


def execute_xtb_optimization(config: Any, elements: Sequence[str], coordinates: Any, *,
                             directory: Path, authority: Any, environment: dict[str, str],
                             cancellation_event: Any = None,
                             on_event: Callable[[dict[str, Any]], None] | None = None,
                             telemetry_job_id: str | None = None, nuclides: Sequence[str] | None = None,
                             store_path: str | Path | None = None,
                             metadata: dict[str, Any] | None = None,
                             optimization_level: str = "tight", strict: bool = False) -> dict[str, Any]:
    """Run genuine native gradients with one wall-clock budget and audited CPU allocation."""
    from cochem_base.calc.calculation_service import parse_run_geometry

    if not config.is_opt:
        raise ValueError("The measured-gradient optimizer requires is_opt=true")
    if optimization_level not in {"tight", "vtight"} or not isinstance(strict, bool):
        raise ValueError("xTB optimizer supports explicit tight or vtight controls and a boolean strict policy")
    component_limit = 1e-6 if optimization_level == "vtight" else 1e-5
    norm_limit = 1e-5 if optimization_level == "vtight" else 1e-4
    identity = resolve_nuclear_identity(nuclides if nuclides is not None else elements)
    if identity.elements != tuple(elements):
        raise ValueError("xTB gradient telemetry isotope identities must match electronic elements")
    if authority.engine != "xtb":
        raise RegistryAuthorityViolationError("xTB optimization requires audited xTB execution authority")
    arguments = validate_xtb_config(config, elements)
    opt = arguments.index("--opt")
    arguments = [*arguments[:opt], *arguments[opt + 2:], "--grad"]
    if strict:
        arguments.append("--strict")
    native_config = config.model_copy(update={"is_opt": False})
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    initial = np.asarray(coordinates, dtype=float)
    if initial.shape != (len(elements), 3) or not np.isfinite(initial).all():
        raise ValueError("xTB optimizer requires finite N x 3 submitted coordinates")
    write_xtb_input(directory, elements, initial)
    started = time.monotonic()
    child_environment = dict(environment)
    child_environment["OMP_NUM_THREADS"] = str(authority.cores)
    for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        child_environment[name] = "1"
    evaluations: list[dict[str, Any]] = []
    final_native: dict[str, Any] | None = None
    event = on_event or (lambda record: None)

    def verify_binary() -> None:
        if hashlib.sha256(Path(authority.executable).read_bytes()).hexdigest() != authority.binary_sha256:
            raise RegistryAuthorityViolationError("xTB binary changed after Stage 0 execution authorization")

    def cancelled() -> None:
        if cancellation_event is not None and cancellation_event.is_set():
            raise SubprocessCancelledError("xTB optimization was cancelled")

    def remaining_budget() -> float:
        remaining = config.timeout_seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("xTB optimization exceeded its total wall-clock budget")
        return remaining

    def evaluate(flat: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal final_native
        cancelled()
        remaining = remaining_budget()
        if len(evaluations) >= 500:
            raise RuntimeError("xTB optimization exceeded its 500 measured-evaluation budget")
        verify_binary()
        xyz = flat.reshape(-1, 3)
        work = directory / f"evaluation-{len(evaluations):04d}"
        work.mkdir(exist_ok=False)
        deck = write_xtb_input(work, elements, xyz)
        event({"kind": "status", "status": "RUNNING", "engine": "xtb", "evaluation": len(evaluations)})
        process = safe_subprocess_run(authority.command([deck.name, *arguments]), cwd=work,
            timeout=remaining, check=False, capture_output=True, text=True,
            env=child_environment, required_disk_gb=0.1, load_full_stdout=True,
            on_stdout_line=lambda line: event({"kind": "log", "stream": "stdout", "message": line}),
            on_stderr_line=lambda line: event({"kind": "log", "stream": "stderr", "message": line}),
            cancellation_event=cancellation_event, cpu_affinity=list(authority.cpu_affinity) or None,
            sanitize_mpi=False)
        cancelled()
        verify_binary()
        accepted = accept_xtb_result(process, work, native_config, elements, parse_run_geometry)
        derivative = read_xtb_gradient(work / "gradient", elements, xyz, accepted["energy_hartree"])
        remaining_budget()
        gradient = np.asarray(derivative["gradients_hartree_per_bohr"])
        record = {"evaluation_index": len(evaluations), "energy_hartree": accepted["energy_hartree"],
                  "coordinates_angstrom": xyz.tolist(), "gradients_hartree_per_bohr": gradient.tolist(),
                  "directory": work.name, "record_kind": "measured_optimization_gradient_evaluation",
                  "gradient_artifact": {**derivative["gradient_artifact"], "path": f"{work.name}/gradient"},
                  "input_sha256": hashlib.sha256(deck.read_bytes()).hexdigest(),
                  "stdout_sha256": hashlib.sha256((work / "xtb.out").read_bytes()).hexdigest(),
                  "binary_sha256": authority.binary_sha256, "cores": authority.cores,
                  "nuclear_identity": identity.metadata,
                  "optimization_level": optimization_level, "native_strict": strict,
                  "optimizer": "SciPy BFGS with native xTB analytic gradients"}
        if telemetry_job_id is not None:
            archive = append_scientific_result(telemetry_job_id, identity.nuclides, xyz,
                accepted["energy_hartree"], gradients=gradient,
                metadata={**(metadata or {}), "engine": "xtb", "method": config.method,
                          "gradient_source": record}, store_path=store_path)
            record["archive_path"] = str(archive)
        evaluations.append(record)
        with (directory / "xtbopt.log").open("a", encoding="utf-8") as output:
            output.write(f"{len(elements)}\nenergy: {accepted['energy_hartree']:.17g} Eh xtb: measured BFGS evaluation {len(evaluations) - 1}\n")
            for symbol, position in zip(elements, xyz, strict=True):
                output.write(symbol + " " + " ".join(format(value, ".17g") for value in position) + "\n")
        (directory / "optimization_evaluations.json").write_text(json.dumps(evaluations, indent=2, allow_nan=False), encoding="utf-8")
        event({"kind": "telemetry", "engine": "xtb", "record": record})
        cancelled()
        remaining_budget()
        final_native = {**accepted, **derivative, "native_directory": work}
        return accepted["energy_hartree"], gradient.ravel() / BOHR_ANGSTROM

    event({"kind": "status", "status": "OPTIMIZING", "engine": "xtb"})
    optimized = minimize(evaluate, initial.ravel(), method="BFGS", jac=True,
                         options={"gtol": component_limit / BOHR_ANGSTROM, "maxiter": 200})
    cancelled()
    if not optimized.success:
        raise RuntimeError(f"xTB measured-gradient BFGS optimization did not converge: {optimized.message}")
    # Explicitly re-evaluate the accepted optimizer geometry; a prior line-search
    # observation must never be relabeled as the optimizer's final coordinates.
    energy, _ = evaluate(np.asarray(optimized.x))
    cancelled()
    final_coordinates = np.asarray(optimized.x).reshape(-1, 3)
    gradient = np.asarray(final_native["gradients_hartree_per_bohr"])
    if np.max(np.abs(gradient)) > component_limit or np.linalg.norm(gradient) > norm_limit:
        raise ValueError("xTB final measured Cartesian gradient exceeds tight optimization limits")
    work = final_native.pop("native_directory")
    for name in ("xtb.out", "stderr.log", "gradient", "input.engrad"):
        if (work / name).is_file():
            shutil.copyfile(work / name, directory / name)
    shutil.copyfile(work / "input.xyz", directory / "xtbopt.xyz")
    evidence = {"optimizer": "SciPy BFGS with native xTB analytic gradients", "converged": True,
        "iterations": int(optimized.nit), "evaluations": len(evaluations),
        "trajectory_scope": "Every genuine gradient evaluation, including line-search evaluations",
        "gradient_norm_hartree_per_bohr": float(np.linalg.norm(gradient)),
        "maximum_gradient_component_hartree_per_bohr": float(np.max(np.abs(gradient))),
        "gradient_norm_limit_hartree_per_bohr": norm_limit, "maximum_gradient_component_limit_hartree_per_bohr": component_limit,
        "optimization_level": optimization_level, "native_strict": strict,
        "optimizer_success_message": str(optimized.message), "scientific_accuracy_established": False}
    result = {**final_native, "energy_hartree": energy, "optimization_converged": True,
        "operation": "optimization", "coordinates_angstrom": final_coordinates.tolist(),
        "gradient_artifact": {**final_native["gradient_artifact"], "path": "gradient"},
        "optimization_evidence": evidence, "metadata": {"optimization_evidence": evidence}}
    (directory / "optimization_evidence.json").write_text(json.dumps(evidence, indent=2, allow_nan=False), encoding="utf-8")
    cancelled()
    remaining_budget()
    (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    try:
        cancelled()
        remaining_budget()
    except (TimeoutError, SubprocessCancelledError):
        (directory / "result.json").unlink(missing_ok=True)
        raise
    return result
