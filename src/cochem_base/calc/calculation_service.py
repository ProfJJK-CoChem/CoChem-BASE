"""Native calculation service shared by headless CLI and the Voilà interface."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from cochem_base.exceptions import BinaryNotFoundError
from cochem_base.calc.t9_fallback import T9FallbackConfig, execute_with_t9_fallback
from cochem_base.core_engine.scientific_writer import scientific_producer

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]


def _engine_environment(engine: str, threads: int | None, inherited: dict[str, str],
                        *, executable: str | Path | None = None) -> dict[str, str]:
    """Keep ORCA's MPI ranks from each inheriting the full CPU thread budget."""
    from cochem_base.core_engine.cochem_core_subprocess_broker import sanitize_mpi_environment
    from cochem_base.core_engine.engine_environment import engine_runtime_environment

    environment = engine_runtime_environment(engine, inherited, executable=executable)
    if engine == "orca":
        # ORCA launches its MPI ranks from %pal in the input, which is not
        # visible to the broker's command-line MPI detection.
        return sanitize_mpi_environment(environment, force_single_thread=True)
    if engine == "cfour":
        if threads is not None:
            environment["OMP_NUM_THREADS"] = str(threads)
        # NCC can use OpenMP while its BLAS remains serial; allowing each
        # OpenMP worker another BLAS team would exceed the audited allocation.
        for variable in ("MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "GOTO_NUM_THREADS",
                         "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
            environment[variable] = "1"
        return environment
    if threads is not None:
        environment.update(OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads),
                           OPENBLAS_NUM_THREADS=str(threads))
    return environment


class CalculationMatrixConfig(BaseModel):
    """Validated single-geometry operation; product assignment is explicit."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    geometry: str
    engine: str = "orca"
    method: str = "wB97M-V"
    basis_set: Optional[str] = "def2-TZVP"
    product_class: Optional[str] = None
    theory_tier: Optional[str] = None
    charge: StrictInt = 0
    multiplicity: StrictInt = Field(default=1, ge=1)
    is_opt: bool = True
    is_freq: bool = False
    is_vpt2: bool = False
    recipe: Optional[str] = None
    grid_stage: Optional[StrictInt] = Field(default=None, ge=1, le=3)
    implicit_solvation: Optional[str] = None
    frozen_monomer_indices: Optional[List[StrictInt]] = None
    initial_hessian: str = "XTB2"
    hessian_file: Optional[Path] = None
    geometry_source: str = "electronic_structure"
    ab_initio_relaxed: bool = False
    cbs_cardinal_pair: Optional[Tuple[StrictInt, StrictInt]] = None
    timeout_seconds: float = Field(default=3600.0, gt=0.0, allow_inf_nan=False)
    t9_fallback: T9FallbackConfig | None = None
    r2_reference_manifest: Path | None = None
    pyscf_version: str = "2.14.0"
    periodic: dict[str, Any] | None = None

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, value: str) -> str:
        parse_run_geometry(value)
        return value

    @field_validator("engine")
    @classmethod
    def validate_engine(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"orca", "cfour", "xtb", "pyscf", "qe"}:
            raise ValueError(f"Unknown engine: {value}")
        return cleaned

    @model_validator(mode="after")
    def validate_recovery_and_reference_scope(self) -> "CalculationMatrixConfig":
        if self.engine == "orca":
            import re
            keywords = " ".join(value for value in (self.method, self.basis_set) if value)
            if re.search(r"\b(?:VPT2|ANFREQ)\b", keywords, re.I) and not self.is_vpt2:
                raise ValueError("ORCA anharmonic keywords require is_vpt2=true and its pending downstream contract")
            if re.search(r"\b(?:FREQ|NUMFREQ)\b", keywords, re.I) and not (self.is_freq or self.is_vpt2):
                raise ValueError("ORCA frequency keywords require is_freq=true and harmonic artifact validation")
            if re.search(r"\b(?:OPT|TIGHTOPT|VERYTIGHTOPT|LOOSEOPT|OPTTS|COPT)\b", keywords, re.I) and not self.is_opt:
                raise ValueError("ORCA optimization keywords require is_opt=true and geometry validation")
        if self.method.strip().lower() == "r2scan-3c":
            if "basis_set" not in self.model_fields_set:
                object.__setattr__(self, "basis_set", None)
            elif self.basis_set and self.basis_set.lower() not in {"built-in", "default"}:
                raise ValueError("r2SCAN-3c uses its published built-in composite basis; an appended basis changes the method")
        if self.t9_fallback is not None and self.engine != "orca":
            raise ValueError("Automatic T9 recovery currently requires the live ORCA spin gate")
        if self.r2_reference_manifest is not None and self.recipe != "R2":
            raise ValueError("A CCSD(T)/CBS reference manifest belongs to Recipe R2")
        if self.periodic is not None and self.engine != "qe":
            raise ValueError("Periodic cell and PAW configuration require the QE adapter")
        if self.engine == "qe" and self.periodic is None:
            raise ValueError("The QE adapter requires explicit periodic cell and PAW configuration")
        return self


def parse_run_geometry_identity(text: str):
    """Return the immutable nuclear identity and coordinates of one geometry."""
    from cochem_base.geometry.nuclide_geometry import parse_geometry_identity
    return parse_geometry_identity(text)


def parse_run_geometry(text: str) -> Tuple[List[str], List[Tuple[float, float, float]]]:
    """Return canonical electronic elements; nuclear assignments remain separate."""
    identity = parse_run_geometry_identity(text)
    return list(identity.elements), list(identity.coordinates_angstrom)


def _external_run_path(path: Path) -> Path:
    from cochem.core.context import assert_writable_path
    path = path.expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError("Calculation runtime and output paths must be outside the source checkout")
    assert_writable_path(path)
    return path


def _publish_run_artifacts(sandbox_dir: Path, output: Path) -> None:
    """Publish a complete evidence or pending-input package atomically."""
    import filelock
    output.parent.mkdir(parents=True, exist_ok=True)
    with filelock.FileLock(str(output) + ".lock", timeout=10.0):
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"Output directory is not empty: {output}")
        staging = output.parent / f".{output.name}.{uuid.uuid4().hex}.tmp"
        staging.mkdir()
        try:
            for artifact in sandbox_dir.rglob("*"):
                # Native CFOUR stages licensed basis libraries as symlinks.
                # Publish measured job artifacts without following links into
                # engine installations or distributing their runtime payload.
                # Persistent lock ownership changes on every reader admission.
                # Retain those locks in scratch; they are coordination state,
                # not immutable measured artifacts or checksum sidecars.
                if (artifact.is_symlink() or artifact.name in {"GENBAS", "ECPDATA"}
                        or artifact.name.endswith((".lock", ".lock.sha256"))):
                    continue
                if artifact.is_file():
                    destination = staging / artifact.relative_to(sandbox_dir)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(artifact, destination)
                    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
                    destination.with_name(destination.name + ".sha256").write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
            if output.exists():
                output.rmdir()
            os.replace(staging, output)
        finally:
            if staging.exists():
                shutil.rmtree(staging)


def _accept_orca_result(result: Any, sandbox_dir: Path, basin_id: str, config: CalculationMatrixConfig) -> dict[str, Any]:
    """Keep process diagnostics and reject a failed process before scientific parsing."""
    from cochem_base.calc.cochem_calc_output_parser import QuantumParser

    log = sandbox_dir / f"{basin_id}_job.out"
    log.write_text(result.stdout or "", encoding="utf-8")
    (sandbox_dir / "stderr.log").write_text(result.stderr or "", encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"ORCA failed with exit code {result.returncode}; diagnostics retained in {sandbox_dir}")
    parser = QuantumParser(str(sandbox_dir))
    if not parser.process_artifact(basin_id, is_optimization=config.is_opt, multiplicity=config.multiplicity):
        raise RuntimeError(f"ORCA output failed convergence validation; diagnostics retained in {sandbox_dir}")
    return json.loads((sandbox_dir / f"{basin_id}_qcschema.json").read_text(encoding="utf-8"))


def validate_frozen_monomer_trajectory(
    path: Path, elements: list[str], initial_coordinates: list, final_coordinates: list,
) -> dict[str, Any]:
    """Check every ORCA XYZ trajectory frame, including the actual final geometry."""
    from cochem_base.geometry.constraints import validate_trajectory_monomer_drift
    from cochem_base.geometry.fragment_partitioner import detect_molecular_fragments

    lines = path.read_text(encoding="utf-8").splitlines()
    frames = [initial_coordinates]
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        count = int(lines[index].strip())
        stop = index + count + 2
        if count != len(elements) or stop > len(lines):
            raise ValueError("Frozen-monomer trajectory contains an incomplete or incompatible XYZ frame")
        frame_elements, frame_coordinates = parse_run_geometry("\n".join(lines[index:stop]))
        if frame_elements != elements:
            raise ValueError("Frozen-monomer trajectory atom identities/order changed")
        frames.append(frame_coordinates)
        index = stop
    if len(frames) == 1:
        raise ValueError("An empty ORCA trajectory cannot certify frozen-monomer integrity")
    frames.append(final_coordinates)
    fragments = detect_molecular_fragments(elements, initial_coordinates)
    if len(fragments) < 2:
        raise ValueError("Frozen-monomer execution requires distinct molecular fragments")
    drifts = [validate_trajectory_monomer_drift(frames, group, raise_on_violation=True)[1] for group in fragments]
    return {"frame_count": len(frames) - 2, "monomer_indices": fragments,
            "maximum_internal_drift_angstrom": max(drifts), "tolerance_angstrom": 1e-6}


@scientific_producer
def run_calculation(
    config_path: str | Path, *, scratch: str | Path | None = None,
    output: str | Path | None = None, threads: int | None = None,
    maxcore_mb: int | None = None,
    device: str = "auto", dry_run: bool = False, keep_scratch: bool = False,
    engine: str | None = None, cancellation_event: Any = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute native capabilities, or preserve a pending job for future integration."""

    from cochem_base.calc.cochem_calc_input_generator import generate_orca_input, generate_pyscf_input
    from cochem_base.calc.molecular_input import build_molecular_input, canonical_theory_tier
    from cochem_base.config_loader import get_artifact_dir, resolve_executable
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    from cochem_base.theory_matrix import ProductClass
    from cochem_base.calc.xtb_execution import accept_xtb_result, validate_xtb_config, write_xtb_input
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    from cochem_base.physics.eckart_aligner import align_coordinates
    from cochem_base.interfaces.scientific_jobs import (
        calculation_capability, prepare_calculation_handoff, validate_job_configuration,
    )
    import numpy as np

    def emit(event: dict[str, Any]) -> None:
        if on_event is not None:
            on_event(event)

    cfg_path = Path(config_path).expanduser().resolve()
    sandbox_dir = None
    success = False
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        if engine:
            raw["engine"] = engine
        config = CalculationMatrixConfig.model_validate(raw)
        if config.hessian_file is not None and not config.hessian_file.is_absolute():
            config = config.model_copy(update={"hessian_file": (cfg_path.parent / config.hessian_file).resolve()})
        validate_job_configuration(config)
        capability = calculation_capability(config)
        pending = capability.adapter_status == "pending_integration"
        if not dry_run and not pending and config.engine == "orca" and config.multiplicity > 1 and config.t9_fallback is None:
            raise ValueError("Open-shell ORCA requires an explicit T9 active space before calculation so spin contamination can trigger automatic recovery without inventing orbitals or electron counts")
        if config.recipe == "R2" and not dry_run and not pending and config.r2_reference_manifest is None:
            raise ValueError("Recipe R2 production requires a validated CCSD(T)/CBS monomer reference manifest")
        if device == "cuda":
            raise ValueError("The native CPU adapters do not support --device cuda")
        if threads is not None and (isinstance(threads, bool) or threads < 1):
            raise ValueError("--threads must be a positive integer")
        if maxcore_mb is not None and (isinstance(maxcore_mb, bool) or not isinstance(maxcore_mb, int) or maxcore_mb < 1):
            raise ValueError("maxcore_mb must be a positive integer per process")
        if threads is None and config.engine in {"xtb", "pyscf", "qe", "cfour"}:
            threads = 1
        identity = parse_run_geometry_identity(config.geometry)
        elements, coordinates = list(identity.elements), list(identity.coordinates_angstrom)
        nuclides = list(identity.nuclides)
        original_coordinates = np.asarray(coordinates, dtype=float)
        product = None
        if config.product_class:
            if config.product_class.upper() in {"A", "B", "C"}:
                product = config.product_class.upper()
            else:
                product = ProductClass(config.product_class).name.rsplit("_", 1)[1]
        periodic = None
        if config.engine == "qe":
            from cochem_base.calc.periodic_execution import PeriodicCalculationConfig
            periodic = PeriodicCalculationConfig.model_validate(config.periodic)
            if product != "B" or config.method.upper() != "PBE" or config.basis_set not in {None, "PAW", "plane_wave", "built-in"}:
                raise ValueError("QE execution requires Product B, PBE and a plane-wave PAW basis")
            if config.is_opt or config.is_freq or config.is_vpt2 or config.recipe or config.implicit_solvation or config.frozen_monomer_indices is not None or config.hessian_file or config.grid_stage is not None or config.cbs_cardinal_pair or config.theory_tier or config.initial_hessian != "XTB2":
                raise ValueError("The QE adapter supports periodic single-point energies; molecular recipes, grids, Hessians and optimization/frequency requests are not supported")
            rotation, alignment_rmsd = None, None
        elif pending:
            # Reused Hessians/orbitals are bound to the supplied coordinate frame.
            # Its future consumer must validate/transform all coupled artifacts.
            rotation, alignment_rmsd = None, None
        else:
            normalized_coordinates, rotation, alignment_rmsd = align_coordinates(
                original_coordinates, original_coordinates, masses=identity.masses_u,
            )
            coordinates = normalized_coordinates.tolist()
        canonical_theory_tier(config.theory_tier)
        basin_id = f"job_{uuid.uuid4().hex}"
        molecule = build_molecular_input(
            config, basin_id=basin_id, coordinates=coordinates, nprocs=threads, maxcore_mb=maxcore_mb,
        ) if config.engine in {"orca", "pyscf"} else None
        xtb_config = config.model_copy(update={"is_freq": False, "is_vpt2": False}) if pending else config
        xtb_arguments = validate_xtb_config(xtb_config, elements) if config.engine == "xtb" else []
        engine_path = None
        authorization = None
        if not dry_run and not pending:
            override = os.environ.get(f"{config.engine.upper()}_CMD")
            engine_path = shutil.which(resolve_executable(override)) if override else None
            if override and engine_path is None:
                raise BinaryNotFoundError(f"A real {config.engine.upper()} executable is required; "
                                          f"configure {config.engine.upper()}_CMD or PATH")
            authorization = authorize_engine_execution(
                config.engine, registry_path=registry_path, executable=engine_path,
                cores=threads, maxcore_mb=maxcore_mb,
            )
            engine_path, threads = authorization.executable, authorization.cores
            if molecule is not None:
                molecule = molecule.model_copy(update={"nprocs": threads, "maxcore_mb": authorization.maxcore_mb})
        scratch_root = _external_run_path(Path(scratch or os.environ.get("COCH_SCRATCH") or get_artifact_dir() / "Scratch"))
        output_arg = output
        output = _external_run_path(Path(output_arg)) if output_arg else None
        scratch_root.mkdir(parents=True, exist_ok=True)
        sandbox_dir = scratch_root / basin_id
        sandbox_dir.mkdir()
        (sandbox_dir / "matrix_config.validated.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
        if config.engine == "orca" and config.initial_hessian == "READ" and not pending:
            # An electronic Hessian is a tensor tied to ordered atoms and a
            # coordinate frame. Snapshot the uploaded evidence, then rotate
            # its actual tensor into the same Eckart frame as the native deck.
            # Retain both files and their separate identities for inspection.
            from cochem_base.interfaces.scientific_inputs import transform_read_hessian
            checkpoint_dir = sandbox_dir / "scientific-inputs"
            checkpoint_dir.mkdir()
            source_checkpoint = config.hessian_file.resolve(strict=True)
            original_checkpoint = checkpoint_dir / ("original" + source_checkpoint.suffix.lower())
            source_digest = hashlib.sha256(source_checkpoint.read_bytes()).hexdigest()
            shutil.copyfile(source_checkpoint, original_checkpoint)
            if hashlib.sha256(original_checkpoint.read_bytes()).hexdigest() != source_digest:
                raise ValueError("The READ checkpoint changed while preserving its original input")
            transformed = transform_read_hessian(original_checkpoint, config.geometry,
                                                  checkpoint_dir / "aligned.hess")
            if (hashlib.sha256(source_checkpoint.read_bytes()).hexdigest() != source_digest
                    or not np.allclose(transformed["coordinates_angstrom"], coordinates, rtol=0, atol=1e-12)):
                raise ValueError("The preserved READ Hessian does not match the native input coordinate frame")
            receipt = dict(transformed["receipt"])
            receipt.update(original_input="scientific-inputs/" + original_checkpoint.name,
                           native_input="scientific-inputs/aligned.hess", uploaded_source_sha256=source_digest)
            (checkpoint_dir / "frame-binding.json").write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
            config = config.model_copy(update={"hessian_file": Path(transformed["path"])})
            molecule = build_molecular_input(config, basin_id=basin_id, coordinates=coordinates,
                                             nprocs=threads, maxcore_mb=authorization.maxcore_mb if authorization else maxcore_mb)
            (sandbox_dir / "matrix_config.execution.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
        (sandbox_dir / "ingress_alignment.json").write_text(json.dumps({
            "method": "periodic_cell_frame_preserved" if periodic is not None else "pending_input_frame_preserved" if pending else "mass_weighted_COM_and_Eckart_SVD", "elements": elements,
            "nuclear_identity": identity.metadata,
            "original_coordinates_angstrom": original_coordinates.tolist(),
            "coordinates_angstrom": coordinates, "rotation": rotation.tolist() if rotation is not None else None,
            "mass_weighted_rmsd_angstrom": alignment_rmsd,
        }, indent=2, allow_nan=False), encoding="utf-8")
        if pending:
            geometry = "\n".join([str(len(elements)), "Validated BASE job input; pending scientific integration"] +
                                 [symbol + " " + " ".join(format(float(value), ".17g") for value in xyz)
                                  for symbol, xyz in zip(nuclides, coordinates)]) + "\n"
            geometry_path = sandbox_dir / "geometry.xyz"
            geometry_path.write_text(geometry, encoding="utf-8")
            handoff_config = config.model_copy(update={"geometry": geometry})
            dependencies = {}
            for field_name in ("hessian_file", "r2_reference_manifest"):
                source = getattr(config, field_name)
                if source is not None:
                    source = source if source.is_absolute() else cfg_path.parent / source
                    dependencies[field_name + source.suffix] = source
            handoff = prepare_calculation_handoff(
                handoff_config, geometry_path, sandbox_dir / "handoff", dependency_files=dependencies,
                provider_options={"requested_threads": threads, "requested_device": device,
                                  "requested_maxcore_mb": maxcore_mb,
                                  "dependency_fields": list(dependencies)},
            )
            payload = {
                "status": "PENDING_INTEGRATION", "scientific_execution_performed": False,
                "config_file": str(cfg_path), "engine": config.engine, "method": config.method,
                "basis_set": config.basis_set, "dry_run": dry_run, "scratch_dir": str(sandbox_dir),
                "output_dir": str(output) if output is not None else None,
                "handoff_manifest": str((output or sandbox_dir) / "handoff" / "handoff.json"),
                "handoff_id": handoff.handoff_id, "capability": capability.model_dump(mode="json"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            (sandbox_dir / "execution.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
            if output is not None:
                _publish_run_artifacts(sandbox_dir, output)
            emit({"kind": "status", **payload})
            success = True
            return payload
        if authorization is not None:
            from dataclasses import asdict
            (sandbox_dir / "execution_authority.json").write_text(
                json.dumps(asdict(authorization), indent=2), encoding="utf-8",
            )
        if config.engine == "cfour":
            from cochem_base.calc.cfour_execution import write_cfour_input
            deck = write_cfour_input(
                sandbox_dir, config, elements, coordinates,
                memory_mb=authorization.total_memory_mb if authorization is not None else (maxcore_mb or 1024) * threads,
                gradient=config.method == "HF", harmonic=config.is_freq,
            )
        elif config.engine == "qe":
            from cochem_base.calc.periodic_execution import write_periodic_input
            deck = write_periodic_input(elements, coordinates, periodic, directory=sandbox_dir,
                                        charge=config.charge, multiplicity=config.multiplicity)
        elif config.engine == "pyscf":
            deck = generate_pyscf_input(molecule, output_dir=sandbox_dir, expected_version=config.pyscf_version)
        elif molecule is not None:
            deck = generate_orca_input(molecule, output_dir=sandbox_dir, registry_path=registry_path)
        else:
            deck = write_xtb_input(sandbox_dir, elements, coordinates)
        fallback = None
        if config.engine == "orca":
            from cochem_base.calc.grid_execution import quadrature_execution_plan
            (sandbox_dir / "grid_lifecycle.plan.json").write_text(
                json.dumps(quadrature_execution_plan(molecule), indent=2, allow_nan=False), encoding="utf-8",
            )
        emit({"kind": "status", "status": "DECK_GENERATED", "scratch_dir": str(sandbox_dir)})
        if not dry_run:
            environment = _engine_environment(config.engine, threads, dict(os.environ), executable=engine_path)
            accepted: dict[str, Any] | None = None

            def primary() -> None:
                nonlocal accepted
                if config.engine == "cfour":
                    from cochem_base.calc.cfour_execution import execute_cfour
                    emit({"kind": "status", "status": "RUNNING", "engine": "cfour"})
                    accepted = execute_cfour(
                        config, elements, coordinates, directory=sandbox_dir / "cfour",
                        authority=authorization, environment=environment,
                        cancellation_event=cancellation_event, on_event=on_event,
                        telemetry_job_id=basin_id,
                    )
                    return
                if config.engine == "qe":
                    from cochem_base.calc.periodic_execution import execute_periodic_singlepoint
                    accepted = execute_periodic_singlepoint(
                        elements, coordinates, periodic=periodic, workdir=sandbox_dir / "periodic",
                        cores=threads, timeout_seconds=config.timeout_seconds, charge=config.charge,
                        multiplicity=config.multiplicity, job_id=basin_id,
                        registry_path=registry_path,
                        cancellation_event=cancellation_event,
                        on_event=lambda event: emit({"kind": event.get("kind", "status"), **event}),
                        nuclides=nuclides,
                    )
                    return
                if config.recipe == "R2":
                    from cochem_base.calc.recipe_r2_execution import execute_recipe_r2
                    if not config.is_opt:
                        raise ValueError("Recipe R2 counterpoise production includes frozen-monomer geometry optimization; set is_opt=true")
                    manifest = config.r2_reference_manifest
                    if not manifest.is_absolute():
                        manifest = cfg_path.parent / manifest
                    accepted = execute_recipe_r2(
                        elements, coordinates, manifest,
                        work_dir=sandbox_dir / "r2", charge=config.charge, multiplicity=config.multiplicity,
                        registry_path=registry_path,
                        cores=threads, maxcore_mb=authorization.maxcore_mb,
                        timeout_seconds=config.timeout_seconds,
                        cancellation_event=cancellation_event, on_event=on_event,
                        is_freq=config.is_freq, is_vpt2=config.is_vpt2,
                        nuclides=nuclides,
                        publication_metadata={
                            "source_artifact_relative_path": "r2/dimer/native-gradient-evaluations.txt",
                            "published_source_path": str(output / "r2/dimer/native-gradient-evaluations.txt")
                                                     if output is not None else None,
                        },
                    )
                    return
                if config.engine == "orca":
                    from cochem_base.calc.grid_execution import execute_orca_calculation
                    accepted = execute_orca_calculation(
                        config, molecule, directory=sandbox_dir, authority=authorization,
                        environment=environment, capability=capability, registry_path=registry_path,
                        cancellation_event=cancellation_event, on_event=on_event,
                        telemetry_job_id=basin_id, nuclides=nuclides,
                        published_directory=output,
                    )
                    return
                if config.engine == "xtb" and config.is_opt:
                    from cochem_base.calc.xtb_optimization import execute_xtb_optimization
                    accepted = execute_xtb_optimization(
                        config, elements, coordinates, directory=sandbox_dir,
                        authority=authorization, environment=environment,
                        cancellation_event=cancellation_event, on_event=on_event,
                        telemetry_job_id=basin_id, nuclides=nuclides,
                        metadata={"nuclear_identity": identity.metadata},
                    )
                    return

                def stdout_line(line: str) -> None:
                    emit({"kind": "log", "stream": "stdout", "message": line})

                emit({"kind": "status", "status": "RUNNING", "engine": config.engine})
                command = ([engine_path, "-I", deck.name] if config.engine == "pyscf" else
                           [engine_path, deck.name, *xtb_arguments])
                result = safe_subprocess_run(
                    command, cwd=sandbox_dir,
                    timeout=config.timeout_seconds, check=False, capture_output=True, text=True,
                    env=environment, required_disk_gb=0.1, on_stdout_line=stdout_line,
                    on_stderr_line=lambda line: emit({"kind": "log", "stream": "stderr", "message": line}),
                    load_full_stdout=True, cancellation_event=cancellation_event,
                    cpu_affinity=list(authorization.cpu_affinity) or None,
                )
                if config.engine == "xtb":
                    accepted = accept_xtb_result(result, sandbox_dir, config, elements, parse_run_geometry)
                else:
                    from cochem_base.calc.pyscf_execution import accept_pyscf_result
                    accepted = accept_pyscf_result(result, sandbox_dir, deck, config, elements, coordinates)

            fallback = execute_with_t9_fallback(
                primary, config.t9_fallback, elements=elements, coordinates=coordinates,
                charge=config.charge, multiplicity=config.multiplicity,
                directory=sandbox_dir / "t9", cancellation_event=cancellation_event,
                registry_path=registry_path,
                nuclides=nuclides,
            )
            if fallback is not None:
                emit({"kind": "status", "status": "T9_FALLBACK_VERIFIED", "result": fallback})
                if config.is_opt or config.is_freq or config.is_vpt2:
                    raise RuntimeError(
                        "The contaminated trajectory was rejected and T9 single-point recovery verified. "
                        "The requested optimization/frequency calculation remains incomplete; "
                        f"multireference evidence is retained in {sandbox_dir / 't9'}."
                    )
            elif accepted is not None:
                from cochem_base.core_engine.scientific_telemetry import append_scientific_result
                accepted.update(nuclides=nuclides, nuclear_identity=identity.metadata)
                accepted.setdefault("metadata", {})["nuclear_identity"] = identity.metadata
                if config.engine == "qe" and accepted.get("job_id") == basin_id:
                    store = Path(accepted["archive_path"])
                else:
                    store = append_scientific_result(
                        basin_id, nuclides, accepted["coordinates_angstrom"], accepted["energy_hartree"],
                        gradients=accepted.get("gradients_hartree_per_bohr"),
                        metadata={"engine": config.engine, "method": config.method,
                                  "operation": accepted.get("operation", "optimization" if config.is_opt else "single_point"),
                                  "converged": True, "product_class": product,
                                  "cell_angstrom": accepted.get("cell_angstrom"),
                                  "result_metadata": accepted.get("metadata", {})},
                    )
                accepted.update(telemetry_path=str(store), telemetry_job_id=basin_id)
                (sandbox_dir / "result.json").write_text(json.dumps(accepted, indent=2, allow_nan=False), encoding="utf-8")
        status = "DECK_GENERATED" if dry_run else "T9_FALLBACK_VERIFIED" if fallback else "EXECUTION_VERIFIED"
        payload = {"status": status, "config_file": str(cfg_path), "engine": config.engine, "method": config.method,
                   "basis_set": config.basis_set, "dry_run": dry_run, "scratch_dir": str(sandbox_dir),
                   "operation": capability.operation,
                   "output_dir": str(output) if output is not None else None,
                   "timestamp": datetime.now(timezone.utc).isoformat()}
        if fallback is not None:
            payload.update(requested_engine=config.engine, requested_method=config.method,
                           engine="pyscf", method=fallback["method"], basis_set=fallback["basis"],
                           fallback=fallback, original_single_reference_rejected=True)
        (sandbox_dir / "execution.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if output is not None:
            _publish_run_artifacts(sandbox_dir, output)
        emit({"kind": "status", **payload})
        success = True
        return payload
    except Exception as exc:
        logger.error("Calculation was not accepted: %s", exc)
        if sandbox_dir is not None:
            failure = {"status": "REJECTED", "exception_type": type(exc).__name__, "error": str(exc)}
            if getattr(exc, "__notes__", None):
                failure["notes"] = list(exc.__notes__)
            details = getattr(exc, "details", None)
            if isinstance(details, dict):
                failure["details"] = details
            try:
                (sandbox_dir / "execution_failure.json").write_text(json.dumps(failure, indent=2, allow_nan=False), encoding="utf-8")
            except OSError as write_error:
                logger.error("Could not retain failure metadata: %s", write_error)
        emit({"kind": "status", "status": "REJECTED", "error": str(exc)})
        raise
    finally:
        # Failed jobs retain evidence; a successful unpromoted deck must remain usable.
        if success and sandbox_dir and output and not keep_scratch:
            shutil.rmtree(sandbox_dir)
