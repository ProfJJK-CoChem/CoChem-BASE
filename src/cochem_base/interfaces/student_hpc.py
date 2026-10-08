"""No-code student requests on real connected Slurm/OpenPBS allocations.

The interface host stages data and calls scheduler commands. Scientific adapters
run only after the controller confirms this job, its owner and its compute node,
followed by a fresh eleven-phase Stage 0 audit. There is no local fallback.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid

from .student_request import canonical_json, safe_relative_path, strict_json

SCHEMA = "cochem.student-hpc/1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
JOB_IDS = {"slurm": re.compile(r"[1-9][0-9]*"), "pbs": re.compile(r"[1-9][0-9]*(?:\.[A-Za-z0-9_.-]+)?")}
COMMANDS = {"slurm": ("sbatch", "squeue", "scontrol", "scancel"), "pbs": ("qsub", "qstat", "qdel")}
MAX_FILES, MAX_BYTES = 4096, 512 * 1024 * 1024


class StudentHpcError(RuntimeError):
    """Scheduler access, admission or result-integrity failure."""


def _write(path: Path, data: dict) -> None:
    from cochem_base.core.cochem_core_registry_manager import atomic_write_json
    atomic_write_json(path, data)


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _external(path: Path) -> Path:
    from cochem_base.calc.calculation_service import _external_run_path
    return _external_run_path(path)


def validate_resources(resources: dict) -> dict:
    from cochem_base.calc.slurm_submission import validate_slurm_walltime
    required = {"scheduler", "queue", "job_name", "cores", "memory_mb", "walltime"}
    if not isinstance(resources, dict) or not required.issubset(resources) or set(resources) - required - {"email", "account"}:
        raise ValueError("HPC requests require complete typed single-node scheduler resources")
    result = deepcopy(resources)
    if result["scheduler"] not in {"auto", "slurm", "pbs"}:
        raise ValueError("Select a configured Slurm or OpenPBS scheduler")
    for field in ("queue", "job_name", "account"):
        if field in result and (not isinstance(result[field], str) or not IDENTIFIER.fullmatch(result[field])):
            raise ValueError("HPC " + field + " must be a single scheduler identifier")
    if type(result["cores"]) is not int or not 1 <= result["cores"] <= 4096:
        raise ValueError("Request a positive bounded single-node CPU allocation")
    if type(result["memory_mb"]) is not int or not 256 <= result["memory_mb"] <= 4 * 1024 * 1024:
        raise ValueError("Request explicit bounded total HPC memory in MB")
    if int(result["memory_mb"] * .75) // result["cores"] < 1:
        raise ValueError("HPC memory must support a positive per-process scientific budget")
    result["walltime"] = validate_slurm_walltime(result["walltime"])
    if result.get("email") is not None and (not isinstance(result["email"], str) or not re.fullmatch(r"[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+", result["email"])):
        raise ValueError("Scheduler notifications need a single valid email address")
    return result


def _seconds(walltime: str) -> int:
    days, clock = (walltime.split("-", 1) if "-" in walltime else ("0", walltime))
    hours, minutes, seconds = map(int, clock.split(":"))
    return int(days) * 86400 + hours * 3600 + minutes * 60 + seconds


def validate_portable_calculation(calculation: dict, *, resources: dict,
                                  scientific_inputs: dict | None = None,
                                  t9_request: dict | None = None) -> dict:
    """Validate scientific data without authorizing a login-host interpreter.

    HPC resources are independently admitted: hosted Actions' two-core/time
    limits do not apply to a measured cluster allocation. Full native reference
    and Hessian acceptance still happens inside that allocation.
    """
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry_identity
    from .scientific_jobs import calculation_capability, validate_job_configuration
    if not isinstance(calculation, dict) or not {"geometry", "engine", "charge", "multiplicity", "method", "is_opt", "is_freq"}.issubset(calculation):
        raise ValueError("HPC native calculations require their explicit geometry, method, state and operation")
    raw = deepcopy(calculation)
    if any(raw.get(field) is not None for field in ("hessian_file", "r2_reference_manifest", "t9_fallback")):
        raise ValueError("HPC scientific dependencies require portable sealed data; login-host file/interpreter paths are forbidden")
    if scientific_inputs is not None:
        if raw["engine"] != "orca" or not isinstance(scientific_inputs, dict):
            raise ValueError("Portable READ/R2 inputs require the native ORCA adapter")
        kind, entrypoint = scientific_inputs.get("kind"), scientific_inputs.get("entrypoint")
        safe_relative_path(entrypoint)
        if kind == "r2_reference" and raw.get("recipe") == "R2" and raw.get("initial_hessian", "XTB2").upper() != "READ":
            raw["r2_reference_manifest"] = "scientific-inputs/" + entrypoint
        elif kind == "read_hessian" and raw.get("initial_hessian", "XTB2").upper() == "READ" and raw.get("recipe") != "R2":
            raw["hessian_file"] = "scientific-inputs/" + entrypoint
        else:
            raise ValueError("The scientific bundle does not match the selected READ or R2 operation")
    elif raw.get("recipe") == "R2" or raw.get("initial_hessian", "XTB2").upper() == "READ":
        raise ValueError("READ/R2 requires its uploaded original scientific evidence bundle")
    model = CalculationMatrixConfig.model_validate_json(canonical_json(raw), strict=True)
    validate_job_configuration(model)
    if calculation_capability(model).adapter_status != "connected":
        raise ValueError("This native calculation has no connected execution adapter")
    if model.timeout_seconds > _seconds(resources["walltime"]):
        raise ValueError("The native calculation timeout exceeds the scheduler walltime")
    if model.engine == "orca" and model.multiplicity > 1 and t9_request is None:
        raise ValueError("Open-shell ORCA requires an explicit portable T9 active space before submission")
    if t9_request is not None:
        permitted = {"pyscf_version", "method", "basis", "active_electrons", "active_orbitals", "active_space_rationale", "threads", "memory_mb", "timeout_seconds", "max_cycle"}
        if model.engine != "orca" or not isinstance(t9_request, dict) or set(t9_request) != permitted:
            raise ValueError("T9 needs a complete portable ORCA recovery configuration without interpreter paths")
        orbitals = t9_request["active_orbitals"]
        if (t9_request["method"] not in {"CASSCF", "NEVPT2"}
                or type(t9_request["active_electrons"]) is not int or not isinstance(orbitals, list) or not orbitals
                or len(orbitals) > 4096 or any(type(index) is not int or not 0 <= index <= 1000000 for index in orbitals)
                or len(set(orbitals)) != len(orbitals) or not 1 <= t9_request["active_electrons"] <= 2 * len(orbitals)
                or type(t9_request["threads"]) is not int or not 1 <= t9_request["threads"] <= resources["cores"]
                or type(t9_request["memory_mb"]) is not int or not 64 <= t9_request["memory_mb"] <= int(resources["memory_mb"] * .75)
                or type(t9_request["max_cycle"]) is not int or not 1 <= t9_request["max_cycle"] <= 1000
                or type(t9_request["timeout_seconds"]) not in (int, float) or not math.isfinite(t9_request["timeout_seconds"])
                or not 0 < t9_request["timeout_seconds"] or t9_request["timeout_seconds"] + model.timeout_seconds > _seconds(resources["walltime"])):
            raise ValueError("T9 active space or resource budget exceeds the admitted compute allocation")
        for field, maximum in (("pyscf_version", 100), ("basis", 200), ("active_space_rationale", 4000)):
            value = t9_request[field]
            if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value or (field != "active_space_rationale" and any(char in value for char in "\n\r")):
                raise ValueError("T9 requires a bounded explicit version, basis and scientific active-space rationale")
        from cochem_base.physics.nuclide_resolver import get_element
        identity = parse_run_geometry_identity(model.geometry)
        total = sum(int(get_element(symbol).atomic_number) for symbol in identity.elements) - model.charge
        active, spin = t9_request["active_electrons"], model.multiplicity - 1
        if (total < active or (total - active) % 2 or (active - spin) % 2 or spin > active or (active + spin) // 2 > len(orbitals)):
            raise ValueError("The T9 active space cannot represent the explicit molecular electronic state")
    return model.model_dump(mode="json")


def _source_inventory() -> dict:
    package = Path(__file__).resolve().parents[1]
    import cochem
    from scripts import manage_modules
    roots = [package, Path(cochem.__file__).resolve().parent, Path(manage_modules.__file__).resolve().parent]
    files = {str(path): _hash(path) for root in roots for path in sorted(root.rglob("*"))
             if path.is_file() and not path.is_symlink() and path.suffix in {".py", ".json", ".yaml", ".toml", ".csv"}}
    # Preserve actual import authority when the interface was opened in a
    # source checkout but the scheduler worker changes to its external job
    # directory. Paths originate from already imported reviewed packages,
    # never from uploaded requests or inherited student PYTHONPATH overrides.
    search_paths = list(dict.fromkeys([str(roots[1].parent), str(package.parent), str(roots[2].parent)]))
    return {"python": str(Path(sys.executable).absolute()), "python_sha256": _hash(Path(sys.executable)),
            "module_search_paths": search_paths, "files": files}


def _verify_source(source: dict) -> None:
    if source != _source_inventory():
        raise StudentHpcError("BASE execution source/interpreter changed while this job was queued; refresh and resubmit")


def render_batch_script(package: Path, scheduler: str, resources: dict, *, request_sha256: str) -> str:
    """Render only the reviewed worker entry point, never uploaded code/commands."""
    resources = validate_resources(resources)
    if not isinstance(request_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
        raise ValueError("The controller-spooled worker script requires the original request SHA-256")
    if scheduler not in COMMANDS:
        raise ValueError("Unsupported HPC scheduler")
    package = package.resolve()
    if any(character in str(package) for character in "\n\r\0"):
        raise ValueError("HPC package path must occupy one line")
    lines = ["#!/bin/bash"]
    if scheduler == "slurm":
        lines += ["#SBATCH --nodes=1", "#SBATCH --ntasks=1", "#SBATCH --cpus-per-task=" + str(resources["cores"]),
                  "#SBATCH --mem=" + str(resources["memory_mb"]) + "M", "#SBATCH --time=" + resources["walltime"],
                  "#SBATCH --partition=" + resources["queue"], "#SBATCH --job-name=" + resources["job_name"],
                  "#SBATCH --output=" + shlex.quote(str(package / "scheduler-%j.stdout.log").replace("%", "%%").replace("%%j", "%j")),
                  "#SBATCH --error=" + shlex.quote(str(package / "scheduler-%j.stderr.log").replace("%", "%%").replace("%%j", "%j"))]
        if resources.get("account"):
            lines.append("#SBATCH --account=" + resources["account"])
        if resources.get("email"):
            lines += ["#SBATCH --mail-user=" + resources["email"], "#SBATCH --mail-type=END,FAIL"]
    else:
        hours = _seconds(resources["walltime"]) // 3600
        rest = _seconds(resources["walltime"]) % 3600
        lines += ["#PBS -N " + resources["job_name"], "#PBS -q " + resources["queue"],
                  f"#PBS -l select=1:ncpus={resources['cores']}:mem={resources['memory_mb']}mb",
                  f"#PBS -l walltime={hours:02}:{rest//60:02}:{rest%60:02}",
                  "#PBS -o " + shlex.quote(str(package / "scheduler.stdout.log")),
                  "#PBS -e " + shlex.quote(str(package / "scheduler.stderr.log"))]
        if resources.get("account"):
            lines.append("#PBS -A " + resources["account"])
        if resources.get("email"):
            lines += ["#PBS -M " + resources["email"], "#PBS -m ae"]
    lines += ["set -euo pipefail", "unset PYTHONHOME", "export PYTHONPATH=" + shlex.quote(os.pathsep.join(_source_inventory()["module_search_paths"])),
              "cd " + shlex.quote(str(package)),
              shlex.join([sys.executable, "-m", "cochem_base.interfaces.student_hpc", "--execute", str(package),
                          "--request-sha256", request_sha256])]
    return "\n".join(lines) + "\n"


def _command(name: str, arguments: list[str], *, cwd: Path | None = None) -> str:
    executable = shutil.which(name)
    if not executable:
        raise StudentHpcError("Required scheduler command is unavailable: " + name)
    completed = subprocess.run([executable, *arguments], cwd=cwd, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, check=False, timeout=30)
    if completed.returncode:
        raise StudentHpcError(name + " failed with exit " + str(completed.returncode) + ": " + completed.stderr.strip()[:1000])
    if len(completed.stdout.encode("utf-8")) > 4 * 1024 * 1024:
        raise StudentHpcError("Scheduler response exceeds the bounded protocol size")
    return completed.stdout


def _load_package(package: Path, *, integrity: str) -> dict:
    package = _external(package).resolve(strict=True)
    manifest_path = package / "request.json"
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 4 * 1024 * 1024:
        raise StudentHpcError("HPC request cannot be a link")
    request = strict_json(manifest_path.read_bytes())
    if request.get("schema_version") != SCHEMA or _hash(manifest_path) != integrity:
        raise StudentHpcError("HPC request identity or source hash changed")
    if (str(uuid.UUID(request.get("request_id", ""))) != package.name
            or request.get("scheduler") not in COMMANDS or request.get("resources") != validate_resources(request["resources"])):
        raise StudentHpcError("HPC staging identity differs from its original request and resources")
    inventory = request.get("files")
    if not isinstance(inventory, dict) or len(inventory) > MAX_FILES:
        raise StudentHpcError("HPC inputs require their exact bounded file inventory")
    total = 0
    for name, identity in inventory.items():
        path = package / safe_relative_path(name)
        if (path.is_symlink() or not path.is_file() or any(parent.is_symlink() for parent in path.parents if parent != package and parent.is_relative_to(package))
                or not path.resolve(strict=True).is_relative_to(package) or identity != {"sha256": _hash(path), "size_bytes": path.stat().st_size}):
            raise StudentHpcError("HPC source input changed: " + name)
        total += path.stat().st_size
        if total > MAX_BYTES:
            raise StudentHpcError("HPC source inventory exceeds the admitted bounded bytes")
    _verify_source(request["source"])
    return request


class StudentHpcClient:
    """Connected cluster login/shared-filesystem scheduler client."""

    def __init__(self, *, artifact_dir: Path, module_root: Path | None = None, registry_path: Path | None = None):
        self.artifact_dir = _external(Path(artifact_dir))
        self.jobs = self.artifact_dir / "StudentHpc"
        self.module_root = Path(module_root).resolve() if module_root else self.artifact_dir / "Modules"
        self.registry_path = registry_path

    def preflight(self) -> dict:
        from cochem_base.core.cochem_core_registry_manager import RegistryError
        try:
            if os.name != "posix":
                raise StudentHpcError("Use a connected Linux cluster interface for Slurm/OpenPBS; no local fallback is performed")
            from cochem_base.config_loader import resolve_config_path
            from cochem_base.core.cochem_core_registry_manager import load_system_config
            registry = load_system_config(resolve_config_path(self.registry_path))
            scheduler = registry.hpc.scheduler.lower()
            if registry.stage0 is None or scheduler not in COMMANDS:
                raise StudentHpcError("Complete BASE setup on a connected Slurm/OpenPBS login host before selecting HPC")
            missing = [name for name in COMMANDS[scheduler] if shutil.which(name) is None]
            if missing:
                raise StudentHpcError("Configured scheduler access is unavailable (" + ", ".join(missing) + "); no interface-host calculation will run")
            if scheduler == "slurm":
                if not re.search(r"\bis UP\b", _command("scontrol", ["ping"])):
                    raise StudentHpcError("The Slurm controller is unavailable; no calculation is submitted")
            else:
                queues = strict_json(_command("qstat", ["-Q", "-F", "json"]).encode()).get("Queue", {})
                if not isinstance(queues, dict) or not queues:
                    raise StudentHpcError("OpenPBS requires an accessible JSON controller and configured queues")
            return {"ready": True, "scheduler": scheduler, "reason": "Connected single-node scheduler route; chemistry requires a measured compute allocation"}
        except (ValueError, OSError, RegistryError, StudentHpcError) as error:
            return {"ready": False, "scheduler": None, "reason": str(error)}

    def submit(self, calculation: dict | None, *, provider: dict | None = None, xyz_files: dict[str, str | bytes] | None = None,
               resources: dict, native_search: dict | None = None, ingestion_inputs: dict | None = None,
               periodic_inputs: dict | None = None, scientific_inputs: dict | None = None,
               t9_request: dict | None = None) -> dict:
        ready = self.preflight()
        if not ready["ready"]:
            raise StudentHpcError(ready["reason"])
        resources = validate_resources(resources)
        scheduler = ready["scheduler"]
        if resources["scheduler"] not in {"auto", scheduler}:
            raise StudentHpcError("Selected scheduler differs from the audited connected cluster")
        resources["scheduler"] = scheduler
        if sum(item is not None for item in (calculation, provider, native_search)) != 1:
            raise ValueError("Select exactly one native calculation, scientific provider or physical conformer search")
        if ingestion_inputs is not None and periodic_inputs is not None:
            raise ValueError("Select a molecular original or periodic original, not both")
        if calculation is None and (scientific_inputs is not None or t9_request is not None):
            raise ValueError("READ/R2/T9 portable inputs belong to an explicit native calculation")
        input_files = {}
        for name, contents in (xyz_files or {}).items():
            path = safe_relative_path(name)
            if not path.parts or path.parts[0] != "inputs":
                raise ValueError("Uploaded HPC data must remain under inputs/")
            if not isinstance(contents, (str, bytes)):
                raise ValueError("Upload unchanged input bytes or XYZ text")
            input_files[name] = contents.encode("utf-8") if isinstance(contents, str) else contents
        if len(input_files) > 64 or sum(map(len, input_files.values())) > MAX_BYTES:
            raise ValueError("HPC input data exceeds its bounded inventory")
        calculation = deepcopy(calculation)
        provider = deepcopy(provider)
        if provider is not None:
            from .student_research import validate_provider_request, validate_provider_resources
            provider = validate_provider_request(provider, {name: hashlib.sha256(contents).hexdigest() for name, contents in input_files.items()})
            validate_provider_resources(provider, {**resources, "memory_mb": int(resources["memory_mb"] * .75),
                                                  "budget_seconds": _seconds(resources["walltime"])})
            from scripts.manage_modules import DEFAULT_MANIFEST, load_manifest, verify_installation
            from .student_research import required_provider_modules
            catalog = load_manifest(DEFAULT_MANIFEST)
            provider_receipts = {}
            for name in required_provider_modules(provider):
                receipt = verify_installation(name, catalog["modules"][name], self.module_root)
                provider_receipts[name] = {"revision": receipt["revision"],
                    "receipt_sha256": _hash(self.module_root / name / "installation.json")}
        else:
            provider_receipts = {}
        if native_search is not None and periodic_inputs is not None:
            raise ValueError("Physical molecular conformer search cannot accept periodic input data")
        if calculation is not None:
            if periodic_inputs is not None:
                if calculation.get("engine") != "qe":
                    raise ValueError("Periodic PAW inputs require the native QE calculation adapter")
                calculation["periodic"]["pseudopotentials"] = {element: {"path": "pseudopotentials/" + element + ".UPF", "sha256": entry["sha256"]}
                                                               for element, entry in periodic_inputs["pseudopotentials"].items()}
            calculation = validate_portable_calculation(calculation, resources=resources,
                scientific_inputs=scientific_inputs, t9_request=t9_request)
        if native_search is not None:
            from cochem_base.topos_runner import TOPOSSearchConfig
            native_search = deepcopy(native_search)
            artifact = native_search.pop("artifact", None) or native_search.pop("input_xyz_path", None)
            if artifact not in input_files:
                raise ValueError("Physical conformer search requires its explicit uploaded XYZ artifact")
            if (not {"atom_count", "protocol", "charge", "multiplicity", "threads_per_engine", "max_hours"}.issubset(native_search)
                    or any(type(native_search[field]) is not int for field in ("atom_count", "charge", "multiplicity", "threads_per_engine"))):
                raise ValueError("Physical search requires its explicit uploaded geometry, electronic state and allocation")
            for field in ("scratch_dir", "store_dir", "crest_binary", "orca_binary"):
                if native_search.get(field):
                    raise ValueError("Physical HPC search obtains paths only from the fresh allocation authority")
                native_search.pop(field, None)
            config = TOPOSSearchConfig.model_validate({**native_search, "input_xyz_path": artifact})
            from cochem_base.calc.calculation_service import parse_run_geometry_identity
            from cochem_base.physics.nuclide_resolver import get_element
            identity = parse_run_geometry_identity(input_files[artifact].decode("utf-8-sig"))
            electrons = sum(int(get_element(symbol).atomic_number) for symbol in identity.elements) - config.charge
            if (len(identity.elements) != config.atom_count or electrons <= 0 or config.multiplicity - 1 > electrons
                    or (electrons - config.multiplicity + 1) % 2):
                raise ValueError("Physical search electronic state or atom count differs from its uploaded geometry")
            requested = config.threads_per_engine * (2 if config.protocol == "CREST_GOAT" else 1)
            if requested > resources["cores"] or config.max_hours * 3600 > _seconds(resources["walltime"]):
                raise ValueError("Physical search exceeds the requested compute allocation")
            native_search = config.model_dump(mode="json")
        request_id = str(uuid.uuid4())
        package = self.jobs / request_id
        package.mkdir(parents=True, exist_ok=False)
        for name, contents in input_files.items():
            path = package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        data_descriptor = None
        geometry = calculation["geometry"].encode("utf-8") if calculation is not None else input_files[(provider["artifact"] if provider else native_search["input_xyz_path"])]
        scientific_descriptor = None
        if scientific_inputs is not None:
            from .scientific_inputs import build_bundle, verify_bundle
            geometry_sha256 = hashlib.sha256(geometry).hexdigest()
            if scientific_inputs.get("geometry_sha256") != geometry_sha256:
                raise ValueError("The uploaded scientific evidence belongs to a different original geometry")
            contents, scientific_descriptor = build_bundle(scientific_inputs.get("files"), kind=scientific_inputs["kind"],
                entrypoint=scientific_inputs["entrypoint"], request_id=request_id, geometry_sha256=geometry_sha256)
            verify_bundle(contents, request_id=request_id, geometry_sha256=geometry_sha256,
                          kind=scientific_inputs["kind"], entrypoint=scientific_inputs["entrypoint"])
            (package / "scientific-inputs.zip").write_bytes(contents)
        if ingestion_inputs is not None or periodic_inputs is not None:
            from .student_data_inputs import build_data_bundle
            contents, data_descriptor = build_data_bundle(periodic_inputs if periodic_inputs is not None else ingestion_inputs,
                kind="periodic_inputs" if periodic_inputs is not None else "molecular_ingestion", request_id=request_id,
                geometry_sha256=hashlib.sha256(geometry).hexdigest())
            (package / "data-inputs.zip").write_bytes(contents)
        from cochem_base.config_loader import resolve_config_path
        registry = resolve_config_path(self.registry_path)
        request = {"schema_version": SCHEMA, "request_id": request_id, "scheduler": scheduler, "resources": resources,
            "calculation": calculation, "provider": provider, "native_search": native_search, "data_inputs": data_descriptor,
            "scientific_inputs": scientific_descriptor, "t9_request": deepcopy(t9_request),
            "module_root": str(self.module_root), "source": _source_inventory(), "registry_path": str(registry),
            "provider_receipts": provider_receipts,
            "registry_sha256": _hash(registry), "files": {str(path.relative_to(package)): {"sha256": _hash(path), "size_bytes": path.stat().st_size}
                for path in sorted(package.rglob("*")) if path.is_file()}, "created_at": datetime.now(timezone.utc).isoformat()}
        _write(package / "request.json", request)
        request_sha256 = _hash(package / "request.json")
        script = package / "submit.sh"
        script.write_text(render_batch_script(package, scheduler, resources, request_sha256=request_sha256))
        if scheduler == "slurm":
            raw = _command("sbatch", ["--parsable", "--comment=CoChem-" + request_id, str(script)], cwd=package).strip()
            job_id = raw.split(";", 1)[0]
        else:
            job_id = _command("qsub", ["-v", "COCHEM_HPC_REQUEST_ID=" + request_id, str(script)], cwd=package).strip()
        if not JOB_IDS[scheduler].fullmatch(job_id):
            raise StudentHpcError("Scheduler did not return a valid job ID; inspect its queue before resubmitting")
        submission = {"schema_version": SCHEMA, "request_id": request_id, "scheduler": scheduler, "job_id": job_id,
                      "package": str(package), "request_sha256": request_sha256, "script_sha256": _hash(script),
                      "submitted_at": datetime.now(timezone.utc).isoformat()}
        _write(package / "submission.json", submission)
        return submission

    def _saved(self, submission: dict) -> tuple[Path, dict]:
        if not isinstance(submission, dict) or not isinstance(submission.get("request_id"), str):
            raise StudentHpcError("Select an original saved HPC submission")
        try:
            identity = str(uuid.UUID(submission["request_id"]))
        except ValueError:
            raise StudentHpcError("Invalid HPC request identifier") from None
        package = self.jobs / identity
        if package.is_symlink() or not package.is_dir():
            raise StudentHpcError("HPC submission must retain its original owned package directory")
        saved = strict_json((package / "submission.json").read_bytes())
        if (any(submission.get(key) != value for key, value in saved.items())
                or set(submission) - set(saved) - {"status", "conclusion"}
                or saved.get("package") != str(package) or not JOB_IDS[saved["scheduler"]].fullmatch(saved["job_id"])):
            raise StudentHpcError("Scheduler job differs from the original owned submission")
        if _hash(package / "request.json") != saved["request_sha256"]:
            raise StudentHpcError("Original HPC request changed")
        return package, saved

    def history(self) -> list[dict]:
        if not self.jobs.is_dir():
            return []
        records = []
        for path in sorted(self.jobs.glob("*/submission.json")):
            saved = strict_json(path.read_bytes())
            self._saved(saved)
            records.append(saved)
        return records

    list_submissions = history

    def status(self, submission: dict) -> dict:
        package, saved = self._saved(submission)
        scheduler, job_id = saved["scheduler"], saved["job_id"]
        status, conclusion = "unknown", None
        try:
            if scheduler == "slurm":
                if shutil.which("sacct"):
                    raw = _command("sacct", ["--jobs", job_id, "--noheader", "--parsable2", "--format=JobIDRaw,State,ExitCode"])
                    states = [line.split("|")[1].split()[0] for line in raw.splitlines() if line.split("|")[0] == job_id and len(line.split("|")) >= 3]
                else:
                    raw = _command("squeue", ["--jobs", job_id, "--noheader", "--format=%i|%T"])
                    states = [line.split("|", 1)[1].strip() for line in raw.splitlines() if line.split("|", 1)[0].strip() == job_id]
                state = states[0] if states else "UNKNOWN"
                if state in {"PENDING", "CONFIGURING", "REQUEUED", "SUSPENDED"}:
                    status = "queued"
                elif state in {"RUNNING", "COMPLETING"}:
                    status = "running"
                elif state in {"COMPLETED", "CANCELLED", "FAILED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "PREEMPTED", "BOOT_FAIL", "DEADLINE"}:
                    status, conclusion = "completed", "cancelled" if state == "CANCELLED" else "failure"
            else:
                job = _pbs_record(job_id)
                state = job.get("job_state")
                if state in {"Q", "H", "W", "S"}:
                    status = "queued"
                elif state in {"R", "E"}:
                    status = "running"
                elif state in {"F", "C"}:
                    status, conclusion = "completed", "failure"
        except StudentHpcError:
            pass  # Scheduler history may be purged; sealed worker evidence remains.
        report_path = package / "results/student-result.json"
        if report_path.is_file() and (package / "results/publication-manifest.json").is_file():
            verified = self.retrieve_results(saved)
            report = verified["report"]
            status, conclusion = "completed", "success" if report["status"] == "completed" else "failure"
        return {"status": status, "conclusion": conclusion, "job_id": job_id, "scheduler": scheduler, "request_id": saved["request_id"]}

    def cancel(self, submission: dict) -> None:
        _, saved = self._saved(submission)
        _command("scancel" if saved["scheduler"] == "slurm" else "qdel", [saved["job_id"]])

    def retrieve_results(self, submission: dict) -> dict:
        package, saved = self._saved(submission)
        root = package / "results"
        manifest = strict_json((root / "publication-manifest.json").read_bytes())
        report = strict_json((root / "student-result.json").read_bytes())
        paths = list(root.rglob("*"))
        if (root.is_symlink() or any(path.is_symlink() or not (path.is_file() or path.is_dir()) for path in paths)
                or len(paths) > MAX_FILES or sum(path.stat().st_size for path in paths if path.is_file()) > MAX_BYTES):
            raise StudentHpcError("HPC evidence contains links, special files or an excessive inventory")
        actual = {str(path.relative_to(root)) for path in paths if path.is_file()}
        if (manifest.get("schema_version") != "cochem.hpc-publication/1" or manifest.get("request_sha256") != saved["request_sha256"]
                or any(report.get(key) != saved[key] for key in ("request_id", "job_id", "scheduler"))
                or set(manifest.get("files", {})) | {"publication-manifest.json"} != actual):
            raise StudentHpcError("Retained HPC evidence differs from the original job or complete inventory")
        for name, record in manifest["files"].items():
            path = root / safe_relative_path(name)
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or record != {"sha256": _hash(path), "size_bytes": path.stat().st_size}:
                raise StudentHpcError("Retained HPC result changed: " + name)
        if _hash(root / "request.json") != saved["request_sha256"]:
            raise StudentHpcError("Retained HPC input differs from the submitted request")
        if report.get("status") not in {"completed", "failed"} or type(report.get("operation_performed")) is not bool:
            raise StudentHpcError("HPC worker outcome is not a supported exact completion record")
        if report["status"] == "completed":
            if report.get("operation_performed") is not True or not (root / "allocation-authority.json").is_file():
                raise StudentHpcError("A completed HPC result lacks actual allocation and science evidence")
            allocation = strict_json((root / "allocation-authority.json").read_bytes())
            if any(allocation.get(key) != saved[key] for key in ("request_id", "job_id", "scheduler")):
                raise StudentHpcError("Retained scientific evidence belongs to a different compute allocation")
            if report.get("registry_sha256") != _hash(root / "compute-registry.json"):
                raise StudentHpcError("Completed HPC result lacks its exact fresh compute setup authority")
        return {"path": str(root), "report": report, "files": sorted(actual)}


def _pbs_record(job_id: str) -> dict:
    data = strict_json(_command("qstat", ["-f", "-F", "json", job_id]).encode("utf-8"))
    jobs = data.get("Jobs", {})
    if not isinstance(jobs, dict) or job_id not in jobs or not isinstance(jobs[job_id], dict):
        raise StudentHpcError("OpenPBS did not identify this exact job; its JSON controller protocol is required")
    return jobs[job_id]


def _memory_mb(value: str) -> float:
    """Decode the controller's allocated memory, using binary scheduler units."""
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KMGT]?)(?:i?[bB])?", str(value), re.I)
    if not match:
        raise StudentHpcError("The scheduler did not report verifiable allocated memory")
    factor = {"": 1 / 1024**2, "K": 1 / 1024, "M": 1, "G": 1024, "T": 1024**2}[match[2].upper()]
    return float(match[1]) * factor


def require_allocation(request: dict, package: Path) -> dict:
    """Confirm real scheduler job/owner/node identity before any chemistry call."""
    import pwd
    scheduler = request["scheduler"]
    if scheduler not in JOB_IDS:
        raise StudentHpcError("Unsupported compute allocation scheduler")
    job_id = os.environ.get("SLURM_JOB_ID" if scheduler == "slurm" else "PBS_JOBID", "")
    if not JOB_IDS[scheduler].fullmatch(job_id):
        raise StudentHpcError("A real scheduler compute allocation is required; interface-host execution is forbidden")
    hostname = socket.gethostname().split(".")[0]
    username = pwd.getpwuid(os.getuid()).pw_name
    if scheduler == "slurm":
        raw = _command("scontrol", ["show", "job", "-o", job_id])
        fields = {key: value.strip() for key, value in re.findall(r"(?:^|\s)([A-Za-z_]+)=(.*?)(?=\s+[A-Za-z_]+=|$)", raw)}
        if (fields.get("JobId") != job_id or fields.get("JobState") != "RUNNING"
                or fields.get("UserId") != f"{username}({os.getuid()})" or fields.get("NumNodes") != "1"
                or int(fields.get("NumCPUs", "0")) < request["resources"]["cores"]
                or fields.get("Comment") != "CoChem-" + request["request_id"]
                or fields.get("Command") != str(package / "submit.sh")):
            raise StudentHpcError("Slurm controller did not confirm this owned single-node scientific job")
        nodes = _command("scontrol", ["show", "hostnames", fields.get("NodeList", "")]).splitlines()
        if hostname not in {node.strip().split(".")[0] for node in nodes}:
            raise StudentHpcError("This host is outside the actual Slurm compute allocation")
        allocated = dict(pair.split("=", 1) for pair in fields.get("AllocTRES", fields.get("TRES", "")).split(",") if "=" in pair)
        memory_mb = _memory_mb(allocated.get("mem", ""))
        cores = int(fields["NumCPUs"])
        limit = fields.get("TimeLimit", "")
        if limit in {"UNLIMITED", "Partition_Limit", "N/A"} or _seconds(limit) < _seconds(request["resources"]["walltime"]):
            raise StudentHpcError("Slurm did not confirm the admitted finite allocation walltime")
        controller = fields
    else:
        job = _pbs_record(job_id)
        variables = job.get("Variable_List", {})
        if (job.get("job_state") != "R" or str(job.get("Job_Owner", "")).split("@", 1)[0] != username
                or not isinstance(variables, dict) or variables.get("COCHEM_HPC_REQUEST_ID") != request["request_id"]
                or int(job.get("Resource_List", {}).get("ncpus", "0")) < request["resources"]["cores"]):
            raise StudentHpcError("OpenPBS controller did not confirm this owned compute job")
        nodes = {part.split("/", 1)[0].split(".")[0] for part in str(job.get("exec_host", "")).split("+")}
        if nodes != {hostname}:
            raise StudentHpcError("This host is outside the actual single-node PBS allocation")
        chunks = re.findall(r"\(([^()]+)\)", str(job.get("exec_vnode", "")))
        if not chunks:
            raise StudentHpcError("OpenPBS did not report this actual allocated compute vnode")
        chunk_resources = [dict(part.split("=", 1) for part in chunk.split(":")[1:] if "=" in part) for chunk in chunks]
        memory_mb = sum(_memory_mb(record.get("mem", "")) for record in chunk_resources)
        cores = sum(int(record.get("ncpus", "0")) for record in chunk_resources)
        if cores < request["resources"]["cores"] or _seconds(str(job.get("Resource_List", {}).get("walltime", ""))) < _seconds(request["resources"]["walltime"]):
            raise StudentHpcError("OpenPBS actual allocation is smaller than the admitted CPU/walltime request")
        controller = job
    if memory_mb < request["resources"]["memory_mb"]:
        raise StudentHpcError("The actual scheduler memory allocation is below the admitted scientific budget")
    return {"schema_version": "cochem.hpc-allocation/1", "scheduler": scheduler, "job_id": job_id,
            "request_id": request["request_id"], "hostname": hostname, "username": username,
            "allocated_cores": cores, "allocated_memory_mb": memory_mb,
            "controller_record": controller, "verified_at": datetime.now(timezone.utc).isoformat()}


def _bind_scientific_inputs(request: dict, package: Path, output: Path, registry: Path,
                            calculation: dict) -> dict:
    """Bind sealed originals and a freshly audited allocation interpreter."""
    raw = deepcopy(calculation)
    descriptor = request["scientific_inputs"]
    if descriptor is not None:
        from .scientific_inputs import extract_bundle
        contents = (package / "scientific-inputs.zip").read_bytes()
        if len(contents) != descriptor["bundle_size_bytes"] or hashlib.sha256(contents).hexdigest() != descriptor["bundle_sha256"]:
            raise StudentHpcError("Queued scientific evidence differs from its immutable original ZIP")
        if hashlib.sha256(raw["geometry"].encode()).hexdigest() != descriptor["geometry_sha256"]:
            raise StudentHpcError("Scientific evidence belongs to a different submitted geometry")
        extracted = extract_bundle(contents, output / "scientific-inputs", request_id=request["request_id"],
            geometry_sha256=descriptor["geometry_sha256"], kind=descriptor["kind"], entrypoint=descriptor["entrypoint"])
        _write(output / "scientific-inputs.json", {"manifest": extracted["manifest"], "manifest_sha256": extracted["manifest_sha256"],
            "paths": {name: str(path) for name, path in extracted["paths"].items()},
            "entrypoint_path": str(extracted["entrypoint_path"]), "scientific_validation_performed": False})
        field = "r2_reference_manifest" if descriptor["kind"] == "r2_reference" else "hessian_file"
        raw[field] = str(extracted["entrypoint_path"])
    if request["t9_request"] is not None:
        from cochem_base.core_engine.execution_authority import authorize_engine_execution
        recovery = deepcopy(request["t9_request"])
        authority = authorize_engine_execution("pyscf", registry_path=registry, cores=recovery["threads"],
            maxcore_mb=math.ceil(recovery["memory_mb"] / recovery["threads"]))
        recovery["python_executable"] = authority.executable
        raw["t9_fallback"] = recovery
    from cochem_base.calc.calculation_service import CalculationMatrixConfig
    from .scientific_jobs import validate_job_configuration
    model = CalculationMatrixConfig.model_validate_json(canonical_json(raw), strict=True)
    validate_job_configuration(model)
    return model.model_dump(mode="json")


def _verify_native_result(result: dict, output: Path, registry: Path) -> None:
    """Retain actual completed scientific telemetry, including qualified T9."""
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    if result.get("status") == "T9_FALLBACK_VERIFIED":
        if result.get("original_single_reference_rejected") is not True:
            raise StudentHpcError("T9 recovery lacks explicit rejection of the original single-reference result")
        accepted = result["fallback"]
        source = output / "native/t9/t9_input.json"
        if _hash(source) != accepted.get("input_sha256"):
            raise StudentHpcError("Recovered T9 result differs from its actual native input")
        geometry = strict_json(source.read_bytes())["coordinates_angstrom"]
    elif result.get("status") == "EXECUTION_VERIFIED":
        accepted = strict_json((output / "native/result.json").read_bytes())
        if accepted.get("scf_converged", accepted.get("converged")) is not True:
            raise StudentHpcError("Allocated native result is not converged")
        geometry = accepted["coordinates_angstrom"]
    else:
        raise StudentHpcError("Allocated native calculation did not complete with genuine accepted science")
    energy = accepted.get("energy_hartree")
    if type(energy) not in (int, float) or not math.isfinite(energy):
        raise StudentHpcError("Allocated result lacks a finite measured energy")
    store = Path(accepted["telemetry_path"])
    if store.is_symlink() or not store.is_file():
        raise StudentHpcError("The native scientific archive must be an actual regular file")
    data = read_scientific_results(accepted["telemetry_job_id"], store_path=store)
    if (not len(data["energy_hartree"]) or float(data["energy_hartree"][-1]) != energy
            or data["nuclides"] != accepted["nuclides"]
            or data["coordinates_angstrom"][-1].tolist() != geometry
            or result["status"] == "T9_FALLBACK_VERIFIED" and data["metadata"][-1].get("tier") != "T9"):
        raise StudentHpcError("Allocated native result contradicts its actual scientific telemetry")
    digest = _hash(store)
    shutil.copy2(store, output / "complexes.h5")
    if _hash(store) != digest or _hash(output / "complexes.h5") != digest:
        raise StudentHpcError("The completed native archive changed during result retention")
    _write(output / "telemetry-publication.json", {"archive": "complexes.h5", "sha256": digest,
        "telemetry_job_id": accepted["telemetry_job_id"], "original_runner_store": str(store),
        "registry": "compute-registry.json", "registry_sha256": _hash(registry)})


def execute_staged(package: Path, *, request_sha256: str) -> dict:
    """Worker entry point. No branch launches chemistry before allocation audit."""
    request = _load_package(package, integrity=request_sha256)
    package = package.resolve()
    result_root = package / "results"
    result_root.mkdir(exist_ok=False)
    shutil.copy2(package / "request.json", result_root / "request.json")
    report = {"schema_version": "cochem.hpc-result/1", "request_id": request["request_id"],
        "scheduler": request["scheduler"], "job_id": os.environ.get("SLURM_JOB_ID" if request["scheduler"] == "slurm" else "PBS_JOBID"),
        "status": "failed", "operation_performed": False, "resources": request["resources"]}
    try:
        allocation = require_allocation(request, package)
        _write(result_root / "allocation-authority.json", allocation)
        from cochem_base.orchestrator.bootstrap_service import run_setup
        from cochem_base.core.cochem_core_registry_manager import load_system_config
        submitting = Path(request["registry_path"])
        if _hash(submitting) != request["registry_sha256"]:
            raise StudentHpcError("Submitting setup authority changed while this job was queued")
        source_config = load_system_config(submitting).model_dump(mode="json")
        bindings = {"orca": "COCHEM_ORCA_BIN", "cfour": "COCHEM_CFOUR_BIN", "xtb": "XTB_CMD", "crest": "CREST_CMD", "qe": "QE_CMD"}
        for engine, variable in bindings.items():
            found = source_config.get("engines", {}).get(engine, {})
            if found.get("path"):
                os.environ[variable] = found["path"]
        runtime = package / "allocation-runtime"
        os.environ.update(COCHEM_ARTIFACT_DIR=str(runtime), COCHEM_ARTIFACTS=str(runtime),
                          COCHEM_CONFIG=str(runtime / "Registry/cochem_system_config.json"))
        setup = run_setup(runtime, skip_heavy=True)
        _write(result_root / "compute-setup.json", setup)
        registry = Path(os.environ["COCHEM_CONFIG"])
        shutil.copy2(registry, result_root / "compute-registry.json")
        resources = request["resources"]
        if request["provider_receipts"]:
            from scripts.manage_modules import DEFAULT_MANIFEST, load_manifest, verify_installation
            catalog = load_manifest(DEFAULT_MANIFEST)
            module_root = Path(request["module_root"])
            for name, identity in request["provider_receipts"].items():
                if name not in {"topos", "torq"}:
                    raise StudentHpcError("Unexpected queued provider identity")
                receipt = verify_installation(name, catalog["modules"][name], module_root)
                if identity != {"revision": receipt["revision"], "receipt_sha256": _hash(module_root / name / "installation.json")}:
                    raise StudentHpcError("Installed provider changed while this job was queued; resubmit")
        maxcore = int(resources["memory_mb"] * .75) // resources["cores"]
        local = deepcopy(request)
        local["files"] = {name: {"content_base64": base64.b64encode((package / name).read_bytes()).decode(), **identity}
                          for name, identity in request["files"].items() if name.startswith("inputs/")}
        if request["data_inputs"] is not None:
            from .student_data_inputs import extract_data_bundle
            descriptor = request["data_inputs"]
            bundle = extract_data_bundle((package / "data-inputs.zip").read_bytes(), result_root / "data-inputs",
                request_id=request["request_id"], geometry_sha256=descriptor["geometry_sha256"], kind=descriptor["kind"])
            _write(result_root / "data-inputs.json", bundle)
        from .student_original_inputs import bind_original_inputs
        if local["native_search"] is not None:
            selection = deepcopy(local)
            selection["calculation"] = {"geometry": (package / local["native_search"]["input_xyz_path"]).read_text(encoding="utf-8-sig"),
                "charge": local["native_search"]["charge"], "multiplicity": local["native_search"]["multiplicity"]}
            bind_original_inputs(selection, result_root)
            bound = None
        else:
            bound = bind_original_inputs(local, result_root)
        if bound is not None:
            from cochem_base.calc.calculation_service import run_calculation
            bound = _bind_scientific_inputs(request, package, result_root, registry, bound)
            config_path = result_root / "allocation-calculation.json"
            _write(config_path, bound)
            result = run_calculation(config_path, registry_path=registry, threads=resources["cores"], maxcore_mb=maxcore,
                device="cpu", scratch=runtime / "Scratch", output=result_root / "native")
            _verify_native_result(result, result_root, registry)
        elif local["provider"] is not None:
            from .student_research import execute_provider_request
            result = execute_provider_request(local["provider"], package, result_root / "provider", registry=registry,
                root=Path(request["module_root"]), resources={"cores": resources["cores"], "memory_mb": int(resources["memory_mb"] * .75),
                                                           "budget_seconds": _seconds(resources["walltime"])})
            if result.get("status") != "completed" or result.get("operation_performed") is not True:
                raise StudentHpcError("Allocated scientific provider did not complete")
        else:
            from cochem_base.topos_runner import TOPOSExecutionBroker, TOPOSSearchConfig
            config = deepcopy(local["native_search"])
            config["input_xyz_path"] = str(package / config["input_xyz_path"])
            broker = TOPOSExecutionBroker(runtime / "Scratch", result_root / "conformer")
            job_id = broker.launch_search(TOPOSSearchConfig.model_validate(config))
            while True:
                result = broker.poll_telemetry(job_id)
                if result["status"] != "RUNNING":
                    break
                time.sleep(.25)
            if result["status"] != "COMPLETED":
                raise StudentHpcError("Allocated physical conformer search did not complete")
            promoted = broker.promote_artifacts(job_id)
            result["artifact_directory"] = str(promoted["promoted_dir"])
        _verify_source(request["source"])
        report.update(status="completed", operation_performed=True, result=result,
                      registry_sha256=_hash(registry), authority="measured_compute_node")
        return report
    except BaseException as error:
        report.update(error=str(error), error_type=type(error).__name__)
        raise
    finally:
        _write(result_root / "student-result.json", report)
        files = list(result_root.rglob("*"))
        if any(path.is_symlink() for path in files) or len(files) > MAX_FILES or sum(path.stat().st_size for path in files if path.is_file()) > MAX_BYTES:
            raise StudentHpcError("HPC results exceed bounded publication or contain links")
        _write(result_root / "publication-manifest.json", {"schema_version": "cochem.hpc-publication/1",
            "request_sha256": _hash(package / "request.json"), "files": {str(path.relative_to(result_root)):
            {"sha256": _hash(path), "size_bytes": path.stat().st_size} for path in files if path.is_file()}})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    execute_staged(args.execute, request_sha256=args.request_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
