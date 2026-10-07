"""Execute the proposal's MACE-OFF24m ↔ g-xTB screening fallback with evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Sequence
import uuid

import numpy as np

from cochem_base.core_engine.execution_authority import authorize_engine_execution
from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
from cochem_base.core_engine.scientific_telemetry import append_scientific_result
from cochem_base.physics.isotopes import parse_nuclide_token
from cochem_base.physics.nuclide_resolver import get_element
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass

# Local reproducibility digest of the official pinned v0.2 release checkpoint;
# this is not represented as an upstream cryptographic signature.
OFF24_MEDIUM_SHA256 = "e5ccf5837f685899811a68754e7c994393bfd1a81720393b03c643b46c70bc69"


class ScreeningBackendUnavailable(RuntimeError):
    """An audited backend or the required checkpoint is absent."""


class UnsupportedScreeningDomain(RuntimeError):
    """The requested model cannot represent this chemical state."""


class ScreeningEngineFailure(RuntimeError):
    """A real engine reported unsuccessful execution or incomplete evidence."""


class ScreeningFallbackExhausted(RuntimeError):
    def __init__(self, attempts: list[dict[str, Any]], evidence_path: Path):
        super().__init__(f"Both screening backends failed; evidence: {evidence_path}")
        self.attempts = attempts
        self.evidence_path = evidence_path


def _gxtb_gradient(path: Path, atom_count: int) -> np.ndarray:
    lines = path.read_text(encoding="utf-8").splitlines()
    cycles = [index for index, line in enumerate(lines) if "cycle =" in line.lower()]
    if not cycles:
        raise ScreeningEngineFailure("g-xTB gradient lacks a physical cycle header")
    rows = lines[cycles[-1] + 1 + atom_count:cycles[-1] + 1 + 2 * atom_count]
    try:
        gradient = np.asarray([[float(token.replace("D", "E").replace("d", "e")) for token in row.split()] for row in rows])
    except ValueError as exc:
        raise ScreeningEngineFailure("Unreadable g-xTB gradient") from exc
    if gradient.shape != (atom_count, 3) or not np.isfinite(gradient).all():
        raise ScreeningEngineFailure("Incomplete/nonfinite g-xTB gradient")
    return gradient


def execute_screening_with_fallback(
    elements: Sequence[str], coordinates_angstrom: Any, *,
    primary: str = "MACE-OFF24m", charge: int = 0, multiplicity: int = 1,
    checkpoint: str | Path | None = None, registry_path: str | Path | None = None,
    workdir: str | Path, cores: int = 1, timeout_seconds: float = 180,
) -> dict[str, Any]:
    """Run energy/gradient screening, retrying only typed domain/backend failures.

    Registry ``mace`` records the isolated ML Python interpreter and its digest;
    ``gxtb`` records the actual g-xTB executable. Results remain screening data,
    requiring ab initio relaxation before Product A/C production assignment.
    Neither estimates nor an alternate checkpoint are substituted for OFF24m.
    """
    from cochem_base.config_loader import resolve_config_path
    from cochem_base.cochem_core_registry_schema import CoChemSystemConfig
    from cochem.core.context import assert_writable_path
    from filelock import FileLock

    selected = {"mace-off24m": "mace", "mace-off24-medium": "mace", "g-xtb": "gxtb", "gxtb": "gxtb"}.get(primary.lower())
    if selected is None:
        raise ValueError("Primary screening backend must be MACE-OFF24m or g-xTB")
    symbols = list(elements)
    electronic_symbols = [parse_nuclide_token(symbol)[0] for symbol in symbols]
    for symbol in symbols:
        get_nuclide_mass(symbol)
    coordinates = np.asarray(coordinates_angstrom, dtype=float)
    if not symbols or coordinates.shape != (len(symbols), 3) or not np.isfinite(coordinates).all():
        raise ValueError("Screening requires finite N x 3 coordinates")
    if isinstance(charge, bool) or not isinstance(charge, int) or isinstance(multiplicity, bool) or not isinstance(multiplicity, int):
        raise ValueError("Charge and multiplicity must be integers")
    electrons = sum(int(get_element(symbol).atomic_number) for symbol in electronic_symbols) - charge
    if electrons < 0 or multiplicity < 1 or multiplicity > electrons + 1 or (electrons + multiplicity) % 2 != 1:
        raise ValueError("Charge/multiplicity contradict the physical electron count")
    if not np.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Execution timeout must be finite and positive")
    registry = resolve_config_path(registry_path)
    with FileLock(str(registry) + ".lock", timeout=10):
        config = CoChemSystemConfig.model_validate_json(registry.read_text(encoding="utf-8"))
    if not config.verify_checksum():
        raise ValueError("Missing or invalid Golden Registry checksum")
    engines = config.model_dump(mode="json")["engines"]
    root = Path(workdir).expanduser().resolve()
    assert_writable_path(root)
    root.mkdir(parents=True, exist_ok=True)
    job_id = f"screening_{uuid.uuid4().hex}"
    job = root / job_id
    job.mkdir()
    molecular_input = {"elements": symbols, "electronic_elements": electronic_symbols,
                       "coordinates_angstrom": coordinates.tolist(), "charge": charge,
                       "multiplicity": multiplicity}
    input_text = json.dumps(molecular_input, sort_keys=True, allow_nan=False)
    (job / "molecular_input.json").write_text(input_text, encoding="utf-8")
    input_digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    evidence = job / "attempts.json"
    attempts: list[dict[str, Any]] = []
    for backend in (selected, "gxtb" if selected == "mace" else "mace"):
        attempt: dict[str, Any] = {"backend": backend, "status": "STARTED", "input_sha256": input_digest}
        attempts.append(attempt)
        started = time.monotonic()
        directory = job / backend
        directory.mkdir()
        try:
            record = engines.get(backend, {})
            if not record or record.get("status") not in {"found", "ready"} or not record.get("path") or not Path(record["path"]).is_file():
                raise ScreeningBackendUnavailable(f"Audited {backend} executable is unavailable")
            authority = authorize_engine_execution(backend, registry_path=registry, cores=cores)
            attempt.update(binary_path=authority.executable, binary_sha256=authority.binary_sha256,
                           cpu_affinity=list(authority.cpu_affinity), registry_path=str(registry))
            environment = dict(os.environ, OMP_NUM_THREADS=str(cores), MKL_NUM_THREADS=str(cores), OPENBLAS_NUM_THREADS=str(cores))
            if backend == "mace":
                silo_config = Path(authority.executable).parent.parent / "pyvenv.cfg"
                if not silo_config.is_file() or not re.search(
                    r"(?im)^include-system-site-packages\s*=\s*false\s*$", silo_config.read_text(encoding="utf-8")
                ):
                    raise ScreeningBackendUnavailable("MACE requires an isolated virtual environment without system-site packages")
                if charge != 0 or multiplicity != 1:
                    raise UnsupportedScreeningDomain("MACE-OFF24 requires neutral closed-shell molecules")
                model = Path(checkpoint).expanduser().resolve() if checkpoint is not None else None
                if model is None or not model.is_file():
                    raise ScreeningBackendUnavailable("MACE-OFF24 medium checkpoint is absent")
                with model.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest != OFF24_MEDIUM_SHA256:
                    raise ValueError("Checkpoint digest does not identify the pinned official MACE-OFF24 medium model")
                attempt.update(checkpoint_path=str(model), checkpoint_sha256=digest, backend_kind="isolated_python")
                request = directory / "request.json"
                request.write_text(json.dumps({"elements": electronic_symbols, "coordinates_angstrom": coordinates.tolist(),
                    "checkpoint": str(model), "checkpoint_sha256": digest, "cores": cores}), encoding="utf-8")
                output = directory / "result.json"
                command = authority.command(["-I", str(Path(__file__).with_name("mlff_worker.py")), str(request), str(output)])
            else:
                source = directory / "input.xyz"
                source.write_text(f"{len(symbols)}\nPhysical screening input\n" + "\n".join(
                    symbol + " " + " ".join(f"{number:.17g}" for number in coordinate)
                    for symbol, coordinate in zip(electronic_symbols, coordinates, strict=True)) + "\n", encoding="utf-8")
                command = authority.command([source.name, "--gxtb", "--grad", "--chrg", str(charge), "--uhf", str(multiplicity - 1)])
            attempt["command"] = command
            process = safe_subprocess_run(command, cwd=directory, env=environment, timeout=timeout_seconds,
                capture_output=True, text=True, check=False, required_disk_gb=0.1,
                cpu_affinity=list(authority.cpu_affinity) or None, load_full_stdout=True)
            (directory / "stdout.log").write_text(process.stdout or "", encoding="utf-8")
            (directory / "stderr.log").write_text(process.stderr or "", encoding="utf-8")
            attempt["returncode"] = process.returncode
            if backend == "mace":
                if not output.is_file():
                    raise RuntimeError("MACE worker failed without typed engine evidence; inspect retained traceback")
                result = json.loads(output.read_text(encoding="utf-8"))
                if result.get("status") == "UNSUPPORTED_DOMAIN":
                    raise UnsupportedScreeningDomain(result["error"])
                if result.get("status") == "UNAVAILABLE":
                    raise ScreeningBackendUnavailable(result["error"])
                if result.get("status") == "ENGINE_FAILURE":
                    raise ScreeningEngineFailure(result["error"])
                if process.returncode != 0 or result.get("status") != "SUCCESS":
                    raise RuntimeError("MACE worker exit contradicts its result evidence")
                energy = float(result["energy_hartree"])
                gradient = np.asarray(result["gradient_hartree_per_bohr"])
                attempt["versions"] = result["versions"]
            else:
                text = (process.stdout or "") + (process.stderr or "")
                matches = re.findall(r"TOTAL ENERGY\s+([-+\d.EeDd]+)", text)
                if process.returncode != 0 or not matches or "g-xTB" not in text or "normal termination of xtb" not in text.lower():
                    raise ScreeningEngineFailure("g-xTB lacks successful method/termination/energy evidence")
                energy = float(matches[-1].replace("D", "E"))
                if not (directory / "gradient").is_file():
                    raise ScreeningEngineFailure("g-xTB did not produce its analytic gradient")
                gradient = _gxtb_gradient(directory / "gradient", len(symbols))
            if not np.isfinite(energy) or gradient.shape != coordinates.shape or not np.isfinite(gradient).all():
                raise ScreeningEngineFailure("Engine returned incomplete/nonfinite energy or gradient")
            attempt.update(status="SUCCESS", elapsed_seconds=time.monotonic() - started)
            evidence.write_text(json.dumps(attempts, indent=2, allow_nan=False), encoding="utf-8")
            archive = append_scientific_result(job_id, symbols, coordinates, energy, gradient,
                metadata={"attempts": attempts, "scope": "screening only; ab initio relaxation required"})
            return {"status": "SCREENING_VERIFIED", "backend": backend, "energy_hartree": energy,
                "gradient_hartree_per_bohr": gradient.tolist(), "attempts": attempts,
                "evidence_path": str(evidence), "telemetry_archive": str(archive), "job_id": job_id}
        except (ScreeningBackendUnavailable, UnsupportedScreeningDomain, ScreeningEngineFailure) as exc:
            attempt.update(status="REJECTED", error_type=type(exc).__name__, error=str(exc),
                           elapsed_seconds=time.monotonic() - started)
            evidence.write_text(json.dumps(attempts, indent=2, allow_nan=False), encoding="utf-8")
        except Exception as exc:
            attempt.update(status="ABORTED", error_type=type(exc).__name__, error=str(exc),
                           elapsed_seconds=time.monotonic() - started)
            evidence.write_text(json.dumps(attempts, indent=2, allow_nan=False), encoding="utf-8")
            raise
    raise ScreeningFallbackExhausted(attempts, evidence)
