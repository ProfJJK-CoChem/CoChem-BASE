"""Asynchronous, physical CREST/ORCA GOAT searches and validated ensemble promotion.

The default search is the parallel CREST + GOAT union. Missing input, unavailable
engines, failed calculations, and incomplete ensembles fail closed. No generated
molecule or surrogate calculator is substituted for a requested search engine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import filelock
import numpy as np
import psutil
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.config_loader import get_artifact_dir, resolve_executable
from cochem_base.intake.conformer_deduplication import ConformerCandidate, ConformerDeduplicator
from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.cochem_core_subprocess_broker import sanitize_mpi_environment
from cochem_base.core_engine.scientific_telemetry import append_scientific_result
from cochem_base.physics.eckart_aligner import align_coordinates, verify_com_residual, verify_eckart_residual
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity


class TOPOSJobStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TOPOSSearchConfig(BaseModel):
    """Explicit physical search input; engine paths can name configured binaries."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    tier_id: str = "T1-10m"
    protocol: Literal["CREST_GOAT", "GOAT", "CREST_NCI"] = "CREST_GOAT"
    product_class: Literal["A", "B", "C"] = "A"
    atom_count: int = Field(default=6, ge=1)
    input_xyz_path: str = ""
    max_hours: float = Field(default=2.0, gt=0.0, allow_inf_nan=False)
    scratch_dir: str = ""
    store_dir: str = ""
    charge: int = 0
    multiplicity: int = Field(default=1, ge=1)
    threads_per_engine: int = Field(default=1, ge=1)
    crest_binary: str | None = None
    orca_binary: str | None = None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Publish a complete telemetry document under the shared 10-second lock."""
    with filelock.FileLock(str(path) + ".lock", timeout=10.0):
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    with filelock.FileLock(str(path) + ".lock", timeout=10.0):
        return dict(json.loads(path.read_text(encoding="utf-8")))


def _parse_xyz(path: Path, *, require_energy: bool) -> list[ConformerCandidate]:
    """Read full XYZ frames, rejecting incomplete coordinates or absent energies.

    Native CREST/GOAT comments contain Hartree energies. Named ``E=``/``energy=``
    values and bare native numeric comments are accepted; other units are rejected.
    """
    frames: list[ConformerCandidate] = []
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
    with path.open(encoding="utf-8") as stream:
        while True:
            first = stream.readline()
            if not first:
                break
            if not first.strip():
                continue
            try:
                count = int(first.strip())
            except ValueError as exc:
                raise ValueError(f"Invalid XYZ atom count in {path}") from exc
            if count <= 0:
                raise ValueError("XYZ must contain at least one atom")
            comment = stream.readline()
            if not comment:
                raise ValueError("Incomplete XYZ comment")
            energy = 0.0
            if require_energy:
                if re.search(r"kcal|kJ|\beV\b", comment, re.IGNORECASE):
                    raise ValueError("Engine ensemble energies must be in Hartree")
                match = re.search(rf"\b(?:energy|E)\s*[:=]\s*({number})", comment, re.I)
                if match is None:
                    match = re.match(rf"\s*({number})(?:\s|$)", comment)
                if match is None:
                    raise ValueError(f"Missing engine energy in XYZ comment: {comment.strip()}")
                suffix = comment[match.end():].strip()
                unit = re.match(r"([A-Za-z][A-Za-z0-9^./-]*)(?:\s|$)", suffix)
                if unit and unit.group(1).lower() not in {"hartree", "hartrees", "eh", "au", "a.u."}:
                    raise ValueError(f"Unrecognized ensemble energy unit: {unit.group(1)}")
                energy = float(match.group(1).replace("D", "E").replace("d", "e"))
                if not math.isfinite(energy):
                    raise ValueError("Nonfinite engine energy")
            symbols, positions = [], []
            for _ in range(count):
                fields = stream.readline().split()
                if len(fields) != 4:
                    raise ValueError("Invalid or incomplete XYZ coordinates")
                xyz = [float(value) for value in fields[1:]]
                if not all(math.isfinite(value) for value in xyz):
                    raise ValueError("Nonfinite XYZ coordinates")
                symbols.append(fields[0])
                positions.append(xyz)
            frames.append(ConformerCandidate(
                conformer_id=f"{path.parent.name}:{len(frames)}",
                symbols=list(resolve_nuclear_identity(symbols).nuclides), coordinates=np.asarray(positions), energy=energy,
            ))
    if not frames:
        raise ValueError(f"Empty XYZ file: {path}")
    return frames


def _resolve_engine(name: str, explicit: str | None) -> str:
    candidate = explicit or resolve_executable(name, env_var=f"{name.upper()}_CMD")
    resolved = shutil.which(candidate)
    if resolved is None:
        raise FileNotFoundError(f"Required physical {name.upper()} executable is unavailable: {candidate}")
    return authorize_engine_execution(name, executable=Path(resolved).resolve(), cores=1).executable


def _normalize_ingress(symbols: list[str], coordinates: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    """Normalize a physical input to its mass-weighted, COM-centered Eckart frame."""
    masses = np.asarray([get_nuclide_mass(symbol) for symbol in symbols])
    aligned, rotation, _ = align_coordinates(coordinates, coordinates, masses=masses)
    com_residual = verify_com_residual(aligned, masses)
    reference = coordinates - np.average(coordinates, axis=0, weights=masses)
    angular_residual = verify_eckart_residual(reference, aligned, masses)
    return aligned, {
        "masses_u": masses.tolist(), "rotation_matrix": rotation.tolist(),
        "com_mass_residual_u_angstrom": com_residual,
        "eckart_residual_u_angstrom2": angular_residual,
    }


def _terminate_tree(proc: subprocess.Popen[Any]) -> None:
    """Terminate the worker and all known engine descendants on either OS family."""
    try:
        parent = psutil.Process(proc.pid)
        processes = parent.children(recursive=True) + [parent]
    except psutil.NoSuchProcess:
        proc.wait()
        return
    for process in reversed(processes):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            continue
    _, alive = psutil.wait_procs(processes, timeout=2.0)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            continue
    psutil.wait_procs(alive, timeout=2.0)
    proc.wait(timeout=5.0)


def _process_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


class TOPOSExecutionBroker:
    """Launch isolated workers, expose measured progress, and promote final data."""

    def __init__(self, scratch_root: str | Path | None = None, store_root: str | Path | None = None) -> None:
        artifact_root = get_artifact_dir() if scratch_root is None or store_root is None else None
        self.scratch_root = Path(scratch_root or os.environ.get("COCH_SCRATCH") or artifact_root / "Scratch").resolve()
        self.store_root = Path(store_root or os.environ.get("COCH_STORE_DIR") or artifact_root / "Processed").resolve()
        from cochem.core.context import assert_writable_path
        code_root = Path(__file__).resolve().parents[2]
        for runtime_path in (self.scratch_root, self.store_root):
            if runtime_path == code_root or code_root in runtime_path.parents:
                raise ValueError("TOPOS scratch and store paths must be outside the source checkout")
            assert_writable_path(runtime_path)
        if self.scratch_root == self.store_root:
            raise ValueError("TOPOS scratch and persistent store must be separate directories")
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.store_root.mkdir(parents=True, exist_ok=True)
        self.active_processes: dict[str, subprocess.Popen[Any]] = {}

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"topos_job_[0-9a-f]{32}", job_id):
            raise ValueError("Invalid TOPOS job identifier")
        return self.scratch_root / job_id

    def launch_search(self, config: TOPOSSearchConfig) -> str:
        for requested, actual in ((config.scratch_dir, self.scratch_root), (config.store_dir, self.store_root)):
            if requested and Path(requested).expanduser().resolve() != actual:
                raise ValueError("Search runtime paths must match the broker constructor paths")
        if not config.input_xyz_path:
            raise ValueError("A physical input XYZ file is required for conformer search")
        source = Path(config.input_xyz_path).expanduser().resolve(strict=True)
        original_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        seeds = _parse_xyz(source, require_energy=False)
        if len(seeds) != 1 or len(seeds[0].symbols) != config.atom_count:
            raise ValueError("Input must contain one XYZ frame matching atom_count")
        config = config.model_copy(deep=True)
        if config.protocol in ("CREST_GOAT", "CREST_NCI"):
            config.crest_binary = _resolve_engine("crest", config.crest_binary)
        if config.protocol in ("CREST_GOAT", "GOAT"):
            config.orca_binary = _resolve_engine("orca", config.orca_binary)
        total_cores = config.threads_per_engine * (2 if config.protocol == "CREST_GOAT" else 1)
        for engine, binary in (("crest", config.crest_binary), ("orca", config.orca_binary)):
            if binary is not None:
                authorize_engine_execution(engine, executable=binary, cores=total_cores)
        identity = resolve_nuclear_identity(seeds[0].symbols)
        coordinates, alignment = _normalize_ingress(seeds[0].symbols, seeds[0].coordinates)
        alignment["nuclear_identity"] = identity.metadata
        alignment["original_input_sha256"] = original_sha256
        job_id = f"topos_job_{uuid.uuid4().hex}"
        job_scratch = self._job_dir(job_id)
        job_scratch.mkdir()
        shutil.copy2(source, job_scratch / "input.original.xyz")
        if hashlib.sha256((job_scratch / "input.original.xyz").read_bytes()).hexdigest() != original_sha256:
            raise ValueError("Conformer nuclear input changed while preserving its immutable snapshot")
        with (job_scratch / "input.xyz").open("w", encoding="utf-8") as stream:
            stream.write(f"{config.atom_count}\nMass-weighted Eckart normalized input\n")
            for symbol, coordinate in zip(identity.elements, coordinates, strict=True):
                stream.write(symbol + " " + " ".join(f"{value:.17g}" for value in coordinate) + "\n")
        _write_json(job_scratch / "ingress.json", alignment)
        config.input_xyz_path = str(job_scratch / "input.xyz")
        config_path = job_scratch / "config.json"
        _write_json(config_path, config.model_dump())
        telemetry = {
            "job_id": job_id, "status": "RUNNING", "start_time": time.time(),
            "tier_id": config.tier_id, "protocol": config.protocol,
            "candidates_found": 0, "deduplicated_count": 0,
            "lowest_energy_hartree": None, "engines": {}, "error": None,
        }
        _write_json(job_scratch / "telemetry.json", telemetry)
        try:
            with (job_scratch / "worker.stdout").open("wb") as out, (job_scratch / "worker.stderr").open("wb") as err:
                process = subprocess.Popen(
                    [sys.executable, "-m", "cochem_base.topos_runner", "--worker", str(config_path)],
                    cwd=job_scratch, stdout=out, stderr=err, **_process_options(),
                )
            self.active_processes[job_id] = process
        except OSError as exc:
            telemetry.update(status="FAILED", error=str(exc))
            _write_json(job_scratch / "telemetry.json", telemetry)
            raise
        return job_id

    def poll_telemetry(self, job_id: str) -> dict[str, Any]:
        telemetry_path = self._job_dir(job_id) / "telemetry.json"
        data = _read_json(telemetry_path)
        process = self.active_processes.get(job_id)
        if process is not None and process.poll() is None and data["status"] == "COMPLETED":
            # The worker publishes its result before interpreter cleanup finishes.
            # Expose completion only when process evidence permits promotion.
            return {**data, "status": "RUNNING"}
        if process is not None and process.poll() is not None:
            if data["status"] == "RUNNING" or (process.returncode != 0 and data["status"] != "CANCELLED"):
                data.update(status="FAILED", error=data.get("error") or f"Worker exit code {process.returncode}")
                _write_json(telemetry_path, data)
        return data

    def cancel_search(self, job_id: str) -> bool:
        telemetry_path = self._job_dir(job_id) / "telemetry.json"
        data = _read_json(telemetry_path)
        if data["status"] != "RUNNING":
            return False
        process = self.active_processes.get(job_id)
        if process is None:
            raise RuntimeError("Cannot cancel a job without its owning process handle")
        _terminate_tree(process)
        data = _read_json(telemetry_path)
        data.update(status="CANCELLED", end_time=time.time())
        _write_json(telemetry_path, data)
        return True

    def promote_artifacts(self, job_id: str) -> dict[str, Path]:
        job_scratch = self._job_dir(job_id)
        data = self.poll_telemetry(job_id)
        process = self.active_processes.get(job_id)
        if data["status"] != "COMPLETED" or (process is not None and process.poll() != 0):
            raise RuntimeError("Only successfully completed physical searches can be promoted")
        ensemble = job_scratch / "conformer_ensemble.xyz"
        if hashlib.sha256(ensemble.read_bytes()).hexdigest() != data.get("ensemble_sha256"):
            raise ValueError("Completed ensemble changed after validation")
        _parse_xyz(ensemble, require_energy=True)
        target = self.store_root / job_id
        staging = self.store_root / f".{job_id}.{uuid.uuid4().hex}.tmp"
        with filelock.FileLock(str(target) + ".lock", timeout=10.0):
            if target.exists():
                raise FileExistsError(f"Job artifacts are already promoted: {target}")
            staging.mkdir()
            try:
                for name in ("conformer_ensemble.xyz", "telemetry.json", "provenance.jsonld"):
                    shutil.copy2(job_scratch / name, staging / name)
                os.replace(staging, target)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        return {"ensemble_xyz": target / "conformer_ensemble.xyz", "promoted_dir": target}


def _run_worker(config_path: Path) -> int:
    config = TOPOSSearchConfig.model_validate(_read_json(config_path))
    job = config_path.parent
    telemetry_path = job / "telemetry.json"
    data = _read_json(telemetry_path)
    processes: dict[str, subprocess.Popen[Any]] = {}
    commands: dict[str, list[str]] = {}
    ensembles: dict[str, Path] = {}
    started = time.monotonic()

    def interrupted(signum: int, frame: Any) -> None:
        raise InterruptedError(f"Search worker interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        with ExitStack() as streams:
            for engine in ("CREST", "GOAT"):
                if engine == "CREST" and config.protocol == "GOAT" or engine == "GOAT" and config.protocol == "CREST_NCI":
                    continue
                work = job / engine
                work.mkdir()
                shutil.copy2(config.input_xyz_path, work / "input.xyz")
                if engine == "CREST":
                    command = [str(config.crest_binary), "input.xyz", "--gfn2", "--nci", "--noreftopo", "--chrg", str(config.charge), "--uhf", str(config.multiplicity - 1), "-T", str(config.threads_per_engine)]
                    ensembles[engine] = work / "crest_conformers.xyz"
                else:
                    deck = f"! GOAT XTB2\n%pal nprocs {config.threads_per_engine} end\n* xyzfile {config.charge} {config.multiplicity} input.xyz\n"
                    (work / "search.inp").write_text(deck, encoding="utf-8")
                    command = [str(config.orca_binary), "search.inp"]
                    ensembles[engine] = work / "search.finalensemble.xyz"
                commands[engine] = command
                if not Path(command[0]).is_file():
                    raise FileNotFoundError(f"Required {engine} executable is unavailable: {command[0]}")
                concurrent_engines = 2 if config.protocol == "CREST_GOAT" else 1
                authority = authorize_engine_execution(
                    "crest" if engine == "CREST" else "orca", command=command,
                    cores=config.threads_per_engine * concurrent_engines,
                )
                engine_index = len(processes)
                pins = authority.cpu_affinity[
                    engine_index * config.threads_per_engine:(engine_index + 1) * config.threads_per_engine
                ]
                if len(pins) != config.threads_per_engine:
                    raise RuntimeError("Refresh Stage 0 CPU/NUMA evidence before conformer execution")
                out = streams.enter_context((work / "stdout.log").open("wb"))
                err = streams.enter_context((work / "stderr.log").open("wb"))
                engine_env = dict(os.environ, OMP_NUM_THREADS=str(config.threads_per_engine), MKL_NUM_THREADS=str(config.threads_per_engine))
                from cochem_base.core_engine.engine_environment import engine_runtime_environment
                engine_env = engine_runtime_environment(
                    "crest" if engine == "CREST" else "orca", engine_env, executable=command[0],
                )
                if engine != "CREST":
                    # ORCA GOAT's %pal allocates ranks; BLAS/OpenMP remain serial per rank.
                    engine_env = sanitize_mpi_environment(engine_env, force_single_thread=True)
                engine_env["OMP_PROC_BIND"] = "true"
                engine_env["OMP_PLACES"] = ",".join("{" + str(cpu) + "}" for cpu in pins)
                processes[engine] = subprocess.Popen(command, cwd=work, stdout=out, stderr=err, env=engine_env, **_process_options())
                child = psutil.Process(processes[engine].pid)
                if hasattr(child, "cpu_affinity"):
                    child.cpu_affinity(list(pins))
                else:
                    raise RuntimeError("This OS cannot enforce the audited process CPU binding")
            while True:
                data["engines"] = {name: {"pid": proc.pid, "returncode": proc.poll()} for name, proc in processes.items()}
                _write_json(telemetry_path, data)
                failed = [name for name, proc in processes.items() if proc.poll() not in (None, 0)]
                if failed:
                    raise RuntimeError(f"Physical search failed: {', '.join(failed)}; see engine stderr.log")
                if all(proc.poll() is not None for proc in processes.values()):
                    break
                if time.monotonic() - started > config.max_hours * 3600:
                    raise TimeoutError("Physical conformer search exceeded configured wall time")
                time.sleep(0.1)
        seed = _parse_xyz(Path(config.input_xyz_path), require_energy=False)[0]
        original = job / "input.original.xyz"
        ingress = _read_json(job / "ingress.json")
        if hashlib.sha256(original.read_bytes()).hexdigest() != ingress["original_input_sha256"]:
            raise ValueError("Conformer nuclear input snapshot integrity verification failed")
        identity = resolve_nuclear_identity(_parse_xyz(original, require_energy=False)[0].symbols)
        if identity.metadata != ingress["nuclear_identity"]:
            raise ValueError("Conformer isotope assignments contradict the retained input provenance")
        if tuple(seed.symbols) != identity.elements:
            raise ValueError("Conformer electronic input no longer matches its retained nuclear assignments")
        candidates = []
        for name, path in ensembles.items():
            parsed = _parse_xyz(path, require_energy=True)
            if any(tuple(frame.symbols) != identity.elements for frame in parsed):
                raise ValueError(f"{name} ensemble changed the ordered electronic atom identities")
            for index, candidate in enumerate(parsed):
                candidate.symbols = list(identity.nuclides)
                candidate.coordinates, alignment = _normalize_ingress(candidate.symbols, candidate.coordinates)
                archive = append_scientific_result(
                    f"{data['job_id']}_{name}", candidate.symbols, candidate.coordinates, candidate.energy,
                    metadata={"engine": name, "ensemble_frame": index,
                              "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "alignment": alignment, "nuclear_identity": identity.metadata, "scope": "conformer screening"},
                )
                data["scientific_telemetry_archive"] = str(archive)
            candidates.extend(parsed)
        unique = ConformerDeduplicator().deduplicate(candidates)
        output = job / "conformer_ensemble.xyz"
        with output.open("w", encoding="utf-8") as stream:
            for candidate in unique:
                stream.write(f"{len(candidate.symbols)}\nE={candidate.energy:.16g} Hartree source={candidate.conformer_id}\n")
                for symbol, coordinate in zip(candidate.symbols, candidate.coordinates, strict=True):
                    stream.write(symbol + " " + " ".join(f"{value:.15g}" for value in coordinate) + "\n")
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        provenance = {
            "@context": {"prov": "http://www.w3.org/ns/prov#", "cochem": "urn:cochem:"},
            "@type": "prov:Activity", "@id": f"urn:cochem:{data['job_id']}",
            "prov:used": [{"@id": str(path), "cochem:sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in [original, Path(config.input_xyz_path), *ensembles.values()]],
            "cochem:commands": commands, "cochem:energyUnit": "hartree",
            "cochem:ingress": _read_json(job / "ingress.json"),
            "cochem:ensembleSha256": digest,
            "cochem:scope": "conformer screening; production electronic relaxation remains required",
        }
        _write_json(job / "provenance.jsonld", provenance)
        data.update(status="COMPLETED", candidates_found=len(candidates), deduplicated_count=len(unique), lowest_energy_hartree=min(conf.energy for conf in unique), ensemble_sha256=digest, end_time=time.time())
        _write_json(telemetry_path, data)
        return 0
    except Exception as exc:
        data.update(status="FAILED", error=f"{type(exc).__name__}: {exc}", end_time=time.time())
        _write_json(telemetry_path, data)
        return 1
    finally:
        for process in processes.values():
            if process.poll() is None:
                _terminate_tree(process)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    raise SystemExit(_run_worker(parser.parse_args().worker.resolve()))
